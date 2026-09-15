# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Cas d'usage : assembler le serveur HTTP a partir de la configuration
et des ports du conteneur de dependances - point unique ou le resolveur
de chemin, le serveur et (si l'option waf est active) les
collaborateurs WAF sont cables ensemble.

`build_waf_collaborators` est expose separement (pas seulement appele
depuis `build_server`) : le CLI en a aussi besoin sans demarrer de
serveur reel, pour `waf test` (simulateur) et la gestion de blocklist -
memes objets reels, jamais une reconstruction paralelle."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from omega_serv.domain.config.entities import OmegaServConfig
from omega_serv.domain.routing.proxy_zone import ProxyRoundRobinState
from omega_serv.domain.routing.zone_resolver import Zone
from omega_serv.domain.security.active_defense.config import (
    ActiveDefenseConfig,
    parse_active_defense_config,
)
from omega_serv.domain.security.auth.entities import AuthZone, UserAccount
from omega_serv.domain.security.waf.config import WafConfig, parse_waf_config
from omega_serv.infrastructure.active_defense.asyncio_delay_scheduler import AsyncioDelayScheduler
from omega_serv.infrastructure.auth.auth_zones_repository import JsonAuthZonesRepository
from omega_serv.infrastructure.auth.users_repository import JsonUsersRepository
from omega_serv.infrastructure.clock.system_clock import SystemClock
from omega_serv.infrastructure.decoys.in_process_fixture_dispatcher import (
    InProcessFixtureDispatcher,
)
from omega_serv.infrastructure.fastcgi.asyncio_fastcgi_client import AsyncioFastCgiClient
from omega_serv.infrastructure.filesystem.safe_path_resolver import SafePathResolver
from omega_serv.infrastructure.persistence.sqlite_active_defense_connection import (
    open_active_defense_connection,
)
from omega_serv.infrastructure.persistence.sqlite_deception_assignment_repository import (
    SqliteDeceptionAssignmentRepository,
)
from omega_serv.infrastructure.persistence.sqlite_incident_repository import (
    SqliteIncidentRepository,
)
from omega_serv.infrastructure.persistence.sqlite_threat_state_repository import (
    SqliteThreatStateRepository,
)
from omega_serv.infrastructure.proxy.asyncio_http_proxy_client import AsyncioHttpProxyClient
from omega_serv.infrastructure.server.asyncio_server import AsyncioHttpServer
from omega_serv.infrastructure.waf.blocklist_store import JsonBlocklistStore
from omega_serv.infrastructure.waf.python_waf_engine import PythonWafEngine
from omega_serv.infrastructure.waf.rate_limit_store import InMemoryRateLimitStore
from omega_serv.infrastructure.waf.reputation_tracker import InMemoryReputationTracker
from omega_serv.infrastructure.waf.rule_pack_loader import load_rule_packs
from omega_serv.ports.auth_zones_repository_port import AuthZonesRepositoryPort
from omega_serv.ports.blocklist_port import BlocklistPort
from omega_serv.ports.clock_port import ClockPort
from omega_serv.ports.deception_assignment_repository_port import DeceptionAssignmentRepositoryPort
from omega_serv.ports.decoy_dispatch_port import DecoyDispatchPort
from omega_serv.ports.delay_scheduler_port import DelaySchedulerPort
from omega_serv.ports.filesystem_port import FilesystemPort
from omega_serv.ports.http_proxy_client_port import HttpProxyClientPort
from omega_serv.ports.incident_repository_port import IncidentRepositoryPort
from omega_serv.ports.logger_port import LoggerPort
from omega_serv.ports.rate_limit_port import RateLimitPort
from omega_serv.ports.reputation_tracker_port import ReputationTrackerPort
from omega_serv.ports.threat_state_repository_port import ThreatStateRepositoryPort
from omega_serv.ports.users_repository_port import UsersRepositoryPort
from omega_serv.ports.waf_port import WafPort


@dataclass(frozen=True)
class WafCollaborators:
    config: WafConfig
    waf_port: WafPort
    blocklist_port: BlocklistPort
    rate_limit_port: RateLimitPort
    reputation_tracker: ReputationTrackerPort
    alert_log_path: Path


def build_waf_collaborators(
    config: OmegaServConfig,
    project_root: Path,
    filesystem: FilesystemPort,
    clock: ClockPort,
    force: bool = False,
) -> WafCollaborators | None:
    """`force=True` construit les collaborateurs meme si l'option "waf"
    est desactivee - utilise par `omega-serv waf test` (doc WAF,
    "Tests WAF" : le simulateur doit permettre de tester des regles
    AVANT de les activer en production, pas seulement une fois actives)."""
    if not force and not config.option_enabled("waf"):
        return None
    if "waf" not in config.options:
        return None
    waf_config = parse_waf_config(config.options["waf"].settings)
    rule_paths = tuple(project_root / p for p in waf_config.rule_paths)
    compiled_packs = load_rule_packs(filesystem, rule_paths)
    return WafCollaborators(
        config=waf_config,
        waf_port=PythonWafEngine(compiled_packs, waf_config),
        blocklist_port=JsonBlocklistStore(filesystem, project_root / waf_config.blocklist.path, clock),
        rate_limit_port=InMemoryRateLimitStore(clock),
        reputation_tracker=InMemoryReputationTracker(clock),
        alert_log_path=project_root / waf_config.logging.path,
    )


@dataclass(frozen=True)
class ActiveDefenseCollaborators:
    config: ActiveDefenseConfig
    threat_state_repository: ThreatStateRepositoryPort
    incident_repository: IncidentRepositoryPort
    deception_assignment_repository: DeceptionAssignmentRepositoryPort
    decoy_dispatch_port: DecoyDispatchPort
    delay_scheduler: DelaySchedulerPort
    enriched_log_path: Path
    decoy_proxy_client: HttpProxyClientPort


def build_active_defense_collaborators(
    config: OmegaServConfig,
    project_root: Path,
) -> ActiveDefenseCollaborators | None:
    """Meme patron exact que build_waf_collaborators - seul point de
    construction reel de la connexion sqlite (plan_active_defense_omega_
    serv.md, Phase 1/2/3). N'ouvre la connexion QUE si l'option est active -
    jamais un fichier sqlite cree par simple presence de la cle dans le
    JSON. Les trois repositories PARTAGENT la MEME connexion (meme
    fichier .sqlite3, jamais deux connexions separees vers la meme base).
    `decoy_dispatch_port` est toujours l'InProcessFixtureDispatcher (Niveau
    1). `decoy_proxy_client` sert au Niveau 2 (Phase 5, "Routage vers les
    leurres") - construit inconditionnellement des qu'active_defense est
    actif (comme les 3 repositories), jamais partage avec le
    `proxy_client` de production (`options.reverse_proxy`, construit
    separement dans `build_server` ci-dessous) : les deux clients
    peuvent coexister sans jamais se meler."""
    if not config.option_enabled("active_defense"):
        return None
    if "active_defense" not in config.options:
        return None
    active_defense_config = parse_active_defense_config(config.options["active_defense"].settings)
    connection = open_active_defense_connection(project_root / active_defense_config.storage.database)
    return ActiveDefenseCollaborators(
        config=active_defense_config,
        threat_state_repository=SqliteThreatStateRepository(connection),
        incident_repository=SqliteIncidentRepository(connection),
        deception_assignment_repository=SqliteDeceptionAssignmentRepository(connection),
        decoy_dispatch_port=InProcessFixtureDispatcher(),
        delay_scheduler=AsyncioDelayScheduler(),
        enriched_log_path=project_root / active_defense_config.logging.log_path,
        decoy_proxy_client=AsyncioHttpProxyClient(),
    )


def build_blocklist_port(
    config: OmegaServConfig,
    project_root: Path,
    filesystem: FilesystemPort,
    clock: ClockPort,
) -> BlocklistPort:
    """Construit un BlocklistPort utilisable meme si l'option "waf" est
    desactivee - la blocklist est un etat independant, gerable en CLI
    (menu "Gestion blocklist") avant meme d'activer le WAF."""
    settings = config.options["waf"].settings if "waf" in config.options else {}
    waf_config = parse_waf_config(settings)
    return JsonBlocklistStore(filesystem, project_root / waf_config.blocklist.path, clock)


@dataclass(frozen=True)
class AuthCollaborators:
    zones: tuple[Zone[AuthZone], ...]
    users_by_name: Mapping[str, UserAccount]


def build_users_repository(config: OmegaServConfig, project_root: Path, filesystem: FilesystemPort) -> UsersRepositoryPort:
    return JsonUsersRepository(filesystem, project_root / config.paths.auth_file)


def build_auth_zones_repository(config: OmegaServConfig, project_root: Path, filesystem: FilesystemPort) -> AuthZonesRepositoryPort:
    return JsonAuthZonesRepository(filesystem, project_root / config.paths.auth_zones)


def build_auth_collaborators(
    config: OmegaServConfig,
    project_root: Path,
    filesystem: FilesystemPort,
) -> AuthCollaborators | None:
    if not config.option_enabled("auth"):
        return None
    zones = build_auth_zones_repository(config, project_root, filesystem).load()
    users = build_users_repository(config, project_root, filesystem).load()
    return AuthCollaborators(
        zones=tuple(Zone(z.path_prefix, z) for z in zones),
        users_by_name={u.username: u for u in users},
    )


def build_server(
    config: OmegaServConfig,
    project_root: Path,
    filesystem: FilesystemPort,
    logger: LoggerPort,
    clock: ClockPort | None = None,
) -> AsyncioHttpServer:
    clock = clock or SystemClock()
    webroot = project_root / config.paths.webroot
    path_resolver = SafePathResolver(filesystem, webroot)

    waf = build_waf_collaborators(config, project_root, filesystem, clock)

    ssl_context = None
    if config.tls.enabled and config.tls.mode == "direct":
        from omega_serv.infrastructure.tls.ssl_context_builder import build_ssl_context
        ssl_context = build_ssl_context(config.tls, project_root)

    auth = build_auth_collaborators(config, project_root, filesystem)
    active_defense = build_active_defense_collaborators(config, project_root)

    fastcgi_client = AsyncioFastCgiClient() if config.option_enabled("fastcgi") else None
    proxy_client = AsyncioHttpProxyClient() if config.option_enabled("reverse_proxy") else None
    proxy_round_robin = ProxyRoundRobinState() if proxy_client is not None else None
    proxy_client_ssl_context_verified = None
    proxy_client_ssl_context_unverified = None
    if proxy_client is not None:
        # Import local, pas en tete de module - meme raison que
        # build_ssl_context ci-dessus : bootstrap/container.py atteint
        # build_waf_collaborators (meme fichier) transitivement, et
        # bootstrap/ est protege par le contrat import-linter "ssl
        # seulement dans infrastructure.tls.ssl_context_builder" (voir
        # OMEGA-SERV_PLAN-DETAILLE_REVERSE_PROXY.md §5.3/§12).
        from omega_serv.infrastructure.tls.ssl_context_builder import build_client_ssl_context
        proxy_client_ssl_context_verified = build_client_ssl_context(verify_upstream_tls=True)
        proxy_client_ssl_context_unverified = build_client_ssl_context(verify_upstream_tls=False)

    return AsyncioHttpServer(
        config=config,
        path_resolver=path_resolver,
        filesystem=filesystem,
        logger=logger,
        access_log_path=project_root / config.logs.access,
        error_log_path=project_root / config.logs.error,
        project_root=project_root,
        waf_config=waf.config if waf else None,
        waf_port=waf.waf_port if waf else None,
        blocklist_port=waf.blocklist_port if waf else None,
        rate_limit_port=waf.rate_limit_port if waf else None,
        reputation_tracker=waf.reputation_tracker if waf else None,
        waf_alert_log_path=waf.alert_log_path if waf else None,
        ssl_context=ssl_context,
        auth_zones=auth.zones if auth else (),
        users_by_name=auth.users_by_name if auth else None,
        fastcgi_client=fastcgi_client,
        proxy_client=proxy_client,
        proxy_round_robin=proxy_round_robin,
        proxy_client_ssl_context_verified=proxy_client_ssl_context_verified,
        proxy_client_ssl_context_unverified=proxy_client_ssl_context_unverified,
        active_defense_config=active_defense.config if active_defense else None,
        threat_state_repository=active_defense.threat_state_repository if active_defense else None,
        incident_repository=active_defense.incident_repository if active_defense else None,
        deception_assignment_repository=active_defense.deception_assignment_repository if active_defense else None,
        decoy_dispatch_port=active_defense.decoy_dispatch_port if active_defense else None,
        delay_scheduler=active_defense.delay_scheduler if active_defense else None,
        active_defense_enriched_log_path=active_defense.enriched_log_path if active_defense else None,
        decoy_proxy_client=active_defense.decoy_proxy_client if active_defense else None,
        clock=clock,
    )


def reload_server(
    server: AsyncioHttpServer,
    config: OmegaServConfig,
    project_root: Path,
    filesystem: FilesystemPort,
    clock: ClockPort | None = None,
) -> None:
    """Rechargement a chaud borne (SIGHUP, angle mort §9.1) : recompile
    les regles WAF et recharge zones/utilisateurs Auth depuis la
    configuration donnee, sans jamais toucher au socket d'ecoute ni au
    contexte TLS (voir AsyncioHttpServer.reload_scoped - la meme regle
    "pas de changement de bind/port/certificat sans restart complet"
    s'applique ici, ce cas d'usage ne fait que rassembler les
    collaborateurs, la garantie est imposee cote serveur).

    Active Defense N'EST PAS rechargee a chaud ici (plan_active_defense_
    omega_serv.md, Phase 1 - limitation deliberee de cette premiere
    integration, pas un oubli) : un changement de `options.active_defense`
    necessite un restart complet pour l'instant, `reload_scoped()` ne
    touche jamais `_active_defense_config`/`_threat_state_repository`."""
    clock = clock or SystemClock()
    waf = build_waf_collaborators(config, project_root, filesystem, clock)
    auth = build_auth_collaborators(config, project_root, filesystem)

    server.reload_scoped(
        config=config,
        waf_config=waf.config if waf else None,
        waf_port=waf.waf_port if waf else None,
        blocklist_port=waf.blocklist_port if waf else None,
        rate_limit_port=waf.rate_limit_port if waf else None,
        reputation_tracker=waf.reputation_tracker if waf else None,
        waf_alert_log_path=waf.alert_log_path if waf else None,
        auth_zones=auth.zones if auth else (),
        users_by_name=auth.users_by_name if auth else None,
    )
