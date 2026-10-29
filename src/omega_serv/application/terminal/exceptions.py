"""Exceptions du sous-systeme interface interactive (plan interface
§3.1, Phase I) - meme racine que le reste du projet
(core/exceptions.py::OmegaServError), meme patron que
domain/services/exceptions.py."""
from __future__ import annotations

from omega_serv.core.exceptions import OmegaServError
from omega_serv.core.i18n import _


class UnsafeDirectoryError(OmegaServError):
    """Dossier qu'on refuse de vider (application/terminal/clear_directory.py)."""

    def __init__(self, path: str, reason: str):
        self.path = path
        self.reason = reason
        super().__init__(_("Dossier refusé ({reason}) : {path}").format(reason=reason, path=path))


class UnknownThemeError(OmegaServError):
    def __init__(self, theme_name: str):
        self.theme_name = theme_name
        super().__init__(_("thème inconnu : {theme_name!r}").format(theme_name=theme_name))


class UnknownLanguageError(OmegaServError):
    def __init__(self, language_code: str):
        self.language_code = language_code
        super().__init__(_("langue inconnue : {language_code!r}").format(language_code=language_code))
