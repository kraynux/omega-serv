"""Processus d'administration web (tableau de bord web, lot 2, OMEGA-SERV_PLAN-DETAILLE_TABLEAU_DE_BORD_WEB.md §2).

- `omega-serv admin-web run` : le processus lui-meme, lance par `serve` quand l'option `admin_web` est active
  (utilisable seul pour le diagnostic). Ses pages suivent la langue reglee dans le TUI de l'instance (Q8) ; ses
  messages de journal (stderr, error.log) restent en francais, comme `serve` (D18b).
- `build_admin_web_supervisor` : le superviseur commun (child_supervisor.py), comme RIPOSTE, dans les trois modes
  (Python simple, boost, natif). Un arret de l'administration n'arrete jamais le site.

Un probleme de configuration (certificat illisible, port deja pris) n'est jamais une relance en boucle : la raison
est ecrite une fois dans error.log et le processus attend un rechargement (`systemctl reload`) pour reessayer.
Activer ou desactiver l'option demande un redemarrage complet (comme RIPOSTE)."""
from __future__ import annotations

import argparse
import asyncio
import contextlib
import getpass
import json
import os
import signal
import socket
import ssl
import sys
import threading
import time
from collections.abc import Callable
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from omega_serv.application.active_defense.auto_export import auto_export_closed_incidents
from omega_serv.application.active_defense.queries import list_incidents
from omega_serv.application.admin_web.actions import ActionOutcome, AdminActions, ArchiveLine
from omega_serv.application.admin_web.alert_monitor import AlertMonitor
from omega_serv.application.admin_web.auth import AdminAuth
from omega_serv.application.admin_web.certificate_watch import CertificateWatch
from omega_serv.application.admin_web.checks import admin_web_certificate_paths, admin_web_settings
from omega_serv.application.admin_web.dashboard import DashboardData, LogEntry, log_id_of
from omega_serv.application.admin_web.dashboard_view import SecurityFacts
from omega_serv.application.admin_web.fleet import FleetService
from omega_serv.application.admin_web.history import HistoryRecorder
from omega_serv.application.admin_web.manage_accounts import (
    AccountResult,
    add_account,
    confirm_totp,
    disable_totp,
    new_totp_secret,
    regenerate_backup_codes,
    remaining_backup_codes,
    remove_account,
    set_password,
    set_role,
)
from omega_serv.application.admin_web.master_link import MasterAccess, MasterLinkManager
from omega_serv.application.admin_web.session_publisher import SessionPublisher
from omega_serv.application.admin_web.stats_aggregator import StatsAggregator
from omega_serv.application.admin_web.web_app import AdminWebApp
from omega_serv.application.config.load_config import load_config
from omega_serv.application.logs.library import list_library
from omega_serv.application.riposte.console import database_path, riposte_enabled
from omega_serv.application.riposte.get_status import get_riposte_status
from omega_serv.application.security.manual_intervention import (
    ban_rows_for_display,
    collect_ban_rows,
    magnet_list_path,
)
from omega_serv.application.server.start_server import (
    ActiveDefenseCollaborators,
    build_active_defense_collaborators,
    build_blocklist_port,
)
from omega_serv.application.services.build_service_manager import build_service_manager
from omega_serv.application.services.pid_file import read_pid_file
from omega_serv.application.status.instance_status import AdminRunner, InstanceStatusCollector
from omega_serv.application.tls.certificate_inventory import (
    CertificateLine,
    certificate_sources,
    inspect_all,
)
from omega_serv.bootstrap.container import DependencyContainer
from omega_serv.core.i18n import _
from omega_serv.domain.admin_web import qr, totp
from omega_serv.domain.admin_web.accounts import AdminAccount, accounts_missing_totp
from omega_serv.domain.admin_web.alerts import thresholds_from_settings
from omega_serv.domain.admin_web.master import display_pairing_code, format_fingerprint
from omega_serv.domain.admin_web.run_state import AdminRunState
from omega_serv.domain.admin_web.settings import AdminWebSettings
from omega_serv.domain.config.entities import OmegaServConfig
from omega_serv.domain.security.active_defense.entities import IncidentFilters
from omega_serv.domain.security.waf.config import parse_waf_config
from omega_serv.infrastructure.admin_web import log_reader
from omega_serv.infrastructure.admin_web.accounts_repository import (
    ACCOUNTS_RELATIVE_PATH,
    AdminAccountsFileError,
    JsonAdminAccountsRepository,
)
from omega_serv.infrastructure.admin_web.alert_store import AlertStore
from omega_serv.infrastructure.admin_web.certificate import certificate_fingerprint
from omega_serv.infrastructure.admin_web.history_probe import HistoryProbe
from omega_serv.infrastructure.admin_web.history_store import HistoryStore
from omega_serv.infrastructure.admin_web.master_store import FleetStore, MasterStore
from omega_serv.infrastructure.admin_web.remote_client import RemoteInstanceClient
from omega_serv.infrastructure.admin_web.run_state_store import AdminRunStateStore
from omega_serv.infrastructure.admin_web.server import AdminWebServer
from omega_serv.infrastructure.admin_web.session_files import SessionFiles
from omega_serv.infrastructure.admin_web.stats_store import StatsStore
from omega_serv.infrastructure.admin_web.traffic_reader import TrafficTotals
from omega_serv.infrastructure.admin_web.used_backup_codes import (
    USED_BACKUP_CODES_RELATIVE_PATH,
    UsedBackupCodes,
)
from omega_serv.infrastructure.exporters.ioc_exporters import build_ioc_exporters
from omega_serv.infrastructure.exporters.markdown_incident_report_exporter import (
    MarkdownIncidentReportExporter,
)
from omega_serv.infrastructure.persistence.sqlite_riposte_connection import open_riposte_connection
from omega_serv.infrastructure.persistence.sqlite_riposte_store import SqliteRiposteStore
from omega_serv.infrastructure.proxy_admin.http_admin_client import call_admin_endpoint
from omega_serv.infrastructure.tls.ssl_context_builder import build_ssl_context
from omega_serv.interfaces.cli.admin_web_entry import LABEL
from omega_serv.interfaces.cli.riposte_text import format_status
from omega_serv.interfaces.cli.serve_native import log_error_line
from omega_serv.ports.blocklist_port import BlocklistPort
from omega_serv.ports.certificate_tool_port import CertificateToolPort
from omega_serv.ports.clock_port import ClockPort
from omega_serv.ports.filesystem_port import FilesystemPort
from omega_serv.ports.incident_repository_port import IncidentRepositoryPort
from omega_serv.ports.riposte_store_port import RiposteStorePort
from omega_serv.ports.service_manager_port import ServiceManagerPort

