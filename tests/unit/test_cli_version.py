"""`omega-serv version [--check]` (2026-11-07) : meme verification que le bouton du Guide d'aide."""
from __future__ import annotations

import contextlib
import io
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path
from unittest import mock

from omega_serv.bootstrap.container import DependencyContainer
from omega_serv.interfaces.cli.main import build_parser, cmd_version

_FETCH = "omega_serv.infrastructure.updates.https_release_source.HttpsReleaseSource.fetch_sha_list"


class TestCliVersion(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        (root / "pyproject.toml").write_text('version = "2.5.0"\n', encoding="utf-8")
        self.container = DependencyContainer(project_root=root)

    def tearDown(self):
        self._tmp.cleanup()

    def _run(self, check: bool) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cmd_version(Namespace(check=check), self.container)
        return code, out.getvalue(), err.getvalue()

    def test_parser_knows_the_command(self):
        args = build_parser().parse_args(["version", "--check"])
        self.assertIs(args.func, cmd_version)
        self.assertTrue(args.check)

    def test_prints_installed_version_without_network(self):
        with mock.patch(_FETCH) as fetch:
            code, out, _err = self._run(check=False)
        fetch.assert_not_called()
        self.assertEqual((code, out), (0, "2.5.0\n"))

    def test_check_reports_new_version_with_notes(self):
        with mock.patch(_FETCH, return_value="aa  omega-serv-2.6.0.tar.gz\n"):
            code, out, _err = self._run(check=True)
        self.assertEqual(code, 0)
        self.assertIn("2.6.0", out)
        self.assertIn("omega-serv-2.6.0-nouveautes.txt", out)

    def test_check_unreachable_site_exit_code_1(self):
        with mock.patch(_FETCH, return_value=None):
            code, _out, err = self._run(check=True)
        self.assertEqual(code, 1)
        self.assertIn("2.5.0", err)


if __name__ == "__main__":
    unittest.main()
