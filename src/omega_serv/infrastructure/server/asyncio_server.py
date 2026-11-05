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
import socket
import time
import uuid
from collections.abc import Callable, Mapping
from concurrent.futures import Executor
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import ssl

from omega_serv.application.active_defense.manage_deception import (
    assign_deception,
    resolve_routing_decision,
)
from omega_serv.application.active_defense.manage_incidents import create_or_update_incident
from omega_serv.application.active_defense.observe_threat import observe_threat
from omega_serv.application.security.evaluate_waf_request import evaluate_waf_request
from omega_serv.application.server.poll_upstream_load import (
    poll_upstream_load_forever,
    stop_pollers,
)
from omega_serv.application.server.proxy_cache_locks import ProxyCacheLocks
from omega_serv.application.server.resolve_error_page import resolve_error_page_body
from omega_serv.application.server.route_request import route_request
from omega_serv.application.server.serve_proxy import serve_proxy
from omega_serv.application.server.serve_websocket_proxy import serve_websocket_proxy
from omega_serv.domain.config.entities import OmegaServConfig
from omega_serv.domain.http.headers import HttpHeaders
from omega_serv.domain.http.request import (
    HttpRequest,
    InvalidAbsoluteTarget,
    absolute_form_parts,
    split_request_target,
)
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
from omega_serv.domain.logging.security_event_format import (
    SecurityEvent,
    SecurityEventType,
    format_security_event_line,
)
from omega_serv.domain.logging.waf_alert_format import WafAlertEntry, format_waf_alert_line
from omega_serv.domain.routing.access_rule import (
    AccessRule,
    parse_access_rules,
    resolve_access_verdict,
)
from omega_serv.domain.routing.proxy_cache_metrics import ProxyCacheMetrics
from omega_serv.domain.routing.proxy_health import ProxyHealthState
from omega_serv.domain.routing.proxy_zone import (
    ProxyLoadBalancerState,
    ProxyZone,
    UpstreamTarget,
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
    is_assignment_active,
    is_source_marked,
    user_agent_fingerprint,
    validate_playbook_action,
)
from omega_serv.domain.security.active_defense.value_objects import AttackClass
from omega_serv.domain.security.auth.authorize import authorize_request
from omega_serv.domain.security.auth.basic_auth import build_www_authenticate_header
from omega_serv.domain.security.auth.entities import AuthZone, UserAccount
from omega_serv.domain.security.csp import allow_inline_styles_by_hash, csp_header_name
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
    ParsedRequestHead,
    read_and_discard_body,
    read_request_head,
)
from omega_serv.ports.active_defense_writer_port import (
    ActiveDefenseRepositories,
    ActiveDefenseWriterPort,
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
from omega_serv.ports.proxy_cache_store_port import ProxyCacheStorePort
from omega_serv.ports.rate_limit_port import RateLimitPort
from omega_serv.ports.reputation_tracker_port import ReputationTrackerPort
from omega_serv.ports.threat_state_repository_port import ThreatStateRepositoryPort
from omega_serv.ports.waf_port import WafPort

ACTIVE_DEFENSE_STOP_TIMEOUT_SECONDS = 2.0
"""A l'arret, temps maximal laisse au fil d'ecriture d'Active Defense pour vider sa file."""


@dataclass(frozen=True)
class SecurityOutcome:
    """Resultat de `AsyncioServer.security_stage` : reponse a envoyer (None = continuer vers le routage)."""
    response: HttpResponse | None
    keep_alive_allowed: bool = False
    # Leurre, decision WAF autre que « autoriser » (journal seul compris) ou refus Auth : la requete n'etait pas
    # propre (controle 1/N du moteur natif, plan WAF natif lot 4).
    notable: bool = False


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
        magnet_port: WafPort | None = None,
        magnet_executor: Executor | None = None,
        blocklist_port: BlocklistPort | None = None,
        rate_limit_port: RateLimitPort | None = None,
        reputation_tracker: ReputationTrackerPort | None = None,
        waf_alert_log_path: Path | None = None,
        ssl_context: ssl.SSLContext | None = None,
        auth_zones: tuple[Zone[AuthZone], ...] = (),
        users_by_name: Mapping[str, UserAccount] | None = None,
        fastcgi_client: FastCgiClientPort | None = None,
        proxy_client: HttpProxyClientPort | None = None,
        proxy_load_balancer: ProxyLoadBalancerState | None = None,
        proxy_health_state: ProxyHealthState | None = None,
        proxy_client_ssl_context_verified: ssl.SSLContext | None = None,
        proxy_client_ssl_context_unverified: ssl.SSLContext | None = None,
        proxy_cache_store: ProxyCacheStorePort | None = None,
        proxy_cache_locks: ProxyCacheLocks | None = None,
        proxy_cache_metrics: ProxyCacheMetrics | None = None,
        active_defense_config: ActiveDefenseConfig | None = None,
        threat_state_repository: ThreatStateRepositoryPort | None = None,
        incident_repository: IncidentRepositoryPort | None = None,
        deception_assignment_repository: DeceptionAssignmentRepositoryPort | None = None,
        decoy_dispatch_port: DecoyDispatchPort | None = None,
        delay_scheduler: DelaySchedulerPort | None = None,
        active_defense_enriched_log_path: Path | None = None,
        decoy_proxy_client: HttpProxyClientPort | None = None,
        active_defense_security_events_path: Path | None = None,
        clock: ClockPort | None = None,
        active_defense_writer: ActiveDefenseWriterPort | None = None,
    ):
        self._config = config
        self._path_resolver = path_resolver
        self._filesystem = filesystem
        self._logger = logger
        self._access_log_path = access_log_path
        self._error_log_path = error_log_path
        self._project_root = project_root
        self._waf_config = waf_config
        self._waf_port = waf_port
        self._magnet_port = magnet_port
        self._magnet_executor = magnet_executor
        self._blocklist_port = blocklist_port
        self._rate_limit_port = rate_limit_port
        self._reputation_tracker = reputation_tracker
        self._waf_alert_log_path = waf_alert_log_path
        self._ssl_context = ssl_context
        self._auth_zones = auth_zones
        self._users_by_name = users_by_name or {}
        self._fastcgi_client = fastcgi_client
        self._proxy_client = proxy_client
        self._proxy_load_balancer = proxy_load_balancer or ProxyLoadBalancerState()
        self._proxy_health_state = proxy_health_state or ProxyHealthState()
        self._proxy_client_ssl_context_verified = proxy_client_ssl_context_verified
        self._proxy_client_ssl_context_unverified = proxy_client_ssl_context_unverified
        self._proxy_cache_store = proxy_cache_store
        self._proxy_cache_locks = proxy_cache_locks or ProxyCacheLocks()
        self._proxy_cache_metrics = proxy_cache_metrics or ProxyCacheMetrics()
        self._active_defense_config = active_defense_config
        self._threat_state_repository = threat_state_repository
        self._incident_repository = incident_repository
        self._deception_assignment_repository = deception_assignment_repository
        self._decoy_dispatch_port = decoy_dispatch_port
        self._delay_scheduler = delay_scheduler
        self._active_defense_enriched_log_path = active_defense_enriched_log_path
        self._active_defense_security_events_path = active_defense_security_events_path
        self._decoy_proxy_client = decoy_proxy_client
        self._active_defense_writer = active_defense_writer
        self._active_defense_guard_failing = False
        self._decoy_load_balancer = ProxyLoadBalancerState()
        self._decoy_health_state = ProxyHealthState()
        self._active_defense_playbook: DefensePlaybook | None = (
            build_playbook(active_defense_config.war_mode) if active_defense_config is not None else None
        )
        self._clock = clock or SystemClock()
        self._server: asyncio.Server | None = None
        self._stopped = asyncio.Event()
        # Mode « boost » : compteurs de securite partages entre workers (pose par build_server).
        self.shared_counters: Any = None
        # Moteur natif (plan WAF natif, lot 3) : (adresse, echeance en secondes Unix) d'une source que le natif doit
        # toujours envoyer ici - pose par le processus de securite ; None avec le moteur Python.
        self.watch_sink: Callable[[str, float], None] | None = None
        self._active_connections: set[asyncio.Task] = set()
        self._access_control_rules_cache: list[AccessRule] = self._parse_access_control_rules()
        self._websocket_proxy_zones_cache: list[ProxyZone] = self._parse_websocket_proxy_zones()
        self._proxy_load_poll_tasks: list[asyncio.Task] = []

    @property
    def sockets(self) -> tuple:
        assert self._server is not None
        return self._server.sockets

    @property
    def reputation_tracker(self) -> ReputationTrackerPort | None:
        """Compteur de recidive en cours - relu par reload_server pour le
        CONSERVER au SIGHUP (OMEGA-SERV_PLAN-DETAILLE_SENSITIVE_PATHS.md
        §3.12 : chaque enregistrement depuis l'editeur declenche un
        rechargement, qui remettait sinon toutes les recidives a zero)."""
        return self._reputation_tracker

    async def start(self, listen_socket: socket.socket | None = None) -> None:
        """`listen_socket` : port deja ouvert par le processus principal du mode « boost »,
        partage par tous les workers (le noyau repartit les connexions entre eux)."""
        if self._active_defense_writer is not None:
            # Fil d'ecriture demarre ICI (dans le worker, apres le fork du mode boost : un fil
            # ne survit jamais a un fork) - OMEGA-SERV_ETUDE_ACTIVE_DEFENSE_STIX_MISP_CHARGE.md §3.6.
            self._active_defense_writer.set_error_reporter(lambda message: self._log_error(message, request_id=None))
            self._active_defense_writer.start()
        server_config = self._config.server
        if listen_socket is not None:
            self._server = await asyncio.start_server(
                self._handle_connection_tracked,
                sock=listen_socket,
                limit=RAW_LINE_BUFFER_LIMIT,
                ssl=self._ssl_context,
            )
        else:
            self._server = await asyncio.start_server(
                self._handle_connection_tracked,
                host=server_config.bind,
                port=server_config.port,
                backlog=server_config.listen_backlog,
                limit=RAW_LINE_BUFFER_LIMIT,
                ssl=self._ssl_context,
            )
        self._start_proxy_load_pollers()

    async def serve_forever(self) -> None:
        """Attend l'arret (shutdown()/close()). N'utilise jamais
        `asyncio.Server.serve_forever()` : depuis Python 3.13, son annulation
        - declenchee par `Server.close()` dans shutdown() - appelle
        `close_clients()` et coupe net toutes les connexions en cours, avant
        meme le delai de grace (drainage devenu inoperant sans aucun message,
        trouve par test_sigterm_drains_in_flight_request). Le serveur ecoute
        deja depuis start() (`start_server` demarre l'ecoute d'office)."""
        assert self._server is not None
        await self._stopped.wait()

    async def close(self) -> None:
        self._stopped.set()
        await self._stop_proxy_load_pollers()
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
        if self._active_defense_writer is not None:
            # Ecrit ce qui peut l'etre en 2 s au plus : l'arret n'attend jamais une base bloquee.
            await asyncio.to_thread(self._active_defense_writer.stop, ACTIVE_DEFENSE_STOP_TIMEOUT_SECONDS)
        if self._magnet_executor is not None:
            # wait=False : un script magnet bloque (lot E, limite connue
            # - voir evaluate_waf_request.py::_inspect_with_magnet) ne
            # doit jamais empecher l'arret du serveur.
            self._magnet_executor.shutdown(wait=False, cancel_futures=True)

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
        magnet_port: WafPort | None = None,
        magnet_executor: Executor | None = None,
    ) -> None:
        """Rechargement a chaud borne (decision transverse "Reload
        scope", plan de developpement §6) : remplace la configuration
        et les collaborateurs WAF/Auth deja compiles/charges en memoire,
        sans jamais toucher au socket d'ecoute, au contexte TLS ni au
        bind/port - un changement la-dessus exige un restart complet,
        documente comme tel (jamais fait ici). Declenche par SIGHUP
        (angle mort §9.1), voir interfaces/cli/main.py::cmd_serve.

        `magnet_executor` REMPLACE (jamais accumule) : l'ancien pool de
        threads dedie au magnet, s'il existe, est ferme explicitement
        avant d'etre abandonne - sinon chaque SIGHUP laisserait fuiter
        un `ThreadPoolExecutor` entier (lot E, meme vigilance que pour
        tout executor cree par configuration)."""
        if self._magnet_executor is not None and self._magnet_executor is not magnet_executor:
            self._magnet_executor.shutdown(wait=False, cancel_futures=True)
        self._config = config
        self._waf_config = waf_config
        self._waf_port = waf_port
        self._magnet_port = magnet_port
        self._magnet_executor = magnet_executor
        self._blocklist_port = blocklist_port
        self._rate_limit_port = rate_limit_port
        self._reputation_tracker = reputation_tracker
        self._waf_alert_log_path = waf_alert_log_path
        self._auth_zones = auth_zones
        self._users_by_name = users_by_name or {}
        self._access_control_rules_cache = self._parse_access_control_rules()
        self._websocket_proxy_zones_cache = self._parse_websocket_proxy_zones()
        self._restart_proxy_load_pollers()

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
        await self._stop_proxy_load_pollers()
        if self._server is not None:
            self._server.close()

        if not self._active_connections:
            self._stopped.set()
            return 0

        _, pending = await asyncio.wait(self._active_connections, timeout=grace_period_seconds)
        for task in pending:
            task.cancel()
        self._stopped.set()
        if pending:
            self._log_error(
                f"arret force de {len(pending)} connexion(s) encore actives apres le delai de grace de {grace_period_seconds}s",
                request_id=None,
            )
        return len(pending)

    async def _handle_connection_tracked(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
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

    async def _handle_connection(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter, requests_served: int = 0,
    ) -> None:
        """`requests_served` : requetes deja servies sur cette connexion par le moteur natif avant qu'il la confie
        (plan moteur C++ lot 6) - la limite keep-alive reste celle de la connexion entiere."""
        peername = writer.get_extra_info("peername")
        peer_ip = peername[0] if peername else "unknown"
        server_config = self._config.server

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
                    request_id = uuid.uuid4().hex[:16]
                    error_response = await self._write_error_response(writer, e.status)
                    self._log_error(f"erreur de parsing : {e.reason}", request_id=request_id)
                    self._log_unparsed_access(peer_ip, e, error_response, request_id)
                    break

                request_id = uuid.uuid4().hex[:16]
                start_time = time.monotonic()

                request, absolute_target_valid = self._build_request(head, peer_ip, request_id)

                if self._config.security.require_valid_host:
                    host_error = validate_host_header(head.headers)
                    if host_error is not None:
                        response = await self._write_error_response(writer, HttpStatus.BAD_REQUEST)
                        self._log_error(f"Host invalide : {host_error}", request_id=request_id)
                        self._log_access(request, response, start_time)
                        break

                if not absolute_target_valid:
                    response = await self._write_error_response(writer, HttpStatus.BAD_REQUEST)
                    self._log_error("cible de requête absolue invalide", request_id=request_id)
                    self._log_access(request, response, start_time)
                    break

                if not is_method_allowed(head.method, self._config.security):
                    response = HttpResponse.empty(HttpStatus.METHOD_NOT_ALLOWED)
                    response.set_header("Allow", ", ".join(self._config.security.allowed_methods))
                    await self._write_response(writer, response, keep_alive=False)
                    self._log_access(request, response, start_time)
                    break

                if resolve_access_verdict(request.path, self._access_control_rules()) == "deny":
                    response = HttpResponse.empty(HttpStatus.FORBIDDEN)
                    apply_security_headers(response, self._config.security, self._config.tls.enabled, request.path)
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
                    capture_max_bytes = max(capture_max_bytes, server_config.max_request_size)

                try:
                    _, captured_body = await asyncio.wait_for(
                        read_and_discard_body(reader, head, server_config.max_request_size, capture_max_bytes),
                        timeout=timeout,
                    )
                except asyncio.TimeoutError:
                    response = await self._write_error_response(writer, HttpStatus.REQUEST_TIMEOUT)
                    self._log_error("corps de requete trop lent (timeout)", request_id=request_id)
                    self._log_access(request, response, start_time)
                    break
                except HttpParseError as e:
                    response = await self._write_error_response(writer, e.status)
                    self._log_error(f"erreur de corps de requete : {e.reason}", request_id=request_id)
                    self._log_access(request, response, start_time)
                    break

                if captured_body:
                    request = replace(request, body=captured_body)

                # Leurre, WAF, Active Defense, mode guerre, Auth : la MEME etape que le processus de securite du
                # moteur natif (plan moteur C++ lot 4) - une seule implementation pour les deux moteurs.
                outcome = await self.security_stage(request)
                if outcome.response is not None:
                    apply_security_headers(outcome.response, self._config.security, self._config.tls.enabled, request.path)
                    if outcome.keep_alive_allowed:  # leurre : la connexion continue comme pour une requete servie
                        requests_served += 1
                        keep_alive = (
                            requests_served < server_config.max_keepalive_requests
                            and head.http_version == "HTTP/1.1"
                            and (head.header("connection") or "").lower() != "close"
                        )
                        await self._write_response(writer, outcome.response, keep_alive)
                        self._log_access(request, outcome.response, start_time)
                        if not keep_alive:
                            break
                        continue
                    await self._write_response(writer, outcome.response, keep_alive=False)
                    self._log_access(request, outcome.response, start_time)
                    break

                if self._proxy_client is not None and is_websocket_upgrade_request(request):
                    proxy_zone = self._match_websocket_proxy_zone(request.path)
                    if proxy_zone is not None:
                        ws_status = await serve_websocket_proxy(
                            request, proxy_zone, self._proxy_client, self._proxy_load_balancer,
                            self._proxy_health_state, reader, writer,
                            self._proxy_client_ssl_context_verified, self._proxy_client_ssl_context_unverified,
                        )
                        self._log_access(request, HttpResponse.empty(ws_status), start_time)
                        break

                response = await self.route(request)
                apply_security_headers(response, self._config.security, self._config.tls.enabled, request.path)

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

    def _build_request(
        self, head: ParsedRequestHead, peer_ip: str, request_id: str, remote_ip: str | None = None,
    ) -> tuple[HttpRequest, bool]:
        """Requete normalisee construite depuis une tete analysee (moteur Python et processus de securite du
        natif). Le booleen dit si une cible en forme absolue est utilisable (sinon 400, verifie par l'appelant).
        `remote_ip` : IP cliente deja resolue par le natif (meme regle trusted_proxy, plan lot 8)."""
        path, query = split_request_target(head.target)
        header_pairs = list(head.headers)
        absolute_target_valid = True
        try:
            absolute = absolute_form_parts(head.target)
        except InvalidAbsoluteTarget:
            absolute, absolute_target_valid = None, False
        if absolute is not None:
            # RFC 9112 §3.2.2 : l'hote de la cible remplace l'en-tete Host (valide plus bas tel que recu).
            absolute_host, origin_target = absolute
            path, query = split_request_target(origin_target)
            header_pairs = [(n, v) for n, v in header_pairs if n.lower() != "host"] + [("Host", absolute_host)]
        headers = HttpHeaders.from_pairs(header_pairs)
        request = HttpRequest(
            request_id=request_id,
            remote_ip=remote_ip if remote_ip is not None else self._resolve_remote_ip(peer_ip, headers),
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
        return request, absolute_target_valid

    def build_request(
        self, head: ParsedRequestHead, peer_ip: str, request_id: str, body: bytes | None = None,
        remote_ip: str | None = None,
    ) -> HttpRequest:
        """Processus de securite du moteur natif : la requete telle que le moteur Python l'aurait construite (le
        natif a deja verifie Host, cible, methode, regles d'acces et lu le corps ; `body` = extrait capture)."""
        request, _valid = self._build_request(head, peer_ip, request_id, remote_ip)
        return replace(request, body=body) if body else request

    async def security_stage(self, request: HttpRequest, blocklist_known_clear: bool = False,
                             native_rate_limit: int | None = None) -> SecurityOutcome:
        """Leurre, WAF (alerte, Active Defense, mode guerre), Auth - dans cet ordre, comme toujours. Rend la
        reponse a envoyer (AVANT en-tetes de securite, appliques par l'appelant) ou None pour continuer vers le
        routage. `keep_alive_allowed` : seul un leurre laisse la connexion ouverte ; tout refus la ferme.
        `blocklist_known_clear`, `native_rate_limit` : indications du moteur natif (voir evaluate_waf_request)."""
        decoy_response = await self._maybe_serve_decoy(request)
        if decoy_response is not None:
            return SecurityOutcome(decoy_response, keep_alive_allowed=True, notable=True)

        waf_notable = False
        if self._waf_config is not None:
            assert self._waf_port is not None
            assert self._blocklist_port is not None
            assert self._rate_limit_port is not None
            assert self._reputation_tracker is not None
            waf_start = time.monotonic()
            decision = await evaluate_waf_request(
                request,
                self._waf_config,
                self._waf_port,
                self._blocklist_port,
                self._rate_limit_port,
                self._reputation_tracker,
                self._magnet_port,
                self._magnet_executor,
                blocklist_known_clear=blocklist_known_clear,
                native_rate_limit=native_rate_limit,
            )
            if decision.action != "allow":
                waf_notable = True
                self._watch_source(request.remote_ip)
                self._log_waf_alert(request, decision, (time.monotonic() - waf_start) * 1000)
                state = self._observe_active_defense_threat(request, decision)
                if state is not None:
                    war_mode_response = await self._apply_active_defense_war_mode_actions(request, state)
                    if war_mode_response is not None:
                        return SecurityOutcome(war_mode_response, notable=True)
            if decision.action == "block":
                response = HttpResponse.empty(HttpStatus(decision.status_code or 403))
                if decision.retry_after_seconds is not None:
                    response.set_header("Retry-After", str(int(decision.retry_after_seconds)))
                return SecurityOutcome(response, notable=True)

        if self._auth_zones:
            auth_decision = authorize_request(
                request.path, request.method, request.header("authorization"),
                self._auth_zones, self._users_by_name,
            )
            if auth_decision.outcome in ("unauthenticated", "forbidden"):
                status = HttpStatus.UNAUTHORIZED if auth_decision.outcome == "unauthenticated" else HttpStatus.FORBIDDEN
                response = HttpResponse.empty(status)
                if auth_decision.outcome == "unauthenticated":
                    response.set_header("WWW-Authenticate", build_www_authenticate_header(auth_decision.realm or "Zone protégée"))
                return SecurityOutcome(response, notable=True)
        return SecurityOutcome(None, notable=waf_notable)

    async def serve_handed_off(self, sock: socket.socket, pending: bytes, requests_served: int) -> None:
        """Lot 6 : connexion confiee par le moteur natif (reverse proxy, FastCGI, envoi de fichiers, WebSocket).
        Les octets deja lus par le natif (tete de la requete en cours comprise) sont rejoues d'abord ; la suite
        est le MEME `_handle_connection` que le moteur Python, jusqu'a la fin de la connexion (journal d'acces
        compris)."""
        loop = asyncio.get_running_loop()
        reader = asyncio.StreamReader(limit=RAW_LINE_BUFFER_LIMIT, loop=loop)
        reader.feed_data(pending)
        protocol = asyncio.StreamReaderProtocol(reader, loop=loop)
        transport, _ = await loop.connect_accepted_socket(lambda: protocol, sock=sock)
        writer = asyncio.StreamWriter(transport, protocol, reader, loop)
        await self._handle_connection(reader, writer, requests_served)

    async def route(self, request: HttpRequest) -> HttpResponse:
        """Routage complet (avant en-tetes de securite) : moteur Python, et routes deleguees par le natif (listing
        de repertoire, /load, /admin - plan moteur C++ lot 5)."""
        return await route_request(
            request,
            self._path_resolver,
            self._filesystem,
            self._config,
            self._project_root,
            self._fastcgi_client,
            self._logger,
            self._proxy_client,
            self._proxy_load_balancer,
            self._proxy_health_state,
            self._proxy_client_ssl_context_verified,
            self._proxy_client_ssl_context_unverified,
            self._proxy_cache_store,
            self._proxy_cache_locks,
            self._proxy_cache_metrics,
        )

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
            response.body = resolve_error_page_body(
                int(response.status), self._error_page_custom_dir(), self._filesystem
            )
            response.headers.setdefault("Content-Type", "text/html; charset=utf-8")
            for csp_header in (csp_header_name("enforce"), csp_header_name("report-only")):
                if csp_header in response.headers:
                    response.headers[csp_header] = allow_inline_styles_by_hash(
                        response.headers[csp_header], response.body
                    )

        headers = dict(response.headers)
        headers.setdefault("Connection", "keep-alive" if keep_alive else "close")
        if int(response.status) == HttpStatus.NOT_MODIFIED:
            # 304 : jamais de corps ; un Content-Length annoncerait a tort une
            # representation de 0 octet (RFC 9110 §15.4.5).
            headers.pop("Content-Length", None)
            response.body = b""
        else:
            headers.setdefault("Content-Length", str(response.content_length))

        status_line = f"HTTP/1.1 {int(response.status)} {reason_phrase_for(response.status)}\r\n"
        header_lines = "".join(f"{name}: {value}\r\n" for name, value in headers.items())
        head = (status_line + header_lines + "\r\n").encode("latin-1")
        if response.body_file is None:
            writer.write(head + response.body)
            await writer.drain()
            return
        writer.write(head)
        await writer.drain()
        await self._send_file_body(writer, response)

    async def _send_file_body(self, writer: asyncio.StreamWriter, response: HttpResponse) -> None:
        """Copie par le noyau (`sendfile`) en HTTP ; a travers TLS, asyncio bascule
        seul sur un envoi par blocs lus hors de la boucle - dans les deux cas,
        jamais le fichier entier en memoire. En-tetes deja partis : un fichier
        disparu ou illisible entre-temps ne peut plus devenir une page d'erreur,
        la connexion est fermee (le client voit une reponse tronquee, jamais un
        contenu faux)."""
        assert response.body_file is not None
        try:
            with open(response.body_file, "rb") as handle:  # noqa: ASYNC230 - ouverture seule, la lecture se fait par blocs
                await asyncio.get_running_loop().sendfile(
                    writer.transport, handle, response.body_file_offset, response.body_file_length,
                )
        except (ConnectionResetError, BrokenPipeError):
            raise
        except OSError as e:
            self._log_error(f"envoi interrompu de {response.body_file} : {e}", request_id=None)
            raise ConnectionResetError(str(e)) from e

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

    def _load_polling_upstream_pairs(self) -> list[tuple[ProxyZone, UpstreamTarget]]:
        """Phase 7 (§19) puis §18.2 (controle actif, reouverture du §23
        angle mort) : une paire (zone, upstream) par upstream dont
        `load_source != "none"` OU `active_health_check_enabled=True` -
        meme nom de methode conserve (reutilise telle quelle par
        `_start_proxy_load_pollers`/`_restart_proxy_load_pollers`, le
        mecanisme de tache de fond sous-jacent sert desormais les deux
        besoins, §18.2/§19 - voir docstring de `poll_upstream_load.py`).
        Filtrage en cache, reconstruit uniquement a `start()`/
        `reload_scoped()`, jamais par requete (`parse_proxy_zones`
        reste, lui, re-parse a chaque requete ailleurs - mais une tache
        de fond n'a pas de "requete", ce cache est le seul point de
        verite pour elle)."""
        option = self._config.options.get("reverse_proxy")
        if option is None or not option.enabled or self._proxy_client is None:
            return []
        pairs: list[tuple[ProxyZone, UpstreamTarget]] = []
        for zone in parse_proxy_zones(option.settings.get("zones", [])):
            for upstream in zone.upstreams:
                if upstream.load_source != "none" or upstream.active_health_check_enabled:
                    pairs.append((zone, upstream))
        return pairs

    def _start_proxy_load_pollers(self) -> None:
        """Appelee seulement depuis `start()`/`reload_scoped()` (jamais
        depuis `__init__`, avant qu'une boucle asyncio ne tourne
        reellement - §19 angle mort "tache de fond dans le cycle de vie
        du serveur"). `_load_polling_upstream_pairs()` retourne toujours
        `[]` si `self._proxy_client is None` (option desactivee) -
        aucune garde supplementaire necessaire ici (conserve quand meme
        une verification locale pour satisfaire le typage statique)."""
        proxy_client = self._proxy_client
        if proxy_client is None:
            return
        for zone, upstream in self._load_polling_upstream_pairs():
            task = asyncio.create_task(poll_upstream_load_forever(
                zone, upstream, proxy_client, self._proxy_health_state,
                self._proxy_client_ssl_context_verified, self._proxy_client_ssl_context_unverified,
            ))
            self._proxy_load_poll_tasks.append(task)

    async def _stop_proxy_load_pollers(self) -> None:
        tasks, self._proxy_load_poll_tasks = self._proxy_load_poll_tasks, []
        await stop_pollers(tasks)

    def _restart_proxy_load_pollers(self) -> None:
        """Appelee depuis `reload_scoped()` (SIGHUP) - volontairement
        SYNCHRONE : annule les anciennes taches sans attendre leur fin
        (`task.cancel()` suffit, aucune ressource cote client a drainer
        pour une sonde de charge) puis en recree de nouvelles a partir
        de la configuration fraichement rechargee, jamais un cumul."""
        for task in self._proxy_load_poll_tasks:
            task.cancel()
        self._proxy_load_poll_tasks = []
        self._start_proxy_load_pollers()

    async def _write_error_response(self, writer: asyncio.StreamWriter, status: HttpStatus) -> HttpResponse:
        response = HttpResponse.empty(status)
        try:
            await self._write_response(writer, response, keep_alive=False)
        except (ConnectionResetError, BrokenPipeError, OSError):
            pass
        return response

    def _log_unparsed_access(
        self, peer_ip: str, error: HttpParseError, response: HttpResponse, request_id: str,
    ) -> None:
        """Ligne d'access.log d'une requete refusee pendant l'analyse de sa tete (plan moteur C++ §14, valide
        2026-11-02 : visible par fail2ban et RIPOSTE). Ligne de requete brute telle que recue (`-` si illisible),
        IP client resolue avec les en-tetes deja lus - meme regle trusted_proxy qu'une requete complete."""
        headers = HttpHeaders.from_pairs(list(error.headers))
        entry = AccessLogEntry(
            remote_ip=self._resolve_remote_ip(peer_ip, headers),
            timestamp=datetime.now(timezone.utc),
            method="",
            request_target="",
            http_version="",
            status_code=int(response.status),
            response_size=response.content_length,
            referer=headers.get("referer"),
            user_agent=headers.get("user-agent"),
            request_id=request_id,
            raw_request_line=error.request_line if error.request_line is not None else "-",
        )
        self._logger.append_line(self._access_log_path, format_combined_log_line(entry))

    def _log_access(self, request: HttpRequest, response: HttpResponse, start_time: float) -> None:
        entry = AccessLogEntry(
            remote_ip=request.remote_ip,
            timestamp=datetime.now(timezone.utc),
            method=request.method,
            request_target=request.raw_path,
            http_version="HTTP/1.1",
            status_code=int(response.status),
            response_size=response.content_length,
            referer=request.header("referer"),
            user_agent=request.header("user-agent"),
            request_id=request.request_id,
        )
        self._logger.append_line(self._access_log_path, format_combined_log_line(entry))

    def log_error_line(self, message: str, request_id: str | None) -> None:
        """Journal d'erreurs, pour le processus de securite du moteur natif (meme format que le serveur)."""
        self._log_error(message, request_id)

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

    def _watch_source(self, ip: str, until: float | None = None) -> None:
        """Lot 3 du plan WAF natif : une source qui a un etat Active Defense (decision notable, leurre affecte) ne doit
        plus etre jugee seule par le natif - toutes ses requetes viennent ici, pendant la duree de cet etat (decision
        utilisateur 2026-11-04, Q2), ou jusqu'a l'expiration de son leurre si elle est plus lointaine. Seulement
        quand les leurres sont actifs : sans eux, rien dans l'etat d'une source ne change une requete propre."""
        config = self._active_defense_config
        if self.watch_sink is None or config is None or not config.deception.enabled:
            return
        horizon = self._clock.now().timestamp() + config.state_ttl_seconds
        self.watch_sink(ip, max(horizon, until or 0.0))

    def active_deception_sources(self) -> list[tuple[str, float]]:
        """(adresse, echeance) des affectations de leurre encore actives - processus de securite du natif (lot 3).
        L'identifiant d'une source est `adresse:empreinte` : l'adresse seule est suivie (sur-ensemble)."""
        config = self._active_defense_config
        if config is None or not config.deception.enabled or self._deception_assignment_repository is None:
            return []
        now = self._clock.now()
        return [(assignment.subject_id.rpartition(":")[0], assignment.expires_at.timestamp())
                for assignment in self._deception_assignment_repository.list_active()
                if is_assignment_active(assignment, now) and ":" in assignment.subject_id]

    def _active_defense_subject_id(self, request: HttpRequest) -> str:
        user_agent = request.header("user-agent") or ""
        return f"{request.remote_ip}:{user_agent_fingerprint(user_agent)}"

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
        try:
            state = self._observe_active_defense_threat_unguarded(request, decision)
        except Exception as error:  # noqa: BLE001 - Active Defense ne doit JAMAIS faire echouer une requete
            # Mesure du 2026-10-26 (S5) : une erreur SQLite non rattrapee ici coupait la connexion
            # sans reponse. Desormais la requete suit la decision du WAF seule ; une ligne par serie.
            if not self._active_defense_guard_failing:
                self._active_defense_guard_failing = True
                self._log_error(
                    f"Active Defense : observation ignorée ({error!r}) - la requête suit la décision du WAF",
                    request_id=request.request_id,
                )
            return None
        self._active_defense_guard_failing = False
        return state

    def flush_active_defense(self, timeout: float = 5.0) -> bool:
        """Attend que les ecritures differees deja deposees soient en base (tests, outils)."""
        if self._active_defense_writer is None:
            return True
        return self._active_defense_writer.flush(timeout)

    def _observe_active_defense_threat_unguarded(self, request: HttpRequest, decision: WafDecision) -> ThreatState:
        assert self._active_defense_config is not None
        assert self._threat_state_repository is not None
        assert self._active_defense_playbook is not None
        playbook = self._active_defense_playbook
        subject_id = self._active_defense_subject_id(request)
        state, observation, escalation = observe_threat(
            self._threat_state_repository, self._clock, self._active_defense_config,
            subject_id=subject_id, waf_decision=decision,
        )
        if escalation is not None:
            self._write_security_event(
                "threat_escalated", subject_id, request.remote_ip, escalation.occurred_at,
                level=escalation.new_level, previous_level=escalation.previous_level, score=state.score,
                attack_class=observation.attack_class if observation is not None else None,
            )
        threshold = self._active_defense_config.war_mode.thresholds.incident_score
        # Sous le seuil, create_or_update_incident ne fait rien par definition : aucun travail a
        # deposer (sous un botnet, c'est le cas de presque toutes les observations).
        if observation is not None and state.score >= threshold and validate_playbook_action("create_incident", playbook):
            if self._active_defense_writer is not None:
                # Les incidents ne changent pas la reponse : ecrits entierement par le fil
                # d'ecriture (OMEGA-SERV_ETUDE_ACTIVE_DEFENSE_STIX_MISP_CHARGE.md §3.6).
                clock, score, seen, remote_ip = self._clock, state.score, observation, request.remote_ip

                def record_incident(repositories: ActiveDefenseRepositories) -> None:
                    _incident, opened = create_or_update_incident(
                        repositories.incidents, clock, subject_id=subject_id, observation=seen,
                        score=score, incident_score_threshold=threshold, return_incident=False,
                    )
                    if opened is not None:  # fil d'ecriture : append_line est protege par un verrou
                        self._write_security_event(
                            "incident_opened", subject_id, remote_ip, opened.occurred_at,
                            score=score, attack_class=seen.attack_class, incident_id=opened.incident_id,
                        )

                self._active_defense_writer.submit(record_incident)
            elif self._incident_repository is not None:
                _incident, opened = create_or_update_incident(
                    self._incident_repository, self._clock, subject_id=subject_id, observation=observation,
                    score=state.score, incident_score_threshold=threshold,
                )
                if opened is not None:
                    self._write_security_event(
                        "incident_opened", subject_id, request.remote_ip, opened.occurred_at,
                        score=state.score, attack_class=observation.attack_class, incident_id=opened.incident_id,
                    )
        if (
            observation is not None
            and state.level in ("hostile", "contained")
            and self._active_defense_config.deception.enabled
            and self._deception_assignment_repository is not None
            and validate_playbook_action("redirect_to_decoy", playbook)
        ):
            assignment = assign_deception(
                self._deception_assignment_repository, self._clock, self._active_defense_config.deception,
                subject_id=subject_id, attack_class=observation.attack_class,
            )
            if assignment is not None:
                self._watch_source(request.remote_ip, assignment.expires_at.timestamp())
                self._write_security_event(
                    "deception_assigned", subject_id, request.remote_ip, assignment.assigned_at,
                    level=state.level, attack_class=observation.attack_class, decoy_profile=assignment.profile_name,
                )
        if (
            observation is not None
            and is_source_marked(state.level)
            and validate_playbook_action("enrich_log", playbook)
            and self._active_defense_enriched_log_path is not None
        ):
            self._write_active_defense_enriched_log(request, state, observation.attack_class)
        return state

    def _write_security_event(
        self,
        event_type: SecurityEventType,
        subject_id: str,
        remote_ip: str,
        occurred_at: datetime,
        **fields: Any,
    ) -> None:
        """Une ligne dans `security-events.jsonl` (lot 1 RIPOSTE) - jamais d'exception vers la
        requete : FileLineLogger avale deja toute OSError (une ligne sur stderr)."""
        if self._active_defense_security_events_path is None:
            return
        event = SecurityEvent(
            event_id=uuid.uuid4().hex, type=event_type, timestamp=occurred_at,
            subject_id=subject_id, remote_ip=remote_ip, **fields,
        )
        self._logger.append_line(self._active_defense_security_events_path, format_security_event_line(event))

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
            self._write_security_event(
                "decoy_hit", subject_id, request.remote_ip, self._clock.now(),
                decoy_profile=routing_decision.deception_profile_name,
            )
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
        self._write_security_event(
            "decoy_hit", self._active_defense_subject_id(request), request.remote_ip, self._clock.now(),
            decoy_profile=routing_decision.deception_profile_name or routing_decision.reverse_proxy_zone_name,
        )
        return await serve_proxy(
            request, zone, self._decoy_proxy_client, self._decoy_load_balancer, self._decoy_health_state,
            self._proxy_client_ssl_context_verified, self._proxy_client_ssl_context_unverified,
        )
