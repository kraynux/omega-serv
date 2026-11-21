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
            "listen_backlog, TLS, 1ere activation de fastcgi, active_defense) "
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
            "construit une seule fois au démarrage (client FastCGI à la première "
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
            "QUE la CONFIGURATION (règles WAF, zones d'authentification, routage, reverse proxy) - il "
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
        question=_("J'ai coupé le WAF : pourquoi les adresses bannies passent et la limite de débit ne s'applique plus ?"),
        answer=(
            _("C'est voulu : la liste de blocage (page 451) et la limite de débit (429) font partie du WAF. Couper le "
              "WAF les coupe aussi, dans les deux moteurs ; les bans déjà posés restent enregistrés et reprennent "
              "effet quand le WAF est réactivé. Pour garder les bannissements et la limite de débit sans le filtrage "
              "des attaques, laissez le WAF actif en mode log-only plutôt que de le couper.")
        ),
    ),
    FaqEntry(
        category=_("WAF/Active Defense"),
        question=_("Une image ou une archive est refusée (403) par le WAF alors que le fichier est sain : pourquoi ?"),
        answer=(
            _("Lu comme du texte, un fichier binaire contient forcément des suites d'octets qui ressemblent à une "
              "attaque (substitution de commande, injection). Depuis la 3.0.0, le WAF ne lit plus comme du texte un "
              "fichier dont le format est reconnu à son contenu réel - la signature de ses premiers octets, jamais "
              "son extension - parmi la liste de l'écran WAF - Modules (« Fichiers binaires non inspectés » : "
              "images, vidéo, son, PDF, archives). Un formulaire, du JSON, du XML ou du texte reste toujours "
              "inspecté, même précédé d'une fausse signature ; dans un formulaire avec fichiers, seuls les fichiers "
              "reconnus sont retirés. Un fichier de format inconnu (ou un exécutable) reste inspecté et peut encore "
              "être refusé : ajoutez son format à la liste s'il est connu, ou excluez son chemin du WAF en dernier "
              "recours (cela retire aussi les autres contrôles sur ce chemin).")
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
            + " " + _("Nouvelle classe (2.1) : command_injection (injection de commandes shell, ex : $(...), ; cat /etc/passwd). Les sondes WordPress (wp-login, xmlrpc.php) sont classées scan.")
        ),
    ),
    FaqEntry(
        category=_("WAF/Active Defense"),
        question=_("« Ajouter un profil de leurre » refuse le profil - que corriger ?"),
        answer=(
            _("Rien n'est enregistré tant que le profil est invalide. Le formulaire reste ouvert, la raison s'affiche "
              "sous les champs et la saisie est conservée : corrigez le champ indiqué, puis cliquez à nouveau sur "
              "Valider. Causes les plus fréquentes : (1) Isolation = fixture avec un nom autre que fake_admin, fake_cms, fake_api ou "
              "fake_secrets (en minuscules, sans espace) ; (2) classe d'attaque mal écrite - valeurs exactes, "
              "séparées par des virgules : scan, credential_stuffing, sqli, xss, path_traversal, upload_probe, "
              "api_probe, command_injection, unknown ; (3) Isolation = proxy sans zone de leurre, ou avec un nom de "
              "zone qui n'existe pas encore (créez d'abord la zone dans « Zones de leurre ») ; (4) un autre réglage "
              "de l'écran est invalide (le message le nomme). Le plus simple : Isolation fixture, l'un des 4 noms, "
              "zone vide. Le formulaire « Ajouter une zone » fonctionne de la même façon.")
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
    FaqEntry(
        category=_("WAF/Active Defense"),
        question=_("Comment bannir une adresse IP à la main, sans écrire de règle ?"),
        answer=(
            _(
                "Active Sécurité -> INTERVENTION MANUELLE -> Bannir : une adresse, un motif, une durée. Le ban est "
                "immédiat (page 451 sur tout le site, avant les backends), sans droits root et sans lien avec la récidive "
                "RIPOSTE ; il se lève dans Débannir. Statut des bans liste tous les bans avec leur origine et les exporte "
                "(JSON, HTML, ou TXT importable tel quel dans omega-fire). Pour un réseau, passez par WAF -> Modules -> "
                "Liste de blocage."
            )
        ),
    ),
    FaqEntry(
        category=_("RIPOSTE"),
        question=_("Quelle différence entre Active Defense et RIPOSTE ?"),
        answer=(
            _("Active Defense agit PENDANT la requête : il note chaque source selon ce qu'elle fait maintenant (score, "
              "niveaux normal / suspicious / hostile / contained) et réagit tout de suite (leurre, ralentissement, "
              "incident). RIPOSTE agit DANS LA DURÉE : il se souvient des sources qui reviennent après un silence "
              "(épisodes) et leur applique des bans de plus en plus longs (paliers, par défaut 1 h, 6 h, 24 h, 7 j), "
              "avec une échéance, une levée possible et une mémoire de récidive. RIPOSTE ne modifie jamais le score ni "
              "les seuils d'Active Defense ; il peut seulement exiger un niveau Active Defense minimal dans une politique.")
        ),
    ),
    FaqEntry(
        category=_("RIPOSTE"),
        question=_("Pourquoi RIPOSTE a-t-il banni cette adresse ?"),
        answer=(
            _("Écran Actions : le détail de l'action donne la politique, le palier, l'événement d'origine et l'échéance. "
              "Écran Simuler, « Décisions récentes » : chaque décision est expliquée ligne par ligne (politique retenue, "
              "nombre de retours, exclusions vérifiées). En ligne de commande : « riposte actions show <id> » et "
              "« riposte decisions list --ip <adresse> --explain ». Faux positif : « Lever » avec « ne pas compter ce "
              "ban dans la récidive », et au besoin « Lever et exempter cette source ».")
        ),
    ),
    FaqEntry(
        category=_("RIPOSTE"),
        question=_("J'ai levé un ban RIPOSTE mais l'adresse reste bloquée - pourquoi ?"),
        answer=(
            _("Une politique « ban local + ban réseau » passe aussi le ban à fail2ban, par les jails omega-jail "
              "<service>-riposte-1h/6h/24h/7d. omega-serv n'a pas les droits de lever un ban fail2ban : « Lever » ne "
              "retire que le ban local (blocklist du WAF). Levez le ban réseau dans omega-fire ou avec fail2ban-client "
              "(la jail est indiquée dans le détail de l'action). Vérifiez aussi qu'un ban du WAF ou un ban manuel ne "
              "couvre pas la même adresse : RIPOSTE n'y touche jamais.")
        ),
    ),
    FaqEntry(
        category=_("RIPOSTE"),
        question=_("Les scénarios « Explorateur de leurres » et « Sonde upload / API » sont refusés (profil de leurre inconnu) - que faire ?"),
        answer=(
            _("Ces deux scénarios ne bannissent pas : ils envoient la source vers un leurre d'Active Defense, qui doit "
              "donc exister AVANT de charger le scénario - « Explorateur de leurres » utilise le profil fake_admin, "
              "« Sonde upload / API » le profil fake_api. (1) L'option active_defense doit être activée (menu "
              "Options). (2) Dans Active Sécurité -> Réglages (bloc Active Defense) : « Deception active » = oui, "
              "puis Enregistrer. (3) Toujours dans Réglages, « Ajouter un profil » : Nom fake_admin (ou fake_api), "
              "Actif oui, Classes d'attaque scan,credential_stuffing pour fake_admin ou api_probe,upload_probe pour "
              "fake_api, Isolation fixture, Zone de leurre vide. (4) Revenez dans RIPOSTE -> Politiques -> Ajouter "
              "-> Scénario prêt à charger : le scénario est accepté. Les leurres ne fonctionnent qu'après un "
              "redémarrage complet. Les trois autres scénarios bannissent et n'ont besoin d'aucun leurre.")
        ),
    ),
    FaqEntry(
        category=_("RIPOSTE"),
        question=_("RIPOSTE ne fait rien - pourquoi ?"),
        answer=(
            _("Dans l'ordre : (1) le module 'riposte' doit être activé dans Options, puis le service REDÉMARRÉ "
              "complètement ; (2) le WAF doit être actif, sinon RIPOSTE ne voit aucune attaque ; (3) au moins une "
              "politique doit être active (« Enregistrer sans activer » la laisse en observation) ; (4) l'arrêt "
              "d'urgence ne doit pas être actif (écran État : le bouton affiche « Reprendre ») ; (5) la condition doit "
              "être atteinte : par exemple 3 épisodes en 7 jours, un épisode étant séparé du précédent par au moins "
              "1 h de silence. Simuler avec la même situation montre la condition qui manque.")
        ),
    ),
    FaqEntry(
        category=_("RIPOSTE"),
        question=_("Une adresse bannie reçoit une page 451 : est-ce omega-serv ou fail2ban ?"),
        answer=(
            _("C'est omega-serv. Une adresse présente dans la liste de blocage du WAF (auto-ban du WAF, ban manuel ou "
              "ban local RIPOSTE) reçoit la page 451 « Votre IP a été bannie » sur toutes ses requêtes, pendant toute "
              "la durée du ban. Un 403 refuse seulement une requête (une règle touchée), sans bannir. Un ban fail2ban "
              "agit sur le pare-feu : il ne renvoie jamais de page, la connexion est coupée ou n'aboutit pas. Pour "
              "savoir qui a banni, regardez la source du ban dans la liste de blocage (« auto » = auto-ban du WAF, « "
              "riposte », « manual ») : WAF → Modules → Liste de blocage, ou « blocklist list ».")
        ),
    ),
    FaqEntry(
        category=_("RIPOSTE"),
        question=_("À quoi servent les jails omega-serv-riposte-1h, -6h, -24h et -7d ?"),
        answer=(
            _("Ce sont les jails fail2ban du ban réseau de RIPOSTE, installés par omega-jail (1.1.0 ou plus). Quand une"
              " politique « ban local + ban réseau » bannit, omega-serv pose d'abord le ban local, puis écrit une ligne"
              " dans « var/log/riposte-decisions.jsonl » ; fail2ban la lit et bannit l'adresse au pare-feu. Les jails "
              "ont une durée fixe : chaque palier RIPOSTE va à la plus longue qui ne le dépasse pas (un palier de 2 h "
              "va dans la jail de 1 h), et l'interface l'indique. Chaque instance omega-serv a son propre jeu de jails,"
              " préfixé par le nom de son service.")
        ),
    ),
    FaqEntry(
        category=_("RIPOSTE"),
        question=_("J'ai mis à jour omega-jail, mais les jails RIPOSTE n'apparaissent ni dans fail2ban ni dans omega-fire"),
        answer=(
            _("Mettre à jour omega-jail ne suffit pas à installer ses nouveaux jails. Extrayez l'archive par-dessus le "
              "dossier existant, puis lancez « ./install.sh » : il liste les jails du catalogue pas encore installés et"
              " propose de les installer (« sudo »). À défaut : « sudo ./omega-jail.sh --apply ». Les jails RIPOSTE ne "
              "sont proposés que si le module RIPOSTE est activé dans omega-serv (sinon « source non configurée »). "
              "Vérification : « sudo fail2ban-client status ». omega-fire les affiche dès qu'ils sont installés, sans "
              "rien à déclarer.")
        ),
    ),
    FaqEntry(
        category=_("RIPOSTE"),
        question=_("Derrière Tailscale Funnel ou un proxy local, le ban réseau sert-il à quelque chose ?"),
        answer=(
            _("Pas le ban fail2ban seul : les connexions arrivent alors du proxy local (tailscaled, 127.0.0.1), pas du "
              "visiteur, et le ban pare-feu ne le touche pas. omega-jail (1.1.0 ou plus) le détecte et relaie alors "
              "chaque ban fail2ban d'une adresse publique dans la liste de blocage d'omega-serv : l'adresse reçoit la "
              "page 451, comme avec le script Magnet. Les jails RIPOSTE ne sont pas relayés : RIPOSTE a déjà posé son "
              "ban local (451). Quand les visiteurs se connectent directement au serveur, le ban pare-feu agit seul.")
        ),
    ),
    FaqEntry(
        category=_("RIPOSTE"),
        question=_("La jail omega-serv-active-defense fait-elle double emploi avec RIPOSTE ?"),
        answer=(
            _("En partie. Cette jail d'omega-jail bannit au pare-feu pendant 24 h fixes toute adresse classée hostile "
              "ou contained par Active Defense, sans tenir compte des paliers RIPOSTE : une adresse peut donc être "
              "bannie au niveau réseau plus tôt ou plus longtemps que le palier choisi. L'écran État de RIPOSTE la "
              "signale. Gardez-la si vous voulez ce filet de sécurité ; retirez-la (gestion des jails d'omega-fire) si "
              "seuls les paliers RIPOSTE doivent compter.")
        ),
    ),
    FaqEntry(
        category=_("RIPOSTE"),
        question=_("Mon attaque de test ne déclenche aucun ban RIPOSTE - pourquoi ?"),
        answer=(
            _("Dans l'ordre : (1) la requête doit toucher une règle du WAF, ce qui donne un 403 (par exemple « /?id=1 "
              "UNION SELECT 1 » ou « /.env ») ; une simple 404 n'est pas une attaque ; (2) l'adresse ne doit pas être "
              "exemptée : hôte local, Tailscale et réseau local ne sont jamais bannis, testez depuis une adresse "
              "publique (4G) et, derrière un proxy, réglez le proxy de confiance ; (3) la politique doit être remplie :"
              " nombre d'épisodes, classes d'attaque et niveau Active Defense minimal (« aucun » pour un test) ; (4) "
              "une adresse déjà bannie (page 451, souvent par l'auto-ban du WAF) n'est plus analysée : RIPOSTE ignore "
              "les refus de la liste de blocage, levez d'abord ce ban. Simuler la même situation montre ce qui manque.")
        ),
    ),
    FaqEntry(
        category=_("RIPOSTE"),
        question=_("Active Defense tient-il compte des bans posés par fail2ban ou omega-fire ?"),
        answer=(
            _("Oui, quand omega-connect relie vos outils : omega-fire (ses bans manuels) et omega-jail (action "
              "fail2ban de ses jails, et de ceux choisis avec « --journal sshd ») publient chaque ban dans le journal "
              "des bans de la zone omega-connect. Active Defense le relit toutes les 5 secondes, sans redémarrage : "
              "une requête suspecte d'une adresse bannie ailleurs gagne 25 points. Les jails RIPOSTE d'omega-serv "
              "sont ignorés (sinon une même attaque serait comptée deux fois). Le service doit être dans le groupe "
              "omega-synchro, ce que règle omega-connect.")
        ),
    ),
    FaqEntry(
        category=_("RIPOSTE"),
        question=_("Pourquoi omega-fire n'affiche-t-il que les bans fail2ban ?"),
        answer=(
            _("omega-fire lit fail2ban et le pare-feu. Les bans d'omega-serv (liste de blocage du WAF, page 451 : "
              "auto-ban, ban manuel, ban local RIPOSTE) se consultent pour l'instant dans omega-serv : WAF → Modules → "
              "Liste de blocage, écran Actions de RIPOSTE, ou « blocklist list ». Les jails installés par omega-jail, "
              "dont ceux de RIPOSTE, apparaissent bien dans omega-fire.")
        ),
    ),
    FaqEntry(
        category=_("Moteur HTTP et performances"),
        question=_("Moteur Python ou natif : qu'est-ce que ça change concrètement ?"),
        answer=(
            _("Ce qui ne change pas : les réponses, les journaux, la sécurité et les fonctions disponibles. Ce qui "
            "change, c'est qui traite les requêtes HTTP : l'interpréteur Python, ou un programme compilé qui "
            "utilise tous les cœurs. Avec le WAF, le moteur natif cherche lui-même les règles : une requête sur "
            "laquelle aucune règle ne correspond est servie sans passer par Python ; au moindre doute "
            "(correspondance, texte non ASCII, en-têtes ou corps à inspecter, source suivie par Active Defense, "
            "zone d'authentification), c'est Python qui décide, exactement comme avec le moteur Python. Si "
            "magnet est actif, toutes les requêtes passent par Python ; la limite de débit, elle, est comptée "
            "par le moteur natif, sans coût mesurable. Mesuré sur trois "
            "machines (comparatif des serveurs web, à lire pour le détail), le moteur natif sert les petites "
            "pages 10 à 27 fois plus vite que le moteur Python sans contrôle de sécurité, et 8 à 30 fois plus "
            "vite avec le WAF, qui ne lui retire que 5 à 22 % de son débit ; les fichiers de 100 Ko 3,5 à 10 "
            "fois plus vite ; les gros fichiers 1,3 à 2,7 fois plus vite. Le temps de réponse des requêtes les "
            "plus lentes est divisé par 5 à 15. Il occupe aussi moins de mémoire : environ 10 Mo contre 20 Mo "
            "pour le moteur Python, et environ 30 Mo avec le WAF (règles chargées dans le natif, plus le "
            "processus Python des contrôles de sécurité). Le reverse proxy, WebSocket "
            "compris, est relayé par le natif. Le listing, les pages internes, FastCGI, l'envoi de fichiers et "
            "les zones de reverse proxy avec cache sont confiés à Python : ces requêtes-là gardent la vitesse "
            "du moteur Python. Pour un "
            "petit site peu visité, les deux suffisent largement : même le moteur Python avec le WAF sert des "
            "dizaines de millions de requêtes par jour sur une machine modeste.")
        ),
    ),
    FaqEntry(
        category=_("Moteur HTTP et performances"),
        question=_("Combien de processus choisir ?"),
        answer=(
            _("Ça dépend du moteur. Moteur Python : chaque processus sert les requêtes ; mesuré, 2 processus "
            "servent 1,6 à 2 fois plus que 1, et 4 environ 3,5 fois plus, jusqu'au nombre de cœurs physiques "
            "(le maximum proposé). Chaque processus occupe environ 15 à 25 Mo de mémoire de plus. Moteur "
            "natif : il utilise déjà tous les cœurs, les processus réglés sont ceux des contrôles de sécurité, "
            "qui ne reçoivent que les requêtes à vérifier (correspondance ou doute du WAF, sources suivies par "
            "Active Defense, authentification). Pour le trafic ordinaire, un 2e processus n'apporte donc rien : "
            "mesuré, le débit reste le même. Il sert quand toutes les requêtes passent par Python (magnet "
            "actif) et que la machine a au moins 4 cœurs physiques : 1,5 à 1,7 fois plus de "
            "requêtes. Sur 2 cœurs, il n'apporte que 5 à 12 %, le processeur étant déjà occupé : "
            "l'écran ne le propose donc qu'à partir de 4 cœurs. Au-delà de 2, le gain mesuré est de 4 %. "
            "L'écran Résistance et limites affiche le maximum de cette machine et ce qu'augmenter apporte ; "
            "le nombre réellement appliqué s'affiche dans État & Ressources.")
        ),
    ),
    FaqEntry(
        category=_("Moteur HTTP et performances"),
        question=_("Je décoche une option (WAF, reverse proxy...) : sa mémoire est-elle rendue ?"),
        answer=(
            _("Pas tout de suite. Le code d'une option n'est chargé que si elle est active, au démarrage ou au "
              "premier rechargement qui l'active. Une fois chargé, il reste en mémoire : Python ne décharge "
              "jamais un module. Décochée puis appliquée, l'option ne fait plus rien et ne coûte plus de "
              "processeur, mais sa mémoire (environ 2 Mo pour le WAF) n'est rendue qu'au prochain redémarrage "
              "du service. Avec le moteur natif, activer la première option de sécurité ou couper la dernière "
              "demande de toute façon un redémarrage complet, qui rend tout ; décocher une option parmi "
              "d'autres se comporte comme avec le moteur Python. Pour retrouver la mémoire la plus basse : "
              "redémarrer le service après avoir coupé des options.")
        ),
    ),
    FaqEntry(
        category=_("Moteur HTTP et performances"),
        question=_("Pourquoi le choix « Natif C++ » est-il grisé dans Configuration de base ?"),
        answer=(
            _("Parce qu'une cause empêche le moteur natif de tout servir : le binaire bin/omega-http-core "
            "est absent ou ne démarre pas sur cette machine (install.sh essaie alors de le recompiler), "
            "ou TLS est en mode direct alors qu'une zone de reverse proxy avec cache, FastCGI ou l'envoi de "
            "fichiers est actif "
            "(ces routes demandent de confier la connexion au processus Python, impossible quand le natif "
            "chiffre lui-même). La liste des causes, et comment lever chacune, s'affiche sous le choix. "
            "Jamais de serveur à moitié natif : levez la cause, puis choisissez le natif.")
        ),
    ),
    FaqEntry(
        category=_("Moteur HTTP et performances"),
        question=_("Reverse proxy avec le moteur natif : qu'est-ce qui change par rapport à la version 2 ?"),
        answer=(
            _("Les zones sont relayées par le natif (sauf celles avec cache), avec les mêmes contrôles de "
            "sécurité avant tout envoi au backend et les mêmes journaux. Changements visibles : une seule "
            "limite de débit par adresse (le moteur natif la comptait deux fois sur le proxy) ; "
            "max_connections, keep-alive et délais s'appliquent aussi aux connexions relayées ; un backend trop "
            "lent donne 504 ; un client parti avant toute réponse est noté 499 dans access.log ; les refus "
            "décidés par le natif (bannie, débit) ont leur ligne dans waf-alerts ; plusieurs Set-Cookie sont "
            "gardés ; un caractère de contrôle dans l'adresse demandée donne 400 ; les sondes de santé tournent "
            "dès le démarrage ; un processus de sécurité (environ 20 Mo) existe dès qu'une zone existe. Un "
            "tunnel WebSocket inactif est fermé après une heure (réglable par zone). Retour en arrière sans "
            "recompiler : Réglages communs, moteur des zones = python. Mesuré sur trois machines (comparatif "
            "des serveurs web, section reverse proxy), le natif relaie les petites réponses 9 à 12 fois plus "
            "vite que le moteur Python, à 0,82 à 0,91 fois nginx, devant lighttpd, Apache, Traefik et Caddy ; "
            "les réponses de 100 Ko aussi vite ou plus vite que nginx. Le WAF lui retire 1 à 9 % de son débit.")
        ),
    ),
    FaqEntry(
        category=_("Moteur HTTP et performances"),
        question=_("Écran Reverse proxy : où voir quel moteur relaie chaque zone, et les réglages du moteur natif ?"),
        answer=(
            _("Sur l'écran Reverse proxy lui-même, sans rien ouvrir : la ligne au-dessus du tableau résume les "
              "réglages communs en vigueur (moteur des zones, mémoire des corps en attente, inspections, connexions "
              "vers les backends, taille des réponses lues par Python), et la colonne « Moteur » dit qui relaie "
              "chaque zone : natif, Python (cache), Python (réglage), Python (repli) ou Python. Pour les modifier : "
              "bouton « Réglages communs », toujours visible en bas de l'écran. C'est le moteur prévu par la "
              "configuration ; l'écran État montre celui qui tourne réellement.")
        ),
    ),
    FaqEntry(
        category=_("Multi-instance"),
        question=_("Administration web : que montre la vue Historique, et combien coûte-t-elle ?"),
        answer=(
            _("Plages 1 heure, 3 heures, 12 heures, 24 heures, 7 jours et 30 jours. Graphes de toute la machine : "
              "processeur, mémoire, swap, charge (1, 5 et 15 min), réseau reçu et envoyé, connexions TCP et sockets, "
              "disque (lecture, écriture, espace de la partition de l'instance), nombre de processus, température du "
              "processeur et batterie (masqués quand la machine n'en a pas). Graphes de cette instance : requêtes par "
              "seconde, processeur et mémoire des processus d'omega-serv, Téléchargements et Téléversement (octets "
              "envoyés aux visiteurs et reçus d'eux, en-têtes et chiffrement TLS compris, comptés par le moteur "
              "Python comme par le natif). Le processus d'administration fait un "
              "relevé toutes les 10 secondes, même sans page ouverte ; les requêtes sont les lignes ajoutées au "
              "journal d'accès, comptées sans être relues, donc le coût reste faible même sous forte charge.")
            + " " + _("Moyenne ou Max 1 min : sur 24 heures, 7 et 30 jours, chaque point couvre 5 minutes, 30 minutes "
                      "ou 2 heures ; Moyenne trace la moyenne de la tranche, Max 1 min sa minute la plus chargée, pour "
                      "voir les pointes que la moyenne efface. Sur 1, 3 et 12 heures, les deux courbes sont les mêmes.")
            + " " + _("Mémoire, swap, disque (espace), processeur et mémoire d'omega-serv, batterie : courbe remplie et, en haut à "
                      "droite, la dernière mesure en taille utilisée sur le total, puis en pourcentage (cœurs pour le processeur "
                      "d'omega-serv ; sur secteur ou temps restant pour la batterie).")
            + " " + _("L'historique tient dans var/run/admin/history.json (environ 350 Ko une fois les 30 jours "
                      "remplis), écrit toutes les 5 minutes et à l'arrêt : un redémarrage ne perd que les dernières "
                      "minutes, qui apparaissent comme un trou dans les courbes. Pour l'arrêter : Instances -> "
                      "Configuration distante -> Historique -> Désactivé.")
        ),
    ),
    FaqEntry(
        category=_("Multi-instance"),
        question=_("Mon instance n'est pas dans l'écran Instances : comment régler son accès distant ?"),
        answer=(
            _("L'instance courante est toujours affichée en tête du tableau, marquée « (courante) », même si elle "
              "n'a jamais été inscrite au registre (c'est le cas de l'installation d'origine, seules les instances "
              "créées par « Créer une nouvelle instance » y sont inscrites). Sélectionnez-la puis « Configuration "
              "distante » ; si le bouton est grisé, activez d'abord l'option admin_web dans Voir options actives. "
              "Elle ne peut jamais être désinstallée depuis elle-même : basculez d'abord sur une autre instance.")
        ),
    ),
    FaqEntry(
        category=_("Multi-instance"),
        question=_("Administration web : comment l'activer et la régler (port, TLS, accès depuis un autre appareil) ?"),
        answer=(
            _("Tout se fait dans Instances -> Configuration distante, sans commande à taper : le cadre État dit ce "
              "qui manque, avec un bouton pour chaque point. 1. Activer (option admin_web, puis redémarrage "
              "complet). 2. Adresse d'écoute : 127.0.0.1 pour cette machine seulement ; adresse du réseau local, de "
              "Tailscale ou 0.0.0.0 pour un autre appareil (TLS « Certificat dédié » est alors choisi tout seul). "
              "Enregistrer. 3. Générer le certificat (auto-signé, clé lisible par le service). 4. Comptes : créer un "
              "compte ; hors de cette machine, un compte d'administration doit activer TOTP. 5. Recharger ou "
              "Redémarrer jusqu'à « En écoute ». Le cadre donne aussi l'adresse à ouvrir sur l'autre appareil. Le "
              "port par défaut est 9643 ; Enregistrer refuse un port déjà pris par un autre programme. La colonne "
              "« Accès distant » de l'écran Instances montre si l'administration web est active. Un problème de "
              "l'administration n'empêche jamais le site de démarrer.")
        ),
    ),
    FaqEntry(
        category=_("Multi-instance"),
        question=_("Administration web : la page ne s'ouvre pas depuis un autre appareil, que vérifier ?"),
        answer=(
            _("Regardez d'abord le cadre État de Instances -> Configuration distante : chaque ✗ a son bouton. Si tout "
              "est ✓ : rien ne répond = pare-feu (avec omega-fire inscrit dans la zone omega-connect, le bouton Ouvrir "
              "le port s'en charge, ufw ou firewalld compris ; sinon le cadre signale ufw, firewalld ou nftables "
              "actifs : ouvrez-y le port pour vos réseaux permis avec l'outil du pare-feu) ou mauvaise adresse (utilisez "
              "celle que le cadre affiche) ; « certificat non signé » = normal avec un certificat auto-signé, "
              "acceptez-le une fois ; 403 avant la page de connexion = l'adresse de l'appareil n'est pas dans les "
              "réseaux permis ; refus après la connexion = identifiant, mot de passe ou code TOTP (vérifiez l'heure "
              "du téléphone).")
        ),
    ),
    FaqEntry(
        category=_("Multi-instance"),
        question=_("Administration web : comment créer un compte, activer TOTP, et que faire si le téléphone est perdu ?"),
        answer=(
            _("Les comptes se créent sur la machine seulement, jamais depuis le navigateur : Instances -> Configuration "
              "distante -> Comptes, ou « omega-serv admin-web account add NOM --role lecture|administration ». Un "
              "compte lecture voit le Tableau de bord ; un compte administration peut aussi agir. Activer TOTP affiche "
              "un QR code à scanner depuis un autre appareil, et, sans scan, le secret à saisir ou un lien à ouvrir sur "
              "le téléphone ; le secret n'est enregistré qu'après un code juste, puis 10 codes de secours s'affichent "
              "une seule fois. TOTP est obligatoire pour un compte administration dès que l'administration web sort de "
              "cette machine. Téléphone perdu : un code de secours remplace le code une fois ; sinon, désactivez TOTP "
              "dans Comptes puis réactivez-le. La colonne « Codes de secours » de Comptes montre combien il en reste, "
              "et « Nouveaux codes de secours » en génère 10 autres sans toucher au TOTP du téléphone. Cinq échecs de connexion en dix minutes bloquent la connexion un moment ; "
              "tout est noté dans var/log/admin-audit.log.")
            + " " + _("Sur la page de connexion, « Administration » ne sert qu'aux comptes administration : un compte "
                      "lecture arrive sur le Tableau de bord, avec un message qui le dit (une seule fois).")
            + " " + _("Le rôle se choisit dans un menu déroulant : lecture ou administration.")
        ),
    ),
    FaqEntry(
        category=_("Multi-instance"),
        question=_("Administration web : que montre le Tableau de bord, et pourquoi un journal n'apparaît-il pas ?"),
        answer=(
            _("Le Tableau de bord reprend l'écran État & Ressources du TUI (état du serveur, flux avec BACKENDS, "
              "ressources), rafraîchi toutes les 2 secondes tant qu'une page est ouverte ; s'y ajoutent Journaux, "
              "Sécurité (bans, RIPOSTE, incidents) et, pour les comptes administration, le journal d'audit. Les "
              "chiffres sont calculés une seule fois pour tous les navigateurs ouverts, et plus du tout quand personne "
              "ne regarde. Journaux : access.log, error.log et les alertes du WAF de l'instance, puis les fichiers de "
              "sa bibliothèque (Gestion des logs), jamais un chemin tapé dans le navigateur ; un journal que le compte du service ne peut pas "
              "lire s'affiche « illisible pour le service » (il n'y a pas de sudo depuis le web). Les lignes sont "
              "toujours affichées comme du texte : un journal peut contenir n'importe quoi envoyé par un visiteur.")
            + " " + _("Couleurs : les 10 thèmes omega de la TUI. Par défaut le panneau suit le thème de la TUI de "
                      "l'instance (Instances -> Configuration distante -> Thème du panneau web pour en imposer un) ; "
                      "chaque navigateur peut aussi choisir le sien dans la barre du haut, gardé dans ce navigateur "
                      "seulement.")
        ),
    ),
    FaqEntry(
        category=_("Multi-instance"),
        question=_("Administration web : comment marchent les alertes, et quelque chose part-il sur Internet ?"),
        answer=(
            _("Rien ne part : les alertes sont locales (vue Alertes du panneau web, var/log/alertes.log). Le processus "
              "d'administration surveille le disque, la mémoire, le swap, le processeur, la température, la batterie, "
              "le taux d'erreurs 5xx du site (sur 5 minutes), les backends hors service, les incidents Active Defense "
              "et les certificats (30, 14, 7 et 1 jour avant l'échéance). Une alerte s'ouvre quand le seuil est "
              "dépassé pendant un moment et se ferme quand la mesure redescend nettement, pour ne pas clignoter.")
            + " " + _("Seuils, règles coupées et maintenance (1 h ou 24 h sans nouvelle alerte) : Instances -> "
                      "Configuration distante -> Alertes. Il faut l'administration web active (en boucle locale "
                      "suffit) ; les mesures de la machine demandent aussi l'Historique. Un service arrêté ne peut "
                      "rien signaler lui-même.")
        ),
    ),
    FaqEntry(
        category=_("Multi-instance"),
        question=_("Administration web : que montrent les vues Trafic, Certificats et Sessions ?"),
        answer=(
            _("Trafic : pages les plus demandées, pages introuvables (404), adresses IP les plus actives, statuts, "
              "référents (nom du site seulement), navigateurs et robots, requêtes par heure ; aujourd'hui, 7 ou 30 "
              "jours. Lu dans le journal d'accès au fil de l'eau (environ 85 000 lignes par seconde sur un PC de "
              "bureau, rien sans visiteur), un fichier par jour dans var/lib/admin/stats/, 31 jours gardés. Pas de "
              "pays : il faudrait une base externe. Adresses masquables (Configuration distante).")
            + " " + _("Certificats : ceux de cette instance et leur échéance, lus par openssl (aussi dans la TUI : "
                      "TLS -> Échéances des certificats). Sessions : navigateurs connectés ; un compte administration "
                      "peut fermer n'importe quelle session, un compte lecture les siennes (aussi dans la TUI : "
                      "Comptes -> Sessions).")
        ),
    ),
    FaqEntry(
        category=_("Multi-instance"),
        question=_("Administration web : que peut-on faire depuis le mode Administration ?"),
        answer=(
            _("Bannir et débannir une adresse IP (comme l'intervention manuelle ; les bans du WAF, de RIPOSTE et de la "
              "récidive se lèvent là où ils ont été posés), fermer un incident Active Defense, déclencher ou lever "
              "l'arrêt d'urgence de RIPOSTE, mettre un backend en DRAINING ou MAINTENANCE puis le rendre à "
              "l'automatique, archiver un journal de l'instance (var/backups/logs) ou supprimer une archive, recharger "
              "la configuration comme systemctl reload (les sessions restent ouvertes).")
            + " " + _("Chaque bouton ouvre d'abord une page de confirmation qui dit ce qui va se passer ; rien n'est "
                      "fait avant « Confirmer ». Réservé aux comptes administration, avec une saisie de moins de 15 "
                      "minutes ; chaque action, réussie ou refusée, est écrite dans le journal d'audit "
                      "(var/log/admin-audit.log).")
            + " " + _("Jamais depuis le web : modifier la configuration ou les comptes, redémarrer ou arrêter le "
                      "serveur. Le service n'a pas ces droits, et une erreur à distance pourrait couper l'accès.")
            + " " + _("var/backups/logs (archives des journaux) est partagé avec le service pour que l'administration web puisse "
                      "archiver un journal et supprimer une archive ; var/backups reste privé, seulement traversable par le "
                      "service. Si le web affiche « Archives illisibles par le service » : Accueil -> Service -> Réparer les "
                      "permissions.")
        ),
    ),
    FaqEntry(
        category=_("Multi-instance"),
        question=_("Administration web : comment suivre et piloter plusieurs instances depuis un seul tableau de bord ?"),
        answer=(
            _("Choisissez une instance maître : sa page Instances (tableau de bord web) montre toutes les instances qui "
              "l'ont acceptée, toutes les 5 secondes, et ouvre le tableau de bord de chacune. Sur chaque instance à "
              "suivre : Configuration distante -> Maître -> « Accepter un maître (code) », avec le droit lecture ou "
              "administration ; puis sur le maître, page Instances -> « Ajouter à la main » : adresse, port de "
              "l'administration web et code (10 minutes, une seule fois).")
            + " " + _("Entre deux instances de cette machine, rien à recopier : écran Instances -> « Relier au "
                      "maître ». En commande : omega-serv admin-web master accept sur l'instance, admin-web instances "
                      "add sur le maître.")
            + " " + _("Une instance n'accepte qu'un maître ; ses droits sont fixés chez elle et se révoquent chez "
                      "elle. Une action lancée depuis le maître est écrite dans les deux journaux d'audit. Pour un "
                      "backend qui n'est pas omega-serv, « Ajouter une sonde HTTP » montre son statut et son temps de "
                      "réponse.")
        ),
    ),
    FaqEntry(
        category=_("Multi-instance"),
        question=_("Administration web : le maître affiche « certificat changé », « jeton refusé » ou « injoignable » "
                   "pour une instance, que faire ?"),
        answer=(
            _("Certificat changé : le maître a retenu l'empreinte du certificat de l'instance à l'appairage et refuse "
              "d'envoyer son jeton à un autre certificat (protection contre une interception). Si le certificat a été "
              "renouvelé volontairement, retirez l'instance sur le maître et refaites l'appairage.")
            + " " + _("Jeton refusé : l'instance a révoqué ce maître ou en a accepté un autre. Injoignable ou "
                      "refusé par l'instance : vérifiez que son administration web écoute sur une adresse que le "
                      "maître peut joindre, et que l'adresse du maître est dans ses réseaux permis.")
        ),
    ),
    FaqEntry(
        category=_("Gestion des logs"),
        question=_("Pourquoi les appels à /.omega-serv-admin/ n'apparaissent-ils pas dans access.log ?"),
        answer=(
            _("Ce sont des appels internes, faits depuis cette machine toutes les 2 secondes par l'écran État & "
              "Ressources du TUI et par l'administration web pour lire l'état des backends : ils gonflaient le flux et "
              "les statistiques. Un appel accepté n'est donc jamais écrit dans access.log, dans les deux moteurs. Un "
              "appel refusé (403, adresse hors des réseaux de confiance) reste écrit : omega-jail et RIPOSTE voient "
              "toujours qui sonde cette route depuis l'extérieur.")
        ),
    ),
    FaqEntry(
        category=_("Authentification"),
        question=_("Une zone protégée par mot de passe répond 429 ou 503 : pourquoi ?"),
        answer=(
            _("Vérifier un mot de passe coûte environ 0,3 à 0,5 s de calcul. Un succès est retenu (5 minutes "
              "renouvelées, une heure au plus), mais chaque mauvais mot de passe coûte toujours ce calcul : après 10 "
              "échecs d'une même adresse, ou 30 pour un même nom d'utilisateur, en 5 minutes, le serveur répond 429 "
              "sans rien calculer jusqu'à la fin des 5 minutes (en-tête Retry-After). 503 : plus de 10 vérifications "
              "attendent déjà, le serveur refuse au lieu de les empiler. Un visiteur déjà vérifié n'est jamais "
              "concerné. Les récidivistes restent l'affaire de RIPOSTE. Ces seuils sont réglables : Configuration "
              "détaillée -> Authentification -> Protection des mots de passe.")
        ),
    ),
    FaqEntry(
        category=_("Gestion des logs"),
        question=_("Viewer Simple : pourquoi les colonnes Service et Durée affichent « - » ?"),
        answer=(
            _("Service est l'étiquette d'un syslog ou d'un journal système (sshd, nginx, kernel...) ; Durée est le "
              "temps de traitement quand le format l'écrit en fin de ligne (Apache %D ou %T). Un access log au "
              "format Combined, dont celui d'omega-serv, n'a ni l'un ni l'autre : « - » signifie « absent de la "
              "ligne », jamais une valeur inventée.")
        ),
    ),
    FaqEntry(
        category=_("Interface"),
        question=_("L'administration web répond 421 « Nom d'hôte refusé » : pourquoi ?"),
        answer=(
            _("Sans TLS, l'administration web n'accepte que les adresses IP, « localhost » et les noms de cette "
              "machine dans la barre d'adresse. Une page Internet pouvait sinon faire pointer son propre nom vers "
              "127.0.0.1 (« DNS rebinding ») et piloter l'interface depuis le navigateur d'un utilisateur de la "
              "machine. Ouvrez-la par son adresse (par exemple http://127.0.0.1:9643/) ou activez TLS : avec un "
              "certificat, le navigateur vérifie déjà le nom et tout nom couvert par le certificat est accepté.")
        ),
    ),
    FaqEntry(
        category=_("WAF/Active Defense"),
        question=_("Depuis la 3.0.0, un envoi de fichier est bloqué par le WAF alors qu'il passait avant : pourquoi ?"),
        answer=(
            _("Le WAF ne saute l'inspection d'un corps que si son type annoncé est explicitement binaire (image/*, "
              "audio/*, video/*, application/pdf, application/zip, application/octet-stream...) ET que ses "
              "premiers octets portent la signature correspondante. Un corps sans Content-Type, ou avec un type "
              "inconnu ou mal écrit, est désormais inspecté comme du texte : PHP lisait par exemple "
              "« application/x-www-form-urlencoded, » comme un formulaire alors que le WAF le laissait passer sans "
              "le lire. Faites envoyer le bon type par le client, ou ajoutez une exclusion de chemin pour cette "
              "adresse d'envoi.")
        ),
    ),
    FaqEntry(
        category=_("Reverse proxy"),
        question=_("Derrière nginx ou Caddy, /.omega-serv-admin/ ou /.omega-serv-load/ répond 403 : pourquoi ?"),
        answer=(
            _("Ces routes internes ne sont pas faites pour passer par un proxy frontal. Quand nginx ou Caddy tourne "
              "sur la même machine, chaque visiteur d'Internet arrive par 127.0.0.1, une adresse des réseaux de "
              "confiance : l'adresse seule ne suffit donc plus. Depuis la 3.0.0, un appel qui porte un en-tête "
              "ajouté par un proxy (X-Forwarded-For, Forwarded, X-Real-IP, X-Forwarded-Host, X-Forwarded-Proto, "
              "X-Forwarded-Port, CF-Connecting-IP, True-Client-IP, X-Client-IP) est refusé (403) dans les deux "
              "moteurs, même depuis un réseau de confiance.")
            + " " + _("La TUI, l'administration web et la sonde de charge d'une instance frontale appellent "
                      "omega-serv directement, sans ces en-têtes : rien à changer pour elles. Un script maison doit "
                      "faire de même : appeler l'adresse et le port d'écoute d'omega-serv (par exemple "
                      "http://127.0.0.1:8080/.omega-serv-admin/health), jamais l'adresse publique servie par le "
                      "proxy. L'appel refusé reste écrit dans access.log.")
        ),
    ),
    FaqEntry(
        category=_("Moteur HTTP et performances"),
        question=_("Reverse proxy : où voir combien de requêtes partent vers chaque backend, et leurs erreurs ?"),
        answer=(
            _("Dans État & Ressources : quand l'instance est un reverse proxy ou mixte (type affiché en tête du "
            "premier cadre), le cadre FLUX montre une section BACKENDS avec, pour chaque backend, son état, ses "
            "requêtes, celles en cours, ses erreurs 502 et 504 et son temps de réponse moyen, dans les deux "
            "moteurs. Ce sont des mesures en direct depuis le démarrage du serveur, sans historique ; access.log "
            "garde son format habituel. La section a besoin de trusted_proxy actif avec 127.0.0.1 dans ses réseaux "
            "de confiance, comme « État en direct » de l'écran Reverse proxy.")
        ),
    ),
    FaqEntry(
        category=_("Moteur HTTP et performances"),
        question=_("Un gros envoi de fichier échoue avec 408 (délai dépassé) : pourquoi ?"),
        answer=(
            _("Depuis la 3.0.0, le corps d'une requête n'a plus à arriver en entier dans read_timeout_seconds : "
              "le délai repart à chaque bloc reçu, tant que le débit moyen reste d'au moins 500 octets par seconde. "
              "Un envoi régulier passe donc, même long. Un 408 veut dire que le client s'est arrêté plus longtemps "
              "que read_timeout_seconds, ou qu'il envoie au compte-gouttes (sous 500 octets par seconde en moyenne) "
              "- la protection contre les attaques par envoi lent, dans les deux moteurs. Si de vrais clients font "
              "de longues pauses, augmentez read_timeout_seconds (Résistance et limites). Avant la 3.0.0, tout le "
              "corps devait arriver en 10 s : un fichier de 8 Mo échouait sous 6,4 Mbit/s.")
        ),
    ),
    FaqEntry(
        category=_("Moteur HTTP et performances"),
        question=_("Le moteur natif change-t-il mes journaux, fail2ban (omega-jail) ou RIPOSTE ?"),
        answer=(
            _("Non. Le journal d'accès est écrit au même format, caractère pour caractère, et les journaux "
            "de sécurité (alertes WAF, événements Active Defense) sont écrits par le même code Python "
            "qu'avec le moteur Python. RIPOSTE, omega-jail et omega-fire lisent les mêmes lignes et ne "
            "voient aucune différence. Une adresse bannie l'est quel que soit le moteur.")
        ),
    ),
    FaqEntry(
        category=_("Moteur HTTP et performances"),
        question=_("J'ai choisi le moteur natif mais État & Ressources indique « Python » - pourquoi ?"),
        answer=(
            _("Le serveur n'a pas encore été redémarré (le moteur ne change qu'au redémarrage complet), ou "
            "le natif n'a pas pu démarrer : binaire absent ou refusé, ou fonction active qu'il ne sait pas "
            "servir. Dans ce cas le moteur Python sert tout, et la raison est affichée dans État & "
            "Ressources (section MOTEUR HTTP), dans le journal d'erreurs et par la commande « omega-serv "
            "engine status ». Rien n'est jamais servi à moitié par l'un et à moitié par l'autre.")
        ),
    ),
    FaqEntry(
        category=_("Audit de sécurité"),
        question=_("L'audit signale des fichiers sensibles sous le webroot : lesquels, et sont-ils dangereux ?"),
        answer=(
            _("Depuis la 3.0.0, chaque fichier est nommé sous le constat, avec la raison (nom connu comme .env, "
            ".htpasswd, wp-config.php, ou extension .key, .pem, .crt, .p12) et ce qu'il contient vraiment : "
            "l'audit lit le début du fichier au lieu de se fier à son nom. Une vraie clé privée ou un fichier "
            "avec du contenu est critique (PERM-003) : déplacez-le hors du webroot, par exemple dans secure/. "
            "Un fichier vide, comme un exemple posé pour afficher une icône dans le directory listing, n'expose "
            "rien : c'est une simple information (PERM-004). Au-delà de dix fichiers, l'écran affiche « et N "
            "autres » ; la liste complète est donnée par « omega-serv audit security --format json ». Un dossier "
            ".git dans le webroot est signalé lui-même, car il contient tout l'historique du site.")
        ),
    ),
    FaqEntry(
        category=_("Service système"),
        question=_("Que se passe-t-il si je change le nom du service alors qu'il est installé et en marche ?"),
        answer=(
            _("Depuis la 3.0.0, le nom est verrouillé : Modifier, puis Valider. Avant, chaque touche était "
            "enregistrée aussitôt : une faute de frappe faisait piloter une unité inexistante, l'ancienne "
            "continuait de tourner sans que l'écran puisse l'arrêter, et Installer créait une seconde unité sur "
            "le même port. Désormais, si une unité de cette installation existe sous l'ancien nom, une fenêtre "
            "explique d'abord l'enchaînement : arrêter et désactiver l'ancienne, la désinstaller, installer la "
            "nouvelle, puis la réactiver et la redémarrer si c'était le cas. Le serveur est coupé quelques "
            "secondes. Un nom déjà utilisé par une autre installation est refusé, et un nom mal formé est "
            "signalé sans rien changer.")
        ),
    ),
    FaqEntry(
        category=_("Service système"),
        question=_("Une valeur est refusée dans un formulaire : dois-je tout ressaisir ?"),
        answer=(
            _("Non, depuis la 3.0.0. L'explication s'affiche dans le formulaire, qui reste ouvert avec tout ce que "
            "vous avez tapé : corrigez la valeur fautive puis Valider, ou Annuler pour abandonner. Sont refusés, "
            "avec la raison : une valeur hors format (préfixe sans « / », nombre attendu, réseau invalide…), un "
            "doublon (même préfixe, même réseau, même backend qu'une ligne existante, dont le numéro est donné) et "
            "une réponse qui n'est ni oui ni non. Avant, une faute de frappe dans un champ oui/non valait non sans "
            "rien dire.")
        ),
    ),
    FaqEntry(
        category=_("Sauvegarde et restauration"),
        question=_("Comment réinstaller omega-serv et retrouver mon serveur exactement comme avant ?"),
        answer=(
            _("Sauvegarde de configuration : cochez « Tout sauvegarder » (et, si vous les voulez aussi, « contenu "
            "du site », « données des zones personnalisées » pour les dossiers des alias, du listing et les scripts "
            "FastCGI, « rapports d'export »), créez la sauvegarde, puis « Exporter » vers un dossier HORS "
            "d'omega-serv : le "
            "dossier var/backups disparaît avec l'instance. Après la réinstallation : « Importer une sauvegarde » "
            "(l'empreinte .sha256 doit être à côté de l'archive), puis « Restaurer ». La configuration contient "
            "tout ce que vous avez saisi : alias, rewrites, redirections, directory listing, cache, reverse proxy et "
            "ses zones, WAF, Active Defense, RIPOSTE ; les cases ajoutent règles et listes, zones Auth, certificats, "
            "bases, pages d'erreur, préférences, journaux suivis, profils personnalisés. Restent à refaire : "
            "l'unité systemd (écran Service, Installer l'unité) et les certificats placés hors du dossier "
            "omega-serv, par exemple dans /etc/letsencrypt.")
        ),
    ),
    FaqEntry(
        category=_("Sauvegarde et restauration"),
        question=_("Après une restauration, une zone répond 404 ou le serveur refuse de démarrer : pourquoi ?"),
        answer=(
            _("Le dossier vers lequel pointe la zone n'est pas sur le disque : la sauvegarde ne contenait pas les "
            "données des zones, ou le dossier est hors d'omega-serv (par exemple /srv/media). omega-serv le dit "
            "juste après la restauration, dans « Vérifier la configuration » et dans error.log au démarrage. Un "
            "alias ou un listing absent répond 404 sans gêner le reste du site ; une zone FastCGI active sans son "
            "dossier de scripts empêche le serveur de démarrer. Remettez le dossier (copie, ou sauvegarde faite "
            "avec « données des zones personnalisées »), ou désactivez la zone le temps de le retrouver.")
        ),
    ),
    FaqEntry(
        category=_("Profils"),
        question=_("Un profil personnalisé change-t-il mon port, mon TLS ou mes zones ?"),
        answer=(
            _("Non. Un profil personnalisé (Profils, Créer un profil personnalisé) ne fixe que la sécurité "
            "(en-têtes, CSP, fichiers cachés, Host, méthodes) et l'état actif ou inactif des options. Adresse, port, "
            "TLS, chemins, journaux et réglages des options (alias, zones, listes...) restent ceux de l'instance. "
            "Les profils fournis, eux, repartent des valeurs par défaut pour tout ce qu'ils ne fixent pas : la "
            "différence est toujours affichée avant d'appliquer. Un profil personnalisé ne se modifie pas : on en "
            "recrée un en repartant de ses choix. Il est rangé dans config/profiles/custom/, compris dans les "
            "sauvegardes et repris lors d'une mise à jour.")
        ),
    ),
    FaqEntry(
        category=_("Rapport complet"),
        question=_("Comment voir d'un coup tout ce qui est configuré et actif sur mon serveur ?"),
        answer=(
            _("Menu principal, Rapport complet (sous Sauvegarde de configuration). Le sommaire montre l'instance, le "
            "profil appliqué, le service et son uptime, l'adresse et le mode (site web, reverse proxy ou les deux), "
            "le moteur utilisé, le TLS et son expiration, les options actives ou non, le nombre d'alias, rewrites, "
            "zones et backends, la sécurité, les contrôles de la configuration, les sauvegardes et les journaux. "
            "Cochez le détail voulu puis exportez en HTML (5 thèmes), TXT ou JSON. Aucun secret n'est exporté. Le "
            "bouton Quitter a quitté le menu : Échap, q ou Ctrl+Q demandent toujours confirmation.")
        ),
    ),
    FaqEntry(
        category=_("Interface"),
        question=_("La liste est longue : faut-il la dérouler jusqu'en bas pour revenir ou enregistrer ?"),
        answer=(
            _("Non. Sur les écrans à liste ou à long formulaire (zones, WAF, Active Defense, journaux, instances, "
            "audit, guide d'aide...), la dernière rangée de boutons, Retour compris, est dans une barre fixe en bas "
            "de l'écran, hors de la zone qui défile : elle reste visible quelle que soit la longueur. Un bouton sorti "
            "de sa section porte un nom explicite (« Enregistrer les exclusions », « Ajouter une zone », « Bloquer "
            "un réseau »). Sur les grands menus (Service, Instances, Audit, Sauvegarde, Rapport complet, Profils, "
            "Guide d'aide), Retour est seul et centré, et le titre est centré au-dessus. Échap revient aussi en "
            "arrière depuis n'importe quel écran.")
        ),
    ),
    FaqEntry(
        category=_("FastCGI / PHP-FPM"),
        question=_("Peut-on servir deux applications PHP (/blog/ et /wiki/) sur la même instance ?"),
        answer=(
            _("Oui. L'écran FastCGI / PHP-FPM est une liste de zones : une zone par application, chacune avec son "
            "préfixe, sa racine de scripts (hors du webroot), sa socket PHP-FPM, ses délais, ses fichiers d'index "
            "et sa liste blanche. Le préfixe le plus long l'emporte : /blog/admin/ peut être une zone fermée par "
            "liste blanche à côté de /blog/. Chaque zone a son interrupteur (Désactiver / Activer) : pendant la "
            "maintenance des fichiers d'une application, sa zone répond 503 et les autres continuent. L'option "
            "fastcgi du menu Options coupe toutes les zones d'un coup.")
        ),
    ),
    FaqEntry(
        category=_("FastCGI / PHP-FPM"),
        question=_("Une zone PHP a besoin d'autres réglages PHP (mémoire, taille d'envoi) : comment faire ?"),
        answer=(
            _("Avec un pool PHP-FPM par zone : chaque pool a sa socket, son compte système et ses propres "
            "réglages PHP, et la zone pointe vers la socket de son pool (champ « Socket PHP-FPM »). omega-serv ne "
            "transmet jamais de valeur PHP par requête (PHP_VALUE) : sur un pool partagé, cette valeur reste dans "
            "le processus PHP et déborde sur les requêtes suivantes des autres zones.")
            + " " + _("omega-serv n'installe, n'écrit ni ne vérifie la configuration de PHP-FPM : son édition reste "
            "de la responsabilité de l'administrateur. Pour que la zone fonctionne, le fichier de chaque pool doit "
            "au minimum contenir :")
            + "\n" + _("- listen : le chemin complet de la socket, le même que le champ « Socket PHP-FPM » de la "
            "zone ;")
            + "\n" + _("- listen.owner, listen.group et listen.mode (0660, par exemple) : le compte qui fait tourner "
            "omega-serv (omega-serv pour le service systemd) doit pouvoir se connecter à la socket, sinon la zone "
            "répond 503 ;")
            + "\n" + _("- user et group : un compte qui peut lire la racine des scripts de la zone.")
            + "\n" + _("Conseillé pour isoler les zones entre elles : un compte différent par pool et la valeur "
            "open_basedir limitée à la racine des scripts de la zone (réglée par php_admin_value dans le pool). "
            "L'écran Capacités indique si la socket de chaque zone active répond.")
            + " " + _("Chaque zone peut aussi fixer sa propre taille maximale de requête (vide = celle de l'écran "
            "Limites) : un envoi plus gros est refusé avant d'atteindre PHP ; réglez upload_max_filesize et "
            "post_max_size du pool en conséquence.")
        ),
    ),
    FaqEntry(
        category=_("Reverse proxy"),
        question=_("Quelle est la différence entre le \"reverse proxy sortant\" et `server.tls.mode = \"behind_proxy\"` ? "
                   "Les deux parlent de proxy..."),
        answer=_("Ce sont deux mécanismes INVERSES, qui ne s'activent jamais ensemble pour le même usage. "
                 "`behind_proxy` : Omega-serv est DERRIÈRE un reverse proxy tiers (nginx, Caddy...) qui le protège — "
                 "il fait confiance aux en-têtes `X-Forwarded-*` envoyés par ce proxy amont. Reverse proxy sortant : "
                 "Omega-serv agit lui-même comme proxy DEVANT un ou plusieurs backends HTTP/HTTPS qu'il relaie. "
                 "Confondre les deux revient à faire confiance à des en-têtes `X-Forwarded-*` qui n'existent pas, ou à"
                 " l'inverse écraser ceux d'un vrai proxy amont."),
    ),
    FaqEntry(
        category=_("Reverse proxy"),
        question=_("Un de mes upstreams de reverse proxy bascule DOWN puis UP sans arrêt (flapping) — pourquoi ?"),
        answer=_("La santé passive utilise des seuils de bascule DOWN et UP distincts, justement pour limiter ce "
                 "comportement — un upstream instable qui échoue puis réussit immédiatement en alternance peut tout de"
                 " même dépasser les deux seuils en boucle sur un backend réellement capricieux. Augmentez les seuils "
                 "(nombre d'échecs/succès consécutifs requis) depuis l'écran Reverse Proxy, ou activez la santé active"
                 " (sonde périodique indépendante du trafic réel) qui donne une mesure plus stable que les échecs du "
                 "trafic live."),
    ),
    FaqEntry(
        category=_("Reverse proxy"),
        question=_("Le cache du reverse proxy ne sert jamais mes réponses, même en rechargeant plusieurs fois la même "
                   "page — pourquoi ?"),
        answer=_("Plusieurs causes possibles, toutes volontaires : seules les méthodes GET/HEAD sont mises en cache "
                 "(jamais POST/PUT/DELETE), une réponse d'erreur n'est JAMAIS mise en cache, une réponse avec "
                 "`Set-Cookie` ne l'est pas non plus sauf opt-in explicite par zone, et le cache respecte l'en-tête "
                 "`Cache-Control` envoyé par votre backend lui-même (un backend qui renvoie `no-store` ou `private` "
                 "empêche la mise en cache, par construction). Vérifiez l'en-tête `X-Omega-Cache` sur la réponse "
                 "(HIT/MISS/BYPASS) pour diagnostiquer précisément quel cas s'applique, et l'écran dédié Cache du "
                 "reverse proxy pour la supervision."),
    ),
    FaqEntry(
        category=_("Gestion des logs"),
        question=_("Je vois \"vide\" sur un log dans un viewer ou dans lnav — le serveur a-t-il un problème ?"),
        answer=_("Pas forcément un bug : un viewer qui affiche \"vide\" reflète fidèlement un fichier réellement vide "
                 "sur le disque (0 octet) — par exemple `access.log` avant toute requête réelle reçue par le serveur, "
                 "ou un log natif dont le module correspondant n'a jamais été activé. Vérifiez la colonne \"Taille\" "
                 "dans la Bibliothèque : si elle affiche 0, le comportement est normal, pas un défaut du viewer."),
    ),
    FaqEntry(
        category=_("Gestion des logs"),
        question=_("lnav reste sur un écran noir qui semble figé pendant plusieurs secondes sur un gros fichier — "
                   "l'application a-t-elle planté ?"),
        answer=_("Non, pas un plantage : lnav indexe le fichier avant d'afficher quoi que ce soit, et rien côté "
                 "Omega-Serv n'affiche d'indicateur de chargement pendant cette phase — l'écran noir est simplement "
                 "l'attente de la première image envoyée par lnav. Plus le fichier est gros (des centaines de milliers"
                 " de lignes, par exemple un log centralisé via une Source distante SSH), plus cette attente est "
                 "longue. Patientez quelques secondes ; si l'écran ne revient vraiment jamais, c'est `Ctrl-Q` qui "
                 "reste la sortie normale de lnav lui-même."),
    ),
    FaqEntry(
        category=_("Gestion des logs"),
        question=_("Comment sont gérés le mot de passe ou la clé privée pour une Source distante (SSH) ?"),
        answer=_("Ils ne sont jamais gérés par Omega-Serv : aucun mot de passe n'est jamais demandé ni stocké, et une "
                 "clé privée n'est référencée que par son CHEMIN sur le disque — jamais lue ni copiée dans la "
                 "configuration. L'authentification reste entièrement déléguée à votre propre `ssh`/`scp` système et à"
                 " sa configuration habituelle (agent SSH, `~/.ssh/config`), exactement comme si vous tapiez la "
                 "commande vous-même dans un terminal."),
    ),
    FaqEntry(
        category=_("Gestion des logs"),
        question=_("Pourquoi les Sources distantes ne proposent que SSH, et pas Samba ?"),
        answer=_("Choix délibéré documenté dans l'étude de faisabilité dédiée : SSH est quasi toujours déjà présent "
                 "sur un backend Linux déjà administré, avec un modèle d'authentification déjà éprouvé (clé publique) "
                 "ne demandant à Omega-Serv aucune nouvelle responsabilité de gestion de secrets. Samba exigerait un "
                 "service CIFS dédié en plus côté backend, et reste documenté comme option de repli — à n'introduire "
                 "que si un besoin réel et concret se présente (parc mixte Windows, Samba déjà en place), jamais par "
                 "anticipation."),
    ),
)
