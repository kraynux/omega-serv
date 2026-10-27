"""Fiches guide : Active Securite - menu + 5 Active Defense + 4 WAF + 2
modaux (plan guide d'aide, Phase 8)."""
from __future__ import annotations

from omega_serv.core.i18n import _
from omega_serv.interfaces.tui.guide.model import FieldGuide, ScreenGuide

ACTIVE_DEFENSE_MENU_SCREEN = ScreenGuide(
    screen_class_name="ActiveDefenseMenuScreen",
    title=_("Active Sécurité (menu)"),
    acces=_("Accueil -> Active Sécurité"),
    definition=(
        _("Regroupe deux blocs d'état opérationnel (change en continu, pas des formulaires de "
        "réglages statiques) : Active Defense (menaces/incidents/leurres) et WAF (mode/packs/blocklist).")
    ),
    fields=(),
    consequences=_("Aucune - purement navigation."),
    points_de_vigilance=(
        (
            _("Si un avertissement de groupe système apparaît en haut de cet écran, reconnectez "
            "votre session avant d'utiliser les sous-écrans - sinon ils resteront en erreur d'accès.")
        ),
        (
            _("Activer l'option 'active_defense' (menu Options) ne suffit PAS à lui seul - voir la "
            "fiche 'Active Defense - État' et la FAQ 'Active Defense ne détecte jamais rien'.")
        ),
    ),
)

ACTIVE_DEFENSE_STATUS_SCREEN = ScreenGuide(
    screen_class_name="ActiveDefenseStatusScreen",
    title=_("Active Defense - État"),
    acces=_("Accueil -> Active Sécurité -> État (bloc Active Defense)"),
    definition=_("Vue d'ensemble en lecture seule : mode, état du mode guerre, état de la deception, nombre de sources suivies."),
    fields=(),
    consequences=(
        _("Purement consultatif - mais la ligne 'Mode guerre' affichée ici est le seul endroit où "
        "vérifier le VRAI interrupteur qui déclenche quoi que ce soit (voir points de vigilance).")
    ),
    points_de_vigilance=(
        _("L'activation de l'option active_defense se fait dans le menu Options, jamais ici."),
        (
            _("PIÈGE RÉEL VÉRIFIÉ DANS LE CODE : activer l'option 'active_defense' seule ne "
            "déclenche RIEN. Un second interrupteur, `war_mode.enabled` (Active Defense - "
            "Réglages), vaut FALSE par défaut. Tant qu'il reste à false, les écrans Menaces/"
            "Incidents/Leurres restent fonctionnels mais ne se peuplent jamais, même avec un "
            "trafic hostile réel.")
        ),
        (
            _("Une fois `war_mode.enabled=true`, tout devient automatique et déterministe, sans "
            "aucune intervention manuelle : chaque décision WAF déjà calculée alimente un score "
            "cumulé par source (IP + User-Agent hache, avec décroissance dans le temps), qui "
            "franchit des seuils configurables (normal/suspicious/hostile/contained) déclenchant "
            "des actions automatiques (redirection vers un leurre, journalisation enrichie, "
            "ralentissement, création d'incident).")
        ),
    ),
)

