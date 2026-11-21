"""Detection d'une requete de mise a niveau WebSocket (RFC 6455 §4.1) -
utilisee EXCLUSIVEMENT pour le court-circuit du reverse proxy sortant
vers un upstream WebSocket (OMEGA-SERV_PLAN-DETAILLE_REVERSE_PROXY.md
§4). OMEGA-SERV lui-meme n'implemente jamais le protocole WebSocket -
il ne fait que relayer un tube TCP bidirectionnel entre le client et
l'upstream, jamais interpreter les frames. Plan proxy natif v2, lot 10 : seul
l'en-tete des trames est lu (`WebSocketFrameTracker`), pour inserer une trame
de fermeture 1001 entre deux trames - jamais leur contenu."""
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


GOING_AWAY = 1001
"""RFC 6455 §7.4.1 : code de fermeture « l'extremite s'en va » - plan proxy natif v2, lot 10 (C14, C17) : envoye a la
fin du delai d'inactivite d'un tunnel et a la fin du delai de grace de l'arret (decision de l'auteur du 2026-11-14)."""


class WebSocketFrameTracker:
    """Plan proxy natif v2, lot 10 : repere la fin des trames d'un sens du tunnel, pour savoir si une trame de
    fermeture peut s'inserer entre deux trames. Ne lit que l'en-tete de chaque trame (2 a 14 octets : longueur, masque,
    code d'operation), jamais le contenu - aucune trame n'est decodee ni modifiee. Meme automate que le natif
    (`native/omega-http-core/src/websocket.cpp`)."""

    __slots__ = ("_header", "_remaining", "close_seen")

    def __init__(self) -> None:
        self._header = bytearray()
        self._remaining = 0
        self.close_seen = False
        """Une trame de fermeture est deja passee dans ce sens : plus aucune trame a envoyer (RFC 6455 §5.5.1)."""

    def feed(self, data: bytes) -> None:
        position, size = 0, len(data)
        while position < size:
            if self._remaining:
                take = min(self._remaining, size - position)
                self._remaining -= take
                position += take
                continue
            self._header.append(data[position])
            position += 1
            if len(self._header) == self._header_size():
                self._end_of_header()

    def _header_size(self) -> int:
        header = self._header
        if len(header) < 2:
            return 2
        length = header[1] & 0x7F
        extended = 2 if length == 126 else 8 if length == 127 else 0
        return 2 + extended + (4 if header[1] & 0x80 else 0)

    def _end_of_header(self) -> None:
        header = self._header
        length = header[1] & 0x7F
        if length == 126:
            length = int.from_bytes(header[2:4], "big")
        elif length == 127:
            length = int.from_bytes(header[2:10], "big")
        if header[0] & 0x0F == 0x8:
            self.close_seen = True
        self._remaining = length
        self._header.clear()

    @property
    def at_boundary(self) -> bool:
        """Tout ce qui est passe forme des trames entieres."""
        return not self._header and self._remaining == 0

    @property
    def can_send_close(self) -> bool:
        return self.at_boundary and not self.close_seen


def close_frame_to_client(code: int = GOING_AWAY) -> bytes:
    """Trame de fermeture d'un serveur vers son client : jamais masquee (RFC 6455 §5.1)."""
    return bytes((0x88, 0x02)) + code.to_bytes(2, "big")


def close_frame_to_server(mask: bytes, code: int = GOING_AWAY) -> bytes:
    """Trame de fermeture d'un client vers le serveur (le backend) : toujours masquee (RFC 6455 §5.3), cle de 4 octets
    imprevisible fournie par l'appelant."""
    payload = code.to_bytes(2, "big")
    return bytes((0x88, 0x82)) + mask + bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
