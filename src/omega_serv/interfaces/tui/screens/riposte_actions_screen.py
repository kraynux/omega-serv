"""RIPOSTE - Actions (topo §6.4-3, §6.6, §6.7 ; lot 5) : le registre des actions, filtre En cours /
Terminees (rien ne disparait : une action levee reste dans les terminees, avec qui l'a levee et quand),
detail, « Lever » (confirme : [Lever] [Lever et exempter cette source...] [Annuler] + case « ne pas compter
ce ban dans la recidive ») et « Ne compte pas dans la recidive » pour une action deja terminee.

L'ecran ne touche jamais au registre : il depose une commande, executee par le processus RIPOSTE."""
from __future__ import annotations

from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, VerticalScroll
from textual.widgets import Button, DataTable, Footer, Header, Static

from omega_serv.core.i18n import _
from omega_serv.interfaces.cli.riposte_text import (
    action_detail_label,
    action_label,
    action_short_label,
    action_state_label,
    finished_by_label,
    format_duration,
    network_ban_notice,
)
from omega_serv.interfaces.tui.screens._base import OmegaScreen
from omega_serv.interfaces.tui.screens._riposte_access import (
    RiposteAccessMixin,
    StoreUnavailable,
    cell,
    local_time,
    show,
)
from omega_serv.interfaces.tui.screens.choice_screen import Choice, ChoiceResult, ChoiceScreen

if TYPE_CHECKING:

    from omega_serv.bootstrap.container import DependencyContainer
    from omega_serv.domain.security.riposte.actions import RiposteAction

LIST_LIMIT = 500



