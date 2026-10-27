"""Fiches guide : Alias, Redirections, Rewrites, Directory listing,
Cache, Pages d'erreur, Proxies de confiance (plan guide d'aide, Phase 3)."""
from __future__ import annotations

from omega_serv.core.i18n import _
from omega_serv.interfaces.tui.guide.model import FieldGuide, ScreenGuide

ALIASES_SCREEN = ScreenGuide(
    screen_class_name="AliasesScreen",
    title=_("Alias"),
    acces=_("Accueil -> Configuration détaillée -> Alias"),
    definition=_("CRUD d'alias : sert un préfixe d'URL depuis un chemin cible, y compris hors du webroot."),
    fields=(
        FieldGuide(
            label=_("Préfixe URL"),
            definition=_("Le préfixe d'URL à rediriger vers un autre emplacement disque."),
            utilisation=_("Doit commencer par '/', ex: /media/."),
            action=_("Ajoute/modifie un alias."),
            reaction=_("Aucun effet sans rechargement du service (automatique si actif)."),
        ),
        FieldGuide(
            label=_("Chemin cible"),
            definition=_("L'emplacement disque réellement servi pour ce préfixe."),
            utilisation=_("Chemin relatif au projet, ex: webroot/media, ou un chemin hors webroot."),
            action=_("Ajoute/modifie un alias."),
            reaction=_("Aucun effet sans rechargement du service."),
        ),
        FieldGuide(
            label=_("Autoriser hors webroot (oui/non)"),
            definition=_("Autorise explicitement une cible située en dehors du webroot habituel."),
            utilisation=_("oui ou non. Valeur par défaut : non."),
            action=_("Ajoute/modifie un alias."),
            reaction=_("Aucun effet sans rechargement du service."),
        ),
    ),
    consequences=(
        _("L'option aliases doit être activée (écran Options) pour que ces alias soient "
        "réellement appliqués. Toutes les modifications se rechargent à chaud.")
    ),
    points_de_vigilance=(
        (
            _("Directory listing et Cache se configurent par ZONE (préfixe d'URL), jamais par "
            "dossier cible : un alias '/media/' pointant sur 'webroot/photos/' a besoin de sa "
            "PROPRE zone '/media/' sur ces écrans - une zone déjà créée pour '/photos/' (le nom "
            "du dossier réel) ne s'applique jamais à l'alias, même si les deux mènent au même "
            "contenu sur le disque.")
        ),
    ),
)

REDIRECTS_SCREEN = ScreenGuide(
    screen_class_name="RedirectsScreen",
    title=_("Redirections"),
    acces=_("Accueil -> Configuration détaillée -> Redirections"),
    definition=_("CRUD de redirections HTTP (réponse 3xx avec en-tête Location)."),
    fields=(
        FieldGuide(
            label=_("Préfixe URL"),
            definition=_("Le préfixe d'URL qui déclenche la redirection."),
            utilisation=_("Doit commencer par '/', ex: /old/."),
            action=_("Ajoute/modifie une redirection."),
            reaction=_("Aucun effet sans rechargement du service."),
        ),
        FieldGuide(
            label=_("Destination"),
            definition=_("L'URL ou le chemin envoyé dans l'en-tête Location de la réponse."),
            utilisation=_("Chaîne libre, ex: /new/."),
            action=_("Ajoute/modifie une redirection."),
            reaction=_("Aucun effet sans rechargement du service."),
        ),
        FieldGuide(
            label=_("Code"),
            definition=_("Le code de statut HTTP de redirection utilisé."),
            utilisation=_("301, 302, 307 ou 308. Valeur par défaut : 302."),
            action=_("Ajoute/modifie une redirection."),
            reaction=_("Aucun effet sans rechargement du service."),
        ),
    ),
    consequences=(
        _("L'option redirects doit être activée (écran Options). Toutes les modifications se "
        "rechargent à chaud.")
    ),
)

