"""Cas d'usage `omega-serv certs sign-csr` (doc TLS §7.3 etapes 7-8).
Ne valide pas de parametres domaine (la CSR est deja construite) -
seule verification faite ici : les 4 fichiers d'entree (CSR, cle/
certificat de CA) existent reellement, avant d'appeler l'outil."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from omega_serv.ports.certificate_tool_port import CertificateToolPort
from omega_serv.ports.clock_port import ClockPort
from omega_serv.ports.filesystem_port import FilesystemPort


@dataclass(frozen=True)
class SignCsrResult:
    success: bool
    message: str


def sign_certificate_signing_request(
    csr_path: Path,
    ca_key_path: Path,
    ca_cert_path: Path,
    ca_key_password: str,
    serial_path: Path,
    index_path: Path,
    validity_days: int,
    out_cert_path: Path,
    tool: CertificateToolPort,
    filesystem: FilesystemPort,
    clock: ClockPort,
    backups_dir: Path,
    out_fullchain_path: Path | None = None,
) -> SignCsrResult:
    for label, path in (("CSR", csr_path), ("cle de CA", ca_key_path), ("certificat de CA", ca_cert_path)):
        if not filesystem.exists(path):
            return SignCsrResult(False, f"{label} introuvable : {path}")
    if validity_days <= 0:
        return SignCsrResult(False, "validity_days doit etre strictement positif")

    if filesystem.exists(out_cert_path):
        backup_dir = backups_dir / clock.now().strftime("%Y%m%d-%H%M%S")
        filesystem.copy_file(out_cert_path, backup_dir / out_cert_path.name)

    tool.sign_csr(
        csr_path, ca_key_path, ca_cert_path, ca_key_password, serial_path, index_path, validity_days, out_cert_path
    )
    filesystem.set_file_mode(out_cert_path, 0o644)

    message = f"Certificat signe par la CA locale : {out_cert_path}"
    if out_fullchain_path is not None:
        tool.build_fullchain(out_cert_path, ca_cert_path, out_fullchain_path)
        filesystem.set_file_mode(out_fullchain_path, 0o644)
        message += f" (chaine complete : {out_fullchain_path})"

    return SignCsrResult(True, message)
