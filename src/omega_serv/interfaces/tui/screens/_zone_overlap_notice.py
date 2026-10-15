"""Avertissement de chevauchement de prefixe depuis chaque ecran CRUD de
zone concerne (OMEGA-SERV_PLAN-DETAILLE_REVERSE_PROXY.md §29.4/§30.1) -
`domain/config/rules.py::detect_zone_prefix_overlaps` existe depuis
l'item 2 de l'ordre de construction (§26) mais n'etait jusqu'ici cable
que sur l'ecran central `ConfigCheckScreen` ("pas encore dupliquee dans
chaque ecran CRUD individuel", note de fin du §32) - ce module ferme cet
angle mort en appelant la meme fonction juste apres chaque sauvegarde
reelle, filtree sur le type de zone de l'ecran appelant.

Toujours un avertissement non bloquant (`severity="warning"`, jamais
"error") - un chevauchement peut etre parfaitement voulu (meme principe
que `detect_zone_prefix_overlaps` lui-meme) : ceci ne fait qu'eviter que
l'utilisateur le decouvre seulement en ouvrant `ConfigCheckScreen`
separement, jamais une nouvelle regle de validation."""
from __future__ import annotations

from typing import TYPE_CHECKING

from omega_serv.application.config.load_config import load_config
from omega_serv.domain.config.rules import detect_zone_prefix_overlaps

if TYPE_CHECKING:
    from omega_serv.bootstrap.container import DependencyContainer
    from omega_serv.interfaces.tui.screens._base import OmegaScreen


def notify_zone_prefix_overlaps(screen: OmegaScreen, container: DependencyContainer, zone_type: str) -> None:
    """`zone_type` : le type EXACT tel qu'utilise par
    `domain/config/rules.py::_collect_dispatch_zone_prefixes` ("alias"
    au singulier, "redirects", "fastcgi", "reverse_proxy" - jamais la
    cle de `config.options` telle quelle pour "alias", qui differe
    ("aliases") - verifie par lecture directe de rules.py plutot que
    suppose."""
    load_result = load_config(container.configuration, container.config_file)
    if not load_result.success or load_result.config is None:
        return
    needle = f"options.{zone_type} ("
    for conflict in detect_zone_prefix_overlaps(load_result.config):
        if needle in conflict.message:
            screen.app.notify(conflict.message, severity="warning", timeout=10)
