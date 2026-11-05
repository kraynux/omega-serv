"""RIPOSTE - Politiques (topo §6.4-2, §6.5 a §6.7 ; lot 5) : tableau (etat, nom, condition, reponse) et
Ajouter (scenario pret a charger, copie d'une politique, Custom), Modifier, Activer / Desactiver, Retirer.

- Desactiver (topo §6.6) : avec le nombre d'actions en cours de la regle, [Desactiver et lever ses actions
  en cours] [Desactiver seulement] [Annuler]. La regle reste listee (rien ne disparait, §6.7).
- Activer repasse par la mesure et la confirmation (l'effet mesure est montre avant d'activer).
- Retirer supprime la regle de la configuration ; ses actions passees restent dans l'historique sous son
  identifiant."""
from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, VerticalScroll
from textual.widgets import Button, DataTable, Footer, Header, Static

from omega_serv.application.riposte.console import (
    deception_available,
    journal_paths,
    measure_policy,
    remove_policy,
    riposte_config_of,
    set_policy_enabled,
    unique_policy_id,
    waf_enabled,
)
from omega_serv.core.i18n import _
from omega_serv.domain.security.riposte.config import RipostePolicy
from omega_serv.domain.security.riposte.scenarios import SCENARIOS
from omega_serv.interfaces.cli.riposte_text import (
    action_short_label,
    format_duration,
    format_measure,
    policy_lines,
)
from omega_serv.interfaces.tui.screens._base import OmegaScreen
from omega_serv.interfaces.tui.screens._riposte_access import (
    RiposteAccessMixin,
    StoreUnavailable,
    cell,
    show,
)
from omega_serv.interfaces.tui.screens.choice_screen import Choice, ChoiceResult, ChoiceScreen
from omega_serv.interfaces.tui.screens.confirm import ConfirmScreen
from omega_serv.interfaces.tui.screens.riposte_policy_form_screen import (
    MEASURE_DAYS,
    RipostePolicyFormScreen,
)

if TYPE_CHECKING:
    from omega_serv.application.riposte.measure import MeasureResult
    from omega_serv.bootstrap.container import DependencyContainer
    from omega_serv.domain.config.entities import OmegaServConfig


def _condition(policy: RipostePolicy) -> str:
    text = _("{returns} épisode(s) en {within}").format(returns=policy.returns, within=format_duration(policy.within_seconds))
    if policy.attack_classes:
        text += " [" + ", ".join(policy.attack_classes) + "]"
    return text


