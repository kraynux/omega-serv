"""Cas d'usage : verifier la compatibilite d'un script magnet AVANT de
l'activer (TUI, ecran Magnet - `omega-serv waf test` fait un controle
equivalent au fil d'une requete testee). Reutilise le MEME pont
`lighty.*` que la vraie execution (infrastructure/waf/lua_waf_adapter.py)
- jamais une verification separee qui pourrait diverger du comportement
reel en production.

Isole dans application/ (pas interfaces.tui/) parce que `lua_waf_adapter.py`
depend de `lupa`, et `interfaces.tui` n'a pas le droit d'importer cette
dependance meme transitivement (pyproject.toml, contrat import-linter
"lupa seulement dans infrastructure.waf.lua_waf_adapter" - application/
en est deliberement exclue, meme raison que `start_server.py` construit
deja `LuaWafAdapter` par configuration)."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path

from omega_serv.domain.http.headers import HttpHeaders
from omega_serv.domain.http.request import HttpRequest
from omega_serv.domain.security.waf.config import MagnetConfig, WafConfig
from omega_serv.ports.filesystem_port import FilesystemPort

_COMPAT_CHECK_TIMEOUT_SECONDS = 5.0
"""Delai dedie a ce controle ponctuel - SANS RAPPORT avec
`magnet.timeout_ms` (regle par requete reelle, typiquement 50ms, trop
court pour un premier chargement/compile de script lors d'un diagnostic
manuel). Une valeur fixe, genereuse, evite qu'un script lent en premiere
execution (I/O, lecture de rate_store.lua existant) soit signale a tort
comme incompatible."""


@dataclass(frozen=True)
class MagnetCompatibilityCheck:
    """`construction_error`/`dependency_missing` : le script n'a meme
    pas pu etre charge (introuvable, syntaxe invalide, ou extra 'magnet'
    non installe) - `unsupported_members`/`dry_run_error` ne s'appliquent
    alors pas (restent a leurs valeurs par defaut, jamais une preuve de
    compatibilite)."""
    construction_error: str | None = None
    dependency_missing: bool = False
    unsupported_members: frozenset[str] = frozenset()
    dry_run_error: str | None = None


async def check_magnet_compatibility(
    magnet: MagnetConfig, project_root: Path, filesystem: FilesystemPort,
) -> MagnetCompatibilityCheck:
    from omega_serv.application.server.start_server import resolve_magnet_paths
    from omega_serv.infrastructure.waf.lua_waf_adapter import (
        WafMagnetScriptError,
        load_lua_waf_adapter,
    )

    script_path = project_root / magnet.script
    resolved_paths = resolve_magnet_paths(project_root, magnet.paths)
    waf_config = WafConfig(mode="block", magnet=magnet)
    try:
        adapter = load_lua_waf_adapter(filesystem, script_path, waf_config, resolved_paths)
    except WafMagnetScriptError as e:
        return MagnetCompatibilityCheck(construction_error=str(e))
    except ImportError:
        return MagnetCompatibilityCheck(dependency_missing=True)

    benign_request = HttpRequest(
        request_id="magnet-compat-check", remote_ip="127.0.0.1", peer_ip="127.0.0.1",
        method="GET", path="/", raw_path="/", query="",
        headers=HttpHeaders.from_pairs([]), body=None, content_length=None, is_tls=False,
    )
    loop = asyncio.get_running_loop()
    try:
        dry_run_error = await asyncio.wait_for(
            loop.run_in_executor(None, adapter.dry_run, benign_request),
            timeout=_COMPAT_CHECK_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        dry_run_error = "delai depasse (le script bloque trop longtemps sur une requete de test)"
    return MagnetCompatibilityCheck(unsupported_members=adapter.unsupported_members, dry_run_error=dry_run_error)
