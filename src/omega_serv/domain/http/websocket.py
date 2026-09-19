"""Detection d'une requete de mise a niveau WebSocket (RFC 6455 §4.1) -
utilisee EXCLUSIVEMENT pour le court-circuit du reverse proxy sortant
vers un upstream WebSocket (OMEGA-SERV_PLAN-DETAILLE_REVERSE_PROXY.md
§4). OMEGA-SERV lui-meme n'implemente jamais le protocole WebSocket -
il ne fait que relayer un tube TCP bidirectionnel entre le client et
l'upstream, jamais interpreter les frames."""
from __future__ import annotations

from omega_serv.domain.http.request import HttpRequest


def is_websocket_upgrade_request(request: HttpRequest) -> bool:
    """RFC 6455 exige GET, `Connection` contenant le jeton `upgrade`
    (insensible a la casse, eventuellement parmi d'autres jetons
    separes par des virgules) et `Upgrade: websocket` exactement."""
    if request.method != "GET":
        return False
    connection_tokens = {token.strip().lower() for token in (request.header("connection") or "").split(",")}
    if "upgrade" not in connection_tokens:
        return False
    return (request.header("upgrade") or "").strip().lower() == "websocket"
