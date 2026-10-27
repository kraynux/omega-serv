"""Fiches guide : Configuration de base et Limites (plan guide d'aide,
Phase 0 - ecrans pilotes), Securite generique et Controle d'acces
(Phase 2), menu Configuration detaillee (Phase 9 - dernier ecran du
plan, boucle la couverture a 64/64)."""
from __future__ import annotations

from omega_serv.core.i18n import _
from omega_serv.interfaces.tui.guide.model import FieldGuide, ScreenGuide

SERVER_CONFIG_MENU_SCREEN = ScreenGuide(
    screen_class_name="ServerConfigMenuScreen",
    title=_("Configuration détaillée (menu)"),
    acces=_("Accueil -> Configuration détaillée"),
    definition=(
        _("Sous-menu regroupant tous les écrans de configuration du serveur et des options "
        "superposables, plus deux raccourcis (Voir options actives, Vérifier la configuration).")
    ),
    fields=(),
    consequences=_("Aucune - purement navigation."),
)

BASE_CONFIG_SCREEN = ScreenGuide(
    screen_class_name="BaseConfigScreen",
    title=_("Configuration de base"),
    acces=_("Accueil -> Configuration détaillée -> Configuration de base"),
    definition=(
        _("Réglages fondamentaux du serveur : adresse d'écoute, port, nom de serveur "
        "annoncé, fichiers d'index cherches dans un répertoire sans nom de fichier explicite.")
    ),
    fields=(
        FieldGuide(
            label=_("Adresse d'écoute (bind)"),
            definition=_("Adresse IP sur laquelle le serveur accepte les connexions."),
            utilisation=(
                _("Une adresse IP valide - '127.0.0.1' (local uniquement) ou '0.0.0.0' "
                "(toutes les interfaces réseau). Valeur par défaut : 127.0.0.1.")
            ),
            action=_("Enregistre dans server.bind après validation structurelle de la configuration."),
            reaction=(
                _("Nécessite un REDÉMARRAGE COMPLET - le socket d'écoute n'est jamais retouché "
                "par un simple rechargement. Un bouton 'Redémarrer maintenant' est proposé "
                "après l'enregistrement si un service est détecté.")
            ),
        ),
        FieldGuide(
            label=_("Port (port)"),
            definition=_("Port TCP d'écoute."),
            utilisation=(
                _("Un entier de port valide (1-65535 ; 0 signifie 'port libre choisi par le "
                "système', surtout utile pour des tests). Valeur par défaut : 8080.")
            ),
            action=_("Enregistre dans server.port après validation."),
            reaction=_("Nécessite un REDÉMARRAGE COMPLET, même raison que l'adresse d'écoute."),
        ),
        FieldGuide(
            label=_("Nom de serveur (server_name)"),
            definition=_("Nom de serveur utilisé en interne (transmis notamment à FastCGI)."),
            utilisation=_("Chaîne libre, optionnelle. Vide par défaut."),
            action=_("Enregistre dans server.server_name."),
            reaction=(
                _("Se recharge à chaud (pas de redémarrage complet nécessaire) - mais reste sans "
                "effet tant qu'un rechargement du service en cours n'a pas eu lieu (automatique "
                "si un service actif existe, sinon à faire manuellement depuis l'écran SERVICE).")
            ),
        ),
        FieldGuide(
            label=_("Fichiers d'index (index_files)"),
            definition=(
                _("Noms de fichiers cherches, dans l'ordre, quand une URL pointe vers un "
                "répertoire sans fichier explicite.")
            ),
            utilisation=_("Liste séparée par des virgules. Valeur par défaut : index.html."),
            action=_("Enregistre dans server.index_files."),
            reaction=_("Même réaction que le nom de serveur - rechargement nécessaire, jamais un redémarrage complet."),
        ),
    ),
    consequences=(
        _("bind/port exigent toujours un redémarrage complet. server_name/index_files se "
        "rechargent à chaud mais nécessitent quand même un rechargement du service déjà lancé "
        "pour être pris en compte.")
    ),
    points_de_vigilance=(
        (
            _("Changer bind/port pendant qu'un service systemd est déjà actif ne prend jamais "
            "effet tant qu'un redémarrage complet n'a pas eu lieu - toutes les connexions en "
            "cours sont alors coupées, contrairement à un simple rechargement.")
        ),
    ),
)

