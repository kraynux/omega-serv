"""« Arreter, restaurer, redemarrer » (decision utilisateur 2026-11-01) : seulement pour une sauvegarde qui
contient une base, quand le serveur tourne. Utilise le gestionnaire de service existant (systemd, OpenRC,
runit) ; un serveur lance a la main (sans service) n'est jamais arrete ici : l'utilisateur doit l'arreter
lui-meme. Le service est TOUJOURS redemarre a la fin, meme si la restauration echoue."""
from __future__ import annotations

import time
from collections.abc import Callable

from omega_serv.application.persistence.restore_backup import RestoreResult
from omega_serv.application.services.manage_service import start_service, stop_service
from omega_serv.core.i18n import _
from omega_serv.ports.service_manager_port import ServiceManagerPort

STOP_TIMEOUT_SECONDS = 60.0


def restore_stopping_service(
    restore: Callable[[], RestoreResult],
    manager: ServiceManagerPort,
    service_name: str,
    server_running: Callable[[], bool],
    *,
    sleep: Callable[[float], None] = time.sleep,
    monotonic: Callable[[], float] = time.monotonic,
) -> RestoreResult:
    stopped = stop_service(manager, service_name)
    if not stopped.success:
        return RestoreResult(False, _("Arrêt du service impossible ({message}) : rien n'a été restauré. Si le serveur a "
                                      "été lancé à la main, arrêtez-le puis restaurez.").format(message=stopped.message))
    deadline = monotonic() + STOP_TIMEOUT_SECONDS
    while server_running() and monotonic() < deadline:
        sleep(0.5)
    if server_running():
        start_service(manager, service_name)
        return RestoreResult(False, _("Le serveur ne s'est pas arrêté à temps : rien n'a été restauré, service relancé."))
    result = restore()
    started = start_service(manager, service_name)
    suffix = "" if started.success else " " + _("ATTENTION : redémarrage du service impossible ({message}).").format(
        message=started.message)
    return RestoreResult(result.success, result.message + suffix, databases=result.databases)
