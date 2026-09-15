# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
import asyncio
import unittest

from omega_serv.domain.http.status_codes import HttpStatus
from omega_serv.infrastructure.server.http_parser import (
    HttpParseError,
    read_and_discard_body,
    read_request_head,
)


def _reader_from_bytes(data: bytes) -> asyncio.StreamReader:
    reader = asyncio.StreamReader()
    reader.feed_data(data)
    reader.feed_eof()
    return reader


class TestReadRequestHead(unittest.IsolatedAsyncioTestCase):
    async def test_valid_request_parses(self):
        raw = b"GET /index.html?x=1 HTTP/1.1\r\nHost: example.com\r\nUser-Agent: test\r\n\r\n"
        head = await read_request_head(_reader_from_bytes(raw), max_request_line_size=8192, max_header_size=16384)
        self.assertEqual(head.method, "GET")
        self.assertEqual(head.target, "/index.html?x=1")
        self.assertEqual(head.http_version, "HTTP/1.1")
        self.assertEqual(head.header("host"), "example.com")
        self.assertEqual(head.header("Host"), "example.com")
        self.assertEqual(head.header("user-agent"), "test")

    async def test_no_headers(self):
        raw = b"GET / HTTP/1.1\r\n\r\n"
        head = await read_request_head(_reader_from_bytes(raw), max_request_line_size=8192, max_header_size=16384)
        self.assertEqual(head.headers, ())

    async def test_request_line_too_long_rejected(self):
        raw = b"GET /" + b"a" * 100 + b" HTTP/1.1\r\n\r\n"
        with self.assertRaises(HttpParseError) as ctx:
            await read_request_head(_reader_from_bytes(raw), max_request_line_size=10, max_header_size=16384)
        self.assertEqual(ctx.exception.status, HttpStatus.URI_TOO_LONG)

    async def test_headers_too_large_rejected(self):
        raw = b"GET / HTTP/1.1\r\nX-Long: " + b"a" * 100 + b"\r\n\r\n"
        with self.assertRaises(HttpParseError) as ctx:
            await read_request_head(_reader_from_bytes(raw), max_request_line_size=8192, max_header_size=20)
        self.assertEqual(ctx.exception.status, HttpStatus.REQUEST_HEADER_FIELDS_TOO_LARGE)

    async def test_malformed_request_line_rejected(self):
        raw = b"GET /index.html\r\n\r\n"  # manque la version HTTP
        with self.assertRaises(HttpParseError) as ctx:
            await read_request_head(_reader_from_bytes(raw), max_request_line_size=8192, max_header_size=16384)
        self.assertEqual(ctx.exception.status, HttpStatus.BAD_REQUEST)

    async def test_header_without_colon_rejected(self):
        raw = b"GET / HTTP/1.1\r\nNotAHeader\r\n\r\n"
        with self.assertRaises(HttpParseError) as ctx:
            await read_request_head(_reader_from_bytes(raw), max_request_line_size=8192, max_header_size=16384)
        self.assertEqual(ctx.exception.status, HttpStatus.BAD_REQUEST)

    async def test_header_with_control_character_rejected(self):
        raw = b"GET / HTTP/1.1\r\nX-Evil: value\x01withcontrol\r\n\r\n"
        with self.assertRaises(HttpParseError) as ctx:
            await read_request_head(_reader_from_bytes(raw), max_request_line_size=8192, max_header_size=16384)
        self.assertEqual(ctx.exception.status, HttpStatus.BAD_REQUEST)

    async def test_obsolete_line_folding_rejected(self):
        raw = b"GET / HTTP/1.1\r\nX-Header: value\r\n continuation\r\n\r\n"
        with self.assertRaises(HttpParseError) as ctx:
            await read_request_head(_reader_from_bytes(raw), max_request_line_size=8192, max_header_size=16384)
        self.assertEqual(ctx.exception.status, HttpStatus.BAD_REQUEST)

    async def test_too_many_headers_rejected(self):
        many_headers = b"".join(f"X-{i}: v\r\n".encode("ascii") for i in range(200))
        raw = b"GET / HTTP/1.1\r\n" + many_headers + b"\r\n"
        with self.assertRaises(HttpParseError) as ctx:
            await read_request_head(_reader_from_bytes(raw), max_request_line_size=8192, max_header_size=1_048_000)
        self.assertEqual(ctx.exception.status, HttpStatus.REQUEST_HEADER_FIELDS_TOO_LARGE)

    async def test_duplicate_content_length_rejected(self):
        raw = b"POST / HTTP/1.1\r\nContent-Length: 5\r\nContent-Length: 5\r\n\r\nhello"
        with self.assertRaises(HttpParseError) as ctx:
            await read_request_head(_reader_from_bytes(raw), max_request_line_size=8192, max_header_size=16384)
        self.assertEqual(ctx.exception.status, HttpStatus.BAD_REQUEST)

    async def test_duplicate_content_length_rejected_even_with_different_values(self):
        raw = b"POST / HTTP/1.1\r\nContent-Length: 5\r\nContent-Length: 999\r\n\r\nhello"
        with self.assertRaises(HttpParseError) as ctx:
            await read_request_head(_reader_from_bytes(raw), max_request_line_size=8192, max_header_size=16384)
        self.assertEqual(ctx.exception.status, HttpStatus.BAD_REQUEST)

    async def test_expect_header_rejected(self):
        raw = b"POST / HTTP/1.1\r\nExpect: 100-continue\r\nContent-Length: 5\r\n\r\nhello"
        with self.assertRaises(HttpParseError) as ctx:
            await read_request_head(_reader_from_bytes(raw), max_request_line_size=8192, max_header_size=16384)
        self.assertEqual(ctx.exception.status, HttpStatus.EXPECTATION_FAILED)


