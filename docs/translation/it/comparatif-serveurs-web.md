<!-- Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE) -->

# omega-serv a confronto con i server web del mercato

**Confronto misurato: nginx · lighttpd · Apache · Caddy · Traefik · omega-serv 2.5 e 3.0.0**

🌐 [Français](../../comparatif-serveurs-web.md) · [English](../en/comparatif-serveurs-web.md) · [Español](../es/comparatif-serveurs-web.md) · [Português (Brasil)](../pt-BR/comparatif-serveurs-web.md) · **Italiano** · [Deutsch](../de/comparatif-serveurs-web.md) · [Nederlands](../nl/comparatif-serveurs-web.md) · [Polski](../pl/comparatif-serveurs-web.md) · [Русский](../ru/comparatif-serveurs-web.md) · [中文](../zh-CN/comparatif-serveurs-web.md) · [Tiếng Việt](../vi/comparatif-serveurs-web.md) · [ไทย](../th/comparatif-serveurs-web.md) · [Bahasa Indonesia](../id/comparatif-serveurs-web.md) · [日本語](../ja/comparatif-serveurs-web.md) · [한국어](../ko/comparatif-serveurs-web.md) · [हिन्दी](../hi/comparatif-serveurs-web.md) · [العربية](../ar/comparatif-serveurs-web.md)

Questo documento colloca omega-serv tra i server web più diffusi. Non cerca di designare un «server migliore»: ogni strumento risponde a esigenze diverse, e ognuno ha i suoi punti di forza. Fornisce tre cose:

1. **misure reali**, fatte su **tre macchine** molto diverse, con lo stesso client, gli stessi file e lo stesso protocollo, e riproducibili;
2. un **confronto delle funzioni**, ciascuna verificata nella documentazione ufficiale di ogni server (link alla fine del documento), distinguendo ciò che è integrato da ciò che richiede un modulo o un plugin;
3. ciò che omega-serv **porta davvero in più**, e ciò che gli altri fanno **meglio di lui**.

Le misure come server di file sono state fatte il 3 e il 4 novembre 2026 (omega-serv 2.5), quelle del reverse proxy il 14 novembre 2026 (omega-serv 3.0.0, in preparazione). La memoria di omega-serv 3.0.0, nettamente ridotta da allora, è stata rimisurata il 19 novembre 2026 su tutte e tre le macchine, con lo stesso protocollo (§4, §5 e §6). Nessun dato è ripreso da un altro sito o stimato. I dati grezzi sono pubblicati con questo documento.

---

## Sommario

