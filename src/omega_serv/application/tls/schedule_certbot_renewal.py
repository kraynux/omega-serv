"""Cas d'usage "planifier/verifier le renouvellement Certbot" (etude
OMEGA-SERV_PLAN-DETAILLE_TLS_AUTO.md, Phase 5). S'adapte au gestionnaire
de service reellement detecte pour CETTE instance (meme sonde que le
registre des capacites, `infrastructure/services/detector.py`) :
systemd -> timer genere et installe depuis l'interface ; sinon -> ligne
crontab (utilisateur courant, aucun privilege requis) si `crontab` est
disponible ; sinon -> instructions manuelles seulement, aucune ecriture.

Jamais un mecanisme global partage entre instances : `service_name`
scope le nom d'unite/la ligne cron (voir domain/security/tls/
renewal_schedule.py) - une instance sans TLS actif n'a simplement jamais
besoin d'appeler ce module."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from omega_serv.domain.security.tls.renewal_schedule import (
    build_renewal_cron_line,
    build_renewal_service_unit,
    build_renewal_timer_unit,
    render_manual_renewal_instructions,
    renewal_cron_marker,
    renewal_unit_base_name,
    replace_marked_cron_line,
)

if TYPE_CHECKING:
    from omega_serv.ports.process_runner_port import ProcessRunnerPort
    from omega_serv.ports.service_manager_port import ServiceManagerPort

_CRONTAB_MISSING_RETURNCODE = 127
_CRONTAB_TIMEOUT_RETURNCODE = 124
_TIMEOUT_SECONDS = 10.0
"""Retour utilisateur 2026-09-21 : meme classe de bug que
infrastructure/services/*_service_manager.py - c'etaient les seuls
appels `process_runner.run()` restants du projet sans timeout (spool/
verrou cron bloque = appel synchrone indefiniment bloque sur le thread
UI, meme si `crontab` ne demande normalement pas de terminal
interactif, donc pas de `_maybe_suspend` necessaire ici)."""


@dataclass(frozen=True)
class ScheduleRenewalResult:
    outcome: Literal["systemd", "cron", "manual", "error"]
    success: bool
    message: str


@dataclass(frozen=True)
class RenewalScheduleStatus:
    mechanism: Literal["systemd", "cron", "none"]
    already_configured: bool
    detail: str


def _uses_systemd(service_manager: ServiceManagerPort | None) -> bool:
    return (
        service_manager is not None
        and service_manager.manager_type() == "systemd"
        and getattr(service_manager, "write_unit_file", None) is not None
    )


def check_renewal_schedule_status(
    service_name: str, service_manager: ServiceManagerPort | None, process_runner: ProcessRunnerPort,
) -> RenewalScheduleStatus:
    if _uses_systemd(service_manager):
        assert service_manager is not None  # garanti par _uses_systemd
        timer_name = f"{renewal_unit_base_name(service_name)}.timer"
        active = service_manager.is_active(timer_name)
        enabled = service_manager.is_enabled(timer_name)
        if active or enabled:
            return RenewalScheduleStatus(
                "systemd", True, f"Timer systemd {timer_name} : actif={active}, active au demarrage={enabled}.",
            )
        return RenewalScheduleStatus("systemd", False, f"Timer systemd {timer_name} non installe (ou inactif).")

    result = process_runner.run(["crontab", "-l"], timeout=_TIMEOUT_SECONDS)
    if result.returncode == _CRONTAB_MISSING_RETURNCODE:
        return RenewalScheduleStatus("none", False, "Aucun mecanisme detecte (ni systemd, ni crontab disponible).")
    if result.returncode == _CRONTAB_TIMEOUT_RETURNCODE:
        return RenewalScheduleStatus("none", False, f"Impossible de verifier crontab : {result.stderr.strip()}")
    marker = renewal_cron_marker(service_name)
    if any(line.rstrip().endswith(marker) for line in result.stdout.splitlines()):
        return RenewalScheduleStatus("cron", True, "Ligne crontab deja installee pour cette instance.")
    return RenewalScheduleStatus("cron", False, "Aucune ligne crontab trouvee pour cette instance.")


def schedule_certbot_renewal(
    service_name: str,
    letsencrypt_dir: Path,
    service_manager: ServiceManagerPort | None,
    systemd_unit_dir: Path,
    process_runner: ProcessRunnerPort,
    installing_user: str,
) -> ScheduleRenewalResult:
    config_dir = str(letsencrypt_dir / "config")
    work_dir = str(letsencrypt_dir / "work")
    logs_dir = str(letsencrypt_dir / "logs")

    if _uses_systemd(service_manager):
        assert service_manager is not None  # garanti par _uses_systemd
        return _schedule_via_systemd(
            service_name, config_dir, work_dir, logs_dir, service_manager, systemd_unit_dir, installing_user,
        )
    return _schedule_via_cron_or_manual(service_name, config_dir, work_dir, logs_dir, process_runner)


def _schedule_via_systemd(
    service_name: str, config_dir: str, work_dir: str, logs_dir: str,
    service_manager: ServiceManagerPort, systemd_unit_dir: Path, installing_user: str,
) -> ScheduleRenewalResult:
    unit_base = renewal_unit_base_name(service_name)
    service_unit_path = systemd_unit_dir / f"{unit_base}.service"
    timer_unit_path = systemd_unit_dir / f"{unit_base}.timer"

    write_unit_file = getattr(service_manager, "write_unit_file", None)
    assert write_unit_file is not None  # garanti par _uses_systemd()
    write_unit_file(
        service_unit_path,
        build_renewal_service_unit(
            certbot_config_dir=config_dir, certbot_work_dir=work_dir, certbot_logs_dir=logs_dir, user=installing_user,
        ),
    )
    write_unit_file(timer_unit_path, build_renewal_timer_unit())

    reload_daemon = getattr(service_manager, "reload_daemon", None)
    if reload_daemon is not None:
        reload_daemon()

    timer_name = f"{unit_base}.timer"
    service_manager.enable(timer_name)
    service_manager.start(timer_name)
    return ScheduleRenewalResult(
        "systemd", True,
        f"Timer systemd installe et actif : {timer_name} (renouvellement deux fois par jour). "
        f"Unites : {service_unit_path}, {timer_unit_path}.",
    )


def _schedule_via_cron_or_manual(
    service_name: str, config_dir: str, work_dir: str, logs_dir: str, process_runner: ProcessRunnerPort,
) -> ScheduleRenewalResult:
    new_line = build_renewal_cron_line(
        service_name=service_name, certbot_config_dir=config_dir, certbot_work_dir=work_dir, certbot_logs_dir=logs_dir,
    )
    list_result = process_runner.run(["crontab", "-l"], timeout=_TIMEOUT_SECONDS)
    if list_result.returncode == _CRONTAB_MISSING_RETURNCODE:
        return ScheduleRenewalResult("manual", False, render_manual_renewal_instructions(cron_line=new_line))
    if list_result.returncode == _CRONTAB_TIMEOUT_RETURNCODE:
        return ScheduleRenewalResult("error", False, f"Impossible de lire la crontab : {list_result.stderr.strip()}")

    existing = list_result.stdout if list_result.returncode == 0 else ""
    updated_crontab = replace_marked_cron_line(existing, service_name, new_line)
    write_result = process_runner.run(["crontab", "-"], input_text=updated_crontab, timeout=_TIMEOUT_SECONDS)
    if write_result.returncode != 0:
        return ScheduleRenewalResult(
            "error", False, f"Echec de l'ecriture de la crontab : {(write_result.stderr or write_result.stdout).strip()}",
        )
    return ScheduleRenewalResult("cron", True, f"Ligne crontab installee (deux fois par jour) : {new_line}")
