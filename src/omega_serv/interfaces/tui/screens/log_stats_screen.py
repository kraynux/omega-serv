"""Ecran Statistiques (Gestion des logs, colonne BIBLIOTHEQUE) - porte d'omega-log le 2026-11-07
(OMEGA-SERV_A_FAIRE_STATS_DEPUIS_OMEGA_LOG.md, lot 3), retour utilisateur : « le statistiques est tres
bien, spinner, message d'attente, export complet, visuel ». Remplace l'ancien ecran limite a l'access log
(plus relie a aucun menu depuis le 2026-10-15, copie dans ~/DEV/SERV/sauvegardes/).

N'importe quel(s) log(s) de la Bibliotheque, periode 24h/7j/30j/« Tout (fichier entier) » : synthese,
statuts HTTP en jauges, top IP, chemins demandes et en 404, repartition horaire, tendance par jour. Export
JSON (donnees) et HTML (5 themes, langue des exports).

Calcul dans le pool de PROCESSUS (`_parallel_compute.py`, un gros fichier decoupe en morceaux) : un thread
se disputerait le GIL avec l'interface. Garde `_computing` : un seul calcul a la fois. Toute mise a jour
apres un `await` rattrape NoMatches (l'utilisateur a pu quitter l'ecran). Jamais de sudo : un log illisible
est signale avec son chemin."""
from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from omega_lib.theme.policies import DEFAULT_EXPORT_THEME, EXPORT_PALETTES
from rich.cells import cell_len
from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, VerticalScroll
from textual.css.query import NoMatches
from textual.widgets import Button, DataTable, Footer, Header, Input, Select, Static

from omega_serv.application.logs.library import list_library
from omega_serv.application.logs.stats_presentation import (
    format_bytes,
    period_label,
    stats_export_payload,
)
from omega_serv.core.i18n import _
from omega_serv.domain.logs.exceptions import LogPermissionError
from omega_serv.domain.logs.library import LogFile
from omega_serv.domain.logs.stats_accumulator import StatsAccumulator
from omega_serv.domain.logs.stats_report import RankedItem, StatsReport
from omega_serv.interfaces.tui.screens._base import OmegaScreen
from omega_serv.interfaces.tui.screens._elevation import request_elevation
from omega_serv.interfaces.tui.screens._export_worker import run_html_export
from omega_serv.interfaces.tui.screens._parallel_compute import accumulate_in_pool
from omega_serv.interfaces.tui.widgets.busy_indicator import (
    PERIOD_BUTTON_LABELS,
    PERIOD_HINT,
    BusyIndicator,
    describe_selection,
)
from omega_serv.interfaces.tui.widgets.gauges import append_gauge_line
from omega_serv.interfaces.tui.widgets.log_library_table import (
    SELECTION_HINT,
    LogLibraryTable,
    selection_or_cursor,
    toggle_selection_number,
)

if TYPE_CHECKING:
    from omega_serv.bootstrap.container import DependencyContainer
    from omega_serv.ports.process_runner_port import ProcessRunnerPort

_PERIODS: tuple[tuple[str, str | None], ...] = (
    ("24h", "24h"), ("7j", "7d"), ("30j", "30d"), ("Tout", None),
)
_BAR_WIDTH = 40
_LABEL_WIDTH = 39
"""Largeur maximale des libelles des classements (ajustee au plus long) : une IPv6 complete (39
caracteres) tient sans coupure."""


def _export_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")


