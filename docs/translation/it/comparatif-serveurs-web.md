<!-- Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE) -->

# omega-serv a confronto con i server web del mercato

**Confronto misurato: nginx · lighttpd · Apache · Caddy · Traefik · omega-serv 2.5**

🌐 [Français](../../comparatif-serveurs-web.md) · [English](../en/comparatif-serveurs-web.md) · [Español](../es/comparatif-serveurs-web.md) · [Português (Brasil)](../pt-BR/comparatif-serveurs-web.md) · **Italiano** · [Deutsch](../de/comparatif-serveurs-web.md) · [Nederlands](../nl/comparatif-serveurs-web.md) · [Polski](../pl/comparatif-serveurs-web.md) · [Русский](../ru/comparatif-serveurs-web.md) · [中文](../zh-CN/comparatif-serveurs-web.md) · [Tiếng Việt](../vi/comparatif-serveurs-web.md) · [ไทย](../th/comparatif-serveurs-web.md) · [Bahasa Indonesia](../id/comparatif-serveurs-web.md) · [日本語](../ja/comparatif-serveurs-web.md) · [한국어](../ko/comparatif-serveurs-web.md) · [हिन्दी](../hi/comparatif-serveurs-web.md) · [العربية](../ar/comparatif-serveurs-web.md)

Questo documento colloca omega-serv tra i server web più diffusi. Non cerca di designare un «server migliore»: ogni strumento risponde a esigenze diverse, e ognuno ha i suoi punti di forza. Fornisce tre cose:

1. **misure reali**, fatte su **tre macchine** molto diverse, con lo stesso client, gli stessi file e lo stesso protocollo, e riproducibili;
2. un **confronto delle funzioni**, ciascuna verificata nella documentazione ufficiale di ogni server (link alla fine del documento), distinguendo ciò che è integrato da ciò che richiede un modulo o un plugin;
3. ciò che omega-serv **porta davvero in più**, e ciò che gli altri fanno **meglio di lui**.

Tutte le misure di prestazione sono state fatte il 3 e il 4 novembre 2026. Nessun dato è ripreso da un altro sito o stimato. I dati grezzi sono pubblicati con questo documento.

---

## Sommario

