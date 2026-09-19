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
                    dns.append(line.split()[1])
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
        "dns": dns,
    }
