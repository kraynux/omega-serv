#!/usr/bin/env python3
# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Medianes des repetitions de campaign.sh (reverse proxy), et rapport a nginx-2 du meme protocole (HTTP ou HTTPS) -
outil de developpement.

  python3 tools/bench/proxy/summarize.py resultats.txt
"""
import collections
import re
import statistics
import sys
from pathlib import Path

rows: dict = collections.defaultdict(list)
memory: dict = collections.defaultdict(list)
errors: dict = collections.defaultdict(int)
for line in Path(sys.argv[1]).read_text(encoding="utf-8").splitlines():
    fields = line.split()
    if len(fields) == 7 and fields[1].endswith((".html", ".png")):
        rows[(fields[0], fields[1])].append([float(x) for x in fields[2:6]])
        errors[fields[0]] += int(fields[6])
    elif match := re.match(r"(\S+) PSS_Mo repos=(\d+) apres_charge=(\d+)", line):
        memory[match[1]].append((int(match[2]), int(match[3])))
names = list(dict.fromkeys(name for name, _ in rows))


def med(name: str, path: str, column: int) -> float:
    values = [r[column] for r in rows.get((name, path), [])]
    return statistics.median(values) if values else 0.0


print(f"{'configuration':<24}{'1 Ko req/s':>11}{'rapport':>8}{'p99':>7}{'100 Ko req/s':>13}{'rapport':>8}"
      f"{'PSS repos':>10}{'PSS charge':>11}{'non 200':>9}")
for name in names:
    ref = "nginx-2-tls" if name.endswith("-tls") else "nginx-2"
    small, medium = med(name, "small.html", 0), med(name, "medium.png", 0)
    ref_small, ref_medium = med(ref, "small.html", 0), med(ref, "medium.png", 0)
    idle = statistics.median(m[0] for m in memory[name]) if memory[name] else 0
    loaded = statistics.median(m[1] for m in memory[name]) if memory[name] else 0
    print(f"{name:<24}{small:>11.0f}{small / ref_small if ref_small else 0:>8.2f}{med(name, 'small.html', 3):>7.1f}"
          f"{medium:>13.0f}{medium / ref_medium if ref_medium else 0:>8.2f}{idle:>10.0f}{loaded:>11.0f}"
          f"{errors[name]:>9}")
