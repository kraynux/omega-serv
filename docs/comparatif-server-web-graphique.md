# omega-serv face aux serveurs web du marché — version graphique

**omega-serv face à nginx · lighttpd · Apache · Caddy · Traefik — mesures sur trois machines (nov. 2026).**

🌐 **Français** · [English](translation/en/comparatif-server-web-graphique.md) · [Español](translation/es/comparatif-server-web-graphique.md) · [Português (Brasil)](translation/pt-BR/comparatif-server-web-graphique.md) · [Italiano](translation/it/comparatif-server-web-graphique.md) · [Deutsch](translation/de/comparatif-server-web-graphique.md) · [Nederlands](translation/nl/comparatif-server-web-graphique.md) · [Polski](translation/pl/comparatif-server-web-graphique.md) · [Русский](translation/ru/comparatif-server-web-graphique.md) · [中文](translation/zh-CN/comparatif-server-web-graphique.md) · [Tiếng Việt](translation/vi/comparatif-server-web-graphique.md) · [ไทย](translation/th/comparatif-server-web-graphique.md) · [Bahasa Indonesia](translation/id/comparatif-server-web-graphique.md) · [日本語](translation/ja/comparatif-server-web-graphique.md) · [한국어](translation/ko/comparatif-server-web-graphique.md) · [हिन्दी](translation/hi/comparatif-server-web-graphique.md) · [العربية](translation/ar/comparatif-server-web-graphique.md)

> **Lecture :** plus la barre est longue, plus le serveur est rapide. La référence **nginx = 1,00**.

## Légende des couleurs

<!-- 🖼️ IMAGE : legende-couleurs -->
<div align="center">
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/assets/stats-1.png" alt="Légende des couleurs" width="1024">
</div>

---

## 📊 Fichiers 1 Ko — débit (requêtes/s)

Machines A (i5 2010), B (Celeron 2016) et C (Ryzen 2024). Les barres sont normalisées par rapport à nginx (1,00) sur la même machine.

<!-- 🖼️ IMAGE : 1ko-banner — 3 colonnes côte à côte (Machine A · 2 cœurs | Machine B · 4 cœurs | Machine C · 10 cœurs), largeur totale -->
<div align="center">
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/assets/stats-2.png" alt="Fichiers 1 Ko — machines A, B et C" width="1024">
</div>

> \* Machine C : le moteur natif utilise 4 cœurs, nginx 2 processus (2 cœurs). À cœurs égaux, le rapport retombe à ~0,70.
---

## 📦 Fichiers moyens (100 Ko) — mode web normal

Ici, Apache surprend : il dépasse souvent le moteur natif d'omega-serv. lighttpd reste le plus rapide. Référence : nginx = 1,00.

<!-- 🖼️ IMAGE : 100ko-banner.png — 3 colonnes côte à côte (A | B | C), largeur totale -->
<div align="center">
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/assets/stats-3.png" alt="Fichiers 100 Ko — machines A, B et C" width="1024">
</div>

---

## 💿 Gros fichiers (5 Mo) — mode web normal

Sur les gros fichiers, les serveurs se rejoignent : c'est le noyau qui copie les données (sendfile). Caddy fait exception sur la machine C. Débit en Mo/s.

<!-- 🖼️ IMAGE : 5mo-banner.png — 3 colonnes côte à côte (A | B | C), largeur totale -->
<div align="center">
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/assets/stats-4.png" alt="Fichiers 5Mo — machines A, B et C" width="1024">
</div>

---

## 🔄 Reverse proxy — petites réponses (1 Ko)

Chaque proxy relaie vers un backend nginx. Référence : nginx = 1,00. Machine C : 4 processus.

<!-- 🖼️ IMAGE : proxy-1ko-banner.png — 3 colonnes côte à côte (A | B | C), largeur totale -->
<div align="center">
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/assets/stats-5.png" alt="Proxy 1 Ko — machines A, B et C" width="1024">
</div>

---

## 🔄 Reverse proxy — réponses 100 Ko

Sur les réponses moyennes, omega-serv natif fait jeu égal ou dépasse nginx.

<!-- 🖼️ IMAGE : proxy-100ko-banner.png — 3 colonnes côte à côte (A | B | C), largeur totale -->
<div align="center">
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/assets/stats-6.png" alt="Proxy 100 Ko — machines A, B et C" width="1024">
</div>

---

## 💾 Mémoire (PSS) — au repos → après charge

