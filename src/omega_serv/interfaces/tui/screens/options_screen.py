# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Ecran Options (plan interface §6, `option list/enable/disable`) -
liste des 10 options superposables connues avec leur etat actuel,
bascule directe (pas de formulaire de reglages detailles ici : ce sera
le role des sous-ecrans de configuration detaillee, plan interface §7)."""
from __future__ import annotations

from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Button, DataTable, Footer, Header, Static

from omega_serv.application.config.load_config import load_config
from omega_serv.application.config.manage_option import set_option_enabled
from omega_serv.domain.config.option import KNOWN_OPTION_NAMES
from omega_serv.interfaces.tui.screens._base import OmegaScreen
from omega_serv.interfaces.tui.screens.restart_prompt import (
    notify_reload_required,
    notify_restart_required,
)

if TYPE_CHECKING:
    from omega_serv.bootstrap.container import DependencyContainer


class OptionsScreen(OmegaScreen):
    def __init__(self, *, container: DependencyContainer) -> None:
        super().__init__()
        self._container = container
        self._selected_name: str | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(classes="omega-panel"):
            yield Static("OPTIONS", classes="omega-title")
            yield Static("", id="options-error", classes="omega-hint")
            yield DataTable(id="options-table")
            with Horizontal(classes="omega-actions"):
                with Container(classes="omega-btn-frame"):
                    yield Button("Activer", id="enable", variant="primary", disabled=True)
                with Container(classes="omega-btn-frame"):
                    yield Button("Desactiver", id="disable", variant="error", disabled=True)
                with Container(classes="omega-btn-frame"):
                    yield Button("Retour", id="back")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#options-table", DataTable)
        table.cursor_type = "row"
        table.add_columns("Option", "Etat")
        self._refresh_table()

    def _refresh_table(self) -> None:
        table = self.query_one("#options-table", DataTable)
        table.clear()
        result = load_config(self._container.configuration, self._container.config_file)
        if not result.success:
            self.query_one("#options-error", Static).update(
                "Configuration introuvable ou invalide : " + "; ".join(result.errors)
            )
            return
        assert result.config is not None
        self.query_one("#options-error", Static).update("")
        for name in sorted(KNOWN_OPTION_NAMES):
            option = result.config.options.get(name)
            state = "actif" if option is not None and option.enabled else "inactif"
            table.add_row(name, state, key=name)

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        self._selected_name = str(event.row_key.value)
        self.query_one("#enable", Button).disabled = False
        self.query_one("#disable", Button).disabled = False

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "back":
            self.dismiss()
            return
        if event.button.id in ("enable", "disable") and self._selected_name is not None:
            self._set_option(event.button.id == "enable")

    def _set_option(self, enabled: bool) -> None:
        assert self._selected_name is not None
        load_result = load_config(self._container.configuration, self._container.config_file)
        if not load_result.success:
            self.app.notify("Configuration introuvable ou invalide.", severity="error")
            return
        assert load_result.config is not None

        # Retour utilisateur 2026-09-11 (audit reload/restart) : activer
        # FastCGI (ou le reverse proxy sortant, meme caracteristique -
        # OMEGA-SERV_PLAN-DETAILLE_REVERSE_PROXY.md) pour la PREMIERE
        # FOIS (transition desactive->active) n'a jamais d'effet via un
        # simple rechargement - le client (FastCGI ou proxy) n'est
        # construit qu'au demarrage (build_server), jamais reconstruit
        # par reload_scoped. Modifier ses reglages une fois deja actif
        # au demarrage reste bien a chaud (pas de warning dans ce cas,
        # seulement a la transition elle-meme).
        was_enabled = self._selected_name in load_result.config.options and load_result.config.options[self._selected_name].enabled
        client_built_once_first_enable = (
            self._selected_name in ("fastcgi", "reverse_proxy") and enabled and not was_enabled
        )
        # Active Defense (retour utilisateur 2026-09-12) : cas ENCORE PLUS
        # strict que fastcgi/reverse_proxy - reload_scoped() ne touche
        # jamais _active_defense_config/_threat_state_repository/
        # _incident_repository/les collaborateurs deception (voir
        # infrastructure/server/asyncio_server.py::reload_scoped, deja
        # documente comme tel). Donc TOUTE bascule (activer OU
        # desactiver), pas seulement la premiere activation, exige un
        # redemarrage complet - jamais seulement a la transition
        # desactive->active comme fastcgi/reverse_proxy ci-dessus.
        active_defense_always_needs_restart = self._selected_name == "active_defense"

        result = set_option_enabled(load_result.config, self._selected_name, enabled)
        if not result.success:
            self.app.notify(result.message, severity="error")
            return
        assert result.new_config is not None
        self._container.configuration.save(self._container.config_file, result.new_config)
        if client_built_once_first_enable:
            notify_restart_required(
                self, self._container,
                f"{result.message} Necessite un REDEMARRAGE COMPLET pour prendre effet "
                "(un simple rechargement ne suffit pas pour une PREMIERE activation).",
            )
        elif active_defense_always_needs_restart:
            notify_restart_required(
                self, self._container,
                f"{result.message} Necessite un REDEMARRAGE COMPLET pour prendre effet "
                "(Active Defense n'est JAMAIS recharge a chaud, meme pour la desactiver).",
            )
        else:
            # Retour utilisateur (guide d'aide, point 4) : angle mort
            # reel - meme pour ces options "hot-reloadables", le
            # processus DEJA LANCE ne relit jamais le fichier de
            # configuration tout seul ; sans cet avertissement,
            # l'utilisateur croit (a tort) que l'activation est
            # immediate et ne comprend pas pourquoi rien ne change tant
            # qu'il n'a pas recharge/redemarre.
            notify_reload_required(self, self._container, result.message)
        self._refresh_table()
