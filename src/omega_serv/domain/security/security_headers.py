"""En-tetes de securite generiques (spec §12.1) et application au
pipeline de reponse.

HSTS (doc TLS §13) : n'est JAMAIS emis si `tls_enabled=False`, meme si
`security.hsts_enabled` est active dans la configuration - double
protection en plus de la porte de validation bloquante
(domain/security/tls/validation.py::validate_tls_startup) qui refuse
deja de demarrer dans ce cas ; ce module ne fait pas confiance a la
configuration seule pour une garantie aussi sensible.

`Cross-Origin-Embedder-Policy` (retour utilisateur 2026-10-10, scan
externe signalant son absence) : volontairement PAS dans
`STATIC_SECURITY_HEADERS` ci-dessous - contrairement a COOP/CORP (deja
`same-origin` partout, aucun risque reel de casser un site), une valeur
stricte (`require-corp`/`credentialless`) peut bloquer des ressources
cross-origin que ce serveur generique ne connait pas a l'avance. Toujours
emis (jamais absent - `security.coep_mode`, defaut "unsafe-none" sur
tous les profils meme hardened), pour qu'un scanner externe voie un
choix explicite plutot qu'une absence."""
from __future__ import annotations

from omega_serv.domain.config.entities import SecurityConfig
from omega_serv.domain.http.response import HttpResponse
from omega_serv.domain.security.csp import csp_header_name, csp_policy_for_path


def _build_hsts_value(security: SecurityConfig) -> str:
    parts = [f"max-age={security.hsts_max_age}"]
    if security.hsts_include_subdomains:
        parts.append("includeSubDomains")
    if security.hsts_preload:
        parts.append("preload")
    return "; ".join(parts)

STATIC_SECURITY_HEADERS: dict[str, str] = {
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "X-Frame-Options": "SAMEORIGIN",
    "Permissions-Policy": (
        "geolocation=(), microphone=(), camera=(), payment=(), "
        "usb=(), bluetooth=(), clipboard-read=()"
    ),
    "Cross-Origin-Opener-Policy": "same-origin",
    "Cross-Origin-Resource-Policy": "same-origin",
    "X-Permitted-Cross-Domain-Policies": "none",
}


def apply_security_headers(
    response: HttpResponse, security: SecurityConfig, tls_enabled: bool = False, path: str | None = None,
) -> None:
    """Impose les en-tetes de securite en fin de pipeline - jamais
    ecrasables par un handler en amont (voir
    HttpResponse.force_security_header, decision transverse deja posee
    en Phase 0). `path` (defaut None = politique globale, aucune zone)
    permet a l'appelant de fournir le chemin de la requete pour que la
    CSP par zone (`security.csp_zones`) s'applique - omis par un
    appelant qui ne connait pas de chemin pertinent (ex. une reponse
    d'erreur generique construite hors contexte de requete)."""
    if not security.security_headers_enabled:
        return

    for name, value in STATIC_SECURITY_HEADERS.items():
        response.force_security_header(name, value)

    policy = csp_policy_for_path(path, security.csp_zones)
    response.force_security_header(csp_header_name(security.csp_mode), policy)
    response.force_security_header("Cross-Origin-Embedder-Policy", security.coep_mode)

    if security.hsts_enabled and tls_enabled:
        response.force_security_header("Strict-Transport-Security", _build_hsts_value(security))
