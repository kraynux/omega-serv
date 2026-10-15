"""Compteurs HIT/MISS cumules du cache de reponses proxiees (OMEGA-SERV_
PLAN-DETAILLE_REVERSE_PROXY.md §21, reouverture du §18.3/§22 : le ratio
hits/miss envisage dans l'etude initiale n'avait jamais pu etre cable au
TUI, le TUI et le serveur etant des processus SEPARES sans memoire
partagee - ferme par la route d'administration HTTP (§23, item
"Canal TUI<->serveur"), ce module reste pur domaine, agnostique du
transport qui l'expose.

EN MEMOIRE UNIQUEMENT, jamais persiste (§21 etude initiale : "compteurs
en memoire, jamais persistes") - redemarre a zero a chaque demarrage du
processus serveur, coherent avec l'intitule "depuis le dernier
demarrage" affiche par l'ecran TUI. Une seule instance par serveur,
jamais recreee par requete - meme convention que `ProxyHealthState`/
`ProxyLoadBalancerState`. BYPASS (cache desactive pour la zone/methode
non cacheable) ne compte JAMAIS dans ce ratio - ce n'est pas une
decision de cache, juste son absence."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class _ZoneCacheCounts:
    hits: int = 0
    misses: int = 0


class ProxyCacheMetrics:
    def __init__(self) -> None:
        self._counts: dict[str, _ZoneCacheCounts] = {}

    def record_hit(self, zone_key: str) -> None:
        self._counts.setdefault(zone_key, _ZoneCacheCounts()).hits += 1

    def record_miss(self, zone_key: str) -> None:
        self._counts.setdefault(zone_key, _ZoneCacheCounts()).misses += 1

    def snapshot(self, zone_key: str | None = None) -> tuple[int, int]:
        """`(hits, misses)` - pour UNE zone si `zone_key` est fourni,
        agrege sur TOUTES les zones connues sinon (jamais une moyenne,
        une vraie somme - un ratio global reste significatif meme si
        une zone domine le trafic)."""
        if zone_key is not None:
            counts = self._counts.get(zone_key)
            return (counts.hits, counts.misses) if counts is not None else (0, 0)
        total_hits = sum(c.hits for c in self._counts.values())
        total_misses = sum(c.misses for c in self._counts.values())
        return (total_hits, total_misses)
