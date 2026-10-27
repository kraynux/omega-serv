<!-- Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE) -->

# omega-serv vergeleken met de webservers op de markt

**Gemeten vergelijking: nginx · lighttpd · Caddy · Apache · Traefik · omega-serv 2.0**

🌐 [Français](../../comparatif-serveurs-web.md) · [English](../en/comparatif-serveurs-web.md) · [Español](../es/comparatif-serveurs-web.md) · [Português (Brasil)](../pt-BR/comparatif-serveurs-web.md) · [Italiano](../it/comparatif-serveurs-web.md) · [Deutsch](../de/comparatif-serveurs-web.md) · **Nederlands** · [Polski](../pl/comparatif-serveurs-web.md) · [Русский](../ru/comparatif-serveurs-web.md) · [中文](../zh-CN/comparatif-serveurs-web.md) · [Tiếng Việt](../vi/comparatif-serveurs-web.md) · [ไทย](../th/comparatif-serveurs-web.md) · [Bahasa Indonesia](../id/comparatif-serveurs-web.md) · [日本語](../ja/comparatif-serveurs-web.md) · [한국어](../ko/comparatif-serveurs-web.md) · [हिन्दी](../hi/comparatif-serveurs-web.md) · [العربية](../ar/comparatif-serveurs-web.md)

Dit document plaatst omega-serv tussen de meest gebruikte webservers. Het wil geen „beste server” aanwijzen: elk hulpmiddel beantwoordt aan andere behoeften. Het biedt drie dingen:

1. **echte metingen**, gedaan op dezelfde machine, met dezelfde client en dezelfde bestanden, en reproduceerbaar;
2. een **functievergelijking**, waarbij elke functie is nagekeken in de officiële documentatie van elke server (links aan het einde van het document), met onderscheid tussen wat ingebouwd is en wat een module of plugin vereist;
3. wat omega-serv **werkelijk extra biedt**, en wat de anderen **beter doen**.

Alle onderstaande cijfers zijn gemeten op 26 oktober 2026. Geen enkel cijfer is overgenomen van een andere website of geschat.

---

## Inhoud

