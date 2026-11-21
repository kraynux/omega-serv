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
import contextvars
import os
import signal
import socket
import sys
from collections import deque
from collections.abc import Callable
from typing import TYPE_CHECKING

from omega_serv.application.server.engine_selection import native_zone_prefixes
from omega_serv.infrastructure.server import native_ipc as ipc
from omega_serv.infrastructure.server.http_parser import ParsedRequestHead
from omega_serv.infrastructure.server.relayed_health import RelayedHealthState

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


def _attach_memfd_body(frame: ipc.Frame, fds: list[int]) -> None:
    """Plan proxy natif v2, lot 4 (S23) : corps capture trop gros pour la trame, passe par memfd (fd 1) - relu ici et
    remis dans la trame comme INSPECT_BODY. Le descripteur est ferme par l'appelant sur tous les chemins."""
    size = frame.uint(ipc.INSPECT_BODY_FD)
    if size is None or not fds:
        return
    chunks = []
    offset = 0
    while offset < size:
        chunk = os.pread(fds[0], min(size - offset, 1 << 20), offset)
        if not chunk:
            raise OSError(f"memfd plus court que prevu ({offset} sur {size} octets)")
        chunks.append(chunk)
        offset += len(chunk)
    frame.fields.append((ipc.INSPECT_BODY, b"".join(chunks)))


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
_VERDICT_WATCH: contextvars.ContextVar[list[tuple[str, float]] | None] = contextvars.ContextVar(
    "omega_verdict_watch", default=None)
"""Plan proxy natif v2, lot 6 (P5, S26) : sources que l'inspection en cours fait surveiller - jointes a son verdict, que
le natif applique avant de repondre (avant : trame WATCH sur un autre canal, parfois lue apres la requete suivante)."""


