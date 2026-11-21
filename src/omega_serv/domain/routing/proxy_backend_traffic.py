"""Tableau de bord par type d'instance (OMEGA-SERV_ETUDE_TABLEAU_DE_BORD_REVERSE_PROXY.md, decision de l'auteur du
2026-11-16, chantier 3 de OMEGA-SERV_PROJETS_3.0.0.md §9) : mesures en direct de chaque backend de reverse proxy.

Direct seulement, depuis le demarrage du serveur : jamais d'historique ni de fichier, jamais un champ de plus dans
access.log (format lu par omega-jail, RIPOSTE et les outils tiers).

Les deux moteurs comptent de la meme facon :
- une requete = une tentative envoyee a ce backend (un nouvel essai sur un autre backend compte chez l'autre) ;
- 502 = tentative en echec (connexion impossible, reponse invalide ou coupee, reponse trop grande) ;
- 504 = delai de lecture depasse apres l'envoi de la requete ;
- temps moyen = moyenne glissante deja tenue pour la strategie « le plus rapide » (un echec y compte pour le delai
  de lecture de la zone) ;
- en cours = requetes envoyees sans reponse finie."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal

from omega_serv.domain.config.entities import OmegaServConfig
from omega_serv.domain.routing.proxy_zone import parse_proxy_zones

InstanceKind = Literal["site", "php", "proxy", "mixed"]


def instance_kind(config: OmegaServConfig) -> InstanceKind:
    """Type d'instance lu dans la configuration, jamais devine du trafic (etude §3.1) :
    - reverse proxy : reverse_proxy actif avec une zone sur « / » (tout part aux backends) ;
    - mixte : reverse_proxy actif avec des zones qui ne couvrent pas « / » (le reste est servi en local) ;
    - application PHP : FastCGI actif (sans reverse proxy) ;
    - site : ni l'un ni l'autre (statique, listing, upload)."""
    proxy = config.options.get("reverse_proxy")
    if proxy is not None and proxy.enabled:
        zones = parse_proxy_zones(proxy.settings.get("zones", []))
        if zones:
            return "proxy" if any(zone.url_prefix == "/" for zone in zones) else "mixed"
    if config.option_enabled("fastcgi"):
        return "php"
    return "site"


@dataclass(frozen=True)
class BackendTraffic:
    """Une ligne du cadre BACKENDS : `name` = backend tel que configure (host:port) ; `address` = adresse reelle
    quand le natif a resolu un nom DNS en plusieurs adresses (« nom (adresse):port »), sinon egale a `name`."""
    zone: str
    name: str
    address: str
    engine: Literal["natif", "python"]
    status: str
    requests: int = 0
    errors_502: int = 0
    errors_504: int = 0
    avg_ms: float | None = None
    active: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BackendTraffic | None:
        """None pour une entree illisible (reponse d'un autre serveur, version differente) : jamais une exception."""
        try:
            avg = data.get("avg_ms")
            engine: Literal["natif", "python"] = "natif" if data.get("engine") == "natif" else "python"
            return cls(
                zone=str(data["zone"]), name=str(data["name"]), address=str(data.get("address") or data["name"]),
                engine=engine, status=str(data["status"]), requests=int(data.get("requests", 0)),
                errors_502=int(data.get("errors_502", 0)), errors_504=int(data.get("errors_504", 0)),
                avg_ms=None if avg is None else float(avg), active=int(data.get("active", 0)),
            )
        except (KeyError, TypeError, ValueError):
            return None
