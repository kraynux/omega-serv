"""Trames du contrat IPC v1 avec le moteur natif (OMEGA-SERV_CONTRAT_IPC_MOTEUR.md §2-3, plan moteur C++ lot 3).

Meme encodage que native/omega-http-core/src/ipc.cpp, verifie sur les memes vecteurs binaires
(tools/differential/make_vectors.py -> tests/vectors/ipc.tsv, relus par le test C++). En-tete fixe de 24 octets
petit-boutiste (magic, version de contrat, type, request_id, generation, longueur) puis champs TLV (tag u16,
longueur u32, valeur brute). Un tag inconnu est conserve et ignore plus haut (compatibilite ascendante).

L'instantane de configuration (~330 Kio) depasse la taille d'un message SOCK_SEQPACKET sans privileges
(net.core.wmem_default = 208 Kio) : il voyage dans un memfd scelle transmis en SCM_RIGHTS - aucun fichier sur
disque - avec sa taille et son SHA-256 dans la trame CONFIG."""
from __future__ import annotations

import fcntl
import hashlib
import os
import select
import socket
import struct
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from omega_serv.domain.http.response import HttpResponse

MAGIC = 0x4F4D4743  # « OMGC »
CONTRACT_VERSION = 1
HEADER = struct.Struct("<IHHQII")
HEADER_SIZE = HEADER.size  # 24
_TLV = struct.Struct("<HI")
MAX_PAYLOAD = 1 << 20

HELLO, HELLO_ACK, CONFIG, CONFIG_ACK, HEALTH, SHUTDOWN, ERROR = 1, 2, 3, 4, 5, 6, 20
DATA_ATTACH, INSPECT, VERDICT, HANDOFF = 7, 10, 11, 12  # lots 4 et 6
WATCH = 14  # plan WAF natif, lot 3 : Python -> natif, sources a toujours inspecter (ignore par un natif plus ancien)

# Tags (contrat §3.5)
HELLO_CONTRACT, HELLO_BINARY, HELLO_CAPABILITY, HELLO_PID = 1, 2, 3, 4
ACK_ACCEPTED, ACK_REASON = 1, 2
CONFIG_SIZE, CONFIG_SHA256 = 1, 2
CONFIG_OK, CONFIG_ERROR = 1, 2
HEALTH_CONNECTIONS, HEALTH_REQUESTS, HEALTH_REJECTED, HEALTH_GENERATION = 1, 2, 3, 4
SHUTDOWN_GRACE_MS = 1
ERROR_CODE, ERROR_MESSAGE = 1, 2
ATTACH_THREAD = 1
INSPECT_PEER, INSPECT_METHOD, INSPECT_TARGET, INSPECT_VERSION, INSPECT_HEADER, INSPECT_BODY = 1, 2, 3, 4, 5, 6
INSPECT_DELEGATE = 7  # lot 5 : route deleguee (listing, /load, /admin) -> route_request
INSPECT_CLIENT_IP = 8  # lot 8 : IP cliente deja resolue par le natif (trusted_proxy)
INSPECT_BLOCKLIST_CLEAR = 9  # lot 8 : u8 1 = etat actuel de la blocklist lu par le natif, adresse absente
INSPECT_AUDIT = 10  # plan WAF natif, lot 4 : u8 1 = requete jugee propre par le natif, envoyee pour controle (1/N)
INSPECT_RATE_LIMIT = 11  # lot 6 : u32, limite de debit comptee par le natif - 0 autorisee, N = Retry-After (s)
HANDOFF_BYTES, HANDOFF_SERVED, HANDOFF_BYTES_FD = 1, 2, 3  # lot 6 : fd 1 socket client, fd 2 memfd optionnel
(VERDICT_DECISION, VERDICT_STATUS, VERDICT_HEADER, VERDICT_BODY, VERDICT_KEEP_ALIVE, VERDICT_FILE, VERDICT_FILE_OFFSET,
 VERDICT_FILE_LENGTH) = 1, 2, 3, 4, 5, 6, 7, 8
