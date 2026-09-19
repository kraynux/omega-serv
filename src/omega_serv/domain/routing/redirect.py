"""Redirections HTTP (spec §17.2).

Anti-open-redirect par construction : la destination vient toujours
d'une regle statique de configuration, jamais construite a partir d'une
donnee de requete - aucune fonction ici ne prend de parametre derive du
client pour former une destination."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

VALID_REDIRECT_CODES = (301, 302, 307, 308)


@dataclass(frozen=True)
class RedirectRule:
    url_prefix: str
    destination: str
    status_code: int = 302


def parse_redirect_rules(raw_list: list[dict[str, Any]]) -> list[RedirectRule]:
    return [
        RedirectRule(
            url_prefix=item["url_prefix"],
            destination=item["destination"],
            status_code=int(item.get("status_code", 302)),
        )
        for item in raw_list
    ]


def validate_redirect_rule(rule: RedirectRule) -> str | None:
    if not rule.url_prefix.startswith("/"):
        return f"url_prefix doit commencer par '/' : {rule.url_prefix!r}"
    if rule.status_code not in VALID_REDIRECT_CODES:
        return f"status_code invalide : {rule.status_code} (attendu : {VALID_REDIRECT_CODES})"
    if not rule.destination:
        return "destination ne peut pas etre vide"
    return None
