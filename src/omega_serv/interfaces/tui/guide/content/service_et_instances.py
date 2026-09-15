# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Fiches guide : Options (Phase 0 - ecran pilote), Service, Multi-
instance, Etat & Ressources, Simuler une requete, Verifier la
configuration (Phase 7)."""
from __future__ import annotations

from omega_serv.interfaces.tui.guide.model import FieldGuide, ScreenGuide

OPTIONS_SCREEN = ScreenGuide(
    screen_class_name="OptionsScreen",
    title="Options",
    acces="Accueil -> Configuration detaillee -> Voir options actives",
    definition=(
        "Active ou desactive les options superposables (fonctionnalites optionnelles qui "
        "s'ajoutent par-dessus le profil de base) et affiche leur etat actuel."
    ),
    fields=(
        FieldGuide(
            label="Selection + Activer / Desactiver",
            definition="Chaque ligne du tableau represente une option superposable connue.",
            utilisation=(
                "14 options connues : dirlisting, waf, auth, fastcgi, aliases, redirects, "
                "rewrites, cache, trusted_proxy, upload, error_pages, access_control, "
                "reverse_proxy, active_defense."
            ),
            action="Selectionner une ligne puis Activer/Desactiver bascule option.enabled dans la configuration.",
            reaction=(
                "Depend de l'option : la plupart se rechargent a chaud (automatique si un "
                "service actif existe). La 1ere activation de fastcgi/reverse_proxy exige un "
                "REDEMARRAGE COMPLET (leur client n'est construit qu'au demarrage). "
                "active_defense exige TOUJOURS un redemarrage complet, a l'activation comme a "
                "la desactivation."
            ),
        ),
    ),
    consequences=(
        "Activer une option ici ne configure que son interrupteur enabled - les reglages "
        "detailles (zones, regles, seuils...) vivent dans le sous-ecran dedie a cette option, "
        "dans Configuration detaillee."
    ),
    points_de_vigilance=(
        (
            "Activer une option ne suffit jamais a elle seule : sans un rechargement (ou "
            "redemarrage) du service deja lance, rien ne change reellement - voir la FAQ "
            "'Pourquoi mon option activee ne fonctionne pas ?'."
        ),
    ),
)

SERVICE_SCREEN = ScreenGuide(
    screen_class_name="ServiceScreen",
    title="Service",
    acces="Accueil -> Service",
    definition=(
        "Pilote le service systeme (systemd/OpenRC/runit) qui fait tourner OMEGA-SERV : "
        "demarrer/arreter/redemarrer/recharger, activer/desactiver au demarrage, installer/"
        "desinstaller l'unite."
    ),
    fields=(
        FieldGuide(
            label="Nom du service",
            definition="Le nom de l'unite systeme pilotee par cet ecran.",
            utilisation="Chaine libre - fige si cette instance est enregistree en multi-instance.",
            action="Utilise par tous les boutons de cet ecran.",
            reaction="Aucun effet seul - simplement le nom cible des actions ci-dessous.",
        ),
        FieldGuide(
            label="Demarrer / Arreter / Redemarrer / Recharger",
            definition="Actions directes de controle du service - Recharger (SIGHUP) est leger, les autres coupent les connexions.",
            utilisation="Un clic suffit, aucune confirmation demandee pour ces 4 actions.",
            action="Execute la commande systeme correspondante, avec elevation (sudo) ponctuelle si necessaire.",
            reaction="Effet reel et immediat sur le service.",
        ),
        FieldGuide(
            label="Activer / Desactiver au demarrage",
            definition="Controle si le service demarre automatiquement avec la machine.",
            utilisation="Un clic suffit.",
            action="Modifie l'enregistrement systemd/OpenRC/runit.",
            reaction="N'affecte jamais l'etat actuel du service, seulement son comportement au prochain demarrage machine.",
        ),
        FieldGuide(
            label="Installer l'unite (systemd uniquement)",
            definition="Cree le fichier d'unite systemd, le compte systeme dedie, et prepare les acces necessaires.",
            utilisation="Une seule fois par instance - demande confirmation et une authentification (sudo).",
            action="Ecrit /etc/systemd/system/<nom>.service, cree le compte dedie omega-serv/omega-serv.",
            reaction=(
                "Deux garde-fous bloquent l'installation si un conflit est detecte (une autre "
                "unite pointe deja vers ce repertoire, ou ce nom est deja utilise par une unite "
                "pointant ailleurs)."
            ),
        ),
        FieldGuide(
            label="Desinstaller l'unite (systemd uniquement)",
            definition="Retire l'unite systemd installee.",
            utilisation="Demande confirmation et une authentification (sudo).",
            action="Arrete le service et supprime le fichier d'unite.",
            reaction="Le compte systeme dedie et le repertoire projet ne sont jamais supprimes par cette action.",
        ),
    ),
    consequences=(
        "Installer/Desinstaller ne sont proposes QUE pour systemd - desactives pour OpenRC/"
        "runit (deja configures directement sur le systeme requis pour ces gestionnaires)."
    ),
    points_de_vigilance=(
        (
            "Apres 'Installer l'unite', une session deja ouverte n'a pas automatiquement le "
            "nouveau groupe systeme cree pour le compte dedie - reconnectez votre session une "
            "seule fois si l'etat semble incoherent (voir Etat & Ressources)."
        ),
    ),
)

INSTANCES_SCREEN = ScreenGuide(
    screen_class_name="InstancesScreen",
    title="Multi-instance",
    acces="Accueil -> Instances (N)",
    definition=(
        "Registre de toutes les installations d'OMEGA-SERV connues sur cette machine, avec le "
        "statut systemd de chacune - permet de creer une nouvelle instance ou de basculer entre elles."
    ),
    fields=(
        FieldGuide(
            label="Creer une nouvelle instance",
            definition="Duplique cette installation vers un nouveau repertoire FRERE (jamais a l'interieur de celui-ci).",
            utilisation="Nom, repertoire parent, adresse d'ecoute, port (un port libre est propose par defaut).",
            action="Copie le code/l'environnement, cree la nouvelle configuration et l'enregistre au registre.",
            reaction="Operation reelle sur disque, peut prendre du temps (progression affichee).",
        ),
        FieldGuide(
            label="Piloter cette instance",
            definition="Bascule l'interface pour piloter une AUTRE instance enregistree, en quittant celle-ci.",
            utilisation="Selectionner une instance differente de la courante (jamais soi-meme).",
            action="Ferme cette interface et relance l'application pointee sur l'autre repertoire.",
            reaction="Necessite que l'environnement virtuel de l'instance cible existe reellement.",
        ),
        FieldGuide(
            label="Desinstaller cette instance",
            definition="Retire l'unite systemd, le compte dedie (si plus utilise par personne d'autre) et l'entree du registre.",
            utilisation="Ne peut jamais cibler l'instance courante (basculer ailleurs d'abord).",
            action="Deux confirmations : l'operation elle-meme, puis si le repertoire doit aussi etre supprime.",
            reaction="Le repertoire n'est supprime que sur confirmation explicite separee - conserve par defaut.",
        ),
    ),
    consequences="Registre en lecture seule sinon - toute modification passe par les actions ci-dessus.",
)

RESOURCE_STATUS_SCREEN = ScreenGuide(
    screen_class_name="ResourceStatusScreen",
    title="Etat & Ressources",
    acces="Accueil -> Etat & Ressources",
    definition=(
        "Tableau de bord en trois cadres, rafraichi automatiquement toutes les 2 secondes : "
        "etat du serveur/service, flux du log d'acces en direct, ressources systeme."
    ),
    fields=(
        FieldGuide(
            label="Rafraichir",
            definition="Force un rafraichissement immediat (sans attendre le prochain cycle de 2s).",
            utilisation="Aucune saisie.",
            action="Relit l'etat, les nouvelles lignes de log et les ressources systeme.",
            reaction="Aucun effet (lecture seule).",
        ),
        FieldGuide(
            label="Simuler une requete",
            definition="Ouvre l'ecran de simulation de routage.",
            utilisation="Aucune saisie ici.",
            action="Ouvre SimulateRequestScreen.",
            reaction="Aucun effet (lecture seule).",
        ),
    ),
    consequences="Purement consultatif.",
    points_de_vigilance=(
        (
            "Le cadre FLUX ne lit que le log d'acces au format 'combined' - un format different "
            "ne produira aucune statistique."
        ),
    ),
)

SIMULATE_REQUEST_SCREEN = ScreenGuide(
    screen_class_name="SimulateRequestScreen",
    title="Simuler une requete",
    acces="Accueil -> Etat & Ressources -> Simuler une requete",
    definition=(
        "Rejoue le VRAI routage d'OMEGA-SERV (memes regles que pour une requete reseau reelle) "
        "sans envoyer de requete reseau - utile pour diagnostiquer une regle avant de la tester en vrai."
    ),
    fields=(
        FieldGuide(
            label="Methode",
            definition="Methode HTTP simulee.",
            utilisation="Chaine libre, ex: GET, HEAD, POST. Valeur par defaut : GET.",
            action="Utilisee au clic sur Simuler.",
            reaction="Aucun effet (lecture seule, aucune requete reseau).",
        ),
        FieldGuide(
            label="Chemin",
            definition="Chemin d'URL simule.",
            utilisation="Chaine libre commencant par '/'. Valeur par defaut : /.",
            action="Utilise au clic sur Simuler.",
            reaction="Aucun effet (lecture seule).",
        ),
    ),
    consequences="Affiche le chemin normalise, si la methode est autorisee, si une regle bloque la requete, le statut de reponse attendu et les en-tetes attendus.",
)

CONFIG_CHECK_SCREEN = ScreenGuide(
    screen_class_name="ConfigCheckScreen",
    title="Verifier la configuration",
    acces="Accueil -> Configuration detaillee -> Verifier la configuration",
    definition=(
        "Verifie la configuration en deux couches : structurelle (deja verifiee au chargement) "
        "puis environnement reel (fichiers presents, permissions...)."
    ),
    fields=(
        FieldGuide(
            label="Verifier",
            definition="Relance explicitement la verification.",
            utilisation="Aucune saisie - une premiere verification a deja lieu automatiquement a l'ouverture de l'ecran.",
            action="Relit la configuration et l'environnement reel.",
            reaction="Aucun effet sur le serveur (lecture seule) - notifie explicitement le resultat sur un clic explicite.",
        ),
    ),
    consequences="Purement consultatif - ne modifie jamais rien.",
)
