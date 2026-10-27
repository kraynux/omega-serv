"""Viewer 2 (CLASSIQUE) - lecture + suivi en direct d'un chemin de log
(gestion des logs, refonte menu 2026-10-15) - un seul ecran couvre les
deux (meme mecanisme sous-jacent : lecture, puis suivi incremental des
lignes ajoutees) via `container.build_live_tail_reader` (aucun
subprocess/ssl, construit directement dans bootstrap/container.py).

GENERALISE (refonte menu 2026-10-15) : accepte desormais un `path`
arbitraire (n'importe quel log de la Bibliotheque), au lieu d'un
`log_id` fixe parmi les quelques logs propres a Omega-Serv (access/
error/waf-alerts/magnet) - ce choix se fait maintenant en amont, dans
l'ecran "Voir les logs" (qui s'appuie sur la Bibliotheque), jamais
duplique ici."""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.timer import Timer
from textual.widgets import Button, Footer, Header, RichLog, Static

from omega_serv.core.i18n import _
from omega_serv.interfaces.tui.screens._base import OmegaScreen
from omega_serv.ports.live_tail_port import LiveTailPort

if TYPE_CHECKING:
    from omega_serv.bootstrap.container import DependencyContainer

_TAIL_INTERVAL_SECONDS = 1.0
_INITIAL_LINES = 200


class LogViewerScreen(OmegaScreen):
    def __init__(self, *, container: DependencyContainer, path: str) -> None:
        super().__init__()
        self._container = container
        self._path = path
        self._tail_reader: LiveTailPort | None = None
        self._following = False
        self._timer: Timer | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(classes="omega-panel"):
            yield Static(_("VOIR / SUIVRE - {path}").format(path=self._path), classes="omega-title")
            yield Static("", id="viewer-error", classes="omega-hint")
            yield RichLog(id="log-content", wrap=False, highlight=False, markup=False)
            with Horizontal(classes="omega-actions"):
                with Container(classes="omega-btn-frame"):
                    yield Button(_("Suivre en direct"), id="follow")
                with Container(classes="omega-btn-frame"):
                    yield Button(_("Retour"), id="back")
        yield Footer()

    def on_mount(self) -> None:
        self._open_log()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id or ""
        if button_id == "back":
            self.dismiss()
            return
        if button_id == "follow":
            self._toggle_follow()

    def _open_log(self) -> None:
        error_widget = self.query_one("#viewer-error", Static)
        path = Path(self._path)
        log_widget = self.query_one("#log-content", RichLog)
        log_widget.clear()

        if not path.exists():
            error_widget.update(_("Fichier introuvable : {path}").format(path=path))
            self._tail_reader = None
            return

        try:
            content = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            error_widget.update(_("Impossible de lire {path} : {exc}").format(path=path, exc=exc))
            self._tail_reader = None
            return

        error_widget.update("")
        for line in content.splitlines()[-_INITIAL_LINES:]:
            log_widget.write(line)
        self._tail_reader = self._container.build_live_tail_reader(path)

    def _toggle_follow(self) -> None:
        if self._tail_reader is None:
            self.query_one("#viewer-error", Static).update(_("Aucun fichier valide à suivre."))
            return
        if self._following:
            self._stop_following()
        else:
            self._start_following()

    def _start_following(self) -> None:
        self._following = True
        self.query_one("#follow", Button).label = _("Arrêter le suivi")
        self._timer = self.set_interval(_TAIL_INTERVAL_SECONDS, self._poll_new_lines)

    def _stop_following(self) -> None:
        self._following = False
        if self._timer is not None:
            self._timer.stop()
            self._timer = None
        if self.is_mounted:
            self.query_one("#follow", Button).label = _("Suivre en direct")

    def on_unmount(self) -> None:
        if self._timer is not None:
            self._timer.stop()

    def _poll_new_lines(self) -> None:
        if not self._following or self._tail_reader is None:
            return
        try:
            new_lines = self._tail_reader.read_new_lines()
        except OSError as exc:
            self.query_one("#log-content", RichLog).write(_("(suivi interrompu : {exc})").format(exc=exc))
            self._stop_following()
            return
        for line in new_lines:
            self.query_one("#log-content", RichLog).write(line)
