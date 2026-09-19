import unittest

from omega_serv.domain.upload.multipart import extract_boundary, parse_multipart


class TestExtractBoundary(unittest.TestCase):
    def test_extracts_quoted_boundary(self):
        self.assertEqual(extract_boundary('multipart/form-data; boundary="abc123"'), "abc123")

    def test_extracts_unquoted_boundary(self):
        self.assertEqual(extract_boundary("multipart/form-data; boundary=abc123"), "abc123")

    def test_non_multipart_returns_none(self):
        self.assertIsNone(extract_boundary("application/json"))

    def test_multipart_without_boundary_returns_none(self):
        self.assertIsNone(extract_boundary("multipart/form-data"))


class TestParseMultipart(unittest.TestCase):
    def test_parses_single_file_part_without_type_error(self):
        boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
        body = (
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="file"; filename="photo.jpg"\r\n'
            "Content-Type: image/jpeg\r\n"
            "\r\n"
            "BINARYDATA"
            f"\r\n--{boundary}--\r\n"
        ).encode()

        parts = parse_multipart(body, boundary)

        self.assertEqual(len(parts), 1)
        self.assertEqual(parts[0].filename, "photo.jpg")
        self.assertEqual(parts[0].field_content_type, "image/jpeg")
        self.assertEqual(parts[0].content, b"BINARYDATA")

    def test_parses_multiple_parts(self):
        boundary = "XYZ"
        body = (
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="description"\r\n'
            "\r\n"
            "hello"
            f"\r\n--{boundary}\r\n"
            'Content-Disposition: form-data; name="file"; filename="a.txt"\r\n'
            "Content-Type: text/plain\r\n"
            "\r\n"
            "content"
            f"\r\n--{boundary}--\r\n"
        ).encode()

        parts = parse_multipart(body, boundary)

        self.assertEqual(len(parts), 2)
        self.assertIsNone(parts[0].filename)
        self.assertEqual(parts[0].content, b"hello")
        self.assertEqual(parts[1].filename, "a.txt")
        self.assertEqual(parts[1].content, b"content")

    def test_binary_content_with_non_utf8_bytes_does_not_raise(self):
        boundary = "B"
        body = (
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="file"; filename="a.bin"\r\n'
            "\r\n"
        ).encode() + b"\xff\xfe\x00\x01" + f"\r\n--{boundary}--\r\n".encode()

        parts = parse_multipart(body, boundary)

        self.assertEqual(len(parts), 1)
        self.assertEqual(parts[0].content, b"\xff\xfe\x00\x01")


if __name__ == "__main__":
    unittest.main()
