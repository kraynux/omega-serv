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

import re
import unicodedata

_PERCENT_RUN = re.compile(r"(?:%[0-9A-Fa-f]{2})+")


def _decode_percent_run(match: re.Match[str]) -> str:
    return bytes.fromhex(match.group().replace("%", "")).decode("utf-8", errors="replace")


def unquote_replace(text: str) -> str:
    """Meme resultat que `urllib.parse.unquote(text, errors="replace")`, verifie par vecteurs (plan proxy natif v2,
    lot 2, B). `unquote` decode chaque suite ASCII a part : sur un texte non ASCII qui contient des `%` (corps
    binaire), des centaines de milliers d'appels - 3 s de CPU par Mo, mesure du lot 2. Ici, une seule expression
    reguliere ne touche qu'aux suites `%XX`. Equivalent : un octet ASCII, ecrit tel quel, termine toute sequence
    UTF-8 en cours exactement comme la fin des octets (un U+FFFD pour la sous-partie maximale), donc decoder chaque
    suite `%XX` a part donne le meme texte que decoder toute la suite ASCII d'un bloc."""
    if "%" not in text:
        return text
    return _PERCENT_RUN.sub(_decode_percent_run, text)


def decode_bounded_for_inspection(raw: str, max_passes: int) -> str:
    """Decode au plus `max_passes` fois (meme logique de profondeur
    bornee que path_policy.py, contre le double-encodage utilise pour
    contourner un filtre naif) - tolerant aux sequences invalides
    (`errors="replace"`) plutot que strict : un payload WAF malforme ne
    doit jamais lever, seulement etre inspecte du mieux possible.
    Normalisation Unicode (NFKC) appliquee avant ET apres le decodage -
    voir docstring de module."""
    if raw.isascii() and "%" not in raw:
        # Cas courant (2026-11-04, cout du WAF) : NFKC laisse tout texte ASCII intact et `unquote` ne touche qu'aux
        # sequences « % » - resultat identique, sans les deux passes.
        return raw
    current = unicodedata.normalize("NFKC", raw)
    for _ in range(max(1, max_passes)):
        unquoted = unquote_replace(current)
        if unquoted == current:
            # Lot 2 : rien a decoder - `current` sort deja de NFKC (idempotente), la passe suivante le rendrait tel
            # quel. Meme resultat, sans une normalisation de plus (178 ms par Mo de corps binaire).
            break
        decoded = unicodedata.normalize("NFKC", unquoted)
        if decoded == current:
            break
        current = decoded
    return current
