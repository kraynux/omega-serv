<!-- Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE) -->

# omega-serv a confronto con i server web del mercato

**Confronto misurato: nginx · lighttpd · Caddy · Apache · Traefik · omega-serv 2.0**

🌐 [Français](../../comparatif-serveurs-web.md) · [English](../en/comparatif-serveurs-web.md) · [Español](../es/comparatif-serveurs-web.md) · [Português (Brasil)](../pt-BR/comparatif-serveurs-web.md) · **Italiano** · [Deutsch](../de/comparatif-serveurs-web.md) · [Nederlands](../nl/comparatif-serveurs-web.md) · [Polski](../pl/comparatif-serveurs-web.md) · [Русский](../ru/comparatif-serveurs-web.md) · [中文](../zh-CN/comparatif-serveurs-web.md) · [Tiếng Việt](../vi/comparatif-serveurs-web.md) · [ไทย](../th/comparatif-serveurs-web.md) · [Bahasa Indonesia](../id/comparatif-serveurs-web.md) · [日本語](../ja/comparatif-serveurs-web.md) · [한국어](../ko/comparatif-serveurs-web.md) · [हिन्दी](../hi/comparatif-serveurs-web.md) · [العربية](../ar/comparatif-serveurs-web.md)

Questo documento colloca omega-serv tra i server web più diffusi. Non cerca di indicare un «server migliore»: ogni strumento risponde a esigenze diverse. Fornisce tre cose:

1. **misure reali**, fatte sulla stessa macchina, con lo stesso client e gli stessi file, e riproducibili;
2. un **confronto delle funzioni**, ciascuna verificata nella documentazione ufficiale di ogni server (link in fondo al documento), distinguendo ciò che è integrato da ciò che richiede un modulo o un plugin;
3. ciò che omega-serv **offre realmente in più**, e ciò che gli altri fanno **meglio di lui**.

Tutti i numeri che seguono sono stati misurati il 26 ottobre 2026. Nessun numero è ripreso da un altro sito né stimato.

---

## Sommario