ACTIVE_DEFENSE_SETTINGS_SCREEN = ScreenGuide(
    screen_class_name="ActiveDefenseSettingsScreen",
    title=_("Active Defense - Réglages"),
    acces=_("Accueil -> Active Sécurité -> Réglages (bloc Active Defense)"),
    definition=(
        _("Configure l'intégralité d'Active Defense (mode guerre, deception/leurres, IoC, "
        "stockage, journalisation) - AUCUNE édition manuelle de config/omega-serve.json n'est "
        "plus nécessaire pour ces réglages.")
    ),
    fields=(
        FieldGuide(
            label=_("Mode"),
            definition=_("Mode global d'Active Defense."),
            utilisation=_("monitor (observe uniquement) ou enforce. Valeur par défaut : monitor."),
            action=_("Enregistre au clic sur Enregistrer, après validation."),
            reaction=_("REDÉMARRAGE COMPLET toujours nécessaire - active_defense n'est jamais rechargé à chaud."),
        ),
        FieldGuide(
            label=_("Mode guerre actif (war_mode.enabled)"),
            definition=_("LE VRAI INTERRUPTEUR qui déclenche l'observation et les actions automatiques."),
            utilisation=_("oui/non. Valeur par défaut : non - RIEN ne se déclenche tant qu'il reste à 'non'."),
            action=_("Enregistre avec le reste des réglages généraux."),
            reaction=_("REDÉMARRAGE COMPLET toujours nécessaire."),
        ),
        FieldGuide(
            label=_("Portée / Actions autorisées / Seuils / Ralentissement / Limite de requêtes"),
            definition=_("Réglages fins du mode guerre : à qui s'appliquent les actions, lesquelles, à quel score, et leurs paramètres."),
            utilisation=(
                _("Portée : source/instance. Actions : liste parmi observe, enrich_log, delay, "
                "rate_limit, redirect_to_decoy, create_incident, export_ioc. Seuils : 4 entiers "
                "croissants (suspect <= hostile <= incident, confine >= hostile). Ralentissement "
                "et limite de requêtes : bornes en millisecondes/secondes.")
            ),
            action=_("Valides par les mêmes règles que le domaine (`validate_active_defense_config`) avant tout enregistrement."),
            reaction=_("REDÉMARRAGE COMPLET toujours nécessaire."),
        ),
        FieldGuide(
            label=_("Deception (actif, comportement par défaut, durée de vie d'une affectation)"),
            definition=_("Active ou non le routage vers des leurres, et ce qui se passe si aucun profil ne correspond à l'attaque."),
            utilisation=_("actif : oui/non. Comportement : pass_through (laisse passer) ou reject."),
            action=_("Enregistre avec le reste des réglages généraux."),
            reaction=_("REDÉMARRAGE COMPLET toujours nécessaire."),
        ),
        FieldGuide(
            label=_("Profils de leurre (table)"),
            definition=_("Associe une classe d'attaque à un niveau d'isolation - le premier profil actif qui correspond est utilisé."),
            utilisation=(
                _("Nom : si Isolation = fixture, DOIT être exactement fake_admin, fake_cms, "
                "fake_api ou fake_secrets (les 4 seules fixtures réellement implémentées) - "
                "tout autre nom fait que le leurre ne se déclenche JAMAIS, sans aucune erreur "
                "visible (bloqué désormais à l'enregistrement par validate_active_defense_config). "
                "Libre si Isolation = proxy. "
                "Classes d'attaque visées (séparées par virgules) : scan (sondage d'URLs/ports), "
                "credential_stuffing (essais massifs de mots de passe), sqli (injection SQL), "
                "xss (script injecté), path_traversal (ex : ../../etc/passwd), upload_probe "
                "(upload de fichier suspect), api_probe (sondage d'endpoints /api/...), unknown "
                "(tout le reste, filet de sécurité). Exemple concret : un profil "
                "fake_admin avec scan,credential_stuffing intercepte les scanners et les tentatives "
                "de bruteforce de login. Isolation : fixture (simulation interne, rapide, sans "
                "risque) ou proxy (redirigé vers un vrai serveur isolé que vous faites tourner, "
                "voir Zones de leurre ci-dessous). Zone de leurre associée : requise si Isolation "
                "= proxy, doit correspondre à un nom de la table Zones de leurre.")
            ),
            action=_("Ajouter/Supprimer un profil."),
            reaction=_("REDÉMARRAGE COMPLET toujours nécessaire."),
        ),
        FieldGuide(
            label=_("Zones de leurre (table, Niveau 2)"),
            definition=_("Backends réellement isolés vers lesquels un profil 'proxy' peut rediriger - jamais confondues avec les zones de reverse_proxy de production."),
            utilisation=(
                _("Nom : un simple identifiant (pas une URL, pas un dossier) référence depuis un "
                "profil de leurre en Isolation = proxy. Upstreams (host:port, séparés par "
                "virgules) : adresse(s) d'un serveur DÉJÀ EN COURS D'EXÉCUTION que vous "
                "contrôlez - rien n'est créé automatiquement ici, aucun dossier n'est généré, "
                "et l'enregistrement n'exige PAS que la zone existe déjà ou réponde. Exemple : "
                "127.0.0.1:9001. Si au moment d'une vraie requête rien n'écoute à cette adresse, "
                "l'attaquant reçoit simplement une erreur HTTP 502 Bad Gateway - jamais de "
                "crash, jamais de création silencieuse.")
            ),
            action=_("Ajouter/Supprimer une zone."),
            reaction=_("REDÉMARRAGE COMPLET toujours nécessaire."),
        ),
        FieldGuide(
            label=_("IoC (export d'indicateurs de compromission)"),
            definition=_("Contrôle l'export automatique d'indicateurs à la fermeture d'un incident."),
            utilisation=_("Formats : json, csv, markdown, stix (bundle STIX 2.1) et misp (événement MISP à importer par son interface) - fichiers locaux, jamais envoyés. Marquage TLP des exports STIX et MISP : amber par défaut (white, green, amber, red). Politique de partage : local_only ou manual_export."),
            action=_("Enregistre avec le reste des réglages généraux."),
            reaction=_("REDÉMARRAGE COMPLET toujours nécessaire."),
        ),
        FieldGuide(
            label=_("Stockage et journalisation"),
            definition=_("Emplacement de la base de données, du répertoire d'export, et paramètres de capture enrichie (corps de requête, champs masques)."),
            utilisation=_("Chemins relatifs au projet ; capture du corps de requête désactivée par défaut (données potentiellement sensibles)."),
            action=_("Enregistre avec le reste des réglages généraux."),
            reaction=_("REDÉMARRAGE COMPLET toujours nécessaire."),
        ),
    ),
    consequences=(
        _("TOUT changement ici exige un redémarrage complet, sans aucune exception - "
        "active_defense n'est jamais rechargé à chaud, contrairement à la plupart des autres options.")
    ),
    points_de_vigilance=(
        (
            _("Sans activer 'war_mode.enabled' ICI, activer seulement l'option 'active_defense' "
            "(menu Options) ne sert à rien - voir la FAQ dédiée.")
        ),
        (
            _("Un profil de leurre en Isolation = fixture dont le nom n'est pas exactement "
            "fake_admin, fake_cms, fake_api ou fake_secrets ne se déclenchera JAMAIS - "
            "l'enregistrement le refuse désormais avec un message explicite.")
        ),
        (
            _("Une zone de leurre n'est jamais créée automatiquement et son existence n'est pas "
            "vérifiée à l'enregistrement - si rien n'écoute à l'adresse indiquée, l'attaquant "
            "reçoit une erreur 502 au moment de la requête, pas avant.")
        ),
    ),
)

THREATS_SCREEN = ScreenGuide(
    screen_class_name="ThreatsScreen",
    title=_("Active Defense - Menaces"),
    acces=_("Accueil -> Active Sécurité -> Menaces"),
    definition=_("Liste toutes les sources actuellement suivies par Active Defense, avec leur score et niveau de menace."),
    fields=(
        FieldGuide(
            label=_("Table des menaces"),
            definition=_("Une ligne par source suivie (IP, score, niveau, dernière mise à jour, expiration)."),
            utilisation=_("Sélectionner une ligne affiche son détail complet."),
            action=_("Aucune action mutante sur cet écran."),
            reaction=_("Purement consultatif."),
        ),
    ),
    consequences=_("Aucune modification possible depuis cet écran."),
)

