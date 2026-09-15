# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""FAQ du guide d'aide (plan guide d'aide §3.7) - liste groupee par
categorie, alimentee par interfaces/tui/guide/content/faq.py."""
from __future__ import annotations

from itertools import groupby

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, VerticalScroll
from textual.widgets import Button, Footer, Header, Static

from omega_serv.interfaces.tui.guide.registry import ALL_FAQ_ENTRIES
from omega_serv.interfaces.tui.screens._base import OmegaScreen


class FaqScreen(OmegaScreen):
    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll(classes="omega-panel"):
            yield Static("FAQ", classes="omega-title")
            if not ALL_FAQ_ENTRIES:
                yield Static("Aucune question repertoriee pour l'instant.", classes="omega-hint")
            # itertools.groupby ne regroupe que des cles consecutives -
            # trier par categorie d'abord, jamais supposer que
            # ALL_FAQ_ENTRIES est deja range dans cet ordre (agrege
            # depuis plusieurs fichiers content/*.py au fil des phases).
            sorted_entries = sorted(ALL_FAQ_ENTRIES, key=lambda e: e.category)
            for category, entries in groupby(sorted_entries, key=lambda e: e.category):
                yield Static("")
                yield Static(category.upper(), classes="omega-subtitle")
                for entry in entries:
                    yield Static("")
                    yield Static(f"Q. {entry.question}")
                    yield Static(f"R. {entry.answer}")
            yield Static("")
            with Horizontal(classes="omega-actions"), Container(classes="omega-btn-frame"):
                yield Button("Retour", id="back")
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "back":
            self.dismiss()
