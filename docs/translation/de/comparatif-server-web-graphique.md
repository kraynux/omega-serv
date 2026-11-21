# omega-serv im Vergleich mit den Webservern am Markt — grafische Version

**omega-serv im Vergleich mit nginx · lighttpd · Apache · Caddy · Traefik — Messungen auf drei Maschinen (Nov. 2026).**

🌐 [Français](../../comparatif-server-web-graphique.md) · [English](../en/comparatif-server-web-graphique.md) · [Español](../es/comparatif-server-web-graphique.md) · [Português (Brasil)](../pt-BR/comparatif-server-web-graphique.md) · [Italiano](../it/comparatif-server-web-graphique.md) · **Deutsch** · [Nederlands](../nl/comparatif-server-web-graphique.md) · [Polski](../pl/comparatif-server-web-graphique.md) · [Русский](../ru/comparatif-server-web-graphique.md) · [中文](../zh-CN/comparatif-server-web-graphique.md) · [Tiếng Việt](../vi/comparatif-server-web-graphique.md) · [ไทย](../th/comparatif-server-web-graphique.md) · [Bahasa Indonesia](../id/comparatif-server-web-graphique.md) · [日本語](../ja/comparatif-server-web-graphique.md) · [한국어](../ko/comparatif-server-web-graphique.md) · [हिन्दी](../hi/comparatif-server-web-graphique.md) · [العربية](../ar/comparatif-server-web-graphique.md)

> **Lesehilfe:** Je länger der Balken, desto schneller der Server. Die Referenz ist **nginx = 1,00**.

## Farblegende

<!-- 🖼️ IMAGE : legende-couleurs -->
<div align="center">
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/translation/de/omega-serv/stats-1.png" alt="Farblegende" width="1024">
</div>

---

## 📊 1-KB-Dateien — Durchsatz (Anfragen/s)

Maschinen A (i5 2010), B (Celeron 2016) und C (Ryzen 2024). Die Balken sind auf nginx (1,00) auf derselben Maschine normiert.

<!-- 🖼️ IMAGE : 1ko-banner — 3 colonnes côte à côte (Machine A · 2 cœurs | Machine B · 4 cœurs | Machine C · 10 cœurs), largeur totale -->
<div align="center">
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/translation/de/omega-serv/stats-2.png" alt="1-KB-Dateien — Maschinen A, B und C" width="1024">
</div>

> \* Maschine C: Die native Engine nutzt 4 Kerne, nginx 2 Prozesse (2 Kerne). Bei gleicher Kernzahl fällt das Verhältnis auf ~0,70 zurück.
---

## 📦 Mittlere Dateien (100 KB) — normaler Webmodus

Hier überrascht Apache: Er übertrifft oft die native Engine von omega-serv. lighttpd bleibt der schnellste. Referenz: nginx = 1,00.

<!-- 🖼️ IMAGE : 100ko-banner.png — 3 colonnes côte à côte (A | B | C), largeur totale -->
<div align="center">
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/translation/de/omega-serv/stats-3.png" alt="100-KB-Dateien — Maschinen A, B und C" width="1024">
</div>

---

## 💿 Große Dateien (5 MB) — normaler Webmodus

Bei großen Dateien rücken die Server zusammen: Es ist der Kernel, der die Daten kopiert (sendfile). Caddy bildet auf Maschine C eine Ausnahme. Durchsatz in MB/s.

<!-- 🖼️ IMAGE : 5mo-banner.png — 3 colonnes côte à côte (A | B | C), largeur totale -->
<div align="center">
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/translation/de/omega-serv/stats-4.png" alt="5-MB-Dateien — Maschinen A, B und C" width="1024">
</div>

---

## 🔄 Reverse Proxy — kleine Antworten (1 KB)

Jeder Proxy leitet an ein nginx-Backend weiter. Referenz: nginx = 1,00. Maschine C: 4 Prozesse.

