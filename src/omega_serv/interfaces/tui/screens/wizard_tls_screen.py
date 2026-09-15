# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Assistant premier lancement, etape 5/8 - TLS optionnel (plan interface
§11 etape 5) : propose un certificat auto-signe sauf si le profil choisi
est "development" (jamais force). Meme cas d'usage que
GenerateSelfSignedScreen (application/tls/generate_self_signed.py), mais
utilise les chemins de la configuration candidate en memoire
(`state.config.tls.*`) plutot qu'un fichier deja ecrit sur disque -
aucune configuration n'existe encore a ce stade de l'assistant."""
from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING, cast

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, VerticalScroll
from textual.widgets import Button, Footer, Header, Input, Static

from omega_serv.application.tls.generate_self_signed import generate_self_signed_certificate
from omega_serv.domain.security.tls.entities import VALID_KEY_TYPES, KeyType, SelfSignedCertParams
from omega_serv.domain.security.tls.exceptions import CertificateToolError
from omega_serv.interfaces.tui.screens._base import OmegaScreen
from omega_serv.interfaces.tui.screens.wizard_check_screen import WizardCheckScreen

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from omega_serv.application.tls.generate_self_signed import GenerateSelfSignedResult
    from omega_serv.bootstrap.container import DependencyContainer
    from omega_serv.interfaces.tui.screens.wizard_state import WizardState
    from omega_serv.ports.certificate_tool_port import CertificateToolPort


class WizardTlsScreen(OmegaScreen):
    def __init__(self, *, container: DependencyContainer, state: WizardState) -> None:
        super().__init__()
        self._container = container
        self._state = state

    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll(classes="omega-panel"):
            yield Static("ETAPE 5/8 : TLS (OPTIONNEL)", classes="omega-title")
            if self._state.profile_name == "development":
                yield Static(
                    "TLS n'est pas propose pour le profil 'development'. Cette etape est ignoree.",
                    classes="omega-hint",
                )
            else:
                yield Static("", id="form-error", classes="omega-hint")
                yield Static("Nom commun (CN)", classes="omega-subtitle")
                yield Input(id="cn-input")
                yield Static("SAN DNS (separes par des virgules)", classes="omega-subtitle")
                yield Input(id="san-dns-input")
                yield Static(f"Type de cle ({'/'.join(sorted(VALID_KEY_TYPES))})", classes="omega-subtitle")
                yield Input(value="rsa2048", id="key-type-input")
                with Horizontal(classes="omega-actions"), Container(classes="omega-btn-frame"):
                    yield Button("Generer et activer TLS", id="generate", variant="primary")
            with Horizontal(classes="omega-actions"):
                with Container(classes="omega-btn-frame"):
                    yield Button("Suivant (sans TLS)" if self._state.profile_name != "development" else "Suivant", id="next")
                with Container(classes="omega-btn-frame"):
                    yield Button("Precedent", id="back")
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "back":
            self.dismiss()
            return
        if event.button.id == "next":
            self._next()
            return
        if event.button.id == "generate":
            self._generate()

    def _next(self) -> None:
        self.app.push_screen(WizardCheckScreen(container=self._container, state=self._state))

    def _generate(self) -> None:
        error_widget = self.query_one("#form-error", Static)
        factory = self._container.certificate_tool_factory
        if factory is None:
            error_widget.update("Generation indisponible dans cet environnement.")
            return

        key_type_text = self.query_one("#key-type-input", Input).value.strip()
        if key_type_text not in VALID_KEY_TYPES:
            error_widget.update(f"Type de cle invalide : {key_type_text!r}")
            return

        params = SelfSignedCertParams(
            common_name=self.query_one("#cn-input", Input).value.strip(),
            san_dns=tuple(i.strip() for i in self.query_one("#san-dns-input", Input).value.split(",") if i.strip()),
            key_type=cast(KeyType, key_type_text),
        )
        key_path = self._container.project_root / self._state.config.tls.private_key_path
        cert_path = self._container.project_root / self._state.config.tls.certificate_path
        backups_dir = self._container.project_root / "var" / "backups" / "certificates"

        # Retour utilisateur (audit "gel d'ecran") : openssl en
        # sous-processus, execute directement sur la boucle asyncio -
        # gelait TOUTE l'interface. Meme patron que
        # generate_self_signed_screen.py : deporte dans un thread.
        error_widget.update("Generation en cours...")
        self.query_one("#generate", Button).disabled = True
        self.run_worker(
            lambda: self._generate_in_thread(params, key_path, cert_path, backups_dir, factory),
            thread=True, exclusive=True,
        )

    def _generate_in_thread(
        self, params: SelfSignedCertParams, key_path: Path, cert_path: Path, backups_dir: Path,
        factory: Callable[[], CertificateToolPort],
    ) -> None:
        try:
            result = generate_self_signed_certificate(
                params, key_path, cert_path, factory(), self._container.filesystem, self._container.clock, backups_dir,
            )
        except CertificateToolError as exc:
            self.app.call_from_thread(self._finish_generate, None, str(exc))
            return
        self.app.call_from_thread(self._finish_generate, result, None)

    def _finish_generate(self, result: GenerateSelfSignedResult | None, error: str | None) -> None:
        self.query_one("#generate", Button).disabled = False
        error_widget = self.query_one("#form-error", Static)

        if error is not None:
            error_widget.update(f"Erreur : {error}")
            return
        assert result is not None  # garanti par construction : error XOR result
        if not result.success:
            error_widget.update(f"Erreur : {result.message}")
            return

        self._state.config = replace(
            self._state.config, tls=replace(self._state.config.tls, enabled=True, mode="direct"),
        )
        error_widget.update("")
        self.app.notify(result.message)
