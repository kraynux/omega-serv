"""RIPOSTE de bout en bout, lot 2 (OMEGA-SERV_PLAN-DETAILLE_RIPOSTE.md §3.1-3.2) : un vrai `serve`
dans un dossier temporaire (copie de src/ : jamais le var/ du depot), mode simple et mode boost.
Verifie : processus lance par serve, attaque reelle vue par RIPOSTE, relance apres un arret brutal,
arret avec le serveur sans orphelin, rien du tout quand RIPOSTE est desactive."""
import http.client
import json
import os
import shutil
import signal
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

from omega_serv.core.platform_info import cpu_info

_REAL_SRC_DIR = Path(__file__).resolve().parents[2] / "src"


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _descendants(pid: int) -> list[int]:
    found: list[int] = []
    try:
        direct = [int(p) for p in Path(f"/proc/{pid}/task/{pid}/children").read_text().split()]
    except OSError:
        return found
    for child in direct:
        found.append(child)
        found.extend(_descendants(child))
    return found


def _riposte_processes_for(config_path: Path) -> list[int]:
    """Tout processus `riposte run` de CETTE instance encore vivant, ou qu'il soit (orphelin compris)."""
    found = []
    for entry in Path("/proc").iterdir():
        if entry.name.isdigit():
            cmdline = _cmdline(int(entry.name))
            if "riposte run" in cmdline and str(config_path) in cmdline:
                found.append(int(entry.name))
    return found


def _cmdline(pid: int) -> str:
    try:
        return Path(f"/proc/{pid}/cmdline").read_bytes().replace(b"\0", b" ").decode()
    except OSError:
        return ""


class _RiposteServeTestCase(unittest.TestCase):
    workers = 1
    riposte_enabled = True

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        shutil.copytree(_REAL_SRC_DIR, self.root / "src", ignore=shutil.ignore_patterns("*.bak", "__pycache__"))
        (self.root / "webroot").mkdir()
        (self.root / "webroot" / "index.html").write_text("ok")
        rules = self.root / "secure" / "waf" / "rules"
        rules.mkdir(parents=True)
        (rules / "scan.json").write_text(json.dumps({
            "version": 1, "pack": "sensitive-paths", "enabled": True,
            "rules": [{"id": "S1", "description": "sonde", "scope": ["path"], "pattern": "zzzz-sonde", "weight": 10}],
        }))
        (self.root / "config").mkdir()
        self.port = _free_port()
        self.config_path = self.root / "config" / "omega-serve.json"
        self.config_path.write_text(json.dumps({
            "version": 1, "profile": "standard",
            "server": {"bind": "127.0.0.1", "port": self.port, "shutdown_grace_period_seconds": 2,
                       "workers": self.workers},
            "options": {
                "waf": {"enabled": True, "mode": "block", "scoring": {"block_threshold": 5},
                        "rules": {"paths": ["secure/waf/rules/scan.json"]}},
                "riposte": {"enabled": self.riposte_enabled, "policies": [{
                    "id": "scan-immediat", "name": "Scan immédiat",
                    "when": {"attack_classes": ["scan"], "returns": 1, "within_seconds": 86400},
                }]},
            },
        }))
        env = dict(os.environ, PYTHONPATH=str(self.root / "src"))
        self.proc = subprocess.Popen(
            [sys.executable, "-m", "omega_serv", "--config", str(self.config_path), "serve"],
            cwd=self.root, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
            start_new_session=True,
        )
        self._wait_for(lambda: self._request("/index.html") == 200, 20)

    def tearDown(self):
        try:
            os.killpg(self.proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        self.proc.wait(10)
        self.proc.stdout.close()
        self._tmp.cleanup()

    def _wait_for(self, condition, seconds):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            if condition():
                return True
            time.sleep(0.2)
        return False

    def _request(self, path):
        try:
            conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=3)
            conn.request("GET", path)
            status = conn.getresponse().status
            conn.close()
            return status
        except OSError:
            return None

    def _riposte_pids(self):
        return [pid for pid in _descendants(self.proc.pid) if "riposte run" in _cmdline(pid)]

    def _stats(self):
        database = self.root / "var" / "lib" / "riposte.sqlite3"
        if not database.exists():
            return {}
        connection = sqlite3.connect(f"file:{database}?mode=ro", uri=True)
        try:
            row = connection.execute("SELECT value FROM state WHERE key='stats'").fetchone()
        except sqlite3.Error:
            return {}
        finally:
            connection.close()
        return json.loads(row[0]) if row else {}

    def _stop(self):
        self.proc.send_signal(signal.SIGTERM)
        self.proc.wait(30)
        return self.proc.stdout.read()


