<!-- Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE) -->
<div align="center">
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/assets/omega-serv.png" alt="Omega-Serv" width="384">
</div>

# 🔒 OMEGA-SERV

**Serveur web HTTP autonome, portable et durci par défaut**

> Élaboré par **kraynux** pour **Omega-server** 
[kraynux.snake-mackarel](https://kraynux.snake-mackarel.ts.net)

Page officielle : [OMEGA-SERV](https://kraynux.snake-mackarel.ts.net/omega-serv/) &nbsp; Référence, utilisation, Aide & FAQ : [Guide complet](https://kraynux.snake-mackarel.ts.net/omega-serv/guide.html) &nbsp; Aperçu : [Screenshots](https://kraynux.snake-mackarel.ts.net/omega-serv/screenshots/)  

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/Platform-Linux-informational.svg)](https://www.linux.org/)
[![Interface](https://img.shields.io/badge/Interface-CLI%20%2B%20TUI-cyan.svg)](#3-utilisation)

**Langues:**
[Français](README.md) · [English](README.en.md) · [Español](README.es.md) · [Русский](README.ru.md) · [中文](README.zh-CN.md)
---

**Omega-serv** est un serveur HTTP/1.1 écrit en Python pur (bibliothèque standard uniquement pour le cœur du serveur), pensé pour servir du contenu statique et, en option, du PHP-FPM, avec un durcissement de protocole non désactivable et des modules de sécurité (WAF, TLS, authentification) superposables plutôt qu'imposés. Septième outil de la suite `omega-` mais volontairement **hors de la future intégration `omega-suite`** (il agit sur la machine locale qui l'héberge, pas sur des cibles distantes — même famille qu'`omega-fire`) ; structuré en Clean Architecture, `bootstrap/` faisant office de racine de composition.

## 1. Vision et périmètre

La priorité affichée est la **solidité/sécurité du cœur HTTP d'abord** — WAF et TLS sont des modules optionnels posés par-dessus, jamais des prérequis. Un serveur qui ne fait qu'une chose (servir des fichiers, éventuellement du PHP) mais la fait correctement, avec un vrai durcissement protocolaire non contournable, plutôt qu'un serveur qui fait beaucoup de choses à moitié.

### Ce que fait Omega-serv

- Sert du contenu statique (fichiers, listing de répertoire optionnel, alias, redirections, réécritures, cache) avec résolution de chemin sûre (traversal, double-encodage, liens symboliques).
- Durcit le protocole HTTP par défaut, sans option pour le désactiver : méthodes autorisées explicites, validation de l'en-tête `Host`, rejet de l'ambiguïté `Content-Length`/`Transfer-Encoding`, en-têtes de sécurité et CSP de base non-contournables.
- Optionnellement : filtrage WAF (signatures, limitation de débit, liste de blocage), TLS direct (certificat auto-signé, signé par une CA locale, ou public via Let's Encrypt/Certbot avec renouvellement automatique — voir §9), authentification HTTP Basic par zone, PHP via FastCGI/PHP-FPM, zones d'upload confinées.
- Audite sa propre configuration (`audit security`) et s'installe comme service système (systemd/OpenRC/runit).
- CLI non-interactive scriptable de bout en bout, **et interface interactive (Textual)** qui habille exactement les mêmes cas d'usage — voir §3. Feuille de route interface (`OMEGA-SERV_PLAN-DETAILLE_INTERFACE.md`, §12) **entièrement livrée** : registre des capacités, profils/options, configuration détaillée (alias/redirections/rewrites/FastCGI/dirlisting/authentification/cache/WAF/proxies de confiance/reverse proxy sortant/TLS), gestion des logs (voir/suivre/lnav/rotation/sauvegarde/automatisation/statistiques/top IPs), service système, multi-instance (registre, création), vérification/simulation/audit, sauvegarde/restauration de configuration, assistant de premier lancement, réglages applicatifs (thème, profil de rendu, chemins d'export/captures), guide d'aide contextuel (fiche par écran avec exemples concrets, FAQ, export HTML, couverture exhaustive vérifiée par test), indication systématique rechargement/redémarrage après chaque enregistrement, configuration Active Defense intégrale sans édition manuelle de fichier.

### Ce qu'Omega-serv ne fait pas

- CGI brut (retiré du périmètre V1 — seul FastCGI/PHP-FPM est supporté).
- Authentification mutuelle TLS (mTLS), OCSP stapling — hors périmètre V1, voir §15. (ACME/Let's Encrypt via Certbot est disponible, voir §9c/9d.)
- Cache HTTP partagé entre processus.
- Scan/audit d'une cible distante (voir `omega-check`/`omega-scan`/`omega-deep` pour ça — Omega-serv s'audite lui-même, jamais un tiers).

### Avertissement d'usage

Omega-serv **refuse de démarrer en tant que root**. Aucun module de sécurité (WAF, TLS, authentification) n'est activé par défaut dans aucun profil fourni, y compris `hardened` — les activer est toujours un geste explicite (`config enable-tls`, `option enable waf`...). Le profil `hardened` lui-même recommande un reverse proxy pour une exposition Internet réelle plutôt que de s'y substituer.

## 2. Installation

### Prérequis

- Python 3.10+
- `openssl` (binaire, pas une bibliothèque Python) pour tout ce qui touche aux certificats TLS — les autres fonctions marchent sans.

### Installation

```bash
[ -d omega-serv ] && echo "ℹ️ Déjà extrait ici, étape ignorée." || tar -xzf omega-serv.tar.gz
cd omega-serv/
chmod +x install.sh
./install.sh
```

`install.sh` :

1. Crée l'environnement virtuel `.venv` s'il n'existe pas déjà.
2. Installe le paquet (`pip install -e .`) — **aucune dépendance externe** (voir §6).
3. Rend `omega-serv.sh` et `install.sh` exécutables.
4. Ajoute l'alias `serv` à `~/.bashrc` et `~/.zshrc` (sans doublon si déjà présent).

### Dépendances

Le cœur du serveur (parseur HTTP/1.1, client FastCGI, hachage de mot de passe via `hashlib.scrypt`) reste en Python pur/stdlib, et tout ce qui touche aux certificats TLS passe par le binaire `openssl` en sous-processus plutôt que par une bibliothèque crypto Python — **aucune dépendance externe pour ça**. Seule l'interface interactive (§3) en introduit : `omega-lib` (thèmes, détection de terminal — bibliothèque partagée de la suite, non publiée sur PyPI, vendorée dans l'archive distribuable), `textual` et `pyte` (émulation de terminal pour le rendu `lnav` fusionné dans l'interface), `jinja2` (exports HTML thématisés) et `psutil` (écran État & Ressources — CPU/RAM/disque/réseau). Dépendance de développement/test optionnelle (`pip install -e ".[test]"`) : `hypothesis` (tests de propriétés du parseur HTTP et du résolveur de chemin, jamais en production). Outillage qualité (`pip install -e ".[dev]"`) : `pytest`, `ruff`, `mypy`, `import-linter`.

### Outils optionnels recommandés

L'interface fonctionne en mode dégradé si ces outils sont absents :

- `lnav` — analyse avancée des logs fusionnée dans l'écran **Gestion des logs** (§3) ; message d'erreur clair et explicite si l'exécutable est introuvable, aucun crash, le reste de l'écran (voir/suivre/rotation/statistiques) fonctionne normalement sans.
- `python-psutil` (paquet système équivalent au `psutil` de PyPI) — installé automatiquement par `pip install -e .` dans tous les cas (dépendance obligatoire du paquet, l'écran **État & Ressources** en a toujours besoin), mais le préinstaller via le gestionnaire système évite à `pip` de devoir compiler son wheel localement.

```bash
# Arch Linux et dérivés
sudo pacman -S lnav python-psutil

# Debian/Ubuntu et dérivées
sudo apt install lnav python3-psutil

# Fedora
sudo dnf install lnav python3-psutil
```

## 3. Utilisation

Deux interfaces strictement équivalentes fonctionnellement, jamais de logique dupliquée entre les deux : CLI non-interactive (scriptable, utilisée ci-dessous) et interface interactive Textual (menus, formulaires, tableaux) — chaque action de l'une existe côté CLI, l'interface ne fait qu'habiller les mêmes cas d'usage.

### Mode interactif (TUI)

Recommandé pour l'usage quotidien — lancé sans argument :

```bash
./omega-serv.sh
```
si vous avez créé l'alias, tapez juste `serv` dans le terminal :
```bash
serv
```

### Parcours général

Écran de démarrage (splash, se ferme sur une touche ou un clic) → menu principal (Assistant premier lancement / Registre des capacités / Profils / Configuration détaillée / Active Sécurité / Gestion des logs / Service / Multi-instance / État & Ressources / Audit / Sauvegarde) → sélection d'une section puis d'une action, chaque formulaire validant ses champs requis avant de continuer → confirmation explicite avant toute opération sensible ou destructive (redémarrage, suppression, restauration...) → indication systématique de la suite (rechargement à chaud automatique, ou confirmation de redémarrage complet) après tout enregistrement qui modifie une configuration déjà servie. L'adaptation au terminal (couleurs, taille, dégradation structurelle du profil de rendu) est automatique et sans flag manuel — voir §4.

#### Raccourcis clavier (interface interactive)

| Touche | Action |
|---|---|
| `↑` / `↓` | Naviguer entre les éléments d'un écran |
| `Tab` / `Maj+Tab` | Naviguer entre les champs d'un formulaire |
| `Échap` | Retour à l'écran précédent (confirmation de sortie sur l'accueil) |
| `t` | Thème suivant (appliqué immédiatement, sans confirmation) |
| `r` | Rafraîchir la détection du terminal |
| `F1` | Aide de l'écran actif (fiche contextuelle — voir "Guide d'aide" ci-dessous) |
| `a` | Guide d'aide complet (menu navigable + FAQ) |
| `o` | Réglages applicatifs (thème, profil de rendu, chemins d'export/captures — voir ci-dessous) |
| `q` | Quitter (avec confirmation) |
| `Ctrl+P` | Palette de commandes (Thème, Capture d'écran, Options...) |

#### Guide d'aide (touches `F1`/`a`)

Système d'aide intégré, jamais un simple texte statique : chaque écran documenté (fiche définition/champs à remplir avec exemples concrets/action déclenchée/réaction — rechargement, redémarrage ou aucun) est accessible directement depuis lui via `F1` ; la touche `a` ouvre le menu complet (arborescence identique à la navigation réelle de l'application) avec un accès à la FAQ (pièges rencontrés en usage réel, ex. classes d'attaque Active Defense, permissions de service partagé) et un export HTML autonome (thème actif conservé) de l'intégralité du guide. Repli sur un écran de référence générique tant qu'une fiche précise n'existe pas encore — couverture actuellement exhaustive, vérifiée par test.

#### Menu principal (interface interactive)

- **Assistant premier lancement** — parcours guidé en 8 étapes (bienvenue → capacités en lecture seule → choix du profil → bind/port → TLS optionnel → vérification → résumé + écriture → proposition d'installation du service) ; permet de générer une configuration complète et de mettre le serveur en route sans connaître la CLI.
- **Registre des capacités** — sonde système en lecture seule (init système, port configuré déjà occupé ou non, `openssl`/`logrotate`/`tailscale`/`lnav` présents, espace disque, limite de descripteurs...), export JSON/HTML.
- **Profils** — même cas d'usage que `profile` en CLI (§5), diff toujours affiché avant écriture.
- **Configuration détaillée du serveur** — CRUD complet sur alias/redirections/rewrites/dirlisting/proxies de confiance/reverse proxy sortant/FastCGI/cache/authentification/contrôle d'accès/pages d'erreur, plus le sous-menu **TLS** (statut, génération auto-signée, assistant CA locale, assistant Let's Encrypt/Certbot, renouvellement automatique, révocation, activer/désactiver — voir §9) ; un second cadre **OPTIONS ET VÉRIFICATION** y regroupe les raccourcis vers **Options** (`option` CLI, §7) et **Vérifier la configuration** (`config check` CLI, §10) — même parcours qu'ajuster des réglages puis vérifier, ces deux écrans ne sont plus accessibles directement depuis le menu principal. Le WAF n'y vit plus (voir "Active Sécurité" ci-dessous) : il expose surtout de l'état opérationnel qui change en continu, pas un simple formulaire de configuration statique. Chaque enregistrement précise systématiquement la suite : rechargement à chaud automatique et silencieux si un service est actif (dirlisting, accès, alias/redirections/rewrites, cache, pages d'erreur, proxies de confiance, zones reverse proxy/FastCGI, utilisateurs/zones d'authentification), ou confirmation explicite de redémarrage complet quand le changement touche le socket d'écoute, TLS ou Active Defense — plus aucun écran ne laisse deviner s'il faut relancer le serveur.
- **Active Sécurité** — écran unique regroupant deux blocs : **Active Defense** (Etat, Menaces suivies avec score/niveau, Incidents avec chronologie/export IoC/rapport, affectations de Deception, Simuler une décision en dry-run, **Réglages** — configuration intégrale sans jamais éditer `config/omega-serve.json` à la main, voir §11) et **WAF** (Etat, Modules — mode/packs de règles/liste de blocage, Tester une requête, Custom — auteur de règle personnalisée) — voir §11.
- **Gestion des logs** — voir/suivre un fichier en direct, `lnav` fusionné (rendu terminal réel dans l'interface), rotation/archivage manuel ou automatique par seuil de taille, création de sauvegarde immédiate, configuration/gestion d'automatisations planifiées (déclaratif — voir note ci-dessous), restaurer/purger une archive, export de la liste, statistiques (top IPs, répartition par code de statut, histogramme horaire) avec retrait d'une IP du log d'accès.
- **Service** — mêmes actions que `service` en CLI (§12), élévation `sudo` ponctuelle par action, jamais l'application entière lancée en root.
- **Multi-instance** — registre global (`~/.config/omega-serv/instances.json`, hors de tout répertoire de projet) des installations connues sur la machine, avec statut systemd de chacune ; création d'une nouvelle instance (copie d'arborescence, environnement virtuel et dépendances propres, configuration fraîche avec port distinct, vérification de non-imbrication et de conflit de port) directement depuis l'interface. Bouton invisible en substance pour une installation unique (libellé "Multi-instance" devient "Instances (N)" dès 2 connues) ; bascule complète vers une autre instance (`os.execv`, confirmation explicite, splash dédié annonçant la bascule au redémarrage) ; désinstallation complète d'une instance (retrait de l'unité, du compte système dédié s'il n'est plus utilisé par aucune autre instance, et suppression optionnelle du répertoire, jamais par défaut).
- **État & Ressources** — vue d'ensemble en un coup d'œil, rafraîchie toutes les 2 secondes : état du serveur (processus/PID, statut du service système, profil/options actives/TLS/port), flux du log d'accès en direct (débit, répartition par code de statut, IPs uniques, taux d'erreur), ressources système (CPU/RAM/disque/swap/charge/réseau, via `psutil`) ; regroupe aussi le raccourci **Simuler une requête** (même cas d'usage que la commande CLI correspondante, §10).
- **Audit de sécurité** — même cas d'usage que la commande CLI correspondante (§10).
- **Sauvegarde de configuration** — archive tar.gz du fichier de configuration et, sur option explicite, des règles WAF/zones d'authentification/certificats (confirmation obligatoire dès que des secrets réels sont inclus)/base Active Defense, restauration, liste, suppression.

> Note sur les automatisations de rotation planifiées : elles sont enregistrées (fréquence + log ciblé) mais **rien ne les exécute automatiquement** — ni côté interface, ni en tâche de fond. C'est un choix délibéré de parité avec l'écran équivalent d'`omega-fire`, qui a le même comportement déclaratif. Une exécution périodique réelle (minuteur systemd, tâche de fond) reste à construire séparément si le besoin est confirmé.

#### Réglages applicatifs (touche `o` ou palette de commandes)

Préférences d'interface uniquement — jamais confondues avec `config/omega-serve.json` (configuration du serveur) : thème actif, profil de rendu (`complete`/`standard`/`reduced`/`mono`, redémarrage requis), chemin des exports (`var/exports/` par défaut), chemin des captures d'écran (`var/screenshots/` par défaut), purge de l'un ou l'autre dossier (confirmation obligatoire).

```bash
# Lancer le serveur (premier plan, SIGTERM = arrêt propre avec délai de grâce, SIGHUP = rechargement a chaud WAF/Auth)
./omega-serv.sh serve

# Configuration
./omega-serv.sh config init                # genere config/omega-serve.json (valeurs sures par defaut)
./omega-serv.sh config check                # verifie sans demarrer (memes portes bloquantes qu'au demarrage)
./omega-serv.sh config show
./omega-serv.sh config enable-tls --cert ... --key ... --mode direct
./omega-serv.sh config disable-tls

# Profils (minimal / standard / hardened / development)
./omega-serv.sh profile list
./omega-serv.sh profile show hardened
./omega-serv.sh profile apply hardened --dry-run   # diff avant application, toujours

# Options (aliases, redirects, rewrites, dirlisting, cache, waf, upload, fastcgi, reverse_proxy...)
./omega-serv.sh option list
./omega-serv.sh option enable waf
./omega-serv.sh option disable waf

# Simuler une requete sans lancer le serveur (utile pour valider une regle avant activation)
./omega-serv.sh simulate-request GET /index.html

# WAF (fonctionne meme option desactivee, via --force implicite)
./omega-serv.sh waf test --method GET --path /admin --remote-ip 203.0.113.1
./omega-serv.sh blocklist list
./omega-serv.sh blocklist add --network 203.0.113.0/24 --reason "scan detecte" --duration-seconds 3600
./omega-serv.sh blocklist remove --network 203.0.113.0/24

# Active Defense (deception + mode guerre, option "active_defense" - voir §11)
./omega-serv.sh active-defense status
./omega-serv.sh active-defense simulate --ip 203.0.113.42 --path /wp-login.php --attack-class scan --score 40
./omega-serv.sh active-defense purge
./omega-serv.sh threats list --level hostile
./omega-serv.sh threats show 203.0.113.42:ab12cd34
./omega-serv.sh incidents list --status open
./omega-serv.sh incidents show <incident-id>
./omega-serv.sh incidents close <incident-id>
./omega-serv.sh incidents export-ioc <incident-id> --format json,csv
./omega-serv.sh incidents generate-report <incident-id>
./omega-serv.sh deception list
./omega-serv.sh deception release --subject 203.0.113.42:ab12cd34

# Certificats TLS - auto-signe (9a)
./omega-serv.sh certs generate-self-signed --cn localhost --san-dns localhost --san-ip 127.0.0.1
./omega-serv.sh certs show
./omega-serv.sh certs check-expiry --warn-days 30

# Certificats TLS - CA locale (9b)
./omega-serv.sh certs generate-ca --cn "Mon CA locale" --days 3650
./omega-serv.sh certs generate-csr --cn serveur.local --san-dns serveur.local --key-out server.key --csr-out server.csr
./omega-serv.sh certs sign-csr --csr server.csr --ca-key secure/certificates/ca/root-ca.key --ca-cert secure/certificates/ca/root-ca.pem --out server.pem --fullchain-out fullchain.pem
./omega-serv.sh certs revoke --cert server.pem --ca-key secure/certificates/ca/root-ca.key --ca-cert secure/certificates/ca/root-ca.pem

# Certificats TLS - import (9c, ex. depuis un hook Certbot)
./omega-serv.sh certs import --key privkey.pem --cert fullchain.pem

# Authentification HTTP Basic
./omega-serv.sh auth add-user --username alice
./omega-serv.sh auth create-zone --url-prefix /admin/ --allowed-users alice
./omega-serv.sh auth list

# Audit de securite (ne bloque jamais, informatif)
./omega-serv.sh audit security --format text --min-severity medium

# Sauvegarde de configuration (config toujours incluse ; secrets reels
# jamais chiffres par defaut, --confirm-secrets obligatoire pour les inclure)
./omega-serv.sh config backup --description "avant migration"
./omega-serv.sh config backup --include-auth --include-certificates --confirm-secrets
./omega-serv.sh config backup --include-active-defense --description "menaces/incidents"
./omega-serv.sh config list-backups
./omega-serv.sh config restore --snapshot-id snapshot_20260908_170003_762484

# Service systeme (systemd/OpenRC/runit, detection automatique)
./omega-serv.sh service install --user omega-serv --group omega-serv
./omega-serv.sh service start
./omega-serv.sh service status
```

### Codes de sortie notables

| Commande | Code | Signification |
|---|---:|---|
| `audit security` | `0` | Rien de grave (aucun `CRITICAL`/`HIGH`) |
| `audit security` | `1` | Au moins un finding `CRITICAL` |
| `audit security` | `2` | Au moins un `HIGH` sans `CRITICAL` |
| `audit security` | `3` | Erreur d'exécution (config introuvable...) |
| `certs check-expiry` | `1` | Certificat expiré |
| toute autre commande | `0`/`1` | Succès / échec de validation |

## 4. Compatibilité terminaux

L'interface interactive (Textual) détecte automatiquement les capacités du terminal (émulateur, taille) et adapte sa feuille de style structurelle en conséquence (`complete`/`standard`/`reduced`/`mono`), sans flag manuel. Le mode CLI reste toujours en texte simple, indépendant du terminal. Politique partagée par toute la suite `omega-` (`omega-lib`, `terminal/policies.py`) — identique à celle d'`omega-check`/`omega-fire`.

### Profil selon l'émulateur détecté

| Émulateur | Profil initial |
|---|---|
| Ghostty, Alacritty, WezTerm, Kitty | `complete` |
| Konsole, GNOME Terminal, Terminator, Xfce4 Terminal | `standard` |
| xterm, urxvt, SSH moderne | `reduced` |
| TTY Linux, SSH ancien | `mono` |
| Émulateur non reconnu | `reduced` (repli par défaut) |

### Profil selon la taille du terminal

| Taille minimale (colonnes × lignes) | Plafond de profil |
|---|---|
| 120 × 32 | `complete` |
| 100 × 28 | `standard` |
| 80 × 24 | `reduced` |
| en dessous | `mono` |

Le profil final retenu est **le plus restrictif des deux** (émulateur et taille) — un Ghostty en plein écran redimensionné à 70 colonnes redescend en `mono`, même si son émulateur autoriserait `complete`. Rafraîchissable en direct par la touche `r`, ou surchargeable manuellement depuis les Réglages applicatifs (touche `o`, §3).

## 5. Profils

| Profil | Usage visé |
|---|---|
| `minimal` | Démonstration/local simple : statique seul, aucune option activée |
| `standard` | Site statique ou petite production : en-têtes usuels, CSP de base, dirlisting/CGI/FastCGI désactivés |
| `hardened` | Exposition avec moindre privilège : bind local par défaut (reverse proxy recommandé pour Internet), méthodes limitées GET/HEAD, CSP stricte, anti-slowloris — le WAF n'est **jamais** activé automatiquement, même ici |
| `development` | Développement local uniquement, jamais présenté comme adapté à Internet : bind loopback obligatoire, CSP en report-only, pages d'erreur détaillées |

Ordre de fusion de configuration : valeurs sûres intégrées → profil sélectionné → options actuellement actives conservées (survivent à un changement de profil) → overlay utilisateur explicite. Un diff complet est toujours affiché avant écriture (`profile apply`).

## 6. Architecture

Clean Architecture (`core / domain / ports / application / infrastructure / interfaces / bootstrap`) — `bootstrap/` est la racine de composition (équivalent du `app/` des autres outils de la suite). Particularité assumée de ce projet, vérifiée par `import-linter` plutôt que supposée : `application/server/start_server.py` (et `validate_config.py`, `run_audit.py`) jouent un rôle d'**usine de construction dépendante de la configuration réelle** (quel gestionnaire de service, activer le WAF ou non...) et instancient des adaptateurs `infrastructure/` concrets directement — contrairement au patron plus strict de CHECK/TRACK où `application/` ne consomme que des `ports/`. La seule règle universelle réellement imposée : `domain/`/`core/` ne dépendent jamais des couches externes.

```text
src/omega_serv/
├── core/            Vocabulaire transverse (platform_info, constantes)
├── domain/           Logique metier pure (HTTP, config, securite WAF/TLS/auth/audit, routage)
├── ports/            Contrats (Protocol) attendus par l'application
├── application/      Cas d'usage - certaines fonctions (build_server...) composent aussi des adaptateurs concrets (voir ci-dessus)
├── infrastructure/    Implementations reelles (asyncio, openssl en subprocess, systemd/OpenRC/runit, fichiers)
├── interfaces/cli/    CLI argparse non-interactive
├── interfaces/tui/    Interface interactive Textual (memes cas d'usage, jamais de logique dupliquee)
└── bootstrap/         DependencyContainer, resolution de la racine du projet
```

Règles vérifiées par `import-linter` (7 contrats) : `domain`/`core` jamais dépendants des couches externes ; `interfaces.tui` jamais directement dépendant d'`infrastructure` ; `textual` confiné à `interfaces.tui` ; `subprocess` confiné à `infrastructure/process/subprocess_runner.py` (et `infrastructure/lnav/`, flux PTY interactif) ; `ssl` confiné à `infrastructure/tls/ssl_context_builder.py` ; `jinja2` confiné à `infrastructure/exporters/html_exporter.py` ; `sqlite3` confiné à `infrastructure/persistence/sqlite_active_defense_connection.py` (seul stockage relationnel du projet, réservé à Active Defense — voir §11).

## 7. Modules optionnels

Tous désactivés par défaut dans tous les profils fournis — activation toujours explicite (`option enable <nom>` ou `config enable-tls`) :

| Module | Rôle |
|---|---|
| `waf` | Signatures (chemins sensibles, UA scanner, SQLi/XSS/CMDi dans le corps), limitation de débit (seau à jetons), liste de blocage (CIDR + expiration), réputation/escalade — mode `log-only` structurellement incapable de bloquer |
| TLS | Direct (auto-signé, CA locale, ou public via Let's Encrypt/Certbot avec renouvellement automatique — voir §9), jamais mTLS/OCSP en V1 |
| Authentification | HTTP Basic par zone (`url_prefix`), `hashlib.scrypt` avec défense anti-timing (temps constant même pour un utilisateur inconnu) |
| FastCGI/PHP-FPM | Un seul `(url_prefix, script_root)`, `script_root` confiné hors de `webroot/` par construction (le handler statique ne peut jamais divulguer de source PHP) |
| Reverse proxy sortant | Omega-serv agit lui-même comme proxy vers un backend (sens inverse de `server.tls.mode = "behind_proxy"`) — un ou plusieurs upstreams HTTP/HTTPS par zone avec répartition de charge round-robin (vérification TLS stricte par défaut, désactivable mais dangereuse), en-têtes hop-by-hop retirés, `X-Forwarded-*` toujours écrasés (jamais fusionnés avec ceux du client), WebSocket (un seul upstream figé pour la durée du tube, sans timeout applicatif une fois établi) |
| Upload | Zones confinées, quotas par zone, noms de fichiers générés côté serveur — pas de streaming en V1 (borné par `server.max_request_size`) |
| `active_defense` | Deception + mode guerre à partir des signaux WAF déjà calculés (jamais un second score) : leurres statiques, ralentissement/journalisation enrichie/limitation de débit ciblés, incidents + export IoC — voir §11 |

## 8. Durcissement HTTP (non désactivable)

- En-tête/ligne de requête bornés **pendant** la lecture (jamais après coup), repliage d'en-tête obsolète refusé, `Transfer-Encoding` toujours refusé (jamais deviné).
- `Content-Length` dupliqué rejeté ; `Expect: 100-continue` rejeté proprement (417).
- Liste blanche de méthodes explicite (405 + `Allow` sinon), en-tête `Host` validé (manquant/vide/dupliqué-même-identique/caractère de contrôle → 400).
- En-têtes de sécurité et CSP de base (`enforce`/`report-only`) appliqués à **toute** réponse, y compris les erreurs — non contournables par une option.
- Adresses IPv4-mappées-IPv6 (`::ffff:x.x.x.x`) normalisées avant toute comparaison (liste de blocage, proxy de confiance, limitation de débit) — bypass connu sinon.
- Vérifié par tests de propriétés (`hypothesis`, des milliers d'exemples générés) contre le parseur HTTP et le résolveur de chemin, en plus des tests unitaires/intégration classiques.

## 9. TLS

### 9a. Certificat auto-signé (minimal)

Couvre l'usage réaliste local/labo/VPN (Tailscale...) : un seul écouteur, `ssl.SSLContext` direct, RSA 2048/4096 ou ECDSA P-256/P-384.

### 9b. CA locale

Pour plusieurs appareils clients qui doivent faire confiance sans réimporter un certificat individuellement : une autorité de certification locale signe autant de certificats serveur que nécessaire.

```text
secure/certificates/ca/
├── root-ca.key    # 0600 - l'element le plus sensible du projet
├── root-ca.pem    # 0644 - a importer dans le magasin de confiance des clients
├── serial.txt     # 0600 - suivi du prochain numero de serie
└── index.txt      # 0600 - suivi statut V(alide)/R(evoque) par certificat signe
```

Flux : `certs generate-ca` (passphrase de clé CA **obligatoire**, saisie interactive à double confirmation si `--password` omis) → `certs generate-csr` (clé + CSR serveur) → `certs sign-csr` (signe avec la CA, copie le SAN de la CSR, construit `fullchain.pem` si demandé) → pointer `tls.certificate.certificate_path` vers ce `fullchain.pem`. Un certificat compromis se retire via `certs revoke` (marque `index.txt`, vérifie d'abord que le certificat provient bien de cette CA — refuse sinon). Pas de distribution CRL en V1, ni de CA externe/CSR pour autorité tierce, ni de mTLS (voir §15).

### 9c. Let's Encrypt / ACME (Certbot) — public, auto-hébergé

Pour un site réellement public avec un certificat reconnu par les navigateurs, schéma auto-hébergé complet : DDNS (Dynu ou équivalent, entièrement à la charge de l'opérateur) → Certbot → Omega-serv. Assistant TUI uniquement (`Configuration détaillée → TLS → Assistant Let's Encrypt`) — invoque `certbot certonly --webroot` en sous-processus (**jamais** `--standalone`, le port 80 est déjà occupé par Omega-serv ; **jamais** de client ACME réimplémenté) avec `--config-dir`/`--work-dir`/`--logs-dir` pointés sous `secure/certificates/letsencrypt/` du projet — **jamais** `/etc/letsencrypt/` — ce qui rend Certbot lui-même entièrement non privilégié. Le certificat obtenu est importé automatiquement (même mécanisme que `certs import`, voir les exemples CLI ci-dessus) et un script de hook de renouvellement est écrit. Mode test (staging) coché par défaut — à décocher une fois le domaine/webroot vérifiés fonctionnels, pour éviter les limites de taux réelles de Let's Encrypt.

Prérequis entièrement hors du périmètre d'Omega-serv : domaine pointé vers l'IP publique (DDNS), et ports 80/443 redirigés vers cette machine.

### 9d. Renouvellement automatique (Certbot)

`Configuration détaillée → TLS → Renouvellement automatique` s'adapte au gestionnaire de service réellement détecté **pour cette instance** (jamais un mécanisme partagé entre plusieurs instances multi-instance) : systemd → génère et installe un timer (`<service>-certbot-renew.timer`, deux fois par jour + délai aléatoire, `certbot renew` scopé au `--config-dir` de l'instance) ; sinon → ligne crontab (utilisateur courant, aucun privilège) si `crontab` est disponible ; sinon → instructions manuelles affichées, aucune écriture forcée. Sur certaines distributions (dont Arch/Manjaro), le paquet Certbot n'installe **aucun** timer par défaut, contrairement à Debian/Ubuntu — d'où cet écran plutôt qu'une simple vérification d'un mécanisme supposé déjà présent. Une fois configuré, le renouvellement réimporte automatiquement chaque certificat renouvelé (`certs import`) puis redémarre le service, sans plus jamais intervenir manuellement.

## 10. Audit de sécurité

`audit security` est **non bloquant** : il ré-exécute les portes déjà bloquantes de `config check` en `CRITICAL`, puis applique des règles consultatives (TLS, CSP, méthodes dangereuses, timeouts, hygiène upload en pur ; permissions de fichiers, expiration de certificat, unité systemd installée, taille des logs en I/O réelle). `WAF-001` (WAF resté en `log-only`) s'observe dans le temps via un petit fichier d'état (`var/run/waf-mode-state.json`) — ne se déclenche qu'après ≥14 jours observés en `log-only` sur des exécutions répétées, pas au premier `audit`.

## 11. Active Defense (deception + mode guerre)

Module optionnel (`option enable active_defense`, désactivé par défaut) qui qualifie un comportement hostile à partir des signaux WAF déjà calculés (`WafDecision`/réputation/liste de blocage — jamais un second calcul de score indépendant), et peut faire basculer une source vers un leurre, ralentir ses réponses et journaliser plus finement, construire un incident exploitable, puis exporter des indicateurs de compromission (IoC). Ne bloque jamais le trafic lui-même — le blocage réseau reste du ressort d'`omega-fire` ; Active Defense observe, dérive, ralentit et consigne.

**Menaces et score** : chaque source (`IP + hash SHA-256 du User-Agent`) accumule un score (`WAF-001` bloquant +10, escalade de réputation +25, bannissement connu +25, POST sur un leurre déjà assigné +30 — décroissance de -5 toutes les 15 minutes sans nouvel événement) qualifié en `normal`/`suspicious`/`hostile`/`contained` (`contained` exige en plus un bannissement déjà connu). `mode: monitor` observe sans agir ; `mode: enforce` applique réellement les actions ci-dessous.

**Mode guerre** (`options.active_defense.settings.war_mode`) : un `DefensePlaybook` (`actions: ["redirect_to_decoy", "enrich_log", "delay", "rate_limit", "create_incident", "export_ioc"]`) déclenché par seuils configurables, pour toute source non `normal` :
- `enrich_log` — journal JSONL séparé (`var/log/active-defense-enriched.jsonl`, jamais mélangé au log WAF/production), en-têtes redactés, corps HTTP haché (SHA-256) ou tronqué selon `logging.capture_request_body`.
- `delay` — ralentissement borné et jitté (`war_mode.slowdown.minimum_ms`/`maximum_ms`/`jitter_ms`), jamais un blocage de la boucle asyncio.
- `rate_limit` — limitation de débit dédiée par source (`war_mode.rate_limit.requests`/`window_seconds`), réutilise le même mécanisme que le WAF sous une clé distincte.
- `create_incident` — ouverture/fusion automatique d'un incident au franchissement de `thresholds.incident_score`.

**Deception** : une source `hostile`/`contained` peut être affectée à un leurre statique (`fake_admin`, `fake_cms`, `fake_api`, `fake_secrets` — réponses plausibles mais toujours fixes, jamais de lecture réelle de fichier ni de sous-processus) sélectionné selon la classe d'attaque observée (`deception.profiles.<nom>.match_attack_classes`, une ou plusieurs parmi `scan`/`credential_stuffing`/`sqli`/`xss`/`path_traversal`/`upload_probe`/`api_probe`/`unknown`). Deux niveaux d'isolation, assumés et documentés comme tels :
- **Niveau 1** (fixture in-process, `isolation_level: "fixture"`, par défaut) — isolation FAIBLE explicite : même processus, même utilisateur OS que la production, acceptable uniquement parce que la fixture ne fait jamais rien d'autre que retourner un gabarit statique. Le NOM du profil doit correspondre exactement à l'une des 4 fixtures ci-dessus — sinon rejeté à la validation (`validate_active_defense_config`), pour éviter le piège d'un leurre mal nommé qui ne se déclenche alors jamais silencieusement.
- **Niveau 2** (backend réellement isolé, `isolation_level: "proxy"`) — relayé vers un processus séparé via `options.active_defense.settings.deception.decoy_zones.<nom>` (upstream `host`/`port` d'un serveur déjà en cours d'exécution, jamais créé automatiquement ; jamais lu depuis `options.reverse_proxy` — un leurre ne peut jamais accidentellement pointer vers une zone de production, vérifié à `config check`), en réutilisant le même mécanisme de reverse proxy sortant que la production (`serve_proxy()` — upstream injoignable au moment d'une requête réelle : 502 renvoyé à l'attaquant, jamais un crash).

**Écran Réglages** (TUI, Active Sécurité → Active Defense → Réglages) : configuration intégrale de tout ce qui précède — mode, activation du mode guerre, portée/actions/seuils/ralentissement/limite de requêtes, deception (comportement par défaut, CRUD des profils de leurre et des zones de leurre avec exemples de valeurs affichés dans chaque champ), IoC, stockage et journalisation — validée par les mêmes règles que la CLI avant tout enregistrement, sans jamais nécessiter d'édition manuelle de `config/omega-serve.json`. Redémarrage complet systématiquement requis après tout changement (Active Defense n'est jamais rechargé à chaud).

**Incidents et IoC** : chronologie complète par incident, extraction d'indicateurs (IP, User-Agent haché), export JSON versionné/CSV limité aux IoC partageables/rapport Markdown — chaque export accompagné d'un fichier `<export>.sha256` (format `sha256sum` standard). Export automatique à la fermeture d'un incident si `ioc.auto_export_on_close` (vrai par défaut). `active-defense purge` ferme les incidents redevenus silencieux et retire les états de menace expirés.

**Simulation** : `active-defense simulate` (CLI) et le bouton "Simuler" (TUI, écran Active Sécurité) projettent le score/niveau et expliquent chaque action qui se déclencherait — dry-run strict, aucune écriture réelle, aucun impact réseau.

Sauvegarde/restauration : `config backup --include-active-defense` inclut la base sqlite (menaces/incidents/affectations) dans l'archive — jamais de secret en clair, donc pas de `--confirm-secrets` requis contrairement à `--include-auth`.

## 12. Services et exploitation

Détection automatique systemd/OpenRC/runit (`service install/status/start/stop/restart/enable/disable/uninstall`). L'unité systemd générée applique un durcissement non négociable par défaut : `NoNewPrivileges`, `PrivateTmp`, `ProtectSystem=strict`, `ProtectHome`, `ReadWritePaths` limité à `var/`, utilisateur/groupe dédiés obligatoires, `UMask=0077`, `Restart=on-failure`. Arrêt propre sur SIGTERM (drainage des connexions en cours, délai de grâce configurable puis fermeture forcée) ; rechargement à chaud sur SIGHUP (règles WAF et zones Auth uniquement — bind/port/TLS et Active Defense jamais modifiables sans redémarrage complet).

## 13. Journaux

`var/log/access.log` (format Apache combined + `request_id`, échappement anti-injection de logs), `var/log/error.log`. Rotation par taille/nombre de fichiers conservés (`logs.rotation`).

## 14. Tests

```bash
source .venv/bin/activate
lint-imports        # verifie les 7 contrats de couches
pytest -q           # 1763 tests
ruff check .
mypy src
```

Structure : `tests/unit/` (domaine/application, doubles de test), `tests/integration/` (vrai serveur asyncio sur de vrais sockets TCP, vrai `openssl` en sous-processus, vraies commandes CLI contre un projet temporaire complet, interface interactive via l'API `Pilot` de Textual - jamais de capture d'écran), `tests/security/` (tests de propriétés `hypothesis` sur le parseur HTTP et le résolveur de chemin).

## 15. Hors périmètre

- CGI brut (FastCGI/PHP-FPM uniquement)
- mTLS (authentification client par certificat), OCSP stapling
- CA externe / CSR pour autorité tierce, distribution CRL complète
- Mode batch/surveillance récurrente — chaque commande est une action explicite
- Extraction du module WAF en projet autonome `omega-waf` (prévue, jamais commencée — conception déjà séparée en vue de cette extraction, pas de développement parallèle)
- Intégration à `omega-suite` (agit sur la machine locale, pas sur une cible distante — même exception qu'`omega-fire`)
- Active Defense : export STIX 2.1/MISP, tests de charge dédiés, intégration réelle avec les événements de ban `omega-fire` (bloquée côté `omega-fire`, qui n'expose aujourd'hui aucune surface de lecture)

---

> Omega-serv — Un serveur web solide, complet, securisé et defensif.
