"""Avertissement "redemarrage complet requis" (`notify_restart_required`)
ou "rechargement requis" (`notify_reload_required`), proposes depuis
n'importe quel ecran de configuration (retour utilisateur, guide d'aide
- point 4 : "soit le preciser et renvoyer a SERVICE, soit l'incorporer
(bouton redemarrer) dans l'interface de l'option selectionnee").

`notify_reload_required` couvre un angle mort reel trouve en testant
(retour utilisateur : "j'ai active le dir listing, ca marchait pas,
j'ai redemarre et ca marche... l'utilisateur va etre perdu") - AUCUN
ecran de configuration detaillee ne signalait qu'un changement ecrit
sur disque restait sans effet tant que le PROCESSUS DEJA LANCE n'avait
pas rechu la config (reload SIGHUP ou restart complet) : le silence de
`OptionsScreen`/`DirlistingScreen`/etc. apres "enregistre" laissait
croire a tort qu'aucune action supplementaire n'etait necessaire.
Verifie reellement (pas suppose) qu'un simple reload_scoped() suffit
deja pour dirlisting/access_control (route_request lit `self._config`
a chaque requete, remplace en bloc par reload_scoped - jamais besoin
d'un restart complet pour ces options-la, contrairement a bind/port/
TLS/listen_backlog/Active Defense qui restent sur
`notify_restart_required`).

`notify_reload_required` delegue a `_service_reload.py::reload_service_if_active`
(deja etabli et valide par l'utilisateur pour WAF le 2026-09-14 : "il
faut qu'il puisse pas taper de commande a chaque fois") - rechargement
AUTOMATIQUE et SILENCIEUX si aucun service actif n'est trouve, jamais de
confirmation pour un simple reload (leger, sans coupure de connexion).
`notify_restart_required` reste sur une confirmation explicite (`ConfirmScreen`)
car un restart complet, lui, coupe toutes les connexions en cours -
dissymetrie assumee, jamais un lancement privilegie de l'application
entiere, meme patron `_maybe_suspend` que service_screen.py (sudo
ponctuel par action, plan interface §3.6)."""
from __future__ import annotations

from typing import TYPE_CHECKING

from omega_serv.application.services.manage_service import restart_service
from omega_serv.application.services.resolve_current_service_name import (
    resolve_current_service_name,
)
from omega_serv.interfaces.tui.screens._service_reload import reload_service_if_active
from omega_serv.interfaces.tui.screens.confirm import ConfirmScreen

if TYPE_CHECKING:
    from omega_serv.bootstrap.container import DependencyContainer
    from omega_serv.interfaces.tui.screens._base import OmegaScreen
    from omega_serv.ports.service_manager_port import ServiceManagerPort


def notify_restart_required(screen: OmegaScreen, container: DependencyContainer, reason: str) -> None:
    """`reason` est deja la phrase complete decrivant pourquoi (ex:
    "bind/port necessitent...") - ce module se contente d'ajouter la
    proposition d'action, jamais de reformuler la raison metier propre
    a chaque ecran appelant."""
    factory = container.service_manager_factory
    manager = factory() if factory is not None else None
    if manager is None:
        screen.app.notify(reason, severity="warning", timeout=10)
        return

    service_name = resolve_current_service_name(
        container.instance_registry, container.filesystem, container.settings_store, container.project_root,
    )
    screen.app.push_screen(
        ConfirmScreen(
            title="REDEMARRAGE REQUIS",
            message=f"{reason}\n\nRedemarrer le service {service_name!r} maintenant ?",
        ),
        lambda confirmed: _restart_if_confirmed(screen, manager, service_name, confirmed),
    )


def _restart_if_confirmed(
    screen: OmegaScreen, manager: ServiceManagerPort, service_name: str, confirmed: bool | None,
) -> None:
    if not confirmed:
        screen.app.notify(
            "Redemarrage non effectue - pensez a le faire manuellement (ecran SERVICE) des que possible.",
            severity="warning", timeout=10,
        )
        return
    with screen._maybe_suspend():
        result = restart_service(manager, service_name)
    screen.app.notify(result.message, severity="information" if result.success else "error")


def notify_reload_required(screen: OmegaScreen, container: DependencyContainer, reason: str) -> None:
    """Meme role que `notify_restart_required`, pour un changement qui
    n'a besoin que d'un rechargement (SIGHUP) - jamais un restart
    complet. `reason` reste la phrase decrivant CE qui vient d'etre
    enregistre (ex: "Option 'dirlisting' activee.").

    Contrairement au restart, jamais de confirmation ici : un reload est
    leger (aucune coupure de connexion), donc declenche automatiquement
    des qu'un service actif existe (meme mecanisme deja valide pour WAF,
    voir docstring de module) - `reason` est toujours notifie, le
    resultat du reload s'y ajoute s'il a reellement eu lieu."""
    screen.app.notify(reason)
    reload_message = reload_service_if_active(screen, container)
    if reload_message is not None:
        screen.app.notify(reload_message)
        return
    screen.app.notify(
        "Rechargez le serveur en cours (ecran SERVICE -> Recharger) ou redemarrez-le pour appliquer "
        "ce changement - rien n'est repris automatiquement par un processus deja lance.",
        severity="warning", timeout=10,
    )
