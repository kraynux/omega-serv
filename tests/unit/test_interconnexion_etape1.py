"""Correctifs du 2026-11-10 (etude de l'interconnecteur, etape 1) : refus de root pour les commandes
qui ecrivent, origine des bans (--origin), sortie JSON de la blocklist, setgid de var/run."""
import argparse
import json
import stat
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from omega_serv.application.security.manage_blocklist import add_blocklist_entry, remove_blocklist_entry
from omega_serv.application.services.pid_file import write_pid_file
from omega_serv.domain.security.waf.blocklist import validate_origin
from omega_serv.infrastructure.filesystem.local_filesystem import LocalFilesystem
from omega_serv.interfaces.cli import main as cli


class _FakeBlocklist:
    def __init__(self):
        self.entries = []

    def list_entries(self):
        return tuple(self.entries)

    def add_entry(self, entry):
        self.entries = [e for e in self.entries if e.network != entry.network] + [entry]

    def remove_entry(self, network):
        before = len(self.entries)
        self.entries = [e for e in self.entries if e.network != network]
        return len(self.entries) < before

    def remove_entry_if(self, network, predicate):
        before = len(self.entries)
        self.entries = [e for e in self.entries if not (e.network == network and predicate(e))]
        return len(self.entries) < before


class TestOrigin(unittest.TestCase):
    def test_origin_is_stored_and_only_that_origin_can_remove(self):
        blocklist = _FakeBlocklist()
        self.assertTrue(add_blocklist_entry(blocklist, "203.0.113.9", "ban", 60, origin="omega-fire").success)
        self.assertEqual(blocklist.entries[0].origin, "omega-fire")
        self.assertFalse(remove_blocklist_entry(blocklist, "203.0.113.9", origin="omega-jail").success)
        self.assertEqual(len(blocklist.entries), 1)
        self.assertTrue(remove_blocklist_entry(blocklist, "203.0.113.9", origin="omega-fire").success)
        self.assertEqual(blocklist.entries, [])

    def test_ban_replaced_by_another_tool_is_not_removed_by_origin(self):
        """Course corrigee : le WAF remplace l'entree du pont entre sa lecture et son retrait."""
        blocklist = _FakeBlocklist()
        add_blocklist_entry(blocklist, "203.0.113.9", "pont", 60, origin="omega-jail")
        add_blocklist_entry(blocklist, "203.0.113.9", "waf", 3600)  # sans origine (WAF, CLI)
        self.assertFalse(remove_blocklist_entry(blocklist, "203.0.113.9", origin="omega-jail").success)
        self.assertEqual(len(blocklist.entries), 1)

    def test_invalid_and_reserved_origins_are_refused(self):
        self.assertIsNone(validate_origin("omega-fire"))
        self.assertIsNone(validate_origin("omega-jail:riposte-1h"))
        self.assertIsNotNone(validate_origin("Omega Fire"))
        self.assertIsNotNone(validate_origin("intervention"))
        self.assertIsNotNone(validate_origin("x" * 65))
        result = add_blocklist_entry(_FakeBlocklist(), "203.0.113.9", "ban", 60, origin="intervention")
        self.assertFalse(result.success)


class TestRootRefusal(unittest.TestCase):
    def _args(self, func_name, command="blocklist"):
        func = getattr(cli, func_name)
        return argparse.Namespace(command=command, func=func)

    @patch.object(cli, "running_as_root", return_value=True)
    def test_writing_command_refused_as_root(self, _root):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(cli._refuse_root_for_writing_command(self._args("cmd_blocklist_add"), Path(tmp)), 1)

    @patch.object(cli, "running_as_root", return_value=True)
    def test_read_only_and_service_commands_allowed_as_root(self, _root):
        with tempfile.TemporaryDirectory() as tmp:
            for name in ("cmd_blocklist_list", "cmd_waf_never_auto_block", "cmd_service_install", "cmd_version"):
                self.assertIsNone(cli._refuse_root_for_writing_command(self._args(name), Path(tmp)), name)

    @patch.object(cli, "running_as_root", return_value=False)
    def test_nothing_refused_without_root(self, _root):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(cli._refuse_root_for_writing_command(self._args("cmd_blocklist_add"), Path(tmp)))

    def test_allowed_names_all_exist(self):
        from omega_serv.interfaces.cli import riposte_query_commands as riposte
        missing = [n for n in cli._ROOT_ALLOWED_COMMANDS if not hasattr(cli, n) and not hasattr(riposte, n)]
        self.assertEqual(missing, [])


class TestBlocklistJson(unittest.TestCase):
    def test_list_json_is_untranslated_and_versioned(self):
        blocklist = _FakeBlocklist()
        add_blocklist_entry(blocklist, "203.0.113.9", "ban", None, confirm_permanent=True, origin="omega-fire")
        args = argparse.Namespace(config=None, format="json")
        with patch.object(cli, "load_config") as load, patch.object(cli, "build_blocklist_port", return_value=blocklist), \
                patch("builtins.print") as printed:
            load.return_value = argparse.Namespace(success=True, config=object(), errors=[])
            self.assertEqual(cli.cmd_blocklist_list(args, argparse.Namespace(
                configuration=None, project_root=Path("/x"), filesystem=None, clock=None)), 0)
        payload = json.loads(printed.call_args[0][0])
        self.assertEqual(payload["schema_version"], 1)
        self.assertEqual(payload["entries"][0]["origin"], "omega-fire")
        self.assertIsNone(payload["entries"][0]["expires_at"])  # jamais le mot traduit « permanent »


class TestRunDirectorySetgid(unittest.TestCase):
    def test_run_directory_keeps_setgid(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "var" / "run" / "omega-serv.pid"
            write_pid_file(LocalFilesystem(), path, 4242)
            self.assertTrue(path.parent.stat().st_mode & stat.S_ISGID)


if __name__ == "__main__":
    unittest.main()
