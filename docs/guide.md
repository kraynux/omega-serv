<!-- Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE) -->
<!-- Version Markdown de guide.html, generee pour l'archive distribuee
     (la page HTML depend de CSS/JS serveur, illisible hors serveur). -->

# Guide complet d'Omega-Serv

## 📖 À propos de ce guide complet

Ce document compile **intégralement** deux guides complémentaires : le **guide de référence** (philosophie du projet, concepts transverses, scénarios d'exploitation et bonnes pratiques) et le **guide d'aide intégré** (fiches écran par écran, FAQ orientée pièges réels). Rien n'a été résumé : vous y trouverez tout le contenu des deux documents originaux, dans le même style.

Utilisez les sections dépliables pour naviguer. Chaque écran de l'application a aussi sa propre aide contextuelle accessible avec `F1`, et la touche `a` ouvre le guide intégré complet.

---

# 📚 Partie 1 — Guide de référence

Philosophie du projet, concepts transverses, scénarios d'exploitation et bonnes pratiques.

## 🎯 Présentation du projet — 5 fiches

Comprendre ce qu'est Omega-Serv, pour qui il a été conçu, et comment il se situe.

### Objectif du guide et du projet

Omega-Serv est un serveur HTTP/1.1 autonome, destiné principalement au contenu statique et, en option, à PHP-FPM/FastCGI. Son objectif n'est pas de rivaliser avec les serveurs C ou Go sur la performance brute ou les charges Internet massives : il propose une **administration locale plus cohérente, accessible et défensive**.

L'administration passe par deux interfaces fonctionnellement équivalentes : une **CLI non interactive et scriptable**, ainsi qu'une **interface TUI Textual** utilisable au clavier et à la souris. La configuration ne demande pas d'éditer manuellement les fichiers de configuration ; les commandes, formulaires et assistants appliquent les validations nécessaires avant l'écriture.

### À qui s'adresse Omega-Serv

Omega-Serv est adapté aux **administrateurs Linux**, **développeurs** et **utilisateurs** qui veulent gérer un service HTTP local avec une interface d'administration centralisée. Il est particulièrement pertinent pour :

- Un laboratoire ou un environnement de test
- Un accès VPN
- Un petit site statique
- Un service interne
- Une petite installation PHP-FPM

> **⚠️ Pour une exposition Internet sensible**
> - Pour un trafic élevé ou une architecture distribuée, validez le comportement dans votre environnement et envisagez de placer Omega-Serv derrière un reverse proxy d'edge adapté.
> - Les fonctions de sécurité intégrées complètent une architecture défensive ; elles ne remplacent ni la segmentation réseau, ni les mises à jour, ni la supervision externe.

### Guide intégré et guide de référence

L'application inclut une **aide contextuelle** accessible avec `F1` depuis l'écran actif. La touche `a` ouvre le guide complet, sa navigation et sa FAQ ; le guide fourni le 15 octobre 2026 documente **75 écrans**.

Ce document ne remplace pas ces fiches interactives. Il fournit une vue d'ensemble, explique les concepts transverses, relie les fonctions entre elles et propose des scénarios complets d'exploitation.

### Vue fonctionnelle

Omega-Serv regroupe plusieurs domaines d'administration dans une même application :

- **Serveur HTTP** : écoute, webroot, contenu statique, alias, redirections, réécritures, listing, pages d'erreur et cache.
- **Modules d'application** : TLS, authentification HTTP Basic, FastCGI/PHP-FPM, reverse proxy sortant et zones d'upload confinées.
- **Sécurité active** : WAF, liste de blocage, limitation de débit, réputation, Active Defense, deception et incidents.
- **Exploitation** : services système, logs, rotation, statistiques, état des ressources, audits, sauvegardes et multi-instance.
- **Interfaces** : CLI pour les scripts et la répétabilité ; TUI pour l'exploration, les formulaires, les assistants et l'aide contextuelle.

### Carte de navigation

Le menu principal organise les fonctions autour d'un cycle d'administration logique : **préparer, configurer, vérifier, exploiter, observer et sauvegarder**.

| Zone | Rôle principal | Quand l'utiliser |
|---|---|---|
| Accueil | Point d'entrée et accès aux fonctions | À chaque lancement |
| Assistant premier lancement | Création guidée d'une configuration initiale | Première installation ou nouvelle instance |
| Registre des capacités | Vérification en lecture seule de l'environnement | Avant l'activation de TLS, d'un service ou d'un module |
| Profils | Choix d'une base de configuration | Pour démarrer avec un niveau adapté au contexte |
| Configuration détaillée | Paramétrage du serveur et de ses modules | Pour modifier le comportement HTTP |
| Active Sécurité | WAF et Active Defense | Pour observer, tester et appliquer des protections |
| Gestion des logs | Consultation, suivi, rotation, statistiques et archives | Pour diagnostiquer et suivre l'activité |
| Service | Installation et pilotage systemd/OpenRC/runit | Pour exploiter le serveur comme service |
| Multi-instance | Gestion de plusieurs installations séparées | Un projet ou environnement par instance |
| État & Ressources | Vue opérationnelle et métriques locales | Pour surveiller le serveur en fonctionnement |
| Audit de sécurité | Contrôles et recommandations | Avant une mise en service et régulièrement |
| Sauvegarde | Snapshots et restauration | Avant une modification importante ou une migration |
| Réglages applicatifs | Thème, rendu, exports et captures | Pour adapter l'interface, pas le serveur |

### CLI et TUI : deux interfaces, mêmes cas d'usage

La CLI et la TUI utilisent les **mêmes cas d'usage** afin d'éviter deux comportements divergents. Choisissez la CLI lorsque vous avez besoin d'automatiser, de versionner des procédures shell ou de rejouer une action de manière répétable.

Préférez la TUI lorsque vous découvrez les options, souhaitez une aide liée au contexte, voulez visualiser les logs et statistiques, ou devez remplir un formulaire avec validation guidée. Les actions sensibles et destructives demandent une confirmation explicite dans l'interface.

### Cycle d'administration conseillé

1. Créez une configuration avec l'assistant ou avec `config init`.
2. Choisissez un profil adapté au contexte, puis vérifiez le diff avant son application.
3. Activez uniquement les modules nécessaires, un par un.
4. Lancez `config check` avant de démarrer ou de modifier un service.
5. Installez un service sous un utilisateur et groupe dédiés, jamais en root.
6. Suivez les logs et l'écran État & Ressources après chaque changement significatif.
7. Exécutez régulièrement l'audit de sécurité et créez des sauvegardes avant les opérations importantes.

## 🧠 Concepts essentiels — 11 fiches

Les notions transverses qui structurent Omega-Serv et son administration.

### Profils

Les profils apportent une **base cohérente de paramètres**. Ils ne doivent pas être interprétés comme une garantie de sécurité universelle : le réseau, le contenu servi, les permissions locales et le reverse proxy éventuel restent déterminants.

| Profil | Usage visé | Intention |
|---|---|---|
| `minimal` | Démonstration ou environnement local simple | Statique seul, options désactivées |
| `standard` | Site statique ou petite production | Base raisonnable avec protections usuelles |
| `hardened` | Exposition avec moindre privilège | Bind local recommandé et restrictions renforcées |
| `development` | Développement local | Bind loopback, diagnostic facilité, jamais destiné à Internet |

> **💡 À savoir**
> Lorsqu'un profil est appliqué, Omega-Serv fusionne les valeurs sûres intégrées, le profil choisi, les options déjà activées puis les réglages utilisateur explicites. Vérifiez systématiquement le diff présenté avant l'écriture.

### Rechargement et redémarrage

Un **rechargement à chaud** applique certaines modifications sans interrompre complètement le service. Dans Omega-Serv, les règles WAF et les zones d'authentification peuvent être rechargées par `SIGHUP` ; certains changements de configuration courante sont également appliqués selon le mécanisme de service utilisé.

Un **redémarrage complet** est nécessaire pour les éléments qui modifient le socket d'écoute, TLS ou Active Defense. Après chaque enregistrement dans la TUI, l'application doit indiquer explicitement si une action est appliquée à chaud, exige un redémarrage ou ne demande aucune action.

### Durcissement HTTP

Le noyau HTTP applique des contrôles qui ne sont pas proposés comme options désactivables. Ils incluent notamment :

- La validation de l'en-tête `Host`
- Une liste explicite de méthodes autorisées
- Le rejet des ambiguïtés liées à `Content-Length` et `Transfer-Encoding`
- Le rejet de `Expect: 100-continue`

Les tailles de ligne et d'en-têtes sont limitées pendant la lecture, les en-têtes obsolètes repliés sont refusés, et les réponses reçoivent des en-têtes de sécurité ainsi qu'une CSP de base. La résolution de chemin vise à protéger le service statique contre traversal, double encodage et cas sensibles liés aux liens symboliques.

### Modules optionnels

Les modules ne sont pas activés implicitement par les profils fournis, y compris `hardened`. Leur activation est un **choix explicite**, qui doit être précédé de tests fonctionnels et suivi d'une observation des logs.

| Module | Usage | Point d'attention |
|---|---|---|
| **WAF** | Signatures, rate limiting, blocklist CIDR, réputation | Commencer en observation et tester les faux positifs |
| **TLS** | Certificat auto-signé, CA locale, ou public via Let's Encrypt/Certbot | mTLS, CA externe et OCSP stapling restent hors périmètre |
| **Authentification** | HTTP Basic par zone | Réserver à des accès adaptés et utiliser TLS |
| **FastCGI/PHP-FPM** | Exécution PHP via PHP-FPM | Vérifier les permissions et séparer `script_root` du webroot |
| **Reverse proxy sortant** | Routage vers un ou plusieurs backends HTTP/HTTPS | Contrôler les upstreams, en-têtes et vérification TLS |
| **Upload** | Zones confinées avec quotas | Définir des tailles maximales réalistes et vérifier les permissions |
| **Active Defense** | Deception, incidents, journaux enrichis et IoC | Traiter les actions comme un dispositif défensif observé et testé |

### WAF

Le WAF peut utiliser des signatures, des détections de chemins ou user-agents sensibles, des signaux d'injection, une limitation de débit, une blocklist CIDR et une logique de réputation. Son rôle est de fournir une **couche applicative supplémentaire** autour du serveur HTTP.

Le mode `log-only` est volontairement incapable de bloquer ; il sert à observer les décisions et à ajuster les règles sans impact sur les clients. Avant d'activer un comportement bloquant, utilisez le test de requête, consultez les logs et vérifiez les accès légitimes concernés.

### Active Defense

Active Defense exploite les signaux déjà produits par le WAF pour qualifier les sources et déclencher des actions défensives. Il ne remplace pas le pare-feu ni le blocage réseau : le module **observe, enrichit, ralentit, oriente vers un leurre et construit des incidents exploitables**.

Les niveaux de menace suivent une progression `normal`, `suspicious`, `hostile` et `contained`. Une source est identifiée par son IP et un hash du User-Agent ; le score décroît en l'absence de nouvel événement afin de limiter la persistance d'un contexte devenu obsolète.

### Deception

La deception peut orienter une source hostile ou contenue vers un leurre statique, par exemple `fake_admin`, `fake_cms`, `fake_api` ou `fake_secrets`. Les leurres de type `fixture` restent dans le processus et ne retournent que des gabarits fixes ; ils sont explicitement documentés comme une **isolation faible**.

Pour une isolation plus forte, utilisez une zone de leurre de type `proxy` qui pointe vers un backend distinct déjà exploité dans un processus séparé. Vérifiez toujours que le backend est joignable et distinct des zones de production : en cas d'upstream indisponible, la réponse attendue est une erreur HTTP au client, jamais un crash du serveur.

### TLS et certificats

Omega-Serv gère TLS direct via un certificat auto-signé ou une CA locale. Le certificat auto-signé convient principalement au local, au laboratoire, à un VPN ou à un environnement où les clients peuvent accepter explicitement le certificat ou faire confiance à votre CA locale.

Une CA locale permet de signer plusieurs certificats serveur à destination d'appareils dont vous contrôlez le magasin de confiance. La clé privée de l'autorité est l'élément le plus sensible : conservez-la hors des sauvegardes non chiffrées, avec des permissions restrictives et une phrase de passe adaptée.

Pour un site réellement public, l'assistant **Let's Encrypt (Certbot)** obtient un certificat reconnu par les navigateurs via le défi HTTP-01 en mode `webroot` — jamais `--standalone` (le port 80 est déjà occupé par Omega-Serv) et jamais `/etc/letsencrypt/` (tout reste sous `secure/certificates/letsencrypt/` du projet, entièrement non-privilégié). Le certificat obtenu est importé automatiquement, et l'écran **Renouvellement automatique** installe ensuite un timer systemd (ou, à défaut, une ligne crontab) qui renouvelle sans plus jamais intervenir manuellement — voir le scénario dédié et la FAQ pour le détail (DDNS, redirection de port, cas conteneur).

### Logs et monitoring

Les journaux incluent un log d'accès et un log d'erreurs. L'interface permet de consulter et suivre les fichiers, de gérer la rotation, de créer des archives et d'obtenir des statistiques telles que la répartition par code de statut, le débit, les IP uniques ou les principales IPs observées.

Le mode d'intégration `lnav` est optionnel et l'interface doit rester utilisable lorsqu'il n'est pas installé. Les automatisations de rotation enregistrées dans l'application sont **déclaratives** tant qu'un mécanisme externe — par exemple un timer systemd — n'est pas configuré pour les exécuter.

### Services système

Omega-Serv détecte systemd, OpenRC ou runit pour installer et piloter un service. L'installation doit s'effectuer avec un utilisateur et groupe dédiés ; le programme **refuse de démarrer directement comme root**.

Lorsqu'une unité systemd est générée, elle applique notamment `NoNewPrivileges`, `PrivateTmp`, `ProtectSystem=strict`, `ProtectHome`, un `UMask=0077`, des chemins d'écriture limités et un redémarrage sur échec. Vérifiez malgré tout les permissions réelles du webroot, des certificats, des journaux et des répertoires d'upload.

### Multi-instance

Une instance représente une installation séparée, avec sa configuration, son environnement Python, ses fichiers et son port. Le registre global permet d'identifier les installations connues et de basculer entre elles.

Utilisez une instance par projet ou par environnement — par exemple développement, démonstration et service interne. Ne créez pas plusieurs unités systemd pointant vers le même répertoire sous des noms différents : cela rend le statut, les redémarrages et les fichiers d'état ambigus.

### Sauvegardes

Une sauvegarde de configuration inclut la configuration de base. L'inclusion des zones d'authentification et des certificats est volontairement soumise à une confirmation supplémentaire, car ces données peuvent contenir des secrets utiles à un attaquant.

> **⚠️ À savoir**
> - Les sauvegardes **ne sont pas chiffrées par défaut**.
> - Stockez-les avec des permissions restrictives, dans un emplacement protégé, et testez périodiquement une restauration sur une instance de laboratoire.

## 🛠️ Scénarios pratiques — 9 fiches

Des parcours complets, du premier lancement à la mise en production.

### Site statique interne avec WAF

**Objectif :** publier un site statique réservé à un réseau interne ou VPN, avec une configuration initiale sûre, des logs exploitables et une première couche WAF.

1. Lancez l'assistant de premier lancement depuis la TUI, ou initialisez la configuration :

```
./omega-serv.sh config init
```

1. Choisissez le profil `standard` pour un petit site, ou `hardened` si le service doit être placé derrière un reverse proxy. Examinez le diff avant application :

```
./omega-serv.sh profile show hardened
./omega-serv.sh profile apply hardened --dry-run
```

1. Configurez le bind, le port et le webroot depuis la TUI ou les commandes correspondantes. Vérifiez que le compte de service peut lire le contenu sans droits d'écriture inutiles.
2. Activez le WAF, commencez par le mode d'observation, puis vérifiez le comportement à l'aide de requêtes simulées et des logs :

```
./omega-serv.sh option enable waf
./omega-serv.sh waf test --method GET --path /admin --remote-ip 203.0.113.1
```

1. Vérifiez la configuration avant le démarrage :

```
./omega-serv.sh config check
```

1. Installez ensuite le service sous un utilisateur dédié, démarrez-le et consultez son statut :

```
./omega-serv.sh service install --user omega-serv --group omega-serv
./omega-serv.sh service start
./omega-serv.sh service status
```

1. Depuis Gestion des logs ou État & Ressources, observez les premières requêtes, les erreurs et les codes HTTP. Ajustez les règles avant d'envisager un mode WAF bloquant.

### TLS interne avec CA locale

**Objectif :** fournir HTTPS à plusieurs appareils internes sous votre contrôle, sans dépendre d'une autorité publique.

1. Vérifiez que `openssl` est présent et que le stockage prévu pour les certificats est correctement protégé.
2. Créez une CA locale. Si aucune phrase de passe n'est fournie, le programme demande une saisie interactive avec confirmation :

```
./omega-serv.sh certs generate-ca --cn "Mon CA locale" --days 3650
```

1. Générez la clé et la CSR du serveur, en définissant les noms DNS ou IP réellement utilisés par les clients :

```
./omega-serv.sh certs generate-csr \
  --cn serveur.local \
  --san-dns serveur.local \
  --key-out server.key \
  --csr-out server.csr
```

1. Signez la CSR avec la CA locale et produisez la chaîne complète :

```
./omega-serv.sh certs sign-csr \
  --csr server.csr \
  --ca-key secure/certificates/ca/root-ca.key \
  --ca-cert secure/certificates/ca/root-ca.pem \
  --out server.pem \
  --fullchain-out fullchain.pem
```

1. Activez TLS avec le certificat et la clé correspondants depuis la TUI ou via la commande de configuration. Lancez ensuite `config check`, puis redémarrez complètement le service : un changement TLS ne relève pas du rechargement à chaud.
2. Importez uniquement le certificat public `root-ca.pem` dans le magasin de confiance des clients. Ne distribuez jamais la clé privée `root-ca.key`.

### Site public en HTTPS avec Let's Encrypt (Certbot)

**Objectif :** auto-héberger un site avec un certificat public réellement reconnu par les navigateurs, schéma DDNS → Certbot → Omega-Serv.

1. Prérequis, entièrement à votre charge, hors d'Omega-Serv : un nom de domaine géré par un service DDNS (par exemple Dynu) pointé vers votre IP publique, et les ports 80/443 redirigés depuis votre routeur/pare-feu vers cette machine.
2. Depuis `Configuration détaillée → TLS → Assistant Let's Encrypt (Certbot)`, renseignez le domaine (et éventuellement un email), laissez la case **Mode test (staging)** cochée, puis confirmez. Certbot répond au défi HTTP-01 via le webroot déjà servi par Omega-Serv (jamais `--standalone`) et le certificat est importé automatiquement.
3. Vérifiez le résultat (certificat non reconnu par les navigateurs, c'est normal en mode test), puis décochez la case et relancez la même demande pour obtenir un certificat de production.
4. Activez TLS (`Configuration détaillée → TLS → Activer / désactiver TLS`) avec les chemins déjà pré-remplis par l'import, puis redémarrez complètement le service.
5. Depuis `TLS → Renouvellement automatique (Certbot)`, cliquez sur **Configurer maintenant** : un timer systemd (ou une ligne crontab si aucun gestionnaire de service systemd n'est détecté) est installé, et renouvellera automatiquement sans plus jamais intervenir.

### WAF : observer, tester, appliquer

**Objectif :** activer une protection sans bloquer par erreur les utilisateurs légitimes.

1. Activez le module WAF depuis Active Sécurité ou via la CLI :

```
./omega-serv.sh option enable waf
```

1. Utilisez le mode `log-only` lors de la phase de calibration. Ce mode est structurellement incapable de bloquer et permet d'observer les décisions sans perturber le service.
2. Testez les règles avec `waf test` ou l'écran de test de requête. Consultez les logs WAF et le log d'accès pour comparer la décision avec le comportement attendu.
3. Ajoutez une règle personnalisée uniquement lorsque sa portée, ses faux positifs potentiels et son mode d'action sont compris. Après une modification, vérifiez si l'interface demande un rechargement ou un redémarrage.
4. Passez progressivement à un mode bloquant pour des règles validées. Surveillez les erreurs applicatives, les taux de réponses 4xx/5xx et les retours utilisateurs après chaque changement.

### Protéger les chemins sensibles (listes WAF)

**Objectif :** bloquer les sondes classiques (`.env`, `.git/`, sauvegardes, consoles d'administration…) avec une liste maintenue dans un simple fichier texte, sans jamais bannir ses propres machines.

1. Ouvrez **Active Sécurité → Custom → Ajouter**, choisissez **« CHARGER une liste de chemins (fichier) »**, puis la référence livrée `sensitive-paths-hostile` (298 chemins sans usage légitime). Les réglages conseillés se remplissent seuls ; gardez la gravité **Observation** au premier chargement.

1. Cliquez **Charger** : la copie locale est créée dans `secure/waf/rules/keywords/`, la liste est vérifiée (syntaxe, droits, conflits avec vos routes), puis la réputation et l'auto-ban sont activés avec un message. Rien n'est actif avant ce clic.

1. Laissez tourner quelques jours en Observation : chaque détection est écrite dans le journal d'alertes WAF, sans blocage ni ban. Dans l'éditeur (**Éditer la liste**), **Vérifier contre mes logs** montre les lignes qui auraient touché des requêtes réussies ; ajoutez une exception `!/chemin` en un clic.

1. Passez la liste en bloquant : **Modifier → Gravité Élevé**, récidive 2 accès en 10 min → ban 24 h. Vérifiez ensuite un chemin avec le simulateur :

```
./omega-serv.sh waf test --method GET --path /blog/.env --remote-ip 203.0.113.1
```

1. Chargez éventuellement `sensitive-paths-probe` (132 chemins de sondage, parfois servis par un vrai site) en gravité Moyen : il ne bloque jamais seul, il compte pour la récidive (5 accès en 10 min → ban 1 h).

1. Vos machines ne sont jamais bannies automatiquement : hôte local, Tailscale (`100.64.0.0/10`) et réseau local sont exemptés (`options.waf.reputation.never_auto_block`). Derrière `tailscale serve` ou un reverse proxy local, activez **Proxy de confiance** avec `127.0.0.1` pour que les visiteurs externes soient vus avec leur vraie adresse.

### Active Defense : simulation avant activation

**Objectif :** comprendre et valider la réponse défensive avant d'appliquer une action réelle.

1. Activez l'option Active Defense depuis l'écran Active Sécurité ou via la CLI :

```
./omega-serv.sh option enable active_defense
```

1. Définissez le mode, les seuils, les actions et les profils de leurre. Commencez par `monitor` afin d'observer les qualifications sans déployer une réponse active.
2. Utilisez la simulation stricte pour vérifier le score, le niveau obtenu et les actions projetées. Cette opération n'écrit pas d'état et n'a aucun impact réseau :

```
./omega-serv.sh active-defense simulate \
  --ip 203.0.113.42 \
  --path /wp-login.php \
  --attack-class scan \
  --score 40
```

1. Si vous utilisez un leurre `fixture`, limitez-le à des réponses statiques plausibles et considérez explicitement son isolation comme faible. Pour une zone `proxy`, déployez d'abord un backend de leurre isolé, distinct de la production, puis vérifiez sa disponibilité.
2. En mode `enforce`, surveillez les incidents ouverts, le journal enrichi et les exports IoC. Les exports JSON, CSV ou rapports doivent être traités comme des éléments sensibles.

### Seconde instance pour un autre projet

**Objectif :** héberger deux projets indépendants sans confondre leurs ports, services, logs ou configurations.

1. Ouvrez Multi-instance dans la TUI et lancez la création d'une instance.
2. Choisissez un répertoire distinct, non imbriqué dans l'installation existante, et un port qui n'est pas déjà utilisé.
3. Laissez l'outil créer un environnement virtuel propre et une configuration fraîche. En cas d'échec à l'étape des dépendances, vérifiez la connectivité, l'espace disque, les permissions et la version Python requise.
4. Configurez puis vérifiez la nouvelle instance indépendamment. Installez une unité de service qui cible exclusivement son répertoire et son utilisateur dédié.
5. Contrôlez le registre des instances et le statut du service avant toute bascule. Chaque instance doit conserver ses propres sauvegardes, certificats et fichiers de journalisation.

### Reverse proxy sortant

**Objectif :** exposer un chemin ou un hôte local qui relaie les requêtes vers un ou plusieurs backends HTTP/HTTPS internes, avec équilibrage round-robin et gestion des en-têtes.

1. Depuis la TUI, ouvrez **Configuration détaillée → Reverse proxy sortant**.
2. Définissez une zone, par exemple :

- `url_prefix = /api-interne/`
- Upstreams : `http://10.0.0.10:8080`, `http://10.0.0.11:8080`

1. Configurez les options : vérification TLS stricte pour les upstreams HTTPS (désactivable mais déconseillée), retrait des en-têtes hop-by-hop, écrasement systématique des `X-Forwarded-*`.
2. Si vous voulez du WebSocket, configurez une zone dédiée avec un upstream fixe pour la durée du tube, sans timeout applicatif une fois établi.
3. Vérifiez la configuration :

```
./omega-serv.sh config check
```

1. Redémarrez complètement le service. Testez depuis un client :

```
curl -i http://localhost/api-interne/health
```

1. Observez les logs d'accès et d'erreurs pour vérifier le routage, les codes HTTP et les en-têtes. Ajustez les upstreams ou les options en cas de 502/504.

### Upload confiné

**Objectif :** permettre l'envoi de fichiers sur un chemin précis, avec quotas, noms générés côté serveur et confinement strict hors du reste du webroot.

1. Depuis la TUI, ouvrez **Configuration détaillée → Upload**.
2. Créez une zone d'upload, par exemple :

- `url_prefix = /uploads/`
- `upload_root` dans un répertoire dédié, hors du webroot statique principal.
- Quota par zone (par exemple 500 Mo).
- Taille maximale par requête (`max_request_size`) cohérente avec votre usage.

1. Choisissez la stratégie de nommage : noms générés côté serveur (recommandé), extensions autorisées restreintes.
2. Vérifiez les permissions : le compte de service doit pouvoir écrire dans `upload_root` mais pas ailleurs. Le handler statique ne doit jamais pouvoir lister ou servir les sources applicatives ou les fichiers sensibles.
3. Vérifiez la configuration :

```
./omega-serv.sh config check
```

1. Redémarrez le service si nécessaire, puis testez l'upload :

```
curl -X POST -F "file=@monfichier.pdf" http://localhost/uploads/
```

1. Consultez les logs pour vérifier les réponses (200/201/413/4xx) et ajustez quotas et tailles si nécessaire.

## 🔒 Exploitation et sécurité — 4 fiches

Les bonnes pratiques à appliquer avant, pendant et après la mise en service.

### Checklist avant mise en service

- Utiliser un compte de service dédié, sans privilèges root.
- Choisir un webroot lisible mais non modifiable par le compte de service, sauf nécessité justifiée.
- Lancer `config check` avant le démarrage ou après toute modification importante.
- Exécuter `audit security` et traiter les constats critiques ou élevés.
- Mettre en place une rotation réelle des logs (logrotate ou timer systemd si les automatisations déclaratives ne sont pas exécutées automatiquement).
- Créer une sauvegarde avant les opérations sensibles et protéger les archives contenant certificats ou données d'authentification.
- Tester les règles WAF en observation avant activation du blocage.
- Valider TLS depuis un client réel (chaîne de confiance, SAN, expiration).
- Pour une exposition Internet, évaluer l'intérêt d'un reverse proxy d'edge, de restrictions réseau, de sauvegardes hors machine et d'une supervision externe.

### Audit régulier

L'audit de sécurité est **informatif** : il ne bloque pas le fonctionnement du serveur. Il rejoue certains contrôles bloquants comme constats critiques, puis évalue également des recommandations liées à TLS, CSP, méthodes HTTP, timeouts, uploads, permissions, certificats, service et taille des logs.

Exécutez-le après une installation, avant une exposition, après un changement de profil ou de TLS, et à intervalle régulier. Les codes de sortie permettent une intégration dans des scripts ou une supervision.

```
./omega-serv.sh audit security --format text --min-severity medium
```

| Code | Signification |
|---|---|
| `0` | Absence de constat critique ou élevé |
| `1` | Au moins un constat critique |
| `2` | Au moins un constat élevé sans critique |
| `3` | Erreur d'exécution |

### Sauvegarde et restauration

Créez une sauvegarde avant une migration, une régénération de certificats, un changement de module ou une modification Active Defense significative :

```
./omega-serv.sh config backup --description "avant migration"
```

L'inclusion de certificats ou de données d'authentification demande une confirmation explicite, car les archives peuvent alors contenir des secrets. Testez la restauration sur une instance de laboratoire avant de dépendre d'une sauvegarde pour un rétablissement réel.

### Limites et périmètre

Omega-Serv est conçu comme un serveur HTTP/1.1 durci, orienté administration unifiée et sécurité applicative. Il ne vise pas à couvrir tous les cas d'usage des serveurs web généralistes.

### Fonctions hors périmètre en V1

- CGI brut : seul FastCGI/PHP-FPM est supporté.
- mTLS, authentification client par certificat, OCSP stapling, CA externe et distribution CRL complète (ACME/Let's Encrypt via Certbot est disponible depuis Configuration détaillée → TLS).
- Cache HTTP partagé entre processus.
- Mode batch ou surveillance récurrente intégrée.
- Extraction du module WAF en projet autonome `omega-waf` (prévue, jamais commencée).
- Intégration à `omega-suite`.
- Active Defense : pas d'export STIX 2.1/MISP, pas de tests de charge dédiés, pas d'intégration réelle avec `omega-fire`.

### Limites de performance et de concurrence

- L'objectif n'est pas la très haute concurrence ni les gros débits d'un serveur C ou Go spécialisé.
- Python et asyncio imposent des contraintes en très haute charge ; Omega-Serv est adapté à des charges modestes à moyennes (labo, VPN, petit service interne).

### Limites de sécurité et de déploiement

- Le WAF et Active Defense sont des modules applicatifs complémentaires : ils ne remplacent pas un pare-feu réseau, un outil de prévention d'intrusion, la journalisation centralisée, une réponse à incident organisée ou les mises à jour régulières.
- TLS repose sur `openssl` en sous-processus. L'intégration ACME (Let's Encrypt) est un pont vers Certbot réel — jamais un client ACME réimplémenté — et reste limitée au défi HTTP-01/webroot (pas de DNS-01).
- Les leurres `fixture` sont explicitement documentés comme une isolation faible.

### Limites opérationnelles

- Pas de cache HTTP partagé entre processus.
- Pas de fonction de scan/audit d'une cible distante.
- Les automatisations de rotation de logs sont déclaratives tant qu'un mécanisme externe ne les exécute pas.

## 🩺 Dépannage rapide — 6 fiches

Les situations les plus souvent rencontrées — et leur résolution.

### Une modification semble sans effet

Vérifiez d'abord si l'action nécessitait un **rechargement ou un redémarrage complet**. Les changements concernant le bind, le port, TLS ou Active Defense nécessitent un redémarrage ; les zones WAF et d'authentification peuvent être rechargées à chaud selon le cas.

Exécutez `config check`, consultez les logs et vérifiez le statut du service. Dans la TUI, l'indication après enregistrement doit préciser la suite attendue.

### Le WAF est actif mais ne bloque rien

Le WAF peut être en mode `log-only`, qui ne bloque jamais par conception. Vérifiez son mode, les règles réellement activées, la portée des routes concernées et les résultats de `waf test` avant de conclure à un défaut.

### Active Defense ne semble pas agir

Active Defense dépend des signaux WAF et de seuils de qualification. Vérifiez que le module est activé, que le mode choisi n'est pas seulement `monitor`, que les scores atteignent les seuils configurés et que les profils de leurre correspondent à la classe d'attaque observée.

Utilisez toujours `active-defense simulate` avant de tester avec du trafic réel. Pour une zone de leurre en mode `proxy`, vérifiez aussi que le backend isolé est réellement joignable.

### Le certificat servi semble ancien

Une régénération, révocation ou modification TLS requiert un **redémarrage complet** du serveur. Vérifiez que la configuration pointe vers le bon certificat et la bonne clé, contrôlez les dates avec `certs check-expiry`, puis redémarrez le service.

### Les sauvegardes sont-elles chiffrées ?

Non, les sauvegardes **ne sont pas chiffrées par défaut**. Protégez-les par les permissions, le stockage, le chiffrement de votre infrastructure et des procédures de rétention adaptées, particulièrement lorsqu'elles incluent certificats ou zones d'authentification.

### L'assistant Let's Encrypt échoue (défi HTTP-01)

Dans l'ordre à vérifier : le port 80 n'est pas réellement joignable depuis Internet (redirection de port manquante/incorrecte sur le routeur, ou un autre service occupe déjà ce port) ; le domaine ne pointe pas encore vers cette IP (DNS/DDNS pas encore propagé — vérifiez avec `dig`/`nslookup` depuis une machine externe) ; ou vous êtes en mode test (staging, coché par défaut), auquel cas le certificat obtenu n'est jamais reconnu par les navigateurs — c'est normal, décochez la case une fois le domaine et le webroot vérifiés fonctionnels.

## 📎 Annexes (référence) — 2 fiches

Commandes utiles et glossaire.

### Commandes utiles

```
# Initialiser et vérifier
./omega-serv.sh config init
./omega-serv.sh config check
./omega-serv.sh config show

# Profils
./omega-serv.sh profile list
./omega-serv.sh profile show hardened
./omega-serv.sh profile apply hardened --dry-run

# WAF et listes de blocage
./omega-serv.sh option enable waf
./omega-serv.sh waf test --method GET --path /admin --remote-ip 203.0.113.1
./omega-serv.sh blocklist list

# Active Defense
./omega-serv.sh option enable active_defense
./omega-serv.sh active-defense status
./omega-serv.sh threats list --level hostile
./omega-serv.sh incidents list --status open

# Audit et sauvegarde
./omega-serv.sh audit security --format text --min-severity medium
./omega-serv.sh config backup --description "avant modification"
./omega-serv.sh config list-backups

# Service
./omega-serv.sh service status
./omega-serv.sh service restart
```

### Glossaire

| Terme | Définition courte |
|---|---|
| **ACME** | Protocole d'émission et renouvellement automatisé de certificats, notamment utilisé par Let's Encrypt |
| **Active Defense** | Fonctions défensives basées sur les signaux WAF : qualification, ralentissement, leurres, incidents et IoC |
| **CA locale** | Autorité de certification contrôlée localement, dont le certificat public est importé sur les clients de confiance |
| **Certbot** | Client ACME de référence pour Let's Encrypt ; Omega-Serv l'invoque comme sous-processus (mode webroot, chemins projet-local) plutôt que de réimplémenter le protocole |
| **CIDR** | Notation permettant de représenter une adresse IP ou un réseau IP, par exemple `203.0.113.0/24` |
| **CSP** | Content Security Policy, en-tête HTTP qui aide à limiter certaines sources de contenu exécutables ou chargées |
| **Deception** | Mécanisme qui oriente une source hostile vers un leurre statique ou un backend isolé, afin d'observer et de qualifier son comportement |
| **FastCGI** | Protocole de communication entre le serveur web et un processus applicatif, ici notamment PHP-FPM |
| **Incident** | Objet Active Defense qui regroupe chronologie, décisions, IoC et exports pour une source ou un ensemble de sources suspectes |
| **IoC** | Indicator of Compromise : indicateur exploitable de comportement ou d'activité suspecte, tel qu'une IP ou un identifiant de requête |
| **Mode guerre** | Configuration Active Defense qui déclenche automatiquement un ensemble d'actions (ralentissement, rate limit, incident, deception...) selon des seuils |
| **Reverse proxy sortant** | Configuration où Omega-Serv agit comme client proxy vers un ou plusieurs backends HTTP/HTTPS, avec équilibrage et gestion des en-têtes |
| **Upload confiné** | Zone dédiée à l'envoi de fichiers, avec quotas, noms générés côté serveur et isolation par rapport au reste du webroot |
| **WAF** | Web Application Firewall : couche de filtrage HTTP applicative |

# 🎓 Partie 2 — Guide d'aide intégré

Fiches écran par écran, détail de chaque champ, et FAQ orientée pièges réels.

## 🚀 Démarrage rapide — 3 fiches

Les premiers écrans que vous rencontrerez en lançant Omega-Serv.

### 🏠 Accueil

*écran racine*

Le point de départ de toute votre navigation. Un bouton par grande section de l'application, aucun réglage ici.

- **Assistant premier lancement**
  - *À quoi ça sert :* Un parcours guidé en 8 étapes pour composer une première configuration complète.
  - *Quand l'utiliser :* Une seule fois, au tout premier démarrage — ou pour repartir de zéro.
  - *Ce qui se passe :* **rien avant l'étape 7** Aucune écriture tant que le résumé final n'est pas validé.

- **Registre des capacités**
  - *À quoi ça sert :* Un scan en lecture seule de votre environnement (port libre, openssl présent, PHP-FPM...).
  - *Ce qui se passe :* **lecture seule** Aucun effet sur le serveur.

- **Profils**
  - *À quoi ça sert :* Quatre profils prêts à l'emploi (minimal, standard, hardened, development).
  - *Ce qui se passe :* **écrase la config** Appliquer un profil remplace la configuration active — un diff complet est toujours affiché avant.

- **Configuration détaillée**
  - *À quoi ça sert :* Tous les réglages du serveur et des options, écran par écran. C'est le cœur de la configuration au quotidien.

- **Gestion des logs**
  - *À quoi ça sert :* Consulter, suivre en direct, faire tourner et analyser vos journaux.

- **Service**
  - *À quoi ça sert :* Piloter le service système (démarrer/arrêter/redémarrer/recharger/installer).
  - *À noter :* Certaines actions demandent une authentification (sudo).

- **Multi-instance / Instances (N)**
  - *À quoi ça sert :* Registre des installations d'Omega-Serv connues sur cette machine. Le libellé devient "Instances (N)" dès la deuxième.

- **État & Ressources**
  - *À quoi ça sert :* Vue d'ensemble en direct, rafraîchie toutes les 2 secondes. Idéal pour un diagnostic rapide.

- **Active Sécurité**
  - *À quoi ça sert :* Regroupe Active Defense (deception, menaces, incidents) et le pare-feu applicatif (WAF).

- **Audit de sécurité**
  - *À quoi ça sert :* Vérifications consultatives (service, rotation des logs, mode WAF...).
  - *Ce qui se passe :* **lecture seule** Un avis global, jamais bloquant.

- **Sauvegarde de configuration**
  - *À quoi ça sert :* Créer, lister, restaurer ou supprimer des sauvegardes complètes.
  - *Ce qui se passe :* **écrase** Restaurer remplace directement les fichiers visés.

> **⚠️ À savoir**
> - Depuis cet écran, `Échap` demande une confirmation de sortie de l'application (contrairement aux autres écrans).

### 🧙 Assistant premier lancement — 1/8 Bienvenue

*Accueil → Assistant*

Le point d'entrée du parcours guidé qui compose votre première configuration complète, étape par étape.

- **Commencer**
  - *À quoi ça sert :* Démarrer le parcours guidé.
  - *Ce qui se passe :* **aucune écriture** Ouvre simplement l'étape suivante — rien n'est écrit avant l'étape 7.

### 🧙 Assistant — 2/8 Capacités

*Assistant → étape 2/8*

Un scan en lecture seule de votre environnement, avec le port par défaut — aucun profil ni port personnalisé n'est encore choisi.

- **Suivant / Précédent**
  - *À quoi ça sert :* Naviguer entre les étapes.
  - *Ce qui se passe :* **informatif** Rien n'est écrit.

## ⚙️ Configuration du serveur — 5 fiches

Les écrans pour ajuster le comportement de votre serveur — du plus simple au plus fin.

### 🔧 Configuration de base

*Configuration détaillée →*

Les réglages fondamentaux : adresse d'écoute, port, nom de serveur, fichiers d'index.

- **Adresse d'écoute (bind)**
  - *En clair :* L'adresse IP sur laquelle le serveur accepte les connexions.
  - *Exemples :* `127.0.0.1` (local uniquement) ou `0.0.0.0` (toutes les interfaces). Défaut : 127.0.0.1.
  - *Réaction :* **redémarrage** Le socket d'écoute n'est jamais retouché par un simple rechargement.

- **Port**
  - *En clair :* Le port TCP d'écoute.
  - *Exemples :* 1 à 65535. La valeur `0` demande au système de choisir un port libre (utile pour les tests). Défaut : 8080.
  - *Réaction :* **redémarrage** Même raison que l'adresse d'écoute.

- **Nom de serveur**
  - *En clair :* Un nom interne, transmis notamment à FastCGI.
  - *Réaction :* **rechargement** Pris en compte après un rechargement du service.

- **Fichiers d'index**
  - *En clair :* Les noms de fichiers cherchés, dans l'ordre, quand une URL pointe vers un dossier.
  - *Exemple :* `index.html` par défaut.
  - *Réaction :* **rechargement**

> **⚠️ À savoir**
> - Changer bind/port pendant qu'un service est déjà actif ne prend effet qu'après un redémarrage complet — les connexions en cours seront alors coupées.

### 🛡️ Résistance et limites

*Configuration détaillée →*

Dix réglages anti-abus appliqués à chaque connexion et requête.

- **Connexions simultanées max**
  - *En clair :* Nombre maximal de connexions ouvertes en même temps. Défaut : 256.
  - *Réaction :* **rechargement**

- **Taille max de requête**
  - *En clair :* Taille maximale du corps d'une requête, en octets. Défaut : 10 Mio.
  - *Réaction :* **rechargement**

- **Taille max des en-têtes**
  - *En clair :* Protection contre les en-têtes surdimensionnés. Défaut : 16 Ko.
  - *Réaction :* **rechargement**

- **Délais (lecture, écriture, keep-alive)**
  - *En clair :* Bornes de temps pour recevoir une requête, envoyer une réponse, et garder une connexion ouverte. Défauts : 10 / 15 / 5 secondes.
  - *Réaction :* **rechargement**

- **File d'attente d'écoute (listen_backlog)**
  - *En clair :* Taille de la file de connexions en attente d'acceptation. Défaut : 128.
  - *Réaction :* **redémarrage** Fixé au moment de la création du socket.

> **⚠️ À savoir**
> - Un `listen_backlog` trop bas sous forte charge fait échouer des connexions avant même qu'elles n'atteignent Omega-Serv. Ne descendez sous 128 qu'en connaissance de cause.

### 🔒 Sécurité générique

*Configuration détaillée →*

Règles de sécurité appliquées à toutes les requêtes.

- **Méthodes autorisées**
  - *En clair :* Liste blanche des méthodes HTTP acceptées. Défaut : GET, HEAD.
  - *Réaction :* **rechargement**

- **Refuser les fichiers cachés**
  - *En clair :* Masque les fichiers/dossiers dont un segment commence par un point. Défaut : oui.
  - *Réaction :* **rechargement**

- **Mode CSP**
  - *En clair :* `enforce` (bloque) ou `report-only` (signale seulement). Défaut : enforce.
  - *Réaction :* **rechargement**

- **HSTS et en-têtes de sécurité**
  - *En clair :* Force HTTPS et active les en-têtes de sécurité standard.
  - *Réaction :* **rechargement**

- **Cross-Origin-Embedder-Policy**
  - *En clair :* `unsafe-none` (permissif, par défaut partout y compris `hardened`), `require-corp` ou `credentialless`.
  - *À noter :* Toujours émis explicitement, même en `unsafe-none` — jamais un en-tête absent (un scanner externe distingue ainsi "non considéré" de "permissif par choix"). Contrairement à `Cross-Origin-Opener-Policy`/`Cross-Origin-Resource-Policy` (toujours `same-origin`, sans risque réel), une valeur stricte peut bloquer des ressources cross-origin (polices, images, iframes tiers) propres au site réellement servi.
  - *Réaction :* **rechargement**

- **Zones CSP (Ajouter une zone / Retirer)**
  - *En clair :* Exceptions EXPLICITES à la CSP globale, par préfixe de chemin — ex. `unsafe-inline` uniquement sous `/un-dossier/` qui en a réellement besoin, sans jamais relâcher la CSP du reste du site.
  - *À noter :* Une zone REMPLACE ENTIÈREMENT la politique par défaut pour son préfixe, jamais une fusion de directives — l'assistant d'ajout (par directive, pré-rempli avec la politique globale actuelle) existe précisément pour éviter de sacrifier des directives par inadvertance.
  - *Réaction :* enregistré immédiatement, rechargement automatique si un service actif existe.

> **⚠️ À savoir**
> - Activer HSTS sans que TLS soit réellement actif n'a aucun effet utile : le navigateur ignore cet en-tête reçu en HTTP simple.
> - Une zone CSP qui relâche `unsafe-inline`/`unsafe-eval`/une source générique `*` exige une confirmation explicite à l'ajout, et reste ensuite TOUJOURS visible dans `omega-serv audit security` (règles CSP-001/CSP-002, qui scannent aussi les zones) — même délibérée, jamais silencieuse.

### 🚦 Contrôle d'accès

*Configuration détaillée →*

Règles allow/deny par préfixe d'URL, avec filtre optionnel par extension.

- **Préfixe URL**
  - *En clair :* Le préfixe auquel s'applique la règle. Doit commencer par `/`.
  - *Exemple :* `/private/`. Le préfixe le plus long l'emporte.

- **Verdict**
  - *En clair :* `allow` ou `deny`.

- **Extensions**
  - *En clair :* Restreint la règle aux fichiers avec ces extensions. Vide = toutes.
  - *Exemple :* `.key, .pem` pour bloquer les extensions sensibles partout, sauf dans une zone précise.

> **💡 Astuce**
> Pour bloquer une extension sensible partout sauf dans une zone : une règle `deny` sur `/` avec l'extension visée, puis une règle `allow` (sans extension) sur le préfixe à excepter — le préfixe le plus spécifique l'emporte.

### 🔗 Alias

*Configuration détaillée →*

Sert un préfixe d'URL depuis un autre emplacement, y compris hors du webroot.

- **Préfixe URL + chemin cible**
  - *En clair :* L'URL à rediriger et l'emplacement disque réellement servi.
  - *Exemple :* `/media/` → `webroot/media`.
  - *Réaction :* **rechargement**

- **Autoriser hors webroot**
  - *En clair :* Autorise explicitement une cible en dehors du webroot habituel. Défaut : non.

## 🧩 Modules optionnels — 9 fiches

Tous désactivés par défaut. Vous activez uniquement ce dont vous avez besoin.

### ↪️ Redirections

*Configuration détaillée →*

Renvoie une réponse 3xx vers une autre URL. Contrairement aux rewrites, le client voit l'URL changer dans son navigateur.

- **Préfixe, destination, code**
  - *En clair :* L'URL déclenchante, l'URL cible, et le code HTTP de redirection.
  - *Codes disponibles :* 301, 302, 307, 308. Défaut : 302.

### ✏️ Rewrites

*Configuration détaillée →*

Réécrit une URL en interne, sans jamais renvoyer de redirection au client. Invisible côté navigateur.

> **💡 Différence avec une redirection**
> Une redirection change l'URL affichée dans le navigateur. Un rewrite garde l'URL apparente inchangée — c'est le serveur qui traduit discrètement.

### 🐘 FastCGI / PHP-FPM

*Configuration détaillée →*

Un seul enregistrement : proxy vers un serveur PHP-FPM pour exécuter du PHP.

- **Préfixe URL + racine d'exécution**
  - *En clair :* L'URL sous laquelle PHP est exécuté et le dossier contenant les scripts.
  - *Important :* Le dossier de scripts ne peut jamais se trouver dans le webroot (vérifié structurellement).

- **Socket PHP-FPM**
  - *En clair :* Le chemin du socket Unix utilisé pour communiquer avec PHP-FPM. Défaut : var/run/php-fpm.sock.

> **⚠️ À savoir**
> - La première activation de l'option FastCGI exige un redémarrage complet (le client n'est construit qu'au démarrage).

### 📂 Directory listing

*Configuration détaillée →*

Affiche la liste des fichiers quand un dossier n'a pas de fichier d'index.

- **Thème CSS + CSS externe**
  - *En clair :* Palette de couleurs du listing. Un CSS externe peut être ajouté en plus (jamais à la place).

- **Fichiers HEADER et README**
  - *En clair :* Affiche le contenu d'un fichier texte en haut (HEADER) ou en bas (README) du listing, s'il existe.

- **Zones**
  - *En clair :* Les préfixes d'URL où le listing est actif.

> **💡 À savoir**
> Les fichiers/dossiers commençant par un point restent masqués par la règle "deny_hidden_files", indépendamment des réglages ici.

### 🔐 Authentification

*Configuration détaillée →*

Protège un dossier ou une application par authentification HTTP Basic.

- **Utilisateurs**
  - *En clair :* Ajoutez, modifiez le mot de passe ou supprimez des comptes. Les mots de passe sont hachés avec `scrypt`.
  - *Stockage :* Dans un fichier séparé (`users.json`), jamais dans la configuration principale.

- **Zones protégées**
  - *En clair :* Associe un préfixe d'URL à un groupe d'utilisateurs autorisés.
  - *Stockage :* Dans `zones.json`.

> **⚠️ À savoir**
> - Une authentification active SANS TLS transmet les identifiants en clair sur le réseau. L'assistant de premier lancement demande une confirmation explicite dans ce cas.

### 💾 Cache

*Configuration détaillée →*

Contrôle du cache navigateur, par zone d'URL et par extension.

- **Valeur par défaut (Cache-Control)**
  - *En clair :* En-tête envoyé quand aucune règle spécifique ne s'applique. Défaut : `no-cache, must-revalidate`.
  - *Directives courantes :* no-cache, no-store, must-revalidate, private, public, max-age, immutable.

- **Règles par zone / par extension**
  - *En clair :* Cache-Control spécifique pour un préfixe d'URL ou une extension.
  - *Exemple :* `/static/` → `public, max-age=31536000, immutable`.

### 🔀 Reverse Proxy

*Configuration détaillée →*

Omega-Serv agit lui-même comme reverse proxy vers un ou plusieurs backends — le sens inverse de l'option `behind_proxy` (où c'est Omega-Serv qui est *derrière* un proxy). Une zone se crée en deux temps : d'abord ses réglages généraux (préfixe d'URL, stratégie, délais), puis la liste de ses backends dans un écran dédié (host, port, TLS, poids).

- **Stratégie de répartition**
  - *Options :* `round_robin` (par défaut), `weighted_round_robin`, `weighted_least_connections`, `least_connections`, `ip_hash`, `least_response_time`, `real_load`.
  - *En clair :* `real_load` interroge vraiment chaque backend pour savoir lequel est le moins chargé — en mode natif (si c'est un autre Omega-Serv) ou déclaratif (si le backend expose sa propre sonde HTTP de charge, n'importe quel format minimal accepté).

- **Backends (étape 2)**
  - *En clair :* Host/port/TLS/poids pour la répartition, plus deux options avancées par backend : un plafond de connexions actives (backpressure) et une sonde de santé active (indépendante du trafic réel).
  - *Réaction :* Un backend saturé (plafond atteint) répond 503 proprement, jamais la même erreur qu'un backend réellement en panne (502) — les deux situations sont volontairement distinguées.

- **Affinité de session et règles sur en-tête**
  - *En clair :* Un cookie opaque peut coller un client au même backend (jamais l'adresse réelle exposée), et des règles simples peuvent forcer un backend selon la valeur d'un en-tête entrant.

> **💡 À savoir**
> Un backend peut être mis en pause (DRAINING) ou en maintenance (MAINTENANCE) sans jamais toucher à la configuration — voir la fiche « État en direct des backends » ci-dessous. L'état « DOWN », lui, reste toujours automatique, déduit des échecs réels observés.

> **⚠️ Redémarrage systématique**
> La toute première activation de l'option exige un redémarrage complet (le client HTTP n'est construit qu'au démarrage). Une fois déjà active, modifier les zones ne demande plus qu'un simple rechargement.

### 📡 État en direct des backends

*Configuration détaillée → Reverse Proxy → zone →*

Interroge le serveur **réellement en cours d'exécution** (jamais la configuration sur disque) pour afficher l'état actuel de chaque backend d'une zone, et permet de forcer DRAINING ou MAINTENANCE à chaud.

- **DRAINING / MAINTENANCE / Revenir à l'automatique**
  - *En clair :* Exclut un backend des nouveaux choix sans jamais couper les connexions déjà en cours, ni le marquer en panne.
  - *À noter :* Ces deux états ne sont jamais écrits dans la configuration — un redémarrage complet du serveur les efface (un simple rechargement les conserve).

> **⚠️ Piège réel**
> Cet écran a besoin de `trusted_proxy` actif avec `127.0.0.1` dans ses réseaux de confiance, et d'un serveur réellement démarré — sinon il affiche « serveur injoignable », jamais une erreur bloquante.

### 🗃️ Cache du reverse proxy

*Configuration détaillée →*

Supervision et purge du cache des réponses proxiées — à ne pas confondre avec l'écran « Cache » ci-dessus, qui ne pose qu'un en-tête `Cache-Control` pour le navigateur du client. Ici, Omega-Serv conserve lui-même une copie de la réponse sur disque.

- **Statistiques**
  - *En clair :* Nombre d'entrées et taille sur disque, lus directement — fonctionne même serveur éteint. Le ratio hits/miss, lui, interroge le serveur réellement en cours d'exécution (affiche « indisponible » s'il est éteint ou injoignable, sans jamais bloquer le reste de l'écran).

- **Purger une zone / Purger tout**
  - *En clair :* Supprime les entrées de cache sur disque immédiatement, y compris si le serveur tourne (il relira à froid).

> **💡 À savoir**
> Le diagnostic au cas par cas reste l'en-tête de réponse `X-Omega-Cache` (`HIT`/`MISS`/`BYPASS`), visible via les outils du navigateur ou `curl -I`.

## 🔐 TLS / HTTPS — 7 fiches

Pour mettre votre site en HTTPS — du plus simple (auto-signé) au plus complet (CA locale).

### 📋 Statut TLS

*TLS →*

Inspecte le certificat configuré : validité, expiration, correspondance clé/certificat, permissions.

> **💡 À savoir**
> Cet écran inspecte le fichier sur disque, pas nécessairement celui réellement servi par un serveur déjà lancé si celui-ci a changé depuis le dernier redémarrage.

### 🎫 Générer un certificat auto-signé

*TLS →*

Génère un certificat auto-signé (non reconnu par défaut par les navigateurs, mais parfait pour le local/labo).

- **Nom commun (CN)**
  - *En clair :* Généralement le nom d'hôte du serveur. Exemple : `mon-serveur.local`.

- **SAN DNS / SAN IP**
  - *En clair :* Noms et adresses IP supplémentaires couverts par le certificat.

- **Type de clé**
  - *En clair :* RSA 2048/4096 ou ECDSA P-256/P-384. Défaut : RSA 2048.

> **⚠️ À savoir**
> - La génération écrit réellement les fichiers sur disque dès le clic.
> - Si TLS est déjà actif, le serveur continue de servir l'ancien certificat jusqu'à un redémarrage complet.

### 🏛️ Assistant CA locale

*TLS →*

Pour plusieurs appareils qui doivent faire confiance sans réimporter un certificat individuellement.

- **1. Générer la CA**
  - *En clair :* Crée votre autorité de certification locale. Une seule fois. La passphrase est obligatoire.

- **2. Générer la CSR**
  - *En clair :* Crée une demande de signature pour ce serveur.

- **3. Signer la CSR**
  - *En clair :* Signe la demande avec votre CA. Le certificat final est prêt.
  - *À noter :* La passphrase de la CA est resaisie ici (jamais conservée en mémoire entre les étapes).

> **💡 À savoir**
> Le certificat racine (`root-ca.pem`) doit être importé manuellement dans le magasin de confiance de chaque client — c'est ce qui rend le certificat final reconnu.

### 🌐 Assistant Let's Encrypt (Certbot)

*TLS →*

Obtient un certificat public reconnu par les navigateurs via Certbot (défi HTTP-01, mode webroot) — jamais `--standalone` (le port 80 est déjà occupé par Omega-Serv) et jamais `/etc/letsencrypt/` (tout est écrit sous `secure/certificates/letsencrypt/` du projet, entièrement non-privilégié). Importe automatiquement le certificat obtenu.

- **Domaine**
  - *En clair :* Nom de domaine public déjà pointé vers ce serveur (obligatoire). Ex : `monserveur.dynu.com`.

- **Email**
  - *En clair :* Optionnel — alertes d'expiration envoyées par Let's Encrypt.

- **Mode test (staging)**
  - *En clair :* Coché par défaut. Certificat non reconnu par les navigateurs mais jamais soumis aux limites de taux réelles.

> **⚠️ À savoir**
> - Le port 80 doit rester accessible depuis Internet le temps du défi HTTP-01 — le DDNS et la redirection de port restent entièrement à votre charge.
> - Si TLS est déjà actif, le serveur continue de servir l'ancien certificat jusqu'à un redémarrage complet.

### 🔁 Renouvellement automatique (Certbot)

*TLS →*

Planifie le renouvellement des certificats Certbot déjà obtenus — s'adapte au gestionnaire de service détecté pour CETTE instance uniquement (jamais un mécanisme partagé entre plusieurs instances).

- **Configurer maintenant**
  - *En clair :* systemd → installe et active un timer (sudo ponctuel). Sinon → ajoute une ligne à votre crontab utilisateur si possible, ou affiche la ligne à ajouter vous-même.

> **💡 À savoir**
> Reconfigurer ne duplique jamais l'entrée — remplace toujours celle de cette instance. Une fois installé, le renouvellement tourne deux fois par jour sans intervention, réimporte le certificat et redémarre le service automatiquement.

> **⚠️ À savoir**
> Sur certaines distributions (dont Arch/Manjaro), le paquet Certbot n'installe AUCUN timer par défaut, contrairement à Debian/Ubuntu — vérifiez toujours le statut affiché ici.

### 🚫 Révoquer un certificat

*TLS →*

Marque un certificat comme révoqué dans le registre de la CA. Action irréversible pour ce certificat.

> **⚠️ À savoir**
> - Pas de distribution CRL complète en V1 — la révocation reste locale (index.txt), jamais publiée automatiquement vers les clients.

### 🔀 Activer / désactiver TLS

*TLS →*

Active ou désactive TLS, et choisit son mode.

- **Mode direct / behind_proxy**
  - *En clair :* `direct` = ce serveur termine TLS lui-même. `behind_proxy` = TLS est déjà terminé en amont, ce serveur reste en HTTP simple.

- **Chemin du certificat / de la clé**
  - *En clair :* Utilisés si le mode est `direct`. Vides = conservent la valeur actuelle.

> **⚠️ À savoir**
> - Le contexte SSL n'est construit qu'une seule fois au démarrage — activer, désactiver, ou changer le mode exige systématiquement un redémarrage complet.
> - À ne pas confondre avec le réglage `reverse_proxy` : ici, `behind_proxy` signifie qu'Omega-Serv est DERRIÈRE un proxy, l'inverse d'agir soi-même comme proxy.

## 📜 Gestion des logs — 12 fiches

Menu en deux colonnes (refonte 2026-10-15, au même niveau que le reste de la suite) : **Bibliothèque** (consulter, choisir un viewer, traiter les IP) et **Maintenance** (rotation/restauration/purge/export, inchangée).

### 📚 Bibliothèque

*Gestion des logs →*

Hub central référençant tout log à traiter — ceux d'Omega-Serv ou n'importe quel autre fichier de la machine. Alimentation **manuelle** pour cette passe (aucun scan automatique du système). Source commune de Favoris, Voir les logs et Voir et traiter IP.

- **Chemin à ajouter manuellement**
  - *En clair :* Référence un fichier de log quelconque — il n'a pas besoin d'exister déjà.

- **Ajouter les logs connus d'Omega-Serv**
  - *En clair :* Ajoute en un clic access/error/waf-alerts, + les 2 logs du script magnet si actif.
  - *À noter :* Jamais un scan du reste du système — uniquement les quelques logs déjà connus de ce projet.

> **💡 À savoir**
> L'état affiché (OK/SUSPECT/ABSENT) et la colonne **Modifié** sont toujours recalculés en lisant le disque réellement à chaque ouverture de cet écran, jamais une donnée figée au moment de l'ajout.

### 🌐 Sources distantes (SSH)

*Gestion des logs → Bibliothèque →*

Centralise, sur demande explicite, le log d'un serveur backend du même réseau local (derrière le reverse proxy) via `scp`, puis l'ajoute à la Bibliothèque. Ce n'est **jamais** une consultation en direct du serveur distant : c'est un instantané figé au moment du clic — une nouvelle récupération remplace simplement la copie précédente.

- **Label / Hôte / Chemin distant**
  - *En clair :* Identifie la source — un nom choisi par vous, l'adresse du serveur, le chemin du fichier sur ce serveur. Tous les trois obligatoires.

- **Utilisateur / Port / Chemin de la clé privée**
  - *En clair :* Optionnels — laissez vide pour utiliser les réglages par défaut de votre propre SSH (agent, `~/.ssh/config`), exactement comme si vous tapiez la commande vous-même.
  - *À noter :* Omega-Serv ne lit ni ne stocke **jamais** le contenu d'une clé — uniquement son chemin, si vous en indiquez un. Aucun mot de passe n'est jamais demandé.

- **Récupérer maintenant**
  - *En clair :* Lance `scp` en arrière-plan (l'interface reste utilisable) et ajoute le résultat à la Bibliothèque (colonne Accès = `ssh`, colonne Modifié = date de cette récupération).
  - *À noter :* En cas d'échec (hôte injoignable, `scp` absent, droits refusés), le message d'erreur du système s'affiche tel quel, aucun fichier n'est ajouté.

> **💡 À savoir**
> Aucun scan réseau automatique, aucune connexion sans configuration explicite, aucune vérification de taille avant transfert. La capacité `scp` se vérifie dans le **Registre des capacités** (présence du binaire uniquement, jamais un test de joignabilité d'un hôte).

### ⭐ Favoris

*Gestion des logs → Bibliothèque →*

Combinaisons nommées (un ou plusieurs logs de la Bibliothèque + un viewer) pour un lancement direct — un favori Simple/Classique ouvre immédiatement le viewer final, un favori lnav lance `lnav` directement sans écran intermédiaire.

- **Numéros + Nom + Viewer + Enregistrer**
  - *En clair :* Un seul log autorisé avec Simple/Classique ; `lnav` uniquement au-delà d'un log.
  - *À noter :* Refusé à la création si le viewer choisi est incompatible avec le nombre de logs — jamais tronqué silencieusement.

### 📜 Voir les logs

*Gestion des logs → Bibliothèque →*

Choisit un ou plusieurs logs exclusivement depuis la Bibliothèque, puis un viewer : Simple (tail en direct + stats génériques), Classique (lecture + suivi), lnav (fusion multi-logs).

- **Numéros (ex: 1,3)**
  - *En clair :* Simple et Classique exigent exactement UN log sélectionné ; lnav fonctionne avec un ou plusieurs.

### 👁️ Voir les logs — Simple

*Gestion des logs → Bibliothèque → Voir les logs →*

Suit un log en direct avec un parseur **générique** (fonctionne sur n'importe quel format — access log, auth.log, syslog...) et un tableau de statistiques (IPs uniques, taux d'erreur, répartition des codes HTTP si le format s'y prête).

> **💡 À savoir**
> La section "STATUTS HTTP" n'apparaît que si au moins une ligne ressemble à un access log Combined/Common — jamais affichée pour un auth.log/syslog.

### 👁️ Voir les logs — Classique

*Gestion des logs → Bibliothèque → Voir les logs →*

Affiche les 200 dernières lignes d'un log choisi dans la Bibliothèque et peut suivre son évolution en direct.

- **Suivre en direct**
  - *En clair :* Rafraîchit automatiquement toutes les secondes.

### 🔍 Suivre les logs fusionnés (lnav)

*Gestion des logs → Bibliothèque → Voir les logs, ou Favoris →*

Lance l'outil externe lnav sur un ou plusieurs logs fusionnés chronologiquement, dans un vrai terminal.

- **Cases à cocher (Access/Error/WAF alerts/WAF magnet)**
  - *En clair :* Les 2 logs du script magnet sont inclus d'office, comme les logs natifs. Un log coché mais absent est simplement ignoré au lancement, jamais bloquant pour les autres.

- **Logs sélectionnés depuis la Bibliothèque**
  - *En clair :* Pré-coche les logs choisis dans "Voir les logs" — jamais ajouté aux épingles persistées.

- **Chemins épinglés**
  - *En clair :* Un chemin manuel saisi puis "Épinglé" est conservé PERSISTANT entre sessions (contrairement au champ manuel seul, utilisable une seule fois) — affiché ensuite comme une case à cocher supplémentaire, au même titre que les logs connus.
  - *À noter :* "Retirer l'épingle" ne supprime jamais le fichier de log lui-même, seulement le raccourci.

> **💡 À savoir**
> Nécessite que `lnav` soit installé. Sans lui, un message explicite vous l'indique — le reste de l'écran reste utilisable. Lancé depuis un favori, cet écran se lance tout seul, sans clic supplémentaire.

### 🔎 Voir et traiter IP

*Gestion des logs → Bibliothèque →*

Liste les IP les plus actives parmi un ou plusieurs logs de la Bibliothèque (n'importe quel format, pas seulement l'access log), avec possibilité de retirer une IP des logs analysés.

- **24 heures / 7 jours / 30 jours / Tout**
  - *En clair :* Choisit la période analysée — "Tout" est nouveau, l'ancien écran ne proposait que 24h/7j/30j.

> **⚠️ Action destructive**
> - Le retrait d'IP modifie directement et irréversiblement **tous** les fichiers de log analysés, quel que soit leur format.

### 🔄 Rotation / archivage

*Gestion des logs →*

Quatre modes disponibles selon votre besoin.

- **Tourner si nécessaire**
  - *En clair :* Archive le log uniquement s'il dépasse le seuil de taille configuré.

- **Sauvegarde maintenant**
  - *En clair :* Archive le log immédiatement, quelle que soit sa taille.

- **Automatisation planifiée**
  - *En clair :* Enregistre une fréquence (hebdomadaire, mensuelle...) — **note importante :** rien ne l'exécute automatiquement, c'est un choix délibéré de parité avec omega-fire. Une exécution réelle reste à construire séparément si le besoin est confirmé.

> **💡 À savoir**
> Les archives sont écrites dans `var/backups/logs/`, un emplacement distinct de `var/backups/` (réservé aux sauvegardes de configuration).

### 📥 Restaurer une archive

*Gestion des logs →*

Extrait le contenu d'une archive de log dans un dossier de restauration. N'écrase jamais les logs actifs.

### 🗑️ Purger les archives

*Gestion des logs →*

Supprime définitivement une archive de log. Confirmation obligatoire — action irréversible.

### 📤 Exporter la liste des archives

*Gestion des logs →*

Exporte la liste des archives (métadonnées, pas leur contenu) en JSON ou HTML.

## 🔧 Service & multi-instance — 2 fiches

Piloter le service système et gérer plusieurs installations.

### ⚙️ Service

*Accueil → Service*

Pilote le service système (systemd/OpenRC/runit) qui fait tourner Omega-Serv.

- **Démarrer / Arrêter / Redémarrer / Recharger**
  - *En clair :* Actions directes de contrôle. **Recharger** (SIGHUP) est léger, les autres coupent les connexions en cours.
  - *À noter :* Aucune confirmation demandée pour ces 4 actions.

- **Installer / Désinstaller l'unité**
  - *En clair :* Crée ou retire le fichier d'unité systemd. Demande confirmation et une authentification (sudo).
  - *Garde-fous :* Bloqué si une autre unité pointe déjà vers ce répertoire, ou si ce nom est déjà utilisé ailleurs.

> **⚠️ Piège réel**
> - Après "Installer l'unité", une session déjà ouverte n'a pas automatiquement le nouveau groupe système créé. Reconnectez-vous une seule fois si l'état semble incohérent.

### 🗂️ Multi-instance

*Accueil → Instances (N)*

Registre de toutes les installations connues sur cette machine, avec le statut systemd de chacune.

- **Créer une nouvelle instance**
  - *En clair :* Duplique cette installation vers un nouveau répertoire frère. Un port libre est proposé par défaut.

- **Piloter cette instance**
  - *En clair :* Bascule l'interface pour piloter une autre instance enregistrée. Nécessite que son environnement virtuel existe.

- **Désinstaller cette instance**
  - *En clair :* Retire l'unité systemd, le compte dédié (si plus utilisé) et l'entrée du registre. Le répertoire n'est supprimé que sur confirmation explicite séparée.

## 📊 État & ressources — 2 fiches

Vue d'ensemble opérationnelle en temps réel.

### 📊 État & Ressources

*Accueil →*

Tableau de bord en trois cadres, rafraîchi automatiquement toutes les 2 secondes.

- **État du serveur/service**
  - *En clair :* Processus/PID, statut du service système, profil actif, options, TLS, port.

- **Flux du log d'accès**
  - *En clair :* Débit, répartition par code de statut, IPs uniques, taux d'erreur.
  - *À noter :* Ne lit que le log d'accès au format combined.

- **Ressources système**
  - *En clair :* CPU, RAM, disque, swap, charge, réseau.

### 🧪 Simuler une requête

*État & Ressources →*

Rejoue le vrai routage d'Omega-Serv sans envoyer de requête réseau. Idéal pour comprendre pourquoi une règle s'applique ou pas.

## 🛡️ Active Sécurité (WAF + Active Defense) — 14 fiches

Le centre de sécurité d'Omega-Serv. Tout est optionnel et désactivé par défaut.

> **💡 Deux piliers**
> **WAF** filtre les requêtes malveillantes connues (signatures, limitation de débit, liste de blocage). **Active Defense** va plus loin : il qualifie le comportement hostile à partir des signaux WAF, et peut ralentir, journaliser, rediriger vers un leurre et créer des incidents documentés.

### 📊 Active Defense — État

*Active Sécurité →*

Vue d'ensemble en lecture seule : mode, état du mode guerre, état de la déception, nombre de sources suivies.

> **⚠️ Piège vérifié**
> - Activer l'option `active_defense` (menu Options) ne suffit PAS : un second interrupteur, `war_mode.enabled`, vaut **false** par défaut. Tant qu'il reste à false, aucun événement n'est enregistré même avec du trafic hostile réel.
> - La ligne "Mode guerre" affichée ici est le seul endroit où vérifier le VRAI interrupteur.

### ⚙️ Active Defense — Réglages

*Active Sécurité →*

Configure l'intégralité d'Active Defense sans jamais éditer manuellement `config/omega-serve.json`.

- **Mode**
  - *En clair :* `monitor` (observe seulement) ou `enforce` (applique les actions). Défaut : monitor.

- **Mode guerre actif**
  - *En clair :* LE VRAI INTERRUPTEUR qui déclenche l'observation et les actions automatiques. Défaut : non.

- **Profils de leurre**
  - *En clair :* Associe une classe d'attaque à un niveau d'isolation.
  - *⚠️ Important :* En isolation `fixture`, le nom doit être EXACTEMENT `fake_admin`, `fake_cms`, `fake_api` ou `fake_secrets`. Tout autre nom fait que le leurre ne se déclenche JAMAIS silencieusement — bloqué à l'enregistrement depuis une mise à jour.

- **Zones de leurre (Niveau 2)**
  - *En clair :* Backends isolés vers lesquels un profil proxy peut rediriger.
  - *À noter :* Jamais créées automatiquement, l'existence n'est pas vérifiée à l'enregistrement. Si rien n'écoute, l'attaquant reçoit un 502 au moment de la requête.

> **⚠️ Redémarrage systématique**
> - TOUT changement ici exige un redémarrage complet — Active Defense n'est jamais rechargé à chaud.

### 🎯 Menaces suivies

*Active Sécurité →*

Liste toutes les sources suivies avec leur score et niveau de menace (normal, suspicious, hostile, contained).

> **💡 Calcul du score**
> Chaque source (IP + hash du User-Agent) accumule un score : +10 (WAF-001 bloquant), +25 (escalade de réputation), +25 (bannissement connu), +30 (POST sur un leurre déjà assigné), avec décroissance de -5 toutes les 15 minutes sans nouvel événement.

### 📋 Incidents

*Active Sécurité →*

Liste les incidents de sécurité, permet de les fermer et d'exporter des indicateurs de compromission (IoC).

- **Fermer l'incident**
  - *En clair :* Marque l'incident comme fermé. Peut déclencher un export IoC/rapport automatique selon la configuration.

- **Exporter IoC / Générer rapport**
  - *En clair :* Écrit un fichier d'indicateurs (JSON/CSV) ou un rapport Markdown complet.
  - *À noter :* Chaque export est accompagné d'un fichier `<export>.sha256` (format standard).

### 🎭 Leurres (Deception)

*Active Sécurité →*

Liste les affectations actives vers les leurres, permet de les libérer manuellement.

> **💡 Deux niveaux d'isolation**
> **Niveau 1 (fixture)** : même processus, même utilisateur OS que la production — isolation faible, acceptable uniquement parce que la fixture ne retourne qu'un gabarit statique. **Niveau 2 (proxy)** : relayé vers un processus séparé via une zone de leurre.

### 🧪 Simuler une décision

*Active Sécurité →*

Simule une décision Active Defense (score, classe d'attaque) sans aucun effet réel — dry-run complet.

> **💡 Astuce**
> Idéal pour vérifier une configuration ou expliquer une décision sans toucher à la production. Aucune écriture réelle, aucun impact réseau.

### 🛡️ WAF — État

*Active Sécurité →*

Vue d'ensemble en lecture seule : mode, comportement en cas d'erreur, packs de règles référencés, taille de la liste de blocage.

> **⚠️ Piège vérifié**
> - Si aucun pack de règles n'est référencé, le WAF ne peut RIEN détecter même actif — l'écran l'indique explicitement.

### 🧩 WAF — Modules

*Active Sécurité →*

Trois sections : mode, gestion des packs de règles, gestion de la liste de blocage.

- **Mode**
  - *En clair :* `log-only` (journalise sans bloquer) ou `block` (bloque réellement).
  - *Réaction :* **rechargement automatique**

- **Packs de règles**
  - *En clair :* Fichiers de règles chargés par le WAF. Sans au moins un pack, rien n'est détecté.
  - *Réaction :* **rechargement automatique**

- **Liste de blocage**
  - *En clair :* IP/réseaux bannis, avec motif et expiration optionnelle. Fichier par défaut : `var/lib/waf/blocklist.json` (sous `var/`, le seul dossier où le service systemd peut écrire ses auto-bans) ; un ancien `secure/waf/blocklist.json` est repris une fois au démarrage et laissé en place comme sauvegarde.
  - *Réaction :* **effet immédiat** Relue depuis le disque à CHAQUE requête — aucun rechargement nécessaire.

### 🧪 WAF — Tester une requête

*Active Sécurité →*

Teste une requête simulée contre les règles WAF enregistrées, sans requête réseau.

> **💡 À savoir**
> Reconstruit le moteur WAF à partir de la configuration SAUVEGARDÉE sur disque à chaque test. Si un serveur déjà lancé n'a pas encore été rechargé après un changement de règles, ce test peut refléter un comportement différent de ce que ce serveur applique réellement.

### ✏️ WAF — Règles et listes personnalisées

*Active Sécurité →*

Un seul tableau pour les **règles** (écrites dans `secure/waf/rules/custom.json`, pack référencé automatiquement) et les **listes** (fichiers texte de `secure/waf/rules/keywords/`, chargées explicitement par l'assistant). La colonne **Type** fait la différence : une liste n'est pas une règle de `custom.json`.

- **Ajouter**
  - *En clair :* ouvre l'assistant : une règle simple, ou **CHARGER une liste**.

- **Modifier · Éditer la liste · Activer/Désactiver**
  - *En clair :* change gravité, récidive et zone de recherche d'une liste, ouvre son fichier dans l'éditeur intégré, ou bascule une règle/liste sans la supprimer. Chaque changement est vérifié comme au chargement, puis rechargé automatiquement.

- **Supprimer / Retirer**
  - *En clair :* supprime une règle de `custom.json`, ou retire une liste du WAF — son **fichier est conservé** et reste proposé par l'assistant.

- **Colonnes Détail et Gravité**
  - *En clair :* nombre d'entrées de la liste (ou « ⚠ fichier absent / illisible par le service »), gravité et récidive, ex. « Élevé, 2 en 10 min -> ban 24 h ».

> **💡 Astuce**
> L'assistant propose un questionnaire en langage clair pour les 4 scénarios les plus courants (chemin précis, mot-clé dans l'URL, mot-clé dans un formulaire, User-Agent de scanner). Un mode Avancé reste disponible pour écrire directement motif/portée.

### 🧙 WAF — Assistant règle / chargement de liste

*Active Sécurité →*

Questionnaire en langage clair pour construire une règle WAF sans connaître les expressions régulières, **ou** pour charger une liste de chemins / de mots-clés depuis un fichier texte. Le chargement est une action explicite : rien n'est actif avant le clic sur **Charger**.

- **Que voulez-vous détecter ?**
  - *Options :* un chemin précis, un mot-clé dans l'adresse, un mot-clé envoyé en formulaire, un outil de scan connu, Avancé (regex/portée libres), **CHARGER une liste de chemins**, **CHARGER une liste de mots-clés**.

- **Gravité (règle)**
  - *En clair :* poids de la règle dans le calcul du score de menace. Faible/Moyen/Élevé/Critique (1/3/6/9).

- **Fichier de liste**
  - *Options :* vos fichiers `.txt` de `secure/waf/rules/keywords/`, les références livrées (`sensitive-paths-hostile`, `sensitive-paths-probe`) pas encore copiées, ou « Nouveau fichier… ».
  - *En clair :* une référence est **copiée** au chargement ; c'est cette copie que vous modifiez, une mise à jour ne l'écrase jamais. Choisir une référence pré-remplit les réglages conseillés.

- **Où chercher · Partie de la requête**
  - *En clair :* liste de chemins : n'importe où dans l'adresse (attrape `/blog/.env`) ou seulement au début (plus prudent pour `/api`, `/admin`). Liste de mots-clés : adresse et paramètres, formulaire POST, User-Agent ou Referer.

- **Gravité (liste)**
  - *Options :* **Observation** (journal seulement, conseillé au premier chargement), Faible (1), Moyen (3, ne bloque jamais seul), Élevé (6, 403 dès le premier accès), Critique (9).

- **Récidive**
  - *En clair :* bannir après N accès à **cette** liste en M minutes, pendant une durée choisie (ban applicatif temporaire, réponse 451). Références : hostile 2 en 10 min → 24 h, sondage 5 en 10 min → 1 h. Grisée en Observation.

- **Charger**
  - *En clair :* vérifie dans l'ordre le nom du fichier, la syntaxe (numéro de ligne en cas d'erreur), la lisibilité par le compte du service, l'absence de doublon et les conflits avec les routes du site. Si une seule vérification échoue, la configuration n'est pas modifiée.

> **⚠️ Point de vigilance**
> Une liste qui bloque seule (gravité ≥ 5) et qui toucherait une route réellement servie (alias, reverse proxy, zone Auth, fichier du webroot) est refusée : ajoutez une exception `!/chemin` dans la liste, ou chargez-la en Observation.

### 📝 WAF — Éditeur de liste

*Active Sécurité → Custom →*

Éditeur de texte intégré, sans éditeur externe. **Tout se fait à la souris** : aucun raccourci clavier, le clavier ne sert qu'à la saisie (caractères, Entrée, flèches, Début/Fin, Page préc./suiv., Retour arrière, Suppr).

- **Syntaxe d'une liste de chemins**
  - *En clair :* une entrée par ligne, `#` = commentaire. `/admin` → `/admin` et `/admin/xxx` (jamais `/administrator`) ; `/.git/` → tout ce qui est dessous ; `/*.bak` → extension ; `!/api/v1` → exception, toujours prioritaire.
  - *Réaction :* analyse en direct ; les erreurs s'affichent avec leur numéro de ligne, un clic place le curseur dessus. Un texte en erreur ne peut pas être enregistré.

- **Barre d'outils · Rechercher**
  - *En clair :* Annuler, Rétablir, Couper, Copier, Coller, Sélectionner la ligne, Tout sélectionner, Supprimer la ligne ; recherche Précédent/Suivant. Le collage du terminal (clic du milieu) fonctionne aussi.

- **Tester**
  - *En clair :* indique ce que ferait la liste **en cours d'édition** d'un chemin : « DÉTECTÉ par la ligne N », « AUTORISÉ : exception ligne N » ou « aucune ligne ne correspond » — même normalisation que le WAF.

- **Vérifier contre mes logs**
  - *En clair :* rejoue les requêtes **réussies** (2xx/3xx) du journal d'accès : chaque ligne qui aurait touché une requête probablement légitime est montrée avec un exemple ; un clic ajoute une exception (pour le chemin ou son dossier) ou supprime la ligne.

- **Nouveautés de la référence**
  - *En clair :* propose, case par case, les entrées de la référence absentes de votre liste. Une ligne de la référence que vous supprimez est marquée `#retire: /x` et n'est plus jamais reproposée.

- **Corriger les droits**
  - *En clair :* rend le fichier lisible par le compte du service, en listant chaque changement de droits avant de l'appliquer — uniquement sur ce qui vous appartient, jamais via sudo.

- **Enregistrer et appliquer**
  - *En clair :* écriture sûre : droits et groupe conservés, nouveau fichier en `0644`, refus si le fichier a été modifié ailleurs ou si c'est un lien symbolique.
  - *Réaction :* le serveur n'est rechargé que si la liste passe la vérification ; sinon la raison est affichée et le serveur garde ses règles actuelles.

> **💡 Fermer, Aide et ctrl+q**
> `Échap`, `F1` et `Ctrl+P` ne font rien dans l'éditeur, volontairement : utilisez les boutons **Fermer** (confirmation s'il reste des modifications) et **Aide**. Seul `Ctrl+Q` reste actif pour quitter l'application, avec confirmation.

### ⚙️ WAF — Modifier une liste

*Active Sécurité → Custom →*

Change le nom affiché, la zone de recherche, la gravité et la récidive d'une liste déjà chargée, sans toucher à son fichier.

- **Gravité · Récidive**
  - *En clair :* mêmes choix que dans l'assistant. Typiquement : passer d'Observation à Élevé une fois les alertes lues. La nouvelle configuration est vérifiée avant d'être écrite ; rendre une liste bloquante réactive la réputation et l'auto-ban s'ils avaient été éteints.

### 🧲 WAF — Magnet (import d'un WAF externe)

*Active Sécurité →*

Importe un script WAF `mod_magnet` Lighttpd EXISTANT (écrit pour un autre site) sans le réécrire, comme renfort additif au WAF natif — il ne peut jamais lever un blocage déjà décidé par le natif.

> **💡 Pont `lighty.*`, pas un contrat inventé**
> Le script reçoit `lighty.env`/`lighty.header`/`lighty.content`/`lighty.stat` exactement comme sous un vrai Lighttpd (runtime Lua persistant : les compteurs internes du script — rate limiting, blocklist progressive — survivent entre requêtes). Convention de retour mod_magnet : `0` = continuer, un code ≥ 100 = blocage avec ce code HTTP.

- **Script (chemin relatif au projet)**
  - *En clair :* Le fichier Lua à importer — une liste des scripts trouvés sous `secure/waf/scripts/` est affichée en indice.

- **Chemins personnels dissociés**
  - *En clair :* 5 chemins (blocklist, dossier de règles, 2 journaux, fichier de persistance du rate limiting) injectés dans le script à la place de ses chemins en dur d'origine — propre à chaque script importé, jamais un contrat générique. Blocklist par défaut : `var/lib/waf/magnet-blocklist.txt` (le script y écrit ; un ancien `secure/waf/magnet-blocklist.txt` est repris une fois). Un chemin choisi à la main doit rester inscriptible par le compte du service, sinon les bans sont perdus sans message.
  - *À noter :* Les dossiers parents sont créés automatiquement à l'usage réel, jamais lors d'un simple `config check`.

- **Vérifier la compatibilité**
  - *En clair :* Exécute RÉELLEMENT le script avec les valeurs du formulaire en cours de saisie — scan statique (membres `lighty.X` non supportés) + exécution réelle sur une requête de test bénigne.
  - *À utiliser :* Avant d'activer un script importé en production — répond à "ce script est-il compatible ?" sans rien écrire sur disque.

> **⚠️ Piège vérifié**
> - Un script importé peut référencer une fonctionnalité `lighty.*` non supportée par ce pont (reste toujours `nil` côté Lua) — toujours lancer "Vérifier la compatibilité" avant d'activer un nouveau script, surtout avec `on_error=fail-closed` (sinon, une seule incompatibilité peut bloquer du trafic légitime).
> - Dépendance optionnelle `lupa` (`pip install -e ".[magnet]"`), jamais installée par défaut — son absence est signalée par le registre des capacités (`waf-magnet`) avec la commande exacte.
> - Le script peut écrire `lighty.header`/`lighty.content` sans planter, mais ce n'est JAMAIS relu ni renvoyé au visiteur : Omega-Serv rend toujours sa propre page d'erreur générique.

## 🔎 Audit, sauvegarde & aide — 6 fiches

Les écrans de vérification, de protection et d'assistance.

### 🔎 Audit de sécurité

*Accueil →*

Vérifications consultatives non bloquantes (service, rotation, mode WAF, TLS, CSP, méthodes, timeouts, uploads, permissions, certificats...).

> **💡 Codes de sortie**
> `0` = rien de grave · `1` = au moins un CRITICAL · `2` = au moins un HIGH sans CRITICAL · `3` = erreur d'exécution.

### ✅ Vérifier la configuration

*Configuration détaillée →*

Vérifie la configuration en deux couches : structurelle (déjà vérifiée au chargement) puis environnement réel (fichiers présents, permissions...).

> **💡 À savoir**
> Purement consultatif — ne modifie jamais rien. Utile avant de démarrer ou après toute modification importante.

### 💾 Sauvegarde / restauration

*Accueil →*

Créer, lister, restaurer ou supprimer des sauvegardes complètes de la configuration.

- **Inclure les règles WAF**
  - *En clair :* Ajoute les règles WAF et la liste de blocage à la sauvegarde.

- **Inclure les zones d'authentification**
  - *En clair :* Ajoute users.json/zones.json (SECRETS RÉELS : hash de mots de passe) — demande une confirmation explicite supplémentaire.

- **Inclure les certificats**
  - *En clair :* Ajoute les certificats TLS (CLÉS PRIVÉES INCLUSES) — demande une confirmation explicite supplémentaire.

- **Inclure Active Defense**
  - *En clair :* Ajoute la base sqlite de menaces/incidents/affectations. Jamais de secret en clair, donc pas de confirmation renforcée requise.

- **Restaurer**
  - *Ce qui se passe :* **écrase** Écrit directement les fichiers visés aux mêmes emplacements. Nécessite TOUJOURS un redémarrage complet par prudence.

- **Supprimer**
  - *En clair :* Supprime définitivement une sauvegarde (confort TUI, n'existe pas côté CLI).

### ❓ Aide — Guide

*Touche `a`*

Menu complet du guide intégré, avec navigation identique à celle de l'application.

- **Touche `F1`**
  - *En clair :* Ouvre directement la fiche de l'écran actif, sans passer par le menu.

### 💡 Aide — FAQ

*Touche `a` → FAQ*

Questions fréquentes avec réponses concrètes, orientées pièges réels.

### 📖 Aide — Par écran

*Touche `a` → Par écran*

Fiches détaillées pour chacun des 75 écrans de l'application, avec exemples concrets.

> **💡 À savoir**
> Chaque fiche documente : définition de l'écran, champs à remplir avec exemples, action déclenchée, et réaction attendue (rechargement, redémarrage ou aucun effet).

### 🎛️ Options (menu actif)

*Configuration détaillée → Voir options actives*

Active ou désactive les options superposables (14 options connues).

- **Les 14 options**
  - *Liste :* dirlisting, waf, auth, fastcgi, aliases, redirects, rewrites, cache, trusted_proxy, upload, error_pages, access_control, reverse_proxy, active_defense.

- **Réaction selon l'option**
  - *Rechargement simple :* La plupart.
  - *Redémarrage complet :* Première activation de fastcgi/reverse_proxy (leur client est construit au démarrage). active_defense exige TOUJOURS un redémarrage.

> **⚠️ Piège classique**
> - Activer une option ne suffit jamais à elle seule : sans un rechargement (ou redémarrage) du service déjà lancé, rien ne change réellement.

## ❓ FAQ — questions fréquentes — 44 fiches

Les questions qui reviennent le plus souvent, avec des réponses concrètes — la plupart du temps, ce sont des pièges déjà rencontrés par d'autres utilisateurs.

**J'ai activé/modifié une option, mais rien ne change sur le serveur — pourquoi ?** _Redémarrage_

Le serveur tourne dans un **processus déjà lancé**, séparé de l'interface. Écrire un changement dans la configuration ne le fait jamais relire tout seul : il faut soit le **recharger** (SIGHUP, écran SERVICE → Recharger — léger, aucune coupure), soit le **redémarrer complètement** (coupe toutes les connexions en cours). La plupart des écrans déclenchent désormais ce rechargement automatiquement dès qu'un service systemd actif est détecté.

**Comment savoir si un changement précis a besoin d'un rechargement ou d'un redémarrage complet ?** _Redémarrage_

La réaction exacte de chaque champ est indiquée dans sa fiche via `F1`. En règle générale : tout ce qui touche le socket d'écoute (adresse, port, listen_backlog), le contexte TLS, ou un composant construit une seule fois au démarrage (client FastCGI/reverse proxy à la première activation, Active Defense) exige un redémarrage complet. Tout le reste se recharge à chaud.

**Le rechargement/redémarrage automatique ne s'est pas déclenché — pourquoi ?** _Redémarrage_

Le déclenchement automatique ne fonctionne que si un gestionnaire de service système est reconnu ET qu'un service est réellement actif pour ce répertoire. Si vous faites tourner le serveur via l'assistant ("Lancer maintenant", sans service installé), aucun rechargement automatique n'est possible — relancez manuellement, ou installez le service depuis l'écran SERVICE.

**Juste après "Installer l'unité", l'écran État & Ressources affiche "Arrêté" alors que le service tourne — pourquoi ?** _Service_

L'installation crée un compte système dédié et ajoute votre session au groupe correspondant, mais l'appartenance à un **nouveau** groupe Unix ne s'applique jamais à une session déjà ouverte. Déconnectez-vous puis reconnectez-vous **une seule fois** — l'écran affichera alors l'état réel. En attendant, vérifiez via l'écran SERVICE ou `systemctl status`.

**Le champ "Nom du service" ne correspond pas à ce que je pilote ailleurs — pourquoi ?** _Service_

Ce champ persiste une préférence d'interface, distincte de la configuration serveur. Si cette instance est enregistrée en multi-instance, le nom est **figé** — jamais improvisé ici. Une interface peut piloter n'importe quelle unité installée en tapant simplement son nom exact.

**Puis-je installer une seconde unité systemd qui pointe vers le même répertoire, sous un autre nom ?** _Multi-instance_

Non — deux garde-fous bloquent explicitement cette situation : une unité différente pointant déjà vers ce répertoire (partagerait silencieusement var/, la configuration et le compte système dédié), et un nom déjà utilisé par une unité pointant ailleurs (volerait ce nom, écrasant l'unité existante). Pour héberger plusieurs serveurs, utilisez Multi-instance : chaque instance a son propre répertoire, sa propre configuration et son propre compte système.

**La création d'une nouvelle instance échoue à l'étape 4/6 (Installation des dépendances) — pourquoi ?** _Multi-instance_

Piège réel corrigé : si le message d'échec mentionne `omega-lib` et `No matching distribution found`, c'était un bug de la création d'instance. Corrigé : la nouvelle instance réutilise désormais la même source qu'omega-lib déjà installée pour l'instance en cours. Si l'échec persiste, vérifiez que le réseau est disponible pour les autres dépendances (`textual`, `pyte`, `jinja2`, `psutil`).

**Le WAF est actif mais ne bloque jamais rien — pourquoi ?** _WAF_

Vérifiez d'abord l'écran WAF — État : si "Packs de règles référencés" est à zéro, le WAF ne peut **rien** détecter même actif. Ajoutez au moins un pack depuis WAF — Modules. Vérifiez ensuite le mode : `log-only` journalise sans jamais bloquer, seul `block` bloque réellement.

**J'ai activé l'option "active_defense" mais rien ne se passe jamais — pourquoi ?** _Active Defense_

Activer l'option elle-même ne suffit PAS. Un second interrupteur, `war_mode.enabled`, vaut **false** par défaut — activez-le depuis Active Defense → Réglages → "Mode guerre actif". Vérifiez la ligne "Mode guerre" sur l'écran Active Defense — État : si elle affiche "inactif", c'est la cause. Un **redémarrage complet** est ensuite nécessaire. Une fois actif, tout devient automatique.

**J'ai créé une règle WAF personnalisée mais elle ne se déclenche jamais — pourquoi ?** _WAF_

Utilisez l'écran WAF — Règles personnalisées (pas "Modules") pour **créer** la règle elle-même — il l'écrit dans custom.json ET référence automatiquement ce pack. Ajouter seulement le pack comme référence depuis "Modules" ne crée aucune règle si le fichier est vide. Utilisez l'écran "Tester une requête" pour vérifier qu'une règle se déclenche bien avant de compter dessus.

**Quelle classe d'attaque choisir pour un profil de leurre ?** _Deception_

Les 8 classes possibles : **scan** (sondage d'URLs/ports), **credential_stuffing** (essais massifs de mots de passe), **sqli** (injection SQL), **xss** (script injecté), **path_traversal** (sortie du dossier servi, ex : ../../etc/passwd), **upload_probe** (upload suspect), **api_probe** (sondage d'endpoints /api/), **unknown** (filet de sécurité). Exemple : `fake_admin` avec `scan,credential_stuffing` attirera les scanners et tentatives de bruteforce vers une fausse page d'authentification.

**Mon profil de leurre en isolation "fixture" ne se déclenche jamais — pourquoi ?** _Deception_

Le NOM du profil doit correspondre EXACTEMENT à l'une des 4 fixtures réellement implémentées : `fake_admin`, `fake_cms`, `fake_api`, `fake_secrets`. Tout autre nom faisait auparavant que le leurre ne se déclenchait jamais, sans aucune erreur visible. L'écran refuse désormais d'enregistrer un tel nom.

**J'ai créé une zone de leurre avec une adresse qui n'existe pas encore — que se passe-t-il ?** _Deception_

Rien de spécial à l'enregistrement : une zone de leurre (Niveau 2) est une simple cible réseau (host:port), jamais un dossier — aucune création automatique, aucune vérification au moment de la sauvegarde. La conséquence n'apparaît que lors d'une **vraie requête** routée vers cette zone : si rien n'écoute, l'attaquant reçoit simplement une erreur HTTP 502 — jamais de crash, jamais de création silencieuse.

**J'ai régénéré/révoqué le certificat TLS mais le serveur sert toujours l'ancien — pourquoi ?** _TLS_

Le contexte SSL n'est construit qu'**une seule fois** au démarrage du serveur, jamais retouché par un simple rechargement. Régénérer ou révoquer un certificat pendant que TLS est déjà actif nécessite TOUJOURS un redémarrage complet pour que le changement soit pris en compte, même si le fichier sur disque a déjà changé.

**Comment m'auto-héberger avec un vrai certificat public, de bout en bout (schéma DDNS → Certbot → Omega-Serv) ?** _TLS_

Le schéma complet : un service DDNS (Dynu ou équivalent) fait pointer un nom de domaine public vers votre IP, mis à jour automatiquement par leur client à chaque changement — **entièrement hors du périmètre d'Omega-Serv**, à installer et configurer vous-même. Vous devez aussi rediriger les ports 80 et 443 de votre routeur/pare-feu vers cette machine. Une fois cela fait : **Assistant Let's Encrypt** (Configuration détaillée → TLS) obtient le premier certificat (défi HTTP-01, webroot), l'importe et vous rappelle d'activer TLS puis de redémarrer. Ensuite, **Renouvellement automatique** (même sous-menu) installe la planification (timer systemd ou crontab) qui renouvelle et redémarre tout seul, sans plus jamais intervenir manuellement pour cette partie.

**Omega-Serv tourne dans un conteneur — comment obtenir un certificat Let's Encrypt ?** _TLS_

N'exécutez PAS l'assistant Let's Encrypt/le renouvellement automatique à l'intérieur du conteneur qui sert déjà le trafic public. Exécutez-les sur l'hôte (ou dans un conteneur/sidecar distinct dédié à l'administration) en partageant avec le conteneur serveur : le même volume de webroot (Certbot y dépose son défi, que le conteneur sert déjà via le port 80 qu'il expose), et le même volume `secure/certificates/` — le conteneur serveur peut monter ce dernier en **lecture seule**, puisque l'import du certificat (écriture) se fait toujours côté hôte/sidecar. Un redémarrage du conteneur serveur reste nécessaire après chaque renouvellement (le contexte SSL n'est jamais rechargé à chaud) — le hook de renouvellement redémarre le service qu'il connaît (hôte/sidecar), pensez à l'adapter si le conteneur serveur est piloté séparément (ex. `docker restart`) plutôt que par un service systemd/OpenRC/runit classique.

**L'assistant Let's Encrypt échoue (défi HTTP-01) — pourquoi ?** _TLS_

Les causes les plus fréquentes, dans l'ordre à vérifier : (1) le port 80 n'est pas réellement joignable depuis Internet (redirection de port manquante ou incorrecte sur le routeur/pare-feu, ou un autre service occupe déjà ce port), (2) le domaine ne pointe pas encore vers cette IP (DNS/DDNS pas encore propagé — vérifiez avec `dig`/`nslookup` depuis une machine externe), (3) en mode test (staging, coché par défaut) tout fonctionne mais le certificat obtenu n'est jamais reconnu par les navigateurs — c'est normal, décochez la case une fois le domaine et le webroot vérifiés. Le message d'erreur affiché est directement celui renvoyé par Certbot.

**Mes sauvegardes de configuration sont-elles chiffrées ?** _Sauvegarde_

Non, jamais par défaut. Si vous incluez les zones d'authentification (hash de mots de passe) ou les certificats (clés privées TLS), la sauvegarde contient des secrets réels en clair — une confirmation explicite supplémentaire est demandée avant de créer ce type de sauvegarde. Protégez ces fichiers comme n'importe quel secret.

**J'ai mis à jour le code d'Omega-Serv (nouvelle archive, correctif appliqué) mais rien ne change jamais, même après un rechargement (SIGHUP) — pourquoi ?** _Redémarrage_

Piège réel rencontré (2026-10-10) : le rechargement à chaud (SIGHUP, écran SERVICE → Recharger) ne relit QUE certains éléments de configuration (règles WAF, zones d'authentification) — il ne recharge JAMAIS le code Python lui-même, qui reste celui chargé en mémoire depuis le DERNIER démarrage du processus. Après une mise à jour du code, un **redémarrage complet** est toujours nécessaire (`systemctl restart <service>`), jamais un simple rechargement. Vérifiez `systemctl status <service>` : une date de démarrage plus ancienne que votre mise à jour confirme immédiatement ce diagnostic.

**Comment bloquer les chemins sensibles (.env, .git, sauvegardes, consoles d'admin…) sans tout écrire à la main ?** _WAF_

Active Sécurité → Custom → Ajouter → **« CHARGER une liste de chemins (fichier) »**, puis la référence livrée `sensitive-paths-hostile` (298 chemins sans usage légitime) et/ou `sensitive-paths-probe` (132 chemins de sondage, parfois servis par un vrai site). Les réglages conseillés se remplissent seuls ; gardez Observation au premier chargement. Rien n'est actif avant le clic sur Charger.

**Quelle différence entre une règle personnalisée et une liste ?** _WAF_

Une règle détecte **un** motif et vit dans `custom.json`. Une liste est un fichier texte d'un chemin (ou mot-clé) par ligne, facile à maintenir à plusieurs centaines d'entrées, avec ses exceptions `!/x`, sa gravité et sa propre récidive. Les deux apparaissent dans le même tableau de l'écran Custom, colonne Type.

**J'ai chargé une liste en Observation — comment savoir ce qu'elle aurait bloqué, puis l'activer ?** _WAF_

En Observation, chaque détection est écrite dans le journal d'alertes WAF, sans blocage ni ban. Lisez ces alertes quelques jours, utilisez **Vérifier contre mes logs** dans l'éditeur pour repérer les lignes qui toucheraient des requêtes légitimes (exception `!/chemin` en un clic), puis **Custom → Modifier → Gravité Élevé ou Moyen**.

**Mes propres machines (Wi-Fi, Ethernet, Tailscale) risquent-elles d'être bannies par la récidive ?** _WAF_

Non : l'hôte local, le réseau Tailscale (`100.64.0.0/10`) et le réseau local (`192.168.x`, `10.x`, `172.16-31.x`…) ne sont **jamais** bannis automatiquement (`options.waf.reputation.never_auto_block`). Seule une adresse publique peut l'être. Leurs requêtes vers un chemin dangereux restent refusées (403) et journalisées, ce qui permet de tester le WAF. Derrière un proxy local, l'exemption de `127.0.0.1` n'est appliquée que si **Proxy de confiance** est actif — sinon tout Internet paraîtrait venir de `127.0.0.1`.

**Mettre mes adresses dans « Proxy de confiance » évite-t-il qu'elles soient bannies ?** _WAF_

Non. Les réseaux de confiance disent seulement **qui** a le droit de transmettre la vraie adresse du visiteur (en-tête `X-Forwarded-For`) — en pratique le proxy placé devant omega-serv (`127.0.0.1` pour `tailscale serve`). Ils n'exemptent de rien d'autre. Les réseaux à ne jamais bannir sont un réglage distinct (`never_auto_block`). Une plage large comme `100.0.0.0/8` contient des adresses publiques : préférez `100.64.0.0/10`.

**J'ai modifié une liste mais le serveur ne l'applique pas — pourquoi ?** _WAF_

Le message affiché après **Enregistrer et appliquer** donne la raison : la liste n'est pas encore chargée dans le WAF (assistant → Charger) ; la vérification a trouvé un problème (le serveur garde alors ses règles actuelles, rien n'est rechargé à moitié) ; le compte du service ne peut pas lire le fichier (**Corriger les droits**) ; ou aucun service actif — relancez le serveur lancé à la main.

**J'ai activé le script magnet mais le serveur refuse de démarrer / l'écran signale "lupa" absent — pourquoi ?** _WAF — Magnet_

Le magnet est un extra OPTIONNEL, jamais installé par défaut : `pip install -e ".[magnet]"` (dépendance `lupa`, liaison Lua embarquée — aucun interpréteur Lua système requis). Son absence est signalée par le registre des capacités (capacité `waf-magnet`, écran Capacités) avec la commande exacte, et bloque le démarrage si `options.waf.magnet.enabled` est actif sans cette dépendance — jamais un échec silencieux.

**Le but du magnet, c'est d'écrire un nouveau WAF en Lua ?** _WAF — Magnet_

Non — c'est l'inverse : importer un script WAF `mod_magnet` Lighttpd EXISTANT, écrit à l'origine pour un autre site, SANS le réécrire. Le pont `lighty.*` reproduit le modèle d'exécution réel de Lighttpd plutôt qu'un contrat inventé par Omega-Serv. Le natif reste TOUJOURS actif en parallèle : le magnet est un renfort additif, il ne peut jamais lever un blocage déjà décidé par le natif.

**Comment savoir si un script magnet importé est compatible AVANT de l'activer en production ?** _WAF — Magnet_

Écran Active Sécurité → WAF → Magnet, bouton "Vérifier la compatibilité" (ou `omega-serv waf test` en CLI) — exécute RÉELLEMENT le script avec les valeurs du formulaire en cours de saisie. Deux contrôles combinés : un scan statique signale toute référence `lighty.X` non supportée ; un smoke test exécute le script pour de vrai sur une requête de test bénigne. Les deux s'affichent comme avertissements explicites.

**J'ai activé un script magnet avec on_error="fail-closed" et maintenant du trafic légitime se fait bloquer — pourquoi ?** _WAF — Magnet_

`fail-closed` bloque TOUTE requête qui déclenche une erreur du script (incompatibilité, exception Lua, timeout) — dangereux combiné à un script jamais vérifié au préalable. Lancez "Vérifier la compatibilité" avant d'activer fail-closed en production. En cas de doute, repassez `on_error` à `ignore` (le défaut) : le trafic continue d'être traité par le natif seul si le magnet échoue.

**Les logs/la blocklist de mon script magnet importé n'apparaissent jamais sur le disque — pourquoi ?** _WAF — Magnet_

Un script `mod_magnet` écrit typiquement ses logs/sa blocklist à des chemins ABSOLUS en dur, propres à son site d'origine. La dissociation se fait via `options.waf.magnet.paths`, injectés dans le script comme table Lua globale `omega_magnet_paths` — seule une COPIE adaptée du script (les 5 lignes de configuration modifiées pour lire cette table, avec repli sur le chemin en dur d'origine si absente) en bénéficie. `secure/waf/scripts/waf.lua` est livré comme exemple minimal de cette technique.

**Mon script magnet écrit une page HTML personnalisée (lighty.content) en cas de blocage — pourquoi je ne la vois jamais ?** _WAF — Magnet_

Choix délibéré : le moteur WAF (natif ou magnet) rend TOUJOURS une décision, jamais une page HTML — c'est le serveur qui rend systématiquement sa propre page d'erreur générique. Les écritures `lighty.header`/`lighty.content` sont acceptées (le script ne plante jamais pour les avoir faites) mais jamais relues ni renvoyées au visiteur.

**J'ai ajouté une zone CSP pour un dossier, et maintenant ce dossier semble avoir perdu d'autres protections — pourquoi ?** _Sécurité — CSP_

Une zone CSP REMPLACE ENTIÈREMENT la politique par défaut pour son préfixe — jamais une fusion. Une zone qui ne contient que `style-src 'self' 'unsafe-inline'` fait disparaître toutes les AUTRES directives sous ce préfixe. L'assistant d'ajout de zone existe exactement pour éviter ce piège : chaque directive y est pré-remplie avec sa valeur ACTUELLE (la politique globale), à modifier uniquement là où c'est nécessaire.

**Comment autoriser "unsafe-inline" uniquement pour un dossier précis, sans affaiblir le reste du site ?** _Sécurité — CSP_

Zones CSP (`security.csp_zones`, écran Sécurité générique) : une exception EXPLICITE par préfixe de chemin, jamais une relâche globale. L'assistant d'ajout détecte toute directive relâchée et exige une confirmation explicite supplémentaire. Cette zone reste ensuite TOUJOURS visible dans `omega-serv audit security` (règles CSP-001/CSP-002, qui scannent aussi les zones) — même délibérée, jamais silencieuse.

**Pourquoi Cross-Origin-Embedder-Policy reste à "unsafe-none" même en profil hardened ?** _Sécurité — CSP_

Choix délibéré, différent de `Cross-Origin-Opener-Policy`/`Cross-Origin-Resource-Policy` (toujours `same-origin`, sans risque réel) : une valeur stricte peut bloquer des ressources cross-origin (polices, images, iframes tiers) propres au contenu réellement servi, qu'un serveur générique ne connaît jamais à l'avance. Le header reste néanmoins toujours émis explicitement, même à cette valeur permissive. Réglable via `security.coep_mode` si vous connaissez le contenu servi.

**Le listing de répertoire perd tout son style visuel depuis que j'ai une CSP stricte — pourquoi ?** _Sécurité — CSP_

Corrigé (2026-10-10) : le CSS du listing est désormais servi en fichier EXTERNE réservé plutôt qu'inline dans le HTML — `style-src 'self'` (politique par défaut) autorise déjà une feuille de style de même origine, sans besoin d'aucune exception. Si ce problème persiste après mise à jour, voyez la question sur le redémarrage après mise à jour du code ci-dessus : un simple rechargement (SIGHUP) ne suffit jamais à appliquer un changement de code.

**Quelle est la différence entre le "reverse proxy sortant" et `server.tls.mode = "behind_proxy"` ? Les deux parlent de proxy...** _Reverse Proxy_

Ce sont deux mécanismes INVERSES, qui ne s'activent jamais ensemble pour le même usage. `behind_proxy` : Omega-serv est **DERRIÈRE** un reverse proxy tiers (nginx, Caddy...) qui le protège — il fait confiance aux en-têtes `X-Forwarded-*` envoyés par ce proxy amont. Reverse proxy sortant (§7a) : Omega-serv agit lui-même comme proxy **DEVANT** un ou plusieurs backends HTTP/HTTPS qu'il relaie. Confondre les deux revient à faire confiance à des en-têtes `X-Forwarded-*` qui n'existent pas, ou à l'inverse écraser ceux d'un vrai proxy amont.

**Un de mes upstreams de reverse proxy bascule DOWN puis UP sans arrêt (flapping) — pourquoi ?** _Reverse Proxy_

La santé passive utilise des seuils de bascule DOWN et UP **distincts**, justement pour limiter ce comportement — un upstream instable qui échoue puis réussit immédiatement en alternance peut tout de même dépasser les deux seuils en boucle sur un backend réellement capricieux. Augmentez les seuils (nombre d'échecs/succès consécutifs requis) depuis l'écran Reverse Proxy, ou activez la santé active (sonde périodique indépendante du trafic réel) qui donne une mesure plus stable que les échecs du trafic live.

**Le cache du reverse proxy ne sert jamais mes réponses, même en rechargeant plusieurs fois la même page — pourquoi ?** _Reverse Proxy_

Plusieurs causes possibles, toutes volontaires : seules les méthodes GET/HEAD sont mises en cache (jamais POST/PUT/DELETE), une réponse d'erreur n'est JAMAIS mise en cache, une réponse avec `Set-Cookie` ne l'est pas non plus sauf opt-in explicite par zone, et le cache respecte l'en-tête `Cache-Control` envoyé par votre backend lui-même (un backend qui renvoie `no-store` ou `private` empêche la mise en cache, par construction). Vérifiez l'en-tête `X-Omega-Cache` sur la réponse (HIT/MISS/BYPASS) pour diagnostiquer précisément quel cas s'applique, et l'écran dédié *Cache du reverse proxy* pour la supervision.

**Je vois "vide" sur un log dans un viewer ou dans lnav — le serveur a-t-il un problème ?** _Logs_

Pas forcément un bug : un viewer qui affiche "vide" reflète fidèlement un fichier réellement vide sur le disque (0 octet) — par exemple `access.log` avant toute requête réelle reçue par le serveur, ou un log natif dont le module correspondant n'a jamais été activé. Vérifiez la colonne "Taille" dans la Bibliothèque : si elle affiche 0, le comportement est normal, pas un défaut du viewer.

**Le viewer "Simple" de la Bibliothèque n'affichait que les statistiques HTTP, jamais le tableau des lignes parsées — bug connu ?** _Logs_

Piège réel corrigé (2026-10-15) : le panneau de statistiques, sans largeur fixe dans la feuille de style, s'étalait sur presque toute la largeur de l'écran et écrasait la table des lignes parsées à 1 colonne de large — invisible, pas absente. Corrigé en fixant la largeur du panneau de statistiques ; la table des entrées parsées est de nouveau pleinement visible à côté.

**Je clique sur "Lancer" pour un favori "lnav", mais ça ne fait qu'ouvrir l'écran de configuration lnav au lieu de lancer directement — pourquoi ?** _Logs_

Piège réel corrigé (2026-10-15) : un favori est censé lancer directement son viewer, ce qui fonctionnait déjà pour Simple/Classique mais pas pour lnav, qui n'arrivait que sur son écran de configuration (cases à cocher) sans se lancer tout seul — un clic supplémentaire était encore nécessaire, ce qui défaisait l'intérêt même d'un favori. Corrigé : un favori lnav lance désormais lnav immédiatement, sans clic de plus. Ce comportement reste volontairement différent pour "Voir les logs" → lnav, où arriver sur l'écran de configuration pour ajuster la sélection avant de lancer est le comportement voulu.

**lnav reste sur un écran noir qui semble figé pendant plusieurs secondes sur un gros fichier — l'application a-t-elle planté ?** _Logs_

Non, pas un plantage : lnav indexe le fichier avant d'afficher quoi que ce soit, et rien côté Omega-Serv n'affiche d'indicateur de chargement pendant cette phase — l'écran noir est simplement l'attente de la première image envoyée par lnav. Plus le fichier est gros (des centaines de milliers de lignes, par exemple un log centralisé via une Source distante SSH), plus cette attente est longue. Patientez quelques secondes ; si l'écran ne revient vraiment jamais, c'est `Ctrl-Q` qui reste la sortie normale de lnav lui-même.

**Comment sont gérés le mot de passe ou la clé privée pour une Source distante (SSH) ?** _Logs_

Ils ne sont jamais gérés par Omega-Serv : aucun mot de passe n'est jamais demandé ni stocké, et une clé privée n'est référencée que par son CHEMIN sur le disque — jamais lue ni copiée dans la configuration. L'authentification reste entièrement déléguée à votre propre `ssh`/`scp` système et à sa configuration habituelle (agent SSH, `~/.ssh/config`), exactement comme si vous tapiez la commande vous-même dans un terminal.

**Pourquoi les Sources distantes ne proposent que SSH, et pas Samba ?** _Logs_

Choix délibéré documenté dans l'étude de faisabilité dédiée : SSH est quasi toujours déjà présent sur un backend Linux déjà administré, avec un modèle d'authentification déjà éprouvé (clé publique) ne demandant à Omega-Serv aucune nouvelle responsabilité de gestion de secrets. Samba exigerait un service CIFS dédié en plus côté backend, et reste documenté comme option de repli — à n'introduire que si un besoin réel et concret se présente (parc mixte Windows, Samba déjà en place), jamais par anticipation.

## 📎 Annexes (aide) — 2 fiches

Commandes utiles et glossaire.

### Commandes utiles étendues

```
# Initialiser et vérifier
./omega-serv.sh config init
./omega-serv.sh config check
./omega-serv.sh config show

# Profils
./omega-serv.sh profile list
./omega-serv.sh profile show hardened
./omega-serv.sh profile apply hardened --dry-run

# Options./omega-serv.sh option list
./omega-serv.sh option enable waf
./omega-serv.sh option disable waf

# Simuler une requête
./omega-serv.sh simulate-request GET /index.html

# WAF
./omega-serv.sh waf test --method GET --path /admin --remote-ip 203.0.113.1
./omega-serv.sh blocklist list
./omega-serv.sh blocklist add --network 203.0.113.0/24 --reason "scan détecté" --duration-seconds 3600
./omega-serv.sh blocklist remove --network 203.0.113.0/24

# Active Defense
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

# Certificats TLS - auto-signé
./omega-serv.sh certs generate-self-signed --cn localhost --san-dns localhost --san-ip 127.0.0.1
./omega-serv.sh certs show
./omega-serv.sh certs check-expiry --warn-days 30

# Certificats TLS - CA locale
./omega-serv.sh certs generate-ca --cn "Mon CA locale" --days 3650
./omega-serv.sh certs generate-csr --cn serveur.local --san-dns serveur.local --key-out server.key --csr-out server.csr
./omega-serv.sh certs sign-csr --csr server.csr --ca-key secure/certificates/ca/root-ca.key --ca-cert secure/certificates/ca/root-ca.pem --out server.pem --fullchain-out fullchain.pem
./omega-serv.sh certs revoke --cert server.pem --ca-key secure/certificates/ca/root-ca.key --ca-cert secure/certificates/ca/root-ca.pem

# Authentification
./omega-serv.sh auth add-user --username alice
./omega-serv.sh auth create-zone --url-prefix /admin/ --allowed-users alice
./omega-serv.sh auth list

# Audit
./omega-serv.sh audit security --format text --min-severity medium

# Sauvegarde
./omega-serv.sh config backup --description "avant migration"
./omega-serv.sh config backup --include-auth --include-certificates --confirm-secrets
./omega-serv.sh config backup --include-active-defense --description "menaces/incidents"
./omega-serv.sh config list-backups
./omega-serv.sh config restore --snapshot-id snapshot_20260908_170003_762484

# Service
./omega-serv.sh service install --user omega-serv --group omega-serv
./omega-serv.sh service start
./omega-serv.sh service status
./omega-serv.sh service restart
./omega-serv.sh service stop

# Diagnostics
./omega-serv.sh diagnostics
```

### Codes de sortie notables

| Commande | Code | Signification |
|---|---|---|
| `audit security` | 0 | Rien de grave (aucun `CRITICAL`/`HIGH`) |
| `audit security` | 1 | Au moins un finding `CRITICAL` |
| `audit security` | 2 | Au moins un `HIGH` sans `CRITICAL` |
| `audit security` | 3 | Erreur d'exécution (config introuvable...) |
| `certs check-expiry` | 1 | Certificat expiré |
| toute autre commande | 0/1 | Succès / échec de validation |

### Raccourcis clavier (TUI)

| Touche | Action |
|---|---|
| `↑` / `↓` | Naviguer entre les éléments d'un écran |
| `Tab` / `Maj+Tab` | Naviguer entre les champs d'un formulaire |
| `Échap` | Retour à l'écran précédent (confirmation de sortie sur l'accueil) |
| `t` | Thème suivant (appliqué immédiatement, sans confirmation) |
| `r` | Rafraîchir la détection du terminal |
| `F1` | Aide de l'écran actif (fiche contextuelle) |
| `a` | Guide d'aide complet (menu navigable + FAQ) |
| `o` | Réglages applicatifs (thème, profil de rendu, chemins) |
| `q` | Quitter (avec confirmation) |
| `Ctrl+P` | Palette de commandes (Thème, Capture d'écran, Options...) |

---
