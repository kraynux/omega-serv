"""Ecran Sante des logs (Gestion des logs, colonne MAINTENANCE - 2026-11-07, OMEGA-SERV_A_FAIRE_STATS_DEPUIS_
OMEGA_LOG.md, lot 4 ; retour utilisateur : « il faut que ce soit assez complet, avec une fonction d'export »).

Controle en lecture seule des logs d'omega-serv et de la Bibliotheque, du disque qui les porte et des
archives (regles : domain/logs/health.py ; collecte : application/logs/log_health.py). Une ligne par log
(OK, Info, Attention, Probleme) ; la ligne surlignee montre tous ses constats et ce qu'on peut faire.

Actions qui ecrivent, toujours apres confirmation : « Corriger les droits » (log d'omega-serv que le compte
du service ne peut plus alimenter, piege des logs crees en 644 : bit d'ecriture du groupe, sans sudo, si vous
etes proprietaire) et « Corriger avec sudo » (2026-11-07, demande utilisateur : quand les droits bloquent,
`chgrp` + `chmod g+w`, ou `chmod o-w` pour un log inscriptible par tout le monde - la commande exacte est
montree avant). « Analyser avec sudo » complete les dates et le format des logs illisibles par votre compte.
Export JSON (donnees), HTML (5 themes) et TXT, dans la langue des exports.

La collecte tourne dans un thread : elle ne lit que le debut et la fin de chaque log (quelques
millisecondes), l'interface reste libre meme avec beaucoup de logs ou un disque lent."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from omega_lib.theme.policies import DEFAULT_EXPORT_THEME, EXPORT_PALETTES
from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, VerticalScroll
from textual.css.query import NoMatches
from textual.widgets import Button, DataTable, Footer, Header, Select, Static

from omega_serv.application.config.load_config import load_config
from omega_serv.application.logs.health_presentation import (
    archives_line,
    automations_line,
    disk_line,
    finding_hint,
    finding_text,
    format_age,
    level_label,
    log_facts_line,
    log_summary,
    origin_label,
    report_to_dict,
)
from omega_serv.application.logs.library import list_library
from omega_serv.application.logs.log_health import (
    apply_write_fix,
    archive_facts,
    collect_log_health,
    health_targets,
)
from omega_serv.application.logs.privileged_logs import (
    run_sudo_fix,
    shown_command,
    sudo_fix_commands,
)
from omega_serv.application.logs.rotation_automation import rotation_schedule_status
from omega_serv.application.logs.stats_presentation import format_bytes
from omega_serv.application.services.resolve_current_service_name import (
    resolve_current_service_account,
    resolve_current_service_name,
)
from omega_serv.core.i18n import _
from omega_serv.domain.logs.health import evaluate_automations
from omega_serv.interfaces.tui.screens._base import OmegaScreen
from omega_serv.interfaces.tui.screens._elevation import request_elevation
from omega_serv.interfaces.tui.screens._export_worker import run_html_export
from omega_serv.interfaces.tui.screens.confirm import ConfirmScreen

if TYPE_CHECKING:
    from omega_serv.bootstrap.container import DependencyContainer
    from omega_serv.ports.process_runner_port import ProcessRunnerPort


def _export_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")


class LogHealthScreen(OmegaScreen):
    def __init__(self, *, container: DependencyContainer) -> None:
        super().__init__()
        self._container = container
        self._data: dict | None = None
        self._analysing = False
        self._runner: ProcessRunnerPort | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll(classes="omega-panel"):
            yield Static(_("SANTÉ DES LOGS"), classes="omega-title")
            yield Static(_("Contrôle en lecture seule des logs d'omega-serv et de la Bibliothèque, du disque "
                           "qui les porte et des archives. Surlignez un log pour voir le détail."),
                         classes="omega-hint")
            yield Static("", id="health-status", classes="omega-hint")
            yield Static("", id="health-summary")
            yield DataTable(id="health-table")
            yield Static("", id="health-detail")
            with Horizontal(classes="omega-actions"):
                with Container(classes="omega-btn-frame"):
                    yield Button(_("Relancer l'analyse"), id="refresh", variant="primary")
                with Container(classes="omega-btn-frame"):
                    yield Button(_("Analyser avec sudo"), id="analyse-sudo", disabled=True)
                with Container(classes="omega-btn-frame"):
                    yield Button(_("Corriger les droits"), id="fix", disabled=True)
                with Container(classes="omega-btn-frame"):
                    yield Button(_("Corriger avec sudo"), id="fix-sudo", disabled=True)
            yield Static(_("DISQUES"), classes="omega-subtitle")
            yield Static("", id="health-disks")
            yield Static(_("ARCHIVES"), classes="omega-subtitle")
            yield Static("", id="health-archives")
            yield Static(_("AUTOMATISATIONS"), classes="omega-subtitle")
            yield Static("", id="health-automations")

            yield Static(_("Thème d'export HTML"), classes="omega-subtitle")
            yield Select([(name, name) for name in EXPORT_PALETTES], value=DEFAULT_EXPORT_THEME, allow_blank=False,
                         id="theme-select")
            with Horizontal(classes="omega-actions"):
                with Container(classes="omega-btn-frame"):
                    yield Button(_("Exporter JSON"), id="export-json")
                with Container(classes="omega-btn-frame"):
                    yield Button(_("Exporter HTML"), id="export-html")
                with Container(classes="omega-btn-frame"):
                    yield Button(_("Exporter TXT"), id="export-txt")
                with Container(classes="omega-btn-frame"):
                    yield Button(_("Retour"), id="back")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#health-table", DataTable)
        table.cursor_type = "row"
        # Origine dans le detail seulement : le constat doit rester visible sans defilement horizontal.
        table.add_columns(_("État"), _("Log"), _("Taille"), _("Modifié"), _("Constat"))
        self._analyse()

    # ---- analyse -----------------------------------------------------------

    def _analyse(self) -> None:
        if self._analysing:
            return
        self._analysing = True
        self.query_one("#refresh", Button).disabled = True
        self.query_one("#health-status", Static).update(_("Analyse en cours…"))
        runner = self._runner
        self.run_worker(lambda: self._collect(runner), thread=True, group="log-health")

    def _analyse_with_sudo(self) -> None:
        runner = request_elevation(self, self._container)
        if runner is not None:
            self._runner = runner
            self._analyse()

    def _collect(self, runner: ProcessRunnerPort | None) -> None:
        container = self._container
        try:
            load_result = load_config(container.configuration, container.config_file)
            config = load_result.config if load_result.success else None
            library = list_library(container.build_log_library_repository())
            account = resolve_current_service_account(
                container.instance_registry, container.filesystem, container.settings_store,
                container.project_root, container.systemd_unit_dir,
            )
            rotation = None if config is None else config.logs.rotation
            archive_dir = container.project_root / "var" / "backups" / "logs"
            store = container.build_archive_store(archive_dir)
            infos = [store.get_archive_info(path) for path in store.list_archives()]
            report = collect_log_health(
                health_targets(None if config is None else config.logs, container.project_root, library),
                file_access=container.file_access,
                service_account=account,
                rotation_max_bytes=rotation.max_bytes if rotation is not None and rotation.enabled else None,
                archives=archive_facts(archive_dir, infos, None if rotation is None else rotation.keep),
                privileged_runner=runner,
            )
            automations = container.build_rotation_automation_store().list_all()
            report.automations = evaluate_automations(
                automations, self._schedule_installed(bool(automations)), datetime.now(timezone.utc))
            data = report_to_dict(report)
            warning = None if config is not None else _("Erreur de configuration : ") + "; ".join(load_result.errors)
        except Exception as exc:  # noqa: BLE001 - jamais planter l'interface pour un controle
            self.app.call_from_thread(self._show_error, str(exc))
            return
        self.app.call_from_thread(self._apply, data, warning)

    def _schedule_installed(self, has_automations: bool) -> bool | None:
        """Tache planifiee des automatisations presente ? None si rien a verifier ou verification impossible."""
        runner_factory = self._container.privileged_runner_factory
        if not has_automations or runner_factory is None:
            return None
        factory = self._container.service_manager_factory
        manager = factory() if factory is not None else None
        service_name = resolve_current_service_name(
            self._container.instance_registry, self._container.filesystem,
            self._container.settings_store, self._container.project_root,
        )
        status = rotation_schedule_status(service_name, manager, runner_factory())
        return None if status.mechanism == "manual" else status.success

    def _finish(self) -> None:
        self._analysing = False
        try:
            self.query_one("#refresh", Button).disabled = False
        except NoMatches:
            pass  # ecran deja ferme

    def _show_error(self, message: str) -> None:
        self._finish()
        try:
            self.query_one("#health-status", Static).update(_("Erreur : {message}").format(message=message))
        except NoMatches:
            pass  # ecran deja ferme

    def _styles(self) -> dict[str, str]:
        variables = self.app.get_css_variables()
        return {
            "ok": variables.get("success", "green") or "green",
            "info": variables.get("secondary", "cyan") or "cyan",
            "warning": variables.get("warning", "yellow") or "yellow",
            "problem": f"bold {variables.get('error', 'red') or 'red'}",
        }

    def _apply(self, data: dict, warning: str | None) -> None:
        self._finish()
        self._data = data
        try:
            table = self.query_one("#health-table", DataTable)
        except NoMatches:
            return  # ecran deja ferme
        styles = self._styles()
        now = datetime.fromisoformat(data["generated_at"])
        self.query_one("#health-status", Static).update(warning or _("Analysé {age}.").format(
            age=format_age(data["generated_at"], datetime.now(timezone.utc))))
        summary = Text()
        summary.append(_("Résumé : "), style="bold")
        for index, code in enumerate(("ok", "info", "warning", "problem")):
            count = data["counts"][code]
            summary.append(" · " if index else "")
            summary.append(f"{count} {level_label(code)}", style=styles[code] if count else "dim")
        self.query_one("#health-summary", Static).update(summary)

        cursor = table.cursor_row
        table.clear()
        for log in data["logs"]:
            size = "-" if log["size_bytes"] is None else format_bytes(float(log["size_bytes"]))
            table.add_row(
                Text(level_label(log["level"]), style=styles[log["level"]]),
                log["path"], size, format_age(log["modified_at"], now), log_summary(log),
            )
        if data["logs"]:
            table.move_cursor(row=min(cursor, len(data["logs"]) - 1))
        unreadable = any(f["code"] == "unreadable" for log in data["logs"] for f in log["findings"])
        self.query_one("#analyse-sudo", Button).disabled = not unreadable or self._runner is not None
        self._show_detail(table.cursor_row)

        disks = Text()
        for disk in data["disks"]:
            disks.append(f"[{level_label(disk['level'])}] ", style=styles[disk["level"]])
            disks.append(disk_line(disk) + "\n")
            for finding in disk["findings"]:
                self._append_finding(disks, finding, disk["mount_point"], styles)
        self.query_one("#health-disks", Static).update(disks if data["disks"] else "-")
        archives = data["archives"]
        self.query_one("#health-archives", Static).update("-" if archives is None else archives_line(archives))
        automations_text = Text()
        if data.get("automations") is not None:
            automations_text.append(f"[{level_label(data['automations']['level'])}] ",
                                    style=styles[data["automations"]["level"]])
            automations_text.append(automations_line(data["automations"]) + "\n")
            for finding in data["automations"]["findings"]:
                self._append_finding(automations_text, finding, "", styles)
        self.query_one("#health-automations", Static).update(automations_text)

    def _append_finding(self, content: Text, finding: dict, path: str, styles: dict[str, str]) -> None:
        content.append("  ● ", style=styles[finding["level"]])
        content.append(finding_text(finding) + "\n")
        hint = finding_hint(finding, path)
        if hint:
            content.append(f"    → {hint}\n", style="dim")

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        if event.data_table.id == "health-table":
            self._show_detail(event.cursor_row)

    def _selected_log(self, row: int | None = None) -> dict | None:
        if self._data is None or not self._data["logs"]:
            return None
        index = self.query_one("#health-table", DataTable).cursor_row if row is None else row
        return self._data["logs"][index] if 0 <= index < len(self._data["logs"]) else None

    def _show_detail(self, row: int) -> None:
        log = self._selected_log(row)
        fix_button = self.query_one("#fix", Button)
        sudo_button = self.query_one("#fix-sudo", Button)
        if log is None or self._data is None:
            self.query_one("#health-detail", Static).update("")
            fix_button.disabled = sudo_button.disabled = True
            return
        styles = self._styles()
        content = Text()
        content.append(f"\n{log['path']}\n", style="bold")
        content.append(origin_label(log) + "\n", style="dim")
        facts = log_facts_line(log, datetime.fromisoformat(self._data["generated_at"]))
        if facts:
            content.append(facts + "\n", style="dim")
        if not log["findings"]:
            content.append("  ● ", style=styles["ok"])
            content.append(_("Aucun problème.") + "\n")
        for finding in log["findings"]:
            self._append_finding(content, finding, log["path"], styles)
        self.query_one("#health-detail", Static).update(content)
        fix_button.disabled = log.get("write_fix_mode") is None
        sudo_button.disabled = not self._sudo_commands(log)

    def _sudo_commands(self, log: dict) -> list[list[str]]:
        if self._container.privileged_runner_factory is None:
            return []
        commands: list[list[str]] = []
        for finding in log["findings"]:
            if finding["code"] == "writer_cannot_write" and "new_mode" in finding.get("params", {}):
                continue  # corrigeable sans sudo : bouton « Corriger les droits »
            commands += sudo_fix_commands(finding["code"], log["path"], log.get("writer"))
        return commands

    # ---- correction des droits ---------------------------------------------

    def _fix_selected(self) -> None:
        log = self._selected_log()
        if log is None or log.get("write_fix_mode") is None:
            return
        path, mode = log["path"], log["write_fix_mode"]
        self.app.push_screen(
            ConfirmScreen(
                title=_("CORRIGER LES DROITS ?"),
                message=_("{path} : droits {old} → {new}, pour que le compte {account} puisse y écrire.").format(
                    path=path, old=log["mode"], new=mode, account=log.get("writer") or ""),
            ),
            lambda confirmed: self._fix_if_confirmed(confirmed, path, mode),
        )

    def _fix_with_sudo(self) -> None:
        log = self._selected_log()
        commands = [] if log is None else self._sudo_commands(log)
        if log is None or not commands:
            return
        path = log["path"]
        self.app.push_screen(
            ConfirmScreen(
                title=_("CORRIGER AVEC SUDO ?"),
                message=_("Commande lancée après votre mot de passe :\n{command}").format(command=shown_command(commands)),
            ),
            lambda confirmed: self._fix_with_sudo_if_confirmed(confirmed, path, commands),
        )

    def _fix_with_sudo_if_confirmed(self, confirmed: bool | None, path: str, commands: list[list[str]]) -> None:
        if not confirmed:
            return
        runner = request_elevation(self, self._container)  # sans mot de passe si sudo est encore valide
        if runner is None:
            return
        self._runner = runner
        error = run_sudo_fix(runner, commands)
        if error is not None:
            self.app.notify(_("Correction impossible : {error}").format(error=error), severity="error")
            return
        self.app.notify(_("Droits corrigés avec sudo : {path}.").format(path=path))
        self._analyse()

    def _fix_if_confirmed(self, confirmed: bool | None, path: str, mode: str) -> None:
        if not confirmed:
            return
        try:
            apply_write_fix(self._container.file_access, path, int(mode, 8))
        except OSError as exc:
            self.app.notify(_("Correction impossible : {error}").format(error=exc), severity="error")
            return
        self.app.notify(_("Droits corrigés : {path} ({mode}).").format(path=path, mode=mode))
        self._analyse()

    # ---- boutons et exports ------------------------------------------------

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id or ""
        if button_id == "back":
            self.dismiss()
        elif button_id == "refresh":
            self._analyse()
        elif button_id == "fix":
            self._fix_selected()
        elif button_id == "fix-sudo":
            self._fix_with_sudo()
        elif button_id == "analyse-sudo":
            self._analyse_with_sudo()
        elif button_id == "export-json":
            self._export_json()
        elif button_id == "export-html":
            self._export_rendered("log-health", "html")
        elif button_id == "export-txt":
            self._export_rendered("log-health-txt", "txt")

    def _exports_dir(self) -> Path:
        override = self._container.settings_store.get("exports_dir_override", "")
        return Path(override) if override else self._container.default_exports_dir

    def _ready_data(self) -> dict | None:
        if self._data is None:
            self.app.notify(_("Attendez la fin de l'analyse."), severity="warning")
        return self._data

    def _export_json(self) -> None:
        data = self._ready_data()
        if data is None:
            return
        content = json.dumps(data, indent=2, ensure_ascii=False)
        self._write_export(self._exports_dir() / f"log-health-export.{_export_timestamp()}.json", content)

    def _export_rendered(self, kind: str, extension: str) -> None:
        data = self._ready_data()
        if data is None:
            return
        theme_name = str(self.query_one("#theme-select", Select).value)
        run_html_export(
            self, self._container,
            lambda: self._container.export_payload(kind, data, theme_name),
            lambda content: self._write_export(
                self._exports_dir() / f"log-health-export.{_export_timestamp()}.{extension}", content),
            lambda reason: self.query_one("#health-status", Static).update(reason),
        )

    def _write_export(self, export_path: Path, content: str) -> None:
        self._container.filesystem.make_directory(export_path.parent)
        self._container.filesystem.write_text(export_path, content)
        self.app.notify(_("Export écrit : {export_path}").format(export_path=export_path))
