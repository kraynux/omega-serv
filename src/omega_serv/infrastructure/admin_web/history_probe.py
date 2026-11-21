"""Sonde de l'historique (lots 7 et 9) : peu couteuse, appelee toutes les 10 s meme quand personne ne regarde.

- processeur : ecart des temps processeur (psutil.cpu_times), jamais psutil.cpu_percent, dont l'etat global est
  partage avec le tableau de bord ;
- memoire et swap : pourcentages utilises ; charge : os.getloadavg ;
- reseau : octets recus et envoyes cumules ; connexions TCP en cours et sockets ouverts : /proc/net/sockstat(6),
  quelques lignes, au lieu de parcourir toutes les connexions ;
- disque : octets lus et ecrits des disques physiques (ni partitions, ni volumes virtuels, qui compteraient deux
  fois) ; espace : partition de l'instance ;
- processus : nombre sur la machine ; processeur et memoire d'omega-serv (serveur et ses enfants, plus ce processus
  d'administration), temps processeur cumule PAR processus pour qu'un enfant qui part ne fasse pas reculer le total ;
- temperature du processeur et batterie : None quand la machine n'en a pas ;
- trafic des sites (lot 9b) : octets recus des visiteurs et envoyes, publies par les processus serveur des deux
  moteurs (traffic_reader.py) ;
- requetes : lignes ajoutees au journal d'acces, COMPTEES sans etre analysees (un compte d'octets « \\n » par bloc),
  a partir de la fin du fichier au premier releve ; rotation (autre fichier ou fichier raccourci) : on repart du
  debut du nouveau fichier ; au plus 64 Mo lus par releve, le reste au releve suivant.

Chaque mesure est independante : une mesure impossible vaut None, les autres restent."""
from __future__ import annotations

import os
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import psutil

from omega_serv.application.admin_web.stats_aggregator import StatsAggregator
from omega_serv.domain.admin_web.history import Counters

CHUNK = 1024 * 1024
MAX_READ_PER_SAMPLE = 64 * CHUNK
CPU_SENSORS = ("coretemp", "k10temp", "zenpower", "cpu_thermal", "cpu-thermal", "soc_thermal", "acpitz")
"""Capteurs du processeur, du plus precis au plus vague (acpitz : zone de la carte mere, en dernier recours)."""
CPU_LABELS = ("package", "tctl", "tdie", "cpu")


class LineCounter:
    def __init__(self, path: Callable[[], Path], sink: Callable[[list[bytes]], None] | None = None) -> None:
        self._path = path
        self._identity: tuple[int, int] | None = None
        self._offset = 0
        self.lines = 0
        self._sink = sink
        """Statistiques de trafic (etude modules, module 2) : recoit les lignes completes lues."""
        self._tail = b""

    def count(self) -> int | None:
        try:
            path = self._path()
            info = os.stat(path)
        except OSError:
            if self._identity is None:
                self._identity = (-1, -1)  # absent au premier releve : quand il apparait, tout compte depuis son debut
            return None
        identity = (info.st_dev, info.st_ino)
        if self._identity is None:
            self._identity, self._offset = identity, info.st_size  # premier releve : seulement la suite
            return self.lines
        if identity != self._identity or info.st_size < self._offset:
            self._identity, self._offset, self._tail = identity, 0, b""
        if info.st_size == self._offset:
            return self.lines
        try:
            with open(path, "rb") as handle:
                handle.seek(self._offset)
                remaining = min(info.st_size - self._offset, MAX_READ_PER_SAMPLE)
                while remaining > 0:
                    block = handle.read(min(CHUNK, remaining))
                    if not block:
                        break
                    self.lines += block.count(b"\n")
                    self._offset += len(block)
                    remaining -= len(block)
                    if self._sink is not None:
                        parts = (self._tail + block).split(b"\n")
                        self._tail = parts.pop()[-65536:]  # fin de ligne au bloc suivant ; jamais sans borne
                        if parts:
                            self._sink(parts)
        except OSError:
            return None
        return self.lines


class ProcessTreeCpu:
    """Temps processeur cumule d'un ensemble de processus. Chaque processus compte son ecart depuis le releve
    precedent ; un nouveau venu compte depuis son lancement s'il est ne apres le premier releve (sinon son passe
    entier gonflerait le premier point)."""

    def __init__(self) -> None:
        self._seen: dict[int, tuple[float, float]] = {}
        self._started: float | None = None
        self.total = 0.0

    def update(self, processes: list[psutil.Process]) -> tuple[float, int]:
        seen: dict[int, tuple[float, float]] = {}
        memory = 0
        for process in processes:
            try:
                with process.oneshot():
                    created = process.create_time()
                    times = process.cpu_times()
                    rss = process.memory_info().rss
            except (psutil.Error, OSError):
                continue
            used = times.user + times.system
            memory += rss
            before = self._seen.get(process.pid)
            if before is not None and before[0] == created:
                self.total += max(0.0, used - before[1])
            elif self._started is not None and created >= self._started:
                self.total += used
            seen[process.pid] = (created, used)
        if self._started is None:
            self._started = time.time()
        self._seen = seen
        return self.total, memory


def _optional(read: Callable[[], Any]) -> Any:
    try:
        return read()
    except Exception:  # noqa: BLE001 - mesure absente ou refusee sur cette machine : None, les autres restent
        return None


