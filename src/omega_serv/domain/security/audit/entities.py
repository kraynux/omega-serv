"""Entites de l'audit de securite (spec §26, plan corrige - voir
OMEGA-SERV_PLAN-DETAILLE_SYSTEME_AUDIT.md §3).

`Severity` distinct de domain/security/waf/entities.py::Severity
(LOW/MEDIUM/HIGH/CRITICAL, sans INFO) : les deux enumerations couvrent
des domaines differents (une decision de blocage temps reel pour le
WAF, un rapport consultatif hors ligne pour l'audit) et ne sont jamais
importees dans le meme contexte - pas de collision de nom reelle,
seulement une similitude de vocabulaire (decision actee, plan corrige
§3.1)."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class Severity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


_SEVERITY_ORDER: tuple[Severity, ...] = (
    Severity.CRITICAL, Severity.HIGH, Severity.MEDIUM, Severity.LOW, Severity.INFO,
)


def severity_at_least(severity: Severity, minimum: Severity) -> bool:
    """True si `severity` est au moins aussi grave que `minimum` (ordre
    CRITICAL > HIGH > MEDIUM > LOW > INFO) - utilise par le filtre
    --min-severity du CLI."""
    return _SEVERITY_ORDER.index(severity) <= _SEVERITY_ORDER.index(minimum)


@dataclass(frozen=True)
class AuditFinding:
    rule_id: str
    rule_name: str
    severity: Severity
    category: str
    message: str
    recommendation: str
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "rule_name": self.rule_name,
            "severity": self.severity.value,
            "category": self.category,
            "message": self.message,
            "recommendation": self.recommendation,
            "details": self.details,
        }


@dataclass(frozen=True)
class AuditResult:
    timestamp: datetime
    config_path: str
    findings: tuple[AuditFinding, ...]

    @property
    def summary(self) -> dict[str, int]:
        return {sev.value: sum(1 for f in self.findings if f.severity == sev) for sev in Severity}

    @property
    def is_secure(self) -> bool:
        return not any(f.severity in (Severity.CRITICAL, Severity.HIGH) for f in self.findings)

    @property
    def exit_code(self) -> int:
        """Code retour du CLI (plan corrige §7.3) : 1 si au moins un
        CRITICAL, 2 si au moins un HIGH (sans CRITICAL), 0 sinon."""
        if any(f.severity == Severity.CRITICAL for f in self.findings):
            return 1
        if any(f.severity == Severity.HIGH for f in self.findings):
            return 2
        return 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "config_path": self.config_path,
            "findings": [f.to_dict() for f in self.findings],
            "summary": self.summary,
            "is_secure": self.is_secure,
        }
