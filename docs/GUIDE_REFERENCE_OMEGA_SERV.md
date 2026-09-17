# Omega-Serv — Guide de référence

> Guide complémentaire à l'aide intégrée de l'application. Il présente la philosophie du projet, les concepts importants, les parcours d'administration et des pratiques d'exploitation.

## Objectif du guide

Omega-Serv est un serveur HTTP/1.1 autonome, destiné principalement au contenu statique et, en option, à PHP-FPM/FastCGI. Son objectif n'est pas de rivaliser avec les serveurs C ou Go sur la performance brute ou les charges Internet massives : il propose une administration locale plus cohérente, accessible et défensive.

L'administration passe par deux interfaces fonctionnellement équivalentes : une CLI non interactive et scriptable, ainsi qu'une interface TUI Textual utilisable au clavier et à la souris. La configuration ne demande pas d'éditer manuellement les fichiers de configuration ; les commandes, formulaires et assistants appliquent les validations nécessaires avant l'écriture.

## À qui s'adresse Omega-Serv

Omega-Serv est adapté aux administrateurs Linux, développeurs et utilisateurs qui veulent gérer un service HTTP local avec une interface d'administration centralisée. Il est particulièrement pertinent pour un laboratoire, un accès VPN, un petit site statique, un service interne ou une petite installation PHP-FPM.

Pour une exposition Internet sensible, un trafic élevé ou une architecture distribuée, validez le comportement dans votre environnement et envisagez de placer Omega-Serv derrière un reverse proxy d'edge adapté. Les fonctions de sécurité intégrées complètent une architecture défensive ; elles ne remplacent ni la segmentation réseau, ni les mises à jour, ni la supervision externe.

## Guide intégré et guide référence

L'application inclut une aide contextuelle accessible avec `F1` depuis l'écran actif. La touche `a` ouvre le guide complet, sa navigation et sa FAQ ; le guide fourni le 14 septembre 2026 documente 65 écrans.

Ce document ne remplace pas ces fiches interactives. Il fournit une vue d'ensemble, explique les concepts transverses, relie les fonctions entre elles et propose des scénarios complets d'exploitation.

## Vue fonctionnelle

Omega-Serv regroupe plusieurs domaines d'administration dans une même application :

- **Serveur HTTP** : écoute, webroot, contenu statique, alias, redirections, réécritures, listing, pages d'erreur et cache.
- **Modules d'application** : TLS, authentification HTTP Basic, FastCGI/PHP-FPM, reverse proxy sortant et zones d'upload confinées.
- **Sécurité active** : WAF, liste de blocage, limitation de débit, réputation, Active Defense, deception et incidents.
- **Exploitation** : services système, logs, rotation, statistiques, état des ressources, audits, sauvegardes et multi-instance.
- **Interfaces** : CLI pour les scripts et la répétabilité ; TUI pour l'exploration, les formulaires, les assistants et l'aide contextuelle.

## Carte de navigation

Le menu principal organise les fonctions autour d'un cycle d'administration logique : préparer, configurer, vérifier, exploiter, observer et sauvegarder.

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

## CLI et TUI

La CLI et la TUI utilisent les mêmes cas d'usage afin d'éviter deux comportements divergents. Choisissez la CLI lorsque vous avez besoin d'automatiser, de versionner des procédures shell ou de rejouer une action de manière répétable.

Préférez la TUI lorsque vous découvrez les options, souhaitez une aide liée au contexte, voulez visualiser les logs et statistiques, ou devez remplir un formulaire avec validation guidée. Les actions sensibles et destructives demandent une confirmation explicite dans l'interface.

## Cycle d'administration conseillé

1. Créez une configuration avec l'assistant ou avec `config init`.
2. Choisissez un profil adapté au contexte, puis vérifiez le diff avant son application.
3. Activez uniquement les modules nécessaires, un par un.
4. Lancez `config check` avant de démarrer ou de modifier un service.
5. Installez un service sous un utilisateur et groupe dédiés, jamais en root.
6. Suivez les logs et l'écran État & Ressources après chaque changement significatif.
7. Exécutez régulièrement l'audit de sécurité et créez des sauvegardes avant les opérations importantes.

# Concepts essentiels

