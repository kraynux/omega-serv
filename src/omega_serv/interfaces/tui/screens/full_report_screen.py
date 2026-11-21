# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Rapport complet (projets 3.0.0 §7.7 et §7.10, decisions de l'auteur du 2026-11-15) : un sommaire a l'ecran (le
minimum non desactivable), le detail coche seulement dans l'export (HTML aux 5 themes d'export, TXT, JSON). La
generation tourne hors du fil de l'interface, avec un indicateur d'attente : l'ecran ne gele jamais."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

from omega_lib.theme.policies import DEFAULT_EXPORT_THEME, EXPORT_PALETTES
from rich.markup import escape
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.widgets import Button, Checkbox, Footer, Header, Select, Static

from omega_serv.application.config.load_config import load_config
from omega_serv.application.report.full_report import DETAIL_KEYS
from omega_serv.application.report.full_report_presentation import sections
from omega_serv.core.i18n import _
from omega_serv.interfaces.tui.screens._base import OmegaScreen, main_menu_title

if TYPE_CHECKING:
    from omega_serv.bootstrap.container import DependencyContainer


def _detail_labels() -> dict[str, str]:
    return {
        "zones": _("Détail des zones (alias, redirections, rewrites, FastCGI, envois, accès, cache)"),
        "reverse_proxy": _("Reverse proxy : zones, backends, santé, équilibrage"),
        "waf": _("Règles WAF : packs, listes, débit, exclusions"),
        "active_defense": _("Réglages d'Active Defense et de RIPOSTE"),
        "logs_library": _("Journaux suivis (bibliothèque)"),
        "options_settings": _("Toutes les options avec leurs réglages (sans secret)"),
        "audit": _("Audit de sécurité complet (peut être long)"),
    }


class FullReportScreen(OmegaScreen):
    def __init__(self, *, container: DependencyContainer) -> None:
        super().__init__()
        self._container = container

    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll(classes="omega-panel omega-main-panel"):
            yield main_menu_title(_("RAPPORT COMPLET"))
            yield Static(_("Ce qui est configuré et actif, d'un coup d'œil (réglages et système, pas le trafic). "
                           "Le sommaire est ci-dessous ; le détail coché va dans l'export. Aucun secret n'est "
                           "inclus."), classes="omega-hint")
            yield Static("", id="report-summary")
            yield Static(_("Détail à inclure dans l'export"), classes="omega-subtitle")
            for key, label in _detail_labels().items():
                yield Checkbox(label, id=f"detail-{key}")
            yield Static(_("Format"), classes="omega-subtitle")
            yield Select([(_("HTML (thème ci-dessous)"), "html"), ("TXT", "txt"), ("JSON", "json")], value="html",
                         allow_blank=False, id="export-format")
            yield Static(_("Thème de l'export HTML"), classes="omega-subtitle")
            yield Select([(name, name) for name in EXPORT_PALETTES], value=DEFAULT_EXPORT_THEME, allow_blank=False,
                         id="export-theme")
            yield Static("", id="report-error", classes="omega-hint")
        with Vertical(classes="omega-proxy-actions"):
            with Horizontal(classes="omega-actions omega-riposte-actions"):
                with Container(classes="omega-btn-frame"):
                    yield Button(_("Actualiser"), id="refresh")
                with Container(classes="omega-btn-frame"):
                    yield Button(_("Exporter"), id="export", variant="primary")
            with Horizontal(classes="omega-actions omega-riposte-actions omega-service-back"), \
                    Container(classes="omega-btn-frame"):
                yield Button(_("Retour"), id="back")
        yield Footer()

    def on_mount(self) -> None:
        self._generate(export=None)

    def _details(self) -> frozenset[str]:
        return frozenset(key for key in DETAIL_KEYS if self.query_one(f"#detail-{key}", Checkbox).value)

    def _busy(self, busy: bool, message: str = "") -> None:
        self.query_one("#report-summary", Static).loading = busy
        for button_id in ("#refresh", "#export"):
            self.query_one(button_id, Button).disabled = busy
        self.query_one("#report-error", Static).update(message)

    def _generate(self, export: str | None) -> None:
        load_result = load_config(self._container.configuration, self._container.config_file)
        if not load_result.success or load_result.config is None:
            self.query_one("#report-error", Static).update(
                _("Erreur de configuration : ") + "; ".join(load_result.errors))
            return
        config = load_result.config
        details = self._details() if export is not None else frozenset()
        theme = str(self.query_one("#export-theme", Select).value)
        self._busy(True, _("Génération du rapport en cours..."))

        def work() -> None:
            try:
                payload = self._container.collect_full_report(config, details)
                content = self._export_content(export, payload, theme) if export is not None else None
            except Exception as exc:  # noqa: BLE001 - jamais un ecran fige : l'erreur est dite
                self.app.call_from_thread(self._failed, str(exc))
                return
            self.app.call_from_thread(self._done, payload, export, content)

        self.run_worker(work, thread=True, exclusive=True, group="full-report")

    def _export_content(self, export: str, payload: dict[str, Any], theme: str) -> str | None:
        if export == "json":
            return json.dumps(payload, indent=2, ensure_ascii=False, default=str) + "\n"
        kind = "full-report" if export == "html" else "full-report-txt"
        return self._container.export_payload(kind, payload, theme)

    def _failed(self, message: str) -> None:
        self._busy(False, _("Rapport impossible : {error}").format(error=message))

    def _done(self, payload: dict[str, Any], export: str | None, content: str | None) -> None:
        self._busy(False)
        lines: list[str] = []
        for section in sections(payload)[:10]:
            lines.append(f"[b]{escape(str(section['title']))}[/b]")
            lines.extend(f"  {escape(str(label))} : {escape(str(value))}" for label, value in section["rows"])
            lines.append("")
        self.query_one("#report-summary", Static).update("\n".join(lines))
        if export is None:
            return
        if content is None:
            self.query_one("#report-error", Static).update(
                self._container.last_export_error or _("Export indisponible dans cet environnement."))
            return
        override = self._container.settings_store.get("exports_dir_override", "")
        directory = Path(override) if override else self._container.default_exports_dir
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        path = directory / f"omega-serv-rapport.{stamp}.{export}"
        try:
            self._container.filesystem.make_directory(directory)
            self._container.filesystem.write_text(path, content)
        except OSError as exc:
            self.query_one("#report-error", Static).update(_("Export impossible : {error}").format(error=exc))
            return
        self.app.notify(_("Export écrit : {export_path}").format(export_path=path))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "back":
            self.dismiss()
        elif event.button.id == "refresh":
            self._generate(export=None)
        elif event.button.id == "export":
            self._generate(export=str(self.query_one("#export-format", Select).value))
