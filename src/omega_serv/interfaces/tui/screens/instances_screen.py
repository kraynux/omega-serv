"""Ecran Instances (OMEGA-SERV_PLAN-DETAILLE_MULTI_INSTANCE.md §9
Phase B/C) - liste en lecture seule du registre global
(`~/.config/omega-serv/instances.json`) + statut systemd de chacune
(deja possible sans bascule de process, §0/§6 Niveau 1), et point
d'entree vers la creation d'une nouvelle instance (Phase C).

Un seul bouton d'entree au menu principal, jamais de fonctions
grisees individuellement (§10) - cet ecran lui-meme gere le cas "0/1
instance connue" en l'affichant simplement, sans ecran d'introduction
separe."""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, cast

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Button, DataTable, Footer, Header, Static

from omega_serv.application.instances.uninstall_instance import uninstall_instance
from omega_serv.application.services.manage_service import get_service_status
from omega_serv.domain.services.entities import ServiceStatus
from omega_serv.interfaces.tui.pending_instance_switch import PendingInstanceSwitch
from omega_serv.interfaces.tui.screens._base import OmegaScreen
from omega_serv.interfaces.tui.screens.confirm import ConfirmScreen
from omega_serv.interfaces.tui.screens.create_instance_progress_screen import (
    CreateInstanceProgressScreen,
)
from omega_serv.interfaces.tui.screens.dynamic_form_screen import DynamicFormScreen

if TYPE_CHECKING:
    from omega_serv.bootstrap.container import DependencyContainer
    from omega_serv.domain.instances.entities import InstanceEntry
    from omega_serv.interfaces.tui.app import OmegaServApp
    from omega_serv.ports.service_manager_port import ServiceManagerPort