INCIDENTS_SCREEN = ScreenGuide(
    screen_class_name="IncidentsScreen",
    title=_("Active Defense - Incidents"),
    acces=_("Accueil -> Active Sécurité -> Incidents"),
    definition=_("Liste les incidents de sécurité ouverts/fermes, permet de les fermer et d'exporter des indicateurs de compromission (IoC)."),
    fields=(
        FieldGuide(
            label=_("Fermer l'incident"),
            definition=_("Marque un incident comme fermé."),
            utilisation=_("Sélectionner un incident, puis confirmer."),
            action=_("Ferme l'incident immédiatement."),
            reaction=(
                _("Peut déclencher un export IoC/rapport AUTOMATIQUE si "
                "ioc.auto_export_on_close est activé dans la configuration d'Active Defense.")
            ),
        ),
        FieldGuide(
            label=_("Exporter IoC"),
            definition=_("Exporte les indicateurs de compromission de l'incident sélectionné."),
            utilisation=_("Format : json, csv, stix (bundle STIX 2.1) ou misp (événement MISP à importer par son interface)."),
            action=_("Écrit un fichier dans le répertoire d'export configuré."),
            reaction=_("Écriture réelle sur disque immédiate."),
        ),
        FieldGuide(
            label=_("Générer rapport"),
            definition=_("Génère un rapport Markdown complet de l'incident sélectionné."),
            utilisation=_("Aucune saisie supplémentaire."),
            action=_("Écrit un fichier Markdown dans le répertoire d'export configuré."),
            reaction=_("Écriture réelle sur disque immédiate."),
        ),
    ),
    consequences=_("Purement consultatif sauf fermeture d'incident (irréversible) et exports (écriture disque)."),
)

DECEPTION_SCREEN = ScreenGuide(
    screen_class_name="DeceptionScreen",
    title=_("Active Defense - Leurres"),
    acces=_("Accueil -> Active Sécurité -> Deception"),
    definition=_("Liste les affectations actives (et expirées non libérées) vers les leurres de deception, permet de les libérer."),
    fields=(
        FieldGuide(
            label=_("Libérer"),
            definition=_("Retire l'affectation d'une source vers son leurre."),
            utilisation=_("Sélectionner une ligne, puis confirmer."),
            action=_("Libère immédiatement l'affectation."),
            reaction=_("Effet immédiat - la source n'est plus redirigée vers le leurre à la prochaine requête."),
        ),
    ),
    consequences=(
        _("Les affectations expirées mais jamais libérées restent visibles avec l'état 'expirée' - "
        "distinct d'une libération manuelle.")
    ),
)

ACTIVE_DEFENSE_SIMULATE_SCREEN = ScreenGuide(
    screen_class_name="ActiveDefenseSimulateScreen",
    title=_("Active Defense - Simuler"),
    acces=_("Accueil -> Active Sécurité -> Simuler"),
    definition=_("Simule une décision Active Defense (score, classe d'attaque) SANS aucun effet réel - dry-run complet."),
    fields=(
        FieldGuide(
            label=_("IP simulée"),
            definition=_("Adresse IP source utilisée pour la simulation."),
            utilisation=_("Une IP quelconque. Valeur par défaut : 203.0.113.42."),
            action=_("Utilisée au clic sur Simuler."),
            reaction=_("Aucun effet réel - aucune écriture, aucun impact réseau."),
        ),
        FieldGuide(
            label=_("Chemin simulé"),
            definition=_("Chemin de la requête simulée."),
            utilisation=_("Chaîne libre. Valeur par défaut : /wp-login.php."),
            action=_("Utilisée au clic sur Simuler."),
            reaction=_("Aucun effet réel."),
        ),
        FieldGuide(
            label=_("User-Agent"),
            definition=_("User-Agent simulé (participe au calcul de l'identifiant de source simulé)."),
            utilisation=_("Chaîne libre, optionnelle."),
            action=_("Utilisée au clic sur Simuler."),
            reaction=_("Aucun effet réel."),
        ),
        FieldGuide(
            label=_("Classe d'attaque"),
            definition=_("Type d'attaque simulé."),
            utilisation=_("Doit être une classe connue (ex: scan). Valeur par défaut : scan."),
            action=_("Utilisée au clic sur Simuler."),
            reaction=_("Aucun effet réel."),
        ),
        FieldGuide(
            label=_("Score"),
            definition=_("Delta de score appliqué à la simulation."),
            utilisation=_("Entier. Valeur par défaut : 10."),
            action=_("Utilisée au clic sur Simuler."),
            reaction=_("Aucun effet réel."),
        ),
    ),
    consequences=_("Aucune - dry-run complet, jamais d'écriture (aucun repository.save()/create() appelé)."),
)

WAF_STATUS_SCREEN = ScreenGuide(
    screen_class_name="WafStatusScreen",
    title=_("WAF - État"),
    acces=_("Accueil -> Active Sécurité -> État (bloc WAF)"),
    definition=_("Vue d'ensemble en lecture seule : mode, comportement en cas d'erreur interne, packs de règles référencés, taille de la blocklist."),
    fields=(),
    consequences=_("Purement consultatif."),
    points_de_vigilance=(
        (
            _("Si aucun pack de règles n'est référence, le WAF ne peut RIEN détecter même actif - "
            "l'écran l'indique explicitement, corrige un vrai trou signalé par l'utilisateur.")
        ),
    ),
)

WAF_MODULES_SCREEN = ScreenGuide(
    screen_class_name="WafModulesScreen",
    title=_("WAF - Modules"),
    acces=_("Accueil -> Active Sécurité -> Modules (bloc WAF)"),
    definition=_("Trois sections : mode/comportement d'erreur, gestion des packs de règles actifs, gestion de la liste de blocage."),
    fields=(
        FieldGuide(
            label=_("Mode"),
            definition=_("Comportement du WAF face à une requête jugée malveillante."),
            utilisation=_("log-only (journalise sans bloquer) ou block (bloque réellement)."),
            action=_("Enregistre au clic sur Enregistrer."),
            reaction=_("Rechargement AUTOMATIQUE déclenché des l'enregistrement si un service actif existe."),
        ),
        FieldGuide(
            label=_("Comportement en cas d'erreur interne"),
            definition=_("Que faire si le moteur WAF rencontre une erreur inattendue en analysant une requête."),
            utilisation=_("fail-open (laisse passer) ou fail-closed (bloque par prudence)."),
            action=_("Enregistre avec le mode."),
            reaction=_("Rechargement automatique."),
        ),
        FieldGuide(
            label=_("Packs de règles (rule_paths)"),
            definition=_("Fichiers de règles réellement charges par le WAF - sans au moins un pack, rien n'est détecté."),
            utilisation=_("Ajouter ouvre un sélecteur des packs présents sous secure/waf/rules/ non déjà référencés."),
            action=_("Ajoute/retire une référence de pack."),
            reaction=_("Rechargement automatique déclenché immédiatement (recompile les règles en mémoire)."),
        ),
        FieldGuide(
            label=_("Liste de blocage"),
            definition=(
                _("IP/reseaux bannis, avec motif et expiration optionnelle. Fichier par défaut : "
                "var/lib/waf/blocklist.json (sous var/, le seul dossier où le service systemd peut "
                "écrire ses auto-bans). Un ancien secure/waf/blocklist.json est repris une fois au "
                "démarrage et laissé en place comme sauvegarde.")
            ),
            utilisation=_("Réseau (CIDR), motif, durée en secondes (vide = permanent, confirmation requise dans ce cas)."),
            action=_("Ajoute/retire une entrée."),
            reaction=(
                _("EFFET IMMÉDIAT, sans rechargement nécessaire - la blocklist est relue depuis "
                "le disque à CHAQUE requête, jamais mise en cache en mémoire (contrairement au "
                "mode et aux packs de règles).")
            ),
        ),
    ),
    consequences=(
        _("Mode/comportement d'erreur/packs de règles nécessitent un rechargement pour s'appliquer "
        "(automatique si un service actif existe). La liste de blocage, elle, s'applique "
        "instantanément sans aucune action supplémentaire.")
    ),
)

