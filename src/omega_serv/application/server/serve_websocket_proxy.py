"""Cas d'usage : court-circuiter la boucle de requete/reponse HTTP
habituelle pour relayer un tube WebSocket bidirectionnel vers un
backend amont (reverse proxy sortant, OMEGA-SERV_PLAN-DETAILLE_
REVERSE_PROXY.md §4). Chemin de code SEPARE de `serve_proxy.py`, jamais
une variante de celui-ci - la forme meme du resultat differe (un tube
ouvert, pas une seule `HttpResponse` a retourner), donc cette fonction
ecrit elle-meme directement sur `client_writer` plutot que de retourner
une valeur a l'appelant.

`ProxyLoadBalancerState` (meme instance que `serve_proxy.py`, Phase 5
§16/§27.1) choisit l'upstream UNE SEULE FOIS pour toute la duree du
tube - aucune bascule possible une fois la mise a niveau reussie, a la
difference du relai HTTP ordinaire qui peut choisir un upstream
different a chaque requete individuelle (§4 du document, une connexion
persistante n'a pas de sens avec une repartition par requete). La
"connexion active" (acquire/release) reste comptabilisee pendant TOUTE
la duree de vie du tube (pas seulement le handshake) - un tube
WebSocket ouvert occupe reellement l'upstream pour les strategies
least_connections. Le temps de reponse enregistre (`least_response_time`)
ne mesure que la duree du HANDSHAKE (jusqu'au 101), jamais la duree du
tube lui-meme.

Plan proxy natif v2, lot 10 (Q11, C14, C17 ; decisions de l'auteur du
2026-11-14) : un tube qui ne transporte aucun octet, dans aucun sens,
pendant `zone.websocket_idle_timeout_seconds` (3 600 s par defaut, 0 =
aucun delai) est ferme par une trame 1001 vers le client et vers le
backend - de meme a la fin du delai de grace de l'arret (annulation de la
tache). La trame n'est inseree qu'entre deux trames (`WebSocketFrameTracker`
ne lit que leurs en-tetes) ; une trame coupee en plein milieu : fermeture
sans 1001. `TunnelStats` porte au journal les octets envoyes au client
pendant le tube (comme `$body_bytes_sent` de nginx ; avant, 0). Les timeouts
HTTP (`read_timeout_seconds`/`keepalive_timeout_seconds`) ne s'appliquent
qu'a la phase de handshake initiale, jamais au tube.

Phase 5bis (§17/§27.3) : le choix d'upstream suit `resolve_upstream()`
(meme fonction que `serve_proxy.py`, regle d'en-tete > cookie sticky >
strategie active) - une mise a niveau WebSocket est une requete HTTP
ordinaire jusqu'au 101, le cookie sticky doit donc etre lu/honore des
ce choix initial. Le cookie sticky n'est pose QUE si le 101 est reellement
obtenu (jamais sur un rejet/une erreur de connexion) - ecrit en ligne
brute ici (`_write_status_line_and_headers`), PAS via `HttpResponse.
set_header` (limitation structurelle de `HttpResponse`, dict[str,str],
une seule valeur par en-tete - sans objet sur ce chemin de code qui
n'utilise jamais `HttpResponse`).

Phase 6 (§18.1/§18.3) : `resolve_upstream()` filtre desormais par
eligibilite (`ProxyHealthState`) et `record_failure`/`record_success`
alimentent le meme etat que `serve_proxy.py` (controle PASSIF, cle par
zone - un upstream marque `DOWN` via le trafic HTTP ordinaire est
immediatement exclu des nouveaux tubes WebSocket, et reciproquement).
**Pas de retry ici** (§18.4 existe pour `serve_proxy.py` uniquement) :
une nouvelle tentative impliquerait de re-acquerir/liberer l'upstream
en cours de tube, une semantique plus delicate que pour une requete
HTTP ordinaire sans benefice demontre - deliberement non construit
plutot que risquer un bug subtil d'acquire/release autour d'un tube
persistant.

Phase 7bis (§20) : `resolve_upstream()` peut lever
`AllUpstreamsAtCapacityError` (tous les upstreams sains au plafond de
backpressure) - traduit en 503 ici, meme discipline que
`serve_proxy.py`."""
from __future__ import annotations

import asyncio
import contextlib
import os
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import ssl

from omega_serv.application.server.serve_proxy import (
    HOP_BY_HOP_HEADERS,
    MAX_PROXY_HOPS,
    AllUpstreamsAtCapacityError,
    ForwardingContext,
    build_outgoing_headers,
    incoming_proxy_hop_count,
    resolve_upstream,
    upstream_ssl_context,
)
from omega_serv.domain.http.cookies import build_set_cookie_header
from omega_serv.domain.http.request import HttpRequest
from omega_serv.domain.http.status_codes import HttpStatus, reason_phrase_for
from omega_serv.domain.http.websocket import (
    WebSocketFrameTracker,
    close_frame_to_client,
    close_frame_to_server,
)
from omega_serv.domain.routing.proxy_health import ProxyHealthState
from omega_serv.domain.routing.proxy_zone import (
    ProxyLoadBalancerState,
    ProxyZone,
    sticky_cookie_value_for,
)
from omega_serv.ports.http_proxy_client_port import HttpProxyClientPort, HttpProxyConnectionError

