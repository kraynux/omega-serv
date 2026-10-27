"""Fiches guide : Assistant premier lancement, 8 etapes (plan guide
d'aide, Phase 1)."""
from __future__ import annotations

from omega_serv.core.i18n import _
from omega_serv.interfaces.tui.guide.model import FieldGuide, ScreenGuide

WIZARD_WELCOME_SCREEN = ScreenGuide(
    screen_class_name="WizardWelcomeScreen",
    title=_("Assistant premier lancement - 1/8 Bienvenue"),
    acces=_("Accueil -> Assistant premier lancement"),
    definition=(
        _("Point d'entrée de l'assistant guide qui compose une première configuration complète, "
        "étape par étape.")
    ),
    fields=(
        FieldGuide(
            label=_("Commencer"),
            definition=_("Démarre le parcours guide."),
            utilisation=_("Aucune saisie à cette étape."),
            action=_("Ouvre l'étape 2/8 (Registre des capacités)."),
            reaction=_("Aucun effet sur disque - rien n'est écrit avant l'étape 7 (Résumé)."),
        ),
    ),
    consequences=_("Aucune - purement informatif."),
)

WIZARD_CAPABILITIES_SCREEN = ScreenGuide(
    screen_class_name="WizardCapabilitiesScreen",
    title=_("Assistant premier lancement - 2/8 Capacités"),
    acces=_("Assistant premier lancement -> étape 2/8"),
    definition=(
        _("Scan en lecture seule de l'environnement (port par défaut déjà occupé, openssl "
        "présent...), avec le port par défaut - aucun profil ni port personnalisé n'est encore choisi.")
    ),
    fields=(
        FieldGuide(
            label=_("Suivant / Précédent"),
            definition=_("Navigation entre les étapes."),
            utilisation=_("Aucune saisie à cette étape (table en lecture seule)."),
            action=_("Suivant ouvre l'étape 3/8 (Profil)."),
            reaction=_("Aucun effet - purement informatif."),
        ),
    ),
    consequences=_("Aucune."),
)

WIZARD_PROFILE_SCREEN = ScreenGuide(
    screen_class_name="WizardProfileScreen",
    title=_("Assistant premier lancement - 3/8 Profil"),
    acces=_("Assistant premier lancement -> étape 3/8"),
    definition=_("Choix d'un profil de base parmi les quatre profils preconfigures."),
    fields=(
        FieldGuide(
            label=_("Table des profils"),
            definition=_("Liste des profils disponibles avec leur description au clic."),
            utilisation=_("4 profils : minimal, standard, hardened, development."),
            action=_("Sélectionner une ligne affiche sa description et active le bouton Suivant."),
            reaction=_("Le profil choisi est appliqué à la CONFIGURATION CANDIDATE EN MÉMOIRE uniquement."),
        ),
    ),
    consequences=_("Rien n'est encore écrit sur disque à cette étape."),
)

WIZARD_BASE_CONFIG_SCREEN = ScreenGuide(
    screen_class_name="WizardBaseConfigScreen",
    title=_("Assistant premier lancement - 4/8 Configuration de base"),
    acces=_("Assistant premier lancement -> étape 4/8"),
    definition=_("Ajuste uniquement l'adresse d'écoute et le port - le reste vient du profil choisi."),
    fields=(
        FieldGuide(
            label=_("Adresse d'écoute (server.bind)"),
            definition=_("Adresse IP sur laquelle le serveur écoutera."),
            utilisation=_("Une adresse IP valide. Pré-remplie avec la valeur du profil choisi."),
            action=_("Validée (structurellement) au clic sur Suivant."),
            reaction=_("En mémoire uniquement à ce stade - voir l'étape 7 pour l'écriture réelle."),
        ),
        FieldGuide(
            label=_("Port (server.port)"),
            definition=_("Port TCP d'écoute."),
            utilisation=_("Un entier de port valide. Pré-rempli avec la valeur du profil choisi."),
            action=_("Validé au clic sur Suivant."),
            reaction=_("En mémoire uniquement à ce stade."),
        ),
    ),
    consequences=_("Rien n'est encore écrit sur disque à cette étape."),
)

WIZARD_TLS_SCREEN = ScreenGuide(
    screen_class_name="WizardTlsScreen",
    title=_("Assistant premier lancement - 5/8 TLS"),
    acces=_("Assistant premier lancement -> étape 5/8"),
    definition=(
        _("Propose de générer un certificat auto-signé et d'activer TLS - jamais force, et jamais "
        "proposé du tout si le profil choisi est 'development'.")
    ),
    fields=(
        FieldGuide(
            label=_("Nom commun (CN)"),
            definition=_("Nom commun (Common Name) du certificat - généralement le nom d'hôte du serveur."),
            utilisation=_("Chaîne libre, ex: mon-serveur.local."),
            action=_("Utilisé au clic sur 'Générer et activer TLS'."),
            reaction=_("Génère réellement le certificat sur disque immédiatement (pas différé à l'étape 7)."),
        ),
        FieldGuide(
            label=_("SAN DNS"),
            definition=_("Noms DNS alternatifs couverts par le certificat (Subject Alternative Name)."),
            utilisation=_("Liste séparée par des virgules, optionnelle."),
            action=_("Utilisé au clic sur 'Générer et activer TLS'."),
            reaction=_("Génère réellement le certificat sur disque immédiatement."),
        ),
        FieldGuide(
            label=_("Type de clé"),
            definition=_("Algorithme et taille de la clé privée générée."),
            utilisation=_("Valeurs valides listées dans le sous-titre du champ. Valeur par défaut : rsa2048."),
            action=_("Utilisé au clic sur 'Générer et activer TLS'."),
            reaction=_("Génère réellement le certificat sur disque immédiatement."),
        ),
    ),
    consequences=(
        _("Générer un certificat ici écrit réellement des fichiers sur disque tout de suite "
        "(contrairement au reste de l'assistant) - active tls.enabled en mémoire pour la suite du "
        "parcours, écrit dans la configuration finale à l'étape 7.")
    ),
    points_de_vigilance=(
        _("Cette étape est entièrement absente pour le profil 'development' - remplacée par un simple message."),
    ),
)

