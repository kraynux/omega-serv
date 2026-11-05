"""Moteur HTTP effectif : UNE seule fonction decide, tout le monde l'affiche (plan moteur C++ §16.5, exigence
utilisateur 2026-11-02 : « eviter le melange des genres [...] que cela soit bien explicite »).

`decide_engine` est appelee par `serve` au demarrage, par le rechargement (SIGHUP), par l'ecran Etat et par
`omega-serv engine status` : ce que l'interface annonce est toujours ce qui tournera, jamais deux regles qui
divergent. Le natif n'est jamais lance pour une configuration qu'il ne sait pas servir entierement : une seule
fonction non prise en charge = repli complet sur le moteur Python (plan §6), jamais un serveur partiel.

Les raisons sont des codes stables (journal, fichier d'etat, tests) ; leur texte affiche passe par
`describe_reason` (traduit) et `log_reason` (journal, francais fixe comme le reste d'error.log)."""
from __future__ import annotations

from dataclasses import dataclass

from omega_serv.core.i18n import _
from omega_serv.domain.config.entities import OmegaServConfig

NATIVE_BINARY_RELATIVE_PATH = "bin/omega-http-core"
"""Produit par build-release.sh (plan §7.3), jamais versionne."""

NATIVE_OPTION_GAPS: tuple[str, ...] = ()
"""Options que le natif ne sait pas servir : aucune depuis le lot 6. WAF, Auth et Active Defense passent par le
processus Python de securite (lot 4), le listing par une route deleguee (lot 5), reverse proxy / FastCGI / envoi de
fichiers / WebSocket par une connexion confiee a Python (lot 6)."""

APPLICATION_OPTIONS = ("upload", "fastcgi", "reverse_proxy")
TLS_HANDOFF = "tls_handoff"
"""TLS direct + route applicative : la connexion chiffree par le natif ne peut pas etre confiee a Python."""

BINARY_MISSING = "binary_missing"
BINARY_NOT_EXECUTABLE = "binary_not_executable"
WORKERS_IGNORED = "workers_ignored"  # avis, jamais une cause de repli


@dataclass(frozen=True)
class EngineDecision:
    requested: str
    effective: str
    reasons: tuple[str, ...] = ()
    """Pourquoi le moteur effectif differe du moteur demande (vide sinon)."""
    notices: tuple[str, ...] = ()
    """Reglages sans effet avec ce moteur (ex. workers du mode boost avec le natif)."""

    @property
    def fallback(self) -> bool:
        return self.requested != self.effective


def native_unsupported_features(config: OmegaServConfig) -> list[str]:
    """Fonctions actives que le natif ne prend pas encore en charge : une seule entree = repli moteur Python."""
    # TLS direct pris en charge depuis le lot 3b (OpenSSL, meme contexte que Python) : jamais une cause de repli.
    missing = [option for option in NATIVE_OPTION_GAPS if config.option_enabled(option)]
    if config.tls.enabled and config.tls.mode == "direct" and any(config.option_enabled(o) for o in APPLICATION_OPTIONS):
        missing.append(TLS_HANDOFF)
    return missing


def decide_engine(config: OmegaServConfig, binary_problem: str | None) -> EngineDecision:
    """`binary_problem` : None si le binaire natif est present et executable, sinon BINARY_MISSING /
    BINARY_NOT_EXECUTABLE (verifie par l'infrastructure, jamais suppose ici)."""
    requested = config.server.engine
    if requested != "native":
        return EngineDecision(requested, "python")
    reasons = ([binary_problem] if binary_problem else []) + native_unsupported_features(config)
    notices: tuple[str, ...] = ()  # lot 7 : server.workers = processus de securite du natif, jamais ignore
    if reasons:
        return EngineDecision(requested, "python", tuple(reasons), notices)
    return EngineDecision(requested, "native", (), notices)


_OPTION_LABELS = {
    "waf": "WAF",
    "auth": "Auth",
    "active_defense": "Active Defense",
    "upload": "Upload",
    "fastcgi": "FastCGI / PHP",
    "reverse_proxy": "Reverse proxy",
    "dirlisting": "Dirlisting",
}


def describe_reason(code: str) -> str:
    """Texte affiche (TUI, `engine status`) : quoi, et comment lever la cause."""
    if code == BINARY_MISSING:
        return _("binaire natif absent ({path}) - réinstaller l'archive complète").format(path=NATIVE_BINARY_RELATIVE_PATH)
    if code == BINARY_NOT_EXECUTABLE:
        return _("binaire natif non exécutable ({path})").format(path=NATIVE_BINARY_RELATIVE_PATH)
    if code == TLS_HANDOFF:
        return _("TLS en mode direct avec reverse proxy, FastCGI ou envoi de fichiers : ces routes demandent de "
                 "confier la connexion à Python, impossible quand le moteur natif chiffre lui-même - passer en mode "
                 "behind_proxy, ou désactiver ces options")
    if code == WORKERS_IGNORED:
        return _("le nombre de workers (mode boost) ne s'applique pas au moteur natif, qui utilise ses propres fils")
    if code in _OPTION_LABELS:
        return _("option {option} active : pas encore prise en charge par le moteur natif - la désactiver "
                 "pour utiliser le natif").format(option=_OPTION_LABELS[code])
    return _("raison inconnue : {code}").format(code=code)


def log_reason(code: str) -> str:
    """Texte d'error.log (francais fixe, comme le reste du journal d'erreurs)."""
    if code == BINARY_MISSING:
        return f"binaire natif absent ({NATIVE_BINARY_RELATIVE_PATH})"
    if code == BINARY_NOT_EXECUTABLE:
        return f"binaire natif non executable ({NATIVE_BINARY_RELATIVE_PATH})"
    if code == TLS_HANDOFF:
        return "TLS direct avec route applicative (connexion non transmissible a Python)"
    if code in _OPTION_LABELS:
        return f"option {code} active, non prise en charge par le moteur natif"
    return code
