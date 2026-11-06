"""Cas d'usage de l'INTERVENTION MANUELLE (Active Securite) : bannir / debannir une adresse IP sans condition, et
lister tous les bans avec leur origine (domain/security/waf/manual_intervention.py). Passe par le meme BlocklistPort
que le WAF, la CLI, RIPOSTE et omega-jail : verrou entre processus, droits du fichier garantis (660)."""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from omega_serv.application.security.manage_blocklist import ManageBlocklistResult
from omega_serv.core.i18n import _
from omega_serv.domain.config.entities import OmegaServConfig
from omega_serv.domain.security.waf.blocklist import is_expired, validate_blocklist_entry
from omega_serv.domain.security.waf.config import WafConfig, parse_waf_config
from omega_serv.domain.security.waf.entities import BlocklistEntry
from omega_serv.domain.security.waf.manual_intervention import (
    INTERVENTION_ORIGIN,
    BanRow,
    build_ban_rows,
    check_single_address,
    classify_origin,
    is_protected_address,
    origin_label,
    parse_magnet_blocklist,
)
from omega_serv.ports.blocklist_port import BlocklistPort
from omega_serv.ports.filesystem_port import FilesystemPort

NETWORK_HINT = _("Pour bannir un réseau : menu WAF → Modules → Liste de blocage.")


def waf_config_of(config: OmegaServConfig) -> WafConfig:
    return parse_waf_config(config.options["waf"].settings if "waf" in config.options else {})


def waf_enabled(config: OmegaServConfig) -> bool:
    """Sans WAF actif, la blocklist n'est jamais consultee : un ban n'aurait aucun effet."""
    return "waf" in config.options and config.options["waf"].enabled


def protected_networks(config: OmegaServConfig) -> tuple[str, ...]:
    """Les reseaux que l'auto-ban ne touche jamais (options.waf.reputation.never_auto_block)."""
    return waf_config_of(config).reputation.never_auto_block


def magnet_list_path(config: OmegaServConfig, project_root: Path) -> Path | None:
    """Liste du script Magnet, seulement si Magnet est actif (sinon elle n'est appliquee par personne)."""
    magnet = waf_config_of(config).magnet
    return project_root / magnet.paths.blocklist_file if magnet.enabled else None


@dataclass(frozen=True)
class BanRequestCheck:
    """Resultat de la verification d'une saisie, AVANT toute ecriture : erreur bloquante, ou avertissements a faire
    confirmer par l'utilisateur."""
    network: str | None
    error: str = ""
    warnings: tuple[str, ...] = ()


def address_error(code: str) -> str:
    if code == "empty":
        return _("Adresse IP manquante.")
    if code == "network":
        return _("Une seule adresse IP, pas de réseau. {hint}").format(hint=NETWORK_HINT)
    return _("Adresse IP invalide.")


def check_ban_request(
    blocklist_port: BlocklistPort, address: str, permanent: bool, protected_networks: Sequence[str], now: datetime,
) -> BanRequestCheck:
    checked = check_single_address(address)
    if checked.network is None:
        return BanRequestCheck(None, address_error(checked.error))
    warnings: list[str] = []
    if is_protected_address(checked.network, protected_networks):
        warnings.append(_("{ip} est une adresse locale, privée ou Tailscale : la bannir peut couper votre propre "
                          "accès au site.").format(ip=checked.network.split("/")[0]))
    existing = next((e for e in blocklist_port.list_entries() if e.network == checked.network), None)
    if existing is not None and not is_expired(existing, now):
        origin, detail = classify_origin(existing)
        if existing.origin != INTERVENTION_ORIGIN:
            warnings.append(_("Cette adresse est déjà bannie ({origin}) : ce ban sera remplacé par le vôtre.").format(
                origin=origin_label(origin, detail)))
    if permanent:
        warnings.append(_("Ban permanent : il reste en place jusqu'à ce que vous le leviez dans Débannir."))
    return BanRequestCheck(checked.network, warnings=tuple(warnings))


