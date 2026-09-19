"""Implementation reelle de HttpProxyClientPort - client HTTP/1.1 ecrit
a la main (meme parti que le client FastCGI, infrastructure/fastcgi/
asyncio_fastcgi_client.py : aucune bibliotheque HTTP tierce).

Phase 3 (§5.3/§12 du document) : upstream HTTPS via `ssl_context` deja
construit (jamais construit ici - le contrat import-linter confine
"ssl" a infrastructure.tls.ssl_context_builder, ce module ne fait que
le transmettre a asyncio.open_connection). Toujours pas de Transfer-
Encoding: chunked en reponse (Content-Length ou lecture jusqu'a EOF
seulement) - meme limite deliberee que infrastructure/server/
http_parser.py (perimetre reduit d'abord, chunked est un chantier a
part).

Phase 4 (WebSocket, §4/§14) : `open_websocket_tunnel` ne lit JAMAIS de
corps de reponse - un statut 101 n'en a pas (le tube commence
immediatement apres les en-tetes), et un rejet (tout autre statut)
n'a rien a relayer ici, le corps eventuel de ce rejet est simplement
abandonne a la fermeture (limitation deliberee, documentee - jamais
suppose necessaire d'emblee). Jamais concerne par le pool ci-dessous :
un tunnel etabli n'est par nature jamais reutilisable pour autre chose.

Retour utilisateur (audit performance, 2026-09-14) : `forward_request`
ouvrait une connexion TCP/TLS neuve a CHAQUE requete relayee, puis la
refermait systematiquement - une poignee de main complete (handshake
TLS inclus) par requete au lieu de reutiliser une connexion persistante,
alors meme qu'aucun cote (client apres retrait des en-tetes hop-by-hop,
upstream sauf mention contraire) ne demandait explicitement la
fermeture. `AsyncioHttpProxyClient` garde desormais un petit pool de
connexions IDLE par upstream (host, port, TLS ou non), reutilisees pour
la requete suivante vers le meme upstream. Regle de reutilisation
stricte : seule une reponse avec un VRAI `Content-Length` (jamais une
lecture "jusqu'a EOF", qui exige structurellement que le pair ferme la
connexion) et sans `Connection: close` explicite est retournee au pool -
une connexion recuperee du pool qui s'avere en realite deja morte
cote upstream (ferme silencieusement pendant son inactivite, tres
courant) declenche une seule reprise automatique avec une connexion
fraiche, jamais une erreur immediate remontee a l'appelant."""
from __future__ import annotations

import asyncio
import contextlib
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import ssl

from omega_serv.ports.http_proxy_client_port import (
    HttpProxyConnectionError,
    HttpProxyResult,
    WebSocketUpstreamHandshake,
)


def _parse_status_line(line: bytes) -> int:
    text = line.decode("latin-1", errors="replace")
    parts = text.split(None, 2)
    if len(parts) < 2 or not parts[0].startswith("HTTP/"):
        raise ValueError(f"ligne de statut invalide : {text!r}")
    return int(parts[1])


async def _read_status_and_headers(
    reader: asyncio.StreamReader, read_timeout: float, host: str, port: int,
) -> tuple[int, list[tuple[str, str]]]:
    status_line = await asyncio.wait_for(reader.readline(), timeout=read_timeout)
    if not status_line:
        raise HttpProxyConnectionError(f"upstream a ferme la connexion sans reponse ({host}:{port})")
    status_code = _parse_status_line(status_line)

    response_headers: list[tuple[str, str]] = []
    while True:
        line = await asyncio.wait_for(reader.readline(), timeout=read_timeout)
        if line in (b"\r\n", b""):
            break
        name, _, value = line.decode("latin-1").partition(":")
        response_headers.append((name.strip(), value.strip()))
    return status_code, response_headers


async def _open_connection(
    host: str, port: int, connect_timeout: float, ssl_context: ssl.SSLContext | None,
) -> tuple[asyncio.StreamReader, asyncio.StreamWriter]:
    try:
        return await asyncio.wait_for(
            asyncio.open_connection(
                host, port, ssl=ssl_context, server_hostname=host if ssl_context is not None else None,
            ),
            timeout=connect_timeout,
        )
    except (OSError, asyncio.TimeoutError) as e:
        raise HttpProxyConnectionError(f"connexion a l'upstream impossible ({host}:{port}) : {e}") from e


async def _close_quietly(writer: asyncio.StreamWriter) -> None:
    writer.close()
    with contextlib.suppress(Exception):
        await writer.wait_closed()


