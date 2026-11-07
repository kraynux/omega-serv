"""Ecran "Voir et traiter IP" (gestion des logs, refonte menu
2026-10-15, OMEGA-LOG_PLAN §2/§3/§7) - REMPLACE `top_ips_screen.py` :
generalise le top N a N'IMPORTE QUEL(S) log(s) de la Bibliotheque
(plus seulement l'access log fixe d'Omega-Serv), via le parseur
generique (`domain/logs/parser.py`) et `application/logs/top_ips.py`.
Le retrait d'IP (`container.remove_ip_from_log`) existait DEJA dans
Omega-Serv - corrige en meme temps pour etre generique lui aussi (voir
`infrastructure/logging/logs_maintenance.py`), jamais re-ecrit ici.

Selection des logs par NUMEROS separes par des virgules - meme
convention que `log_view_screen.py`. Periode "Tout" AJOUTEE (absente de
l'ancien ecran, qui ne proposait que 24h/7j/30j).

Indicateur d'attente et calcul en processus separes (2026-11-07, porte d'omega-log -
OMEGA-SERV_A_FAIRE_STATS_DEPUIS_OMEGA_LOG.md, lot 2) : le calcul tourne dans le pool de processus
(`_parallel_compute.py`, un gros fichier est decoupe en morceaux), l'interface reste libre et montre une
roue, des messages, le temps ecoule et une vraie barre de progression. Garde `_computing` : un seul
calcul a la fois (un morceau deja lance dans le pool ne s'annule plus, des clics rapproches satureraient
le pool). Toute mise a jour apres un `await` rattrape NoMatches : l'utilisateur a pu quitter l'ecran.

Recherche manuelle (demande utilisateur 2026-11-07) : saisir une IP, compter ses lignes dans les logs
selectionnes (fichier entier) et pouvoir la retirer, sans attendre qu'elle apparaisse dans le top."""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.css.query import NoMatches
from textual.widgets import Button, DataTable, Footer, Header, Input, Static

from omega_serv.application.logs.ip_occurrences import IpOccurrences, count_ip_occurrences
from omega_serv.application.logs.library import list_library
from omega_serv.core.i18n import _
from omega_serv.domain.logs.exceptions import LogPermissionError
from omega_serv.domain.logs.ip_match import normalize_ip
from omega_serv.domain.logs.library import LogFile
from omega_serv.domain.logs.models import TopIP
from omega_serv.domain.logs.stats_accumulator import StatsAccumulator
from omega_serv.interfaces.tui.screens._base import OmegaScreen
from omega_serv.interfaces.tui.screens._elevation import request_elevation
from omega_serv.interfaces.tui.screens._parallel_compute import accumulate_in_pool
from omega_serv.interfaces.tui.screens.confirm import ConfirmScreen
from omega_serv.interfaces.tui.widgets.busy_indicator import (
    PERIOD_BUTTON_LABELS,
    PERIOD_HINT,
    BusyIndicator,
    describe_selection,
)
from omega_serv.interfaces.tui.widgets.log_library_table import (
    SELECTION_HINT,
    selection_or_cursor,
    toggle_selection_number,
)

if TYPE_CHECKING:
    from omega_serv.bootstrap.container import DependencyContainer
    from omega_serv.ports.process_runner_port import ProcessRunnerPort

_PERIODS: tuple[tuple[str, str | None], ...] = (
    ("24h", "24h"), ("7j", "7d"), ("30j", "30d"), ("Tout", None),
)
"""(cle de PERIOD_BUTTON_LABELS = id du bouton, periode du calcul) - memes boutons que Statistiques."""


