# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
import tempfile
import unittest
from pathlib import Path

from omega_serv.domain.config.exceptions import ProfileLoadError, ProfileNotFoundError
from omega_serv.infrastructure.config.profile_repository import FileProfileRepository
from omega_serv.infrastructure.filesystem.local_filesystem import LocalFilesystem


class TestFileProfileRepository(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.profiles_dir = Path(self._tmp.name) / "profiles"
        self.profiles_dir.mkdir()
        (self.profiles_dir / "standard.json").write_text('{"name": "standard", "description": "d"}')
        (self.profiles_dir / "hardened.json").write_text('{"name": "hardened", "description": "d2"}')
        (self.profiles_dir / "broken.json").write_text("{ not valid json")
        self.repo = FileProfileRepository(LocalFilesystem(), self.profiles_dir)

    def tearDown(self):
        self._tmp.cleanup()

    def test_list_profile_names(self):
        self.assertEqual(self.repo.list_profile_names(), ["broken", "hardened", "standard"])

    def test_load_existing_profile(self):
        profile = self.repo.load_profile("standard")
        self.assertEqual(profile.name, "standard")

    def test_load_missing_profile_raises(self):
        with self.assertRaises(ProfileNotFoundError):
            self.repo.load_profile("does-not-exist")

    def test_load_broken_profile_raises(self):
        with self.assertRaises(ProfileLoadError):
            self.repo.load_profile("broken")

    def test_list_on_missing_directory_returns_empty(self):
        repo = FileProfileRepository(LocalFilesystem(), self.profiles_dir / "nope")
        self.assertEqual(repo.list_profile_names(), [])


if __name__ == "__main__":
    unittest.main()
