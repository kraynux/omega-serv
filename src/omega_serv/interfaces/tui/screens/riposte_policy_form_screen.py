"""RIPOSTE - formulaire de politique (topo §6.5 ; lot 5) : un seul formulaire, trois points d'entree
(scenario pret a charger, copie d'une politique, Custom), meme esprit que l'assistant de zone CSP : chaque
champ montre sa valeur reelle, un exemple en grise quand il est vide et une ligne d'explication.

Sections : Declencheur (niveau Active Defense minimal, classes d'attaque, N retours en J jours, visites de
leurre), Reponse (action, paliers, leurre), Garde-fous (actions simultanees par source, exclusions heritees
du WAF en lecture seule).

« Mesurer » rejoue la politique sur les journaux des 7 derniers jours (hors du fil de l'interface, sur
bouton, jamais a chaque frappe). « Enregistrer » : validation (rien n'est ecrit si un champ est refuse),
confirmation nommee pour un reglage moins prudent que la norme (duree > 7 j, niveau « suspicious »), puis
[Activer] [Enregistrer sans activer] [Annuler] avec l'effet mesure (ou « non mesuree »). Une politique
activee agit automatiquement, sans validation action par action."""
from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, VerticalScroll
from textual.widgets import Button, Footer, Header, Input, Select, Static

from omega_serv.application.riposte.console import (
    deception_available,
    decoy_profiles,
    journal_paths,
    measure_policy,
    policy_problems,
    required_risks,
    riposte_config_of,
    save_policy,
    waf_enabled,
)
from omega_serv.application.riposte.safety import riposte_exempt_networks
from omega_serv.core.i18n import _
from omega_serv.domain.security.active_defense.value_objects import KNOWN_ATTACK_CLASSES
from omega_serv.domain.security.riposte.config import DEFAULT_TIERS_SECONDS, RipostePolicy
from omega_serv.domain.security.riposte.durations import (
    duration_text,
    durations_text,
    parse_duration,
    parse_durations,
)
from omega_serv.interfaces.cli.riposte_text import action_label, format_measure, network_jails_text
from omega_serv.interfaces.tui.screens._base import OmegaScreen
from omega_serv.interfaces.tui.screens._riposte_access import (
    RiposteAccessMixin,
    show,
)
from omega_serv.interfaces.tui.screens.choice_screen import Choice, ChoiceResult, ChoiceScreen
from omega_serv.interfaces.tui.screens.confirm import ConfirmScreen

if TYPE_CHECKING:
    from omega_serv.application.riposte.measure import MeasureResult
    from omega_serv.bootstrap.container import DependencyContainer
    from omega_serv.domain.config.entities import OmegaServConfig

MEASURE_DAYS = 7
_LEVELS = ("hostile", "contained", "suspicious")
_ACTIONS = ("local_ban", "local_and_network_ban", "decoy")
_CLASSES_EXAMPLE = ("scan", "sqli")


def risk_text(risk: str) -> str:
    return {
        "long_duration": _("une durée au-delà de 7 jours (ban ou leurre)"),
        "suspicious_level": _("une réaction dès le niveau « suspicious » d'Active Defense (plus tôt, plus de faux positifs)"),
    }.get(risk, risk)


