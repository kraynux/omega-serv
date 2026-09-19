"""Fiches guide : Alias, Redirections, Rewrites, Directory listing,
Cache, Pages d'erreur, Proxies de confiance (plan guide d'aide, Phase 3)."""
from __future__ import annotations

from omega_serv.interfaces.tui.guide.model import FieldGuide, ScreenGuide

ALIASES_SCREEN = ScreenGuide(
    screen_class_name="AliasesScreen",
    title="Alias",
    acces="Accueil -> Configuration detaillee -> Alias",
    definition="CRUD d'alias : sert un prefixe d'URL depuis un chemin cible, y compris hors du webroot.",
    fields=(
        FieldGuide(
            label="Prefixe URL",
            definition="Le prefixe d'URL a rediriger vers un autre emplacement disque.",
            utilisation="Doit commencer par '/', ex: /media/.",
            action="Ajoute/modifie un alias.",
            reaction="Aucun effet sans rechargement du service (automatique si actif).",
        ),
        FieldGuide(
            label="Chemin cible",
            definition="L'emplacement disque reellement servi pour ce prefixe.",
            utilisation="Chemin relatif au projet, ex: webroot/media, ou un chemin hors webroot.",
            action="Ajoute/modifie un alias.",
            reaction="Aucun effet sans rechargement du service.",
        ),
        FieldGuide(
            label="Autoriser hors webroot (oui/non)",
            definition="Autorise explicitement une cible situee en dehors du webroot habituel.",
            utilisation="oui ou non. Valeur par defaut : non.",
            action="Ajoute/modifie un alias.",
            reaction="Aucun effet sans rechargement du service.",
        ),
    ),
    consequences=(
        "L'option aliases doit etre activee (ecran Options) pour que ces alias soient "
        "reellement appliques. Toutes les modifications se rechargent a chaud."
    ),
)

REDIRECTS_SCREEN = ScreenGuide(
    screen_class_name="RedirectsScreen",
    title="Redirections",
    acces="Accueil -> Configuration detaillee -> Redirections",
    definition="CRUD de redirections HTTP (reponse 3xx avec en-tete Location).",
    fields=(
        FieldGuide(
            label="Prefixe URL",
            definition="Le prefixe d'URL qui declenche la redirection.",
            utilisation="Doit commencer par '/', ex: /old/.",
            action="Ajoute/modifie une redirection.",
            reaction="Aucun effet sans rechargement du service.",
        ),
        FieldGuide(
            label="Destination",
            definition="L'URL ou le chemin envoye dans l'en-tete Location de la reponse.",
            utilisation="Chaine libre, ex: /new/.",
            action="Ajoute/modifie une redirection.",
            reaction="Aucun effet sans rechargement du service.",
        ),
        FieldGuide(
            label="Code",
            definition="Le code de statut HTTP de redirection utilise.",
            utilisation="301, 302, 307 ou 308. Valeur par defaut : 302.",
            action="Ajoute/modifie une redirection.",
            reaction="Aucun effet sans rechargement du service.",
        ),
    ),
    consequences=(
        "L'option redirects doit etre activee (ecran Options). Toutes les modifications se "
        "rechargent a chaud."
    ),
)

REWRITES_SCREEN = ScreenGuide(
    screen_class_name="RewritesScreen",
    title="Rewrites",
    acces="Accueil -> Configuration detaillee -> Rewrites",
    definition=(
        "CRUD de reecritures d'URL internes - remplace un prefixe par un autre AVANT le "
        "traitement de la requete, sans jamais renvoyer de redirection au client (invisible cote navigateur)."
    ),
    fields=(
        FieldGuide(
            label="Prefixe recherche",
            definition="Le prefixe d'URL a reconnaitre.",
            utilisation="Doit commencer par '/', ex: /old/.",
            action="Ajoute/modifie un rewrite.",
            reaction="Aucun effet sans rechargement du service.",
        ),
        FieldGuide(
            label="Prefixe remplacement",
            definition="Le prefixe qui remplace le prefixe recherche.",
            utilisation="Chaine non vide, ex: /new/.",
            action="Ajoute/modifie un rewrite.",
            reaction="Aucun effet sans rechargement du service.",
        ),
    ),
    consequences=(
        "L'option rewrites doit etre activee (ecran Options). Toutes les modifications se "
        "rechargent a chaud."
    ),
    points_de_vigilance=(
        (
            "Distinct d'une redirection : le client ne voit jamais l'URL rewritee, "
            "contrairement a une redirection qui change l'URL affichee dans le navigateur."
        ),
    ),
)

