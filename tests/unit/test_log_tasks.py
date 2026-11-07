"""Lecture decoupee en morceaux paralleles (2026-11-06) : aucune ligne perdue ni comptee deux fois,
resultat identique a une lecture d'un bloc, top IP identique a l'ancien calcul. Porte d'omega-log le 2026-11-07."""
from __future__ import annotations

import os
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from itertools import pairwise
from pathlib import Path

import pytest

from omega_serv.application.logs import log_tasks
from omega_serv.application.logs.log_tasks import plan_read_tasks, run_read_task
from omega_serv.domain.logs.analytics import compute_top_ips
from omega_serv.domain.logs.exceptions import LogPermissionError
from omega_serv.domain.logs.parser import parse_log_line
from omega_serv.domain.logs.stats_accumulator import StatsAccumulator, accumulate


def _write_log(path: Path, lines: int) -> list[str]:
    start = datetime(2026, 10, 1, 0, 0, 0, tzinfo=timezone.utc)
    rows = []
    for i in range(lines):
        moment = (start + timedelta(minutes=13 * i)).strftime("%d/%b/%Y:%H:%M:%S")
        status = (200, 404, 301, 500, 403)[i % 5]
        rows.append(f'10.0.{i % 7}.{i % 11} - - [{moment} +0000] "GET /p{i % 23}?x={i} HTTP/1.1" {status} {i % 900} '
                    f'"-" "agent {"a" * (i % 50)}"')
    path.write_text("\n".join(rows) + "\n")
    return rows


@pytest.fixture
def small_chunks(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(log_tasks, "MIN_CHUNK_BYTES", 4096)


def test_chunks_cover_every_line_once(tmp_path: Path, small_chunks: None) -> None:
    log = tmp_path / "access.log"
    rows = _write_log(log, 3000)
    tasks = plan_read_tasks([str(log)], workers=4)
    assert len(tasks) == 16
    assert tasks[0].start == 0 and tasks[-1].end == log.stat().st_size
    assert all(a.end == b.start for a, b in pairwise(tasks))
    data = log.read_bytes()
    assert all(data[task.start - 1:task.start] == b"\n" for task in tasks[1:])   # bornes en debut de ligne
    total = StatsAccumulator()
    for task in tasks:
        total.merge(run_read_task(task))
    assert total.total == len(rows)


def test_chunked_report_equals_single_read(tmp_path: Path, small_chunks: None) -> None:
    log = tmp_path / "access.log"
    rows = _write_log(log, 3000)
    merged = StatsAccumulator()
    for task in plan_read_tasks([str(log)], workers=4):
        merged.merge(run_read_task(task))
    entries = [entry for entry in (parse_log_line(row) for row in rows) if entry is not None]
    assert asdict(merged.to_report()) == asdict(accumulate(entries).to_report())
    assert merged.top_ips(10) == compute_top_ips(entries, n=10)


def test_small_file_is_one_task_and_period_is_one_reverse_task(tmp_path: Path) -> None:
    log = tmp_path / "access.log"
    _write_log(log, 50)
    assert len(plan_read_tasks([str(log)], workers=8)) == 1
    tasks = plan_read_tasks([str(log)], period="7d", now=datetime(2026, 10, 8, 5, 0, 0, tzinfo=timezone.utc), workers=8)
    assert len(tasks) == 1 and tasks[0].period == "7d"
    assert run_read_task(tasks[0]).total == 26        # lignes de 05:12 (i=24) a 10:37 (i=49)


def test_missing_file_is_skipped(tmp_path: Path) -> None:
    assert plan_read_tasks([str(tmp_path / "absent.log")], workers=2) == []


def test_unreadable_file_raises_log_permission_error(tmp_path: Path) -> None:
    log = tmp_path / "access.log"
    _write_log(log, 5)
    log.chmod(0)
    try:
        if os.access(log, os.R_OK):
            pytest.skip("compte root : tout est lisible")
        with pytest.raises(LogPermissionError) as raised:
            plan_read_tasks([str(log)], workers=2)
        assert raised.value.path == str(log)
    finally:
        log.chmod(0o644)
