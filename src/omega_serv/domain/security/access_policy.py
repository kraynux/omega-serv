# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Regles d'acces generiques (spec §13.1) : dotfiles, extensions
sensibles, motifs de fichiers refuses par defaut - independant de la
resolution de chemin (path_policy.py, deja garante du confinement au
webroot) et de la methode HTTP."""
from __future__ import annotations

from omega_serv.domain.config.entities import SecurityConfig
from omega_serv.domain.http.headers import has_control_characters


def is_method_allowed(method: str, security: SecurityConfig) -> bool:
    """Liste blanche de methodes (spec §11.1 : "Rejeter les methodes
    inconnues, sauf si explicitement autorisees" / "Rejeter TRACE,
    TRACK, CONNECT et DELETE par defaut"). Aucune methode n'est
    speciale ici : le refus par defaut vient simplement du fait
    qu'aucun profil ne les inclut dans allowed_methods, pas d'une liste
    noire separee a maintenir."""
    return method in security.allowed_methods


def validate_host_header(headers: tuple[tuple[str, str], ...]) -> str | None:
    """Valide l'en-tete Host (spec §11.1 : "Rejeter les Host vides,
    ambigus ou non autorises"). Retourne None si valide, sinon une
    raison de rejet. Ne verifie PAS que le Host correspond a
    server_name - cette correspondance est un chantier separe (routage
    multi-site), hors perimetre de la validation protocolaire de base."""
    host_values = [value for name, value in headers if name.lower() == "host"]

    if len(host_values) == 0:
        return "Host manquant"
    if len(host_values) > 1:
        return "Host duplique (ambigu)"

    host = host_values[0]
    if not host:
        return "Host vide"
    if has_control_characters(host):
        return "Host contient un caractere de controle"

    return None


def is_denied_path(segments: tuple[str, ...], security: SecurityConfig) -> bool:
    """Verifie si un chemin normalise (deja confine au webroot) doit
    etre refuse par les regles generiques de la configuration - pas de
    verification de methode HTTP ici (voir la responsabilite separee du
    handler statique)."""
    if security.deny_hidden_files and any(segment.startswith(".") for segment in segments):
        return True

    if not segments:
        return False

    filename = segments[-1].lower()

    for extension in security.deny_sensitive_extensions:
        if filename.endswith(extension.lower()):
            return True

    for pattern in security.deny_patterns:
        if pattern.lower() in filename:
            return True

    return False
