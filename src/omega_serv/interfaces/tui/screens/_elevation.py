"""Point d'entree UNIQUE pour demander sudo depuis un ecran de logs (2026-11-07, porte d'omega-log) :
l'ecran est suspendu, `sudo -v` demande le mot de passe sur le vrai terminal, puis l'interface reprend.
Retourne le runner a utiliser (deja root ou authentification reussie), None sinon - l'utilisateur est
prevenu, jamais une exception."""
from __future__ import annotations

from typing import TYPE_CHECKING

from omega_serv.application.logs.privileged_logs import authenticate
from omega_serv.core.i18n import _

if TYPE_CHECKING:
    from omega_serv.bootstrap.container import DependencyContainer
    from omega_serv.interfaces.tui.screens._base import OmegaScreen
    from omega_serv.ports.process_runner_port import ProcessRunnerPort


def request_elevation(screen: OmegaScreen, container: DependencyContainer) -> ProcessRunnerPort | None:
    factory = container.privileged_runner_factory
    if factory is None:
        screen.app.notify(_("sudo indisponible dans cet environnement."), severity="error")
        return None
    runner = factory()
    with screen._maybe_suspend():
        authenticated = authenticate(runner)
    if not authenticated:
        screen.app.notify(_("Authentification sudo échouée ou annulée."), severity="error")
        return None
    return runner
