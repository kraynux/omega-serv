"""Page Administration et page de confirmation, tableau de bord web lot 5 (plan §6).

HTML rendu par le serveur, sans JavaScript : chaque bouton est un petit formulaire POST `/action` (jeton CSRF,
champs caches) ; le serveur repond d'abord par une page de confirmation qui dit ce qui va se passer, et n'agit qu'au
second envoi (`confirme=1`). Toute valeur affichee passe par html.escape (raisons de ban, noms de backends)."""
from __future__ import annotations

import html
from collections.abc import Callable, Iterable
from datetime import datetime

from omega_serv.application.admin_web.actions import AdminState
from omega_serv.application.status.formatting import backend_status_text, bytes_to_human
from omega_serv.core.i18n import _

ACTION_FIELDS = ("action", "adresse", "duree", "raison", "reseau", "incident", "zone", "backend", "etat", "journal",
                 "archive")
ACTIONS = ("bannir", "debannir", "fermer_incident", "riposte_arret", "riposte_arret_lever", "riposte_reprise",
           "backend", "archiver", "supprimer_archive", "recharger")


def _e(text: object) -> str:
    return html.escape(str(text))


def duration_labels() -> dict[str, str]:
    return {"1h": _("1 heure"), "6h": _("6 heures"), "24h": _("24 heures"), "7j": _("7 jours"),
            "30j": _("30 jours"), "permanent": _("Permanent")}


def _local(moment: str | datetime | None) -> str:
    if moment is None:
        return _("Permanent")
    try:
        value = moment if isinstance(moment, datetime) else datetime.fromisoformat(moment)
    except ValueError:
        return str(moment)
    return value.astimezone().strftime("%Y-%m-%d %H:%M")


def _hidden(csrf: str, fields: dict[str, str]) -> str:
    items = {"csrf": csrf, **fields}
    return "".join(f'<input type="hidden" name="{_e(key)}" value="{_e(value)}">' for key, value in items.items())


def action_button(csrf: str, fields: dict[str, str], label: str, danger: bool = False) -> str:
    css = ' class="danger"' if danger else ""
    return (f'<form method="post" action="/action" class="inline">{_hidden(csrf, fields)}'
            f'<button type="submit"{css}>{_e(label)}</button></form>')


def _table(headers: Iterable[str], rows: list[list[str]]) -> str:
    head = "".join(f"<th>{_e(h)}</th>" for h in headers)
    body = "".join("<tr>" + "".join(f"<td>{cell}</td>" for cell in row) + "</tr>" for row in rows)
    return f'<div class="table-wrap"><table><tr>{head}</tr>{body}</table></div>'


def _panel(title: str, content: str, hint: str = "") -> str:
    hint_html = f'<p class="hint">{_e(hint)}</p>' if hint else ""
    return f'<section class="panel"><h2>{_e(title)}</h2>{hint_html}{content}</section>'


def _problem(text: str) -> str:
    return f'<p class="hint">{_e(text)}</p>'


# ---------------------------------------------------------------------------------------------- sections
def _bans(state: AdminState, csrf: str) -> str:
    if state.bans_problem and not state.bans:
        return _panel(_("Bannir une adresse IP"), _problem(state.bans_problem))
    options = "".join(f'<option value="{key}"{" selected" if key == "24h" else ""}>{_e(label)}</option>'
                      for key, label in duration_labels().items())
    form = (f'<form method="post" action="/action" class="row-form">{_hidden(csrf, {"action": "bannir"})}'
            f'<label>{_e(_("Adresse IP"))} <input type="text" name="adresse" required size="22"></label>'
            f'<label>{_e(_("Durée"))} <select name="duree">{options}</select></label>'
            f'<label>{_e(_("Raison"))} <input type="text" name="raison" size="24" maxlength="200"></label>'
            f'<button type="submit">{_e(_("Bannir..."))}</button></form>')
    rows = [[_e(ban.network.split("/")[0]), _e(ban.reason), _e(_local(ban.expires_at)),
             action_button(csrf, {"action": "debannir", "reseau": ban.network}, _("Débannir..."))]
            for ban in state.bans]
    listing = _table((_("IP"), _("Raison"), _("Jusqu'au"), ""), rows) if rows else _problem(
        _("Aucun ban posé par l'intervention manuelle."))
    hint = _("Bans de l'intervention manuelle (comme Active Sécurité -> Intervention manuelle). Les bans du WAF, de "
             "RIPOSTE et de la récidive se lèvent là où ils ont été posés.")
    return _panel(_("Bannir une adresse IP"), form + (_problem(state.bans_problem) if state.bans_problem else "")
                  + f"<h3>{_e(_('Bans manuels en place'))}</h3>" + listing, hint)


