"""Presse-papiers du systeme (activation TOTP de l'administration web, 2026-11-17 : sans scanner le QR code, le
secret et le lien otpauth doivent pouvoir se coller dans l'application d'authentification)."""
from __future__ import annotations

from typing import Protocol


class ClipboardPort(Protocol):
    def copy(self, text: str) -> str:
        """Nom de l'outil qui a pris le texte ; vide si aucun (pas d'affichage graphique, aucun outil installe)."""
        ...
