"""Processus Python de securite du moteur natif (plan moteur C++ lot 4, §3.2-3.3 ; contrat IPC §3.2-3.3).

Le natif lit, analyse et sert ; pour chaque requete, apres la lecture du corps, il envoie un INSPECT sur le canal
de son fil. Ce processus reconstruit la requete EXACTEMENT comme le moteur Python (`AsyncioServer.build_request`)
et lui applique la MEME etape de securite (`AsyncioServer.security_stage` : leurre, WAF, alerte, Active Defense,
mode guerre, Auth) - pas une seconde implementation, le meme objet `AsyncioServer` construit par `build_server`,
qui n'ecoute simplement aucun port. Les journaux de securite (waf-alerts, security-events, AD) sont donc ecrits
ici, comme aujourd'hui : RIPOSTE et omega-jail ne voient aucune difference. Le VERDICT dit au natif de continuer
(routage natif) ou quelle reponse envoyer (avant en-tetes de securite, que le natif applique comme Python).

Une requete = une tache asyncio : un ralentissement du mode guerre n'immobilise jamais les autres. Le processus
s'arrete de lui-meme quand tous ses canaux sont fermes (natif arrete) ; SIGHUP : rechargement comme `serve`."""
from __future__ import annotations

import asyncio
import os
import signal
import socket
import sys
from collections import deque
from collections.abc import Callable
from typing import TYPE_CHECKING

from omega_serv.infrastructure.server import native_ipc as ipc
from omega_serv.infrastructure.server.http_parser import ParsedRequestHead

if TYPE_CHECKING:
    from omega_serv.infrastructure.server.asyncio_server import AsyncioHttpServer


def _inspected_head(frame: ipc.Frame) -> tuple[str, ParsedRequestHead, bytes | None, str | None, dict[int, bytes]]:
    """(IP du pair, tete reconstruite, corps capture ou None, IP cliente resolue par le natif ou None, premier
    champ par tag - pour les indicateurs, sans reparcourir la trame) - octets bruts = texte latin-1, comme le
    parseur."""
    # Un seul parcours des champs (lot 8 : `first` par champ = un parcours de la trame chacun) ; premier = retenu.
    single: dict[int, bytes] = {}
    headers = []
    for tag, raw in frame.fields:
        if tag == ipc.INSPECT_HEADER:
            name, _, value = raw.partition(b"\0")
            headers.append((name.decode("latin-1"), value.decode("latin-1")))
        else:
            single.setdefault(tag, raw)

    def text(tag: int) -> str:
        return single.get(tag, b"").decode("latin-1")

    head = ParsedRequestHead(method=text(ipc.INSPECT_METHOD), target=text(ipc.INSPECT_TARGET),
                             http_version=text(ipc.INSPECT_VERSION), headers=tuple(headers))
    client_ip = single.get(ipc.INSPECT_CLIENT_IP)
    return (single.get(ipc.INSPECT_PEER, b"").decode("utf-8"), head, single.get(ipc.INSPECT_BODY),
            client_ip.decode("utf-8") if client_ip is not None else None, single)


def _counted_rate_limit(single: dict[int, bytes]) -> int | None:
    """Lot 6 : limite de debit deja comptee par le natif (0 = autorisee, N = Retry-After) ; None = a compter ici."""
    value = single.get(ipc.INSPECT_RATE_LIMIT)
    if value is None or len(value) not in (1, 2, 4, 8):
        return None
    return int.from_bytes(value, "little")


def _flag(single: dict[int, bytes], tag: int) -> bool:
    """Indicateur u8 = 1 (meme lecture que `Frame.uint`, sur le champ deja extrait)."""
    value = single.get(tag)
    return value is not None and len(value) in (1, 2, 4, 8) and int.from_bytes(value, "little") == 1


def _start_task(coro) -> None:  # type: ignore[no-untyped-def]
    """Tache demarree tout de suite (Python >= 3.12 : `eager_start`), sinon tache ordinaire."""
    loop = asyncio.get_running_loop()
    if sys.version_info >= (3, 12):
        asyncio.Task(coro, loop=loop, eager_start=True)
    else:  # pragma: no cover - Python 3.10/3.11
        loop.create_task(coro)


_WATCH_SYNC_SECONDS = 1.0     # leurres affectes ailleurs (RIPOSTE) : vus par le natif en au plus 1 s
_WATCH_ENTRIES_PER_FRAME = 2000  # ≈ 100 Kio par trame, loin de MAX_PAYLOAD
_PENDING_WARNING = 1000  # trames en attente sur un canal : signale une fois (natif qui ne lit plus)


