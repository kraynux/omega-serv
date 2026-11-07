"""Pool de PROCESSUS des calculs de logs (Statistiques, Voir et traiter IP) - porte d'omega-log le
2026-11-07 (OMEGA-SERV_A_FAIRE_STATS_DEPUIS_OMEGA_LOG.md, lot 1).

Un processus, pas un thread : le calcul est du Python pur, un thread se disputerait le GIL avec la boucle
de l'interface (mesure chez omega-log : 1,2 s de latence pendant le calcul, l'ecran « gele et degele »).

Amorcage AVANT `App.run()` (`warm_up_stats_pool`, appele par __main__.py) : Python demarre le pool en
« forkserver », un processus auxiliaire cree en forkant le processus principal au premier envoi. Forker
une fois le vrai pilote Textual lance (son thread de lecture clavier tourne deja) peut figer l'enfant pour
toujours. omega-log l'amorce a l'import de son module ; omega-serv l'amorce explicitement, juste avant
de construire l'interface, pour ne jamais le lancer dans `omega-serv serve` ni dans les commandes CLI.
Arret avant tout `os.execv` (changement de langue ou d'instance) et a la sortie : les processus du
pool ne survivent jamais a l'interface.

Taille : coeurs LOGIQUES moins un (laisse a l'interface), entre 2 et 8 (meme regle qu'omega-log)."""
from __future__ import annotations

import atexit
import os
from concurrent.futures import ProcessPoolExecutor

POOL_WORKERS = max(2, min(8, (os.cpu_count() or 2) - 1))
_pool: ProcessPoolExecutor | None = None


def stats_pool() -> ProcessPoolExecutor:
    """Le pool partage, cree au premier appel (les tests n'ont jamais besoin de l'amorcage)."""
    global _pool
    if _pool is None:
        _pool = ProcessPoolExecutor(max_workers=POOL_WORKERS)
        atexit.register(shutdown_stats_pool)
    return _pool


def warm_up_stats_pool() -> None:
    """Lance le forkserver MAINTENANT, avant le pilote Textual (voir la note du module)."""
    stats_pool().submit(int).result()


def shutdown_stats_pool() -> None:
    global _pool
    if _pool is not None:
        _pool.shutdown(cancel_futures=True)
        _pool = None
