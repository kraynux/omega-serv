<!-- Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE) -->

# omega-serv im Vergleich mit den Webservern am Markt

**Gemessener Vergleich: nginx · lighttpd · Caddy · Apache · Traefik · omega-serv 2.0**

🌐 [Français](../../comparatif-serveurs-web.md) · [English](../en/comparatif-serveurs-web.md) · [Español](../es/comparatif-serveurs-web.md) · [Português (Brasil)](../pt-BR/comparatif-serveurs-web.md) · [Italiano](../it/comparatif-serveurs-web.md) · **Deutsch** · [Nederlands](../nl/comparatif-serveurs-web.md) · [Polski](../pl/comparatif-serveurs-web.md) · [Русский](../ru/comparatif-serveurs-web.md) · [中文](../zh-CN/comparatif-serveurs-web.md) · [Tiếng Việt](../vi/comparatif-serveurs-web.md) · [ไทย](../th/comparatif-serveurs-web.md) · [Bahasa Indonesia](../id/comparatif-serveurs-web.md) · [日本語](../ja/comparatif-serveurs-web.md) · [한국어](../ko/comparatif-serveurs-web.md) · [हिन्दी](../hi/comparatif-serveurs-web.md) · [العربية](../ar/comparatif-serveurs-web.md)

Dieses Dokument ordnet omega-serv unter den verbreitetsten Webservern ein. Es will keinen „besten Server“ küren: Jedes Werkzeug erfüllt andere Anforderungen. Es liefert drei Dinge:

1. **echte Messungen**, auf derselben Maschine, mit demselben Client und denselben Dateien, und reproduzierbar;
2. einen **Funktionsvergleich**, jede Funktion geprüft in der offiziellen Dokumentation des jeweiligen Servers (Links am Ende des Dokuments), wobei unterschieden wird, was integriert ist und was ein Modul oder Plugin braucht;
3. was omega-serv **tatsächlich zusätzlich bietet**, und was die anderen **besser machen**.

Alle folgenden Zahlen wurden am 26. Oktober 2026 gemessen. Keine Zahl stammt von einer anderen Website oder ist geschätzt.

---

## Inhalt

