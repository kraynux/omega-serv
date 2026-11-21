<!-- Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE) -->

# omega-serv vergeleken met de webservers op de markt

**Gemeten vergelijking: nginx · lighttpd · Apache · Caddy · Traefik · omega-serv 2.5 en 3.0.0**

🌐 [Français](../../comparatif-serveurs-web.md) · [English](../en/comparatif-serveurs-web.md) · [Español](../es/comparatif-serveurs-web.md) · [Português (Brasil)](../pt-BR/comparatif-serveurs-web.md) · [Italiano](../it/comparatif-serveurs-web.md) · [Deutsch](../de/comparatif-serveurs-web.md) · **Nederlands** · [Polski](../pl/comparatif-serveurs-web.md) · [Русский](../ru/comparatif-serveurs-web.md) · [中文](../zh-CN/comparatif-serveurs-web.md) · [Tiếng Việt](../vi/comparatif-serveurs-web.md) · [ไทย](../th/comparatif-serveurs-web.md) · [Bahasa Indonesia](../id/comparatif-serveurs-web.md) · [日本語](../ja/comparatif-serveurs-web.md) · [한국어](../ko/comparatif-serveurs-web.md) · [हिन्दी](../hi/comparatif-serveurs-web.md) · [العربية](../ar/comparatif-serveurs-web.md)

Dit document plaatst omega-serv tussen de meest gebruikte webservers. Het probeert geen „beste server” aan te wijzen: elk hulpmiddel beantwoordt aan andere behoeften, en elk heeft zijn sterke punten. Het levert drie dingen:

1. **echte metingen**, uitgevoerd op **drie** zeer verschillende **machines**, met dezelfde client, dezelfde bestanden en hetzelfde protocol, en reproduceerbaar;
2. een **functievergelijking**, elke functie gecontroleerd in de officiële documentatie van elke server (links aan het einde van het document), met onderscheid tussen wat ingebouwd is en wat een module of plugin vereist;
3. wat omega-serv **echt extra biedt**, en wat de anderen **beter doen dan hij**.

De metingen als bestandsserver zijn uitgevoerd op 3 en 4 november 2026 (omega-serv 2.5), die als reverse proxy op 14 november 2026 (omega-serv 3.0.0, in voorbereiding). Het geheugen van omega-serv 3.0.0, sindsdien flink verkleind, is op 19 november 2026 opnieuw gemeten op alle drie de machines, met hetzelfde protocol (§4, §5 en §6). Geen enkel cijfer is van een andere site overgenomen of geschat. De ruwe cijfers worden met dit document gepubliceerd.

---

## Inhoud

