"""Reglage de l'allocateur C pour les processus qui manipulent de grands blocs : `serve` avec l'authentification,
le reverse proxy, l'envoi de fichiers ou FastCGI (application/server/start_server.py::tune_allocator_for, au demarrage
et au rechargement), et l'administration web (au demarrage).

Constat du 2026-11-18 (remesure memoire 3.0.0, OMEGA-SERV_ETUDE_PROXY_ET_MEMOIRE.md §6) : glibc releve son seuil
`mmap` chaque fois qu'un grand bloc obtenu par `mmap` est rendu. Le premier hash scrypt (16 Mio) passe par `mmap`
et rend sa memoire ; le seuil monte alors a 16 Mio et le scrypt suivant est pris dans le tas, qui garde ensuite ces
16 Mio pour toujours (+15 Mo par processus, mesure). Fixer le seuil desactive ce reglage automatique : un bloc de
4 Mio ou plus passe toujours par `mmap` et revient au systeme des qu'il est libere ; les tampons ordinaires restent
dans le tas, aussi rapides qu'avant.

Sans glibc (musl, autre systeme) : rien n'est fait, jamais d'erreur."""
from __future__ import annotations

_M_MMAP_THRESHOLD = -3  # malloc.h de glibc
LARGE_BLOCK_BYTES = 4 * 1024 * 1024


def keep_large_blocks_out_of_heap() -> bool:
    """Vrai si le reglage a ete applique. A appeler une fois, au debut du processus."""
    try:
        import ctypes

        libc = ctypes.CDLL(None)
        mallopt = libc.mallopt
    except (OSError, AttributeError, ImportError):
        return False
    try:
        return bool(mallopt(_M_MMAP_THRESHOLD, LARGE_BLOCK_BYTES))
    except (OSError, ctypes.ArgumentError):
        return False
