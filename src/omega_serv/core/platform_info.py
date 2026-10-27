"""Informations plateforme minimales necessaires au demarrage.

Le registre de capacites complet (detection systemd/OpenRC/runit,
PHP-FPM, Lua...) arrive avec l'extraction omega-lib prevue en Phase 9 -
ce module se limite a ce que Phase 0 exige reellement : verifier que la
version de Python est compatible avant d'aller plus loin."""
from __future__ import annotations

import math
import os
import platform
import sys
from dataclasses import dataclass
from pathlib import Path

MIN_PYTHON_VERSION = (3, 10)


@dataclass(frozen=True)
class PlatformInfo:
    python_version: str
    system: str
    machine: str


def get_platform_info() -> PlatformInfo:
    return PlatformInfo(
        python_version=platform.python_version(),
        system=platform.system(),
        machine=platform.machine(),
    )


def python_version_supported() -> bool:
    return sys.version_info[:2] >= MIN_PYTHON_VERSION


def running_as_root() -> bool:
    """Refus de demarrage si root (plan de developpement §6, meme
    logique que les portes TLS/FastCGI - un constat verifie au boot,
    pas seulement un avertissement d'audit a posteriori). `os.getuid`
    n'existe pas hors POSIX - retourne False dans ce cas plutot que de
    lever, ce projet ne cible que des serveurs POSIX de toute facon."""
    return hasattr(os, "getuid") and os.getuid() == 0


@dataclass(frozen=True)
class CpuInfo:
    """Processeur vu par CE processus (mode « boost », OMEGA-SERV_ETUDE_MODE_BOOST.md). Un
    nombre de workers doit correspondre a la machine ou omega-serv est installe."""
    logical: int  # threads logiques exposes par le noyau (hyperthreading compris)
    physical: int  # coeurs physiques
    affinity: int  # CPU que ce processus a le droit d'utiliser (conteneur, taskset...)
    quota: float | None  # quota cgroup v2 (cpu.max, ex. CPUQuota= de systemd), None = aucun
    load_1min: float | None
    detected: bool  # False : detection impossible, valeurs de repli (1)

    @property
    def available(self) -> int:
        """CPU reellement utilisables : affinite, plafonnee par le quota (arrondi superieur)."""
        if self.quota is None:
            return self.affinity
        return max(1, min(self.affinity, math.ceil(self.quota)))

    @property
    def recommended_workers(self) -> int:
        """Valeur « auto » : un worker par coeur physique, jamais plus que les CPU disponibles."""
        return max(1, min(self.physical, self.available))


def _cgroup_cpu_quota() -> float | None:
    """Plus petit quota `cpu.max` du cgroup du processus et de ses parents (cgroup v2)."""
    try:
        line = next(
            entry for entry in Path("/proc/self/cgroup").read_text(encoding="utf-8").splitlines()
            if entry.startswith("0::")
        )
    except (OSError, StopIteration):
        return None
    relative = line[3:].strip("/")
    parts = relative.split("/") if relative else []
    quotas: list[float] = []
    for depth in range(len(parts), -1, -1):
        path = Path("/sys/fs/cgroup", *parts[:depth], "cpu.max")
        try:
            limit, period = path.read_text(encoding="utf-8").split()[:2]
        except (OSError, ValueError):
            continue
        if limit != "max" and int(period) > 0:
            quotas.append(int(limit) / int(period))
    return min(quotas) if quotas else None


def _physical_cores() -> int | None:
    """Coeurs physiques lus dans /sys (couples boitier/coeur distincts) - sans psutil, confine
    a infrastructure/probe/system_stats.py et traite comme facultatif. None si illisible."""
    cores: set[tuple[str, str]] = set()
    for topology in Path("/sys/devices/system/cpu").glob("cpu[0-9]*/topology"):
        try:
            package = (topology / "physical_package_id").read_text(encoding="utf-8").strip()
            core = (topology / "core_id").read_text(encoding="utf-8").strip()
        except OSError:
            continue
        cores.add((package, core))
    return len(cores) or None


def cpu_info() -> CpuInfo:
    """Jamais une exception : toute valeur introuvable retombe sur 1 (`detected=False` si
    meme le nombre de CPU logiques est inconnu)."""
    logical_raw = os.cpu_count()
    logical = max(1, logical_raw or 1)
    physical = _physical_cores() or logical
    try:
        affinity = max(1, len(os.sched_getaffinity(0)))
    except (AttributeError, OSError):
        affinity = logical
    try:
        load_1min: float | None = os.getloadavg()[0]
    except (AttributeError, OSError):
        load_1min = None
    return CpuInfo(
        logical=logical, physical=max(1, min(physical, logical)), affinity=affinity,
        quota=_cgroup_cpu_quota(), load_1min=load_1min, detected=logical_raw is not None,
    )


def available_cpu_cores() -> int:
    """CPU reellement utilisables (affinite + quota cgroup) - voir CpuInfo.available."""
    return cpu_info().available


def is_missing_live_group(group_name: str) -> bool:
    """Retour utilisateur 2026-09-13 (cas reel rencontre : `var/` partage
    avec un compte systeme dedie via `grant_directory_access()`, qui
    ajoute deja l'utilisateur interactif au groupe via `usermod -aG` -
    mais cet ajout ne prend JAMAIS effet pour les processus DEJA lances,
    seule une nouvelle session -deconnexion/reconnexion ou `newgrp`-
    l'applique). Retourne True uniquement si le groupe existe REELLEMENT
    (sinon aucun service dedie n'a jamais ete installe, rien a signaler)
    mais n'est PAS dans les groupes REELS du processus courant
    (`os.getgroups()`, jamais `/etc/group` qui refleterait a tort une
    appartenance pas encore active dans cette session). `grp` n'existe
    pas hors POSIX (meme regle que `running_as_root` ci-dessus)."""
    try:
        import grp
    except ImportError:
        return False
    try:
        gid = grp.getgrnam(group_name).gr_gid
    except KeyError:
        return False
    return gid not in os.getgroups()


def is_process_running(pid: int) -> bool:
    """Ecran "Etat & Ressources" (retour utilisateur 2026-09-09) :
    `os.kill(pid, 0)` n'envoie aucun signal reel (signal 0), demande
    juste au noyau si ce PID existe et nous est visible - technique
    standard, jamais un appel a `ps`/`pgrep` en subprocess. Un
    `PermissionError` (PID existant mais possede par un autre
    utilisateur) compte comme "en cours d'execution" - le processus
    existe reellement, seule la verification d'appartenance a echoue."""
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True
