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
from typing import TYPE_CHECKING, cast

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
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
from omega_serv.application.services.rename_service import (
    RenamePlan,
    plan_rename,
    rename_installed_service,
    validate_service_name,
)
from omega_serv.core.i18n import _
from omega_serv.domain.instances.entities import InstanceEntry
from omega_serv.domain.services.entities import ServiceStatus
from omega_serv.domain.services.shared_access import SharedAccessReport
from omega_serv.domain.services.systemd_unit import (
    DEFAULT_SYSTEM_GROUP,
    DEFAULT_SYSTEM_USER,
    SystemdUnitParams,
)
from omega_serv.interfaces.tui.screens._base import OmegaScreen, main_menu_title
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

_REFRESH_SECONDS = 3.0
"""Etat relu seul (plus de bouton « Rafraichir », decision de l'auteur du 2026-11-15) ; aussi apres chaque action."""


def _colored(style: str, text: str) -> str:
    """Etat en couleur du theme (balises Textual) ; le texte vient deja traduit."""
    return "[" + style + "]" + text + "[/]"


def button_states(manager_type: str | None, installed: bool, status: ServiceStatus | None,
                  permissions_ok: bool | None) -> dict[str, bool]:
    """Boutons ACTIFS selon l'etat (decision de l'auteur du 2026-11-15 : seuls les boutons qui servent sont actifs,
    on ne devine plus). `installed` : unite systemd presente ; hors systemd, le service est gere par le systeme
    (toujours vrai). `permissions_ok` None = inconnu (reparation proposee)."""
    if manager_type is None:
        return dict.fromkeys(("install", "uninstall", "enable", "disable", "repair-permissions",
                              "start", "stop", "restart", "reload"), False)
    systemd = manager_type == "systemd"
    active = status is not None and status.active
    enabled = status is not None and status.enabled
    known = status is not None
    return {
        "install": systemd and not installed,
        "uninstall": systemd and installed,
        "enable": installed and known and not enabled,
        "disable": installed and known and enabled,
        "repair-permissions": systemd and installed and permissions_ok is not True,
        "start": installed and known and not active,
        "stop": installed and active,
        "restart": installed and active,
        "reload": installed and active,
    }


