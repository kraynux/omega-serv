<!-- Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE) -->

# Changelog

Toutes les modifications notables de ce projet sont documentées dans ce fichier.

Le format est basé sur [Keep a Changelog](https://keepachangelog.com/fr/1.0.0/),
et ce projet adhère au [Semantic Versioning](https://semver.org/lang/fr/).

Pour un serveur exposé à Internet, une attention particulière est portée aux
changements de **comportement par défaut** (blocage, bannissement, adresse
client retenue) et aux **corrections de sécurité** : ce sont les changements les
plus susceptibles d'affecter une installation déjà en production, donc toujours
signalés explicitement, même mineurs.

## version 2.6.1 : construite le 2026-11-10, non publiée

Correctifs issus de l'étude de l'interconnecteur de la suite (`~/DEV/CONNECT/`), étape 1 : rendre chaque outil
sûr avant de les relier ; étape 2 : contrats communs (omega-lib 0.2.0).

### Ajouté

- **`synchro jeton` et `synchro fiche --format json`** (liens avec les autres outils omega, futur omega-connect) :
  - le **jeton d'installation** `var/omega-jeton.json` dit, sans rien exécuter, quel outil est là, sa version,
    un identifiant tiré au hasard, l'emplacement et le compte. Il est déposé par `install.sh` et mis à jour à
    chaque ouverture de l'interface ; jamais écrit en root ni par un autre compte que le propriétaire du
    dossier ; jamais publié (`var/` est exclu de l'archive). Un dossier copié reçoit un nouvel identifiant ;
  - la **fiche** de l'instance (fonctions actives : WAF, magnet, omega-waf, RIPOSTE, Active Defense, moteur
    natif, liste noire ; service ; journaux partagés et leur format ; réseaux jamais bannis automatiquement,
    comme `waf never-auto-block`) sort en JSON non traduit et versionné. Lecture seule, acceptée en root. Le service n'écrit jamais dans la future zone commune.
  - `omega-serv.sh synchro …` n'affiche plus la bannière de démarrage : la sortie reste du JSON pur, lisible
    par omega-connect.

- **`blocklist add --origin OUTIL` et `blocklist remove --origin OUTIL`** : un autre outil (omega-fire, le pont
  d'omega-jail) marque ses bans de son nom et ne lève **que** les siens, en une seule opération verrouillée.
  Avant, lever un ban se faisait en deux temps (lecture puis retrait) : un ban posé entre-temps par le WAF ou
  RIPOSTE sur la même adresse pouvait être levé par erreur. Origine réservée : `intervention`.
- **`blocklist list --format json`** : sortie versionnée et jamais traduite, pour les autres outils (la sortie
  texte, traduite, ne doit plus être analysée par un programme).
- **`service permissions`** (étape 3, lot E, `omega-connect reparer`) : la réparation du bouton de l'écran Service,
  en ligne de commande, précédée de la remise au propriétaire du dossier des fichiers de `var/` appartenant à root
  (une commande lancée en root les y avait créés : incident craftdark du 2026-10-18). Groupe lu dans l'unité du
  service. Demande sudo elle-même.
- **`synchro groupe-service ajouter|retirer`** (étape 3, lot E) : donne (ou retire) au service de cette instance le
  groupe `omega-synchro` de la zone neutre d'omega-connect, par un complément systemd
  `/etc/systemd/system/<service>.service.d/omega-synchro.conf` ; l'unité générée par `service install` n'est
  jamais touchée. Refusé si le groupe n'existe pas (le service ne démarrerait plus), si l'unité appartient à une
  autre installation, ou sans unité. Pris en compte au prochain redémarrage du service. Demandée par
  omega-connect (`etablir`, `retirer --tout`).

### Corrigé

- **Sécurité — réparation des permissions : liens symboliques jamais suivis.** `var/` est inscriptible par le
  compte du service : un lien `var/x → /etc/shadow` y aurait fait faire à root `chgrp omega-serv` et `chmod g+rw`
  sur la cible (installation du service, bouton « réparer les permissions », et désormais `service permissions`).
  Les liens sont maintenant écartés (`! -type l`) et `chgrp -h` traite un lien apparu entre-temps comme un lien.
- **`omega-serv.sh` ne lance plus `pip install` en root** (venv incomplet) : il demande de relancer `install.sh`
  sans sudo, comme `omega-jail.sh`. omega-connect lance certaines commandes avec sudo.

- **Commandes lancées en root refusées quand elles écrivent dans le projet** (`blocklist add/remove`,
  `riposte run`, `logs run-automations`, `auth`, `certs`, `config`, etc.) : lancées en root, elles créaient
  dans `var/` ou `secure/` des fichiers que le service ne pouvait plus modifier (même mécanisme que l'incident
  du 2026-10-18 : liste noire en root, puis 502). Restent permises en root : les commandes de lecture seule
  (vérifiées : aucun fichier écrit) et les commandes `service`, qui gèrent elles-mêmes leurs privilèges.
- **« Réparer les permissions » ne partage plus `var/backups/`** : les sauvegardes complètes contiennent
  `users.json`, les certificats et leurs clés privées. Elles devenaient lisibles par tout le groupe
  `omega-serv` ; elles sont maintenant sautées puis remises en accès propriétaire seul.
- **`var/run/` garde son bit setgid** : le `chmod` appliqué à chaque démarrage l'effaçait, et les fichiers
  créés ensuite par l'utilisateur dans `var/run/` gardaient son groupe personnel (illisibles par le service).
- **Mode log-only respecté par le script magnet omega-waf** : le serveur lui transmet désormais le mode du WAF
  (`omega_waf_mode`). En log-only, omega-waf ne pose plus de ban ; avant, sa ligne `AJOUT BLOCKLIST` devenait
  un ban réseau fail2ban alors que le serveur, lui, ne bloquait rien.

## version 2.6.0 : Publié

### Ajouté

- **Version affichée et vérification des mises à jour** : la barre de titre montre la version (« OMEGA-SERV 2.6.0 »),
  lue dans `pyproject.toml`, seule source (le splash n'a plus de version écrite en dur). Guide d'aide → Contact et
  support → « Vérifier les mises à jour » : compare la version installée à la liste des versions publiées
  (`download/sha.txt` du site), seulement sur votre clic, rien n'est envoyé ; « Voir les nouveautés » ouvre le
  résumé de la nouvelle version. En ligne de commande : `omega-serv version` et `omega-serv version --check`
  (code 1 si le site est injoignable).
- **Voir et traiter IP : recherche manuelle** : saisir une IP (IPv4 ou IPv6), voir son nombre de lignes dans
  chaque log sélectionné (fichier entier) et la retirer directement, sans attendre qu'elle apparaisse dans le top.
- **Gestion des logs → Statistiques** (5e bouton de la colonne BIBLIOTHÈQUE), même écran qu'omega-log : un ou
  plusieurs logs de la Bibliothèque, quel que soit leur format, période 24h / 7j / 30j / « Tout (fichier
  entier) ». Synthèse, statuts HTTP en jauges, top IP, chemins demandés et en 404, répartition horaire,
  tendance par jour. Export JSON et HTML (5 thèmes, langue des exports). Remplace l'ancien écran limité à
  l'access log, qui n'était plus relié à aucun menu.
- **Gestion des logs → Santé des logs** (5e bouton de la colonne MAINTENANCE) : contrôle en lecture seule des
  logs d'omega-serv et de la Bibliothèque, du disque qui les porte et des archives. Fichier absent ou lien
  cassé, droits (lecture par votre compte, écriture par le compte du service, écriture par tout le monde),
  log muet depuis plus de 7 jours, fichier vide, dates non reconnues ou dans le futur, octets nuls, seuil de
  rotation dépassé, gros log sans règle logrotate, doublon dans la Bibliothèque ; croissance par jour et
  jours avant disque plein. Chaque constat dit quoi faire. « Corriger les droits » rend un log d'omega-serv
  de nouveau inscriptible par le service (bit d'écriture du groupe, après confirmation, sans sudo, quand vous
  êtes propriétaire du fichier). Export JSON, HTML et TXT. Fiches F1, 16 langues.
- **Authentification sudo quand les droits bloquent**, même mécanisme que l'écran Service (l'interface est
  suspendue, `sudo -v` demande le mot de passe dans le terminal, puis des commandes `sudo -n` : jamais de mot
  de passe demandé ailleurs) :
  - **Statistiques** et **Voir et traiter IP** : un log illisible par votre compte (par exemple
    `/var/log/auth.log`) déclenche la demande, puis il est lu avec sudo ; un refus affiche le chemin en cause.
    La lecture sudo se fait dans le processus de l'interface, jamais dans les processus de calcul : elle marche
    aussi quand sudoers mémorise l'authentification par processus parent (`timestamp_type=ppid`).
  - **Santé des logs → Corriger avec sudo** : quand « Corriger les droits » ne suffit pas (fichier à root,
    groupe étranger au service) ou qu'un log est inscriptible par tout le monde. La commande exacte est montrée
    avant : `chgrp` vers le compte du service puis `chmod g+w`, ou `chmod o-w`. Jamais `chown`, jamais
    récursif, un seul fichier.
  - **Santé des logs → Analyser avec sudo** : lit avec sudo le début et la fin des logs illisibles par votre
    compte (dates, format, octets nuls) ; le constat « illisible par votre compte » reste affiché.
- **Rotate / archivage : les automatisations s'exécutent pour de vrai.** Jusqu'ici elles étaient seulement
  enregistrées, rien ne les lançait. La première automatisation installe une tâche planifiée quotidienne,
  la dernière supprimée la retire :
  - **systemd** : timer `<service>-log-rotation.timer` (mot de passe sudo demandé à l'installation) ;
  - **OpenRC, runit ou aucun gestionnaire** : ligne de votre crontab, sans privilège (il faut un démon cron
    actif : cronie, dcron, busybox crond…) ; une autre instance garde sa propre ligne ;
  - **sans crontab** : la ligne à ajouter vous-même est affichée.

  Chaque nuit, la nouvelle commande `omega-serv logs run-automations` (sous votre compte, jamais root) archive
  chaque log arrivé à échéance, comme « Sauvegarde maintenant ». Un échec est retenté la nuit suivante.
  « Gérer les automatisations » montre l'état de la tâche, la dernière et la prochaine exécution, et propose
  « Réinstaller l'exécution ».
- **Santé des logs → AUTOMATISATIONS** : signale une automatisation de rotation en échec (avec l'erreur), en
  retard de plus de 2 jours (machine éteinte la nuit sans systemd, démon cron arrêté), ou des automatisations
  sans tâche planifiée pour les exécuter ; aussi dans les exports JSON, HTML et TXT.

### Modifié

- **Viewer Simple** : titre et panneau remontés, trois lignes de plus pour le cadre de statistiques ; en plein
  écran, il s'affiche en entier sans ascenseur ; quand l'ascenseur apparaît, une colonne vide le sépare des
  chiffres (on ne devine plus si un chiffre est caché derrière).
- **README** : nouvelle section « 13a. Gestionnaire de logs » (lire, analyser — dont la recherche d'une IP précise —,
  contrôler, sauvegarder, automatiser) ; « Sources distantes (SSH) » devient 13b. Même chose dans les 16 langues, avec
  le site (readme, présentation, guide : fiches Statistiques et Santé des logs, 75 fiches).
- **Multi-instance** : les boutons sont sur trois rangées (Rafraîchir et Créer une nouvelle instance ; Piloter et
  Désinstaller cette instance ; Retour) ; sur une seule ligne, un petit terminal les coupait.

- **Voir et traiter IP** : le calcul tourne en arrière-plan, sur plusieurs cœurs pour un gros log, avec le
  même indicateur d'attente qu'omega-log (roue, messages, temps écoulé, barre de progression réelle). La
  taille et le nombre de lignes estimé de la sélection s'affichent avant le clic ; « Tout » devient « Tout
  (fichier entier) », avec l'avertissement de durée.
- Analyse des lignes de log plus rapide (mêmes résultats), reprise d'omega-log.

### Corrigé

- **Voir et traiter IP** : « Retirer cette IP » ne retirait aucune ligne pour une IPv6 terminée par `::` (par exemple
  `2a03:2880:f800:15::`) ; la règle de correspondance ne coupe plus non plus une IP plus longue (1.1.1.1 ne touche
  jamais 1.1.1.11).
- **Aide F1 de Santé des logs** : la fiche citait une colonne « origine » qui n'existe plus et disait qu'omega-serv
  ne fait pas tourner ses logs tout seul ; elle renvoie maintenant vers la sauvegarde immédiate ou l'automatisation
  planifiée de Rotate / archivage (16 langues).
- Voir et traiter IP : sur un gros log, l'interface restait figée pendant tout le calcul.
- Commandes externes : une sortie contenant un octet non UTF-8 (log lu avec sudo) ne fait plus planter la
  lecture, les octets invalides sont remplacés.

## version 2.5.0 : Publié

### Ajouté

- **Active Sécurité → INTERVENTION MANUELLE** : un 4e cadre sous les colonnes WAF / Active Defense / RIPOSTE, avec
  trois boutons. *Bannir* bannit une adresse IP sans condition (aucune règle, aucun seuil) dans la blocklist du WAF :
  page 451 sur tout le site, avant le routage, donc jamais vue par les backends ; sans droits root, effet immédiat
  avec les deux moteurs ; durée 1 h à 30 jours, libre ou permanente (confirmée). Un réseau est refusé (il se bannit
  dans WAF → Modules) ; adresse locale, privée ou Tailscale : confirmation. *Débannir* ne montre et ne lève que ces
  bans manuels. *Statut des bans* liste tous les bans avec leur origine (intervention manuelle, manuel, auto-ban WAF
  règles ou liste, RIPOSTE, omega-jail, Magnet) et les exporte en JSON, HTML (thèmes) ou TXT d'injection (bans actifs
  ou toute la liste, une adresse par ligne, en-tête « # » : importable tel quel dans omega-fire). Sans lien avec
  Active Defense ni RIPOSTE : un ban manuel ne compte jamais dans la récidive, et aucun automate ne le remplace.
  Fiches F1, 16 langues.

- **Aide complète de la ligne de commande** : chaque commande et chaque option ont désormais un texte
  d'aide (`omega-serv <commande> --help`, jusque-là les noms seuls). Nouvelle commande `omega-serv help`
  (arbre de toutes les commandes, ou d'une branche : `omega-serv help riposte`), page de manuel
  `man omega-serv` installée par `install.sh` dans `~/.local/share/man/man1/` (sans sudo) et référence
  `docs/HELP.md`. La page de manuel et `docs/HELP.md` sont générées depuis le code
  (`tools/cli_reference.py`) ; un test signale toute commande sans aide ou tout document en retard.
  Textes d'aide, `omega-serv help` et les nouveaux messages (packs WAF ajoutés, « expire le » de
  `blocklist add`) traduits dans les 16 langues (249 phrases) ; la page de manuel et `docs/HELP.md`
  restent en français.
 doit on changer la version en 2.5.1
- **État & Ressources plus complet** *FLUX* : relit à l'ouverture les 15 dernières minutes du journal d'accès (plus de cadre vide au
  départ), débits sur la dernière minute et les 5 dernières, top 5 des IP, des chemins demandés et des
  chemins en 404 (souvent des scanners), section *SÉCURITÉ* (attaques bloquées, refus de liste de blocage et
  de limite de débit lus dans le journal d'alertes du WAF, refus 403/429, IP bannies dont RIPOSTE) et les
  5 dernières requêtes. *RESSOURCES* : nouvelle section *OMEGA-SERV* (processus du serveur avec CPU, RAM,
  fils, fichiers ouverts et durée de fonctionnement ; connexions établies sur son port ; taille des
  journaux et plus gros fichier ; espace libre de `var/`). Lecture seule, toujours hors du fil de l'écran. Titres des
  cadres et des sections centrés ; jauges CPU, RAM et disque colorées selon le niveau (vert jusqu'à 49 %,
  jaune de 50 à 74 %, orange de 75 à 94 %, rouge à partir de 95 %), teintes prises dans le thème actif. *ÉTAT DU
  SERVEUR* : nouvelles sections *INSTANCE* (nombre d'instances, l'instance courante comprise même si elle
  n'est pas inscrite au registre, celle qui affiche l'écran, puis au plus 3 instances avec leur PID, la
  courante d'abord puis celles en marche) et *SAUVEGARDE* (date de la dernière sauvegarde et nombre de
  sauvegardes du menu Sauvegarde) ; les options actives ont leur titre *CONFIGURATION OPTIONS*. *RÉSEAU* :
  section *INTERFACES* (cartes ethernet et wifi, l'active - celle de la route par défaut - en vert). Graphique
  TCP/UDP sous *Débit* (paquets/s sur les 2 dernières minutes, le noyau ne comptant pas les octets par
  protocole) ; ligne *Envoyé* d'omega-serv (somme des tailles de réponse de l'access log depuis le
  démarrage du serveur : Linux ne compte pas le réseau par processus) ; swap, charge (rapportée au nombre
  de cœurs, affiché) et espace libre de `var/` (barème retourné) colorés selon le niveau. Bouton
  **access.log** : ouvre directement le viewer Simple sur l'access log de l'instance, sans sélection.
- **Viewer Simple : repris du tableau de bord** - refus 403 et 429, top 5 des IP (au lieu d'une seule),
  top 5 des chemins demandés et des chemins en 404 (sans la partie `?…`), chemin depuis le bord gauche et
  compte collé à droite ; le cadre de gauche défile. Tableau de bord : icônes devant les titres de section
  et les lignes clés (emoji de largeur fixe, l'alignement est conservé). Viewers Simple et Classique :
  titre et boutons centrés. État & Ressources remonté de deux lignes (moins de vide sous l'en-tête). README : police emoji (Noto
  Color Emoji) ajoutée aux outils facultatifs - une Nerd Font ne contient pas ces icônes.
- **Contact et support** (Guide d'aide, touche `a`) : *Payer un café* (page PayPal du développeur),
  *Contacter le support* (formulaire de contact du site, adresse mail affichée ; aucun formulaire dans
  omega-serv) et *Se déclarer utilisateur (anonyme)*. La déclaration est **volontaire et désactivée par
  défaut** : une clé tirée au hasard, la version, le mode choisi (*une seule fois* ou *chaque jour*) et,
  facultatifs, un continent et un pays pris dans des listes fermées (249 pays, noms traduits dans les
  17 langues). Le message exact est affiché avant l'envoi. En mode *chaque jour*, `serve` lance au plus un
  envoi par 24 h dans un **processus séparé** (jamais un fil dans le serveur, jamais attendu au démarrage ni
  à l'arrêt) ; une seule ligne au journal d'erreurs par série d'échecs ; `DO_NOT_TRACK=1` coupe tout envoi
  automatique. *Ne plus me déclarer* supprime l'entrée côté réception puis efface la clé locale. Aucun mot de
  passe ni secret dans le code, aucune dépendance ajoutée (`urllib`). État sous `var/lib/declaration/`.
  Ligne de commande : `omega-serv declaration status | declare | withdraw`. Fiches d'aide F1, guide du site
  et README dans les 17 langues.
- **Version 2.5.0** : numéro porté dans `pyproject.toml`, splash « 2.5.0 », README et pages du site
  (téléchargement, « Version : ») dans les 17 langues.
- **README : outils de compilation du moteur natif** (documentation). « Outils optionnels recommandés »
  liste désormais `cmake`, un compilateur C++20, les en-têtes OpenSSL 3 et PCRE2, avec leur commande
  d'installation (Arch, Debian/Ubuntu, Fedora) : nécessaires seulement si le moteur natif fourni ne démarre
  pas (glibc antérieure à 2.38). Jusqu'ici, seul le message d'`install.sh` les citait. 17 langues.
- **Sauvegarde de configuration complète** : case **« Tout sauvegarder (configuration complète) »**
  (`config backup --all`) et nouvelles cases — **RIPOSTE** (`--include-riposte`), **pages d'erreur
  personnalisées** (`--include-error-pages`), **préférences** : thème, langues, nom du service
  (`--include-preferences`), **bibliothèque des journaux** : favoris, sources distantes, rotations planifiées
  (`--include-logs-library`). Après la création, ce qui n'a pas pu être archivé est indiqué (ex. un certificat
  hors du dossier omega-serv). Nouvelle option `config restore --stop-and-restart`.
- **Moteur HTTP natif** : réglage `server.engine` (`python` par défaut, `native`). Le moteur
  natif (C++) sert le contenu statique ; le serveur Python garde la configuration, la sécurité et la surveillance.
  Il gère aussi TLS en mode direct (même bibliothèque OpenSSL et mêmes réglages que le moteur Python : versions,
  suites, certificat, phrase de passe ; un certificat inutilisable empêche le démarrage, jamais de HTTP à la place).
  Avec WAF, Auth, Active Defense ou leurres actifs, chaque requête passe par un processus Python de sécurité qui
  applique exactement les mêmes contrôles que le moteur Python (mêmes alertes, mêmes journaux de sécurité) ; s'il ne
  répond pas, `waf.on_internal_error` décide (servir sans contrôle ou 503), et une zone Auth active est toujours
  refusée (503) dans ce cas.
  Pour alléger ce contrôle, le moteur natif transmet l'adresse client déjà résolue et indique quand une adresse est
  absente de la blocklist (relue à chaque requête : un ban ajouté ou retiré s'applique dès la requête suivante) ;
  dans tous les autres cas, le contrôle Python vérifie lui-même.
  **Interface** : choix du moteur dans **Configuration de base** (le choix « Natif C++ » est grisé tant qu'une
  cause l'empêche, avec ce qu'il faut changer pour le rendre possible) ; ce qui tournera au prochain démarrage est
  affiché tel quel (« moteur natif, 1 processus ») ; avec le moteur natif, les processus réglés dans **Résistance et
  limites** sont ceux des contrôles de sécurité : 1, ou 2 à partir de 4 cœurs physiques, l'écran disant ce qu'un 2e
  apporte sur la machine ; tableau des connecteurs (natif, contrôle Python, route Python, confié à Python) dans
  **État & Ressources** et `omega-serv engine status` ; un réglage enregistré ailleurs (TLS, options, profil) qui
  ferait perdre le moteur natif demande d'abord une confirmation. FAQ « Moteur HTTP et performances », avec ce que
  le choix du moteur et du nombre de processus change, mesuré.
  **Installation** : l'archive contient le moteur natif compilé (x86_64, glibc 2.38 ou plus récente, OpenSSL 3) ;
  `install.sh` vérifie qu'il démarre et, sinon, le recompile sur place quand cmake, un compilateur C++20 et les
  en-têtes OpenSSL sont présents — sans jamais bloquer l'installation. Une nouvelle instance reçoit aussi le moteur
  natif.
  Les routes applicatives (reverse proxy, FastCGI/PHP, envoi de fichiers, WebSocket) sont confiées au moteur Python
  pour toute la suite de la connexion, et le listing de répertoire lui est demandé : mêmes réponses qu'avec le moteur
  Python. En mode `fail-open`, une adresse déjà bannie reste refusée (451) même si le contrôle est indisponible.
  Seule combinaison non prise en charge : TLS direct avec ces routes applicatives.
  Si le natif ne peut pas tout servir ou ne démarre pas, le moteur Python est
  utilisé à sa place et la raison est affichée (écran État & Ressources, `omega-serv engine status`, error.log) -
  jamais un serveur à moitié natif. Changer de moteur demande un redémarrage complet : un rechargement qui l'exigerait
  est refusé avec ce message.
- **RIPOSTE** : 3e module de Sécurité active, qui
  décide de réponses graduées dans la durée (bans de plus en plus longs pour les récidivistes). Option
  `riposte`, désactivée par défaut ; l'activer demande un redémarrage complet. Processus séparé lancé et
  surveillé par `serve` (mode simple et mode boost, un par instance, relancé s'il s'arrête, jamais au
  détriment du serveur web), qui lit `waf-alerts.log` et `security-events.jsonl`, tient une mémoire de
  récidive par IP (épisodes, retours, paliers 1 h / 6 h / 24 h / 7 j, fenêtre 30 j, historique 90 j) et
  **applique** ses décisions : ban local dans la blocklist du WAF (source `riposte`, toujours avec une
  échéance, jamais au-dessus d'un ban manuel, permanent ou plus long) ou leurre Active Defense prolongé.
  Registre des actions (en cours / terminées, rien ne disparaît), vérifié au démarrage et toutes les
  60 s (une action retirée à la main est vue comme telle). Sans WAF, les bans restent sans effet et le
  disent. Commandes : `riposte status`, `riposte scenarios list|show`, `riposte policies
  list|show|enable|disable [--revoke]`, `riposte simulate`, `riposte measure` (rejeu d'une politique sur
  les journaux), `riposte sources list|show|forget`, `riposte decisions list`, `riposte actions
  list [--finished]|show|revoke [--exempt 24h|7d|forever] [--not-recidive]|not-recidive`,
  `riposte exemptions list|remove`, `riposte stop [--revoke]` (arrêt d'urgence, persistant) et
  `riposte resume`. Base séparée `var/lib/riposte.sqlite3`. Aucune dépendance nouvelle.
  **Interface** : l'écran ACTIVE SÉCURITÉ passe à trois colonnes dans l'ordre d'une attaque — WAF, ACTIVE
  DEFENSE, RIPOSTE — et tient en 80 colonnes ; le bouton WAF « Exclusions et débit » devient « Limitations »
  (le titre de l'écran ne change pas). Six écrans RIPOSTE : **État** (processus, actions en cours, arrêt
  d'urgence / Reprendre), **Politiques** (ajout à partir d'un scénario, d'une copie ou d'un formulaire
  vierge ; modifier, activer, désactiver avec ou sans levée des actions, retirer), **Actions** (en cours /
  terminées, lever, lever et exempter 24 h / 7 j / toujours, « ne compte pas dans la récidive »),
  **Récidives** (chronologie par source, oublier une source), **Simuler** (décision expliquée, décisions
  récentes) et **Réglages** (paliers, fenêtres, plafond, exemptions). Le formulaire de politique explique
  chaque champ, mesure la politique sur les journaux des 7 derniers jours, demande une confirmation nommée
  pour un réglage moins prudent (durée > 7 j, niveau « suspicious ») puis propose Activer / Enregistrer sans
  activer. Les heures de `riposte status` sont affichées à l'heure locale.
  **Ban réseau** (action « ban local + ban réseau ») : après le ban local, RIPOSTE écrit une ligne dans
  `var/log/riposte-decisions.jsonl`, lue par les jails omega-jail `<service>-riposte-1h/6h/24h/7d` de l'instance ;
  chaque palier va à la jail la plus longue qui ne le dépasse pas (affiché : « palier 2 h -> jail …-1h »). Une levée
  ne retire que le ban local et le dit ; l'écran État indique les jails installées ou absentes et signale la jail
  `omega-serv-active-defense` (ban fixe de 24 h) qui écrase les paliers réseau. Nécessite omega-jail avec les jails
  RIPOSTE.
  Interface et aide (F1, FAQ) traduites dans les 16 langues ; README, readme.html et guide.html décrivent RIPOSTE
  dans les 17 langues.
  FAQ (guide et F1) : 7 questions sur les bans RIPOSTE — page 451 ou fail2ban, rôle des jails
  `<service>-riposte-*`, mise à jour d'omega-jail, bans derrière Tailscale Funnel (relayés en 451 par
  omega-jail), jail
  `omega-serv-active-defense`, attaque de test sans effet, bans visibles dans omega-fire.

- **Journal des événements de sécurité** `var/log/security-events.jsonl` (Active Defense, réglable par
  `options.active_defense.logging.security_events_path`). Une ligne JSON par événement — escalade de
  niveau d'une source, incident ouvert, leurre affecté, visite d'un leurre — jamais par requête normale.
  Contenu : identifiant unique, type, date, IP, identifiant de source (IP + empreinte du User-Agent),
  niveau, score, classe d'attaque, incident ou profil de leurre ; jamais de corps, d'en-têtes ni de
  User-Agent en clair. Ces événements existaient déjà dans le code mais n'étaient écrits nulle part ;
  ils servent de source au futur module RIPOSTE et à tout outil externe.
- **Champ `stage` dans `waf-alerts.log`** : étape du WAF qui a produit la décision (`blocklist`,
  `rate_limit`, `inspection`). Un refus parce que l'IP est déjà dans la blocklist (score 0, sans règle)
  devient identifiable. Ajout seulement : aucun champ retiré, les jails omega-jail (qui ne lisent que
  l'IP et l'action) fonctionnent sans changement.

### Modifié

- **Archive allégée : 7,1 Mo au lieu de 9,0 Mo.** Les tests (Python et C++, vecteurs compris), un
  reste de compilation (`build/`), les fichiers `HEADER.txt` et les sources de traduction d'omega-lib ne
  sont plus livrés ; seuls ce qui sert à l'installation et à l'exécution reste. La compilation locale du
  moteur natif par `install.sh` fonctionne sans les tests.

- **Nombre de processus (`server.workers`) limité selon le moteur et le processeur** : avec le moteur Python, au plus
  un processus par **cœur physique** (auparavant : par CPU logique, hyperthreading compris — au-delà, les mesures
  ne montrent aucun gain) ; avec le moteur natif, 1, ou 2 à partir de 4 cœurs physiques. L'écran **Résistance et
  limites** affiche le maximum de la machine et ce qu'augmenter apporte, et refuse une valeur trop grande ou 0.
  **Une configuration existante démarre toujours** : une valeur trop grande, ou l'ancien `0` (automatique), est
  ramenée au maximum de la machine, avec un message dans le journal d'erreurs et dans **État & Ressources**.
  Passer au moteur natif avec un nombre de processus trop grand demande de le ramener au maximum (confirmation).
- **WAF plus rapide, avec les mêmes décisions** (moteurs Python et natif) :
  - les règles insensibles à la casse sont cherchées sur le texte mis en minuscules, quand le texte est en ASCII et
    que la règle est prouvée équivalente (sinon, recherche d'origine) ;
  - seules les parties de la requête qu'une règle lit sont préparées et parcourues ;
  - la normalisation est sautée quand elle ne changerait rien (texte ASCII sans `%`) ;
  - la liste de blocage répond tout de suite quand elle est vide et mémorise les adresses déjà analysées ;
  - avec le moteur natif, le processus de sécurité traite une requête propre sans attente dans la boucle et
    renvoie un verdict préparé à l'avance.

  Des tests comparent l'ancien et le nouveau calcul sur toutes les règles livrées.
- **Moteur natif avec WAF : les requêtes propres ne passent plus par Python.** Le moteur natif évalue lui-même les
  règles du WAF (traduites depuis les règles Python et vérifiées contre elles) et sert directement une requête sur
  laquelle **aucune règle ne correspond**. Tout le reste part au processus de sécurité Python, qui décide et
  journalise comme avant : correspondance, adresse bannie, zone protégée, texte non ASCII, toutes les requêtes
  d'une source qui a un état Active Defense ou un leurre (pendant la durée de cet état, leurres affectés par RIPOSTE
  compris), et toutes les requêtes quand magnet est actif. Sans processus de sécurité,
  `on_internal_error` s'applique comme avant (fail-closed et authentification : 503).
  Compilation du moteur natif : PCRE2 conseillé (lié dans le binaire, rien à installer pour l'utiliser) ; sans
  PCRE2, le moteur fonctionne comme avant, chaque requête étant inspectée par Python.
  - Au chargement, le moteur natif rejoue pour chaque règle des textes de contrôle calculés par Python ; au moindre
    désaccord, ou si une règle ne peut pas être traduite, elle reste évaluée par Python seul et une ligne l'indique
    dans le journal d'erreurs.
  - Nouveau réglage `options.waf.native_check_every` (0 par défaut, désactivé) : une requête jugée propre par le
    moteur natif sur N est quand même soumise à Python, qui la traite normalement et journalise tout désaccord.
  - Limite de débit comptée par le moteur natif, qui voit toutes les requêtes : même seau à jetons et mêmes règles
    (dossier, IP/réseau, globale) que Python, même réponse 429 et mêmes journaux, écrits par Python. L'activer ne coûte
    plus rien de mesurable (machine A : 11 391 req/s avec, 11 330 sans ; avant, toutes les requêtes passaient par
    Python). Les requêtes servies par un leurre ou refusées par la liste de blocage comptent aussi : plus strict
    qu'avec le moteur Python, jamais plus permissif.
  - Écrans : avec le moteur natif, WAF — État indique combien de règles il évalue lui-même, s'il sert seul les
    requêtes propres (sinon pourquoi) et l'état du contrôle 1/N, réglable dans WAF — Modules.
  - Mesuré sur trois machines : avec le WAF, le moteur natif sert 3,4 à 6,8 fois plus de petites pages qu'avant et
    garde 78 à 95 % de son débit sans WAF. Un 2e processus de sécurité n'apporte plus rien au trafic ordinaire.

### Corrigé

- **Exports HTML jamais échappés** (registre des capacités, archives de logs, guide d'aide) : le réglage
  d'échappement ne reconnaissait pas l'extension `.html.j2` des modèles. Dans l'export du guide, les emplacements
  comme `<nom-archive>` ou `<adresse>` disparaissaient (pris pour des balises) ; un texte venu de l'extérieur aurait pu
  injecter du HTML. Tous les exports sont désormais échappés.

- **WAF → Modules → Liste de blocage** : la colonne et le champ « Motif » d'un ban s'affichaient « Pattern » (et
  l'équivalent dans les autres langues), traduits comme le motif d'une règle ; ils s'appellent désormais « Motif du ban ».

- **Bans ignorés après un ban d'omega-jail** (constaté en production) : `omega-serv blocklist add`, lancé par
  le pont omega-jail sous un umask 077, recréait `var/lib/waf/blocklist.json` en `600` - illisible par le
  service. Les adresses bannies continuaient de recevoir 403/404 au lieu de la page 451, et les auto-bans du
  WAF étaient refusés (« blocklist illisible » dans journalctl). La blocklist est désormais toujours écrite
  lisible et modifiable par le groupe du service (660 au minimum, groupe conservé), quel que soit l'umask de
  celui qui écrit (CLI, omega-jail, RIPOSTE, auto-ban) ; un fichier déjà resté en 600 est réparé à la
  prochaine écriture.

- **`option enable waf` donnait un WAF sans aucune règle** sur une configuration neuve : `config check` et
  `serve` le refusaient ensuite (« rules.paths et keyword_lists ne peuvent pas être tous les deux vides »),
  sans moyen de choisir les packs en ligne de commande. À la première activation, tous les packs présents
  dans `secure/waf/rules/` sont désormais ajoutés, en mode log-only (rien n'est bloqué tant que le mode
  n'est pas `block`, comme avant) ; des packs déjà choisis ne sont jamais remplacés. Même comportement
  depuis l'écran Options.
- **RIPOSTE : une politique « leurre » enregistrée sans profil choisi recevait le profil « Select.NULL »**
  (nom inexistant) au lieu de « aucun profil ». Même cause, corrigée aussi : « Retirer l'épingle » de lnav
  sans épingle choisie ne disait rien. Les listes déroulantes qui ont toujours une valeur (thème d'export,
  action, journal et fréquence de la rotation) ne proposent plus de ligne vide.
- **`blocklist add` affichait « (_(expire )2026-…) »** pour un ban à durée limitée : le message indique
  désormais « (expire le 2026-…) ».
- **État & Ressources : le « Débit » réseau affichait le total depuis le démarrage de la machine**, pas un
  débit. Il affiche désormais les octets reçus et envoyés par seconde, mesurés entre deux rafraîchissements.
- **État & Ressources : un cadre trop long était coupé au lieu de défiler** (la fin du contenu restait
  invisible). Chaque cadre défile désormais réellement, la barre d'actions restant fixe en bas.
- **Installation : avertissement setuptools répété** (« `project.license` as a TOML table is deprecated ») pendant
  `install.sh`. `pyproject.toml` déclare désormais la licence au format SPDX (`license = "MIT"`,
  `license-files = ["LICENSE"]`, setuptools 77 ou plus récent, téléchargé automatiquement par pip).
- **Alias : une cible absolue sous `/var` du système était refusée** (« alias vers un dossier interdit (var/) »),
  par exemple `/var/www/html` ou `/var/secure`, même avec `allow_outside_webroot`. La règle visait les dossiers
  `secure/`, `config/`, `src/` et `var/` d'omega-serv lui-même : elle s'applique désormais à eux seuls, y compris
  quand une cible absolue ou un lien symbolique y ramène.

- **Interface, formulaires « Ajouter un profil » et « Ajouter une zone » (Active Defense → Réglages)** : un profil
  ou une zone invalide fermait le formulaire sans rien enregistrer, et la raison s'affichait en haut de l'écran
  Réglages, souvent hors de vue ; il fallait tout ressaisir. Le formulaire reste désormais ouvert, affiche la
  raison sous les champs et garde la saisie : on corrige le champ fautif et on valide de nouveau. La fiche FAQ
  correspondante (guide et F1, 17 langues) est mise à jour.

- **Documentation, badges** : « Python pur » et « Sans dépendance » ne décrivaient plus omega-serv depuis le
  moteur natif ; ils deviennent « Python + C++ natif » et « Cœur HTTP stdlib » (index, présentation, readme,
  17 langues). L'étape d'installation du README précise « aucune dépendance externe **pour le cœur du serveur** »,
  comme le readme du site.

- **Documentation, commandes fausses** : `simulate-request` s'écrit `--method GET --url /index.html` et
  `auth create-zone` attend `--path-prefix` et `--realm` (le README et le guide donnaient `--url-prefix` et des
  arguments sans option, refusés) ; `diagnostics`, cité par le guide, n'existe pas. Toutes les commandes du guide
  sont désormais vérifiées par le parseur du CLI, et les 16 commandes qui manquaient à « Commandes utiles
  étendues » y sont ajoutées (`serve`, `config enable-tls|disable-tls`, `engine status`, `waf never-auto-block`,
  `certs import|verify`, `auth change-password|remove-user|remove-zone|check-permissions`,
  `service reload|enable|disable|uninstall`).

- **Sécurité, analyse HTTP plus stricte (RFC 9112)** : un nom d'en-tête contenant une espace ou une
  tabulation (`X-A : 1`) était accepté après nettoyage ; un `Content-Length` écrit `+5`, `1_000` ou avec des
  chiffres non ASCII était lu comme un nombre. D'autres serveurs (proxy devant omega-serv) peuvent lire ces
  formes autrement, ce qui ouvre la porte à la désynchronisation de requêtes (« request smuggling »). Ces
  requêtes reçoivent désormais **400** (lignes dans error.log et access.log, comme toute erreur d'analyse).
  Aucun client HTTP normal n'envoie ces formes.
- **Sécurité, version HTTP vérifiée (RFC 9112 / 9110)** : toute version commençant par `HTTP/` était servie
  (`HTTP/9.9`, `HTTP/2.0`, `HTTP/abc`...). Une version mal écrite reçoit désormais **400**, une version majeure
  autre que 1 reçoit **505** (« HTTP Version Not Supported ») ; `HTTP/1.2` à `HTTP/1.9` sont traitées comme
  `HTTP/1.1`. Les navigateurs et outils courants envoient `HTTP/1.0` ou `HTTP/1.1` : rien ne change pour eux.
- **Cible de requête en forme absolue acceptée (RFC 9112)** : `GET http://hôte/page HTTP/1.1` cherchait un
  fichier nommé d'après l'adresse entière (404). Le chemin est maintenant extrait et servi normalement ;
  l'hôte de l'adresse remplace l'en-tête `Host`, qui reste obligatoire. Un hôte vide, avec identifiants
  (`user@`), espace ou caractère de contrôle reçoit **400**. Seuls `http://` et `https://` sont reconnus.
- **Logs, erreurs d'analyse dans access.log** : une requête refusée avant d'être traitée (mal formée, trop
  grande, version refusée, `Expect`, `Host` invalide, corps trop lent ou tronqué) n'écrivait qu'une ligne dans
  error.log ; elle écrit désormais aussi sa ligne dans access.log, visible par fail2ban, omega-jail et RIPOSTE.
  La ligne de requête y figure telle que reçue (`-` si elle n'a pas pu être lue). L'adresse client suit la
  même règle de proxy de confiance que les autres requêtes, avec les en-têtes déjà lus : une erreur détectée
  sur la ligne de requête elle-même est donc attribuée à l'adresse du proxy quand un proxy est devant
  omega-serv. La ligne d'error.log porte maintenant l'identifiant de requête, comme la ligne d'access.log.
- **Restauration d'une sauvegarde avec base pendant que le serveur tourne** : la vérification « serveur en
  marche » lisait mal le fichier PID et répondait toujours « arrêté » ; la restauration n'était donc pas bloquée
  comme prévu. Elle l'est désormais, et « Arrêter, restaurer, redémarrer » attend réellement l'arrêt.
- **Listing de répertoire : un lien symbolique en boucle ou cassé faisait planter tout le listing** (connexion
  fermée sans réponse). Ces entrées, inaccessibles de toute façon, sont désormais simplement absentes de la liste.
- **Logs, guillemets échappés dans access.log** : un guillemet `"` envoyé par le client (requête, Referer,
  User-Agent) était écrit tel quel et fermait le champ avant l'heure : la ligne devenait illisible pour les
  statistiques et l'écran des journaux, et un client pouvait faire apparaître un faux statut (« 404 ») devant le
  vrai. Il est désormais écrit `\x22`, comme nginx. Les outils qui lisent le format combiné (fail2ban,
  omega-jail, lnav, goaccess) ne sont pas affectés.
- **Logs, viewer Simple** : la barre de statut se limitait à « Aperçu » et « Top IP » ; elle reprend celle
  du viewer Simple d'omega-fire — rendement (débit, latence moyenne), bande passante (débit réseau, volume,
  taille moyenne), statuts HTTP, clients et réseau, santé et tampon — calculée uniquement sur les valeurs
  présentes dans le log (« - » sinon, jamais une taille ou une latence supposée). Le tableau n'affichait que
  30 lignes sans ascenseur pour un tampon de 200 : tout le tampon défile désormais, et l'affichage suit les
  nouvelles lignes tant qu'on est en bas.
- **Logs : adresses IPv6 compressées non reconnues** (`2a02:8440:a501:9913::be86:aa87`, `::1`) : seule la
  forme complète à 8 groupes l'était ; colonne IP vide et statistiques par IP fausses (viewer Simple, Voir
  et traiter IP) pour tout client IPv6.
- **Comportement par défaut — une IP bannie reçoit enfin 451** (page « Votre IP a été bannie ») sur toutes
  ses requêtes pendant la durée du ban, comme promis par la documentation et le message d'activation de
  l'auto-ban ; elle recevait jusqu'ici un 403 (« accès interdit à la ressource »), impossible à distinguer d'un
  simple refus. Vaut pour tout ban de la blocklist native : auto-ban du WAF, ban manuel, RIPOSTE, pont
  omega-jail. La requête d'attaque elle-même reste refusée en 403.
- **Sauvegarde de configuration incomplète** : les **listes de mots-clés du WAF** et les **scripts Magnet**
  (`waf.lua`, script personnel, `magnet-rules.d/`, blocklist Magnet) n'étaient jamais sauvegardés ; ils font
  désormais partie de « Règles WAF ». Un certificat configuré à un autre endroit du projet que
  `secure/certificates` est maintenant inclus.
- **Base Active Defense mal copiée par la sauvegarde** : la base, en mode WAL, était archivée sans son fichier
  `-wal` — les écritures récentes pouvaient manquer, et une copie faite pendant une écriture pouvait être
  incohérente. Les bases (Active Defense, RIPOSTE) sont désormais copiées par l'API de sauvegarde de SQLite :
  copie complète et cohérente, **serveur en marche**.
- **Restauration d'une base sous un serveur actif** : une sauvegarde qui contient une base n'est plus jamais
  restaurée pendant que le serveur tourne (les workers et RIPOSTE écrivent dans ces bases). L'interface propose
  **« Arrêter, restaurer, redémarrer »** (gestionnaire de service ; `--stop-and-restart` en ligne de commande) ;
  le service est toujours redémarré, même si la restauration échoue. Les bases remplacées et leurs fichiers
  `-wal`/`-shm` sont d'abord mis de côté : un ancien `-wal` laissé en place aurait été rejoué sur la base
  restaurée. Une sauvegarde sans base se restaure comme avant.
- **Sondes WordPress et injections de commandes non classées** (Active Defense, changement de comportement).
  Les attaques détectées par les packs livrés `wordpress-probes` et `body-cmdi` recevaient la classe
  « unknown » : un profil de leurre visant « scan » ne voyait pas les sondes WordPress, et l'injection de
  commandes n'avait aucune classe. Désormais `wordpress-probes` → **scan** (reconnaissance, comme
  `sensitive-paths`) et `body-cmdi` → nouvelle classe **command_injection**, utilisable dans les profils de
  leurre. Un test vérifie la classe de chaque pack livré : un pack ajouté sans classe est détecté.
- **Incidents fermés mêlés aux ouverts, et jamais supprimés** (Active Defense). L'écran Incidents affichait
  tout sans distinction : un incident fermé restait dans la liste. Il propose désormais un filtre
  **Ouverts** (par défaut) / **Fermés** / **Tous** avec le nombre de chaque sorte ; un incident fermé reste
  consultable et exportable dans « Fermés ». La base ne supprimait jamais aucun incident : les incidents
  **fermés depuis plus de 90 jours** sont maintenant supprimés avec leur historique (événements,
  observations, indicateurs), et jamais plus de 10 000 incidents fermés ne sont gardés — par l'entretien
  automatique du serveur et par `active-defense purge`. Un incident **ouvert** n'est jamais supprimé ; les
  exports IoC et rapports déjà écrits restent sur le disque.
- **Un incident dont la menace était effacée restait « ouvert »** (Active Defense). L'état de menace expirait
  bien tout seul, mais l'incident ne se fermait qu'avec `active-defense purge` lancé à la main. Désormais
  **l'entretien automatique du serveur ferme lui-même** ces incidents (source revenue au niveau normal et
  calme depuis la durée de vie de l'état, 2 h par défaut — même règle qu'avant) : ils quittent la vue
  « Ouverts » sans intervention. Nouveau bouton **« Purger maintenant »** dans l'écran Incidents pour le faire
  tout de suite (avec confirmation et bilan). L'export automatique à la fermeture (`ioc.auto_export_on_close`,
  **activé par défaut** : JSON, CSV, Markdown dans `var/lib/active-defense/exports/`) s'applique à toutes ces
  fermetures, y compris par `active-defense purge` en ligne de commande, qui ne l'appliquait pas.
- **Lignes de journal perdues après « Voir et traiter IP »**. Retirer une IP d'un journal le réécrit
  sous un nouveau fichier ; le serveur, qui gardait l'ancien fichier ouvert, continuait d'écrire dans ce
  fichier supprimé : les lignes suivantes (accès, alertes WAF…) n'apparaissaient plus nulle part —
  ni dans lnav, ni pour fail2ban / omega-jail — jusqu'au redémarrage du serveur. Désormais le serveur
  vérifie au plus une fois par seconde que le journal est toujours le même fichier, et le rouvre sinon
  (même chose si le fichier a été supprimé). La rotation (troncature sur place) n'est pas concernée.
  Coût mesuré : +0,56 µs par ligne écrite.

- **Bans perdus quand plusieurs processus écrivent la blocklist au même moment** (sécurité). La
  blocklist (`var/lib/waf/blocklist.json`) s'écrivait en « lire → modifier → remplacer » sans verrou
  entre processus : en mode boost, deux workers qui bannissaient au même moment (ou un worker et la
  CLI / la TUI) partaient de la même liste, et le second effaçait le ban du premier. Mesuré : 4
  processus posant 160 bans en même temps n'en gardaient que 56 à 61. Désormais chaque écriture se
  fait sous un verrou exclusif (`blocklist.json.lock`, créé en mode 664 pour rester utilisable par le
  service dédié et par l'utilisateur) et relit toujours le fichier sous ce verrou : 160 sur 160.
  Attente du verrou bornée à 1 s ; au-delà, ou si le verrou ne peut pas être ouvert, l'écriture se fait
  comme avant (sans verrou) avec un avertissement sur stderr (journalctl) — jamais un ban refusé ni un
  serveur figé. Un fichier devenu illisible mais inchangé reste réécrit depuis le cache (correctif du
  2026-10-18 conservé).
- **Un ban automatique pouvait écraser un ban plus fort** (changement de comportement). Le
  bannissement automatique du WAF (récidive) remplaçait toute entrée du même réseau : un ban manuel ou
  permanent posé entre-temps par un autre processus, ou un ban automatique plus long, pouvait être
  remplacé par un ban plus court. Désormais un ban automatique **ne remplace jamais** une entrée encore
  en vigueur qui est manuelle, permanente ou plus longue. Un ajout manuel (CLI, TUI) remplace toujours,
  comme avant : c'est une décision explicite.
- Nouvelle opération interne de retrait conditionnel (ne retire une entrée que si elle remplit une
  condition donnée), pour qu'un mécanisme automatique ne puisse jamais retirer un ban qu'il n'a pas posé.
  Aucun changement pour les retraits manuels.

## version 2.0.1 : Publié

### Ajouté

- **Version 2.0.1** : archive `omega-serv-2.0.1.tar.gz` dans `html/download/`, empreinte ajoutée en
  tête de `html/download/sha.txt`. Splash « V2.01 ».

### Corrigé

- **Pages d'erreur personnalisées sans mise en forme sous la CSP** (sécurité, affichage). Les pages
  du dossier `error_pages.custom_dir` (`webroot/.errors/` par défaut) gardent souvent leur CSS dans
  un bloc `<style>` de la page : la politique par défaut (`style-src 'self'`) le bloquait, et la page
  s'affichait brute. Même défaut pour la page d'erreur générique intégrée (codes sans page dédiée).
  Désormais, pour une réponse d'erreur seulement, l'empreinte SHA-256 de chaque bloc `<style>` de la
  page est ajoutée à `style-src` (`style-src 'self' 'sha256-…'`). **Jamais `'unsafe-inline'`** : seul
  le CSS exact du fichier est autorisé, un style injecté ou modifié reste bloqué ; les autres pages
  du site gardent leur politique inchangée. Rien à configurer. Politique laissée telle quelle si
  `style-src` vaut `'none'` ou contient déjà `'unsafe-inline'`. Vérifié en production.

- **Blocklist : le serveur ralentissait à mesure que la liste se remplissait** (sécurité,
  robustesse sous attaque). Chaque requête réanalysait toutes les entrées de la blocklist
  (réseau et date d'expiration), entrées expirées comprises : ~16 µs par entrée et par requête.
  Avec 100 entrées (le plafond des bannissements automatiques), le débit tombait de ~1 000 à
  ~330 requêtes par seconde pour **tout** le trafic — au moment même où une attaque remplit la
  liste. Les entrées sont désormais analysées une seule fois, quand la liste change ; une IP
  seule (tous les bannissements automatiques) est trouvée directement. Mesuré : 100 entrées →
  944 à 988 requêtes par seconde, le même niveau qu'avec une liste vide. **Aucun changement de
  comportement** : la même entrée bloque la même IP, dans le même ordre, avec les mêmes
  expirations (vérifié sur 3 000 listes aléatoires contre l'ancienne recherche).

### Modifié

- **Gestion des logs : sélection à la souris** (Voir les logs, Voir et traiter IP, Favoris). Le
  tableau de la Bibliothèque n'affichait pas les numéros qu'on demandait de saisir : il fallait
  compter les lignes à la main. Une colonne « # » les affiche désormais (aussi dans l'écran
  Bibliothèque). Un clic sur un log suffit : champ vide, c'est la ligne surlignée qui est ouverte,
  comme dans omega-fire. Double-clic ou Entrée sur une ligne ajoute ou retire son numéro dans le
  champ, pour combiner plusieurs logs (lnav, favori). Un champ rempli reste prioritaire.
- Fichiers statiques : le fichier demandé n'est plus examiné qu'une fois (un seul appel système
  au lieu de quatre pour son type, sa taille et sa date), de même que ses variantes `.br` / `.gz`.
  Environ 20 µs de moins par requête (~2 %). Aucun changement de comportement.

Un seul texte affiché ajouté (aide de sélection des logs), traduit dans les 16 langues.

## version 2.0.0 : Publié



### Ajouté



- **Version 2.0.0** : archive nommée `omega-serv-2.0.0.tar.gz`, construite dans `html/download/`
  (dossier publié du site, remplace `dist/`) ; son empreinte est ajoutée à `html/download/sha.txt`
  (une section par version, la plus récente en tête, vérifiable avec
  `sha256sum -c --ignore-missing sha.txt`). Splash « V2.00 ». Les sources de traduction
  (`.po`/`.pot`) ne sont plus livrées, seuls les catalogues compilés `.mo` le sont (archive ~3,9 Mo).
- README : disponible en 17 langues (barre de langues), section « Langues de l'interface » et
  téléchargement avec vérification d'empreinte ; les README traduits sont rangés dans
  `docs/translation/<code>/`.
  

  
- **Active Defense : export STIX 2.1 et MISP** des indicateurs d'un incident (étude
  `OMEGA-SERV_ETUDE_ACTIVE_DEFENSE_STIX_MISP_CHARGE.md`) : bundle STIX 2.1 (`<incident>.stix.json` :
  producteur, un indicateur par adresse IP, rapport d'incident) et événement MISP (`<incident>.misp.json`,
  à importer par l'interface de MISP, distribution « votre organisation »). Marquage TLP réglable
  (`ioc.tlp`, AMBER par défaut, jamais WHITE d'office), identifiants stables (réexporter ne crée pas
  de doublons), fichiers locaux seulement, jamais envoyés, avec `.sha256`. Formats `stix` et `misp`
  dans `ioc.formats`, `incidents export-ioc --format stix,misp` et l'écran Incidents. Vérifié avec la
  bibliothèque officielle OASIS `stix2` (analyse stricte) et son validateur de motifs.
- **Guide : fiche « Active Defense en production »** (limites mesurées, base bornée, réglages
  conseillés) et 3 entrées de FAQ (limites, purge ou sauvegarde pendant une attaque, partage avec MISP
  ou OpenCTI), dans le guide du site et la FAQ intégrée (17 langues).  

- **Reverse proxy complet** (`options.reverse_proxy`, plan `OMEGA-SERV_PLAN-DETAILLE_REVERSE_PROXY.md`,
  phases 5 à 8, livrées les 14-15/10) : la 1.0.0 n'avait qu'un relais simple (round-robin, TLS
  amont, WebSocket). Ajoutés : répartition `weighted_round_robin`, `weighted_least_connections`,
  `ip_hash`, `least_connections`, `least_response_time`, `real_load` (charge réelle native ou sonde
  tierce) ; affinité de session (cookie opaque) et routage sur en-tête ; santé passive et active
  (états DOWN automatique, DRAINING/MAINTENANCE manuels), nouvel essai sur un autre backend pour les
  méthodes idempotentes ; plafond de connexions par backend (503) ; cache des réponses sur disque
  (variantes `Vary`, verrou anti-ruée, en-tête `X-Omega-Cache`, écran de supervision et de purge) ;
  protection anti-boucle (`X-Omega-Proxy-Hops`, 5 sauts au plus) ; API d'administration locale
  (`/.omega-serv-admin/`) et écran « État en direct des backends ».
- **Gestion des logs refondue sur les conventions d'omega-log** (15/10) : Bibliothèque (journaux
  d'omega-serv et journaux personnels) avec favoris ; trois lecteurs (simple, classique, lnav fusionné) ;
  Voir et traiter une IP ; sources distantes par SSH (copie à la demande via `scp`, jamais de mot de
  passe stocké) ; rotation, sauvegarde, automatisation, restauration, purge et export des archives.
- **Magnet : import d'un WAF externe** (10/10) : un script Lighttpd `mod_magnet` existant est exécuté
  tel quel (pont `lighty.*`, extra optionnel `pip install -e ".[magnet]"`), en renfort du WAF natif
  (le plus restrictif des deux l'emporte, jamais l'inverse) ; chemins personnels du script dissociés
  par la configuration ; « Vérifier la compatibilité » avant activation ; écran Active Sécurité → Magnet.
- **Listes de chemins sensibles** (`options.waf.rules.keyword_lists`, `match: "path",` , plan  : `OMEGA-SERV_PLAN-DETAILLE_SENSITIVE_PATHS.md`),
  une ligne = un chemin, mêmes frontières que la règle « chemin précis »
  (`/admin` ne touche jamais `/administrator`), dossiers `/x/`, extensions `/*.ext`,
  exceptions prioritaires `!/x`, recherche partout (`anchor: "any_segment"`) ou au
  début du chemin (`anchor: "root"`). Une liste invalide est refusée avec ses
  numéros de ligne (démarrage, rechargement, `config check`).
- **Deux listes de référence livrées** dans le paquet :
  `sensitive-paths-hostile` (298 chemins sans usage légitime) et
  `sensitive-paths-probe` (132 chemins de sondage). Elles ne sont **jamais chargées
  par défaut** ; elles sont copiées dans `secure/waf/rules/keywords/` au premier
  chargement, et la copie locale n'est jamais écrasée par une mise à jour.
- **Mode Observation** (`observe_only`) : une liste journalise ses détections sans
  compter dans le score de blocage ni dans la récidive.
- **Récidive propre à chaque liste** (`escalation_threshold`,
  `escalation_window_seconds`, `auto_block_duration_seconds`) : compteur par
  (IP, liste), durée de ban propre à la liste ; une requête qui dépasse plusieurs
  seuils produit une seule entrée de blocklist, avec la durée la plus longue.
- **Réseaux jamais bannis automatiquement** (`options.waf.reputation.never_auto_block`,
  par défaut : hôte local, Tailscale `100.64.0.0/10` et `fd7a:115c:a1e0::/48`, réseaux
  locaux IPv4/IPv6) : seul le trafic externe peut être banni ; la requête elle-même
  reste refusée et journalisée. L'exemption du loopback n'est appliquée que si
  `trusted_proxy` est actif.
- **Garde-fous** : chemins vitaux qu'aucune liste ne peut bloquer (`/`, `robots.txt`,
  `sitemap.xml`, `/.well-known/acme-challenge/…`) ; `config check` refuse une liste
  bloquante qui toucherait une route réellement servie (alias, redirections,
  réécritures, reverse proxy, upload, FastCGI, zones Auth, fichier du webroot).
- **TUI — assistant WAF Custom** : types « CHARGER une liste de chemins / de mots-clés
  (fichier) », avec préréglages des références, gravité, récidive, nom affiché.
  Le chargement est une action explicite ; il active la réputation et l'auto-ban
  s'ils étaient éteints, avec un message.
- **TUI — écran WAF Custom** : règles et listes dans un seul tableau (colonne Type),
  Modifier, Éditer la liste, Activer/Désactiver, Retirer (le fichier est conservé).
- **TUI — éditeur de liste intégré**, utilisable à la souris uniquement, **sans aucun
  raccourci clavier** : diagnostics en direct, Tester un chemin, Vérifier contre mes
  logs, Nouveautés de la référence (marqueurs `#retire:`), Corriger les droits,
  bouton Aide. La palette de commandes (`Ctrl+P`) y est neutralisée ; `Ctrl+Q`
  demande confirmation s'il reste des modifications non enregistrées.
- Écriture sûre des fichiers édités depuis la TUI (mode et groupe conservés quel que
  soit l'umask, liens symboliques refusés, modification extérieure détectée) et
  vérification que le **compte du service** peut lire le fichier.
- Script magnet : la liste effective des réseaux jamais bannis est injectée en table
  globale `omega_never_auto_block` (à côté d'`omega_magnet_paths`) ; omega-waf.lua la lit
  et n'auto-bannit plus ces adresses, comme le WAF natif.
- `omega-serv waf never-auto-block` : affiche, un par ligne, les réseaux réellement
  exemptés d'auto-ban pour la configuration (garde-fou du proxy de confiance compris) ;
  lu par omega-jail à l'installation (`ignoreip` des jails), jamais une copie de la liste.
- `build-release.sh` régénère les références depuis le fichier maître
  (`SENSITIVE_PATHS_MASTER`, défaut `~/DEV/JAIL/sensitive-path.txt`) et refuse de
  livrer une référence invalide.
- Guide d'aide : fiches de l'éditeur et de « Modifier une liste », fiches de l'écran
  Custom et de l'assistant réécrites, six nouvelles entrées de FAQ.

- **Choix de la langue de l'interface** (`OMEGA-SERV_PLAN-DETAILLE_I18N.md`, lot 2 — socle,
  aucune traduction livrée pour l'instant) : Options → **« Langue / Language »**. Libellé
  jamais traduit et langues écrites dans leur propre langue, Français toujours en tête.
  Changer de langue redémarre **l'interface** (jamais le service), avec un écran de
  confirmation dans la nouvelle langue. Retour au français : ce même réglage, ou
  `OMEGA_SERV_LANG=fr serv` une fois, ou retirer la clé `language` de `var/settings.json`.
  Langue indisponible ou catalogue illisible : démarrage en français avec un message.
  Le processus serveur (`omega-serv serve`) n'active jamais la traduction : ses messages
  dans `journalctl` restent en français.
- **Accents dans toute l'interface** (`OMEGA-SERV_PLAN-DETAILLE_I18N.md`, lot 3) : écrans, aide,
  CLI, notifications et messages affichés écrits désormais avec leurs accents (« Sécurité »,
  « Réappliquer », « Gravité », « Élevé »…). Les journaux du serveur (journalctl), la
  configuration, les commandes et toutes les valeurs techniques sont inchangés. Les en-têtes
  des listes de référence livrées suivent.
- **Interface prête à être traduite** (`OMEGA-SERV_PLAN-DETAILLE_I18N.md`, lot 4) : tous les
  textes affichés passent par le catalogue de traduction (écrans, aide, CLI, notifications,
  exports HTML). Pages servies aux visiteurs (erreurs 401/403/404/451, listing de répertoire)
  dans la langue des pages - réglage **séparé** de la langue de l'interface (écran Pages
  d'erreur, français par défaut ; changer sa propre interface ne change jamais ce que voient
  les visiteurs), attribut `lang` compris ; une page d'erreur personnalisée peut
  exister par langue (`404-en.html`, sinon `404.html`). Écran **État & Ressources** :
  alignement calculé selon la langue (plus de colonnes tapées à la main). Champs oui/non :
  `yes`/`no` et `oui`/`non` acceptés partout, quelle que soit la langue. En français,
  l'affichage et les pages servies sont inchangés.
- **Interface en anglais** (`OMEGA-SERV_PLAN-DETAILLE_I18N.md`, lot 5, validé le 2026-10-21) : Options →
  « Langue / Language » → English. Écrans, CLI, notifications, guide d'aide complet et FAQ,
  exports HTML et pages servies aux visiteurs. Saisie oui/non : `yes`/`no` et `oui`/`non`
  acceptés. Les journaux du serveur (journalctl) restent en français.
- **Interface en espagnol** (`OMEGA-SERV_PLAN-DETAILLE_I18N.md`, lot 6, validé le 2026-10-22) : même
  périmètre que l'anglais (écrans, CLI, guide et FAQ, exports, pages visiteurs). Saisie
  oui/non : « sí » ou « si » acceptés, accents ignorés.
- Anglais et espagnol validés : plus de mention « en test » dans le sélecteur.
- **Interface en russe** (`OMEGA-SERV_PLAN-DETAILLE_I18N.md`, lot 7, validé le 2026-10-22) : même périmètre
  que l'anglais et l'espagnol. Saisie oui/non : « да »/« нет » acceptés en plus des autres.
- **Interface en chinois simplifié** (`OMEGA-SERV_PLAN-DETAILLE_I18N.md`, lot 8, validé le 2026-10-22) : même
  périmètre. Saisie oui/non : « 是 »/« 否 » acceptés en plus des autres. Les noms de modules
  (Active Defense, Deception, Custom, Magnet, WAF) restent en lettres latines dans toutes les langues.
- lnav (suivi des logs fusionnés) : en-tête et barre de raccourcis mesurés en colonnes de
  terminal (caractères chinois sur 2 colonnes) - plus de débordement de ligne.
- **Interface en hindi** (`OMEGA-SERV_ETUDE_I18N_HINDI_ARABE.md`, lot 10, validé le 2026-10-22) : même
  périmètre, termes techniques gardés en anglais. Saisie oui/non : « हाँ »/« हां »/« नहीं » acceptés.
- Largeur d'affichage des voyelles devanagari alignée sur celle du terminal (glibc/VTE) : les
  cadres et colonnes restent droits en hindi.
- **Interface en arabe** (`OMEGA-SERV_ETUDE_I18N_HINDI_ARABE.md`, lot 11, validé le 2026-10-23) : complète dans
  la CLI, le guide HTML et les pages visiteurs, qui s'affichent de droite à gauche (`dir="rtl"`).
  Dans l'interface terminal, omega-serv met lui-même le texte arabe dans l'ordre de lecture et
  demande au terminal de ne plus rien déplacer (mode bidi explicite, `CSI 8 l`, rétabli à la
  sortie) : boutons, cadres et fonds restent en place dans Terminator/VTE, et l'ordre devient
  aussi correct dans les terminaux sans gestion bidi. Saisie oui/non : « نعم »/« لا » acceptés.
- Console texte (TTY Linux) : le chinois, l'hindi et l'arabe n'y sont pas affichables - l'interface
  passe en anglais pour la session, avec un message ; le réglage de langue est conservé.
- **Interface en portugais du Brésil** (`OMEGA-SERV_PLAN-DETAILLE_I18N.md`, liste définitive à
  17 langues, validé le 2026-10-23) : même périmètre que les autres langues. Saisie oui/non : « sim »/« não ».
- **Interface en italien** (liste définitive à 17 langues, validé le 2026-10-23) : même périmètre. Saisie
  oui/non : « sì »/« si »/« no ».
- **Interface en allemand** (liste définitive à 17 langues, validé le 2026-10-23) : même périmètre. Saisie
  oui/non : « ja »/« nein ».
- **Interface en néerlandais** (liste définitive à 17 langues, validé le 2026-10-23) : même périmètre, vouvoiement
  « u ». Saisie oui/non : « ja »/« nee ».
- **Interface en polonais** (liste définitive à 17 langues, validé le 2026-10-23) : même périmètre. Saisie
  oui/non : « tak »/« nie ».
- **Interface en vietnamien** (liste définitive à 17 langues, validé le 2026-10-23) : même périmètre. Saisie
  oui/non : « có »/« không » (aussi sans accents : « co »/« khong »). En console texte (TTY
  Linux), interface en anglais pour la session, comme le chinois, le hindi et l'arabe : aucune
  police console n'affiche à la fois les lettres vietnamiennes et les cadres.
- **Interface en thaï** (liste définitive à 17 langues, validé le 2026-10-23) : même périmètre. Saisie oui/non :
  « ใช่ »/« ไม่ » (aussi sans signes de ton). Colonnes alignées calculées sur la largeur affichée (voyelles
  et tons thaïs sans largeur propre). En console texte (TTY Linux), interface en anglais pour la session.
- **Interface en indonésien** (liste définitive à 17 langues, validé le 2026-10-23) : même périmètre. Saisie
  oui/non : « ya »/« tidak ». Lisible aussi en console texte (alphabet latin sans accents).
- **Interface en japonais** (liste définitive à 17 langues, validé le 2026-10-23) : même périmètre. Saisie oui/non :
  « はい »/« いいえ ». Colonnes alignées calculées sur la largeur affichée (caractères en double
  largeur). En console texte (TTY Linux), interface en anglais pour la session.
- **Interface en coréen** (liste définitive à 17 langues, validé le 2026-10-24) : même périmètre. Saisie oui/non :
  « 예 »/« 아니요 ». Colonnes alignées calculées sur la largeur affichée (hangul en double largeur).
  En console texte (TTY Linux), interface en anglais pour la session.
- **Langue des exports** (Options -> Réglages, défaut « Comme l'interface ») : langue des 3 exports
  HTML (registre des capacités, archives de logs, guide d'aide) et du rapport d'incident Markdown,
  indépendante de celle de l'interface (un export se diffuse). Dans une autre langue, l'export est
  produit par un processus séparé lancé dans cette langue (quelques secondes, l'interface reste
  utilisable, l'utilisateur est prévenu). Échec : l'export HTML n'est pas écrit et la raison est
  affichée ; le rapport d'incident est quand même écrit, dans la langue de l'interface, avec un
  avertissement. Exports JSON/CSV inchangés.
- Liste définitive des langues de l'interface (17) et ordre du sélecteur : français, anglais,
  espagnol, portugais (Brésil), italien, allemand, néerlandais, polonais, russe, chinois,
  vietnamien, thaï, indonésien, japonais, coréen, hindi, arabe.
- Descriptions des profils livrés et des règles WAF livrées traduites à l'affichage (écran
  Profils, assistant, `profile show`, sélecteur de pack) et accentuées en français.
- omega-lib : module `omega_lib.i18n` (modèles, politique de choix, état de traduction) et
  lecture des catalogues gettext (`omega_lib.infrastructure.i18n`), communs à la suite.

- **Limite de débit par dossier et par IP/réseau** (`options.waf.rate_limit.path_policies` /
  `source_policies`, étude `OMEGA-SERV_ETUDE_RATE_LIMIT_EXCLUSIONS.md`) : une règle remplace la
  limite globale pour un dossier ou une source, avec son propre compteur (`requests: 0` =
  illimité). Priorité : dossier (plus long préfixe), puis IP/réseau (plus précis), puis global.
  Utile pour une page lourde (galerie d'images) qui recevait 429 puis faisait bannir l'IP.
- **Sources sûres** pour le débit : réseaux `never_auto_block` et règles `trusted: true`. Leur
  dépassement renvoie toujours 429 mais est journalisé `"action": "throttle"` dans
  `waf-alerts.log` : la jail omega-jail ne le compte pas. Une IP publique reste journalisée
  `"action": "block"`, donc bannissable (aucun changement côté omega-jail).
- Écran **Active Sécurité → Exclusions et débit** (bloc WAF) : limite globale, règles par
  dossier, règles par IP/réseau, exclusions d'inspection ; validé avant écriture, rechargement
  à chaud, fiche d'aide F1, 17 langues.

- **Page 429 fournie** (thème jaune, d'après le modèle `errors/429.html`), comme les 401/403/404/451 :
  feuille de style externe, donc stylée aussi sous la CSP du profil durci (l'ancienne page générique
  de secours, avec son style intégré, s'affichait sans style), traduite dans les 17 langues des
  pages visiteurs. Une page 429 personnalisée (option `error_pages`) reste prioritaire.

- **Avertissement « service lancé avec une ancienne version »** : si le service actif a démarré
  avant la dernière mise à jour du code installé, l'interface le signale (notification à l'accueil,
  et avertissement ajouté au message « rechargé »). Un rechargement ne relit que la configuration :
  sans redémarrage, les réglages apparus avec la mise à jour restaient sans effet. systemd et runit
  (OpenRC n'expose pas le PID du service : pas d'avertissement).

- **Hindi dans Kitty, Ghostty et Konsole** : avertissement au démarrage. Ces terminaux composent
  eux-mêmes les lettres liées devanagari sur une largeur variable (selon le groupe de lettres et la
  police) : cadres et colonnes se décalent, sans correction possible côté omega-serv. Terminator,
  GNOME Terminal, Xfce Terminal et Alacritty restent alignés.

- **ETag, Last-Modified et réponses 304** sur les fichiers statiques : un rechargement ne
  retélécharge plus que ce qui a changé. **Requêtes partielles `Range` (206/416)** : reprise de
  téléchargement, avance dans une vidéo.
- **`Cache-Control` par défaut par extension** (option `cache`) : images et médias 1 jour, polices
  7 jours, CSS et JS 1 heure, le reste revalidé (304). Modifiable dans l'écran Cache : toute
  modification y enregistre sa propre liste, qui remplace celle-ci.
- **Fichiers texte pré-compressés** : `fichier.br` / `fichier.gz` déposés à côté de l'original
  (HTML, CSS, JS, JSON, SVG, XML, TXT…) sont envoyés avec `Content-Encoding` quand le navigateur les
  accepte (brotli préféré), `Vary: Accept-Encoding` toujours présent ; ignorés s'ils sont plus anciens
  que l'original ou s'ils pointent hors de son dossier. Aucune compression à la volée.
- **Mode « boost » : plusieurs processus serveur** (`server.workers`, écran Résistance et limites) :
  1 par défaut (fonctionnement inchangé), 0 = automatique (un par cœur physique), au plus les CPU
  disponibles de la machine (affinité et quota cgroup compris) — une valeur plus grande est refusée
  à l'écran, et ramenée aux CPU disponibles au démarrage si la configuration vient d'une machine plus
  grosse. Un processus principal ouvre le port, lance les workers, relaie rechargement et arrêt
  propre, et relance un worker qui s'arrête (arrêt complet si les arrêts se répètent). **Compteurs
  de sécurité (rate limit, récidive) partagés en mémoire entre workers** : limites exactes quel que
  soit le nombre de workers (un script magnet garde ses propres compteurs). Avec plusieurs workers,
  un seuil de récidive ne peut pas dépasser 32. Mesuré (petits fichiers, WAF et rate limit actifs,
  machine de test chargée) : environ +50 % de débit avec 2 workers, +65 % avec 3. Registre des
  capacités : nouvelle entrée « Processeur » (cœurs physiques, threads, CPU disponibles, quota,
  charge, nombre de workers conseillé).
- Scripts de mesure de performance dans `tools/bench/` (outil de développement, non livré), dont `bench_any.py` (client seul, pointable sur n'importe quel serveur) et `compare/` (campagne omega-serv 1.0/2.0 contre nginx, lighttpd et Caddy, serveur et client épinglés sur des cœurs distincts), et `active_defense_load.py` (charge et résilience d'Active Defense : attaquants simulés derrière le proxy de confiance, base verrouillée en pleine attaque) ; comparatif publié dans `docs/comparatif-serveurs-web.md`, chiffres bruts dans `docs/benchmarks/`.

### Modifié

- La langue de contrôle « Test ⟦…⟧ » n'est plus proposée dans le sélecteur (encore utilisable
  par `OMEGA_SERV_LANG=x-test` pour un futur lot de traduction).

- **`X-Forwarded-For` / `Forwarded` sont désormais lus de droite à gauche** : l'adresse
  retenue est la première qui n'appartient pas aux réseaux de confiance. Avec un seul
  proxy qui remplace l'en-tête, le résultat est identique ; un client ne peut plus
  se déclarer `127.0.0.1` en envoyant lui-même l'en-tête.
- Le compteur de récidive est **conservé au rechargement** (SIGHUP) ; seul un
  redémarrage complet le remet à zéro.
- Un rechargement qui échoue est **signalé** (« Rechargement REFUSE - les regles
  precedentes restent actives », visible dans `journalctl`) au lieu d'être perdu
  silencieusement.
- Les valeurs par défaut du code sont **inchangées** : réputation et auto-ban restent
  désactivés tant qu'aucune liste n'est chargée.
- **Emplacement par défaut des blocklists** : `var/lib/waf/blocklist.json` (au lieu de
  `secure/waf/blocklist.json`) et `var/lib/waf/magnet-blocklist.txt` (au lieu de
  `secure/waf/magnet-blocklist.txt`). Sous systemd, le service ne peut écrire que dans `var/`
  (`ReadWritePaths`) : **aucun auto-ban n'était jamais enregistré** avec l'ancien emplacement.
  Au premier démarrage, l'ancien fichier est recopié s'il existe (jamais un écrasement, l'ancien
  est conservé) ; l'ancien chemin par défaut **enregistré en toutes lettres** dans la config
  (l'écran WAF Magnet enregistre toujours ses 5 chemins) suit lui aussi le nouveau défaut ; un
  chemin réellement personnalisé n'est jamais touché. Le dossier `var/lib/waf/` est créé
  en `2770` quel que soit l'umask.
- **Mise à jour par extraction de l'archive** : `var/` et `secure/auth/` ne sont plus livrés
  dans l'archive, même vides. Extraire une mise à jour par-dessus l'installation remettait les
  droits de ces dossiers à ceux de l'archive et le service tombait en `PermissionError` jusqu'au
  bouton « Réappliquer les permissions ». `install.sh` crée les dossiers manquants et ne modifie
  jamais ceux qui existent.
- **Préfixes d'exclusion du WAF à frontière de dossier** (`exclusions.path_prefixes`,
  `do_not_inspect_body_path_prefixes`) : `/admin` couvre `/admin` et `/admin/x` mais plus
  `/administrateur`, comme les alias, redirections et le cache. Une exclusion qui comptait sur
  la simple correspondance de début de chaîne (`/img` pour `/images/`) doit être réécrite
  (`/images`).
- Écran **Proxies de confiance** : explication avant chaque champ (n'y mettre que le proxy placé
  devant omega-serv, jamais ses propres appareils : ça n'exempte pas du bannissement ; en-têtes
  possibles `X-Forwarded-For`, `Forwarded`, `X-Real-IP`, et pourquoi « aucun » passe par la
  désactivation de l'option). Un nom d'en-tête invalide est refusé à l'enregistrement.
- Écran WAF Custom : le bouton « Ajouter une règle » devient « Ajouter ».
- Invite des écrans de démarrage : « Cliquez ou appuyez sur une touche pour continuer... » (le clic
  fonctionnait déjà, seule la touche était annoncée).
- `build-release.sh` n'inclut plus les listes locales `secure/waf/rules/keywords/*.txt`
  dans l'archive ; `migrate-state.sh` les recopie depuis l'ancienne installation.

### Corrigé
- **Active Defense : adresse IPv6 tronquée dans les exports d'IoC** (JSON, CSV, rapport) : l'identifiant
  d'une source (`adresse:empreinte`) était coupé au premier « : », une IPv6 `2001:db8::7` sortait
  « 2001 ». Coupé désormais au dernier.
- **Active Defense : base verrouillée = serveur figé et requêtes perdues** (mesuré le 2026-10-26,
  `tools/bench/active_defense_load.py`) : quand un autre programme tenait la base (purge,
  sauvegarde), chaque requête suspecte attendait jusqu'à 5 s sur la boucle principale, ce qui
  figeait tout le serveur, puis échouait sur « database is locked » sans être rattrapée :
  connexion coupée sans réponse (1 500 à 1 600 en 10 s), rien dans `error.log`. Les écritures
  d'Active Defense passent désormais par un fil d'écriture unique, hors de la boucle, avec une
  file bornée et un nouvel essai automatique ; une erreur d'Active Defense ne fait plus jamais
  échouer une requête (elle suit la décision du WAF) et laisse une ligne dans `error.log` au
  début et à la fin de l'incident. Mesuré après correctif : 0 connexion coupée, pire attente d'un
  visiteur légitime 189 ms au lieu de 5 s. Écritures groupées par lots (fenêtre de 50 ms, une
  validation par lot) et aucun travail d'incident sous le seuil : le fil d'écriture consomme 70 %
  de processeur en moins sous une attaque à adresses changeantes (2,7 → 0,8 s pour 20 s).
- **Active Defense : un attaquant persistant ralentissait de plus en plus le serveur** : chaque
  observation rechargeait tout l'historique de son incident ouvert (coût croissant avec la durée
  de l'attaque). Seul l'identifiant de l'incident est désormais lu, et rien sous le seuil d'incident.
- **Active Defense : la base pouvait remplir le disque** (trou de sécurité) : journal d'audit jamais
  purgé, sources suivies et historique des incidents sans limite. Désormais : audit purgé au-delà
  de 30 jours et plafonné à 200 000 lignes ; au plus 200 000 sources suivies (les sources « normal »
  les plus anciennes supprimées d'abord) ; par incident, les 100 premiers et les 1 000 derniers
  éléments de l'historique sont gardés, ceux du milieu sont comptés (« N omis » dans le rapport, la
  CLI et l'écran Incidents, compteurs dans l'export JSON).
- **Active Defense : la base grossissait sans limite sous une attaque** à adresses changeantes
  (la purge n'était que manuelle) : les états de menace expirés sont maintenant purgés
  automatiquement, toutes les 10 minutes au plus. La fermeture des incidents et leur export
  restent faits par `active-defense purge`, comme avant.
- **Active Defense bloquait le serveur ~3 ms par requête suspecte** (écriture SQLite synchronisée
  sur disque à chaque transaction, faite sur la boucle principale) : base en `synchronous=NORMAL`
  (réglage recommandé par SQLite en mode WAL, déjà actif) → 0,3 ms. Jamais de corruption ; une
  coupure de courant peut seulement perdre les toutes dernières écritures (état de menace, audit).
- **Coût par requête réduit** sur le chemin du statique : résolution du chemin 269 → 72 µs (la
  racine du site n'est plus revérifiée depuis `/` à chaque requête ; seuls les dossiers demandés le
  sont, avec la même protection contre les liens symboliques), ligne du journal d'accès 52 → 23 µs.
- **Gros fichiers chargés en entier en mémoire** : chaque téléchargement d'un fichier statique le
  lisait complètement, de façon bloquante (mesuré : 3 téléchargements de 300 Mo → serveur à 1,8 Go,
  figé jusqu'à 2 s). Au-delà de 256 Ko, le fichier part désormais par blocs depuis le disque
  (`sendfile` en HTTP, blocs lus hors de la boucle en HTTPS) : mémoire stable (39 Mo mesurés),
  aucune attente pour les autres visiteurs, débit gros fichiers +30 %.
- **Messages du service en retard dans journalctl** : sous systemd (sortie non interactive),
  « à l'écoute », « Rechargement demandé/terminé », etc. restaient en mémoire tampon et n'étaient
  écrits qu'à l'arrêt, tous datés de l'heure d'arrêt. Ils sont maintenant écrits ligne par ligne.
- **Auto-ban d'un visiteur légitime par le rate limit du script magnet** (cas réel : une page
  d'images chargée en 4G) : chaque 429 renvoyé par magnet devenait une détection
  `magnet-external` comptée par la réputation, et 3 suffisaient au ban. Un 429/413/414 de magnet
  est désormais un simple rejet de volume, comme le rate limit natif : jamais une détection, journalisé
  `block` pour une IP publique (omega-jail inchangé) et `throttle` pour une source sûre. Sur une
  requête couverte par une règle de débit native (dossier ou IP/réseau), le 429 de magnet est
  ignoré. Les 403/451 de magnet restent des détections.
- **Page d'erreur sans style pour une IP bloquée** : la feuille de style des pages d'erreur par
  défaut (`/.omega-serv-error-css/error-pages.css`) est servie même à une IP bloquée ou limitée ; ces
  requêtes ne sont plus journalisées comme des blocages (elles gonflaient le compteur d'omega-jail).
- **Arrêt propre sans drainage** (SIGTERM, `systemctl stop/restart`) : sous Python 3.13 et plus,
  les requêtes en cours étaient coupées net au lieu d'être terminées pendant le délai de grâce
  (`server.shutdown_grace_period_seconds`). L'arrêt attend de nouveau la fin des connexions en
  cours, puis ferme de force celles qui restent après le délai, avec un message dans le journal.
- `build-release.sh` échouait à la régénération des listes de chemins sensibles depuis la
  traduction de l'application (omega-lib absent du `PYTHONPATH` du générateur).
- Messages « Service … démarré / redémarré / rechargé » : ces trois mots restaient en français
  (sans accents) dans toutes les langues ; ils sont maintenant traduits.
- **Site entier en 502 si la blocklist devient illisible** (incident réel du 2026-10-18 sur
  craftdark : `secure/waf/blocklist.json` réécrit en `root:root 600` par le relais
  omega-jail lancé en root) : chaque requête levait `PermissionError`. Désormais la
  lecture garde la dernière liste valide (une seule ligne d'erreur dans le journal), une
  écriture sur un fichier modifié et illisible est refusée (jamais un fichier réécrit
  sans les bans existants), et un auto-ban impossible à enregistrer ne fait plus échouer
  la requête en cours.
- **Ban IPv6 trop large** : le ban automatique d'un client IPv6 créait une entrée
  `<ipv6>/32`, acceptée comme réseau, qui bloquait toute la plage /32 de son
  fournisseur d'accès. L'entrée est maintenant `/128`.
- **Listes effacées** : ajouter une règle Custom ou modifier les packs (écran
  Modules) remplaçait tout le bloc `rules` et effaçait toutes les `keyword_lists`.
- Rechargement silencieux : une liste illisible au SIGHUP levait une erreur jamais
  rapportée, et la TUI annonçait « rechargé ».
- Une écriture atomique pouvait rendre un fichier illisible par le compte du service
  (mode recalculé depuis l'umask, groupe perdu) ; l'écriture atomique existante est
  inchangée pour ses autres usages, les fichiers édités depuis la TUI utilisent la
  nouvelle écriture qui conserve les droits.
