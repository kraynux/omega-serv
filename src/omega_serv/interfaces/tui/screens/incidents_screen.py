"""Ecran Incidents - equivalent TUI de `omega-serv incidents
list/show/close/export-ioc/generate-report`. `ioc_export_runner`/
`incident_report_export_runner` sont injectes depuis `__main__.py`
(memes raisons que `waf_test_runner`/`blocklist_port_factory` : les
exporters concrets vivent sous `infrastructure/exporters/`, hors de
portee directe de `interfaces.tui`)."""
from __future__ import annotations

from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Button, DataTable, Footer, Header, Static

from omega_serv.application.active_defense.manage_incidents import close_incident
from omega_serv.application.active_defense.queries import (
    get_incident_omitted_events,
    get_incident_timeline,
    list_incidents,
    omitted_history_notice,
)
from omega_serv.core.i18n import _
from omega_serv.domain.security.active_defense.entities import IncidentFilters
from omega_serv.interfaces.tui.screens._active_defense_collaborators_cache import (
    ActiveDefenseCollaboratorsCacheMixin,
)
from omega_serv.interfaces.tui.screens._base import OmegaScreen
from omega_serv.interfaces.tui.screens.confirm import ConfirmScreen
from omega_serv.interfaces.tui.screens.dynamic_form_screen import DynamicFormScreen

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from omega_serv.application.server.start_server import ActiveDefenseCollaborators
    from omega_serv.bootstrap.container import DependencyContainer
    from omega_serv.domain.security.active_defense.entities import ExportResult, Incident


