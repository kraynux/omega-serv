# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Cas d'usage `omega-serv certs generate-ca` (doc TLS §7.3 etapes 1-5).
Meme squelette que generate_self_signed.py (valider -> sauvegarder
l'existant -> appeler l'outil -> permissions), avec deux differences :
le dossier `secure/certificates/ca/` doit etre 0700 (doc TLS §4.1, "la
cle de CA la plus sensible"), et serial.txt/index.txt sont sauvegardes
et proteges au meme titre que la cle."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from omega_serv.domain.security.tls.entities import CaParams
from omega_serv.domain.security.tls.validation import validate_ca_params
from omega_serv.ports.certificate_tool_port import CertificateToolPort
from omega_serv.ports.clock_port import ClockPort
from omega_serv.ports.filesystem_port import FilesystemPort


@dataclass(frozen=True)
class GenerateCaResult:
    success: bool
    message: str


def generate_ca_certificate(
    params: CaParams,
    key_path: Path,
    cert_path: Path,
    serial_path: Path,
    index_path: Path,
    tool: CertificateToolPort,
    filesystem: FilesystemPort,
    clock: ClockPort,
    backups_dir: Path,
) -> GenerateCaResult:
    errors = validate_ca_params(params)
    if errors:
        return GenerateCaResult(False, "; ".join(errors))

    existing = [p for p in (key_path, cert_path, serial_path, index_path) if filesystem.exists(p)]
    if existing:
        backup_dir = backups_dir / clock.now().strftime("%Y%m%d-%H%M%S")
        for path in existing:
            filesystem.copy_file(path, backup_dir / path.name)

    filesystem.make_directory(key_path.parent, mode=0o700)
    tool.generate_ca(params, key_path, cert_path, serial_path, index_path)
    filesystem.set_file_mode(key_path, 0o600)
    filesystem.set_file_mode(cert_path, 0o644)
    filesystem.set_file_mode(serial_path, 0o600)
    filesystem.set_file_mode(index_path, 0o600)

    return GenerateCaResult(
        True, f"CA locale generee : {cert_path} (cle : {key_path}, mode 0600, dossier 0700)"
    )
