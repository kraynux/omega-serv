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
    include_error_pages: bool = False
    """Pages d'erreur personnalisees (`error_pages.custom_dir`, `webroot/.errors/` par defaut)."""
    include_preferences: bool = False
    """`var/settings.json` : theme, langues (interface et pages visiteurs), dossiers d'export, nom du service."""
    include_logs_library: bool = False
    """Bibliotheque et favoris des journaux, sources distantes (chemin de cle seulement), rotations planifiees."""
    include_riposte: bool = False
    """Base RIPOSTE (memoire de recidive, decisions, actions) - les politiques sont dans la configuration."""
    description: str = ""

    @classmethod
    def everything(cls, description: str = "") -> BackupRequest:
        """« Tout sauvegarder » (decision utilisateur 2026-11-01) : configuration complete, y compris les
        secrets (zones Auth, cles TLS) - l'appelant DOIT faire confirmer les secrets."""
        return cls(
            include_waf_rules=True, include_auth_zones=True, include_certificates=True, include_active_defense=True,
            include_error_pages=True, include_preferences=True, include_logs_library=True, include_riposte=True,
            description=description,
        )

    @property
    def includes_databases(self) -> bool:
        return self.include_active_defense or self.include_riposte
