# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Mixin partage par les 4 ecrans Active Defense (status/threats/
incidents/deception) - `build_active_defense_collaborators` ouvre une
VRAIE connexion sqlite a chaque appel (correct pour le serveur HTTP, qui
ne l'appelle qu'une fois au demarrage et la garde pour toute la vie du
process) - jamais rappelee plusieurs fois pour un meme affichage
d'ecran ici, sous peine d'accumuler des connexions jamais fermees a
chaque interaction (selection de ligne, fermeture d'incident, export...)
au fil d'une session TUI longue. Mise en cache PAR INSTANCE D'ECRAN
(jamais partagee entre ecrans - une navigation retour puis ren-avant
doit revoir un etat frais)."""
from __future__ import annotations

from typing import TYPE_CHECKING

from omega_serv.application.config.load_config import load_config

if TYPE_CHECKING:
    from omega_serv.application.server.start_server import ActiveDefenseCollaborators
    from omega_serv.bootstrap.container import DependencyContainer


class ActiveDefenseCollaboratorsCacheMixin:
    """A melanger avec `OmegaScreen` (jamais utilisee seule) : suppose
    `self._container: DependencyContainer` deja present."""

    _container: DependencyContainer

    def _reset_active_defense_cache(self) -> None:
        self._active_defense: ActiveDefenseCollaborators | None = None
        self._active_defense_checked = False
        self._active_defense_error: str | None = None

    def _active_defense_or_none(self) -> ActiveDefenseCollaborators | None:
        if not hasattr(self, "_active_defense_checked"):
            self._reset_active_defense_cache()
        if self._active_defense_checked:
            return self._active_defense
        self._active_defense_checked = True
        load_result = load_config(self._container.configuration, self._container.config_file)
        if not load_result.success:
            self._active_defense_error = "Configuration introuvable ou invalide : " + "; ".join(load_result.errors)
            return None
        assert load_result.config is not None
        factory = self._container.active_defense_collaborators_factory
        if factory is None:
            self._active_defense_error = "Active Defense indisponible dans cet environnement."
            return None
        # Retour utilisateur 2026-09-13 : "gele le terminal, oblige de
        # killer" - `open_active_defense_connection` fait de la VRAIE
        # I/O disque (mkdir + sqlite3.connect) qui peut echouer pour de
        # vraies raisons d'environnement (permissions sur var/lib/ -
        # notamment si le repertoire appartient a l'utilisateur systeme
        # dedie omega-serv et que la session courante n'a pas encore
        # rafraichi son appartenance de groupe apres un ajout recent,
        # cas reellement rencontre) - jamais laisser une exception non
        # attrapee remonter dans un gestionnaire d'evenement Textual,
        # ou l'ecran peut rester bloque sans jamais restaurer le
        # terminal proprement plutot que de planter proprement.
        try:
            self._active_defense = factory(load_result.config, self._container.project_root)
        except OSError as exc:
            self._active_defense_error = (
                f"Erreur d'acces a la base Active Defense : {exc}. Si l'appartenance a un groupe "
                "systeme a change recemment (ex. compte de service dedie proprietaire de var/lib/), "
                "une NOUVELLE session (deconnexion/reconnexion) peut etre necessaire."
            )
            return None
        if self._active_defense is None:
            self._active_defense_error = "options.active_defense absent ou desactive de la configuration."
        return self._active_defense
