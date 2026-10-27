#!/usr/bin/env python3
# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Cout unitaire des etapes chaudes d'une requete (OMEGA-SERV_ETUDE_PERFORMANCE.md, priorite 3) -
outil de developpement. Meilleur de 7 essais : peu sensible a la charge de fond de la machine.

  .venv/bin/python tools/bench/micro.py
"""
import tempfile
import timeit
from datetime import datetime, timezone
from pathlib import Path

from omega_serv.domain.logging.access_log_format import AccessLogEntry, format_combined_log_line
from omega_serv.infrastructure.filesystem.local_filesystem import LocalFilesystem
from omega_serv.infrastructure.filesystem.safe_path_resolver import SafePathResolver

N = 20_000

root = Path(tempfile.mkdtemp()) / "srv" / "site" / "webroot"
(root / "omega-serv" / "screenshots").mkdir(parents=True)
(root / "omega-serv" / "screenshots" / "1.png").write_bytes(b"x")
resolver = SafePathResolver(LocalFilesystem(), root)
entry = AccessLogEntry(
    remote_ip="203.0.113.9", timestamp=datetime.now(timezone.utc), method="GET",
    request_target="/omega-serv/screenshots/1.png", http_version="HTTP/1.1", status_code=200,
    response_size=12345, referer="https://exemple.test/", user_agent="Mozilla/5.0 (X11; Linux x86_64)",
    request_id="abcdef0123456789",
)


def best(stmt) -> float:
    return min(timeit.repeat(stmt, number=N, repeat=7)) / N * 1e6


print(f"resolution du chemin      : {best(lambda: resolver.resolve('/omega-serv/screenshots/1.png')):6.2f} us/requete")
print(f"ligne du journal d'acces  : {best(lambda: format_combined_log_line(entry)):6.2f} us/requete")
