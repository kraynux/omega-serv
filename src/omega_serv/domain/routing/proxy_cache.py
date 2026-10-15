"""Cache des reponses proxiees (OMEGA-SERV_PLAN-DETAILLE_REVERSE_PROXY.md
§21 : Phase 8) - le plus orthogonal des chantiers de cette etude,
n'interagit pas avec le CHOIX du backend, seulement avec la REPONSE une
fois obtenue. A ne jamais confondre avec `domain/routing/cache_policy.py`
(purement un en-tete `Cache-Control` SORTANT pour le fallback fichier
statique, jamais un cache serveur - verifie par recherche dediee avant
d'ecrire ce module, aucun code existant reutilisable pour interpreter
`Cache-Control`/`Vary` AMONT, a ecrire de zero) - nommage distinct
impose au TUI/a la doc pour ne jamais confondre les deux (§29.1/§30.2).

**Regles non negociables, jamais configurables a la baisse** (§21) :
- Jamais de cache sur une methode autre que GET/HEAD.
- Jamais de cache sur une reponse d'erreur (statut >= 400).
- Jamais de cache sur une reponse portant `Set-Cookie`, sauf si la zone
  l'assume explicitement (`cache_allow_set_cookie=True`, meme
  philosophie que `verify_upstream_tls=False` - un raccourci RISQUE,
  jamais un defaut silencieux).
Ces trois regles s'appliquent INDEPENDAMMENT de `cache_respect_upstream_
headers` - ce dernier ne controle QUE l'interpretation de `Cache-Control`/
`max-age`, jamais ces trois garde-fous.

**Support multi-variantes pour `Vary`** (ferme l'ecart precedemment
documente - ancienne simplification "une seule entree par cle primaire,
Vary different = MISS qui ecrase" retiree, §23 angle mort #3 reouvert) :
`primary_cache_key` (methode+host+chemin+query) identifie desormais une
FAMILLE de variantes, jamais une entree unique - `variant_cache_key`
derive une cle SECONDAIRE a partir des valeurs REELLEMENT observees des
en-tetes listes par `Vary` au moment de la pose (noms ET valeurs
toujours stockes dans l'entree elle-meme, `entry_matches_request` reste
le seul juge de correspondance). Plusieurs variantes d'une meme
ressource (ex. `Accept-Encoding: gzip` vs `identity`) coexistent donc
reellement sur disque, chacune evaluee independamment - jamais de
"dernier arrive gagne" qui ecraserait une variante encore valide.
Aucun plafond SEPARE par ressource (deliberement, §21/§24 - une seconde
limite redondante avec `cache_max_size_mb` deja existant) : le nombre de
variantes simultanees reste borne par le MEME plafond global LRU que le
reste du cache, jamais un knob supplementaire."""
from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import dataclass

_CACHEABLE_METHODS = frozenset({"GET", "HEAD"})


@dataclass(frozen=True)
class ProxyCacheEntry:
    status_code: int
    headers: tuple[tuple[str, str], ...]
    body: bytes
    stored_at: float
    """`time.time()` (horodatage mur, pas monotonic - affiche tel quel
    dans un futur outil de diagnostic, contrairement aux horloges
    internes de `ProxyLoadBalancerState`/`ProxyHealthState` qui restent
    `time.monotonic()` - ces deux etats ne sont jamais compares entre
    eux, aucun risque de confusion)."""
    ttl_seconds: float
    vary_header_names: tuple[str, ...]
    vary_header_values: tuple[str, ...]
    """Meme ordre que `vary_header_names` - valeurs de la requete au
    moment de la pose, cf. docstring de module (simplification Vary)."""


@dataclass(frozen=True)
class CacheControlDirectives:
    no_store: bool
    no_cache: bool
    private: bool
    max_age: int | None


