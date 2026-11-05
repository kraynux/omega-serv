"""Declaration anonyme d'utilisateur (OMEGA-SERV_ETUDE_TELEMETRIE.md §3b) - pure, aucune I/O.

Ce qui est envoye, et rien d'autre : une cle tiree au hasard (sans lien avec la machine), la
version d'omega-serv, le mode d'envoi choisi et, facultatifs, un continent et un pays pris dans
des listes fermees. Les codes (`unique`, `EU`, `FR`, `autre`...) ne sont jamais traduits ; seuls
les libelles affiches le sont.

Retrait (« Ne plus me declarer ») : `{"cle": ..., "retrait": true}`, la reception supprime l'entree."""
from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta

from omega_serv.domain.declaration.countries import COUNTRY_CODES

RECEPTION_URL = "https://kraynux.snake-mackarel.ts.net/compteur/"
"""Adresse de reception (site kraynux, HTTPS). Affichee telle quelle dans l'ecran."""

MODE_ONCE = "unique"
MODE_DAILY = "quotidien"
MODES = (MODE_ONCE, MODE_DAILY)

OTHER = "autre"
"""Element « Autre » des deux listes : continent ou pays non reference."""

CONTINENTS = ("AF", "AN", "AS", "EU", "NA", "OC", "SA")
"""Afrique, Antarctique, Asie, Europe, Amerique du Nord, Oceanie, Amerique du Sud."""

DAILY_INTERVAL = timedelta(hours=24)
"""Mode quotidien : au plus un envoi (reussi ou non) par periode - jamais d'acharnement."""

DO_NOT_TRACK_VARIABLE = "DO_NOT_TRACK"

_KEY = re.compile(r"^[0-9a-f]{32}$")
_VERSION = re.compile(r"^\d{1,3}\.\d{1,3}\.\d{1,3}$")


@dataclass(frozen=True)
class Declaration:
    key: str
    mode: str
    continent: str = ""
    country: str = ""


def declaration_errors(declaration: Declaration) -> list[str]:
    """Noms des champs invalides (ceux du message envoye) ; liste vide si la declaration est
    envoyable telle quelle. Jamais vu en pratique : l'ecran et la CLI ne proposent que des valeurs
    des listes fermees."""
    errors = []
    if not _KEY.match(declaration.key):
        errors.append("cle")
    if declaration.mode not in MODES:
        errors.append("envoi")
    if declaration.continent and declaration.continent not in (*CONTINENTS, OTHER):
        errors.append("continent")
    if declaration.country and declaration.country not in (*COUNTRY_CODES, OTHER):
        errors.append("pays")
    return errors


def is_valid_version(version: str) -> bool:
    return bool(_VERSION.match(version))


def build_payload(declaration: Declaration, version: str) -> dict[str, str]:
    """Le message exact envoye (et affiche a l'utilisateur avant l'envoi). Continent et pays
    absents du message quand ils ne sont pas choisis."""
    payload = {"cle": declaration.key, "version": version, "envoi": declaration.mode}
    if declaration.continent:
        payload["continent"] = declaration.continent
    if declaration.country:
        payload["pays"] = declaration.country
    return payload


def build_withdrawal(key: str) -> dict[str, object]:
    return {"cle": key, "retrait": True}


def do_not_track(environ: Mapping[str, str]) -> bool:
    """Convention DO_NOT_TRACK=1 : aucun envoi automatique, meme avec l'accord donne."""
    return environ.get(DO_NOT_TRACK_VARIABLE, "").strip() not in ("", "0")


def daily_send_due(
    declaration: Declaration | None, last_attempt: datetime | None, now: datetime, *, do_not_track_set: bool,
) -> bool:
    """Envoi quotidien a faire ? Seulement en mode quotidien, sans DO_NOT_TRACK, et si le dernier
    essai (reussi ou non, par l'interface ou par le service) date d'au moins 24 h."""
    if declaration is None or declaration.mode != MODE_DAILY or do_not_track_set:
        return False
    return last_attempt is None or now - last_attempt >= DAILY_INTERVAL