<!-- 🖼️ IMAGE : proxy-1ko-banner.png — 3 colonnes côte à côte (A | B | C), largeur totale -->
<div align="center">
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/translation/de/omega-serv/stats-5.png" alt="Proxy 1 KB — Maschinen A, B und C" width="1024">
</div>

---

## 🔄 Reverse Proxy — Antworten von 100 KB

Bei mittleren Antworten ist omega-serv nativ gleichauf mit nginx oder übertrifft es.

<!-- 🖼️ IMAGE : proxy-100ko-banner.png — 3 colonnes côte à côte (A | B | C), largeur totale -->
<div align="center">
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/translation/de/omega-serv/stats-6.png" alt="Proxy 100 KB — Maschinen A, B und C" width="1024">
</div>

---

## 💾 Speicher (PSS) — im Ruhezustand → nach Last

Je kürzer der Balken, desto sparsamer der Server. lighttpd, nginx und Apache sind die sparsamsten; omega-serv 3.0.0 (am 19. November neu gemessen) folgt, mit 10 bis 16 MB für die native Engine.

<!-- 🖼️ IMAGE : memoire-banner.png — 3 colonnes côte à côte de jauges (A | B | C), largeur totale -->
<div align="center">
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/translation/de/omega-serv/stats-7.png" alt="Speicher — Maschinen A, B und C" width="1024">
</div>

---

## 🏆 Rangliste normaler Webmodus — wer ist der Schnellste?

Zusammenfassung der drei Maschinen beim Ausliefern statischer Dateien.

<!-- 🖼️ IMAGE : classement-web.png -->
<!-- Contenu : 1. 🥇 lighttpd — meilleur en petits & moyens fichiers · 2. 🥈 nginx — référence, excellent partout · 3. 🥉 omega-serv natif — très bon, 2ᵉ en reverse proxy · 4. Apache — bon, robuste, écosystème · 5. Caddy — simple, HTTPS auto · 6. omega-serv Python — moteur de repli -->
<div align="center">
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/translation/de/omega-serv/stats-8.png" alt="Rangliste normaler Webmodus" width="1024">
</div>

---

## 🔄 Rangliste Reverse Proxy — wer ist der Beste?

nginx bleibt die Referenz; omega-serv nativ ist sein engster Verfolger, weit vor den anderen.

<!-- 🖼️ IMAGE : classement-proxy.png -->
<!-- Contenu : 1. 🥇 nginx · 2. 🥈 omega-serv natif — 0,82 à 0,91× nginx en 1 Ko · 3. 🥉 omega-serv + WAF — toujours devant lighttpd/Apache · 4. lighttpd — 0,53 à 0,61× · 5. Apache — 0,50 à 0,59× · 6. Traefik — 0,29 à 0,35× · 7. Caddy — 0,23 à 0,32× · 8. omega-serv Python — moteur de repli -->
<div align="center">
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/translation/de/omega-serv/stats-9.png" alt="Rangliste Reverse Proxy" width="1024">
</div>

---

## 🆚 Direkter Vergleich — Rangliste Web & Reverse Proxy nebeneinander

Zwei Einsatzzwecke, zwei Ranglisten. Ein Server kann in dem einen glänzen und im anderen enttäuschen: Apache überrascht beim Weiterleiten, Caddy enttäuscht überall außer bei der Einfachheit.

<!-- 🖼️ IMAGE : face-a-face.png — 2 colonnes côte à côte (web | proxy), largeur totale -->
<div align="center">
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/translation/de/omega-serv/stats-10.png" alt="Direkter Vergleich Web gegen Reverse Proxy" width="1024">
</div>

### Kreuzübersicht

