"""Mise en forme commune des valeurs d'etat (tableau de bord web, lot 4) : utilisee par l'ecran « Etat & Ressources »
du TUI et par le tableau de bord web, pour qu'une taille, une duree ou un temps de reponse s'ecrive partout pareil,
dans la langue de l'interface."""
from __future__ import annotations

from omega_serv.core.i18n import _
from omega_serv.domain.routing.proxy_backend_traffic import InstanceKind


def bytes_to_human(num_bytes: float) -> str:
    units = (_("o"), _("Ko"), _("Mo"), _("Go"))
    for unit in units:
        if num_bytes < 1024:
            return f"{num_bytes:.1f} {unit}"
        num_bytes /= 1024
    return f"{num_bytes:.1f} {_('To')}"


def duration_text(seconds: float) -> str:
    days, rem = divmod(int(seconds), 86400)
    hours, rem = divmod(rem, 3600)
    return _("{days} j {hours} h {minutes} min").format(days=days, hours=hours, minutes=rem // 60)


def instance_kind_label(kind: InstanceKind) -> str:
    return {"site": _("Site"), "php": _("Application PHP"), "proxy": _("Reverse proxy"),
            "mixed": _("Mixte (site + reverse proxy)")}[kind]


def response_time_text(avg_ms: float | None) -> str:
    if avg_ms is None:
        return "-"
    if avg_ms >= 1000:
        return _("{seconds:.2f} s").format(seconds=avg_ms / 1000)
    return _("{ms:.1f} ms").format(ms=avg_ms) if avg_ms < 10 else _("{ms:.0f} ms").format(ms=avg_ms)


def backend_status_text(status: str) -> tuple[str, str]:
    """(libelle, ton) d'un etat de backend ; ton = ok | error | warn. DRAINING et MAINTENANCE gardent le nom des
    boutons de l'ecran « Etat en direct »."""
    if status == "up":
        return _("en service"), "ok"
    if status == "down":
        return _("hors service"), "error"
    return status.upper(), "warn"
