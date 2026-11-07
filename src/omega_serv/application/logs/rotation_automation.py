"""Automatisations de rotation EXECUTEES (2026-11-07) : la tache planifiee quotidienne et ce qu'elle fait.

- `run_due_automations` : appelee par `omega-serv logs run-automations` (timer systemd ou ligne crontab).
  Pour chaque automatisation arrivee a echeance, meme geste que « Créer une sauvegarde maintenant » dans
  Rotate / archivage (archive puis log remis a zero, en place) ; date et resultat notes dans
  var/run/log_rotation_automations.json, affiches par l'ecran.
- `install_rotation_schedule` / `remove_rotation_schedule` / `rotation_schedule_status` : la tache
  planifiee elle-meme, une par instance. systemd -> timer (sudo, comme le renouvellement Certbot) ;
  OpenRC, runit ou aucun gestionnaire -> ligne de votre crontab (aucun privilege) ; sans crontab ->
  instructions a suivre soi-meme. Installee a la premiere automatisation, retiree avec la derniere."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from omega_serv.core.i18n import _
from omega_serv.domain.logs.rotation_schedule import (
    build_rotation_cron_line,
    build_rotation_service_unit,
    build_rotation_timer_unit,
    is_due,
    render_manual_rotation_instructions,
    rotation_cron_marker,
    rotation_unit_base_name,
    without_marked_line,
)

if TYPE_CHECKING:
    from omega_serv.application.logs.rotate_log import RotateLogResult
    from omega_serv.domain.config.entities import LogsConfig
    from omega_serv.infrastructure.logging.rotation_automation_store import RotationAutomationStore
    from omega_serv.ports.process_runner_port import ProcessRunnerPort
    from omega_serv.ports.service_manager_port import ServiceManagerPort

_CRONTAB_MISSING = 127
_CRONTAB_TIMEOUT = 124
_TIMEOUT_SECONDS = 10.0


@dataclass(frozen=True)
class AutomationRun:
    log_id: str
    success: bool
    message: str


def run_due_automations(
    store: RotationAutomationStore, logs_config: LogsConfig, project_root: Path, now: datetime,
    rotate: Callable[[Path, int, int, Path], RotateLogResult],
) -> list[AutomationRun]:
    """`rotate(chemin, seuil, nombre_garde, dossier_archives)` = `container.rotate_log_if_needed` (seuil 0 :
    toujours). Une automatisation en echec reste due : elle sera retentee le lendemain."""
    archive_dir = project_root / "var" / "backups" / "logs"
    runs: list[AutomationRun] = []
    automations = store.list_all()
    for automation in automations:
        if not is_due(automation, now):
            continue
        log_id = str(automation.get("log_id", ""))
        relative = getattr(logs_config, log_id, None)
        if not isinstance(relative, str):
            runs.append(AutomationRun(log_id, False, _("Log inconnu : {log_id!r}").format(log_id=log_id)))
            continue
        try:
            result = rotate(project_root / relative, 0, logs_config.rotation.keep, archive_dir)
        except Exception as exc:  # noqa: BLE001 - une automatisation en echec ne bloque jamais les suivantes
            runs.append(AutomationRun(log_id, False, str(exc)))
            automation["last_result"], automation["last_success"] = str(exc), False
            continue
        success, message = result.success, result.message
        runs.append(AutomationRun(log_id, success, message))
        automation["last_result"], automation["last_success"] = message, success
        if success:
            automation["last_run_at"] = now.isoformat()
    if runs:
        store.save_all(automations)
    return runs


# ---- tache planifiee -----------------------------------------------------------------

@dataclass(frozen=True)
class ScheduleResult:
    mechanism: Literal["systemd", "cron", "manual", "error"]
    success: bool
    message: str


def _uses_systemd(service_manager: ServiceManagerPort | None) -> bool:
    return (
        service_manager is not None
        and service_manager.manager_type() == "systemd"
        and getattr(service_manager, "write_unit_file", None) is not None
    )


def uses_systemd(service_manager: ServiceManagerPort | None) -> bool:
    """L'ecran suspend l'interface (sudo) seulement dans ce cas."""
    return _uses_systemd(service_manager)


def rotation_schedule_status(
    service_name: str, service_manager: ServiceManagerPort | None, process_runner: ProcessRunnerPort,
) -> ScheduleResult:
    if _uses_systemd(service_manager):
        assert service_manager is not None
        timer = f"{rotation_unit_base_name(service_name)}.timer"
        if service_manager.is_active(timer) or service_manager.is_enabled(timer):
            return ScheduleResult("systemd", True, _("Exécution : timer systemd {timer} actif (chaque nuit).").format(timer=timer))
        return ScheduleResult("systemd", False, _("Exécution : timer systemd {timer} non installé.").format(timer=timer))
    listing = process_runner.run(["crontab", "-l"], timeout=_TIMEOUT_SECONDS)
    if listing.returncode == _CRONTAB_MISSING:
        return ScheduleResult("manual", False, _("Exécution : aucun planificateur (ni systemd, ni crontab)."))
    marker = rotation_cron_marker(service_name)
    if any(line.rstrip().endswith(marker) for line in listing.stdout.splitlines()):
        return ScheduleResult("cron", True, _("Exécution : ligne crontab installée (chaque nuit)."))
    return ScheduleResult("cron", False, _("Exécution : aucune ligne crontab pour cette instance."))


def install_rotation_schedule(
    service_name: str, project_root: Path, python_executable: str, service_manager: ServiceManagerPort | None,
    systemd_unit_dir: Path, process_runner: ProcessRunnerPort, user: str,
) -> ScheduleResult:
    if _uses_systemd(service_manager):
        assert service_manager is not None
        base = rotation_unit_base_name(service_name)
        write_unit_file = getattr(service_manager, "write_unit_file", None)  # propre a systemd, hors du port
        assert write_unit_file is not None  # garanti par _uses_systemd
        try:
            write_unit_file(systemd_unit_dir / f"{base}.service", build_rotation_service_unit(
                python_executable=python_executable, project_root=str(project_root), user=user))
            write_unit_file(systemd_unit_dir / f"{base}.timer", build_rotation_timer_unit())
            reload_daemon = getattr(service_manager, "reload_daemon", None)
            if reload_daemon is not None:
                reload_daemon()
            service_manager.enable(f"{base}.timer")
            service_manager.start(f"{base}.timer")
        except Exception as exc:  # noqa: BLE001 - sudo refuse, systemd absent... : message, jamais un plantage
            return ScheduleResult("error", False, _("Timer systemd non installé : {error}").format(error=exc))
        return ScheduleResult("systemd", True, _("Timer systemd {timer} installé : les automatisations "
                                                 "s'exécutent chaque nuit.").format(timer=f"{base}.timer"))

    line = build_rotation_cron_line(service_name=service_name, python_executable=python_executable,
                                    project_root=str(project_root))
    listing = process_runner.run(["crontab", "-l"], timeout=_TIMEOUT_SECONDS)
    if listing.returncode == _CRONTAB_MISSING:
        return ScheduleResult("manual", False, render_manual_rotation_instructions(cron_line=line))
    if listing.returncode == _CRONTAB_TIMEOUT:
        return ScheduleResult("error", False, _("Impossible de lire la crontab : {value}").format(value=listing.stderr.strip()))
    kept = without_marked_line(listing.stdout if listing.returncode == 0 else "", service_name)
    written = process_runner.run(["crontab", "-"], input_text="\n".join([*kept, line]) + "\n", timeout=_TIMEOUT_SECONDS)
    if written.returncode != 0:
        return ScheduleResult("error", False, _("Échec de l'écriture de la crontab : {value}").format(
            value=(written.stderr or written.stdout).strip()))
    return ScheduleResult("cron", True, _("Ligne crontab installée : les automatisations s'exécutent chaque nuit."))


def remove_rotation_schedule(
    service_name: str, service_manager: ServiceManagerPort | None, systemd_unit_dir: Path,
    process_runner: ProcessRunnerPort,
) -> ScheduleResult:
    if _uses_systemd(service_manager):
        assert service_manager is not None
        base = rotation_unit_base_name(service_name)
        timer_path = systemd_unit_dir / f"{base}.timer"
        if not timer_path.exists():
            return ScheduleResult("systemd", True, "")
        try:
            service_manager.stop(f"{base}.timer")
            service_manager.disable(f"{base}.timer")
            remove_unit_file = getattr(service_manager, "remove_unit_file", None)  # propre a systemd
            assert remove_unit_file is not None
            remove_unit_file(timer_path)
            remove_unit_file(systemd_unit_dir / f"{base}.service")
            reload_daemon = getattr(service_manager, "reload_daemon", None)
            if reload_daemon is not None:
                reload_daemon()
        except Exception as exc:  # noqa: BLE001 - message, jamais un plantage
            return ScheduleResult("error", False, _("Timer systemd non retiré : {error}").format(error=exc))
        return ScheduleResult("systemd", True, _("Plus aucune automatisation : timer systemd retiré."))
    listing = process_runner.run(["crontab", "-l"], timeout=_TIMEOUT_SECONDS)
    if listing.returncode != 0:
        return ScheduleResult("cron", True, "")
    kept = without_marked_line(listing.stdout, service_name)
    if len(kept) == len(listing.stdout.splitlines()):
        return ScheduleResult("cron", True, "")
    written = process_runner.run(["crontab", "-"], input_text="\n".join(kept) + "\n" if kept else "",
                                 timeout=_TIMEOUT_SECONDS)
    if written.returncode != 0:
        return ScheduleResult("error", False, _("Échec de l'écriture de la crontab : {value}").format(
            value=(written.stderr or written.stdout).strip()))
    return ScheduleResult("cron", True, _("Plus aucune automatisation : ligne crontab retirée."))
