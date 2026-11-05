"""Fiches guide : RIPOSTE - 6 ecrans + formulaire de politique (OMEGA-SERV_PLAN-DETAILLE_RIPOSTE.md §9.1,
lot 7). Chaque fiche cite les commandes CLI equivalentes (memes regles metier : application/riposte/console.py)."""
from __future__ import annotations

from omega_serv.core.i18n import _
from omega_serv.interfaces.tui.guide.model import FieldGuide, ScreenGuide

RIPOSTE_STATUS_SCREEN = ScreenGuide(
    screen_class_name="RiposteStatusScreen",
    title=_("RIPOSTE - État"),
    acces=_("Accueil -> Active Sécurité -> État (bloc RIPOSTE)"),
    definition=(
        _("RIPOSTE agit DANS LA DURÉE : il se souvient des sources qui reviennent et leur applique des bans de plus "
          "en plus longs (paliers), alors qu'Active Defense agit PENDANT la requête selon le niveau de menace du "
          "moment. Cet écran montre le module (activé ou non, politiques actives), le processus RIPOSTE (actif, PID, "
          "dernier signe de vie, lignes lues), les actions en cours et l'arrêt d'urgence.")
    ),
    fields=(
        FieldGuide(
            label=_("Arrêt d'urgence"),
            definition=_("Coupe toute nouvelle action RIPOSTE, pour toutes les règles, même après un redémarrage."),
            utilisation=(
                _("Choisir « Arrêter et lever les actions en cours » (bans retirés de la blocklist, leurres libérés tout "
                  "de suite) ou « Arrêter seulement » (les actions vont jusqu'à leur échéance).")
            ),
            action=_("Effet immédiat, même si le processus RIPOSTE est arrêté (drapeau mémorisé dans sa base)."),
            reaction=_("Le bouton devient « Reprendre » ; « Reprendre » relance les règles qui étaient actives."),
        ),
    ),
    consequences=(
        _("L'arrêt ne touche jamais les bans automatiques du WAF, le mode guerre d'Active Defense, ni les bans réseau "
          "déjà passés à fail2ban (à lever dans omega-jail ou fail2ban).")
    ),
    points_de_vigilance=(
        _("Le module s'active dans le menu Options et demande un redémarrage complet du service."),
        _("Sans WAF actif, RIPOSTE ne voit aucune attaque : l'écran l'indique."),
        _("Ban réseau : l'écran dit si les jails RIPOSTE de cette instance sont installées par omega-jail, et signale "
          "la jail omega-serv-active-defense (ban fixe de 24 h) qui écrase les paliers réseau."),
        _("En ligne de commande : « riposte status », « riposte stop [--revoke] », « riposte resume »."),
    ),
)

RIPOSTE_POLICIES_SCREEN = ScreenGuide(
    screen_class_name="RipostePoliciesScreen",
    title=_("RIPOSTE - Politiques"),
    acces=_("Accueil -> Active Sécurité -> Politiques (bloc RIPOSTE)"),
    definition=(
        _("Une politique dit QUAND agir (classes d'attaque, nombre de retours dans une fenêtre, niveau Active Defense, "
          "visites de leurre) et COMMENT (ban local, ban local + réseau, leurre). Une politique active agit "
          "automatiquement, sans validation action par action.")
    ),
    fields=(
        FieldGuide(
            label=_("Ajouter"),
            definition=_("Trois points de départ : un scénario prêt à charger, la copie d'une politique, ou Custom."),
            utilisation=_("Le formulaire s'ouvre pré-rempli ; tout reste modifiable avant l'enregistrement."),
            action=_("Rien n'est écrit avant « Enregistrer » dans le formulaire."),
            reaction=_("La politique apparaît dans le tableau, active ou non selon le choix fait à l'enregistrement."),
        ),
        FieldGuide(
            label=_("Activer / Désactiver"),
            definition=_("Arrêt d'une seule règle (les autres continuent)."),
            utilisation=(
                _("Désactiver propose de lever ses actions en cours ou de les laisser aller à leur échéance. Activer "
                  "mesure d'abord la règle et montre l'effet avant de confirmer.")
            ),
            action=_("Écrit la configuration puis demande au processus RIPOSTE de la relire."),
            reaction=_("La règle reste listée, avec ses réglages, même désactivée."),
        ),
        FieldGuide(
            label=_("Retirer"),
            definition=_("Supprime la politique de la configuration."),
            utilisation=_("Confirmation demandée."),
            action=_("Ses actions passées restent dans l'historique sous son nom."),
            reaction=_("Ses actions en cours vont jusqu'à leur échéance (les lever dans Actions)."),
        ),
    ),
    consequences=_("Une modification est prise en compte par le processus RIPOSTE en moins d'une seconde."),
    points_de_vigilance=(
        _("Le détail d'une politique « ban local + réseau » indique quelle jail reçoit chaque palier."),
        _("En ligne de commande : « riposte policies list|show|enable|disable [--revoke] », « riposte scenarios »."),
        _("Les scénarios « Explorateur de leurres » et « Sonde upload / API » exigent le profil de leurre fake_admin ou "
          "fake_api dans Active Defense -> Réglages (option active_defense activée) ; sinon ils sont refusés "
          "(« profil de leurre inconnu »). Marche à suivre : FAQ, rubrique RIPOSTE."),
    ),
)

