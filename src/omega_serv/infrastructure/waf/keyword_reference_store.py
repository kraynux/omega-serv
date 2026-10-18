"""Lecture des references livrees dans le paquet (dossier voisin
`keyword_references/`, regenere par build-release.sh depuis le fichier
maitre - voir keyword_reference_generator.py)."""
from __future__ import annotations

from pathlib import Path

_REFERENCES_DIR = Path(__file__).resolve().parent / "keyword_references"


class PackagedKeywordReferences:
    def __init__(self, directory: Path = _REFERENCES_DIR):
        self._directory = directory

    def names(self) -> tuple[str, ...]:
        if not self._directory.is_dir():
            return ()
        return tuple(sorted(p.name for p in self._directory.glob("*.txt")))

    def read(self, name: str) -> str | None:
        if name not in self.names():
            return None  # jamais un chemin construit librement depuis un nom fourni
        return (self._directory / name).read_text(encoding="utf-8")
