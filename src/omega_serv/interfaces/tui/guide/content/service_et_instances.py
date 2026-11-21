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
                _("16 options connues : dirlisting, waf, auth, fastcgi, aliases, redirects, rewrites, cache, "
                  "trusted_proxy, upload, error_pages, access_control, reverse_proxy, active_defense, riposte, "
                  "admin_web.")
            ),
            action=_("Sélectionner une ligne puis Activer/Desactiver bascule option.enabled dans la configuration."),
            reaction=(
                _("Dépend de l'option : la plupart se rechargent à chaud (automatique si un "
                "service actif existe). La 1ere activation de fastcgi/reverse_proxy exige un "
                "REDÉMARRAGE COMPLET (leur client n'est construit qu'au démarrage). "
                "active_defense exige TOUJOURS un redémarrage complet, à l'activation comme à "
                "la désactivation.")
                + " " + _("riposte aussi : son processus est lancé et surveillé par le service au démarrage.")
                + " " + _("admin_web aussi : le processus d'administration web est lancé au démarrage ; ses réglages "
                "(adresse, port, TLS, réseaux permis) se font dans Instances -> Configuration distante.")
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
        _("Pilote le service système (systemd/OpenRC/runit) qui fait tourner OMEGA-SERV, en cinq lignes "
        "dans l'ordre d'usage : nom du service, installation, démarrage avec la machine, permissions, "
        "pilotage. Sous chaque titre, l'état actuel ; seuls les boutons qui ont un sens dans cet état sont "
        "actifs (par exemple Démarrer est grisé si le service tourne déjà, Installer si l'unité existe). "
        "L'état se met à jour seul toutes les 3 secondes et après chaque action.")
    ),
    fields=(
        FieldGuide(
            label=_("Nom du service"),
            definition=_("Le nom de l'unité système pilotée par cet écran. Le champ est verrouillé : une faute de "
                         "frappe ne peut plus changer le service piloté par accident."),
            utilisation=_("Modifier déverrouille le champ, Valider enregistre. 1 à 64 caractères : minuscules, "
                          "chiffres, « - », « _ », « . » (sans « .service »). Rien n'est enregistré avant Valider ; "
                          "Échap quitte l'écran sans rien changer. Figé si cette instance est enregistrée en "
                          "multi-instance."),
            action=_("Si une unité de cette installation existe sous l'ancien nom, une fenêtre détaille avant toute "
                     "action l'enchaînement : arrêter et désactiver l'ancienne, la désinstaller, installer la "
                     "nouvelle, puis la réactiver au démarrage et la redémarrer si c'était le cas (une seule "
                     "authentification sudo). Sans unité installée, seul le nom change."),
            reaction=_("Un nom déjà pris par une autre installation est refusé. Jamais deux unités pour le même "
                       "dossier. Si une étape échoue, l'enchaînement s'arrête et le message dit laquelle."),
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
            label=_("Permissions"),
            definition=_("Vérifie à l'ouverture, en lecture seule, que var/ est partagé avec le compte du service "
                         "(groupe omega-serv, lecture et écriture de groupe) ; var/backups, privé, est ignoré.")
            + " " + _("var/backups/logs (archives des journaux) est partagé avec le service pour que l'administration web puisse "
                      "archiver un journal et supprimer une archive ; var/backups reste privé, seulement traversable par le "
                      "service. Si le web affiche « Archives illisibles par le service » : Accueil -> Service -> Réparer les "
                      "permissions."),
            utilisation=_("État affiché sous le titre : correctes, « N à réparer » ou compte absent. Réparer les "
                          "permissions n'est actif que si quelque chose est faux (ou si la vérification n'a pas pu "
                          "se faire)."),
            action=_("Réparer réapplique le partage sur var/ et secure/auth/, avec confirmation et sudo, sans "
                     "toucher à l'unité."),
            reaction=_("Utile après une mise à jour par extraction d'archive, qui remet les permissions d'origine."),
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
        + " " + _("L'instance courante figure toujours en tête du tableau, marquée « (courante) », même quand elle "
                  "n'est pas inscrite au registre (installation d'origine) : sa Configuration distante est donc "
                  "toujours accessible.")
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
            label=_("Configuration distante"),
            definition=_("Règle l'administration web de l'instance choisie : adresse, port, chiffrement (TLS) et "
                         "réseaux permis. La colonne « Accès distant » dit, pour chaque instance, si elle est active."),
            utilisation=_("Sélectionner une instance dont l'option admin_web est active (Voir options actives) ; "
                          "sinon le bouton reste grisé et la raison s'affiche sous le tableau."),
            action=_("Instance pilotée : ouvre l'écran de réglage. Autre instance : demande confirmation (avec son "
                     "nom), bascule sur elle, puis ouvre son écran de réglage - jamais de réglage écrit à distance "
                     "dans une autre instance."),
            reaction=_("Aucun effet avant Enregistrer dans l'écran de réglage."),
        ),
        FieldGuide(
            label=_("Relier au maître"),
            definition=_("Fait suivre l'instance choisie par une autre instance de cette machine, depuis la page "
                         "Instances du tableau de bord web de ce maître."),
            utilisation=_("Sélectionner l'instance à suivre, puis choisir le maître (l'instance courante par défaut) "
                          "et ses droits : lecture ou administration. L'administration web doit être active sur les "
                          "deux ; sinon le bouton reste grisé et la raison s'affiche sous le tableau."),
            action=_("Chaque instance enregistre elle-même la liaison, par sa propre commande : l'instance suivie "
                     "accepte le maître, puis le maître l'ajoute à sa page Instances. Rien à recopier."),
            reaction=_("Si l'instance a déjà un autre maître, une confirmation est demandée : l'ancien est révoqué "
                       "aussitôt. Une instance d'une autre machine se relie par le code d'appairage (Configuration "
                       "distante -> Maître)."),
        ),
        FieldGuide(
            label=_("Désinstaller cette instance"),
            definition=_("Retire l'unité systemd, le compte dédié (si plus utilisé par personne d'autre) et l'entrée du registre."),
            utilisation=_("Ne peut jamais cibler l'instance courante, ni un répertoire qui la contient : le bouton "
                          "reste grisé et le programme refuse aussi de lui-même (basculer ailleurs d'abord)."),
            action=_("Deux confirmations : l'opération elle-même, puis si le répertoire doit aussi être supprimé."),
            reaction=_("Le répertoire n'est supprimé que sur confirmation explicite séparée - conservé par défaut."),
        ),
    ),
    consequences=_("Registre en lecture seule sinon - toute modification passe par les actions ci-dessus."),
)

