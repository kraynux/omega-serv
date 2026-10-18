"""Fiches guide : Active Securite - menu + 5 Active Defense + 4 WAF + 2
modaux (plan guide d'aide, Phase 8)."""
from __future__ import annotations

from omega_serv.interfaces.tui.guide.model import FieldGuide, ScreenGuide

ACTIVE_DEFENSE_MENU_SCREEN = ScreenGuide(
    screen_class_name="ActiveDefenseMenuScreen",
    title="Active Securite (menu)",
    acces="Accueil -> Active Securite",
    definition=(
        "Regroupe deux blocs d'etat operationnel (change en continu, pas des formulaires de "
        "reglages statiques) : Active Defense (menaces/incidents/leurres) et WAF (mode/packs/blocklist)."
    ),
    fields=(),
    consequences="Aucune - purement navigation.",
    points_de_vigilance=(
        (
            "Si un avertissement de groupe systeme apparait en haut de cet ecran, reconnectez "
            "votre session avant d'utiliser les sous-ecrans - sinon ils resteront en erreur d'acces."
        ),
        (
            "Activer l'option 'active_defense' (menu Options) ne suffit PAS a lui seul - voir la "
            "fiche 'Active Defense - Etat' et la FAQ 'Active Defense ne detecte jamais rien'."
        ),
    ),
)

ACTIVE_DEFENSE_STATUS_SCREEN = ScreenGuide(
    screen_class_name="ActiveDefenseStatusScreen",
    title="Active Defense - Etat",
    acces="Accueil -> Active Securite -> Etat (bloc Active Defense)",
    definition="Vue d'ensemble en lecture seule : mode, etat du mode guerre, etat de la deception, nombre de sources suivies.",
    fields=(),
    consequences=(
        "Purement consultatif - mais la ligne 'Mode guerre' affichee ici est le seul endroit ou "
        "verifier le VRAI interrupteur qui declenche quoi que ce soit (voir points de vigilance)."
    ),
    points_de_vigilance=(
        "L'activation de l'option active_defense se fait dans le menu Options, jamais ici.",
        (
            "PIEGE REEL VERIFIE DANS LE CODE : activer l'option 'active_defense' seule ne "
            "declenche RIEN. Un second interrupteur, `war_mode.enabled` (Active Defense - "
            "Reglages), vaut FALSE par defaut. Tant qu'il reste a false, les ecrans Menaces/"
            "Incidents/Leurres restent fonctionnels mais ne se peuplent jamais, meme avec un "
            "trafic hostile reel."
        ),
        (
            "Une fois `war_mode.enabled=true`, tout devient automatique et deterministe, sans "
            "aucune intervention manuelle : chaque decision WAF deja calculee alimente un score "
            "cumule par source (IP + User-Agent hache, avec decroissance dans le temps), qui "
            "franchit des seuils configurables (normal/suspicious/hostile/contained) declenchant "
            "des actions automatiques (redirection vers un leurre, journalisation enrichie, "
            "ralentissement, creation d'incident)."
        ),
    ),
)