_RELAY_CHUNK_BYTES = 65536
_UPGRADE_HOP_BY_HOP_HEADERS = HOP_BY_HOP_HEADERS - {"connection", "upgrade"}
_CLOSE_FLUSH_SECONDS = 2.0
"""Lot 10 : temps laisse a la trame 1001 (et a ce qui la precede) pour partir, avant la fermeture."""


@dataclass
class TunnelStats:
    """Lot 10 : rempli pendant le tube, lu par l'appelant pour la ligne d'access.log - meme apres une annulation
    (arret du serveur), ou la valeur de retour n'existe pas."""

    status: int | None = None
    """Statut ecrit au client (None : rien d'ecrit)."""
    bytes_to_client: int = 0
    """Octets du backend envoyes au client apres le 101 (decision de l'auteur du 2026-11-14)."""


class _Activity:
    __slots__ = ("last",)

    def __init__(self, now: float) -> None:
        self.last = now


async def _write_status_line_and_headers(
    writer: asyncio.StreamWriter, status_code: int, headers: tuple[tuple[str, str], ...],
) -> None:
    status_line = f"HTTP/1.1 {status_code} {reason_phrase_for(status_code)}\r\n"
    kept = [(name, value) for name, value in headers if name.lower() not in _UPGRADE_HOP_BY_HOP_HEADERS]
    if status_code != 101:
        # Plan proxy natif v2, lot 1 (D14) : un refus transmettait le `Content-Length` du backend sans son corps
        # (abandonne) - le client attendait des octets qui ne venaient jamais. Refus = aucun corps, annonce comme tel.
        kept = [(name, value) for name, value in kept if name.lower() not in ("content-length", "connection")]
        kept += [("Content-Length", "0"), ("Connection", "close")]
    header_lines = "".join(f"{name}: {value}\r\n" for name, value in kept)
    writer.write((status_line + header_lines + "\r\n").encode("latin-1"))
    with contextlib.suppress(ConnectionResetError, BrokenPipeError, OSError):
        await writer.drain()


async def _pump(
    source: asyncio.StreamReader, destination: asyncio.StreamWriter, tracker: WebSocketFrameTracker,
    activity: _Activity, stats: TunnelStats | None,
) -> None:
    loop = asyncio.get_running_loop()
    try:
        while True:
            chunk = await source.read(_RELAY_CHUNK_BYTES)
            if not chunk:
                break
            activity.last = loop.time()
            tracker.feed(chunk)  # meme instant que write() : le reperage suit exactement ce qui est en file
            destination.write(chunk)
            if stats is not None:
                stats.bytes_to_client += len(chunk)
            await destination.drain()
    except (ConnectionResetError, BrokenPipeError, OSError):
        pass


async def _idle_watchdog(activity: _Activity, idle_timeout: float) -> None:
    loop = asyncio.get_running_loop()
    while True:
        remaining = activity.last + idle_timeout - loop.time()
        if remaining <= 0:
            return
        await asyncio.sleep(remaining)


async def _send_going_away(
    client_writer: asyncio.StreamWriter, to_client: WebSocketFrameTracker,
    upstream_writer: asyncio.StreamWriter, to_upstream: WebSocketFrameTracker,
) -> None:
    """Lot 10 : trame 1001 dans chaque sens ou elle tombe entre deux trames, puis un court delai pour partir."""
    for writer, tracker, frame in ((client_writer, to_client, close_frame_to_client()),
                                   (upstream_writer, to_upstream, close_frame_to_server(os.urandom(4)))):
        if tracker.can_send_close and not writer.is_closing():
            writer.write(frame)
    for writer in (client_writer, upstream_writer):
        with contextlib.suppress(Exception):
            await asyncio.wait_for(writer.drain(), timeout=_CLOSE_FLUSH_SECONDS)


