# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Implementation reelle de LiveTailPort (plan interface §3.4, "tail
simple") - `f.seek()` + lecture incrementale, pas besoin de PTY (SERV
n'a qu'un flux texte a suivre, contrairement au besoin fire d'encapsuler
un processus interactif). Pas de dependance a FilesystemPort ici : le
suivi position-par-position (stat + seek + tell) n'entre pas dans son
interface generique (lecture/ecriture de fichier entier) - meme
discipline que infrastructure/lnav/ (I/O reelle et specifique, propre a
ce module)."""
from __future__ import annotations

from pathlib import Path


class LiveTailReader:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._offset = path.stat().st_size if path.exists() else 0

    def read_new_lines(self) -> list[str]:
        if not self._path.exists():
            return []
        size = self._path.stat().st_size
        if size < self._offset:
            # Fichier tronque ou tourne (rotation) depuis le dernier
            # appel : on repart du debut plutot que de lever ou de
            # rester bloque sur un offset devenu invalide.
            self._offset = 0
        if size == self._offset:
            return []
        with self._path.open(encoding="utf-8", errors="replace") as f:
            f.seek(self._offset)
            data = f.read()
            self._offset = f.tell()
        return data.splitlines()