REWRITES_SCREEN = ScreenGuide(
    screen_class_name="RewritesScreen",
    title=_("Rewrites"),
    acces=_("Accueil -> Configuration détaillée -> Rewrites"),
    definition=(
        _("CRUD de réécritures d'URL internes - remplace un préfixe par un autre AVANT le "
        "traitement de la requête, sans jamais renvoyer de redirection au client (invisible côté navigateur).")
    ),
    fields=(
        FieldGuide(
            label=_("Préfixe recherche"),
            definition=_("Le préfixe d'URL à reconnaître."),
            utilisation=_("Doit commencer par '/', ex: /old/."),
            action=_("Ajoute/modifie un rewrite."),
            reaction=_("Aucun effet sans rechargement du service."),
        ),
        FieldGuide(
            label=_("Préfixe remplacement"),
            definition=_("Le préfixe qui remplace le préfixe recherche."),
            utilisation=_("Chaîne non vide, ex: /new/."),
            action=_("Ajoute/modifie un rewrite."),
            reaction=_("Aucun effet sans rechargement du service."),
        ),
    ),
    consequences=(
        _("L'option rewrites doit être activée (écran Options). Toutes les modifications se "
        "rechargent à chaud.")
    ),
    points_de_vigilance=(
        (
            _("Distinct d'une redirection : le client ne voit jamais l'URL rewritee, "
            "contrairement à une redirection qui change l'URL affichée dans le navigateur.")
        ),
    ),
)

DIRLISTING_SCREEN = ScreenGuide(
    screen_class_name="DirlistingScreen",
    title=_("Directory listing"),
    acces=_("Accueil -> Configuration détaillée -> Directory listing"),
    definition=(
        _("Deux sections sur le même écran : réglages d'affichage (thème CSS, header/readme) et "
        "CRUD des zones où le listing de répertoire est actif.")
    ),
    fields=(
        FieldGuide(
            label=_("Thème du CSS de base"),
            definition=_("Palette de couleurs utilisée pour le CSS généré automatiquement du listing."),
            utilisation=_("5 thèmes disponibles (dont 'omega-base'). Valeur par défaut : omega-base."),
            action=_("Enregistre au clic sur 'Enregistrer les réglages'."),
            reaction=_("Aucun effet sans rechargement du service (automatique si actif)."),
        ),
        FieldGuide(
            label=_("CSS externe"),
            definition=_("URL optionnelle d'une feuille de style chargée EN PLUS du CSS de base (jamais à la place)."),
            utilisation=_("Une URL/chemin, ex: /.assets/css/folder.css. Vide par défaut."),
            action=_("Enregistre avec les réglages."),
            reaction=_("Aucun effet sans rechargement du service."),
        ),
        FieldGuide(
            label=_("Afficher un fichier HEADER (oui/non) + nom du fichier"),
            definition=_("Affiche le contenu d'un fichier texte en haut du listing, s'il existe dans le répertoire liste."),
            utilisation=_("oui/non ; nom de fichier par défaut : HEADER.txt."),
            action=_("Enregistre avec les réglages."),
            reaction=_("Aucun effet sans rechargement - absence du fichier sur disque : ignore silencieusement, jamais une erreur."),
        ),
        FieldGuide(
            label=_("Encoder le contenu HEADER (oui/non)"),
            definition=_("Si oui, échappe le contenu comme texte pur ; si non, l'insère tel quel (HTML autorisé)."),
            utilisation=_("oui/non. Valeur par défaut : non (HTML tel quel)."),
            action=_("Enregistre avec les réglages."),
            reaction=_("Aucun effet sans rechargement du service."),
        ),
        FieldGuide(
            label=_("Masquer le fichier HEADER dans la liste (oui/non)"),
            definition=_("Retire ce fichier de la liste des entrées affichées (pour ne pas le voir apparaître deux fois)."),
            utilisation=_("oui/non. Valeur par défaut : oui."),
            action=_("Enregistre avec les réglages."),
            reaction=_("Aucun effet sans rechargement du service."),
        ),
        FieldGuide(
            label=_("README (mêmes 4 réglages que HEADER, affiché en bas du listing)"),
            definition=_("Équivalent de HEADER, affiché après la liste des fichiers plutôt qu'avant."),
            utilisation=_("oui/non ; nom de fichier par défaut : README.txt."),
            action=_("Enregistre avec les réglages."),
            reaction=_("Aucun effet sans rechargement du service."),
        ),
        FieldGuide(
            label=_("Zones (table)"),
            definition=(
                _("Préfixes d'URL où le listing de répertoire est proposé quand aucun index n'existe. "
                "Un préfixe est une URL TELLE QUE LE NAVIGATEUR LA VOIT, jamais un chemin ou un nom "
                "de dossier réel sur le disque.")
            ),
            utilisation=_("Un préfixe par ligne, doit commencer par '/'."),
            action=_("Ajouter/Supprimer une zone."),
            reaction=_("Aucun effet sans rechargement du service."),
        ),
    ),
    consequences=(
        _("L'option dirlisting doit être activée (écran Options) pour que le listing apparaisse "
        "réellement. Toutes les modifications (réglages et zones) se rechargent à chaud.")
    ),
    points_de_vigilance=(
        (
            _("Les fichiers/dossiers commençant par un point restent masques du listing par la "
            "règle générique 'deny_hidden_files' (écran Sécurité générique), indépendamment des "
            "réglages de cet écran.")
        ),
        (
            _("Servir un MÊME dossier par deux URLs différentes (ex: directement en '/mondossier/' "
            "ET via un alias '/autre-nom/' pointant sur ce même dossier, écran Alias) exige DEUX "
            "zones ici, une par URL - le listing ne 'suit' jamais le dossier réel, seulement le "
            "préfixe d'URL exact tapé par le visiteur. Ajouter uniquement '/mondossier/' n'active "
            "jamais le listing sur '/autre-nom/', même si les deux mènent au même contenu sur le "
            "disque.")
        ),
    ),
)

