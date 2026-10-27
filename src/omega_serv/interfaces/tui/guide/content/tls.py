"""Fiches guide : TLS - menu + 7 sous-ecrans (plan guide d'aide, Phase 5 ;
LetsEncryptScreen/RenewalScheduleScreen ajoutes par
OMEGA-SERV_PLAN-DETAILLE_TLS_AUTO.md, Phase 6)."""
from __future__ import annotations

from omega_serv.core.i18n import _
from omega_serv.interfaces.tui.guide.model import FieldGuide, ScreenGuide

TLS_MENU_SCREEN = ScreenGuide(
    screen_class_name="TlsMenuScreen",
    title=_("TLS (menu)"),
    acces=_("Accueil -> Configuration détaillée -> TLS"),
    definition=_("Sous-menu regroupant les 5 écrans liés à TLS : statut, génération, CA locale, révocation, activation."),
    fields=(),
    consequences=_("Aucune - purement navigation."),
)

TLS_STATUS_SCREEN = ScreenGuide(
    screen_class_name="TlsStatusScreen",
    title=_("Statut TLS"),
    acces=_("Configuration détaillée -> TLS -> Statut TLS"),
    definition=_("Inspecte le certificat actuellement configuré : validité, expiration, correspondance avec la clé privée, permissions."),
    fields=(
        FieldGuide(
            label=_("Rafraîchir"),
            definition=_("Relit et reanalyse le certificat configuré."),
            utilisation=_("Aucune saisie."),
            action=_("Relance l'inspection."),
            reaction=_("Aucun effet (lecture seule)."),
        ),
    ),
    consequences=_("Aucune - purement consultatif."),
    points_de_vigilance=(
        (
            _("Inspecte le FICHIER sur disque, pas nécessairement celui réellement servi par un "
            "serveur déjà lancé si celui-ci a changé depuis le dernier redémarrage.")
        ),
    ),
)

GENERATE_SELF_SIGNED_SCREEN = ScreenGuide(
    screen_class_name="GenerateSelfSignedScreen",
    title=_("Générer un certificat auto-signé"),
    acces=_("Configuration détaillée -> TLS -> Générer un certificat auto-signé"),
    definition=_("Génère un certificat auto-signé (jamais reconnu par défaut par les navigateurs) et l'écrit sur disque."),
    fields=(
        FieldGuide(
            label=_("Nom commun (CN)"),
            definition=_("Nom commun du certificat."),
            utilisation=_("Chaîne libre, généralement le nom d'hôte du serveur."),
            action=_("Utilisé à la génération."),
            reaction=_("Écrit réellement le certificat/la clé sur disque immédiatement."),
        ),
        FieldGuide(
            label=_("SAN DNS / SAN IP"),
            definition=_("Noms DNS et adresses IP alternatifs couverts par le certificat."),
            utilisation=_("Listes séparées par des virgules, optionnelles."),
            action=_("Utilisé à la génération."),
            reaction=_("Écrit sur disque immédiatement."),
        ),
        FieldGuide(
            label=_("Organisation / Unité / Ville / Région / Pays"),
            definition=_("Champs d'identité du certificat (sujet X.509)."),
            utilisation=_("Chaînes libres, tous optionnels sauf Organisation (pré-rempli : OMEGA-SERV)."),
            action=_("Utilisé à la génération."),
            reaction=_("Écrit sur disque immédiatement."),
        ),
        FieldGuide(
            label=_("Validité en jours"),
            definition=_("Durée de validité du certificat généré."),
            utilisation=_("Entier positif, en jours. Valeur par défaut : 365."),
            action=_("Utilisé à la génération."),
            reaction=_("Écrit sur disque immédiatement."),
        ),
        FieldGuide(
            label=_("Type de clé"),
            definition=_("Algorithme et taille de la clé privée générée."),
            utilisation=_("Valeurs valides indiquées dans le sous-titre. Valeur par défaut : rsa2048."),
            action=_("Utilisé à la génération."),
            reaction=_("Écrit sur disque immédiatement."),
        ),
        FieldGuide(
            label=_("Mot de passe de clé (optionnel)"),
            definition=_("Passphrase protégeant la clé privée générée."),
            utilisation=_("Chaîne libre, optionnelle - saisie masquée."),
            action=_("Utilisé à la génération."),
            reaction=_("Écrit sur disque immédiatement."),
        ),
    ),
    consequences=(
        _("Génère réellement des fichiers sur disque des le clic sur Générer. Si TLS est DÉJÀ "
        "actif, le serveur en cours d'exécution continue de servir l'ANCIEN certificat jusqu'à "
        "un REDÉMARRAGE COMPLET, même si le fichier a changé (le contexte SSL n'est construit "
        "qu'une seule fois au démarrage).")
    ),
)