class ProcessIpScreen(OmegaScreen):
    def __init__(self, *, container: DependencyContainer) -> None:
        super().__init__()
        self._container = container
        self._entries: list[LogFile] = []
        self._current_paths: list[str] = []
        self._selected_ip: str | None = None
        self._searched_ip: str | None = None
        """IP de la derniere recherche manuelle : apres un retrait, c'est elle qu'on recompte."""
        self._computing = False
        self._runner: ProcessRunnerPort | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(classes="omega-panel"):
            yield Static(_("VOIR ET TRAITER IP"), classes="omega-title")
            yield DataTable(id="library-table")
            yield Static(_("Logs à analyser (numéros ci-dessus, séparés par des virgules)"), classes="omega-subtitle")
            yield Input(placeholder=_("ex: 1,2"), id="selection-input")
            yield Static(_(SELECTION_HINT), classes="omega-hint")
            with Horizontal(classes="omega-actions"):
                for period_id, _period in _PERIODS:
                    with Container(classes="omega-btn-frame"):
                        yield Button(_(PERIOD_BUTTON_LABELS[period_id]), id=f"period-{period_id}")
            yield Static(PERIOD_HINT, classes="omega-hint")
            yield Static("", id="selection-size", classes="omega-hint")
            yield Static(_("Ou cherchez une IP précise dans ces logs (fichier entier) :"), classes="omega-subtitle")
            with Horizontal(classes="omega-actions"):
                yield Input(placeholder=_("ex: 203.0.113.42"), id="ip-input")
                with Container(classes="omega-btn-frame"):
                    yield Button(_("Rechercher cette IP"), id="search-ip")
            yield BusyIndicator(id="busy")
            yield Static("", id="ip-error", classes="omega-hint")
            yield Static("", id="ip-search-result", classes="omega-hint")
            yield DataTable(id="top-ips-table")
            with Horizontal(classes="omega-actions"), Container(classes="omega-btn-frame"):
                yield Button(_("Retirer cette IP des logs analyses"), id="remove-ip", variant="error", disabled=True)
            with Horizontal(classes="omega-actions"), Container(classes="omega-btn-frame"):
                yield Button(_("Retour"), id="back")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#library-table", DataTable).cursor_type = "row"
        self.query_one("#library-table", DataTable).add_columns("#", _("Chemin"))
        self.query_one("#top-ips-table", DataTable).cursor_type = "row"
        self.query_one("#top-ips-table", DataTable).add_columns(_("IP"), _("Occurrences"))
        self._entries = list_library(self._container.build_log_library_repository())
        table = self.query_one("#library-table", DataTable)
        for idx, entry in enumerate(self._entries, start=1):
            table.add_row(str(idx), entry.path)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "ip-input":
            self._search_ip()

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "selection-input":
            self._refresh_selection_size()

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        if event.data_table.id == "library-table":
            self._refresh_selection_size()

    def _refresh_selection_size(self) -> None:
        """Taille et nombre de lignes estime de la selection, affiches AVANT le calcul."""
        table = self.query_one("#library-table", DataTable)
        raw = selection_or_cursor(
            self.query_one("#selection-input", Input).value, table.cursor_row, len(self._entries)
        )
        tokens = [token.strip() for token in raw.split(",") if token.strip()]
        paths = [self._entries[int(t) - 1].path for t in tokens if t.isdigit() and 1 <= int(t) <= len(self._entries)]
        description = describe_selection(paths)
        self.query_one("#selection-size", Static).update(
            _("Sélection : {description}").format(description=description) if description else "")

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        if event.data_table.id == "library-table":
            field = self.query_one("#selection-input", Input)
            field.value = toggle_selection_number(field.value, event.cursor_row + 1)
            return
        if event.data_table.id != "top-ips-table":
            return
        self._selected_ip = str(event.row_key.value)
        self.query_one("#remove-ip", Button).disabled = False

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id or ""
        if button_id == "back":
            self.dismiss()
            return
        if button_id.startswith("period-"):
            period = dict(_PERIODS)[button_id.removeprefix("period-")]
            self._compute(period)
            return
        if button_id == "search-ip":
            self._search_ip()
            return
        if button_id == "remove-ip":
            self._remove_selected_ip()

    def _selected_paths(self) -> list[str] | None:
        error_widget = self.query_one("#ip-error", Static)
        table = self.query_one("#library-table", DataTable)
        raw = selection_or_cursor(
            self.query_one("#selection-input", Input).value, table.cursor_row, len(self._entries)
        )
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

    def _compute(self, period: str | None) -> None:
        if self._computing:
            self.app.notify(_("Un calcul est déjà en cours, patientez."), severity="warning")
            return
        paths = self._selected_paths()
        if paths is None:
            return
        self._current_paths = paths
        self._searched_ip = None
        self.query_one("#ip-search-result", Static).update("")
        self._computing = True
        self._set_period_buttons_disabled(True)
        self.query_one("#busy", BusyIndicator).start(paths, period)
        self.run_worker(self._compute_async(paths, period))

    def _search_ip(self) -> None:
        if self._computing:
            self.app.notify(_("Un calcul est déjà en cours, patientez."), severity="warning")
            return
        paths = self._selected_paths()
        if paths is None:
            return
        typed = self.query_one("#ip-input", Input).value
        ip = normalize_ip(typed)
        if ip is None:
            self.query_one("#ip-error", Static).update(_("Adresse IP invalide : {value!r}.").format(value=typed.strip()))
            return
        self._run_search(ip, paths)

    def _run_search(self, ip: str, paths: list[str]) -> None:
        self._current_paths = paths
        self._searched_ip = ip
        self._computing = True
        self._set_period_buttons_disabled(True)
        self.query_one("#busy", BusyIndicator).start(paths, None)
        self.run_worker(self._search_async(ip, paths))

    async def _search_async(self, ip: str, paths: list[str]) -> None:
        try:
            results = await asyncio.to_thread(count_ip_occurrences, ip, paths)
        except LogPermissionError as exc:
            self._show_compute_error(_("log illisible par votre compte : {path}").format(path=exc.path))
            return
        except Exception as exc:  # noqa: BLE001 - jamais planter l'interface pour une recherche
            self._show_compute_error(str(exc))
            return
        self._apply_ip_search(ip, results)

    def _apply_ip_search(self, ip: str, results: list[IpOccurrences]) -> None:
        self._finish_computing()
        try:
            table = self.query_one("#top-ips-table", DataTable)
            remove_button = self.query_one("#remove-ip", Button)
            result_line = self.query_one("#ip-search-result", Static)
        except NoMatches:
            return  # ecran deja ferme
        total = sum(result.count for result in results)
        names = [Path(result.path).name for result in results]
        # Nom seul, sauf si deux logs portent le meme (deux access.log) : chemin complet
        labels = [result.path if names.count(name) > 1 else name for result, name in zip(results, names, strict=True)]
        detail = " · ".join(f"{label} : {result.count}" for label, result in zip(labels, results, strict=True))
        result_line.update(_("{ip} : {total} ligne(s) - {detail}").format(ip=ip, total=total, detail=detail))
        table.clear()
        self._selected_ip = None
        remove_button.disabled = True
        if not total:
            self.app.notify(_("{ip} est absente des log(s) sélectionné(s).").format(ip=ip))
            return
        table.add_row(ip, str(total), key=ip)
        self._selected_ip = ip
        remove_button.disabled = False

    def _set_period_buttons_disabled(self, disabled: bool) -> None:
        try:
            for period_id, _period in _PERIODS:
                self.query_one(f"#period-{period_id}", Button).disabled = disabled
            self.query_one("#search-ip", Button).disabled = disabled
        except NoMatches:
            pass  # ecran deja ferme (utilisateur reparti avant la fin du calcul) - rien a mettre a jour

    async def _compute_async(self, paths: list[str], period: str | None) -> None:
        try:
            accumulator = await self._accumulate(paths, period)
        except LogPermissionError as exc:
            self._show_compute_error(_("log illisible par votre compte : {path}").format(path=exc.path))
            return
        except Exception as exc:  # noqa: BLE001 - jamais planter l'interface pour un calcul de top IP
            self._show_compute_error(str(exc))
            return
        self._apply_top_ips(accumulator.top_ips(10))

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
            self.query_one("#ip-error", Static).update(_("Erreur : {message}").format(message=message))
        except NoMatches:
            pass  # ecran deja ferme

    def _apply_top_ips(self, top_ips: list[TopIP]) -> None:
        self._finish_computing()
        try:
            table = self.query_one("#top-ips-table", DataTable)
            remove_button = self.query_one("#remove-ip", Button)
        except NoMatches:
            return  # ecran deja ferme (utilisateur reparti avant la fin du calcul) - rien a mettre a jour
        table.clear()
        self._selected_ip = None
        remove_button.disabled = True
        for top_ip in top_ips:
            table.add_row(top_ip.ip, str(top_ip.count), key=top_ip.ip)
        if not top_ips:
            self.app.notify(_("Aucune IP trouvée dans les log(s) sélectionné(s) pour cette période."))

    def _remove_selected_ip(self) -> None:
        if self._selected_ip is None or not self._current_paths:
            return
        ip = self._selected_ip
        self.app.push_screen(
            ConfirmScreen(
                title=_("RETIRER CETTE IP ?"),
                message=_("Retirer toutes les lignes contenant {ip} de {count} fichier(s).").format(ip=ip, count=len(self._current_paths)),
            ),
            lambda confirmed: self._remove_if_confirmed(confirmed, ip),
        )

    def _remove_if_confirmed(self, confirmed: bool | None, ip: str) -> None:
        if not confirmed:
            return
        total = 0
        for path in self._current_paths:
            total += self._container.remove_ip_from_log(ip, Path(path))
        self.app.notify(_("{total} occurrence(s) de {ip} retirée(s) au total.").format(total=total, ip=ip))
        if self._searched_ip == ip:
            self._run_search(ip, list(self._current_paths))  # recherche manuelle : on recompte cette IP
        else:
            self._compute(None)
