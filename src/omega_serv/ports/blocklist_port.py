"""Contrat de lecture/ecriture de la blocklist WAF (doc WAF, tableau
"Repartition Clean Architecture" : ports/blocklist_port.py)."""
from __future__ import annotations

from typing import Protocol

from omega_serv.domain.security.waf.entities import BlocklistEntry


class BlocklistPort(Protocol):
    def is_blocked(self, ip: str) -> BlocklistEntry | None:
        ...

    def list_entries(self) -> tuple[BlocklistEntry, ...]:
        ...

    def add_entry(self, entry: BlocklistEntry) -> None:
        ...

    def remove_entry(self, network: str) -> bool:
        """Retire l'entree dont `network` correspond exactement (pas de
        correspondance CIDR partielle) - retourne False si absente."""
        ...

    def purge_expired(self) -> int:
        """Retire les entrees expirees, retourne le nombre retire."""
        ...

    def count_auto_entries(self) -> int:
        """Nombre d'entrees `source == "auto"` actuellement presentes -
        necessaire pour appliquer reputation.auto_block_max_entries
        sans avoir a tout relire ailleurs."""
        ...