class IncidentsScreen(ActiveDefenseCollaboratorsCacheMixin, OmegaScreen):
    def __init__(self, *, container: DependencyContainer) -> None:
        super().__init__()
        self._container = container
        self._reset_active_defense_cache()
        self._selected_incident_id: str | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(classes="omega-panel"):
            yield Static(_("INCIDENTS"), classes="omega-title")
            yield Static("", id="incidents-error", classes="omega-hint")
            yield DataTable(id="incidents-table")
            yield Static("", id="incident-detail", classes="omega-hint")
            with Horizontal(classes="omega-actions"):
                with Container(classes="omega-btn-frame"):
                    yield Button(_("Fermer l'incident"), id="close-incident", variant="error", disabled=True)
                with Container(classes="omega-btn-frame"):
                    yield Button(_("Exporter IoC"), id="export-ioc", disabled=True)
                with Container(classes="omega-btn-frame"):
                    yield Button(_("Générer rapport"), id="generate-report", disabled=True)
                with Container(classes="omega-btn-frame"):
                    yield Button(_("Retour"), id="back")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#incidents-table", DataTable)
        table.cursor_type = "row"
        table.add_columns(_("Incident"), _("Source"), _("Statut"), _("Ouvert le"), _("Fermé le"))
        self._refresh()

    def _refresh(self) -> None:
        self._selected_incident_id = None
        self.query_one("#close-incident", Button).disabled = True
        self.query_one("#export-ioc", Button).disabled = True
        self.query_one("#generate-report", Button).disabled = True
        self.query_one("#incident-detail", Static).update("")
        active_defense = self._active_defense_or_none()
        table = self.query_one("#incidents-table", DataTable)
        table.clear()
        if active_defense is None:
            self.query_one("#incidents-error", Static).update(self._active_defense_error or "")
            return
        self.query_one("#incidents-error", Static).update("")
        for incident in list_incidents(active_defense.incident_repository, IncidentFilters()):
            table.add_row(
                incident.incident_id, incident.subject_id, incident.status,
                incident.opened_at.isoformat(), incident.closed_at.isoformat() if incident.closed_at else "-",
                key=incident.incident_id,
            )

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        self._selected_incident_id = str(event.row_key.value)
        self.query_one("#close-incident", Button).disabled = False
        self.query_one("#export-ioc", Button).disabled = False
        self.query_one("#generate-report", Button).disabled = False
        active_defense = self._active_defense_or_none()
        if active_defense is None:
            return
        events = get_incident_timeline(active_defense.incident_repository, self._selected_incident_id)
        lines = [_("Chronologie de {selected_incident_id} :").format(selected_incident_id=self._selected_incident_id)]
        lines += [f"  {e.occurred_at.isoformat()}  {e.kind}  {e.detail}" for e in events] or [_("  (aucun événement)")]
        omitted = get_incident_omitted_events(active_defense.incident_repository, self._selected_incident_id)
        if omitted:
            lines.append("  " + omitted_history_notice(omitted))
        self.query_one("#incident-detail", Static).update("\n".join(lines))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id
        if button_id == "back":
            self.dismiss()
            return
        if button_id == "close-incident" and self._selected_incident_id is not None:
            self.app.push_screen(
                ConfirmScreen(
                    title=_("FERMER L'INCIDENT"),
                    message=_("Confirmer la fermeture de l'incident {selected_incident_id!r} ?").format(selected_incident_id=self._selected_incident_id),
                ),
                self._close_incident,
            )
            return
        if button_id == "export-ioc" and self._selected_incident_id is not None:
            self.app.push_screen(
                DynamicFormScreen(title=_("EXPORTER LES IOC"), fields=[("format", _("Format (json/csv/stix/misp)"), "json")]),
                self._export_ioc,
            )
            return
        if button_id == "generate-report" and self._selected_incident_id is not None:
            self._generate_report()

    def _close_incident(self, confirmed: bool | None) -> None:
        if not confirmed or self._selected_incident_id is None:
            return
        active_defense = self._active_defense_or_none()
        if active_defense is None:
            return
        closed = close_incident(active_defense.incident_repository, self._container.clock, self._selected_incident_id)
        if closed is None:
            self.app.notify(_("Incident introuvable ou déjà fermé."), severity="error")
        else:
            self.app.notify(_("Incident {incident_id!r} fermé.").format(incident_id=closed.incident_id))
            self._auto_export_ioc_on_close(active_defense, closed)
        self._refresh()

    def _auto_export_ioc_on_close(self, active_defense: ActiveDefenseCollaborators, incident: Incident) -> None:
        """Plan §"Mode guerre" : "produire un export IoC a la fermeture
        de l'incident" (IoCConfig.auto_export_on_close, Phase 2, jamais
        applique avant cette Phase 4). Meme raison que le CLI : reutilise
        les runners deja injectes (`ioc_export_runner`/
        `incident_report_export_runner`, memes que le bouton manuel
        "Exporter IoC"/"Generer rapport") plutot qu'un import direct
        d'infrastructure (interdit depuis interfaces.tui)."""
        config = active_defense.config
        if not config.ioc.auto_export_on_close:
            return
        export_dir = self._container.project_root / config.storage.export_dir
        ioc_runner = self._container.ioc_export_runner
        report_runner = self._container.incident_report_export_runner
        for export_format in config.ioc.formats:
            if export_format in ("json", "csv", "stix", "misp") and ioc_runner is not None:
                result = ioc_runner(incident, export_format, export_dir, self._container.filesystem, config.ioc)
                if result is not None:
                    self.app.notify(_("Auto-export ({export_format}) : {path}").format(export_format=export_format, path=result.path))
            elif export_format == "markdown" and report_runner is not None:
                self._export_report(report_runner, incident, export_dir, _("Auto-export (markdown) : {path}"))

    def _export_ioc(self, values: dict[str, str] | None) -> None:
        if values is None or self._selected_incident_id is None:
            return
        active_defense = self._active_defense_or_none()
        runner = self._container.ioc_export_runner
        if active_defense is None or runner is None:
            return
        incident = active_defense.incident_repository.get(self._selected_incident_id)
        if incident is None:
            self.app.notify(_("Incident introuvable."), severity="error")
            return
        export_format = values["format"].strip() or "json"
        export_dir = self._container.project_root / active_defense.config.storage.export_dir
        result = runner(incident, export_format, export_dir, self._container.filesystem, active_defense.config.ioc)
        if result is None:
            self.app.notify(_("Format d'export inconnu : {export_format!r} (json, csv, stix ou misp).").format(export_format=export_format), severity="error")
            return
        self.app.notify(_("Exporté : {path}").format(path=result.path))

    def _generate_report(self) -> None:
        active_defense = self._active_defense_or_none()
        runner = self._container.incident_report_export_runner
        if active_defense is None or runner is None or self._selected_incident_id is None:
            return
        incident = active_defense.incident_repository.get(self._selected_incident_id)
        if incident is None:
            self.app.notify(_("Incident introuvable."), severity="error")
            return
        export_dir = self._container.project_root / active_defense.config.storage.export_dir
        self._export_report(runner, incident, export_dir, _("Rapport généré : {path}"))

    def _export_report(self, runner: Callable[..., ExportResult], incident: Incident, export_dir: Path, done_message: str) -> None:
        """Hors du fil de l'interface : dans une langue d'export differente de
        l'interface, le rapport est produit par un processus enfant (quelques
        secondes). S'il echoue, le rapport existe quand meme, dans la langue de
        l'interface - l'utilisateur en est prevenu."""
        language_name = self._container.export_language_name
        if language_name is not None:
            self.app.notify(_("Export en cours dans la langue « {name} »…").format(name=language_name))

        def work() -> None:
            result = runner(incident, export_dir, self._container.filesystem)
            error = self._container.last_export_error
            self.app.call_from_thread(self._report_done, done_message.format(path=result.path), error)

        self.run_worker(work, thread=True, group="report-export")

    def _report_done(self, message: str, error: str | None) -> None:
        self.app.notify(message)
        if error is not None:
            self.app.notify(
                _("Rapport écrit dans la langue de l'interface : {error}").format(error=error), severity="warning")
