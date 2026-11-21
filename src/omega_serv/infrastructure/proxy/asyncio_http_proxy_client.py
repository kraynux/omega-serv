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
  renvoyee apres n'importe quelle erreur (POST recu deux fois).

Plan proxy natif v2, lot 1 (contrat C5, exigences S7 a S14 de
OMEGA-SERV_ANALYSES_PROXY_NATIF.md) - la reference que le natif reproduira :
- S7, S8 (D24) : ligne de statut `HTTP/1.x` + trois chiffres de 100 a 599 ;
  en-tetes stricts (nom en tchar, ni controle ni NUL dans la valeur, aucune
  ligne repliee), en nombre et en taille bornes. Sinon 502.
- S12 : reponses 1xx lues puis ignorees (8 au plus) jusqu'a la reponse finale ;
  HEAD, 204 et 304 n'ont JAMAIS de corps, quel que soit `Content-Length` (D1,
  D2 : on attendait un corps qui ne venait pas, puis 502).
- S11 (D3) : `Transfer-Encoding: chunked` decode et valide (taille hexadecimale
  bornee, CRLF stricts, trailers bornes puis retires) ; le corps decode est
  relaye. S10 : tout autre `Transfer-Encoding` -> 502 (decision de l'auteur).
- S13 (D23) : corps borne par `max_body_bytes` (options.reverse_proxy.
  max_response_body_mb) -> `HttpProxyResponseTooLargeError` ; lecture
  jusqu'a la fermeture bornee de meme, jamais recyclee.
- C11 : `read_timeout` vaut entre deux blocs recus, plus pour la reponse
  entiere ; un delai depasse apres l'envoi -> `HttpProxyTimeoutError` (504).
- D4 : la cle du pool distingue le contexte TLS (verifie ou non)."""
from __future__ import annotations

import asyncio
import contextlib
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import ssl

from omega_serv.ports.http_proxy_client_port import (
    HttpProxyConnectionError,
    HttpProxyResponseTooLargeError,
    HttpProxyResult,
    HttpProxyTimeoutError,
    HttpProxyTlsError,
    WebSocketUpstreamHandshake,
)

_STATUS_LINE = re.compile(rb"(HTTP/1\.[01]) ([1-5][0-9]{2})(?:[ \t][^\r\n\x00]*)?\r?\n")
_TOKEN = re.compile(rb"[!#$%&'*+\-.^_`|~0-9A-Za-z]+")
_FORBIDDEN_IN_VALUE = re.compile(rb"[\x00-\x08\x0a-\x1f\x7f]")
_HEX = re.compile(rb"[0-9A-Fa-f]{1,16}")
MAX_RESPONSE_HEADERS = 100
MAX_RESPONSE_HEADER_BYTES = 64 * 1024
MAX_INTERIM_RESPONSES = 8
MAX_CHUNK_LINE_BYTES = 4096
MAX_TRAILER_LINES = 32
MAX_TRAILER_BYTES = 16 * 1024
_READ_BLOCK = 64 * 1024


def _parse_status_line(line: bytes) -> tuple[str, int]:
    """S7 : `HTTP/1.0` ou `HTTP/1.1`, un espace, trois chiffres de 100 a 599 (phrase facultative)."""
    match = _STATUS_LINE.fullmatch(line)
    if match is None:
        raise ValueError(f"ligne de statut invalide : {line[:200]!r}")
    return match.group(1).decode("ascii"), int(match.group(2))


def _parse_header_line(line: bytes) -> tuple[str, str]:
    """S8 : nom en tchar, valeur sans controle (tabulation permise), jamais une ligne repliee."""
    if line[:1] in (b" ", b"\t"):
        raise ValueError("en-tete replie (obs-fold) refuse")
    content = line[:-2] if line.endswith(b"\r\n") else line[:-1] if line.endswith(b"\n") else line
    name, separator, value = content.partition(b":")
    value = value.strip(b" \t")
    if not separator or _TOKEN.fullmatch(name) is None or _FORBIDDEN_IN_VALUE.search(value):
        raise ValueError(f"en-tete de reponse invalide : {line[:200]!r}")
    return name.decode("latin-1"), value.decode("latin-1")


async def _read_headers(reader: asyncio.StreamReader, read_timeout: float) -> list[tuple[str, str]]:
    response_headers: list[tuple[str, str]] = []
    total = 0
    while True:
        line = await asyncio.wait_for(reader.readline(), timeout=read_timeout)
        if line in (b"\r\n", b"\n"):
            return response_headers
        if not line.endswith(b"\n"):
            raise ValueError("en-tetes de reponse incomplets (connexion fermee)")
        total += len(line)
        if len(response_headers) >= MAX_RESPONSE_HEADERS or total > MAX_RESPONSE_HEADER_BYTES:
            raise ValueError("en-tetes de reponse trop nombreux ou trop longs")
        response_headers.append(_parse_header_line(line))


async def _read_final_head(
    reader: asyncio.StreamReader, read_timeout: float, status_line: bytes,
) -> tuple[str, int, list[tuple[str, str]]]:
    """S12 : 1xx lues puis ignorees jusqu'a la reponse finale (101 : chemin WebSocket seulement -> erreur ici)."""
    for _ in range(MAX_INTERIM_RESPONSES + 1):
        version, status_code = _parse_status_line(status_line)
        response_headers = await _read_headers(reader, read_timeout)
        if status_code >= 200:
            return version, status_code, response_headers
        if status_code == 101:
            raise ValueError("101 sans demande de mise a niveau")
        status_line = await asyncio.wait_for(reader.readline(), timeout=read_timeout)
        if not status_line:
            raise ValueError("connexion fermee apres une reponse 1xx")
    raise ValueError("trop de reponses 1xx")


def _body_framing(method: str, status_code: int, response_headers: list[tuple[str, str]]) -> tuple[str, int | None]:
    """("none" | "length" | "chunked" | "close", longueur). D1, D2, S9, S10."""
    if method == "HEAD" or status_code in (204, 304):
        return "none", None
    transfer_encodings = [value for name, value in response_headers if name.lower() == "transfer-encoding"]
    if transfer_encodings:
        if any(name.lower() == "content-length" for name, _ in response_headers):
            raise ValueError("réponse avec Content-Length et Transfer-Encoding (RFC 9112 §6.3)")
        tokens = [token.strip().lower() for value in transfer_encodings for token in value.split(",") if token.strip()]
        if tokens != ["chunked"]:
            raise ValueError(f"Transfer-Encoding non pris en charge : {transfer_encodings!r}")
        return "chunked", None
    length = _response_content_length(response_headers)
    return ("length", length) if length is not None else ("close", None)


def _too_large(limit: int | None) -> HttpProxyResponseTooLargeError:
    return HttpProxyResponseTooLargeError(f"corps de réponse au-delà de {limit} octets (max_response_body_mb)")


async def _read_exactly(reader: asyncio.StreamReader, size: int, read_timeout: float) -> bytes:
    """C11 : le delai vaut entre deux blocs, jamais pour un gros corps entier."""
    parts: list[bytes] = []
    remaining = size
    while remaining:
        block = await asyncio.wait_for(reader.read(min(remaining, _READ_BLOCK)), timeout=read_timeout)
        if not block:
            raise asyncio.IncompleteReadError(b"".join(parts), size)
        parts.append(block)
        remaining -= len(block)
    return b"".join(parts)


async def _read_chunked(reader: asyncio.StreamReader, read_timeout: float, limit: int | None) -> bytes:
    """S11 : taille hexadecimale sans signe (16 chiffres au plus), extensions bornees, CRLF stricts ; trailers
    valides et bornes, puis retires (§2.1 point 3)."""
    body = bytearray()
    while True:
        line = await asyncio.wait_for(reader.readline(), timeout=read_timeout)
        if not line.endswith(b"\r\n") or len(line) > MAX_CHUNK_LINE_BYTES:
            raise ValueError(f"ligne de taille de bloc invalide : {line[:80]!r}")
        size_text = line[:-2].split(b";", 1)[0].rstrip(b" \t")
        if _HEX.fullmatch(size_text) is None:
            raise ValueError(f"taille de bloc invalide : {size_text[:40]!r}")
        size = int(size_text, 16)
        if size == 0:
            break
        if limit is not None and len(body) + size > limit:
            raise _too_large(limit)
        body += await _read_exactly(reader, size, read_timeout)
        if await _read_exactly(reader, 2, read_timeout) != b"\r\n":
            raise ValueError("bloc sans CRLF final")
    lines = total = 0
    while True:
        line = await asyncio.wait_for(reader.readline(), timeout=read_timeout)
        if line == b"\r\n":
            return bytes(body)
        if not line.endswith(b"\r\n"):
            raise ValueError("trailers incomplets")
        lines, total = lines + 1, total + len(line)
        if lines > MAX_TRAILER_LINES or total > MAX_TRAILER_BYTES:
            raise ValueError("trailers trop nombreux ou trop longs")
        _parse_header_line(line)


async def _read_until_close(reader: asyncio.StreamReader, read_timeout: float, limit: int | None) -> bytes:
    """S13 : dernier recours, borne par le delai entre blocs et par `limit` ; jamais recyclee."""
    parts: list[bytes] = []
    total = 0
    while True:
        block = await asyncio.wait_for(reader.read(_READ_BLOCK), timeout=read_timeout)
        if not block:
            return b"".join(parts)
        total += len(block)
        if limit is not None and total > limit:
            raise _too_large(limit)
        parts.append(block)


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


def tls_failure(error: BaseException) -> tuple[str, bool] | None:
    """Plan proxy natif v2, lot 8 : (raison, certificat refuse ?) pour un echec de poignee de main TLS vers un backend,
    None sinon (connexion refusee, delai, backend parti pendant la poignee de main : SSLEOFError). Lu par les
    attributs des exceptions du module ssl, jamais en l'important (contrat « ssl seulement dans
    infrastructure.tls.ssl_context_builder »). Raison : verify_message pour un certificat, reason (nom OpenSSL)
    sinon - le moteur natif ecrit le meme texte (server.cpp, tls_failure_reason)."""
    if type(error).__module__ != "ssl" or type(error).__name__ == "SSLEOFError":
        return None
    if hasattr(error, "verify_code"):  # ssl.SSLCertVerificationError
        return getattr(error, "verify_message", None) or getattr(error, "reason", None) or str(error), True
    return getattr(error, "reason", None) or str(error), False


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
        failure = tls_failure(e)  # lot 8 : certificat refuse ou protocole TLS - une ligne dans error.log
        if failure is not None:
            raise HttpProxyTlsError(f"connexion à l'upstream impossible ({host}:{port}) : {e}", failure[0],
                                    certificate=failure[1]) from e
        raise HttpProxyConnectionError(f"connexion à l'upstream impossible ({host}:{port}) : {e}") from e


async def _close_quietly(writer: asyncio.StreamWriter) -> None:
    writer.close()
    with contextlib.suppress(Exception):
        await writer.wait_closed()


_MAX_IDLE_CONNECTIONS_PER_UPSTREAM = 10
_PoolKey = tuple[str, int, int | None]
_Connection = tuple[asyncio.StreamReader, asyncio.StreamWriter]


class AsyncioHttpProxyClient:
    def __init__(self) -> None:
        self._idle: dict[_PoolKey, list[_Connection]] = {}

    def _pool_key(self, host: str, port: int, ssl_context: ssl.SSLContext | None) -> _PoolKey:
        # Lot 1 (D4) : le contexte lui-meme (verifie ou non), plus seulement « TLS ou non » - une connexion ouverte
        # sans verification ne sert jamais une zone qui exige la verification.
        return (host, port, None if ssl_context is None else id(ssl_context))

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
        max_body_bytes: int | None = None,
    ) -> HttpProxyResult:
        key = self._pool_key(host, port, ssl_context)

        reused = self._borrow_idle_connection(key) if method in _REPLAYABLE_METHODS else None  # D42
        if reused is not None:
            try:
                return await self._send_and_read(
                    key, reused, method, path, headers, body, read_timeout, host, port, max_body_bytes, reused=True,
                )
            except _NoResponseFromReusedConnection:
                pass  # connexion morte dans le pool, rien recu : une seule reprise, connexion neuve

        connection = await _open_connection(host, port, connect_timeout, ssl_context)
        return await self._send_and_read(
            key, connection, method, path, headers, body, read_timeout, host, port, max_body_bytes,
        )

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
        max_body_bytes: int | None = None,
        reused: bool = False,
    ) -> HttpProxyResult:
        reader, writer = connection
        response_started = False
        sent = False
        try:
            request_line = f"{method} {path} HTTP/1.1\r\n"
            header_lines = "".join(f"{name}: {value}\r\n" for name, value in headers)
            writer.write((request_line + header_lines + "\r\n").encode("latin-1") + body)
            await writer.drain()
            sent = True

            status_line = await asyncio.wait_for(reader.readline(), timeout=read_timeout)
            if not status_line:
                raise ConnectionResetError("upstream a fermé la connexion sans réponse")
            response_started = True
            version, status_code, response_headers = await _read_final_head(reader, read_timeout, status_line)
            framing, content_length = _body_framing(method, status_code, response_headers)  # D1, D2, D21, S10

            if framing == "none":
                response_body = b""
            elif framing == "length":
                assert content_length is not None
                if max_body_bytes is not None and content_length > max_body_bytes:
                    raise _too_large(max_body_bytes)
                response_body = await _read_exactly(reader, content_length, read_timeout)
            elif framing == "chunked":
                response_body = await _read_chunked(reader, read_timeout, max_body_bytes)  # D3
            else:
                response_body = await _read_until_close(reader, read_timeout, max_body_bytes)
            # D22 : longueur etablie sans ambiguite, HTTP/1.1, aucun jeton close, et rien apres la reponse
            reusable = (framing != "close" and version == "HTTP/1.1" and not _asks_close(response_headers)
                        and not _has_pending_bytes(reader))
        except HttpProxyResponseTooLargeError:
            await _close_quietly(writer)
            raise
        except asyncio.CancelledError:
            writer.close()  # lot 1 (P3) : client parti, requete annulee - jamais une connexion laissee ouverte
            raise
        except (asyncio.IncompleteReadError, asyncio.TimeoutError, ValueError, OSError) as e:
            await _close_quietly(writer)
            if reused and not response_started:
                raise _NoResponseFromReusedConnection(f"connexion du pool inutilisable ({host}:{port}) : {e}") from e
            error = HttpProxyTimeoutError if sent and isinstance(e, asyncio.TimeoutError) else HttpProxyConnectionError
            raise error(f"erreur de communication avec l'upstream ({host}:{port}) : {e!r}") from e

        if reusable:
            self._release_connection(key, (reader, writer))
        else:
            await _close_quietly(writer)

        # Trailers et decoupage chunked retires : le corps relaye est le corps decode (§2.1 point 3, P2).
        relayed = tuple((name, value) for name, value in response_headers if name.lower() != "transfer-encoding")
        return HttpProxyResult(status_code=status_code, headers=relayed, body=response_body)

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
