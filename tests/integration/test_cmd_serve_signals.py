"""Tests d'integration Phase 9 : `omega-serv serve` reel, lance comme
vrai sous-processus, vrais signaux OS (SIGTERM/SIGHUP) - la seule
maniere de verifier honnetement l'arret propre et le rechargement, ces
deux mecanismes ne pouvant pas etre asseres depuis l'interieur du meme
processus de test (asyncio.run() bloque le thread principal)."""
import http.client
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_REAL_SRC_DIR = _REPO_ROOT / "src"


def _wait_for_port(port: int, timeout: float = 5.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            conn = http.client.HTTPConnection("127.0.0.1", port, timeout=0.5)
            conn.request("GET", "/index.html")
            conn.getresponse()
            conn.close()
            return True
        except (ConnectionRefusedError, OSError, http.client.HTTPException):
            time.sleep(0.1)
    return False


def _wait_for_exit(proc: subprocess.Popen, timeout: float = 5.0) -> bool:
    try:
        proc.wait(timeout=timeout)
        return True
    except subprocess.TimeoutExpired:
        return False


class TestCmdServeSignals(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        shutil.copytree(_REAL_SRC_DIR, self.root / "src")
        self.src_dir = self.root / "src"

        (self.root / "webroot").mkdir()
        (self.root / "webroot" / "index.html").write_text("ok")
        (self.root / "config").mkdir()
        self.config_path = self.root / "config" / "omega-serve.json"
        self.config_path.write_text(json.dumps({
            "version": 1, "profile": "standard",
            "server": {"bind": "127.0.0.1", "port": 18765, "shutdown_grace_period_seconds": 3},
        }))
        self.pid_path = self.root / "var" / "run" / "omega-serv.pid"
        self._proc: subprocess.Popen | None = None

    def tearDown(self):
        if self._proc is not None:
            if self._proc.poll() is None:
                self._proc.kill()
                self._proc.wait(timeout=5)
            if self._proc.stdout is not None:
                self._proc.stdout.close()
        self._tmp.cleanup()

    def _spawn_server(self) -> subprocess.Popen:
        env = dict(os.environ)
        env["PYTHONPATH"] = str(self.src_dir)
        proc = subprocess.Popen(
            [sys.executable, "-m", "omega_serv", "--config", str(self.config_path), "serve"],
            cwd=str(self.root),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        self._proc = proc
        return proc

    def test_pid_file_written_while_running_and_removed_after_sigterm(self):
        proc = self._spawn_server()
        self.assertTrue(_wait_for_port(18765), "le serveur n'a jamais commence a repondre")
        self.assertTrue(self.pid_path.exists(), "fichier PID absent alors que le serveur tourne")
        self.assertEqual(int(self.pid_path.read_text().strip()), proc.pid)

        proc.send_signal(signal.SIGTERM)
        self.assertTrue(_wait_for_exit(proc, timeout=8), "le processus n'a pas quitte apres SIGTERM")
        self.assertFalse(self.pid_path.exists(), "fichier PID toujours present apres arret propre")

    def test_pid_file_written_while_running_and_removed_after_sigint(self):
        proc = self._spawn_server()
        self.assertTrue(_wait_for_port(18765), "le serveur n'a jamais commence a repondre")
        self.assertTrue(self.pid_path.exists(), "fichier PID absent alors que le serveur tourne")

        proc.send_signal(signal.SIGINT)
        self.assertTrue(_wait_for_exit(proc, timeout=8), "le processus n'a pas quitte apres SIGINT")
        self.assertFalse(self.pid_path.exists(), "fichier PID toujours present apres arret propre")

    def test_sigterm_drains_in_flight_request(self):
        import socket

        proc = self._spawn_server()
        self.assertTrue(_wait_for_port(18765))

        sock = socket.create_connection(("127.0.0.1", 18765), timeout=5)
        sock.sendall(b"GET /index.html HTTP/1.1\r\n")
        time.sleep(0.2)

        proc.send_signal(signal.SIGTERM)
        exited_immediately = _wait_for_exit(proc, timeout=0.5)
        self.assertFalse(exited_immediately, "le processus s'est arrete instantanement, sans drainer la connexion active")

        self.assertTrue(_wait_for_exit(proc, timeout=8), "le processus n'a pas quitte apres le delai de grace")
        sock.close()

    def test_sighup_reloads_without_stopping_server(self):
        proc = self._spawn_server()
        self.assertTrue(_wait_for_port(18765))

        proc.send_signal(signal.SIGHUP)
        time.sleep(0.5)
        self.assertIsNone(proc.poll(), "le processus s'est arrete alors qu'on attendait un simple rechargement")
        self.assertTrue(_wait_for_port(18765, timeout=2), "le serveur ne repond plus apres SIGHUP")

        proc.send_signal(signal.SIGTERM)
        self.assertTrue(_wait_for_exit(proc, timeout=8))

        output = proc.stdout.read() if proc.stdout else ""
        self.assertIn("Rechargement", output)


if __name__ == "__main__":
    unittest.main()
