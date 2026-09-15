# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Cas d'usage : choisir et persister le theme TUI actif (plan
interface §3.1, Phase I) - porte depuis omega-check."""
from __future__ import annotations

from omega_lib.theme.policies import TUI_THEMES

from omega_serv.application.terminal.exceptions import UnknownThemeError
from omega_serv.ports.settings_store import SettingsStore

_THEME_KEY = "theme"


def select_theme(*, settings_store: SettingsStore, theme_name: str) -> None:
    if theme_name not in TUI_THEMES:
        raise UnknownThemeError(theme_name)
    settings_store.set(_THEME_KEY, theme_name)