CONTINUE, RESPOND, ABORT = 1, 2, 3
WATCH_ENTRY = 1  # texte « adresse\0echeance » (secondes Unix, entier), repete


class FrameError(ValueError):
    """Trame refusee (magic, version, longueur, TLV debordant)."""


@dataclass
class Frame:
    type: int
    request_id: int = 0
    generation: int = 0
    fields: list[tuple[int, bytes]] = field(default_factory=list)

    def add(self, tag: int, value: bytes | str) -> Frame:
        self.fields.append((tag, value.encode("utf-8") if isinstance(value, str) else value))
        return self

    def add_uint(self, tag: int, value: int, size: int) -> Frame:
        return self.add(tag, value.to_bytes(size, "little"))

    def first(self, tag: int) -> bytes | None:
        return next((value for t, value in self.fields if t == tag), None)

    def all(self, tag: int) -> list[bytes]:
        return [value for t, value in self.fields if t == tag]

    def uint(self, tag: int) -> int | None:
        value = self.first(tag)
        if value is None or len(value) not in (1, 2, 4, 8):
            return None
        return int.from_bytes(value, "little")

    def text(self, tag: int) -> str | None:
        value = self.first(tag)
        return None if value is None else value.decode("utf-8", errors="replace")


def encode(frame: Frame) -> bytes:
    payload = b"".join(struct.pack("<HI", tag, len(value)) + value for tag, value in frame.fields)
    return HEADER.pack(MAGIC, CONTRACT_VERSION, frame.type, frame.request_id, frame.generation, len(payload)) + payload


def decode(data: bytes) -> Frame:
    if len(data) < HEADER_SIZE:
        raise FrameError("trame plus courte que l'en-tete")
    magic, version, kind, request_id, generation, length = HEADER.unpack_from(data)
    if magic != MAGIC:
        raise FrameError("magic invalide")
    if version != CONTRACT_VERSION:
        raise FrameError("version de contrat differente")
    if length != len(data) - HEADER_SIZE:
        raise FrameError("longueur annoncee differente de la trame")
    if length > MAX_PAYLOAD:
        raise FrameError("charge utile trop grande")
    frame = Frame(kind, request_id, generation)
    fields = frame.fields
    unpack_tlv = _TLV.unpack_from
    offset, end = HEADER_SIZE, len(data)
    while offset < end:
        if end - offset < 6:
            raise FrameError("champ TLV tronque")
        tag, size = unpack_tlv(data, offset)
        offset += 6
        if size > end - offset:
            raise FrameError("champ TLV deborde de la trame")
        fields.append((tag, data[offset:offset + size]))
        offset += size
    return frame


def send_frame(sock: socket.socket, frame: Frame, pass_fd: int | None = None) -> None:
    data = encode(frame)
    if pass_fd is None:
        sock.sendall(data)
    else:
        socket.send_fds(sock, [data], [pass_fd])


def recv_frame(sock: socket.socket, timeout: float | None) -> tuple[Frame, int | None] | None:
    """(trame, fd recu ou None) ; None = fin du canal. TimeoutError si rien sous `timeout` secondes."""
    if timeout is not None:
        ready, _, _ = select.select([sock], [], [], timeout)
        if not ready:
            raise TimeoutError("aucune trame recue dans le delai")
    data, fds, flags, _ = socket.recv_fds(sock, HEADER_SIZE + MAX_PAYLOAD, 4)
    if not data and not fds:
        return None
    if flags & (socket.MSG_TRUNC | socket.MSG_CTRUNC) or len(fds) > 1:
        for fd in fds:
            os.close(fd)
        raise FrameError("trame tronquee ou descripteurs inattendus")
    try:
        frame = decode(data)
    except FrameError:
        for fd in fds:
            os.close(fd)
        raise
    return frame, (fds[0] if fds else None)


