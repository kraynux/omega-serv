# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Redaction champ par champ d'un corps `application/x-www-form-urlencoded`
avant journalisation (audit securite, 2026-09-14).

Retour utilisateur (audit securite) : `active_defense_enriched_log_format.py`
et `waf_alert_format.py` redigent deja correctement les EN-TETES sensibles
(`redact_fields`/`mask_headers`) avant journalisation, mais journalisaient
le CORPS de requete verbatim des que la capture est activee - ironique
puisqu'Active Defense sert justement a detecter le credential stuffing :
un `POST /login` avec `username=admin&password=Secret123` intercepte par
cette fonctionnalite finissait en clair dans le journal, exactement
l'usage documente dans le guide d'aide du projet. Reutilise la MEME liste
de champs sensibles que chaque appelant a deja configuree pour ses
en-tetes (`redact_fields`/`mask_headers`) plutot que d'inventer une
troisieme liste independante - si un operateur ajoute un nom de champ
personnalise, il s'applique alors uniformement partout.

Fonction pure, aucune I/O ici (meme discipline que access_log_format.py) -
volontairement tolerante : un corps qui n'est pas du form-urlencoded
exploitable (JSON, binaire...) est retourne sans modification, la
detection du bon moment pour appeler cette fonction (Content-Type)
restant la responsabilite de l'appelant."""
from __future__ import annotations

from urllib.parse import parse_qsl, urlencode

_REDACTED_VALUE = "***REDACTED***"

DEFAULT_SENSITIVE_BODY_FIELDS: tuple[str, ...] = (
    "password", "passwd", "pwd", "token", "secret", "api_key", "apikey",
    "access_token", "refresh_token", "authorization",
)
"""Reglages par defaut pour un appelant sans liste de champs sensibles
deja configuree pour ses en-tetes (ex. waf_alert_format.py::mask_headers
liste des NOMS D'EN-TETE comme "cookie"/"x-api-key", jamais des noms de
CHAMPS DE FORMULAIRE comme "password" - reutiliser cette liste-la pour
le corps aurait laisse passer exactement le cas signale par l'audit,
"username=admin&password=..."). active_defense_enriched_log_format.py
utilise en revanche directement sa propre config `redact_fields`, qui
inclut deja "password" par defaut et reste extensible par l'operateur."""


def redact_form_urlencoded_body(text: str, fields_to_redact: tuple[str, ...] = DEFAULT_SENSITIVE_BODY_FIELDS) -> str:
    """Rediged les VALEURS des champs de `text` (paires `cle=valeur`
    separees par `&`) dont la cle correspond (insensible a la casse) a
    l'un de `fields_to_redact` - les cles elles-memes et les autres
    valeurs restent intactes. Retourne `text` inchange si aucune paire
    exploitable n'est trouvee (corps vide, ou pas reellement au format
    attendu)."""
    if not text or "=" not in text:
        return text
    # keep_blank_values=False (le defaut) est deliberement CONSERVE ici :
    # avec True, parse_qsl accepte un segment SANS "=" comme une cle a
    # valeur vide plutot que de le rejeter - un texte quelconque
    # (JSON, texte libre) sans aucune structure cle=valeur se
    # retrouvait alors traite a tort comme UNE SEULE paire valide (sa
    # totalite comme cle), contournant silencieusement le filtre
    # "if not pairs: return text" cense justement l'ecarter (bug trouve
    # en testant, jamais suppose).
    pairs = parse_qsl(text, keep_blank_values=False, strict_parsing=False)
    if not pairs:
        return text

    lowered_targets = {field.lower() for field in fields_to_redact}
    redacted_pairs = [
        (key, _REDACTED_VALUE if key.lower() in lowered_targets else value)
        for key, value in pairs
    ]
    return urlencode(redacted_pairs)
