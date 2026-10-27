#!/usr/bin/env python3
# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Prototype du mode « boost » (OMEGA-SERV_ETUDE_MODE_BOOST.md §6) - outil de developpement.

Deux modes :
- `--mode real` (defaut) : le vrai mode boost (`server.workers = N`), rate limit ACTIF avec une
  limite tres haute - chaque requete passe par les compteurs partages (cout compris) ;
- `--mode proto` : prototype d'origine, N copies independantes de `omega-serv serve` sur le meme
  port (SO_REUSEPORT via un sitecustomize de mesure), compteurs NON partages.
Plusieurs processus clients (un seul client Python plafonne lui-meme vers 1 000 req/s). Petit
fichier, WAF actif.

  .venv/bin/python tools/bench/workers_proto.py [--mode real|proto] [--workers 1 2 4] [--clients 3] [--duration 8]
"""
import argparse
import asyncio
import json
import multiprocessing
import os
import shutil
import socket
import subprocess
import tempfile
import time
from pathlib import Path

SERV = Path(__file__).resolve().parents[2]
PORT = 18911
_SITECUSTOMIZE = '''import asyncio
_original = asyncio.start_server


async def _start_server(*args, **kwargs):
    kwargs.setdefault("reuse_port", True)
    return await _original(*args, **kwargs)


asyncio.start_server = _start_server
'''


def make_root(workers: int = 1) -> Path:
    root = Path(tempfile.mkdtemp(prefix="boost-"))
    shutil.copytree(SERV / "src", root / "src", ignore=shutil.ignore_patterns("*.bak", "__pycache__"))
    (root / "webroot").mkdir()
    (root / "webroot/small.html").write_bytes(b"x" * 1024)
    rules = root / "secure/waf/rules"
    rules.mkdir(parents=True)
    for pack in (SERV / "secure/waf/rules").glob("*.json"):
        shutil.copy(pack, rules / pack.name)
    (root / "config").mkdir()
    (root / "config/omega-serve.json").write_text(json.dumps({
        "version": 1, "profile": "standard",
        "server": {"bind": "127.0.0.1", "port": PORT, "max_connections": 1024, "max_keepalive_requests": 100000,
                   "workers": workers},
        "options": {"waf": {"enabled": True, "mode": "block",
                            "rules": {"paths": [f"secure/waf/rules/{p.name}" for p in rules.glob("*.json")]},
                            "rate_limit": {"enabled": True,
                                           "global": {"requests": 10_000_000, "window_seconds": 60}}}},
    }))
    (root / "boostsite").mkdir()
    (root / "boostsite/sitecustomize.py").write_text(_SITECUSTOMIZE)
    return root


async def _connection(deadline: float, latencies: list[float]) -> int:
    reader, writer = await asyncio.open_connection("127.0.0.1", PORT)
    request = b"GET /small.html HTTP/1.1\r\nHost: b\r\nUser-Agent: Mozilla/5.0 bench\r\n\r\n"
    count = 0
    try:
        while time.perf_counter() < deadline:
            started = time.perf_counter()
            writer.write(request)
            await writer.drain()
            await reader.readline()
            length = 0
            while (line := await reader.readline()) not in (b"\r\n", b""):
                if line.lower().startswith(b"content-length:"):
                    length = int(line.split(b":")[1])
            await reader.readexactly(length)
            latencies.append(time.perf_counter() - started)
            count += 1
    finally:
        writer.close()
    return count


def _client(args: tuple[float, int, multiprocessing.Queue]) -> None:
    deadline, connections, queue = args

    async def run() -> None:
        latencies: list[float] = []
        total = sum(await asyncio.gather(*(_connection(deadline, latencies) for _ in range(connections))))
        queue.put((total, latencies))

    asyncio.run(run())


def measure(workers: int, clients: int, duration: float, mode: str) -> tuple[float, float, float]:
    real = mode == "real"
    root = make_root(workers if real else 1)
    path = str(root / "src") if real else f"{root / 'boostsite'}{os.pathsep}{root / 'src'}"
    env = dict(os.environ, PYTHONPATH=path)
    processes = [
        subprocess.Popen(
            [str(SERV / ".venv/bin/python"), "-m", "omega_serv", "--config", str(root / "config/omega-serve.json"), "serve"],
            cwd=root, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True,
        )
        for _ in range(1 if real else workers)
    ]
    try:
        for _ in range(100):
            try:
                socket.create_connection(("127.0.0.1", PORT), 0.2).close()
                break
            except OSError:
                time.sleep(0.1)
        time.sleep(1.0 + 0.3 * workers)  # chaque worker charge ses regles WAF
        queue: multiprocessing.Queue = multiprocessing.Queue()
        deadline = time.perf_counter() + duration
        started = time.perf_counter()
        jobs = [multiprocessing.Process(target=_client, args=((deadline, 16, queue),)) for _ in range(clients)]
        for job in jobs:
            job.start()
        results = [queue.get() for _ in jobs]
        for job in jobs:
            job.join()
        elapsed = time.perf_counter() - started
        total = sum(r[0] for r in results)
        latencies = sorted(lat for r in results for lat in r[1])
        p50 = latencies[len(latencies) // 2] * 1000
        p99 = latencies[int(len(latencies) * 0.99)] * 1000
        return total / elapsed, p50, p99
    finally:
        for process in processes:
            process.terminate()
        for process in processes:
            process.wait(30)
        shutil.rmtree(root, ignore_errors=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workers", type=int, nargs="+", default=[1, 2, 4])
    parser.add_argument("--clients", type=int, default=3)
    parser.add_argument("--duration", type=float, default=8)
    parser.add_argument("--mode", choices=("real", "proto"), default="real")
    args = parser.parse_args()
    print(f"mode : {args.mode}  cœurs : {os.cpu_count()}  processus clients : {args.clients}  "
          f"duree : {args.duration}s (WAF + rate limit actifs, 1 Ko)")
    print(f"{'workers':>8}{'req/s':>10}{'p50 ms':>9}{'p99 ms':>9}")
    for workers in args.workers:
        rps, p50, p99 = measure(workers, args.clients, args.duration, args.mode)
        print(f"{workers:>8}{rps:>10.0f}{p50:>9.1f}{p99:>9.1f}")


if __name__ == "__main__":
    main()
