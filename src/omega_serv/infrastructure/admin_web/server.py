"""Ecoute reseau du processus d'administration web (tableau de bord web, lot 2,
OMEGA-SERV_PLAN-DETAILLE_TABLEAU_DE_BORD_WEB.md §2).

Un `asyncio.start_server` sur `options.admin_web.bind:port`, jamais sur le port public. Chaque connexion : une seule
requete (Connection: close), tete lue par le lecteur HTTP durci du serveur (lignes et en-tetes bornes), delais
bornes, connexions simultanees plafonnees. La decision (403, 405, page) est prise par
application/admin_web/responses.py ; ce module ne fait que le reseau et le TLS."""
from __future__ import annotations

import asyncio
import contextlib
import logging
import ssl
from collections.abc import Awaitable, Callable
from typing import Any

from omega_serv.application.admin_web.responses import AdminResponse
from omega_serv.application.admin_web.web_app import MAX_FORM_BYTES, AdminRequest
from omega_serv.infrastructure.server.http_parser import (
    ConnectionClosedCleanly,
    HttpParseError,
    read_request_head,
)

MAX_CONNECTIONS = 64
"""Connexions simultanees au plus : au-dela, la connexion est fermee aussitot (un tableau de bord n'en ouvre que
quelques-unes)."""
HEAD_TIMEOUT_SECONDS = 10.0
TLS_HANDSHAKE_TIMEOUT_SECONDS = 10.0
MAX_REQUEST_LINE = 8_192
MAX_HEADERS = 16_384

Responder = Callable[[AdminRequest], Awaitable[AdminResponse]]
MAX_BODY_BYTES = MAX_FORM_BYTES


_LOG = logging.getLogger("omega_serv.admin_web")
_REASON_PHRASES = {500: "Internal Server Error"}
"""Phrases de statut HTTP (protocole, jamais traduites)."""


def _bare(status: int, reason: str) -> AdminResponse:
    return AdminResponse(status, reason, (("Content-Type", "text/plain; charset=utf-8"),), b"")


def encode_response(response: AdminResponse, *, head_only: bool) -> bytes:
    lines = [f"HTTP/1.1 {response.status} {response.reason}"]
    lines += [f"{name}: {value}" for name, value in response.headers]
    lines += [f"Content-Length: {len(response.body)}", "Connection: close", "", ""]
    head = "\r\n".join(lines).encode("latin-1")
    return head if head_only else head + response.body


class AdminWebServer:
    def __init__(self, bind: str, port: int, ssl_context: ssl.SSLContext | None, responder: Responder) -> None:
        self._bind = bind
        self._port = port
        self._ssl_context = ssl_context
        self._responder = responder
        self._server: asyncio.Server | None = None
        self._open = 0

    async def start(self) -> None:
        """Leve OSError si le port est pris ou interdit (l'appelant le dit dans error.log)."""
        tls: dict[str, Any] = {"ssl": self._ssl_context, "ssl_handshake_timeout": TLS_HANDSHAKE_TIMEOUT_SECONDS} if self._ssl_context else {}
        self._server = await asyncio.start_server(self._handle, host=self._bind, port=self._port, **tls)

    @property
    def listening(self) -> bool:
        return self._server is not None and self._server.is_serving()

    async def close(self) -> None:
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
            self._server = None

    async def _handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        if self._open >= MAX_CONNECTIONS:
            writer.close()
            return
        self._open += 1
        try:
            peer = writer.get_extra_info("peername")
            peer_ip = str(peer[0]) if peer else ""
            try:
                head = await asyncio.wait_for(read_request_head(reader, MAX_REQUEST_LINE, MAX_HEADERS),
                                              HEAD_TIMEOUT_SECONDS)
            except (ConnectionClosedCleanly, HttpParseError, TimeoutError, ConnectionError, ssl.SSLError):
                return
            if head.header("transfer-encoding") is not None:
                writer.write(encode_response(_bare(411, "Length Required"), head_only=False))
                return
            length_text = head.header("content-length") or "0"
            length = int(length_text) if length_text.isascii() and length_text.isdigit() else -1
            if length < 0 or length > MAX_BODY_BYTES:
                writer.write(encode_response(_bare(413, "Content Too Large"), head_only=False))
                return
            try:
                body = await asyncio.wait_for(reader.readexactly(length), HEAD_TIMEOUT_SECONDS) if length else b""
            except (asyncio.IncompleteReadError, TimeoutError, ConnectionError, ssl.SSLError):
                return
            try:
                response = await self._responder(AdminRequest(peer_ip, head.method, head.target, head.headers, body))
            except Exception:  # noqa: BLE001 - jamais de connexion fermee sans reponse (ERR_EMPTY_RESPONSE, 2026-11-17)
                _LOG.exception("administration web : erreur pendant %s %s", head.method, head.target.split("?")[0])
                response = _bare(500, _REASON_PHRASES[500])
            writer.write(encode_response(response, head_only=head.method == "HEAD"))
            with contextlib.suppress(ConnectionError, ssl.SSLError, TimeoutError):
                await asyncio.wait_for(writer.drain(), HEAD_TIMEOUT_SECONDS)
        finally:
            self._open -= 1
            writer.close()
            with contextlib.suppress(Exception):
                await asyncio.wait_for(writer.wait_closed(), 2.0)
