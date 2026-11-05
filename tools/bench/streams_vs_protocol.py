#!/usr/bin/env python3
# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Plafond de gain « asyncio.Protocol au lieu de StreamReader/StreamWriter » (plan moteur C++, lot 0,
2026-11-02) - outil de developpement.

Deux mini-serveurs HTTP/1.1 keep-alive, SANS aucune logique omega-serv (ni WAF, ni routage, ni journal),
servent la meme reponse de 1 Ko : l'ecart entre les deux est le gain MAXIMAL qu'apporterait la reecriture de
la couche connexion d'omega-serv - le reste du traitement d'une requete ne change pas.

  python3 tools/bench/streams_vs_protocol.py streams 18960   # puis : oha -z 10s -c 32 http://127.0.0.1:18960/
  python3 tools/bench/streams_vs_protocol.py protocol 18961
"""
import asyncio
import sys

BODY = b"x" * 1024
RESPONSE = (
    b"HTTP/1.1 200 OK\r\nContent-Type: text/html\r\nContent-Length: 1024\r\nConnection: keep-alive\r\n\r\n" + BODY
)


async def _streams_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    try:
        while True:
            head = await reader.readuntil(b"\r\n\r\n")
            if not head:
                break
            writer.write(RESPONSE)
            await writer.drain()
    except (asyncio.IncompleteReadError, ConnectionError):
        pass
    finally:
        writer.close()


class _Http(asyncio.Protocol):
    def connection_made(self, transport: asyncio.BaseTransport) -> None:
        self.transport = transport  # type: ignore[assignment]
        self.buffer = b""

    def data_received(self, data: bytes) -> None:
        self.buffer += data
        while True:
            end = self.buffer.find(b"\r\n\r\n")
            if end < 0:
                return
            self.buffer = self.buffer[end + 4:]
            self.transport.write(RESPONSE)  # type: ignore[attr-defined]


async def main(kind: str, port: int) -> None:
    if kind == "streams":
        server = await asyncio.start_server(_streams_client, "127.0.0.1", port, backlog=128)
    else:
        server = await asyncio.get_running_loop().create_server(_Http, "127.0.0.1", port, backlog=128)
    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1], int(sys.argv[2])))
