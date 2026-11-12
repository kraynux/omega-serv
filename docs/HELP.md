# omega-serv 2.6.2 : aide de la ligne de commande

> Fichier généré par `tools/cli_reference.py` depuis le code : ne pas le modifier à la main.

omega-serv a deux visages :

- **sans argument**, il ouvre l'interface interactive (TUI), qui couvre tout ce qui suit et davantage ;
- **avec une commande**, il travaille en ligne de commande, sans question, pour les scripts, les
  tâches planifiées et le service système.

Toute action de l'interface reste ainsi scriptable. Les commandes sont rangées en groupes
(`config`, `waf`, `riposte`...) ; chaque groupe a ses sous-commandes.

## Lancer omega-serv

Après `install.sh`, trois façons équivalentes de lancer omega-serv :

    <dossier d'installation>/omega-serv.sh <commande>
    serv <commande>                 # alias ajouté par install.sh (nouveau terminal)
    .venv/bin/omega-serv <commande> # dans le dossier d'installation

L'option générale `--config FICHIER` se place **avant** la commande :

    serv --config /chemin/autre.json config check

## Obtenir de l'aide

    serv help                      # l'arbre complet des commandes
    serv help riposte              # une seule branche
    serv riposte actions --help    # le détail d'une commande et de ses options
    man omega-serv                 # ce manuel (installé par install.sh)

## Option générale