class SecurityWorker:
    def __init__(self, server: AsyncioHttpServer, channels: list[socket.socket]) -> None:
        self.server = server
        self.channels = channels
        self.open_channels = len(channels)
        self.done: asyncio.Event | None = None
        self._watched: dict[str, float] = {}  # adresse -> echeance deja envoyee au natif
        # Correctif 2.6.2 (D19) : trames qui attendent que le canal se libere, par canal, dans l'ordre d'envoi.
        self._pending: dict[socket.socket, deque[bytes]] = {}
        server.watch_sink = self._watch

    async def run(self) -> None:
        loop = asyncio.get_running_loop()
        self.done = asyncio.Event()
        for channel in self.channels:
            channel.setblocking(False)
            loop.add_reader(channel.fileno(), self._readable, channel)
        sync = asyncio.ensure_future(self._sync_watch_list())
        await self.done.wait()
        sync.cancel()

    def _watch(self, ip: str, until: float) -> None:
        """Plan WAF natif, lot 3 : le natif envoie ici toutes les requetes de `ip` jusqu'a `until` (jamais raccourci).
        Envoye tout de suite, sur le premier canal ouvert : la table du natif est commune a tous ses fils."""
        self._send_watch([(ip, until)])

    def _send_watch(self, entries: list[tuple[str, float]]) -> None:
        fresh = [(ip, until) for ip, until in entries if until > self._watched.get(ip, 0.0)]
        channel = next((c for c in self.channels if c.fileno() >= 0), None)
        if not fresh or channel is None:
            return
        for start in range(0, len(fresh), _WATCH_ENTRIES_PER_FRAME):
            chunk = fresh[start:start + _WATCH_ENTRIES_PER_FRAME]
            if not self._send(channel, ipc.encode(ipc.watch_frame(chunk))):
                return  # canal perdu : le natif s'arrete, ou un nouveau processus de securite renverra la liste
            self._watched.update(chunk)  # envoyee ou en file : la file garantit l'envoi tant que le canal vit

    # ------------------------------------------------------------------ envoi vers le natif
    def _send(self, channel: socket.socket, data: bytes) -> bool:
        """Correctif 2.6.2 (D19) : avant, canal non bloquant + `except OSError: pass` -> un verdict (meme « bloquer »)
        ou une entree WATCH disparaissait quand le canal etait plein ; la requete attendait 60 s puis passait en
        fail-open. Desormais : envoi direct si rien n'attend, sinon file videe des que le canal se libere, toujours
        dans l'ordre (SEQPACKET : une trame part entiere ou pas du tout). False seulement si le canal est perdu - sa
        fermeture reste faite par la lecture, qui voit la fin du canal (comme avant)."""
        if channel.fileno() < 0:
            return False
        queue = self._pending.get(channel)
        if queue is not None:
            queue.append(data)
            if len(queue) == _PENDING_WARNING:
                print(f"processus de securite : {len(queue)} trames attendent que le moteur natif lise son canal",
                      file=sys.stderr)
            return True
        try:
            channel.send(data)
            return True
        except BlockingIOError:
            self._pending[channel] = deque([data])
            asyncio.get_running_loop().add_writer(channel.fileno(), self._flush, channel)
            return True
        except OSError:
            return False

    def _flush(self, channel: socket.socket) -> None:
        queue = self._pending.get(channel)
        while queue:
            try:
                channel.send(queue[0])
            except BlockingIOError:
                return  # toujours plein : add_writer rappellera
            except OSError:
                break  # canal perdu : la lecture le fermera
            queue.popleft()
        self._drop_pending(channel)

    def _drop_pending(self, channel: socket.socket) -> None:
        if self._pending.pop(channel, None) is not None and channel.fileno() >= 0:
            asyncio.get_running_loop().remove_writer(channel.fileno())

    async def _sync_watch_list(self) -> None:
        """Affectations ecrites par un autre processus (RIPOSTE, autre processus de securite) ou deja presentes au
        demarrage : relues dans la base des leurres et envoyees au natif (seulement ce qui est nouveau)."""
        while True:
            try:
                self._send_watch(self.server.active_deception_sources())
            except Exception as e:  # noqa: BLE001 - jamais l'arret du processus de securite pour cette lecture
                print(f"processus de securite : liste des sources suivies illisible ({type(e).__name__} : {e})",
                      file=sys.stderr)
            await asyncio.sleep(_WATCH_SYNC_SECONDS)

    def _readable(self, channel: socket.socket) -> None:
        while True:
            try:
                data, fds, _flags, _address = socket.recv_fds(channel, ipc.HEADER_SIZE + ipc.MAX_PAYLOAD, 4)
            except BlockingIOError:
                return
            except OSError:
                data, fds = b"", []
            if not data:
                for fd in fds:
                    os.close(fd)
                self._close(channel)
                return
            try:
                frame = ipc.decode(data)
            except ipc.FrameError as e:
                for fd in fds:
                    os.close(fd)
                print(f"processus de securite : trame refusee ({e})", file=sys.stderr)
                continue
            if frame.type == ipc.INSPECT:
                for fd in fds:
                    os.close(fd)
                # Demarrage immediat (2026-11-04, cout du WAF) : une requete propre est jugee et son verdict envoye
                # sans passer par la file de la boucle ; une requete qui attend (mode guerre, magnet) est suspendue
                # a son premier `await` et continue ensuite comme une tache ordinaire.
                _start_task(self._inspect(channel, frame))
            elif frame.type == ipc.HANDOFF and fds:
                asyncio.ensure_future(self._take_over(frame, fds))
            else:
                for fd in fds:
                    os.close(fd)

    async def _take_over(self, frame: ipc.Frame, fds: list[int]) -> None:
        """Lot 6 : connexion confiee (fd 1 = client ; fd 2 = memfd des octets deja lus s'ils sont gros)."""
        client = socket.socket(fileno=fds[0])
        pending = frame.first(ipc.HANDOFF_BYTES) or b""
        try:
            if len(fds) > 1:
                size = frame.uint(ipc.HANDOFF_BYTES_FD) or 0
                pending = os.pread(fds[1], size, 0)
                for fd in fds[2:]:
                    os.close(fd)
                os.close(fds[1])
            await self.server.serve_handed_off(client, pending, frame.uint(ipc.HANDOFF_SERVED) or 0)
        except Exception as e:  # noqa: BLE001 - une connexion perdue, jamais le processus
            print(f"processus de securite : connexion confiee abandonnee ({type(e).__name__} : {e})", file=sys.stderr)
            client.close()

    def _close(self, channel: socket.socket) -> None:
        self._drop_pending(channel)
        asyncio.get_running_loop().remove_reader(channel.fileno())
        channel.close()
        self.open_channels -= 1
        if self.open_channels <= 0 and self.done is not None:
            self.done.set()  # natif arrete : ce processus n'a plus de raison d'etre

    async def _inspect(self, channel: socket.socket, frame: ipc.Frame) -> None:
        request_id = f"{frame.request_id:016x}"
        try:
            peer_ip, head, body, client_ip, single = _inspected_head(frame)
            request = self.server.build_request(head, peer_ip, request_id, body, client_ip)
            if _flag(single, ipc.INSPECT_DELEGATE):
                # Lot 5 : route que le natif confie a Python (listing de repertoire, /load, /admin) - meme
                # route_request que le moteur Python ; la connexion continue normalement (keep-alive).
                data = ipc.encode(ipc.verdict_frame(frame.request_id, await self.server.route(request), True))
            else:
                outcome = await self.server.security_stage(
                    request, blocklist_known_clear=_flag(single, ipc.INSPECT_BLOCKLIST_CLEAR),
                    native_rate_limit=_counted_rate_limit(single))
                if outcome.notable and _flag(single, ipc.INSPECT_AUDIT):
                    # Lot 4 : le natif l'avait jugee propre - traitee normalement ici, desaccord journalise.
                    self.server.log_error_line(
                        f"controle du filtre WAF natif : desaccord, requete jugee propre par le moteur natif mais "
                        f"retenue par le controle de securite ({request.method} {request.path}) - a signaler",
                        request_id)
                if outcome.response is None:
                    data = ipc.continue_verdict_bytes(frame.request_id)  # cas courant : octets tout faits
                else:
                    data = ipc.encode(ipc.verdict_frame(frame.request_id, outcome.response, outcome.keep_alive_allowed))
        except Exception as e:  # noqa: BLE001 - moteur Python : exception = connexion fermee sans reponse
            print(f"processus de securite : erreur sur {request_id} : {type(e).__name__} : {e}", file=sys.stderr)
            data = ipc.encode(ipc.abort_frame(frame.request_id))
        self._send(channel, data)


def run_security_worker(server: AsyncioHttpServer, channel_fds: list[int], reload: Callable[[], None]) -> int:
    """Point d'entree du processus fils (fork du superviseur). `server` : AsyncioServer deja construit ; `reload` :
    rechargement sur SIGHUP (meme fonction que le moteur Python : configuration relue, try_reload_server)."""
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, signal.SIG_DFL)
    channels = [socket.socket(fileno=fd) for fd in channel_fds]
    worker = SecurityWorker(server, channels)

    async def main() -> None:
        loop = asyncio.get_running_loop()
        loop.add_signal_handler(signal.SIGHUP, reload)
        await worker.run()

    asyncio.run(main())
    return 0
