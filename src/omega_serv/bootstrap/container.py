"""Racine de composition des dependances (charte §2.3).

Seul point du projet ou les adaptateurs concrets d'infrastructure/ sont
instancies directement - tout le reste du code (application/,
interfaces/) ne recoit que des ports. S'enrichira au fil des phases
(port de service systemd en Phase 9, port WAF en Phase 5, etc.) sans
que les couches superieures aient a changer."""
from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from omega_serv.bootstrap.paths import INSTANCE_REGISTRY_PATH, PROJECT_ROOT

if TYPE_CHECKING:
    from omega_lib.theme.policies import Palette

    from omega_serv.ports.admin_accounts_port import AdminAccountsPort
    from omega_serv.ports.capability_scanner_port import CapabilityScannerPort
    from omega_serv.ports.clock_port import ClockPort
    from omega_serv.ports.configuration_port import ConfigurationPort
    from omega_serv.ports.declaration_port import DeclarationSenderPort, DeclarationStorePort
    from omega_serv.ports.file_access_port import FileAccessPort
    from omega_serv.ports.filesystem_port import FilesystemPort
    from omega_serv.ports.instance_registry_port import InstanceRegistryPort
    from omega_serv.ports.keyword_reference_port import KeywordReferencePort
    from omega_serv.ports.language_catalog_port import LanguageCatalogPort
    from omega_serv.ports.live_tail_port import LiveTailPort
    from omega_serv.ports.log_favorite_repository_port import LogFavoriteRepositoryPort
    from omega_serv.ports.log_library_repository_port import LogLibraryRepositoryPort
    from omega_serv.ports.logger_port import LoggerPort
    from omega_serv.ports.profile_repository_port import ProfileRepositoryPort
    from omega_serv.ports.proxy_cache_store_port import ProxyCacheStorePort
    from omega_serv.ports.release_source_port import ReleaseSourcePort
    from omega_serv.ports.remote_log_source_repository_port import RemoteLogSourceRepositoryPort
    from omega_serv.ports.service_manager_port import ServiceManagerPort
    from omega_serv.ports.settings_store import SettingsStore
    from omega_serv.ports.terminal_detector import TerminalDetector


if TYPE_CHECKING:
    from omega_serv.application.admin_web.firewall_setup import FirewallRecord
    from omega_serv.application.admin_web.master_link import MasterLinkManager
    from omega_serv.application.admin_web.readiness import ReadinessItem
    from omega_serv.application.logs.rotate_log import RotateLogResult
    from omega_serv.application.persistence.backup_transfer import ArchiveIdentity, TransferResult
    from omega_serv.application.persistence.create_backup import BackupResult
    from omega_serv.application.persistence.restore_backup import RestoreResult
    from omega_serv.application.security.check_magnet_compatibility import MagnetCompatibilityCheck
    from omega_serv.application.security.simulate_waf_request import WafSimulationReport
    from omega_serv.application.server.engine_status import EngineStatus
    from omega_serv.application.server.simulate_request import SimulationReport
    from omega_serv.application.server.start_server import ActiveDefenseCollaborators
    from omega_serv.core.capability import Capability
    from omega_serv.domain.admin_web.accounts import AdminAccount
    from omega_serv.domain.admin_web.run_state import AdminRunState
    from omega_serv.domain.config.entities import OmegaServConfig
    from omega_serv.domain.instances.entities import InstanceEntry
    from omega_serv.domain.logging.stats import LogStatsSummary
    from omega_serv.domain.persistence.backup import BackupRequest
    from omega_serv.domain.persistence.snapshots import SnapshotMetadata
    from omega_serv.domain.security.active_defense.config import IoCConfig
    from omega_serv.domain.security.active_defense.entities import ExportResult, Incident
    from omega_serv.domain.security.audit.entities import AuditResult
    from omega_serv.domain.security.riposte.events import ObservedEvent
    from omega_serv.domain.security.waf.config import MagnetConfig
    from omega_serv.domain.services.shared_access import SharedAccessReport
    from omega_serv.infrastructure.logging.rotation_automation_store import RotationAutomationStore
    from omega_serv.infrastructure.persistence.backup_metadata_store import BackupMetadataStore
    from omega_serv.infrastructure.storage.files.archive_store import ArchiveStore
    from omega_serv.ports.admin_alerts_port import AlertStorePort
    from omega_serv.ports.admin_sessions_port import SessionFilesPort
    from omega_serv.ports.admin_web_setup_port import AdminWebSetupPort
    from omega_serv.ports.auth_zones_repository_port import AuthZonesRepositoryPort
    from omega_serv.ports.blocklist_port import BlocklistPort
    from omega_serv.ports.certificate_tool_port import CertificateToolPort
    from omega_serv.ports.clipboard_port import ClipboardPort
    from omega_serv.ports.instance_command_port import InstanceCommandPort
    from omega_serv.ports.process_runner_port import ProcessResult, ProcessRunnerPort
    from omega_serv.ports.riposte_store_port import RiposteStorePort
    from omega_serv.ports.users_repository_port import UsersRepositoryPort


