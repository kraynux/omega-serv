"""Ecran de rendu generique d'une fiche du guide d'aide (plan guide
d'aide §3.4) - UN SEUL ecran pour les 64 fiches possibles, alimente par
un `ScreenGuide` (interfaces/tui/guide/model.py) plutot que 64 ecrans
Python dedies : evite la duplication et le risque de divergence avec le
comportement reel decrit dans chaque fiche (§3.1 du plan)."""
from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, VerticalScroll
from textual.widgets import Button, Footer, Header, Static

from omega_serv.core.i18n import _
from omega_serv.interfaces.tui.guide.model import ScreenGuide
from omega_serv.interfaces.tui.screens._base import OmegaScreen


class GuideDetailScreen(OmegaScreen):
    def __init__(self, guide: ScreenGuide) -> None:
        super().__init__()
        self._guide = guide

    def compose(self) -> ComposeResult:
        guide = self._guide
        yield Header()
        with VerticalScroll(classes="omega-panel"):
            yield Static(guide.title.upper(), classes="omega-title")
            yield Static(_("Parcours : {acces}").format(acces=guide.acces), classes="omega-hint")
            yield Static("")
            yield Static(_("DÉFINITION"), classes="omega-subtitle")
            yield Static(guide.definition)
            if guide.fields:
                yield Static("")
                yield Static(_("CHAMPS"), classes="omega-subtitle")
                for guide_field in guide.fields:
                    yield Static("")
                    yield Static(guide_field.label, classes="omega-subtitle")
                    yield Static(_("Définition : {definition}").format(definition=guide_field.definition))
                    yield Static(_("Utilisation : {utilisation}").format(utilisation=guide_field.utilisation))
                    yield Static(_("Action : {action}").format(action=guide_field.action))
                    yield Static(_("Réaction : {reaction}").format(reaction=guide_field.reaction))
            if guide.consequences:
                yield Static("")
                yield Static(_("CONSÉQUENCES"), classes="omega-subtitle")
                yield Static(guide.consequences)
            if guide.points_de_vigilance:
                yield Static("")
                yield Static(_("POINTS DE VIGILANCE"), classes="omega-subtitle")
                for point in guide.points_de_vigilance:
                    yield Static(_("- {point}").format(point=point))
            yield Static("")
            with Horizontal(classes="omega-actions"), Container(classes="omega-btn-frame"):
                yield Button(_("Retour"), id="back")
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "back":
            self.dismiss()
