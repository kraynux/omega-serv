#!/usr/bin/env python3
# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Memoire et blocage du serveur pendant 3 telechargements simultanes d'un fichier de 300 Mo,
avec la latence d'une petite page servie en meme temps. Outil de developpement.

  .venv/bin/python tools/bench/bigfile.py
  BENCH_SRC=dossier/src -> autre code source ; BENCH_EXTRA_PATH=dossier -> ajoute au PYTHONPATH du serveur
"""
import asyncio
import json
import os
import shutil
import socket
import subprocess
import tempfile
import time
from pathlib import Path

SERV = Path(__file__).resolve().parents[2]; PORT = 18903
SRC = Path(os.environ.get("BENCH_SRC") or SERV / "src")
root = Path(tempfile.mkdtemp(prefix="big-")); shutil.copytree(SRC, root / "src", ignore=shutil.ignore_patterns("*.bak", "__pycache__"))
(root / "webroot").mkdir(); (root / "webroot/small.html").write_bytes(b"x" * 1024)
with open(root / "webroot/big.iso", "wb") as f:
    f.truncate(300 * 1024 * 1024)
(root / "config").mkdir(); (root / "config/omega-serve.json").write_text(json.dumps({"version": 1, "profile": "standard", "server": {"bind": "127.0.0.1", "port": PORT}}))
proc = subprocess.Popen([str(SERV / ".venv/bin/python"), "-m", "omega_serv", "--config", str(root / "config/omega-serve.json"), "serve"], cwd=root, env=dict(os.environ, PYTHONPATH=os.pathsep.join(filter(None, [os.environ.get("BENCH_EXTRA_PATH"), str(root / "src")]))), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
def rss():
    return int(next(l.split()[1] for l in open(f"/proc/{proc.pid}/status") if l.startswith("VmRSS"))) // 1024
async def get(path, read_body=True):
    r, w = await asyncio.open_connection("127.0.0.1", PORT)
    w.write(f"GET {path} HTTP/1.1\r\nHost: b\r\nConnection: close\r\n\r\n".encode()); await w.drain()
    t0 = time.perf_counter(); await r.readline(); first = time.perf_counter() - t0
    while True:
        chunk = await r.read(1 << 20)
        if not chunk: break
    w.close(); return first
async def main():
    for _ in range(50):
        try: socket.create_connection(("127.0.0.1", PORT), 0.2).close(); break
        except OSError: await asyncio.sleep(0.1)
    base = rss(); peak = base
    big = [asyncio.create_task(get("/big.iso")) for _ in range(3)]
    small_lat = []
    for _ in range(20):
        small_lat.append((await get("/small.html")) * 1000)
        peak = max(peak, rss()); await asyncio.sleep(0.05)
    await asyncio.gather(*big)
    print(f"memoire du serveur : repos {base} Mo, pic {peak} Mo pendant 3 telechargements de 300 Mo")
    print(f"petite page pendant ces telechargements : max {max(small_lat):.0f} ms, mediane {sorted(small_lat)[10]:.0f} ms")
asyncio.run(main())
proc.terminate(); proc.wait(10); shutil.rmtree(root, ignore_errors=True)
