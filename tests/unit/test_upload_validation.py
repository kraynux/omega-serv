# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
import unittest

from omega_serv.domain.routing.upload_zone import UploadPolicy
from omega_serv.domain.upload.entities import UploadRequest
from omega_serv.domain.upload.validation import validate_filename, validate_upload


class TestValidateFilename(unittest.TestCase):
    def test_valid_filename_passes(self):
        self.assertIsNone(validate_filename("photo.jpg"))

    def test_empty_filename_rejected(self):
        self.assertIsNotNone(validate_filename(""))

    def test_dot_and_dotdot_rejected(self):
        self.assertIsNotNone(validate_filename("."))
        self.assertIsNotNone(validate_filename(".."))

    def test_path_separator_rejected(self):
        self.assertIsNotNone(validate_filename("../../etc/passwd"))
        self.assertIsNotNone(validate_filename("sub/dir.txt"))

    def test_too_long_rejected(self):
        self.assertIsNotNone(validate_filename("a" * 256 + ".txt"))

    def test_control_character_rejected(self):
        self.assertIsNotNone(validate_filename("photo\x00.jpg"))


class TestValidateUpload(unittest.TestCase):
    def _request(self, **overrides) -> UploadRequest:
        defaults = {
            "zone_prefix": "/upload/", "filename": "photo.jpg", "content_type": "image/jpeg",
            "size": 1024, "source_ip": "203.0.113.10",
        }
        defaults.update(overrides)
        return UploadRequest(**defaults)

    def test_valid_upload_passes(self):
        policy = UploadPolicy(max_file_size_bytes=2048, allowed_extensions=(".jpg",), allowed_content_types=("image/jpeg",))
        self.assertIsNone(validate_upload(self._request(), policy))

    def test_oversized_file_rejected(self):
        policy = UploadPolicy(max_file_size_bytes=512)
        self.assertIsNotNone(validate_upload(self._request(size=1024), policy))

    def test_disallowed_extension_rejected(self):
        policy = UploadPolicy(allowed_extensions=(".png",))
        self.assertIsNotNone(validate_upload(self._request(filename="photo.jpg"), policy))

    def test_disallowed_content_type_rejected(self):
        policy = UploadPolicy(allowed_content_types=("image/png",))
        self.assertIsNotNone(validate_upload(self._request(content_type="image/jpeg"), policy))

    def test_empty_allowed_lists_mean_no_restriction(self):
        policy = UploadPolicy(allowed_extensions=(), allowed_content_types=())
        self.assertIsNone(validate_upload(self._request(), policy))


if __name__ == "__main__":
    unittest.main()