CA_WIZARD_SCREEN = ScreenGuide(
    screen_class_name="CaWizardScreen",
    title=_("Assistant CA locale"),
    acces=_("Configuration détaillée -> TLS -> Assistant CA locale"),
    definition=(
        _("Enchaîne trois étapes indépendantes : générer une autorité de certification locale, "
        "générer une demande de signature (CSR) pour ce serveur, signer cette CSR avec la CA - "
        "permet d'obtenir un certificat reconnu par les clients ayant importe la CA, sans passer "
        "par une autorité publique.")
    ),
    fields=(
        FieldGuide(
            label=_("1. Générer la CA"),
            definition=_("Crée l'autorité de certification locale (clé + certificat racine)."),
            utilisation=_("CN, organisation, validité (défaut 3650 jours), type de clé, passphrase OBLIGATOIRE (saisie deux fois)."),
            action=_("Écrit root-ca.key/root-ca.pem/serial.txt/index.txt sous secure/certificates/ca/."),
            reaction=_("Écrit réellement sur disque immédiatement. À faire une seule fois."),
        ),
        FieldGuide(
            label=_("2. Générer la CSR"),
            definition=_("Crée une demande de signature de certificat pour CE serveur."),
            utilisation=_("CN, SAN DNS/IP, identité, type de clé - pas de passphrase ici."),
            action=_("Écrit le fichier .csr à côté de la clé privée du serveur."),
            reaction=_("Écrit réellement sur disque immédiatement."),
        ),
        FieldGuide(
            label=_("3. Signer la CSR"),
            definition=_("Signe la CSR générée à l'étape 2 avec la CA de l'étape 1, produit le certificat final."),
            utilisation=_("Chemin de la CSR (pré-rempli), passphrase de la CA (resaisie), validité en jours (défaut 365)."),
            action=_("Écrit le certificat signé (et la chaîne complète) sur disque."),
            reaction=(
                _("Écrit réellement sur disque immédiatement. Si TLS est DÉJÀ actif, un "
                "REDÉMARRAGE COMPLET reste nécessaire pour que le serveur serve ce nouveau "
                "certificat (le contexte SSL en mémoire ne se recharge jamais tout seul).")
            ),
        ),
    ),
    consequences=(
        _("Le certificat racine de la CA (root-ca.pem) doit être importe manuellement dans le "
        "magasin de confiance de chaque client pour que le certificat final soit reconnu - "
        "rappelé dans le journal de l'assistant après chaque étape réussie.")
    ),
    points_de_vigilance=(
        (
            _("La passphrase de la CA n'est jamais conservée en mémoire entre les étapes - elle "
            "est resaisie explicitement à l'étape 3.")
        ),
    ),
)

