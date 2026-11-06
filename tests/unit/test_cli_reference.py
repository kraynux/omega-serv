"""Aide de la CLI : chaque commande et chaque option ont un texte, `omega-serv help` affiche l'arbre, et
docs/HELP.md + docs/omega-serv.1 (generes par tools/cli_reference.py) suivent le parseur."""
from __future__ import annotations

import contextlib
import importlib.util
import io
import unittest
from argparse import Namespace
from pathlib import Path

from omega_serv.interfaces.cli.command_tree import cmd_help, render_tree, walk
from omega_serv.interfaces.cli.main import build_parser

PROJECT = Path(__file__).resolve().parents[2]


def _reference_tool():  # type: ignore[no-untyped-def]
    spec = importlib.util.spec_from_file_location("cli_reference", PROJECT / "tools" / "cli_reference.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestCliHelpTexts(unittest.TestCase):
    def test_every_command_has_a_text(self):
        missing = [" ".join(c.path) for c in walk(build_parser()) if not c.text.strip()]
        self.assertEqual(missing, [])

    def test_every_argument_has_a_text(self):
        missing = [f"{' '.join(c.path)} {a.names}" for c in walk(build_parser()) for a in c.arguments
                   if not a.text.strip()]
        self.assertEqual(missing, [])

    def test_tree_lists_nested_commands_in_order(self):
        paths = [c.path for c in walk(build_parser())]
        self.assertLess(paths.index(("config",)), paths.index(("config", "backup")))
        self.assertIn(("riposte", "actions", "revoke"), paths)
        self.assertIn(("help",), paths)


class TestHelpCommand(unittest.TestCase):
    def _run(self, *branch: str) -> tuple[int, str]:
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = cmd_help(build_parser(), Namespace(branch=list(branch)))
        return code, output.getvalue()

    def test_full_tree(self):
        code, output = self._run()
        self.assertEqual(code, 0)
        self.assertIn("serve", output)
        self.assertIn("    revoke", output)

    def test_branch_only(self):
        code, output = self._run("riposte", "actions")
        self.assertEqual(code, 0)
        self.assertIn("revoke", output)
        self.assertNotIn("blocklist", output)

    def test_unknown_branch(self):
        code, output = self._run("inexistante")
        self.assertEqual(code, 1)
        self.assertIn("inexistante", output)

    def test_wrapped_tree_keeps_every_command(self):
        parser = build_parser()
        narrow = render_tree(parser, columns=60) or []
        self.assertTrue(all(len(line) <= 60 for line in narrow))
        command_lines = [line for line in narrow if not line.startswith(" " * 10)]
        self.assertEqual(len(command_lines), len(walk(parser)))

    def test_dispatched_from_parser(self):
        args = build_parser().parse_args(["help", "audit"])
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = args.func(args, None)
        self.assertEqual(code, 0)
        self.assertIn("security", output.getvalue())


class TestGeneratedReference(unittest.TestCase):
    def test_help_md_and_man_page_up_to_date(self):
        tool = _reference_tool()
        parser = build_parser()
        for path, content in ((tool.HELP_MD, tool.render_markdown(parser)), (tool.MAN_PAGE, tool.render_man(parser))):
            with self.subTest(fichier=path.name):
                self.assertTrue(path.exists(), f"{path.name} absent : lancer tools/cli_reference.py")
                self.assertEqual(path.read_text(encoding="utf-8"), content,
                                 f"{path.name} pas à jour : lancer tools/cli_reference.py")

    def test_man_page_escapes_option_dashes(self):
        man = _reference_tool().render_man(build_parser())
        self.assertIn("\\-\\-config", man)
        self.assertNotIn("\n--", man)


if __name__ == "__main__":
    unittest.main()
