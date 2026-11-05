"""Modale a plusieurs choix (RIPOSTE, lot 5 - topo §6.5 a §6.7) : la ou ConfirmScreen n'offre que
Confirmer / Annuler, certaines decisions en ont trois (« Arreter et lever les actions en cours » /
« Arreter seulement » / « Annuler », « Activer » / « Enregistrer sans activer » / « Annuler »), avec
parfois une case a cocher (« ne pas compter ce ban dans la recidive »). Boutons empiles : leurs libelles
sont longs, et plus encore une fois traduits. `echap` = annuler (None)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Center, Container, Middle, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Checkbox, Static

from omega_serv.core.i18n import _


@dataclass(frozen=True)
class Choice:
    id: str
    label: str
    variant: str = "default"
    """`default`, `primary` ou `error` (action destructive)."""


@dataclass(frozen=True)
class ChoiceResult:
    choice: str
    checked: bool = False


class ChoiceScreen(ModalScreen[ChoiceResult | None]):
    BINDINGS: ClassVar[list[BindingType]] = [Binding("escape", "back", _("Annuler"), show=True)]

    def __init__(self, *, title: str, message: str, choices: list[Choice], checkbox: str | None = None) -> None:
        super().__init__()
        self._title = title
        self._message = message
        self._choices = choices
        self._checkbox = checkbox

    def compose(self) -> ComposeResult:
        with Middle(), Center(), Vertical(classes="omega-choice-box"):
            yield Static(self._title, classes="omega-confirm-title")
            with VerticalScroll(classes="omega-choice-message-scroll"):
                yield Static(Text(self._message), classes="omega-choice-message")
            if self._checkbox is not None:
                yield Checkbox(self._checkbox, id="choice-checkbox")
            with Vertical(classes="omega-confirm-buttons omega-choice-buttons"):
                for choice in self._choices:
                    with Container(classes="omega-btn-frame"):
                        yield Button(choice.label, id=f"choice-{choice.id}", variant=choice.variant)  # type: ignore[arg-type]

    def on_mount(self) -> None:
        """Jamais le focus sur un bouton destructif : `entree` par megarde = Annuler."""
        cancel = self.query("#choice-cancel")
        if cancel:
            cancel.first().focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        choice = (event.button.id or "").removeprefix("choice-")
        if choice == "cancel":
            self.dismiss(None)
            return
        checked = self._checkbox is not None and self.query_one("#choice-checkbox", Checkbox).value
        self.dismiss(ChoiceResult(choice=choice, checked=checked))

    def action_back(self) -> None:
        self.dismiss(None)
