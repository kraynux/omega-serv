# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Partage d'une arborescence avec le groupe du service, sans jamais suivre un lien (scan de securite n° 2 du
2026-11-20, F11/F21/F23).

Avant : root lancait `find var/ ! -type l -exec chgrp -h|chmod g+rwX|chmod g+s {} +`. Le compte du service peut
ecrire dans var/ : entre le passage de find et l'execution groupee de chgrp/chmod, il remplacait un dossier
intermediaire par un lien, et root changeait le groupe et les droits d'un fichier systeme (/etc/shadow...).

Ici chaque entree est ouverte RELATIVEMENT au descripteur de son dossier parent, avec O_NOFOLLOW (O_PATH), et
les changements passent par ce descripteur (/proc/self/fd/N designe l'inode deja ouvert) : un lien pose apres
coup n'est jamais traverse. Uniquement la bibliotheque standard : lance par root (`sudo python -I ce_fichier
'<json>'`), il n'importe rien du projet. Linux seulement (O_PATH, /proc), comme systemd.

Operations (argument JSON) :
- {"op": "share", "root": ..., "group": ..., "private": [...], "open": [...]} : groupe + g+rwX, setgid sur les
  dossiers ; `private` (chemins relatifs) jamais partages et remis proprietaire seul (go-rwx) ; `open` (dossier
  partage DANS un dossier prive) : parents seulement traversables par le groupe (g+x, SANS setgid - F23 : le
  setgid de var/backups faisait heriter le groupe du service a chaque sauvegarde complete), dossier lui partage.
- {"op": "return_root_owned", "root": ..., "owner": ...} : fichiers de root rendus a `owner`, meme systeme de
  fichiers seulement.
- {"op": "fix_file", "path": ..., "trusted_uid": ..., "group": ..., "add": ..., "remove": ...} : groupe et droits
  d'un seul fichier ordinaire (Sante des logs), chemin ouvert sans suivre de lien douteux."""
from __future__ import annotations

import grp
import json
import os
import pwd
import stat
import sys
from collections.abc import Callable

_PATH_FLAGS = os.O_PATH | os.O_NOFOLLOW | os.O_CLOEXEC
_DIR_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC

Visit = Callable[[int, os.stat_result], None]


def _proc(fd: int) -> str:
    return f"/proc/self/fd/{fd}"


def _open_relative(base_fd: int, relative: str) -> int | None:
    """Descripteur O_PATH de `relative` sous `base_fd`, chaque composant ouvert sans suivre de lien ; None si un
    composant manque ou est un lien."""
    fd = os.dup(base_fd)
    try:
        for part in [p for p in relative.split("/") if p]:
            if part in (".", ".."):
                return None
            try:
                child = os.open(part, _PATH_FLAGS, dir_fd=fd)
            except OSError:
                return None
            os.close(fd)
            fd = child
            if stat.S_ISLNK(os.fstat(fd).st_mode):
                return None
        result, fd = fd, -1
        return result
    finally:
        if fd >= 0:
            os.close(fd)


def _walk(path_fd: int, visit: Visit, skip: frozenset[str] = frozenset(), rel: str = "",
          same_device: int | None = None) -> None:
    """Visite `path_fd` (O_PATH, deja verifie) puis tout ce qu'il contient, jamais a travers un lien."""
    st = os.fstat(path_fd)
    if stat.S_ISLNK(st.st_mode) or (same_device is not None and st.st_dev != same_device):
        return
    visit(path_fd, st)
    if not stat.S_ISDIR(st.st_mode):
        return
    dir_fd = os.open(".", _DIR_FLAGS, dir_fd=path_fd)
    try:
        names = os.listdir(dir_fd)
        for name in names:
            child_rel = f"{rel}/{name}" if rel else name
            if child_rel in skip:
                continue
            try:
                child = os.open(name, _PATH_FLAGS, dir_fd=dir_fd)
            except FileNotFoundError:
                continue
            try:
                _walk(child, visit, skip, child_rel, same_device)
            finally:
                os.close(child)
    finally:
        os.close(dir_fd)


def _share_visit(gid: int) -> Visit:
    def visit(fd: int, st: os.stat_result) -> None:
        os.chown(_proc(fd), -1, gid)
        mode = stat.S_IMODE(st.st_mode)
        if stat.S_ISDIR(st.st_mode):
            mode |= 0o070 | stat.S_ISGID
        else:
            mode |= 0o060 | (0o010 if mode & 0o111 else 0)
            mode &= ~(stat.S_ISUID | stat.S_ISGID)
        os.chmod(_proc(fd), mode)
    return visit


def _private_visit(fd: int, st: os.stat_result) -> None:
    os.chmod(_proc(fd), stat.S_IMODE(st.st_mode) & ~0o077)


def share(root: str, group: str, private: list[str], open_dirs: list[str]) -> None:
    gid = grp.getgrnam(group).gr_gid
    root_fd = os.open(root, _PATH_FLAGS | os.O_DIRECTORY)
    try:
        _walk(root_fd, _share_visit(gid), skip=frozenset(p.strip("/") for p in private))
        for name in private:
            fd = _open_relative(root_fd, name)
            if fd is not None:
                try:
                    _walk(fd, _private_visit)
                finally:
                    os.close(fd)
        for name in open_dirs:
            parts = [p for p in name.split("/") if p]
            target = _open_relative(root_fd, name)
            if target is None or not stat.S_ISDIR(os.fstat(target).st_mode):
                if target is not None:
                    os.close(target)
                continue
            try:
                for depth in range(1, len(parts)):
                    parent = _open_relative(root_fd, "/".join(parts[:depth]))
                    if parent is None:
                        break
                    try:
                        os.chown(_proc(parent), -1, gid)
                        mode = stat.S_IMODE(os.fstat(parent).st_mode)
                        os.chmod(_proc(parent), (mode | 0o010) & ~(0o060 | stat.S_ISGID))
                    finally:
                        os.close(parent)
                _walk(target, _share_visit(gid))
            finally:
                os.close(target)
    finally:
        os.close(root_fd)


def return_root_owned(root: str, owner: str) -> None:
    uid = pwd.getpwnam(owner).pw_uid

    def visit(fd: int, st: os.stat_result) -> None:
        if st.st_uid == 0:
            os.chown(_proc(fd), uid, -1)

    root_fd = os.open(root, _PATH_FLAGS | os.O_DIRECTORY)
    try:
        _walk(root_fd, visit, same_device=os.fstat(root_fd).st_dev)
    finally:
        os.close(root_fd)


def _open_trusted_path(path: str, trusted_uid: int) -> int:
    """Descripteur O_PATH du fichier `path`, ouvert composant par composant sans jamais suivre un lien qu'un
    autre compte aurait pu poser : un lien n'est suivi que s'il appartient a root ou a `trusted_uid` ET que son
    dossier appartient a l'un d'eux sans etre inscriptible par le groupe ni les autres (cas d'un ~/DEV -> /data).
    Le dernier composant doit etre un fichier ordinaire. OSError sinon."""
    trusted = {0, trusted_uid}
    pending = [p for p in path.split("/") if p]
    fd = os.open("/", _PATH_FLAGS | os.O_DIRECTORY)
    hops = 0
    try:
        while pending:
            part = pending.pop(0)
            if part in (".", ".."):
                raise OSError(f"segment {part!r} refuse dans {path}")
            child = os.open(part, _PATH_FLAGS, dir_fd=fd)
            st = os.fstat(child)
            if stat.S_ISLNK(st.st_mode):
                parent = os.fstat(fd)
                if (st.st_uid not in trusted or parent.st_uid not in trusted or parent.st_mode & 0o022
                        or hops >= 16):
                    os.close(child)
                    raise OSError(f"lien non sur dans le chemin : {path}")
                target = os.readlink(part, dir_fd=fd)
                os.close(child)
                hops += 1
                pending = [p for p in target.split("/") if p] + pending
                if target.startswith("/"):
                    os.close(fd)
                    fd = os.open("/", _PATH_FLAGS | os.O_DIRECTORY)
                continue
            os.close(fd)
            fd = child
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise OSError(f"pas un fichier ordinaire : {path}")
        result, fd = fd, -1
        return result
    finally:
        if fd >= 0:
            os.close(fd)


def fix_file(path: str, trusted_uid: int, group: str | None, add_mode: int, remove_mode: int) -> None:
    """Sante des logs, « Corriger avec sudo » (F4) : groupe et droits d'UN fichier ordinaire, par descripteur."""
    fd = _open_trusted_path(path, trusted_uid)
    try:
        if group:
            os.chown(_proc(fd), -1, grp.getgrnam(group).gr_gid)
        mode = stat.S_IMODE(os.fstat(fd).st_mode)
        os.chmod(_proc(fd), (mode | add_mode) & ~remove_mode)
    finally:
        os.close(fd)


def main(argv: list[str]) -> int:
    try:
        spec = json.loads(argv[1])
        if spec["op"] == "share":
            share(spec["root"], spec["group"], list(spec.get("private", [])), list(spec.get("open", [])))
        elif spec["op"] == "fix_file":
            fix_file(spec["path"], int(spec["trusted_uid"]), spec.get("group"), int(spec.get("add", 0)),
                     int(spec.get("remove", 0)))
        elif spec["op"] == "return_root_owned":
            return_root_owned(spec["root"], spec["owner"])
        else:
            print(f"operation inconnue : {spec['op']!r}", file=sys.stderr)
            return 2
    except (OSError, KeyError, IndexError, ValueError) as error:
        print(str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
