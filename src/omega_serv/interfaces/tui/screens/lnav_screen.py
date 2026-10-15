"""Ecran Suivre les logs fusionnes avec lnav (plan interface §3.4/§8) -
simplifie par rapport a l'ecran equivalent d'omega-fire : SERV connait
deja ses propres chemins de log fixes (access/error/waf-alerts, depuis
la configuration chargee), aucune ambiguite de "quel serveur web/quel
backend" a resoudre. Cases a cocher sur les logs connus + un champ pour
un chemin manuel supplementaire, lancement via `App.suspend()` (le rendu
PTY+pyte lui-meme vit dans infrastructure/lnav/, injecte via
container.lnav_runner car il touche subprocess).

Logs du script WAF complementaire "magnet" (options.waf.magnet.paths)
ajoutes en dur (retour utilisateur 2026-10-10) comme les logs natifs -
un fichier absent/non encore cree est deja gere par `_launch()` ci-dessous
(liste "introuvable(s), ignore(s)", jamais bloquant), aucun grisage
necessaire ici contrairement a l'ecran Tail (ou le grisage evite un clic
qui ne menerait qu'a un message d'erreur a lui seul - ici cocher un log
absent est deja sans consequence par construction).

Epingles (retour utilisateur 2026-10-10, "gestion d'epingle dans les
logs fusionnes") : chemins manuels PERSISTES entre sessions
(`container.settings_store`, cle `_PINNED_PATHS_SETTINGS_KEY`, liste
JSON - pas de nouveau port, reutilise le mecanisme deja existant pour
d'autres preferences comme `exports_dir_override`). Rendus comme des
cases a cocher dynamiques, exactement au meme titre que les logs
natifs/magnet "en dur" - une epingle n'est qu'un chemin en dur ajoute
par l'utilisateur plutot que par le code, jamais un mecanisme distinct
cote selection/lancement. Contrairement a omega-fire
(`ManageLiveTailPinsCommand`, concu pour merger des logs de plusieurs
backends web tiers dont fire ne connait pas les chemins a l'avance),
l'essentiel reste connu a l'avance ici - les epingles couvrent le cas
residuel (un chemin de log hors des emplacements standard)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

from omega_lib.theme.policies import TUI_THEMES
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, VerticalScroll
from textual.widgets import Button, Checkbox, Footer, Header, Input, Select, Static

from omega_serv.application.config.load_config import load_config
from omega_serv.domain.security.waf.config import MagnetPathsConfig, parse_waf_config
from omega_serv.interfaces.tui.screens._base import OmegaScreen

if TYPE_CHECKING:
    from omega_serv.bootstrap.container import DependencyContainer
    from omega_serv.domain.config.entities import OmegaServConfig

_TITLE = "\U0001f512 OMEGA-SERV"
_MENU_LABEL = "Suivre les logs fusionnes (lnav)"

_KNOWN_LOGS: tuple[tuple[str, str], ...] = (
    ("access", "Access log"),
    ("error", "Error log"),
    ("waf_alerts", "WAF alerts log"),
)

_MAGNET_LOGS: tuple[tuple[str, str], ...] = (
    ("magnet_alerts", "WAF magnet - alertes"),
    ("magnet_blocklist", "WAF magnet - blocklist"),
)

_PINNED_PATHS_SETTINGS_KEY = "lnav_pinned_paths"


class LnavScreen(OmegaScreen):
    def __init__(
        self, *, container: DependencyContainer, preset_paths: tuple[str, ...] = (), auto_launch: bool = False,
    ) -> None:
        super().__init__()
        self._container = container
        self._preset_paths = preset_paths
        """Chemins deja selectionnes en amont (ecran "Voir les logs",
        refonte menu 2026-10-15) - rendus PRE-COCHES ici, jamais ajoutes
        aux epingles persistees (une selection ponctuelle depuis la
        Bibliotheque n'est pas forcement destinee a survivre entre
        sessions, contrairement a une vraie epingle)."""
        self._auto_launch = auto_launch
        """Lance automatiquement (sans clic supplementaire) des l'arrivee
        sur cet ecran - retour utilisateur 2026-10-15 ("souci de
        coherence depuis les favoris, on tombe sur l'ecran lnav au lieu
        de lancer directement le favori") : un favori Simple/Classique
        ouvre deja directement le viewer final (zero clic) ; un favori
        lnav, lui, ne faisait qu'arriver sur CET ecran de configuration
        (cases a cocher deja pre-remplies par `preset_paths`) et exigeait
        encore un clic sur 'Lancer lnav' - cassait la promesse meme d'un
        favori. Reserve au lancement depuis un favori (jamais depuis
        "Voir les logs", ou arriver sur cet ecran pour ajuster la
        selection avant de lancer reste le comportement voulu)."""

    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll(classes="omega-panel"):
            yield Static("SUIVRE LES LOGS FUSIONNES (LNAV)", classes="omega-title")
            yield Static(
                "Cochez un ou plusieurs logs a fusionner. lnav quitte avec Ctrl-Q "
                "(ou sa propre commande de sortie) ; vous revenez alors a cet ecran.",
                classes="omega-hint",
            )
            yield Static("", id="lnav-error", classes="omega-hint")
            for log_id, label in _KNOWN_LOGS:
                yield Checkbox(label, id=f"check-{log_id}")
            for log_id, label in _MAGNET_LOGS:
                yield Checkbox(label, id=f"check-{log_id}")

            if self._preset_paths:
                yield Static("Logs selectionnes depuis la Bibliotheque", classes="omega-subtitle")
                for index, preset_path in enumerate(self._preset_paths):
                    yield Checkbox(preset_path, value=True, id=f"check-preset-{index}")

            yield Static("Chemins epingles", classes="omega-subtitle")
            yield Container(id="pinned-checkboxes")

            yield Static("Chemin manuel - 'Epingler' le conserve pour les prochains lancements", classes="omega-subtitle")
            yield Input(id="manual-path-input")
            with Horizontal(classes="omega-actions"):
                with Container(classes="omega-btn-frame"):
                    yield Button("Epingler ce chemin", id="pin-manual")

            yield Static("Retirer une epingle existante", classes="omega-subtitle")
            yield Select[str]([], id="unpin-select", allow_blank=True, prompt="(aucune epingle)")
            with Horizontal(classes="omega-actions"):
                with Container(classes="omega-btn-frame"):
                    yield Button("Retirer l'epingle choisie", id="unpin")

            with Horizontal(classes="omega-actions"):
                with Container(classes="omega-btn-frame"):
                    yield Button("Lancer lnav", id="launch", variant="primary")
                with Container(classes="omega-btn-frame"):
                    yield Button("Retour", id="back")
        yield Footer()

    def on_mount(self) -> None:
        self._refresh_pins()
        if self._auto_launch:
            # Apres le premier affichage reellement stabilise, jamais
            # pendant la transition de push_screen elle-meme (ou suspendre
            # le terminal serait premature).
            self.call_after_refresh(self._launch)

    def _load_pinned_paths(self) -> list[str]:
        raw = self._container.settings_store.get(_PINNED_PATHS_SETTINGS_KEY, "[]") or "[]"
        try:
            data = json.loads(raw)
        except ValueError:
            return []
        return [str(p) for p in data] if isinstance(data, list) else []

    def _save_pinned_paths(self, pins: list[str]) -> None:
        self._container.settings_store.set(_PINNED_PATHS_SETTINGS_KEY, json.dumps(pins))

    def _refresh_pins(self) -> None:
        pins = self._load_pinned_paths()
        container = self.query_one("#pinned-checkboxes", Container)
        container.remove_children()
        for index, path in enumerate(pins):
            container.mount(Checkbox(path, id=f"check-pinned-{index}"))
        select = self.query_one("#unpin-select", Select)
        select.set_options((path, path) for path in pins)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "back":
            self.dismiss()
            return
        if event.button.id == "launch":
            self._launch()
            return
        if event.button.id == "pin-manual":
            self._pin_manual()
            return
        if event.button.id == "unpin":
            self._unpin_selected()

    def _pin_manual(self) -> None:
        error_widget = self.query_one("#lnav-error", Static)
        manual_input = self.query_one("#manual-path-input", Input)
        manual = manual_input.value.strip()
        if not manual:
            error_widget.update("Saisissez d'abord un chemin a epingler.")
            return
        pins = self._load_pinned_paths()
        if manual in pins:
            error_widget.update("Ce chemin est deja epingle.")
            return
        pins.append(manual)
        self._save_pinned_paths(pins)
        # Vide le champ manuel : le chemin vient d'etre represente par sa
        # propre case a cocher epinglee - le laisser rempli aurait compte
        # le meme fichier DEUX FOIS au lancement si les deux sont cochees.
        manual_input.value = ""
        error_widget.update("")
        self.app.notify("Chemin epingle.")
        self._refresh_pins()

    def _unpin_selected(self) -> None:
        error_widget = self.query_one("#lnav-error", Static)
        select = self.query_one("#unpin-select", Select)
        value = select.value
        if value is Select.BLANK or not value:
            error_widget.update("Choisissez d'abord une epingle a retirer.")
            return
        pins = self._load_pinned_paths()
        if str(value) in pins:
            pins.remove(str(value))
            self._save_pinned_paths(pins)
            error_widget.update("")
            self.app.notify("Epingle retiree.")
        self._refresh_pins()

    def _resolve_known_log_path(self, config: OmegaServConfig, log_id: str) -> Path:
        relative_path: str
        if log_id in ("magnet_alerts", "magnet_blocklist"):
            magnet_paths = (
                parse_waf_config(config.options["waf"].settings).magnet.paths
                if "waf" in config.options else MagnetPathsConfig()
            )
            relative_path = magnet_paths.alerts_log if log_id == "magnet_alerts" else magnet_paths.blocklist_log
        else:
            relative_path = getattr(config.logs, log_id)
        return self._container.project_root / relative_path

    def _selected_paths(self) -> list[Path]:
        load_result = load_config(self._container.configuration, self._container.config_file)
        if not load_result.success or load_result.config is None:
            return []
        paths = []
        for log_id, _label in (*_KNOWN_LOGS, *_MAGNET_LOGS):
            if self.query_one(f"#check-{log_id}", Checkbox).value:
                paths.append(self._resolve_known_log_path(load_result.config, log_id))
        for index, preset_path in enumerate(self._preset_paths):
            if self.query_one(f"#check-preset-{index}", Checkbox).value:
                paths.append(Path(preset_path))
        for index, pinned_path in enumerate(self._load_pinned_paths()):
            if self.query_one(f"#check-pinned-{index}", Checkbox).value:
                candidate = Path(pinned_path)
                paths.append(candidate if candidate.is_absolute() else self._container.project_root / candidate)
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