class RiposteActionsScreen(RiposteAccessMixin, OmegaScreen):
    def __init__(self, *, container: DependencyContainer, ip: str | None = None) -> None:
        super().__init__()
        self._container = container
        self._ip = ip
        """Filtre optionnel (ouverture depuis Recidives)."""
        self._in_progress = True
        self._actions: dict[str, RiposteAction] = {}
        self._selected: RiposteAction | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll(classes="omega-panel"):
            yield Static(_("RIPOSTE - ACTIONS"), classes="omega-title")
            yield Static(
                _("Une action levée quitte « en cours » mais reste visible dans « terminées ». Si la source "
                  "continue, la règle la bannit de nouveau : « Lever et exempter » l'évite."),
                classes="omega-hint",
            )
            yield Static("", id="actions-error", classes="omega-hint")
            with Horizontal(classes="omega-actions"):
                with Container(classes="omega-btn-frame"):
                    yield Button(_("En cours"), id="filter-in-progress", variant="primary")
                with Container(classes="omega-btn-frame"):
                    yield Button(_("Terminées"), id="filter-finished")
            yield DataTable(id="actions-table", classes="omega-riposte-table")
            yield Static("", id="action-detail", classes="omega-hint")
        with Horizontal(classes="omega-actions omega-riposte-actions"):
            with Container(classes="omega-btn-frame"):
                yield Button(_("Lever"), id="revoke", variant="error", disabled=True)
            with Container(classes="omega-btn-frame"):
                yield Button(_("Ne compte pas dans la récidive"), id="not-recidive", disabled=True)
            with Container(classes="omega-btn-frame"):
                yield Button(_("Rafraîchir"), id="refresh")
            with Container(classes="omega-btn-frame"):
                yield Button(_("Retour"), id="back")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#actions-table", DataTable)
        table.cursor_type = "row"
        table.add_columns(_("Source"), _("Action"), _("Palier"), _("Depuis"), _("Fin"), _("Politique"), _("État"))
        self._refresh()

    def _refresh(self) -> None:
        self._select(None)
        table = self.query_one("#actions-table", DataTable)
        table.clear()
        self._actions = {}
        error = self.query_one("#actions-error", Static)
        config = self._load_riposte_config()
        if config is None:
            return
        try:
            with self._riposte_store(config) as store:
                current = store.list_actions(in_progress=True, limit=LIST_LIMIT, ip=self._ip)
                finished = store.list_actions(in_progress=False, limit=LIST_LIMIT, ip=self._ip)
        except StoreUnavailable as problem:
            show(error, str(problem))
            return
        show(error, _("Source : {ip}").format(ip=self._ip) if self._ip else "")
        self.query_one("#filter-in-progress", Button).label = _("En cours ({count})").format(count=len(current))
        self.query_one("#filter-finished", Button).label = _("Terminées ({count})").format(count=len(finished))
        self.query_one("#filter-in-progress", Button).variant = "primary" if self._in_progress else "default"
        self.query_one("#filter-finished", Button).variant = "default" if self._in_progress else "primary"
        shown = current if self._in_progress else finished
        now = self._container.clock.now()
        for action in shown:
            self._actions[action.id] = action
            if action.in_progress:
                end = _("dans {duration}").format(duration=format_duration(max(60, int((action.ends_at - now).total_seconds()) // 60 * 60)))
            else:
                end = local_time(action.finished_at or action.ends_at, short=True)
            table.add_row(
                cell(action.ip), cell(action_short_label(action.kind)),
                cell(str(action.tier_index + 1) if action.tier_index is not None else "-"),
                cell(local_time(action.created_at, short=True)), cell(end), cell(action.policy_id),
                cell(action_state_label(action.state)), key=action.id,
            )
        if not shown:
            show(self.query_one("#action-detail", Static),
                _("Aucune action en cours.") if self._in_progress else _("Aucune action terminée."))

    def _select(self, action: RiposteAction | None) -> None:
        self._selected = action
        self.query_one("#revoke", Button).disabled = action is None or not action.in_progress
        self.query_one("#not-recidive", Button).disabled = action is None or not action.counts_for_recidive
        show(self.query_one("#action-detail", Static), "" if action is None else "\n".join(self._detail(action)))

    def _detail(self, action: RiposteAction) -> list[str]:
        lines = [
            _("Action {id} - {action} pour {ip} ({state})").format(
                id=action.id, action=action_label(action.kind), ip=action.ip, state=action_state_label(action.state)),
            _("Créée le {when} (événement {event})").format(when=local_time(action.created_at), event=action.event_id or "-"),
            _("Échéance : {when}").format(when=local_time(action.ends_at)),
        ]
        if action.decoy_profile:
            lines.append(_("Leurre {profile} pour : {subjects}").format(
                profile=action.decoy_profile, subjects=", ".join(action.subject_ids) or "-"))
        if action.finished_at is not None:
            lines.append(_("Terminée le {when} : {by}").format(when=local_time(action.finished_at),
                                                              by=finished_by_label(action.finished_by)))
        if action.detail:
            lines.append(action_detail_label(action.detail))
        if not action.counts_for_recidive:
            lines.append(_("Ne compte pas dans la récidive."))
        if action.kind == "local_and_network_ban" and action.state in ("applied", "revoked", "expired"):
            lines.append(network_ban_notice(self._service_name(), self._duration(action)))
        return lines

    @staticmethod
    def _duration(action: RiposteAction) -> int:
        return int((action.ends_at - action.created_at).total_seconds())

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        self._select(self._actions.get(str(event.row_key.value)))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id
        if button_id == "back":
            self.dismiss()
        elif button_id == "refresh":
            self._refresh()
        elif button_id in ("filter-in-progress", "filter-finished"):
            self._in_progress = button_id == "filter-in-progress"
            self._refresh()
        elif button_id == "revoke" and self._selected is not None:
            self._ask_revoke(self._selected)
        elif button_id == "not-recidive" and self._selected is not None:
            self._send(("not_recidive", {"action_id": self._selected.id}))

    def _ask_revoke(self, action: RiposteAction) -> None:
        self.app.push_screen(ChoiceScreen(
            title=_("LEVER L'ACTION"),
            message=_("Lever {action} sur {ip} (politique {policy}) ? Si la source continue, la règle la bannira de "
                      "nouveau au prochain événement - sauf si elle est exemptée.").format(
                action=action_label(action.kind), ip=action.ip, policy=action.policy_id)
            + ("\n\n" + _("Seul le ban local est levé.") + " " + network_ban_notice(self._service_name(), self._duration(action))
               if action.kind == "local_and_network_ban" else ""),
            choices=[
                Choice("revoke", _("Lever"), "error"),
                Choice("exempt", _("Lever et exempter cette source..."), "error"),
                Choice("cancel", _("Annuler"), "primary"),
            ],
            checkbox=_("Ne pas compter ce ban dans la récidive (faux positif)") if action.counts_for_recidive else None,
        ), lambda result: self._revoke_chosen(action, result))

    def _revoke_chosen(self, action: RiposteAction, result: ChoiceResult | None) -> None:
        if result is None:
            return
        if result.choice == "revoke":
            self._send(("revoke", {"action_id": action.id, "exempt": None, "not_recidive": result.checked}))
            return
        self.app.push_screen(ChoiceScreen(
            title=_("EXEMPTER {ip}").format(ip=action.ip),
            message=_("Pendant l'exemption, RIPOSTE ne prend plus aucune action contre cette source (les exclusions "
                      "du WAF s'appliquent toujours en plus). Durée :"),
            choices=[
                Choice("24h", _("24 heures")),
                Choice("7d", _("7 jours")),
                Choice("forever", _("Toujours (jusqu'au retrait manuel, écran Réglages)"), "error"),
                Choice("cancel", _("Annuler"), "primary"),
            ],
        ), lambda exempt: self._exempt_chosen(action, result.checked, exempt))

    def _exempt_chosen(self, action: RiposteAction, not_recidive: bool, exempt: ChoiceResult | None) -> None:
        if exempt is None:
            return
        self._send(("revoke", {"action_id": action.id, "exempt": exempt.choice, "not_recidive": not_recidive}))

    def _send(self, command: tuple[str, dict[str, object]]) -> None:
        config = self._load_riposte_config()
        if config is not None:
            self._send_commands(config, [command], done=self._refresh)
