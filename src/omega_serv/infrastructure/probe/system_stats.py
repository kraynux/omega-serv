"""Statistiques systeme (CPU/RAM/disque/reseau...) via psutil (retour
utilisateur 2026-09-09, ecran "Etat & Ressources") - transpose depuis
omega-fire (interfaces/cli/renderers/dashboard.py::collect_os_stats(),
integralement generique - aucune partie de cette fonction n'etait
specifique au pare-feu, seule la fonction elle-meme vivait dans un
module dashboard "melant" systeme+pare-feu chez fire).

I/O reelle (psutil, /proc/net/route, /etc/resolv.conf) : vit en
infrastructure/, jamais construit ailleurs. `psutil` lit /proc
directement sur Linux (jamais de subprocess), donc construit
directement dans bootstrap/container.py - meme regime que
build_capability_scanner (verifie via lint-imports, pas suppose)."""
from __future__ import annotations

import socket
import struct
import time
from pathlib import Path
from typing import Any

import psutil

_PROC_NET_ROUTE = Path("/proc/net/route")
_RESOLV_CONF = Path("/etc/resolv.conf")
_SYS_CLASS_NET = Path("/sys/class/net")
_PROC_NET_SNMP = Path("/proc/net/snmp")


def _detect_default_gateway() -> str:
    """Porte depuis omega-fire (infrastructure/probe/network_probe.py::
    get_default_gateway) - lecture directe de /proc/net/route (Linux
    uniquement), jamais un appel a `ip route` en subprocess. Retourne
    "" si indisponible (fichier absent, aucune route par defaut,
    systeme non-Linux) - a traiter comme "detection indisponible",
    jamais comme "aucune passerelle"."""
    try:
        if not _PROC_NET_ROUTE.is_file():
            return ""
        with _PROC_NET_ROUTE.open(encoding="utf-8") as f:
            next(f)  # ligne d'en-tete
            for line in f:
                fields = line.split()
                if len(fields) >= 3 and fields[1] == "00000000":
                    return socket.inet_ntoa(struct.pack("<L", int(fields[2], 16)))
        return ""
    except (OSError, ValueError, IndexError):
        return ""


def _detect_default_interface() -> str:
    """Interface de la route par defaut de plus petite metrique (/proc/net/route) : celle qui sort
    reellement quand l'ethernet et le wifi sont branches ensemble. "" si indisponible."""
    best: tuple[int, str] | None = None
    try:
        with _PROC_NET_ROUTE.open(encoding="utf-8") as f:
            next(f)  # ligne d'en-tete
            for line in f:
                fields = line.split()
                if len(fields) >= 7 and fields[1] == "00000000":
                    candidate = (int(fields[6]), fields[0])
                    best = candidate if best is None or candidate < best else best
    except (OSError, ValueError, StopIteration):
        return ""
    return best[1] if best is not None else ""


def _physical_links(addresses: dict[str, str]) -> list[dict[str, Any]]:
    """Cartes reseau physiques (ethernet, wifi) : celles qui ont un peripherique dans /sys/class/net -
    jamais lo, tailscale, docker, ponts ou veth (2026-11-05, ecran Etat & Ressources)."""
    try:
        stats = psutil.net_if_stats()
    except (psutil.Error, AttributeError, OSError):
        stats = {}
    links = []
    for name in sorted(stats):
        sys_dir = _SYS_CLASS_NET / name
        if not (sys_dir / "device").exists():
            continue
        wifi = (sys_dir / "wireless").exists() or (sys_dir / "phy80211").exists()
        links.append({"name": name, "kind": "wifi" if wifi else "ethernet", "up": stats[name].isup,
                      "speed": stats[name].speed, "ip": addresses.get(name, "")})
    return links