ADMIN_WEB_SCREEN = ScreenGuide(
    screen_class_name="AdminWebScreen",
    title=_("Administration web - configuration distante"),
    acces=_("Accueil -> Instances -> Configuration distante"),
    definition=(
        _("Réglages de l'administration web : le tableau de bord de l'instance dans un navigateur, servi par un "
          "processus à part sur son propre port, jamais sur le port du site. L'option admin_web s'active dans Voir "
          "options actives (redémarrage complet).")
        + " " + _("Tout se règle dans cet écran, sans commande à taper ailleurs : le cadre État dit ce qui est prêt "
                  "et ce qui manque, avec le bouton qui le règle (Activer, Générer le certificat, Comptes, "
                  "Redémarrer, Recharger), l'adresse à ouvrir sur l'autre appareil et le pare-feu actif.")
        + " " + _("La page de connexion demande identifiant, mot de passe et code TOTP (s'il est activé), et le mode "
                  "d'arrivée : Tableau de bord (consulter) ou Administration (agir, comptes administration seulement). "
                  "Le Tableau de bord montre, rafraîchis toutes les 2 secondes : État & Ressources (les trois cadres de "
                  "l'écran du TUI, BACKENDS compris), Journaux (instantané ou direct : journaux de l'instance et "
                  "fichiers de la bibliothèque), Sécurité (bans, RIPOSTE, incidents) et, pour les comptes administration, le journal "
                  "d'audit.")
        + " " + _("La vue Historique trace la machine (processeur, mémoire, swap, charge, réseau, connexions, disque, "
                  "processus, température, batterie) et cette instance (requêtes, processus d'omega-serv, téléchargements et téléversement des visiteurs) sur 1 "
                  "heure, 3 heures, 12 heures, 24 heures, 7 jours ou 30 jours, en Moyenne ou en Max 1 min (la minute "
                  "la plus chargée de chaque tranche) ; le relevé continue même quand aucune page n'est ouverte.")
        + " " + _("Le mode Administration propose, chacune avec une page de confirmation et une ligne dans le journal "
                  "d'audit : bannir et débannir une adresse IP (intervention manuelle), fermer un incident, arrêt "
                  "d'urgence de RIPOSTE et sa levée, DRAINING, MAINTENANCE ou retour à l'automatique d'un backend, "
                  "archiver un journal de l'instance ou supprimer une archive, recharger la configuration. Une action "
                  "demande une saisie de moins de 15 minutes : sinon le mot de passe (et le code) est redemandé, puis "
                  "l'action est proposée de nouveau.")
        + " " + _("La page Instances fait de cette instance un maître : elle montre les instances qui l'ont acceptée "
                  "(état, type, requêtes par seconde, erreurs 5xx, bans, incidents), ouvre leur tableau de bord et, si "
                  "elles lui ont donné le droit d'administration, y lance les mêmes actions. Le bouton Maître règle "
                  "l'inverse : quel maître peut suivre cette instance.")
    ),
    fields=(
        FieldGuide(
            label=_("État"),
            definition=_("Bilan de l'administration web, une ligne par point : ✓ prêt, ✗ manque, • information."),
            utilisation=_("Option active ; adresse à ouvrir sur l'autre appareil ; certificat ; comptes et TOTP ; "
                          "port pris par une autre instance ; administration en écoute (ou la raison de son arrêt : "
                          "port pris par un autre programme, adresse absente, certificat illisible...) ; pare-feu "
                          "actif (ufw, firewalld, nftables) hors de cette machine."),
            action=_("Activer : option admin_web, puis redémarrage complet proposé. Générer le certificat : "
                     "auto-signé au nom de la machine et de ses adresses (valable 825 jours), clé lisible par le "
                     "service ; un ancien fichier est gardé en .ancien ; sudo est demandé seulement si votre session "
                     "n'a pas encore le groupe omega-serv. Comptes : créer un compte ou activer son TOTP. "
                     "Redémarrer, Recharger : le service. Ouvrir le port : quand omega-fire et cette instance sont "
                     "inscrits dans la zone omega-connect, omega-fire ouvre le port pour vos réseaux permis (boucle "
                     "locale exclue), dans son pare-feu et dans ufw ou firewalld s'ils sont actifs ; sudo est demandé "
                     "par-dessus la TUI ; une fois fait, la ligne passe à ✓ tant que le port et les réseaux ne "
                     "changent pas."),
            reaction=_("Sans omega-fire inscrit dans la zone omega-connect avec cette instance, le pare-feu est "
                       "seulement signalé : ouvrez-y le port pour vos réseaux permis avec l'outil du pare-feu."),
        ),
        FieldGuide(
            label=_("Adresse d'écoute"),
            definition=_("Adresse IP sur laquelle l'administration web écoute."),
            utilisation=_("127.0.0.1 (défaut) : depuis cette machine seulement. Adresse Tailscale ou du réseau local "
                          "pour un autre appareil ; 0.0.0.0 : toutes les adresses. Hors de 127.0.0.1, TLS est "
                          "obligatoire : avec « Aucun », Enregistrer choisit tout seul « Certificat dédié »."),
            action=_("Prise en compte au rechargement (Enregistrer le propose)."),
            reaction=_("Une adresse invalide est refusée sans rien écrire."),
        ),
        FieldGuide(
            label=_("Port"),
            definition=_("Port de l'administration web (9643 par défaut)."),
            utilisation=_("Toujours différent du port du site ; un port déjà pris par une autre instance du registre "
                          "est signalé. 8443 était le défaut avant la 3.0.0 : d'autres outils l'utilisent souvent."),
            action=_("Prise en compte au rechargement. Enregistrer essaie d'abord d'écouter : un port déjà pris par "
                     "un autre programme, ou une adresse absente de cette machine, est refusé sans rien écrire."),
            reaction=_("Port pris au démarrage : le site démarre, l'administration reste arrêtée et le dit dans "
                       "error.log et dans le cadre État."),
        ),
        FieldGuide(
            label=_("Chiffrement (TLS)"),
            definition=_("Aucun (cette machine seulement), certificat du site (écran TLS), ou certificat dédié (chemins "
                         "à indiquer)."),
            utilisation=_("Un certificat auto-signé suffit : le navigateur demande de l'accepter la première fois."),
            action=_("Prise en compte au rechargement."),
            reaction=_("Certificat absent ou illisible : signalé dans Vérifier la configuration ; le site démarre, "
                       "l'administration reste arrêtée jusqu'au rechargement suivant."),
        ),
        FieldGuide(
            label=_("Réseaux permis"),
            definition=_("Adresses autorisées à joindre l'administration web, séparées par des virgules."),
            utilisation=_("Par défaut : cette machine, Tailscale et le réseau local. Une adresse hors liste est refusée "
                          "(403) avant même la page de connexion."),
            action=_("Prise en compte au rechargement."),
            reaction=_("La connexion par compte reste toujours exigée, même depuis un réseau permis."),
        ),
        FieldGuide(
            label=_("Historique"),
            definition=_("Graphes de la machine et de cette instance, de 1 heure à 30 jours, dans la vue Historique "
                         "du tableau de bord.")
            + " " + _("Mémoire, swap, disque (espace), processeur et mémoire d'omega-serv, batterie : courbe remplie et, en haut à "
                      "droite, la dernière mesure en taille utilisée sur le total, puis en pourcentage (cœurs pour le processeur "
                      "d'omega-serv ; sur secteur ou temps restant pour la batterie)."),
            utilisation=_("Activé par défaut. Désactivé : plus de relevé, plus de vue Historique."),
            action=_("Un relevé toutes les 10 secondes par le processus d'administration, gardé dans "
                     "var/run/admin/history.json (écrit toutes les 5 minutes et à l'arrêt, relu au démarrage)."),
            reaction=_("Processeur et mémoire : toute la machine. Requêtes : lignes ajoutées au journal d'accès de "
                       "cette instance, comptées sans être relues."),
        ),
        FieldGuide(
            label=_("Thème du panneau web"),
            definition=_("Couleurs du panneau web, parmi les 10 thèmes omega de la TUI. « Comme la TUI » (par défaut) "
                         "suit le thème de cette instance (touche t)."),
            utilisation=_("Chaque navigateur peut choisir un autre thème dans la liste de la barre du haut du "
                          "panneau ; ce choix reste dans ce navigateur (cookie), jamais sur le serveur. « Thème de "
                          "l'instance » l'efface."),
            action=_("Enregistrer, puis Recharger ; « Comme la TUI » suit la touche t dès la page suivante."),
            reaction=_("Les couleurs trop pâles pour être lues sur le web sont foncées ou éclaircies tout seules ; "
                       "omega-base garde la charte du site."),
        ),
        FieldGuide(
            label=_("Adresses IP dans la vue Trafic"),
            definition=_("Entières, ou masquées : dernier nombre à 0 en IPv4, 48 premiers bits seulement en IPv6."),
            utilisation=_("Masquées si le panneau est consulté par d'autres personnes que l'administrateur du site."),
            action=_("Enregistrer, puis Recharger."),
            reaction=_("Seul l'affichage change : le journal d'accès garde les adresses entières."),
        ),
        FieldGuide(
            label=_("Alertes"),
            definition=_("Ouvre l'écran des alertes locales : seuils, maintenance, alertes en cours."),
            utilisation=_("Aucune saisie ici."),
            action=_("Ouvre l'écran."),
            reaction=_("Aucun effet par lui-même."),
        ),
    ),
    consequences=_("Enregistrer valide d'abord : un réglage refusé n'écrit rien et la saisie reste dans le formulaire. "
                   "Un problème de l'administration web n'empêche jamais le site de démarrer."),
    points_de_vigilance=(
        _("Activer ou désactiver l'option demande un redémarrage complet ; changer un réglage demande seulement un "
          "rechargement."),
        _("Jamais depuis le web : modifier la configuration, les profils, les zones ou les comptes, redémarrer ou "
          "arrêter le serveur. Ces gestes restent réservés au TUI et à la CLI."),
    ),
)