AUDIT_LOG_RELATIVE_PATH = Path("var") / "log" / "admin-audit.log"
EXIT_MASTER_EXISTS = 3
"""`admin-web master accept` sans --replace alors qu'un autre maitre est accepte (lu par « Relier au maitre »)."""


def audit_writer(container: DependencyContainer) -> Callable[[str], None]:
    """Une ligne horodatee dans var/log/admin-audit.log : processus d'administration, TUI et CLI."""
    return container.admin_audit


def instance_display_name(container: DependencyContainer) -> str:
    root = container.filesystem.resolve_real_path(container.project_root)
    entry = next((e for e in container.instance_registry.load() if e.path == root), None)
    return entry.name if entry is not None else root.name


def admin_fingerprint(config: OmegaServConfig, project_root: Path) -> str:
    """Empreinte du certificat presente par l'administration web ; vide sans TLS. Leve OSError ou ValueError."""
    settings = admin_web_settings(config)
    paths = admin_web_certificate_paths(config, settings) if settings is not None else None
    if paths is None:
        return ""
    path = Path(paths[0])
    return certificate_fingerprint(path if path.is_absolute() else project_root / path)




def _ssl_context(config: OmegaServConfig, project_root: Path) -> ssl.SSLContext | None:
    settings = admin_web_settings(config)
    assert settings is not None
    paths = admin_web_certificate_paths(config, settings)
    if paths is None:
        return None
    certificate, key = paths
    tls = replace(config.tls, enabled=True, mode="direct", certificate_path=certificate, private_key_path=key)
    if settings.tls == "own":
        tls = replace(tls, private_key_passphrase_env="")
    return build_ssl_context(tls, project_root)


def _openssl_certificate_tool() -> CertificateToolPort:
    from omega_serv.infrastructure.process.subprocess_runner import SubprocessRunner
    from omega_serv.infrastructure.tls.openssl_certificate_tool import OpensslCertificateTool

    return OpensslCertificateTool(SubprocessRunner())


class _StatusSources:
    """Le conteneur, plus le canal HTTP local vers `/.omega-serv-admin/` du serveur (mesures des backends) : le
    conteneur de la CLI ne le fournit qu'au TUI, le processus d'administration en a besoin aussi."""

    def __init__(self, container: DependencyContainer) -> None:
        self._container = container
        self._active_defense: dict[int, ActiveDefenseCollaborators | None] = {}

    def __getattr__(self, name: str) -> Any:
        return getattr(self._container, name)

    @property
    def admin_request_runner(self) -> AdminRunner:
        return self._container.admin_request_runner or call_admin_endpoint

    @property
    def blocklist_port_factory(self) -> Callable[[OmegaServConfig, FilesystemPort, Path, ClockPort], BlocklistPort]:
        return self._container.blocklist_port_factory or (
            lambda config, filesystem, root, clock: build_blocklist_port(config, root, filesystem, clock))

    @property
    def service_manager_factory(self) -> Callable[[], ServiceManagerPort | None]:
        """Cadre SERVICE SYSTÈME : sans lui, la page affichait « Aucun gestionnaire de service reconnu »."""
        return self._container.service_manager_factory or build_service_manager

    def active_defense(self, config: OmegaServConfig) -> ActiveDefenseCollaborators | None:
        """Ouverte une seule fois PAR FIL pour la duree du tableau de bord (une connexion SQLite a chaque releve,
        toutes les 2 s, s'accumulerait) ; reconstruite au rechargement, avec le tableau de bord. Par fil
        (correctif 2026-11-18) : les releves passent par asyncio.to_thread, donc par n'importe quel fil du pool, et
        SQLite refuse une connexion ouverte dans un autre fil (« SQLite objects created in a thread can only be used
        in that same thread ») : la vue Securite affichait cette erreur des qu'Active Defense etait actif. Le pool
        garde peu de fils : quelques connexions au plus."""
        key = threading.get_ident()
        if key not in self._active_defense:
            self._active_defense[key] = build_active_defense_collaborators(config, self._container.project_root)
        return self._active_defense[key]


ARCHIVES_RELATIVE_DIR = Path("var") / "backups" / "logs"