| Server | Einordnung |
|---|---|
| 🟢 **omega-serv nativ** | Der Vielseitigste: 3. im Web, **2. im Reverse Proxy**. Der einzige Server mit integriertem WAF, der beim Weiterleiten vor lighttpd und Apache bleibt. Der beste Kompromiss für ein einziges Werkzeug, das beide Einsatzzwecke abdeckt, mit zusätzlicher Sicherheit. |
| 🔵 **nginx** | Der Gleichmäßigste: 2. im Web, **1. im Reverse Proxy**. Immer im oberen Teil der Rangliste, ohne nennenswerte Schwäche. Die Standardwahl ohne besondere Anforderungen. |
| 🟢 **lighttpd** | Der Sprinter für Statisches: **1. im Web**, aber nur 4. beim Weiterleiten. Die beste Wahl für rein statische Inhalte, überlässt omega-serv oder nginx das Feld, sobald ein Reverse Proxy hinzukommt. |
| 🔴 **Apache** | Das Gegenbeispiel: 4. im Web, 5. beim Weiterleiten. Bei großen Dateien überrascht er sogar nginx (Maschine C). Weder der Schnellste noch der Leichteste: Sein Trumpf bleibt das PHP-Ökosystem. |
| 🟠 **Caddy** | Einfachheit vor Geschwindigkeit: 5. im Web, **7. beim Weiterleiten**. Nicht auf Durchsatz ausgelegt: automatisches HTTPS und kurze Konfiguration. Kleinen Projekten vorbehalten. |
| 🟣 **Traefik** | Außerhalb der Web-Kategorie: kein Dateiserver, 6. beim Weiterleiten. Sein Einsatzgebiet bleiben Docker und Kubernetes, nicht die rohe Leistung. |

---

## 📋 Vollständige Übersichtstabelle — Verhältnisse zu nginx (1,00)

Überblick über **alle** Messwerte: normaler Webmodus (1 KB, 100 KB, 5 MB) und Reverse Proxy (1 KB, 100 KB), dazu der Speicher. Je näher der Wert bei 1,00 oder darüber liegt, desto besser.

| Server | Web 1 KB (A/B/C) | Web 100 KB (A/B/C) | Web 5 MB (A/B/C) | Proxy 1 KB (A/B/C) | Proxy 100 KB (A/B/C) | Speicher (A/B/C) |
|---|---|---|---|---|---|---|
| **lighttpd** | 1,52 / 1,26 / 1,53 | 1,08 / 1,07 / 1,26 | 1,05 / 0,99 / 0,81 | 0,61 / 0,56 / 0,53 | 0,74 / 0,62 / 0,96 | 1 MB |
| **nginx** | 1,00 / 1,00 / 1,00 | 1,00 / 1,00 / 1,00 | 1,00 / 1,00 / 1,00 | 1,00 / 1,00 / 1,00 | 1,00 / 1,00 / 1,00 | 4–5 MB |
| **omega-serv (nativ)** | **0,70 / 0,67 / 1,15\*** | **0,38 / 0,28 / 0,61** | **0,99 / 0,91 / 1,09** | **0,85 / 0,91 / 0,82** | **1,11 / 0,97 / 1,43** | 10–16 MB |
| **omega-serv + WAF** | 0,56 / 0,53 / 1,07\* | 0,37 / 0,27 / 0,62 | — | 0,81 / 0,89 / 0,77 | 1,10 / 0,93 / 1,30 | 28–33 MB |
| **Apache** | 0,42 / 0,35 / 0,76 | 0,55 / 0,62 / 0,97 | 1,01 / 1,00 / 1,19 | 0,59 / 0,53 / 0,50 | 0,62 / 0,65 / 0,71 | 4–9 MB |
| **Caddy** | 0,26 / 0,17 / 0,21 | 0,40 / 0,33 / 0,14 | 0,95 / 0,94 / 0,11 | 0,32 / 0,28 / 0,23 | 0,60 / 0,54 / 0,59 | 46–67 MB |
| **Traefik** | — | — | — | 0,35 / 0,35 / 0,29 | 0,64 / 0,60 / 0,70 | 93–131 MB |
| **omega-serv (Python)** | 0,11 / 0,05 / 0,08 | 0,14 / 0,10 / 0,12 | 0,92 / 0,91 / 0,75 | 0,09 / 0,08 / 0,07 | 0,21 / 0,19 / — | 20–48 MB |