def _sockstat() -> tuple[int | None, int | None]:
    tcp: int | None = None
    sockets: int | None = None
    for name in ("/proc/net/sockstat", "/proc/net/sockstat6"):
        try:
            with open(name, encoding="ascii") as handle:
                lines = handle.read().splitlines()
        except OSError:
            continue
        for line in lines:
            label, _sep, rest = line.partition(":")
            fields = rest.split()
            if label in ("TCP", "TCP6") and len(fields) >= 2 and fields[0] == "inuse":
                tcp = (tcp or 0) + int(fields[1])
            elif label == "sockets" and len(fields) >= 2 and fields[0] == "used":
                sockets = int(fields[1])
    return tcp, sockets


def _disk_io() -> tuple[int | None, int | None]:
    disks = psutil.disk_io_counters(perdisk=True) or {}
    physical = [counters for name, counters in disks.items()
                if os.path.exists(f"/sys/block/{name.replace('/', '!')}/device")]
    if not physical:
        total = psutil.disk_io_counters()
        return (total.read_bytes, total.write_bytes) if total is not None else (None, None)
    return sum(c.read_bytes for c in physical), sum(c.write_bytes for c in physical)


def cpu_temperature(sensors: dict[str, list[Any]]) -> float | None:
    for name in CPU_SENSORS:
        entries = [entry for entry in sensors.get(name, []) if entry.current is not None]
        if not entries:
            continue
        labelled = [entry for entry in entries if (entry.label or "").lower().startswith(CPU_LABELS)]
        return float(max(entry.current for entry in (labelled or entries)))
    return None


def _battery() -> float | None:
    battery = psutil.sensors_battery()
    return float(battery.percent) if battery is not None else None


def _swap() -> float | None:
    swap = psutil.swap_memory()
    return float(swap.percent) if swap.total > 0 else None


class HistoryProbe:
    def __init__(self, access_log: Callable[[], Path], clock: Callable[[], float] = time.time, *,
                 instance_root: Path | None = None, server_pids: Callable[[], list[int]] = list,
                 traffic: Callable[[], tuple[int, int] | None] | None = None,
                 stats: StatsAggregator | None = None) -> None:
        self._stats = stats
        """Statistiques de trafic et compte des 5xx (etude modules, module 2) ; None : lignes seulement comptees."""
        self._lines = LineCounter(access_log, stats.feed if stats is not None else None)
        self._clock = clock
        self._instance_root = instance_root
        self._server_pids = server_pids
        self._tree = ProcessTreeCpu()
        self._traffic = traffic
        """Lot 9b : (recus, envoyes) cumules des processus serveur (TrafficTotals) ; None : pas de mesure."""

    def _omega_processes(self) -> list[psutil.Process]:
        found: dict[int, psutil.Process] = {}
        for pid in [*self._server_pids(), os.getpid()]:
            try:
                root = psutil.Process(pid)
                for process in [root, *root.children(recursive=True)]:
                    found.setdefault(process.pid, process)
            except (psutil.Error, OSError):
                continue
        return list(found.values())

    def capacities(self) -> dict[str, Any]:
        """Lot 9c (essai de l'auteur du 2026-11-17) : tailles totales pour « utilise / total · % » ; batterie :
        sur secteur, ou secondes restantes quand le systeme les donne."""
        found: dict[str, Any] = {"coeurs": psutil.cpu_count() or 1}
        memory = _optional(lambda: psutil.virtual_memory().total)
        if memory:
            found["memoire"] = int(memory)
        swap = _optional(lambda: psutil.swap_memory().total)
        if swap:
            found["swap"] = int(swap)
        root = self._instance_root
        disk = _optional(lambda: psutil.disk_usage(str(root)).total) if root is not None else None
        if disk:
            found["disque"] = int(disk)
        battery = _optional(psutil.sensors_battery)
        if battery is not None:
            left = battery.secsleft
            found["batterie"] = {
                "secteur": bool(battery.power_plugged),
                "restant": int(left) if isinstance(left, (int, float)) and 0 < left < 7 * 86400 else None}
        return found

    def read(self) -> Counters:
        times = psutil.cpu_times()
        idle = times.idle + getattr(times, "iowait", 0.0)
        total = sum(times)
        net = psutil.net_io_counters()
        tcp, sockets = _optional(_sockstat) or (None, None)
        disk_read, disk_write = _optional(_disk_io) or (None, None)
        root = self._instance_root
        serv = _optional(lambda: self._tree.update(self._omega_processes())) or (None, None)
        site = (_optional(self._traffic) if self._traffic is not None else None) or (None, None)
        return Counters(
            at=self._clock(), cpu_busy=total - idle, cpu_total=total, mem_percent=psutil.virtual_memory().percent,
            net_recv=net.bytes_recv, net_sent=net.bytes_sent, requests=self._lines.count(),
            swap_percent=_optional(_swap), load=_optional(os.getloadavg), tcp=tcp, sockets=sockets,
            disk_read=disk_read, disk_write=disk_write,
            disk_used=_optional(lambda: psutil.disk_usage(str(root)).percent) if root is not None else None,
            procs=_optional(lambda: len(psutil.pids())), serv_cpu=serv[0], serv_mem=serv[1],
            site_recv=site[0], site_sent=site[1],
            cpu_count=psutil.cpu_count() or 1,
            temp=_optional(lambda: cpu_temperature(psutil.sensors_temperatures())), battery=_optional(_battery),
            errors_5xx=self._stats.errors_5xx if self._stats is not None else None)