CACHE_SCREEN = ScreenGuide(
    screen_class_name="CacheScreen",
    title=_("Cache"),
    acces=_("Accueil -> Configuration détaillée -> Cache"),
    definition=_("Valeur Cache-Control par défaut, plus des règles spécifiques par zone d'URL et par extension de fichier."),
    fields=(
        FieldGuide(
            label=_("Valeur par défaut (Cache-Control)"),
            definition=_("En-tête Cache-Control envoyé quand aucune règle de zone/extension ne s'applique."),
            utilisation=(
                _("Directives usuelles combinables par virgule : no-cache, no-store, must-revalidate, "
                "private, public, max-age=<secondes>, immutable. Valeur par défaut : "
                "'no-cache, must-revalidate'.")
            ),
            action=_("Enregistrée au clic sur 'Enregistrer la valeur par défaut'."),
            reaction=_("Aucun effet sans rechargement du service (automatique si actif)."),
        ),
        FieldGuide(
            label=_("Règles par zone"),
            definition=_("Cache-Control spécifique pour un préfixe d'URL donné."),
            utilisation=_("Un préfixe (ex: /static/) + une valeur Cache-Control."),
            action=_("Ajouter/Supprimer une règle de zone."),
            reaction=_("Aucun effet sans rechargement du service."),
        ),
        FieldGuide(
            label=_("Règles par extension"),
            definition=(
                _("Cache-Control spécifique pour une extension de fichier donnée. Règles fournies par "
                "défaut tant qu'aucune n'est modifiée : images et médias max-age=86400 (1 jour), polices "
                "max-age=604800 (7 jours), CSS et JS max-age=3600 (1 heure) - une page riche en images "
                "n'est plus redemandée à chaque visite. Toute modification enregistre votre propre liste, "
                "qui remplace celle-ci.")
            ),
            utilisation=_("Une extension (ex: .css, doit commencer par un point) + une valeur Cache-Control."),
            action=_("Ajouter/Supprimer une règle d'extension."),
            reaction=_("Aucun effet sans rechargement du service."),
        ),
    ),
    consequences=(
        _("L'option cache doit être activée (écran Options). Toutes les modifications se "
        "rechargent à chaud. Indépendamment de cette option, chaque fichier statique porte un ETag "
        "et une date de modification : un rechargement ne retélécharge que ce qui a changé "
        "(réponse 304), et un téléchargement interrompu ou une vidéo peut reprendre en cours de "
        "fichier (Range).")
    ),
)

