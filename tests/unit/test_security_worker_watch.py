"""Sources suivies envoyees au moteur natif (plan WAF natif, lot 3) : trame WATCH, jamais de doublon, prolongation
envoyee, grosses listes decoupees. Controle 1/N (lot 4) : desaccord journalise, requete traitee normalement."""
import asyncio
import socket
import unittest

from omega_serv.infrastructure.server import native_ipc as ipc
from omega_serv.infrastructure.server import security_worker as module
from omega_serv.infrastructure.server.asyncio_server import SecurityOutcome
from omega_serv.infrastructure.server.security_worker import SecurityWorker


class _Server:
    watch_sink = None


def _frames(sock: socket.socket) -> list[ipc.Frame]:
    sock.setblocking(False)
    frames = []
    while True:
        try:
            frames.append(ipc.decode(sock.recv(ipc.HEADER_SIZE + ipc.MAX_PAYLOAD)))
        except BlockingIOError:
            return frames


class TestWatch(unittest.TestCase):
    def setUp(self):
        self.ours, self.native = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)
        self.server = _Server()
        self.worker = SecurityWorker(self.server, [self.ours])

    def tearDown(self):
        self.ours.close()
        self.native.close()

    def test_sink_installed_and_entries_sent_once(self):
        self.assertEqual(self.server.watch_sink, self.worker._watch)
        self.worker._watch("203.0.113.1", 1000.2)
        self.worker._watch("203.0.113.1", 900.0)   # plus courte : rien
        self.worker._watch("203.0.113.1", 1000.2)  # identique : rien
        self.worker._watch("203.0.113.1", 2000.0)  # prolongee : envoyee
        frames = _frames(self.native)
        self.assertEqual([f.type for f in frames], [ipc.WATCH, ipc.WATCH])
        self.assertEqual(frames[0].all(ipc.WATCH_ENTRY), [b"203.0.113.1\x001001"])  # arrondi vers le haut
        self.assertEqual(frames[1].all(ipc.WATCH_ENTRY), [b"203.0.113.1\x002001"])

    def test_large_lists_are_split(self):
        entries = [(f"10.0.{i // 256}.{i % 256}", 5000.0) for i in range(module._WATCH_ENTRIES_PER_FRAME + 5)]
        self.worker._send_watch(entries)
        frames = _frames(self.native)
        self.assertEqual([len(f.all(ipc.WATCH_ENTRY)) for f in frames], [module._WATCH_ENTRIES_PER_FRAME, 5])
        self.worker._send_watch(entries)  # deja connues : rien
        self.assertEqual(_frames(self.native), [])

    def test_lost_channel_never_raises(self):
        self.native.close()
        self.worker._watch("203.0.113.9", 3000.0)  # canal perdu : silencieux, rien de memorise
        self.assertNotIn("203.0.113.9", self.worker._watched)


class _AuditServer:
    watch_sink = None

    def __init__(self, notable: bool):
        self.notable = notable
        self.errors: list[str] = []

    def build_request(self, head, peer_ip, request_id, body=None, client_ip=None):
        return type("R", (), {"method": head.method, "path": head.target, "remote_ip": peer_ip})()

    async def security_stage(self, request, blocklist_known_clear=False, native_rate_limit=None):
        self.native_rate_limit = native_rate_limit
        return SecurityOutcome(None, notable=self.notable)

    def log_error_line(self, message, request_id):
        self.errors.append(message)


class TestAudit(unittest.TestCase):
    def _inspect(self, notable: bool, audit: bool, rate: int | None = None) -> tuple[list[str], list[ipc.Frame]]:
        ours, native = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)
        server = self.server = _AuditServer(notable)
        worker = SecurityWorker(server, [ours])
        frame = (ipc.Frame(ipc.INSPECT, request_id=9).add(ipc.INSPECT_PEER, "203.0.113.4").add(ipc.INSPECT_METHOD, "GET")
                 .add(ipc.INSPECT_TARGET, "/x").add(ipc.INSPECT_VERSION, "HTTP/1.1"))
        if audit:
            frame.add_uint(ipc.INSPECT_AUDIT, 1, 1)
        if rate is not None:
            frame.add_uint(ipc.INSPECT_RATE_LIMIT, rate, 4)
        asyncio.run(worker._inspect(ours, frame))
        frames = _frames(native)
        ours.close()
        native.close()
        return server.errors, frames

    def test_disagreement_logged_and_request_still_handled(self):
        errors, frames = self._inspect(notable=True, audit=True)
        self.assertEqual(len(errors), 1)
        self.assertIn("desaccord", errors[0])
        self.assertEqual(frames[0].uint(ipc.VERDICT_DECISION), ipc.CONTINUE)  # meme verdict qu'un controle normal

    def test_rate_limit_counted_by_native_passed_to_security_stage(self):
        # Lot 6 : etiquette 11 (u32) -> native_rate_limit ; absente -> None (Python compte lui-meme)
        self._inspect(notable=False, audit=False, rate=12)
        self.assertEqual(self.server.native_rate_limit, 12)
        self._inspect(notable=False, audit=False, rate=0)
        self.assertEqual(self.server.native_rate_limit, 0)
        self._inspect(notable=False, audit=False)
        self.assertIsNone(self.server.native_rate_limit)

    def test_no_log_when_python_agrees_or_not_an_audit(self):
        self.assertEqual(self._inspect(notable=False, audit=True)[0], [])
        self.assertEqual(self._inspect(notable=True, audit=False)[0], [])  # requete ordinaire : pas un desaccord


if __name__ == "__main__":
    unittest.main()
