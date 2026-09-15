# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
import json
import unittest
from datetime import datetime, timezone
from pathlib import Path

from omega_serv.application.upload.handle_upload import handle_upload
from omega_serv.domain.http.headers import HttpHeaders
from omega_serv.domain.http.request import HttpRequest
from omega_serv.domain.routing.upload_zone import UploadPolicy, UploadZoneRule
from omega_serv.domain.routing.zone_resolver import Zone


class _FakeClock:
    def now(self):
        return datetime(2026, 1, 1, tzinfo=timezone.utc)


class _FakeStorage:
    def __init__(self, existing_count=0, existing_total=0):
        self._existing_count = existing_count
        self._existing_total = existing_total
        self.stored = []

    def store(self, request, storage_relative_path, content):
        self.stored.append((storage_relative_path, content))
        return Path("/var/uploads/generated-name.jpg")

    def count_and_size(self, storage_relative_path):
        return self._existing_count, self._existing_total


class _FakeLogger:
    def __init__(self):
        self.lines = []

    def append_line(self, path, line):
        self.lines.append((path, line))


_BOUNDARY = "----test"


def _multipart_body(filename="photo.jpg", content=b"BINARY", content_type="image/jpeg"):
    return (
        f"--{_BOUNDARY}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
        f"Content-Type: {content_type}\r\n"
        "\r\n"
    ).encode() + content + f"\r\n--{_BOUNDARY}--\r\n".encode()


def _request(content_type_header=f"multipart/form-data; boundary={_BOUNDARY}") -> HttpRequest:
    return HttpRequest(
        request_id="r1", remote_ip="203.0.113.10", peer_ip="203.0.113.10", method="POST",
        path="/upload/", raw_path="/upload/", query="",
        headers=HttpHeaders.from_pairs([("Content-Type", content_type_header)]),
        body=None, content_length=None, is_tls=False,
    )


def _zone(**policy_overrides) -> Zone[UploadZoneRule]:
    policy = UploadPolicy(**policy_overrides)
    rule = UploadZoneRule(url_prefix="/upload/", storage_path="var/uploads/public", policy=policy)
    return Zone("/upload/", rule)


class TestHandleUpload(unittest.TestCase):
    def test_valid_upload_is_stored_and_returns_201(self):
        storage = _FakeStorage()
        response = handle_upload(_request(), _zone(), _multipart_body(), storage, _FakeClock())
        self.assertEqual(response.status, 201)
        self.assertEqual(len(storage.stored), 1)
        payload = json.loads(response.body)
        self.assertEqual(payload["filename"], "generated-name.jpg")

    def test_missing_boundary_returns_400(self):
        response = handle_upload(
            _request(content_type_header="multipart/form-data"), _zone(), b"", _FakeStorage(), _FakeClock(),
        )
        self.assertEqual(response.status, 400)

    def test_non_multipart_content_type_returns_400(self):
        response = handle_upload(
            _request(content_type_header="application/json"), _zone(), b"{}", _FakeStorage(), _FakeClock(),
        )
        self.assertEqual(response.status, 400)

    def test_body_without_file_part_returns_400(self):
        body = (
            f"--{_BOUNDARY}\r\n"
            'Content-Disposition: form-data; name="description"\r\n\r\n'
            "no file here"
            f"\r\n--{_BOUNDARY}--\r\n"
        ).encode()
        response = handle_upload(_request(), _zone(), body, _FakeStorage(), _FakeClock())
        self.assertEqual(response.status, 400)

    def test_oversized_file_rejected_before_storage(self):
        storage = _FakeStorage()
        response = handle_upload(
            _request(), _zone(max_file_size_bytes=2), _multipart_body(content=b"toobig"), storage, _FakeClock(),
        )
        self.assertEqual(response.status, 400)
        self.assertEqual(storage.stored, [])

    def test_disallowed_extension_rejected(self):
        storage = _FakeStorage()
        response = handle_upload(
            _request(), _zone(allowed_extensions=(".png",)), _multipart_body(filename="photo.jpg"),
            storage, _FakeClock(),
        )
        self.assertEqual(response.status, 400)
        self.assertEqual(storage.stored, [])

    def test_file_count_quota_exceeded_returns_507(self):
        storage = _FakeStorage(existing_count=5)
        response = handle_upload(
            _request(), _zone(max_files_per_zone=5), _multipart_body(), storage, _FakeClock(),
        )
        self.assertEqual(response.status, 507)
        self.assertEqual(storage.stored, [])

    def test_total_bytes_quota_exceeded_returns_507(self):
        storage = _FakeStorage(existing_total=100)
        response = handle_upload(
            _request(), _zone(max_total_bytes_per_zone=100), _multipart_body(content=b"x"), storage, _FakeClock(),
        )
        self.assertEqual(response.status, 507)
        self.assertEqual(storage.stored, [])

    def test_logs_accepted_upload_when_logger_provided(self):
        logger = _FakeLogger()
        handle_upload(
            _request(), _zone(), _multipart_body(), _FakeStorage(), _FakeClock(),
            logger=logger, upload_log_path=Path("var/log/uploads.log"),
        )
        self.assertEqual(len(logger.lines), 1)
        path, line = logger.lines[0]
        self.assertEqual(path, Path("var/log/uploads.log"))
        record = json.loads(line)
        self.assertTrue(record["accepted"])
        self.assertEqual(record["filename_original"], "photo.jpg")

    def test_logs_rejected_upload_when_logger_provided(self):
        logger = _FakeLogger()
        handle_upload(
            _request(), _zone(max_file_size_bytes=1), _multipart_body(content=b"toobig"), _FakeStorage(),
            _FakeClock(), logger=logger, upload_log_path=Path("var/log/uploads.log"),
        )
        self.assertEqual(len(logger.lines), 1)
        record = json.loads(logger.lines[0][1])
        self.assertFalse(record["accepted"])
        self.assertIsNotNone(record["reason_rejected"])

    def test_no_logger_provided_does_not_raise(self):
        response = handle_upload(_request(), _zone(), _multipart_body(), _FakeStorage(), _FakeClock())
        self.assertEqual(response.status, 201)


if __name__ == "__main__":
    unittest.main()
