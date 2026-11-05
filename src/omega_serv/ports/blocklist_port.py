"""Contrat de lecture/ecriture de la blocklist WAF (doc WAF, tableau
"Repartition Clean Architecture" : ports/blocklist_port.py)."""
from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from omega_serv.domain.security.waf.entities import BlocklistEntry


class BlocklistPort(Protocol):
    def is_blocked(self, ip: str) -> BlocklistEntry | None:
        ...

    def list_entries(self) -> tuple[BlocklistEntry, ...]:
        ...

    def add_entry(self, entry: BlocklistEntry) -> None:
        ...

    def add_entry_unless_stronger(self, entry: BlocklistEntry) -> bool:
        """Ajout AUTOMATIQUE (auto-ban, plus tard RIPOSTE) : n'ecrase jamais une entree du
        meme reseau encore en vigueur qui est manuelle, permanente ou plus longue
        (domain/security/waf/blocklist.py::is_stronger_entry). Retourne False si l'entree
        existante a ete gardee. `add_entry` reste l'ajout manuel, qui remplace toujours."""
        ...

    def remove_entry(self, network: str) -> bool:
        """Retire l'entree dont `network` correspond exactement (pas de
        correspondance CIDR partielle) - retourne False si absente."""
        ...

    def remove_entry_if(self, network: str, predicate: Callable[[BlocklistEntry], bool]) -> bool:
        """Comme `remove_entry`, mais seulement si `predicate(entree)` est vrai - pour un
        retrait AUTOMATIQUE qui ne doit toucher qu'a ses propres bans (jamais a un ban
        manuel ou pose par un autre mecanisme). Retourne False si rien n'a ete retire."""
        ...

    def purge_expired(self) -> int:
        """Retire les entrees expirees, retourne le nombre retire."""
        ...

    def count_auto_entries(self) -> int:
        """Nombre d'entrees `source == "auto"` actuellement presentes -
        necessaire pour appliquer reputation.auto_block_max_entries
        sans avoir a tout relire ailleurs."""
        ...
