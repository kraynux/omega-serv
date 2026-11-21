"""Stockage d'archives tar.gz (plan interface §3.4/§3.5, port direct
depuis omega-fire infrastructure/storage/files/archive_store.py) -
creation/extraction generiques, utilisees pour la rotation des logs
(un fichier unique enveloppe en tar.gz) et plus tard pour les
sauvegardes de configuration (Phase VII, plusieurs fichiers)."""
from __future__ import annotations

import os
import shutil
import tarfile
from datetime import datetime, timezone
from pathlib import Path

from omega_serv.core.i18n import _
from omega_serv.domain.logs.exceptions import ArchiveStoreError


def _resolves_within(dest_dir: Path, candidate: Path) -> bool:
    resolved_dest = dest_dir.resolve()
    resolved_candidate = candidate.resolve()
    return resolved_candidate == resolved_dest or resolved_dest in resolved_candidate.parents


def _safe_members(tar: tarfile.TarFile, dest_dir: Path) -> list[tarfile.TarInfo]:
    """Repli manuel du filtre "data" (PEP 706) pour Python < 3.12 (voir
    extract_archive ci-dessous) : un membre d'archive malveillant peut
    porter un chemin absolu, une remontee `..`, ou etre un lien
    (symbolique/dur) pointant hors de `dest_dir` - `Path./` avec un
    operande absolu remplace ENTIEREMENT le chemin de base en pathlib
    (`Path("/dest") / "/etc/passwd"` vaut `/etc/passwd`), d'ou la
    verification par resolution complete plutot qu'un simple
    `startswith`/recherche de `..` dans la chaine, plus facilement
    contournable (encodages, segments `.` intercales...)."""
    safe: list[tarfile.TarInfo] = []
    for member in tar.getmembers():
        if member.isdev():
            continue
        member_target = dest_dir / member.name
        if not _resolves_within(dest_dir, member_target):
            continue
        if (member.issym() or member.islnk()) and not _resolves_within(dest_dir, member_target.parent / member.linkname):
            continue
        safe.append(member)
    return safe


