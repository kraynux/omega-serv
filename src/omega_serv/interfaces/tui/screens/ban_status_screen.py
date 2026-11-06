"""Active Securite -> INTERVENTION MANUELLE -> Statut (decisions utilisateur 2026-11-06) : TOUS les bans en cours
dans la blocklist du WAF (et la liste du script Magnet s'il est actif, en lecture seule), avec leur origine detaillee.
Lecture seule : chaque ban se leve la ou il a ete pose.

Exports : JSON et HTML (themes) de tous les bans ; TXT d'injection, bans actifs ou toute la liste - une adresse par
ligne, en-tete en commentaires « # » (format d'import d'omega-fire), reseaux seulement en commentaire."""
from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from omega_lib.theme.policies import DEFAULT_EXPORT_THEME, EXPORT_PALETTES
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, VerticalScroll
from textual.widgets import Button, DataTable, Footer, Header, Select, Static

from omega_serv.application.security.manual_intervention import (
    ban_rows_for_display,
    collect_ban_rows,
    magnet_list_path,
)
from omega_serv.core.i18n import _
from omega_serv.domain.security.waf.manual_intervention import (
    BanRow,
    TxtScope,
    ban_rows_payload,
    origin_label,
    render_injection_txt,
)
from omega_serv.interfaces.tui.screens._base import OmegaScreen
from omega_serv.interfaces.tui.screens._export_worker import run_html_export
from omega_serv.interfaces.tui.screens._intervention_access import (
    BlocklistUnavailable,
    open_blocklist,
)
from omega_serv.interfaces.tui.screens._riposte_access import cell, show

if TYPE_CHECKING:
    from omega_serv.bootstrap.container import DependencyContainer

_EXPORT_JSON = "json"
_EXPORT_HTML = "html"
_EXPORT_TXT_ACTIVE = "txt-active"
_EXPORT_TXT_ALL = "txt-all"
_EXPORT_FORMATS: tuple[tuple[str, str], ...] = (
    (_("JSON - tous les bans"), _EXPORT_JSON),
    (_("HTML - tous les bans (thème ci-dessous)"), _EXPORT_HTML),
    (_("TXT injection - bans actifs"), _EXPORT_TXT_ACTIVE),
    (_("TXT injection - toute la liste"), _EXPORT_TXT_ALL),
)


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")


class BanStatusScreen(OmegaScreen):
    def __init__(self, *, container: DependencyContainer) -> None:
        super().__init__()
        self._container = container
        self._rows: list[BanRow] = []

    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll(classes="omega-panel"):
            yield Static(_("STATUT DES BANS"), classes="omega-title")
            yield Static(
                _("Tous les bans de la blocklist du WAF, avec leur origine. Lecture seule : chaque ban se lève là où "
                  "il a été posé (Débannir pour l'intervention manuelle, WAF → Modules, RIPOSTE → Actions)."),
                classes="omega-hint",
            )
            yield Static("", id="status-error", classes="omega-hint")
            yield Static("", id="status-summary", classes="omega-hint")
            yield DataTable(id="status-table", classes="omega-riposte-table")
            yield Static(_("Format d'export"), classes="omega-subtitle")
            yield Select(_EXPORT_FORMATS, value=_EXPORT_JSON, allow_blank=False, id="export-format")
            yield Static(
                _("TXT injection : une adresse par ligne, lignes « # » ignorées - importable tel quel dans omega-fire "
                  "(Bannir une liste d'IPs). Un réseau n'y figure qu'en commentaire."),
                classes="omega-hint",
            )
            yield Static(_("Thème d'export HTML"), classes="omega-subtitle")
            yield Select(
                [(name, name) for name in EXPORT_PALETTES], value=DEFAULT_EXPORT_THEME, allow_blank=False,
                id="export-theme",
            )
        with Horizontal(classes="omega-actions omega-riposte-actions"):
            with Container(classes="omega-btn-frame"):
                yield Button(_("Exporter"), id="export", variant="primary")
            with Container(classes="omega-btn-frame"):
                yield Button(_("Rafraîchir"), id="refresh")
            with Container(classes="omega-btn-frame"):
                yield Button(_("Retour"), id="back")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#status-table", DataTable)
        table.cursor_type = "row"
        table.add_columns(_("Adresse / réseau"), _("Origine"), _("État"), _("Expiration"), _("Posé le"), _("Motif du ban"))
        self._refresh()

    def _refresh(self) -> None:
        table = self.query_one("#status-table", DataTable)
        table.clear()
        error = self.query_one("#status-error", Static)
        try:
            config, port = open_blocklist(self._container)
            self._rows, warning = collect_ban_rows(
                port, self._container.filesystem, magnet_list_path(config, self._container.project_root),
                self._container.clock.now())
        except BlocklistUnavailable as problem:
            show(error, str(problem))
            return
        except OSError as e:
            show(error, _("Blocklist illisible ou non modifiable : {error}").format(error=e))
            return
        show(error, warning)
        for shown in ban_rows_for_display(self._rows, short=True):
            table.add_row(cell(shown["network"]), cell(shown["origin"]), cell(shown["state"]), cell(shown["expires"]),
                          cell(shown["created"]), cell(shown["reason"]))
        show(self.query_one("#status-summary", Static), self._summary())

    def _summary(self) -> str:
        if not self._rows:
            return _("Aucun ban dans la blocklist.")
        active = [r for r in self._rows if r.active]
        by_origin = Counter(origin_label(r.origin) for r in active)
        detail = ", ".join(_("{label} : {count}").format(label=label, count=count) for label, count in by_origin.items())
        return _("{active} ban(s) actif(s) sur {total}").format(active=len(active), total=len(self._rows)) + (
            f" - {detail}" if detail else "")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "back":
            self.dismiss()
        elif event.button.id == "refresh":
            self._refresh()
        elif event.button.id == "export":
            self._export(str(self.query_one("#export-format", Select).value))

    def _exports_dir(self) -> Path:
        override = self._container.settings_store.get("exports_dir_override", "")
        return Path(override) if override else self._container.default_exports_dir

    def _export(self, kind: str) -> None:
        now = self._container.clock.now()
        if kind == _EXPORT_JSON:
            content = json.dumps(ban_rows_payload(self._rows, now), indent=2, ensure_ascii=False) + "\n"
            self._write(self._exports_dir() / f"omega-serv-bans.{_timestamp()}.json", content)
        elif kind in (_EXPORT_TXT_ACTIVE, _EXPORT_TXT_ALL):
            scope: TxtScope = "active" if kind == _EXPORT_TXT_ACTIVE else "all"
            self._write(self._exports_dir() / f"omega-serv-bans-{scope}.{_timestamp()}.txt",
                        render_injection_txt(self._rows, scope, now))
        elif kind == _EXPORT_HTML:
            theme = str(self.query_one("#export-theme", Select).value)
            shown = ban_rows_for_display(self._rows)
            active = sum(1 for r in self._rows if r.active)
            run_html_export(
                self, self._container,
                lambda: self._container.export_bans_html(shown, active, theme),
                lambda content: self._write(self._exports_dir() / f"omega-serv-bans.{_timestamp()}.html", content),
                lambda reason: show(self.query_one("#status-error", Static), reason),
            )

    def _write(self, path: Path, content: str) -> None:
        try:
            self._container.filesystem.make_directory(path.parent)
            self._container.filesystem.write_text(path, content)
        except OSError as e:
            show(self.query_one("#status-error", Static), _("Export impossible : {error}").format(error=e))
            return
        self.app.notify(_("Export écrit : {export_path}").format(export_path=path))
