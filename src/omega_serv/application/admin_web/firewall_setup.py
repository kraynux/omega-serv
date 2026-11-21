# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""« Ouvrir le port » de l'ecran Configuration distante (sous-lot 8b, plan tableau de bord web §9.4 ; decisions de
l'auteur du 2026-11-17) : omega-serv ouvre lui-meme le port de l'administration web par omega-fire, seulement si
omega-fire et cette instance sont inscrits dans la zone omega-connect ; sinon le pare-feu est seulement signale.

Reseaux ouverts : les reseaux permis de l'option, sans la boucle locale (jamais filtree). Ce qui a ete ouvert est
retenu (var/lib/admin/pare-feu.json) : le bilan dit « ouvert » tant que le port et les reseaux n'ont pas change."""
from __future__ import annotations

import ipaddress
import re
from dataclasses import dataclass
from typing import Any

from omega_serv.domain.admin_web.settings import AdminWebSettings


@dataclass(frozen=True)
class FirewallRecord:
    port: int
    sources: tuple[str, ...]
    at: str
    """Date de l'ouverture (ISO), pour l'affichage."""

    def to_dict(self) -> dict[str, Any]:
        return {"port": self.port, "sources": list(self.sources), "at": self.at}

    @classmethod
    def from_dict(cls, data: object) -> FirewallRecord | None:
        if not isinstance(data, dict):
            return None
        port, sources, at = data.get("port"), data.get("sources"), data.get("at")
        if not isinstance(port, int) or isinstance(port, bool) or not isinstance(sources, list) \
                or not all(isinstance(s, str) for s in sources) or not isinstance(at, str):
            return None
        return cls(port, tuple(sources), at[:40])


def firewall_sources(settings: AdminWebSettings) -> tuple[str, ...]:
    sources: list[str] = []
    for raw in settings.allowed_networks:
        try:
            network = ipaddress.ip_network(str(raw), strict=False)
        except ValueError:
            continue
        if not network.is_loopback and str(network) not in sources:
            sources.append(str(network))
    return tuple(sources)


def firewall_label(instance_name: str) -> str:
    """Nom des regles cote omega-fire : « omega-serv:<instance> » (caracteres sans risque seulement)."""
    cleaned = re.sub(r"[^A-Za-z0-9._-]", "-", instance_name)[:40].strip("-.") or "instance"
    return f"omega-serv:{cleaned}"


def record_covers(record: FirewallRecord | None, settings: AdminWebSettings) -> bool:
    return record is not None and isinstance(settings.port, int) and record.port == settings.port \
        and set(firewall_sources(settings)) <= set(record.sources)