def _read_packet_totals() -> tuple[int, int] | None:
    """Paquets TCP (segments) et UDP (datagrammes), recus + envoyes, depuis le demarrage (/proc/net/snmp).
    Le noyau ne compte pas les OCTETS par protocole : le graphique TCP/UDP est donc en paquets/s."""
    try:
        rows: dict[str, dict[str, int]] = {}
        lines = _PROC_NET_SNMP.read_text(encoding="utf-8").splitlines()
        for header, values in zip(lines[::2], lines[1::2], strict=False):
            name, *keys = header.split()
            rows[name] = dict(zip(keys, (int(v) for v in values.split()[1:]), strict=False))
        tcp, udp = rows["Tcp:"], rows["Udp:"]
        return tcp["InSegs"] + tcp["OutSegs"], udp["InDatagrams"] + udp["OutDatagrams"]
    except (OSError, KeyError, ValueError):
        return None


def _detect_outbound_ip() -> str:
    """Connexion UDP factice (aucun paquet reellement envoye, UDP ne
    fait pas de handshake) - demande juste au noyau quelle IP locale
    serait utilisee pour joindre cette destination, fonctionne meme
    hors ligne. C'est l'IP de sortie de la machine (LAN derriere un
    routeur le cas echeant), jamais la veritable IP publique internet."""
    try:
        probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            probe.connect(("8.8.8.8", 80))
            return str(probe.getsockname()[0])
        finally:
            probe.close()
    except OSError:
        return "N/A"


def collect_system_stats() -> dict[str, Any]:
    cpu_percent = psutil.cpu_percent(interval=0)
    mem = psutil.virtual_memory()
    swap = psutil.swap_memory()
    load_1, load_5, load_15 = psutil.getloadavg()
    num_processes = len(psutil.pids())
    uptime_seconds = time.time() - psutil.boot_time()
    disk = psutil.disk_usage("/")
    net_io = psutil.net_io_counters()

    temps: dict[str, float] = {}
    try:
        sensors = psutil.sensors_temperatures()
        if sensors:
            for name, entries in sensors.items():
                for entry in entries:
                    temps[entry.label or name] = entry.current
    except (psutil.Error, AttributeError, NotImplementedError):
        pass

    fans: dict[str, float] = {}
    try:
        fan_sensors = psutil.sensors_fans()
        if fan_sensors:
            for name, fan_entries in fan_sensors.items():
                for fan_entry in fan_entries:
                    fans[fan_entry.label or name] = fan_entry.current
    except (psutil.Error, AttributeError, NotImplementedError):
        pass

    try:
        tcp_conns = psutil.net_connections(kind="tcp")
        tcp_established = len([c for c in tcp_conns if c.status == "ESTABLISHED"])
    except (psutil.Error, AttributeError):
        tcp_established = 0

    interfaces: list[dict[str, str]] = []
    try:
        for iface, addrs in psutil.net_if_addrs().items():
            for addr in addrs:
                if addr.family == socket.AF_INET:
                    interfaces.append({"name": iface, "ip": addr.address})
    except (psutil.Error, AttributeError):
        pass

    dns: list[str] = []
    try:
        with _RESOLV_CONF.open(encoding="utf-8") as f:
            for line in f:
                if line.startswith("nameserver"):
                    # Retour utilisateur 2026-09-26 : IndexError reel en
                    # usage (Archcraft) - une ligne "nameserver" sans
                    # adresse a la suite (resolv.conf malforme/genere
                    # partiellement par systemd-resolved ou NetworkManager)
                    # faisait planter l'indexation, remontant jusqu'au
                    # worker Textual (gel avant le passage en worker,
                    # toast d'erreur generique depuis).
                    parts = line.split()
                    if len(parts) > 1:
                        dns.append(parts[1])
    except OSError:
        pass

    return {
        "cpu_percent": cpu_percent,
        "mem_total": mem.total,
        "mem_used": mem.used,
        "mem_percent": mem.percent,
        "swap_total": swap.total,
        "swap_used": swap.used,
        "swap_percent": swap.percent,
        "load_1": load_1,
        "cpu_count": psutil.cpu_count() or 1,
        "load_5": load_5,
        "load_15": load_15,
        "num_processes": num_processes,
        "temps": temps,
        "fans": fans,
        "uptime_seconds": uptime_seconds,
        "disk_total": disk.total,
        "disk_used": disk.used,
        "disk_percent": disk.percent,
        "net_bytes_sent": net_io.bytes_sent,
        "net_bytes_recv": net_io.bytes_recv,
        "tcp_established": tcp_established,
        "user_names": [u.name for u in psutil.users()],
        "outbound_ip": _detect_outbound_ip(),
        "interfaces": interfaces,
        "gateway": _detect_default_gateway(),
        "links": _physical_links({i["name"]: i["ip"] for i in interfaces}),
        "default_interface": _detect_default_interface(),
        "packets": _read_packet_totals(),
        "dns": dns,
    }


