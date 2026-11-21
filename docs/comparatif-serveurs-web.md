<!-- Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE) -->

# omega-serv face aux serveurs web du marché

**Comparatif mesuré : nginx · lighttpd · Apache · Caddy · Traefik · omega-serv 2.5 et 3.0.0**

🌐 **Français** · [English](translation/en/comparatif-serveurs-web.md) · [Español](translation/es/comparatif-serveurs-web.md) · [Português (Brasil)](translation/pt-BR/comparatif-serveurs-web.md) · [Italiano](translation/it/comparatif-serveurs-web.md) · [Deutsch](translation/de/comparatif-serveurs-web.md) · [Nederlands](translation/nl/comparatif-serveurs-web.md) · [Polski](translation/pl/comparatif-serveurs-web.md) · [Русский](translation/ru/comparatif-serveurs-web.md) · [中文](translation/zh-CN/comparatif-serveurs-web.md) · [Tiếng Việt](translation/vi/comparatif-serveurs-web.md) · [ไทย](translation/th/comparatif-serveurs-web.md) · [Bahasa Indonesia](translation/id/comparatif-serveurs-web.md) · [日本語](translation/ja/comparatif-serveurs-web.md) · [한국어](translation/ko/comparatif-serveurs-web.md) · [हिन्दी](translation/hi/comparatif-serveurs-web.md) · [العربية](translation/ar/comparatif-serveurs-web.md)

Ce document situe omega-serv parmi les serveurs web les plus répandus. Il ne cherche pas à désigner un « meilleur serveur » : chaque outil répond à des besoins différents, et chacun a ses points forts. Il donne trois choses :

1. des **mesures réelles**, faites sur **trois machines** très différentes, avec le même client, les mêmes fichiers et le même protocole, et reproductibles ;
2. un **comparatif des fonctions**, chacune vérifiée dans la documentation officielle de chaque serveur (liens en fin de document), en distinguant ce qui est intégré de ce qui demande un module ou un plugin ;
3. ce qu'omega-serv **apporte réellement de plus**, et ce que les autres font **mieux que lui**.

Les mesures de serveur de fichiers ont été faites les 3 et 4 novembre 2026 (omega-serv 2.5), celles du reverse proxy le 14 novembre 2026 (omega-serv 3.0.0, en préparation). La mémoire d'omega-serv 3.0.0, nettement réduite depuis, a été remesurée le 19 novembre 2026 sur les trois machines, au même protocole (§4, §5 et §6). Aucun chiffre n'est repris d'un autre site ou estimé. Les chiffres bruts sont publiés avec ce document.

---

## Sommaire

