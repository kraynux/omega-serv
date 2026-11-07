"""Automatisations de rotation executees (2026-11-07) : echeances, execution quotidienne, tache planifiee
selon le systeme (timer systemd ; ligne crontab pour OpenRC, runit ou sans gestionnaire ; sinon
instructions) et retrait avec la derniere automatisation."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from omega_serv.application.logs.rotate_log import RotateLogResult
from omega_serv.application.logs.rotation_automation import (
    install_rotation_schedule,
    remove_rotation_schedule,
    rotation_schedule_status,
    run_due_automations,
)
from omega_serv.domain.config.entities import LogsConfig
from omega_serv.domain.logs.rotation_schedule import (
    build_rotation_cron_line,
    build_rotation_service_unit,
    is_due,
    next_run,
)
from omega_serv.infrastructure.logging.rotation_automation_store import RotationAutomationStore
from omega_serv.ports.process_runner_port import ProcessResult

NOW = datetime(2026, 11, 7, 3, 30, tzinfo=timezone.utc)


def _automation(days: int, created_days_ago: int, last_run_days_ago: int | None = None, log_id: str = "access") -> dict:
    item: dict = {"log_id": log_id, "days_interval": days, "interval_label": "x",
                  "created_at": (NOW - timedelta(days=created_days_ago)).isoformat()}
    if last_run_days_ago is not None:
        item["last_run_at"] = (NOW - timedelta(days=last_run_days_ago)).isoformat()
    return item


def test_due_from_creation_then_from_last_run() -> None:
    assert not is_due(_automation(7, 6), NOW)
    assert is_due(_automation(7, 7), NOW)
    assert not is_due(_automation(7, 30, last_run_days_ago=2), NOW)
    assert is_due(_automation(30, 90, last_run_days_ago=31), NOW)
    assert next_run(_automation(7, 6)) == NOW + timedelta(days=1)
    assert not is_due({"log_id": "access"}, NOW)  # donnee incomplete : jamais due


def test_run_due_rotates_and_records(tmp_path: Path) -> None:
    store = RotationAutomationStore(tmp_path / "automations.json")
    store.save_all([_automation(7, 10), _automation(7, 1, log_id="error"), _automation(7, 10, log_id="nope")])
    calls: list[tuple] = []

    def rotate(path: Path, threshold: int, keep: int, archive_dir: Path) -> RotateLogResult:
        calls.append((path, threshold, keep, archive_dir))
        return RotateLogResult(success=True, message="archive écrite")

    runs = run_due_automations(store, LogsConfig(), tmp_path, NOW, rotate)
    assert [(run.log_id, run.success) for run in runs] == [("access", True), ("nope", False)]
    assert calls == [(tmp_path / "var/log/access.log", 0, 7, tmp_path / "var/backups/logs")]
    saved = store.list_all()
    assert saved[0]["last_run_at"] == NOW.isoformat() and saved[0]["last_result"] == "archive écrite"
    assert "last_run_at" not in saved[1]
    assert run_due_automations(store, LogsConfig(), tmp_path, NOW, rotate)[0].log_id == "nope"  # access fait


def test_failed_rotation_stays_due(tmp_path: Path) -> None:
    store = RotationAutomationStore(tmp_path / "automations.json")
    store.save_all([_automation(7, 10)])
    runs = run_due_automations(store, LogsConfig(), tmp_path, NOW,
                               lambda *args: RotateLogResult(success=False, message="disque plein"))
    assert not runs[0].success
    assert is_due(store.list_all()[0], NOW) and store.list_all()[0]["last_result"] == "disque plein"


def test_units_run_as_the_user_never_root() -> None:
    unit = build_rotation_service_unit(python_executable="/p/.venv/bin/python", project_root="/p", user="kray")
    assert "User=kray" in unit and "WorkingDirectory=/p" in unit
    assert "ExecStart=/p/.venv/bin/python -m omega_serv logs run-automations" in unit
    line = build_rotation_cron_line(service_name="omega-serv", python_executable="/p/py", project_root="/p")
    assert line.startswith("30 3 * * * cd /p && /p/py -m omega_serv logs run-automations >> ")
    assert line.endswith("# omega-serv-log-rotation:omega-serv")


class FakeSystemd:
    def __init__(self) -> None:
        self.written: dict[Path, str] = {}
        self.calls: list[tuple] = []

    def manager_type(self) -> str:
        return "systemd"

    def write_unit_file(self, path: Path, content: str) -> None:
        self.written[path] = content
        path.write_text(content)

    def remove_unit_file(self, path: Path) -> None:
        self.calls.append(("rm", path.name))
        path.unlink(missing_ok=True)

    def reload_daemon(self) -> bool:
        return True

    def __getattr__(self, verb: str):
        def act(name: str) -> bool:
            self.calls.append((verb, name))
            return verb in ("enable", "start", "stop", "disable") or (verb == "is_active" and ("start", name) in self.calls)
        return act


class FakeCrontab:
    """`crontab` simule ; `missing` = commande absente (code 127)."""

    def __init__(self, content: str = "", missing: bool = False) -> None:
        self.content, self.missing = content, missing

    def run(self, args: list[str], input_text: str | None = None, timeout: float | None = None) -> ProcessResult:
        if self.missing:
            return ProcessResult(127, "", "crontab : commande introuvable")
        if args == ["crontab", "-l"]:
            return ProcessResult(0 if self.content else 1, self.content, "" if self.content else "no crontab")
        self.content = input_text or ""
        return ProcessResult(0, "", "")


class OpenRc:
    def manager_type(self) -> str:
        return "openrc"


def test_systemd_installs_and_removes_a_timer(tmp_path: Path) -> None:
    systemd = FakeSystemd()
    result = install_rotation_schedule("omega-serv", Path("/p"), "/p/py", systemd, tmp_path, FakeCrontab(), "kray")
    assert result.mechanism == "systemd" and result.success
    assert sorted(path.name for path in systemd.written) == ["omega-serv-log-rotation.service", "omega-serv-log-rotation.timer"]
    assert ("enable", "omega-serv-log-rotation.timer") in systemd.calls
    assert rotation_schedule_status("omega-serv", systemd, FakeCrontab()).success
    removed = remove_rotation_schedule("omega-serv", systemd, tmp_path, FakeCrontab())
    assert removed.success and not (tmp_path / "omega-serv-log-rotation.timer").exists()


def test_openrc_and_runit_use_the_user_crontab_and_keep_other_lines(tmp_path: Path) -> None:
    crontab = FakeCrontab("0 1 * * * autre-tache\n30 3 * * * x  # omega-serv-log-rotation:autre-instance\n")
    result = install_rotation_schedule("omega-serv", Path("/p"), "/p/py", OpenRc(), tmp_path, crontab, "kray")
    assert result.mechanism == "cron" and result.success
    assert crontab.content.count("omega-serv-log-rotation:omega-serv") == 1
    install_rotation_schedule("omega-serv", Path("/p"), "/p/py", OpenRc(), tmp_path, crontab, "kray")
    assert crontab.content.count("omega-serv-log-rotation:omega-serv") == 1  # jamais en double
    assert rotation_schedule_status("omega-serv", OpenRc(), crontab).success
    remove_rotation_schedule("omega-serv", OpenRc(), tmp_path, crontab)
    assert "omega-serv-log-rotation:omega-serv" not in crontab.content
    assert "autre-tache" in crontab.content and "autre-instance" in crontab.content


def test_without_any_scheduler_the_line_is_shown(tmp_path: Path) -> None:
    result = install_rotation_schedule("omega-serv", Path("/p"), "/p/py", None, tmp_path, FakeCrontab(missing=True), "kray")
    assert result.mechanism == "manual" and not result.success
    assert "omega_serv logs run-automations" in result.message


# ---- Sante des logs : automatisations (2026-11-07) ----------------------------------

from omega_serv.domain.logs.health import HealthLevel, evaluate_automations  # noqa: E402


def test_health_flags_missing_schedule_overdue_and_failing() -> None:
    ok = _automation(7, 3)
    overdue = _automation(7, 12)  # due depuis 5 jours, jamais executee
    failing = {**_automation(7, 12), "log_id": "error", "last_result": "Permission denied", "last_success": False}
    health = evaluate_automations([ok, overdue, failing], scheduled=False, now=NOW)
    assert [f.code for f in health.findings] == ["schedule_missing", "automation_overdue", "automation_failing"]
    assert health.level == HealthLevel.WARNING
    assert health.findings[2].params == {"log_id": "error", "days": 5, "error": "Permission denied"}


def test_health_is_quiet_when_everything_runs() -> None:
    assert evaluate_automations([_automation(7, 3), _automation(7, 8)], scheduled=True, now=NOW).findings == []
    assert evaluate_automations([], scheduled=False, now=NOW).findings == []
