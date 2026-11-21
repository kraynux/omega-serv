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

## version 3.0.0 : Construite le 2026-11-21

Version majeure : reverse proxy relayé par le moteur natif (plan v2, lots A à 11), tableau de bord web, mémoire
réduite, deux audits de sécurité complets (87 failles corrigées). Résumé pour l'utilisateur :
`omega-serv-3.0.0-nouveautes.txt`. Lot A (correctifs prioritaires) : chaque défaut a d'abord été prouvé par un
essai, puis corrigé, avec des tests qui échouent sur la 2.6.2.

### Ajouté (journal des bans, 2026-11-21)

- **Active Defense tient compte des bans posés ailleurs sur la machine** (plan omega-connect, phase 3 ; levée de
  la limite « Hors périmètre » du README) : `infrastructure/active_defense/known_bans_journal.py` lit le journal
  des bans de la zone omega-synchro (`bans/actifs.json` puis `bans/journal.jsonl` suivi par position, omega-lib
  0.3.0), publié par omega-fire (`omega-fire:manual`) et l'action fail2ban d'omega-jail (`fail2ban:<jail>`).
  Une observation d'une adresse bannie ailleurs reçoit `known_ban` (+25, condition du niveau « contained »).
  Relu au plus toutes les 5 s, sans redémarrage ni fil ; jails RIPOSTE ignorés (anti-boucle) ; zone absente ou
  illisible = aucune adresse connue. Le contrat `OmegaFireEventsPort`/`FirewallEvent`, jamais implémenté, est
  remplacé par `KnownBansPort.is_banned()`. La fiche déclare les contrats `omega-ban` et `omega-bans-actifs`.

### Sécurité

- **Authentification Basic : mots de passe faux limités AVANT le calcul (2026-11-20).** Une vérification scrypt
  coûte 0,3 à 0,5 s : après 10 échecs d'une même adresse, ou 30 pour un même nom d'utilisateur, en 5 minutes,
  réponse **429** immédiate (Retry-After) sans aucun calcul jusqu'à la fin de la fenêtre ; plus de 10 vérifications
  en attente : **503** immédiat au lieu d'un empilement (2 calculs simultanés au plus, hors de la boucle du
  serveur). Le cache des succès (scan n° 1) garde 5 minutes **renouvelées** à chaque requête, avec un plafond
  d'une heure, une éviction LRU (4096 entrées) et une purge à chaque modification d'utilisateur ou de zone ; il est
  consulté avant la limite : un visiteur déjà vérifié n'est jamais refusé. Compteurs par processus (mode boost :
  par processus de travail). Deux moteurs (le natif confie ces requêtes au processus Python). Les 7 valeurs sont
  réglables dans Configuration détaillée → Authentification → **Protection des mots de passe**
  (`options.auth.password_protection`, bornes vérifiées ; appliquées au rechargement).
- **Scan de sécurité n° 2 (2026-11-20), 45 failles corrigées (WAF, Active Defense, TLS, RIPOSTE, CLI/TUI,
  administration web, services).** Rapport : `CLAUDE-SECURITY-20261120-150934/` ; tests
  `tests/unit/test_security_scan2_rules.py`, `tests/integration/test_security_scan2_paths.py` et
  `native/.../test_security_scan2.cpp`.
  - **Cible de requête sans « / » initial** (`GET private/x`) : elle échappait aux zones d'authentification et aux
    règles d'accès puis était servie. Seules la forme `/…`, la forme absolue `http(s)://…` et `*` sont acceptées
    (sinon 400), dans les deux moteurs. `..;` compte comme `..` (backends Java). WAF (signatures de chemin), limites
    de débit par dossier, exclusions et règles par extension (`/x.db/`) jugés sur le chemin canonique.
  - **Compte du service → root ou opérateur** : le nom de service lu dans `var/settings.json` (modifiable par le
    service) est validé partout où root s'en sert (systemctl avec `--`, `/etc/systemd/system`, minuterie Certbot,
    `synchro groupe-service`, option `--service-name`) ; un nom douteux donne le nom par défaut ou un refus. Le
    partage de `var/` avec le groupe du service ne passe plus par `find … -exec chgrp/chmod` en root mais par un
    parcours qui ne suit jamais un lien (`infrastructure/services/secure_tree.py`) ; `var/backups` n'est plus setgid,
    sauvegardes complètes et exports créés 0700/0600 dès l'ouverture. Santé des logs « Corriger avec sudo »,
    restauration d'archive de log (dossier neuf 0700, refus si lien), purge des exports, rotation des logs et verrou
    de la liste de blocage ne suivent plus un lien posé dans `var/`. `waf test` et « Vérifier la compatibilité »
    Magnet exécutent le script avec un état privé et vide (plus le fichier Lua de `var/cache`).
  - **WAF** : expressions livrées SQLI-005, CMDI-001/002, XSS-005/007 bornées (retour arrière quadratique sur la
    boucle) ; `Content-Type` lu comme PHP (coupé à `;`, `,` ou blanc), corps non inspecté seulement pour un type
    explicitement binaire dont la signature correspond ; partie fichier multipart = paramètre `filename` exact.
    Active Defense identifie une source par son adresse IP seule (changer de User-Agent sortait de la quarantaine) :
    champ User-Agent du simulateur et option `active-defense simulate --user-agent` retirés, plus d'indicateur
    User-Agent fictif dans les exports STIX/MISP.
  - **Administration web** : sans TLS, en-tête `Host` limité aux adresses IP, `localhost` et noms de la machine
    (421 sinon : DNS rebinding) ; cookies `omega_admin*` retirés avant tout relais vers PHP ou un backend (deux
    moteurs) ; verrou des échecs par couple compte + adresse ; même temps de réponse avec un mauvais mot de passe et
    un code de secours ; le jeton du maître n'est envoyé à une instance locale sans TLS que si le port est tenu par
    root, un compte système ou le propriétaire de l'installation ; visionneuse web des journaux coupée sur `\n` seul
    et champs de journal sans contrôles C1 ni U+2028/2029 (deux moteurs).
  - **Secrets locaux** : phrases de passe des clés et de la CA passées à `openssl` par l'entrée standard (plus
    `pass:` visible dans `ps`) ; en-têtes ressemblant à un identifiant (`X-Api-Key`, `*-Token`, `Proxy-Authorization`…)
    toujours masqués dans le journal enrichi ; `omega-serv.sh` et les relances internes en `python -I`.
  - **Divers** : adresse relayée qui n'est pas une IP → adresse du pair TCP (deux moteurs) ; cellules CSV des IoC
    neutralisées ; motif de bannissement sans caractères de contrôle ; textes venus du réseau affichés sans balisage
    dans la TUI ; requêtes en pipeline du moteur natif reprises par la boucle d'événements (plus de récursion).

