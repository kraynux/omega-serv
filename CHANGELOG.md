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
