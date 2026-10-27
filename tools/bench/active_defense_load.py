#!/usr/bin/env python3
# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Charge et resilience d'Active Defense (OMEGA-SERV_ETUDE_ACTIVE_DEFENSE_STIX_MISP_CHARGE.md §3)
- outil de developpement.

Lance un vrai `omega-serv serve` (copie de src/ dans un dossier temporaire) avec le WAF en mode
block, 127.0.0.1 en proxy de confiance (X-Forwarded-For) et, selon le scenario, Active Defense en
mode guerre. Deux familles de clients, chacune dans ses processus :
- legitimes : GET /index.html, navigateur ordinaire, adresse fixe (198.51.100.10) ;
- hostiles : chemins sensibles avec un User-Agent de scanner, une adresse differente tiree parmi
  --sources (203.0.113.0/24 puis 2001:db8::/32), donc autant de « sujets » Active Defense.

Scenarios :
  S1  legitimes seuls, Active Defense desactive puis active (cout au repos)
  S2  legitimes + attaque, Active Defense desactive puis active (cout sous attaque)
  S3  attaque longue : croissance de la base et de la memoire (--duration plus long)
  S4  S2 avec --workers 2 (verrous SQLite entre processus)
  S5  S2, et la base est verrouillee par un autre programme pendant 10 s au milieu de la mesure

  .venv/bin/python tools/bench/active_defense_load.py --scenario S2 [--duration 20] [--sources 1000]
  [--hostile-connections 16]  ; --sources 100000 = « botnet » : chaque requete vient d'une nouvelle
  adresse, donc une nouvelle ecriture en base et aucun ralentissement du mode guerre
  SRV_CPUS=0,2 CLI_CPUS=1,3 (par defaut) : serveur et clients epingles sur des cœurs distincts.
  BENCH_PROFILE=fichier.prof : profil cProfile du serveur (fil principal = la boucle), Active Defense active.