## Profils

Les profils apportent une base cohérente de paramètres. Ils ne doivent pas être interprétés comme une garantie de sécurité universelle : le réseau, le contenu servi, les permissions locales et le reverse proxy éventuel restent déterminants.

| Profil | Usage visé | Intention |
|---|---|---|
| `minimal` | Démonstration ou environnement local simple | Statique seul, options désactivées |
| `standard` | Site statique ou petite production | Base raisonnable avec protections usuelles |
| `hardened` | Exposition avec moindre privilège | Bind local recommandé et restrictions renforcées |
| `development` | Développement local | Bind loopback, diagnostic facilité, jamais destiné à Internet |

Lorsqu'un profil est appliqué, Omega-Serv fusionne les valeurs sûres intégrées, le profil choisi, les options déjà activées puis les réglages utilisateur explicites. Vérifiez systématiquement le diff présenté avant l'écriture.

## Rechargement et redémarrage

Un rechargement à chaud applique certaines modifications sans interrompre complètement le service. Dans Omega-Serv, les règles WAF et les zones d'authentification peuvent être rechargées par `SIGHUP` ; certains changements de configuration courante sont également appliqués selon le mécanisme de service utilisé.

Un redémarrage complet est nécessaire pour les éléments qui modifient le socket d'écoute, TLS ou Active Defense. Après chaque enregistrement dans la TUI, l'application doit indiquer explicitement si une action est appliquée à chaud, exige un redémarrage ou ne demande aucune action.

## Durcissement HTTP

Le noyau HTTP applique des contrôles qui ne sont pas proposés comme options désactivables. Ils incluent notamment la validation de l'en-tête `Host`, une liste explicite de méthodes autorisées, le rejet des ambiguïtés liées à `Content-Length` et `Transfer-Encoding`, ainsi que le rejet de `Expect: 100-continue`.

Les tailles de ligne et d'en-têtes sont limitées pendant la lecture, les en-têtes obsolètes repliés sont refusés, et les réponses reçoivent des en-têtes de sécurité ainsi qu'une CSP de base. La résolution de chemin vise à protéger le service statique contre traversal, double encodage et cas sensibles liés aux liens symboliques.

## Modules optionnels

Les modules ne sont pas activés implicitement par les profils fournis, y compris `hardened`. Leur activation est un choix explicite, qui doit être précédé de tests fonctionnels et suivi d'une observation des logs.

| Module | Usage | Point d'attention |
|---|---|---|
| WAF | Signatures, rate limiting, blocklist CIDR, réputation | Commencer en observation et tester les faux positifs |
| TLS | Certificat auto-signé ou CA locale | La V1 ne fournit pas ACME, mTLS ou OCSP stapling |
| Authentification | HTTP Basic par zone | Réserver à des accès adaptés et utiliser TLS |
| FastCGI/PHP-FPM | Exécution PHP via PHP-FPM | Vérifier les permissions et séparer `script_root` du webroot |
| Reverse proxy sortant | Routage vers un ou plusieurs backends HTTP/HTTPS | Contrôler les upstreams, en-têtes et vérification TLS |
| Upload | Zones confinées avec quotas | Définir des tailles maximales réalistes et vérifier les permissions |
| Active Defense | Deception, incidents, journaux enrichis et IoC | Traiter les actions comme un dispositif défensif observé et testé |

## WAF

Le WAF peut utiliser des signatures, des détections de chemins ou user-agents sensibles, des signaux d'injection, une limitation de débit, une blocklist CIDR et une logique de réputation. Son rôle est de fournir une couche applicative supplémentaire autour du serveur HTTP.

Le mode `log-only` est volontairement incapable de bloquer ; il sert à observer les décisions et à ajuster les règles sans impact sur les clients. Avant d'activer un comportement bloquant, utilisez le test de requête, consultez les logs et vérifiez les accès légitimes concernés.

## Active Defense

Active Defense exploite les signaux déjà produits par le WAF pour qualifier les sources et déclencher des actions défensives. Il ne remplace pas le pare-feu ni le blocage réseau : le module observe, enrichit, ralentit, oriente vers un leurre et construit des incidents exploitables.

