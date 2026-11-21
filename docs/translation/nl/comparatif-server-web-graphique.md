# omega-serv tegenover de webservers op de markt — grafische versie

**omega-serv tegenover nginx · lighttpd · Apache · Caddy · Traefik — metingen op drie machines (nov. 2026).**

🌐 [Français](../../comparatif-server-web-graphique.md) · [English](../en/comparatif-server-web-graphique.md) · [Español](../es/comparatif-server-web-graphique.md) · [Português (Brasil)](../pt-BR/comparatif-server-web-graphique.md) · [Italiano](../it/comparatif-server-web-graphique.md) · [Deutsch](../de/comparatif-server-web-graphique.md) · **Nederlands** · [Polski](../pl/comparatif-server-web-graphique.md) · [Русский](../ru/comparatif-server-web-graphique.md) · [中文](../zh-CN/comparatif-server-web-graphique.md) · [Tiếng Việt](../vi/comparatif-server-web-graphique.md) · [ไทย](../th/comparatif-server-web-graphique.md) · [Bahasa Indonesia](../id/comparatif-server-web-graphique.md) · [日本語](../ja/comparatif-server-web-graphique.md) · [한국어](../ko/comparatif-server-web-graphique.md) · [हिन्दी](../hi/comparatif-server-web-graphique.md) · [العربية](../ar/comparatif-server-web-graphique.md)

> **Leeswijzer:** hoe langer de balk, hoe sneller de server. De referentie is **nginx = 1,00**.

## Kleurenlegenda

<!-- 🖼️ IMAGE : legende-couleurs -->
<div align="center">
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/translation/nl/omega-serv/stats-1.png" alt="Kleurenlegenda" width="1024">
</div>

---

## 📊 Bestanden van 1 kB — doorvoer (verzoeken/s)

Machines A (i5 2010), B (Celeron 2016) en C (Ryzen 2024). De balken zijn genormaliseerd ten opzichte van nginx (1,00) op dezelfde machine.

<!-- 🖼️ IMAGE : 1ko-banner — 3 colonnes côte à côte (Machine A · 2 cœurs | Machine B · 4 cœurs | Machine C · 10 cœurs), largeur totale -->
<div align="center">
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/translation/nl/omega-serv/stats-2.png" alt="Bestanden van 1 kB — machines A, B en C" width="1024">
</div>

> \* Machine C: de native engine gebruikt 4 kernen, nginx 2 processen (2 kernen). Bij een gelijk aantal kernen zakt de verhouding terug naar ~0,70.
---

## 📦 Middelgrote bestanden (100 kB) — normale webmodus

Hier verrast Apache: hij overtreft vaak de native engine van omega-serv. lighttpd blijft de snelste. Referentie: nginx = 1,00.

<!-- 🖼️ IMAGE : 100ko-banner.png — 3 colonnes côte à côte (A | B | C), largeur totale -->
<div align="center">
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/translation/nl/omega-serv/stats-3.png" alt="Bestanden van 100 kB — machines A, B en C" width="1024">
</div>

---

## 💿 Grote bestanden (5 MB) — normale webmodus

Bij grote bestanden komen de servers dicht bij elkaar: het is de kernel die de gegevens kopieert (sendfile). Caddy vormt een uitzondering op machine C. Doorvoer in MB/s.

<!-- 🖼️ IMAGE : 5mo-banner.png — 3 colonnes côte à côte (A | B | C), largeur totale -->
<div align="center">
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/translation/nl/omega-serv/stats-4.png" alt="Bestanden van 5 MB — machines A, B en C" width="1024">
</div>

---

## 🔄 Reverse proxy — kleine antwoorden (1 kB)

Elke proxy stuurt door naar een nginx-backend. Referentie: nginx = 1,00. Machine C: 4 processen.

<!-- 🖼️ IMAGE : proxy-1ko-banner.png — 3 colonnes côte à côte (A | B | C), largeur totale -->
<div align="center">
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/translation/nl/omega-serv/stats-5.png" alt="Proxy 1 kB — machines A, B en C" width="1024">
</div>

---

## 🔄 Reverse proxy — antwoorden van 100 kB

Bij middelgrote antwoorden doet omega-serv native het even goed als nginx of beter.

<!-- 🖼️ IMAGE : proxy-100ko-banner.png — 3 colonnes côte à côte (A | B | C), largeur totale -->
<div align="center">
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/translation/nl/omega-serv/stats-6.png" alt="Proxy 100 kB — machines A, B en C" width="1024">
</div>

---

## 💾 Geheugen (PSS) — in rust → na belasting

Hoe korter de balk, hoe zuiniger de server. lighttpd, nginx en Apache zijn de zuinigste; omega-serv 3.0.0 (op 19 november opnieuw gemeten) volgt, met 10 tot 16 MB voor de native engine.

