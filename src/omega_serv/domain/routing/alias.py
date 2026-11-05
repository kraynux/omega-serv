"""Alias URL -> chemin (spec §17.1).

Regles :
- La cible reste par defaut dans webroot/.
- Une cible hors webroot exige allow_outside_webroot=true (avertissement
  fort attendu cote CLI/menu, pas verifie ici).
- Jamais d'alias vers secure/, config/, src/ ou var/ - quel que soit
  allow_outside_webroot (spec §17.1, derniere regle : ces dossiers ne
  sont jamais des cibles legitimes, contrairement a un dossier
  utilisateur hors webroot qui peut l'etre).
- Ces noms designent les dossiers DU PROJET : une cible absolue du
  systeme (ex. /var/www/html, /var/secure) n'est jamais comparee a ces
  noms - seule une cible absolue situee sous <projet>/secure, config,
  src ou var est refusee, quand `project_root` est connu (correction
  2026-11-05 : « /var/... » etait refuse comme le var/ du projet)."""
from __future__ import annotations

import posixpath
from dataclasses import dataclass
from pathlib import Path
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


def _forbidden_project_dir(target: str, project_root: Path) -> str | None:
    """Dossier interdit du projet contenant `target` (absolu), ou None.
    Comparaison purement lexicale (posixpath.normpath) : la resolution
    des liens symboliques est faite par l'appelant qui a acces au disque
    (application/config/validate_config.py)."""
    root = posixpath.normpath(str(project_root).replace("\\", "/"))
    normalized = posixpath.normpath(target)
    for name in _FORBIDDEN_TARGET_ROOTS:
        forbidden = posixpath.join(root, name)
        if normalized == forbidden or normalized.startswith(forbidden + "/"):
            return name
    return None


def validate_alias_rule(rule: AliasRule, project_root: Path | None = None) -> str | None:
    """Retourne une raison de rejet si la regle est invalide, None si
    elle est acceptable. Verification purement textuelle sur les
    chemins declares - la resolution filesystem reelle (symlinks,
    existence) reste la responsabilite de SafePathResolver au moment
    de servir une requete."""
    if not rule.url_prefix.startswith("/"):
        return _("url_prefix doit commencer par '/' : {url_prefix!r}").format(url_prefix=rule.url_prefix)

    target = rule.target_path.replace("\\", "/")
    if target.startswith("/"):
        if not rule.allow_outside_webroot:
            return (
                _("cible hors webroot sans allow_outside_webroot=true : {target_path!r}").format(target_path=rule.target_path)
            )
        forbidden = _forbidden_project_dir(target, project_root) if project_root is not None else None
        if forbidden is not None:
            return _("alias vers un dossier interdit ({first_segment}/) : {target_path!r}").format(first_segment=forbidden, target_path=rule.target_path)
        return None

    normalized = target.strip("/")
    first_segment = normalized.split("/", 1)[0] if normalized else ""

    if first_segment in _FORBIDDEN_TARGET_ROOTS:
        return _("alias vers un dossier interdit ({first_segment}/) : {target_path!r}").format(first_segment=first_segment, target_path=rule.target_path)

    if not rule.allow_outside_webroot and first_segment != "webroot":
        return (
            _("cible hors webroot sans allow_outside_webroot=true : {target_path!r}").format(target_path=rule.target_path)
        )

    return None