class TestRiposteWithSimpleServe(_RiposteServeTestCase):
    def test_real_attack_gives_a_real_ban(self):
        """Lot 4 : la decision est appliquee - ban reel dans la blocklist (source « riposte »), que le
        serveur applique a la requete suivante de la meme source."""
        self.assertTrue(self._wait_for(lambda: len(self._riposte_pids()) == 1, 15), "RIPOSTE non lance")
        time.sleep(2)  # le processus a fini de demarrer (ses lecteurs sont crees)
        self.assertEqual(self._request("/zzzz-sonde"), 403)

        def decisions():
            database = self.root / "var" / "lib" / "riposte.sqlite3"
            connection = sqlite3.connect(f"file:{database}?mode=ro", uri=True)
            try:
                return connection.execute("SELECT status, policy_id, applied FROM decisions").fetchall()
            except sqlite3.Error:
                return []
            finally:
                connection.close()

        self.assertTrue(self._wait_for(lambda: decisions() == [("matched", "scan-immediat", 1)], 15), decisions())
        blocklist = self.root / "var" / "lib" / "waf" / "blocklist.json"
        entries = json.loads(blocklist.read_text())["entries"]
        self.assertEqual([e["source"] for e in entries if e["reason"].startswith("riposte:")], ["riposte"])
        self.assertEqual(self._request("/index.html"), 451)  # bannie par RIPOSTE
        self._stop()

    def test_launched_sees_a_real_attack_restarts_and_stops_with_the_server(self):
        self.assertTrue(self._wait_for(lambda: len(self._riposte_pids()) == 1, 15), "RIPOSTE non lance")
        self.assertEqual(self._request("/zzzz-sonde"), 403)
        self.assertTrue(self._wait_for(lambda: self._stats().get("new_events", 0) >= 1, 15), self._stats())

        (first,) = self._riposte_pids()
        os.kill(first, signal.SIGKILL)
        self.assertTrue(self._wait_for(lambda: self._riposte_pids() not in ([], [first]), 15), "pas de relance")
        # Le serveur web repond toujours ; le client du test (127.0.0.1, sans proxy de confiance) est banni
        # par RIPOSTE depuis le lot 4 -> 451 de la blocklist, jamais une absence de reponse.
        self.assertEqual(self._request("/index.html"), 451)

        output = self._stop()
        self.assertEqual(self.proc.returncode, 0, output)
        self.assertIn("relance", output)
        self.assertEqual(_riposte_processes_for(self.config_path), [], output)  # aucun orphelin


@unittest.skipIf(cpu_info().available < 2, "mode boost : au moins 2 CPU disponibles necessaires")
class TestRiposteWithBoostServe(_RiposteServeTestCase):
    workers = 2

    def test_one_riposte_beside_the_workers_and_clean_stop(self):
        self.assertTrue(self._wait_for(lambda: len(self._riposte_pids()) == 1, 15), "RIPOSTE non lance")
        self.assertEqual(self._request("/zzzz-sonde"), 403)
        self.assertTrue(self._wait_for(lambda: self._stats().get("new_events", 0) >= 1, 15), self._stats())
        (riposte_pid,) = self._riposte_pids()
        os.kill(riposte_pid, signal.SIGKILL)  # recolte par le waitpid(-1) du superviseur
        self.assertTrue(self._wait_for(lambda: self._riposte_pids() not in ([], [riposte_pid]), 15), "pas de relance")
        self.assertEqual(self._request("/index.html"), 451)  # le serveur repond ; client banni par RIPOSTE (lot 4)
        output = self._stop()
        self.assertEqual(self.proc.returncode, 0, output)
        self.assertEqual(_riposte_processes_for(self.config_path), [], output)


class TestRiposteDisabled(_RiposteServeTestCase):
    riposte_enabled = False

    def test_nothing_is_started_or_created(self):
        time.sleep(2)
        self.assertEqual(self._riposte_pids(), [])
        self.assertFalse((self.root / "var" / "lib" / "riposte.sqlite3").exists())
        self._stop()
        self.assertEqual(self.proc.returncode, 0)


if __name__ == "__main__":
    unittest.main()
