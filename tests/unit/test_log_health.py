"""Sante des logs (2026-11-07, OMEGA-SERV_A_FAIRE_STATS_DEPUIS_OMEGA_LOG.md, lot 4) : regles du domaine,
collecte sur de vrais fichiers, droits d'ecriture du compte du service, textes et exports."""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from omega_serv.application.logs.health_presentation import (
    finding_hint,
    finding_text,
    html_arguments,
    render_text,
    report_to_dict,
)
from omega_serv.application.logs.log_health import (
    HealthTarget,
    archive_facts,
    collect_log_health,
    health_targets,
)
from omega_serv.domain.config.entities import LogsConfig
from omega_serv.domain.logs.health import (
    ORIGIN_LIBRARY,
    ORIGIN_OMEGA_SERV,
    ArchiveFacts,
    DiskFacts,
    HealthLevel,
    LogFacts,
    build_health_report,
    covered_by_logrotate,
    evaluate_disks,
    evaluate_log,
    parse_logrotate_patterns,
)
from omega_serv.domain.logs.library import LogFile
from omega_serv.domain.security.file_access import (
    AccountIdentity,
    PathNode,
    plan_write_access_fix,
    service_can_write,
)
from omega_serv.infrastructure.exporters.html_exporter import export_log_health_html

NOW = datetime(2026, 11, 7, 12, 0, tzinfo=timezone.utc)


def _codes(facts: LogFacts) -> list[str]:
    return [finding.code for finding in evaluate_log(facts, NOW).findings]


def _existing(**changes: object) -> LogFacts:
    values: dict = {"path": "/var/log/x.log", "origin": ORIGIN_LIBRARY, "exists": True, "size": 1000,
                    "modified_at": NOW - timedelta(hours=1), "mode": 0o644}
    values.update(changes)
    return LogFacts(**values)


# ---- regles -------------------------------------------------------------------

def test_missing_depends_on_origin_and_log() -> None:
    assert evaluate_log(LogFacts("/a", ORIGIN_LIBRARY), NOW).level == HealthLevel.PROBLEM
    assert _codes(LogFacts("/a", ORIGIN_LIBRARY)) == ["missing_library"]
    assert evaluate_log(LogFacts("/a", ORIGIN_OMEGA_SERV, "access"), NOW).level == HealthLevel.WARNING
    assert _codes(LogFacts("/a", ORIGIN_OMEGA_SERV, "uploads")) == ["not_created_yet"]
    assert _codes(LogFacts("/a", ORIGIN_LIBRARY, broken_link=True)) == ["broken_link"]


def test_healthy_log_has_no_finding() -> None:
    health = evaluate_log(_existing(), NOW)
    assert health.findings == [] and health.level == HealthLevel.OK


def test_writer_cannot_write_is_a_problem_with_fix_mode() -> None:
    health = evaluate_log(_existing(origin=ORIGIN_OMEGA_SERV, log_id="access", writer="omega-serv",
                                    writer_can_write=False, write_fix_mode=0o664), NOW)
    assert health.level == HealthLevel.PROBLEM
    assert health.findings[0].params == {"account": "omega-serv", "mode": "644", "new_mode": "664"}


def test_silence_is_a_warning_only_for_watched_logs() -> None:
    old = NOW - timedelta(days=10)
    assert evaluate_log(_existing(modified_at=old), NOW).level == HealthLevel.WARNING
    assert evaluate_log(_existing(origin=ORIGIN_OMEGA_SERV, log_id="error", modified_at=old), NOW).level == HealthLevel.INFO
    assert evaluate_log(_existing(origin=ORIGIN_OMEGA_SERV, log_id="access", modified_at=old), NOW).level == HealthLevel.WARNING


@pytest.mark.parametrize(("changes", "code"), [
    ({"size": 0}, "empty"),
    ({"nul_bytes": True}, "nul_bytes"),
    ({"sampled_lines": 40, "dated_lines": 10}, "undated"),
    ({"last_timestamp": NOW + timedelta(days=2)}, "future_dates"),
    ({"world_writable": True}, "world_writable"),
    ({"readable": False}, "unreadable"),
    ({"duplicate_of": "/var/log/y.log"}, "duplicate"),
    ({"size": 200 * 1024 * 1024, "logrotate_covered": False}, "no_logrotate"),
])
def test_each_rule(changes: dict, code: str) -> None:
    assert code in _codes(_existing(**changes))