class InstancesScreen(OmegaScreen):
    def __init__(self, *, container: DependencyContainer) -> None:
        super().__init__()
        self._container = container
        self._manager: ServiceManagerPort | None = None
        self._selected_index: int | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(classes="omega-panel"):
            yield Static("INSTANCES", classes="omega-title")
            yield Static("", id="current-instance-hint", classes="omega-hint")
            yield DataTable(id="instances-table")
            with Horizontal(classes="omega-actions"):
                with Container(classes="omega-btn-frame"):
                    yield Button("Rafraichir", id="refresh")
                with Container(classes="omega-btn-frame"):
                    yield Button("Creer une nouvelle instance", id="create", variant="primary")
                with Container(classes="omega-btn-frame"):
                    yield Button("Piloter cette instance", id="switch-to", disabled=True)
                with Container(classes="omega-btn-frame"):
                    yield Button("Desinstaller cette instance", id="uninstall-instance", variant="error", disabled=True)
                with Container(classes="omega-btn-frame"):
                    yield Button("Retour", id="back")
        yield Footer()

    def on_mount(self) -> None:
        factory = self._container.service_manager_factory
        self._manager = factory() if factory is not None else None
        table = self.query_one("#instances-table", DataTable)
        table.cursor_type = "row"
        table.add_columns("Nom", "Chemin", "Bind:Port", "Service", "Statut")
        self.query_one("#current-instance-hint", Static).update(
            f"Instance actuelle (celle qui heberge cette interface) : {self._container.project_root}"
        )
        self._refresh_table()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        self._selected_index = int(str(event.row_key.value))
        entries = self._container.instance_registry.load()
        entry = entries[self._selected_index]
        current_path = self._container.filesystem.resolve_real_path(self._container.project_root)
        is_current = entry.path == current_path
        self.query_one("#switch-to", Button).disabled = is_current
        self.query_one("#uninstall-instance", Button).disabled = is_current

    def _status_text(self, entry: InstanceEntry) -> str:
        if self._manager is None:
            return "gestionnaire indisponible"
        result = get_service_status(self._manager, entry.service_name)
        if isinstance(result, ServiceStatus):
            return "actif" if result.is_running else "arrete"
        return "unite introuvable"

    def _refresh_table(self) -> None:
        table = self.query_one("#instances-table", DataTable)
        table.clear()
        current_path = self._container.filesystem.resolve_real_path(self._container.project_root)
        for index, entry in enumerate(self._container.instance_registry.load()):
            name = f"{entry.name} (courante)" if entry.path == current_path else entry.name
            table.add_row(
                name, str(entry.path), f"{entry.bind}:{entry.port}", entry.service_name,
                self._status_text(entry), key=str(index),
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

    def _suggest_free_port(self) -> int:
        used_ports = {entry.port for entry in self._container.instance_registry.load()}
        port = 8080
        while port in used_ports:
            port += 1
        return port

    def _open_create_form(self) -> None:
        fields = [
            ("name", "Nom de l'instance (ex: test)", ""),
            ("parent_dir", "Repertoire parent (FRERE de celui-ci, jamais dedans)", str(self._container.project_root.parent)),
            ("bind", "Adresse d'ecoute (server.bind)", "127.0.0.1"),
            ("port", "Port (server.port)", str(self._suggest_free_port())),
        ]
        self.app.push_screen(
            DynamicFormScreen(title="CREER UNE INSTANCE", fields=fields), self._create_form_submitted,
        )

    def _create_form_submitted(self, values: dict[str, str] | None) -> None:
        if values is None:
            return
        name = values["name"].strip()
        if not name:
            self.app.notify("Le nom d'instance ne peut pas etre vide.", severity="error")
            return
        try:
            port = int(values["port"].strip())
        except ValueError:
            self.app.notify(f"Port invalide : {values['port']!r}", severity="error")
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
        entry = self._container.instance_registry.load()[self._selected_index]
        self.app.push_screen(
            ConfirmScreen(
                title="BASCULER VERS CETTE INSTANCE",
                message=(
                    f"L'application va s'arreter puis redemarrer, pointee sur l'instance {entry.name!r} "
                    f"({entry.path}). Continuer ?"
                ),
            ),
            lambda confirmed: self._switch_if_confirmed(confirmed, entry.name, entry.path),
        )

    def _switch_if_confirmed(self, confirmed: bool | None, target_name: str, target_path: Path) -> None:
        if not confirmed:
            return
        python_executable = target_path / ".venv" / "bin" / "python"
        if not self._container.filesystem.exists(python_executable):
            self.app.notify(
                f"Environnement virtuel introuvable pour {target_name!r} ({python_executable}) - "
                "bascule annulee.",
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
            python_executable=python_executable, source_name=current_name,
        )
        self.app.exit()

    def _open_uninstall_confirmation(self) -> None:
        assert self._selected_index is not None
        entry = self._container.instance_registry.load()[self._selected_index]
        self.app.push_screen(
            ConfirmScreen(
                title="DESINSTALLER CETTE INSTANCE",
                message=(
                    f"L'unite systemd de {entry.name!r} sera arretee et retiree (si installee), "
                    "le compte systeme dedie sera retire s'il n'est plus utilise par aucune autre "
                    f"instance, et l'entree sera retiree du registre. Le repertoire {entry.path} "
                    "sera CONSERVE sauf confirmation explicite a l'etape suivante. Continuer ?"
                ),
            ),
            lambda confirmed: self._ask_directory_deletion(confirmed, entry),
        )

    def _ask_directory_deletion(self, confirmed: bool | None, entry: InstanceEntry) -> None:
        if not confirmed:
            return
        self.app.push_screen(
            ConfirmScreen(
                title="SUPPRIMER AUSSI LE REPERTOIRE ?",
                message=(
                    f"Supprimer DEFINITIVEMENT {entry.path} (code, configuration, donnees, "
                    "journaux) ? Action IRREVERSIBLE. Repondez Annuler pour conserver le "
                    "repertoire sur disque (l'instance est quand meme retiree du service et du "
                    "registre)."
                ),
            ),
            lambda delete_directory: self._perform_uninstall(entry, bool(delete_directory)),
        )

    def _perform_uninstall(self, entry: InstanceEntry, delete_directory: bool) -> None:
        with self._maybe_suspend():
            result = uninstall_instance(
                self._container.filesystem, self._container.instance_registry, self._manager,
                self._container.systemd_unit_dir, entry=entry, delete_directory=delete_directory,
            )
        self.app.notify(result.message, severity="information" if result.success else "error", timeout=15)
        self._selected_index = None
        self.query_one("#switch-to", Button).disabled = True
        self.query_one("#uninstall-instance", Button).disabled = True
        self._refresh_table()
