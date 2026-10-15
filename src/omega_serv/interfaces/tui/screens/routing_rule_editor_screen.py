"""Modale d'edition des regles de routage conditionnel d'une zone de
reverse proxy (OMEGA-SERV_PLAN-DETAILLE_REVERSE_PROXY.md §17 : Phase
5bis). Meme principe que `upstream_editor_screen.py` (table + formulaire
dedie, jamais un champ texte a plat pour une structure a plusieurs
champs) : une regle = en-tete + motif + upstream cible (identite stable
`host:port`, §16.1).

Appelee en 3e etape du CRUD de zone (apres les champs de zone puis la
liste des backends, voir `reverse_proxy_screen.py`) - `upstreams` est
la liste DEJA CONFIRMEE a l'etape precedente, utilisee uniquement pour
afficher les identites valides en aide (la validation reelle de
`upstream_key` reste du ressort de `validate_proxy_zone`, point unique
de validation)."""
from __future__ import annotations

from typing import ClassVar

from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Center, Container, Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, DataTable, Static

from omega_serv.domain.routing.proxy_zone import RoutingRule, UpstreamTarget, upstream_key
from omega_serv.interfaces.tui.screens.confirm import ConfirmScreen
from omega_serv.interfaces.tui.screens.dynamic_form_screen import DynamicFormScreen


class RoutingRuleEditorScreen(ModalScreen[list[RoutingRule] | None]):
    BINDINGS: ClassVar[list[BindingType]] = [Binding("escape", "cancel", "Annuler", show=True)]

    def __init__(self, *, rules: list[RoutingRule], upstreams: list[UpstreamTarget]) -> None:
        super().__init__()
        self._rules: list[RoutingRule] = list(rules)
        self._upstream_keys = [upstream_key(u) for u in upstreams]
        self._selected_index: int | None = None

    def compose(self) -> ComposeResult:
        with Center(), Vertical(classes="omega-dynamic-form-box"):
            yield Static("REGLES DE ROUTAGE CONDITIONNEL (optionnel)", classes="omega-title")
            yield Static(
                "Si l'en-tete correspond au motif (egalite exacte, ou prefixe si le motif se "
                "termine par '*'), force cet upstream precis - sinon la strategie normale "
                "s'applique. Evaluee AVANT le cookie sticky et avant la strategie active. "
                f"Backends disponibles pour cette zone : {', '.join(self._upstream_keys) or '(aucun)'}.",
                classes="omega-hint",
            )
            yield Static("", id="rule-error", classes="omega-hint")
            yield DataTable(id="routing-rules-table")
            with Horizontal(classes="omega-actions"):
                with Container(classes="omega-btn-frame"):
                    yield Button("Ajouter", id="add", variant="primary")
                with Container(classes="omega-btn-frame"):
                    yield Button("Modifier", id="edit", disabled=True)
                with Container(classes="omega-btn-frame"):
                    yield Button("Supprimer", id="delete", variant="error", disabled=True)
            with Horizontal(classes="omega-confirm-buttons"):
                with Container(classes="omega-btn-frame"):
                    yield Button("Valider", id="confirm", variant="primary")
                with Container(classes="omega-btn-frame"):
                    yield Button("Annuler", id="cancel")

    def on_mount(self) -> None:
        table = self.query_one("#routing-rules-table", DataTable)
        table.cursor_type = "row"
        table.add_columns("En-tete", "Motif", "Upstream cible")
        self._refresh_table()

    def _refresh_table(self) -> None:
        table = self.query_one("#routing-rules-table", DataTable)
        table.clear()
        for index, rule in enumerate(self._rules):
            table.add_row(rule.header_name, rule.pattern, rule.upstream_key, key=str(index))
        self._selected_index = None
        self.query_one("#edit", Button).disabled = True
        self.query_one("#delete", Button).disabled = True

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        self._selected_index = int(str(event.row_key.value))
        self.query_one("#edit", Button).disabled = False
        self.query_one("#delete", Button).disabled = False

    @staticmethod
    def _fields_for(rule: RoutingRule | None) -> list[tuple[str, str, str]]:
        r = rule or RoutingRule(header_name="", pattern="", upstream_key="")
        return [
            ("header_name", "Nom de l'en-tete (ex: X-Canary)", r.header_name),
            ("pattern", "Motif (egalite exacte, ou se termine par '*' pour un prefixe)", r.pattern),
            ("upstream_key", "Upstream cible (host:port, voir la liste ci-dessus)", r.upstream_key),
        ]

    def _rule_from_values(self, values: dict[str, str]) -> RoutingRule | None:
        header_name = values["header_name"].strip()
        pattern = values["pattern"].strip()
        target = values["upstream_key"].strip()
        if not header_name or not pattern or not target:
            self.query_one("#rule-error", Static).update("Tous les champs sont requis.")
            return None
        return RoutingRule(header_name=header_name, pattern=pattern, upstream_key=target)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel":
            self.dismiss(None)
            return
        if event.button.id == "confirm":
            self.dismiss(list(self._rules))
            return
        if event.button.id == "add":
            self.app.push_screen(
                DynamicFormScreen(title="AJOUTER UNE REGLE", fields=self._fields_for(None)), self._add_rule,
            )
            return
        if event.button.id == "edit" and self._selected_index is not None:
            rule = self._rules[self._selected_index]
            self.app.push_screen(
                DynamicFormScreen(title="MODIFIER LA REGLE", fields=self._fields_for(rule)), self._edit_rule,
            )
            return
        if event.button.id == "delete" and self._selected_index is not None:
            self.app.push_screen(
                ConfirmScreen(title="SUPPRIMER LA REGLE", message="Confirmer la suppression de cette regle ?"),
                self._delete_rule,
            )

    def _add_rule(self, values: dict[str, str] | None) -> None:
        if values is None:
            return
        rule = self._rule_from_values(values)
        if rule is None:
            return
        self._rules.append(rule)
        self.query_one("#rule-error", Static).update("")
        self._refresh_table()

    def _edit_rule(self, values: dict[str, str] | None) -> None:
        if values is None or self._selected_index is None:
            return
        rule = self._rule_from_values(values)
        if rule is None:
            return
        self._rules[self._selected_index] = rule
        self.query_one("#rule-error", Static).update("")
        self._refresh_table()

    def _delete_rule(self, confirmed: bool | None) -> None:
        if not confirmed or self._selected_index is None:
            return
        del self._rules[self._selected_index]
        self._refresh_table()

    def action_cancel(self) -> None:
        self.dismiss(None)