ACTIVE_DEFENSE_SETTINGS_SCREEN = ScreenGuide(
    screen_class_name="ActiveDefenseSettingsScreen",
    title="Active Defense - Reglages",
    acces="Accueil -> Active Securite -> Reglages (bloc Active Defense)",
    definition=(
        "Configure l'integralite d'Active Defense (mode guerre, deception/leurres, IoC, "
        "stockage, journalisation) - AUCUNE edition manuelle de config/omega-serve.json n'est "
        "plus necessaire pour ces reglages."
    ),
    fields=(
        FieldGuide(
            label="Mode",
            definition="Mode global d'Active Defense.",
            utilisation="monitor (observe uniquement) ou enforce. Valeur par defaut : monitor.",
            action="Enregistre au clic sur Enregistrer, apres validation.",
            reaction="REDEMARRAGE COMPLET toujours necessaire - active_defense n'est jamais recharge a chaud.",
        ),
        FieldGuide(
            label="Mode guerre actif (war_mode.enabled)",
            definition="LE VRAI INTERRUPTEUR qui declenche l'observation et les actions automatiques.",
            utilisation="oui/non. Valeur par defaut : non - RIEN ne se declenche tant qu'il reste a 'non'.",
            action="Enregistre avec le reste des reglages generaux.",
            reaction="REDEMARRAGE COMPLET toujours necessaire.",
        ),
        FieldGuide(
            label="Portee / Actions autorisees / Seuils / Ralentissement / Limite de requetes",
            definition="Reglages fins du mode guerre : a qui s'appliquent les actions, lesquelles, a quel score, et leurs parametres.",
            utilisation=(
                "Portee : source/instance. Actions : liste parmi observe, enrich_log, delay, "
                "rate_limit, redirect_to_decoy, create_incident, export_ioc. Seuils : 4 entiers "
                "croissants (suspect <= hostile <= incident, confine >= hostile). Ralentissement "
                "et limite de requetes : bornes en millisecondes/secondes."
            ),
            action="Valides par les memes regles que le domaine (`validate_active_defense_config`) avant tout enregistrement.",
            reaction="REDEMARRAGE COMPLET toujours necessaire.",
        ),
        FieldGuide(
            label="Deception (actif, comportement par defaut, duree de vie d'une affectation)",
            definition="Active ou non le routage vers des leurres, et ce qui se passe si aucun profil ne correspond a l'attaque.",
            utilisation="actif : oui/non. Comportement : pass_through (laisse passer) ou reject.",
            action="Enregistre avec le reste des reglages generaux.",
            reaction="REDEMARRAGE COMPLET toujours necessaire.",
        ),
        FieldGuide(
            label="Profils de leurre (table)",
            definition="Associe une classe d'attaque a un niveau d'isolation - le premier profil actif qui correspond est utilise.",
            utilisation=(
                "Nom : si Isolation = fixture, DOIT etre exactement fake_admin, fake_cms, "
                "fake_api ou fake_secrets (les 4 seules fixtures reellement implementees) - "
                "tout autre nom fait que le leurre ne se declenche JAMAIS, sans aucune erreur "
                "visible (bloque desormais a l'enregistrement par validate_active_defense_config). "
                "Libre si Isolation = proxy. "
                "Classes d'attaque visees (separees par virgules) : scan (sondage d'URLs/ports), "
                "credential_stuffing (essais massifs de mots de passe), sqli (injection SQL), "
                "xss (script injecte), path_traversal (ex : ../../etc/passwd), upload_probe "
                "(upload de fichier suspect), api_probe (sondage d'endpoints /api/...), unknown "
                "(tout le reste, filet de securite). Exemple concret : un profil "
                "fake_admin avec scan,credential_stuffing intercepte les scanners et les tentatives "
                "de bruteforce de login. Isolation : fixture (simulation interne, rapide, sans "
                "risque) ou proxy (redirige vers un vrai serveur isole que vous faites tourner, "
                "voir Zones de leurre ci-dessous). Zone de leurre associee : requise si Isolation "
                "= proxy, doit correspondre a un nom de la table Zones de leurre."
            ),
            action="Ajouter/Supprimer un profil.",
            reaction="REDEMARRAGE COMPLET toujours necessaire.",
        ),
        FieldGuide(
            label="Zones de leurre (table, Niveau 2)",
            definition="Backends reellement isoles vers lesquels un profil 'proxy' peut rediriger - jamais confondues avec les zones de reverse_proxy de production.",
            utilisation=(
                "Nom : un simple identifiant (pas une URL, pas un dossier) reference depuis un "
                "profil de leurre en Isolation = proxy. Upstreams (host:port, separes par "
                "virgules) : adresse(s) d'un serveur DEJA EN COURS D'EXECUTION que vous "
                "controlez - rien n'est cree automatiquement ici, aucun dossier n'est genere, "
                "et l'enregistrement n'exige PAS que la zone existe deja ou reponde. Exemple : "
                "127.0.0.1:9001. Si au moment d'une vraie requete rien n'ecoute a cette adresse, "
                "l'attaquant recoit simplement une erreur HTTP 502 Bad Gateway - jamais de "
                "crash, jamais de creation silencieuse."
            ),
            action="Ajouter/Supprimer une zone.",
            reaction="REDEMARRAGE COMPLET toujours necessaire.",
        ),
        FieldGuide(
            label="IoC (export d'indicateurs de compromission)",
            definition="Controle l'export automatique d'indicateurs a la fermeture d'un incident.",
            utilisation="Formats : json, csv, markdown. Politique de partage : local_only ou manual_export.",
            action="Enregistre avec le reste des reglages generaux.",
            reaction="REDEMARRAGE COMPLET toujours necessaire.",
        ),
        FieldGuide(
            label="Stockage et journalisation",
            definition="Emplacement de la base de donnees, du repertoire d'export, et parametres de capture enrichie (corps de requete, champs masques).",
            utilisation="Chemins relatifs au projet ; capture du corps de requete desactivee par defaut (donnees potentiellement sensibles).",
            action="Enregistre avec le reste des reglages generaux.",
            reaction="REDEMARRAGE COMPLET toujours necessaire.",
        ),
    ),
    consequences=(
        "TOUT changement ici exige un redemarrage complet, sans aucune exception - "
        "active_defense n'est jamais recharge a chaud, contrairement a la plupart des autres options."
    ),
    points_de_vigilance=(
        (
            "Sans activer 'war_mode.enabled' ICI, activer seulement l'option 'active_defense' "
            "(menu Options) ne sert a rien - voir la FAQ dediee."
        ),
        (
            "Un profil de leurre en Isolation = fixture dont le nom n'est pas exactement "
            "fake_admin, fake_cms, fake_api ou fake_secrets ne se declenchera JAMAIS - "
            "l'enregistrement le refuse desormais avec un message explicite."
        ),
        (
            "Une zone de leurre n'est jamais creee automatiquement et son existence n'est pas "
            "verifiee a l'enregistrement - si rien n'ecoute a l'adresse indiquee, l'attaquant "
            "recoit une erreur 502 au moment de la requete, pas avant."
        ),
    ),
)

