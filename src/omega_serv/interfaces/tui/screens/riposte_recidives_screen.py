"""RIPOSTE - Recidives (topo §6.4-4 ; lot 5) : les sources suivies, leurs retours, le palier atteint et le
suivant, la chronologie (episodes, classes d'attaque, bans, leurres) ; « Voir ses actions » et « Oublier
cette source » (donnees personnelles : retention bornee, effacement sur demande ; refuse par le processus
tant qu'une action court contre elle)."""
from __future__ import annotations

from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, VerticalScroll
from textual.widgets import Button, DataTable, Footer, Header, Static

from omega_serv.application.riposte.console import riposte_config_of
from omega_serv.core.i18n import _
from omega_serv.domain.security.riposte.history import next_tier_index
from omega_serv.interfaces.cli.riposte_text import format_duration
from omega_serv.interfaces.tui.screens._base import OmegaScreen
from omega_serv.interfaces.tui.screens._riposte_access import (
    RiposteAccessMixin,
    StoreUnavailable,
    cell,
    local_time,
    show,
)
from omega_serv.interfaces.tui.screens.confirm import ConfirmScreen
from omega_serv.interfaces.tui.screens.riposte_actions_screen import RiposteActionsScreen

if TYPE_CHECKING:
    from datetime import datetime

    from omega_serv.bootstrap.container import DependencyContainer
    from omega_serv.domain.security.riposte.config import RiposteConfig
    from omega_serv.domain.security.riposte.history import SourceHistory

LIST_LIMIT = 500



class RiposteRecidivesScreen(RiposteAccessMixin, OmegaScreen):
    def __init__(self, *, container: DependencyContainer) -> None:
        super().__init__()
        self._container = container
        self._sources: dict[str, SourceHistory] = {}
        self._selected: str | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll(classes="omega-panel"):
            yield Static(_("RIPOSTE - RÉCIDIVES"), classes="omega-title")
            yield Static(
                _("Un retour = un nouvel épisode d'attaque après un silence. Chaque action qui compte dans la récidive "
                  "fait monter le palier suivant ; une fenêtre de récidive calme ramène au premier palier."),
                classes="omega-hint",
            )
            yield Static("", id="recidives-error", classes="omega-hint")
            yield DataTable(id="sources-table", classes="omega-riposte-table")
            yield Static("", id="source-detail", classes="omega-hint")
        with Horizontal(classes="omega-actions omega-riposte-actions"):
            with Container(classes="omega-btn-frame"):
                yield Button(_("Voir ses actions"), id="show-actions", disabled=True)
            with Container(classes="omega-btn-frame"):
                yield Button(_("Oublier cette source"), id="forget", variant="error", disabled=True)
            with Container(classes="omega-btn-frame"):
                yield Button(_("Rafraîchir"), id="refresh")
            with Container(classes="omega-btn-frame"):
                yield Button(_("Retour"), id="back")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#sources-table", DataTable)
        table.cursor_type = "row"
        table.add_columns(_("Source"), _("Épisodes"), _("Actions"), _("Palier suivant"), _("Dernière activité"))
        self._refresh()

    def _refresh(self) -> None:
        self._select(None)
        table = self.query_one("#sources-table", DataTable)
        table.clear()
        self._sources = {}
        error = self.query_one("#recidives-error", Static)
        config = self._load_riposte_config()
        if config is None:
            return
        riposte = riposte_config_of(config)
        try:
            with self._riposte_store(config) as store:
                rows = store.list_sources(LIST_LIMIT)
        except StoreUnavailable as problem:
            show(error, str(problem))
            return
        show(error, "" if rows else _("Aucune source suivie pour l'instant."))
        now = self._container.clock.now()
        for history, updated_at in rows:
            self._sources[history.ip] = history
            table.add_row(cell(history.ip), cell(str(len(history.episodes))), cell(str(len(history.actions))),
                          cell(self._next_tier(history, riposte, now)), cell(local_time(updated_at)), key=history.ip)

    @staticmethod
    def _next_tier(history: SourceHistory, riposte: RiposteConfig, now: datetime) -> str:
        tiers = riposte.tiers_seconds
        index = next_tier_index(history, now, recidive_window_seconds=riposte.recidive_window_seconds,
                                tier_count=len(tiers))
        return _("{n} ({duration})").format(n=index + 1, duration=format_duration(tiers[index]))

    def _select(self, ip: str | None) -> None:
        self._selected = ip
        self.query_one("#show-actions", Button).disabled = ip is None
        self.query_one("#forget", Button).disabled = ip is None
        history = self._sources.get(ip) if ip else None
        show(self.query_one("#source-detail", Static), "" if history is None else "\n".join(self._chronology(history)))

    @staticmethod
    def _chronology(history: SourceHistory) -> list[str]:
        """Episodes et actions melanges dans l'ordre du temps."""
        entries: list[tuple[datetime, str]] = []
        for episode in history.episodes:
            text = _("Épisode : {attacks} attaque(s) [{classes}], leurres {decoys}, refus blocklist {blocked}").format(
                attacks=episode.attacks, classes=", ".join(episode.attack_classes) or "-",
                decoys=episode.decoy_hits, blocked=episode.blocklist_hits)
            if episode.max_level:
                text += _(", niveau {level}").format(level=episode.max_level)
            entries.append((episode.started_at, text))
        for action in history.actions:
            text = _("Action {policy} palier {tier}, jusqu'au {end}").format(
                policy=action.policy_id, tier=action.tier_index + 1, end=local_time(action.ends_at))
            if not action.counts_for_recidive:
                text += " - " + _("ne compte pas dans la récidive")
            entries.append((action.taken_at, text))
        lines = [_("Chronologie de {ip} :").format(ip=history.ip)]
        lines += [f"  {local_time(moment)}  {text}" for moment, text in sorted(entries, key=lambda entry: entry[0])]
        return lines

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        self._select(str(event.row_key.value))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id
        if button_id == "back":
            self.dismiss()
        elif button_id == "refresh":
            self._refresh()
        elif button_id == "show-actions" and self._selected is not None:
            self.app.push_screen(RiposteActionsScreen(container=self._container, ip=self._selected))
        elif button_id == "forget" and self._selected is not None:
            ip = self._selected
            self.app.push_screen(ConfirmScreen(
                title=_("OUBLIER CETTE SOURCE"),
                message=_("Effacer toute la mémoire de RIPOSTE sur {ip} (épisodes, paliers) ? Son prochain retour sera "
                          "traité comme une première fois. Refusé tant qu'une action est en cours contre elle.").format(ip=ip),
            ), lambda confirmed: self._forget(ip, confirmed))

    def _forget(self, ip: str, confirmed: bool | None) -> None:
        if not confirmed:
            return
        config = self._load_riposte_config()
        if config is not None:
            self._send_commands(config, [("forget_source", {"ip": ip})], done=self._refresh)
