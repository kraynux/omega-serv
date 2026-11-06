"""Cas d'usage : `omega-serv option enable/disable` (spec §8.2)."""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from omega_serv.core.i18n import _
from omega_serv.domain.config.entities import OmegaServConfig
from omega_serv.domain.config.option import KNOWN_OPTION_NAMES, Option
from omega_serv.ports.filesystem_port import FilesystemPort

WAF_RULES_DIR = Path("secure", "waf", "rules")


@dataclass
class ManageOptionResult:
    success: bool
    new_config: OmegaServConfig | None
    message: str


def waf_rule_packs_present(filesystem: FilesystemPort, project_root: Path) -> tuple[str, ...]:
    """Packs de regles reellement presents sous secure/waf/rules/ (chemins relatifs, tries)."""
    return tuple(str(path.relative_to(project_root))
                 for path in filesystem.list_json_files(project_root / WAF_RULES_DIR))


def set_option_enabled(
    current_config: OmegaServConfig, option_name: str, enabled: bool, waf_rule_packs: Sequence[str] = (),
) -> ManageOptionResult:
    """`waf_rule_packs` : packs proposes a une PREMIERE activation du WAF (aucun pack ni liste de
    mots-cles encore choisis) - sans eux, la configuration serait refusee au demarrage. Le mode reste
    celui configure (log-only par defaut) : activer ne se met jamais a bloquer tout seul."""
    if option_name not in KNOWN_OPTION_NAMES:
        return ManageOptionResult(False, None, _("Option inconnue : {option_name} (connues : {value})").format(option_name=option_name, value=sorted(KNOWN_OPTION_NAMES)))

    existing = current_config.options.get(option_name, Option(name=option_name))
    settings = dict(existing.settings)
    rules = dict(settings.get("rules") or {})
    packs_added = 0
    if enabled and option_name == "waf" and waf_rule_packs and not rules.get("paths") and not rules.get("keyword_lists"):
        rules["paths"] = list(waf_rule_packs)
        settings["rules"] = rules
        packs_added = len(waf_rule_packs)
    updated_options = dict(current_config.options)
    updated_options[option_name] = Option(name=option_name, enabled=enabled, settings=settings)

    data = current_config.to_dict()
    data["options"] = {name: option.to_dict() for name, option in updated_options.items()}
    new_config = OmegaServConfig.from_dict(data)

    verb = _("activée") if enabled else _("désactivée")
    message = _("Option '{option_name}' {verb}.").format(option_name=option_name, verb=verb)
    if packs_added:
        mode = str(settings.get("mode", "log-only"))
        message += " " + _("{count} pack(s) de règles ajouté(s) (secure/waf/rules/). Mode {mode}").format(
            count=packs_added, mode=mode)
        if mode != "block":
            message += _(" : rien n'est bloqué, les attaques sont seulement journalisées.")
        else:
            message += "."
    return ManageOptionResult(True, new_config, message)
