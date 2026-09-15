# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Regle d'audit TLS avec vraie I/O (plan corrige §6) - TLS-002,
certificat proche de l'expiration. L'expiration REELLE (deja passee)
est deja une porte bloquante au demarrage
(domain/security/tls/validation.py::validate_tls_startup, reexecutee en
CRITICAL par application/security/run_audit.py) - cette regle ajoute
seulement l'avertissement "expire bientot", pas encore bloquant.

Reutilise application/tls/inspect_certificate.py::inspect_certificate_report
(deja construit pour `omega-serv certs check-expiry`) plutot que de
dupliquer le calcul de jours restants."""
from __future__ import annotations

from pathlib import Path

from omega_serv.application.tls.inspect_certificate import inspect_certificate_report
from omega_serv.domain.config.entities import OmegaServConfig
from omega_serv.domain.security.audit.entities import AuditFinding, Severity
from omega_serv.domain.security.tls.exceptions import CertificateToolError
from omega_serv.ports.certificate_tool_port import CertificateToolPort
from omega_serv.ports.clock_port import ClockPort
from omega_serv.ports.filesystem_port import FilesystemPort

_WARN_DAYS = 30


def check_certificate_expiry(
    config: OmegaServConfig,
    project_root: Path,
    filesystem: FilesystemPort,
    certificate_tool: CertificateToolPort,
    clock: ClockPort,
) -> list[AuditFinding]:
    if not (config.tls.enabled and config.tls.mode == "direct"):
        return []

    cert_path = project_root / config.tls.certificate_path
    key_path = project_root / config.tls.private_key_path
    if not filesystem.exists(cert_path):
        return []

    try:
        report = inspect_certificate_report(cert_path, key_path, certificate_tool, filesystem, clock, warn_days=_WARN_DAYS)
    except CertificateToolError:
        return []  # deja rapporte en CRITICAL par la porte bloquante reexecutee (CORE-ENV)

    if not report.is_expired and report.expiring_soon:
        return [AuditFinding(
            rule_id="TLS-002", rule_name="Certificat TLS expire bientot",
            severity=Severity.MEDIUM, category="tls",
            message=f"Expire dans {report.days_remaining} jours ({cert_path}).",
            recommendation="Prevoir le renouvellement (`omega-serv certs generate-self-signed` ou remplacement).",
            details={"certificate_path": str(cert_path), "days_remaining": report.days_remaining},
        )]
    return []
