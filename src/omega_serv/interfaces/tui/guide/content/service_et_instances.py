"""Fiches guide : Options (Phase 0 - ecran pilote), Service, Multi-
instance, Etat & Ressources, Simuler une requete, Verifier la
configuration (Phase 7)."""
from __future__ import annotations

from omega_serv.core.i18n import _
from omega_serv.interfaces.tui.guide.model import FieldGuide, ScreenGuide

OPTIONS_SCREEN = ScreenGuide(
    screen_class_name="OptionsScreen",
    title=_("Options"),
    acces=_("Accueil -> Configuration détaillée -> Voir options actives"),
    definition=(
        _("Active ou désactive les options superposables (fonctionnalités optionnelles qui "
        "s'ajoutent par-dessus le profil de base) et affiche leur état actuel.")
    ),
    fields=(
        FieldGuide(
            label=_("Sélection + Activer / Désactiver"),
            definition=_("Chaque ligne du tableau représente une option superposable connue."),
            utilisation=(
                _("14 options connues : dirlisting, waf, auth, fastcgi, aliases, redirects, "
                "rewrites, cache, trusted_proxy, upload, error_pages, access_control, "
                "reverse_proxy, active_defense.")
            ),
            action=_("Sélectionner une ligne puis Activer/Desactiver bascule option.enabled dans la configuration."),
            reaction=(
                _("Dépend de l'option : la plupart se rechargent à chaud (automatique si un "
                "service actif existe). La 1ere activation de fastcgi/reverse_proxy exige un "
                "REDÉMARRAGE COMPLET (leur client n'est construit qu'au démarrage). "
                "active_defense exige TOUJOURS un redémarrage complet, à l'activation comme à "
                "la désactivation.")
            ),
        ),
    ),
    consequences=(
        _("Activer une option ici ne configure que son interrupteur enabled - les réglages "
        "détaillés (zones, règles, seuils...) vivent dans le sous-écran dédié à cette option, "
        "dans Configuration détaillée.")
    ),
    points_de_vigilance=(
        (
            _("Activer une option ne suffit jamais à elle seule : sans un rechargement (ou "
            "redémarrage) du service déjà lancé, rien ne change réellement - voir la FAQ "
            "'Pourquoi mon option activée ne fonctionne pas ?'.")
        ),
    ),
)

SERVICE_SCREEN = ScreenGuide(
    screen_class_name="ServiceScreen",
    title=_("Service"),
    acces=_("Accueil -> Service"),
    definition=(
        _("Pilote le service système (systemd/OpenRC/runit) qui fait tourner OMEGA-SERV : "
        "demarrer/arreter/redemarrer/recharger, activer/desactiver au démarrage, installer/"
        "désinstaller l'unité.")
    ),
    fields=(
        FieldGuide(
            label=_("Nom du service"),
            definition=_("Le nom de l'unité système pilotée par cet écran."),
            utilisation=_("Chaîne libre - figé si cette instance est enregistrée en multi-instance."),
            action=_("Utilisé par tous les boutons de cet écran."),
            reaction=_("Aucun effet seul - simplement le nom cible des actions ci-dessous."),
        ),
        FieldGuide(
            label=_("Démarrer / Arrêter / Redémarrer / Recharger"),
            definition=_("Actions directes de contrôle du service - Recharger (SIGHUP) est léger, les autres coupent les connexions."),
            utilisation=_("Un clic suffit, aucune confirmation demandée pour ces 4 actions."),
            action=_("Exécute la commande système correspondante, avec élévation (sudo) ponctuelle si nécessaire."),
            reaction=_("Effet réel et immédiat sur le service."),
        ),
        FieldGuide(
            label=_("Activer / Désactiver au démarrage"),
            definition=_("Contrôle si le service démarre automatiquement avec la machine."),
            utilisation=_("Un clic suffit."),
            action=_("Modifie l'enregistrement systemd/OpenRC/runit."),
            reaction=_("N'affecte jamais l'état actuel du service, seulement son comportement au prochain démarrage machine."),
        ),
        FieldGuide(
            label=_("Installer l'unité (systemd uniquement)"),
            definition=_("Crée le fichier d'unité systemd, le compte système dédié, et prépare les accès nécessaires."),
            utilisation=_("Une seule fois par instance - demande confirmation et une authentification (sudo)."),
            action=_("Écrit /etc/systemd/system/<nom>.service, crée le compte dédié omega-serv/omega-serv."),
            reaction=(
                _("Deux garde-fous bloquent l'installation si un conflit est détecté (une autre "
                "unité pointe déjà vers ce répertoire, ou ce nom est déjà utilisé par une unité "
                "pointant ailleurs).")
            ),
        ),
        FieldGuide(
            label=_("Désinstaller l'unité (systemd uniquement)"),
            definition=_("Retire l'unité systemd installée."),
            utilisation=_("Demande confirmation et une authentification (sudo)."),
            action=_("Arrête le service et supprime le fichier d'unité."),
            reaction=_("Le compte système dédié et le répertoire projet ne sont jamais supprimés par cette action."),
        ),
    ),
    consequences=(
        _("Installer/Desinstaller ne sont proposes QUE pour systemd - désactivés pour OpenRC/"
        "runit (déjà configurés directement sur le système requis pour ces gestionnaires).")
    ),
    points_de_vigilance=(
        (
            _("Après 'Installer l'unité', une session déjà ouverte n'a pas automatiquement le "
            "nouveau groupe système créé pour le compte dédié - reconnectez votre session une "
            "seule fois si l'état semble incohérent (voir État & Ressources).")
        ),
    ),
)

