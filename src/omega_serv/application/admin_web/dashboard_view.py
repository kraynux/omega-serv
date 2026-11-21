"""Modele de vue du tableau de bord web, lot 4 (OMEGA-SERV_PLAN-DETAILLE_TABLEAU_DE_BORD_WEB.md §4-§5).

Les trois cadres d'« Etat & Ressources » (etat du serveur, flux avec BACKENDS, ressources), mis en sections pretes a
afficher : libelles deja traduits dans la langue de l'instance (decision Q8), memes libelles que le TUI. Le JavaScript
de la page ne fait qu'afficher ces sections, toujours comme du texte (jamais du HTML) : aucune logique de mise en
forme, aucune chaine a traduire cote navigateur.

Une section : titre, lignes « libelle : valeur » (avec un ton : ok, warn, error, dim, strong ; une jauge 0-100 en
option), puis un tableau facultatif (en-tetes, lignes) et une note."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, cast

from omega_serv.application.server.engine_status import engine_connector_rows, engine_status_rows
from omega_serv.application.status.formatting import (
    backend_status_text,
    bytes_to_human,
    duration_text,
    instance_kind_label,
    response_time_text,
)
from omega_serv.application.status.instance_status import (
    KINDS_WITH_BACKENDS,
    BackendsSnapshot,
    ServerStateSnapshot,
    SystemSnapshot,
    TrafficSnapshot,
)
from omega_serv.core.i18n import _

_TONES = {"green": "ok", "yellow": "warn", "red": "error", "dim": "dim", "": ""}


@dataclass
class Row:
    label: str
    value: str
    tone: str = ""
    gauge: float | None = None


@dataclass
class Section:
    title: str
    rows: list[Row] = field(default_factory=list)
    headers: list[str] = field(default_factory=list)
    table: list[list[str]] = field(default_factory=list)
    note: str = ""

    def row(self, label: str, value: object, tone: str = "", gauge: float | None = None) -> Section:
        self.rows.append(Row(label, str(value), tone, gauge))
        return self


def sections_payload(sections: list[Section]) -> dict[str, Any]:
    return {"sections": [asdict(section) for section in sections]}


def _time(value: datetime | None, fmt: str = "%Y-%m-%d %H:%M") -> str:
    return value.astimezone().strftime(fmt) if value is not None else "-"


def _gauge_tone(percent: float) -> str:
    return "ok" if percent < 50 else ("warn" if percent < 95 else "error")


# ---------------------------------------------------------------------------------------------- etat du serveur


def server_state_sections(state: ServerStateSnapshot) -> list[Section]:
    sections = []
    if state.config is not None:
        sections.append(Section("").row(_("Type d'instance"), instance_kind_label(state.config.kind), "strong"))
    process = Section(_("PROCESSUS"))
    pid = state.process.pid
    if pid is not None and state.process.running:
        process.row(_("Statut"), _("DÉMARRÉ (PID {pid})").format(pid=pid), "ok")
    elif pid is not None:
        process.row(_("Statut"), _("ARRÊTÉ (PID {pid} obsolète)").format(pid=pid), "warn")
    else:
        process.row(_("Statut"), _("ARRÊTÉ (aucun fichier PID)"), "dim")
    sections.append(process)

    service = Section(_("SERVICE SYSTÈME"))
    if not state.service.manager_found:
        service.note = _("Aucun gestionnaire de service reconnu")
    elif state.service.status is not None:
        status = state.service.status
        tone = "ok" if status.is_running else ("error" if status.is_failed else "warn")
        service.row(_("Actif"), status.active, tone).row(_("Démarrage auto"), status.enabled)
        service.row(_("État"), f"{status.state} ({status.sub_state})")
    else:
        service.row(_("ERREUR STATUT"), state.service.error or "", "error")
    sections.append(service)

    instances = Section(_("INSTANCE"), headers=[_("Nom"), _("Statut")])
    instances.row(_("Nombre"), state.instances.count).row(_("Cette instance"), state.instances.current_name)
    for entry in state.instances.rows:
        name = _("{name} (courante)").format(name=entry.name) if entry.current else entry.name
        status_text = (_("PID {pid}").format(pid=entry.pid) if entry.pid is not None
                       else _("PID illisible") if entry.unreadable else _("arrêtée"))
        instances.table.append([name, status_text])
    sections.append(instances)

    backup = Section(_("SAUVEGARDE"))
    if state.latest_backup is not None:
        backup.row(_("Dernière"), _time(state.latest_backup)).row(_("Nombre"), state.backup_count)
    elif state.backups_unreadable:
        backup.note = _("Réservées au propriétaire de l'instance : visibles dans le TUI.")
    else:
        backup.note = _("Aucune sauvegarde")
    sections.append(backup)

    config = state.config
    active = Section(_("CONFIGURATION ACTIVE"))
    if config is None:
        active.row(_("Erreur de configuration : "), "; ".join(state.config_errors), "error")
        sections.append(active)
        return sections
    tls = _("activé ({mode})").format(mode=config.tls_mode) if config.tls_enabled else _("désactivé")
    active.row(_("Profil"), config.profile).row(_("Écoute"), f"{config.bind}:{config.port}").row(_("TLS"), tls)
    sections.append(active)

    engine = Section(_("MOTEUR HTTP"))
    for label, value, style in engine_status_rows(config.engine):
        engine.row(label, value, _TONES.get(style, ""))
    sections.append(engine)
    connectors = engine_connector_rows(config.engine)
    if connectors:
        section = Section(_("CONNECTEURS (NATIF)"))
        for label, value, style in connectors:
            section.row(label, value, _TONES.get(style, ""))
        sections.append(section)
    options = Section(_("CONFIGURATION OPTIONS"))
    options.note = _("Options actives ({enabled}/{known}) :").format(enabled=len(config.enabled_options),
                                                                     known=config.known_options)
    options.table = [[name] for name in config.enabled_options] or [[_("(aucune)")]]
    sections.append(options)
    return sections


# ---------------------------------------------------------------------------------------------- flux


def traffic_sections(traffic: TrafficSnapshot, backends: BackendsSnapshot | None, banned: tuple[int, int] | None,
                     python_processes: int = 1) -> list[Section]:
    stats = traffic.stats
    since = Section(_("RENDEMENT"))
    since.note = _("Depuis {time} (15 min relues à l'ouverture)").format(time=_time(traffic.since, "%H:%M"))
    since.row(_("Dernière minute"), _("{rate:.2f} req/s").format(rate=stats.rps_1m))
    since.row(_("5 dernières min"), _("{rate:.2f} req/s").format(rate=stats.rps_5m))
    since.row(_("Moyenne"), _("{rate:.2f} req/s").format(rate=stats.rps))
    since.row(_("Volume"), _("{size}/s").format(size=bytes_to_human(stats.bps)))
    sections = [since]

    rate_tone = "ok" if stats.error_rate < 5 else ("warn" if stats.error_rate < 15 else "error")
    statuses = Section(_("STATUTS HTTP")).row(_("Total"), stats.total).row(_("Succès 2xx"), stats.success_2xx, "ok")
    statuses.row(_("Redirections 3xx"), stats.redirect_3xx).row(_("Erreurs 4xx"), stats.errors_4xx, "warn")
    statuses.row(_("Erreurs 5xx"), stats.errors_5xx, "error")
    statuses.row(_("Taux d'erreur"), f"{stats.error_rate:.1f}%", rate_tone)
    statuses.row(_("Taille moy."), bytes_to_human(stats.avg_size))
    sections.append(statuses)

    security = Section(_("SÉCURITÉ"))
    if not traffic.waf_active:
        security.row(_("WAF"), _("inactif"), "dim")
    else:
        attacks = traffic.waf_counts.get("attack", 0)
        security.row(_("Attaques bloquées"), attacks, "error" if attacks else "")
        security.row(_("Refus liste blocage"), traffic.waf_counts.get("blocklist_hit", 0))
        security.row(_("Limite de débit"), traffic.waf_counts.get("rate_limited", 0))
    security.row(_("Refus 403"), stats.forbidden_403).row(_("Refus 429"), stats.rate_limited_429)
    if banned is not None:
        security.row(_("IP bannies"), _("{count} (dont RIPOSTE : {riposte})").format(count=banned[0],
                                                                                     riposte=banned[1]))
    sections.append(security)

    clients = Section(_("CLIENTS"), headers=[_("Requêtes"), "IP"])
    clients.row(_("IPs uniques"), stats.unique_ips)
    clients.table = [[str(count), ip] for ip, count in stats.top_ips]
    sections.append(clients)

    if backends is not None and backends.kind in KINDS_WITH_BACKENDS:
        sections.append(backends_section(backends, python_processes))

    for title, items in ((_("CHEMINS LES PLUS DEMANDÉS"), stats.top_paths), (_("CHEMINS EN 404"), stats.top_not_found)):
        section = Section(title, headers=[_("Requêtes"), _("Chemin")])
        section.table = [[str(count), path] for path, count in items]
        if not items:
            section.note = _("(aucun)")
        sections.append(section)

    recent = Section(_("DERNIÈRES REQUÊTES"), headers=[_("Heure"), "IP", _("Statut"), _("Chemin")])
    recent.table = [[_time(entry.timestamp, "%H:%M:%S"), entry.ip, str(entry.status_code), entry.path or "-"]
                    for entry in stats.recent]
    if not stats.recent:
        recent.note = _("(aucune)")
    sections.append(recent)
    return sections


def backends_section(snapshot: BackendsSnapshot, python_processes: int = 1) -> Section:
    section = Section(_("BACKENDS"), headers=[_("Zone"), _("Backend"), _("État"), _("Requêtes"), _("En cours"),
                                              "502 / 504", _("Temps moyen")])
    if snapshot.rows is None:
        if snapshot.problem == "stopped":
            section.note = _("Serveur arrêté ou injoignable.")
        elif snapshot.problem == "refused":
            section.note = _("Administration refusée : ajoutez 127.0.0.1 aux réseaux de confiance (trusted_proxy).")
        elif snapshot.problem == "unexpected":
            section.note = _("Réponse inattendue du serveur (statut {status}).").format(status=snapshot.status)
        return section
    if not snapshot.rows:
        section.note = _("(aucun backend)")
    for row in snapshot.rows:
        engine = _("natif") if row.engine == "natif" else "Python"
        label, _tone = backend_status_text(row.status)
        section.table.append([f"{row.zone} · {engine}", row.address, label, str(row.requests), str(row.active),
                              f"{row.errors_502} / {row.errors_504}", response_time_text(row.avg_ms)])
    if python_processes > 1 and any(row.engine == "python" for row in snapshot.rows):
        section.note = _("Zones servies par Python avec plusieurs processus : chiffres d'un seul processus.")
    return section


# ---------------------------------------------------------------------------------------------- ressources


def system_sections(snapshot: SystemSnapshot) -> list[Section]:
    server, machine = snapshot.server, snapshot.machine
    omega = Section(_("OMEGA-SERV"))
    if server.get("running"):
        omega.row(_("Processus"), _("{count} (PID {pid})").format(count=server["process_count"], pid=server["pid"]),
                  "ok")
        omega.row(_("CPU"), f"{server['cpu_percent']:.1f}%").row(_("RAM"), bytes_to_human(server["rss"]))
        omega.row(_("Fils"), server["threads"])
        omega.row(_("Fichiers ouverts"), server["open_files"] if server["open_files"] is not None
                  else _("N/D (compte du service)"))
        omega.row(_("Lancé depuis"), duration_text(server["uptime_seconds"]))
    else:
        omega.row(_("Processus"), _("arrêté"), "dim")
    connections = server.get("connections")
    omega.row(_("Connexions"), f"{connections}  (:{server['port']})" if connections is not None else _("N/D"))
    if server.get("running"):
        omega.row(_("Envoyé"), bytes_to_human(snapshot.sent_total) if snapshot.sent_total is not None
                  else _("calcul en cours..."))
    omega.row(_("Journaux"), bytes_to_human(server.get("log_total", 0)))
    if server.get("state_free") is not None and server.get("state_total"):
        free_percent = 100.0 * server["state_free"] / server["state_total"]
        omega.row(_("Libre (var/)"), f"{bytes_to_human(server['state_free'])} / {bytes_to_human(server['state_total'])}",
                  _gauge_tone(100.0 - free_percent), 100.0 - free_percent)
    sections = [omega]

    box = Section(_("MACHINE"))
    for label, percent_key, used, total in ((_("CPU"), "cpu_percent", None, None),
                                            (_("RAM"), "mem_percent", "mem_used", "mem_total"),
                                            (_("Disque"), "disk_percent", "disk_used", "disk_total"),
                                            (_("Swap"), "swap_percent", "swap_used", "swap_total")):
        percent = float(machine.get(percent_key, 0.0))
        detail = f"{percent:.1f}%"
        if used is not None:
            detail += f" ({bytes_to_human(machine[used])} / {bytes_to_human(machine[cast(str, total)])})"
        box.row(label, detail, _gauge_tone(percent), percent)
    cores = max(1, int(machine.get("cpu_count") or 1))
    load = " ".join(f"{machine[key]:.2f}" for key in ("load_1", "load_5", "load_15") if key in machine)
    box.row(_("Charge"), f"{load} " + _("({count} cœurs)").format(count=cores))
    box.row(_("Processus"), machine.get("num_processes", "-")).row(_("Uptime"),
                                                                   duration_text(machine.get("uptime_seconds", 0)))
    sections.append(box)

    network = Section(_("RÉSEAU"))
    if snapshot.net_rate is None:
        network.row(_("Débit"), _("mesure en cours..."))
    else:
        down, up = snapshot.net_rate
        network.row(_("Débit"), f"↓{bytes_to_human(down)}/s  ↑{bytes_to_human(up)}/s")
    users = machine.get("user_names") or []
    network.row(_("TCP établies"), machine.get("tcp_established", "-"))
    network.row(_("IP sortante"), machine.get("outbound_ip", "-"))
    network.row(_("Passerelle"), machine.get("gateway") or _("N/D"))
    network.row(_("Utilisateurs"), ", ".join(users) if users else _("aucun"))
    sections.append(network)

    links = Section(_("INTERFACES"), headers=[_("Interface"), _("Type"), _("Adresse")])
    for link in machine.get("links") or []:
        address = (link["ip"] or _("sans IP")) if link["up"] else _("déconnectée")
        links.table.append([link["name"], link["kind"], address])
    if not links.table:
        links.note = _("(aucune)")
    sections.append(links)
    return sections


# ---------------------------------------------------------------------------------------------- securite


@dataclass(frozen=True)
class SecurityFacts:
    """Ce que le processus d'administration a lu (bans, RIPOSTE, incidents) ; un probleme = un texte a afficher a la
    place, jamais une exception."""
    bans: list[dict[str, str]] = field(default_factory=list)
    bans_problem: str = ""
    riposte_lines: list[str] | None = None
    riposte_problem: str = ""
    incidents: list[tuple[str, str, str, datetime, datetime | None]] = field(default_factory=list)
    """(identifiant, sujet, statut, ouvert le, ferme le)."""
    incidents_problem: str = ""


def security_sections(facts: SecurityFacts, ban_limit: int = 200, incident_limit: int = 100) -> list[Section]:
    bans = Section(_("BANS"), headers=[_("Adresse / réseau"), _("Origine"), _("État"), _("Expiration"), _("Posé le"),
                                       _("Motif du ban")])
    bans.table = [[row["network"], row["origin"], row["state"], row["expires"], row["created"], row["reason"]]
                  for row in facts.bans[:ban_limit]]
    bans.note = facts.bans_problem or (_("Aucun ban.") if not facts.bans else
                                       _("{shown} affiché(s) sur {count}.").format(shown=min(ban_limit, len(facts.bans)),
                                                                                  count=len(facts.bans)))
    riposte = Section(_("RIPOSTE"))
    if facts.riposte_lines is None:
        riposte.note = facts.riposte_problem or _("RIPOSTE inactif.")
    else:
        riposte.table = [[line] for line in facts.riposte_lines]
    incidents = Section(_("INCIDENTS"), headers=[_("Incident"), _("Sujet"), _("Statut"), _("Ouvert le"),
                                                 _("Fermé le")])
    open_count = sum(1 for item in facts.incidents if item[2] == "open")
    incidents.row(_("Ouverts"), open_count, "warn" if open_count else "")
    incidents.row(_("Fermés"), len(facts.incidents) - open_count)
    incidents.table = [[ident, subject, status, _time(opened), _time(closed)]
                       for ident, subject, status, opened, closed in facts.incidents[:incident_limit]]
    if facts.incidents_problem:
        incidents.note = facts.incidents_problem
    return [bans, riposte, incidents]
