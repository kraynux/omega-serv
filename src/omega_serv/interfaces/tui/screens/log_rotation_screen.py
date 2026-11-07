"""Ecran Rotation/archivage des logs (plan interface §3.4/§8) - patron a
3 modes identique a omega-fire (interfaces/tui/screens/
rotate_logs_screen.py) : creer une sauvegarde maintenant (inconditionnel,
contrairement a la rotation automatique qui verifie d'abord le seuil de
taille), configurer une automatisation (frequence declarative - meme
bookkeeping-seul que la reference, voir infrastructure/logging/
rotation_automation_store.py) et gerer/supprimer les automatisations en
cours. Archives ecrites dans var/backups/logs/, distinct de
var/backups/ (sauvegardes de configuration, deja utilise ailleurs).

Automatisations EXECUTEES depuis le 2026-11-07 (application/logs/rotation_automation.py) : la premiere
automatisation installe une tache planifiee quotidienne (timer systemd, sinon ligne crontab, sinon
instructions), la derniere supprimee la retire. « Gérer les automatisations » montre l'etat de cette tache,
la derniere et la prochaine execution."""
from __future__ import annotations

import getpass
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Button, DataTable, Footer, Header, Select, Static

from omega_serv.application.config.load_config import load_config
from omega_serv.application.logs.rotation_automation import (
    ScheduleResult,
    install_rotation_schedule,
    remove_rotation_schedule,
    rotation_schedule_status,
    uses_systemd,
)
from omega_serv.application.services.resolve_current_service_name import (
    resolve_current_service_name,
)
from omega_serv.core.i18n import _
from omega_serv.domain.logs.rotation_schedule import next_run
from omega_serv.interfaces.tui.screens._base import OmegaScreen
from omega_serv.interfaces.tui.screens.confirm import ConfirmScreen

if TYPE_CHECKING:
    from omega_serv.bootstrap.container import DependencyContainer
    from omega_serv.ports.process_runner_port import ProcessRunnerPort
    from omega_serv.ports.service_manager_port import ServiceManagerPort

_KNOWN_LOGS: tuple[tuple[str, str], ...] = (
    (_("Access log"), "access"),
    (_("Error log"), "error"),
    (_("WAF alerts log"), "waf_alerts"),
)

_MODE_ROTATE = "rotate"
_MODE_BACKUP = "backup"
_MODE_SCHEDULE = "schedule"
_MODE_MANAGE = "manage"

_MODE_OPTIONS: tuple[tuple[str, str], ...] = (
    (_("Tourner un log si nécessaire (seuil de taille)"), _MODE_ROTATE),
    (_("Créer une sauvegarde maintenant (inconditionnel)"), _MODE_BACKUP),
    (_("Configurer une automatisation de sauvegarde"), _MODE_SCHEDULE),
    (_("Gérer les automatisations en cours"), _MODE_MANAGE),
)

_FREQ_OPTIONS: dict[str, tuple[int, str]] = {
    "weekly": (7, _("Toutes les semaines")),
    "monthly": (30, _("Tous les mois")),
    "quarterly": (90, _("Tous les trimestres")),
    "semiannual": (180, _("Tous les semestres")),
    "yearly": (364, _("Tous les ans")),
}