class RipostePolicyFormScreen(RiposteAccessMixin, OmegaScreen):
    def __init__(self, *, container: DependencyContainer, policy: RipostePolicy, replaces: str | None = None,
                 title: str) -> None:
        """`replaces` : identifiant de la politique modifiee (None = ajout)."""
        super().__init__()
        self._container = container
        self._policy = policy
        self._replaces = replaces
        self._title = title
        self._measured: tuple[RipostePolicy, list[str]] | None = None

    def compose(self) -> ComposeResult:
        policy = self._policy
        yield Header()
        with VerticalScroll(classes="omega-panel"):
            yield Static(self._title, classes="omega-title")
            yield Static("", id="form-error", classes="omega-hint")
            yield Static(_("Identifiant"), classes="omega-subtitle")
            yield Static(_("Minuscules, chiffres et tirets ; repris dans la blocklist et le registre des actions."),
                         classes="omega-hint")
            yield Input(value=policy.id, placeholder="scan-recidive", id="policy-id")
            yield Static(_("Nom"), classes="omega-subtitle")
            yield Input(value=policy.name, placeholder=_("Scanner récidiviste"), id="policy-name")

            yield Static(_("DÉCLENCHEUR"), classes="omega-subtitle")
            yield Static(_("Classes d'attaque"), classes="omega-subtitle")
            yield Static(_("Séparées par des virgules ; vide = toutes. Connues : {classes}.").format(
                classes=", ".join(sorted(KNOWN_ATTACK_CLASSES))), classes="omega-hint")
            yield Input(value=", ".join(policy.attack_classes), placeholder=", ".join(_CLASSES_EXAMPLE), id="policy-classes")
            yield Static(_("Nombre d'épisodes (retours)"), classes="omega-subtitle")
            yield Static(_("La règle agit au N-ième épisode d'attaque de la même IP dans la fenêtre ci-dessous "
                           "(1 = dès le premier)."), classes="omega-hint")
            yield Input(value=str(policy.returns), placeholder="3", id="policy-returns")
            yield Static(_("Fenêtre des retours"), classes="omega-subtitle")
            yield Static(_("Durée : un nombre suivi de s, m, h ou d (ex. 7d)."), classes="omega-hint")
            yield Input(value=duration_text(policy.within_seconds), placeholder="7d", id="policy-within")
            yield Static(_("Niveau Active Defense minimal"), classes="omega-subtitle")
            yield Static(_("Exiger qu'Active Defense ait classé la source à ce niveau pendant l'épisode."),
                         classes="omega-hint")
            yield Select([(_("aucun (non exigé)"), ""), *((level, level) for level in _LEVELS)],
                         value=policy.min_ad_level or "", allow_blank=False, id="policy-level")
            yield Static(_("Visites de leurre minimales"), classes="omega-subtitle")
            yield Static(_("0 = condition ignorée."), classes="omega-hint")
            yield Input(value=str(policy.decoy_hits), placeholder="0", id="policy-decoy-hits")

            yield Static(_("RÉPONSE"), classes="omega-subtitle")
            yield Static(_("Action"), classes="omega-subtitle")
            yield Static("", id="action-hint", classes="omega-hint")
            yield Select([(action_label(action), action) for action in _ACTIONS], value=policy.action,
                         allow_blank=False, id="policy-action")
            yield Static(_("Paliers de durée"), classes="omega-subtitle")
            yield Static(_("Vide = paliers globaux (Réglages). Un ban par retour, de plus en plus long. Ban réseau : "
                           "jails omega-jail de durée fixe (1 h, 6 h, 24 h, 7 j), chaque palier va à la plus longue "
                           "qui ne le dépasse pas."), classes="omega-hint")
            yield Input(value=durations_text(policy.tiers_seconds) if policy.tiers_seconds else "",
                        placeholder=durations_text(DEFAULT_TIERS_SECONDS), id="policy-tiers")
            yield Static(_("Profil de leurre (action « leurre »)"), classes="omega-subtitle")
            yield Static("", id="decoy-hint", classes="omega-hint")
            yield Select([], allow_blank=True, id="policy-decoy-profile")
            yield Static(_("Durée du leurre"), classes="omega-subtitle")
            yield Input(value=duration_text(policy.decoy_duration_seconds), placeholder="24h", id="policy-decoy-duration")
            yield Static(_("Portée : l'adresse IP seule."), classes="omega-hint")

            yield Static(_("GARDE-FOUS"), classes="omega-subtitle")
            yield Static(_("Actions simultanées au plus par source"), classes="omega-subtitle")
            yield Input(value=str(policy.max_active_per_source), placeholder="1", id="policy-max-per-source")
            yield Static(_("Exclusions héritées du WAF (lecture seule) et exemptions RIPOSTE"), classes="omega-subtitle")
            yield Static("", id="policy-exclusions", classes="omega-hint")

            yield Static(_("MESURE"), classes="omega-subtitle")
            yield Static(_("« Mesurer » rejoue cette politique sur les journaux des {days} derniers jours, sans rien "
                           "appliquer.").format(days=MEASURE_DAYS), classes="omega-hint")
            yield Static("", id="measure-result")
        with Horizontal(classes="omega-actions omega-riposte-actions"):
            with Container(classes="omega-btn-frame"):
                yield Button(_("Mesurer"), id="measure")
            with Container(classes="omega-btn-frame"):
                yield Button(_("Enregistrer"), id="save", variant="primary")
            with Container(classes="omega-btn-frame"):
                yield Button(_("Annuler"), id="back")
        yield Footer()

    def on_mount(self) -> None:
        config = self._load_riposte_config()
        if config is None:
            return
        profiles = sorted(decoy_profiles(config) | ({self._policy.decoy_profile} if self._policy.decoy_profile else set()))
        select = self.query_one("#policy-decoy-profile", Select)
        select.set_options([(name, name) for name in profiles])
        if self._policy.decoy_profile:
            select.value = self._policy.decoy_profile
        show(self.query_one("#decoy-hint", Static),
            _("Profils de leurre d'Active Defense.") if deception_available(config)
            else _("Leurres inactifs : activer Active Defense et ses leurres."))
        show(self.query_one("#action-hint", Static),
            _("Ban local = blocklist du WAF ; ban réseau = jails omega-jail (en plus du ban local).")
            if waf_enabled(config) else _("WAF inactif : activer le WAF pour les actions de ban."))
        riposte = riposte_config_of(config)
        show(self.query_one("#policy-exclusions", Static),
            ", ".join(riposte_exempt_networks(config, riposte)) or _("aucune"))

    # --- Lecture du formulaire ------------------------------------------------------------------

    def _text(self, widget_id: str) -> str:
        return self.query_one(f"#{widget_id}", Input).value.strip()

    def _read(self) -> RipostePolicy | str:
        """La politique saisie, ou le message d'erreur (traduit) du premier champ invalide."""
        returns, decoy_hits, max_per_source = (self._text(w) for w in ("policy-returns", "policy-decoy-hits",
                                                                         "policy-max-per-source"))
        if not (returns.isdigit() and decoy_hits.isdigit() and max_per_source.isdigit()):
            return _("Nombre invalide (entier positif attendu).")
        within = parse_duration(self._text("policy-within"))
        decoy_duration = parse_duration(self._text("policy-decoy-duration"))
        tiers_text = self._text("policy-tiers")
        tiers = parse_durations(tiers_text) if tiers_text else None
        if within is None or decoy_duration is None or (tiers_text and not tiers):
            return _("Durée invalide : un nombre suivi de s, m, h ou d (ex. 6h, 30d).")
        action = str(self.query_one("#policy-action", Select).value)
        profile_value = self.query_one("#policy-decoy-profile", Select).value
        profile = str(profile_value) if action == "decoy" and profile_value not in (Select.NULL, None, "") else None
        level = str(self.query_one("#policy-level", Select).value) or None
        return replace(
            self._policy,
            id=self._text("policy-id"), name=self._text("policy-name"),
            attack_classes=tuple(c.strip() for c in self._text("policy-classes").split(",") if c.strip()),
            returns=int(returns), within_seconds=within, decoy_hits=int(decoy_hits),
            min_ad_level=level,  # type: ignore[arg-type]
            action=action,  # type: ignore[arg-type]
            tiers_seconds=tiers, decoy_profile=profile, decoy_duration_seconds=decoy_duration,
            max_active_per_source=int(max_per_source),
        )

    # --- Mesurer ----------------------------------------------------------------------------------

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "back":
            self.dismiss()
        elif event.button.id == "measure":
            self._measure()
        elif event.button.id == "save":
            self._save()

    def _measure(self) -> None:
        policy = self._read()
        result_widget = self.query_one("#measure-result", Static)
        if isinstance(policy, str):
            show(result_widget, policy)
            return
        config = self._load_riposte_config()
        reader = self._container.riposte_journal_reader
        if config is None or reader is None:
            show(result_widget, _("Mesure indisponible dans cet environnement."))
            return
        self.query_one("#measure", Button).disabled = True
        show(result_widget, _("Mesure en cours..."))
        now = self._container.clock.now()
        paths = journal_paths(config, self._container.project_root)

        def work() -> None:
            try:
                result: MeasureResult | str = measure_policy(config, policy, reader(*paths), now, days=MEASURE_DAYS)
            except OSError as error:
                result = _("Journaux illisibles : {error}").format(error=error)
            self.app.call_from_thread(self._measure_done, policy, result)

        self.run_worker(work, thread=True, exclusive=True, group="riposte-measure")

    def _measure_done(self, policy: RipostePolicy, result: MeasureResult | str) -> None:
        self.query_one("#measure", Button).disabled = False
        lines = [result] if isinstance(result, str) else format_measure(result)
        if not isinstance(result, str):
            self._measured = (policy, lines)
        show(self.query_one("#measure-result", Static), "\n".join(lines))
        self.query_one("#measure-result", Static).scroll_visible()

    # --- Enregistrer ------------------------------------------------------------------------------

    def _save(self) -> None:
        error = self.query_one("#form-error", Static)
        policy = self._read()
        if isinstance(policy, str):
            show(error, policy)
            return
        config = self._load_riposte_config()
        if config is None:
            return
        needed = required_risks(policy)
        policy = replace(policy, confirmed_risks=tuple(r for r in policy.confirmed_risks if r in needed))
        checked = policy_problems(config, replace(policy, confirmed_risks=needed), replaces=self._replaces)
        if not checked.ok:
            show(error, _("Non enregistré : ") + "; ".join(checked.errors or (_("politique introuvable"),)))
            return
        show(error, "")
        unconfirmed = [r for r in needed if r not in policy.confirmed_risks]
        if unconfirmed:
            self.app.push_screen(ConfirmScreen(
                title=_("MOINS PRUDENT QUE LA NORME"),
                message=_("Cette politique demande {risks}. Confirmer ce choix ?").format(
                    risks=" ; ".join(risk_text(r) for r in unconfirmed)),
            ), lambda confirmed: self._ask_activation(config, replace(policy, confirmed_risks=needed))
                if confirmed else None)
            return
        self._ask_activation(config, policy)

    def _ask_activation(self, config: OmegaServConfig, policy: RipostePolicy) -> None:
        measured = self._measured[1] if self._measured is not None and self._measured[0] == replace(
            policy, confirmed_risks=self._measured[0].confirmed_risks) else None
        effect = "\n".join(measured) if measured else _("Politique non mesurée.")
        if policy.action == "local_and_network_ban":
            tiers = policy.tiers_seconds or riposte_config_of(config).tiers_seconds
            effect += "\n" + _("Ban réseau : {jails}").format(jails=network_jails_text(self._service_name(), tiers))
        message = "\n\n".join((
            effect,
            _("Une politique activée agit automatiquement, sans validation action par action (levée possible dans "
              "Actions, arrêt d'urgence dans État). Conseil : Mesurer et Simuler avant d'activer."),
        ))
        self.app.push_screen(ChoiceScreen(
            title=_("ENREGISTRER LA POLITIQUE {id}").format(id=policy.id),
            message=message,
            choices=[
                Choice("activate", _("Activer"), "error"),
                Choice("save", _("Enregistrer sans activer"), "primary"),
                Choice("cancel", _("Annuler")),
            ],
        ), lambda result: self._store_policy(config, policy, result))

    def _store_policy(self, config: OmegaServConfig, policy: RipostePolicy, result: ChoiceResult | None) -> None:
        if result is None:
            return
        policy = replace(policy, enabled=result.choice == "activate")
        saved = save_policy(self._container.configuration, self._container.config_file, config, policy,
                            replaces=self._replaces)
        if not saved.ok:
            show(self.query_one("#form-error", Static),
                _("Non enregistré : ") + "; ".join(saved.errors or (_("politique introuvable"),)))
            return
        self.app.notify((_("Politique {id} enregistrée et activée.") if policy.enabled
                         else _("Politique {id} enregistrée, non activée.")).format(id=policy.id))
        self._reload_riposte(config, done=self._close)

    def _close(self) -> None:
        self.dismiss()