THREATS_SCREEN = ScreenGuide(
    screen_class_name="ThreatsScreen",
    title="Active Defense - Menaces",
    acces="Accueil -> Active Securite -> Menaces",
    definition="Liste toutes les sources actuellement suivies par Active Defense, avec leur score et niveau de menace.",
    fields=(
        FieldGuide(
            label="Table des menaces",
            definition="Une ligne par source suivie (IP, score, niveau, derniere mise a jour, expiration).",
            utilisation="Selectionner une ligne affiche son detail complet.",
            action="Aucune action mutante sur cet ecran.",
            reaction="Purement consultatif.",
        ),
    ),
    consequences="Aucune modification possible depuis cet ecran.",
)

INCIDENTS_SCREEN = ScreenGuide(
    screen_class_name="IncidentsScreen",
    title="Active Defense - Incidents",
    acces="Accueil -> Active Securite -> Incidents",
    definition="Liste les incidents de securite ouverts/fermes, permet de les fermer et d'exporter des indicateurs de compromission (IoC).",
    fields=(
        FieldGuide(
            label="Fermer l'incident",
            definition="Marque un incident comme ferme.",
            utilisation="Selectionner un incident, puis confirmer.",
            action="Ferme l'incident immediatement.",
            reaction=(
                "Peut declencher un export IoC/rapport AUTOMATIQUE si "
                "ioc.auto_export_on_close est active dans la configuration d'Active Defense."
            ),
        ),
        FieldGuide(
            label="Exporter IoC",
            definition="Exporte les indicateurs de compromission de l'incident selectionne.",
            utilisation="Format : json ou csv.",
            action="Ecrit un fichier dans le repertoire d'export configure.",
            reaction="Ecriture reelle sur disque immediate.",
        ),
        FieldGuide(
            label="Generer rapport",
            definition="Genere un rapport Markdown complet de l'incident selectionne.",
            utilisation="Aucune saisie supplementaire.",
            action="Ecrit un fichier Markdown dans le repertoire d'export configure.",
            reaction="Ecriture reelle sur disque immediate.",
        ),
    ),
    consequences="Purement consultatif sauf fermeture d'incident (irreversible) et exports (ecriture disque).",
)

DECEPTION_SCREEN = ScreenGuide(
    screen_class_name="DeceptionScreen",
    title="Active Defense - Leurres",
    acces="Accueil -> Active Securite -> Deception",
    definition="Liste les affectations actives (et expirees non liberees) vers les leurres de deception, permet de les liberer.",
    fields=(
        FieldGuide(
            label="Liberer",
            definition="Retire l'affectation d'une source vers son leurre.",
            utilisation="Selectionner une ligne, puis confirmer.",
            action="Libere immediatement l'affectation.",
            reaction="Effet immediat - la source n'est plus redirigee vers le leurre a la prochaine requete.",
        ),
    ),
    consequences=(
        "Les affectations expirees mais jamais liberees restent visibles avec l'etat 'expiree' - "
        "distinct d'une liberation manuelle."
    ),
)

ACTIVE_DEFENSE_SIMULATE_SCREEN = ScreenGuide(
    screen_class_name="ActiveDefenseSimulateScreen",
    title="Active Defense - Simuler",
    acces="Accueil -> Active Securite -> Simuler",
    definition="Simule une decision Active Defense (score, classe d'attaque) SANS aucun effet reel - dry-run complet.",
    fields=(
        FieldGuide(
            label="IP simulee",
            definition="Adresse IP source utilisee pour la simulation.",
            utilisation="Une IP quelconque. Valeur par defaut : 203.0.113.42.",
            action="Utilisee au clic sur Simuler.",
            reaction="Aucun effet reel - aucune ecriture, aucun impact reseau.",
        ),
        FieldGuide(
            label="Chemin simule",
            definition="Chemin de la requete simulee.",
            utilisation="Chaine libre. Valeur par defaut : /wp-login.php.",
            action="Utilisee au clic sur Simuler.",
            reaction="Aucun effet reel.",
        ),
        FieldGuide(
            label="User-Agent",
            definition="User-Agent simule (participe au calcul de l'identifiant de source simule).",
            utilisation="Chaine libre, optionnelle.",
            action="Utilisee au clic sur Simuler.",
            reaction="Aucun effet reel.",
        ),
        FieldGuide(
            label="Classe d'attaque",
            definition="Type d'attaque simule.",
            utilisation="Doit etre une classe connue (ex: scan). Valeur par defaut : scan.",
            action="Utilisee au clic sur Simuler.",
            reaction="Aucun effet reel.",
        ),
        FieldGuide(
            label="Score",
            definition="Delta de score applique a la simulation.",
            utilisation="Entier. Valeur par defaut : 10.",
            action="Utilisee au clic sur Simuler.",
            reaction="Aucun effet reel.",
        ),
    ),
    consequences="Aucune - dry-run complet, jamais d'ecriture (aucun repository.save()/create() appele).",
)

WAF_STATUS_SCREEN = ScreenGuide(
    screen_class_name="WafStatusScreen",
    title="WAF - Etat",
    acces="Accueil -> Active Securite -> Etat (bloc WAF)",
    definition="Vue d'ensemble en lecture seule : mode, comportement en cas d'erreur interne, packs de regles references, taille de la blocklist.",
    fields=(),
    consequences="Purement consultatif.",
    points_de_vigilance=(
        (
            "Si aucun pack de regles n'est reference, le WAF ne peut RIEN detecter meme actif - "
            "l'ecran l'indique explicitement, corrige un vrai trou signale par l'utilisateur."
        ),
    ),
)