WAF_RATE_LIMIT_SCREEN = ScreenGuide(
    screen_class_name="WafRateLimitScreen",
    title=_("WAF - Exclusions et débit"),
    acces=_("Accueil -> Active Sécurité -> Exclusions et débit (bloc WAF)"),
    definition=(
        _("Règle la limite de débit (rate limit) du WAF natif : la limite globale, des règles par "
        "dossier et des règles par IP/réseau, ainsi que les exclusions d'inspection. Sert surtout "
        "aux pages lourdes (une galerie d'images, par exemple) qui dépassent la limite globale et "
        "reçoivent une erreur 429.")
    ),
    fields=(
        FieldGuide(
            label=_("Limite globale"),
            definition=_("Nombre de requêtes autorisées par IP et par fenêtre, pour tout ce qui n'a pas de règle spécifique."),
            utilisation=_("Rate limit actif (oui/non), nombre de requêtes, fenêtre en secondes."),
            action=_("Enregistre au clic sur Enregistrer."),
            reaction=_("Rechargement automatique déclenché si un service actif existe."),
        ),
        FieldGuide(
            label=_("Règles par dossier"),
            definition=(
                _("Une règle REMPLACE la limite globale pour ce dossier et a son propre compteur : "
                "les requêtes sur ce dossier ne consomment plus la limite globale. 0 = illimité. "
                "Si plusieurs dossiers correspondent, le plus long gagne. /images couvre /images/a.png "
                "mais jamais /images2.")
            ),
            utilisation=_("Ajouter / Modifier : dossier, requêtes par fenêtre, fenêtre en secondes. Sélectionner une ligne pour la modifier ou la retirer."),
            action=_("Enregistré dès la validation du formulaire."),
            reaction=(
                _("Rechargement automatique. Une IP publique qui dépasse une règle de dossier est "
                "toujours journalisée comme un blocage, donc bannissable par omega-jail.")
            ),
        ),
        FieldGuide(
            label=_("Règles par IP / réseau"),
            definition=(
                _("Même principe pour une IP ou un réseau (ex. le réseau Tailscale 100.64.0.0/10). "
                "Une règle de dossier passe avant une règle IP/réseau ; entre deux réseaux, le plus "
                "précis gagne.")
            ),
            utilisation=(
                _("IP ou réseau (CIDR), requêtes, fenêtre, Source sûre (oui/non). Une source sûre qui "
                "dépasse la limite reçoit toujours le 429, mais la ligne est journalisée « throttle » : "
                "jamais bannissable.")
            ),
            action=_("Enregistré dès la validation du formulaire."),
            reaction=(
                _("Les réseaux never_auto_block (affichés au-dessus du tableau) sont toujours sûrs "
                "d'office. Sans proxy de confiance actif, une règle couvrant 127.0.0.1/::1 est "
                "ignorée.")
            ),
        ),
        FieldGuide(
            label=_("Exclusions d'inspection"),
            definition=_("Dossiers et extensions jamais inspectés par le WAF natif ni par magnet, et dossiers dont seul le corps n'est pas inspecté."),
            utilisation=_("Valeurs séparées par des virgules ; un dossier commence par « / »."),
            action=_("Enregistre au clic sur Enregistrer."),
            reaction=_("Le rate limit s'applique toujours à ces chemins : une exclusion ne règle jamais un 429."),
        ),
    ),
    consequences=_("Une règle de débit ne désactive jamais l'inspection : une attaque sur un dossier à débit élevé reste détectée et bloquée."),
    points_de_vigilance=(
        (
            _("Un dossier en illimité (0) ne protège plus contre un robot qui le martèle depuis une "
            "IP publique : préférer une valeur haute (ex. 600 / 60 s) à l'illimité.")
        ),
        (
            _("Sans rapport avec « Requêtes max par connexion keep-alive » (Configuration détaillée -> "
            "Résistance et limites) : ce réglage ferme seulement une connexion après N requêtes, le "
            "navigateur en rouvre une aussitôt. Il ne renvoie jamais 429 et ne compte rien par IP : "
            "c'est la limite de débit, ici, qui produit le 429.")
        ),
        (
            _("Script magnet : son propre rate limit (429) ne compte jamais comme une détection, donc "
            "ne mène jamais à l'auto-ban. Sur une requête couverte par une règle de dossier ou "
            "d'IP/réseau ci-dessus, c'est cette règle qui fait foi : le 429 de magnet est ignoré "
            "(ses signatures d'attaque restent appliquées).")
        ),
    ),
)

