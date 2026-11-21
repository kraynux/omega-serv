# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Lecture seule de ce que `grant_directory_access` (systemd_service_manager.py) pose sur var/ : groupe du service,
lecture/ecriture de groupe, bit setgid sur les dossiers. Aucun privilege, aucun lien suivi ; var/backups (prive) est
ignore, comme a la reparation."""
from __future__ import annotations

import grp
import os
import stat
from pathlib import Path

from omega_serv.domain.services.shared_access import SharedAccessReport

_MAX_ENTRIES = 5000
_MAX_REPORTED = 5


def probe_shared_access(var_dir: Path, group: str, private_subdirs: tuple[str, ...] = ("backups",),
                        open_subdirs: tuple[str, ...] = ("backups/logs",)) -> SharedAccessReport:
    """`open_subdirs` (2026-11-17) : dossiers partages dans un dossier prive (var/backups/logs) ; leurs parents prives
    doivent seulement etre traversables par le groupe (g+x)."""
    try:
        gid = grp.getgrnam(group).gr_gid
    except KeyError:
        return SharedAccessReport(group_exists=False, checked=0)
    wrong: list[str] = []
    wrong_count = checked = 0
    truncated = False
    opened = [var_dir / name for name in open_subdirs
              if (var_dir / name).is_dir() and not (var_dir / name).is_symlink()]  # absent : rien a exiger
    traversed = {parent for target in opened for parent in target.parents if var_dir in parent.parents}
    stack = [var_dir, *opened]
    for parent in sorted(traversed):
        try:
            info = os.lstat(parent)
        except OSError:
            continue
        if stat.S_ISLNK(info.st_mode):
            continue
        checked += 1
        if info.st_gid != gid or not info.st_mode & stat.S_IXGRP:
            wrong_count += 1
            if len(wrong) < _MAX_REPORTED:
                wrong.append(str(parent.relative_to(var_dir.parent)))
    while stack:
        current = stack.pop()
        try:
            info = os.lstat(current)
        except OSError:
            continue
        if stat.S_ISLNK(info.st_mode):
            continue
        checked += 1
        is_dir = stat.S_ISDIR(info.st_mode)
        needed = stat.S_IRGRP | stat.S_IWGRP | ((stat.S_IXGRP | stat.S_ISGID) if is_dir else 0)
        if info.st_gid != gid or info.st_mode & needed != needed:
            wrong_count += 1
            if len(wrong) < _MAX_REPORTED:
                wrong.append(str(current.relative_to(var_dir.parent)))
        if checked >= _MAX_ENTRIES:
            truncated = True
            break
        if is_dir:
            try:
                names = os.listdir(current)
            except OSError:
                continue
            stack.extend(current / name for name in names
                         if not (current == var_dir and name in private_subdirs))
    return SharedAccessReport(True, checked, tuple(wrong), wrong_count, truncated)