WAF_MODULES_SCREEN = ScreenGuide(
    screen_class_name="WafModulesScreen",
    title="WAF - Modules",
    acces="Accueil -> Active Securite -> Modules (bloc WAF)",
    definition="Trois sections : mode/comportement d'erreur, gestion des packs de regles actifs, gestion de la liste de blocage.",
    fields=(
        FieldGuide(
            label="Mode",
            definition="Comportement du WAF face a une requete jugee malveillante.",
            utilisation="log-only (journalise sans bloquer) ou block (bloque reellement).",
            action="Enregistre au clic sur Enregistrer.",
            reaction="Rechargement AUTOMATIQUE declenche des l'enregistrement si un service actif existe.",
        ),
        FieldGuide(
            label="Comportement en cas d'erreur interne",
            definition="Que faire si le moteur WAF rencontre une erreur inattendue en analysant une requete.",
            utilisation="fail-open (laisse passer) ou fail-closed (bloque par prudence).",
            action="Enregistre avec le mode.",
            reaction="Rechargement automatique.",
        ),
        FieldGuide(
            label="Packs de regles (rule_paths)",
            definition="Fichiers de regles reellement charges par le WAF - sans au moins un pack, rien n'est detecte.",
            utilisation="Ajouter ouvre un selecteur des packs presents sous secure/waf/rules/ non deja references.",
            action="Ajoute/retire une reference de pack.",
            reaction="Rechargement automatique declenche immediatement (recompile les regles en memoire).",
        ),
        FieldGuide(
            label="Liste de blocage",
            definition=(
                "IP/reseaux bannis, avec motif et expiration optionnelle. Fichier par defaut : "
                "var/lib/waf/blocklist.json (sous var/, le seul dossier ou le service systemd peut "
                "ecrire ses auto-bans). Un ancien secure/waf/blocklist.json est repris une fois au "
                "demarrage et laisse en place comme sauvegarde."
            ),
            utilisation="Reseau (CIDR), motif, duree en secondes (vide = permanent, confirmation requise dans ce cas).",
            action="Ajoute/retire une entree.",
            reaction=(
                "EFFET IMMEDIAT, sans rechargement necessaire - la blocklist est relue depuis "
                "le disque a CHAQUE requete, jamais mise en cache en memoire (contrairement au "
                "mode et aux packs de regles)."
            ),
        ),
    ),
    consequences=(
        "Mode/comportement d'erreur/packs de regles necessitent un rechargement pour s'appliquer "
        "(automatique si un service actif existe). La liste de blocage, elle, s'applique "
        "instantanement sans aucune action supplementaire."
    ),
)

WAF_TEST_SCREEN = ScreenGuide(
    screen_class_name="WafTestScreen",
    title="WAF - Tester une requete",
    acces="Accueil -> Active Securite -> Tester (bloc WAF)",
    definition="Teste une requete simulee contre les regles WAF ACTUELLEMENT ENREGISTREES (pas necessairement celles reellement chargees par un serveur deja lance), sans requete reseau.",
    fields=(
        FieldGuide(
            label="Methode / Chemin / Query / Body / IP distante",
            definition="Composants de la requete HTTP simulee.",
            utilisation="Valeurs libres - methode et chemin pre-remplis (GET, /).",
            action="Utilises au clic sur Tester.",
            reaction="Aucun effet reel, aucune requete reseau.",
        ),
    ),
    consequences="Purement consultatif.",
    points_de_vigilance=(
        (
            "Reconstruit le moteur WAF a partir de la configuration SAUVEGARDEE sur disque a "
            "chaque test - si un serveur deja lance n'a pas encore ete recharge apres un "
            "changement de regles, ce test peut refleter un comportement different de ce que ce "
            "serveur applique reellement pour l'instant."
        ),
    ),
)

