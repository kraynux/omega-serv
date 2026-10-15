"""Modale d'edition de la liste des upstreams d'une zone de reverse proxy
(OMEGA-SERV_PLAN-DETAILLE_REVERSE_PROXY.md §16.2/§28.1 : Phase 5).

Remplace l'ancien champ texte a plat "host:port, host:port, ..." de
`reverse_proxy_screen.py` - reconnu illisible des qu'un poids ou
plusieurs upstreams s'accumulent (§28.1). Un backend se saisit desormais
via un formulaire dedie (host/port/TLS/poids), un par un, dans une table.

Appelee en 2e etape du CRUD de zone (apres les champs de zone eux-memes :
prefixe, strategie, delais, options - voir `reverse_proxy_screen.py`) -
retourne la liste finale d'`UpstreamTarget` au clic sur "Valider", `None`
sur "Annuler"/echap (la zone appelante abandonne alors toute la saisie,
meme les champs de zone deja remplis a l'etape precedente - coherent
avec le reste du projet : un "Annuler" annule toujours l'operation
entiere, jamais une sauvegarde partielle silencieuse). La validation de
plage du port (1-65535) et du "au moins un upstream" restent du ressort
de `validate_proxy_zone` (point unique de validation, appele par
l'ecran appelant une fois la liste revenue) - seule la forme (port/poids
entiers, host non vide) est verifiee ici, immediatement, pour un retour
rapide a la saisie."""
from __future__ import annotations

from typing import ClassVar

from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Center, Container, Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, DataTable, Static

from omega_serv.domain.routing.proxy_zone import UpstreamTarget
from omega_serv.interfaces.tui.screens.confirm import ConfirmScreen
from omega_serv.interfaces.tui.screens.dynamic_form_screen import DynamicFormScreen


