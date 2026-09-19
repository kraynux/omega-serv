import tempfile
import unittest
from pathlib import Path

from omega_serv.domain.security.path_policy import PathRejectionReason
from omega_serv.infrastructure.filesystem.local_filesystem import LocalFilesystem
from omega_serv.infrastructure.filesystem.safe_path_resolver import SafePathResolver


class TestSafePathResolver(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.project_root = Path(self._tmp.name)
        self.webroot = self.project_root / "webroot"
        self.webroot.mkdir()
        (self.webroot / "index.html").write_text("ok")
        (self.webroot / "public").mkdir()
        (self.webroot / "public" / "file.txt").write_text("content")

        self.secure = self.project_root / "secure"
        self.secure.mkdir()
        (self.secure / "secret.txt").write_text("do not serve")

        self.resolver = SafePathResolver(LocalFilesystem(), self.webroot)

    def tearDown(self):
        self._tmp.cleanup()

    def test_valid_file_resolves_under_webroot(self):
        result = self.resolver.resolve("/public/file.txt")
        self.assertTrue(result.ok)
        self.assertEqual(result.absolute_path, self.webroot / "public" / "file.txt")

    def test_traversal_outside_webroot_rejected(self):
        result = self.resolver.resolve("/../secure/secret.txt")
        self.assertFalse(result.ok)
        self.assertEqual(result.rejection_reason, PathRejectionReason.TRAVERSAL_ATTEMPT)

    def test_symlink_escaping_webroot_rejected(self):
        symlink_path = self.webroot / "escape"
        symlink_path.symlink_to(self.secure / "secret.txt")

        result = self.resolver.resolve("/escape")
        self.assertFalse(result.ok)
        self.assertEqual(result.rejection_reason, PathRejectionReason.TRAVERSAL_ATTEMPT)

    def test_symlink_staying_inside_webroot_is_allowed(self):
        symlink_path = self.webroot / "alias.html"
        symlink_path.symlink_to(self.webroot / "index.html")

        result = self.resolver.resolve("/alias.html")
        self.assertTrue(result.ok)

    def test_nonexistent_file_still_resolves_safely(self):
        result = self.resolver.resolve("/does-not-exist.html")
        self.assertTrue(result.ok)
        self.assertEqual(result.absolute_path, self.webroot / "does-not-exist.html")


if __name__ == "__main__":
    unittest.main()
