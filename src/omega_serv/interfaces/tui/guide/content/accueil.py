"""Fiche guide : Accueil (plan guide d'aide, Phase 1)."""
from __future__ import annotations

from omega_serv.core.i18n import _
from omega_serv.interfaces.tui.guide.model import FieldGuide, ScreenGuide

HOME_SCREEN = ScreenGuide(
    screen_class_name="HomeScreen",
    title=_("Accueil"),
    acces=_("Écran racine, affiché au lancement de l'interface (après le splash)."),
    definition=(
        _("Menu principal : un bouton par grande section de l'application. Aucun réglage ici, "
        "uniquement de la navigation.")
    ),
    fields=(
        FieldGuide(
            label=_("Assistant premier lancement"),
            definition=_("Parcours guide en 8 étapes pour composer et écrire une première configuration."),
            utilisation=_("À utiliser une seule fois, au tout premier démarrage (ou pour repartir de zéro)."),
            action=_("Ouvre l'assistant."),
            reaction=_("Aucun effet tant que l'étape 7 (Résumé) n'a pas été validée - rien n'est écrit avant."),
        ),
        FieldGuide(
            label=_("Registre des capacités"),
            definition=_("Scan en lecture seule de l'environnement (port libre, openssl présent, PHP-FPM...)."),
            utilisation=_("Consultation uniquement."),
            action=_("Ouvre le registre des capacités."),
            reaction=_("Aucun effet (lecture seule)."),
        ),
        FieldGuide(
            label=_("Profils"),
            definition=_("Quatre profils de base preconfigures (minimal/standard/hardened/development)."),
            utilisation=_("Consultation puis application optionnelle."),
            action=_("Ouvre l'écran des profils."),
            reaction=_("Appliquer un profil ÉCRASE la configuration active - voir sa propre fiche."),
        ),
        FieldGuide(
            label=_("Configuration détaillée"),
            definition=_("Tous les réglages du serveur et des options superposables, écran par écran."),
            utilisation=_("Le cœur de la configuration au quotidien."),
            action=_("Ouvre le menu de configuration détaillée."),
            reaction=_("Dépend de l'écran ouvert ensuite - voir sa propre fiche."),
        ),
        FieldGuide(
            label=_("Gestion des logs"),
            definition=_("Consultation, suivi en direct, rotation/archivage et statistiques des journaux."),
            utilisation=_("Consultation et maintenance des logs."),
            action=_("Ouvre le menu de gestion des logs."),
            reaction=_("Dépend de l'écran ouvert ensuite - voir sa propre fiche."),
        ),
        FieldGuide(
            label=_("Service"),
            definition=_("Pilotage du service système (demarrer/arreter/redemarrer/recharger/installer)."),
            utilisation=_("À utiliser pour piloter le serveur en tant que service système."),
            action=_("Ouvre l'écran Service."),
            reaction=_("Voir sa propre fiche - certaines actions demandent une authentification (sudo)."),
        ),
        FieldGuide(
            label=_("Multi-instance / Instances (N)"),
            definition=_("Registre des installations d'OMEGA-SERV connues sur cette machine."),
            utilisation=_("Le libellé affiche le nombre d'instances dès que 2 ou plus sont enregistrées."),
            action=_("Ouvre l'écran Multi-instance."),
            reaction=_("Aucun effet direct (lecture) - voir sa propre fiche pour les actions possibles."),
        ),
        FieldGuide(
            label=_("État & Ressources"),
            definition=_("Vue d'ensemble en direct : état du serveur/service, flux du log d'accès, ressources système."),
            utilisation=_("À consulter pour un diagnostic rapide."),
            action=_("Ouvre l'écran État & Ressources."),
            reaction=_("Aucun effet (lecture, rafraîchie automatiquement toutes les 2 secondes)."),
        ),
        FieldGuide(
            label=_("Active Sécurité"),
            definition=_("Regroupe Active Defense (deception/menaces/incidents) et le pare-feu applicatif (WAF)."),
            utilisation=_("À utiliser pour la sécurité active du serveur."),
            action=_("Ouvre le menu Active Sécurité."),
            reaction=_("Dépend de l'écran ouvert ensuite - voir sa propre fiche."),
        ),
        FieldGuide(
            label=_("Audit de sécurité"),
            definition=_("Vérifications consultatives (service, rotation des logs, mode WAF...)."),
            utilisation=_("À lancer ponctuellement pour un avis global."),
            action=_("Ouvre l'écran d'audit."),
            reaction=_("Aucun effet (lecture seule)."),
        ),
        FieldGuide(
            label=_("Sauvegarde de configuration"),
            definition=_("Créer, lister, restaurer ou supprimer des sauvegardes complètes de la configuration."),
            utilisation=_("À utiliser avant un changement risque, ou pour migrer une configuration."),
            action=_("Ouvre l'écran de sauvegarde."),
            reaction=_("Restaurer ÉCRASE directement les fichiers vises - voir sa propre fiche."),
        ),
    ),
    consequences=_("Cet écran ne modifie jamais la configuration lui-même - uniquement de la navigation."),
    points_de_vigilance=(
        (
            _("Appuyer sur Échap depuis cet écran demande une confirmation de sortie de "
            "l'application (contrairement aux autres écrans, où Échap revient simplement en arrière).")
        ),
    ),
)