INSTANCES_SCREEN = ScreenGuide(
    screen_class_name="InstancesScreen",
    title=_("Multi-instance"),
    acces=_("Accueil -> Instances (N)"),
    definition=(
        _("Registre de toutes les installations d'OMEGA-SERV connues sur cette machine, avec le "
        "statut systemd de chacune - permet de créer une nouvelle instance ou de basculer entre elles.")
    ),
    fields=(
        FieldGuide(
            label=_("Créer une nouvelle instance"),
            definition=_("Dupliqué cette installation vers un nouveau répertoire FRÈRE (jamais à l'intérieur de celui-ci)."),
            utilisation=_("Nom, répertoire parent, adresse d'écoute, port (un port libre est proposé par défaut)."),
            action=_("Copie le code/l'environnement, crée la nouvelle configuration et l'enregistre au registre."),
            reaction=_("Opération réelle sur disque, peut prendre du temps (progression affichée)."),
        ),
        FieldGuide(
            label=_("Piloter cette instance"),
            definition=_("Bascule l'interface pour piloter une AUTRE instance enregistrée, en quittant celle-ci."),
            utilisation=_("Sélectionner une instance différente de la courante (jamais soi-même)."),
            action=_("Ferme cette interface et relance l'application pointée sur l'autre répertoire."),
            reaction=_("Nécessite que l'environnement virtuel de l'instance cible existe réellement."),
        ),
        FieldGuide(
            label=_("Désinstaller cette instance"),
            definition=_("Retire l'unité systemd, le compte dédié (si plus utilisé par personne d'autre) et l'entrée du registre."),
            utilisation=_("Ne peut jamais cibler l'instance courante (basculer ailleurs d'abord)."),
            action=_("Deux confirmations : l'opération elle-même, puis si le répertoire doit aussi être supprimé."),
            reaction=_("Le répertoire n'est supprimé que sur confirmation explicite séparée - conservé par défaut."),
        ),
    ),
    consequences=_("Registre en lecture seule sinon - toute modification passe par les actions ci-dessus."),
)

RESOURCE_STATUS_SCREEN = ScreenGuide(
    screen_class_name="ResourceStatusScreen",
    title=_("État & Ressources"),
    acces=_("Accueil -> État & Ressources"),
    definition=(
        _("Tableau de bord en trois cadres, rafraîchi automatiquement toutes les 2 secondes : "
        "état du serveur/service, flux du log d'accès en direct, ressources système.")
    ),
    fields=(
        FieldGuide(
            label=_("Rafraîchir"),
            definition=_("Force un rafraîchissement immédiat (sans attendre le prochain cycle de 2s)."),
            utilisation=_("Aucune saisie."),
            action=_("Relit l'état, les nouvelles lignes de log et les ressources système."),
            reaction=_("Aucun effet (lecture seule)."),
        ),
        FieldGuide(
            label=_("Simuler une requête"),
            definition=_("Ouvre l'écran de simulation de routage."),
            utilisation=_("Aucune saisie ici."),
            action=_("Ouvre SimulateRequestScreen."),
            reaction=_("Aucun effet (lecture seule)."),
        ),
    ),
    consequences=_("Purement consultatif."),
    points_de_vigilance=(
        (
            _("Le cadre FLUX ne lit que le log d'accès au format 'combined' - un format différent "
            "ne produira aucune statistique.")
        ),
    ),
)

SIMULATE_REQUEST_SCREEN = ScreenGuide(
    screen_class_name="SimulateRequestScreen",
    title=_("Simuler une requête"),
    acces=_("Accueil -> État & Ressources -> Simuler une requête"),
    definition=(
        _("Rejoue le VRAI routage d'OMEGA-SERV (mêmes règles que pour une requête réseau réelle) "
        "sans envoyer de requête réseau - utile pour diagnostiquer une règle avant de la tester en vrai.")
    ),
    fields=(
        FieldGuide(
            label=_("Méthode"),
            definition=_("Méthode HTTP simulée."),
            utilisation=_("Chaîne libre, ex: GET, HEAD, POST. Valeur par défaut : GET."),
            action=_("Utilisée au clic sur Simuler."),
            reaction=_("Aucun effet (lecture seule, aucune requête réseau)."),
        ),
        FieldGuide(
            label=_("Chemin"),
            definition=_("Chemin d'URL simulé."),
            utilisation=_("Chaîne libre commençant par '/'. Valeur par défaut : /."),
            action=_("Utilisé au clic sur Simuler."),
            reaction=_("Aucun effet (lecture seule)."),
        ),
    ),
    consequences=_("Affiche le chemin normalisé, si la méthode est autorisée, si une règle bloque la requête, le statut de réponse attendu et les en-têtes attendus."),
)

CONFIG_CHECK_SCREEN = ScreenGuide(
    screen_class_name="ConfigCheckScreen",
    title=_("Vérifier la configuration"),
    acces=_("Accueil -> Configuration détaillée -> Vérifier la configuration"),
    definition=(
        _("Vérifie la configuration en deux couches : structurelle (déjà vérifiée au chargement) "
        "puis environnement réel (fichiers présents, permissions...).")
    ),
    fields=(
        FieldGuide(
            label=_("Vérifier"),
            definition=_("Relance explicitement la vérification."),
            utilisation=_("Aucune saisie - une première vérification a déjà lieu automatiquement à l'ouverture de l'écran."),
            action=_("Relit la configuration et l'environnement réel."),
            reaction=_("Aucun effet sur le serveur (lecture seule) - notifie explicitement le résultat sur un clic explicite."),
        ),
    ),
    consequences=_("Purement consultatif - ne modifie jamais rien."),
)
