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
    repair_directory_permissions,
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
from omega_serv.core.i18n import _
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
            yield Static(_("SERVICE"), classes="omega-title")
            directory_hint = self._directory_hint()
            if directory_hint:
                yield Static(directory_hint, classes="omega-hint")
            registered_entry = self._registered_entry_for_this_instance()
            with Horizontal(classes="omega-actions omega-labeled-input-row"):
                yield Static(_("Nom du service :"), classes="omega-input-row-label")
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
                    _("Nom figé (instance enregistrée en multi-instance) - "
                    "voir Menu Multi-instance pour gérer d'autres instances/services."),
                    classes="omega-hint",
                )
            yield Static("", id="service-status", classes="omega-hint")
            with Horizontal(classes="omega-actions"):
                with Container(classes="omega-btn-frame"):
                    yield Button(_("Rafraîchir"), id="refresh")
                for item_id, label in (
                    ("start", _("Démarrer")), ("stop", _("Arrêter")), ("restart", _("Redémarrer")), ("reload", _("Recharger")),
                ):
                    with Container(classes="omega-btn-frame"):
                        yield Button(label, id=item_id)
            with Horizontal(classes="omega-actions"):
                for item_id, label in (("enable", _("Activer au démarrage")), ("disable", _("Désactiver au démarrage"))):
                    with Container(classes="omega-btn-frame"):
                        yield Button(label, id=item_id)
            with Horizontal(classes="omega-actions"):
                with Container(classes="omega-btn-frame"):
                    yield Button(_("Installer l'unité"), id="install")
                with Container(classes="omega-btn-frame"):
                    yield Button(_("Désinstaller l'unité"), id="uninstall", variant="error")
            with Horizontal(classes="omega-actions"):
                with Container(classes="omega-btn-frame"):
                    yield Button(_("Réparer les permissions"), id="repair-permissions")
                with Container(classes="omega-btn-frame"):
                    yield Button(_("Retour"), id="back")
            yield Static("", id="journey-hint", classes="omega-hint")
        yield Footer()

    def on_mount(self) -> None:
        factory = self._container.service_manager_factory
        self._manager = factory() if factory is not None else None
        if self._manager is None:
            self.query_one("#service-status", Static).update(
                _("Aucun gestionnaire de service reconnu (systemd/OpenRC/runit) sur ce système.")
            )
            self._set_mutating_buttons_disabled(True)
            return
        if self._manager.manager_type() != "systemd":
            self.query_one("#install", Button).disabled = True
            self.query_one("#uninstall", Button).disabled = True
            self.query_one("#repair-permissions", Button).disabled = True
        self.query_one("#journey-hint", Static).update(self._journey_hint())
        self._refresh_status()

    def _journey_hint(self) -> str:
        assert self._manager is not None
        if self._manager.manager_type() == "systemd":
            return (
                _("SYSTEMD uniquement : 'Installer l'unité' (une fois) prépare tout "
                "(fichier systemd + compte dédié) ; 'Démarrer' échoue tant que ce n'est "
                "pas fait. Lancement immédiat sans service : assistant premier lancement "
                "-> 'Lancer maintenant'.")
            )
        return (
            _("{value} : service déjà configuré sur le système requis (installation/desinstallation non proposées ici) - voir le guide d'aide pour le détail (à venir).").format(value=self._manager.manager_type().upper())
        )

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "service-name":
            self._container.settings_store.set(_SERVICE_NAME_KEY, event.value)

    def _directory_hint(self) -> str:
        if len(self._container.instance_registry.load()) <= 1:
            return ""
        return _("Répertoire pilote : {project_root}").format(project_root=self._container.project_root)

    def _set_mutating_buttons_disabled(self, disabled: bool) -> None:
        for item_id in (
            "start", "stop", "restart", "reload", "enable", "disable",
            "install", "uninstall", "repair-permissions",
        ):
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
                _("Actif : {active}   Activé au démarrage : {enabled}   État : {state} ({sub_state})\n{description}").format(active=result.active, enabled=result.enabled, state=result.state, sub_state=result.sub_state, description=result.description)
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
                    _("Une autre unité ({conflict!r}) pointe déjà vers ce répertoire - l'installer sous un second nom créerait un conflit (même fichier PID, même config, même compte système). Pour héberger plusieurs serveurs, installez une copie séparée d'OMEGA-SERV dans un autre répertoire (chaque copie a son propre var/config/unite) - cet écran peut déjà piloter n'importe quelle unité installée (demarrer/arreter/statut) en tapant simplement son nom, sans avoir à lancer l'interface depuis chaque répertoire.").format(conflict=conflict),
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
                    _("Le nom {value!r} est déjà utilisé par une unité pointant vers {value2!r} (une autre installation) - l'installer ici écraserait cette unité et vous priverait du contrôle sur ce serveur-la. Choisissez un nom différent, ou lancez cette action depuis l'installation d'origine.").format(value=self._service_name(), value2=str(hijack)),
                    severity="error",
                    timeout=15,
                )
                return
            self.app.push_screen(
                ConfirmScreen(
                    title=_("INSTALLER L'UNITÉ SYSTEMD"),
                    message=(
                        _("Service : {value}\nUtilisateur/groupe dédiés : {DEFAULT_SYSTEM_USER}/{DEFAULT_SYSTEM_GROUP}\nUne authentification (sudo) sera demandée pour l'écriture dans /etc/systemd/system/ et le rechargement de systemd. Continuer ?").format(value=self._service_name(), DEFAULT_SYSTEM_USER=DEFAULT_SYSTEM_USER, DEFAULT_SYSTEM_GROUP=DEFAULT_SYSTEM_GROUP)
                    ),
                ),
                self._install_if_confirmed,
            )
            return
        if button_id == "uninstall":
            self.app.push_screen(
                ConfirmScreen(
                    title=_("DÉSINSTALLER L'UNITÉ SYSTEMD"),
                    message=_("Retirer l'unité du service {value!r} ? Une authentification (sudo) sera demandée.").format(value=self._service_name()),
                ),
                self._uninstall_if_confirmed,
            )
            return
        if button_id == "repair-permissions":
            self.app.push_screen(
                ConfirmScreen(
                    title=_("RÉPARER LES PERMISSIONS"),
                    message=(
                        _("Réapplique le partage de permissions sur var/ et secure/auth/ pour le compte système dédié ({DEFAULT_SYSTEM_GROUP}) - utile après une mise à jour par extraction d'archive (tar restaure les permissions d'origine, annulant ce partage) si le service boucle en redémarrage avec une 'PermissionError' dans les journaux. Ne touche jamais à l'unité systemd elle-même. Une authentification (sudo) sera demandée. Continuer ?").format(DEFAULT_SYSTEM_GROUP=DEFAULT_SYSTEM_GROUP)
                    ),
                ),
                self._repair_permissions_if_confirmed,
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
            description=_("OMEGA-SERV web server"),
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

    def _repair_permissions_if_confirmed(self, confirmed: bool | None) -> None:
        if not confirmed or self._manager is None:
            return
        with self._maybe_suspend():
            result = repair_directory_permissions(
                self._container.filesystem, self._container.project_root,
                DEFAULT_SYSTEM_GROUP, getpass.getuser(), self._manager,
            )
        self.app.notify(result.message, severity="information" if result.success else "error")
        self._refresh_status()
