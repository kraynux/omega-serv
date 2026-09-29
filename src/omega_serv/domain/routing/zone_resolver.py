"""Resolution de zone generique (decision transverse, voir
OMEGA-SERV_PLAN_DEVELOPPEMENT.md §6) : alias, redirections, cache,
directory listing et (plus tard) auth/CSP/politiques de service WAF
matchent tous un chemin par prefixe d'URL. Un seul mecanisme partage
(plus-long-prefixe-gagne) plutot que chaque fonctionnalite reimplemente
sa propre logique de correspondance legerement differente."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, TypeVar

T = TypeVar("T")


@dataclass(frozen=True)
class Zone(Generic[T]):
    path_prefix: str
    data: T


def _normalize_prefix(prefix: str) -> str:
    """"/" reste un cas particulier (correspond a tout chemin, jamais
    reduit a une chaine vide utilisable telle quelle dans un
    startswith) - tout le reste perd son(ses) "/" final(aux) : c'est
    cette forme normalisee qui sert a la fois a la comparaison de match
    et au calcul de specificite (voir path_matches_prefix()/
    resolve_zone() ci-dessous)."""
    if prefix == "/":
        return ""
    return prefix.rstrip("/")


def path_matches_prefix(path: str, prefix: str) -> bool:
    """Retour utilisateur 2026-09-28 (bug reel rapporte, "amalgame entre
    /test/ et /test - le slash change le comportement... il faut
    uniformiser") : jusqu'ici chaque appelant de `path.startswith(prefix)`
    traitait "/old" et "/old/" comme deux prefixes DIFFERENTS - "/old"
    matchait a tort "/oldish-unrelated-page" (sur-matching, aucune notion
    de frontiere de segment), tandis que "/old/" ne matchait PAS le
    chemin exact "/old" sans slash final (sous-matching, une URL tapee
    sans slash tombait hors de la zone). Le "/" final d'un prefixe
    configure est desormais purement cosmetique : "/old" et "/old/"
    sont rigoureusement equivalents, matchent le chemin exact ainsi que
    tout sous-chemin sur une frontiere de "/" - jamais un prefixe de nom
    de segment partiel."""
    normalized = _normalize_prefix(prefix)
    if normalized == "":
        return True
    return path == normalized or path.startswith(normalized + "/")


def resolve_zone(path: str, zones: list[Zone[T]]) -> Zone[T] | None:
    """Retourne la zone dont le `path_prefix` correspond au chemin et
    est le plus long une fois normalise (la plus specifique gagne) -
    None si aucune zone ne correspond. "/old" et "/old/" comptent pour
    la MEME longueur de specificite (voir path_matches_prefix()) : deux
    regles equivalentes configurees sous ces deux formes departagent
    alors sur l'ordre de la liste (max() stable), jamais sur un artefact
    de longueur de chaine brute."""
    matches = [zone for zone in zones if path_matches_prefix(path, zone.path_prefix)]
    if not matches:
        return None
    return max(matches, key=lambda zone: len(_normalize_prefix(zone.path_prefix)))
