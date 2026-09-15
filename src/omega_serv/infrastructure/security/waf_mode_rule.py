# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""WAF-001 (plan corrige §5.2, puis suite 2026-09-06) : signale un WAF
maintenu en mode 'log-only' depuis trop longtemps.

Bloquant initial (voir la version corrigee du plan) : aucune donnee ne
date le passage en 'log-only' ailleurs dans le projet - `WafConfig` ne
porte aucun horodatage, et aucune commande CLI ne modifie
`options.waf.settings.mode` directement aujourd'hui (seul un edit JSON
manuel le fait). Decision retenue : cette regle d'audit EST elle-meme
le point d'observation, pas une commande dediee.

A chaque execution de `omega-serv audit security`, elle compare le mode
WAF actuel au dernier mode observe (stocke dans
`var/run/waf-mode-state.json`) :
- mode different du dernier observe (ou fichier absent) : nouvel etat
  enregistre avec `since = maintenant`, aucun finding cette fois - on
  vient de commencer a observer cette transition, sa duree est encore
  inconnue.
- mode identique : la duree ecoulee depuis `since` est comparee au
  seuil.

Limite assumee et documentee, pas cachee : si l'audit n'est jamais
execute entre deux changements de mode, la transition intermediaire est
invisible - cette regle ne connait que ce qu'elle a elle-meme observe,
pas l'historique complet de la configuration. C'est le seul ecrit sur
disque effectue par l'outil d'audit (sinon strictement en lecture
seule) - assume explicitement ici, pas une consequence accidentelle."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from omega_serv.domain.config.entities import OmegaServConfig
from omega_serv.domain.security.audit.entities import AuditFinding, Severity
from omega_serv.ports.clock_port import ClockPort
from omega_serv.ports.filesystem_port import FilesystemPort

_LOG_ONLY_WARN_DAYS = 14


def check_waf_log_only_duration(
    config: OmegaServConfig,
    project_root: Path,
    filesystem: FilesystemPort,
    clock: ClockPort,
) -> list[AuditFinding]:
    waf_option = config.options.get("waf")
    if waf_option is None or not waf_option.enabled:
        return []
    mode = waf_option.settings.get("mode", "log-only")

    state_path = project_root / "var" / "run" / "waf-mode-state.json"
    now = clock.now()
    stored_mode, stored_since = _read_state(filesystem, state_path)

    if stored_mode != mode:
        _write_state(filesystem, state_path, mode, now)
        return []

    if mode != "log-only" or stored_since is None:
        return []

    days_in_mode = (now - stored_since).days
    if days_in_mode < _LOG_ONLY_WARN_DAYS:
        return []

    return [AuditFinding(
        rule_id="WAF-001", rule_name="WAF en mode log-only depuis trop longtemps",
        severity=Severity.HIGH, category="waf",
        message=f"options.waf.settings.mode = 'log-only' depuis au moins {days_in_mode} jour(s) (observe(s) par l'audit).",
        recommendation=(
            "Passer en mode 'block' une fois les faux positifs stabilises, "
            "ou justifier explicitement le maintien en log-only."
        ),
        details={"days_in_mode": days_in_mode, "since": stored_since.isoformat()},
    )]


def _read_state(filesystem: FilesystemPort, path: Path) -> tuple[str | None, datetime | None]:
    if not filesystem.exists(path):
        return None, None
    try:
        data = json.loads(filesystem.read_text(path))
        return data.get("mode"), datetime.fromisoformat(data["since"])
    except (json.JSONDecodeError, KeyError, ValueError):
        return None, None


def _write_state(filesystem: FilesystemPort, path: Path, mode: str, since: datetime) -> None:
    filesystem.make_directory(path.parent)
    filesystem.atomic_write_text(path, json.dumps({"mode": mode, "since": since.isoformat()}) + "\n")
