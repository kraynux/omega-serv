# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Libelles et messages des reglages de protection des mots de passe (menu Authentification, validation de la
configuration) ; valeurs et bornes : domain/security/auth/password_protection.py."""
from __future__ import annotations

from omega_serv.core.i18n import _
from omega_serv.domain.security.auth.password_protection import (
    SETTINGS_KEY,
    PasswordProtection,
    protection_problems,
)


def protection_labels() -> dict[str, str]:
    return {
        "success_ttl_seconds": _("Succès retenu (secondes, renouvelées à chaque requête ; 0 = aucun cache)"),
        "success_max_age_seconds": _("Durée maximale d'un succès retenu (secondes)"),
        "success_entries": _("Succès retenus au plus"),
        "failure_window_seconds": _("Fenêtre de comptage des échecs (secondes)"),
        "failures_per_ip": _("Échecs par adresse avant refus 429"),
        "failures_per_user": _("Échecs par nom d'utilisateur avant refus 429"),
        "pending_checks_max": _("Vérifications en attente au plus (au-delà : 503)"),
    }


def protection_error_messages(raw: object) -> list[str]:
    labels = protection_labels()
    messages = []
    for problem in protection_problems(raw):
        label = labels.get(problem.name, problem.name)
        if problem.kind == "unknown":
            messages.append(_("options.auth.{key} : réglage inconnu {name!r}").format(key=SETTINGS_KEY, name=problem.name))
        elif problem.kind == "integer":
            messages.append(_("{label} : nombre entier attendu").format(label=label))
        elif problem.kind == "range":
            messages.append(_("{label} : entre {low} et {high}").format(label=label, low=problem.low, high=problem.high))
        else:
            messages.append(_("{label} : doit être au moins égale à la durée d'un succès retenu").format(label=label))
    return messages


def protection_to_settings(protection: PasswordProtection) -> dict[str, int]:
    return {name: getattr(protection, name) for name in protection_labels()}
