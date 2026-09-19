"""Ecran Service (plan interface §9, `service status/start/stop/restart/
enable/disable/install/uninstall`) - toute operation mutante (start/stop/
restart/enable/disable/install/uninstall) passe par `self.app.suspend()` :
le gestionnaire systemd prefixe ses commandes par `sudo` quand le
processus n'est pas deja root (infrastructure/services/
systemd_service_manager.py::_run_privileged), et sudo lit son mot de passe
sur le terminal reel - Textual doit liberer le terminal le temps de
l'invite, sinon le rendu brut de sudo se melange a celui de l'app (plan
interface §3.6, decision 2026-09-08 : elevation par action, jamais par
lancement de l'appli entiere en root)."""
from __future__ import annotations

import getpass
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Button, Footer, Header, Input, Static

from omega_serv.application.services.install_service import (
    check_for_conflicting_unit,
    check_for_name_hijack,
    install_systemd_service,
    uninstall_systemd_service,
)
from omega_serv.application.services.manage_service import (
    ManageServiceResult,
    disable_service,
    enable_service,
    get_service_status,
    reload_service,
    restart_service,
    start_service,
    stop_service,
)
from omega_serv.domain.instances.entities import InstanceEntry
from omega_serv.domain.services.entities import ServiceStatus
from omega_serv.domain.services.systemd_unit import (
    DEFAULT_SYSTEM_GROUP,
    DEFAULT_SYSTEM_USER,
    SystemdUnitParams,
)
from omega_serv.interfaces.tui.screens._base import OmegaScreen
from omega_serv.interfaces.tui.screens.confirm import ConfirmScreen

if TYPE_CHECKING:
    from omega_serv.bootstrap.container import DependencyContainer
    from omega_serv.ports.service_manager_port import ServiceManagerPort

_DEFAULT_SERVICE_NAME = "omega-serv"
_SERVICE_NAME_KEY = "service_name"
"""Persiste le nom de service tape ici dans settings_store
(var/settings.json, meme mecanisme que le theme/profil de rendu/
chemins d'export - preference d'interface, jamais melangee a
config/omega-serve.json) - sans cela, resource_status_screen.py
(ecran totalement separe) n'a aucun moyen de savoir quel nom a ete
choisi ici et affiche le statut d'une unite potentiellement sans
rapport apres un renommage (bug latent signale, corrige ici)."""

