"""Implementation concrete de FilesystemPort - seul point du module
filesystem/ qui touche reellement pathlib/os (charte : infrastructure/
est la seule couche autorisee a faire de l'I/O disque)."""
from __future__ import annotations

import os
import shutil
import threading
from pathlib import Path


class LocalFilesystem:
    """Implementation reelle de ports.filesystem_port.FilesystemPort."""

    def exists(self, path: Path) -> bool:
        return path.exists()

    def is_file(self, path: Path) -> bool:
        return path.is_file()

    def is_dir(self, path: Path) -> bool:
        return path.is_dir()

    def read_text(self, path: Path) -> str:
        return path.read_text(encoding="utf-8")

    def read_bytes(self, path: Path) -> bytes:
        return path.read_bytes()

    def write_bytes(self, path: Path, content: bytes) -> None:
        path.write_bytes(content)

    def file_size(self, path: Path) -> int:
        return path.stat().st_size

    def file_mtime(self, path: Path) -> float:
        return path.stat().st_mtime

    def write_text(self, path: Path, content: str) -> None:
        path.write_text(content, encoding="utf-8")

    def atomic_write_text(self, path: Path, content: str) -> None:
        # Nom temporaire UNIQUE par appel (2026-09-29, incident reel :
        # boucle de crash systemd, PermissionError persistante sur
        # var/run/omega-serv.pid.tmp malgre var/ deja partage avec le
        # groupe dedie) : l'ancien nom fixe (`<nom>.tmp`) est PARTAGE par
        # tous les appelants, quel que soit le compte qui ecrit - si ce
        # fichier temporaire a deja ete cree UNE SEULE FOIS par un autre
        # compte (ex. l'utilisateur interactif lancant `serve` a la main
        # pendant un depannage), `open(tmp_path, "w")` (troncature d'un
        # fichier EXISTANT) exige une permission d'ECRITURE SUR CE
        # FICHIER precis pour tout compte suivant - contrairement a
        # `os.replace()` juste apres, qui ne regarde LUI que les droits
        # du DOSSIER (rename POSIX, jamais les permissions du fichier
        # cible). Un suffixe pid+thread rend chaque ecriture atomique
        # totalement independante des tentatives precedentes, d'ou
        # qu'elles viennent - la creation du fichier temporaire
        # redevient alors une simple creation dans le dossier (deja
        # partage en ecriture avec le groupe, voir infrastructure/
        # services/systemd_service_manager.py::grant_directory_access),
        # jamais une troncature d'un fichier existant potentiellement
        # possede par un autre compte.
        tmp_path = path.with_name(f"{path.name}.{os.getpid()}-{threading.get_ident()}.tmp")
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)

    def copy_file(self, source: Path, destination: Path) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)

    def copy_directory(self, source: Path, destination: Path) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source, destination)

    def make_directory(self, path: Path, mode: int = 0o750) -> None:
        path.mkdir(parents=True, exist_ok=True, mode=mode)

    def delete_file(self, path: Path) -> None:
        path.unlink()

    def delete_directory(self, path: Path) -> None:
        shutil.rmtree(path)

    def file_mode(self, path: Path) -> int:
        return path.stat().st_mode & 0o777

    def set_file_mode(self, path: Path, mode: int) -> None:
        path.chmod(mode)

    def resolve_real_path(self, path: Path) -> Path:
        return path.resolve()

    def list_json_files(self, directory: Path) -> list[Path]:
        if not directory.is_dir():
            return []
        return sorted(directory.glob("*.json"))

    def list_directory_entries(self, directory: Path) -> list[str]:
        if not directory.is_dir():
            return []
        return sorted(entry.name for entry in directory.iterdir())
