# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Zones de controle d'acces par prefixe d'URL (retour utilisateur
2026-09-09) - bloque des requetes (toutes methodes) sur un prefixe tout
en pouvant re-autoriser un sous-chemin precis, ex: deny "/private/",
allow "/private/.assets/" (comportement recherche : Apache
Deny/Allow, IIS <location>). Reutilise ZoneResolver (deja utilise par
alias/redirections/cache/dirlisting/auth/upload, plan de developpement
§6) plutot qu'un nouveau moteur de correspondance : le plus long
prefixe gagne deja naturellement, ce qui donne exactement la semantique
"l'enfant plus specifique l'emporte sur le parent" recherchee ici, sans
code nouveau pour cette partie.

Distinct de `domain/security/access_policy.py::is_denied_path`
(filtre global par nom/extension/motif de fichier, aucune notion de
prefixe) et du WAF (`secure/waf/rules/sensitive-paths.json`, signatures
regex a score, pas un ACL par repertoire) - aucun des deux ne couvrait
ce besoin (verifie par recherche exhaustive avant d'ecrire ce module).

`extensions` (retour utilisateur - guide d'aide, point 2 : bloquer des
extensions sensibles PARTOUT SAUF dans une zone precise, meme esprit
que l'exemple lighttpd "SECURITE ARCH LINUX") - une regle dont
`extensions` est vide s'applique a tout chemin sous son prefixe (comme
avant, retro-compatible) ; une regle avec `extensions` non vide ne
devient candidate que si le chemin se termine par l'une d'elles.
Filtrer les regles NON candidates avant d'appeler `resolve_zone` (plus
long prefixe gagne) plutot que de reimplementer cette selection ici -
laisse le mecanisme partage inchange, cf. docstring plus haut."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from omega_serv.domain.routing.zone_resolver import Zone, resolve_zone

_VALID_VERDICTS = ("allow", "deny")


@dataclass(frozen=True)
class AccessRule:
    path_prefix: str
    verdict: str  # "allow" | "deny"
    extensions: tuple[str, ...] = field(default_factory=tuple)


def parse_access_rules(raw_list: list[dict[str, Any]]) -> list[AccessRule]:
    return [
        AccessRule(
            path_prefix=item["path_prefix"],
            verdict=item["verdict"],
            extensions=tuple(item.get("extensions", [])),
        )
        for item in raw_list
    ]


def validate_access_rule(rule: AccessRule) -> str | None:
    if not rule.path_prefix.startswith("/"):
        return f"path_prefix doit commencer par '/' : {rule.path_prefix!r}"
    if rule.verdict not in _VALID_VERDICTS:
        return f"verdict invalide (attendu allow/deny) : {rule.verdict!r}"
    return None


def _applicable_rules(path: str, rules: list[AccessRule]) -> list[AccessRule]:
    lower_path = path.lower()
    return [
        rule for rule in rules
        if not rule.extensions or any(lower_path.endswith(ext.lower()) for ext in rule.extensions)
    ]


def resolve_access_verdict(path: str, rules: list[AccessRule]) -> str:
    """"allow" si aucune regle ne correspond (option absente/liste
    vide = aucune restriction, retro-compatible) ou si la zone la plus
    specifique correspondante est "allow"."""
    if not rules:
        return "allow"
    applicable = _applicable_rules(path, rules)
    if not applicable:
        return "allow"
    zones = [Zone(path_prefix=rule.path_prefix, data=rule.verdict) for rule in applicable]
    zone = resolve_zone(path, zones)
    return zone.data if zone is not None else "allow"


def has_explicit_allow_match(path: str, rules: list[AccessRule]) -> bool:
    """Distinct de resolve_access_verdict()=="allow" : une regle a
    reellement matche EXPLICITEMENT ce chemin avec le verdict "allow",
    ce n'est pas juste l'absence de correspondance. Utilise par
    serve_static_file.py pour lever ponctuellement `deny_hidden_files`/
    `deny_patterns` (domain/security/access_policy.py, regles globales
    sans notion de prefixe) sur un chemin explicitement re-autorise
    par l'administrateur - cas reel demande : re-autoriser un
    sous-dossier `.assets/` a l'interieur d'un prefixe par ailleurs
    bloque, meme si son nom commence par un point."""
    if not rules:
        return False
    applicable = _applicable_rules(path, rules)
    if not applicable:
        return False
    zones = [Zone(path_prefix=rule.path_prefix, data=rule.verdict) for rule in applicable]
    zone = resolve_zone(path, zones)
    return zone is not None and zone.data == "allow"