- **Scan de sécurité n° 1 (2026-11-20), 42 failles corrigées dans les deux moteurs.** Rapport :
  `CLAUDE-SECURITY-20261120-074442/` ; tests `tests/*/test_security_scan1_*.py` et `native/.../test_security_scan1.cpp`.
  - **Zones d'authentification, règles d'accès, listage, FastCGI et zones proxy contournables par une autre
    écriture du chemin (16 failles HIGH).** Ces décisions comparaient le chemin brut ; le fichier servi venait du
    chemin décodé. `//private/x`, `/%70rivate/x`, `/private%2fx` ou `/private\x` servaient `/private/x` sans
    identifiants. Toutes ces décisions se prennent désormais sur un chemin canonique unique (décodé comme le fichier
    servi, `\` en `/`, segments vides retirés) ; le backend d'une zone proxy reçoit toujours le chemin d'origine.
    Un chemin sans forme canonique (encodage invalide, NUL, caractère de contrôle) est refusé : 400.
  - **`..` doublement encodé (`%252e%252e`) accepté** : il sortait d'une zone `allow` et levait le refus des
    fichiers cachés (`.env`, `.git/`) dans tout le webroot. Refusé (400), comme `..` écrit tel quel.
  - **Contrebande de requêtes vers le backend du proxy** : un client qui nommait `Content-Length` dans `Connection`
    faisait retirer la longueur alors que son corps partait. La longueur envoyée au backend est maintenant toujours
    recalculée sur le corps transmis.
  - **`/.omega-serv-admin/` et `/.omega-serv-load/` ouverts à Internet derrière un proxy installé sur la même
    machine** (pair 127.0.0.1 de confiance). Un appel portant un en-tête de relais (`X-Forwarded-For`,
    `Forwarded`, `X-Real-IP`...) y est refusé (403) ; la TUI et la sonde d'une instance frontale n'en envoient pas.
  - **Déni de service** : la vérification scrypt d'un mot de passe Basic (0,3 à 0,5 s) gelait tout le serveur
    Python ; elle tourne maintenant à part (deux à la fois), et un succès est retenu 5 min (le navigateur renvoie
    ses identifiants à chaque requête). Suivi de réputation du WAF plafonné à 100 000 adresses. Script magnet Lua :
    une exécution à la fois (le verdict d'une requête pouvait se calculer sur les données d'une autre). Natif : une
    entrée de blocklist contenant `%` ne fait plus lire un tableau vide.
  - **Mineurs** : backend HTTPS d'un leurre d'Active Defense relayé en clair ; fausses lignes possibles dans
    `admin-audit.log` (`\r`, U+2028) ; en-tête client `Proxy` transmis en `HTTP_PROXY` à FastCGI (« httpoxy ») et
    noms avec `_` ignorés désormais ; cookie de session collante signé par une clé de l'instance
    (`var/lib/proxy/sticky-cookie.key`) au lieu d'un SHA-256 réversible - l'affinité repart une fois après la mise
    à jour.
- **TLS direct : les poignées de main n'étaient pas comptées dans `server.max_connections` (D30), dans les deux
  moteurs.** Une connexion TLS n'existait pour le serveur qu'une fois sa poignée de main terminée, avec un délai de
  60 s. Mesuré : avec `max_connections = 5`, 300 connexions muettes restaient ouvertes. Désormais une connexion TLS
  compte dès son acceptation, comme en clair ; au-delà de la capacité, elle est fermée aussitôt. La poignée de
  main est bornée par `server.read_timeout_seconds` au lieu de 60 s. Moteur Python : il faut Python 3.11 ou plus.
  Sous Python 3.10, qui est en fin de vie, seule la borne de durée s'applique.
- **Un client qui ne lisait pas sa réponse gardait sa place indéfiniment (D31), dans les deux moteurs.**
  `server.write_timeout_seconds` était lu, validé et réglable dans l'interface, mais aucun moteur ne l'appliquait.
  Mesuré : 3 clients qui ne lisaient pas un gros fichier occupaient `max_connections = 3`, et tout nouveau
  visiteur recevait 503. Désormais le délai s'applique **sans progrès**, comme `send_timeout` de nginx : un client
  qui ne lit plus rien pendant tout le délai est coupé, tandis qu'un client lent qui continue de lire est servi
  jusqu'au bout, quel que soit son débit.
- **Moteur natif : boucle à vide quand le système manquait de descripteurs (D32).** Une fois la limite de fichiers
  ouverts atteinte, la socket d'écoute restait signalée prête et le moteur tournait à vide. Mesuré : 5,9 s de CPU
  en 3 s, soit deux cœurs à 100 %. Désormais l'acceptation s'arrête 1 s avec un message, puis reprend, comme le fait
  asyncio dans le moteur Python.
- **Limite de débit : mémoire sans plafond face à des adresses changeantes (D33), dans les deux moteurs.** Chaque
  adresse source gardait son compteur pendant 1 h, sans limite de nombre. Une source IPv6 qui change d'adresse à
  chaque requête faisait donc grossir la mémoire. Mesuré : +5,4 Mo pour 40 000 adresses. Désormais au plus
  100 000 adresses sont suivies ; quand la table est pleine, la moins récemment vue est remplacée et repartira à
  pleine capacité. Une adresse active n'est jamais remplacée. Le mode boost avait déjà un plafond.

### Corrigé

- **Gestion des logs, viewer Simple (2026-11-20).** La colonne « Message » coupait la ligne à 80 caractères :
  l'ascenseur horizontal s'arrêtait avant la fin (User-Agent invisible) ; elle montre maintenant la ligne entière,
  colorée avec les couleurs du thème (date, adresse, méthode, code HTTP, User-Agent). La colonne « Service »
  prenait l'heure d'une date syslog pour le service (`Nov 20 10:00:00` → « 10 ») : seule l'étiquette
  `machine service[pid]:` compte désormais. La colonne « Timeout » s'appelle « Durée » (temps de traitement écrit
  en fin de ligne, absent d'un access log Combined).
- **Moteur Python : débit en recul d'environ 13 % par rapport à la 2.6.2 (petits fichiers)** (trouvé le 2026-11-19).
  Trois ajouts de sécurité des lots 1 à 4 coûtaient du calcul à chaque requête, sans changer leur règle : les
  en-têtes de sécurité sont maintenant imposés en une passe (au lieu d'un parcours de tous les en-têtes pour chacun),
  la cible est contrôlée par une recherche en C, et une requête servie aussitôt (fichier statique) ne crée plus de
  surveillance « client parti » (Python 3.12 et plus ; inchangé avant). Mesuré sur la machine A, 1 processus :
  −13 % → −7 % (petits fichiers), −6 % → −3 % (gros fichiers). Mêmes refus et mêmes en-têtes qu'avant (vérifié sur
  des centaines de milliers de cas tirés au hasard). Test ajouté.
- **Rapport complet : « Rapport impossible : string indices must be integers » dès que l'option reverse
  proxy figurait dans la configuration, même désactivée** (trouvé le 2026-11-18 en préparant les captures). La liste
  des zones était lue sur tout le réglage de l'option au lieu de sa seule liste `zones`. Test de non-régression
  ajouté.
- **Moteur natif : sondes de santé des backends et écriture différée d'Active Defense jamais lancées (D10).** Les
  processus de sécurité du moteur natif ne démarraient pas leurs tâches de fond. Mesuré : 0 sonde en mode natif,
  contre 7 en 3 s en mode Python. Un backend en panne n'était donc jamais écarté, et les écritures différées
  d'Active Defense n'étaient jamais faites. Désormais elles démarrent au lancement, et les écritures en attente sont
  vidées à l'arrêt, en 2 s au plus.
- **Activer le reverse proxy par rechargement n'avait aucun effet (D15).** Le client vers les backends n'était
  construit qu'au démarrage : après un rechargement (SIGHUP, ou *Recharger* dans l'écran Service), la zone
  renvoyait le 404 du site local. Désormais il est construit au rechargement, dans les deux moteurs. Une zone déjà
  active garde ses connexions et son état de santé.
- **Moteur natif : message de refus de rechargement trompeur.** Sans processus de sécurité lancé au démarrage, le
  rechargement qui active une option traitée par Python est refusé ; le message parlait toujours de « leurres /
  WAF / Active Defense / Auth ». Il nomme désormais l'option en cause, par exemple `options.reverse_proxy`, et dit
  pourquoi un redémarrage est nécessaire.
- Message du rechargement (moteur Python) : « WAF, Auth, routage et reverse proxy relus », au lieu de « règles WAF
  et zones Auth uniquement ».

- **Reverse proxy : lecture stricte des réponses du backend (lot 1).** La réponse à un HEAD, un 204 ou un 304 n'a
  jamais de corps, et le proxy ne l'attend plus. Avant, il attendait un corps qui ne venait pas, puis répondait 502
  et comptait le backend en échec (D1, D2). Une réponse `chunked` est décodée, validée et relayée, au lieu d'arriver
  au client avec son découpage brut ou en 502 (D3). La ligne de statut et les en-têtes du backend sont lus
  strictement : caractère de contrôle, en-tête replié, trop d'en-têtes ou statut invalide donnent 502 (D24). Les
  réponses intermédiaires 1xx sont ignorées jusqu'à la réponse finale. Un `content-length` en minuscules ne donne
  plus deux `Content-Length` au client (D27). Une connexion vérifiée en TLS et une connexion non vérifiée ne
  partagent plus le même pool (D4).
- **Reverse proxy : corps de réponse plafonné (D23).** Le proxy Python lit toute la réponse en mémoire avant de
  l'envoyer, sans limite jusqu'ici. Nouvelle option `options.reverse_proxy.max_response_body_mb` (256 par défaut) :
  au-delà, 502 et une ligne dans le journal d'erreurs.

- **Reverse proxy : tous les `Set-Cookie` du backend sont relayés (D6).** Un seul survivait. Le cookie de session
  collante ne les écrase plus : il s'ajoute à côté. Un en-tête de sécurité écrit en minuscules par le backend n'est
  plus doublé, il est remplacé par celui qu'impose le serveur (D27).
- **Reverse proxy : protocole et port transmis au backend (R1, R2).** `X-Forwarded-Proto` et `X-Forwarded-Port`
  envoyés par un client ne sont plus repris : le backend reçoit le protocole et le port réels d'omega-serv. Seul un
  relais déclaré dans `trusted_proxy` peut les fournir, par exemple Tailscale Funnel, qui termine le HTTPS devant
  omega-serv. Le backend écrit alors ses liens en `https` avec le bon port.
- Reverse proxy : `Host` vers un backend IPv6 écrit entre crochets (D28).

- **Cache du reverse proxy (D13).** Une page privée d'un visiteur authentifié n'est plus mise en cache, sauf si le
  backend la déclare `public` : avant, elle pouvait être servie à un autre visiteur. Une requête partielle (`Range`)
  ne passe plus par le cache, une réponse 206 n'y entre jamais, et `Vary: *` empêche la mise en cache. Après un
  redémarrage, la taille occupée n'est plus comptée deux fois, ce qui faisait évincer trop tôt. Une entrée
  illisible n'est plus une erreur.
- **WebSocket (D14).** La zone est choisie après les réécritures, comme pour les autres requêtes. Un refus de mise à
  niveau par le backend n'annonce plus un corps qui n'arrive jamais : le navigateur n'attend plus.

- **Reverse proxy : boucle vers soi-même mieux détectée (D17).** `config check` ne reconnaissait que
  `127.0.0.1`, `localhost` et l'adresse d'écoute. Il refuse maintenant aussi `::1`, `::`, `0.0.0.0`, tout
  127.x.x.x, les formes courtes comme `127.1` et les adresses IPv4 dans IPv6, y compris pour les backends des
  leurres d'Active Defense. Un nom d'hôte de backend mal formé est refusé.

- **WAF : plus de lien caché entre options (D34, P9).** Activer le reverse proxy, FastCGI ou l'envoi de fichiers
  faisait lire et inspecter le corps entier des requêtes sur toutes les routes, dans le moteur Python seulement.
  Désormais seules ces routes lisent le corps entier, pour le transmettre. Depuis le lot 2, le WAF n'en inspecte que
  `waf.inspect.body_max_inspect_bytes`, sur toutes les routes.
- **WAF : `exclusions.do_not_inspect_body_path_prefixes` enfin appliqué (D35).** Le réglage était proposé par
  l'interface mais lu nulle part. Le corps des requêtes vers ces chemins n'est plus inspecté, et il part toujours
  entier vers la route.
- **Moteur natif : après une relance du moteur, les sources surveillées pour leur niveau de menace le restent
  (D37).** Avant, seules les affectations de leurres étaient renvoyées au moteur.
- **Journal d'accès : mois toujours en anglais (D41)**, quelle que soit la locale du système. Les failregex
  d'omega-jail, lnav et les statistiques en dépendent. Même correction pour la lecture des dates des certificats.

### Sécurité (suite)

- **Cible de requête : caractères de contrôle et segments `.` ou `..` refusés (D26), dans les deux moteurs, sur
  toutes les routes.** Le proxy recopiait vers le backend une cible qui contenait des caractères de contrôle. Une
  cible comme `/api/../admin` restait dans la zone `/api/`, et les règles d'accès étaient évaluées sur ce chemin
  brut, alors que le backend la comprenait souvent comme `/admin` : une protection pouvait ainsi être contournée.
  Désormais, une cible qui contient un octet de contrôle, ou un segment `.` ou `..` écrit tel quel ou encodé
  (`%2e`, avec `%2f` et `%5c` comptés comme séparateurs), reçoit **400**. Les navigateurs normalisent ces chemins
  avant de les envoyer.

- **Client parti avant la réponse : journalisé en 499 (P3, D39).** Avant, l'abandon d'un client n'était pas
  journalisé, ou l'était avec le statut d'une réponse qu'il n'avait jamais reçue. Désormais, comme nginx, un client
  qui ferme sa connexion pendant le traitement, demi-fermeture comprise, donne une ligne `499` dans `access.log`, et
  la requête vers le backend est annulée. Une réponse interrompue en cours d'envoi est journalisée avec son vrai
  statut et les octets reçus par le client. Les jails d'omega-jail ne comptent que 401 et 404 : aucun effet.

- **Reverse proxy : un backend écarté sans sonde active n'était jamais réessayé (D7).** Il restait DOWN pour
  toujours, jusqu'au redémarrage. Désormais, 10 s après sa mise à l'écart, il reçoit une requête d'essai, une seule
  à la fois. Un succès le remet en service, un échec relance l'attente. C'est le comportement de nginx.
- **Reverse proxy : les sondes de santé partent avec un en-tête `Host` (D8).** Un backend à hôtes virtuels pouvait
  les refuser et passer DOWN à tort.
- **Moteur natif : connexions confiées au processus de sécurité.** Elles comptent maintenant dans
  `server.max_connections` (D9), et un arrêt du service les laisse finir dans `shutdown_grace_period_seconds` au
  lieu de les couper net (D11). C'est le cas d'une requête proxifiée ou d'un envoi de fichier en cours.

- **Moteur natif : refus décidés seul enfin tracés dans `waf-alerts` (D36, lot 1N).** Quand le contrôle de
  sécurité est indisponible en `fail-open`, le natif refuse lui-même une adresse bannie (451), mais n'écrivait
  aucune alerte : RIPOSTE et le jail `omega-serv-waf-block` ne voyaient rien. Il écrit maintenant la même ligne que
  Python, vérifiée octet pour octet sur 423 cas : mêmes clés dans le même ordre, mêmes plafonds, extrait du corps
  avec les mots de passe masqués. Les 503 dus à une panne du serveur (`fail-closed`, requête trop grande pour le
  canal, route Python injoignable) restent dans `error.log` seulement : ce ne sont pas des actes du visiteur, et
  une alerte ferait bannir des visiteurs innocents.
- **Moteur natif : la limite de débit n'était plus appliquée pendant une panne du contrôle en `fail-open` (lot
  1N).** Une source qui dépassait la limite était servie normalement. Désormais le natif répond lui-même, comme le
  WAF : statut de la règle (429 par défaut), `Retry-After`, connexion fermée, et une alerte `rate_limit`, notée
  `throttle` pour une source sûre afin que fail2ban ne la compte jamais. Le débit est maintenant compté même quand
  le processus de sécurité est absent.
- **Moteur natif : client parti pendant l'attente du verdict (P3, lot 1N).** Comme dans le moteur Python depuis le
  lot 1, et comme nginx : un client qui ferme sa connexion, demi-fermeture comprise, ou qui la coupe, pendant le
  contrôle de sécurité donne une ligne `499` et rien n'est envoyé. Le départ n'est constaté qu'aux vérifications
  faites toutes les 250 ms, donc un verdict rapide part toujours, même à un client à demi fermé. Une réponse
  interrompue en cours d'envoi, y compris par `write_timeout_seconds`, est maintenant journalisée avec son vrai
  statut et les octets du corps reçus par le client ; avant, elle n'avait aucune ligne.
- **Moteur natif : liste de blocage lue sans verrou global (D33, seconde moitié, lot 1N).** Chaque requête
  inspectée prenait deux verrous communs à tous les fils, pendant le `stat()` du fichier et le parcours de toutes les
  entrées. Mesuré : 3,2 µs par requête avec 10 bannis et 9 µs avec 1000, et un débit total qui baissait quand on
  ajoutait des fils (215 000 vérifications par seconde à 4 fils contre 311 000 à 1). Désormais les adresses exactes
  sont indexées et la liste est partagée en lecture seule. De plus, au lieu d'un `stat()` du fichier à chaque
  requête, le natif est prévenu de ses changements par `inotify` (demande de l'auteur) : il demande seulement au
  noyau si un changement attend. Résultat : environ 1,05 µs par requête quel que soit le nombre de bannis, et
  2 millions de vérifications par seconde à 4 fils. La fraîcheur est la même qu'avec `stat()` : le noyau signale le
  changement avant que l'écrivain ait fini son remplacement, donc un nouveau ban s'applique dès la requête suivante.
  Chaque dossier du chemin est surveillé : le noyau ne signale pas toujours la suppression d'un dossier, et un
  dossier `var/lib/waf` supprimé puis recréé serait sinon passé inaperçu. Dans les cas où `inotify` ne peut pas
  garantir cette fraîcheur, le natif revient au `stat()` à chaque requête : lien symbolique dans le chemin, système
  de fichiers réseau, dossier absent, structure du chemin changée.
- **WAF : un gros corps de requête gelait le contrôle de sécurité (déni de service, lot 2).** Sur les routes proxy,
  FastCGI et envoi de fichiers, le WAF inspectait le corps entier. Mesuré : un seul POST binaire de 2 Mo occupait le
  processus 6 s, et un GET envoyé en même temps attendait autant. En moteur natif, les inspections et les requêtes
  proxifiées étaient bloquées pendant ce temps. Avec 10 Mio, il fallait environ 30 s. Ce défaut existait déjà en
  2.6.2, sur toutes les routes dès que le reverse proxy était actif. Désormais, le WAF n'inspecte que les
  `waf.inspect.body_max_inspect_bytes` premiers octets (64 Ko par défaut), sur toutes les routes, dans les deux
  moteurs. La route reçoit toujours le corps entier. Au plus, l'inspection coûte maintenant 17 ms pour un
  formulaire, 45 ms pour un JSON avec accents et 80 ms pour un corps binaire, quelle que soit la taille du corps.
- **Nouvelle option `waf.inspect.body_over_limit` (lot 2).** `pass`, la valeur par défaut, laisse la suite du corps
  partir sans inspection, comme les WAF du marché. `reject` refuse avec **413** tout corps plus grand que la partie
  inspectée, en mode `block` : rien de non inspecté ne passe. C'est utile pour un site qui ne reçoit jamais de gros
  envois. Le refus est expliqué dans `error.log` et n'écrit aucune alerte : une limite de taille n'est pas une
  attaque, et ne doit pas faire bannir.
- **WAF : décodage des corps non ASCII accéléré, avec un résultat identique (lot 2).** Le décodage `%XX`
  (`urllib.parse.unquote`) traitait séparément chaque morceau ASCII d'un texte non ASCII. Il est maintenant fait par
  une seule expression régulière, et une normalisation Unicode inutile est évitée. Le texte inspecté est exactement
  le même : c'est vérifié contre l'ancienne fonction sur 140 000 cas. Exemple : 1 Mo de binaire se décode en 43 ms au
  lieu de 595 ms.
- **Ligne de requête ou d'en-tête trop longue, puis fermeture (D38, lot 1N).** Le moteur Python répondait 400, le
  natif 414 ou 431. Les deux répondent maintenant 414 ou 431, le statut qu'aurait eu la même ligne terminée.

### Ajouté (lot 3)

Le lot 3 prépare le relais natif sans rien activer pour les visiteurs : jusqu'au lot 4, toute zone du reverse proxy
reste relayée par le moteur Python, exactement comme avant.

- **Option `options.reverse_proxy.engine` (P8)** : `auto` (par défaut), `native` ou `python`. `auto` relaiera par le
  moteur natif chaque zone qui le peut ; `python` confie toutes les zones au moteur Python, sans recompiler ; `native`
  exige que toutes les zones soient relayées par le natif. Tant que le relais natif n'existe pas, `native` est
  refusé par `config check`, au démarrage et au rechargement, avec un message qui le dit. Avec
  `server.engine = python`, l'option est sans effet et `config check` l'indique par un avis : ce retour en arrière
  démarre toujours (décision du 2026-11-13). Une zone avec cache restera toujours relayée par Python.
- **Budgets du relais natif (C2)**, trois nouvelles options sous `options.reverse_proxy` (décision du
  2026-11-13) : `max_pending_body_mb` (128), mémoire de tous les corps reçus en attente de leur envoi ;
  `max_concurrent_inspections` (64), contrôles de sécurité en attente ; `max_upstream_connections` (512),
  connexions vers les backends. Ces plafonds valent pour tout le serveur, tous fils confondus, et donneront 503 une
  fois atteints. Ils ne concernent que le moteur natif. `max_pending_body_mb` doit contenir au moins une requête de
  la taille maximale acceptée (`server.max_request_size`). L'écran et le guide viendront au lot 11.
- **`config check` affiche maintenant des avertissements et des avis**, sans rendre la configuration invalide :
  - moteur natif avec TLS direct et une zone du reverse proxy, FastCGI ou l'envoi de fichiers : le serveur démarre
    avec le moteur Python, comme avant, et l'avertissement donne la sortie : terminer TLS devant omega-serv
    (`tls.mode = behind_proxy`). Le même avertissement est écrit dans `error.log` au démarrage (P7). Rien ne cesse de
    démarrer après la mise à jour ;
  - backend en adresse locale au lien (169.254.0.0/16, fe80::/10) : adresse instable, et 169.254.169.254 est le
    service de métadonnées des hébergeurs ;
  - backend désigné par un nom DNS qui se résout vers ce serveur, sur son port d'écoute : boucle probable. La
    résolution est faite par `config check` seulement, en 3 s au plus, jamais au démarrage.
- **Boucle vers soi-même par une interface locale refusée (D17+).** Quand le serveur écoute sur `0.0.0.0` ou `::`,
  un backend qui vise l'adresse d'une interface de la machine, sur le port d'écoute, est ce serveur lui-même. Une
  telle configuration ne marchait pas : 502 après 5 sauts. Elle est maintenant refusée, comme `127.0.0.1`, pour les
  zones du reverse proxy et pour les leurres d'Active Defense.
- **Moteur natif avec deux processus de sécurité : `/.omega-serv-admin/` arrive toujours au processus n° 0 (P6).**
  Chaque fil du natif est servi par un processus ; la route d'administration pouvait donc atteindre l'un ou
  l'autre, chacun avec son propre état des backends. Une connexion vers cette route acceptée par un fil de l'autre
  processus est maintenant confiée au fil 0, qui la traite entièrement : contrôles, sécurité, puis route. Un seul
  processus : rien ne change. Les sondes faites par le seul n° 0 et l'état partagé viendront au lot 6.
- Moteur natif : au moins un processus de sécurité dès qu'une zone proxy existe, même sans option de sécurité (P6).
  C'était déjà le cas tant que les zones sont confiées à Python ; c'est désormais une règle écrite.
- Instantané du moteur natif : nouvelle section `proxy` (zones, backends, règles, délais, budgets, contrôle de
  sécurité demandé par zone, choix « native » ou « confiée »), lue et vérifiée par le natif, sans effet avant le
  lot 4. Nouvelle option du binaire `--dump-proxy`, pour les tests.

### Ajouté (lot 4) : premier relais natif, en aperçu

- **Relais natif des zones du reverse proxy, activé seulement par `options.reverse_proxy.engine = native`**
  (décision du 2026-11-13). `auto`, la valeur par défaut, garde toutes les zones dans le moteur Python
  jusqu'à la fin du chantier : personne n'est concerné sans l'avoir demandé. Une zone relayée par le natif ne passe
  plus par Python, sauf pour le contrôle de sécurité quand une option le demande. Périmètre de l'aperçu : un seul
  backend désigné par son adresse IP, en HTTP clair, réponse avec `Content-Length` ou sans corps. Une zone à
  plusieurs backends, avec cookie collant, règles par en-tête, plafond de requêtes ou nom DNS fait refuser
  `engine = native` (lot 6), comme le TLS vers le backend (lot 8), le TLS direct (lot 9) et le WebSocket (lot 10).
  Au lot 4, une réponse `chunked` ou délimitée par la fermeture donnait 502 ; le lot 5 les relaie (voir plus bas).
- Ce que le relais natif reproduit du proxy Python, vérifié octet pour octet par le banc différentiel :
  - requête vers le backend réécrite à partir des en-têtes analysés : en-têtes de saut et ceux nommés dans
    `Connection:` retirés, `X-Forwarded-*`, `X-Real-IP` et compteur de sauts écrits, `Host` réécrit sauf
    `preserve_host_header`, protocole et port d'un relais de confiance repris ;
  - réponse lue strictement (ligne de statut, en-têtes, 1xx ignorées, HEAD, 204 et 304 sans corps,
    `Content-Length` contradictoire refusé), `Set-Cookie` multiples gardés, en-têtes de sécurité imposés sans
    doublon, page d'erreur, `X-Omega-Cache: BYPASS` ;
  - 502 pour un backend injoignable ou une réponse invalide, 504 pour un délai dépassé après l'envoi, 502 pour un
    compteur de sauts à 5 ou plus, avant toute connexion ;
  - journal d'accès identique ; client parti pendant le relais : 499, requête vers le backend annulée.
- **Budgets du relais appliqués** : corps en attente au-delà de `max_pending_body_mb`, contrôles en attente
  au-delà de `max_concurrent_inspections`, connexions au-delà de `max_upstream_connections` donnent 503 tout de
  suite, avec une ligne dans `error.log`.
- **Contrôle de sécurité (S22)** : aucun octet n'est envoyé au backend avant le verdict requis. Une zone avec
  magnet, une zone entièrement protégée par Auth ou un filtre natif indisponible envoient chaque requête au
  contrôle ; sinon, la présélection native décide comme pour le statique. Zéro désaccord avec `check_every = 1`.
- **Corps inspecté par memfd (S23, P10 revu)** : le moteur natif transmet au contrôle de sécurité toute la part
  `waf.inspect.body_max_inspect_bytes`, même au-delà de ce qu'une trame peut porter. Avant, il en envoyait moins
  que Python au-delà d'environ 200 Ko, avec un avertissement dans `error.log` ; cet avertissement disparaît. Les
  deux moteurs inspectent maintenant la même part.
- **Une seule autorité pour la limite de débit (D12)** : quand une route est confiée à Python (zone proxy avec
  cache, FastCGI, envoi de fichiers), le moteur natif compte la requête lui-même, et Python **lui rend la
  connexion** après sa réponse (`HANDOFF_DONE`, prévu par le contrat IPC). Chaque requête repasse donc par le
  natif. Avant, Python gardait la connexion et comptait ses requêtes dans son propre magasin : une source pouvait
  faire deux fois la limite en mêlant statique et routes confiées. Effet de bord heureux : sur une connexion
  keep-alive, une requête statique qui suit une requête confiée est de nouveau servie par le natif.
- État du moteur (`engine-state.json`) : requêtes relayées par le natif et budgets en cours d'usage, remontés
  environ une fois par seconde.

### Ajouté (lot 5) : relais natif en flux, pool de connexions

Toujours en aperçu, seulement avec `options.reverse_proxy.engine = native`.

- **Réponses relayées en flux, jamais gardées entières en mémoire (C12).** Le natif envoie la réponse au client au
  fur et à mesure qu'elle arrive du backend :
  - avec `Content-Length`, la longueur annoncée est reprise telle quelle ;
  - une réponse `chunked` est vérifiée au fil de l'eau, avec les règles du proxy Python, puis redécoupée par le
    serveur ; les extensions et les trailers sont retirés (Q4) ;
  - une réponse terminée par la fermeture du backend est relayée en `chunked` à un client HTTP/1.1, qui garde sa
    connexion ; un client HTTP/1.0 reçoit une réponse terminée par la fermeture (décision du
    2026-11-13).

  Le tampon vers le client est borné par connexion : au-delà de 128 Kio en attente, la lecture du backend est
  suspendue, puis reprise sous 32 Kio. Un client lent face à un backend rapide ne fait plus grossir la mémoire.
- **Page d'erreur décidée avant l'envoi de la tête (C7)** : une réponse 4xx ou 5xx `chunked` ou terminée par la
  fermeture n'est envoyée qu'au premier octet de son corps ; un corps vide reçoit la page d'erreur, comme avec Python.
- **Délais (C11)** : le délai `read_timeout_seconds` vaut pour le premier octet puis entre deux blocs reçus ; quand le
  client lit trop lentement et que le backend est suspendu, c'est `server.write_timeout_seconds` qui s'applique.
- **Pool de connexions vers les backends (S14)**, avec les règles de la 2.6.2 : une connexion n'est gardée que si la
  réponse s'est terminée exactement, en HTTP/1.1, sans jeton `close` et sans octet en trop. 10 connexions inactives
  au plus par backend, réparties entre les fils, fermées après 60 s d'inactivité ou dès que le backend les ferme
  (décision du 2026-11-13 : constantes, pas de nouvelle option). Une connexion inactive reste comptée
  dans `max_upstream_connections` et cède sa place quand le budget est atteint. Seules GET, HEAD et OPTIONS
  empruntent une connexion du pool (D42).
- **Un seul nouvel essai (C8)**, comme le proxy Python : une connexion du pool morte avant le moindre octet de
  réponse (fermée, RST ou délai) est remplacée par une connexion neuve. Les nouveaux essais en cours sont plafonnés
  pour tout le moteur, à `max(3, max_upstream_connections / 5)`, contre la tempête d'essais (S19).
- **Fin par la fermeture au-delà de `max_response_body_mb` (S13, D23)** : la réponse, déjà commencée, est coupée
  sans bloc final, avec une ligne dans `error.log` (décision du 2026-11-13). C'est le seul cas que
  l'option borne dans le natif : une réponse avec `Content-Length` ou `chunked` passe en flux, sans limite.
- **Taille journalisée et abandon (P2, P3)** : `access.log` donne les octets du corps réellement relayés, découpage
  `chunked` retiré. Un client qui part pendant le flux donne le statut déjà envoyé et les octets acquittés, jamais
  499 ; 499 reste pour un client parti avant le moindre octet.
- État du moteur : nouveaux essais (cumul) et connexions inactives du pool. Le superviseur exige du binaire la
  capacité `proxy_stream` dès qu'une zone est relayée par le natif : un binaire du lot 4 fait replier sur Python.

### Ajouté (lot 6) : équilibrage, santé et noms DNS dans le relais natif

Toujours en aperçu, seulement avec `options.reverse_proxy.engine = native`. Une zone à plusieurs backends, avec cookie
collant, règles par en-tête, plafond de requêtes ou nom DNS ne fait plus refuser `engine = native`.

- **Les 7 stratégies de répartition**, le cookie collant, les règles par en-tête, le plafond
  `max_concurrent_requests`, la santé passive (`unhealthy_after`, `healthy_after`) et le coupe-circuit à demi ouvert
  (une requête d'essai 10 s après la panne), avec les règles exactes du proxy Python. Vérifié par 240 scénarios
  aléatoires rejoués dans le vrai `resolve_upstream` Python et dans le natif : même backend à chaque choix (plus de
  4 000 choix, les 7 stratégies, des refus 503).
- **État commun à tous les fils du natif** : connexions en cours, temps de réponse, santé et coupe-circuit. Le choix
  et la réservation se font ensemble, sous un verrou par zone : le plafond d'un backend est exact sur tous les fils,
  et une seule requête d'essai à demi ouverte part pour tout le moteur. Cet état survit aux rechargements (clé : zone
  et backend, jamais sa position).
- **Nouvel essai sur un autre backend** pour GET, HEAD et OPTIONS, comme Python, mais seulement si le backend n'a
  encore rien répondu (le natif relaie en flux).
- **Processus de sécurité n° 0 (P6)** : lui seul sonde les backends des zones natives (sondes actives et de charge) ;
  chaque résultat, chaque score de charge (`real_load`) et chaque état manuel (drainage, maintenance) posé par
  l'administration part au natif, qui l'applique à tous ses fils. En retour, le natif lui envoie l'état de ses
  backends environ une fois par seconde : l'écran Reverse proxy montre l'état réel.
- **Noms DNS (C18)** : résolus par Python à la construction de l'instantané ; chaque adresse devient un backend, avec
  son propre poids, son plafond, son cookie collant et sa santé (décision du 2026-11-13). Les adresses
  obtenues sont écrites dans `error.log`. Un nom qui ne se résout pas met son backend hors service, avec un
  avertissement dans `config check` et une ligne dans `error.log` ; au rechargement, les adresses précédentes sont
  gardées (décision du 2026-11-13). Une adresse qui désigne ce serveur lui-même est hors service
  (boucle). Les sondes actives visent le nom : leur résultat vaut pour toutes ses adresses.
- **Surveillance portée par le verdict (P5, S26)** : quand une inspection fait surveiller une source (leurre, mode
  guerre), l'entrée part avec le verdict, et le natif l'applique avant de répondre. La requête suivante de cette
  source est donc inspectée, quel que soit le fil. Avant, l'entrée partait sur un autre canal et pouvait arriver
  après la requête suivante.
- Le superviseur exige du binaire la capacité `proxy_balance` dès qu'une zone est relayée par le natif.

### Ajouté (lot 7) : rechargement et arrêt propre

- **Rechargement pendant le trafic (C13)** : une requête déjà commencée (réponse longue, envoi lent, contrôle de
  sécurité en attente) finit avec la configuration de son début ; vérifié par des tests pendant chacun de ces cas.
- **Pool rattaché à la génération** : à chaque rechargement, les connexions inactives vers un backend inchangé (même
  adresse, même port) restent ; celles des backends retirés sont fermées. La santé, la charge et les compteurs d'un
  backend inchangé sont gardés ; ceux des backends et zones retirés sont oubliés.

### Ajouté (lot 8) : TLS vers le backend dans le relais natif

- **Zones avec un backend HTTPS relayées par le natif** (`engine = native`) : poignée de main non bloquante, bornée
  par `connect_timeout_seconds` comme en Python ; pool de connexions TLS gardées et reprises.
- **Même TLS que Python** : contexte construit comme `ssl.create_default_context()` (TLS 1.2 au minimum, mêmes suites
  de chiffrement proposées, vérifié contre le moteur Python), même magasin de confiance (celui du système,
  `SSL_CERT_FILE` et `SSL_CERT_DIR` compris). SNI seulement pour un nom ; le nom ou l'adresse IP du backend est vérifié
  dans son certificat.
- **Pool séparé selon la vérification** : la clé du pool comprend l'adresse, le port, la politique de vérification et
  le nom du backend. Une connexion ouverte sans vérification ne sert jamais une zone qui l'exige.
- Le binaire annonce la capacité `proxy_tls` ; un binaire plus ancien garde ces zones en Python.

### Ajouté (lot 9) : TLS direct pour les zones relayées par le natif

- **`tls.mode = direct` avec `options.reverse_proxy.engine = native` n'est plus refusé** : le natif chiffre lui-même
  vers le client, avec le même contexte TLS que le statique, et relaie la zone. Avant, une zone ne pouvait pas être
  relayée par le natif en TLS direct, et `engine = native` était refusé au démarrage. Une zone que le natif ne relaie
  pas (cache, WebSocket jusqu'au lot 10) garde les règles d'avant : refus avec `engine = native`, démarrage en Python
  avec un avertissement pour `auto`.
- **Route d'administration en TLS direct** : avec plusieurs processus de sécurité, `/.omega-serv-admin/` arrive
  toujours au processus n° 0, seul responsable de la santé des backends (P6). La connexion TLS passe au fil 0 avec sa
  session. Avant, seule une connexion en clair était déplacée.
- Poignées de main TLS comptées dans `max_connections` dès l'acceptation : fait au lot A (D30), valable aussi pour le
  relais.
- **Écran État** : la ligne « Reverse proxy » du tableau des moteurs affiche « natif » quand toutes les zones sont
  relayées par le natif ; avant, elle affichait « confié à Python », ou « impossible (repli) » en TLS direct. Le
  détail par zone viendra au lot 11.
- Le binaire annonce la capacité `proxy_tls_direct`, exigée dès qu'une zone est relayée par le natif en TLS direct ;
  un binaire plus ancien est refusé au démarrage, et le serveur démarre avec le moteur Python.

### Ajouté (lot 10) : WebSocket dans le relais natif

- **Une zone `websocket_enabled` est relayée par le natif** : mise à niveau, puis tunnel dans les deux sens, sans
  passer la connexion à Python. Avant, la zone était confiée à Python, et `engine = native` était refusé avec elle en
  TLS direct. Les règles sont celles du proxy Python : `Connection` et `Upgrade` transmis au backend, connexion neuve,
  aucun nouvel essai, refus du backend renvoyé sans son corps, 502 sans corps si le backend est injoignable, cookie
  collant posé seulement avec le 101, backend réservé pendant tout le tunnel.
- **Nouvelle option de zone `websocket_idle_timeout_seconds`** (Q11) : 3 600 s par défaut, `0` pour aucun délai,
  dans les deux moteurs. Écran Reverse proxy et guide au lot 11 ; l'écran garde la valeur déjà réglée quand on
  modifie une zone.
- Le binaire annonce la capacité `proxy_websocket`, exigée dès qu'une zone WebSocket est relayée par le natif ; un
  binaire plus ancien est refusé au démarrage, et le serveur démarre avec le moteur Python.

### Ajouté (lot 11) : fin de l'aperçu, écrans et documentation

- **`options.reverse_proxy.engine = auto` (défaut) relaie par le natif** : avec `server.engine = native`, chaque zone
  que le natif sait relayer l'est ; seule une zone avec cache reste confiée à Python (Q6). Jusqu'au lot 10, `auto`
  gardait toutes les zones en Python et seul `engine = native` activait le relais. `python` reste le retour en
  arrière sans recompiler.
- **Écran Reverse proxy** : bouton « Réglages communs » (moteur des zones, `max_response_body_mb`,
  `max_pending_body_mb`, `max_concurrent_inspections`, `max_upstream_connections`), validé comme `config check`
  avant d'écrire ; champ de zone « Fermer un tunnel WebSocket inactif après » (`websocket_idle_timeout_seconds`).
  Retour de l'auteur (2026-11-14, « rien n'a changé ») : le bouton était sur une rangée coupée en 80×24, sous un
  long texte. Les deux rangées de boutons sont maintenant hors de la zone qui défile, toujours visibles ; une
  ligne au-dessus du tableau résume les réglages communs en vigueur ; nouvelle colonne « Moteur » par zone
  (natif, Python (cache), Python (réglage), Python (repli), Python) ; le tableau passe avant l'explication.
  Fiche « Colonne Moteur » dans l'aide F1.
- **Écran WAF - Modules** : taille du corps inspectée (`inspect.body_max_inspect_bytes`) et sort du corps au-delà
  (`inspect.body_over_limit`, `pass` ou `reject`), réglages du lot 2.
- **Écran État & Ressources** : quand certaines zones seulement sont confiées à Python, chacune est listée sous la
  ligne « Reverse proxy » (natif) ; un préfixe trop long est coupé.
- **Envoi lent accepté s'il progresse** (constat F1 de la mesure du §7, décision de l'auteur du 2026-11-14 : dans le
  code, pas une option). Le corps d'une requête devait arriver en entier dans `read_timeout_seconds` (10 s) : un
  envoi de 100 Ko à 5 Ko/s recevait 408, un fichier de 8 Mo sous 6,4 Mbit/s aussi (proxy, zones d'envoi,
  FastCGI). Désormais, dans les deux moteurs, l'échéance est min(dernier octet + délai, début du corps + délai +
  reçu / 500 o/s), comme `mod_reqtimeout` d'Apache : un envoi régulier passe, un envoi au compte-gouttes (sous
  500 o/s en moyenne) ou arrêté plus longtemps que le délai reçoit toujours 408. La tête de la requête garde son
  délai total (anti-slowloris inchangé).
- **WAF : fichiers binaires reconnus à leur contenu** (constat F2, décision de l'auteur du 2026-11-14). Le corps
  était lu comme du texte quel que soit son type : 1 Mo d'octets aléatoires envoyé en `application/octet-stream`
  était refusé à chaque fois (motifs de commande shell trouvés par hasard), et une vraie image subit le même sort.
  Nouveau réglage `waf.inspect.binary_formats` (écran WAF - Modules ; par défaut les 20 formats connus : images,
  vidéo, son, PDF, archives ; vide = tout inspecter) : un corps n'est pas lu comme du texte quand **sa signature
  binaire** (premiers octets, jamais l'extension) correspond à un format de la liste **et** que son type annoncé
  n'est pas textuel (formulaire, JSON, XML, texte : toujours inspectés, même précédés d'une fausse signature). En
  `multipart/form-data`, seules les parties fichier reconnues sont retirées ; les champs restent inspectés. Un seul
  endroit pour les deux moteurs (le natif confie déjà le corps à Python pour l'inspection).
- **Relais natif plus économe** (mesures du lot 11, accord de l'auteur du 2026-11-14 pour changer la constante du
  lot 5). Sur la machine C (proxy sur 4 cœurs, 32 clients, page de 1 Ko), le relais plafonnait à 78 600 req/s
  pour 39,7 µs de CPU par requête, dont 33,2 dans le noyau ; nginx en demandait 7,5. En cause, compté appel par
  appel :
  - **pool trop petit** : 10 connexions inactives par backend, partagées entre les fils (2 par fil sur 4), soit une
    connexion neuve vers le backend toutes les 5 requêtes. Désormais 32 par backend **et par fil**, et toutes les
    connexions inactives du moteur restent sous la moitié de `max_upstream_connections` : un fil trouve toujours
    de la place pour une connexion neuve ;
  - **connexion reprise du pool** : elle reste inscrite à epoll et la requête part aussitôt, sans attendre un tour
    de boucle (avant : retrait, inscription, puis changement de surveillance, soit 3 `epoll_ctl`) ; remise au pool
    sans `epoll_ctl` quand la surveillance est déjà la bonne ; client en attente de la réponse relayée surveillé
    une seule fois au lieu de deux ;
  - **texte des en-têtes** : les conversions latin-1 et UTF-8 passaient par les points de code, caractère par
    caractère ; un texte tout ASCII (le cas des en-têtes) est désormais rendu tel quel, avec le même résultat.

  Résultat sur la même machine : 7 `epoll_ctl` par requête deviennent 2, plus aucune connexion neuve, 13 µs de
  CPU par requête, environ 190 000 à 206 000 req/s. Le proxy Python garde ses 10 connexions par processus.
- Guide (fiches Reverse proxy et WAF - Modules, FAQ du moteur, nouvelle question sur le proxy natif, avec les
  mesures), README, comparatif (nouvelle section 5 : reverse proxy mesuré sur les trois machines, en HTTP et en
  HTTPS, face à nginx, lighttpd, Apache, Caddy et Traefik) et notes de version (`docs/omega-serv-3.0.0-nouveautes.txt`) mis à jour ; README : rechargement à
  chaud décrit partout de la même façon (D40).

### Ajouté : interface et confort 

Suivi : `~/DEV/SERV/OMEGA-SERV_PROJETS_3.0.0.md` §7 (étude, décisions, avancement).

- **Audit de sécurité : chaque fichier sensible est nommé, avec la raison et le contenu réel.** Avant, l'écran
  disait seulement « N fichier(s) sensible(s) sous webroot » : dans un dossier de plusieurs centaines de fichiers,
  il fallait deviner lesquels. La liste était calculée mais jamais affichée. Désormais, sous le constat, chaque
  fichier est donné avec :
  - la raison : nom connu (`.env`, `.htpasswd`, `wp-config.php`…) ou extension (`.key`, `.pem`, `.crt`, `.p12`) ;
  - ce qu'il contient vraiment, lu au début du fichier et non deviné d'après le nom : clé privée, certificat,
    conteneur PKCS#12, dossier, contenu présent ou fichier vide.

  Dix fichiers au plus sont listés à l'écran et dans la CLI texte, puis « et N autres ». La liste complète est
  dans `omega-serv audit security --format json` (`details.entries`). Un fichier de plus de 1 Mio n'est pas lu.
- **Changement de gravité : un fichier vide n'est plus critique.** Un fichier vide au nom sensible, comme un
  exemple posé pour afficher une icône dans le directory listing, n'expose rien. Il devient un constat
  d'information, **PERM-004**. PERM-003 reste critique pour les fichiers qui ont du contenu.
- **Correction : un dossier `.git` dans le webroot n'était pas signalé.** L'audit descendait dedans sans le
  nommer. Il est désormais signalé lui-même, puisqu'il contient tout l'historique du site.
- **Authentification : bouton « Modifier » pour les zones protégées.** Avant, une faute de frappe obligeait à
  supprimer la zone puis à tout ressaisir. Désormais :
  - le formulaire s'ouvre déjà rempli et la zone garde sa place dans la liste ;
  - un préfixe déjà pris par une autre zone est refusé (nouvelle fonction `update_zone`) ;
  - en création comme en modification, une saisie invalide est signalée dans le formulaire et ce qui a été tapé
    est gardé.
- **Configuration détaillée : « TLS » et « Cache du reverse proxy » échangent leur place.** Le cache se trouve
  maintenant juste sous « Reverse Proxy » dans la grille, au lieu d'être en diagonale.
- **Listes déroulantes : la flèche prend la couleur d'accent du thème**, dans les 10 thèmes de l'interface. Avant,
  elle était dessinée à moitié éteinte, et rien n'indiquait qu'il fallait cliquer pour ouvrir la liste tant
  qu'elle n'avait pas le focus.

- **Menu Service refait en formulaire.** Il y a cinq lignes, dans l'ordre d'usage : nom du service, installation,
  démarrage avec la machine, permissions, pilotage. Le titre et l'état actuel sont à gauche, des boutons de même
  largeur à droite, et Retour est seul en bas, hors de la zone qui défile.
  - **Seuls les boutons utiles sont actifs** : Démarrer est grisé si le service tourne, Installer si l'unité
    existe, Activer si c'est déjà fait…
  - L'état se met à jour seul toutes les 3 s et après chaque action. Le bouton « Rafraîchir » est retiré.
  - **Permissions vérifiées à l'ouverture, en lecture seule** : il faut que `var/` soit partagé avec le compte du
    service ; `var/backups`, privé, est ignoré. Il n'y a pas de bouton « Vérifier » : l'état s'affiche (correctes,
    « N à réparer », compte absent) et « Réparer les permissions » n'est actif que si quelque chose est faux.
  - À 80×24, la ligne Pilotage demande deux lignes de défilement ; elle est visible en entier dès 26 lignes.
- **Correction : le nom du service était enregistré à chaque frappe.** Une faute de frappe, avec l'unité installée
  et le serveur en marche, faisait piloter par l'écran une unité inexistante. L'ancienne continuait de tourner
  sans que le TUI puisse l'arrêter ou la désinstaller, et « Installer » créait une seconde unité pour le même
  dossier et le même port.
  - Le champ est désormais **verrouillé** : [Modifier] puis [Valider]. Rien n'est enregistré avant Valider.
  - Le format est contrôlé : 1 à 64 caractères, minuscules, chiffres, `-`, `_` et `.`, sans `.service`.
  - Si une unité de cette installation existe sous l'ancien nom, une fenêtre détaille l'**enchaînement** avant
    toute action : arrêter et désactiver l'ancienne, la désinstaller, installer la nouvelle, puis la réactiver
    au démarrage et la redémarrer si c'était le cas. Une seule authentification sudo est demandée
    (`application/services/rename_service.py`).
  - Si une étape échoue, l'enchaînement s'arrête et le message dit laquelle.
  - Un nom déjà pris par une autre installation est refusé.
  - Une unité du même nom qui pointe vers un autre dossier n'est plus prise pour la nôtre.

- **Lot V : une saisie refusée ne fait plus tout recommencer.** Sur plusieurs écrans de la Configuration
  détaillée, une valeur refusée fermait le formulaire et l'erreur ne s'affichait que sur l'écran derrière : il
  fallait rouvrir le formulaire et tout ressaisir. Désormais l'explication s'affiche **dans le formulaire**, qui
  reste ouvert avec ce qui a été tapé.
  - **Écrans concernés** : Alias, Redirections, Rewrites, Contrôle d'accès, Cache, Directory listing, Proxies de
    confiance, limites de débit du WAF, WAF - Modules (entrée de blocklist), Reverse proxy (réglages communs ; les
    paramètres d'une zone sont contrôlés avant de passer aux backends), éditeurs de backends et de règles de
    routage, Cache du reverse proxy, Instances (création), assistant CA (trois étapes), export des IOC d'un
    incident.
  - Mécanisme commun (`FormHostMixin.push_form` et `report_form_error`) : la saisie est appliquée avant que le
    formulaire se ferme.
  - **Doublons refusés** : un deuxième alias, une deuxième redirection ou un deuxième rewrite au même préfixe,
    une règle d'accès identique, une zone de cache ou de directory listing en double, un réseau de confiance
    déjà listé, une règle de débit en double, deux fois le même backend, une zone de reverse proxy au préfixe déjà
    pris. Le message donne la ligne existante. Avant, ces doublons s'enregistraient sans un mot et seule la
    première entrée servait.
  - **Réponses oui/non contrôlées**, dans les formulaires comme sur les écrans (Sécurité générique, Directory
    listing, Active Defense, Magnet, limite de débit). Avant, une faute comme « ouii » valait **non** en silence.
    Désormais la saisie est refusée, et le champ est nommé avec ce qui a été tapé.
  - Dans un éditeur de règles de routage, une cible qui n'est pas un backend de la zone est refusée tout de suite
    (avant : à la fin, formulaires déjà fermés). Un backend est contrôlé dès sa saisie (hôte, port, poids, chemins).

- **Sauvegarde : export et import.** Objectif : désinstaller, réinstaller, et retrouver le serveur à
  l'identique à partir d'un fichier. Avant, une sauvegarde restait dans `var/backups/` de l'instance : supprimer le
  dossier l'effaçait aussi, et la restauration ne voyait que ce dossier.
  - **Exporter** copie la sauvegarde choisie hors du dossier omega-serv. Le fichier est lisible par son
    propriétaire seul et il est accompagné de son empreinte `.sha256` ; rien n'est jamais écrasé.
  - **Importer une sauvegarde** vérifie l'archive avant de l'accepter : empreinte obligatoire et juste ; ni chemin
    absolu, ni `..`, ni lien, ni fichier spécial ; seulement les emplacements d'une sauvegarde omega-serv ;
    `config/omega-serve.json` présent ; taille et nombre de fichiers bornés.
  - L'archive importée rejoint la liste. La restauration reste une étape à part.
  - Ligne de commande : `config export-backup`, `config import-backup`.
- **Restauration : version et conflit de port annoncés avant.**
  - Chaque sauvegarde porte une fiche, `.omega-serv-backup.json` : version d'omega-serv, instance, adresse, port
    et nom du service. La fiche est retirée après la restauration.
  - Une version différente est signalée.
  - Si l'adresse et le port de l'archive sont déjà pris par une autre instance enregistrée, la confirmation le dit
    et propose de garder l'adresse, le port et le nom de service de l'instance. Ils sont remis juste après
    l'extraction, avant tout redémarrage. En ligne de commande, il faut `--keep-current-port`, sinon rien n'est
    restauré.
- **Sauvegarde : contenu du site en case facultative** (« peut être long »), jamais comprise dans « Tout
  sauvegarder ». La liste montre un indicateur d'attente pendant la création, l'export, l'import et la
  restauration. En ligne de commande : `--include-site-content`.
- **Correction : les profils personnalisés (`config/profiles/custom/`) sont désormais dans toute sauvegarde**
  (constat A.1 de l'étude 3.0.0).
- Écran Sauvegarde : les boutons sont regroupés par usage (Créer et Importer, puis Restaurer, Exporter et
  Supprimer pour la ligne choisie), et Retour est seul en bas, hors de la zone qui défile.

- **Profils personnalisés** (projets 3.0.0 §1, §B et §7.1) : Profils → « Créer un profil personnalisé ».
  - **Point de départ** : un serveur web minimal sans aucune protection débrayable. Ce que le cœur HTTP impose
    reste actif et n'est pas proposé : analyse stricte, confinement au webroot, rejet de la traversée,
    normalisation, HSTS jamais sans TLS.
  - **Choix uniquement par listes déroulantes** : en-têtes de sécurité, CSP (rapport seulement ou appliquée),
    fichiers cachés, Host, méthodes HTTP, WAF, authentification, directory listing, FastCGI, cache, proxy de
    confiance, contrôle d'accès, reverse proxy.
  - **Vérification en direct** des « trous » : bloquants (ex. FastCGI avec GET et HEAD seulement) ou à accepter un
    par un (ex. pas d'en-têtes de sécurité, fichiers cachés servis, PUT/DELETE sans authentification, pas de WAF).
    S'y ajoutent les contrôles de la configuration qui en résulterait. « Enregistrer » n'est actif que si tout
    est bon, et une saisie fautive ne ferme jamais l'écran.
  - **Identification obligatoire et bornée**, relue par le tableau de bord : nom de 3 à 32 caractères
    `a-z 0-9 - _` qui ne reprend jamais un nom existant, libellé de 3 à 40 caractères, description de 200 au plus.
  - **Non modifiable** : on en recrée un, en repartant des choix d'un profil existant. Suppression avec
    confirmation, pour les profils personnalisés seulement. Le nombre n'est pas limité.
  - **Application** : un profil personnalisé ne fixe que la sécurité et l'état des options. Adresse, port, TLS,
    chemins, journaux et réglages des options restent ceux de l'instance. C'est la recommandation §E.1, appliquée
    le 2026-11-15 et à confirmer par l'auteur. Le comportement des profils fournis ne change pas.
  - **Stockage** dans `config/profiles/custom/`. Ce dossier est compris dans toute sauvegarde, repris par
    `migrate-state.sh` et exclu de l'archive livrée.
  - **Écran Profils** : colonnes Nom, Type et Libellé, boutons Créer et Supprimer, Retour seul en bas.

- **Rapport complet** (projets 3.0.0 §7.7 et §7.10) : tout ce qui est configuré et actif, en une fois, sans passer
  par chaque menu. Il couvre les réglages et le système, jamais le trafic.
  - **Sommaire à l'écran** : le minimum validé par l'auteur, qu'on ne peut pas décocher :
    - identité : instance, dossier, version, profil appliqué, machine ;
    - fonctionnement : service, unité, en marche, démarrage, **uptime**, compte, processus ;
    - adresse et **mode** : site web, reverse proxy, ou les deux ;
    - **moteur utilisé**, avec la raison d'un repli et le moteur de chaque zone ;
    - **TLS** et jours avant expiration ;
    - **options** actives ou non ;
    - nombres d'alias, redirections, rewrites, zones et backends ;
    - sécurité ;
    - contrôles de la configuration ;
    - sauvegardes : nombre, dernière, place occupée ;
    - journaux.
  - **Détail en cases à cocher, dans l'export seulement** : zones, reverse proxy, règles WAF, Active Defense et
    RIPOSTE, journaux suivis, réglages de toutes les options, audit complet.
  - **Génération en arrière-plan**, avec un indicateur d'attente.
  - **Exports** : HTML dans les 5 thèmes d'export, TXT, ou JSON. Le JSON contient les données brutes et sert aussi
    au futur tableau de bord. Les exports sont produits dans la langue des exports.
  - **Aucun secret** : toute clé qui évoque un mot de passe, un jeton, une clé ou un hachage devient vrai ou faux.
- **Menu principal** : « Rapport complet » arrive sous « Sauvegarde de configuration » ; « Aide » et « Options »
  descendent d'un cran. **Le bouton « Quitter » est retiré** : Échap, `q` et Ctrl+Q demandent toujours
  confirmation, et le pied d'écran affiche « q Quitter ».
- **Retours d'étapes** (2026-11-15) :
  - **Assistant de profil personnalisé**, corrigé : l'ascenseur n'allait pas au bout du formulaire. La boîte des
    points à accepter tombait à une ligne et coupait la fin. Chaque point est maintenant un paragraphe, suivi de sa
    case « J'accepte ce point ».
  - **Sauvegarde, deux cases**, hors « Tout sauvegarder » comme le contenu du site :
    - « **Inclure les données des zones personnalisées** » (`--include-zone-data`) : cible des alias, dossiers du
      listing, scripts FastCGI ;
    - « **Inclure les rapports d'export** » (`--include-exports`) : dossier des exports des Réglages.
    
    L'écran rappelle que les réglages de toutes les zones sont déjà dans la configuration, toujours sauvegardée.
    Un dossier hors du dossier omega-serv est signalé, pas archivé, et un dossier déjà couvert par le contenu du
    site n'est archivé qu'une fois. À l'import, ces dossiers sont acceptés seulement si la configuration de
    l'archive les désigne, jamais un emplacement de l'installation (`src`, `tools`, `native`…).
  - **Correctif sauvegarde** : décocher « Contenu du site » décochait aussi « Tout sauvegarder ». Seules les cases
    qui en font partie le décochent maintenant.
  - **Barre d'actions fixe en bas** sur 18 écrans, comme RIPOSTE et Reverse proxy : la dernière rangée de
    boutons, Retour compris, reste visible quelle que soit la longueur de la liste ou du formulaire. Écrans
    concernés :
    - Alias, Rewrites, Directory listing, Cache, Contrôle d'accès, Redirections, Authentification, Pages
      d'erreur ;
    - WAF Modules, WAF Exclusions et débit, WAF Magnet ;
    - Active Defense : Réglages, Menaces, Incidents, Deception ;
    - Voir et traiter IP, Statistiques, Santé des logs, Instances, Audit.
    
    Libellés précisés, hors de leur section : « Ajouter une zone » / « Supprimer la zone » (Listing),
    « Enregistrer les exclusions » (WAF débit), « Bloquer un réseau » / « Débloquer » (WAF Modules).
  - **Grands menus** (Service, Instances, Audit, Sauvegarde, Rapport complet, Profils, Guide d'aide) : titre
    centré dans un cadre de 70 colonnes (comme Réglages) et Retour seul, centré, en bas. Le formulaire Service est
    centré sous son titre, avec une ligne d'air entre les deux.
  - **Guide d'aide** : il fallait faire défiler deux ascenseurs (panneau et tableau) pour atteindre Retour. Le
    panneau ne défile plus, le tableau prend la place restante et défile seul. FAQ et Contact et support passent
    au centre de la barre fixe, Retour seul et centré dessous. Le choix du thème d'export, qui paraissait décalé,
    est sur une ligne avec son libellé et le bouton « Exporter » juste derrière (avant : « Exporter le guide en
    HTML » en haut, loin du thème qu'il utilise).
  - **FAQ** : les 89 questions tenaient sur une seule longue page, questions et réponses de la même couleur.
    Chaque thème est maintenant repliable : fermé à l'ouverture, avec son nombre de questions entre
    parenthèses, il s'ouvre par un clic ou par Entrée. La question est en gras dans la couleur d'accent du
    thème, la réponse en texte normal, décalée dessous. Les thèmes sont triés sans tenir compte des majuscules
    ni des accents. Retour reste fixé en bas, hors défilement.
  - **Aide** : un point de vigilance de l'accueil et une entrée de FAQ (« Interface ») expliquent la barre fixe et
    les grands menus.
  - **Guide du site** (2026-11-18) : la Partie 2 (fiches d'écran et FAQ) est désormais produite depuis l'aide F1
    par `tools/docs/guide_site.py`, dans les 17 langues : elle dit toujours la même chose que F1 (102 fiches,
    96 questions). Sept questions qui n'existaient que sur le site (reverse proxy, logs) rejoignent la FAQ
    intégrée. La Partie 1 couvre la 3.0.0 : moteur natif, administration web, zones FastCGI, export et import de
    sauvegarde, échéances des certificats, nouveaux cas de dépannage.
  - **Menu Active Sécurité** : les trois colonnes suivent le même ordre, État, puis l'essai, puis les réglages,
    puis les écrans propres au bloc :
    - WAF : État, Tester, Modules, Limitations, Custom, Magnet ;
    - Active Defense : État, Simuler, Réglages, Menaces, Incidents, Deception ;
    - RIPOSTE : État, Simuler, Réglages, Politiques, Actions, Récidives.
    
    Même ordre dans la liste du Guide d'aide, et la fiche du menu l'explique.
  - **Menus Active Sécurité et Configuration détaillée** : une seule ligne entre le haut de l'écran et le titre
    (deux avant) ; plus de ligne vide au-dessus ni au-dessous des boutons dans les cadres (WAF, Active Defense,
    RIPOSTE, Sous-écrans, Options et vérification, sur le modèle d'Intervention manuelle) ; Intervention manuelle
    collée aux trois colonnes. Retour remonte, sans barre fixe : elle reste réservée aux écrans de modules. Sans
    ascenseur à partir de 38 lignes (Active Sécurité) et de 44 (Configuration détaillée).
  - **Étude** FastCGI / PHP-FPM par zone : `OMEGA-SERV_PROJETS_3.0.0.md` §8, puis codée (ci-dessous).
- **FastCGI / PHP-FPM : plusieurs zones, un interrupteur par zone** (décisions de l'auteur du 2026-11-15, projets
  §8.1) :
  - l'écran FastCGI devient une liste (Ajouter, Modifier, Désactiver / Activer, Supprimer, barre fixe). Chaque
    zone a son préfixe, sa racine de scripts (toujours hors du webroot), sa socket PHP-FPM, ses délais, ses
    extensions, ses fichiers d'index et sa liste blanche. Le préfixe le plus long l'emporte ; deux zones au même
    préfixe sont refusées ;
  - **interrupteur par zone** : une zone désactivée répond 503 (maintenance) sur tout son préfixe, sans servir un
    fichier du webroot à sa place, et les autres zones continuent. Son dossier et sa socket ne sont plus exigés
    au démarrage ; la règle « hors du webroot » s'applique toujours. L'option `fastcgi` reste l'interrupteur
    général ;
  - **compatibilité** : une configuration à un seul enregistrement (`options.fastcgi.url_prefix`...) est lue
    comme une zone ; l'écran l'écrit au nouveau format (`options.fastcgi.zones`) au premier enregistrement ;
  - suivent les zones : le moteur natif (toutes les zones confiées à Python), la vérification de la
    configuration, le recouvrement de préfixes, les routes protégées des listes WAF, le rapport complet (nombre et
    détail des zones), la sauvegarde (« données des zones » : une racine de scripts par zone, à l'export comme à
    l'import) et l'écran Capacités (une ligne par socket des zones actives) ;
  - omega-serv ne transmet jamais de valeur PHP par requête (`PHP_VALUE`), qui déborderait sur les autres zones
    d'un même pool. Des réglages PHP différents passent par un pool PHP-FPM par zone. L'aide (fiche FastCGI et
    deux entrées de FAQ) donne le minimum que le fichier de chaque pool doit contenir (`listen`, droits de la
    socket, compte) et rappelle que son édition reste de la responsabilité de l'administrateur : omega-serv ne
    l'installe, ne l'écrit ni ne la vérifie ;
  - export HTML du guide : les retours à la ligne des réponses de FAQ sont gardés.

### Ajouté : zones, FastCGI et État & Ressources (chantiers 1 à 3)

Suivi : `~/DEV/SERV/OMEGA-SERV_PROJETS_3.0.0.md` §8-§9.

- **Dossiers de zones absents** (P1). Après une restauration, ils sont listés dans la TUI et la CLI. « Vérifier la
  configuration » et `config check` avertissent (alias, listing), et une ligne est écrite dans error.log au
  démarrage. Une zone FastCGI active sans dossier restait déjà bloquante.
- **FastCGI : taille maximale de requête par zone** (`max_request_size`, en octets). Vide, c'est la valeur de l'écran
  Limites ; elle peut être plus grande ou plus petite. Le refus 413 a lieu avant PHP, dans les deux moteurs.
- **État & Ressources selon le type d'instance** :
  - le type est affiché en tête : site, application PHP, reverse proxy (zone sur `/`) ou mixte ;
  - une section BACKENDS est ajoutée dans FLUX, pour les reverse proxy et les instances mixtes. Elle donne par
    backend l'état, les requêtes, les requêtes en cours, les 502/504 et le temps moyen, dans les deux moteurs, en
    direct et sans historique ;
  - nouvelle route interne `/.omega-serv-admin/backends`.
- **Écran Instances** :
  - l'instance courante figure toujours en tête, marquée « (courante) », même hors registre ;
  - la désinstaller est refusée par le programme lui-même, plus seulement par le bouton grisé ;
  - nouvelle disposition des boutons : ligne 1 Rafraîchir, Créer, Désinstaller ; ligne 2 Piloter, Configuration
    distante, Relier au maître.
- **Activer TOTP : boutons « Copier le secret » et « Copier le lien »**, quand le QR code ne peut pas être scanné.
  La copie passe par le presse-papiers du système (wl-copy, xclip, xsel), ou par le terminal en SSH.

### Ajouté : tableau de bord web (administration à distance)

Plan : `~/DEV/SERV/OMEGA-SERV_PLAN-DETAILLE_TABLEAU_DE_BORD_WEB.md` (lots 1 à 9, §9). Modules suivants :
`~/DEV/SERV/OMEGA-SERV_ETUDE_MODULES_ADMIN_WEB.md`.

Un panneau dans le navigateur pour suivre l'instance depuis un autre appareil (téléphone, portable), et agir sur
ce qui ne touche que `var/`. Il ne modifie jamais la configuration ni les comptes, et ne redémarre jamais le serveur.

- **Principe et sécurité**
  - Option `admin_web`, désactivée par défaut. Le panneau est servi par un processus d'administration à part,
    lancé par `serve` comme RIPOSTE, sous le compte du service, dans les trois modes (Python, workers, natif).
  - Il a son propre port, **9643** par défaut, jamais le port du site. Il écoute sur 127.0.0.1 par défaut.
  - TLS est obligatoire hors de la machine (certificat du site ou certificat dédié). Les adresses hors des réseaux
    permis reçoivent 403 avant même la page de connexion (par défaut : la machine, Tailscale et le réseau local).
  - Un problème du panneau (certificat absent, port pris) n'empêche jamais le site de démarrer. La raison est
    écrite une fois dans error.log et dans `var/run/admin/etat.json`, sans relance en boucle.
  - Les pages ne contiennent aucun style ni script en ligne (CSP stricte).
- **Comptes et connexion**
  - Deux rôles : « lecture » (Tableau de bord) et « administration » (Tableau de bord et Administration).
  - Les comptes se créent seulement dans la TUI (Configuration distante → Comptes) ou par la CLI
    (`admin-web account …`). Le rôle se choisit dans un menu déroulant. Les mots de passe sont stockés hachés
    (scrypt).
  - TOTP : QR code, secret et lien otpauth, plus 10 codes de secours. Il est obligatoire hors de la machine pour
    les comptes administration.
  - Cinq échecs imposent une attente. Le mode Administration redemande la saisie après 15 minutes. Toute action est
    écrite dans `var/log/admin-audit.log`.
  - Un compte lecture qui coche « Administration » est prévenu par un message, au lieu d'arriver en silence sur le
    Tableau de bord.
- **Vues**
  - **État & Ressources** (comme dans la TUI, BACKENDS compris), **Journaux** (instantané ou direct, fichiers de
    la bibliothèque, filtre), **Sécurité** (bans, RIPOSTE, incidents) et **Journal d'audit**. Rafraîchies toutes
    les 2 s, calculées une seule fois pour tous les navigateurs ouverts, et plus du tout quand personne ne regarde.
  - **Historique** : relevé toutes les 10 s, même sans page ouverte.
    - Plages 1 h, 3 h, 12 h, 24 h, 7 jours et 30 jours, en « Moyenne » ou « Max 1 min ».
    - Graphes : processeur, mémoire, swap, charge, réseau, requêtes/s, connexions et sockets, disque (E/S et
      espace), processus, processeur et mémoire d'omega-serv, température, batterie.
    - **Téléchargements / Téléversement** des sites : octets comptés par le noyau pour chaque connexion, dans les
      deux moteurs (`var/run/traffic/`).
    - Les graphes en pourcentage sont remplis et affichent « utilisé / total · % ».
    - Fichier `var/run/admin/history.json` (environ 350 Ko une fois plein).
  - **Trafic** (façon GoAccess, sans pays) : pages, pages en 404, adresses IP (masquables), statuts, référents,
    navigateurs et robots, requêtes par heure. Périodes : aujourd'hui, 7 ou 30 jours. Lu au fil de l'eau dans la
    même passe que l'Historique (environ 86 000 lignes/s mesurées) ; `var/lib/admin/stats/`, 31 jours gardés.
  - **Certificats** : ceux de l'instance et leur échéance. Aussi dans la TUI : TLS → « Échéances des
    certificats ». Seulement les fichiers locaux, lus par openssl toutes les 12 h ; les clés ne sont jamais lues.
  - **Alertes locales** : rien n'est envoyé hors de la machine.
    - Règles : disque, mémoire, swap, processeur, température, batterie, taux de 5xx sur 5 minutes, backend hors
      service, incident Active Defense, certificat (30, 14, 7 et 1 jour avant l'échéance).
    - Chaque règle a un seuil, une durée et un retour à la normale plus bas que le seuil, pour ne pas clignoter.
    - `var/log/alertes.log`, 30 jours d'historique. Réglages et maintenance dans la TUI.
  - **Sessions** : navigateurs connectés. Un compte administration ferme n'importe quelle session, un compte
    lecture les siennes. Aussi dans la TUI : Comptes → Sessions.
  - **10 thèmes omega**, comme la TUI. Réglage « Comme la TUI » par défaut, et choix possible dans chaque
    navigateur. Les couleurs trop pâles sont ajustées pour rester lisibles.
- **Administration** (comptes administration)
  - Actions : bannir et débannir une adresse IP, fermer un incident, arrêt d'urgence et reprise de RIPOSTE, passer
    un backend en DRAINING, MAINTENANCE ou automatique, archiver un journal ou supprimer une archive, recharger la
    configuration.
  - Chaque bouton passe par une page de confirmation, et chaque action est écrite dans le journal d'audit.
- **Instance maître** : une page Instances suit d'autres omega-serv, toutes les 5 s, avec actions à distance.
  - Ajout par code d'appairage (10 minutes, usage unique) ou par sonde HTTP ; empreinte du certificat épinglée.
  - « Relier au maître » depuis l'écran Instances ; CLI `admin-web master …` et `admin-web instances …`.
- **Tout le parcours dans la TUI** (Instances → Configuration distante)
  - Cadre État « prêt / ce qui manque », avec un bouton par manque : Activer, Générer le certificat, Comptes,
    Redémarrer, Recharger.
  - Certificat dédié généré pour la machine.
  - Enregistrer refuse un port déjà pris ou une adresse absente.
  - Le pare-feu actif est signalé. Si omega-fire et l'instance sont inscrits dans la zone omega-connect, le bouton
    **Ouvrir le port** passe par omega-fire (nouvelle commande `port ouvrir`), y compris pour ufw et firewalld.

### Corrigé : tableau de bord web (essais réels du 2026-11-17)

- Vue **Sécurité** en erreur dès qu'Active Defense était actif : « SQLite objects created in a thread can only be
  used in that same thread ». La base était ouverte une seule fois, puis lue depuis un autre fil du processus
  d'administration. Elle est maintenant ouverte une fois par fil, ce qui fait quelques connexions au plus. Trouvé
  le 2026-11-18 en préparant les captures.
- Vue **Certificats** et alertes d'échéance : toujours « échéance inconnue (openssl absent) », même avec openssl
  installé, car le processus d'administration ne recevait pas l'outil openssl. Les alertes « certificat bientôt
  expiré » ne pouvaient donc jamais se déclencher. Corrigé le 2026-11-18, avec 2 tests de non-régression.
- Connexion refusée à chaque essai (403) : `Referrer-Policy: no-referrer` faisait envoyer `Origin: null` par les
  navigateurs. La politique est maintenant `same-origin`.
- Page Administration jamais affichée (`ERR_EMPTY_RESPONSE`) quand le service ne pouvait pas lire `var/backups`.
  Désormais :
  - la page s'affiche et renvoie vers « Réparer les permissions » ;
  - une erreur imprévue donne une réponse 500 et une ligne dans le journal, jamais une connexion fermée sans
    réponse.
- Les trois colonnes d'État étaient vidées par la même erreur de droits ; seule la ligne Sauvegarde le signale
  maintenant.
- Cadre SERVICE SYSTÈME : il affichait « Aucun gestionnaire de service reconnu ».
- Journaux : changer le nombre de lignes ou le filtre n'avait aucun effet sans passer par un autre journal.
- Mobile : le menu « Journal » sortait de l'écran ; le titre de connexion coupait « omega-serv » au tiret.
- Instance neuve :
  - un journal d'accès créé après le démarrage du panneau voyait ses premières visites sautées (requêtes/s,
    Trafic) ;
  - le premier trafic d'un serveur lancé juste avant le panneau était pris pour un point de départ.
- « Relier au maître » était actif sans administration web, et sans effet.

### Amélioré : mémoire

- **Mémoire de chaque processus du serveur nettement sous celle de la 2.6.2.** Mesuré sur une instance, au repos :
  moteur Python 49 → 20 Mo (2.6.2 : 32 Mo) ; moteur natif pour un site statique 53 → 10 Mo (2.6.2 : 35 Mo) ; natif
  avec WAF 67 → 28 Mo (2.6.2 : 44 Mo) ; natif avec WAF et reverse proxy 70 → 29 Mo (2.6.2 : 50 Mo) ; mode boost à
  2 workers 45 → 38 Mo. Débit inchangé.
  - deux hash scrypt « témoins » (protection contre la devinette des comptes) étaient calculés au démarrage, dans
    chaque processus. Le second restait dans la mémoire du processus (16 Mio, comportement de l'allocateur glibc).
    Ils sont maintenant calculés au premier besoin, et un grand bloc mémoire est toujours rendu au système dès
    qu'une option en manipule (authentification, reverse proxy, envoi de fichiers, FastCGI). Le démarrage gagne
    aussi environ 0,6 s par processus ;
  - le code d'une option n'est chargé que si elle est active, au démarrage ou au rechargement qui l'active, jamais
    pendant une requête : WAF, Active Defense, authentification, reverse proxy, WebSocket, FastCGI, envoi de
    fichiers, réécritures, alias, redirections, RIPOSTE ;
  - le code de l'administration web, de l'envoi de la déclaration et de la sauvegarde n'est chargé qu'au moment
    où il sert ;
  - moteur natif : une fois le natif lancé, le superviseur se relance lui-même en version réduite (même PID, pour
    systemd et l'écran Service) : ~6 Mo au lieu de ~22. La configuration y est relue sur SIGHUP par un processus
    éphémère, avec les mêmes contrôles et les mêmes messages. Le processus de sécurité (WAF, authentification,
    reverse proxy...) est lancé à part, avec la configuration acceptée, au lieu d'hériter de tout ce que le
    superviseur avait chargé. Avec plusieurs processus de sécurité (`server.workers`), le superviseur reste complet,
    comme avant ;
  - le serveur ne charge plus la détection du terminal ni la mise en forme du texte de la console ;
  - `ssl` n'est chargé que si le serveur en a besoin (TLS, backend en HTTPS) : asyncio le chargeait toujours
    (1,6 Mo) ; le reverse proxy ne prépare plus ses connexions TLS vers les backends s'ils sont tous en HTTP ;
  - moteur natif : le processus de sécurité naît du superviseur réduit et partage avec lui les pages de
    l'interpréteur ; mode boost : le code du serveur est chargé une fois avant le lancement des workers, qui le
    partagent au lieu de le charger chacun.
- **Remesuré au protocole du comparatif** (19 novembre, trois machines, nginx remesuré dans la même session) : au repos → après la charge, moteur natif 10 → 10-16 Mo, moteur Python 20-22 → 23-28 Mo, natif avec WAF 28-30 → 30-33 Mo, reverse proxy natif 27-29 → 28-33 Mo ; gros téléchargements simultanés 39 Mo (Python) et 23 à 26 Mo (natif). Un test entrelacé, code 3.0.0 avant et après ce travail, donne le même débit à 1 à 4 % près. Le comparatif des serveurs web (sections 4, 5 et 6, avec des lignes 3.0.0 à côté de 1.0, 2.0 et 2.5) et sa version graphique sont mis à jour en 17 langues ; chiffres bruts dans `docs/benchmarks/2026-11-19-*-memoire-3.0.0-brut.txt`, outil `tools/bench/memoire-3.0.0.sh`.
- **FAQ** : nouvelle question « Je décoche une option (WAF, reverse proxy...) : sa mémoire est-elle rendue ? » (non : au prochain redémarrage) ; chiffres de mémoire corrigés dans « Moteur Python ou natif », « Combien de processus choisir ? » et « Reverse proxy avec le moteur natif » (17 langues, guide du site régénéré).
- **Corrigé :** un rechargement (SIGHUP) arrivé pendant le démarrage du processus de sécurité du moteur natif
  l'arrêtait ; il est maintenant appliqué dès que ce processus est prêt.
- Tests : 11 gardes (`test_memory_serve_imports.py`) : modules lourds absents du démarrage de `serve` et du
  superviseur réduit, code d'une option absent sans elle et chargé par le rechargement qui l'active, témoins non
  calculés à l'import, commandes chargées à la demande, mémoire rendue après trois scrypt ; superviseur réduit
  (`test_native_watch.py`, `test_native_reduced_supervisor.py` avec le vrai binaire : même PID, rechargement
  accepté puis refusé, natif tué relancé, arrêt propre ; processus de sécurité né du superviseur, SIGHUP pendant
  son démarrage, relance) ; `ssl` chargé tard (`test_lazy_ssl.py` : vrai serveur et client TLS asyncio, modules
  d'asyncio dépendant de `ssl` vérifiés sur les sources). Suite complète : 4292 tests uniques.

### Changements de comportement

- **Administration web : port par défaut 9643** (8443 est souvent pris, par exemple par KULA).
- **access.log : les appels internes acceptés à `/.omega-serv-admin/`** (État & Ressources de la TUI, panneau web)
  ne sont plus écrits, dans les deux moteurs. Un appel refusé (403) reste écrit, pour omega-jail et RIPOSTE.
- **« Réparer les permissions »** (Accueil → Service) partage maintenant `var/backups/logs` avec le service (2770),
  pour que le panneau web puisse archiver et supprimer des archives. `var/backups` devient seulement traversable
  par le service (2710) ; le reste y reste privé. La vérification des permissions le contrôle aussi.

- **Moteur natif, réglage par défaut : le reverse proxy est relayé par le natif** (lot 11). Une configuration qui
  n'a pas `options.reverse_proxy.engine` passe donc du proxy Python au relais natif au premier démarrage de la
  3.0.0. En TLS direct, une zone ordinaire ne fait plus démarrer le serveur avec le moteur Python.

- **Tunnel WebSocket inactif fermé, dans les deux moteurs** (décision du 2026-11-14) : sans aucun octet, dans aucun
  sens, pendant `websocket_idle_timeout_seconds` (3 600 s par défaut), le serveur envoie une trame de fermeture 1001
  (« going away ») au client et au backend, puis ferme. Avant, un tunnel restait ouvert sans limite. Une application
  qui garde un tunnel silencieux plus d'une heure doit envoyer des pings, ou régler `0`.
- **Arrêt (SIGTERM) : les tunnels WebSocket reçoivent une trame 1001 à la fin du délai de grâce**, dans les deux
  moteurs (C14). Avant, ils étaient coupés sans trame. La trame n'est jamais insérée au milieu d'une trame : le
  serveur lit seulement l'en-tête des trames (2 à 14 octets), jamais leur contenu ; une trame coupée en plein milieu
  est fermée sans 1001.
- **`access.log`, tunnel WebSocket, dans les deux moteurs** (décision du 2026-11-14) : la taille est le nombre
  d'octets envoyés au client pendant le tunnel, comme `$body_bytes_sent` de nginx ; avant, 0. La ligne est écrite à
  la fermeture du tunnel, arrêt du serveur compris : avant, un tunnel coupé à l'arrêt n'en laissait aucune.
- **Moteur natif : une connexion gardée ouverte prend la nouvelle configuration dès sa requête suivante**
  (décision du 2026-11-13), comme le moteur Python. Avant, elle gardait celle de son ouverture jusqu'à sa
  fermeture (au plus 100 requêtes ou le délai keep-alive) : une règle de sécurité changée par rechargement pouvait
  mettre ce temps à s'appliquer à ce client (C20).
- **Arrêt (SIGTERM), dans les deux moteurs : une connexion keep-alive qui attend sa prochaine requête est fermée
  tout de suite** (décision du 2026-11-13, comme nginx). Seules les requêtes en cours (envois, relais,
  contrôles) ont le délai de grâce pour finir ; elles reçoivent `Connection: close`. Avant, un client resté connecté
  retenait l'arrêt jusqu'au bout du délai de grâce (10 s par défaut), puis `error.log` signalait un « arrêt forcé ».
  Une requête dont un seul octet est arrivé compte comme en cours : elle a le délai de grâce, même si ses en-têtes ne
  sont pas finis.
- **Backend HTTPS dont le certificat est refusé, dans les deux moteurs** (décision du 2026-11-13) : une
  ligne dans `error.log` donne la raison d'OpenSSL, au plus une par backend et par minute, par exemple
  `reverse proxy : certificat de 10.0.0.5:8443 refusé : self-signed certificate`. Un autre échec de la poignée de main
  TLS (backend qui répond en clair, version refusée) donne `reverse proxy : poignée de main TLS avec … impossible :
  <raison>`. Avant, le client recevait 502 sans aucune trace dans les journaux.
- **`verify_upstream_tls = false` avec un backend HTTPS, dans les deux moteurs** (décision du 2026-11-13) :
  avertissement dans `config check`, et ligne dans `error.log` au démarrage et à chaque rechargement. Avant, seul
  l'audit de sécurité le signalait.
- **Relais natif (aperçu, `engine = native`), écarts voulus avec le proxy Python, qui lit toute la réponse avant
  de l'envoyer :**
  - une réponse `chunked` ou terminée par la fermeture arrive au client en `chunked`, là où Python envoie
    `Content-Length` ; le corps et la taille journalisée sont les mêmes ;
  - une erreur du backend après l'envoi de la tête (connexion perdue, réponse tronquée, délai entre deux blocs)
    coupe la connexion du client, avec une ligne dans `error.log`, là où Python répond 502 : la réponse commencée
    n'est jamais remplacée (C4) ;
  - une réponse avec `Content-Length` ou `chunked` plus grande que `max_response_body_mb` passe, là où Python
    répond 502 (D23).
  - lot 6 : le nouvel essai sur un autre backend n'a lieu que si le backend n'a encore rien envoyé ; Python rejoue
    aussi après une réponse invalide ou coupée, qu'il a lue en entier avant de répondre (C8) ;
  - lot 6 : un nom DNS donne un backend par adresse, avec son cookie collant ; Python garde un seul backend par nom,
    résolu à chaque connexion. La valeur du cookie d'un backend désigné par son adresse IP reste la même.
- **Moteur natif, client qui part pendant le contrôle de sécurité.** Comme
  le moteur Python, le départ du client n'est plus surveillé pendant le contrôle de sécurité, seulement pendant la
  route (relais vers le backend). Le verdict est donc appliqué : un client à demi fermé reçoit sa réponse, et un
  client coupé (RST) donne la ligne d'un envoi échoué, avec le statut décidé. Le lot 1N journalisait 499 dans ces
  deux cas ; les deux moteurs se comportent maintenant de la même façon.
- `/../fichier` ou `/%2e%2e/fichier` sur une route statique : 400 au lieu de 403.
- Reverse proxy : **504** quand le backend ne répond pas dans `read_timeout_seconds` (502 avant) ; 502 reste pour
  un backend injoignable ou une réponse invalide. Le délai vaut désormais entre deux blocs reçus, et plus pour la
  réponse entière.
- Reverse proxy : un `Transfer-Encoding` autre que `chunked` dans une réponse du backend donne 502.
- TLS direct : une connexion au-delà de `max_connections` est fermée tout de suite, au lieu de recevoir un 503
  après la poignée de main (D30).
- Un client qui ne lit pas sa réponse est coupé après `server.write_timeout_seconds`, 15 s par défaut (D31).
- TLS direct : une poignée de main inachevée est coupée après `server.read_timeout_seconds`, 10 s par défaut, au
  lieu de 60 s (D30).
- Moteur natif, contrôle indisponible en `fail-open` : une source au-delà de sa limite de débit reçoit 429, au
  lieu d'être servie.
- Moteur natif : une requête dont le client se ferme à demi pendant le contrôle de sécurité, plus de 250 ms, est
  abandonnée (`499`), au lieu de recevoir sa réponse (règle nginx, décision du 2026-11-12).
- Moteur Python : une ligne trop longue suivie d'une fermeture donne 414 ou 431 au lieu de 400.
- WAF : sur les routes proxy, FastCGI et envoi de fichiers, seuls les 64 premiers Ko du corps sont inspectés, comme
  ailleurs (`waf.inspect.body_max_inspect_bytes`). Une attaque placée plus loin n'est plus vue, sauf avec
  `waf.inspect.body_over_limit = reject`.
- `config check` : un backend sur l'adresse d'une interface de la machine, au port d'écoute, avec une écoute sur
  `0.0.0.0` ou `::`, est refusé (lot 3).
- `config check` peut afficher des lignes « Avertissement » et « Avis » avant « configuration valide » (lot 3).

### Tests

- 17 tests ajoutés pour le lot A ; tous échouent sur la 2.6.2 (code Python et binaire natif de l'archive), sauf 2
  gardes qui vérifient qu'un client lent qui lit reste servi :
  - D10 et D15 : 5 (sondes en mode natif dès le démarrage, zone activée par rechargement dans les deux moteurs,
    refus qui nomme l'option, client gardé au second rechargement) ;
  - D30 : 4 ; D31 : 4 ; D32 : 1 ; D33 : 3, dont 1 test C++ (250 000 adresses).
- Tests C++ verts en version normale et sous ASan et UBSan.
- Lot 0, 45 tests de caractérisation du reverse proxy, lancés dans les deux moteurs (Python, et natif sous son
  superviseur) :
  - 38 tests de comportement voulu, devant un faux backend scripté : sécurité sur la route proxifiée (WAF 403 et
    alerte, 451, 429, 401, accès refusé, backend jamais atteint), 401 et 404 du backend dans `access.log`, découpage
    des réponses, en-têtes, compteur de sauts, délais, abandon du client ;
  - 1 banc différentiel (profil `proxy`, 24 cas) qui compare octet pour octet les réponses et les journaux des deux
    moteurs ;
  - 6 tests de grille des options de sécurité (aucune, WAF bloquant, `log-only`, limite de débit, Auth, WAF et Auth),
    avec contrôle croisé du filtre natif : zéro désaccord.
- 9 défauts connus du proxy Python sont marqués dans chaque moteur, en attente du lot 1 : HEAD avec longueur, 204 et
  304, réponses chunked, `Set-Cookie` multiples, `Content-Length` en double, caractère de contrôle dans la cible,
  504, abandon du client.
- Lot 1N :
  - 423 vecteurs `wafalert` : la ligne `waf-alerts` du natif comparée octet pour octet à la vraie
    `format_waf_alert_line` (horodatage, plafonds, échappement JSON, extrait du corps et masquage) ;
  - 26 vecteurs de lignes trop longues suivies d'une fermeture, autour de la limite exacte, plus 3 tests Python ;
  - intégration native : alerte du 451 identique à Python, 429 en `fail-open` (`block` et `throttle`, statut
    réglé), aucune alerte pour un 503 de panne, 499 sur demi-fermeture et sur RST pendant l'attente du verdict,
    garde du verdict rapide servi à un client à demi fermé, ligne d'accès d'un envoi coupé par
    `write_timeout_seconds` ;
  - C++ : décodage UTF-8 comme CPython, masquage du corps, horodatage, arrondi de la durée, index de la liste de
    blocage (adresses exactes, réseaux, échéances, IPv4 et IPv6). Pour `inotify` :
    - remplacement vu dès l'appel suivant ;
    - fichier abîmé ;
    - dossier supprimé puis recréé, et dossier parent renommé puis recréé ;
    - retour au `stat()` pour un lien symbolique ou un dossier absent ;
    - course à 4 fils, sans aucune réponse périmée sur plus de 200 000 vérifications. Tests C++ verts en version normale et sous ASan ;
    la liste de blocage sous ThreadSanitizer, 4 fils de lecture pendant 300 remplacements du fichier, sans
    signalement.
  - les 8 nouveaux tests échouent sur la 2.6.2, sauf les 4 gardes, qui y passent.
- Lot 2 : rapport de mesure dans `~/DEV/SERV/mesures-lot2-proxy-natif-20261112/`. 16 tests ajoutés :
  - inspection limitée sur la route proxy, avec le corps transmis entier ;
  - 4 Mo binaires sans gel, dans les deux moteurs ;
  - `reject` dans les deux moteurs : 413, backend jamais atteint, explication dans `error.log` ;
  - équivalence du décodage, validation de l'option, instantané natif.

  12 de ces tests échouent sur la 2.6.2 ; les 4 gardes y passent.
- Lot 3 : 47 tests ajoutés.
  - 34 tests unitaires : réglages et budgets, choix par zone et ses raisons, un test par cas du tableau P7 (TLS direct
    avec `auto`, `native` et `python`), FastCGI et envoi de fichiers jamais refusés (E9), retour en arrière accepté
    (E10), boucles par interface locale (zones et leurres), adresse locale au lien, nom DNS (résolu seulement par
    `config check`), instantané `proxy`, contrôle demandé par zone, processus de sécurité, sortie de `config check`.
  - 5 tests C++ (doctest) : lecture de la section `proxy`, incohérences refusées, sortie relisible,
    `security_processes`.
  - 8 tests d'intégration :
    - différentiel : ce que le natif lit, par `--dump-proxy`, est identique à ce que Python écrit, sur des zones
      variées (IPv6, nom DNS, TLS, cache, WebSocket, règles, cookie collant, accents) ;
    - 6 sections incohérentes refusées par le natif ;
    - administration toujours confiée au processus n° 0 sous rafale parallèle, avec une garde : sans second
      processus, rien n'est déplacé ;
    - refus de `engine = native` au rechargement, l'ancienne génération restant active ;
    - démarrage en TLS direct avec une zone proxy : moteur Python et avertissement dans `error.log`.
  - Tests C++ verts en version normale et sous ASan et UBSan, aiguillage de l'administration compris.
- Lot 4 :
  - 5 tests C++ du relais : requête réécrite comme `build_outgoing_headers`, compteur de sauts lu comme `int()`,
    tête de réponse stricte et cadrage du corps, réponse relayée ;
  - les tests de caractérisation du lot 0 lancés une troisième fois, sur la zone relayée par le natif : 20 verts,
    2 marqués pour le lot 5 (chunked, fermeture) ; une garde montre que la zone est bien relayée par le natif
    en `engine = native` et confiée à Python en `auto`, et que chaque budget revient à zéro ;
  - banc différentiel : relais natif identique au proxy Python, octet pour octet, sur tout le corpus hors lot 5 ;
  - grille C20 : relais natif ajouté, mêmes statuts et alertes que Python, zéro désaccord (S25) ;
  - D12 : même seau pour le statique et le proxy, dans le moteur Python, le natif avec zone confiée et le relais
    natif ; ce test échoue sans le retour de la connexion ;
  - connexion rendue au natif : requête statique suivante servie par lui, requêtes envoyées d'un bloc conservées,
    descripteurs stables après 90 retours ;
  - relais : budget des corps (503), requête bloquée jamais relayée, 502 expliqué pour une réponse chunked,
    descripteurs et budgets stables après 45 relais (erreurs et 504 compris) ;
  - memfd : attaque placée à 1,5 Mo vue par le natif comme par Python, descripteurs stables après 20 envois de
    1,2 Mo, dans le natif et le processus de sécurité ;
  - rechargement qui fait passer une zone au relais natif.
  - 52 tests d'intégration du relais passés aussi sur le binaire ASan et UBSan, sans aucun rapport.
- Lot 5 : 23 tests Python et 4 tests C++ ajoutés.
  - Analyseur de réponse du natif comparé aux vraies fonctions du proxy Python (`_read_final_head`,
    `_body_framing`, `_read_chunked`…) sur 1 529 réponses, écrites à la main ou obtenues par mutations aléatoires :
    même verdict, même statut, même découpage, même corps, mêmes octets restants. Aucun écart, ni sur 20 058 réponses
    de plus essayées une fois.
  - 4 tests C++ du décodeur `chunked` : même résultat quel que soit le découpage des octets reçus, refus stricts
    (taille, CRLF, extensions et trailers aux limites exactes), fin de flux, jeton `close`.
  - Fuzzing de l'analyseur de réponse et du décodeur (`fuzz_upstream`) : 741 114 exécutions en 5 minutes, aucun
    plantage, et le même résultat quel que soit le découpage.
  - 15 tests du relais en flux : `chunked` redécoupé sans trailers, premier bloc reçu avant la fin du backend,
    fin par la fermeture en `chunked` avec connexion gardée, client HTTP/1.0, page d'erreur d'un corps vide,
    32 Mio et 16 Mio intacts, mémoire bornée face à un client lent, coupure du backend après la tête, délai entre
    deux blocs, départ du client pendant le flux (jamais 499), dépassement de `max_response_body_mb`, délai
    d'écriture, pool (GET réutilise, POST jamais), nouvel essai sur une connexion du pool morte dans les deux
    moteurs, réservations revenues à zéro.
  - 3 tests des refus du natif sur une zone relayée, contrôle indisponible : 451 et 429 avec la même ligne
    `waf-alerts` que Python, aucune alerte pour une panne en `fail-closed`.
  - 4 tests unitaires : capacité `proxy_stream` exigée du binaire, étiquettes HEALTH identiques des deux côtés.
  - Tests du lot 0 sur la zone relayée : les 2 marques du lot 5 retirées, tous verts. Banc différentiel sur tout le
    corpus, sans exclusion : seul le découpage vers le client diffère, et il est vérifié.
  - 67 tests d'intégration du relais passés aussi sur le binaire ASan et UBSan, sans aucun rapport.
  - Test RIPOSTE « vraie attaque, vrai bannissement » rendu sûr : il ouvrait la base de RIPOSTE avant sa création
    et échouait sur une machine chargée, avec ou sans le lot 5. RIPOSTE n'est pas modifié.

- Lot 6 : 24 tests Python ajoutés.
  - Choix du backend comparé au vrai `resolve_upstream` Python : 240 scénarios aléatoires (graine fixe) rejoués par
    le binaire (`--simulate-balance`) - même backend à chaque choix, plus de 4 000 choix, les 7 stratégies, plafonds,
    cookie collant, règles, santé, coupe-circuit, scores de charge, états manuels ; plus l'essai à demi ouvert unique
    après 10 s.
  - 8 tests de bout en bout : répartition et poids identiques à Python, cookie collant et règle par en-tête dans les
    deux moteurs, 503 au plafond, plafond exact sous rafale parallèle (2 réponses sur 8), backend mort rejoué puis
    marqué hors service et relu par l'administration, drainage posé par l'administration appliqué par le natif, nom
    DNS résolu (une adresse morte écartée), nom non résolu hors service.
  - 14 tests unitaires : backends de l'instantané (clé et cookie identiques à Python pour une IP, une adresse par
    backend pour un nom, résolution gardée, boucle), avertissement de `config check`, processus n° 0 (sondes seules,
    trames vers le natif, état relu par l'administration, nom DNS agrégé), WATCH porté par le verdict, capacité.
  - Tests existants mis à jour : lacunes « équilibrage » et « nom DNS » levées (le refus de `engine = native` porte
    désormais sur le WebSocket), champs nouveaux de l'instantané dans les tests C++.
  - 80 tests d'intégration du relais passés aussi sur le binaire ASan et UBSan, sans aucun rapport.

- Lot 7 : 7 tests d'intégration ajoutés (3 dans les deux moteurs) et 2 tests de l'arrêt du moteur Python.
  - Rechargement pendant une réponse longue en flux (réponse intacte, puis requête suivante de la même connexion
    vers le nouveau backend), pendant un envoi lent (fini avec l'ancienne configuration) et pendant un contrôle de
    sécurité en attente (processus de sécurité suspendu : verdict appliqué, backend jamais atteint).
  - Connexion inactive du pool vers un backend retiré : fermée au rechargement.
  - Arrêt : une connexion keep-alive inactive ne retarde plus l'arrêt, sans « arrêt forcé » ; une réponse en cours
    finit entière, puis la connexion est fermée et plus rien n'est accepté.
  - Arrêt : une tête de requête commencée (ligne de requête lue, en-têtes pas finis, ou ligne de requête pas encore
    complète) garde le délai de grâce ; une connexion qui n'a rien reçu est fermée sans être comptée comme forcée.
    Ces tests viennent d'une régression trouvée par la suite complète du lot 7 : le moteur Python fermait aussi une
    requête dont la ligne était déjà lue.
  - Chacun de ces tests échoue sur le code d'avant le lot 7 (binaire natif recompilé depuis la sauvegarde, et moteur
    Python d'avant) : 10,2 s d'arrêt au lieu de moins de 5 s, ancien backend servi après le rechargement, connexion
    gardée au pool.

- Lot 8 : 10 tests d'intégration (dans les deux moteurs, avec une CA de test générée par `openssl`) et 8 tests
  unitaires.
  - Certificat auto-signé : servi sans vérification (et signalé au démarrage puis au rechargement), refusé avec
    vérification (502, une seule ligne pour trois requêtes, aucune requête arrivée au backend).
  - Vraie CA (`SSL_CERT_FILE`) : certificat accepté ; pas de SNI pour une adresse IP ; nom envoyé en SNI et vérifié ;
    certificat d'un autre nom refusé, avec le même texte que Python.
  - Mêmes versions et mêmes suites proposées que Python, relevées par le backend de test.
  - Pool : connexion TLS reprise trois fois (tickets TLS 1.3 compris) ; zone non vérifiée jamais servie par une
    connexion vérifiée, et l'inverse.
  - Réponse de 4 Mio lue lentement : arrivée entière (lecture TLS suspendue puis reprise).
  - Poignée de main jamais finie : 502 dans le délai de connexion, sans ligne TLS ; backend qui répond en clair : même
    ligne dans les deux moteurs.
  - Sur le code d'avant le lot 8 (binaire recompilé depuis la sauvegarde, Python d'avant) : 17 sous-tests échouent,
    tous ceux du natif et ceux des nouvelles lignes d'`error.log` ; les sous-tests Python qui passent décrivent un
    comportement qui existait déjà.

- Lot 9 : 9 tests d'intégration (7 dans les deux moteurs, client en HTTPS) et 7 tests unitaires.
  - Zone relayée en TLS direct : `X-Forwarded-Proto: https` vers le backend ; corps de 300 Kio envoyé en POST ;
    keep-alive qui mélange zone et statique sur une même connexion TLS ; trois requêtes envoyées d'un bloc, servies
    dans l'ordre.
  - Réponse de 4 Mio lue lentement : arrivée entière (écritures TLS partielles, reprise) ; réponse `chunked` en
    plusieurs fois ; client parti au milieu d'une réponse de 8 Mio : une ligne dans `access.log`, serveur intact.
  - Administration en TLS avec deux processus de sécurité : les 80 requêtes arrivent au n° 0 ; avec un seul
    processus, rien ne bouge.
  - Sur le code d'avant le lot 9 (binaire recompilé depuis la sauvegarde, Python d'avant) : 7 sous-tests natifs
    échouent (configuration refusée), et 40 requêtes d'administration sur 80 arrivent au processus n° 1.
  - Tests du lot 3 mis à jour : le refus de `engine = native` en TLS direct ne vaut plus que pour une zone confiée.

- Lot 10 : 13 tests d'intégration, tous dans les deux moteurs, avec un vrai backend WebSocket (trames masquées,
  écho), 7 tests unitaires et 7 tests C++.
  - Mise à niveau et écho dans les deux sens ; `Connection`, `Upgrade` et `Sec-WebSocket-Key` transmis au backend ;
    tête 101 identique octet pour octet dans les deux moteurs ; ligne d'`access.log` avec les octets envoyés.
  - Octets envoyés avec le 101 transmis ; refus du backend sans corps, identique dans les deux moteurs ; backend
    injoignable : 502 sans corps ; requête ordinaire d'une zone WebSocket toujours relayée.
  - Délai d'inactivité : 1001 vers le client (sans masque) et vers le backend (masquée), puis fermeture ; échanges
    réguliers : tunnel gardé ; `0` : jamais fermé ; trame coupée en plein milieu : pas de 1001 de ce côté.
  - Flux de 8 Mio lu lentement : arrivé entier ; backend qui ferme : derniers octets reçus, puis fermeture ; arrêt :
    1001 à la fin du délai de grâce, et ligne d'accès ; tunnel en TLS direct.
  - Sur le code d'avant le lot 10 (binaire recompilé depuis la sauvegarde, Python d'avant) : les 13 sous-tests natifs
    échouent (configuration refusée : zone WebSocket confiée à Python), et 6 sous-tests Python.
  - Trois anciens tests qui prenaient une zone WebSocket comme exemple de zone confiée portent maintenant sur une
    zone avec cache.

- Lot 11 : 9 tests unitaires (`auto` relaie tout sauf le cache, TLS direct garde le natif, lignes de l'écran État),
  3 tests d'écran (réglages communs validés et écrits, délai WebSocket de zone, inspection du corps du WAF), 6
  tests de la colonne « Moteur », 1 test d'écran en 80×24 (résumé, colonne, boutons visibles), 14 tests
  unitaires des constats F1 et F2 (échéance du corps, signatures, formulaires, multipart, réglage), 5 tests
  d'intégration (envoi lent régulier accepté et envoi au compte-gouttes refusé, dans chaque moteur ; image
  et faux formulaire derrière le WAF avec le moteur natif) et 2
  tests d'intégration du pool (plus de 10 connexions inactives gardées ; jamais plus de la moitié de
  `max_upstream_connections`).
  - 11 tests existants prenaient `auto` comme exemple de zone confiée : ils utilisent `engine = python` (ou une
    zone avec cache) et vérifient en plus qu'`auto` relaie. Différentiel : un trajet confié (identique octet pour
    octet) et un trajet `auto` relayé (seul le découpage vers le client diffère).
  - Test C++ de course de la liste de blocage : seuil relatif (chaque version vérifiée par un lecteur), 400/400 en
    Release et sous ASan.
  - Fuzzing, 10 minutes par cible, aucun plantage : analyseur HTTP 10,8 M d'entrées, moteur 1,1 M, canal 38,6 M,
    WAF 5,9 M, réponse du backend 0,47 M (tête 101 comprise), nouvelle cible WebSocket 18,6 M (repérage des trames
    identique quel que soit le découpage). L'instantané du fuzzer du moteur datait d'avant le lot A : corrigé.
  - ASan et UBSan, 143 tests du relais (différentiels compris), avant puis après le correctif du relais : aucun
    rapport. Tests du proxy natif après le correctif : 296 réussis, 2 sautés, 90 sous-tests.
  - Mesures (A, B, C, 6 proxys, HTTP et HTTPS) : `docs/benchmarks/2026-11-14-*-reverse-proxy-brut.txt`, premier
    passage compris ; comparatif, section 5.

- Compléments (2026-11-15) : 38 tests ajoutés.
  - Audit : 4 tests unitaires (raison et contenu réel des fichiers sensibles, fichier vide en PERM-004, dossier
    `.git` signalé, liste bornée à 10 lignes).
  - Authentification : 3 tests de `update_zone` (correction sur place à la même position, zone invalide ou
    absente sans effet, préfixe d'une autre zone refusé).
  - Service : 10 tests unitaires (format du nom, plans, renommage qui enchaîne les étapes et rétablit l'état,
    arrêt au premier échec, service arrêté seulement déplacé, unité d'une autre installation jamais renommée,
    contrôle des permissions partagées).
  - Lot V : 5 tests d'écran (erreur dans le formulaire avec saisie intacte, doublons, oui/non stricts).
  - Sauvegarde : 4 tests unitaires (export puis import sur une installation neuve puis restauration, empreinte
    exigée, archive dangereuse ou étrangère refusée, manifeste, profils et contenu du site facultatif) et 2 tests
    d'écran (Exporter / Importer, conflit de port expliqué et port actuel gardé).
  - Profils personnalisés : 6 tests unitaires (identification bornée, trou bloquant, trous à accepter un par un,
    application qui garde l'identité et les réglages, profils fournis inchangés, enregistrement sans fuite des
    métadonnées) et 2 tests d'écran (créer, accepter chaque trou, enregistrer, supprimer ; profil fourni
    impossible à supprimer).
  - Rapport complet : 1 test d'écran (sommaire, exports HTML, TXT et JSON) et 1 test de retrait des secrets.
  - Tests existants adaptés au nouveau comportement (erreur gardée dans le formulaire, menu Service, menu
    principal sans Quitter, arbre des menus du guide).
  - Suite complète : 4017 tests uniques ; les tests d'écran et différentiels en échec sous charge repassent seuls.
  - Retours de l'auteur : 1 test unitaire (données des zones et rapports d'export : cases facultatives, dossier
    hors projet signalé, pas de doublon avec le contenu du site, import accepté, archive qui vise `src/`
    refusée) ; le test d'écran « Tout sauvegarder » vérifie que les trois cases de contenu restent à part.
  - Zones FastCGI : 6 tests unitaires (ancien format lu comme une zone, liste vide, interrupteur, ancien format
    retiré à l'enregistrement, doublons nommés, sockets des zones actives), 1 test de vérification (zone désactivée :
    ni dossier ni socket exigés, mais jamais dans le webroot), 2 tests d'intégration sur un vrai serveur (chaque
    zone atteint son propre pool, le plus long préfixe l'emporte ; zone désactivée en 503 pendant que les autres
    répondent), le test de sauvegarde étendu à deux zones au nouveau format. Les 3 tests de l'écran FastCGI sont
    réécrits pour la liste (ajouter, modifier, doublon, désactiver, supprimer ; racine dans le webroot refusée ;
    ancien format repris puis réécrit).

## version 2.6.2 : Publié

**Correctif de sécurité, mise à jour conseillée** pour toute installation qui utilise le moteur natif
(`server.engine = native`) ou le reverse proxy (`options.reverse_proxy`). Sept failles trouvées par les analyses
de sécurité préparant la 3.0.0 (`~/DEV/SERV/OMEGA-SERV_ANALYSES_PROXY_NATIF.md`, plan
`OMEGA-SERV_PLAN_CORRECTIF_2.6.2.md`), chacune prouvée par un essai avant correction. Aucune option nouvelle,
aucun changement de configuration à faire.

### Sécurité

- **Moteur natif : un client pouvait occuper un cœur à 100 % pendant l'attente d'un verdict (D29).** Pendant que
  le processus de sécurité Python juge une requête, la connexion du client restait surveillée en lecture ; un
  client qui fermait son côté écriture faisait tourner le fil à vide jusqu'au verdict (jusqu'à 60 s, davantage en
  mode guerre, qui retient volontairement les verdicts des sources hostiles). Mesuré : 99 % d'un cœur par
  connexion. Désormais la connexion n'est plus surveillée en lecture pendant l'attente ; un client réellement
  parti est détecté et sa connexion libérée aussitôt. Une simple demi-fermeture est traitée comme par le moteur
  Python : la réponse est envoyée, puis la connexion se ferme.
- **Moteur natif : une requête trop grande pour être inspectée était servie sans contrôle (D20).** La requête
  soumise au processus de sécurité (tête et début du corps) voyage dans une trame dont la taille est limitée par
  le tampon du canal (208 Kio par défaut sur Linux). Au-delà, en `waf.on_internal_error = fail-open` (réglage par
  défaut), la requête était servie **sans WAF ni limite de débit** : c'était le cas dès que
  `waf.inspect.body_max_inspect_bytes` dépassait environ 170 Kio, ou avec un `server.max_header_size` très
  élevé. Pire, une trame refusée par le système faisait perdre le canal entier du fil, et toutes les inspections
  suivantes de ce fil passaient sans contrôle. Désormais :
  - les canaux sont créés avec un tampon assez grand pour une trame complète quand le système le permet
    (`net.core.wmem_max`), et le moteur natif relit la capacité réelle ;
  - la part du corps envoyée est plafonnée à ce qui tient dans la trame. Un avertissement est écrit dans le
    journal d'erreurs au démarrage et au rechargement quand ce plafond réduit `body_max_inspect_bytes` (jamais un
    refus de démarrer) ;
  - une requête impossible à inspecter est **toujours refusée (503)**, quel que soit `on_internal_error`, et
    seule cette requête est touchée : le canal reste en service.
- **Processus de sécurité : un verdict pouvait se perdre en silence (D19).** Les verdicts et la liste des
  sources surveillées partent vers le moteur natif sur un canal non bloquant ; quand ce canal était plein,
  l'erreur était ignorée et la trame perdue. La requête attendait alors 60 s puis passait en `fail-open` : **un
  verdict « bloquer » pouvait ainsi se perdre**. Désormais les trames attendent que le canal se libère et partent
  toutes, dans l'ordre.
- **Reverse proxy : la réponse d'un visiteur pouvait partir chez un autre (D22).** Une connexion vers le backend
  revenait au pool sans vérifier qu'il ne restait rien à lire après le corps annoncé. Un backend qui envoyait
  plus d'octets que son `Content-Length` (bogue, ou compromission) glissait ainsi une réponse au visiteur
  suivant, et toutes les réponses suivantes étaient décalées d'un visiteur. Une réponse HTTP/1.0 ou un
  `Connection: close, …` (liste de jetons) n'empêchaient pas non plus le recyclage. Désormais une connexion ne
  revient au pool que si la réponse est HTTP/1.1, sans jeton `close`, et lue exactement sans octet en trop ; une
  connexion du pool qui a reçu des octets pendant son attente est jetée.
- **Reverse proxy : longueur de réponse ambiguë (D21).** Avec `Content-Length` et `Transfer-Encoding` reçus
  ensemble, le proxy croyait `Content-Length` : réponse tronquée et reste de la réponse laissé dans la
  connexion recyclée. Désormais `Content-Length` avec `Transfer-Encoding`, plusieurs longueurs différentes, ou
  une longueur qui n'est pas faite que de chiffres donnent **502**, et la connexion est fermée (RFC 9112 §6.3).
- **Reverse proxy : une requête POST pouvait être envoyée deux fois au backend (D42).** Après une erreur sur une
  connexion réutilisée, le proxy renvoyait la requête sur une connexion neuve, quelle que soit sa méthode, alors
  que la règle de reprise excluait POST. Une action (commande, paiement, message) pouvait ainsi être exécutée
  deux fois. Désormais POST, PUT, PATCH, DELETE et les autres méthodes non rejouables ouvrent toujours une
  connexion neuve, et ne sont donc jamais renvoyées. La reprise reste pour GET, HEAD et OPTIONS, seulement si la
  connexion réutilisée n'a renvoyé aucun octet de réponse.
- **Reverse proxy : un client pouvait se faire passer pour une autre adresse auprès du backend (D25).**
  `X-Real-IP`, `Forwarded`, `Proxy-Connection` et les en-têtes nommés dans `Connection:` passaient tels quels du
  client au backend. Un backend qui faisait confiance à `X-Real-IP` (cas courant) croyait donc l'adresse choisie
  par le client. Désormais ces en-têtes sont retirés, et `X-Real-IP` est écrit avec l'adresse réelle du client,
  la même que `X-Forwarded-For` : derrière un relais de confiance déclaré dans `trusted_proxy` (Tailscale, par
  exemple), c'est l'adresse du visiteur, jamais celle du relais. `X-Forwarded-Port` passe comme avant.

### Tests

- 20 tests ajoutés, écrits avant chaque correction ; 15 échouaient sur 2.6.1, les 5 autres gardent contre une
  régression du correctif :
  - moteur natif et processus de sécurité : 7 (4 d'intégration, 2 du processus de sécurité, 1 de l'instantané) ;
  - reverse proxy : 13 (8 du client vers le backend, 3 des en-têtes envoyés, 2 d'intégration de bout en bout,
    dont le vrai client derrière un relais de confiance, retrouvé dans les en-têtes et dans le journal).

## version 2.6.1 : Publié

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
