"""Blocklists sous var/lib/waf/ (2026-10-18) : dossier partage 2770 quel que
soit l'umask, reprise UNIQUE des anciens fichiers de secure/waf/, jamais un
ecrasement ni un chemin personnalise touche."""
from __future__ import annotations

import os
import stat
import tempfile
import unittest
from pathlib import Path

from omega_serv.application.security.blocklist_location import prepare_blocklist_location
from omega_serv.domain.security.waf.config import (
    DEFAULT_BLOCKLIST_PATH,
    DEFAULT_MAGNET_BLOCKLIST_FILE,
    LEGACY_BLOCKLIST_PATH,
    LEGACY_MAGNET_BLOCKLIST_FILE,
)
from omega_serv.infrastructure.filesystem.local_filesystem import LocalFilesystem


class TestPrepareBlocklistLocation(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.fs = LocalFilesystem()
        self._old_umask = os.umask(0o022)

    def tearDown(self) -> None:
        os.umask(self._old_umask)
        self._tmp.cleanup()

    def _prepare(self, configured: str = DEFAULT_BLOCKLIST_PATH) -> str | None:
        return prepare_blocklist_location(
            self.fs, self.root, configured, DEFAULT_BLOCKLIST_PATH, LEGACY_BLOCKLIST_PATH,
        )

    def _legacy(self, content: str) -> Path:
        legacy = self.root / LEGACY_BLOCKLIST_PATH
        legacy.parent.mkdir(parents=True)
        legacy.write_text(content)
        return legacy

    def test_directory_is_group_writable_despite_umask_022(self):
        self._prepare()
        directory = self.root / "var/lib/waf"
        mode = stat.S_IMODE(directory.stat().st_mode)
        self.assertEqual(mode, 0o2770)

    def test_legacy_file_is_copied_once_and_kept(self):
        legacy = self._legacy('{"entries": [{"ip": "203.0.113.9"}]}')
        message = self._prepare()
        target = self.root / DEFAULT_BLOCKLIST_PATH
        self.assertEqual(target.read_text(), '{"entries": [{"ip": "203.0.113.9"}]}')
        self.assertTrue(legacy.exists(), "l'ancien fichier sert de sauvegarde")
        self.assertIn("reprise", message or "")

    def test_existing_new_file_is_never_overwritten(self):
        self._legacy("ancien")
        target = self.root / DEFAULT_BLOCKLIST_PATH
        target.parent.mkdir(parents=True)
        target.write_text("nouveau")
        self.assertIsNone(self._prepare())
        self.assertEqual(target.read_text(), "nouveau")

    def test_second_start_does_nothing(self):
        self._legacy("ancien")
        self._prepare()
        (self.root / DEFAULT_BLOCKLIST_PATH).write_text("bans ajoutes depuis")
        self.assertIsNone(self._prepare())
        self.assertEqual((self.root / DEFAULT_BLOCKLIST_PATH).read_text(), "bans ajoutes depuis")

    def test_custom_path_is_left_alone(self):
        self._legacy("ancien")
        self.assertIsNone(self._prepare("secure/waf/blocklist.json"))
        self.assertFalse((self.root / "var/lib/waf").exists())

    def test_no_legacy_file_only_creates_directory(self):
        self.assertIsNone(self._prepare())
        self.assertTrue((self.root / "var/lib/waf").is_dir())
        self.assertFalse((self.root / DEFAULT_BLOCKLIST_PATH).exists())

    def test_existing_directory_mode_is_untouched(self):
        directory = self.root / "var/lib/waf"
        directory.mkdir(parents=True, mode=0o700)
        os.chmod(directory, 0o700)
        self._prepare()
        self.assertEqual(stat.S_IMODE(directory.stat().st_mode), 0o700)

    def test_magnet_blocklist_uses_same_rules(self):
        legacy = self.root / LEGACY_MAGNET_BLOCKLIST_FILE
        legacy.parent.mkdir(parents=True)
        legacy.write_text("198.51.100.7\n")
        prepare_blocklist_location(
            self.fs, self.root, DEFAULT_MAGNET_BLOCKLIST_FILE,
            DEFAULT_MAGNET_BLOCKLIST_FILE, LEGACY_MAGNET_BLOCKLIST_FILE,
        )
        self.assertEqual((self.root / DEFAULT_MAGNET_BLOCKLIST_FILE).read_text(), "198.51.100.7\n")


if __name__ == "__main__":
    unittest.main()
