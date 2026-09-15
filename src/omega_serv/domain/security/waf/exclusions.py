# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Exclusions WAF par prefixe/extension (doc WAF, config generique
"exclusions"). C'est le mecanisme utilise par /healthz (angle mort
§9.6 du plan de developpement) pour echapper a l'inspection sans
casser aucune autre protection - un simple filtre, pas une politique
de zone complete (waf_service_policies, non construit en V1)."""
from __future__ import annotations


def matches_any_prefix(path: str, prefixes: tuple[str, ...]) -> bool:
    return any(path.startswith(prefix) for prefix in prefixes)


def is_extension_excluded(path: str, extensions: tuple[str, ...]) -> bool:
    lower_path = path.lower()
    return any(lower_path.endswith(ext.lower()) for ext in extensions)
