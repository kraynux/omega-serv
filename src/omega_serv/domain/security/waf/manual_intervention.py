"""INTERVENTION MANUELLE (Active Securite, decisions utilisateur 2026-11-06) : ban SANS CONDITION d'une seule adresse
IP dans la blocklist du WAF - page 451 avant tout routage, les backends ne voient jamais l'adresse, aucun droit root.
Sans lien avec Active Defense ni RIPOSTE (jamais compte dans la recidive) ; leve seulement depuis ce menu. Un reseau se
bannit dans WAF -> Modules -> Liste de blocage.

Statut : tous les bans (blocklist + liste Magnet, en lecture seule) avec leur origine detaillee, exportables en JSON,
HTML et TXT. Le TXT est un format d'injection (une adresse par ligne, lignes « # » ignorees : format d'import
d'omega-fire) : jamais traduit, et un vrai reseau n'y est ecrit qu'en commentaire - omega-fire ne lit que des
adresses, il n'en garderait que la premiere. Pur : aucune I/O."""
from __future__ import annotations

import ipaddress
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Literal

from omega_serv.core.i18n import _
from omega_serv.domain.security.waf.blocklist import is_expired
from omega_serv.domain.security.waf.entities import BlocklistEntry

INTERVENTION_ORIGIN = "intervention"
"""Valeur du champ `origin` des entrees posees par ce menu (relue par le code : jamais traduite)."""

ORIGIN_INTERVENTION = "intervention"
ORIGIN_WAF_RULES = "waf-rules"
ORIGIN_WAF_LIST = "waf-list"
ORIGIN_RIPOSTE = "riposte"
ORIGIN_OMEGA_JAIL = "omega-jail"
ORIGIN_MANUAL = "manual"
ORIGIN_MAGNET = "magnet"

ORIGIN_ORDER: tuple[str, ...] = (
    ORIGIN_INTERVENTION, ORIGIN_MANUAL, ORIGIN_WAF_RULES, ORIGIN_WAF_LIST, ORIGIN_RIPOSTE, ORIGIN_OMEGA_JAIL,
    ORIGIN_MAGNET,
)

# Prefixes ecrits par le code (jamais traduits) : auto-ban sur liste (evaluate_waf_request.py), pont omega-jail
# (tailscale_bridge.py : --reason omega-jail:<jail>), RIPOSTE (riposte:<action> <politique> #palier).
_LIST_RECIDIVE_PREFIX = "récidive "
_OMEGA_JAIL_PREFIX = "omega-jail"
_RIPOSTE_PREFIX = "riposte:"

TxtScope = Literal["active", "all"]


@dataclass(frozen=True)
class BanRow:
    network: str
    origin: str
    origin_detail: str
    """Nom de la liste, de la jail ou de la politique RIPOSTE ; vide sinon."""
    reason: str
    created_at: str
    expires_at: str | None
    active: bool

    @property
    def removable(self) -> bool:
        """Debannir (ce menu) ne leve que ses propres bans."""
        return self.origin == ORIGIN_INTERVENTION


@dataclass(frozen=True)
class AddressCheck:
    network: str | None
    """`<ip>/32` ou `<ip>/128` si l'adresse est acceptee."""
    error: Literal["", "empty", "network", "invalid"] = ""


def check_single_address(text: str) -> AddressCheck:
    """Une seule adresse IPv4/IPv6 ; toute notation reseau (« / ») est refusee, meme /32."""
    value = text.strip()
    if not value:
        return AddressCheck(None, "empty")
    if "/" in value:
        return AddressCheck(None, "network")
    try:
        address = ipaddress.ip_address(value)
    except ValueError:
        return AddressCheck(None, "invalid")
    return AddressCheck(f"{address}/{address.max_prefixlen}")


def is_protected_address(network: str, protected_networks: Sequence[str]) -> bool:
    """Adresse locale, privee ou Tailscale (les reseaux que l'auto-ban ne touche jamais) : confirmation demandee."""
    address = ipaddress.ip_network(network, strict=False).network_address
    for candidate in protected_networks:
        try:
            if address in ipaddress.ip_network(candidate, strict=False):
                return True
        except ValueError:
            continue
    return False


def classify_origin(entry: BlocklistEntry) -> tuple[str, str]:
    """(origine, detail) d'une entree de blocklist, d'apres son marqueur, sa source et le prefixe de son motif."""
    if entry.origin == INTERVENTION_ORIGIN:
        return ORIGIN_INTERVENTION, ""
    if entry.source == "riposte":
        rest = entry.reason[len(_RIPOSTE_PREFIX):] if entry.reason.startswith(_RIPOSTE_PREFIX) else ""
        parts = rest.split()
        return ORIGIN_RIPOSTE, parts[1] if len(parts) > 1 else ""
    if entry.source == "auto":
        if entry.reason.startswith(_LIST_RECIDIVE_PREFIX):
            return ORIGIN_WAF_LIST, entry.reason[len(_LIST_RECIDIVE_PREFIX):].split(" :")[0].strip()
        return ORIGIN_WAF_RULES, ""
    if entry.reason.startswith(_OMEGA_JAIL_PREFIX):
        return ORIGIN_OMEGA_JAIL, entry.reason.partition(":")[2].strip()
    return ORIGIN_MANUAL, ""


