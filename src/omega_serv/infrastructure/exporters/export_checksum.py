"""Sidecar de checksum SHA-256 pour les exports IoC/rapport
(plan_active_defense_omega_serv.md, Phase 6 : "signatures ou hachage des
exports"). Format `sha256sum` standard (`<hash>  <nom-de-fichier>\\n`),
verifiable avec l'outil `sha256sum -c` habituel - jamais un format
maison. Partage par les 3 exporters (JSON/CSV/Markdown), seuil de 3
repetitions reelles atteint (charte du projet)."""
from __future__ import annotations

from pathlib import Path

from omega_serv.domain.security.active_defense.policies import hash_payload
from omega_serv.ports.filesystem_port import FilesystemPort


def write_export_checksum(filesystem: FilesystemPort, export_path: Path, content: str) -> Path:
    digest = hash_payload(content.encode("utf-8"))
    checksum_path = export_path.with_name(export_path.name + ".sha256")
    filesystem.atomic_write_text(checksum_path, f"{digest}  {export_path.name}\n")
    return checksum_path
