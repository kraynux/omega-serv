"""Traduction de l'interface (OMEGA-SERV_PLAN-DETAILLE_I18N.md §5.2) - seul point d'acces
aux phrases traduites pour tout le code d'omega-serv.

    from omega_serv.core.i18n import _, N_, ngettext

- `_("Texte")` : phrase traduite dans la langue active (francais par defaut : texte tel quel).
- `ngettext("{n} entree", "{n} entrees", n)` : pluriels (3 formes en russe).
- `N_("Texte")` : marque une constante definie au chargement d'un module, traduite plus
  tard a l'affichage avec `_()`.

La langue est installee UNE fois, au demarrage, avant la construction de l'interface
(application/terminal/select_language.py::install_interface_language). Changer de langue
redemarre l'interface (os.execv), jamais le service. Le processus serveur
(`omega-serv serve`) ne l'installe jamais (D18b) : ses messages restent en francais."""
from __future__ import annotations

from omega_lib.i18n.policies import text_direction
from omega_lib.i18n.service import TranslationState, mark

DOMAIN = "omega-serv"
"""Nom des catalogues : locale/<langue>/LC_MESSAGES/omega-serv.mo."""

STATE = TranslationState()

PAGE_STATE = TranslationState()
"""Pages servies aux VISITEURS (pages d'erreur, listing de dossier - D19) : traduction distincte
de STATE. Le processus serveur l'installe (ses pages suivent la langue choisie dans omega-serv)
tout en n'installant jamais STATE (D18b : journalctl reste en francais)."""

N_ = mark


def _(message: str) -> str:
    return STATE.gettext(message)


def ngettext(singular: str, plural: str, n: int) -> str:
    return STATE.ngettext(singular, plural, n)


def P_(message: str) -> str:
    """Texte d'une page servie aux visiteurs (D19)."""
    return PAGE_STATE.gettext(message)


def _html_lang(state: TranslationState) -> str:
    code = state.language.code
    return "fr" if code.startswith("x-") else code.replace("_", "-")


def interface_html_lang() -> str:
    """Attribut lang= des exports HTML (langue de l'interface)."""
    return _html_lang(STATE)


def page_html_lang() -> str:
    """Valeur de l'attribut `<html lang="...">` des pages visiteurs (BCP 47 : zh_CN -> zh-CN ;
    la langue de controle reste annoncee comme du francais)."""
    code = PAGE_STATE.language.code
    if code.startswith("x-"):
        return "fr"
    return code.replace("_", "-")


def interface_html_dir() -> str:
    """Attribut dir= des exports HTML : "rtl" en arabe, "ltr" sinon."""
    return text_direction(STATE.language.code)


def page_html_dir() -> str:
    """Attribut dir= des pages visiteurs : "rtl" en arabe, "ltr" sinon."""
    return text_direction(PAGE_STATE.language.code)