Les niveaux de menace suivent une progression `normal`, `suspicious`, `hostile` et `contained`. Une source est identifiée par son IP et un hash du User-Agent ; le score décroît en l'absence de nouvel événement afin de limiter la persistance d'un contexte devenu obsolète.

## Deception

La deception peut orienter une source hostile ou contenue vers un leurre statique, par exemple `fake_admin`, `fake_cms`, `fake_api` ou `fake_secrets`. Les leurres de type `fixture` restent dans le processus et ne retournent que des gabarits fixes ; ils sont explicitement documentés comme une isolation faible.

Pour une isolation plus forte, utilisez une zone de leurre de type `proxy` qui pointe vers un backend distinct déjà exploité dans un processus séparé. Vérifiez toujours que le backend est joignable et distinct des zones de production : en cas d'upstream indisponible, la réponse attendue est une erreur HTTP au client, jamais un crash du serveur.

## TLS et certificats

Omega-Serv gère TLS direct via un certificat auto-signé ou une CA locale. Le certificat auto-signé convient principalement au local, au laboratoire, à un VPN ou à un environnement où les clients peuvent accepter explicitement le certificat ou faire confiance à votre CA locale.

Une CA locale permet de signer plusieurs certificats serveur à destination d'appareils dont vous contrôlez le magasin de confiance. La clé privée de l'autorité est l'élément le plus sensible : conservez-la hors des sauvegardes non chiffrées, avec des permissions restrictives et une phrase de passe adaptée.

## Logs et monitoring

Les journaux incluent un log d'accès et un log d'erreurs. L'interface permet de consulter et suivre les fichiers, de gérer la rotation, de créer des archives et d'obtenir des statistiques telles que la répartition par code de statut, le débit, les IP uniques ou les principales IPs observées.

Le mode d'intégration `lnav` est optionnel et l'interface doit rester utilisable lorsqu'il n'est pas installé. Les automatisations de rotation enregistrées dans l'application sont déclaratives tant qu'un mécanisme externe — par exemple un timer systemd — n'est pas configuré pour les exécuter.

## Services système

Omega-Serv détecte systemd, OpenRC ou runit pour installer et piloter un service. L'installation doit s'effectuer avec un utilisateur et groupe dédiés ; le programme refuse de démarrer directement comme root.

Lorsqu'une unité systemd est générée, elle applique notamment `NoNewPrivileges`, `PrivateTmp`, `ProtectSystem=strict`, `ProtectHome`, un `UMask=0077`, des chemins d'écriture limités et un redémarrage sur échec. Vérifiez malgré tout les permissions réelles du webroot, des certificats, des journaux et des répertoires d'upload.

## Multi-instance

Une instance représente une installation séparée, avec sa configuration, son environnement Python, ses fichiers et son port. Le registre global permet d'identifier les installations connues et de basculer entre elles.

Utilisez une instance par projet ou par environnement — par exemple développement, démonstration et service interne. Ne créez pas plusieurs unités systemd pointant vers le même répertoire sous des noms différents : cela rend le statut, les redémarrages et les fichiers d'état ambigus.

## Sauvegardes

Une sauvegarde de configuration inclut la configuration de base. L'inclusion des zones d'authentification et des certificats est volontairement soumise à une confirmation supplémentaire, car ces données peuvent contenir des secrets utiles à un attaquant.

Les sauvegardes ne sont pas chiffrées par défaut. Stockez-les avec des permissions restrictives, dans un emplacement protégé, et testez périodiquement une restauration sur une instance de laboratoire.

# Scénarios pratiques

## Site statique interne avec WAF

**Objectif :** publier un site statique réservé à un réseau interne ou VPN, avec une configuration initiale sûre, des logs exploitables et une première couche WAF.

1. Lancez l'assistant de premier lancement depuis la TUI, ou initialisez la configuration avec :

```bash
./omega-serv.sh config init
```

2. Choisissez le profil `standard` pour un petit site, ou `hardened` si le service doit être placé derrière un reverse proxy et que ses contraintes correspondent à votre réseau. Examinez le diff avant application :

```bash
./omega-serv.sh profile show hardened
./omega-serv.sh profile apply hardened --dry-run
```

