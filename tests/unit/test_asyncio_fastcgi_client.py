# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Teste l'implementation asyncio reelle contre un faux serveur FastCGI
(vrai socket Unix, vrais octets sur le fil) - meme discipline que les
autres tests d'infrastructure (I/O reelle, pas de mock du transport)."""
import asyncio
import struct
import tempfile
import unittest
from pathlib import Path

from omega_serv.domain.http.fastcgi_protocol import (
    FCGI_BEGIN_REQUEST,
    FCGI_END_REQUEST,
    FCGI_PARAMS,
    FCGI_REQUEST_COMPLETE,
    FCGI_STDIN,
    FCGI_STDOUT,
    FastCgiConnectionError,
    decode_record_header,
    encode_record,
)
from omega_serv.infrastructure.fastcgi.asyncio_fastcgi_client import AsyncioFastCgiClient


async def _serve_one_request(socket_path: Path, response_body: bytes, delay: float = 0.0):
    received_stdin = bytearray()

    async def handle(reader, writer):
        request_id = 1
        params_done = False
        stdin_done = False
        while not (params_done and stdin_done):
            header_bytes = await reader.readexactly(8)
            header = decode_record_header(header_bytes)
            content = await reader.readexactly(header.content_length) if header.content_length else b""
            if header.padding_length:
                await reader.readexactly(header.padding_length)
            if header.type == FCGI_BEGIN_REQUEST:
                request_id = header.request_id
            elif header.type == FCGI_PARAMS:
                if not content:
                    params_done = True
            elif header.type == FCGI_STDIN:
                if not content:
                    stdin_done = True
                else:
                    received_stdin.extend(content)

        if delay:
            await asyncio.sleep(delay)

        writer.write(encode_record(FCGI_STDOUT, request_id, response_body))
        writer.write(encode_record(FCGI_STDOUT, request_id, b""))
        end_body = struct.pack("!IB3x", 0, FCGI_REQUEST_COMPLETE)
        writer.write(encode_record(FCGI_END_REQUEST, request_id, end_body))
        await writer.drain()
        writer.close()
        await writer.wait_closed()
        server.close()

    server = await asyncio.start_unix_server(handle, path=str(socket_path))
    async with server:
        await server.serve_forever()


class TestAsyncioFastCgiClient(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.socket_path = Path(self._tmp.name) / "test.sock"

    async def asyncTearDown(self):
        self._tmp.cleanup()

    async def _run_with_fake_server(self, response_body: bytes, coro_factory, delay: float = 0.0):
        server_task = asyncio.create_task(_serve_one_request(self.socket_path, response_body, delay))
        await asyncio.sleep(0.05)  # laisser le serveur ouvrir le socket
        try:
            return await coro_factory()
        finally:
            server_task.cancel()
            try:
                await server_task
            except (asyncio.CancelledError, Exception):  # noqa: BLE001, S110
                # Meme discipline que test_fastcgi_server.py : nettoyage
                # best-effort d'une tache qu'on vient d'annuler nous-memes,
                # jamais un echec de test a cause de ca.
                pass

    async def test_receives_parsed_response(self):
        client = AsyncioFastCgiClient()
        result = await self._run_with_fake_server(
            b"Content-Type: text/html\r\n\r\n<h1>hello</h1>",
            lambda: client.send_request(self.socket_path, {"REQUEST_METHOD": "GET"}, b"", 2.0, 2.0),
        )
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.body, b"<h1>hello</h1>")
        self.assertIn(("Content-Type", "text/html"), result.headers)

    async def test_status_header_forwarded(self):
        client = AsyncioFastCgiClient()
        result = await self._run_with_fake_server(
            b"Status: 404 Not Found\r\n\r\nnope",
            lambda: client.send_request(self.socket_path, {}, b"", 2.0, 2.0),
        )
        self.assertEqual(result.status_code, 404)

    async def test_connect_to_missing_socket_raises_connection_error(self):
        client = AsyncioFastCgiClient()
        with self.assertRaises(FastCgiConnectionError):
            await client.send_request(self.socket_path, {}, b"", 1.0, 1.0)

    async def test_read_timeout_raises_connection_error(self):
        client = AsyncioFastCgiClient()
        with self.assertRaises(FastCgiConnectionError):
            await self._run_with_fake_server(
                b"body",
                lambda: client.send_request(self.socket_path, {}, b"", 2.0, 0.05),
                delay=1.0,
            )


if __name__ == "__main__":
    unittest.main()
