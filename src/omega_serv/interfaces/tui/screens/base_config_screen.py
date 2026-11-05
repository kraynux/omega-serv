"""Sous-ecran Configuration de base (plan interface §7) - bind/port/
server_name/index_files, edition directe puis validation structurelle
(domain/config/validation.py, pure) avant ecriture, meme discipline que
partout ailleurs dans l'interface (jamais d'ecriture sans verification).

Moteur HTTP (`server.engine`, plan moteur C++ Q6 tranchee le 2026-11-03 : ici, pas de nouveau bouton de
menu). Le choix « natif » est GRISE tant qu'une fonction active l'empeche (decision utilisateur 2026-11-02),
avec, pour chaque cause, comment la lever : un ordre de selection impose, jamais un moteur choisi qui ne peut
pas tourner. Sous le choix : ce qui tournera au prochain demarrage (« moteur natif, 1 processus » ; plan §25,
2026-11-04 : plus de noms de niveaux). Changer de moteur avec un nombre de processus au-dela du maximum du nouveau
moteur sur cette machine demande de le ramener au maximum (confirmation) : jamais un reglage qui ne s'appliquerait
pas sans que l'utilisateur le sache."""
from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Button, Footer, Header, Input, RadioButton, RadioSet, Static

from omega_serv.application.config.load_config import load_config
from omega_serv.application.server.engine_levels import (
    describe_run,
    max_workers,
    native_blockers,
    resolved_worker_count,
    worker_count_notice,
)
from omega_serv.application.server.engine_selection import describe_reason
from omega_serv.core.i18n import _
from omega_serv.core.platform_info import cpu_info
from omega_serv.domain.config.validation import validate_config
from omega_serv.interfaces.tui.screens._base import OmegaScreen
from omega_serv.interfaces.tui.screens.confirm import ConfirmScreen
from omega_serv.interfaces.tui.screens.restart_prompt import (
    notify_reload_required,
    notify_restart_required,
)

if TYPE_CHECKING:
    from omega_serv.bootstrap.container import DependencyContainer
    from omega_serv.domain.config.entities import OmegaServConfig


