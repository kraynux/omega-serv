<!-- Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE) -->

# omega-serv vergeleken met de webservers op de markt

**Gemeten vergelijking: nginx · lighttpd · Apache · Caddy · Traefik · omega-serv 2.5**

🌐 [Français](../../comparatif-serveurs-web.md) · [English](../en/comparatif-serveurs-web.md) · [Español](../es/comparatif-serveurs-web.md) · [Português (Brasil)](../pt-BR/comparatif-serveurs-web.md) · [Italiano](../it/comparatif-serveurs-web.md) · [Deutsch](../de/comparatif-serveurs-web.md) · **Nederlands** · [Polski](../pl/comparatif-serveurs-web.md) · [Русский](../ru/comparatif-serveurs-web.md) · [中文](../zh-CN/comparatif-serveurs-web.md) · [Tiếng Việt](../vi/comparatif-serveurs-web.md) · [ไทย](../th/comparatif-serveurs-web.md) · [Bahasa Indonesia](../id/comparatif-serveurs-web.md) · [日本語](../ja/comparatif-serveurs-web.md) · [한국어](../ko/comparatif-serveurs-web.md) · [हिन्दी](../hi/comparatif-serveurs-web.md) · [العربية](../ar/comparatif-serveurs-web.md)

Dit document plaatst omega-serv tussen de meest gebruikte webservers. Het probeert geen „beste server” aan te wijzen: elk hulpmiddel beantwoordt aan andere behoeften, en elk heeft zijn sterke punten. Het levert drie dingen:

1. **echte metingen**, uitgevoerd op **drie** zeer verschillende **machines**, met dezelfde client, dezelfde bestanden en hetzelfde protocol, en reproduceerbaar;
2. een **functievergelijking**, elke functie gecontroleerd in de officiële documentatie van elke server (links aan het einde van het document), met onderscheid tussen wat ingebouwd is en wat een module of plugin vereist;
3. wat omega-serv **echt extra biedt**, en wat de anderen **beter doen dan hij**.

Alle prestatiemetingen zijn uitgevoerd op 3 en 4 november 2026. Geen enkel cijfer is van een andere site overgenomen of geschat. De ruwe cijfers worden met dit document gepubliceerd.

---

## Inhoud

