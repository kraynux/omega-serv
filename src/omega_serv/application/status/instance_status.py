"""Instantane d'etat d'une instance (tableau de bord web, OMEGA-SERV_PLAN-DETAILLE_TABLEAU_DE_BORD_WEB.md, lot 1).

Ce que l'ecran « Etat & Ressources » calculait lui-meme, sorti en cas d'usage pour etre partage par le TUI, la CLI
et le futur processus d'administration web : un collecteur, `InstanceStatusCollector`, rend quatre instantanes de
donnees pures (aucune mise en forme, aucun libelle traduit, aucun widget) :

- `server_state()` : processus, service systeme, instances du registre, sauvegarde, configuration, moteur, type
  d'instance. Peut bloquer jusqu'a 10 s (gestionnaire de service degrade) : a appeler dans un fil de travail.
- `traffic()` : flux du journal d'acces (15 dernieres minutes relues a l'ouverture, puis lecture incrementale),
  alertes du WAF, IP bannies. Rapide.
- `system()` : ressources de la machine et du processus serveur (psutil : peut bloquer sur un /sys degrade, fil de
  travail), debit reseau et paquets par seconde entre deux releves.
- `backends()` : mesures en direct des backends de reverse proxy (route `/.omega-serv-admin/backends`), pour un
  reverse proxy ou une instance mixte.

Le collecteur garde l'etat qui doit survivre entre deux rafraichissements (position de lecture des journaux, releve
precedent du reseau, volume envoye deja compte) : un collecteur par ecran ou par client, jamais recree a chaque
rafraichissement."""
from __future__ import annotations

import time
from collections import deque
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Literal, Protocol

from omega_serv.application.config.load_config import load_config
from omega_serv.application.server.engine_status import EngineStatus
from omega_serv.application.services.manage_service import get_service_status
from omega_serv.application.services.pid_file import pid_file_status
from omega_serv.core.platform_info import is_process_running
from omega_serv.domain.config.entities import OmegaServConfig
from omega_serv.domain.config.option import KNOWN_OPTION_NAMES
from omega_serv.domain.instances.entities import InstanceEntry
from omega_serv.domain.logging.access_log_parser import parse_combined_log_line
from omega_serv.domain.logging.live_traffic_stats import LiveTrafficBuffer, LiveTrafficStats
from omega_serv.domain.persistence.snapshots import SnapshotMetadata
from omega_serv.domain.routing.proxy_backend_traffic import (
    BackendTraffic,
    InstanceKind,
    instance_kind,
)
from omega_serv.domain.security.riposte.events import parse_waf_alert_line
from omega_serv.domain.security.waf.config import parse_waf_config
from omega_serv.domain.services.entities import ServiceStatus
from omega_serv.ports.blocklist_port import BlocklistPort
from omega_serv.ports.clock_port import ClockPort
from omega_serv.ports.configuration_port import ConfigurationPort
from omega_serv.ports.file_access_port import FileAccessPort
from omega_serv.ports.filesystem_port import FilesystemPort
from omega_serv.ports.instance_registry_port import InstanceRegistryPort
from omega_serv.ports.live_tail_port import LiveTailPort
from omega_serv.ports.service_manager_port import ServiceManagerPort
from omega_serv.ports.settings_store import SettingsStore

HISTORY = timedelta(minutes=15)
"""Relu a l'ouverture : le flux n'est jamais vide au depart."""
HISTORY_MAX_BYTES = 4 * 1024 * 1024
"""Lecture de la fin du journal bornee : jamais un gros access.log lu en entier."""
SPARK_SAMPLES = 60
"""Historique des paquets/s : 60 releves, soit 2 min au rythme de 2 s."""
DEFAULT_SERVICE_NAME = "omega-serv"
SERVICE_NAME_KEY = "service_name"
"""Meme cle que l'ecran Service (var/settings.json) : jamais un nom fige (renommage du service)."""
ADMIN_BACKENDS_PATH = "/.omega-serv-admin/backends"
KINDS_WITH_BACKENDS: tuple[InstanceKind, ...] = ("proxy", "mixed")

AdminRunner = Callable[[int, str, str], Awaitable[tuple[int, dict | None] | None]]


