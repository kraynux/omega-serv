# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Regles d'audit service avec vraie I/O (plan corrige §5.5).

SVC-001 (reformulee) : le refus de demarrage en root est deja une porte
bloquante reelle (core/platform_info.py::running_as_root(), verifiee
dans cmd_serve) - `omega-serv serve` ne peut structurellement pas
tourner en root. Le seul axe qui reste utile est de verifier que
l'UNITE SYSTEMD INSTALLEE (si presente) declare bien un User/Group
dedie plutot que d'omettre ces directives."""
from __future__ import annotations

from pathlib import Path

from omega_serv.domain.config.entities import OmegaServConfig
from omega_serv.domain.security.audit.entities import AuditFinding, Severity
from omega_serv.ports.filesystem_port import FilesystemPort

_MAX_LOG_SIZE_BYTES = 100 * 1024 * 1024


def check_service_unit(unit_path: Path, filesystem: FilesystemPort) -> list[AuditFinding]:
    """SVC-001. `unit_path` est fourni par l'appelant (CLI, memes
    conventions --service-name/--unit-path que `omega-serv service
    install/uninstall`) - rien a verifier si l'unite n'est pas
    installee via ce mecanisme (deploiement hors systemd, ou pas encore
    installe)."""
    if not filesystem.exists(unit_path):
        return []

    content = filesystem.read_text(unit_path)
    if "User=" not in content or "Group=" not in content:
        return [AuditFinding(
            rule_id="SVC-001", rule_name="Unite systemd sans User/Group dedie",
            severity=Severity.HIGH, category="service",
            message=f"{unit_path} ne declare pas User=/Group= explicitement.",
            recommendation=(
                "Regenerer l'unite via `omega-serv service install` (qui les impose deja "
                "par defaut, voir domain/services/systemd_unit.py)."
            ),
            details={"unit_path": str(unit_path)},
        )]
    return []


def check_log_sizes(config: OmegaServConfig, project_root: Path, filesystem: FilesystemPort) -> list[AuditFinding]:
    """SVC-002 : lit les vrais champs (logs.rotation.enabled,
    logs.access/error/waf_alerts/uploads), pas un dict 'logs' arbitraire
    avec des cles '*_path'."""
    findings: list[AuditFinding] = []

    if not config.logs.rotation.enabled:
        findings.append(AuditFinding(
            rule_id="SVC-002", rule_name="Rotation des logs desactivee",
            severity=Severity.MEDIUM, category="service",
            message="logs.rotation.enabled = false",
            recommendation="Activer la rotation (logs.rotation.enabled = true).",
        ))

    for label, relative in (
        ("access", config.logs.access), ("error", config.logs.error),
        ("waf_alerts", config.logs.waf_alerts), ("uploads", config.logs.uploads),
    ):
        path = project_root / relative
        if not filesystem.exists(path):
            continue
        size = filesystem.file_size(path)
        if size > _MAX_LOG_SIZE_BYTES:
            findings.append(AuditFinding(
                rule_id="SVC-002", rule_name=f"Log {label} volumineux",
                severity=Severity.MEDIUM, category="service",
                message=f"{path} : {size / 1024 / 1024:.1f} Mo",
                recommendation="Verifier que la rotation fonctionne reellement (logs.rotation.max_bytes).",
                details={"path": str(path), "size_bytes": size},
            ))

    return findings
