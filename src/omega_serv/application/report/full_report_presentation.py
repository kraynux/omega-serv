# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Presentation du rapport complet dans la langue du processus (interface, ou enfant d'export dans une autre langue) :
sections (titre, lignes libelle/valeur), texte brut, arguments du gabarit HTML."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from omega_serv.core.i18n import _


def _yes_no(value: object) -> str:
    return _("oui") if value else _("non")


def _size(value: Any) -> str:
    size = float(value or 0)
    units = (_("o"), _("Kio"), _("Mio"), _("Gio"))
    for index, unit in enumerate(units):
        if size < 1024 or index == len(units) - 1:
            return f"{size:.0f} {unit}" if index == 0 else f"{size:.1f} {unit}"
        size /= 1024
    return str(value)


def _uptime(started: str | None, generated: str) -> str:
    if not started:
        return "-"
    try:
        seconds = int((datetime.fromisoformat(generated) - datetime.fromisoformat(started)).total_seconds())
    except ValueError:
        return "-"
    days, rest = divmod(max(seconds, 0), 86400)
    hours, rest = divmod(rest, 3600)
    return _("{days} j {hours} h {minutes} min").format(days=days, hours=hours, minutes=rest // 60)


def _mode(code: str) -> str:
    return {"web": _("site web"), "proxy": _("reverse proxy"), "both": _("site web et reverse proxy")}.get(code, code)


def sections(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """[{title, rows: [(libelle, valeur)], lines: [texte]}] - minimum puis detail present dans la charge."""
    identity, service, listen = payload.get("identity", {}), payload.get("service", {}), payload.get("listen", {})
    tls, counts, security = payload.get("tls", {}), payload.get("counts", {}), payload.get("security", {})
    checks, backups, logs = payload.get("checks", {}), payload.get("backups", {}), payload.get("logs", {})
    generated = str(identity.get("generated_at", ""))
    profile = identity.get("profile", "")
    if identity.get("profile_label"):
        profile = f"{profile} ({identity['profile_label']})"
    out: list[dict[str, Any]] = [
        {"title": _("Identité"), "rows": [
            (_("Instance"), identity.get("instance", "")), (_("Dossier"), identity.get("path", "")),
            (_("Version"), identity.get("app_version", "")), (_("Profil appliqué"), profile),
            (_("Machine"), identity.get("hostname", "")), (_("Rapport généré le"), generated)]},
        {"title": _("Fonctionnement"), "rows": [
            (_("Service"), service.get("name", "")),
            (_("Gestionnaire"), service.get("manager") or _("aucun")),
            (_("Unité installée"), _yes_no(service.get("unit_installed"))),
            (_("En marche"), _yes_no(service.get("running"))),
            (_("Activé au démarrage"), _yes_no(service.get("enabled"))),
            (_("Uptime"), _uptime(service.get("started_at"), generated)),
            (_("Compte du service"), service.get("account") or "-"),
            (_("Processus"), str(service.get("workers", "")))]},
        {"title": _("Écoute et mode"), "rows": [
            (_("Adresse et port"), f"{listen.get('bind', '')}:{listen.get('port', '')}"),
            (_("Mode"), _mode(str(listen.get("mode", "")))),
            (_("Moteur utilisé"), listen.get("engine", "")),
            *([(_("Raison du repli"), "; ".join(listen["fallback_reasons"]))] if listen.get("fallback_reasons") else []),
            *[(_("Zone {prefix}").format(prefix=prefix), label) for prefix, label in listen.get("zone_engines", {}).items()]]},
        {"title": "TLS", "rows": [
            (_("Activé"), _yes_no(tls.get("enabled"))), (_("Mode"), tls.get("mode") or "-"),
            (_("Certificat"), tls.get("certificate_path") or "-"), (_("Émetteur"), tls.get("issuer") or "-"),
            (_("Expiration"), tls.get("expires_at") or "-"),
            (_("Jours restants"), str(tls["days_remaining"]) if tls.get("days_remaining") is not None else "-"),
            ("HSTS", _yes_no(tls.get("hsts")))]},
        {"title": _("Options"), "rows": [
            (name, _("active") if enabled else _("inactive")) for name, enabled in sorted(payload.get("options", {}).items())]},
        {"title": _("Configuration, en nombres"), "rows": [
            (_("Alias"), str(counts.get("aliases", 0))), (_("Redirections"), str(counts.get("redirects", 0))),
            (_("Rewrites"), str(counts.get("rewrites", 0))), (_("Zones FastCGI"), str(counts.get("fastcgi_zones", 0))),
            (_("Zones d'envoi"), str(counts.get("upload_zones", 0))),
            (_("Zones reverse proxy"), str(counts.get("proxy_zones", 0))),
            (_("Backends"), str(counts.get("proxy_backends", 0))),
            (_("Règles de contrôle d'accès"), str(counts.get("access_rules", 0))),
            (_("Cache"), _yes_no(counts.get("cache_enabled"))),
            (_("Pages d'erreur personnalisées"), _yes_no(counts.get("custom_error_pages")))]},
        {"title": _("Sécurité, résumé"), "rows": [
            (_("WAF"), (security.get("waf_mode") or "-") if security.get("waf") else _("inactif")),
            (_("Packs de règles WAF"), str(security.get("waf_packs", 0))),
            (_("Active Defense"), _yes_no(security.get("active_defense"))),
            ("RIPOSTE", _yes_no(security.get("riposte"))),
            (_("Adresses bannies (actives)"), "-" if security.get("banned_active") is None
             else str(security["banned_active"])),
            (_("Zones d'authentification"), str(security.get("auth_zones", 0))),
            (_("En-têtes de sécurité"), _yes_no(security.get("security_headers"))),
            ("CSP", str(security.get("csp_mode", "")))]},
        {"title": _("Contrôles"), "rows": [
            (_("Erreurs"), str(len(checks.get("errors", [])))), (_("Avertissements"), str(len(checks.get("warnings", []))))],
         "lines": [*checks.get("errors", []), *checks.get("warnings", [])]},
        {"title": _("Sauvegardes"), "rows": [
            (_("Nombre"), str(backups.get("count", 0))), (_("Dernière"), backups.get("last_date") or "-"),
            (_("Contenu de la dernière"), backups.get("last_scope") or "-"),
            (_("Place occupée"), _size(backups.get("total_bytes", 0)))]},
        {"title": _("Journaux"), "rows": [
            (_("Dossier"), logs.get("dir", "")), (_("Place occupée"), _size(logs.get("total_bytes", 0)))]},
    ]
    details = payload.get("details", {})
    titles = {"zones": _("Détail des zones"), "reverse_proxy": _("Reverse proxy"), "waf": _("Règles WAF"),
              "active_defense": _("Active Defense et RIPOSTE"), "logs_library": _("Journaux suivis"),
              "options_settings": _("Réglages des options"), "audit": _("Audit de sécurité")}
    for key, title in titles.items():
        if key in details:
            out.append({"title": title, "rows": [], "lines": _detail_lines(details[key])})
    return out


def _detail_lines(value: Any, indent: str = "") -> list[str]:
    if isinstance(value, dict):
        lines: list[str] = []
        for key, item in value.items():
            if isinstance(item, (dict, list)) and item:
                lines.append(f"{indent}{key} :")
                lines.extend(_detail_lines(item, indent + "  "))
            else:
                lines.append(f"{indent}{key} : {item}")
        return lines
    if isinstance(value, list):
        lines = []
        for item in value:
            sub = _detail_lines(item, indent + "  ")
            if sub:
                lines.append(f"{indent}- {sub[0].strip()}")
                lines.extend(sub[1:])
        return lines
    return [f"{indent}{value}"]


def render_text(payload: dict[str, Any]) -> str:
    lines = [_("OMEGA-SERV - RAPPORT COMPLET"), ""]
    for section in sections(payload):
        lines.append(f"== {section['title']} ==")
        width = max((len(str(label)) for label, _value in section["rows"]), default=0)
        lines.extend(f"  {str(label).ljust(width)}  {value}" for label, value in section["rows"])
        lines.extend(f"  {line}" for line in section.get("lines", []))
        lines.append("")
    return "\n".join(lines)


def summary_markup(payload: dict[str, Any]) -> str:
    """Sommaire a l'ecran : le minimum, une ligne par reglage (le detail reste dans l'export)."""
    out: list[str] = []
    for section in sections(payload)[:10]:
        out.append(f"[b]{section['title']}[/b]")
        out.extend(f"  {label} : {value}" for label, value in section["rows"])
        out.append("")
    return "\n".join(out)


def html_arguments(payload: dict[str, Any]) -> dict[str, Any]:
    return {"sections": sections(payload), "generated_at": payload.get("identity", {}).get("generated_at", "")}