class SecurityWorker:
    def __init__(self, server: AsyncioHttpServer, channels: list[socket.socket], first: bool = False) -> None:
        self.server = server
        self.channels = channels
        self.first = first  # lot 6 (P6) : processus n° 0 - sondes des zones natives, etats vers le natif
        self.relayed_health: RelayedHealthState | None = None
        self.open_channels = len(channels)
        self.done: asyncio.Event | None = None
        self._watched: dict[str, float] = {}  # adresse -> echeance deja envoyee au natif
        # Correctif 2.6.2 (D19) : trames qui attendent que le canal se libere, par canal, dans l'ordre d'envoi.
        self._pending: dict[socket.socket, deque[tuple[bytes, int | None]]] = {}
        server.watch_sink = self._watch
        # Plan proxy natif v2, lot 6 (P6) : les zones relayees par le natif ne sont sondees que par le processus n° 0,
        # dont l'etat de sante relaie sondes et etats manuels vers le natif et lit en retour l'etat de ses backends.
        server.probe_filter = lambda prefix: self.first or prefix not in self._native_zones()
        if first:
            self.relayed_health = RelayedHealthState(self._send_backend_events, self._native_zones)
            server.replace_proxy_health_state(self.relayed_health)

    async def run(self) -> None:
        loop = asyncio.get_running_loop()
        self.done = asyncio.Event()
        for channel in self.channels:
            channel.setblocking(False)
            loop.add_reader(channel.fileno(), self._readable, channel)
        sync = asyncio.ensure_future(self._sync_watch_list())
        await self.done.wait()
        sync.cancel()

    def _native_zones(self) -> frozenset[str]:
        return native_zone_prefixes(self.server.config)

    def _send_backend_events(self, entries: list[tuple[str, str, str, str]]) -> None:
        channel = next((c for c in self.channels if c.fileno() >= 0), None)
        if channel is not None:  # la table du natif est commune a tous ses fils
            self._send(channel, ipc.encode(ipc.backend_event_frame(entries)))

    def _watch(self, ip: str, until: float) -> None:
        """Plan WAF natif, lot 3 : le natif envoie ici toutes les requetes de `ip` jusqu'a `until` (jamais raccourci).
        Envoye tout de suite, sur le premier canal ouvert : la table du natif est commune a tous ses fils. Lot 6 (P5) :
        decide pendant une inspection, joint a son verdict - applique avant la requete suivante de la source."""
        collected = _VERDICT_WATCH.get()
        if collected is not None:
            if until > self._watched.get(ip, 0.0):
                collected.append((ip, until))
                self._watched[ip] = until
            return
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
    def _send(self, channel: socket.socket, data: bytes, pass_fd: int | None = None) -> bool:
        """Correctif 2.6.2 (D19) : avant, canal non bloquant + `except OSError: pass` -> un verdict (meme « bloquer »)
        ou une entree WATCH disparaissait quand le canal etait plein ; la requete attendait 60 s puis passait en
        fail-open. Desormais : envoi direct si rien n'attend, sinon file videe des que le canal se libere, toujours
        dans l'ordre (SEQPACKET : une trame part entiere ou pas du tout). False seulement si le canal est perdu - sa
        fermeture reste faite par la lecture, qui voit la fin du canal (comme avant).

        Plan proxy natif v2, lot 4 : `pass_fd` (HANDOFF_DONE) part avec la trame, puis est ferme ici, envoye ou non -
        jamais une fuite. Canal perdu : False, et l'appelant garde sa propre copie (la connexion reste chez lui)."""
        if channel.fileno() < 0:
            return False
        queue = self._pending.get(channel)
        if queue is not None:
            queue.append((data, pass_fd))
            if len(queue) == _PENDING_WARNING:
                print(f"processus de securite : {len(queue)} trames attendent que le moteur natif lise son canal",
                      file=sys.stderr)
            return True
        try:
            self._send_now(channel, data, pass_fd)
            return True
        except BlockingIOError:
            self._pending[channel] = deque([(data, pass_fd)])
            asyncio.get_running_loop().add_writer(channel.fileno(), self._flush, channel)
            return True
        except OSError:
            if pass_fd is not None:
                os.close(pass_fd)
            return False

    @staticmethod
    def _send_now(channel: socket.socket, data: bytes, pass_fd: int | None) -> None:
        if pass_fd is None:
            channel.send(data)
            return
        socket.send_fds(channel, [data], [pass_fd])
        os.close(pass_fd)  # le natif a maintenant sa propre copie

    def _flush(self, channel: socket.socket) -> None:
        queue = self._pending.get(channel)
        while queue:
            try:
                self._send_now(channel, *queue[0])
            except BlockingIOError:
                return  # toujours plein : add_writer rappellera
            except OSError:
                break  # canal perdu : la lecture le fermera
            queue.popleft()
        self._drop_pending(channel)

    def _drop_pending(self, channel: socket.socket) -> None:
        queue = self._pending.pop(channel, None)
        if queue is not None:
            for _data, pass_fd in queue:  # canal perdu : connexions rendues jamais parties, fermees
                if pass_fd is not None:
                    os.close(pass_fd)
            if channel.fileno() >= 0:
                asyncio.get_running_loop().remove_writer(channel.fileno())

    async def _sync_watch_list(self) -> None:
        """Affectations ecrites par un autre processus (RIPOSTE, autre processus de securite) ou deja presentes au
        demarrage : relues dans la base des leurres et envoyees au natif (seulement ce qui est nouveau). Plan proxy
        natif v2, lot 1 (D37) : au premier passage, aussi les sources surveillees pour leur etat de menace."""
        first = True
        while True:
            try:
                if first:
                    first = False
                    self._send_watch(self.server.active_threat_sources())
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
                try:
                    _attach_memfd_body(frame, fds)
                except OSError as e:
                    # Jamais un controle sans le corps attendu : requete abandonnee (fermeture sans reponse).
                    print(f"processus de securite : corps inspecte illisible ({e})", file=sys.stderr)
                    self._send(channel, ipc.encode(ipc.abort_frame(frame.request_id)))
                    continue
                finally:
                    for fd in fds:
                        os.close(fd)
                # Demarrage immediat (2026-11-04, cout du WAF) : une requete propre est jugee et son verdict envoye
                # sans passer par la file de la boucle ; une requete qui attend (mode guerre, magnet) est suspendue
                # a son premier `await` et continue ensuite comme une tache ordinaire.
                _start_task(self._inspect(channel, frame))
            elif frame.type == ipc.HANDOFF and fds:
                asyncio.ensure_future(self._take_over(frame, fds, channel))
            elif frame.type == ipc.BACKEND_STATE and self.relayed_health is not None:
                for fd in fds:
                    os.close(fd)
                self.relayed_health.apply_report(ipc.backend_states(frame))
            else:
                for fd in fds:
                    os.close(fd)

    async def _take_over(self, frame: ipc.Frame, fds: list[int], channel: socket.socket) -> None:
        """Lot 6 : connexion confiee (fd 1 = client ; fd 2 = memfd des octets deja lus s'ils sont gros). Plan proxy
        natif v2, lot 4 (D12) : rendue au natif sur le meme canal apres chaque reponse (HANDOFF_DONE), et la limite de
        debit de la requete confiee est celle que le natif a deja comptee."""
        client = socket.socket(fileno=fds[0])
        pending = frame.first(ipc.HANDOFF_BYTES) or b""

        def give_back(fd: int, buffered: bytes, served: int) -> bool:
            return self._send(channel, ipc.encode(ipc.handoff_done_frame(buffered, served)), fd)

        try:
            if len(fds) > 1:
                size = frame.uint(ipc.HANDOFF_BYTES_FD) or 0
                pending = os.pread(fds[1], size, 0)
                for fd in fds[2:]:
                    os.close(fd)
                os.close(fds[1])
            await self.server.serve_handed_off(client, pending, frame.uint(ipc.HANDOFF_SERVED) or 0,
                                               native_rate_limit=frame.uint(ipc.HANDOFF_RATE_LIMIT),
                                               give_back=give_back)
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
        watched: list[tuple[str, float]] = []
        token = _VERDICT_WATCH.set(watched)  # retiree a la sortie, meme quand l'inspection est attendue directement
        try:
            await self._inspect_collecting(channel, frame, request_id, watched)
        finally:
            _VERDICT_WATCH.reset(token)

    async def _inspect_collecting(self, channel: socket.socket, frame: ipc.Frame, request_id: str,
                                  watched: list[tuple[str, float]]) -> None:
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
        if watched:
            verdict = ipc.decode(data)  # P5 : la surveillance part avec le verdict
            data = ipc.encode(ipc.add_verdict_watch(verdict, watched))
        self._send(channel, data)


