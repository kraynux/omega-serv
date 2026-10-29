"""Cas d'usage : vider le dossier d'export ou de captures d'ecran (ecran Reglages).

Remplace clear_exports.py / clear_screenshots.py (retour utilisateur 2026-10-27, meme correctif
qu'omega-fire) :
- le dossier vide est le dossier CONFIGURE (Reglages -> champ Export / Captures), plus le dossier
  par defaut quand un autre est choisi ;
- seul le CONTENU est supprime, le dossier reste ; un lien symbolique est supprime sans suivre sa
  cible ;
- dossiers systeme, personnels, racine du projet et ses parents refuses : le champ est libre et
  l'interface peut tourner avec des droits eleves ;
- un element qui resiste (droits, fichier du service) est signale, jamais retente avec `sudo` :
  une demande de mot de passe dans la TUI figerait l'application (_service_reload.py)."""
from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from omega_serv.application.terminal.exceptions import UnsafeDirectoryError
from omega_serv.core.i18n import _

_SYSTEM_DIRS = frozenset(Path(p) for p in (
    "/", "/bin", "/boot", "/dev", "/etc", "/home", "/lib", "/lib32", "/lib64", "/media", "/mnt",
    "/opt", "/proc", "/root", "/run", "/sbin", "/srv", "/sys", "/tmp", "/usr", "/var",
    "/var/lib", "/var/log", "/usr/local",
))


@dataclass(frozen=True)
class ClearResult:
    directory: Path
    removed: int
    failed: tuple[str, ...]


def check_clearable(directory: Path, project_root: Path) -> Path:
    """Chemin reel du dossier a vider, ou UnsafeDirectoryError s'il ne doit jamais l'etre."""
    target = directory.resolve()
    project = project_root.resolve()
    if target in _SYSTEM_DIRS or target.parent == Path("/home"):
        raise UnsafeDirectoryError(str(target), _("dossier système ou personnel"))
    if target == project or target in project.parents:
        raise UnsafeDirectoryError(str(target), _("contient l'installation d'omega-serv"))
    if target.exists() and not target.is_dir():
        raise UnsafeDirectoryError(str(target), _("ce n'est pas un dossier"))
    return target


def clear_directory(directory: Path, project_root: Path) -> ClearResult:
    """Supprime tout le contenu du dossier (cree s'il n'existe pas) ; continue apres un echec.
    Peut etre long : a appeler hors du thread de l'interface."""
    target = check_clearable(directory, project_root)
    target.mkdir(parents=True, exist_ok=True)
    removed = 0
    failed: list[str] = []
    for entry in sorted(target.iterdir()):
        try:
            if entry.is_dir() and not entry.is_symlink():
                shutil.rmtree(entry)
            else:
                entry.unlink()
        except OSError as exc:
            failed.append(f"{entry.name} ({exc.strerror or exc})")
        else:
            removed += 1
    return ClearResult(target, removed, tuple(failed))
