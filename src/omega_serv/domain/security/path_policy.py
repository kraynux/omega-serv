# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Regles pures de resolution de chemin sure (spec §11.2, etapes 1-4).

Ce module ne couvre QUE la partie decodage/normalisation, sans aucune
I/O filesystem : decoder l'URI, rejeter NUL/caracteres de controle,
normaliser les segments '.'/'..'. La suite de l'algorithme (etapes 5-7 :
construction depuis la racine autorisee, resolution des liens
symboliques, verification de confinement reel) exige un acces disque
reel et vit dans infrastructure/filesystem/safe_path_resolver.py, qui
consomme ce module plutot que de dupliquer sa logique.

"La protection '../' in url est insuffisante" (spec §11.2) - d'ou
l'algorithme complet plutot qu'un simple test de sous-chaine.
"""
from __future__ import annotations

import urllib.parse
from dataclasses import dataclass
from enum import Enum, auto

from omega_serv.domain.http.status_codes import HttpStatus

_CONTROL_CHARS = frozenset(chr(c) for c in range(0x20))
_MAX_DECODE_PASSES = 2  # spec WAF §"normalisation": "limitation de profondeur de decodage" - empeche le decodage double/multiple utilise pour contourner un filtre naif, sans boucler indefiniment sur une entree malveillante.


class PathRejectionReason(Enum):
    EMPTY_PATH = auto()
    DECODE_ERROR = auto()
    NUL_BYTE = auto()
    CONTROL_CHARACTER = auto()
    TRAVERSAL_ATTEMPT = auto()


_REJECTION_STATUS: dict[PathRejectionReason, HttpStatus] = {
    PathRejectionReason.EMPTY_PATH: HttpStatus.BAD_REQUEST,
    PathRejectionReason.DECODE_ERROR: HttpStatus.BAD_REQUEST,
    PathRejectionReason.NUL_BYTE: HttpStatus.BAD_REQUEST,
    PathRejectionReason.CONTROL_CHARACTER: HttpStatus.BAD_REQUEST,
    PathRejectionReason.TRAVERSAL_ATTEMPT: HttpStatus.FORBIDDEN,
}


@dataclass(frozen=True)
class PathDecision:
    ok: bool
    segments: tuple[str, ...] = ()
    rejection_reason: PathRejectionReason | None = None

    @property
    def suggested_status(self) -> HttpStatus | None:
        if self.rejection_reason is None:
            return None
        return _REJECTION_STATUS[self.rejection_reason]


def _percent_decode_bounded(raw: str, max_passes: int = _MAX_DECODE_PASSES) -> str:
    """Decode au plus `max_passes` fois - un decodage repete au-dela de
    ce point n'a plus vocation a reveler une nouvelle sequence
    dangereuse et signale plutot un encodage multiple deliberement
    construit pour contourner une validation naive."""
    current = raw
    for _ in range(max_passes):
        decoded = urllib.parse.unquote(current, errors="strict")
        if decoded == current:
            break
        current = decoded
    return current


def normalize_uri_path(raw_path: str) -> PathDecision:
    """Decode et normalise un chemin d'URI brut (sans query string,
    deja extraite en amont par le parseur HTTP - Phase 1).

    Retourne les segments normalises (jamais '.', jamais '..' residuel,
    jamais de segment vide) ou une raison de rejet explicite. Ne
    resout PAS de chemin filesystem reel - voir le docstring du module.
    """
    if not raw_path:
        return PathDecision(ok=False, rejection_reason=PathRejectionReason.EMPTY_PATH)

    try:
        decoded = _percent_decode_bounded(raw_path)
    except (UnicodeDecodeError, ValueError):
        return PathDecision(ok=False, rejection_reason=PathRejectionReason.DECODE_ERROR)

    if "\x00" in decoded:
        return PathDecision(ok=False, rejection_reason=PathRejectionReason.NUL_BYTE)

    if any(ch in _CONTROL_CHARS for ch in decoded):
        return PathDecision(ok=False, rejection_reason=PathRejectionReason.CONTROL_CHARACTER)

    normalized: list[str] = []
    for segment in decoded.replace("\\", "/").split("/"):
        if segment in ("", "."):
            continue
        if segment == "..":
            if not normalized:
                # Remontee au-dessus de la racine autorisee - jamais
                # tolere, meme si un ".." plus loin dans le chemin
                # aurait pu "compenser" : la remontee est deja hors
                # limites au moment ou elle se produit.
                return PathDecision(ok=False, rejection_reason=PathRejectionReason.TRAVERSAL_ATTEMPT)
            normalized.pop()
            continue
        normalized.append(segment)

    return PathDecision(ok=True, segments=tuple(normalized))