WAF_CUSTOM_RULE_SCREEN = ScreenGuide(
    screen_class_name="WafCustomRuleScreen",
    title="WAF - Regles et listes personnalisees",
    acces="Accueil -> Active Securite -> Custom (bloc WAF)",
    definition=(
        "Un seul tableau pour les REGLES (ecrites dans secure/waf/rules/custom.json, pack "
        "reference automatiquement) et les LISTES (fichiers texte de secure/waf/rules/keywords/, "
        "chargees explicitement par l'assistant). La colonne Type fait la difference : une "
        "liste n'est pas une regle de custom.json."
    ),
    fields=(
        FieldGuide(
            label="Ajouter",
            definition="Ouvre l'assistant : une regle simple, ou CHARGER une liste (voir sa fiche).",
            utilisation="Clic, puis suivre l'assistant.",
            action="Regle : ecrite dans custom.json. Liste : ajoutee a options.waf.rules.keyword_lists.",
            reaction="Rechargement automatique declenche immediatement si un service actif existe.",
        ),
        FieldGuide(
            label="Colonne Detail (listes)",
            definition="Nombre d'entrees du fichier, ou un avertissement.",
            utilisation=(
                "'fichier absent', 'illisible par le service' ou 'emplacement refuse' : la liste "
                "n'est pas chargeable telle quelle - ouvrez-la avec Editer la liste."
            ),
            action="Recalcule a chaque affichage du tableau.",
            reaction="Aucun effet en lui-meme.",
        ),
        FieldGuide(
            label="Colonne Gravite (listes)",
            definition="Observation, Faible, Moyen, Eleve ou Critique, suivie de la recidive propre a la liste.",
            utilisation="Ex. 'Eleve, 2 en 10 min -> ban 24 h'.",
            action="Se change avec Modifier.",
            reaction="Aucun effet en lui-meme.",
        ),
        FieldGuide(
            label="Modifier (listes)",
            definition="Change gravite, recidive, zone de recherche et nom affiche d'une liste deja chargee.",
            utilisation="Selectionner une ligne Liste, puis Modifier.",
            action=(
                "Verifie la nouvelle configuration comme au chargement : rendre bloquante une liste "
                "qui toucherait une route du site est refuse avec la raison."
            ),
            reaction="Rechargement automatique declenche immediatement.",
        ),
        FieldGuide(
            label="Editer la liste",
            definition="Ouvre l'editeur integre sur le fichier de la liste (voir sa fiche).",
            utilisation="Selectionner une ligne Liste, puis Editer la liste.",
            action="Aucune ecriture tant que l'editeur n'a pas enregistre.",
            reaction="Le tableau est rafraichi a la fermeture de l'editeur.",
        ),
        FieldGuide(
            label="Activer/Desactiver",
            definition="Bascule une regle ou une liste sans la supprimer.",
            utilisation="Selectionner une ligne, puis cliquer.",
            action="Regle : champ enabled de custom.json. Liste : champ enabled de keyword_lists.",
            reaction="Rechargement automatique declenche immediatement.",
        ),
        FieldGuide(
            label="Supprimer / Retirer",
            definition="Supprimer une regle, ou Retirer une liste du WAF.",
            utilisation="Selectionner une ligne, puis confirmer.",
            action="Regle : retiree de custom.json. Liste : retiree de la configuration, FICHIER CONSERVE.",
            reaction="Rechargement automatique declenche immediatement.",
        ),
    ),
    consequences=(
        "Une regle ou une liste refusee par la validation est refusee ICI de la meme facon qu'elle "
        "le serait au chargement reel - jamais une double logique de validation divergente."
    ),
    points_de_vigilance=(
        (
            "Piege deja rencontre par un utilisateur : ajouter le PACK via 'Modules' n'est pas la "
            "meme chose que creer une REGLE ici - cet ecran fait desormais les deux a la fois "
            "automatiquement."
        ),
        (
            "Retirer une liste ne supprime jamais son fichier : il reste propose par l'assistant, "
            "pret a etre recharge."
        ),
    ),
)