class LogStatsScreen(OmegaScreen):
    def __init__(self, *, container: DependencyContainer) -> None:
        super().__init__()
        self._container = container
        self._entries: list[LogFile] = []
        self._sources: list[str] = []
        self._period: str | None = None
        self._report: StatsReport | None = None
        self._computing = False
        self._runner: ProcessRunnerPort | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll(classes="omega-panel"):
            yield Static(_("STATISTIQUES"), classes="omega-title")
            yield LogLibraryTable(id="library-table")
            yield Static(_("Logs à analyser (numéros ci-dessus, séparés par des virgules)"), classes="omega-subtitle")
            yield Input(placeholder=_("ex: 1,2"), id="selection-input")
            yield Static(_(SELECTION_HINT), classes="omega-hint")
            with Horizontal(classes="omega-actions"):
                for period_id, _period in _PERIODS:
                    with Container(classes="omega-btn-frame"):
                        yield Button(_(PERIOD_BUTTON_LABELS[period_id]), id=f"period-{period_id}")
            yield Static(PERIOD_HINT, classes="omega-hint")
            yield Static("", id="selection-size", classes="omega-hint")
            yield BusyIndicator(id="busy")
            yield Static("", id="stats-error", classes="omega-hint")

            yield Static("", id="stats-summary")
            yield Static("", id="stats-hourly")

            yield Static(_("Thème d'export HTML"), classes="omega-subtitle")
            yield Select([(name, name) for name in EXPORT_PALETTES], value=DEFAULT_EXPORT_THEME, allow_blank=False,
                         id="theme-select")
            with Horizontal(classes="omega-actions"):
                with Container(classes="omega-btn-frame"):
                    yield Button(_("Exporter JSON"), id="export-json")
                with Container(classes="omega-btn-frame"):
                    yield Button(_("Exporter HTML"), id="export-html")
                with Container(classes="omega-btn-frame"):
                    yield Button(_("Retour"), id="back")
        yield Footer()

    def on_mount(self) -> None:
        self._entries = list_library(self._container.build_log_library_repository())
        self.query_one("#library-table", LogLibraryTable).load(self._entries)

    # ---- selection ---------------------------------------------------------

    def _raw_selection(self) -> str:
        table = self.query_one("#library-table", LogLibraryTable)
        return selection_or_cursor(self.query_one("#selection-input", Input).value, table.cursor_row,
                                   len(self._entries))

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "selection-input":
            self._refresh_selection_size()

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        if event.data_table.id == "library-table":
            self._refresh_selection_size()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        if event.data_table.id == "library-table":
            field = self.query_one("#selection-input", Input)
            field.value = toggle_selection_number(field.value, event.cursor_row + 1)

    def _refresh_selection_size(self) -> None:
        """Taille et nombre de lignes estime de la selection, affiches AVANT le calcul."""
        tokens = [token.strip() for token in self._raw_selection().split(",") if token.strip()]
        paths = [self._entries[int(t) - 1].path for t in tokens if t.isdigit() and 1 <= int(t) <= len(self._entries)]
        description = describe_selection(paths)
        self.query_one("#selection-size", Static).update(
            _("Sélection : {description}").format(description=description) if description else "")

    def _selected_paths(self) -> list[str] | None:
        error_widget = self.query_one("#stats-error", Static)
        raw = self._raw_selection()
        if not raw:
            error_widget.update(_("Saisissez au moins un numéro de ligne."))
            return None
        paths: list[str] = []
        for token in raw.split(","):
            token = token.strip()
            if not token.isdigit() or not (1 <= int(token) <= len(self._entries)):
                error_widget.update(_("Numéro invalide : {token!r}.").format(token=token))
                return None
            paths.append(self._entries[int(token) - 1].path)
        error_widget.update("")
        return paths

    # ---- calcul ------------------------------------------------------------

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id or ""
        if button_id == "back":
            self.dismiss()
        elif button_id.startswith("period-"):
            self._compute(dict(_PERIODS)[button_id.removeprefix("period-")])
        elif button_id == "export-json":
            self._export_json()
        elif button_id == "export-html":
            self._export_html()

    def _compute(self, period: str | None) -> None:
        if self._computing:
            self.app.notify(_("Un calcul est déjà en cours, patientez."), severity="warning")
            return
        paths = self._selected_paths()
        if paths is None:
            return
        self._computing = True
        self._set_period_buttons_disabled(True)
        self.query_one("#stats-summary", Static).update("")
        self.query_one("#stats-hourly", Static).update("")
        self.query_one("#busy", BusyIndicator).start(paths, period)
        self.run_worker(self._compute_async(paths, period))

    def _set_period_buttons_disabled(self, disabled: bool) -> None:
        try:
            for period_id, _period in _PERIODS:
                self.query_one(f"#period-{period_id}", Button).disabled = disabled
        except NoMatches:
            pass  # ecran deja ferme (utilisateur reparti avant la fin du calcul) - rien a mettre a jour

    async def _compute_async(self, paths: list[str], period: str | None) -> None:
        try:
            accumulator = await self._accumulate(paths, period)
        except LogPermissionError as exc:
            self._show_compute_error(_("log illisible par votre compte : {path}").format(path=exc.path))
            return
        except Exception as exc:  # noqa: BLE001 - jamais planter l'interface pour un calcul de stats
            self._show_compute_error(str(exc))
            return
        self._apply_result(paths, period, accumulator.to_report())

    async def _accumulate(self, paths: list[str], period: str | None) -> StatsAccumulator:
        """Un log illisible par votre compte : authentification sudo demandee (une fois par ecran, de
        nouveau si elle a expire), puis le calcul reprend en le lisant avec sudo. Refus : LogPermissionError."""
        try:
            return await accumulate_in_pool(paths, period, self._show_progress, self._runner)
        except LogPermissionError:
            runner = request_elevation(self, self._container)
            if runner is None:
                raise
            self._runner = runner
            return await accumulate_in_pool(paths, period, self._show_progress, runner)

    def _show_progress(self, done_bytes: int, total_bytes: int, done_parts: int, total_parts: int) -> None:
        try:
            self.query_one("#busy", BusyIndicator).set_progress(done_bytes, total_bytes, done_parts, total_parts)
        except NoMatches:
            pass  # ecran deja ferme

    def _finish_computing(self) -> None:
        """A appeler sur TOUTE sortie de `_compute_async` (succes ou erreur), sinon les boutons de periode
        resteraient desactives."""
        self._computing = False
        self._set_period_buttons_disabled(False)
        try:
            self.query_one("#busy", BusyIndicator).stop()
        except NoMatches:
            pass  # ecran deja ferme

    def _show_compute_error(self, message: str) -> None:
        self._finish_computing()
        self.app.notify(_("Erreur de calcul : {message}").format(message=message), severity="error")
        try:
            self.query_one("#stats-summary", Static).update(_("Erreur de calcul : {message}").format(message=message))
        except NoMatches:
            pass  # ecran deja ferme

    def _apply_result(self, paths: list[str], period: str | None, report: StatsReport) -> None:
        self._finish_computing()
        self._sources, self._period, self._report = paths, period, report
        try:
            summary_widget = self.query_one("#stats-summary", Static)
            hourly_widget = self.query_one("#stats-hourly", Static)
        except NoMatches:
            return  # ecran deja ferme (utilisateur reparti avant la fin du calcul) - rien a mettre a jour
        colors = self._colors()
        summary_widget.update(self._summary_text(report, period, len(paths), colors))
        hourly_widget.update(self._time_text(report, colors))

    # ---- rendu -------------------------------------------------------------

    def _colors(self) -> dict[str, str]:
        variables = self.app.get_css_variables()
        return {
            "heading": f"bold {variables.get('secondary', '')}".strip(),
            "bar": variables.get("accent", "cyan") or "cyan",
            "peak": variables.get("error", "red") or "red",
            "good": variables.get("success", "green") or "green",
            "warn": variables.get("warning", "yellow") or "yellow",
            "bad": variables.get("error", "red") or "red",
            "info": variables.get("secondary", "cyan") or "cyan",
        }

    def _summary_text(self, report: StatsReport, period: str | None, log_count: int, colors: dict[str, str]) -> Text:
        """Synthese, statuts HTTP et classements (presentation du rapport d'omega-fire)."""
        content = Text()
        content.append(_("── SYNTHÈSE — {period_label}, {log_count} log(s) ──\n").format(
            period_label=period_label(period), log_count=log_count), style=colors["heading"])
        if report.total == 0:
            content.append(_(" Aucune ligne sur cette période.\n"))
            return content
        rate_style = colors["good"] if report.error_rate < 5 else (colors["warn"] if report.error_rate < 15 else colors["bad"])
        volume = "-" if report.bytes_total is None else format_bytes(report.bytes_total)
        covered = "-" if report.first_day is None else f"{report.first_day} → {report.last_day}"
        content.append(_(" Lignes analysées   : {total}\n").format(total=report.total))
        content.append(_(" Requêtes HTTP      : {http_total}\n").format(http_total=report.http_total))
        content.append(_(" IPs uniques        : {unique_ips}\n").format(unique_ips=report.unique_ips))
        content.append(_(" Taux d'erreur      : {error_rate:.1f} %\n").format(error_rate=report.error_rate), style=rate_style)
        content.append(_(" Volume transféré   : {volume}\n").format(volume=volume))
        content.append(_(" Heure de pointe    : {peak_hour:02d}h ({peak_count} lignes)\n").format(
            peak_hour=report.peak_hour, peak_count=report.peak_count), style=colors["info"])
        content.append(_(" Période couverte   : {covered}\n\n").format(covered=covered))

        if report.statuses:
            content.append(_("── STATUTS HTTP ──\n"), style=colors["heading"])
            status_styles = {"2xx": colors["good"], "3xx": colors["info"], "4xx": colors["warn"], "5xx": colors["bad"],
                             "403": colors["warn"], "429": colors["warn"]}
            labels = {name: _("Refus {name}").format(name=name) if name in ("403", "429") else name
                      for name in report.statuses}
            # Largeur du plus long libelle (« Abgewiesen 403 » en allemand), jamais coupe a 10 colonnes.
            label_width = min(_LABEL_WIDTH, max(10, *(cell_len(label) for label in labels.values())))
            for name, count in report.statuses.items():
                share = count / report.http_total * 100 if report.http_total else 0
                append_gauge_line(content, labels[name], count, report.http_total, label_width=label_width,
                                  bar_width=_BAR_WIDTH, style=status_styles[name], suffix=f"  {share:5.1f} %")
            content.append("\n")

        self._append_ranking(content, _("TOP IP"), report.top_ips, colors["bar"], colors)
        if report.top_paths:
            self._append_ranking(content, _("CHEMINS DEMANDÉS"), report.top_paths, colors["bar"], colors)
            self._append_ranking(content, _("CHEMINS EN 404"), report.top_not_found, colors["warn"], colors)
        return content

    def _append_ranking(self, content: Text, title: str, items: list[RankedItem], style: str,
                        colors: dict[str, str]) -> None:
        content.append(f"── {title} ──\n", style=colors["heading"])
        if not items:
            content.append("  " + _("(aucun)") + "\n\n", style="dim")
            return
        maximum = items[0].count
        label_width = min(_LABEL_WIDTH, max(cell_len(item.value) for item in items))
        for item in items:
            suffix = "  " + _("dont {errors} en erreur").format(errors=item.errors) if item.errors else ""
            append_gauge_line(content, item.value, item.count, maximum, label_width=label_width,
                              bar_width=_BAR_WIDTH // 2, style=style, suffix=suffix)
        content.append("\n")

    def _time_text(self, report: StatsReport, colors: dict[str, str]) -> Text:
        """Repartition horaire (24 jauges, heure de pointe en couleur d'alerte) puis tendance par jour."""
        content = Text()
        if report.total == 0:
            return content
        content.append(_("── RÉPARTITION HORAIRE (24 h) ──\n"), style=colors["heading"])
        maximum = max(report.hourly)
        for hour, count in enumerate(report.hourly):
            style = colors["peak"] if count == maximum and count > 0 else colors["bar"]
            append_gauge_line(content, f"{hour:02d}h", count, maximum, label_width=4, bar_width=_BAR_WIDTH, style=style)
        content.append("\n")
        content.append(_("── TENDANCE PAR JOUR ({count} j) ──\n").format(count=len(report.daily)), style=colors["heading"])
        maximum_day = max((count for _day, count in report.daily), default=0)
        for day, count in report.daily:
            append_gauge_line(content, day, count, maximum_day, label_width=10, bar_width=_BAR_WIDTH, style=colors["bar"])
        return content

    # ---- exports -----------------------------------------------------------

    def _exports_dir(self) -> Path:
        override = self._container.settings_store.get("exports_dir_override", "")
        return Path(override) if override else self._container.default_exports_dir

    def _payload(self) -> dict | None:
        if self._report is None:
            self.app.notify(_("Calculez d'abord les statistiques (choisissez une période)."), severity="warning")
            return None
        return stats_export_payload(self._sources, self._period, asdict(self._report))

    def _export_json(self) -> None:
        payload = self._payload()
        if payload is None:
            return
        content = json.dumps({"generated_at": datetime.now(timezone.utc).isoformat(), **payload},
                             indent=2, ensure_ascii=False, default=str)
        self._write_export(self._exports_dir() / f"log-stats-export.{_export_timestamp()}.json", content)

    def _export_html(self) -> None:
        payload = self._payload()
        if payload is None:
            return
        theme_name = str(self.query_one("#theme-select", Select).value)
        run_html_export(
            self, self._container,
            lambda: self._container.export_payload("log-stats", payload, theme_name),
            lambda content: self._write_export(
                self._exports_dir() / f"log-stats-export.{_export_timestamp()}.html", content),
            lambda reason: self.query_one("#stats-error", Static).update(reason),
        )

    def _write_export(self, export_path: Path, content: str) -> None:
        self._container.filesystem.make_directory(export_path.parent)
        self._container.filesystem.write_text(export_path, content)
        self.app.notify(_("Export écrit : {export_path}").format(export_path=export_path))
