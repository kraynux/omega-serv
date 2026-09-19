"""Cas d'usage : court-circuiter la boucle de requete/reponse HTTP
habituelle pour relayer un tube WebSocket bidirectionnel vers un
backend amont (reverse proxy sortant, OMEGA-SERV_PLAN-DETAILLE_
REVERSE_PROXY.md §4). Chemin de code SEPARE de `serve_proxy.py`, jamais
une variante de celui-ci - la forme meme du resultat differe (un tube
ouvert, pas une seule `HttpResponse` a retourner), donc cette fonction
ecrit elle-meme directement sur `client_writer` plutot que de retourner
une valeur a l'appelant.

Round-robin (meme `ProxyRoundRobinState` que `serve_proxy.py`) choisit
l'upstream UNE SEULE FOIS pour toute la duree du tube - aucune bascule
possible une fois la mise a niveau reussie, a la difference du relai
HTTP ordinaire qui peut choisir un upstream different a chaque requete
individuelle (§4 du document, une connexion persistante n'a pas de sens
avec une repartition par requete).

Aucun timeout applicatif une fois le tube etabli (§4, angle mort
recense) : `_relay_bidirectional` ne borne jamais ses lectures - un
WebSocket legitime peut rester ouvert des heures. Les timeouts HTTP
existants (`read_timeout_seconds`/`keepalive_timeout_seconds`) ne
s'appliquent qu'a la phase de handshake initiale, jamais au tube."""
from __future__ import annotations

import asyncio
import contextlib
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import ssl

from omega_serv.application.server.serve_proxy import HOP_BY_HOP_HEADERS, build_outgoing_headers
from omega_serv.domain.http.request import HttpRequest
from omega_serv.domain.http.status_codes import HttpStatus, reason_phrase_for
from omega_serv.domain.routing.proxy_zone import ProxyRoundRobinState, ProxyZone
from omega_serv.ports.http_proxy_client_port import HttpProxyClientPort, HttpProxyConnectionError

_RELAY_CHUNK_BYTES = 65536
_UPGRADE_HOP_BY_HOP_HEADERS = HOP_BY_HOP_HEADERS - {"connection", "upgrade"}


async def _write_status_line_and_headers(
    writer: asyncio.StreamWriter, status_code: int, headers: tuple[tuple[str, str], ...],
) -> None:
    status_line = f"HTTP/1.1 {status_code} {reason_phrase_for(status_code)}\r\n"
    header_lines = "".join(
        f"{name}: {value}\r\n" for name, value in headers if name.lower() not in _UPGRADE_HOP_BY_HOP_HEADERS
    )
    writer.write((status_line + header_lines + "\r\n").encode("latin-1"))
    with contextlib.suppress(ConnectionResetError, BrokenPipeError, OSError):
        await writer.drain()


async def _pump(source: asyncio.StreamReader, destination: asyncio.StreamWriter) -> None:
    try:
        while True:
            chunk = await source.read(_RELAY_CHUNK_BYTES)
            if not chunk:
                break
            destination.write(chunk)
            await destination.drain()
    except (ConnectionResetError, BrokenPipeError, OSError):
        pass


async def _relay_bidirectional(
    client_reader: asyncio.StreamReader,
    client_writer: asyncio.StreamWriter,
    upstream_reader: asyncio.StreamReader,
    upstream_writer: asyncio.StreamWriter,
) -> None:
    client_to_upstream = asyncio.create_task(_pump(client_reader, upstream_writer))
    upstream_to_client = asyncio.create_task(_pump(upstream_reader, client_writer))
    try:
        await asyncio.wait({client_to_upstream, upstream_to_client}, return_when=asyncio.FIRST_COMPLETED)
    finally:
        for task in (client_to_upstream, upstream_to_client):
            if not task.done():
                task.cancel()
        with contextlib.suppress(Exception):
            await asyncio.gather(client_to_upstream, upstream_to_client, return_exceptions=True)
        upstream_writer.close()
        with contextlib.suppress(Exception):
            await upstream_writer.wait_closed()


async def serve_websocket_proxy(
    request: HttpRequest,
    zone: ProxyZone,
    proxy_client: HttpProxyClientPort,
    round_robin: ProxyRoundRobinState,
    client_reader: asyncio.StreamReader,
    client_writer: asyncio.StreamWriter,
    client_ssl_context_verified: ssl.SSLContext | None = None,
    client_ssl_context_unverified: ssl.SSLContext | None = None,
) -> int:
    """Retourne le statut ecrit au client (101 si le tube a ete etabli
    et relaye jusqu'a sa fermeture, tout autre statut si l'upstream a
    refuse la mise a niveau ou etait inatteignable) - utilise par
    l'appelant (infrastructure/server/asyncio_server.py) uniquement
    pour la ligne d'acces, jamais pour decider quoi que ce soit."""
    index = round_robin.pick(zone.url_prefix, len(zone.upstreams))
    upstream = zone.upstreams[index]

    target = request.path + (f"?{request.query}" if request.query else "")
    outgoing_headers = build_outgoing_headers(request, zone, upstream, preserve_upgrade=True)

    ssl_context = None
    if upstream.use_tls:
        ssl_context = client_ssl_context_verified if zone.verify_upstream_tls else client_ssl_context_unverified

    try:
        handshake = await proxy_client.open_websocket_tunnel(
            upstream.host, upstream.port, request.method, target,
            outgoing_headers, zone.connect_timeout_seconds, zone.read_timeout_seconds, ssl_context,
        )
    except HttpProxyConnectionError:
        await _write_status_line_and_headers(client_writer, int(HttpStatus.BAD_GATEWAY), ())
        return int(HttpStatus.BAD_GATEWAY)

    await _write_status_line_and_headers(client_writer, handshake.status_code, handshake.headers)

    if handshake.status_code != 101 or handshake.reader is None or handshake.writer is None:
        return handshake.status_code

    await _relay_bidirectional(client_reader, client_writer, handshake.reader, handshake.writer)
    return handshake.status_code
