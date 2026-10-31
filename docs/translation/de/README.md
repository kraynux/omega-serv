<!-- Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE) -->
<div align="center">
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/assets/omega-serv.png" alt="Omega-Serv" width="384">
</div>

# 🔒 OMEGA-SERV

**Eigenständiger, portabler und standardmäßig gehärteter HTTP-Webserver**

> Entwickelt von [kraynux](https://github.com/kraynux) für [Omega-Server](https://kraynux.snake-mackarel.ts.net)   

Offizielle Seite: [OMEGA-SERV](https://kraynux.snake-mackarel.ts.net/omega-serv/translation/de/) &nbsp; Referenz, Verwendung, Hilfe & FAQ: [Vollständiges Handbuch](https://kraynux.snake-mackarel.ts.net/omega-serv/translation/de/guide.html)  
Vorschau: [Screenshots](https://kraynux.snake-mackarel.ts.net/omega-serv/screenshots/) &nbsp; Demonstration [Demo-Server](https://craftdark.snake-mackarel.ts.net) &nbsp; [Webserver-Vergleich/Tests](comparatif-serveurs-web.md)  

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](../../../LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![Lua](https://img.shields.io/badge/Lua-5.4%2B-2C2D72.svg)](https://www.lua.org/)
[![JavaScript](https://img.shields.io/badge/JavaScript-ES2020%2B-F7DF1E.svg)](https://developer.mozilla.org/docs/Web/JavaScript)
[![Platform](https://img.shields.io/badge/Platform-Linux-informational.svg)](https://www.linux.org/)
[![Interface](https://img.shields.io/badge/Interface-CLI%20%2B%20TUI-cyan.svg)](#3-verwendung)
[![Textual](https://img.shields.io/badge/Textual-TUI-5A5AFB.svg)](https://textual.textualize.io/)

🌐 Dokumentation, Exporte und Oberfläche in **17 Sprachen** verfügbar — siehe [Sprachen der Oberfläche](#sprachen-der-oberfläche).  
**Sprachen:**
<img src="https://flagcdn.com/w20/fr.png" alt="France" style="height:14px;"> [Français](../../../README.md) · <img src="https://flagcdn.com/w20/gb.png" alt="English" style="height:14px;"> [English](../en/README.md) · <img src="https://flagcdn.com/w20/es.png" alt="Español" style="height:14px;"> [Español](../es/README.md) · <img src="https://flagcdn.com/w20/br.png" alt="Português (Brasil)" style="height:14px;"> [Português (Brasil)](../pt-BR/README.md) · <img src="https://flagcdn.com/w20/it.png" alt="Italiano" style="height:14px;"> [Italiano](../it/README.md) · <img src="https://flagcdn.com/w20/de.png" alt="Deutsch" style="height:14px;"> [Deutsch](README.md) · <img src="https://flagcdn.com/w20/nl.png" alt="Nederlands" style="height:14px;"> [Nederlands](../nl/README.md) · <img src="https://flagcdn.com/w20/pl.png" alt="Polski" style="height:14px;"> [Polski](../pl/README.md) · <img src="https://flagcdn.com/w20/ru.png" alt="Русский" style="height:14px;"> [Русский](../ru/README.md) · <img src="https://flagcdn.com/w20/cn.png" alt="中文" style="height:14px;"> [中文](../zh-CN/README.md) · <img src="https://flagcdn.com/w20/vn.png" alt="Tiếng Việt" style="height:14px;"> [Tiếng Việt](../vi/README.md) · <img src="https://flagcdn.com/w20/th.png" alt="ไทย" style="height:14px;"> [ไทย](../th/README.md) · <img src="https://flagcdn.com/w20/id.png" alt="Bahasa Indonesia" style="height:14px;"> [Bahasa Indonesia](../id/README.md) · <img src="https://flagcdn.com/w20/jp.png" alt="日本語" style="height:14px;"> [日本語](../ja/README.md) · <img src="https://flagcdn.com/w20/kr.png" alt="한국어" style="height:14px;"> [한국어](../ko/README.md) · <img src="https://flagcdn.com/w20/in.png" alt="हिन्दी" style="height:14px;"> [हिन्दी](../hi/README.md) · <img src="https://flagcdn.com/w20/ae.png" alt="العربية" style="height:14px;"> [العربية](../ar/README.md)

---

**OMEGA-SERV** ist ein in reinem Python geschriebener HTTP/1.1-Server (für den Serverkern ausschließlich die Standardbibliothek), gedacht für statische Inhalte und optional PHP-FPM, mit einer nicht abschaltbaren Protokollhärtung und Sicherheitsmodulen (WAF, TLS, Authentifizierung), die sich aufschichten lassen, statt aufgezwungen zu werden. Siebtes Werkzeug der `omega-`-Suite, aber bewusst **außerhalb der künftigen `omega-suite`-Integration** (es wirkt auf die lokale Maschine, die es beherbergt, nicht auf entfernte Ziele — gleiche Familie wie `omega-fire`); aufgebaut nach Clean Architecture, wobei `bootstrap/` als Kompositionswurzel dient.

## 1. Vision und Umfang

Die erklärte Priorität ist **zuerst die Robustheit/Sicherheit des HTTP-Kerns** — WAF und TLS sind optionale Module, die darüber gelegt werden, niemals Voraussetzungen. Ein Server, der nur eine Sache tut (Dateien ausliefern, eventuell PHP), diese aber richtig, mit einer echten, nicht umgehbaren Protokollhärtung — statt eines Servers, der vieles nur halb tut.

### Was OMEGA-SERV tut

- Liefert statische Inhalte aus (Dateien, optionale Verzeichnisliste, Aliase, Weiterleitungen, Rewrites, Cache) mit sicherer Pfadauflösung (Traversal, Doppelkodierung, symbolische Links). Große Dateien werden blockweise direkt von der Festplatte gesendet, nie in den Speicher geladen; jede Datei trägt ein `ETag` und ein `Last-Modified` (Neuladen = leere 304-Antwort) und akzeptiert Teilanfragen `Range` (fortgesetzte Downloads, Video); Bilder, Medien, Schriften, CSS und JS erhalten ein Standard-`Cache-Control`, änderbar im Bildschirm Cache. Vorkomprimierte Textdateien: Liegt `site.css.br` oder `site.css.gz` neben `site.css` (erstellt mit `brotli -k site.css` oder `gzip -k site.css`) und akzeptiert der Browser sie, wird sie stattdessen gesendet, nie eine ältere Version als das Original.
- Härtet das HTTP-Protokoll standardmäßig, ohne Option zum Abschalten: explizit erlaubte Methoden, Validierung des `Host`-Headers, Ablehnung der Mehrdeutigkeit `Content-Length`/`Transfer-Encoding`, nicht umgehbare Sicherheits-Header und Basis-CSP.
- Optional: WAF-Filterung (Signaturen, Ratenbegrenzung, Sperrliste), direktes TLS (selbstsigniertes Zertifikat, von einer lokalen CA signiert oder öffentlich über Let's Encrypt/Certbot mit automatischer Erneuerung — siehe §9), HTTP-Basic-Authentifizierung pro Zone, PHP über FastCGI/PHP-FPM, abgeschottete Upload-Zonen.
- « Boost »-Modus: mehrere Serverprozesse, höchstens einer pro auf der Maschine verfügbarer CPU (Bildschirm Widerstandsfähigkeit und Grenzen); die Sicherheitszähler (Ratenbegrenzung, Wiederholungsregel) werden zwischen ihnen geteilt und bleiben exakt.
- Auditiert seine eigene Konfiguration (`audit security`) und installiert sich als Systemdienst (systemd/OpenRC/runit).
- Durchgängig skriptbare, nicht interaktive CLI **und interaktive Oberfläche (Textual)**, die exakt dieselben Anwendungsfälle abbildet — siehe §3. Die Roadmap der Oberfläche (`OMEGA-SERV_PLAN-DETAILLE_INTERFACE.md`, §12) ist **vollständig ausgeliefert**: Fähigkeitsregister, Profile/Optionen, detaillierte Konfiguration (Aliase/Weiterleitungen/Rewrites/FastCGI/Verzeichnisliste/Authentifizierung/Cache/WAF/vertrauenswürdige Proxys/ausgehender Reverse Proxy/TLS), Log-Verwaltung (Bibliothek/Favoriten, 3 Viewer — einfach/klassisch/zusammengeführtes lnav —, IP ansehen und bearbeiten, entfernte SSH-Quellen, Rotation/Sicherung/Automatisierung/Wiederherstellung/Bereinigung/Export), Systemdienst, Multi-Instanz (Register, Erstellung), Prüfung/Simulation/Audit, Sicherung/Wiederherstellung der Konfiguration, Ersteinrichtungs-Assistent, Anwendungseinstellungen (Theme, Rendering-Profil, Pfade für Exporte/Screenshots), kontextbezogenes Hilfehandbuch (Seite pro Bildschirm mit konkreten Beispielen, FAQ, HTML-Export, per Test verifizierte vollständige Abdeckung), systematischer Hinweis auf Neuladen/Neustart nach jedem Speichern, vollständige Konfiguration von Active Defense ohne manuelle Dateibearbeitung.

### Was OMEGA-SERV nicht tut

- Reines CGI (aus dem Umfang von V1 entfernt — nur FastCGI/PHP-FPM wird unterstützt).
- Gegenseitige TLS-Authentifizierung (mTLS), OCSP-Stapling — außerhalb des Umfangs von V1, siehe §15. (ACME/Let's Encrypt über Certbot ist verfügbar, siehe §9c/9d.)
- Zwischen Prozessen geteilter HTTP-Cache.
- Scan/Audit eines entfernten Ziels (dafür siehe `omega-check`/`omega-scan`/`omega-deep` — Omega-serv auditiert sich selbst, niemals Dritte).

### OMEGA-SERV im Vergleich mit den Webservern am Markt

Siehe [Messungen & Vergleich](comparatif-serveurs-web.md)  
Gemessener Vergleich zwischen: [Nginx](https://nginx.org/) · [Lighttpd](https://www.lighttpd.net/) · [Caddy](https://caddyserver.com/) · [Apache](https://www.apache.org) · [Traefik](https://traefik.io/) · [Omega-Serv](https://kraynux.snake-mackarel.ts.net/omega-serv/translation/de/)

### Nutzungshinweis

Omega-serv **verweigert den Start als root**. In keinem mitgelieferten Profil, auch nicht `hardened`, ist ein Sicherheitsmodul (WAF, TLS, Authentifizierung) standardmäßig aktiviert — sie zu aktivieren ist immer ein expliziter Schritt (`config enable-tls`, `option enable waf`...). Das Profil `hardened` selbst empfiehlt für eine echte Internet-Exposition einen Reverse Proxy, statt ihn zu ersetzen.

## 2. Installation

### Voraussetzungen

- Python 3.10+
- `openssl` (Binärprogramm, keine Python-Bibliothek) für alles rund um TLS-Zertifikate — die übrigen Funktionen arbeiten auch ohne.

### Download

Archiv der neuesten Version und SHA-256-Prüfsummen jeder Version: [omega-serv-2.0.1.tar.gz](https://kraynux.snake-mackarel.ts.net/omega-serv/download/omega-serv-2.0.1.tar.gz) · [sha.txt](https://kraynux.snake-mackarel.ts.net/omega-serv/download/sha.txt)

```bash
wget https://kraynux.snake-mackarel.ts.net/omega-serv/download/omega-serv-2.0.1.tar.gz
wget https://kraynux.snake-mackarel.ts.net/omega-serv/download/sha.txt
sha256sum -c --ignore-missing sha.txt
```

### Installation

> ⚠️ **Aktualisieren Sie eine bestehende Installation?** Der folgende Befehl **überspringt das Entpacken stillschweigend**, wenn `omega-serv/` bereits existiert (er nimmt an, es handle sich um eine abgebrochene Erstinstallation, nicht um ein Update) — Sie würden die Abhängigkeiten dann auf dem **alten, unveränderten Code** neu installieren, ohne die geringste Fehlermeldung. Verwenden Sie stattdessen den Abschnitt [Aktualisierung](#aktualisierung) weiter unten.

```bash
[ -d omega-serv ] && echo "ℹ️ Hier bereits entpackt, Schritt übersprungen." || tar -xzf omega-serv-2.0.1.tar.gz
cd omega-serv/
chmod +x install.sh
./install.sh
```

`install.sh`:

1. Erstellt die virtuelle Umgebung `.venv`, falls sie noch nicht existiert.
2. Installiert das Paket (`pip install -e .`) — **keine externe Abhängigkeit** (siehe §6).
3. Macht `omega-serv.sh` und `install.sh` ausführbar.
4. Fügt den Alias `serv` zu `~/.bashrc` und `~/.zshrc` hinzu (ohne Duplikat, falls bereits vorhanden).

### Aktualisierung

Wenn `omega-serv/` bereits existiert (frühere Installation), **starten Sie `tar` niemals aus diesem Ordner heraus**: Es würde versuchen, ein verschachteltes `omega-serv/omega-serv/` anzulegen, und scheitern. Anders als bei omega-fire verändert `install.sh` niemals die Berechtigungen des Ordners (kein Schritt verlangt dort `sudo`) — es besteht hier also kein Risiko eines Ordners, der `root` gehört; ein Entpacken direkt über die bestehende Installation ist sicher.

```bash
# Aus dem ÜBERGEORDNETEN Ordner von omega-serv/ (niemals von innen)
tar -xzf omega-serv-2.0.1.tar.gz
cd omega-serv/
./install.sh
```

Das Archiv schließt bewusst den gesamten laufenden Zustand aus (`var/db/`, `var/log/`, `var/backups/`, `secure/secrets/`, `secure/certificates/*.key`, `config/omega-serve.json`, **`webroot/` — die tatsächlich ausgelieferte Website**...) — ein Entpacken darüber berührt niemals die vorhandenen Daten, Zertifikate, Einstellungen oder ausgelieferten Inhalte, nur der Anwendungscode wird ersetzt. `install.sh` verwendet die bestehende `.venv` weiter und installiert die Abhängigkeiten einfach darüber neu.

Seit dem 2026-10-18 sind `var/` und `secure/auth/` überhaupt nicht mehr im Archiv enthalten, nicht einmal leer: Ein Entpacken darüber setzt ihre Rechte (geteilt mit dem Konto des systemd-Dienstes) daher nicht mehr zurück — nach einem Update ist « Dienst → Rechte erneut anwenden » nicht mehr nötig. `install.sh` legt diese Ordner an, falls sie fehlen, ohne jemals vorhandene anzutasten.

> ⚠️ **Wenn bereits ein Dienst läuft, reicht der obige Schritt nicht aus.** Er ersetzt den Code auf der Festplatte, aber der bereits laufende Prozess arbeitet weiter mit dem alten, im Speicher geladenen Code — danach ist systematisch ein **vollständiger Neustart** nötig:
> ```bash
> sudo systemctl restart <dienstname>
> ```
> **Niemals ein einfaches Neuladen** (`systemctl reload` oder Bildschirm DIENST → *Neu laden*): Dieses liest nur bestimmte Konfigurationsoptionen neu ein (WAF-Regeln, Authentifizierungszonen...), **niemals den Python-Code selbst**. Ein `systemctl status <dienstname>`, das ein Startdatum vor Ihrem Update anzeigt, bestätigt, dass er noch mit dem alten Code läuft. Wenn Sie immer durch Überschreiben desselben Ordners aktualisieren (Standardfall oben), ist dieser Neustart der einzige fehlende Schritt — eine Neuinstallation des Dienstes ist nicht erforderlich.

> ⚠️ **Wenn der Dienst danach in einer Neustartschleife hängt** (`systemctl status` wechselt zwischen aktiv/inaktiv, `journalctl -u <dienstname>` zeigt einen `PermissionError` beim Schreiben einer Datei unter `var/`): Das Entpacken mit `tar` stellt die Ordnerberechtigungen so wieder her, wie sie im Archiv erfasst wurden, was die bei der Erstinstallation für das dedizierte Systemkonto eingerichtete Rechtefreigabe löschen kann — auch wenn `install.sh` selbst sie nie anrührt. Keine Neuinstallation der Unit nötig: Bildschirm DIENST → **Rechte reparieren** (wendet die Freigabe auf `var/` und `secure/auth/` erneut an, ohne die systemd-Unit anzutasten).

### Abhängigkeiten

Der Serverkern (HTTP/1.1-Parser, FastCGI-Client, Passwort-Hashing über `hashlib.scrypt`) bleibt reines Python/Stdlib, und alles rund um TLS-Zertifikate läuft über das Binärprogramm `openssl` als Unterprozess statt über eine Python-Kryptobibliothek — **keine externe Abhängigkeit dafür**. Nur die interaktive Oberfläche (§3) bringt welche mit: `omega-lib` (Themes, Terminalerkennung — gemeinsame Bibliothek der Suite, nicht auf PyPI veröffentlicht, im verteilbaren Archiv mitgeliefert), `textual` und `pyte` (Terminalemulation für die in die Oberfläche integrierte, zusammengeführte `lnav`-Darstellung), `jinja2` (HTML-Exporte mit Theme) und `psutil` (Bildschirm Status & Ressourcen — CPU/RAM/Festplatte/Netzwerk). Optionale Entwicklungs-/Testabhängigkeit (`pip install -e ".[test]"`): `hypothesis` (Eigenschaftstests des HTTP-Parsers und des Pfadauflösers, niemals in Produktion). Qualitätswerkzeuge (`pip install -e ".[dev]"`): `pytest`, `ruff`, `mypy`, `import-linter`. Zusätzliches optionales Extra (`pip install -e ".[magnet]"`): `lupa` (eingebettete Lua-Anbindung, vorkompiliertes Wheel, kein System-`lua`-Interpreter nötig), ausschließlich für das ergänzende WAF-Skript « magnet » (§7) — niemals standardmäßig installiert; sein Fehlen wird gemeldet (Fähigkeit `waf-magnet`, Bildschirm **Fähigkeiten**), mit dem genauen Installationsbefehl, ohne den Rest des Servers zu blockieren.

### Empfohlene optionale Werkzeuge

Die Oberfläche arbeitet im eingeschränkten Modus, wenn diese Werkzeuge fehlen:

- `openssl` — nötig für alles rund um TLS-Zertifikate (selbstsigniert, lokale CA, Import); ohne es schlagen die Befehle `certs *` fehl, der Rest des Servers funktioniert aber normal (siehe §9).
- `certbot` — nur für den **Let's-Encrypt**-Assistenten und dessen automatische Erneuerung nötig (§9c/9d); selbstsigniertes TLS/lokale CA benötigen es nicht.
- `lnav` — erweiterte, zusammengeführte Log-Analyse im Bildschirm **Log-Verwaltung** (§3); klare, eindeutige Fehlermeldung, wenn das Programm nicht gefunden wird, kein Absturz, der Rest des Bildschirms (ansehen/verfolgen/Rotation/Statistiken) funktioniert auch ohne normal.
- `scp` (Paket `openssh`/`openssh-clients`, fast immer bereits vorhanden) — nur für die **Entfernten Quellen (SSH)** nötig (§13a); ohne es schlägt der Abruf mit einer klaren Meldung fehl, der Rest der Bibliothek funktioniert normal.
- `python-psutil` (Systempaket, entspricht `psutil` von PyPI) — wird in jedem Fall automatisch von `pip install -e .` installiert (Pflichtabhängigkeit des Pakets, der Bildschirm **Status & Ressourcen** braucht es immer), aber eine Vorinstallation über den Paketmanager erspart `pip` das lokale Kompilieren des Wheels.

```bash
# Arch Linux und Derivate
sudo pacman -S openssl certbot lnav python-psutil openssh

# Debian/Ubuntu und Derivate
sudo apt install openssl certbot lnav python3-psutil openssh-client

# Fedora
sudo dnf install openssl certbot lnav python3-psutil openssh-clients
```

## 3. Verwendung

Zwei funktional streng gleichwertige Oberflächen, niemals duplizierte Logik zwischen beiden: nicht interaktive CLI (skriptbar, unten verwendet) und interaktive Textual-Oberfläche (Menüs, Formulare, Tabellen) — jede Aktion der einen existiert auf CLI-Seite, die Oberfläche bildet nur dieselben Anwendungsfälle ab.

### Interaktiver Modus (TUI)

Empfohlen für die tägliche Nutzung — ohne Argument gestartet:

```bash
./omega-serv.sh
```
wenn Sie den Alias angelegt haben, tippen Sie einfach `serv` im Terminal:
```bash
serv
```

### Sprachen der Oberfläche

17 Sprachen: Französisch, Englisch, Spanisch, Portugiesisch (Brasilien), Italienisch, Deutsch, Niederländisch, Polnisch, Russisch, Chinesisch, Vietnamesisch, Thailändisch, Indonesisch, Japanisch, Koreanisch, Hindi, Arabisch. Auswahl in den Einstellungen (Taste `o`, « Langue / Language », Bezeichnung wird nie übersetzt) oder einmalig mit `OMEGA_SERV_LANG=en serv`. In der Linux-Textkonsole (TTY) werden Sprachen, deren Schrift in den Konsolenschriftarten nicht existiert (Vietnamesisch, Chinesisch, Thailändisch, Japanisch, Koreanisch, Hindi, Arabisch), für die Sitzung auf Englisch angezeigt. Auf Hindi verschieben Terminals, die verbundene Buchstaben selbst setzen (Kitty, Ghostty, Konsole), Rahmen und Spalten, je nach Schriftart unterschiedlich: beim Start erscheint eine Warnung; Terminator, GNOME Terminal, Xfce Terminal und Alacritty zeigen Hindi ausgerichtet an. Zwei separate Einstellungen: die **Sprache der Besucherseiten** (Fehlerseiten, Verzeichnisliste — Bildschirm Fehlerseiten, standardmäßig Französisch) und die **Sprache der Exporte** (HTML und Vorfallbericht — Einstellungen, standardmäßig « Wie die Oberfläche »). Die Serverprotokolle (`journalctl`) bleiben auf Französisch.

### Allgemeiner Ablauf

Startbildschirm (Splash, schließt sich per Taste oder Klick) → Hauptmenü (Ersteinrichtung / Fähigkeitsregister / Profile / Detaillierte Konfiguration / Aktive Sicherheit / Log-Verwaltung / Dienst / Multi-Instanz / Status & Ressourcen / Audit / Sicherung) → Auswahl eines Bereichs und dann einer Aktion, wobei jedes Formular seine Pflichtfelder validiert, bevor es weitergeht → explizite Bestätigung vor jeder sensiblen oder destruktiven Operation (Neustart, Löschen, Wiederherstellen...) → systematischer Hinweis auf den nächsten Schritt (automatisches Neuladen im laufenden Betrieb oder Bestätigung eines vollständigen Neustarts) nach jedem Speichern, das eine bereits ausgelieferte Konfiguration ändert. Die Anpassung an das Terminal (Farben, Größe, strukturelle Abstufung des Rendering-Profils) erfolgt automatisch und ohne manuelles Flag — siehe §4.

#### Tastenkürzel (interaktive Oberfläche)

| Taste | Aktion |
|---|---|
| `↑` / `↓` | Zwischen den Elementen eines Bildschirms navigieren |
| `Tab` / `Umschalt+Tab` | Zwischen den Feldern eines Formulars navigieren |
| `Esc` | Zurück zum vorherigen Bildschirm (Bestätigung zum Beenden auf dem Startbildschirm) |
| `t` | Nächstes Theme (sofort angewendet, ohne Bestätigung) |
| `r` | Terminalerkennung aktualisieren |
| `F1` | Hilfe zum aktiven Bildschirm (kontextbezogene Seite — siehe „Hilfehandbuch“ unten) |
| `a` | Vollständiges Hilfehandbuch (navigierbares Menü + FAQ) |
| `o` | Anwendungseinstellungen (Theme, Rendering-Profil, Pfade für Exporte/Screenshots — siehe unten) |
| `q` | Beenden (mit Bestätigung) |
| `Ctrl+P` | Befehlspalette (Theme, Screenshot, Optionen...) |

> **Ausnahme — Listeneditor (WAF → Custom)**: keine Tastenkürzel, alles geschieht mit der Maus; die Tastatur dient nur der Eingabe (Zeichen, Eingabe, Pfeiltasten, Pos1/Ende, Bild auf/ab, Rücktaste, Entf). `Esc`, `F1` und `Ctrl+P` sind dort inaktiv (Schaltfläche **Hilfe**); nur `Ctrl+Q` bleibt aktiv, mit Bestätigung bei ungespeicherten Änderungen.

#### Hilfehandbuch (Tasten `F1`/`a`)

Integriertes Hilfesystem, niemals bloß statischer Text: Jeder dokumentierte Bildschirm (Seite mit Definition/auszufüllenden Feldern mit konkreten Beispielen/ausgelöster Aktion/Reaktion — Neuladen, Neustart oder keine) ist direkt von ihm aus über `F1` erreichbar; die Taste `a` öffnet das vollständige Menü (Baumstruktur identisch mit der tatsächlichen Navigation der Anwendung) mit Zugang zur FAQ (in der Praxis aufgetretene Fallstricke, z. B. Angriffsklassen von Active Defense, Berechtigungen bei geteiltem Dienst) und einem eigenständigen HTML-Export (aktives Theme bleibt erhalten) des gesamten Handbuchs. Rückfall auf einen generischen Referenzbildschirm, solange es noch keine spezifische Seite gibt — die Abdeckung ist derzeit vollständig und per Test verifiziert.

#### Hauptmenü (interaktive Oberfläche)

- **Ersteinrichtung** — geführter Ablauf in 8 Schritten (Willkommen → Fähigkeiten nur lesend → Profilwahl → Bind/Port → optionales TLS → Prüfung → Zusammenfassung + Schreiben → Angebot zur Dienstinstallation); erzeugt eine vollständige Konfiguration und bringt den Server in Gang, ohne die CLI kennen zu müssen.
- **Fähigkeitsregister** — schreibgeschützte Systemsonde (Init-System, konfigurierter Port bereits belegt oder nicht, `openssl`/`logrotate`/`tailscale`/`lnav` vorhanden, Festplattenplatz, Deskriptorgrenze...), JSON/HTML-Export.
- **Profile** — derselbe Anwendungsfall wie `profile` in der CLI (§5), Diff wird vor dem Schreiben immer angezeigt.
- **Detaillierte Konfiguration des Servers** — vollständiges CRUD für Aliase/Weiterleitungen/Rewrites/Verzeichnisliste/vertrauenswürdige Proxys/ausgehenden Reverse Proxy/FastCGI/Cache/Authentifizierung/Zugriffskontrolle/Fehlerseiten, dazu das Untermenü **TLS** (Status, selbstsignierte Erzeugung, Assistent lokale CA, Let's-Encrypt/Certbot-Assistent, automatische Erneuerung, Widerruf, aktivieren/deaktivieren — siehe §9); ein zweiter Rahmen **OPTIONEN UND PRÜFUNG** bündelt dort die Verknüpfungen zu **Optionen** (`option` CLI, §7) und **Konfiguration prüfen** (`config check` CLI, §10) — derselbe Ablauf wie Einstellungen anpassen und dann prüfen; diese beiden Bildschirme sind nicht mehr direkt vom Hauptmenü aus erreichbar. Der WAF wohnt nicht mehr hier (siehe „Aktive Sicherheit“ unten): Er zeigt vor allem fortlaufend wechselnden Betriebszustand, kein einfaches statisches Konfigurationsformular. Jedes Speichern nennt systematisch den nächsten Schritt: automatisches und stilles Neuladen im laufenden Betrieb, wenn ein Dienst aktiv ist (Verzeichnisliste, Zugriff, Aliase/Weiterleitungen/Rewrites, Cache, Fehlerseiten, vertrauenswürdige Proxys, Reverse-Proxy-/FastCGI-Zonen, Benutzer/Authentifizierungszonen), oder explizite Bestätigung eines vollständigen Neustarts, wenn die Änderung den Listen-Socket, TLS oder Active Defense betrifft — kein Bildschirm lässt mehr raten, ob der Server neu gestartet werden muss.
- **Aktive Sicherheit** — ein einziger Bildschirm mit zwei nebeneinander liegenden Blöcken: **Active Defense** (Status, Verfolgte Bedrohungen mit Punktzahl/Stufe, Vorfälle mit Chronologie/IoC-Export/Bericht, Deception-Zuweisungen, Entscheidung im Dry-Run simulieren, **Einstellungen** — vollständige Konfiguration, ohne jemals `config/omega-serve.json` von Hand zu bearbeiten, siehe §11) und **WAF** (Status, Module — Modus/Regelpakete/Sperrliste, Anfrage testen, Custom — Erstellen eigener Regeln und Laden mausbearbeitbarer Pfad-/Stichwortlisten (siehe §11b), Magnet — ein externes `mod_magnet`-Skript importieren, mit Kompatibilitätsprüfung vor der Aktivierung) — siehe §11.
- **Log-Verwaltung** — Menü in zwei Spalten. Spalte **Bibliothek**: zentraler Hub, der jedes zu bearbeitende Log referenziert (manuelle Befüllung, ein Klick fügt automatisch die instanzeigenen Logs hinzu — access/error/nativer WAF, + Magnet-Skript §7, falls aktiv —, oder eine über SSH abgerufene **entfernte Quelle**, siehe unten); **Favoriten** (unter einem Namen gespeicherte Kombination aus Logs + Viewer, Direktstart); **Logs ansehen** mit 3 Viewern zur Wahl je nach Anzahl der ausgewählten Logs — Einfach (Live-tail + generische Statistiken zu IPs/Fehlern/HTTP-Codes für jedes Format), Klassisch (Lesen + Verfolgen), zusammengeführtes `lnav` (echte Terminaldarstellung in der Oberfläche, Magnet-Logs automatisch enthalten + manuelle, **angeheftete** Pfade, um sie zwischen Sitzungen zu behalten); **IP ansehen und bearbeiten** (Top-IPs aus einem oder mehreren gewählten Logs, Zeitraum 24h/7T/30T/alles, Entfernen einer IP). Spalte **Wartung** (unverändert): manuelle oder automatische Rotation/Archivierung ab einer Größenschwelle, sofortige Sicherung, Einrichtung/Verwaltung geplanter Automatisierungen (deklarativ — siehe Hinweis unten), Archiv wiederherstellen/bereinigen, Export der Liste.
- **Dienst** — dieselben Aktionen wie `service` in der CLI (§12), punktuelle `sudo`-Erhöhung pro Aktion, niemals die ganze Anwendung als root gestartet.
- **Multi-Instanz** — globales Register (`~/.config/omega-serv/instances.json`, außerhalb jedes Projektverzeichnisses) der auf der Maschine bekannten Installationen, mit dem systemd-Status jeder einzelnen; Erstellung einer neuen Instanz (Kopie des Verzeichnisbaums, eigene virtuelle Umgebung und Abhängigkeiten, frische Konfiguration mit eigenem Port, Prüfung auf Verschachtelung und Portkonflikt) direkt aus der Oberfläche. Schaltfläche bei einer Einzelinstallation praktisch unsichtbar (die Bezeichnung „Multi-Instanz“ wird ab 2 bekannten zu „Instanzen (N)“); vollständiger Wechsel zu einer anderen Instanz (`os.execv`, explizite Bestätigung, eigener Splash, der den Wechsel beim Neustart ankündigt); vollständige Deinstallation einer Instanz (Entfernen der Unit, des dedizierten Systemkontos, falls von keiner anderen Instanz mehr genutzt, und optionales Löschen des Verzeichnisses, niemals standardmäßig).
- **Status & Ressourcen** — Überblick auf einen Blick, alle 2 Sekunden aktualisiert: Serverzustand (Prozess/PID, Status des Systemdienstes, Profil/aktive Optionen/TLS/Port), Live-Fluss des Zugriffslogs (Durchsatz, Verteilung nach Statuscode, eindeutige IPs, Fehlerquote), Systemressourcen (CPU/RAM/Festplatte/Swap/Last/Netzwerk, über `psutil`); enthält auch die Verknüpfung **Anfrage simulieren** (derselbe Anwendungsfall wie der entsprechende CLI-Befehl, §10).
- **Sicherheitsaudit** — derselbe Anwendungsfall wie der entsprechende CLI-Befehl (§10).
- **Sicherung der Konfiguration** — tar.gz-Archiv der Konfigurationsdatei und, auf ausdrücklichen Wunsch, der WAF-Regeln/Authentifizierungszonen/Zertifikate (Bestätigung Pflicht, sobald echte Geheimnisse enthalten sind)/Active-Defense-Datenbank, Wiederherstellung, Liste, Löschen.

> Hinweis zu geplanten Rotationsautomatisierungen: Sie werden gespeichert (Häufigkeit + Ziel-Log), aber **nichts führt sie automatisch aus** — weder auf Seiten der Oberfläche noch im Hintergrund. Das ist eine bewusste Entscheidung für Gleichheit mit dem entsprechenden Bildschirm von `omega-fire`, das dasselbe deklarative Verhalten hat. Eine echte periodische Ausführung (systemd-Timer, Hintergrundaufgabe) muss bei bestätigtem Bedarf separat gebaut werden.

#### Anwendungseinstellungen (Taste `o` oder Befehlspalette)

Nur Oberflächeneinstellungen — niemals mit `config/omega-serve.json` (Serverkonfiguration) zu verwechseln: aktives Theme, Rendering-Profil (`complete`/`standard`/`reduced`/`mono`, Neustart erforderlich), Pfad der Exporte (standardmäßig `var/exports/`), Pfad der Screenshots (standardmäßig `var/screenshots/`), Leeren des einen oder anderen Ordners (Bestätigung Pflicht).

```bash
# Server starten (Vordergrund, SIGTERM = sauberes Beenden mit Karenzzeit, SIGHUP = Neuladen im laufenden Betrieb WAF/Auth)
./omega-serv.sh serve

# Konfiguration
./omega-serv.sh config init                # erzeugt config/omega-serve.json (sichere Standardwerte)
./omega-serv.sh config check                # prueft ohne Start (dieselben Sperren wie beim Start)
./omega-serv.sh config show
./omega-serv.sh config enable-tls --cert ... --key ... --mode direct
./omega-serv.sh config disable-tls

# Profile (minimal / standard / hardened / development)
./omega-serv.sh profile list
./omega-serv.sh profile show hardened
./omega-serv.sh profile apply hardened --dry-run   # Diff vor dem Anwenden, immer

# Optionen (aliases, redirects, rewrites, dirlisting, cache, waf, upload, fastcgi, reverse_proxy...)
./omega-serv.sh option list
./omega-serv.sh option enable waf
./omega-serv.sh option disable waf

# Eine Anfrage simulieren, ohne den Server zu starten (nuetzlich, um eine Regel vor der Aktivierung zu pruefen)
./omega-serv.sh simulate-request GET /index.html

# WAF (funktioniert auch bei deaktivierter Option, ueber implizites --force)
./omega-serv.sh waf test --method GET --path /admin --remote-ip 203.0.113.1
./omega-serv.sh blocklist list
./omega-serv.sh blocklist add --network 203.0.113.0/24 --reason "Scan erkannt" --duration-seconds 3600
./omega-serv.sh blocklist remove --network 203.0.113.0/24

# Active Defense (Deception + Kriegsmodus, Option "active_defense" - siehe §11)
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

# TLS-Zertifikate - selbstsigniert (9a)
./omega-serv.sh certs generate-self-signed --cn localhost --san-dns localhost --san-ip 127.0.0.1
./omega-serv.sh certs show
./omega-serv.sh certs check-expiry --warn-days 30

# TLS-Zertifikate - lokale CA (9b)
./omega-serv.sh certs generate-ca --cn "Meine lokale CA" --days 3650
./omega-serv.sh certs generate-csr --cn server.local --san-dns server.local --key-out server.key --csr-out server.csr
./omega-serv.sh certs sign-csr --csr server.csr --ca-key secure/certificates/ca/root-ca.key --ca-cert secure/certificates/ca/root-ca.pem --out server.pem --fullchain-out fullchain.pem
./omega-serv.sh certs revoke --cert server.pem --ca-key secure/certificates/ca/root-ca.key --ca-cert secure/certificates/ca/root-ca.pem

# TLS-Zertifikate - Import (9c, z. B. aus einem Certbot-Hook)
./omega-serv.sh certs import --key privkey.pem --cert fullchain.pem

# HTTP-Basic-Authentifizierung
./omega-serv.sh auth add-user --username alice
./omega-serv.sh auth create-zone --url-prefix /admin/ --allowed-users alice
./omega-serv.sh auth list

# Sicherheitsaudit (blockiert nie, informativ)
./omega-serv.sh audit security --format text --min-severity medium

# Sicherung der Konfiguration (Konfiguration immer enthalten; echte Geheimnisse
# standardmaessig nie verschluesselt, --confirm-secrets Pflicht, um sie einzuschliessen)
./omega-serv.sh config backup --description "vor der Migration"
./omega-serv.sh config backup --include-auth --include-certificates --confirm-secrets
./omega-serv.sh config backup --include-active-defense --description "Bedrohungen/Vorfaelle"
./omega-serv.sh config list-backups
./omega-serv.sh config restore --snapshot-id snapshot_20260908_170003_762484

# Systemdienst (systemd/OpenRC/runit, automatische Erkennung)
./omega-serv.sh service install --user omega-serv --group omega-serv
./omega-serv.sh service start
./omega-serv.sh service status
```

### Wichtige Exit-Codes

| Befehl | Code | Bedeutung |
|---|---:|---|
| `audit security` | `0` | Nichts Ernstes (kein `CRITICAL`/`HIGH`) |
| `audit security` | `1` | Mindestens ein Befund `CRITICAL` |
| `audit security` | `2` | Mindestens ein `HIGH` ohne `CRITICAL` |
| `audit security` | `3` | Ausführungsfehler (Konfiguration nicht gefunden...) |
| `certs check-expiry` | `1` | Zertifikat abgelaufen |
| jeder andere Befehl | `0`/`1` | Erfolg / Validierungsfehler |

## 4. Terminal-Kompatibilität

Die interaktive Oberfläche ([Textual](https://textual.textualize.io/), aufgebaut auf [Rich](https://rich.readthedocs.io/)) erkennt automatisch die Fähigkeiten des Terminals (Emulator, Größe) und passt ihr strukturelles Stylesheet entsprechend an (`complete`/`standard`/`reduced`/`mono`), ohne manuelles Flag. Der CLI-Modus bleibt immer einfacher Text, unabhängig vom Terminal. Von der gesamten `omega-`-Suite geteilte Richtlinie (`omega-lib`, `terminal/policies.py`) — identisch mit der von `omega-check`/`omega-fire`.

### Profil je nach erkanntem Emulator

| Emulator | Anfangsprofil |
|---|---|
| Ghostty, Alacritty, WezTerm, Kitty | `complete` |
| Konsole, GNOME Terminal, Terminator, Xfce4 Terminal | `standard` |
| xterm, urxvt, modernes SSH | `reduced` |
| Linux-TTY, altes SSH | `mono` |
| Nicht erkannter Emulator | `reduced` (Standard-Rückfall) |

### Profil je nach Terminalgröße

| Mindestgröße (Spalten × Zeilen) | Profil-Obergrenze |
|---|---|
| 120 × 32 | `complete` |
| 100 × 28 | `standard` |
| 80 × 24 | `reduced` |
| darunter | `mono` |

Das endgültige Profil ist **das restriktivere von beiden** (Emulator und Größe) — ein Ghostty im Vollbild, das auf 70 Spalten verkleinert wird, fällt auf `mono` zurück, auch wenn sein Emulator `complete` erlauben würde. Live aktualisierbar mit der Taste `r` oder manuell überschreibbar in den Anwendungseinstellungen (Taste `o`, §3).

## 5. Profile

| Profil | Vorgesehene Nutzung |
|---|---|
| `minimal` | Demonstration/einfach lokal: nur statisch, keine Option aktiviert |
| `standard` | Statische Website oder kleine Produktion: übliche Header, Basis-CSP, Verzeichnisliste/CGI/FastCGI deaktiviert |
| `hardened` | Exposition mit minimalen Rechten: standardmäßig lokales Bind (Reverse Proxy für Internet empfohlen), Methoden auf GET/HEAD beschränkt, strenge CSP, Anti-Slowloris — der WAF wird **niemals** automatisch aktiviert, auch hier nicht |
| `development` | Nur lokale Entwicklung, niemals als internettauglich dargestellt: Loopback-Bind Pflicht, CSP im Report-only-Modus, ausführliche Fehlerseiten |

Reihenfolge der Konfigurationszusammenführung: integrierte sichere Werte → gewähltes Profil → aktuell aktive Optionen bleiben erhalten (überstehen einen Profilwechsel) → explizites Benutzer-Overlay. Vor dem Schreiben wird immer ein vollständiger Diff angezeigt (`profile apply`).

## 6. Architektur

Clean Architecture (`core / domain / ports / application / infrastructure / interfaces / bootstrap`) — `bootstrap/` ist die Kompositionswurzel (Entsprechung von `app/` der anderen Werkzeuge der Suite). Eine bewusste Besonderheit dieses Projekts, durch `import-linter` geprüft statt nur angenommen: `application/server/start_server.py` (und `validate_config.py`, `run_audit.py`) spielen die Rolle einer **von der tatsächlichen Konfiguration abhängigen Fabrik** (welcher Dienstmanager, WAF aktivieren oder nicht...) und instanziieren konkrete `infrastructure/`-Adapter direkt — anders als beim strengeren Muster von CHECK/TRACK, wo `application/` nur `ports/` nutzt. Die einzige wirklich durchgesetzte universelle Regel: `domain/`/`core/` hängen niemals von äußeren Schichten ab.

```text
src/omega_serv/
├── core/            Querschnittsvokabular (platform_info, Konstanten)
├── domain/           Reine Fachlogik (HTTP, Konfiguration, Sicherheit WAF/TLS/Auth/Audit, Routing)
├── ports/            Vertraege (Protocol), die die Anwendung erwartet
├── application/      Anwendungsfaelle - manche Funktionen (build_server...) setzen auch konkrete Adapter zusammen (siehe oben)
├── infrastructure/    Echte Implementierungen (asyncio, openssl als Unterprozess, systemd/OpenRC/runit, Dateien)
├── interfaces/cli/    Nicht interaktive argparse-CLI
├── interfaces/tui/    Interaktive Textual-Oberflaeche (dieselben Anwendungsfaelle, niemals duplizierte Logik)
└── bootstrap/         DependencyContainer, Aufloesung der Projektwurzel
```

Durch `import-linter` geprüfte Regeln (8 Verträge): `domain`/`core` niemals von äußeren Schichten abhängig; `interfaces.tui` niemals direkt von `infrastructure` abhängig; `textual` auf `interfaces.tui` beschränkt; `subprocess` auf `infrastructure/process/subprocess_runner.py` beschränkt (und `infrastructure/lnav/`, interaktiver PTY-Datenstrom); `ssl` auf `infrastructure/tls/ssl_context_builder.py` beschränkt; `jinja2` auf `infrastructure/exporters/html_exporter.py` beschränkt; `sqlite3` auf `infrastructure/persistence/sqlite_active_defense_connection.py` beschränkt (einziger relationaler Speicher des Projekts, Active Defense vorbehalten — siehe §11); `lupa` auf `infrastructure/waf/lua_waf_adapter.py` beschränkt (ergänzendes WAF-Skript « magnet », §7).

## 7. Optionale Module

In allen mitgelieferten Profilen standardmäßig deaktiviert — Aktivierung immer explizit (`option enable <name>` oder `config enable-tls`):

| Modul | Rolle |
|---|---|
| `waf` | Signaturen (sensible Pfade, Scanner-UA/Referer, SQLi/XSS/CMDi im Body), als Textdatei bearbeitbare Listen (Stichwörter oder sensible Pfade mit `!`-Ausnahmen, Beobachtungsmodus und eigener Wiederholungsregel pro Liste — zwei mitgelieferte Referenzen, explizites Laden, siehe §11b), Ratenbegrenzung (Token-Bucket, Regeln pro Ordner und pro IP/Netz, siehe §11c), Sperrliste (CIDR + Ablauf), Reputation/Eskalation, Import eines bestehenden `mod_magnet`-WAF-Skripts von Lighttpd als optionale Verstärkung vom Typ « magnet » (ohne Umschreiben, Extra `pip install -e ".[magnet]"` — additiv, kann niemals eine native Sperre aufheben; Kompatibilitätsprüfung beim Import, eigener TUI-Bildschirm) — Modus `log-only` strukturell unfähig zu blockieren |
| TLS | Direkt (selbstsigniert, lokale CA oder öffentlich über Let's Encrypt/Certbot mit automatischer Erneuerung — siehe §9), niemals mTLS/OCSP in V1 |
| Authentifizierung | HTTP Basic pro Zone (`url_prefix`), `hashlib.scrypt` mit Schutz gegen Timing-Angriffe (konstante Zeit auch für einen unbekannten Benutzer) |
| FastCGI/PHP-FPM | Ein einziges `(url_prefix, script_root)`, `script_root` konstruktionsbedingt außerhalb von `webroot/` gehalten (der statische Handler kann niemals PHP-Quellcode preisgeben) |
| Ausgehender Reverse Proxy | Omega-serv agiert selbst als Proxy zu einem oder mehreren Backends (Gegenrichtung zu `server.tls.mode = "behind_proxy"`) — Lastverteilung (Round-Robin, gewichtet, Least-Connections, IP-Hash, Least-Response-Time, echte Last), Sitzungsaffinität und Routingregeln nach Header, passive und aktive Gesundheitsprüfung, Antwort-Cache (mehrere `Vary`-Varianten), Backpressure, Schleifenschutz, Verwaltungs-API im laufenden Betrieb — siehe §7a für alle Details |
| Upload | Abgeschottete Zonen, Kontingente pro Zone, serverseitig erzeugte Dateinamen — kein Streaming in V1 (begrenzt durch `server.max_request_size`) |
| `active_defense` | Deception + Kriegsmodus auf Basis der bereits berechneten WAF-Signale (niemals eine zweite Punktzahl): statische Köder, gezieltes Verlangsamen/angereichertes Protokollieren/Ratenbegrenzen, Vorfälle + IoC-Export — siehe §11 |

### 7a. Ausgehender Reverse Proxy — Details

OMEGA-SERV kann selbst als Reverse Proxy zu einem oder mehreren HTTP/HTTPS-Backends agieren — niemals zu verwechseln mit `server.tls.mode = "behind_proxy"` (OMEGA-SERV **hinter** einem Proxy, umgekehrter Mechanismus). Zonen mit vollständigem CRUD konfigurierbar (TUI: *Detaillierte Konfiguration → Reverse Proxy*), ein oder mehrere Upstreams pro Zone.

- **Lastverteilung** — `round_robin` (Standard), `weighted_round_robin`/`weighted_least_connections`/`ip_hash` (gewichtet), `least_connections`, `least_response_time`, `real_load` (echte Last). Modus `real_load` nativ (Sonde `/.omega-serv-load/`, verwendet dieselbe `psutil`-Messung wie der Bildschirm « Status & Ressourcen », niemals ein zweiter Aufruf) oder deklarativ (HTTP-Sonde eines Drittanbieters, Minimalformat `{"load_percent": ...}` oder nackte Zahl) — Granularität pro Upstream, eine Zone kann beides mischen.
- **Sitzungsaffinität und bedingtes Routing** — undurchsichtiges Sticky-Cookie (niemals der echte host:port für den Client sichtbar) und Header-Regeln (Gleichheit oder Präfix), beide gefiltert nach der Verfügbarkeit des Ziel-Upstreams (fallen sauber auf die aktive Strategie zurück, wenn der angestrebte Upstream nicht verfügbar ist).
- **Gesundheit** — passiv (aufeinanderfolgende Fehlschläge/Erfolge, getrennte Umschaltschwellen für down/up, um Flapping zu begrenzen) **und** aktiv (periodische Sonde unabhängig vom echten Verkehr, optional pro Upstream, nutzt denselben Hintergrundmechanismus wie die echte Last). Zustände `DOWN` (immer automatisch), `DRAINING`/`MAINTENANCE` (immer manuell, ausdrücklich flüchtig, niemals gespeichert) — ein manuell ausgelöster Upstream bleibt von neuen Auswahlen ausgeschlossen, ohne jemals eine bereits bestehende Verbindung zu unterbrechen. Automatischer Wiederholversuch auf einem anderen Upstream, nur für idempotente Methoden (GET/HEAD/OPTIONS) und nur bei Verbindungsfehler.
- **Backpressure** — pro Upstream konfigurierbare Obergrenze aktiver Verbindungen; ein ausgelasteter Upstream lehnt sauber mit 503 ab, unterscheidbar von einem ausgefallenen Upstream (502, trotzdem erneut versucht).
- **Antwort-Cache** — nur GET/HEAD, niemals eine Fehlerantwort, niemals `Set-Cookie` außer bei explizitem Opt-in pro Zone; respektiert `Cache-Control`/`Vary` des Upstreams (abschaltbare, aber gefährliche Option, gleiche Philosophie wie die TLS-Prüfung). Mehrere Varianten derselben Ressource (`Vary`) existieren tatsächlich nebeneinander auf der Festplatte, niemals ein einfaches « der Letzte gewinnt ». Anti-Stampede-Sperre (nur eine gleichzeitige Anfrage baut den Cache tatsächlich neu auf). Diagnose-Header `X-Omega-Cache: HIT`/`MISS`/`BYPASS` an jeder Antwort. Überwachung/Bereinigung in einem eigenen TUI-Bildschirm (*Reverse-Proxy-Cache*).
- **Schleifenschutz** — Hop-by-Hop-Header entfernt, `X-Forwarded-*` immer überschrieben (niemals mit denen des Clients zusammengeführt), Zähler `X-Omega-Proxy-Hops` bei jeder Weiterleitung erhöht (saubere Ablehnung ab 5 Sprüngen — erkennt eine indirekte Schleife zwischen zwei Instanzen, die eine einfache lokale Konfigurationsprüfung niemals sehen kann).
- **WebSocket** — Upgrade pro Zone erlaubbar, ein einziger Upstream für die gesamte Dauer des Tunnels festgelegt, sobald er steht, ohne Anwendungs-Timeout.
- **Verwaltung im laufenden Betrieb** — kleine lokale HTTP-API (`/.omega-serv-admin/`, wie die native Lastsonde durch `trusted_proxy` geschützt), mit der die TUI den Zustand DRAINING/MAINTENANCE eines Backends lesen/erzwingen und die Hit/Miss-Quote des Caches **des tatsächlich laufenden Servers** lesen kann (eigener Bildschirm *Live-Status der Backends*) — da TUI und Server zwei getrennte Prozesse ohne gemeinsamen Speicher bleiben, ist dieser lokale HTTP-Kanal die einzige Brücke zwischen beiden.

## 8. HTTP-Härtung (nicht abschaltbar)

- Header/Anfragezeile **während** des Lesens begrenzt (niemals hinterher), veraltete Header-Faltung abgelehnt, `Transfer-Encoding` immer abgelehnt (niemals erraten).
- Doppeltes `Content-Length` abgewiesen; `Expect: 100-continue` sauber abgewiesen (417).
- Explizite Methoden-Whitelist (sonst 405 + `Allow`), `Host`-Header validiert (fehlend/leer/doppelt-selbst-identisch/Steuerzeichen → 400).
- Sicherheits-Header und Basis-CSP (`enforce`/`report-only`) auf **jede** Antwort angewendet, auch auf Fehler — durch keine Option umgehbar. `Cross-Origin-Opener-Policy`/`Cross-Origin-Resource-Policy` immer `same-origin`, ohne echtes Risiko, eine Website zu beschädigen. `Cross-Origin-Embedder-Policy` immer explizit gesendet (niemals fehlend — ein externer Scanner unterscheidet so « nicht berücksichtigt » von « bewusst permissiv »), Standard `unsafe-none` in **allen** Profilen einschließlich `hardened`: Anders als die beiden vorherigen können `require-corp`/`credentialless` Cross-Origin-Ressourcen (Schriftarten, Bilder, Iframes von Drittanbietern) blockieren, die zur tatsächlich ausgelieferten Website gehören — einstellbar (`security.coep_mode`). CSP-Zonen (`security.csp_zones`): **explizite** Ausnahmen pro Pfadpräfix (z. B. `unsafe-inline` nur unter `/ein-ordner/`, der es wirklich braucht), jede ersetzt die Standardrichtlinie für ihr Präfix vollständig — niemals eine Zusammenführung, niemals eine globale Lockerung; jede Ausnahme bleibt in `audit security` sichtbar (CSP-001/CSP-002 durchsuchen auch die Zonen), auch wenn sie bewusst ist. Erstellung geführt von einem Assistenten Direktive für Direktive (Bildschirm **Allgemeine Sicherheit**), jedes Feld vorausgefüllt mit dem **aktuellen** Wert der globalen Richtlinie — um nur zu ändern, was sich ändern muss, statt von einem leeren Feld auszugehen, das ungewollt die übrigen Direktiven opfern würde; eine zusätzliche explizite Bestätigung wird verlangt, wenn die zusammengesetzte Zone `unsafe-inline`/`unsafe-eval`/eine generische Quelle `*` lockert.
- IPv4-mapped-IPv6-Adressen (`::ffff:x.x.x.x`) vor jedem Vergleich normalisiert (Sperrliste, vertrauenswürdiger Proxy, Ratenbegrenzung) — sonst ein bekannter Bypass.
- Durch Eigenschaftstests verifiziert (`hypothesis`, Tausende generierter Beispiele) gegen den HTTP-Parser und den Pfadauflöser, zusätzlich zu den klassischen Unit-/Integrationstests.

## 9. TLS

### 9a. Selbstsigniertes Zertifikat (minimal)

Deckt die realistische Nutzung lokal/Labor/VPN (Tailscale...) ab: ein einziger Listener, direktes `ssl.SSLContext`, RSA 2048/4096 oder ECDSA P-256/P-384.

### 9b. Lokale CA

Für mehrere Client-Geräte, die vertrauen sollen, ohne ein Zertifikat einzeln neu zu importieren: Eine lokale Zertifizierungsstelle signiert so viele Serverzertifikate wie nötig.

```text
secure/certificates/ca/
├── root-ca.key    # 0600 - das sensibelste Element des Projekts
├── root-ca.pem    # 0644 - in den Vertrauensspeicher der Clients zu importieren
├── serial.txt     # 0600 - Verfolgung der naechsten Seriennummer
└── index.txt      # 0600 - Statusverfolgung V(alid)/R(evoked) pro signiertem Zertifikat
```

Ablauf: `certs generate-ca` (Passphrase des CA-Schlüssels **Pflicht**, interaktive Eingabe mit doppelter Bestätigung, wenn `--password` fehlt) → `certs generate-csr` (Schlüssel + Server-CSR) → `certs sign-csr` (signiert mit der CA, übernimmt den SAN der CSR, erstellt auf Wunsch `fullchain.pem`) → `tls.certificate.certificate_path` auf diese `fullchain.pem` zeigen lassen. Ein kompromittiertes Zertifikat wird über `certs revoke` zurückgezogen (markiert `index.txt`, prüft vorher, ob das Zertifikat wirklich von dieser CA stammt — lehnt sonst ab). Keine CRL-Verteilung in V1, keine externe CA/CSR für eine Drittstelle, kein mTLS (siehe §15).

### 9c. Let's Encrypt / ACME (Certbot) — öffentlich, selbst gehostet

Für eine wirklich öffentliche Website mit einem von Browsern anerkannten Zertifikat, vollständiges selbst gehostetes Schema: DDNS (Dynu oder gleichwertig, vollständig Sache des Betreibers) → Certbot → Omega-serv. Nur TUI-Assistent (`Detaillierte Konfiguration → TLS → Let's-Encrypt-Assistent`) — ruft `certbot certonly --webroot` als Unterprozess auf (**niemals** `--standalone`, Port 80 ist bereits von Omega-serv belegt; **niemals** ein neu implementierter ACME-Client) mit `--config-dir`/`--work-dir`/`--logs-dir` unter `secure/certificates/letsencrypt/` des Projekts — **niemals** `/etc/letsencrypt/` —, wodurch Certbot selbst vollständig ohne Privilegien läuft. Das erhaltene Zertifikat wird automatisch importiert (derselbe Mechanismus wie `certs import`, siehe die CLI-Beispiele oben) und ein Hook-Skript für die Erneuerung wird geschrieben. Testmodus (Staging) standardmäßig angekreuzt — abzuwählen, sobald Domain/Webroot als funktionsfähig geprüft sind, um die echten Ratenlimits von Let's Encrypt zu vermeiden.

Voraussetzungen vollständig außerhalb des Umfangs von Omega-serv: Domain auf die öffentliche IP gezeigt (DDNS) und Ports 80/443 an diese Maschine weitergeleitet.

### 9d. Automatische Erneuerung (Certbot)

`Detaillierte Konfiguration → TLS → Automatische Erneuerung` passt sich dem tatsächlich erkannten Dienstmanager **für diese Instanz** an (niemals ein von mehreren Multi-Instanz-Instanzen geteilter Mechanismus): systemd → erzeugt und installiert einen Timer (`<service>-certbot-renew.timer`, zweimal täglich + zufällige Verzögerung, `certbot renew` auf das `--config-dir` der Instanz beschränkt); sonst → crontab-Zeile (aktueller Benutzer, keine Privilegien), wenn `crontab` verfügbar ist; sonst → angezeigte manuelle Anweisungen, kein erzwungenes Schreiben. Bei manchen Distributionen (darunter Arch/Manjaro) installiert das Certbot-Paket standardmäßig **keinen** Timer, anders als bei Debian/Ubuntu — daher dieser Bildschirm statt einer bloßen Prüfung eines vermeintlich schon vorhandenen Mechanismus. Einmal eingerichtet, importiert die Erneuerung jedes erneuerte Zertifikat automatisch neu (`certs import`) und startet dann den Dienst neu, ohne je wieder manuell eingreifen zu müssen.

## 10. Sicherheitsaudit

`audit security` ist **nicht blockierend**: Es führt die bereits blockierenden Sperren von `config check` als `CRITICAL` erneut aus und wendet dann beratende Regeln an (TLS, CSP, gefährliche Methoden, Timeouts, Upload-Hygiene rein; Dateiberechtigungen, Zertifikatsablauf, installierte systemd-Unit, Loggröße mit echtem I/O). `WAF-001` (WAF ist im Modus `log-only` geblieben) wird über die Zeit mithilfe einer kleinen Zustandsdatei (`var/run/waf-mode-state.json`) beobachtet — löst erst nach ≥14 beobachteten Tagen in `log-only` über wiederholte Ausführungen aus, nicht beim ersten `audit`.

## 11. Active Defense (Deception + Kriegsmodus)

Optionales Modul (`option enable active_defense`, standardmäßig deaktiviert), das feindliches Verhalten auf Basis der bereits berechneten WAF-Signale qualifiziert (`WafDecision`/Reputation/Sperrliste — niemals eine zweite, unabhängige Punktberechnung) und eine Quelle zu einem Köder umleiten, ihre Antworten verlangsamen und feiner protokollieren, einen verwertbaren Vorfall aufbauen und dann Kompromittierungsindikatoren (IoC) exportieren kann. Blockiert niemals selbst den Verkehr — die Netzwerksperre bleibt Sache von `omega-fire`; Active Defense beobachtet, lenkt um, verlangsamt und dokumentiert.

**Bedrohungen und Punktzahl**: Jede Quelle (`IP + SHA-256-Hash des User-Agent`) sammelt eine Punktzahl (`WAF-001` blockierend +10, Reputationseskalation +25, bekannte Sperre +25, POST auf einen bereits zugewiesenen Köder +30 — Abnahme um -5 alle 15 Minuten ohne neues Ereignis), qualifiziert als `normal`/`suspicious`/`hostile`/`contained` (`contained` erfordert zusätzlich eine bereits bekannte Sperre). `mode: monitor` beobachtet, ohne zu handeln; `mode: enforce` wendet die folgenden Aktionen tatsächlich an.

**Kriegsmodus** (`options.active_defense.settings.war_mode`): ein `DefensePlaybook` (`actions: ["redirect_to_decoy", "enrich_log", "delay", "rate_limit", "create_incident", "export_ioc"]`), ausgelöst durch konfigurierbare Schwellen, für jede Quelle, die nicht `normal` ist:
- `enrich_log` — separates JSONL-Log (`var/log/active-defense-enriched.jsonl`, niemals mit dem WAF-/Produktionslog vermischt), geschwärzte Header, HTTP-Body gehasht (SHA-256) oder gekürzt je nach `logging.capture_request_body`.
- `delay` — begrenzte Verlangsamung mit Jitter (`war_mode.slowdown.minimum_ms`/`maximum_ms`/`jitter_ms`), niemals ein Blockieren der asyncio-Schleife.
- `rate_limit` — eigene Ratenbegrenzung pro Quelle (`war_mode.rate_limit.requests`/`window_seconds`), verwendet denselben Mechanismus wie der WAF unter einem separaten Schlüssel.
- `create_incident` — automatisches Öffnen/Zusammenführen eines Vorfalls beim Überschreiten von `thresholds.incident_score`.

**Deception**: Eine Quelle `hostile`/`contained` kann einem statischen Köder zugewiesen werden (`fake_admin`, `fake_cms`, `fake_api`, `fake_secrets` — plausible, aber immer feste Antworten, niemals echtes Lesen von Dateien oder Unterprozesse), ausgewählt je nach beobachteter Angriffsklasse (`deception.profiles.<name>.match_attack_classes`, eine oder mehrere aus `scan`/`credential_stuffing`/`sqli`/`xss`/`path_traversal`/`upload_probe`/`api_probe`/`unknown`). Zwei Isolationsstufen, bewusst gewählt und als solche dokumentiert:
- **Stufe 1** (Fixture im Prozess, `isolation_level: "fixture"`, Standard) — ausdrücklich SCHWACHE Isolation: derselbe Prozess, derselbe OS-Benutzer wie die Produktion, nur akzeptabel, weil die Fixture niemals etwas anderes tut, als eine statische Vorlage zurückzugeben. Der NAME des Profils muss exakt einer der 4 obigen Fixtures entsprechen — sonst bei der Validierung abgelehnt (`validate_active_defense_config`), um die Falle eines falsch benannten Köders zu vermeiden, der dann stillschweigend nie auslöst.
- **Stufe 2** (wirklich isoliertes Backend, `isolation_level: "proxy"`) — an einen separaten Prozess weitergeleitet über `options.active_defense.settings.deception.decoy_zones.<name>` (Upstream `host`/`port` eines bereits laufenden Servers, niemals automatisch erstellt; niemals aus `options.reverse_proxy` gelesen — ein Köder kann niemals versehentlich auf eine Produktionszone zeigen, geprüft bei `config check`), unter Wiederverwendung desselben ausgehenden Reverse-Proxy-Mechanismus wie die Produktion (`serve_proxy()` — Upstream zum Zeitpunkt einer echten Anfrage nicht erreichbar: 502 an den Angreifer, niemals ein Absturz).

**Bildschirm Einstellungen** (TUI, Aktive Sicherheit → Active Defense → Einstellungen): vollständige Konfiguration all dessen — Modus, Aktivierung des Kriegsmodus, Geltungsbereich/Aktionen/Schwellen/Verlangsamung/Anfragelimit, Deception (Standardverhalten, CRUD der Köderprofile und Köderzonen mit Beispielwerten in jedem Feld), IoC, Speicherung und Protokollierung — vor jedem Speichern mit denselben Regeln wie die CLI validiert, ohne jemals `config/omega-serve.json` manuell bearbeiten zu müssen. Nach jeder Änderung ist systematisch ein vollständiger Neustart nötig (Active Defense wird niemals im laufenden Betrieb neu geladen).

**Vorfälle und IoC**: vollständige Chronologie pro Vorfall, Extraktion von Indikatoren (IP, gehashter User-Agent), versionierter JSON-Export/CSV beschränkt auf teilbare IoC/Markdown-Bericht sowie die Austauschformate **STIX 2.1** (Bundle zum Laden in OpenCTI, ein SIEM…) und **MISP** (Ereignis zum Import über die MISP-Oberfläche), standardmäßig mit TLP:AMBER gekennzeichnet — lokale Dateien, nie versendet; jeder Export begleitet von einer Datei `<export>.sha256` (Standardformat `sha256sum`). Automatischer Export beim Schließen eines Vorfalls, wenn `ioc.auto_export_on_close` (standardmäßig wahr). Abgelaufene Zustände und das Audit-Protokoll werden automatisch bereinigt, die Datenbank ist begrenzt (Schutz davor, die Festplatte zu füllen); `active-defense purge` schließt zusätzlich wieder still gewordene Vorfälle.

**Simulation**: `active-defense simulate` (CLI) und die Schaltfläche „Simulieren“ (TUI, Bildschirm Aktive Sicherheit) projizieren Punktzahl/Stufe und erklären jede Aktion, die ausgelöst würde — strikter Dry-Run, kein echtes Schreiben, keine Auswirkung auf das Netzwerk.

Sicherung/Wiederherstellung: `config backup --include-active-defense` nimmt die sqlite-Datenbank (Bedrohungen/Vorfälle/Zuweisungen) ins Archiv auf — niemals Geheimnisse im Klartext, daher kein `--confirm-secrets` erforderlich, anders als bei `--include-auth`.

## 11b. Listen sensibler Pfade (WAF)

Der WAF kann **bearbeitbare Listen** als Textdatei laden, ein Pfad (oder Stichwort) pro Zeile, über **Aktive Sicherheit → Custom → Hinzufügen → « Eine Liste LADEN »**. Standardmäßig wird nie etwas geladen: Es ist eine explizite Aktion.

- **Mitgelieferte Referenzen**: `sensitive-paths-hostile` (298 Pfade ohne legitime Nutzung: Geheimnisse, Sicherungen, VCS, Konsolen…) und `sensitive-paths-probe` (132 Sondierungspfade, manchmal von einer echten Website ausgeliefert: `/admin`, `/api`, Monitoring…). Beim Laden wird eine **lokale Kopie** in `secure/waf/rules/keywords/` erstellt: Diese bearbeiten Sie, ein Update von omega-serv überschreibt sie niemals (« Neues aus der Referenz » schlägt danach Feld für Feld die neuen Einträge vor).
- **Syntax**: `/admin` (→ `/admin` und `/admin/xxx`, niemals `/administrator`), `/.git/` (alles darunter), `/*.bak` (Endung), `!/api/v1` (Ausnahme, hat immer Vorrang). Pfade werden wie in der Engine dekodiert (`%2e`, Doppelkodierung, Vollbreitenzeichen).
- **Schweregrad**: *Beobachtung* (nur Log, beim ersten Laden empfohlen), dann Mittel (blockiert nie allein) oder Hoch (403 ab dem ersten Zugriff).
- **Eigene Wiederholungsregel pro Liste**: 1. Zugriff = Information oder Ablehnung; N Zugriffe in M Minuten = temporäre Anwendungssperre (Antwort 451, auch über Tailscale); wiederholte Sperren = Netzwerksperre durch omega-jail. Referenzen: hostile 2 Zugriffe in 10 Min. → 24 h, Sondierung 5 in 10 Min. → 1 h.
- **Niemals automatische Sperre** für den lokalen Host, Tailscale (`100.64.0.0/10`) und das lokale Netzwerk (`options.waf.reputation.never_auto_block`): Nur externer Verkehr kann gesperrt werden. Hinter einem lokalen Proxy erfordert die Ausnahme für `127.0.0.1` ein aktives `trusted_proxy`. `X-Forwarded-For` wird von rechts nach links gelesen: Ein Client kann sich nicht selbst als lokal ausgeben.
- **Schutzmechanismen**: geschützte lebenswichtige Pfade (`/`, `robots.txt`, `sitemap.xml`, `/.well-known/acme-challenge/`…), Ablehnung einer blockierenden Liste, die eine tatsächlich ausgelieferte Route treffen würde (Alias, Reverse Proxy, Auth-Zone, Webroot), **« Mit meinen Logs prüfen »** im Editor (Zeilen, die erfolgreiche Anfragen getroffen hätten, Ausnahme mit einem Klick).
- **Integrierter Editor**: Live-Diagnosen mit Zeilennummer, einen Pfad « Testen », sicheres Schreiben (Rechte und Gruppe bleiben erhalten, symbolische Links abgelehnt, externe Änderung erkannt), Lesbarkeit durch das Dienstkonto geprüft (« Rechte korrigieren ») und **ehrliches** Neuladen: mit Begründung abgelehnt, wenn die Liste die Prüfung nicht besteht, wobei der Server dann seine aktuellen Regeln behält.

## 11c. Ratenbegrenzung pro Ordner und pro IP/Netz (WAF)

Die Ratenbegrenzung des WAF (Token-Bucket, `options.waf.rate_limit`, standardmäßig 60 Anfragen / 60 s pro IP) lässt sich unter **Aktive Sicherheit → Ausnahmen und Rate-Limit** verfeinern (oder von Hand, `rate_limit.path_policies` / `rate_limit.source_policies`):

- **Regel pro Ordner** (`prefix`, `requests`, `window_seconds`): Sie **ersetzt** die globale Begrenzung für diesen Ordner, mit eigenem Zähler (`requests: 0` = unbegrenzt). Das längste Präfix gewinnt; `/images` deckt `/images/a.png` ab, nie `/images2`. Typischerweise eine schwere Seite (Bildergalerie), die 429 liefert.
- **Regel pro IP/Netz** (`network`, `requests`, `window_seconds`, `trusted`): gleiches Prinzip; das genaueste Netz gewinnt. Priorität: Ordner, dann IP/Netz, dann globale Begrenzung.
- **Sperren für die Öffentlichkeit unverändert**: Eine Überschreitung durch eine öffentliche IP wird weiterhin als `"action": "block"` in `waf-alerts.log` protokolliert und kann daher von omega-jail gesperrt werden (3 Ablehnungen in 10 min → 12 h). Eine **sichere Quelle** — ein `never_auto_block`-Netz oder eine mit `trusted: true` markierte Regel — erhält zwar das 429, wird aber als `"action": "throttle"` protokolliert, was die Jail nie zählt.
- **Magnet-Skript**: Seine eigene Ratenbegrenzung (Antwort 429) zählt nie als Erkennung und führt daher nie zur automatischen Sperre; bei einer Anfrage, die von einer Ordner- oder IP/Netz-Regel abgedeckt wird, gilt die native Regel und das 429 von magnet wird ignoriert (seine Angriffssignaturen gelten weiter).
- Eine Ratenregel deaktiviert **nie** die WAF-Prüfung; umgekehrt hebt eine Prüfungsausnahme (`exclusions.path_prefixes`) nie die Ratenbegrenzung auf. Ohne aktives `trusted_proxy` wird eine Regel für `127.0.0.1`/`::1` ignoriert (gleiche Schutzmaßnahme wie `never_auto_block`).

## 12. Dienste und Betrieb

Automatische Erkennung von systemd/OpenRC/runit (`service install/status/start/stop/restart/enable/disable/uninstall`). Die erzeugte systemd-Unit wendet standardmäßig eine nicht verhandelbare Härtung an: `NoNewPrivileges`, `PrivateTmp`, `ProtectSystem=strict`, `ProtectHome`, `ReadWritePaths` auf `var/` beschränkt, dedizierter Benutzer/dedizierte Gruppe Pflicht, `UMask=0077`, `Restart=on-failure`. Sauberes Beenden bei SIGTERM (Abarbeiten laufender Verbindungen, konfigurierbare Karenzzeit, dann erzwungenes Schließen); Neuladen im laufenden Betrieb bei SIGHUP (nur WAF-Regeln und Auth-Zonen — Bind/Port/TLS und Active Defense niemals ohne vollständigen Neustart änderbar).

## 13. Protokolle

`var/log/access.log` (Apache-combined-Format + `request_id`, Escaping gegen Log-Injection), `var/log/error.log`. Rotation nach Größe/Anzahl aufbewahrter Dateien (`logs.rotation`). Nativer WAF: `var/log/waf-alerts.log` (`options.waf.logging.path`). Magnet-Skript (§7): `options.waf.magnet.paths.alerts_log`/`.blocklist_log`, Standardwerte `var/log/waf-magnet-alerts.log`/`var/log/waf-magnet-blocklist.log` — nur dann automatisch zur Bibliothek hinzugefügt (Schaltfläche *Bekannte Omega-Serv-Logs hinzufügen*), wenn Magnet aktiv ist; `lnav` schlägt sie dagegen immer vor (eine fehlende Datei wird beim Start einfach ignoriert).

### 13a. Entfernte Quellen (SSH)

Zentralisiert auf ausdrücklichen Wunsch das Log eines Backend-Servers im selben lokalen Netzwerk hinter dem Reverse Proxy (Bildschirm **Log-Verwaltung → Bibliothek → Entfernte Quellen (SSH)**). Ein « Fetch » ist eine manuelle, einmalige Aktion, niemals ein Live-Datenstrom oder automatisches Polling: Eine **Kopie** wird beim Klick auf *Jetzt abrufen* über `scp` geholt, unter `var/log/remote/` geschrieben und dann wie ein gewöhnliches Log zur Bibliothek hinzugefügt (Spalte *Zugriff* = `ssh`, Spalte *Geändert* = Datum **dieses** Abrufs — niemals das der entfernten Datei); ein neuer Abruf ersetzt einfach die vorherige Kopie durch eine neuere.

Bewusste Schutzmechanismen (siehe `OMEGA-SERV_ETUDE-FAISABILITE_LOGS_DISTANTS.md` für die vollständige Studie): kein automatischer Netzwerkscan, keine Verbindung ohne explizite Konfiguration (Bezeichnung/Host/entfernter Pfad, Benutzer/Port/privater Schlüssel optional — leer lassen sie `ssh`/`~/.ssh/config` entscheiden, als würde der Befehl von Hand eingegeben), niemals wird ein Passwort abgefragt oder gespeichert (ein privater Schlüssel wird nur über seinen Pfad referenziert, niemals von Omega-serv gelesen oder gespeichert), keine Größenprüfung vor der Übertragung. Fähigkeit `scp` lokal im **Fähigkeitsregister** erkannt (nur Vorhandensein des Binärprogramms, niemals ein Erreichbarkeitstest eines Hosts); Samba bewusst außen vor gelassen (YAGNI, solange sich kein echter Bedarf bestätigt).

## 14. Tests

```bash
source .venv/bin/activate
lint-imports        # prueft die 8 Schichtenvertraege
pytest -q           # 2485 Tests
ruff check .
mypy src
```

Struktur: `tests/unit/` (Domäne/Anwendung, Test-Doubles), `tests/integration/` (echter asyncio-Server auf echten TCP-Sockets, echtes `openssl` als Unterprozess, echte CLI-Befehle gegen ein vollständiges temporäres Projekt, interaktive Oberfläche über die `Pilot`-API von Textual - niemals Screenshots), `tests/security/` (`hypothesis`-Eigenschaftstests für den HTTP-Parser und den Pfadauflöser).

## 15. Außerhalb des Umfangs

- Reines CGI (nur FastCGI/PHP-FPM)
- mTLS (Client-Authentifizierung per Zertifikat), OCSP-Stapling
- Externe CA / CSR für eine Drittstelle, vollständige CRL-Verteilung
- Active Defense: echte Integration mit den Sperrereignissen von `omega-fire` (auf Seiten von `omega-fire` blockiert, das derzeit keine Leseschnittstelle bereitstellt)

---

> 🔒 OMEGA-SERV — Ein robuster, vollständiger, sicherer und defensiver Webserver.
