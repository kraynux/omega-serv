"""Sous-ecran Etat WAF (retour utilisateur 2026-09-13 : restructuration
du menu WAF - Etat/Modules/Tester/Custom, deplace du menu principal
"Active Securite" plutot que la Configuration detaillee, meme raison que
pour Active Defense : etat operationnel, pas un formulaire de reglages
statiques)."""
from __future__ import annotations

from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Button, Footer, Header, Static

from omega_serv.application.config.load_config import load_config
from omega_serv.core.i18n import _
from omega_serv.domain.security.waf.config import parse_waf_config
from omega_serv.interfaces.tui.screens._base import OmegaScreen

if TYPE_CHECKING:
    from omega_serv.bootstrap.container import DependencyContainer


class WafStatusScreen(OmegaScreen):
    def __init__(self, *, container: DependencyContainer) -> None:
        super().__init__()
        self._container = container

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(classes="omega-panel"):
            yield Static(_("WAF - ÉTAT"), classes="omega-title")
            yield Static(
                _("L'activation de l'option 'waf' se fait dans le menu Options."),
                classes="omega-hint",
            )
            yield Static("", id="status-body")
            with Horizontal(classes="omega-actions"), Container(classes="omega-btn-frame"):
                yield Button(_("Retour"), id="back")
        yield Footer()

    def on_mount(self) -> None:
        self._refresh()

    def _refresh(self) -> None:
        body = self.query_one("#status-body", Static)
        result = load_config(self._container.configuration, self._container.config_file)
        if not result.success or result.config is None:
            body.update(_("Erreur de configuration : ") + "; ".join(result.errors))
            return
        config = result.config
        option = config.options.get("waf")
        if option is None or not option.enabled:
            body.update(_("WAF : désactivé (options.waf.enabled = false ou absent)."))
            return
        waf_config = parse_waf_config(option.settings)
        lines = [
            _("WAF : actif (mode={mode})").format(mode=waf_config.mode),
            _("Comportement en cas d'erreur interne : {on_internal_error}").format(on_internal_error=waf_config.on_internal_error),
            _("Packs de règles référencés : {count}").format(count=len(waf_config.rule_paths)),
        ]
        lines.extend(f"  - {path}" for path in waf_config.rule_paths)
        if not waf_config.rule_paths:
            lines.append(_("  (AUCUN - le WAF ne peut rien détecter tant qu'aucun pack n'est référence, voir Modules)"))
        factory = self._container.blocklist_port_factory
        if factory is not None:
            port = factory(config, self._container.filesystem, self._container.project_root, self._container.clock)
            lines.append(_("Entrées en liste de blocage : {count}").format(count=len(port.list_entries())))
        body.update("\n".join(lines))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "back":
            self.dismiss()