class TestReadAndDiscardBody(unittest.IsolatedAsyncioTestCase):
    async def _parse(self, raw: bytes, max_request_size: int = 1024, capture_max_bytes: int = 0):
        reader = _reader_from_bytes(raw)
        head = await read_request_head(reader, max_request_line_size=8192, max_header_size=16384)
        consumed, captured = await read_and_discard_body(reader, head, max_request_size, capture_max_bytes)
        return consumed, captured, reader

    async def test_no_content_length_consumes_nothing(self):
        consumed, captured, _ = await self._parse(b"GET / HTTP/1.1\r\n\r\n")
        self.assertEqual(consumed, 0)
        self.assertEqual(captured, b"")

    async def test_content_length_body_is_consumed(self):
        body = b"field=value"
        raw = f"POST / HTTP/1.1\r\nContent-Length: {len(body)}\r\n\r\n".encode("ascii") + body
        consumed, captured, _reader = await self._parse(raw)
        self.assertEqual(consumed, len(body))
        self.assertEqual(captured, b"")  # capture_max_bytes=0 par defaut : rien retenu

    async def test_body_captured_up_to_configured_limit(self):
        body = b"0123456789"
        raw = f"POST / HTTP/1.1\r\nContent-Length: {len(body)}\r\n\r\n".encode("ascii") + body
        consumed, captured, _ = await self._parse(raw, capture_max_bytes=4)
        self.assertEqual(consumed, len(body))
        self.assertEqual(captured, b"0123")

    async def test_transfer_encoding_rejected(self):
        raw = b"POST / HTTP/1.1\r\nTransfer-Encoding: chunked\r\n\r\n"
        with self.assertRaises(HttpParseError) as ctx:
            await self._parse(raw)
        self.assertEqual(ctx.exception.status, HttpStatus.BAD_REQUEST)

    async def test_non_numeric_content_length_rejected(self):
        raw = b"POST / HTTP/1.1\r\nContent-Length: abc\r\n\r\n"
        with self.assertRaises(HttpParseError) as ctx:
            await self._parse(raw)
        self.assertEqual(ctx.exception.status, HttpStatus.BAD_REQUEST)

    async def test_content_length_exceeding_max_is_rejected(self):
        raw = b"POST / HTTP/1.1\r\nContent-Length: 2000\r\n\r\n" + b"x" * 2000
        with self.assertRaises(HttpParseError) as ctx:
            await self._parse(raw, max_request_size=1024)
        self.assertEqual(ctx.exception.status, HttpStatus.PAYLOAD_TOO_LARGE)


if __name__ == "__main__":
    unittest.main()
