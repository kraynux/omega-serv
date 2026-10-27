"""Viewer 1 (SIMPLE) - tail en direct + stats generiques (gestion des
logs, refonte menu 2026-10-15, OMEGA-LOG_PLAN §2) - ADAPTE depuis
omega-log/interfaces/tui/screens/live_tail_screen.py (lui-meme adapte
depuis omega-fire), PAS porte verbatim : la branche d'elevation sudo
ponctuelle (lecture privilegiee) est volontairement ABSENTE ici -
Omega-Serv n'a pas cette infrastructure (`infrastructure/privileged/`)
et la Bibliotheque reste a alimentation MANUELLE pour cette passe (des
logs deja lisibles par l'utilisateur courant, jamais des logs systeme
proteges necessitant une elevation - a reconsiderer si ce besoin se
confirme).

Reutilise le mecanisme de suivi incremental DEJA existant
(`container.build_live_tail_reader`/`LiveTailPort`, identique a
`log_viewer_screen.py`) - seule nouveaute : le parseur GENERIQUE
multi-format (`domain/logs/parser.py`) plutot qu'un affichage brut,
pour que les stats (IPs uniques, taux d'erreur, repartition HTTP si le
format s'y prete) soient disponibles pour N'IMPORTE QUEL log de la
Bibliotheque, pas seulement l'access log Combined d'Omega-Serv."""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.timer import Timer
from textual.widgets import Button, DataTable, Footer, Header, Static

from omega_serv.core.i18n import _
from omega_serv.domain.logs.analytics import compute_stats
from omega_serv.domain.logs.models import LogEntry
from omega_serv.domain.logs.parser import parse_log_line
from omega_serv.interfaces.tui.screens._base import OmegaScreen
from omega_serv.ports.live_tail_port import LiveTailPort

if TYPE_CHECKING:
    from omega_serv.bootstrap.container import DependencyContainer

_REFRESH_SECONDS = 2.0
_VISIBLE_ROWS = 30
_BUFFER_SIZE = 500
_INITIAL_LINES = 200