class _ActionSources:
    """Ce dont les actions du mode Administration ont besoin (application/admin_web/actions.py), lot 5."""

    def __init__(self, container: DependencyContainer, config_path: Path, status: _StatusSources,
                 supervisor_pid: int | None) -> None:
        self._container = container
        self._config_path = config_path
        self._status = status
        self._supervisor_pid = supervisor_pid

    def config(self) -> OmegaServConfig | None:
        result = load_config(self._container.configuration, self._config_path)
        return result.config if result.success else None

    @property
    def clock(self) -> ClockPort:
        return self._container.clock

    @property
    def project_root(self) -> Path:
        return self._container.project_root

    def blocklist(self, config: OmegaServConfig) -> BlocklistPort | None:
        factory = self._status.blocklist_port_factory
        container = self._container
        port: BlocklistPort = factory(config, container.filesystem, container.project_root,
                                      container.clock)
        return port

    def incident_repository(self, config: OmegaServConfig) -> IncidentRepositoryPort | None:
        collaborators = self._status.active_defense(config)
        return collaborators.incident_repository if collaborators is not None else None

    def export_closed_incident(self, config: OmegaServConfig, incident_id: str) -> None:
        collaborators = self._status.active_defense(config)
        if collaborators is None or not collaborators.config.ioc.auto_export_on_close:
            return
        container = self._container
        export_dir = container.project_root / collaborators.config.storage.export_dir
        exporters = build_ioc_exporters(container.filesystem, export_dir, collaborators.config.ioc)
        auto_export_closed_incidents(
            [incident_id], collaborators.incident_repository, collaborators.config,
            lambda incident, fmt: exporters[fmt].export(incident) if fmt in exporters else None,
            lambda incident: MarkdownIncidentReportExporter(container.filesystem, export_dir).render(incident),
            lambda message: self._log_error(config, f"export automatique impossible {message}"))

    def _log_error(self, config: OmegaServConfig, message: str) -> None:
        print(f"{LABEL} : {message}", file=sys.stderr)
        log_error_line(self._container, config, f"administration web : {message}")

    def riposte_store(self, config: OmegaServConfig, write: bool) -> RiposteStorePort:
        return SqliteRiposteStore(open_riposte_connection(database_path(config, self._container.project_root),
                                                          read_only=not write, create=False))

    async def admin_call(self, port: int, method: str, path: str) -> tuple[int, dict | None] | None:
        runner = self._status.admin_request_runner
        return await runner(port, method, path)

    def file_size(self, path: Path) -> int | None:
        try:
            return path.stat().st_size
        except OSError:
            return None

    def _archive_dir(self) -> Path:
        return self._container.project_root / ARCHIVES_RELATIVE_DIR

    def rotate_now(self, log_path: Path, keep: int) -> ActionOutcome:
        try:
            result = self._container.rotate_log_if_needed(log_path, 0, keep, self._archive_dir())
        except OSError as error:
            return ActionOutcome(False, _("Archivage impossible : {error}").format(error=error))
        return ActionOutcome(result.success, result.message)

    def archives(self) -> list[ArchiveLine]:
        store = self._container.build_archive_store(self._archive_dir())
        lines = []
        for path in store.list_archives():
            with contextlib.suppress(OSError):
                stat = path.stat()
                stamp = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).astimezone()
                lines.append(ArchiveLine(path.name, stat.st_size, stamp.strftime("%Y-%m-%d %H:%M")))
        return lines

    def delete_archive(self, name: str) -> bool:
        try:
            store = self._container.build_archive_store(self._archive_dir())
            return bool(store.delete_archive(store.base_dir / Path(name).name))
        except OSError:
            return False

    def reload_problem(self) -> str:
        if self._supervisor_pid is None:
            return _("Rechargement indisponible : l'administration web n'a pas été lancée par le serveur.")
        if os.getppid() != self._supervisor_pid:
            return _("Rechargement indisponible : le serveur qui a lancé l'administration web ne tourne plus.")
        return ""

    def request_reload(self) -> None:
        """Le signal part juste apres la reponse : la page a le temps de partir avant le rechargement."""
        pid = self._supervisor_pid
        if pid is not None:
            asyncio.get_running_loop().call_later(0.3, os.kill, pid, signal.SIGHUP)


