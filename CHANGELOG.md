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

## [Non publié]

Plan de référence : `OMEGA-SERV_PLAN-DETAILLE_SENSITIVE_PATHS.md`.

### Ajouté

- **Listes de chemins sensibles** (`options.waf.rules.keyword_lists`, `match: "path"`) :
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

### Modifié

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
- Écran WAF Custom : le bouton « Ajouter une règle » devient « Ajouter ».
- `build-release.sh` n'inclut plus les listes locales `secure/waf/rules/keywords/*.txt`
  dans l'archive ; `migrate-state.sh` les recopie depuis l'ancienne installation.

### Corrigé

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