<!-- 🖼️ IMAGE : memoire-banner.png — 3 colonnes côte à côte de jauges (A | B | C), largeur totale -->
<div align="center">
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/translation/nl/omega-serv/stats-7.png" alt="Geheugen — machines A, B en C" width="1024">
</div>

---

## 🏆 Ranglijst normale webmodus — wie is de snelste?

Samenvatting van de drie machines bij het leveren van statische bestanden.

<!-- 🖼️ IMAGE : classement-web.png -->
<!-- Contenu : 1. 🥇 lighttpd — meilleur en petits & moyens fichiers · 2. 🥈 nginx — référence, excellent partout · 3. 🥉 omega-serv natif — très bon, 2ᵉ en reverse proxy · 4. Apache — bon, robuste, écosystème · 5. Caddy — simple, HTTPS auto · 6. omega-serv Python — moteur de repli -->
<div align="center">
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/translation/nl/omega-serv/stats-8.png" alt="Ranglijst normale webmodus" width="1024">
</div>

---

## 🔄 Ranglijst reverse proxy — wie is de beste?

nginx blijft de referentie; omega-serv native is zijn dichtste achtervolger, ver voor de andere.

<!-- 🖼️ IMAGE : classement-proxy.png -->
<!-- Contenu : 1. 🥇 nginx · 2. 🥈 omega-serv natif — 0,82 à 0,91× nginx en 1 Ko · 3. 🥉 omega-serv + WAF — toujours devant lighttpd/Apache · 4. lighttpd — 0,53 à 0,61× · 5. Apache — 0,50 à 0,59× · 6. Traefik — 0,29 à 0,35× · 7. Caddy — 0,23 à 0,32× · 8. omega-serv Python — moteur de repli -->
<div align="center">
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/translation/nl/omega-serv/stats-9.png" alt="Ranglijst reverse proxy" width="1024">
</div>

---

## 🆚 Rechtstreekse vergelijking — ranglijst web & reverse proxy naast elkaar

Twee toepassingen, twee ranglijsten. Een server kan in de ene schitteren en in de andere tegenvallen: Apache verrast bij doorsturen, Caddy valt overal tegen behalve qua eenvoud.

<!-- 🖼️ IMAGE : face-a-face.png — 2 colonnes côte à côte (web | proxy), largeur totale -->
<div align="center">
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/translation/nl/omega-serv/stats-10.png" alt="Rechtstreekse vergelijking web tegenover reverse proxy" width="1024">
</div>

### Gekruiste samenvatting

| Server | Positionering |
|---|---|
| 🟢 **omega-serv native** | De meest veelzijdige: 3e bij web, **2e bij reverse proxy**. De enige server met een ingebouwde WAF die bij doorsturen voor lighttpd en Apache blijft. Het beste compromis voor één enkel hulpmiddel dat beide toepassingen dekt, met extra beveiliging. |
| 🔵 **nginx** | De meest constante: 2e bij web, **1e bij reverse proxy**. Altijd in de top van de ranglijst, zonder opvallende zwakte. De standaardkeuze zonder bijzondere eisen. |
| 🟢 **lighttpd** | De sprinter voor statische inhoud: **1e bij web**, maar 4e bij doorsturen. De beste keuze voor puur statische inhoud, laat het veld aan omega-serv of nginx zodra er een reverse proxy bij komt. |
| 🔴 **Apache** | Het tegenvoorbeeld: 4e bij web, 5e bij doorsturen. Bij grote bestanden verrast hij zelfs nginx (machine C). Niet de snelste en niet de lichtste: zijn troef blijft het PHP-ecosysteem. |
| 🟠 **Caddy** | Eenvoud boven snelheid: 5e bij web, **7e bij doorsturen**. Niet gemaakt voor doorvoer: automatische HTTPS en korte configuratie. Te reserveren voor kleine projecten. |
| 🟣 **Traefik** | Buiten de webcategorie: geen bestandsserver, 6e bij doorsturen. Zijn terrein blijft Docker en Kubernetes, niet de ruwe prestaties. |

---

## 📋 Volledige overzichtstabel — verhoudingen ten opzichte van nginx (1,00)

Overzicht van **alle** metingen: normale webmodus (1 kB, 100 kB, 5 MB) en reverse proxy (1 kB, 100 kB), plus het geheugen. Hoe dichter de waarde bij 1,00 ligt of erboven, hoe beter.

