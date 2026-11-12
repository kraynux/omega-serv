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
fraiche, jamais une erreur immediate remontee a l'appelant.

Correctif 2.6.2 (D21, D22, D42 - OMEGA-SERV_PLAN_CORRECTIF_2.6.2.md §7) :
- D21 : `Content-Length` avec `Transfer-Encoding`, ou plusieurs longueurs
  differentes, ou une longueur qui n'est pas faite que de chiffres -> erreur
  (502 cote appelant), connexion fermee, jamais recyclee (RFC 9112 §6.3).
- D22 : une connexion ne revient au pool que si la reponse est HTTP/1.1, sans
  jeton `close`, de longueur connue lue exactement, et SANS octet en attente
  apres le corps ; reprise du pool : connexion jetee si fermee, a EOF ou avec
  des octets en attente. Sinon ces octets devenaient la reponse du client
  suivant.
- D42 : les methodes non rejouables (POST, PUT, PATCH, DELETE...) ouvrent
  toujours une connexion neuve, donc jamais de reprise ; la reprise interne
  ne vaut que pour GET/HEAD/OPTIONS et seulement si la connexion reutilisee
  n'a renvoye AUCUN octet de reponse. Avant : n'importe quelle requete etait
  renvoyee apres n'importe quelle erreur (POST recu deux fois)."""
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


def _parse_status_line(line: bytes) -> tuple[str, int]:
    text = line.decode("latin-1", errors="replace")
    parts = text.split(None, 2)
    if len(parts) < 2 or not parts[0].startswith("HTTP/"):
        raise ValueError(f"ligne de statut invalide : {text!r}")
    return parts[0], int(parts[1])


async def _read_headers(reader: asyncio.StreamReader, read_timeout: float) -> list[tuple[str, str]]:
    response_headers: list[tuple[str, str]] = []
    while True:
        line = await asyncio.wait_for(reader.readline(), timeout=read_timeout)
        if line in (b"\r\n", b""):
            break
        name, _, value = line.decode("latin-1").partition(":")
        response_headers.append((name.strip(), value.strip()))
    return response_headers


async def _read_status_and_headers(
    reader: asyncio.StreamReader, read_timeout: float, host: str, port: int,
) -> tuple[int, list[tuple[str, str]]]:
    status_line = await asyncio.wait_for(reader.readline(), timeout=read_timeout)
    if not status_line:
        raise HttpProxyConnectionError(f"upstream a fermé la connexion sans réponse ({host}:{port})")
    _version, status_code = _parse_status_line(status_line)
    return status_code, await _read_headers(reader, read_timeout)


def _response_content_length(response_headers: list[tuple[str, str]]) -> int | None:
    """D21 : longueur du corps sans ambiguite, sinon ValueError (502, connexion jamais recyclee)."""
    values = [value for name, value in response_headers if name.lower() == "content-length"]
    has_transfer_encoding = any(name.lower() == "transfer-encoding" for name, _ in response_headers)
    if not values:
        return None
    if has_transfer_encoding:
        raise ValueError("réponse avec Content-Length et Transfer-Encoding (RFC 9112 §6.3)")
    # Chiffres seulement (ni signe, ni liste « 2, 2 » - deja refusee avant) ; en-tetes repetes : meme valeur.
    if not all(value.isascii() and value.isdigit() for value in values) or len({int(value) for value in values}) != 1:
        raise ValueError(f"Content-Length invalide ou contradictoire : {values!r}")
    return int(values[0])


def _asks_close(response_headers: list[tuple[str, str]]) -> bool:
    """D22 : `Connection` est une liste de jetons (`close, x`), sans tenir compte de la casse."""
    return any(
        token.strip().lower() == "close"
        for name, value in response_headers if name.lower() == "connection"
        for token in value.split(",")
    )


def _has_pending_bytes(reader: asyncio.StreamReader) -> bool:
    """D22 : octets deja recus et pas encore lus. asyncio n'a pas d'acces public : attribut interne
    `_buffer` (stable depuis Python 3.4). S'il disparaissait, on repond « oui » : plus aucun recyclage,
    jamais un recyclage sale (le test de reutilisation du pool le signalerait aussitot)."""
    buffer = getattr(reader, "_buffer", None)
    return buffer is None or len(buffer) > 0


_REPLAYABLE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
"""D42 : meme liste que `_IDEMPOTENT_RETRY_METHODS` (application/server/serve_proxy.py) - seules
ces methodes passent par une connexion du pool et peuvent etre rejouees sur une connexion neuve."""


class _NoResponseFromReusedConnection(HttpProxyConnectionError):
    """D42 : connexion du pool morte avant le moindre octet de reponse - seul cas de reprise interne."""


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
        raise HttpProxyConnectionError(f"connexion à l'upstream impossible ({host}:{port}) : {e}") from e


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
            if writer.is_closing() or reader.at_eof() or reader.exception() is not None or _has_pending_bytes(reader):
                writer.close()  # D22 : fermee, fermee par le backend, ou octets arrives hors reponse
                continue
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

        reused = self._borrow_idle_connection(key) if method in _REPLAYABLE_METHODS else None  # D42
        if reused is not None:
            try:
                return await self._send_and_read(
                    key, reused, method, path, headers, body, read_timeout, host, port, reused=True,
                )
            except _NoResponseFromReusedConnection:
                pass  # connexion morte dans le pool, rien recu : une seule reprise, connexion neuve

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
        reused: bool = False,
    ) -> HttpProxyResult:
        reader, writer = connection
        response_started = False
        try:
            request_line = f"{method} {path} HTTP/1.1\r\n"
            header_lines = "".join(f"{name}: {value}\r\n" for name, value in headers)
            writer.write((request_line + header_lines + "\r\n").encode("latin-1") + body)
            await writer.drain()

            status_line = await asyncio.wait_for(reader.readline(), timeout=read_timeout)
            if not status_line:
                raise ConnectionResetError("upstream a fermé la connexion sans réponse")
            response_started = True
            version, status_code = _parse_status_line(status_line)
            response_headers = await _read_headers(reader, read_timeout)
            content_length = _response_content_length(response_headers)  # D21

            if content_length is not None:
                response_body = await asyncio.wait_for(reader.readexactly(content_length), timeout=read_timeout)
                # D22 : HTTP/1.1, aucun jeton close, et rien apres le corps annonce
                reusable = version == "HTTP/1.1" and not _asks_close(response_headers) and not _has_pending_bytes(reader)
            else:
                response_body = await asyncio.wait_for(reader.read(), timeout=read_timeout)
                reusable = False
        except (asyncio.IncompleteReadError, asyncio.TimeoutError, ValueError, OSError) as e:
            await _close_quietly(writer)
            error = _NoResponseFromReusedConnection if reused and not response_started else HttpProxyConnectionError
            raise error(f"erreur de communication avec l'upstream ({host}:{port}) : {e}") from e

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
