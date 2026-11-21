"""Commande `omega-serv` d'une AUTRE instance de cette machine, lancee avec son propre environnement (ecran
Instances -> « Relier au maître », 2026-11-16) : chaque instance ecrit ses fichiers elle-meme, jamais l'instance
qui pilote l'interface a sa place."""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class CommandReply:
    code: int
    stdout: str
    stderr: str

    def last_line(self) -> str:
        """Derniere ligne non vide (stderr d'abord) : la raison d'un echec, a montrer telle quelle."""
        for text in (self.stderr, self.stdout):
            lines = [line.strip() for line in text.splitlines() if line.strip()]
            if lines:
                return lines[-1]
        return ""


class InstanceCommandPort(Protocol):
    def run(self, root: Path, arguments: Sequence[str], stdin: str = "") -> CommandReply:
        """`omega-serv --config <root>/config/omega-serve.json <arguments>` dans l'instance `root`."""
        ...