def test_rotation_threshold_only_for_omega_serv_logs() -> None:
    assert "over_rotation_threshold" in _codes(_existing(origin=ORIGIN_OMEGA_SERV, log_id="access", rotation_max_bytes=10))
    assert "no_logrotate" not in _codes(_existing(size=200 * 1024 * 1024, logrotate_covered=True))


def test_growth_needs_one_day_of_dated_lines() -> None:
    day_span = _existing(size=86400, first_timestamp=NOW - timedelta(days=2), last_timestamp=NOW)
    assert evaluate_log(day_span, NOW).growth_per_day == pytest.approx(43200)
    short = _existing(first_timestamp=NOW - timedelta(hours=2), last_timestamp=NOW)
    assert evaluate_log(short, NOW).growth_per_day is None


def test_disk_projection_and_fill_levels() -> None:
    log = evaluate_log(_existing(device=7, size=10 * 86400, first_timestamp=NOW - timedelta(days=10),
                                 last_timestamp=NOW), NOW)
    soon, = evaluate_disks([DiskFacts(7, "/", total=1000 * 86400, free=5 * 86400)], [log])
    assert soon.days_to_full == pytest.approx(5)
    assert {finding.code: finding.level for finding in soon.findings} == {
        "disk_almost_full": HealthLevel.PROBLEM, "disk_full_soon": HealthLevel.PROBLEM}
    roomy, = evaluate_disks([DiskFacts(7, "/", total=100, free=50)], [evaluate_log(_existing(device=7), NOW)])
    assert roomy.findings == [] and roomy.days_to_full is None


def test_report_level_and_counts() -> None:
    report = build_health_report([LogFacts("/a", ORIGIN_LIBRARY), _existing()], [], ArchiveFacts("/arch"), NOW)
    assert report.level == HealthLevel.PROBLEM
    assert report.counts()[HealthLevel.OK] == 1 and report.counts()[HealthLevel.PROBLEM] == 1
    assert report.archives is not None and report.archives.findings[0].code == "no_archives"


# ---- logrotate -------------------------------------------------------------------

def test_logrotate_patterns_ignore_directives() -> None:
    text = """# global
weekly
include /etc/logrotate.d
/var/log/wtmp /var/log/btmp {
    monthly
}
"/var/log/nginx/*.log" {
    daily  # commentaire
}
"""
    patterns = parse_logrotate_patterns(text)
    assert patterns == ["/var/log/wtmp", "/var/log/btmp", "/var/log/nginx/*.log"]
    assert covered_by_logrotate("/var/log/nginx/access.log", patterns)
    assert not covered_by_logrotate("/var/log/auth.log", patterns)


# ---- droits d'ecriture du compte du service ----------------------------------------

def _chain(file_mode: int, file_uid: int = 1000, file_gid: int = 900) -> tuple[PathNode, ...]:
    return (PathNode("/", 0o40755, 0, 0, True), PathNode("/srv", 0o40755, 1000, 1000, True),
            PathNode("/srv/access.log", 0o100000 | file_mode, file_uid, file_gid, False))


SERVICE = AccountIdentity("omega-serv", 950, frozenset({900}))


def test_service_write_through_group_bit() -> None:
    assert not service_can_write(_chain(0o644), SERVICE).readable
    assert service_can_write(_chain(0o664), SERVICE).readable
    fix = plan_write_access_fix(service_can_write(_chain(0o644), SERVICE), SERVICE, current_uid=1000)
    assert fix is not None and fix.new_mode == 0o664


def test_no_fix_when_not_owner_or_not_in_group() -> None:
    verdict = service_can_write(_chain(0o644), SERVICE)
    assert plan_write_access_fix(verdict, SERVICE, current_uid=1001) is None
    other_group = service_can_write(_chain(0o644, file_gid=1000), SERVICE)
    assert plan_write_access_fix(other_group, SERVICE, current_uid=1000) is None  # jamais le bit « autres »


# ---- collecte sur de vrais fichiers --------------------------------------------------

def _access_line(moment: datetime) -> str:
    return f'1.1.1.1 - - [{moment.strftime("%d/%b/%Y:%H:%M:%S")} +0000] "GET / HTTP/1.1" 200 10 "-" "curl"\n'