def parse_cache_control_header(value: str | None) -> CacheControlDirectives:
    if not value:
        return CacheControlDirectives(no_store=False, no_cache=False, private=False, max_age=None)
    no_store = no_cache = private = False
    max_age: int | None = None
    for directive in value.split(","):
        token = directive.strip().lower()
        if token == "no-store":
            no_store = True
        elif token == "no-cache":
            no_cache = True
        elif token == "private":
            private = True
        elif token.startswith("max-age="):
            try:
                max_age = int(token[len("max-age="):].strip())
            except ValueError:
                pass
    return CacheControlDirectives(no_store=no_store, no_cache=no_cache, private=private, max_age=max_age)


def parse_vary_header(value: str | None) -> tuple[str, ...]:
    if not value:
        return ()
    return tuple(name.strip() for name in value.split(",") if name.strip())


def resolve_cache_ttl_seconds(
    response_headers: tuple[tuple[str, str], ...], *, respect_upstream_headers: bool, default_ttl_seconds: float,
) -> float | None:
    """`None` signifie "ne jamais mettre en cache cette reponse" (directive
    amont `no-store`/`no-cache`/`private`, consultee SEULEMENT si
    `respect_upstream_headers=True`). `cache_respect_upstream_headers=False`
    est un raccourci EXPLICITEMENT DANGEREUX (meme philosophie que
    `verify_upstream_tls=False`, §5.3) : il ignore ces directives et met
    en cache selon `default_ttl_seconds` quoi qu'en dise le backend -
    jamais le defaut, jamais silencieux."""
    if not respect_upstream_headers:
        return default_ttl_seconds
    raw = next((v for n, v in response_headers if n.lower() == "cache-control"), None)
    directives = parse_cache_control_header(raw)
    if directives.no_store or directives.no_cache or directives.private:
        return None
    if directives.max_age is not None:
        return float(directives.max_age)
    return default_ttl_seconds


def is_cacheable_request(method: str) -> bool:
    return method in _CACHEABLE_METHODS


def is_cacheable_response(
    status_code: int, response_headers: tuple[tuple[str, str], ...], *, allow_set_cookie: bool,
) -> bool:
    if status_code >= 400:
        return False
    return allow_set_cookie or not any(name.lower() == "set-cookie" for name, _ in response_headers)


def primary_cache_key(method: str, host: str, path: str, query: str) -> str:
    """Cle PRIMAIRE (methode+host+chemin+query, §21) - ne depend PAS des
    en-tetes `Vary` : identifie une FAMILLE de variantes (voir
    `variant_cache_key`), jamais une entree unique - le store expose
    `get_variants(zone_key, primary_key)` pour enumerer toutes les
    variantes connues de cette famille, departagees par
    `entry_matches_request`."""
    raw = f"{method}\n{host}\n{path}\n{query}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def variant_cache_key(
    primary_key: str, vary_header_names: tuple[str, ...], vary_header_values: tuple[str, ...],
) -> str:
    """Cle SECONDAIRE deterministe a partir des valeurs REELLES des
    en-tetes `Vary` au moment de la pose - deux requetes avec les memes
    valeurs pour ces en-tetes partagent la meme variante (reecrivent
    l'ancienne, jamais une accumulation infinie pour un meme jeu de
    valeurs) ; des valeurs differentes produisent une cle differente,
    donc une variante SEPAREE sur disque (separateur `\\x1f` - jamais
    confondu avec un caractere plausible dans un nom ou une valeur
    d'en-tete HTTP). `"--"` separe la partie primaire de l'empreinte de
    variante - sans risque de collision avec `primary_key` (toujours un
    hex sha256 de longueur fixe, jamais de `-`)."""
    fingerprint_raw = "\n".join(
        f"{name}\x1f{value}" for name, value in zip(vary_header_names, vary_header_values, strict=True)
    )
    fingerprint = hashlib.sha256(fingerprint_raw.encode("utf-8")).hexdigest()
    return f"{primary_key}--{fingerprint}"


def entry_matches_request(entry: ProxyCacheEntry, header_lookup: Callable[[str], str | None]) -> bool:
    return all(
        (header_lookup(name) or "") == stored_value
        for name, stored_value in zip(entry.vary_header_names, entry.vary_header_values, strict=True)
    )


def is_expired(entry: ProxyCacheEntry, *, now: float) -> bool:
    return (now - entry.stored_at) > entry.ttl_seconds
