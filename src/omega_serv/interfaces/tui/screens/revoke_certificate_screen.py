# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Sous-ecran Revoquer un certificat (plan interface §7.3, `certs
revoke`) - marque le numero de serie comme revoque dans index.txt
(bascule minimale, doc TLS §7.3 etape derniere / OMEGA-SERV_PLAN
§6 : pas de distribution CRL complete en V1)."""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, VerticalScroll
from textual.widgets import Button, Footer, Header, Input, Static

from omega_serv.application.config.load_config import load_config
from omega_serv.application.tls.revoke_certificate import revoke_certificate
from omega_serv.domain.security.tls.exceptions import CertificateToolError
from omega_serv.interfaces.tui.screens._base import OmegaScreen
from omega_serv.interfaces.tui.screens.confirm import ConfirmScreen
from omega_serv.interfaces.tui.screens.restart_prompt import notify_restart_required

if TYPE_CHECKING:
    from collections.abc import Callable

    from omega_serv.application.tls.revoke_certificate import RevokeCertificateResult
    from omega_serv.bootstrap.container import DependencyContainer
    from omega_serv.ports.certificate_tool_port import CertificateToolPort


class RevokeCertificateScreen(OmegaScreen):
    def __init__(self, *, container: DependencyContainer) -> None:
        super().__init__()
        self._container = container

    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll(classes="omega-form-panel"):
            yield Static("REVOQUER UN CERTIFICAT", classes="omega-title")
            yield Static("", id="form-error", classes="omega-hint")
            yield Static("Certificat a revoquer", classes="omega-subtitle")
            yield Input(id="cert-input")
            yield Static("Cle de la CA (root-ca.key)", classes="omega-subtitle")
            yield Input(
                value=str(Path("secure") / "certificates" / "ca" / "root-ca.key"),
                id="ca-key-input",
            )
            yield Static("Certificat de la CA (root-ca.pem)", classes="omega-subtitle")
            yield Input(
                value=str(Path("secure") / "certificates" / "ca" / "root-ca.pem"),
                id="ca-cert-input",
            )
            yield Static("Passphrase de la cle CA", classes="omega-subtitle")
            yield Input(password=True, id="password-input")
            with Horizontal(classes="omega-actions"):
                with Container(classes="omega-btn-frame"):
                    yield Button("Revoquer", id="revoke", variant="error")
                with Container(classes="omega-btn-frame"):
                    yield Button("Retour", id="back")
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "back":
            self.dismiss()
            return
        if event.button.id == "revoke":
            self.app.push_screen(
                ConfirmScreen(
                    title="REVOQUER LE CERTIFICAT",
                    message="Cette action est irreversible pour ce certificat. Confirmer la revocation ?",
                ),
                self._revoke_if_confirmed,
            )

    def _revoke_if_confirmed(self, confirmed: bool | None) -> None:
        if not confirmed:
            return
        error_widget = self.query_one("#form-error", Static)
        factory = self._container.certificate_tool_factory
        if factory is None:
            error_widget.update("Revocation indisponible dans cet environnement.")
            return

        cert_path = self._container.project_root / self.query_one("#cert-input", Input).value.strip()
        ca_key_path = self._container.project_root / self.query_one("#ca-key-input", Input).value.strip()
        ca_cert_path = self._container.project_root / self.query_one("#ca-cert-input", Input).value.strip()
        password = self.query_one("#password-input", Input).value

        # Retour utilisateur (audit "gel d'ecran") : openssl en
        # sous-processus, execute directement sur la boucle asyncio -
        # gelait TOUTE l'interface. Meme patron que
        # generate_self_signed_screen.py : deporte dans un thread.
        error_widget.update("Revocation en cours...")
        self.query_one("#revoke", Button).disabled = True
        self.run_worker(
            lambda: self._revoke_in_thread(cert_path, ca_key_path, ca_cert_path, password, factory),
            thread=True, exclusive=True,
        )

    def _revoke_in_thread(
        self, cert_path: Path, ca_key_path: Path, ca_cert_path: Path, password: str,
        factory: Callable[[], CertificateToolPort],
    ) -> None:
        try:
            result = revoke_certificate(
                cert_path, ca_key_path, ca_cert_path, password, ca_key_path.parent / "index.txt",
                factory(), self._container.filesystem,
            )
        except CertificateToolError as exc:
            self.app.call_from_thread(self._finish_revoke, None, str(exc), cert_path)
            return
        self.app.call_from_thread(self._finish_revoke, result, None, cert_path)

    def _finish_revoke(self, result: RevokeCertificateResult | None, error: str | None, cert_path: Path) -> None:
        self.query_one("#revoke", Button).disabled = False
        error_widget = self.query_one("#form-error", Static)

        if error is not None:
            error_widget.update(f"Erreur : {error}")
            return
        assert result is not None  # garanti par construction : error XOR result
        if not result.success:
            error_widget.update(f"Erreur : {result.message}")
            return
        error_widget.update("")
        # Retour utilisateur 2026-09-13 : le contexte SSL du serveur en
        # cours d'execution est construit UNE FOIS (jamais retouche par
        # reload_scoped) - s'il sert precisement CE certificat, revoquer
        # ne l'empeche jamais de continuer a le presenter aux clients
        # tant qu'un redemarrage complet n'a pas eu lieu.
        load_result = load_config(self._container.configuration, self._container.config_file)
        active_cert_matches = (
            load_result.success and load_result.config is not None and load_result.config.tls.enabled
            and (self._container.project_root / load_result.config.tls.certificate_path).resolve() == cert_path.resolve()
        )
        if active_cert_matches:
            notify_restart_required(
                self, self._container,
                f"{result.message} Ce certificat est celui actuellement utilise par le serveur "
                "(TLS actif) : un REDEMARRAGE COMPLET est necessaire, sinon il continue d'etre "
                "presente aux clients malgre la revocation.",
            )
        else:
            self.app.notify(result.message)