def origin_label(origin: str, detail: str = "") -> str:
    """Libelle affiche (traduit a l'appel : un export dans une autre langue est rendu dans un processus enfant)."""
    if origin == ORIGIN_INTERVENTION:
        return _("Intervention manuelle")
    if origin == ORIGIN_WAF_RULES:
        return _("Auto-ban WAF (règles)")
    if origin == ORIGIN_WAF_LIST:
        return _("Auto-ban WAF (liste {name})").format(name=detail) if detail else _("Auto-ban WAF (liste)")
    if origin == ORIGIN_RIPOSTE:
        return _("RIPOSTE ({policy})").format(policy=detail) if detail else "RIPOSTE"
    if origin == ORIGIN_OMEGA_JAIL:
        return _("omega-jail ({jail})").format(jail=detail) if detail else "omega-jail"
    if origin == ORIGIN_MAGNET:
        return _("Magnet (liste du script)")
    return _("Manuel (WAF → Modules ou CLI)")


def parse_magnet_blocklist(text: str) -> list[tuple[str, str, str]]:
    """Liste du script Magnet (`magnet-blocklist.txt`, ecrite par omega-waf.lua) : une adresse par ligne, precedee
    d'un commentaire `# <date> - <motif>`. Rend (reseau, date, motif) ; lignes illisibles ignorees."""
    rows: list[tuple[str, str, str]] = []
    when, why = "", ""
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#"):
            when, _sep, why = line.lstrip("#").strip().partition(" - ")
            continue
        try:
            address = ipaddress.ip_address(line)
        except ValueError:
            continue
        rows.append((f"{address}/{address.max_prefixlen}", when.strip(), why.strip()))
        when, why = "", ""
    return rows


def build_ban_rows(
    entries: Sequence[BlocklistEntry], magnet: Sequence[tuple[str, str, str]], now: datetime,
) -> list[BanRow]:
    """Tous les bans, regroupes par origine (ordre ORIGIN_ORDER) puis du plus recent au plus ancien."""
    rows = []
    for entry in entries:
        origin, detail = classify_origin(entry)
        rows.append(BanRow(entry.network, origin, detail, entry.reason, entry.created_at, entry.expires_at,
                           not is_expired(entry, now)))
    rows.extend(BanRow(network, ORIGIN_MAGNET, "", why, when, None, True) for network, when, why in magnet)
    rows.sort(key=lambda r: r.created_at, reverse=True)
    rows.sort(key=lambda r: ORIGIN_ORDER.index(r.origin))
    return rows


def ban_rows_payload(rows: Sequence[BanRow], now: datetime) -> dict[str, Any]:
    """Export JSON : codes d'origine stables (relus par d'autres outils) + libelle dans la langue de l'export."""
    return {
        "generated_at": now.isoformat(),
        "bans": [
            {
                "network": r.network, "origin": r.origin, "origin_detail": r.origin_detail,
                "origin_label": origin_label(r.origin, r.origin_detail), "reason": r.reason,
                "created_at": r.created_at, "expires_at": r.expires_at, "active": r.active,
            }
            for r in rows
        ],
    }


def render_injection_txt(rows: Sequence[BanRow], scope: TxtScope, now: datetime) -> str:
    """Une adresse par ligne, en-tete en commentaires (jamais traduit : format lu par d'autres outils). Les vrais
    reseaux (WAF -> Modules) ne sont ecrits qu'en commentaire en fin de fichier."""
    addresses: list[str] = []
    networks: list[str] = []
    for row in rows:
        if scope == "active" and not row.active:
            continue
        try:
            network = ipaddress.ip_network(row.network, strict=False)
        except ValueError:
            continue
        if network.prefixlen == network.max_prefixlen:
            text = str(network.network_address)
            if text not in addresses:
                addresses.append(text)
        elif str(network) not in networks:
            networks.append(str(network))
    label = "active bans" if scope == "active" else "all bans in the list"
    lines = [
        f"# omega-serv - {label} - exported {now.astimezone(timezone.utc).strftime('%Y-%m-%d %H:%M')} UTC",
        f"# {len(addresses)} address(es); {len(networks)} network(s) not exported (see end of file)",
        "# One address per line; lines starting with # are ignored (omega-fire import format).",
        *addresses,
        *(f"# network not exported (addresses only): {network}" for network in networks),
    ]
    return "\n".join(lines) + "\n"
