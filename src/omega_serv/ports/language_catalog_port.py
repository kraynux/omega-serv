"""Catalogues de traduction de l'interface (OMEGA-SERV_PLAN-DETAILLE_I18N.md §5)."""
from __future__ import annotations

import gettext
from typing import Protocol

from omega_lib.i18n.models import LanguageStatus

from omega_serv.core.exceptions import OmegaServError


class LanguageCatalogError(OmegaServError):
    """Catalogue present mais illisible, ou absent."""


class LanguageCatalogPort(Protocol):
    def available(self) -> dict[str, LanguageStatus]:
        """Langues dont le catalogue est present (sans le francais, toujours disponible)."""
        ...

    def load(self, code: str) -> gettext.NullTranslations | None:
        """None pour le francais ; LanguageCatalogError si le catalogue manque ou est illisible."""
        ...
