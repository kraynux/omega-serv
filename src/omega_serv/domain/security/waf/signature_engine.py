"""Moteur de signatures (doc WAF, module "signature_engine") : compile
les regles une fois, puis les evalue contre les textes de scope d'une
requete. Compilation et evaluation sont toutes deux du calcul pur (pas
d'I/O) - seul le CHARGEMENT du JSON depuis le disque est une
responsabilite d'infrastructure/waf/rule_pack_loader.py.

Sensitive-paths, scanner-user-agents, body-sqli/xss/cmdi sont TOUS des
packs de regles traites par ce meme moteur generique - aucun code
special par pack (doc WAF §3/§4 : ce sont des donnees, pas des
algorithmes distincts).

Voie rapide (2026-11-04, cout du WAF) : une regle insensible a la casse est
cherchee jusqu'a 6 fois plus lentement par `re` qu'une regle sensible. Quand le
texte est en ASCII et que la regle est PROUVEE equivalente sur l'ASCII
(`_folds_safely`), la recherche se fait sans IGNORECASE sur le texte mis en
minuscules - meme resultat, garanti par construction. Le moindre doute (non-ASCII,
majuscule dans le motif, drapeau en ligne, construction inconnue, parseur
indisponible) garde la recherche d'origine."""
from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from omega_serv.domain.security.waf.entities import RuleDefinition, RulePack, Severity, WafFinding

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


try:  # Python >= 3.11
    import re._parser as _sre_parser  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover - Python 3.10
    import sre_parse as _sre_parser

_ASCII = tuple(chr(code) for code in range(128))
_CATEGORY_CLASS = {
    "CATEGORY_DIGIT": r"\d", "CATEGORY_NOT_DIGIT": r"\D", "CATEGORY_SPACE": r"\s",
    "CATEGORY_NOT_SPACE": r"\S", "CATEGORY_WORD": r"\w", "CATEGORY_NOT_WORD": r"\W",
}


_PlanEntry = tuple[int, re.Pattern[str], "re.Pattern[str] | None", bool]


@dataclass(frozen=True)
class CompiledRule:
    definition: RuleDefinition
    pattern: re.Pattern[str]
    pack: str
    exclude: re.Pattern[str] | None = None
    # Voie rapide : memes motifs SANS IGNORECASE, a appliquer au texte ASCII mis en minuscules. None = jamais.
    folded_pattern: re.Pattern[str] | None = None
    folded_exclude: re.Pattern[str] | None = None


def _literal_folds(code: int) -> bool:
    """Un caractere du motif : ASCII et pas une majuscule (sinon un texte en minuscules ne le contient jamais ;
    un caractere non ASCII peut, avec IGNORECASE, egaler une lettre ASCII : « ſ » et « s », « K » et « k »)."""
    return code < 128 and not ("A" <= chr(code) <= "Z")


def _class_folds(items: list[tuple[Any, Any]]) -> bool:
    """Classe [...] : verifiee caractere par caractere sur les 128 caracteres ASCII, avec le vrai moteur -
    appartenance avec IGNORECASE == appartenance de sa minuscule sans IGNORECASE."""
    parts: list[str] = []
    for op, av in items:
        name = str(op)
        if name == "NEGATE":
            parts.insert(0, "^")
        elif name == "LITERAL":
            parts.append(f"\\U{av:08x}")
        elif name == "RANGE":
            parts.append(f"\\U{av[0]:08x}-\\U{av[1]:08x}")
        elif name == "CATEGORY" and str(av) in _CATEGORY_CLASS:
            parts.append(_CATEGORY_CLASS[str(av)])
        else:
            return False
    try:
        folded = re.compile(f"[{''.join(parts)}]")
        insensitive = re.compile(f"[{''.join(parts)}]", re.IGNORECASE)
    except re.error:
        return False
    return all(bool(insensitive.fullmatch(char)) == bool(folded.fullmatch(char.lower())) for char in _ASCII)


