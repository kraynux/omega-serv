"""Stockage d'archives tar.gz (plan interface §3.4/§3.5, port direct
depuis omega-fire infrastructure/storage/files/archive_store.py) -
creation/extraction generiques, utilisees pour la rotation des logs
(un fichier unique enveloppe en tar.gz) et plus tard pour les
sauvegardes de configuration (Phase VII, plusieurs fichiers)."""
from __future__ import annotations

import tarfile
from datetime import datetime, timezone
from pathlib import Path

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
    def __init__(self, base_dir: Path) -> None:
        self._base_dir = base_dir
        self._base_dir.mkdir(parents=True, exist_ok=True)

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

    def create_archive(self, archive_name: str, source_paths: list[Path], base_path: Path | None = None) -> Path:
        archive_path = self._base_dir / archive_name
        try:
            with tarfile.open(archive_path, "w:gz") as tar:
                for source in source_paths:
                    if not source.exists():
                        continue
                    arcname = self._arcname_for(source, base_path)
                    tar.add(source, arcname=arcname)
        except (OSError, tarfile.TarError) as exc:
            raise ArchiveStoreError(f"Echec de creation de l'archive {archive_name} : {exc}") from exc
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
            raise ArchiveStoreError(f"Echec d'extraction de l'archive {archive_path} : {exc}") from exc

    def list_archives(self, pattern: str = "*.tar.gz") -> list[Path]:
        return sorted(self._base_dir.glob(pattern))

    def get_archive_info(self, archive_path: Path) -> dict:
        try:
            stat = archive_path.stat()
        except OSError as exc:
            raise ArchiveStoreError(f"Echec de lecture des informations de {archive_path} : {exc}") from exc
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
