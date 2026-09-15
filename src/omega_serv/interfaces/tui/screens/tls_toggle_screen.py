# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Sous-ecran Activer/desactiver TLS (plan interface §7.3, `config
enable-tls`/`config disable-tls`)."""
from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Button, Footer, Header, Input, Static

from omega_serv.application.config.load_config import load_config
from omega_serv.interfaces.tui.screens._base import OmegaScreen
from omega_serv.interfaces.tui.screens.restart_prompt import notify_restart_required

if TYPE_CHECKING:
    from omega_serv.bootstrap.container import DependencyContainer

_VALID_MODES = ("direct", "behind_proxy")


class TlsToggleScreen(OmegaScreen):
    def __init__(self, *, container: DependencyContainer) -> None:
        super().__init__()
        self._container = container

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(classes="omega-form-panel"):
            yield Static("ACTIVER / DESACTIVER TLS", classes="omega-title")
            yield Static("", id="form-error", classes="omega-hint")
            yield Static("", id="status-text", classes="omega-hint")
            yield Static(f"Mode ({'/'.join(_VALID_MODES)})", classes="omega-subtitle")
            yield Input(id="mode-input")
            yield Static("Chemin du certificat (optionnel, garde la valeur actuelle si vide)", classes="omega-subtitle")
            yield Input(id="cert-input")
            yield Static("Chemin de la cle privee (optionnel)", classes="omega-subtitle")
            yield Input(id="key-input")
            with Horizontal(classes="omega-actions"):
                with Container(classes="omega-btn-frame"):
                    yield Button("Activer TLS", id="enable", variant="primary")
                with Container(classes="omega-btn-frame"):
                    yield Button("Desactiver TLS", id="disable", variant="error")
                with Container(classes="omega-btn-frame"):
                    yield Button("Retour", id="back")
        yield Footer()

    def on_mount(self) -> None:
        self._refresh_status()

    def _refresh_status(self) -> None:
        result = load_config(self._container.configuration, self._container.config_file)
        status_widget = self.query_one("#status-text", Static)
        if not result.success or result.config is None:
            status_widget.update("Erreur de configuration.")
            return
        tls = result.config.tls
        status_widget.update(f"Etat actuel : {'active' if tls.enabled else 'desactive'} (mode {tls.mode})")
        self.query_one("#mode-input", Input).value = tls.mode

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "back":
            self.dismiss()
            return
        if event.button.id == "enable":
            self._enable()
        elif event.button.id == "disable":
            self._disable()

    def _enable(self) -> None:
        error_widget = self.query_one("#form-error", Static)
        load_result = load_config(self._container.configuration, self._container.config_file)
        if not load_result.success or load_result.config is None:
            error_widget.update("Erreur de configuration : " + "; ".join(load_result.errors))
            return

        mode = self.query_one("#mode-input", Input).value.strip()
        if mode not in _VALID_MODES:
            error_widget.update(f"Mode invalide : {mode!r} (attendu : {'/'.join(_VALID_MODES)})")
            return

        cert = self.query_one("#cert-input", Input).value.strip()
        key = self.query_one("#key-input", Input).value.strip()
        new_tls = replace(
            load_result.config.tls,
            enabled=True,
            mode=mode,
            certificate_path=cert or load_result.config.tls.certificate_path,
            private_key_path=key or load_result.config.tls.private_key_path,
        )
        new_config = replace(load_result.config, tls=new_tls)
        self._container.configuration.save(self._container.config_file, new_config)
        error_widget.update("")
        # Retour utilisateur 2026-09-11 (audit reload/restart) : TLS
        # n'est jamais recharge a chaud, quel que soit le reglage
        # (contexte SSL construit une seule fois dans build_server,
        # jamais retouche par reload_scoped) - toujours un REDEMARRAGE
        # COMPLET, contrairement a la plupart des autres options.
        notify_restart_required(
            self, self._container,
            f"TLS active (mode {mode}) - necessite un REDEMARRAGE COMPLET pour prendre effet "
            "(jamais un simple rechargement).",
        )
        self._refresh_status()

    def _disable(self) -> None:
        load_result = load_config(self._container.configuration, self._container.config_file)
        if not load_result.success or load_result.config is None:
            self.query_one("#form-error", Static).update("Erreur de configuration : " + "; ".join(load_result.errors))
            return
        new_tls = replace(load_result.config.tls, enabled=False)
        new_config = replace(load_result.config, tls=new_tls)
        self._container.configuration.save(self._container.config_file, new_config)
        self.query_one("#form-error", Static).update("")
        notify_restart_required(
            self, self._container,
            "TLS desactive - necessite un REDEMARRAGE COMPLET pour prendre effet "
            "(jamais un simple rechargement).",
        )
        self._refresh_status()
