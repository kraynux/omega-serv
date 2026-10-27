<!-- Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE) -->

# omega-serv face aux serveurs web du marché

**Comparatif mesuré : nginx · lighttpd · Caddy · Apache · Traefik · omega-serv 2.0**

🌐 **Français** · [English](translation/en/comparatif-serveurs-web.md) · [Español](translation/es/comparatif-serveurs-web.md) · [Português (Brasil)](translation/pt-BR/comparatif-serveurs-web.md) · [Italiano](translation/it/comparatif-serveurs-web.md) · [Deutsch](translation/de/comparatif-serveurs-web.md) · [Nederlands](translation/nl/comparatif-serveurs-web.md) · [Polski](translation/pl/comparatif-serveurs-web.md) · [Русский](translation/ru/comparatif-serveurs-web.md) · [中文](translation/zh-CN/comparatif-serveurs-web.md) · [Tiếng Việt](translation/vi/comparatif-serveurs-web.md) · [ไทย](translation/th/comparatif-serveurs-web.md) · [Bahasa Indonesia](translation/id/comparatif-serveurs-web.md) · [日本語](translation/ja/comparatif-serveurs-web.md) · [한국어](translation/ko/comparatif-serveurs-web.md) · [हिन्दी](translation/hi/comparatif-serveurs-web.md) · [العربية](translation/ar/comparatif-serveurs-web.md)

Ce document situe omega-serv parmi les serveurs web les plus répandus. Il ne cherche pas à désigner un « meilleur serveur » : chaque outil répond à des besoins différents. Il donne trois choses :

1. des **mesures réelles**, faites sur la même machine, avec le même client et les mêmes fichiers, et reproductibles ;
2. un **comparatif des fonctions**, chacune vérifiée dans la documentation officielle de chaque serveur (liens en fin de document), en distinguant ce qui est intégré de ce qui demande un module ou un plugin ;
3. ce qu'omega-serv **apporte réellement de plus**, et ce que les autres font **mieux que lui**.

Tous les chiffres ci-dessous ont été mesurés le 26 octobre 2026. Aucun chiffre n'est repris d'un autre site ou estimé.

---

## Sommaire