def test_collect_real_files(tmp_path: Path) -> None:
    now = datetime.now(timezone.utc)
    good = tmp_path / "access.log"
    good.write_text("".join(_access_line(now - timedelta(days=3) + timedelta(hours=i)) for i in range(72)))
    undated = tmp_path / "undated.log"
    undated.write_text("sans date\n" * 50)
    corrupt = tmp_path / "corrupt.log"
    corrupt.write_bytes(_access_line(now).encode() + b"\x00\x00\x00\n")
    link = tmp_path / "link.log"
    link.symlink_to(good)
    targets = [HealthTarget(str(path), ORIGIN_LIBRARY) for path in (good, undated, corrupt, link, tmp_path / "absent.log")]
    report = collect_log_health(targets, file_access=None, service_account=None, rotation_max_bytes=None,
                                archives=None, logrotate_patterns=[])
    by_path = {log.facts.path: log for log in report.logs}
    assert by_path[str(good)].findings == []
    assert by_path[str(good)].growth_per_day is not None
    assert by_path[str(good)].facts.detected_source == "access"
    assert [f.code for f in by_path[str(undated)].findings] == ["undated"]
    assert "nul_bytes" in [f.code for f in by_path[str(corrupt)].findings]
    assert [f.code for f in by_path[str(link)].findings] == ["duplicate"]
    assert [f.code for f in by_path[str(tmp_path / "absent.log")].findings] == ["missing_library"]
    assert len(report.disks) == 1 and report.disks[0].logs


def test_targets_put_omega_serv_logs_first_without_duplicates(tmp_path: Path) -> None:
    access = os.path.abspath(tmp_path / "var/log/access.log")
    library = [LogFile(path=access), LogFile(path="/var/log/auth.log"), LogFile(path="/remote.log", access="ssh")]
    targets = health_targets(LogsConfig(), tmp_path, library)
    assert [target.log_id for target in targets[:5]] == ["access", "error", "waf_alerts", "breakage", "uploads"]
    assert [target.path for target in targets[5:]] == ["/var/log/auth.log"]


def test_archive_facts() -> None:
    infos = [{"size_bytes": 10, "modified_at": "2026-10-01T00:00:00+00:00"},
             {"size_bytes": 5, "modified_at": "2026-11-01T00:00:00+00:00"}]
    facts = archive_facts(Path("/arch"), infos, keep=7)
    assert (facts.count, facts.total_bytes, facts.oldest.month, facts.keep) == (2, 15, 10, 7)


# ---- textes et exports ------------------------------------------------------------------

ALL_CODES = ["broken_link", "missing", "missing_library", "not_created_yet", "not_regular", "unreadable",
             "writer_cannot_write", "world_writable", "empty", "silent", "nul_bytes", "undated", "future_dates",
             "over_rotation_threshold", "no_logrotate", "duplicate", "disk_almost_full", "disk_full_soon",
             "no_archives"]


@pytest.mark.parametrize("code", ALL_CODES)
def test_every_code_has_a_sentence(code: str) -> None:
    assert finding_text({"code": code, "level": "info", "params": {}}) != code


def test_hints() -> None:
    fixable = {"code": "writer_cannot_write", "params": {"account": "omega-serv", "new_mode": "664"}}
    assert "Corriger les droits" in (finding_hint(fixable, "/x") or "")
    manual = {"code": "writer_cannot_write", "params": {"account": "omega-serv"}}
    assert finding_hint(manual, "/x") == "sudo chgrp omega-serv /x && sudo chmod g+w /x"


def test_text_and_html_exports_from_the_data_form() -> None:
    report = build_health_report(
        [LogFacts("/a.log", ORIGIN_LIBRARY), _existing(device=1)], [DiskFacts(1, "/", 100, 60)],
        ArchiveFacts("/arch", 2, 2048, NOW - timedelta(days=30), NOW, 7), NOW)
    data = report_to_dict(report)
    text = render_text(data)
    assert "[PROBLÈME] /a.log" in text and "Fichier absent" in text and "2 archive(s)" in text
    html = export_log_health_html(theme_name="omega-dark", **html_arguments(data))
    assert '<html lang="fr" dir="ltr">' in html and "/a.log" in html and "Santé des logs" in html