DIRLISTING_SCREEN = ScreenGuide(
    screen_class_name="DirlistingScreen",
    title="Directory listing",
    acces="Accueil -> Configuration detaillee -> Directory listing",
    definition=(
        "Deux sections sur le meme ecran : reglages d'affichage (theme CSS, header/readme) et "
        "CRUD des zones ou le listing de repertoire est actif."
    ),
    fields=(
        FieldGuide(
            label="Theme du CSS de base",
            definition="Palette de couleurs utilisee pour le CSS genere automatiquement du listing.",
            utilisation="5 themes disponibles (dont 'omega-base'). Valeur par defaut : omega-base.",
            action="Enregistre au clic sur 'Enregistrer les reglages'.",
            reaction="Aucun effet sans rechargement du service (automatique si actif).",
        ),
        FieldGuide(
            label="CSS externe",
            definition="URL optionnelle d'une feuille de style chargee EN PLUS du CSS de base (jamais a la place).",
            utilisation="Une URL/chemin, ex: /.assets/css/folder.css. Vide par defaut.",
            action="Enregistre avec les reglages.",
            reaction="Aucun effet sans rechargement du service.",
        ),
        FieldGuide(
            label="Afficher un fichier HEADER (oui/non) + nom du fichier",
            definition="Affiche le contenu d'un fichier texte en haut du listing, s'il existe dans le repertoire liste.",
            utilisation="oui/non ; nom de fichier par defaut : HEADER.txt.",
            action="Enregistre avec les reglages.",
            reaction="Aucun effet sans rechargement - absence du fichier sur disque : ignore silencieusement, jamais une erreur.",
        ),
        FieldGuide(
            label="Encoder le contenu HEADER (oui/non)",
            definition="Si oui, echappe le contenu comme texte pur ; si non, l'insere tel quel (HTML autorise).",
            utilisation="oui/non. Valeur par defaut : non (HTML tel quel).",
            action="Enregistre avec les reglages.",
            reaction="Aucun effet sans rechargement du service.",
        ),
        FieldGuide(
            label="Masquer le fichier HEADER dans la liste (oui/non)",
            definition="Retire ce fichier de la liste des entrees affichees (pour ne pas le voir apparaitre deux fois).",
            utilisation="oui/non. Valeur par defaut : oui.",
            action="Enregistre avec les reglages.",
            reaction="Aucun effet sans rechargement du service.",
        ),
        FieldGuide(
            label="README (memes 4 reglages que HEADER, affiche en bas du listing)",
            definition="Equivalent de HEADER, affiche apres la liste des fichiers plutot qu'avant.",
            utilisation="oui/non ; nom de fichier par defaut : README.txt.",
            action="Enregistre avec les reglages.",
            reaction="Aucun effet sans rechargement du service.",
        ),
        FieldGuide(
            label="Zones (table)",
            definition="Prefixes d'URL ou le listing de repertoire est propose quand aucun index n'existe.",
            utilisation="Un prefixe par ligne, doit commencer par '/'.",
            action="Ajouter/Supprimer une zone.",
            reaction="Aucun effet sans rechargement du service.",
        ),
    ),
    consequences=(
        "L'option dirlisting doit etre activee (ecran Options) pour que le listing apparaisse "
        "reellement. Toutes les modifications (reglages et zones) se rechargent a chaud."
    ),
    points_de_vigilance=(
        (
            "Les fichiers/dossiers commencant par un point restent masques du listing par la "
            "regle generique 'deny_hidden_files' (ecran Securite generique), independamment des "
            "reglages de cet ecran."
        ),
    ),
)

