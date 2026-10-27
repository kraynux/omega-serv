"""Redirections HTTP (spec §17.2).

Anti-open-redirect par construction : la destination vient toujours
d'une regle statique de configuration, jamais construite a partir d'une
donnee de requete - aucune fonction ici ne prend de parametre derive du
client pour former une destination."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from omega_serv.core.i18n import _

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
        return _("url_prefix doit commencer par '/' : {url_prefix!r}").format(url_prefix=rule.url_prefix)
    if rule.status_code not in VALID_REDIRECT_CODES:
        return _("status_code invalide : {status_code} (attendu : {VALID_REDIRECT_CODES})").format(status_code=rule.status_code, VALID_REDIRECT_CODES=VALID_REDIRECT_CODES)
    if not rule.destination:
        return _("destination ne peut pas être vide")
    return None