Plus la barre est courte, plus le serveur est économe. lighttpd, nginx et Apache sont les plus sobres ; omega-serv 3.0.0 (remesuré le 19 novembre) suit, avec 10 à 16 Mo pour le moteur natif.

<!-- 🖼️ IMAGE : memoire-banner.png — 3 colonnes côte à côte de jauges (A | B | C), largeur totale -->
<div align="center">
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/assets/stats-7.png" alt="Mémoire — machines A, B et C" width="1024">
</div>

---

## 🏆 Classement web normal — qui est le plus rapide ?

Synthèse des trois machines en service de fichiers statiques.

<!-- 🖼️ IMAGE : classement-web.png -->
<!-- Contenu : 1. 🥇 lighttpd — meilleur en petits & moyens fichiers · 2. 🥈 nginx — référence, excellent partout · 3. 🥉 omega-serv natif — très bon, 2ᵉ en reverse proxy · 4. Apache — bon, robuste, écosystème · 5. Caddy — simple, HTTPS auto · 6. omega-serv Python — moteur de repli -->
<div align="center">
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/assets/stats-8.png" alt="Classement web normal" width="1024">
</div>

---

## 🔄 Classement reverse proxy — qui est le meilleur ?

nginx reste la référence ; omega-serv natif est son dauphin le plus proche, loin devant les autres.

<!-- 🖼️ IMAGE : classement-proxy.png -->
<!-- Contenu : 1. 🥇 nginx · 2. 🥈 omega-serv natif — 0,82 à 0,91× nginx en 1 Ko · 3. 🥉 omega-serv + WAF — toujours devant lighttpd/Apache · 4. lighttpd — 0,53 à 0,61× · 5. Apache — 0,50 à 0,59× · 6. Traefik — 0,29 à 0,35× · 7. Caddy — 0,23 à 0,32× · 8. omega-serv Python — moteur de repli -->
<div align="center">
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/assets/stats-9.png" alt="Classement reverse proxy" width="1024">
</div>

---

## 🆚 Face à face — classement web & reverse proxy côte à côte

Deux usages, deux classements. Un serveur peut briller dans l'un et décevoir dans l'autre : Apache surprend en relais, Caddy déçoit partout sauf pour sa simplicité.

<!-- 🖼️ IMAGE : face-a-face.png — 2 colonnes côte à côte (web | proxy), largeur totale -->
<div align="center">
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/assets/stats-10.png" alt="Face à face web vs reverse proxy" width="1024">
</div>

### Synthèse croisée

| Serveur | Positionnement |
|---|---|
| 🟢 **omega-serv natif** | Le plus polyvalent : 3ᵉ en web, **2ᵉ en reverse proxy**. Seul serveur avec un WAF intégré qui reste devant lighttpd et Apache en relais. Le meilleur compromis pour un seul outil couvrant les deux usages, avec la sécurité en plus. |
| 🔵 **nginx** | Le plus régulier : 2ᵉ en web, **1ᵉ en reverse proxy**. Toujours dans le haut du classement, sans point faible marquant. Le choix par défaut sans exigence particulière. |
| 🟢 **lighttpd** | Le sprinteur du statique : **1ᵉ en web**, mais 4ᵉ en relais. Meilleur choix pour du statique pur, laisse la place à omega-serv ou nginx dès qu'on ajoute du reverse proxy. |
| 🔴 **Apache** | Le contre-exemple : 4ᵉ en web, 5ᵉ en relais. Sur les gros fichiers, il surprend même nginx (machine C). Ni le plus rapide ni le plus léger : son atout reste l'écosystème PHP. |
| 🟠 **Caddy** | La simplicité avant la vitesse : 5ᵉ en web, **7ᵉ en relais**. Pas fait pour le débit : HTTPS automatique et config courte. À réserver aux petits projets. |
| 🟣 **Traefik** | Hors catégorie web : pas serveur de fichiers, 6ᵉ en relais. Son terrain reste Docker et Kubernetes, pas la performance brute. |

---

## 📋 Tableau récapitulatif complet — ratios vs nginx (1,00)

Vue d'ensemble de **toutes** les métriques : mode web normal (1 Ko, 100 Ko, 5 Mo) et reverse proxy (1 Ko, 100 Ko), plus la mémoire. Plus la valeur est proche de 1,00 ou au-dessus, meilleur c'est.

