# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Assistant de creation de regle WAF Custom (retour utilisateur
2026-09-14 : "il faut rajouter une indication pour l'utilisateur car
c'est flou... le but c'est qu'un utilisateur qui ne sait pas coder
puisse utiliser [cet ecran]"). Remplace le formulaire brut (regex +
scope a ecrire a la main, DynamicFormScreen generique) par un
questionnaire en langage clair pour les 4 scenarios les plus courants -
la regex reelle est CONSTRUITE par le code (`build_path_segment_pattern`/
`build_keyword_pattern`, domain/security/waf/rule_validation.py,
`re.escape` systematique : un caractere special tape sans le savoir
n'est jamais interprete comme une regex) a partir d'une valeur saisie EN
CLAIR. Un mode "Avance" reste disponible pour qui veut ecrire sa propre
regex/scope directement - jamais retire, seulement plus un choix
explicite qu'un point de depart impose a tout le monde."""
from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Center, Container, Horizontal, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Select, Static

from omega_serv.domain.security.waf.rule_validation import (
    build_keyword_pattern,
    build_path_segment_pattern,
)

_DETECTION_TYPES: tuple[tuple[str, str], ...] = (
    ("Un chemin precis visite (ex: /admin)", "path_exact"),
    ("Un mot-cle dans l'adresse ou les parametres", "keyword_url"),
    ("Un mot-cle envoye dans un formulaire (POST)", "keyword_body"),
    ("Un outil de scan connu (User-Agent)", "user_agent"),
    ("Avance : j'ecris moi-meme une expression reguliere", "advanced"),
)

_TYPE_HINTS: dict[str, str] = {
    "path_exact": (
        "Tapez le chemin SANS le '/' de tete. Exemple : 'admin' detecte /admin et /admin/xxx, "
        "mais jamais /administrator."
    ),
    "keyword_url": (
        "Tapez le mot recherche tel quel. Exemple : 'union select' - detecte ce mot n'importe ou "
        "dans l'adresse ou les parametres de la requete."
    ),
    "keyword_body": (
        "Tapez le mot recherche tel quel. Detecte ce mot dans les donnees envoyees par un "
        "formulaire (methode POST)."
    ),
    "user_agent": (
        "Tapez le nom de l'outil recherche tel quel. Exemple : 'sqlmap' - detecte les requetes "
        "envoyees par cet outil."
    ),
    "advanced": (
        "Ecrivez vous-meme le motif (expression reguliere Python) et la portee "
        "(path, query, body, headers, user_agent - separes par des virgules)."
    ),
}

_SEVERITY_LEVELS: tuple[tuple[str, str], ...] = (
    ("Faible", "1"),
    ("Moyen", "3"),
    ("Eleve", "6"),
    ("Critique", "9"),
)


class WafCustomRuleWizardScreen(ModalScreen[dict[str, str] | None]):
    """Retourne un dict `{description, scope, pattern, weight}` (jamais
    `id` - genere par l'appelant, qui connait deja les regles
    existantes) pret a etre valide/ecrit tel quel par WafCustomRuleScreen,
    ou None si annule."""

    def compose(self) -> ComposeResult:
        with Center(), VerticalScroll(classes="omega-dynamic-form-box"):
            yield Static("AJOUTER UNE REGLE - ASSISTANT", classes="omega-title")
            yield Static(
                "Une regle repere un texte dans une partie de la requete (le chemin visite, "
                "un parametre, le logiciel utilise...). Choisissez ci-dessous ce que vous voulez "
                "detecter - aucune connaissance des expressions regulieres n'est necessaire, sauf "
                "en mode Avance.",
                classes="omega-hint",
            )
            yield Static("Que voulez-vous detecter ?", classes="omega-subtitle")
            yield Select(_DETECTION_TYPES, value="path_exact", allow_blank=False, id="detection-type-select")
            yield Static(_TYPE_HINTS["path_exact"], id="type-hint", classes="omega-hint")

            yield Static("Valeur a detecter (mode simple)", id="value-label", classes="omega-subtitle")
            yield Input(placeholder="ex: admin", id="value-input")

            with Container(id="advanced-fields"):
                yield Static("Portee (path, query, body, headers, user_agent - separes par des virgules)", classes="omega-subtitle")
                yield Input(value="path", id="scope-input")
                yield Static("Motif (expression reguliere Python)", classes="omega-subtitle")
                yield Input(id="pattern-input")

            yield Static("Description (facultatif)", classes="omega-subtitle")
            yield Input(id="description-input")
            yield Static("Gravite", classes="omega-subtitle")
            yield Select(_SEVERITY_LEVELS, value="3", allow_blank=False, id="severity-select")

            with Horizontal(classes="omega-confirm-buttons"):
                with Container(classes="omega-btn-frame"):
                    yield Button("Ajouter", id="confirm", variant="primary")
                with Container(classes="omega-btn-frame"):
                    yield Button("Annuler", id="cancel")

    def on_mount(self) -> None:
        self._apply_mode("path_exact")

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id == "detection-type-select":
            self._apply_mode(str(event.value))

    def _apply_mode(self, detection_type: str) -> None:
        self.query_one("#type-hint", Static).update(_TYPE_HINTS[detection_type])
        advanced = detection_type == "advanced"
        self.query_one("#advanced-fields", Container).display = advanced
        self.query_one("#value-label", Static).display = not advanced
        self.query_one("#value-input", Input).display = not advanced

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel":
            self.dismiss(None)
            return
        if event.button.id == "confirm":
            self.dismiss(self._build_result())

    def _build_result(self) -> dict[str, str]:
        detection_type = str(self.query_one("#detection-type-select", Select).value)
        description = self.query_one("#description-input", Input).value.strip()
        weight = str(self.query_one("#severity-select", Select).value)

        if detection_type == "advanced":
            scope = self.query_one("#scope-input", Input).value
            pattern = self.query_one("#pattern-input", Input).value
        else:
            value = self.query_one("#value-input", Input).value
            if detection_type == "path_exact":
                scope, pattern = "path", build_path_segment_pattern(value)
            elif detection_type == "keyword_url":
                scope, pattern = "path,query", build_keyword_pattern(value)
            elif detection_type == "keyword_body":
                scope, pattern = "body", build_keyword_pattern(value)
            else:  # user_agent
                scope, pattern = "user_agent", build_keyword_pattern(value)

        return {
            "description": description, "scope": scope, "pattern": pattern,
            "weight": weight, "case_insensitive": "oui", "enabled": "oui",
        }