"""
import argparse
import asyncio
import json
import multiprocessing
import os
import shutil
import socket
import sqlite3
import subprocess
import tempfile
import threading
import time
from pathlib import Path

SERV = Path(__file__).resolve().parents[2]
PORT = 18921
LEGIT_IP = "198.51.100.10"
HOSTILE_PATHS = ("/.env", "/wp-login.php", "/.git/config", "/phpmyadmin/", "/backup.sql")
HOSTILE_UA = "sqlmap/1.7.2#stable (https://sqlmap.org)"
REPLY_TIMEOUT = 15.0  # au-dela, une requete compte « sans reponse » (serveur fige)
LEGIT_UA = "Mozilla/5.0 (X11; Linux x86_64; rv:131.0) Gecko/20100101 Firefox/131.0"


def _cpus(name: str, default: str) -> set[int]:
    return {int(c) for c in os.environ.get(name, default).split(",")}


def make_root(active_defense: bool, workers: int, state_ttl: int | None = None) -> Path:
    root = Path(tempfile.mkdtemp(prefix="adload-"))
    shutil.copytree(SERV / "src", root / "src", ignore=shutil.ignore_patterns("*.bak", "__pycache__"))
    (root / "webroot").mkdir()
    (root / "webroot/index.html").write_bytes(b"<!doctype html><title>ok</title>" + b"x" * 1000)
    rules = root / "secure/waf/rules"
    rules.mkdir(parents=True)
    for pack in (SERV / "secure/waf/rules").glob("*.json"):
        shutil.copy(pack, rules / pack.name)
    options = {
        "waf": {"enabled": True, "mode": "block",
                "rules": {"paths": [f"secure/waf/rules/{p.name}" for p in sorted(rules.glob("*.json"))]},
                "rate_limit": {"enabled": False}},
        "trusted_proxy": {"enabled": True, "trusted_networks": ["127.0.0.1/32"],
                          "header_preference": ["X-Forwarded-For"]},
    }
    if active_defense:
        options["active_defense"] = {"enabled": True, "war_mode": {"enabled": True}}
        if state_ttl is not None:
            options["active_defense"]["state_ttl_seconds"] = state_ttl
    (root / "config").mkdir()
    (root / "config/omega-serve.json").write_text(json.dumps({
        "version": 1, "profile": "standard",
        "server": {"bind": "127.0.0.1", "port": PORT, "max_connections": 2048,
                   "max_keepalive_requests": 1_000_000, "workers": workers},
        "options": options,
    }))
    return root


def _source(index: int) -> str:
    if index < 254:
        return f"203.0.113.{index + 1}"
    return f"2001:db8::{index:x}"


async def _connection(kind: str, deadline: float, sources: int, offset: int, out: dict) -> None:
    reader, writer = await asyncio.open_connection("127.0.0.1", PORT)
    try:
        while time.perf_counter() < deadline:
            if kind == "legit":
                request = (f"GET /index.html HTTP/1.1\r\nHost: bench\r\nUser-Agent: {LEGIT_UA}\r\n"
                           f"X-Forwarded-For: {LEGIT_IP}\r\n\r\n")
            else:
                # compteur commun au processus : le serveur ferme la connexion apres un 403, la
                # reconnexion doit continuer sur une NOUVELLE source, jamais repartir du debut
                count = offset + out["sent"]
                path = HOSTILE_PATHS[count % len(HOSTILE_PATHS)]
                request = (f"GET {path} HTTP/1.1\r\nHost: bench\r\nUser-Agent: {HOSTILE_UA}\r\n"
                           f"X-Forwarded-For: {_source(count % sources)}\r\n\r\n")
            out["sent"] += 1
            started = time.perf_counter()
            writer.write(request.encode())
            await writer.drain()
            try:
                status_line = await asyncio.wait_for(reader.readline(), timeout=REPLY_TIMEOUT)
            except TimeoutError:
                out["timeouts"] += 1
                break
            if not status_line:
                out["closed"] += 1
                break
            length, close = 0, False
            while (line := await asyncio.wait_for(reader.readline(), timeout=REPLY_TIMEOUT)) not in (b"\r\n", b""):
                lower = line.lower()
                if lower.startswith(b"content-length:"):
                    length = int(line.split(b":")[1])
                elif lower.startswith(b"connection:") and b"close" in lower:
                    close = True
            await asyncio.wait_for(reader.readexactly(length), timeout=REPLY_TIMEOUT)
            out["latencies"].append(time.perf_counter() - started)
            code = status_line.split()[1].decode()
            out["codes"][code] = out["codes"].get(code, 0) + 1
            if close:
                break
    except TimeoutError:
        out["timeouts"] += 1
    except (ConnectionError, asyncio.IncompleteReadError):
        out["closed"] += 1
    finally:
        writer.close()


def _client(args: tuple) -> None:
    kind, deadline, connections, sources, seed, queue = args
    os.sched_setaffinity(0, _cpus("CLI_CPUS", "1,3"))

    async def run() -> None:
        out: dict = {"latencies": [], "codes": {}, "closed": 0, "sent": 0, "timeouts": 0}
        while time.perf_counter() < deadline:  # une connexion fermee par le serveur est rouverte
            await asyncio.gather(*(_connection(kind, deadline, sources, seed, out)
                                   for i in range(connections)))
        queue.put((kind, out))

    asyncio.run(run())


def _pss_mb(pid: int) -> int:
    total = 0
    pids = [pid] + [int(p) for p in subprocess.run(["pgrep", "-P", str(pid)], capture_output=True, text=True, check=False).stdout.split()]
    for p in pids:
        try:
            for line in Path(f"/proc/{p}/smaps_rollup").read_text().splitlines():
                if line.startswith("Pss:"):
                    total += int(line.split()[1])
        except OSError:
            pass
    return total // 1024


def _threads_cpu(pid: int) -> dict[str, float]:
    """Temps processeur (s) par fil du serveur et de ses workers : boucle, ecrivain, autres."""
    hertz = os.sysconf("SC_CLK_TCK")
    totals: dict[str, float] = {}
    pids = [pid] + [int(p) for p in subprocess.run(["pgrep", "-P", str(pid)], capture_output=True, text=True, check=False).stdout.split()]
    for process in pids:
        for task in Path(f"/proc/{process}/task").glob("*"):
            try:
                name = (task / "comm").read_text().strip()
                fields = (task / "stat").read_text().rsplit(")", 1)[1].split()
            except OSError:
                continue
            seconds = (int(fields[11]) + int(fields[12])) / hertz
            key = "ecrivain" if name.startswith("omega-serv-act") else ("boucle" if task.name == str(process) else "autres")
            totals[key] = round(totals.get(key, 0.0) + seconds, 2)
    return totals


def _quantile(sorted_values: list[float], fraction: float) -> float:
    if not sorted_values:
        return 0.0
    return sorted_values[min(len(sorted_values) - 1, int(fraction * len(sorted_values)))] * 1000


def _hold_lock(database: Path, start_after: float, hold: float, report: dict) -> None:
    time.sleep(start_after)
    connection = sqlite3.connect(database, timeout=30)
    connection.execute("BEGIN EXCLUSIVE")
    report["lock_held_at"] = time.perf_counter()
    time.sleep(hold)
    connection.rollback()
    connection.close()


def measure(*, active_defense: bool, attack: bool, workers: int, duration: float, sources: int,
            legit_clients: int, hostile_clients: int, hostile_connections: int, lock_test: bool,
            state_ttl: int | None = None) -> dict:
    root = make_root(active_defense, workers, state_ttl)
    env = dict(os.environ, PYTHONPATH=str(root / "src"))
    # sortie d'erreurs dans un FICHIER : un pipe non lu se remplit (64 Ko) et bloque le serveur
    stderr_file = (root / "server-stderr.txt").open("wb")
    profile = ["-m", "cProfile", "-o", os.environ["BENCH_PROFILE"]] if os.environ.get("BENCH_PROFILE") and active_defense else []
    server = subprocess.Popen(
        ["taskset", "-c", os.environ.get("SRV_CPUS", "0,2"), str(SERV / ".venv/bin/python"), *profile, "-m", "omega_serv",
         "--config", str(root / "config/omega-serve.json"), "serve"],
        cwd=root, env=env, stdout=subprocess.DEVNULL, stderr=stderr_file, start_new_session=True,
    )
    try:
        for _ in range(150):
            try:
                socket.create_connection(("127.0.0.1", PORT), 0.2).close()
                break
            except OSError:
                time.sleep(0.1)
        time.sleep(1.0 + 0.5 * workers)
        pss_idle = _pss_mb(server.pid)
        queue: multiprocessing.Queue = multiprocessing.Queue()
        deadline = time.perf_counter() + duration
        jobs = [multiprocessing.Process(target=_client, args=(("legit", deadline, 8, sources, i * 101, queue),))
                for i in range(legit_clients)]
        if attack:
            jobs += [multiprocessing.Process(target=_client, args=(("hostile", deadline, hostile_connections, sources, i * 977, queue),))
                     for i in range(hostile_clients)]
        lock_report: dict = {}
        database = root / "var/lib/active-defense.sqlite3"
        if lock_test:
            threading.Thread(target=_hold_lock, args=(database, duration / 2 - 5, 10, lock_report), daemon=True).start()
        started = time.perf_counter()
        for job in jobs:
            job.start()
        results = [queue.get() for _ in jobs]
        elapsed = time.perf_counter() - started
        for job in jobs:
            job.join()
        pss_loaded = _pss_mb(server.pid)
        threads_cpu = _threads_cpu(server.pid)
        merged: dict = {}
        for kind, out in results:
            entry = merged.setdefault(kind, {"latencies": [], "codes": {}, "closed": 0, "timeouts": 0})
            entry["latencies"].extend(out["latencies"])
            entry["closed"] += out["closed"]
            entry["timeouts"] += out["timeouts"]
            for code, n in out["codes"].items():
                entry["codes"][code] = entry["codes"].get(code, 0) + n
        summary: dict = {"pss_idle_mb": pss_idle, "pss_loaded_mb": pss_loaded, "threads_cpu": threads_cpu}
        for kind, entry in merged.items():
            lat = sorted(entry["latencies"])
            summary[kind] = {"rps": len(lat) / elapsed, "p50": _quantile(lat, 0.5), "p95": _quantile(lat, 0.95),
                             "p99": _quantile(lat, 0.99),
                             "max": lat[-1] * 1000 if lat else 0.0, "codes": entry["codes"], "closed": entry["closed"],
                             "timeouts": entry["timeouts"]}
        if database.exists():
            size = sum(p.stat().st_size for p in database.parent.glob(database.name + "*"))
            summary["db_mb"] = round(size / 1e6, 2)
            try:
                with sqlite3.connect(f"file:{database}?mode=ro", uri=True, timeout=10) as ro:
                    summary["subjects"] = ro.execute("SELECT COUNT(*) FROM threat_states").fetchone()[0]
                    summary["incidents"] = ro.execute("SELECT COUNT(*) FROM incidents").fetchone()[0]
            except sqlite3.Error as error:
                summary["db_read_error"] = str(error)
        error_log = root / "var/log/error.log"
        text = error_log.read_text(errors="replace") if error_log.exists() else ""
        summary["error_log"] = {"lines": text.count("\n"), "locked": text.count("locked"),
                                "traceback": text.count("Traceback")}
        summary["lock_test"] = bool(lock_report)
        stderr_text = (root / "server-stderr.txt").read_text(errors="replace")
        summary["stderr"] = {"traceback": stderr_text.count("Traceback"),
                             "locked": stderr_text.count("database is locked"),
                             "unhandled": stderr_text.count("Unhandled exception")}
        return summary
    finally:
        os.killpg(server.pid, 15)
        try:
            server.wait(timeout=30)
        except subprocess.TimeoutExpired:
            os.killpg(server.pid, 9)
            server.wait()
        stderr_file.close()
        shutil.rmtree(root, ignore_errors=True)


def _print(label: str, s: dict) -> None:
    parts = [f"{label:<26}"]
    for kind in ("legit", "hostile"):
        if kind in s:
            k = s[kind]
            codes = ",".join(f"{c}:{n}" for c, n in sorted(k["codes"].items()))
            parts.append(f"{kind} {k['rps']:6.0f} req/s p50 {k['p50']:5.1f} p95 {k['p95']:6.1f} "
                         f"p99 {k['p99']:6.1f} max {k['max']:7.1f} ms [{codes}] coupees {k['closed']} "
                         f"sans reponse {k['timeouts']}")
    parts.append(f"PSS {s['pss_idle_mb']}->{s['pss_loaded_mb']} Mo ; CPU par fil (s) {s['threads_cpu']}")
    if "db_mb" in s:
        parts.append(f"base {s['db_mb']} Mo, {s.get('subjects', '?')} sujets, {s.get('incidents', '?')} incidents")
    if "db_read_error" in s:
        parts.append(f"lecture base : {s['db_read_error']}")
    e = s["error_log"]
    parts.append(f"error.log {e['lines']} lignes (locked {e['locked']}, traceback {e['traceback']})")
    r = s["stderr"]
    parts.append(f"stderr : {r['unhandled']} exceptions non gerees, {r['locked']} « database is locked »")
    print("\n    ".join(parts), flush=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", choices=("S1", "S2", "S3", "S4", "S5"), required=True)
    parser.add_argument("--duration", type=float, default=20)
    parser.add_argument("--sources", type=int, default=1000)
    parser.add_argument("--workers", type=int, default=None)
    parser.add_argument("--legit-clients", type=int, default=1)
    parser.add_argument("--hostile-clients", type=int, default=1)
    parser.add_argument("--hostile-connections", type=int, default=16, help="connexions par client hostile")
    parser.add_argument("--state-ttl", type=int, default=None,
                        help="duree de vie d'un etat de menace (s) ; courte = purge automatique visible en S3")
    args = parser.parse_args()
    workers = args.workers or (2 if args.scenario == "S4" else 1)
    attack = args.scenario != "S1"
    print(f"scenario {args.scenario}  workers {workers}  duree {args.duration}s  sources hostiles {args.sources}  "
          f"(serveur sur {os.environ.get('SRV_CPUS', '0,2')}, clients sur {os.environ.get('CLI_CPUS', '1,3')})", flush=True)
    common = {"attack": attack, "workers": workers, "duration": args.duration, "sources": args.sources,
              "legit_clients": args.legit_clients, "hostile_clients": args.hostile_clients,
              "hostile_connections": args.hostile_connections, "state_ttl": args.state_ttl}
    if args.scenario in ("S1", "S2", "S4"):
        _print("Active Defense desactive", measure(active_defense=False, lock_test=False, **common))
    _print("Active Defense active", measure(active_defense=True, lock_test=args.scenario == "S5", **common))


if __name__ == "__main__":
    main()
