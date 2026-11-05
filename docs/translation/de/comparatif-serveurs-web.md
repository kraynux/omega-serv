<!-- Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE) -->

# omega-serv im Vergleich mit den Webservern am Markt

**Gemessener Vergleich: nginx · lighttpd · Apache · Caddy · Traefik · omega-serv 2.5**

🌐 [Français](../../comparatif-serveurs-web.md) · [English](../en/comparatif-serveurs-web.md) · [Español](../es/comparatif-serveurs-web.md) · [Português (Brasil)](../pt-BR/comparatif-serveurs-web.md) · [Italiano](../it/comparatif-serveurs-web.md) · **Deutsch** · [Nederlands](../nl/comparatif-serveurs-web.md) · [Polski](../pl/comparatif-serveurs-web.md) · [Русский](../ru/comparatif-serveurs-web.md) · [中文](../zh-CN/comparatif-serveurs-web.md) · [Tiếng Việt](../vi/comparatif-serveurs-web.md) · [ไทย](../th/comparatif-serveurs-web.md) · [Bahasa Indonesia](../id/comparatif-serveurs-web.md) · [日本語](../ja/comparatif-serveurs-web.md) · [한국어](../ko/comparatif-serveurs-web.md) · [हिन्दी](../hi/comparatif-serveurs-web.md) · [العربية](../ar/comparatif-serveurs-web.md)

Dieses Dokument ordnet omega-serv unter den verbreitetsten Webservern ein. Es versucht nicht, einen „besten Server“ zu küren: Jedes Werkzeug erfüllt andere Bedürfnisse, und jedes hat seine Stärken. Es liefert drei Dinge:

1. **echte Messungen** auf **drei** sehr unterschiedlichen **Maschinen**, mit demselben Client, denselben Dateien und demselben Protokoll, reproduzierbar;
2. einen **Funktionsvergleich**, jede Funktion in der offiziellen Dokumentation des jeweiligen Servers geprüft (Links am Ende des Dokuments), wobei zwischen Eingebautem und dem unterschieden wird, was ein Modul oder ein Plugin erfordert;
3. was omega-serv **wirklich zusätzlich bietet** und was die anderen **besser machen als er**.

Alle Leistungsmessungen wurden am 3. und 4. November 2026 durchgeführt. Keine Zahl ist von einer anderen Website übernommen oder geschätzt. Die Rohdaten werden mit diesem Dokument veröffentlicht.

---

## Inhalt