class ArchiveStore:
    def __init__(self, base_dir: Path, private: bool = False) -> None:
        """`private` (scan de securite n° 2 du 2026-11-20, F23) : sauvegardes completes (cles privees TLS,
        users.json) - dossier cree 0700 et archives 0600 DES leur creation. Les archives de logs restent partagees
        avec le groupe du service (var/backups/logs)."""
        self._base_dir = base_dir
        self._private = private
        self._base_dir.mkdir(parents=True, exist_ok=True, mode=0o700 if private else 0o777)

    @property
    def base_dir(self) -> Path:
        return self._base_dir

    @staticmethod
    def _arcname_for(source: Path, base_path: Path | None) -> str:
        if base_path is None:
            return source.name
        try:
            return str(source.relative_to(base_path))
        except ValueError:
            return source.name

    def create_archive(
        self, archive_name: str, source_paths: list[Path], base_path: Path | None = None,
        extra_files: list[tuple[Path, str]] | None = None,
    ) -> Path:
        """`extra_files` : (fichier, nom dans l'archive) - ex. la copie coherente d'une base, faite ailleurs
        mais restauree a l'emplacement de la base (2026-11-01)."""
        archive_path = self._base_dir / archive_name
        try:
            if self._private:
                descriptor = os.open(archive_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
                os.fchmod(descriptor, 0o600)
                os.close(descriptor)
            with tarfile.open(archive_path, "w:gz") as tar:
                for source in source_paths:
                    if not source.exists():
                        continue
                    arcname = self._arcname_for(source, base_path)
                    tar.add(source, arcname=arcname)
                for source, arcname in extra_files or ():
                    tar.add(source, arcname=arcname)
        except (OSError, tarfile.TarError) as exc:
            raise ArchiveStoreError(_("Échec de création de l'archive {archive_name} : {exc}").format(archive_name=archive_name, exc=exc)) from exc
        return archive_path

    def extract_archive(self, archive_path: Path, dest_dir: Path) -> None:
        try:
            dest_dir.mkdir(parents=True, exist_ok=True)
            with tarfile.open(archive_path, "r:gz") as tar:
                try:
                    tar.extractall(dest_dir, filter="data")
                except TypeError:
                    tar.extractall(dest_dir, members=_safe_members(tar, dest_dir))
        except (OSError, tarfile.TarError) as exc:
            raise ArchiveStoreError(_("Échec d'extraction de l'archive {archive_path} : {exc}").format(archive_path=archive_path, exc=exc)) from exc

    def extract_archive_confined(self, archive_path: Path, trusted_root: Path, relative_dest: str) -> Path:
        """Scan de securite n° 2 (2026-11-20, F6) : restauration d'une archive de log par l'operateur dans
        `trusted_root/relative_dest`, ou les dossiers intermediaires (var/log) sont inscriptibles par le compte du
        service. Chaque dossier est ouvert depuis `trusted_root` sans suivre de lien, la destination est CREEE
        (jamais reprise : elle ne doit pas exister) en 0700, et seuls fichiers et dossiers ordinaires sont ecrits,
        relativement a ces descripteurs - un lien pose par le service ne peut plus detourner l'ecriture.
        Retourne le chemin de la destination."""
        parts = [part for part in relative_dest.split("/") if part]
        if not parts or any(part in (".", "..") for part in parts):
            raise ArchiveStoreError(_("Destination refusée : {dest}").format(dest=relative_dest))
        dir_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
        opened: list[int] = []
        try:
            fd = os.open(trusted_root, dir_flags)
            opened.append(fd)
            for index, part in enumerate(parts):
                last = index == len(parts) - 1
                try:
                    os.mkdir(part, 0o700 if last else 0o770, dir_fd=fd)
                except FileExistsError:
                    if last:
                        raise ArchiveStoreError(_("{dest} existe déjà : rien n'a été écrasé.").format(
                            dest=trusted_root / relative_dest)) from None
                fd = os.open(part, dir_flags, dir_fd=fd)
                opened.append(fd)
            os.fchmod(fd, 0o700)
            with tarfile.open(archive_path, "r:gz") as tar:
                for member in tar.getmembers():
                    self._extract_member(tar, member, fd)
        except ArchiveStoreError:
            raise
        except (OSError, tarfile.TarError) as exc:
            raise ArchiveStoreError(_("Échec d'extraction de l'archive {archive_path} : {exc}").format(
                archive_path=archive_path, exc=exc)) from exc
        finally:
            for descriptor in reversed(opened):
                os.close(descriptor)
        return trusted_root / relative_dest

    @staticmethod
    def _extract_member(tar: tarfile.TarFile, member: tarfile.TarInfo, dest_fd: int) -> None:
        names = [part for part in member.name.split("/") if part and part != "."]
        if not names or any(part == ".." for part in names) or member.name.startswith("/"):
            return
        if not (member.isfile() or member.isdir()):
            return  # liens, peripheriques : jamais ecrits
        dir_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
        directories = names if member.isdir() else names[:-1]
        opened: list[int] = []
        try:
            fd = dest_fd
            for part in directories:
                try:
                    os.mkdir(part, 0o700, dir_fd=fd)
                except FileExistsError:
                    pass
                fd = os.open(part, dir_flags, dir_fd=fd)
                opened.append(fd)
            if member.isfile():
                source = tar.extractfile(member)
                if source is None:
                    return
                out = os.open(names[-1], os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
                              0o600, dir_fd=fd)
                with os.fdopen(out, "wb") as handle:
                    shutil.copyfileobj(source, handle)
        finally:
            for descriptor in reversed(opened):
                os.close(descriptor)

    def list_members(self, archive_path: Path) -> list[str]:
        try:
            with tarfile.open(archive_path, "r:gz") as tar:
                return tar.getnames()
        except (OSError, tarfile.TarError) as exc:
            raise ArchiveStoreError(_("Archive illisible {archive_path} : {exc}").format(archive_path=archive_path, exc=exc)) from exc

    def read_member(self, archive_path: Path, name: str, max_bytes: int = 4 * 1024 * 1024) -> bytes | None:
        """Contenu d'un fichier de l'archive (lecture seule, borne) ; None s'il est absent ou n'est pas un fichier."""
        try:
            with tarfile.open(archive_path, "r:gz") as tar:
                try:
                    member = tar.getmember(name)
                except KeyError:
                    return None
                if not member.isfile() or member.size > max_bytes:
                    return None
                handle = tar.extractfile(member)
                return handle.read() if handle is not None else None
        except (OSError, tarfile.TarError) as exc:
            raise ArchiveStoreError(_("Archive illisible {archive_path} : {exc}").format(archive_path=archive_path, exc=exc)) from exc

    def describe_members(self, archive_path: Path) -> list[tuple[str, str, int]]:
        """(nom, type, taille) de chaque membre ; type : « file », « dir » ou « other » (lien, peripherique...)."""
        try:
            with tarfile.open(archive_path, "r:gz") as tar:
                return [
                    (member.name, "file" if member.isfile() else "dir" if member.isdir() else "other", member.size)
                    for member in tar.getmembers()
                ]
        except (OSError, tarfile.TarError, EOFError) as exc:
            raise ArchiveStoreError(_("Archive illisible {archive_path} : {exc}").format(archive_path=archive_path, exc=exc)) from exc

    def list_archives(self, pattern: str = "*.tar.gz") -> list[Path]:
        return sorted(self._base_dir.glob(pattern))

    def get_archive_info(self, archive_path: Path) -> dict:
        try:
            stat = archive_path.stat()
        except OSError as exc:
            raise ArchiveStoreError(_("Échec de lecture des informations de {archive_path} : {exc}").format(archive_path=archive_path, exc=exc)) from exc
        return {
            "path": str(archive_path),
            "name": archive_path.name,
            "size_bytes": stat.st_size,
            "modified_at": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
        }

    def delete_archive(self, archive_path: Path) -> bool:
        if archive_path.exists():
            archive_path.unlink()
            return True
        return False
