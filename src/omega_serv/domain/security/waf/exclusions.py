"""Exclusions WAF par prefixe/extension (doc WAF, config generique
"exclusions"). C'est le mecanisme utilise par /healthz (angle mort
§9.6 du plan de developpement) pour echapper a l'inspection sans
casser aucune autre protection - un simple filtre, pas une politique
de zone complete (waf_service_policies, non construit en V1)."""
from __future__ import annotations

from omega_serv.domain.routing.zone_resolver import path_matches_prefix


def matches_any_prefix(path: str, prefixes: tuple[str, ...]) -> bool:
    """Frontiere de segment (OMEGA-SERV_ETUDE_RATE_LIMIT_EXCLUSIONS.md D5) :
    "/images" correspond a "/images" et "/images/..." mais plus a
    "/images-x" - meme mecanisme que les alias/redirections/cache."""
    return any(path_matches_prefix(path, prefix) for prefix in prefixes)


def is_extension_excluded(path: str, extensions: tuple[str, ...]) -> bool:
    lower_path = path.lower()
    return any(lower_path.endswith(ext.lower()) for ext in extensions)