class UpstreamEditorScreen(ModalScreen[list[UpstreamTarget] | None]):
    BINDINGS: ClassVar[list[BindingType]] = [Binding("escape", "cancel", "Annuler", show=True)]

    def __init__(self, *, upstreams: list[UpstreamTarget]) -> None:
        super().__init__()
        self._upstreams: list[UpstreamTarget] = list(upstreams)
        self._selected_index: int | None = None

    def compose(self) -> ComposeResult:
        with Center(), Vertical(classes="omega-dynamic-form-box"):
            yield Static("BACKENDS DE LA ZONE", classes="omega-title")
            yield Static(
                "Au moins un backend est requis. Le poids n'a d'effet qu'avec une strategie "
                "ponderee (weighted_round_robin, weighted_least_connections, ip_hash).",
                classes="omega-hint",
            )
            yield Static("", id="upstream-error", classes="omega-hint")
            yield DataTable(id="upstreams-table")
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
        table = self.query_one("#upstreams-table", DataTable)
        table.cursor_type = "row"
        table.add_columns("Host", "Port", "TLS", "Poids", "Charge", "Plafond", "Sonde active")
        self._refresh_table()

    def _refresh_table(self) -> None:
        table = self.query_one("#upstreams-table", DataTable)
        table.clear()
        for index, upstream in enumerate(self._upstreams):
            table.add_row(
                upstream.host, str(upstream.port), "Oui" if upstream.use_tls else "Non", str(upstream.weight),
                upstream.load_source,
                str(upstream.max_concurrent_requests) if upstream.max_concurrent_requests is not None else "illimite",
                "Oui" if upstream.active_health_check_enabled else "Non",
                key=str(index),
            )
        self._selected_index = None
        self.query_one("#edit", Button).disabled = True
        self.query_one("#delete", Button).disabled = True

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        self._selected_index = int(str(event.row_key.value))
        self.query_one("#edit", Button).disabled = False
        self.query_one("#delete", Button).disabled = False

    @staticmethod
    def _fields_for(upstream: UpstreamTarget | None) -> list[tuple[str, str, str]]:
        u = upstream or UpstreamTarget(host="", port=0)
        return [
            ("host", "Host (ex: 127.0.0.1)", u.host),
            ("port", "Port (1-65535)", str(u.port) if u.port else ""),
            ("use_tls", "HTTPS vers ce backend (oui/non)", "oui" if u.use_tls else "non"),
            ("weight", "Poids (entier >= 1 - sans effet hors strategie ponderee)", str(u.weight)),
            (
                "load_source",
                "Source de charge reelle (none/native/declarative - §19, sans effet hors strategie real_load)",
                u.load_source,
            ),
            (
                "load_check_path",
                "Chemin de charge declarative (sans effet si load_source != declarative)",
                u.load_check_path,
            ),
            (
                "max_concurrent_requests",
                "Plafond de connexions actives (entier >= 1, vide = illimite - §20)",
                str(u.max_concurrent_requests) if u.max_concurrent_requests is not None else "",
            ),
            (
                "active_health_check_enabled",
                "Sonde de sante active periodique, independante du trafic reel (oui/non - §18.2)",
                "oui" if u.active_health_check_enabled else "non",
            ),
            (
                "active_health_check_path",
                "Chemin sonde par la sonde active (sans effet si sonde active desactivee)",
                u.active_health_check_path,
            ),
        ]

    def _upstream_from_values(self, values: dict[str, str]) -> UpstreamTarget | None:
        host = values["host"].strip()
        if not host:
            self.query_one("#upstream-error", Static).update("Host requis.")
            return None
        max_concurrent_text = values["max_concurrent_requests"].strip()
        try:
            port = int(values["port"].strip())
            weight = int(values["weight"].strip())
            max_concurrent_requests = int(max_concurrent_text) if max_concurrent_text else None
        except ValueError:
            self.query_one("#upstream-error", Static).update(
                "Port, poids et plafond de connexions doivent etre des nombres entiers (plafond vide = illimite).",
            )
            return None
        use_tls = values["use_tls"].strip().lower() in ("oui", "yes", "true")
        return UpstreamTarget(
            host=host, port=port, use_tls=use_tls, weight=weight,
            load_source=values["load_source"].strip() or "none",
            load_check_path=values["load_check_path"].strip() or "/",
            max_concurrent_requests=max_concurrent_requests,
            active_health_check_enabled=values["active_health_check_enabled"].strip().lower() in ("oui", "yes", "true"),
            active_health_check_path=values["active_health_check_path"].strip() or "/",
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel":
            self.dismiss(None)
            return
        if event.button.id == "confirm":
            self.dismiss(list(self._upstreams))
            return
        if event.button.id == "add":
            self.app.push_screen(
                DynamicFormScreen(title="AJOUTER UN BACKEND", fields=self._fields_for(None)), self._add_upstream,
            )
            return
        if event.button.id == "edit" and self._selected_index is not None:
            upstream = self._upstreams[self._selected_index]
            self.app.push_screen(
                DynamicFormScreen(title="MODIFIER LE BACKEND", fields=self._fields_for(upstream)), self._edit_upstream,
            )
            return
        if event.button.id == "delete" and self._selected_index is not None:
            self.app.push_screen(
                ConfirmScreen(title="SUPPRIMER LE BACKEND", message="Confirmer la suppression de ce backend ?"),
                self._delete_upstream,
            )

    def _add_upstream(self, values: dict[str, str] | None) -> None:
        if values is None:
            return
        upstream = self._upstream_from_values(values)
        if upstream is None:
            return
        self._upstreams.append(upstream)
        self.query_one("#upstream-error", Static).update("")
        self._refresh_table()

    def _edit_upstream(self, values: dict[str, str] | None) -> None:
        if values is None or self._selected_index is None:
            return
        upstream = self._upstream_from_values(values)
        if upstream is None:
            return
        self._upstreams[self._selected_index] = upstream
        self.query_one("#upstream-error", Static).update("")
        self._refresh_table()

    def _delete_upstream(self, confirmed: bool | None) -> None:
        if not confirmed or self._selected_index is None:
            return
        del self._upstreams[self._selected_index]
        self._refresh_table()

    def action_cancel(self) -> None:
        self.dismiss(None)
