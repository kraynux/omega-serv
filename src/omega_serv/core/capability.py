# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Modele d'une capacite systeme (plan interface §3.3/§5, menu 1) - port
adapte depuis omega-fire (core/capability.py, generique, zero logique
fire-specifique) : dataclass gelee plutot que mutable avec methodes
mark_*/update_status (convention OMEGA-SERV deja utilisee partout
ailleurs - Option, AuditFinding... - et suffisant ici puisque le
registre est reconstruit entierement a chaque scan, jamais mis a jour
capacite par capacite, voir core/capability_registry.py)."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class CapabilityStatus(str, Enum):
    AVAILABLE = "available"
    DEGRADED = "degraded"
    MISSING = "missing"
    DISQUALIFIED = "disqualified"


@dataclass(frozen=True)
class Capability:
    id: str
    status: CapabilityStatus
    reason: str = ""
    detail: dict[str, Any] | None = None
    category: str = ""
    last_checked: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def is_usable(self) -> bool:
        return self.status in (CapabilityStatus.AVAILABLE, CapabilityStatus.DEGRADED)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "status": self.status.value,
            "reason": self.reason,
            "detail": self.detail,
            "category": self.category,
            "last_checked": self.last_checked.isoformat(),
        }
