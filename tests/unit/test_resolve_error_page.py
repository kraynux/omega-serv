import tempfile
import unittest
from pathlib import Path

from omega_serv.application.server.resolve_error_page import resolve_error_page_body
from omega_serv.infrastructure.filesystem.local_filesystem import LocalFilesystem


class TestResolveErrorPageBody(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.custom_dir = Path(self._tmp.name) / ".errors"
        self.custom_dir.mkdir()
        self.filesystem = LocalFilesystem()

    def tearDown(self):
        self._tmp.cleanup()

    def test_no_custom_dir_returns_default_page(self):
        body = resolve_error_page_body(404, None, self.filesystem)
        self.assertIn(b"404", body)
        self.assertIn(b"Not Found", body)

    def test_custom_dir_without_matching_file_falls_back_to_default(self):
        body = resolve_error_page_body(404, self.custom_dir, self.filesystem)
        self.assertIn(b"404", body)
        self.assertIn(b"Not Found", body)

    def test_custom_dir_with_matching_file_returns_its_content(self):
        (self.custom_dir / "404.html").write_text("<html>404 sur mesure</html>")
        body = resolve_error_page_body(404, self.custom_dir, self.filesystem)
        self.assertEqual(body, b"<html>404 sur mesure</html>")


if __name__ == "__main__":
    unittest.main()