1. [In breve](#1-in-breve)
2. [Come leggere questo confronto](#2-come-leggere-questo-confronto)
3. [Metodo di misura](#3-metodo-di-misura)
4. [Prestazioni: omega-serv a confronto con nginx, lighttpd, Apache e Caddy](#4-prestazioni-omega-serv-a-confronto-con-nginx-lighttpd-apache-e-caddy)
5. [Prestazioni come reverse proxy: omega-serv a confronto con nginx, lighttpd, Apache, Caddy e Traefik](#5-prestazioni-come-reverse-proxy-omega-serv-a-confronto-con-nginx-lighttpd-apache-caddy-e-traefik)
6. [Le versioni di omega-serv: 1.0 → 2.0 → 2.5 → 3.0.0](#6-le-versioni-di-omega-serv-10--20--25--300)
7. [Confronto delle funzioni](#7-confronto-delle-funzioni)
8. [Amministrazione ed ergonomia](#8-amministrazione-ed-ergonomia)
9. [Cosa porta in più omega-serv](#9-cosa-porta-in-più-omega-serv)
10. [Cosa fanno meglio gli altri](#10-cosa-fanno-meglio-gli-altri)
11. [Quale server per quale uso](#11-quale-server-per-quale-uso)
12. [Riprodurre le misure](#12-riprodurre-le-misure)
13. [Fonti](#13-fonti)

---

## 1. In breve

- **omega-serv ha due motori.** Il **motore Python** elabora tutto da sé. Il **motore nativo**, scritto in C++ e introdotto con la 2.5, serve da sé le richieste; Python mantiene la configurazione e le decisioni di sicurezza, mentre il nativo riconosce da solo le richieste a cui non corrisponde alcuna regola del WAF.
- **Con il motore nativo, senza WAF**, omega-serv serve i file piccoli a **circa 0,7 volte la velocità di nginx**, su tutte e tre le macchine. Si colloca così **davanti ad Apache e Caddy, dietro nginx e lighttpd**.
- **Con il motore Python**, omega-serv resta molto dietro a tutti gli altri: **dal 3 all'11 % della velocità di nginx**.
- **Con il WAF attivo**, omega-serv ispeziona ogni richiesta, cosa che gli altri server misurati non fanno. Con il motore nativo, serve allora **da 0,53 a 0,56 volte** la velocità di nginx (senza WAF) sulle macchine A e B, e 1,07 volte sulla macchina C (4 core contro 2): il WAF gli toglie solo dal 5 al 22 % del throughput. Resta davanti ad Apache e Caddy misurati senza WAF.
- **File medi (100 KB)**: è il punto debole attuale del motore nativo, a **da 0,3 a 0,6 volte** nginx, dietro Apache.
- **File grandi (5 MB)**: nginx, lighttpd, Apache e omega-serv nativo raggiungono lo stesso ordine di throughput. Caddy è nettamente più lento sulla macchina più veloce.
- **Come reverse proxy (3.0.0)**, il motore nativo inoltra le risposte piccole a **da 0,82 a 0,91 volte nginx**, e le risposte da 100 KB **alla stessa velocità o più velocemente** (da 0,97 a 1,43). È **secondo dietro nginx**, davanti a lighttpd, Apache, Traefik e Caddy. In HTTPS, resta secondo sulle risposte piccole delle macchine A e B; lighttpd lo eguaglia sulla macchina C.
- **Memoria**: lighttpd (1 MB), nginx (da 4 a 5 MB) e Apache (da 4 a 9 MB) sono molto parchi. omega-serv 3.0.0 occupa **da 10 a 16 MB** con il motore nativo, **da 20 a 33 MB** con il motore Python o il WAF, e da 35 a 55 MB con 2 processi; Caddy **da 50 a 67 MB**. La 2.5 occupava da 28 a 57 MB.
- **Cosa ha in più omega-serv**: un'amministrazione completa in interfaccia da terminale, in 17 lingue; un WAF e una difesa attiva integrati; limiti di sicurezza esatti con più processi; l'importazione di script mod_magnet di lighttpd; la gestione di più istanze.
- **Cosa non ha**: HTTP/2 e HTTP/3, la compressione al volo, la scoperta dei servizi Docker/Kubernetes, un client ACME integrato (passa per Certbot), un ecosistema di moduli.

---

## 2. Come leggere questo confronto

Alcune nozioni ritornano in tutto il documento.

- **Richieste al secondo (req/s)**: il numero di file che un server invia in un secondo. Più è alto, meglio è.
- **Distanza da nginx**: i valori assoluti dipendono enormemente dalla macchina. Sulle nostre tre macchine, nginx va da 22.000 a 440.000 req/s. Ciò che resta stabile è **il rapporto tra i server**. Le tabelle danno quindi, accanto a ogni valore, il suo rapporto con nginx misurato nella stessa sessione: **1,00 = veloce quanto nginx**, 0,50 = metà, 1,50 = una volta e mezza.
- **Latenza p99**: il tempo di risposta che il 99 % delle richieste non supera. Mostra i «momenti difficili» che una media nasconde.
- **PSS (*Proportional Set Size*)**: la memoria realmente occupata da tutti i processi del server. Una pagina condivisa tra più processi è contata una sola volta.
- **Processi e core**: un server può usare più core del processore. Ognuno lo fa a modo suo. nginx, lighttpd, Apache e omega-serv in modalità Python avviano più processi. Caddy, in Go, distribuisce il lavoro sui core. Il motore nativo di omega-serv avvia un thread per core disponibile. Per confrontare ad armi pari, diamo a ogni server **gli stessi core**.
- **WAF (*Web Application Firewall*)**: un filtro che ispeziona ogni richiesta per bloccare gli attacchi (iniezioni, scanner…). omega-serv lo integra. Gli altri server possono riceverne uno come modulo (ModSecurity, Coraza), ma **sono stati misurati senza**, nella loro configurazione di base.

**Il riflesso giusto**: confrontare i rapporti, non i valori assoluti, e verificare sempre se il WAF è attivo.

---

## 3. Metodo di misura

### Le tre macchine

| | Macchina A | Macchina B | Macchina C |
|---|---|---|---|
| Processore | Intel Core i5 M480, 2,67 GHz (2010) | Intel Celeron J3455, 1,5 GHz (2016) | AMD Ryzen AI 9 365 (2024) |
| Core | 2 core fisici, 4 thread | 4 core, senza hyperthreading | 10 core (4 Zen 5 + 6 Zen 5c), 20 thread |
| Memoria | 8 GB | 8 GB | 32 GB |
| Sistema | Mabox Linux (base Manjaro), kernel 6.18 | EndeavourOS, kernel 7.2 | Arch Linux, kernel 7.2 (CachyOS) |
| Core del server | 1 core fisico (thread 0 e 2) | 2 core (0 e 1) | 4 core Zen 5, un thread ciascuno (da 0 a 3) |
| Core del client | 1 core fisico (thread 1 e 3) | 2 core (2 e 3) | 6 core Zen 5c (da 4 a 9) |

La macchina A è un vecchio portatile, la macchina B un mini PC a basso consumo, la macchina C un portatile recente, collegato alla rete, con profilo energetico «bilanciato». Coprono una gamma che va da un piccolo server domestico a una macchina attuale.

### Software

| Software | Versione |
|---|---|
| nginx | 1.30.4 (A), 1.30.5 (B, C) |
| lighttpd | 1.4.85 |
| Apache HTTP Server | 2.4.69, MPM `event` |
| Caddy | 2.11.4 (A, B), 2.11.7 (C) |
| omega-serv | 1.0.0 e 2.0.0 (archivi pubblicati), 2.5 e 3.0.0, con Python 3.14 |
| Client di carico | [oha](https://github.com/hatoo/oha) 1.16.0 (scritto in Rust) |

Traefik non è stato misurato come server di file: non lo è (vedi §7). È misurato come reverse proxy, il suo ruolo, al §5.

### Protocollo

- **Isolamento del processore**: server e client sono fissati su core separati (tabella qui sopra). Il client non ruba quindi tempo al server, e tutti i server dispongono esattamente delle stesse risorse.
- **Stessi file per tutti**: `small.html` (1 KB), `medium.png` (100 KB) e `large.bin` (5 MB), serviti dalla stessa cartella.
- **Log di accesso attivo ovunque**, perché un server in produzione registra.
- **HTTP/1.1 in chiaro, connessioni persistenti (keep-alive)**. La concorrenza è di 32 connessioni per i file da 1 KB e 100 KB, e di 8 per il file da 5 MB.
- **Durata**: 10 secondi per file e per configurazione.
- **Ripetizioni**: 3 giri completi, intercalati (tutte le configurazioni al giro 1, poi tutte al giro 2, ecc.). Le tabelle danno la **mediana** dei tre giri. Da un giro all'altro, lo scarto resta per lo più sotto il 5 %.
- **Memoria**: PSS di tutti i processi del server, rilevata a riposo e poi dopo il carico. Quella di omega-serv 3.0.0 è stata rimisurata il 19 novembre 2026 con nginx come riferimento nella stessa sessione: resta entro il 3 % del suo throughput del 4 novembre sui file piccoli, ed entro 1 MB della sua memoria.
- **Configurazioni**:
  - nginx, lighttpd, Apache e Caddy nella loro configurazione di base: file statici e log di accesso;
  - omega-serv con il profilo `standard`, il WAF disattivato e poi attivato con tutte le regole fornite (senza limitazione di frequenza).
- **Numero di processi**: ogni server è misurato con 1 e poi 2 processi: nginx `worker_processes`, lighttpd `server.max-worker`, Apache `StartServers`/`ServerLimit`, Caddy `GOMAXPROCS`, omega-serv `server.workers`. Per il motore nativo di omega-serv, `server.workers` conta i processi Python di sicurezza; il motore nativo, invece, usa sempre tutti i core che gli vengono dati.
- **Nessun errore**: tutte le risposte di tutte le misure sono 200.

### Limiti da conoscere

- **Ciò che confrontiamo sono i rapporti.** I valori assoluti sarebbero diversi sul vostro hardware, o su un server dedicato.
- **Loopback (127.0.0.1)**: la misura non passa per una rete reale. Su una rete reale, il throughput dei file grandi è quasi sempre limitato dalla banda, non dal server. I throughput di diverse decine di GB/s della macchina C sono possibili solo in loopback.
- **Nessun TLS** nelle misure come server di file (§4 e §6). Il reverse proxy (§5) è misurato in HTTP e in HTTPS.
- **Macchina A**: il servizio omega-serv di produzione di questa macchina girava in background, senza ricevere traffico.
- **Macchina C**: processore ibrido (core Zen 5 e Zen 5c). Il server ha ricevuto i 4 core veloci, il client gli altri 6.
- **Configurazioni di base**: nessun server è stato ottimizzato. Un amministratore esperto otterrebbe senza dubbio di più da ciascuno, omega-serv compreso.
- **Dati grezzi**: [`docs/benchmarks/`](../../benchmarks/) (un file per macchina e per campagna; nuova misura della 3.0.0: `2026-11-19-*-memoire-3.0.0-brut.txt`).

---

## 4. Prestazioni: omega-serv a confronto con nginx, lighttpd, Apache e Caddy

In tutte le tabelle, il valore di riferimento è **nginx con 2 processi** (= 1,00), misurato nella stessa sessione sulla stessa macchina. Sulle macchine A e B, è la configurazione che occupa tutti i core dati al server.

### File piccoli (1 KB): richieste al secondo

| Server | Macchina A | Macchina B | Macchina C |
|---|---:|---:|---:|
| lighttpd, 2 processi | 33.138 (**1,52**) | 31.125 (**1,26**) | 378.590 (**1,53**) |
| nginx, 2 processi | 21.801 (1,00) | 24.705 (1,00) | 248.184 (1,00) |
| **omega-serv, motore nativo** | **15.222 (0,70)** | **16.542 (0,67)** | **285.213 (1,15 \*)** |
| omega-serv, nativo + WAF † | 11.990 (0,56) | 12.998 (0,53) | 264.484 (1,07 \*) |
| omega-serv, nativo + WAF, 2 processi di sicurezza † | 11.746 (0,55) | 12.718 (0,52) | 253.527 (1,02 \*) |
| Apache, 2 processi | 9.192 (0,42) | 8.634 (0,35) | 188.335 (0,76) |
| Caddy, 2 processi | 5.749 (0,26) | 4.116 (0,17) | 52.897 (0,21) |
| omega-serv, motore Python, 2 processi | 2.354 (0,11) | 1.312 (0,05) | 19.911 (0,08) |
| omega-serv, Python + WAF, 2 processi | 1.901 (0,09) | 1.104 (0,04) | 15.783 (0,06) |
| omega-serv, motore Python | 1.507 (0,07) | 663 (0,03) | 10.553 (0,04) |
| omega-serv, Python + WAF | 1.561 (0,07) | 564 (0,02) | 8.365 (0,03) |

\* Sulla macchina C, il motore nativo usa i suoi 4 core, mentre nginx ne usa solo 2 con 2 processi. Il confronto a parità di core è dato più sotto: il rapporto torna lì a **da 0,67 a 0,71**, come sulle altre macchine.

† Misurato il 4 novembre, dopo l'ottimizzazione del WAF, in una campagna separata con lo stesso protocollo. Il rapporto è calcolato con nginx (2 processi) di quella campagna: 21 439, 24.424 e 248.127 req/s sui file piccoli, 11 545, 11.004 e 157.491 sui file da 100 KB. Prima di questa ottimizzazione, il motore nativo con WAF serviva 3 495, 2.622 e 39.000 req/s (da 0,11 a 0,16 volte nginx), perché ogni richiesta passava da Python. Dati grezzi: file `*-waf-natif-brut.txt`.

Con 1 solo processo, nginx fa da 0,52 a 0,73, lighttpd da 0,81 a 1,43, Apache da 0,33 a 0,74 e Caddy da 0,09 a 0,17 (dati grezzi).

### Latenza p99 sui file piccoli

| Server | Macchina A | Macchina B | Macchina C |
|---|---:|---:|---:|
| lighttpd, 2 processi | 4,4 ms | 4,1 ms | 0,2 ms |
| nginx, 2 processi | 4,9 ms | 5,2 ms | 0,2 ms |
| **omega-serv, motore nativo** | **6,1 ms** | **6,2 ms** | **0,3 ms** |
| omega-serv, nativo + WAF † | 7,2 ms | 6,7 ms | 0,3 ms |
| Apache, 2 processi | 18,8 ms | 20,6 ms | 0,8 ms |
| Caddy, 2 processi | 24,1 ms | 30,5 ms | 2,8 ms |
| omega-serv, motore Python, 2 processi | 22,6 ms | 28,1 ms | 3,3 ms |
| omega-serv, motore Python | 32,0 ms | 51,6 ms | 4,4 ms |

### File medi (100 KB): richieste al secondo

| Server | Macchina A | Macchina B | Macchina C |
|---|---:|---:|---:|
| lighttpd, 2 processi | 13.561 (**1,08**) | 12.126 (**1,07**) | 197.905 (**1,26**) |
| nginx, 2 processi | 12.513 (1,00) | 11.303 (1,00) | 157.224 (1,00) |
| Apache, 2 processi | 6.939 (0,55) | 7.035 (0,62) | 153.265 (0,97) |
| Caddy, 2 processi | 5.059 (0,40) | 3.744 (0,33) | 22.094 (0,14) |
| **omega-serv, motore nativo** | **4.738 (0,38)** | **3.115 (0,28)** | **96.277 (0,61)** |
| omega-serv, nativo + WAF † | 4.229 (0,37) | 2.926 (0,27) | 98.185 (0,62) |
| omega-serv, motore Python, 2 processi | 1.741 (0,14) | 1.154 (0,10) | 18.806 (0,12) |
| omega-serv, motore Python | 1.329 (0,11) | 611 (0,05) | 9.805 (0,06) |

### File grande (5 MB): throughput

| Server | Macchina A | Macchina B | Macchina C |
|---|---:|---:|---:|
| lighttpd, 2 processi | 2.440 MB/s (1,05) | 2.110 MB/s (0,99) | 28.011 MB/s (0,81) |
| nginx, 2 processi | 2.322 MB/s (1,00) | 2.124 MB/s (1,00) | 34.651 MB/s (1,00) |
| Apache, 2 processi | 2.355 MB/s (1,01) | 2.134 MB/s (1,00) | 41.153 MB/s (**1,19**) |
| **omega-serv, motore nativo** | **2.294 MB/s (0,99)** | **1.936 MB/s (0,91)** | **37.918 MB/s (1,09)** |
| Caddy, 2 processi | 2.205 MB/s (0,95) | 1.996 MB/s (0,94) | 3.811 MB/s (0,11) |
| omega-serv, motore Python, 2 processi | 2.145 MB/s (0,92) | 1.931 MB/s (0,91) | 25.829 MB/s (0,75) |
| omega-serv, motore Python | 1.686 MB/s (0,73) | 1.472 MB/s (0,69) | 14.227 MB/s (0,41) |

### Memoria (PSS, tutti i processi del server): a riposo → dopo il carico

omega-serv: versione 3.0.0, rimisurata il 19 novembre 2026 (i valori della 2.5 sono al §6). Altri server: campagna del 4 novembre.

| Server | Macchina A | Macchina B | Macchina C |
|---|---:|---:|---:|
| lighttpd | 1 → 1 MB | 1 → 1 MB | 1 → 1 MB |
| nginx | 4 → 5 MB | 5 → 5 MB | 4 → 4 MB |
| Apache | 4 → 7 MB | 4 → 7 MB | 4 → 7 MB |
| **omega-serv, motore nativo** | **10 → 10 MB** | **10 → 12 MB** | **12 → 16 MB** |
| omega-serv, motore Python | 20 → 23 MB | 21 → 24 MB | 22 → 28 MB |
| omega-serv, nativo + WAF | 28 → 30 MB | 29 → 32 MB | 30 → 33 MB |
| omega-serv, motore Python, 2 processi | 35 → 46 MB | 36 → 46 MB | 38 → 48 MB |
| omega-serv, nativo + WAF, 2 processi di sicurezza ‡ | 28 → 28 MB | 29 → 31 MB | 51 → 55 MB |
| Caddy, 2 processi | 50 → 57 MB | 46 → 54 MB | 48 → 62 MB |

‡ Sulle macchine A e B, il server dispone solo di 2 core: omega-serv vi avvia un solo processo di sicurezza (ne avvia 2 a partire da 4 core). Sulla macchina C, con 2 processi di sicurezza, il supervisore Python mantiene la sua forma completa, necessaria ai contatori che condividono: 51 MB invece di 30.

### A parità di core: macchina C con 4 processi

Campagna separata del 3 novembre, stesso protocollo, sulla macchina C: ogni server riceve 4 processi (o 4 core per Caddy e il motore nativo). Riferimento: nginx con 4 processi. Il motore nativo con WAF non compare più qui: misurato prima dell'ottimizzazione del WAF, non è stato ancora rimisurato con 4 processi. Memoria di omega-serv: 3.0.0, rimisurata il 19 novembre (throughput: 2.5, 3 novembre).

| Server | 1 KB | 100 KB | 5 MB | Memoria |
|---|---:|---:|---:|---:|
| lighttpd, 4 processi | 638.907 (**1,46**) | 312.402 (**1,21**) | 41.982 MB/s (0,93) | 1 → 2 MB |
| nginx, 4 processi | 438.496 (1,00) | 258.242 (1,00) | 45.162 MB/s (1,00) | 5 → 5 MB |
| **omega-serv, motore nativo** | **294.083 a 310.972 (0,67 a 0,71)** | **108.991 a 109.955 (0,42)** | **40.137 a 40.463 MB/s (0,89 a 0,90)** | **12 → 16 a 18 MB** |
| Apache, 4 processi | 200.592 (0,46) | 162.607 (0,63) | 39.664 MB/s (0,88) | 6 → 9 MB |
| Caddy, 4 core | 97.085 (0,22) | 35.900 (0,14) | 5.998 MB/s (0,13) | 52 → 67 MB |
| omega-serv, motore Python, 4 processi | 37.697 (0,09) | 35.064 (0,14) | 37.123 MB/s (0,82) | 45 → 60 MB |

### Lettura

- **Il motore nativo cambia la posizione di omega-serv.**
  - Sui file piccoli, passa da 0,03-0,11 volte nginx (motore Python) a circa **0,7 volte nginx**, qualunque sia la macchina.
  - Si colloca davanti ad Apache e Caddy, e dietro nginx e lighttpd, che restano i più veloci.
  - La sua latenza p99 è vicina a quella di nginx.
- **lighttpd è il più veloce sui file piccoli e medi**, su tutte e tre le macchine, e il più parco di memoria. La sua documentazione sconsiglia però `server.max-worker` (più processi), che abbiamo usato per confrontare a parità di processi.
- **I file medi sono il punto debole attuale del motore nativo**: da 0,28 a 0,61 volte nginx, dietro Apache, e non migliore con più core. È una pista di miglioramento individuata.
- **Sui file grandi**, i server si avvicinano, perché è il kernel a copiare i dati (`sendfile`). Caddy fa eccezione sulla macchina C: non abbiamo cercato di ottimizzare la sua configurazione di base.
- **Il WAF costa poco al motore nativo, e va letto con equilibrio.**
  - Il motore nativo cerca da sé le regole del WAF: una richiesta a cui non ne corrisponde nessuna viene servita senza passare da Python. Al minimo dubbio (corrispondenza, testo non ASCII, origine sorvegliata da Active Defense, zona di autenticazione…), decide Python. Con il WAF, il motore nativo conserva così dal 78 al 95 % del suo throughput sui file piccoli, e dal 93 al 99 % sui file da 100 KB. Prima di questa ottimizzazione, il suo throughput era diviso da 4 a 7.
  - La limitazione di frequenza è conteggiata dal motore nativo: attivarla non cambia questi dati (macchina A: 11.391 req/s con, 11.330 senza). Se magnet è attivo, tutte le richieste passano ancora da Python, e il costo torna quello di prima.
  - omega-serv con WAF resta davanti ad Apache e Caddy **senza** WAF.
  - nginx, lighttpd, Apache e Caddy sono stati misurati **senza** WAF. Un WAF aggiunto a questi server (ModSecurity, Coraza) ha anch'esso un costo, che non abbiamo misurato. Il confronto «con WAF» non è quindi fatto ad armi pari, e non pretendiamo che omega-serv sarebbe più veloce di un altro server dotato di un WAF.
- **Più processi di sicurezza non aiutano più il traffico ordinario**: non passa più da loro, e il throughput resta lo stesso con 2 processi (da −2 a −4 %, nel rumore di misura). Servono solo quando molte richieste passano da Python (magnet attivo, attacco): misurato prima dell'ottimizzazione, quando tutte le richieste ci passavano, 2 processi di sicurezza moltiplicavano il throughput con WAF da 1,5 a 1,7 volte su 4 core, ma portavano solo dal 5 al 12 % su 2 core.
- **Il motore Python cresce con i processi** (da ×1,6 a ×2 con 2 processi, circa ×3,5 con 4), ma resta al 5-11 % di nginx.
- **Memoria**: con il motore nativo senza WAF, omega-serv 3.0.0 occupa da 10 a 16 MB, da due a quattro volte nginx o Apache e da tre a sei volte meno di Caddy. Con il WAF o il motore Python, bisogna contare da 20 a 33 MB, soprattutto a causa di Python: un processo Python con asyncio costa almeno 10 MB. Con un processo, è dal 30 al 70 % in meno rispetto alla 2.5 (§6).
- **Per situare questi dati**: anche il caso più lento, il motore Python con WAF sulla macchina B (564 req/s), rappresenta quasi 50 milioni di richieste al giorno. È molto oltre le esigenze di un sito personale, di un servizio interno o di un laboratorio. La velocità è davvero decisiva solo per un sito ad alto traffico.

---

## 5. Prestazioni come reverse proxy: omega-serv a confronto con nginx, lighttpd, Apache, Caddy e Traefik

Qui i server non servono file: ognuno **inoltra** le richieste a un server applicativo (il *backend*) e ne restituisce la risposta. Misure del 14 novembre 2026, con omega-serv 3.0.0 (in preparazione), il cui motore nativo inoltra da sé il reverse proxy.

### Protocollo specifico di queste misure

- **Stesso backend per tutti**: un nginx statico con 2 processi, che serve `small.html` (1 KB) e `medium.png` (100 KB). Ogni misura verifica che la risposta provenga davvero dal backend (intestazione aggiunta da lui): il proxy inoltra, non serve mai il file da sé.
- **Core**: macchina A, il proxy su un core fisico (thread 0 e 2), il client e il backend sull'altro (1 e 3); macchina B, il proxy sui core 0 e 1, il client e il backend su 2 e 3; macchina C, il proxy sui 4 core Zen 5 (da 0 a 3), il backend su 2 core Zen 5c (4 e 5), il client sugli altri 4 (da 6 a 9).
- **Processi**: 2 sulle macchine A e B, **4 sulla macchina C**, perché ogni server usi tutti i core dati al proxy. Il motore nativo di omega-serv usa sempre tutti questi core, con un processo Python di sicurezza.
- **HTTP e HTTPS** lato client (certificato ECDSA P-256 autofirmato); il backend è sempre raggiunto in HTTP.
- **Configurazioni**:
  - nginx: `proxy_pass` verso un gruppo `upstream` che mantiene le sue connessioni verso il backend (`keepalive 64`); senza questa impostazione, assente dalla sua configurazione di base, nginx apre una connessione per richiesta;
  - lighttpd: `mod_proxy`, configurazione di base;
  - Apache: `mod_proxy` e `mod_proxy_http`, MPM `event`, una riga `ProxyPass`;
  - Caddy: `reverse_proxy`, configurazione di base;
  - Traefik 3.7: un router e un servizio, configurazione di base;
  - omega-serv: una zona di reverse proxy su `/`, profilo `standard`, motore nativo senza e poi con il WAF (tutte le regole fornite, senza limitazione di frequenza), e motore Python con 2 processi.
- **Il resto non cambia** (§3): log di accesso attivo ovunque, oha, 32 connessioni persistenti, 10 secondi, 3 giri intercalati, mediana. **Nessun errore**: tutte le risposte sono 200.

Tra parentesi: il rapporto con nginx con lo stesso numero di processi, misurato nella stessa sessione (= 1,00).

### Risposte piccole (1 KB): richieste al secondo

| Server | Macchina A (2 processi) | Macchina B (2 processi) | Macchina C (4 processi) |
|---|---:|---:|---:|
| nginx | 11.151 (1,00) | 11.049 (1,00) | 246.595 (1,00) |
| **omega-serv, motore nativo** | **9.507 (0,85)** | **10.098 (0,91)** | **203.021 (0,82)** |
| omega-serv, nativo + WAF | 9.078 (0,81) | 9.857 (0,89) | 190.201 (0,77) |
| lighttpd | 6.752 (0,61) | 6.242 (0,56) | 129.827 (0,53) |
| Apache | 6.616 (0,59) | 5.872 (0,53) | 124.458 (0,50) |
| Traefik | 3.940 (0,35) | 3.890 (0,35) | 70.465 (0,29) |
| Caddy | 3.578 (0,32) | 3.117 (0,28) | 55.910 (0,23) |
| omega-serv, motore Python | 1.039 (0,09) | 859 (0,08) | — \* |

\* Il motore Python è stato misurato solo con 2 processi sulla macchina C: 11.530 req/s, cioè 0,07 volte nginx con 2 processi (171.075 req/s).

### Risposte medie (100 KB): richieste al secondo

| Server | Macchina A | Macchina B | Macchina C |
|---|---:|---:|---:|
| **omega-serv, motore nativo** | **4.281 (1,11)** | **3.497 (0,97)** | **80.361 (1,43)** |
| omega-serv, nativo + WAF | 4.236 (1,10) | 3.335 (0,93) | 73.025 (1,30) |
| nginx | 3.855 (1,00) | 3.605 (1,00) | 56.011 (1,00) |
| lighttpd | 2.834 (0,74) | 2.252 (0,62) | 53.523 (0,96) |
| Apache | 2.404 (0,62) | 2.357 (0,65) | 39.807 (0,71) |
| Traefik | 2.477 (0,64) | 2.181 (0,60) | 39.419 (0,70) |
| Caddy | 2.294 (0,60) | 1.956 (0,54) | 33.120 (0,59) |
| omega-serv, motore Python | 821 (0,21) | 669 (0,19) | — |

### HTTPS: richieste al secondo

| Server | 1 KB: A | 1 KB: B | 1 KB: C | 100 KB: A | 100 KB: B | 100 KB: C |
|---|---:|---:|---:|---:|---:|---:|
| nginx | 9.203 (1,00) | 9.305 (1,00) | 202.095 (1,00) | 780 (1,00) | 2.338 (1,00) | 47.609 (1,00) |
| **omega-serv, motore nativo** | **6.840 (0,74)** | **7.976 (0,86)** | **130.337 (0,64) †** | **690 (0,88)** | **1.917 (0,82)** | **42.507 (0,89)** |
| omega-serv, nativo + WAF | 6.372 (0,69) | 7.456 (0,80) | 146.590 (0,73) † | 683 (0,88) | 1.882 (0,80) | 39.400 (0,83) |
| lighttpd | 5.188 (0,56) | 5.513 (0,59) | 130.572 (0,65) | 638 (0,82) | 1.381 (0,59) | 45.566 (0,96) |
| Apache | 5.038 (0,55) | 4.193 (0,45) | 114.898 (0,57) | 588 (0,75) | 1.368 (0,59) | 29.948 (0,63) |
| Traefik | 3.389 (0,37) | 3.195 (0,34) | 62.251 (0,31) | 889 (**1,14**) | 1.548 (0,66) | 28.513 (0,60) |
| Caddy | 3.263 (0,35) | 2.733 (0,29) | 54.279 (0,27) | 1.135 (**1,46**) | 1.424 (0,61) | 26.452 (0,56) |
| omega-serv, motore Python | 922 (0,10) | 759 (0,08) | — | 423 (0,54) | 549 (0,23) | — |

† Sulla macchina C, in HTTPS, il motore nativo varia molto da un giro all'altro: da 130.000 a 185.000 req/s senza WAF, da 138.000 a 150.000 con. Lo scarto tra le due righe rientra quindi nel rumore di questa misura.

### Latenza p99 sulle risposte piccole (HTTP)

| Server | Macchina A | Macchina B | Macchina C |
|---|---:|---:|---:|
| nginx | 7,7 ms | 7,8 ms | 0,4 ms |
| **omega-serv, motore nativo** | **10,5 ms** | **9,7 ms** | **0,6 ms** |
| omega-serv, nativo + WAF | 9,6 ms | 11,0 ms | 0,8 ms |
| lighttpd | 11,9 ms | 14,0 ms | 0,9 ms |
| Apache | 14,7 ms | 21,3 ms | 2,0 ms |
| Traefik | 25,9 ms | 26,5 ms | 2,1 ms |
| Caddy | 23,9 ms | 27,2 ms | 2,5 ms |
| omega-serv, motore Python | 41,0 ms | 47,6 ms | — |

### Memoria del proxy (PSS): a riposo → dopo il carico, in HTTP

omega-serv: versione 3.0.0, rimisurata il 19 novembre 2026; i throughput qui sopra risalgono al 14 novembre.

| Server | Macchina A | Macchina B | Macchina C |
|---|---:|---:|---:|
| lighttpd | 3 → 4 MB | 3 → 4 MB | 3 → 4 MB |
| nginx | 7 → 8 MB | 7 → 8 MB | 10 → 11 MB |
| Apache | 6 → 12 MB | 6 → 12 MB | 8 → 15 MB |
| **omega-serv, motore nativo** | **27 → 28 MB** | **27 → 28 MB** | **29 → 33 MB** |
| omega-serv, nativo + WAF | 29 → 30 MB | 29 → 31 MB | 31 → 36 MB |
| Caddy | 48 → 57 MB | 48 → 59 MB | 50 → 60 MB |
| omega-serv, motore Python | 42 → 50 MB | 43 → 51 MB | — |
| Traefik | 93 → 117 MB | 107 → 131 MB | 100 → 123 MB |

In HTTPS, la memoria dopo il carico aumenta da 0 a 5 MB per la maggior parte dei server, di più per Apache (fino a 66 MB sulla macchina C) e per il motore Python (fino a 72 MB): vedi i dati grezzi.

### Lettura

- **Come reverse proxy, omega-serv con il motore nativo è secondo dietro nginx**, su tutte e tre le macchine.
  - Sulle risposte piccole, inoltra da 0,82 a 0,91 volte quanto nginx. È da 1,4 a 1,7 volte lighttpd e Apache, e da 2,4 a 3,6 volte Traefik e Caddy.
  - La sua latenza p99 è la più bassa dopo quella di nginx.
- **Sulle risposte da 100 KB, è alla pari con nginx o lo supera** (da 0,97 a 1,43). Il motore nativo inoltra la risposta man mano che arriva, con un buffer limitato. Nella sua configurazione di base, nginx tiene in memoria solo qualche decina di KB per risposta inoltrata (`proxy_buffers`) e può scrivere il resto in un file temporaneo. Non abbiamo regolato questo punto.
- **In HTTPS**, il motore nativo resta secondo sulle risposte piccole delle macchine A e B. Sulla macchina C, lighttpd e lui sono allo stesso livello.
  - Sulle risposte da 100 KB, lighttpd lo supera sulla macchina C.
  - Sulla macchina A, Caddy e Traefik superano tutti, nginx compreso. Sono scritti in Go, con la propria libreria TLS, a quanto pare più efficiente su questo processore del 2010. Non lo abbiamo approfondito.
- **Il WAF costa poco come reverse proxy**: dall'1 al 9 % del throughput in HTTP, con tutte le regole attive. Gli altri server sono stati misurati senza WAF: il confronto «con WAF» non è fatto ad armi pari (vedi §4).
- **Memoria**: con il motore nativo, omega-serv 3.0.0 occupa circa 30 MB (da 27 a 36 MB). Questo totale comprende il supervisore Python, il processo di sicurezza e il motore nativo. È diverse volte nginx, lighttpd o Apache, ma meno di Caddy e da tre a quattro volte meno di Traefik. Alla misura del 14 novembre (3.0.0 in preparazione), occupava circa 50 MB.
- **Il motore Python** inoltra da 0,08 a 0,10 volte quanto nginx sulle risposte piccole: resta il motore di riserva. Le zone di reverse proxy con cache gli sono ancora affidate, e mantengono quindi il suo throughput.
- **Una correzione fatta prima di queste misure.** Un primo passaggio, lo stesso giorno e con lo stesso protocollo, collocava il motore nativo da 0,32 a 0,69 volte nginx sulle risposte piccole. Si bloccava intorno a 78.000 req/s sulla macchina C, qualunque fosse il numero di core. La sua riserva di connessioni verso il backend era troppo piccola: ne apriva una nuova ogni cinque richieste. Questa riserva è stata ampliata e l'inoltro alleggerito prima del passaggio pubblicato qui. Anche i dati del primo passaggio sono pubblicati.

### Limiti specifici di queste misure

- **nginx è regolato a suo favore**: mantiene le sue connessioni verso il backend, cosa che non fa nella sua configurazione di base. Gli altri server sono nella loro configurazione di base.
- **Il backend gira sulla stessa macchina**, in loopback. Sulle macchine A e B, condivide i suoi core con il client. Contano quindi solo i rapporti tra i server, misurati nelle stesse condizioni. Da solo, questo backend serve circa 345.000 req/s sulla macchina C: lì non limita nessuno dei proxy.
- **Solo HTTP/1.1**, sia verso il client sia verso il backend: omega-serv non parla HTTP/2.
- **Dati grezzi**: [`docs/benchmarks/`](../../benchmarks/), file `2026-11-14-*-reverse-proxy-brut.txt`, compreso il primo passaggio (`2026-11-14-reverse-proxy-avant-correctif-brut.txt`).

---

## 6. Le versioni di omega-serv: 1.0 → 2.0 → 2.5 → 3.0.0

Le tre versioni sono state misurate nella stessa sessione del §4, su tutte e tre le macchine, con lo stesso protocollo. Tra parentesi: il rapporto con nginx (2 processi) della stessa sessione. †: campagna del 4 novembre dopo l'ottimizzazione del WAF (vedi §4). La 3.0.0 è stata misurata il 19 novembre, con lo stesso protocollo; i suoi rapporti sono calcolati con nginx (2 processi) rimisurato in quella sessione, che resta entro il 3 % del suo valore del 4 novembre.

### File piccoli (1 KB): richieste al secondo

| Versione e modalità | Macchina A | Macchina B | Macchina C |
|---|---:|---:|---:|
| 1.0.0 | 1.547 (0,07) | 645 (0,03) | 8.870 (0,04) |
| 1.0.0 + WAF | 1.453 (0,07) | 561 (0,02) | 7.687 (0,03) |
| 2.0.0 | 1.740 (0,08) | 650 (0,03) | 10.245 (0,04) |
| 2.0.0 + WAF | 1.456 (0,07) | 565 (0,02) | 8.371 (0,03) |
| 2.0.0, 2 processi | 2.153 (0,10) | 1.277 (0,05) | 19.192 (0,08) |
| 2.0.0 + WAF, 2 processi | 1.775 (0,08) | 1.113 (0,05) | 15.351 (0,06) |
| 2.5, motore Python | 1.507 (0,07) | 663 (0,03) | 10.553 (0,04) |
| 2.5, motore Python + WAF | 1.561 (0,07) | 564 (0,02) | 8.365 (0,03) |
| 2.5, motore Python, 2 processi | 2.354 (0,11) | 1.312 (0,05) | 19.911 (0,08) |
| 2.5, motore Python + WAF, 2 processi | 1.901 (0,09) | 1.104 (0,04) | 15.783 (0,06) |
| **2.5, motore nativo** | **15.222 (0,70)** | **16.542 (0,67)** | **285.213 (1,15)** |
| **2.5, motore nativo + WAF †** | **11.990 (0,56)** | **12.998 (0,53)** | **264.484 (1,07)** |
| **2.5, motore nativo + WAF, 2 processi di sicurezza †** | **11.746 (0,55)** | **12.718 (0,52)** | **253.527 (1,02)** |
| 3.0.0, motore Python | 1.309 (0,06) | 752 (0,03) | 9.482 (0,04) |
| 3.0.0, motore Python + WAF | 1.168 (0,05) | 653 (0,03) | 8.788 (0,04) |
| 3.0.0, motore Python, 2 processi | 1.733 (0,08) | 1.154 (0,05) | 17.234 (0,07) |
| 3.0.0, motore Python + WAF, 2 processi | 1.605 (0,07) | 994 (0,04) | 14.873 (0,06) |
| **3.0.0, motore nativo** | **14.503 (0,68)** | **15.075 (0,63)** | **276.938 (1,15)** |
| **3.0.0, motore nativo + WAF** | **12.762 (0,60)** | **11.618 (0,48)** | **257.741 (1,07)** |
| **3.0.0, motore nativo + WAF, 2 processi di sicurezza** | **12.974 (0,61)** | **11.957 (0,50)** | **253.993 (1,06)** |

### File medi, file grande e memoria (1 processo, senza WAF)

| Versione | 100 KB, req/s (A / B / C) | 5 MB, MB/s (A / B / C) | Memoria a riposo → dopo il carico (A / B / C) |
|---|---|---|---|
| 1.0.0 | 1.071 / 563 / 7.625 | 578 / 549 / 3.640 | 21 → **98** / 22 → **98** / 23 → **73** MB |
| 2.0.0 | 1.570 / 603 / 9.469 | 1.665 / 1.470 / 14.058 | 26 → 30 / 27 → 31 / 28 → 32 MB |
| 2.5, motore Python | 1.329 / 611 / 9.805 | 1.686 / 1.472 / 14.227 | 28 → 32 / 29 → 33 / 30 → 34 MB |
| **2.5, motore nativo** | **4.738 / 3.115 / 96.277** | **2.294 / 1.936 / 37.918** | **33 → 34 / 34 → 35 / 35 → 39 MB** |
| 3.0.0, motore Python | 1.185 / 606 / 8.655 | 1.765 / 1.318 / 13.028 | 20 → 23 / 21 → 24 / 22 → 28 MB |
| **3.0.0, motore nativo** | **4.665 / 3.026 / 100.513** | **2.399 / 1.932 / 40.755** | **10 → 10 / 10 → 12 / 12 → 16 MB** |

### Grandi download simultanei

Test: 3 download simultanei di un file da 300 MB, mentre una pagina piccola viene richiesta di continuo. Due passaggi per versione e per macchina, con risultati quasi identici. La memoria qui è l'**RSS** di tutti i processi del server, come nel test originale: conta più volte la memoria condivisa, il che dà valori più alti della PSS delle altre tabelle.

| Versione | Memoria di picco | Pagina piccola, caso peggiore: A / B / C |
|---|---:|---|
| 1.0.0 | **1.833 a 1.836 MB** | **1,4 a 1,9 s** / **1,4 a 1,7 s** / 0,16 s |
| 2.0.0 | 39 a 42 MB | 3 ms / 4 a 6 ms / 1 ms |
| 2.5, motore Python | 41 a 44 MB | 2 ms / 4 ms / 1 ms |
| 2.5, motore nativo | 49 a 55 MB | 1 a 2 ms / 2 a 4 ms / meno di 1 ms |
| 3.0.0, motore Python | 39 MB | 3 ms / 5 a 8 ms / 1 ms |
| 3.0.0, motore nativo | 23 a 26 MB | 1 ms / 2 a 3 ms / meno di 1 ms |

### Costo della difesa attiva (1.0 → 2.0)

Misura del 26 ottobre 2026 sulla macchina A, non ripetuta da allora: costo di un'osservazione di minaccia da parte di Active Defense, per ogni richiesta sospetta, misurato su disco (ext4) su 2.000 osservazioni.

| Misura | 1.0.0 | 2.0.0 |
|---|---:|---:|
| Mediana | 2,84 ms | 0,23 ms |
| p99 | 11,6 ms | 2,3 ms |
| Massimo | 18 a 20 ms | 37 a 46 ms |

La mediana è divisa per 12. Il massimo è invece più alto nella 2.0: alcuni picchi isolati, legati alla scrittura periodica del journal SQLite su disco.

### Lettura

- **Dalla 1.0 alla 2.0**, il progresso riguarda la memoria e i file grandi, non la velocità delle pagine piccole:
  - la memoria dopo il carico passa da 73-98 MB a 30-32 MB;
  - durante i grandi download, passa da più di 1,8 GB a circa 40 MB, e il server resta reattivo (qualche millisecondo invece di quasi 2 secondi);
  - il throughput dei file grandi è moltiplicato da 2,7 a 3,9;
  - la 2.0 aggiunge più processi, che aumentano dal 25 % a quasi il 100 % il throughput delle pagine piccole secondo la macchina.
  La 1.0 caricava ogni file interamente in memoria prima di inviarlo. La 2.0 lo invia a blocchi, o lo affida al kernel.
- **Dalla 2.0 alla 2.5, il motore Python non cambia velocità**: gli scarti restano sotto il 4 % sulle macchine B e C, e nel rumore di misura della macchina A (da −13 % a +9 %), la più sensibile al carico di fondo. Tutto il guadagno della 2.5 viene dal **motore nativo**: circa da ×10 a ×27 sui file piccoli rispetto al motore Python, e la latenza divisa da 5 a 15.
- **Nella 2.5, il motore nativo occupava circa 5 MB in più** a riposo rispetto al motore Python (PSS): il prezzo del secondo programma. Con il WAF, ancora circa 8 MB in più: le regole caricate nel nativo.
- **Dalla 2.5 alla 3.0.0, la memoria cala dal 30 al 70 %** con un processo:
  - motore nativo: 33-35 → 10-12 MB a riposo. Quando nient'altro lo richiede, il supervisore Python si riduce a un piccolo programma di sorveglianza, che non tiene in memoria né la configurazione né il server Python;
  - motore Python: 28-30 → 20-22 MB. Il codice di un'opzione viene caricato solo se è attiva, e la libreria TLS solo se serve;
  - nativo + WAF: 43-45 → 28-30 MB. Il processo di sicurezza nasce dal supervisore ridotto e condivide le sue pagine con esso;
  - motore Python con 2 processi: 40-43 → 35-38 MB;
  - durante i grandi download: 39 MB (Python) e da 23 a 26 MB (nativo), contro 41-55 MB;
  - il motore nativo occupa ora la metà della memoria del motore Python.
- **Il lavoro sulla memoria non cambia il throughput**: un test intercalato sulle macchine B e C, con il codice 3.0.0 prima e dopo questo lavoro, dà uno scarto dall'1 al 4 %. Rispetto alla 2.5, il motore Python con 2 processi serve dal 12 al 13 % in meno sulle macchine B e C (26 % sulla macchina A, la più sensibile al carico di fondo); il codice 3.0.0 di prima di questo lavoro mostra lo stesso calo, che viene quindi da altri cambiamenti della 3.0.0 e resta da studiare. Gli altri scarti rispetto alla 2.5 vanno da −13 % a +13 %, nei due sensi.

### Cosa sapere sul motore nativo

- È **facoltativo**: il motore Python resta il motore predefinito, e quello di riserva.
- Serve da sé il contenuto statico, i reindirizzamenti, le riscritture, gli alias, la cache, le pagine di errore, le intestazioni di sicurezza e TLS.
- Cerca da sé le regole del WAF e serve da solo una richiesta a cui non ne corrisponde nessuna. Ogni altra richiesta (corrispondenza o dubbio del WAF, Active Defense, autenticazione) è decisa da Python, con esattamente gli stessi controlli e gli stessi log. Un controllo regolabile sottopone comunque a Python una richiesta pulita su N, per verificare che entrambi diano lo stesso verdetto.
- Inoltra da sé il reverse proxy, WebSocket compreso (dalla 3.0.0). L'elenco delle directory e le pagine interne sono chiesti a Python; FastCGI, l'invio di file e le zone di reverse proxy con cache gli sono affidati per tutta la connessione. Queste funzioni mantengono quindi la velocità del motore Python.
- Con TLS diretto, FastCGI, l'invio di file e le zone di reverse proxy con cache non sono gestiti dal nativo: serve allora il motore Python, e l'interfaccia lo indica.
- Richiede glibc 2.38 o più recente e OpenSSL 3. Se non si avvia, l'installazione lo ricompila sul posto, e in mancanza omega-serv resta sul motore Python.

---

## 7. Confronto delle funzioni

Legenda:
- ✅ integrato;
- 🧩 modulo ufficiale del progetto, da attivare o installare;
- 🔌 modulo o plugin di terze parti;
- ⚙️ tramite uno strumento esterno;
- ❌ assente.

«Commercial» indica una funzione riservata all'edizione a pagamento.

### Servizio HTTP

| Funzione | nginx | lighttpd | Caddy | Apache | Traefik | omega-serv 2.5 |
|---|---|---|---|---|---|---|
| Linguaggio del server | C | C | Go | C | Go | Python, con un motore nativo C++ facoltativo |
| Servire file statici | ✅ | ✅ | ✅ | ✅ | ❌ (solo proxy) | ✅ |
| ETag / 304 / Range | ✅ | ✅ | ✅ | ✅ | — | ✅ |
| File precompressi `.gz` / `.br` | ✅ `gzip_static` (`.br`: 🔌) | 🔌 script Lua (mod_magnet) | ✅ `precompressed` | 🧩 ricetta mod_rewrite | — | ✅ |
| Compressione al volo | ✅ | ✅ mod_deflate | ✅ | 🧩 mod_deflate | ✅ middleware | ❌ |
| HTTP/2 | ✅ | ✅ | ✅ | 🧩 mod_http2 | ✅ | ❌ |
| HTTP/3 (QUIC) | ✅ | ❌ | ✅ | ❌ | ✅ | ❌ |
| PHP tramite FastCGI | ✅ | ✅ | ✅ | ✅ | ❌ | ✅ |
| Più processi o core | ✅ worker | ⚠️ `max-worker`, sconsigliato dalla documentazione | ✅ (Go, tutti i core) | ✅ MPM | ✅ (Go) | ✅ `server.workers`; motore nativo: tutti i core |

### Reverse proxy

| Funzione | nginx | lighttpd | Caddy | Apache | Traefik | omega-serv 2.5 |
|---|---|---|---|---|---|---|
| Bilanciamento del carico | ✅ a rotazione, meno connessioni, hash | ✅ fair, round-robin, hash, sticky | ✅ una dozzina di strategie | 🧩 mod_proxy_balancer | ✅ wrr, p2c, hrw, least-time | ✅ 7 strategie, tra cui il carico reale |
| Salute passiva (escludere un server guasto) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Salute attiva (sonda periodica) | Commercial (NGINX Plus) | ❌ | ✅ | 🧩 mod_proxy_hcheck | ✅ | ✅ |
| Cache delle risposte | ✅ `proxy_cache` | ❌ | 🔌 | 🧩 mod_cache | Commercial | ✅ |
| WebSocket | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Scoperta dei servizi (Docker, Kubernetes) | 🔌 | ❌ | 🔌 | ❌ | ✅ (cuore del progetto) | ❌ |

### TLS

| Funzione | nginx | lighttpd | Caddy | Apache | Traefik | omega-serv 2.5 |
|---|---|---|---|---|---|---|
| Certificati automatici (ACME, Let's Encrypt) | 🧩 `ngx_http_acme_module` | ⚙️ Certbot | ✅ di default | 🧩 mod_md | ✅ | ⚙️ Certbot, con procedura guidata integrata e rinnovo programmato |
| CA locale | ❌ | ❌ | ✅ CA interna (emissione automatica) | ❌ | ❌ | ✅ generazione, firma di CSR, revoca |

### Sicurezza

| Funzione | nginx | lighttpd | Caddy | Apache | Traefik | omega-serv 2.5 |
|---|---|---|---|---|---|---|
| Limite di frequenza per client | ✅ `limit_req` | ⚠️ mod_evasive (solo connessioni simultanee) | 🔌 caddy-ratelimit | 🔌 mod_evasive, mod_qos | ✅ middleware | ✅ |
| Limite condiviso tra processi | ✅ zona di memoria condivisa | ❌ contato per processo | — (1 solo processo) | secondo il modulo | 1 istanza; più istanze con Redis | ✅ memoria condivisa |
| WAF (firme SQLi/XSS, scanner…) | 🔌 ModSecurity, Commercial (App Protect) | ❌ (script Lua da scrivere) | 🔌 Coraza | 🔌 ModSecurity | 🔌 plugin | ✅ integrato |
| Lista di blocco con scadenza, recidiva | ⚙️ fail2ban | ⚙️ fail2ban | ⚙️ fail2ban | ⚙️ fail2ban | ⚙️ | ✅ integrato |
| Esche, modalità guerra, incidenti, esportazione IoC | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ Active Defense |
| Ban graduati nel tempo | ⚙️ fail2ban | ⚙️ fail2ban | ⚙️ fail2ban | ⚙️ fail2ban | ⚙️ | ✅ RIPOSTE |
| Audit di sicurezza della configurazione | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ `audit security` |
| Modalità osservazione (registrare senza bloccare) | secondo il modulo | — | secondo il plugin | ✅ ModSecurity `DetectionOnly` | secondo il plugin | ✅ |

Ban graduati: ban sempre più lunghi per gli indirizzi che ritornano, nell'arco di settimane, in locale o a livello di rete. fail2ban li ottiene con la sua opzione `bantime.increment`; RIPOSTE aggiunge politiche misurate sui log e simulate prima dell'attivazione, la revoca di un'azione e un arresto di emergenza.

### Estensibilità

| Funzione | nginx | lighttpd | Caddy | Apache | Traefik | omega-serv 2.5 |
|---|---|---|---|---|---|---|
| Linguaggio di script | 🧩 njs (JavaScript); 🔌 Lua (OpenResty) | ✅ Lua (mod_magnet) | moduli Go (ricompilazione) | 🧩 mod_lua | plugin Go o WebAssembly | 🔌 importazione di script mod_magnet (opzione `magnet`) |
| Ecosistema di moduli | molto ampio | mirato | ampio | molto ampio | ampio | nessuno: tutto è integrato |

---

## 8. Amministrazione ed ergonomia

| Server | Modalità di amministrazione principale | Interfaccia | Ricaricamento senza interruzione |
|---|---|---|---|
| nginx | file di configurazione | nessuna (dashboard: NGINX Plus, commerciale) | ✅ `nginx -s reload` |
| lighttpd | file di configurazione | nessuna (mod_status in sola lettura) | ✅ riavvio graduale |
| Caddy | Caddyfile o JSON | API REST di amministrazione | ✅ tramite l'API |
| Apache | file di configurazione e `.htaccess` | nessuna (mod_status in sola lettura) | ✅ `graceful` |
| Traefik | etichette dei container, file o Kubernetes | dashboard web (sola lettura) | ✅ configurazione dinamica |
| omega-serv | interfaccia da terminale (TUI) e riga di comando (CLI); il file JSON non va modificato a mano | **TUI completa con tastiera e mouse, 17 lingue, guida integrata** | ✅ per la maggior parte delle impostazioni; riavvio annunciato per la porta, TLS, il motore e il numero di processi |

In concreto, con omega-serv, la configurazione, la sicurezza, i log, i servizi di sistema, i backup e le istanze si gestiscono da un'unica interfaccia. Ogni impostazione è spiegata e verificata prima di essere scritta. Con gli altri server, si modificano file di testo, poi si ricorre a strumenti separati (Certbot, fail2ban, logrotate, ModSecurity, uno strumento di monitoraggio…).

In compenso, l'approccio «file di configurazione» di nginx, Apache e Caddy si automatizza molto bene (Ansible, container, controllo di versione). omega-serv ha una CLI scriptabile, ma il suo ecosistema di automazione resta limitato.

---

## 9. Cosa porta in più omega-serv

Questa sezione considera solo ciò che nessuno dei server confrontati fornisce così com'è, senza modulo di terze parti né strumento esterno.

1. **Un'amministrazione completa in interfaccia da terminale.**
   - L'interfaccia copre tutto il server: il sito, la sicurezza, i log, i servizi, i backup e le istanze.
   - Si usa con tastiera e mouse, su un server senza display grafico, anche tramite SSH.
   - È disponibile in 17 lingue e spiega ogni impostazione.
   - Gli altri server non hanno interfaccia di amministrazione (nginx, lighttpd, Apache), o solo un'API (Caddy) o una dashboard in sola lettura (Traefik).
2. **Una sicurezza attiva integrata, senza moduli da assemblare.**
   - Il WAF comprende firme, liste di percorsi modificabili, la recidiva, una lista di blocco con scadenza, la reputazione e una modalità osservazione.
   - Active Defense aggiunge esche, una modalità guerra, il monitoraggio degli incidenti, l'esportazione di indicatori di compromissione e una simulazione a vuoto.
   - RIPOSTE risponde nel tempo: ricorda gli indirizzi che ritornano e applica loro risposte graduate, ban sempre più lunghi (1 h, 6 h, 24 h, 7 giorni di default), locali nella lista di blocco o di rete tramite fail2ban (omega-jail), oppure un'esca prolungata. Ogni politica può essere misurata sui log reali e simulata prima dell'attivazione; ogni azione resta visibile e può essere revocata, con un arresto di emergenza.
   - Altrove, queste funzioni richiedono di assemblare ModSecurity o Coraza, set di regole e fail2ban.
3. **Limiti di sicurezza esatti con più processi.**
   - Con più processi, la limitazione di frequenza e la recidiva del WAF sono condivise in memoria tra loro. Un attaccante non può quindi moltiplicare il suo limite per il numero di processi.
   - lighttpd documenta il caso opposto: con `server.max-worker`, `mod_evasive` e `mod_status` contano separatamente in ogni processo.
   - Anche nginx condivide i suoi contatori (zone `limit_req`), ma non ha un WAF integrato.
4. **Due motori, un solo comportamento.** Il motore nativo e il motore Python producono le stesse risposte e gli stessi log, verificati automaticamente su un banco di confronto. Gli strumenti che leggono i log (fail2ban, per esempio) non vedono alcuna differenza.
5. **L'importazione di script mod_magnet di lighttpd.**
   - Uno script di protezione Lua già scritto per lighttpd si importa senza riscriverlo.
   - Si aggiunge alla protezione integrata senza mai poterla indebolire, e la sua compatibilità è verificata prima dell'attivazione.
6. **La gestione di più istanze.**
   - Un registro elenca tutte le istanze, e l'interfaccia passa dall'una all'altra.
   - Sa anche disinstallare completamente un'istanza.
7. **Un audit di sicurezza della configurazione**: il comando `audit security` è informativo, non blocca mai e restituisce codici di uscita utilizzabili in uno script.
8. **Sorgenti di log remote.**
   - L'interfaccia recupera via SSH il log di un altro server, su richiesta, senza password memorizzata.
   - Può leggerlo con lnav, unendolo ai log locali.
9. **Un irrigidimento HTTP non disattivabile**, attivo dall'installazione, qualunque sia il profilo e il motore:
   - validazione rigorosa dell'intestazione Host;
   - rifiuto delle ambiguità Content-Length / Transfer-Encoding;
   - intestazioni di sicurezza e CSP sulle risposte del sito, comprese le sue pagine di errore;
   - lettura sicura di X-Forwarded-For;
   - rifiuto di avviarsi come root.

---

## 10. Cosa fanno meglio gli altri

- **Throughput**: lighttpd e nginx restano i più veloci sui file piccoli e medi, su tutte e tre le macchine. Anche con il motore nativo, omega-serv serve circa 0,7 volte nginx e 0,5 volte lighttpd sui file piccoli, e da 0,3 a 0,6 volte nginx sui file da 100 KB. Per un sito ad alto traffico, un'API pubblica o una CDN, sono loro da scegliere.
- **File medi**: Apache serve i file da 100 KB più velocemente del motore nativo di omega-serv, su tutte e tre le macchine.
- **Reverse proxy**:
  - nginx inoltra le risposte piccole dal 10 al 22 % più velocemente del motore nativo, e fino a 1,6 volte più velocemente in HTTPS sulla macchina C;
  - in HTTPS, sulle risposte da 100 KB, lighttpd lo supera sulla macchina C, e Caddy e Traefik sulla macchina A;
  - nginx, lighttpd e Apache inoltrano usando da 4 a 15 MB di memoria, omega-serv circa 30.
- **Memoria**: lighttpd (1 MB), nginx (da 4 a 5 MB) e Apache (da 4 a 9 MB) sono adatti a macchine molto limitate (embedded, piccoli container). omega-serv 3.0.0 ne richiede da 10 a 55 secondo la modalità.
- **Costo della sicurezza**: il WAF ha ancora un costo. Con il motore nativo, toglie dal 5 al 22 % del throughput sui file piccoli, limitazione di frequenza compresa: omega-serv con WAF serve da 0,53 a 0,56 volte nginx senza WAF sulle macchine A e B. Una richiesta sospetta o dubbia (corrispondenza di una regola, testo non ASCII, origine sorvegliata da Active Defense) passa sempre da Python, ed è servita alla velocità del motore Python. Con magnet attivo, tutte le richieste passano da Python, e il WAF divide allora il throughput del motore nativo da 4 a 7, come prima dell'ottimizzazione.
- **Protocolli**: HTTP/2 in tutti gli altri, HTTP/3 in nginx, Caddy e Traefik. omega-serv parla solo HTTP/1.1.
- **HTTPS automatico**: Caddy e Traefik lo integrano di default, nginx (`ngx_http_acme_module`) e Apache (`mod_md`) con un modulo ufficiale. omega-serv delega a Certbot, con una procedura guidata e un rinnovo programmato.
- **Ambienti containerizzati**: la scoperta automatica dei servizi di Traefik (Docker, Kubernetes) non ha equivalenti in omega-serv.
- **Ecosistema e maturità**: nginx e Apache offrono migliaia di moduli, guide e integrazioni, e decenni di uso in produzione. Caddy offre un sistema di moduli in Go. omega-serv è un progetto giovane, mantenuto da una sola persona, e il suo motore nativo è recente.
- **Compressione al volo**: omega-serv serve solo file già compressi.

---

## 11. Quale server per quale uso

| Esigenza | Scelta consigliata |
|---|---|
| Sito ad alto traffico, API pubblica, CDN, throughput massimo | **nginx** o **lighttpd** |
| Reverse proxy al massimo throughput, HTTP/2 o HTTP/3 verso i client | **nginx** |
| Macchina molto limitata, embedded, file statici | **lighttpd** |
| Avvio rapido con HTTPS automatico, configurazione breve | **Caddy** |
| Applicazione PHP storica, `.htaccess`, hosting condiviso | **Apache** |
| Docker, Kubernetes, microservizi | **Traefik** |
| Sito piccolo o medio, servizio interno, laboratorio, VPN, amministrazione senza modificare file | **omega-serv** (motore nativo se possibile) |
| Server esposto di cui si vuole vedere e controllare la sicurezza (WAF, ban graduati, esche) da un'unica interfaccia | **omega-serv** |
| Reverse proxy con bilanciamento, salute, cache e WAF, gestito da un'interfaccia | **omega-serv** (motore nativo: secondo dietro nginx per throughput) |
| Imparare l'irrigidimento HTTP e la difesa attiva | **omega-serv** |

Questi strumenti si combinano anche. Per esempio:
- nginx o Traefik in prima linea su Internet, con omega-serv dietro per un servizio interno, la sua sicurezza e la sua amministrazione;
- omega-serv come reverse proxy interno davanti a più server applicativi.

---

## 12. Riprodurre le misure

Gli strumenti sono forniti nel repository, in `tools/bench/`. Servono nginx, lighttpd, Apache, Caddy e oha installati (e Traefik per il reverse proxy), l'ambiente di sviluppo di omega-serv (`.venv`) e, per il motore nativo, il binario compilato in `native/omega-http-core/build-release`.

```sh
# 1. preparare una cartella di misura (file di test, configurazioni, omega-serv 1.0, 2.0 e versione corrente)
tools/bench/compare/setup.sh /percorso/misura omega-serv-1.0.0.tar.gz omega-serv-2.0.0.tar.gz

# 2. le 21 configurazioni, 3 ripetizioni intercalate (da 40 a 60 minuti)
#    SRV_CPUS / CLI_CPUS: core del server e del client (lscpu -e mostra la topologia)
SRV_CPUS=0,1 CLI_CPUS=2,3 tools/bench/compare/campaign.sh /percorso/misura > risultati.txt

# 3. mediane
python3 tools/bench/compare/summarize.py risultati.txt

# altra lista di configurazioni, per esempio 4 processi
CONFIGS="nginx-4 lighttpd-4 caddy-4 apache-4 omega-v2-1-0-native omega-v2-4-1-native" \
  tools/bench/compare/campaign.sh /percorso/misura > risultati-4.txt

# grandi download (memoria e reattività): versione corrente, motore Python poi nativo, poi 1.0
.venv/bin/python tools/bench/bigfile.py
BENCH_ENGINE=native .venv/bin/python tools/bench/bigfile.py
BENCH_SRC=/percorso/misura/v1-archive/omega-serv/src \
BENCH_EXTRA_PATH=/percorso/misura/v1-archive/omega-serv/vendor/omega-lib/src \
  .venv/bin/python tools/bench/bigfile.py

# reverse proxy (§5): backend, certificato, configurazioni dei 6 proxy, poi 3 ripetizioni intercalate
#    macchina C: SRV_CPUS=0-3 BACK_CPUS=4,5 CLI_CPUS=6-9 e CONFIGS="nginx-4 lighttpd-4 apache-4 caddy-4 traefik-4 omega-nat-1-0 omega-nat-1-1"
tools/bench/proxy/setup.sh /percorso/proxy /percorso/verso/traefik
SRV_CPUS=0,1 CLI_CPUS=2,3 tools/bench/proxy/campaign.sh /percorso/proxy > proxy.txt
python3 tools/bench/proxy/summarize.py proxy.txt

# rimisurare solo omega-serv (memoria della 3.0.0): file, grandi download e reverse proxy, nginx come riferimento
MACHINE=a SRV_CPUS=0,2 CLI_CPUS=1,3 tools/bench/memoire-3.0.0.sh /percorso/misura > memoria.txt

# misurare qualsiasi altro server già avviato, senza oha
python3 tools/bench/bench_any.py --make-files /srv/webroot-di-prova
python3 tools/bench/bench_any.py --port 8080
```

Nomi delle configurazioni: `nginx-N`, `lighttpd-N`, `apache-N`, `caddy-N` (N processi, o N core per Caddy); `omega-vX-N-W` per omega-serv (versione `v1`, `v20` o `v2` per la versione corrente, N processi, W = 0 senza WAF o 1 con), seguito da `-native` per il motore nativo.

Per il reverse proxy: `nginx-N`, `lighttpd-N`, `apache-N`, `caddy-N`, `traefik-N`, `omega-py-N-W` (motore Python) e `omega-nat-N-W` (motore nativo, N processi di sicurezza), seguiti da `-tls` per HTTPS lato client.

Per pubblicare i vostri risultati, indicate la macchina, le versioni, la ripartizione dei core e le tre ripetizioni.

---

## 13. Fonti

Funzioni degli altri server, secondo la loro documentazione ufficiale (consultata il 26 ottobre 2026).

**nginx**
- [Limitazione di frequenza `limit_req` (zona di memoria condivisa)](https://nginx.org/en/docs/http/ngx_http_limit_req_module.html)
- [File precompressi `gzip_static`](https://nginx.org/en/docs/http/ngx_http_gzip_static_module.html)
- [Modulo ACME ufficiale `ngx_http_acme_module`](https://nginx.org/en/docs/http/ngx_http_acme_module.html)
- [Bilanciamento del carico (`upstream`)](https://nginx.org/en/docs/http/ngx_http_upstream_module.html)
- [HTTP/3](https://nginx.org/en/docs/http/ngx_http_v3_module.html)
- [Connettore ModSecurity per nginx](https://github.com/owasp-modsecurity/ModSecurity-nginx)

**lighttpd**
- [`server.max-worker`: sconsigliato, contatori per processo per mod_status e mod_evasive](https://redmine.lighttpd.net/projects/lighttpd/wiki/Server_max-workerDetails)
- [mod_magnet (script Lua)](https://redmine.lighttpd.net/projects/lighttpd/wiki/Docs_ModMagnet)
- [mod_deflate (compressione, cache)](https://redmine.lighttpd.net/projects/lighttpd/wiki/Mod_deflate)
- [mod_proxy (bilanciamento, salute passiva, WebSocket)](https://redmine.lighttpd.net/projects/lighttpd/wiki/Docs_ModProxy)
- [mod_evasive (connessioni simultanee per indirizzo)](https://redmine.lighttpd.net/projects/lighttpd/wiki/Docs_ModEvasive)

**Caddy**
- [HTTPS automatico](https://caddyserver.com/docs/automatic-https)
- [`file_server` e `precompressed`](https://caddyserver.com/docs/caddyfile/directives/file_server)
- [`reverse_proxy` (strategie, salute attiva e passiva)](https://caddyserver.com/docs/caddyfile/directives/reverse_proxy)
- [API di amministrazione](https://caddyserver.com/docs/api)
- [Plugin di limitazione di frequenza caddy-ratelimit](https://github.com/mholt/caddy-ratelimit)
- [WAF Coraza per Caddy](https://github.com/corazawaf/coraza-caddy)
- [caddy-docker-proxy](https://github.com/lucaslorentz/caddy-docker-proxy)

**Apache HTTP Server**
- [MPM event](https://httpd.apache.org/docs/2.4/mod/event.html)
- [mod_md (ACME)](https://httpd.apache.org/docs/2.4/mod/mod_md.html)
- [mod_proxy_balancer](https://httpd.apache.org/docs/2.4/mod/mod_proxy_balancer.html)
- [mod_proxy_hcheck](https://httpd.apache.org/docs/2.4/mod/mod_proxy_hcheck.html)
- [mod_http2](https://httpd.apache.org/docs/2.4/mod/mod_http2.html)
- [mod_deflate, contenuto precompresso](https://httpd.apache.org/docs/2.4/mod/mod_deflate.html)
- [ModSecurity](https://github.com/owasp-modsecurity/ModSecurity)

**Traefik**
- [Middleware `ratelimit` (in memoria per istanza, Redis come opzione)](https://doc.traefik.io/traefik/reference/routing-configuration/http/middlewares/ratelimit/)
- [ACME](https://doc.traefik.io/traefik/https/acme/)
- [Providers (Docker, Kubernetes…)](https://doc.traefik.io/traefik/providers/overview/)

**fail2ban**
- [`jail.conf`: `bantime.increment`, `bantime.factor`, `bantime.multipliers`, `bantime.maxtime` (ban più lunghi per i recidivi)](https://github.com/fail2ban/fail2ban/blob/master/config/jail.conf) (consultato il 4 novembre 2026)

**Strumento di misura**
- [oha](https://github.com/hatoo/oha)

---

*Confronto realizzato da kraynux per omega-serv 2.5 e 3.0.0: misure del 3 e 4 novembre 2026 su tre macchine (reverse proxy: 14 novembre 2026; memoria di omega-serv 3.0.0: 19 novembre 2026; difesa attiva: 26 ottobre 2026). Per ogni decisione di capacità, misurate sul vostro hardware con gli strumenti forniti.*