3. Configurez le bind, le port et le webroot depuis la TUI ou les commandes correspondantes. Vérifiez que le compte de service peut lire le contenu sans disposer de droits d'écriture inutiles.

4. Activez le WAF, commencez par le mode d'observation, puis vérifiez le comportement à l'aide de requêtes simulées et des logs :

```bash
./omega-serv.sh option enable waf
./omega-serv.sh waf test --method GET --path /admin --remote-ip 203.0.113.1
```

5. Vérifiez la configuration avant le démarrage :

```bash
./omega-serv.sh config check
```

6. Installez ensuite le service sous un utilisateur dédié, démarrez-le et consultez son statut :

```bash
./omega-serv.sh service install --user omega-serv --group omega-serv
./omega-serv.sh service start
./omega-serv.sh service status
```

7. Depuis Gestion des logs ou État & Ressources, observez les premières requêtes, les erreurs et les codes HTTP. Ajustez les règles avant d'envisager un mode WAF bloquant.

## TLS interne avec CA locale

**Objectif :** fournir HTTPS à plusieurs appareils internes sous votre contrôle, sans dépendre d'une autorité publique.

1. Vérifiez que `openssl` est présent et que le stockage prévu pour les certificats est correctement protégé.

2. Créez une CA locale. Si aucune phrase de passe n'est fournie, le programme demande une saisie interactive avec confirmation :

```bash
./omega-serv.sh certs generate-ca --cn "Mon CA locale" --days 3650
```

3. Générez la clé et la CSR du serveur, en définissant les noms DNS ou IP réellement utilisés par les clients :

```bash
./omega-serv.sh certs generate-csr \
  --cn serveur.local \
  --san-dns serveur.local \
  --key-out server.key \
  --csr-out server.csr
```

4. Signez la CSR avec la CA locale et produisez la chaîne complète :

```bash
./omega-serv.sh certs sign-csr \
  --csr server.csr \
  --ca-key secure/certificates/ca/root-ca.key \
  --ca-cert secure/certificates/ca/root-ca.pem \
  --out server.pem \
  --fullchain-out fullchain.pem
```

5. Activez TLS avec le certificat et la clé correspondants depuis la TUI ou via la commande de configuration. Lancez ensuite `config check`, puis redémarrez complètement le service : un changement TLS ne relève pas du rechargement à chaud.

6. Importez uniquement le certificat public `root-ca.pem` dans le magasin de confiance des clients. Ne distribuez jamais la clé privée `root-ca.key`.

## WAF : observer, tester, appliquer

**Objectif :** activer une protection sans bloquer par erreur les utilisateurs légitimes.

1. Activez le module WAF depuis Active Sécurité ou via la CLI :

```bash
./omega-serv.sh option enable waf
```

2. Utilisez le mode `log-only` lors de la phase de calibration. Ce mode est structurellement incapable de bloquer et permet d'observer les décisions sans perturber le service.

3. Testez les règles avec `waf test` ou l'écran de test de requête. Consultez les logs WAF et le log d'accès pour comparer la décision avec le comportement attendu.

4. Ajoutez une règle personnalisée uniquement lorsque sa portée, ses faux positifs potentiels et son mode d'action sont compris. Après une modification, vérifiez si l'interface demande un rechargement ou un redémarrage.

5. Passez progressivement à un mode bloquant pour des règles validées. Surveillez les erreurs applicatives, les taux de réponses 4xx/5xx et les retours utilisateurs après chaque changement.

## Active Defense : simulation avant activation

**Objectif :** comprendre et valider la réponse défensive avant d'appliquer une action réelle.

1. Activez l'option Active Defense depuis l'écran Active Sécurité ou via la CLI :

```bash
./omega-serv.sh option enable active_defense
```

2. Définissez le mode, les seuils, les actions et les profils de leurre. Commencez par `monitor` afin d'observer les qualifications sans déployer une réponse active.

3. Utilisez la simulation stricte pour vérifier le score, le niveau obtenu et les actions projetées. Cette opération n'écrit pas d'état et n'a aucun impact réseau :

```bash
./omega-serv.sh active-defense simulate \
  --ip 203.0.113.42 \
  --path /wp-login.php \
  --attack-class scan \
  --score 40
```