| Serveur | Web 1 Ko (A/B/C) | Web 100 Ko (A/B/C) | Web 5 Mo (A/B/C) | Proxy 1 Ko (A/B/C) | Proxy 100 Ko (A/B/C) | Mémoire (A/B/C) |
|---|---|---|---|---|---|---|
| **lighttpd** | 1,52 / 1,26 / 1,53 | 1,08 / 1,07 / 1,26 | 1,05 / 0,99 / 0,81 | 0,61 / 0,56 / 0,53 | 0,74 / 0,62 / 0,96 | 1 Mo |
| **nginx** | 1,00 / 1,00 / 1,00 | 1,00 / 1,00 / 1,00 | 1,00 / 1,00 / 1,00 | 1,00 / 1,00 / 1,00 | 1,00 / 1,00 / 1,00 | 4–5 Mo |
| **omega-serv (natif)** | **0,70 / 0,67 / 1,15\*** | **0,38 / 0,28 / 0,61** | **0,99 / 0,91 / 1,09** | **0,85 / 0,91 / 0,82** | **1,11 / 0,97 / 1,43** | 10–16 Mo |
| **omega-serv + WAF** | 0,56 / 0,53 / 1,07\* | 0,37 / 0,27 / 0,62 | — | 0,81 / 0,89 / 0,77 | 1,10 / 0,93 / 1,30 | 28–33 Mo |
| **Apache** | 0,42 / 0,35 / 0,76 | 0,55 / 0,62 / 0,97 | 1,01 / 1,00 / 1,19 | 0,59 / 0,53 / 0,50 | 0,62 / 0,65 / 0,71 | 4–9 Mo |
| **Caddy** | 0,26 / 0,17 / 0,21 | 0,40 / 0,33 / 0,14 | 0,95 / 0,94 / 0,11 | 0,32 / 0,28 / 0,23 | 0,60 / 0,54 / 0,59 | 46–67 Mo |
| **Traefik** | — | — | — | 0,35 / 0,35 / 0,29 | 0,64 / 0,60 / 0,70 | 93–131 Mo |
| **omega-serv (Python)** | 0,11 / 0,05 / 0,08 | 0,14 / 0,10 / 0,12 | 0,92 / 0,91 / 0,75 | 0,09 / 0,08 / 0,07 | 0,21 / 0,19 / — | 20–48 Mo |

> \* Machine C : 4 cœurs pour le natif vs 2 pour nginx ; à cœurs égaux, ratio ~0,67–0,71.
> Les trois valeurs par cellule correspondent aux machines **A / B / C**. « — » : non mesuré ou non applicable.

---

## ⚖️ Forces et faiblesses — tous les serveurs

Chaque serveur a ses atouts et ses limites. Voici la vue complète, sans favoritisme.

### 🟢 omega-serv (natif)

**Points forts**
- ✅ Administration complète en terminal (TUI, 17 langues)
- ✅ WAF + Active Defense + RIPOSTE intégrés
- ✅ Moteur natif C++ : ~0,7× nginx en statique
- ✅ 2ᵉ en reverse proxy derrière nginx
- ✅ Limites partagées entre processus (sécurité exacte)
- ✅ Import scripts lighttpd mod_magnet
- ✅ Gestion multi-instances
- ✅ Administration Web


**Points faibles**
- ❌ Pas de HTTP/2 ni HTTP/3
- ❌ Pas de compression à la volée
- ❌ Pas de découverte Docker/Kubernetes
- ❌ ACME via Certbot (pas intégré nativement)
- ❌ Fichiers 100 Ko : 0,3–0,6× nginx
- ❌ Mémoire 10–55 Mo selon le mode (vs 1–5 Mo nginx/lighttpd)
- ❌ Écosystème jeune, maintenu par une personne

---

### 🔵 nginx

**Points forts**
- ✅ Référence de performance et de stabilité
- ✅ HTTP/2, HTTP/3, compression
- ✅ Écosystème immense (modules, docs, communauté)
- ✅ Très économe en mémoire (4–5 Mo)
- ✅ Reverse proxy excellent
- ✅ Module ACME officiel
- ✅ Configuration mature et éprouvée

**Points faibles**
- ❌ Configuration verbeuse, syntaxe propre à apprendre
- ❌ Pas de WAF intégré (nécessite ModSecurity ou équivalent)
- ❌ Pas d'interface d'administration native
- ❌ Rechargement de config parfois délicat en production
- ❌ Version open source limitée (certaines fonctions en Nginx Plus payant)
- ❌ Pas de découverte Docker/Kubernetes native (via templates)

---

### 🟢 lighttpd

**Points forts**
- ✅ Le plus rapide sur petits/moyens fichiers
- ✅ Le plus économe en mémoire (1 Mo)
- ✅ Léger, adapté aux systèmes contraints
- ✅ Bon reverse proxy
- ✅ Configuration simple et lisible