1. [Kurz gesagt](#1-kurz-gesagt)
2. [Wie man diesen Vergleich liest](#2-wie-man-diesen-vergleich-liest)
3. [Messmethode](#3-messmethode)
4. [Leistung: omega-serv im Vergleich mit nginx, lighttpd, Apache und Caddy](#4-leistung-omega-serv-im-vergleich-mit-nginx-lighttpd-apache-und-caddy)
5. [Die Versionen von omega-serv: 1.0 → 2.0 → 2.5](#5-die-versionen-von-omega-serv-10--20--25)
6. [Funktionsvergleich](#6-funktionsvergleich)
7. [Verwaltung und Bedienung](#7-verwaltung-und-bedienung)
8. [Was omega-serv zusätzlich bietet](#8-was-omega-serv-zusätzlich-bietet)
9. [Was die anderen besser machen](#9-was-die-anderen-besser-machen)
10. [Welcher Server für welchen Einsatz](#10-welcher-server-für-welchen-einsatz)
11. [Die Messungen reproduzieren](#11-die-messungen-reproduzieren)
12. [Quellen](#12-quellen)

---

## 1. Kurz gesagt

- **omega-serv hat zwei Engines.** Die **Python-Engine** verarbeitet alles selbst. Die **native Engine**, in C++ geschrieben und mit 2.5 eingeführt, liefert die Anfragen selbst aus; Python behält die Konfiguration und die Sicherheitsentscheidungen, wobei die native Engine die Anfragen, auf die keine WAF-Regel zutrifft, allein erkennt.
- **Mit der nativen Engine, ohne WAF**, liefert omega-serv kleine Dateien mit **etwa 0,7-facher Geschwindigkeit von nginx** aus, auf allen drei Maschinen. Er liegt damit **vor Apache und Caddy, hinter nginx und lighttpd**.
- **Mit der Python-Engine** bleibt omega-serv weit hinter allen anderen: **3 bis 11 % der Geschwindigkeit von nginx**.
- **Mit aktivem WAF** prüft omega-serv jede Anfrage, was die anderen gemessenen Server nicht tun. Mit der nativen Engine liefert er dann **das 0,53- bis 0,56-Fache** der Geschwindigkeit von nginx (ohne WAF) auf den Maschinen A und B und das 1,07-Fache auf Maschine C (4 Kerne gegenüber 2): Der WAF nimmt ihm nur 5 bis 22 % seines Durchsatzes. Er bleibt vor Apache und Caddy, die ohne WAF gemessen wurden.
- **Mittlere Dateien (100 KB)**: Das ist die derzeitige Schwachstelle der nativen Engine, mit **dem 0,3- bis 0,6-Fachen** von nginx, hinter Apache.
- **Große Dateien (5 MB)**: nginx, lighttpd, Apache und omega-serv nativ erreichen dieselbe Größenordnung beim Durchsatz. Caddy ist auf der schnellsten Maschine deutlich langsamer.
- **Speicher**: lighttpd (1 MB), nginx (4 bis 5 MB) und Apache (4 bis 9 MB) sind sehr sparsam. omega-serv belegt je nach Modus **30 bis 65 MB**, Caddy **50 bis 67 MB**.
- **Was omega-serv zusätzlich hat**: eine vollständige Verwaltung in einer Terminaloberfläche, in 17 Sprachen; ein eingebauter WAF und eine aktive Abwehr; exakte Sicherheitsgrenzen bei mehreren Prozessen; den Import von lighttpd-mod_magnet-Skripten; die Verwaltung mehrerer Instanzen.
- **Was er nicht hat**: HTTP/2 und HTTP/3, Komprimierung im laufenden Betrieb, Dienst-Erkennung für Docker/Kubernetes, einen eingebauten ACME-Client (er nutzt Certbot), ein Modul-Ökosystem.

---

## 2. Wie man diesen Vergleich liest

Einige Begriffe kehren im ganzen Dokument wieder.

- **Anfragen pro Sekunde (req/s)**: die Zahl der Dateien, die ein Server in einer Sekunde sendet. Je höher, desto besser.
- **Abstand zu nginx**: Die absoluten Werte hängen stark von der Maschine ab. Auf unseren drei Maschinen reicht nginx von 22.000 bis 440.000 req/s. Stabil bleibt **das Verhältnis zwischen den Servern**. Die Tabellen geben daher neben jedem Wert sein Verhältnis zu nginx aus derselben Messsitzung an: **1,00 = so schnell wie nginx**, 0,50 = halb so schnell, 1,50 = anderthalbmal so schnell.
- **p99-Latenz**: die Antwortzeit, die 99 % der Anfragen nicht überschreiten. Sie zeigt die „schlechten Momente“, die ein Mittelwert verbirgt.
- **PSS (*Proportional Set Size*)**: der Speicher, den alle Prozesse des Servers tatsächlich belegen. Eine von mehreren Prozessen gemeinsam genutzte Seite wird nur einmal gezählt.
- **Prozesse und Kerne**: Ein Server kann mehrere Prozessorkerne nutzen. Jeder tut es auf seine Weise. nginx, lighttpd, Apache und omega-serv im Python-Modus starten mehrere Prozesse. Caddy verteilt seine Arbeit in Go auf die Kerne. Die native Engine von omega-serv startet einen Thread pro verfügbarem Kern. Um fair zu vergleichen, geben wir jedem Server **dieselben Kerne**.
- **WAF (*Web Application Firewall*)**: ein Filter, der jede Anfrage prüft, um Angriffe zu blockieren (Injektionen, Scanner…). omega-serv bringt ihn mit. Die anderen Server können einen als Modul erhalten (ModSecurity, Coraza), aber **sie wurden ohne gemessen**, in ihrer Grundkonfiguration.

**Der richtige Reflex**: die Verhältnisse vergleichen, nicht die absoluten Werte, und immer prüfen, ob der WAF aktiv ist.

---

## 3. Messmethode

### Die drei Maschinen

| | Maschine A | Maschine B | Maschine C |
|---|---|---|---|
| Prozessor | Intel Core i5 M480, 2,67 GHz (2010) | Intel Celeron J3455, 1,5 GHz (2016) | AMD Ryzen AI 9 365 (2024) |
| Kerne | 2 physische Kerne, 4 Threads | 4 Kerne, ohne Hyperthreading | 10 Kerne (4 Zen 5 + 6 Zen 5c), 20 Threads |
| Arbeitsspeicher | 8 GB | 8 GB | 32 GB |
| System | Mabox Linux (Basis Manjaro), Kernel 6.18 | EndeavourOS, Kernel 7.2 | Arch Linux, Kernel 7.2 (CachyOS) |
| Kerne des Servers | 1 physischer Kern (Threads 0 und 2) | 2 Kerne (0 und 1) | 4 Zen-5-Kerne, je ein Thread (0 bis 3) |
| Kerne des Clients | 1 physischer Kern (Threads 1 und 3) | 2 Kerne (2 und 3) | 6 Zen-5c-Kerne (4 bis 9) |

Maschine A ist ein alter Laptop, Maschine B ein stromsparender Mini-PC, Maschine C ein aktueller Laptop am Netz im Energieprofil „ausgeglichen“. Sie decken die Spanne von einem kleinen Heimserver bis zu einer aktuellen Maschine ab.

### Software

| Software | Version |
|---|---|
| nginx | 1.30.4 (A), 1.30.5 (B, C) |
| lighttpd | 1.4.85 |
| Apache HTTP Server | 2.4.69, MPM `event` |
| Caddy | 2.11.4 (A, B), 2.11.7 (C) |
| omega-serv | 1.0.0 und 2.0.0 (veröffentlichte Archive) und 2.5, unter Python 3.14 |
| Last-Client | [oha](https://github.com/hatoo/oha) 1.16.0 (in Rust geschrieben) |

Traefik wurde nicht gemessen: Es ist kein Dateiserver (siehe §6). Es erscheint nur im Funktionsvergleich.

### Protokoll

- **Prozessor-Isolation**: Server und Client sind auf getrennte Kerne festgelegt (Tabelle oben). Der Client stiehlt dem Server also keine Zeit, und alle Server haben genau dieselben Ressourcen.
- **Dieselben Dateien für alle**: `small.html` (1 KB), `medium.png` (100 KB) und `large.bin` (5 MB), aus demselben Ordner ausgeliefert.
- **Zugriffsprotokoll überall aktiv**, denn ein Server in Produktion protokolliert.
- **HTTP/1.1 unverschlüsselt, persistente Verbindungen (keep-alive)**. Die Parallelität beträgt 32 Verbindungen für die Dateien von 1 KB und 100 KB und 8 für die 5-MB-Datei.
- **Dauer**: 10 Sekunden pro Datei und Konfiguration.
- **Wiederholungen**: 3 vollständige, verschränkte Runden (alle Konfigurationen in Runde 1, dann alle in Runde 2 usw.). Die Tabellen geben den **Median** der drei Runden an. Von Runde zu Runde bleibt die Abweichung meist unter 5 %.
- **Speicher**: PSS aller Prozesse des Servers, im Leerlauf und nach der Last erfasst.
- **Konfigurationen**:
  - nginx, lighttpd, Apache und Caddy in ihrer Grundkonfiguration: statische Dateien und Zugriffsprotokoll;
  - omega-serv mit dem Profil `standard`, der WAF deaktiviert und dann aktiviert mit allen mitgelieferten Regeln (ohne Ratenbegrenzung).
- **Anzahl der Prozesse**: Jeder Server wird mit 1 und dann 2 Prozessen gemessen: nginx `worker_processes`, lighttpd `server.max-worker`, Apache `StartServers`/`ServerLimit`, Caddy `GOMAXPROCS`, omega-serv `server.workers`. Bei der nativen Engine von omega-serv zählt `server.workers` die Python-Sicherheitsprozesse; die native Engine selbst nutzt immer alle Kerne, die ihr gegeben werden.
- **Kein Fehler**: Alle Antworten aller Messungen sind 200.

### Bekannte Grenzen

- **Wir vergleichen die Verhältnisse.** Die absoluten Werte wären auf Ihrer Hardware oder auf einem dedizierten Server anders.
- **Loopback (127.0.0.1)**: Die Messung läuft nicht über ein echtes Netzwerk. In einem echten Netzwerk ist der Durchsatz großer Dateien fast immer durch die Bandbreite begrenzt, nicht durch den Server. Die Durchsätze von mehreren zehn GB/s auf Maschine C sind nur über Loopback möglich.
- **Kein TLS** in diesen Messungen.
- **Maschine A**: Der produktive omega-serv-Dienst dieser Maschine lief im Hintergrund, ohne Verkehr zu erhalten.
- **Maschine C**: Hybridprozessor (Zen-5- und Zen-5c-Kerne). Der Server erhielt die 4 schnellen Kerne, der Client die 6 anderen.
- **Grundkonfigurationen**: Kein Server wurde optimiert. Ein erfahrener Administrator würde aus jedem zweifellos mehr herausholen, omega-serv eingeschlossen.
- **Rohdaten**: [`docs/benchmarks/`](../../benchmarks/) (eine Datei pro Maschine).

---

## 4. Leistung: omega-serv im Vergleich mit nginx, lighttpd, Apache und Caddy

In allen Tabellen ist der Referenzwert **nginx mit 2 Prozessen** (= 1,00), gemessen in derselben Sitzung auf derselben Maschine. Auf den Maschinen A und B ist das die Konfiguration, die alle dem Server gegebenen Kerne belegt.

### Kleine Dateien (1 KB): Anfragen pro Sekunde

| Server | Maschine A | Maschine B | Maschine C |
|---|---:|---:|---:|
| lighttpd, 2 Prozesse | 33.138 (**1,52**) | 31.125 (**1,26**) | 378.590 (**1,53**) |
| nginx, 2 Prozesse | 21.801 (1,00) | 24.705 (1,00) | 248.184 (1,00) |
| **omega-serv, native Engine** | **15.222 (0,70)** | **16.542 (0,67)** | **285.213 (1,15 \*)** |
| omega-serv, nativ + WAF † | 11.990 (0,56) | 12.998 (0,53) | 264.484 (1,07 \*) |
| omega-serv, nativ + WAF, 2 Sicherheitsprozesse † | 11.746 (0,55) | 12.718 (0,52) | 253.527 (1,02 \*) |
| Apache, 2 Prozesse | 9.192 (0,42) | 8.634 (0,35) | 188.335 (0,76) |
| Caddy, 2 Prozesse | 5.749 (0,26) | 4.116 (0,17) | 52.897 (0,21) |
| omega-serv, Python-Engine, 2 Prozesse | 2.354 (0,11) | 1.312 (0,05) | 19.911 (0,08) |
| omega-serv, Python + WAF, 2 Prozesse | 1.901 (0,09) | 1.104 (0,04) | 15.783 (0,06) |
| omega-serv, Python-Engine | 1.507 (0,07) | 663 (0,03) | 10.553 (0,04) |
| omega-serv, Python + WAF | 1.561 (0,07) | 564 (0,02) | 8.365 (0,03) |

\* Auf Maschine C nutzt die native Engine ihre 4 Kerne, während nginx mit 2 Prozessen nur 2 nutzt. Der Vergleich bei gleicher Kernzahl folgt weiter unten: Dort liegt das Verhältnis wieder bei **0,67 bis 0,71**, wie auf den anderen Maschinen.

† Gemessen am 4. November nach der Optimierung des WAF, in einer separaten Messkampagne mit demselben Protokoll. Das Verhältnis ist mit nginx (2 Prozesse) dieser Kampagne berechnet: 21 439, 24.424 und 248.127 req/s bei kleinen Dateien, 11 545, 11.004 und 157.491 bei Dateien von 100 KB. Vor dieser Optimierung lieferte die native Engine mit WAF 3 495, 2.622 und 39.000 req/s (das 0,11- bis 0,16-Fache von nginx), weil jede Anfrage über Python lief. Rohdaten: Dateien `*-waf-natif-brut.txt`.

Mit nur 1 Prozess erreicht nginx 0,52 bis 0,73, lighttpd 0,81 bis 1,43, Apache 0,33 bis 0,74 und Caddy 0,09 bis 0,17 (Rohdaten).

### p99-Latenz bei kleinen Dateien

| Server | Maschine A | Maschine B | Maschine C |
|---|---:|---:|---:|
| lighttpd, 2 Prozesse | 4,4 ms | 4,1 ms | 0,2 ms |
| nginx, 2 Prozesse | 4,9 ms | 5,2 ms | 0,2 ms |
| **omega-serv, native Engine** | **6,1 ms** | **6,2 ms** | **0,3 ms** |
| omega-serv, nativ + WAF † | 7,2 ms | 6,7 ms | 0,3 ms |
| Apache, 2 Prozesse | 18,8 ms | 20,6 ms | 0,8 ms |
| Caddy, 2 Prozesse | 24,1 ms | 30,5 ms | 2,8 ms |
| omega-serv, Python-Engine, 2 Prozesse | 22,6 ms | 28,1 ms | 3,3 ms |
| omega-serv, Python-Engine | 32,0 ms | 51,6 ms | 4,4 ms |

### Mittlere Dateien (100 KB): Anfragen pro Sekunde

| Server | Maschine A | Maschine B | Maschine C |
|---|---:|---:|---:|
| lighttpd, 2 Prozesse | 13.561 (**1,08**) | 12.126 (**1,07**) | 197.905 (**1,26**) |
| nginx, 2 Prozesse | 12.513 (1,00) | 11.303 (1,00) | 157.224 (1,00) |
| Apache, 2 Prozesse | 6.939 (0,55) | 7.035 (0,62) | 153.265 (0,97) |
| Caddy, 2 Prozesse | 5.059 (0,40) | 3.744 (0,33) | 22.094 (0,14) |
| **omega-serv, native Engine** | **4.738 (0,38)** | **3.115 (0,28)** | **96.277 (0,61)** |
| omega-serv, nativ + WAF † | 4.229 (0,37) | 2.926 (0,27) | 98.185 (0,62) |
| omega-serv, Python-Engine, 2 Prozesse | 1.741 (0,14) | 1.154 (0,10) | 18.806 (0,12) |
| omega-serv, Python-Engine | 1.329 (0,11) | 611 (0,05) | 9.805 (0,06) |

### Große Datei (5 MB): Durchsatz

| Server | Maschine A | Maschine B | Maschine C |
|---|---:|---:|---:|
| lighttpd, 2 Prozesse | 2.440 MB/s (1,05) | 2.110 MB/s (0,99) | 28.011 MB/s (0,81) |
| nginx, 2 Prozesse | 2.322 MB/s (1,00) | 2.124 MB/s (1,00) | 34.651 MB/s (1,00) |
| Apache, 2 Prozesse | 2.355 MB/s (1,01) | 2.134 MB/s (1,00) | 41.153 MB/s (**1,19**) |
| **omega-serv, native Engine** | **2.294 MB/s (0,99)** | **1.936 MB/s (0,91)** | **37.918 MB/s (1,09)** |
| Caddy, 2 Prozesse | 2.205 MB/s (0,95) | 1.996 MB/s (0,94) | 3.811 MB/s (0,11) |
| omega-serv, Python-Engine, 2 Prozesse | 2.145 MB/s (0,92) | 1.931 MB/s (0,91) | 25.829 MB/s (0,75) |
| omega-serv, Python-Engine | 1.686 MB/s (0,73) | 1.472 MB/s (0,69) | 14.227 MB/s (0,41) |

### Speicher (PSS, alle Prozesse des Servers): im Leerlauf → nach der Last

| Server | Maschine A | Maschine B | Maschine C |
|---|---:|---:|---:|
| lighttpd | 1 → 1 MB | 1 → 1 MB | 1 → 1 MB |
| nginx | 4 → 5 MB | 5 → 5 MB | 4 → 4 MB |
| Apache | 4 → 7 MB | 4 → 7 MB | 4 → 7 MB |
| omega-serv, Python-Engine | 28 → 32 MB | 29 → 33 MB | 30 → 34 MB |
| **omega-serv, native Engine** | **33 → 34 MB** | **34 → 35 MB** | **35 → 39 MB** |
| omega-serv, nativ + WAF † | 45 → 47 MB | 43 → 44 MB | 44 → 48 MB |
| omega-serv, Python-Engine, 2 Prozesse | 40 → 50 MB | 43 → 51 MB | 42 → 51 MB |
| omega-serv, nativ + WAF, 2 Sicherheitsprozesse † | 45 → 47 MB | 43 → 44 MB | 55 → 57 MB |
| Caddy, 2 Prozesse | 50 → 57 MB | 46 → 54 MB | 48 → 62 MB |

### Bei gleicher Kernzahl: Maschine C mit 4 Prozessen

Separate Messkampagne vom 3. November, gleiches Protokoll, auf Maschine C: Jeder Server erhält 4 Prozesse (bzw. 4 Kerne für Caddy und die native Engine). Referenz: nginx mit 4 Prozessen. Die native Engine mit WAF erscheint hier nicht mehr: Sie wurde vor der Optimierung des WAF gemessen und noch nicht mit 4 Prozessen neu gemessen.

| Server | 1 KB | 100 KB | 5 MB | Speicher |
|---|---:|---:|---:|---:|
| lighttpd, 4 Prozesse | 638.907 (**1,46**) | 312.402 (**1,21**) | 41.982 MB/s (0,93) | 1 → 2 MB |
| nginx, 4 Prozesse | 438.496 (1,00) | 258.242 (1,00) | 45.162 MB/s (1,00) | 5 → 5 MB |
| **omega-serv, native Engine** | **294.083 bis 310.972 (0,67 bis 0,71)** | **108.991 bis 109.955 (0,42)** | **40.137 bis 40.463 MB/s (0,89 bis 0,90)** | **35 → 38 MB** |
| Apache, 4 Prozesse | 200.592 (0,46) | 162.607 (0,63) | 39.664 MB/s (0,88) | 6 → 9 MB |
| Caddy, 4 Kerne | 97.085 (0,22) | 35.900 (0,14) | 5.998 MB/s (0,13) | 52 → 67 MB |
| omega-serv, Python-Engine, 4 Prozesse | 37.697 (0,09) | 35.064 (0,14) | 37.123 MB/s (0,82) | 48 → 66 MB |

### Auswertung

- **Die native Engine verändert die Position von omega-serv.**
  - Bei kleinen Dateien steigt er vom 0,03- bis 0,11-Fachen von nginx (Python-Engine) auf etwa **das 0,7-Fache von nginx**, unabhängig von der Maschine.
  - Er liegt vor Apache und Caddy und hinter nginx und lighttpd, die die schnellsten bleiben.
  - Seine p99-Latenz liegt nahe an der von nginx.
- **lighttpd ist bei kleinen und mittleren Dateien der schnellste**, auf allen drei Maschinen, und der sparsamste beim Speicher. Seine Dokumentation rät dennoch von `server.max-worker` (mehrere Prozesse) ab, das wir für den Vergleich bei gleicher Prozesszahl verwendet haben.
- **Mittlere Dateien sind die derzeitige Schwachstelle der nativen Engine**: das 0,28- bis 0,61-Fache von nginx, hinter Apache, und mit mehr Kernen nicht besser. Das ist ein erkannter Ansatzpunkt für Verbesserungen.
- **Bei großen Dateien** gleichen sich die Server an, weil der Kernel die Daten kopiert (`sendfile`). Caddy ist auf Maschine C die Ausnahme: Wir haben nicht versucht, seine Grundkonfiguration zu optimieren.
- **Der WAF kostet die native Engine wenig, und man muss das richtig lesen.**
  - Die native Engine durchsucht die WAF-Regeln selbst: Eine Anfrage, auf die keine zutrifft, wird ohne Python ausgeliefert. Beim geringsten Zweifel (Übereinstimmung, Nicht-ASCII-Text, von Active Defense beobachtete Quelle, Authentifizierungszone…) entscheidet Python. Mit dem WAF behält die native Engine so 78 bis 95 % ihres Durchsatzes bei kleinen Dateien und 93 bis 99 % bei Dateien von 100 KB. Vor dieser Optimierung wurde ihr Durchsatz durch 4 bis 7 geteilt.
  - Die Ratenbegrenzung zählt die native Engine: Ihre Aktivierung ändert diese Zahlen nicht (Maschine A: 11.391 req/s mit, 11.330 ohne). Ist magnet aktiv, laufen weiterhin alle Anfragen über Python, und die Kosten sind wieder wie vorher.
  - omega-serv mit WAF bleibt vor Apache und Caddy **ohne** WAF.
  - nginx, lighttpd, Apache und Caddy wurden **ohne** WAF gemessen. Ein diesen Servern hinzugefügter WAF (ModSecurity, Coraza) hat ebenfalls Kosten, die wir nicht gemessen haben. Der Vergleich „mit WAF“ ist daher nicht fair, und wir behaupten nicht, dass omega-serv schneller wäre als ein anderer Server mit WAF.
- **Mehrere Sicherheitsprozesse helfen dem gewöhnlichen Verkehr nicht mehr**: Er läuft nicht mehr über sie, und der Durchsatz bleibt mit 2 Prozessen gleich (−2 bis −4 %, im Messrauschen). Sie helfen nur, wenn viele Anfragen über Python laufen (magnet aktiv, Angriff): Vor der Optimierung gemessen, als alle Anfragen dort durchliefen, vervielfachten 2 Sicherheitsprozesse den Durchsatz mit WAF auf 4 Kernen um das 1,5- bis 1,7-Fache, brachten auf 2 Kernen aber nur 5 bis 12 %.
- **Die Python-Engine skaliert mit den Prozessen** (×1,6 bis ×2 mit 2 Prozessen, etwa ×3,5 mit 4), bleibt aber bei 5 bis 11 % von nginx.
- **Speicher**: omega-serv belegt mehrere zehn MB mehr als nginx, lighttpd oder Apache, vor allem wegen Python, und so viel wie Caddy. Mit der nativen Engine ohne WAF bleibt der Speicher während der Last fast stabil.
- **Zur Einordnung dieser Zahlen**: Selbst der langsamste Fall, die Python-Engine mit WAF auf Maschine B (564 req/s), entspricht fast 50 Millionen Anfragen pro Tag. Das liegt weit über dem Bedarf einer privaten Website, eines internen Dienstes oder eines Labors. Die Geschwindigkeit ist nur für eine Website mit hohem Verkehr wirklich entscheidend.

---

## 5. Die Versionen von omega-serv: 1.0 → 2.0 → 2.5

Die drei Versionen wurden in derselben Sitzung wie §4 gemessen, auf allen drei Maschinen, mit demselben Protokoll. In Klammern: das Verhältnis zu nginx (2 Prozesse) derselben Sitzung. †: Messkampagne vom 4. November nach der Optimierung des WAF (siehe §4).

### Kleine Dateien (1 KB): Anfragen pro Sekunde

| Version und Modus | Maschine A | Maschine B | Maschine C |
|---|---:|---:|---:|
| 1.0.0 | 1.547 (0,07) | 645 (0,03) | 8.870 (0,04) |
| 1.0.0 + WAF | 1.453 (0,07) | 561 (0,02) | 7.687 (0,03) |
| 2.0.0 | 1.740 (0,08) | 650 (0,03) | 10.245 (0,04) |
| 2.0.0 + WAF | 1.456 (0,07) | 565 (0,02) | 8.371 (0,03) |
| 2.0.0, 2 Prozesse | 2.153 (0,10) | 1.277 (0,05) | 19.192 (0,08) |
| 2.0.0 + WAF, 2 Prozesse | 1.775 (0,08) | 1.113 (0,05) | 15.351 (0,06) |
| 2.5, Python-Engine | 1.507 (0,07) | 663 (0,03) | 10.553 (0,04) |
| 2.5, Python-Engine + WAF | 1.561 (0,07) | 564 (0,02) | 8.365 (0,03) |
| 2.5, Python-Engine, 2 Prozesse | 2.354 (0,11) | 1.312 (0,05) | 19.911 (0,08) |
| 2.5, Python-Engine + WAF, 2 Prozesse | 1.901 (0,09) | 1.104 (0,04) | 15.783 (0,06) |
| **2.5, native Engine** | **15.222 (0,70)** | **16.542 (0,67)** | **285.213 (1,15)** |
| **2.5, native Engine + WAF †** | **11.990 (0,56)** | **12.998 (0,53)** | **264.484 (1,07)** |
| **2.5, native Engine + WAF, 2 Sicherheitsprozesse †** | **11.746 (0,55)** | **12.718 (0,52)** | **253.527 (1,02)** |

### Mittlere Dateien, große Datei und Speicher (1 Prozess, ohne WAF)

| Version | 100 KB, req/s (A / B / C) | 5 MB, MB/s (A / B / C) | Speicher im Leerlauf → nach der Last (A / B / C) |
|---|---|---|---|
| 1.0.0 | 1.071 / 563 / 7.625 | 578 / 549 / 3.640 | 21 → **98** / 22 → **98** / 23 → **73** MB |
| 2.0.0 | 1.570 / 603 / 9.469 | 1.665 / 1.470 / 14.058 | 26 → 30 / 27 → 31 / 28 → 32 MB |
| 2.5, Python-Engine | 1.329 / 611 / 9.805 | 1.686 / 1.472 / 14.227 | 28 → 32 / 29 → 33 / 30 → 34 MB |
| **2.5, native Engine** | **4.738 / 3.115 / 96.277** | **2.294 / 1.936 / 37.918** | **33 → 34 / 34 → 35 / 35 → 39 MB** |

### Große gleichzeitige Downloads

Test: 3 gleichzeitige Downloads einer 300-MB-Datei, während eine kleine Seite fortlaufend abgerufen wird. Zwei Durchläufe pro Version und Maschine, mit fast identischen Ergebnissen. Der Speicher ist hier der **RSS** aller Prozesse des Servers, wie im ursprünglichen Test: Er zählt gemeinsam genutzten Speicher mehrfach, was höhere Werte ergibt als der PSS der anderen Tabellen.

| Version | Spitzenspeicher | Kleine Seite, schlechtester Fall: A / B / C |
|---|---:|---|
| 1.0.0 | **1.833 bis 1.836 MB** | **1,4 bis 1,9 s** / **1,4 bis 1,7 s** / 0,16 s |
| 2.0.0 | 39 bis 42 MB | 3 ms / 4 bis 6 ms / 1 ms |
| 2.5, Python-Engine | 41 bis 44 MB | 2 ms / 4 ms / 1 ms |
| 2.5, native Engine | 49 bis 55 MB | 1 bis 2 ms / 2 bis 4 ms / unter 1 ms |

### Kosten der aktiven Abwehr (1.0 → 2.0)

Messung vom 26. Oktober 2026 auf Maschine A, seither nicht wiederholt: Kosten einer Bedrohungsbeobachtung durch Active Defense, für jede verdächtige Anfrage, auf Datenträger (ext4) über 2.000 Beobachtungen gemessen.

| Messung | 1.0.0 | 2.0.0 |
|---|---:|---:|
| Median | 2,84 ms | 0,23 ms |
| p99 | 11,6 ms | 2,3 ms |
| Maximum | 18 bis 20 ms | 37 bis 46 ms |

Der Median wird durch 12 geteilt. Das Maximum ist in 2.0 dagegen höher: einige vereinzelte Spitzen, verbunden mit dem periodischen Schreiben des SQLite-Journals auf den Datenträger.

### Auswertung

- **Von 1.0 zu 2.0** betrifft der Fortschritt den Speicher und die großen Dateien, nicht die Geschwindigkeit kleiner Seiten:
  - der Speicher nach der Last sinkt von 73-98 MB auf 30-32 MB;
  - bei großen Downloads sinkt er von mehr als 1,8 GB auf etwa 40 MB, und der Server bleibt reaktionsschnell (einige Millisekunden statt fast 2 Sekunden);
  - der Durchsatz großer Dateien wird um das 2,7- bis 3,9-Fache gesteigert;
  - 2.0 bringt mehrere Prozesse, die den Durchsatz kleiner Seiten je nach Maschine um 25 % bis fast 100 % erhöhen.
  1.0 lud jede Datei vollständig in den Speicher, bevor sie gesendet wurde. 2.0 sendet sie in Blöcken oder überlässt sie dem Kernel.
- **Von 2.0 zu 2.5 ändert die Python-Engine ihre Geschwindigkeit nicht**: Die Abweichungen bleiben auf den Maschinen B und C unter 4 % und auf Maschine A im Messrauschen (−13 % bis +9 %), der Maschine, die am empfindlichsten auf Hintergrundlast reagiert. Der gesamte Gewinn von 2.5 stammt von der **nativen Engine**: etwa ×10 bis ×27 bei kleinen Dateien gegenüber der Python-Engine und eine durch 5 bis 15 geteilte Latenz.
- **Die native Engine belegt im Leerlauf etwa 5 MB mehr** als die Python-Engine (PSS): Das ist der Preis des zweiten Programms. Mit dem WAF belegt sie noch etwa 8 MB mehr: die in die native Engine geladenen Regeln.

### Was man über die native Engine wissen sollte

- Sie ist **optional**: Die Python-Engine bleibt die Standard-Engine und die Ausweich-Engine.
- Sie liefert statische Inhalte, Weiterleitungen, Umschreibungen, Aliase, den Cache, die Fehlerseiten, die Sicherheits-Header und TLS selbst aus.
- Sie durchsucht die WAF-Regeln selbst und liefert eine Anfrage, auf die keine zutrifft, allein aus. Jede andere Anfrage (Übereinstimmung oder Zweifel des WAF, Active Defense, Authentifizierung) entscheidet Python, mit genau denselben Prüfungen und denselben Protokollen. Eine einstellbare Kontrolle legt Python trotzdem eine saubere Anfrage von N vor, um zu prüfen, dass beide dasselbe Urteil fällen.
- Verzeichnislisting und interne Seiten werden bei Python angefragt; Reverse Proxy, FastCGI, Datei-Upload und WebSocket werden ihm für die ganze Verbindung übergeben. Diese Funktionen behalten also die Geschwindigkeit der Python-Engine.
- Mit direktem TLS werden Reverse Proxy, FastCGI und Datei-Upload von der nativen Engine nicht unterstützt: Dann liefert die Python-Engine aus, und die Oberfläche zeigt es an.
- Sie erfordert glibc 2.38 oder neuer und OpenSSL 3. Startet sie nicht, kompiliert die Installation sie vor Ort neu, und andernfalls bleibt omega-serv bei der Python-Engine.

---

## 6. Funktionsvergleich

Legende:
- ✅ eingebaut;
- 🧩 offizielles Modul des Projekts, zu aktivieren oder zu installieren;
- 🔌 Modul oder Plugin von Drittanbietern;
- ⚙️ über ein externes Werkzeug;
- ❌ fehlt.

„Commercial“ bezeichnet eine Funktion, die der kostenpflichtigen Edition vorbehalten ist.

### HTTP-Dienst

| Funktion | nginx | lighttpd | Caddy | Apache | Traefik | omega-serv 2.5 |
|---|---|---|---|---|---|---|
| Sprache des Servers | C | C | Go | C | Go | Python, mit einer optionalen nativen C++-Engine |
| Statische Dateien ausliefern | ✅ | ✅ | ✅ | ✅ | ❌ (nur Proxy) | ✅ |
| ETag / 304 / Range | ✅ | ✅ | ✅ | ✅ | — | ✅ |
| Vorkomprimierte Dateien `.gz` / `.br` | ✅ `gzip_static` (`.br`: 🔌) | 🔌 Lua-Skript (mod_magnet) | ✅ `precompressed` | 🧩 mod_rewrite-Rezept | — | ✅ |
| Komprimierung im laufenden Betrieb | ✅ | ✅ mod_deflate | ✅ | 🧩 mod_deflate | ✅ Middleware | ❌ |
| HTTP/2 | ✅ | ✅ | ✅ | 🧩 mod_http2 | ✅ | ❌ |
| HTTP/3 (QUIC) | ✅ | ❌ | ✅ | ❌ | ✅ | ❌ |
| PHP über FastCGI | ✅ | ✅ | ✅ | ✅ | ❌ | ✅ |
| Mehrere Prozesse oder Kerne | ✅ Worker | ⚠️ `max-worker`, von der Dokumentation abgeraten | ✅ (Go, alle Kerne) | ✅ MPM | ✅ (Go) | ✅ `server.workers`; native Engine: alle Kerne |

### Reverse Proxy

| Funktion | nginx | lighttpd | Caddy | Apache | Traefik | omega-serv 2.5 |
|---|---|---|---|---|---|---|
| Lastverteilung | ✅ Round Robin, wenigste Verbindungen, Hash | ✅ fair, round-robin, hash, sticky | ✅ ein Dutzend Strategien | 🧩 mod_proxy_balancer | ✅ wrr, p2c, hrw, least-time | ✅ 7 Strategien, darunter die tatsächliche Last |
| Passive Gesundheit (ausgefallenen Server aussortieren) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Aktive Gesundheit (periodische Prüfung) | Commercial (NGINX Plus) | ❌ | ✅ | 🧩 mod_proxy_hcheck | ✅ | ✅ |
| Antwort-Cache | ✅ `proxy_cache` | ❌ | 🔌 | 🧩 mod_cache | Commercial | ✅ |
| WebSocket | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Dienst-Erkennung (Docker, Kubernetes) | 🔌 | ❌ | 🔌 | ❌ | ✅ (Kern des Projekts) | ❌ |

### TLS

| Funktion | nginx | lighttpd | Caddy | Apache | Traefik | omega-serv 2.5 |
|---|---|---|---|---|---|---|
| Automatische Zertifikate (ACME, Let's Encrypt) | 🧩 `ngx_http_acme_module` | ⚙️ Certbot | ✅ standardmäßig | 🧩 mod_md | ✅ | ⚙️ Certbot, mit eingebautem Assistenten und geplanter Erneuerung |
| Lokale CA | ❌ | ❌ | ✅ interne CA (automatische Ausstellung) | ❌ | ❌ | ✅ Erzeugung, CSR-Signatur, Widerruf |

### Sicherheit

| Funktion | nginx | lighttpd | Caddy | Apache | Traefik | omega-serv 2.5 |
|---|---|---|---|---|---|---|
| Ratenbegrenzung pro Client | ✅ `limit_req` | ⚠️ mod_evasive (nur gleichzeitige Verbindungen) | 🔌 caddy-ratelimit | 🔌 mod_evasive, mod_qos | ✅ Middleware | ✅ |
| Zwischen Prozessen geteilte Grenze | ✅ gemeinsamer Speicherbereich | ❌ pro Prozess gezählt | — (nur 1 Prozess) | je nach Modul | 1 Instanz; mehrere mit Redis | ✅ gemeinsamer Speicher |
| WAF (SQLi/XSS-Signaturen, Scanner…) | 🔌 ModSecurity, Commercial (App Protect) | ❌ (Lua-Skripte zu schreiben) | 🔌 Coraza | 🔌 ModSecurity | 🔌 Plugins | ✅ eingebaut |
| Sperrliste mit Ablauf, Wiederholung | ⚙️ fail2ban | ⚙️ fail2ban | ⚙️ fail2ban | ⚙️ fail2ban | ⚙️ | ✅ eingebaut |
| Köder, Kriegsmodus, Vorfälle, IoC-Export | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ Active Defense |
| Abgestufte Sperren über die Zeit | ⚙️ fail2ban | ⚙️ fail2ban | ⚙️ fail2ban | ⚙️ fail2ban | ⚙️ | ✅ RIPOSTE |
| Sicherheitsaudit der Konfiguration | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ `audit security` |
| Beobachtungsmodus (protokollieren ohne zu blockieren) | je nach Modul | — | je nach Plugin | ✅ ModSecurity `DetectionOnly` | je nach Plugin | ✅ |

Abgestufte Sperren: immer längere Sperren für Adressen, die wiederkommen, über Wochen, lokal oder auf Netzwerkebene. fail2ban erreicht das mit seiner Option `bantime.increment`; RIPOSTE ergänzt Richtlinien, die an den Protokollen gemessen und vor der Aktivierung simuliert werden, die Aufhebung einer Aktion und einen Not-Aus.

### Erweiterbarkeit

| Funktion | nginx | lighttpd | Caddy | Apache | Traefik | omega-serv 2.5 |
|---|---|---|---|---|---|---|
| Skriptsprache | 🧩 njs (JavaScript); 🔌 Lua (OpenResty) | ✅ Lua (mod_magnet) | Go-Module (Neukompilierung) | 🧩 mod_lua | Go- oder WebAssembly-Plugins | 🔌 Import von mod_magnet-Skripten (Option `magnet`) |
| Modul-Ökosystem | sehr groß | gezielt | groß | sehr groß | groß | keins: alles ist eingebaut |

---

## 7. Verwaltung und Bedienung

| Server | Hauptart der Verwaltung | Oberfläche | Neuladen ohne Unterbrechung |
|---|---|---|---|
| nginx | Konfigurationsdateien | keine (Dashboard: NGINX Plus, kommerziell) | ✅ `nginx -s reload` |
| lighttpd | Konfigurationsdatei | keine (mod_status nur lesend) | ✅ sanfter Neustart |
| Caddy | Caddyfile oder JSON | REST-Verwaltungs-API | ✅ über die API |
| Apache | Konfigurationsdateien und `.htaccess` | keine (mod_status nur lesend) | ✅ `graceful` |
| Traefik | Container-Labels, Dateien oder Kubernetes | Web-Dashboard (nur lesend) | ✅ dynamische Konfiguration |
| omega-serv | Terminaloberfläche (TUI) und Befehlszeile (CLI); die JSON-Datei muss nicht bearbeitet werden | **vollständige TUI mit Tastatur und Maus, 17 Sprachen, eingebaute Hilfe** | ✅ für die meisten Einstellungen; Neustart angekündigt für Port, TLS, Engine und Anzahl der Prozesse |

Konkret verwaltet man mit omega-serv Konfiguration, Sicherheit, Protokolle, Systemdienste, Sicherungen und Instanzen über eine einzige Oberfläche. Jede Einstellung wird erklärt und vor dem Schreiben geprüft. Bei den anderen Servern bearbeitet man Textdateien und greift dann auf getrennte Werkzeuge zurück (Certbot, fail2ban, logrotate, ModSecurity, ein Überwachungswerkzeug…).

Im Gegenzug lässt sich der Ansatz „Konfigurationsdatei“ von nginx, Apache und Caddy sehr gut automatisieren (Ansible, Container, Versionsverwaltung). omega-serv hat eine skriptfähige CLI, aber sein Automatisierungs-Ökosystem bleibt begrenzt.

---

## 8. Was omega-serv zusätzlich bietet

Dieser Abschnitt nennt nur, was keiner der verglichenen Server so mitliefert, ohne Drittmodul oder externes Werkzeug.

1. **Eine vollständige Verwaltung in einer Terminaloberfläche.**
   - Die Oberfläche deckt den ganzen Server ab: die Website, die Sicherheit, die Protokolle, die Dienste, die Sicherungen und die Instanzen.
   - Sie wird mit Tastatur und Maus bedient, auf einem Server ohne grafische Anzeige, auch über SSH.
   - Sie ist in 17 Sprachen verfügbar und erklärt jede Einstellung.
   - Die anderen Server haben keine Verwaltungsoberfläche (nginx, lighttpd, Apache) oder nur eine API (Caddy) oder ein nur lesendes Dashboard (Traefik).
2. **Eine eingebaute aktive Sicherheit, ohne Module zusammenzusetzen.**
   - Der WAF umfasst Signaturen, bearbeitbare Pfadlisten, die Wiederholungsregel, eine Sperrliste mit Ablauf, die Reputation und einen Beobachtungsmodus.
   - Active Defense ergänzt Köder, einen Kriegsmodus, die Verfolgung von Vorfällen, den Export von Kompromittierungsindikatoren und eine Trockensimulation.
   - RIPOSTE reagiert über die Zeit: Es merkt sich die Adressen, die wiederkommen, und wendet abgestufte Antworten an, immer längere Sperren (standardmäßig 1 h, 6 h, 24 h, 7 Tage), lokal in der Sperrliste oder auf Netzwerkebene über fail2ban (omega-jail), oder einen verlängerten Köder. Jede Richtlinie kann an den echten Protokollen gemessen und vor der Aktivierung simuliert werden; jede Aktion bleibt sichtbar und kann aufgehoben werden, mit einem Not-Aus.
   - Anderswo muss man dafür ModSecurity oder Coraza, Regelwerke und fail2ban zusammensetzen.
3. **Exakte Sicherheitsgrenzen bei mehreren Prozessen.**
   - Bei mehreren Prozessen werden die Ratenbegrenzung und die Wiederholungsregel des WAF im Speicher zwischen ihnen geteilt. Ein Angreifer kann seine Grenze also nicht mit der Zahl der Prozesse vervielfachen.
   - lighttpd dokumentiert den umgekehrten Fall: Mit `server.max-worker` zählen `mod_evasive` und `mod_status` in jedem Prozess getrennt.
   - nginx teilt seine Zähler ebenfalls (Zonen `limit_req`), hat aber keinen eingebauten WAF.
4. **Zwei Engines, ein Verhalten.** Die native Engine und die Python-Engine erzeugen dieselben Antworten und dieselben Protokolle, automatisch auf einem Vergleichsprüfstand geprüft. Die Werkzeuge, die die Protokolle lesen (zum Beispiel fail2ban), sehen keinen Unterschied.
5. **Der Import von lighttpd-mod_magnet-Skripten.**
   - Ein bereits für lighttpd geschriebenes Lua-Schutzskript wird ohne Umschreiben importiert.
   - Es ergänzt den eingebauten Schutz, ohne ihn je schwächen zu können, und seine Kompatibilität wird vor der Aktivierung geprüft.
6. **Die Verwaltung mehrerer Instanzen.**
   - Ein Register erfasst alle Instanzen, und die Oberfläche wechselt zwischen ihnen.
   - Sie kann eine Instanz auch vollständig deinstallieren.
7. **Ein Sicherheitsaudit der Konfiguration**: Der Befehl `audit security` ist informativ, blockiert nie und liefert in einem Skript auswertbare Rückgabecodes.
8. **Entfernte Protokollquellen.**
   - Die Oberfläche holt das Protokoll eines anderen Servers bei Bedarf über SSH, ohne gespeichertes Passwort.
   - Sie kann es mit lnav lesen und dabei mit den lokalen Protokollen zusammenführen.
9. **Eine nicht abschaltbare HTTP-Härtung**, ab der Installation aktiv, unabhängig von Profil und Engine:
   - strikte Validierung des Host-Headers;
   - Ablehnung der Mehrdeutigkeiten Content-Length / Transfer-Encoding;
   - Sicherheits-Header und CSP auf den Antworten der Website, auch auf ihren Fehlerseiten;
   - sicheres Lesen von X-Forwarded-For;
   - Weigerung, als root zu starten.

---

## 9. Was die anderen besser machen

- **Durchsatz**: lighttpd und nginx bleiben bei kleinen und mittleren Dateien die schnellsten, auf allen drei Maschinen. Selbst mit der nativen Engine liefert omega-serv etwa das 0,7-Fache von nginx und das 0,5-Fache von lighttpd bei kleinen Dateien und das 0,3- bis 0,6-Fache von nginx bei Dateien von 100 KB. Für eine Website mit hohem Verkehr, eine öffentliche API oder ein CDN sind sie die richtige Wahl.
- **Mittlere Dateien**: Apache liefert Dateien von 100 KB schneller aus als die native Engine von omega-serv, auf allen drei Maschinen.
- **Speicher**: lighttpd (1 MB), nginx (4 bis 5 MB) und Apache (4 bis 9 MB) eignen sich für sehr beschränkte Maschinen (eingebettete Systeme, kleine Container). omega-serv braucht 30 bis 65.
- **Kosten der Sicherheit**: Der WAF hat weiterhin Kosten. Mit der nativen Engine nimmt er bei kleinen Dateien 5 bis 22 % des Durchsatzes, Ratenbegrenzung inbegriffen: omega-serv mit WAF liefert auf den Maschinen A und B das 0,53- bis 0,56-Fache von nginx ohne WAF. Eine verdächtige oder zweifelhafte Anfrage (Übereinstimmung einer Regel, Nicht-ASCII-Text, von Active Defense beobachtete Quelle) läuft immer über Python und wird mit der Geschwindigkeit der Python-Engine ausgeliefert. Mit aktivem magnet laufen alle Anfragen über Python, und der WAF teilt den Durchsatz der nativen Engine dann durch 4 bis 7, wie vor der Optimierung.
- **Protokolle**: HTTP/2 bei allen anderen, HTTP/3 bei nginx, Caddy und Traefik. omega-serv spricht nur HTTP/1.1.
- **Automatisches HTTPS**: Caddy und Traefik bringen es standardmäßig mit, nginx (`ngx_http_acme_module`) und Apache (`mod_md`) mit einem offiziellen Modul. omega-serv delegiert an Certbot, mit einem Assistenten und geplanter Erneuerung.
- **Container-Umgebungen**: Die automatische Dienst-Erkennung von Traefik (Docker, Kubernetes) hat in omega-serv keine Entsprechung.
- **Ökosystem und Reife**: nginx und Apache bieten Tausende von Modulen, Anleitungen und Integrationen sowie Jahrzehnte des Produktiveinsatzes. Caddy bietet ein Modulsystem in Go. omega-serv ist ein junges Projekt, das von einer einzigen Person gepflegt wird, und seine native Engine ist neu.
- **Komprimierung im laufenden Betrieb**: omega-serv liefert nur bereits komprimierte Dateien aus.

---

## 10. Welcher Server für welchen Einsatz

| Bedarf | Empfohlene Wahl |
|---|---|
| Website mit hohem Verkehr, öffentliche API, CDN, maximaler Durchsatz | **nginx** oder **lighttpd** |
| Sehr beschränkte Maschine, eingebettetes System, statische Dateien | **lighttpd** |
| Schneller Start mit automatischem HTTPS, kurze Konfiguration | **Caddy** |
| Historische PHP-Anwendung, `.htaccess`, Shared Hosting | **Apache** |
| Docker, Kubernetes, Microservices | **Traefik** |
| Kleine oder mittlere Website, interner Dienst, Labor, VPN, Verwaltung ohne Dateien zu bearbeiten | **omega-serv** (native Engine wenn möglich) |
| Exponierter Server, dessen Sicherheit (WAF, abgestufte Sperren, Köder) man über eine einzige Oberfläche sehen und steuern will | **omega-serv** |
| Interner Reverse Proxy mit Lastverteilung, Gesundheitsprüfung und Cache, über eine Oberfläche gesteuert | **omega-serv** |
| HTTP-Härtung und aktive Abwehr lernen | **omega-serv** |

Diese Werkzeuge lassen sich auch kombinieren. Zum Beispiel:
- nginx oder Traefik vorne zum Internet hin, mit omega-serv dahinter für einen internen Dienst, seine Sicherheit und seine Verwaltung;
- omega-serv als interner Reverse Proxy vor mehreren Anwendungsservern.

---

## 11. Die Messungen reproduzieren

Die Werkzeuge werden im Repository unter `tools/bench/` mitgeliefert. Man braucht installierte nginx, lighttpd, Apache, Caddy und oha, die Entwicklungsumgebung von omega-serv (`.venv`) und, für die native Engine, die in `native/omega-http-core/build-release` kompilierte Binärdatei.

```sh
# 1. einen Messordner vorbereiten (Testdateien, Konfigurationen, omega-serv 1.0, 2.0 und aktuelle Version)
tools/bench/compare/setup.sh /pfad/messung omega-serv-1.0.0.tar.gz omega-serv-2.0.0.tar.gz

# 2. die 21 Konfigurationen, 3 verschränkte Wiederholungen (40 bis 60 Minuten)
#    SRV_CPUS / CLI_CPUS: Kerne von Server und Client (lscpu -e zeigt die Topologie)
SRV_CPUS=0,1 CLI_CPUS=2,3 tools/bench/compare/campaign.sh /pfad/messung > ergebnisse.txt

# 3. Mediane
python3 tools/bench/compare/summarize.py ergebnisse.txt

# andere Liste von Konfigurationen, zum Beispiel 4 Prozesse
CONFIGS="nginx-4 lighttpd-4 caddy-4 apache-4 omega-v2-1-0-native omega-v2-4-1-native" \
  tools/bench/compare/campaign.sh /pfad/messung > ergebnisse-4.txt

# große Downloads (Speicher und Reaktionsfähigkeit): aktuelle Version, Python-Engine, dann nativ, dann 1.0
.venv/bin/python tools/bench/bigfile.py
BENCH_ENGINE=native .venv/bin/python tools/bench/bigfile.py
BENCH_SRC=/pfad/messung/v1-archive/omega-serv/src \
BENCH_EXTRA_PATH=/pfad/messung/v1-archive/omega-serv/vendor/omega-lib/src \
  .venv/bin/python tools/bench/bigfile.py

# einen beliebigen anderen, bereits laufenden Server messen, ohne oha
python3 tools/bench/bench_any.py --make-files /srv/test-webroot
python3 tools/bench/bench_any.py --port 8080
```

Namen der Konfigurationen: `nginx-N`, `lighttpd-N`, `apache-N`, `caddy-N` (N Prozesse, oder N Kerne bei Caddy); `omega-vX-N-W` für omega-serv (Version `v1`, `v20` oder `v2` für die aktuelle Version, N Prozesse, W = 0 ohne WAF oder 1 mit), gefolgt von `-native` für die native Engine.

Um eigene Ergebnisse zu veröffentlichen, geben Sie die Maschine, die Versionen, die Verteilung der Kerne und die drei Wiederholungen an.

---

## 12. Quellen

Funktionen der anderen Server, nach ihrer offiziellen Dokumentation (abgerufen am 26. Oktober 2026).

**nginx**
- [Ratenbegrenzung `limit_req` (gemeinsamer Speicherbereich)](https://nginx.org/en/docs/http/ngx_http_limit_req_module.html)
- [Vorkomprimierte Dateien `gzip_static`](https://nginx.org/en/docs/http/ngx_http_gzip_static_module.html)
- [Offizielles ACME-Modul `ngx_http_acme_module`](https://nginx.org/en/docs/http/ngx_http_acme_module.html)
- [Lastverteilung (`upstream`)](https://nginx.org/en/docs/http/ngx_http_upstream_module.html)
- [HTTP/3](https://nginx.org/en/docs/http/ngx_http_v3_module.html)
- [ModSecurity-Connector für nginx](https://github.com/owasp-modsecurity/ModSecurity-nginx)

**lighttpd**
- [`server.max-worker`: abgeraten, Zähler pro Prozess für mod_status und mod_evasive](https://redmine.lighttpd.net/projects/lighttpd/wiki/Server_max-workerDetails)
- [mod_magnet (Lua-Skripte)](https://redmine.lighttpd.net/projects/lighttpd/wiki/Docs_ModMagnet)
- [mod_deflate (Komprimierung, Cache)](https://redmine.lighttpd.net/projects/lighttpd/wiki/Mod_deflate)
- [mod_proxy (Lastverteilung, passive Gesundheit, WebSocket)](https://redmine.lighttpd.net/projects/lighttpd/wiki/Docs_ModProxy)
- [mod_evasive (gleichzeitige Verbindungen pro Adresse)](https://redmine.lighttpd.net/projects/lighttpd/wiki/Docs_ModEvasive)

**Caddy**
- [Automatisches HTTPS](https://caddyserver.com/docs/automatic-https)
- [`file_server` und `precompressed`](https://caddyserver.com/docs/caddyfile/directives/file_server)
- [`reverse_proxy` (Strategien, aktive und passive Gesundheit)](https://caddyserver.com/docs/caddyfile/directives/reverse_proxy)
- [Verwaltungs-API](https://caddyserver.com/docs/api)
- [Ratenbegrenzungs-Plugin caddy-ratelimit](https://github.com/mholt/caddy-ratelimit)
- [WAF Coraza für Caddy](https://github.com/corazawaf/coraza-caddy)
- [caddy-docker-proxy](https://github.com/lucaslorentz/caddy-docker-proxy)

**Apache HTTP Server**
- [MPM event](https://httpd.apache.org/docs/2.4/mod/event.html)
- [mod_md (ACME)](https://httpd.apache.org/docs/2.4/mod/mod_md.html)
- [mod_proxy_balancer](https://httpd.apache.org/docs/2.4/mod/mod_proxy_balancer.html)
- [mod_proxy_hcheck](https://httpd.apache.org/docs/2.4/mod/mod_proxy_hcheck.html)
- [mod_http2](https://httpd.apache.org/docs/2.4/mod/mod_http2.html)
- [mod_deflate, vorkomprimierte Inhalte](https://httpd.apache.org/docs/2.4/mod/mod_deflate.html)
- [ModSecurity](https://github.com/owasp-modsecurity/ModSecurity)

**Traefik**
- [Middleware `ratelimit` (im Speicher pro Instanz, Redis optional)](https://doc.traefik.io/traefik/reference/routing-configuration/http/middlewares/ratelimit/)
- [ACME](https://doc.traefik.io/traefik/https/acme/)
- [Providers (Docker, Kubernetes…)](https://doc.traefik.io/traefik/providers/overview/)

**fail2ban**
- [`jail.conf`: `bantime.increment`, `bantime.factor`, `bantime.multipliers`, `bantime.maxtime` (längere Sperren für Wiederholungstäter)](https://github.com/fail2ban/fail2ban/blob/master/config/jail.conf) (abgerufen am 4. November 2026)

**Messwerkzeug**
- [oha](https://github.com/hatoo/oha)

---

*Vergleich von kraynux für omega-serv 2.5: Messungen vom 3. und 4. November 2026 auf drei Maschinen (aktive Abwehr: 26. Oktober 2026). Messen Sie für jede Kapazitätsentscheidung auf Ihrer eigenen Hardware mit den mitgelieferten Werkzeugen.*