def _incidents(state: AdminState, csrf: str) -> str:
    if state.incidents_problem:
        return _panel(_("Incidents ouverts"), _problem(state.incidents_problem))
    if not state.incidents:
        return _panel(_("Incidents ouverts"), _problem(_("Aucun incident ouvert.")))
    rows = [[_e(incident.incident_id), _e(incident.subject), _e(_local(incident.opened_at)),
             action_button(csrf, {"action": "fermer_incident", "incident": incident.incident_id}, _("Fermer..."))]
            for incident in state.incidents]
    return _panel(_("Incidents ouverts"), _table((_("Incident"), _("Sujet"), _("Ouvert le"), ""), rows))


def _riposte(state: AdminState, csrf: str) -> str:
    title = _("RIPOSTE")
    if state.riposte_stopped is None:
        return _panel(title, _problem(state.riposte_problem))
    if state.riposte_stopped:
        active = _e(_("Arrêt d'urgence ACTIF : aucune nouvelle action."))
        content = (f'<p class="tone-error">{active}</p>'
                   + action_button(csrf, {"action": "riposte_reprise"}, _("Reprendre...")))
    else:
        content = (f'<p class="tone-ok">{_e(_("RIPOSTE décide normalement."))}</p>'
                   + action_button(csrf, {"action": "riposte_arret"}, _("Arrêter seulement..."), danger=True)
                   + action_button(csrf, {"action": "riposte_arret_lever"},
                                   _("Arrêter et lever les actions en cours..."), danger=True))
    return _panel(title, content)


def _backends(state: AdminState, csrf: str) -> str:
    if not state.backends_shown:
        return ""
    title = _("Backends")
    if state.backends_problem:
        return _panel(title, _problem(state.backends_problem))
    if not state.backends:
        return _panel(title, _problem(_("(aucun backend)")))
    rows = []
    for line in state.backends:
        label, tone = backend_status_text(line.status)
        base = {"action": "backend", "zone": line.zone, "backend": line.name}
        buttons = (action_button(csrf, {**base, "etat": "draining"}, "DRAINING")
                   + action_button(csrf, {**base, "etat": "maintenance"}, "MAINTENANCE")
                   + action_button(csrf, {**base, "etat": "clear"}, _("Automatique")))
        rows.append([_e(line.zone), _e(line.name), f'<span class="tone-{tone}">{_e(label)}</span>', buttons])
    hint = _("DRAINING : plus de nouvelles requêtes, celles en cours finissent. MAINTENANCE : retiré tout de suite. "
             "Automatique : l'état revient à la santé mesurée.")
    return _panel(title, _table((_("Zone"), _("Backend"), _("État"), ""), rows), hint)


def _logs(state: AdminState, csrf: str) -> str:
    rows = [[_e(line.path.name), _e(bytes_to_human(line.size) if line.size is not None else _("absent")),
             action_button(csrf, {"action": "archiver", "journal": line.key}, _("Archiver maintenant..."))
             if line.size is not None else ""]
            for line in state.logs]
    archives = [[_e(a.name), _e(bytes_to_human(a.size)), _e(a.modified),
                 action_button(csrf, {"action": "supprimer_archive", "archive": a.name}, _("Supprimer..."),
                               danger=True)]
                for a in state.archives]
    archive_html = (_table((_("Archive"), _("Taille"), _("Modifiée le"), ""), archives) if archives
                    else _problem(state.archives_problem or _("Aucune archive.")))
    hint = _("Archiver maintenant : copie du journal dans var/backups/logs (archive .tar.gz), puis journal vidé ; les "
             "archives au-delà du nombre gardé (logs.rotation.keep) sont supprimées.")
    return _panel(_("Journaux de l'instance"), _table((_("Journal"), _("Taille"), ""), rows)
                  + f"<h3>{_e(_('Archives'))}</h3>" + archive_html, hint)