LETS_ENCRYPT_SCREEN = ScreenGuide(
    screen_class_name="LetsEncryptScreen",
    title=_("Assistant Let's Encrypt (Certbot)"),
    acces=_("Configuration détaillée -> TLS -> Assistant Let's Encrypt (Certbot)"),
    definition=(
        _("Obtient un certificat public reconnu par les navigateurs via Certbot (défi HTTP-01, "
        "mode webroot) - jamais --standalone (le port 80 est déjà occupé par OMEGA-SERV) et "
        "jamais /etc/letsencrypt/ (tout est écrit sous secure/certificates/letsencrypt/ du "
        "projet, entièrement non-privilégié). Importe automatiquement le certificat obtenu et "
        "installe un script de renouvellement (voir Renouvellement automatique (Certbot)).")
    ),
    fields=(
        FieldGuide(
            label=_("Domaine"),
            definition=_("Nom de domaine public déjà pointé vers ce serveur (obligatoire)."),
            utilisation=_("Ex : monserveur.dynu.com - un DDNS (Dynu ou équivalent) reste à configurer par vous-même, hors de cet assistant."),
            action=_("Utilisé pour la demande Certbot et le défi HTTP-01."),
            reaction=_("Aucun effet avant confirmation - le résumé préalable rappelle le domaine et le mode choisis."),
        ),
        FieldGuide(
            label=_("Email"),
            definition=_("Adresse utilisée par Let's Encrypt pour les alertes d'expiration (optionnelle)."),
            utilisation=_("Chaîne libre. Vide : Certbot s'enregistre sans email (--register-unsafely-without-email)."),
            action=_("Transmis à Certbot à la demande."),
            reaction=_("Aucun effet avant confirmation."),
        ),
        FieldGuide(
            label=_("Mode test (staging)"),
            definition=_("Utilise l'environnement de test de Let's Encrypt plutôt que la production."),
            utilisation=_("Case à cocher, COCHÉE PAR DÉFAUT - certificat non reconnu par les navigateurs mais jamais soumis aux limites de taux réelles."),
            action=_("Transmis à Certbot (--staging) si coché."),
            reaction=_("À décocher seulement une fois le domaine/webroot vérifiés fonctionnels en mode test."),
        ),
        FieldGuide(
            label=_("Obtenir le certificat"),
            definition=_("Lance la demande après un résumé et une confirmation explicite."),
            utilisation=_("Aucune saisie - déclenche l'appel réseau réel à Let's Encrypt."),
            action=_("Exécute Certbot puis importe le certificat obtenu (déporté dans un thread de travail, l'interface reste réactive)."),
            reaction=(
                _("Écrit réellement sur disque en cas de succès. Si TLS est DÉJÀ actif, le serveur "
                "en cours d'exécution continue de servir l'ANCIEN certificat jusqu'à un "
                "REDÉMARRAGE COMPLET.")
            ),
        ),
    ),
    consequences=(
        _("Le port 80 doit rester accessible depuis Internet le temps du défi HTTP-01 (webroot) - "
        "échoue sinon (pare-feu, redirection de port non faite sur le routeur, DNS/DDNS pas "
        "encore propagé). Soumis aux limites de taux réelles de Let's Encrypt en mode production "
        "(jamais en mode test).")
    ),
    points_de_vigilance=(
        (
            _("Le DDNS (Dynu ou équivalent) et la redirection de port restent ENTIÈREMENT à votre "
            "charge - cet assistant ne configure jamais rien en dehors de ce serveur.")
        ),
        (
            _("Si OMEGA-SERV tourne dans un conteneur : exécutez cet assistant HORS du conteneur "
            "qui sert le trafic (sur l'hôte, ou un conteneur/sidecar distinct partageant le même "
            "volume secure/ et le même webroot) - jamais Certbot à l'intérieur du conteneur "
            "servant déjà le trafic public, voir la FAQ.")
        ),
    ),
)

RENEWAL_SCHEDULE_SCREEN = ScreenGuide(
    screen_class_name="RenewalScheduleScreen",
    title=_("Renouvellement automatique (Certbot)"),
    acces=_("Configuration détaillée -> TLS -> Renouvellement automatique (Certbot)"),
    definition=(
        _("Planifie le renouvellement automatique des certificats Certbot déjà obtenus (Assistant "
        "Let's Encrypt) - s'adapte au gestionnaire de service réellement détecté pour CETTE "
        "instance : timer systemd installé depuis l'interface, sinon une ligne crontab si "
        "possible, sinon des instructions manuelles affichées sans rien écrire. Jamais un "
        "mécanisme global partagé entre plusieurs instances multi-instance.")
    ),
    fields=(
        FieldGuide(
            label=_("Configurer maintenant"),
            definition=_("Installe (ou réinstalle) le mécanisme de renouvellement adapté à ce système."),
            utilisation=_("Aucune saisie."),
            action=(
                _("systemd : écrit et active un timer (sudo ponctuel, même mécanisme que l'écran "
                "SERVICE). OpenRC/runit/aucun gestionnaire reconnu : ajoute une ligne à votre "
                "crontab utilisateur si `crontab` est disponible, sinon affiche la ligne à ajouter "
                "vous-même.")
            ),
            reaction=_("Reconfigurer ne dupliqué jamais l'entrée (idempotent) - remplace toujours l'entrée précédente de CETTE instance."),
        ),
    ),
    consequences=(
        _("Une fois installé, le renouvellement tourne deux fois par jour sans aucune intervention "
        "- le script de hook (Assistant Let's Encrypt) réimporte automatiquement chaque "
        "certificat renouvelé puis redémarre le service.")
    ),
    points_de_vigilance=(
        (
            _("Sur certaines distributions (dont Arch/Manjaro), le paquet Certbot n'installe AUCUN "
            "timer par défaut, contrairement à Debian/Ubuntu - vérifiez toujours le statut affiché "
            "ici plutôt que de supposer qu'un mécanisme existe déjà.")
        ),
        (
            _("Ne concerne QUE les certificats gérés par Certbot (secure/certificates/letsencrypt/) "
            "- un certificat auto-signé ou signé par la CA locale n'a pas besoin (et ne bénéficie "
            "pas) de ce renouvellement.")
        ),
    ),
)

