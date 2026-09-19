"""Contrat de communication avec un backend HTTP amont (reverse proxy
sortant, OMEGA-SERV_PLAN-DETAILLE_REVERSE_PROXY.md) - meme patron que
FastCgiClientPort (ports/fastcgi_client_port.py).

`open_websocket_tunnel` (phase 4, §4) retourne les flux bruts
`asyncio.StreamReader`/`StreamWriter` deja connectes a l'upstream SI la
mise a niveau a reussi (status 101) - seule maniere honnete de modeliser
"donne-moi un tube bidirectionnel deja etabli" sans reinventer une
abstraction de transport. `asyncio` n'est confine par aucun contrat
import-linter de ce projet (contrairement a `ssl`/`subprocess`),
importable directement ici."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    import ssl


@dataclass(frozen=True)
class HttpProxyResult:
    status_code: int
    headers: tuple[tuple[str, str], ...]
    body: bytes


class HttpProxyConnectionError(Exception):
    """Connexion a l'upstream impossible, ou coupee/expiree en cours
    d'echange - meme role que FastCgiConnectionError (domain/http/
    fastcgi_protocol.py) pour le backend FastCGI - levee par
    infrastructure/proxy/, jamais par ce module."""


@dataclass(frozen=True)
class WebSocketUpstreamHandshake:
    status_code: int
    headers: tuple[tuple[str, str], ...]
    reader: asyncio.StreamReader | None
    writer: asyncio.StreamWriter | None
    """`reader`/`writer` valent None sauf si `status_code == 101` - un
    upstream qui refuse la mise a niveau (400, 404...) n'a aucun tube a
    relayer, la connexion a deja ete fermee cote infrastructure avant
    de retourner."""


class HttpProxyClientPort(Protocol):
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
        ...

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
        ...
