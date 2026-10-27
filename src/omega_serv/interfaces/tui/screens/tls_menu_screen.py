"""Sous-ecran TLS (plan interface §7.3, Phase III) - sous-menu vers
statut/generation auto-signee (6a)/assistant CA locale (6b)/revocation/
activation-desactivation. Absent de la spec §8.3 d'origine (Phase 6
n'existait pas encore quand §8 a ete ecrit), ajoute au plan interface."""
from __future__ import annotations

from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.containers import Center, Container, Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Static

from omega_serv.core.i18n import _
from omega_serv.interfaces.tui.screens._base import OmegaScreen
from omega_serv.interfaces.tui.screens.ca_wizard_screen import CaWizardScreen
from omega_serv.interfaces.tui.screens.generate_self_signed_screen import GenerateSelfSignedScreen
from omega_serv.interfaces.tui.screens.lets_encrypt_screen import LetsEncryptScreen
from omega_serv.interfaces.tui.screens.renewal_schedule_screen import RenewalScheduleScreen
from omega_serv.interfaces.tui.screens.revoke_certificate_screen import RevokeCertificateScreen
from omega_serv.interfaces.tui.screens.tls_status_screen import TlsStatusScreen
from omega_serv.interfaces.tui.screens.tls_toggle_screen import TlsToggleScreen

if TYPE_CHECKING:
    from omega_serv.bootstrap.container import DependencyContainer

_MENU_ITEMS: tuple[tuple[str, str], ...] = (
    ("status", _("Statut TLS")),
    ("self-signed", _("Générer un certificat auto-signé")),
    ("ca-wizard", _("Assistant CA locale")),
    ("lets-encrypt", _("Assistant Let's Encrypt (Certbot)")),
    ("renewal-schedule", _("Renouvellement automatique (Certbot)")),
    ("revoke", _("Révoquer un certificat")),
    ("toggle", _("Activer / désactiver TLS")),
)


class TlsMenuScreen(OmegaScreen):
    def __init__(self, *, container: DependencyContainer) -> None:
        super().__init__()
        self._container = container

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(classes="omega-panel"):
            with Center():
                yield Static(_("TLS"), classes="omega-title")
            with Center(), Vertical(classes="omega-home-menu") as menu:
                for item_id, label in _MENU_ITEMS:
                    with Container(classes="omega-btn-frame"):
                        yield Button(label, id=item_id)
                menu.border_title = _("SOUS-ÉCRANS TLS")
            with Center(), Horizontal(classes="omega-actions"), Container(classes="omega-btn-frame"):
                yield Button(_("Retour"), id="back")
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "back":
            self.dismiss()
            return
        screen = self._screen_for(event.button.id)
        if screen is not None:
            self.app.push_screen(screen)

    def _screen_for(self, item_id: str | None) -> Screen[None] | None:
        mapping = {
            "status": TlsStatusScreen, "self-signed": GenerateSelfSignedScreen,
            "ca-wizard": CaWizardScreen, "lets-encrypt": LetsEncryptScreen,
            "renewal-schedule": RenewalScheduleScreen,
            "revoke": RevokeCertificateScreen, "toggle": TlsToggleScreen,
        }
        screen_cls = mapping.get(item_id) if item_id else None
        if screen_cls is None:
            return None
        return screen_cls(container=self._container)
