"""Alias URL -> chemin (spec §17.1).

Regles :
- La cible reste par defaut dans webroot/.
- Une cible hors webroot exige allow_outside_webroot=true (avertissement
  fort attendu cote CLI/menu, pas verifie ici).
- Jamais d'alias vers secure/, config/, src/ ou var/ - quel que soit
  allow_outside_webroot (spec §17.1, derniere regle : ces dossiers ne
  sont jamais des cibles legitimes, contrairement a un dossier
  utilisateur hors webroot qui peut l'etre)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from omega_serv.core.i18n import _

_FORBIDDEN_TARGET_ROOTS = ("secure", "config", "src", "var")


@dataclass(frozen=True)
class AliasRule:
    url_prefix: str
    target_path: str
    allow_outside_webroot: bool = False


def parse_alias_rules(raw_list: list[dict[str, Any]]) -> list[AliasRule]:
    return [
        AliasRule(
            url_prefix=item["url_prefix"],
            target_path=item["target_path"],
            allow_outside_webroot=bool(item.get("allow_outside_webroot", False)),
        )
        for item in raw_list
    ]


def validate_alias_rule(rule: AliasRule) -> str | None:
    """Retourne une raison de rejet si la regle est invalide, None si
    elle est acceptable. Verification purement textuelle sur les
    chemins declares - la resolution filesystem reelle (symlinks,
    existence) reste la responsabilite de SafePathResolver au moment
    de servir une requete."""
    if not rule.url_prefix.startswith("/"):
        return _("url_prefix doit commencer par '/' : {url_prefix!r}").format(url_prefix=rule.url_prefix)

    normalized = rule.target_path.replace("\\", "/").strip("/")
    first_segment = normalized.split("/", 1)[0] if normalized else ""

    if first_segment in _FORBIDDEN_TARGET_ROOTS:
        return _("alias vers un dossier interdit ({first_segment}/) : {target_path!r}").format(first_segment=first_segment, target_path=rule.target_path)

    if not rule.allow_outside_webroot and first_segment != "webroot":
        return (
            _("cible hors webroot sans allow_outside_webroot=true : {target_path!r}").format(target_path=rule.target_path)
        )

    return None
