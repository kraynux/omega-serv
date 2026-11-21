# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Cookies de l'administration web jamais relayes au site (scan de securite n° 2 du 2026-11-20, F16).

L'administration web tourne sur un autre port du MEME hote que le site ; un cookie n'est jamais isole par port :
le navigateur envoyait `omega_admin=<jeton de session>` avec chaque requete au site public, et le serveur le
transmettait tel quel a PHP et aux backends du proxy - une application hebergee recevait une session
d'administration valide. Ces cookies sont retires de l'en-tete `Cookie` avant tout relais (Python et natif,
upstream.cpp, without_admin_cookies). Noms : application/admin_web (COOKIE_NAME, THEME_COOKIE)."""
from __future__ import annotations

ADMIN_COOKIE_NAMES = frozenset({"omega_admin", "omega_admin_theme"})


def without_admin_cookies(value: str) -> str:
    """En-tete `Cookie` sans les cookies de l'administration web ; "" s'il ne reste rien."""
    if "omega_admin" not in value:
        return value
    kept = [piece.strip() for piece in value.split(";")
            if piece.strip() and piece.split("=", 1)[0].strip() not in ADMIN_COOKIE_NAMES]
    return "; ".join(kept)
