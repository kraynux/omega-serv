#!/usr/bin/env python3
# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Cout d'une observation de menace Active Defense (lecture + ecriture SQLite, etat + journal
d'audit), telle qu'executee sur la boucle du serveur pour chaque requete suspecte
(OMEGA-SERV_ETUDE_PERFORMANCE.md, priorite 4) - outil de developpement.

  .venv/bin/python tools/bench/active_defense_cost.py
"""
import statistics
import tempfile
import time
from pathlib import Path

from omega_serv.application.active_defense.observe_threat import observe_threat
from omega_serv.domain.security.active_defense.config import parse_active_defense_config
from omega_serv.domain.security.waf.entities import Severity, WafDecision, WafFinding
from omega_serv.infrastructure.clock.system_clock import SystemClock
from omega_serv.infrastructure.persistence.sqlite_active_defense_connection import (
    open_active_defense_connection,
)
from omega_serv.infrastructure.persistence.sqlite_threat_state_repository import (
    SqliteThreatStateRepository,
)

connection = open_active_defense_connection(Path(tempfile.mkdtemp()) / "active-defense.sqlite")
repository = SqliteThreatStateRepository(connection)
config = parse_active_defense_config({"war_mode": {"enabled": True}})
decision = WafDecision(
    action="block", status_code=403, score=6,
    findings=(WafFinding(rule_id="R", pack="p", description="", severity=Severity.HIGH, weight=6, scope="path"),),
)
durations = []
for i in range(2000):
    started = time.perf_counter()
    observe_threat(repository, SystemClock(), config, subject_id=f"203.0.113.{i % 200}:ua", waf_decision=decision)
    durations.append((time.perf_counter() - started) * 1000)
durations.sort()
print(f"observation de menace : mediane {statistics.median(durations):.3f} ms, "
      f"p99 {durations[int(len(durations) * 0.99)]:.3f} ms, max {durations[-1]:.3f} ms")
