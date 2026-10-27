"""Mode « boost » de bout en bout (OMEGA-SERV_ETUDE_MODE_BOOST.md) : vrai `omega-serv serve`
avec plusieurs workers, vrais signaux, vrais compteurs partages.

La preuve centrale : avec une limite de debit de 10 et des connexions separees (le noyau les
repartit entre les workers), EXACTEMENT 10 requetes passent au total - pas 10 par worker."""
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

from omega_serv.core.platform_info import cpu_info

_REAL_SRC_DIR = Path(__file__).resolve().parents[2] / "src"
_PORT = 18766


def _status(path: str = "/index.html") -> int | None:
    try:
        conn = http.client.HTTPConnection("127.0.0.1", _PORT, timeout=3)
        conn.request("GET", path, headers={"Connection": "close"})
        status = conn.getresponse().status
        conn.close()
        return status
    except OSError:
        return None


def _children(pid: int) -> list[int]:
    try:
        return [int(p) for p in Path(f"/proc/{pid}/task/{pid}/children").read_text().split()]
    except OSError:
        return []


@unittest.skipIf(cpu_info().available < 2, "mode boost : au moins 2 CPU disponibles necessaires")
class TestServeWorkers(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        shutil.copytree(_REAL_SRC_DIR, self.root / "src", ignore=shutil.ignore_patterns("*.bak", "__pycache__"))
        (self.root / "webroot").mkdir()
        (self.root / "webroot" / "index.html").write_text("ok")
        rules = self.root / "secure" / "waf" / "rules"
        rules.mkdir(parents=True)
        (rules / "vide.json").write_text(json.dumps({
            "version": 1, "pack": "vide", "enabled": True,
            "rules": [{"id": "V1", "description": "jamais", "scope": ["path"], "pattern": "zzzz-jamais", "weight": 1}],
        }))
        (self.root / "config").mkdir()
        self.config_path = self.root / "config" / "omega-serve.json"
        self.config_path.write_text(json.dumps({
            "version": 1, "profile": "standard",
            "server": {"bind": "127.0.0.1", "port": _PORT, "shutdown_grace_period_seconds": 3, "workers": 2},
            "options": {"waf": {
                "enabled": True, "mode": "block", "rules": {"paths": ["secure/waf/rules/vide.json"]},
                "rate_limit": {"enabled": True, "global": {"requests": 10, "window_seconds": 3600}},
            }},
        }))
        env = dict(os.environ, PYTHONPATH=str(self.root / "src"))
        self.proc = subprocess.Popen(
            [sys.executable, "-m", "omega_serv", "--config", str(self.config_path), "serve"],
            cwd=self.root, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
            start_new_session=True,  # groupe de processus propre : rien d'orphelin si un test echoue
        )
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline and len(_children(self.proc.pid)) < 2:
            time.sleep(0.1)
        time.sleep(1.0)  # les workers chargent leurs regles

    def tearDown(self):
        try:
            os.killpg(self.proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        self.proc.wait(10)
        self.proc.stdout.close()
        self._tmp.cleanup()

    def _stop(self) -> str:
        self.proc.send_signal(signal.SIGTERM)
        self.proc.wait(20)
        return self.proc.stdout.read()

    def test_two_workers_share_the_rate_limit_exactly(self):
        self.assertEqual(len(_children(self.proc.pid)), 2)
        statuses = [_status() for _ in range(25)]
        self.assertEqual(statuses.count(200), 10, statuses)
        self.assertEqual(statuses.count(429), 15, statuses)
        output = self._stop()
        self.assertIn("2 worker(s)", output)
        self.assertEqual(self.proc.returncode, 0)

    def test_reload_reaches_every_worker_and_keeps_the_counters(self):
        for _ in range(10):
            _status()
        self.proc.send_signal(signal.SIGHUP)
        time.sleep(1.5)
        self.assertEqual(_status(), 429)  # compteurs conserves au rechargement
        output = self._stop()
        self.assertEqual(output.count("Rechargement termine."), 2, output)

    def test_stop_ends_all_workers_and_frees_the_shared_memory(self):
        children = _children(self.proc.pid)
        self.assertEqual(len(children), 2)
        self.assertTrue(Path(f"/dev/shm/omega_serv_{_PORT}").exists())
        self._stop()
        self.assertEqual(self.proc.returncode, 0)
        for child in children:
            self.assertFalse(Path(f"/proc/{child}").exists(), child)
        self.assertFalse(Path(f"/dev/shm/omega_serv_{_PORT}").exists())
        self.assertFalse((self.root / "var" / "run" / "omega-serv.pid").exists())

    def test_a_crashed_worker_is_restarted(self):
        victim = _children(self.proc.pid)[0]
        os.kill(victim, signal.SIGKILL)
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            children = _children(self.proc.pid)
            if len(children) == 2 and victim not in children:
                break
            time.sleep(0.1)
        self.assertEqual(len(_children(self.proc.pid)), 2)
        self.assertEqual(_status(), 200)
        self.assertIn("relance", self._stop())


if __name__ == "__main__":
    unittest.main()