_MAX_IDLE_CONNECTIONS_PER_UPSTREAM = 10
_PoolKey = tuple[str, int, bool]
_Connection = tuple[asyncio.StreamReader, asyncio.StreamWriter]


class AsyncioHttpProxyClient:
    def __init__(self) -> None:
        self._idle: dict[_PoolKey, list[_Connection]] = {}

    def _pool_key(self, host: str, port: int, ssl_context: ssl.SSLContext | None) -> _PoolKey:
        return (host, port, ssl_context is not None)

    def _borrow_idle_connection(self, key: _PoolKey) -> _Connection | None:
        pool = self._idle.get(key)
        while pool:
            reader, writer = pool.pop()
            if not writer.is_closing():
                return reader, writer
        return None

    def _release_connection(self, key: _PoolKey, connection: _Connection) -> None:
        pool = self._idle.setdefault(key, [])
        if len(pool) >= _MAX_IDLE_CONNECTIONS_PER_UPSTREAM:
            connection[1].close()
            return
        pool.append(connection)

    async def forward_request(
        self,
        host: str,
        port: int,
        method: str,
        path: str,
        headers: tuple[tuple[str, str], ...],
        body: bytes,
        connect_timeout: float,
        read_timeout: float,
        ssl_context: ssl.SSLContext | None = None,
    ) -> HttpProxyResult:
        key = self._pool_key(host, port, ssl_context)

        reused = self._borrow_idle_connection(key)
        if reused is not None:
            try:
                return await self._send_and_read(key, reused, method, path, headers, body, read_timeout, host, port)
            except HttpProxyConnectionError:
                pass

        connection = await _open_connection(host, port, connect_timeout, ssl_context)
        return await self._send_and_read(key, connection, method, path, headers, body, read_timeout, host, port)

    async def _send_and_read(
        self,
        key: _PoolKey,
        connection: _Connection,
        method: str,
        path: str,
        headers: tuple[tuple[str, str], ...],
        body: bytes,
        read_timeout: float,
        host: str,
        port: int,
    ) -> HttpProxyResult:
        reader, writer = connection
        try:
            request_line = f"{method} {path} HTTP/1.1\r\n"
            header_lines = "".join(f"{name}: {value}\r\n" for name, value in headers)
            writer.write((request_line + header_lines + "\r\n").encode("latin-1") + body)
            await writer.drain()

            status_code, response_headers = await _read_status_and_headers(reader, read_timeout, host, port)
            content_length = next(
                (int(value) for name, value in response_headers if name.lower() == "content-length"), None,
            )
            upstream_wants_close = any(
                name.lower() == "connection" and value.lower() == "close" for name, value in response_headers
            )

            if content_length is not None:
                response_body = await asyncio.wait_for(reader.readexactly(content_length), timeout=read_timeout)
                reusable = not upstream_wants_close
            else:
                response_body = await asyncio.wait_for(reader.read(), timeout=read_timeout)
                reusable = False
        except (asyncio.IncompleteReadError, asyncio.TimeoutError, ValueError, OSError) as e:
            await _close_quietly(writer)
            raise HttpProxyConnectionError(f"erreur de communication avec l'upstream ({host}:{port}) : {e}") from e

        if reusable:
            self._release_connection(key, (reader, writer))
        else:
            await _close_quietly(writer)

        return HttpProxyResult(status_code=status_code, headers=tuple(response_headers), body=response_body)

    async def open_websocket_tunnel(
        self,
        host: str,
        port: int,
        method: str,
        path: str,
        headers: tuple[tuple[str, str], ...],
        connect_timeout: float,
        read_timeout: float,
        ssl_context: ssl.SSLContext | None = None,
    ) -> WebSocketUpstreamHandshake:
        reader, writer = await _open_connection(host, port, connect_timeout, ssl_context)

        try:
            request_line = f"{method} {path} HTTP/1.1\r\n"
            header_lines = "".join(f"{name}: {value}\r\n" for name, value in headers)
            writer.write((request_line + header_lines + "\r\n").encode("latin-1"))
            await writer.drain()
            status_code, response_headers = await _read_status_and_headers(reader, read_timeout, host, port)
        except (asyncio.TimeoutError, ValueError, OSError) as e:
            await _close_quietly(writer)
            raise HttpProxyConnectionError(f"erreur de communication avec l'upstream ({host}:{port}) : {e}") from e

        if status_code != 101:
            await _close_quietly(writer)
            return WebSocketUpstreamHandshake(status_code=status_code, headers=tuple(response_headers), reader=None, writer=None)

        return WebSocketUpstreamHandshake(status_code=status_code, headers=tuple(response_headers), reader=reader, writer=writer)
