# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Retour utilisateur 2026-09-14 : "il faut qu'il puisse pas taper de
commande a chaque fois qu'il change le mode de blocage ou met une
nouvelle regle" - le rechargement a chaud (SIGHUP) existait deja
(bouton "Recharger" de l'ecran Service, meme cas d'usage `reload_service`)
mais restait une action manuelle SEPAREE, facile a oublier apres avoir
enregistre un changement ailleurs dans l'interface. `reload_service_if_active`
declenche ce meme rechargement AUTOMATIQUEMENT juste apres une sauvegarde
reelle - jamais un echec bloquant : la sauvegarde elle-meme (deja faite
par l'appelant AVANT ce declenchement) reste TOUJOURS acquise
independamment du resultat du rechargement.

Ne notifie l'utilisateur QUE si un service reellement actif existe pour
ce repertoire (jamais un avertissement "service introuvable" a chaque
sauvegarde pour qui developpe sans jamais avoir installe de service -
c'est une situation normale, pas une erreur).

Introduit pour WAF (`reload_service_after_waf_change`, nom historique
conserve tel quel - tests/imports existants) puis generalise (guide
d'aide, point 4) : le meme angle mort ("rien ne previent qu'un
changement ecrit sur disque reste sans effet tant que le processus deja
lance n'a pas rechu la config") touchait en realite TOUTE option
hot-reloadable, pas seulement WAF - meme mecanisme reutilise maintenant
par `restart_prompt.py::notify_reload_required`."""
from __future__ import annotations

from typing import TYPE_CHECKING

from omega_serv.application.services.resolve_current_service_name import (
    resolve_current_service_name,
)

if TYPE_CHECKING:
    from omega_serv.bootstrap.container import DependencyContainer


def reload_service_if_active(container: DependencyContainer) -> str | None:
    """Retourne un message a notifier (succes ou echec du rechargement),
    ou None s'il n'y a rien a signaler (aucun gestionnaire de service
    disponible, ou aucun service actif sous ce nom pour ce repertoire) -
    jamais une exception, meme principe de robustesse deja applique a
    FileLineLogger.append_line (un effet de bord auxiliaire ne doit
    jamais faire echouer l'action principale)."""
    try:
        factory = container.service_manager_factory
        if factory is None:
            return None
        manager = factory()
        if manager is None:
            return None

        service_name = resolve_current_service_name(
            container.instance_registry, container.filesystem, container.settings_store, container.project_root,
        )
        if not manager.is_active(service_name):
            return None

        from omega_serv.application.services.manage_service import reload_service

        return reload_service(manager, service_name).message
    except Exception:  # noqa: BLE001 - effet de bord auxiliaire, jamais une raison d'echouer la sauvegarde appelante
        return None


def reload_service_after_waf_change(container: DependencyContainer) -> str | None:
    """Alias historique (retour utilisateur 2026-09-14, WAF) - voir
    `reload_service_if_active`, strictement la meme fonction, conserve
    pour ne pas renommer un nom deja repris par tests/imports existants."""
    return reload_service_if_active(container)