WIZARD_CHECK_SCREEN = ScreenGuide(
    screen_class_name="WizardCheckScreen",
    title=_("Assistant premier lancement - 6/8 Vérification"),
    acces=_("Assistant premier lancement -> étape 6/8"),
    definition=(
        _("Vérification automatique (structurelle puis environnement réel) avant de pouvoir "
        "continuer - les mêmes deux couches que l'écran 'Vérifier la configuration'.")
    ),
    fields=(
        FieldGuide(
            label=_("Confirmer : bind public + certificat auto-signé"),
            definition=(
                _("Porte de confirmation explicite requise pour continuer si le serveur écoute "
                "publiquement avec un certificat auto-signé (jamais reconnu par les navigateurs).")
            ),
            utilisation=_("À cocher uniquement si cette combinaison est réellement voulue."),
            action=_("Pris en compte au prochain clic sur Vérifier."),
            reaction=_("Sans cette confirmation, le bouton Suivant reste désactivé si la situation s'applique."),
        ),
        FieldGuide(
            label=_("Confirmer : authentification sans TLS"),
            definition=(
                _("Porte de confirmation explicite requise pour continuer si l'authentification est "
                "active sans TLS (identifiants transmis en clair).")
            ),
            utilisation=_("À cocher uniquement si cette combinaison est réellement voulue."),
            action=_("Pris en compte au prochain clic sur Vérifier."),
            reaction=_("Sans cette confirmation, le bouton Suivant reste désactivé si la situation s'applique."),
        ),
    ),
    consequences=_("Rien n'est encore écrit sur disque à cette étape - seulement des vérifications."),
)

WIZARD_SUMMARY_SCREEN = ScreenGuide(
    screen_class_name="WizardSummaryScreen",
    title=_("Assistant premier lancement - 7/8 Résumé"),
    acces=_("Assistant premier lancement -> étape 7/8"),
    definition=(
        _("Affiche la différence complète entre les valeurs par défaut et la configuration composée "
        "par l'assistant, puis écrit réellement le fichier de configuration.")
    ),
    fields=(
        FieldGuide(
            label=_("Écrire la configuration"),
            definition=_("Confirme et écrit la configuration composée."),
            utilisation=_("À vérifier attentivement le résumé affiché avant de cliquer."),
            action=_("Écrit config/omega-serve.json (une sauvegarde de l'ancien fichier est faite automatiquement s'il existait)."),
            reaction=_("C'EST LA PREMIÈRE ÉCRITURE RÉELLE de tout le parcours - ouvre ensuite l'étape 8/8."),
        ),
    ),
    consequences=_("Écrase config/omega-serve.json (avec sauvegarde automatique du fichier précédent s'il existait)."),
)

WIZARD_SERVICE_SCREEN = ScreenGuide(
    screen_class_name="WizardServiceScreen",
    title=_("Assistant premier lancement - 8/8 Service"),
    acces=_("Assistant premier lancement -> étape 8/8"),
    definition=_("La configuration est écrite - propose de lancer le serveur, de l'installer comme service, ou de terminer."),
    fields=(
        FieldGuide(
            label=_("Lancer maintenant"),
            definition=_("Lance réellement le serveur au premier plan, tout de suite."),
            utilisation=_("Pour un test immédiat sans installer de service système."),
            action=_("Rend la main au terminal réel et bloque jusqu'à Ctrl+C (ou arrêt du service)."),
            reaction=_("Le serveur écoute réellement le temps de cette action - revient à l'accueil à l'arrêt."),
        ),
        FieldGuide(
            label=_("Installer le service"),
            definition=_("Ouvre l'écran SERVICE pour installer une unité systemd (démarrage automatique)."),
            utilisation=_("Pour un usage durable (le serveur redémarre avec la machine)."),
            action=_("Ouvre l'écran SERVICE."),
            reaction=_("Voir la fiche SERVICE - une authentification (sudo) sera demandée."),
        ),
        FieldGuide(
            label=_("Terminer"),
            definition=_("Quitte l'assistant sans rien lancer."),
            utilisation=_("À choisir si vous comptez lancer le serveur plus tard manuellement."),
            action=_("Revient à l'accueil."),
            reaction=_("Le serveur ne tourne pas - `omega-serv.sh serve` (CLI) reste à lancer manuellement."),
        ),
    ),
    consequences=_("La configuration est déjà écrite depuis l'étape précédente - cet écran ne fait que décider comment démarrer."),
)

ALL_WIZARD_GUIDES: tuple[ScreenGuide, ...] = (
    WIZARD_WELCOME_SCREEN,
    WIZARD_CAPABILITIES_SCREEN,
    WIZARD_PROFILE_SCREEN,
    WIZARD_BASE_CONFIG_SCREEN,
    WIZARD_TLS_SCREEN,
    WIZARD_CHECK_SCREEN,
    WIZARD_SUMMARY_SCREEN,
    WIZARD_SERVICE_SCREEN,
)