WAF_CUSTOM_RULE_WIZARD_SCREEN = ScreenGuide(
    screen_class_name="WafCustomRuleWizardScreen",
    title="WAF - Assistant regle personnalisee / chargement de liste",
    acces="WAF - Regles et listes personnalisees -> Ajouter",
    definition=(
        "Questionnaire en langage clair pour construire une regle WAF sans connaitre les "
        "expressions regulieres (4 scenarios courants + mode Avance), OU pour CHARGER une liste "
        "de chemins / de mots-cles depuis un fichier texte. Le chargement d'une liste est une "
        "action explicite : rien n'est actif avant le clic sur Charger."
    ),
    fields=(
        FieldGuide(
            label="Que voulez-vous detecter ?",
            definition="Choisit le scenario de detection.",
            utilisation=(
                "Un chemin precis visite, un mot-cle dans l'adresse/parametres, un mot-cle "
                "envoye en formulaire (POST), un outil de scan connu (User-Agent), Avance "
                "(regex/portee libres), CHARGER une liste de chemins, CHARGER une liste de mots-cles."
            ),
            action="Change les champs affiches en dessous et leur indice.",
            reaction="Aucun effet en lui-meme.",
        ),
        FieldGuide(
            label="Valeur a detecter (mode simple)",
            definition="Le texte a repérer, saisi en clair (jamais une regex a ecrire).",
            utilisation="Un mot ou un chemin, selon le scenario choisi ci-dessus.",
            action="La regex reelle est CONSTRUITE automatiquement par le code (caracteres speciaux jamais interpretes).",
            reaction="Aucun effet avant validation sur l'ecran precedent (WafCustomRuleScreen).",
        ),
        FieldGuide(
            label="Portee / Motif (mode Avance)",
            definition="Portee et expression reguliere ecrites directement.",
            utilisation="Portee : path, query, body, headers, user_agent, referer (separes par des virgules).",
            action="Utilise tel quel si Avance est choisi.",
            reaction="Aucun effet avant validation sur l'ecran precedent.",
        ),
        FieldGuide(
            label="Gravite (regle)",
            definition="Poids de la regle dans le calcul du score de menace.",
            utilisation="Faible/Moyen/Eleve/Critique (1/3/6/9).",
            action="Inclus dans la regle produite.",
            reaction="Aucun effet avant validation sur l'ecran precedent.",
        ),
        FieldGuide(
            label="Fichier de liste (CHARGER)",
            definition="Le fichier texte qui contient la liste.",
            utilisation=(
                "Vos fichiers .txt de secure/waf/rules/keywords/ (avec leur nombre d'entrees), les "
                "references livrees avec omega-serv (sensitive-paths-hostile, sensitive-paths-probe) "
                "pas encore copiees, ou 'Nouveau fichier...' (nom en lettres, chiffres et '-')."
            ),
            action=(
                "Une reference est COPIEE dans keywords/ au chargement : c'est cette copie locale que "
                "vous modifiez, une mise a jour d'omega-serv ne l'ecrase jamais. Choisir une reference "
                "pre-remplit tous les reglages conseilles."
            ),
            reaction="Aucun effet avant Charger.",
        ),
        FieldGuide(
            label="Ou chercher (liste de chemins)",
            definition="N'importe ou dans l'adresse, ou seulement au debut.",
            utilisation=(
                "Partout attrape /blog/.env ; au debut seulement est plus prudent pour des chemins "
                "qu'un vrai site peut servir (/api, /admin)."
            ),
            action="Champ anchor de la liste (any_segment / root).",
            reaction="Aucun effet avant Charger.",
        ),
        FieldGuide(
            label="Dans quelle partie de la requete (liste de mots-cles)",
            definition="Ou chercher les mots-cles.",
            utilisation="L'adresse et ses parametres, un formulaire envoye (POST), le User-Agent, ou le Referer.",
            action="Champ scope de la liste.",
            reaction="Aucun effet avant Charger.",
        ),
        FieldGuide(
            label="Gravite (liste)",
            definition="Observation, Faible (1), Moyen (3), Eleve (6), Critique (9).",
            utilisation=(
                "Observation (conseille au premier chargement) : alertes journalisees, AUCUN blocage, "
                "aucune recidive. Eleve (6) atteint le seuil de blocage : 403 des le premier acces. "
                "Moyen (3) ne bloque jamais seul."
            ),
            action="Champs weight et observe_only de la liste.",
            reaction="Aucun effet avant Charger.",
        ),
        FieldGuide(
            label="Recidive",
            definition="Bannir apres N acces a CETTE liste en M minutes, pendant une duree choisie.",
            utilisation=(
                "'pas de recidive propre' = compteur commun du WAF. References : hostile 2 acces en "
                "10 min -> 24 h, sondage 5 en 10 min -> 1 h. Grise en Observation."
            ),
            action=(
                "Ban applicatif temporaire (blocklist, reponse 451), jamais pour l'hote local "
                "(derriere un proxy de confiance), Tailscale ou le reseau local."
            ),
            reaction="Aucun effet avant Charger.",
        ),
        FieldGuide(
            label="Ouvrir l'editeur",
            definition="Ouvre le fichier choisi dans l'editeur integre (ou la reference si pas encore copiee).",
            utilisation="Pour verifier ou adapter la liste AVANT de la charger.",
            action="Rien n'est charge dans le WAF depuis l'editeur.",
            reaction="Les nombres d'entrees sont rafraichis a la fermeture.",
        ),
        FieldGuide(
            label="Charger",
            definition="Charge la liste dans le WAF.",
            utilisation="Dernier clic de l'assistant.",
            action=(
                "Verifie, dans l'ordre : nom de fichier, syntaxe (numero de ligne en cas d'erreur), "
                "lisibilite par le compte du service, absence de doublon, conflits avec les routes du "
                "site. Si une seule verification echoue, la configuration n'est PAS modifiee. Active "
                "ensuite la reputation et l'auto-ban s'ils etaient eteints (avec un message)."
            ),
            reaction="Rechargement automatique declenche immediatement si un service actif existe.",
        ),
    ),
    consequences=(
        "Regle : ne fait qu'assembler les valeurs, l'ecriture a lieu sur l'ecran WAF - Regles et "
        "listes personnalisees. Liste : rien n'est actif tant que Charger n'a pas reussi."
    ),
    points_de_vigilance=(
        (
            "Une liste qui bloque seule (gravite >= 5) et qui toucherait une route reellement servie "
            "(alias, reverse proxy, zone Auth, fichier du webroot) est refusee : ajoutez une exception "
            "'!/chemin' dans la liste, ou chargez-la en Observation."
        ),
    ),
)