1. [In het kort](#1-in-het-kort)
2. [Meetmethode](#2-meetmethode)
3. [Prestaties: omega-serv tegenover nginx, lighttpd en Caddy](#3-prestaties-omega-serv-tegenover-nginx-lighttpd-en-caddy)
4. [omega-serv 1.0 → 2.0: wat er veranderd is, gemeten](#4-omega-serv-10--20-wat-er-veranderd-is-gemeten)
5. [Functievergelijking](#5-functievergelijking)
6. [Beheer en gebruiksgemak](#6-beheer-en-gebruiksgemak)
7. [Wat omega-serv extra biedt](#7-wat-omega-serv-extra-biedt)
8. [Wat de anderen beter doen](#8-wat-de-anderen-beter-doen)
9. [Welke server voor welk gebruik](#9-welke-server-voor-welk-gebruik)
10. [De metingen reproduceren](#10-de-metingen-reproduceren)
11. [Bronnen](#11-bronnen)

---

## 1. In het kort

- **Ruwe doorvoer bij kleine bestanden**: nginx en lighttpd, geschreven in C, verwerken **10 tot 20 keer meer** verzoeken per seconde dan omega-serv, geschreven in Python. Caddy, geschreven in Go, zit daartussen. Dit is een verschil in aard, niet in afstelling: omega-serv richt zich niet op dit terrein.
- **Grote bestanden**: sinds 2.0 laat omega-serv het verzenden over aan de kernel (`sendfile`). Het haalt dan op deze machine **dezelfde orde van grootte** als nginx, lighttpd en Caddy: 2,1 GB/s tegenover 2,0 tot 2,4 GB/s.
- **Geheugen**: lighttpd (1 MB) en nginx (4 tot 5 MB) blijven onbereikbaar. omega-serv blijft onder belasting met 1 proces onder 30 MB, Caddy rond 55 MB.
- **Van 1.0 naar 2.0**: doorvoer bij grote bestanden maal 2,8; geheugen tijdens grote downloads gedeeld door 45; tot +50% bij kleine bestanden met 2 processen (boostmodus); kosten van Active Defense gedeeld door 12.
- **Wat omega-serv extra heeft**: volledig beheer via een terminalinterface (TUI), in 17 talen; een ingebouwde WAF en actieve verdediging; beveiligingslimieten die exact blijven met meerdere processen; import van lighttpd-mod_magnet-scripts; beheer van meerdere instanties.
- **Wat het niet heeft**: HTTP/2 en HTTP/3, service discovery voor Docker/Kubernetes, een ingebouwde ACME-client (het gebruikt Certbot), de doorvoer van een server die in C is geschreven.

---

## 2. Meetmethode

### Machine en software

| Onderdeel | Waarde |
|---|---|
| Processor | Intel Core i5 M480 op 2,67 GHz (2010): 2 fysieke kernen, 4 threads |
| Geheugen | 8 GB |
| Systeem | Manjaro Linux, kernel 6.18 |
| Netwerk | loopback (127.0.0.1) |
| Belastingsclient | [oha](https://github.com/hatoo/oha) 1.16.0 (geschreven in Rust) |
| nginx | 1.30.4 (Manjaro-pakket) |
| lighttpd | 1.4.85 (Manjaro-pakket) |
| Caddy | 2.11.4 (Manjaro-pakket) |
| omega-serv | 1.0.0 (gepubliceerd archief) en 2.0.0, onder Python 3.14.7 |

Apache en Traefik zijn niet gemeten, omdat ze niet op deze machine geïnstalleerd waren. Traefik is bovendien geen bestandsserver (zie §5). Deze twee servers komen dus alleen voor in de functievergelijking.

### Protocol

- **Isolatie van de processor**: elke server is vastgezet op fysieke kern 0 (threads 0 en 2), de client op fysieke kern 1 (threads 1 en 3). Zo steelt de client geen tijd van de server, en hebben alle servers exact dezelfde middelen.
- **Dezelfde bestanden voor iedereen**: `small.html` (1 KB), `medium.png` (100 KB) en `large.bin` (5 MB), geserveerd vanuit dezelfde map.
- **Toegangslog overal ingeschakeld**, want een productieserver logt.
- **Onversleuteld HTTP/1.1, blijvende verbindingen (keep-alive)**. De gelijktijdigheid is 32 verbindingen voor de bestanden van 1 KB en 100 KB, en 8 voor het bestand van 5 MB.
- **Duur**: 10 seconden per bestand en per configuratie.
- **Herhalingen**: 3 volledige, verweven rondes (alle servers in ronde 1, dan alle in ronde 2, enz.). De tabellen geven de **mediaan** van de drie rondes.
- **Geheugen**: PSS (*Proportional Set Size*), opgeteld over alle processen van de server. Anders dan bij RSS wordt een pagina die tussen processen gedeeld wordt maar één keer geteld. Gemeten in rust en na de belasting.
- **Configuraties**: nginx, lighttpd en Caddy in hun basisconfiguratie (statische bestanden, toegangslog). omega-serv gebruikt het profiel `standard`, met de WAF uitgeschakeld en daarna ingeschakeld met alle meegeleverde regels.
- **Aantal processen**: elke server wordt gemeten met 1 en daarna met 2 processen (nginx `worker_processes`, lighttpd `server.max-worker`, Caddy `GOMAXPROCS`, omega-serv `server.workers`).

### Beperkingen om te kennen

- **Bescheiden en oude machine.** De absolute waarden zouden op een recente server veel hoger zijn. Wat zin heeft, zijn de **verhoudingen** tussen servers die in dezelfde sessie gemeten zijn.
- **Variatie tussen sessies**: ongeveer 10 tot 30% afhankelijk van de achtergrondbelasting van de machine. De rondes binnen één sessie blijven consistent: minder dan 5% verschil voor omega-serv en Caddy, meer voor nginx en lighttpd, waarvan de zeer hoge doorvoer gevoeliger is voor de rest van de machine.
- **Loopback**: de meting gaat niet over een echt netwerk. Op een echt netwerk wordt de doorvoer van grote bestanden bijna altijd beperkt door de bandbreedte, niet door de server.
- **Geen TLS** in deze metingen. Met HTTPS kan omega-serv `sendfile` niet gebruiken en verzendt het bestanden in blokken.
- **Ruwe cijfers**: ze worden met dit document gepubliceerd in [`docs/benchmarks/2026-10-26-campagne-brute.txt`](../../benchmarks/2026-10-26-campagne-brute.txt).

---

## 3. Prestaties: omega-serv tegenover nginx, lighttpd en Caddy

### Kleine bestanden (1 KB): verzoeken per seconde

| Server | 1 proces | 2 processen | Latentie p99 (1 proc.) |
|---|---:|---:|---:|
| lighttpd 1.4.85 | 25.521 | 29.700 | 4,5 ms |
| nginx 1.30.4 | 14.054 | 18.315 | 4,7 ms |
| Caddy 2.11.4 | 3.697 | 5.345 | 25,3 ms |
| **omega-serv 2.0** | **1.358** | **1.953** | **37,5 ms** |
| omega-serv 2.0 + WAF | 1.130 | 1.617 | 48,5 ms |
| omega-serv 1.0 | 1.304 | — | 41,2 ms |

### Middelgrote bestanden (100 KB): verzoeken per seconde

| Server | 1 proces | 2 processen |
|---|---:|---:|
| lighttpd | 11.635 | 13.037 |
| nginx | 8.024 | 9.555 |
| Caddy | 3.280 | 4.344 |
| **omega-serv 2.0** | **1.247** | **1.629** |
| omega-serv 2.0 + WAF | 1.012 | 1.347 |
| omega-serv 1.0 | 1.064 | — |

### Groot bestand (5 MB): doorvoer

| Server | 1 proces | 2 processen |
|---|---:|---:|
| lighttpd | 2.379 MB/s | 2.407 MB/s |
| nginx | 2.242 MB/s | 1.981 MB/s |
| Caddy | 2.165 MB/s | 2.229 MB/s |
| **omega-serv 2.0** | **1.658 MB/s** | **2.115 MB/s** |
| omega-serv 1.0 | 584 MB/s | — |

### Geheugen (PSS, alle processen van de server)

| Server | In rust | Na de belasting |
|---|---:|---:|
| lighttpd (1 of 2 proc.) | 1 MB | 1 MB |
| nginx (1 of 2 proc.) | 4 tot 5 MB | 4 tot 5 MB |
| **omega-serv 2.0 (1 proc.)** | **26 MB** | **30 MB** |
| omega-serv 2.0 (2 proc.) | 39 MB | 48 MB |
| Caddy | 50 MB | 56 MB |
| omega-serv 1.0 | 22 MB | 100 MB |

### Interpretatie

- **Bij kleine en middelgrote bestanden** is het verschil met nginx en lighttpd een orde van grootte (×10 tot ×20). Dat is de prijs van een server in Python: elk verzoek gaat door de interpreter, terwijl nginx en lighttpd het in gecompileerd C verwerken. De boostmodus verkleint het verschil, zonder het te dichten.
- **Bij grote bestanden** komen de servers dicht bij elkaar, omdat de kernel de gegevens kopieert (`sendfile`). Met 2 processen haalt omega-serv 2.0 2,1 GB/s, in hetzelfde gebied als de anderen (2,0 tot 2,4 GB/s).
- **De WAF van omega-serv kost ongeveer 17%** bij kleine bestanden: hij inspecteert elk verzoek. nginx, lighttpd en Caddy zijn zonder WAF gemeten; een WAF die aan deze servers wordt toegevoegd (ModSecurity, Coraza) kost ook prestaties, wat hier niet gemeten is.
- **Om deze cijfers te plaatsen**: 1.300 verzoeken per seconde is meer dan 110 miljoen verzoeken per dag op deze machine uit 2010. Dat ligt ver boven de behoeften van een persoonlijke site, een interne dienst of een lab, precies de toepassingen waarop omega-serv zich richt.

---

## 4. omega-serv 1.0 → 2.0: wat er veranderd is, gemeten

### Prestaties

Beide versies zijn in dezelfde sessie gemeten, op dezelfde machine en met hetzelfde protocol.

| Meting | 1.0.0 | 2.0.0 | Verandering |
|---|---:|---:|---:|
| Kleine bestanden (1 KB), 1 proces | 1.304 verz/s | 1.358 verz/s | +4% |
| Kleine bestanden (1 KB), boostmodus 2 processen | — | 1.953 verz/s | **+50%** t.o.v. 1.0 |
| Kleine bestanden met WAF, 1 proces | 1.097 verz/s | 1.130 verz/s | +3% |
| Kleine bestanden met WAF, 2 processen | — | 1.617 verz/s | **+47%** t.o.v. 1.0 |
| Bestanden van 100 KB, 1 proces | 1.064 verz/s | 1.247 verz/s | +17% |
| Groot bestand (5 MB), 1 proces | 584 MB/s | 1.658 MB/s | **×2,8** |
| Groot bestand (5 MB), 2 processen | — | 2.115 MB/s | **×3,6** t.o.v. 1.0 |
| Geheugen na de belasting, 1 proces | 100 MB | 30 MB | **÷3** |

### Gelijktijdige grote downloads

Test: 3 gelijktijdige downloads van een bestand van 300 MB, terwijl continu een kleine pagina wordt opgevraagd. Twee runs geven identieke resultaten.

| Meting | 1.0.0 | 2.0.0 |
|---|---:|---:|
| Piekgeheugen van de server | 1.835 MB | 40 MB |
| Kleine pagina tijdens de downloads: mediaan | 3 tot 4 ms | 2 ms |
| Kleine pagina tijdens de downloads: slechtste geval | 1,7 tot 1,8 s | 5 ms |

Versie 1.0 laadde elk bestand volledig in het geheugen voordat het verzonden werd. Versie 2.0 verzendt het in blokken of laat het over aan de kernel: het geheugen hangt niet meer af van de bestandsgrootte, en de server blijft reageren tijdens de downloads.

### Kosten van de actieve verdediging

Kosten van één dreigingsobservatie door Active Defense, voor elk verdacht verzoek, gemeten op schijf (ext4) over 2.000 observaties:

| Meting | 1.0.0 | 2.0.0 |
|---|---:|---:|
| Mediaan | 2,84 ms | 0,23 ms |
| p99 | 11,6 ms | 2,3 ms |
| Maximum | 18 tot 20 ms | 37 tot 46 ms |

De mediaan is gedeeld door 12. Het maximum is in 2.0 daarentegen hoger: enkele losse pieken, veroorzaakt door het periodiek wegschrijven van het SQLite-journaal naar schijf.

### Functies die met 2.0 zijn gekomen

**Bijwerken naar de marktstandaarden**: nginx, lighttpd, Caddy en Apache doen dit allemaal al. omega-serv haalt ze in.

- Voorwaardelijke verzoeken (ETag, Last-Modified, 304-antwoorden): bij het herladen van een pagina wordt alleen opnieuw gedownload wat veranderd is.
- Gedeeltelijke verzoeken (Range, 206/416): een download hervatten, vooruitspoelen in een video.
- Bestanden verzenden met `sendfile` of in blokken, met stabiel geheugen.
- Voorgecomprimeerde bestanden (`.gz`, `.br`) naast het origineel geplaatst.
- Standaard Cache-Control per bestandstype (afbeeldingen, lettertypen, CSS/JS), instelbaar.
- Meerdere serverprocessen (boostmodus, `server.workers`).

**Uitgebreidere functies:**

- **Volledige reverse proxy.** Versie 1.0 had alleen een eenvoudige doorgifte (om de beurt, TLS naar de upstream-server, WebSocket). Versie 2.0 voegt toe:
  - 6 verdeelstrategieën, 7 in totaal;
  - sessieaffiniteit en routering op header;
  - passieve en actieve gezondheidscontrole van de upstream-servers;
  - een antwoordcache;
  - bescherming tegen overbelasting en tegen lussen;
  - besturing tijdens bedrijf.
- **Limiet per map en per adres of netwerk**, naast de globale limiet.
- **Beveiligingstellers die tussen processen gedeeld worden** (zie §7).
- **Lijsten met gevoelige paden**, direct bruikbaar, met een observatiemodus en een ingebouwde editor.
- **Import van lighttpd-mod_magnet-scripts** (zie §7).
- **Interface in 17 talen**, met een aparte taal voor de pagina's die bezoekers zien en voor exports.
- **Logs volledig vernieuwd**:
  - een logbibliotheek;
  - drie viewers, waaronder lnav;
  - het ophalen van externe logs via SSH.

---

## 5. Functievergelijking

Legenda:
- ✅ ingebouwd;
- 🧩 officiële module van het project, in te schakelen of te installeren;
- 🔌 module of plugin van derden;
- ⚙️ via een extern hulpmiddel;
- ❌ afwezig.

„Commercieel” duidt een functie aan die voorbehouden is aan de betaalde editie.

### HTTP-levering

| Functie | nginx | lighttpd | Caddy | Apache | Traefik | omega-serv 2.0 |
|---|---|---|---|---|---|---|
| Statische bestanden serveren | ✅ | ✅ | ✅ | ✅ | ❌ (alleen proxy) | ✅ |
| ETag / 304 / Range | ✅ | ✅ | ✅ | ✅ | — | ✅ |
| Voorgecomprimeerde bestanden `.gz` / `.br` | ✅ `gzip_static` (`.br`: 🔌) | 🔌 Lua-script (mod_magnet) | ✅ `precompressed` | 🧩 mod_rewrite-recept | — | ✅ |
| Compressie on-the-fly | ✅ | ✅ mod_deflate | ✅ | 🧩 mod_deflate | ✅ middleware | ❌ |
| HTTP/2 | ✅ | ✅ | ✅ | 🧩 mod_http2 | ✅ | ❌ |
| HTTP/3 (QUIC) | ✅ | ❌ | ✅ | ❌ | ✅ | ❌ |
| PHP via FastCGI | ✅ | ✅ | ✅ | ✅ | ❌ | ✅ |
| Meerdere processen of kernen | ✅ workers | ⚠️ `max-worker`, afgeraden door de documentatie | ✅ (Go, alle kernen) | ✅ MPM | ✅ (Go) | ✅ `server.workers` |

### Reverse proxy

| Functie | nginx | lighttpd | Caddy | Apache | Traefik | omega-serv 2.0 |
|---|---|---|---|---|---|---|
| Lastverdeling | ✅ om de beurt, minste verbindingen, hash | ✅ fair, round-robin, hash, sticky | ✅ een twaalftal strategieën | 🧩 mod_proxy_balancer | ✅ wrr, p2c, hrw, least-time | ✅ 7 strategieën, waaronder de werkelijke belasting |
| Passieve gezondheid (een uitgevallen server uitsluiten) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Actieve gezondheid (periodieke controle) | Commercieel (NGINX Plus) | ❌ | ✅ | 🧩 mod_proxy_hcheck | ✅ | ✅ |
| Antwoordcache | ✅ `proxy_cache` | ❌ | 🔌 | 🧩 mod_cache | Commercieel | ✅ |
| WebSocket | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Service discovery (Docker, Kubernetes) | 🔌 | ❌ | 🔌 | ❌ | ✅ (kern van het project) | ❌ |

### TLS

| Functie | nginx | lighttpd | Caddy | Apache | Traefik | omega-serv 2.0 |
|---|---|---|---|---|---|---|
| Automatische certificaten (ACME, Let's Encrypt) | 🧩 `ngx_http_acme_module` | ⚙️ Certbot | ✅ standaard | 🧩 mod_md | ✅ | ⚙️ Certbot, met ingebouwde assistent en geplande vernieuwing |
| Lokale CA | ❌ | ❌ | ✅ interne CA (automatische uitgifte) | ❌ | ❌ | ✅ aanmaken, CSR ondertekenen, intrekken |

### Beveiliging

| Functie | nginx | lighttpd | Caddy | Apache | Traefik | omega-serv 2.0 |
|---|---|---|---|---|---|---|
| Limiet per client | ✅ `limit_req` | ⚠️ mod_evasive (alleen gelijktijdige verbindingen) | 🔌 caddy-ratelimit | 🔌 mod_evasive, mod_qos | ✅ middleware | ✅ |
| Limiet gedeeld tussen processen | ✅ gedeelde geheugenzone | ❌ per proces geteld | — (één proces) | afhankelijk van de module | 1 instantie; meerdere met Redis | ✅ gedeeld geheugen |
| WAF (SQLi/XSS-handtekeningen, scanners…) | 🔌 ModSecurity, Commercieel (App Protect) | ❌ (Lua-scripts zelf schrijven) | 🔌 Coraza | 🔌 ModSecurity | 🔌 plugins | ✅ ingebouwd |
| Blokkeerlijst met vervaldatum, recidive | ⚙️ fail2ban | ⚙️ fail2ban | ⚙️ fail2ban | ⚙️ fail2ban | ⚙️ | ✅ ingebouwd |
| Lokaas, oorlogsmodus, incidenten, IoC-export | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ Active Defense |
| Beveiligingsaudit van de configuratie | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ `audit security` |
| Observatiemodus (loggen zonder blokkeren) | afhankelijk van de module | — | afhankelijk van de plugin | ✅ ModSecurity `DetectionOnly` | afhankelijk van de plugin | ✅ |

### Uitbreidbaarheid

| Functie | nginx | lighttpd | Caddy | Apache | Traefik | omega-serv 2.0 |
|---|---|---|---|---|---|---|
| Scripttaal | 🧩 njs (JavaScript); 🔌 Lua (OpenResty) | ✅ Lua (mod_magnet) | Go-modules (hercompilatie) | 🧩 mod_lua | Go- of WebAssembly-plugins | 🔌 import van mod_magnet-scripts (optie `magnet`) |
| Module-ecosysteem | zeer groot | gericht | groot | zeer groot | groot | geen: alles is ingebouwd |

---

## 6. Beheer en gebruiksgemak

| Server | Belangrijkste beheerwijze | Interface | Herladen zonder onderbreking |
|---|---|---|---|
| nginx | configuratiebestanden | geen (dashboard: NGINX Plus, commercieel) | ✅ `nginx -s reload` |
| lighttpd | configuratiebestand | geen (mod_status, alleen lezen) | ✅ geleidelijke herstart |
| Caddy | Caddyfile of JSON | REST-beheer-API | ✅ via de API |
| Apache | configuratiebestanden en `.htaccess` | geen (mod_status, alleen lezen) | ✅ `graceful` |
| Traefik | containerlabels, bestanden of Kubernetes | webdashboard (alleen lezen) | ✅ dynamische configuratie |
| omega-serv | terminalinterface (TUI) en opdrachtregel (CLI); het JSON-bestand hoeft nooit met de hand bewerkt te worden | **volledige TUI met toetsenbord en muis, 17 talen, ingebouwde hulp** | ✅ voor de meeste instellingen; herstart aangekondigd voor de poort, TLS en het aantal processen |

Concreet worden bij omega-serv configuratie, beveiliging, logs, systeemdiensten, back-ups en instanties vanuit één interface beheerd. Elke instelling wordt uitgelegd en gecontroleerd voordat ze wordt weggeschreven. Bij de andere servers bewerkt men tekstbestanden en schakelt men daarna aparte hulpmiddelen in (Certbot, fail2ban, logrotate, ModSecurity, een monitoringtool…).

Daartegenover staat dat de aanpak met „configuratiebestanden” van nginx, Apache en Caddy zich zeer goed laat automatiseren (Ansible, containers, versiebeheer). omega-serv heeft een scriptbare CLI, maar zijn automatiseringsecosysteem blijft beperkt.

---

## 7. Wat omega-serv extra biedt

Deze sectie behoudt alleen wat geen van de vergeleken servers zo levert, zonder module van derden of extern hulpmiddel.

1. **Volledig beheer via een terminalinterface.**
   - De interface dekt de hele server: de site, de beveiliging, de logs, de diensten, de back-ups en de instanties.
   - Hij werkt met toetsenbord en muis, op een server zonder grafische omgeving, zelfs via SSH.
   - Hij is beschikbaar in 17 talen en legt elke instelling uit.
   - De andere servers hebben geen beheerinterface (nginx, lighttpd, Apache), of alleen een API (Caddy) of een dashboard dat alleen kan lezen (Traefik).
2. **Ingebouwde actieve beveiliging, zonder modules samen te stellen.**
   - De WAF omvat handtekeningen, bewerkbare padlijsten, recidive, een blokkeerlijst met vervaldatum, reputatie en een observatiemodus.
   - Active Defense voegt lokaas toe, een oorlogsmodus, het opvolgen van incidenten, het exporteren van indicatoren van compromittering en een proefsimulatie.
   - Elders vereisen deze functies het samenstellen van ModSecurity of Coraza, regelsets en fail2ban.
3. **Exacte beveiligingslimieten met meerdere processen.**
   - In boostmodus worden de limiet en de recidive van de WAF in het geheugen gedeeld tussen de processen. Een aanvaller kan zijn limiet dus niet vermenigvuldigen met het aantal processen.
   - lighttpd documenteert het omgekeerde geval: met `server.max-worker` tellen `mod_evasive` en `mod_status` afzonderlijk in elk proces.
   - nginx deelt zijn tellers ook (zones van `limit_req`), maar heeft geen ingebouwde WAF.
4. **Import van lighttpd-mod_magnet-scripts.**
   - Een Lua-beveiligingsscript dat al voor lighttpd geschreven is, wordt geïmporteerd zonder het te herschrijven.
   - Het vult de ingebouwde bescherming aan zonder haar ooit te kunnen verzwakken, en de compatibiliteit wordt vóór activering gecontroleerd.
5. **Beheer van meerdere instanties.**
   - Een register bevat alle instanties, en de interface schakelt tussen hen.
   - Hij kan een instantie ook volledig verwijderen.
6. **Een beveiligingsaudit van de configuratie**: de opdracht `audit security` is informatief, blokkeert nooit en geeft afsluitcodes terug die in een script bruikbaar zijn.
7. **Externe logbronnen.**
   - De interface haalt het log van een andere server op via SSH, op verzoek, zonder opgeslagen wachtwoord.
   - Hij kan het lezen met lnav, samengevoegd met de lokale logs.
8. **Een HTTP-verharding die niet uitgeschakeld kan worden**, actief vanaf de installatie, ongeacht het profiel:
   - strikte validatie van de Host-header;
   - weigering van dubbelzinnigheden tussen Content-Length en Transfer-Encoding;
   - beveiligingsheaders en CSP, zelfs op foutpagina's;
   - veilig uitlezen van X-Forwarded-For;
   - weigering om als root te starten.

---

## 8. Wat de anderen beter doen

- **Doorvoer en latentie**: nginx en lighttpd verwerken 10 tot 20 keer meer kleine verzoeken, met een 8 tot 10 keer lagere latentie. Voor een site met veel verkeer, een publieke API of een CDN zijn zij de juiste keuze.
- **Geheugen**: lighttpd (1 MB) en nginx (4 tot 5 MB) passen bij zeer beperkte machines (embedded, instap-Raspberry Pi, kleine containers).
- **Protocollen**: HTTP/2 bij alle anderen, HTTP/3 bij nginx, Caddy en Traefik. omega-serv spreekt alleen HTTP/1.1.
- **Automatische HTTPS**: Caddy en Traefik hebben het standaard ingebouwd, nginx (`ngx_http_acme_module`) en Apache (`mod_md`) via een officiële module. omega-serv laat het over aan Certbot, met een assistent en geplande vernieuwing.
- **Containeromgevingen**: de automatische service discovery van Traefik (Docker, Kubernetes) heeft geen equivalent in omega-serv.
- **Ecosysteem**: nginx en Apache bieden duizenden modules, handleidingen en integraties. Caddy biedt een modulesysteem in Go. omega-serv is een jong project dat door één persoon wordt onderhouden.
- **Compressie on-the-fly**: omega-serv levert alleen bestanden die al gecomprimeerd zijn.

---

## 9. Welke server voor welk gebruik

| Behoefte | Aanbevolen keuze |
|---|---|
| Site met veel verkeer, publieke API, CDN, maximale doorvoer | **nginx** |
| Zeer beperkte machine, embedded, statische bestanden | **lighttpd** |
| Snelle start met automatische HTTPS, korte configuratie | **Caddy** |
| Oudere PHP-toepassing, `.htaccess`, gedeelde hosting | **Apache** |
| Docker, Kubernetes, microservices | **Traefik** |
| Kleine site, interne dienst, lab, VPN, beheer zonder bestanden te bewerken | **omega-serv** |
| Blootgestelde server waarvan je de beveiliging (WAF, blokkades, lokaas) vanuit één interface wilt zien en sturen | **omega-serv** |
| Interne reverse proxy met lastverdeling, gezondheidscontrole en cache, beheerd vanuit een interface | **omega-serv** |
| HTTP-verharding en actieve verdediging leren | **omega-serv** |

Deze hulpmiddelen zijn ook te combineren. Bijvoorbeeld:
- nginx of Traefik vooraan richting internet, met omega-serv erachter voor een interne dienst, de beveiliging en het beheer ervan;
- omega-serv als interne reverse proxy vóór meerdere applicatieservers.

---

## 10. De metingen reproduceren

De hulpmiddelen worden meegeleverd in de repository, onder `tools/bench/`. Je hebt nginx, lighttpd, Caddy en oha geïnstalleerd nodig, plus de ontwikkelomgeving van omega-serv (`.venv`).

```sh
# 1. een meetmap voorbereiden (testbestanden, configuraties, omega-serv 1.0 en 2.0)
tools/bench/compare/setup.sh /pad/meting omega-serv-1.0.0.tar.gz

# 2. de 12 configuraties, 3 verweven herhalingen (ongeveer 22 minuten)
tools/bench/compare/campaign.sh /pad/meting > resultaten.txt

# 3. medianen
python3 tools/bench/compare/summarize.py resultaten.txt

# grote downloads (geheugen en reactiesnelheid), 2.0 en daarna 1.0
.venv/bin/python tools/bench/bigfile.py
BENCH_SRC=/pad/meting/v1-archive/omega-serv/src \
BENCH_EXTRA_PATH=/pad/meting/v1-archive/omega-serv/vendor/omega-lib/src \
  .venv/bin/python tools/bench/bigfile.py

# elke andere, al draaiende server meten, zonder oha
python3 tools/bench/bench_any.py --make-files /srv/test-webroot
python3 tools/bench/bench_any.py --port 8080
```

Standaard wordt de server vastgezet op threads 0 en 2, en de client op threads 1 en 3, wat overeenkomt met de meetmachine. Pas deze verdeling aan je processor aan (`lscpu -e` toont de topologie) met de variabelen `SRV_CPUS` en `CLI_CPUS`.

Vermeld bij het publiceren van je eigen resultaten de machine, de versies, de verdeling van de processoren en de drie herhalingen.

---

## 11. Bronnen

Functies van de andere servers, volgens hun officiële documentatie (geraadpleegd op 26 oktober 2026).

**nginx**
- [Limiet `limit_req` (gedeelde geheugenzone)](https://nginx.org/en/docs/http/ngx_http_limit_req_module.html)
- [Voorgecomprimeerde bestanden `gzip_static`](https://nginx.org/en/docs/http/ngx_http_gzip_static_module.html)
- [Officiële ACME-module `ngx_http_acme_module`](https://nginx.org/en/docs/http/ngx_http_acme_module.html)
- [Lastverdeling (`upstream`)](https://nginx.org/en/docs/http/ngx_http_upstream_module.html)
- [HTTP/3](https://nginx.org/en/docs/http/ngx_http_v3_module.html)
- [ModSecurity-connector voor nginx](https://github.com/owasp-modsecurity/ModSecurity-nginx)

**lighttpd**
- [`server.max-worker`: afgeraden, tellers per proces voor mod_status en mod_evasive](https://redmine.lighttpd.net/projects/lighttpd/wiki/Server_max-workerDetails)
- [mod_magnet (Lua-scripts)](https://redmine.lighttpd.net/projects/lighttpd/wiki/Docs_ModMagnet)
- [mod_deflate (compressie, cache)](https://redmine.lighttpd.net/projects/lighttpd/wiki/Mod_deflate)
- [mod_proxy (lastverdeling, passieve gezondheid, WebSocket)](https://redmine.lighttpd.net/projects/lighttpd/wiki/Docs_ModProxy)
- [mod_evasive (gelijktijdige verbindingen per adres)](https://redmine.lighttpd.net/projects/lighttpd/wiki/Docs_ModEvasive)

**Caddy**
- [Automatische HTTPS](https://caddyserver.com/docs/automatic-https)
- [`file_server` en `precompressed`](https://caddyserver.com/docs/caddyfile/directives/file_server)
- [`reverse_proxy` (strategieën, actieve en passieve gezondheid)](https://caddyserver.com/docs/caddyfile/directives/reverse_proxy)
- [Beheer-API](https://caddyserver.com/docs/api)
- [Limietplugin caddy-ratelimit](https://github.com/mholt/caddy-ratelimit)
- [WAF Coraza voor Caddy](https://github.com/corazawaf/coraza-caddy)
- [caddy-docker-proxy](https://github.com/lucaslorentz/caddy-docker-proxy)

**Apache HTTP Server**
- [mod_md (ACME)](https://httpd.apache.org/docs/2.4/mod/mod_md.html)
- [mod_proxy_balancer](https://httpd.apache.org/docs/2.4/mod/mod_proxy_balancer.html)
- [mod_proxy_hcheck](https://httpd.apache.org/docs/2.4/mod/mod_proxy_hcheck.html)
- [mod_http2](https://httpd.apache.org/docs/2.4/mod/mod_http2.html)
- [mod_deflate, voorgecomprimeerde inhoud](https://httpd.apache.org/docs/2.4/mod/mod_deflate.html)
- [ModSecurity](https://github.com/owasp-modsecurity/ModSecurity)

**Traefik**
- [Middleware `ratelimit` (in het geheugen per instantie, Redis optioneel)](https://doc.traefik.io/traefik/reference/routing-configuration/http/middlewares/ratelimit/)
- [ACME](https://doc.traefik.io/traefik/https/acme/)
- [Providers (Docker, Kubernetes…)](https://doc.traefik.io/traefik/providers/overview/)

**Meethulpmiddel**
- [oha](https://github.com/hatoo/oha)

---

*Vergelijking gemaakt door kraynux voor omega-serv 2.0.0: metingen van 26 oktober 2026. De metingen betreffen één enkele machine. Meet voor elke capaciteitsbeslissing op je eigen hardware met de meegeleverde hulpmiddelen.*
