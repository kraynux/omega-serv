# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Helpers partages par waf_modules_screen.py et waf_custom_rule_screen.py
(retour utilisateur 2026-09-13) - lire/ecrire `options.waf.settings.
rules.paths` est la MEME operation dans les deux ecrans (le second doit
pouvoir s'auto-referencer sans passer par le premier, pour eviter
exactement la confusion deja rencontree : "j'ai cree une regle dans
l'interface, elle ne se declenche jamais" - le pack custom.json existait
mais n'etait jamais reference). Fonctions PURES (aucune I/O ici -
lire/ecrire le fichier de config reste a la charge de chaque appelant)."""
from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from omega_serv.domain.config.option import Option

if TYPE_CHECKING:
    from omega_serv.domain.config.entities import OmegaServConfig


def get_waf_rule_paths(config: OmegaServConfig) -> list[str]:
    settings = config.options["waf"].settings if "waf" in config.options else {}
    return list(settings.get("rules", {}).get("paths", []))


def with_waf_rule_paths(config: OmegaServConfig, paths: list[str]) -> OmegaServConfig:
    existing = config.options.get("waf")
    enabled = existing.enabled if existing is not None else False
    new_settings = dict(existing.settings) if existing is not None else {}
    new_settings["rules"] = {"paths": paths}
    new_options = dict(config.options)
    new_options["waf"] = Option(name="waf", enabled=enabled, settings=new_settings)
    return replace(config, options=new_options)
