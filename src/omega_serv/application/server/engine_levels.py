"""Moteur HTTP : nombre de processus et connecteurs (plan moteur C++ §5, §7, §16.5 et §25).

Decision utilisateur 2026-11-04 (§25) : plus de niveaux (Normal / Boost / Superboost / Hyperboost, qui laissaient
supposer un mode superieur alors que l'effet depend du WAF et des coeurs). On affiche ce qui tourne : « moteur
Python, 2 processus », « moteur natif, 1 processus ». Le moteur se choisit dans « Configuration de base »
(`server.engine`), le nombre de processus dans « Resistance et limites » (`server.workers`), borne selon le moteur
et le processeur detecte - d'apres les mesures du comparatif (docs/comparatif-serveurs-web.md, 3 machines) :
  - moteur Python : chaque processus sert les requetes, le debit monte jusqu'au nombre de coeurs physiques ;
  - moteur natif : il occupe deja tous les coeurs ; les processus sont ceux des controles de securite (Python),
    un 2e n'apporte qu'a partir de 4 coeurs physiques (x1,5 a 1,7 avec WAF), un 3e ou un 4e presque rien (+4 %).
Une valeur au-dela du maximum est refusee par l'interface ; dans un fichier (configuration copiee d'une autre
machine, ancien `0` = automatique), elle est ramenee au maximum avec un message, jamais un refus de demarrer.

Les connecteurs disent, fonction active par fonction active, qui la sert avec le moteur natif : le natif seul, le
processus Python de securite (controle de chaque requete), une route demandee a Python, une connexion confiee a
Python - ou rien (repli complet sur le moteur Python, decide par `decide_engine`, jamais un serveur partiel)."""
from __future__ import annotations

from dataclasses import replace

from omega_serv.application.server.engine_selection import (
    APPLICATION_OPTIONS,
    ZONE_CACHE,
    decide_engine,
    decide_proxy_zones,
)
from omega_serv.core.i18n import _
from omega_serv.domain.config.entities import OmegaServConfig

NATIVE_SECOND_PROCESS_MIN_CORES = 4
"""Coeurs physiques a partir desquels un 2e processus de securite apporte du debit avec le moteur natif."""

NATIVE = "native"
PYTHON_CHECK = "python_check"
PYTHON_ROUTE = "python_route"
PYTHON_CONNECTION = "python_connection"
UNSUPPORTED = "unsupported"


def max_workers(engine: str, usable_cores: int) -> int:
    """Nombre maximal de processus pour `engine` sur une machine de `usable_cores` coeurs physiques utilisables."""
    if engine == "native":
        return 2 if usable_cores >= NATIVE_SECOND_PROCESS_MIN_CORES else 1
    return max(1, usable_cores)


def describe_run(engine: str, workers: int) -> str:
    """Ce qui tourne, sans nom de niveau : « moteur natif, 2 processus »."""
    if engine == "native":
        return _("moteur natif, {workers} processus").format(workers=workers)
    return _("moteur Python, {workers} processus").format(workers=workers)


def native_blockers(config: OmegaServConfig, binary_problem: str | None) -> tuple[str, ...]:
    """Ce qui empecherait le natif de tourner avec `config` (vide : le choix « natif » est possible). Meme
    fonction que le demarrage (`decide_engine`), appliquee a la configuration avec le natif demande."""
    probe = replace(config, server=replace(config.server, engine="native"))
    return decide_engine(probe, binary_problem).reasons


_ZONE_INDENT = "  "
_ZONE_LABEL_MAX = 16
"""Colonne etroite de l'ecran Etat : un prefixe plus long est coupe (le libelle le plus long fixe l'alignement)."""


def _short_prefix(prefix: str) -> str:
    return prefix if len(prefix) <= _ZONE_LABEL_MAX else prefix[:_ZONE_LABEL_MAX - 1] + "…"