| Option | Rôle |
|---|---|
| `--config FICHIER` | Fichier de configuration (défaut : config/omega-serve.json de l'installation). |

## Structure des commandes

```text
serve                   Démarre le serveur au premier plan (c'est ce que lance le service système).
                        Refuse de tourner en root.
config                  Fichier de configuration : création, vérification, TLS, sauvegardes.
  init                  Crée le fichier de configuration par défaut.
  check                 Vérifie la configuration et l'environnement (chemins, droits, certificats)
                        sans démarrer.
  show                  Affiche la configuration chargée, en JSON.
  enable-tls            Active TLS dans la configuration.
  disable-tls           Désactive TLS dans la configuration.
  backup                Crée une sauvegarde : la configuration toujours, le reste selon les options
                        --include-*.
  restore               Restaure une sauvegarde.
  list-backups          Liste les sauvegardes.
profile                 Profils de configuration prêts à l'emploi.
  list                  Liste les profils disponibles.
  show                  Affiche un profil et les valeurs qu'il fixe.
  apply                 Applique un profil à la configuration (modifications et conflits affichés
                        d'abord).
option                  Modules optionnels (waf, fastcgi, active_defense, riposte...).
  list                  Liste les options et leur état.
  enable                Active une option.
  disable               Désactive une option.
simulate-request        Montre comment le serveur traiterait une requête (chemin, règles, statut,
                        en-têtes), sans l'envoyer.
waf                     Pare-feu applicatif (WAF).
  test                  Soumet une requête fictive au WAF et affiche sa décision (règles, score,
                        statut).
  never-auto-block      Affiche les réseaux jamais bannis automatiquement (lu par omega-jail).
blocklist               Adresses bannies.
  list                  Affiche les bans : réseau, origine, expiration, motif.
  add                   Bannit une adresse ou un réseau.
  remove                Lève un ban.
active-defense          Active Defense : état, simulation, purge (voir aussi threats, incidents,
                        deception).
  status                Affiche l'état : mode, mode guerre, leurres, nombre de sources suivies.
  simulate              Montre la décision qu'Active Defense prendrait pour une source, sans rien
                        écrire.
  purge                 Purge les menaces expirées, ferme les incidents redevenus calmes, supprime
                        les incidents fermés depuis plus de 90 jours.
logs                    Logs d'omega-serv.
  run-automations       Fait tourner les logs dont l'automatisation (Rotate / archivage) est à
                        échéance.
engine                  Moteur HTTP (Python ou natif).
  status                Affiche le moteur demandé, celui qui tourne et la raison d'un éventuel
                        repli.
riposte                 RIPOSTE : bans de plus en plus longs pour les récidivistes.
  run                   Lance le processus RIPOSTE au premier plan (normalement lancé par serve ;
                        utile au diagnostic).
  status                Affiche l'état de RIPOSTE (lecture seule).
  scenarios             Scénarios prêts à l'emploi.
    list                Liste les scénarios.
    show                Affiche un scénario et la politique qu'il propose.
  policies              Politiques de la configuration.
    list                Liste les politiques et leur état.
    show                Affiche une politique.
    enable              Active une politique.
    disable             Désactive une politique.
  simulate              Explique la décision de RIPOSTE pour une situation donnée, avec la
                        configuration réelle ; rien n'est appliqué.
  measure               Mesure sur les journaux ce qu'une politique aurait décidé, sans rien
                        appliquer.
  sources               Adresses mémorisées par RIPOSTE.
    list                Liste les sources mémorisées.
    show                Affiche l'historique d'une source.
    forget              Efface la mémoire d'une source : ses récidives repartent de zéro.
  decisions             Décisions prises par RIPOSTE.
    list                Liste les dernières décisions.
  actions               Bans et leurres posés par RIPOSTE.
    list                Liste les actions en cours.
    show                Affiche le détail d'une action.
    revoke              Lève une action.
    not-recidive        Ne compte pas une action dans la récidive, sans la lever.
  exemptions            Adresses exemptées de RIPOSTE.
    list                Liste les exemptions.
    remove              Retire une exemption.
  stop                  Arrêt d'urgence : RIPOSTE ne décide plus rien, même après un redémarrage,
                        jusqu'à riposte resume.
  resume                Lève l'arrêt d'urgence.
threats                 Menaces suivies par Active Defense.
  list                  Liste les sources suivies avec leur score et leur niveau.
  show                  Affiche le détail d'une source suivie.
incidents               Incidents Active Defense.
  list                  Liste les incidents.
  show                  Affiche un incident et sa chronologie.
  close                 Ferme un incident (et l'exporte si l'export automatique est activé).
  export-ioc            Exporte les indicateurs de compromission (IoC) d'un incident.
  generate-report       Écrit le rapport Markdown d'un incident.
deception               Leurres Active Defense.
  list                  Liste les sources envoyées vers un leurre.
  release               Libère une source de son leurre.
certs                   Certificats TLS (via OpenSSL).
  generate-self-signed  Génère un certificat auto-signé aux chemins de la configuration (l'ancien
                        est sauvegardé).
  generate-ca           Crée une autorité de certification locale dans secure/certificates/ca.
  generate-csr          Génère une clé et une demande de signature (CSR) à faire signer par une CA.
  sign-csr              Signe une demande de signature (CSR) avec une CA.
  import                Installe un certificat existant aux chemins de la configuration (Let's
                        Encrypt, CA d'entreprise...).
  revoke                Révoque un certificat émis par une CA locale.
  verify                Vérifie un certificat : dates, correspondance avec la clé, droits de la clé.
                        Code 1 s'il a expiré.
  show                  Affiche le détail d'un certificat (même rapport que verify).
  check-expiry          Même rapport que verify, avec une alerte si l'expiration approche.
auth                    Authentification HTTP Basic : utilisateurs et zones protégées.
  add-user              Crée un utilisateur.
  remove-user           Supprime un utilisateur.
  change-password       Change le mot de passe d'un utilisateur.
  create-zone           Protège un chemin par mot de passe.
  remove-zone           Retire la protection d'un chemin.
  list                  Liste les utilisateurs et les zones protégées.
  check-permissions     Vérifie que les fichiers des utilisateurs et des zones ne sont lisibles que
                        par leur propriétaire.
service                 Service système (systemd, OpenRC ou runit).
  status                Affiche l'état du service.
  start                 Démarre le service.
  stop                  Arrête le service.
  restart               Redémarre le service (nécessaire après une mise à jour).
  reload                Recharge sans couper : règles WAF et zones ; bind, port, TLS et moteur
                        demandent un redémarrage.
  enable                Active le démarrage automatique au boot.
  disable               Désactive le démarrage automatique au boot.
  install               Crée l'unité systemd du service (systemd seulement ; demande les droits
                        administrateur).
  permissions           Répare les droits partagés avec le service : fichiers de var/ appartenant à
                        root rendus au propriétaire du dossier, var/ et secure/auth/ partagés avec
                        le groupe du service (demande les droits administrateur).
  uninstall             Supprime l'unité du service.
audit                   Audit de sécurité.
  security              Audite l'installation : configuration, droits, TLS, service. Code 1 si
                        critique, 2 si élevé, 3 si la configuration est illisible.
declaration             Déclaration anonyme d'utilisateur (volontaire, désactivée par défaut).
  status                Affiche l'état de la déclaration.
  declare               Se déclarer utilisateur. Sans --yes, affiche seulement le message exact et
                        sa destination.
  withdraw              Retire la déclaration (supprimée à la réception).
  send-scheduled        Envoi quotidien, lancé par serve (pas à utiliser à la main).
synchro                 Liens avec les autres outils omega (omega-connect) : jeton d'installation et
                        fiche de l'instance.
  jeton                 Crée ou met à jour le jeton d'installation (var/omega-jeton.json) et
                        l'affiche en JSON.
  fiche                 Affiche la fiche de cette instance (fonctions actives, service, journaux
                        partagés), pour omega-connect.
  groupe-service        Donne (ou retire) au service de cette instance le groupe omega-synchro, pour
                        qu'il lise la zone neutre : complément systemd <service>.service.d/omega-
                        synchro.conf, l'unité n'est pas touchée. Demandé par omega-connect ; pris en
                        compte au prochain redémarrage du service.
version                 Affiche la version installée ; --check la compare à la dernière version
                        publiée sur le site.
help                    Affiche l'arbre de toutes les commandes, ou d'une branche (ex. : omega-serv
                        help riposte).
```

## Sommaire

- [`serve`](#serve) : Démarre le serveur au premier plan (c'est ce que lance le service système). Refuse de tourner en root.
- [`config`](#config) : Fichier de configuration : création, vérification, TLS, sauvegardes.
- [`profile`](#profile) : Profils de configuration prêts à l'emploi.
- [`option`](#option) : Modules optionnels (waf, fastcgi, active_defense, riposte...).
- [`simulate-request`](#simulate-request) : Montre comment le serveur traiterait une requête (chemin, règles, statut, en-têtes), sans l'envoyer.
- [`waf`](#waf) : Pare-feu applicatif (WAF).
- [`blocklist`](#blocklist) : Adresses bannies.
- [`active-defense`](#active-defense) : Active Defense : état, simulation, purge (voir aussi threats, incidents, deception).
- [`logs`](#logs) : Logs d'omega-serv.
- [`engine`](#engine) : Moteur HTTP (Python ou natif).
- [`riposte`](#riposte) : RIPOSTE : bans de plus en plus longs pour les récidivistes.
- [`threats`](#threats) : Menaces suivies par Active Defense.
- [`incidents`](#incidents) : Incidents Active Defense.
- [`deception`](#deception) : Leurres Active Defense.
- [`certs`](#certs) : Certificats TLS (via OpenSSL).
- [`auth`](#auth) : Authentification HTTP Basic : utilisateurs et zones protégées.
- [`service`](#service) : Service système (systemd, OpenRC ou runit).
- [`audit`](#audit) : Audit de sécurité.
- [`declaration`](#declaration) : Déclaration anonyme d'utilisateur (volontaire, désactivée par défaut).
- [`synchro`](#synchro) : Liens avec les autres outils omega (omega-connect) : jeton d'installation et fiche de l'instance.
- [`version`](#version) : Affiche la version installée ; --check la compare à la dernière version publiée sur le site.
- [`help`](#help) : Affiche l'arbre de toutes les commandes, ou d'une branche (ex. : omega-serv help riposte).

## serve

Démarre le serveur au premier plan (c'est ce que lance le service système). Refuse de tourner en root.

```text
omega-serv serve [--confirm-self-signed-public-bind] [--confirm-auth-without-tls]
```

| Argument | Rôle |
|---|---|
| `--confirm-self-signed-public-bind` | Accepte un certificat auto-signé sur une adresse publique. |
| `--confirm-auth-without-tls` | Accepte des zones à mot de passe sans TLS (mots de passe lisibles sur le réseau). |

## config

Fichier de configuration : création, vérification, TLS, sauvegardes.

```text
omega-serv config COMMANDE
```

### config init

Crée le fichier de configuration par défaut.

```text
omega-serv config init [--force]
```

| Argument | Rôle |
|---|---|
| `--force` | Écrase le fichier existant. |

### config check

Vérifie la configuration et l'environnement (chemins, droits, certificats) sans démarrer.

```text
omega-serv config check [--confirm-self-signed-public-bind] [--confirm-auth-without-tls]
```

| Argument | Rôle |
|---|---|
| `--confirm-self-signed-public-bind` | Accepte un certificat auto-signé sur une adresse publique. |
| `--confirm-auth-without-tls` | Accepte des zones à mot de passe sans TLS (mots de passe lisibles sur le réseau). |

### config show

Affiche la configuration chargée, en JSON.

```text
omega-serv config show
```

### config enable-tls

Active TLS dans la configuration.

```text
omega-serv config enable-tls [--cert FICHIER] [--key FICHIER] [--mode {direct,behind_proxy}]
```

| Argument | Rôle |
|---|---|
| `--cert FICHIER` | Certificat à utiliser (sinon celui déjà configuré). |
| `--key FICHIER` | Clé privée à utiliser (sinon celle déjà configurée). |
| `--mode {direct,behind_proxy}` | direct : omega-serv chiffre lui-même ; behind_proxy : derrière un reverse proxy (défaut : direct). |

### config disable-tls

Désactive TLS dans la configuration.

```text
omega-serv config disable-tls
```

### config backup

Crée une sauvegarde : la configuration toujours, le reste selon les options --include-*.

```text
omega-serv config backup [--include-waf] [--include-auth] [--include-certificates] [--include-active-defense] [--include-error-pages] [--include-preferences] [--include-logs-library] [--include-riposte] [--all] [--confirm-secrets] [--description TEXTE]
```

| Argument | Rôle |
|---|---|
| `--include-waf` | Ajoute les règles et listes du WAF. |
| `--include-auth` | Ajoute les utilisateurs et les zones protégées (secrets : demande --confirm-secrets). |
| `--include-certificates` | Ajoute les certificats et les clés TLS (secrets : demande --confirm-secrets). |
| `--include-active-defense` | Ajoute la base Active Defense. |
| `--include-error-pages` | Ajoute les pages d'erreur personnalisées. |
| `--include-preferences` | Ajoute les préférences de l'interface. |
| `--include-logs-library` | Ajoute la bibliothèque des journaux. |
| `--include-riposte` | Ajoute la base RIPOSTE. |
| `--all` | Tout sauvegarder : toutes les options --include-* (secrets compris : demande --confirm-secrets). |
| `--confirm-secrets` | Confirme l'ajout de secrets non chiffrés (hash de mots de passe, clés privées). |
| `--description TEXTE` | Texte libre enregistré avec la sauvegarde. |

### config restore

Restaure une sauvegarde.

```text
omega-serv config restore --snapshot-id ID [--stop-and-restart]
```

| Argument | Rôle |
|---|---|
| `--snapshot-id ID` | Identifiant de la sauvegarde (voir config list-backups). **(obligatoire)** |
| `--stop-and-restart` | Arrête le service, restaure, puis le redémarre (nécessaire si le service tourne). |

### config list-backups

Liste les sauvegardes.

```text
omega-serv config list-backups
```

## profile

Profils de configuration prêts à l'emploi.

```text
omega-serv profile COMMANDE
```

### profile list

Liste les profils disponibles.

```text
omega-serv profile list
```

### profile show

Affiche un profil et les valeurs qu'il fixe.

```text
omega-serv profile show NOM
```

| Argument | Rôle |
|---|---|
| `NOM` | Nom du profil (voir profile list). |

### profile apply

Applique un profil à la configuration (modifications et conflits affichés d'abord).

```text
omega-serv profile apply NOM [--dry-run] [--force]
```

| Argument | Rôle |
|---|---|
| `NOM` | Nom du profil (voir profile list). |
| `--dry-run` | Montre seulement ce qui changerait, sans rien écrire. |
| `--force` | Applique malgré des problèmes bloquants. |

## option

Modules optionnels (waf, fastcgi, active_defense, riposte...).

```text
omega-serv option COMMANDE
```

### option list

Liste les options et leur état.

```text
omega-serv option list
```

### option enable

Active une option.

Première activation du WAF : tous les packs de secure/waf/rules/ sont ajoutés, en mode log-only.

```text
omega-serv option enable NOM
```

| Argument | Rôle |
|---|---|
| `NOM` | Nom de l'option (voir option list). |

### option disable

Désactive une option.

```text
omega-serv option disable NOM
```

| Argument | Rôle |
|---|---|
| `NOM` | Nom de l'option (voir option list). |

## simulate-request

Montre comment le serveur traiterait une requête (chemin, règles, statut, en-têtes), sans l'envoyer.

```text
omega-serv simulate-request [--method METHOD] --url CHEMIN
```

| Argument | Rôle |
|---|---|
| `--method METHOD` | Méthode HTTP (défaut : GET). |
| `--url CHEMIN` | Chemin demandé, par exemple /docs/index.html. **(obligatoire)** |

## waf

Pare-feu applicatif (WAF).

```text
omega-serv waf COMMANDE
```

### waf test

Soumet une requête fictive au WAF et affiche sa décision (règles, score, statut).

```text
omega-serv waf test [--method METHOD] --path CHEMIN [--query TEXTE] [--body TEXTE] [--remote-ip IP]
```

| Argument | Rôle |
|---|---|
| `--method METHOD` | Méthode HTTP (défaut : GET). |
| `--path CHEMIN` | Chemin de la requête. **(obligatoire)** |
| `--query TEXTE` | Chaîne de requête, sans le « ? ». |
| `--body TEXTE` | Corps de la requête. |
| `--remote-ip IP` | Adresse du client simulé (défaut : 127.0.0.1). |

### waf never-auto-block

Affiche les réseaux jamais bannis automatiquement (lu par omega-jail).

```text
omega-serv waf never-auto-block
```

## blocklist

Adresses bannies.

```text
omega-serv blocklist COMMANDE
```

### blocklist list

Affiche les bans : réseau, origine, expiration, motif.

```text
omega-serv blocklist list [--format {text,json}]
```

| Argument | Rôle |
|---|---|
| `--format {text,json}` | text (défaut, traduit) ou json (pour les autres outils, jamais traduit). |

### blocklist add

Bannit une adresse ou un réseau.

```text
omega-serv blocklist add --network RESEAU --reason TEXTE [--duration-seconds SECONDES] [--confirm-permanent] [--origin OUTIL]
```

| Argument | Rôle |
|---|---|
| `--network RESEAU` | Adresse IP ou réseau CIDR, par exemple 203.0.113.7 ou 203.0.113.0/24. **(obligatoire)** |
| `--reason TEXTE` | Motif du ban. **(obligatoire)** |
| `--duration-seconds SECONDES` | Durée du ban. Sans durée, le ban est permanent et demande --confirm-permanent. |
| `--confirm-permanent` | Confirme un ban permanent. |
| `--origin OUTIL` | Outil qui pose le ban (ex. omega-fire) : lui seul pourra le lever avec --origin. |

### blocklist remove

Lève un ban.

```text
omega-serv blocklist remove --network RESEAU [--origin OUTIL]
```

| Argument | Rôle |
|---|---|
| `--network RESEAU` | Adresse ou réseau, tel qu'affiché par blocklist list. **(obligatoire)** |
| `--origin OUTIL` | Ne lève le ban que s'il a été posé avec cette origine. |

## active-defense

Active Defense : état, simulation, purge (voir aussi threats, incidents, deception).

```text
omega-serv active-defense COMMANDE
```

### active-defense status

Affiche l'état : mode, mode guerre, leurres, nombre de sources suivies.

```text
omega-serv active-defense status
```

### active-defense simulate

Montre la décision qu'Active Defense prendrait pour une source, sans rien écrire.

```text
omega-serv active-defense simulate --ip IP [--path CHEMIN] [--user-agent TEXTE] [--attack-class CLASSE] [--score POINTS]
```

| Argument | Rôle |
|---|---|
| `--ip IP` | Adresse de la source simulée. **(obligatoire)** |
| `--path CHEMIN` | Chemin observé (défaut : /). |
| `--user-agent TEXTE` | User-Agent de la source. |
| `--attack-class CLASSE` | Classe d'attaque (défaut : scan ; liste affichée si inconnue). |
| `--score POINTS` | Points ajoutés au score de menace (défaut : 10). |

### active-defense purge

Purge les menaces expirées, ferme les incidents redevenus calmes, supprime les incidents fermés depuis plus de 90 jours.

```text
omega-serv active-defense purge
```

## logs

Logs d'omega-serv.

```text
omega-serv logs COMMANDE
```

### logs run-automations

Fait tourner les logs dont l'automatisation (Rotate / archivage) est à échéance.

Lancée chaque nuit par le timer systemd ou la ligne crontab installés par l'interface.

```text
omega-serv logs run-automations
```

## engine

Moteur HTTP (Python ou natif).

```text
omega-serv engine COMMANDE
```

### engine status

Affiche le moteur demandé, celui qui tourne et la raison d'un éventuel repli.

```text
omega-serv engine status
```

## riposte

RIPOSTE : bans de plus en plus longs pour les récidivistes.

```text
omega-serv riposte COMMANDE
```

### riposte run

Lance le processus RIPOSTE au premier plan (normalement lancé par serve ; utile au diagnostic).

```text
omega-serv riposte run
```

### riposte status

Affiche l'état de RIPOSTE (lecture seule).

```text
omega-serv riposte status
```

### riposte scenarios

Scénarios prêts à l'emploi.

```text
omega-serv riposte scenarios COMMANDE
```

### riposte scenarios list

Liste les scénarios.

```text
omega-serv riposte scenarios list
```

### riposte scenarios show

Affiche un scénario et la politique qu'il propose.

```text
omega-serv riposte scenarios show ID
```

| Argument | Rôle |
|---|---|
| `ID` | Identifiant du scénario (voir riposte scenarios list). |

### riposte policies

Politiques de la configuration.

```text
omega-serv riposte policies COMMANDE
```

### riposte policies list

Liste les politiques et leur état.

```text
omega-serv riposte policies list
```

### riposte policies show

Affiche une politique.

```text
omega-serv riposte policies show ID
```

| Argument | Rôle |
|---|---|
| `ID` | Identifiant de la politique (voir riposte policies list). |

### riposte policies enable

Active une politique.

```text
omega-serv riposte policies enable ID
```

| Argument | Rôle |
|---|---|
| `ID` | Identifiant de la politique (voir riposte policies list). |

### riposte policies disable

Désactive une politique.

```text
omega-serv riposte policies disable ID [--revoke]
```

| Argument | Rôle |
|---|---|
| `ID` | Identifiant de la politique (voir riposte policies list). |
| `--revoke` | Lève aussi ses actions en cours. |

### riposte simulate

Explique la décision de RIPOSTE pour une situation donnée, avec la configuration réelle ; rien n'est appliqué.

```text
omega-serv riposte simulate --ip IP [--class CLASSE] [--level {normal,suspicious,hostile,contained}] [--returns N] [--decoy-hits N]
```

| Argument | Rôle |
|---|---|
| `--ip IP` | Adresse de la source. **(obligatoire)** |
| `--class CLASSE` | Classe d'attaque (défaut : scan). |
| `--level {normal,suspicious,hostile,contained}` | Niveau de menace Active Defense de la source. |
| `--returns N` | Nombre de retours de la source (défaut : 1). |
| `--decoy-hits N` | Nombre de leurres touchés (défaut : 0). |

### riposte measure

Mesure sur les journaux ce qu'une politique aurait décidé, sans rien appliquer.

```text
omega-serv riposte measure ID [--days JOURS]
```

| Argument | Rôle |
|---|---|
| `ID` | Politique de la configuration, ou scenario:<id> pour mesurer un scénario avant de l'ajouter. |
| `--days JOURS` | Période mesurée en jours (défaut : 7 ; 0 = tout le journal). |

### riposte sources

Adresses mémorisées par RIPOSTE.

```text
omega-serv riposte sources COMMANDE
```

### riposte sources list

Liste les sources mémorisées.

```text
omega-serv riposte sources list [--limit N]
```

| Argument | Rôle |
|---|---|
| `--limit N` | Nombre maximal de lignes (défaut : 50). |

### riposte sources show

Affiche l'historique d'une source.

```text
omega-serv riposte sources show IP
```

| Argument | Rôle |
|---|---|
| `IP` | Adresse de la source. |

### riposte sources forget

Efface la mémoire d'une source : ses récidives repartent de zéro.

```text
omega-serv riposte sources forget IP
```

| Argument | Rôle |
|---|---|
| `IP` | Adresse de la source. |

### riposte decisions

Décisions prises par RIPOSTE.

```text
omega-serv riposte decisions COMMANDE
```

### riposte decisions list

Liste les dernières décisions.

```text
omega-serv riposte decisions list [--limit N] [--ip IP] [--explain]
```

| Argument | Rôle |
|---|---|
| `--limit N` | Nombre maximal de lignes (défaut : 50). |
| `--ip IP` | Seulement cette adresse. |
| `--explain` | Détaille le raisonnement de chaque décision. |

### riposte actions

Bans et leurres posés par RIPOSTE.

Une commande est exécutée par le processus RIPOSTE en moins d'une seconde, ou à son prochain démarrage s'il est arrêté.

```text
omega-serv riposte actions COMMANDE
```

### riposte actions list

Liste les actions en cours.

```text
omega-serv riposte actions list [--finished] [--ip IP] [--limit N]
```

| Argument | Rôle |
|---|---|
| `--finished` | Liste les actions terminées à la place. |
| `--ip IP` | Seulement cette adresse. |
| `--limit N` | Nombre maximal de lignes (défaut : 50). |

### riposte actions show

Affiche le détail d'une action.

```text
omega-serv riposte actions show ID
```

| Argument | Rôle |
|---|---|
| `ID` | Identifiant de l'action (voir riposte actions list). |

### riposte actions revoke

Lève une action.

```text
omega-serv riposte actions revoke ID [--exempt {24h,7d,forever}] [--not-recidive]
```

| Argument | Rôle |
|---|---|
| `ID` | Identifiant de l'action (voir riposte actions list). |
| `--exempt {24h,7d,forever}` | Exempte aussi l'adresse : 24 h, 7 jours ou jusqu'à levée manuelle (forever). |
| `--not-recidive` | Ne compte pas cette action dans la récidive. |

### riposte actions not-recidive

Ne compte pas une action dans la récidive, sans la lever.

```text
omega-serv riposte actions not-recidive ID
```

| Argument | Rôle |
|---|---|
| `ID` | Identifiant de l'action (voir riposte actions list). |

### riposte exemptions

Adresses exemptées de RIPOSTE.

```text
omega-serv riposte exemptions COMMANDE
```

### riposte exemptions list

Liste les exemptions.

```text
omega-serv riposte exemptions list
```

### riposte exemptions remove

Retire une exemption.

```text
omega-serv riposte exemptions remove RESEAU
```

| Argument | Rôle |
|---|---|
| `RESEAU` | Adresse ou réseau exempté. |

### riposte stop

Arrêt d'urgence : RIPOSTE ne décide plus rien, même après un redémarrage, jusqu'à riposte resume.

```text
omega-serv riposte stop [--revoke]
```

| Argument | Rôle |
|---|---|
| `--revoke` | Lève aussi toutes les actions en cours. |

### riposte resume

Lève l'arrêt d'urgence.

```text
omega-serv riposte resume
```

## threats

Menaces suivies par Active Defense.

```text
omega-serv threats COMMANDE
```

### threats list

Liste les sources suivies avec leur score et leur niveau.

```text
omega-serv threats list [--level {normal,suspicious,hostile,contained}]
```

| Argument | Rôle |
|---|---|
| `--level {normal,suspicious,hostile,contained}` | Seulement ce niveau. |

### threats show

Affiche le détail d'une source suivie.

```text
omega-serv threats show SOURCE
```

| Argument | Rôle |
|---|---|
| `SOURCE` | Identifiant de la source, tel qu'affiché par threats list. |

## incidents

Incidents Active Defense.

```text
omega-serv incidents COMMANDE
```

### incidents list

Liste les incidents.

```text
omega-serv incidents list [--status {open,closed}] [--since-hours HEURES]
```

| Argument | Rôle |
|---|---|
| `--status {open,closed}` | Seulement les incidents ouverts (open) ou fermés (closed). |
| `--since-hours HEURES` | Seulement les incidents des N dernières heures. |

### incidents show

Affiche un incident et sa chronologie.

```text
omega-serv incidents show ID
```

| Argument | Rôle |
|---|---|
| `ID` | Identifiant de l'incident (voir incidents list). |

### incidents close

Ferme un incident (et l'exporte si l'export automatique est activé).

```text
omega-serv incidents close ID
```

| Argument | Rôle |
|---|---|
| `ID` | Identifiant de l'incident (voir incidents list). |

### incidents export-ioc

Exporte les indicateurs de compromission (IoC) d'un incident.

```text
omega-serv incidents export-ioc ID [--format FORMATS]
```

| Argument | Rôle |
|---|---|
| `ID` | Identifiant de l'incident (voir incidents list). |
| `--format FORMATS` | Un ou plusieurs formats séparés par des virgules : json, csv, stix, misp (défaut : json). |

### incidents generate-report

Écrit le rapport Markdown d'un incident.

```text
omega-serv incidents generate-report ID
```

| Argument | Rôle |
|---|---|
| `ID` | Identifiant de l'incident (voir incidents list). |

## deception

Leurres Active Defense.

```text
omega-serv deception COMMANDE
```

### deception list

Liste les sources envoyées vers un leurre.

```text
omega-serv deception list
```

### deception release

Libère une source de son leurre.

```text
omega-serv deception release --subject SOURCE
```

| Argument | Rôle |
|---|---|
| `--subject SOURCE` | Identifiant de la source, tel qu'affiché par deception list. **(obligatoire)** |

## certs

Certificats TLS (via OpenSSL).

```text
omega-serv certs COMMANDE
```

### certs generate-self-signed

Génère un certificat auto-signé aux chemins de la configuration (l'ancien est sauvegardé).

```text
omega-serv certs generate-self-signed --cn NOM [--org TEXTE] [--ou TEXTE] [--city TEXTE] [--region TEXTE] [--country CODE] [--san-dns NOM ...] [--san-ip IP ...] [--days JOURS] [--key-type {rsa2048,rsa4096,ecdsa-p256,ecdsa-p384}] [--password MOT-DE-PASSE]
```

| Argument | Rôle |
|---|---|
| `--cn NOM` | Nom commun : le nom de domaine principal. **(obligatoire)** |
| `--org TEXTE` | Organisation (défaut : OMEGA-SERV). |
| `--ou TEXTE` | Service ou département. |
| `--city TEXTE` | Ville. |
| `--region TEXTE` | Région. |
| `--country CODE` | Pays, code à deux lettres (FR, BE...). |
| `--san-dns NOM ...` | Noms de domaine supplémentaires couverts par le certificat. |
| `--san-ip IP ...` | Adresses IP couvertes par le certificat. |
| `--days JOURS` | Validité en jours (défaut : 365). |
| `--key-type {rsa2048,rsa4096,ecdsa-p256,ecdsa-p384}` | Type de clé (défaut : rsa2048). |
| `--password MOT-DE-PASSE` | Chiffre la clé privée avec ce mot de passe (facultatif). |

### certs generate-ca

Crée une autorité de certification locale dans secure/certificates/ca.

```text
omega-serv certs generate-ca --cn NOM [--org TEXTE] [--ou TEXTE] [--city TEXTE] [--region TEXTE] [--country CODE] [--days JOURS] [--key-type {rsa2048,rsa4096,ecdsa-p256,ecdsa-p384}] [--password MOT-DE-PASSE]
```

| Argument | Rôle |
|---|---|
| `--cn NOM` | Nom de l'autorité de certification. **(obligatoire)** |
| `--org TEXTE` | Organisation (défaut : OMEGA-SERV). |
| `--ou TEXTE` | Service ou département. |
| `--city TEXTE` | Ville. |
| `--region TEXTE` | Région. |
| `--country CODE` | Pays, code à deux lettres (FR, BE...). |
| `--days JOURS` | Validité en jours (défaut : 3650). |
| `--key-type {rsa2048,rsa4096,ecdsa-p256,ecdsa-p384}` | Type de clé (défaut : rsa4096). |
| `--password MOT-DE-PASSE` | Mot de passe de la clé de CA ; sans cette option, il est demandé deux fois au clavier (conseillé). |

### certs generate-csr

Génère une clé et une demande de signature (CSR) à faire signer par une CA.

```text
omega-serv certs generate-csr --cn NOM [--org TEXTE] [--ou TEXTE] [--city TEXTE] [--region TEXTE] [--country CODE] [--san-dns NOM ...] [--san-ip IP ...] [--key-type {rsa2048,rsa4096,ecdsa-p256,ecdsa-p384}] --key-out FICHIER --csr-out FICHIER
```

| Argument | Rôle |
|---|---|
| `--cn NOM` | Nom commun : le nom de domaine principal. **(obligatoire)** |
| `--org TEXTE` | Organisation (défaut : OMEGA-SERV). |
| `--ou TEXTE` | Service ou département. |
| `--city TEXTE` | Ville. |
| `--region TEXTE` | Région. |
| `--country CODE` | Pays, code à deux lettres (FR, BE...). |
| `--san-dns NOM ...` | Noms de domaine supplémentaires couverts par le certificat. |
| `--san-ip IP ...` | Adresses IP couvertes par le certificat. |
| `--key-type {rsa2048,rsa4096,ecdsa-p256,ecdsa-p384}` | Type de clé (défaut : rsa2048). |
| `--key-out FICHIER` | Clé privée à créer. **(obligatoire)** |
| `--csr-out FICHIER` | Demande de signature à créer. **(obligatoire)** |

### certs sign-csr

Signe une demande de signature (CSR) avec une CA.

```text
omega-serv certs sign-csr --csr FICHIER --ca-key FICHIER --ca-cert FICHIER [--ca-key-password MOT-DE-PASSE] [--days JOURS] --out FICHIER [--fullchain-out FICHIER]
```

| Argument | Rôle |
|---|---|
| `--csr FICHIER` | Demande de signature à signer. **(obligatoire)** |
| `--ca-key FICHIER` | Clé privée de la CA. **(obligatoire)** |
| `--ca-cert FICHIER` | Certificat de la CA. **(obligatoire)** |
| `--ca-key-password MOT-DE-PASSE` | Mot de passe de la clé de CA (sinon demandé au clavier, conseillé). |
| `--days JOURS` | Validité en jours (défaut : 365). |
| `--out FICHIER` | Certificat signé à écrire. **(obligatoire)** |
| `--fullchain-out FICHIER` | Écrit aussi la chaîne complète (certificat puis CA). |

### certs import

Installe un certificat existant aux chemins de la configuration (Let's Encrypt, CA d'entreprise...).

```text
omega-serv certs import --key FICHIER --cert FICHIER [--chain FICHIER]
```

| Argument | Rôle |
|---|---|
| `--key FICHIER` | Clé privée. **(obligatoire)** |
| `--cert FICHIER` | Certificat. **(obligatoire)** |
| `--chain FICHIER` | Chaîne des certificats intermédiaires (facultatif). |

### certs revoke

Révoque un certificat émis par une CA locale.

```text
omega-serv certs revoke --cert FICHIER --ca-key FICHIER --ca-cert FICHIER [--ca-key-password MOT-DE-PASSE]
```

| Argument | Rôle |
|---|---|
| `--cert FICHIER` | Certificat à révoquer. **(obligatoire)** |
| `--ca-key FICHIER` | Clé privée de la CA. **(obligatoire)** |
| `--ca-cert FICHIER` | Certificat de la CA. **(obligatoire)** |
| `--ca-key-password MOT-DE-PASSE` | Mot de passe de la clé de CA (sinon demandé au clavier, conseillé). |

### certs verify

Vérifie un certificat : dates, correspondance avec la clé, droits de la clé. Code 1 s'il a expiré.

```text
omega-serv certs verify [--cert FICHIER]
```

| Argument | Rôle |
|---|---|
| `--cert FICHIER` | Certificat à lire (défaut : celui de la configuration). |

### certs show

Affiche le détail d'un certificat (même rapport que verify).

```text
omega-serv certs show [--cert FICHIER]
```

| Argument | Rôle |
|---|---|
| `--cert FICHIER` | Certificat à lire (défaut : celui de la configuration). |

### certs check-expiry

Même rapport que verify, avec une alerte si l'expiration approche.

```text
omega-serv certs check-expiry [--cert FICHIER] [--warn-days JOURS]
```

| Argument | Rôle |
|---|---|
| `--cert FICHIER` | Certificat à lire (défaut : celui de la configuration). |
| `--warn-days JOURS` | Seuil d'alerte en jours (défaut : 30). |

## auth

Authentification HTTP Basic : utilisateurs et zones protégées.

```text
omega-serv auth COMMANDE
```

### auth add-user

Crée un utilisateur.

```text
omega-serv auth add-user --username NOM [--password MOT-DE-PASSE]
```

| Argument | Rôle |
|---|---|
| `--username NOM` | Nom d'utilisateur. **(obligatoire)** |
| `--password MOT-DE-PASSE` | Mot de passe (sinon demandé au clavier, conseillé : il resterait dans l'historique). |

### auth remove-user

Supprime un utilisateur.

```text
omega-serv auth remove-user --username NOM
```

| Argument | Rôle |
|---|---|
| `--username NOM` | Nom d'utilisateur. **(obligatoire)** |

### auth change-password

Change le mot de passe d'un utilisateur.

```text
omega-serv auth change-password --username NOM [--password MOT-DE-PASSE]
```

| Argument | Rôle |
|---|---|
| `--username NOM` | Nom d'utilisateur. **(obligatoire)** |
| `--password MOT-DE-PASSE` | Mot de passe (sinon demandé au clavier, conseillé : il resterait dans l'historique). |

### auth create-zone

Protège un chemin par mot de passe.

```text
omega-serv auth create-zone --path-prefix CHEMIN --realm TEXTE --allowed-users NOM ... [--allow-methods METHODE ...]
```

| Argument | Rôle |
|---|---|
| `--path-prefix CHEMIN` | Début de chemin protégé, par exemple /admin. **(obligatoire)** |
| `--realm TEXTE` | Nom affiché par le navigateur dans la demande de connexion. **(obligatoire)** |
| `--allowed-users NOM ...` | Utilisateurs autorisés dans la zone. **(obligatoire)** |
| `--allow-methods METHODE ...` | Seules ces méthodes HTTP sont acceptées dans la zone (défaut : toutes celles que le serveur autorise). |

### auth remove-zone

Retire la protection d'un chemin.

```text
omega-serv auth remove-zone --path-prefix CHEMIN
```

| Argument | Rôle |
|---|---|
| `--path-prefix CHEMIN` | Début de chemin protégé, par exemple /admin. **(obligatoire)** |

### auth list

Liste les utilisateurs et les zones protégées.

```text
omega-serv auth list
```

### auth check-permissions

Vérifie que les fichiers des utilisateurs et des zones ne sont lisibles que par leur propriétaire.

```text
omega-serv auth check-permissions
```

## service

Service système (systemd, OpenRC ou runit).

```text
omega-serv service COMMANDE
```

### service status

Affiche l'état du service.

```text
omega-serv service status [--service-name NOM]
```

| Argument | Rôle |
|---|---|
| `--service-name NOM` | Nom du service (défaut : omega-serv). |

### service start

Démarre le service.

```text
omega-serv service start [--service-name NOM]
```

| Argument | Rôle |
|---|---|
| `--service-name NOM` | Nom du service (défaut : omega-serv). |

### service stop

Arrête le service.

```text
omega-serv service stop [--service-name NOM]
```

| Argument | Rôle |
|---|---|
| `--service-name NOM` | Nom du service (défaut : omega-serv). |

### service restart

Redémarre le service (nécessaire après une mise à jour).

```text
omega-serv service restart [--service-name NOM]
```

| Argument | Rôle |
|---|---|
| `--service-name NOM` | Nom du service (défaut : omega-serv). |

### service reload

Recharge sans couper : règles WAF et zones ; bind, port, TLS et moteur demandent un redémarrage.

```text
omega-serv service reload [--service-name NOM]
```

| Argument | Rôle |
|---|---|
| `--service-name NOM` | Nom du service (défaut : omega-serv). |

### service enable

Active le démarrage automatique au boot.

```text
omega-serv service enable [--service-name NOM]
```

| Argument | Rôle |
|---|---|
| `--service-name NOM` | Nom du service (défaut : omega-serv). |

### service disable

Désactive le démarrage automatique au boot.

```text
omega-serv service disable [--service-name NOM]
```

| Argument | Rôle |
|---|---|
| `--service-name NOM` | Nom du service (défaut : omega-serv). |

### service install

Crée l'unité systemd du service (systemd seulement ; demande les droits administrateur).

```text
omega-serv service install [--service-name NOM] [--description TEXTE] [--python-executable FICHIER] [--user NOM] [--group NOM] [--stop-timeout-seconds SECONDES] [--unit-path FICHIER]
```

| Argument | Rôle |
|---|---|
| `--service-name NOM` | Nom du service (défaut : omega-serv). |
| `--description TEXTE` | Description de l'unité (défaut : OMEGA-SERV web server). |
| `--python-executable FICHIER` | Python à utiliser (défaut : celui du .venv de l'installation). |
| `--user NOM` | Compte système qui fait tourner le service (défaut : omega-serv). |
| `--group NOM` | Groupe du service (défaut : omega-serv). |
| `--stop-timeout-seconds SECONDES` | Délai laissé à l'arrêt avant de forcer (défaut : 15). |
| `--unit-path FICHIER` | Fichier d'unité (défaut : /etc/systemd/system/<nom>.service). |

### service permissions

Répare les droits partagés avec le service : fichiers de var/ appartenant à root rendus au propriétaire du dossier, var/ et secure/auth/ partagés avec le groupe du service (demande les droits administrateur).

```text
omega-serv service permissions [--service-name NOM] [--group NOM]
```

| Argument | Rôle |
|---|---|
| `--service-name NOM` | Nom du service (défaut : omega-serv). |
| `--group NOM` | Groupe du service (défaut : celui de son unité, sinon omega-serv). |

### service uninstall

Supprime l'unité du service.

```text
omega-serv service uninstall [--service-name NOM] [--unit-path FICHIER]
```

| Argument | Rôle |
|---|---|
| `--service-name NOM` | Nom du service (défaut : omega-serv). |
| `--unit-path FICHIER` | Fichier d'unité (défaut : /etc/systemd/system/<nom>.service). |

## audit

Audit de sécurité.

```text
omega-serv audit COMMANDE
```

### audit security

Audite l'installation : configuration, droits, TLS, service. Code 1 si critique, 2 si élevé, 3 si la configuration est illisible.

```text
omega-serv audit security [--format {text,json}] [--min-severity {critical,high,medium,low,info}] [--service-name NOM] [--unit-path FICHIER] [--confirm-self-signed-public-bind] [--confirm-auth-without-tls]
```

| Argument | Rôle |
|---|---|
| `--format {text,json}` | Format du rapport (défaut : text). |
| `--min-severity {critical,high,medium,low,info}` | N'affiche que ce niveau et les plus graves (défaut : info). |
| `--service-name NOM` | Nom du service (défaut : omega-serv). |
| `--unit-path FICHIER` | Fichier d'unité (défaut : /etc/systemd/system/<nom>.service). |
| `--confirm-self-signed-public-bind` | Accepte un certificat auto-signé sur une adresse publique. |
| `--confirm-auth-without-tls` | Accepte des zones à mot de passe sans TLS (mots de passe lisibles sur le réseau). |

## declaration

Déclaration anonyme d'utilisateur (volontaire, désactivée par défaut).

```text
omega-serv declaration COMMANDE
```

### declaration status

Affiche l'état de la déclaration.

```text
omega-serv declaration status
```

### declaration declare

Se déclarer utilisateur. Sans --yes, affiche seulement le message exact et sa destination.

```text
omega-serv declaration declare --mode {unique,quotidien} [--continent CODE] [--pays CODE] [--yes]
```

| Argument | Rôle |
|---|---|
| `--mode {unique,quotidien}` | unique : une seule fois ; quotidien : chaque jour, envoyé par le serveur. **(obligatoire)** |
| `--continent CODE` | Continent (facultatif) : AF, AN, AS, EU, NA, OC, SA ou autre. |
| `--pays CODE` | Pays (facultatif) : code à deux lettres (FR, BE...) ou autre. |
| `--yes` | Confirme l'envoi. |

### declaration withdraw

Retire la déclaration (supprimée à la réception).

```text
omega-serv declaration withdraw
```

### declaration send-scheduled

Envoi quotidien, lancé par serve (pas à utiliser à la main).

```text
omega-serv declaration send-scheduled
```

## synchro

Liens avec les autres outils omega (omega-connect) : jeton d'installation et fiche de l'instance.

```text
omega-serv synchro COMMANDE
```

### synchro jeton

Crée ou met à jour le jeton d'installation (var/omega-jeton.json) et l'affiche en JSON.

Lancée par install.sh et à chaque ouverture de l'interface. Jamais en root.

```text
omega-serv synchro jeton
```

### synchro fiche

Affiche la fiche de cette instance (fonctions actives, service, journaux partagés), pour omega-connect.

```text
omega-serv synchro fiche [--format {json}]
```

| Argument | Rôle |
|---|---|
| `--format {json}` | Format de sortie : json seulement (non traduit, versionné). |

### synchro groupe-service

Donne (ou retire) au service de cette instance le groupe omega-synchro, pour qu'il lise la zone neutre : complément systemd <service>.service.d/omega-synchro.conf, l'unité n'est pas touchée. Demandé par omega-connect ; pris en compte au prochain redémarrage du service.

```text
omega-serv synchro groupe-service ACTION [--service-name NOM]
```

| Argument | Rôle |
|---|---|
| `ACTION` | ajouter ou retirer. |
| `--service-name NOM` | Nom du service (défaut : celui de cette instance). |

## version

Affiche la version installée ; --check la compare à la dernière version publiée sur le site.

```text
omega-serv version [--check]
```

| Argument | Rôle |
|---|---|
| `--check` | Lit la liste des versions publiées (download/sha.txt du site) ; rien n'est envoyé. |

## help

Affiche l'arbre de toutes les commandes, ou d'une branche (ex. : omega-serv help riposte).

```text
omega-serv help COMMANDE ...
```

| Argument | Rôle |
|---|---|
| `COMMANDE ...` | Branche à afficher (facultatif). |

## Fichiers

Chemins relatifs au dossier d'installation.

| Chemin | Contenu |
|---|---|
| `config/omega-serve.json` | Configuration principale (créée par `config init`). |
| `config/profiles/` | Profils prêts à l'emploi (`profile list`). |
| `secure/auth/` | Utilisateurs et zones protégées (droits 600). |
| `secure/certificates/` | Certificats et clés TLS, autorité de certification locale (`ca/`). |
| `secure/waf/` | Règles du WAF et scripts Magnet. |
| `var/log/` | Journaux : accès, erreurs, alertes du WAF. |
| `var/lib/` | État écrit par le serveur : liste des bans, bases Active Defense et RIPOSTE. |
| `var/backups/` | Sauvegardes (`config backup`) et anciens certificats. |
| `var/exports/` | Exports d'incidents (IoC, rapports). |
| `var/run/omega-serv.pid` | PID du serveur en marche. |
| `webroot/` | Le site servi. |

## Variables d'environnement

| Variable | Effet |
|---|---|
| `OMEGA_SERV_LANG` | Langue de l'interface pour ce lancement seulement (ex. `OMEGA_SERV_LANG=fr serv`). Sans effet sur `serve`, dont les messages restent en français. |
| `DO_NOT_TRACK` | Toute valeur autre que 0 (ex. `DO_NOT_TRACK=1`) : aucun envoi automatique de la déclaration anonyme, même avec l'accord donné. |

## Signaux (serveur en marche)

| Signal | Effet |
|---|---|
| `SIGHUP` | Recharge les règles WAF et les zones protégées sans couper (= `service reload`). Bind, port, TLS et moteur demandent un redémarrage. |
| `SIGTERM, SIGINT` | Arrêt propre : les connexions en cours se terminent dans le délai de grâce. |

## Codes de sortie

| Code | Sens |
|---|---|
| 0 | Succès. |
| 1 | Erreur (configuration invalide, élément introuvable, action refusée...). Pour `certs verify`/`show`/`check-expiry` : certificat expiré. |
| 2 | Erreur d'utilisation (commande ou option inconnue). Pour `audit security` : problème de niveau élevé. |
| 3 | `audit security` : configuration illisible. |

`audit security` renvoie 1 dès qu'un problème critique est trouvé.

## Exemples

Vérifier la configuration avant un redémarrage :

    serv config check

Tester une URL suspecte contre le WAF :

    serv waf test --path /index.php --query 'q=<script>alert(1)</script>'

Bannir une adresse pendant une heure :

    serv blocklist add --network 203.0.113.7 --reason scan --duration-seconds 3600

Tout sauvegarder, secrets compris :

    serv config backup --all --confirm-secrets --description "avant mise à jour"

Voir les dernières décisions de RIPOSTE, expliquées :

    serv riposte decisions list --limit 10 --explain

Audit de sécurité en JSON pour un script :

    serv audit security --format json --min-severity high

## Voir aussi

`docs/guide.md` (guide complet), `README.md`, la touche F1 dans l'interface.
