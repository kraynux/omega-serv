"""Sous-ecran Resistance et limites (plan interface §7) - les 10 champs
entiers de ServerConfig lies aux limites/delais anti-abus (spec §9.2)."""
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

_FIELDS: tuple[tuple[str, str], ...] = (
    ("max_connections", "Connexions simultanees max (max_connections)"),
    ("max_request_size", "Taille maximale de requete en octets (max_request_size)"),
    ("max_header_size", "Taille maximale des en-tetes en octets (max_header_size)"),
    ("max_request_line_size", "Taille maximale de la ligne de requete (max_request_line_size)"),
    ("read_timeout_seconds", "Delai de lecture en secondes (read_timeout_seconds)"),
    ("write_timeout_seconds", "Delai d'ecriture en secondes (write_timeout_seconds)"),
    ("keepalive_timeout_seconds", "Delai keep-alive en secondes (keepalive_timeout_seconds)"),
    ("max_keepalive_requests", "Requetes max par connexion keep-alive (max_keepalive_requests)"),
    ("listen_backlog", "File d'attente d'ecoute (listen_backlog)"),
    ("shutdown_grace_period_seconds", "Delai de grace a l'arret en secondes (shutdown_grace_period_seconds)"),
)


class LimitsScreen(OmegaScreen):
    def __init__(self, *, container: DependencyContainer) -> None:
        super().__init__()
        self._container = container

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(classes="omega-form-panel"):
            yield Static("RESISTANCE ET LIMITES", classes="omega-title")
            yield Static("", id="form-error", classes="omega-hint")
            for field_name, label in _FIELDS:
                yield Static(label, classes="omega-subtitle")
                yield Input(id=f"field-{field_name}")
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
        for field_name, _label in _FIELDS:
            self.query_one(f"#field-{field_name}", Input).value = str(getattr(server, field_name))

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

        values: dict[str, int] = {}
        for field_name, label in _FIELDS:
            text = self.query_one(f"#field-{field_name}", Input).value.strip()
            try:
                values[field_name] = int(text)
            except ValueError:
                error_widget.update(f"Valeur invalide pour {label} (nombre entier attendu) : {text!r}")
                return

        new_server = replace(
            load_result.config.server,
            max_connections=values["max_connections"],
            max_request_size=values["max_request_size"],
            max_header_size=values["max_header_size"],
            max_request_line_size=values["max_request_line_size"],
            read_timeout_seconds=values["read_timeout_seconds"],
            write_timeout_seconds=values["write_timeout_seconds"],
            keepalive_timeout_seconds=values["keepalive_timeout_seconds"],
            max_keepalive_requests=values["max_keepalive_requests"],
            listen_backlog=values["listen_backlog"],
            shutdown_grace_period_seconds=values["shutdown_grace_period_seconds"],
        )
        new_config = replace(load_result.config, server=new_server)

        errors = validate_config(new_config)
        if errors:
            error_widget.update("Erreur de validation :\n" + "\n".join(f"  - {e}" for e in errors))
            return

        self._container.configuration.save(self._container.config_file, new_config)
        error_widget.update("")
        if new_server.listen_backlog != load_result.config.server.listen_backlog:
            notify_restart_required(
                self, self._container,
                "Enregistre - mais listen_backlog necessite un REDEMARRAGE COMPLET pour prendre "
                "effet (jamais un simple rechargement, le socket d'ecoute n'est jamais retouche).",
            )
        else:
            notify_reload_required(self, self._container, "Limites enregistrees.")
