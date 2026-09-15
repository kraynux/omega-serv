# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Exceptions du sous-systeme interface interactive (plan interface
§3.1, Phase I) - meme racine que le reste du projet
(core/exceptions.py::OmegaServError), meme patron que
domain/services/exceptions.py."""
from __future__ import annotations

from omega_serv.core.exceptions import OmegaServError


class UnknownThemeError(OmegaServError):
    def __init__(self, theme_name: str):
        self.theme_name = theme_name
        super().__init__(f"theme inconnu : {theme_name!r}")