WAF_TEST_SCREEN = ScreenGuide(
    screen_class_name="WafTestScreen",
    title=_("WAF - Tester une requête"),
    acces=_("Accueil -> Active Sécurité -> Tester (bloc WAF)"),
    definition=_("Teste une requête simulée contre les règles WAF ACTUELLEMENT ENREGISTRÉES (pas nécessairement celles réellement chargées par un serveur déjà lancé), sans requête réseau."),
    fields=(
        FieldGuide(
            label=_("Méthode / Chemin / Query / Body / IP distante"),
            definition=_("Composants de la requête HTTP simulée."),
            utilisation=_("Valeurs libres - méthode et chemin pré-remplis (GET, /)."),
            action=_("Utilisés au clic sur Tester."),
            reaction=_("Aucun effet réel, aucune requête réseau."),
        ),
    ),
    consequences=_("Purement consultatif."),
    points_de_vigilance=(
        (
            _("Reconstruit le moteur WAF à partir de la configuration SAUVEGARDÉE sur disque à "
            "chaque test - si un serveur déjà lancé n'a pas encore été rechargé après un "
            "changement de règles, ce test peut refléter un comportement différent de ce que ce "
            "serveur applique réellement pour l'instant.")
        ),
    ),
)

WAF_CUSTOM_RULE_SCREEN = ScreenGuide(
    screen_class_name="WafCustomRuleScreen",
    title=_("WAF - Règles et listes personnalisées"),
    acces=_("Accueil -> Active Sécurité -> Custom (bloc WAF)"),
    definition=(
        _("Un seul tableau pour les RÈGLES (écrites dans secure/waf/rules/custom.json, pack "
        "référence automatiquement) et les LISTES (fichiers texte de secure/waf/rules/keywords/, "
        "chargées explicitement par l'assistant). La colonne Type fait la différence : une "
        "liste n'est pas une règle de custom.json.")
    ),
    fields=(
        FieldGuide(
            label=_("Ajouter"),
            definition=_("Ouvre l'assistant : une règle simple, ou CHARGER une liste (voir sa fiche)."),
            utilisation=_("Clic, puis suivre l'assistant."),
            action=_("Règle : écrite dans custom.json. Liste : ajoutée à options.waf.rules.keyword_lists."),
            reaction=_("Rechargement automatique déclenché immédiatement si un service actif existe."),
        ),
        FieldGuide(
            label=_("Colonne Détail (listes)"),
            definition=_("Nombre d'entrées du fichier, ou un avertissement."),
            utilisation=(
                _("'fichier absent', 'illisible par le service' ou 'emplacement refusé' : la liste "
                "n'est pas chargeable telle quelle - ouvrez-la avec Éditer la liste.")
            ),
            action=_("Recalculé à chaque affichage du tableau."),
            reaction=_("Aucun effet en lui-même."),
        ),
        FieldGuide(
            label=_("Colonne Gravité (listes)"),
            definition=_("Observation, Faible, Moyen, Élevé ou Critique, suivie de la récidive propre à la liste."),
            utilisation=_("Ex. 'Élevé, 2 en 10 min -> ban 24 h'."),
            action=_("Se change avec Modifier."),
            reaction=_("Aucun effet en lui-même."),
        ),
        FieldGuide(
            label=_("Modifier (listes)"),
            definition=_("Change gravité, récidive, zone de recherche et nom affiché d'une liste déjà chargée."),
            utilisation=_("Sélectionner une ligne Liste, puis Modifier."),
            action=(
                _("Vérifie la nouvelle configuration comme au chargement : rendre bloquante une liste "
                "qui toucherait une route du site est refusé avec la raison.")
            ),
            reaction=_("Rechargement automatique déclenché immédiatement."),
        ),
        FieldGuide(
            label=_("Éditer la liste"),
            definition=_("Ouvre l'éditeur intégré sur le fichier de la liste (voir sa fiche)."),
            utilisation=_("Sélectionner une ligne Liste, puis Éditer la liste."),
            action=_("Aucune écriture tant que l'éditeur n'a pas enregistré."),
            reaction=_("Le tableau est rafraîchi à la fermeture de l'éditeur."),
        ),
        FieldGuide(
            label=_("Activer/Desactiver"),
            definition=_("Bascule une règle ou une liste sans la supprimer."),
            utilisation=_("Sélectionner une ligne, puis cliquer."),
            action=_("Règle : champ enabled de custom.json. Liste : champ enabled de keyword_lists."),
            reaction=_("Rechargement automatique déclenché immédiatement."),
        ),
        FieldGuide(
            label=_("Supprimer / Retirer"),
            definition=_("Supprimer une règle, ou Retirer une liste du WAF."),
            utilisation=_("Sélectionner une ligne, puis confirmer."),
            action=_("Règle : retirée de custom.json. Liste : retirée de la configuration, FICHIER CONSERVÉ."),
            reaction=_("Rechargement automatique déclenché immédiatement."),
        ),
    ),
    consequences=(
        _("Une règle ou une liste refusée par la validation est refusée ICI de la même façon qu'elle "
        "le serait au chargement réel - jamais une double logique de validation divergente.")
    ),
    points_de_vigilance=(
        (
            _("Piège déjà rencontré par un utilisateur : ajouter le PACK via 'Modules' n'est pas la "
            "même chose que créer une RÈGLE ici - cet écran fait désormais les deux à la fois "
            "automatiquement.")
        ),
        (
            _("Retirer une liste ne supprime jamais son fichier : il reste proposé par l'assistant, "
            "prêt à être rechargé.")
        ),
    ),
)