class RipostePoliciesScreen(RiposteAccessMixin, OmegaScreen):
    def __init__(self, *, container: DependencyContainer) -> None:
        super().__init__()
        self._container = container
        self._policies: dict[str, RipostePolicy] = {}
        self._selected: RipostePolicy | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll(classes="omega-panel"):
            yield Static(_("RIPOSTE - POLITIQUES"), classes="omega-title")
            yield Static(
                _("Une politique active agit automatiquement. Une politique désactivée reste listée, avec ses réglages ; "
                  "ses actions déjà prises restent visibles dans Actions."),
                classes="omega-hint",
            )
            yield Static("", id="policies-warnings", classes="omega-hint")
            yield DataTable(id="policies-table", classes="omega-riposte-table")
            yield Static("", id="policy-detail", classes="omega-hint")
        with Horizontal(classes="omega-actions omega-riposte-actions"):
            with Container(classes="omega-btn-frame"):
                yield Button(_("Ajouter"), id="add", variant="primary")
            with Container(classes="omega-btn-frame"):
                yield Button(_("Modifier"), id="edit", disabled=True)
            with Container(classes="omega-btn-frame"):
                yield Button(_("Désactiver"), id="toggle", disabled=True)
            with Container(classes="omega-btn-frame"):
                yield Button(_("Retirer"), id="remove", variant="error", disabled=True)
            with Container(classes="omega-btn-frame"):
                yield Button(_("Retour"), id="back")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#policies-table", DataTable)
        table.cursor_type = "row"
        table.add_columns(_("État"), _("Politique"), _("Condition"), _("Réponse"))
        self._refresh()

    def _refresh(self) -> None:
        self._select(None)
        table = self.query_one("#policies-table", DataTable)
        table.clear()
        config = self._load_riposte_config()
        if config is None:
            return
        policies = riposte_config_of(config).policies
        self._policies = {p.id: p for p in policies}
        warnings = []
        if not policies:
            warnings.append(_("Aucune politique : « Ajouter » propose des scénarios prêts à charger."))
        if any(p.enabled and p.action != "decoy" for p in policies) and not waf_enabled(config):
            warnings.append(_("WAF inactif : activer le WAF pour les actions de ban."))
        if any(p.enabled and p.action == "decoy" for p in policies) and not deception_available(config):
            warnings.append(_("Leurres inactifs : activer Active Defense et ses leurres."))
        show(self.query_one("#policies-warnings", Static), "\n".join(warnings))
        for policy in policies:
            state = _("✔ active") if policy.enabled else _("✘ désactivée")
            table.add_row(cell(state), cell(f"{policy.id} - {policy.name}"), cell(_condition(policy)),
                          cell(action_short_label(policy.action)), key=policy.id)

    def _select(self, policy: RipostePolicy | None) -> None:
        self._selected = policy
        for button_id in ("edit", "toggle", "remove"):
            self.query_one(f"#{button_id}", Button).disabled = policy is None
        toggle = self.query_one("#toggle", Button)
        toggle.label = _("Activer") if policy is not None and not policy.enabled else _("Désactiver")
        detail = self.query_one("#policy-detail", Static)
        config = self._load_riposte_config() if policy is not None else None
        if policy is None or config is None:
            show(detail, "")
            return
        show(detail, "\n".join(policy_lines(policy, riposte_config_of(config), self._service_name())))

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        self._select(self._policies.get(str(event.row_key.value)))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id
        policy = self._selected
        if button_id == "back":
            self.dismiss()
        elif button_id == "add":
            self._ask_origin()
        elif button_id == "edit" and policy is not None:
            self._open_form(policy, replaces=policy.id, title=_("MODIFIER LA POLITIQUE {id}").format(id=policy.id))
        elif button_id == "toggle" and policy is not None:
            if policy.enabled:
                self._ask_disable(policy)
            else:
                self._measure_then_enable(policy)
        elif button_id == "remove" and policy is not None:
            self.app.push_screen(ConfirmScreen(
                title=_("RETIRER LA POLITIQUE"),
                message=_("Supprimer {id} de la configuration ? Ses actions passées restent dans l'historique sous son "
                          "nom ; ses actions en cours vont jusqu'à leur échéance (les lever dans Actions).").format(id=policy.id),
            ), lambda confirmed: self._remove(policy, confirmed))

    # --- Ajouter : trois points d'entree -------------------------------------------------------

    def _open_form(self, policy: RipostePolicy, *, replaces: str | None, title: str) -> None:
        self.app.push_screen(RipostePolicyFormScreen(container=self._container, policy=policy, replaces=replaces,
                                                     title=title), lambda _result: self._refresh())

    def _ask_origin(self) -> None:
        choices = [Choice("scenario", _("Scénario prêt à charger"), "primary")]
        if self._policies:
            choices.append(Choice("copy", _("Copier une politique")))
        choices += [Choice("custom", _("Custom (valeurs par défaut sûres)")), Choice("cancel", _("Annuler"))]
        self.app.push_screen(ChoiceScreen(
            title=_("AJOUTER UNE POLITIQUE"),
            message=_("Partir d'un scénario, d'une politique existante ou d'un formulaire vierge : tout reste modifiable "
                      "avant l'enregistrement."),
            choices=choices,
        ), self._origin_chosen)

    def _origin_chosen(self, result: ChoiceResult | None) -> None:
        if result is None:
            return
        title = _("AJOUTER UNE POLITIQUE")
        if result.choice == "custom":
            self._open_form(RipostePolicy(id="", name="", origin="custom"), replaces=None, title=title)
        elif result.choice == "scenario":
            self.app.push_screen(ChoiceScreen(
                title=_("SCÉNARIOS PRÊTS À CHARGER"),
                message="\n".join(f"- {s.name} : {s.what_it_does}" for s in SCENARIOS),
                choices=[*(Choice(s.id, s.name) for s in SCENARIOS), Choice("cancel", _("Annuler"))],
            ), self._scenario_chosen)
        elif result.choice == "copy":
            self.app.push_screen(ChoiceScreen(
                title=_("COPIER UNE POLITIQUE"), message=_("Politique à copier :"),
                choices=[*(Choice(p.id, f"{p.id} - {p.name}") for p in self._policies.values()),
                         Choice("cancel", _("Annuler"))],
            ), self._copy_chosen)

    def _scenario_chosen(self, result: ChoiceResult | None) -> None:
        scenario = next((s for s in SCENARIOS if result is not None and s.id == result.choice), None)
        if scenario is None:
            return
        policy = replace(scenario.policy, id=unique_policy_id(scenario.policy.id, set(self._policies)))
        self._open_form(policy, replaces=None, title=_("AJOUTER : {name}").format(name=scenario.name))

    def _copy_chosen(self, result: ChoiceResult | None) -> None:
        source = self._policies.get(result.choice) if result is not None else None
        if source is None:
            return
        policy = replace(source, id=unique_policy_id(source.id, set(self._policies)), origin=f"copy:{source.id}")
        self._open_form(policy, replaces=None, title=_("COPIER {id}").format(id=source.id))

    # --- Activer / desactiver / retirer -------------------------------------------------------

    def _in_progress_count(self, config: OmegaServConfig, policy_id: str) -> int:
        try:
            with self._riposte_store(config) as store:
                return len(store.list_actions(in_progress=True, limit=10_000, policy_id=policy_id))
        except StoreUnavailable:
            return 0

    def _ask_disable(self, policy: RipostePolicy) -> None:
        config = self._load_riposte_config()
        if config is None:
            return
        count = self._in_progress_count(config, policy.id)
        self.app.push_screen(ChoiceScreen(
            title=_("DÉSACTIVER {id}").format(id=policy.id),
            message=_("La règle ne déclenchera plus rien ; elle reste listée avec ses réglages. Actions en cours de "
                      "cette règle : {count}. « Désactiver seulement » : elles vont jusqu'à leur échéance.").format(count=count),
            choices=[
                Choice("revoke", _("Désactiver et lever ses actions en cours"), "error"),
                Choice("only", _("Désactiver seulement"), "error"),
                Choice("cancel", _("Annuler"), "primary"),
            ],
        ), lambda result: self._disable(policy, result))

    def _disable(self, policy: RipostePolicy, result: ChoiceResult | None) -> None:
        config = self._load_riposte_config() if result is not None else None
        if config is None or result is None:
            return
        saved = set_policy_enabled(self._container.configuration, self._container.config_file, config, policy.id, False)
        if not saved.ok:
            self.app.notify(_("Politique inconnue : {id}").format(id=policy.id), severity="error")
            return
        self.app.notify(_("Politique {id} désactivée.").format(id=policy.id))
        extra = [("revoke_policy", {"policy_id": policy.id})] if result.choice == "revoke" else []
        self._reload_riposte(config, extra, done=self._refresh)

    def _measure_then_enable(self, policy: RipostePolicy) -> None:
        config = self._load_riposte_config()
        if config is None:
            return
        reader = self._container.riposte_journal_reader
        if reader is None:
            self._confirm_enable(config, policy, [_("Politique non mesurée.")])
            return
        self.app.notify(_("Mesure en cours..."))
        now = self._container.clock.now()
        paths = journal_paths(config, self._container.project_root)

        def work() -> None:
            try:
                result: MeasureResult | str = measure_policy(config, policy, reader(*paths), now, days=MEASURE_DAYS)
            except OSError as error:
                result = _("Journaux illisibles : {error}").format(error=error)
            lines = [result] if isinstance(result, str) else format_measure(result)
            self.app.call_from_thread(self._confirm_enable, config, policy, lines)

        self.run_worker(work, thread=True, exclusive=True, group="riposte-measure")

    def _confirm_enable(self, config: OmegaServConfig, policy: RipostePolicy, measured: list[str]) -> None:
        self.app.push_screen(ChoiceScreen(
            title=_("ACTIVER {id}").format(id=policy.id),
            message="\n\n".join(("\n".join(measured), _(
                "Une politique activée agit automatiquement, sans validation action par action (levée possible dans "
                "Actions, arrêt d'urgence dans État)."))),
            choices=[Choice("activate", _("Activer"), "error"), Choice("cancel", _("Annuler"), "primary")],
        ), lambda result: self._enable(config, policy, result))

    def _enable(self, config: OmegaServConfig, policy: RipostePolicy, result: ChoiceResult | None) -> None:
        if result is None:
            return
        saved = set_policy_enabled(self._container.configuration, self._container.config_file, config, policy.id, True)
        if saved.unknown:
            self.app.notify(_("Politique inconnue : {id}").format(id=policy.id), severity="error")
            return
        if saved.errors:
            self.app.notify(_("Configuration RIPOSTE invalide : ") + "; ".join(saved.errors), severity="error")
            return
        self.app.notify(_("Politique {id} activée.").format(id=policy.id))
        self._reload_riposte(config, done=self._refresh)

    def _remove(self, policy: RipostePolicy, confirmed: bool | None) -> None:
        config = self._load_riposte_config() if confirmed else None
        if config is None:
            return
        remove_policy(self._container.configuration, self._container.config_file, config, policy.id)
        self.app.notify(_("Politique {id} retirée.").format(id=policy.id))
        self._reload_riposte(config, done=self._refresh)
