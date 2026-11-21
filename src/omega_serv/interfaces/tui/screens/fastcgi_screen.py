"""Sous-ecran FastCGI/PHP-FPM (plan interface §7). Projets 3.0.0 §8.1 (decision de l'auteur du 2026-11-15) : une
LISTE de zones, chacune avec son prefixe, sa racine de scripts, sa socket PHP-FPM, ses delais, ses extensions, ses
fichiers d'index et sa liste blanche, et son propre interrupteur (Activer / Desactiver) pour la maintenance de ses
fichiers sans couper les autres zones. L'option `fastcgi` elle-meme (interrupteur general) reste dans le menu
Options. Validation structurelle par le domaine, avertissement « hors webroot » des la saisie (la porte bloquante
reelle reste verifiee par Configuration detaillee -> Verifier la configuration). Une ancienne configuration (un seul
enregistrement a plat) s'affiche comme une zone et passe au nouveau format au premier enregistrement."""
from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Button, DataTable, Footer, Header, Static

from omega_serv.application.config.load_config import load_config
from omega_serv.core.i18n import _
from omega_serv.domain.config.option import Option
from omega_serv.domain.routing.fastcgi_zone import (
    FastCgiConfig,
    fastcgi_settings_with_zones,
    parse_fastcgi_zones,
    validate_fastcgi_config_structure,
)
from omega_serv.interfaces.tui.screens._base import OmegaScreen
from omega_serv.interfaces.tui.screens._duplicates import duplicate_error
from omega_serv.interfaces.tui.screens._zone_overlap_notice import notify_zone_prefix_overlaps
from omega_serv.interfaces.tui.screens.confirm import ConfirmScreen
from omega_serv.interfaces.tui.screens.dynamic_form_screen import DynamicFormScreen
from omega_serv.interfaces.tui.screens.restart_prompt import notify_reload_required
from omega_serv.interfaces.tui.yes_no import to_text

if TYPE_CHECKING:
    from omega_serv.bootstrap.container import DependencyContainer
    from omega_serv.domain.config.entities import OmegaServConfig

_FIELDS: tuple[tuple[str, str], ...] = (
    ("url_prefix", _("Préfixe URL (url_prefix, ex: /app/)")),
    ("script_root", _("Racine d'exécution (script_root, relatif au projet)")),
    ("socket_path", _("Socket PHP-FPM (socket_path)")),
    ("connect_timeout_seconds", _("Délai de connexion en secondes")),
    ("read_timeout_seconds", _("Délai de lecture en secondes")),
    ("max_request_size", _("Taille maximale de requête en octets (max_request_size, vide = celle de l'écran Limites)")),
    ("allowed_extensions", _("Extensions autorisées (séparées par des virgules)")),
    ("index_files", _("Fichiers d'index (séparés par des virgules)")),
    (
        "allowed_scripts",
        (
            _("Liste blanche de scripts (chemins relatifs à script_root, séparés par des "
            "virgules, ex: index.php, api/router.php - vide = tout .php sous script_root reste exécutable)")
        ),
    ),
)


def _field_values(zone: FastCgiConfig) -> dict[str, str]:
    return {
        "url_prefix": zone.url_prefix, "script_root": zone.script_root, "socket_path": zone.socket_path,
        "connect_timeout_seconds": str(zone.connect_timeout_seconds),
        "read_timeout_seconds": str(zone.read_timeout_seconds),
        "max_request_size": "" if zone.max_request_size is None else str(zone.max_request_size),
        "allowed_extensions": ", ".join(zone.allowed_extensions), "index_files": ", ".join(zone.index_files),
        "allowed_scripts": ", ".join(zone.allowed_scripts),
    }


def _form_fields(zone: FastCgiConfig) -> list[tuple[str, str, str]]:
    values = _field_values(zone)
    return [(field, label, values[field]) for field, label in _FIELDS]


def _split(value: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in value.split(",") if item.strip())


