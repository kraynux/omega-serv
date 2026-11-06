"""Acces commun des ecrans INTERVENTION MANUELLE (Bannir, Debannir, Statut) : configuration chargee + BlocklistPort,
par la meme fabrique que WAF -> Modules (meme fichier, meme verrou, memes droits)."""
from __future__ import annotations

from typing import TYPE_CHECKING

from omega_serv.application.config.load_config import load_config
from omega_serv.core.i18n import _

if TYPE_CHECKING:
    from omega_serv.bootstrap.container import DependencyContainer
    from omega_serv.domain.config.entities import OmegaServConfig
    from omega_serv.ports.blocklist_port import BlocklistPort


class BlocklistUnavailable(Exception):
    """Configuration illisible ou blocklist indisponible : le message (traduit) est pret a afficher."""


def open_blocklist(container: DependencyContainer) -> tuple[OmegaServConfig, BlocklistPort]:
    result = load_config(container.configuration, container.config_file)
    if not result.success or result.config is None:
        raise BlocklistUnavailable(_("Erreur de configuration."))
    factory = container.blocklist_port_factory
    if factory is None:
        raise BlocklistUnavailable(_("Blocklist indisponible dans cet environnement."))
    return result.config, factory(result.config, container.filesystem, container.project_root, container.clock)
