"""Modale de formulaire generique (plan interface §7, menu 3) : un champ
texte par entree de `fields`, retourne un dict id->valeur saisie au clic
sur "Valider", None sur "Annuler"/echap. Reutilisee par les ecrans CRUD
de regles (alias/redirections/rewrites/FastCGI/cache/proxies de
confiance) - meme forme partout, evite de dupliquer un formulaire quasi
identique 6 fois."""
from __future__ import annotations

from typing import ClassVar

from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Center, Container, Horizontal, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Static


class DynamicFormScreen(ModalScreen[dict[str, str] | None]):
    """`fields` : sequence de (id, label, valeur_par_defaut). `password_fields` :
    identifiants a masquer (mot de passe - auth_menu_screen.py, jamais
    affiche en clair a l'ecran)."""

    BINDINGS: ClassVar[list[BindingType]] = [Binding("escape", "back", "Annuler", show=True)]

    def __init__(
        self,
        *,
        title: str,
        fields: list[tuple[str, str, str]],
        password_fields: frozenset[str] = frozenset(),
    ) -> None:
        super().__init__()
        self._title = title
        self._fields = fields
        self._password_fields = password_fields

    def compose(self) -> ComposeResult:
        with Center(), VerticalScroll(classes="omega-dynamic-form-box"):
            yield Static(self._title, classes="omega-title")
            for field_id, label, default in self._fields:
                yield Static(label, classes="omega-subtitle")
                yield Input(value=default, id=f"df-{field_id}", password=field_id in self._password_fields)
            with Horizontal(classes="omega-confirm-buttons"):
                with Container(classes="omega-btn-frame"):
                    yield Button("Valider", id="confirm", variant="primary")
                with Container(classes="omega-btn-frame"):
                    yield Button("Annuler", id="cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel":
            self.dismiss(None)
            return
        values = {field_id: self.query_one(f"#df-{field_id}", Input).value.strip() for field_id, _label, _default in self._fields}
        self.dismiss(values)

    def action_back(self) -> None:
        self.dismiss(None)
