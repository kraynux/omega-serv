"""Assistant d'ajout d'une zone CSP (retour utilisateur 2026-10-10 :
"il faut detailler et proposer pour que l'utilisateur ne sacrifie pas
entierement une politique pour juste un rajout... afficher la politique
en place et les options disponibles en rajout"). Une zone CSP remplace
ENTIEREMENT la politique par defaut pour son prefixe (domain/security/
csp.py::csp_policy_for_path, jamais une fusion) - un simple champ texte
vide inviterait a perdre des directives sans le vouloir. Cet assistant
pre-remplit CHAQUE directive connue avec sa valeur ACTUELLE (la
politique globale), avec un indice de ce qu'elle controle, pour que
l'utilisateur ne modifie que ce dont il a besoin - meme esprit que
`waf_custom_rule_wizard_screen.py` (langage clair plutot qu'un champ
brut a completer de zero).

Une directive videe par l'utilisateur est OMISE de la zone finale
(`domain/security/csp.py::build_csp_policy`) - comportement assume,
jamais un "oubli" invisible : la liste des directives presentees reste
toujours visible et complete, rien n'est jamais cache."""
from __future__ import annotations

from typing import ClassVar

from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Center, Container, Horizontal, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Static

from omega_serv.domain.security.csp import (
    KNOWN_CSP_DIRECTIVES,
    build_csp_policy,
    find_csp_risks,
    parse_csp_directives,
)
from omega_serv.interfaces.tui.screens.confirm import ConfirmScreen


class CspZoneWizardScreen(ModalScreen[tuple[str, str] | None]):
    BINDINGS: ClassVar[list[BindingType]] = [Binding("escape", "cancel", "Annuler", show=True)]

    def __init__(self, *, current_policy: str) -> None:
        super().__init__()
        self._current_directives = parse_csp_directives(current_policy)

    def compose(self) -> ComposeResult:
        with Center(), VerticalScroll(classes="omega-dynamic-form-box"):
            yield Static("AJOUTER UNE ZONE CSP", classes="omega-title")
            yield Static(
                "Cette zone REMPLACE ENTIEREMENT la politique ci-dessous pour son prefixe - "
                "jamais un simple ajout a la politique globale. Chaque champ est pre-rempli avec "
                "la valeur ACTUELLE : ne modifiez que ce dont vous avez besoin, videz un champ "
                "pour omettre cette directive dans la zone.",
                classes="omega-hint",
            )
            yield Static("", id="wizard-error", classes="omega-hint")
            yield Static("Prefixe (ex: /public-widgets/)", classes="omega-subtitle")
            yield Input(id="wiz-path-prefix")
            for name, hint in KNOWN_CSP_DIRECTIVES:
                yield Static(f"{name} - {hint}", classes="omega-subtitle")
                yield Input(value=self._current_directives.get(name, ""), id=f"wiz-{name}")
            with Horizontal(classes="omega-confirm-buttons"):
                with Container(classes="omega-btn-frame"):
                    yield Button("Valider", id="confirm", variant="primary")
                with Container(classes="omega-btn-frame"):
                    yield Button("Annuler", id="cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel":
            self.dismiss(None)
            return
        if event.button.id == "confirm":
            self._validate_and_confirm()

    def action_cancel(self) -> None:
        self.dismiss(None)

    def _validate_and_confirm(self) -> None:
        error_widget = self.query_one("#wizard-error", Static)
        path_prefix = self.query_one("#wiz-path-prefix", Input).value.strip()
        if not path_prefix.startswith("/"):
            error_widget.update(f"Prefixe invalide (doit commencer par '/') : {path_prefix!r}")
            return

        directives = {
            name: self.query_one(f"#wiz-{name}", Input).value.strip()
            for name, _hint in KNOWN_CSP_DIRECTIVES
        }
        policy = build_csp_policy(directives)
        if not policy:
            error_widget.update("Au moins une directive doit avoir une valeur - une zone vide n'a aucun effet.")
            return
        error_widget.update("")

        risky_directives = find_csp_risks(policy)
        if risky_directives:
            self.app.push_screen(
                ConfirmScreen(
                    title="ZONE CSP MOINS STRICTE QUE LA NORME",
                    message=(
                        f"Cette zone relache {', '.join(risky_directives)} (unsafe-inline/unsafe-eval/"
                        "source generique '*') par rapport a une politique stricte. Elle restera "
                        "visible dans 'omega-serv audit security' (CSP-001/CSP-002). Confirmer "
                        "cette zone malgre tout ?"
                    ),
                ),
                lambda confirmed: self._finish(confirmed, path_prefix, policy),
            )
            return
        self.dismiss((path_prefix, policy))

    def _finish(self, confirmed: bool | None, path_prefix: str, policy: str) -> None:
        if confirmed:
            self.dismiss((path_prefix, policy))
