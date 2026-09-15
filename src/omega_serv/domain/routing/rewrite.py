# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Reecriture interne de chemin (spec §17.3) : compteur maximal de
reecritures, detection de boucle - en cas de boucle ou de depassement,
echec explicite (traite comme une erreur serveur par l'appelant, jamais
un chemin devine ou un silence)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

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
        matched_rule = next((rule for rule in rules if current.startswith(rule.match_prefix)), None)
        if matched_rule is None:
            return RewriteResult(final_path=current, loop_detected=False)

        current = matched_rule.replacement_prefix + current[len(matched_rule.match_prefix):]
        if current in seen:
            return RewriteResult(final_path=path, loop_detected=True)
        seen.add(current)

    return RewriteResult(final_path=path, loop_detected=True)