ADMIN_ACCOUNTS_SCREEN = ScreenGuide(
    screen_class_name="AdminAccountsScreen",
    title=_("Administration web - comptes"),
    acces=_("Accueil -> Instances -> Configuration distante -> Comptes"),
    definition=(
        _("Comptes qui peuvent se connecter à l'administration web. Ils se créent et se modifient seulement ici ou par "
          "la CLI (omega-serv admin-web account), jamais depuis le navigateur. Rôle lecture : Tableau de bord "
          "seulement ; rôle administration : Tableau de bord et Administration.")
        + " " + _("Sur la page de connexion, « Administration » ne sert qu'aux comptes administration : un compte "
                  "lecture arrive sur le Tableau de bord, avec un message qui le dit (une seule fois).")
        + " " + _("Le rôle se choisit dans un menu déroulant : lecture ou administration.")
    ),
    fields=(
        FieldGuide(
            label=_("Ajouter un compte"),
            definition=_("Identifiant, mot de passe (12 caractères au moins, saisi deux fois) et rôle."),
            utilisation=_("Identifiant : lettres, chiffres, point, tiret, soulignement (32 au plus)."),
            action=_("Le mot de passe est enregistré haché (scrypt), jamais en clair."),
            reaction=_("Une saisie refusée reste dans le formulaire avec la raison."),
        ),
        FieldGuide(
            label=_("Activer TOTP"),
            definition=_("Deuxième facteur : un code à 6 chiffres qui change toutes les 30 secondes dans une "
                         "application du téléphone (Aegis, FreeOTP, 2FAS, Google Authenticator...)."),
            utilisation=_("Scanner le QR code depuis un autre appareil, ou, sans scan, saisir le secret affiché ou "
                          "ouvrir le lien sur le téléphone ; puis taper le code affiché par l'application."),
            action=_("Le secret n'est enregistré que si le code est juste ; 10 codes de secours s'affichent alors une "
                     "seule fois, à noter."),
            reaction=_("Obligatoire pour un compte administration dès que l'administration web sort de cette machine."),
        ),
        FieldGuide(
            label=_("Nouveaux codes de secours"),
            definition=_("La colonne « Codes de secours » montre combien il en reste (par exemple 7 sur 10) ; un message "
                         "prévient quand il en reste 2 ou moins."),
            utilisation=_("Sélectionner un compte dont TOTP est activé, puis confirmer."),
            action=_("Génère 10 nouveaux codes, affichés une seule fois ; les anciens ne marchent plus."),
            reaction=_("Le TOTP du téléphone ne change pas et les sessions ouvertes restent ouvertes."),
        ),
        FieldGuide(
            label=_("Mot de passe, Rôle, Désactiver TOTP, Supprimer"),
            definition=_("Modifient le compte choisi dans le tableau."),
            utilisation=_("Sélectionner une ligne d'abord."),
            action=_("Effet immédiat, sans rechargement."),
            reaction=_("Les sessions web ouvertes du compte sont fermées."),
        ),
    ),
    consequences=_("Téléphone perdu : un code de secours remplace le code une fois ; sans code de secours, désactivez "
                   "TOTP ici puis réactivez-le."),
    points_de_vigilance=(
        _("L'heure du serveur et du téléphone doit être juste (moins de 30 secondes d'écart) : sinon les codes sont "
          "refusés."),
    ),
)

