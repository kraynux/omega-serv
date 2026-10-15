"""Parsing/construction minimale de cookies HTTP (RFC 6265).

Aucune fonctionnalite de ce type n'existait dans le projet avant la
Phase 5bis du reverse proxy (OMEGA-SERV_PLAN-DETAILLE_REVERSE_PROXY.md
§17, affinite de session) - verifie par recherche exhaustive avant
d'ecrire ce module (seules occurrences anterieures du mot "cookie" :
des listes de masquage de logs, jamais un parsing reel). Place dans
`domain/http/` (pas dans `domain/routing/proxy_zone.py`) car un concept
HTTP generique, reutilisable par tout futur mecanisme de session (ex.
une authentification par cookie - anticipee mais pas construite, voir
§30.3 du document de conception)."""
from __future__ import annotations


def parse_cookie_header(header_value: str | None) -> dict[str, str]:
    """Retourne {} si header_value est None/vide. Un cookie malforme
    (pas de '=') est simplement ignore plutot que de lever - meme
    tolerance que le reste du parsing HTTP entrant du projet, jamais
    une confiance aveugle mais jamais un crash non plus."""
    if not header_value:
        return {}
    cookies: dict[str, str] = {}
    for chunk in header_value.split(";"):
        name, sep, value = chunk.strip().partition("=")
        if not sep or not name:
            continue
        cookies[name] = value
    return cookies


def build_set_cookie_header(
    name: str,
    value: str,
    *,
    max_age_seconds: int,
    path: str = "/",
    same_site: str = "Lax",
) -> str:
    """`Secure`/`HttpOnly` toujours presents, jamais configurables -
    coherent avec l'audit candidat PROXY-003 (§27.6 du document de
    conception : un cookie de session sticky pose sans ces attributs
    est une alerte MEDIUM) - aucun raccourci silencieux possible ici,
    contrairement a `verify_upstream_tls` qui reste un choix assume et
    documente comme dangereux. Un deploiement sans TLS verra ce cookie
    simplement ignore par le navigateur (echec ouvert vers "pas
    d'affinite de session", jamais un probleme de securite)."""
    return "; ".join((
        f"{name}={value}",
        f"Max-Age={max_age_seconds}",
        f"Path={path}",
        f"SameSite={same_site}",
        "Secure",
        "HttpOnly",
    ))