class _AdminWebProcess:
    def __init__(self, container: DependencyContainer, config_path: Path, supervisor_pid: int | None = None) -> None:
        self._container = container
        self._config_path = config_path
        self._supervisor_pid = supervisor_pid
        self._auth: AdminAuth | None = None
        self._stop = asyncio.Event()
        self._reload = asyncio.Event()
        self._server: AdminWebServer | None = None
        self._dashboard: DashboardData | None = None
        self._master_access: MasterAccess | None = None
        self._fleet: FleetService | None = None
        self._fingerprint = ""
        self._history: HistoryRecorder | None = None
        """Historique (lot 7) : garde ses anneaux d'un rechargement a l'autre ; None si `history` est a false."""
        self._history_stop: asyncio.Event | None = None
        self._history_task: asyncio.Future[None] | None = None
        self._access_log = container.project_root / "var" / "log" / "access.log"
        self._certificates = CertificateWatch(self._check_certificates)
        self._alert_thresholds = thresholds_from_settings(None)
        self._alerts = AlertMonitor(AlertStore(container.filesystem, container.project_root),
                                    lambda: self._alert_thresholds)
        """Alertes locales (etude modules, module 1) : points de l'Historique et sources toutes les minutes."""
        self._actions: AdminActions | None = None
        self._stats = StatsAggregator(StatsStore(container.filesystem, container.project_root))
        """Statistiques de trafic (etude modules, module 2) : lues par la sonde de l'Historique."""
        self._sessions = SessionPublisher(SessionFiles(container.filesystem, container.project_root),
                                          lambda: self._auth)
        """Sessions ouvertes pour la TUI (etude modules, module 5)."""
        """Echeances des certificats (etude modules, module 3) : 12 h et a chaque rechargement."""

    def _check_certificates(self) -> list[CertificateLine]:
        container = self._container
        result = load_config(container.configuration, self._config_path)
        if not result.success or result.config is None:
            return self._certificates.lines
        config = result.config
        settings = admin_web_settings(config)
        admin_certificate = Path(settings.certificate_path) if settings is not None and settings.tls == "own" else None
        sources = certificate_sources(config, container.project_root, container.filesystem, admin_certificate)
        # openssl fourni ici (correctif 2026-11-18) : le conteneur de la CLI ne le donne qu'au TUI, la vue
        # Certificats et les alertes d'echeance disaient toujours « echeance inconnue (openssl absent) ».
        return inspect_all(sources, container.project_root, container.filesystem,
                           container.certificate_tool_factory or _openssl_certificate_tool, datetime.now(timezone.utc))

    async def _alert_sources(self) -> tuple[list[tuple[str, str]] | None, list[str] | None,
                                            list[CertificateLine] | None]:
        """Backends et incidents de la page Administration, echeances des certificats ; None = source illisible."""
        backends: list[tuple[str, str]] | None = None
        incidents: list[str] | None = None
        if self._actions is not None:
            state = await self._actions.state()
            if not state.backends_problem:
                backends = [(f"{line.zone}/{line.name}", line.status) for line in state.backends]
            if not state.incidents_problem:
                incidents = [incident.incident_id for incident in state.incidents]
        certificates = self._certificates.lines if self._certificates.checked_at is not None else None
        return backends, incidents, certificates

    def _log(self, config: OmegaServConfig | None, message: str) -> None:
        print(f"{LABEL} : {message}", file=sys.stderr)
        if config is not None:
            log_error_line(self._container, config, f"administration web : {message}")

    async def _start(self) -> None:
        result = load_config(self._container.configuration, self._config_path)
        if not result.success or result.config is None:
            self._log(None, "configuration illisible - " + "; ".join(result.errors))
            self._write_state("config", "; ".join(result.errors))
            return
        config = result.config
        settings = admin_web_settings(config)
        if settings is None:
            self._log(config, "option inactive - rien a servir (redemarrage complet pour l'arreter tout a fait)")
            self._write_state("inactive")
            return
        try:
            context = _ssl_context(config, self._container.project_root)
        except (OSError, ssl.SSLError, ValueError) as error:
            self._log(config, f"certificat illisible ({error}) - arretee jusqu'au prochain rechargement")
            self._write_state("certificate", str(error), settings)
            return
        accounts = JsonAdminAccountsRepository(self._container.filesystem,
                                               self._container.project_root / ACCOUNTS_RELATIVE_PATH)
        try:
            known = accounts.load()
        except AdminAccountsFileError as error:
            self._log(config, f"fichier des comptes illisible ({error}) - arretee jusqu'au prochain rechargement")
            self._write_state("accounts_file", str(error), settings)
            return
        missing = accounts_missing_totp(known)
        if missing and not settings.local_only:
            # Choix b de l'auteur (2026-11-16) : hors de cette machine, un compte administration sans TOTP est interdit.
            self._log(config, "TOTP obligatoire hors de la boucle locale pour les comptes administration sans TOTP ("
                              + ", ".join(missing) + ") - arretee jusqu'au prochain rechargement")
            self._write_state("totp", ", ".join(missing), settings)
            return
        if not known:
            self._log(config, "aucun compte : creez-en un (TUI : Instances -> Configuration distante -> Comptes, "
                              "ou omega-serv admin-web account add)")
        self._dashboard = self._build_dashboard()
        if self._auth is None:
            self._auth = self._build_auth(config, settings, accounts)
        self._auth.local_only = settings.local_only  # un rechargement garde les sessions ouvertes (lot 5)
        actions = AdminActions(_ActionSources(self._container, self._config_path, _StatusSources(self._container),
                                              self._supervisor_pid))
        self._actions = actions
        self._alert_thresholds = thresholds_from_settings(settings.alerts)
        try:
            fingerprint = admin_fingerprint(config, self._container.project_root)
        except (OSError, ValueError) as error:
            self._log(config, f"empreinte du certificat illisible ({error}) - arretee jusqu'au prochain rechargement")
            self._write_state("fingerprint", str(error), settings)
            return
        container = self._container
        audit = audit_writer(container)
        name = self._instance_name()
        if self._master_access is None:
            self._master_access = MasterAccess(MasterStore(container.filesystem, container.project_root), time.time,
                                               audit, lambda: self._fingerprint, lambda: name)
        self._fingerprint = fingerprint
        if self._fleet is None:
            self._fleet = FleetService(FleetStore(container.filesystem, container.project_root),
                                       RemoteInstanceClient(), audit, f"{name}@{socket.gethostname()}")
        self._access_log = container.project_root / config.logs.access
        await self._set_history(bool(settings.history))
        app = AdminWebApp(settings, self._auth, name, self._dashboard, actions, self._master_access, self._fleet,
                          self._history, tui_theme=lambda: container.settings_store.get("theme"),
                          certificates=self._certificates, alerts=self._alerts,
                          stats=self._stats if self._history is not None else None)
        server = AdminWebServer(str(settings.bind), int(settings.port), context, app.handle)
        try:
            await server.start()
        except OSError as error:
            self._log(config, f"ecoute impossible sur {settings.bind}:{settings.port} ({error}) - arretee jusqu'au "
                              "prochain rechargement")
            self._write_state("listen", error.strerror or str(error), settings)
            return
        self._server = server
        self._log(config, f"ecoute sur {settings.url}")
        self._write_state("", "", settings)

    def _write_state(self, problem: str, detail: str = "", settings: AdminWebSettings | None = None) -> None:
        """Lot 8 : etat lu par l'ecran Configuration distante (en ecoute, ou la raison de l'arret)."""
        bind = str(settings.bind) if settings is not None else ""
        port = settings.port if settings is not None and isinstance(settings.port, int) else 0
        AdminRunStateStore(self._container.filesystem, self._container.project_root).save(
            AdminRunState(os.getpid(), not problem, bind, port, problem, detail))

    # ------------------------------------------------------------------ tableau de bord (lot 4)
    def _build_dashboard(self) -> DashboardData:
        container = self._container
        audit_path = container.project_root / AUDIT_LOG_RELATIVE_PATH

        def python_processes() -> int:
            result = load_config(container.configuration, self._config_path)
            return container.engine_status(result.config).workers if result.success and result.config else 1

        def audit_lines(count: int) -> list[str]:
            return container.file_access.read_tail_lines(audit_path, 256 * 1024)[-count:]

        sources = _StatusSources(container)
        return DashboardData(InstanceStatusCollector(sources),
                             lambda: security_facts(sources, self._config_path),
                             lambda: library_logs(container), log_reader.tail, log_reader.read_from, audit_lines,
                             python_processes)

    # ------------------------------------------------------------------ historique (lot 7)
    async def _set_history(self, enabled: bool) -> None:
        if enabled and self._history is None:
            container = self._container
            pid_path = container.project_root / "var" / "run" / "omega-serv.pid"

            def server_pids() -> list[int]:
                pid = read_pid_file(container.filesystem, pid_path)
                return [pid] if pid is not None else []

            traffic = TrafficTotals(container.project_root)
            self._history = HistoryRecorder(HistoryProbe(lambda: self._access_log, instance_root=container.project_root,
                                                         server_pids=server_pids, traffic=traffic.read,
                                                         stats=self._stats),
                                            HistoryStore(container.filesystem, container.project_root))
            self._history_stop = asyncio.Event()
            self._history.listener = self._alerts.on_point
            self._history_task = asyncio.ensure_future(self._history.run(self._history_stop))
        elif not enabled and self._history is not None:
            await self._stop_history()

    async def _stop_history(self) -> None:
        if self._history_stop is not None and self._history_task is not None:
            self._history_stop.set()
            await self._history_task  # ecrit le fichier une derniere fois
            await asyncio.to_thread(self._stats.save)
        self._history, self._history_stop, self._history_task = None, None, None

    def _instance_name(self) -> str:
        return instance_display_name(self._container)

    def _build_auth(self, config: OmegaServConfig, settings: AdminWebSettings,
                    accounts: JsonAdminAccountsRepository) -> AdminAuth:
        container = self._container
        used = UsedBackupCodes(container.filesystem, container.project_root / USED_BACKUP_CODES_RELATIVE_PATH)
        audit = audit_writer(container)

        def load_accounts() -> tuple[AdminAccount, ...]:
            try:
                return accounts.load()
            except AdminAccountsFileError:
                return ()  # fichier en cours d'ecriture ou abime : personne ne se connecte, rien ne casse

        return AdminAuth(load_accounts, time.time, audit, local_only=settings.local_only,
                         used_backup_codes=used.load, mark_backup_code_used=used.add)

    async def run(self) -> int:
        loop = asyncio.get_running_loop()
        loop.add_signal_handler(signal.SIGTERM, self._stop.set)
        loop.add_signal_handler(signal.SIGINT, self._stop.set)
        loop.add_signal_handler(signal.SIGHUP, self._reload.set)
        await self._start()
        dashboard_stop = asyncio.Event()
        dashboard_task = asyncio.ensure_future(self._dashboard_loop(dashboard_stop))
        monitor_stop = asyncio.Event()
        certificates_task = asyncio.ensure_future(self._certificates.run(monitor_stop))
        alerts_task = asyncio.ensure_future(self._alerts.run(monitor_stop, self._alert_sources))
        sessions_task = asyncio.ensure_future(self._sessions.run(monitor_stop))
        while not self._stop.is_set():
            reload_wait = asyncio.ensure_future(self._reload.wait())
            stop_wait = asyncio.ensure_future(self._stop.wait())
            await asyncio.wait({reload_wait, stop_wait}, return_when=asyncio.FIRST_COMPLETED)
            for pending in (reload_wait, stop_wait):
                pending.cancel()
            if self._stop.is_set():
                break
            self._reload.clear()
            self._certificates.refresh_soon()
            if self._server is not None:
                await self._server.close()
                self._server = None
            await self._start()
        dashboard_stop.set()
        await dashboard_task
        monitor_stop.set()
        await certificates_task
        await alerts_task
        await sessions_task
        await self._stop_history()
        if self._server is not None:
            await self._server.close()
        return 0

    async def _dashboard_loop(self, stop: asyncio.Event) -> None:
        """Recalcul du tableau de bord (toutes les 2 s, seulement quand une page est ouverte) ; suit le tableau de
        bord reconstruit a chaque rechargement."""
        while not stop.is_set():
            dashboard = self._dashboard
            if dashboard is not None:
                inner = asyncio.Event()
                waiter = asyncio.ensure_future(stop.wait())
                runner = asyncio.ensure_future(dashboard.run(inner))
                while not stop.is_set() and self._dashboard is dashboard:
                    await asyncio.wait({waiter}, timeout=1.0)
                inner.set()
                await runner
                waiter.cancel()
            else:
                try:
                    await asyncio.wait_for(stop.wait(), 1.0)
                except TimeoutError:
                    pass


