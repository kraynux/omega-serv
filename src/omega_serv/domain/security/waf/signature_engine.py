# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Moteur de signatures (doc WAF, module "signature_engine") : compile
les regles une fois, puis les evalue contre les textes de scope d'une
requete. Compilation et evaluation sont toutes deux du calcul pur (pas
d'I/O) - seul le CHARGEMENT du JSON depuis le disque est une
responsabilite d'infrastructure/waf/rule_pack_loader.py.

Sensitive-paths, scanner-user-agents, body-sqli/xss/cmdi sont TOUS des
packs de regles traites par ce meme moteur generique - aucun code
special par pack (doc WAF §3/§4 : ce sont des donnees, pas des
algorithmes distincts)."""
from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass

from omega_serv.domain.security.waf.entities import RuleDefinition, RulePack, Severity, WafFinding

# Poids -> severite indicative pour les logs/alertes (doc WAF §9 :
# "regle declenchee, score, decision" - la severite n'entre pas dans le
# calcul du score, seul le poids compte, mais elle aide un humain a lire
# une alerte sans consulter le pack de regles).
_SEVERITY_BY_WEIGHT_THRESHOLD: tuple[tuple[int, Severity], ...] = (
    (8, Severity.CRITICAL),
    (5, Severity.HIGH),
    (2, Severity.MEDIUM),
)


def _severity_for_weight(weight: int) -> Severity:
    for threshold, severity in _SEVERITY_BY_WEIGHT_THRESHOLD:
        if weight >= threshold:
            return severity
    return Severity.LOW


@dataclass(frozen=True)
class CompiledRule:
    definition: RuleDefinition
    pattern: re.Pattern[str]
    pack: str


@dataclass(frozen=True)
class CompiledRulePack:
    pack: str
    enabled: bool
    rules: tuple[CompiledRule, ...]


def compile_rule_pack(pack: RulePack) -> CompiledRulePack:
    """Suppose le pack deja valide (rule_validation.validate_rule_pack)
    - ne revalide pas, compile directement. Un motif invalide leverait
    ici `re.error`, jamais rattrape silencieusement."""
    flags_cache: dict[bool, int] = {True: re.IGNORECASE, False: 0}
    rules = tuple(
        CompiledRule(
            definition=rule,
            pattern=re.compile(rule.pattern, flags_cache[rule.case_insensitive]),
            pack=pack.pack,
        )
        for rule in pack.rules
        if rule.enabled
    )
    return CompiledRulePack(pack=pack.pack, enabled=pack.enabled, rules=rules)


def evaluate_rules(
    compiled_packs: tuple[CompiledRulePack, ...],
    scope_texts: Mapping[str, str],
    excluded_packs: frozenset[str] = frozenset(),
) -> tuple[WafFinding, ...]:
    """Evalue chaque regle activee, dans chaque pack active et non
    exclu, contre le texte du scope qu'elle cible. `scope_texts` ne
    contient que les scopes reellement disponibles pour cette requete
    (ex. pas de "body" si la methode n'est pas dans inspect.body_methods
    ou si le corps n'a pas ete capture) - une regle dont AUCUN scope
    n'est present est simplement ignoree, jamais une erreur."""
    findings: list[WafFinding] = []
    for compiled_pack in compiled_packs:
        if not compiled_pack.enabled or compiled_pack.pack in excluded_packs:
            continue
        for compiled_rule in compiled_pack.rules:
            rule = compiled_rule.definition
            for scope in rule.scope:
                text = scope_texts.get(scope)
                if not text:
                    continue
                if compiled_rule.pattern.search(text):
                    findings.append(
                        WafFinding(
                            rule_id=rule.id,
                            pack=compiled_pack.pack,
                            description=rule.description,
                            severity=_severity_for_weight(rule.weight),
                            weight=rule.weight,
                            scope=scope,
                        )
                    )
                    break  # une regle ne compte qu'une fois par requete, meme si plusieurs scopes matchent
    return tuple(findings)
