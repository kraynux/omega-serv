"""Choix proposes a la souris pour une liste (keyword_lists) - partages par
l'assistant WAF Custom et l'ecran "Modifier une liste" (OMEGA-SERV_PLAN-
DETAILLE_SENSITIVE_PATHS.md lots 6/7), jamais deux listes de choix
divergentes."""
from __future__ import annotations

from omega_serv.core.i18n import _

NEW_FILE = "__new__"
GRAVITY_LEVELS: tuple[tuple[str, str], ...] = (
    (_("Observation (journal seulement - conseillé au 1er chargement)"), "observe"),
    (_("Faible (1)"), "1"),
    (_("Moyen (3) - ne bloque jamais seul"), "3"),
    (_("Élevé (6) - bloque dès le 1er accès"), "6"),
    (_("Critique (9)"), "9"),
)
ANCHORS: tuple[tuple[str, str], ...] = (
    (_("n'importe où dans l'adresse"), "any_segment"),
    (_("seulement au début de l'adresse"), "root"),
)
KEYWORD_SCOPES: tuple[tuple[str, str], ...] = (
    (_("l'adresse et ses paramètres"), "path,query"),
    (_("un formulaire envoyé (POST)"), "body"),
    (_("le logiciel du visiteur (User-Agent)"), "user_agent"),
    (_("la page d'origine (Referer)"), "referer"),
)
RECIDIVE_COUNTS: tuple[tuple[str, str], ...] = (
    (_("pas de récidive propre (compteur commun du WAF)"), "0"),
    *((_("{n} accès").format(n=n), str(n)) for n in (1, 2, 3, 5, 10, 20)),
)
RECIDIVE_WINDOWS: tuple[tuple[str, str], ...] = (
    (_("1 min"), "60"), (_("5 min"), "300"), (_("10 min"), "600"), (_("30 min"), "1800"), (_("1 h"), "3600"),
)
BAN_DURATIONS: tuple[tuple[str, str], ...] = (
    (_("1 h"), "3600"), (_("6 h"), "21600"), (_("24 h"), "86400"), (_("7 jours"), "604800"),
)


def gravity_value(weight: int, observe_only: bool) -> str:
    """Valeur de GRAVITY_LEVELS correspondant a une definition existante."""
    if observe_only:
        return "observe"
    known = {value for _, value in GRAVITY_LEVELS}
    return str(weight) if str(weight) in known else "3"


def gravity_label(weight: int, observe_only: bool) -> str:
    value = gravity_value(weight, observe_only)
    return next(label for label, v in GRAVITY_LEVELS if v == value).split(" (")[0].split(" -")[0]
