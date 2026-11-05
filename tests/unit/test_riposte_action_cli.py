"""CLI RIPOSTE du lot 4 : la CLI depose des commandes, ne touche jamais au registre, ne cree jamais la base ;
arret d'urgence pose directement (persistant) ; desactivation d'une regle dans la configuration."""
import argparse
import contextlib
import io
import tempfile
import threading
import time
import unittest
from datetime import datetime, timezone
from pathlib import Path

from omega_serv.application.config.load_config import load_config
from omega_serv.bootstrap.container import DependencyContainer
from omega_serv.domain.config.entities import OmegaServConfig
from omega_serv.domain.config.option import Option
from omega_serv.infrastructure.persistence.sqlite_riposte_connection import open_riposte_connection
from omega_serv.infrastructure.persistence.sqlite_riposte_store import SqliteRiposteStore
from omega_serv.interfaces.cli import riposte_action_commands as cli
from omega_serv.interfaces.cli.main import build_parser

POLICY = {"id": "scan", "name": "Scan", "attack_classes": ["scan"], "returns": 2, "within_seconds": 86400,
          "action": "local_ban"}


class TestActionCli(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.container = DependencyContainer(project_root=self.root,
                                             instance_registry_path=self.root / "instances.json")
        self.config_path = self.root / "config" / "omega-serve.json"
        self.config_path.parent.mkdir()
        config = OmegaServConfig(options={"riposte": Option(name="riposte", enabled=True,
                                                            settings={"policies": [POLICY]})})
        self.container.configuration.save(self.config_path, config)
        self.database = self.root / "var" / "lib" / "riposte.sqlite3"

    def tearDown(self):
        self._tmp.cleanup()

    def _args(self, **values):
        return argparse.Namespace(config=self.config_path, **values)

    def _call(self, function, **values):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            code = function(self._args(**values), self.container)
        return code, out.getvalue()

    def _create_database(self):
        connection = open_riposte_connection(self.database)  # comme le processus au premier lancement
        connection.close()

    def _store(self):
        return SqliteRiposteStore(open_riposte_connection(self.database, read_only=True))

    def test_parser_knows_the_new_commands(self):
        parser = build_parser()
        for argv in (["riposte", "actions", "list", "--finished"], ["riposte", "actions", "revoke", "abc",
                     "--exempt", "7d", "--not-recidive"], ["riposte", "policies", "disable", "scan", "--revoke"],
                     ["riposte", "sources", "forget", "203.0.113.7"], ["riposte", "exemptions", "remove", "x"],
                     ["riposte", "stop", "--revoke"], ["riposte", "resume"]):
            self.assertTrue(callable(parser.parse_args(argv).func), argv)

    def test_never_creates_the_database(self):
        code, out = self._call(cli.cmd_riposte_stop, revoke=False)
        self.assertEqual(code, 1)
        self.assertIn("jamais été lancé", out)
        self.assertFalse(self.database.exists())

    def test_emergency_stop_is_persistent_and_resume_clears_it(self):
        self._create_database()
        code, out = self._call(cli.cmd_riposte_stop, revoke=True)
        self.assertEqual(code, 0)
        self.assertIn("arrêté", out)  # processus arrete : la levee attend son demarrage
        store = self._store()
        self.assertEqual(store.get_state("emergency_stop"), "1")
        self.assertEqual([c.kind for c in store.pending_commands(10)], ["revoke_all"])
        self._call(cli.cmd_riposte_resume)
        self.assertEqual(self._store().get_state("emergency_stop"), "0")

    def test_revoke_only_deposits_a_command(self):
        self._create_database()
        code, _out = self._call(cli.cmd_riposte_actions_revoke, id="abc", exempt="24h", not_recidive=True)
        self.assertEqual(code, 0)
        [command] = self._store().pending_commands(10)
        self.assertEqual((command.kind, command.params),
                         ("revoke", {"action_id": "abc", "exempt": "24h", "not_recidive": True}))

    def test_disable_policy_writes_the_config_then_asks_reload_and_revoke(self):
        self._create_database()
        code, out = self._call(cli.cmd_riposte_policies_disable, id="scan", revoke=True)
        self.assertEqual(code, 0, out)
        config = load_config(self.container.configuration, self.config_path).config
        self.assertFalse(config.options["riposte"].settings["policies"][0]["enabled"])
        self.assertEqual([c.kind for c in self._store().pending_commands(10)], ["reload", "revoke_policy"])

    def test_unknown_policy(self):
        code, _out = self._call(cli.cmd_riposte_policies_enable, id="nope")
        self.assertEqual(code, 1)

    def test_actions_list_without_actions(self):
        self._create_database()
        code, out = self._call(cli.cmd_riposte_actions_list, finished=False, ip=None, limit=10)
        self.assertEqual(code, 0)
        self.assertIn("Aucune action en cours", out)

    def test_running_process_result_is_shown(self):
        self._create_database()
        process = SqliteRiposteStore(open_riposte_connection(self.database))
        process.set_state("heartbeat_at", datetime.now(timezone.utc).isoformat())

        def _process_runs():  # le processus RIPOSTE execute la commande deposee (sa propre connexion)
            process = SqliteRiposteStore(open_riposte_connection(self.database))
            for _attempt in range(50):
                pending = process.pending_commands(10)
                if pending:
                    process.finish_command(pending[0].id, state="done", result="revoked",
                                           result_params={"action_id": "abc"}, done_at=datetime.now(timezone.utc))
                    return
                time.sleep(0.05)

        worker = threading.Thread(target=_process_runs)
        worker.start()
        code, out = self._call(cli.cmd_riposte_actions_revoke, id="abc", exempt=None, not_recidive=False)
        worker.join()
        self.assertEqual(code, 0)
        self.assertIn("Action abc levée.", out)

if __name__ == "__main__":
    unittest.main()