RIPOSTE_POLICY_FORM_SCREEN = ScreenGuide(
    screen_class_name="RipostePolicyFormScreen",
    title=_("RIPOSTE - Formulaire de politique"),
    acces=_("Accueil -> Active Sécurité -> Politiques -> Ajouter ou Modifier"),
    definition=_("Chaque champ montre sa valeur réelle, un exemple en grisé quand il est vide, et une ligne d'explication."),
    fields=(
        FieldGuide(
            label=_("Déclencheur"),
            definition=_("Classes d'attaque (vide = toutes), nombre d'épisodes (retours) dans une fenêtre, niveau Active Defense minimal, visites de leurre."),
            utilisation=_("Un retour = un nouvel épisode d'attaque après un silence (réglable dans Réglages)."),
            action=_("Vérifié à l'enregistrement : rien n'est écrit si un champ est refusé."),
            reaction=_("Le message d'erreur nomme le champ fautif."),
        ),
        FieldGuide(
            label=_("Réponse"),
            definition=_("Ban local (blocklist du WAF), ban local + ban réseau (jails omega-jail), ou leurre Active Defense."),
            utilisation=_("Paliers : vide = paliers globaux ; durées en s, m, h ou d (ex. 1h, 6h, 1d, 7d)."),
            action=_("Au-delà de 7 jours ou dès le niveau « suspicious » : confirmation « moins prudent que la norme »."),
            reaction=_("Le choix confirmé est mémorisé dans la politique."),
        ),
        FieldGuide(
            label=_("Mesurer"),
            definition=_("Rejoue la politique sur les journaux des 7 derniers jours, sans rien appliquer."),
            utilisation=_("Sur bouton seulement ; le résultat dit la période réellement couverte par les journaux."),
            action=_("Calcul hors de l'interface (elle reste utilisable)."),
            reaction=_("Le résultat est repris dans la confirmation finale."),
        ),
        FieldGuide(
            label=_("Enregistrer"),
            definition=_("Confirmation finale : Activer, Enregistrer sans activer, ou Annuler."),
            utilisation=_("« Enregistrer sans activer » permet d'observer d'abord (Mesurer, Simuler)."),
            action=_("Écrit la configuration puis demande au processus RIPOSTE de la relire."),
            reaction=_("Retour à l'écran Politiques."),
        ),
    ),
    consequences=_("Une politique activée agit automatiquement dès le prochain événement correspondant."),
    points_de_vigilance=(
        _("Ban réseau : les jails ont des durées fixes (1 h, 6 h, 24 h, 7 j) ; chaque palier va à la plus longue qui "
          "ne le dépasse pas (un palier de 2 h va à la jail de 1 h). La confirmation l'affiche."),
        _("En ligne de commande : « riposte measure <id>|scenario:<id> [--days N] »."),
    ),
)

RIPOSTE_ACTIONS_SCREEN = ScreenGuide(
    screen_class_name="RiposteActionsScreen",
    title=_("RIPOSTE - Actions"),
    acces=_("Accueil -> Active Sécurité -> Actions (bloc RIPOSTE)"),
    definition=(
        _("Le registre des actions : en cours, ou terminées (échéance, levée par l'utilisateur, règle désactivée, "
          "arrêt d'urgence, retirée hors RIPOSTE, non appliquée). Rien ne disparaît.")
    ),
    fields=(
        FieldGuide(
            label=_("Lever"),
            definition=_("Retire ce ban de la blocklist ou libère ce leurre, tout de suite."),
            utilisation=(
                _("« Lever et exempter cette source » évite qu'elle soit bannie de nouveau (24 h, 7 j ou toujours) ; la "
                  "case « ne pas compter ce ban dans la récidive » corrige un faux positif.")
            ),
            action=_("Exécuté par le processus RIPOSTE en moins d'une seconde ; s'il est arrêté, à son prochain démarrage."),
            reaction=_("L'action passe dans « terminées »."),
        ),
        FieldGuide(
            label=_("Ne compte pas dans la récidive"),
            definition=_("L'action reste dans l'historique mais ne fait plus monter le palier suivant."),
            utilisation=_("Pour un faux positif découvert après coup."),
            action=_("Exécuté par le processus RIPOSTE."),
            reaction=_("Le détail de l'action l'indique."),
        ),
    ),
    consequences=_("Une levée ne retire que le ban local : un ban réseau reste dans fail2ban jusqu'à son terme."),
    points_de_vigilance=(
        _("Une action retirée à la main de la blocklist est vue par RIPOSTE (vérification toutes les 60 s)."),
        _("En ligne de commande : « riposte actions list [--finished]|show|revoke [--exempt 24h|7d|forever] "
          "[--not-recidive]|not-recidive », « riposte exemptions list|remove »."),
    ),
)