1. [Kurz gesagt](#1-kurz-gesagt)
2. [Messmethode](#2-messmethode)
3. [Leistung: omega-serv im Vergleich mit nginx, lighttpd und Caddy](#3-leistung-omega-serv-im-vergleich-mit-nginx-lighttpd-und-caddy)
4. [omega-serv 1.0 → 2.0: was sich geändert hat, gemessen](#4-omega-serv-10--20-was-sich-geändert-hat-gemessen)
5. [Funktionsvergleich](#5-funktionsvergleich)
6. [Verwaltung und Bedienung](#6-verwaltung-und-bedienung)
7. [Was omega-serv zusätzlich bietet](#7-was-omega-serv-zusätzlich-bietet)
8. [Was die anderen besser machen](#8-was-die-anderen-besser-machen)
9. [Welcher Server für welchen Einsatz](#9-welcher-server-für-welchen-einsatz)
10. [Die Messungen nachvollziehen](#10-die-messungen-nachvollziehen)
11. [Quellen](#11-quellen)

---

## 1. Kurz gesagt

- **Rohdurchsatz bei kleinen Dateien**: nginx und lighttpd, in C geschrieben, liefern **10- bis 20-mal mehr** Anfragen pro Sekunde als das in Python geschriebene omega-serv. Caddy, in Go geschrieben, liegt dazwischen. Das ist ein grundsätzlicher Unterschied, keine Frage der Einstellung: omega-serv zielt nicht auf dieses Terrain.
- **Große Dateien**: Seit 2.0 überlässt omega-serv das Senden dem Kernel (`sendfile`). Es erreicht damit auf dieser Maschine **dieselbe Größenordnung** wie nginx, lighttpd und Caddy: 2,1 GB/s gegenüber 2,0 bis 2,4 GB/s.
- **Speicher**: lighttpd (1 MB) und nginx (4 bis 5 MB) bleiben unerreichbar. omega-serv bleibt unter Last mit 1 Prozess unter 30 MB, Caddy bei rund 55 MB.
- **Von 1.0 zu 2.0**: Durchsatz bei großen Dateien mal 2,8; Speicher bei großen Downloads durch 45 geteilt; bis zu +50 % bei kleinen Dateien mit 2 Prozessen (Boost-Modus); Kosten von Active Defense durch 12 geteilt.
- **Was omega-serv zusätzlich hat**: eine vollständige Verwaltung über eine Terminal-Oberfläche (TUI) in 17 Sprachen; eine integrierte WAF und aktive Abwehr; Sicherheitslimits, die auch mit mehreren Prozessen exakt bleiben; den Import von lighttpd-mod_magnet-Skripten; die Verwaltung mehrerer Instanzen.
- **Was es nicht hat**: HTTP/2 und HTTP/3, Service Discovery für Docker/Kubernetes, einen integrierten ACME-Client (es nutzt Certbot), den Durchsatz eines in C geschriebenen Servers.

---

## 2. Messmethode

### Maschine und Software

| Element | Wert |
|---|---|
| Prozessor | Intel Core i5 M480 mit 2,67 GHz (2010): 2 physische Kerne, 4 Threads |
| Arbeitsspeicher | 8 GB |
| System | Manjaro Linux, Kernel 6.18 |
| Netzwerk | Loopback (127.0.0.1) |
| Last-Client | [oha](https://github.com/hatoo/oha) 1.16.0 (in Rust geschrieben) |
| nginx | 1.30.4 (Manjaro-Paket) |
| lighttpd | 1.4.85 (Manjaro-Paket) |
| Caddy | 2.11.4 (Manjaro-Paket) |
| omega-serv | 1.0.0 (veröffentlichtes Archiv) und 2.0.0, unter Python 3.14.7 |

Apache und Traefik wurden nicht gemessen, da sie auf dieser Maschine nicht installiert waren. Traefik ist zudem kein Dateiserver (siehe §5). Diese beiden Server erscheinen daher nur im Funktionsvergleich.

### Ablauf

- **Prozessor-Isolation**: Jeder Server ist an den physischen Kern 0 gebunden (Threads 0 und 2), der Client an den physischen Kern 1 (Threads 1 und 3). So nimmt der Client dem Server keine Rechenzeit weg, und alle Server haben exakt dieselben Ressourcen.
- **Dieselben Dateien für alle**: `small.html` (1 KB), `medium.png` (100 KB) und `large.bin` (5 MB), ausgeliefert aus demselben Ordner.
- **Zugriffsprotokoll überall aktiv**, denn ein Produktionsserver protokolliert.
- **Unverschlüsseltes HTTP/1.1, persistente Verbindungen (Keep-Alive)**. Die Parallelität beträgt 32 Verbindungen für die Dateien mit 1 KB und 100 KB und 8 für die 5-MB-Datei.
- **Dauer**: 10 Sekunden pro Datei und pro Konfiguration.
- **Wiederholungen**: 3 vollständige, verschachtelte Durchgänge (alle Server in Durchgang 1, dann alle in Durchgang 2 usw.). Die Tabellen zeigen den **Median** der drei Durchgänge.
- **Speicher**: PSS (*Proportional Set Size*), summiert über alle Prozesse des Servers. Anders als beim RSS wird eine zwischen Prozessen geteilte Seite nur einmal gezählt. Gemessen im Leerlauf und nach der Last.
- **Konfigurationen**: nginx, lighttpd und Caddy in ihrer Grundkonfiguration (statische Dateien, Zugriffsprotokoll). omega-serv nutzt das Profil `standard`, mit deaktivierter WAF und dann mit aktivierter WAF samt allen mitgelieferten Regeln.
- **Anzahl der Prozesse**: Jeder Server wird mit 1 und dann mit 2 Prozessen gemessen (nginx `worker_processes`, lighttpd `server.max-worker`, Caddy `GOMAXPROCS`, omega-serv `server.workers`).

### Grenzen, die man kennen sollte

- **Bescheidene und alte Maschine.** Die absoluten Werte wären auf einem aktuellen Server deutlich höher. Aussagekräftig sind die **Verhältnisse** zwischen Servern, die in derselben Sitzung gemessen wurden.
- **Schwankung zwischen Sitzungen**: etwa 10 bis 30 %, je nach Hintergrundlast der Maschine. Die Durchgänge einer Sitzung bleiben konsistent: unter 5 % Abweichung bei omega-serv und Caddy, mehr bei nginx und lighttpd, deren sehr hoher Durchsatz empfindlicher auf den Rest der Maschine reagiert.
- **Loopback**: Die Messung läuft nicht über ein echtes Netzwerk. In einem echten Netzwerk begrenzt bei großen Dateien fast immer die Bandbreite, nicht der Server.
- **Kein TLS** in diesen Messungen. Mit HTTPS kann omega-serv `sendfile` nicht nutzen und sendet Dateien in Blöcken.
- **Rohdaten**: Sie werden mit diesem Dokument veröffentlicht in [`docs/benchmarks/2026-10-26-campagne-brute.txt`](../../benchmarks/2026-10-26-campagne-brute.txt).

---

## 3. Leistung: omega-serv im Vergleich mit nginx, lighttpd und Caddy

### Kleine Dateien (1 KB): Anfragen pro Sekunde

| Server | 1 Prozess | 2 Prozesse | Latenz p99 (1 Proz.) |
|---|---:|---:|---:|
| lighttpd 1.4.85 | 25.521 | 29.700 | 4,5 ms |
| nginx 1.30.4 | 14.054 | 18.315 | 4,7 ms |
| Caddy 2.11.4 | 3.697 | 5.345 | 25,3 ms |
| **omega-serv 2.0** | **1.358** | **1.953** | **37,5 ms** |
| omega-serv 2.0 + WAF | 1.130 | 1.617 | 48,5 ms |
| omega-serv 1.0 | 1.304 | — | 41,2 ms |

### Mittlere Dateien (100 KB): Anfragen pro Sekunde

| Server | 1 Prozess | 2 Prozesse |
|---|---:|---:|
| lighttpd | 11.635 | 13.037 |
| nginx | 8.024 | 9.555 |
| Caddy | 3.280 | 4.344 |
| **omega-serv 2.0** | **1.247** | **1.629** |
| omega-serv 2.0 + WAF | 1.012 | 1.347 |
| omega-serv 1.0 | 1.064 | — |

### Große Datei (5 MB): Durchsatz

| Server | 1 Prozess | 2 Prozesse |
|---|---:|---:|
| lighttpd | 2.379 MB/s | 2.407 MB/s |
| nginx | 2.242 MB/s | 1.981 MB/s |
| Caddy | 2.165 MB/s | 2.229 MB/s |
| **omega-serv 2.0** | **1.658 MB/s** | **2.115 MB/s** |
| omega-serv 1.0 | 584 MB/s | — |

### Speicher (PSS, alle Prozesse des Servers)

| Server | Im Leerlauf | Nach der Last |
|---|---:|---:|
| lighttpd (1 oder 2 Proz.) | 1 MB | 1 MB |
| nginx (1 oder 2 Proz.) | 4 bis 5 MB | 4 bis 5 MB |
| **omega-serv 2.0 (1 Proz.)** | **26 MB** | **30 MB** |
| omega-serv 2.0 (2 Proz.) | 39 MB | 48 MB |
| Caddy | 50 MB | 56 MB |
| omega-serv 1.0 | 22 MB | 100 MB |

### Einordnung

- **Bei kleinen und mittleren Dateien** liegt der Abstand zu nginx und lighttpd bei einer Größenordnung (×10 bis ×20). Das ist der Preis eines in Python geschriebenen Servers: Jede Anfrage durchläuft den Interpreter, während nginx und lighttpd sie in kompiliertem C verarbeiten. Der Boost-Modus verringert den Abstand, schließt ihn aber nicht.
- **Bei großen Dateien** gleichen sich die Server an, weil der Kernel die Daten kopiert (`sendfile`). Mit 2 Prozessen erreicht omega-serv 2.0 2,1 GB/s, im selben Bereich wie die anderen (2,0 bis 2,4 GB/s).
- **Die WAF von omega-serv kostet etwa 17 %** bei kleinen Dateien: Sie prüft jede Anfrage. nginx, lighttpd und Caddy wurden ohne WAF gemessen; eine bei diesen Servern hinzugefügte WAF (ModSecurity, Coraza) kostet ebenfalls Leistung, was hier nicht gemessen wurde.
- **Zur Einordnung**: 1.300 Anfragen pro Sekunde sind über 110 Millionen Anfragen pro Tag auf dieser Maschine von 2010. Das liegt weit über dem Bedarf einer persönlichen Website, eines internen Dienstes oder eines Labors – genau den Einsätzen, auf die omega-serv zielt.

---

## 4. omega-serv 1.0 → 2.0: was sich geändert hat, gemessen

### Leistung

Beide Versionen wurden in derselben Sitzung, auf derselben Maschine und nach demselben Ablauf gemessen.

| Messung | 1.0.0 | 2.0.0 | Veränderung |
|---|---:|---:|---:|
| Kleine Dateien (1 KB), 1 Prozess | 1.304 Anf./s | 1.358 Anf./s | +4 % |
| Kleine Dateien (1 KB), Boost-Modus 2 Prozesse | — | 1.953 Anf./s | **+50 %** ggü. 1.0 |
| Kleine Dateien mit WAF, 1 Prozess | 1.097 Anf./s | 1.130 Anf./s | +3 % |
| Kleine Dateien mit WAF, 2 Prozesse | — | 1.617 Anf./s | **+47 %** ggü. 1.0 |
| Dateien mit 100 KB, 1 Prozess | 1.064 Anf./s | 1.247 Anf./s | +17 % |
| Große Datei (5 MB), 1 Prozess | 584 MB/s | 1.658 MB/s | **×2,8** |
| Große Datei (5 MB), 2 Prozesse | — | 2.115 MB/s | **×3,6** ggü. 1.0 |
| Speicher nach der Last, 1 Prozess | 100 MB | 30 MB | **÷3** |

### Gleichzeitige große Downloads

Test: 3 gleichzeitige Downloads einer 300-MB-Datei, während eine kleine Seite fortlaufend angefordert wird. Zwei Durchläufe liefern identische Ergebnisse.

| Messung | 1.0.0 | 2.0.0 |
|---|---:|---:|
| Höchster Speicherverbrauch des Servers | 1.835 MB | 40 MB |
| Kleine Seite während der Downloads: Median | 3 bis 4 ms | 2 ms |
| Kleine Seite während der Downloads: schlechtester Fall | 1,7 bis 1,8 s | 5 ms |

Version 1.0 lud jede Datei vollständig in den Speicher, bevor sie sie sendete. Version 2.0 sendet sie in Blöcken oder überlässt sie dem Kernel: Der Speicher hängt nicht mehr von der Dateigröße ab, und der Server bleibt während der Downloads reaktionsschnell.

### Kosten der aktiven Abwehr

Kosten einer Bedrohungsbeobachtung durch Active Defense, für jede verdächtige Anfrage, gemessen auf der Festplatte (ext4) über 2.000 Beobachtungen:

| Messung | 1.0.0 | 2.0.0 |
|---|---:|---:|
| Median | 2,84 ms | 0,23 ms |
| p99 | 11,6 ms | 2,3 ms |
| Maximum | 18 bis 20 ms | 37 bis 46 ms |

Der Median ist durch 12 geteilt. Das Maximum ist in 2.0 dagegen höher: einige vereinzelte Spitzen, verursacht durch das periodische Schreiben des SQLite-Journals auf die Festplatte.

### Mit 2.0 neu hinzugekommene Funktionen

**Angleichung an die Marktstandards**: nginx, lighttpd, Caddy und Apache können all das bereits. omega-serv holt auf.

- Bedingte Anfragen (ETag, Last-Modified, 304-Antworten): Beim Neuladen einer Seite wird nur erneut geladen, was sich geändert hat.
- Teilanfragen (Range, 206/416): Fortsetzen eines Downloads, Springen in einem Video.
- Senden der Dateien per `sendfile` oder in Blöcken, mit stabilem Speicherverbrauch.
- Vorkomprimierte Dateien (`.gz`, `.br`) neben dem Original abgelegt.
- Standard-Cache-Control je Dateityp (Bilder, Schriften, CSS/JS), einstellbar.
- Mehrere Serverprozesse (Boost-Modus, `server.workers`).

**Erweiterte Funktionen:**

- **Vollständiger Reverse Proxy.** Version 1.0 hatte nur eine einfache Weiterleitung (Rundlauf, TLS zum Upstream-Server, WebSocket). Version 2.0 ergänzt:
  - 6 Lastverteilungsstrategien, insgesamt 7;
  - Sitzungsaffinität und Routing nach Header;
  - passive und aktive Zustandsprüfung der Upstream-Server;
  - einen Antwort-Cache;
  - Schutz vor Überlastung und vor Schleifen;
  - Steuerung im laufenden Betrieb.
- **Rate-Limit pro Ordner und pro Adresse oder Netz**, zusätzlich zum globalen Limit.
- **Zwischen Prozessen geteilte Sicherheitszähler** (siehe §7).
- **Listen sensibler Pfade**, sofort einsatzbereit, mit einem Beobachtungsmodus und einem integrierten Editor.
- **Import von lighttpd-mod_magnet-Skripten** (siehe §7).
- **Oberfläche in 17 Sprachen**, mit einer eigenen Sprache für die Seiten, die Besucher sehen, und für Exporte.
- **Komplett überarbeitete Protokolle**:
  - eine Protokollbibliothek;
  - drei Betrachter, darunter lnav;
  - das Abrufen entfernter Protokolle per SSH.

---

## 5. Funktionsvergleich

Legende:
- ✅ integriert;
- 🧩 offizielles Modul des Projekts, zu aktivieren oder zu installieren;
- 🔌 Modul oder Plugin eines Drittanbieters;
- ⚙️ über ein externes Werkzeug;
- ❌ nicht vorhanden.

„Kommerziell“ bezeichnet eine Funktion, die der kostenpflichtigen Edition vorbehalten ist.

### HTTP-Auslieferung

| Funktion | nginx | lighttpd | Caddy | Apache | Traefik | omega-serv 2.0 |
|---|---|---|---|---|---|---|
| Statische Dateien ausliefern | ✅ | ✅ | ✅ | ✅ | ❌ (nur Proxy) | ✅ |
| ETag / 304 / Range | ✅ | ✅ | ✅ | ✅ | — | ✅ |
| Vorkomprimierte Dateien `.gz` / `.br` | ✅ `gzip_static` (`.br`: 🔌) | 🔌 Lua-Skript (mod_magnet) | ✅ `precompressed` | 🧩 mod_rewrite-Rezept | — | ✅ |
| Komprimierung im laufenden Betrieb | ✅ | ✅ mod_deflate | ✅ | 🧩 mod_deflate | ✅ Middleware | ❌ |
| HTTP/2 | ✅ | ✅ | ✅ | 🧩 mod_http2 | ✅ | ❌ |
| HTTP/3 (QUIC) | ✅ | ❌ | ✅ | ❌ | ✅ | ❌ |
| PHP über FastCGI | ✅ | ✅ | ✅ | ✅ | ❌ | ✅ |
| Mehrere Prozesse oder Kerne | ✅ Worker | ⚠️ `max-worker`, von der Dokumentation abgeraten | ✅ (Go, alle Kerne) | ✅ MPM | ✅ (Go) | ✅ `server.workers` |

### Reverse Proxy

| Funktion | nginx | lighttpd | Caddy | Apache | Traefik | omega-serv 2.0 |
|---|---|---|---|---|---|---|
| Lastverteilung | ✅ Rundlauf, wenigste Verbindungen, Hash | ✅ fair, round-robin, hash, sticky | ✅ rund ein Dutzend Strategien | 🧩 mod_proxy_balancer | ✅ wrr, p2c, hrw, least-time | ✅ 7 Strategien, darunter die reale Last |
| Passive Zustandsprüfung (ausgefallenen Server ausschließen) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Aktive Zustandsprüfung (regelmäßige Sonde) | Kommerziell (NGINX Plus) | ❌ | ✅ | 🧩 mod_proxy_hcheck | ✅ | ✅ |
| Antwort-Cache | ✅ `proxy_cache` | ❌ | 🔌 | 🧩 mod_cache | Kommerziell | ✅ |
| WebSocket | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Service Discovery (Docker, Kubernetes) | 🔌 | ❌ | 🔌 | ❌ | ✅ (Kern des Projekts) | ❌ |

### TLS

| Funktion | nginx | lighttpd | Caddy | Apache | Traefik | omega-serv 2.0 |
|---|---|---|---|---|---|---|
| Automatische Zertifikate (ACME, Let's Encrypt) | 🧩 `ngx_http_acme_module` | ⚙️ Certbot | ✅ standardmäßig | 🧩 mod_md | ✅ | ⚙️ Certbot, mit integriertem Assistenten und geplanter Erneuerung |
| Lokale CA | ❌ | ❌ | ✅ interne CA (automatische Ausstellung) | ❌ | ❌ | ✅ Erzeugung, Signieren von CSRs, Widerruf |

### Sicherheit

| Funktion | nginx | lighttpd | Caddy | Apache | Traefik | omega-serv 2.0 |
|---|---|---|---|---|---|---|
| Rate-Limit pro Client | ✅ `limit_req` | ⚠️ mod_evasive (nur gleichzeitige Verbindungen) | 🔌 caddy-ratelimit | 🔌 mod_evasive, mod_qos | ✅ Middleware | ✅ |
| Zwischen Prozessen geteiltes Limit | ✅ gemeinsame Speicherzone | ❌ pro Prozess gezählt | — (ein einziger Prozess) | je nach Modul | 1 Instanz; mehrere mit Redis | ✅ gemeinsamer Speicher |
| WAF (SQLi/XSS-Signaturen, Scanner…) | 🔌 ModSecurity, Kommerziell (App Protect) | ❌ (Lua-Skripte selbst schreiben) | 🔌 Coraza | 🔌 ModSecurity | 🔌 Plugins | ✅ integriert |
| Sperrliste mit Ablauf, Rückfall | ⚙️ fail2ban | ⚙️ fail2ban | ⚙️ fail2ban | ⚙️ fail2ban | ⚙️ | ✅ integriert |
| Köder, Kriegsmodus, Vorfälle, IoC-Export | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ Active Defense |
| Sicherheitsaudit der Konfiguration | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ `audit security` |
| Beobachtungsmodus (protokollieren ohne zu blockieren) | je nach Modul | — | je nach Plugin | ✅ ModSecurity `DetectionOnly` | je nach Plugin | ✅ |

### Erweiterbarkeit

| Funktion | nginx | lighttpd | Caddy | Apache | Traefik | omega-serv 2.0 |
|---|---|---|---|---|---|---|
| Skriptsprache | 🧩 njs (JavaScript); 🔌 Lua (OpenResty) | ✅ Lua (mod_magnet) | Go-Module (Neukompilierung) | 🧩 mod_lua | Go- oder WebAssembly-Plugins | 🔌 Import von mod_magnet-Skripten (Option `magnet`) |
| Modul-Ökosystem | sehr groß | gezielt | groß | sehr groß | groß | keines: alles ist integriert |

---

## 6. Verwaltung und Bedienung

| Server | Hauptsächliche Verwaltungsart | Oberfläche | Neuladen ohne Unterbrechung |
|---|---|---|---|
| nginx | Konfigurationsdateien | keine (Dashboard: NGINX Plus, kommerziell) | ✅ `nginx -s reload` |
| lighttpd | Konfigurationsdatei | keine (mod_status, nur lesend) | ✅ sanfter Neustart |
| Caddy | Caddyfile oder JSON | REST-Verwaltungs-API | ✅ über die API |
| Apache | Konfigurationsdateien und `.htaccess` | keine (mod_status, nur lesend) | ✅ `graceful` |
| Traefik | Container-Labels, Dateien oder Kubernetes | Web-Dashboard (nur lesend) | ✅ dynamische Konfiguration |
| omega-serv | Terminal-Oberfläche (TUI) und Befehlszeile (CLI); die JSON-Datei muss nie von Hand bearbeitet werden | **vollständige TUI mit Tastatur und Maus, 17 Sprachen, integrierte Hilfe** | ✅ für die meisten Einstellungen; Neustart angekündigt für Port, TLS und Prozessanzahl |

Konkret werden bei omega-serv Konfiguration, Sicherheit, Protokolle, Systemdienste, Sicherungen und Instanzen über eine einzige Oberfläche verwaltet. Jede Einstellung wird erklärt und vor dem Schreiben geprüft. Bei den anderen Servern bearbeitet man Textdateien und greift dann zu separaten Werkzeugen (Certbot, fail2ban, logrotate, ModSecurity, ein Überwachungswerkzeug…).

Im Gegenzug lässt sich der Ansatz „Konfigurationsdatei“ von nginx, Apache und Caddy sehr gut automatisieren (Ansible, Container, Versionsverwaltung). omega-serv hat eine skriptfähige CLI, sein Automatisierungs-Ökosystem ist aber noch begrenzt.

---

## 7. Was omega-serv zusätzlich bietet

Dieser Abschnitt nennt nur, was keiner der verglichenen Server so bereitstellt, ohne Drittanbietermodul oder externes Werkzeug.

1. **Eine vollständige Verwaltung über eine Terminal-Oberfläche.**
   - Die Oberfläche deckt den gesamten Server ab: Website, Sicherheit, Protokolle, Dienste, Sicherungen und Instanzen.
   - Sie lässt sich mit Tastatur und Maus bedienen, auf einem Server ohne grafische Oberfläche, auch über SSH.
   - Sie ist in 17 Sprachen verfügbar und erklärt jede Einstellung.
   - Die anderen Server haben keine Verwaltungsoberfläche (nginx, lighttpd, Apache) oder nur eine API (Caddy) bzw. ein schreibgeschütztes Dashboard (Traefik).
2. **Eine integrierte aktive Sicherheit, ohne Module zusammenzusetzen.**
   - Die WAF umfasst Signaturen, bearbeitbare Pfadlisten, Rückfallerkennung, eine Sperrliste mit Ablauf, Reputation und einen Beobachtungsmodus.
   - Active Defense ergänzt Köder, einen Kriegsmodus, Vorfallsverfolgung, den Export von Kompromittierungsindikatoren und eine Trockenlauf-Simulation.
   - Anderswo muss man dafür ModSecurity oder Coraza, Regelsätze und fail2ban zusammenstellen.
3. **Exakte Sicherheitslimits mit mehreren Prozessen.**
   - Im Boost-Modus werden das Rate-Limit und die Rückfallerkennung der WAF im Speicher zwischen den Prozessen geteilt. Ein Angreifer kann sein Limit also nicht mit der Anzahl der Prozesse vervielfachen.
   - lighttpd dokumentiert den umgekehrten Fall: Mit `server.max-worker` zählen `mod_evasive` und `mod_status` in jedem Prozess getrennt.
   - nginx teilt seine Zähler ebenfalls (Zonen von `limit_req`), hat aber keine integrierte WAF.
4. **Der Import von lighttpd-mod_magnet-Skripten.**
   - Ein bereits für lighttpd geschriebenes Lua-Schutzskript lässt sich importieren, ohne es neu zu schreiben.
   - Es ergänzt den integrierten Schutz, ohne ihn je schwächen zu können, und seine Kompatibilität wird vor der Aktivierung geprüft.
5. **Die Verwaltung mehrerer Instanzen.**
   - Ein Register erfasst alle Instanzen, und die Oberfläche wechselt zwischen ihnen.
   - Sie kann eine Instanz auch vollständig deinstallieren.
6. **Ein Sicherheitsaudit der Konfiguration**: Der Befehl `audit security` ist informativ, blockiert nie und liefert in Skripten auswertbare Exit-Codes.
7. **Entfernte Protokollquellen.**
   - Die Oberfläche ruft das Protokoll eines anderen Servers per SSH ab, bei Bedarf und ohne gespeichertes Passwort.
   - Sie kann es mit lnav lesen, zusammengeführt mit den lokalen Protokollen.
8. **Eine nicht abschaltbare HTTP-Härtung**, aktiv ab der Installation, unabhängig vom Profil:
   - strenge Prüfung des Host-Headers;
   - Ablehnung von Mehrdeutigkeiten zwischen Content-Length und Transfer-Encoding;
   - Sicherheits-Header und CSP, auch auf Fehlerseiten;
   - sicheres Auslesen von X-Forwarded-For;
   - Verweigerung des Starts als root.

---

## 8. Was die anderen besser machen

- **Durchsatz und Latenz**: nginx und lighttpd liefern 10- bis 20-mal mehr kleine Anfragen, mit 8- bis 10-mal geringerer Latenz. Für eine Website mit hohem Verkehr, eine öffentliche API oder ein CDN sind sie die richtige Wahl.
- **Speicher**: lighttpd (1 MB) und nginx (4 bis 5 MB) eignen sich für sehr eingeschränkte Maschinen (Embedded, Einstiegs-Raspberry-Pi, kleine Container).
- **Protokolle**: HTTP/2 bei allen anderen, HTTP/3 bei nginx, Caddy und Traefik. omega-serv spricht nur HTTP/1.1.
- **Automatisches HTTPS**: Caddy und Traefik bringen es standardmäßig mit, nginx (`ngx_http_acme_module`) und Apache (`mod_md`) über ein offizielles Modul. omega-serv delegiert an Certbot, mit einem Assistenten und geplanter Erneuerung.
- **Container-Umgebungen**: Die automatische Service Discovery von Traefik (Docker, Kubernetes) hat in omega-serv keine Entsprechung.
- **Ökosystem**: nginx und Apache bieten Tausende von Modulen, Anleitungen und Integrationen. Caddy bietet ein Modulsystem in Go. omega-serv ist ein junges Projekt, das von einer einzigen Person gepflegt wird.
- **Komprimierung im laufenden Betrieb**: omega-serv liefert nur bereits komprimierte Dateien aus.

---

## 9. Welcher Server für welchen Einsatz

| Bedarf | Empfohlene Wahl |
|---|---|
| Website mit hohem Verkehr, öffentliche API, CDN, maximaler Durchsatz | **nginx** |
| Sehr eingeschränkte Maschine, Embedded, statische Dateien | **lighttpd** |
| Schneller Einstieg mit automatischem HTTPS, kurze Konfiguration | **Caddy** |
| Ältere PHP-Anwendung, `.htaccess`, Shared Hosting | **Apache** |
| Docker, Kubernetes, Microservices | **Traefik** |
| Kleine Website, interner Dienst, Labor, VPN, Verwaltung ohne Dateien zu bearbeiten | **omega-serv** |
| Öffentlich erreichbarer Server, dessen Sicherheit (WAF, Sperren, Köder) man über eine einzige Oberfläche sehen und steuern will | **omega-serv** |
| Interner Reverse Proxy mit Lastverteilung, Zustandsprüfung und Cache, über eine Oberfläche gesteuert | **omega-serv** |
| HTTP-Härtung und aktive Abwehr lernen | **omega-serv** |

Diese Werkzeuge lassen sich auch kombinieren. Zum Beispiel:
- nginx oder Traefik vorne zum Internet hin, mit omega-serv dahinter für einen internen Dienst, dessen Sicherheit und Verwaltung;
- omega-serv als interner Reverse Proxy vor mehreren Anwendungsservern.

---

## 10. Die Messungen nachvollziehen

Die Werkzeuge liegen im Repository unter `tools/bench/`. Benötigt werden installierte Pakete nginx, lighttpd, Caddy und oha sowie die Entwicklungsumgebung von omega-serv (`.venv`).

```sh
# 1. einen Messordner vorbereiten (Testdateien, Konfigurationen, omega-serv 1.0 und 2.0)
tools/bench/compare/setup.sh /pfad/messung omega-serv-1.0.0.tar.gz

# 2. die 12 Konfigurationen, 3 verschachtelte Wiederholungen (etwa 22 Minuten)
tools/bench/compare/campaign.sh /pfad/messung > ergebnisse.txt

# 3. Mediane
python3 tools/bench/compare/summarize.py ergebnisse.txt

# große Downloads (Speicher und Reaktionsfähigkeit), 2.0 und dann 1.0
.venv/bin/python tools/bench/bigfile.py
BENCH_SRC=/pfad/messung/v1-archive/omega-serv/src \
BENCH_EXTRA_PATH=/pfad/messung/v1-archive/omega-serv/vendor/omega-lib/src \
  .venv/bin/python tools/bench/bigfile.py

# einen beliebigen anderen, bereits laufenden Server messen, ohne oha
python3 tools/bench/bench_any.py --make-files /srv/test-webroot
python3 tools/bench/bench_any.py --port 8080
```

Standardmäßig wird der Server an die Threads 0 und 2 gebunden und der Client an die Threads 1 und 3, was der Messmaschine entspricht. Passen Sie diese Aufteilung an Ihren Prozessor an (`lscpu -e` zeigt die Topologie), mit den Variablen `SRV_CPUS` und `CLI_CPUS`.

Wenn Sie eigene Ergebnisse veröffentlichen, nennen Sie die Maschine, die Versionen, die Prozessoraufteilung und die drei Wiederholungen.

---

## 11. Quellen

Funktionen der anderen Server laut ihrer offiziellen Dokumentation (abgerufen am 26. Oktober 2026).

**nginx**
- [Rate-Limit `limit_req` (gemeinsame Speicherzone)](https://nginx.org/en/docs/http/ngx_http_limit_req_module.html)
- [Vorkomprimierte Dateien `gzip_static`](https://nginx.org/en/docs/http/ngx_http_gzip_static_module.html)
- [Offizielles ACME-Modul `ngx_http_acme_module`](https://nginx.org/en/docs/http/ngx_http_acme_module.html)
- [Lastverteilung (`upstream`)](https://nginx.org/en/docs/http/ngx_http_upstream_module.html)
- [HTTP/3](https://nginx.org/en/docs/http/ngx_http_v3_module.html)
- [ModSecurity-Connector für nginx](https://github.com/owasp-modsecurity/ModSecurity-nginx)

**lighttpd**
- [`server.max-worker`: abgeraten, Zähler pro Prozess für mod_status und mod_evasive](https://redmine.lighttpd.net/projects/lighttpd/wiki/Server_max-workerDetails)
- [mod_magnet (Lua-Skripte)](https://redmine.lighttpd.net/projects/lighttpd/wiki/Docs_ModMagnet)
- [mod_deflate (Komprimierung, Cache)](https://redmine.lighttpd.net/projects/lighttpd/wiki/Mod_deflate)
- [mod_proxy (Lastverteilung, passive Zustandsprüfung, WebSocket)](https://redmine.lighttpd.net/projects/lighttpd/wiki/Docs_ModProxy)
- [mod_evasive (gleichzeitige Verbindungen pro Adresse)](https://redmine.lighttpd.net/projects/lighttpd/wiki/Docs_ModEvasive)

**Caddy**
- [Automatisches HTTPS](https://caddyserver.com/docs/automatic-https)
- [`file_server` und `precompressed`](https://caddyserver.com/docs/caddyfile/directives/file_server)
- [`reverse_proxy` (Strategien, aktive und passive Zustandsprüfung)](https://caddyserver.com/docs/caddyfile/directives/reverse_proxy)
- [Verwaltungs-API](https://caddyserver.com/docs/api)
- [Rate-Limit-Plugin caddy-ratelimit](https://github.com/mholt/caddy-ratelimit)
- [WAF Coraza für Caddy](https://github.com/corazawaf/coraza-caddy)
- [caddy-docker-proxy](https://github.com/lucaslorentz/caddy-docker-proxy)

**Apache HTTP Server**
- [mod_md (ACME)](https://httpd.apache.org/docs/2.4/mod/mod_md.html)
- [mod_proxy_balancer](https://httpd.apache.org/docs/2.4/mod/mod_proxy_balancer.html)
- [mod_proxy_hcheck](https://httpd.apache.org/docs/2.4/mod/mod_proxy_hcheck.html)
- [mod_http2](https://httpd.apache.org/docs/2.4/mod/mod_http2.html)
- [mod_deflate, vorkomprimierte Inhalte](https://httpd.apache.org/docs/2.4/mod/mod_deflate.html)
- [ModSecurity](https://github.com/owasp-modsecurity/ModSecurity)

**Traefik**
- [Middleware `ratelimit` (im Speicher pro Instanz, Redis optional)](https://doc.traefik.io/traefik/reference/routing-configuration/http/middlewares/ratelimit/)
- [ACME](https://doc.traefik.io/traefik/https/acme/)
- [Provider (Docker, Kubernetes…)](https://doc.traefik.io/traefik/providers/overview/)

**Messwerkzeug**
- [oha](https://github.com/hatoo/oha)

---

*Vergleich erstellt von kraynux für omega-serv 2.0.0: Messungen vom 26. Oktober 2026. Die Messungen beziehen sich auf eine einzige Maschine. Messen Sie für jede Kapazitätsentscheidung auf Ihrer eigenen Hardware mit den bereitgestellten Werkzeugen.*