def cmd_admin_web_run(args: argparse.Namespace, container: DependencyContainer) -> int:
    from omega_serv.infrastructure.process.memory_tuning import keep_large_blocks_out_of_heap

    keep_large_blocks_out_of_heap()  # comme `serve` : les scrypt (16 Mio) ne restent jamais dans le tas
    for stream in (sys.stdout, sys.stderr):  # sous systemd : messages dans journalctl au fil de l'eau
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(line_buffering=True)
    with contextlib.suppress(KeyboardInterrupt):
        return asyncio.run(_AdminWebProcess(container, args.config, getattr(args, "supervisor_pid", None)).run())
    return 0


# ---------------------------------------------------------------------- donnees du tableau de bord (lot 4)
def security_facts(container: _StatusSources, config_path: Path) -> SecurityFacts:
    """Bans, RIPOSTE et incidents lus pour la page Securite ; chaque source absente ou illisible donne un texte a
    afficher, jamais une exception."""
    result = load_config(container.configuration, config_path)
    if not result.success or result.config is None:
        problem = _("Configuration illisible.")
        return SecurityFacts(bans_problem=problem, riposte_problem=problem, incidents_problem=problem)
    config = result.config
    now = container.clock.now()
    bans: list[dict[str, str]] = []
    bans_problem = ""
    factory = container.blocklist_port_factory
    if factory is None:
        bans_problem = _("Blocklist indisponible dans cet environnement.")
    else:
        try:
            rows, warning = collect_ban_rows(factory(config, container.filesystem, container.project_root,
                                                     container.clock), container.filesystem,
                                             magnet_list_path(config, container.project_root), now)
            bans, bans_problem = ban_rows_for_display(rows, short=True), warning
        except OSError as error:
            bans_problem = _("Blocklist illisible : {error}").format(error=error)
    riposte_lines: list[str] | None = None
    riposte_problem = ""
    if riposte_enabled(config):
        try:
            connection = open_riposte_connection(database_path(config, container.project_root), read_only=True)
        except FileNotFoundError:
            riposte_problem = _("RIPOSTE n'a encore jamais été lancé sur cette instance.")
        except OSError as error:
            riposte_problem = _("Base RIPOSTE illisible : {error}").format(error=error)
        else:
            try:
                store = SqliteRiposteStore(connection)
                riposte_lines = format_status(get_riposte_status(store, now), store.count_in_progress(bans_only=False),
                                              store.count_in_progress(bans_only=True))
            finally:
                connection.close()
    incidents: list[tuple[str, str, str, datetime, datetime | None]] = []
    incidents_problem = ""
    if not config.option_enabled("active_defense"):
        incidents_problem = _("Active Defense inactif.")
    else:
        try:
            collaborators = container.active_defense(config)
        except OSError as error:
            collaborators, incidents_problem = None, _("Base Active Defense illisible : {error}").format(error=error)
        if collaborators is not None:
            incidents = [(i.incident_id, i.subject_id, i.status, i.opened_at, i.closed_at)
                         for i in list_incidents(collaborators.incident_repository, IncidentFilters())]
    return SecurityFacts(bans, bans_problem, riposte_lines, riposte_problem, incidents, incidents_problem)


