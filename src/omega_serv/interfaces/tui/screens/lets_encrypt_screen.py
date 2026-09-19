"""Sous-ecran Assistant Let's Encrypt (etude OMEGA-SERV_PLAN-DETAILLE_TLS_AUTO.md,
Phase 4) - appelle Certbot en mode `--webroot` (jamais `--standalone`,
port 80 deja occupe par omega-serv) avec `--config-dir`/`--work-dir`/
`--logs-dir` sous `secure/certificates/letsencrypt/` (jamais
`/etc/letsencrypt/`, voir domain/security/tls/acme.py) - entierement
non-privilegie, contrairement a `service_screen.py`/`_run_privileged`.

Confirmation explicite avec resume prealable (domaine, mode, webroot)
avant tout appel reseau reel - Certbot en mode staging par defaut
(rate limits Let's Encrypt, etude §5)."""
from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, VerticalScroll
from textual.widgets import Button, Checkbox, Footer, Header, Input, Static

from omega_serv.application.config.load_config import load_config
from omega_serv.application.services.resolve_current_service_name import (
    resolve_current_service_name,
)
from omega_serv.application.tls.request_lets_encrypt_certificate import (
    request_lets_encrypt_certificate,
)
from omega_serv.domain.security.tls.exceptions import CertificateToolError
from omega_serv.interfaces.tui.screens._base import OmegaScreen
from omega_serv.interfaces.tui.screens.confirm import ConfirmScreen
from omega_serv.interfaces.tui.screens.restart_prompt import notify_restart_required

if TYPE_CHECKING:
    from collections.abc import Callable

    from omega_serv.application.tls.request_lets_encrypt_certificate import (
        RequestLetsEncryptCertificateResult,
    )
    from omega_serv.bootstrap.container import DependencyContainer
    from omega_serv.ports.certificate_tool_port import CertificateToolPort
    from omega_serv.ports.process_runner_port import ProcessRunnerPort


