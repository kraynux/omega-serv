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
from omega_serv.domain.security.waf.config import parse_waf_config
from omega_serv.interfaces.tui.screens._base import OmegaScreen
from omega_serv.ports.live_tail_port import LiveTailPort

if TYPE_CHECKING:
    from omega_serv.bootstrap.container import DependencyContainer
    from omega_serv.domain.config.entities import OmegaServConfig

_TAIL_INTERVAL_SECONDS = 1.0
_INITIAL_LINES = 200

_KNOWN_LOGS: tuple[tuple[str, str], ...] = (
    ("access", "access"),
    ("error", "error"),
    ("waf_alerts", "waf-alerts"),
)

_MAGNET_LOGS: tuple[tuple[str, str], ...] = (
    ("magnet_alerts", "waf magnet (alertes)"),
    ("magnet_blocklist", "waf magnet (blocklist)"),
)
"""Logs du script WAF complementaire "magnet" (import d'un WAF externe,
options.waf.magnet.paths) - retour utilisateur 2026-10-10 : boutons
presents "en dur" d'office (pas besoin d'activer magnet pour les VOIR),
mais GRISES tant que magnet n'est pas reellement actif (voir
`_magnet_active`) - plus clair qu'un bouton cliquable qui ne menerait
qu'a un message d'erreur. Une fois actif, si le fichier n'existe pas
encore (aucune alerte declenchee), un message d'info distinct de
"fichier introuvable" (`_MAGNET_EMPTY_HINTS`) evite de laisser croire a
une panne."""

_MAGNET_EMPTY_HINTS: dict[str, str] = {
    "magnet_alerts": "(log vide - aucune alerte du script magnet pour l'instant)",
    "magnet_blocklist": "(log vide - aucun ajout a la blocklist par le script magnet pour l'instant)",
}


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
                for log_id, label in _MAGNET_LOGS:
                    with Container(classes="omega-btn-frame"):
                        yield Button(label, id=f"open-{log_id}")
            yield RichLog(id="log-content", wrap=False, highlight=False, markup=False)
            with Horizontal(classes="omega-actions"):
                with Container(classes="omega-btn-frame"):
                    yield Button("Suivre en direct", id="follow")
                with Container(classes="omega-btn-frame"):
                    yield Button("Retour", id="back")
        yield Footer()

    def on_mount(self) -> None:
        self._refresh_magnet_buttons()

    def _magnet_active(self, config: OmegaServConfig) -> bool:
        """Magnet reellement actif seulement si l'option "waf" ET
        `options.waf.magnet.enabled` le sont (meme condition exacte que
        `build_waf_collaborators` - jamais une approximation locale a
        cet ecran)."""
        if "waf" not in config.options or not config.option_enabled("waf"):
            return False
        return parse_waf_config(config.options["waf"].settings).magnet.enabled

    def _refresh_magnet_buttons(self) -> None:
        load_result = load_config(self._container.configuration, self._container.config_file)
        active = load_result.success and load_result.config is not None and self._magnet_active(load_result.config)
        for log_id, _label in _MAGNET_LOGS:
            self.query_one(f"#open-{log_id}", Button).disabled = not active

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

    def _resolve_log_path(self, config: OmegaServConfig, log_id: str) -> Path | None:
        relative_path: str | None
        if log_id in ("magnet_alerts", "magnet_blocklist"):
            if "waf" not in config.options:
                return None
            magnet_paths = parse_waf_config(config.options["waf"].settings).magnet.paths
            relative_path = magnet_paths.alerts_log if log_id == "magnet_alerts" else magnet_paths.blocklist_log
        else:
            relative_path = getattr(config.logs, log_id, None)
            if relative_path is None:
                return None
        return self._container.project_root / relative_path

    def _open_log(self, log_id: str) -> None:
        error_widget = self.query_one("#viewer-error", Static)
        load_result = load_config(self._container.configuration, self._container.config_file)
        if not load_result.success or load_result.config is None:
            error_widget.update("Erreur de configuration : " + "; ".join(load_result.errors))
            return

        path = self._resolve_log_path(load_result.config, log_id)
        if path is None:
            error_widget.update(f"Log inconnu : {log_id!r}")
            return

        self._stop_following()
        self._current_path = path
        error_widget.update("")
        log_widget = self.query_one("#log-content", RichLog)
        log_widget.clear()

        if not self._current_path.exists():
            empty_hint = _MAGNET_EMPTY_HINTS.get(log_id, f"(fichier introuvable : {self._current_path})")
            log_widget.write(empty_hint)
            self._tail_reader = None
            return

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