WAF_CUSTOM_RULE_WIZARD_SCREEN = ScreenGuide(
    screen_class_name="WafCustomRuleWizardScreen",
    title=_("WAF - Assistant règle personnalisée / chargement de liste"),
    acces=_("WAF - Règles et listes personnalisées -> Ajouter"),
    definition=(
        _("Questionnaire en langage clair pour construire une règle WAF sans connaître les "
        "expressions régulières (4 scénarios courants + mode Avance), OU pour CHARGER une liste "
        "de chemins / de mots-clés depuis un fichier texte. Le chargement d'une liste est une "
        "action explicite : rien n'est actif avant le clic sur Charger.")
    ),
    fields=(
        FieldGuide(
            label=_("Que voulez-vous détecter ?"),
            definition=_("Choisit le scénario de détection."),
            utilisation=(
                _("Un chemin précis visite, un mot-clé dans l'adresse/parametres, un mot-clé "
                "envoyé en formulaire (POST), un outil de scan connu (User-Agent), Avance "
                "(regex/portee libres), CHARGER une liste de chemins, CHARGER une liste de mots-clés.")
            ),
            action=_("Change les champs affiches en dessous et leur indice."),
            reaction=_("Aucun effet en lui-même."),
        ),
        FieldGuide(
            label=_("Valeur à détecter (mode simple)"),
            definition=_("Le texte à repérer, saisi en clair (jamais une regex à écrire)."),
            utilisation=_("Un mot ou un chemin, selon le scénario choisi ci-dessus."),
            action=_("La regex réelle est CONSTRUITE automatiquement par le code (caractères spéciaux jamais interprétés)."),
            reaction=_("Aucun effet avant validation sur l'écran précédent (WafCustomRuleScreen)."),
        ),
        FieldGuide(
            label=_("Portée / Motif (mode Avance)"),
            definition=_("Portée et expression régulière écrites directement."),
            utilisation=_("Portée : path, query, body, headers, user_agent, referer (séparés par des virgules)."),
            action=_("Utilisé tel quel si Avance est choisi."),
            reaction=_("Aucun effet avant validation sur l'écran précédent."),
        ),
        FieldGuide(
            label=_("Gravité (règle)"),
            definition=_("Poids de la règle dans le calcul du score de menace."),
            utilisation=_("Faible/Moyen/Eleve/Critique (1/3/6/9)."),
            action=_("Inclus dans la règle produite."),
            reaction=_("Aucun effet avant validation sur l'écran précédent."),
        ),
        FieldGuide(
            label=_("Fichier de liste (CHARGER)"),
            definition=_("Le fichier texte qui contient la liste."),
            utilisation=(
                _("Vos fichiers .txt de secure/waf/rules/keywords/ (avec leur nombre d'entrées), les "
                "références livrées avec omega-serv (sensitive-paths-hostile, sensitive-paths-probe) "
                "pas encore copiées, ou 'Nouveau fichier...' (nom en lettres, chiffres et '-').")
            ),
            action=(
                _("Une référence est COPIÉE dans keywords/ au chargement : c'est cette copie locale que "
                "vous modifiez, une mise à jour d'omega-serv ne l'écrase jamais. Choisir une référence "
                "pré-remplit tous les réglages conseillés.")
            ),
            reaction=_("Aucun effet avant Charger."),
        ),
        FieldGuide(
            label=_("Où chercher (liste de chemins)"),
            definition=_("N'importe où dans l'adresse, ou seulement au début."),
            utilisation=(
                _("Partout attrape /blog/.env ; au début seulement est plus prudent pour des chemins "
                "qu'un vrai site peut servir (/api, /admin).")
            ),
            action=_("Champ anchor de la liste (any_segment / root)."),
            reaction=_("Aucun effet avant Charger."),
        ),
        FieldGuide(
            label=_("Dans quelle partie de la requête (liste de mots-clés)"),
            definition=_("Où chercher les mots-clés."),
            utilisation=_("L'adresse et ses paramètres, un formulaire envoyé (POST), le User-Agent, ou le Referer."),
            action=_("Champ scope de la liste."),
            reaction=_("Aucun effet avant Charger."),
        ),
        FieldGuide(
            label=_("Gravité (liste)"),
            definition=_("Observation, Faible (1), Moyen (3), Élevé (6), Critique (9)."),
            utilisation=(
                _("Observation (conseillé au premier chargement) : alertes journalisées, AUCUN blocage, "
                "aucune récidive. Élevé (6) atteint le seuil de blocage : 403 dès le premier accès. "
                "Moyen (3) ne bloque jamais seul.")
            ),
            action=_("Champs weight et observe_only de la liste."),
            reaction=_("Aucun effet avant Charger."),
        ),
        FieldGuide(
            label=_("Récidive"),
            definition=_("Bannir après N accès à CETTE liste en M minutes, pendant une durée choisie."),
            utilisation=(
                _("'pas de récidive propre' = compteur commun du WAF. Références : hostile 2 accès en "
                "10 min -> 24 h, sondage 5 en 10 min -> 1 h. Grise en Observation.")
            ),
            action=(
                _("Ban applicatif temporaire (blocklist, réponse 451), jamais pour l'hôte local "
                "(derrière un proxy de confiance), Tailscale ou le réseau local.")
            ),
            reaction=_("Aucun effet avant Charger."),
        ),
        FieldGuide(
            label=_("Ouvrir l'éditeur"),
            definition=_("Ouvre le fichier choisi dans l'éditeur intégré (ou la référence si pas encore copiée)."),
            utilisation=_("Pour vérifier ou adapter la liste AVANT de la charger."),
            action=_("Rien n'est chargé dans le WAF depuis l'éditeur."),
            reaction=_("Les nombres d'entrées sont rafraîchis à la fermeture."),
        ),
        FieldGuide(
            label=_("Charger"),
            definition=_("Charge la liste dans le WAF."),
            utilisation=_("Dernier clic de l'assistant."),
            action=(
                _("Vérifie, dans l'ordre : nom de fichier, syntaxe (numéro de ligne en cas d'erreur), "
                "lisibilité par le compte du service, absence de doublon, conflits avec les routes du "
                "site. Si une seule vérification échoue, la configuration n'est PAS modifiée. Active "
                "ensuite la réputation et l'auto-ban s'ils étaient éteints (avec un message).")
            ),
            reaction=_("Rechargement automatique déclenché immédiatement si un service actif existe."),
        ),
    ),
    consequences=(
        _("Règle : ne fait qu'assembler les valeurs, l'écriture a lieu sur l'écran WAF - Règles et "
        "listes personnalisées. Liste : rien n'est actif tant que Charger n'a pas réussi.")
    ),
    points_de_vigilance=(
        (
            _("Une liste qui bloque seule (gravité >= 5) et qui toucherait une route réellement servie "
            "(alias, reverse proxy, zone Auth, fichier du webroot) est refusée : ajoutez une exception "
            "'!/chemin' dans la liste, ou chargez-la en Observation.")
        ),
    ),
)