**Points faibles**
- ❌ Pas de HTTP/3 (HTTP/2 partiel selon build)
- ❌ 4ᵉ seulement en reverse proxy (0,53–0,61× nginx)
- ❌ Écosystème plus restreint que nginx/Apache
- ❌ Pas de WAF intégré
- ❌ Pas de découverte Docker/Kubernetes
- ❌ Développement moins actif que par le passé
- ❌ Faible sur les gros fichiers (0,81× nginx sur machine C)

---

### 🔴 Apache

**Points forts**
- ✅ Écosystème historique immense (modules, `.htaccess`, PHP)
- ✅ Robuste et éprouvé depuis des décennies
- ✅ Excellent sur les gros fichiers (dépasse nginx sur machine C)
- ✅ Support `.htaccess` sans redémarrage
- ✅ Compression, HTTP/2, ACME disponibles
- ✅ Documentation abondante

**Points faibles**
- ❌ Lent sur petits fichiers (0,35–0,42× nginx)
- ❌ Gourmand en mémoire en mode prefork (4–9 Mo, monte vite en charge)
- ❌ Modèle de processus moins efficace que l'event-driven
- ❌ Configuration verbeuse
- ❌ 5ᵉ en reverse proxy (0,50–0,59× nginx)
- ❌ Pas de WAF intégré (ModSecurity en module séparé)
- ❌ Surface d'attaque historiquement plus large

---

### 🟠 Caddy

**Points forts**
- ✅ HTTPS automatique (ACME intégré, zéro config)
- ✅ Configuration très courte et lisible (Caddyfile)
- ✅ HTTP/2 et HTTP/3 natifs
- ✅ Binaire unique, déploiement simple
- ✅ Reverse proxy correct sur réponses moyennes

**Points faibles**
- ❌ Lent en débit brut (5ᵉ en web, 7ᵉ en relais)
- ❌ Mémoire élevée (46–67 Mo)
- ❌ Très faible sur gros fichiers machine C (0,11× nginx)
- ❌ Pas de WAF intégré
- ❌ Écosystème plus jeune que nginx/Apache
- ❌ Peu adapté aux très hauts débits

---

### 🟣 Traefik

**Points forts**
- ✅ Découverte automatique Docker/Kubernetes
- ✅ Idéal en environnement conteneurisé
- ✅ HTTPS automatique (ACME intégré)
- ✅ Configuration dynamique sans redémarrage
- ✅ Bon en reverse proxy sur réponses moyennes (0,60–0,70× nginx)

**Points faibles**
- ❌ Pas un serveur de fichiers (absent du classement web)
- ❌ 6ᵉ en reverse proxy (0,29–0,35× nginx en 1 Ko)
- ❌ Mémoire très élevée (93–131 Mo)
- ❌ Complexité de configuration hors contexte conteneurs
- ❌ Pas de WAF intégré
- ❌ Surdimensionné pour un simple site statique

---

## 🎯 Quel serveur pour quel usage ?

| Usage | Serveur recommandé | Raison |
|---|---|---|
| Site à fort trafic | **nginx** ou **lighttpd** | Débit maximal, HTTP/2-3 |
| Machine contrainte / embarqué | **lighttpd** | 1 Mo de mémoire, le plus rapide et le moins gourmand |
| HTTPS automatique simple | **Caddy** | Certificats automatiques, configuration courte |
| Docker / Kubernetes | **Traefik** | Découverte de services |
| Application PHP / .htaccess | **Apache** | Écosystème historique |
| Reverse Proxy | **nginx** ou **omega-serv (natif)** | Meilleures performances |
| Sites web + sécurité + interface | **omega-serv (natif)** | Infra complète : WAF, administration WEB, multi-instance, Reverse-proxy, gestionnaire de logs, backup... |

---

Données issues du comparatif omega-serv (novembre 2026) — kraynux. Licence MIT.
[oha](https://github.com/hatoo/oha) pour la mesure · graphiques HTML/CSS autonomes.

> *Version graphique du comparatif mesuré d'omega-serv (mêmes chiffres que le comparatif détaillé : mesures des 3 et 4 novembre 2026 sur trois machines ; reverse proxy : 14 novembre 2026 ; mémoire d'omega-serv 3.0.0 : 19 novembre 2026). Pour toute décision de capacité, mesurez sur votre propre matériel.*
>
> Copyright © 2026 kraynux — kraynux@proton.me — Licence MIT (voir fichier LICENSE).
