"""Format et logique de correspondance de la blocklist (doc WAF §5).
Pur : parsing/validation/correspondance IP-dans-CIDR et verification
d'expiration, sans aucune I/O - la lecture/ecriture du fichier JSON est
infrastructure/waf/blocklist_store.py."""
from __future__ import annotations

import ipaddress
from datetime import datetime, timezone
from typing import Any

from omega_serv.core.i18n import _
from omega_serv.domain.security.waf.entities import BlocklistEntry

SUPPORTED_BLOCKLIST_VERSIONS = frozenset({1})


def parse_blocklist(data: dict[str, Any]) -> list[BlocklistEntry]:
    return [
        BlocklistEntry(
            network=item["network"],
            reason=item.get("reason", ""),
            created_at=item["created_at"],
            expires_at=item.get("expires_at"),
            source=item.get("source", "manual"),
        )
        for item in data.get("entries", [])
    ]


def serialize_blocklist(entries: list[BlocklistEntry]) -> dict[str, Any]:
    return {
        "version": 1,
        "entries": [
            {
                "network": e.network,
                "reason": e.reason,
                "created_at": e.created_at,
                "expires_at": e.expires_at,
                "source": e.source,
            }
            for e in entries
        ],
    }


def validate_blocklist_entry(entry: BlocklistEntry) -> str | None:
    try:
        ipaddress.ip_network(entry.network, strict=False)
    except ValueError:
        return _("network invalide (attendu une IP ou un CIDR) : {network!r}").format(network=entry.network)
    if not entry.reason:
        return _("reason ne peut pas être vide")
    if entry.source not in ("manual", "auto"):
        return _("source invalide : {source!r}").format(source=entry.source)
    return None


def _is_expired(entry: BlocklistEntry, now: datetime) -> bool:
    if entry.expires_at is None:
        return False
    expires = datetime.fromisoformat(entry.expires_at)
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    return now >= expires


def find_matching_entry(ip: str, entries: list[BlocklistEntry], now: datetime) -> BlocklistEntry | None:
    """Premiere entree non expiree dont le reseau contient `ip` - une
    IP individuelle invalide (ex. deja normalisee ailleurs) ne doit
    jamais lever ici : elle ne correspond simplement a rien."""
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return None
    for entry in entries:
        if _is_expired(entry, now):
            continue
        try:
            network = ipaddress.ip_network(entry.network, strict=False)
        except ValueError:
            continue
        if addr in network:
            return entry
    return None


class BlocklistIndex:
    """Meme resultat que `find_matching_entry` (premiere entree non expiree,
    dans l'ordre du fichier, dont le reseau contient l'IP), sans rien reparser
    a chaque requete (OMEGA-SERV_ANALYSE_OPTIMISATION.md §1) : chaque reseau et
    chaque date ne sont analyses qu'une fois, a la construction. Une IP seule
    (/32, /128 - tous les bans automatiques) est trouvee directement dans une
    table ; seuls les vrais reseaux sont parcourus.

    Mesure (2026-10-29, 1 processus, WAF actif) : `find_matching_entry` coutait
    ~16 us par entree et par requete - 100 entrees (plafond des bans automatiques)
    = 1,6 ms par requete, debit -65 % pour TOUT le trafic, au moment ou une
    attaque remplit la liste. Avec l'index, le cout ne depend plus du nombre de
    bans d'IP seules.

    Une date d'expiration illisible leve `ValueError` au moment ou l'entree est
    examinee, exactement comme `_is_expired` - jamais une entree ignoree en
    silence ni une erreur a la construction."""

    def __init__(self, entries: list[BlocklistEntry]):
        self._exact: dict[ipaddress.IPv4Address | ipaddress.IPv6Address, list[tuple[int, BlocklistEntry, object]]] = {}
        self._networks: list[tuple[int, ipaddress.IPv4Network | ipaddress.IPv6Network, BlocklistEntry, object]] = []
        for position, entry in enumerate(entries):
            try:
                network = ipaddress.ip_network(entry.network, strict=False)
            except ValueError:
                continue
            expiry = _parsed_expiry(entry.expires_at)
            if network.num_addresses == 1:
                self._exact.setdefault(network.network_address, []).append((position, entry, expiry))
            else:
                self._networks.append((position, network, entry, expiry))

    def find(self, ip: str, now: datetime) -> BlocklistEntry | None:
        try:
            addr = ipaddress.ip_address(ip)
        except ValueError:
            return None
        best_position: int | None = None
        best: BlocklistEntry | None = None
        for position, entry, expiry in self._exact.get(addr, ()):
            if not _expired_at(expiry, now):
                best_position, best = position, entry
                break
        for position, network, entry, expiry in self._networks:
            if best_position is not None and position > best_position:
                break
            if addr in network and not _expired_at(expiry, now):
                return entry
        return best


def _parsed_expiry(expires_at: str | None) -> object:
    """None (jamais), la date, ou l'erreur a relever quand l'entree sera examinee."""
    if expires_at is None:
        return None
    try:
        expires = datetime.fromisoformat(expires_at)
    except ValueError as e:
        return e
    return expires if expires.tzinfo is not None else expires.replace(tzinfo=timezone.utc)


def _expired_at(expiry: object, now: datetime) -> bool:
    if expiry is None:
        return False
    if isinstance(expiry, ValueError):
        raise expiry
    return now >= expiry  # type: ignore[operator]


def purge_expired(entries: list[BlocklistEntry], now: datetime) -> tuple[list[BlocklistEntry], int]:
    kept = [e for e in entries if not _is_expired(e, now)]
    return kept, len(entries) - len(kept)
