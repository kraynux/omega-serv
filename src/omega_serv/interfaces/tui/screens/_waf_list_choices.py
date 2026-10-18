"""Choix proposes a la souris pour une liste (keyword_lists) - partages par
l'assistant WAF Custom et l'ecran "Modifier une liste" (OMEGA-SERV_PLAN-
DETAILLE_SENSITIVE_PATHS.md lots 6/7), jamais deux listes de choix
divergentes."""
from __future__ import annotations

NEW_FILE = "__new__"
GRAVITY_LEVELS: tuple[tuple[str, str], ...] = (
    ("Observation (journal seulement - conseille au 1er chargement)", "observe"),
    ("Faible (1)", "1"),
    ("Moyen (3) - ne bloque jamais seul", "3"),
    ("Eleve (6) - bloque des le 1er acces", "6"),
    ("Critique (9)", "9"),
)
ANCHORS: tuple[tuple[str, str], ...] = (
    ("n'importe ou dans l'adresse", "any_segment"),
    ("seulement au debut de l'adresse", "root"),
)
KEYWORD_SCOPES: tuple[tuple[str, str], ...] = (
    ("l'adresse et ses parametres", "path,query"),
    ("un formulaire envoye (POST)", "body"),
    ("le logiciel du visiteur (User-Agent)", "user_agent"),
    ("la page d'origine (Referer)", "referer"),
)
RECIDIVE_COUNTS: tuple[tuple[str, str], ...] = (
    ("pas de recidive propre (compteur commun du WAF)", "0"),
    *((f"{n} acces", str(n)) for n in (1, 2, 3, 5, 10, 20)),
)
RECIDIVE_WINDOWS: tuple[tuple[str, str], ...] = (
    ("1 min", "60"), ("5 min", "300"), ("10 min", "600"), ("30 min", "1800"), ("1 h", "3600"),
)
BAN_DURATIONS: tuple[tuple[str, str], ...] = (
    ("1 h", "3600"), ("6 h", "21600"), ("24 h", "86400"), ("7 jours", "604800"),
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
