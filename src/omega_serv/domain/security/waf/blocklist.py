"""Format et logique de correspondance de la blocklist (doc WAF §5).
Pur : parsing/validation/correspondance IP-dans-CIDR et verification
d'expiration, sans aucune I/O - la lecture/ecriture du fichier JSON est
infrastructure/waf/blocklist_store.py."""
from __future__ import annotations

import functools
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
            origin=item.get("origin"),
        )
        for item in data.get("entries", [])
    ]


def serialize_blocklist(entries: list[BlocklistEntry]) -> dict[str, Any]:
    return {
        "version": 1,
        "entries": [_serialize_entry(e) for e in entries],
    }


def _serialize_entry(e: BlocklistEntry) -> dict[str, Any]:
    item: dict[str, Any] = {
        "network": e.network,
        "reason": e.reason,
        "created_at": e.created_at,
        "expires_at": e.expires_at,
        "source": e.source,
    }
    if e.origin is not None:  # seulement si present : fichier inchange pour toutes les autres entrees
        item["origin"] = e.origin
    return item


def validate_blocklist_entry(entry: BlocklistEntry) -> str | None:
    try:
        ipaddress.ip_network(entry.network, strict=False)
    except ValueError:
        return _("network invalide (attendu une IP ou un CIDR) : {network!r}").format(network=entry.network)
    if not entry.reason:
        return _("reason ne peut pas être vide")
    if entry.source not in ("manual", "auto", "riposte"):
        return _("source invalide : {source!r}").format(source=entry.source)
    return None


def _is_expired(entry: BlocklistEntry, now: datetime) -> bool:
    if entry.expires_at is None:
        return False
    expires = datetime.fromisoformat(entry.expires_at)
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    return now >= expires


def is_expired(entry: BlocklistEntry, now: datetime) -> bool:
    """Date illisible : tenue pour active (jamais un ban libere par une date abimee)."""
    try:
        return _is_expired(entry, now)
    except ValueError:
        return False


def is_stronger_entry(existing: BlocklistEntry, candidate: BlocklistEntry, now: datetime) -> bool:
    """Vrai si `existing` (meme reseau) doit etre GARDEE plutot que remplacee par `candidate`,
    pour un ajout AUTOMATIQUE (auto-ban du WAF, plus tard RIPOSTE) - jamais pour un ajout manuel,
    qui reste une decision explicite de l'utilisateur (CLI, TUI) et remplace toujours.
    Gardee si elle est encore en vigueur ET : manuelle (decision humaine, jamais ecrasee par un
    automate), ou permanente, ou expirant au plus tot en meme temps que `candidate`. Une date
    illisible compte comme plus forte : dans le doute, on ne touche pas a un ban existant."""
    try:
        if _is_expired(existing, now):
            return False
        if existing.source == "manual" or existing.expires_at is None:
            return True
        if candidate.expires_at is None:
            return False
        existing_expiry = datetime.fromisoformat(existing.expires_at)
        candidate_expiry = datetime.fromisoformat(candidate.expires_at)
    except ValueError:
        return True
    if existing_expiry.tzinfo is None:
        existing_expiry = existing_expiry.replace(tzinfo=timezone.utc)
    if candidate_expiry.tzinfo is None:
        candidate_expiry = candidate_expiry.replace(tzinfo=timezone.utc)
    return existing_expiry >= candidate_expiry


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
        if not self._exact and not self._networks:
            return None  # liste vide (cas courant) : rien a analyser
        try:
            addr = _parsed_ip(ip)
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


@functools.lru_cache(maxsize=1024)
def _parsed_ip(ip: str) -> ipaddress.IPv4Address | ipaddress.IPv6Address:
    """Analyse d'une adresse (~5 us) memorisee : un meme client envoie ses requetes a la suite. Une adresse
    invalide leve `ValueError` a chaque fois (jamais memorisee)."""
    return ipaddress.ip_address(ip)


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
