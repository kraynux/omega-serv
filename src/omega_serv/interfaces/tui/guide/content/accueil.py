"""Fiche guide : Accueil (plan guide d'aide, Phase 1)."""
from __future__ import annotations

from omega_serv.interfaces.tui.guide.model import FieldGuide, ScreenGuide

HOME_SCREEN = ScreenGuide(
    screen_class_name="HomeScreen",
    title="Accueil",
    acces="Ecran racine, affiche au lancement de l'interface (apres le splash).",
    definition=(
        "Menu principal : un bouton par grande section de l'application. Aucun reglage ici, "
        "uniquement de la navigation."
    ),
    fields=(
        FieldGuide(
            label="Assistant premier lancement",
            definition="Parcours guide en 8 etapes pour composer et ecrire une premiere configuration.",
            utilisation="A utiliser une seule fois, au tout premier demarrage (ou pour repartir de zero).",
            action="Ouvre l'assistant.",
            reaction="Aucun effet tant que l'etape 7 (Resume) n'a pas ete validee - rien n'est ecrit avant.",
        ),
        FieldGuide(
            label="Registre des capacites",
            definition="Scan en lecture seule de l'environnement (port libre, openssl present, PHP-FPM...).",
            utilisation="Consultation uniquement.",
            action="Ouvre le registre des capacites.",
            reaction="Aucun effet (lecture seule).",
        ),
        FieldGuide(
            label="Profils",
            definition="Quatre profils de base preconfigures (minimal/standard/hardened/development).",
            utilisation="Consultation puis application optionnelle.",
            action="Ouvre l'ecran des profils.",
            reaction="Appliquer un profil ECRASE la configuration active - voir sa propre fiche.",
        ),
        FieldGuide(
            label="Configuration detaillee",
            definition="Tous les reglages du serveur et des options superposables, ecran par ecran.",
            utilisation="Le cœur de la configuration au quotidien.",
            action="Ouvre le menu de configuration detaillee.",
            reaction="Depend de l'ecran ouvert ensuite - voir sa propre fiche.",
        ),
        FieldGuide(
            label="Gestion des logs",
            definition="Consultation, suivi en direct, rotation/archivage et statistiques des journaux.",
            utilisation="Consultation et maintenance des logs.",
            action="Ouvre le menu de gestion des logs.",
            reaction="Depend de l'ecran ouvert ensuite - voir sa propre fiche.",
        ),
        FieldGuide(
            label="Service",
            definition="Pilotage du service systeme (demarrer/arreter/redemarrer/recharger/installer).",
            utilisation="A utiliser pour piloter le serveur en tant que service systeme.",
            action="Ouvre l'ecran Service.",
            reaction="Voir sa propre fiche - certaines actions demandent une authentification (sudo).",
        ),
        FieldGuide(
            label="Multi-instance / Instances (N)",
            definition="Registre des installations d'OMEGA-SERV connues sur cette machine.",
            utilisation="Le libelle affiche le nombre d'instances des que 2 ou plus sont enregistrees.",
            action="Ouvre l'ecran Multi-instance.",
            reaction="Aucun effet direct (lecture) - voir sa propre fiche pour les actions possibles.",
        ),
        FieldGuide(
            label="Etat & Ressources",
            definition="Vue d'ensemble en direct : etat du serveur/service, flux du log d'acces, ressources systeme.",
            utilisation="A consulter pour un diagnostic rapide.",
            action="Ouvre l'ecran Etat & Ressources.",
            reaction="Aucun effet (lecture, rafraichie automatiquement toutes les 2 secondes).",
        ),
        FieldGuide(
            label="Active Securite",
            definition="Regroupe Active Defense (deception/menaces/incidents) et le pare-feu applicatif (WAF).",
            utilisation="A utiliser pour la securite active du serveur.",
            action="Ouvre le menu Active Securite.",
            reaction="Depend de l'ecran ouvert ensuite - voir sa propre fiche.",
        ),
        FieldGuide(
            label="Audit de securite",
            definition="Verifications consultatives (service, rotation des logs, mode WAF...).",
            utilisation="A lancer ponctuellement pour un avis global.",
            action="Ouvre l'ecran d'audit.",
            reaction="Aucun effet (lecture seule).",
        ),
        FieldGuide(
            label="Sauvegarde de configuration",
            definition="Créer, lister, restaurer ou supprimer des sauvegardes completes de la configuration.",
            utilisation="A utiliser avant un changement risque, ou pour migrer une configuration.",
            action="Ouvre l'ecran de sauvegarde.",
            reaction="Restaurer ECRASE directement les fichiers vises - voir sa propre fiche.",
        ),
    ),
    consequences="Cet ecran ne modifie jamais la configuration lui-meme - uniquement de la navigation.",
    points_de_vigilance=(
        (
            "Appuyer sur Echap depuis cet ecran demande une confirmation de sortie de "
            "l'application (contrairement aux autres ecrans, ou Echap revient simplement en arriere)."
        ),
    ),
)
