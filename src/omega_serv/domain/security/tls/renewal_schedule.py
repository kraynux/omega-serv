"""Planification du renouvellement Certbot (etude
OMEGA-SERV_PLAN-DETAILLE_TLS_AUTO.md, Phase 5) - gabarits texte purs
(meme convention que domain/services/systemd_unit.py : aucune I/O ici).

`certbot renew` (sans argument de domaine) renouvelle TOUS les
certificats deja geres sous le `--config-dir` donne - un seul mecanisme
de planification suffit par instance, jamais un par domaine.

Nom d'unite/ligne cron scoques par `service_name` (jamais par domaine
ni globalement) - retour utilisateur explicite : chaque instance doit
rester distincte dans sa propre configuration (une instance peut ne pas
avoir TLS active du tout), jamais une planification partagee entre
plusieurs instances multi-instance sur la meme machine."""
from __future__ import annotations


def renewal_unit_base_name(service_name: str) -> str:
    return f"{service_name}-certbot-renew"


def build_renewal_service_unit(*, certbot_config_dir: str, certbot_work_dir: str, certbot_logs_dir: str, user: str) -> str:
    return (
        "[Unit]\n"
        "Description=Renouvellement Certbot (OMEGA-SERV, genere - ne pas editer a la main)\n"
        "\n"
        "[Service]\n"
        "Type=oneshot\n"
        f"User={user}\n"
        f"ExecStart=certbot renew --non-interactive --config-dir {certbot_config_dir} "
        f"--work-dir {certbot_work_dir} --logs-dir {certbot_logs_dir}\n"
    )


def build_renewal_timer_unit() -> str:
    return (
        "[Unit]\n"
        "Description=Timer de renouvellement Certbot (OMEGA-SERV, genere - ne pas editer a la main)\n"
        "\n"
        "[Timer]\n"
        "OnCalendar=*-*-* 00,12:00:00\n"
        "RandomizedDelaySec=43200\n"
        "Persistent=true\n"
        "\n"
        "[Install]\n"
        "WantedBy=timers.target\n"
    )


def renewal_cron_marker(service_name: str) -> str:
    return f"# omega-serv-certbot-renew:{service_name}"


def build_renewal_cron_line(*, service_name: str, certbot_config_dir: str, certbot_work_dir: str, certbot_logs_dir: str) -> str:
    command = (
        f"certbot renew --non-interactive --config-dir {certbot_config_dir} "
        f"--work-dir {certbot_work_dir} --logs-dir {certbot_logs_dir}"
    )
    return f"0 0,12 * * * {command}  {renewal_cron_marker(service_name)}"


def replace_marked_cron_line(existing_crontab: str, service_name: str, new_line: str) -> str:
    """Retire toute ligne deja marquee pour CETTE instance (idempotent -
    reconfigurer ne duplique jamais l'entree), puis ajoute la nouvelle a
    la fin. Ne touche jamais une ligne marquee pour une AUTRE instance
    (marqueur distinct par `service_name`, voir `renewal_cron_marker`) -
    plusieurs instances peuvent partager la meme crontab utilisateur
    sans jamais s'ecraser mutuellement."""
    marker = renewal_cron_marker(service_name)
    kept_lines = [line for line in existing_crontab.splitlines() if not line.rstrip().endswith(marker)]
    kept_lines.append(new_line)
    return "\n".join(kept_lines) + "\n"


def render_manual_renewal_instructions(*, cron_line: str) -> str:
    return (
        "Aucun mecanisme de planification automatique detecte sur ce systeme "
        "(ni systemd, ni crontab). Ajoutez cette ligne vous-meme a votre "
        "planificateur habituel (crontab -e, /etc/cron.d/, tache OpenRC/runit "
        "equivalente...) :\n\n"
        f"{cron_line}"
    )
