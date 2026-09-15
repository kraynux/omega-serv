# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Sous-ecran Securite generique (plan interface §7) - SecurityConfig
(methodes autorisees, CSP, en-tetes, HSTS). Champs booleens en "oui/non"
texte (meme convention simple que le reste de ce menu, pas de nouveau
type de widget pour un seul sous-ecran)."""
from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Button, Footer, Header, Input, Static

from omega_serv.application.config.load_config import load_config
from omega_serv.domain.config.validation import validate_config
from omega_serv.interfaces.tui.screens._base import OmegaScreen
from omega_serv.interfaces.tui.screens.restart_prompt import notify_reload_required

if TYPE_CHECKING:
    from omega_serv.bootstrap.container import DependencyContainer

_TRUE_VALUES = frozenset({"oui", "true", "1", "o", "y"})


def _bool_to_text(value: bool) -> str:
    return "oui" if value else "non"


def _text_to_bool(value: str) -> bool:
    return value.strip().lower() in _TRUE_VALUES


class SecurityScreen(OmegaScreen):
    def __init__(self, *, container: DependencyContainer) -> None:
        super().__init__()
        self._container = container

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(classes="omega-form-panel"):
            yield Static("SECURITE GENERIQUE", classes="omega-title")
            yield Static("", id="form-error", classes="omega-hint")
            yield Static("Methodes autorisees (separees par des virgules)", classes="omega-subtitle")
            yield Input(id="allowed-methods-input")
            yield Static("Refuser les fichiers caches (oui/non)", classes="omega-subtitle")
            yield Input(id="deny-hidden-files-input")
            yield Static("Mode CSP (enforce/report-only)", classes="omega-subtitle")
            yield Input(id="csp-mode-input")
            yield Static("En-tetes de securite actifs (oui/non)", classes="omega-subtitle")
            yield Input(id="security-headers-input")
            yield Static("HSTS actif (oui/non)", classes="omega-subtitle")
            yield Input(id="hsts-enabled-input")
            yield Static("HSTS max-age en secondes", classes="omega-subtitle")
            yield Input(id="hsts-max-age-input")
            yield Static("HSTS includeSubDomains (oui/non)", classes="omega-subtitle")
            yield Input(id="hsts-subdomains-input")
            yield Static("HSTS preload (oui/non)", classes="omega-subtitle")
            yield Input(id="hsts-preload-input")
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
        security = result.config.security
        self.query_one("#allowed-methods-input", Input).value = ", ".join(security.allowed_methods)
        self.query_one("#deny-hidden-files-input", Input).value = _bool_to_text(security.deny_hidden_files)
        self.query_one("#csp-mode-input", Input).value = security.csp_mode
        self.query_one("#security-headers-input", Input).value = _bool_to_text(security.security_headers_enabled)
        self.query_one("#hsts-enabled-input", Input).value = _bool_to_text(security.hsts_enabled)
        self.query_one("#hsts-max-age-input", Input).value = str(security.hsts_max_age)
        self.query_one("#hsts-subdomains-input", Input).value = _bool_to_text(security.hsts_include_subdomains)
        self.query_one("#hsts-preload-input", Input).value = _bool_to_text(security.hsts_preload)

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

        max_age_text = self.query_one("#hsts-max-age-input", Input).value.strip()
        try:
            hsts_max_age = int(max_age_text)
        except ValueError:
            error_widget.update(f"HSTS max-age invalide (nombre attendu) : {max_age_text!r}")
            return

        allowed_methods = tuple(
            item.strip().upper() for item in self.query_one("#allowed-methods-input", Input).value.split(",") if item.strip()
        )
        new_security = replace(
            load_result.config.security,
            allowed_methods=allowed_methods,
            deny_hidden_files=_text_to_bool(self.query_one("#deny-hidden-files-input", Input).value),
            csp_mode=self.query_one("#csp-mode-input", Input).value.strip(),
            security_headers_enabled=_text_to_bool(self.query_one("#security-headers-input", Input).value),
            hsts_enabled=_text_to_bool(self.query_one("#hsts-enabled-input", Input).value),
            hsts_max_age=hsts_max_age,
            hsts_include_subdomains=_text_to_bool(self.query_one("#hsts-subdomains-input", Input).value),
            hsts_preload=_text_to_bool(self.query_one("#hsts-preload-input", Input).value),
        )
        new_config = replace(load_result.config, security=new_security)

        errors = validate_config(new_config)
        if errors:
            error_widget.update("Erreur de validation :\n" + "\n".join(f"  - {e}" for e in errors))
            return

        self._container.configuration.save(self._container.config_file, new_config)
        error_widget.update("")
        notify_reload_required(self, self._container, "Securite generique enregistree.")