| Server | Web 1 kB (A/B/C) | Web 100 kB (A/B/C) | Web 5 MB (A/B/C) | Proxy 1 kB (A/B/C) | Proxy 100 kB (A/B/C) | Geheugen (A/B/C) |
|---|---|---|---|---|---|---|
| **lighttpd** | 1,52 / 1,26 / 1,53 | 1,08 / 1,07 / 1,26 | 1,05 / 0,99 / 0,81 | 0,61 / 0,56 / 0,53 | 0,74 / 0,62 / 0,96 | 1 MB |
| **nginx** | 1,00 / 1,00 / 1,00 | 1,00 / 1,00 / 1,00 | 1,00 / 1,00 / 1,00 | 1,00 / 1,00 / 1,00 | 1,00 / 1,00 / 1,00 | 4–5 MB |
| **omega-serv (native)** | **0,70 / 0,67 / 1,15\*** | **0,38 / 0,28 / 0,61** | **0,99 / 0,91 / 1,09** | **0,85 / 0,91 / 0,82** | **1,11 / 0,97 / 1,43** | 10–16 MB |
| **omega-serv + WAF** | 0,56 / 0,53 / 1,07\* | 0,37 / 0,27 / 0,62 | — | 0,81 / 0,89 / 0,77 | 1,10 / 0,93 / 1,30 | 28–33 MB |
| **Apache** | 0,42 / 0,35 / 0,76 | 0,55 / 0,62 / 0,97 | 1,01 / 1,00 / 1,19 | 0,59 / 0,53 / 0,50 | 0,62 / 0,65 / 0,71 | 4–9 MB |
| **Caddy** | 0,26 / 0,17 / 0,21 | 0,40 / 0,33 / 0,14 | 0,95 / 0,94 / 0,11 | 0,32 / 0,28 / 0,23 | 0,60 / 0,54 / 0,59 | 46–67 MB |
| **Traefik** | — | — | — | 0,35 / 0,35 / 0,29 | 0,64 / 0,60 / 0,70 | 93–131 MB |
| **omega-serv (Python)** | 0,11 / 0,05 / 0,08 | 0,14 / 0,10 / 0,12 | 0,92 / 0,91 / 0,75 | 0,09 / 0,08 / 0,07 | 0,21 / 0,19 / — | 20–48 MB |

> \* Machine C: 4 kernen voor de native engine tegenover 2 voor nginx; bij een gelijk aantal kernen is de verhouding ~0,67–0,71.
> De drie waarden per cel horen bij de machines **A / B / C**. „—”: niet gemeten of niet van toepassing.

---

## ⚖️ Sterke en zwakke punten — alle servers

Elke server heeft zijn troeven en zijn beperkingen. Hier het volledige overzicht, zonder voorkeur.

### 🟢 omega-serv (native)

**Sterke punten**
- ✅ Volledig beheer in de terminal (TUI, 17 talen)
- ✅ WAF + Active Defense + RIPOSTE ingebouwd
- ✅ Native C++-engine: ~0,7× nginx bij statische bestanden
- ✅ 2e bij reverse proxy achter nginx
- ✅ Limieten gedeeld tussen processen (exacte beveiliging)
- ✅ Import van lighttpd mod_magnet-scripts
- ✅ Beheer van meerdere instanties
- ✅ Webbeheer


**Zwakke punten**
- ❌ Geen HTTP/2 of HTTP/3
- ❌ Geen compressie on the fly
- ❌ Geen Docker/Kubernetes-detectie
- ❌ ACME via Certbot (niet native geïntegreerd)
- ❌ Bestanden van 100 kB: 0,3–0,6× nginx
- ❌ Geheugen 10–55 MB afhankelijk van de modus (tegenover 1–5 MB bij nginx/lighttpd)
- ❌ Jong ecosysteem, onderhouden door één persoon

---

### 🔵 nginx

**Sterke punten**
- ✅ Referentie voor prestaties en stabiliteit
- ✅ HTTP/2, HTTP/3, compressie
- ✅ Enorm ecosysteem (modules, documentatie, community)
- ✅ Zeer zuinig met geheugen (4–5 MB)
- ✅ Uitstekende reverse proxy
- ✅ Officiële ACME-module
- ✅ Volwassen en beproefde configuratie

**Zwakke punten**
- ❌ Uitgebreide configuratie, eigen syntaxis die je moet leren
- ❌ Geen ingebouwde WAF (vereist ModSecurity of gelijkwaardig)
- ❌ Geen native beheerinterface
- ❌ Configuratie herladen soms lastig in productie
- ❌ Open-sourceversie beperkt (sommige functies in het betaalde Nginx Plus)
- ❌ Geen native Docker/Kubernetes-detectie (via templates)

---

### 🟢 lighttpd

**Sterke punten**
- ✅ De snelste bij kleine/middelgrote bestanden
- ✅ De zuinigste met geheugen (1 MB)
- ✅ Licht, geschikt voor beperkte systemen
- ✅ Goede reverse proxy
- ✅ Eenvoudige en leesbare configuratie

