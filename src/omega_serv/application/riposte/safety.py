"""Exclusions appliquees par RIPOSTE (OMEGA-SERV_PLAN-DETAILLE_RIPOSTE.md §3.5, §7) : EXACTEMENT celles du
WAF telles que le serveur les applique (application/server/start_server.py : `effective_never_auto_block`,
qui n'exempte le loopback que si le proxy de confiance est actif - sinon tout Internet, vu comme
127.0.0.1 derriere un proxy local, serait exempte), plus les exemptions propres a RIPOSTE. Jamais une
seconde liste recopiee."""
from __future__ import annotations

from omega_serv.domain.config.entities import OmegaServConfig
from omega_serv.domain.security.riposte.config import RiposteConfig
from omega_serv.domain.security.waf.config import parse_waf_config
from omega_serv.domain.security.waf.reputation import effective_never_auto_block


def riposte_exempt_networks(config: OmegaServConfig, riposte_config: RiposteConfig) -> tuple[str, ...]:
    waf_option = config.options.get("waf")
    waf_config = parse_waf_config(waf_option.settings if waf_option is not None else {})
    waf_networks = effective_never_auto_block(
        waf_config.reputation.never_auto_block, config.option_enabled("trusted_proxy"),
    )
    return (*waf_networks, *(n for n in riposte_config.exemptions if n not in waf_networks))