def engine_connectors(config: OmegaServConfig) -> list[tuple[str, str]]:
    """(fonction, mode) pour les fonctions ACTIVES de `config`, avec le moteur natif. Libelles et modes courts :
    bloc aligne dans une colonne etroite de l'ecran Etat."""
    rows: list[tuple[str, str]] = [(_("Statique"), NATIVE), (_("Limites"), NATIVE)]
    if config.option_enabled("trusted_proxy"):
        rows.append((_("IP via proxy"), NATIVE))
    direct_tls = config.tls.enabled and config.tls.mode == "direct"
    if direct_tls:
        rows.append((_("TLS direct"), NATIVE))
    for option, label in (("waf", _("WAF")), ("active_defense", _("Active Defense")), ("auth", _("Auth"))):
        if config.option_enabled(option):
            rows.append((label, PYTHON_CHECK))
    if config.option_enabled("dirlisting"):
        rows.append((_("Listing"), PYTHON_ROUTE))
    if config.option_enabled("trusted_proxy"):
        rows.append((_("/load, /admin"), PYTHON_ROUTE))
    labels = {"reverse_proxy": _("Reverse proxy"), "fastcgi": _("FastCGI"), "upload": _("Upload")}
    for option in APPLICATION_OPTIONS:
        if not config.option_enabled(option):
            continue
        if option == "reverse_proxy":
            # Plan proxy natif v2 (lots 4 a 11) : zones relayees par le natif, TLS direct compris (lot 9). Lot 11 :
            # detail par zone - si certaines zones seulement sont confiees (cache), une ligne par zone confiee sous
            # « natif ». Avec TLS direct, une zone confiee fait tout demarrer en Python (P7) : ligne unique.
            zones = decide_proxy_zones(config)
            delegated = [zone.url_prefix for zone in zones if zone.engine == "python"]
            if zones and not (direct_tls and delegated) and len(delegated) < len(zones):
                rows.append((labels[option], NATIVE))
                rows.extend((_ZONE_INDENT + _short_prefix(prefix), PYTHON_CONNECTION) for prefix in delegated)
                continue
        rows.append((labels[option], UNSUPPORTED if direct_tls else PYTHON_CONNECTION))
    return rows


def zone_engine_labels(config: OmegaServConfig) -> dict[str, str]:
    """Lot 11 (retour de l'auteur du 2026-11-14) : colonne « Moteur » de l'ecran Reverse proxy, par prefixe - le
    moteur prevu par la configuration (le binaire n'est pas verifie ici ; l'ecran Etat montre ce qui tourne). Une
    zone absente du resultat : option desactivee."""
    zones = decide_proxy_zones(config)
    if config.server.engine != "native":
        return {zone.url_prefix: _("Python") for zone in zones}
    if decide_engine(config, None).fallback:  # repli complet (P7, option non prise en charge) : tout en Python
        return {zone.url_prefix: _("Python (repli)") for zone in zones}
    labels = {}
    for zone in zones:
        if zone.engine == "native":
            labels[zone.url_prefix] = _("natif")
        elif ZONE_CACHE in zone.reasons:
            labels[zone.url_prefix] = _("Python (cache)")
        else:
            labels[zone.url_prefix] = _("Python (réglage)")
    return labels


def describe_connector(mode: str) -> str:
    if mode == NATIVE:
        return _("natif")
    if mode == PYTHON_CHECK:
        return _("contrôle Python")
    if mode == PYTHON_ROUTE:
        return _("route Python")
    if mode == PYTHON_CONNECTION:
        return _("confié à Python")
    return _("impossible (repli)")


def resolved_worker_count(configured: int, engine: str, usable_cores: int) -> int:
    """`server.workers` tel qu'il sera applique avec `engine` : ramene au maximum de la machine (0 = ancien
    « automatique » : le maximum) - meme regle que le demarrage (interfaces/cli/serve_workers.py::
    effective_worker_count ; accord verifie par les tests)."""
    maximum = max_workers(engine, usable_cores)
    if configured <= 0:
        return maximum
    return min(configured, maximum)


def worker_count_notice(configured: int, engine: str, usable_cores: int) -> str | None:
    """Pourquoi la valeur appliquee differe de `server.workers` (None : elle est appliquee telle quelle)."""
    applied = resolved_worker_count(configured, engine, usable_cores)
    if configured == applied:
        return None
    engine_name = _("moteur natif") if engine == "native" else _("moteur Python")
    if configured <= 0:
        return _("server.workers = {configured} (ancien réglage automatique) : {applied} processus, le maximum "
                 "de cette machine avec le {engine}.").format(configured=configured, applied=applied,
                                                                engine=engine_name)
    return _("server.workers = {configured} : {applied} processus au maximum sur cette machine avec le {engine} "
             "({cores} cœur(s) physique(s)).").format(configured=configured, applied=applied, engine=engine_name,
                                                      cores=usable_cores)
