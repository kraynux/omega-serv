# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Ecran Voir un fichier log + Suivre en direct (plan interface §3.4/§8) -
un seul ecran couvre les deux lignes du tableau §8 (meme mecanisme sous-
jacent : lecture, puis suivi incremental des lignes ajoutees). Affiche
les dernieres lignes au montage, "Suivre en direct" bascule un
rafraichissement periodique (`set_interval`, pas un vrai flux asyncio
pousse - inutile ici, Textual gere deja sa propre boucle d'evenements)
via `container.build_live_tail_reader` (aucun subprocess/ssl, construit
directement dans bootstrap/container.py)."""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.timer import Timer
from textual.widgets import Button, Footer, Header, RichLog, Static

from omega_serv.application.config.load_config import load_config
from omega_serv.interfaces.tui.screens._base import OmegaScreen
from omega_serv.ports.live_tail_port import LiveTailPort

if TYPE_CHECKING:
    from omega_serv.bootstrap.container import DependencyContainer

_TAIL_INTERVAL_SECONDS = 1.0
_INITIAL_LINES = 200

_KNOWN_LOGS: tuple[tuple[str, str], ...] = (
    ("access", "access"),
    ("error", "error"),
    ("waf_alerts", "waf-alerts"),
)


class LogViewerScreen(OmegaScreen):
    def __init__(self, *, container: DependencyContainer) -> None:
        super().__init__()
        self._container = container
        self._current_path: Path | None = None
        self._tail_reader: LiveTailPort | None = None
        self._following = False
        self._timer: Timer | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(classes="omega-panel"):
            yield Static("VOIR / SUIVRE UN FICHIER LOG", classes="omega-title")
            yield Static("", id="viewer-error", classes="omega-hint")
            with Horizontal(classes="omega-actions"):
                for log_id, label in _KNOWN_LOGS:
                    with Container(classes="omega-btn-frame"):
                        yield Button(label, id=f"open-{log_id}", variant="primary")
            yield RichLog(id="log-content", wrap=False, highlight=False, markup=False)
            with Horizontal(classes="omega-actions"):
                with Container(classes="omega-btn-frame"):
                    yield Button("Suivre en direct", id="follow")
                with Container(classes="omega-btn-frame"):
                    yield Button("Retour", id="back")
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id or ""
        if button_id == "back":
            self.dismiss()
            return
        if button_id == "follow":
            self._toggle_follow()
            return
        if button_id.startswith("open-"):
            self._open_log(button_id.removeprefix("open-"))

    def _open_log(self, log_id: str) -> None:
        error_widget = self.query_one("#viewer-error", Static)
        load_result = load_config(self._container.configuration, self._container.config_file)
        if not load_result.success or load_result.config is None:
            error_widget.update("Erreur de configuration : " + "; ".join(load_result.errors))
            return

        relative_path = getattr(load_result.config.logs, log_id, None)
        if relative_path is None:
            error_widget.update(f"Log inconnu : {log_id!r}")
            return

        self._stop_following()
        self._current_path = self._container.project_root / relative_path
        error_widget.update("")
        log_widget = self.query_one("#log-content", RichLog)
        log_widget.clear()

        if not self._current_path.exists():
            log_widget.write(f"(fichier introuvable : {self._current_path})")
            self._tail_reader = None
            return

        # Retour utilisateur 2026-09-14 : "j'ai clique sur waf-alerts.log,
        # ca a bloque l'application" - un fichier peut appartenir au
        # compte systeme dedie du service (var/log/ partage, voir
        # grant_directory_access) alors que la session TUI courante n'a
        # pas encore pris en compte l'appartenance de groupe qui donne
        # normalement l'acces (meme cause deja rencontree et corrigee
        # pour la connexion sqlite Active Defense, jamais protegee ici) -
        # PermissionError non rattrapee plantait l'ecran plutot que
        # d'afficher un message clair.
        try:
            content = self._current_path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            log_widget.write(f"(impossible de lire {self._current_path} : {exc})")
            self._tail_reader = None
            return
        lines = content.splitlines()[-_INITIAL_LINES:]
        for line in lines:
            log_widget.write(line)
        self._tail_reader = self._container.build_live_tail_reader(self._current_path)

    def _toggle_follow(self) -> None:
        if self._current_path is None:
            self.query_one("#viewer-error", Static).update("Choisissez d'abord un fichier de log.")
            return
        if self._following:
            self._stop_following()
        else:
            self._start_following()

    def _start_following(self) -> None:
        self._following = True
        self.query_one("#follow", Button).label = "Arreter le suivi"
        self._timer = self.set_interval(_TAIL_INTERVAL_SECONDS, self._poll_new_lines)

    def _stop_following(self) -> None:
        self._following = False
        if self._timer is not None:
            self._timer.stop()
            self._timer = None
        if self.is_mounted:
            self.query_one("#follow", Button).label = "Suivre en direct"

    def on_unmount(self) -> None:
        if self._timer is not None:
            self._timer.stop()

    def _poll_new_lines(self) -> None:
        if not self._following or self._tail_reader is None:
            return
        try:
            new_lines = self._tail_reader.read_new_lines()
        except OSError as exc:
            self.query_one("#log-content", RichLog).write(f"(suivi interrompu : {exc})")
            self._stop_following()
            return
        for line in new_lines:
            self.query_one("#log-content", RichLog).write(line)
