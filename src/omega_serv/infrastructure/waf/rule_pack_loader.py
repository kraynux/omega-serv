"""Chargement des packs de regles WAF depuis le disque (doc WAF,
"Repartition Clean Architecture" : infrastructure/waf/ porte la
compilation/chargement de regles). Delegue tout le parsing/validation
structurel a domain/security/waf/{rule_validation,signature_engine}.py
- ce module ne fait que l'I/O et la compilation regex finale."""
from __future__ import annotations

import json
from pathlib import Path

from omega_serv.core.i18n import _
from omega_serv.domain.security.waf.exceptions import WafRuleLoadError, WafRuleValidationError
from omega_serv.domain.security.waf.rule_validation import parse_rule_pack, validate_rule_pack
from omega_serv.domain.security.waf.signature_engine import CompiledRulePack, compile_rule_pack
from omega_serv.ports.filesystem_port import FilesystemPort


def load_rule_pack(filesystem: FilesystemPort, path: Path) -> CompiledRulePack:
    if not filesystem.exists(path):
        raise WafRuleLoadError(_("Fichier de pack de règles introuvable : {path}").format(path=path))
    try:
        raw = filesystem.read_text(path)
    except OSError as e:
        raise WafRuleLoadError(_("Impossible de lire {path} : {e}").format(path=path, e=e)) from e
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise WafRuleLoadError(_("JSON invalide dans {path} : {e}").format(path=path, e=e)) from e
    if not isinstance(data, dict):
        raise WafRuleLoadError(_("{path} ne contient pas un objet JSON à la racine").format(path=path))

    pack = parse_rule_pack(data)
    errors = validate_rule_pack(pack)
    if errors:
        raise WafRuleValidationError(errors)
    return compile_rule_pack(pack)


def load_rule_packs(filesystem: FilesystemPort, paths: tuple[Path, ...]) -> tuple[CompiledRulePack, ...]:
    return tuple(load_rule_pack(filesystem, path) for path in paths)
