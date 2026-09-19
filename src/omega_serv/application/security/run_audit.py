"""Cas d'usage `omega-serv audit security` (spec §26, plan corrige -
voir OMEGA-SERV_PLAN-DETAILLE_SYSTEME_AUDIT.md).

Reexecute les validateurs deja bloquants du projet (`validate_config`,
`validate_config_environment`) plutot que de les dupliquer - un
probleme qui bloquerait deja `serve`/`config check` reste rapporte ici
en CRITICAL, une seule source de verite (plan corrige §0/§4.1)."""
from __future__ import annotations

from pathlib import Path

from omega_serv.application.config.validate_config import validate_config_environment
from omega_serv.domain.config.entities import OmegaServConfig
from omega_serv.domain.config.validation import validate_config
from omega_serv.domain.security.audit.entities import AuditFinding, AuditResult, Severity
from omega_serv.domain.security.audit.rules import PURE_RULES
from omega_serv.infrastructure.security.permission_rules import check_permissions
from omega_serv.infrastructure.security.service_rules import check_log_sizes, check_service_unit
from omega_serv.infrastructure.security.tls_rules import check_certificate_expiry
from omega_serv.infrastructure.security.waf_mode_rule import check_waf_log_only_duration
from omega_serv.ports.certificate_tool_port import CertificateToolPort
from omega_serv.ports.clock_port import ClockPort
from omega_serv.ports.filesystem_port import FilesystemPort


def run_audit(
    config: OmegaServConfig,
    config_path: Path,
    project_root: Path,
    filesystem: FilesystemPort,
    certificate_tool: CertificateToolPort,
    clock: ClockPort,
    service_unit_path: Path | None = None,
    self_signed_public_bind_confirmed: bool = False,
    auth_without_tls_confirmed: bool = False,
) -> AuditResult:
    findings: list[AuditFinding] = []

    for message in validate_config(config):
        findings.append(AuditFinding(
            rule_id="CORE-STRUCT", rule_name="Configuration structurellement invalide",
            severity=Severity.CRITICAL, category="core", message=message,
            recommendation="Corriger la configuration (voir `omega-serv config check`).",
        ))

    for message in validate_config_environment(
        config, filesystem, project_root, certificate_tool,
        self_signed_public_bind_confirmed, auth_without_tls_confirmed,
    ):
        findings.append(AuditFinding(
            rule_id="CORE-ENV", rule_name="Porte d'environnement bloquante violee",
            severity=Severity.CRITICAL, category="core", message=message,
            recommendation="Corriger avant de demarrer le serveur (voir `omega-serv config check`).",
        ))

    for rule in PURE_RULES:
        findings.extend(rule(config))

    findings.extend(check_permissions(config, project_root, filesystem))
    findings.extend(check_certificate_expiry(config, project_root, filesystem, certificate_tool, clock))
    findings.extend(check_log_sizes(config, project_root, filesystem))
    findings.extend(check_waf_log_only_duration(config, project_root, filesystem, clock))
    if service_unit_path is not None:
        findings.extend(check_service_unit(service_unit_path, filesystem))

    return AuditResult(timestamp=clock.now(), config_path=str(config_path), findings=tuple(findings))