STARTUP_SIGNALS = (signal.SIGHUP, signal.SIGTERM, signal.SIGINT)
"""A bloquer des la naissance du processus de securite (fork ou interpreteur neuf), jusqu'a ses gestionnaires."""


def run_security_worker(server: AsyncioHttpServer, channel_fds: list[int], reload: Callable[[], None],
                        first: bool = False) -> int:
    """Point d'entree du processus fils (fork du superviseur). `server` : AsyncioServer deja construit ; `reload` :
    rechargement sur SIGHUP (meme fonction que le moteur Python : configuration relue, try_reload_server)."""
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, signal.SIG_DFL)
    channels = [socket.socket(fileno=fd) for fd in channel_fds]
    worker = SecurityWorker(server, channels, first)

    async def main() -> None:
        loop = asyncio.get_running_loop()
        loop.add_signal_handler(signal.SIGHUP, reload)
        # Plan proxy natif v2, lot 1 (D11) : SIGTERM = arret propre (avant : mort immediate, connexions confiees
        # - proxy, envoi de fichiers - coupees net).
        stopping = asyncio.Event()
        loop.add_signal_handler(signal.SIGTERM, stopping.set)
        # Bloques depuis la naissance du processus (STARTUP_SIGNALS) : un rechargement ou un arret demande pendant la
        # construction du serveur est traite maintenant, jamais l'action par defaut qui le tuait (2026-11-19).
        signal.pthread_sigmask(signal.SIG_UNBLOCK, STARTUP_SIGNALS)
        # Plan proxy natif v2, lot A (D10) : sondes des backends et ecriture differee d'Active Defense, comme
        # `start()` du moteur Python - avant, jamais lancees ici (0 sonde en mode natif, essai du 2026-11-11).
        server.start_background_tasks()
        running = asyncio.ensure_future(worker.run())
        stop_requested = asyncio.ensure_future(stopping.wait())
        try:
            await asyncio.wait({running, stop_requested}, return_when=asyncio.FIRST_COMPLETED)
            # Lot 1 (D11) : natif arrete ou SIGTERM - connexions confiees en cours videes dans le delai de grace.
            await server.shutdown(float(server.grace_period_seconds))
        finally:
            stop_requested.cancel()
            running.cancel()
            # Sondes arretees, ecritures Active Defense en attente videes (2 s au plus), comme close().
            await server.close()

    asyncio.run(main())
    return 0