LIMITS_SCREEN = ScreenGuide(
    screen_class_name="LimitsScreen",
    title=_("Résistance et limites"),
    acces=_("Accueil -> Configuration détaillée -> Résistance et limites"),
    definition=(
        _("Dix réglages numériques anti-abus : bornes de taille/nombre/delai appliquées à "
        "chaque connexion et requête.")
    ),
    fields=(
        FieldGuide(
            label=_("Connexions simultanées max (max_connections)"),
            definition=_("Nombre maximal de connexions ouvertes en même temps."),
            utilisation=_("Entier positif. Valeur par défaut : 256."),
            action=_("Enregistre dans server.max_connections."),
            reaction=_("Se recharge à chaud (rechargement du service nécessaire, automatique si actif)."),
        ),
        FieldGuide(
            label=_("Taille max de requête (max_request_size)"),
            definition=_("Taille maximale acceptée pour le corps d'une requête, en octets."),
            utilisation=_("Entier positif, en octets. Valeur par défaut : 10 485 760 (10 Mio)."),
            action=_("Enregistre dans server.max_request_size."),
            reaction=_("Se recharge à chaud."),
        ),
        FieldGuide(
            label=_("Taille max des en-têtes (max_header_size)"),
            definition=(
                _("Taille cumulée maximale des en-têtes HTTP d'une requête, en octets - "
                "protection contre les en-têtes surdimensionnés (HTTP smuggling, saturation mémoire).")
            ),
            utilisation=_("Entier positif, en octets. Valeur par défaut : 16 384."),
            action=_("Enregistre dans server.max_header_size."),
            reaction=_("Se recharge à chaud."),
        ),
        FieldGuide(
            label=_("Taille max de la ligne de requête (max_request_line_size)"),
            definition=_("Taille maximale de la première ligne HTTP (méthode + chemin + version), en octets."),
            utilisation=_("Entier positif, en octets. Valeur par défaut : 8 192."),
            action=_("Enregistre dans server.max_request_line_size."),
            reaction=_("Se recharge à chaud."),
        ),
        FieldGuide(
            label=_("Délai de lecture (read_timeout_seconds)"),
            definition=_("Délai maximal, en secondes, pour recevoir une requête complète avant coupure."),
            utilisation=_("Entier positif, en secondes. Valeur par défaut : 10."),
            action=_("Enregistre dans server.read_timeout_seconds."),
            reaction=_("Se recharge à chaud."),
        ),
        FieldGuide(
            label=_("Délai d'écriture (write_timeout_seconds)"),
            definition=_("Délai maximal, en secondes, pour envoyer la réponse avant coupure."),
            utilisation=_("Entier positif, en secondes. Valeur par défaut : 15."),
            action=_("Enregistre dans server.write_timeout_seconds."),
            reaction=_("Se recharge à chaud."),
        ),
        FieldGuide(
            label=_("Délai keep-alive (keepalive_timeout_seconds)"),
            definition=_("Délai d'inactivité, en secondes, avant fermeture d'une connexion gardée ouverte."),
            utilisation=_("Entier positif, en secondes. Valeur par défaut : 5."),
            action=_("Enregistre dans server.keepalive_timeout_seconds."),
            reaction=_("Se recharge à chaud."),
        ),
        FieldGuide(
            label=_("Requêtes max en keep-alive (max_keepalive_requests)"),
            definition=(
                _("Nombre maximal de requêtes traitées sur une même connexion gardée ouverte. "
                "Une fois atteint, la connexion est simplement fermée et le navigateur en ouvre "
                "une nouvelle : aucune erreur, aucun bannissement. Sans rapport avec la limite de "
                "débit du WAF (Active Sécurité -> Exclusions et débit), qui compte les requêtes "
                "par IP toutes connexions confondues.")
            ),
            utilisation=_("Entier positif. Valeur par défaut : 30."),
            action=_("Enregistre dans server.max_keepalive_requests."),
            reaction=_("Se recharge à chaud."),
        ),
        FieldGuide(
            label=_("File d'attente d'écoute (listen_backlog)"),
            definition=(
                _("Taille de la file d'attente de connexions en attente d'acceptation par le "
                "système d'exploitation (paramètre backlog du socket d'écoute).")
            ),
            utilisation=_("Entier positif. Valeur par défaut : 128."),
            action=_("Enregistre dans server.listen_backlog."),
            reaction=(
                _("Nécessite un REDÉMARRAGE COMPLET - fixé au moment de la création du socket "
                "d'écoute, comme bind/port, jamais retouché par un simple rechargement.")
            ),
        ),
        FieldGuide(
            label=_("Délai de grâce à l'arrêt (shutdown_grace_period_seconds)"),
            definition=_("Délai, en secondes, laissé aux connexions actives pour se terminer lors d'un arrêt."),
            utilisation=_("Entier positif, en secondes. Valeur par défaut : 10."),
            action=_("Enregistre dans server.shutdown_grace_period_seconds."),
            reaction=_("Se recharge à chaud."),
        ),
        FieldGuide(
            label=_("Nombre de workers - mode boost (workers)"),
            definition=(
                _("Nombre de processus serveur qui se partagent le port. Un processus Python n'utilise "
                "qu'un cœur : plusieurs workers servent davantage de requêtes en parallèle. Les compteurs de "
                "sécurité (rate limit, récidive) sont partagés entre workers et restent exacts ; un "
                "script magnet garde ses propres compteurs dans chaque worker.")
            ),
            utilisation=(
                _("1 = un seul processus (par défaut, fonctionnement classique) ; 0 = automatique (un par "
                "cœur physique) ; sinon un nombre jusqu'aux CPU disponibles de cette machine, affichés "
                "sous le champ et dans le registre des capacités. Le nombre doit correspondre à la machine "
                "où omega-serv est installé : une valeur plus grande est refusée.")
            ),
            action=_("Enregistre dans server.workers."),
            reaction=(
                _("Redémarrage complet nécessaire. Si la configuration est recopiée sur une machine plus "
                "petite, le serveur se limite à ses CPU disponibles et l'écrit dans le journal.")
            ),
        ),
    ),
    consequences=(
        _("Neuf champs sur onze se rechargent à chaud (rechargement du service nécessaire, "
        "automatique si actif). listen_backlog et le nombre de workers exigent un redémarrage complet.")
    ),
    points_de_vigilance=(
        (
            _("Un listen_backlog trop bas sous forte charge fait échouer des connexions "
            "entrantes avant même qu'elles atteignent OMEGA-SERV (comportement du système "
            "d'exploitation) - ne descendre sous 128 qu'en connaissance de cause.")
        ),
    ),
)