PATH_LIST_EDITOR_SCREEN = ScreenGuide(
    screen_class_name="PathListEditorScreen",
    title="WAF - Editeur de liste",
    acces="WAF - Regles et listes personnalisees -> Editer la liste (ou Assistant -> Ouvrir l'editeur)",
    definition=(
        "Editeur de texte integre, sans editeur externe, pour une liste de chemins ou de mots-cles. "
        "Tout se fait a la SOURIS : aucun raccourci clavier, le clavier ne sert qu'a la saisie "
        "(caracteres, Entree, fleches, Debut/Fin, Page prec./suiv., Retour arriere, Suppr)."
    ),
    fields=(
        FieldGuide(
            label="Syntaxe d'une liste de chemins",
            definition="Une entree par ligne, '#' = commentaire.",
            utilisation=(
                "/admin -> /admin et /admin/xxx (jamais /administrator) ; /.git/ -> tout ce qui est "
                "sous /.git/ ; /*.bak -> fichiers finissant par .bak ; !/api/v1 -> exception, "
                "toujours prioritaire sur les entrees, quel que soit l'ordre des lignes."
            ),
            action="Analysee en direct (compteur d'entrees, d'exceptions, d'erreurs et d'avertissements).",
            reaction="Les erreurs s'affichent avec leur numero de ligne ; cliquer une erreur place le curseur dessus.",
        ),
        FieldGuide(
            label="Barre d'outils",
            definition="Annuler la modif, Retablir, Couper, Copier, Coller, Selectionner la ligne, Tout selectionner, Supprimer la ligne.",
            utilisation="Clic. Le collage du terminal (clic du milieu, menu du terminal) fonctionne aussi.",
            action="Modifie le texte affiche, jamais le fichier.",
            reaction="Toujours annulable.",
        ),
        FieldGuide(
            label="Rechercher",
            definition="Trouve un texte dans la liste (casse ignoree).",
            utilisation="Taper le texte, puis Precedent / Suivant.",
            action="Selectionne l'occurrence trouvee.",
            reaction="Recommence au debut apres la derniere occurrence.",
        ),
        FieldGuide(
            label="Tester (liste de chemins)",
            definition="Indique ce que ferait la liste EN COURS d'edition d'un chemin donne.",
            utilisation="Taper un chemin (ex. /blog/.env), puis Tester.",
            action="Meme normalisation que le WAF (parametres retires, decodage URL).",
            reaction="'DETECTE par la ligne N', 'AUTORISE : exception ligne N', ou 'aucune ligne ne correspond'.",
        ),
        FieldGuide(
            label="Verifier contre mes logs (liste de chemins)",
            definition="Rejoue les requetes REUSSIES (2xx/3xx) du journal d'acces contre la liste.",
            utilisation="Chaque ligne de la liste qui aurait touche une requete probablement legitime est montree avec un exemple.",
            action="Cliquer une ligne : exception pour ce chemin, exception pour son dossier, ou suppression de la ligne.",
            reaction="Modifie le texte affiche (annulable), jamais le fichier avant Enregistrer.",
        ),
        FieldGuide(
            label="Nouveautes de la reference",
            definition="Entrees de la reference livree absentes de votre liste.",
            utilisation="Cocher celles a ajouter, puis Ajouter la selection.",
            action=(
                "Rien n'est ajoute sans etre coche. Une ligne de la reference que vous supprimez est "
                "marquee '#retire: /x' a l'enregistrement et n'est plus jamais reproposee."
            ),
            reaction="Modifie le texte affiche.",
        ),
        FieldGuide(
            label="Corriger les droits",
            definition="Rend le fichier lisible par le compte du service (omega-serv).",
            utilisation="Propose seulement si l'etat signale que le service ne peut pas lire le fichier.",
            action=(
                "Liste chaque changement de droits avant de l'appliquer, uniquement sur ce qui vous "
                "appartient - jamais via sudo."
            ),
            reaction="L'etat est recalcule.",
        ),
        FieldGuide(
            label="Enregistrer et appliquer",
            definition="Ecrit le fichier, puis recharge le serveur si la liste est chargee.",
            utilisation="Refuse tant qu'il reste une erreur.",
            action=(
                "Ecriture sure : droits et groupe conserves, nouveau fichier en 0644, refus si le "
                "fichier a ete modifie ailleurs depuis l'ouverture, ou si c'est un lien symbolique."
            ),
            reaction=(
                "Le rechargement n'est declenche que si la verification de la liste reussit - sinon "
                "la raison est affichee et le serveur garde ses regles actuelles."
            ),
        ),
        FieldGuide(
            label="Fermer / Aide",
            definition="Fermer l'editeur, ou ouvrir cette fiche.",
            utilisation="Clic.",
            action="Fermer demande une confirmation s'il reste des modifications non enregistrees.",
            reaction="Retour a l'ecran precedent.",
        ),
    ),
    consequences=(
        "Le fichier n'est jamais modifie avant Enregistrer. Un fichier non modifiable par votre "
        "compte s'ouvre en LECTURE SEULE, avec la raison."
    ),
    points_de_vigilance=(
        (
            "Echap et F1 ne font rien ici, volontairement (aucun raccourci) : utilisez Fermer et Aide. "
            "Seul ctrl+q reste actif pour quitter l'application, avec confirmation."
        ),
        (
            "L'etat en bas de l'ecran indique si le compte du service peut lire le fichier : un fichier "
            "illisible ferait echouer le prochain rechargement."
        ),
    ),
)

KEYWORD_LIST_SETTINGS_SCREEN = ScreenGuide(
    screen_class_name="KeywordListSettingsScreen",
    title="WAF - Modifier une liste",
    acces="WAF - Regles et listes personnalisees -> Modifier (ligne Liste)",
    definition="Change les reglages d'une liste deja chargee, sans toucher a son fichier.",
    fields=(
        FieldGuide(
            label="Nom affiche / Ou chercher / Gravite / Recidive",
            definition="Memes choix que dans l'assistant (voir sa fiche).",
            utilisation="Passer d'Observation a une gravite bloquante une fois les alertes lues.",
            action="Verifie la nouvelle configuration avant de l'ecrire.",
            reaction="Rechargement automatique ; refus affiche avec sa raison si la verification echoue.",
        ),
    ),
    consequences="Rendre une liste bloquante reactive la reputation et l'auto-ban s'ils avaient ete eteints.",
)

