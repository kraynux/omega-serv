# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Cas d'usage `omega-serv certs revoke` (doc TLS §5, menu "Revoquer un
certificat (CA locale)"). Bascule minimale : marque l'entree
correspondante comme revoquee dans index.txt (infrastructure/tls/
openssl_certificate_tool.py::revoke_certificate) - pas de generation de
CRL distribuee en V1."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from omega_serv.ports.certificate_tool_port import CertificateToolPort
from omega_serv.ports.filesystem_port import FilesystemPort


@dataclass(frozen=True)
class RevokeCertificateResult:
    success: bool
    message: str


def revoke_certificate(
    cert_path: Path,
    ca_key_path: Path,
    ca_cert_path: Path,
    ca_key_password: str,
    index_path: Path,
    tool: CertificateToolPort,
    filesystem: FilesystemPort,
) -> RevokeCertificateResult:
    for label, path in (
        ("certificat a revoquer", cert_path), ("cle de CA", ca_key_path),
        ("certificat de CA", ca_cert_path), ("index de la CA", index_path),
    ):
        if not filesystem.exists(path):
            return RevokeCertificateResult(False, f"{label} introuvable : {path}")

    tool.revoke_certificate(cert_path, ca_key_path, ca_cert_path, ca_key_password, index_path)
    return RevokeCertificateResult(True, f"Certificat {cert_path} marque comme revoque dans {index_path}")
