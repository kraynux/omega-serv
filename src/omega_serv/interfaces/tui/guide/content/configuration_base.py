# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Fiches guide : Configuration de base et Limites (plan guide d'aide,
Phase 0 - ecrans pilotes), Securite generique et Controle d'acces
(Phase 2), menu Configuration detaillee (Phase 9 - dernier ecran du
plan, boucle la couverture a 64/64)."""
from __future__ import annotations

from omega_serv.interfaces.tui.guide.model import FieldGuide, ScreenGuide

SERVER_CONFIG_MENU_SCREEN = ScreenGuide(
    screen_class_name="ServerConfigMenuScreen",
    title="Configuration detaillee (menu)",
    acces="Accueil -> Configuration detaillee",
    definition=(
        "Sous-menu regroupant tous les ecrans de configuration du serveur et des options "
        "superposables, plus deux raccourcis (Voir options actives, Verifier la configuration)."
    ),
    fields=(),
    consequences="Aucune - purement navigation.",
)

BASE_CONFIG_SCREEN = ScreenGuide(
    screen_class_name="BaseConfigScreen",
    title="Configuration de base",
    acces="Accueil -> Configuration detaillee -> Configuration de base",
    definition=(
        "Reglages fondamentaux du serveur : adresse d'ecoute, port, nom de serveur "
        "annonce, fichiers d'index cherches dans un repertoire sans nom de fichier explicite."
    ),
    fields=(
        FieldGuide(
            label="Adresse d'ecoute (bind)",
            definition="Adresse IP sur laquelle le serveur accepte les connexions.",
            utilisation=(
                "Une adresse IP valide - '127.0.0.1' (local uniquement) ou '0.0.0.0' "
                "(toutes les interfaces reseau). Valeur par defaut : 127.0.0.1."
            ),
            action="Enregistre dans server.bind apres validation structurelle de la configuration.",
            reaction=(
                "Necessite un REDEMARRAGE COMPLET - le socket d'ecoute n'est jamais retouche "
                "par un simple rechargement. Un bouton 'Redemarrer maintenant' est propose "
                "apres l'enregistrement si un service est detecte."
            ),
        ),
        FieldGuide(
            label="Port (port)",
            definition="Port TCP d'ecoute.",
            utilisation=(
                "Un entier de port valide (1-65535 ; 0 signifie 'port libre choisi par le "
                "systeme', surtout utile pour des tests). Valeur par defaut : 8080."
            ),
            action="Enregistre dans server.port apres validation.",
            reaction="Necessite un REDEMARRAGE COMPLET, meme raison que l'adresse d'ecoute.",
        ),
        FieldGuide(
            label="Nom de serveur (server_name)",
            definition="Nom de serveur utilise en interne (transmis notamment a FastCGI).",
            utilisation="Chaine libre, optionnelle. Vide par defaut.",
            action="Enregistre dans server.server_name.",
            reaction=(
                "Se recharge a chaud (pas de redemarrage complet necessaire) - mais reste sans "
                "effet tant qu'un rechargement du service en cours n'a pas eu lieu (automatique "
                "si un service actif existe, sinon a faire manuellement depuis l'ecran SERVICE)."
            ),
        ),
        FieldGuide(
            label="Fichiers d'index (index_files)",
            definition=(
                "Noms de fichiers cherches, dans l'ordre, quand une URL pointe vers un "
                "repertoire sans fichier explicite."
            ),
            utilisation="Liste separee par des virgules. Valeur par defaut : index.html.",
            action="Enregistre dans server.index_files.",
            reaction="Meme reaction que le nom de serveur - rechargement necessaire, jamais un redemarrage complet.",
        ),
    ),
    consequences=(
        "bind/port exigent toujours un redemarrage complet. server_name/index_files se "
        "rechargent a chaud mais necessitent quand meme un rechargement du service deja lance "
        "pour etre pris en compte."
    ),
    points_de_vigilance=(
        (
            "Changer bind/port pendant qu'un service systemd est deja actif ne prend jamais "
            "effet tant qu'un redemarrage complet n'a pas eu lieu - toutes les connexions en "
            "cours sont alors coupees, contrairement a un simple rechargement."
        ),
    ),
)

LIMITS_SCREEN = ScreenGuide(
    screen_class_name="LimitsScreen",
    title="Resistance et limites",
    acces="Accueil -> Configuration detaillee -> Resistance et limites",
    definition=(
        "Dix reglages numeriques anti-abus : bornes de taille/nombre/delai appliquees a "
        "chaque connexion et requete."
    ),
    fields=(
        FieldGuide(
            label="Connexions simultanees max (max_connections)",
            definition="Nombre maximal de connexions ouvertes en meme temps.",
            utilisation="Entier positif. Valeur par defaut : 256.",
            action="Enregistre dans server.max_connections.",
            reaction="Se recharge a chaud (rechargement du service necessaire, automatique si actif).",
        ),
        FieldGuide(
            label="Taille max de requete (max_request_size)",
            definition="Taille maximale acceptee pour le corps d'une requete, en octets.",
            utilisation="Entier positif, en octets. Valeur par defaut : 10 485 760 (10 Mio).",
            action="Enregistre dans server.max_request_size.",
            reaction="Se recharge a chaud.",
        ),
        FieldGuide(
            label="Taille max des en-tetes (max_header_size)",
            definition=(
                "Taille cumulee maximale des en-tetes HTTP d'une requete, en octets - "
                "protection contre les en-tetes surdimensionnes (HTTP smuggling, saturation memoire)."
            ),
            utilisation="Entier positif, en octets. Valeur par defaut : 16 384.",
            action="Enregistre dans server.max_header_size.",
            reaction="Se recharge a chaud.",
        ),
        FieldGuide(
            label="Taille max de la ligne de requete (max_request_line_size)",
            definition="Taille maximale de la premiere ligne HTTP (methode + chemin + version), en octets.",
            utilisation="Entier positif, en octets. Valeur par defaut : 8 192.",
            action="Enregistre dans server.max_request_line_size.",
            reaction="Se recharge a chaud.",
        ),
        FieldGuide(
            label="Delai de lecture (read_timeout_seconds)",
            definition="Delai maximal, en secondes, pour recevoir une requete complete avant coupure.",
            utilisation="Entier positif, en secondes. Valeur par defaut : 10.",
            action="Enregistre dans server.read_timeout_seconds.",
            reaction="Se recharge a chaud.",
        ),
        FieldGuide(
            label="Delai d'ecriture (write_timeout_seconds)",
            definition="Delai maximal, en secondes, pour envoyer la reponse avant coupure.",
            utilisation="Entier positif, en secondes. Valeur par defaut : 15.",
            action="Enregistre dans server.write_timeout_seconds.",
            reaction="Se recharge a chaud.",
        ),
        FieldGuide(
            label="Delai keep-alive (keepalive_timeout_seconds)",
            definition="Delai d'inactivite, en secondes, avant fermeture d'une connexion gardee ouverte.",
            utilisation="Entier positif, en secondes. Valeur par defaut : 5.",
            action="Enregistre dans server.keepalive_timeout_seconds.",
            reaction="Se recharge a chaud.",
        ),
        FieldGuide(
            label="Requetes max en keep-alive (max_keepalive_requests)",
            definition="Nombre maximal de requetes traitees sur une meme connexion gardee ouverte.",
            utilisation="Entier positif. Valeur par defaut : 30.",
            action="Enregistre dans server.max_keepalive_requests.",
            reaction="Se recharge a chaud.",
        ),
        FieldGuide(
            label="File d'attente d'ecoute (listen_backlog)",
            definition=(
                "Taille de la file d'attente de connexions en attente d'acceptation par le "
                "systeme d'exploitation (parametre backlog du socket d'ecoute)."
            ),
            utilisation="Entier positif. Valeur par defaut : 128.",
            action="Enregistre dans server.listen_backlog.",
            reaction=(
                "Necessite un REDEMARRAGE COMPLET - fixe au moment de la creation du socket "
                "d'ecoute, comme bind/port, jamais retouche par un simple rechargement."
            ),
        ),
        FieldGuide(
            label="Delai de grace a l'arret (shutdown_grace_period_seconds)",
            definition="Delai, en secondes, laisse aux connexions actives pour se terminer lors d'un arret.",
            utilisation="Entier positif, en secondes. Valeur par defaut : 10.",
            action="Enregistre dans server.shutdown_grace_period_seconds.",
            reaction="Se recharge a chaud.",
        ),
    ),
    consequences=(
        "Neuf champs sur dix se rechargent a chaud (rechargement du service necessaire, "
        "automatique si actif). Seul listen_backlog exige un redemarrage complet."
    ),
    points_de_vigilance=(
        (
            "Un listen_backlog trop bas sous forte charge fait echouer des connexions "
            "entrantes avant meme qu'elles atteignent OMEGA-SERV (comportement du systeme "
            "d'exploitation) - ne descendre sous 128 qu'en connaissance de cause."
        ),
    ),
)

SECURITY_SCREEN = ScreenGuide(
    screen_class_name="SecurityScreen",
    title="Securite generique",
    acces="Accueil -> Configuration detaillee -> Securite generique",
    definition=(
        "Regles de securite generiques appliquees a toutes les requetes : methodes autorisees, "
        "fichiers caches, en-tetes de securite, CSP, HSTS."
    ),
    fields=(
        FieldGuide(
            label="Methodes autorisees",
            definition="Liste blanche des methodes HTTP acceptees - tout le reste est refuse par defaut.",
            utilisation="Liste separee par des virgules, ex: GET, HEAD. Valeur par defaut : GET, HEAD.",
            action="Enregistre dans security.allowed_methods.",
            reaction="Se recharge a chaud (rechargement du service necessaire, automatique si actif).",
        ),
        FieldGuide(
            label="Refuser les fichiers caches (oui/non)",
            definition=(
                "Masque tout fichier ou dossier dont un segment de chemin commence par un point "
                "(dotfile) - a la fois en acces direct et dans le directory listing."
            ),
            utilisation="oui ou non (accepte aussi true/1/o/y). Valeur par defaut : oui.",
            action="Enregistre dans security.deny_hidden_files.",
            reaction="Se recharge a chaud.",
        ),
        FieldGuide(
            label="Mode CSP",
            definition="Mode d'application de la Content-Security-Policy envoyee dans les reponses.",
            utilisation="enforce (bloque) ou report-only (signale sans bloquer). Valeur par defaut : enforce.",
            action="Enregistre dans security.csp_mode.",
            reaction="Se recharge a chaud.",
        ),
        FieldGuide(
            label="En-tetes de securite actifs (oui/non)",
            definition="Active l'envoi des en-tetes de securite standard (CSP, X-Content-Type-Options...).",
            utilisation="oui ou non. Valeur par defaut : oui.",
            action="Enregistre dans security.security_headers_enabled.",
            reaction="Se recharge a chaud.",
        ),
        FieldGuide(
            label="HSTS actif (oui/non)",
            definition="Active l'en-tete Strict-Transport-Security (force HTTPS pour les visites futures).",
            utilisation="oui ou non. Valeur par defaut : non. N'a de sens que si TLS est reellement actif.",
            action="Enregistre dans security.hsts_enabled.",
            reaction="Se recharge a chaud.",
        ),
        FieldGuide(
            label="HSTS max-age",
            definition="Duree, en secondes, pendant laquelle un navigateur retient l'obligation HTTPS.",
            utilisation="Entier positif, en secondes. Valeur par defaut : 31 536 000 (un an).",
            action="Enregistre dans security.hsts_max_age.",
            reaction="Se recharge a chaud.",
        ),
        FieldGuide(
            label="HSTS includeSubDomains (oui/non)",
            definition="Etend l'obligation HTTPS a tous les sous-domaines.",
            utilisation="oui ou non. Valeur par defaut : oui.",
            action="Enregistre dans security.hsts_include_subdomains.",
            reaction="Se recharge a chaud.",
        ),
        FieldGuide(
            label="HSTS preload (oui/non)",
            definition="Signale l'eligibilite a la liste de prechargement HSTS des navigateurs.",
            utilisation="oui ou non. Valeur par defaut : non.",
            action="Enregistre dans security.hsts_preload.",
            reaction="Se recharge a chaud.",
        ),
    ),
    consequences="Tous les champs de cet ecran se rechargent a chaud - aucun n'exige de redemarrage complet.",
    points_de_vigilance=(
        (
            "Activer HSTS sans que TLS soit reellement actif n'a aucun effet utile - le navigateur "
            "ignore cet en-tete recu en HTTP simple."
        ),
    ),
)

ACCESS_CONTROL_SCREEN = ScreenGuide(
    screen_class_name="AccessControlScreen",
    title="Controle d'acces",
    acces="Accueil -> Configuration detaillee -> Controle d'acces",
    definition=(
        "CRUD de regles allow/deny par prefixe d'URL, avec filtre optionnel par extension - permet "
        "par exemple de bloquer des extensions sensibles partout SAUF dans une zone precise."
    ),
    fields=(
        FieldGuide(
            label="Prefixe URL",
            definition="Le prefixe de chemin auquel s'applique la regle.",
            utilisation="Doit commencer par '/', ex: /private/. Le plus long prefixe correspondant gagne.",
            action="Ajoute/modifie une regle via Ajouter/Modifier.",
            reaction="Aucun effet sans rechargement du service (automatique si actif).",
        ),
        FieldGuide(
            label="Verdict",
            definition="Ce que decide la regle pour les chemins qu'elle couvre.",
            utilisation="allow ou deny.",
            action="Ajoute/modifie une regle.",
            reaction="Aucun effet sans rechargement du service.",
        ),
        FieldGuide(
            label="Extensions",
            definition=(
                "Restreint la regle aux chemins se terminant par l'une de ces extensions - vide "
                "signifie 'toutes', la regle s'applique alors a tout chemin sous ce prefixe."
            ),
            utilisation="Liste separee par des virgules, ex: .key, .pem. Vide par defaut (toutes).",
            action="Ajoute/modifie une regle.",
            reaction="Aucun effet sans rechargement du service.",
        ),
    ),
    consequences=(
        "L'option access_control doit etre activee (ecran Options) pour que ces regles soient "
        "reellement appliquees. Toutes les modifications se rechargent a chaud."
    ),
    points_de_vigilance=(
        (
            "Le plus long prefixe correspondant gagne : une regle 'allow' plus specifique leve "
            "le 'deny' d'un prefixe parent (ex: deny /private/, allow /private/.assets/). Une "
            "regle 'allow' explicite leve aussi les regles generiques dotfiles/motifs de l'ecran "
            "Securite generique sur ce chemin precis."
        ),
        (
            "Pour bloquer une extension sensible PARTOUT sauf dans une zone : une regle deny sur "
            "'/' avec l'extension visee, puis une regle allow (sans extension) sur le prefixe a "
            "excepter - le prefixe le plus specifique l'emporte."
        ),
    ),
)
