# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
import tempfile
import unittest
from pathlib import Path

from omega_serv.domain.upload.entities import UploadRequest
from omega_serv.infrastructure.filesystem.local_filesystem import LocalFilesystem
from omega_serv.infrastructure.upload.filesystem_upload_storage import FilesystemUploadStorage


def _request(filename="photo.jpg") -> UploadRequest:
    return UploadRequest(
        zone_prefix="/upload/", filename=filename, content_type="image/jpeg",
        size=7, source_ip="203.0.113.10",
    )


class TestFilesystemUploadStorage(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.project_root = Path(self._tmp.name)
        self.filesystem = LocalFilesystem()
        self.storage = FilesystemUploadStorage(self.filesystem, self.project_root)

    def tearDown(self):
        self._tmp.cleanup()

    def test_store_creates_directory_and_writes_content(self):
        target = self.storage.store(_request(), "var/uploads/public", b"content")
        self.assertTrue(target.exists())
        self.assertEqual(target.read_bytes(), b"content")
        self.assertTrue(target.parent.samefile(self.project_root / "var" / "uploads" / "public"))

    def test_stored_filename_is_not_the_original_name(self):
        target = self.storage.store(_request(filename="photo.jpg"), "var/uploads", b"x")
        self.assertNotEqual(target.name, "photo.jpg")
        self.assertTrue(target.name.endswith(".jpg"))

    def test_two_uploads_of_same_original_name_do_not_collide(self):
        first = self.storage.store(_request(filename="photo.jpg"), "var/uploads", b"a")
        second = self.storage.store(_request(filename="photo.jpg"), "var/uploads", b"b")
        self.assertNotEqual(first.name, second.name)
        self.assertEqual(first.read_bytes(), b"a")
        self.assertEqual(second.read_bytes(), b"b")

    def test_count_and_size_on_missing_directory_is_zero(self):
        self.assertEqual(self.storage.count_and_size("var/uploads/does-not-exist"), (0, 0))

    def test_count_and_size_reflects_stored_files(self):
        self.storage.store(_request(), "var/uploads", b"1234567")
        self.storage.store(_request(), "var/uploads", b"12")
        count, total = self.storage.count_and_size("var/uploads")
        self.assertEqual(count, 2)
        self.assertEqual(total, 9)


if __name__ == "__main__":
    unittest.main()
