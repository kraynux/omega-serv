"""Cas d'usage : relayer une requete vers un backend HTTP amont
(reverse proxy sortant, OMEGA-SERV_PLAN-DETAILLE_REVERSE_PROXY.md §2).

Deux points non negociables (meme document, §5) :
- En-tetes "hop-by-hop" (RFC 7230 §6.1) retires dans les DEUX sens -
  un oubli casserait le keep-alive ou fuiterait des details de
  connexion internes.
- X-Forwarded-* toujours ECRASES avec les valeurs entrantes du client,
  jamais fusionnes - sinon un client peut usurper son IP auprès du
  backend (injection d'en-tete classique).

Phase 3 (§5.3/§12) : deux contextes TLS CLIENT construits une seule
fois (jamais par requete) et passes ici en parametres - le contexte
"verified" ou "unverified" est choisi selon `zone.verify_upstream_tls`,
applique seulement quand l'upstream choisi a `use_tls=True`.

`HOP_BY_HOP_HEADERS`/`build_outgoing_headers` sont reutilises tels
quels par `serve_websocket_proxy.py` (phase 4, §4) - SEULE exception :
une requete de mise a niveau WebSocket doit transmettre `Connection`/
`Upgrade` a l'upstream (le seul cas ou ces deux en-tetes ne sont PAS
hop-by-hop, §5.1), via `preserve_upgrade=True`."""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import ssl

from omega_serv.domain.http.request import HttpRequest
from omega_serv.domain.http.response import HttpResponse
from omega_serv.domain.http.status_codes import HttpStatus
from omega_serv.domain.routing.proxy_zone import ProxyRoundRobinState, ProxyZone, UpstreamTarget
from omega_serv.ports.http_proxy_client_port import HttpProxyClientPort, HttpProxyConnectionError

HOP_BY_HOP_HEADERS = frozenset({
    "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
    "te", "trailers", "transfer-encoding", "upgrade",
})


def build_outgoing_headers(
    request: HttpRequest, zone: ProxyZone, upstream: UpstreamTarget, *, preserve_upgrade: bool = False,
) -> tuple[tuple[str, str], ...]:
    hop_by_hop = HOP_BY_HOP_HEADERS - {"connection", "upgrade"} if preserve_upgrade else HOP_BY_HOP_HEADERS
    original_host = request.header("host")
    headers = [
        (name, value) for name, value in request.headers
        if name not in hop_by_hop and name not in ("host", "x-forwarded-for", "x-forwarded-proto", "x-forwarded-host")
    ]
    headers.append(("Host", original_host if zone.preserve_host_header and original_host else f"{upstream.host}:{upstream.port}"))
    headers.append(("X-Forwarded-For", request.remote_ip))
    headers.append(("X-Forwarded-Proto", "https" if request.is_tls else "http"))
    if original_host:
        headers.append(("X-Forwarded-Host", original_host))
    return tuple(headers)


async def serve_proxy(
    request: HttpRequest,
    zone: ProxyZone,
    proxy_client: HttpProxyClientPort,
    round_robin: ProxyRoundRobinState,
    client_ssl_context_verified: ssl.SSLContext | None = None,
    client_ssl_context_unverified: ssl.SSLContext | None = None,
) -> HttpResponse:
    index = round_robin.pick(zone.url_prefix, len(zone.upstreams))
    upstream = zone.upstreams[index]

    target = request.path + (f"?{request.query}" if request.query else "")
    outgoing_headers = build_outgoing_headers(request, zone, upstream)

    ssl_context = None
    if upstream.use_tls:
        ssl_context = client_ssl_context_verified if zone.verify_upstream_tls else client_ssl_context_unverified

    try:
        result = await proxy_client.forward_request(
            upstream.host, upstream.port, request.method, target,
            outgoing_headers, request.body or b"", zone.connect_timeout_seconds, zone.read_timeout_seconds,
            ssl_context,
        )
    except HttpProxyConnectionError:
        return HttpResponse.empty(HttpStatus.BAD_GATEWAY)

    response = HttpResponse.empty(result.status_code)
    for name, value in result.headers:
        if name.lower() not in HOP_BY_HOP_HEADERS:
            response.set_header(name, value)
    response.body = result.body
    return response
