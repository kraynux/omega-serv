# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Normalisation des textes de scope avant inspection (doc WAF §2,
module "normalization" : "limitation de profondeur de decodage...
normalisation URL deterministe"). Distinct de
domain/security/path_policy.py : ce module ne fait AUCUNE verification
de securite (pas de rejet NUL/traversal) - il decode juste le texte du
mieux possible pour le moteur de signatures, qui est heuristique et ne
doit jamais faire echouer une requete a cause d'un decodage imparfait
(contrairement au resolveur de chemin, qui doit rejeter plutot que
deviner).

Retour utilisateur (audit securite, 2026-09-14) : le double-encodage URL
est deja borne ici, mais aucune normalisation Unicode n'etait appliquee
avant la comparaison aux signatures (regex ASCII litterales type
`<script>`/`union select`) - un payload utilisant des caracteres
pleine-largeur ou confusables (`＜ｓｃｒｉｐｔ＞`, `ｕｎｉｏｎ ｓｅｌｅｃｔ`) contournait
alors silencieusement toute signature cherchant le motif ASCII exact.
NFKC (Unicode Normalization Form Compatibility Composition) ramene ces
variantes vers leur equivalent ASCII canonique AVANT le decodage URL
(un payload peut combiner les deux techniques) et a nouveau APRES (le
decodage URL peut lui-meme reveler des caracteres non normalises)."""
from __future__ import annotations

import unicodedata
import urllib.parse


def decode_bounded_for_inspection(raw: str, max_passes: int) -> str:
    """Decode au plus `max_passes` fois (meme logique de profondeur
    bornee que path_policy.py, contre le double-encodage utilise pour
    contourner un filtre naif) - tolerant aux sequences invalides
    (`errors="replace"`) plutot que strict : un payload WAF malforme ne
    doit jamais lever, seulement etre inspecte du mieux possible.
    Normalisation Unicode (NFKC) appliquee avant ET apres le decodage -
    voir docstring de module."""
    current = unicodedata.normalize("NFKC", raw)
    for _ in range(max(1, max_passes)):
        decoded = urllib.parse.unquote(current, errors="replace")
        decoded = unicodedata.normalize("NFKC", decoded)
        if decoded == current:
            break
        current = decoded
    return current
