"""Fenetre "Modifier une liste" de l'ecran WAF Custom (OMEGA-SERV_PLAN-
DETAILLE_SENSITIVE_PATHS.md lot 7) : gravite, recidive, ancrage, nom d'une
liste DEJA chargee - memes choix que l'assistant (_waf_list_choices.py).
Retourne les champs modifies, valides ensuite par
`update_keyword_list_entry` (aucune ecriture ici)."""
from __future__ import annotations

from typing import Any

from textual.app import ComposeResult
from textual.containers import Center, Container, Horizontal, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Select, Static

from omega_serv.core.i18n import _
from omega_serv.interfaces.tui.screens._waf_list_choices import (
    ANCHORS,
    BAN_DURATIONS,
    GRAVITY_LEVELS,
    RECIDIVE_COUNTS,
    RECIDIVE_WINDOWS,
    gravity_value,
)


def _choice(options: tuple[tuple[str, str], ...], value: object, default: str) -> str:
    text = str(value)
    return text if text in {v for _, v in options} else default


class KeywordListSettingsScreen(ModalScreen[dict[str, Any] | None]):
    def __init__(self, entry: dict[str, Any]) -> None:
        super().__init__()
        self._entry = entry
        self._path_mode = entry.get("match", "substring") == "path"

    def compose(self) -> ComposeResult:
        entry = self._entry
        with Center(), VerticalScroll(classes="omega-dynamic-form-box"):
            yield Static(_("MODIFIER LA LISTE - {value}").format(value=entry.get('id')), classes="omega-title")
            yield Static(_("Fichier : {value}").format(value=entry.get('file')), classes="omega-hint")
            yield Static(_("Nom affiché"), classes="omega-subtitle")
            yield Input(value=str(entry.get("label") or entry.get("id")), id="settings-label")
            if self._path_mode:
                yield Static(_("Où chercher"), classes="omega-subtitle")
                yield Select(ANCHORS, value=_choice(ANCHORS, entry.get("anchor"), "any_segment"),
                             allow_blank=False, id="settings-anchor")
            yield Static(_("Gravité"), classes="omega-subtitle")
            yield Select(GRAVITY_LEVELS,
                         value=gravity_value(int(entry.get("weight", 1)), bool(entry.get("observe_only"))),
                         allow_blank=False, id="settings-gravity")
            yield Static(_("Récidive : bannir après ... accès en ... pendant ..."), classes="omega-subtitle")
            yield Select(RECIDIVE_COUNTS, value=_choice(RECIDIVE_COUNTS, entry.get("escalation_threshold", 0), "0"),
                         allow_blank=False, id="settings-count")
            yield Select(RECIDIVE_WINDOWS,
                         value=_choice(RECIDIVE_WINDOWS, entry.get("escalation_window_seconds", 600), "600"),
                         allow_blank=False, id="settings-window")
            yield Select(BAN_DURATIONS,
                         value=_choice(BAN_DURATIONS, entry.get("auto_block_duration_seconds") or 3600, "3600"),
                         allow_blank=False, id="settings-duration")
            with Horizontal(classes="omega-confirm-buttons"):
                with Container(classes="omega-btn-frame"):
                    yield Button(_("Enregistrer"), id="settings-save", variant="primary")
                with Container(classes="omega-btn-frame"):
                    yield Button(_("Annuler"), id="settings-cancel")

    def on_mount(self) -> None:
        self._apply_recidive_state()

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id in ("settings-gravity", "settings-count"):
            self._apply_recidive_state()

    def _apply_recidive_state(self) -> None:
        observe = str(self.query_one("#settings-gravity", Select).value) == "observe"
        own_counter = str(self.query_one("#settings-count", Select).value) != "0"
        self.query_one("#settings-count", Select).disabled = observe
        for select_id in ("#settings-window", "#settings-duration"):
            self.query_one(select_id, Select).disabled = observe or not own_counter

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id != "settings-save":
            self.dismiss(None)
            return
        gravity = str(self.query_one("#settings-gravity", Select).value)
        observe = gravity == "observe"
        count = int(str(self.query_one("#settings-count", Select).value))
        changes: dict[str, Any] = {
            "label": self.query_one("#settings-label", Input).value.strip() or self._entry.get("id"),
            "observe_only": observe,
            "weight": int(self._entry.get("weight", 3)) if observe else int(gravity),
            "escalation_threshold": 0 if observe else count,
            "escalation_window_seconds": int(str(self.query_one("#settings-window", Select).value)),
            "auto_block_duration_seconds": (
                int(str(self.query_one("#settings-duration", Select).value)) if count and not observe else None
            ),
        }
        if self._path_mode:
            changes["anchor"] = str(self.query_one("#settings-anchor", Select).value)
        self.dismiss(changes)