4. Si vous utilisez un leurre `fixture`, limitez-le à des réponses statiques plausibles et considérez explicitement son isolation comme faible. Pour une zone `proxy`, déployez d'abord un backend de leurre isolé, distinct de la production, puis vérifiez sa disponibilité.

5. En mode `enforce`, surveillez les incidents ouverts, le journal enrichi et les exports IoC. Les exports JSON, CSV ou rapports doivent être traités comme des éléments sensibles : ils peuvent contenir des informations utiles sur votre activité et vos détections.

## Seconde instance pour un autre projet

**Objectif :** héberger deux projets indépendants sans confondre leurs ports, services, logs ou configurations.

1. Ouvrez Multi-instance dans la TUI et lancez la création d'une instance, ou utilisez le parcours CLI équivalent si disponible.

2. Choisissez un répertoire distinct, non imbriqué dans l'installation existante, et un port qui n'est pas déjà utilisé.

3. Laissez l'outil créer un environnement virtuel propre et une configuration fraîche. En cas d'échec à l'étape des dépendances, vérifiez la connectivité nécessaire à l'installation, l'espace disque, les permissions et la version Python requise.

4. Configurez puis vérifiez la nouvelle instance indépendamment. Installez une unité de service qui cible exclusivement son répertoire et son utilisateur dédié.

5. Contrôlez le registre des instances et le statut du service avant toute bascule. Chaque instance doit conserver ses propres sauvegardes, certificats et fichiers de journalisation.

## Reverse proxy sortant

**Objectif :** exposer un chemin ou un hôte local qui relaie les requêtes vers un ou plusieurs backends HTTP/HTTPS internes, avec équilibrage round-robin et gestion des en-têtes.

1. Depuis la TUI, ouvrez **Configuration détaillée → Reverse proxy sortant**, ou utilisez les commandes CLI équivalentes.
2. Définissez une zone, par exemple :

   - `url_prefix = /api-interne/`  
   - Upstreams :  
     - `http://10.0.0.10:8080`  
     - `http://10.0.0.11:8080`  

3. Configurez les options :

   - Vérification TLS stricte pour les upstreams HTTPS (désactivable mais déconseillée).  
   - Retrait des en-têtes hop-by-hop.  
   - Écrasement systématique des en-têtes `X-Forwarded-*` (jamais de fusion avec ceux envoyés par le client).

4. Si vous voulez du WebSocket, configurez une zone dédiée avec un upstream fixe pour la durée du tube, sans timeout applicatif une fois établi.

5. Vérifiez la configuration :

```bash
./omega-serv.sh config check
```

6. Redémarrez complètement le service (changement de routage proxy). Testez depuis un client :

```bash
curl -i http://localhost/api-interne/health
```

7. Observez les logs d'accès et d'erreurs pour vérifier que le routage, les codes HTTP et les en-têtes sont conformes. Ajustez les upstreams ou les options en cas de 502/504.

## Upload confiné

**Objectif :** permettre l'envoi de fichiers sur un chemin précis, avec quotas, noms générés côté serveur et confinement strict hors du reste du webroot.

1. Depuis la TUI, ouvrez **Configuration détaillée → Upload**, ou utilisez les commandes CLI équivalentes.  
2. Créez une zone d'upload, par exemple :

   - `url_prefix = /uploads/`  
   - `upload_root` dans un répertoire dédié, hors du webroot statique principal.  
   - Quota par zone (par exemple 500 Mo).  
   - Taille maximale par requête (`max_request_size`) cohérente avec votre usage.

3. Choisissez la stratégie de nommage :

   - Noms générés côté serveur (recommandé) pour éviter les conflits et les injections de chemin.  
   - Extensions autorisées restreintes (par exemple images et documents courants).

4. Vérifiez les permissions :

   - Le compte de service doit pouvoir écrire dans `upload_root` mais pas ailleurs.  
   - Le handler statique ne doit jamais pouvoir lister ou servir les sources applicatives ou les fichiers sensibles.

5. Vérifiez la configuration :

```bash
./omega-serv.sh config check
```

6. Redémarrez le service si nécessaire, puis testez l'upload :

```bash
curl -X POST -F "file=@monfichier.pdf" http://localhost/uploads/
```

