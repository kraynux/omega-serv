"""Sous-ecran Generer un certificat auto-signe (plan interface §7.3,
`certs generate-self-signed`, TLS 6a). Le mot de passe de cle reste
optionnel ici (SelfSignedCertParams.key_password, contrairement a la CA
locale ou il est obligatoire, doc TLS §7.2/§7.3) - simple saisie
masquee, pas de double confirmation."""
from __future__ import annotations

from typing import TYPE_CHECKING, cast

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, VerticalScroll
from textual.widgets import Button, Footer, Header, Input, Static

from omega_serv.application.config.load_config import load_config
from omega_serv.application.tls.generate_self_signed import generate_self_signed_certificate
from omega_serv.domain.security.tls.entities import VALID_KEY_TYPES, KeyType, SelfSignedCertParams
from omega_serv.domain.security.tls.exceptions import CertificateToolError
from omega_serv.interfaces.tui.screens._base import OmegaScreen
from omega_serv.interfaces.tui.screens.restart_prompt import notify_restart_required

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from omega_serv.application.tls.generate_self_signed import GenerateSelfSignedResult
    from omega_serv.bootstrap.container import DependencyContainer
    from omega_serv.ports.certificate_tool_port import CertificateToolPort


class GenerateSelfSignedScreen(OmegaScreen):
    def __init__(self, *, container: DependencyContainer) -> None:
        super().__init__()
        self._container = container

    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll(classes="omega-form-panel"):
            yield Static("CERTIFICAT AUTO-SIGNE", classes="omega-title")
            yield Static("", id="form-error", classes="omega-hint")
            yield Static("Nom commun (CN)", classes="omega-subtitle")
            yield Input(id="cn-input")
            yield Static("SAN DNS (separes par des virgules)", classes="omega-subtitle")
            yield Input(id="san-dns-input")
            yield Static("SAN IP (separees par des virgules)", classes="omega-subtitle")
            yield Input(id="san-ip-input")
            yield Static("Organisation", classes="omega-subtitle")
            yield Input(value="OMEGA-SERV", id="org-input")
            yield Static("Unite organisationnelle", classes="omega-subtitle")
            yield Input(id="ou-input")
            yield Static("Ville / region / pays", classes="omega-subtitle")
            yield Input(id="city-input")
            yield Input(id="region-input")
            yield Input(id="country-input")
            yield Static("Validite en jours", classes="omega-subtitle")
            yield Input(value="365", id="days-input")
            yield Static(f"Type de cle ({'/'.join(sorted(VALID_KEY_TYPES))})", classes="omega-subtitle")
            yield Input(value="rsa2048", id="key-type-input")
            yield Static("Mot de passe de cle (optionnel)", classes="omega-subtitle")
            yield Input(password=True, id="password-input")
            with Horizontal(classes="omega-actions"):
                with Container(classes="omega-btn-frame"):
                    yield Button("Generer", id="generate", variant="primary")
                with Container(classes="omega-btn-frame"):
                    yield Button("Retour", id="back")
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "back":
            self.dismiss()
            return
        if event.button.id == "generate":
            self._generate()

    def _generate(self) -> None:
        error_widget = self.query_one("#form-error", Static)
        load_result = load_config(self._container.configuration, self._container.config_file)
        if not load_result.success or load_result.config is None:
            error_widget.update("Erreur de configuration : " + "; ".join(load_result.errors))
            return

        factory = self._container.certificate_tool_factory
        if factory is None:
            error_widget.update("Generation indisponible dans cet environnement.")
            return

        days_text = self.query_one("#days-input", Input).value.strip()
        try:
            days = int(days_text)
        except ValueError:
            error_widget.update(f"Validite invalide (nombre attendu) : {days_text!r}")
            return

        key_type_text = self.query_one("#key-type-input", Input).value.strip()
        if key_type_text not in VALID_KEY_TYPES:
            error_widget.update(f"Type de cle invalide : {key_type_text!r} (attendu : {', '.join(sorted(VALID_KEY_TYPES))})")
            return

        password = self.query_one("#password-input", Input).value.strip() or None
        params = SelfSignedCertParams(
            common_name=self.query_one("#cn-input", Input).value.strip(),
            san_dns=tuple(i.strip() for i in self.query_one("#san-dns-input", Input).value.split(",") if i.strip()),
            san_ip=tuple(i.strip() for i in self.query_one("#san-ip-input", Input).value.split(",") if i.strip()),
            organization=self.query_one("#org-input", Input).value.strip(),
            organizational_unit=self.query_one("#ou-input", Input).value.strip(),
            city=self.query_one("#city-input", Input).value.strip(),
            region=self.query_one("#region-input", Input).value.strip(),
            country=self.query_one("#country-input", Input).value.strip(),
            validity_days=days,
            key_type=cast(KeyType, key_type_text),
            key_password=password,
        )

        key_path = self._container.project_root / load_result.config.tls.private_key_path
        cert_path = self._container.project_root / load_result.config.tls.certificate_path
        backups_dir = self._container.project_root / "var" / "backups" / "certificates"

        error_widget.update("Generation en cours...")
        self.query_one("#generate", Button).disabled = True
        self.run_worker(
            lambda: self._generate_in_thread(params, key_path, cert_path, factory, backups_dir, load_result.config.tls.enabled),
            thread=True, exclusive=True,
        )

    def _generate_in_thread(
        self,
        params: SelfSignedCertParams,
        key_path: Path,
        cert_path: Path,
        factory: Callable[[], CertificateToolPort],
        backups_dir: Path,
        tls_enabled: bool,
    ) -> None:
        try:
            result = generate_self_signed_certificate(
                params, key_path, cert_path, factory(), self._container.filesystem, self._container.clock, backups_dir,
            )
        except CertificateToolError as exc:
            self.app.call_from_thread(self._finish_generate, None, str(exc), tls_enabled)
            return
        self.app.call_from_thread(self._finish_generate, result, None, tls_enabled)

    def _finish_generate(self, result: GenerateSelfSignedResult | None, error: str | None, tls_enabled: bool) -> None:
        self.query_one("#generate", Button).disabled = False
        error_widget = self.query_one("#form-error", Static)

        if error is not None:
            error_widget.update(f"Erreur : {error}")
            return
        assert result is not None  # garanti par construction dans _generate_in_thread : error XOR result
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