REVOKE_CERTIFICATE_SCREEN = ScreenGuide(
    screen_class_name="RevokeCertificateScreen",
    title=_("Révoquer un certificat"),
    acces=_("Configuration détaillée -> TLS -> Révoquer un certificat"),
    definition=_("Marque un certificat comme révoqué dans le registre de la CA (index.txt) - action irréversible pour ce certificat."),
    fields=(
        FieldGuide(
            label=_("Certificat à révoquer"),
            definition=_("Chemin du certificat à marquer comme révoqué."),
            utilisation=_("Chemin relatif au projet."),
            action=_("Utilisé à la confirmation."),
            reaction=_("Modifie index.txt immédiatement après confirmation."),
        ),
        FieldGuide(
            label=_("Clé / Certificat de la CA"),
            definition=_("Identité de l'autorité de certification qui a signé le certificat visé."),
            utilisation=_("Chemins pré-remplis vers secure/certificates/ca/."),
            action=_("Utilisé à la confirmation."),
            reaction=_("Modifie index.txt immédiatement."),
        ),
        FieldGuide(
            label=_("Passphrase de la clé CA"),
            definition=_("Nécessaire pour prouver l'autorité sur la CA avant de révoquer."),
            utilisation=_("Saisie masquée."),
            action=_("Utilisé à la confirmation."),
            reaction=_("Modifie index.txt immédiatement."),
        ),
    ),
    consequences=(
        _("Demande une confirmation explicite (action irréversible pour ce certificat). Si le "
        "certificat révoqué est celui ACTUELLEMENT utilisé par un serveur TLS déjà actif, un "
        "REDÉMARRAGE COMPLET est nécessaire, sinon il continue d'être présenté aux clients "
        "malgré sa révocation.")
    ),
    points_de_vigilance=(
        (
            _("Pas de distribution CRL complète en V1 - la révocation reste locale (index.txt), "
            "jamais publiée vers les clients automatiquement.")
        ),
    ),
)

TLS_TOGGLE_SCREEN = ScreenGuide(
    screen_class_name="TlsToggleScreen",
    title=_("Activer / désactiver TLS"),
    acces=_("Configuration détaillée -> TLS -> Activer / désactiver TLS"),
    definition=_("Active ou désactive TLS, et choisit son mode (direct ou derrière un proxy qui termine déjà le TLS)."),
    fields=(
        FieldGuide(
            label=_("Mode"),
            definition=_("Comment TLS est géré par ce serveur."),
            utilisation=(
                _("direct (ce serveur termine TLS lui-même, via ssl.SSLContext local) ou "
                "behind_proxy (TLS déjà terminé en amont, ce serveur reste en HTTP simple).")
            ),
            action=_("Enregistre au clic sur Activer TLS."),
            reaction=_("Nécessite TOUJOURS un REDÉMARRAGE COMPLET, jamais un simple rechargement."),
        ),
        FieldGuide(
            label=_("Chemin du certificat / de la clé privée"),
            definition=_("Fichiers utilisés si le mode est 'direct'. Optionnels : conservent la valeur actuelle si vides."),
            utilisation=_("Chemins relatifs au projet."),
            action=_("Enregistre avec le mode."),
            reaction=_("Nécessite TOUJOURS un REDÉMARRAGE COMPLET."),
        ),
    ),
    consequences=(
        _("Le contexte SSL n'est construit qu'une seule fois au démarrage - activer, désactiver, "
        "ou changer le mode TLS exige SYSTÉMATIQUEMENT un redémarrage complet, que ce soit pour "
        "l'activation ou la désactivation.")
    ),
    points_de_vigilance=(
        (
            _("À ne pas confondre avec le réglage 'reverse_proxy' (Configuration détaillée -> "
            "Reverse Proxy) : ici, 'behind_proxy' signifie qu'OMEGA-SERV est DERRIÈRE un proxy "
            "TLS externe, l'inverse d'agir soi-même comme proxy.")
        ),
    ),
)

ALL_TLS_GUIDES: tuple[ScreenGuide, ...] = (
    TLS_MENU_SCREEN,
    TLS_STATUS_SCREEN,
    GENERATE_SELF_SIGNED_SCREEN,
    CA_WIZARD_SCREEN,
    LETS_ENCRYPT_SCREEN,
    RENEWAL_SCHEDULE_SCREEN,
    REVOKE_CERTIFICATE_SCREEN,
    TLS_TOGGLE_SCREEN,
)
