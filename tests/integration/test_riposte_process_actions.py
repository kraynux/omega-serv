"""RIPOSTE lot 4, bout en bout avec le VRAI processus `riposte run` (OMEGA-SERV_PLAN-DETAILLE_RIPOSTE.md §10,
critere « tests de crash verts ; ban reel en local ») : une attaque ecrite dans waf-alerts.log devient un
ban dans la blocklist, levee par une commande de la CLI ; le processus tue brutalement (SIGKILL) retrouve
au redemarrage l'etat reel des actions (reconciliation)."""
import argparse
import contextlib
import io
import json
import os
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from datetime import datetime, timezone
from pathlib import Path

from omega_serv.bootstrap.container import DependencyContainer
from omega_serv.domain.config.entities import OmegaServConfig
from omega_serv.domain.config.option import Option
from omega_serv.infrastructure.persistence.sqlite_riposte_connection import open_riposte_connection
from omega_serv.infrastructure.persistence.sqlite_riposte_store import SqliteRiposteStore
from omega_serv.interfaces.cli import riposte_action_commands as cli

SRC = Path(__file__).resolve().parents[2] / "src"
IP = "203.0.113.7"
_RUN = (
    "import argparse, sys\n"
    "from pathlib import Path\n"
    "from omega_serv.bootstrap.container import DependencyContainer\n"
    "from omega_serv.interfaces.cli.riposte_commands import cmd_riposte_run\n"
    "root = Path(sys.argv[1])\n"
    "container = DependencyContainer(project_root=root, instance_registry_path=root / 'instances.json')\n"
    "sys.exit(cmd_riposte_run(argparse.Namespace(config=root / 'config' / 'omega-serve.json'), container))\n"
)


def _wait(condition, timeout=10.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = condition()
        if value:
            return value
        time.sleep(0.1)
    return None


class TestRiposteProcessActions(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.container = DependencyContainer(project_root=self.root, instance_registry_path=self.root / "i.json")
        self.config_path = self.root / "config" / "omega-serve.json"
        self.config_path.parent.mkdir()
        policy = {"id": "sqli", "name": "Injections", "attack_classes": ["sqli"], "returns": 1,
                  "within_seconds": 86400, "action": "local_ban"}
        self.container.configuration.save(self.config_path, OmegaServConfig(options={
            "waf": Option(name="waf", enabled=True, settings={}),
            "riposte": Option(name="riposte", enabled=True, settings={"policies": [policy]}),
        }))
        self.waf_log = self.root / "var" / "log" / "waf-alerts.log"
        self.waf_log.parent.mkdir(parents=True)
        self.waf_log.touch()
        self.blocklist = self.root / "var" / "lib" / "waf" / "blocklist.json"
        self.database = self.root / "var" / "lib" / "riposte.sqlite3"
        self.process = None
        self._requests = 0

    def tearDown(self):
        self._stop(signal.SIGTERM)
        self._tmp.cleanup()

    def _start(self):
        env = {**os.environ, "PYTHONPATH": str(SRC)}
        self.process = subprocess.Popen([sys.executable, "-c", _RUN, str(self.root)], env=env,
                                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        self.assertTrue(_wait(lambda: self._state("heartbeat_at")), "RIPOSTE n'a pas demarre")

    def _stop(self, sig):
        if self.process is None:
            return ""
        if self.process.poll() is None:
            self.process.send_signal(sig)
        output, _err = self.process.communicate(timeout=10)
        self.process = None
        return output

    def _state(self, key):
        if not self.database.exists():
            return None
        connection = open_riposte_connection(self.database, read_only=True)
        try:
            return SqliteRiposteStore(connection).get_state(key)
        finally:
            connection.close()

    def _store(self):
        return SqliteRiposteStore(open_riposte_connection(self.database, read_only=True))

    def _attack(self):
        self._requests += 1
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(), "request_id": f"r{self._requests}",
            "remote_ip": IP, "method": "GET", "path": "/x", "user_agent": "curl", "action": "block",
            "stage": "inspection", "status_code": 403, "score": 8, "rules": ["SQLI-1"],
            "findings": [{"id": "SQLI-1", "pack": "body-sqli"}],
        }
        with self.waf_log.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record) + "\n")

    def _riposte_entries(self):
        if not self.blocklist.exists():
            return []
        try:
            entries = json.loads(self.blocklist.read_text(encoding="utf-8")).get("entries", [])
        except ValueError:
            return []
        return [e for e in entries if e.get("source") == "riposte"]

    def test_ban_revoke_crash_and_reconcile(self):
        self._start()
        self._attack()
        [entry] = _wait(self._riposte_entries) or self.fail("aucun ban RIPOSTE pose")
        self.assertEqual(entry["network"], IP + "/32")
        self.assertTrue(entry["reason"].endswith(" sqli #1"), entry["reason"])
        [action] = self._store().list_actions(in_progress=True, limit=10)

        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = cli.cmd_riposte_actions_revoke(
                argparse.Namespace(config=self.config_path, id=action.id, exempt=None, not_recidive=False),
                self.container)
        self.assertEqual(code, 0, out.getvalue())
        self.assertIn(f"Action {action.id} levée.", out.getvalue())
        self.assertEqual(self._riposte_entries(), [])

        # Retour de la source apres la levee : nouvel episode, palier 2.
        self._attack()
        [second] = _wait(self._riposte_entries) or self.fail("pas de 2e ban")
        self.assertTrue(second["reason"].endswith(" sqli #2"), second["reason"])

        # Arret brutal, puis ban retire a la main pendant que RIPOSTE est arrete.
        self._stop(signal.SIGKILL)
        data = json.loads(self.blocklist.read_text(encoding="utf-8"))
        data["entries"] = [e for e in data["entries"] if e.get("source") != "riposte"]
        self.blocklist.write_text(json.dumps(data), encoding="utf-8")

        self._start()
        self.assertTrue(_wait(lambda: not self._store().list_actions(in_progress=True, limit=10)))
        output = self._stop(signal.SIGTERM)
        self.assertIn("reconciliation des actions - revoked 1", output)
        finished = {a.id: a for a in self._store().list_actions(in_progress=False, limit=10)}
        self.assertEqual(finished[action.id].finished_by, "user")
        [outside] = [a for a in finished.values() if a.id != action.id]
        self.assertEqual((outside.state, outside.detail), ("revoked", "removed_outside"))


if __name__ == "__main__":
    unittest.main()