def library_logs(container: DependencyContainer) -> list[LogEntry]:
    """Journaux lisibles depuis le web : d'abord ceux de l'instance (access.log, error.log, alertes du WAF s'il est
    actif), presents d'office, puis les fichiers de la bibliotheque (Gestion des logs), sans doublon. Jamais journald ni
    une source distante, jamais un chemin venu du navigateur."""
    entries: list[LogEntry] = []
    seen: set[str] = set()

    def add(path: Path, label: str) -> None:
        key = str(path)
        if key not in seen:
            seen.add(key)
            entries.append(LogEntry(log_id_of(key), label, path))

    result = load_config(container.configuration, container.config_file)
    if result.success and result.config is not None:
        config = result.config
        for relative in (config.logs.access, config.logs.error):
            path = container.project_root / relative
            add(path, _("{name} (cette instance)").format(name=path.name))
        waf = config.options.get("waf")
        if waf is not None and waf.enabled:
            path = container.project_root / parse_waf_config(waf.settings).logging.path
            add(path, _("{name} (cette instance)").format(name=path.name))
    for log in list_library(container.build_log_library_repository()):
        if log.access == "file":
            add(Path(log.path), log.path)
    return entries


# ---------------------------------------------------------------------- comptes (lot 3)
def _print_result(result: AccountResult) -> int:
    print(result.message, file=sys.stdout if result.success else sys.stderr)
    return 0 if result.success else 1


def _ask_password() -> str | None:
    first = getpass.getpass(_("Mot de passe : "))
    if first != getpass.getpass(_("Mot de passe (à nouveau) : ")):
        print(_("Les deux saisies diffèrent : rien n'a été changé."), file=sys.stderr)
        return None
    return first