CACHE_SCREEN = ScreenGuide(
    screen_class_name="CacheScreen",
    title="Cache",
    acces="Accueil -> Configuration detaillee -> Cache",
    definition="Valeur Cache-Control par defaut, plus des regles specifiques par zone d'URL et par extension de fichier.",
    fields=(
        FieldGuide(
            label="Valeur par defaut (Cache-Control)",
            definition="En-tete Cache-Control envoye quand aucune regle de zone/extension ne s'applique.",
            utilisation=(
                "Directives usuelles combinables par virgule : no-cache, no-store, must-revalidate, "
                "private, public, max-age=<secondes>, immutable. Valeur par defaut : "
                "'no-cache, must-revalidate'."
            ),
            action="Enregistree au clic sur 'Enregistrer la valeur par defaut'.",
            reaction="Aucun effet sans rechargement du service (automatique si actif).",
        ),
        FieldGuide(
            label="Regles par zone",
            definition="Cache-Control specifique pour un prefixe d'URL donne.",
            utilisation="Un prefixe (ex: /static/) + une valeur Cache-Control.",
            action="Ajouter/Supprimer une regle de zone.",
            reaction="Aucun effet sans rechargement du service.",
        ),
        FieldGuide(
            label="Regles par extension",
            definition="Cache-Control specifique pour une extension de fichier donnee.",
            utilisation="Une extension (ex: .css, doit commencer par un point) + une valeur Cache-Control.",
            action="Ajouter/Supprimer une regle d'extension.",
            reaction="Aucun effet sans rechargement du service.",
        ),
    ),
    consequences=(
        "L'option cache doit etre activee (ecran Options). Toutes les modifications se "
        "rechargent a chaud."
    ),
)

ERROR_PAGES_SCREEN = ScreenGuide(
    screen_class_name="ErrorPagesScreen",
    title="Pages d'erreur",
    acces="Accueil -> Configuration detaillee -> Pages d'erreur",
    definition=(
        "Des pages HTML par defaut sont TOUJOURS servies pour toute reponse d'erreur (404, 403, "
        "500...), meme sans rien configurer ici. Cet ecran ne controle que la SURCHARGE "
        "personnalisee optionnelle."
    ),
    fields=(
        FieldGuide(
            label="Repertoire de surcharge",
            definition="Repertoire contenant des fichiers <statut>.html qui remplacent la page par defaut.",
            utilisation="Chemin relatif au projet. Valeur par defaut : webroot/.errors.",
            action="Enregistre au clic sur Enregistrer.",
            reaction=(
                "Si l'option error_pages est deja activee : rechargement du service necessaire "
                "(automatique si actif). Si l'option est desactivee : AUCUN EFFET tant qu'elle "
                "n'est pas activee depuis Options - un rechargement seul ne suffit pas."
            ),
        ),
    ),
    consequences=(
        "Le tableau des statuts geres indique 'Personnalisee: Oui' des qu'un fichier "
        "<statut>.html existe reellement dans le repertoire configure, meme si l'option "
        "error_pages reste desactivee - a ne pas confondre avec 'applique reellement'."
    ),
    points_de_vigilance=(
        (
            "Cas reel deja rencontre : un fichier 404.html correctement place n'avait aucun "
            "effet car l'option 'error_pages' n'etait pas activee separement dans Options - "
            "l'ecran l'indique desormais explicitement."
        ),
    ),
)

