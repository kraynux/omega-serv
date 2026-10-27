"""Modale de selection d'un pack de regles WAF (retour utilisateur
2026-09-13 : "au lieu d'un champ et rentrer l'adresse a la main,
proposer un menu deroulant... avec un descriptif en dessous"). Liste
REELLE des packs presents sous secure/waf/rules/ (jamais figee dans le
code), exclut ceux deja references dans rule_paths - jamais propose de
doublon. Retourne le chemin relatif choisi (str) ou None sur annulation,
meme convention que DynamicFormScreen mais un Select plutot qu'un champ
libre, puisqu'un chemin de fichier existant se choisit, il ne se tape
pas."""
from __future__ import annotations

import json
from typing import TYPE_CHECKING, ClassVar

from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Center, Container, Horizontal, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Select, Static

from omega_serv.core.i18n import _

if TYPE_CHECKING:
    from pathlib import Path

    from omega_serv.ports.filesystem_port import FilesystemPort

_RULES_SUBDIR = ("secure", "waf", "rules")
_MAX_RULES_LISTED = 8


class WafRulePackPickerScreen(ModalScreen[str | None]):
    BINDINGS: ClassVar[list[BindingType]] = [Binding("escape", "cancel", _("Annuler"), show=True)]

    def __init__(
        self, *, filesystem: FilesystemPort, project_root: Path, existing_paths: list[str],
    ) -> None:
        super().__init__()
        self._filesystem = filesystem
        self._project_root = project_root
        self._options = self._discover_packs(existing_paths)

    def _discover_packs(self, existing_paths: list[str]) -> list[tuple[str, str]]:
        rules_dir = self._project_root.joinpath(*_RULES_SUBDIR)
        if not self._filesystem.is_dir(rules_dir):
            return []
        existing = set(existing_paths)
        relative_paths = sorted(
            str(path.relative_to(self._project_root)) for path in self._filesystem.list_json_files(rules_dir)
        )
        return [(path, path) for path in relative_paths if path not in existing]

    def compose(self) -> ComposeResult:
        with Center(), VerticalScroll(classes="omega-dynamic-form-box"):
            yield Static(_("AJOUTER UN PACK DE RÈGLES"), classes="omega-title")
            if self._options:
                yield Select(self._options, value=self._options[0][1], allow_blank=False, id="pack-select")
            else:
                yield Static(
                    _("Aucun pack disponible (déjà tous ajoutés, ou secure/waf/rules/ vide/absent)."),
                    id="no-packs-hint",
                    classes="omega-hint",
                )
            yield Static("", id="pack-description", classes="omega-hint")
            with Horizontal(classes="omega-confirm-buttons"):
                with Container(classes="omega-btn-frame"):
                    yield Button(_("Ajouter"), id="confirm", variant="primary", disabled=not self._options)
                with Container(classes="omega-btn-frame"):
                    yield Button(_("Annuler"), id="cancel")

    def on_mount(self) -> None:
        if self._options:
            self._refresh_description(self._options[0][1])

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id == "pack-select":
            self._refresh_description(str(event.value))

    def _refresh_description(self, relative_path: str) -> None:
        self.query_one("#pack-description", Static).update(self._describe_pack(relative_path))

    def _describe_pack(self, relative_path: str) -> str:
        try:
            raw = self._filesystem.read_text(self._project_root / relative_path)
            data = json.loads(raw)
        except (OSError, ValueError) as exc:
            return _("Impossible de lire ce pack : {exc}").format(exc=exc)
        pack_name = data.get("pack", relative_path)
        enabled = _("actif") if data.get("enabled", True) else _("inactif")
        rules = data.get("rules", [])
        lines = [_("Pack {pack_name!r} ({enabled} par défaut, {count} règle(s)) :").format(pack_name=pack_name, enabled=enabled, count=len(rules))]
        for rule in rules[:_MAX_RULES_LISTED]:
            # Pack livre : description traduite si le catalogue la connait (tools/i18n_catalog.py
            # extract) ; regle ecrite par l'utilisateur : son texte tel quel.
            description = rule.get("description", "")
            lines.append(f"  - {rule.get('id', '?')} : {_(description) if description else ''}")
        if len(rules) > _MAX_RULES_LISTED:
            lines.append(_("  ... et {value} de plus").format(value=len(rules) - _MAX_RULES_LISTED))
        return "\n".join(lines)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel":
            self.dismiss(None)
            return
        if event.button.id == "confirm" and self._options:
            self.dismiss(str(self.query_one("#pack-select", Select).value))

    def action_cancel(self) -> None:
        self.dismiss(None)