ERROR_PAGES_SCREEN = ScreenGuide(
    screen_class_name="ErrorPagesScreen",
    title=_("Pages d'erreur"),
    acces=_("Accueil -> Configuration détaillée -> Pages d'erreur"),
    definition=(
        _("Des pages HTML par défaut sont TOUJOURS servies pour toute réponse d'erreur (404, 403, "
        "500...), même sans rien configurer ici. Cet écran ne contrôle que la SURCHARGE "
        "personnalisée optionnelle.")
    ),
    fields=(
        FieldGuide(
            label=_("Langue des pages visiteurs (pages d'erreur et listing de dossier)"),
            definition=_("Langue des pages d'erreur et du listing de dossier vus par les visiteurs du site - jamais celle de votre interface."),
            utilisation=_("Une langue de la liste. Valeur par défaut : Français."),
            action=_("Enregistrée dès le choix dans la liste."),
            reaction=(
                _("Nécessite un REDÉMARRAGE COMPLET du serveur (proposé aussitôt si un service est "
                "détecté) - un simple rechargement ne change pas la langue des pages.")
            ),
        ),
        FieldGuide(
            label=_("Répertoire de surcharge"),
            definition=_("Répertoire contenant des fichiers <statut>.html qui remplacent la page par défaut."),
            utilisation=_("Chemin relatif au projet. Valeur par défaut : webroot/.errors."),
            action=_("Enregistre au clic sur Enregistrer."),
            reaction=(
                _("Si l'option error_pages est déjà activée : rechargement du service nécessaire "
                "(automatique si actif). Si l'option est désactivée : AUCUN EFFET tant qu'elle "
                "n'est pas activée depuis Options - un rechargement seul ne suffit pas.")
            ),
        ),
    ),
    consequences=(
        _("Le tableau des statuts gérés indique 'Personnalisée: Oui' dès qu'un fichier "
        "<statut>.html existe réellement dans le répertoire configuré, même si l'option "
        "error_pages reste désactivée - à ne pas confondre avec 'appliqué réellement'.")
    ),
    points_de_vigilance=(
        (
            _("Cas réel déjà rencontré : un fichier 404.html correctement place n'avait aucun "
            "effet car l'option 'error_pages' n'était pas activée séparément dans Options - "
            "l'écran l'indique désormais explicitement.")
        ),
    ),
)

TRUSTED_PROXY_SCREEN = ScreenGuide(
    screen_class_name="TrustedProxyScreen",
    title=_("Proxies de confiance"),
    acces=_("Accueil -> Configuration détaillée -> Proxies de confiance"),
    definition=(
        _("Déclare les réseaux CIDR considérés comme des proxys de confiance (pour lire la vraie IP "
        "cliente derrière eux) et l'ordre de préférence des en-têtes X-Forwarded-*.")
    ),
    fields=(
        FieldGuide(
            label=_("Réseaux de confiance (CIDR)"),
            definition=_("Réseaux dont l'adresse source est considérée comme un proxy légitime."),
            utilisation=(
                _("Notation CIDR, ex: 127.0.0.1/32 pour tailscale serve ou un reverse proxy local. "
                "Uniquement le proxy placé devant omega-serv, jamais vos propres appareils : une "
                "adresse mise ici n'est pas exemptée de bannissement (réglage never_auto_block). "
                "Vérifié réellement au moment de l'ajout.")
            ),
            action=_("Ajouter/Supprimer un réseau."),
            reaction=_("Aucun effet sans rechargement du service (automatique si actif)."),
        ),
        FieldGuide(
            label=_("En-têtes préférés (ordre)"),
            definition=_("Ordre de préférence des en-têtes utilisés pour retrouver l'IP cliente réelle."),
            utilisation=(
                _("Liste séparée par des virgules, essayée dans l'ordre : X-Forwarded-For (tailscale "
                "serve, nginx, Caddy, Apache), Forwarded (RFC 7239), X-Real-IP. Ne peut pas être vide : "
                "pour ne lire aucun en-tête, désactiver l'option trusted_proxy. Un nom d'en-tête "
                "invalide est refusé.")
            ),
            action=_("Enregistre au clic sur 'Enregistrer les en-têtes'."),
            reaction=_("Aucun effet sans rechargement du service."),
        ),
    ),
    consequences=(
        _("L'option trusted_proxy doit être activée (écran Options). Toutes les modifications se "
        "rechargent à chaud.")
    ),
    points_de_vigilance=(
        (
            _("Ne jamais faire confiance à X-Forwarded-For sans restreindre les réseaux sources - "
            "n'importe quel client pourrait sinon usurper une IP arbitraire.")
        ),
    ),
)

