# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Serveur de l'administration web : une erreur imprevue dans une page donne une reponse 500, jamais une connexion
fermee sans reponse (essai de l'auteur du 2026-11-17 : ERR_EMPTY_RESPONSE dans le navigateur)."""
from __future__ import annotations

import asyncio
import unittest

from omega_serv.application.admin_web.responses import AdminResponse
from omega_serv.infrastructure.admin_web.server import AdminWebServer


class TestServer(unittest.TestCase):
    def test_a_failing_page_answers_500_and_the_server_keeps_serving(self):
        async def scenario():
            async def responder(request):
                if request.target == "/plante":
                    raise PermissionError(13, "Permission denied")
                return AdminResponse(200, "OK", (), b"ok")
            server = AdminWebServer("127.0.0.1", 0, None, responder)
            await server.start()
            port = server._server.sockets[0].getsockname()[1]
            answers = []
            for target in ("/plante", "/"):
                reader, writer = await asyncio.open_connection("127.0.0.1", port)
                writer.write(f"GET {target} HTTP/1.1\r\nHost: x\r\n\r\n".encode())
                await writer.drain()
                answers.append(await reader.read())
                writer.close()
            await server.close()
            return answers
        with self.assertLogs("omega_serv.admin_web", level="ERROR"):
            failed, ok = asyncio.run(scenario())
        self.assertTrue(failed.startswith(b"HTTP/1.1 500 "))
        self.assertTrue(ok.startswith(b"HTTP/1.1 200 ") and ok.endswith(b"ok"))


if __name__ == "__main__":
    unittest.main()
