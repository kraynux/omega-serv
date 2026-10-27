<!-- Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE) -->
<div align="center">
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/assets/omega-serv.png" alt="Omega-Serv" width="384">
</div>

# 🔒 OMEGA-SERV

**Zelfstandige, draagbare en standaard geharde HTTP-webserver**

> Ontwikkeld door **kraynux** voor **Omega-server** 
[kraynux.snake-mackarel](https://kraynux.snake-mackarel.ts.net)

Officiële pagina: [OMEGA-SERV](https://kraynux.snake-mackarel.ts.net/omega-serv/translation/nl/) &nbsp; Referentie, gebruik, Help & FAQ: [Volledige handleiding](https://kraynux.snake-mackarel.ts.net/omega-serv/translation/nl/guide.html)  
Voorbeeld: [Screenshots](https://kraynux.snake-mackarel.ts.net/omega-serv/screenshots/) &nbsp; Demonstratie [Demoserver](https://craftdark.snake-mackarel.ts.net) &nbsp; [Vergelijking/tests van webservers](comparatif-serveurs-web.md)  

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](../../../LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![Lua](https://img.shields.io/badge/Lua-5.4%2B-2C2D72.svg)](https://www.lua.org/)
[![JavaScript](https://img.shields.io/badge/JavaScript-ES2020%2B-F7DF1E.svg)](https://developer.mozilla.org/docs/Web/JavaScript)
[![Platform](https://img.shields.io/badge/Platform-Linux-informational.svg)](https://www.linux.org/)
[![Interface](https://img.shields.io/badge/Interface-CLI%20%2B%20TUI-cyan.svg)](#3-gebruik)
[![Textual](https://img.shields.io/badge/Textual-TUI-5A5AFB.svg)](https://textual.textualize.io/)

🌐 Documentatie, exports en interface beschikbaar in **17 talen** — zie [Talen van de interface](#talen-van-de-interface).  
**Talen:**
<img src="https://flagcdn.com/w20/fr.png" alt="France" style="height:14px;"> [Français](../../../README.md) · <img src="https://flagcdn.com/w20/gb.png" alt="English" style="height:14px;"> [English](../en/README.md) · <img src="https://flagcdn.com/w20/es.png" alt="Español" style="height:14px;"> [Español](../es/README.md) · <img src="https://flagcdn.com/w20/br.png" alt="Português (Brasil)" style="height:14px;"> [Português (Brasil)](../pt-BR/README.md) · <img src="https://flagcdn.com/w20/it.png" alt="Italiano" style="height:14px;"> [Italiano](../it/README.md) · <img src="https://flagcdn.com/w20/de.png" alt="Deutsch" style="height:14px;"> [Deutsch](../de/README.md) · <img src="https://flagcdn.com/w20/nl.png" alt="Nederlands" style="height:14px;"> [Nederlands](README.md) · <img src="https://flagcdn.com/w20/pl.png" alt="Polski" style="height:14px;"> [Polski](../pl/README.md) · <img src="https://flagcdn.com/w20/ru.png" alt="Русский" style="height:14px;"> [Русский](../ru/README.md) · <img src="https://flagcdn.com/w20/cn.png" alt="中文" style="height:14px;"> [中文](../zh-CN/README.md) · <img src="https://flagcdn.com/w20/vn.png" alt="Tiếng Việt" style="height:14px;"> [Tiếng Việt](../vi/README.md) · <img src="https://flagcdn.com/w20/th.png" alt="ไทย" style="height:14px;"> [ไทย](../th/README.md) · <img src="https://flagcdn.com/w20/id.png" alt="Bahasa Indonesia" style="height:14px;"> [Bahasa Indonesia](../id/README.md) · <img src="https://flagcdn.com/w20/jp.png" alt="日本語" style="height:14px;"> [日本語](../ja/README.md) · <img src="https://flagcdn.com/w20/kr.png" alt="한국어" style="height:14px;"> [한국어](../ko/README.md) · <img src="https://flagcdn.com/w20/in.png" alt="हिन्दी" style="height:14px;"> [हिन्दी](../hi/README.md) · <img src="https://flagcdn.com/w20/ae.png" alt="العربية" style="height:14px;"> [العربية](../ar/README.md)

---

**OMEGA-SERV** is een HTTP/1.1-server geschreven in puur Python (voor de serverkern alleen de standaardbibliotheek), bedoeld om statische inhoud en optioneel PHP-FPM te serveren, met een niet uitschakelbare protocolverharding en beveiligingsmodules (WAF, TLS, authenticatie) die u kunt stapelen in plaats van dat ze worden opgelegd. Zevende tool van de `omega-`-suite, maar bewust **buiten de toekomstige `omega-suite`-integratie** (hij werkt op de lokale machine die hem host, niet op externe doelen — dezelfde familie als `omega-fire`); opgebouwd volgens Clean Architecture, waarbij `bootstrap/` dienstdoet als compositiewortel.

## 1. Visie en reikwijdte

De uitgesproken prioriteit is **eerst de robuustheid/veiligheid van de HTTP-kern** — WAF en TLS zijn optionele modules die erbovenop komen, nooit voorwaarden. Een server die maar één ding doet (bestanden serveren, eventueel PHP), maar dat goed doet, met een echte, niet te omzeilen protocolverharding — in plaats van een server die veel dingen half doet.

### Wat OMEGA-SERV doet

- Serveert statische inhoud (bestanden, optioneel mapoverzicht, aliassen, omleidingen, herschrijvingen, cache) met veilige padresolutie (traversal, dubbele codering, symbolische links). Grote bestanden gaan in blokken rechtstreeks van de schijf, nooit in het geheugen geladen; elk bestand krijgt een `ETag` en een `Last-Modified` (herladen = lege 304-respons) en accepteert gedeeltelijke `Range`-verzoeken (download hervatten, video); afbeeldingen, media, lettertypen, CSS en JS krijgen een standaard-`Cache-Control`, aan te passen in het scherm Cache. Voorgecomprimeerde tekstbestanden: als `site.css.br` of `site.css.gz` naast `site.css` staat (gemaakt met `brotli -k site.css` of `gzip -k site.css`) en de browser ze accepteert, worden ze in plaats daarvan verzonden, nooit een versie die ouder is dan het origineel.
- Verhardt het HTTP-protocol standaard, zonder optie om dit uit te schakelen: expliciet toegestane methoden, validatie van de `Host`-header, weigering van de dubbelzinnigheid `Content-Length`/`Transfer-Encoding`, niet te omzeilen beveiligingsheaders en basis-CSP.
- Optioneel: WAF-filtering (signaturen, snelheidsbeperking, blokkeerlijst), direct TLS (zelfondertekend certificaat, ondertekend door een lokale CA, of publiek via Let's Encrypt/Certbot met automatische vernieuwing — zie §9), HTTP Basic-authenticatie per zone, PHP via FastCGI/PHP-FPM, afgeschermde uploadzones.
- « Boost »-modus: meerdere serverprocessen, hoogstens één per beschikbare CPU van de machine (scherm Weerbaarheid en limieten); de beveiligingstellers (snelheidsbeperking, herhaling) worden tussen hen gedeeld en blijven exact.
- Auditeert zijn eigen configuratie (`audit security`) en installeert zich als systeemdienst (systemd/OpenRC/runit).
- Volledig scriptbare, niet-interactieve CLI, **én interactieve interface (Textual)** die precies dezelfde use-cases omvat — zie §3. Roadmap van de interface (`OMEGA-SERV_PLAN-DETAILLE_INTERFACE.md`, §12) **volledig opgeleverd**: capaciteitenregister, profielen/opties, gedetailleerde configuratie (aliassen/omleidingen/herschrijvingen/FastCGI/mapoverzicht/authenticatie/cache/WAF/vertrouwde proxy's/uitgaande reverse proxy/TLS), logbeheer (Bibliotheek/Favorieten, 3 viewers — eenvoudig/klassiek/samengevoegde lnav —, IP bekijken en behandelen, externe SSH-bronnen, rotatie/back-up/automatisering/herstel/opschonen/export), systeemdienst, multi-instantie (register, aanmaak), controle/simulatie/audit, back-up/herstel van de configuratie, eerste-installatie-assistent, applicatie-instellingen (thema, weergaveprofiel, paden voor exports/screenshots), contextuele helphandleiding (pagina per scherm met concrete voorbeelden, FAQ, HTML-export, volledige dekking gecontroleerd door tests), systematische melding herladen/herstarten na elke opslag, volledige configuratie van Active Defense zonder handmatige bestandsbewerking.

### Wat OMEGA-SERV niet doet

- Kale CGI (uit de reikwijdte van V1 gehaald — alleen FastCGI/PHP-FPM wordt ondersteund).
- Wederzijdse TLS-authenticatie (mTLS), OCSP-stapling — buiten de reikwijdte van V1, zie §15. (ACME/Let's Encrypt via Certbot is beschikbaar, zie §9c/9d.)
- Tussen processen gedeelde HTTP-cache.
- Scan/audit van een extern doel (zie daarvoor `omega-check`/`omega-scan`/`omega-deep` — Omega-serv auditeert zichzelf, nooit een derde).

### OMEGA-SERV vergeleken met de webservers op de markt

Zie [Metingen & vergelijking](comparatif-serveurs-web.md)  
Gemeten vergelijking tussen: [Nginx](https://nginx.org/) · [Lighttpd](https://www.lighttpd.net/) · [Caddy](https://caddyserver.com/) · [Apache](https://www.apache.org) · [Traefik](https://traefik.io/) · [Omega-Serv](https://kraynux.snake-mackarel.ts.net/omega-serv/translation/nl/)

### Gebruikswaarschuwing

Omega-serv **weigert te starten als root**. In geen enkel meegeleverd profiel, ook niet `hardened`, is standaard een beveiligingsmodule (WAF, TLS, authenticatie) ingeschakeld — inschakelen is altijd een expliciete handeling (`config enable-tls`, `option enable waf`...). Het profiel `hardened` zelf raadt voor een echte blootstelling aan internet een reverse proxy aan, in plaats van die te vervangen.

## 2. Installatie

### Vereisten

- Python 3.10+
- `openssl` (programma, geen Python-bibliotheek) voor alles wat met TLS-certificaten te maken heeft — de andere functies werken ook zonder.

### Downloaden

Archief van de nieuwste versie en SHA-256-controlesommen van elke versie: [omega-serv-2.0.0.tar.gz](https://kraynux.snake-mackarel.ts.net/omega-serv/download/omega-serv-2.0.0.tar.gz) · [sha.txt](https://kraynux.snake-mackarel.ts.net/omega-serv/download/sha.txt)

```bash
wget https://kraynux.snake-mackarel.ts.net/omega-serv/download/omega-serv-2.0.0.tar.gz
wget https://kraynux.snake-mackarel.ts.net/omega-serv/download/sha.txt
sha256sum -c --ignore-missing sha.txt
```

### Installatie

> ⚠️ **Werkt u een bestaande installatie bij?** De onderstaande opdracht **slaat het uitpakken stilzwijgend over** als `omega-serv/` al bestaat (hij gaat ervan uit dat het om een onderbroken eerste installatie gaat, niet om een update) — u zou dan de afhankelijkheden opnieuw installeren op de **oude, ongewijzigde code**, zonder ook maar één foutmelding. Gebruik in plaats daarvan het onderdeel [Bijwerken](#bijwerken) hieronder.

```bash
[ -d omega-serv ] && echo "ℹ️ Hier al uitgepakt, stap overgeslagen." || tar -xzf omega-serv-2.0.0.tar.gz
cd omega-serv/
chmod +x install.sh
./install.sh
```

`install.sh`:

1. Maakt de virtuele omgeving `.venv` aan als die nog niet bestaat.
2. Installeert het pakket (`pip install -e .`) — **geen externe afhankelijkheid** (zie §6).
3. Maakt `omega-serv.sh` en `install.sh` uitvoerbaar.
4. Voegt de alias `serv` toe aan `~/.bashrc` en `~/.zshrc` (zonder duplicaat als hij al bestaat).

### Bijwerken

Als `omega-serv/` al bestaat (eerdere installatie), **start `tar` dan nooit vanuit die map**: het zou proberen een geneste `omega-serv/omega-serv/` aan te maken en mislukken. Anders dan omega-fire raakt `install.sh` nooit de rechten van de map aan (geen enkele stap vraagt er `sudo`) — er is hier dus geen risico op een map die eigendom is van `root`; direct over de bestaande installatie heen uitpakken is veilig.

```bash
# Vanuit de BOVENLIGGENDE map van omega-serv/ (nooit van binnenuit)
tar -xzf omega-serv-2.0.0.tar.gz
cd omega-serv/
./install.sh
```

Het archief sluit bewust alle levende status uit (`var/db/`, `var/log/`, `var/backups/`, `secure/secrets/`, `secure/certificates/*.key`, `config/omega-serve.json`, **`webroot/` — de daadwerkelijk geserveerde site**...) — eroverheen uitpakken raakt nooit de aanwezige gegevens, certificaten, instellingen of geserveerde inhoud aan; alleen de applicatiecode wordt vervangen. `install.sh` hergebruikt de bestaande `.venv` en installeert de afhankelijkheden er gewoon opnieuw overheen.

Sinds 2026-10-18 zitten `var/` en `secure/auth/` helemaal niet meer in het archief, zelfs niet leeg: eroverheen uitpakken zet hun rechten (gedeeld met het account van de systemd-dienst) dus niet meer terug — « Dienst → Rechten opnieuw toepassen » is na een update niet meer nodig. `install.sh` maakt deze mappen aan als ze ontbreken, zonder ooit bestaande mappen aan te raken.

> ⚠️ **Als er al een dienst actief is, is de bovenstaande stap niet genoeg.** Hij vervangt de code op schijf, maar het al draaiende proces blijft werken met de oude code die in het geheugen is geladen — daarna is systematisch een **volledige herstart** nodig:
> ```bash
> sudo systemctl restart <dienstnaam>
> ```
> **Nooit een gewone herlading** (`systemctl reload`, of scherm DIENST → *Herladen*): die leest alleen bepaalde configuratieopties opnieuw in (WAF-regels, authenticatiezones...), **nooit de Python-code zelf**. Een `systemctl status <dienstnaam>` die een startdatum toont van vóór uw update bevestigt dat hij nog op de oude code draait. Als u altijd bijwerkt door dezelfde map te overschrijven (standaardgeval hierboven), is deze herstart de enige ontbrekende stap — de dienst opnieuw installeren is niet nodig.

> ⚠️ **Als de dienst daarna in een herstartlus blijft hangen** (`systemctl status` wisselt tussen actief/inactief, `journalctl -u <dienstnaam>` toont een `PermissionError` bij het schrijven van een bestand onder `var/`): het uitpakken met `tar` herstelt de maprechten zoals ze in het archief zijn vastgelegd, wat de rechtendeling kan wissen die bij de eerste installatie voor het speciale systeemaccount is ingesteld — ook al raakt `install.sh` zelf die nooit aan. De unit opnieuw installeren is niet nodig: scherm DIENST → **Rechten herstellen** (past de deling opnieuw toe op `var/` en `secure/auth/`, zonder de systemd-unit aan te raken).

### Afhankelijkheden

De serverkern (HTTP/1.1-parser, FastCGI-client, wachtwoordhashing via `hashlib.scrypt`) blijft puur Python/stdlib, en alles rond TLS-certificaten loopt via het programma `openssl` als subproces in plaats van via een Python-cryptobibliotheek — **daarvoor geen externe afhankelijkheid**. Alleen de interactieve interface (§3) brengt er enkele mee: `omega-lib` (thema's, terminaldetectie — gedeelde bibliotheek van de suite, niet gepubliceerd op PyPI, meegeleverd in het distribueerbare archief), `textual` en `pyte` (terminalemulatie voor de in de interface samengevoegde `lnav`-weergave), `jinja2` (HTML-exports met thema) en `psutil` (scherm Status & bronnen — CPU/RAM/schijf/netwerk). Optionele ontwikkel-/testafhankelijkheid (`pip install -e ".[test]"`): `hypothesis` (eigenschapstests van de HTTP-parser en de padresolver, nooit in productie). Kwaliteitstools (`pip install -e ".[dev]"`): `pytest`, `ruff`, `mypy`, `import-linter`. Extra optioneel pakket (`pip install -e ".[magnet]"`): `lupa` (ingebedde Lua-koppeling, voorgecompileerd wheel, geen systeem-`lua`-interpreter nodig), uitsluitend voor het aanvullende WAF-script « magnet » (§7) — nooit standaard geïnstalleerd; de afwezigheid ervan wordt gemeld (capaciteit `waf-magnet`, scherm **Capaciteiten**) met de exacte installatieopdracht, zonder de rest van de server te blokkeren.

### Aanbevolen optionele tools

De interface werkt in beperkte modus als deze tools ontbreken:

- `openssl` — nodig voor alles rond TLS-certificaten (zelfondertekend, lokale CA, import); zonder dit mislukken de opdrachten `certs *`, maar de rest van de server werkt normaal (zie §9).
- `certbot` — alleen nodig voor de **Let's Encrypt**-assistent en de automatische vernieuwing (§9c/9d); zelfondertekende TLS/lokale CA hebben het niet nodig.
- `lnav` — geavanceerde, samengevoegde loganalyse in het scherm **Logbeheer** (§3); duidelijke, expliciete foutmelding als het programma niet gevonden wordt, geen crash; de rest van het scherm (bekijken/volgen/rotatie/statistieken) werkt ook zonder normaal.
- `scp` (pakket `openssh`/`openssh-clients`, bijna altijd al aanwezig) — alleen nodig voor de **Externe bronnen (SSH)** (§13a); zonder dit mislukt het ophalen met een duidelijke melding, de rest van de Bibliotheek werkt normaal.
- `python-psutil` (systeempakket dat overeenkomt met `psutil` van PyPI) — wordt in alle gevallen automatisch geïnstalleerd door `pip install -e .` (verplichte afhankelijkheid van het pakket, het scherm **Status & bronnen** heeft het altijd nodig), maar het vooraf via de pakketbeheerder installeren bespaart `pip` het lokaal compileren van het wheel.

```bash
# Arch Linux en afgeleiden
sudo pacman -S openssl certbot lnav python-psutil openssh

# Debian/Ubuntu en afgeleiden
sudo apt install openssl certbot lnav python3-psutil openssh-client

# Fedora
sudo dnf install openssl certbot lnav python3-psutil openssh-clients
```

## 3. Gebruik

Twee functioneel strikt gelijkwaardige interfaces, nooit gedupliceerde logica tussen beide: niet-interactieve CLI (scriptbaar, hieronder gebruikt) en interactieve Textual-interface (menu's, formulieren, tabellen) — elke actie van de ene bestaat aan CLI-zijde, de interface omvat alleen dezelfde use-cases.

### Interactieve modus (TUI)

Aanbevolen voor dagelijks gebruik — gestart zonder argument:

```bash
./omega-serv.sh
```
als u de alias hebt aangemaakt, typ dan gewoon `serv` in de terminal:
```bash
serv
```

### Talen van de interface

17 talen: Frans, Engels, Spaans, Portugees (Brazilië), Italiaans, Duits, Nederlands, Pools, Russisch, Chinees, Vietnamees, Thai, Indonesisch, Japans, Koreaans, Hindi, Arabisch. Keuze in de Instellingen (toets `o`, « Langue / Language », label wordt nooit vertaald), of eenmalig met `OMEGA_SERV_LANG=en serv`. In de Linux-tekstconsole (TTY) worden de talen waarvan het schrift niet bestaat in de consolelettertypen (Vietnamees, Chinees, Thai, Japans, Koreaans, Hindi, Arabisch) voor de sessie in het Engels weergegeven. In het Hindi verschuiven terminals die verbonden letters zelf samenstellen (Kitty, Ghostty, Konsole) kaders en kolommen, wisselend per lettertype: bij het opstarten verschijnt een waarschuwing; Terminator, GNOME Terminal, Xfce Terminal en Alacritty tonen het Hindi uitgelijnd. Twee aparte instellingen: de **taal van de bezoekerspagina's** (foutpagina's, mapoverzicht — scherm Foutpagina's, standaard Frans) en de **taal van de exports** (HTML en incidentrapport — Instellingen, standaard « Zoals de interface »). De serverlogs (`journalctl`) blijven in het Frans.

### Algemeen verloop

Opstartscherm (splash, sluit met een toets of klik) → hoofdmenu (Eerste installatie / Capaciteitenregister / Profielen / Gedetailleerde configuratie / Actieve beveiliging / Logbeheer / Dienst / Multi-instantie / Status & bronnen / Audit / Back-up) → keuze van een onderdeel en daarna een actie, waarbij elk formulier zijn verplichte velden valideert voordat het verdergaat → expliciete bevestiging vóór elke gevoelige of destructieve handeling (herstart, verwijderen, herstellen...) → systematische melding van de volgende stap (automatische herlading tijdens bedrijf, of bevestiging van een volledige herstart) na elke opslag die een al geserveerde configuratie wijzigt. De aanpassing aan de terminal (kleuren, grootte, structurele afschaling van het weergaveprofiel) gebeurt automatisch en zonder handmatige vlag — zie §4.

#### Sneltoetsen (interactieve interface)

| Toets | Actie |
|---|---|
| `↑` / `↓` | Navigeren tussen de elementen van een scherm |
| `Tab` / `Shift+Tab` | Navigeren tussen de velden van een formulier |
| `Esc` | Terug naar het vorige scherm (bevestiging om af te sluiten op het startscherm) |
| `t` | Volgend thema (direct toegepast, zonder bevestiging) |
| `r` | Terminaldetectie vernieuwen |
| `F1` | Help bij het actieve scherm (contextuele pagina — zie "Helphandleiding" hieronder) |
| `a` | Volledige helphandleiding (navigeerbaar menu + FAQ) |
| `o` | Applicatie-instellingen (thema, weergaveprofiel, paden voor exports/screenshots — zie hieronder) |
| `q` | Afsluiten (met bevestiging) |
| `Ctrl+P` | Opdrachtpalet (Thema, Screenshot, Opties...) |

> **Uitzondering — lijsteditor (WAF → Custom)**: geen sneltoetsen, alles gaat met de muis; het toetsenbord dient alleen om te typen (tekens, Enter, pijltoetsen, Home/End, Page Up/Down, Backspace, Delete). `Esc`, `F1` en `Ctrl+P` zijn daar inactief (knop **Help**); alleen `Ctrl+Q` blijft actief, met bevestiging bij niet-opgeslagen wijzigingen.

#### Helphandleiding (toetsen `F1`/`a`)

Geïntegreerd helpsysteem, nooit een simpele statische tekst: elk gedocumenteerd scherm (pagina met definitie/in te vullen velden met concrete voorbeelden/geactiveerde actie/reactie — herladen, herstarten of geen) is er direct vanuit bereikbaar via `F1`; de toets `a` opent het volledige menu (boomstructuur identiek aan de echte navigatie van de applicatie) met toegang tot de FAQ (in de praktijk tegengekomen valkuilen, bv. aanvalsklassen van Active Defense, rechten bij een gedeelde dienst) en een zelfstandige HTML-export (actief thema behouden) van de hele handleiding. Terugval op een generiek referentiescherm zolang er nog geen specifieke pagina bestaat — de dekking is momenteel volledig en door tests gecontroleerd.

#### Hoofdmenu (interactieve interface)

- **Eerste installatie** — begeleid traject in 8 stappen (welkom → capaciteiten alleen-lezen → profielkeuze → bind/poort → optionele TLS → controle → samenvatting + schrijven → aanbod om de dienst te installeren); genereert een volledige configuratie en zet de server aan het werk zonder de CLI te kennen.
- **Capaciteitenregister** — alleen-lezen systeemscan (init-systeem, geconfigureerde poort al bezet of niet, `openssl`/`logrotate`/`tailscale`/`lnav` aanwezig, schijfruimte, limiet van descriptors...), export naar JSON/HTML.
- **Profielen** — dezelfde use-case als `profile` in de CLI (§5), diff altijd getoond vóór het schrijven.
- **Gedetailleerde configuratie van de server** — volledige CRUD op aliassen/omleidingen/herschrijvingen/mapoverzicht/vertrouwde proxy's/uitgaande reverse proxy/FastCGI/cache/authenticatie/toegangscontrole/foutpagina's, plus het submenu **TLS** (status, zelfondertekende generatie, assistent lokale CA, Let's Encrypt/Certbot-assistent, automatische vernieuwing, intrekking, in-/uitschakelen — zie §9); een tweede kader **OPTIES EN CONTROLE** bundelt daar de snelkoppelingen naar **Opties** (`option` CLI, §7) en **Configuratie controleren** (`config check` CLI, §10) — hetzelfde traject als instellingen aanpassen en daarna controleren; deze twee schermen zijn niet meer rechtstreeks vanuit het hoofdmenu bereikbaar. De WAF woont hier niet meer (zie "Actieve beveiliging" hieronder): hij toont vooral operationele status die voortdurend verandert, geen eenvoudig statisch configuratieformulier. Elke opslag vermeldt systematisch de volgende stap: automatische en stille herlading tijdens bedrijf als er een dienst actief is (mapoverzicht, toegang, aliassen/omleidingen/herschrijvingen, cache, foutpagina's, vertrouwde proxy's, reverse-proxy-/FastCGI-zones, gebruikers/authenticatiezones), of expliciete bevestiging van een volledige herstart wanneer de wijziging de luistersocket, TLS of Active Defense raakt — geen enkel scherm laat u nog raden of de server opnieuw gestart moet worden.
- **Actieve beveiliging** — één scherm met twee blokken naast elkaar: **Active Defense** (Status, Gevolgde dreigingen met score/niveau, Incidenten met tijdlijn/IoC-export/rapport, toewijzingen van Deception, Een beslissing simuleren in dry-run, **Instellingen** — volledige configuratie zonder ooit `config/omega-serve.json` met de hand te bewerken, zie §11) en **WAF** (Status, Modules — modus/regelpakketten/blokkeerlijst, Een verzoek testen, Custom — eigen regels opstellen en met de muis bewerkbare lijsten van paden/trefwoorden laden (zie §11b), Magnet — een extern `mod_magnet`-script importeren met compatibiliteitscontrole vóór activering) — zie §11.
- **Logbeheer** — menu in twee kolommen. Kolom **Bibliotheek**: centrale hub die elke te behandelen log refereert (handmatige vulling, één klik voegt automatisch de eigen logs van de instantie toe — access/error/native WAF, + magnet-script §7 indien actief —, of een via SSH opgehaalde **externe bron**, zie hieronder); **Favorieten** (combinatie van logs + viewer opgeslagen onder een naam, directe start); **Logs bekijken** met 3 viewers naar keuze afhankelijk van het aantal geselecteerde logs — Eenvoudig (live tail + generieke statistieken IP's/fouten/HTTP-codes voor elk formaat), Klassiek (lezen + volgen), samengevoegde `lnav` (echte terminalweergave in de interface, magnet-logs automatisch inbegrepen + handmatige paden die u **vastzet** om ze tussen sessies te bewaren); **IP bekijken en behandelen** (top-IP's uit één of meer gekozen logs, periode 24u/7d/30d/alles, verwijderen van een IP). Kolom **Onderhoud** (ongewijzigd): handmatige of automatische rotatie/archivering op groottedrempel, direct een back-up maken, instellen/beheren van geplande automatiseringen (declaratief — zie opmerking hieronder), een archief herstellen/opschonen, export van de lijst.
- **Dienst** — dezelfde acties als `service` in de CLI (§12), eenmalige `sudo`-verhoging per actie, nooit de hele applicatie als root gestart.
- **Multi-instantie** — globaal register (`~/.config/omega-serv/instances.json`, buiten elke projectmap) van de op de machine bekende installaties, met de systemd-status van elk; aanmaak van een nieuwe instantie (kopie van de mapstructuur, eigen virtuele omgeving en afhankelijkheden, verse configuratie met aparte poort, controle op nesting en poortconflict) rechtstreeks vanuit de interface. Knop praktisch onzichtbaar bij een enkele installatie (het label "Multi-instantie" wordt "Instanties (N)" zodra er 2 bekend zijn); volledige overschakeling naar een andere instantie (`os.execv`, expliciete bevestiging, eigen splash die de overschakeling bij het herstarten aankondigt); volledige verwijdering van een instantie (verwijderen van de unit, van het speciale systeemaccount als geen andere instantie het nog gebruikt, en optioneel verwijderen van de map, nooit standaard).
- **Status & bronnen** — overzicht in één oogopslag, elke 2 seconden vernieuwd: serverstatus (proces/PID, status van de systeemdienst, profiel/actieve opties/TLS/poort), live stroom van de toegangslog (doorvoer, verdeling per statuscode, unieke IP's, foutpercentage), systeembronnen (CPU/RAM/schijf/swap/belasting/netwerk, via `psutil`); bundelt ook de snelkoppeling **Een verzoek simuleren** (dezelfde use-case als de bijbehorende CLI-opdracht, §10).
- **Beveiligingsaudit** — dezelfde use-case als de bijbehorende CLI-opdracht (§10).
- **Back-up van de configuratie** — tar.gz-archief van het configuratiebestand en, op expliciete keuze, van de WAF-regels/authenticatiezones/certificaten (bevestiging verplicht zodra echte geheimen zijn inbegrepen)/Active Defense-database, herstel, lijst, verwijderen.

> Opmerking over geplande rotatieautomatiseringen: ze worden opgeslagen (frequentie + doellog), maar **niets voert ze automatisch uit** — niet aan de interfacekant en niet op de achtergrond. Dat is een bewuste keuze voor gelijkheid met het overeenkomstige scherm van `omega-fire`, dat hetzelfde declaratieve gedrag heeft. Een echte periodieke uitvoering (systemd-timer, achtergrondtaak) moet apart worden gebouwd als de behoefte wordt bevestigd.

#### Applicatie-instellingen (toets `o` of opdrachtpalet)

Alleen interfacevoorkeuren — nooit te verwarren met `config/omega-serve.json` (serverconfiguratie): actief thema, weergaveprofiel (`complete`/`standard`/`reduced`/`mono`, herstart vereist), pad van de exports (standaard `var/exports/`), pad van de screenshots (standaard `var/screenshots/`), leegmaken van de ene of de andere map (bevestiging verplicht).

```bash
# De server starten (voorgrond, SIGTERM = net afsluiten met respijttijd, SIGHUP = herladen tijdens bedrijf WAF/Auth)
./omega-serv.sh serve

# Configuratie
./omega-serv.sh config init                # genereert config/omega-serve.json (veilige standaardwaarden)
./omega-serv.sh config check                # controleert zonder te starten (dezelfde blokkades als bij het starten)
./omega-serv.sh config show
./omega-serv.sh config enable-tls --cert ... --key ... --mode direct
./omega-serv.sh config disable-tls

# Profielen (minimal / standard / hardened / development)
./omega-serv.sh profile list
./omega-serv.sh profile show hardened
./omega-serv.sh profile apply hardened --dry-run   # diff voor het toepassen, altijd

# Opties (aliases, redirects, rewrites, dirlisting, cache, waf, upload, fastcgi, reverse_proxy...)
./omega-serv.sh option list
./omega-serv.sh option enable waf
./omega-serv.sh option disable waf

# Een verzoek simuleren zonder de server te starten (handig om een regel voor activering te valideren)
./omega-serv.sh simulate-request GET /index.html

# WAF (werkt zelfs met uitgeschakelde optie, via impliciete --force)
./omega-serv.sh waf test --method GET --path /admin --remote-ip 203.0.113.1
./omega-serv.sh blocklist list
./omega-serv.sh blocklist add --network 203.0.113.0/24 --reason "scan gedetecteerd" --duration-seconds 3600
./omega-serv.sh blocklist remove --network 203.0.113.0/24

# Active Defense (deception + oorlogsmodus, optie "active_defense" - zie §11)
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

# TLS-certificaten - zelfondertekend (9a)
./omega-serv.sh certs generate-self-signed --cn localhost --san-dns localhost --san-ip 127.0.0.1
./omega-serv.sh certs show
./omega-serv.sh certs check-expiry --warn-days 30

# TLS-certificaten - lokale CA (9b)
./omega-serv.sh certs generate-ca --cn "Mijn lokale CA" --days 3650
./omega-serv.sh certs generate-csr --cn server.local --san-dns server.local --key-out server.key --csr-out server.csr
./omega-serv.sh certs sign-csr --csr server.csr --ca-key secure/certificates/ca/root-ca.key --ca-cert secure/certificates/ca/root-ca.pem --out server.pem --fullchain-out fullchain.pem
./omega-serv.sh certs revoke --cert server.pem --ca-key secure/certificates/ca/root-ca.key --ca-cert secure/certificates/ca/root-ca.pem

# TLS-certificaten - import (9c, bv. vanuit een Certbot-hook)
./omega-serv.sh certs import --key privkey.pem --cert fullchain.pem

# HTTP Basic-authenticatie
./omega-serv.sh auth add-user --username alice
./omega-serv.sh auth create-zone --url-prefix /admin/ --allowed-users alice
./omega-serv.sh auth list

# Beveiligingsaudit (blokkeert nooit, informatief)
./omega-serv.sh audit security --format text --min-severity medium

# Back-up van de configuratie (configuratie altijd inbegrepen; echte geheimen
# standaard nooit versleuteld, --confirm-secrets verplicht om ze op te nemen)
./omega-serv.sh config backup --description "voor de migratie"
./omega-serv.sh config backup --include-auth --include-certificates --confirm-secrets
./omega-serv.sh config backup --include-active-defense --description "dreigingen/incidenten"
./omega-serv.sh config list-backups
./omega-serv.sh config restore --snapshot-id snapshot_20260908_170003_762484

# Systeemdienst (systemd/OpenRC/runit, automatische detectie)
./omega-serv.sh service install --user omega-serv --group omega-serv
./omega-serv.sh service start
./omega-serv.sh service status
```

### Belangrijke exitcodes

| Opdracht | Code | Betekenis |
|---|---:|---|
| `audit security` | `0` | Niets ernstigs (geen `CRITICAL`/`HIGH`) |
| `audit security` | `1` | Minstens één bevinding `CRITICAL` |
| `audit security` | `2` | Minstens één `HIGH` zonder `CRITICAL` |
| `audit security` | `3` | Uitvoeringsfout (configuratie niet gevonden...) |
| `certs check-expiry` | `1` | Certificaat verlopen |
| elke andere opdracht | `0`/`1` | Succes / validatiefout |

## 4. Terminalcompatibiliteit

De interactieve interface ([Textual](https://textual.textualize.io/), gebouwd op [Rich](https://rich.readthedocs.io/)) detecteert automatisch de mogelijkheden van de terminal (emulator, grootte) en past haar structurele stylesheet daarop aan (`complete`/`standard`/`reduced`/`mono`), zonder handmatige vlag. De CLI-modus blijft altijd gewone tekst, onafhankelijk van de terminal. Beleid gedeeld door de hele `omega-`-suite (`omega-lib`, `terminal/policies.py`) — identiek aan dat van `omega-check`/`omega-fire`.

### Profiel volgens de gedetecteerde emulator

| Emulator | Beginprofiel |
|---|---|
| Ghostty, Alacritty, WezTerm, Kitty | `complete` |
| Konsole, GNOME Terminal, Terminator, Xfce4 Terminal | `standard` |
| xterm, urxvt, moderne SSH | `reduced` |
| Linux-TTY, oude SSH | `mono` |
| Onbekende emulator | `reduced` (standaard terugval) |

### Profiel volgens de terminalgrootte

| Minimale grootte (kolommen × regels) | Profielplafond |
|---|---|
| 120 × 32 | `complete` |
| 100 × 28 | `standard` |
| 80 × 24 | `reduced` |
| daaronder | `mono` |

Het uiteindelijk gekozen profiel is **het strengste van de twee** (emulator en grootte) — een Ghostty op volledig scherm die wordt verkleind tot 70 kolommen zakt terug naar `mono`, ook al zou zijn emulator `complete` toestaan. Live te vernieuwen met de toets `r`, of handmatig te overschrijven in de Applicatie-instellingen (toets `o`, §3).

## 5. Profielen

| Profiel | Beoogd gebruik |
|---|---|
| `minimal` | Demonstratie/eenvoudig lokaal: alleen statisch, geen enkele optie ingeschakeld |
| `standard` | Statische site of kleine productie: gebruikelijke headers, basis-CSP, mapoverzicht/CGI/FastCGI uitgeschakeld |
| `hardened` | Blootstelling met minimale rechten: standaard lokale bind (reverse proxy aanbevolen voor internet), methoden beperkt tot GET/HEAD, strikte CSP, anti-slowloris — de WAF wordt **nooit** automatisch ingeschakeld, ook hier niet |
| `development` | Alleen lokale ontwikkeling, nooit voorgesteld als geschikt voor internet: loopback-bind verplicht, CSP in report-only, gedetailleerde foutpagina's |

Volgorde van het samenvoegen van de configuratie: ingebouwde veilige waarden → gekozen profiel → momenteel actieve opties blijven behouden (overleven een profielwissel) → expliciete gebruikersoverlay. Vóór het schrijven wordt altijd een volledige diff getoond (`profile apply`).

## 6. Architectuur

Clean Architecture (`core / domain / ports / application / infrastructure / interfaces / bootstrap`) — `bootstrap/` is de compositiewortel (equivalent van `app/` van de andere tools van de suite). Een bewuste eigenaardigheid van dit project, gecontroleerd door `import-linter` in plaats van aangenomen: `application/server/start_server.py` (en `validate_config.py`, `run_audit.py`) spelen de rol van een **fabriek die afhangt van de echte configuratie** (welke dienstbeheerder, de WAF wel of niet inschakelen...) en instantiëren concrete `infrastructure/`-adapters rechtstreeks — anders dan het strengere patroon van CHECK/TRACK, waar `application/` alleen `ports/` gebruikt. De enige universele regel die echt wordt afgedwongen: `domain/`/`core/` hangen nooit af van de buitenste lagen.

```text
src/omega_serv/
├── core/            Overkoepelende woordenschat (platform_info, constanten)
├── domain/           Pure domeinlogica (HTTP, configuratie, beveiliging WAF/TLS/auth/audit, routering)
├── ports/            Contracten (Protocol) die de applicatie verwacht
├── application/      Use-cases - sommige functies (build_server...) stellen ook concrete adapters samen (zie hierboven)
├── infrastructure/    Echte implementaties (asyncio, openssl als subproces, systemd/OpenRC/runit, bestanden)
├── interfaces/cli/    Niet-interactieve argparse-CLI
├── interfaces/tui/    Interactieve Textual-interface (dezelfde use-cases, nooit gedupliceerde logica)
└── bootstrap/         DependencyContainer, bepaling van de projectwortel
```

Regels gecontroleerd door `import-linter` (8 contracten): `domain`/`core` nooit afhankelijk van de buitenste lagen; `interfaces.tui` nooit rechtstreeks afhankelijk van `infrastructure`; `textual` beperkt tot `interfaces.tui`; `subprocess` beperkt tot `infrastructure/process/subprocess_runner.py` (en `infrastructure/lnav/`, interactieve PTY-stroom); `ssl` beperkt tot `infrastructure/tls/ssl_context_builder.py`; `jinja2` beperkt tot `infrastructure/exporters/html_exporter.py`; `sqlite3` beperkt tot `infrastructure/persistence/sqlite_active_defense_connection.py` (enige relationele opslag van het project, voorbehouden aan Active Defense — zie §11); `lupa` beperkt tot `infrastructure/waf/lua_waf_adapter.py` (aanvullend WAF-script « magnet », §7).

## 7. Optionele modules

In alle meegeleverde profielen standaard uitgeschakeld — inschakelen altijd expliciet (`option enable <naam>` of `config enable-tls`):

| Module | Rol |
|---|---|
| `waf` | Signaturen (gevoelige paden, scanner-UA/Referer, SQLi/XSS/CMDi in de body), als tekstbestand bewerkbare lijsten (trefwoorden, of gevoelige paden met `!`-uitzonderingen, Observatiemodus en eigen herhalingsregel per lijst — twee meegeleverde referenties, expliciet laden, zie §11b), snelheidsbeperking (token bucket, regels per map en per IP/netwerk, zie §11c), blokkeerlijst (CIDR + vervaldatum), reputatie/escalatie, import van een bestaand `mod_magnet`-WAF-script van Lighttpd als optionele versterking van het type « magnet » (zonder herschrijven, extra `pip install -e ".[magnet]"` — additief, kan nooit een native blokkade opheffen; compatibiliteitscontrole bij de import, eigen TUI-scherm) — modus `log-only` structureel niet in staat te blokkeren |
| TLS | Direct (zelfondertekend, lokale CA, of publiek via Let's Encrypt/Certbot met automatische vernieuwing — zie §9), nooit mTLS/OCSP in V1 |
| Authenticatie | HTTP Basic per zone (`url_prefix`), `hashlib.scrypt` met bescherming tegen timingaanvallen (constante tijd, ook voor een onbekende gebruiker) |
| FastCGI/PHP-FPM | Eén enkele `(url_prefix, script_root)`, `script_root` per constructie buiten `webroot/` gehouden (de statische handler kan nooit PHP-broncode prijsgeven) |
| Uitgaande reverse proxy | Omega-serv treedt zelf op als proxy naar één of meer backends (omgekeerde richting van `server.tls.mode = "behind_proxy"`) — lastverdeling (round-robin, gewogen, least-connections, ip-hash, least-response-time, echte belasting), sessie-affiniteit en routeringsregels op header, passieve en actieve gezondheid, antwoordcache (meerdere `Vary`-varianten), backpressure, lusbescherming, beheer-API tijdens bedrijf — zie §7a voor alle details |
| Upload | Afgeschermde zones, quota per zone, aan serverzijde gegenereerde bestandsnamen — geen streaming in V1 (begrensd door `server.max_request_size`) |
| `active_defense` | Deception + oorlogsmodus op basis van de al berekende WAF-signalen (nooit een tweede score): statische lokazen, gerichte vertraging/verrijkte logging/snelheidsbeperking, incidenten + IoC-export — zie §11 |

### 7a. Uitgaande reverse proxy — details

OMEGA-SERV kan zelf optreden als reverse proxy naar één of meer HTTP/HTTPS-backends — nooit te verwarren met `server.tls.mode = "behind_proxy"` (OMEGA-SERV **achter** een proxy, omgekeerd mechanisme). Zones configureerbaar met volledige CRUD (TUI: *Gedetailleerde configuratie → Reverse Proxy*), één of meer upstreams per zone.

- **Lastverdeling** — `round_robin` (standaard), `weighted_round_robin`/`weighted_least_connections`/`ip_hash` (gewogen), `least_connections`, `least_response_time`, `real_load` (echte belasting). Modus `real_load` native (sonde `/.omega-serv-load/`, hergebruikt dezelfde `psutil`-meting als het scherm « Status & bronnen », nooit een tweede aanroep) of declaratief (HTTP-sonde van derden, minimaal formaat `{"load_percent": ...}` of een kaal getal) — granulariteit per upstream, eenzelfde zone kan beide mengen.
- **Sessie-affiniteit en voorwaardelijke routering** — ondoorzichtige sticky cookie (de echte host:poort nooit zichtbaar voor de client) en regels op header (gelijkheid of prefix), beide gefilterd op de beschikbaarheid van de beoogde upstream (vallen netjes terug op de actieve strategie als de beoogde upstream niet beschikbaar is).
- **Gezondheid** — passief (opeenvolgende mislukkingen/successen, aparte omschakeldrempels down/up om flapping te beperken) **en** actief (periodieke sonde onafhankelijk van het echte verkeer, optioneel per upstream, hergebruikt hetzelfde achtergrondmechanisme als de echte belasting). Toestanden `DOWN` (altijd automatisch), `DRAINING`/`MAINTENANCE` (altijd handmatig, uitdrukkelijk tijdelijk, nooit opgeslagen) — een handmatig ingestelde upstream blijft uitgesloten van nieuwe keuzes zonder ooit een al gelegde verbinding te onderbreken. Automatische nieuwe poging op een andere upstream, alleen voor idempotente methoden (GET/HEAD/OPTIONS) en alleen bij een verbindingsfout.
- **Backpressure** — per upstream instelbaar plafond van actieve verbindingen; een verzadigde upstream weigert netjes met 503, te onderscheiden van een uitgevallen upstream (502, toch opnieuw geprobeerd).
- **Antwoordcache** — alleen GET/HEAD, nooit een foutantwoord, nooit `Set-Cookie` behalve bij expliciete opt-in per zone; respecteert `Cache-Control`/`Vary` van de upstream (uitschakelbare maar gevaarlijke optie, dezelfde filosofie als de TLS-controle). Meerdere varianten van eenzelfde bron (`Vary`) bestaan echt naast elkaar op schijf, nooit een simpel « de laatste wint ». Anti-stampede-vergrendeling (slechts één gelijktijdig verzoek bouwt de cache echt opnieuw op). Diagnoseheader `X-Omega-Cache: HIT`/`MISS`/`BYPASS` bij elk antwoord. Toezicht/opschonen in een eigen TUI-scherm (*Reverse-proxycache*).
- **Lusbescherming** — hop-by-hop-headers verwijderd, `X-Forwarded-*` altijd overschreven (nooit samengevoegd met die van de client), teller `X-Omega-Proxy-Hops` bij elke doorgifte verhoogd (nette weigering boven 5 sprongen — detecteert een indirecte lus tussen twee instanties, die een simpele lokale configuratiecontrole nooit kan zien).
- **WebSocket** — upgrade per zone toe te staan, één enkele upstream vastgelegd voor de hele duur van de tunnel zodra die is opgezet, zonder applicatietime-out.
- **Beheer tijdens bedrijf** — kleine lokale HTTP-API (`/.omega-serv-admin/`, net als de native belastingsonde beschermd door `trusted_proxy`) waarmee de TUI de toestand DRAINING/MAINTENANCE van een backend kan lezen/afdwingen en de hit/miss-ratio van de cache **van de daadwerkelijk draaiende server** kan lezen (eigen scherm *Live status van de backends*) — omdat TUI en server twee aparte processen zonder gedeeld geheugen blijven, is dit lokale HTTP-kanaal de enige brug tussen beide.

## 8. HTTP-verharding (niet uitschakelbaar)

- Header/verzoekregel begrensd **tijdens** het lezen (nooit achteraf), verouderd vouwen van headers geweigerd, `Transfer-Encoding` altijd geweigerd (nooit geraden).
- Dubbele `Content-Length` afgewezen; `Expect: 100-continue` netjes afgewezen (417).
- Expliciete whitelist van methoden (anders 405 + `Allow`), `Host`-header gevalideerd (ontbrekend/leeg/dubbel-zelfs-identiek/stuurteken → 400).
- Beveiligingsheaders en basis-CSP (`enforce`/`report-only`) toegepast op **elk** antwoord, ook op fouten — niet te omzeilen met een optie. `Cross-Origin-Opener-Policy`/`Cross-Origin-Resource-Policy` altijd `same-origin`, zonder echt risico een site te breken. `Cross-Origin-Embedder-Policy` altijd expliciet verzonden (nooit afwezig — een externe scanner onderscheidt zo « niet overwogen » van « bewust permissief »), standaard `unsafe-none` in **alle** profielen inclusief `hardened`: anders dan de twee vorige kunnen `require-corp`/`credentialless` cross-origin bronnen (lettertypen, afbeeldingen, iframes van derden) blokkeren die bij de daadwerkelijk geserveerde site horen — instelbaar (`security.coep_mode`). CSP-zones (`security.csp_zones`): **expliciete** uitzonderingen per padprefix (bv. `unsafe-inline` alleen onder `/een-map/` die het echt nodig heeft), elk vervangt het standaardbeleid voor zijn prefix volledig — nooit een samenvoeging, nooit een globale versoepeling; elke uitzondering blijft zichtbaar in `audit security` (CSP-001/CSP-002 scannen ook de zones), ook als die bewust is. Aanmaak begeleid door een assistent richtlijn voor richtlijn (scherm **Algemene beveiliging**), elk veld vooraf ingevuld met de **huidige** waarde van het globale beleid — om alleen te wijzigen wat moet veranderen, in plaats van te beginnen met een leeg veld dat ongewild de andere richtlijnen zou opofferen; een extra expliciete bevestiging wordt gevraagd als de samengestelde zone `unsafe-inline`/`unsafe-eval`/een generieke bron `*` versoepelt.
- IPv4-gemapte IPv6-adressen (`::ffff:x.x.x.x`) genormaliseerd vóór elke vergelijking (blokkeerlijst, vertrouwde proxy, snelheidsbeperking) — anders een bekende omzeiling.
- Gecontroleerd met eigenschapstests (`hypothesis`, duizenden gegenereerde voorbeelden) op de HTTP-parser en de padresolver, naast de klassieke unit-/integratietests.

## 9. TLS

### 9a. Zelfondertekend certificaat (minimaal)

Dekt het realistische gebruik lokaal/lab/VPN (Tailscale...): één listener, direct `ssl.SSLContext`, RSA 2048/4096 of ECDSA P-256/P-384.

### 9b. Lokale CA

Voor meerdere clientapparaten die moeten vertrouwen zonder een certificaat afzonderlijk opnieuw te importeren: een lokale certificeringsinstantie ondertekent zoveel servercertificaten als nodig.

```text
secure/certificates/ca/
├── root-ca.key    # 0600 - het gevoeligste element van het project
├── root-ca.pem    # 0644 - te importeren in de vertrouwensopslag van de clients
├── serial.txt     # 0600 - bijhouden van het volgende serienummer
└── index.txt      # 0600 - bijhouden van de status V(alid)/R(evoked) per ondertekend certificaat
```

Verloop: `certs generate-ca` (wachtwoordzin van de CA-sleutel **verplicht**, interactieve invoer met dubbele bevestiging als `--password` ontbreekt) → `certs generate-csr` (sleutel + server-CSR) → `certs sign-csr` (ondertekent met de CA, neemt de SAN van de CSR over, bouwt op verzoek `fullchain.pem`) → `tls.certificate.certificate_path` naar die `fullchain.pem` laten wijzen. Een gecompromitteerd certificaat wordt ingetrokken met `certs revoke` (markeert `index.txt`, controleert eerst of het certificaat wel van deze CA komt — weigert anders). Geen CRL-distributie in V1, geen externe CA/CSR voor een derde instantie, geen mTLS (zie §15).

### 9c. Let's Encrypt / ACME (Certbot) — publiek, zelf gehost

Voor een echt publieke site met een door browsers erkend certificaat, volledig zelf gehost schema: DDNS (Dynu of gelijkwaardig, volledig de verantwoordelijkheid van de beheerder) → Certbot → Omega-serv. Alleen een TUI-assistent (`Gedetailleerde configuratie → TLS → Let's Encrypt-assistent`) — roept `certbot certonly --webroot` aan als subproces (**nooit** `--standalone`, poort 80 is al bezet door Omega-serv; **nooit** een opnieuw geïmplementeerde ACME-client) met `--config-dir`/`--work-dir`/`--logs-dir` onder `secure/certificates/letsencrypt/` van het project — **nooit** `/etc/letsencrypt/` —, waardoor Certbot zelf volledig zonder privileges draait. Het verkregen certificaat wordt automatisch geïmporteerd (hetzelfde mechanisme als `certs import`, zie de CLI-voorbeelden hierboven) en er wordt een hookscript voor de vernieuwing geschreven. Testmodus (staging) standaard aangevinkt — uit te vinken zodra domein/webroot als werkend zijn gecontroleerd, om de echte snelheidslimieten van Let's Encrypt te vermijden.

Vereisten volledig buiten de reikwijdte van Omega-serv: domein dat naar het publieke IP wijst (DDNS), en poorten 80/443 doorgestuurd naar deze machine.

### 9d. Automatische vernieuwing (Certbot)

`Gedetailleerde configuratie → TLS → Automatische vernieuwing` past zich aan de daadwerkelijk gedetecteerde dienstbeheerder aan **voor deze instantie** (nooit een mechanisme gedeeld tussen meerdere instanties): systemd → genereert en installeert een timer (`<service>-certbot-renew.timer`, twee keer per dag + willekeurige vertraging, `certbot renew` beperkt tot de `--config-dir` van de instantie); anders → crontab-regel (huidige gebruiker, geen privileges) als `crontab` beschikbaar is; anders → getoonde handmatige instructies, geen geforceerd schrijven. Op sommige distributies (waaronder Arch/Manjaro) installeert het Certbot-pakket standaard **geen** timer, anders dan Debian/Ubuntu — vandaar dit scherm in plaats van een simpele controle van een verondersteld al aanwezig mechanisme. Eenmaal ingesteld importeert de vernieuwing elk vernieuwd certificaat automatisch opnieuw (`certs import`) en herstart daarna de dienst, zonder ooit nog handmatig in te grijpen.

## 10. Beveiligingsaudit

`audit security` is **niet blokkerend**: het voert de al blokkerende controles van `config check` opnieuw uit als `CRITICAL` en past daarna adviserende regels toe (TLS, CSP, gevaarlijke methoden, time-outs, uploadhygiëne puur; bestandsrechten, verlopen van certificaten, geïnstalleerde systemd-unit, loggrootte met echte I/O). `WAF-001` (WAF in `log-only` gebleven) wordt in de tijd gevolgd via een klein statusbestand (`var/run/waf-mode-state.json`) — gaat pas af na ≥14 waargenomen dagen in `log-only` over herhaalde uitvoeringen, niet bij de eerste `audit`.

## 11. Active Defense (deception + oorlogsmodus)

Optionele module (`option enable active_defense`, standaard uitgeschakeld) die vijandig gedrag kwalificeert op basis van de al berekende WAF-signalen (`WafDecision`/reputatie/blokkeerlijst — nooit een tweede, onafhankelijke scoreberekening) en een bron naar een lokaas kan omleiden, haar antwoorden kan vertragen en fijner kan loggen, een bruikbaar incident kan opbouwen en daarna indicatoren van compromittering (IoC) kan exporteren. Blokkeert het verkeer nooit zelf — de netwerkblokkade blijft de taak van `omega-fire`; Active Defense observeert, leidt om, vertraagt en legt vast.

**Dreigingen en score**: elke bron (`IP + SHA-256-hash van de User-Agent`) bouwt een score op (`WAF-001` blokkerend +10, reputatie-escalatie +25, bekende ban +25, POST op een al toegewezen lokaas +30 — afname van -5 per 15 minuten zonder nieuwe gebeurtenis), gekwalificeerd als `normal`/`suspicious`/`hostile`/`contained` (`contained` vereist bovendien een al bekende ban). `mode: monitor` observeert zonder te handelen; `mode: enforce` past de onderstaande acties echt toe.

**Oorlogsmodus** (`options.active_defense.settings.war_mode`): een `DefensePlaybook` (`actions: ["redirect_to_decoy", "enrich_log", "delay", "rate_limit", "create_incident", "export_ioc"]`), geactiveerd door instelbare drempels, voor elke bron die niet `normal` is:
- `enrich_log` — aparte JSONL-log (`var/log/active-defense-enriched.jsonl`, nooit vermengd met de WAF-/productielog), headers geredigeerd, HTTP-body gehasht (SHA-256) of ingekort volgens `logging.capture_request_body`.
- `delay` — begrensde vertraging met jitter (`war_mode.slowdown.minimum_ms`/`maximum_ms`/`jitter_ms`), nooit een blokkade van de asyncio-lus.
- `rate_limit` — eigen snelheidsbeperking per bron (`war_mode.rate_limit.requests`/`window_seconds`), hergebruikt hetzelfde mechanisme als de WAF onder een aparte sleutel.
- `create_incident` — automatisch openen/samenvoegen van een incident bij het overschrijden van `thresholds.incident_score`.

**Deception**: een bron `hostile`/`contained` kan worden toegewezen aan een statisch lokaas (`fake_admin`, `fake_cms`, `fake_api`, `fake_secrets` — plausibele maar altijd vaste antwoorden, nooit echt lezen van bestanden of subprocessen), gekozen volgens de waargenomen aanvalsklasse (`deception.profiles.<naam>.match_attack_classes`, één of meer uit `scan`/`credential_stuffing`/`sqli`/`xss`/`path_traversal`/`upload_probe`/`api_probe`/`unknown`). Twee isolatieniveaus, bewust gekozen en als zodanig gedocumenteerd:
- **Niveau 1** (fixture in het proces, `isolation_level: "fixture"`, standaard) — uitdrukkelijk ZWAKKE isolatie: hetzelfde proces, dezelfde OS-gebruiker als de productie, alleen aanvaardbaar omdat de fixture nooit iets anders doet dan een statisch sjabloon teruggeven. De NAAM van het profiel moet exact overeenkomen met een van de 4 fixtures hierboven — anders afgewezen bij de validatie (`validate_active_defense_config`), om de valkuil te vermijden van een verkeerd benoemd lokaas dat dan stilzwijgend nooit afgaat.
- **Niveau 2** (echt geïsoleerde backend, `isolation_level: "proxy"`) — doorgegeven aan een apart proces via `options.active_defense.settings.deception.decoy_zones.<naam>` (upstream `host`/`port` van een al draaiende server, nooit automatisch aangemaakt; nooit gelezen uit `options.reverse_proxy` — een lokaas kan nooit per ongeluk naar een productiezone wijzen, gecontroleerd bij `config check`), met hergebruik van hetzelfde uitgaande reverse-proxymechanisme als de productie (`serve_proxy()` — upstream onbereikbaar op het moment van een echt verzoek: 502 naar de aanvaller, nooit een crash).

**Scherm Instellingen** (TUI, Actieve beveiliging → Active Defense → Instellingen): volledige configuratie van al het voorgaande — modus, inschakelen van de oorlogsmodus, bereik/acties/drempels/vertraging/verzoeklimiet, deception (standaardgedrag, CRUD van de lokaasprofielen en lokaaszones met voorbeeldwaarden in elk veld), IoC, opslag en logging — vóór elke opslag gevalideerd met dezelfde regels als de CLI, zonder ooit `config/omega-serve.json` handmatig te hoeven bewerken. Na elke wijziging is systematisch een volledige herstart nodig (Active Defense wordt nooit tijdens bedrijf herladen).

**Incidenten en IoC**: volledige tijdlijn per incident, extractie van indicatoren (IP, gehashte User-Agent), geversioneerde JSON-export/CSV beperkt tot deelbare IoC/Markdown-rapport, en de uitwisselingsformaten **STIX 2.1** (bundel om in OpenCTI, een SIEM… te laden) en **MISP** (gebeurtenis om via de MISP-interface te importeren), standaard gemarkeerd TLP:AMBER — lokale bestanden, nooit verzonden; elke export vergezeld van een bestand `<export>.sha256` (standaardformaat `sha256sum`). Automatische export bij het sluiten van een incident als `ioc.auto_export_on_close` (standaard waar). Verlopen toestanden en het auditlog worden automatisch opgeschoond en de database is begrensd (bescherming tegen het vollopen van de schijf); `active-defense purge` sluit daarnaast weer stil geworden incidenten.

**Simulatie**: `active-defense simulate` (CLI) en de knop "Simuleren" (TUI, scherm Actieve beveiliging) projecteren score/niveau en leggen elke actie uit die zou worden geactiveerd — strikte dry-run, geen echt schrijven, geen impact op het netwerk.

Back-up/herstel: `config backup --include-active-defense` neemt de sqlite-database (dreigingen/incidenten/toewijzingen) op in het archief — nooit geheimen in platte tekst, dus geen `--confirm-secrets` nodig, anders dan bij `--include-auth`.

## 11b. Lijsten van gevoelige paden (WAF)

De WAF kan **bewerkbare lijsten** als tekstbestand laden, één pad (of trefwoord) per regel, via **Actieve beveiliging → Custom → Toevoegen → « Een lijst LADEN »**. Standaard wordt nooit iets geladen: het is een expliciete actie.

- **Meegeleverde referenties**: `sensitive-paths-hostile` (298 paden zonder legitiem gebruik: geheimen, back-ups, VCS, consoles…) en `sensitive-paths-probe` (132 verkenningspaden, soms door een echte site geserveerd: `/admin`, `/api`, monitoring…). Bij het laden wordt een **lokale kopie** gemaakt in `secure/waf/rules/keywords/`: die bewerkt u, een update van omega-serv overschrijft haar nooit (« Nieuw in de referentie » stelt daarna, vakje per vakje, de nieuwe items voor).
- **Syntaxis**: `/admin` (→ `/admin` en `/admin/xxx`, nooit `/administrator`), `/.git/` (alles eronder), `/*.bak` (extensie), `!/api/v1` (uitzondering, altijd voorrang). Paden gedecodeerd zoals in de engine (`%2e`, dubbele codering, tekens op volle breedte).
- **Ernst**: *Observatie* (alleen log, aanbevolen bij het eerste laden), daarna Gemiddeld (blokkeert nooit alleen) of Hoog (403 vanaf de eerste toegang).
- **Eigen herhalingsregel per lijst**: 1e toegang = informatie of weigering; N toegangen in M minuten = tijdelijke applicatieban (antwoord 451, ook via Tailscale); herhaalde blokkades = netwerkban door omega-jail. Referenties: hostile 2 toegangen in 10 min → 24 u, verkenning 5 in 10 min → 1 u.
- **Nooit een automatische ban** voor de lokale host, Tailscale (`100.64.0.0/10`) en het lokale netwerk (`options.waf.reputation.never_auto_block`): alleen extern verkeer kan worden gebannen. Achter een lokale proxy vereist de uitzondering voor `127.0.0.1` een actieve `trusted_proxy`. `X-Forwarded-For` wordt van rechts naar links gelezen: een client kan zichzelf niet als lokaal opgeven.
- **Vangrails**: beschermde vitale paden (`/`, `robots.txt`, `sitemap.xml`, `/.well-known/acme-challenge/`…), weigering van een blokkerende lijst die een daadwerkelijk geserveerde route zou raken (alias, reverse proxy, Auth-zone, webroot), **« Controleren tegen mijn logs »** in de editor (regels die geslaagde verzoeken zouden hebben geraakt, uitzondering met één klik).
- **Geïntegreerde editor**: live diagnose met regelnummer, een pad « Testen », veilig schrijven (rechten en groep behouden, symbolische links geweigerd, externe wijziging gedetecteerd), leesbaarheid voor het dienstaccount gecontroleerd (« Rechten herstellen ») en **eerlijke** herlading: geweigerd met de reden als de lijst de controle niet doorstaat, waarbij de server dan zijn huidige regels behoudt.

## 11c. Snelheidsbeperking per map en per IP/netwerk (WAF)

De snelheidsbeperking van de WAF (token bucket, `options.waf.rate_limit`, standaard 60 verzoeken / 60 s per IP) kan worden verfijnd via **Actieve beveiliging → Uitzonderingen en limiet** (of met de hand, `rate_limit.path_policies` / `rate_limit.source_policies`):

- **Regel per map** (`prefix`, `requests`, `window_seconds`): die **vervangt** de globale limiet voor die map, met een eigen teller (`requests: 0` = onbeperkt). Het langste voorvoegsel wint; `/images` dekt `/images/a.png`, nooit `/images2`. Typisch een zware pagina (afbeeldingengalerij) die 429 teruggeeft.
- **Regel per IP/netwerk** (`network`, `requests`, `window_seconds`, `trusted`): zelfde principe; het meest precieze netwerk wint. Prioriteit: map, dan IP/netwerk, dan de globale limiet.
- **Bannen ongewijzigd voor het publiek**: een overschrijding door een publiek IP wordt nog steeds als `"action": "block"` in `waf-alerts.log` gelogd en kan dus door omega-jail worden geband (3 weigeringen in 10 min → 12 u). Een **veilige bron** — een `never_auto_block`-netwerk of een regel gemarkeerd `trusted: true` — krijgt nog steeds de 429 maar wordt gelogd als `"action": "throttle"`, wat de jail nooit telt.
- **Magnet-script**: zijn eigen snelheidsbeperking (429-respons) telt nooit als een detectie en leidt dus nooit tot een automatische ban; bij een verzoek dat onder een map- of IP/netwerkregel valt, geldt de native regel en wordt de 429 van magnet genegeerd (zijn aanvalssignaturen blijven gelden).
- Een snelheidsregel schakelt de WAF-inspectie **nooit** uit; omgekeerd heft een inspectie-uitzondering (`exclusions.path_prefixes`) de snelheidsbeperking nooit op. Zonder actieve `trusted_proxy` wordt een regel voor `127.0.0.1`/`::1` genegeerd (dezelfde beveiliging als `never_auto_block`).

## 12. Diensten en beheer

Automatische detectie van systemd/OpenRC/runit (`service install/status/start/stop/restart/enable/disable/uninstall`). De gegenereerde systemd-unit past standaard een niet-onderhandelbare verharding toe: `NoNewPrivileges`, `PrivateTmp`, `ProtectSystem=strict`, `ProtectHome`, `ReadWritePaths` beperkt tot `var/`, speciale gebruiker/groep verplicht, `UMask=0077`, `Restart=on-failure`. Net afsluiten bij SIGTERM (afhandelen van lopende verbindingen, instelbare respijttijd en daarna geforceerd sluiten); herladen tijdens bedrijf bij SIGHUP (alleen WAF-regels en Auth-zones — bind/poort/TLS en Active Defense nooit te wijzigen zonder volledige herstart).

## 13. Logboeken

`var/log/access.log` (Apache combined-formaat + `request_id`, escaping tegen loginjectie), `var/log/error.log`. Rotatie op grootte/aantal bewaarde bestanden (`logs.rotation`). Native WAF: `var/log/waf-alerts.log` (`options.waf.logging.path`). Magnet-script (§7): `options.waf.magnet.paths.alerts_log`/`.blocklist_log`, standaardwaarden `var/log/waf-magnet-alerts.log`/`var/log/waf-magnet-blocklist.log` — alleen automatisch aan de Bibliotheek toegevoegd (knop *Bekende Omega-Serv-logs toevoegen*) als magnet actief is; `lnav` stelt ze daarentegen altijd voor (een ontbrekend bestand wordt bij het starten gewoon genegeerd).

### 13a. Externe bronnen (SSH)

Centraliseert op uitdrukkelijk verzoek de log van een backendserver op hetzelfde lokale netwerk achter de reverse proxy (scherm **Logbeheer → Bibliotheek → Externe bronnen (SSH)**). Een « fetch » is een handmatige, eenmalige actie, nooit een live stroom of automatische polling: een **kopie** wordt via `scp` opgehaald op het moment van de klik op *Nu ophalen*, geschreven onder `var/log/remote/` en daarna als een gewone log aan de Bibliotheek toegevoegd (kolom *Toegang* = `ssh`, kolom *Gewijzigd* = datum van **deze** ophaling — nooit die van het externe bestand); een nieuwe ophaling vervangt gewoon de vorige kopie door een recentere.

Bewuste vangrails (zie `OMEGA-SERV_ETUDE-FAISABILITE_LOGS_DISTANTS.md` voor de volledige studie): geen automatische netwerkscan, geen verbinding zonder expliciete configuratie (label/host/extern pad, gebruiker/poort/privésleutel optioneel — leeg laten ze `ssh`/`~/.ssh/config` beslissen alsof de opdracht met de hand werd getypt), nooit wordt een wachtwoord gevraagd of opgeslagen (een privésleutel wordt alleen via zijn pad gerefereerd, nooit door Omega-serv gelezen of opgeslagen), geen groottecontrole vóór de overdracht. Capaciteit `scp` lokaal gedetecteerd in het **Capaciteitenregister** (alleen aanwezigheid van het programma, nooit een bereikbaarheidstest van een host); Samba bewust buiten beschouwing gelaten (YAGNI, zolang er geen echte behoefte wordt bevestigd).

## 14. Tests

```bash
source .venv/bin/activate
lint-imports        # controleert de 8 laagcontracten
pytest -q           # 2485 tests
ruff check .
mypy src
```

Structuur: `tests/unit/` (domein/applicatie, test-doubles), `tests/integration/` (echte asyncio-server op echte TCP-sockets, echte `openssl` als subproces, echte CLI-opdrachten tegen een volledig tijdelijk project, interactieve interface via de `Pilot`-API van Textual - nooit screenshots), `tests/security/` (`hypothesis`-eigenschapstests op de HTTP-parser en de padresolver).

## 15. Buiten de reikwijdte

- Kale CGI (alleen FastCGI/PHP-FPM)
- mTLS (clientauthenticatie via certificaat), OCSP-stapling
- Externe CA / CSR voor een derde instantie, volledige CRL-distributie
- Active Defense: echte integratie met de ban-gebeurtenissen van `omega-fire` (geblokkeerd aan de kant van `omega-fire`, dat vandaag geen enkele leesinterface biedt)

---

> 🔒 OMEGA-SERV — Een robuuste, complete, veilige en defensieve webserver.
