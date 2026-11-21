"""Ecran Instances (OMEGA-SERV_PLAN-DETAILLE_MULTI_INSTANCE.md §9
Phase B/C) - liste en lecture seule du registre global
(`~/.config/omega-serv/instances.json`) + statut systemd de chacune
(deja possible sans bascule de process, §0/§6 Niveau 1), et point
d'entree vers la creation d'une nouvelle instance (Phase C).

Un seul bouton d'entree au menu principal, jamais de fonctions
grisees individuellement (§10) - cet ecran lui-meme gere le cas "0/1
instance connue" en l'affichant simplement, sans ecran d'introduction
separe.

L'instance courante figure toujours dans le tableau, en tete, meme si elle n'est pas dans le registre (instance
d'origine, installee avant tout « Creer ») : sinon sa configuration distante restait inaccessible (2026-11-16)."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, cast

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Button, DataTable, Footer, Header, Static

from omega_serv.application.admin_web.checks import admin_web_settings
from omega_serv.application.admin_web.local_link import LocalLinkRequest, link_local_master
from omega_serv.application.config.load_config import load_config
from omega_serv.application.instances.uninstall_instance import uninstall_instance
from omega_serv.application.services.manage_service import get_service_status
from omega_serv.application.services.resolve_current_service_name import (
    resolve_current_service_name,
)
from omega_serv.core.i18n import _
from omega_serv.domain.admin_web.master import local_admin_address
from omega_serv.domain.instances.entities import InstanceEntry
from omega_serv.domain.services.entities import ServiceStatus
from omega_serv.interfaces.tui.pending_instance_switch import OPEN_ADMIN_WEB, PendingInstanceSwitch
from omega_serv.interfaces.tui.screens._base import OmegaScreen, main_menu_title
from omega_serv.interfaces.tui.screens.admin_web_screen import AdminWebScreen
from omega_serv.interfaces.tui.screens.confirm import ConfirmScreen
from omega_serv.interfaces.tui.screens.create_instance_progress_screen import (
    CreateInstanceProgressScreen,
)
from omega_serv.interfaces.tui.screens.dynamic_form_screen import DynamicFormScreen
from omega_serv.interfaces.tui.screens.link_master_dialog import LinkMasterScreen

if TYPE_CHECKING:
    from omega_serv.bootstrap.container import DependencyContainer
    from omega_serv.domain.admin_web.settings import AdminWebSettings
    from omega_serv.interfaces.tui.app import OmegaServApp
    from omega_serv.ports.instance_command_port import InstanceCommandPort
    from omega_serv.ports.service_manager_port import ServiceManagerPort


def _create_form_error(values: dict[str, str]) -> str | None:
    """Lot V (2026-11-15) : erreurs dans le formulaire, saisie gardee (avant : notification puis tout a refaire)."""
    if not values["name"].strip():
        return _("Le nom d'instance ne peut pas être vide.")
    try:
        port = int(values["port"].strip())
    except ValueError:
        return _("Port invalide : {port!r}").format(port=values["port"])
    if not 1 <= port <= 65535:
        return _("Port invalide : {port!r}").format(port=values["port"])
    if not values["parent_dir"].strip():
        return _("Le répertoire parent ne peut pas être vide.")
    return None


class InstancesScreen(OmegaScreen):
    def __init__(self, *, container: DependencyContainer) -> None:
        super().__init__()
        self._container = container
        self._manager: ServiceManagerPort | None = None
        self._selected_index: int | None = None
        self._remote_cache: dict[Path, AdminWebSettings | None] = {}

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(classes="omega-panel omega-main-panel"):
            yield main_menu_title(_("INSTANCES"))
            yield Static("", id="current-instance-hint", classes="omega-hint")
            yield DataTable(id="instances-table")
            yield Static("", id="remote-config-hint", classes="omega-hint")
        # Trois rangees (retour utilisateur 2026-11-07 : sur une seule ligne, un petit terminal coupait les boutons).
        # Disposition decidee par l'auteur le 2026-11-16 : ligne 1 la liste (Rafraichir, Creer, Desinstaller, en
        # rouge et en dernier), ligne 2 l'instance choisie (Piloter, Configuration distante, Relier au maitre), puis
        # Retour seul. Hors de la zone qui defile (demande de l'auteur du 2026-11-15) : la liste peut grandir.
        with Vertical(classes="omega-proxy-actions"):
            with Horizontal(classes="omega-actions omega-riposte-actions"):
                with Container(classes="omega-btn-frame"):
                    yield Button(_("Rafraîchir"), id="refresh")
                with Container(classes="omega-btn-frame"):
                    yield Button(_("Créer une nouvelle instance"), id="create", variant="primary")
                with Container(classes="omega-btn-frame"):
                    yield Button(_("Désinstaller cette instance"), id="uninstall-instance", variant="error",
                                 disabled=True)
            with Horizontal(classes="omega-actions omega-riposte-actions"):
                with Container(classes="omega-btn-frame"):
                    yield Button(_("Piloter cette instance"), id="switch-to", disabled=True)
                with Container(classes="omega-btn-frame"):
                    yield Button(_("Configuration distante"), id="remote-config", disabled=True)
                with Container(classes="omega-btn-frame"):
                    yield Button(_("Relier au maître"), id="link-master", disabled=True)
            with Horizontal(classes="omega-actions omega-riposte-actions omega-service-back"), \
                    Container(classes="omega-btn-frame"):
                yield Button(_("Retour"), id="back")
        yield Footer()

    def on_mount(self) -> None:
        factory = self._container.service_manager_factory
        self._manager = factory() if factory is not None else None
        table = self.query_one("#instances-table", DataTable)
        table.cursor_type = "row"
        table.add_columns(_("Nom"), _("Chemin"), _("Bind:Port"), _("Service"), _("Statut"), _("Accès distant"))
        self.query_one("#current-instance-hint", Static).update(
            _("Instance actuelle (celle qui héberge cette interface) : {project_root}").format(project_root=self._container.project_root)
        )
        self._refresh_table()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        self._select(int(str(event.row_key.value)))

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        if event.row_key is not None and event.row_key.value is not None:
            self._select(int(str(event.row_key.value)))

    def _entries(self) -> list[InstanceEntry]:
        """Registre + instance courante en tete si elle n'y est pas (son nom = celui de son dossier)."""
        entries = self._container.instance_registry.load()
        current_path = self._container.filesystem.resolve_real_path(self._container.project_root)
        if any(entry.path == current_path for entry in entries):
            return entries
        result = load_config(self._container.configuration, self._container.config_file)
        server = result.config.server if result.success and result.config is not None else None
        current = InstanceEntry(
            name=current_path.name, path=current_path, bind=server.bind if server is not None else "-",
            port=server.port if server is not None else 0,
            service_name=resolve_current_service_name(
                self._container.instance_registry, self._container.filesystem, self._container.settings_store,
                self._container.project_root),
            created_at=datetime.fromtimestamp(0, timezone.utc))
        return [current, *entries]

    def _select(self, index: int) -> None:
        entries = self._entries()
        if not 0 <= index < len(entries):
            return
        self._selected_index = index
        entry = entries[index]
        current_path = self._container.filesystem.resolve_real_path(self._container.project_root)
        is_current = entry.path == current_path
        self.query_one("#switch-to", Button).disabled = is_current
        self.query_one("#uninstall-instance", Button).disabled = is_current
        # Bouton visible mais grise tant que l'option est inactive sur l'instance choisie, avec la raison (2026-11-15).
        remote = self._remote_access(entry)
        self.query_one("#remote-config", Button).disabled = remote is None
        link_problem = self._link_problem(entry, remote)
        # Grise aussi quand l'administration web de l'instance choisie est inactive (retour de l'auteur du 2026-11-17 :
        # le bouton restait actif et un clic ne faisait rien).
        self.query_one("#link-master", Button).disabled = remote is None or bool(link_problem)
        hint = self.query_one("#remote-config-hint", Static)
        if remote is None:
            hint.update(_("Configuration distante : activez d'abord l'option « admin_web » de {name!r} dans Voir "
                          "options actives.").format(name=entry.name))
        else:
            hint.update(link_problem)

    def _masters_for(self, follower: InstanceEntry) -> list[InstanceEntry]:
        """Maitres possibles : les autres instances de cette machine dont l'administration web est active."""
        return [entry for entry in self._entries()
                if entry.path != follower.path and self._remote_access(entry) is not None]

    def _link_problem(self, follower: InstanceEntry, remote: AdminWebSettings | None) -> str:
        """Raison pour laquelle « Relier au maître » est grise (vide : possible)."""
        if remote is None:
            return ""  # la raison « admin_web » est deja affichee
        if self._container.instance_commands is None:
            return _("Relier au maître : indisponible dans ce mode.")
        if not self._masters_for(follower):
            return _("Relier au maître : aucune autre instance de cette machine n'a l'administration web active "
                     "(elle doit l'être sur le maître).")
        return ""

    def _remote_access(self, entry: InstanceEntry) -> AdminWebSettings | None:
        """Reglages de l'administration web de cette instance, lus en lecture seule dans SA configuration ; None si
        l'option est inactive ou la configuration illisible. Lus une fois par rafraichissement du tableau : relire et
        valider chaque configuration a chaque ligne survolee figeait l'ecran (2026-11-17)."""
        if entry.path in self._remote_cache:
            return self._remote_cache[entry.path]
        settings = self._read_remote_access(entry)
        self._remote_cache[entry.path] = settings
        return settings

    def _read_remote_access(self, entry: InstanceEntry) -> AdminWebSettings | None:
        result = load_config(self._container.configuration, entry.path / "config" / "omega-serve.json")
        if not result.success or result.config is None:
            return None
        return admin_web_settings(result.config)

    def _remote_access_text(self, entry: InstanceEntry) -> str:
        settings = self._remote_access(entry)
        return _("inactif") if settings is None else _("actif (port {port})").format(port=settings.port)

    def _status_text(self, entry: InstanceEntry) -> str:
        if self._manager is None:
            return _("gestionnaire indisponible")
        result = get_service_status(self._manager, entry.service_name)
        if isinstance(result, ServiceStatus):
            return _("actif") if result.is_running else _("arrêté")
        return _("unité introuvable")

    def _refresh_table(self) -> None:
        self._remote_cache = {}
        table = self.query_one("#instances-table", DataTable)
        table.clear()
        current_path = self._container.filesystem.resolve_real_path(self._container.project_root)
        for index, entry in enumerate(self._entries()):
            name = _("{name} (courante)").format(name=entry.name) if entry.path == current_path else entry.name
            table.add_row(
                name, str(entry.path), f"{entry.bind}:{entry.port}", entry.service_name,
                self._status_text(entry), self._remote_access_text(entry), key=str(index),
            )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "back":
            self.dismiss()
        elif event.button.id == "refresh":
            self._refresh_table()
        elif event.button.id == "create":
            self._open_create_form()
        elif event.button.id == "switch-to" and self._selected_index is not None:
            self._open_switch_confirmation()
        elif event.button.id == "uninstall-instance" and self._selected_index is not None:
            self._open_uninstall_confirmation()
        elif event.button.id == "remote-config" and self._selected_index is not None:
            self._open_remote_config()
        elif event.button.id == "link-master" and self._selected_index is not None:
            self._open_link_master()

    # ------------------------------------------------------------------ Relier au maitre (2026-11-16)
    def _open_link_master(self) -> None:
        assert self._selected_index is not None
        follower = self._entries()[self._selected_index]
        masters = self._masters_for(follower)
        if not masters:
            self.app.notify(self._link_problem(follower, self._remote_access(follower)) or _(
                "Relier au maître : activez d'abord l'option « admin_web » de {name!r} dans Voir options "
                "actives.").format(name=follower.name), severity="warning", timeout=10)
            return
        current_path = self._container.filesystem.resolve_real_path(self._container.project_root)
        default = next((str(entry.path) for entry in masters if entry.path == current_path), str(masters[0].path))
        self.app.push_screen(
            LinkMasterScreen(follower=follower.name, masters=[(entry.name, str(entry.path)) for entry in masters],
                             default_master=default),
            lambda chosen: self._link_chosen(follower, chosen),
        )

    def _link_chosen(self, follower: InstanceEntry, chosen: tuple[str, str] | None,
                     replace: bool = False) -> None:
        if chosen is None:
            return
        settings = self._remote_access(follower)
        runner = self._container.instance_commands
        master = next((entry for entry in self._entries() if str(entry.path) == chosen[0]), None)
        if settings is None or runner is None or master is None:
            return
        request = LocalLinkRequest(follower.path, follower.name, local_admin_address(settings.bind), settings.port,
                                   master.path, chosen[1], replace)
        self.app.notify(_("Liaison de {name} au maître {master} en cours...").format(name=follower.name,
                                                                                   master=master.name))
        self.run_worker(self._link(runner, request, follower, chosen), exclusive=True, group="link-master")

    async def _link(self, runner: InstanceCommandPort, request: LocalLinkRequest, follower: InstanceEntry,
                    chosen: tuple[str, str]) -> None:
        outcome = await asyncio.to_thread(link_local_master, runner, request)
        if outcome.exists:
            self.app.push_screen(
                ConfirmScreen(title=_("REMPLACER LE MAÎTRE"), message=_(
                    "{reason}\n\nLe remplacer ? L'ancien maître est révoqué aussitôt : ses appels vers {name} sont "
                    "refusés.").format(reason=outcome.message, name=follower.name)),
                lambda confirmed: self._link_chosen(follower, chosen, replace=True) if confirmed else None,
            )
            return
        self.app.notify(outcome.message, severity="information" if outcome.ok else "error", timeout=15)

    def _open_remote_config(self) -> None:
        """Instance pilotee : l'ecran s'ouvre. Autre instance : on bascule d'abord sur elle, par securite, apres une
        confirmation qui donne son nom ; l'ecran s'ouvre ensuite sur elle (decision de l'auteur du 2026-11-15)."""
        assert self._selected_index is not None
        entry = self._entries()[self._selected_index]
        current_path = self._container.filesystem.resolve_real_path(self._container.project_root)
        if entry.path == current_path:
            self.app.push_screen(AdminWebScreen(container=self._container), lambda _result: self._refresh_table())
            return
        self.app.push_screen(
            ConfirmScreen(
                title=_("BASCULER VERS CETTE INSTANCE"),
                message=_("La configuration distante se règle sur l'instance pilotée. L'application va s'arrêter puis "
                          "redémarrer, pointée sur l'instance {name!r} ({path}), et ouvrira sa configuration "
                          "distante. Continuer ?").format(name=entry.name, path=entry.path),
            ),
            lambda confirmed: self._switch_if_confirmed(confirmed, entry.name, entry.path, open_after=OPEN_ADMIN_WEB),
        )

    def _suggest_free_port(self) -> int:
        used_ports = {entry.port for entry in self._entries()}
        port = 8080
        while port in used_ports:
            port += 1
        return port

    def _open_create_form(self) -> None:
        fields = [
            ("name", _("Nom de l'instance (ex: test)"), ""),
            ("parent_dir", _("Répertoire parent (FRÈRE de celui-ci, jamais dedans)"), str(self._container.project_root.parent)),
            ("bind", _("Adresse d'écoute (server.bind)"), "127.0.0.1"),
            ("port", _("Port (server.port)"), str(self._suggest_free_port())),
        ]
        self.app.push_screen(
            DynamicFormScreen(title=_("CRÉER UNE INSTANCE"), fields=fields, validate=_create_form_error),
            self._create_form_submitted,
        )

    def _create_form_submitted(self, values: dict[str, str] | None) -> None:
        if values is None:
            return
        name = values["name"].strip()
        if not name:
            self.app.notify(_("Le nom d'instance ne peut pas être vide."), severity="error")
            return
        try:
            port = int(values["port"].strip())
        except ValueError:
            self.app.notify(_("Port invalide : {port!r}").format(port=values['port']), severity="error")
            return
        bind = values["bind"].strip() or "127.0.0.1"
        parent_dir = Path(values["parent_dir"].strip())
        service_name = f"omega-serv-{name}"
        self.app.push_screen(
            CreateInstanceProgressScreen(
                container=self._container, source_root=self._container.project_root, name=name,
                target_parent_dir=parent_dir, bind=bind, port=port, service_name=service_name,
            ),
            self._on_create_finished,
        )

    def _on_create_finished(self, _result: None) -> None:
        self._refresh_table()

    def _open_switch_confirmation(self) -> None:
        assert self._selected_index is not None
        entry = self._entries()[self._selected_index]
        self.app.push_screen(
            ConfirmScreen(
                title=_("BASCULER VERS CETTE INSTANCE"),
                message=(
                    _("L'application va s'arrêter puis redémarrer, pointée sur l'instance {name!r} ({path}). Continuer ?").format(name=entry.name, path=entry.path)
                ),
            ),
            lambda confirmed: self._switch_if_confirmed(confirmed, entry.name, entry.path),
        )

    def _switch_if_confirmed(self, confirmed: bool | None, target_name: str, target_path: Path,
                             open_after: str = "") -> None:
        if not confirmed:
            return
        python_executable = target_path / ".venv" / "bin" / "python"
        if not self._container.filesystem.exists(python_executable):
            self.app.notify(
                _("Environnement virtuel introuvable pour {target_name!r} ({python_executable}) - bascule annulée.").format(target_name=target_name, python_executable=python_executable),
                severity="error",
                timeout=10,
            )
            return
        current_path = self._container.filesystem.resolve_real_path(self._container.project_root)
        current_name = current_path.name
        for entry in self._container.instance_registry.load():
            if entry.path == current_path:
                current_name = entry.name
                break
        cast("OmegaServApp", self.app).pending_switch = PendingInstanceSwitch(
            python_executable=python_executable, source_name=current_name, open_after=open_after,
        )
        self.app.exit()

    def _open_uninstall_confirmation(self) -> None:
        assert self._selected_index is not None
        entry = self._entries()[self._selected_index]
        self.app.push_screen(
            ConfirmScreen(
                title=_("DÉSINSTALLER CETTE INSTANCE"),
                message=(
                    _("L'unité systemd de {name!r} sera arrêtée et retirée (si installée), le compte système dédié sera retiré s'il n'est plus utilisé par aucune autre instance, et l'entrée sera retirée du registre. Le répertoire {path} sera CONSERVÉ sauf confirmation explicite à l'étape suivante. Continuer ?").format(name=entry.name, path=entry.path)
                ),
            ),
            lambda confirmed: self._ask_directory_deletion(confirmed, entry),
        )

    def _ask_directory_deletion(self, confirmed: bool | None, entry: InstanceEntry) -> None:
        if not confirmed:
            return
        self.app.push_screen(
            ConfirmScreen(
                title=_("SUPPRIMER AUSSI LE RÉPERTOIRE ?"),
                message=(
                    _("Supprimer DÉFINITIVEMENT {path} (code, configuration, données, journaux) ? Action IRRÉVERSIBLE. Répondez Annuler pour conserver le répertoire sur disque (l'instance est quand même retirée du service et du registre).").format(path=entry.path)
                ),
            ),
            lambda delete_directory: self._perform_uninstall(entry, bool(delete_directory)),
        )

    def _perform_uninstall(self, entry: InstanceEntry, delete_directory: bool) -> None:
        with self._maybe_suspend():
            result = uninstall_instance(
                self._container.filesystem, self._container.instance_registry, self._manager,
                self._container.systemd_unit_dir, entry=entry, delete_directory=delete_directory,
                current_path=self._container.project_root,
            )
        self.app.notify(result.message, severity="information" if result.success else "error", timeout=15)
        self._selected_index = None
        self.query_one("#switch-to", Button).disabled = True
        self.query_one("#uninstall-instance", Button).disabled = True
        self.query_one("#remote-config", Button).disabled = True
        self.query_one("#link-master", Button).disabled = True
        self._refresh_table()