class LogSimpleViewerScreen(OmegaScreen):
    """Suit un fichier en direct, affiche les dernieres lignes parsees +
    un petit tableau de stats generique (`compute_stats`)."""

    def __init__(self, *, container: DependencyContainer, path: str) -> None:
        super().__init__()
        self._container = container
        self._path = path
        self._buffer: list[LogEntry] = []
        self._line_number = 0
        self._tail_reader: LiveTailPort | None = None
        self._timer: Timer | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(classes="omega-panel"):
            yield Static(_("VOIR LES LOGS - SIMPLE - {path}").format(path=self._path), classes="omega-title")
            with Horizontal():
                yield Static(id="stats-box", classes="omega-dash-box")
                yield DataTable(id="entries-table")
            with Horizontal(classes="omega-actions"), Container(classes="omega-btn-frame"):
                yield Button(_("Retour"), id="back")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#entries-table", DataTable).add_columns(
            _("Heure"), _("Niveau"), _("Source"), _("IP"), _("Service"), _("Code"), _("Timeout"), _("Message")
        )
        self._load_initial()
        self._render_stats()
        self._render_table()
        self._timer = self.set_interval(_REFRESH_SECONDS, self._poll)

    def _load_initial(self) -> None:
        """Lecture ponctuelle des dernieres lignes DEJA presentes au
        moment de l'ouverture - le lecteur incremental construit ensuite
        dans `_poll()` ne voit, lui, que les lignes ecrites APRES."""
        path = Path(self._path)
        if not path.is_file():
            return
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return
        for line in text.splitlines()[-_INITIAL_LINES:]:
            self._line_number += 1
            entry = parse_log_line(line, line_number=self._line_number, log_path=self._path)
            if entry is not None:
                self._buffer.append(entry)
        self._tail_reader = self._container.build_live_tail_reader(path)

    def action_back(self) -> None:
        self._stop()
        self.dismiss()

    def _stop(self) -> None:
        if self._timer is not None:
            self._timer.stop()
            self._timer = None

    def on_unmount(self) -> None:
        self._stop()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "back":
            self.action_back()

    def _poll(self) -> None:
        if self._tail_reader is None:
            return
        try:
            new_lines = self._tail_reader.read_new_lines()
        except OSError as exc:
            self.app.notify(_("Suivi interrompu : {exc}").format(exc=exc), severity="error")
            self._stop()
            return

        for line in new_lines:
            self._line_number += 1
            entry = parse_log_line(line, line_number=self._line_number, log_path=self._path)
            if entry is not None:
                self._buffer.append(entry)
        if len(self._buffer) > _BUFFER_SIZE:
            self._buffer = self._buffer[-_BUFFER_SIZE:]

        self._render_stats()
        self._render_table()

    def _render_stats(self) -> None:
        stats = compute_stats(self._buffer, top_n=5)
        content = Text()
        content.append(_("-- APERÇU --------------\n"), style="bold")
        content.append(_(" Lignes tampon : {count}\n").format(count=len(self._buffer)))
        content.append(_(" IPs uniques   : {unique_ips}\n").format(unique_ips=stats.unique_ips))
        content.append(_(" Taux d'erreur : {value:.1f}%\n\n").format(value=stats.error_rate()))

        statuses = [e.http_status for e in self._buffer if e.http_status is not None]
        if statuses:
            # N'apparait que si au moins une ligne du tampon est reconnue comme
            # un access log Combined/Common - jamais affiche (vide/inutile) pour
            # un tampon auth.log/syslog/....
            content.append(_("-- STATUTS HTTP ---------\n"), style="bold")
            s2xx = sum(1 for s in statuses if 200 <= s < 300)
            s3xx = sum(1 for s in statuses if 300 <= s < 400)
            s4xx = sum(1 for s in statuses if 400 <= s < 500)
            s5xx = sum(1 for s in statuses if 500 <= s < 600)
            content.append(_(" 2xx succès    : {s2xx}\n").format(s2xx=s2xx), style="green")
            content.append(_(" 3xx redirect  : {s3xx}\n").format(s3xx=s3xx), style="cyan")
            content.append(_(" 4xx client    : {s4xx}\n").format(s4xx=s4xx), style="yellow")
            content.append(_(" 5xx serveur   : {s5xx}\n\n").format(s5xx=s5xx), style="red")

        content.append(_("-- TOP IP ---------------\n"), style="bold")
        for top_ip in stats.top_ips[:5]:
            content.append(f" {top_ip.ip:<15} {top_ip.count}\n")
        self.query_one("#stats-box", Static).update(content)

    def _render_table(self) -> None:
        table = self.query_one("#entries-table", DataTable)
        table.clear()
        for entry in self._buffer[-_VISIBLE_ROWS:]:
            level_style = {"error": "red", "critical": "bold red", "warning": "yellow"}.get(entry.level.value, "")

            if entry.http_status is None:
                code_cell: Text | str = "-"
            else:
                status = entry.http_status
                if 200 <= status < 300:
                    status_style = "green"
                elif 300 <= status < 400:
                    status_style = "cyan"
                elif 400 <= status < 500:
                    status_style = "yellow"
                else:
                    status_style = "red"
                code_cell = Text(str(status), style=status_style)

            if entry.latency_ms is None:
                timeout_cell: Text | str = "-"
            else:
                latency = entry.latency_ms
                latency_style = "green" if latency < 200 else ("yellow" if latency < 500 else "red")
                timeout_cell = Text(f"{latency}ms", style=latency_style)

            table.add_row(
                entry.timestamp.strftime("%H:%M:%S"),
                Text(entry.level.value.upper(), style=level_style) if level_style else entry.level.value.upper(),
                entry.source.value,
                entry.ip or "-",
                entry.service or "-",
                code_cell,
                timeout_cell,
                entry.message[:80],
            )
