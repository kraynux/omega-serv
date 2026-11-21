"""Donnees des zones personnalisees (demande de l'auteur du 2026-11-15) : les dossiers vers lesquels pointent les
zones, a sauvegarder a part du contenu du site. Les reglages des zones (alias, rewrites, listing, cache,
redirections, FastCGI) sont dans `config/omega-serve.json`, toujours sauvegarde ; ici, seulement les fichiers :

- alias : dossier cible (dans le webroot, ailleurs dans le dossier omega-serv, ou hors du projet : alors signale
  et non sauvegarde, comme tout element hors du dossier omega-serv) ;
- listing de repertoire : dossier de chaque zone (sous le webroot, avec ses fichiers d'en-tete et de README) ;
- FastCGI : racine des scripts (`script_root`, toujours hors du webroot).

Rewrites, redirections et cache n'ont que des reglages ; le cache du reverse proxy (`var/cache/reverse_proxy/`) se
reconstruit et n'est jamais sauvegarde."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from omega_serv.core.i18n import _
from omega_serv.domain.config.entities import OmegaServConfig
from omega_serv.domain.routing.alias import parse_alias_rules
from omega_serv.domain.routing.fastcgi_zone import fastcgi_zone_entries, parse_fastcgi_zones

INSTALLATION_NAMES = frozenset({
    "bin", "build", "docs", "native", "src", "tests", "tools", "venv", "dist", "omega_serv",
    "install.sh", "omega-serv.sh", "migrate-state.sh", "build-release.sh", "pyproject.toml", "LICENSE",
    *(stem + ".md" for stem in ("README", "CHANGELOG")),
})
"""Emplacements livres par l'archive d'installation : une sauvegarde importee ne peut jamais les ecrire, meme si
la configuration qu'elle contient y fait pointer une zone."""


def _alias_rules(settings: Mapping[str, Any]) -> list[Any]:
    raw = settings.get("list", [])
    try:
        return parse_alias_rules([item for item in raw if isinstance(item, dict)]) if isinstance(raw, list) else []
    except (KeyError, TypeError):
        return []


def zone_data_paths(config: OmegaServConfig) -> list[tuple[Path, str]]:
    """(chemin tel que configure, etiquette) de chaque dossier de zone ; relatif = relatif au dossier omega-serv."""
    paths: list[tuple[Path, str]] = []
    aliases = config.options.get("aliases")
    if aliases is not None:
        for rule in _alias_rules(aliases.settings):
            paths.append((Path(rule.target_path), _("alias {prefix}").format(prefix=rule.url_prefix)))
    dirlisting = config.options.get("dirlisting")
    if dirlisting is not None:
        for prefix in dirlisting.settings.get("zone_prefixes", []) or []:
            if isinstance(prefix, str) and prefix.strip("/"):
                paths.append((Path(config.paths.webroot) / prefix.strip("/"),
                              _("listing {prefix}").format(prefix=prefix)))
    fastcgi = config.options.get("fastcgi")
    if fastcgi is not None:
        for zone in parse_fastcgi_zones(fastcgi.settings):
            if zone.script_root:
                paths.append((Path(zone.script_root), _("scripts FastCGI {prefix}").format(prefix=zone.url_prefix)))
    return paths


def zone_data_roots(raw_config: Mapping[str, Any]) -> frozenset[str]:
    """Premiers dossiers (dans le projet, hors webroot) que la configuration d'une archive designe comme donnees de
    zones : seuls emplacements que l'import accepte en plus de config/, secure/, var/ et du webroot. Jamais un
    emplacement de l'installation (INSTALLATION_NAMES) ni un nom cache."""
    options = raw_config.get("options", {})
    if not isinstance(options, Mapping):
        return frozenset()
    targets: list[str] = []
    aliases = options.get("aliases", {})
    if isinstance(aliases, Mapping):
        targets.extend(rule.target_path for rule in _alias_rules(aliases))
    fastcgi = options.get("fastcgi", {})
    if isinstance(fastcgi, Mapping):
        targets.extend(entry["script_root"] for entry in fastcgi_zone_entries(dict(fastcgi))
                       if isinstance(entry.get("script_root"), str))
    roots: set[str] = set()
    for target in targets:
        path = PurePosixPath(target.replace("\\", "/"))
        if path.is_absolute() or not path.parts or ".." in path.parts:
            continue
        top = path.parts[0]
        if top in (".", "") or top.startswith(".") or top in INSTALLATION_NAMES:
            continue
        roots.add(top)
    return frozenset(roots)


@dataclass(frozen=True)
class MissingZoneFolder:
    """Dossier vers lequel pointe une zone active, absent du disque (projets 3.0.0 §8.2, P1, decision de l'auteur du
    2026-11-16). `blocking` : zone FastCGI active, le serveur refuse de demarrer tant qu'il manque."""

    label: str
    path: Path
    blocking: bool

    def message(self) -> str:
        if self.blocking:
            return _("{label} : dossier absent ({path}). Le serveur ne démarre pas tant qu'il manque : remettez le "
                     "dossier, ou désactivez cette zone (Configuration détaillée → FastCGI).").format(
                label=self.label, path=self.path)
        return _("{label} : dossier absent ({path}). Cette zone répond 404 tant qu'il manque.").format(
            label=self.label, path=self.path)

    def log_text(self) -> str:
        """Texte non traduit pour error.log (meme convention que les autres lignes du journal)."""
        return f"dossier de zone absent : {self.label} ({self.path})"


def _enabled(config: OmegaServConfig, name: str) -> Any:
    option = config.options.get(name)
    return option if option is not None and option.enabled else None


def missing_zone_folders(config: OmegaServConfig, project_root: Path) -> list[MissingZoneFolder]:
    """Dossiers des zones ACTIVES absents du disque : cible d'un alias (dossier ou fichier), dossier d'une zone de
    listing, racine des scripts d'une zone FastCGI active. Une option desactivee n'est jamais signalee."""
    missing: list[MissingZoneFolder] = []

    def resolve(target: str) -> Path:
        path = Path(target)
        return path if path.is_absolute() else project_root / path

    aliases = _enabled(config, "aliases")
    if aliases is not None:
        for rule in _alias_rules(aliases.settings):
            path = resolve(rule.target_path)
            if not path.exists():
                missing.append(MissingZoneFolder(_("alias {prefix}").format(prefix=rule.url_prefix), path, False))
    dirlisting = _enabled(config, "dirlisting")
    if dirlisting is not None:
        for prefix in dirlisting.settings.get("zone_prefixes", []) or []:
            if isinstance(prefix, str) and prefix.strip("/"):
                path = resolve(config.paths.webroot) / prefix.strip("/")
                if not path.is_dir():
                    missing.append(MissingZoneFolder(_("listing {prefix}").format(prefix=prefix), path, False))
    fastcgi = _enabled(config, "fastcgi")
    if fastcgi is not None:
        for zone in parse_fastcgi_zones(fastcgi.settings):
            if zone.enabled and zone.script_root:
                path = resolve(zone.script_root)
                if not path.is_dir():
                    missing.append(MissingZoneFolder(
                        _("scripts FastCGI {prefix}").format(prefix=zone.url_prefix), path, True))
    return missing
