"""Protection anti-stampede du cache de reponses proxiees (OMEGA-SERV_
PLAN-DETAILLE_REVERSE_PROXY.md §21 : Phase 8) - un `asyncio.Lock` par
cle de cache, construit a la demande : si une entree expire et que
plusieurs requetes concurrentes arrivent avant qu'une seule d'entre
elles n'ait fini de reconstituer le cache, UNE SEULE effectue
reellement l'appel au backend, les autres attendent son resultat
plutot que de toutes frapper le backend simultanement ("thundering
herd" classique sur une entree populaire qui expire).

Une seule instance par serveur (meme convention que `ProxyLoadBalancerState`/
`ProxyHealthState`) - jamais recreee par requete. Purement en memoire,
jamais persiste : un verrou qui n'existe pas encore signifie simplement
"personne n'est en train de reconstituer cette entree pour l'instant".

**Limite acceptee, pas corrigee** : le dictionnaire de verrous grandit
sans jamais retirer une entree (un objet `asyncio.Lock` par cle de
cache DISTINCTE jamais vue au cours de la vie du processus) - cout
memoire negligeable par verrou, mais pas de nettoyage. Une eviction
active risquerait une course (retirer un verrou pendant qu'une autre
coroutine l'attend deja) pour un gain memoire marginal - jamais corrige
sans besoin reel demontre (YAGNI)."""
from __future__ import annotations

import asyncio


class ProxyCacheLocks:
    def __init__(self) -> None:
        self._locks: dict[tuple[str, str], asyncio.Lock] = {}

    def get_lock(self, zone_key: str, cache_key: str) -> asyncio.Lock:
        key = (zone_key, cache_key)
        lock = self._locks.get(key)
        if lock is None:
            lock = asyncio.Lock()
            self._locks[key] = lock
        return lock
