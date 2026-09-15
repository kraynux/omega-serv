# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Contrat de journalisation - ecriture de lignes deja formatees
(le formatage lui-meme est une regle domain, voir
domain/logging/access_log_format.py, pure et testable sans disque)."""
from __future__ import annotations

from pathlib import Path
from typing import Protocol


class LoggerPort(Protocol):
    def append_line(self, path: Path, line: str) -> None:
        ...