7. Consultez les logs pour vérifier les réponses (200/201/413/4xx) et ajustez quotas et tailles si vous observez des erreurs de taille ou des rejets inattendus.

# Exploitation et sécurité

## Checklist avant mise en service

- Utiliser un compte de service dédié, sans privilèges root.
- Choisir un webroot lisible mais non modifiable par le compte de service, sauf nécessité justifiée.
- Lancer `config check` avant le démarrage ou après toute modification importante.
- Exécuter `audit security` et traiter les constats critiques ou élevés.
- Mettre en place une rotation réelle des logs, par exemple avec logrotate ou un timer systemd si les automatisations déclaratives ne sont pas exécutées automatiquement.
- Créer une sauvegarde avant les opérations sensibles et protéger les archives contenant certificats ou données d'authentification.
- Tester les règles WAF en observation avant activation du blocage.
- Valider TLS depuis un client réel, y compris la chaîne de confiance, les SAN et la date d'expiration.
- Pour une exposition Internet, évaluer l'intérêt d'un reverse proxy d'edge, de restrictions réseau, de sauvegardes hors machine et d'une supervision externe.

## Audit régulier

L'audit de sécurité est informatif : il ne bloque pas le fonctionnement du serveur. Il rejoue certains contrôles bloquants comme constats critiques, puis évalue également des recommandations liées à TLS, CSP, méthodes HTTP, timeouts, uploads, permissions, certificats, service et taille des logs.

Exécutez-le après une installation, avant une exposition, après un changement de profil ou de TLS, et à intervalle régulier. Les codes de sortie permettent une intégration dans des scripts ou une supervision : `0` signifie l'absence de constat critique ou élevé, `1` indique au moins un constat critique, `2` au moins un constat élevé sans critique et `3` une erreur d'exécution.

```bash
./omega-serv.sh audit security --format text --min-severity medium
```

## Sauvegarde et restauration

Créez une sauvegarde avant une migration, une régénération de certificats, un changement de module ou une modification Active Defense significative :

```bash
./omega-serv.sh config backup --description "avant migration"
```

L'inclusion de certificats ou de données d'authentification demande une confirmation explicite, car les archives peuvent alors contenir des secrets. Testez la restauration sur une instance de laboratoire avant de dépendre d'une sauvegarde pour un rétablissement réel.

## Limites et périmètre

Omega-Serv est conçu comme un serveur HTTP/1.1 durci, orienté administration unifiée et sécurité applicative. Il ne vise pas à couvrir tous les cas d'usage des serveurs web généralistes.

**Fonctions hors périmètre en V1 :**