class ServiceScreen(OmegaScreen):
    """Formulaire en 5 lignes (decision de l'auteur du 2026-11-15) : un titre et son etat a gauche, des boutons de
    meme largeur a droite, dans l'ordre d'usage - nom, installation, demarrage, permissions, pilotage ; Retour seul en
    bas, hors de la zone qui defile."""

    def __init__(self, *, container: DependencyContainer) -> None:
        super().__init__()
        self._container = container
        self._manager: ServiceManagerPort | None = None
        self._registered_entry = self._registered_entry_for_this_instance()
        self._current_name = (
            self._registered_entry.service_name if self._registered_entry is not None
            else self._container.settings_store.get(_SERVICE_NAME_KEY, "") or _DEFAULT_SERVICE_NAME
        )
        self._editing = False
        self._permissions: SharedAccessReport | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll(classes="omega-panel omega-service-panel"):
            yield main_menu_title(_("SERVICE"))
            directory_hint = self._directory_hint()
            if directory_hint:
                yield Static(directory_hint, classes="omega-hint")
            with Vertical(classes="omega-service-form"):
                with Horizontal(classes="omega-service-row"):
                    yield from self._label(_("Nom du service"), "state-name")
                    yield Input(value=self._current_name, id="service-name", disabled=True,
                                classes="omega-service-name-input", max_length=64)
                    with Container(classes="omega-btn-frame"):
                        yield Button(_("Modifier"), id="edit-name", disabled=self._registered_entry is not None)
                with Horizontal(classes="omega-service-row"):
                    yield from self._label(_("Installation"), "state-install")
                    with Container(classes="omega-btn-frame omega-service-wide"):
                        yield Button(_("Installer l'unité"), id="install")
                    with Container(classes="omega-btn-frame omega-service-wide"):
                        yield Button(_("Désinstaller l'unité"), id="uninstall", variant="error")
                with Horizontal(classes="omega-service-row"):
                    yield from self._label(_("Démarrage"), "state-boot")
                    with Container(classes="omega-btn-frame omega-service-wide"):
                        yield Button(_("Activer au démarrage"), id="enable")
                    with Container(classes="omega-btn-frame omega-service-wide"):
                        yield Button(_("Désactiver au démarrage"), id="disable")
                with Horizontal(classes="omega-service-row"):
                    yield from self._label(_("Permissions"), "state-permissions")
                    with Container(classes="omega-btn-frame omega-service-wide"):
                        yield Button(_("Réparer les permissions"), id="repair-permissions")
                with Horizontal(classes="omega-service-row"):
                    yield from self._label(_("Pilotage"), "state-control")
                    for item_id, label in (
                        ("start", _("Démarrer")), ("stop", _("Arrêter")), ("restart", _("Redémarrer")),
                        ("reload", _("Recharger")),
                    ):
                        with Container(classes="omega-btn-frame"):
                            yield Button(label, id=item_id)
            # Message d'une action (saisie refusee...) : a part de l'etat, que le rafraichissement automatique
            # reecrit toutes les 3 s - sinon l'explication disparaissait avant d'etre lue.
            yield Static("", id="service-message", classes="omega-hint")
            yield Static("", id="service-status", classes="omega-hint")
            yield Static("", id="journey-hint", classes="omega-hint")
        with Horizontal(classes="omega-actions omega-riposte-actions omega-service-back"), \
                Container(classes="omega-btn-frame"):
            yield Button(_("Retour"), id="back")
        yield Footer()

    @staticmethod
    def _label(title: str, state_id: str) -> ComposeResult:
        with Vertical(classes="omega-service-label"):
            yield Static(title, classes="omega-service-label-title")
            yield Static("", id=state_id, classes="omega-service-label-state")

    def on_mount(self) -> None:
        # Libelles sans marge interne : la CSS refuse « line-pad: 0 » (entier non nul exige), d'ou le reglage ici ;
        # « Désactiver au démarrage » tient alors dans sa colonne double.
        for button in self.query(".omega-service-row Button").results(Button):
            button.styles.line_pad = 0
        factory = self._container.service_manager_factory
        self._manager = factory() if factory is not None else None
        if self._registered_entry is not None:
            self.query_one("#state-name", Static).update(_("figé"))
        if self._manager is None:
            self.query_one("#service-status", Static).update(
                _("Aucun gestionnaire de service reconnu (systemd/OpenRC/runit) sur ce système.")
            )
            self._apply_states(installed=False, status=None)
            return
        self.query_one("#journey-hint", Static).update(self._journey_hint())
        self._probe_permissions()
        self._refresh_status()
        self.set_interval(_REFRESH_SECONDS, self._refresh_status)

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

    def _directory_hint(self) -> str:
        if len(self._container.instance_registry.load()) <= 1:
            return ""
        return _("Répertoire pilote : {project_root}").format(project_root=self._container.project_root)

    def _service_name(self) -> str:
        """Le nom PILOTE : celui qui est enregistre, jamais ce qui est en cours de saisie."""
        return self._current_name

    def _registered_entry_for_this_instance(self) -> InstanceEntry | None:
        current_path = self._container.filesystem.resolve_real_path(self._container.project_root)
        for entry in self._container.instance_registry.load():
            if entry.path == current_path:
                return entry
        return None

    def _unit_installed(self) -> bool:
        if self._manager is None or self._manager.manager_type() != "systemd":
            return self._manager is not None
        # Unite de CETTE installation : un fichier du meme nom qui pointe vers un autre dossier n'est pas a nous.
        name = self._service_name()
        return self._container.filesystem.exists(self._container.systemd_unit_dir / f"{name}.service") and \
            check_for_name_hijack(self._container.filesystem, self._container.systemd_unit_dir,
                                  self._container.project_root, name) is None

    def _probe_permissions(self) -> None:
        if self._manager is None or self._manager.manager_type() != "systemd" or not self._unit_installed():
            self._permissions = None
            return
        self._permissions = self._container.probe_shared_access(DEFAULT_SYSTEM_GROUP)

    def _refresh_status(self) -> None:
        if self._manager is None:
            return
        result = get_service_status(self._manager, self._service_name())
        status = result if isinstance(result, ServiceStatus) else None
        status_widget = self.query_one("#service-status", Static)
        if status is not None:
            status_widget.update(
                _("Actif : {active}   Activé au démarrage : {enabled}   État : {state} ({sub_state})\n{description}").format(active=status.active, enabled=status.enabled, state=status.state, sub_state=status.sub_state, description=status.description)
            )
        else:
            status_widget.update(cast("ManageServiceResult", result).message)
        self._apply_states(installed=self._unit_installed(), status=status)

    def _apply_states(self, *, installed: bool, status: ServiceStatus | None) -> None:
        manager_type = self._manager.manager_type() if self._manager is not None else None
        permissions_ok = self._permissions.ok if self._permissions is not None else None
        for button_id, enabled in button_states(manager_type, installed, status, permissions_ok).items():
            self.query_one(f"#{button_id}", Button).disabled = not enabled
        systemd = manager_type == "systemd"
        install_state = (_("installée") if installed else _("non installée")) if systemd else (
            _("gérée par {manager}").format(manager=manager_type.upper()) if manager_type else "-")
        if status is None:
            boot_state = control_state = "-"
        else:
            boot_state = _("activé") if status.enabled else _("désactivé")
            control_state = (_colored("$success", _("en marche")) if status.active
                             else _colored("$warning", _("arrêté")))
        if self._permissions is None:
            permissions_state = "-"
        elif not self._permissions.group_exists:
            permissions_state = _colored("$error", _("compte absent"))
        elif self._permissions.ok:
            permissions_state = _colored("$success", _("correctes"))
        else:
            permissions_state = _colored("$error", _("{count} à réparer").format(count=self._permissions.wrong_count))
        self.query_one("#state-install", Static).update(
            _colored("$success", install_state) if installed and systemd else install_state)
        self.query_one("#state-boot", Static).update(boot_state)
        self.query_one("#state-permissions", Static).update(permissions_state)
        self.query_one("#state-control", Static).update(control_state)

    def _default_python_executable(self) -> Path:
        venv_python = self._container.project_root / ".venv" / "bin" / "python"
        if self._container.filesystem.exists(venv_python):
            return venv_python
        return Path(sys.executable)

    def _unit_params(self, service_name: str) -> SystemdUnitParams:
        return SystemdUnitParams(
            service_name=service_name,
            description=_("OMEGA-SERV web server"),
            python_executable=self._default_python_executable(),
            project_root=self._container.project_root,
            config_path=self._container.config_file,
            user=DEFAULT_SYSTEM_USER,
            group=DEFAULT_SYSTEM_GROUP,
        )

    # --- nom du service : verrouille, Modifier -> Valider (2026-11-15) ---

    def _set_editing(self, editing: bool) -> None:
        self._editing = editing
        name_input = self.query_one("#service-name", Input)
        name_input.disabled = not editing
        self.query_one("#edit-name", Button).label = _("Valider") if editing else _("Modifier")
        if editing:
            name_input.focus()
        else:
            name_input.value = self._current_name

    def _name_error(self, message: str) -> None:
        self.query_one("#state-name", Static).update(_colored("$error", _("saisie refusée")))
        self.query_one("#service-message", Static).update(_colored("$error", message))
        self.app.notify(message, severity="error", timeout=10)

    def _save_name(self, name: str) -> None:
        self._current_name = name
        self._container.settings_store.set(_SERVICE_NAME_KEY, name)
        self.query_one("#state-name", Static).update("")
        self.query_one("#service-message", Static).update("")
        self._set_editing(False)
        self._probe_permissions()
        self._refresh_status()

    def _validate_name(self) -> None:
        new_name = self.query_one("#service-name", Input).value.strip()
        error = validate_service_name(new_name)
        if error is not None:
            self._name_error(error)
            return
        plan = plan_rename(self._container.filesystem, self._container.systemd_unit_dir,
                           self._container.project_root, self._current_name, new_name)
        if plan.kind == "same":
            self.query_one("#state-name", Static).update("")
            self._set_editing(False)
            return
        if plan.kind == "taken":
            self._name_error(_("Le nom {value!r} est déjà utilisé par une unité pointant vers {value2!r} (une autre "
                               "installation). Choisissez un autre nom.").format(value=new_name,
                                                                                value2=str(plan.other_directory)))
            return
        if plan.kind == "name_only":
            self._save_name(new_name)
            self.app.notify(_("Nom du service enregistré : {name}. Aucune unité de cette installation n'existait "
                              "sous l'ancien nom : rien d'autre n'a changé.").format(name=new_name))
            return
        self.app.push_screen(
            ConfirmScreen(title=_("RENOMMER LE SERVICE"), message=self._rename_message(plan)),
            lambda confirmed: self._rename_if_confirmed(plan, confirmed),
        )

    def _rename_message(self, plan: RenamePlan) -> str:
        status = get_service_status(self._manager, plan.old_name) if self._manager is not None else None
        active = isinstance(status, ServiceStatus) and status.active
        enabled = isinstance(status, ServiceStatus) and status.enabled
        steps = [
            *([_("arrêter {name}").format(name=plan.old_name)] if active else []),
            *([_("désactiver {name} au démarrage").format(name=plan.old_name)] if enabled else []),
            _("désinstaller l'unité {name}").format(name=plan.old_name),
            _("installer l'unité {name}").format(name=plan.new_name),
            *([_("activer {name} au démarrage").format(name=plan.new_name)] if enabled else []),
            *([_("démarrer {name}").format(name=plan.new_name)] if active else []),
        ]
        numbered = "\n".join(f"  {index}. {step}" for index, step in enumerate(steps, 1))
        return _("L'unité {old} de cette installation est installée. La renommer en {new} enchaîne :\n{steps}\n"
                 "Le serveur est coupé quelques secondes s'il tourne. Une authentification (sudo) sera demandée. "
                 "Continuer ?").format(old=plan.old_name, new=plan.new_name, steps=numbered)

    def _rename_if_confirmed(self, plan: RenamePlan, confirmed: bool | None) -> None:
        if not confirmed or self._manager is None:
            return
        with self._maybe_suspend():
            result = rename_installed_service(
                self._container.filesystem, self._manager, self._container.systemd_unit_dir, plan,
                self._unit_params, getpass.getuser(),
            )
        unit_dir = self._container.systemd_unit_dir
        new_exists = self._container.filesystem.exists(unit_dir / f"{plan.new_name}.service")
        old_exists = self._container.filesystem.exists(unit_dir / f"{plan.old_name}.service")
        # Le nom pilote suit l'unite qui existe vraiment : jamais un nom sans unite quand l'autre en a une.
        self._save_name(plan.new_name if result.success or new_exists or not old_exists else plan.old_name)
        done = "\n".join(f"  - {step}" for step in result.steps)
        self.app.notify("\n".join((result.message, done)) if done else result.message,  # noqa: FLY002 - i18n
                        severity="information" if result.success else "error", timeout=15)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id
        if button_id == "back":
            self.dismiss()
            return
        if button_id == "edit-name":
            if self._editing:
                self._validate_name()
            else:
                self._set_editing(True)
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
        self._probe_permissions()
        self._refresh_status()

    def _install_if_confirmed(self, confirmed: bool | None) -> None:
        if not confirmed or self._manager is None:
            return
        service_name = self._service_name()
        params = self._unit_params(service_name)
        unit_path = self._container.systemd_unit_dir / f"{service_name}.service"
        with self._maybe_suspend():
            result = install_systemd_service(
                self._container.filesystem, params, unit_path, self._manager,
                installing_user=getpass.getuser(),
            )
        self.app.notify(result.message, severity="information" if result.success else "error")
        self._probe_permissions()
        self._refresh_status()

    def _uninstall_if_confirmed(self, confirmed: bool | None) -> None:
        if not confirmed or self._manager is None:
            return
        unit_path = self._container.systemd_unit_dir / f"{self._service_name()}.service"
        with self._maybe_suspend():
            result = uninstall_systemd_service(self._container.filesystem, unit_path, self._manager)
        self.app.notify(result.message, severity="information" if result.success else "error")
        self._probe_permissions()
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
        self._probe_permissions()
        self._refresh_status()