SECURITY_SCREEN = ScreenGuide(
    screen_class_name="SecurityScreen",
    title=_("Sécurité générique"),
    acces=_("Accueil -> Configuration détaillée -> Sécurité générique"),
    definition=(
        _("Règles de sécurité génériques appliquées à toutes les requêtes : méthodes autorisées, "
        "fichiers cachés, en-têtes de sécurité, CSP, HSTS.")
    ),
    fields=(
        FieldGuide(
            label=_("Méthodes autorisées"),
            definition=_("Liste blanche des méthodes HTTP acceptées - tout le reste est refusé par défaut."),
            utilisation=_("Liste séparée par des virgules, ex: GET, HEAD. Valeur par défaut : GET, HEAD."),
            action=_("Enregistre dans security.allowed_methods."),
            reaction=_("Se recharge à chaud (rechargement du service nécessaire, automatique si actif)."),
        ),
        FieldGuide(
            label=_("Refuser les fichiers cachés (oui/non)"),
            definition=(
                _("Masque tout fichier ou dossier dont un segment de chemin commence par un point "
                "(dotfile) - à la fois en accès direct et dans le directory listing.")
            ),
            utilisation=_("oui ou non (accepte aussi true/1/o/y). Valeur par défaut : oui."),
            action=_("Enregistre dans security.deny_hidden_files."),
            reaction=_("Se recharge à chaud."),
        ),
        FieldGuide(
            label=_("Mode CSP"),
            definition=_("Mode d'application de la Content-Security-Policy envoyée dans les réponses."),
            utilisation=_("enforce (bloque) ou report-only (signale sans bloquer). Valeur par défaut : enforce."),
            action=_("Enregistre dans security.csp_mode."),
            reaction=_("Se recharge à chaud."),
        ),
        FieldGuide(
            label=_("Cross-Origin-Embedder-Policy"),
            definition=(
                _("Isolation cross-origin - 'require-corp'/'credentialless' peuvent bloquer des "
                "ressources cross-origin (polices, images, iframes tiers) que ce serveur "
                "générique ne connaît pas à l'avance, contrairement à COOP/CORP (toujours actifs, "
                "sans ce risque).")
            ),
            utilisation=(
                _("unsafe-none (permissif, par défaut partout y compris hardened), require-corp ou "
                "credentialless - à activer uniquement en connaissance du contenu réellement servi.")
            ),
            action=_("Enregistre dans security.coep_mode."),
            reaction=_("Se recharge à chaud - toujours émis explicitement, même en unsafe-none (jamais un en-tête absent)."),
        ),
        FieldGuide(
            label=_("En-têtes de sécurité actifs (oui/non)"),
            definition=_("Active l'envoi des en-têtes de sécurité standard (CSP, X-Content-Type-Options...)."),
            utilisation=_("oui ou non. Valeur par défaut : oui."),
            action=_("Enregistre dans security.security_headers_enabled."),
            reaction=_("Se recharge à chaud."),
        ),
        FieldGuide(
            label=_("Zones CSP (Ajouter une zone / Retirer)"),
            definition=(
                _("Exceptions EXPLICITES à la CSP globale, par préfixe de chemin - ex. 'unsafe-inline' "
                "uniquement sous /un-dossier/ qui en a réellement besoin, sans jamais relâcher la "
                "CSP du reste du site.")
            ),
            utilisation=(
                _("Préfixe (ex: /public-widgets/) + politique CSP COMPLÈTE pour ce préfixe (remplace "
                "entièrement le défaut pour ces chemins, jamais une fusion de directives).")
            ),
            action=_("Enregistre immédiatement dans security.csp_zones, sans passer par Enregistrer."),
            reaction=(
                _("Rechargement automatique immédiat si un service actif existe. Une exception comme "
                "'unsafe-inline' reste TOUJOURS visible dans 'omega-serv audit security' (CSP-001/"
                "CSP-002), même délibérée - jamais silencieuse.")
            ),
        ),
        FieldGuide(
            label=_("HSTS actif (oui/non)"),
            definition=_("Active l'en-tête Strict-Transport-Security (force HTTPS pour les visites futures)."),
            utilisation=_("oui ou non. Valeur par défaut : non. N'a de sens que si TLS est réellement actif."),
            action=_("Enregistre dans security.hsts_enabled."),
            reaction=_("Se recharge à chaud."),
        ),
        FieldGuide(
            label=_("HSTS max-age"),
            definition=_("Durée, en secondes, pendant laquelle un navigateur retient l'obligation HTTPS."),
            utilisation=_("Entier positif, en secondes. Valeur par défaut : 31 536 000 (un an)."),
            action=_("Enregistre dans security.hsts_max_age."),
            reaction=_("Se recharge à chaud."),
        ),
        FieldGuide(
            label=_("HSTS includeSubDomains (oui/non)"),
            definition=_("Étend l'obligation HTTPS à tous les sous-domaines."),
            utilisation=_("oui ou non. Valeur par défaut : oui."),
            action=_("Enregistre dans security.hsts_include_subdomains."),
            reaction=_("Se recharge à chaud."),
        ),
        FieldGuide(
            label=_("HSTS preload (oui/non)"),
            definition=_("Signale l'éligibilité à la liste de prechargement HSTS des navigateurs."),
            utilisation=_("oui ou non. Valeur par défaut : non."),
            action=_("Enregistre dans security.hsts_preload."),
            reaction=_("Se recharge à chaud."),
        ),
    ),
    consequences=_("Tous les champs de cet écran se rechargent à chaud - aucun n'exige de redémarrage complet."),
    points_de_vigilance=(
        (
            _("Activer HSTS sans que TLS soit réellement actif n'a aucun effet utile - le navigateur "
            "ignore cet en-tête reçu en HTTP simple.")
        ),
    ),
)

