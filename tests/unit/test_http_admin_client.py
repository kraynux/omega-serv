"""Vrai socket TCP loopback des deux cotes (jamais un double) - meme
discipline que test_serve_websocket_proxy.py : seule maniere honnete de
verifier qu'un appel HTTP reel part bien et revient correctement."""
import asyncio
import unittest

from omega_serv.infrastructure.proxy_admin.http_admin_client import call_admin_endpoint


class TestCallAdminEndpoint(unittest.IsolatedAsyncioTestCase):
    async def test_successful_json_response_is_parsed(self):
        async def handle(reader, writer):
            await reader.read(4096)
            body = b'{"hits": 3, "misses": 1}'
            writer.write(f"HTTP/1.1 200 OK\r\nContent-Length: {len(body)}\r\n\r\n".encode("latin-1") + body)
            await writer.drain()
            writer.close()

        server = await asyncio.start_server(handle, "127.0.0.1", 0)
        port = server.sockets[0].getsockname()[1]
        try:
            result = await call_admin_endpoint(port, "GET", "/.omega-serv-admin/cache-stats?zone=/api/")
            self.assertIsNotNone(result)
            status, body = result
            self.assertEqual(status, 200)
            self.assertEqual(body, {"hits": 3, "misses": 1})
        finally:
            server.close()
            await server.wait_closed()

    async def test_non_json_body_returns_none_body(self):
        async def handle(reader, writer):
            await reader.read(4096)
            writer.write(b"HTTP/1.1 403 Forbidden\r\nContent-Length: 0\r\n\r\n")
            await writer.drain()
            writer.close()

        server = await asyncio.start_server(handle, "127.0.0.1", 0)
        port = server.sockets[0].getsockname()[1]
        try:
            result = await call_admin_endpoint(port, "GET", "/.omega-serv-admin/health?zone=/api/")
            self.assertIsNotNone(result)
            status, body = result
            self.assertEqual(status, 403)
            self.assertIsNone(body)
        finally:
            server.close()
            await server.wait_closed()

    async def test_connection_refused_returns_none(self):
        dead_server = await asyncio.start_server(lambda r, w: None, "127.0.0.1", 0)
        port = dead_server.sockets[0].getsockname()[1]
        dead_server.close()
        await dead_server.wait_closed()

        result = await call_admin_endpoint(port, "GET", "/.omega-serv-admin/health?zone=/api/")
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