TRUSTED_PROXY_SCREEN = ScreenGuide(
    screen_class_name="TrustedProxyScreen",
    title="Proxies de confiance",
    acces="Accueil -> Configuration detaillee -> Proxies de confiance",
    definition=(
        "Declare les reseaux CIDR consideres comme des proxys de confiance (pour lire la vraie IP "
        "cliente derriere eux) et l'ordre de preference des en-tetes X-Forwarded-*."
    ),
    fields=(
        FieldGuide(
            label="Reseaux de confiance (CIDR)",
            definition="Reseaux dont l'adresse source est consideree comme un proxy legitime.",
            utilisation="Notation CIDR, ex: 10.0.0.0/8. Verifie reellement au moment de l'ajout.",
            action="Ajouter/Supprimer un reseau.",
            reaction="Aucun effet sans rechargement du service (automatique si actif).",
        ),
        FieldGuide(
            label="En-tetes preferes (ordre)",
            definition="Ordre de preference des en-tetes utilises pour retrouver l'IP cliente reelle.",
            utilisation="Liste separee par des virgules, ex: Forwarded, X-Forwarded-For. Ne peut pas etre vide.",
            action="Enregistre au clic sur 'Enregistrer les en-tetes'.",
            reaction="Aucun effet sans rechargement du service.",
        ),
    ),
    consequences=(
        "L'option trusted_proxy doit etre activee (ecran Options). Toutes les modifications se "
        "rechargent a chaud."
    ),
    points_de_vigilance=(
        (
            "Ne jamais faire confiance a X-Forwarded-For sans restreindre les reseaux sources - "
            "n'importe quel client pourrait sinon usurper une IP arbitraire."
        ),
    ),
)

REVERSE_PROXY_SCREEN = ScreenGuide(
    screen_class_name="ReverseProxyScreen",
    title="Reverse Proxy",
    acces="Accueil -> Configuration detaillee -> Reverse Proxy",
    definition=(
        "CRUD de zones de relais sortant : OMEGA-SERV agit lui-meme comme reverse proxy vers un "
        "ou plusieurs backends (repartition de charge round-robin, TLS amont optionnel, WebSocket)."
    ),
    fields=(
        FieldGuide(
            label="Prefixe URL",
            definition="Le prefixe d'URL relaye vers les upstreams.",
            utilisation="Doit commencer par '/', ex: /api/.",
            action="Ajoute/modifie une zone.",
            reaction="Aucun effet sans rechargement (une fois l'option deja active une premiere fois).",
        ),
        FieldGuide(
            label="Upstreams",
            definition="Backends vers lesquels la requete est relayee, en round-robin si plusieurs.",
            utilisation="Liste 'host:port' separee par des virgules, prefixe 'https://' optionnel par upstream.",
            action="Ajoute/modifie une zone.",
            reaction="Aucun effet sans rechargement.",
        ),
        FieldGuide(
            label="Delai de connexion / Delai de lecture",
            definition="Delais reseau appliques a la connexion vers l'upstream et a la lecture de sa reponse.",
            utilisation="Nombres en secondes.",
            action="Ajoute/modifie une zone.",
            reaction="Aucun effet sans rechargement.",
        ),
        FieldGuide(
            label="Preserver le Host du client (oui/non)",
            definition="Transmet l'en-tete Host original du client a l'upstream plutot que le sien.",
            utilisation="oui/non.",
            action="Ajoute/modifie une zone.",
            reaction="Aucun effet sans rechargement.",
        ),
        FieldGuide(
            label="Verifier le certificat des upstreams HTTPS (oui/non)",
            definition="Verifie ou non le certificat TLS presente par un upstream HTTPS.",
            utilisation="oui/non. DANGEREUX si non (attaque MITM possible) - defaut sur, jamais desactive silencieusement.",
            action="Ajoute/modifie une zone.",
            reaction="Aucun effet sans rechargement.",
        ),
        FieldGuide(
            label="Autoriser Upgrade: websocket (oui/non)",
            definition="Autorise la mise a niveau WebSocket sur cette zone.",
            utilisation="oui/non. Une fois le tube etabli, un seul upstream reste fige pour sa duree de vie.",
            action="Ajoute/modifie une zone.",
            reaction="Aucun effet sans rechargement.",
        ),
    ),
    consequences=(
        "La PREMIERE activation de l'option reverse_proxy exige un REDEMARRAGE COMPLET (le "
        "client HTTP n'est construit qu'au demarrage). Une fois deja active, modifier les zones "
        "ici ne demande plus qu'un simple rechargement."
    ),
    points_de_vigilance=(
        (
            "A ne jamais confondre avec le reglage TLS 'mode = behind_proxy' (OMEGA-SERV "
            "DERRIERE un proxy) - ici, c'est OMEGA-SERV qui EST le proxy vers d'autres backends."
        ),
    ),
)