CSP_ZONE_WIZARD_SCREEN = ScreenGuide(
    screen_class_name="CspZoneWizardScreen",
    title=_("Sécurité générique - Assistant zone CSP"),
    acces=_("Sécurité générique -> Ajouter une zone"),
    definition=(
        _("Construit la politique CSP d'une zone directive par directive, chacune pré-remplie avec "
        "sa valeur ACTUELLE (la politique globale) - une zone remplace ENTIÈREMENT la politique "
        "par défaut pour son préfixe, jamais un simple ajout, d'où le pré-remplissage pour éviter "
        "de perdre des directives sans le vouloir.")
    ),
    fields=(
        FieldGuide(
            label=_("Préfixe"),
            definition=_("Chemin URL auquel s'applique cette politique de remplacement."),
            utilisation=_("Doit commencer par '/', ex: /public-widgets/."),
            action=_("Utilisé au clic sur Valider."),
            reaction=_("Aucun effet avant Valider."),
        ),
        FieldGuide(
            label=_("Directives (une par ligne, ex. style-src, script-src...)"),
            definition=_("Chaque champ contrôle une famille de ressources - l'indice sous chaque champ explique précisément laquelle."),
            utilisation=_("Pré-rempli avec la valeur actuelle - modifier uniquement ce qui doit changer, vider pour omettre la directive dans la zone."),
            action=_("Reassemblees en une seule politique au clic sur Valider."),
            reaction=_("Une valeur contenant unsafe-inline/unsafe-eval/'*' déclenche une confirmation explicite supplémentaire avant d'enregistrer."),
        ),
    ),
    consequences=(
        _("La zone créée reste visible dans 'omega-serv audit security' (CSP-001/CSP-002 scannent "
        "aussi les zones) si elle contient une relâche - jamais silencieuse, même délibérée.")
    ),
)

