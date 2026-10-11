"""Listes de mots-clefs WAF (OMEGA-SERV_PLAN-DETAILLE_REFERER_ET_MAGNET_
WAF.md, lot B) : format texte "un mot-clef par ligne", pense pour une
liste qui s'allonge dans le temps (ex. mots-clefs de spam Referer) sans
avoir a reecrire un `RuleDefinition` JSON complet a chaque ajout.

Fonctions pures uniquement - aucune I/O ici (ca, c'est infrastructure/
waf/keyword_list_loader.py). Chaque mot-clef est echappe (`re.escape`)
avant d'etre joint en alternance : l'utilisateur ecrit des mots/sous-
chaines simples, jamais une regex brute a ecrire a la main - ce qui
elimine par construction tout risque de regex catastrophiquement
retro-active (ReDoS) ou de syntaxe cassee via un simple mot-clef."""
from __future__ import annotations

import re
from typing import Any

from omega_serv.domain.config.validation import is_safe_relative_path
from omega_serv.domain.security.waf.entities import (
    _VALID_SCOPES,
    KeywordListDefinition,
    RuleDefinition,
    RulePack,
)


def tokens_from_text(text: str) -> tuple[str, ...]:
    """Une ligne = un mot-clef. Lignes vides et lignes commencant par
    '#' (apres espaces de tete) ignorees - jamais de syntaxe plus
    riche que ca (pas de guillemets, pas d'echappement a la charge de
    l'utilisateur, voir note de securite en tete de module)."""
    tokens: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        tokens.append(line)
    return tuple(tokens)


def compile_keyword_pattern(tokens: tuple[str, ...]) -> str:
    """Construit une alternance regex a partir de mots-clefs en clair,
    chacun echappe individuellement (`re.escape`) - jamais une regex
    utilisateur assemblee telle quelle."""
    return "(" + "|".join(re.escape(token) for token in tokens) + ")"


def parse_keyword_list_definition(data: dict[str, Any]) -> KeywordListDefinition:
    scope = data.get("scope", [])
    return KeywordListDefinition(
        id=str(data.get("id", "")),
        scope=tuple(scope) if isinstance(scope, list) else tuple(scope.split(",")),
        file=str(data.get("file", "")),
        weight=int(data.get("weight", 1)),
        enabled=bool(data.get("enabled", True)),
    )


def validate_keyword_list_definition(definition: KeywordListDefinition) -> list[str]:
    """Validation structurelle pure (pas d'I/O - l'existence reelle du
    fichier est verifiee par application/config/validate_config.py,
    meme repartition que RulePack/rule_validation.py)."""
    errors: list[str] = []
    if not definition.id:
        errors.append("keyword_lists : 'id' ne peut pas etre vide")
    if not definition.scope:
        errors.append(f"keyword_lists[{definition.id!r}] : 'scope' ne peut pas etre vide")
    unknown_scopes = set(definition.scope) - _VALID_SCOPES
    if unknown_scopes:
        errors.append(f"keyword_lists[{definition.id!r}] : scope inconnu : {sorted(unknown_scopes)}")
    if not is_safe_relative_path(definition.file):
        errors.append(
            f"keyword_lists[{definition.id!r}] : 'file' doit etre un chemin relatif au projet, "
            f"sans '..' : {definition.file!r}"
        )
    if definition.weight < 0:
        errors.append(f"keyword_lists[{definition.id!r}] : 'weight' doit etre >= 0")
    return errors


def validate_keyword_list_definitions(definitions: tuple[KeywordListDefinition, ...]) -> list[str]:
    errors: list[str] = []
    for definition in definitions:
        errors.extend(validate_keyword_list_definition(definition))
    ids = [d.id for d in definitions]
    duplicates = {i for i in ids if ids.count(i) > 1}
    if duplicates:
        errors.append(f"keyword_lists : id duplique(s) : {sorted(duplicates)}")
    return errors


def build_rule_pack_from_keyword_list(definition: KeywordListDefinition, tokens: tuple[str, ...]) -> RulePack:
    """Construit un `RulePack` synthetique a une seule regle - jamais
    compile ici (voir infrastructure/waf/keyword_list_loader.py, qui
    delegue la compilation reelle a signature_engine.compile_rule_pack,
    exactement comme un pack JSON classique : aucune seconde logique de
    compilation a maintenir)."""
    if not tokens:
        rule_pattern = r"(?!)"  # liste vide = ne matche jamais, jamais une erreur de compilation
    else:
        rule_pattern = compile_keyword_pattern(tokens)
    return RulePack(
        version=1,
        pack=definition.id,
        enabled=definition.enabled,
        rules=(
            RuleDefinition(
                id=definition.id,
                description=f"Liste de mots-clefs ({len(tokens)} entree(s))",
                scope=definition.scope,
                pattern=rule_pattern,
                case_insensitive=True,
                weight=definition.weight,
                enabled=definition.enabled,
            ),
        ),
    )