class BaseConfigScreen(OmegaScreen):
    def __init__(self, *, container: DependencyContainer) -> None:
        super().__init__()
        self._container = container

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(classes="omega-form-panel"):
            yield Static(_("CONFIGURATION DE BASE"), classes="omega-title")
            yield Static("", id="form-error", classes="omega-hint")
            yield Static(_("Adresse d'écoute (server.bind)"), classes="omega-subtitle")
            yield Input(id="bind-input")
            yield Static(_("Port (server.port)"), classes="omega-subtitle")
            yield Input(id="port-input")
            yield Static(_("Nom du serveur (server.server_name)"), classes="omega-subtitle")
            yield Input(id="server-name-input")
            yield Static(_("Fichiers d'index (séparés par des virgules)"), classes="omega-subtitle")
            yield Input(id="index-files-input")
            yield Static(_("Moteur HTTP (server.engine)"), classes="omega-subtitle")
            with RadioSet(id="engine-set"):
                yield RadioButton(_("Python"), id="engine-python")
                yield RadioButton(_("Natif C++ (omega-http-core)"), id="engine-native")
            yield Static("", id="engine-hint", classes="omega-hint")
            with Horizontal(classes="omega-actions"):
                with Container(classes="omega-btn-frame"):
                    yield Button(_("Enregistrer"), id="save", variant="primary")
                with Container(classes="omega-btn-frame"):
                    yield Button(_("Retour"), id="back")
        yield Footer()

    def on_mount(self) -> None:
        result = load_config(self._container.configuration, self._container.config_file)
        if not result.success:
            self.query_one("#form-error", Static).update(
                _("Erreur de configuration : ") + "; ".join(result.errors)
            )
            self.query_one("#save", Button).disabled = True
            return
        assert result.config is not None
        server = result.config.server
        self.query_one("#bind-input", Input).value = server.bind
        self.query_one("#port-input", Input).value = str(server.port)
        self.query_one("#server-name-input", Input).value = server.server_name
        self.query_one("#index-files-input", Input).value = ", ".join(server.index_files)
        self._workers = server.workers
        self._blockers = native_blockers(result.config, self._container.native_binary_problem())
        native_button = self.query_one("#engine-native", RadioButton)
        # Grise si une cause l'empeche - sauf s'il est deja le choix enregistre (on doit pouvoir en sortir).
        native_button.disabled = bool(self._blockers) and server.engine != "native"
        if native_button.disabled:
            native_button.label = _("Natif C++ (omega-http-core) - indisponible, voir ci-dessous")
        self.query_one("#engine-python" if server.engine != "native" else "#engine-native", RadioButton).value = True
        self._refresh_engine_hint()

    def _selected_engine(self) -> str:
        return "native" if self.query_one("#engine-native", RadioButton).value else "python"

    def on_radio_set_changed(self, event: RadioSet.Changed) -> None:
        self._refresh_engine_hint()

    def _refresh_engine_hint(self) -> None:
        engine = self._selected_engine()
        lines: list[str] = []
        if self._blockers:
            lines.append(_("Moteur natif indisponible avec la configuration actuelle. Pour le choisir :"))
            lines += [f"  - {describe_reason(code)}" for code in self._blockers]
            lines.append("")
        effective = "native" if engine == "native" and not self._blockers else "python"
        cores = cpu_info().usable_cores
        workers = resolved_worker_count(self._workers, effective, cores)
        lines.append(_("Au prochain démarrage : {run}.").format(run=describe_run(effective, workers)))
        notice = worker_count_notice(self._workers, effective, cores)
        if notice:
            lines.append(notice)
        lines.append(_("Nombre de processus : écran « Résistance et limites ». Changer de moteur demande un "
                       "redémarrage complet."))
        self.query_one("#engine-hint", Static).update("\n".join(lines))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "back":
            self.dismiss()
            return
        if event.button.id == "save":
            self._save()

    def _save(self) -> None:
        error_widget = self.query_one("#form-error", Static)
        load_result = load_config(self._container.configuration, self._container.config_file)
        if not load_result.success:
            error_widget.update(_("Erreur de configuration : ") + "; ".join(load_result.errors))
            return
        assert load_result.config is not None

        port_text = self.query_one("#port-input", Input).value.strip()
        try:
            port = int(port_text)
        except ValueError:
            error_widget.update(_("Port invalide (nombre attendu) : {port_text!r}").format(port_text=port_text))
            return

        index_files = tuple(
            item.strip() for item in self.query_one("#index-files-input", Input).value.split(",") if item.strip()
        )
        new_server = replace(
            load_result.config.server,
            bind=self.query_one("#bind-input", Input).value.strip(),
            port=port,
            server_name=self.query_one("#server-name-input", Input).value.strip(),
            index_files=index_files,
            engine=self._selected_engine(),
        )
        new_config = replace(load_result.config, server=new_server)

        errors = validate_config(new_config)
        if errors:
            error_widget.update(_("Erreur de validation :\n") + "\n".join(f"  - {e}" for e in errors))
            return

        previous = load_result.config
        effective = "native" if new_server.engine == "native" and not self._blockers else "python"
        maximum = max_workers(effective, cpu_info().usable_cores)
        if new_server.engine != previous.server.engine and new_server.workers > maximum:
            clamped = replace(new_config, server=replace(new_server, workers=maximum))
            engine = _("moteur natif") if effective == "native" else _("moteur Python")
            message = _(
                "Le nombre de processus enregistré ({workers}) dépasse le maximum du {engine} sur cette machine "
                "({maximum}). Enregistrer en le ramenant à {maximum} ?"
            ).format(workers=new_server.workers, engine=engine, maximum=maximum)

            def answered(confirmed: bool | None) -> None:
                if confirmed:
                    self._write(clamped, previous)

            self.app.push_screen(ConfirmScreen(title=_("NOMBRE DE PROCESSUS"), message=message), answered)
            return
        self._write(new_config, previous)

    def _write(self, new_config: OmegaServConfig, previous: OmegaServConfig) -> None:
        new_server = new_config.server
        self._container.configuration.save(self._container.config_file, new_config)
        self._workers = new_server.workers
        self.query_one("#form-error", Static).update("")
        self._refresh_engine_hint()
        if new_server.engine != previous.server.engine:
            notify_restart_required(
                self, self._container,
                _("Enregistré - le changement de moteur HTTP ne prend effet qu'au REDÉMARRAGE COMPLET (un "
                  "rechargement est refusé)."),
            )
        elif new_server.bind != previous.server.bind or new_server.port != previous.server.port:
            notify_restart_required(
                self, self._container,
                _("Enregistré - mais bind/port nécessitent un REDÉMARRAGE COMPLET pour prendre "
                "effet (jamais un simple rechargement, le socket d'écoute n'est jamais retouché)."),
            )
        else:
            notify_reload_required(self, self._container, _("Configuration de base enregistrée."))
