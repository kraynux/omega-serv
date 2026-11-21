"""Modale de formulaire generique (plan interface §7, menu 3) : un champ
texte par entree de `fields`, retourne un dict id->valeur saisie au clic
sur "Valider", None sur "Annuler"/echap. Reutilisee par les ecrans CRUD
de regles (alias/redirections/rewrites/FastCGI/cache/proxies de
confiance) - meme forme partout, evite de dupliquer un formulaire quasi
identique 6 fois. `validate` (optionnel) : appele au clic sur "Valider" ;
s'il renvoie un message, celui-ci s'affiche dans la modale, qui reste
ouverte avec la saisie intacte (sinon l'utilisateur devait tout
ressaisir apres chaque erreur).

Lot V (decision de l'auteur du 2026-11-15, projets 3.0.0 §7.1 et §7.9) : `submit` (pose par
`OmegaScreen.push_form`) applique la saisie AVANT de fermer ; toute erreur signalee pendant
l'application garde la modale ouverte, saisie intacte, avec l'explication. Les champs oui/non
(valeur initiale « oui » ou « non ») n'acceptent plus qu'un oui ou un non : avant, « ouii »
valait silencieusement non.

`choices` (essai de l'auteur du 2026-11-17, role des comptes de l'administration web) : un champ a valeurs fixes
devient un menu deroulant (libelle affiche, valeur rendue) au lieu d'un texte a taper."""
from __future__ import annotations

from collections.abc import Callable
from typing import ClassVar

from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Center, Container, Horizontal, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Select, Static

from omega_serv.core.i18n import _
from omega_serv.interfaces.tui.yes_no import is_no, is_yes, no, to_text, yes


class DynamicFormScreen(ModalScreen[dict[str, str] | None]):
    """`fields` : sequence de (id, label, valeur_par_defaut). `password_fields` :
    identifiants a masquer (mot de passe - auth_menu_screen.py, jamais
    affiche en clair a l'ecran)."""

    BINDINGS: ClassVar[list[BindingType]] = [Binding("escape", "back", _("Annuler"), show=True)]

    def __init__(
        self,
        *,
        title: str,
        fields: list[tuple[str, str, str]],
        password_fields: frozenset[str] = frozenset(),
        validate: Callable[[dict[str, str]], str | None] | None = None,
        submit: Callable[[dict[str, str]], str | None] | None = None,
        choices: dict[str, list[tuple[str, str]]] | None = None,
    ) -> None:
        super().__init__()
        self._title = title
        self._fields = fields
        self._password_fields = password_fields
        self._validate = validate
        self.submit = submit
        self._choices = choices or {}
        """Champ -> [(libelle, valeur)] : menu deroulant ; la valeur par defaut doit etre l'une des valeurs."""
        """Applique la saisie ; renvoie un message d'erreur (la modale reste ouverte) ou None (elle se ferme)."""
        self._yes_no_fields = frozenset(
            field_id for field_id, _label, default in fields if default in (to_text(True), to_text(False)))

    def compose(self) -> ComposeResult:
        with Center(), VerticalScroll(classes="omega-dynamic-form-box"):
            yield Static(self._title, classes="omega-title")
            for field_id, label, default in self._fields:
                yield Static(label, classes="omega-subtitle")
                if field_id in self._choices:
                    options = self._choices[field_id]
                    known = [value for _text, value in options]
                    yield Select(options, value=default if default in known else known[0], allow_blank=False,
                                 id=f"df-{field_id}")
                else:
                    yield Input(value=default, id=f"df-{field_id}", password=field_id in self._password_fields)
            yield Static("", id="df-error", classes="omega-hint")
            with Horizontal(classes="omega-confirm-buttons"):
                with Container(classes="omega-btn-frame"):
                    yield Button(_("Valider"), id="confirm", variant="primary")
                with Container(classes="omega-btn-frame"):
                    yield Button(_("Annuler"), id="cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel":
            self.dismiss(None)
            return
        values = {field_id: self._value(field_id) for field_id, _label, _default in self._fields}
        error = self._yes_no_error(values)
        if error is None and self._validate is not None:
            error = self._validate(values)
        if not error and self.submit is not None:
            error = self.submit(values)
        if error:
            self.query_one("#df-error", Static).update(error)
            return
        self.dismiss(values)

    def _value(self, field_id: str) -> str:
        if field_id in self._choices:
            return str(self.query_one(f"#df-{field_id}", Select).value)
        return self.query_one(f"#df-{field_id}", Input).value.strip()

    def _yes_no_error(self, values: dict[str, str]) -> str | None:
        for field_id, label, _default in self._fields:
            if field_id in self._yes_no_fields and not (is_yes(values[field_id]) or is_no(values[field_id])):
                self.query_one(f"#df-{field_id}", Input).focus()
                return _("« {label} » : répondez {yes} ou {no} (saisi : {value!r}).").format(
                    label=label, yes=yes(), no=no(), value=values[field_id])
        return None

    def action_back(self) -> None:
        self.dismiss(None)
