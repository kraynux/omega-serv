# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Profil « Custom » (projets 3.0.0 §1, §B, §7.1 ; decisions de l'auteur des 2026-11-07 et 2026-11-15).

- **Point de depart** : un serveur web minimal SANS protection debrayable ; ce que le coeur HTTP impose reste actif
  quoi qu'on choisisse (analyse stricte, confinement au webroot, rejet de la traversee, normalisation, HSTS jamais
  sans TLS) et n'est pas propose.
- **Choix guides** : chaque reglage est une liste de valeurs (jamais de texte libre a deviner).
- **Trous** : chaque combinaison risquee est une regle explicite (code stable, gravite, texte) ; un trou
  « bloquant » empeche l'enregistrement, un trou « a accepter » doit etre accepte un par un. S'y ajoutent, a
  l'enregistrement, les controles existants de la configuration (`validate_config`, `detect_conflicts`).
- **Non modifiable** : on en recree un (on peut repartir d'un existant). Nombre non limite : un seul profil est
  applique a la fois.
- **Identification** (lue par le tableau de bord) : nom, libelle, description bornes."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from omega_serv.core.i18n import _

NAME_PATTERN = re.compile(r"[a-z0-9][a-z0-9_-]{2,31}")
LABEL_MIN, LABEL_MAX, DESCRIPTION_MAX = 3, 40, 200
METADATA_KEYS = frozenset({"label", "custom", "created_at"})
"""Cles de fiche d'un profil personnalise, jamais des valeurs de configuration."""


def identification_errors(name: str, label: str, description: str, taken: set[str]) -> dict[str, str]:
    """Erreur par champ (« name », « label », « description ») ; vide si tout est bon."""
    errors: dict[str, str] = {}
    if not NAME_PATTERN.fullmatch(name):
        errors["name"] = _("Nom : 3 à 32 caractères, minuscules a-z, chiffres, « - » ou « _ », commençant par une "
                           "lettre ou un chiffre (il sert aussi de nom de fichier).")
    elif name in taken:
        errors["name"] = _("Nom déjà utilisé par un autre profil : {name!r}.").format(name=name)
    clean_label = label.strip()
    if not LABEL_MIN <= len(clean_label) <= LABEL_MAX or not clean_label.isprintable():
        errors["label"] = _("Libellé : {minimum} à {maximum} caractères imprimables (affiché au tableau de "
                            "bord).").format(minimum=LABEL_MIN, maximum=LABEL_MAX)
    if len(description) > DESCRIPTION_MAX or not description.isprintable():
        errors["description"] = _("Description : {maximum} caractères imprimables au plus.").format(
            maximum=DESCRIPTION_MAX)
    return errors


@dataclass(frozen=True)
class Choice:
    key: str
    label: str
    values: tuple[tuple[str, str], ...]
    """(valeur, libelle affiche)."""
    minimal: str
    """Valeur du serveur minimal sans protection (point de depart decide le 2026-11-07)."""


ON, OFF = "on", "off"
_METHODS = {"read": ["GET", "HEAD"], "forms": ["GET", "HEAD", "POST"],
            "all": ["GET", "HEAD", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"]}


def _on_off() -> tuple[tuple[str, str], ...]:
    return ((OFF, _("non")), (ON, _("oui")))


def choices() -> tuple[Choice, ...]:
    return (
        Choice("security_headers", _("En-têtes de sécurité (X-Content-Type-Options, Referrer-Policy...)"),
               _on_off(), OFF),
        # Pas de valeur « desactivee » : la configuration n'accepte que enforce et report-only (validate_config).
        Choice("csp_mode", _("Content-Security-Policy"),
               (("report-only", _("rapport seulement")), ("enforce", _("appliquée"))), "report-only"),
        Choice("deny_hidden_files", _("Refuser les fichiers cachés (.env, .git...)"), _on_off(), OFF),
        Choice("require_valid_host", _("Exiger un en-tête Host valide"), _on_off(), OFF),
        Choice("methods", _("Méthodes HTTP acceptées"),
               tuple((key, ", ".join(methods)) for key, methods in _METHODS.items()), "all"),
        Choice("waf", _("WAF (pare-feu applicatif)"), _on_off(), OFF),
        Choice("auth", _("Authentification HTTP (zones protégées)"), _on_off(), OFF),
        Choice("dirlisting", _("Directory listing"), _on_off(), OFF),
        Choice("fastcgi", _("FastCGI / PHP-FPM"), _on_off(), OFF),
        Choice("cache", _("Cache navigateur (en-têtes Cache-Control)"), _on_off(), OFF),
        Choice("trusted_proxy", _("Derrière un proxy de confiance (X-Forwarded-For)"), _on_off(), OFF),
        Choice("access_control", _("Contrôle d'accès par chemin"), _on_off(), OFF),
        Choice("reverse_proxy", _("Reverse proxy (vers des backends)"), _on_off(), OFF),
    )


def minimal_selection() -> dict[str, str]:
    return {choice.key: choice.minimal for choice in choices()}


_OPTION_KEYS = ("waf", "auth", "dirlisting", "fastcgi", "cache", "trusted_proxy", "access_control", "reverse_proxy")


def profile_values(selection: dict[str, str]) -> dict[str, Any]:
    """Valeurs du profil (meme forme que la configuration). Seules la securite et les options viennent du profil ;
    adresse, port, TLS, chemins et journaux restent ceux de l'instance a l'application."""
    return {
        "security": {
            "security_headers_enabled": selection["security_headers"] == ON,
            "csp_mode": selection["csp_mode"],
            "deny_hidden_files": selection["deny_hidden_files"] == ON,
            "require_valid_host": selection["require_valid_host"] == ON,
            "allowed_methods": _METHODS[selection["methods"]],
        },
        "options": {key: {"enabled": selection[key] == ON} for key in _OPTION_KEYS},
    }


@dataclass(frozen=True)
class Hole:
    code: str
    blocking: bool
    message: str


def holes(selection: dict[str, str]) -> list[Hole]:
    """« Trous » de la combinaison choisie : jamais une erreur decouverte apres coup."""
    found: list[Hole] = []

    def accept(code: str, message: str) -> None:
        found.append(Hole(code, False, message))

    def block(code: str, message: str) -> None:
        found.append(Hole(code, True, message))

    on = {key for key, value in selection.items() if value == ON}
    if "security_headers" not in on:
        accept("no-security-headers", _("Aucun en-tête de sécurité : le navigateur ne reçoit aucune consigne "
                                        "(type de contenu, origine des requêtes)."))
    if selection["csp_mode"] != "enforce":
        accept("csp-report-only", _("Content-Security-Policy en rapport seulement : rien n'est bloqué, une page "
                                    "piégée peut charger des scripts d'ailleurs."))
    if "deny_hidden_files" not in on:
        accept("hidden-files-served", _("Fichiers cachés servis : un .env ou un dossier .git oublié dans le site "
                                        "est lisible par tous."))
    if "require_valid_host" not in on:
        accept("any-host", _("En-tête Host non vérifié : le serveur répond pour n'importe quel nom de domaine."))
    if selection["methods"] == "all" and "auth" not in on:
        accept("write-methods-open", _("PUT, DELETE et PATCH acceptés sans authentification."))
    if "waf" not in on:
        accept("no-waf", _("Pas de WAF : les injections et les scanners connus ne sont pas filtrés."))
    if "dirlisting" in on and "deny_hidden_files" not in on:
        accept("listing-shows-hidden", _("Le directory listing affichera aussi les fichiers cachés."))
    if "fastcgi" in on and selection["methods"] == "read":
        block("fastcgi-without-post", _("FastCGI avec GET et HEAD seulement : les formulaires PHP (POST) "
                                        "échoueraient tous. Choisissez « GET, HEAD, POST » ou plus."))
    if "reverse_proxy" in on and selection["methods"] == "read":
        accept("proxy-read-only", _("Reverse proxy avec GET et HEAD seulement : les backends ne recevront aucun "
                                    "envoi de formulaire."))
    if "trusted_proxy" in on:
        accept("trusted-proxy-list", _("Proxy de confiance : n'ajoutez à sa liste que vos propres proxies, sinon "
                                       "un visiteur peut se faire passer pour une autre adresse."))
    return found