class ServiceScreen(OmegaScreen):
    def __init__(self, *, container: DependencyContainer) -> None:
        super().__init__()
        self._container = container
        self._manager: ServiceManagerPort | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(classes="omega-panel"):
            yield Static("SERVICE", classes="omega-title")
            directory_hint = self._directory_hint()
            if directory_hint:
                yield Static(directory_hint, classes="omega-hint")
            registered_entry = self._registered_entry_for_this_instance()
            with Horizontal(classes="omega-actions omega-labeled-input-row"):
                yield Static("Nom du service :", classes="omega-input-row-label")
                yield Input(
                    value=(
                        registered_entry.service_name if registered_entry is not None
                        else self._container.settings_store.get(_SERVICE_NAME_KEY, "") or _DEFAULT_SERVICE_NAME
                    ),
                    id="service-name",
                    disabled=registered_entry is not None,
                )
            if registered_entry is not None:
                yield Static(
                    "Nom fige (instance enregistree en multi-instance) - "
                    "voir Menu Multi-instance pour gerer d'autres instances/services.",
                    classes="omega-hint",
                )
            yield Static("", id="service-status", classes="omega-hint")
            with Horizontal(classes="omega-actions"):
                with Container(classes="omega-btn-frame"):
                    yield Button("Rafraichir", id="refresh")
                for item_id, label in (
                    ("start", "Demarrer"), ("stop", "Arreter"), ("restart", "Redemarrer"), ("reload", "Recharger"),
                ):
                    with Container(classes="omega-btn-frame"):
                        yield Button(label, id=item_id)
            with Horizontal(classes="omega-actions"):
                for item_id, label in (("enable", "Activer au demarrage"), ("disable", "Desactiver au demarrage")):
                    with Container(classes="omega-btn-frame"):
                        yield Button(label, id=item_id)
            with Horizontal(classes="omega-actions"):
                with Container(classes="omega-btn-frame"):
                    yield Button("Installer l'unite", id="install")
                with Container(classes="omega-btn-frame"):
                    yield Button("Desinstaller l'unite", id="uninstall", variant="error")
                with Container(classes="omega-btn-frame"):
                    yield Button("Retour", id="back")
            yield Static("", id="journey-hint", classes="omega-hint")
        yield Footer()

    def on_mount(self) -> None:
        factory = self._container.service_manager_factory
        self._manager = factory() if factory is not None else None
        if self._manager is None:
            self.query_one("#service-status", Static).update(
                "Aucun gestionnaire de service reconnu (systemd/OpenRC/runit) sur ce systeme."
            )
            self._set_mutating_buttons_disabled(True)
            return
        if self._manager.manager_type() != "systemd":
            self.query_one("#install", Button).disabled = True
            self.query_one("#uninstall", Button).disabled = True
        self.query_one("#journey-hint", Static).update(self._journey_hint())
        self._refresh_status()

    def _journey_hint(self) -> str:
        assert self._manager is not None
        if self._manager.manager_type() == "systemd":
            return (
                "SYSTEMD uniquement : 'Installer l'unite' (une fois) prepare tout "
                "(fichier systemd + compte dedie) ; 'Demarrer' echoue tant que ce n'est "
                "pas fait. Lancement immediat sans service : assistant premier lancement "
                "-> 'Lancer maintenant'."
            )
        return (
            f"{self._manager.manager_type().upper()} : service deja configure sur le "
            "systeme requis (installation/desinstallation non proposees ici) - voir le "
            "guide d'aide pour le detail (a venir)."
        )

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "service-name":
            self._container.settings_store.set(_SERVICE_NAME_KEY, event.value)

    def _directory_hint(self) -> str:
        if len(self._container.instance_registry.load()) <= 1:
            return ""
        return f"Repertoire pilote : {self._container.project_root}"

    def _set_mutating_buttons_disabled(self, disabled: bool) -> None:
        for item_id in ("start", "stop", "restart", "reload", "enable", "disable", "install", "uninstall"):
            self.query_one(f"#{item_id}", Button).disabled = disabled

    def _service_name(self) -> str:
        return self.query_one("#service-name", Input).value.strip() or _DEFAULT_SERVICE_NAME

    def _registered_entry_for_this_instance(self) -> InstanceEntry | None:
        current_path = self._container.filesystem.resolve_real_path(self._container.project_root)
        for entry in self._container.instance_registry.load():
            if entry.path == current_path:
                return entry
        return None

    def _refresh_status(self) -> None:
        if self._manager is None:
            return
        result = get_service_status(self._manager, self._service_name())
        status_widget = self.query_one("#service-status", Static)
        if isinstance(result, ServiceStatus):
            status_widget.update(
                f"Actif : {result.active}   Active au demarrage : {result.enabled}   "
                f"Etat : {result.state} ({result.sub_state})\n{result.description}"
            )
        else:
            status_widget.update(result.message)

    def _default_python_executable(self) -> Path:
        venv_python = self._container.project_root / ".venv" / "bin" / "python"
        if self._container.filesystem.exists(venv_python):
            return venv_python
        return Path(sys.executable)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id
        if button_id == "back":
            self.dismiss()
            return
        if button_id == "refresh":
            self._refresh_status()
            return
        if self._manager is None:
            return
        if button_id in ("start", "stop", "restart", "reload", "enable", "disable"):
            self._run_control(button_id)
            return
        if button_id == "install":
            conflict = check_for_conflicting_unit(
                self._container.filesystem, self._container.systemd_unit_dir,
                self._container.project_root, self._service_name(),
            )
            if conflict is not None:
                self.app.notify(
                    f"Une autre unite ({conflict!r}) pointe deja vers ce repertoire - "
                    "l'installer sous un second nom creerait un conflit (meme fichier PID, "
                    "meme config, meme compte systeme). Pour heberger plusieurs serveurs, "
                    "installez une copie separee d'OMEGA-SERV dans un autre repertoire "
                    "(chaque copie a son propre var/config/unite) - cet ecran peut deja "
                    "piloter n'importe quelle unite installee (demarrer/arreter/statut) en "
                    "tapant simplement son nom, sans avoir a lancer l'interface depuis "
                    "chaque repertoire.",
                    severity="error",
                    timeout=15,
                )
                return
            hijack = check_for_name_hijack(
                self._container.filesystem, self._container.systemd_unit_dir,
                self._container.project_root, self._service_name(),
            )
            if hijack is not None:
                self.app.notify(
                    f"Le nom {self._service_name()!r} est deja utilise par une unite "
                    f"pointant vers {str(hijack)!r} (une autre installation) - "
                    "l'installer ici ecraserait cette unite et vous priverait du controle "
                    "sur ce serveur-la. Choisissez un nom different, ou lancez cette action "
                    "depuis l'installation d'origine.",
                    severity="error",
                    timeout=15,
                )
                return
            self.app.push_screen(
                ConfirmScreen(
                    title="INSTALLER L'UNITE SYSTEMD",
                    message=(
                        f"Service : {self._service_name()}\n"
                        f"Utilisateur/groupe dedies : {DEFAULT_SYSTEM_USER}/{DEFAULT_SYSTEM_GROUP}\n"
                        f"Une authentification (sudo) sera demandee pour l'ecriture dans "
                        f"/etc/systemd/system/ et le rechargement de systemd. Continuer ?"
                    ),
                ),
                self._install_if_confirmed,
            )
            return
        if button_id == "uninstall":
            self.app.push_screen(
                ConfirmScreen(
                    title="DESINSTALLER L'UNITE SYSTEMD",
                    message=f"Retirer l'unite du service {self._service_name()!r} ? Une authentification (sudo) sera demandee.",
                ),
                self._uninstall_if_confirmed,
            )

    def _run_control(self, action: str) -> None:
        assert self._manager is not None
        action_map = {
            "start": start_service, "stop": stop_service, "restart": restart_service, "reload": reload_service,
            "enable": enable_service, "disable": disable_service,
        }
        with self._maybe_suspend():
            result: ManageServiceResult = action_map[action](self._manager, self._service_name())
        self.app.notify(result.message, severity="information" if result.success else "error")
        self._refresh_status()

    def _install_if_confirmed(self, confirmed: bool | None) -> None:
        if not confirmed or self._manager is None:
            return
        service_name = self._service_name()
        params = SystemdUnitParams(
            service_name=service_name,
            description="OMEGA-SERV web server",
            python_executable=self._default_python_executable(),
            project_root=self._container.project_root,
            config_path=self._container.config_file,
            user=DEFAULT_SYSTEM_USER,
            group=DEFAULT_SYSTEM_GROUP,
        )
        unit_path = self._container.systemd_unit_dir / f"{service_name}.service"
        with self._maybe_suspend():
            result = install_systemd_service(
                self._container.filesystem, params, unit_path, self._manager,
                installing_user=getpass.getuser(),
            )
        self.app.notify(result.message, severity="information" if result.success else "error")
        self._refresh_status()

    def _uninstall_if_confirmed(self, confirmed: bool | None) -> None:
        if not confirmed or self._manager is None:
            return
        unit_path = self._container.systemd_unit_dir / f"{self._service_name()}.service"
        with self._maybe_suspend():
            result = uninstall_systemd_service(self._container.filesystem, unit_path, self._manager)
        self.app.notify(result.message, severity="information" if result.success else "error")
        self._refresh_status()
