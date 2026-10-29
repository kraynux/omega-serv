"""Ecran Reglages de l'application (pas la configuration du serveur,
menu 3 - preferences d'interface uniquement) : theme, profil de rendu,
chemins d'export/captures d'ecran, purge. Adapte du patron
omega-check/interfaces/tui/screens/settings_screen.py - pas de concept
de cible epinglee ni d'historique de scan cote SERV (rien a porter la).
Accessible via le raccourci clavier 'o' (footer), la palette de
commandes, ET desormais le bouton "OPTIONS" du menu principal (retour
utilisateur, passage a 2 colonnes - initialement absent du menu "deja
charge", plan interface §12, redevenu possible une fois la place liberee).
Homonyme a ne pas confondre : `options_screen.py::OptionsScreen` (liste
des options superposables du serveur), un ecran totalement different,
accessible uniquement depuis Configuration detaillee."""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, cast

from omega_lib.i18n.models import LanguageStatus
from omega_lib.i18n.policies import PSEUDO_LANGUAGE_CODE
from omega_lib.terminal.models import RenderProfile
from omega_lib.theme.policies import TUI_THEMES
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Button, Footer, Header, Input, Select, Static

from omega_serv.application.terminal.clear_directory import ClearResult, clear_directory
from omega_serv.application.terminal.exceptions import (
    UnknownLanguageError,
    UnknownThemeError,
    UnsafeDirectoryError,
)
from omega_serv.application.terminal.select_language import (
    EXPORT_LANGUAGE_KEY,
    available_languages,
    select_export_language,
    select_language,
)
from omega_serv.application.terminal.select_render_profile import select_render_profile
from omega_serv.application.terminal.select_theme import select_theme
from omega_serv.core.i18n import STATE, _
from omega_serv.interfaces.tui.pending_interface_restart import PendingInterfaceRestart
from omega_serv.interfaces.tui.screens._base import OmegaScreen
from omega_serv.interfaces.tui.screens.confirm import ConfirmScreen
from omega_serv.interfaces.tui.screens.language_changed_splash_screen import LANGUAGE_LABEL

if TYPE_CHECKING:
    from omega_serv.bootstrap.container import DependencyContainer
    from omega_serv.interfaces.tui.app import OmegaServApp
    from omega_serv.ports.language_catalog_port import LanguageCatalogPort

_AUTO = "auto"
_EXPORT_LIKE_INTERFACE = "interface"
_EXPORTS_DIR_KEY = "exports_dir_override"
_SCREENSHOTS_DIR_KEY = "screenshots_dir_override"


def language_options(catalog: LanguageCatalogPort) -> list[tuple[str, str]]:
    """Libelles du selecteur de langue (chaque langue dans sa langue, mention 'en test') -
    partages avec l'ecran Pages d'erreur (langue des pages visiteurs)."""
    options: list[tuple[str, str]] = []
    for language in available_languages(catalog):
        label = language.native_name
        if language.status is LanguageStatus.TESTING and language.code != PSEUDO_LANGUAGE_CODE:
            label = _("{label} ({value})").format(label=label, value=_('en test'))
        options.append((label, language.code))
    return options