> \* Maschine C: 4 Kerne für die native Engine gegenüber 2 für nginx; bei gleicher Kernzahl Verhältnis ~0,67–0,71.
> Die drei Werte pro Zelle entsprechen den Maschinen **A / B / C**. „—“: nicht gemessen oder nicht anwendbar.

---

## ⚖️ Stärken und Schwächen — alle Server

Jeder Server hat seine Vorzüge und Grenzen. Hier die vollständige Übersicht, ohne Bevorzugung.

### 🟢 omega-serv (nativ)

**Stärken**
- ✅ Vollständige Verwaltung im Terminal (TUI, 17 Sprachen)
- ✅ WAF + Active Defense + RIPOSTE integriert
- ✅ Native C++-Engine: ~0,7× nginx bei statischen Dateien
- ✅ 2. im Reverse Proxy hinter nginx
- ✅ Zwischen Prozessen geteilte Limits (exakte Sicherheit)
- ✅ Import von lighttpd-mod_magnet-Skripten
- ✅ Verwaltung mehrerer Instanzen
- ✅ Webverwaltung


**Schwächen**
- ❌ Kein HTTP/2 und kein HTTP/3
- ❌ Keine Komprimierung im laufenden Betrieb
- ❌ Keine Docker/Kubernetes-Erkennung
- ❌ ACME über Certbot (nicht nativ integriert)
- ❌ 100-KB-Dateien: 0,3–0,6× nginx
- ❌ Speicher 10–55 MB je nach Modus (gegenüber 1–5 MB bei nginx/lighttpd)
- ❌ Junges Ökosystem, von einer Person gepflegt

---

### 🔵 nginx

**Stärken**
- ✅ Referenz für Leistung und Stabilität
- ✅ HTTP/2, HTTP/3, Komprimierung
- ✅ Riesiges Ökosystem (Module, Dokumentation, Community)
- ✅ Sehr sparsam im Speicher (4–5 MB)
- ✅ Ausgezeichneter Reverse Proxy
- ✅ Offizielles ACME-Modul
- ✅ Ausgereifte und bewährte Konfiguration

**Schwächen**
- ❌ Ausführliche Konfiguration, eigene Syntax zu erlernen
- ❌ Kein integrierter WAF (erfordert ModSecurity oder Gleichwertiges)
- ❌ Keine native Administrationsoberfläche
- ❌ Neuladen der Konfiguration im Betrieb mitunter heikel
- ❌ Open-Source-Version eingeschränkt (einige Funktionen nur im kostenpflichtigen Nginx Plus)
- ❌ Keine native Docker/Kubernetes-Erkennung (über Templates)

---

### 🟢 lighttpd

**Stärken**
- ✅ Der Schnellste bei kleinen/mittleren Dateien
- ✅ Der sparsamste im Speicher (1 MB)
- ✅ Leicht, geeignet für eingeschränkte Systeme
- ✅ Guter Reverse Proxy
- ✅ Einfache und lesbare Konfiguration

**Schwächen**
- ❌ Kein HTTP/3 (HTTP/2 je nach Build nur teilweise)
- ❌ Nur 4. im Reverse Proxy (0,53–0,61× nginx)
- ❌ Kleineres Ökosystem als nginx/Apache
- ❌ Kein integrierter WAF
- ❌ Keine Docker/Kubernetes-Erkennung
- ❌ Weniger aktive Entwicklung als früher
- ❌ Schwach bei großen Dateien (0,81× nginx auf Maschine C)

---

### 🔴 Apache

**Stärken**
- ✅ Riesiges historisches Ökosystem (Module, `.htaccess`, PHP)
- ✅ Robust und seit Jahrzehnten bewährt
- ✅ Ausgezeichnet bei großen Dateien (übertrifft nginx auf Maschine C)
- ✅ Unterstützung für `.htaccess` ohne Neustart
- ✅ Komprimierung, HTTP/2, ACME verfügbar
- ✅ Umfangreiche Dokumentation

