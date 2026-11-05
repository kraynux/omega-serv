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

from rich.cells import cell_len, set_cell_size
from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Center, Container, Horizontal, Vertical, VerticalScroll
from textual.timer import Timer
from textual.widgets import Button, DataTable, Footer, Header, Static

from omega_serv.core.i18n import _
from omega_serv.domain.logs.analytics import compute_traffic_stats
from omega_serv.domain.logs.models import LogEntry, TrafficStats
from omega_serv.domain.logs.parser import parse_log_line
from omega_serv.interfaces.tui.screens._base import OmegaScreen
from omega_serv.ports.live_tail_port import LiveTailPort

if TYPE_CHECKING:
    from omega_serv.bootstrap.container import DependencyContainer

_REFRESH_SECONDS = 2.0
_BUFFER_SIZE = 500
_INITIAL_LINES = 200
_TOP_WIDTH = 29
"""Largeur utile du cadre de gauche avant son premier affichage (34 colonnes, cadre et barre deduits)."""


def _format_bytes(size: float) -> str:
    if size >= 1024 * 1024:
        return f"{size / (1024 * 1024):.1f} MB"
    if size >= 1024:
        return f"{size / 1024:.1f} KB"
    return f"{int(size)} B"


class LogSimpleViewerScreen(OmegaScreen):
    """Suit un fichier en direct : tout le tampon dans un tableau qui defile (suivi automatique quand on
    est en bas) + barre de statut identique au viewer Simple d'omega-fire (rendement, bande passante,
    statuts HTTP, clients et reseau, sante et tampon - retour utilisateur 2026-11-02 : seuls « Apercu »
    et « Top IP », et 30 lignes visibles sans ascenseur pour un tampon de 200)."""

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
            with Center():  # titre et bouton centres (2026-11-05)
                yield Static(_("VOIR LES LOGS - SIMPLE - {path}").format(path=self._path), classes="omega-title")
            with Horizontal(id="simple-viewer-body"):
                # Cadre qui defile (2026-11-05) : avec les tops repris d'Etat & Ressources, un Static seul
                # a hauteur fixe coupait la fin de son contenu.
                with VerticalScroll(id="stats-frame", classes="omega-dash-box"):
                    yield Static(id="stats-box")
                yield DataTable(id="entries-table")
            with Center(), Horizontal(classes="omega-actions"), Container(classes="omega-btn-frame"):
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

        added = False
        for line in new_lines:
            self._line_number += 1
            entry = parse_log_line(line, line_number=self._line_number, log_path=self._path)
            if entry is not None:
                self._buffer.append(entry)
                added = True
        if len(self._buffer) > _BUFFER_SIZE:
            self._buffer = self._buffer[-_BUFFER_SIZE:]

        self._render_stats()
        if added:
            self._render_table()

    def _render_stats(self) -> None:
        self.query_one("#stats-box", Static).update(self._stats_text(compute_traffic_stats(self._buffer)))

    def _stats_text(self, stats: TrafficStats) -> Text:
        variables = self.app.get_css_variables()
        heading = f"bold {variables.get('secondary', '')}".strip()
        good = variables.get("success", "green") or "green"
        warn = variables.get("warning", "yellow") or "yellow"
        bad = variables.get("error", "red") or "red"
        info = variables.get("secondary", "cyan") or "cyan"
        none = "-"

        content = Text()
        content.append(_("── RENDEMENT ──────────────\n"), style=heading)
        rps = none if stats.requests_per_second is None else _("{rps:.1f} req/s").format(rps=stats.requests_per_second)
        content.append(_(" ⚡ Débit        : {value}\n").format(value=rps), style=info)
        if stats.avg_latency_ms is None:
            content.append(_(" ⏱ Latence moy. : {value}\n\n").format(value=none))
        else:
            latency = stats.avg_latency_ms
            style = good if latency < 200 else (warn if latency < 500 else bad)
            content.append(_(" ⏱ Latence moy. : {value}\n\n").format(value=f"{latency:.0f} ms"), style=style)

        content.append(_("── BANDE PASSANTE ─────────\n"), style=heading)
        bps = none if stats.bytes_per_second is None else f"{_format_bytes(stats.bytes_per_second)}/s"
        total = none if stats.bytes_total is None else _format_bytes(stats.bytes_total)
        average = none if stats.avg_size is None else _format_bytes(stats.avg_size)
        content.append(_(" 🌐 Débit réseau : {value}\n").format(value=bps))
        content.append(_(" 📦 Volume total : {value}\n").format(value=total))
        content.append(_(" 🗜 Taille moy.  : {value}\n\n").format(value=average))

        content.append(_("── STATUTS HTTP ───────────\n"), style=heading)
        content.append(_(" 📊 Requêtes     : {count}\n").format(count=stats.http_total))
        content.append(_(" √  Succès 2xx   : {count}\n").format(count=stats.status_2xx), style=good)
        content.append(_(" ↔  Redir. 3xx   : {count}\n").format(count=stats.status_3xx), style=info)
        content.append(_(" ⚠  Erreurs 4xx  : {count}\n").format(count=stats.status_4xx), style=warn)
        content.append(_(" ❌ Erreurs 5xx  : {count}\n").format(count=stats.status_5xx), style=bad)
        content.append(_(" ⛔ Refus 403    : {count}\n").format(count=stats.status_403), style=warn)
        content.append(_(" ⏳ Refus 429    : {count}\n\n").format(count=stats.status_429), style=warn)

        content.append(_("── CLIENTS & RÉSEAU ───────\n"), style=heading)
        content.append(_(" 💻 IPs uniques  : {count}\n").format(count=stats.unique_ips))
        # Adresse sur sa propre ligne : une IPv4 longue ou une IPv6 deborderait du cadre (34 colonnes).
        content.append(_(" 🖧 Top 5 IP     :\n"), style=info)
        self._append_top(content, stats.top_ips, info)
        if stats.top_paths:
            content.append(_("── CHEMINS DEMANDÉS ───────\n"), style=heading)
            self._append_top(content, stats.top_paths, "")
            content.append(_("── CHEMINS EN 404 ─────────\n"), style=heading)
            self._append_top(content, stats.top_not_found, warn)

        content.append(_("── SANTÉ & TAMPON ─────────\n"), style=heading)
        rate = stats.error_rate
        health_style = good if rate < 5 else (warn if rate < 15 else bad)
        health = _("EXCELLENT") if rate < 2 else (_("CORRECT") if rate < 10 else _("DÉGRADÉ"))
        content.append(_(" 🌡 Santé        : {health}\n").format(health=health), style=health_style)
        content.append(_(" ⚠  Taux d'erreur: {rate:.1f}%\n").format(rate=rate), style=health_style)
        content.append(_(" 📥 Tampon       : {count}/{size}").format(count=len(self._buffer), size=_BUFFER_SIZE))
        return content

    def _append_top(self, content: Text, items: list[tuple[str, int]], style: str) -> None:
        """Valeur (IP, chemin) depuis le bord gauche, compte colle au bord droit (2026-11-05) : le chemin
        dispose de toute la largeur restante au lieu de commencer au milieu du cadre."""
        if not items:
            content.append("    " + _("(aucun)") + "\n\n", style="dim")
            return
        width = self.query_one("#stats-box", Static).size.width or _TOP_WIDTH
        count_width = max(len(str(count)) for _value, count in items)
        room = max(8, width - 2 - count_width)  # 1 espace de marge + 1 avant le compte
        for value, count in items:
            shown = value if cell_len(value) <= room else set_cell_size(value, room - 1) + "…"
            content.append(" " + shown + " " * (room - cell_len(shown)) + " ", style=style)
            content.append(f"{count:>{count_width}}\n", style="bold")
        content.append("\n")

    def _render_table(self) -> None:
        table = self.query_one("#entries-table", DataTable)
        # Suivi automatique seulement si on etait deja en bas : jamais arrache d'une lecture plus haut.
        follow = table.scroll_y >= table.max_scroll_y - 1
        table.clear()
        for entry in self._buffer:
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
        if follow:
            table.call_after_refresh(table.scroll_end, animate=False)