1. [In breve](#1-in-breve)
2. [Metodo di misura](#2-metodo-di-misura)
3. [Prestazioni: omega-serv a confronto con nginx, lighttpd e Caddy](#3-prestazioni-omega-serv-a-confronto-con-nginx-lighttpd-e-caddy)
4. [omega-serv 1.0 → 2.0: cosa è cambiato, misurato](#4-omega-serv-10--20-cosa-è-cambiato-misurato)
5. [Confronto delle funzioni](#5-confronto-delle-funzioni)
6. [Amministrazione ed ergonomia](#6-amministrazione-ed-ergonomia)
7. [Cosa offre omega-serv in più](#7-cosa-offre-omega-serv-in-più)
8. [Cosa fanno meglio gli altri](#8-cosa-fanno-meglio-gli-altri)
9. [Quale server per quale uso](#9-quale-server-per-quale-uso)
10. [Riprodurre le misure](#10-riprodurre-le-misure)
11. [Fonti](#11-fonti)

---

## 1. In breve

- **Throughput grezzo sui file piccoli**: nginx e lighttpd, scritti in C, servono **da 10 a 20 volte più** richieste al secondo di omega-serv, scritto in Python. Caddy, scritto in Go, si colloca nel mezzo. È una differenza di natura, non di regolazione: omega-serv non punta a questo terreno.
- **File grandi**: dalla 2.0, omega-serv affida l'invio al kernel (`sendfile`). Raggiunge così **lo stesso ordine di throughput** di nginx, lighttpd e Caddy su questa macchina: 2,1 GB/s contro 2,0–2,4 GB/s.
- **Memoria**: lighttpd (1 MB) e nginx (4–5 MB) restano irraggiungibili. omega-serv resta sotto i 30 MB sotto carico con 1 processo, Caddy intorno ai 55 MB.
- **Dalla 1.0 alla 2.0**: throughput dei file grandi moltiplicato per 2,8; memoria durante grandi download divisa per 45; fino a +50% sui file piccoli con 2 processi (modalità boost); costo di Active Defense diviso per 12.
- **Cosa ha in più omega-serv**: un'amministrazione completa da interfaccia terminale (TUI), in 17 lingue; un WAF e una difesa attiva integrati; limiti di sicurezza che restano esatti con più processi; l'importazione di script mod_magnet di lighttpd; la gestione di più istanze.
- **Cosa non ha**: HTTP/2 e HTTP/3, la scoperta dei servizi Docker/Kubernetes, un client ACME integrato (passa da Certbot), il throughput di un server scritto in C.

---

## 2. Metodo di misura

### Macchina e software

| Elemento | Valore |
|---|---|
| Processore | Intel Core i5 M480 a 2,67 GHz (2010): 2 core fisici, 4 thread |
| Memoria | 8 GB |
| Sistema | Manjaro Linux, kernel 6.18 |
| Rete | loopback (127.0.0.1) |
| Client di carico | [oha](https://github.com/hatoo/oha) 1.16.0 (scritto in Rust) |
| nginx | 1.30.4 (pacchetto Manjaro) |
| lighttpd | 1.4.85 (pacchetto Manjaro) |
| Caddy | 2.11.4 (pacchetto Manjaro) |
| omega-serv | 1.0.0 (archivio pubblicato) e 2.0.0, con Python 3.14.7 |

Apache e Traefik non sono stati misurati, perché non installati su questa macchina. Del resto Traefik non è un server di file (vedi §5). Questi due server compaiono quindi solo nel confronto delle funzioni.

### Protocollo

- **Isolamento del processore**: ogni server è vincolato al core fisico 0 (thread 0 e 2), il client al core fisico 1 (thread 1 e 3). Così il client non ruba tempo al server, e tutti i server dispongono esattamente delle stesse risorse.
- **Gli stessi file per tutti**: `small.html` (1 KB), `medium.png` (100 KB) e `large.bin` (5 MB), serviti dalla stessa cartella.
- **Log di accesso attivo ovunque**, perché un server in produzione registra.
- **HTTP/1.1 in chiaro, connessioni persistenti (keep-alive)**. La concorrenza è di 32 connessioni per i file da 1 KB e 100 KB, e di 8 per quello da 5 MB.
- **Durata**: 10 secondi per file e per configurazione.
- **Ripetizioni**: 3 giri completi, alternati (tutti i server al giro 1, poi tutti al giro 2, ecc.). Le tabelle riportano la **mediana** dei tre giri.
- **Memoria**: PSS (*Proportional Set Size*) sommata su tutti i processi del server. A differenza dell'RSS, una pagina condivisa tra processi è contata una sola volta. Viene rilevata a riposo, poi dopo il carico.
- **Configurazioni**: nginx, lighttpd e Caddy nella loro configurazione di base (file statici, log di accesso). omega-serv usa il profilo `standard`, con il WAF disattivato, poi attivato con tutte le regole fornite.
- **Numero di processi**: ogni server è misurato con 1 e poi con 2 processi (nginx `worker_processes`, lighttpd `server.max-worker`, Caddy `GOMAXPROCS`, omega-serv `server.workers`).

### Limiti da conoscere

- **Macchina modesta e datata.** I valori assoluti sarebbero molto più alti su un server recente. Ciò che conta sono i **rapporti** tra server misurati nella stessa sessione.
- **Variabilità da una sessione all'altra**: circa il 10–30% a seconda del carico di fondo della macchina. I giri di una stessa sessione restano coerenti: meno del 5% di scarto per omega-serv e Caddy, di più per nginx e lighttpd, il cui throughput molto elevato è più sensibile al resto della macchina.
- **Loopback**: la misura non passa da una rete reale. Su una rete reale, il throughput dei file grandi è quasi sempre limitato dalla banda, non dal server.
- **Niente TLS** in queste misure. Con HTTPS, omega-serv non può usare `sendfile` e invia i file a blocchi.
- **Numeri grezzi**: sono pubblicati con questo documento in [`docs/benchmarks/2026-10-26-campagne-brute.txt`](../../benchmarks/2026-10-26-campagne-brute.txt).

---

## 3. Prestazioni: omega-serv a confronto con nginx, lighttpd e Caddy

### File piccoli (1 KB): richieste al secondo

| Server | 1 processo | 2 processi | Latenza p99 (1 proc.) |
|---|---:|---:|---:|
| lighttpd 1.4.85 | 25.521 | 29.700 | 4,5 ms |
| nginx 1.30.4 | 14.054 | 18.315 | 4,7 ms |
| Caddy 2.11.4 | 3.697 | 5.345 | 25,3 ms |
| **omega-serv 2.0** | **1.358** | **1.953** | **37,5 ms** |
| omega-serv 2.0 + WAF | 1.130 | 1.617 | 48,5 ms |
| omega-serv 1.0 | 1.304 | — | 41,2 ms |

### File medi (100 KB): richieste al secondo

| Server | 1 processo | 2 processi |
|---|---:|---:|
| lighttpd | 11.635 | 13.037 |
| nginx | 8.024 | 9.555 |
| Caddy | 3.280 | 4.344 |
| **omega-serv 2.0** | **1.247** | **1.629** |
| omega-serv 2.0 + WAF | 1.012 | 1.347 |
| omega-serv 1.0 | 1.064 | — |

### File grande (5 MB): throughput

| Server | 1 processo | 2 processi |
|---|---:|---:|
| lighttpd | 2.379 MB/s | 2.407 MB/s |
| nginx | 2.242 MB/s | 1.981 MB/s |
| Caddy | 2.165 MB/s | 2.229 MB/s |
| **omega-serv 2.0** | **1.658 MB/s** | **2.115 MB/s** |
| omega-serv 1.0 | 584 MB/s | — |

### Memoria (PSS, tutti i processi del server)

| Server | A riposo | Dopo il carico |
|---|---:|---:|
| lighttpd (1 o 2 proc.) | 1 MB | 1 MB |
| nginx (1 o 2 proc.) | 4–5 MB | 4–5 MB |
| **omega-serv 2.0 (1 proc.)** | **26 MB** | **30 MB** |
| omega-serv 2.0 (2 proc.) | 39 MB | 48 MB |
| Caddy | 50 MB | 56 MB |
| omega-serv 1.0 | 22 MB | 100 MB |

### Lettura

- **Sui file piccoli e medi**, lo scarto con nginx e lighttpd è di un ordine di grandezza (×10–×20). È il costo di un server scritto in Python: ogni richiesta attraversa l'interprete, mentre nginx e lighttpd la elaborano in C compilato. La modalità boost riduce lo scarto, senza colmarlo.
- **Sui file grandi**, i server si avvicinano, perché è il kernel a copiare i dati (`sendfile`). Con 2 processi, omega-serv 2.0 arriva a 2,1 GB/s, nella stessa fascia degli altri (2,0–2,4 GB/s).
- **Il WAF di omega-serv costa circa il 17%** sui file piccoli: ispeziona ogni richiesta. nginx, lighttpd e Caddy sono stati misurati senza WAF; un WAF aggiunto a questi server (ModSecurity, Coraza) ha anch'esso un costo, non misurato qui.
- **Per dare un'idea**: 1.300 richieste al secondo sono più di 110 milioni di richieste al giorno su questa macchina del 2010. È ben oltre le esigenze di un sito personale, di un servizio interno o di un laboratorio, che sono gli usi a cui mira omega-serv.

---

## 4. omega-serv 1.0 → 2.0: cosa è cambiato, misurato

### Prestazioni

Le due versioni sono state misurate nella stessa sessione, sulla stessa macchina e con lo stesso protocollo.

| Misura | 1.0.0 | 2.0.0 | Evoluzione |
|---|---:|---:|---:|
| File piccoli (1 KB), 1 processo | 1.304 rich/s | 1.358 rich/s | +4% |
| File piccoli (1 KB), modalità boost 2 processi | — | 1.953 rich/s | **+50%** vs 1.0 |
| File piccoli con WAF, 1 processo | 1.097 rich/s | 1.130 rich/s | +3% |
| File piccoli con WAF, 2 processi | — | 1.617 rich/s | **+47%** vs 1.0 |
| File da 100 KB, 1 processo | 1.064 rich/s | 1.247 rich/s | +17% |
| File grande (5 MB), 1 processo | 584 MB/s | 1.658 MB/s | **×2,8** |
| File grande (5 MB), 2 processi | — | 2.115 MB/s | **×3,6** vs 1.0 |
| Memoria dopo il carico, 1 processo | 100 MB | 30 MB | **÷3** |

### Grandi download simultanei

Test: 3 download simultanei di un file da 300 MB, mentre una piccola pagina viene richiesta di continuo. Due esecuzioni danno risultati identici.

| Misura | 1.0.0 | 2.0.0 |
|---|---:|---:|
| Picco di memoria del server | 1.835 MB | 40 MB |
| Piccola pagina durante i download: mediana | 3–4 ms | 2 ms |
| Piccola pagina durante i download: caso peggiore | 1,7–1,8 s | 5 ms |

La 1.0 caricava ogni file interamente in memoria prima di inviarlo. La 2.0 lo invia a blocchi, o lo affida al kernel: la memoria non dipende più dalla dimensione dei file, e il server resta reattivo durante i download.

### Costo della difesa attiva

Costo di un'osservazione di minaccia da parte di Active Defense, per ogni richiesta sospetta, misurato su disco (ext4) su 2.000 osservazioni:

| Misura | 1.0.0 | 2.0.0 |
|---|---:|---:|
| Mediana | 2,84 ms | 0,23 ms |
| p99 | 11,6 ms | 2,3 ms |
| Massimo | 18–20 ms | 37–46 ms |

La mediana è divisa per 12. Il massimo è invece più alto nella 2.0: alcuni picchi isolati, dovuti alla scrittura periodica del journal SQLite su disco.

### Funzioni arrivate con la 2.0

**Allineamento agli standard del mercato**: nginx, lighttpd, Caddy e Apache fanno già tutto questo. omega-serv li raggiunge.

- Richieste condizionali (ETag, Last-Modified, risposte 304): ricaricando una pagina si riscarica solo ciò che è cambiato.
- Richieste parziali (Range, 206/416): ripresa di un download, avanzamento in un video.
- Invio dei file con `sendfile` o a blocchi, con memoria stabile.
- File precompressi (`.gz`, `.br`) depositati accanto all'originale.
- Cache-Control predefinito per tipo di file (immagini, font, CSS/JS), regolabile.
- Più processi server (modalità boost, `server.workers`).

**Funzioni più ampie:**

- **Reverse proxy completo.** La 1.0 aveva solo un inoltro semplice (a turno, TLS verso il server a monte, WebSocket). La 2.0 aggiunge:
  - 6 strategie di ripartizione, 7 in totale;
  - affinità di sessione e instradamento per intestazione;
  - controllo di salute passivo e attivo dei server a monte;
  - una cache delle risposte;
  - protezione contro il sovraccarico e contro i loop;
  - gestione a caldo.
- **Limite di frequenza per cartella e per indirizzo o rete**, oltre al limite globale.
- **Contatori di sicurezza condivisi tra processi** (vedi §7).
- **Elenchi di percorsi sensibili** pronti all'uso, con una modalità osservazione e un editor integrato.
- **Importazione di script mod_magnet di lighttpd** (vedi §7).
- **Interfaccia in 17 lingue**, con una lingua separata per le pagine viste dai visitatori e per le esportazioni.
- **Log completamente rivisti**:
  - una libreria di log;
  - tre visualizzatori, tra cui lnav;
  - il recupero di log remoti via SSH.

---

## 5. Confronto delle funzioni

Legenda:
- ✅ integrato;
- 🧩 modulo ufficiale del progetto, da attivare o installare;
- 🔌 modulo o plugin di terze parti;
- ⚙️ tramite uno strumento esterno;
- ❌ assente.

«Commerciale» indica una funzione riservata all'edizione a pagamento.

### Servizio HTTP

| Funzione | nginx | lighttpd | Caddy | Apache | Traefik | omega-serv 2.0 |
|---|---|---|---|---|---|---|
| Servire file statici | ✅ | ✅ | ✅ | ✅ | ❌ (solo proxy) | ✅ |
| ETag / 304 / Range | ✅ | ✅ | ✅ | ✅ | — | ✅ |
| File precompressi `.gz` / `.br` | ✅ `gzip_static` (`.br`: 🔌) | 🔌 script Lua (mod_magnet) | ✅ `precompressed` | 🧩 ricetta mod_rewrite | — | ✅ |
| Compressione al volo | ✅ | ✅ mod_deflate | ✅ | 🧩 mod_deflate | ✅ middleware | ❌ |
| HTTP/2 | ✅ | ✅ | ✅ | 🧩 mod_http2 | ✅ | ❌ |
| HTTP/3 (QUIC) | ✅ | ❌ | ✅ | ❌ | ✅ | ❌ |
| PHP tramite FastCGI | ✅ | ✅ | ✅ | ✅ | ❌ | ✅ |
| Più processi o core | ✅ workers | ⚠️ `max-worker`, sconsigliato dalla documentazione | ✅ (Go, tutti i core) | ✅ MPM | ✅ (Go) | ✅ `server.workers` |

### Reverse proxy

| Funzione | nginx | lighttpd | Caddy | Apache | Traefik | omega-serv 2.0 |
|---|---|---|---|---|---|---|
| Bilanciamento del carico | ✅ a turno, meno connessioni, hash | ✅ fair, round-robin, hash, sticky | ✅ una dozzina di strategie | 🧩 mod_proxy_balancer | ✅ wrr, p2c, hrw, least-time | ✅ 7 strategie, tra cui il carico reale |
| Salute passiva (escludere un server guasto) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Salute attiva (sonda periodica) | Commerciale (NGINX Plus) | ❌ | ✅ | 🧩 mod_proxy_hcheck | ✅ | ✅ |
| Cache delle risposte | ✅ `proxy_cache` | ❌ | 🔌 | 🧩 mod_cache | Commerciale | ✅ |
| WebSocket | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Scoperta dei servizi (Docker, Kubernetes) | 🔌 | ❌ | 🔌 | ❌ | ✅ (cuore del progetto) | ❌ |

### TLS

| Funzione | nginx | lighttpd | Caddy | Apache | Traefik | omega-serv 2.0 |
|---|---|---|---|---|---|---|
| Certificati automatici (ACME, Let's Encrypt) | 🧩 `ngx_http_acme_module` | ⚙️ Certbot | ✅ predefinito | 🧩 mod_md | ✅ | ⚙️ Certbot, con procedura guidata integrata e rinnovo programmato |
| CA locale | ❌ | ❌ | ✅ CA interna (emissione automatica) | ❌ | ❌ | ✅ generazione, firma di CSR, revoca |

### Sicurezza

| Funzione | nginx | lighttpd | Caddy | Apache | Traefik | omega-serv 2.0 |
|---|---|---|---|---|---|---|
| Limite di frequenza per client | ✅ `limit_req` | ⚠️ mod_evasive (solo connessioni simultanee) | 🔌 caddy-ratelimit | 🔌 mod_evasive, mod_qos | ✅ middleware | ✅ |
| Limite condiviso tra processi | ✅ zona di memoria condivisa | ❌ contato per processo | — (un solo processo) | dipende dal modulo | 1 istanza; più istanze con Redis | ✅ memoria condivisa |
| WAF (firme SQLi/XSS, scanner…) | 🔌 ModSecurity, Commerciale (App Protect) | ❌ (script Lua da scrivere) | 🔌 Coraza | 🔌 ModSecurity | 🔌 plugin | ✅ integrato |
| Lista di blocco con scadenza, recidiva | ⚙️ fail2ban | ⚙️ fail2ban | ⚙️ fail2ban | ⚙️ fail2ban | ⚙️ | ✅ integrato |
| Esche, modalità guerra, incidenti, esportazione IoC | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ Active Defense |
| Audit di sicurezza della configurazione | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ `audit security` |
| Modalità osservazione (registrare senza bloccare) | dipende dal modulo | — | dipende dal plugin | ✅ ModSecurity `DetectionOnly` | dipende dal plugin | ✅ |

### Estendibilità

| Funzione | nginx | lighttpd | Caddy | Apache | Traefik | omega-serv 2.0 |
|---|---|---|---|---|---|---|
| Linguaggio di scripting | 🧩 njs (JavaScript); 🔌 Lua (OpenResty) | ✅ Lua (mod_magnet) | moduli Go (ricompilazione) | 🧩 mod_lua | plugin Go o WebAssembly | 🔌 importazione di script mod_magnet (opzione `magnet`) |
| Ecosistema di moduli | molto ampio | mirato | ampio | molto ampio | ampio | nessuno: tutto è integrato |

---

## 6. Amministrazione ed ergonomia

| Server | Modalità di amministrazione principale | Interfaccia | Ricarica senza interruzioni |
|---|---|---|---|
| nginx | file di configurazione | nessuna (dashboard: NGINX Plus, commerciale) | ✅ `nginx -s reload` |
| lighttpd | file di configurazione | nessuna (mod_status, sola lettura) | ✅ riavvio graduale |
| Caddy | Caddyfile o JSON | API REST di amministrazione | ✅ tramite l'API |
| Apache | file di configurazione e `.htaccess` | nessuna (mod_status, sola lettura) | ✅ `graceful` |
| Traefik | etichette dei container, file o Kubernetes | dashboard web (sola lettura) | ✅ configurazione dinamica |
| omega-serv | interfaccia terminale (TUI) e riga di comando (CLI); il file JSON non va mai modificato a mano | **TUI completa con tastiera e mouse, 17 lingue, aiuto integrato** | ✅ per la maggior parte delle impostazioni; riavvio segnalato per la porta, TLS e il numero di processi |

In pratica, con omega-serv, configurazione, sicurezza, log, servizi di sistema, backup e istanze si gestiscono da un'unica interfaccia. Ogni impostazione è spiegata e verificata prima di essere scritta. Con gli altri server, si modificano file di testo, poi si ricorre a strumenti separati (Certbot, fail2ban, logrotate, ModSecurity, uno strumento di monitoraggio…).

In compenso, l'approccio «file di configurazione» di nginx, Apache e Caddy si automatizza molto bene (Ansible, container, controllo di versione). omega-serv ha una CLI utilizzabile negli script, ma il suo ecosistema di automazione resta limitato.

---

## 7. Cosa offre omega-serv in più

Questa sezione considera solo ciò che nessuno dei server confrontati fornisce così com'è, senza modulo di terze parti né strumento esterno.

1. **Un'amministrazione completa da interfaccia terminale.**
   - L'interfaccia copre tutto il server: il sito, la sicurezza, i log, i servizi, i backup e le istanze.
   - Si usa con tastiera e mouse, su un server senza ambiente grafico, anche tramite SSH.
   - È disponibile in 17 lingue e spiega ogni impostazione.
   - Gli altri server non hanno un'interfaccia di amministrazione (nginx, lighttpd, Apache), oppure hanno solo un'API (Caddy) o una dashboard in sola lettura (Traefik).
2. **Una sicurezza attiva integrata, senza moduli da assemblare.**
   - Il WAF comprende firme, elenchi di percorsi modificabili, recidiva, una lista di blocco con scadenza, reputazione e una modalità osservazione.
   - Active Defense aggiunge esche, una modalità guerra, il monitoraggio degli incidenti, l'esportazione di indicatori di compromissione e una simulazione a vuoto.
   - Altrove, queste funzioni richiedono di assemblare ModSecurity o Coraza, set di regole e fail2ban.
3. **Limiti di sicurezza esatti con più processi.**
   - In modalità boost, il limite di frequenza e la recidiva del WAF sono condivisi in memoria tra i processi. Un attaccante non può quindi moltiplicare il proprio limite per il numero di processi.
   - lighttpd documenta il caso opposto: con `server.max-worker`, `mod_evasive` e `mod_status` contano separatamente in ogni processo.
   - Anche nginx condivide i suoi contatori (zone `limit_req`), ma non ha un WAF integrato.
4. **L'importazione di script mod_magnet di lighttpd.**
   - Uno script di protezione Lua già scritto per lighttpd si importa senza riscriverlo.
   - Si aggiunge alla protezione integrata senza mai poterla indebolire, e la sua compatibilità è verificata prima dell'attivazione.
5. **La gestione di più istanze.**
   - Un registro elenca tutte le istanze, e l'interfaccia passa dall'una all'altra.
   - Sa anche disinstallare completamente un'istanza.
6. **Un audit di sicurezza della configurazione**: il comando `audit security` è informativo, non blocca mai e restituisce codici di uscita utilizzabili in uno script.
7. **Sorgenti di log remote.**
   - L'interfaccia recupera via SSH il log di un altro server, su richiesta, senza password memorizzata.
   - Può leggerlo con lnav, unito ai log locali.
8. **Un hardening HTTP non disattivabile**, attivo fin dall'installazione, qualunque sia il profilo:
   - validazione rigorosa dell'intestazione Host;
   - rifiuto delle ambiguità Content-Length / Transfer-Encoding;
   - intestazioni di sicurezza e CSP, anche sulle pagine di errore;
   - lettura sicura di X-Forwarded-For;
   - rifiuto di avviarsi come root.

---

## 8. Cosa fanno meglio gli altri

- **Throughput e latenza**: nginx e lighttpd servono da 10 a 20 volte più richieste piccole, con una latenza da 8 a 10 volte più bassa. Per un sito ad alto traffico, un'API pubblica o una CDN, sono loro da scegliere.
- **Memoria**: lighttpd (1 MB) e nginx (4–5 MB) si adattano a macchine molto limitate (embedded, Raspberry Pi di fascia bassa, piccoli container).
- **Protocolli**: HTTP/2 in tutti gli altri, HTTP/3 in nginx, Caddy e Traefik. omega-serv parla solo HTTP/1.1.
- **HTTPS automatico**: Caddy e Traefik lo integrano di default, e nginx (`ngx_http_acme_module`) e Apache (`mod_md`) tramite un modulo ufficiale. omega-serv delega a Certbot, con una procedura guidata e un rinnovo programmato.
- **Ambienti containerizzati**: la scoperta automatica dei servizi di Traefik (Docker, Kubernetes) non ha equivalenti in omega-serv.
- **Ecosistema**: nginx e Apache offrono migliaia di moduli, guide e integrazioni. Caddy offre un sistema di moduli in Go. omega-serv è un progetto giovane, mantenuto da una sola persona.
- **Compressione al volo**: omega-serv serve solo file già compressi.

---

## 9. Quale server per quale uso

| Esigenza | Scelta consigliata |
|---|---|
| Sito ad alto traffico, API pubblica, CDN, throughput massimo | **nginx** |
| Macchina molto limitata, embedded, file statici | **lighttpd** |
| Avvio rapido con HTTPS automatico, configurazione breve | **Caddy** |
| Applicazione PHP storica, `.htaccess`, hosting condiviso | **Apache** |
| Docker, Kubernetes, microservizi | **Traefik** |
| Piccolo sito, servizio interno, laboratorio, VPN, amministrazione senza modificare file | **omega-serv** |
| Server esposto di cui si vuole vedere e controllare la sicurezza (WAF, ban, esche) da un'unica interfaccia | **omega-serv** |
| Reverse proxy interno con ripartizione, salute e cache, gestito da un'interfaccia | **omega-serv** |
| Imparare l'hardening HTTP e la difesa attiva | **omega-serv** |

Questi strumenti si possono anche combinare. Per esempio:
- nginx o Traefik in prima linea su Internet, con omega-serv dietro per un servizio interno, la sua sicurezza e la sua amministrazione;
- omega-serv come reverse proxy interno davanti a più server applicativi.

---

## 10. Riprodurre le misure

Gli strumenti sono forniti nel repository, in `tools/bench/`. Servono nginx, lighttpd, Caddy e oha installati, oltre all'ambiente di sviluppo di omega-serv (`.venv`).

```sh
# 1. preparare una cartella di misura (file di test, configurazioni, omega-serv 1.0 e 2.0)
tools/bench/compare/setup.sh /percorso/misura omega-serv-1.0.0.tar.gz

# 2. le 12 configurazioni, 3 ripetizioni alternate (circa 22 minuti)
tools/bench/compare/campaign.sh /percorso/misura > risultati.txt

# 3. mediane
python3 tools/bench/compare/summarize.py risultati.txt

# grandi download (memoria e reattività), 2.0 poi 1.0
.venv/bin/python tools/bench/bigfile.py
BENCH_SRC=/percorso/misura/v1-archive/omega-serv/src \
BENCH_EXTRA_PATH=/percorso/misura/v1-archive/omega-serv/vendor/omega-lib/src \
  .venv/bin/python tools/bench/bigfile.py

# misurare qualsiasi altro server già avviato, senza oha
python3 tools/bench/bench_any.py --make-files /srv/webroot-di-test
python3 tools/bench/bench_any.py --port 8080
```

Per impostazione predefinita, il server è vincolato ai thread 0 e 2, e il client ai thread 1 e 3, il che corrisponde alla macchina di misura. Adattate questa ripartizione al vostro processore (`lscpu -e` mostra la topologia) con le variabili `SRV_CPUS` e `CLI_CPUS`.

Per pubblicare i vostri risultati, indicate la macchina, le versioni, la ripartizione dei processori e le tre ripetizioni.

---

## 11. Fonti

Funzioni degli altri server, secondo la loro documentazione ufficiale (consultata il 26 ottobre 2026).

**nginx**
- [Limite di frequenza `limit_req` (zona di memoria condivisa)](https://nginx.org/en/docs/http/ngx_http_limit_req_module.html)
- [File precompressi `gzip_static`](https://nginx.org/en/docs/http/ngx_http_gzip_static_module.html)
- [Modulo ACME ufficiale `ngx_http_acme_module`](https://nginx.org/en/docs/http/ngx_http_acme_module.html)
- [Bilanciamento del carico (`upstream`)](https://nginx.org/en/docs/http/ngx_http_upstream_module.html)
- [HTTP/3](https://nginx.org/en/docs/http/ngx_http_v3_module.html)
- [Connettore ModSecurity per nginx](https://github.com/owasp-modsecurity/ModSecurity-nginx)

**lighttpd**
- [`server.max-worker`: sconsigliato, contatori per processo per mod_status e mod_evasive](https://redmine.lighttpd.net/projects/lighttpd/wiki/Server_max-workerDetails)
- [mod_magnet (script Lua)](https://redmine.lighttpd.net/projects/lighttpd/wiki/Docs_ModMagnet)
- [mod_deflate (compressione, cache)](https://redmine.lighttpd.net/projects/lighttpd/wiki/Mod_deflate)
- [mod_proxy (ripartizione, salute passiva, WebSocket)](https://redmine.lighttpd.net/projects/lighttpd/wiki/Docs_ModProxy)
- [mod_evasive (connessioni simultanee per indirizzo)](https://redmine.lighttpd.net/projects/lighttpd/wiki/Docs_ModEvasive)

**Caddy**
- [HTTPS automatico](https://caddyserver.com/docs/automatic-https)
- [`file_server` e `precompressed`](https://caddyserver.com/docs/caddyfile/directives/file_server)
- [`reverse_proxy` (strategie, salute attiva e passiva)](https://caddyserver.com/docs/caddyfile/directives/reverse_proxy)
- [API di amministrazione](https://caddyserver.com/docs/api)
- [Plugin di limite di frequenza caddy-ratelimit](https://github.com/mholt/caddy-ratelimit)
- [WAF Coraza per Caddy](https://github.com/corazawaf/coraza-caddy)
- [caddy-docker-proxy](https://github.com/lucaslorentz/caddy-docker-proxy)

**Apache HTTP Server**
- [mod_md (ACME)](https://httpd.apache.org/docs/2.4/mod/mod_md.html)
- [mod_proxy_balancer](https://httpd.apache.org/docs/2.4/mod/mod_proxy_balancer.html)
- [mod_proxy_hcheck](https://httpd.apache.org/docs/2.4/mod/mod_proxy_hcheck.html)
- [mod_http2](https://httpd.apache.org/docs/2.4/mod/mod_http2.html)
- [mod_deflate, contenuto precompresso](https://httpd.apache.org/docs/2.4/mod/mod_deflate.html)
- [ModSecurity](https://github.com/owasp-modsecurity/ModSecurity)

**Traefik**
- [Middleware `ratelimit` (in memoria per istanza, Redis opzionale)](https://doc.traefik.io/traefik/reference/routing-configuration/http/middlewares/ratelimit/)
- [ACME](https://doc.traefik.io/traefik/https/acme/)
- [Provider (Docker, Kubernetes…)](https://doc.traefik.io/traefik/providers/overview/)

**Strumento di misura**
- [oha](https://github.com/hatoo/oha)

---

*Confronto realizzato da kraynux per omega-serv 2.0.0: misure del 26 ottobre 2026. Le misure riguardano una sola macchina. Per qualsiasi decisione di capacità, misurate sul vostro hardware con gli strumenti forniti.*