**Zwakke punten**
- ❌ Geen HTTP/3 (HTTP/2 gedeeltelijk, afhankelijk van de build)
- ❌ Slechts 4e bij reverse proxy (0,53–0,61× nginx)
- ❌ Kleiner ecosysteem dan nginx/Apache
- ❌ Geen ingebouwde WAF
- ❌ Geen Docker/Kubernetes-detectie
- ❌ Minder actieve ontwikkeling dan vroeger
- ❌ Zwak bij grote bestanden (0,81× nginx op machine C)

---

### 🔴 Apache

**Sterke punten**
- ✅ Enorm historisch ecosysteem (modules, `.htaccess`, PHP)
- ✅ Robuust en al tientallen jaren beproefd
- ✅ Uitstekend bij grote bestanden (overtreft nginx op machine C)
- ✅ Ondersteuning voor `.htaccess` zonder herstart
- ✅ Compressie, HTTP/2, ACME beschikbaar
- ✅ Uitgebreide documentatie

**Zwakke punten**
- ❌ Traag bij kleine bestanden (0,35–0,42× nginx)
- ❌ Geheugenhongerig in prefork-modus (4–9 MB, loopt onder belasting snel op)
- ❌ Procesmodel minder efficiënt dan het event-driven model
- ❌ Uitgebreide configuratie
- ❌ 5e bij reverse proxy (0,50–0,59× nginx)
- ❌ Geen ingebouwde WAF (ModSecurity als aparte module)
- ❌ Historisch groter aanvalsoppervlak

---

### 🟠 Caddy

**Sterke punten**
- ✅ Automatische HTTPS (ACME ingebouwd, zonder configuratie)
- ✅ Zeer korte en leesbare configuratie (Caddyfile)
- ✅ HTTP/2 en HTTP/3 native
- ✅ Eén enkel binair bestand, eenvoudige uitrol
- ✅ Redelijke reverse proxy bij middelgrote antwoorden

**Zwakke punten**
- ❌ Traag in ruwe doorvoer (5e bij web, 7e bij doorsturen)
- ❌ Hoog geheugengebruik (46–67 MB)
- ❌ Zeer zwak bij grote bestanden op machine C (0,11× nginx)
- ❌ Geen ingebouwde WAF
- ❌ Jonger ecosysteem dan nginx/Apache
- ❌ Weinig geschikt voor zeer hoge doorvoer

---

### 🟣 Traefik

**Sterke punten**
- ✅ Automatische Docker/Kubernetes-detectie
- ✅ Ideaal in containeromgevingen
- ✅ Automatische HTTPS (ACME ingebouwd)
- ✅ Dynamische configuratie zonder herstart
- ✅ Goed als reverse proxy bij middelgrote antwoorden (0,60–0,70× nginx)

**Zwakke punten**
- ❌ Geen bestandsserver (ontbreekt in de webranglijst)
- ❌ 6e bij reverse proxy (0,29–0,35× nginx bij 1 kB)
- ❌ Zeer hoog geheugengebruik (93–131 MB)
- ❌ Configuratiecomplexiteit buiten containeromgevingen
- ❌ Geen ingebouwde WAF
- ❌ Overgedimensioneerd voor een eenvoudige statische site

---

## 🎯 Welke server voor welk gebruik?

| Gebruik | Aanbevolen server | Reden |
|---|---|---|
| Site met veel verkeer | **nginx** of **lighttpd** | Maximale doorvoer, HTTP/2-3 |
| Beperkte machine / embedded | **lighttpd** | 1 MB geheugen, de snelste en de zuinigste |
| Eenvoudige automatische HTTPS | **Caddy** | Automatische certificaten, korte configuratie |
| Docker / Kubernetes | **Traefik** | Servicedetectie |
| PHP-toepassing / .htaccess | **Apache** | Historisch ecosysteem |
| Reverse proxy | **nginx** of **omega-serv (native)** | Beste prestaties |
| Websites + beveiliging + interface | **omega-serv (native)** | Complete infrastructuur: WAF, webbeheer, multi-instantie, reverse proxy, logbeheer, back-ups… |

---

Gegevens uit de omega-serv-vergelijking (november 2026) — kraynux. MIT-licentie.
[oha](https://github.com/hatoo/oha) voor de meting · zelfstandige HTML/CSS-grafieken.

> *Grafische versie van de gemeten vergelijking van omega-serv (dezelfde cijfers als in de gedetailleerde vergelijking: metingen van 3 en 4 november 2026 op drie machines; reverse proxy: 14 november 2026; geheugen van omega-serv 3.0.0: 19 november 2026). Meet voor elke capaciteitsbeslissing op uw eigen hardware.*
>
> Copyright © 2026 kraynux — kraynux@proton.me — MIT-licentie (zie bestand LICENSE).
