"""CSP de base (spec §12.3/§12.4).

Politique stricte de depart pour un site statique minimal. CSP par zone
(spec §12.4, plusieurs politiques par prefixe d'URL - retour utilisateur
2026-10-10 : "autoriser des regles conditionnelles pour des dossiers
choisis, par exemple unsafe-inline uniquement dans un dossier
specifique") livree ici, construite sur `domain/routing/
zone_resolver.py` (meme mecanisme que cache/alias/redirections,
plus-long-prefixe-gagne) - jamais une logique de correspondance
reinventee pour ce seul besoin."""
from __future__ import annotations

from omega_serv.core.i18n import _
from omega_serv.domain.routing.zone_resolver import Zone, resolve_zone

DEFAULT_CSP_POLICY = (
    "default-src 'none'; base-uri 'self'; form-action 'self'; "
    "frame-ancestors 'none'; img-src 'self' data:; style-src 'self'; "
    "script-src 'self'; font-src 'self'; connect-src 'self'; object-src 'none'"
)


def csp_header_name(csp_mode: str) -> str:
    """`Content-Security-Policy-Report-Only` avant d'imposer une CSP sur
    un site existant (spec §12.5) - les violations sont journalisees
    sans jamais bloquer le rendu."""
    if csp_mode == "report-only":
        return "Content-Security-Policy-Report-Only"
    return "Content-Security-Policy"


def csp_policy_for_path(path: str | None, zones: tuple[Zone[str], ...]) -> str:
    """Politique de REMPLACEMENT COMPLETE pour `path` si une zone
    correspond (jamais une fusion de directives avec `DEFAULT_CSP_POLICY`
    - plus simple a auditer qu'un merge, meme choix que les autres
    usages de Zone dans ce projet, ex. CachePolicy). `csp_mode`
    (enforce/report-only) reste GLOBAL, jamais par zone - seul le
    CONTENU change ici, jamais la posture d'application (voir
    security_headers.py::apply_security_headers, seul appelant)."""
    if path is None or not zones:
        return DEFAULT_CSP_POLICY
    zone = resolve_zone(path, list(zones))
    return zone.data if zone is not None else DEFAULT_CSP_POLICY


# Retour utilisateur 2026-10-10 : "il faut detailler et proposer pour que
# l'utilisateur ne sacrifie pas entierement une politique pour juste un
# rajout" - une zone remplace ENTIEREMENT la politique par defaut (voir
# ci-dessus), donc un champ texte vide inviterait a perdre des
# directives sans le vouloir. `KNOWN_CSP_DIRECTIVES` + parse/build ci-
# dessous alimentent un assistant par directive (interfaces/tui/screens/
# csp_zone_wizard_screen.py) qui pre-remplit chaque directive avec sa
# valeur actuelle - le meme esprit que l'assistant de regle WAF
# personnalisee (langage clair plutot qu'un champ brut a completer).
KNOWN_CSP_DIRECTIVES: tuple[tuple[str, str], ...] = (
    ("default-src", _("Source par défaut pour tout type de contenu non couvert par une autre directive ci-dessous.")),
    ("base-uri", _("URL valides pour la balise <base> - restreindre à 'self' évite un détournement de chemins relatifs.")),
    ("form-action", _("Destination autorisée pour la soumission d'un formulaire - 'self' empêche l'exfiltration vers un domaine externe.")),
    ("frame-ancestors", _("Qui peut vous afficher dans une <iframe> - 'none' empêche le clickjacking.")),
    ("img-src", _("Origines autorisées pour les images.")),
    ("style-src", _("Origines/mecanismes autorisés pour le CSS - 'unsafe-inline' autorise tout style inline, y compris injecté.")),
    ("script-src", _("Origines/mecanismes autorisés pour le JavaScript - 'unsafe-inline'/'unsafe-eval' sont les relâches les plus risquées.")),
    ("font-src", _("Origines autorisées pour les polices.")),
    ("connect-src", _("Destinations autorisées pour fetch/XHR/WebSocket - restreint l'exfiltration de données.")),
    ("object-src", _("Autorise <object>/<embed>/<applet> - 'none' recommandé (vecteur historique Flash/plugins).")),
)
_KNOWN_DIRECTIVE_NAMES = frozenset(name for name, _hint in KNOWN_CSP_DIRECTIVES)


def parse_csp_directives(policy: str) -> dict[str, str]:
    """Decoupe une politique CSP en {directive: valeurs} - inverse de
    `build_csp_policy`. Une directive non reconnue (hors de
    `KNOWN_CSP_DIRECTIVES`) est conservee telle quelle sous son propre
    nom plutot qu'ignoree silencieusement - l'assistant peut alors au
    moins l'afficher brute plutot que la faire disparaitre sans le
    dire."""
    directives: dict[str, str] = {}
    for directive in policy.split(";"):
        directive = directive.strip()
        if not directive:
            continue
        name, _, values = directive.partition(" ")
        directives[name] = values.strip()
    return directives


def build_csp_policy(directives: dict[str, str]) -> str:
    """Assemble une politique dans l'ORDRE connu (`KNOWN_CSP_DIRECTIVES`)
    d'abord, puis toute directive supplementaire non reconnue ensuite -
    une directive avec une valeur vide est OMISE (equivalent a
    "non precisee", jamais une directive vide invalide dans le header
    final)."""
    parts = []
    seen = set()
    for name, _hint in KNOWN_CSP_DIRECTIVES:
        value = directives.get(name, "").strip()
        if value:
            parts.append(f"{name} {value}")
        seen.add(name)
    for name, value in directives.items():
        if name not in seen and value.strip():
            parts.append(f"{name} {value.strip()}")
    return "; ".join(parts)


_RISKY_VALUE_TOKENS = frozenset({"'unsafe-inline'", "'unsafe-eval'", "*"})


def find_csp_risks(policy: str) -> list[str]:
    """Directives dont la valeur contient un jeton reconnu comme risque
    (unsafe-inline/unsafe-eval/source generique '*') - partagee entre
    `domain/security/audit/rules.py` (CSP-001/CSP-002, apres coup) ET
    l'assistant de zone CSP (avant meme d'enregistrer) : UNE SEULE
    detection, jamais deux logiques qui pourraient diverger."""
    risky = []
    for name, values in parse_csp_directives(policy).items():
        if _RISKY_VALUE_TOKENS.intersection(values.split()):
            risky.append(name)
    return risky
