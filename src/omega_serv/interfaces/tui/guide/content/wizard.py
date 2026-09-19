"""Fiches guide : Assistant premier lancement, 8 etapes (plan guide
d'aide, Phase 1)."""
from __future__ import annotations

from omega_serv.interfaces.tui.guide.model import FieldGuide, ScreenGuide

WIZARD_WELCOME_SCREEN = ScreenGuide(
    screen_class_name="WizardWelcomeScreen",
    title="Assistant premier lancement - 1/8 Bienvenue",
    acces="Accueil -> Assistant premier lancement",
    definition=(
        "Point d'entree de l'assistant guide qui compose une premiere configuration complete, "
        "etape par etape."
    ),
    fields=(
        FieldGuide(
            label="Commencer",
            definition="Demarre le parcours guide.",
            utilisation="Aucune saisie a cette etape.",
            action="Ouvre l'etape 2/8 (Registre des capacites).",
            reaction="Aucun effet sur disque - rien n'est ecrit avant l'etape 7 (Resume).",
        ),
    ),
    consequences="Aucune - purement informatif.",
)

WIZARD_CAPABILITIES_SCREEN = ScreenGuide(
    screen_class_name="WizardCapabilitiesScreen",
    title="Assistant premier lancement - 2/8 Capacites",
    acces="Assistant premier lancement -> etape 2/8",
    definition=(
        "Scan en lecture seule de l'environnement (port par defaut deja occupe, openssl "
        "present...), avec le port par defaut - aucun profil ni port personnalise n'est encore choisi."
    ),
    fields=(
        FieldGuide(
            label="Suivant / Precedent",
            definition="Navigation entre les etapes.",
            utilisation="Aucune saisie a cette etape (table en lecture seule).",
            action="Suivant ouvre l'etape 3/8 (Profil).",
            reaction="Aucun effet - purement informatif.",
        ),
    ),
    consequences="Aucune.",
)

WIZARD_PROFILE_SCREEN = ScreenGuide(
    screen_class_name="WizardProfileScreen",
    title="Assistant premier lancement - 3/8 Profil",
    acces="Assistant premier lancement -> etape 3/8",
    definition="Choix d'un profil de base parmi les quatre profils preconfigures.",
    fields=(
        FieldGuide(
            label="Table des profils",
            definition="Liste des profils disponibles avec leur description au clic.",
            utilisation="4 profils : minimal, standard, hardened, development.",
            action="Selectionner une ligne affiche sa description et active le bouton Suivant.",
            reaction="Le profil choisi est applique a la CONFIGURATION CANDIDATE EN MEMOIRE uniquement.",
        ),
    ),
    consequences="Rien n'est encore ecrit sur disque a cette etape.",
)

WIZARD_BASE_CONFIG_SCREEN = ScreenGuide(
    screen_class_name="WizardBaseConfigScreen",
    title="Assistant premier lancement - 4/8 Configuration de base",
    acces="Assistant premier lancement -> etape 4/8",
    definition="Ajuste uniquement l'adresse d'ecoute et le port - le reste vient du profil choisi.",
    fields=(
        FieldGuide(
            label="Adresse d'ecoute (server.bind)",
            definition="Adresse IP sur laquelle le serveur ecoutera.",
            utilisation="Une adresse IP valide. Pre-remplie avec la valeur du profil choisi.",
            action="Validee (structurellement) au clic sur Suivant.",
            reaction="En memoire uniquement a ce stade - voir l'etape 7 pour l'ecriture reelle.",
        ),
        FieldGuide(
            label="Port (server.port)",
            definition="Port TCP d'ecoute.",
            utilisation="Un entier de port valide. Pre-rempli avec la valeur du profil choisi.",
            action="Valide au clic sur Suivant.",
            reaction="En memoire uniquement a ce stade.",
        ),
    ),
    consequences="Rien n'est encore ecrit sur disque a cette etape.",
)

WIZARD_TLS_SCREEN = ScreenGuide(
    screen_class_name="WizardTlsScreen",
    title="Assistant premier lancement - 5/8 TLS",
    acces="Assistant premier lancement -> etape 5/8",
    definition=(
        "Propose de generer un certificat auto-signe et d'activer TLS - jamais force, et jamais "
        "propose du tout si le profil choisi est 'development'."
    ),
    fields=(
        FieldGuide(
            label="Nom commun (CN)",
            definition="Nom commun (Common Name) du certificat - generalement le nom d'hote du serveur.",
            utilisation="Chaine libre, ex: mon-serveur.local.",
            action="Utilise au clic sur 'Generer et activer TLS'.",
            reaction="Genere reellement le certificat sur disque immediatement (pas differe a l'etape 7).",
        ),
        FieldGuide(
            label="SAN DNS",
            definition="Noms DNS alternatifs couverts par le certificat (Subject Alternative Name).",
            utilisation="Liste separee par des virgules, optionnelle.",
            action="Utilise au clic sur 'Generer et activer TLS'.",
            reaction="Genere reellement le certificat sur disque immediatement.",
        ),
        FieldGuide(
            label="Type de cle",
            definition="Algorithme et taille de la cle privee generee.",
            utilisation="Valeurs valides listees dans le sous-titre du champ. Valeur par defaut : rsa2048.",
            action="Utilise au clic sur 'Generer et activer TLS'.",
            reaction="Genere reellement le certificat sur disque immediatement.",
        ),
    ),
    consequences=(
        "Generer un certificat ici ecrit reellement des fichiers sur disque tout de suite "
        "(contrairement au reste de l'assistant) - active tls.enabled en memoire pour la suite du "
        "parcours, ecrit dans la configuration finale a l'etape 7."
    ),
    points_de_vigilance=(
        "Cette etape est entierement absente pour le profil 'development' - remplacee par un simple message.",
    ),
)

