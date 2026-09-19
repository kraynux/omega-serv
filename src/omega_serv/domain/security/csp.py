"""CSP de base (spec §12.3/§12.4).

Politique stricte de depart pour un site statique minimal - la CSP par
zone (spec §12.4, plusieurs politiques par prefixe d'URL) est un
chantier ulterieur, une fois le concept de zone/ZoneResolver construit
(voir OMEGA-SERV_PLAN_DEVELOPPEMENT.md §6). Ce module se limite a la
politique globale par defaut."""
from __future__ import annotations

DEFAULT_CSP_POLICY = (
    "default-src 'none'; base-uri 'self'; form-action 'self'; "
    "frame-ancestors 'none'; img-src 'self' data:; style-src 'self'; "
    "script-src 'self'; font-src 'self'; connect-src 'self'; object-src 'none'"
)


def csp_header_name(csp_mode: str) -> str:
    """`Content-Security-Policy-Report-Only` avant d'imposer une CSP sur
    un site existant (spec §12.5) - les violations sont journalisees
    sans jamais bloquer le rendu."""
    if csp_mode == "report-only":
        return "Content-Security-Policy-Report-Only"
    return "Content-Security-Policy"
