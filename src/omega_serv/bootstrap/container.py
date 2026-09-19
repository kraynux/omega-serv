"""Racine de composition des dependances (charte §2.3).

Seul point du projet ou les adaptateurs concrets d'infrastructure/ sont
instancies directement - tout le reste du code (application/,
interfaces/) ne recoit que des ports. S'enrichira au fil des phases
(port de service systemd en Phase 9, port WAF en Phase 5, etc.) sans
que les couches superieures aient a changer."""
from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any

from omega_lib.infrastructure.terminal.detector import SystemTerminalDetector
from omega_lib.theme.policies import Palette

from omega_serv.bootstrap.paths import INSTANCE_REGISTRY_PATH, PROJECT_ROOT
from omega_serv.infrastructure.auth.auth_zones_repository import JsonAuthZonesRepository
from omega_serv.infrastructure.auth.users_repository import JsonUsersRepository
from omega_serv.infrastructure.clock.system_clock import SystemClock
from omega_serv.infrastructure.config.json_config_repository import JsonConfigRepository
from omega_serv.infrastructure.config.json_settings_store import JsonSettingsStore
from omega_serv.infrastructure.config.profile_repository import FileProfileRepository
from omega_serv.infrastructure.filesystem.local_filesystem import LocalFilesystem
from omega_serv.infrastructure.instances.json_instance_registry import JsonInstanceRegistry
from omega_serv.infrastructure.logging.file_line_logger import FileLineLogger
from omega_serv.ports.capability_scanner_port import CapabilityScannerPort
from omega_serv.ports.clock_port import ClockPort
from omega_serv.ports.configuration_port import ConfigurationPort
from omega_serv.ports.filesystem_port import FilesystemPort
from omega_serv.ports.instance_registry_port import InstanceRegistryPort
from omega_serv.ports.live_tail_port import LiveTailPort
from omega_serv.ports.logger_port import LoggerPort
from omega_serv.ports.profile_repository_port import ProfileRepositoryPort
from omega_serv.ports.service_manager_port import ServiceManagerPort
from omega_serv.ports.settings_store import SettingsStore
from omega_serv.ports.terminal_detector import TerminalDetector

