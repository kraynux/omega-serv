"""Logs illisibles par votre compte, lus ou corriges avec sudo (2026-11-07) : commandes exactes, `sudo -n`
(jamais de mot de passe hors du terminal), refus de sudo = LogPermissionError, rien d'autre que chgrp/chmod."""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from omega_serv.application.logs import privileged_logs
from omega_serv.application.logs.log_health import HealthTarget, collect_log_health
from omega_serv.application.logs.log_tasks import accumulate_paths, plan_read_tasks
from omega_serv.application.logs.privileged_logs import (
    authenticate,
    read_privileged,
    run_sudo_fix,
    shown_command,
    sudo_fix_commands,
)
from omega_serv.domain.logs.exceptions import LogPermissionError
from omega_serv.domain.logs.health import ORIGIN_LIBRARY
from omega_serv.ports.process_runner_port import ProcessResult


class FakeSudo:
    """Simule sudo : lit le vrai fichier pour `cat`/`head -c`/`tail -c`, note chaque commande."""

    def __init__(self, *, allowed: bool = True, password_ok: bool = True) -> None:
        self.allowed, self.password_ok = allowed, password_ok
        self.calls: list[list[str]] = []

    def run_interactive(self, args: list[str]) -> int:
        self.calls.append(args)
        return 0 if self.password_ok else 1

    def run(self, args: list[str], input_text: str | None = None, timeout: float | None = None) -> ProcessResult:
        self.calls.append(args)
        if not self.allowed:
            return ProcessResult(1, "", "sudo: a password is required")
        assert args[:2] == ["sudo", "-n"]
        command, path = args[2], args[-1]
        data = b""
        if command in ("cat", "head", "tail"):  # le vrai fichier est en 000 : le lire comme sudo le ferait
            Path(path).chmod(0o600)
            data = Path(path).read_bytes()
            Path(path).chmod(0)
        if command == "head":
            data = data[: int(args[4])]
        elif command == "tail":
            data = data[-int(args[4]):]
        return ProcessResult(0, data.decode("utf-8", errors="replace"), "")


@pytest.fixture(autouse=True)
def _not_root(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(privileged_logs, "running_as_root", lambda: False)


@pytest.fixture
def protected_log(tmp_path: Path) -> Path:
    now = datetime.now(timezone.utc)
    log = tmp_path / "auth.log"
    log.write_text("".join(
        f'1.1.1.{i} - - [{(now - timedelta(hours=i)).strftime("%d/%b/%Y:%H:%M:%S")} +0000] "GET / HTTP/1.1" 200 5 "-" "x"\n'
        for i in range(48)))
    log.chmod(0)
    yield log
    log.chmod(0o644)


def _skip_if_root(path: Path) -> None:
    if os.access(path, os.R_OK):
        pytest.skip("compte root : tout est lisible")


def test_authenticate_runs_sudo_v_on_the_terminal() -> None:
    runner = FakeSudo()
    assert authenticate(runner) and runner.calls == [["sudo", "-v"]]
    assert not authenticate(FakeSudo(password_ok=False))


def test_protected_log_is_read_with_sudo_n(protected_log: Path) -> None:
    _skip_if_root(protected_log)
    with pytest.raises(LogPermissionError):
        plan_read_tasks([str(protected_log)])
    runner = FakeSudo()
    total = accumulate_paths([str(protected_log)], period="24h", runner=runner)
    assert total.total == 24  # filtre de periode applique apres la lecture complete
    assert runner.calls == [["sudo", "-n", "cat", "--", str(protected_log)]]


def test_refused_sudo_raises_log_permission_error(protected_log: Path) -> None:
    _skip_if_root(protected_log)
    with pytest.raises(LogPermissionError):
        read_privileged(FakeSudo(allowed=False), str(protected_log))


def test_health_reads_samples_of_unreadable_logs_with_sudo(protected_log: Path) -> None:
    _skip_if_root(protected_log)
    target = [HealthTarget(str(protected_log), ORIGIN_LIBRARY)]
    plain = collect_log_health(target, file_access=None, service_account=None, rotation_max_bytes=None,
                               archives=None, logrotate_patterns=[])
    assert plain.logs[0].facts.last_timestamp is None
    runner = FakeSudo()
    with_sudo = collect_log_health(target, file_access=None, service_account=None, rotation_max_bytes=None,
                                   archives=None, logrotate_patterns=[], privileged_runner=runner)
    facts = with_sudo.logs[0].facts
    assert facts.last_timestamp is not None and facts.detected_source == "access"
    assert [f.code for f in with_sudo.logs[0].findings] == ["unreadable"]  # le constat reste vrai
    assert all(call[:3] in (["sudo", "-n", "head"], ["sudo", "-n", "tail"]) for call in runner.calls)


def test_fix_commands_are_limited_and_shown_exactly() -> None:
    writer = sudo_fix_commands("writer_cannot_write", "/srv/access.log", "omega-serv")
    assert writer == [["chgrp", "omega-serv", "--", "/srv/access.log"], ["chmod", "g+w", "--", "/srv/access.log"]]
    assert shown_command(writer) == "sudo chgrp omega-serv /srv/access.log && sudo chmod g+w /srv/access.log"
    assert sudo_fix_commands("world_writable", "/x", None) == [["chmod", "o-w", "--", "/x"]]
    assert sudo_fix_commands("writer_cannot_write", "/x", None) == []
    assert sudo_fix_commands("silent", "/x", "omega-serv") == []


def test_run_sudo_fix_stops_at_first_error() -> None:
    runner = FakeSudo(allowed=False)
    error = run_sudo_fix(runner, [["chmod", "o-w", "--", "/x"], ["chgrp", "a", "--", "/x"]])
    assert error == "sudo: a password is required" and len(runner.calls) == 1
    ok = FakeSudo()
    assert run_sudo_fix(ok, [["chmod", "o-w", "--", "/nonexistent"]]) is None
    assert ok.calls == [["sudo", "-n", "chmod", "o-w", "--", "/nonexistent"]]


def test_parallel_compute_reads_with_sudo_in_the_main_process(protected_log: Path) -> None:
    """Le pool ne recoit que le texte : le runner (et donc sudo) reste dans le processus principal."""
    import asyncio

    from omega_serv.application.logs.process_pool import warm_up_stats_pool
    from omega_serv.interfaces.tui.screens._parallel_compute import accumulate_in_pool

    _skip_if_root(protected_log)
    warm_up_stats_pool()
    runner = FakeSudo()
    total = asyncio.run(accumulate_in_pool([str(protected_log)], "24h", None, runner))
    assert total.total == 24
    assert runner.calls == [["sudo", "-n", "cat", "--", str(protected_log)]]