1. [En bref](#1-en-bref)
2. [Comment lire ce comparatif](#2-comment-lire-ce-comparatif)
3. [Méthode de mesure](#3-méthode-de-mesure)
4. [Performances : omega-serv face à nginx, lighttpd, Apache et Caddy](#4-performances--omega-serv-face-à-nginx-lighttpd-apache-et-caddy)
5. [Performances en reverse proxy : omega-serv face à nginx, lighttpd, Apache, Caddy et Traefik](#5-performances-en-reverse-proxy--omega-serv-face-à-nginx-lighttpd-apache-caddy-et-traefik)
6. [Les versions d'omega-serv : 1.0 → 2.0 → 2.5 → 3.0.0](#6-les-versions-domega-serv--10--20--25--300)
7. [Comparatif des fonctions](#7-comparatif-des-fonctions)
8. [Administration et ergonomie](#8-administration-et-ergonomie)
9. [Ce qu'omega-serv apporte de plus](#9-ce-quomega-serv-apporte-de-plus)
10. [Ce que les autres font mieux](#10-ce-que-les-autres-font-mieux)
11. [Quel serveur pour quel usage](#11-quel-serveur-pour-quel-usage)
12. [Reproduire les mesures](#12-reproduire-les-mesures)
13. [Sources](#13-sources)

---

## 1. En bref

- **omega-serv a deux moteurs.** Le **moteur Python** traite tout lui-même. Le **moteur natif**, écrit en C++ et apparu avec la 2.5, sert les requêtes lui-même ; Python garde la configuration et les décisions de sécurité, le natif reconnaissant seul les requêtes sur lesquelles aucune règle du WAF ne correspond.
- **Avec le moteur natif, sans WAF**, omega-serv sert les petits fichiers à **environ 0,7 fois la vitesse de nginx**, sur les trois machines. Il se place ainsi **devant Apache et Caddy, derrière nginx et lighttpd**.
- **Avec le moteur Python**, omega-serv reste loin derrière tous les autres : **3 à 11 % de la vitesse de nginx**.
- **Avec le WAF actif**, omega-serv inspecte chaque requête, ce que les autres serveurs mesurés ne font pas. Avec le moteur natif, il sert alors **0,53 à 0,56 fois** la vitesse de nginx (sans WAF) sur les machines A et B, et 1,07 fois sur la machine C (4 cœurs contre 2) : le WAF ne lui retire que 5 à 22 % de son débit. Il reste devant Apache et Caddy mesurés sans WAF.
- **Fichiers moyens (100 Ko)** : c'est le point faible actuel du moteur natif, à **0,3 à 0,6 fois** nginx, derrière Apache.
- **Gros fichiers (5 Mo)** : nginx, lighttpd, Apache et omega-serv natif atteignent le même ordre de débit. Caddy est nettement plus lent sur la machine la plus rapide.
- **En reverse proxy (3.0.0)**, le moteur natif relaie les petites réponses à **0,82 à 0,91 fois nginx**, et les réponses de 100 Ko **aussi vite ou plus vite que lui** (0,97 à 1,43). Il est **deuxième derrière nginx**, devant lighttpd, Apache, Traefik et Caddy. En HTTPS, il reste deuxième sur les petites réponses des machines A et B ; lighttpd l'égale sur la machine C.
- **Mémoire** : lighttpd (1 Mo), nginx (4 à 5 Mo) et Apache (4 à 9 Mo) sont très économes. omega-serv 3.0.0 occupe **10 à 16 Mo** avec le moteur natif, **20 à 33 Mo** avec le moteur Python ou le WAF, et 35 à 55 Mo avec 2 processus ; Caddy **50 à 67 Mo**. La 2.5 occupait 28 à 57 Mo.
- **Ce qu'omega-serv a en plus** : une administration complète en interface terminal, en 17 langues ; un WAF et une défense active intégrés ; des limites de sécurité exactes avec plusieurs processus ; l'import de scripts lighttpd mod_magnet ; la gestion de plusieurs instances.
- **Ce qu'il n'a pas** : HTTP/2 et HTTP/3, la compression à la volée, la découverte de services Docker/Kubernetes, un client ACME intégré (il passe par Certbot), un écosystème de modules.

---

## 2. Comment lire ce comparatif

Quelques notions reviennent dans tout le document.

- **Requêtes par seconde (req/s)** : le nombre de fichiers qu'un serveur envoie en une seconde. Plus c'est haut, mieux c'est.
- **Écart avec nginx** : les valeurs absolues dépendent énormément de la machine. Sur nos trois machines, nginx va de 22 000 à 440 000 req/s. Ce qui reste stable, c'est **le rapport entre serveurs**. Les tableaux donnent donc, à côté de chaque valeur, son rapport avec nginx mesuré dans la même session : **1,00 = aussi rapide que nginx**, 0,50 = moitié moins, 1,50 = moitié plus.
- **Latence p99** : le temps de réponse que 99 % des requêtes ne dépassent pas. Elle montre les « mauvais moments » qu'une moyenne cache.
- **PSS (*Proportional Set Size*)** : la mémoire réellement occupée par tous les processus du serveur. Une page partagée entre plusieurs processus n'y est comptée qu'une fois.
- **Processus et cœurs** : un serveur peut utiliser plusieurs cœurs du processeur. Chacun le fait à sa façon. nginx, lighttpd, Apache et omega-serv en mode Python lancent plusieurs processus. Caddy, en Go, répartit son travail sur les cœurs. Le moteur natif d'omega-serv lance un fil par cœur disponible. Pour comparer à armes égales, nous donnons à chaque serveur **les mêmes cœurs**.
- **WAF (*Web Application Firewall*)** : un filtre qui inspecte chaque requête pour bloquer les attaques (injections, scanners…). omega-serv l'intègre. Les autres serveurs peuvent en recevoir un en module (ModSecurity, Coraza), mais **ils ont été mesurés sans**, dans leur configuration de base.

**Le bon réflexe** : comparer les rapports, pas les valeurs absolues, et toujours vérifier si le WAF est actif.

---

## 3. Méthode de mesure

### Les trois machines

| | Machine A | Machine B | Machine C |
|---|---|---|---|
| Processeur | Intel Core i5 M480, 2,67 GHz (2010) | Intel Celeron J3455, 1,5 GHz (2016) | AMD Ryzen AI 9 365 (2024) |
| Cœurs | 2 cœurs physiques, 4 threads | 4 cœurs, sans hyperthreading | 10 cœurs (4 Zen 5 + 6 Zen 5c), 20 threads |
| Mémoire | 8 Go | 8 Go | 32 Go |
| Système | Mabox Linux (base Manjaro), noyau 6.18 | EndeavourOS, noyau 7.2 | Arch Linux, noyau 7.2 (CachyOS) |
| Cœurs du serveur | 1 cœur physique (threads 0 et 2) | 2 cœurs (0 et 1) | 4 cœurs Zen 5, un thread chacun (0 à 3) |
| Cœurs du client | 1 cœur physique (threads 1 et 3) | 2 cœurs (2 et 3) | 6 cœurs Zen 5c (4 à 9) |

La machine A est un ancien portable, la machine B un mini-PC basse consommation, la machine C un portable récent, sur secteur, en profil d'énergie « équilibré ». Elles couvrent un éventail allant d'un petit serveur domestique à une machine actuelle.

### Logiciels

| Logiciel | Version |
|---|---|
| nginx | 1.30.4 (A), 1.30.5 (B, C) |
| lighttpd | 1.4.85 |
| Apache HTTP Server | 2.4.69, MPM `event` |
| Caddy | 2.11.4 (A, B), 2.11.7 (C) |
| omega-serv | 1.0.0 et 2.0.0 (archives publiées), 2.5 et 3.0.0, sous Python 3.14 |
| Client de charge | [oha](https://github.com/hatoo/oha) 1.16.0 (écrit en Rust) |

Traefik n'a pas été mesuré en serveur de fichiers : ce n'en est pas un (voir §7). Il est mesuré en reverse proxy, son rôle, au §5.

### Protocole

- **Isolation du processeur** : le serveur et le client sont épinglés sur des cœurs séparés (tableau ci-dessus). Le client ne vole donc pas de temps au serveur, et tous les serveurs disposent exactement des mêmes ressources.
- **Mêmes fichiers pour tous** : `small.html` (1 Ko), `medium.png` (100 Ko) et `large.bin` (5 Mo), servis depuis le même dossier.
- **Journal d'accès actif partout**, car un serveur en production journalise.
- **HTTP/1.1 en clair, connexions persistantes (keep-alive)**. La concurrence est de 32 connexions pour les fichiers de 1 Ko et 100 Ko, et de 8 pour le fichier de 5 Mo.
- **Durée** : 10 secondes par fichier et par configuration.
- **Répétitions** : 3 tours complets, entrelacés (toutes les configurations au tour 1, puis toutes au tour 2, etc.). Les tableaux donnent la **médiane** des trois tours. D'un tour à l'autre, l'écart reste le plus souvent sous 5 %.
- **Mémoire** : PSS de tous les processus du serveur, relevée au repos puis après la charge. Celle d'omega-serv 3.0.0 a été remesurée le 19 novembre 2026 avec, dans la même session, nginx comme référence : il reste à 3 % près de son débit du 4 novembre sur les petits fichiers, et sa mémoire à 1 Mo près.
- **Configurations** :
  - nginx, lighttpd, Apache et Caddy dans leur configuration de base : fichiers statiques et journal d'accès ;
  - omega-serv avec le profil `standard`, le WAF désactivé puis activé avec toutes ses règles livrées (sans limite de débit).
- **Nombre de processus** : chaque serveur est mesuré avec 1 puis 2 processus : nginx `worker_processes`, lighttpd `server.max-worker`, Apache `StartServers`/`ServerLimit`, Caddy `GOMAXPROCS`, omega-serv `server.workers`. Pour le moteur natif d'omega-serv, `server.workers` compte les processus Python de sécurité ; le moteur natif, lui, utilise toujours tous les cœurs qui lui sont donnés.
- **Aucune erreur** : toutes les réponses de toutes les mesures sont des 200.

### Limites à connaître

- **Ce que nous comparons, ce sont les rapports.** Les valeurs absolues seraient différentes sur votre matériel, ou sur un serveur dédié.
- **Boucle locale (127.0.0.1)** : la mesure ne passe pas par un vrai réseau. Sur un vrai réseau, le débit des gros fichiers est presque toujours limité par la bande passante, pas par le serveur. Les débits de plusieurs dizaines de Go/s de la machine C ne sont possibles qu'en boucle locale.
- **Pas de TLS** dans les mesures de serveur de fichiers (§4 et §6). Le reverse proxy (§5) est mesuré en HTTP et en HTTPS.
- **Machine A** : le service omega-serv de production de cette machine tournait en arrière-plan, sans recevoir de trafic.
- **Machine C** : processeur hybride (cœurs Zen 5 et Zen 5c). Le serveur a reçu les 4 cœurs rapides, le client les 6 autres.
- **Configurations de base** : aucun serveur n'a été optimisé. Un administrateur expérimenté tirerait sans doute davantage de chacun, omega-serv compris.
- **Chiffres bruts** : [`docs/benchmarks/`](benchmarks/) (un fichier par machine et par campagne ; remesure de la 3.0.0 : `2026-11-19-*-memoire-3.0.0-brut.txt`).

---

## 4. Performances : omega-serv face à nginx, lighttpd, Apache et Caddy

Dans tous les tableaux, la valeur de référence est **nginx avec 2 processus** (= 1,00), mesuré dans la même session sur la même machine. Sur les machines A et B, c'est la configuration qui occupe tous les cœurs donnés au serveur.

### Petits fichiers (1 Ko) : requêtes par seconde

| Serveur | Machine A | Machine B | Machine C |
|---|---:|---:|---:|
| lighttpd, 2 processus | 33 138 (**1,52**) | 31 125 (**1,26**) | 378 590 (**1,53**) |
| nginx, 2 processus | 21 801 (1,00) | 24 705 (1,00) | 248 184 (1,00) |
| **omega-serv, moteur natif** | **15 222 (0,70)** | **16 542 (0,67)** | **285 213 (1,15 \*)** |
| omega-serv, natif + WAF † | 11 990 (0,56) | 12 998 (0,53) | 264 484 (1,07 \*) |
| omega-serv, natif + WAF, 2 processus de sécurité † | 11 746 (0,55) | 12 718 (0,52) | 253 527 (1,02 \*) |
| Apache, 2 processus | 9 192 (0,42) | 8 634 (0,35) | 188 335 (0,76) |
| Caddy, 2 processus | 5 749 (0,26) | 4 116 (0,17) | 52 897 (0,21) |
| omega-serv, moteur Python, 2 processus | 2 354 (0,11) | 1 312 (0,05) | 19 911 (0,08) |
| omega-serv, Python + WAF, 2 processus | 1 901 (0,09) | 1 104 (0,04) | 15 783 (0,06) |
| omega-serv, moteur Python | 1 507 (0,07) | 663 (0,03) | 10 553 (0,04) |
| omega-serv, Python + WAF | 1 561 (0,07) | 564 (0,02) | 8 365 (0,03) |

\* Sur la machine C, le moteur natif utilise ses 4 cœurs, alors que nginx n'en utilise que 2 avec 2 processus. La comparaison à nombre de cœurs égal est donnée plus bas : le rapport y redevient **0,67 à 0,71**, comme sur les autres machines.

† Mesuré le 4 novembre, après l'optimisation du WAF, dans une campagne séparée au même protocole. Le rapport est calculé avec nginx (2 processus) de cette campagne : 21 439, 24 424 et 248 127 req/s sur les petits fichiers, 11 545, 11 004 et 157 491 sur les fichiers de 100 Ko. Avant cette optimisation, le moteur natif avec WAF servait 3 495, 2 622 et 39 000 req/s (0,11 à 0,16 fois nginx), car chaque requête passait par Python. Chiffres bruts : fichiers `*-waf-natif-brut.txt`.

Avec 1 seul processus, nginx fait 0,52 à 0,73, lighttpd 0,81 à 1,43, Apache 0,33 à 0,74 et Caddy 0,09 à 0,17 (chiffres bruts).

### Latence p99 sur les petits fichiers

| Serveur | Machine A | Machine B | Machine C |
|---|---:|---:|---:|
| lighttpd, 2 processus | 4,4 ms | 4,1 ms | 0,2 ms |
| nginx, 2 processus | 4,9 ms | 5,2 ms | 0,2 ms |
| **omega-serv, moteur natif** | **6,1 ms** | **6,2 ms** | **0,3 ms** |
| omega-serv, natif + WAF † | 7,2 ms | 6,7 ms | 0,3 ms |
| Apache, 2 processus | 18,8 ms | 20,6 ms | 0,8 ms |
| Caddy, 2 processus | 24,1 ms | 30,5 ms | 2,8 ms |
| omega-serv, moteur Python, 2 processus | 22,6 ms | 28,1 ms | 3,3 ms |
| omega-serv, moteur Python | 32,0 ms | 51,6 ms | 4,4 ms |

### Fichiers moyens (100 Ko) : requêtes par seconde

| Serveur | Machine A | Machine B | Machine C |
|---|---:|---:|---:|
| lighttpd, 2 processus | 13 561 (**1,08**) | 12 126 (**1,07**) | 197 905 (**1,26**) |
| nginx, 2 processus | 12 513 (1,00) | 11 303 (1,00) | 157 224 (1,00) |
| Apache, 2 processus | 6 939 (0,55) | 7 035 (0,62) | 153 265 (0,97) |
| Caddy, 2 processus | 5 059 (0,40) | 3 744 (0,33) | 22 094 (0,14) |
| **omega-serv, moteur natif** | **4 738 (0,38)** | **3 115 (0,28)** | **96 277 (0,61)** |
| omega-serv, natif + WAF † | 4 229 (0,37) | 2 926 (0,27) | 98 185 (0,62) |
| omega-serv, moteur Python, 2 processus | 1 741 (0,14) | 1 154 (0,10) | 18 806 (0,12) |
| omega-serv, moteur Python | 1 329 (0,11) | 611 (0,05) | 9 805 (0,06) |

### Gros fichier (5 Mo) : débit

| Serveur | Machine A | Machine B | Machine C |
|---|---:|---:|---:|
| lighttpd, 2 processus | 2 440 Mo/s (1,05) | 2 110 Mo/s (0,99) | 28 011 Mo/s (0,81) |
| nginx, 2 processus | 2 322 Mo/s (1,00) | 2 124 Mo/s (1,00) | 34 651 Mo/s (1,00) |
| Apache, 2 processus | 2 355 Mo/s (1,01) | 2 134 Mo/s (1,00) | 41 153 Mo/s (**1,19**) |
| **omega-serv, moteur natif** | **2 294 Mo/s (0,99)** | **1 936 Mo/s (0,91)** | **37 918 Mo/s (1,09)** |
| Caddy, 2 processus | 2 205 Mo/s (0,95) | 1 996 Mo/s (0,94) | 3 811 Mo/s (0,11) |
| omega-serv, moteur Python, 2 processus | 2 145 Mo/s (0,92) | 1 931 Mo/s (0,91) | 25 829 Mo/s (0,75) |
| omega-serv, moteur Python | 1 686 Mo/s (0,73) | 1 472 Mo/s (0,69) | 14 227 Mo/s (0,41) |

### Mémoire (PSS, tous processus du serveur) : au repos → après la charge

omega-serv : version 3.0.0, remesurée le 19 novembre 2026 (les valeurs de la 2.5 sont au §6). Autres serveurs : campagne du 4 novembre.

| Serveur | Machine A | Machine B | Machine C |
|---|---:|---:|---:|
| lighttpd | 1 → 1 Mo | 1 → 1 Mo | 1 → 1 Mo |
| nginx | 4 → 5 Mo | 5 → 5 Mo | 4 → 4 Mo |
| Apache | 4 → 7 Mo | 4 → 7 Mo | 4 → 7 Mo |
| **omega-serv, moteur natif** | **10 → 10 Mo** | **10 → 12 Mo** | **12 → 16 Mo** |
| omega-serv, moteur Python | 20 → 23 Mo | 21 → 24 Mo | 22 → 28 Mo |
| omega-serv, natif + WAF | 28 → 30 Mo | 29 → 32 Mo | 30 → 33 Mo |
| omega-serv, moteur Python, 2 processus | 35 → 46 Mo | 36 → 46 Mo | 38 → 48 Mo |
| omega-serv, natif + WAF, 2 processus de sécurité ‡ | 28 → 28 Mo | 29 → 31 Mo | 51 → 55 Mo |
| Caddy, 2 processus | 50 → 57 Mo | 46 → 54 Mo | 48 → 62 Mo |

‡ Sur les machines A et B, le serveur ne dispose que de 2 cœurs : omega-serv n'y lance qu'un processus de sécurité (il en lance 2 à partir de 4 cœurs). Sur la machine C, avec 2 processus de sécurité, le superviseur Python garde sa forme complète, nécessaire aux compteurs qu'ils partagent : 51 Mo au lieu de 30.

### À nombre de cœurs égal : machine C avec 4 processus

Campagne séparée du 3 novembre, même protocole, sur la machine C : chaque serveur reçoit 4 processus (ou 4 cœurs pour Caddy et le moteur natif). Référence : nginx avec 4 processus. Le moteur natif avec WAF n'y figure plus : mesuré avant l'optimisation du WAF, il n'est pas encore remesuré à 4 processus. Mémoire d'omega-serv : 3.0.0, remesurée le 19 novembre (débits : 2.5, 3 novembre).

| Serveur | 1 Ko | 100 Ko | 5 Mo | Mémoire |
|---|---:|---:|---:|---:|
| lighttpd, 4 processus | 638 907 (**1,46**) | 312 402 (**1,21**) | 41 982 Mo/s (0,93) | 1 → 2 Mo |
| nginx, 4 processus | 438 496 (1,00) | 258 242 (1,00) | 45 162 Mo/s (1,00) | 5 → 5 Mo |
| **omega-serv, moteur natif** | **294 083 à 310 972 (0,67 à 0,71)** | **108 991 à 109 955 (0,42)** | **40 137 à 40 463 Mo/s (0,89 à 0,90)** | **12 → 16 à 18 Mo** |
| Apache, 4 processus | 200 592 (0,46) | 162 607 (0,63) | 39 664 Mo/s (0,88) | 6 → 9 Mo |
| Caddy, 4 cœurs | 97 085 (0,22) | 35 900 (0,14) | 5 998 Mo/s (0,13) | 52 → 67 Mo |
| omega-serv, moteur Python, 4 processus | 37 697 (0,09) | 35 064 (0,14) | 37 123 Mo/s (0,82) | 45 → 60 Mo |

### Lecture

- **Le moteur natif change la place d'omega-serv.**
  - Sur les petits fichiers, il passe de 0,03-0,11 fois nginx (moteur Python) à environ **0,7 fois nginx**, quelle que soit la machine.
  - Il se place devant Apache et Caddy, et derrière nginx et lighttpd, qui restent les plus rapides.
  - Sa latence p99 est proche de celle de nginx.
- **lighttpd est le plus rapide sur les petits et moyens fichiers**, sur les trois machines, et le plus économe en mémoire. Sa documentation déconseille pourtant `server.max-worker` (plusieurs processus), que nous avons utilisé pour comparer à nombre de processus égal.
- **Les fichiers moyens sont le point faible actuel du moteur natif** : 0,28 à 0,61 fois nginx, derrière Apache, et pas meilleur avec plus de cœurs. C'est une piste d'amélioration identifiée.
- **Sur les gros fichiers**, les serveurs se rejoignent, car c'est le noyau qui copie les données (`sendfile`). Caddy fait exception sur la machine C : nous n'avons pas cherché à optimiser sa configuration de base.
- **Le WAF coûte peu au moteur natif, et il faut le lire avec justesse.**
  - Le moteur natif cherche lui-même les règles du WAF : une requête sur laquelle aucune ne correspond est servie sans passer par Python. Au moindre doute (correspondance, texte non ASCII, source suivie par Active Defense, zone d'authentification…), c'est Python qui décide. Avec le WAF, le moteur natif garde ainsi 78 à 95 % de son débit sur les petits fichiers, et 93 à 99 % sur les fichiers de 100 Ko. Avant cette optimisation, son débit était divisé par 4 à 7.
  - La limite de débit est comptée par le moteur natif : l'activer ne change pas ces chiffres (machine A : 11 391 req/s avec, 11 330 sans). Si magnet est actif, toutes les requêtes passent encore par Python, et le coût redevient celui d'avant.
  - omega-serv avec WAF reste devant Apache et Caddy **sans** WAF.
  - nginx, lighttpd, Apache et Caddy ont été mesurés **sans** WAF. Un WAF ajouté à ces serveurs (ModSecurity, Coraza) a lui aussi un coût, que nous n'avons pas mesuré. La comparaison « avec WAF » n'est donc pas faite à armes égales, et nous ne prétendons pas qu'omega-serv serait plus rapide qu'un autre serveur équipé d'un WAF.
- **Plusieurs processus de sécurité n'aident plus le trafic ordinaire** : il ne passe plus par eux, et le débit reste le même avec 2 processus (−2 à −4 %, dans le bruit de mesure). Ils ne servent que lorsque beaucoup de requêtes passent par Python (magnet actif, attaque) : mesuré avant l'optimisation, alors que toutes les requêtes y passaient, 2 processus de sécurité multipliaient le débit avec WAF par 1,5 à 1,7 sur 4 cœurs, mais n'apportaient que 5 à 12 % sur 2 cœurs.
- **Le moteur Python progresse avec les processus** (×1,6 à ×2 avec 2 processus, environ ×3,5 avec 4), mais il reste à 5-11 % de nginx.
- **Mémoire** : avec le moteur natif sans WAF, omega-serv 3.0.0 occupe 10 à 16 Mo, deux à quatre fois nginx ou Apache et trois à six fois moins que Caddy. Avec le WAF ou le moteur Python, il faut compter 20 à 33 Mo, essentiellement pour Python : un processus Python avec asyncio coûte au moins 10 Mo. Avec un processus, c'est 30 à 70 % de moins qu'en 2.5 (§6).
- **Pour situer ces chiffres** : même le cas le plus lent, le moteur Python avec WAF sur la machine B (564 req/s), représente près de 50 millions de requêtes par jour. C'est très au-delà des besoins d'un site personnel, d'un service interne ou d'un laboratoire. La vitesse n'est vraiment décisive que pour un site à fort trafic.

---

## 5. Performances en reverse proxy : omega-serv face à nginx, lighttpd, Apache, Caddy et Traefik

Ici, chaque serveur ne sert pas de fichiers : il **relaie** les requêtes vers un serveur d'application (le *backend*) et renvoie sa réponse. Mesures du 14 novembre 2026, avec omega-serv 3.0.0 (en préparation), dont le moteur natif relaie lui-même le reverse proxy.

### Protocole propre à ces mesures

- **Même backend pour tous** : un nginx statique à 2 processus, qui sert `small.html` (1 Ko) et `medium.png` (100 Ko). Chaque mesure vérifie que la réponse vient bien du backend (en-tête ajouté par lui) : le proxy relaie, il ne sert jamais le fichier lui-même.
- **Cœurs** : machine A, le proxy sur un cœur physique (threads 0 et 2), le client et le backend sur l'autre (1 et 3) ; machine B, le proxy sur les cœurs 0 et 1, le client et le backend sur 2 et 3 ; machine C, le proxy sur les 4 cœurs Zen 5 (0 à 3), le backend sur 2 cœurs Zen 5c (4 et 5), le client sur les 4 autres (6 à 9).
- **Processus** : 2 sur les machines A et B, **4 sur la machine C**, pour que chaque serveur utilise tous les cœurs donnés au proxy. Le moteur natif d'omega-serv utilise toujours tous ces cœurs, avec un processus de sécurité Python.
- **HTTP et HTTPS** côté client (certificat ECDSA P-256 auto-signé) ; le backend est toujours joint en HTTP.
- **Configurations** :
  - nginx : `proxy_pass` vers un groupe `upstream` qui garde ses connexions vers le backend (`keepalive 64`) ; sans ce réglage, absent de sa configuration de base, nginx ouvre une connexion par requête ;
  - lighttpd : `mod_proxy`, configuration de base ;
  - Apache : `mod_proxy` et `mod_proxy_http`, MPM `event`, une ligne `ProxyPass` ;
  - Caddy : `reverse_proxy`, configuration de base ;
  - Traefik 3.7 : un routeur et un service, configuration de base ;
  - omega-serv : une zone de reverse proxy sur `/`, profil `standard`, moteur natif sans puis avec le WAF (toutes ses règles livrées, sans limite de débit), et moteur Python à 2 processus.
- **Le reste ne change pas** (§3) : journal d'accès actif partout, oha, 32 connexions persistantes, 10 secondes, 3 tours entrelacés, médiane. **Aucune erreur** : toutes les réponses sont des 200.

Entre parenthèses : le rapport avec nginx du même nombre de processus, mesuré dans la même session (= 1,00).

### Petites réponses (1 Ko) : requêtes par seconde

| Serveur | Machine A (2 processus) | Machine B (2 processus) | Machine C (4 processus) |
|---|---:|---:|---:|
| nginx | 11 151 (1,00) | 11 049 (1,00) | 246 595 (1,00) |
| **omega-serv, moteur natif** | **9 507 (0,85)** | **10 098 (0,91)** | **203 021 (0,82)** |
| omega-serv, natif + WAF | 9 078 (0,81) | 9 857 (0,89) | 190 201 (0,77) |
| lighttpd | 6 752 (0,61) | 6 242 (0,56) | 129 827 (0,53) |
| Apache | 6 616 (0,59) | 5 872 (0,53) | 124 458 (0,50) |
| Traefik | 3 940 (0,35) | 3 890 (0,35) | 70 465 (0,29) |
| Caddy | 3 578 (0,32) | 3 117 (0,28) | 55 910 (0,23) |
| omega-serv, moteur Python | 1 039 (0,09) | 859 (0,08) | — \* |

\* Le moteur Python n'a été mesuré qu'avec 2 processus sur la machine C : 11 530 req/s, soit 0,07 fois nginx à 2 processus (171 075 req/s).

### Réponses moyennes (100 Ko) : requêtes par seconde

| Serveur | Machine A | Machine B | Machine C |
|---|---:|---:|---:|
| **omega-serv, moteur natif** | **4 281 (1,11)** | **3 497 (0,97)** | **80 361 (1,43)** |
| omega-serv, natif + WAF | 4 236 (1,10) | 3 335 (0,93) | 73 025 (1,30) |
| nginx | 3 855 (1,00) | 3 605 (1,00) | 56 011 (1,00) |
| lighttpd | 2 834 (0,74) | 2 252 (0,62) | 53 523 (0,96) |
| Apache | 2 404 (0,62) | 2 357 (0,65) | 39 807 (0,71) |
| Traefik | 2 477 (0,64) | 2 181 (0,60) | 39 419 (0,70) |
| Caddy | 2 294 (0,60) | 1 956 (0,54) | 33 120 (0,59) |
| omega-serv, moteur Python | 821 (0,21) | 669 (0,19) | — |

### HTTPS : requêtes par seconde

| Serveur | 1 Ko : A | 1 Ko : B | 1 Ko : C | 100 Ko : A | 100 Ko : B | 100 Ko : C |
|---|---:|---:|---:|---:|---:|---:|
| nginx | 9 203 (1,00) | 9 305 (1,00) | 202 095 (1,00) | 780 (1,00) | 2 338 (1,00) | 47 609 (1,00) |
| **omega-serv, moteur natif** | **6 840 (0,74)** | **7 976 (0,86)** | **130 337 (0,64) †** | **690 (0,88)** | **1 917 (0,82)** | **42 507 (0,89)** |
| omega-serv, natif + WAF | 6 372 (0,69) | 7 456 (0,80) | 146 590 (0,73) † | 683 (0,88) | 1 882 (0,80) | 39 400 (0,83) |
| lighttpd | 5 188 (0,56) | 5 513 (0,59) | 130 572 (0,65) | 638 (0,82) | 1 381 (0,59) | 45 566 (0,96) |
| Apache | 5 038 (0,55) | 4 193 (0,45) | 114 898 (0,57) | 588 (0,75) | 1 368 (0,59) | 29 948 (0,63) |
| Traefik | 3 389 (0,37) | 3 195 (0,34) | 62 251 (0,31) | 889 (**1,14**) | 1 548 (0,66) | 28 513 (0,60) |
| Caddy | 3 263 (0,35) | 2 733 (0,29) | 54 279 (0,27) | 1 135 (**1,46**) | 1 424 (0,61) | 26 452 (0,56) |
| omega-serv, moteur Python | 922 (0,10) | 759 (0,08) | — | 423 (0,54) | 549 (0,23) | — |

† Sur la machine C, en HTTPS, le moteur natif varie beaucoup d'un tour à l'autre : 130 000 à 185 000 req/s sans WAF, 138 000 à 150 000 avec. L'écart entre les deux lignes est donc dans le bruit de cette mesure.

### Latence p99 sur les petites réponses (HTTP)

| Serveur | Machine A | Machine B | Machine C |
|---|---:|---:|---:|
| nginx | 7,7 ms | 7,8 ms | 0,4 ms |
| **omega-serv, moteur natif** | **10,5 ms** | **9,7 ms** | **0,6 ms** |
| omega-serv, natif + WAF | 9,6 ms | 11,0 ms | 0,8 ms |
| lighttpd | 11,9 ms | 14,0 ms | 0,9 ms |
| Apache | 14,7 ms | 21,3 ms | 2,0 ms |
| Traefik | 25,9 ms | 26,5 ms | 2,1 ms |
| Caddy | 23,9 ms | 27,2 ms | 2,5 ms |
| omega-serv, moteur Python | 41,0 ms | 47,6 ms | — |

### Mémoire du proxy (PSS) : au repos → après la charge, en HTTP

omega-serv : version 3.0.0, remesurée le 19 novembre 2026 ; les débits ci-dessus datent du 14 novembre.

| Serveur | Machine A | Machine B | Machine C |
|---|---:|---:|---:|
| lighttpd | 3 → 4 Mo | 3 → 4 Mo | 3 → 4 Mo |
| nginx | 7 → 8 Mo | 7 → 8 Mo | 10 → 11 Mo |
| Apache | 6 → 12 Mo | 6 → 12 Mo | 8 → 15 Mo |
| **omega-serv, moteur natif** | **27 → 28 Mo** | **27 → 28 Mo** | **29 → 33 Mo** |
| omega-serv, natif + WAF | 29 → 30 Mo | 29 → 31 Mo | 31 → 36 Mo |
| Caddy | 48 → 57 Mo | 48 → 59 Mo | 50 → 60 Mo |
| omega-serv, moteur Python | 42 → 50 Mo | 43 → 51 Mo | — |
| Traefik | 93 → 117 Mo | 107 → 131 Mo | 100 → 123 Mo |

En HTTPS, la mémoire après la charge augmente de 0 à 5 Mo pour la plupart des serveurs, davantage pour Apache (jusqu'à 66 Mo sur la machine C) et le moteur Python (jusqu'à 72 Mo) : voir les chiffres bruts.

### Lecture

- **En reverse proxy, omega-serv avec le moteur natif est deuxième derrière nginx**, sur les trois machines.
  - Sur les petites réponses, il relaie 0,82 à 0,91 fois autant que nginx. C'est 1,4 à 1,7 fois lighttpd et Apache, et 2,4 à 3,6 fois Traefik et Caddy.
  - Sa latence p99 est la plus basse après celle de nginx.
- **Sur les réponses de 100 Ko, il fait jeu égal avec nginx ou le dépasse** (0,97 à 1,43). Le moteur natif relaie la réponse au fil de l'eau, avec un tampon borné. Dans sa configuration de base, nginx ne garde en mémoire que quelques dizaines de Ko par réponse relayée (`proxy_buffers`) et peut écrire le reste dans un fichier temporaire. Nous n'avons pas réglé ce point.
- **En HTTPS**, le moteur natif reste deuxième sur les petites réponses des machines A et B. Sur la machine C, lighttpd et lui sont au même niveau.
  - Sur les réponses de 100 Ko, lighttpd passe devant lui sur la machine C.
  - Sur la machine A, Caddy et Traefik passent devant tout le monde, nginx compris. Ils sont écrits en Go, avec leur propre bibliothèque TLS, apparemment plus efficace sur ce processeur de 2010. Nous ne l'avons pas étudié davantage.
- **Le WAF coûte peu en reverse proxy** : 1 à 9 % du débit en HTTP, toutes règles actives. Les autres serveurs ont été mesurés sans WAF : la comparaison « avec WAF » n'est pas faite à armes égales (voir §4).
- **Mémoire** : avec le moteur natif, omega-serv 3.0.0 occupe environ 30 Mo (27 à 36 Mo). Ce total comprend le superviseur Python, le processus de sécurité et le moteur natif. C'est plusieurs fois nginx, lighttpd ou Apache, mais moins que Caddy et trois à quatre fois moins que Traefik. À la mesure du 14 novembre (3.0.0 en préparation), il occupait environ 50 Mo.
- **Le moteur Python** relaie à 0,08 à 0,10 fois nginx sur les petites réponses : il reste le moteur de repli. Les zones de reverse proxy avec cache lui sont toujours confiées, et gardent donc son débit.
- **Une correction faite avant ces mesures.** Un premier passage, le même jour et au même protocole, plaçait le moteur natif à 0,32 à 0,69 fois nginx sur les petites réponses. Il plafonnait vers 78 000 req/s sur la machine C, quel que soit le nombre de cœurs. Sa réserve de connexions vers le backend était trop petite : il en ouvrait une nouvelle toutes les cinq requêtes. Cette réserve a été agrandie et le relais allégé avant le passage publié ici. Les chiffres du premier passage sont publiés aussi.

### Limites propres à ces mesures

- **nginx est réglé en sa faveur** : il garde ses connexions vers le backend, ce qu'il ne fait pas dans sa configuration de base. Les autres serveurs sont dans leur configuration de base.
- **Le backend tourne sur la même machine**, en boucle locale. Sur les machines A et B, il partage ses cœurs avec le client. Seuls comptent donc les rapports entre serveurs, mesurés dans les mêmes conditions. Seul, ce backend sert environ 345 000 req/s sur la machine C : il n'y limite aucun des proxys.
- **HTTP/1.1 seulement**, vers le client comme vers le backend : omega-serv ne parle pas HTTP/2.
- **Chiffres bruts** : [`docs/benchmarks/`](benchmarks/), fichiers `2026-11-14-*-reverse-proxy-brut.txt`, dont le premier passage (`2026-11-14-reverse-proxy-avant-correctif-brut.txt`).

---

## 6. Les versions d'omega-serv : 1.0 → 2.0 → 2.5 → 3.0.0

Les trois versions ont été mesurées dans la même session que le §4, sur les trois machines, avec le même protocole. Entre parenthèses : le rapport avec nginx (2 processus) de la même session. † : campagne du 4 novembre après l'optimisation du WAF (voir §4). La 3.0.0 a été mesurée le 19 novembre, au même protocole ; ses rapports sont pris avec nginx (2 processus) remesuré dans cette session, qui reste à 3 % près de sa valeur du 4 novembre.

### Petits fichiers (1 Ko) : requêtes par seconde

| Version et mode | Machine A | Machine B | Machine C |
|---|---:|---:|---:|
| 1.0.0 | 1 547 (0,07) | 645 (0,03) | 8 870 (0,04) |
| 1.0.0 + WAF | 1 453 (0,07) | 561 (0,02) | 7 687 (0,03) |
| 2.0.0 | 1 740 (0,08) | 650 (0,03) | 10 245 (0,04) |
| 2.0.0 + WAF | 1 456 (0,07) | 565 (0,02) | 8 371 (0,03) |
| 2.0.0, 2 processus | 2 153 (0,10) | 1 277 (0,05) | 19 192 (0,08) |
| 2.0.0 + WAF, 2 processus | 1 775 (0,08) | 1 113 (0,05) | 15 351 (0,06) |
| 2.5, moteur Python | 1 507 (0,07) | 663 (0,03) | 10 553 (0,04) |
| 2.5, moteur Python + WAF | 1 561 (0,07) | 564 (0,02) | 8 365 (0,03) |
| 2.5, moteur Python, 2 processus | 2 354 (0,11) | 1 312 (0,05) | 19 911 (0,08) |
| 2.5, moteur Python + WAF, 2 processus | 1 901 (0,09) | 1 104 (0,04) | 15 783 (0,06) |
| **2.5, moteur natif** | **15 222 (0,70)** | **16 542 (0,67)** | **285 213 (1,15)** |
| **2.5, moteur natif + WAF †** | **11 990 (0,56)** | **12 998 (0,53)** | **264 484 (1,07)** |
| **2.5, moteur natif + WAF, 2 processus de sécurité †** | **11 746 (0,55)** | **12 718 (0,52)** | **253 527 (1,02)** |
| 3.0.0, moteur Python | 1 309 (0,06) | 752 (0,03) | 9 482 (0,04) |
| 3.0.0, moteur Python + WAF | 1 168 (0,05) | 653 (0,03) | 8 788 (0,04) |
| 3.0.0, moteur Python, 2 processus | 1 733 (0,08) | 1 154 (0,05) | 17 234 (0,07) |
| 3.0.0, moteur Python + WAF, 2 processus | 1 605 (0,07) | 994 (0,04) | 14 873 (0,06) |
| **3.0.0, moteur natif** | **14 503 (0,68)** | **15 075 (0,63)** | **276 938 (1,15)** |
| **3.0.0, moteur natif + WAF** | **12 762 (0,60)** | **11 618 (0,48)** | **257 741 (1,07)** |
| **3.0.0, moteur natif + WAF, 2 processus de sécurité** | **12 974 (0,61)** | **11 957 (0,50)** | **253 993 (1,06)** |

### Fichiers moyens, gros fichier et mémoire (1 processus, sans WAF)

| Version | 100 Ko, req/s (A / B / C) | 5 Mo, Mo/s (A / B / C) | Mémoire au repos → après la charge (A / B / C) |
|---|---|---|---|
| 1.0.0 | 1 071 / 563 / 7 625 | 578 / 549 / 3 640 | 21 → **98** / 22 → **98** / 23 → **73** Mo |
| 2.0.0 | 1 570 / 603 / 9 469 | 1 665 / 1 470 / 14 058 | 26 → 30 / 27 → 31 / 28 → 32 Mo |
| 2.5, moteur Python | 1 329 / 611 / 9 805 | 1 686 / 1 472 / 14 227 | 28 → 32 / 29 → 33 / 30 → 34 Mo |
| **2.5, moteur natif** | **4 738 / 3 115 / 96 277** | **2 294 / 1 936 / 37 918** | **33 → 34 / 34 → 35 / 35 → 39 Mo** |
| 3.0.0, moteur Python | 1 185 / 606 / 8 655 | 1 765 / 1 318 / 13 028 | 20 → 23 / 21 → 24 / 22 → 28 Mo |
| **3.0.0, moteur natif** | **4 665 / 3 026 / 100 513** | **2 399 / 1 932 / 40 755** | **10 → 10 / 10 → 12 / 12 → 16 Mo** |

### Gros téléchargements simultanés

Test : 3 téléchargements simultanés d'un fichier de 300 Mo, pendant qu'une petite page est demandée en continu. Deux passages par version et par machine, aux résultats presque identiques. La mémoire est ici la **RSS** de tous les processus du serveur, comme dans le test d'origine : elle compte plusieurs fois la mémoire partagée, ce qui donne des valeurs plus hautes que la PSS des autres tableaux.

| Version | Mémoire au plus haut | Petite page, pire cas : A / B / C |
|---|---:|---|
| 1.0.0 | **1 833 à 1 836 Mo** | **1,4 à 1,9 s** / **1,4 à 1,7 s** / 0,16 s |
| 2.0.0 | 39 à 42 Mo | 3 ms / 4 à 6 ms / 1 ms |
| 2.5, moteur Python | 41 à 44 Mo | 2 ms / 4 ms / 1 ms |
| 2.5, moteur natif | 49 à 55 Mo | 1 à 2 ms / 2 à 4 ms / moins de 1 ms |
| 3.0.0, moteur Python | 39 Mo | 3 ms / 5 à 8 ms / 1 ms |
| 3.0.0, moteur natif | 23 à 26 Mo | 1 ms / 2 à 3 ms / moins de 1 ms |

### Coût de la défense active (1.0 → 2.0)

Mesure du 26 octobre 2026 sur la machine A, non refaite depuis : coût d'une observation de menace par Active Defense, pour chaque requête suspecte, mesuré sur disque (ext4) sur 2 000 observations.

| Mesure | 1.0.0 | 2.0.0 |
|---|---:|---:|
| Médiane | 2,84 ms | 0,23 ms |
| p99 | 11,6 ms | 2,3 ms |
| Maximum | 18 à 20 ms | 37 à 46 ms |

La médiane est divisée par 12. Le maximum est en revanche plus élevé en 2.0 : quelques pics isolés, liés à l'écriture périodique du journal SQLite sur disque.

### Lecture

- **De la 1.0 à la 2.0**, le progrès porte sur la mémoire et les gros fichiers, pas sur la vitesse des petites pages :
  - la mémoire après la charge passe de 73-98 Mo à 30-32 Mo ;
  - pendant de gros téléchargements, elle passe de plus de 1,8 Go à environ 40 Mo, et le serveur reste réactif (quelques millisecondes au lieu de près de 2 secondes) ;
  - le débit des gros fichiers est multiplié par 2,7 à 3,9 ;
  - la 2.0 ajoute plusieurs processus, qui augmentent de 25 % à presque 100 % le débit des petites pages selon la machine.
  La 1.0 chargeait chaque fichier entièrement en mémoire avant de l'envoyer. La 2.0 l'envoie par blocs, ou le confie au noyau.
- **De la 2.0 à la 2.5, le moteur Python ne change pas de vitesse** : les écarts restent sous 4 % sur les machines B et C, et dans le bruit de mesure de la machine A (−13 % à +9 %), la plus sensible à la charge de fond. Tout le gain de la 2.5 vient du **moteur natif** : environ ×10 à ×27 sur les petits fichiers par rapport au moteur Python, et la latence divisée par 5 à 15.
- **En 2.5, le moteur natif occupait environ 5 Mo de plus** au repos que le moteur Python (PSS) : le prix du second programme. Avec le WAF, environ 8 Mo de plus encore : les règles chargées dans le natif.
- **De la 2.5 à la 3.0.0, la mémoire baisse de 30 à 70 %** avec un processus :
  - moteur natif : 33-35 → 10-12 Mo au repos. Quand rien d'autre ne l'exige, le superviseur Python se réduit à un petit programme de surveillance, qui ne garde en mémoire ni la configuration ni le serveur Python ;
  - moteur Python : 28-30 → 20-22 Mo. Le code d'une option n'est chargé que si elle est active, et la bibliothèque TLS seulement si elle sert ;
  - natif + WAF : 43-45 → 28-30 Mo. Le processus de sécurité naît du superviseur réduit et partage ses pages avec lui ;
  - moteur Python à 2 processus : 40-43 → 35-38 Mo ;
  - pendant de gros téléchargements : 39 Mo (Python) et 23 à 26 Mo (natif), contre 41 à 55 Mo ;
  - le moteur natif occupe désormais deux fois moins de mémoire que le moteur Python.
- **Le travail sur la mémoire ne change pas le débit** : un test entrelacé sur les machines B et C, code 3.0.0 avant et après ce travail, donne 1 à 4 % d'écart. Par rapport à la 2.5, le moteur Python à 2 processus sert 12 à 13 % de moins sur les machines B et C (26 % sur la machine A, la plus sensible à la charge de fond) ; le code 3.0.0 d'avant ce travail montre le même recul, qui vient donc d'autres changements de la 3.0.0 et reste à étudier. Les autres écarts avec la 2.5 vont de −13 % à +13 %, dans les deux sens.

### Ce qu'il faut savoir sur le moteur natif

- Il est **optionnel** : le moteur Python reste le moteur par défaut, et le moteur de repli.
- Il sert lui-même le contenu statique, les redirections, les réécritures, les alias, le cache, les pages d'erreur, les en-têtes de sécurité et TLS.
- Il cherche lui-même les règles du WAF et sert seul une requête sur laquelle aucune ne correspond. Toute autre requête (correspondance ou doute du WAF, Active Defense, authentification) est décidée par Python, avec exactement les mêmes contrôles et les mêmes journaux. Un contrôle réglable soumet quand même à Python une requête propre sur N, pour vérifier que les deux donnent le même verdict.
- Il relaie lui-même le reverse proxy, WebSocket compris (depuis la 3.0.0). Le listing de répertoire et les pages internes sont demandés à Python ; FastCGI, l'envoi de fichiers et les zones de reverse proxy avec cache lui sont confiés pour toute la connexion. Ces fonctions-là gardent donc la vitesse du moteur Python.
- Avec TLS direct, FastCGI, l'envoi de fichiers et les zones de reverse proxy avec cache ne sont pas pris en charge par le natif : c'est alors le moteur Python qui sert, et l'interface l'indique.
- Il demande glibc 2.38 ou plus récente et OpenSSL 3. S'il ne démarre pas, l'installation le recompile sur place, et à défaut omega-serv reste sur le moteur Python.

---

## 7. Comparatif des fonctions

Légende :
- ✅ intégré ;
- 🧩 module officiel du projet, à activer ou à installer ;
- 🔌 module ou plugin tiers ;
- ⚙️ via un outil externe ;
- ❌ absent.

« Commercial » désigne une fonction réservée à l'édition payante.

### Service HTTP

| Fonction | nginx | lighttpd | Caddy | Apache | Traefik | omega-serv 2.5 |
|---|---|---|---|---|---|---|
| Langage du serveur | C | C | Go | C | Go | Python, avec un moteur natif C++ optionnel |
| Servir des fichiers statiques | ✅ | ✅ | ✅ | ✅ | ❌ (proxy uniquement) | ✅ |
| ETag / 304 / Range | ✅ | ✅ | ✅ | ✅ | — | ✅ |
| Fichiers pré-compressés `.gz` / `.br` | ✅ `gzip_static` (`.br` : 🔌) | 🔌 script Lua (mod_magnet) | ✅ `precompressed` | 🧩 recette mod_rewrite | — | ✅ |
| Compression à la volée | ✅ | ✅ mod_deflate | ✅ | 🧩 mod_deflate | ✅ middleware | ❌ |
| HTTP/2 | ✅ | ✅ | ✅ | 🧩 mod_http2 | ✅ | ❌ |
| HTTP/3 (QUIC) | ✅ | ❌ | ✅ | ❌ | ✅ | ❌ |
| PHP via FastCGI | ✅ | ✅ | ✅ | ✅ | ❌ | ✅ |
| Plusieurs processus ou cœurs | ✅ workers | ⚠️ `max-worker`, déconseillé par la documentation | ✅ (Go, tous les cœurs) | ✅ MPM | ✅ (Go) | ✅ `server.workers` ; moteur natif : tous les cœurs |

### Reverse proxy

| Fonction | nginx | lighttpd | Caddy | Apache | Traefik | omega-serv 2.5 |
|---|---|---|---|---|---|---|
| Répartition de charge | ✅ tour de rôle, moins de connexions, hash | ✅ fair, round-robin, hash, sticky | ✅ une douzaine de stratégies | 🧩 mod_proxy_balancer | ✅ wrr, p2c, hrw, least-time | ✅ 7 stratégies, dont la charge réelle |
| Santé passive (écarter un serveur en panne) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Santé active (sonde périodique) | Commercial (NGINX Plus) | ❌ | ✅ | 🧩 mod_proxy_hcheck | ✅ | ✅ |
| Cache des réponses | ✅ `proxy_cache` | ❌ | 🔌 | 🧩 mod_cache | Commercial | ✅ |
| WebSocket | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Découverte de services (Docker, Kubernetes) | 🔌 | ❌ | 🔌 | ❌ | ✅ (cœur du projet) | ❌ |

### TLS

| Fonction | nginx | lighttpd | Caddy | Apache | Traefik | omega-serv 2.5 |
|---|---|---|---|---|---|---|
| Certificats automatiques (ACME, Let's Encrypt) | 🧩 `ngx_http_acme_module` | ⚙️ Certbot | ✅ par défaut | 🧩 mod_md | ✅ | ⚙️ Certbot, avec assistant intégré et renouvellement programmé |
| CA locale | ❌ | ❌ | ✅ CA interne (émission automatique) | ❌ | ❌ | ✅ génération, signature de CSR, révocation |

### Sécurité

| Fonction | nginx | lighttpd | Caddy | Apache | Traefik | omega-serv 2.5 |
|---|---|---|---|---|---|---|
| Limite de débit par client | ✅ `limit_req` | ⚠️ mod_evasive (connexions simultanées seulement) | 🔌 caddy-ratelimit | 🔌 mod_evasive, mod_qos | ✅ middleware | ✅ |
| Limite partagée entre processus | ✅ zone mémoire partagée | ❌ comptée par processus | — (1 seul processus) | selon le module | 1 instance ; plusieurs avec Redis | ✅ mémoire partagée |
| WAF (signatures SQLi/XSS, scanners…) | 🔌 ModSecurity, Commercial (App Protect) | ❌ (scripts Lua à écrire) | 🔌 Coraza | 🔌 ModSecurity | 🔌 plugins | ✅ intégré |
| Liste de blocage avec expiration, récidive | ⚙️ fail2ban | ⚙️ fail2ban | ⚙️ fail2ban | ⚙️ fail2ban | ⚙️ | ✅ intégré |
| Leurres, mode guerre, incidents, export IoC | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ Active Defense |
| Bans gradués dans la durée | ⚙️ fail2ban | ⚙️ fail2ban | ⚙️ fail2ban | ⚙️ fail2ban | ⚙️ | ✅ RIPOSTE |
| Audit de sécurité de la configuration | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ `audit security` |
| Mode observation (journaliser sans bloquer) | selon module | — | selon plugin | ✅ ModSecurity `DetectionOnly` | selon plugin | ✅ |

Bans gradués : bans de plus en plus longs pour les adresses qui reviennent, sur des semaines, en local ou au niveau du réseau. fail2ban les obtient avec son option `bantime.increment` ; RIPOSTE y ajoute des politiques mesurées sur les journaux et simulées avant activation, la levée d'une action et un arrêt d'urgence.

### Extensibilité

| Fonction | nginx | lighttpd | Caddy | Apache | Traefik | omega-serv 2.5 |
|---|---|---|---|---|---|---|
| Langage de script | 🧩 njs (JavaScript) ; 🔌 Lua (OpenResty) | ✅ Lua (mod_magnet) | modules Go (recompilation) | 🧩 mod_lua | plugins Go ou WebAssembly | 🔌 import de scripts mod_magnet (option `magnet`) |
| Écosystème de modules | très large | ciblé | large | très large | large | aucun : tout est intégré |

---

## 8. Administration et ergonomie

| Serveur | Mode d'administration principal | Interface | Rechargement sans coupure |
|---|---|---|---|
| nginx | fichiers de configuration | aucune (tableau de bord : NGINX Plus, commercial) | ✅ `nginx -s reload` |
| lighttpd | fichier de configuration | aucune (mod_status en lecture seule) | ✅ redémarrage gracieux |
| Caddy | Caddyfile ou JSON | API REST d'administration | ✅ via l'API |
| Apache | fichiers de configuration et `.htaccess` | aucune (mod_status en lecture seule) | ✅ `graceful` |
| Traefik | étiquettes de conteneurs, fichiers ou Kubernetes | tableau de bord web (lecture seule) | ✅ configuration dynamique |
| omega-serv | interface terminal (TUI) et ligne de commande (CLI) ; le fichier JSON n'a pas à être édité | **TUI complète au clavier et à la souris, 17 langues, aide intégrée** | ✅ pour la plupart des réglages ; redémarrage annoncé pour le port, TLS, le moteur et le nombre de processus |

Concrètement, avec omega-serv, la configuration, la sécurité, les journaux, les services système, les sauvegardes et les instances se gèrent depuis une seule interface. Chaque réglage est expliqué et vérifié avant d'être écrit. Avec les autres serveurs, on édite des fichiers texte, puis on fait appel à des outils séparés (Certbot, fail2ban, logrotate, ModSecurity, un outil de supervision…).

En contrepartie, l'approche « fichier de configuration » de nginx, Apache et Caddy s'automatise très bien (Ansible, conteneurs, gestion de version). omega-serv a une CLI scriptable, mais son écosystème d'automatisation reste limité.

---

## 9. Ce qu'omega-serv apporte de plus

Cette section ne retient que ce qu'aucun des serveurs comparés ne fournit tel quel, sans module tiers ni outil externe.

1. **Une administration complète en interface terminal.**
   - L'interface couvre tout le serveur : le site, la sécurité, les journaux, les services, les sauvegardes et les instances.
   - Elle s'utilise au clavier et à la souris, sur un serveur sans affichage graphique, même à travers SSH.
   - Elle est disponible en 17 langues et explique chaque réglage.
   - Les autres serveurs n'ont pas d'interface d'administration (nginx, lighttpd, Apache), ou seulement une API (Caddy) ou un tableau de bord en lecture seule (Traefik).
2. **Une sécurité active intégrée, sans module à assembler.**
   - Le WAF comprend des signatures, des listes de chemins éditables, la récidive, une liste de blocage avec expiration, la réputation et un mode observation.
   - Active Defense ajoute des leurres, un mode guerre, le suivi d'incidents, l'export d'indicateurs de compromission et une simulation à blanc.
   - RIPOSTE répond dans la durée : il garde la mémoire des adresses qui reviennent et leur applique des réponses graduées, des bans de plus en plus longs (1 h, 6 h, 24 h, 7 jours par défaut), locaux dans la liste de blocage ou réseau par fail2ban (omega-jail), ou un leurre prolongé. Chaque politique peut être mesurée sur les journaux réels et simulée avant d'être activée ; chaque action reste visible et peut être levée, avec un arrêt d'urgence.
   - Ailleurs, ces fonctions demandent d'assembler ModSecurity ou Coraza, des jeux de règles et fail2ban.
3. **Des limites de sécurité exactes avec plusieurs processus.**
   - Avec plusieurs processus, la limite de débit et la récidive du WAF sont partagées en mémoire entre eux. Un attaquant ne peut donc pas multiplier sa limite par le nombre de processus.
   - lighttpd documente le cas inverse : avec `server.max-worker`, `mod_evasive` et `mod_status` comptent séparément dans chaque processus.
   - nginx partage aussi ses compteurs (zones `limit_req`), mais il n'a pas de WAF intégré.
4. **Deux moteurs, un seul comportement.** Le moteur natif et le moteur Python produisent les mêmes réponses et les mêmes journaux, vérifiés automatiquement sur un banc de comparaison. Les outils qui lisent les journaux (fail2ban, par exemple) ne voient aucune différence.
5. **L'import de scripts lighttpd mod_magnet.**
   - Un script de protection Lua déjà écrit pour lighttpd s'importe sans être réécrit.
   - Il s'ajoute à la protection intégrée sans jamais pouvoir l'affaiblir, et sa compatibilité est vérifiée avant activation.
6. **La gestion de plusieurs instances.**
   - Un registre recense toutes les instances, et l'interface passe de l'une à l'autre.
   - Elle sait aussi désinstaller complètement une instance.
7. **Un audit de sécurité de la configuration** : la commande `audit security` est informative, ne bloque jamais et renvoie des codes de sortie exploitables dans un script.
8. **Des sources de journaux distantes.**
   - L'interface récupère par SSH le journal d'un autre serveur, à la demande, sans mot de passe enregistré.
   - Elle peut le lire avec lnav, en le fusionnant avec les journaux locaux.
9. **Un durcissement HTTP non désactivable**, actif dès l'installation, quel que soit le profil et le moteur :
   - validation stricte de l'en-tête Host ;
   - rejet des ambiguïtés Content-Length / Transfer-Encoding ;
   - en-têtes de sécurité et CSP sur les réponses du site, y compris ses pages d'erreur ;
   - lecture sûre de X-Forwarded-For ;
   - refus de démarrer en root.

---

## 10. Ce que les autres font mieux

- **Débit** : lighttpd et nginx restent les plus rapides sur les petits et moyens fichiers, sur les trois machines. Même avec le moteur natif, omega-serv sert environ 0,7 fois nginx et 0,5 fois lighttpd sur les petits fichiers, et 0,3 à 0,6 fois nginx sur les fichiers de 100 Ko. Pour un site à fort trafic, une API publique ou un CDN, ce sont eux qu'il faut choisir.
- **Fichiers moyens** : Apache sert les fichiers de 100 Ko plus vite que le moteur natif d'omega-serv, sur les trois machines.
- **Reverse proxy** :
  - nginx relaie les petites réponses 10 à 22 % plus vite que le moteur natif, et jusqu'à 1,6 fois plus vite en HTTPS sur la machine C ;
  - en HTTPS, sur les réponses de 100 Ko, lighttpd le dépasse sur la machine C, et Caddy et Traefik sur la machine A ;
  - nginx, lighttpd et Apache relaient avec 4 à 15 Mo de mémoire, omega-serv avec environ 30.
- **Mémoire** : lighttpd (1 Mo), nginx (4 à 5 Mo) et Apache (4 à 9 Mo) conviennent aux machines très contraintes (embarqué, petits conteneurs). omega-serv 3.0.0 en demande 10 à 55 selon le mode.
- **Coût de la sécurité** : le WAF garde un coût. Avec le moteur natif, il retire 5 à 22 % du débit sur les petits fichiers, limite de débit comprise : omega-serv avec WAF sert 0,53 à 0,56 fois nginx sans WAF sur les machines A et B. Une requête suspecte ou douteuse (correspondance d'une règle, texte non ASCII, source suivie par Active Defense) passe toujours par Python, et elle est servie au débit du moteur Python. Avec magnet actif, toutes les requêtes passent par Python, et le WAF divise alors le débit du moteur natif par 4 à 7, comme avant l'optimisation.
- **Protocoles** : HTTP/2 chez tous les autres, HTTP/3 chez nginx, Caddy et Traefik. omega-serv ne parle que HTTP/1.1.
- **HTTPS automatique** : Caddy et Traefik l'intègrent par défaut, et nginx (`ngx_http_acme_module`) et Apache (`mod_md`) avec un module officiel. omega-serv délègue à Certbot, avec un assistant et un renouvellement programmé.
- **Environnements conteneurisés** : la découverte automatique de services de Traefik (Docker, Kubernetes) n'a pas d'équivalent dans omega-serv.
- **Écosystème et maturité** : nginx et Apache offrent des milliers de modules, de guides et d'intégrations, et des décennies d'usage en production. Caddy offre un système de modules en Go. omega-serv est un projet jeune, maintenu par une seule personne, et son moteur natif est récent.
- **Compression à la volée** : omega-serv ne sert que des fichiers déjà compressés.

---

## 11. Quel serveur pour quel usage

| Besoin | Choix conseillé |
|---|---|
| Site à fort trafic, API publique, CDN, débit maximal | **nginx** ou **lighttpd** |
| Reverse proxy au débit maximal, HTTP/2 ou HTTP/3 vers les clients | **nginx** |
| Machine très contrainte, embarqué, fichiers statiques | **lighttpd** |
| Démarrage rapide avec HTTPS automatique, configuration courte | **Caddy** |
| Application PHP historique, `.htaccess`, hébergement mutualisé | **Apache** |
| Docker, Kubernetes, microservices | **Traefik** |
| Petit ou moyen site, service interne, laboratoire, VPN, administration sans éditer de fichiers | **omega-serv** (moteur natif si possible) |
| Serveur exposé où l'on veut voir et contrôler la sécurité (WAF, bannissements gradués, leurres) depuis une seule interface | **omega-serv** |
| Reverse proxy avec répartition, santé, cache et WAF, piloté depuis une interface | **omega-serv** (moteur natif : deuxième derrière nginx en débit) |
| Apprendre le durcissement HTTP et la défense active | **omega-serv** |

Ces outils se combinent aussi. Par exemple :
- nginx ou Traefik en frontal sur Internet, avec omega-serv derrière pour un service interne, sa sécurité et son administration ;
- omega-serv en reverse proxy interne devant plusieurs serveurs d'application.

---

## 12. Reproduire les mesures

Les outils sont livrés dans le dépôt, sous `tools/bench/`. Il faut nginx, lighttpd, Apache, Caddy et oha installés (et Traefik pour le reverse proxy), l'environnement de développement d'omega-serv (`.venv`), et, pour le moteur natif, le binaire compilé dans `native/omega-http-core/build-release`.

```sh
# 1. préparer un dossier de mesure (fichiers de test, configurations, omega-serv 1.0, 2.0 et version courante)
tools/bench/compare/setup.sh /chemin/mesure omega-serv-1.0.0.tar.gz omega-serv-2.0.0.tar.gz

# 2. les 21 configurations, 3 répétitions entrelacées (40 à 60 minutes)
#    SRV_CPUS / CLI_CPUS : cœurs du serveur et du client (lscpu -e donne la topologie)
SRV_CPUS=0,1 CLI_CPUS=2,3 tools/bench/compare/campaign.sh /chemin/mesure > resultats.txt

# 3. médianes
python3 tools/bench/compare/summarize.py resultats.txt

# autre liste de configurations, par exemple 4 processus
CONFIGS="nginx-4 lighttpd-4 caddy-4 apache-4 omega-v2-1-0-native omega-v2-4-1-native" \
  tools/bench/compare/campaign.sh /chemin/mesure > resultats-4.txt

# gros téléchargements (mémoire et réactivité) : version courante, moteur Python puis natif, puis 1.0
.venv/bin/python tools/bench/bigfile.py
BENCH_ENGINE=native .venv/bin/python tools/bench/bigfile.py
BENCH_SRC=/chemin/mesure/v1-archive/omega-serv/src \
BENCH_EXTRA_PATH=/chemin/mesure/v1-archive/omega-serv/vendor/omega-lib/src \
  .venv/bin/python tools/bench/bigfile.py

# reverse proxy (§5) : backend, certificat, configurations des 6 proxys, puis 3 répétitions entrelacées
#    machine C : SRV_CPUS=0-3 BACK_CPUS=4,5 CLI_CPUS=6-9 et CONFIGS="nginx-4 lighttpd-4 apache-4 caddy-4 traefik-4 omega-nat-1-0 omega-nat-1-1"
tools/bench/proxy/setup.sh /chemin/proxy /chemin/vers/traefik
SRV_CPUS=0,1 CLI_CPUS=2,3 tools/bench/proxy/campaign.sh /chemin/proxy > proxy.txt
python3 tools/bench/proxy/summarize.py proxy.txt

# remesure d'omega-serv seul (mémoire de la 3.0.0) : fichiers, gros téléchargements et reverse proxy, nginx en référence
MACHINE=a SRV_CPUS=0,2 CLI_CPUS=1,3 tools/bench/memoire-3.0.0.sh /chemin/mesure > memoire.txt

# mesurer n'importe quel autre serveur déjà lancé, sans oha
python3 tools/bench/bench_any.py --make-files /srv/webroot-de-test
python3 tools/bench/bench_any.py --port 8080
```

Noms des configurations : `nginx-N`, `lighttpd-N`, `apache-N`, `caddy-N` (N processus, ou N cœurs pour Caddy) ; `omega-vX-N-W` pour omega-serv (version `v1`, `v20` ou `v2` pour la version courante, N processus, W = 0 sans WAF ou 1 avec), suivi de `-native` pour le moteur natif.

Pour le reverse proxy : `nginx-N`, `lighttpd-N`, `apache-N`, `caddy-N`, `traefik-N`, `omega-py-N-W` (moteur Python) et `omega-nat-N-W` (moteur natif, N processus de sécurité), suivis de `-tls` pour HTTPS côté client.

Pour publier vos propres résultats, donnez la machine, les versions, la répartition des cœurs et les trois répétitions.

---

## 13. Sources

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
- [MPM event](https://httpd.apache.org/docs/2.4/mod/event.html)
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

**fail2ban**
- [`jail.conf` : `bantime.increment`, `bantime.factor`, `bantime.multipliers`, `bantime.maxtime` (bans allongés pour les récidivistes)](https://github.com/fail2ban/fail2ban/blob/master/config/jail.conf) (consulté le 4 novembre 2026)

**Outil de mesure**
- [oha](https://github.com/hatoo/oha)

---

*Comparatif réalisé par kraynux pour omega-serv 2.5 et 3.0.0 : mesures des 3 et 4 novembre 2026 sur trois machines (reverse proxy : 14 novembre 2026 ; mémoire d'omega-serv 3.0.0 : 19 novembre 2026 ; défense active : 26 octobre 2026). Pour toute décision de capacité, mesurez sur votre propre matériel avec les outils fournis.*
