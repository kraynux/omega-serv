"""Exceptions du module Auth."""
from __future__ import annotations

from omega_serv.core.exceptions import OmegaServError


class AuthError(OmegaServError):
    """Racine des erreurs Auth."""


class UsersFileError(AuthError):
    """Le fichier de comptes est illisible ou syntaxiquement invalide."""


class AuthZonesFileError(AuthError):
    """Le fichier de zones est illisible ou syntaxiquement invalide."""
