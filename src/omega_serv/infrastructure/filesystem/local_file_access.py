"""Implementation reelle de FileAccessPort (OMEGA-SERV_PLAN-DETAILLE_
SENSITIVE_PATHS.md §3.7).

`atomic_write_preserving` existe parce que `LocalFilesystem.atomic_write_text`
PERD le mode et le groupe du fichier (nouvel inode cree selon l'umask, puis
os.replace) - demontre le 2026-10-18 : un fichier `640 :omega-serv` reecrit
sous umask 077 devenait `600 :kraynux`, illisible par le service.
`atomic_write_text` reste inchange pour ses autres appelants (PID, unite
systemd), dont le comportement actuel est voulu."""
from __future__ import annotations

import grp
import os
import pwd
import stat
import threading
from pathlib import Path

from omega_serv.domain.security.file_access import AccountIdentity, PathNode
from omega_serv.ports.file_access_port import WriteOutcome


class LocalFileAccess:
    def stat_chain(self, path: Path) -> tuple[PathNode, ...]:
        absolute = Path(os.path.abspath(path))
        nodes: list[PathNode] = []
        for element in (*reversed(absolute.parents), absolute):
            st = os.stat(element)
            nodes.append(PathNode(
                path=str(element), mode=st.st_mode, uid=st.st_uid, gid=st.st_gid,
                is_dir=stat.S_ISDIR(st.st_mode),
            ))
        return tuple(nodes)

    def lookup_account(self, name: str) -> AccountIdentity | None:
        try:
            entry = pwd.getpwnam(name)
        except KeyError:
            return None
        gids = set(os.getgrouplist(name, entry.pw_gid))
        gids.update(g.gr_gid for g in grp.getgrall() if name in g.gr_mem)
        return AccountIdentity(name=name, uid=entry.pw_uid, gids=frozenset(gids))

    def current_uid(self) -> int:
        return os.getuid()

    def has_symlink_between(self, root: Path, path: Path) -> bool:
        absolute_root = Path(os.path.abspath(root))
        absolute = Path(os.path.abspath(path))
        try:
            relative = absolute.relative_to(absolute_root)
        except ValueError:
            return True  # hors de la racine : traite comme un detour, jamais accepte
        current = absolute_root
        for part in relative.parts:
            current = current / part
            if current.is_symlink():
                return True
        return False

    def fingerprint(self, path: Path) -> tuple[int, int] | None:
        try:
            st = os.stat(path)
        except FileNotFoundError:
            return None
        return st.st_mtime_ns, st.st_size

    def can_write(self, path: Path) -> bool:
        directory = path.parent
        if not os.access(directory, os.W_OK | os.X_OK):
            return False
        return not path.exists() or os.access(path, os.W_OK)

    def atomic_write_preserving(self, path: Path, content: str, new_file_mode: int) -> WriteOutcome:
        existing = os.stat(path) if path.exists() else None
        tmp_path = path.with_name(f".{path.name}.{os.getpid()}-{threading.get_ident()}.tmp")
        fd = os.open(tmp_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        group_preserved = True
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(content)
                f.flush()
                if existing is not None:
                    mode = stat.S_IMODE(existing.st_mode)
                    try:
                        os.fchown(f.fileno(), -1, existing.st_gid)
                    except PermissionError:
                        group_preserved = False
                else:
                    mode = new_file_mode
                # fchmod APRES fchown : un changement de groupe peut effacer setgid
                os.fchmod(f.fileno(), mode)
                os.fsync(f.fileno())
            os.replace(tmp_path, path)
        except BaseException:
            tmp_path.unlink(missing_ok=True)
            raise
        return WriteOutcome(mode=mode, group_preserved=group_preserved)

    def set_mode(self, path: Path, mode: int) -> None:
        os.chmod(path, mode)

    def read_tail_lines(self, path: Path, max_bytes: int) -> list[str]:
        try:
            size = os.stat(path).st_size
        except FileNotFoundError:
            return []
        with open(path, "rb") as f:
            start = max(0, size - max_bytes)
            f.seek(start)
            data = f.read()
        lines = data.decode("utf-8", errors="replace").splitlines()
        return lines[1:] if start > 0 and lines else lines  # 1re ligne tronquee par le decoupage
