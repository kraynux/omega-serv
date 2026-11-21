"""Superviseur reduit du natif seul (lot 5 memoire, 2026-11-19, OMEGA-SERV_ETUDE_PROXY_ET_MEMOIRE.md §8), de bout en
bout avec le vrai binaire : `serve` se re-execute (meme PID) puis sert, recharge (accepte et refuse), relance le natif
tue, s'arrete proprement. Le binaire natif n'est pas versionne : sans build, ces tests sont sautes."""
from __future__ import annotations

import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from typing import ClassVar

from tests.integration.proxy_harness import NATIVE_BINARY, REPO


def _get(port: int, path: str = "/") -> bytes:
    with socket.create_connection(("127.0.0.1", port), timeout=5) as sock:
        sock.sendall(f"GET {path} HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n".encode())
        chunks = []
        while data := sock.recv(65536):
            chunks.append(data)
    return b"".join(chunks)


@unittest.skipUnless(NATIVE_BINARY.exists(), "binaire natif non construit")
class TestReducedSupervisor(unittest.TestCase):
    options: ClassVar[dict] = {}

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="omega-watch-")
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        shutil.copytree(REPO / "src", self.root / "src", ignore=shutil.ignore_patterns("__pycache__", "*.bak"))
        for folder in ("webroot", "var/log", "var/run", "config", "bin"):
            (self.root / folder).mkdir(parents=True, exist_ok=True)
        (self.root / "webroot" / "index.html").write_text("site local")
        (self.root / "bin" / "omega-http-core").symlink_to(NATIVE_BINARY)
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            self.port = probe.getsockname()[1]
        self.config = {"server": {"engine": "native", "bind": "127.0.0.1", "port": self.port, "workers": 1},
                       "options": json.loads(json.dumps(self.options))}
        self._write_config()
        env = {**os.environ, "PYTHONPATH": str(self.root / "src")}
        self.process = subprocess.Popen([sys.executable, "-m", "omega_serv", "--config", "config/omega-serve.json",
                                         "serve"], cwd=self.root, env=env, stdout=subprocess.PIPE,
                                        stderr=subprocess.STDOUT)
        self.addCleanup(self._stop)
        self._wait(lambda: self._state().get("supervisor_pid") == self.process.pid, "etat du superviseur reduit")

    def _write_config(self) -> None:
        (self.root / "config" / "omega-serve.json").write_text(json.dumps(self.config))

    def _stop(self) -> None:
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(15)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(5)
        if self.process.stdout is not None:
            self.process.stdout.close()

    def _state(self) -> dict:
        try:
            return json.loads((self.root / "var" / "run" / "engine-state.json").read_text())
        except (OSError, ValueError):
            return {}

    def _wait(self, condition, what: str, timeout: float = 20) -> None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.process.poll() is not None:
                self.fail(f"serveur arrete ({what}) : {self.process.stdout.read().decode(errors='replace')[-2000:]}")
            if condition():
                return
            time.sleep(0.1)
        self.fail(f"delai depasse : {what} ; etat {self._state()}")

    def test_same_pid_reexecuted_and_serving(self):
        cmdline = Path(f"/proc/{self.process.pid}/cmdline").read_bytes().split(b"\0")
        self.assertIn(b"omega_serv.interfaces.cli.native_watch", cmdline)
        self.assertIn(b"site local", _get(self.port))
        state = self._state()
        self.assertEqual((state["effective"], state["requested"], state["generation"]), ("native", "native", 1))
        self.assertEqual((self.root / "var" / "run" / "omega-serv.pid").read_text().strip(), str(self.process.pid))

    def test_reload_accepted_then_refused(self):
        self.config["server"]["read_timeout_seconds"] = 7
        self._write_config()
        os.kill(self.process.pid, signal.SIGHUP)
        self._wait(lambda: self._state().get("last_reload") == "generation 2 active", "rechargement accepte")
        self.config["server"]["port"] = self.port + 1
        self._write_config()
        os.kill(self.process.pid, signal.SIGHUP)
        self._wait(lambda: "REFUSE" in self._state().get("last_reload", ""), "rechargement refuse")
        self.assertIn("server.port modifie", self._state()["last_reload"])
        (self.root / "config" / "omega-serve.json").write_text("{ pas du json")
        os.kill(self.process.pid, signal.SIGHUP)
        self._wait(lambda: "configuration invalide" in self._state().get("last_reload", ""), "configuration invalide")
        self.assertEqual(self._state()["generation"], 2)
        self.assertIn(b"site local", _get(self.port))
        error_log = (self.root / "var" / "log" / "error.log").read_text()
        self.assertIn("server.port modifie - redemarrage complet necessaire", error_log)

    def test_killed_native_is_restarted(self):
        native_pid = self._state()["native_pid"]
        os.kill(native_pid, signal.SIGKILL)
        self._wait(lambda: self._state().get("restarts") == 1 and self._state().get("native_pid") not in (0, native_pid),
                   "relance du natif")
        self._wait(lambda: b"site local" in _get(self.port), "natif relance qui sert")
        self.assertIn("moteur natif arrete de facon inattendue",
                      (self.root / "var" / "log" / "error.log").read_text())

    def test_sigterm_stops_everything(self):
        native_pid = self._state()["native_pid"]
        self.process.terminate()
        self.assertEqual(self.process.wait(20), 0)
        self.assertFalse((self.root / "var" / "run" / "omega-serv.pid").exists())
        self.assertFalse(Path(f"/proc/{native_pid}").exists() and
                         b"omega-http-core" in Path(f"/proc/{native_pid}/cmdline").read_bytes())


@unittest.skipUnless(NATIVE_BINARY.exists(), "binaire natif non construit")
class TestReducedSupervisorWithSecurityProcess(TestReducedSupervisor):
    """Etude §11 : processus de securite unique ne du superviseur reduit (fork apres gc.freeze)."""

    options: ClassVar[dict] = {"trusted_proxy": {"enabled": True, "trusted_networks": ["127.0.0.1/32"],
                                 "header_preference": ["X-Forwarded-For"]}}

    def _security_pid(self) -> int:
        return int(self._state().get("extra", {}).get("security_pid") or 0)

    def test_security_process_born_from_the_supervisor(self):
        pid = self._security_pid()
        status = Path(f"/proc/{pid}/status").read_text()
        self.assertIn(f"PPid:\t{self.process.pid}\n", status)
        self.assertEqual(Path(f"/proc/{pid}/comm").read_text().strip(), "omega-securite")

    def test_sighup_during_startup_never_kills_it(self):
        pid = self._security_pid()
        os.kill(pid, signal.SIGHUP)  # sans doute encore en construction de son serveur
        time.sleep(3)
        self.assertEqual(self._security_pid(), pid)
        self.assertTrue(Path(f"/proc/{pid}").exists())
        self.assertNotIn("processus de securite arrete", (self.root / "var" / "log" / "error.log").read_text()
                         if (self.root / "var" / "log" / "error.log").exists() else "")

    def test_killed_security_process_is_restarted(self):
        pid = self._security_pid()
        os.kill(pid, signal.SIGKILL)
        self._wait(lambda: self._security_pid() not in (0, pid), "relance du processus de securite")
        self._wait(lambda: b"site local" in _get(self.port), "site servi apres la relance")


if __name__ == "__main__":
    unittest.main()
