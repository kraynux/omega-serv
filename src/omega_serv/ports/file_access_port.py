"""Contrat des operations sur un fichier EDITE depuis la TUI et LU par le
service (OMEGA-SERV_PLAN-DETAILLE_SENSITIVE_PATHS.md §3.7) - separe de
FilesystemPort, qui reste le contrat generique : ici tout tourne autour de
la question "l'utilisateur ecrit, le compte du service lit"."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from omega_serv.domain.security.file_access import AccountIdentity, PathNode


@dataclass(frozen=True)
class WriteOutcome:
    """`group_preserved` faux = le fichier existait avec un groupe dont
    l'utilisateur n'est pas membre : le mode est conserve, le groupe non
    (a signaler, jamais une erreur)."""
    mode: int
    group_preserved: bool


class FileAccessPort(Protocol):
    def stat_chain(self, path: Path) -> tuple[PathNode, ...]:
        """Chaque dossier depuis `/` jusqu'a `path` inclus (qui doit exister)."""
        ...

    def lookup_account(self, name: str) -> AccountIdentity | None:
        """None si le compte n'existe pas sur la machine."""
        ...

    def current_uid(self) -> int:
        ...

    def has_symlink_between(self, root: Path, path: Path) -> bool:
        """Un element de `root` (exclu) jusqu'a `path` (inclus) est-il un lien ?"""
        ...

    def fingerprint(self, path: Path) -> tuple[int, int] | None:
        """(mtime en ns, taille) - None si absent. Sert a detecter une
        modification exterieure pendant l'edition (regle R7)."""
        ...

    def can_write(self, path: Path) -> bool:
        """Le fichier (s'il existe) ET son dossier (fichier temporaire) sont-ils
        modifiables par l'utilisateur courant ?"""
        ...

    def atomic_write_preserving(self, path: Path, content: str, new_file_mode: int) -> WriteOutcome:
        ...

    def set_mode(self, path: Path, mode: int) -> None:
        ...

    def read_tail_lines(self, path: Path, max_bytes: int) -> list[str]:
        """Dernieres lignes completes d'un fichier (journal d'acces potentiellement
        enorme), au plus `max_bytes` lus depuis la fin. Fichier absent = []."""
        ...
