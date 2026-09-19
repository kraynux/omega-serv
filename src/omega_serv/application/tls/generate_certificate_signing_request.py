"""Cas d'usage `omega-serv certs generate-csr` (doc TLS §7.3 etape 6).
Meme squelette que generate_self_signed.py - la CSR elle-meme n'est pas
un secret (0644, doc TLS §4.1), seule la cle privee generee avec elle
l'est (0600)."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from omega_serv.domain.security.tls.entities import CsrParams
from omega_serv.domain.security.tls.validation import validate_csr_params
from omega_serv.ports.certificate_tool_port import CertificateToolPort
from omega_serv.ports.clock_port import ClockPort
from omega_serv.ports.filesystem_port import FilesystemPort


@dataclass(frozen=True)
class GenerateCsrResult:
    success: bool
    message: str


def generate_certificate_signing_request(
    params: CsrParams,
    key_path: Path,
    csr_path: Path,
    tool: CertificateToolPort,
    filesystem: FilesystemPort,
    clock: ClockPort,
    backups_dir: Path,
) -> GenerateCsrResult:
    errors = validate_csr_params(params)
    if errors:
        return GenerateCsrResult(False, "; ".join(errors))

    if filesystem.exists(key_path) or filesystem.exists(csr_path):
        backup_dir = backups_dir / clock.now().strftime("%Y%m%d-%H%M%S")
        if filesystem.exists(key_path):
            filesystem.copy_file(key_path, backup_dir / key_path.name)
        if filesystem.exists(csr_path):
            filesystem.copy_file(csr_path, backup_dir / csr_path.name)

    tool.generate_csr(params, key_path, csr_path)
    filesystem.set_file_mode(key_path, 0o600)
    filesystem.set_file_mode(csr_path, 0o644)

    return GenerateCsrResult(True, f"CSR generee : {csr_path} (cle : {key_path}, mode 0600)")
