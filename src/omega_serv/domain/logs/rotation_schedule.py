"""Execution reelle des automatisations de rotation (2026-11-07, demande utilisateur : « oui pour une
construction d'automatisation ») - jusqu'ici, Rotate / archivage ENREGISTRAIT seulement l'intention
(infrastructure/logging/rotation_automation_store.py), rien ne l'executait.

Une seule tache planifiee par instance, une fois par jour : `python -m omega_serv logs run-automations`, qui
fait tourner chaque log dont l'automatisation est arrivee a echeance. Meme mecanisme que le renouvellement
Certbot (domain/security/tls/renewal_schedule.py) : timer systemd, sinon ligne crontab de votre compte
(OpenRC, runit, sans gestionnaire), sinon ligne a ajouter soi-meme. Gabarits purs, aucune I/O ici."""
from __future__ import annotations

from datetime import datetime, timedelta

from omega_serv.core.i18n import _


def is_due(automation: dict, now: datetime) -> bool:
    """Echeance = derniere execution (ou creation) + intervalle en jours. Donnee illisible : jamais due."""
    try:
        reference = datetime.fromisoformat(str(automation.get("last_run_at") or automation["created_at"]))
        interval = int(automation["days_interval"])
    except (KeyError, TypeError, ValueError):
        return False
    return now >= reference + timedelta(days=interval)


def next_run(automation: dict) -> datetime | None:
    try:
        reference = datetime.fromisoformat(str(automation.get("last_run_at") or automation["created_at"]))
        return reference + timedelta(days=int(automation["days_interval"]))
    except (KeyError, TypeError, ValueError):
        return None


def rotation_unit_base_name(service_name: str) -> str:
    return f"{service_name}-log-rotation"


def rotation_command(python_executable: str) -> str:
    return f"{python_executable} -m omega_serv logs run-automations"


def build_rotation_service_unit(*, python_executable: str, project_root: str, user: str) -> str:
    """Lance sous VOTRE compte (proprietaire du projet, comme l'ecran Rotate) : jamais root, sinon les
    archives de var/backups/logs/ deviendraient illisibles pour l'interface."""
    return (
        "[Unit]\n"
        "Description=Rotation planifiée des logs (OMEGA-SERV, généré - ne pas éditer à la main)\n"
        "\n"
        "[Service]\n"
        "Type=oneshot\n"
        f"User={user}\n"
        f"WorkingDirectory={project_root}\n"
        f"ExecStart={rotation_command(python_executable)}\n"
    )


def build_rotation_timer_unit() -> str:
    return (
        "[Unit]\n"
        "Description=Timer de rotation des logs (OMEGA-SERV, généré - ne pas éditer à la main)\n"
        "\n"
        "[Timer]\n"
        "OnCalendar=*-*-* 03:30:00\n"
        "RandomizedDelaySec=1800\n"
        "Persistent=true\n"
        "\n"
        "[Install]\n"
        "WantedBy=timers.target\n"
    )


def rotation_cron_marker(service_name: str) -> str:
    return f"# omega-serv-log-rotation:{service_name}"


def build_rotation_cron_line(*, service_name: str, python_executable: str, project_root: str) -> str:
    """Sortie ajoutee a var/log/log-rotation-automations.log : cron n'envoie jamais de courriel pour rien."""
    log = f"{project_root}/var/log/log-rotation-automations.log"
    command = f"cd {project_root} && {rotation_command(python_executable)} >> {log} 2>&1"
    return f"30 3 * * * {command}  {rotation_cron_marker(service_name)}"


def without_marked_line(existing_crontab: str, service_name: str) -> list[str]:
    """Lignes de la crontab sauf celle de CETTE instance (une autre instance garde la sienne)."""
    marker = rotation_cron_marker(service_name)
    return [line for line in existing_crontab.splitlines() if not line.rstrip().endswith(marker)]


def render_manual_rotation_instructions(*, cron_line: str) -> str:
    return _("Aucun planificateur détecté (ni systemd, ni crontab). Ajoutez cette ligne vous-même à votre "
             "planificateur (crontab -e, /etc/cron.d/, tâche OpenRC ou runit équivalente) :\n\n{cron_line}").format(
        cron_line=cron_line)
