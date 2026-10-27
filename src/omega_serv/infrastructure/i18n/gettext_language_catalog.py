"""Catalogues gettext livres avec omega-serv (src/omega_serv/locale/), lus via omega-lib."""
from __future__ import annotations

import gettext
from pathlib import Path

from omega_lib.i18n.models import LanguageStatus
from omega_lib.infrastructure.i18n.gettext_catalogs import (
    CatalogError,
    discover_catalogs,
    load_translations,
)

from omega_serv.core.i18n import DOMAIN
from omega_serv.ports.language_catalog_port import LanguageCatalogError

DEFAULT_LOCALE_DIR = Path(__file__).resolve().parents[2] / "locale"


class GettextLanguageCatalog:
    """Implemente ports/language_catalog_port.py::LanguageCatalogPort."""

    def __init__(self, locale_dir: Path = DEFAULT_LOCALE_DIR, domain: str = DOMAIN) -> None:
        self._locale_dir = locale_dir
        self._domain = domain

    def available(self) -> dict[str, LanguageStatus]:
        return discover_catalogs(self._locale_dir, self._domain)

    def load(self, code: str) -> gettext.NullTranslations | None:
        try:
            return load_translations(self._locale_dir, self._domain, code)
        except CatalogError as e:
            raise LanguageCatalogError(str(e)) from e
