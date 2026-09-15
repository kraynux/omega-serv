# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
import tempfile
import unittest
from pathlib import Path

from omega_serv.domain.security.auth.entities import UserAccount
from omega_serv.domain.security.auth.exceptions import UsersFileError
from omega_serv.infrastructure.auth.users_repository import JsonUsersRepository
from omega_serv.infrastructure.filesystem.local_filesystem import LocalFilesystem


class TestJsonUsersRepository(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.path = self.root / "users.json"
        self.repo = JsonUsersRepository(LocalFilesystem(), self.path)

    def tearDown(self):
        self._tmp.cleanup()

    def test_missing_file_returns_empty(self):
        self.assertEqual(self.repo.load(), ())

    def test_save_then_load_round_trips(self):
        users = (UserAccount(username="admin", password_hash="scrypt$16384$8$1$aa$bb"),)
        self.repo.save(users)
        self.assertEqual(self.repo.load(), users)

    def test_save_sets_strict_permissions(self):
        self.repo.save((UserAccount(username="admin", password_hash="x"),))
        mode = LocalFilesystem().file_mode(self.path)
        self.assertEqual(mode, 0o600)

    def test_invalid_json_raises(self):
        self.path.write_text("{ not json")
        with self.assertRaises(UsersFileError):
            self.repo.load()

    def test_unsupported_version_raises(self):
        self.path.write_text('{"version": 99, "users": []}')
        with self.assertRaises(UsersFileError):
            self.repo.load()


if __name__ == "__main__":
    unittest.main()