1. [In het kort](#1-in-het-kort)
2. [Hoe deze vergelijking te lezen](#2-hoe-deze-vergelijking-te-lezen)
3. [Meetmethode](#3-meetmethode)
4. [Prestaties: omega-serv vergeleken met nginx, lighttpd, Apache en Caddy](#4-prestaties-omega-serv-vergeleken-met-nginx-lighttpd-apache-en-caddy)
5. [Prestaties als reverse proxy: omega-serv vergeleken met nginx, lighttpd, Apache, Caddy en Traefik](#5-prestaties-als-reverse-proxy-omega-serv-vergeleken-met-nginx-lighttpd-apache-caddy-en-traefik)
6. [De versies van omega-serv: 1.0 → 2.0 → 2.5 → 3.0.0](#6-de-versies-van-omega-serv-10--20--25--300)
7. [Functievergelijking](#7-functievergelijking)
8. [Beheer en gebruiksgemak](#8-beheer-en-gebruiksgemak)
9. [Wat omega-serv extra biedt](#9-wat-omega-serv-extra-biedt)
10. [Wat de anderen beter doen](#10-wat-de-anderen-beter-doen)
11. [Welke server voor welk gebruik](#11-welke-server-voor-welk-gebruik)
12. [De metingen reproduceren](#12-de-metingen-reproduceren)
13. [Bronnen](#13-bronnen)

---

## 1. In het kort

- **omega-serv heeft twee engines.** De **Python-engine** verwerkt alles zelf. De **native engine**, geschreven in C++ en verschenen met 2.5, handelt de verzoeken zelf af; Python houdt de configuratie en de beveiligingsbeslissingen, waarbij de native engine zelf de verzoeken herkent waarop geen enkele WAF-regel van toepassing is.
- **Met de native engine, zonder WAF**, levert omega-serv kleine bestanden met **ongeveer 0,7 keer de snelheid van nginx**, op alle drie de machines. Hij staat daarmee **voor Apache en Caddy, achter nginx en lighttpd**.
- **Met de Python-engine** blijft omega-serv ver achter alle anderen: **3 tot 11 % van de snelheid van nginx**.
- **Met de WAF actief** inspecteert omega-serv elk verzoek, wat de andere gemeten servers niet doen. Met de native engine levert hij dan **0,53 tot 0,56 keer** de snelheid van nginx (zonder WAF) op de machines A en B, en 1,07 keer op machine C (4 kernen tegen 2): de WAF kost hem maar 5 tot 22 % van zijn doorvoer. Hij blijft voor Apache en Caddy, die zonder WAF gemeten zijn.
- **Middelgrote bestanden (100 KB)**: dit is het huidige zwakke punt van de native engine, met **0,3 tot 0,6 keer** nginx, achter Apache.
- **Grote bestanden (5 MB)**: nginx, lighttpd, Apache en omega-serv native halen dezelfde orde van doorvoer. Caddy is duidelijk trager op de snelste machine.
- **Als reverse proxy (3.0.0)** stuurt de native engine kleine antwoorden door met **0,82 tot 0,91 keer nginx**, en antwoorden van 100 KB **even snel als nginx of sneller** (0,97 tot 1,43). Hij staat **tweede achter nginx**, voor lighttpd, Apache, Traefik en Caddy. In HTTPS blijft hij tweede bij kleine antwoorden op de machines A en B; lighttpd evenaart hem op machine C.
- **Geheugen**: lighttpd (1 MB), nginx (4 tot 5 MB) en Apache (4 tot 9 MB) zijn zeer zuinig. omega-serv 3.0.0 gebruikt **10 tot 16 MB** met de native engine, **20 tot 33 MB** met de Python-engine of de WAF, en 35 tot 55 MB met 2 processen; Caddy **50 tot 67 MB**. Versie 2.5 gebruikte 28 tot 57 MB.
- **Wat omega-serv extra heeft**: volledig beheer in een terminalinterface, in 17 talen; een ingebouwde WAF en actieve verdediging; exacte beveiligingslimieten met meerdere processen; het importeren van lighttpd-mod_magnet-scripts; het beheer van meerdere instanties.
- **Wat hij niet heeft**: HTTP/2 en HTTP/3, compressie on-the-fly, service discovery voor Docker/Kubernetes, een ingebouwde ACME-client (hij gebruikt Certbot), een ecosysteem van modules.

---

## 2. Hoe deze vergelijking te lezen

Enkele begrippen keren in het hele document terug.

- **Verzoeken per seconde (req/s)**: het aantal bestanden dat een server in één seconde verstuurt. Hoe hoger, hoe beter.
- **Verschil met nginx**: de absolute waarden hangen sterk van de machine af. Op onze drie machines gaat nginx van 22.000 tot 440.000 req/s. Wat stabiel blijft, is **de verhouding tussen servers**. De tabellen geven daarom naast elke waarde de verhouding met nginx, gemeten in dezelfde sessie: **1,00 = even snel als nginx**, 0,50 = half zo snel, 1,50 = anderhalf keer zo snel.
- **p99-latentie**: de responstijd die 99 % van de verzoeken niet overschrijdt. Ze toont de „slechte momenten” die een gemiddelde verbergt.
- **PSS (*Proportional Set Size*)**: het geheugen dat alle processen van de server werkelijk gebruiken. Een pagina die door meerdere processen gedeeld wordt, telt maar één keer.
- **Processen en kernen**: een server kan meerdere kernen van de processor gebruiken. Elk doet het op zijn eigen manier. nginx, lighttpd, Apache en omega-serv in Python-modus starten meerdere processen. Caddy verdeelt zijn werk in Go over de kernen. De native engine van omega-serv start één thread per beschikbare kern. Om eerlijk te vergelijken, geven we elke server **dezelfde kernen**.
- **WAF (*Web Application Firewall*)**: een filter dat elk verzoek inspecteert om aanvallen te blokkeren (injecties, scanners…). omega-serv heeft hem ingebouwd. De andere servers kunnen er een als module krijgen (ModSecurity, Coraza), maar **ze zijn zonder gemeten**, in hun basisconfiguratie.

**De juiste reflex**: de verhoudingen vergelijken, niet de absolute waarden, en altijd nagaan of de WAF actief is.

---

## 3. Meetmethode

### De drie machines

| | Machine A | Machine B | Machine C |
|---|---|---|---|
| Processor | Intel Core i5 M480, 2,67 GHz (2010) | Intel Celeron J3455, 1,5 GHz (2016) | AMD Ryzen AI 9 365 (2024) |
| Kernen | 2 fysieke kernen, 4 threads | 4 kernen, zonder hyperthreading | 10 kernen (4 Zen 5 + 6 Zen 5c), 20 threads |
| Geheugen | 8 GB | 8 GB | 32 GB |
| Systeem | Mabox Linux (basis Manjaro), kernel 6.18 | EndeavourOS, kernel 7.2 | Arch Linux, kernel 7.2 (CachyOS) |
| Kernen van de server | 1 fysieke kern (threads 0 en 2) | 2 kernen (0 en 1) | 4 Zen 5-kernen, elk één thread (0 tot 3) |
| Kernen van de client | 1 fysieke kern (threads 1 en 3) | 2 kernen (2 en 3) | 6 Zen 5c-kernen (4 tot 9) |

Machine A is een oude laptop, machine B een zuinige mini-pc, machine C een recente laptop, op netstroom, in het energieprofiel „gebalanceerd”. Ze bestrijken een bereik van een kleine thuisserver tot een actuele machine.

### Software

| Software | Versie |
|---|---|
| nginx | 1.30.4 (A), 1.30.5 (B, C) |
| lighttpd | 1.4.85 |
| Apache HTTP Server | 2.4.69, MPM `event` |
| Caddy | 2.11.4 (A, B), 2.11.7 (C) |
| omega-serv | 1.0.0 en 2.0.0 (gepubliceerde archieven), 2.5 en 3.0.0, onder Python 3.14 |
| Belastingclient | [oha](https://github.com/hatoo/oha) 1.16.0 (geschreven in Rust) |

Traefik is niet gemeten als bestandsserver: dat is het niet (zie §7). Het wordt gemeten als reverse proxy, zijn eigenlijke rol, in §5.

### Protocol

- **Isolatie van de processor**: server en client zijn vastgezet op aparte kernen (tabel hierboven). De client steelt dus geen tijd van de server, en alle servers beschikken over precies dezelfde middelen.
- **Dezelfde bestanden voor iedereen**: `small.html` (1 KB), `medium.png` (100 KB) en `large.bin` (5 MB), geleverd vanuit dezelfde map.
- **Toegangslogboek overal actief**, want een server in productie logt.
- **HTTP/1.1 onversleuteld, persistente verbindingen (keep-alive)**. De gelijktijdigheid is 32 verbindingen voor de bestanden van 1 KB en 100 KB, en 8 voor het bestand van 5 MB.
- **Duur**: 10 seconden per bestand en per configuratie.
- **Herhalingen**: 3 volledige, verweven rondes (alle configuraties in ronde 1, dan alle in ronde 2, enz.). De tabellen geven de **mediaan** van de drie rondes. Van ronde tot ronde blijft het verschil meestal onder 5 %.
- **Geheugen**: PSS van alle processen van de server, gemeten in rust en daarna na de belasting. Dat van omega-serv 3.0.0 is op 19 november 2026 opnieuw gemeten, met nginx als referentie in dezelfde sessie: nginx blijft bij kleine bestanden binnen 3 % van zijn doorvoer van 4 november, en zijn geheugen binnen 1 MB.
- **Configuraties**:
  - nginx, lighttpd, Apache en Caddy in hun basisconfiguratie: statische bestanden en toegangslogboek;
  - omega-serv met het profiel `standard`, de WAF uitgeschakeld en daarna ingeschakeld met alle meegeleverde regels (zonder snelheidsbeperking).
- **Aantal processen**: elke server wordt gemeten met 1 en daarna 2 processen: nginx `worker_processes`, lighttpd `server.max-worker`, Apache `StartServers`/`ServerLimit`, Caddy `GOMAXPROCS`, omega-serv `server.workers`. Voor de native engine van omega-serv telt `server.workers` de Python-beveiligingsprocessen; de native engine zelf gebruikt altijd alle kernen die hij krijgt.
- **Geen enkele fout**: alle antwoorden van alle metingen zijn 200.

### Grenzen om te kennen

- **Wat we vergelijken, zijn de verhoudingen.** De absolute waarden zouden op uw hardware, of op een dedicated server, anders zijn.
- **Loopback (127.0.0.1)**: de meting gaat niet over een echt netwerk. Op een echt netwerk is de doorvoer van grote bestanden bijna altijd beperkt door de bandbreedte, niet door de server. De doorvoer van enkele tientallen GB/s op machine C is alleen via loopback mogelijk.
- **Geen TLS** in de metingen als bestandsserver (§4 en §6). De reverse proxy (§5) wordt gemeten in HTTP en in HTTPS.
- **Machine A**: de productiedienst omega-serv van deze machine draaide op de achtergrond, zonder verkeer te ontvangen.
- **Machine C**: hybride processor (Zen 5- en Zen 5c-kernen). De server kreeg de 4 snelle kernen, de client de 6 andere.
- **Basisconfiguraties**: geen enkele server is geoptimaliseerd. Een ervaren beheerder zou ongetwijfeld meer uit elke server halen, omega-serv inbegrepen.
- **Ruwe cijfers**: [`docs/benchmarks/`](../../benchmarks/) (één bestand per machine en per campagne; nieuwe meting van 3.0.0: `2026-11-19-*-memoire-3.0.0-brut.txt`).

---

## 4. Prestaties: omega-serv vergeleken met nginx, lighttpd, Apache en Caddy

In alle tabellen is de referentiewaarde **nginx met 2 processen** (= 1,00), gemeten in dezelfde sessie op dezelfde machine. Op de machines A en B is dat de configuratie die alle kernen bezet die de server krijgt.

### Kleine bestanden (1 KB): verzoeken per seconde

| Server | Machine A | Machine B | Machine C |
|---|---:|---:|---:|
| lighttpd, 2 processen | 33.138 (**1,52**) | 31.125 (**1,26**) | 378.590 (**1,53**) |
| nginx, 2 processen | 21.801 (1,00) | 24.705 (1,00) | 248.184 (1,00) |
| **omega-serv, native engine** | **15.222 (0,70)** | **16.542 (0,67)** | **285.213 (1,15 \*)** |
| omega-serv, native + WAF † | 11.990 (0,56) | 12.998 (0,53) | 264.484 (1,07 \*) |
| omega-serv, native + WAF, 2 beveiligingsprocessen † | 11.746 (0,55) | 12.718 (0,52) | 253.527 (1,02 \*) |
| Apache, 2 processen | 9.192 (0,42) | 8.634 (0,35) | 188.335 (0,76) |
| Caddy, 2 processen | 5.749 (0,26) | 4.116 (0,17) | 52.897 (0,21) |
| omega-serv, Python-engine, 2 processen | 2.354 (0,11) | 1.312 (0,05) | 19.911 (0,08) |
| omega-serv, Python + WAF, 2 processen | 1.901 (0,09) | 1.104 (0,04) | 15.783 (0,06) |
| omega-serv, Python-engine | 1.507 (0,07) | 663 (0,03) | 10.553 (0,04) |
| omega-serv, Python + WAF | 1.561 (0,07) | 564 (0,02) | 8.365 (0,03) |

\* Op machine C gebruikt de native engine zijn 4 kernen, terwijl nginx er met 2 processen maar 2 gebruikt. De vergelijking bij een gelijk aantal kernen volgt verderop: de verhouding komt daar weer op **0,67 tot 0,71**, zoals op de andere machines.

† Gemeten op 4 november, na de optimalisatie van de WAF, in een aparte meetcampagne met hetzelfde protocol. De verhouding is berekend met nginx (2 processen) van die campagne: 21 439, 24.424 en 248.127 req/s bij kleine bestanden, 11 545, 11.004 en 157.491 bij bestanden van 100 KB. Vóór deze optimalisatie leverde de native engine met WAF 3 495, 2.622 en 39.000 req/s (0,11 tot 0,16 keer nginx), omdat elk verzoek via Python ging. Ruwe cijfers: bestanden `*-waf-natif-brut.txt`.

Met 1 enkel proces haalt nginx 0,52 tot 0,73, lighttpd 0,81 tot 1,43, Apache 0,33 tot 0,74 en Caddy 0,09 tot 0,17 (ruwe cijfers).

### p99-latentie bij kleine bestanden

| Server | Machine A | Machine B | Machine C |
|---|---:|---:|---:|
| lighttpd, 2 processen | 4,4 ms | 4,1 ms | 0,2 ms |
| nginx, 2 processen | 4,9 ms | 5,2 ms | 0,2 ms |
| **omega-serv, native engine** | **6,1 ms** | **6,2 ms** | **0,3 ms** |
| omega-serv, native + WAF † | 7,2 ms | 6,7 ms | 0,3 ms |
| Apache, 2 processen | 18,8 ms | 20,6 ms | 0,8 ms |
| Caddy, 2 processen | 24,1 ms | 30,5 ms | 2,8 ms |
| omega-serv, Python-engine, 2 processen | 22,6 ms | 28,1 ms | 3,3 ms |
| omega-serv, Python-engine | 32,0 ms | 51,6 ms | 4,4 ms |

### Middelgrote bestanden (100 KB): verzoeken per seconde

| Server | Machine A | Machine B | Machine C |
|---|---:|---:|---:|
| lighttpd, 2 processen | 13.561 (**1,08**) | 12.126 (**1,07**) | 197.905 (**1,26**) |
| nginx, 2 processen | 12.513 (1,00) | 11.303 (1,00) | 157.224 (1,00) |
| Apache, 2 processen | 6.939 (0,55) | 7.035 (0,62) | 153.265 (0,97) |
| Caddy, 2 processen | 5.059 (0,40) | 3.744 (0,33) | 22.094 (0,14) |
| **omega-serv, native engine** | **4.738 (0,38)** | **3.115 (0,28)** | **96.277 (0,61)** |
| omega-serv, native + WAF † | 4.229 (0,37) | 2.926 (0,27) | 98.185 (0,62) |
| omega-serv, Python-engine, 2 processen | 1.741 (0,14) | 1.154 (0,10) | 18.806 (0,12) |
| omega-serv, Python-engine | 1.329 (0,11) | 611 (0,05) | 9.805 (0,06) |

### Groot bestand (5 MB): doorvoer

| Server | Machine A | Machine B | Machine C |
|---|---:|---:|---:|
| lighttpd, 2 processen | 2.440 MB/s (1,05) | 2.110 MB/s (0,99) | 28.011 MB/s (0,81) |
| nginx, 2 processen | 2.322 MB/s (1,00) | 2.124 MB/s (1,00) | 34.651 MB/s (1,00) |
| Apache, 2 processen | 2.355 MB/s (1,01) | 2.134 MB/s (1,00) | 41.153 MB/s (**1,19**) |
| **omega-serv, native engine** | **2.294 MB/s (0,99)** | **1.936 MB/s (0,91)** | **37.918 MB/s (1,09)** |
| Caddy, 2 processen | 2.205 MB/s (0,95) | 1.996 MB/s (0,94) | 3.811 MB/s (0,11) |
| omega-serv, Python-engine, 2 processen | 2.145 MB/s (0,92) | 1.931 MB/s (0,91) | 25.829 MB/s (0,75) |
| omega-serv, Python-engine | 1.686 MB/s (0,73) | 1.472 MB/s (0,69) | 14.227 MB/s (0,41) |

### Geheugen (PSS, alle processen van de server): in rust → na de belasting

omega-serv: versie 3.0.0, opnieuw gemeten op 19 november 2026 (de waarden van 2.5 staan in §6). Andere servers: campagne van 4 november.

| Server | Machine A | Machine B | Machine C |
|---|---:|---:|---:|
| lighttpd | 1 → 1 MB | 1 → 1 MB | 1 → 1 MB |
| nginx | 4 → 5 MB | 5 → 5 MB | 4 → 4 MB |
| Apache | 4 → 7 MB | 4 → 7 MB | 4 → 7 MB |
| **omega-serv, native engine** | **10 → 10 MB** | **10 → 12 MB** | **12 → 16 MB** |
| omega-serv, Python-engine | 20 → 23 MB | 21 → 24 MB | 22 → 28 MB |
| omega-serv, native + WAF | 28 → 30 MB | 29 → 32 MB | 30 → 33 MB |
| omega-serv, Python-engine, 2 processen | 35 → 46 MB | 36 → 46 MB | 38 → 48 MB |
| omega-serv, native + WAF, 2 beveiligingsprocessen ‡ | 28 → 28 MB | 29 → 31 MB | 51 → 55 MB |
| Caddy, 2 processen | 50 → 57 MB | 46 → 54 MB | 48 → 62 MB |

‡ Op de machines A en B heeft de server maar 2 kernen: omega-serv start daar maar één beveiligingsproces (vanaf 4 kernen start hij er 2). Op machine C, met 2 beveiligingsprocessen, behoudt de Python-supervisor zijn volledige vorm, die nodig is voor de tellers die ze delen: 51 MB in plaats van 30.

### Bij een gelijk aantal kernen: machine C met 4 processen

Aparte campagne van 3 november, hetzelfde protocol, op machine C: elke server krijgt 4 processen (of 4 kernen voor Caddy en de native engine). Referentie: nginx met 4 processen. De native engine met WAF staat hier niet meer in: gemeten vóór de optimalisatie van de WAF, is hij nog niet opnieuw met 4 processen gemeten. Geheugen van omega-serv: 3.0.0, opnieuw gemeten op 19 november (doorvoer: 2.5, 3 november).

| Server | 1 KB | 100 KB | 5 MB | Geheugen |
|---|---:|---:|---:|---:|
| lighttpd, 4 processen | 638.907 (**1,46**) | 312.402 (**1,21**) | 41.982 MB/s (0,93) | 1 → 2 MB |
| nginx, 4 processen | 438.496 (1,00) | 258.242 (1,00) | 45.162 MB/s (1,00) | 5 → 5 MB |
| **omega-serv, native engine** | **294.083 tot 310.972 (0,67 tot 0,71)** | **108.991 tot 109.955 (0,42)** | **40.137 tot 40.463 MB/s (0,89 tot 0,90)** | **12 → 16 tot 18 MB** |
| Apache, 4 processen | 200.592 (0,46) | 162.607 (0,63) | 39.664 MB/s (0,88) | 6 → 9 MB |
| Caddy, 4 kernen | 97.085 (0,22) | 35.900 (0,14) | 5.998 MB/s (0,13) | 52 → 67 MB |
| omega-serv, Python-engine, 4 processen | 37.697 (0,09) | 35.064 (0,14) | 37.123 MB/s (0,82) | 45 → 60 MB |

### Lezing

- **De native engine verandert de plaats van omega-serv.**
  - Bij kleine bestanden gaat hij van 0,03-0,11 keer nginx (Python-engine) naar ongeveer **0,7 keer nginx**, op welke machine ook.
  - Hij staat voor Apache en Caddy, en achter nginx en lighttpd, die de snelste blijven.
  - Zijn p99-latentie ligt dicht bij die van nginx.
- **lighttpd is de snelste bij kleine en middelgrote bestanden**, op alle drie de machines, en de zuinigste met geheugen. Zijn documentatie raadt toch `server.max-worker` (meerdere processen) af, dat we gebruikt hebben om bij een gelijk aantal processen te vergelijken.
- **Middelgrote bestanden zijn het huidige zwakke punt van de native engine**: 0,28 tot 0,61 keer nginx, achter Apache, en niet beter met meer kernen. Dat is een vastgesteld verbeterpunt.
- **Bij grote bestanden** komen de servers bij elkaar, omdat de kernel de gegevens kopieert (`sendfile`). Caddy is de uitzondering op machine C: we hebben niet geprobeerd zijn basisconfiguratie te optimaliseren.
- **De WAF kost de native engine weinig, en dat moet je eerlijk lezen.**
  - De native engine doorzoekt zelf de WAF-regels: een verzoek waarop er geen enkele van toepassing is, wordt zonder Python afgehandeld. Bij de minste twijfel (overeenkomst, niet-ASCII-tekst, bron die Active Defense volgt, authenticatiezone…) beslist Python. Met de WAF behoudt de native engine zo 78 tot 95 % van zijn doorvoer bij kleine bestanden, en 93 tot 99 % bij bestanden van 100 KB. Vóór deze optimalisatie werd zijn doorvoer gedeeld door 4 tot 7.
  - De snelheidsbeperking wordt door de native engine geteld: ze inschakelen verandert deze cijfers niet (machine A: 11.391 req/s met, 11.330 zonder). Is magnet actief, dan gaan alle verzoeken nog steeds via Python, en zijn de kosten weer als voorheen.
  - omega-serv met WAF blijft voor Apache en Caddy **zonder** WAF.
  - nginx, lighttpd, Apache en Caddy zijn **zonder** WAF gemeten. Een WAF die aan deze servers wordt toegevoegd (ModSecurity, Coraza) heeft ook kosten, die we niet gemeten hebben. De vergelijking „met WAF” is dus niet eerlijk, en we beweren niet dat omega-serv sneller zou zijn dan een andere server met een WAF.
- **Meerdere beveiligingsprocessen helpen het gewone verkeer niet meer**: het gaat niet meer via hen, en de doorvoer blijft gelijk met 2 processen (−2 tot −4 %, binnen de meetruis). Ze helpen alleen wanneer veel verzoeken via Python gaan (magnet actief, aanval): gemeten vóór de optimalisatie, toen alle verzoeken erlangs gingen, vermenigvuldigden 2 beveiligingsprocessen de doorvoer met WAF met 1,5 tot 1,7 op 4 kernen, maar brachten ze op 2 kernen maar 5 tot 12 %.
- **De Python-engine schaalt met de processen** (×1,6 tot ×2 met 2 processen, ongeveer ×3,5 met 4), maar blijft op 5 tot 11 % van nginx.
- **Geheugen**: met de native engine zonder WAF gebruikt omega-serv 3.0.0 10 tot 16 MB, twee tot vier keer zoveel als nginx of Apache en drie tot zes keer minder dan Caddy. Met de WAF of de Python-engine komt het op 20 tot 33 MB, vooral door Python: een Python-proces met asyncio kost minstens 10 MB. Met één proces is dat 30 tot 70 % minder dan in 2.5 (§6).
- **Om deze cijfers te plaatsen**: zelfs het traagste geval, de Python-engine met WAF op machine B (564 req/s), staat voor bijna 50 miljoen verzoeken per dag. Dat ligt ver boven de behoeften van een persoonlijke site, een interne dienst of een lab. Snelheid is alleen echt doorslaggevend voor een site met veel verkeer.

---

## 5. Prestaties als reverse proxy: omega-serv vergeleken met nginx, lighttpd, Apache, Caddy en Traefik

Hier levert geen enkele server bestanden: elke server **stuurt** de verzoeken **door** naar een applicatieserver (de *backend*) en geeft diens antwoord terug. Metingen van 14 november 2026, met omega-serv 3.0.0 (in voorbereiding), waarvan de native engine de reverse proxy zelf afhandelt.

### Eigen protocol van deze metingen

- **Dezelfde backend voor iedereen**: een statische nginx met 2 processen, die `small.html` (1 KB) en `medium.png` (100 KB) levert. Elke meting controleert dat het antwoord echt van de backend komt (een header die hij toevoegt): de proxy stuurt door, hij levert het bestand nooit zelf.
- **Kernen**: machine A, de proxy op één fysieke kern (threads 0 en 2), de client en de backend op de andere (1 en 3); machine B, de proxy op de kernen 0 en 1, de client en de backend op 2 en 3; machine C, de proxy op de 4 Zen 5-kernen (0 tot 3), de backend op 2 Zen 5c-kernen (4 en 5), de client op de 4 andere (6 tot 9).
- **Processen**: 2 op de machines A en B, **4 op machine C**, zodat elke server alle kernen gebruikt die de proxy krijgt. De native engine van omega-serv gebruikt altijd al deze kernen, met één Python-beveiligingsproces.
- **HTTP en HTTPS** aan de clientkant (zelfondertekend ECDSA P-256-certificaat); de backend wordt altijd via HTTP benaderd.
- **Configuraties**:
  - nginx: `proxy_pass` naar een `upstream`-groep die zijn verbindingen naar de backend openhoudt (`keepalive 64`); zonder deze instelling, die in zijn basisconfiguratie ontbreekt, opent nginx één verbinding per verzoek;
  - lighttpd: `mod_proxy`, basisconfiguratie;
  - Apache: `mod_proxy` en `mod_proxy_http`, MPM `event`, één regel `ProxyPass`;
  - Caddy: `reverse_proxy`, basisconfiguratie;
  - Traefik 3.7: één router en één service, basisconfiguratie;
  - omega-serv: een reverse-proxyzone op `/`, profiel `standard`, native engine zonder en daarna met de WAF (alle meegeleverde regels, zonder snelheidsbeperking), en Python-engine met 2 processen.
- **De rest verandert niet** (§3): toegangslogboek overal actief, oha, 32 persistente verbindingen, 10 seconden, 3 verweven rondes, mediaan. **Geen enkele fout**: alle antwoorden zijn 200.

Tussen haakjes: de verhouding tot nginx met hetzelfde aantal processen, gemeten in dezelfde sessie (= 1,00).

### Kleine antwoorden (1 KB): verzoeken per seconde

| Server | Machine A (2 processen) | Machine B (2 processen) | Machine C (4 processen) |
|---|---:|---:|---:|
| nginx | 11.151 (1,00) | 11.049 (1,00) | 246.595 (1,00) |
| **omega-serv, native engine** | **9.507 (0,85)** | **10.098 (0,91)** | **203.021 (0,82)** |
| omega-serv, native + WAF | 9.078 (0,81) | 9.857 (0,89) | 190.201 (0,77) |
| lighttpd | 6.752 (0,61) | 6.242 (0,56) | 129.827 (0,53) |
| Apache | 6.616 (0,59) | 5.872 (0,53) | 124.458 (0,50) |
| Traefik | 3.940 (0,35) | 3.890 (0,35) | 70.465 (0,29) |
| Caddy | 3.578 (0,32) | 3.117 (0,28) | 55.910 (0,23) |
| omega-serv, Python-engine | 1.039 (0,09) | 859 (0,08) | — \* |

\* De Python-engine is op machine C alleen met 2 processen gemeten: 11.530 req/s, dus 0,07 keer nginx met 2 processen (171.075 req/s).

### Middelgrote antwoorden (100 KB): verzoeken per seconde

| Server | Machine A | Machine B | Machine C |
|---|---:|---:|---:|
| **omega-serv, native engine** | **4.281 (1,11)** | **3.497 (0,97)** | **80.361 (1,43)** |
| omega-serv, native + WAF | 4.236 (1,10) | 3.335 (0,93) | 73.025 (1,30) |
| nginx | 3.855 (1,00) | 3.605 (1,00) | 56.011 (1,00) |
| lighttpd | 2.834 (0,74) | 2.252 (0,62) | 53.523 (0,96) |
| Apache | 2.404 (0,62) | 2.357 (0,65) | 39.807 (0,71) |
| Traefik | 2.477 (0,64) | 2.181 (0,60) | 39.419 (0,70) |
| Caddy | 2.294 (0,60) | 1.956 (0,54) | 33.120 (0,59) |
| omega-serv, Python-engine | 821 (0,21) | 669 (0,19) | — |

### HTTPS: verzoeken per seconde

| Server | 1 KB: A | 1 KB: B | 1 KB: C | 100 KB: A | 100 KB: B | 100 KB: C |
|---|---:|---:|---:|---:|---:|---:|
| nginx | 9.203 (1,00) | 9.305 (1,00) | 202.095 (1,00) | 780 (1,00) | 2.338 (1,00) | 47.609 (1,00) |
| **omega-serv, native engine** | **6.840 (0,74)** | **7.976 (0,86)** | **130.337 (0,64) †** | **690 (0,88)** | **1.917 (0,82)** | **42.507 (0,89)** |
| omega-serv, native + WAF | 6.372 (0,69) | 7.456 (0,80) | 146.590 (0,73) † | 683 (0,88) | 1.882 (0,80) | 39.400 (0,83) |
| lighttpd | 5.188 (0,56) | 5.513 (0,59) | 130.572 (0,65) | 638 (0,82) | 1.381 (0,59) | 45.566 (0,96) |
| Apache | 5.038 (0,55) | 4.193 (0,45) | 114.898 (0,57) | 588 (0,75) | 1.368 (0,59) | 29.948 (0,63) |
| Traefik | 3.389 (0,37) | 3.195 (0,34) | 62.251 (0,31) | 889 (**1,14**) | 1.548 (0,66) | 28.513 (0,60) |
| Caddy | 3.263 (0,35) | 2.733 (0,29) | 54.279 (0,27) | 1.135 (**1,46**) | 1.424 (0,61) | 26.452 (0,56) |
| omega-serv, Python-engine | 922 (0,10) | 759 (0,08) | — | 423 (0,54) | 549 (0,23) | — |

† Op machine C varieert de native engine in HTTPS sterk van ronde tot ronde: 130.000 tot 185.000 req/s zonder WAF, 138.000 tot 150.000 met. Het verschil tussen de twee regels valt dus binnen de ruis van deze meting.

### p99-latentie bij kleine antwoorden (HTTP)

| Server | Machine A | Machine B | Machine C |
|---|---:|---:|---:|
| nginx | 7,7 ms | 7,8 ms | 0,4 ms |
| **omega-serv, native engine** | **10,5 ms** | **9,7 ms** | **0,6 ms** |
| omega-serv, native + WAF | 9,6 ms | 11,0 ms | 0,8 ms |
| lighttpd | 11,9 ms | 14,0 ms | 0,9 ms |
| Apache | 14,7 ms | 21,3 ms | 2,0 ms |
| Traefik | 25,9 ms | 26,5 ms | 2,1 ms |
| Caddy | 23,9 ms | 27,2 ms | 2,5 ms |
| omega-serv, Python-engine | 41,0 ms | 47,6 ms | — |

### Geheugen van de proxy (PSS): in rust → na de belasting, in HTTP

omega-serv: versie 3.0.0, opnieuw gemeten op 19 november 2026; de doorvoer hierboven dateert van 14 november.

| Server | Machine A | Machine B | Machine C |
|---|---:|---:|---:|
| lighttpd | 3 → 4 MB | 3 → 4 MB | 3 → 4 MB |
| nginx | 7 → 8 MB | 7 → 8 MB | 10 → 11 MB |
| Apache | 6 → 12 MB | 6 → 12 MB | 8 → 15 MB |
| **omega-serv, native engine** | **27 → 28 MB** | **27 → 28 MB** | **29 → 33 MB** |
| omega-serv, native + WAF | 29 → 30 MB | 29 → 31 MB | 31 → 36 MB |
| Caddy | 48 → 57 MB | 48 → 59 MB | 50 → 60 MB |
| omega-serv, Python-engine | 42 → 50 MB | 43 → 51 MB | — |
| Traefik | 93 → 117 MB | 107 → 131 MB | 100 → 123 MB |

In HTTPS stijgt het geheugen na de belasting met 0 tot 5 MB voor de meeste servers, meer voor Apache (tot 66 MB op machine C) en de Python-engine (tot 72 MB): zie de ruwe cijfers.

### Lezing

- **Als reverse proxy staat omega-serv met de native engine tweede achter nginx**, op alle drie de machines.
  - Bij kleine antwoorden stuurt hij 0,82 tot 0,91 keer zoveel door als nginx. Dat is 1,4 tot 1,7 keer lighttpd en Apache, en 2,4 tot 3,6 keer Traefik en Caddy.
  - Zijn p99-latentie is de laagste na die van nginx.
- **Bij antwoorden van 100 KB speelt hij gelijk met nginx of gaat hij erover** (0,97 tot 1,43). De native engine stuurt het antwoord gaandeweg door, met een begrensde buffer. In zijn basisconfiguratie houdt nginx per doorgestuurd antwoord maar enkele tientallen KB in het geheugen (`proxy_buffers`) en kan hij de rest naar een tijdelijk bestand schrijven. We hebben dit punt niet aangepast.
- **In HTTPS** blijft de native engine tweede bij kleine antwoorden op de machines A en B. Op machine C zitten lighttpd en hij op hetzelfde niveau.
  - Bij antwoorden van 100 KB gaat lighttpd hem op machine C voorbij.
  - Op machine A gaan Caddy en Traefik iedereen voorbij, nginx inbegrepen. Ze zijn geschreven in Go, met hun eigen TLS-bibliotheek, die op deze processor uit 2010 blijkbaar efficiënter is. We hebben dat niet verder onderzocht.
- **De WAF kost weinig als reverse proxy**: 1 tot 9 % van de doorvoer in HTTP, met alle regels actief. De andere servers zijn zonder WAF gemeten: de vergelijking „met WAF” is niet eerlijk (zie §4).
- **Geheugen**: met de native engine gebruikt omega-serv 3.0.0 ongeveer 30 MB (27 tot 36 MB). Dat totaal omvat de Python-supervisor, het beveiligingsproces en de native engine. Dat is meerdere keren nginx, lighttpd of Apache, maar minder dan Caddy en drie tot vier keer minder dan Traefik. Bij de meting van 14 november (3.0.0 in voorbereiding) gebruikte hij ongeveer 50 MB.
- **De Python-engine** stuurt kleine antwoorden door met 0,08 tot 0,10 keer nginx: hij blijft de terugvalengine. De reverse-proxyzones met cache worden hem nog steeds toevertrouwd, en behouden dus zijn doorvoer.
- **Een correctie vóór deze metingen.** Een eerste meetreeks, op dezelfde dag en met hetzelfde protocol, plaatste de native engine bij kleine antwoorden op 0,32 tot 0,69 keer nginx. Op machine C bleef hij steken rond 78.000 req/s, ongeacht het aantal kernen. Zijn voorraad verbindingen naar de backend was te klein: hij opende er elke vijf verzoeken een nieuwe. Deze voorraad is vergroot en het doorsturen lichter gemaakt vóór de meetreeks die hier gepubliceerd is. De cijfers van de eerste meetreeks worden ook gepubliceerd.

### Grenzen van deze metingen

- **nginx is in zijn voordeel ingesteld**: hij houdt zijn verbindingen naar de backend open, wat hij in zijn basisconfiguratie niet doet. De andere servers staan in hun basisconfiguratie.
- **De backend draait op dezelfde machine**, via loopback. Op de machines A en B deelt hij zijn kernen met de client. Alleen de verhoudingen tussen servers, gemeten onder dezelfde omstandigheden, tellen dus. Op zichzelf levert deze backend ongeveer 345.000 req/s op machine C: hij beperkt daar geen enkele proxy.
- **Alleen HTTP/1.1**, naar de client net als naar de backend: omega-serv spreekt geen HTTP/2.
- **Ruwe cijfers**: [`docs/benchmarks/`](../../benchmarks/), bestanden `2026-11-14-*-reverse-proxy-brut.txt`, waaronder de eerste meetreeks (`2026-11-14-reverse-proxy-avant-correctif-brut.txt`).

---

## 6. De versies van omega-serv: 1.0 → 2.0 → 2.5 → 3.0.0

De drie versies zijn gemeten in dezelfde sessie als §4, op alle drie de machines, met hetzelfde protocol. Tussen haakjes: de verhouding met nginx (2 processen) van dezelfde sessie. †: campagne van 4 november na de optimalisatie van de WAF (zie §4). Versie 3.0.0 is gemeten op 19 november, met hetzelfde protocol; de verhoudingen ervan zijn berekend ten opzichte van nginx (2 processen), opnieuw gemeten in die sessie, dat binnen 3 % van zijn waarde van 4 november blijft.

### Kleine bestanden (1 KB): verzoeken per seconde

| Versie en modus | Machine A | Machine B | Machine C |
|---|---:|---:|---:|
| 1.0.0 | 1.547 (0,07) | 645 (0,03) | 8.870 (0,04) |
| 1.0.0 + WAF | 1.453 (0,07) | 561 (0,02) | 7.687 (0,03) |
| 2.0.0 | 1.740 (0,08) | 650 (0,03) | 10.245 (0,04) |
| 2.0.0 + WAF | 1.456 (0,07) | 565 (0,02) | 8.371 (0,03) |
| 2.0.0, 2 processen | 2.153 (0,10) | 1.277 (0,05) | 19.192 (0,08) |
| 2.0.0 + WAF, 2 processen | 1.775 (0,08) | 1.113 (0,05) | 15.351 (0,06) |
| 2.5, Python-engine | 1.507 (0,07) | 663 (0,03) | 10.553 (0,04) |
| 2.5, Python-engine + WAF | 1.561 (0,07) | 564 (0,02) | 8.365 (0,03) |
| 2.5, Python-engine, 2 processen | 2.354 (0,11) | 1.312 (0,05) | 19.911 (0,08) |
| 2.5, Python-engine + WAF, 2 processen | 1.901 (0,09) | 1.104 (0,04) | 15.783 (0,06) |
| **2.5, native engine** | **15.222 (0,70)** | **16.542 (0,67)** | **285.213 (1,15)** |
| **2.5, native engine + WAF †** | **11.990 (0,56)** | **12.998 (0,53)** | **264.484 (1,07)** |
| **2.5, native engine + WAF, 2 beveiligingsprocessen †** | **11.746 (0,55)** | **12.718 (0,52)** | **253.527 (1,02)** |
| 3.0.0, Python-engine | 1.309 (0,06) | 752 (0,03) | 9.482 (0,04) |
| 3.0.0, Python-engine + WAF | 1.168 (0,05) | 653 (0,03) | 8.788 (0,04) |
| 3.0.0, Python-engine, 2 processen | 1.733 (0,08) | 1.154 (0,05) | 17.234 (0,07) |
| 3.0.0, Python-engine + WAF, 2 processen | 1.605 (0,07) | 994 (0,04) | 14.873 (0,06) |
| **3.0.0, native engine** | **14.503 (0,68)** | **15.075 (0,63)** | **276.938 (1,15)** |
| **3.0.0, native engine + WAF** | **12.762 (0,60)** | **11.618 (0,48)** | **257.741 (1,07)** |
| **3.0.0, native engine + WAF, 2 beveiligingsprocessen** | **12.974 (0,61)** | **11.957 (0,50)** | **253.993 (1,06)** |

### Middelgrote bestanden, groot bestand en geheugen (1 proces, zonder WAF)

| Versie | 100 KB, req/s (A / B / C) | 5 MB, MB/s (A / B / C) | Geheugen in rust → na de belasting (A / B / C) |
|---|---|---|---|
| 1.0.0 | 1.071 / 563 / 7.625 | 578 / 549 / 3.640 | 21 → **98** / 22 → **98** / 23 → **73** MB |
| 2.0.0 | 1.570 / 603 / 9.469 | 1.665 / 1.470 / 14.058 | 26 → 30 / 27 → 31 / 28 → 32 MB |
| 2.5, Python-engine | 1.329 / 611 / 9.805 | 1.686 / 1.472 / 14.227 | 28 → 32 / 29 → 33 / 30 → 34 MB |
| **2.5, native engine** | **4.738 / 3.115 / 96.277** | **2.294 / 1.936 / 37.918** | **33 → 34 / 34 → 35 / 35 → 39 MB** |
| 3.0.0, Python-engine | 1.185 / 606 / 8.655 | 1.765 / 1.318 / 13.028 | 20 → 23 / 21 → 24 / 22 → 28 MB |
| **3.0.0, native engine** | **4.665 / 3.026 / 100.513** | **2.399 / 1.932 / 40.755** | **10 → 10 / 10 → 12 / 12 → 16 MB** |

### Grote gelijktijdige downloads

Test: 3 gelijktijdige downloads van een bestand van 300 MB, terwijl een kleine pagina doorlopend wordt opgevraagd. Twee doorgangen per versie en per machine, met bijna identieke resultaten. Het geheugen is hier de **RSS** van alle processen van de server, zoals in de oorspronkelijke test: die telt gedeeld geheugen meerdere keren, wat hogere waarden geeft dan de PSS van de andere tabellen.

| Versie | Piekgeheugen | Kleine pagina, slechtste geval: A / B / C |
|---|---:|---|
| 1.0.0 | **1.833 tot 1.836 MB** | **1,4 tot 1,9 s** / **1,4 tot 1,7 s** / 0,16 s |
| 2.0.0 | 39 tot 42 MB | 3 ms / 4 tot 6 ms / 1 ms |
| 2.5, Python-engine | 41 tot 44 MB | 2 ms / 4 ms / 1 ms |
| 2.5, native engine | 49 tot 55 MB | 1 tot 2 ms / 2 tot 4 ms / minder dan 1 ms |
| 3.0.0, Python-engine | 39 MB | 3 ms / 5 tot 8 ms / 1 ms |
| 3.0.0, native engine | 23 tot 26 MB | 1 ms / 2 tot 3 ms / minder dan 1 ms |

### Kosten van de actieve verdediging (1.0 → 2.0)

Meting van 26 oktober 2026 op machine A, sindsdien niet herhaald: kosten van een dreigingsobservatie door Active Defense, voor elk verdacht verzoek, gemeten op schijf (ext4) over 2.000 observaties.

| Meting | 1.0.0 | 2.0.0 |
|---|---:|---:|
| Mediaan | 2,84 ms | 0,23 ms |
| p99 | 11,6 ms | 2,3 ms |
| Maximum | 18 tot 20 ms | 37 tot 46 ms |

De mediaan wordt gedeeld door 12. Het maximum is in 2.0 daarentegen hoger: enkele losse pieken, verbonden met het periodiek wegschrijven van het SQLite-journaal naar schijf.

### Lezing

- **Van 1.0 naar 2.0** zit de vooruitgang in het geheugen en de grote bestanden, niet in de snelheid van kleine pagina's:
  - het geheugen na de belasting gaat van 73-98 MB naar 30-32 MB;
  - tijdens grote downloads gaat het van meer dan 1,8 GB naar ongeveer 40 MB, en blijft de server reactief (enkele milliseconden in plaats van bijna 2 seconden);
  - de doorvoer van grote bestanden wordt met 2,7 tot 3,9 vermenigvuldigd;
  - 2.0 voegt meerdere processen toe, die de doorvoer van kleine pagina's afhankelijk van de machine met 25 % tot bijna 100 % verhogen.
  1.0 laadde elk bestand volledig in het geheugen voordat het verstuurd werd. 2.0 verstuurt het in blokken, of laat het aan de kernel over.
- **Van 2.0 naar 2.5 verandert de Python-engine niet van snelheid**: de verschillen blijven onder 4 % op de machines B en C, en binnen de meetruis van machine A (−13 % tot +9 %), de gevoeligste voor achtergrondbelasting. De hele winst van 2.5 komt van de **native engine**: ongeveer ×10 tot ×27 bij kleine bestanden ten opzichte van de Python-engine, en de latentie gedeeld door 5 tot 15.
- **In 2.5 gebruikte de native engine in rust ongeveer 5 MB meer** dan de Python-engine (PSS): de prijs van het tweede programma. Met de WAF nog ongeveer 8 MB meer: de regels die in de native engine geladen zijn.
- **Van 2.5 naar 3.0.0 daalt het geheugen met 30 tot 70 %** met één proces:
  - native engine: 33-35 → 10-12 MB in rust. Als niets anders het vereist, krimpt de Python-supervisor tot een klein bewakingsprogramma, dat noch de configuratie noch de Python-server in het geheugen houdt;
  - Python-engine: 28-30 → 20-22 MB. De code van een optie wordt alleen geladen als die actief is, en de TLS-bibliotheek alleen als die gebruikt wordt;
  - native + WAF: 43-45 → 28-30 MB. Het beveiligingsproces ontstaat uit de verkleinde supervisor en deelt zijn geheugenpagina's met hem;
  - Python-engine met 2 processen: 40-43 → 35-38 MB;
  - tijdens grote downloads: 39 MB (Python) en 23 tot 26 MB (native), tegenover 41 tot 55 MB;
  - de native engine gebruikt nu half zoveel geheugen als de Python-engine.
- **Het werk aan het geheugen verandert de doorvoer niet**: een verweven test op de machines B en C, met de code van 3.0.0 vóór en na dit werk, geeft 1 tot 4 % verschil. Ten opzichte van 2.5 levert de Python-engine met 2 processen 12 tot 13 % minder op de machines B en C (26 % op machine A, de gevoeligste voor achtergrondbelasting); de code van 3.0.0 van vóór dit werk toont dezelfde achteruitgang, die dus van andere wijzigingen in 3.0.0 komt en nog onderzocht moet worden. De andere verschillen met 2.5 lopen van −13 % tot +13 %, in beide richtingen.

### Wat u over de native engine moet weten

- Hij is **optioneel**: de Python-engine blijft de standaardengine, en de terugvalengine.
- Hij levert zelf statische inhoud, omleidingen, herschrijvingen, aliassen, de cache, de foutpagina's, de beveiligingsheaders en TLS.
- Hij doorzoekt zelf de WAF-regels en handelt een verzoek waarop er geen enkele van toepassing is alleen af. Elk ander verzoek (overeenkomst of twijfel van de WAF, Active Defense, authenticatie) wordt door Python beslist, met precies dezelfde controles en dezelfde logs. Een instelbare controle legt toch één schoon verzoek op N aan Python voor, om na te gaan dat beide hetzelfde oordeel geven.
- Hij handelt de reverse proxy zelf af, WebSocket inbegrepen (sinds 3.0.0). De mapweergave en de interne pagina's worden aan Python gevraagd; FastCGI, bestandsupload en de reverse-proxyzones met cache worden hem voor de hele verbinding toevertrouwd. Die functies behouden dus de snelheid van de Python-engine.
- Met direct TLS worden FastCGI, bestandsupload en de reverse-proxyzones met cache niet door de native engine ondersteund: dan handelt de Python-engine af, en de interface meldt het.
- Hij vereist glibc 2.38 of nieuwer en OpenSSL 3. Start hij niet, dan compileert de installatie hem ter plaatse opnieuw, en anders blijft omega-serv op de Python-engine.

---

## 7. Functievergelijking

Legenda:
- ✅ ingebouwd;
- 🧩 officiële module van het project, in te schakelen of te installeren;
- 🔌 module of plugin van derden;
- ⚙️ via een extern hulpmiddel;
- ❌ ontbreekt.

„Commercial” duidt een functie aan die voorbehouden is aan de betaalde editie.

### HTTP-dienst

| Functie | nginx | lighttpd | Caddy | Apache | Traefik | omega-serv 2.5 |
|---|---|---|---|---|---|---|
| Taal van de server | C | C | Go | C | Go | Python, met een optionele native C++-engine |
| Statische bestanden leveren | ✅ | ✅ | ✅ | ✅ | ❌ (alleen proxy) | ✅ |
| ETag / 304 / Range | ✅ | ✅ | ✅ | ✅ | — | ✅ |
| Voorgecomprimeerde bestanden `.gz` / `.br` | ✅ `gzip_static` (`.br`: 🔌) | 🔌 Lua-script (mod_magnet) | ✅ `precompressed` | 🧩 mod_rewrite-recept | — | ✅ |
| Compressie on-the-fly | ✅ | ✅ mod_deflate | ✅ | 🧩 mod_deflate | ✅ middleware | ❌ |
| HTTP/2 | ✅ | ✅ | ✅ | 🧩 mod_http2 | ✅ | ❌ |
| HTTP/3 (QUIC) | ✅ | ❌ | ✅ | ❌ | ✅ | ❌ |
| PHP via FastCGI | ✅ | ✅ | ✅ | ✅ | ❌ | ✅ |
| Meerdere processen of kernen | ✅ workers | ⚠️ `max-worker`, afgeraden door de documentatie | ✅ (Go, alle kernen) | ✅ MPM | ✅ (Go) | ✅ `server.workers`; native engine: alle kernen |

### Reverse proxy

| Functie | nginx | lighttpd | Caddy | Apache | Traefik | omega-serv 2.5 |
|---|---|---|---|---|---|---|
| Lastverdeling | ✅ round robin, minste verbindingen, hash | ✅ fair, round-robin, hash, sticky | ✅ een twaalftal strategieën | 🧩 mod_proxy_balancer | ✅ wrr, p2c, hrw, least-time | ✅ 7 strategieën, waaronder de werkelijke belasting |
| Passieve gezondheid (defecte server uitsluiten) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Actieve gezondheid (periodieke controle) | Commercial (NGINX Plus) | ❌ | ✅ | 🧩 mod_proxy_hcheck | ✅ | ✅ |
| Cache van antwoorden | ✅ `proxy_cache` | ❌ | 🔌 | 🧩 mod_cache | Commercial | ✅ |
| WebSocket | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Service discovery (Docker, Kubernetes) | 🔌 | ❌ | 🔌 | ❌ | ✅ (kern van het project) | ❌ |

### TLS

| Functie | nginx | lighttpd | Caddy | Apache | Traefik | omega-serv 2.5 |
|---|---|---|---|---|---|---|
| Automatische certificaten (ACME, Let's Encrypt) | 🧩 `ngx_http_acme_module` | ⚙️ Certbot | ✅ standaard | 🧩 mod_md | ✅ | ⚙️ Certbot, met ingebouwde assistent en geplande vernieuwing |
| Lokale CA | ❌ | ❌ | ✅ interne CA (automatische uitgifte) | ❌ | ❌ | ✅ aanmaak, ondertekening van CSR, intrekking |

### Beveiliging

| Functie | nginx | lighttpd | Caddy | Apache | Traefik | omega-serv 2.5 |
|---|---|---|---|---|---|---|
| Snelheidsbeperking per client | ✅ `limit_req` | ⚠️ mod_evasive (alleen gelijktijdige verbindingen) | 🔌 caddy-ratelimit | 🔌 mod_evasive, mod_qos | ✅ middleware | ✅ |
| Grens gedeeld tussen processen | ✅ gedeelde geheugenzone | ❌ per proces geteld | — (1 enkel proces) | afhankelijk van de module | 1 instantie; meerdere met Redis | ✅ gedeeld geheugen |
| WAF (SQLi/XSS-signaturen, scanners…) | 🔌 ModSecurity, Commercial (App Protect) | ❌ (Lua-scripts te schrijven) | 🔌 Coraza | 🔌 ModSecurity | 🔌 plugins | ✅ ingebouwd |
| Blokkeerlijst met vervaldatum, herhaling | ⚙️ fail2ban | ⚙️ fail2ban | ⚙️ fail2ban | ⚙️ fail2ban | ⚙️ | ✅ ingebouwd |
| Lokazen, oorlogsmodus, incidenten, IoC-export | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ Active Defense |
| Getrapte blokkades in de tijd | ⚙️ fail2ban | ⚙️ fail2ban | ⚙️ fail2ban | ⚙️ fail2ban | ⚙️ | ✅ RIPOSTE |
| Beveiligingsaudit van de configuratie | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ `audit security` |
| Observatiemodus (loggen zonder blokkeren) | afhankelijk van de module | — | afhankelijk van de plugin | ✅ ModSecurity `DetectionOnly` | afhankelijk van de plugin | ✅ |

Getrapte blokkades: steeds langere blokkades voor adressen die terugkomen, over weken, lokaal of op netwerkniveau. fail2ban bereikt ze met zijn optie `bantime.increment`; RIPOSTE voegt beleidsregels toe die op de logs gemeten en vóór activering gesimuleerd worden, het opheffen van een actie en een noodstop.

### Uitbreidbaarheid

| Functie | nginx | lighttpd | Caddy | Apache | Traefik | omega-serv 2.5 |
|---|---|---|---|---|---|---|
| Scripttaal | 🧩 njs (JavaScript); 🔌 Lua (OpenResty) | ✅ Lua (mod_magnet) | Go-modules (hercompilatie) | 🧩 mod_lua | Go- of WebAssembly-plugins | 🔌 import van mod_magnet-scripts (optie `magnet`) |
| Ecosysteem van modules | zeer groot | gericht | groot | zeer groot | groot | geen: alles is ingebouwd |

---

## 8. Beheer en gebruiksgemak

| Server | Belangrijkste beheerwijze | Interface | Herladen zonder onderbreking |
|---|---|---|---|
| nginx | configuratiebestanden | geen (dashboard: NGINX Plus, commercieel) | ✅ `nginx -s reload` |
| lighttpd | configuratiebestand | geen (mod_status alleen-lezen) | ✅ zachte herstart |
| Caddy | Caddyfile of JSON | REST-beheer-API | ✅ via de API |
| Apache | configuratiebestanden en `.htaccess` | geen (mod_status alleen-lezen) | ✅ `graceful` |
| Traefik | containerlabels, bestanden of Kubernetes | webdashboard (alleen-lezen) | ✅ dynamische configuratie |
| omega-serv | terminalinterface (TUI) en opdrachtregel (CLI); het JSON-bestand hoeft niet bewerkt te worden | **volledige TUI met toetsenbord en muis, 17 talen, ingebouwde hulp** | ✅ voor de meeste instellingen; herstart aangekondigd voor de poort, TLS, de engine en het aantal processen |

Concreet beheer je met omega-serv de configuratie, de beveiliging, de logs, de systeemdiensten, de back-ups en de instanties vanuit één interface. Elke instelling wordt uitgelegd en gecontroleerd voordat ze geschreven wordt. Bij de andere servers bewerk je tekstbestanden en roep je daarna aparte hulpmiddelen in (Certbot, fail2ban, logrotate, ModSecurity, een monitoringtool…).

Daartegenover laat de aanpak „configuratiebestand” van nginx, Apache en Caddy zich heel goed automatiseren (Ansible, containers, versiebeheer). omega-serv heeft een scriptbare CLI, maar zijn automatiseringsecosysteem blijft beperkt.

---

## 9. Wat omega-serv extra biedt

Deze sectie neemt alleen op wat geen van de vergeleken servers zo levert, zonder module van derden of extern hulpmiddel.

1. **Volledig beheer in een terminalinterface.**
   - De interface dekt de hele server: de site, de beveiliging, de logs, de diensten, de back-ups en de instanties.
   - Ze werkt met toetsenbord en muis, op een server zonder grafisch scherm, zelfs via SSH.
   - Ze is beschikbaar in 17 talen en legt elke instelling uit.
   - De andere servers hebben geen beheerinterface (nginx, lighttpd, Apache), of alleen een API (Caddy) of een alleen-lezen dashboard (Traefik).
2. **Een ingebouwde actieve beveiliging, zonder modules samen te stellen.**
   - De WAF omvat signaturen, bewerkbare padlijsten, de herhaling, een blokkeerlijst met vervaldatum, de reputatie en een observatiemodus.
   - Active Defense voegt lokazen toe, een oorlogsmodus, het opvolgen van incidenten, de export van indicatoren van compromittering en een droge simulatie.
   - RIPOSTE reageert in de tijd: het onthoudt de adressen die terugkomen en past er getrapte antwoorden op toe, steeds langere blokkades (standaard 1 u, 6 u, 24 u, 7 dagen), lokaal in de blokkeerlijst of op netwerkniveau via fail2ban (omega-jail), of een verlengd lokaas. Elke beleidsregel kan op de echte logs gemeten en vóór activering gesimuleerd worden; elke actie blijft zichtbaar en kan opgeheven worden, met een noodstop.
   - Elders vereisen deze functies dat je ModSecurity of Coraza, regelsets en fail2ban samenstelt.
3. **Exacte beveiligingslimieten met meerdere processen.**
   - Met meerdere processen worden de snelheidsbeperking en de herhaling van de WAF in het geheugen tussen hen gedeeld. Een aanvaller kan zijn grens dus niet vermenigvuldigen met het aantal processen.
   - lighttpd documenteert het omgekeerde geval: met `server.max-worker` tellen `mod_evasive` en `mod_status` apart in elk proces.
   - nginx deelt ook zijn tellers (zones `limit_req`), maar heeft geen ingebouwde WAF.
4. **Twee engines, één gedrag.** De native engine en de Python-engine produceren dezelfde antwoorden en dezelfde logs, automatisch gecontroleerd op een vergelijkingsbank. De hulpmiddelen die de logs lezen (fail2ban bijvoorbeeld) zien geen verschil.
5. **Het importeren van lighttpd-mod_magnet-scripts.**
   - Een Lua-beveiligingsscript dat al voor lighttpd geschreven is, wordt zonder herschrijven geïmporteerd.
   - Het vult de ingebouwde bescherming aan zonder die ooit te kunnen verzwakken, en zijn compatibiliteit wordt vóór activering gecontroleerd.
6. **Het beheer van meerdere instanties.**
   - Een register houdt alle instanties bij, en de interface schakelt van de ene naar de andere.
   - Ze kan een instantie ook volledig verwijderen.
7. **Een beveiligingsaudit van de configuratie**: het commando `audit security` is informatief, blokkeert nooit en geeft afsluitcodes terug die in een script bruikbaar zijn.
8. **Externe logbronnen.**
   - De interface haalt op verzoek via SSH het log van een andere server op, zonder opgeslagen wachtwoord.
   - Ze kan het met lnav lezen en het samenvoegen met de lokale logs.
9. **Een niet uitschakelbare HTTP-verharding**, actief vanaf de installatie, welk profiel en welke engine ook:
   - strikte validatie van de Host-header;
   - weigering van de dubbelzinnigheden Content-Length / Transfer-Encoding;
   - beveiligingsheaders en CSP op de antwoorden van de site, ook op haar foutpagina's;
   - veilig lezen van X-Forwarded-For;
   - weigering om als root te starten.

---

## 10. Wat de anderen beter doen

- **Doorvoer**: lighttpd en nginx blijven de snelste bij kleine en middelgrote bestanden, op alle drie de machines. Zelfs met de native engine levert omega-serv ongeveer 0,7 keer nginx en 0,5 keer lighttpd bij kleine bestanden, en 0,3 tot 0,6 keer nginx bij bestanden van 100 KB. Voor een site met veel verkeer, een openbare API of een CDN zijn zij de juiste keuze.
- **Middelgrote bestanden**: Apache levert bestanden van 100 KB sneller dan de native engine van omega-serv, op alle drie de machines.
- **Reverse proxy**:
  - nginx stuurt kleine antwoorden 10 tot 22 % sneller door dan de native engine, en tot 1,6 keer sneller in HTTPS op machine C;
  - in HTTPS, bij antwoorden van 100 KB, gaat lighttpd hem voorbij op machine C, en Caddy en Traefik op machine A;
  - nginx, lighttpd en Apache sturen door met 4 tot 15 MB geheugen, omega-serv met ongeveer 30.
- **Geheugen**: lighttpd (1 MB), nginx (4 tot 5 MB) en Apache (4 tot 9 MB) passen bij zeer beperkte machines (embedded, kleine containers). omega-serv 3.0.0 heeft er afhankelijk van de modus 10 tot 55 nodig.
- **Kosten van de beveiliging**: de WAF heeft nog steeds kosten. Met de native engine kost hij 5 tot 22 % van de doorvoer bij kleine bestanden, snelheidsbeperking inbegrepen: omega-serv met WAF levert op de machines A en B 0,53 tot 0,56 keer nginx zonder WAF. Een verdacht of twijfelachtig verzoek (overeenkomst van een regel, niet-ASCII-tekst, bron die Active Defense volgt) gaat altijd via Python, en wordt met de snelheid van de Python-engine afgehandeld. Met magnet actief gaan alle verzoeken via Python, en deelt de WAF de doorvoer van de native engine dan door 4 tot 7, zoals vóór de optimalisatie.
- **Protocollen**: HTTP/2 bij alle anderen, HTTP/3 bij nginx, Caddy en Traefik. omega-serv spreekt alleen HTTP/1.1.
- **Automatisch HTTPS**: Caddy en Traefik hebben het standaard ingebouwd, nginx (`ngx_http_acme_module`) en Apache (`mod_md`) met een officiële module. omega-serv delegeert aan Certbot, met een assistent en een geplande vernieuwing.
- **Containeromgevingen**: de automatische service discovery van Traefik (Docker, Kubernetes) heeft geen tegenhanger in omega-serv.
- **Ecosysteem en volwassenheid**: nginx en Apache bieden duizenden modules, handleidingen en integraties, en tientallen jaren productiegebruik. Caddy biedt een modulesysteem in Go. omega-serv is een jong project, onderhouden door één persoon, en zijn native engine is recent.
- **Compressie on-the-fly**: omega-serv levert alleen bestanden die al gecomprimeerd zijn.

---

## 11. Welke server voor welk gebruik

| Behoefte | Aanbevolen keuze |
|---|---|
| Site met veel verkeer, openbare API, CDN, maximale doorvoer | **nginx** of **lighttpd** |
| Reverse proxy met maximale doorvoer, HTTP/2 of HTTP/3 naar de clients | **nginx** |
| Zeer beperkte machine, embedded, statische bestanden | **lighttpd** |
| Snelle start met automatisch HTTPS, korte configuratie | **Caddy** |
| Historische PHP-applicatie, `.htaccess`, gedeelde hosting | **Apache** |
| Docker, Kubernetes, microservices | **Traefik** |
| Kleine of middelgrote site, interne dienst, lab, VPN, beheer zonder bestanden te bewerken | **omega-serv** (native engine indien mogelijk) |
| Blootgestelde server waarvan je de beveiliging (WAF, getrapte blokkades, lokazen) vanuit één interface wilt zien en sturen | **omega-serv** |
| Reverse proxy met lastverdeling, gezondheid, cache en WAF, aangestuurd vanuit een interface | **omega-serv** (native engine: tweede achter nginx in doorvoer) |
| HTTP-verharding en actieve verdediging leren | **omega-serv** |

Deze hulpmiddelen laten zich ook combineren. Bijvoorbeeld:
- nginx of Traefik vooraan op het internet, met omega-serv erachter voor een interne dienst, zijn beveiliging en zijn beheer;
- omega-serv als interne reverse proxy voor meerdere applicatieservers.

---

## 12. De metingen reproduceren

De hulpmiddelen worden in de repository meegeleverd, onder `tools/bench/`. Je hebt geïnstalleerde nginx, lighttpd, Apache, Caddy en oha nodig (en Traefik voor de reverse proxy), de ontwikkelomgeving van omega-serv (`.venv`) en, voor de native engine, het binaire bestand gecompileerd in `native/omega-http-core/build-release`.

```sh
# 1. een meetmap voorbereiden (testbestanden, configuraties, omega-serv 1.0, 2.0 en huidige versie)
tools/bench/compare/setup.sh /pad/meting omega-serv-1.0.0.tar.gz omega-serv-2.0.0.tar.gz

# 2. de 21 configuraties, 3 verweven herhalingen (40 tot 60 minuten)
#    SRV_CPUS / CLI_CPUS: kernen van server en client (lscpu -e toont de topologie)
SRV_CPUS=0,1 CLI_CPUS=2,3 tools/bench/compare/campaign.sh /pad/meting > resultaten.txt

# 3. medianen
python3 tools/bench/compare/summarize.py resultaten.txt

# andere lijst van configuraties, bijvoorbeeld 4 processen
CONFIGS="nginx-4 lighttpd-4 caddy-4 apache-4 omega-v2-1-0-native omega-v2-4-1-native" \
  tools/bench/compare/campaign.sh /pad/meting > resultaten-4.txt

# grote downloads (geheugen en reactiviteit): huidige versie, Python-engine en dan native, dan 1.0
.venv/bin/python tools/bench/bigfile.py
BENCH_ENGINE=native .venv/bin/python tools/bench/bigfile.py
BENCH_SRC=/pad/meting/v1-archive/omega-serv/src \
BENCH_EXTRA_PATH=/pad/meting/v1-archive/omega-serv/vendor/omega-lib/src \
  .venv/bin/python tools/bench/bigfile.py

# reverse proxy (§5): backend, certificaat, configuraties van de 6 proxy's, daarna 3 verweven herhalingen
#    machine C: SRV_CPUS=0-3 BACK_CPUS=4,5 CLI_CPUS=6-9 en CONFIGS="nginx-4 lighttpd-4 apache-4 caddy-4 traefik-4 omega-nat-1-0 omega-nat-1-1"
tools/bench/proxy/setup.sh /pad/proxy /pad/naar/traefik
SRV_CPUS=0,1 CLI_CPUS=2,3 tools/bench/proxy/campaign.sh /pad/proxy > proxy.txt
python3 tools/bench/proxy/summarize.py proxy.txt

# alleen omega-serv opnieuw meten (geheugen van 3.0.0): bestanden, grote downloads en reverse proxy, nginx als referentie
MACHINE=a SRV_CPUS=0,2 CLI_CPUS=1,3 tools/bench/memoire-3.0.0.sh /pad/meting > geheugen.txt

# een willekeurige andere, al draaiende server meten, zonder oha
python3 tools/bench/bench_any.py --make-files /srv/test-webroot
python3 tools/bench/bench_any.py --port 8080
```

Namen van de configuraties: `nginx-N`, `lighttpd-N`, `apache-N`, `caddy-N` (N processen, of N kernen voor Caddy); `omega-vX-N-W` voor omega-serv (versie `v1`, `v20` of `v2` voor de huidige versie, N processen, W = 0 zonder WAF of 1 met), gevolgd door `-native` voor de native engine.

Voor de reverse proxy: `nginx-N`, `lighttpd-N`, `apache-N`, `caddy-N`, `traefik-N`, `omega-py-N-W` (Python-engine) en `omega-nat-N-W` (native engine, N beveiligingsprocessen), gevolgd door `-tls` voor HTTPS aan de clientkant.

Om uw eigen resultaten te publiceren, vermeld de machine, de versies, de verdeling van de kernen en de drie herhalingen.

---

## 13. Bronnen

Functies van de andere servers, volgens hun officiële documentatie (geraadpleegd op 26 oktober 2026).

**nginx**
- [Snelheidsbeperking `limit_req` (gedeelde geheugenzone)](https://nginx.org/en/docs/http/ngx_http_limit_req_module.html)
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
- [Automatisch HTTPS](https://caddyserver.com/docs/automatic-https)
- [`file_server` en `precompressed`](https://caddyserver.com/docs/caddyfile/directives/file_server)
- [`reverse_proxy` (strategieën, actieve en passieve gezondheid)](https://caddyserver.com/docs/caddyfile/directives/reverse_proxy)
- [Beheer-API](https://caddyserver.com/docs/api)
- [Snelheidsbeperkingsplugin caddy-ratelimit](https://github.com/mholt/caddy-ratelimit)
- [WAF Coraza voor Caddy](https://github.com/corazawaf/coraza-caddy)
- [caddy-docker-proxy](https://github.com/lucaslorentz/caddy-docker-proxy)

**Apache HTTP Server**
- [MPM event](https://httpd.apache.org/docs/2.4/mod/event.html)
- [mod_md (ACME)](https://httpd.apache.org/docs/2.4/mod/mod_md.html)
- [mod_proxy_balancer](https://httpd.apache.org/docs/2.4/mod/mod_proxy_balancer.html)
- [mod_proxy_hcheck](https://httpd.apache.org/docs/2.4/mod/mod_proxy_hcheck.html)
- [mod_http2](https://httpd.apache.org/docs/2.4/mod/mod_http2.html)
- [mod_deflate, voorgecomprimeerde inhoud](https://httpd.apache.org/docs/2.4/mod/mod_deflate.html)
- [ModSecurity](https://github.com/owasp-modsecurity/ModSecurity)

**Traefik**
- [Middleware `ratelimit` (in geheugen per instantie, Redis optioneel)](https://doc.traefik.io/traefik/reference/routing-configuration/http/middlewares/ratelimit/)
- [ACME](https://doc.traefik.io/traefik/https/acme/)
- [Providers (Docker, Kubernetes…)](https://doc.traefik.io/traefik/providers/overview/)

**fail2ban**
- [`jail.conf`: `bantime.increment`, `bantime.factor`, `bantime.multipliers`, `bantime.maxtime` (langere blokkades voor recidivisten)](https://github.com/fail2ban/fail2ban/blob/master/config/jail.conf) (geraadpleegd op 4 november 2026)

**Meethulpmiddel**
- [oha](https://github.com/hatoo/oha)

---

*Vergelijking gemaakt door kraynux voor omega-serv 2.5 en 3.0.0: metingen van 3 en 4 november 2026 op drie machines (reverse proxy: 14 november 2026; geheugen van omega-serv 3.0.0: 19 november 2026; actieve verdediging: 26 oktober 2026). Meet voor elke capaciteitsbeslissing op uw eigen hardware met de meegeleverde hulpmiddelen.*
