"""Ecran Aide : reference statique des raccourcis et fonctions de
l'application. Adapte du patron screens/help_screen.py d'omega-check
(plan interface §0/§3.1) - pas de tableau de profils de ports (concept
propre a CHECK), remplace par la liste des options superposables
connues (domain/config/option.py::KNOWN_OPTION_NAMES).

Role reduit depuis le guide d'aide (2026-09-14, OMEGA-SERV_PLAN-DETAILLE_
GUIDE_AIDE.md §3.5) : n'est plus le point d'entree principal de l'aide
(remplace par `GuideMenuScreen`/`GuideDetailScreen`) - reste le REPLI
utilise par `_base.py::action_show_help` quand la fiche detaillee de
l'ecran courant n'existe pas encore (deploiement progressif)."""
from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, VerticalScroll
from textual.widgets import Button, Footer, Header, Static

from omega_serv.domain.config.option import KNOWN_OPTION_NAMES
from omega_serv.interfaces.tui.screens._base import OmegaScreen

_SHORTCUTS = (
    ("Haut / Bas", "Naviguer entre les elements d'un ecran"),
    ("Tab / Maj+Tab", "Naviguer entre les champs d'un formulaire"),
    ("Echap", "Retour a l'ecran precedent (confirmation de sortie sur l'accueil)"),
    ("t", "Theme suivant (applique immediatement, sans confirmation)"),
    ("r", "Rafraichir la detection du terminal"),
    ("F1", "Aide de l'ecran courant (fiche detaillee si elle existe deja)"),
    ("a", "Guide d'aide complet (parcours de tous les ecrans + FAQ)"),
    ("q", "Quitter (avec confirmation)"),
)

_SCOPE_NOTICE = (
    "Omega-serv sert du contenu statique et, en option, du PHP via "
    "FastCGI/PHP-FPM, avec un durcissement HTTP non desactivable. WAF, "
    "TLS et authentification restent des modules superposables, jamais "
    "actives par defaut. Cette interface habille exactement les memes "
    "cas d'usage que la CLI non-interactive (`omega-serv --help`) - "
    "aucune action ici n'existe qui ne soit pas d'abord une commande CLI."
)


class HelpScreen(OmegaScreen):
    """Reference statique, accessible depuis n'importe quel ecran (touche `a`)."""

    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll(classes="omega-panel"):
            yield Static("AIDE", classes="omega-title")
            yield Static("Raccourcis clavier", classes="omega-subtitle")
            for key, description in _SHORTCUTS:
                yield Static(f"{key:<14} {description}")
            yield Static("")
            yield Static("Options superposables connues", classes="omega-subtitle")
            yield Static(", ".join(sorted(KNOWN_OPTION_NAMES)))
            yield Static("")
            yield Static(_SCOPE_NOTICE, classes="omega-subtitle")
            with Horizontal(classes="omega-actions"), Container(classes="omega-btn-frame"):
                yield Button("Retour", id="back")
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "back":
            self.dismiss()
