"""Informations plateforme minimales necessaires au demarrage.

Le registre de capacites complet (detection systemd/OpenRC/runit,
PHP-FPM, Lua...) arrive avec l'extraction omega-lib prevue en Phase 9 -
ce module se limite a ce que Phase 0 exige reellement : verifier que la
version de Python est compatible avant d'aller plus loin."""
from __future__ import annotations

import os
import platform
import sys
from dataclasses import dataclass

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