def sealed_memfd(content: bytes, name: str = "omega-serv-snapshot") -> int:
    """memfd en lecture seule pour le natif : scelle (ni ecriture, ni retaille) apres remplissage."""
    fd = os.memfd_create(name, os.MFD_CLOEXEC | os.MFD_ALLOW_SEALING)
    try:
        view = memoryview(content)
        while view:
            written = os.write(fd, view)
            view = view[written:]
        fcntl.fcntl(fd, fcntl.F_ADD_SEALS, fcntl.F_SEAL_SHRINK | fcntl.F_SEAL_GROW | fcntl.F_SEAL_WRITE | fcntl.F_SEAL_SEAL)
    except BaseException:
        os.close(fd)
        raise
    return fd


def config_frame(generation: int, snapshot_json: bytes) -> Frame:
    return (Frame(CONFIG, generation=generation)
            .add_uint(CONFIG_SIZE, len(snapshot_json), 8)
            .add(CONFIG_SHA256, hashlib.sha256(snapshot_json).digest()))


def hello_ack(accepted: bool, reason: str = "") -> Frame:
    frame = Frame(HELLO_ACK).add_uint(ACK_ACCEPTED, 1 if accepted else 0, 1)
    return frame.add(ACK_REASON, reason) if reason else frame


def verdict_frame(request_id: int, response: HttpResponse | None, keep_alive_allowed: bool) -> Frame:
    """VERDICT d'une `security_stage` : continuer (None) ou repondre `response` (HttpResponse AVANT en-tetes de
    securite, que le natif applique pour le chemin comme le moteur Python). En-tetes en texte UTF-8 (le natif les
    ecrit en latin-1, comme `_write_response`), corps tel quel ou fichier (chemin, debut, longueur)."""
    frame = Frame(VERDICT, request_id=request_id)
    if response is None:
        return frame.add_uint(VERDICT_DECISION, CONTINUE, 1)
    frame.add_uint(VERDICT_DECISION, RESPOND, 1).add_uint(VERDICT_STATUS, int(response.status), 2)
    for name, value in response.headers.items():
        frame.add(VERDICT_HEADER, f"{name}\0{value}")
    if response.body:
        frame.add(VERDICT_BODY, response.body)
    if response.body_file is not None:
        frame.add(VERDICT_FILE, str(response.body_file))
        frame.add_uint(VERDICT_FILE_OFFSET, response.body_file_offset, 8)
        frame.add_uint(VERDICT_FILE_LENGTH, response.body_file_length, 8)
    return frame.add_uint(VERDICT_KEEP_ALIVE, 1 if keep_alive_allowed else 0, 1)


_CONTINUE_PAYLOAD = struct.pack("<HI", VERDICT_DECISION, 1) + bytes((CONTINUE,))


def continue_verdict_bytes(request_id: int) -> bytes:
    """`encode(verdict_frame(request_id, None, ...))` sans construire la trame : le verdict de presque toutes les
    requetes (memes octets, verifie par test)."""
    return HEADER.pack(MAGIC, CONTRACT_VERSION, VERDICT, request_id, 0, len(_CONTINUE_PAYLOAD)) + _CONTINUE_PAYLOAD


def watch_frame(entries: list[tuple[str, float]]) -> Frame:
    """Sources que le natif envoie toujours au processus de securite jusqu'a leur echeance (ajout ou prolongation
    seulement : jamais de retrait, l'echeance fait foi)."""
    frame = Frame(WATCH)
    for ip, until in entries:
        frame.add(WATCH_ENTRY, f"{ip}\0{int(until) + 1}")  # arrondi vers le haut : jamais une seconde de moins
    return frame


def abort_frame(request_id: int) -> Frame:
    """Exception dans l'etape de securite : le natif ferme la connexion sans reponse, comme asyncio."""
    return Frame(VERDICT, request_id=request_id).add_uint(VERDICT_DECISION, ABORT, 1)


def data_attach_frame(thread_index: int) -> Frame:
    return Frame(DATA_ATTACH).add_uint(ATTACH_THREAD, thread_index, 4)


def shutdown_frame(grace_seconds: float) -> Frame:
    return Frame(SHUTDOWN).add_uint(SHUTDOWN_GRACE_MS, max(0, int(grace_seconds * 1000)), 4)
