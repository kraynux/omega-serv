# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Requete de sauvegarde de configuration (plan interface §3.5) -
specifique a SERV (le `BackupRequest` original d'omega-fire est lie a
`BanEntry`/`FirewallRule`/`Jail`, aucun equivalent cote SERV, non porte).
`include_config` par defaut a True et n'est pas desactivable par la CLI
(§3.5 du plan : la commande `config backup` n'expose que
--include-waf/--include-auth/--include-certificates - le fichier de
configuration lui-meme fait toujours partie d'une sauvegarde)."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BackupRequest:
    include_config: bool = True
    include_waf_rules: bool = False
    include_auth_zones: bool = False
    include_certificates: bool = False
    include_active_defense: bool = False
    """plan_active_defense_omega_serv.md, Phase 6 ("retention, purge,
    sauvegarde/restauration de la base Active Defense") - inclut la base
    sqlite (menaces/incidents/affectations de leurre), jamais les
    exports IoC/rapport (regenerables a partir des incidents, cf.
    `incidents export-ioc`/`generate-report`). Comme `include_waf_rules`/
    `include_certificates`, aucun secret en clair (contrairement a
    `include_auth_zones`) - pas de gate `--confirm-secrets`."""
    description: str = ""
