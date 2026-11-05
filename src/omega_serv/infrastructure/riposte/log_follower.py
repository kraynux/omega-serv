"""Suivi incremental d'un journal par RIPOSTE (OMEGA-SERV_PLAN-DETAILLE_RIPOSTE.md §3.2, lot 2).

Contrairement a infrastructure/logging/live_tail_reader.py (affichage dans la TUI, aucune position
memorisee), ce lecteur doit ne RIEN perdre et ne RIEN compter deux fois a travers :
- la rotation d'omega-serv (troncature sur le meme inode) -> taille < position : reprise au debut ;
- un remplacement (`os.replace` de « Voir et traiter IP », nouvel inode) -> reprise au debut du
  nouveau fichier ;
- une reecriture sur place plus longue que la position (meme inode, debut different) -> detectee par
  l'empreinte des premiers octets, reprise au debut ;
- une ligne en cours d'ecriture (pas encore de saut de ligne) -> jamais consommee, relue au tour suivant.
Les lignes relues apres une reprise au debut sont dedoublonnees par l'appelant (identifiant
d'evenement), jamais ici.

Bornes : au plus `max_bytes_per_read` lus par appel (le reste au tour suivant) ; une « ligne » de plus
de `max_line_bytes` sans saut de ligne est sautee jusqu'au prochain saut de ligne et comptee
(`skipped_long_lines`) - un journal forge ne peut ni saturer la memoire ni bloquer la lecture."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path

from omega_serv.ports.riposte_store_port import FollowerPosition

FINGERPRINT_BYTES = 256


def _fingerprint(handle_path: Path, length: int) -> str:
    with open(handle_path, "rb") as handle:
        return hashlib.sha256(handle.read(length)).hexdigest()


def _byte_before(path: Path, offset: int) -> bytes:
    with open(path, "rb") as handle:
        handle.seek(offset - 1)
        return handle.read(1)


class LogFollower:
    def __init__(
        self,
        path: Path,
        position: FollowerPosition | None,
        *,
        start_at_end: bool = True,
        start_back_bytes: int = 1024 * 1024,
        max_bytes_per_read: int = 4 * 1024 * 1024,
        max_line_bytes: int = 64 * 1024,
    ) -> None:
        """`position` None (premier suivi de ce journal) : `start_at_end` True = ne pas rejouer
        tout l'historique deja present (la mesure le fait a part, plan §3.10). Le depart se fait
        `start_back_bytes` AVANT la fin du journal tel qu'il est A LA CREATION du lecteur, aligne sur
        un debut de ligne : les evenements ecrits pendant le demarrage du processus (une a deux
        secondes) ne sont jamais perdus ; ceux qui sont plus anciens sont ecartes par l'appelant
        selon leur date (follow_once, `not_before`). Un journal absent a la creation sera lu depuis
        son debut."""
        self._path = path
        self._position = position
        self._max_bytes = max_bytes_per_read
        self._max_line = max_line_bytes
        self._discarding_long_line = False
        self._initial_start: tuple[int, int, int] | None = None
        if position is None and start_at_end:
            try:
                stat = os.stat(path)
            except FileNotFoundError:
                pass
            else:
                offset = max(0, stat.st_size - start_back_bytes)
                self._initial_start = (stat.st_ino, stat.st_dev, offset)
                # Depart au milieu d'une ligne : tout jusqu'au prochain saut de ligne est ignore
                # (jamais une ligne complete : seulement si l'octet precedent n'est pas un saut de ligne).
                self._discarding_long_line = offset > 0 and _byte_before(path, offset) != b"\n"
        self.skipped_long_lines = 0
        self.restarts = 0
        """Reprises au debut (rotation, remplacement, reecriture) - diagnostic."""

    @property
    def position(self) -> FollowerPosition | None:
        return self._position

    def read_new_lines(self) -> list[str]:
        try:
            stat = os.stat(self._path)
        except FileNotFoundError:
            return []  # journal pas encore cree ou en cours de remplacement : position gardee
        offset = self._resolve_start(stat)
        if stat.st_size <= offset:
            self._remember(stat, offset)
            return []
        with open(self._path, "rb") as handle:
            handle.seek(offset)
            chunk = handle.read(min(self._max_bytes, stat.st_size - offset))
        lines, consumed = self._split(chunk)
        self._remember(stat, offset + consumed)
        return lines

    def _resolve_start(self, stat: os.stat_result) -> int:
        position = self._position
        if position is None:
            initial = self._initial_start
            if initial is not None and initial[:2] == (stat.st_ino, stat.st_dev) and stat.st_size >= initial[2]:
                return initial[2]
            self._discarding_long_line = False
            return 0  # journal apparu (ou remplace, ou tronque) depuis la creation du lecteur : tout est nouveau
        if (stat.st_ino, stat.st_dev) != (position.inode, position.device):
            self._restart()
            return 0
        if stat.st_size < position.offset:
            self._restart()
            return 0
        if (
            position.fingerprint_length
            and stat.st_size >= position.fingerprint_length
            and _fingerprint(self._path, position.fingerprint_length) != position.fingerprint
        ):
            self._restart()
            return 0
        return position.offset

    def _restart(self) -> None:
        self.restarts += 1
        self._discarding_long_line = False

    def _split(self, chunk: bytes) -> tuple[list[str], int]:
        """Lignes completes du morceau, et nombre d'octets consommes (jamais une ligne inachevee,
        sauf une ligne trop longue, sautee)."""
        lines: list[str] = []
        consumed = 0
        while consumed < len(chunk):
            newline = chunk.find(b"\n", consumed)
            if newline == -1:
                remaining = len(chunk) - consumed
                if remaining > self._max_line:
                    # ligne trop longue sans fin : on avance quand meme, et on saute sa suite
                    if not self._discarding_long_line:
                        self.skipped_long_lines += 1
                    self._discarding_long_line = True
                    consumed = len(chunk)
                break
            raw = chunk[consumed:newline]
            consumed = newline + 1
            if self._discarding_long_line:
                self._discarding_long_line = False  # fin de la ligne trop longue
                continue
            if len(raw) > self._max_line:
                self.skipped_long_lines += 1
                continue
            lines.append(raw.decode("utf-8", errors="replace"))
        return lines, consumed

    def _remember(self, stat: os.stat_result, offset: int) -> None:
        length = min(FINGERPRINT_BYTES, stat.st_size)
        if (
            self._position is not None
            and (self._position.inode, self._position.device) == (stat.st_ino, stat.st_dev)
            and self._position.fingerprint_length == length
            and self._position.offset <= offset
        ):
            fingerprint = self._position.fingerprint
        else:
            fingerprint = _fingerprint(self._path, length) if length else ""
        self._position = FollowerPosition(
            inode=stat.st_ino, device=stat.st_dev, offset=offset,
            fingerprint=fingerprint, fingerprint_length=length,
        )
