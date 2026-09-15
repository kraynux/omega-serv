# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Format et logique de correspondance de la blocklist (doc WAF §5).
Pur : parsing/validation/correspondance IP-dans-CIDR et verification
d'expiration, sans aucune I/O - la lecture/ecriture du fichier JSON est
infrastructure/waf/blocklist_store.py."""
from __future__ import annotations

import ipaddress
from datetime import datetime, timezone
from typing import Any

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
        return f"network invalide (attendu une IP ou un CIDR) : {entry.network!r}"
    if not entry.reason:
        return "reason ne peut pas etre vide"
    if entry.source not in ("manual", "auto"):
        return f"source invalide : {entry.source!r}"
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


def purge_expired(entries: list[BlocklistEntry], now: datetime) -> tuple[list[BlocklistEntry], int]:
    kept = [e for e in entries if not _is_expired(e, now)]
    return kept, len(entries) - len(kept)