REVERSE_PROXY_SCREEN = ScreenGuide(
    screen_class_name="ReverseProxyScreen",
    title=_("Reverse Proxy"),
    acces=_("Accueil -> Configuration détaillée -> Reverse Proxy"),
    definition=(
        _("CRUD de zones de relais sortant : OMEGA-SERV agit lui-même comme reverse proxy vers un "
        "ou plusieurs backends (répartition de charge round-robin, TLS amont optionnel, WebSocket).")
    ),
    fields=(
        FieldGuide(
            label=_("Préfixe URL"),
            definition=_("Le préfixe d'URL relayé vers les upstreams."),
            utilisation=_("Doit commencer par '/', ex: /api/."),
            action=_("Ajoute/modifie une zone."),
            reaction=_("Aucun effet sans rechargement (une fois l'option déjà activé une première fois)."),
        ),
        FieldGuide(
            label=_("Upstreams"),
            definition=_("Backends vers lesquels la requête est relayée, en round-robin si plusieurs."),
            utilisation=_("Liste 'host:port' séparée par des virgules, préfixe 'https://' optionnel par upstream."),
            action=_("Ajoute/modifie une zone."),
            reaction=_("Aucun effet sans rechargement."),
        ),
        FieldGuide(
            label=_("Délai de connexion / Délai de lecture"),
            definition=_("Délais réseau appliqués à la connexion vers l'upstream et à la lecture de sa réponse."),
            utilisation=_("Nombres en secondes."),
            action=_("Ajoute/modifie une zone."),
            reaction=_("Aucun effet sans rechargement."),
        ),
        FieldGuide(
            label=_("Préserver le Host du client (oui/non)"),
            definition=_("Transmet l'en-tête Host original du client à l'upstream plutôt que le sien."),
            utilisation=_("oui/non."),
            action=_("Ajoute/modifie une zone."),
            reaction=_("Aucun effet sans rechargement."),
        ),
        FieldGuide(
            label=_("Vérifier le certificat des upstreams HTTPS (oui/non)"),
            definition=_("Vérifie ou non le certificat TLS présenté par un upstream HTTPS."),
            utilisation=_("oui/non. DANGEREUX si non (attaque MITM possible) - défaut sur, jamais désactivé silencieusement."),
            action=_("Ajoute/modifie une zone."),
            reaction=_("Aucun effet sans rechargement."),
        ),
        FieldGuide(
            label=_("Autoriser Upgrade: websocket (oui/non)"),
            definition=_("Autorise la mise à niveau WebSocket sur cette zone."),
            utilisation=_("oui/non. Une fois le tube établi, un seul upstream reste figé pour sa durée de vie."),
            action=_("Ajoute/modifie une zone."),
            reaction=_("Aucun effet sans rechargement."),
        ),
    ),
    consequences=(
        _("La PREMIÈRE activation de l'option reverse_proxy exige un REDÉMARRAGE COMPLET (le "
        "client HTTP n'est construit qu'au démarrage). Une fois déjà activé, modifier les zones "
        "ici ne demande plus qu'un simple rechargement. Le bouton 'État en direct' (zone "
        "sélectionnée) ouvre un écran séparé pour consulter/forcer l'état de santé de chaque "
        "backend du serveur RÉELLEMENT en cours d'exécution - voir sa fiche dédiée.")
    ),
    points_de_vigilance=(
        (
            _("À ne jamais confondre avec le réglage TLS 'mode = behind_proxy' (OMEGA-SERV "
            "DERRIÈRE un proxy) - ici, c'est OMEGA-SERV qui EST le proxy vers d'autres backends.")
        ),
    ),
)

REVERSE_PROXY_CACHE_SCREEN = ScreenGuide(
    screen_class_name="ReverseProxyCacheScreen",
    title=_("Cache du reverse proxy"),
    acces=_("Accueil -> Configuration détaillée -> Cache du reverse proxy"),
    definition=(
        _("Supervision et purge du cache des réponses proxiées (DISTINCT du cache fichiers "
        "statiques, écran 'Cache') : nombre d'entrées et taille occupée sur disque, lus "
        "directement dans var/cache/reverse_proxy/, que le serveur soit démarré ou non, plus un "
        "ratio hits/miss EN DIRECT (interroge le serveur réellement en cours d'exécution via "
        "/.omega-serv-admin/cache-stats - affiche 'indisponible' si le serveur est éteint ou "
        "injoignable, sans jamais bloquer le reste de l'écran).")
    ),
    fields=(
        FieldGuide(
            label=_("Plafond (Mo)"),
            definition=_("Taille maximale occupée sur disque par le cache avant éviction des entrées les plus anciennes."),
            utilisation=_("Nombre entier >= 1, en megaoctets."),
            action=_("Modifier le plafond."),
            reaction=_("Enregistre dans la configuration ; s'applique à la prochaine écriture en cache (éviction immédiate non déclenchée par ce seul changement)."),
        ),
        FieldGuide(
            label=_("Purger une zone"),
            definition=_("Supprime toutes les entrées de cache pour un préfixe de zone donné."),
            utilisation=_("Saisir le préfixe exact de la zone, ex: /api/."),
            action=_("Confirme puis purge."),
            reaction=_("Entrées supprimées du disque immédiatement, y compris si le serveur tourne (il relira à froid)."),
        ),
        FieldGuide(
            label=_("Purger tout"),
            definition=_("Supprime toutes les entrées de cache, toutes zones confondues."),
            utilisation=_("Action destructive, confirmation demandée."),
            action=_("Confirme puis purge."),
            reaction=_("Cache entièrement vide immédiatement."),
        ),
    ),
    consequences=(
        _("Activation/parametres du cache (active, TTL, respect des en-têtes Cache-Control de "
        "l'upstream, autorisation Set-Cookie) se configurent sur l'écran Reverse Proxy, zone par "
        "zone - cet écran-ci ne fait que superviser et purger ce qui existe déjà sur disque.")
    ),
    points_de_vigilance=(
        (
            _("Le ratio hits/miss est cumulé EN MÉMOIRE depuis le dernier démarrage COMPLET du "
            "serveur (jamais persiste) - un simple rechargement (SIGHUP) ne le remet jamais à "
            "zéro. Nécessite trusted_proxy actif avec 127.0.0.1 dans ses réseaux de confiance, "
            "sinon affiche 'indisponible'. Le diagnostic PAR REQUÊTE reste l'en-tête de réponse "
            "X-Omega-Cache (HIT/MISS/BYPASS), visible via les outils du navigateur ou 'curl -I'.")
        ),
    ),
)

