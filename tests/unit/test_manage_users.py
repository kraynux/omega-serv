# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
import unittest

from omega_serv.application.auth.manage_users import add_user, change_password, remove_user
from omega_serv.domain.security.auth.entities import UserAccount
from omega_serv.domain.security.auth.password_hashing import verify_password


class _FakeUsersRepo:
    def __init__(self, users=()):
        self._users = tuple(users)

    def load(self):
        return self._users

    def save(self, users):
        self._users = tuple(users)


class TestAddUser(unittest.TestCase):
    def test_creates_user_with_hashed_password(self):
        repo = _FakeUsersRepo()
        result = add_user(repo, "admin", "hunter2")
        self.assertTrue(result.success)
        self.assertEqual(len(repo.load()), 1)
        self.assertTrue(verify_password("hunter2", repo.load()[0].password_hash))

    def test_empty_username_rejected(self):
        repo = _FakeUsersRepo()
        result = add_user(repo, "", "hunter2")
        self.assertFalse(result.success)

    def test_empty_password_rejected(self):
        repo = _FakeUsersRepo()
        result = add_user(repo, "admin", "")
        self.assertFalse(result.success)

    def test_duplicate_username_rejected(self):
        repo = _FakeUsersRepo([UserAccount(username="admin", password_hash="x")])
        result = add_user(repo, "admin", "hunter2")
        self.assertFalse(result.success)
        self.assertEqual(len(repo.load()), 1)


class TestRemoveUser(unittest.TestCase):
    def test_removes_existing_user(self):
        repo = _FakeUsersRepo([UserAccount(username="admin", password_hash="x")])
        result = remove_user(repo, "admin")
        self.assertTrue(result.success)
        self.assertEqual(repo.load(), ())

    def test_missing_user_reports_failure(self):
        repo = _FakeUsersRepo()
        result = remove_user(repo, "admin")
        self.assertFalse(result.success)


class TestChangePassword(unittest.TestCase):
    def test_updates_password_hash(self):
        repo = _FakeUsersRepo([UserAccount(username="admin", password_hash="old")])
        result = change_password(repo, "admin", "new-password")
        self.assertTrue(result.success)
        self.assertTrue(verify_password("new-password", repo.load()[0].password_hash))

    def test_missing_user_reports_failure(self):
        repo = _FakeUsersRepo()
        result = change_password(repo, "admin", "new-password")
        self.assertFalse(result.success)

    def test_empty_password_rejected(self):
        repo = _FakeUsersRepo([UserAccount(username="admin", password_hash="old")])
        result = change_password(repo, "admin", "")
        self.assertFalse(result.success)

    def test_does_not_affect_other_users(self):
        repo = _FakeUsersRepo([UserAccount(username="admin", password_hash="old-admin"), UserAccount(username="bob", password_hash="old-bob")])
        change_password(repo, "admin", "new-password")
        bob = next(u for u in repo.load() if u.username == "bob")
        self.assertEqual(bob.password_hash, "old-bob")


if __name__ == "__main__":
    unittest.main()
