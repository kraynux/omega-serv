# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Cas d'usage `omega-serv certs verify/show/check-expiry` (doc TLS
§10). Combine l'inspection X.509, la correspondance cle/certificat et
les permissions de la cle en un seul rapport - le CLI n'a plus qu'a
l'afficher."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from omega_serv.domain.security.tls.entities import CertificateInfo
from omega_serv.ports.certificate_tool_port import CertificateToolPort
from omega_serv.ports.clock_port import ClockPort
from omega_serv.ports.filesystem_port import FilesystemPort

_DEFAULT_WARN_DAYS = 30


@dataclass(frozen=True)
class CertificateReport:
    info: CertificateInfo
    key_matches: bool | None
    key_mode: int | None
    is_expired: bool
    days_remaining: int
    expiring_soon: bool


def inspect_certificate_report(
    cert_path: Path,
    key_path: Path,
    tool: CertificateToolPort,
    filesystem: FilesystemPort,
    clock: ClockPort,
    warn_days: int = _DEFAULT_WARN_DAYS,
) -> CertificateReport:
    info = tool.inspect_certificate(cert_path)
    key_matches = tool.keys_match(key_path, cert_path) if filesystem.exists(key_path) else None
    key_mode = filesystem.file_mode(key_path) if filesystem.exists(key_path) else None
    now = clock.now()
    days_remaining = info.days_remaining(now)

    return CertificateReport(
        info=info,
        key_matches=key_matches,
        key_mode=key_mode,
        is_expired=info.is_expired(now),
        days_remaining=days_remaining,
        expiring_soon=days_remaining < warn_days,
    )
