# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Serveur HTTP/1.1 asyncio (spec §10.2 : modele de concurrence retenu
en Phase 0). Boucle de connexion minimale Phase 1 : lit une requete,
la route, ecrit la reponse, repete en keep-alive dans les limites
configurees. Le durcissement complet (methodes interdites explicitement,
ambiguites protocolaires avancees) est un chantier de la Phase 2 - ce
module applique deja les limites de base deja configurees (spec Phase 1 :
"limites de base") sans anticiper le reste.
"""
from __future__ import annotations

import asyncio
import random
import time
import uuid
from collections.abc import Mapping
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import ssl

from omega_serv.application.active_defense.manage_deception import (
    assign_deception,
    resolve_routing_decision,
)
from omega_serv.application.active_defense.manage_incidents import create_or_update_incident
from omega_serv.application.active_defense.observe_threat import observe_threat
from omega_serv.application.security.evaluate_waf_request import evaluate_waf_request
from omega_serv.application.server.resolve_error_page import resolve_error_page_body
from omega_serv.application.server.route_request import route_request
from omega_serv.application.server.serve_proxy import serve_proxy
from omega_serv.application.server.serve_websocket_proxy import serve_websocket_proxy
from omega_serv.domain.config.entities import OmegaServConfig
from omega_serv.domain.http.headers import HttpHeaders
from omega_serv.domain.http.request import HttpRequest, split_request_target
from omega_serv.domain.http.response import HttpResponse
from omega_serv.domain.http.status_codes import HttpStatus, reason_phrase_for
from omega_serv.domain.http.websocket import is_websocket_upgrade_request
from omega_serv.domain.logging.access_log_format import (
    AccessLogEntry,
    format_combined_log_line,
    format_error_log_line,
)
from omega_serv.domain.logging.active_defense_enriched_log_format import (
    EnrichedLogEntry,
    format_enriched_log_line,
)
from omega_serv.domain.logging.waf_alert_format import WafAlertEntry, format_waf_alert_line
from omega_serv.domain.routing.access_rule import (
    AccessRule,
    parse_access_rules,
    resolve_access_verdict,
)
from omega_serv.domain.routing.proxy_zone import (
    ProxyRoundRobinState,
    ProxyZone,
    parse_proxy_zones,
    resolve_proxy_zone,
)
from omega_serv.domain.routing.zone_resolver import Zone
from omega_serv.domain.security.access_policy import is_method_allowed, validate_host_header
from omega_serv.domain.security.active_defense.config import ActiveDefenseConfig
from omega_serv.domain.security.active_defense.entities import (
    DefensePlaybook,
    RoutingDecision,
    ThreatState,
)
from omega_serv.domain.security.active_defense.policies import (
    build_playbook,
    compute_slowdown_delay_ms,
    hash_payload,
    is_source_marked,
    validate_playbook_action,
)
from omega_serv.domain.security.active_defense.value_objects import AttackClass
from omega_serv.domain.security.auth.authorize import authorize_request
from omega_serv.domain.security.auth.basic_auth import build_www_authenticate_header
from omega_serv.domain.security.auth.entities import AuthZone, UserAccount
from omega_serv.domain.security.security_headers import apply_security_headers
from omega_serv.domain.security.trusted_proxy import normalize_ip, resolve_client_ip
from omega_serv.domain.security.waf.config import WafConfig
from omega_serv.domain.security.waf.entities import WafDecision
from omega_serv.infrastructure.clock.system_clock import SystemClock
from omega_serv.infrastructure.filesystem.safe_path_resolver import SafePathResolver
from omega_serv.infrastructure.server.http_parser import (
    RAW_LINE_BUFFER_LIMIT,
    ConnectionClosedCleanly,
    HttpParseError,
    read_and_discard_body,
    read_request_head,
)
from omega_serv.ports.blocklist_port import BlocklistPort
from omega_serv.ports.clock_port import ClockPort
from omega_serv.ports.deception_assignment_repository_port import DeceptionAssignmentRepositoryPort
from omega_serv.ports.decoy_dispatch_port import DecoyDispatchPort
from omega_serv.ports.delay_scheduler_port import DelaySchedulerPort
from omega_serv.ports.fastcgi_client_port import FastCgiClientPort
from omega_serv.ports.filesystem_port import FilesystemPort
from omega_serv.ports.http_proxy_client_port import HttpProxyClientPort
from omega_serv.ports.incident_repository_port import IncidentRepositoryPort
from omega_serv.ports.logger_port import LoggerPort
from omega_serv.ports.rate_limit_port import RateLimitPort
from omega_serv.ports.reputation_tracker_port import ReputationTrackerPort
from omega_serv.ports.threat_state_repository_port import ThreatStateRepositoryPort
from omega_serv.ports.waf_port import WafPort


class AsyncioHttpServer:
    def __init__(
        self,
        config: OmegaServConfig,
        path_resolver: SafePathResolver,
        filesystem: FilesystemPort,
        logger: LoggerPort,
        access_log_path: Path,
        error_log_path: Path,
        project_root: Path,
        waf_config: WafConfig | None = None,
        waf_port: WafPort | None = None,
        blocklist_port: BlocklistPort | None = None,
        rate_limit_port: RateLimitPort | None = None,
        reputation_tracker: ReputationTrackerPort | None = None,
        waf_alert_log_path: Path | None = None,
        ssl_context: ssl.SSLContext | None = None,
        auth_zones: tuple[Zone[AuthZone], ...] = (),
        users_by_name: Mapping[str, UserAccount] | None = None,
        fastcgi_client: FastCgiClientPort | None = None,
        proxy_client: HttpProxyClientPort | None = None,
        proxy_round_robin: ProxyRoundRobinState | None = None,
        proxy_client_ssl_context_verified: ssl.SSLContext | None = None,
        proxy_client_ssl_context_unverified: ssl.SSLContext | None = None,
        active_defense_config: ActiveDefenseConfig | None = None,
        threat_state_repository: ThreatStateRepositoryPort | None = None,
        incident_repository: IncidentRepositoryPort | None = None,
        deception_assignment_repository: DeceptionAssignmentRepositoryPort | None = None,
        decoy_dispatch_port: DecoyDispatchPort | None = None,
        delay_scheduler: DelaySchedulerPort | None = None,
        active_defense_enriched_log_path: Path | None = None,
        decoy_proxy_client: HttpProxyClientPort | None = None,
        clock: ClockPort | None = None,
    ):
        self._config = config
        self._path_resolver = path_resolver
        self._filesystem = filesystem
        self._logger = logger
        self._access_log_path = access_log_path
        self._error_log_path = error_log_path
        self._project_root = project_root
        # Tous None quand l'option "waf" est desactivee (defaut) - voir
        # application/server/start_server.py::build_server, seul point
        # ou ces collaborateurs sont construits.
        self._waf_config = waf_config
        self._waf_port = waf_port
        self._blocklist_port = blocklist_port
        self._rate_limit_port = rate_limit_port
        self._reputation_tracker = reputation_tracker
        self._waf_alert_log_path = waf_alert_log_path
        self._ssl_context = ssl_context
        self._auth_zones = auth_zones
        self._users_by_name = users_by_name or {}
        self._fastcgi_client = fastcgi_client
        self._proxy_client = proxy_client
        self._proxy_round_robin = proxy_round_robin or ProxyRoundRobinState()
        self._proxy_client_ssl_context_verified = proxy_client_ssl_context_verified
        self._proxy_client_ssl_context_unverified = proxy_client_ssl_context_unverified
        # None quand l'option "active_defense" est desactivee (defaut) ou
        # que war_mode ne l'est pas - voir application/server/
        # start_server.py::build_active_defense_collaborators, seul point
        # ou ces collaborateurs sont construits. Pas de rechargement a
        # chaud (SIGHUP) pour cette option en V1 - reload_scoped() ne la
        # touche pas encore, un changement necessite un restart complet,
        # documente comme tel plutot que fait a moitie.
        self._active_defense_config = active_defense_config
        self._threat_state_repository = threat_state_repository
        self._incident_repository = incident_repository
        self._deception_assignment_repository = deception_assignment_repository
        self._decoy_dispatch_port = decoy_dispatch_port
        self._delay_scheduler = delay_scheduler
        self._active_defense_enriched_log_path = active_defense_enriched_log_path
        # Niveau 2 (plan Phase 5) : client + etat de repartition DEDIES
        # aux leurres, jamais partages avec self._proxy_client/
        # self._proxy_round_robin (production) - une zone leurre ne vit
        # jamais dans le meme espace de configuration qu'une zone
        # reverse_proxy de production (voir DeceptionConfig.decoy_zones).
        self._decoy_proxy_client = decoy_proxy_client
        self._decoy_round_robin = ProxyRoundRobinState()
        # Construit une seule fois (jamais a chaque requete) - coherent
        # avec le fait qu'Active Defense n'est pas rechargeable a chaud
        # (SIGHUP) en V1, voir le commentaire ci-dessus sur
        # `_active_defense_config`.
        self._active_defense_playbook: DefensePlaybook | None = (
            build_playbook(active_defense_config.war_mode) if active_defense_config is not None else None
        )
        self._clock = clock or SystemClock()
        self._server: asyncio.Server | None = None
        self._active_connections: set[asyncio.Task] = set()
        # Retour utilisateur (audit performance, 2026-09-14) : les regles
        # de controle d'acces (et les zones de proxy websocket) etaient
        # reconstruites (parse_access_rules/parse_proxy_zones) a CHAQUE
        # requete, alors que la config ne change qu'au rechargement
        # (SIGHUP) - travail 100% redondant repete a chaque requete a
        # charge elevee. Meme principe deja applique ci-dessus a
        # `_active_defense_playbook` : calcule une seule fois ici et
        # invalide/recalcule uniquement dans reload_scoped().
        self._access_control_rules_cache: list[AccessRule] = self._parse_access_control_rules()
        self._websocket_proxy_zones_cache: list[ProxyZone] = self._parse_websocket_proxy_zones()

    @property
    def sockets(self) -> tuple:
        assert self._server is not None
        return self._server.sockets

    async def start(self) -> None:
        server_config = self._config.server
        self._server = await asyncio.start_server(
            self._handle_connection_tracked,
            host=server_config.bind,
            port=server_config.port,
            backlog=server_config.listen_backlog,
            limit=RAW_LINE_BUFFER_LIMIT,
            ssl=self._ssl_context,
        )

    async def serve_forever(self) -> None:
        assert self._server is not None
        async with self._server:
            await self._server.serve_forever()

    async def close(self) -> None:
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()

    def reload_scoped(
        self,
        config: OmegaServConfig,
        waf_config: WafConfig | None,
        waf_port: WafPort | None,
        blocklist_port: BlocklistPort | None,
        rate_limit_port: RateLimitPort | None,
        reputation_tracker: ReputationTrackerPort | None,
        waf_alert_log_path: Path | None,
        auth_zones: tuple[Zone[AuthZone], ...],
        users_by_name: Mapping[str, UserAccount] | None,
    ) -> None:
        """Rechargement a chaud borne (decision transverse "Reload
        scope", plan de developpement §6) : remplace la configuration
        et les collaborateurs WAF/Auth deja compiles/charges en memoire,
        sans jamais toucher au socket d'ecoute, au contexte TLS ni au
        bind/port - un changement la-dessus exige un restart complet,
        documente comme tel (jamais fait ici). Declenche par SIGHUP
        (angle mort §9.1), voir interfaces/cli/main.py::cmd_serve."""
        self._config = config
        self._waf_config = waf_config
        self._waf_port = waf_port
        self._blocklist_port = blocklist_port
        self._rate_limit_port = rate_limit_port
        self._reputation_tracker = reputation_tracker
        self._waf_alert_log_path = waf_alert_log_path
        self._auth_zones = auth_zones
        self._users_by_name = users_by_name or {}
        # Recalcule les caches derives de la config (voir __init__) -
        # sans ceci, un changement de access_control/reverse_proxy via
        # SIGHUP resterait invisible jusqu'au prochain redemarrage
        # complet, silencieusement, alors que ces options sont deja
        # documentees comme rechargeables a chaud.
        self._access_control_rules_cache = self._parse_access_control_rules()
        self._websocket_proxy_zones_cache = self._parse_websocket_proxy_zones()

    async def shutdown(self, grace_period_seconds: float) -> int:
        """Arret propre (angle mort §9.2, meme patron "signal -> attente
        bornee -> escalade" que omega-fire::kill_lnav()) : arrete
        d'accepter de nouvelles connexions, draine celles en cours
        jusqu'a `grace_period_seconds`, puis annule de force les
        restantes en journalisant un avertissement. Retourne le nombre
        de connexions fermees de force (0 si toutes terminees
        naturellement) - distinct de close() (fermeture immediate,
        utilisee par les tests, sans delai de grace).

        N'appelle jamais `Server.wait_closed()` ici : depuis Python
        3.12.1, elle attend elle-meme (sans aucune limite de temps) que
        toutes les connexions actives se terminent - exactement ce
        qu'on veut borner nous-memes avec `grace_period_seconds`, pas
        deleguer sans limite (bug trouve en testant : un `wait_closed()`
        prealable rend le delai de grace ci-dessous inoperant, la
        methode ne rendait jamais la main avant que toutes les
        connexions soient deja closes)."""
        if self._server is not None:
            self._server.close()

        if not self._active_connections:
            return 0

        _, pending = await asyncio.wait(self._active_connections, timeout=grace_period_seconds)
        for task in pending:
            task.cancel()
        if pending:
            self._log_error(
                f"arret force de {len(pending)} connexion(s) encore actives apres le delai de grace de {grace_period_seconds}s",
                request_id=None,
            )
        return len(pending)

    async def _handle_connection_tracked(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        # Retour utilisateur 2026-09-11 (audit reload/restart) : vrai
        # bug trouve, `server.max_connections` etait configurable et
        # valide mais applique NULLE PART dans le serveur - premiere
        # verification ici, avant meme le comptage dans
        # `_active_connections` (une connexion refusee ne doit jamais
        # etre comptee comme active, ni consommer de ressources de
        # parsing de requete). 503 explicite plutot qu'une fermeture
        # silencieuse - le client sait au moins pourquoi.
        if len(self._active_connections) >= self._config.server.max_connections:
            await self._write_error_response(writer, HttpStatus.SERVICE_UNAVAILABLE)
            writer.close()
            try:
                await writer.wait_closed()
            except (ConnectionResetError, BrokenPipeError, OSError):
                pass
            return
        task = asyncio.current_task()
        assert task is not None
        self._active_connections.add(task)
        try:
            await self._handle_connection(reader, writer)
        finally:
            self._active_connections.discard(task)

    async def _handle_connection(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        peername = writer.get_extra_info("peername")
        peer_ip = peername[0] if peername else "unknown"
        server_config = self._config.server
        requests_served = 0

        try:
            while requests_served < server_config.max_keepalive_requests:
                timeout = (
                    server_config.read_timeout_seconds
                    if requests_served == 0
                    else server_config.keepalive_timeout_seconds
                )
                try:
                    head = await asyncio.wait_for(
                        read_request_head(reader, server_config.max_request_line_size, server_config.max_header_size),
                        timeout=timeout,
                    )
                except asyncio.TimeoutError:
                    break
                except ConnectionClosedCleanly:
                    break
                except HttpParseError as e:
                    await self._write_error_response(writer, e.status)
                    self._log_error(f"erreur de parsing : {e.reason}", request_id=None)
                    break

                request_id = uuid.uuid4().hex[:16]
                start_time = time.monotonic()

                path, query = split_request_target(head.target)
                headers = HttpHeaders.from_pairs(list(head.headers))
                remote_ip = self._resolve_remote_ip(peer_ip, headers)
                request = HttpRequest(
                    request_id=request_id,
                    remote_ip=remote_ip,
                    peer_ip=peer_ip,
                    method=head.method,
                    path=path,
                    raw_path=head.target,
                    query=query,
                    headers=headers,
                    body=None,
                    content_length=None,
                    is_tls=self._ssl_context is not None,
                )

                if self._config.security.require_valid_host:
                    host_error = validate_host_header(head.headers)
                    if host_error is not None:
                        await self._write_error_response(writer, HttpStatus.BAD_REQUEST)
                        self._log_error(f"Host invalide : {host_error}", request_id=request_id)
                        break

                if not is_method_allowed(head.method, self._config.security):
                    response = HttpResponse.empty(HttpStatus.METHOD_NOT_ALLOWED)
                    response.set_header("Allow", ", ".join(self._config.security.allowed_methods))
                    await self._write_response(writer, response, keep_alive=False)
                    self._log_access(request, response, start_time)
                    break

                if resolve_access_verdict(request.path, self._access_control_rules()) == "deny":
                    # Blocage inconditionnel par prefixe (retour utilisateur
                    # 2026-09-09), verifie avant WAF/auth/routage - toutes
                    # methodes, jamais une simple passerelle d'authentification
                    # comme les zones d'auth (domain/routing/access_rule.py).
                    response = HttpResponse.empty(HttpStatus.FORBIDDEN)
                    apply_security_headers(response, self._config.security, self._config.tls.enabled)
                    await self._write_response(writer, response, keep_alive=False)
                    self._log_access(request, response, start_time)
                    break

                capture_max_bytes = 0
                if self._waf_config is not None and head.method in self._waf_config.inspect.body_methods:
                    capture_max_bytes = self._waf_config.inspect.body_max_inspect_bytes
                if (
                    self._fastcgi_client is not None
                    or self._config.option_enabled("upload")
                    or self._proxy_client is not None
                ):
                    # FastCGI (POST PHP), upload (POST multipart) et le
                    # reverse proxy sortant (retour utilisateur
                    # 2026-09-11 : un POST/PUT vers une zone proxy doit
                    # relayer le corps entier a l'upstream, jamais un
                    # corps tronque) ont tous besoin du corps complet -
                    # jamais plus que la limite serveur deja en vigueur
                    # (plan corrige upload §9 : pas de streaming en V1).
                    capture_max_bytes = max(capture_max_bytes, server_config.max_request_size)

                try:
                    # Retour utilisateur (audit securite, 2026-09-14) :
                    # contrairement a la lecture des en-tetes juste au-dessus,
                    # cette lecture n'etait bornee par AUCUN timeout - un
                    # attaquant envoyant un Content-Length eleve puis trickle
                    # le corps a 1 octet/30s (variante "slow-POST" du type
                    # R-U-Dead-Yet) gardait la connexion ouverte indefiniment,
                    # jusqu'a saturer `server.max_connections` a moindre cout.
                    # Meme timeout que la lecture des en-tetes de cette meme
                    # iteration (deja calcule plus haut).
                    _, captured_body = await asyncio.wait_for(
                        read_and_discard_body(reader, head, server_config.max_request_size, capture_max_bytes),
                        timeout=timeout,
                    )
                except asyncio.TimeoutError:
                    await self._write_error_response(writer, HttpStatus.REQUEST_TIMEOUT)
                    self._log_error("corps de requete trop lent (timeout)", request_id=request_id)
                    break
                except HttpParseError as e:
                    await self._write_error_response(writer, e.status)
                    self._log_error(f"erreur de corps de requete : {e.reason}", request_id=request_id)
                    break

                if captured_body:
                    request = replace(request, body=captured_body)

                decoy_response = await self._maybe_serve_decoy(request)
                if decoy_response is not None:
                    apply_security_headers(decoy_response, self._config.security, self._config.tls.enabled)
                    requests_served += 1
                    keep_alive = (
                        requests_served < server_config.max_keepalive_requests
                        and head.http_version == "HTTP/1.1"
                        and (head.header("connection") or "").lower() != "close"
                    )
                    await self._write_response(writer, decoy_response, keep_alive)
                    self._log_access(request, decoy_response, start_time)
                    if not keep_alive:
                        break
                    continue

                if self._waf_config is not None:
                    # Les 4 collaborateurs suivants sont toujours construits
                    # ensemble avec waf_config, jamais independamment (seul
                    # point de construction : application/server/
                    # start_server.py::build_server, "waf.xxx if waf else
                    # None" pour les 5 en une seule fois) - assertions qui
                    # documentent cet invariant reel plutot que des None
                    # verifies un a un sans jamais pouvoir differer en
                    # pratique.
                    assert self._waf_port is not None
                    assert self._blocklist_port is not None
                    assert self._rate_limit_port is not None
                    assert self._reputation_tracker is not None
                    waf_start = time.monotonic()
                    decision = evaluate_waf_request(
                        request,
                        self._waf_config,
                        self._waf_port,
                        self._blocklist_port,
                        self._rate_limit_port,
                        self._reputation_tracker,
                    )
                    if decision.action != "allow":
                        self._log_waf_alert(request, decision, (time.monotonic() - waf_start) * 1000)
                        state = self._observe_active_defense_threat(request, decision)
                        if state is not None:
                            war_mode_response = await self._apply_active_defense_war_mode_actions(request, state)
                            if war_mode_response is not None:
                                apply_security_headers(
                                    war_mode_response, self._config.security, self._config.tls.enabled,
                                )
                                await self._write_response(writer, war_mode_response, keep_alive=False)
                                self._log_access(request, war_mode_response, start_time)
                                break
                    if decision.action == "block":
                        response = HttpResponse.empty(HttpStatus(decision.status_code or 403))
                        if decision.retry_after_seconds is not None:
                            response.set_header("Retry-After", str(int(decision.retry_after_seconds)))
                        apply_security_headers(response, self._config.security, self._config.tls.enabled)
                        await self._write_response(writer, response, keep_alive=False)
                        self._log_access(request, response, start_time)
                        break

                if self._auth_zones:
                    auth_decision = authorize_request(
                        request.path, request.method, request.header("authorization"),
                        self._auth_zones, self._users_by_name,
                    )
                    if auth_decision.outcome in ("unauthenticated", "forbidden"):
                        status = HttpStatus.UNAUTHORIZED if auth_decision.outcome == "unauthenticated" else HttpStatus.FORBIDDEN
                        response = HttpResponse.empty(status)
                        if auth_decision.outcome == "unauthenticated":
                            response.set_header("WWW-Authenticate", build_www_authenticate_header(auth_decision.realm or "Zone protegee"))
                        apply_security_headers(response, self._config.security, self._config.tls.enabled)
                        await self._write_response(writer, response, keep_alive=False)
                        self._log_access(request, response, start_time)
                        break

                if self._proxy_client is not None and is_websocket_upgrade_request(request):
                    # Chemin de code separe (retour utilisateur, §4 du
                    # document) : court-circuite route_request()
                    # ENTIEREMENT plutot que d'y ajouter un cas special -
                    # match sur request.path BRUT, jamais apres
                    # rewrites/redirections/alias (ceux-la ne
                    # s'appliquent qu'au relai HTTP ordinaire, simplification
                    # deliberee du perimetre WebSocket).
                    proxy_zone = self._match_websocket_proxy_zone(request.path)
                    if proxy_zone is not None:
                        ws_status = await serve_websocket_proxy(
                            request, proxy_zone, self._proxy_client, self._proxy_round_robin,
                            reader, writer,
                            self._proxy_client_ssl_context_verified, self._proxy_client_ssl_context_unverified,
                        )
                        self._log_access(request, HttpResponse.empty(ws_status), start_time)
                        break

                response = await route_request(
                    request,
                    self._path_resolver,
                    self._filesystem,
                    self._config,
                    self._project_root,
                    self._fastcgi_client,
                    self._logger,
                    self._proxy_client,
                    self._proxy_round_robin,
                    self._proxy_client_ssl_context_verified,
                    self._proxy_client_ssl_context_unverified,
                )
                apply_security_headers(response, self._config.security, self._config.tls.enabled)

                requests_served += 1
                keep_alive = (
                    requests_served < server_config.max_keepalive_requests
                    and head.http_version == "HTTP/1.1"
                    and (head.header("connection") or "").lower() != "close"
                )

                await self._write_response(writer, response, keep_alive)
                self._log_access(request, response, start_time)

                if not keep_alive:
                    break
        except (ConnectionResetError, BrokenPipeError):
            pass
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except (ConnectionResetError, BrokenPipeError, OSError):
                pass

    def _resolve_remote_ip(self, peer_ip: str, headers: HttpHeaders) -> str:
        settings = self._config.options.get("trusted_proxy")
        if settings is None or not settings.enabled:
            return normalize_ip(peer_ip)
        return resolve_client_ip(
            peer_ip,
            headers,
            trusted_networks=settings.settings.get("trusted_networks", []),
            header_preference=settings.settings.get("header_preference", ["Forwarded", "X-Forwarded-For"]),
        )

    async def _write_response(self, writer: asyncio.StreamWriter, response: HttpResponse, keep_alive: bool) -> None:
        if not response.body and int(response.status) >= 400:
            # Page d'erreur HTML par defaut, toujours servie pour un
            # corps vide (retour utilisateur 2026-09-09) - jamais un
            # corps vide silencieux face a un visiteur reel, meme sans
            # option activee. Voir resolve_error_page.py.
            response.body = resolve_error_page_body(
                int(response.status), self._error_page_custom_dir(), self._filesystem
            )
            response.headers.setdefault("Content-Type", "text/html; charset=utf-8")

        headers = dict(response.headers)
        headers.setdefault("Connection", "keep-alive" if keep_alive else "close")
        headers.setdefault("Content-Length", str(len(response.body)))

        status_line = f"HTTP/1.1 {int(response.status)} {reason_phrase_for(response.status)}\r\n"
        header_lines = "".join(f"{name}: {value}\r\n" for name, value in headers.items())
        writer.write((status_line + header_lines + "\r\n").encode("latin-1") + response.body)
        await writer.drain()

    def _parse_access_control_rules(self) -> list[AccessRule]:
        option = self._config.options.get("access_control")
        if option is None or not option.enabled:
            return []
        return parse_access_rules(option.settings.get("list", []))

    def _access_control_rules(self) -> list[AccessRule]:
        return self._access_control_rules_cache

    def _parse_websocket_proxy_zones(self) -> list[ProxyZone]:
        option = self._config.options.get("reverse_proxy")
        if option is None or not option.enabled:
            return []
        return [z for z in parse_proxy_zones(option.settings.get("zones", [])) if z.websocket_enabled]

    def _match_websocket_proxy_zone(self, path: str) -> ProxyZone | None:
        """Resolution INDEPENDANTE de celle de route_request.py - ne
        considere que les zones `websocket_enabled=true` (§4). Si aucune
        zone websocket ne correspond, le chemin normal (route_request,
        qui resout separement TOUTES les zones) reste le seul a
        decider - jamais un echec silencieux, juste une non-application
        du court-circuit WebSocket."""
        return resolve_proxy_zone(path, self._websocket_proxy_zones_cache)

    def _error_page_custom_dir(self) -> Path | None:
        option = self._config.options.get("error_pages")
        if option is None or not option.enabled:
            return None
        relative = str(option.settings.get("custom_dir", "webroot/.errors"))
        return self._project_root / relative

    async def _write_error_response(self, writer: asyncio.StreamWriter, status: HttpStatus) -> None:
        response = HttpResponse.empty(status)
        try:
            await self._write_response(writer, response, keep_alive=False)
        except (ConnectionResetError, BrokenPipeError, OSError):
            pass

    def _log_access(self, request: HttpRequest, response: HttpResponse, start_time: float) -> None:
        entry = AccessLogEntry(
            remote_ip=request.remote_ip,
            timestamp=datetime.now(timezone.utc),
            method=request.method,
            request_target=request.raw_path,
            http_version="HTTP/1.1",
            status_code=int(response.status),
            response_size=len(response.body),
            referer=request.header("referer"),
            user_agent=request.header("user-agent"),
            request_id=request.request_id,
        )
        self._logger.append_line(self._access_log_path, format_combined_log_line(entry))

    def _log_error(self, message: str, request_id: str | None) -> None:
        line = format_error_log_line(datetime.now(timezone.utc), message, request_id)
        self._logger.append_line(self._error_log_path, line)

    def _log_waf_alert(self, request: HttpRequest, decision: WafDecision, duration_ms: float) -> None:
        if self._waf_alert_log_path is None or self._waf_config is None:
            return
        entry = WafAlertEntry(
            request_id=request.request_id,
            timestamp=datetime.now(timezone.utc),
            remote_ip=request.remote_ip,
            method=request.method,
            path=request.path,
            user_agent=request.header("user-agent"),
            decision=decision,
            duration_ms=duration_ms,
            body_excerpt=request.body.decode("utf-8", errors="replace") if request.body else None,
        )
        line = format_waf_alert_line(entry, self._waf_config.logging)
        self._logger.append_line(self._waf_alert_log_path, line)

    def _active_defense_subject_id(self, request: HttpRequest) -> str:
        user_agent = request.header("user-agent") or ""
        return f"{request.remote_ip}:{hash_payload(user_agent.encode('utf-8'))}"

    def _observe_active_defense_threat(self, request: HttpRequest, decision: WafDecision) -> ThreatState | None:
        """Appelee UNIQUEMENT quand le WAF a deja produit une decision
        notable (decision.action != "allow", meme garde que
        _log_waf_alert) - jamais pour chaque requete allow, qui
        n'apporte aucun signal (plan_active_defense_omega_serv.md,
        §"Risques et garde-fous" : "evaluation rapide en memoire").
        Ne recalcule jamais de score independant, traduit uniquement la
        WafDecision deja calculee (voir "Domaine metier" du plan).
        Retourne le `ThreatState` calcule (pour les actions "delay"/
        "rate_limit" appliquees par l'appelant, Phase 4), None si
        war_mode est inactif."""
        if self._active_defense_config is None or not self._active_defense_config.war_mode.enabled:
            return None
        assert self._threat_state_repository is not None
        assert self._active_defense_playbook is not None
        playbook = self._active_defense_playbook
        subject_id = self._active_defense_subject_id(request)
        state, observation, _escalation = observe_threat(
            self._threat_state_repository, self._clock, self._active_defense_config,
            subject_id=subject_id, waf_decision=decision,
        )
        # Phase 2 : une observation detaillee n'est persistee dans un
        # incident que si le score cumule franchit incident_score - en
        # dessous, seul l'etat agrege (deja sauvegarde par observe_threat
        # ci-dessus) compte, jamais un historique complet pour un simple
        # "suspicious" jamais escalade (voir "Domaine metier" du plan).
        # Phase 4 : gate aussi par le DefensePlaybook - "create_incident"
        # doit figurer dans war_mode.actions, jamais suppose implicite.
        if (
            observation is not None
            and self._incident_repository is not None
            and validate_playbook_action("create_incident", playbook)
        ):
            create_or_update_incident(
                self._incident_repository, self._clock, subject_id=subject_id, observation=observation,
                score=state.score, incident_score_threshold=self._active_defense_config.war_mode.thresholds.incident_score,
            )
        # Phase 3 : l'affectation d'un leurre ne se declenche qu'a partir
        # du niveau "hostile" (jamais des la premiere observation
        # "suspicious", qui reste trop bruitee pour justifier un
        # deroutement reel) - assign_deception() est deja idempotent (une
        # affectation existante n'est jamais remplacee en V1). Phase 4 :
        # gate aussi par "redirect_to_decoy" dans war_mode.actions.
        if (
            observation is not None
            and state.level in ("hostile", "contained")
            and self._active_defense_config.deception.enabled
            and self._deception_assignment_repository is not None
            and validate_playbook_action("redirect_to_decoy", playbook)
        ):
            assign_deception(
                self._deception_assignment_repository, self._clock, self._active_defense_config.deception,
                subject_id=subject_id, attack_class=observation.attack_class,
            )
        # Phase 4 : journalisation enrichie ("enrich_log") - uniquement
        # pour une source deja marquee (jamais "normal", voir
        # is_source_marked), separee du log WAF/production (plan
        # §"Journalisation et protection des donnees").
        if (
            observation is not None
            and is_source_marked(state.level)
            and validate_playbook_action("enrich_log", playbook)
            and self._active_defense_enriched_log_path is not None
        ):
            self._write_active_defense_enriched_log(request, state, observation.attack_class)
        return state

    def _write_active_defense_enriched_log(
        self, request: HttpRequest, state: ThreatState, attack_class: AttackClass,
    ) -> None:
        assert self._active_defense_config is not None
        assert self._active_defense_enriched_log_path is not None
        entry = EnrichedLogEntry(
            timestamp=datetime.now(timezone.utc),
            subject_id=state.subject_id,
            remote_ip=request.remote_ip,
            method=request.method,
            path=request.path,
            user_agent=request.header("user-agent"),
            score=state.score,
            level=state.level,
            attack_class=attack_class,
            headers=dict(request.headers),
            body=request.body or None,
        )
        line = format_enriched_log_line(entry, self._active_defense_config.logging)
        self._logger.append_line(self._active_defense_enriched_log_path, line)

    async def _apply_active_defense_war_mode_actions(
        self, request: HttpRequest, state: ThreatState,
    ) -> HttpResponse | None:
        """Actions "rate_limit"/"delay" du DefensePlaybook (plan
        §"Mode guerre", Phase 4) - jamais appliquees a une source encore
        "normal" (policies.py::is_source_marked). Retourne une reponse
        de rejet si "rate_limit" declenche (la requete s'arrete la,
        jamais de ralentissement applique en plus d'un rejet), sinon
        None apres avoir eventuellement attendu le delai de
        ralentissement (jamais un blocage de la boucle asyncio, voir
        AsyncioDelayScheduler)."""
        assert self._active_defense_config is not None
        assert self._active_defense_playbook is not None
        war_mode = self._active_defense_config.war_mode
        if not is_source_marked(state.level):
            return None
        playbook = self._active_defense_playbook

        if validate_playbook_action("rate_limit", playbook):
            assert self._rate_limit_port is not None
            result = self._rate_limit_port.check(
                f"active-defense:{state.subject_id}", war_mode.rate_limit.requests, war_mode.rate_limit.window_seconds,
            )
            if not result.allowed:
                response = HttpResponse.empty(HttpStatus.TOO_MANY_REQUESTS)
                if result.retry_after_seconds is not None:
                    response.set_header("Retry-After", str(result.retry_after_seconds))
                return response

        if validate_playbook_action("delay", playbook) and war_mode.slowdown.enabled:
            assert self._delay_scheduler is not None
            delay_ms = compute_slowdown_delay_ms(
                random.random(), minimum_ms=war_mode.slowdown.minimum_ms,
                maximum_ms=war_mode.slowdown.maximum_ms, jitter_ms=war_mode.slowdown.jitter_ms,
            )
            await self._delay_scheduler.wait(delay_ms / 1000)

        return None

    async def _maybe_serve_decoy(self, request: HttpRequest) -> HttpResponse | None:
        """Appelee pour CHAQUE requete (pas seulement celles qui
        declenchent une decision WAF notable) des que `deception.enabled` -
        une source deja affectee doit recevoir le leurre sur n'importe
        quel chemin ensuite (plan §"Deception dynamique"), jamais
        seulement sur le chemin qui a declenche l'affectation initiale.
        En `mode: monitor`, la decision est resolue mais jamais appliquee
        (observation seule, meme convention que le WAF log-only) -
        aucune journalisation dediee en V1, deliberement simplifie.

        Phase 5 ("Niveau 2") : `decoy_proxy` relaie reellement la requete
        vers un backend isole via `serve_proxy()` (meme mecanisme deja
        livre et teste pour le reverse proxy sortant de production,
        jamais un second protocole de relai) - `async` desormais pour
        cette seule raison (`decoy_fixture`, Niveau 1, reste un simple
        appel synchrone au dispatcher de fixtures)."""
        if self._active_defense_config is None or not self._active_defense_config.deception.enabled:
            return None
        assert self._deception_assignment_repository is not None
        subject_id = self._active_defense_subject_id(request)
        routing_decision = resolve_routing_decision(
            self._deception_assignment_repository, self._clock, self._active_defense_config.deception, subject_id,
        )
        if routing_decision.kind not in ("decoy_fixture", "decoy_proxy"):
            return None
        if self._active_defense_config.mode != "enforce":
            return None

        if routing_decision.kind == "decoy_proxy":
            return await self._serve_decoy_proxy(request, routing_decision)

        assert self._decoy_dispatch_port is not None
        assert routing_decision.deception_profile_name is not None
        response = self._decoy_dispatch_port.render(routing_decision.deception_profile_name, request)
        if response is not None:
            return response
        if self._active_defense_config.deception.fallback == "reject":
            return HttpResponse.empty(HttpStatus.FORBIDDEN)
        return None

    async def _serve_decoy_proxy(self, request: HttpRequest, routing_decision: RoutingDecision) -> HttpResponse | None:
        """Niveau 2 - relaie reellement vers le backend isole (plan
        §"Routage vers les leurres"). Retourne None (fallback applique
        par l'appelant) si la zone est introuvable dans `decoy_zones`
        (config editee/rechargee entre l'affectation et cette requete -
        meme garde de robustesse que `resolve_routing_decision` cote
        profil) - jamais une exception non attrapee."""
        assert self._active_defense_config is not None
        assert routing_decision.reverse_proxy_zone_name is not None
        zone = self._active_defense_config.deception.decoy_zones.get(routing_decision.reverse_proxy_zone_name)
        if zone is None:
            if self._active_defense_config.deception.fallback == "reject":
                return HttpResponse.empty(HttpStatus.FORBIDDEN)
            return None
        assert self._decoy_proxy_client is not None
        return await serve_proxy(
            request, zone, self._decoy_proxy_client, self._decoy_round_robin,
            self._proxy_client_ssl_context_verified, self._proxy_client_ssl_context_unverified,
        )