RIPOSTE_RECIDIVES_SCREEN = ScreenGuide(
    screen_class_name="RiposteRecidivesScreen",
    title=_("RIPOSTE - Récidives"),
    acces=_("Accueil -> Active Sécurité -> Récidives (bloc RIPOSTE)"),
    definition=_("Les sources suivies : épisodes, actions, palier suivant, chronologie (épisodes, classes d'attaque, actions)."),
    fields=(
        FieldGuide(
            label=_("Oublier cette source"),
            definition=_("Efface la mémoire de RIPOSTE sur cette adresse (données personnelles)."),
            utilisation=_("Refusé tant qu'une action est en cours contre elle : la lever d'abord."),
            action=_("Exécuté par le processus RIPOSTE."),
            reaction=_("Son prochain retour est traité comme une première fois."),
        ),
    ),
    consequences=_("Sans action, l'historique est effacé de lui-même après la durée de conservation (Réglages)."),
    points_de_vigilance=(_("En ligne de commande : « riposte sources list|show|forget », « riposte decisions list »."),),
)

RIPOSTE_SIMULATE_SCREEN = ScreenGuide(
    screen_class_name="RiposteSimulateScreen",
    title=_("RIPOSTE - Simuler"),
    acces=_("Accueil -> Active Sécurité -> Simuler (bloc RIPOSTE)"),
    definition=(
        _("Décision expliquée pour une situation saisie, avec la configuration réelle : politique retenue, exclusions "
          "vérifiées, action, durée, ou raison du refus. Rien n'est appliqué ni écrit.")
    ),
    fields=(
        FieldGuide(
            label=_("Décisions récentes"),
            definition=_("Les dernières décisions du processus RIPOSTE."),
            utilisation=_("Sélectionner une ligne pour lire son explication."),
            action=_("Lecture seule."),
            reaction=_("L'explication s'affiche sous le tableau."),
        ),
    ),
    consequences=_("Aucune - purement consultatif."),
    points_de_vigilance=(_("En ligne de commande : « riposte simulate --ip IP [--class C] [--level L] [--returns N] »."),),
)

RIPOSTE_SETTINGS_SCREEN = ScreenGuide(
    screen_class_name="RiposteSettingsScreen",
    title=_("RIPOSTE - Réglages"),
    acces=_("Accueil -> Active Sécurité -> Réglages (bloc RIPOSTE)"),
    definition=(
        _("Paliers de durée (défaut 1 h, 6 h, 24 h, 7 j), fenêtre de récidive (30 j), silence entre deux épisodes "
          "(1 h), conservation de l'historique (90 j), plafond de bans simultanés (100), exemptions.")
    ),
    fields=(
        FieldGuide(
            label=_("Exemptions"),
            definition=_("Réseaux contre lesquels RIPOSTE n'agit jamais, en plus des exclusions du WAF (lecture seule ici)."),
            utilisation=_("Celles ajoutées par « Lever et exempter » sont listées à part et retirables."),
            action=_("Vérifié avant toute écriture."),
            reaction=_("Le processus RIPOSTE relit la configuration."),
        ),
    ),
    consequences=_("Les nouveaux réglages s'appliquent aux décisions suivantes, jamais aux actions déjà en cours."),
    points_de_vigilance=(
        _("Au-delà de 7 jours, les paliers globaux sont refusés ; seule une politique peut le demander, avec confirmation."),
        _("Le module lui-même s'active dans Options (redémarrage complet), jamais par un profil."),
    ),
)

ALL_RIPOSTE_GUIDES: tuple[ScreenGuide, ...] = (
    RIPOSTE_STATUS_SCREEN,
    RIPOSTE_POLICIES_SCREEN,
    RIPOSTE_POLICY_FORM_SCREEN,
    RIPOSTE_ACTIONS_SCREEN,
    RIPOSTE_RECIDIVES_SCREEN,
    RIPOSTE_SIMULATE_SCREEN,
    RIPOSTE_SETTINGS_SCREEN,
)