BACKUP_CODES_SCREEN = ScreenGuide(
    screen_class_name="BackupCodesScreen",
    title=_("Codes de secours"),
    acces=_("Accueil -> Instances -> Configuration distante -> Comptes -> Nouveaux codes de secours"),
    definition=_("Les 10 nouveaux codes de secours du compte, au format XXXX-XXXX, affichés une seule fois : "
                 "omega-serv n'en garde que l'empreinte et ne peut pas les réafficher."),
    consequences=_("Chaque code remplace une fois le code TOTP à la connexion (téléphone perdu ou indisponible), puis ne "
                   "marche plus. Ils n'expirent pas avec le temps."),
    points_de_vigilance=(
        _("Les noter ailleurs que sur le téléphone de l'application TOTP : papier, ou gestionnaire de mots de passe sur "
          "un autre appareil."),
    ),
)

TOTP_ENROL_SCREEN = ScreenGuide(
    screen_class_name="TotpEnrolScreen",
    title=_("Activer TOTP"),
    acces=_("Accueil -> Instances -> Configuration distante -> Comptes -> Activer TOTP"),
    definition=_("Associe une application d'authentification du téléphone au compte choisi."),
    fields=(
        FieldGuide(
            label=_("QR code, secret et lien"),
            definition=_("Trois façons de transmettre le même secret à l'application."),
            utilisation=_("QR code : à scanner depuis un autre appareil. Si ce terminal est sur le téléphone lui-même, "
                          "saisir le secret (groupes de 4 lettres et chiffres) ou ouvrir le lien otpauth."),
            action=_("Rien n'est enregistré à ce stade."),
            reaction=_("Quitter l'écran sans valider laisse le compte tel qu'il était."),
        ),
        FieldGuide(
            label=_("Copier le secret / Copier le lien"),
            definition=_("Met le secret ou le lien otpauth dans le presse-papiers, pour le coller dans l'application "
                         "sans le recopier à la main."),
            utilisation=_("Secret : à coller dans la saisie manuelle de l'application (type « basé sur le temps »). "
                          "Lien : à ouvrir sur l'appareil qui a l'application."),
            action=_("Presse-papiers de cette machine (wl-copy, xclip ou xsel) et, en plus, celui du terminal : utile "
                     "par SSH, selon le terminal."),
            reaction=_("Un message dit où le texte a été copié ; le presse-papiers garde le secret jusqu'à la "
                       "prochaine copie."),
        ),
        FieldGuide(
            label=_("Valider le code"),
            definition=_("Le code à 6 chiffres affiché maintenant par l'application."),
            utilisation=_("Le taper puis Valider le code."),
            action=_("Code juste : TOTP activé, codes de secours affichés une seule fois."),
            reaction=_("Code faux : rien n'est enregistré ; vérifier l'heure du téléphone et réessayer."),
        ),
    ),
)