class StatusSources(Protocol):
    """Ce dont le collecteur a besoin (le conteneur de dependances le fournit tel quel)."""

    @property
    def project_root(self) -> Path: ...
    @property
    def filesystem(self) -> FilesystemPort: ...
    @property
    def file_access(self) -> FileAccessPort: ...
    @property
    def configuration(self) -> ConfigurationPort: ...
    @property
    def config_file(self) -> Path: ...
    @property
    def clock(self) -> ClockPort: ...
    @property
    def settings_store(self) -> SettingsStore: ...
    @property
    def instance_registry(self) -> InstanceRegistryPort: ...
    @property
    def service_manager_factory(self) -> Callable[[], ServiceManagerPort | None] | None: ...
    @property
    def blocklist_port_factory(self) -> Callable[[OmegaServConfig, FilesystemPort, Path, ClockPort], BlocklistPort] | None: ...
    @property
    def admin_request_runner(self) -> AdminRunner | None: ...
    def build_live_tail_reader(self, path: Path) -> LiveTailPort: ...
    def access_log_sent_bytes(self, path: Path, since: datetime, offset: int | None) -> tuple[int, int]: ...
    def engine_status(self, config: OmegaServConfig) -> EngineStatus: ...
    def list_backups(self) -> list[SnapshotMetadata]: ...
    def collect_system_stats(self) -> dict[str, Any]: ...
    def collect_server_stats(self, pid: int | None, port: int) -> dict[str, Any]: ...


# ---------------------------------------------------------------------------------------------- instantanes


@dataclass(frozen=True)
class ProcessSnapshot:
    pid: int | None
    """PID lu dans var/run/omega-serv.pid (None : pas de fichier, ou illisible)."""
    running: bool
    unreadable: bool
    """Fichier PID present mais illisible (normal juste apres l'installation du service, avant reconnexion)."""


@dataclass(frozen=True)
class ServiceSnapshot:
    manager_found: bool
    name: str
    status: ServiceStatus | None = None
    error: str | None = None
    """Message deja traduit du gestionnaire de service (delai depasse, unite introuvable...)."""


@dataclass(frozen=True)
class InstanceRow:
    name: str
    current: bool
    pid: int | None
    """PID si l'instance tourne, sinon None."""
    unreadable: bool


@dataclass(frozen=True)
class InstancesSnapshot:
    count: int
    current_name: str
    rows: tuple[InstanceRow, ...]
    """La courante d'abord, puis celles en marche, puis les autres (l'affichage en garde les premieres)."""


@dataclass(frozen=True)
class ConfigSnapshot:
    profile: str
    bind: str
    port: int
    tls_enabled: bool
    tls_mode: str
    kind: InstanceKind
    engine: EngineStatus
    enabled_options: tuple[str, ...]
    known_options: int


@dataclass(frozen=True)
class ServerStateSnapshot:
    process: ProcessSnapshot
    service: ServiceSnapshot
    instances: InstancesSnapshot
    latest_backup: datetime | None
    backup_count: int
    config: ConfigSnapshot | None
    config_errors: tuple[str, ...] = ()
    """Erreurs de chargement de la configuration (config = None alors)."""
    backups_unreadable: bool = False
    """var/backups illisible pour le compte qui lit (le processus d'administration tourne sous le compte du service, et
    les sauvegardes restent reservees a leur proprietaire) : seule cette ligne le dit, jamais tout le releve."""


@dataclass(frozen=True)
class TrafficSnapshot:
    stats: LiveTrafficStats
    since: datetime
    """Debut de la fenetre relue a l'ouverture."""
    waf_active: bool
    waf_counts: dict[str, int]
    """attack, blocklist_hit, rate_limited depuis `since`."""


@dataclass(frozen=True)
class SystemSnapshot:
    machine: dict[str, Any]
    """Releve psutil de la machine (infrastructure/probe/system_stats.py::collect_system_stats)."""
    server: dict[str, Any]
    """Releve du processus serveur, plus `pid` et `port`."""
    net_rate: tuple[float, float] | None
    """(octets/s recus, octets/s envoyes) depuis le releve precedent ; None au premier releve."""
    packets: dict[str, tuple[float, ...]]
    """Paquets/s TCP et UDP des derniers releves (au plus SPARK_SAMPLES)."""
    sent_total: int | None
    """Octets de reponse de l'access log depuis le demarrage du serveur (None : pas encore calcule)."""


