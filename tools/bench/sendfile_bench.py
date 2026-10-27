#!/usr/bin/env python3
# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Plafond theorique gros fichier : lecture complete + write contre loop.sendfile, sur un
mini-serveur asyncio nu (aucun code omega-serv). Outil de developpement.

  .venv/bin/python tools/bench/sendfile_bench.py
"""
import asyncio
import os
import tempfile
import time

SIZE = 5 * 1024 * 1024
path = os.path.join(tempfile.mkdtemp(), "large.bin")
with open(path, "wb") as out:
    out.write(os.urandom(SIZE))
HEAD = f"HTTP/1.1 200 OK\r\nContent-Length: {SIZE}\r\nContent-Type: application/octet-stream\r\n\r\n".encode()


async def handler(reader, writer, mode):
    loop = asyncio.get_running_loop()
    try:
        while True:
            line = await reader.readline()
            if not line:
                break
            while (await reader.readline()) not in (b"\r\n", b""):
                pass
            writer.write(HEAD)
            if mode == "read":
                with open(path, "rb") as f:  # noqa: ASYNC230 - c'est precisement la lecture bloquante mesuree
                    writer.write(f.read())
                await writer.drain()
            else:
                await writer.drain()
                with open(path, "rb") as f:  # noqa: ASYNC230 - ouverture seule, comme le serveur
                    await loop.sendfile(writer.transport, f)
    finally:
        writer.close()


async def client(port, deadline):
    r, w = await asyncio.open_connection("127.0.0.1", port)
    n = 0
    while time.perf_counter() < deadline:
        w.write(b"GET /large.bin HTTP/1.1\r\nHost: b\r\n\r\n"); await w.drain()
        await r.readline()
        while (await r.readline()) != b"\r\n":
            pass
        await r.readexactly(SIZE)
        n += 1
    w.close()
    return n


async def main():
    for mode in ("read", "sendfile"):
        server = await asyncio.start_server(lambda r, w, mode=mode: handler(r, w, mode), "127.0.0.1", 0)
        port = server.sockets[0].getsockname()[1]
        t0 = time.perf_counter(); deadline = t0 + 5
        total = sum(await asyncio.gather(*(client(port, deadline) for _ in range(8))))
        elapsed = time.perf_counter() - t0
        print(f"{mode:<9} {total/elapsed:6.1f} req/s  {total*SIZE/elapsed/1e6:7.1f} Mo/s")
        server.close()

asyncio.run(main())
