"""Parsing et validation structurelle d'un pack de regles WAF (doc WAF,
"Format de regles generique"). Pur : ne compile aucune regex ici (voir
signature_engine.py, qui separe volontairement la structure de donnees
de sa forme compilee/executable) et ne lit aucun fichier (ca,
c'est infrastructure/waf/rule_pack_loader.py)."""
from __future__ import annotations

import re
from typing import Any

from omega_serv.core.i18n import _
from omega_serv.domain.security.waf.entities import _VALID_SCOPES, RuleDefinition, RulePack

SUPPORTED_RULE_PACK_VERSIONS = frozenset({1})


def build_path_segment_pattern(segment: str) -> str:
    """Motif regex pour une detection "chemin precis" (retour
    utilisateur 2026-09-14 : "un utilisateur qui ne sait pas coder doit
    pouvoir utiliser" l'ecran WAF Custom - assistant de creation de
    regle, jamais de regex a ecrire a la main pour ce cas). `segment`
    est une valeur EN CLAIR (ex: "admin", jamais deja une regex) -
    `re.escape` neutralise tout caractere special qu'un utilisateur non
    averti pourrait taper sans le savoir (ex: "prix.php" -> le "." ne
    doit jamais devenir "n'importe quel caractere"). "/admin" ne doit
    jamais matcher "/administrator" - `(/|$)` l'exclut explicitement."""
    cleaned = segment.strip().strip("/")
    return f"/{re.escape(cleaned)}(/|$)" if cleaned else ""


def build_keyword_pattern(word: str) -> str:
    """Motif regex pour une detection "mot-cle" (meme assistant,
    memes raisons) - simple echappement, aucun metacaractere regex
    jamais interprete depuis une valeur saisie en clair."""
    return re.escape(word.strip())


def parse_rule_pack(data: dict[str, Any]) -> RulePack:
    rules = tuple(
        RuleDefinition(
            id=item["id"],
            description=item.get("description", ""),
            scope=tuple(item["scope"]),
            pattern=item["pattern"],
            case_insensitive=bool(item.get("case_insensitive", True)),
            weight=int(item.get("weight", 1)),
            action=item.get("action", "score"),
            enabled=bool(item.get("enabled", True)),
        )
        for item in data.get("rules", [])
    )
    return RulePack(
        version=int(data.get("version", 1)),
        pack=data["pack"],
        enabled=bool(data.get("enabled", True)),
        rules=rules,
    )


def validate_rule_pack(pack: RulePack) -> list[str]:
    """Valide la structure ET la compilabilite des motifs (compiler un
    motif pour verifier sa validite ne cree pas d'etat partage - le
    Pattern est jete ici, signature_engine.py recompile pour l'usage
    reel)."""
    errors: list[str] = []
    if pack.version not in SUPPORTED_RULE_PACK_VERSIONS:
        errors.append(_("{pack} : version de pack non supportée : {version}").format(pack=pack.pack, version=pack.version))

    seen_ids: set[str] = set()
    for rule in pack.rules:
        if not rule.id:
            errors.append(_("{pack} : une règle a un id vide").format(pack=pack.pack))
            continue
        if rule.id in seen_ids:
            errors.append(_("{pack} : id de règle dupliqué : {id}").format(pack=pack.pack, id=rule.id))
        seen_ids.add(rule.id)

        unknown_scopes = set(rule.scope) - _VALID_SCOPES
        if unknown_scopes:
            errors.append(_("{pack}/{id} : scope inconnu : {value}").format(pack=pack.pack, id=rule.id, value=sorted(unknown_scopes)))
        if not rule.scope:
            errors.append(_("{pack}/{id} : scope ne peut pas être vide").format(pack=pack.pack, id=rule.id))
        if rule.action != "score":
            errors.append(_("{pack}/{id} : action non supportée en V1 : {action!r}").format(pack=pack.pack, id=rule.id, action=rule.action))
        if rule.weight < 0:
            errors.append(_("{pack}/{id} : weight doit être >= 0").format(pack=pack.pack, id=rule.id))

        try:
            re.compile(rule.pattern)
        except re.error as e:
            errors.append(_("{pack}/{id} : motif regex invalide ({e})").format(pack=pack.pack, id=rule.id, e=e))

    return errors