class LetsEncryptScreen(OmegaScreen):
    def __init__(self, *, container: DependencyContainer) -> None:
        super().__init__()
        self._container = container

    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll(classes="omega-form-panel"):
            yield Static("ASSISTANT LET'S ENCRYPT (CERTBOT)", classes="omega-title")
            yield Static(
                "Necessite un domaine public deja pointe vers ce serveur et le port 80 "
                "accessible depuis Internet (defi HTTP-01, mode webroot).",
                classes="omega-hint",
            )
            yield Static("", id="form-error", classes="omega-hint")
            yield Static("Domaine (ex : monserveur.dynu.com)", classes="omega-subtitle")
            yield Input(id="domain-input")
            yield Static("Email (optionnel, alertes d'expiration Let's Encrypt)", classes="omega-subtitle")
            yield Input(id="email-input")
            yield Checkbox(
                "Mode test (staging - recommande avant la premiere emission reelle)",
                value=True, id="staging-checkbox",
            )
            with Horizontal(classes="omega-actions"):
                with Container(classes="omega-btn-frame"):
                    yield Button("Obtenir le certificat", id="request", variant="primary")
                with Container(classes="omega-btn-frame"):
                    yield Button("Retour", id="back")
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "back":
            self.dismiss()
            return
        if event.button.id == "request":
            self._request()

    def _request(self) -> None:
        error_widget = self.query_one("#form-error", Static)
        domain = self.query_one("#domain-input", Input).value.strip()
        if not domain:
            error_widget.update("Le domaine ne peut pas etre vide.")
            return

        staging = self.query_one("#staging-checkbox", Checkbox).value
        mode = "TEST (staging - certificat non reconnu par les navigateurs)" if staging else "PRODUCTION (certificat reel, soumis aux limites de taux Let's Encrypt)"
        self.app.push_screen(
            ConfirmScreen(
                title="OBTENIR UN CERTIFICAT LET'S ENCRYPT",
                message=(
                    f"Domaine : {domain}\nMode : {mode}\n\n"
                    "Certbot sera invoque (defi HTTP-01 via webroot), puis le certificat obtenu "
                    "sera importe automatiquement. Un script de renouvellement est installe pour "
                    "les prochaines fois. Confirmer ?"
                ),
            ),
            self._request_if_confirmed,
        )

    def _request_if_confirmed(self, confirmed: bool | None) -> None:
        if not confirmed:
            return
        error_widget = self.query_one("#form-error", Static)
        load_result = load_config(self._container.configuration, self._container.config_file)
        if not load_result.success or load_result.config is None:
            error_widget.update("Erreur de configuration : " + "; ".join(load_result.errors))
            return

        certificate_tool_factory = self._container.certificate_tool_factory
        acme_client_factory = self._container.acme_client_factory
        if certificate_tool_factory is None or acme_client_factory is None:
            error_widget.update("Assistant Let's Encrypt indisponible dans cet environnement.")
            return

        domain = self.query_one("#domain-input", Input).value.strip()
        email = self.query_one("#email-input", Input).value.strip() or None
        staging = self.query_one("#staging-checkbox", Checkbox).value

        project_root = self._container.project_root
        webroot_path = project_root / load_result.config.paths.webroot
        letsencrypt_dir = project_root / "secure" / "certificates" / "letsencrypt"
        dest_key_path = project_root / load_result.config.tls.private_key_path
        dest_cert_path = project_root / load_result.config.tls.certificate_path
        backups_dir = project_root / "var" / "backups" / "certificates"
        service_name = resolve_current_service_name(
            self._container.instance_registry, self._container.filesystem,
            self._container.settings_store, project_root,
        )
        tls_enabled = load_result.config.tls.enabled

        error_widget.update("Demande en cours aupres de Let's Encrypt...")
        self.query_one("#request", Button).disabled = True
        self.run_worker(
            lambda: self._request_in_thread(
                domain, webroot_path, letsencrypt_dir, dest_key_path, dest_cert_path,
                service_name, certificate_tool_factory, acme_client_factory,
                backups_dir, email, staging, tls_enabled,
            ),
            thread=True, exclusive=True,
        )

    def _request_in_thread(
        self,
        domain: str,
        webroot_path: Path,
        letsencrypt_dir: Path,
        dest_key_path: Path,
        dest_cert_path: Path,
        service_name: str,
        certificate_tool_factory: Callable[[], CertificateToolPort],
        acme_client_factory: Callable[[], ProcessRunnerPort],
        backups_dir: Path,
        email: str | None,
        staging: bool,
        tls_enabled: bool,
    ) -> None:
        try:
            result = request_lets_encrypt_certificate(
                domain, webroot_path, letsencrypt_dir, dest_key_path, dest_cert_path,
                service_name, str(self._default_python_executable()),
                acme_client_factory(),
                certificate_tool_factory(),
                self._container.filesystem, self._container.clock, backups_dir,
                email=email, staging=staging,
            )
        except CertificateToolError as exc:
            self.app.call_from_thread(self._finish_request, None, str(exc), tls_enabled)
            return
        self.app.call_from_thread(self._finish_request, result, None, tls_enabled)

    def _finish_request(
        self, result: RequestLetsEncryptCertificateResult | None, error: str | None, tls_enabled: bool,
    ) -> None:
        self.query_one("#request", Button).disabled = False
        error_widget = self.query_one("#form-error", Static)

        if error is not None:
            error_widget.update(f"Erreur : {error}")
            return
        assert result is not None  # garanti par construction dans _request_in_thread : error XOR result
        if not result.success:
            error_widget.update(f"Erreur : {result.message}")
            return
        error_widget.update("")
        if tls_enabled:
            notify_restart_required(
                self, self._container,
                f"{result.message} TLS est actif : le serveur en cours d'execution continue de "
                "servir l'ancien certificat jusqu'a un REDEMARRAGE COMPLET (le fichier a change, "
                "la memoire du processus non).",
            )
        else:
            self.app.notify(result.message)

    def _default_python_executable(self) -> Path:
        venv_python = self._container.project_root / ".venv" / "bin" / "python"
        if self._container.filesystem.exists(venv_python):
            return venv_python
        return Path(sys.executable)
