"""Registre des capacites systeme (plan interface §3.3) - port adapte
depuis omega-fire (core/capability_registry.py) : reduit au sous-ensemble
reellement consomme par les ecrans (liste, detail, comptage par statut) -
pas de register()/update()/mark_*() un par un, le registre est toujours
reconstruit entierement par un nouveau scan (`aucune persistance fichier
cote fire, reprendre tel quel`, meme principe ici)."""
from __future__ import annotations

from dataclasses import dataclass, field

from omega_serv.core.capability import Capability, CapabilityStatus


@dataclass(frozen=True)
class CapabilityRegistry:
    capabilities: tuple[Capability, ...] = field(default_factory=tuple)

    def list_all(self) -> tuple[Capability, ...]:
        return tuple(sorted(self.capabilities, key=lambda c: c.id))

    def list_by_status(self, status: CapabilityStatus) -> tuple[Capability, ...]:
        return tuple(c for c in self.list_all() if c.status == status)

    def get(self, capability_id: str) -> Capability | None:
        return next((c for c in self.capabilities if c.id == capability_id), None)

    def count_by_status(self, status: CapabilityStatus) -> int:
        return len(self.list_by_status(status))