BackendsProblem = Literal["stopped", "refused", "unexpected"]


@dataclass(frozen=True)
class BackendsSnapshot:
    kind: InstanceKind | None
    """None : configuration illisible."""
    rows: tuple[BackendTraffic, ...] | None = None
    """None : pas de mesure (instance sans reverse proxy, ou `problem`)."""
    problem: BackendsProblem | None = None
    status: int | None = None
    """Statut HTTP de la reponse quand `problem` = « unexpected »."""


# ---------------------------------------------------------------------------------------------- collecteur


@dataclass
class _NetworkHistory:
    previous_bytes: tuple[float, int, int] | None = None
    previous_packets: tuple[float, int, int] | None = None
    packets: dict[str, deque[float]] = field(default_factory=lambda: {
        "tcp": deque(maxlen=SPARK_SAMPLES), "udp": deque(maxlen=SPARK_SAMPLES)})


class InstanceStatusCollector:
    def __init__(self, sources: StatusSources, *, monotonic: Callable[[], float] = time.monotonic) -> None:
        self._sources = sources
        self._monotonic = monotonic
        self._manager: ServiceManagerPort | None = None
        self._since: datetime | None = None
        self._buffer: LiveTrafficBuffer | None = None
        self._tail: LiveTailPort | None = None
        self._waf_tail: LiveTailPort | None = None
        self._waf_counts = {"attack": 0, "blocklist_hit": 0, "rate_limited": 0}
        self._network = _NetworkHistory()
        self._sent_since: datetime | None = None
        self._sent_offset: int | None = None
        self._sent_total: int | None = None
        self._pending_sent_since: datetime | None = None

    # -------------------------------------------------------------------------------------- ouverture
    def open(self) -> None:
        """Gestionnaire de service, 15 dernieres minutes du journal d'acces et des alertes du WAF, lecteurs
        incrementaux. Une seule fois, a l'ouverture de l'ecran (ou du client)."""
        factory = self._sources.service_manager_factory
        self._manager = factory() if factory is not None else None
        self._since = self._sources.clock.now() - HISTORY
        self._buffer = LiveTrafficBuffer(self._since)
        access_log = self.access_log_path()
        for line in self._history_lines(access_log):
            entry = parse_combined_log_line(line)
            if entry is not None and entry.timestamp >= self._since:
                self._buffer.add(entry)
        self._tail = self._sources.build_live_tail_reader(access_log)
        waf_log = self._waf_alert_log_path()
        if waf_log is not None:
            self._count_waf_alerts(self._history_lines(waf_log), self._since)
            self._waf_tail = self._sources.build_live_tail_reader(waf_log)

    def _config(self) -> OmegaServConfig | None:
        result = load_config(self._sources.configuration, self._sources.config_file)
        return result.config if result.success else None

    def access_log_path(self) -> Path:
        config = self._config()
        if config is None:
            return self._sources.project_root / "var" / "log" / "access.log"
        return self._sources.project_root / config.logs.access

    def _waf_alert_log_path(self) -> Path | None:
        config = self._config()
        option = config.options.get("waf") if config is not None else None
        if option is None or not option.enabled:
            return None
        return self._sources.project_root / parse_waf_config(option.settings).logging.path

    def _history_lines(self, path: Path) -> list[str]:
        try:
            return self._sources.file_access.read_tail_lines(path, HISTORY_MAX_BYTES)
        except OSError:
            return []

    def _count_waf_alerts(self, lines: list[str], since: datetime | None = None) -> None:
        for line in lines:
            event = parse_waf_alert_line(line).event
            if event is not None and (since is None or event.timestamp >= since) and event.kind in self._waf_counts:
                self._waf_counts[event.kind] += 1

    # -------------------------------------------------------------------------------------- flux
    def traffic(self) -> TrafficSnapshot:
        """Lignes ajoutees depuis le releve precedent, puis statistiques de la fenetre. `open()` d'abord."""
        assert self._buffer is not None and self._since is not None  # open() d abord
        if self._tail is not None:
            for line in self._tail.read_new_lines():
                entry = parse_combined_log_line(line)
                if entry is not None:
                    self._buffer.add(entry)
        if self._waf_tail is not None:
            self._count_waf_alerts(self._waf_tail.read_new_lines())
        return TrafficSnapshot(self._buffer.get_stats(self._sources.clock.now()), self._since,
                               self._waf_tail is not None, dict(self._waf_counts))

    def banned_counts(self) -> tuple[int, int] | None:
        """(IP en liste de blocage en vigueur, dont posees par RIPOSTE) ; None si inconnu ou WAF inactif. Lit un
        fichier : fil de travail (l'ecran l'appelle avec `server_state()`)."""
        factory = self._sources.blocklist_port_factory
        config = self._config()
        if factory is None or config is None:
            return None
        option = config.options.get("waf")
        if option is None or not option.enabled:
            return None
        sources = self._sources
        entries = factory(config, sources.filesystem, sources.project_root, sources.clock).list_entries()
        now = sources.clock.now().isoformat()
        active = [e for e in entries if e.expires_at is None or e.expires_at > now]
        return len(active), sum(1 for e in active if e.source == "riposte")

    # -------------------------------------------------------------------------------------- etat du serveur
    def _pid_path(self, root: Path | None = None) -> Path:
        return (root or self._sources.project_root) / "var" / "run" / "omega-serv.pid"

    def process(self) -> ProcessSnapshot:
        pid, unreadable = pid_file_status(self._sources.filesystem, self._pid_path())
        return ProcessSnapshot(pid, pid is not None and is_process_running(pid), unreadable)

    def service(self) -> ServiceSnapshot:
        name = self._sources.settings_store.get(SERVICE_NAME_KEY, "") or DEFAULT_SERVICE_NAME
        if self._manager is None:
            return ServiceSnapshot(False, name)
        result = get_service_status(self._manager, name)
        if isinstance(result, ServiceStatus):
            return ServiceSnapshot(True, name, status=result)
        return ServiceSnapshot(True, name, error=result.message)

    def instances(self) -> InstancesSnapshot:
        filesystem = self._sources.filesystem
        current_path = filesystem.resolve_real_path(self._sources.project_root)
        entries = self._sources.instance_registry.load()
        current = next((e for e in entries if e.path == current_path), None)
        if current is None:  # instance jamais inscrite au registre (installation principale) : elle compte quand meme
            current = InstanceEntry(current_path.name, current_path, "", 0, "", self._sources.clock.now())
            entries = [current, *entries]
        rows = []
        for entry in entries:
            pid, unreadable = pid_file_status(filesystem, self._pid_path(entry.path))
            running = pid is not None and is_process_running(pid)
            rows.append(((entry is not current, not running),
                         InstanceRow(entry.name, entry is current, pid if running else None, unreadable)))
        rows.sort(key=lambda row: row[0])
        return InstancesSnapshot(len(entries), current.name, tuple(row for _key, row in rows))

    def server_state(self) -> ServerStateSnapshot:
        """Peut bloquer (gestionnaire de service) : fil de travail."""
        try:
            backups = self._sources.list_backups()
            unreadable = False
        except PermissionError:
            backups, unreadable = [], True
        latest = backups[0].created_at if backups else None
        result = load_config(self._sources.configuration, self._sources.config_file)
        common: dict[str, Any] = {"process": self.process(), "service": self.service(), "instances": self.instances(),
                  "latest_backup": latest, "backup_count": len(backups), "backups_unreadable": unreadable}
        if not result.success or result.config is None:
            return ServerStateSnapshot(config=None, config_errors=tuple(result.errors), **common)
        config = result.config
        return ServerStateSnapshot(config=ConfigSnapshot(
            profile=str(config.profile), bind=config.server.bind, port=config.server.port,
            tls_enabled=config.tls.enabled, tls_mode=str(config.tls.mode), kind=instance_kind(config),
            engine=self._sources.engine_status(config),
            enabled_options=tuple(sorted(name for name, option in config.options.items() if option.enabled)),
            known_options=len(KNOWN_OPTION_NAMES)), **common)

    # -------------------------------------------------------------------------------------- ressources
    def system(self) -> SystemSnapshot:
        """psutil peut bloquer sur un /sys degrade : fil de travail."""
        machine = self._sources.collect_system_stats()
        self._record_packets(machine)
        net_rate = self._record_network(machine)
        return SystemSnapshot(machine, self._server_stats(), net_rate,
                              {key: tuple(values) for key, values in self._network.packets.items()},
                              self._sent_total)

    def _server_stats(self) -> dict[str, Any]:
        pid, _unreadable = pid_file_status(self._sources.filesystem, self._pid_path())
        if pid is not None and not is_process_running(pid):
            pid = None
        config = self._config()
        port = config.server.port if config is not None else 0
        stats = self._sources.collect_server_stats(pid, port)
        stats["pid"], stats["port"] = pid, port
        if stats.get("running"):
            since = (self._sources.clock.now() - timedelta(seconds=stats["uptime_seconds"])).replace(microsecond=0)
            if self._sent_since is not None and abs((since - self._sent_since).total_seconds()) <= 2:
                since = self._sent_since  # meme demarrage (arrondi de la duree) : on garde la reprise
            self._pending_sent_since = since
        return stats

    def _record_packets(self, machine: dict[str, Any]) -> None:
        packets = machine.get("packets")
        if packets is None:
            return
        now = self._monotonic()
        previous, self._network.previous_packets = self._network.previous_packets, (now, packets[0], packets[1])
        if previous is None or now <= previous[0]:
            return
        elapsed = now - previous[0]
        self._network.packets["tcp"].append(max(0, packets[0] - previous[1]) / elapsed)
        self._network.packets["udp"].append(max(0, packets[1] - previous[2]) / elapsed)

    def _record_network(self, machine: dict[str, Any]) -> tuple[float, float] | None:
        """Debit par seconde entre deux releves (psutil donne des totaux depuis le demarrage de la machine)."""
        now, received, sent = self._monotonic(), int(machine["net_bytes_recv"]), int(machine["net_bytes_sent"])
        previous, self._network.previous_bytes = self._network.previous_bytes, (now, received, sent)
        if previous is None or now <= previous[0]:
            return None
        elapsed = now - previous[0]
        return max(0, received - previous[1]) / elapsed, max(0, sent - previous[2]) / elapsed

    @property
    def pending_sent_since(self) -> datetime | None:
        """Demarrage du serveur releve par `system()` : le volume envoye se compte a partir de la."""
        return self._pending_sent_since

    @property
    def sent_total(self) -> int | None:
        return self._sent_total

    def update_sent_bytes(self, since: datetime) -> None:
        """Volume des reponses depuis `since` : la premiere lecture d'un gros access log peut durer (fil de travail
        a part), les suivantes ne lisent que les nouvelles lignes."""
        if since != self._sent_since:  # nouveau demarrage du serveur : on repart de zero
            self._sent_since, self._sent_offset, self._sent_total = since, None, None
        added, self._sent_offset = self._sources.access_log_sent_bytes(self.access_log_path(), since, self._sent_offset)
        self._sent_total = (self._sent_total or 0) + added

    # -------------------------------------------------------------------------------------- backends
    async def backends(self) -> BackendsSnapshot:
        """Type d'instance, puis mesures des backends par l'administration (reverse proxy ou mixte seulement)."""
        config = self._config()
        if config is None:
            return BackendsSnapshot(None)
        kind = instance_kind(config)
        if kind not in KINDS_WITH_BACKENDS:
            return BackendsSnapshot(kind)
        runner = self._sources.admin_request_runner
        result = await runner(config.server.port, "GET", ADMIN_BACKENDS_PATH) if runner is not None else None
        if result is None:
            return BackendsSnapshot(kind, problem="stopped")
        status, body = result
        if status == 403:
            return BackendsSnapshot(kind, problem="refused", status=status)
        if status != 200 or not isinstance(body, dict) or not isinstance(body.get("backends"), list):
            return BackendsSnapshot(kind, problem="unexpected", status=status)
        rows = [BackendTraffic.from_dict(row) for row in body["backends"] if isinstance(row, dict)]
        return BackendsSnapshot(kind, rows=tuple(row for row in rows if row is not None))