REVERSE_PROXY_UPSTREAM_STATUS_SCREEN = ScreenGuide(
    screen_class_name="ReverseProxyUpstreamStatusScreen",
    title=_("État en direct des backends"),
    acces=_("Accueil -> Configuration détaillée -> Reverse Proxy -> sélectionner une zone -> État en direct"),
    definition=(
        _("Interroge le serveur RÉELLEMENT en cours d'exécution (jamais la configuration sur "
        "disque) pour afficher l'état actuel de chaque backend d'une zone (up/down/draining/"
        "maintenance) et permettre de forcer DRAINING ou MAINTENANCE à chaud, via la route "
        "/.omega-serv-admin/health - un vrai appel HTTP local, jamais une modification en "
        "mémoire de cet écran (qui ne tourne pas dans le processus serveur).")
    ),
    fields=(
        FieldGuide(
            label=_("Mettre en DRAINING"),
            definition=_("Exclut le backend sélectionné des NOUVEAUX choix sans le marquer en panne."),
            utilisation=_("Sélectionner une ligne puis cliquer."),
            action=_("Appel HTTP immédiat vers le serveur en cours."),
            reaction=_("Statut visible immédiatement après actualisation ; jamais écrit dans la configuration."),
        ),
        FieldGuide(
            label=_("Mettre en MAINTENANCE"),
            definition=_("Même exclusion que DRAINING, intention opérateur distincte (intervention planifiée)."),
            utilisation=_("Sélectionner une ligne puis cliquer."),
            action=_("Appel HTTP immédiat vers le serveur en cours."),
            reaction=_("Statut visible immédiatement après actualisation ; jamais écrit dans la configuration."),
        ),
        FieldGuide(
            label=_("Revenir à l'automatique"),
            definition=_("Annule DRAINING/MAINTENANCE - l'état redevient dérivé de la santé réelle observée (up/down)."),
            utilisation=_("Sélectionner une ligne puis cliquer."),
            action=_("Appel HTTP immédiat vers le serveur en cours."),
            reaction=(
                _("Ne force jamais 'up' aveuglément : un backend réellement en panne pendant la "
                "maintenance reste 'down' une fois celle-ci levée.")
            ),
        ),
    ),
    consequences=(
        _("DRAINING/MAINTENANCE restent ÉPHÉMÈRES : jamais écrits dans la configuration, jamais "
        "persistés - seul un REDÉMARRAGE COMPLET du serveur les efface (un simple rechargement "
        "SIGHUP les conserve). 'DOWN' reste toujours dérivé automatiquement de la santé "
        "observée, jamais affecté par cet écran.")
    ),
    points_de_vigilance=(
        (
            _("Nécessite trusted_proxy actif avec 127.0.0.1 dans ses réseaux de confiance - sinon "
            "l'écran affiche 'serveur injoignable', jamais une erreur bloquante.")
        ),
        (
            _("Un serveur éteint rend cet écran entièrement indisponible (contrairement aux "
            "statistiques disque du cache, lisibles à froid) : il interroge exclusivement le "
            "PROCESSUS en cours, jamais la configuration sur disque.")
        ),
    ),
)