def cmd_admin_account_list(args: argparse.Namespace, container: DependencyContainer) -> int:
    try:
        accounts = container.admin_accounts.load()
    except AdminAccountsFileError as error:
        print(str(error), file=sys.stderr)
        return 1
    if not accounts:
        print(_("Aucun compte d'administration web."))
        return 0
    used = container.admin_used_backup_codes()
    for account in accounts:
        line = _("{name}  rôle : {role}  TOTP : {totp}").format(
            name=account.username, role=account.role, totp=_("activé") if account.totp_enabled else _("non"))
        if account.totp_enabled:
            line += "  " + _("codes de secours : {left} sur {total}").format(
                left=remaining_backup_codes(account, used), total=len(account.backup_code_hashes))
        print(line)
    return 0


def cmd_admin_account_add(args: argparse.Namespace, container: DependencyContainer) -> int:
    password = _ask_password()
    if password is None:
        return 1
    return _print_result(add_account(container.admin_accounts, args.username, password, args.role))


def cmd_admin_account_remove(args: argparse.Namespace, container: DependencyContainer) -> int:
    return _print_result(remove_account(container.admin_accounts, args.username))


def cmd_admin_account_password(args: argparse.Namespace, container: DependencyContainer) -> int:
    password = _ask_password()
    if password is None:
        return 1
    return _print_result(set_password(container.admin_accounts, args.username, password))


def cmd_admin_account_role(args: argparse.Namespace, container: DependencyContainer) -> int:
    return _print_result(set_role(container.admin_accounts, args.username, args.role))


def totp_enrolment_text(username: str, secret: str, issuer: str) -> tuple[list[str], str, str]:
    """(lignes du QR code, secret par groupes de 4, lien otpauth) : les deux methodes, toujours (decision de
    l'auteur du 2026-11-16 : la page peut etre lue sur le telephone meme qui porte l'application)."""
    uri = totp.otpauth_uri(secret, username, issuer)
    return qr.to_text(qr.encode(uri)), totp.grouped(secret), uri


def cmd_admin_account_totp_enable(args: argparse.Namespace, container: DependencyContainer) -> int:
    secret = new_totp_secret()
    lines, grouped, uri = totp_enrolment_text(args.username, secret, f"omega-serv {container.project_root.name}")
    print(_("1. Scannez ce QR code avec l'application d'authentification (Aegis, FreeOTP, 2FAS...) :"))
    for line in lines:
        print(f"\x1b[97;40m{line}\x1b[0m")
    print(_("   Sans scan (sur ce même téléphone) : saisissez ce secret dans l'application"))
    print(f"   {grouped}")
    print(_("   ou ouvrez ce lien sur le téléphone :"))
    print(f"   {uri}")
    code = input(_("2. Code à 6 chiffres affiché par l'application : "))
    result = confirm_totp(container.admin_accounts, args.username, secret, code)
    status = _print_result(result)
    if result.backup_codes:
        print(_("Codes de secours (un seul usage chacun ; notez-les maintenant, ils ne seront plus affichés) :"))
        for backup in result.backup_codes:
            print(f"   {backup}")
    return status


def cmd_admin_account_backup_codes(args: argparse.Namespace, container: DependencyContainer) -> int:
    result = regenerate_backup_codes(container.admin_accounts, args.username)
    status = _print_result(result)
    if result.backup_codes:
        print(_("Codes de secours (un seul usage chacun ; notez-les maintenant, ils ne seront plus affichés) :"))
        for backup in result.backup_codes:
            print(f"   {backup}")
    return status


def cmd_admin_account_totp_disable(args: argparse.Namespace, container: DependencyContainer) -> int:
    return _print_result(disable_totp(container.admin_accounts, args.username))




# ---------------------------------------------------------------------- instance maitre (lot 6, plan §7)
def _master_manager(container: DependencyContainer) -> MasterLinkManager:
    return container.admin_master_manager()


def _rights_text(rights: str) -> str:
    return {"lecture": _("lecture"), "administration": _("administration")}.get(rights, rights)


def _local_time(iso: str) -> str:
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone().strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return iso or "-"


def cmd_admin_master_show(args: argparse.Namespace, container: DependencyContainer) -> int:
    manager = _master_manager(container)
    master = manager.master()
    if master is None:
        print(_("Aucun maître accepté : cette instance n'est suivie par aucune autre."))
    else:
        print(_("Maître accepté : {name} (identifiant {master_id})").format(name=master.master_name,
                                                                          master_id=master.master_id))
        print(_("Droits : {rights}").format(rights=_rights_text(master.rights)))
        print(_("Depuis : {since}").format(since=_local_time(master.since)))
        print(_("Dernier appel : {last}").format(last=_local_time(master.last_call) if master.last_call else "-"))
    window = manager.pairing()
    if window is not None:
        left = max(0, int(window.expires_at - time.time()))
        print(_("Fenêtre d'appairage ouverte : code {code}, droits {rights}, encore {minutes} min {seconds} s.").format(
            code=display_pairing_code(window.code), rights=_rights_text(window.rights), minutes=left // 60,
            seconds=left % 60))
    return 0


def _fingerprint_or_error(container: DependencyContainer, config_path: Path) -> str | None:
    result = load_config(container.configuration, config_path)
    if not result.success or result.config is None:
        print(_("Configuration illisible : {errors}").format(errors="; ".join(result.errors)), file=sys.stderr)
        return None
    if admin_web_settings(result.config) is None:
        print(_("L'administration web n'est pas active sur cette instance (option admin_web) : un maître ne "
                "pourrait pas l'appeler."), file=sys.stderr)
        return None
    try:
        return admin_fingerprint(result.config, container.project_root)
    except (OSError, ValueError) as error:
        print(_("Certificat de l'administration web illisible : {error}").format(error=error), file=sys.stderr)
        return None


