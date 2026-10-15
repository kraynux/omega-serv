"""Ecran Etat en direct des backends d'une zone (OMEGA-SERV_PLAN-DETAILLE_
REVERSE_PROXY.md §18.3/§22, reouverture) - ferme l'angle mort documente
depuis la Phase 6 ("declencheur TUI DRAINING/MAINTENANCE... differe, le
TUI et le serveur etant des processus SEPARES sans memoire partagee").

Passe desormais par la route `/.omega-serv-admin/health` (§22, injectee
via `container.admin_request_runner` - meme regime que
`simulate_request_screen.py`/`container.simulate_request_runner`,
`interfaces.tui` ne pouvant jamais importer `infrastructure` directement)
- un vrai appel HTTP LOCAL vers le PROCESSUS SERVEUR reellement en
cours d'execution, jamais une modification en memoire de cet ecran
(qui tourne dans un AUTRE processus).

`DRAINING`/`MAINTENANCE` restent EPHEMERES (§18.3 - jamais ecrits dans
la configuration, jamais persistes) : seul un REDEMARRAGE COMPLET du
serveur les efface (verifie : `reload_scoped()`, SIGHUP, ne touche
jamais `_proxy_health_state` - l'etat manuel survit a un simple
rechargement). `DOWN` reste toujours derive automatiquement, jamais
affecte par cet ecran."""
from __future__ import annotations

from typing import TYPE_CHECKING
from urllib.parse import urlencode

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Button, DataTable, Footer, Header, Static

from omega_serv.application.config.load_config import load_config
from omega_serv.interfaces.tui.screens._base import OmegaScreen

if TYPE_CHECKING:
    from omega_serv.bootstrap.container import DependencyContainer
    from omega_serv.domain.routing.proxy_zone import ProxyZone

_ADMIN_HEALTH_PATH = "/.omega-serv-admin/health"


class ReverseProxyUpstreamStatusScreen(OmegaScreen):
    def __init__(self, *, container: DependencyContainer, zone: ProxyZone) -> None:
        super().__init__()
        self._container = container
        self._zone = zone
        self._selected_upstream_key: str | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(classes="omega-panel"):
            yield Static("ETAT EN DIRECT DES BACKENDS", classes="omega-title")
            yield Static(
                f"Zone {self._zone.url_prefix!r} - interroge le serveur REELLEMENT en cours "
                "d'execution (pas la configuration sur disque). Necessite trusted_proxy actif "
                "avec 127.0.0.1 dans ses reseaux de confiance. DRAINING/MAINTENANCE sont "
                "ephemeres (jamais ecrits dans la configuration) - un redemarrage les efface.",
                classes="omega-hint",
            )
            yield Static("", id="status-error", classes="omega-hint")
            yield DataTable(id="upstream-status-table")
            with Horizontal(classes="omega-actions"):
                with Container(classes="omega-btn-frame"):
                    yield Button("Actualiser", id="refresh", variant="primary")
                with Container(classes="omega-btn-frame"):
                    yield Button("Mettre en DRAINING", id="draining", disabled=True)
                with Container(classes="omega-btn-frame"):
                    yield Button("Mettre en MAINTENANCE", id="maintenance", disabled=True)
            with Horizontal(classes="omega-actions"):
                with Container(classes="omega-btn-frame"):
                    yield Button("Revenir a l'automatique", id="clear", disabled=True)
                with Container(classes="omega-btn-frame"):
                    yield Button("Retour", id="back")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#upstream-status-table", DataTable)
        table.cursor_type = "row"
        table.add_columns("Upstream (host:port)", "Statut")
        self.run_worker(self._refresh(), exclusive=True)

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        self._selected_upstream_key = str(event.row_key.value)
        self.query_one("#draining", Button).disabled = False
        self.query_one("#maintenance", Button).disabled = False
        self.query_one("#clear", Button).disabled = False

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "back":
            self.dismiss()
            return
        if event.button.id == "refresh":
            await self._refresh()
            return
        if event.button.id in ("draining", "maintenance", "clear") and self._selected_upstream_key is not None:
            await self._set_status(event.button.id)

    def _port(self) -> int | None:
        load_result = load_config(self._container.configuration, self._container.config_file)
        if not load_result.success or load_result.config is None:
            return None
        return load_result.config.server.port

    async def _call(self, method: str, extra_query: dict[str, str]) -> tuple[int, dict | None] | None:
        runner = self._container.admin_request_runner
        if runner is None:
            return None
        port = self._port()
        if port is None:
            return None
        query = urlencode({"zone": self._zone.url_prefix, **extra_query})
        return await runner(port, method, f"{_ADMIN_HEALTH_PATH}?{query}")

    async def _refresh(self) -> None:
        error_widget = self.query_one("#status-error", Static)
        result = await self._call("GET", {})
        if result is None:
            error_widget.update(
                "Serveur injoignable - verifiez qu'il est demarre et que trusted_proxy autorise "
                "127.0.0.1 (fonctionnalite indisponible hors TUI avec runner d'administration cable)."
            )
            return
        status, body = result
        if status != 200 or body is None:
            error_widget.update(f"Reponse inattendue du serveur (statut {status}).")
            return
        error_widget.update("")
        table = self.query_one("#upstream-status-table", DataTable)
        table.clear()
        for upstream_key, upstream_status in body.get("upstreams", {}).items():
            table.add_row(upstream_key, upstream_status, key=upstream_key)
        self._selected_upstream_key = None
        self.query_one("#draining", Button).disabled = True
        self.query_one("#maintenance", Button).disabled = True
        self.query_one("#clear", Button).disabled = True

    async def _set_status(self, new_status: str) -> None:
        error_widget = self.query_one("#status-error", Static)
        assert self._selected_upstream_key is not None
        result = await self._call("POST", {"upstream": self._selected_upstream_key, "status": new_status})
        if result is None:
            error_widget.update("Serveur injoignable - le changement n'a pas pu etre applique.")
            return
        status, _body = result
        if status != 200:
            error_widget.update(f"Le serveur a refuse ce changement (statut {status}).")
            return
        await self._refresh()
