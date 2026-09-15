# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Cas d'usage : vider le dossier d'export (ecran Reglages) - housekeeping
filesystem simple, porte depuis omega-check (`shutil` directement, pas de
port dedie, meme raisonnement que pathlib dans infrastructure/config/
paths.py)."""
from __future__ import annotations

import shutil
from pathlib import Path


def clear_exports(exports_dir: Path) -> None:
    shutil.rmtree(exports_dir, ignore_errors=True)
    exports_dir.mkdir(parents=True, exist_ok=True)
