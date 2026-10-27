"""Cas d'usage : langue de l'interface (OMEGA-SERV_PLAN-DETAILLE_I18N.md §5.3/§5.4, lot 2).

Ordre de priorite au demarrage :
  1. variable d'environnement OMEGA_SERV_LANG (une fois, sans toucher au reglage) - voie de
     secours : `OMEGA_SERV_LANG=fr serv` relance en francais ;
  2. reglage `language` de var/settings.json (choisi dans Options -> "Langue / Language") ;
  3. francais.
Langue indisponible ou catalogue illisible : francais, et le repli est memorise pour etre
signale une fois a l'ecran. Jamais d'erreur au demarrage.

Pages servies aux visiteurs (pages d'erreur, listing de dossier) : reglage SEPARE
`page_language` (decision utilisateur 2026-10-23, D19 revue) - la langue de l'interface ne les
touche jamais ; francais par defaut, choisi dans l'ecran Pages d'erreur.

Console TTY Linux (police limitee) avec une langue a ecriture chinoise, devanagari, arabe ou
vietnamienne (ajoutee 2026-10-23 : police viscii sans cadres) :
anglais pour CETTE session seulement, avec un message (decision utilisateur 2026-10-22) - le
reglage n'est pas modifie."""
from __future__ import annotations

from collections.abc import Mapping

from omega_lib.i18n.models import Language, LanguageChoice
from omega_lib.i18n.policies import (
    PSEUDO_LANGUAGE_CODE,
    SOURCE_LANGUAGE_CODE,
    console_fallback_language,
    language_for,
    normalize_language_code,
    ordered_languages,
    resolve_language,
)
from omega_lib.i18n.service import TranslationState

from omega_serv.application.terminal.exceptions import UnknownLanguageError
from omega_serv.core.i18n import PAGE_STATE, STATE
from omega_serv.ports.language_catalog_port import LanguageCatalogError, LanguageCatalogPort
from omega_serv.ports.settings_store import SettingsStore

LANGUAGE_KEY = "language"
PAGE_LANGUAGE_KEY = "page_language"
EXPORT_LANGUAGE_KEY = "export_language"
"""Langue des documents exportes pour etre partages (HTML, rapport d'incident Markdown) -
decision utilisateur 2026-10-23 : un reglage unique dans Options, "" = comme l'interface."""
LANGUAGE_ENV_VAR = "OMEGA_SERV_LANG"
LANGUAGE_CHANGED_ENV_VAR = "OMEGA_SERV_LANGUAGE_CHANGED"
"""Pose par __main__.py juste avant os.execv() : le nouveau processus affiche le splash de
confirmation dans la nouvelle langue (meme canal que OMEGA_SERV_SWITCHED_FROM)."""

_console_fallback_from: str | None = None


def console_fallback_from() -> str | None:
    """Langue choisie mais remplacee par l'anglais faute de pouvoir l'afficher dans ce terminal
    (signalee une fois a l'ecran), sinon None."""
    return _console_fallback_from


# Terminaux qui composent eux-memes les groupes de lettres liees devanagari sur un nombre de
# cases variable (selon le groupe et la police) : aucun calcul de largeur ne peut tomber
# juste, cadres et colonnes se decalent en hindi (mesure reelle 2026-10-26 dans Kitty et
# Konsole ; VTE - Terminator, GNOME Terminal, Xfce Terminal - et Alacritty sont alignes).
# Decision utilisateur : interface conservee en hindi, avertissement au demarrage.
_DEVANAGARI_SHAPING_TERMINALS = frozenset({"kitty", "ghostty", "konsole"})


def devanagari_misaligned_in(language_code: str, terminal_family: str) -> bool:
    return language_code == "hi" and terminal_family in _DEVANAGARI_SHAPING_TERMINALS


INCLUDE_PSEUDO_LANGUAGE = False
"""Langue de controle ⟦…⟧ (plan §4.7), utilisee pendant les lots de traduction ; masquee
depuis la 2.0.0 (plan §12). Remettre a True le temps d'un futur lot de traduction."""


def available_languages(catalog: LanguageCatalogPort) -> list[Language]:
    return ordered_languages(catalog.available(), include_pseudo=INCLUDE_PSEUDO_LANGUAGE)