class FastCgiScreen(OmegaScreen):
    def __init__(self, *, container: DependencyContainer) -> None:
        super().__init__()
        self._container = container
        self._selected_index: int | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(classes="omega-panel"):
            yield Static(_("FASTCGI / PHP-FPM"), classes="omega-title")
            yield Static(
                _("L'activation de l'option 'fastcgi' se fait dans le menu Options. Chaque zone a son propre "
                  "interrupteur : une zone désactivée répond 503 (maintenance), les autres continuent. Des "
                  "réglages PHP différents par zone passent par un pool PHP-FPM par zone (voir l'aide F1)."),
                classes="omega-hint",
            )
            yield Static("", id="form-error", classes="omega-hint")
            yield DataTable(id="fastcgi-table")
        # Barre d'actions hors de la zone qui defile, toujours visible (modele des autres listes de zones).
        with Horizontal(classes="omega-actions omega-riposte-actions"):
            with Container(classes="omega-btn-frame"):
                yield Button(_("Ajouter"), id="add", variant="primary")
            with Container(classes="omega-btn-frame"):
                yield Button(_("Modifier"), id="edit", disabled=True)
            with Container(classes="omega-btn-frame"):
                yield Button(_("Désactiver"), id="toggle", disabled=True)
            with Container(classes="omega-btn-frame"):
                yield Button(_("Supprimer"), id="delete", variant="error", disabled=True)
            with Container(classes="omega-btn-frame"):
                yield Button(_("Retour"), id="back")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#fastcgi-table", DataTable)
        table.cursor_type = "row"
        table.add_columns(_("Préfixe URL"), _("Racine des scripts"), _("Socket PHP-FPM"), _("Active"))
        if self._config() is None:
            self.query_one("#form-error", Static).update(_("Erreur de configuration."))
        self._refresh_table()

    def _config(self) -> OmegaServConfig | None:
        result = load_config(self._container.configuration, self._container.config_file)
        return result.config if result.success else None

    def _zones(self) -> list[FastCgiConfig]:
        config = self._config()
        option = None if config is None else config.options.get("fastcgi")
        return [] if option is None else list(parse_fastcgi_zones(option.settings))

    def _refresh_table(self) -> None:
        table = self.query_one("#fastcgi-table", DataTable)
        table.clear()
        for index, zone in enumerate(self._zones()):
            table.add_row(zone.url_prefix, zone.script_root, zone.socket_path, to_text(zone.enabled), key=str(index))
        self._selected_index = None
        for button_id in ("#edit", "#toggle", "#delete"):
            self.query_one(button_id, Button).disabled = True
        self.query_one("#toggle", Button).label = _("Désactiver")

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        self._selected_index = int(str(event.row_key.value))
        zones = self._zones()
        if self._selected_index >= len(zones):
            return
        for button_id in ("#edit", "#toggle", "#delete"):
            self.query_one(button_id, Button).disabled = False
        self.query_one("#toggle", Button).label = (
            _("Désactiver") if zones[self._selected_index].enabled else _("Activer"))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "back":
            self.dismiss()
            return
        if event.button.id == "add":
            self.push_form(DynamicFormScreen(
                title=_("AJOUTER UNE ZONE FASTCGI"),
                fields=_form_fields(FastCgiConfig()),
            ), self._add_zone)
            return
        if self._selected_index is None:
            return
        zones = self._zones()
        if self._selected_index >= len(zones):
            return
        zone = zones[self._selected_index]
        if event.button.id == "edit":
            self.push_form(DynamicFormScreen(
                title=_("MODIFIER LA ZONE FASTCGI"),
                fields=_form_fields(zone),
            ), self._edit_zone)
            return
        if event.button.id == "toggle":
            zones[self._selected_index] = replace(zone, enabled=not zone.enabled)
            self._save_zones(zones, (_("Zone FastCGI {prefix} activée.") if not zone.enabled
                                     else _("Zone FastCGI {prefix} désactivée (503 jusqu'à sa réactivation)."))
                             .format(prefix=zone.url_prefix))
            return
        if event.button.id == "delete":
            self.app.push_screen(
                ConfirmScreen(title=_("SUPPRIMER LA ZONE FASTCGI"),
                              message=_("Confirmer la suppression de la zone {prefix} ?").format(prefix=zone.url_prefix)),
                self._delete_zone,
            )

    def _zone_from_values(self, values: dict[str, str], enabled: bool) -> FastCgiConfig | None:
        try:
            connect_timeout = float(values["connect_timeout_seconds"])
            read_timeout = float(values["read_timeout_seconds"])
        except ValueError:
            self.report_form_error(_("Délais invalides (nombre attendu)."))
            return None
        size_text = values.get("max_request_size", "").strip()
        if size_text and not (size_text.isascii() and size_text.isdigit()):
            self.report_form_error(_("Taille maximale de requête invalide (nombre entier d'octets, ou vide)."))
            return None
        zone = FastCgiConfig(
            url_prefix=values["url_prefix"], script_root=values["script_root"], socket_path=values["socket_path"],
            connect_timeout_seconds=connect_timeout, read_timeout_seconds=read_timeout,
            allowed_extensions=_split(values["allowed_extensions"]), index_files=_split(values["index_files"]),
            allowed_scripts=_split(values["allowed_scripts"]), enabled=enabled,
            max_request_size=int(size_text) if size_text else None,
        )
        errors = validate_fastcgi_config_structure(zone)
        config = self._config()
        if zone.script_root and config is not None:
            webroot = (self._container.project_root / config.paths.webroot).resolve()
            script_root = (self._container.project_root / zone.script_root).resolve()
            if script_root == webroot or webroot in script_root.parents:
                errors.append(
                    _("script_root ({script_root}) est à l'intérieur de webroot ({webroot}) - interdit structurellement").format(script_root=script_root, webroot=webroot)
                )
        if errors:
            self.report_form_error(_("Erreur :\n") + "\n".join(f"  - {e}" for e in errors))
            return None
        return zone

    def _add_zone(self, values: dict[str, str] | None) -> None:
        if values is None:
            return
        zone = self._zone_from_values(values, enabled=True)
        if zone is None:
            return
        zones = self._zones()
        duplicate = duplicate_error(zones, zone, lambda z: z.url_prefix.rstrip("/") or "/",
                                    _("le préfixe {value!r}").format(value=zone.url_prefix))
        if duplicate is not None:
            self.report_form_error(duplicate)
            return
        zones.append(zone)
        self._save_zones(zones, _("Zone FastCGI {prefix} ajoutée.").format(prefix=zone.url_prefix))

    def _edit_zone(self, values: dict[str, str] | None) -> None:
        if values is None or self._selected_index is None:
            return
        zones = self._zones()
        if self._selected_index >= len(zones):
            return
        zone = self._zone_from_values(values, enabled=zones[self._selected_index].enabled)
        if zone is None:
            return
        duplicate = duplicate_error(zones, zone, lambda z: z.url_prefix.rstrip("/") or "/",
                                    _("le préfixe {value!r}").format(value=zone.url_prefix), self._selected_index)
        if duplicate is not None:
            self.report_form_error(duplicate)
            return
        zones[self._selected_index] = zone
        self._save_zones(zones, _("Zone FastCGI {prefix} enregistrée.").format(prefix=zone.url_prefix))

    def _delete_zone(self, confirmed: bool | None) -> None:
        if not confirmed or self._selected_index is None:
            return
        zones = self._zones()
        if self._selected_index >= len(zones):
            return
        removed = zones.pop(self._selected_index)
        self._save_zones(zones, _("Zone FastCGI {prefix} supprimée.").format(prefix=removed.url_prefix))

    def _save_zones(self, zones: list[FastCgiConfig], message: str) -> None:
        config = self._config()
        if config is None:
            self.report_form_error(_("Erreur de configuration - impossible d'enregistrer."))
            return
        existing = config.options.get("fastcgi")
        enabled = existing.enabled if existing is not None else False
        settings = fastcgi_settings_with_zones(dict(existing.settings) if existing is not None else {}, zones)
        new_options = dict(config.options)
        new_options["fastcgi"] = Option(name="fastcgi", enabled=enabled, settings=settings)
        self._container.configuration.save(self._container.config_file, replace(config, options=new_options))
        self.query_one("#form-error", Static).update("")
        self._refresh_table()
        notify_zone_prefix_overlaps(self, self._container, "fastcgi")
        notify_reload_required(self, self._container, message)
