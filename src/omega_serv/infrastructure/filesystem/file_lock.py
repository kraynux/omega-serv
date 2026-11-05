"""Verrou exclusif entre processus sur un fichier `.lock` (fcntl.flock, bibliotheque standard).

Cree pour la blocklist (OMEGA-SERV_PLAN-DETAILLE_RIPOSTE.md, lot 0) : elle s'ecrit en
« lire -> modifier -> remplacer » et plusieurs processus peuvent y ecrire en meme temps
(workers du mode boost, CLI, TUI, plus tard RIPOSTE). Sans verrou, deux ajouts simultanes
partent de la meme liste et le second efface le premier.

Deux regles, issues des incidents deja rencontres :
- le fichier est ouvert en LECTURE SEULE (`O_RDONLY | O_CREAT`) : flock fonctionne sur un
  descripteur en lecture, donc un `.lock` cree par un autre compte (utilisateur interactif vs
  service dedie, umask 022 -> 644) reste utilisable par tous (meme piege que
  local_filesystem.py::atomic_write_text et file_line_logger.py) ; mode 664 demande a la
  creation, `chmod` explicite ensuite (au mieux : seul le proprietaire peut le faire) ;
- attente BORNEE : un verrou garde trop longtemps par un autre processus ne doit jamais figer
  le serveur (lecon de la base Active Defense, 2026-10-26). Passe le delai, ou si le fichier
  ne peut pas etre ouvert, l'appelant continue SANS verrou (exactement le comportement d'avant)
  et `on_unavailable(raison, detail)` est appele : raison `"open_failed"` (detail = erreur systeme)
  ou `"timeout"` (detail = delai en secondes). Aucun texte humain ici : c'est l'appelant qui
  redige son message (i18n, D18 : messages du processus serveur en francais).
"""
from __future__ import annotations

import fcntl
import os
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path

LOCK_FILE_MODE = 0o664
_POLL_INTERVAL_SECONDS = 0.01


@contextmanager
def exclusive_file_lock(
    lock_path: Path,
    *,
    timeout_seconds: float = 1.0,
    on_unavailable: Callable[[str, str], None] | None = None,
) -> Iterator[bool]:
    """Rend True si le verrou est tenu pendant le bloc, False si le bloc s'execute sans."""
    try:
        fd = os.open(lock_path, os.O_RDONLY | os.O_CREAT, LOCK_FILE_MODE)
    except OSError as error:
        if on_unavailable is not None:
            on_unavailable("open_failed", error.strerror or str(error))
        yield False
        return
    try:
        try:
            os.chmod(lock_path, LOCK_FILE_MODE)
        except OSError:
            pass  # fichier d'un autre compte : il reste utilisable en lecture, donc verrouillable
        deadline = time.monotonic() + timeout_seconds
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    if on_unavailable is not None:
                        on_unavailable("timeout", f"{timeout_seconds:g}")
                    yield False
                    return
                time.sleep(_POLL_INTERVAL_SECONDS)
        try:
            yield True
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)
