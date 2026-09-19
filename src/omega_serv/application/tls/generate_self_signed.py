"""Cas d'usage `omega-serv certs generate-self-signed` (doc TLS §6,
"Resume avant creation" - la confirmation elle-meme est une
responsabilite CLI, ce cas d'usage effectue l'operation une fois
confirmee). Sauvegarde les fichiers existants avant remplacement (doc
TLS §9.2) sous `var/backups/certificates/YYYYMMDD-HHMMSS/`."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from omega_serv.domain.security.tls.entities import SelfSignedCertParams
from omega_serv.domain.security.tls.validation import validate_self_signed_params
from omega_serv.ports.certificate_tool_port import CertificateToolPort
from omega_serv.ports.clock_port import ClockPort
from omega_serv.ports.filesystem_port import FilesystemPort


@dataclass(frozen=True)
class GenerateSelfSignedResult:
    success: bool
    message: str


def generate_self_signed_certificate(
    params: SelfSignedCertParams,
    key_path: Path,
    cert_path: Path,
    tool: CertificateToolPort,
    filesystem: FilesystemPort,
    clock: ClockPort,
    backups_dir: Path,
) -> GenerateSelfSignedResult:
    errors = validate_self_signed_params(params)
    if errors:
        return GenerateSelfSignedResult(False, "; ".join(errors))

    if filesystem.exists(key_path) or filesystem.exists(cert_path):
        backup_dir = backups_dir / clock.now().strftime("%Y%m%d-%H%M%S")
        if filesystem.exists(key_path):
            filesystem.copy_file(key_path, backup_dir / key_path.name)
        if filesystem.exists(cert_path):
            filesystem.copy_file(cert_path, backup_dir / cert_path.name)

    tool.generate_self_signed(params, key_path, cert_path)
    filesystem.set_file_mode(key_path, 0o600)
    filesystem.set_file_mode(cert_path, 0o644)

    return GenerateSelfSignedResult(True, f"Certificat auto-signe genere : {cert_path} (cle : {key_path}, mode 0600)")
