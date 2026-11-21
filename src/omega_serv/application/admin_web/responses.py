"""Reponse du processus d'administration web et en-tetes de securite communs a toutes ses pages (tableau de bord
web, lots 2 et 3). Le routage et les pages : web_app.py.

Toujours : aucune mise en cache, aucun cadre, styles et script servis par le processus lui-meme seulement
(`style-src 'self'`, `script-src 'self'`, jamais de style ni de script en ligne), formulaires vers lui-meme seulement, pas de Referer ; HSTS seulement
en TLS."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AdminResponse:
    status: int
    reason: str
    headers: tuple[tuple[str, str], ...]
    body: bytes


def security_headers(*, tls: bool) -> tuple[tuple[str, str], ...]:
    headers = [
        ("Content-Security-Policy", ("default-src 'none'; style-src 'self'; script-src 'self'; connect-src 'self'; "
                                     "frame-ancestors 'none'; base-uri 'none'; form-action 'self'")),
        ("X-Content-Type-Options", "nosniff"),
        ("X-Frame-Options", "DENY"),
        # same-origin, pas no-referrer (retour de l'auteur du 2026-11-17, 403 a la connexion depuis un portable) :
        # avec no-referrer, le navigateur envoie « Origin: null » pour un formulaire, et le controle d'origine des POST
        # refuse alors toute connexion. same-origin ne transmet toujours rien a un autre site.
        ("Referrer-Policy", "same-origin"),
        ("Cache-Control", "no-store"),
        ("Cross-Origin-Opener-Policy", "same-origin"),
        ("Cross-Origin-Resource-Policy", "same-origin"),
    ]
    if tls:
        headers.append(("Strict-Transport-Security", "max-age=31536000"))
    return tuple(headers)