_PROCESS_CACHE: dict[int, psutil.Process] = {}
"""`cpu_percent()` mesure depuis l'appel precedent SUR LE MEME objet Process : on garde les objets
d'un rafraichissement a l'autre (le premier appel rend 0.0, les suivants la vraie valeur)."""


def _cached_process(pid: int) -> psutil.Process:
    process = _PROCESS_CACHE.get(pid)
    if process is None or not process.is_running():
        process = psutil.Process(pid)
        _PROCESS_CACHE[pid] = process
    return process


def _directory_usage(directory: Path) -> tuple[int, str, int]:
    """(taille totale, plus gros fichier, sa taille) ; sous-dossiers compris (ex. var/log/remote/)."""
    total, largest_name, largest_size = 0, "", 0
    try:
        for path in directory.rglob("*"):
            try:
                if path.is_file() and not path.is_symlink():
                    size = path.stat().st_size
                    total += size
                    if size > largest_size:
                        largest_name, largest_size = path.relative_to(directory).as_posix(), size
            except OSError:
                continue
    except OSError:
        pass
    return total, largest_name, largest_size


def collect_server_stats(pid: int | None, port: int, log_dir: Path, state_dir: Path) -> dict[str, Any]:
    """Ce qui concerne omega-serv lui-meme (retour utilisateur 2026-11-05) : ses processus (principal,
    workers, moteur natif, RIPOSTE...), les connexions etablies sur son port, ses journaux et l'espace
    libre de la partition de var/. Champ a None = donnee indisponible (droits : le service tourne
    souvent sous un compte dedie), jamais une erreur."""
    stats: dict[str, Any] = {"running": False}
    if pid is not None:
        try:
            main = _cached_process(pid)
            processes = [main, *(_cached_process(child.pid) for child in main.children(recursive=True))]
            alive = {p.pid for p in processes}
            for stale in [p for p in _PROCESS_CACHE if p not in alive]:
                del _PROCESS_CACHE[stale]
            cpu = rss = threads = 0.0
            fds: int | None = 0
            for process in processes:
                try:
                    with process.oneshot():
                        cpu += process.cpu_percent(interval=None)
                        rss += process.memory_info().rss
                        threads += process.num_threads()
                        if fds is not None:
                            try:
                                fds += process.num_fds()
                            except psutil.AccessDenied:
                                fds = None
                except (psutil.NoSuchProcess, psutil.ZombieProcess):
                    continue
            stats.update(running=True, process_count=len(processes), cpu_percent=cpu, rss=int(rss),
                         threads=int(threads), open_files=fds,
                         uptime_seconds=max(0.0, time.time() - main.create_time()))
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            stats["running"] = False
    try:
        stats["connections"] = sum(
            1 for c in psutil.net_connections(kind="tcp")
            if c.status == "ESTABLISHED" and c.laddr and c.laddr.port == port
        )
    except (psutil.Error, AttributeError):
        stats["connections"] = None
    log_total, largest_name, largest_size = _directory_usage(log_dir)
    stats.update(log_total=log_total, log_largest_name=largest_name, log_largest_size=largest_size)
    try:
        usage = psutil.disk_usage(str(state_dir))
        stats.update(state_free=usage.free, state_total=usage.total)
    except (OSError, psutil.Error):
        stats.update(state_free=None, state_total=None)
    return stats
