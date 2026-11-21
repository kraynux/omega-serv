"""Adresses de cette machine et resolution DNS bornee (plan proxy natif v2, lot 3 : D17+, C18).

Lues pour le controle de boucle du reverse proxy : un backend qui vise une interface locale, sur le port d'ecoute,
c'est ce serveur lui-meme. psutil lit /proc (aucun sous-processus)."""
from __future__ import annotations

import socket
import threading
import time
from collections.abc import Iterable

DNS_TIMEOUT_SECONDS = 3.0
"""Resolution des noms de backend par `config check` : au-dela, le nom est ignore (pas d'avertissement), jamais un
blocage."""


def local_interface_addresses() -> frozenset[str]:
    """Adresses IPv4 et IPv6 de toutes les interfaces (sans l'indice de zone `%eth0`) ; vide si illisible."""
    import psutil  # ici : `serve` importe ce module sans lire les interfaces (0,8 Mo, 2026-11-19)

    addresses: set[str] = set()
    try:
        interfaces = psutil.net_if_addrs()
    except (OSError, RuntimeError):
        return frozenset()
    for entries in interfaces.values():
        for entry in entries:
            if entry.family in (socket.AF_INET, socket.AF_INET6) and entry.address:
                addresses.add(entry.address.split("%", 1)[0])
    return frozenset(addresses)


def resolve_hosts(hosts: Iterable[str], timeout: float = DNS_TIMEOUT_SECONDS) -> dict[str, tuple[str, ...]]:
    """Adresses de chaque nom (getaddrinfo, TCP), en parallele et bornees par `timeout` au total : un nom qui ne
    repond pas a temps est absent du resultat."""
    results: dict[str, tuple[str, ...]] = {}
    lock = threading.Lock()

    def resolve(host: str) -> None:
        try:
            infos = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
        except (OSError, UnicodeError):
            return
        found = tuple(dict.fromkeys(str(info[4][0]).split("%", 1)[0] for info in infos))
        with lock:
            results[host] = found

    threads = [threading.Thread(target=resolve, args=(host,), daemon=True) for host in dict.fromkeys(hosts)]
    for thread in threads:
        thread.start()
    deadline = time.monotonic() + timeout
    for thread in threads:
        thread.join(max(0.0, deadline - time.monotonic()))  # au total, pas par nom
    with lock:
        return dict(results)
