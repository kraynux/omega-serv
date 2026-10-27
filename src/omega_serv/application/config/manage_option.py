"""Cas d'usage : `omega-serv option enable/disable` (spec §8.2)."""
from __future__ import annotations

from dataclasses import dataclass

from omega_serv.core.i18n import _
from omega_serv.domain.config.entities import OmegaServConfig
from omega_serv.domain.config.option import KNOWN_OPTION_NAMES, Option


@dataclass
class ManageOptionResult:
    success: bool
    new_config: OmegaServConfig | None
    message: str


def set_option_enabled(current_config: OmegaServConfig, option_name: str, enabled: bool) -> ManageOptionResult:
    if option_name not in KNOWN_OPTION_NAMES:
        return ManageOptionResult(False, None, _("Option inconnue : {option_name} (connues : {value})").format(option_name=option_name, value=sorted(KNOWN_OPTION_NAMES)))

    existing = current_config.options.get(option_name, Option(name=option_name))
    updated_options = dict(current_config.options)
    updated_options[option_name] = Option(name=option_name, enabled=enabled, settings=existing.settings)

    data = current_config.to_dict()
    data["options"] = {name: option.to_dict() for name, option in updated_options.items()}
    new_config = OmegaServConfig.from_dict(data)

    verb = _("activée") if enabled else _("désactivée")
    return ManageOptionResult(True, new_config, _("Option '{option_name}' {verb}.").format(option_name=option_name, verb=verb))
