#!/usr/bin/env python3
# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Mesure de debit et de latence (OMEGA-SERV_ETUDE_PERFORMANCE.md) - outil de developpement.

Lance un vrai `omega-serv serve` (copie de src/ dans un dossier temporaire) et le charge avec un
client asyncio keep-alive sur 3 fichiers (1 Ko, 100 Ko, 5 Mo). Le client tourne sur la meme
machine : chiffres a comparer entre eux (avant/apres), jamais a publier tels quels. Bruit ~10 % :
repeter chaque mesure au moins 3 fois.

  .venv/bin/python tools/bench/bench.py [--waf] [--duration S] [--concurrency C]
  BENCH_ONLY=/small.html  -> un seul fichier ;  BENCH_PROFILE=fichier.prof -> profil cProfile du serveur
  BENCH_EXTRA_PATH=dossier -> ajoute au PYTHONPATH du serveur (ex. essai d'uvloop via sitecustomize)
  BENCH_SRC=dossier/src -> mesure un autre code source (ex. une version precedente extraite de son archive)
"""
import argparse
import asyncio
import json
import os
import shutil
import socket
import subprocess
import tempfile
import time
from pathlib import Path

SERV = Path(__file__).resolve().parents[2]
SRC = Path(os.environ.get("BENCH_SRC") or SERV / "src")
PORT = 18901


def make_root(waf: bool) -> Path:
    root = Path(tempfile.mkdtemp(prefix="bench-"))
    shutil.copytree(SRC, root / "src", ignore=shutil.ignore_patterns("*.bak", "__pycache__"))
    web = root / "webroot"; web.mkdir()
    (web / "small.html").write_bytes(b"x" * 1024)
    (web / "medium.png").write_bytes(os.urandom(100 * 1024))
    (web / "large.bin").write_bytes(os.urandom(5 * 1024 * 1024))
    (root / "config").mkdir()
    options = {}
    if waf:
        rules = root / "secure/waf/rules"; rules.mkdir(parents=True)
        for f in (SERV / "secure/waf/rules").glob("*.json"):
            shutil.copy(f, rules / f.name)
        options["waf"] = {"enabled": True, "mode": "block",
                          "rules": {"paths": [f"secure/waf/rules/{f.name}" for f in rules.glob("*.json")]},
                          "rate_limit": {"enabled": False}}
    cfg = {"version": 1, "profile": "standard",
           "server": {"bind": "127.0.0.1", "port": PORT, "max_connections": 1024, "max_keepalive_requests": 100000},
           "logs": {}, "options": options}
    (root / "config/omega-serve.json").write_text(json.dumps(cfg))
    return root


async def worker(path, deadline, lat, size_check):
    r, w = await asyncio.open_connection("127.0.0.1", PORT)
    req = f"GET {path} HTTP/1.1\r\nHost: b\r\nUser-Agent: Mozilla/5.0 bench\r\n\r\n".encode()
    n = 0
    try:
        while time.perf_counter() < deadline:
            t0 = time.perf_counter()
            w.write(req); await w.drain()
            status = await r.readline()
            length = 0
            while True:
                line = await r.readline()
                if line in (b"\r\n", b""):
                    break
                if line.lower().startswith(b"content-length:"):
                    length = int(line.split(b":")[1])
            await r.readexactly(length)
            lat.append(time.perf_counter() - t0)
            if not status.startswith(b"HTTP/1.1 200"):
                size_check.append(status)
            n += 1
    finally:
        w.close()
    return n


async def run(path, duration, conc):
    lat, errors = [], []
    deadline = time.perf_counter() + duration
    t0 = time.perf_counter()
    counts = await asyncio.gather(*(worker(path, deadline, lat, errors) for _ in range(conc)))
    elapsed = time.perf_counter() - t0
    lat.sort()
    q = lambda p: lat[min(len(lat) - 1, int(p * len(lat)))] * 1000
    return sum(counts) / elapsed, q(0.5), q(0.95), q(0.99), len(errors)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--waf", action="store_true")
    ap.add_argument("--duration", type=float, default=8)
    ap.add_argument("--concurrency", type=int, default=32)
    a = ap.parse_args()
    root = make_root(a.waf)
    extra = os.environ.get("BENCH_EXTRA_PATH")
    env = dict(os.environ, PYTHONPATH=os.pathsep.join(filter(None, [extra, str(root / "src")])))
    prof = ["-m", "cProfile", "-o", os.environ["BENCH_PROFILE"]] if os.environ.get("BENCH_PROFILE") else []
    proc = subprocess.Popen([str(SERV / ".venv/bin/python"), *prof, "-m", "omega_serv", "--config",
                             str(root / "config/omega-serve.json"), "serve"], cwd=root, env=env,
                            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    try:
        for _ in range(100):
            try:
                socket.create_connection(("127.0.0.1", PORT), 0.2).close()
                break
            except OSError:
                time.sleep(0.1)
        print(f"WAF={'oui' if a.waf else 'non'}  concurrence={a.concurrency}  duree={a.duration}s")
        print(f"{'fichier':<14}{'req/s':>9}{'Mo/s':>9}{'p50 ms':>9}{'p95 ms':>9}{'p99 ms':>9}{'non-200':>9}")
        files = (("/small.html", 1024), ("/medium.png", 100 * 1024), ("/large.bin", 5 * 1024 * 1024))
        if os.environ.get("BENCH_ONLY"):
            files = tuple(f for f in files if f[0] == os.environ["BENCH_ONLY"])
        for path, size in files:
            conc = a.concurrency if size < 1_000_000 else min(a.concurrency, 8)
            rps, p50, p95, p99, err = asyncio.run(run(path, a.duration, conc))
            print(f"{path:<14}{rps:>9.0f}{rps*size/1e6:>9.1f}{p50:>9.1f}{p95:>9.1f}{p99:>9.1f}{err:>9}")
    finally:
        proc.terminate(); proc.wait(10)
        shutil.rmtree(root, ignore_errors=True)


main()
