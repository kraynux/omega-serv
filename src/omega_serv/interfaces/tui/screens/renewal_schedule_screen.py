"""Sous-ecran Renouvellement automatique Certbot (etude
OMEGA-SERV_PLAN-DETAILLE_TLS_AUTO.md, Phase 5) - s'adapte au
gestionnaire de service detecte pour CETTE instance uniquement (retour
utilisateur explicite : chaque instance reste distincte dans sa propre
configuration, une instance peut tres bien ne jamais activer TLS) :
systemd -> timer installe depuis l'interface (meme patron
`_maybe_suspend` que service_screen.py, sudo ponctuel) ; sinon -> ligne
crontab (utilisateur courant, aucun privilege) si possible, sinon
instructions manuelles affichees, jamais d'ecriture forcee."""
from __future__ import annotations

import getpass
from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, VerticalScroll
from textual.widgets import Button, Footer, Header, Static

from omega_serv.application.services.resolve_current_service_name import (
    resolve_current_service_name,
)
from omega_serv.application.tls.schedule_certbot_renewal import (
    check_renewal_schedule_status,
    schedule_certbot_renewal,
)
from omega_serv.interfaces.tui.screens._base import OmegaScreen

if TYPE_CHECKING:
    from omega_serv.bootstrap.container import DependencyContainer
    from omega_serv.ports.service_manager_port import ServiceManagerPort


class RenewalScheduleScreen(OmegaScreen):
    def __init__(self, *, container: DependencyContainer) -> None:
        super().__init__()
        self._container = container

    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll(classes="omega-panel"):
            yield Static("RENOUVELLEMENT AUTOMATIQUE (CERTBOT)", classes="omega-title")
            yield Static(
                "Concerne uniquement CETTE instance (secure/certificates/letsencrypt/) - "
                "une autre instance sans TLS n'a besoin de rien ici.",
                classes="omega-hint",
            )
            yield Static("", id="status-text")
            with Horizontal(classes="omega-actions"):
                with Container(classes="omega-btn-frame"):
                    yield Button("Configurer maintenant", id="configure", variant="primary")
                with Container(classes="omega-btn-frame"):
                    yield Button("Retour", id="back")
        yield Footer()

    def on_mount(self) -> None:
        self._refresh_status()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "back":
            self.dismiss()
            return
        if event.button.id == "refresh":
            self._refresh_status()
            return
        if event.button.id == "configure":
            self._configure()

    def _manager(self) -> ServiceManagerPort | None:
        factory = self._container.service_manager_factory
        return factory() if factory is not None else None

    def _service_name(self) -> str:
        return resolve_current_service_name(
            self._container.instance_registry, self._container.filesystem,
            self._container.settings_store, self._container.project_root,
        )

    def _refresh_status(self) -> None:
        status_widget = self.query_one("#status-text", Static)
        acme_factory = self._container.acme_client_factory
        if acme_factory is None:
            status_widget.update("Verification indisponible dans cet environnement.")
            return
        status = check_renewal_schedule_status(self._service_name(), self._manager(), acme_factory())
        status_widget.update(status.detail)

    def _configure(self) -> None:
        status_widget = self.query_one("#status-text", Static)
        acme_factory = self._container.acme_client_factory
        if acme_factory is None:
            status_widget.update("Configuration indisponible dans cet environnement.")
            return

        manager = self._manager()
        service_name = self._service_name()
        letsencrypt_dir = self._container.project_root / "secure" / "certificates" / "letsencrypt"
        uses_systemd = manager is not None and manager.manager_type() == "systemd"

        if uses_systemd:
            with self._maybe_suspend():
                result = schedule_certbot_renewal(
                    service_name, letsencrypt_dir, manager, self._container.systemd_unit_dir,
                    acme_factory(), getpass.getuser(),
                )
        else:
            result = schedule_certbot_renewal(
                service_name, letsencrypt_dir, manager, self._container.systemd_unit_dir,
                acme_factory(), getpass.getuser(),
            )
        status_widget.update(result.message)
