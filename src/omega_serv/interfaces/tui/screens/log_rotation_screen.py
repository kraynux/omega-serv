"""Ecran Rotation/archivage des logs (plan interface §3.4/§8) - patron a
3 modes identique a omega-fire (interfaces/tui/screens/
rotate_logs_screen.py) : creer une sauvegarde maintenant (inconditionnel,
contrairement a la rotation automatique qui verifie d'abord le seuil de
taille), configurer une automatisation (frequence declarative - meme
bookkeeping-seul que la reference, voir infrastructure/logging/
rotation_automation_store.py) et gerer/supprimer les automatisations en
cours. Archives ecrites dans var/backups/logs/, distinct de
var/backups/ (sauvegardes de configuration, deja utilise ailleurs)."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Button, DataTable, Footer, Header, Select, Static

from omega_serv.application.config.load_config import load_config
from omega_serv.interfaces.tui.screens._base import OmegaScreen
from omega_serv.interfaces.tui.screens.confirm import ConfirmScreen

if TYPE_CHECKING:
    from omega_serv.bootstrap.container import DependencyContainer

_KNOWN_LOGS: tuple[tuple[str, str], ...] = (
    ("Access log", "access"),
    ("Error log", "error"),
    ("WAF alerts log", "waf_alerts"),
)

_MODE_ROTATE = "rotate"
_MODE_BACKUP = "backup"
_MODE_SCHEDULE = "schedule"
_MODE_MANAGE = "manage"

_MODE_OPTIONS: tuple[tuple[str, str], ...] = (
    ("Tourner un log si necessaire (seuil de taille)", _MODE_ROTATE),
    ("Creer une sauvegarde maintenant (inconditionnel)", _MODE_BACKUP),
    ("Configurer une automatisation de sauvegarde", _MODE_SCHEDULE),
    ("Gerer les automatisations en cours", _MODE_MANAGE),
)

_FREQ_OPTIONS: dict[str, tuple[int, str]] = {
    "weekly": (7, "Toutes les semaines"),
    "monthly": (30, "Tous les mois"),
    "quarterly": (90, "Tous les trimestres"),
    "semiannual": (180, "Tous les semestres"),
    "yearly": (364, "Tous les ans"),
}


class LogRotationScreen(OmegaScreen):
    def __init__(self, *, container: DependencyContainer) -> None:
        super().__init__()
        self._container = container
        self._selected_automation_index: int | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(classes="omega-panel"):
            yield Static("ROTATION / ARCHIVAGE DES LOGS", classes="omega-title")
            yield Static("", id="rotation-result", classes="omega-hint")

            yield Static("Action", classes="omega-subtitle")
            yield Select(_MODE_OPTIONS, value=_MODE_ROTATE, id="mode-select")

            yield Static("Log cible", id="log-label", classes="omega-subtitle")
            yield Select(_KNOWN_LOGS, value="access", id="log-select")

            yield Static("Frequence", id="freq-label", classes="omega-subtitle")
            yield Select(
                [(label, key) for key, (_, label) in _FREQ_OPTIONS.items()],
                value="weekly", id="freq-select",
            )

            yield Static("Automatisations planifiees", id="manage-label", classes="omega-subtitle")
            yield DataTable(id="automations-table")

            with Horizontal(classes="omega-actions"):
                with Container(classes="omega-btn-frame", id="launch-frame"):
                    yield Button("Valider", id="launch", variant="primary")
                with Container(classes="omega-btn-frame", id="delete-automation-frame"):
                    yield Button("Supprimer la selection", id="delete-automation", variant="error")
                with Container(classes="omega-btn-frame"):
                    yield Button("Retour", id="back")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#automations-table", DataTable)
        table.cursor_type = "row"
        table.add_columns("Log", "Frequence", "Creee le")
        self._apply_mode(_MODE_ROTATE)

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id == "mode-select":
            self._apply_mode(str(event.value))

    def _apply_mode(self, mode: str) -> None:
        is_manage = mode == _MODE_MANAGE
        is_schedule = mode == _MODE_SCHEDULE
        log_relevant = mode in (_MODE_ROTATE, _MODE_BACKUP, _MODE_SCHEDULE)

        self.query_one("#log-label", Static).display = log_relevant
        self.query_one("#log-select", Select).display = log_relevant
        self.query_one("#freq-label", Static).display = is_schedule
        self.query_one("#freq-select", Select).display = is_schedule
        self.query_one("#manage-label", Static).display = is_manage
        self.query_one("#automations-table", DataTable).display = is_manage
        self.query_one("#launch-frame", Container).display = not is_manage
        self.query_one("#delete-automation-frame", Container).display = is_manage
        if is_manage:
            self._refresh_automations_table()

    def _refresh_automations_table(self) -> None:
        store = self._container.build_rotation_automation_store()
        table = self.query_one("#automations-table", DataTable)
        table.clear()
        for idx, item in enumerate(store.list_all()):
            table.add_row(
                item.get("log_id", ""), item.get("interval_label", ""), item.get("created_at", ""), key=str(idx),
            )
        self._selected_automation_index = None

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        self._selected_automation_index = int(str(event.row_key.value))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id
        if button_id == "back":
            self.dismiss()
            return
        if button_id == "delete-automation":
            self._delete_selected_automation()
            return
        if button_id != "launch":
            return

        mode = str(self.query_one("#mode-select", Select).value)
        if mode == _MODE_ROTATE:
            self._rotate()
        elif mode == _MODE_BACKUP:
            self._backup_now()
        elif mode == _MODE_SCHEDULE:
            self._configure_schedule()

    def _archive_base_dir(self) -> Path:
        return self._container.project_root / "var" / "backups" / "logs"

    def _resolve_log_path(self, result_widget: Static) -> tuple[str, Path] | None:
        load_result = load_config(self._container.configuration, self._container.config_file)
        if not load_result.success or load_result.config is None:
            result_widget.update("Erreur de configuration : " + "; ".join(load_result.errors))
            return None
        log_id = str(self.query_one("#log-select", Select).value)
        relative_path = getattr(load_result.config.logs, log_id, None)
        if relative_path is None:
            result_widget.update(f"Log inconnu : {log_id!r}")
            return None
        return log_id, self._container.project_root / relative_path

    def _rotate(self) -> None:
        result_widget = self.query_one("#rotation-result", Static)
        resolved = self._resolve_log_path(result_widget)
        if resolved is None:
            return
        _log_id, log_path = resolved

        load_result = load_config(self._container.configuration, self._container.config_file)
        assert load_result.config is not None
        rotation = load_result.config.logs.rotation
        if not rotation.enabled:
            result_widget.update("La rotation est desactivee dans la configuration (logs.rotation.enabled=false).")
            return

        result = self._container.rotate_log_if_needed(log_path, rotation.max_bytes, rotation.keep, self._archive_base_dir())
        result_widget.update(result.message)

    def _backup_now(self) -> None:
        result_widget = self.query_one("#rotation-result", Static)
        resolved = self._resolve_log_path(result_widget)
        if resolved is None:
            return
        _log_id, log_path = resolved

        load_result = load_config(self._container.configuration, self._container.config_file)
        assert load_result.config is not None
        keep = load_result.config.logs.rotation.keep
        result = self._container.rotate_log_if_needed(log_path, 0, keep, self._archive_base_dir())
        result_widget.update(result.message)

    def _configure_schedule(self) -> None:
        result_widget = self.query_one("#rotation-result", Static)
        resolved = self._resolve_log_path(result_widget)
        if resolved is None:
            return
        log_id, _log_path = resolved

        freq_key = str(self.query_one("#freq-select", Select).value)
        days_interval, interval_label = _FREQ_OPTIONS[freq_key]

        store = self._container.build_rotation_automation_store()
        store.add({
            "log_id": log_id,
            "days_interval": days_interval,
            "interval_label": interval_label,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        result_widget.update(f"Automatisation enregistree pour {log_id!r} ({interval_label}).")

    def _delete_selected_automation(self) -> None:
        result_widget = self.query_one("#rotation-result", Static)
        if self._selected_automation_index is None:
            result_widget.update("Selectionnez d'abord une ligne.")
            return
        self.app.push_screen(
            ConfirmScreen(
                title="SUPPRIMER L'AUTOMATISATION",
                message="Supprimer definitivement cette automatisation de rotation ?",
            ),
            self._delete_if_confirmed,
        )

    def _delete_if_confirmed(self, confirmed: bool | None) -> None:
        result_widget = self.query_one("#rotation-result", Static)
        if not confirmed or self._selected_automation_index is None:
            return
        store = self._container.build_rotation_automation_store()
        deleted = store.delete(self._selected_automation_index)
        result_widget.update("Automatisation supprimee." if deleted else "Automatisation introuvable.")
        self._refresh_automations_table()
