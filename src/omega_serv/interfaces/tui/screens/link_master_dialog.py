"""Fenetre « Relier au maître » de l'ecran Instances (2026-11-16) : le maitre, choisi parmi les autres instances de
cette machine dont l'administration web est active, et les droits qu'il recoit (lecture ou administration).
`echap` ou Annuler = rien n'est fait (None)."""
from __future__ import annotations

from typing import ClassVar

from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Center, Container, Horizontal, Middle, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Select, Static

from omega_serv.core.i18n import _


def rights_choices() -> tuple[tuple[str, str], ...]:
    return ((_("Lecture : voir seulement"), "lecture"), (_("Administration : voir et agir"), "administration"))


class LinkMasterScreen(ModalScreen[tuple[str, str] | None]):
    """Renvoie (cle du maitre choisi, droits), ou None."""

    BINDINGS: ClassVar[list[BindingType]] = [Binding("escape", "back", _("Annuler"), show=True)]

    def __init__(self, *, follower: str, masters: list[tuple[str, str]], default_master: str) -> None:
        super().__init__()
        self._follower = follower
        self._masters = masters
        self._default = default_master

    def compose(self) -> ComposeResult:
        with Middle(), Center(), Vertical(classes="omega-confirm-box"):
            yield Static(_("RELIER AU MAÎTRE"), classes="omega-confirm-title")
            yield Static(_("{name} sera suivie depuis le tableau de bord web du maître choisi. Chaque instance "
                           "enregistre elle-même la liaison ; un maître déjà accepté par {name} est remplacé "
                           "seulement après confirmation.").format(name=self._follower))
            yield Static(_("Maître"), classes="omega-subtitle")
            yield Select(self._masters, allow_blank=False, value=self._default, id="link-master")
            yield Static(_("Droits donnés au maître"), classes="omega-subtitle")
            yield Select(rights_choices(), allow_blank=False, value="lecture", id="link-rights")
            with Horizontal(classes="omega-confirm-buttons"):
                with Container(classes="omega-btn-frame"):
                    yield Button(_("Relier"), id="link", variant="primary")
                with Container(classes="omega-btn-frame"):
                    yield Button(_("Annuler"), id="cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id != "link":
            self.dismiss(None)
            return
        self.dismiss((str(self.query_one("#link-master", Select).value),
                      str(self.query_one("#link-rights", Select).value)))

    def action_back(self) -> None:
        self.dismiss(None)
