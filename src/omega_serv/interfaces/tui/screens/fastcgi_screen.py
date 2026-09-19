"""Sous-ecran FastCGI/PHP-FPM (plan interface §7, `option enable
fastcgi` + url_prefix/script_root) - un seul enregistrement (modele de
zone volontairement simplifie, domain/routing/fastcgi_zone.py), jamais
une liste. Validation structurelle via
`validate_fastcgi_config_structure` (domain, pure) + un avertissement
"hors webroot" affiche en direct (spec §21/§6 - la porte bloquante
reelle reste verifiee par Configuration detaillee -> Verifier la configuration,
ce sous-ecran ne fait qu'avertir tot)."""
from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Button, Footer, Header, Input, Static

from omega_serv.application.config.load_config import load_config
from omega_serv.domain.config.option import Option
from omega_serv.domain.routing.fastcgi_zone import (
    FastCgiConfig,
    parse_fastcgi_config,
    validate_fastcgi_config_structure,
)
from omega_serv.interfaces.tui.screens._base import OmegaScreen
from omega_serv.interfaces.tui.screens.restart_prompt import notify_reload_required

if TYPE_CHECKING:
    from omega_serv.bootstrap.container import DependencyContainer

_FIELDS: tuple[tuple[str, str], ...] = (
    ("url_prefix", "Prefixe URL (url_prefix, ex: /app/)"),
    ("script_root", "Racine d'execution (script_root, relatif au projet)"),
    ("socket_path", "Socket PHP-FPM (socket_path)"),
    ("connect_timeout_seconds", "Delai de connexion en secondes"),
    ("read_timeout_seconds", "Delai de lecture en secondes"),
    ("allowed_extensions", "Extensions autorisees (separees par des virgules)"),
    ("index_files", "Fichiers d'index (separes par des virgules)"),
    (
        "allowed_scripts",
        (
            "Liste blanche de scripts (chemins relatifs a script_root, separes par des "
            "virgules, ex: index.php, api/router.php - vide = tout .php sous script_root reste executable)"
        ),
    ),
)


class FastCgiScreen(OmegaScreen):
    def __init__(self, *, container: DependencyContainer) -> None:
        super().__init__()
        self._container = container

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(classes="omega-form-panel"):
            yield Static("FASTCGI / PHP-FPM", classes="omega-title")
            yield Static(
                "L'activation de l'option 'fastcgi' se fait dans le menu Options.",
                classes="omega-hint",
            )
            yield Static("", id="form-error", classes="omega-hint")
            for field_name, label in _FIELDS:
                yield Static(label, classes="omega-subtitle")
                yield Input(id=f"field-{field_name}")
            with Horizontal(classes="omega-actions"):
                with Container(classes="omega-btn-frame"):
                    yield Button("Enregistrer", id="save", variant="primary")
                with Container(classes="omega-btn-frame"):
                    yield Button("Retour", id="back")
        yield Footer()

    def on_mount(self) -> None:
        result = load_config(self._container.configuration, self._container.config_file)
        if not result.success or result.config is None:
            self.query_one("#form-error", Static).update("Erreur de configuration.")
            return
        option = result.config.options.get("fastcgi")
        config = FastCgiConfig() if option is None else parse_fastcgi_config(option.settings)
        self.query_one("#field-url_prefix", Input).value = config.url_prefix
        self.query_one("#field-script_root", Input).value = config.script_root
        self.query_one("#field-socket_path", Input).value = config.socket_path
        self.query_one("#field-connect_timeout_seconds", Input).value = str(config.connect_timeout_seconds)
        self.query_one("#field-read_timeout_seconds", Input).value = str(config.read_timeout_seconds)
        self.query_one("#field-allowed_extensions", Input).value = ", ".join(config.allowed_extensions)
        self.query_one("#field-index_files", Input).value = ", ".join(config.index_files)
        self.query_one("#field-allowed_scripts", Input).value = ", ".join(config.allowed_scripts)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "back":
            self.dismiss()
            return
        if event.button.id == "save":
            self._save()

    def _save(self) -> None:
        error_widget = self.query_one("#form-error", Static)
        load_result = load_config(self._container.configuration, self._container.config_file)
        if not load_result.success or load_result.config is None:
            error_widget.update("Erreur de configuration - impossible d'enregistrer.")
            return

        try:
            connect_timeout = float(self.query_one("#field-connect_timeout_seconds", Input).value.strip())
            read_timeout = float(self.query_one("#field-read_timeout_seconds", Input).value.strip())
        except ValueError:
            error_widget.update("Delais invalides (nombre attendu).")
            return

        config = FastCgiConfig(
            url_prefix=self.query_one("#field-url_prefix", Input).value.strip(),
            script_root=self.query_one("#field-script_root", Input).value.strip(),
            socket_path=self.query_one("#field-socket_path", Input).value.strip(),
            connect_timeout_seconds=connect_timeout,
            read_timeout_seconds=read_timeout,
            allowed_extensions=tuple(
                item.strip() for item in self.query_one("#field-allowed_extensions", Input).value.split(",") if item.strip()
            ),
            index_files=tuple(
                item.strip() for item in self.query_one("#field-index_files", Input).value.split(",") if item.strip()
            ),
            allowed_scripts=tuple(
                item.strip() for item in self.query_one("#field-allowed_scripts", Input).value.split(",") if item.strip()
            ),
        )

        errors = validate_fastcgi_config_structure(config)
        if config.script_root:
            webroot = (self._container.project_root / load_result.config.paths.webroot).resolve()
            script_root = (self._container.project_root / config.script_root).resolve()
            if script_root == webroot or webroot in script_root.parents:
                errors.append(
                    f"script_root ({script_root}) est a l'interieur de webroot ({webroot}) - interdit structurellement"
                )
        if errors:
            error_widget.update("Erreur :\n" + "\n".join(f"  - {e}" for e in errors))
            return

        existing = load_result.config.options.get("fastcgi")
        enabled = existing.enabled if existing is not None else False
        new_options = dict(load_result.config.options)
        new_options["fastcgi"] = Option(name="fastcgi", enabled=enabled, settings=_settings_from_config(config))
        new_config = replace(load_result.config, options=new_options)
        self._container.configuration.save(self._container.config_file, new_config)
        error_widget.update("")
        notify_reload_required(self, self._container, "Configuration FastCGI enregistree.")


def _settings_from_config(config: FastCgiConfig) -> dict:
    return {
        "url_prefix": config.url_prefix,
        "script_root": config.script_root,
        "socket_path": config.socket_path,
        "connect_timeout_seconds": config.connect_timeout_seconds,
        "read_timeout_seconds": config.read_timeout_seconds,
        "allowed_extensions": list(config.allowed_extensions),
        "index_files": list(config.index_files),
        "allowed_scripts": list(config.allowed_scripts),
    }
