"""Trafic des sites (plan tableau de bord web §9.5, lot 9b ; decision de l'auteur du 2026-11-17 : compteurs dans les
deux moteurs) : octets recus des visiteurs et envoyes aux visiteurs, en-tetes et TLS compris.

Mesure : les compteurs du noyau de chaque connexion cliente, lus au debut, toutes les 2 s tant qu'elle est ouverte, et
juste avant sa fermeture. Recu : tcpi_bytes_received (TCP_INFO). Envoye : tout ce qui a ete confie au noyau, soit
tcpi_bytes_acked plus la file d'envoi pas encore acquittee (SIOCOUTQ) - sans elle, la fin de chaque reponse, pas
encore acquittee a la fermeture, serait perdue ; a la fermeture s'ajoute ce qui reste dans le tampon du transport. Rien n'est ajoute aux chemins d'ecriture (sendfile,
TLS, WebSocket, relais : tout passe par la meme socket). Une connexion confiee par l'autre moteur part de ce que la
socket a deja vu (jamais compte deux fois).

Publication : un fichier par processus, var/run/traffic/<pid>.json ({"recu": n, "envoye": n}, cumuls depuis le
lancement du processus), ecrit toutes les 5 s et retire a l'arret ; le processus d'administration les additionne
(TrafficTotals). Hors Linux (pas de TCP_INFO) : rien n'est publie, les graphes restent masques."""
from __future__ import annotations

import fcntl
import json
import os
import socket
import struct
import time
from collections.abc import Callable, Hashable
from pathlib import Path

TYPE_CHECKING = False  # superviseur reduit du natif (lot 5, 2026-11-19) : sans typing (1,2 Mo)
if TYPE_CHECKING:
    from typing import Any

TRAFFIC_RELATIVE_DIR = Path("var") / "run" / "traffic"
SAMPLE_SECONDS = 2.0
PUBLISH_SECONDS = 5.0
_TCP_INFO = getattr(socket, "TCP_INFO", None)
_BYTES_OFFSET = 120
"""struct tcp_info (linux/tcp.h) : tcpi_bytes_acked (u64) a l'octet 120, tcpi_bytes_received (u64) a 128."""
_INFO_SIZE = 136
_SIOCOUTQ = 0x5411
"""ioctl Linux (= TIOCOUTQ) : octets de la file d'envoi d'une socket TCP, envoyes ou non, pas encore acquittes."""


def tcp_bytes(sock: Any) -> tuple[int, int] | None:
    """(recus, envoyes) depuis l'ouverture de la socket ; None si le noyau ne les donne pas (hors Linux, socket non
    TCP, socket deja fermee)."""
    if _TCP_INFO is None or sock is None:
        return None
    try:
        info = sock.getsockopt(socket.IPPROTO_TCP, _TCP_INFO, _INFO_SIZE)
    except (OSError, ValueError, AttributeError):
        return None
    if len(info) < _INFO_SIZE:
        return None
    acked, received = struct.unpack_from("=QQ", info, _BYTES_OFFSET)
    try:
        queued = struct.unpack("=i", fcntl.ioctl(sock.fileno(), _SIOCOUTQ, b"\0\0\0\0"))[0]
    except (OSError, ValueError, AttributeError):
        queued = 0
    return received, acked + max(0, queued)


class TrafficMeter:
    """Cumuls d'un processus serveur. Une entree par connexion ouverte : sa socket et ce qui en est deja compte."""

    def __init__(self, reader: Callable[[Any], tuple[int, int] | None] = tcp_bytes) -> None:
        self._read = reader
        self._open: dict[Hashable, tuple[Any, int, int]] = {}
        self.received = 0
        self.sent = 0
        self.measured = False
        """Au moins une socket a donne ses compteurs : sans cela (hors Linux), rien n'est publie."""

    def open(self, key: Hashable, sock: Any, *, from_start: bool = True) -> None:
        """`from_start` : la connexion est nee ici (tout compte, poignee de main TLS comprise) ; sinon, confiee par
        l'autre moteur : seul ce qui suit compte."""
        if from_start:
            self._open[key] = (sock, 0, 0)
            self._sample(key)
            return
        now = self._read(sock)
        if now is not None:
            self._open[key] = (sock, now[0], now[1])

    def _sample(self, key: Hashable) -> bool:
        sock, received, sent = self._open[key]
        now = self._read(sock)
        if now is None:
            return False
        self.measured = True
        self.received += max(0, now[0] - received)
        self.sent += max(0, now[1] - sent)
        self._open[key] = (sock, max(received, now[0]), max(sent, now[1]))
        return True

    def close(self, key: Hashable, unsent: int = 0) -> None:
        """A appeler AVANT la fermeture de la socket. `unsent` : octets encore dans le tampon du transport, qui
        partiront apres."""
        if key in self._open:
            if self._sample(key):  # hors Linux : rien n'est compte, pas meme le tampon
                self.sent += max(0, unsent)
            del self._open[key]

    def sample_all(self) -> None:
        for key in list(self._open):
            self._sample(key)

    def add(self, received: int, sent: int) -> None:
        """Octets comptes ailleurs (non utilise par le moteur Python lui-meme ; tests)."""
        self.measured = True
        self.received += max(0, received)
        self.sent += max(0, sent)


class TrafficFile:
    """var/run/traffic/<pid>.json : ecrit par le processus serveur, lu par le processus d'administration."""

    def __init__(self, project_root: Path, pid: int | None = None) -> None:
        self.directory = project_root / TRAFFIC_RELATIVE_DIR
        self.pid = os.getpid() if pid is None else pid
        self._written_at = 0.0

    @property
    def path(self) -> Path:
        return self.directory / f"{self.pid}.json"

    def publish(self, received: int, sent: int, *, now: float | None = None, force: bool = False) -> None:
        """Au plus toutes les 5 s (sauf `force`) ; jamais d'exception (dossier non inscriptible : rien n'est publie)."""
        moment = time.monotonic() if now is None else now
        if not force and moment - self._written_at < PUBLISH_SECONDS:
            return
        self._written_at = moment
        try:
            self.directory.mkdir(parents=True, exist_ok=True)
            temporary = self.directory / f".{self.pid}.json.tmp"
            temporary.write_text(json.dumps({"recu": int(received), "envoye": int(sent)}), encoding="ascii")
            os.chmod(temporary, 0o640)
            os.replace(temporary, self.path)
        except OSError:
            pass

    def remove(self) -> None:
        try:
            self.path.unlink()
        except OSError:
            pass
