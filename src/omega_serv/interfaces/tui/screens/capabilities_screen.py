# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Ecran Registre des capacites (plan interface §5, menu 1) - scan
systeme complet, tableau colore par statut, export JSON/HTML. Le port
sonde et le socket FastCGI (si l'option est active) viennent de la
configuration chargee, jamais devines - `container.build_capability_scanner`
reconstruit un scanner a chaque rafraichissement (le registre est
toujours reconstruit entierement, jamais mis a jour capacite par
capacite, voir core/capability_registry.py). Export HTML via jinja2
(infrastructure/exporters/html_exporter.py, retour utilisateur
2026-09-09) - meme mecanisme et memes 5 themes que le reste de la
suite, choisi par `#export-theme-select` avant l'export."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from omega_lib.theme.policies import DEFAULT_EXPORT_THEME, EXPORT_PALETTES
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Button, DataTable, Footer, Header, Select, Static

from omega_serv.application.config.load_config import load_config
from omega_serv.core.capability_registry import CapabilityRegistry
from omega_serv.interfaces.tui.screens._base import OmegaScreen
from omega_serv.interfaces.tui.screens.capability_detail_screen import CapabilityDetailScreen
from omega_serv.interfaces.tui.widgets.capabilities_table import CapabilitiesTable

if TYPE_CHECKING:
    from omega_serv.bootstrap.container import DependencyContainer
    from omega_serv.domain.config.entities import OmegaServConfig


def _export_timestamp() -> str:
    # Meme format que domain/logs/rotation.py::generate_archive_name
    # (retour utilisateur 2026-09-09 : ces exports ecrasaient
    # silencieusement le precedent, faute d'horodatage dans le nom).
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")


class CapabilitiesScreen(OmegaScreen):
    def __init__(self, *, container: DependencyContainer) -> None:
        super().__init__()
        self._container = container
        self._registry = CapabilityRegistry()

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(classes="omega-panel"):
            yield Static("REGISTRE DES CAPACITES", classes="omega-title")
            yield Static("", id="scan-error", classes="omega-hint")
            yield CapabilitiesTable(id="capabilities-table")
            yield Static("Theme d'export HTML", classes="omega-subtitle")
            yield Select(
                [(name, name) for name in EXPORT_PALETTES], value=DEFAULT_EXPORT_THEME, id="export-theme-select",
            )
            with Horizontal(classes="omega-actions"):
                with Container(classes="omega-btn-frame"):
                    yield Button("Rafraichir", id="refresh", variant="primary")
                with Container(classes="omega-btn-frame"):
                    yield Button("Exporter JSON", id="export-json")
                with Container(classes="omega-btn-frame"):
                    yield Button("Exporter HTML", id="export-html")
                with Container(classes="omega-btn-frame"):
                    yield Button("Retour", id="back")
        yield Footer()

    def on_mount(self) -> None:
        self._scan()

    def _scan(self) -> None:
        error_widget = self.query_one("#scan-error", Static)
        load_result = load_config(self._container.configuration, self._container.config_file)
        if not load_result.success or load_result.config is None:
            error_widget.update("Erreur de configuration : " + "; ".join(load_result.errors))
            return
        config = load_result.config

        fastcgi_socket = None
        fastcgi_option = config.options.get("fastcgi")
        if fastcgi_option is not None and fastcgi_option.enabled:
            socket_relative = fastcgi_option.settings.get("socket_path", "var/run/php-fpm.sock")
            fastcgi_socket = self._container.project_root / socket_relative

        # Retour utilisateur (audit "gel d'ecran") : `scanner.scan()`
        # sonde reellement le port/socket configures (connexion reseau)
        # - tourne en synchrone sur la boucle asyncio, gele l'interface
        # le temps de chaque sonde. Meme patron que
        # backup_screen.py/audit_screen.py : deporte dans un thread de
        # travail.
        error_widget.update("Analyse en cours...")
        self.query_one("#refresh", Button).disabled = True
        self.run_worker(lambda: self._scan_in_thread(config, fastcgi_socket), thread=True, exclusive=True)

    def _scan_in_thread(self, config: OmegaServConfig, fastcgi_socket: Path | None) -> None:
        scanner = self._container.build_capability_scanner(config.server.port, fastcgi_socket)
        registry = CapabilityRegistry(scanner.scan())
        self.app.call_from_thread(self._finish_scan, registry)

    def _finish_scan(self, registry: CapabilityRegistry) -> None:
        self.query_one("#refresh", Button).disabled = False
        self._registry = registry
        self.query_one("#scan-error", Static).update("")
        self.query_one("#capabilities-table", CapabilitiesTable).set_capabilities(self._registry.list_all())

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id
        if button_id == "back":
            self.dismiss()
            return
        if button_id == "refresh":
            self._scan()
            return
        if button_id == "export-json":
            self._export_json()
            return
        if button_id == "export-html":
            self._export_html()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        capability_id = str(event.row_key.value)
        self.app.push_screen(CapabilityDetailScreen(container=self._container, registry=self._registry, capability_id=capability_id))

    def _exports_dir(self) -> Path:
        # Respecte la surcharge configuree dans l'ecran Reglages
        # (parametre "exports_dir_override", touche 'o') - meme mecanisme
        # que app.py::_deliver_screenshot_to_configured_dir pour les captures.
        override = self._container.settings_store.get("exports_dir_override", "")
        return Path(override) if override else self._container.default_exports_dir

    def _export_json(self) -> None:
        payload = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "capabilities": [c.to_dict() for c in self._registry.list_all()],
        }
        content = json.dumps(payload, indent=2, ensure_ascii=False)
        export_path = self._exports_dir() / f"capabilities-export.{_export_timestamp()}.json"
        self._write_export(export_path, content)

    def _export_html(self) -> None:
        theme_name = str(self.query_one("#export-theme-select", Select).value)
        content = self._container.export_capabilities_html(self._registry.list_all(), theme_name)
        if content is None:
            self.query_one("#scan-error", Static).update("Export HTML indisponible dans cet environnement.")
            return
        export_path = self._exports_dir() / f"capabilities-export.{_export_timestamp()}.html"
        self._write_export(export_path, content)

    def _write_export(self, export_path: Path, content: str) -> None:
        self._container.filesystem.make_directory(export_path.parent)
        self._container.filesystem.write_text(export_path, content)
        self.app.notify(f"Export ecrit : {export_path}")