async def _relay_bidirectional(
    client_reader: asyncio.StreamReader,
    client_writer: asyncio.StreamWriter,
    upstream_reader: asyncio.StreamReader,
    upstream_writer: asyncio.StreamWriter,
    idle_timeout: float = 0.0,
    stats: TunnelStats | None = None,
) -> None:
    activity = _Activity(asyncio.get_running_loop().time())
    to_upstream, to_client = WebSocketFrameTracker(), WebSocketFrameTracker()
    pumps = {
        asyncio.create_task(_pump(client_reader, upstream_writer, to_upstream, activity, None)),
        asyncio.create_task(_pump(upstream_reader, client_writer, to_client, activity, stats)),
    }
    watched = set(pumps)
    if idle_timeout > 0:
        watched.add(asyncio.create_task(_idle_watchdog(activity, idle_timeout)))
    going_away = True  # annulation (fin du delai de grace de l'arret) : 1001 aussi
    try:
        done, _ = await asyncio.wait(watched, return_when=asyncio.FIRST_COMPLETED)
        going_away = not done & pumps  # seul le delai d'inactivite a expire ; sinon un cote a ferme
    finally:
        for task in watched:
            if not task.done():
                task.cancel()
        with contextlib.suppress(Exception):
            await asyncio.gather(*watched, return_exceptions=True)
        if going_away:
            await _send_going_away(client_writer, to_client, upstream_writer, to_upstream)
        upstream_writer.close()
        with contextlib.suppress(Exception):
            await asyncio.wait_for(upstream_writer.wait_closed(), timeout=_CLOSE_FLUSH_SECONDS)


async def serve_websocket_proxy(
    request: HttpRequest,
    zone: ProxyZone,
    proxy_client: HttpProxyClientPort,
    load_balancer: ProxyLoadBalancerState,
    health_state: ProxyHealthState,
    client_reader: asyncio.StreamReader,
    client_writer: asyncio.StreamWriter,
    client_ssl_context_verified: ssl.SSLContext | None = None,
    client_ssl_context_unverified: ssl.SSLContext | None = None,
    forwarding: ForwardingContext | None = None,
    stats: TunnelStats | None = None,
) -> int:
    """Retourne le statut ecrit au client (101 si le tube a ete etabli
    et relaye jusqu'a sa fermeture, tout autre statut si l'upstream a
    refuse la mise a niveau ou etait inatteignable) - utilise par
    l'appelant (infrastructure/server/asyncio_server.py) uniquement
    pour la ligne d'acces, jamais pour decider quoi que ce soit."""
    if incoming_proxy_hop_count(request) >= MAX_PROXY_HOPS:
        # Meme garde-fou anti-boucle indirecte que serve_proxy.py (§23 angle mort #16).
        await _write_status_line_and_headers(client_writer, int(HttpStatus.BAD_GATEWAY), ())
        return int(HttpStatus.BAD_GATEWAY)
    try:
        upstream = resolve_upstream(request, zone, load_balancer, health_state)
    except AllUpstreamsAtCapacityError:
        await _write_status_line_and_headers(client_writer, int(HttpStatus.SERVICE_UNAVAILABLE), ())
        return int(HttpStatus.SERVICE_UNAVAILABLE)
    zone_key = zone.url_prefix

    target = request.path + (f"?{request.query}" if request.query else "")
    outgoing_headers = build_outgoing_headers(request, zone, upstream, preserve_upgrade=True, forwarding=forwarding)

    ssl_context = upstream_ssl_context(upstream, zone, client_ssl_context_verified, client_ssl_context_unverified)

    load_balancer.acquire(zone_key, upstream)
    health_state.record_request(zone_key, upstream)
    started_at = time.monotonic()
    try:
        try:
            handshake = await proxy_client.open_websocket_tunnel(
                upstream.host, upstream.port, request.method, target,
                outgoing_headers, zone.connect_timeout_seconds, zone.read_timeout_seconds, ssl_context,
            )
        except HttpProxyConnectionError:
            load_balancer.record_response_time(zone_key, upstream, zone.read_timeout_seconds)
            health_state.record_failure(zone_key, upstream, unhealthy_after=zone.unhealthy_after)
            health_state.record_error(zone_key, upstream, int(HttpStatus.BAD_GATEWAY))
            await _write_status_line_and_headers(client_writer, int(HttpStatus.BAD_GATEWAY), ())
            return int(HttpStatus.BAD_GATEWAY)
        load_balancer.record_response_time(zone_key, upstream, time.monotonic() - started_at)
        health_state.record_success(zone_key, upstream, healthy_after=zone.healthy_after)

        outgoing_response_headers = handshake.headers
        if zone.sticky_session_enabled and handshake.status_code == 101:
            outgoing_response_headers = (*handshake.headers, ("Set-Cookie", build_set_cookie_header(
                zone.sticky_cookie_name, sticky_cookie_value_for(upstream),
                max_age_seconds=zone.sticky_cookie_max_age_seconds,
            )))
        await _write_status_line_and_headers(client_writer, handshake.status_code, outgoing_response_headers)
        if stats is not None:
            stats.status = handshake.status_code

        if handshake.status_code != 101 or handshake.reader is None or handshake.writer is None:
            return handshake.status_code

        await _relay_bidirectional(client_reader, client_writer, handshake.reader, handshake.writer,
                                   zone.websocket_idle_timeout_seconds, stats)
        return handshake.status_code
    finally:
        load_balancer.release(zone_key, upstream)