def _reload(state: AdminState, csrf: str) -> str:
    hint = _("Relit la configuration sans couper les connexions, comme systemctl reload. Les sessions de "
             "l'administration web restent ouvertes.")
    content = _problem(state.reload_problem) if state.reload_problem else action_button(
        csrf, {"action": "recharger"}, _("Recharger la configuration..."))
    return _panel(_("Configuration"), content, hint)


def admin_page_body(state: AdminState, csrf: str, notice: str, notice_ok: bool) -> str:
    notice_html = ""
    if notice:
        notice_html = f'<p class="notice {"tone-ok" if notice_ok else "error"}">{_e(notice)}</p>'
    intro = _problem(_("Chaque action demande une confirmation et est écrite dans le journal d'audit. Modifier la "
                       "configuration, les comptes ou redémarrer le serveur reste réservé au TUI et à la CLI."))
    return ('<div class="admin">' + notice_html + intro + _bans(state, csrf) + _incidents(state, csrf)
            + _riposte(state, csrf) + _backends(state, csrf) + _logs(state, csrf) + _reload(state, csrf) + "</div>")


# ---------------------------------------------------------------------------------------------- confirmation
def describe(params: dict[str, str], log_name: Callable[[str], str] = str) -> str:
    """Ce que l'action va faire, en clair, pour la page de confirmation."""
    action = params.get("action", "")
    if action == "bannir":
        label = duration_labels().get(params.get("duree", ""), "?")
        text = _("Bannir {ip} : {duration}.").format(ip=params.get("adresse", ""), duration=label)
        reason = params.get("raison", "").strip()
        return text + (" " + _("Raison : {reason}").format(reason=reason) if reason else "")
    if action == "debannir":
        return _("Lever le ban de {ip}.").format(ip=params.get("reseau", "").split("/")[0])
    if action == "fermer_incident":
        return _("Fermer l'incident {incident_id}.").format(incident_id=params.get("incident", ""))
    if action in ("riposte_arret", "riposte_arret_lever"):
        text = _("Arrêt d'urgence de RIPOSTE : plus aucune nouvelle action, pour toutes les règles, même après un "
                 "redémarrage, jusqu'à « Reprendre ».")
        if action == "riposte_arret":
            return text + " " + _("Les actions en cours vont jusqu'à leur échéance.")
        return text + " " + _("Les actions en cours sont levées tout de suite (retrait de la blocklist, libération "
                              "des leurres).")
    if action == "riposte_reprise":
        return _("Lever l'arrêt d'urgence : RIPOSTE reprend ses décisions.")
    if action == "backend":
        status = {"draining": "DRAINING", "maintenance": "MAINTENANCE"}.get(params.get("etat", ""), _("automatique"))
        return _("Passer {name} ({zone}) en {status}.").format(name=params.get("backend", ""),
                                                                zone=params.get("zone", ""), status=status)
    if action == "archiver":
        return _("Archiver maintenant le journal {name} dans var/backups/logs, puis le vider.").format(
            name=log_name(params.get("journal", "")))
    if action == "supprimer_archive":
        return _("Supprimer définitivement {selected_name} ?").format(selected_name=params.get("archive", ""))
    if action == "recharger":
        return _("Recharger la configuration : omega-serv la relit sans couper les connexions (comme systemctl "
                 "reload).")
    return ""


def confirmation_body(params: dict[str, str], warnings: tuple[str, ...], csrf: str,
                      log_name: Callable[[str], str] = str) -> str:
    warnings_html = "".join(f'<p class="tone-warn">{_e(w)}</p>' for w in warnings)
    fields = {key: value for key, value in params.items() if key != "csrf"}
    title = _e(_("Confirmer l'action"))
    return (f'<section class="panel login"><h2>{title}</h2>'
            f'<p>{_e(describe(params, log_name))}</p>{warnings_html}'
            f'<form method="post" action="/action">{_hidden(csrf, {**fields, "confirme": "1"})}'
            f'<button type="submit" class="danger">{_e(_("Confirmer"))}</button></form>'
            f'<p><a href="/">{_e(_("Annuler"))}</a></p></section>')
