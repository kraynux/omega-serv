"""Echeances des certificats (etude modules du panneau web, module 3, 2026-11-17) : tous les certificats locaux de
l'instance (site, panneau web, secure/certificates/), meme liste que la vue Certificats du panneau web. Lecture seule ;
openssl lance hors du fil de l'ecran."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from rich.text import Text
from textual import work
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, VerticalScroll
from textual.widgets import Button, Footer, Header, Static

from omega_serv.application.admin_web.checks import admin_web_settings
from omega_serv.application.config.load_config import load_config
from omega_serv.application.tls.certificate_inventory import (
    CertificateLine,
    certificate_sources,
    inspect_all,
    state_text,
    tone,
)
from omega_serv.core.i18n import _
from omega_serv.interfaces.tui.screens._base import OmegaScreen

if TYPE_CHECKING:
    from omega_serv.bootstrap.container import DependencyContainer

_STYLES = {"ok": "green", "warn": "yellow", "error": "bold red", "dim": "dim"}


class CertificateExpiryScreen(OmegaScreen):
    def __init__(self, *, container: DependencyContainer) -> None:
        super().__init__()
        self._container = container

    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll(classes="omega-panel"):
            yield Static(_("ÉCHÉANCES DES CERTIFICATS"), classes="omega-title")
            yield Static(_("Certificats de cette instance (site, panneau web, secure/certificates/), lus par openssl. "
                           "Les clés privées ne sont jamais lues. Le panneau web montre la même liste et alerte à 30, "
                           "14, 7 et 1 jour de l'échéance."), classes="omega-hint")
            yield Static(_("Lecture en cours..."), id="certificates-text")
        with Horizontal(classes="omega-actions"):
            with Container(classes="omega-btn-frame"):
                yield Button(_("Rafraîchir"), id="refresh", variant="primary")
            with Container(classes="omega-btn-frame"):
                yield Button(_("Retour"), id="back")
        yield Footer()

    def on_mount(self) -> None:
        self._load()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "back":
            self.dismiss()
        elif event.button.id == "refresh":
            self.query_one("#certificates-text", Static).update(_("Lecture en cours..."))
            self._load()

    @work(thread=True, exclusive=True)
    def _load(self) -> None:
        container = self._container
        result = load_config(container.configuration, container.config_file)
        if not result.success or result.config is None:
            self.app.call_from_thread(self._show, None, "; ".join(result.errors))
            return
        config = result.config
        settings = admin_web_settings(config)
        admin = Path(settings.certificate_path) if settings is not None and settings.tls == "own" else None
        sources = certificate_sources(config, container.project_root, container.filesystem, admin)
        lines = inspect_all(sources, container.project_root, container.filesystem,
                            container.certificate_tool_factory, datetime.now(timezone.utc))
        self.app.call_from_thread(self._show, lines, "")

    def _show(self, lines: list[CertificateLine] | None, error: str) -> None:
        widget = self.query_one("#certificates-text", Static)
        if lines is None:
            widget.update(_("Erreur de configuration : ") + error)
            return
        if not lines:
            widget.update(_("Aucun certificat dans cette instance."))
            return
        text = Text()
        for line in lines:
            text.append(f"{line.label} : {line.path}\n", style="bold")
            text.append(f"  {state_text(line)}", style=_STYLES[tone(line)])
            if line.not_after:
                text.append("  " + _("(fin de validité : {date})").format(date=line.not_after))
            text.append("\n")
            if line.names or line.subject:
                text.append("  " + (", ".join(line.names[:6]) or line.subject) + "\n", style="dim")
            text.append("\n")
        widget.update(text)