1. [En bref](#1-en-bref)
2. [Méthode de mesure](#2-méthode-de-mesure)
3. [Performances : omega-serv face à nginx, lighttpd et Caddy](#3-performances--omega-serv-face-à-nginx-lighttpd-et-caddy)
4. [omega-serv 1.0 → 2.0 : ce qui a changé, mesuré](#4-omega-serv-10--20--ce-qui-a-changé-mesuré)
5. [Comparatif des fonctions](#5-comparatif-des-fonctions)
6. [Administration et ergonomie](#6-administration-et-ergonomie)
7. [Ce qu'omega-serv apporte de plus](#7-ce-quomega-serv-apporte-de-plus)
8. [Ce que les autres font mieux](#8-ce-que-les-autres-font-mieux)
9. [Quel serveur pour quel usage](#9-quel-serveur-pour-quel-usage)
10. [Reproduire les mesures](#10-reproduire-les-mesures)
11. [Sources](#11-sources)

---

## 1. En bref

- **Débit brut sur petits fichiers** : nginx et lighttpd, écrits en C, servent **10 à 20 fois plus** de requêtes par seconde qu'omega-serv, écrit en Python. Caddy, écrit en Go, se situe entre les deux. C'est un écart de nature, pas de réglage : omega-serv ne vise pas ce terrain.
- **Gros fichiers** : depuis la 2.0, omega-serv confie l'envoi au noyau (`sendfile`). Il atteint alors **le même ordre de débit** que nginx, lighttpd et Caddy sur cette machine : 2,1 Go/s contre 2,0 à 2,4 Go/s.
- **Mémoire** : lighttpd (1 Mo) et nginx (4 à 5 Mo) restent hors de portée. omega-serv tient sous 30 Mo en charge avec 1 processus, Caddy environ 55 Mo.
- **De la 1.0 à la 2.0** : débit des gros fichiers multiplié par 2,8 ; mémoire pendant de gros téléchargements divisée par 45 ; jusqu'à +50 % sur les petits fichiers avec 2 processus (mode boost) ; coût d'Active Defense divisé par 12.
- **Ce qu'omega-serv a en plus** : une administration complète en interface terminal (TUI), en 17 langues ; un WAF et une défense active intégrés ; des limites de sécurité qui restent exactes avec plusieurs processus ; l'import de scripts lighttpd mod_magnet ; la gestion de plusieurs instances.
- **Ce qu'il n'a pas** : HTTP/2 et HTTP/3, la découverte de services Docker/Kubernetes, un client ACME intégré (il passe par Certbot), le débit d'un serveur écrit en C.

---

## 2. Méthode de mesure

### Machine et logiciels

| Élément | Valeur |
|---|---|
| Processeur | Intel Core i5 M480 à 2,67 GHz (2010) : 2 cœurs physiques, 4 threads |
| Mémoire | 8 Go |
| Système | Manjaro Linux, noyau 6.18 |
| Réseau | boucle locale (127.0.0.1) |
| Client de charge | [oha](https://github.com/hatoo/oha) 1.16.0 (écrit en Rust) |
| nginx | 1.30.4 (paquet Manjaro) |
| lighttpd | 1.4.85 (paquet Manjaro) |
| Caddy | 2.11.4 (paquet Manjaro) |
| omega-serv | 1.0.0 (archive publiée) et 2.0.0, sous Python 3.14.7 |

Apache et Traefik n'ont pas été mesurés, faute d'installation sur cette machine. Traefik n'est d'ailleurs pas un serveur de fichiers (voir §5). Ces deux serveurs figurent donc seulement au comparatif des fonctions.

### Protocole

- **Isolation du processeur** : chaque serveur est épinglé sur le cœur physique 0 (threads 0 et 2), et le client sur le cœur physique 1 (threads 1 et 3). Ainsi le client ne vole pas de temps au serveur, et tous les serveurs disposent exactement des mêmes ressources.
- **Mêmes fichiers pour tous** : `small.html` (1 Ko), `medium.png` (100 Ko) et `large.bin` (5 Mo), servis depuis le même dossier.
- **Journal d'accès actif partout**, car un serveur en production journalise.
- **HTTP/1.1 en clair, connexions persistantes (keep-alive)**. La concurrence est de 32 connexions pour les fichiers de 1 Ko et 100 Ko, et de 8 pour le fichier de 5 Mo.
- **Durée** : 10 secondes par fichier et par configuration.
- **Répétitions** : 3 tours complets, entrelacés (tous les serveurs au tour 1, puis tous au tour 2, etc.). Les tableaux donnent la **médiane** des trois tours.
- **Mémoire** : PSS (*Proportional Set Size*) cumulée de tous les processus du serveur. Contrairement au RSS, une page partagée entre processus n'y est comptée qu'une fois. Elle est relevée au repos, puis après la charge.
- **Configurations** : nginx, lighttpd et Caddy dans leur configuration de base (fichiers statiques, journal d'accès). omega-serv utilise le profil `standard`, avec le WAF désactivé puis activé avec toutes ses règles livrées.
- **Nombre de processus** : chaque serveur est mesuré avec 1 puis 2 processus (nginx `worker_processes`, lighttpd `server.max-worker`, Caddy `GOMAXPROCS`, omega-serv `server.workers`).

### Limites à connaître

- **Machine modeste et ancienne.** Les valeurs absolues seraient bien plus élevées sur un serveur récent. Ce qui a du sens, ce sont les **rapports** entre serveurs mesurés dans la même session.
- **Variabilité d'une session à l'autre** : environ 10 à 30 % selon la charge de fond de la machine. Les tours d'une même session restent, eux, cohérents : moins de 5 % d'écart pour omega-serv et Caddy, davantage pour nginx et lighttpd, dont le débit très élevé est plus sensible au reste de la machine.
- **Boucle locale** : la mesure ne passe pas par un vrai réseau. Sur un vrai réseau, le débit des gros fichiers est presque toujours limité par la bande passante, pas par le serveur.
- **Pas de TLS** dans ces mesures. Avec HTTPS, omega-serv ne peut pas utiliser `sendfile` et envoie les fichiers par blocs.
- **Chiffres bruts** : ils sont publiés avec ce document dans [`docs/benchmarks/2026-10-26-campagne-brute.txt`](benchmarks/2026-10-26-campagne-brute.txt).

---

## 3. Performances : omega-serv face à nginx, lighttpd et Caddy

### Petits fichiers (1 Ko) : requêtes par seconde

| Serveur | 1 processus | 2 processus | Latence p99 (1 proc.) |
|---|---:|---:|---:|
| lighttpd 1.4.85 | 25 521 | 29 700 | 4,5 ms |
| nginx 1.30.4 | 14 054 | 18 315 | 4,7 ms |
| Caddy 2.11.4 | 3 697 | 5 345 | 25,3 ms |
| **omega-serv 2.0** | **1 358** | **1 953** | **37,5 ms** |
| omega-serv 2.0 + WAF | 1 130 | 1 617 | 48,5 ms |
| omega-serv 1.0 | 1 304 | — | 41,2 ms |

### Fichiers moyens (100 Ko) : requêtes par seconde

| Serveur | 1 processus | 2 processus |
|---|---:|---:|
| lighttpd | 11 635 | 13 037 |
| nginx | 8 024 | 9 555 |
| Caddy | 3 280 | 4 344 |
| **omega-serv 2.0** | **1 247** | **1 629** |
| omega-serv 2.0 + WAF | 1 012 | 1 347 |
| omega-serv 1.0 | 1 064 | — |

### Gros fichier (5 Mo) : débit

| Serveur | 1 processus | 2 processus |
|---|---:|---:|
| lighttpd | 2 379 Mo/s | 2 407 Mo/s |
| nginx | 2 242 Mo/s | 1 981 Mo/s |
| Caddy | 2 165 Mo/s | 2 229 Mo/s |
| **omega-serv 2.0** | **1 658 Mo/s** | **2 115 Mo/s** |
| omega-serv 1.0 | 584 Mo/s | — |

### Mémoire (PSS, tous processus du serveur)

| Serveur | Au repos | Après la charge |
|---|---:|---:|
| lighttpd (1 ou 2 proc.) | 1 Mo | 1 Mo |
| nginx (1 ou 2 proc.) | 4 à 5 Mo | 4 à 5 Mo |
| **omega-serv 2.0 (1 proc.)** | **26 Mo** | **30 Mo** |
| omega-serv 2.0 (2 proc.) | 39 Mo | 48 Mo |
| Caddy | 50 Mo | 56 Mo |
| omega-serv 1.0 | 22 Mo | 100 Mo |

### Lecture

- **Sur les petits et moyens fichiers**, l'écart avec nginx et lighttpd est d'un ordre de grandeur (×10 à ×20). C'est le coût d'un serveur écrit en Python : chaque requête traverse l'interpréteur, alors que nginx et lighttpd la traitent en C compilé. Le mode boost réduit l'écart, sans le combler.
- **Sur les gros fichiers**, les serveurs se rejoignent, car c'est le noyau qui copie les données (`sendfile`). Avec 2 processus, omega-serv 2.0 arrive à 2,1 Go/s, dans la même zone que les autres (2,0 à 2,4 Go/s).
- **Le WAF d'omega-serv coûte environ 17 %** sur les petits fichiers : il inspecte chaque requête. nginx, lighttpd et Caddy ont été mesurés sans WAF ; un WAF ajouté à ces serveurs (ModSecurity, Coraza) a lui aussi un coût, non mesuré ici.
- **Pour situer ces chiffres** : 1 300 requêtes par seconde, c'est plus de 110 millions de requêtes par jour sur cette machine de 2010. C'est très au-delà des besoins d'un site personnel, d'un service interne ou d'un laboratoire, qui sont les usages visés par omega-serv.

---

## 4. omega-serv 1.0 → 2.0 : ce qui a changé, mesuré

### Performances

Les deux versions ont été mesurées dans la même session, sur la même machine et avec le même protocole.

| Mesure | 1.0.0 | 2.0.0 | Évolution |
|---|---:|---:|---:|
| Petits fichiers (1 Ko), 1 processus | 1 304 req/s | 1 358 req/s | +4 % |
| Petits fichiers (1 Ko), mode boost 2 processus | — | 1 953 req/s | **+50 %** vs 1.0 |
| Petits fichiers avec WAF, 1 processus | 1 097 req/s | 1 130 req/s | +3 % |
| Petits fichiers avec WAF, 2 processus | — | 1 617 req/s | **+47 %** vs 1.0 |
| Fichiers de 100 Ko, 1 processus | 1 064 req/s | 1 247 req/s | +17 % |
| Gros fichier (5 Mo), 1 processus | 584 Mo/s | 1 658 Mo/s | **×2,8** |
| Gros fichier (5 Mo), 2 processus | — | 2 115 Mo/s | **×3,6** vs 1.0 |
| Mémoire après la charge, 1 processus | 100 Mo | 30 Mo | **÷3** |

### Gros téléchargements simultanés

Test : 3 téléchargements simultanés d'un fichier de 300 Mo, pendant qu'une petite page est demandée en continu. Deux passages donnent des résultats identiques.

| Mesure | 1.0.0 | 2.0.0 |
|---|---:|---:|
| Mémoire du serveur au plus haut | 1 835 Mo | 40 Mo |
| Petite page pendant les téléchargements : médiane | 3 à 4 ms | 2 ms |
| Petite page pendant les téléchargements : pire cas | 1,7 à 1,8 s | 5 ms |

La 1.0 chargeait chaque fichier entièrement en mémoire avant de l'envoyer. La 2.0 l'envoie par blocs, ou le confie au noyau : la mémoire ne dépend plus de la taille des fichiers, et le serveur reste réactif pendant les téléchargements.

### Coût de la défense active

Coût d'une observation de menace par Active Defense, pour chaque requête suspecte, mesuré sur disque (ext4) sur 2 000 observations :

| Mesure | 1.0.0 | 2.0.0 |
|---|---:|---:|
| Médiane | 2,84 ms | 0,23 ms |
| p99 | 11,6 ms | 2,3 ms |
| Maximum | 18 à 20 ms | 37 à 46 ms |

La médiane est divisée par 12. Le maximum est en revanche plus élevé en 2.0 : quelques pics isolés, liés à l'écriture périodique du journal SQLite sur disque.

### Fonctions arrivées avec la 2.0

**Mise à niveau des standards du marché** : nginx, lighttpd, Caddy et Apache font déjà tout cela. omega-serv les rattrape.

- Requêtes conditionnelles (ETag, Last-Modified, réponses 304) : un rechargement de page ne retélécharge que ce qui a changé.
- Requêtes partielles (Range, 206/416) : reprise de téléchargement, avance dans une vidéo.
- Envoi des fichiers par `sendfile` ou par blocs, avec une mémoire stable.
- Fichiers pré-compressés (`.gz`, `.br`) déposés à côté de l'original.
- Cache-Control par défaut selon le type de fichier (images, polices, CSS/JS), réglable.
- Plusieurs processus serveur (mode boost, `server.workers`).

**Fonctions plus étendues :**

- **Reverse proxy complet.** La 1.0 n'avait qu'un relais simple (tour de rôle, TLS vers l'amont, WebSocket). La 2.0 ajoute :
  - 6 stratégies de répartition, soit 7 au total ;
  - l'affinité de session et le routage sur en-tête ;
  - une santé passive et active des serveurs amont ;
  - un cache des réponses ;
  - une protection contre la surcharge et contre les boucles ;
  - le pilotage à chaud.
- **Limite de débit par dossier et par adresse ou réseau**, en plus de la limite globale.
- **Compteurs de sécurité partagés entre processus** (voir §7).
- **Listes de chemins sensibles** prêtes à l'emploi, avec un mode observation et un éditeur intégré.
- **Import de scripts lighttpd mod_magnet** (voir §7).
- **Interface en 17 langues**, avec une langue séparée pour les pages vues par les visiteurs et pour les exports.
- **Journaux entièrement revus** :
  - une bibliothèque de journaux ;
  - trois visionneuses, dont lnav ;
  - la récupération de journaux distants par SSH.

---

## 5. Comparatif des fonctions

Légende :
- ✅ intégré ;
- 🧩 module officiel du projet, à activer ou à installer ;
- 🔌 module ou plugin tiers ;
- ⚙️ via un outil externe ;
- ❌ absent.

« Commercial » désigne une fonction réservée à l'édition payante.

### Service HTTP

| Fonction | nginx | lighttpd | Caddy | Apache | Traefik | omega-serv 2.0 |
|---|---|---|---|---|---|---|
| Servir des fichiers statiques | ✅ | ✅ | ✅ | ✅ | ❌ (proxy uniquement) | ✅ |
| ETag / 304 / Range | ✅ | ✅ | ✅ | ✅ | — | ✅ |
| Fichiers pré-compressés `.gz` / `.br` | ✅ `gzip_static` (`.br` : 🔌) | 🔌 script Lua (mod_magnet) | ✅ `precompressed` | 🧩 recette mod_rewrite | — | ✅ |
| Compression à la volée | ✅ | ✅ mod_deflate | ✅ | 🧩 mod_deflate | ✅ middleware | ❌ |
| HTTP/2 | ✅ | ✅ | ✅ | 🧩 mod_http2 | ✅ | ❌ |
| HTTP/3 (QUIC) | ✅ | ❌ | ✅ | ❌ | ✅ | ❌ |
| PHP via FastCGI | ✅ | ✅ | ✅ | ✅ | ❌ | ✅ |
| Plusieurs processus ou cœurs | ✅ workers | ⚠️ `max-worker`, déconseillé par la documentation | ✅ (Go, tous les cœurs) | ✅ MPM | ✅ (Go) | ✅ `server.workers` |

### Reverse proxy

| Fonction | nginx | lighttpd | Caddy | Apache | Traefik | omega-serv 2.0 |
|---|---|---|---|---|---|---|
| Répartition de charge | ✅ tour de rôle, moins de connexions, hash | ✅ fair, round-robin, hash, sticky | ✅ une douzaine de stratégies | 🧩 mod_proxy_balancer | ✅ wrr, p2c, hrw, least-time | ✅ 7 stratégies, dont la charge réelle |
| Santé passive (écarter un serveur en panne) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Santé active (sonde périodique) | Commercial (NGINX Plus) | ❌ | ✅ | 🧩 mod_proxy_hcheck | ✅ | ✅ |
| Cache des réponses | ✅ `proxy_cache` | ❌ | 🔌 | 🧩 mod_cache | Commercial | ✅ |
| WebSocket | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Découverte de services (Docker, Kubernetes) | 🔌 | ❌ | 🔌 | ❌ | ✅ (cœur du projet) | ❌ |

### TLS

| Fonction | nginx | lighttpd | Caddy | Apache | Traefik | omega-serv 2.0 |
|---|---|---|---|---|---|---|
| Certificats automatiques (ACME, Let's Encrypt) | 🧩 `ngx_http_acme_module` | ⚙️ Certbot | ✅ par défaut | 🧩 mod_md | ✅ | ⚙️ Certbot, avec assistant intégré et renouvellement programmé |
| CA locale | ❌ | ❌ | ✅ CA interne (émission automatique) | ❌ | ❌ | ✅ génération, signature de CSR, révocation |

### Sécurité

| Fonction | nginx | lighttpd | Caddy | Apache | Traefik | omega-serv 2.0 |
|---|---|---|---|---|---|---|
| Limite de débit par client | ✅ `limit_req` | ⚠️ mod_evasive (connexions simultanées seulement) | 🔌 caddy-ratelimit | 🔌 mod_evasive, mod_qos | ✅ middleware | ✅ |
| Limite partagée entre processus | ✅ zone mémoire partagée | ❌ comptée par processus | — (1 seul processus) | selon le module | 1 instance ; plusieurs avec Redis | ✅ mémoire partagée |
| WAF (signatures SQLi/XSS, scanners…) | 🔌 ModSecurity, Commercial (App Protect) | ❌ (scripts Lua à écrire) | 🔌 Coraza | 🔌 ModSecurity | 🔌 plugins | ✅ intégré |
| Liste de blocage avec expiration, récidive | ⚙️ fail2ban | ⚙️ fail2ban | ⚙️ fail2ban | ⚙️ fail2ban | ⚙️ | ✅ intégré |
| Leurres, mode guerre, incidents, export IoC | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ Active Defense |
| Audit de sécurité de la configuration | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ `audit security` |
| Mode observation (journaliser sans bloquer) | selon module | — | selon plugin | ✅ ModSecurity `DetectionOnly` | selon plugin | ✅ |

### Extensibilité

| Fonction | nginx | lighttpd | Caddy | Apache | Traefik | omega-serv 2.0 |
|---|---|---|---|---|---|---|
| Langage de script | 🧩 njs (JavaScript) ; 🔌 Lua (OpenResty) | ✅ Lua (mod_magnet) | modules Go (recompilation) | 🧩 mod_lua | plugins Go ou WebAssembly | 🔌 import de scripts mod_magnet (option `magnet`) |
| Écosystème de modules | très large | ciblé | large | très large | large | aucun : tout est intégré |

---

## 6. Administration et ergonomie

| Serveur | Mode d'administration principal | Interface | Rechargement sans coupure |
|---|---|---|---|
| nginx | fichiers de configuration | aucune (tableau de bord : NGINX Plus, commercial) | ✅ `nginx -s reload` |
| lighttpd | fichier de configuration | aucune (mod_status en lecture seule) | ✅ redémarrage gracieux |
| Caddy | Caddyfile ou JSON | API REST d'administration | ✅ via l'API |
| Apache | fichiers de configuration et `.htaccess` | aucune (mod_status en lecture seule) | ✅ `graceful` |
| Traefik | étiquettes de conteneurs, fichiers ou Kubernetes | tableau de bord web (lecture seule) | ✅ configuration dynamique |
| omega-serv | interface terminal (TUI) et ligne de commande (CLI) ; le fichier JSON n'a pas à être édité | **TUI complète au clavier et à la souris, 17 langues, aide intégrée** | ✅ pour la plupart des réglages ; redémarrage annoncé pour le port, TLS et le nombre de processus |

Concrètement, avec omega-serv, la configuration, la sécurité, les journaux, les services système, les sauvegardes et les instances se gèrent depuis une seule interface. Chaque réglage est expliqué et vérifié avant d'être écrit. Avec les autres serveurs, on édite des fichiers texte, puis on fait appel à des outils séparés (Certbot, fail2ban, logrotate, ModSecurity, un outil de supervision…).

En contrepartie, l'approche « fichier de configuration » de nginx, Apache et Caddy s'automatise très bien (Ansible, conteneurs, gestion de version). omega-serv a une CLI scriptable, mais son écosystème d'automatisation reste limité.

---

## 7. Ce qu'omega-serv apporte de plus

Cette section ne retient que ce qu'aucun des serveurs comparés ne fournit tel quel, sans module tiers ni outil externe.

1. **Une administration complète en interface terminal.**
   - L'interface couvre tout le serveur : le site, la sécurité, les journaux, les services, les sauvegardes et les instances.
   - Elle s'utilise au clavier et à la souris, sur un serveur sans affichage graphique, même à travers SSH.
   - Elle est disponible en 17 langues et explique chaque réglage.
   - Les autres serveurs n'ont pas d'interface d'administration (nginx, lighttpd, Apache), ou seulement une API (Caddy) ou un tableau de bord en lecture seule (Traefik).
2. **Une sécurité active intégrée, sans module à assembler.**
   - Le WAF comprend des signatures, des listes de chemins éditables, la récidive, une liste de blocage avec expiration, la réputation et un mode observation.
   - Active Defense ajoute des leurres, un mode guerre, le suivi d'incidents, l'export d'indicateurs de compromission et une simulation à blanc.
   - Ailleurs, ces fonctions demandent d'assembler ModSecurity ou Coraza, des jeux de règles et fail2ban.
3. **Des limites de sécurité exactes avec plusieurs processus.**
   - En mode boost, la limite de débit et la récidive du WAF sont partagées en mémoire entre les processus. Un attaquant ne peut donc pas multiplier sa limite par le nombre de processus.
   - lighttpd documente le cas inverse : avec `server.max-worker`, `mod_evasive` et `mod_status` comptent séparément dans chaque processus.
   - nginx partage aussi ses compteurs (zones `limit_req`), mais il n'a pas de WAF intégré.
4. **L'import de scripts lighttpd mod_magnet.**
   - Un script de protection Lua déjà écrit pour lighttpd s'importe sans être réécrit.
   - Il s'ajoute à la protection intégrée sans jamais pouvoir l'affaiblir, et sa compatibilité est vérifiée avant activation.
5. **La gestion de plusieurs instances.**
   - Un registre recense toutes les instances, et l'interface passe de l'une à l'autre.
   - Elle sait aussi désinstaller complètement une instance.
6. **Un audit de sécurité de la configuration** : la commande `audit security` est informative, ne bloque jamais et renvoie des codes de sortie exploitables dans un script.
7. **Des sources de journaux distantes.**
   - L'interface récupère par SSH le journal d'un autre serveur, à la demande, sans mot de passe enregistré.
   - Elle peut le lire avec lnav, en le fusionnant avec les journaux locaux.
8. **Un durcissement HTTP non désactivable**, actif dès l'installation, quel que soit le profil :
   - validation stricte de l'en-tête Host ;
   - rejet des ambiguïtés Content-Length / Transfer-Encoding ;
   - en-têtes de sécurité et CSP, même sur les pages d'erreur ;
   - lecture sûre de X-Forwarded-For ;
   - refus de démarrer en root.

---

## 8. Ce que les autres font mieux

- **Débit et latence** : nginx et lighttpd servent 10 à 20 fois plus de petites requêtes, avec une latence 8 à 10 fois plus basse. Pour un site à fort trafic, une API publique ou un CDN, ce sont eux qu'il faut choisir.
- **Mémoire** : lighttpd (1 Mo) et nginx (4 à 5 Mo) conviennent aux machines très contraintes (embarqué, Raspberry Pi d'entrée de gamme, petits conteneurs).
- **Protocoles** : HTTP/2 chez tous les autres, HTTP/3 chez nginx, Caddy et Traefik. omega-serv ne parle que HTTP/1.1.
- **HTTPS automatique** : Caddy et Traefik l'intègrent par défaut, et nginx (`ngx_http_acme_module`) et Apache (`mod_md`) avec un module officiel. omega-serv délègue à Certbot, avec un assistant et un renouvellement programmé.
- **Environnements conteneurisés** : la découverte automatique de services de Traefik (Docker, Kubernetes) n'a pas d'équivalent dans omega-serv.
- **Écosystème** : nginx et Apache offrent des milliers de modules, de guides et d'intégrations. Caddy offre un système de modules en Go. omega-serv est un projet jeune, maintenu par une seule personne.
- **Compression à la volée** : omega-serv ne sert que des fichiers déjà compressés.

---

## 9. Quel serveur pour quel usage

| Besoin | Choix conseillé |
|---|---|
| Site à fort trafic, API publique, CDN, débit maximal | **nginx** |
| Machine très contrainte, embarqué, fichiers statiques | **lighttpd** |
| Démarrage rapide avec HTTPS automatique, configuration courte | **Caddy** |
| Application PHP historique, `.htaccess`, hébergement mutualisé | **Apache** |
| Docker, Kubernetes, microservices | **Traefik** |
| Petit site, service interne, laboratoire, VPN, administration sans éditer de fichiers | **omega-serv** |
| Serveur exposé où l'on veut voir et contrôler la sécurité (WAF, bannissements, leurres) depuis une seule interface | **omega-serv** |
| Reverse proxy interne avec répartition, santé et cache, piloté depuis une interface | **omega-serv** |
| Apprendre le durcissement HTTP et la défense active | **omega-serv** |

Ces outils se combinent aussi. Par exemple :
- nginx ou Traefik en frontal sur Internet, avec omega-serv derrière pour un service interne, sa sécurité et son administration ;
- omega-serv en reverse proxy interne devant plusieurs serveurs d'application.

---

## 10. Reproduire les mesures

Les outils sont livrés dans le dépôt, sous `tools/bench/`. Il faut nginx, lighttpd, Caddy et oha installés, ainsi que l'environnement de développement d'omega-serv (`.venv`).

```sh
# 1. préparer un dossier de mesure (fichiers de test, configurations, omega-serv 1.0 et 2.0)
tools/bench/compare/setup.sh /chemin/mesure omega-serv-1.0.0.tar.gz

# 2. les 12 configurations, 3 répétitions entrelacées (environ 22 minutes)
tools/bench/compare/campaign.sh /chemin/mesure > resultats.txt

# 3. médianes
python3 tools/bench/compare/summarize.py resultats.txt

# gros téléchargements (mémoire et réactivité), 2.0 puis 1.0
.venv/bin/python tools/bench/bigfile.py
BENCH_SRC=/chemin/mesure/v1-archive/omega-serv/src \
BENCH_EXTRA_PATH=/chemin/mesure/v1-archive/omega-serv/vendor/omega-lib/src \
  .venv/bin/python tools/bench/bigfile.py

# mesurer n'importe quel autre serveur déjà lancé, sans oha
python3 tools/bench/bench_any.py --make-files /srv/webroot-de-test
python3 tools/bench/bench_any.py --port 8080
```

Par défaut, le serveur est épinglé sur les threads 0 et 2, et le client sur les threads 1 et 3, ce qui correspond à la machine de mesure. Adaptez cette répartition à votre processeur (`lscpu -e` donne la topologie) avec les variables `SRV_CPUS` et `CLI_CPUS`.

Pour publier vos propres résultats, donnez la machine, les versions, la répartition des processeurs et les trois répétitions.

---

## 11. Sources

Fonctions des autres serveurs, d'après leur documentation officielle (consultée le 26 octobre 2026).

**nginx**
- [Limite de débit `limit_req` (zone mémoire partagée)](https://nginx.org/en/docs/http/ngx_http_limit_req_module.html)
- [Fichiers pré-compressés `gzip_static`](https://nginx.org/en/docs/http/ngx_http_gzip_static_module.html)
- [Module ACME officiel `ngx_http_acme_module`](https://nginx.org/en/docs/http/ngx_http_acme_module.html)
- [Répartition de charge (`upstream`)](https://nginx.org/en/docs/http/ngx_http_upstream_module.html)
- [HTTP/3](https://nginx.org/en/docs/http/ngx_http_v3_module.html)
- [Connecteur ModSecurity pour nginx](https://github.com/owasp-modsecurity/ModSecurity-nginx)

**lighttpd**
- [`server.max-worker` : déconseillé, compteurs par processus pour mod_status et mod_evasive](https://redmine.lighttpd.net/projects/lighttpd/wiki/Server_max-workerDetails)
- [mod_magnet (scripts Lua)](https://redmine.lighttpd.net/projects/lighttpd/wiki/Docs_ModMagnet)
- [mod_deflate (compression, cache)](https://redmine.lighttpd.net/projects/lighttpd/wiki/Mod_deflate)
- [mod_proxy (répartition, santé passive, WebSocket)](https://redmine.lighttpd.net/projects/lighttpd/wiki/Docs_ModProxy)
- [mod_evasive (connexions simultanées par adresse)](https://redmine.lighttpd.net/projects/lighttpd/wiki/Docs_ModEvasive)

**Caddy**
- [HTTPS automatique](https://caddyserver.com/docs/automatic-https)
- [`file_server` et `precompressed`](https://caddyserver.com/docs/caddyfile/directives/file_server)
- [`reverse_proxy` (stratégies, santé active et passive)](https://caddyserver.com/docs/caddyfile/directives/reverse_proxy)
- [API d'administration](https://caddyserver.com/docs/api)
- [Plugin de limite de débit caddy-ratelimit](https://github.com/mholt/caddy-ratelimit)
- [WAF Coraza pour Caddy](https://github.com/corazawaf/coraza-caddy)
- [caddy-docker-proxy](https://github.com/lucaslorentz/caddy-docker-proxy)

**Apache HTTP Server**
- [mod_md (ACME)](https://httpd.apache.org/docs/2.4/mod/mod_md.html)
- [mod_proxy_balancer](https://httpd.apache.org/docs/2.4/mod/mod_proxy_balancer.html)
- [mod_proxy_hcheck](https://httpd.apache.org/docs/2.4/mod/mod_proxy_hcheck.html)
- [mod_http2](https://httpd.apache.org/docs/2.4/mod/mod_http2.html)
- [mod_deflate, contenu pré-compressé](https://httpd.apache.org/docs/2.4/mod/mod_deflate.html)
- [ModSecurity](https://github.com/owasp-modsecurity/ModSecurity)

**Traefik**
- [Middleware `ratelimit` (en mémoire par instance, Redis en option)](https://doc.traefik.io/traefik/reference/routing-configuration/http/middlewares/ratelimit/)
- [ACME](https://doc.traefik.io/traefik/https/acme/)
- [Providers (Docker, Kubernetes…)](https://doc.traefik.io/traefik/providers/overview/)

**Outil de mesure**
- [oha](https://github.com/hatoo/oha)

---

*Comparatif réalisé par kraynux pour omega-serv 2.0.0 : mesures du 26 octobre 2026. Les mesures portent sur une seule machine. Pour toute décision de capacité, mesurez sur votre propre matériel avec les outils fournis.*
