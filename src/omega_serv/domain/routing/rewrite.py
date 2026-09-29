"""Reecriture interne de chemin (spec §17.3) : compteur maximal de
reecritures, detection de boucle - en cas de boucle ou de depassement,
echec explicite (traite comme une erreur serveur par l'appelant, jamais
un chemin devine ou un silence).

match_prefix (2026-09-28, retour utilisateur) : le test de
correspondance passe par domain/routing/zone_resolver.py::
path_matches_prefix() (meme mecanisme que resolve_zone(), voir son
propre docstring) plutot qu'un `str.startswith()` direct - "/old" et
"/old/" matchent desormais a l'identique, sans sur-matcher un segment
partiel comme "/oldish". Le remplacement (`current[len(rule.
match_prefix):]`) reste un slicing brut sur la longueur CONFIGUREE
(pas normalisee) : Python tolere deja gracieusement un slice plus long
que la chaine (retourne ""), donc "/old"/"/old/" produisent tous deux
un resultat correct sans traitement supplementaire ici."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from omega_serv.domain.routing.zone_resolver import path_matches_prefix

MAX_REWRITE_ITERATIONS = 10


@dataclass(frozen=True)
class RewriteRule:
    match_prefix: str
    replacement_prefix: str


@dataclass(frozen=True)
class RewriteResult:
    final_path: str
    loop_detected: bool


def parse_rewrite_rules(raw_list: list[dict[str, Any]]) -> list[RewriteRule]:
    return [
        RewriteRule(match_prefix=item["match_prefix"], replacement_prefix=item["replacement_prefix"])
        for item in raw_list
    ]


def apply_rewrites(path: str, rules: list[RewriteRule]) -> RewriteResult:
    current = path
    seen = {current}

    for _ in range(MAX_REWRITE_ITERATIONS):
        matched_rule = next(
            (rule for rule in rules if path_matches_prefix(current, rule.match_prefix)), None
        )
        if matched_rule is None:
            return RewriteResult(final_path=current, loop_detected=False)

        current = matched_rule.replacement_prefix + current[len(matched_rule.match_prefix):]
        if current in seen:
            return RewriteResult(final_path=path, loop_detected=True)
        seen.add(current)

    return RewriteResult(final_path=path, loop_detected=True)