- CGI brut : seul FastCGI/PHP-FPM est supporté.  
- ACME, mTLS, OCSP stapling, CA externe et distribution CRL complète.  
- Cache HTTP partagé entre processus.  
- Mode batch ou surveillance récurrente intégrée : chaque commande est une action explicite ; les automatisations de rotation de logs sont déclaratives tant qu'un exécuteur externe (timer systemd, cron, etc.) n'est pas configuré pour les exécuter.  
- Extraction du module WAF en projet autonome `omega-waf` (prévue, jamais commencée).  
- Intégration à `omega-suite` : Omega-Serv agit sur la machine locale, pas sur des cibles distantes.  
- Active Defense : pas d'export STIX 2.1/MISP, pas de tests de charge dédiés, pas d'intégration réelle avec les événements de ban `omega-fire` (bloqué côté `omega-fire` qui n'expose pas de surface de lecture).

**Limites de performance et de concurrence :**

- L'objectif n'est pas la très haute concurrence ni les gros débits d'un serveur C ou Go spécialisé.  
- Python et asyncio imposent des contraintes en très haute charge ; Omega-Serv est adapté à des charges modestes à moyennes, en labo, VPN ou petit service interne.

**Limites de sécurité et de déploiement :**

- Le WAF et Active Defense sont des modules applicatifs complémentaires : ils ne remplacent pas un pare-feu réseau, un outil de prévention d'intrusion, la journalisation centralisée, une réponse à incident organisée ou les mises à jour régulières du système.  
- TLS repose sur `openssl` en sous-processus ; il n'y a pas d'ACME intégré en V1. Pour une exposition Internet, un reverse proxy d'edge gérant ACME peut être préférable.  
- Les leurres `fixture` sont explicitement documentés comme une isolation faible : même processus, même utilisateur OS que la production, acceptables uniquement parce qu'ils ne retournent que des gabarits statiques.

**Limites opérationnelles :**

- Pas de cache HTTP partagé entre processus.  
- Pas de fonction de scan/audit d'une cible distante : Omega-Serv s'audite lui-même, jamais un tiers.  
- Les automatisations de rotation de logs sont déclaratives tant qu'un mécanisme externe ne les exécute pas.

# Dépannage rapide

## Une modification semble sans effet

Vérifiez d'abord si l'action nécessitait un rechargement ou un redémarrage complet. Les changements concernant le bind, le port, TLS ou Active Defense nécessitent un redémarrage ; les zones WAF et d'authentification peuvent être rechargées à chaud selon le cas.

Exécutez `config check`, consultez les logs et vérifiez le statut du service. Dans la TUI, l'indication après enregistrement doit préciser la suite attendue.

## Le WAF est actif mais ne bloque rien

Le WAF peut être en mode `log-only`, qui ne bloque jamais par conception. Vérifiez son mode, les règles réellement activées, la portée des routes concernées et les résultats de `waf test` avant de conclure à un défaut.

## Active Defense ne semble pas agir

Active Defense dépend des signaux WAF et de seuils de qualification. Vérifiez que le module est activé, que le mode choisi n'est pas seulement `monitor`, que les scores atteignent les seuils configurés et que les profils de leurre correspondent à la classe d'attaque observée.

Utilisez toujours `active-defense simulate` avant de tester avec du trafic réel. Pour une zone de leurre en mode `proxy`, vérifiez aussi que le backend isolé est réellement joignable.

## Le certificat servi semble ancien

Une régénération, révocation ou modification TLS requiert un redémarrage complet du serveur. Vérifiez que la configuration pointe vers le bon certificat et la bonne clé, contrôlez les dates avec `certs check-expiry`, puis redémarrez le service.

## Les sauvegardes sont-elles chiffrées ?

Non, les sauvegardes ne sont pas chiffrées par défaut. Protégez-les par les permissions, le stockage, le chiffrement de votre infrastructure et des procédures de rétention adaptées, particulièrement lorsqu'elles incluent certificats ou zones d'authentification.

# Annexes

## Commandes utiles

```bash
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

## Glossaire

| Terme | Définition courte |
|---|---|
| ACME | Protocole d'émission et renouvellement automatisé de certificats, notamment utilisé par Let's Encrypt |
| Active Defense | Fonctions défensives basées sur les signaux WAF : qualification, ralentissement, leurres, incidents et IoC |
| CA locale | Autorité de certification contrôlée localement, dont le certificat public est importé sur les clients de confiance |
| CIDR | Notation permettant de représenter une adresse IP ou un réseau IP, par exemple `203.0.113.0/24` |
| CSP | Content Security Policy, en-tête HTTP qui aide à limiter certaines sources de contenu exécutables ou chargées |
| Deception | Mécanisme qui oriente une source hostile vers un leurre statique ou un backend isolé, afin d'observer et de qualifier son comportement |
| FastCGI | Protocole de communication entre le serveur web et un processus applicatif, ici notamment PHP-FPM |
| Incident | Objet Active Defense qui regroupe chronologie, décisions, IoC et exports pour une source ou un ensemble de sources suspectes |
| IoC | Indicator of Compromise : indicateur exploitable de comportement ou d'activité suspecte, tel qu'une IP ou un identifiant de requête |
| Mode guerre | Configuration Active Defense qui déclenche automatiquement un ensemble d'actions (ralentissement, rate limit, incident, deception, etc.) selon des seuils |
| Reverse proxy sortant | Configuration où Omega-Serv agit comme client proxy vers un ou plusieurs backends HTTP/HTTPS, avec équilibrage et gestion des en-têtes |
| Upload confiné | Zone dédiée à l'envoi de fichiers, avec quotas, noms générés côté serveur et isolation par rapport au reste du webroot |
| WAF | Web Application Firewall : couche de filtrage HTTP applicative |