1. [In het kort](#1-in-het-kort)
2. [Hoe deze vergelijking te lezen](#2-hoe-deze-vergelijking-te-lezen)
3. [Meetmethode](#3-meetmethode)
4. [Prestaties: omega-serv vergeleken met nginx, lighttpd, Apache en Caddy](#4-prestaties-omega-serv-vergeleken-met-nginx-lighttpd-apache-en-caddy)
5. [De versies van omega-serv: 1.0 → 2.0 → 2.5](#5-de-versies-van-omega-serv-10--20--25)
6. [Functievergelijking](#6-functievergelijking)
7. [Beheer en gebruiksgemak](#7-beheer-en-gebruiksgemak)
8. [Wat omega-serv extra biedt](#8-wat-omega-serv-extra-biedt)
9. [Wat de anderen beter doen](#9-wat-de-anderen-beter-doen)
10. [Welke server voor welk gebruik](#10-welke-server-voor-welk-gebruik)
11. [De metingen reproduceren](#11-de-metingen-reproduceren)
12. [Bronnen](#12-bronnen)

---

## 1. In het kort

- **omega-serv heeft twee engines.** De **Python-engine** verwerkt alles zelf. De **native engine**, geschreven in C++ en verschenen met 2.5, handelt de verzoeken zelf af; Python houdt de configuratie en de beveiligingsbeslissingen, waarbij de native engine zelf de verzoeken herkent waarop geen enkele WAF-regel van toepassing is.
- **Met de native engine, zonder WAF**, levert omega-serv kleine bestanden met **ongeveer 0,7 keer de snelheid van nginx**, op alle drie de machines. Hij staat daarmee **voor Apache en Caddy, achter nginx en lighttpd**.
- **Met de Python-engine** blijft omega-serv ver achter alle anderen: **3 tot 11 % van de snelheid van nginx**.
- **Met de WAF actief** inspecteert omega-serv elk verzoek, wat de andere gemeten servers niet doen. Met de native engine levert hij dan **0,53 tot 0,56 keer** de snelheid van nginx (zonder WAF) op de machines A en B, en 1,07 keer op machine C (4 kernen tegen 2): de WAF kost hem maar 5 tot 22 % van zijn doorvoer. Hij blijft voor Apache en Caddy, die zonder WAF gemeten zijn.
- **Middelgrote bestanden (100 KB)**: dit is het huidige zwakke punt van de native engine, met **0,3 tot 0,6 keer** nginx, achter Apache.
- **Grote bestanden (5 MB)**: nginx, lighttpd, Apache en omega-serv native halen dezelfde orde van doorvoer. Caddy is duidelijk trager op de snelste machine.
- **Geheugen**: lighttpd (1 MB), nginx (4 tot 5 MB) en Apache (4 tot 9 MB) zijn zeer zuinig. omega-serv gebruikt **30 tot 65 MB** afhankelijk van de modus, Caddy **50 tot 67 MB**.
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
| omega-serv | 1.0.0 en 2.0.0 (gepubliceerde archieven) en 2.5, onder Python 3.14 |
| Belastingclient | [oha](https://github.com/hatoo/oha) 1.16.0 (geschreven in Rust) |

Traefik is niet gemeten: het is geen bestandsserver (zie §6). Het staat alleen in de functievergelijking.

### Protocol

- **Isolatie van de processor**: server en client zijn vastgezet op aparte kernen (tabel hierboven). De client steelt dus geen tijd van de server, en alle servers beschikken over precies dezelfde middelen.
- **Dezelfde bestanden voor iedereen**: `small.html` (1 KB), `medium.png` (100 KB) en `large.bin` (5 MB), geleverd vanuit dezelfde map.
- **Toegangslogboek overal actief**, want een server in productie logt.
- **HTTP/1.1 onversleuteld, persistente verbindingen (keep-alive)**. De gelijktijdigheid is 32 verbindingen voor de bestanden van 1 KB en 100 KB, en 8 voor het bestand van 5 MB.
- **Duur**: 10 seconden per bestand en per configuratie.
- **Herhalingen**: 3 volledige, verweven rondes (alle configuraties in ronde 1, dan alle in ronde 2, enz.). De tabellen geven de **mediaan** van de drie rondes. Van ronde tot ronde blijft het verschil meestal onder 5 %.
- **Geheugen**: PSS van alle processen van de server, gemeten in rust en daarna na de belasting.
- **Configuraties**:
  - nginx, lighttpd, Apache en Caddy in hun basisconfiguratie: statische bestanden en toegangslogboek;
  - omega-serv met het profiel `standard`, de WAF uitgeschakeld en daarna ingeschakeld met alle meegeleverde regels (zonder snelheidsbeperking).
- **Aantal processen**: elke server wordt gemeten met 1 en daarna 2 processen: nginx `worker_processes`, lighttpd `server.max-worker`, Apache `StartServers`/`ServerLimit`, Caddy `GOMAXPROCS`, omega-serv `server.workers`. Voor de native engine van omega-serv telt `server.workers` de Python-beveiligingsprocessen; de native engine zelf gebruikt altijd alle kernen die hij krijgt.
- **Geen enkele fout**: alle antwoorden van alle metingen zijn 200.

### Grenzen om te kennen

- **Wat we vergelijken, zijn de verhoudingen.** De absolute waarden zouden op uw hardware, of op een dedicated server, anders zijn.
- **Loopback (127.0.0.1)**: de meting gaat niet over een echt netwerk. Op een echt netwerk is de doorvoer van grote bestanden bijna altijd beperkt door de bandbreedte, niet door de server. De doorvoer van enkele tientallen GB/s op machine C is alleen via loopback mogelijk.
- **Geen TLS** in deze metingen.
- **Machine A**: de productiedienst omega-serv van deze machine draaide op de achtergrond, zonder verkeer te ontvangen.
- **Machine C**: hybride processor (Zen 5- en Zen 5c-kernen). De server kreeg de 4 snelle kernen, de client de 6 andere.
- **Basisconfiguraties**: geen enkele server is geoptimaliseerd. Een ervaren beheerder zou ongetwijfeld meer uit elke server halen, omega-serv inbegrepen.
- **Ruwe cijfers**: [`docs/benchmarks/`](../../benchmarks/) (één bestand per machine).

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

| Server | Machine A | Machine B | Machine C |
|---|---:|---:|---:|
| lighttpd | 1 → 1 MB | 1 → 1 MB | 1 → 1 MB |
| nginx | 4 → 5 MB | 5 → 5 MB | 4 → 4 MB |
| Apache | 4 → 7 MB | 4 → 7 MB | 4 → 7 MB |
| omega-serv, Python-engine | 28 → 32 MB | 29 → 33 MB | 30 → 34 MB |
| **omega-serv, native engine** | **33 → 34 MB** | **34 → 35 MB** | **35 → 39 MB** |
| omega-serv, native + WAF † | 45 → 47 MB | 43 → 44 MB | 44 → 48 MB |
| omega-serv, Python-engine, 2 processen | 40 → 50 MB | 43 → 51 MB | 42 → 51 MB |
| omega-serv, native + WAF, 2 beveiligingsprocessen † | 45 → 47 MB | 43 → 44 MB | 55 → 57 MB |
| Caddy, 2 processen | 50 → 57 MB | 46 → 54 MB | 48 → 62 MB |

### Bij een gelijk aantal kernen: machine C met 4 processen

Aparte campagne van 3 november, hetzelfde protocol, op machine C: elke server krijgt 4 processen (of 4 kernen voor Caddy en de native engine). Referentie: nginx met 4 processen. De native engine met WAF staat hier niet meer in: gemeten vóór de optimalisatie van de WAF, is hij nog niet opnieuw met 4 processen gemeten.

| Server | 1 KB | 100 KB | 5 MB | Geheugen |
|---|---:|---:|---:|---:|
| lighttpd, 4 processen | 638.907 (**1,46**) | 312.402 (**1,21**) | 41.982 MB/s (0,93) | 1 → 2 MB |
| nginx, 4 processen | 438.496 (1,00) | 258.242 (1,00) | 45.162 MB/s (1,00) | 5 → 5 MB |
| **omega-serv, native engine** | **294.083 tot 310.972 (0,67 tot 0,71)** | **108.991 tot 109.955 (0,42)** | **40.137 tot 40.463 MB/s (0,89 tot 0,90)** | **35 → 38 MB** |
| Apache, 4 processen | 200.592 (0,46) | 162.607 (0,63) | 39.664 MB/s (0,88) | 6 → 9 MB |
| Caddy, 4 kernen | 97.085 (0,22) | 35.900 (0,14) | 5.998 MB/s (0,13) | 52 → 67 MB |
| omega-serv, Python-engine, 4 processen | 37.697 (0,09) | 35.064 (0,14) | 37.123 MB/s (0,82) | 48 → 66 MB |

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
- **Geheugen**: omega-serv gebruikt enkele tientallen MB meer dan nginx, lighttpd of Apache, vooral door Python, en evenveel als Caddy. Met de native engine zonder WAF blijft het geheugen tijdens de belasting bijna stabiel.
- **Om deze cijfers te plaatsen**: zelfs het traagste geval, de Python-engine met WAF op machine B (564 req/s), staat voor bijna 50 miljoen verzoeken per dag. Dat ligt ver boven de behoeften van een persoonlijke site, een interne dienst of een lab. Snelheid is alleen echt doorslaggevend voor een site met veel verkeer.

---

## 5. De versies van omega-serv: 1.0 → 2.0 → 2.5

De drie versies zijn gemeten in dezelfde sessie als §4, op alle drie de machines, met hetzelfde protocol. Tussen haakjes: de verhouding met nginx (2 processen) van dezelfde sessie. †: campagne van 4 november na de optimalisatie van de WAF (zie §4).

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

### Middelgrote bestanden, groot bestand en geheugen (1 proces, zonder WAF)

| Versie | 100 KB, req/s (A / B / C) | 5 MB, MB/s (A / B / C) | Geheugen in rust → na de belasting (A / B / C) |
|---|---|---|---|
| 1.0.0 | 1.071 / 563 / 7.625 | 578 / 549 / 3.640 | 21 → **98** / 22 → **98** / 23 → **73** MB |
| 2.0.0 | 1.570 / 603 / 9.469 | 1.665 / 1.470 / 14.058 | 26 → 30 / 27 → 31 / 28 → 32 MB |
| 2.5, Python-engine | 1.329 / 611 / 9.805 | 1.686 / 1.472 / 14.227 | 28 → 32 / 29 → 33 / 30 → 34 MB |
| **2.5, native engine** | **4.738 / 3.115 / 96.277** | **2.294 / 1.936 / 37.918** | **33 → 34 / 34 → 35 / 35 → 39 MB** |

### Grote gelijktijdige downloads

Test: 3 gelijktijdige downloads van een bestand van 300 MB, terwijl een kleine pagina doorlopend wordt opgevraagd. Twee doorgangen per versie en per machine, met bijna identieke resultaten. Het geheugen is hier de **RSS** van alle processen van de server, zoals in de oorspronkelijke test: die telt gedeeld geheugen meerdere keren, wat hogere waarden geeft dan de PSS van de andere tabellen.

| Versie | Piekgeheugen | Kleine pagina, slechtste geval: A / B / C |
|---|---:|---|
| 1.0.0 | **1.833 tot 1.836 MB** | **1,4 tot 1,9 s** / **1,4 tot 1,7 s** / 0,16 s |
| 2.0.0 | 39 tot 42 MB | 3 ms / 4 tot 6 ms / 1 ms |
| 2.5, Python-engine | 41 tot 44 MB | 2 ms / 4 ms / 1 ms |
| 2.5, native engine | 49 tot 55 MB | 1 tot 2 ms / 2 tot 4 ms / minder dan 1 ms |

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
- **De native engine gebruikt in rust ongeveer 5 MB meer** dan de Python-engine (PSS): dat is de prijs van het tweede programma. Met de WAF gebruikt hij nog ongeveer 8 MB meer: de regels die in de native engine geladen zijn.

### Wat u over de native engine moet weten

- Hij is **optioneel**: de Python-engine blijft de standaardengine, en de terugvalengine.
- Hij levert zelf statische inhoud, omleidingen, herschrijvingen, aliassen, de cache, de foutpagina's, de beveiligingsheaders en TLS.
- Hij doorzoekt zelf de WAF-regels en handelt een verzoek waarop er geen enkele van toepassing is alleen af. Elk ander verzoek (overeenkomst of twijfel van de WAF, Active Defense, authenticatie) wordt door Python beslist, met precies dezelfde controles en dezelfde logs. Een instelbare controle legt toch één schoon verzoek op N aan Python voor, om na te gaan dat beide hetzelfde oordeel geven.
- De mapweergave en de interne pagina's worden aan Python gevraagd; de reverse proxy, FastCGI, bestandsupload en WebSocket worden hem voor de hele verbinding toevertrouwd. Deze functies behouden dus de snelheid van de Python-engine.
- Met direct TLS worden de reverse proxy, FastCGI en bestandsupload niet door de native engine ondersteund: dan handelt de Python-engine af, en de interface meldt het.
- Hij vereist glibc 2.38 of nieuwer en OpenSSL 3. Start hij niet, dan compileert de installatie hem ter plaatse opnieuw, en anders blijft omega-serv op de Python-engine.

---

## 6. Functievergelijking

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

## 7. Beheer en gebruiksgemak

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

## 8. Wat omega-serv extra biedt

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

## 9. Wat de anderen beter doen

- **Doorvoer**: lighttpd en nginx blijven de snelste bij kleine en middelgrote bestanden, op alle drie de machines. Zelfs met de native engine levert omega-serv ongeveer 0,7 keer nginx en 0,5 keer lighttpd bij kleine bestanden, en 0,3 tot 0,6 keer nginx bij bestanden van 100 KB. Voor een site met veel verkeer, een openbare API of een CDN zijn zij de juiste keuze.
- **Middelgrote bestanden**: Apache levert bestanden van 100 KB sneller dan de native engine van omega-serv, op alle drie de machines.
- **Geheugen**: lighttpd (1 MB), nginx (4 tot 5 MB) en Apache (4 tot 9 MB) passen bij zeer beperkte machines (embedded, kleine containers). omega-serv heeft er 30 tot 65 nodig.
- **Kosten van de beveiliging**: de WAF heeft nog steeds kosten. Met de native engine kost hij 5 tot 22 % van de doorvoer bij kleine bestanden, snelheidsbeperking inbegrepen: omega-serv met WAF levert op de machines A en B 0,53 tot 0,56 keer nginx zonder WAF. Een verdacht of twijfelachtig verzoek (overeenkomst van een regel, niet-ASCII-tekst, bron die Active Defense volgt) gaat altijd via Python, en wordt met de snelheid van de Python-engine afgehandeld. Met magnet actief gaan alle verzoeken via Python, en deelt de WAF de doorvoer van de native engine dan door 4 tot 7, zoals vóór de optimalisatie.
- **Protocollen**: HTTP/2 bij alle anderen, HTTP/3 bij nginx, Caddy en Traefik. omega-serv spreekt alleen HTTP/1.1.
- **Automatisch HTTPS**: Caddy en Traefik hebben het standaard ingebouwd, nginx (`ngx_http_acme_module`) en Apache (`mod_md`) met een officiële module. omega-serv delegeert aan Certbot, met een assistent en een geplande vernieuwing.
- **Containeromgevingen**: de automatische service discovery van Traefik (Docker, Kubernetes) heeft geen tegenhanger in omega-serv.
- **Ecosysteem en volwassenheid**: nginx en Apache bieden duizenden modules, handleidingen en integraties, en tientallen jaren productiegebruik. Caddy biedt een modulesysteem in Go. omega-serv is een jong project, onderhouden door één persoon, en zijn native engine is recent.
- **Compressie on-the-fly**: omega-serv levert alleen bestanden die al gecomprimeerd zijn.

---

## 10. Welke server voor welk gebruik

| Behoefte | Aanbevolen keuze |
|---|---|
| Site met veel verkeer, openbare API, CDN, maximale doorvoer | **nginx** of **lighttpd** |
| Zeer beperkte machine, embedded, statische bestanden | **lighttpd** |
| Snelle start met automatisch HTTPS, korte configuratie | **Caddy** |
| Historische PHP-applicatie, `.htaccess`, gedeelde hosting | **Apache** |
| Docker, Kubernetes, microservices | **Traefik** |
| Kleine of middelgrote site, interne dienst, lab, VPN, beheer zonder bestanden te bewerken | **omega-serv** (native engine indien mogelijk) |
| Blootgestelde server waarvan je de beveiliging (WAF, getrapte blokkades, lokazen) vanuit één interface wilt zien en sturen | **omega-serv** |
| Interne reverse proxy met lastverdeling, gezondheid en cache, aangestuurd vanuit een interface | **omega-serv** |
| HTTP-verharding en actieve verdediging leren | **omega-serv** |

Deze hulpmiddelen laten zich ook combineren. Bijvoorbeeld:
- nginx of Traefik vooraan op het internet, met omega-serv erachter voor een interne dienst, zijn beveiliging en zijn beheer;
- omega-serv als interne reverse proxy voor meerdere applicatieservers.

---

## 11. De metingen reproduceren

De hulpmiddelen worden in de repository meegeleverd, onder `tools/bench/`. Je hebt geïnstalleerde nginx, lighttpd, Apache, Caddy en oha nodig, de ontwikkelomgeving van omega-serv (`.venv`) en, voor de native engine, het binaire bestand gecompileerd in `native/omega-http-core/build-release`.

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

# een willekeurige andere, al draaiende server meten, zonder oha
python3 tools/bench/bench_any.py --make-files /srv/test-webroot
python3 tools/bench/bench_any.py --port 8080
```

Namen van de configuraties: `nginx-N`, `lighttpd-N`, `apache-N`, `caddy-N` (N processen, of N kernen voor Caddy); `omega-vX-N-W` voor omega-serv (versie `v1`, `v20` of `v2` voor de huidige versie, N processen, W = 0 zonder WAF of 1 met), gevolgd door `-native` voor de native engine.

Om uw eigen resultaten te publiceren, vermeld de machine, de versies, de verdeling van de kernen en de drie herhalingen.

---

## 12. Bronnen

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

*Vergelijking gemaakt door kraynux voor omega-serv 2.5: metingen van 3 en 4 november 2026 op drie machines (actieve verdediging: 26 oktober 2026). Meet voor elke capaciteitsbeslissing op uw eigen hardware met de meegeleverde hulpmiddelen.*