if TYPE_CHECKING:
    from omega_serv.application.logs.rotate_log import RotateLogResult
    from omega_serv.application.persistence.create_backup import BackupResult
    from omega_serv.application.persistence.restore_backup import RestoreResult
    from omega_serv.application.security.simulate_waf_request import WafSimulationReport
    from omega_serv.application.server.simulate_request import SimulationReport
    from omega_serv.application.server.start_server import ActiveDefenseCollaborators
    from omega_serv.core.capability import Capability
    from omega_serv.domain.config.entities import OmegaServConfig
    from omega_serv.domain.logging.stats import LogStatsSummary
    from omega_serv.domain.persistence.backup import BackupRequest
    from omega_serv.domain.persistence.snapshots import SnapshotMetadata
    from omega_serv.domain.security.active_defense.entities import ExportResult, Incident
    from omega_serv.domain.security.audit.entities import AuditResult
    from omega_serv.infrastructure.logging.rotation_automation_store import RotationAutomationStore
    from omega_serv.infrastructure.persistence.backup_metadata_store import BackupMetadataStore
    from omega_serv.infrastructure.storage.files.archive_store import ArchiveStore
    from omega_serv.ports.auth_zones_repository_port import AuthZonesRepositoryPort
    from omega_serv.ports.blocklist_port import BlocklistPort
    from omega_serv.ports.certificate_tool_port import CertificateToolPort
    from omega_serv.ports.process_runner_port import ProcessRunnerPort
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
        waf_test_runner: Callable[
            [str, str, str, str, str, OmegaServConfig, FilesystemPort, Path, ClockPort], WafSimulationReport | None
        ] | None = None,
        blocklist_port_factory: Callable[[OmegaServConfig, FilesystemPort, Path, ClockPort], BlocklistPort] | None = None,
        active_defense_collaborators_factory: Callable[
            [OmegaServConfig, Path], ActiveDefenseCollaborators | None
        ] | None = None,
        ioc_export_runner: Callable[[Incident, str, Path, FilesystemPort], ExportResult | None] | None = None,
        incident_report_export_runner: Callable[[Incident, Path, FilesystemPort], ExportResult] | None = None,
        certificate_tool_factory: Callable[[], CertificateToolPort] | None = None,
        acme_client_factory: Callable[[], ProcessRunnerPort] | None = None,
        lnav_runner: Callable[[tuple[Path, ...], Palette, str, str], str | None] | None = None,
        export_capabilities_html_fn: Callable[[Sequence[Capability], str], str] | None = None,
        export_log_archives_html_fn: Callable[[Sequence[dict], str], str] | None = None,
        export_guide_html_fn: Callable[[Sequence[dict], Sequence[dict], str], str] | None = None,
        serve_foreground_runner: Callable[[Path, DependencyContainer], Awaitable[int]] | None = None,
        create_instance_runner: Callable[
            [Path, str, Path, str, int, str, FilesystemPort, InstanceRegistryPort, ClockPort,
             Callable[[int, int, str], None] | None],
            str | None,
        ] | None = None,
        systemd_unit_dir: Path = Path("/etc/systemd/system"),
        instance_registry_path: Path = INSTANCE_REGISTRY_PATH,
    ):
        self._service_manager_factory = service_manager_factory
        self._config_check_runner = config_check_runner
        self._audit_runner = audit_runner
        self._simulate_request_runner = simulate_request_runner
        self._waf_test_runner = waf_test_runner
        self._blocklist_port_factory = blocklist_port_factory
        self._active_defense_collaborators_factory = active_defense_collaborators_factory
        self._ioc_export_runner = ioc_export_runner
        self._incident_report_export_runner = incident_report_export_runner
        self._certificate_tool_factory = certificate_tool_factory
        self._acme_client_factory = acme_client_factory
        self._lnav_runner = lnav_runner
        self._create_instance_runner = create_instance_runner
        self._export_capabilities_html_fn = export_capabilities_html_fn
        self._export_log_archives_html_fn = export_log_archives_html_fn
        self._export_guide_html_fn = export_guide_html_fn
        self._serve_foreground_runner = serve_foreground_runner
        self._project_root = project_root
        self._systemd_unit_dir = systemd_unit_dir
        self._filesystem: FilesystemPort = LocalFilesystem()
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
    def waf_test_runner(
        self,
    ) -> Callable[
        [str, str, str, str, str, OmegaServConfig, FilesystemPort, Path, ClockPort], WafSimulationReport | None
    ] | None:
        return self._waf_test_runner

    @property
    def blocklist_port_factory(self) -> Callable[[OmegaServConfig, FilesystemPort, Path, ClockPort], BlocklistPort] | None:
        return self._blocklist_port_factory

    @property
    def active_defense_collaborators_factory(
        self,
    ) -> Callable[[OmegaServConfig, Path], ActiveDefenseCollaborators | None] | None:
        return self._active_defense_collaborators_factory

    @property
    def ioc_export_runner(self) -> Callable[[Incident, str, Path, FilesystemPort], ExportResult | None] | None:
        return self._ioc_export_runner

    @property
    def incident_report_export_runner(self) -> Callable[[Incident, Path, FilesystemPort], ExportResult] | None:
        return self._incident_report_export_runner

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
        return JsonUsersRepository(self._filesystem, auth_file)

    def build_auth_zones_repository(self, auth_zones_file: Path) -> AuthZonesRepositoryPort:
        return JsonAuthZonesRepository(self._filesystem, auth_zones_file)

    def build_capability_scanner(self, configured_port: int, fastcgi_socket: Path | None) -> CapabilityScannerPort:
        from omega_serv.infrastructure.probe.scanner import SystemCapabilityScanner

        return SystemCapabilityScanner(self._project_root, self._filesystem, configured_port, fastcgi_socket)

    def build_live_tail_reader(self, path: Path) -> LiveTailPort:
        from omega_serv.infrastructure.logging.live_tail_reader import LiveTailReader

        return LiveTailReader(path)

    def collect_system_stats(self) -> dict[str, Any]:
        from omega_serv.infrastructure.probe.system_stats import collect_system_stats

        return collect_system_stats()

    def build_archive_store(self, base_dir: Path) -> ArchiveStore:
        from omega_serv.infrastructure.storage.files.archive_store import ArchiveStore

        return ArchiveStore(base_dir)

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

    def export_capabilities_html(self, capabilities: Sequence[Capability], theme_name: str) -> str | None:
        if self._export_capabilities_html_fn is None:
            return None
        return self._export_capabilities_html_fn(capabilities, theme_name)

    def export_log_archives_html(self, archives: Sequence[dict], theme_name: str) -> str | None:
        if self._export_log_archives_html_fn is None:
            return None
        return self._export_log_archives_html_fn(archives, theme_name)

    def export_guide_html(self, screen_guides: Sequence[dict], faq_entries: Sequence[dict], theme_name: str) -> str | None:
        if self._export_guide_html_fn is None:
            return None
        return self._export_guide_html_fn(screen_guides, faq_entries, theme_name)

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


    def _backups_dir(self) -> Path:
        return self._project_root / "var" / "backups" / "config-snapshots"

    def build_backup_metadata_store(self, base_dir: Path) -> BackupMetadataStore:
        from omega_serv.infrastructure.persistence.backup_metadata_store import BackupMetadataStore

        return BackupMetadataStore(base_dir)

    def create_backup(self, request: BackupRequest, config: OmegaServConfig, config_file: Path) -> BackupResult:
        from omega_serv.application.persistence.create_backup import create_backup

        backups_dir = self._backups_dir()
        archive_store = self.build_archive_store(backups_dir)
        metadata_store = self.build_backup_metadata_store(backups_dir)
        return create_backup(request, config, self._project_root, config_file, archive_store, metadata_store, self._clock)

    def restore_backup(self, snapshot_id: str) -> RestoreResult:
        from omega_serv.application.persistence.restore_backup import restore_backup

        backups_dir = self._backups_dir()
        archive_store = self.build_archive_store(backups_dir)
        metadata_store = self.build_backup_metadata_store(backups_dir)
        return restore_backup(snapshot_id, self._project_root, archive_store, metadata_store)

    def list_backups(self) -> list[SnapshotMetadata]:
        return self.build_backup_metadata_store(self._backups_dir()).list_all()

    def delete_backup(self, snapshot_id: str) -> bool:
        backups_dir = self._backups_dir()
        metadata_store = self.build_backup_metadata_store(backups_dir)
        metadata = metadata_store.load(snapshot_id)
        if metadata is not None and metadata.file_path is not None:
            self.build_archive_store(backups_dir).delete_archive(Path(metadata.file_path))
        return metadata_store.delete(snapshot_id)