def ban_address(
    blocklist_port: BlocklistPort, network: str, reason: str, duration_seconds: int | None, now: datetime,
) -> ManageBlocklistResult:
    """Ban sans condition (deja verifie et confirme par l'appelant). `duration_seconds` None = permanent."""
    expires_at = None if duration_seconds is None else (now + timedelta(seconds=duration_seconds)).isoformat()
    entry = BlocklistEntry(
        network=network, reason=reason.strip() or _("Intervention manuelle"), created_at=now.isoformat(),
        expires_at=expires_at, source="manual", origin=INTERVENTION_ORIGIN,
    )
    error = validate_blocklist_entry(entry)
    if error is not None:
        return ManageBlocklistResult(False, error)
    try:
        blocklist_port.add_entry(entry)
    except OSError as e:
        return ManageBlocklistResult(False, _("Blocklist illisible ou non modifiable : {error}").format(error=e))
    ip = network.split("/")[0]
    if expires_at is None:
        return ManageBlocklistResult(True, _("{ip} bannie (permanent).").format(ip=ip))
    return ManageBlocklistResult(True, _("{ip} bannie jusqu'au {date}.").format(
        ip=ip, date=datetime.fromisoformat(expires_at).astimezone().strftime("%Y-%m-%d %H:%M")))


def manual_bans(blocklist_port: BlocklistPort) -> list[BlocklistEntry]:
    """Les seuls bans que Debannir montre et peut lever : ceux poses par ce menu."""
    return [e for e in blocklist_port.list_entries() if e.origin == INTERVENTION_ORIGIN]


def unban_address(blocklist_port: BlocklistPort, network: str) -> ManageBlocklistResult:
    entry = next((e for e in blocklist_port.list_entries() if e.network == network), None)
    ip = network.split("/")[0]
    if entry is None:
        return ManageBlocklistResult(False, _("Aucun ban pour {ip}.").format(ip=ip))
    if entry.origin != INTERVENTION_ORIGIN:
        return ManageBlocklistResult(False, _("Ce ban n'a pas été posé par l'intervention manuelle : levez-le là où "
                                              "il a été posé (WAF → Modules, RIPOSTE → Actions)."))
    try:
        removed = blocklist_port.remove_entry(network)
    except OSError as e:
        return ManageBlocklistResult(False, _("Blocklist illisible ou non modifiable : {error}").format(error=e))
    if not removed:
        return ManageBlocklistResult(False, _("Aucun ban pour {ip}.").format(ip=ip))
    return ManageBlocklistResult(True, _("Ban levé : {ip}").format(ip=ip))


def collect_ban_rows(
    blocklist_port: BlocklistPort, filesystem: FilesystemPort, magnet_list: Path | None, now: datetime,
) -> tuple[list[BanRow], str]:
    """Tous les bans (blocklist + liste Magnet si Magnet est configure). Rend aussi un avertissement a afficher
    (liste Magnet illisible) - jamais une erreur qui viderait le statut."""
    magnet: list[tuple[str, str, str]] = []
    warning = ""
    if magnet_list is not None and filesystem.exists(magnet_list):
        try:
            magnet = parse_magnet_blocklist(filesystem.read_text(magnet_list))
        except (OSError, UnicodeDecodeError) as e:
            warning = _("Liste Magnet illisible ({path}) : {error}").format(path=magnet_list, error=e)
    return build_ban_rows(blocklist_port.list_entries(), magnet, now), warning


def _local(moment: str | None, short: bool = False) -> str:
    if not moment:
        return ""
    try:
        return datetime.fromisoformat(moment).astimezone().strftime("%m-%d %H:%M" if short else "%Y-%m-%d %H:%M")
    except ValueError:
        return moment


def ban_rows_for_display(rows: Sequence[BanRow], short: bool = False) -> list[dict[str, str]]:
    """Textes affiches (tableau Statut en dates courtes, export HTML), dans la langue du processus appelant."""
    return [
        {
            "network": r.network.split("/")[0] if r.network.endswith(("/32", "/128")) else r.network,
            "origin": origin_label(r.origin, r.origin_detail),
            "reason": r.reason,
            "created": _local(r.created_at, short),
            "expires": _local(r.expires_at, short) if r.expires_at else _("permanent"),
            "state": _("en vigueur") if r.active else _("expiré"),
        }
        for r in rows
    ]
