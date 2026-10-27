"""FAQ du guide d'aide (plan guide d'aide §3.7, Phase 0 - amorcee avec
l'incident fondateur de ce chantier ; completee Phase 10 avec les
pieges reels deja documentes au fil de OMEGA-SERV_PLAN-DETAILLE_
INTERFACE.md et plan_active_defense_omega_serv.md)."""
from __future__ import annotations

from omega_serv.core.i18n import _
from omega_serv.interfaces.tui.guide.model import FaqEntry

FAQ_ENTRIES: tuple[FaqEntry, ...] = (
    FaqEntry(
        category=_("Redémarrage et rechargement"),
        question=_("J'ai active/modifie une option, mais rien ne change sur le serveur - pourquoi ?"),
        answer=(
            _("Le serveur tourne dans un PROCESSUS DÉJÀ LANCÉ, séparé de l'interface. Écrire un "
            "changement dans le fichier de configuration ne le fait jamais relire tout seul par "
            "ce processus : il faut soit le RECHARGER (SIGHUP, écran SERVICE -> Recharger - "
            "léger, aucune coupure de connexion), soit le REDÉMARRER COMPLÈTEMENT (coupe toutes "
            "les connexions en cours). La plupart des écrans de configuration détaillée "
            "déclenchent désormais ce rechargement automatiquement dès qu'un service systemd "
            "actif est détecté, et vous avertissent sinon. Quelques réglages (bind/port, "
            "listen_backlog, TLS, 1ere activation de fastcgi/reverse_proxy, active_defense) "
            "exigent toujours un redémarrage complet - jamais un simple rechargement - car ils "
            "touchent le socket d'écoute ou des composants construits une seule fois au démarrage.")
        ),
    ),
    FaqEntry(
        category=_("Redémarrage et rechargement"),
        question=_("Après une mise à jour d'omega-serv, mes nouveaux réglages ne s'appliquent pas alors que le service est « rechargé » - pourquoi ?"),
        answer=(
            _("Un rechargement ne relit que la configuration, jamais le programme déjà chargé en "
            "mémoire. Si le service tournait déjà avant l'extraction de la mise à jour, il exécute "
            "toujours l'ancienne version, qui ignore les réglages apparus depuis. Redémarrez le "
            "service une fois après chaque mise à jour (écran SERVICE -> Redémarrer). L'interface "
            "le signale : notification à l'accueil, et avertissement après chaque rechargement, "
            "tant que le service n'a pas été redémarré (systemd et runit).")
        ),
    ),
    FaqEntry(
        category=_("Redémarrage et rechargement"),
        question=_("Comment savoir si un changement précis a besoin d'un rechargement ou d'un redémarrage complet ?"),
        answer=(
            _("La réaction exacte de chaque champ est indiquée dans sa fiche du guide (touche F1 "
            "depuis l'écran concerne). En règle générale : tout ce qui touche le socket "
            "d'écoute (adresse, port, listen_backlog), le contexte TLS, ou un composant "
            "construit une seule fois au démarrage (client FastCGI/reverse proxy à la première "
            "activation, Active Defense) exige un redémarrage complet. Tout le reste se "
            "recharge à chaud.")
        ),
    ),
    FaqEntry(
        category=_("Redémarrage et rechargement"),
        question=(
            _("J'ai mis à jour le code d'OMEGA-SERV (nouvelle archive, correctif appliqué) mais le "
            "comportement ne change jamais, même après un rechargement (SIGHUP) - pourquoi ?")
        ),
        answer=(
            _("Piège réel rencontré (2026-10-10, correctif du rendu du directory listing sous une "
            "CSP stricte) : le rechargement à chaud (SIGHUP, écran SERVICE -> Recharger) ne relit "
            "QUE certains éléments de CONFIGURATION (règles WAF, zones d'authentification) - il "
            "ne recharge JAMAIS le CODE Python lui-même, qui reste celui chargé en mémoire depuis "
            "le DERNIER DÉMARRAGE du processus, aussi anciens soient les fichiers sur disque. "
            "Après une mise à jour du code (nouvelle archive installée, correctif appliqué), un "
            "REDÉMARRAGE COMPLET est TOUJOURS nécessaire (`systemctl restart <service>`, ou écran "
            "SERVICE -> Arrêter puis Démarrer) - jamais un simple rechargement, même pour un "
            "changement qui semble léger. Vérifiez `systemctl status <service>` : une date de "
            "démarrage ('Active: active (running) since ...') plus ancienne que votre mise à jour "
            "confirme immédiatement ce diagnostic.")
        ),
    ),
    FaqEntry(
        category=_("Redémarrage et rechargement"),
        question=_("Le rechargement/redemarrage automatique ne s'est pas déclenché - pourquoi ?"),
        answer=(
            _("Le déclenchement automatique ne fonctionne que si un gestionnaire de service "
            "système (systemd/OpenRC/runit) est reconnu ET qu'un service est réellement ACTIF "
            "pour ce répertoire. Si vous faites tourner le serveur via l'assistant premier "
            "lancement (\"Lancer maintenant\", sans service installé), aucun rechargement "
            "automatique n'est possible - relancez manuellement, ou installez le service depuis "
            "l'écran SERVICE.")
        ),
    ),
    FaqEntry(
        category=_("Service système"),
        question=_("Juste après 'Installer l'unité', l'écran État & Ressources affiche 'Arrêté' alors que le service tourne - pourquoi ?"),
        answer=(
            _("L'installation crée un compte système dédié et ajoute votre session au groupe "
            "correspondant, mais l'appartenance à un NOUVEAU groupe Unix ne s'applique jamais à "
            "une session déjà ouverte (même terminal déjà lancé avant l'installation). "
            "Déconnectez-vous puis reconnectez-vous UNE SEULE FOIS - l'écran affichera alors "
            "l'état réel. En attendant, vérifiez via l'écran SERVICE ou `systemctl status`.")
        ),
    ),
    FaqEntry(
        category=_("Service système"),
        question=_("Le champ 'Nom du service' dans l'écran SERVICE ne correspond pas à ce que je pilote ailleurs - pourquoi ?"),
        answer=(
            _("Ce champ persiste une préférence d'interface, distincte de la configuration serveur. "
            "Si cette instance est enregistrée en multi-instance, le nom est FIGÉ (celui choisi à "
            "la création) - jamais improvisé ici. Une seule interface peut déjà piloter "
            "n'importe quelle unité installée en tapant simplement son nom exact, même celle "
            "d'une autre copie du projet.")
        ),
    ),
    FaqEntry(
        category=_("Multi-instance"),
        question=_("Puis-je installer une seconde unité systemd qui pointe vers le même répertoire, sous un autre nom ?"),
        answer=(
            _("Non - deux garde-fous bloquent explicitement cette situation avant toute écriture : "
            "une unité différente pointant déjà vers ce répertoire (partagerait silencieusement "
            "var/, la configuration et le compte système dédié), et un nom déjà utilisé par une "
            "unité pointant vers un AUTRE répertoire (volerait ce nom, écrasant l'unité "
            "existante). Pour héberger plusieurs serveurs, utilisez Multi-instance : chaque "
            "instance a son propre répertoire, sa propre configuration et son propre compte système.")
        ),
    ),
    FaqEntry(
        category=_("Multi-instance"),
        question=_("La création d'une nouvelle instance échoue à l'étape 4/6 (Installation des dépendances) - pourquoi ?"),
        answer=(
            _("Piège réel corrigé : si le message d'échec mentionne 'omega-lib' et 'No matching "
            "distribution found', c'était un bug de la création d'instance elle-même, pas une "
            "erreur de votre part - omega-lib n'est pas publiée sur PyPI, et l'ancienne version "
            "ne savait retrouver sa source réelle (vendorée ou depuis un clone de développement) "
            "que dans un seul des deux cas. Corrigé : la nouvelle instance réutilise désormais "
            "la même source qu'omega-lib déjà installée pour l'instance en cours, quelle que "
            "soit sa provenance. Si l'échec persiste malgré une version à jour, vérifiez que le "
            "réseau est disponible pour les AUTRES dépendances (`textual`, `pyte`, `jinja2`, "
            "`psutil`), qui viennent bien de PyPI.")
        ),
    ),
    FaqEntry(
        category=_("WAF/Active Defense"),
        question=_("Le WAF est actif mais ne bloque jamais rien - pourquoi ?"),
        answer=(
            _("Vérifiez d'abord l'écran WAF - État : si 'Packs de règles référencés' est à zéro, le "
            "WAF ne peut RIEN détecter même actif (piège réel déjà rencontré). Ajoutez au moins "
            "un pack depuis WAF - Modules. Vérifiez ensuite le mode : 'log-only' journalise sans "
            "jamais bloquer, seul 'block' bloque réellement.")
        ),
    ),
    FaqEntry(
        category=_("WAF/Active Defense"),
        question=_("J'ai activé l'option 'active_defense' mais rien ne se passe jamais (aucune menace, aucun incident) - pourquoi ?"),
        answer=(
            _("Activer l'option elle-même (menu Options) ne suffit PAS. Un second interrupteur, "
            "`war_mode.enabled`, vaut FALSE par défaut - activez-le depuis Active Defense -> "
            "Réglages -> 'Mode guerre actif'. Vérifiez la ligne 'Mode guerre' sur l'écran "
            "Active Defense - État : si elle affiche 'inactif', c'est la cause. Un REDÉMARRAGE "
            "COMPLET est ensuite nécessaire (active_defense n'est jamais rechargé à chaud). Une "
            "fois actif, tout devient automatique - le score de chaque source est alimenté par "
            "les décisions WAF déjà calculées à chaque requête, sans aucune action manuelle.")
        ),
    ),
    FaqEntry(
        category=_("WAF/Active Defense"),
        question=_("Active Defense en production : quelles limites connaître ?"),
        answer=(
            _("Mesuré sur une machine à 2 cœurs : aucun coût sans attaque. Face à des attaquants "
            "qui reviennent, le mode guerre les ralentit (environ 0,4 s par requête) et le serveur "
            "sert même plus vite les visiteurs légitimes. Face à un botnet qui change d'adresse à "
            "chaque requête, Active Defense coûte de 10 à 16 % de débit. La base est bornée : au "
            "plus 200 000 sources suivies (les sources « normal » les plus anciennes partent "
            "d'abord), journal d'audit purgé au-delà de 30 jours et de 200 000 lignes, historique "
            "d'un incident limité aux 100 premiers et aux 1 000 derniers éléments. La purge des "
            "états expirés est automatique (au plus toutes les 10 minutes) ; le fichier de la base "
            "ne rétrécit pas, SQLite réutilise la place libérée. Sauvegardez la base avec "
            "`config backup --include-active-defense`.")
        ),
    ),
    FaqEntry(
        category=_("WAF/Active Defense"),
        question=_("Une purge ou une sauvegarde pendant une attaque peut-elle bloquer le serveur ?"),
        answer=(
            _("Non : le serveur écrit dans la base d'Active Defense depuis un fil d'arrière-plan, "
            "jamais pendant une requête. Si la base est verrouillée (purge, sauvegarde, autre "
            "programme), les écritures attendent puis reprennent seules ; error.log reçoit une "
            "ligne au début (« écriture en base impossible ») et une à la fin (« rétablie »). "
            "Au-delà de 10 000 observations en attente, les suivantes sont abandonnées et "
            "comptées ; les requêtes, elles, sont toujours servies.")
        ),
    ),
    FaqEntry(
        category=_("WAF/Active Defense"),
        question=_("Comment partager un incident avec MISP ou OpenCTI ?"),
        answer=(
            _("Exportez-le au format misp ou stix (écran Incidents -> Exporter IoC, ou "
            "`incidents export-ioc <id> --format stix,misp`). Dans MISP : Add Event -> Populate "
            "from -> MISP JSON, puis le fichier .misp.json. Dans OpenCTI ou un SIEM : importez le "
            "bundle .stix.json. Les fichiers restent sur votre serveur, omega-serv n'envoie rien. "
            "Le marquage TLP se règle dans Active Defense -> Réglages (amber par défaut). Seules "
            "les adresses IP sont exportées ; l'adresse d'un attaquant reste une donnée "
            "personnelle : vérifiez avant de partager.")
        ),
    ),
    FaqEntry(
        category=_("WAF/Active Defense"),
        question=_("J'ai créé une règle WAF personnalisée mais elle ne se déclenche jamais - pourquoi ?"),
        answer=(
            _("Utilisez l'écran WAF - Règles personnalisées (pas 'Modules') pour CRÉER la règle "
            "elle-même - il l'écrit dans custom.json ET référence automatiquement ce pack. "
            "Ajouter seulement le pack custom.json comme référence depuis 'Modules' ne crée "
            "aucune règle si le fichier est encore vide. Utilisez l'écran 'Tester une requête' "
            "pour vérifier qu'une règle se déclenche bien avant de compter dessus en production.")
        ),
    ),
    FaqEntry(
        category=_("WAF/Active Defense"),
        question=_("Quelle classe d'attaque choisir pour un profil de leurre ?"),
        answer=(
            _("Les 8 classes possibles et ce qu'elles ciblent concrètement : scan (sondage "
            "d'URLs/ports, scanners automatisés), credential_stuffing (essais massifs de "
            "mots de passe sur un formulaire de login), sqli (tentative d'injection SQL), "
            "xss (script injecté dans un paramètre), path_traversal (tentative de sortir du "
            "dossier servi, ex : ../../etc/passwd), upload_probe (upload de fichier suspect), "
            "api_probe (sondage d'endpoints /api/...), unknown (tout ce qui ne correspond à "
            "aucune des catégories précédentes - un filet de sécurité générique). Exemple : "
            "un profil nommé fake_admin avec les classes scan,credential_stuffing attirera les "
            "scanners et les tentatives de bruteforce de connexion vers une fausse page "
            "d'authentification. Plusieurs classes peuvent être listées, séparées par des virgules.")
        ),
    ),
    FaqEntry(
        category=_("WAF/Active Defense"),
        question=_("Mon profil de leurre en isolation 'fixture' ne se déclenche jamais - pourquoi ?"),
        answer=(
            _("Le NOM du profil doit correspondre EXACTEMENT à l'une des 4 fixtures réellement "
            "implémentées : fake_admin, fake_cms, fake_api, fake_secrets. Tout autre nom "
            "(même descriptif, ex : 'mon-leurre-perso') faisait auparavant que le leurre ne "
            "se déclenchait jamais, sans aucune erreur visible - le trafic suivait alors le "
            "comportement de secours (pass_through ou reject) comme si aucun profil n'existait. "
            "L'écran Active Defense -> Réglages refuse désormais d'enregistrer un tel nom et "
            "indique clairement le problème.")
        ),
    ),
    FaqEntry(
        category=_("WAF/Active Defense"),
        question=_("J'ai créé une zone de leurre avec une adresse qui n'existe pas encore - que se passe-t-il ?"),
        answer=(
            _("Rien de spécial à l'enregistrement : une zone de leurre (Niveau 2, isolation "
            "'proxy') est une simple cible réseau (host:port), jamais un dossier - aucune "
            "création automatique, aucune vérification que l'adresse existe ou répond au "
            "moment de la sauvegarde. La conséquence n'apparaît que lors d'une VRAIE requête "
            "routée vers cette zone : si rien n'écoute à cette adresse, l'attaquant reçoit "
            "simplement une erreur HTTP 502 Bad Gateway (la même mécanique que le reverse "
            "proxy de production) - jamais de crash du serveur, jamais de création silencieuse "
            "de quoi que ce soit.")
        ),
    ),
    FaqEntry(
        category=_("WAF/Active Defense"),
        question=_("Comment bloquer les chemins sensibles (.env, .git, sauvegardes, consoles d'admin...) sans tout écrire à la main ?"),
        answer=(
            _("Active Sécurité -> Custom -> Ajouter -> 'CHARGER une liste de chemins (fichier)', puis "
            "choisissez la référence livrée sensitive-paths-hostile (298 chemins sans usage "
            "légitime) et/ou sensitive-paths-probe (132 chemins de sondage, parfois servis par un "
            "vrai site). Les réglages conseillés se remplissent seuls ; gardez Observation au "
            "premier chargement. Rien n'est actif avant le clic sur Charger.")
        ),
    ),
    FaqEntry(
        category=_("WAF/Active Defense"),
        question=_("Quelle différence entre une règle personnalisée et une liste ?"),
        answer=(
            _("Une règle détecte UN motif et vit dans custom.json. Une liste est un fichier texte d'un "
            "chemin (ou mot-clé) par ligne, facile à maintenir à plusieurs centaines d'entrées, avec "
            "ses exceptions '!/x', sa gravité et sa propre récidive. Les deux apparaissent dans le "
            "même tableau de l'écran Custom, colonne Type.")
        ),
    ),
    FaqEntry(
        category=_("WAF/Active Defense"),
        question=_("J'ai chargé une liste en Observation - comment savoir ce qu'elle aurait bloqué, puis l'activer ?"),
        answer=(
            _("En Observation, chaque détection est écrite dans le journal d'alertes WAF, sans aucun "
            "blocage ni ban. Lisez ces alertes quelques jours, utilisez 'Vérifier contre mes logs' "
            "dans l'éditeur pour repérer les lignes qui toucheraient des requêtes légitimes "
            "(exception '!/chemin' en un clic), puis Custom -> Modifier -> Gravité Élevé ou Moyen.")
        ),
    ),
    FaqEntry(
        category=_("WAF/Active Defense"),
        question=_("Mes propres machines (Wi-Fi, Ethernet, Tailscale) risquent-elles d'être bannies par la récidive ?"),
        answer=(
            _("Non : l'hôte local, le réseau Tailscale (100.64.0.0/10) et le réseau local (192.168.x, "
            "10.x, 172.16-31.x...) ne sont JAMAIS bannis automatiquement (réglage "
            "options.waf.reputation.never_auto_block). Seule une adresse publique peut l'être. Leurs "
            "requêtes vers un chemin dangereux restent refusées (403) et journalisées, ce qui permet "
            "de tester le WAF. Derrière un proxy local (tailscale serve, reverse proxy), l'exemption "
            "de 127.0.0.1 n'est appliquée que si 'Proxy de confiance' est actif - sinon tout Internet "
            "paraîtrait venir de 127.0.0.1.")
        ),
    ),
    FaqEntry(
        category=_("WAF/Active Defense"),
        question=_("Mettre mes adresses dans 'Proxy de confiance' évite-t-il qu'elles soient bannies ?"),
        answer=(
            _("Non. Les réseaux de confiance disent seulement QUI a le droit de transmettre la vraie "
            "adresse du visiteur (en-tête X-Forwarded-For) - en pratique le proxy place devant "
            "omega-serv (127.0.0.1 pour tailscale serve). Ils n'exemptent de rien d'autre. Les "
            "réseaux à ne jamais bannir sont un réglage distinct (never_auto_block). Une plage large "
            "comme 100.0.0.0/8 contient des adresses publiques : préférez 100.64.0.0/10.")
        ),
    ),
    FaqEntry(
        category=_("WAF/Active Defense"),
        question=_("Une page lourde renvoie 429, puis mon IP est bannie - pourquoi ?"),
        answer=(
            _("Une page qui charge beaucoup de fichiers (une galerie d'images, par exemple) dépasse "
            "la limite de débit globale du WAF (60 requêtes / 60 s par IP par défaut) : le WAF répond "
            "429, et trois rejets en 10 minutes suffisent à omega-jail pour bannir une IP publique "
            "12 h. Solution : Active Sécurité -> Exclusions et débit, ajouter une règle pour le dossier "
            "concerné (ex. /images/ à 600 / 60 s). Pour vos propres appareils (Tailscale, réseau "
            "local), une règle IP/réseau avec « Source sûre » à oui évite tout bannissement. Une "
            "exclusion d'inspection ne suffit pas : le rate limit s'applique quand même.")
        ),
    ),
    FaqEntry(
        category=_("WAF/Active Defense"),
        question=_("« Requêtes max par connexion keep-alive » et la limite de débit du WAF font-ils double emploi ?"),
        answer=(
            _("Non, ils ne se chevauchent pas. « Requêtes max par connexion keep-alive » (Résistance et "
            "limites, défaut 30) ferme seulement une connexion après N requêtes : le navigateur en "
            "ouvre une nouvelle aussitôt, sans erreur ni bannissement. La limite de débit du WAF "
            "compte les requêtes par IP sur toutes ses connexions et répond 429 au-delà. Monter ou "
            "baisser l'un ne change rien à l'autre : un 429 se règle toujours dans Exclusions et débit.")
        ),
    ),
    FaqEntry(
        category=_("WAF/Active Defense"),
        question=_("J'ai modifié une liste mais le serveur ne l'applique pas - pourquoi ?"),
        answer=(
            _("Le message affiché après 'Enregistrer et appliquer' donne la raison : (1) la liste n'est "
            "pas encore chargée dans le WAF (utilisez l'assistant -> Charger) ; (2) la vérification a "
            "trouvé un problème (le serveur garde alors ses règles actuelles, rien n'est rechargé à "
            "moitié) ; (3) le compte du service ne peut pas lire le fichier ('Corriger les droits') ; "
            "(4) aucun service actif - relancez le serveur lancé à la main.")
        ),
    ),
    FaqEntry(
        category=_("WAF - Magnet (import d'un WAF externe)"),
        question=_("J'ai activé le script magnet mais le serveur refuse de démarrer / l'écran signale 'lupa' absent - pourquoi ?"),
        answer=(
            _("Le magnet est un extra OPTIONNEL, jamais installé par défaut : `pip install -e "
            "\".[magnet]\"` (dépendance `lupa`, liaison Lua embarquée - aucun interpréteur Lua "
            "système requis, une roue précompilée existe pour les plateformes courantes). Son "
            "absence est signalée par le registre des capacités (capacité `waf-magnet`, écran "
            "Capacités) avec la commande exacte, et bloque `config check`/le démarrage si "
            "`options.waf.magnet.enabled` est actif sans cette dépendance - jamais un échec silencieux.")
        ),
    ),
    FaqEntry(
        category=_("WAF - Magnet (import d'un WAF externe)"),
        question=(
            _("Le but du magnet, c'est d'écrire un nouveau WAF en Lua ?")
        ),
        answer=(
            _("Non - c'est l'inverse : importer un script WAF `mod_magnet` Lighttpd EXISTANT, "
            "écrit à l'origine pour un autre site, SANS le réécrire. Le pont `lighty.*` "
            "(infrastructure/waf/lua_waf_adapter.py) reproduit le modèle d'exécution réel de "
            "Lighttpd (`lighty.env`, `lighty.header`/`lighty.content`, convention de retour "
            "0=continuer / code HTTP=bloquer, runtime Lua persistant pour que les compteurs internes "
            "du script - rate limiting, blocklist progressive - survivent entre requêtes) plutôt "
            "qu'un contrat inventé par OMEGA-SERV. Le natif reste TOUJOURS actif en parallèle : le "
            "magnet est un renfort additif, il ne peut jamais lever un blocage déjà décidé par le natif.")
        ),
    ),
    FaqEntry(
        category=_("WAF - Magnet (import d'un WAF externe)"),
        question=_("Comment savoir si un script magnet que j'importe est compatible AVANT de l'activer en production ?"),
        answer=(
            _("Écran Active Sécurité -> WAF -> Magnet, bouton 'Vérifier la compatibilité' (ou "
            "`omega-serv waf test` en CLI) - exécute RÉELLEMENT le script avec les valeurs du "
            "formulaire en cours de saisie, pas seulement celles déjà enregistrées. Deux contrôles "
            "combinés : un scan statique signale toute référence `lighty.X` non supportée par ce "
            "pont (reste toujours `nil` côté Lua - un script bien écrit dégrade via son propre "
            "repli `or`, un script qui ne dégrade pas remonte une erreur réelle, capturée par le "
            "second contrôle) ; un smoke test exécute le script pour de vrai sur une requête de "
            "test bénigne. Les deux s'affichent comme avertissements explicites, jamais une "
            "vérification cachée.")
        ),
    ),
    FaqEntry(
        category=_("WAF - Magnet (import d'un WAF externe)"),
        question=_("J'ai activé un script magnet avec on_error='fail-closed' et maintenant du trafic légitime se fait bloquer - pourquoi ?"),
        answer=(
            _("`fail-closed` bloque TOUTE requête qui déclenche une erreur du script (incompatibilité, "
            "exception Lua, timeout) - une politique volontairement stricte, mais dangereuse "
            "combinée à un script jamais vérifié au préalable : une seule incompatibilité non "
            "détectée peut alors bloquer tout le trafic qui l'atteint. Lancez 'Vérifier la "
            "compatibilité' (voir question précédente) avant d'activer fail-closed en production - "
            "un avertissement explicite s'affiche précisément quand ces deux conditions se "
            "combinent. En cas de doute, repassez `on_error` à 'ignore' (le défaut) : le trafic "
            "continue d'être traité par le natif seul si le magnet échoue.")
        ),
    ),
    FaqEntry(
        category=_("WAF - Magnet (import d'un WAF externe)"),
        question=_("Les logs/la blocklist de mon script magnet importe n'apparaissent jamais sur le disque - pourquoi ?"),
        answer=(
            _("Un script `mod_magnet` écrit typiquement ses logs/sa blocklist à des chemins ABSOLUS "
            "en dur (ex. `/etc/blocklist.txt`, `/var/log/...`) propres à son site d'origine - ces "
            "chemins n'ont aucune raison d'exister sur cette machine. La dissociation se fait via "
            "`options.waf.magnet.paths` (écran Magnet), injectés dans le script comme table Lua "
            "globale `omega_magnet_paths` : seule une COPIE adaptée du script (les 5 lignes de "
            "configuration modifiées pour lire cette table, avec repli sur le chemin en dur "
            "d'origine si absente) en bénéficie - le script importe lui-même doit être adapté une "
            "fois, manuellement (méthode générique, mais noms de chemins propres à chaque script). "
            "`secure/waf/scripts/waf.lua` (chemin par défaut de `options.waf.magnet.script`) est "
            "livre comme exemple minimal montrant cette technique - un vrai script importe (qui "
            "porte forcément la logique propre à SON site d'origine, jamais généralisable à "
            "l'avance) n'a jamais vocation à être redistribué tel quel à d'autres installations.")
        ),
    ),
    FaqEntry(
        category=_("WAF - Magnet (import d'un WAF externe)"),
        question=_("Mon script magnet écrit une page HTML personnalisée (lighty.content) en cas de blocage - pourquoi je ne la vois jamais ?"),
        answer=(
            _("Choix délibéré, cohérent avec le reste du projet : le moteur WAF (natif ou magnet) "
            "rend TOUJOURS une décision, jamais une page HTML - c'est le serveur qui rend "
            "systématiquement sa propre page d'erreur générique. Les écritures `lighty.header`/"
            "`lighty.content` d'un script importe sont acceptées (le script ne plante jamais pour "
            "les avoir faites) mais jamais relues ni renvoyées au visiteur.")
        ),
    ),
    FaqEntry(
        category=_("Gestion des logs"),
        question=_("Les boutons de log 'waf magnet (alertes/blocklist)' restent grises dans l'écran Voir/Suivre - pourquoi ?"),
        answer=(
            _("Ces deux logs sont proposes d'office (même si le magnet n'est jamais configuré), mais "
            "restent désactivés tant que `options.waf.magnet.enabled` n'est pas réellement actif - "
            "évite un clic qui ne mènerait qu'à un message d'erreur. Une fois actif, un clic "
            "fonctionne même si le fichier n'existe pas encore (log vide, jamais une erreur - "
            "aucune alerte déclenchée pour l'instant). Côté `lnav` (logs fusionnés), ces mêmes logs "
            "sont déjà cochables sans cette restriction : un log absent y est simplement ignore au "
            "lancement, sans bloquer les autres.")
        ),
    ),
    FaqEntry(
        category=_("Sécurité - CSP et en-têtes"),
        question=_("J'ai ajouté une zone CSP pour un dossier, et maintenant ce dossier semble avoir perdu d'autres protections - pourquoi ?"),
        answer=(
            _("Une zone CSP REMPLACE ENTIÈREMENT la politique par défaut pour son préfixe - jamais "
            "une fusion/un simple ajout. Une zone qui ne contient que `style-src 'self' "
            "'unsafe-inline'` par exemple fait disparaître toutes les AUTRES directives "
            "(`object-src`, `frame-ancestors`...) sous ce préfixe, qui retombent alors sur le "
            "comportement par défaut du navigateur plutôt que sur la politique globale stricte. "
            "L'assistant d'ajout de zone (écran Sécurité générique -> Ajouter une zone) existe "
            "exactement pour éviter ce piège : chaque directive y est pré-remplie avec sa valeur "
            "ACTUELLE (la politique globale), à modifier uniquement là où c'est nécessaire.")
        ),
    ),
    FaqEntry(
        category=_("Sécurité - CSP et en-têtes"),
        question=_("Comment autoriser 'unsafe-inline' (ou une source moins stricte) uniquement pour un dossier précis, sans affaiblir le reste du site ?"),
        answer=(
            _("Zones CSP (`security.csp_zones`, écran Sécurité générique) : une exception EXPLICITE "
            "par préfixe de chemin, jamais une relâche globale. L'assistant d'ajout détecte toute "
            "directive relâchée ('unsafe-inline'/'unsafe-eval'/source générique '*') et exige une "
            "confirmation explicite supplémentaire avant d'enregistrer. Cette zone reste ensuite "
            "TOUJOURS visible dans `omega-serv audit security` (règles CSP-001/CSP-002, qui "
            "scannent aussi les zones, pas seulement la politique globale) - même délibérée, "
            "jamais silencieuse.")
        ),
    ),
    FaqEntry(
        category=_("Sécurité - CSP et en-têtes"),
        question=_("Pourquoi Cross-Origin-Embedder-Policy reste à 'unsafe-none' même en profil hardened ?"),
        answer=(
            _("Choix délibéré, différent de `Cross-Origin-Opener-Policy`/`Cross-Origin-Resource-"
            "Policy` (toujours `same-origin`, sans risque réel de casser un site) : une valeur "
            "stricte (`require-corp`/`credentialless`) peut bloquer des ressources cross-origin "
            "(polices, images, iframes tiers) propres au contenu RÉELLEMENT servi, qu'un serveur "
            "générique ne connaît jamais à l'avance - jamais un défaut imposé sans connaissance de "
            "ce contenu. Le header reste néanmoins toujours ÉMIS explicitement, même à cette valeur "
            "permissive (jamais absent de la réponse - un scanner externe distingue ainsi 'non "
            "considéré' de 'permissif par choix'). Réglable via `security.coep_mode` (écran "
            "Sécurité générique) si vous connaissez le contenu servi et voulez l'isolation complète.")
        ),
    ),
    FaqEntry(
        category=_("Sécurité - CSP et en-têtes"),
        question=_("Le listing de répertoire (directory listing) perd tout son style visuel depuis que j'ai une CSP stricte - pourquoi ?"),
        answer=(
            _("Corrigé (2026-10-10) : le CSS du listing est désormais servi en fichier EXTERNE "
            "réservé plutôt qu'inline dans le HTML - `style-src 'self'` (politique par défaut) "
            "autorise déjà une feuille de style de même origine, sans besoin d'aucune exception. "
            "Si ce problème persiste après mise à jour, voir la question sur le redémarrage après "
            "mise à jour du code (catégorie Redémarrage et rechargement) : un simple rechargement "
            "(SIGHUP) ne suffit jamais à appliquer un changement de CODE, seul un redémarrage "
            "complet du service le fait.")
        ),
    ),
    FaqEntry(
        category=_("TLS et certificats"),
        question=_("J'ai regenere/revoque le certificat TLS mais le serveur sert toujours l'ancien - pourquoi ?"),
        answer=(
            _("Le contexte SSL n'est construit qu'UNE SEULE FOIS au démarrage du serveur, jamais "
            "retouché par un simple rechargement. Régénérer ou révoquer un certificat pendant "
            "que TLS est déjà actif nécessite TOUJOURS un redémarrage complet pour que le "
            "changement soit réellement pris en compte, même si le fichier sur disque a déjà changé.")
        ),
    ),
    FaqEntry(
        category=_("Sauvegarde et restauration"),
        question=_("Mes sauvegardes de configuration sont-elles chiffrées ?"),
        answer=(
            _("Non, jamais par défaut. Si vous incluez les zones d'authentification (hash de mots "
            "de passe) ou les certificats (clés privées TLS), la sauvegarde contient des secrets "
            "réels en clair - une confirmation explicite supplémentaire est demandée avant de "
            "créer ce type de sauvegarde. Protégez ces fichiers comme n'importe quel secret.")
        ),
    ),
    FaqEntry(
        category=_("TLS et certificats"),
        question=_("Comment m'auto-héberger avec un vrai certificat public, de bout en bout (schéma DDNS -> Certbot -> OMEGA-SERV) ?"),
        answer=(
            _("Le schéma complet : un service DDNS (Dynu ou équivalent) fait pointer un nom de "
            "domaine public (ex. monserveur.dynu.com) vers votre IP, mise à jour automatiquement "
            "par leur client à chaque changement - ENTIÈREMENT hors du périmètre d'OMEGA-SERV, "
            "à installer et configurer vous-même. Vous devez aussi rediriger les ports 80 et 443 "
            "de votre routeur/pare-feu vers cette machine. Une fois cela fait : Assistant Let's "
            "Encrypt (Configuration détaillée -> TLS) obtient le premier certificat (défi HTTP-01, "
            "webroot - port 80 doit être joignable depuis Internet le temps de la demande), "
            "l'importe et vous rappelle d'activer TLS (écran Activer/desactiver TLS) puis de "
            "redémarrer. Ensuite, Renouvellement automatique (même sous-menu) installe la "
            "planification (timer systemd ou crontab) qui renouvelle et redémarre tout seul, "
            "sans plus jamais intervenir manuellement pour cette partie.")
        ),
    ),
    FaqEntry(
        category=_("TLS et certificats"),
        question=_("OMEGA-SERV tourne dans un conteneur - comment obtenir un certificat Let's Encrypt ?"),
        answer=(
            _("N'exécutez PAS l'Assistant Let's Encrypt/le renouvellement automatique à l'intérieur "
            "du conteneur qui sert déjà le trafic public. Exécutez-les sur l'hôte (ou dans un "
            "conteneur/sidecar distinct dédié à l'administration) en partageant avec le conteneur "
            "serveur : le même volume de webroot (Certbot y dépose son défi, ce que le conteneur "
            "sert déjà via le port 80 qu'il expose), et le même volume secure/certificates/ - le "
            "conteneur serveur peut monter ce dernier en LECTURE SEULE, puisque l'import du "
            "certificat (écriture) se fait toujours côté hote/sidecar, jamais depuis le conteneur "
            "servant le trafic. Un redémarrage du conteneur serveur reste nécessaire après chaque "
            "renouvellement (même règle que partout ailleurs : le contexte SSL n'est jamais "
            "rechargé à chaud) - le hook de renouvellement redémarre le SERVICE qu'il connaît "
            "(hote/sidecar), pensez à l'adapter si le conteneur serveur est pilote séparément "
            "(ex. `docker restart`) plutôt que par un service systemd/OpenRC/runit classique.")
        ),
    ),
    FaqEntry(
        category=_("TLS et certificats"),
        question=_("L'Assistant Let's Encrypt échoue (défi HTTP-01) - pourquoi ?"),
        answer=(
            _("Les causes les plus fréquentes, dans l'ordre à vérifier : (1) le port 80 n'est pas "
            "réellement joignable depuis Internet (redirection de port manquante ou incorrecte "
            "sur le routeur/pare-feu, ou un autre service occupe déjà ce port sur la machine), "
            "(2) le domaine ne pointe pas encore vers cette IP (DNS/DDNS pas encore propagé - "
            "vérifiez avec `dig`/`nslookup` depuis une machine externe), (3) en mode test "
            "(staging, coché par défaut) tout fonctionne mais le certificat obtenu n'est jamais "
            "reconnu par les navigateurs - c'est normal, décochez la case une fois le domaine et "
            "le webroot vérifiés. Le message d'erreur affiché est directement celui renvoyé par "
            "Certbot - il précise généralement laquelle de ces causes s'applique.")
        ),
    ),
)
