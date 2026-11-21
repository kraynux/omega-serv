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

import os
import stat
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


def _inside_project(directory: Path, project_root: Path) -> tuple[str, ...] | None:
    """Composants de `directory` sous la racine du projet (sans resolution), None s'il est ailleurs."""
    try:
        return Path(os.path.abspath(directory)).relative_to(Path(os.path.abspath(project_root))).parts
    except ValueError:
        return None


def check_clearable(directory: Path, project_root: Path) -> Path:
    """Chemin reel du dossier a vider, ou UnsafeDirectoryError s'il ne doit jamais l'etre.

    Scan de securite n° 2 (2026-11-20, F13) : sous le projet (var/exports, var/screenshots par defaut), var/ est
    inscriptible par le compte du service - un dossier ou un composant remplace par un lien est refuse ; avant,
    le lien etait resolu et l'operateur vidait la cible (~/.ssh, un autre projet...)."""
    parts = _inside_project(directory, project_root)
    if parts is not None:
        current = Path(os.path.abspath(project_root))
        for part in parts:
            current = current / part
            if current.is_symlink():
                raise UnsafeDirectoryError(str(directory), _("le chemin passe par un lien symbolique"))
    elif directory.is_symlink():
        raise UnsafeDirectoryError(str(directory), _("le chemin passe par un lien symbolique"))
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
    # Suppression relative au descripteur du dossier, ouvert sans suivre de lien (F13) : un lien pose entre la
    # verification et la suppression fait echouer l'ouverture au lieu de detourner la purge.
    dir_fd = os.open(target, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        for name in sorted(os.listdir(dir_fd)):
            try:
                if stat.S_ISDIR(os.stat(name, dir_fd=dir_fd, follow_symlinks=False).st_mode):
                    _remove_tree_at(name, dir_fd)
                else:
                    os.unlink(name, dir_fd=dir_fd)
            except OSError as exc:
                failed.append(f"{name} ({exc.strerror or exc})")
            else:
                removed += 1
    finally:
        os.close(dir_fd)
    return ClearResult(target, removed, tuple(failed))


def _remove_tree_at(name: str, parent_fd: int) -> None:
    """Supprime le dossier `name` (relatif a `parent_fd`) et son contenu, sans jamais suivre un lien (F13).
    shutil.rmtree(dir_fd=...) n'existe qu'a partir de Python 3.11 ; omega-serv tourne des 3.10."""
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
    fd = os.open(name, flags, dir_fd=parent_fd)
    try:
        for child in os.listdir(fd):
            if stat.S_ISDIR(os.stat(child, dir_fd=fd, follow_symlinks=False).st_mode):
                _remove_tree_at(child, fd)
            else:
                os.unlink(child, dir_fd=fd)
    finally:
        os.close(fd)
    os.rmdir(name, dir_fd=parent_fd)