RESOURCE_STATUS_SCREEN = ScreenGuide(
    screen_class_name="ResourceStatusScreen",
    title=_("État & Ressources"),
    acces=_("Accueil -> État & Ressources"),
    definition=(
        _("Tableau de bord en trois cadres, rafraîchi automatiquement toutes les 2 secondes : "
        "état du serveur/service, flux du log d'accès en direct, ressources système.")
        + " "
        + _("Le type d'instance s'affiche en tête du premier cadre, lu dans la configuration : site (statique, "
        "listing, envoi de fichiers), application PHP (FastCGI actif), reverse proxy (une zone de reverse proxy "
        "sur « / » : tout part aux backends) ou mixte (des zones de reverse proxy à côté d'un site servi en local).")
        + " "
        + _("Pour un reverse proxy ou une instance mixte, le cadre FLUX gagne une section BACKENDS, avant les "
        "chemins les plus demandés : pour chaque backend de chaque zone, son état, ses requêtes, celles en cours, "
        "ses erreurs 502 (connexion impossible ou réponse invalide) et 504 (délai de lecture dépassé) et son temps "
        "de réponse moyen. Ce sont des mesures en direct depuis le démarrage du serveur, lues dans le serveur en "
        "marche : rien n'est gardé d'un démarrage à l'autre. Un nom DNS résolu en plusieurs adresses par le moteur "
        "natif donne une ligne par adresse.")
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
        _("La section BACKENDS interroge le serveur par sa route d'administration, comme « État en direct » de "
        "l'écran Reverse proxy : trusted_proxy doit être actif avec 127.0.0.1 dans ses réseaux de confiance, "
        "sinon la section indique que l'administration est refusée."),
        _("Le temps moyen est une moyenne glissante, celle qu'utilise la stratégie least_response_time : une "
        "tentative en échec y compte pour le délai de lecture de la zone. Une zone servie par Python avec "
        "plusieurs processus n'est comptée que dans le processus qui répond à l'administration."),
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
        + " "
        + _("Un dossier de zone active absent du disque est signalé : cible d'un alias ou dossier d'un listing en "
        "avertissement (la zone répond 404 tant qu'il manque), dossier des scripts d'une zone FastCGI active en "
        "erreur (le serveur ne démarre pas). Au démarrage, un alias ou un listing absent laisse aussi une ligne "
        "dans error.log.")
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

ADMIN_MASTER_SCREEN = ScreenGuide(
    screen_class_name="AdminMasterScreen",
    title=_("Administration web - maître"),
    acces=_("Accueil -> Instances -> Configuration distante -> Maître"),
    definition=(
        _("Le maître accepté par cette instance : une autre instance omega-serv qui la suit depuis la page Instances de "
          "son tableau de bord web, et la pilote si vous lui donnez le droit d'administration. Un seul maître à la "
          "fois ; en accepter un autre remplace l'ancien, révoqué aussitôt. Si le maître s'arrête, cette instance "
          "continue sans rien changer.")
    ),
    fields=(
        FieldGuide(
            label=_("Droits donnés au maître"),
            definition=_("Lecture : le maître voit l'état, le flux, les ressources et la sécurité. Administration : il "
                         "peut aussi lancer les actions du mode Administration (bans, incidents, RIPOSTE, backends, "
                         "archives, rechargement)."),
            utilisation=_("Choisir avant d'ouvrir la fenêtre d'appairage."),
            action=_("Les droits sont fixés ici, jamais par le maître."),
            reaction=_("Une action demandée par un maître en lecture est refusée et écrite dans le journal d'audit."),
        ),
        FieldGuide(
            label=_("Accepter un maître (code)"),
            definition=_("Ouvre une fenêtre d'appairage de 10 minutes et affiche un code comme K7QF-3M9X."),
            utilisation=_("Sur le maître : page Instances -> « Ajouter à la main » -> adresse IP de cette instance, port "
                          "de son administration web, et le code."),
            action=_("Le code sert une seule fois ; 3 essais faux ferment la fenêtre. Le maître retient l'empreinte "
                     "du certificat de cette instance : un certificat changé ensuite est refusé et signalé."),
            reaction=_("Si un maître est déjà accepté, une confirmation est demandée : il sera remplacé à la fin de "
                       "l'appairage."),
        ),
        FieldGuide(
            label=_("Révoquer"),
            definition=_("Retire le maître accepté."),
            utilisation=_("Confirmer."),
            action=_("Ses appels sont refusés dès maintenant (ligne dans le journal d'audit)."),
            reaction=_("Le maître affiche « jeton refusé » pour cette instance."),
        ),
    ),
    consequences=_("Maître sur cette machine, rien à recopier : écran Instances -> « Relier au maître » (il lance "
                   "admin-web master accept sur cette instance, puis admin-web instances add sur le maître)."),
    points_de_vigilance=(
        _("L'adresse du maître doit être dans les réseaux permis de cette instance (Configuration distante), sinon "
          "ses appels reçoivent 403."),
        _("Hors de cette machine, l'administration web est toujours en HTTPS : c'est ce qui protège le jeton du "
          "maître."),
    ),
)


ADMIN_ALERTS_SCREEN = ScreenGuide(
    screen_class_name="AdminAlertsScreen",
    title=_("Administration web - alertes"),
    acces=_("Accueil -> Instances -> Configuration distante -> Alertes"),
    definition=_("Alertes locales : rien n'est envoyé hors de cette machine. Le processus d'administration surveille "
                 "le disque, la mémoire, le swap, le processeur, la température, la batterie, le taux d'erreurs 5xx "
                 "du site, les backends, les incidents Active Defense et les certificats. Une alerte s'ouvre quand le "
                 "seuil est dépassé pendant un moment, et se ferme quand la mesure redescend nettement."),
    fields=(
        FieldGuide(
            label=_("Seuils"),
            definition=_("Un seuil par règle ; vide = règle coupée."),
            utilisation=_("Nombre dans les bornes indiquées. Disque 90 %, mémoire 90 %, swap 80 %, processeur 95 %, "
                          "température 85 °C, batterie 15 %, erreurs 5xx 5 % (sur 5 minutes, à partir de 50 "
                          "requêtes), certificat 30 jours (puis 14, 7 et 1)."),
            action=_("Enregistrer, puis Recharger : le processus d'administration prend les nouveaux seuils."),
            reaction=_("Une alerte ouverte d'une règle coupée se ferme."),
        ),
        FieldGuide(
            label=_("Maintenance 1 h / 24 h, Fin de maintenance"),
            definition=_("Pendant une maintenance, aucune nouvelle alerte ne s'ouvre ; celles déjà ouvertes se "
                         "ferment normalement."),
            utilisation=_("Avant un redémarrage, une mise à jour, un gros transfert."),
            action=_("Effet immédiat (fichier var/lib/admin/alertes-maintenance.json)."),
            reaction=_("Le panneau web l'indique en haut de la vue Alertes."),
        ),
    ),
    consequences=_("Les alertes s'affichent dans le panneau web (vue Alertes, avec leur nombre dans la barre des vues) "
                   "et dans var/log/alertes.log ; 30 jours d'historique dans var/lib/admin/alertes.json."),
    points_de_vigilance=(
        _("Il faut l'administration web active (en boucle locale suffit, rien n'est ouvert au réseau). Disque, "
          "mémoire, swap, processeur, température, batterie et erreurs 5xx demandent aussi l'Historique."),
        _("Un service arrêté ne peut rien signaler lui-même : les alertes s'arrêtent avec lui."),
    ),
)

ADMIN_SESSIONS_SCREEN = ScreenGuide(
    screen_class_name="AdminSessionsScreen",
    title=_("Administration web - sessions ouvertes"),
    acces=_("Accueil -> Instances -> Configuration distante -> Comptes -> Sessions"),
    definition=_("Navigateurs connectés au panneau web : compte, adresse, ouverture et dernière activité. Liste "
                 "publiée toutes les 5 secondes par le processus d'administration, sans jamais le jeton de session."),
    fields=(
        FieldGuide(
            label=_("Fermer la session"),
            definition=_("Déconnecte le navigateur choisi."),
            utilisation=_("Choisir une session dans la liste."),
            action=_("Dépose une demande que le processus d'administration applique dans les 5 secondes."),
            reaction=_("Ligne « session fermee par TUI » dans le journal d'audit ; le navigateur revient à la page "
                       "de connexion."),
        ),
    ),
    consequences=_("Aussi dans le panneau web (vue Sessions) : un compte administration y voit et ferme toutes les "
                   "sessions, un compte lecture les siennes."),
    points_de_vigilance=(
        _("Une session vit 30 minutes sans activité et 8 heures au plus ; un redémarrage du service les ferme toutes."),
    ),
)