class SettingsScreen(OmegaScreen):
    def __init__(self, *, container: DependencyContainer) -> None:
        super().__init__()
        self._container = container

    def compose(self) -> ComposeResult:
        store = self._container.settings_store
        yield Header()
        with Vertical(classes="omega-form-panel"):
            yield Static(_("RÉGLAGES"), classes="omega-title")

            yield Static(_("Thème"), classes="omega-subtitle")
            yield Select([(name, name) for name in TUI_THEMES], value=self.app.theme, id="theme-select")


            yield Static(_("Profil de rendu (redémarrage requis)"), classes="omega-subtitle")
            current_override = store.get("render_profile_override", "")
            yield Select(
                [(_("Automatique"), _AUTO)] + [(p.value, p.value) for p in RenderProfile],
                value=current_override or _AUTO,
                id="render-profile-select",
            )

            # Sous le profil de rendu (retour utilisateur 2026-10-21) : theme et rendu vont
            # ensemble (terminal), la langue vient apres. Libelle bilingue JAMAIS traduit
            # (plan i18n §5.3) : retrouvable meme dans une interface qu'on ne sait pas lire.
            yield Static(LANGUAGE_LABEL, classes="omega-subtitle")
            yield Select(self._language_options(), value=STATE.language.code, allow_blank=False, id="language-select")

            yield Static(_("Export"), classes="omega-subtitle")
            yield Input(
                value=store.get(_EXPORTS_DIR_KEY, str(self._container.default_exports_dir)) or "",
                id="exports-dir-input",
            )
            # Langue des exports HTML et du rapport d'incident (retour utilisateur 2026-10-22) :
            # un rapport se diffuse, sa langue n'est pas forcement celle de l'interface.
            yield Static(_("Langue des exports"), classes="omega-subtitle")
            yield Select(
                [(_("Comme l'interface"), _EXPORT_LIKE_INTERFACE)] + self._language_options(),
                value=store.get(EXPORT_LANGUAGE_KEY, "") or _EXPORT_LIKE_INTERFACE,
                allow_blank=False,
                id="export-language-select",
            )

            yield Static(_("Captures d'écran"), classes="omega-subtitle")
            yield Input(
                value=store.get(_SCREENSHOTS_DIR_KEY, str(self._container.default_screenshots_dir)) or "",
                id="screenshots-dir-input",
            )

            yield Static(_("Purge"), classes="omega-subtitle")
            with Horizontal(classes="omega-actions"):
                with Container(classes="omega-btn-frame"):
                    yield Button(_("Supprimer les exports"), id="clear-exports", variant="error")
                with Container(classes="omega-btn-frame"):
                    yield Button(_("Supprimer les screenshots"), id="clear-screenshots", variant="error")

            with Horizontal(classes="omega-actions"), Container(classes="omega-btn-frame"):
                yield Button(_("Retour"), id="back")
        yield Footer()

    def _language_options(self) -> list[tuple[str, str]]:
        return language_options(self._container.language_catalog)

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id == "language-select":
            if str(event.value) == STATE.language.code:
                return
            self._confirm_language(str(event.value))
        elif event.select.id == "theme-select":
            if str(event.value) == self.app.theme:
                return
            self._apply_theme(str(event.value))
        elif event.select.id == "export-language-select":
            self._apply_export_language(str(event.value))
        elif event.select.id == "render-profile-select":
            current_override = self._container.settings_store.get("render_profile_override", "") or _AUTO
            if str(event.value) == current_override:
                return
            self._apply_render_profile(str(event.value))

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "exports-dir-input":
            self._container.settings_store.set(_EXPORTS_DIR_KEY, event.value)
        elif event.input.id == "screenshots-dir-input":
            self._container.settings_store.set(_SCREENSHOTS_DIR_KEY, event.value)

    def _apply_theme(self, theme_name: str) -> None:
        try:
            select_theme(settings_store=self._container.settings_store, theme_name=theme_name)
        except UnknownThemeError as exc:
            self.app.notify(str(exc), severity="error")
            return
        self.app.theme = theme_name

    def _apply_export_language(self, value: str) -> None:
        code = "" if value == _EXPORT_LIKE_INTERFACE else value
        if code == (self._container.settings_store.get(EXPORT_LANGUAGE_KEY, "") or ""):
            return
        try:
            select_export_language(settings_store=self._container.settings_store,
                                   catalog=self._container.language_catalog, language_code=code)
        except UnknownLanguageError as exc:
            self.app.notify(str(exc), severity="error")

    def _confirm_language(self, code: str) -> None:
        names = {language.code: language.native_name for language in available_languages(self._container.language_catalog)}
        self.app.push_screen(
            ConfirmScreen(
                title=_("REDÉMARRER L'INTERFACE ?"),
                message=_(
                    "La langue « {name} » sera appliquée après le redémarrage de l'interface. "
                    "Le serveur (service) n'est pas concerne et continue de tourner."
                ).format(name=names.get(code, code)),
            ),
            lambda confirmed: self._restart_for_language(code, confirmed),
        )

    def _restore_language_select(self) -> None:
        self.query_one("#language-select", Select).value = STATE.language.code

    def _restart_for_language(self, code: str, confirmed: bool | None) -> None:
        if not confirmed:
            self._restore_language_select()
            return
        try:
            select_language(settings_store=self._container.settings_store,
                            catalog=self._container.language_catalog, language_code=code)
        except (UnknownLanguageError, OSError) as exc:
            self.app.notify(str(exc), title=LANGUAGE_LABEL, severity="error")
            self._restore_language_select()
            return
        cast("OmegaServApp", self.app).pending_restart = PendingInterfaceRestart(language_code=code)
        self.app.exit()

    def _apply_render_profile(self, value: str) -> None:
        profile = None if value == _AUTO else RenderProfile(value)
        select_render_profile(settings_store=self._container.settings_store, render_profile=profile)
        self.app.notify(_("Appliqué au prochain démarrage."), title=_("Profil de rendu"))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "back":
            self.dismiss()
        elif event.button.id == "clear-exports":
            self._confirm_clear(_EXPORTS_DIR_KEY, self._container.default_exports_dir, _("SUPPRIMER LES EXPORTS ?"))
        elif event.button.id == "clear-screenshots":
            self._confirm_clear(_SCREENSHOTS_DIR_KEY, self._container.default_screenshots_dir,
                                _("SUPPRIMER LES SCREENSHOTS ?"))

    def _configured_dir(self, key: str, default: Path) -> Path:
        """Dossier reellement utilise (meme regle que les ecrans d'export et la capture d'ecran :
        le champ de Reglages s'il est rempli, sinon le dossier par defaut). Correctif
        2026-10-27 : la purge videait toujours le dossier par defaut."""
        override = (self._container.settings_store.get(key, "") or "").strip()
        return Path(override).expanduser() if override else default

    def _confirm_clear(self, key: str, default: Path, title: str) -> None:
        directory = self._configured_dir(key, default)
        self.app.push_screen(
            ConfirmScreen(
                title=title,
                message=_("Tout le contenu de ce dossier sera définitivement supprimé :\n{directory}").format(
                    directory=directory),
            ),
            lambda confirmed: self._clear_if_confirmed(directory, confirmed),
        )

    def _clear_if_confirmed(self, directory: Path, confirmed: bool | None) -> None:
        if not confirmed:
            return
        self.app.notify(_("Suppression en cours..."), timeout=3)
        # Dans un thread : un gros dossier ne fige jamais l'interface pendant la suppression.
        self.run_worker(lambda: self._clear_in_thread(directory), thread=True, exclusive=True)

    def _clear_in_thread(self, directory: Path) -> None:
        try:
            result = clear_directory(directory, self._container.project_root)
        except (UnsafeDirectoryError, OSError) as exc:
            self.app.call_from_thread(self.app.notify, str(exc), severity="error", timeout=10)
            return
        self.app.call_from_thread(self._on_cleared, result)

    def _on_cleared(self, result: ClearResult) -> None:
        if not result.failed:
            self.app.notify(_("{removed} élément(s) supprimé(s) : {directory}").format(
                removed=result.removed, directory=result.directory))
            return
        shown = ", ".join(result.failed[:3]) + (" ..." if len(result.failed) > 3 else "")
        self.app.notify(
            _("{removed} élément(s) supprimé(s), {failed} impossible(s) à supprimer : {names}").format(
                removed=result.removed, failed=len(result.failed), names=shown),
            severity="warning", timeout=15,
        )