class LogRotationScreen(OmegaScreen):
    def __init__(self, *, container: DependencyContainer) -> None:
        super().__init__()
        self._container = container
        self._selected_automation_index: int | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(classes="omega-panel"):
            yield Static(_("ROTATION / ARCHIVAGE DES LOGS"), classes="omega-title")
            yield Static("", id="rotation-result", classes="omega-hint")

            yield Static(_("Action"), classes="omega-subtitle")
            yield Select(_MODE_OPTIONS, value=_MODE_ROTATE, allow_blank=False, id="mode-select")

            yield Static(_("Log cible"), id="log-label", classes="omega-subtitle")
            yield Select(_KNOWN_LOGS, value="access", allow_blank=False, id="log-select")

            yield Static(_("Fréquence"), id="freq-label", classes="omega-subtitle")
            yield Select(
                [(label, key) for key, (_ignored, label) in _FREQ_OPTIONS.items()],
                value="weekly", allow_blank=False, id="freq-select",
            )

            yield Static(_("Automatisations planifiées"), id="manage-label", classes="omega-subtitle")
            yield Static("", id="schedule-status", classes="omega-hint")
            yield DataTable(id="automations-table")

            with Horizontal(classes="omega-actions"):
                with Container(classes="omega-btn-frame", id="launch-frame"):
                    yield Button(_("Valider"), id="launch", variant="primary")
                with Container(classes="omega-btn-frame", id="delete-automation-frame"):
                    yield Button(_("Supprimer la sélection"), id="delete-automation", variant="error")
                with Container(classes="omega-btn-frame", id="install-schedule-frame"):
                    yield Button(_("Réinstaller l'exécution"), id="install-schedule")
                with Container(classes="omega-btn-frame"):
                    yield Button(_("Retour"), id="back")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#automations-table", DataTable)
        table.cursor_type = "row"
        table.add_columns(_("Log"), _("Fréquence"), _("Créée le"), _("Dernière exécution"), _("Prochaine"))
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
        self.query_one("#install-schedule-frame", Container).display = is_manage
        self.query_one("#schedule-status", Static).display = is_manage
        if is_manage:
            self._refresh_automations_table()

    def _refresh_automations_table(self) -> None:
        store = self._container.build_rotation_automation_store()
        table = self.query_one("#automations-table", DataTable)
        table.clear()
        automations = store.list_all()
        for idx, item in enumerate(automations):
            last = str(item.get("last_run_at") or "")[:16].replace("T", " ") or "-"
            upcoming = next_run(item)
            table.add_row(
                item.get("log_id", ""), item.get("interval_label", ""), str(item.get("created_at", ""))[:16].replace("T", " "),
                last, "-" if upcoming is None else upcoming.strftime("%Y-%m-%d"), key=str(idx),
            )
        self._selected_automation_index = None
        self._show_schedule_status(bool(automations))

    # ---- tache planifiee (2026-11-07) ----------------------------------------

    def _scheduler(self) -> tuple[ServiceManagerPort | None, ProcessRunnerPort] | None:
        runner_factory = self._container.privileged_runner_factory
        if runner_factory is None:
            return None
        factory = self._container.service_manager_factory
        return (factory() if factory is not None else None), runner_factory()

    def _service_name(self) -> str:
        return resolve_current_service_name(
            self._container.instance_registry, self._container.filesystem,
            self._container.settings_store, self._container.project_root,
        )

    def _show_schedule_status(self, has_automations: bool) -> None:
        status_widget = self.query_one("#schedule-status", Static)
        scheduler = self._scheduler()
        if scheduler is None:
            status_widget.update(_("Exécution automatique indisponible dans cet environnement."))
            return
        manager, runner = scheduler
        status = rotation_schedule_status(self._service_name(), manager, runner)
        hint = "" if status.success or not has_automations else " " + _("Utilisez « Réinstaller l'exécution ».")
        status_widget.update(status.message + hint)

    def _apply_schedule(self, install: bool) -> ScheduleResult | None:
        """Installe (ou retire) la tache planifiee ; ecran suspendu pour systemd (sudo)."""
        scheduler = self._scheduler()
        if scheduler is None:
            return None
        manager, runner = scheduler

        def work() -> ScheduleResult:
            if install:
                return install_rotation_schedule(
                    self._service_name(), self._container.project_root, sys.executable, manager,
                    self._container.systemd_unit_dir, runner, getpass.getuser(),
                )
            return remove_rotation_schedule(
                self._service_name(), manager, self._container.systemd_unit_dir, runner,
            )

        if uses_systemd(manager):
            with self._maybe_suspend():
                return work()
        return work()

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
        if button_id == "install-schedule":
            result = self._apply_schedule(install=True)
            if result is not None:
                self.query_one("#rotation-result", Static).update(result.message)
            self._refresh_automations_table()
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
            result_widget.update(_("Erreur de configuration : ") + "; ".join(load_result.errors))
            return None
        log_id = str(self.query_one("#log-select", Select).value)
        relative_path = getattr(load_result.config.logs, log_id, None)
        if relative_path is None:
            result_widget.update(_("Log inconnu : {log_id!r}").format(log_id=log_id))
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
            result_widget.update(_("La rotation est désactivée dans la configuration (logs.rotation.enabled=false)."))
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
        first = not store.list_all()
        store.add({
            "log_id": log_id,
            "days_interval": days_interval,
            "interval_label": interval_label,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        message = _("Automatisation enregistrée pour {log_id!r} ({interval_label}).").format(log_id=log_id, interval_label=interval_label)
        schedule = self._apply_schedule(install=True) if first else None
        result_widget.update(message if schedule is None else f"{message}\n{schedule.message}")

    def _delete_selected_automation(self) -> None:
        result_widget = self.query_one("#rotation-result", Static)
        if self._selected_automation_index is None:
            result_widget.update(_("Sélectionnez d'abord une ligne."))
            return
        self.app.push_screen(
            ConfirmScreen(
                title=_("SUPPRIMER L'AUTOMATISATION"),
                message=_("Supprimer définitivement cette automatisation de rotation ?"),
            ),
            self._delete_if_confirmed,
        )

    def _delete_if_confirmed(self, confirmed: bool | None) -> None:
        result_widget = self.query_one("#rotation-result", Static)
        if not confirmed or self._selected_automation_index is None:
            return
        store = self._container.build_rotation_automation_store()
        deleted = store.delete(self._selected_automation_index)
        message = _("Automatisation supprimée.") if deleted else _("Automatisation introuvable.")
        schedule = self._apply_schedule(install=False) if deleted and not store.list_all() else None
        result_widget.update(message if schedule is None or not schedule.message else f"{message}\n{schedule.message}")
        self._refresh_automations_table()