WAF_MAGNET_SCREEN = ScreenGuide(
    screen_class_name="WafMagnetScreen",
    title="WAF - Magnet (import d'un WAF externe)",
    acces="Accueil -> Active Securite -> Magnet (bloc WAF)",
    definition=(
        "Importe un script WAF mod_magnet Lighttpd EXISTANT (ecrit pour un autre site) sans le "
        "reecrire, comme renfort additif au WAF natif - il ne peut jamais lever un blocage deja "
        "decide par le natif. Seuls les chemins personnels du script (fichiers de log/blocage) se "
        "dissocient ici, jamais la logique du script lui-meme."
    ),
    fields=(
        FieldGuide(
            label="Actif (oui/non)",
            definition="Active ou desactive le script magnet.",
            utilisation="oui ou non.",
            action="Enregistre au clic sur Enregistrer.",
            reaction="Rechargement automatique declenche si un service actif existe.",
        ),
        FieldGuide(
            label="Script (chemin relatif au projet)",
            definition="Le fichier Lua a importer - une liste des scripts trouves sous secure/waf/scripts/ est affichee en indice.",
            utilisation="Chemin relatif au projet, ex. secure/waf/scripts/waf.lua.",
            action="Enregistre avec Actif.",
            reaction="Aucun effet avant Enregistrer - utiliser Verifier la compatibilite pour tester sans rien ecrire.",
        ),
        FieldGuide(
            label="Delai maximum par appel (ms) / Comportement en cas d'erreur",
            definition="Borne le temps d'execution du script par requete, et la decision prise si le script plante ou depasse ce delai.",
            utilisation="Delai en millisecondes ; ignore (laisse passer) ou fail-closed (bloque par prudence).",
            action="Enregistre avec Actif.",
            reaction="fail-closed combine a une incompatibilite detectee peut bloquer du trafic legitime - avertissement explicite affiche par Verifier la compatibilite dans ce cas.",
        ),
        FieldGuide(
            label="Chemins personnels dissocies",
            definition=(
                "5 chemins (blocklist, dossier de regles, 2 journaux, fichier de persistance du "
                "rate limiting) injectes dans le script a la place de ses chemins en dur d'origine - "
                "propre a chaque script importe, jamais un contrat generique. Blocklist par defaut : "
                "var/lib/waf/magnet-blocklist.txt (le script y ECRIT ; un ancien "
                "secure/waf/magnet-blocklist.txt est repris une fois). Un chemin choisi a la main doit "
                "rester inscriptible par le compte du service, sinon les bans sont perdus sans message."
            ),
            utilisation="Vide = le script garde son propre chemin en dur (aucune injection pour ce champ).",
            action="Enregistre avec Actif.",
            reaction="Les dossiers parents sont crees automatiquement a l'usage reel (jamais lors d'un simple 'config check').",
        ),
        FieldGuide(
            label="Verifier la compatibilite",
            definition="Execute REELLEMENT le script avec les valeurs du formulaire EN COURS DE SAISIE, pas seulement celles deja enregistrees.",
            utilisation="A utiliser avant d'activer un script importe en production - repond a 'ce script est-il compatible ?'.",
            action="Scan statique (membres lighty.* non supportes) + execution reelle sur une requete de test benigne.",
            reaction="Aucun effet sur le serveur ni sur la configuration enregistree - purement diagnostique.",
        ),
    ),
    consequences="Le natif reste toujours actif en parallele - le magnet ne peut qu'ajouter un blocage, jamais en lever un.",
    points_de_vigilance=(
        (
            "Un script importe peut referencer une fonctionnalite lighty.* non supportee par ce "
            "pont (toujours nil cote Lua) - toujours lancer Verifier la compatibilite avant "
            "d'activer un nouveau script en production, surtout avec on_error=fail-closed."
        ),
    ),
)

WAF_RULE_PACK_PICKER_SCREEN = ScreenGuide(
    screen_class_name="WafRulePackPickerScreen",
    title="WAF - Choix d'un pack de regles",
    acces="WAF - Modules -> Ajouter un pack",
    definition="Liste REELLE des packs de regles presents sous secure/waf/rules/, exclut ceux deja references - jamais de doublon propose.",
    fields=(
        FieldGuide(
            label="Selection du pack",
            definition="Choisit un pack parmi ceux disponibles et non deja references.",
            utilisation="Un menu deroulant, avec la description du pack (nombre de regles, etat par defaut) affichee en dessous.",
            action="Confirmer renvoie le chemin choisi a l'ecran Modules.",
            reaction="Aucun effet ici - la reference reelle est ajoutee par l'ecran appelant.",
        ),
    ),
    consequences="Aucune modification directe - purement une aide de selection.",
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
    WAF_TEST_SCREEN,
    WAF_CUSTOM_RULE_SCREEN,
    WAF_CUSTOM_RULE_WIZARD_SCREEN,
    PATH_LIST_EDITOR_SCREEN,
    KEYWORD_LIST_SETTINGS_SCREEN,
    WAF_RULE_PACK_PICKER_SCREEN,
    WAF_MAGNET_SCREEN,
)