ACCESS_CONTROL_SCREEN = ScreenGuide(
    screen_class_name="AccessControlScreen",
    title=_("Contrôle d'accès"),
    acces=_("Accueil -> Configuration détaillée -> Contrôle d'accès"),
    definition=(
        _("CRUD de règles allow/deny par préfixe d'URL, avec filtre optionnel par extension - permet "
        "par exemple de bloquer des extensions sensibles partout SAUF dans une zone précise.")
    ),
    fields=(
        FieldGuide(
            label=_("Préfixe URL"),
            definition=_("Le préfixe de chemin auquel s'applique la règle."),
            utilisation=_("Doit commencer par '/', ex: /private/. Le plus long préfixe correspondant gagne."),
            action=_("Ajoute/modifie une règle via Ajouter/Modifier."),
            reaction=_("Aucun effet sans rechargement du service (automatique si actif)."),
        ),
        FieldGuide(
            label=_("Verdict"),
            definition=_("Ce que décide la règle pour les chemins qu'elle couvre."),
            utilisation=_("allow ou deny."),
            action=_("Ajoute/modifie une règle."),
            reaction=_("Aucun effet sans rechargement du service."),
        ),
        FieldGuide(
            label=_("Extensions"),
            definition=(
                _("Restreint la règle aux chemins se terminant par l'une de ces extensions - vide "
                "signifie 'toutes', la règle s'applique alors à tout chemin sous ce préfixe.")
            ),
            utilisation=_("Liste séparée par des virgules, ex: .key, .pem. Vide par défaut (toutes)."),
            action=_("Ajoute/modifie une règle."),
            reaction=_("Aucun effet sans rechargement du service."),
        ),
    ),
    consequences=(
        _("L'option access_control doit être activée (écran Options) pour que ces règles soient "
        "réellement appliquées. Toutes les modifications se rechargent à chaud.")
    ),
    points_de_vigilance=(
        (
            _("Le plus long préfixe correspondant gagne : une règle 'allow' plus spécifique lève "
            "le 'deny' d'un préfixe parent (ex: deny /private/, allow /private/.assets/). Une "
            "règle 'allow' explicite lève aussi les règles génériques dotfiles/motifs de l'écran "
            "Sécurité générique sur ce chemin précis.")
        ),
        (
            _("Pour bloquer une extension sensible PARTOUT sauf dans une zone : une règle deny sur "
            "'/' avec l'extension visée, puis une règle allow (sans extension) sur le préfixe à "
            "excepter - le préfixe le plus spécifique l'emporte.")
        ),
    ),
)
