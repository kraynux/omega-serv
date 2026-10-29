"""Vidage du dossier d'export / de captures (correctif 2026-10-27) : contenu supprime, dossier
garde, liens non suivis, dossiers dangereux refuses, elements non supprimables signales."""
from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from omega_serv.application.terminal.clear_directory import check_clearable, clear_directory
from omega_serv.application.terminal.exceptions import UnsafeDirectoryError


class ClearDirectoryTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.base = Path(self._tmp.name)
        self.project = self.base / "omega-serv"
        (self.project / "var").mkdir(parents=True)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_clears_content_keeps_folder_and_link_targets(self) -> None:
        target = self.base / "exports"
        (target / "sub").mkdir(parents=True)
        (target / "a.html").write_text("x")
        (target / "sub" / "b.txt").write_text("y")
        outside = self.base / "garder.txt"
        outside.write_text("z")
        (target / "lien").symlink_to(outside)
        result = clear_directory(target, self.project)
        self.assertEqual((result.removed, result.failed), (3, ()))
        self.assertTrue(target.is_dir())
        self.assertEqual(list(target.iterdir()), [])
        self.assertTrue(outside.exists())

    def test_dangerous_folders_refused(self) -> None:
        for path in (Path("/"), Path("/etc"), Path("/home"), Path("/home/quelquun"), Path("/usr"),
                     self.project, self.base):
            with self.subTest(path=path), self.assertRaises(UnsafeDirectoryError):
                check_clearable(path, self.project)

    @unittest.skipIf(os.geteuid() == 0, "root ignore les droits")
    def test_undeletable_entry_reported_others_removed(self) -> None:
        target = self.base / "exports"
        locked = target / "verrou"
        locked.mkdir(parents=True)
        (locked / "f").write_text("x")
        (target / "libre.txt").write_text("x")
        locked.chmod(0o500)
        try:
            result = clear_directory(target, self.project)
        finally:
            locked.chmod(0o700)
        self.assertEqual(result.removed, 1)
        self.assertEqual(len(result.failed), 1)
        self.assertIn("verrou", result.failed[0])
