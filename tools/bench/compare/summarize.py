#!/usr/bin/env python3
# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Medianes des repetitions de campaign.sh - outil de developpement.

  python3 tools/bench/compare/summarize.py resultats.txt
"""
import collections
import re
import statistics
import sys
from pathlib import Path

rows: dict = collections.defaultdict(list)
memory: dict = collections.defaultdict(list)
for line in Path(sys.argv[1]).read_text(encoding="utf-8").splitlines():
    fields = line.split()
    if len(fields) == 7 and fields[1].endswith((".html", ".png", ".bin")):
        rows[(fields[0], fields[1])].append([float(x) for x in fields[2:6]])
    elif match := re.match(r"(\S+) PSS_Mo repos=(\d+) apres_charge=(\d+)", line):
        memory[match[1]].append((int(match[2]), int(match[3])))
names = list(dict.fromkeys(name for name, _ in rows))
print(f"{'configuration':<16}{'1 Ko req/s':>11}{'p99':>7}{'100 Ko req/s':>13}{'5 Mo Mo/s':>11}{'PSS repos':>10}{'PSS charge':>11}")
for name in names:
    def med(path: str, column: int, name: str = name) -> float:
        return statistics.median(r[column] for r in rows[(name, path)])
    idle = statistics.median(m[0] for m in memory[name]) if memory[name] else 0
    loaded = statistics.median(m[1] for m in memory[name]) if memory[name] else 0
    print(f"{name:<16}{med('small.html', 0):>11.0f}{med('small.html', 3):>7.1f}{med('medium.png', 0):>13.0f}"
          f"{med('large.bin', 1):>11.0f}{idle:>10.0f}{loaded:>11.0f}")
