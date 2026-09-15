# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Sous-ecran Configuration de base (plan interface §7) - bind/port/
server_name/index_files, edition directe puis validation structurelle
(domain/config/validation.py, pure) avant ecriture, meme discipline que
partout ailleurs dans l'interface (jamais d'ecriture sans verification)."""
from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Button, Footer, Header, Input, Static

from omega_serv.application.config.load_config import load_config
from omega_serv.domain.config.validation import validate_config
from omega_serv.interfaces.tui.screens._base import OmegaScreen
from omega_serv.interfaces.tui.screens.restart_prompt import (
    notify_reload_required,
    notify_restart_required,
)

if TYPE_CHECKING:
    from omega_serv.bootstrap.container import DependencyContainer


class BaseConfigScreen(OmegaScreen):
    def __init__(self, *, container: DependencyContainer) -> None:
        super().__init__()
        self._container = container

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(classes="omega-form-panel"):
            yield Static("CONFIGURATION DE BASE", classes="omega-title")
            yield Static("", id="form-error", classes="omega-hint")
            yield Static("Adresse d'ecoute (server.bind)", classes="omega-subtitle")
            yield Input(id="bind-input")
            yield Static("Port (server.port)", classes="omega-subtitle")
            yield Input(id="port-input")
            yield Static("Nom du serveur (server.server_name)", classes="omega-subtitle")
            yield Input(id="server-name-input")
            yield Static("Fichiers d'index (separes par des virgules)", classes="omega-subtitle")
            yield Input(id="index-files-input")
            with Horizontal(classes="omega-actions"):
                with Container(classes="omega-btn-frame"):
                    yield Button("Enregistrer", id="save", variant="primary")
                with Container(classes="omega-btn-frame"):
                    yield Button("Retour", id="back")
        yield Footer()

    def on_mount(self) -> None:
        result = load_config(self._container.configuration, self._container.config_file)
        if not result.success:
            self.query_one("#form-error", Static).update(
                "Erreur de configuration : " + "; ".join(result.errors)
            )
            self.query_one("#save", Button).disabled = True
            return
        assert result.config is not None
        server = result.config.server
        self.query_one("#bind-input", Input).value = server.bind
        self.query_one("#port-input", Input).value = str(server.port)
        self.query_one("#server-name-input", Input).value = server.server_name
        self.query_one("#index-files-input", Input).value = ", ".join(server.index_files)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "back":
            self.dismiss()
            return
        if event.button.id == "save":
            self._save()

    def _save(self) -> None:
        error_widget = self.query_one("#form-error", Static)
        load_result = load_config(self._container.configuration, self._container.config_file)
        if not load_result.success:
            error_widget.update("Erreur de configuration : " + "; ".join(load_result.errors))
            return
        assert load_result.config is not None

        port_text = self.query_one("#port-input", Input).value.strip()
        try:
            port = int(port_text)
        except ValueError:
            error_widget.update(f"Port invalide (nombre attendu) : {port_text!r}")
            return

        index_files = tuple(
            item.strip() for item in self.query_one("#index-files-input", Input).value.split(",") if item.strip()
        )
        new_server = replace(
            load_result.config.server,
            bind=self.query_one("#bind-input", Input).value.strip(),
            port=port,
            server_name=self.query_one("#server-name-input", Input).value.strip(),
            index_files=index_files,
        )
        new_config = replace(load_result.config, server=new_server)

        errors = validate_config(new_config)
        if errors:
            error_widget.update("Erreur de validation :\n" + "\n".join(f"  - {e}" for e in errors))
            return

        self._container.configuration.save(self._container.config_file, new_config)
        error_widget.update("")
        # Retour utilisateur 2026-09-11 (audit reload/restart) :
        # bind/port ne se rechargent jamais a chaud - le socket
        # d'ecoute n'est jamais retouche par reload_scoped
        # (application/server/start_server.py::reload_server), seul un
        # restart complet (bouton "Redemarrer", pas "Recharger") prend
        # en compte un changement ici. Avertissement seulement si l'un
        # des deux a reellement change - jamais pour server_name/
        # index_files, qui restent a chaud.
        if new_server.bind != load_result.config.server.bind or new_server.port != load_result.config.server.port:
            notify_restart_required(
                self, self._container,
                "Enregistre - mais bind/port necessitent un REDEMARRAGE COMPLET pour prendre "
                "effet (jamais un simple rechargement, le socket d'ecoute n'est jamais retouche).",
            )
        else:
            # server_name/index_files restent a chaud (lus depuis
            # self._config a chaque requete, remplaces en bloc par
            # reload_scoped) - meme angle mort que les autres options
            # detaillees (guide d'aide, point 4) : un simple reload
            # reste necessaire, jamais applique tout seul.
            notify_reload_required(self, self._container, "Configuration de base enregistree.")
