#!/usr/bin/env python3
# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Vecteurs de reference de la limite de debit comptee par le natif (OMEGA-SERV_PLAN-DETAILLE_WAF_NATIF.md, lot 6) -
outil de developpement.

Section `rate_limit` produite par la VRAIE fonction de l'instantane (`rate_limit_payload`) ; attendus calcules par
les VRAIES fonctions Python : regle retenue (`select_rate_limit`) et suite de verdicts du seau a jetons
(`InMemoryRateLimitStore.check`, horloge simulee). Rejoues par native/omega-http-core/tests/test_rate_limiter.cpp.

  .venv/bin/python tools/differential/make_rate_vectors.py native/omega-http-core/tests/vectors

Sorties : rate_policy.json ; rate_select.tsv (chemin hexa, ip, cle attendue, requests, window) ; rate_buckets.tsv
(requests, window, puis une suite « instant:attendu » ; attendu = 0 autorisee, N = Retry-After)."""
from __future__ import annotations

import json
import random
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from omega_serv.domain.security.waf.config import parse_waf_config
from omega_serv.domain.security.waf.rate_limit_policy import select_rate_limit
from omega_serv.infrastructure.server.native_snapshot import rate_limit_payload
from omega_serv.infrastructure.waf.rate_limit_store import InMemoryRateLimitStore

RNG = random.Random(20261104)


class _Clock:
    def __init__(self) -> None:
        self.t = 1_000_000.0

    def now(self) -> datetime:
        return datetime.fromtimestamp(self.t, UTC)


def main(out_dir: Path) -> None:
    waf = parse_waf_config({"rate_limit": {
        "enabled": True,
        "global": {"requests": 120, "window_seconds": 60},
        "path_policies": [{"prefix": "/galerie", "requests": 600, "window_seconds": 60},
                          {"prefix": "/galerie/grand/", "requests": 0, "window_seconds": 60},
                          {"prefix": "/api", "requests": 10, "window_seconds": 1},
                          {"prefix": "/api/", "requests": 20, "window_seconds": 1}],
        "source_policies": [{"network": "10.0.0.0/8", "requests": 1000, "window_seconds": 60},
                            {"network": "10.1.0.0/16", "requests": 5, "window_seconds": 10, "trusted": True},
                            {"network": "2001:db8::/32", "requests": 50, "window_seconds": 60},
                            {"network": "2001:db8:1::/48", "requests": 0, "window_seconds": 60}],
    }})
    section = rate_limit_payload(waf.rate_limit)
    (out_dir / "rate_policy.json").write_text(json.dumps(section, ensure_ascii=False), encoding="utf-8")
    paths = ["/", "/galerie", "/galerie/", "/galerie/x.png", "/galeries", "/galerie/grand", "/galerie/grand/a",
             "/api", "/api/v1", "/apix", "/a%2Fb", "/été", "/.omega-serv-error-css/error-pages.css", ""]
    ips = ["203.0.113.5", "10.2.3.4", "10.1.2.3", "::ffff:10.1.2.3", "2001:db8::1", "2001:db8:1::5",
           "2001:db9::1", "fe80::1%eth0", "pas-une-ip", "127.0.0.1"]
    rows = []
    for path in paths:
        for ip in ips:
            selected = select_rate_limit(path, ip, waf.rate_limit)
            rows.append("\t".join([path.encode("utf-8").hex() or "-", ip, selected.key,
                                   str(selected.requests), str(selected.window_seconds)]))
    (out_dir / "rate_select.tsv").write_text("\n".join(rows) + "\n", encoding="utf-8")
    buckets = []
    for requests, window in ((1, 1), (3, 10), (5, 60), (120, 60), (10, 1), (7, 3), (2, 0)):
        clock = _Clock()
        store = InMemoryRateLimitStore(clock)
        steps = []
        for _ in range(400):
            clock.t += RNG.choice([0.0, 0.0, 0.01, 0.1, 0.37, 1.0, 2.5, 7.0])
            result = store.check("k", requests, window)
            steps.append(f"{clock.t - 1_000_000.0:.6f}:{0 if result.allowed else result.retry_after_seconds}")
        buckets.append("\t".join([str(requests), str(window)] + steps))
    (out_dir / "rate_buckets.tsv").write_text("\n".join(buckets) + "\n", encoding="utf-8")
    print(f"{len(rows)} selections, {len(buckets)} seaux")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
