"""Installation de la langue AVANT tout autre import du programme
(OMEGA-SERV_PLAN-DETAILLE_I18N.md, lot 4).

La langue ne change jamais en cours de processus (changer = redemarrer l'interface). En
l'installant avant d'importer le conteneur, l'interface ou la CLI, toute phrase traduite au
chargement d'un module (menus, listes d'options, fiches du guide) est deja dans la bonne
langue - pas besoin de traduction "paresseuse". Ce module ne charge volontairement que le
strict minimum (reglages, catalogues, choix de la langue)."""
from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from omega_lib.i18n.models import LanguageChoice
from omega_lib.infrastructure.terminal.detector import SystemTerminalDetector

from omega_serv.application.terminal.select_language import (
    install_interface_language,
    install_page_language,
)
from omega_serv.bootstrap.paths import PROJECT_ROOT
from omega_serv.core.i18n import PAGE_STATE
from omega_serv.infrastructure.config.json_settings_store import JsonSettingsStore
from omega_serv.infrastructure.i18n.gettext_language_catalog import GettextLanguageCatalog


def is_server_process(argv: list[str]) -> bool:
    """`omega-serv serve` (systemd ou "Lancer maintenant") : D18b, ses messages vont dans
    journalctl et restent en francais - la langue n'est jamais installee. Premier argument
    positionnel, `--config X` / `--config=X` ignores."""
    tokens = iter(argv)
    for token in tokens:
        if token == "--config":
            next(tokens, None)
        elif not token.startswith("-"):
            return token == "serve"
    return False


EXPORT_CHILD_ENV_VAR = "OMEGA_SERV_EXPORT_CHILD"
"""Pose pour le processus qui genere un export dans une autre langue que l'interface (lot
« langue des exports ») : il ecrit un fichier, jamais dans le terminal - pas de repli console."""


def install_language_early(environ: Mapping[str, str], project_root: Path = PROJECT_ROOT) -> LanguageChoice:
    exporting = environ.get(EXPORT_CHILD_ENV_VAR) == "1"
    return install_interface_language(
        settings_store=JsonSettingsStore(project_root / "var" / "settings.json"),
        catalog=GettextLanguageCatalog(),
        environ=environ,
        terminal_family=None if exporting else SystemTerminalDetector().detect().family,
    )


def install_page_language_early(environ: Mapping[str, str], project_root: Path = PROJECT_ROOT) -> LanguageChoice:
    """Langue des pages servies aux visiteurs (D19 revue 2026-10-23) - installee dans TOUS les
    processus, y compris `serve` : reglage `page_language` (ecran Pages d'erreur), distinct de
    la langue de l'interface. `environ` est ignore (OMEGA_SERV_LANG ne vise que l'interface)."""
    del environ
    return install_page_language(
        settings_store=JsonSettingsStore(project_root / "var" / "settings.json"),
        catalog=GettextLanguageCatalog(),
        state=PAGE_STATE,
    )
