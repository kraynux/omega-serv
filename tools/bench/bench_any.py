#!/usr/bin/env python3
# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Client de charge seul, pointe sur N'IMPORTE QUEL serveur HTTP deja lance (omega-serv, nginx,
Caddy, Apache, lighttpd...) - outil de developpement.

Meme client que bench.py (asyncio, keep-alive, HTTP/1.1, plusieurs processus clients), pour
comparer des serveurs sur LA MEME machine avec LE MEME client et LES MEMES fichiers. Ne lance
rien : chaque serveur est configure et demarre a part, sur le meme webroot.

Fichiers attendus dans le webroot du serveur mesure (`--make-files DOSSIER` les cree) :
small.html (1 Ko), medium.png (100 Ko), large.bin (5 Mo).

  python3 tools/bench/bench_any.py --make-files /srv/bench-webroot
  python3 tools/bench/bench_any.py --port 8080 [--host 127.0.0.1] [--clients 3] [--concurrency 32] [--duration 10]

Le client consomme lui-meme du CPU : sur une machine a peu de cœurs, les chiffres sont des
planchers communs a tous les serveurs mesures, pas des maxima absolus. Repeter 3 fois au moins.
"""
import argparse
import asyncio
import multiprocessing
import os
import time
from pathlib import Path

FILES = (("/small.html", 1024), ("/medium.png", 100 * 1024), ("/large.bin", 5 * 1024 * 1024))


def make_files(folder: Path) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "small.html").write_bytes(b"x" * 1024)
    (folder / "medium.png").write_bytes(os.urandom(100 * 1024))
    (folder / "large.bin").write_bytes(os.urandom(5 * 1024 * 1024))
    print(f"fichiers crees dans {folder}")


async def _connection(host: str, port: int, path: str, deadline: float, latencies: list[float], errors: list[bytes]) -> int:
    reader, writer = await asyncio.open_connection(host, port)
    request = f"GET {path} HTTP/1.1\r\nHost: {host}\r\nUser-Agent: Mozilla/5.0 bench\r\n\r\n".encode()
    count = 0
    try:
        while time.perf_counter() < deadline:
            started = time.perf_counter()
            writer.write(request)
            await writer.drain()
            status = await reader.readline()
            length = 0
            while (line := await reader.readline()) not in (b"\r\n", b""):
                if line.lower().startswith(b"content-length:"):
                    length = int(line.split(b":")[1])
            await reader.readexactly(length)
            latencies.append(time.perf_counter() - started)
            if not status.startswith(b"HTTP/1.1 200"):
                errors.append(status)
            count += 1
    finally:
        writer.close()
    return count


def _client(args: tuple) -> None:
    host, port, path, deadline, connections, queue = args

    async def run() -> None:
        latencies: list[float] = []
        errors: list[bytes] = []
        try:
            total = sum(await asyncio.gather(*(
                _connection(host, port, path, deadline, latencies, errors) for _ in range(connections))))
        except OSError as error:  # serveur absent ou connexion coupee : ne jamais bloquer le parent
            queue.put((0, latencies, len(errors) + 1, str(error)))
            return
        queue.put((total, latencies, len(errors), ""))

    asyncio.run(run())


def measure(host: str, port: int, path: str, clients: int, concurrency: int, duration: float):
    queue: multiprocessing.Queue = multiprocessing.Queue()
    per_client = max(1, concurrency // clients)
    deadline = time.perf_counter() + duration
    started = time.perf_counter()
    jobs = [multiprocessing.Process(target=_client, args=((host, port, path, deadline, per_client, queue),))
            for _ in range(clients)]
    for job in jobs:
        job.start()
    results = [queue.get() for _ in jobs]
    for job in jobs:
        job.join()
    elapsed = time.perf_counter() - started
    if failure := next((r[3] for r in results if r[3]), ""):
        raise SystemExit(f"echec de connexion : {failure}")
    latencies = sorted(lat for r in results for lat in r[1])
    q = lambda p: latencies[min(len(latencies) - 1, int(p * len(latencies)))] * 1000
    return sum(r[0] for r in results) / elapsed, q(0.5), q(0.99), sum(r[2] for r in results)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int)
    parser.add_argument("--clients", type=int, default=3)
    parser.add_argument("--concurrency", type=int, default=32)
    parser.add_argument("--duration", type=float, default=10)
    parser.add_argument("--make-files", type=Path)
    args = parser.parse_args()
    if args.make_files:
        make_files(args.make_files)
        return
    if args.port is None:
        parser.error("--port est obligatoire")
    print(f"{args.host}:{args.port}  clients={args.clients}  concurrence={args.concurrency}  duree={args.duration}s")
    print(f"{'fichier':<14}{'req/s':>9}{'Mo/s':>9}{'p50 ms':>9}{'p99 ms':>9}{'non-200':>9}")
    for path, size in FILES:
        concurrency = args.concurrency if size < 1_000_000 else min(args.concurrency, 8)
        rps, p50, p99, errors = measure(args.host, args.port, path, args.clients, concurrency, args.duration)
        print(f"{path:<14}{rps:>9.0f}{rps * size / 1e6:>9.1f}{p50:>9.1f}{p99:>9.1f}{errors:>9}")


if __name__ == "__main__":
    main()
