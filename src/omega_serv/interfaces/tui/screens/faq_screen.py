"""FAQ du guide d'aide (plan guide d'aide §3.7) - alimentee par interfaces/tui/guide/content/faq.py.

Retour de l'auteur du 2026-11-18 (« elle pique un peu les yeux ») : un theme repliable par categorie, ferme a
l'ouverture avec son nombre de questions ; question en gras dans la couleur d'accent, reponse en texte normal
decalee ; [Retour] fixe en bas, hors defilement."""
from __future__ import annotations

import unicodedata
from itertools import groupby

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, VerticalScroll
from textual.widgets import Button, Collapsible, Footer, Header, Static

from omega_serv.core.i18n import _
from omega_serv.interfaces.tui.guide.registry import ALL_FAQ_ENTRIES
from omega_serv.interfaces.tui.screens._base import OmegaScreen


class FaqScreen(OmegaScreen):
    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll(classes="omega-panel"):
            yield Static(_("FAQ"), classes="omega-title")
            if not ALL_FAQ_ENTRIES:
                yield Static(_("Aucune question répertoriée pour l'instant."), classes="omega-hint")
            else:
                yield Static(_("Choisissez un thème pour afficher ses questions."), classes="omega-hint")
            sorted_entries = sorted(ALL_FAQ_ENTRIES, key=lambda e: (_sort_key(e.category), e.category))
            for category, group in groupby(sorted_entries, key=lambda e: e.category):
                entries = list(group)
                title = _("{category} ({count})").format(category=category, count=len(entries))
                with Collapsible(title=title, collapsed=True, classes="omega-faq-group"):
                    for entry in entries:
                        yield Static(_("Q. {question}").format(question=entry.question),
                                     classes="omega-faq-question")
                        yield Static(entry.answer, classes="omega-faq-answer")
        with Horizontal(classes="omega-actions omega-service-back"), Container(classes="omega-btn-frame"):
            yield Button(_("Retour"), id="back")
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "back":
            self.dismiss()


def _sort_key(text: str) -> str:
    """Ordre alphabetique sans casse ni accents (« Rapport » avant « RIPOSTE », « Sécurité » parmi les S)."""
    return "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c)).casefold()
