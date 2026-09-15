# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Detection du gestionnaire de service disponible (spec §24.1). Portee
depuis omega-fire (service_manager/detector.py, audite reutilisable) -
3 strategies dans le meme ordre (proc/1/comm, binaires, repertoires).
Simplifie : retourne une chaine litterale ("systemd"/"openrc"/"runit"/
"none") plutot qu'un enum importe d'un autre projet - convention deja
utilisee ailleurs dans OMEGA-SERV (ex. TlsConfig.mode)."""
from __future__ import annotations

import shutil
from pathlib import Path

from omega_serv.ports.service_manager_port import ServiceManagerType

_PROC_1_COMM = Path("/proc/1/comm")


def detect_service_manager_type() -> ServiceManagerType | None:
    result = _detect_from_proc()
    if result is not None:
        return result
    result = _detect_from_binaries()
    if result is not None:
        return result
    return _detect_from_directories()


def _detect_from_proc() -> ServiceManagerType | None:
    try:
        if not _PROC_1_COMM.exists():
            return None
        init_name = _PROC_1_COMM.read_text().strip()
    except OSError:
        return None
    if init_name == "systemd":
        return "systemd"
    if init_name in ("openrc-init", "openrc"):
        return "openrc"
    if init_name in ("runit", "runsvdir"):
        return "runit"
    return None


def _detect_from_binaries() -> ServiceManagerType | None:
    if shutil.which("systemctl") is not None:
        return "systemd"
    if shutil.which("rc-service") is not None:
        return "openrc"
    if shutil.which("sv") is not None:
        return "runit"
    return None


def _detect_from_directories() -> ServiceManagerType | None:
    if Path("/run/systemd/system").exists():
        return "systemd"
    if Path("/etc/init.d").exists() and Path("/etc/rc.conf").exists():
        return "openrc"
    if Path("/etc/runit").exists() or Path("/etc/sv").exists():
        return "runit"
    return None
