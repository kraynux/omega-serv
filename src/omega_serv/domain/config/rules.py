"""Detection de conflits de configuration (spec §6.4).

Distinct de validation.py (structurel : est-ce que CETTE config seule
est bien formee) : ici, on detecte des incoherences entre options et
reste de la configuration. Perimetre volontairement restreint a ce qui
est reellement verifiable maintenant - WAF (Phase 5), auth (Phase 7),
dirlisting (Phase 4) et TLS/HSTS (Phase 6) n'existent pas encore comme
champs de configuration concrets : leurs conflits d'exemple dans la
spec (§6.4) seront ajoutes ici au fur et a mesure que ces phases
introduisent les champs correspondants, jamais anticipes a vide."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from omega_serv.domain.config.entities import OmegaServConfig

Severity = Literal["error", "warning"]


@dataclass(frozen=True)
class ConfigConflict:
    severity: Severity
    message: str


def detect_conflicts(config: OmegaServConfig) -> list[ConfigConflict]:
    conflicts: list[ConfigConflict] = []

    trusted_proxy = config.options.get("trusted_proxy")
    if trusted_proxy is not None and trusted_proxy.enabled:
        networks = trusted_proxy.settings.get("trusted_networks")
        if not networks:
            conflicts.append(ConfigConflict(
                "error",
                "trusted_proxy.enabled=true sans trusted_networks defini (spec §6.4, §19.3)",
            ))

    return conflicts


def has_blocking_conflicts(conflicts: list[ConfigConflict]) -> bool:
    return any(c.severity == "error" for c in conflicts)
