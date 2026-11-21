"""Code de service des options, charge seulement pour les options actives (passe memoire du 2026-11-19,
OMEGA-SERV_ETUDE_PROXY_ET_MEMOIRE.md §7).

Le serveur appelle `load_option_code` a sa construction, a chaque rechargement et quand le reverse proxy est active a
chaud. Dans le chemin d'une requete, le code d'une option est ensuite importe localement : une simple lecture de
sys.modules (0,3 us mesure), jamais une lecture disque, et seulement sur les requetes qui passent par cette option.
Les options du routage (reecritures, alias, FastCGI, envoi de fichiers...) sont chargees de la meme facon par
`routing_tables.build_routing_tables`, appelee ici aussi.

Une option absente de cette table ne coute rien de plus : son code reste charge en tete de module comme avant."""
from __future__ import annotations

import importlib
from collections.abc import Iterable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from omega_serv.domain.config.entities import OmegaServConfig

OPTION_MODULES: dict[str, tuple[str, ...]] = {
    "waf": (
        "omega_serv.application.security.evaluate_waf_request",
        "omega_serv.domain.logging.waf_alert_format",
    ),
    "active_defense": (
        "omega_serv.application.active_defense.manage_deception",
        "omega_serv.application.active_defense.manage_incidents",
        "omega_serv.application.active_defense.observe_threat",
        "omega_serv.domain.security.active_defense.policies",
        "omega_serv.domain.logging.security_event_format",
        "omega_serv.domain.logging.active_defense_enriched_log_format",
        "omega_serv.application.server.serve_proxy",  # leurres de niveau 2
    ),
    "auth": (
        "omega_serv.domain.security.auth.authorize",
        "omega_serv.domain.security.auth.basic_auth",
    ),
    "reverse_proxy": (
        "omega_serv.application.server.serve_proxy",
        "omega_serv.application.server.serve_websocket_proxy",
    ),
}


def preload_server_code(config: OmegaServConfig, *extra: str) -> None:
    """Code du serveur Python et des options actives charge dans un processus qui va faire naitre (fork) ceux qui
    serviront : leurs pages restent partagees (mode boost, mesure 2026-11-19 : 2 workers 44,6 -> 38,0 Mo ; processus
    de securite du superviseur complet). `extra` : modules en plus."""
    for module in ("asyncio", "omega_serv.application.config.load_config", "omega_serv.application.server.start_server",
                   "omega_serv.infrastructure.server.asyncio_server", *extra):
        importlib.import_module(module)
    load_option_code(config, [name for name in OPTION_MODULES if config.option_enabled(name)])


def load_option_code(config: OmegaServConfig, active: Iterable[str]) -> None:
    """`active` : options dont le serveur a recu les collaborateurs (un WAF force par `waf test` compte)."""
    from omega_serv.application.server.routing_tables import routing_tables

    for option in active:
        for module in OPTION_MODULES.get(option, ()):
            importlib.import_module(module)
    routing_tables(config)
