"""Cas d'usage : vider le dossier de captures d'ecran (ecran Reglages) -
voir clear_exports.py pour le raisonnement."""
from __future__ import annotations

import shutil
from pathlib import Path


def clear_screenshots(screenshots_dir: Path) -> None:
    shutil.rmtree(screenshots_dir, ignore_errors=True)
    screenshots_dir.mkdir(parents=True, exist_ok=True)
