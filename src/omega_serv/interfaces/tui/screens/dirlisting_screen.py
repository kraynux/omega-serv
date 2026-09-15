# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Sous-ecran Directory listing (plan interface §7, `option enable
dirlisting`) - deux sections sur le meme ecran (CRUD sur `zone_prefixes`
deja existant + reglages d'affichage, retour utilisateur guide d'aide
point 1 : CSS de base + header/readme) plutot qu'un sous-menu
intermediaire, pour ne pas casser le parcours "dirlisting -> directement
la table de zones" deja couvert par
tests/integration/test_tui_server_config.py::test_dirlisting_add_and_delete.
Champs booleens en "oui/non" texte, meme convention que
security_screen.py (pas de nouveau type de widget pour ce seul ecran)."""
from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from omega_lib.theme.policies import DEFAULT_EXPORT_THEME, EXPORT_PALETTES
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Button, DataTable, Footer, Header, Input, Select, Static

from omega_serv.application.config.load_config import load_config
from omega_serv.domain.config.option import Option
from omega_serv.domain.routing.dirlisting import DirlistingSettings
from omega_serv.interfaces.tui.screens._base import OmegaScreen
from omega_serv.interfaces.tui.screens.confirm import ConfirmScreen
from omega_serv.interfaces.tui.screens.dynamic_form_screen import DynamicFormScreen
from omega_serv.interfaces.tui.screens.restart_prompt import notify_reload_required

if TYPE_CHECKING:
    from omega_serv.bootstrap.container import DependencyContainer

_TRUE_VALUES = frozenset({"oui", "true", "1", "o", "y"})


def _bool_to_text(value: bool) -> str:
    return "oui" if value else "non"


def _text_to_bool(value: str) -> bool:
    return value.strip().lower() in _TRUE_VALUES


class DirlistingScreen(OmegaScreen):
    def __init__(self, *, container: DependencyContainer) -> None:
        super().__init__()
        self._container = container
        self._selected_index: int | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(classes="omega-panel"):
            yield Static("DIRECTORY LISTING", classes="omega-title")
            yield Static(
                "L'activation de l'option 'dirlisting' se fait dans le menu Options.",
                classes="omega-hint",
            )
            yield Static("", id="form-error", classes="omega-hint")

            yield Static("REGLAGES D'AFFICHAGE", classes="omega-subtitle")
            yield Static("Theme du CSS de base")
            yield Select(
                [(name, name) for name in EXPORT_PALETTES], value=DEFAULT_EXPORT_THEME,
                allow_blank=False, id="theme-select",
            )
            yield Static("CSS externe (URL optionnelle, charge en plus du CSS de base)")
            yield Input(id="external-css-input")
            yield Static("Afficher un fichier HEADER en haut du listing (oui/non)")
            yield Input(id="show-header-input")
            yield Static("Nom du fichier HEADER")
            yield Input(id="header-file-input")
            yield Static("Encoder (echapper) le contenu HEADER plutot que l'inserer tel quel (oui/non)")
            yield Input(id="encode-header-input")
            yield Static("Masquer ce fichier HEADER dans la liste (oui/non)")
            yield Input(id="hide-header-file-input")
            yield Static("Afficher un fichier README en bas du listing (oui/non)")
            yield Input(id="show-readme-input")
            yield Static("Nom du fichier README")
            yield Input(id="readme-file-input")
            yield Static("Encoder (echapper) le contenu README plutot que l'inserer tel quel (oui/non)")
            yield Input(id="encode-readme-input")
            yield Static("Masquer ce fichier README dans la liste (oui/non)")
            yield Input(id="hide-readme-file-input")
            with Horizontal(classes="omega-actions"), Container(classes="omega-btn-frame"):
                yield Button("Enregistrer les reglages", id="save-settings", variant="primary")

            yield Static("ZONES OU LE LISTING EST ACTIF", classes="omega-subtitle")
            yield DataTable(id="zones-table")
            with Horizontal(classes="omega-actions"):
                with Container(classes="omega-btn-frame"):
                    yield Button("Ajouter", id="add", variant="primary")
                with Container(classes="omega-btn-frame"):
                    yield Button("Supprimer", id="delete", variant="error", disabled=True)
                with Container(classes="omega-btn-frame"):
                    yield Button("Retour", id="back")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#zones-table", DataTable)
        table.cursor_type = "row"
        table.add_columns("Prefixe de zone")
        self._refresh_table()
        self._load_settings_form()

    def _option(self) -> Option | None:
        result = load_config(self._container.configuration, self._container.config_file)
        if not result.success or result.config is None:
            return None
        return result.config.options.get("dirlisting")

    def _settings(self) -> DirlistingSettings:
        option = self._option()
        if option is None:
            return DirlistingSettings()
        return DirlistingSettings.from_dict(option.settings)

    def _load_settings_form(self) -> None:
        settings = self._settings()
        self.query_one("#theme-select", Select).value = settings.theme
        self.query_one("#external-css-input", Input).value = settings.external_css
        self.query_one("#show-header-input", Input).value = _bool_to_text(settings.show_header)
        self.query_one("#header-file-input", Input).value = settings.header_file
        self.query_one("#encode-header-input", Input).value = _bool_to_text(settings.encode_header)
        self.query_one("#hide-header-file-input", Input).value = _bool_to_text(settings.hide_header_file)
        self.query_one("#show-readme-input", Input).value = _bool_to_text(settings.show_readme)
        self.query_one("#readme-file-input", Input).value = settings.readme_file
        self.query_one("#encode-readme-input", Input).value = _bool_to_text(settings.encode_readme)
        self.query_one("#hide-readme-file-input", Input).value = _bool_to_text(settings.hide_readme_file)

    def _prefixes(self) -> list[str]:
        option = self._option()
        if option is None:
            return []
        return list(option.settings.get("zone_prefixes", []))

    def _refresh_table(self) -> None:
        table = self.query_one("#zones-table", DataTable)
        table.clear()
        for index, prefix in enumerate(self._prefixes()):
            table.add_row(prefix, key=str(index))
        self._selected_index = None
        self.query_one("#delete", Button).disabled = True

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        self._selected_index = int(str(event.row_key.value))
        self.query_one("#delete", Button).disabled = False

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "back":
            self.dismiss()
            return
        if event.button.id == "save-settings":
            self._save_settings()
            return
        if event.button.id == "add":
            self.app.push_screen(
                DynamicFormScreen(title="AJOUTER UNE ZONE", fields=[("prefix", "Prefixe de zone (ex: /files/)", "")]),
                self._add_prefix,
            )
            return
        if event.button.id == "delete" and self._selected_index is not None:
            self.app.push_screen(
                ConfirmScreen(title="SUPPRIMER LA ZONE", message="Confirmer la suppression de cette zone ?"),
                self._delete_prefix,
            )

    def _add_prefix(self, values: dict[str, str] | None) -> None:
        if values is None:
            return
        prefix = values["prefix"].strip()
        if not prefix.startswith("/"):
            self.query_one("#form-error", Static).update(f"Le prefixe doit commencer par '/' : {prefix!r}")
            return
        prefixes = self._prefixes()
        prefixes.append(prefix)
        self._save_settings_dict({"zone_prefixes": prefixes})

    def _delete_prefix(self, confirmed: bool | None) -> None:
        if not confirmed or self._selected_index is None:
            return
        prefixes = self._prefixes()
        del prefixes[self._selected_index]
        self._save_settings_dict({"zone_prefixes": prefixes})

    def _save_settings(self) -> None:
        theme = self.query_one("#theme-select", Select).value
        if theme not in EXPORT_PALETTES:
            self.query_one("#form-error", Static).update(f"Theme inconnu : {theme!r}")
            return
        header_file = self.query_one("#header-file-input", Input).value.strip()
        readme_file = self.query_one("#readme-file-input", Input).value.strip()
        if not header_file or not readme_file:
            self.query_one("#form-error", Static).update("Les noms de fichiers HEADER/README ne peuvent pas etre vides.")
            return

        self._save_settings_dict({
            "theme": theme,
            "external_css": self.query_one("#external-css-input", Input).value.strip(),
            "show_header": _text_to_bool(self.query_one("#show-header-input", Input).value),
            "header_file": header_file,
            "encode_header": _text_to_bool(self.query_one("#encode-header-input", Input).value),
            "hide_header_file": _text_to_bool(self.query_one("#hide-header-file-input", Input).value),
            "show_readme": _text_to_bool(self.query_one("#show-readme-input", Input).value),
            "readme_file": readme_file,
            "encode_readme": _text_to_bool(self.query_one("#encode-readme-input", Input).value),
            "hide_readme_file": _text_to_bool(self.query_one("#hide-readme-file-input", Input).value),
        }, "Reglages d'affichage du listing enregistres.")

    def _save_settings_dict(self, updates: dict[str, object], success_message: str = "Zones mises a jour.") -> None:
        load_result = load_config(self._container.configuration, self._container.config_file)
        if not load_result.success or load_result.config is None:
            self.query_one("#form-error", Static).update("Erreur de configuration - impossible d'enregistrer.")
            return
        existing = load_result.config.options.get("dirlisting")
        enabled = existing.enabled if existing is not None else False
        new_settings = dict(existing.settings) if existing is not None else {}
        new_settings.update(updates)
        new_options = dict(load_result.config.options)
        new_options["dirlisting"] = Option(name="dirlisting", enabled=enabled, settings=new_settings)
        new_config = replace(load_result.config, options=new_options)
        self._container.configuration.save(self._container.config_file, new_config)
        self.query_one("#form-error", Static).update("")
        self._refresh_table()
        # Retour utilisateur (guide d'aide, point 4) : un changement de
        # zone/reglage ecrit sur disque reste sans effet tant que le
        # processus deja lance n'a pas rechu la config (reload SIGHUP
        # suffit deja, verifie reellement - jamais besoin d'un restart
        # complet pour cette option).
        notify_reload_required(self, self._container, success_message)
