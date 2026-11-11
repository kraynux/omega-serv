"""Jeton d'installation et fiche d'instance d'omega-serv (spec ~/DEV/CONNECT/SPEC_ETAPE2_CONTRATS_OMEGA_LIB.md,
validee le 2026-11-10).

- Jeton : `var/omega-jeton.json`, ecrit par `omega-serv synchro jeton` (install.sh) et a chaque ouverture de
  l'interface, sous le compte proprietaire du dossier, jamais en root (omega-lib refuse).
- Fiche : sortie de `omega-serv synchro fiche --format json`, lecture seule ; omega-connect la recopie dans
  la zone neutre. Le service n'ecrit donc jamais dans la zone (aucun ajout a ReadWritePaths=)."""
from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from omega_lib.infrastructure.synchro.install_token import (
    TokenRefresh,
    read_install_token,
    refresh_install_token,
)
from omega_lib.synchro.models import CapabilityState, InstanceSheet, ServiceInfo, SharedFile
from omega_lib.synchro.policies import format_utc

from omega_serv.domain.config.entities import OmegaServConfig
from omega_serv.domain.security.active_defense.config import parse_active_defense_config
from omega_serv.domain.security.riposte.config import parse_riposte_config
from omega_serv.domain.security.waf.config import parse_waf_config
from omega_serv.domain.security.waf.reputation import effective_never_auto_block
from omega_serv.ports.filesystem_port import FilesystemPort

SERV_TOOL = "omega-serv"
SERV_CONTRACTS: dict[str, tuple[int, ...]] = {
    "omega-fiche": (1,), "blocklist": (1,), "waf-log": (1,), "riposte-decisions": (1,),
}
SERV_OFFERS = ("waf-logs", "blocklist", "riposte-decisions", "protected-list")
SERV_WANTS = ("external-bans",)
OMEGA_WAF_MARKERS = ("omega_waf_mode", "BAN EVITE")
"""Textes propres au script omega-waf (le nom du fichier copie, lui, est libre : waf.lua par defaut)."""


def refresh_serv_token(project_root: Path, version: str) -> TokenRefresh:
    return refresh_install_token(project_root, SERV_TOOL, version, contracts=SERV_CONTRACTS,
                                 offers=SERV_OFFERS, wants=SERV_WANTS)


def installation_id(project_root: Path) -> str:
    token = read_install_token(project_root)
    return token.value.installation_id if token.ok and token.value is not None else ""


@dataclass(frozen=True)
class SheetContext:
    version: str
    instance: str
    """Nom du service de l'instance (unique par instance)."""
    installation_id: str
    service: ServiceInfo | None
    native_binary_problem: str | None
    effective_engine: str
    now: datetime


def _option_state(config: OmegaServConfig, name: str) -> CapabilityState:
    if name not in config.options:
        return CapabilityState.ABSENT
    return CapabilityState.ACTIVE if config.option_enabled(name) else CapabilityState.DISABLED


def _path(project_root: Path, relative: str) -> str:
    return os.path.normpath(project_root / relative)


def _is_omega_waf(filesystem: FilesystemPort, script: Path) -> bool:
    try:
        text = filesystem.read_text(script)
    except (OSError, UnicodeDecodeError):
        return False
    return any(marker in text for marker in OMEGA_WAF_MARKERS)


def build_serv_sheet(
    config: OmegaServConfig, project_root: Path, filesystem: FilesystemPort, context: SheetContext,
) -> InstanceSheet:
    waf_settings = config.options["waf"].settings if "waf" in config.options else {}
    waf = parse_waf_config(waf_settings)
    waf_state = _option_state(config, "waf")
    waf_on = waf_state is CapabilityState.ACTIVE

    script = Path(_path(project_root, waf.magnet.script or config.paths.waf_script))
    script_present = filesystem.exists(script)
    magnet_on = waf_on and waf.magnet.enabled
    omega_waf = script_present and _is_omega_waf(filesystem, script)
    if not omega_waf:
        omega_waf_state = CapabilityState.ABSENT
    else:
        omega_waf_state = CapabilityState.ACTIVE if magnet_on else CapabilityState.DISABLED

    if context.native_binary_problem is not None:
        native_state = CapabilityState.ABSENT
    else:
        native_state = CapabilityState.ACTIVE if context.effective_engine == "native" else CapabilityState.DISABLED

    capabilities = {
        "waf": waf_state,
        "magnet": CapabilityState.ACTIVE if magnet_on else (
            CapabilityState.DISABLED if script_present else CapabilityState.ABSENT),
        "omega-waf": omega_waf_state,
        "riposte": _option_state(config, "riposte"),
        "active-defense": _option_state(config, "active_defense"),
        "native-engine": native_state,
        "blocklist": CapabilityState.ACTIVE if waf_on and waf.blocklist.enabled else CapabilityState.DISABLED,
    }

    files: dict[str, SharedFile] = {"access-log": SharedFile(_path(project_root, config.logs.access))}
    if waf_on:
        files["waf-log"] = SharedFile(_path(project_root, waf.logging.path), ("waf-log", 1))
    if waf.blocklist.enabled:
        files["blocklist"] = SharedFile(_path(project_root, waf.blocklist.path), ("blocklist", 1))
    if magnet_on:
        files["magnet-alerts-log"] = SharedFile(_path(project_root, waf.magnet.paths.alerts_log))
        files["magnet-blocklist-log"] = SharedFile(_path(project_root, waf.magnet.paths.blocklist_log))
    if capabilities["active-defense"] is CapabilityState.ACTIVE:
        ad = parse_active_defense_config(config.options["active_defense"].settings)
        files["active-defense-log"] = SharedFile(_path(project_root, ad.logging.log_path))
    if capabilities["riposte"] is CapabilityState.ACTIVE:
        riposte = parse_riposte_config(config.options["riposte"].settings)
        if riposte.network_ban_log:
            files["riposte-decisions"] = SharedFile(
                _path(project_root, riposte.decisions_log_path), ("riposte-decisions", 1))

    extra: dict[str, object] = {
        "exposure": "proxy" if config.option_enabled("trusted_proxy") else "direct",
        "waf_mode": waf.mode,
        # Reseaux jamais bannis automatiquement, tels que `waf never-auto-block` les donne : omega-connect les
        # compare a l'ignoreip des jails et a l'action du pont d'omega-jail (lien « liste protegee »).
        "never_auto_block": list(effective_never_auto_block(
            waf.reputation.never_auto_block, config.option_enabled("trusted_proxy"))),
    }
    if omega_waf:
        extra["omega_waf"] = {"script": str(script), "mode": waf.mode}

    return InstanceSheet(
        tool=SERV_TOOL, version=context.version, installation_id=context.installation_id,
        instance=context.instance, generated_at=format_utc(context.now), capabilities=capabilities,
        service=context.service, files=files, partial=False, extra=extra,
    )