def _nodes_fold(nodes) -> bool:  # type: ignore[no-untyped-def]
    for op, av in nodes:
        name = str(op)
        if name in ("LITERAL", "NOT_LITERAL"):
            if not _literal_folds(av):
                return False
        elif name == "IN":
            if not _class_folds(av):
                return False
        elif name in ("ANY", "AT", "CATEGORY", "GROUPREF"):
            continue
        elif name == "BRANCH":
            if not all(_nodes_fold(branch) for branch in av[1]):
                return False
        elif name == "SUBPATTERN":
            _group, add_flags, del_flags, sub = av
            if add_flags or del_flags or not _nodes_fold(sub):
                return False
        elif name in ("MAX_REPEAT", "MIN_REPEAT", "POSSESSIVE_REPEAT"):
            if not _nodes_fold(av[2]):
                return False
        elif name in ("ASSERT", "ASSERT_NOT"):
            if not _nodes_fold(av[1]):
                return False
        elif name == "ATOMIC_GROUP":
            if not _nodes_fold(av):
                return False
        else:
            return False
    return True


def _folds_safely(pattern: str) -> bool:
    """Vrai si, pour TOUT texte ASCII t : search(pattern, t, IGNORECASE) == search(pattern, t.lower())."""
    try:
        parsed = _sre_parser.parse(pattern, re.IGNORECASE)
        return _nodes_fold(parsed.data)
    except Exception:  # noqa: BLE001 - parseur interne de `re` : au moindre doute, voie d'origine
        return False


def _folded(rule: RuleDefinition) -> tuple[re.Pattern[str] | None, re.Pattern[str] | None]:
    if not rule.case_insensitive or not _folds_safely(rule.pattern):
        return None, None
    if rule.exclude_pattern and not _folds_safely(rule.exclude_pattern):
        return None, None
    return re.compile(rule.pattern), (re.compile(rule.exclude_pattern) if rule.exclude_pattern else None)


@dataclass(frozen=True)
class CompiledRulePack:
    pack: str
    enabled: bool
    rules: tuple[CompiledRule, ...]
    # Plan d'evaluation par scope, calcule une fois (2026-11-04, cout du WAF) : (indice de la regle, motif,
    # exception, texte en minuscules ?). `folded_plan` : voie rapide si la regle le permet, sinon motif d'origine.
    plan: Mapping[str, tuple[_PlanEntry, ...]] = field(default_factory=dict, compare=False)
    folded_plan: Mapping[str, tuple[_PlanEntry, ...]] = field(default_factory=dict, compare=False)


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
            exclude=(
                re.compile(rule.exclude_pattern, flags_cache[rule.case_insensitive])
                if rule.exclude_pattern else None
            ),
            folded_pattern=folded[0],
            folded_exclude=folded[1],
        )
        for rule in pack.rules
        if rule.enabled
        for folded in (_folded(rule),)
    )
    plan: dict[str, list[_PlanEntry]] = {}
    folded_plan: dict[str, list[_PlanEntry]] = {}
    for index, compiled in enumerate(rules):
        for scope in dict.fromkeys(compiled.definition.scope):  # un scope cite deux fois = une recherche
            plan.setdefault(scope, []).append((index, compiled.pattern, compiled.exclude, False))
            folded_plan.setdefault(scope, []).append(
                (index, compiled.folded_pattern, compiled.folded_exclude, True) if compiled.folded_pattern is not None
                else (index, compiled.pattern, compiled.exclude, False)
            )
    return CompiledRulePack(
        pack=pack.pack, enabled=pack.enabled, rules=rules,
        plan={scope: tuple(entries) for scope, entries in plan.items()},
        folded_plan={scope: tuple(entries) for scope, entries in folded_plan.items()},
    )


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
    present = [(scope, text) for scope, text in scope_texts.items() if text]
    for compiled_pack in compiled_packs:
        if not compiled_pack.enabled or compiled_pack.pack in excluded_packs:
            continue
        # Scope par scope (seuls ceux presents dans la requete) ; indice de regle -> scopes qui ont matche.
        hits: dict[int, list[str]] | None = None
        for scope, text in present:
            ascii_text = text.isascii()
            entries = (compiled_pack.folded_plan if ascii_text else compiled_pack.plan).get(scope)
            if not entries:
                continue
            lowered = text.lower() if ascii_text else text
            for index, pattern, exclude, use_lowered in entries:
                subject = lowered if use_lowered else text
                if pattern.search(subject) and (exclude is None or not exclude.search(subject)):
                    if hits is None:
                        hits = {}
                    hits.setdefault(index, []).append(scope)
        if hits is None:
            continue
        for index in sorted(hits):
            compiled_rule = compiled_pack.rules[index]
            rule = compiled_rule.definition
            # une regle ne compte qu'une fois par requete : premier scope de SA liste qui a matche
            scope = next(candidate for candidate in rule.scope if candidate in hits[index])
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
    return tuple(findings)