def select_language(*, settings_store: SettingsStore, catalog: LanguageCatalogPort, language_code: str) -> Language:
    """Enregistre la langue choisie ; appliquee au redemarrage de l'interface."""
    code = normalize_language_code(language_code)
    offered = {language.code: language for language in available_languages(catalog)}
    if code not in offered:
        raise UnknownLanguageError(language_code)
    settings_store.set(LANGUAGE_KEY, "" if code == SOURCE_LANGUAGE_CODE else code)
    return offered[code]


def select_page_language(*, settings_store: SettingsStore, catalog: LanguageCatalogPort, language_code: str) -> Language:
    """Enregistre la langue des pages visiteurs ; appliquee au prochain demarrage du serveur."""
    code = normalize_language_code(language_code)
    offered = {language.code: language for language in available_languages(catalog)}
    if code not in offered:
        raise UnknownLanguageError(language_code)
    settings_store.set(PAGE_LANGUAGE_KEY, "" if code == SOURCE_LANGUAGE_CODE else code)
    return offered[code]


def page_language_code(settings_store: SettingsStore) -> str:
    """Code enregistre pour les pages visiteurs ('fr' si absent)."""
    return normalize_language_code(settings_store.get(PAGE_LANGUAGE_KEY, "") or "") or SOURCE_LANGUAGE_CODE


def select_export_language(*, settings_store: SettingsStore, catalog: LanguageCatalogPort, language_code: str) -> None:
    """Enregistre la langue des exports ; "" = comme l'interface. Effet immediat (chaque
    export lit le reglage au moment ou il est demande)."""
    if not language_code:
        settings_store.set(EXPORT_LANGUAGE_KEY, "")
        return
    code = normalize_language_code(language_code)
    offered = {language.code for language in available_languages(catalog)}
    if code not in offered:
        raise UnknownLanguageError(language_code)
    settings_store.set(EXPORT_LANGUAGE_KEY, code)


def export_language_override(settings_store: SettingsStore, interface_code: str) -> str | None:
    """Langue a utiliser pour un export, ou None s'il suit la langue de l'interface (reglage
    vide ou identique) - dans ce cas l'export se fait comme avant, dans le processus."""
    code = normalize_language_code(settings_store.get(EXPORT_LANGUAGE_KEY, "") or "")
    if not code or code == interface_code:
        return None
    return code


def install_page_language(
    *, settings_store: SettingsStore, catalog: LanguageCatalogPort, state: TranslationState = PAGE_STATE,
) -> LanguageChoice:
    """Langue des pages visiteurs : uniquement `page_language`, jamais OMEGA_SERV_LANG ni la
    langue de l'interface, jamais de repli console (pages affichees par un navigateur)."""
    statuses = catalog.available()
    offered = list(statuses) + ([PSEUDO_LANGUAGE_CODE] if INCLUDE_PSEUDO_LANGUAGE else [])
    choice = resolve_language(settings_store.get(PAGE_LANGUAGE_KEY, "") or "", offered, statuses)
    return _install_choice(choice, catalog, state)


def install_interface_language(
    *, settings_store: SettingsStore, catalog: LanguageCatalogPort, environ: Mapping[str, str],
    state: TranslationState = STATE, terminal_family: str | None = None,
) -> LanguageChoice:
    """`terminal_family` : famille detectee (omega-lib terminal/policies.py), uniquement pour
    l'interface - jamais pour les pages visiteurs, affichees par un navigateur."""
    global _console_fallback_from
    requested = environ.get(LANGUAGE_ENV_VAR) or settings_store.get(LANGUAGE_KEY, "") or ""
    statuses = catalog.available()
    offered = list(statuses) + ([PSEUDO_LANGUAGE_CODE] if INCLUDE_PSEUDO_LANGUAGE else [])
    choice = resolve_language(requested, offered, statuses)
    if terminal_family is not None:
        _console_fallback_from = None
        replacement = console_fallback_language(choice.language.code, terminal_family)
        if replacement is not None and choice.fell_back_from is None:
            _console_fallback_from = choice.language.code
            choice = resolve_language(replacement, offered, statuses)
    return _install_choice(choice, catalog, state)


def _install_choice(choice: LanguageChoice, catalog: LanguageCatalogPort, state: TranslationState) -> LanguageChoice:
    if choice.fell_back_from is None and choice.language.code != SOURCE_LANGUAGE_CODE:
        try:
            translations = catalog.load(choice.language.code)
        except LanguageCatalogError:
            choice = LanguageChoice(language_for(SOURCE_LANGUAGE_CODE), fell_back_from=choice.language.code)
        else:
            state.install(choice.language, translations)
            return choice
    state.install(choice.language, None, fell_back_from=choice.fell_back_from)
    return choice