PATH_LIST_EDITOR_SCREEN = ScreenGuide(
    screen_class_name="PathListEditorScreen",
    title=_("WAF - Éditeur de liste"),
    acces=_("WAF - Règles et listes personnalisées -> Éditer la liste (ou Assistant -> Ouvrir l'éditeur)"),
    definition=(
        _("Éditeur de texte intégré, sans éditeur externe, pour une liste de chemins ou de mots-clés. "
        "Tout se fait à la SOURIS : aucun raccourci clavier, le clavier ne sert qu'à la saisie "
        "(caractères, Entrée, flèches, Debut/Fin, Page prec./suiv., Retour arrière, Suppr).")
    ),
    fields=(
        FieldGuide(
            label=_("Syntaxe d'une liste de chemins"),
            definition=_("Une entrée par ligne, '#' = commentaire."),
            utilisation=(
                _("/admin -> /admin et /admin/xxx (jamais /administrator) ; /.git/ -> tout ce qui est "
                "sous /.git/ ; /*.bak -> fichiers finissant par .bak ; !/api/v1 -> exception, "
                "toujours prioritaire sur les entrées, quel que soit l'ordre des lignes.")
            ),
            action=_("Analysée en direct (compteur d'entrées, d'exceptions, d'erreurs et d'avertissements)."),
            reaction=_("Les erreurs s'affichent avec leur numéro de ligne ; cliquer une erreur place le curseur dessus."),
        ),
        FieldGuide(
            label=_("Barre d'outils"),
            definition=_("Annuler la modif, Rétablir, Couper, Copier, Coller, Sélectionner la ligne, Tout sélectionner, Supprimer la ligne."),
            utilisation=_("Clic. Le collage du terminal (clic du milieu, menu du terminal) fonctionne aussi."),
            action=_("Modifie le texte affiché, jamais le fichier."),
            reaction=_("Toujours annulable."),
        ),
        FieldGuide(
            label=_("Rechercher"),
            definition=_("Trouve un texte dans la liste (casse ignorée)."),
            utilisation=_("Taper le texte, puis Précédent / Suivant."),
            action=_("Sélectionne l'occurrence trouvée."),
            reaction=_("Recommence au début après la dernière occurrence."),
        ),
        FieldGuide(
            label=_("Tester (liste de chemins)"),
            definition=_("Indique ce que ferait la liste EN COURS d'édition d'un chemin donné."),
            utilisation=_("Taper un chemin (ex. /blog/.env), puis Tester."),
            action=_("Même normalisation que le WAF (paramètres retirés, décodage URL)."),
            reaction=_("'DÉTECTÉ par la ligne N', 'AUTORISÉ : exception ligne N', ou 'aucune ligne ne correspond'."),
        ),
        FieldGuide(
            label=_("Vérifier contre mes logs (liste de chemins)"),
            definition=_("Rejoue les requêtes RÉUSSIES (2xx/3xx) du journal d'accès contre la liste."),
            utilisation=_("Chaque ligne de la liste qui aurait touché une requête probablement légitime est montrée avec un exemple."),
            action=_("Cliquer une ligne : exception pour ce chemin, exception pour son dossier, ou suppression de la ligne."),
            reaction=_("Modifie le texte affiché (annulable), jamais le fichier avant Enregistrer."),
        ),
        FieldGuide(
            label=_("Nouveautés de la référence"),
            definition=_("Entrées de la référence livrée absentes de votre liste."),
            utilisation=_("Cocher celles à ajouter, puis Ajouter la sélection."),
            action=(
                _("Rien n'est ajouté sans être coché. Une ligne de la référence que vous supprimez est "
                "marquée '#retire: /x' à l'enregistrement et n'est plus jamais reproposée.")
            ),
            reaction=_("Modifie le texte affiché."),
        ),
        FieldGuide(
            label=_("Corriger les droits"),
            definition=_("Rend le fichier lisible par le compte du service (omega-serv)."),
            utilisation=_("Proposé seulement si l'état signale que le service ne peut pas lire le fichier."),
            action=(
                _("Liste chaque changement de droits avant de l'appliquer, uniquement sur ce qui vous "
                "appartient - jamais via sudo.")
            ),
            reaction=_("L'état est recalculé."),
        ),
        FieldGuide(
            label=_("Enregistrer et appliquer"),
            definition=_("Écrit le fichier, puis recharge le serveur si la liste est chargée."),
            utilisation=_("Refusé tant qu'il reste une erreur."),
            action=(
                _("Écriture sûre : droits et groupe conservés, nouveau fichier en 0644, refus si le "
                "fichier a été modifié ailleurs depuis l'ouverture, ou si c'est un lien symbolique.")
            ),
            reaction=(
                _("Le rechargement n'est déclenché que si la vérification de la liste réussit - sinon "
                "la raison est affichée et le serveur garde ses règles actuelles.")
            ),
        ),
        FieldGuide(
            label=_("Fermer / Aide"),
            definition=_("Fermer l'éditeur, ou ouvrir cette fiche."),
            utilisation=_("Clic."),
            action=_("Fermer demande une confirmation s'il reste des modifications non enregistrées."),
            reaction=_("Retour à l'écran précédent."),
        ),
    ),
    consequences=(
        _("Le fichier n'est jamais modifié avant Enregistrer. Un fichier non modifiable par votre "
        "compte s'ouvre en LECTURE SEULE, avec la raison.")
    ),
    points_de_vigilance=(
        (
            _("Échap et F1 ne font rien ici, volontairement (aucun raccourci) : utilisez Fermer et Aide. "
            "Seul ctrl+q reste actif pour quitter l'application, avec confirmation.")
        ),
        (
            _("L'état en bas de l'écran indique si le compte du service peut lire le fichier : un fichier "
            "illisible ferait échouer le prochain rechargement.")
        ),
    ),
)

KEYWORD_LIST_SETTINGS_SCREEN = ScreenGuide(
    screen_class_name="KeywordListSettingsScreen",
    title=_("WAF - Modifier une liste"),
    acces=_("WAF - Règles et listes personnalisées -> Modifier (ligne Liste)"),
    definition=_("Change les réglages d'une liste déjà chargée, sans toucher à son fichier."),
    fields=(
        FieldGuide(
            label=_("Nom affiché / Où chercher / Gravité / Récidive"),
            definition=_("Mêmes choix que dans l'assistant (voir sa fiche)."),
            utilisation=_("Passer d'Observation à une gravité bloquante une fois les alertes lues."),
            action=_("Vérifie la nouvelle configuration avant de l'écrire."),
            reaction=_("Rechargement automatique ; refus affiché avec sa raison si la vérification échoue."),
        ),
    ),
    consequences=_("Rendre une liste bloquante réactive la réputation et l'auto-ban s'ils avaient été éteints."),
)