1. [In breve](#1-in-breve)
2. [Come leggere questo confronto](#2-come-leggere-questo-confronto)
3. [Metodo di misura](#3-metodo-di-misura)
4. [Prestazioni: omega-serv a confronto con nginx, lighttpd, Apache e Caddy](#4-prestazioni-omega-serv-a-confronto-con-nginx-lighttpd-apache-e-caddy)
5. [Le versioni di omega-serv: 1.0 → 2.0 → 2.5](#5-le-versioni-di-omega-serv-10--20--25)
6. [Confronto delle funzioni](#6-confronto-delle-funzioni)
7. [Amministrazione ed ergonomia](#7-amministrazione-ed-ergonomia)
8. [Cosa porta in più omega-serv](#8-cosa-porta-in-più-omega-serv)
9. [Cosa fanno meglio gli altri](#9-cosa-fanno-meglio-gli-altri)
10. [Quale server per quale uso](#10-quale-server-per-quale-uso)
11. [Riprodurre le misure](#11-riprodurre-le-misure)
12. [Fonti](#12-fonti)

---

## 1. In breve

- **omega-serv ha due motori.** Il **motore Python** elabora tutto da sé. Il **motore nativo**, scritto in C++ e introdotto con la 2.5, serve da sé le richieste; Python mantiene la configurazione e le decisioni di sicurezza, mentre il nativo riconosce da solo le richieste a cui non corrisponde alcuna regola del WAF.
- **Con il motore nativo, senza WAF**, omega-serv serve i file piccoli a **circa 0,7 volte la velocità di nginx**, su tutte e tre le macchine. Si colloca così **davanti ad Apache e Caddy, dietro nginx e lighttpd**.
- **Con il motore Python**, omega-serv resta molto dietro a tutti gli altri: **dal 3 all'11 % della velocità di nginx**.
- **Con il WAF attivo**, omega-serv ispeziona ogni richiesta, cosa che gli altri server misurati non fanno. Con il motore nativo, serve allora **da 0,53 a 0,56 volte** la velocità di nginx (senza WAF) sulle macchine A e B, e 1,07 volte sulla macchina C (4 core contro 2): il WAF gli toglie solo dal 5 al 22 % del throughput. Resta davanti ad Apache e Caddy misurati senza WAF.
- **File medi (100 KB)**: è il punto debole attuale del motore nativo, a **da 0,3 a 0,6 volte** nginx, dietro Apache.
- **File grandi (5 MB)**: nginx, lighttpd, Apache e omega-serv nativo raggiungono lo stesso ordine di throughput. Caddy è nettamente più lento sulla macchina più veloce.
- **Memoria**: lighttpd (1 MB), nginx (da 4 a 5 MB) e Apache (da 4 a 9 MB) sono molto parchi. omega-serv occupa **da 30 a 65 MB** secondo la modalità, Caddy **da 50 a 67 MB**.
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
| omega-serv | 1.0.0 e 2.0.0 (archivi pubblicati) e 2.5, con Python 3.14 |
| Client di carico | [oha](https://github.com/hatoo/oha) 1.16.0 (scritto in Rust) |

Traefik non è stato misurato: non è un server di file (vedi §6). Compare solo nel confronto delle funzioni.

### Protocollo

- **Isolamento del processore**: server e client sono fissati su core separati (tabella qui sopra). Il client non ruba quindi tempo al server, e tutti i server dispongono esattamente delle stesse risorse.
- **Stessi file per tutti**: `small.html` (1 KB), `medium.png` (100 KB) e `large.bin` (5 MB), serviti dalla stessa cartella.
- **Log di accesso attivo ovunque**, perché un server in produzione registra.
- **HTTP/1.1 in chiaro, connessioni persistenti (keep-alive)**. La concorrenza è di 32 connessioni per i file da 1 KB e 100 KB, e di 8 per il file da 5 MB.
- **Durata**: 10 secondi per file e per configurazione.
- **Ripetizioni**: 3 giri completi, intercalati (tutte le configurazioni al giro 1, poi tutte al giro 2, ecc.). Le tabelle danno la **mediana** dei tre giri. Da un giro all'altro, lo scarto resta per lo più sotto il 5 %.
- **Memoria**: PSS di tutti i processi del server, rilevata a riposo e poi dopo il carico.
- **Configurazioni**:
  - nginx, lighttpd, Apache e Caddy nella loro configurazione di base: file statici e log di accesso;
  - omega-serv con il profilo `standard`, il WAF disattivato e poi attivato con tutte le regole fornite (senza limitazione di frequenza).
- **Numero di processi**: ogni server è misurato con 1 e poi 2 processi: nginx `worker_processes`, lighttpd `server.max-worker`, Apache `StartServers`/`ServerLimit`, Caddy `GOMAXPROCS`, omega-serv `server.workers`. Per il motore nativo di omega-serv, `server.workers` conta i processi Python di sicurezza; il motore nativo, invece, usa sempre tutti i core che gli vengono dati.
- **Nessun errore**: tutte le risposte di tutte le misure sono 200.

### Limiti da conoscere

- **Ciò che confrontiamo sono i rapporti.** I valori assoluti sarebbero diversi sul vostro hardware, o su un server dedicato.
- **Loopback (127.0.0.1)**: la misura non passa per una rete reale. Su una rete reale, il throughput dei file grandi è quasi sempre limitato dalla banda, non dal server. I throughput di diverse decine di GB/s della macchina C sono possibili solo in loopback.
- **Nessun TLS** in queste misure.
- **Macchina A**: il servizio omega-serv di produzione di questa macchina girava in background, senza ricevere traffico.
- **Macchina C**: processore ibrido (core Zen 5 e Zen 5c). Il server ha ricevuto i 4 core veloci, il client gli altri 6.
- **Configurazioni di base**: nessun server è stato ottimizzato. Un amministratore esperto otterrebbe senza dubbio di più da ciascuno, omega-serv compreso.
- **Dati grezzi**: [`docs/benchmarks/`](../../benchmarks/) (un file per macchina).

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

| Server | Macchina A | Macchina B | Macchina C |
|---|---:|---:|---:|
| lighttpd | 1 → 1 MB | 1 → 1 MB | 1 → 1 MB |
| nginx | 4 → 5 MB | 5 → 5 MB | 4 → 4 MB |
| Apache | 4 → 7 MB | 4 → 7 MB | 4 → 7 MB |
| omega-serv, motore Python | 28 → 32 MB | 29 → 33 MB | 30 → 34 MB |
| **omega-serv, motore nativo** | **33 → 34 MB** | **34 → 35 MB** | **35 → 39 MB** |
| omega-serv, nativo + WAF † | 45 → 47 MB | 43 → 44 MB | 44 → 48 MB |
| omega-serv, motore Python, 2 processi | 40 → 50 MB | 43 → 51 MB | 42 → 51 MB |
| omega-serv, nativo + WAF, 2 processi di sicurezza † | 45 → 47 MB | 43 → 44 MB | 55 → 57 MB |
| Caddy, 2 processi | 50 → 57 MB | 46 → 54 MB | 48 → 62 MB |

### A parità di core: macchina C con 4 processi

Campagna separata del 3 novembre, stesso protocollo, sulla macchina C: ogni server riceve 4 processi (o 4 core per Caddy e il motore nativo). Riferimento: nginx con 4 processi. Il motore nativo con WAF non compare più qui: misurato prima dell'ottimizzazione del WAF, non è stato ancora rimisurato con 4 processi.

| Server | 1 KB | 100 KB | 5 MB | Memoria |
|---|---:|---:|---:|---:|
| lighttpd, 4 processi | 638.907 (**1,46**) | 312.402 (**1,21**) | 41.982 MB/s (0,93) | 1 → 2 MB |
| nginx, 4 processi | 438.496 (1,00) | 258.242 (1,00) | 45.162 MB/s (1,00) | 5 → 5 MB |
| **omega-serv, motore nativo** | **294.083 a 310.972 (0,67 a 0,71)** | **108.991 a 109.955 (0,42)** | **40.137 a 40.463 MB/s (0,89 a 0,90)** | **35 → 38 MB** |
| Apache, 4 processi | 200.592 (0,46) | 162.607 (0,63) | 39.664 MB/s (0,88) | 6 → 9 MB |
| Caddy, 4 core | 97.085 (0,22) | 35.900 (0,14) | 5.998 MB/s (0,13) | 52 → 67 MB |
| omega-serv, motore Python, 4 processi | 37.697 (0,09) | 35.064 (0,14) | 37.123 MB/s (0,82) | 48 → 66 MB |

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
- **Memoria**: omega-serv occupa diverse decine di MB in più di nginx, lighttpd o Apache, soprattutto a causa di Python, e quanto Caddy. Con il motore nativo senza WAF, la memoria resta quasi stabile durante il carico.
- **Per situare questi dati**: anche il caso più lento, il motore Python con WAF sulla macchina B (564 req/s), rappresenta quasi 50 milioni di richieste al giorno. È molto oltre le esigenze di un sito personale, di un servizio interno o di un laboratorio. La velocità è davvero decisiva solo per un sito ad alto traffico.

---

## 5. Le versioni di omega-serv: 1.0 → 2.0 → 2.5

Le tre versioni sono state misurate nella stessa sessione del §4, su tutte e tre le macchine, con lo stesso protocollo. Tra parentesi: il rapporto con nginx (2 processi) della stessa sessione. †: campagna del 4 novembre dopo l'ottimizzazione del WAF (vedi §4).

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

### File medi, file grande e memoria (1 processo, senza WAF)

| Versione | 100 KB, req/s (A / B / C) | 5 MB, MB/s (A / B / C) | Memoria a riposo → dopo il carico (A / B / C) |
|---|---|---|---|
| 1.0.0 | 1.071 / 563 / 7.625 | 578 / 549 / 3.640 | 21 → **98** / 22 → **98** / 23 → **73** MB |
| 2.0.0 | 1.570 / 603 / 9.469 | 1.665 / 1.470 / 14.058 | 26 → 30 / 27 → 31 / 28 → 32 MB |
| 2.5, motore Python | 1.329 / 611 / 9.805 | 1.686 / 1.472 / 14.227 | 28 → 32 / 29 → 33 / 30 → 34 MB |
| **2.5, motore nativo** | **4.738 / 3.115 / 96.277** | **2.294 / 1.936 / 37.918** | **33 → 34 / 34 → 35 / 35 → 39 MB** |

### Grandi download simultanei

Test: 3 download simultanei di un file da 300 MB, mentre una pagina piccola viene richiesta di continuo. Due passaggi per versione e per macchina, con risultati quasi identici. La memoria qui è l'**RSS** di tutti i processi del server, come nel test originale: conta più volte la memoria condivisa, il che dà valori più alti della PSS delle altre tabelle.

| Versione | Memoria di picco | Pagina piccola, caso peggiore: A / B / C |
|---|---:|---|
| 1.0.0 | **1.833 a 1.836 MB** | **1,4 a 1,9 s** / **1,4 a 1,7 s** / 0,16 s |
| 2.0.0 | 39 a 42 MB | 3 ms / 4 a 6 ms / 1 ms |
| 2.5, motore Python | 41 a 44 MB | 2 ms / 4 ms / 1 ms |
| 2.5, motore nativo | 49 a 55 MB | 1 a 2 ms / 2 a 4 ms / meno di 1 ms |

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
- **Il motore nativo occupa circa 5 MB in più** a riposo rispetto al motore Python (PSS): è il prezzo del secondo programma. Con il WAF, occupa ancora circa 8 MB in più: le regole caricate nel nativo.

### Cosa sapere sul motore nativo

- È **facoltativo**: il motore Python resta il motore predefinito, e quello di riserva.
- Serve da sé il contenuto statico, i reindirizzamenti, le riscritture, gli alias, la cache, le pagine di errore, le intestazioni di sicurezza e TLS.
- Cerca da sé le regole del WAF e serve da solo una richiesta a cui non ne corrisponde nessuna. Ogni altra richiesta (corrispondenza o dubbio del WAF, Active Defense, autenticazione) è decisa da Python, con esattamente gli stessi controlli e gli stessi log. Un controllo regolabile sottopone comunque a Python una richiesta pulita su N, per verificare che entrambi diano lo stesso verdetto.
- L'elenco delle directory e le pagine interne sono chiesti a Python; il reverse proxy, FastCGI, l'invio di file e WebSocket gli sono affidati per tutta la connessione. Queste funzioni mantengono quindi la velocità del motore Python.
- Con TLS diretto, il reverse proxy, FastCGI e l'invio di file non sono gestiti dal nativo: serve allora il motore Python, e l'interfaccia lo indica.
- Richiede glibc 2.38 o più recente e OpenSSL 3. Se non si avvia, l'installazione lo ricompila sul posto, e in mancanza omega-serv resta sul motore Python.

---

## 6. Confronto delle funzioni

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

## 7. Amministrazione ed ergonomia

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

## 8. Cosa porta in più omega-serv

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

## 9. Cosa fanno meglio gli altri

- **Throughput**: lighttpd e nginx restano i più veloci sui file piccoli e medi, su tutte e tre le macchine. Anche con il motore nativo, omega-serv serve circa 0,7 volte nginx e 0,5 volte lighttpd sui file piccoli, e da 0,3 a 0,6 volte nginx sui file da 100 KB. Per un sito ad alto traffico, un'API pubblica o una CDN, sono loro da scegliere.
- **File medi**: Apache serve i file da 100 KB più velocemente del motore nativo di omega-serv, su tutte e tre le macchine.
- **Memoria**: lighttpd (1 MB), nginx (da 4 a 5 MB) e Apache (da 4 a 9 MB) sono adatti a macchine molto limitate (embedded, piccoli container). omega-serv ne richiede da 30 a 65.
- **Costo della sicurezza**: il WAF ha ancora un costo. Con il motore nativo, toglie dal 5 al 22 % del throughput sui file piccoli, limitazione di frequenza compresa: omega-serv con WAF serve da 0,53 a 0,56 volte nginx senza WAF sulle macchine A e B. Una richiesta sospetta o dubbia (corrispondenza di una regola, testo non ASCII, origine sorvegliata da Active Defense) passa sempre da Python, ed è servita alla velocità del motore Python. Con magnet attivo, tutte le richieste passano da Python, e il WAF divide allora il throughput del motore nativo da 4 a 7, come prima dell'ottimizzazione.
- **Protocolli**: HTTP/2 in tutti gli altri, HTTP/3 in nginx, Caddy e Traefik. omega-serv parla solo HTTP/1.1.
- **HTTPS automatico**: Caddy e Traefik lo integrano di default, nginx (`ngx_http_acme_module`) e Apache (`mod_md`) con un modulo ufficiale. omega-serv delega a Certbot, con una procedura guidata e un rinnovo programmato.
- **Ambienti containerizzati**: la scoperta automatica dei servizi di Traefik (Docker, Kubernetes) non ha equivalenti in omega-serv.
- **Ecosistema e maturità**: nginx e Apache offrono migliaia di moduli, guide e integrazioni, e decenni di uso in produzione. Caddy offre un sistema di moduli in Go. omega-serv è un progetto giovane, mantenuto da una sola persona, e il suo motore nativo è recente.
- **Compressione al volo**: omega-serv serve solo file già compressi.

---

## 10. Quale server per quale uso

| Esigenza | Scelta consigliata |
|---|---|
| Sito ad alto traffico, API pubblica, CDN, throughput massimo | **nginx** o **lighttpd** |
| Macchina molto limitata, embedded, file statici | **lighttpd** |
| Avvio rapido con HTTPS automatico, configurazione breve | **Caddy** |
| Applicazione PHP storica, `.htaccess`, hosting condiviso | **Apache** |
| Docker, Kubernetes, microservizi | **Traefik** |
| Sito piccolo o medio, servizio interno, laboratorio, VPN, amministrazione senza modificare file | **omega-serv** (motore nativo se possibile) |
| Server esposto di cui si vuole vedere e controllare la sicurezza (WAF, ban graduati, esche) da un'unica interfaccia | **omega-serv** |
| Reverse proxy interno con bilanciamento, salute e cache, gestito da un'interfaccia | **omega-serv** |
| Imparare l'irrigidimento HTTP e la difesa attiva | **omega-serv** |

Questi strumenti si combinano anche. Per esempio:
- nginx o Traefik in prima linea su Internet, con omega-serv dietro per un servizio interno, la sua sicurezza e la sua amministrazione;
- omega-serv come reverse proxy interno davanti a più server applicativi.

---

## 11. Riprodurre le misure

Gli strumenti sono forniti nel repository, in `tools/bench/`. Servono nginx, lighttpd, Apache, Caddy e oha installati, l'ambiente di sviluppo di omega-serv (`.venv`) e, per il motore nativo, il binario compilato in `native/omega-http-core/build-release`.

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

# misurare qualsiasi altro server già avviato, senza oha
python3 tools/bench/bench_any.py --make-files /srv/webroot-di-prova
python3 tools/bench/bench_any.py --port 8080
```

Nomi delle configurazioni: `nginx-N`, `lighttpd-N`, `apache-N`, `caddy-N` (N processi, o N core per Caddy); `omega-vX-N-W` per omega-serv (versione `v1`, `v20` o `v2` per la versione corrente, N processi, W = 0 senza WAF o 1 con), seguito da `-native` per il motore nativo.

Per pubblicare i vostri risultati, indicate la macchina, le versioni, la ripartizione dei core e le tre ripetizioni.

---

## 12. Fonti

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

*Confronto realizzato da kraynux per omega-serv 2.5: misure del 3 e 4 novembre 2026 su tre macchine (difesa attiva: 26 ottobre 2026). Per ogni decisione di capacità, misurate sul vostro hardware con gli strumenti forniti.*