WIZARD_CHECK_SCREEN = ScreenGuide(
    screen_class_name="WizardCheckScreen",
    title="Assistant premier lancement - 6/8 Verification",
    acces="Assistant premier lancement -> etape 6/8",
    definition=(
        "Verification automatique (structurelle puis environnement reel) avant de pouvoir "
        "continuer - les memes deux couches que l'ecran 'Verifier la configuration'."
    ),
    fields=(
        FieldGuide(
            label="Confirmer : bind public + certificat auto-signe",
            definition=(
                "Porte de confirmation explicite requise pour continuer si le serveur ecoute "
                "publiquement avec un certificat auto-signe (jamais reconnu par les navigateurs)."
            ),
            utilisation="A cocher uniquement si cette combinaison est reellement voulue.",
            action="Pris en compte au prochain clic sur Verifier.",
            reaction="Sans cette confirmation, le bouton Suivant reste desactive si la situation s'applique.",
        ),
        FieldGuide(
            label="Confirmer : authentification sans TLS",
            definition=(
                "Porte de confirmation explicite requise pour continuer si l'authentification est "
                "active sans TLS (identifiants transmis en clair)."
            ),
            utilisation="A cocher uniquement si cette combinaison est reellement voulue.",
            action="Pris en compte au prochain clic sur Verifier.",
            reaction="Sans cette confirmation, le bouton Suivant reste desactive si la situation s'applique.",
        ),
    ),
    consequences="Rien n'est encore ecrit sur disque a cette etape - seulement des verifications.",
)

WIZARD_SUMMARY_SCREEN = ScreenGuide(
    screen_class_name="WizardSummaryScreen",
    title="Assistant premier lancement - 7/8 Resume",
    acces="Assistant premier lancement -> etape 7/8",
    definition=(
        "Affiche la difference complete entre les valeurs par defaut et la configuration composee "
        "par l'assistant, puis ecrit reellement le fichier de configuration."
    ),
    fields=(
        FieldGuide(
            label="Ecrire la configuration",
            definition="Confirme et ecrit la configuration composee.",
            utilisation="A verifier attentivement le resume affiche avant de cliquer.",
            action="Ecrit config/omega-serve.json (une sauvegarde de l'ancien fichier est faite automatiquement s'il existait).",
            reaction="C'EST LA PREMIERE ECRITURE REELLE de tout le parcours - ouvre ensuite l'etape 8/8.",
        ),
    ),
    consequences="Ecrase config/omega-serve.json (avec sauvegarde automatique du fichier precedent s'il existait).",
)

WIZARD_SERVICE_SCREEN = ScreenGuide(
    screen_class_name="WizardServiceScreen",
    title="Assistant premier lancement - 8/8 Service",
    acces="Assistant premier lancement -> etape 8/8",
    definition="La configuration est ecrite - propose de lancer le serveur, de l'installer comme service, ou de terminer.",
    fields=(
        FieldGuide(
            label="Lancer maintenant",
            definition="Lance reellement le serveur au premier plan, tout de suite.",
            utilisation="Pour un test immediat sans installer de service systeme.",
            action="Rend la main au terminal reel et bloque jusqu'a Ctrl+C (ou arret du service).",
            reaction="Le serveur ecoute reellement le temps de cette action - revient a l'accueil a l'arret.",
        ),
        FieldGuide(
            label="Installer le service",
            definition="Ouvre l'ecran SERVICE pour installer une unite systemd (demarrage automatique).",
            utilisation="Pour un usage durable (le serveur redemarre avec la machine).",
            action="Ouvre l'ecran SERVICE.",
            reaction="Voir la fiche SERVICE - une authentification (sudo) sera demandee.",
        ),
        FieldGuide(
            label="Terminer",
            definition="Quitte l'assistant sans rien lancer.",
            utilisation="A choisir si vous comptez lancer le serveur plus tard manuellement.",
            action="Revient a l'accueil.",
            reaction="Le serveur ne tourne pas - `omega-serv.sh serve` (CLI) reste a lancer manuellement.",
        ),
    ),
    consequences="La configuration est deja ecrite depuis l'etape precedente - cet ecran ne fait que decider comment demarrer.",
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
