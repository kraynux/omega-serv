# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Ecran Suivre les logs fusionnes avec lnav (plan interface §3.4/§8) -
simplifie par rapport a l'ecran equivalent d'omega-fire : SERV connait
deja ses propres chemins de log fixes (access/error/waf-alerts, depuis
la configuration chargee), aucune ambiguite de "quel serveur web/quel
backend" a resoudre - pas besoin du systeme d'epingles/historique de
fire (`ManageLiveTailPinsCommand`), concu pour merger des logs de
plusieurs backends web tiers (nginx/apache/lighttpd/caddy) dont fire ne
connait pas les chemins a l'avance. Cases a cocher sur les logs connus +
un champ pour un chemin manuel supplementaire, lancement via
`App.suspend()` (le rendu PTY+pyte lui-meme vit dans
infrastructure/lnav/, injecte via container.lnav_runner car il touche
subprocess)."""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from omega_lib.theme.policies import TUI_THEMES
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Button, Checkbox, Footer, Header, Input, Static

from omega_serv.application.config.load_config import load_config
from omega_serv.interfaces.tui.screens._base import OmegaScreen

if TYPE_CHECKING:
    from omega_serv.bootstrap.container import DependencyContainer

_TITLE = "\U0001f512 OMEGA-SERV"
_MENU_LABEL = "Suivre les logs fusionnes (lnav)"

_KNOWN_LOGS: tuple[tuple[str, str], ...] = (
    ("access", "Access log"),
    ("error", "Error log"),
    ("waf_alerts", "WAF alerts log"),
)


class LnavScreen(OmegaScreen):
    def __init__(self, *, container: DependencyContainer) -> None:
        super().__init__()
        self._container = container

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(classes="omega-panel"):
            yield Static("SUIVRE LES LOGS FUSIONNES (LNAV)", classes="omega-title")
            yield Static(
                "Cochez un ou plusieurs logs a fusionner. lnav quitte avec Ctrl-Q "
                "(ou sa propre commande de sortie) ; vous revenez alors a cet ecran.",
                classes="omega-hint",
            )
            yield Static("", id="lnav-error", classes="omega-hint")
            for log_id, label in _KNOWN_LOGS:
                yield Checkbox(label, id=f"check-{log_id}")
            yield Static("Chemin manuel supplementaire (optionnel)", classes="omega-subtitle")
            yield Input(id="manual-path-input")
            with Horizontal(classes="omega-actions"):
                with Container(classes="omega-btn-frame"):
                    yield Button("Lancer lnav", id="launch", variant="primary")
                with Container(classes="omega-btn-frame"):
                    yield Button("Retour", id="back")
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "back":
            self.dismiss()
            return
        if event.button.id == "launch":
            self._launch()

    def _selected_paths(self) -> list[Path]:
        load_result = load_config(self._container.configuration, self._container.config_file)
        if not load_result.success or load_result.config is None:
            return []
        paths = []
        for log_id, _label in _KNOWN_LOGS:
            if self.query_one(f"#check-{log_id}", Checkbox).value:
                relative_path = getattr(load_result.config.logs, log_id)
                paths.append(self._container.project_root / relative_path)
        manual = self.query_one("#manual-path-input", Input).value.strip()
        if manual:
            paths.append(self._container.project_root / manual if not Path(manual).is_absolute() else Path(manual))
        return paths

    def _launch(self) -> None:
        error_widget = self.query_one("#lnav-error", Static)
        runner = self._container.lnav_runner
        if runner is None:
            error_widget.update("lnav indisponible dans cet environnement.")
            return

        paths = self._selected_paths()
        existing = [p for p in paths if p.exists()]
        missing = [p for p in paths if not p.exists()]
        if missing:
            error_widget.update("Fichier(s) introuvable(s), ignore(s) : " + ", ".join(str(p) for p in missing))
        if not existing:
            error_widget.update("Aucun fichier valide selectionne.")
            return

        theme = TUI_THEMES.get(self.app.theme)
        palette = theme.palette if theme is not None else next(iter(TUI_THEMES.values())).palette

        with self._maybe_suspend():
            result = runner(tuple(existing), palette, _TITLE, _MENU_LABEL)

        if result is not None:
            error_widget.update(result)
        else:
            error_widget.update("")