class DependencyContainer:
    """Racine de composition (charte §2.3) : seul point du projet ou les
    adaptateurs concrets d'infrastructure/ non sensibles (filesystem,
    config, logging...) sont instancies directement dans `__init__`.

    Les usines `*_factory`/`*_runner` ci-dessous couvrent le cas
    different des adaptateurs qui touchent `subprocess`/`ssl`, ou des cas
    d'usage application/ qui importent eux-memes infrastructure/ pour des
    raisons internes (ex. application/server/simulate_request.py importe
    infrastructure/filesystem/safe_path_resolver.py) : bootstrap/ ET
    interfaces.tui/ sont TOUS DEUX exclus de `subprocess`/`ssl` par les
    contrats import-linter, et interfaces.tui/ est en plus exclue de
    infrastructure/ en general - meme au travers d'un import local/tardif
    ou d'un module intermediaire, grimp detecte l'arete transitivement
    (voir pyproject.toml [tool.importlinter]). Ces callables sont donc
    injectes depuis l'exterieur (omega_serv.__main__, seul module neutre
    non liste dans aucun contrat) plutot que construits ici."""

    def __init__(
        self,
        project_root: Path = PROJECT_ROOT,
        service_manager_factory: Callable[[], ServiceManagerPort | None] | None = None,
        config_check_runner: Callable[[OmegaServConfig, FilesystemPort, Path, bool, bool], list[str]] | None = None,
        audit_runner: Callable[
            [OmegaServConfig, Path, Path, FilesystemPort, ClockPort, str, bool, bool], AuditResult
        ] | None = None,
        simulate_request_runner: Callable[
            [str, str, OmegaServConfig, FilesystemPort, Path], Awaitable[SimulationReport]
        ] | None = None,
        admin_request_runner: Callable[[int, str, str], Awaitable[tuple[int, dict | None] | None]] | None = None,
        waf_test_runner: Callable[
            [str, str, str, str, str, OmegaServConfig, FilesystemPort, Path, ClockPort],
            Awaitable[WafSimulationReport | None],
        ] | None = None,
        blocklist_port_factory: Callable[[OmegaServConfig, FilesystemPort, Path, ClockPort], BlocklistPort] | None = None,
        magnet_compat_check_runner: Callable[
            [MagnetConfig, Path, FilesystemPort], Awaitable[MagnetCompatibilityCheck]
        ] | None = None,
        active_defense_collaborators_factory: Callable[
            [OmegaServConfig, Path], ActiveDefenseCollaborators | None
        ] | None = None,
        ioc_export_runner: Callable[[Incident, str, Path, FilesystemPort, IoCConfig], ExportResult | None] | None = None,
        incident_report_export_runner: Callable[[Incident, Path, FilesystemPort], ExportResult] | None = None,
        certificate_tool_factory: Callable[[], CertificateToolPort] | None = None,
        acme_client_factory: Callable[[], ProcessRunnerPort] | None = None,
        remote_log_fetch_runner_factory: Callable[[], ProcessRunnerPort] | None = None,
        database_snapshot_fn: Callable[[Path, Path], None] | None = None,
        lnav_runner: Callable[[tuple[Path, ...], Palette, str, str], str | None] | None = None,
        export_capabilities_html_fn: Callable[[Sequence[Capability], str], str] | None = None,
        export_log_archives_html_fn: Callable[[Sequence[dict], str], str] | None = None,
        export_guide_html_fn: Callable[[Sequence[dict], Sequence[dict], str], str] | None = None,
        export_bans_html_fn: Callable[[Sequence[dict], int, str], str] | None = None,
        export_in_language_runner: Callable[[list[str], str], ProcessResult] | None = None,
        export_payload_fn: Callable[[str, dict, str], str | None] | None = None,
        privileged_runner_factory: Callable[[], ProcessRunnerPort] | None = None,
        serve_foreground_runner: Callable[[Path, DependencyContainer], Awaitable[int]] | None = None,
        riposte_store_factory: Callable[[Path, bool], RiposteStorePort] | None = None,
        riposte_journal_reader: Callable[[Path, Path], list[ObservedEvent]] | None = None,
        installed_jails_reader: Callable[[], frozenset[str] | None] | None = None,
        declaration_sender_factory: Callable[[str], DeclarationSenderPort] | None = None,
        release_source_factory: Callable[[str], ReleaseSourcePort] | None = None,
        url_opener: Callable[[str], bool] | None = None,
        create_instance_runner: Callable[
            [Path, str, Path, str, int, str, FilesystemPort, InstanceRegistryPort, ClockPort,
             Callable[[int, int, str], None] | None],
            str | None,
        ] | None = None,
        stale_service_checker: Callable[[str], bool] | None = None,
        systemd_unit_dir: Path = Path("/etc/systemd/system"),
        instance_registry_path: Path = INSTANCE_REGISTRY_PATH,
        instance_commands: InstanceCommandPort | None = None,
        clipboard: ClipboardPort | None = None,
        admin_web_setup: AdminWebSetupPort | None = None,
    ):
        from omega_lib.infrastructure.terminal.detector import SystemTerminalDetector

        from omega_serv.infrastructure.clock.system_clock import SystemClock
        from omega_serv.infrastructure.config.json_config_repository import JsonConfigRepository
        from omega_serv.infrastructure.config.json_settings_store import JsonSettingsStore
        from omega_serv.infrastructure.config.profile_repository import FileProfileRepository
        from omega_serv.infrastructure.filesystem.local_file_access import LocalFileAccess
        from omega_serv.infrastructure.filesystem.local_filesystem import LocalFilesystem
        from omega_serv.infrastructure.i18n.gettext_language_catalog import GettextLanguageCatalog
        from omega_serv.infrastructure.instances.json_instance_registry import JsonInstanceRegistry
        from omega_serv.infrastructure.logging.file_line_logger import FileLineLogger
        from omega_serv.infrastructure.waf.keyword_reference_store import PackagedKeywordReferences
        self._instance_commands = instance_commands
        self._clipboard = clipboard
        self._admin_web_setup = admin_web_setup
        self._service_manager_factory = service_manager_factory
        self._stale_service_checker = stale_service_checker
        self._config_check_runner = config_check_runner
        self._audit_runner = audit_runner
        self._simulate_request_runner = simulate_request_runner
        self._admin_request_runner = admin_request_runner
        self._waf_test_runner = waf_test_runner
        self._blocklist_port_factory = blocklist_port_factory
        self._magnet_compat_check_runner = magnet_compat_check_runner
        self._active_defense_collaborators_factory = active_defense_collaborators_factory
        self._ioc_export_runner = ioc_export_runner
        self._incident_report_export_runner = incident_report_export_runner
        self._certificate_tool_factory = certificate_tool_factory
        self._acme_client_factory = acme_client_factory
        self._remote_log_fetch_runner_factory = remote_log_fetch_runner_factory
        # Copie coherente d'une base SQLite en service (sauvegarde) : injectee par __main__.py / la CLI,
        # jamais importee ici (contrat import-linter : bootstrap n'atteint jamais sqlite3).
        self._database_snapshot_fn = database_snapshot_fn
        self._lnav_runner = lnav_runner
        self._create_instance_runner = create_instance_runner
        self._export_capabilities_html_fn = export_capabilities_html_fn
        self._export_log_archives_html_fn = export_log_archives_html_fn
        self._export_guide_html_fn = export_guide_html_fn
        self._export_bans_html_fn = export_bans_html_fn
        self._export_in_language_runner = export_in_language_runner
        self._export_payload_fn = export_payload_fn
        self._privileged_runner_factory = privileged_runner_factory
        self._last_export_error: str | None = None
        self._serve_foreground_runner = serve_foreground_runner
        self._riposte_store_factory = riposte_store_factory
        self._riposte_journal_reader = riposte_journal_reader
        self._installed_jails_reader = installed_jails_reader
        self._declaration_sender_factory = declaration_sender_factory
        self._release_source_factory = release_source_factory
        self._url_opener = url_opener
        self._project_root = project_root
        self._systemd_unit_dir = systemd_unit_dir
        self._filesystem: FilesystemPort = LocalFilesystem()
        # Fichiers edites depuis la TUI et lus par le service (OMEGA-SERV_PLAN-
        # DETAILLE_SENSITIVE_PATHS.md §3.7) - port dedie, voir file_access_port.py.
        self._file_access: FileAccessPort = LocalFileAccess()
        self._keyword_references: KeywordReferencePort = PackagedKeywordReferences()
        self._language_catalog: LanguageCatalogPort = GettextLanguageCatalog()
        self._configuration: ConfigurationPort = JsonConfigRepository(
            self._filesystem,
            backups_dir=project_root / "var" / "backups",
        )
        self._logger: LoggerPort = FileLineLogger()
        self._profiles: ProfileRepositoryPort = FileProfileRepository(
            self._filesystem,
            profiles_dir=project_root / "config" / "profiles",
        )
        self._clock: ClockPort = SystemClock()
        self._settings_store: SettingsStore = JsonSettingsStore(project_root / "var" / "settings.json")
        self._terminal_detector: TerminalDetector = SystemTerminalDetector()
        self._default_screenshots_dir = project_root / "var" / "screenshots"
        self._default_exports_dir = project_root / "var" / "exports"
        self._instance_registry_path = instance_registry_path
        self._instance_registry: InstanceRegistryPort = JsonInstanceRegistry(
            self._filesystem, instance_registry_path,
        )

    @property
    def project_root(self) -> Path:
        return self._project_root

    @property
    def filesystem(self) -> FilesystemPort:
        return self._filesystem

    @property
    def file_access(self) -> FileAccessPort:
        return self._file_access

    @property
    def keyword_references(self) -> KeywordReferencePort:
        return self._keyword_references

    @property
    def language_catalog(self) -> LanguageCatalogPort:
        return self._language_catalog

    @property
    def configuration(self) -> ConfigurationPort:
        return self._configuration

    @property
    def logger(self) -> LoggerPort:
        return self._logger

    @property
    def profiles(self) -> ProfileRepositoryPort:
        return self._profiles

    @property
    def clock(self) -> ClockPort:
        return self._clock

    @property
    def settings_store(self) -> SettingsStore:
        return self._settings_store

    @property
    def terminal_detector(self) -> TerminalDetector:
        return self._terminal_detector

    @property
    def default_screenshots_dir(self) -> Path:
        return self._default_screenshots_dir

    @property
    def default_exports_dir(self) -> Path:
        return self._default_exports_dir

    @property
    def systemd_unit_dir(self) -> Path:
        return self._systemd_unit_dir

    @property
    def instance_registry(self) -> InstanceRegistryPort:
        return self._instance_registry

    @property
    def instance_registry_path(self) -> Path:
        return self._instance_registry_path

    @property
    def service_manager_factory(self) -> Callable[[], ServiceManagerPort | None] | None:
        return self._service_manager_factory

    def probe_shared_access(self, group: str) -> SharedAccessReport:
        """Ecran Service, ligne Permissions (2026-11-15) : partage de var/ avec le compte du service, lecture seule."""
        from omega_serv.infrastructure.services.shared_access_probe import probe_shared_access

        return probe_shared_access(self._project_root / "var", group)

    @property
    def config_check_runner(
        self,
    ) -> Callable[[OmegaServConfig, FilesystemPort, Path, bool, bool], list[str]] | None:
        return self._config_check_runner

    @property
    def audit_runner(
        self,
    ) -> Callable[[OmegaServConfig, Path, Path, FilesystemPort, ClockPort, str, bool, bool], AuditResult] | None:
        return self._audit_runner

    @property
    def simulate_request_runner(
        self,
    ) -> Callable[[str, str, OmegaServConfig, FilesystemPort, Path], Awaitable[SimulationReport]] | None:
        return self._simulate_request_runner

    @property
    def admin_request_runner(self) -> Callable[[int, str, str], Awaitable[tuple[int, dict | None] | None]] | None:
        """Canal HTTP local vers `/.omega-serv-admin/` du processus
        serveur REELLEMENT en cours d'execution (§22 reouverture) - meme
        regime d'injection que `simulate_request_runner` (property
        brute, le `None`-check ET l'echec de connexion - `None` retourne
        par l'appel lui-meme, serveur eteint ou injoignable - restent la
        responsabilite de l'ecran)."""
        return self._admin_request_runner

    @property
    def waf_test_runner(
        self,
    ) -> Callable[
        [str, str, str, str, str, OmegaServConfig, FilesystemPort, Path, ClockPort],
        Awaitable[WafSimulationReport | None],
    ] | None:
        return self._waf_test_runner

    @property
    def blocklist_port_factory(self) -> Callable[[OmegaServConfig, FilesystemPort, Path, ClockPort], BlocklistPort] | None:
        return self._blocklist_port_factory

    @property
    def stale_service_checker(self) -> Callable[[str], bool] | None:
        """`checker(service_name)` : True si le service actif a demarre avant la
        derniere mise a jour du code installe (application/services/
        check_stale_service.py) - injecte depuis __main__ (subprocess)."""
        return self._stale_service_checker

    @property
    def magnet_compat_check_runner(
        self,
    ) -> Callable[[MagnetConfig, Path, FilesystemPort], Awaitable[MagnetCompatibilityCheck]] | None:
        return self._magnet_compat_check_runner

    @property
    def active_defense_collaborators_factory(
        self,
    ) -> Callable[[OmegaServConfig, Path], ActiveDefenseCollaborators | None] | None:
        return self._active_defense_collaborators_factory

    @property
    def ioc_export_runner(self) -> Callable[[Incident, str, Path, FilesystemPort, IoCConfig], ExportResult | None] | None:
        return self._ioc_export_runner

    @property
    def incident_report_export_runner(self) -> Callable[[Incident, Path, FilesystemPort], ExportResult] | None:
        """Rapport Markdown dans la langue des exports (Options) : processus enfant si elle
        differe de l'interface ; en cas d'echec, rapport dans la langue de l'interface (jamais
        perdu) et `last_export_error` renseigne pour le signaler."""
        base = self._incident_report_export_runner
        if base is None:
            return None

        from omega_serv.domain.security.active_defense.entities import ExportResult

        def run(incident: Incident, export_dir: Path, filesystem: FilesystemPort) -> ExportResult:
            self._last_export_error = None
            code = self._export_language_override()
            if code is None or self._export_in_language_runner is None:
                return base(incident, export_dir, filesystem)
            result = self._export_in_language_runner(["_export-report", incident.incident_id], code)
            lines = result.stdout.strip().splitlines()
            if result.ok and lines:
                path = Path(lines[-1])
                size = filesystem.file_size(path) if filesystem.is_file(path) else 0
                return ExportResult(path=path, export_format="markdown", bytes_written=size)
            self._last_export_error = self._export_error_message(code, result)
            return base(incident, export_dir, filesystem)

        return run

    @property
    def certificate_tool_factory(self) -> Callable[[], CertificateToolPort] | None:
        return self._certificate_tool_factory

    @property
    def acme_client_factory(self) -> Callable[[], ProcessRunnerPort] | None:
        """`ProcessRunnerPort` brut (jamais un adaptateur specifique a
        Certbot - `domain/security/tls/acme.py` construit deja l'argv
        complet, aucun besoin d'un wrapper dedie) - meme regime que
        `certificate_tool_factory` : None dans les tests (jamais de vrai
        `certbot` invoque par une suite automatisee), une vraie
        `SubprocessRunner()` en production (omega_serv.__main__)."""
        return self._acme_client_factory

    @property
    def remote_log_fetch_runner_factory(self) -> Callable[[], ProcessRunnerPort] | None:
        """`ProcessRunnerPort` brut pour lancer `scp` depuis l'ecran
        "Sources distantes (SSH)" (OMEGA-SERV_ETUDE-FAISABILITE_LOGS_
        DISTANTS.md, 2026-10-15) - meme regime que `acme_client_factory` :
        None dans les tests (jamais un vrai `scp` invoque par une suite
        automatisee), une vraie `SubprocessRunner()` en production
        (omega_serv.__main__). Factory distincte (pas de reutilisation
        de `acme_client_factory`) : type identique mais semantiquement
        "le runner Certbot/ACME", reutiliser ce nom pour `scp` serait un
        nom trompeur meme si le type est identique."""
        return self._remote_log_fetch_runner_factory

    @property
    def lnav_runner(self) -> Callable[[tuple[Path, ...], Palette, str, str], str | None] | None:
        return self._lnav_runner

    @property
    def create_instance_runner(self) -> Callable[
        [Path, str, Path, str, int, str, FilesystemPort, InstanceRegistryPort, ClockPort,
         Callable[[int, int, str], None] | None],
        str | None,
    ] | None:
        return self._create_instance_runner

    @property
    def config_file(self) -> Path:
        return self._project_root / "config" / "omega-serve.json"


    def build_users_repository(self, auth_file: Path) -> UsersRepositoryPort:
        from omega_serv.infrastructure.auth.users_repository import JsonUsersRepository
        return JsonUsersRepository(self._filesystem, auth_file)

    def build_auth_zones_repository(self, auth_zones_file: Path) -> AuthZonesRepositoryPort:
        from omega_serv.infrastructure.auth.auth_zones_repository import JsonAuthZonesRepository
        return JsonAuthZonesRepository(self._filesystem, auth_zones_file)

    def native_waf_filter_section(self, config: OmegaServConfig) -> dict[str, Any] | None:
        """Section `waf_filter` que recevrait le moteur natif (plan WAF natif, lot 5 : ecran Etat du WAF) - memes
        fonctions que l'instantane ; None sans WAF."""
        from omega_serv.infrastructure.server.native_snapshot import waf_filter_section

        return waf_filter_section(config, self._project_root)

    def build_capability_scanner(self, configured_port: int,
                                 fastcgi_sockets: tuple[Path, ...] = ()) -> CapabilityScannerPort:
        from omega_serv.infrastructure.probe.scanner import SystemCapabilityScanner

        return SystemCapabilityScanner(self._project_root, self._filesystem, configured_port, fastcgi_sockets)

    def build_live_tail_reader(self, path: Path) -> LiveTailPort:
        from omega_serv.infrastructure.logging.live_tail_reader import LiveTailReader

        return LiveTailReader(path)

    def collect_system_stats(self) -> dict[str, Any]:
        from omega_serv.infrastructure.probe.system_stats import collect_system_stats

        return collect_system_stats()

    def collect_server_stats(self, pid: int | None, port: int) -> dict[str, Any]:
        """Processus omega-serv, connexions sur son port, journaux et espace libre de var/ (psutil)."""
        from omega_serv.infrastructure.probe.system_stats import collect_server_stats

        return collect_server_stats(pid, port, self._project_root / "var" / "log", self._project_root / "var")

    def access_log_sent_bytes(self, path: Path, since: datetime, offset: int | None) -> tuple[int, int]:
        """Octets de reponse de l'access log depuis `since`, a partir de `offset` (voir access_log_volume)."""
        from omega_serv.infrastructure.logging.access_log_volume import sent_bytes_since

        return sent_bytes_since(path, since, offset)

    def build_archive_store(self, base_dir: Path, private: bool = False) -> ArchiveStore:
        from omega_serv.infrastructure.storage.files.archive_store import ArchiveStore

        return ArchiveStore(base_dir, private=private)

    def rotate_log_if_needed(
        self, log_path: Path, max_size_bytes: int, keep: int, archive_base_dir: Path
    ) -> RotateLogResult:
        from omega_serv.application.logs.rotate_log import rotate_log_if_needed

        archive_store = self.build_archive_store(archive_base_dir)
        return rotate_log_if_needed(log_path, max_size_bytes, keep, self._filesystem, archive_store, self._clock.now())

    def compute_log_stats(self, log_path: Path, period_label: str) -> LogStatsSummary:
        from omega_serv.infrastructure.logging.log_parser import compute_log_stats

        return compute_log_stats(log_path, period_label, self._clock.now())

    def remove_ip_from_log(self, ip: str, log_path: Path) -> int:
        from omega_serv.infrastructure.logging.logs_maintenance import LogsMaintenance

        return LogsMaintenance().remove_ip(ip, log_path)

    def build_rotation_automation_store(self) -> RotationAutomationStore:
        from omega_serv.infrastructure.logging.rotation_automation_store import (
            RotationAutomationStore,
        )

        path = self._project_root / "var" / "run" / "log_rotation_automations.json"
        return RotationAutomationStore(path)

    @property
    def last_export_error(self) -> str | None:
        """Raison du dernier export qui n'a pas pu etre produit dans la langue des exports."""
        return self._last_export_error

    @property
    def export_language_name(self) -> str | None:
        """Nom natif de la langue des exports si elle differe de l'interface (export par
        processus enfant, quelques secondes), sinon None."""
        from omega_lib.i18n.policies import language_for

        code = self._export_language_override()
        return None if code is None else language_for(code).native_name

    def _export_language_override(self) -> str | None:
        from omega_serv.application.terminal.select_language import export_language_override
        from omega_serv.core.i18n import STATE

        return export_language_override(self._settings_store, STATE.language.code)

    def _export_error_message(self, code: str, result: ProcessResult) -> str:
        from omega_lib.i18n.policies import language_for

        from omega_serv.core.i18n import _

        if result.returncode == 3:  # EXPORT_CHILD_INCIDENT_NOT_FOUND (__main__.py)
            detail = _("Incident introuvable.")
        else:
            detail = (result.stderr.strip().splitlines() or [str(result.returncode)])[-1]
        return _("Export dans la langue « {name} » impossible : {error}").format(
            name=language_for(code).native_name, error=detail)

    def _render_html_export(
        self, kind: str, theme_name: str, render_here: Callable[[], str] | None,
    ) -> str | None:
        self._last_export_error = None
        code = self._export_language_override()
        if code is None:
            return None if render_here is None else render_here()
        if self._export_in_language_runner is None:
            return None
        result = self._export_in_language_runner(["_export-html", kind, theme_name], code)
        if not result.ok:
            self._last_export_error = self._export_error_message(code, result)
            return None
        return result.stdout

    def export_capabilities_html(self, capabilities: Sequence[Capability], theme_name: str) -> str | None:
        fn = self._export_capabilities_html_fn
        return self._render_html_export(
            "capabilities", theme_name, None if fn is None else (lambda: fn(capabilities, theme_name)))

    def export_log_archives_html(self, archives: Sequence[dict], theme_name: str) -> str | None:
        fn = self._export_log_archives_html_fn
        return self._render_html_export(
            "log-archives", theme_name, None if fn is None else (lambda: fn(archives, theme_name)))

    def export_guide_html(self, screen_guides: Sequence[dict], faq_entries: Sequence[dict], theme_name: str) -> str | None:
        fn = self._export_guide_html_fn
        return self._render_html_export(
            "guide", theme_name, None if fn is None else (lambda: fn(screen_guides, faq_entries, theme_name)))

    def export_bans_html(self, bans: Sequence[dict], active_count: int, theme_name: str) -> str | None:
        """Statut des bans : dans une autre langue d'export, l'enfant relit lui-meme la blocklist (tous les bans)."""
        fn = self._export_bans_html_fn
        return self._render_html_export(
            "bans", theme_name, None if fn is None else (lambda: fn(bans, active_count, theme_name)))

    @property
    def privileged_runner_factory(self) -> Callable[[], ProcessRunnerPort] | None:
        """Runner des operations sur les logs avec sudo (2026-11-07 : Statistiques, Voir et traiter IP, Sante
        des logs) - meme regime que `acme_client_factory` : None dans les tests (jamais de vrai sudo), une
        vraie `SubprocessRunner()` en production (omega_serv.__main__)."""
        return self._privileged_runner_factory

    def export_payload(self, kind: str, payload: dict, theme_name: str) -> str | None:
        """Rapport rendu a partir de donnees deja calculees (Statistiques, Sante des logs - 2026-11-07) :
        `kind` = "log-stats", "log-health" ou "log-health-txt". Dans une autre langue d'export, les
        donnees passent a l'enfant par un fichier JSON temporaire de var/run/ (jamais recalculees : un
        gros log prendrait des minutes), supprime ensuite."""
        import json
        import tempfile

        self._last_export_error = None
        fn = self._export_payload_fn
        code = self._export_language_override()
        if code is None:
            if fn is None and kind == "full-report-txt":
                from omega_serv.application.report.full_report_presentation import render_text

                return render_text(payload)  # HTML : jinja2 seulement via __main__ (contrat import-linter)
            return None if fn is None else fn(kind, payload, theme_name)
        if self._export_in_language_runner is None:
            return None
        run_dir = self._project_root / "var" / "run"
        run_dir.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".json", prefix="export-payload-",
                                         dir=run_dir, delete=False) as handle:
            json.dump(payload, handle, ensure_ascii=False, default=str)
            payload_path = Path(handle.name)
        try:
            result = self._export_in_language_runner(["_export-payload", kind, theme_name, str(payload_path)], code)
        finally:
            payload_path.unlink(missing_ok=True)
        if not result.ok:
            self._last_export_error = self._export_error_message(code, result)
            return None
        return result.stdout

    @property
    def serve_foreground_runner(self) -> Callable[[Path, DependencyContainer], Awaitable[int]] | None:
        """Lance reellement le serveur au premier plan (bloquant jusqu'a
        Ctrl+C/SIGTERM) - retour utilisateur 2026-09-09 : l'assistant
        premier lancement ecrivait la configuration puis se contentait
        d'un toast ephemere rappelant de lancer `omega-serv.sh serve`
        soi-meme, facilement manque ; le bouton "Lancer maintenant"
        (wizard_service_screen.py) attend directement ce callable sous
        `_maybe_suspend()` (meme mecanisme que sudo/lnav) - jamais un
        appel synchrone : `interfaces.cli.main::run_server_until_stopped`
        est une coroutine qui doit tourner sur la boucle asyncio DEJA
        active de Textual (App.suspend() ne suspend jamais cette boucle,
        seulement le pilote du terminal - imbriquer un `asyncio.run()`
        dedans leve RuntimeError, verifie empiriquement). Meme regime
        d'injection que `simulate_request_runner` (property brute, le
        `None`-check et l'attente restent la responsabilite de
        l'ecran) - cable uniquement depuis `__main__.py`, `cmd_serve`
        importe `build_server` qui touche infrastructure/ssl
        transitivement."""
        return self._serve_foreground_runner

    @property
    def riposte_store_factory(self) -> Callable[[Path, bool], RiposteStorePort] | None:
        """`factory(base, ecriture)` : ouvre la base RIPOSTE (jamais creee : elle appartient au processus
        RIPOSTE) ; FileNotFoundError si RIPOSTE n'a jamais ete lance, OSError si illisible. Une connexion par
        appel, a fermer (`close()`) : jamais partagee entre fils. Injectee depuis __main__.py (sqlite3)."""
        return self._riposte_store_factory

    @property
    def riposte_journal_reader(self) -> Callable[[Path, Path], list[ObservedEvent]] | None:
        """`reader(waf_alerts_log, security_events_log)` : evenements des journaux pour « Mesurer »."""
        return self._riposte_journal_reader

    @property
    def installed_jails_reader(self) -> Callable[[], frozenset[str] | None] | None:
        """`reader()` : noms des jails installees par omega-jail (fichiers `jail.d/omega-jail-<nom>.conf`), None si
        fail2ban est absent ou illisible. Lecture seule ; injectee depuis __main__.py."""
        return self._installed_jails_reader

    @property
    def app_version(self) -> str:
        """Version d'omega-serv (pyproject.toml, seule source)."""
        from omega_serv.infrastructure.declaration.app_version import application_version
        return application_version(self._project_root)

    @property
    def declaration_store(self) -> DeclarationStorePort:
        """Declaration anonyme d'utilisateur (OMEGA-SERV_ETUDE_TELEMETRIE.md §3b), sous var/lib/declaration/."""
        from omega_serv.infrastructure.declaration.json_declaration_store import (
            JsonDeclarationStore,
        )
        return JsonDeclarationStore(self._project_root)

    def declaration_sender(self) -> DeclarationSenderPort | None:
        """Envoi HTTPS vers la reception ; None hors interface (urllib atteint ssl : injecte depuis
        __main__.py, jamais importe ici)."""
        factory = self._declaration_sender_factory
        return None if factory is None else factory(self.app_version)

    def release_source(self) -> ReleaseSourcePort | None:
        """Lecture de download/sha.txt pour « Verifier les mises a jour » ; None hors interface (urllib atteint
        ssl : injecte depuis __main__.py, jamais importe ici, comme declaration_sender)."""
        factory = self._release_source_factory
        return None if factory is None else factory(self.app_version)

    def open_url(self, url: str) -> bool:
        """Ouvre une adresse web dans le navigateur de l'utilisateur (meme sous sudo). False sans
        session graphique : l'ecran affiche alors l'adresse, deja visible en clair."""
        opener = self._url_opener
        return False if opener is None else opener(url)


    def _backups_dir(self) -> Path:
        return self._project_root / "var" / "backups" / "config-snapshots"

    def build_backup_metadata_store(self, base_dir: Path) -> BackupMetadataStore:
        from omega_serv.infrastructure.persistence.backup_metadata_store import BackupMetadataStore

        return BackupMetadataStore(base_dir)

    def build_proxy_cache_store(self, *, max_size_mb: int) -> ProxyCacheStorePort:
        """Usine pour `interfaces.tui.screens.reverse_proxy_cache_screen`
        (Phase 8, OMEGA-SERV_PLAN-DETAILLE_REVERSE_PROXY.md §21) - meme
        regime que `build_backup_metadata_store` : interfaces.tui ne peut
        jamais importer infrastructure directement (contrat import-linter),
        donc l'adaptateur concret est construit ici et rendu via son port.
        Pointe vers le MEME repertoire que `start_server.py` pour que
        l'ecran lise toujours l'etat reel du cache serveur sur disque."""
        from omega_serv.infrastructure.proxy_cache.filesystem_proxy_cache_store import (
            FilesystemProxyCacheStore,
        )

        return FilesystemProxyCacheStore(
            self._project_root / "var" / "cache" / "reverse_proxy", max_size_mb=max_size_mb
        )

    def build_log_library_repository(self) -> LogLibraryRepositoryPort:
        """Usine pour la Bibliotheque de logs (gestion des logs, refonte
        menu 2026-10-15) - meme regime que `build_proxy_cache_store`."""
        from omega_serv.infrastructure.logging.json_log_library_repository import (
            JsonLogLibraryRepository,
        )

        return JsonLogLibraryRepository(self._project_root / "var" / "library.json")

    def build_log_favorite_repository(self) -> LogFavoriteRepositoryPort:
        from omega_serv.infrastructure.logging.json_log_favorite_repository import (
            JsonLogFavoriteRepository,
        )

        return JsonLogFavoriteRepository(self._project_root / "var" / "favorites.json")

    def build_remote_log_source_repository(self) -> RemoteLogSourceRepositoryPort:
        """Usine pour les Sources distantes SSH (OMEGA-SERV_ETUDE-
        FAISABILITE_LOGS_DISTANTS.md, 2026-10-15) - meme regime que
        `build_log_favorite_repository`."""
        from omega_serv.infrastructure.logging.json_remote_log_source_repository import (
            JsonRemoteLogSourceRepository,
        )

        return JsonRemoteLogSourceRepository(self._project_root / "var" / "remote-log-sources.json")

    def create_backup(self, request: BackupRequest, config: OmegaServConfig, config_file: Path) -> BackupResult:
        from omega_serv.application.persistence.create_backup import create_backup

        backups_dir = self._backups_dir()
        archive_store = self.build_archive_store(backups_dir, private=True)
        metadata_store = self.build_backup_metadata_store(backups_dir)
        return create_backup(
            request, config, self._project_root, config_file, archive_store, metadata_store, self._clock,
            snapshot=self._database_snapshot_fn, manifest=self._backup_manifest(config),
            exports_dir=self.exports_dir(),
        )

    def exports_dir(self) -> Path:
        """Dossier des exports en vigueur : celui des Reglages, sinon `var/exports/`."""
        override = self.settings_store.get("exports_dir_override", "")
        return Path(override).expanduser() if override else self._default_exports_dir

    def _backup_manifest(self, config: OmegaServConfig) -> dict[str, object]:
        """Fiche de la sauvegarde (projets 3.0.0 §7.4, 2026-11-15)."""
        from omega_serv.application.persistence.backup_manifest import MANIFEST_FORMAT

        entry = self._this_instance_entry()
        return {
            "format": MANIFEST_FORMAT, "app_version": self.app_version,
            "instance": entry.name if entry is not None else self._project_root.name,
            "bind": config.server.bind, "port": config.server.port,
            "service_name": entry.service_name if entry is not None
            else self.settings_store.get("service_name", "") or "omega-serv",
        }

    def _this_instance_entry(self) -> InstanceEntry | None:
        current = self.filesystem.resolve_real_path(self._project_root)
        return next((entry for entry in self.instance_registry.load() if entry.path == current), None)

    def export_backup(self, snapshot_id: str, dest_dir: Path) -> TransferResult:
        from omega_serv.application.persistence.backup_transfer import export_backup

        entry = self._this_instance_entry()
        return export_backup(self.build_backup_metadata_store(self._backups_dir()), snapshot_id, dest_dir,
                             entry.name if entry is not None else self._project_root.name)

    def import_backup(self, archive_path: Path, webroot_name: str = "webroot") -> TransferResult:
        from omega_serv.application.persistence.backup_transfer import import_backup

        backups_dir = self._backups_dir()
        return import_backup(archive_path, self.build_archive_store(backups_dir, private=True),
                             self.build_backup_metadata_store(backups_dir), self._clock, webroot_name)

    def backup_port_conflict(self, snapshot_id: str) -> tuple[ArchiveIdentity, InstanceEntry] | None:
        """Instance enregistree (autre que celle-ci) qui ecoute deja a l'adresse et au port de l'archive."""
        from omega_serv.application.persistence.backup_transfer import archive_identity
        from omega_serv.domain.instances.registry import find_port_conflict

        backups_dir = self._backups_dir()
        metadata = self.build_backup_metadata_store(backups_dir).load(snapshot_id)
        if metadata is None or metadata.file_path is None:
            return None
        identity = archive_identity(self.build_archive_store(backups_dir, private=True), Path(metadata.file_path))
        if identity.bind is None or identity.port is None:
            return None
        current = self.filesystem.resolve_real_path(self._project_root)
        others = [entry for entry in self.instance_registry.load() if entry.path != current]
        conflict = find_port_conflict(others, identity.bind, identity.port)
        return (identity, conflict) if conflict is not None else None

    @property
    def admin_accounts(self) -> AdminAccountsPort:
        """Comptes de l'administration web (secure/auth/admin-web.json), tableau de bord web lot 3."""
        from omega_serv.infrastructure.admin_web.accounts_repository import (
            ACCOUNTS_RELATIVE_PATH,
            JsonAdminAccountsRepository,
        )

        return JsonAdminAccountsRepository(self.filesystem, self._project_root / ACCOUNTS_RELATIVE_PATH)

    def admin_used_backup_codes(self) -> set[str]:
        """Codes de secours deja utilises (haches), tenus par le processus d'administration dans var/lib/admin/."""
        from omega_serv.infrastructure.admin_web.used_backup_codes import (
            USED_BACKUP_CODES_RELATIVE_PATH,
            UsedBackupCodes,
        )

        return UsedBackupCodes(self.filesystem, self._project_root / USED_BACKUP_CODES_RELATIVE_PATH).load()

    def admin_audit(self, message: str) -> None:
        """Une ligne horodatee dans var/log/admin-audit.log (journal d'audit de l'administration web)."""
        import contextlib
        from datetime import timezone

        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        # Scan de securite n° 1 (2026-11-20, F38/F39) : tout caractere non imprimable (\r, \n, U+2028, U+0085,
        # controles...) est ecrit echappe - une valeur venue d'un formulaire, d'un maitre ou d'une instance suivie ne
        # peut plus fabriquer une fausse ligne d'audit (le lecteur decoupe avec str.splitlines()).
        safe = "".join(ch if ch.isprintable() else ch.encode("unicode_escape").decode("ascii") for ch in message)
        with contextlib.suppress(OSError):
            self.logger.append_line(self._project_root / "var" / "log" / "admin-audit.log", f"{stamp} {safe}")

    def admin_master_manager(self) -> MasterLinkManager:
        """Maitre accepte par cette instance et fenetre d'appairage (tableau de bord web, lot 6) : TUI et CLI."""
        import time

        from omega_serv.application.admin_web.master_link import MasterLinkManager
        from omega_serv.infrastructure.admin_web.master_store import MasterStore

        return MasterLinkManager(MasterStore(self.filesystem, self._project_root), time.time, self.admin_audit)

    @property
    def clipboard(self) -> ClipboardPort | None:
        """Presse-papiers du systeme (copie du secret TOTP) ; injecte par omega_serv.__main__, None dans les tests."""
        return self._clipboard

    @property
    def admin_web_setup(self) -> AdminWebSetupPort | None:
        """Essai d'ecoute, adresses, pare-feu, droits du certificat (lot 8) ; injecte par omega_serv.__main__, None ou
        un faux dans les tests."""
        return self._admin_web_setup

    def admin_run_state(self) -> AdminRunState | None:
        from omega_serv.infrastructure.admin_web.run_state_store import AdminRunStateStore

        return AdminRunStateStore(self.filesystem, self._project_root).load()

    def admin_web_readiness(self, config: OmegaServConfig) -> list[ReadinessItem]:
        """Bilan « prêt / ce qui manque » de Configuration distante (lot 8)."""
        from omega_serv.application.admin_web.checks import admin_web_certificate_paths
        from omega_serv.application.admin_web.readiness import ReadinessFacts, admin_web_readiness
        from omega_serv.domain.admin_web.settings import OPTION_NAME, AdminWebSettings
        from omega_serv.infrastructure.admin_web.accounts_repository import AdminAccountsFileError

        option = config.options.get(OPTION_NAME)
        settings = AdminWebSettings.from_settings(option.settings if option is not None else {})
        paths = admin_web_certificate_paths(config, settings)
        present = tuple(self.filesystem.is_file(self._project_root / p) for p in paths) if paths else (True, True)
        accounts: tuple[AdminAccount, ...] | None
        try:
            accounts, accounts_error = self.admin_accounts.load(), ""
        except AdminAccountsFileError as error:
            accounts, accounts_error = None, str(error)
        setup = self._admin_web_setup
        names = setup.machine_names() if setup is not None else ("", ())
        facts = ReadinessFacts(
            certificate_present=(present[0], present[1]), accounts=accounts, accounts_error=accounts_error,
            others=tuple(self._other_admin_ports()), run_state=self.admin_run_state(),
            service_active=self._service_active(), firewall=setup.active_firewall() if setup is not None else "",
            addresses=names[1],
            firewall_linked=bool(setup.linked_firewall(self._project_root)) if setup is not None else False,
            firewall_opened=self.admin_firewall_record())
        return admin_web_readiness(config, facts)

    def admin_alert_store(self) -> AlertStorePort:
        """Alertes locales du panneau web (etude modules, module 1) : etat, maintenance, journal."""
        from omega_serv.infrastructure.admin_web.alert_store import AlertStore

        return AlertStore(self._filesystem, self._project_root)

    def admin_session_files(self) -> SessionFilesPort:
        """Sessions ouvertes du panneau web, vues depuis la TUI (etude modules, module 5)."""
        from omega_serv.infrastructure.admin_web.session_files import SessionFiles

        return SessionFiles(self._filesystem, self._project_root)

    def admin_firewall_record(self) -> FirewallRecord | None:
        """Sous-lot 8b : ouverture du port de l'administration web par omega-fire, telle que retenue."""
        from omega_serv.infrastructure.admin_web.firewall_record_store import FirewallRecordStore

        return FirewallRecordStore(self._filesystem, self._project_root).load()

    def save_admin_firewall_record(self, record: FirewallRecord) -> bool:
        from omega_serv.infrastructure.admin_web.firewall_record_store import FirewallRecordStore

        return FirewallRecordStore(self._filesystem, self._project_root).save(record)

    def _service_active(self) -> bool | None:
        from omega_serv.application.services.resolve_current_service_name import (
            resolve_current_service_name,
        )
        from omega_serv.domain.services.exceptions import ServiceManagerError

        factory = self._service_manager_factory
        manager = factory() if factory is not None else None
        if manager is None:
            return None
        name = resolve_current_service_name(self.instance_registry, self.filesystem, self.settings_store,
                                            self._project_root)
        if not self.filesystem.exists(self._systemd_unit_dir / f"{name}.service"):
            return None  # pas de service installe : serveur lance a la main, seul l'etat ecrit fait foi
        try:
            return manager.is_active(name)
        except (ServiceManagerError, OSError):
            return None

    @property
    def instance_commands(self) -> InstanceCommandPort | None:
        """CLI d'une autre instance de cette machine, avec son propre environnement (« Relier au maître ») ; une
        vraie `InstanceCommandRunner` en production (omega_serv.__main__), None ou un faux dans les tests."""
        return self._instance_commands

    def admin_web_warnings(self, config: OmegaServConfig) -> list[str]:
        """Tableau de bord web, lot 2 : ce qui empecherait l'administration web de demarrer (certificat absent, port
        deja pris par une autre instance du registre : son site ou sa propre administration web)."""
        from omega_serv.application.admin_web.checks import admin_web_warnings

        others = self._other_admin_ports()
        from omega_serv.infrastructure.admin_web.accounts_repository import AdminAccountsFileError

        try:
            accounts = self.admin_accounts.load()
        except AdminAccountsFileError as error:
            return [*admin_web_warnings(config, self.filesystem, self._project_root, others), str(error)]
        return admin_web_warnings(config, self.filesystem, self._project_root, others, accounts)

    def _other_admin_ports(self) -> list[tuple[InstanceEntry, int | None]]:
        """Autres instances du registre et le port de leur administration web (None si inactive)."""
        from omega_serv.application.admin_web.checks import admin_web_settings
        from omega_serv.application.config.load_config import load_config

        current = self.filesystem.resolve_real_path(self._project_root)
        others: list[tuple[InstanceEntry, int | None]] = []
        for entry in self.instance_registry.load():
            if entry.path == current:
                continue
            result = load_config(self._configuration, entry.path / "config" / "omega-serve.json")
            settings = admin_web_settings(result.config) if result.success and result.config is not None else None
            port = settings.port if settings is not None and isinstance(settings.port, int) else None
            others.append((entry, port))
        return others

    def backup_identity(self, snapshot_id: str) -> ArchiveIdentity | None:
        from omega_serv.application.persistence.backup_transfer import archive_identity

        backups_dir = self._backups_dir()
        metadata = self.build_backup_metadata_store(backups_dir).load(snapshot_id)
        if metadata is None or metadata.file_path is None:
            return None
        return archive_identity(self.build_archive_store(backups_dir, private=True), Path(metadata.file_path))

    def server_running(self) -> bool:
        """Serveur de CETTE instance en marche (fichier PID et processus vivant), service ou lancement a la main."""
        from omega_serv.application.services.pid_file import pid_file_status
        from omega_serv.core.platform_info import is_process_running

        # Corrige 2026-11-02 : pid_file_status rend (pid, ILLISIBLE), pas (pid, vivant) - le second element etait
        # pris pour « vivant », donc un serveur en marche passait pour arrete (restauration d'une base permise).
        pid, _unreadable = pid_file_status(self._filesystem, self._project_root / "var" / "run" / "omega-serv.pid")
        return pid is not None and is_process_running(pid)

    def engine_status(self, config: OmegaServConfig) -> EngineStatus:
        """Moteur HTTP demande / effectif / raisons (plan moteur C++ §16.5) : etat reel si le serveur tourne,
        sinon prevision pour `config`."""
        from omega_serv.application.server.engine_status import engine_status

        return engine_status(self._filesystem, self._project_root, config, self.native_binary_problem())

    def native_binary_problem(self) -> str | None:
        """Binaire natif present et executable (None), sinon BINARY_MISSING / BINARY_NOT_EXECUTABLE - verifie ici,
        jamais suppose par l'interface (choix du moteur grise, garde-fou d'enregistrement)."""
        from omega_serv.application.server.engine_selection import NATIVE_BINARY_RELATIVE_PATH
        from omega_serv.infrastructure.process.native_engine_process import native_binary_problem

        return native_binary_problem(self._project_root / NATIVE_BINARY_RELATIVE_PATH)

    def restore_backup(self, snapshot_id: str, *, stop_and_restart: bool = False,
                       after_restore: Callable[[], None] | None = None) -> RestoreResult:
        """Une sauvegarde qui contient une base est refusee tant que le serveur tourne (decision utilisateur
        2026-11-01) ; `stop_and_restart` : « Arreter, restaurer, redemarrer » par le gestionnaire de service."""
        from omega_serv.application.persistence.restore_backup import RestoreResult, restore_backup
        from omega_serv.application.persistence.restore_with_service import restore_stopping_service
        from omega_serv.application.services.resolve_current_service_name import (
            resolve_current_service_name,
        )
        from omega_serv.core.i18n import _

        backups_dir = self._backups_dir()
        archive_store = self.build_archive_store(backups_dir, private=True)
        metadata_store = self.build_backup_metadata_store(backups_dir)
        def restore_then_fix(running: bool) -> RestoreResult:
            # `after_restore` (2026-11-15, conflit de port) : juste apres l'extraction, AVANT tout redemarrage.
            result = restore_backup(snapshot_id, self._project_root, archive_store, metadata_store,
                                    server_running=running)
            if result.success and after_restore is not None:
                after_restore()
            return self._with_missing_zone_folders(result) if result.success else result

        if not stop_and_restart:
            return restore_then_fix(self.server_running())
        manager = self._service_manager_factory() if self._service_manager_factory is not None else None
        if manager is None:
            return RestoreResult(False, _("Aucun gestionnaire de service : arrêtez le serveur vous-même, puis restaurez."))
        service_name = resolve_current_service_name(
            self.instance_registry, self._filesystem, self.settings_store, self._project_root,
        )
        return restore_stopping_service(
            lambda: restore_then_fix(False),
            manager, service_name, self.server_running,
        )

    def _with_missing_zone_folders(self, result: RestoreResult) -> RestoreResult:
        """Projets 3.0.0 §8.2, P1 (decision de l'auteur du 2026-11-16) : apres une restauration, les dossiers des zones
        actives absents (cible d'alias, listing, scripts FastCGI) sont annonces, jamais passes sous silence."""
        import dataclasses

        from omega_serv.application.config.load_config import load_config
        from omega_serv.application.persistence.zone_data import missing_zone_folders

        loaded = load_config(self.configuration, self.config_file)
        if not loaded.success or loaded.config is None:
            return result
        messages = tuple(m.message() for m in missing_zone_folders(loaded.config, self._project_root))
        return dataclasses.replace(result, missing_zone_folders=messages) if messages else result

    def collect_full_report(self, config: OmegaServConfig, details: frozenset[str] = frozenset()) -> dict[str, object]:
        """Rapport complet (projets 3.0.0 §7.7 et §7.10) : charge brute, sans texte traduit ni secret. Lente au plus
        quelques secondes (audit compris) : toujours appelee hors du fil de l'interface."""
        import os
        import socket

        from omega_serv.application.report.full_report import proxy_mode, scrub
        from omega_serv.application.server.engine_levels import zone_engine_labels
        from omega_serv.application.services.pid_file import pid_file_status
        from omega_serv.application.services.resolve_current_service_name import (
            resolve_current_service_name,
        )
        from omega_serv.core.platform_info import is_process_running
        from omega_serv.domain.config.option import Option
        from omega_serv.domain.config.rules import detect_conflicts
        from omega_serv.domain.config.validation import validate_config
        from omega_serv.domain.routing.proxy_zone import parse_proxy_zones

        root = self._project_root
        now = self._clock.now()

        def option(name: str) -> Option | None:
            return config.options.get(name)

        def enabled(name: str) -> bool:
            found = option(name)
            return bool(found and found.enabled)

        def listed(name: str, key: str) -> list:
            found = option(name)
            value = found.settings.get(key, []) if found is not None else []
            return value if isinstance(value, list) else []

        def fastcgi_zones() -> list:
            # Projets 3.0.0 §8.1 : liste de zones, ou ancien enregistrement a plat (une zone).
            from omega_serv.domain.routing.fastcgi_zone import fastcgi_zone_entries
            found = option("fastcgi")
            return fastcgi_zone_entries(found.settings) if found is not None else []

        entry = self._this_instance_entry()
        profile_label = ""
        try:
            profile_label = self._profiles.load_profile(config.profile).label
        except Exception:  # noqa: BLE001 - profil supprime ou illisible : le nom suffit
            profile_label = ""

        # Service et uptime
        manager = self._service_manager_factory() if self._service_manager_factory is not None else None
        service_name = resolve_current_service_name(self.instance_registry, self._filesystem, self.settings_store, root)
        unit_installed = self._filesystem.exists(self._systemd_unit_dir / f"{service_name}.service")
        active = enabled_at_boot = False
        if manager is not None:
            try:
                status = manager.status(service_name)
                active, enabled_at_boot = status.active, status.enabled
            except Exception:  # noqa: BLE001 - unite inconnue : simplement « non »
                active = enabled_at_boot = False
        pid, _unreadable = pid_file_status(self._filesystem, root / "var" / "run" / "omega-serv.pid")
        running = pid is not None and is_process_running(pid)
        started_at = None
        if running and pid is not None:
            try:
                import psutil

                started_at = datetime.fromtimestamp(psutil.Process(pid).create_time(), tz=now.tzinfo).isoformat()
            except Exception:  # noqa: BLE001
                started_at = None

        # Ecoute, mode, moteur
        engine = self.engine_status(config)
        zones = parse_proxy_zones(cast("Option", option("reverse_proxy")).settings.get("zones", [])) if option("reverse_proxy") is not None else []
        prefixes = [zone.url_prefix for zone in zones]

        # TLS
        tls: dict[str, object] = {"enabled": config.tls.enabled, "mode": config.tls.mode if config.tls.enabled else None,
                                  "certificate_path": config.tls.certificate_path if config.tls.enabled else None,
                                  "hsts": config.security.hsts_enabled}
        if config.tls.enabled and self._certificate_tool_factory is not None:
            try:
                from omega_serv.application.tls.inspect_certificate import (
                    inspect_certificate_report,
                )

                report = inspect_certificate_report(root / config.tls.certificate_path, root / config.tls.private_key_path,
                                                    self._certificate_tool_factory(), self._filesystem, self._clock)
                tls.update(issuer=report.info.issuer, expires_at=report.info.not_after.isoformat(),
                           days_remaining=report.days_remaining)
            except Exception:  # noqa: BLE001 - certificat absent ou illisible : signale par l'audit
                tls["issuer"] = None

        # Securite
        banned: int | None = None
        if enabled("waf") and self._blocklist_port_factory is not None:
            try:
                from omega_serv.application.security.manual_intervention import (
                    collect_ban_rows,
                    magnet_list_path,
                )

                rows, _warning = collect_ban_rows(self._blocklist_port_factory(config, self._filesystem, root, self._clock),
                                                  self._filesystem, magnet_list_path(config, root), now)
                banned = sum(1 for row in rows if row.active)
            except Exception:  # noqa: BLE001
                banned = None
        auth_zones = 0
        try:
            auth_zones = len(self.build_auth_zones_repository(root / config.paths.auth_zones).load())
        except Exception:  # noqa: BLE001
            auth_zones = 0
        waf = option("waf")

        # Sauvegardes et journaux
        backups = sorted(self.list_backups(), key=lambda meta: meta.created_at)
        logs_dir = root / config.paths.logs
        logs_bytes = 0
        for current, _dirs, files in os.walk(logs_dir):
            for name in files:
                try:
                    logs_bytes += os.lstat(os.path.join(current, name)).st_size
                except OSError:
                    continue

        payload: dict[str, object] = {
            "format": 1,
            "identity": {"instance": entry.name if entry is not None else root.name, "path": str(root),
                         "app_version": self.app_version, "profile": config.profile, "profile_label": profile_label,
                         "hostname": socket.gethostname(), "generated_at": now.isoformat()},
            "service": {"name": service_name, "manager": manager.manager_type() if manager is not None else None,
                        "unit_installed": unit_installed, "running": running or active, "enabled": enabled_at_boot,
                        "started_at": started_at, "account": "omega-serv" if unit_installed else None,
                        "workers": engine.workers},
            "listen": {"bind": config.server.bind, "port": config.server.port,
                       "mode": proxy_mode(enabled("reverse_proxy"), prefixes),
                       "engine": engine.forecast.effective, "fallback_reasons": list(engine.forecast.reasons),
                       "zone_engines": zone_engine_labels(config) if enabled("reverse_proxy") else {}},
            "tls": tls,
            "options": {name: found.enabled for name, found in config.options.items()},
            "counts": {"aliases": len(listed("aliases", "list")), "redirects": len(listed("redirects", "list")),
                       "rewrites": len(listed("rewrites", "list")), "fastcgi_zones": len(fastcgi_zones()),
                       "upload_zones": len(listed("upload", "zones")), "proxy_zones": len(zones),
                       "proxy_backends": sum(len(zone.upstreams) for zone in zones),
                       "access_rules": len(listed("access_control", "rules")), "cache_enabled": enabled("cache"),
                       "custom_error_pages": enabled("error_pages")},
            "security": {"waf": enabled("waf"), "waf_mode": waf.settings.get("mode") if waf is not None else None,
                         "waf_packs": len(waf.settings.get("rule_paths", [])) if waf is not None else 0,
                         "active_defense": enabled("active_defense"), "riposte": enabled("riposte"),
                         "banned_active": banned, "auth_zones": auth_zones,
                         "security_headers": config.security.security_headers_enabled,
                         "csp_mode": config.security.csp_mode},
            "checks": {"errors": list(validate_config(config)),
                       "warnings": [c.message for c in detect_conflicts(config)]},
            "backups": {"count": len(backups),
                        "last_date": backups[-1].created_at.isoformat() if backups else None,
                        "last_scope": backups[-1].scope if backups else None,
                        "total_bytes": sum(meta.file_size_bytes or 0 for meta in backups)},
            "logs": {"dir": str(logs_dir), "total_bytes": logs_bytes},
        }
        detail: dict[str, Any] = {}
        if "zones" in details:
            detail["zones"] = {name: scrub(listed(name, key)) for name, key in (
                ("aliases", "list"), ("redirects", "list"), ("rewrites", "list"),
                ("upload", "zones"), ("access_control", "rules"), ("cache", "zones"))}
            detail["zones"]["fastcgi"] = scrub(fastcgi_zones())
        if "reverse_proxy" in details and option("reverse_proxy") is not None:
            detail["reverse_proxy"] = scrub(cast("Option", option("reverse_proxy")).settings)
        if "waf" in details and waf is not None:
            detail["waf"] = scrub({key: waf.settings.get(key) for key in ("mode", "rule_paths", "keyword_lists",
                                                                         "rate_limit", "exclusions", "inspect")})
        if "active_defense" in details:
            detail["active_defense"] = {name: scrub(cast("Option", option(name)).settings) if option(name) is not None else None
                                        for name in ("active_defense", "riposte")}
        if "logs_library" in details:
            detail["logs_library"] = [str(record.path) for record in self.build_log_library_repository().list_all()]
        if "options_settings" in details:
            detail["options_settings"] = {name: scrub(found.settings) for name, found in config.options.items()}
        if "audit" in details and self.audit_runner is not None:
            audit = self.audit_runner(config, self.config_file, root, self._filesystem, self._clock, service_name,
                                      False, False)
            detail["audit"] = [f"[{f.severity.value}] {f.rule_id} {f.rule_name} - {f.message}"
                               + "".join(f"\n    {line}" for line in f.detail_lines) for f in audit.findings]
        if detail:
            payload["details"] = detail
        return payload

    def list_backups(self) -> list[SnapshotMetadata]:
        return self.build_backup_metadata_store(self._backups_dir()).list_all()

    def delete_backup(self, snapshot_id: str) -> bool:
        backups_dir = self._backups_dir()
        metadata_store = self.build_backup_metadata_store(backups_dir)
        metadata = metadata_store.load(snapshot_id)
        if metadata is not None and metadata.file_path is not None:
            self.build_archive_store(backups_dir, private=True).delete_archive(Path(metadata.file_path))
        return metadata_store.delete(snapshot_id)
