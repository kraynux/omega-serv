"""Exceptions du module WAF."""
from __future__ import annotations

from omega_serv.core.exceptions import OmegaServError


class WafError(OmegaServError):
    """Racine des erreurs WAF."""


class WafRuleLoadError(WafError):
    """Un fichier de pack de regles est absent, illisible ou
    syntaxiquement invalide (JSON malforme)."""


class WafRuleValidationError(WafError):
    """Un pack de regles chargeable ne respecte pas la structure
    attendue (domain/security/waf/rule_validation.py)."""

    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__("; ".join(errors))