def cmd_admin_master_accept(args: argparse.Namespace, container: DependencyContainer) -> int:
    """« Relier au maitre » (TUI, et plus tard omega-connect) : la sortie JSON est lue par l'outil, jamais recopiee."""
    fingerprint = _fingerprint_or_error(container, args.config)
    if fingerprint is None:
        return 1
    outcome = _master_manager(container).accept(args.master_id, args.master_name or "", args.rights,
                                                replace_existing=args.replace, source="commande")
    if not outcome.ok:
        messages = {
            "exists": _("Un autre maître est déjà accepté ({name}) : ajoutez --replace pour le remplacer (il sera "
                        "révoqué aussitôt).").format(name=outcome.replaced),
            "master_id": _("Identifiant de maître invalide (32 caractères hexadécimaux)."),
            "rights": _("Droits inconnus."),
            "write": _("Écriture impossible dans var/lib/admin (droits du dossier)."),
        }
        print(messages.get(outcome.error, outcome.error), file=sys.stderr)
        return EXIT_MASTER_EXISTS if outcome.error == "exists" else 1
    config = load_config(container.configuration, args.config).config
    settings = admin_web_settings(config) if config is not None else None
    print(json.dumps({"jeton": outcome.token, "empreinte": fingerprint, "port": settings.port if settings else 0,
                      "nom": instance_display_name(container), "droits": args.rights}, ensure_ascii=False))
    return 0


def cmd_admin_master_pairing_code(args: argparse.Namespace, container: DependencyContainer) -> int:
    fingerprint = _fingerprint_or_error(container, args.config)
    if fingerprint is None:
        return 1
    outcome = _master_manager(container).open_pairing(args.rights, replace_existing=args.replace)
    if not outcome.ok:
        if outcome.error == "exists":
            print(_("Un maître est déjà accepté : ajoutez --replace pour le remplacer à la fin de l'appairage."),
                  file=sys.stderr)
        else:
            print(_("Écriture impossible dans var/lib/admin (droits du dossier)."), file=sys.stderr)
        return 1
    print(_("Code d'appairage : {code}").format(code=display_pairing_code(outcome.code)))
    print(_("Valable 10 minutes, une seule fois ; 3 essais faux ferment la fenêtre."))
    print(_("Sur le maître : page Instances -> « Ajouter à la main » -> adresse, port et ce code."))
    if fingerprint:
        print(_("Empreinte du certificat de cette instance : {fingerprint}").format(
            fingerprint=format_fingerprint(fingerprint)))
    return 0


def cmd_admin_master_revoke(args: argparse.Namespace, container: DependencyContainer) -> int:
    manager = _master_manager(container)
    manager.close_pairing()
    name = manager.revoke()
    print(_("Maître révoqué : {name}. Ses appels sont refusés dès maintenant.").format(name=name) if name
          else _("Aucun maître accepté."))
    return 0


def _fleet_service(container: DependencyContainer) -> FleetService:
    return FleetService(FleetStore(container.filesystem, container.project_root), RemoteInstanceClient(),
                        audit_writer(container), f"{instance_display_name(container)}@{socket.gethostname()}")


def cmd_admin_instances_identity(args: argparse.Namespace, container: DependencyContainer) -> int:
    identity = _fleet_service(container).identity()
    print(json.dumps({"maitre_id": identity.master_id, "nom": identity.name}, ensure_ascii=False))
    return 0


def cmd_admin_instances_list(args: argparse.Namespace, container: DependencyContainer) -> int:
    fleet = _fleet_service(container).fleet()
    if not fleet.instances:
        print(_("Aucune instance suivie."))
        return 0
    for item in fleet.instances:
        kind = _("sonde HTTP") if item.kind == "sonde" else "omega-serv"
        print(f"{item.instance_id}  {item.name}  {kind}  {item.target}")
    return 0


def cmd_admin_instances_add(args: argparse.Namespace, container: DependencyContainer) -> int:
    token = args.token if args.token is not None else sys.stdin.readline().strip()
    outcome = _fleet_service(container).add_direct(args.name or "", args.address, args.port, token,
                                                   args.fingerprint.replace(":", "").lower())
    print(outcome.message, file=sys.stdout if outcome.ok else sys.stderr)
    return 0 if outcome.ok else 1


def cmd_admin_instances_pair(args: argparse.Namespace, container: DependencyContainer) -> int:
    outcome = asyncio.run(_fleet_service(container).pair(args.name or "", args.address, args.port, args.code))
    print(outcome.message, file=sys.stdout if outcome.ok else sys.stderr)
    return 0 if outcome.ok else 1


def cmd_admin_instances_add_probe(args: argparse.Namespace, container: DependencyContainer) -> int:
    outcome = _fleet_service(container).add_probe(args.name or "", args.url)
    print(outcome.message, file=sys.stdout if outcome.ok else sys.stderr)
    return 0 if outcome.ok else 1


def cmd_admin_instances_remove(args: argparse.Namespace, container: DependencyContainer) -> int:
    outcome = _fleet_service(container).remove(args.instance_id)
    print(outcome.message, file=sys.stdout if outcome.ok else sys.stderr)
    return 0 if outcome.ok else 1
