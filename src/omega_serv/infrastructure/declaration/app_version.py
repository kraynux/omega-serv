"""Version d'omega-serv envoyee dans une declaration : pyproject.toml (seule source de la version,
toujours livre dans l'archive), repli sur les metadonnees du paquet installe."""
from __future__ import annotations

import importlib.metadata
import re
from pathlib import Path

_VERSION_LINE = re.compile(r'^version = "([^"]+)"$', re.MULTILINE)


def application_version(project_root: Path) -> str:
    try:
        match = _VERSION_LINE.search((project_root / "pyproject.toml").read_text(encoding="utf-8"))
    except OSError:
        match = None
    if match:
        return match.group(1)
    try:
        return importlib.metadata.version("omega-serv")
    except importlib.metadata.PackageNotFoundError:
        return "0.0.0"