**Schwächen**
- ❌ Langsam bei kleinen Dateien (0,35–0,42× nginx)
- ❌ Speicherhungrig im Prefork-Modus (4–9 MB, steigt unter Last schnell)
- ❌ Prozessmodell weniger effizient als das ereignisgesteuerte
- ❌ Ausführliche Konfiguration
- ❌ 5. im Reverse Proxy (0,50–0,59× nginx)
- ❌ Kein integrierter WAF (ModSecurity als separates Modul)
- ❌ Historisch größere Angriffsfläche

---

### 🟠 Caddy

**Stärken**
- ✅ Automatisches HTTPS (ACME integriert, ohne Konfiguration)
- ✅ Sehr kurze und lesbare Konfiguration (Caddyfile)
- ✅ HTTP/2 und HTTP/3 nativ
- ✅ Einzelne Binärdatei, einfache Bereitstellung
- ✅ Brauchbarer Reverse Proxy bei mittleren Antworten

**Schwächen**
- ❌ Langsam im reinen Durchsatz (5. im Web, 7. beim Weiterleiten)
- ❌ Hoher Speicherverbrauch (46–67 MB)
- ❌ Sehr schwach bei großen Dateien auf Maschine C (0,11× nginx)
- ❌ Kein integrierter WAF
- ❌ Jüngeres Ökosystem als nginx/Apache
- ❌ Wenig geeignet für sehr hohe Durchsätze

---

### 🟣 Traefik

**Stärken**
- ✅ Automatische Docker/Kubernetes-Erkennung
- ✅ Ideal in Container-Umgebungen
- ✅ Automatisches HTTPS (ACME integriert)
- ✅ Dynamische Konfiguration ohne Neustart
- ✅ Guter Reverse Proxy bei mittleren Antworten (0,60–0,70× nginx)

**Schwächen**
- ❌ Kein Dateiserver (fehlt in der Web-Rangliste)
- ❌ 6. im Reverse Proxy (0,29–0,35× nginx bei 1 KB)
- ❌ Sehr hoher Speicherverbrauch (93–131 MB)
- ❌ Konfigurationskomplexität außerhalb von Container-Umgebungen
- ❌ Kein integrierter WAF
- ❌ Überdimensioniert für eine einfache statische Website

---

## 🎯 Welcher Server für welchen Einsatz?

| Einsatz | Empfohlener Server | Grund |
|---|---|---|
| Website mit hohem Verkehr | **nginx** oder **lighttpd** | Maximaler Durchsatz, HTTP/2-3 |
| Eingeschränkte Maschine / Embedded | **lighttpd** | 1 MB Speicher, der schnellste und genügsamste |
| Einfaches automatisches HTTPS | **Caddy** | Automatische Zertifikate, kurze Konfiguration |
| Docker / Kubernetes | **Traefik** | Diensterkennung |
| PHP-Anwendung / .htaccess | **Apache** | Historisches Ökosystem |
| Reverse Proxy | **nginx** oder **omega-serv (nativ)** | Beste Leistung |
| Websites + Sicherheit + Oberfläche | **omega-serv (nativ)** | Komplette Infrastruktur: WAF, Webverwaltung, Mehrinstanzbetrieb, Reverse Proxy, Log-Manager, Sicherung… |

---

Daten aus dem omega-serv-Vergleich (November 2026) — kraynux. MIT-Lizenz.
[oha](https://github.com/hatoo/oha) für die Messung · eigenständige HTML/CSS-Diagramme.

> *Grafische Version des gemessenen Vergleichs von omega-serv (dieselben Zahlen wie im ausführlichen Vergleich: Messungen vom 3. und 4. November 2026 auf drei Maschinen; Reverse Proxy: 14. November 2026; Speicher von omega-serv 3.0.0: 19. November 2026). Für jede Kapazitätsentscheidung messen Sie auf Ihrer eigenen Hardware.*
>
> Copyright © 2026 kraynux — kraynux@proton.me — MIT-Lizenz (siehe Datei LICENSE).