WAF_MAGNET_SCREEN = ScreenGuide(
    screen_class_name="WafMagnetScreen",
    title=_("WAF - Magnet (import d'un WAF externe)"),
    acces=_("Accueil -> Active Sécurité -> Magnet (bloc WAF)"),
    definition=(
        _("Importe un script WAF mod_magnet Lighttpd EXISTANT (écrit pour un autre site) sans le "
        "réécrire, comme renfort additif au WAF natif - il ne peut jamais lever un blocage déjà "
        "décidé par le natif. Seuls les chemins personnels du script (fichiers de log/blocage) se "
        "dissocient ici, jamais la logique du script lui-même.")
    ),
    fields=(
        FieldGuide(
            label=_("Actif (oui/non)"),
            definition=_("Active ou désactive le script magnet."),
            utilisation=_("oui ou non."),
            action=_("Enregistre au clic sur Enregistrer."),
            reaction=_("Rechargement automatique déclenché si un service actif existe."),
        ),
        FieldGuide(
            label=_("Script (chemin relatif au projet)"),
            definition=_("Le fichier Lua à importer - une liste des scripts trouves sous secure/waf/scripts/ est affichée en indice."),
            utilisation=_("Chemin relatif au projet, ex. secure/waf/scripts/waf.lua."),
            action=_("Enregistre avec Actif."),
            reaction=_("Aucun effet avant Enregistrer - utiliser Vérifier la compatibilité pour tester sans rien écrire."),
        ),
        FieldGuide(
            label=_("Délai maximum par appel (ms) / Comportement en cas d'erreur"),
            definition=_("Borne le temps d'exécution du script par requête, et la décision prise si le script plante ou dépasse ce délai."),
            utilisation=_("Délai en millisecondes ; ignore (laisse passer) ou fail-closed (bloque par prudence)."),
            action=_("Enregistre avec Actif."),
            reaction=_("fail-closed combiné à une incompatibilité détectée peut bloquer du trafic légitime - avertissement explicite affiché par Vérifier la compatibilité dans ce cas."),
        ),
        FieldGuide(
            label=_("Chemins personnels dissociés"),
            definition=(
                _("5 chemins (blocklist, dossier de règles, 2 journaux, fichier de persistance du "
                "rate limiting) injectés dans le script à la place de ses chemins en dur d'origine - "
                "propre à chaque script importe, jamais un contrat générique. Blocklist par défaut : "
                "var/lib/waf/magnet-blocklist.txt (le script y ÉCRIT ; un ancien "
                "secure/waf/magnet-blocklist.txt est repris une fois). Un chemin choisi à la main doit "
                "rester inscriptible par le compte du service, sinon les bans sont perdus sans message.")
            ),
            utilisation=_("Vide = le script garde son propre chemin en dur (aucune injection pour ce champ)."),
            action=_("Enregistre avec Actif."),
            reaction=_("Les dossiers parents sont créés automatiquement à l'usage réel (jamais lors d'un simple 'config check')."),
        ),
        FieldGuide(
            label=_("Vérifier la compatibilité"),
            definition=_("Exécute RÉELLEMENT le script avec les valeurs du formulaire EN COURS DE SAISIE, pas seulement celles déjà enregistrées."),
            utilisation=_("À utiliser avant d'activer un script importe en production - répond à 'ce script est-il compatible ?'."),
            action=_("Scan statique (membres lighty.* non supportes) + exécution réelle sur une requête de test bénigne."),
            reaction=_("Aucun effet sur le serveur ni sur la configuration enregistrée - purement diagnostique."),
        ),
    ),
    consequences=_("Le natif reste toujours actif en parallèle - le magnet ne peut qu'ajouter un blocage, jamais en lever un."),
    points_de_vigilance=(
        (
            _("Un script importe peut référencer une fonctionnalité lighty.* non supportée par ce "
            "pont (toujours nil côté Lua) - toujours lancer Vérifier la compatibilité avant "
            "d'activer un nouveau script en production, surtout avec on_error=fail-closed.")
        ),
    ),
)

WAF_RULE_PACK_PICKER_SCREEN = ScreenGuide(
    screen_class_name="WafRulePackPickerScreen",
    title=_("WAF - Choix d'un pack de règles"),
    acces=_("WAF - Modules -> Ajouter un pack"),
    definition=_("Liste RÉELLE des packs de règles présents sous secure/waf/rules/, exclut ceux déjà référencés - jamais de doublon proposé."),
    fields=(
        FieldGuide(
            label=_("Sélection du pack"),
            definition=_("Choisit un pack parmi ceux disponibles et non déjà référencés."),
            utilisation=_("Un menu déroulant, avec la description du pack (nombre de règles, état par défaut) affichée en dessous."),
            action=_("Confirmer renvoie le chemin choisi à l'écran Modules."),
            reaction=_("Aucun effet ici - la référence réelle est ajoutée par l'écran appelant."),
        ),
    ),
    consequences=_("Aucune modification directe - purement une aide de sélection."),
)

ALL_ACTIVE_SECURITY_GUIDES: tuple[ScreenGuide, ...] = (
    ACTIVE_DEFENSE_MENU_SCREEN,
    ACTIVE_DEFENSE_STATUS_SCREEN,
    ACTIVE_DEFENSE_SETTINGS_SCREEN,
    THREATS_SCREEN,
    INCIDENTS_SCREEN,
    DECEPTION_SCREEN,
    ACTIVE_DEFENSE_SIMULATE_SCREEN,
    WAF_STATUS_SCREEN,
    WAF_MODULES_SCREEN,
    WAF_RATE_LIMIT_SCREEN,
    WAF_TEST_SCREEN,
    WAF_CUSTOM_RULE_SCREEN,
    WAF_CUSTOM_RULE_WIZARD_SCREEN,
    PATH_LIST_EDITOR_SCREEN,
    KEYWORD_LIST_SETTINGS_SCREEN,
    WAF_RULE_PACK_PICKER_SCREEN,
    WAF_MAGNET_SCREEN,
)
