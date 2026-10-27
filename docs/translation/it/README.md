<!-- Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE) -->
<div align="center">
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/assets/omega-serv.png" alt="Omega-Serv" width="384">
</div>

# 🔒 OMEGA-SERV

**Server web HTTP autonomo, portatile e rafforzato di default**

> Realizzato da **kraynux** per **Omega-server** 
[kraynux.snake-mackarel](https://kraynux.snake-mackarel.ts.net)

Pagina ufficiale: [OMEGA-SERV](https://kraynux.snake-mackarel.ts.net/omega-serv/translation/it/) &nbsp; Riferimento, uso, Aiuto e FAQ: [Guida completa](https://kraynux.snake-mackarel.ts.net/omega-serv/translation/it/guide.html)  
Anteprima: [Screenshot](https://kraynux.snake-mackarel.ts.net/omega-serv/screenshots/) &nbsp; Dimostrazione [Server demo](https://craftdark.snake-mackarel.ts.net) &nbsp; [Confronto/test dei server web](comparatif-serveurs-web.md)  

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](../../../LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![Lua](https://img.shields.io/badge/Lua-5.4%2B-2C2D72.svg)](https://www.lua.org/)
[![JavaScript](https://img.shields.io/badge/JavaScript-ES2020%2B-F7DF1E.svg)](https://developer.mozilla.org/docs/Web/JavaScript)
[![Platform](https://img.shields.io/badge/Platform-Linux-informational.svg)](https://www.linux.org/)
[![Interface](https://img.shields.io/badge/Interface-CLI%20%2B%20TUI-cyan.svg)](#3-utilizzo)
[![Textual](https://img.shields.io/badge/Textual-TUI-5A5AFB.svg)](https://textual.textualize.io/)

🌐 Documentazione, esportazioni e interfaccia disponibili in **17 lingue** — vedi [Lingue dell'interfaccia](#lingue-dellinterfaccia).  
**Lingue:**
<img src="https://flagcdn.com/w20/fr.png" alt="France" style="height:14px;"> [Français](../../../README.md) · <img src="https://flagcdn.com/w20/gb.png" alt="English" style="height:14px;"> [English](../en/README.md) · <img src="https://flagcdn.com/w20/es.png" alt="Español" style="height:14px;"> [Español](../es/README.md) · <img src="https://flagcdn.com/w20/br.png" alt="Português (Brasil)" style="height:14px;"> [Português (Brasil)](../pt-BR/README.md) · <img src="https://flagcdn.com/w20/it.png" alt="Italiano" style="height:14px;"> [Italiano](README.md) · <img src="https://flagcdn.com/w20/de.png" alt="Deutsch" style="height:14px;"> [Deutsch](../de/README.md) · <img src="https://flagcdn.com/w20/nl.png" alt="Nederlands" style="height:14px;"> [Nederlands](../nl/README.md) · <img src="https://flagcdn.com/w20/pl.png" alt="Polski" style="height:14px;"> [Polski](../pl/README.md) · <img src="https://flagcdn.com/w20/ru.png" alt="Русский" style="height:14px;"> [Русский](../ru/README.md) · <img src="https://flagcdn.com/w20/cn.png" alt="中文" style="height:14px;"> [中文](../zh-CN/README.md) · <img src="https://flagcdn.com/w20/vn.png" alt="Tiếng Việt" style="height:14px;"> [Tiếng Việt](../vi/README.md) · <img src="https://flagcdn.com/w20/th.png" alt="ไทย" style="height:14px;"> [ไทย](../th/README.md) · <img src="https://flagcdn.com/w20/id.png" alt="Bahasa Indonesia" style="height:14px;"> [Bahasa Indonesia](../id/README.md) · <img src="https://flagcdn.com/w20/jp.png" alt="日本語" style="height:14px;"> [日本語](../ja/README.md) · <img src="https://flagcdn.com/w20/kr.png" alt="한국어" style="height:14px;"> [한국어](../ko/README.md) · <img src="https://flagcdn.com/w20/in.png" alt="हिन्दी" style="height:14px;"> [हिन्दी](../hi/README.md) · <img src="https://flagcdn.com/w20/ae.png" alt="العربية" style="height:14px;"> [العربية](../ar/README.md)

---

**OMEGA-SERV** è un server HTTP/1.1 scritto in Python puro (solo libreria standard per il nucleo del server), pensato per servire contenuti statici e, facoltativamente, PHP-FPM, con un irrigidimento del protocollo non disattivabile e moduli di sicurezza (WAF, TLS, autenticazione) che si sovrappongono invece di essere imposti. Settimo strumento della suite `omega-`, ma volutamente **fuori dalla futura integrazione `omega-suite`** (agisce sulla macchina locale che lo ospita, non su bersagli remoti — stessa famiglia di `omega-fire`); strutturato in Clean Architecture, con `bootstrap/` come radice di composizione.

## 1. Visione e perimetro

La priorità dichiarata è **prima di tutto la solidità/sicurezza del nucleo HTTP** — WAF e TLS sono moduli opzionali posati sopra, mai prerequisiti. Un server che fa una sola cosa (servire file, eventualmente PHP) ma la fa bene, con un vero irrigidimento del protocollo impossibile da aggirare, invece di un server che fa molte cose a metà.

### Cosa fa OMEGA-SERV

- Serve contenuti statici (file, elenco delle cartelle opzionale, alias, reindirizzamenti, riscritture, cache) con una risoluzione sicura dei percorsi (traversal, doppia codifica, link simbolici). I file grandi partono a blocchi direttamente dal disco, mai caricati in memoria; ogni file porta un `ETag` e un `Last-Modified` (ricaricamento = risposta 304 vuota) e accetta richieste parziali `Range` (ripresa di un download, video); immagini, contenuti multimediali, font, CSS e JS ricevono un `Cache-Control` predefinito, modificabile nella schermata Cache. File di testo precompressi: se `site.css.br` o `site.css.gz` esiste accanto a `site.css` (creati con `brotli -k site.css` o `gzip -k site.css`) e il browser li accetta, vengono inviati al suo posto, mai una versione più vecchia dell'originale.
- Irrigidisce il protocollo HTTP di default, senza opzione per disattivarlo: metodi consentiti espliciti, validazione dell'intestazione `Host`, rifiuto dell'ambiguità `Content-Length`/`Transfer-Encoding`, intestazioni di sicurezza e CSP di base non aggirabili.
- Facoltativamente: filtraggio WAF (firme, limitazione della frequenza, lista di blocco), TLS diretto (certificato autofirmato, firmato da una CA locale, o pubblico tramite Let's Encrypt/Certbot con rinnovo automatico — vedi §9), autenticazione HTTP Basic per zona, PHP tramite FastCGI/PHP-FPM, zone di upload confinate.
- Modalità « boost »: più processi server, al massimo uno per CPU disponibile sulla macchina (schermata Resistenza e limiti); i contatori di sicurezza (limitazione della frequenza, recidiva) sono condivisi tra loro e restano esatti.
- Verifica la propria configurazione (`audit security`) e si installa come servizio di sistema (systemd/OpenRC/runit).
- CLI non interattiva completamente scriptabile, **e interfaccia interattiva (Textual)** che riveste esattamente gli stessi casi d'uso — vedi §3. Roadmap dell'interfaccia (`OMEGA-SERV_PLAN-DETAILLE_INTERFACE.md`, §12) **interamente consegnata**: registro delle capacità, profili/opzioni, configurazione dettagliata (alias/reindirizzamenti/riscritture/FastCGI/elenco delle cartelle/autenticazione/cache/WAF/proxy attendibili/reverse proxy in uscita/TLS), gestione dei log (Libreria/Preferiti, 3 visualizzatori — semplice/classico/lnav unificato —, Vedi e gestisci IP, origini remote SSH, rotazione/backup/automazione/ripristino/eliminazione/esportazione), servizio di sistema, multi-istanza (registro, creazione), verifica/simulazione/audit, backup/ripristino della configurazione, assistente di primo avvio, impostazioni dell'applicazione (tema, profilo di rendering, percorsi di esportazione/screenshot), guida contestuale (scheda per schermata con esempi concreti, FAQ, esportazione HTML, copertura esaustiva verificata dai test), indicazione sistematica di ricaricamento/riavvio dopo ogni salvataggio, configurazione completa di Active Defense senza modifica manuale di file.

### Cosa OMEGA-SERV non fa

- CGI grezzo (rimosso dal perimetro della V1 — è supportato solo FastCGI/PHP-FPM).
- Autenticazione TLS reciproca (mTLS), OCSP stapling — fuori dal perimetro della V1, vedi §15. (ACME/Let's Encrypt tramite Certbot è disponibile, vedi §9c/9d.)
- Cache HTTP condivisa tra processi.
- Scansione/audit di un bersaglio remoto (vedi `omega-check`/`omega-scan`/`omega-deep` per questo — Omega-serv verifica solo se stesso, mai terzi).

### OMEGA-SERV a confronto con i server web del mercato

Vedi [Misure e confronto](comparatif-serveurs-web.md)  
Confronto misurato tra: [Nginx](https://nginx.org/) · [Lighttpd](https://www.lighttpd.net/) · [Caddy](https://caddyserver.com/) · [Apache](https://www.apache.org) · [Traefik](https://traefik.io/) · [Omega-Serv](https://kraynux.snake-mackarel.ts.net/omega-serv/translation/it/)

### Avvertenza d'uso

Omega-serv **si rifiuta di avviarsi come root**. Nessun modulo di sicurezza (WAF, TLS, autenticazione) è attivato di default in nessuno dei profili forniti, compreso `hardened` — attivarli è sempre un gesto esplicito (`config enable-tls`, `option enable waf`...). Il profilo `hardened` stesso raccomanda un reverse proxy per un'esposizione reale a Internet invece di sostituirlo.

## 2. Installazione

### Prerequisiti

- Python 3.10+
- `openssl` (il binario, non una libreria Python) per tutto ciò che riguarda i certificati TLS — le altre funzioni funzionano senza.

### Download

Archivio dell'ultima versione e somme SHA-256 di ogni versione: [omega-serv-2.0.0.tar.gz](https://kraynux.snake-mackarel.ts.net/omega-serv/download/omega-serv-2.0.0.tar.gz) · [sha.txt](https://kraynux.snake-mackarel.ts.net/omega-serv/download/sha.txt)

```bash
wget https://kraynux.snake-mackarel.ts.net/omega-serv/download/omega-serv-2.0.0.tar.gz
wget https://kraynux.snake-mackarel.ts.net/omega-serv/download/sha.txt
sha256sum -c --ignore-missing sha.txt
```

### Installazione

> ⚠️ **Stai aggiornando un'installazione esistente?** Il comando qui sotto **salta silenziosamente l'estrazione** se `omega-serv/` esiste già (presume che si tratti di una prima installazione interrotta, non di un aggiornamento) — reinstalleresti quindi le dipendenze sul **vecchio codice invariato**, senza il minimo messaggio di errore. Usa invece la sezione [Aggiornamento](#aggiornamento) qui sotto.

```bash
[ -d omega-serv ] && echo "ℹ️ Già estratto qui, passaggio ignorato." || tar -xzf omega-serv-2.0.0.tar.gz
cd omega-serv/
chmod +x install.sh
./install.sh
```

`install.sh`:

1. Crea l'ambiente virtuale `.venv` se non esiste ancora.
2. Installa il pacchetto (`pip install -e .`) — **nessuna dipendenza esterna** (vedi §6).
3. Rende eseguibili `omega-serv.sh` e `install.sh`.
4. Aggiunge l'alias `serv` a `~/.bashrc` e `~/.zshrc` (senza duplicati se già presente).

### Aggiornamento

Se `omega-serv/` esiste già (installazione precedente), **non lanciare mai `tar` dall'interno di quella cartella**: tenterebbe di creare un `omega-serv/omega-serv/` annidato e fallirebbe. A differenza di omega-fire, `install.sh` non tocca mai i permessi della cartella (nessun passaggio richiede `sudo`) — quindi qui non c'è rischio di una cartella appartenente a `root`, e un'estrazione direttamente sopra l'installazione esistente è sicura.

```bash
# Dalla cartella PADRE di omega-serv/ (mai dall'interno)
tar -xzf omega-serv-2.0.0.tar.gz
cd omega-serv/
./install.sh
```

L'archivio esclude deliberatamente tutto lo stato vivo (`var/db/`, `var/log/`, `var/backups/`, `secure/secrets/`, `secure/certificates/*.key`, `config/omega-serve.json`, **`webroot/` — il sito realmente servito**...) — un'estrazione sopra non tocca mai i tuoi dati, certificati, impostazioni o contenuti serviti; viene sostituito solo il codice dell'applicazione. `install.sh` riutilizza il `.venv` esistente e reinstalla semplicemente le dipendenze sopra.

Dal 2026-10-18, `var/` e `secure/auth/` non fanno più parte dell'archivio, nemmeno vuoti: un'estrazione sopra non reimposta quindi più i loro permessi (condivisi con l'account del servizio systemd) — non serve più « Servizio → Ripara i permessi » dopo un aggiornamento. `install.sh` crea queste cartelle se mancano, senza mai toccare quelle esistenti.

> ⚠️ **Se un servizio è già attivo, il passaggio precedente non basta.** Sostituisce il codice su disco, ma il processo già in esecuzione continua a girare con il vecchio codice caricato in memoria — subito dopo è sempre necessario un **riavvio completo**:
> ```bash
> sudo systemctl restart <nome-del-servizio>
> ```
> **Mai un semplice ricaricamento** (`systemctl reload`, o schermata SERVIZIO → *Ricarica*): rilegge solo alcune opzioni di configurazione (regole WAF, zone di autenticazione...), **mai il codice Python stesso**. Un `systemctl status <nome-del-servizio>` che mostra una data di avvio precedente al tuo aggiornamento conferma che sta ancora eseguendo il vecchio codice. Se aggiorni sempre sovrascrivendo la stessa cartella (caso standard sopra), questo riavvio è l'unico passaggio mancante — non serve reinstallare il servizio.

> ⚠️ **Se poi il servizio entra in un ciclo di riavvii** (`systemctl status` che alterna attivo/inattivo, `journalctl -u <nome-del-servizio>` che mostra un `PermissionError` durante la scrittura di un file sotto `var/`): l'estrazione con `tar` ripristina i permessi delle cartelle così come sono stati catturati nell'archivio, il che può cancellare la condivisione dei permessi impostata per l'account di sistema dedicato durante l'installazione iniziale — anche se `install.sh` stesso non li tocca mai. Non serve reinstallare l'unità: schermata SERVIZIO → **Ripara i permessi** (riapplica la condivisione su `var/` e `secure/auth/`, senza toccare l'unità systemd).

### Dipendenze

Il nucleo del server (parser HTTP/1.1, client FastCGI, hash delle password tramite `hashlib.scrypt`) resta in Python puro/stdlib, e tutto ciò che riguarda i certificati TLS passa dal binario `openssl` come sottoprocesso invece che da una libreria crittografica Python — **nessuna dipendenza esterna per questo**. Solo l'interfaccia interattiva (§3) ne introduce: `omega-lib` (temi, rilevamento del terminale — libreria condivisa della suite, non pubblicata su PyPI, inclusa nell'archivio distribuito), `textual` e `pyte` (emulazione di terminale per il rendering di `lnav` integrato nell'interfaccia), `jinja2` (esportazioni HTML con tema) e `psutil` (schermata Stato e risorse — CPU/RAM/disco/rete). Dipendenza opzionale di sviluppo/test (`pip install -e ".[test]"`): `hypothesis` (test basati su proprietà del parser HTTP e del risolutore di percorsi, mai in produzione). Strumenti di qualità (`pip install -e ".[dev]"`): `pytest`, `ruff`, `mypy`, `import-linter`. Extra opzionale aggiuntivo (`pip install -e ".[magnet]"`): `lupa` (binding Lua integrato, wheel precompilata, nessun interprete `lua` di sistema necessario), solo per lo script WAF complementare « magnet » (§7) — mai installato di default; la sua assenza è segnalata (capacità `waf-magnet`, schermata **Capacità**) con il comando di installazione esatto, senza bloccare il resto del server.

### Strumenti opzionali consigliati

L'interfaccia funziona in modalità ridotta se questi strumenti mancano:

- `openssl` — necessario per tutto ciò che riguarda i certificati TLS (autofirmato, CA locale, importazione); senza di esso i comandi `certs *` falliscono, ma il resto del server funziona normalmente (vedi §9).
- `certbot` — necessario solo per l'assistente **Let's Encrypt** e il suo rinnovo automatico (§9c/9d); il TLS autofirmato/CA locale non lo richiede.
- `lnav` — analisi avanzata dei log integrata nella schermata **Gestione dei log** (§3); messaggio di errore chiaro ed esplicito se l'eseguibile non viene trovato, nessun crash, il resto della schermata (vedi/segui/rotazione/statistiche) funziona normalmente senza.
- `scp` (pacchetto `openssh`/`openssh-clients`, quasi sempre già presente) — necessario solo per le **Origini remote (SSH)** (§13a); senza di esso il recupero fallisce con un messaggio chiaro, il resto della Libreria funziona normalmente.
- `python-psutil` (pacchetto di sistema equivalente al `psutil` di PyPI) — installato automaticamente da `pip install -e .` in ogni caso (dipendenza obbligatoria del pacchetto, la schermata **Stato e risorse** ne ha sempre bisogno), ma preinstallarlo con il gestore di pacchetti del sistema evita che `pip` debba compilare la sua wheel in locale.

```bash
# Arch Linux e derivate
sudo pacman -S openssl certbot lnav python-psutil openssh

# Debian/Ubuntu e derivate
sudo apt install openssl certbot lnav python3-psutil openssh-client

# Fedora
sudo dnf install openssl certbot lnav python3-psutil openssh-clients
```

## 3. Utilizzo

Due interfacce strettamente equivalenti dal punto di vista funzionale, mai logica duplicata tra le due: CLI non interattiva (scriptabile, usata qui sotto) e interfaccia interattiva Textual (menu, moduli, tabelle) — ogni azione dell'una esiste lato CLI, l'interfaccia riveste soltanto gli stessi casi d'uso.

### Modalità interattiva (TUI)

Consigliata per l'uso quotidiano — avviata senza argomenti:

```bash
./omega-serv.sh
```
se hai creato l'alias, digita semplicemente `serv` nel terminale:
```bash
serv
```

### Lingue dell'interfaccia

17 lingue: francese, inglese, spagnolo, portoghese (Brasile), italiano, tedesco, olandese, polacco, russo, cinese, vietnamita, thailandese, indonesiano, giapponese, coreano, hindi, arabo. Scelta nelle Impostazioni (tasto `o`, « Langue / Language », etichetta mai tradotta), o puntualmente con `OMEGA_SERV_LANG=it serv`. Nella console testuale di Linux (TTY), le lingue la cui scrittura non esiste nei font della console (vietnamita, cinese, thailandese, giapponese, coreano, hindi, arabo) vengono mostrate in inglese per la sessione. In hindi, i terminali che compongono da sé le lettere legate (Kitty, Ghostty, Konsole) spostano riquadri e colonne, in modo variabile secondo il font: all'avvio compare un avviso; Terminator, GNOME Terminal, Xfce Terminal e Alacritty mostrano l'hindi allineato. Due impostazioni separate: la **lingua delle pagine per i visitatori** (pagine di errore, elenco delle cartelle — schermata Pagine di errore, francese di default) e la **lingua delle esportazioni** (HTML e rapporto di incidente — Impostazioni, « Come l'interfaccia » di default). I log del server (`journalctl`) restano in francese.

### Percorso generale

Schermata iniziale (splash, si chiude con un tasto o un clic) → menu principale (Assistente di primo avvio / Registro delle capacità / Profili / Configurazione dettagliata / Sicurezza attiva / Gestione dei log / Servizio / Multi-istanza / Stato e risorse / Audit / Backup) → scelta di una sezione e poi di un'azione, ogni modulo valida i campi obbligatori prima di proseguire → conferma esplicita prima di ogni operazione sensibile o distruttiva (riavvio, eliminazione, ripristino...) → indicazione sistematica del passo successivo (ricaricamento a caldo automatico, o conferma di riavvio completo) dopo ogni salvataggio che modifica una configurazione già servita. L'adattamento al terminale (colori, dimensioni, degradazione strutturale del profilo di rendering) è automatico e senza flag manuale — vedi §4.

#### Scorciatoie da tastiera (interfaccia interattiva)

| Tasto | Azione |
|---|---|
| `↑` / `↓` | Spostarsi tra gli elementi di una schermata |
| `Tab` / `Maiusc+Tab` | Spostarsi tra i campi di un modulo |
| `Esc` | Tornare alla schermata precedente (conferma di uscita dalla home) |
| `t` | Tema successivo (applicato subito, senza conferma) |
| `r` | Aggiornare il rilevamento del terminale |
| `F1` | Aiuto della schermata attiva (scheda contestuale — vedi "Guida di aiuto" qui sotto) |
| `a` | Guida di aiuto completa (menu navigabile + FAQ) |
| `o` | Impostazioni dell'applicazione (tema, profilo di rendering, percorsi di esportazione/screenshot — vedi sotto) |
| `q` | Uscire (con conferma) |
| `Ctrl+P` | Tavolozza dei comandi (Tema, Screenshot, Opzioni...) |

> **Eccezione — editor di liste (WAF → Custom)**: nessuna scorciatoia, tutto si fa con il mouse; la tastiera serve solo per scrivere (caratteri, Invio, frecce, Home/Fine, Pag su/giù, Backspace, Canc). `Esc`, `F1` e `Ctrl+P` lì sono inattivi (pulsante **Aiuto**); resta attivo solo `Ctrl+Q`, con conferma delle modifiche non salvate.

#### Guida di aiuto (tasti `F1`/`a`)

Sistema di aiuto integrato, mai un semplice testo statico: ogni schermata documentata (scheda con definizione/campi da compilare con esempi concreti/azione eseguita/reazione — ricaricamento, riavvio o nessuna) è raggiungibile direttamente da sé con `F1`; il tasto `a` apre il menu completo (albero identico alla navigazione reale dell'applicazione) con accesso alla FAQ (trappole incontrate nell'uso reale, ad es. classi di attacco di Active Defense, permessi del servizio condiviso) e a un'esportazione HTML autonoma (tema attivo mantenuto) dell'intera guida. Ripiega su una schermata di riferimento generica finché una scheda precisa non esiste — copertura attualmente esaustiva, verificata dai test.

#### Menu principale (interfaccia interattiva)

- **Assistente di primo avvio** — percorso guidato in 8 passaggi (benvenuto → capacità in sola lettura → scelta del profilo → bind/porta → TLS opzionale → verifica → riepilogo + scrittura → proposta di installazione del servizio); permette di generare una configurazione completa e di avviare il server senza conoscere la CLI.
- **Registro delle capacità** — sonda di sistema in sola lettura (sistema di init, porta configurata già occupata o no, presenza di `openssl`/`logrotate`/`tailscale`/`lnav`, spazio su disco, limite dei descrittori...), esportazione JSON/HTML.
- **Profili** — stesso caso d'uso di `profile` nella CLI (§5), diff sempre mostrato prima della scrittura.
- **Configurazione dettagliata del server** — CRUD completo su alias/reindirizzamenti/riscritture/elenco delle cartelle/proxy attendibili/reverse proxy in uscita/FastCGI/cache/autenticazione/controllo degli accessi/pagine di errore, più il sottomenu **TLS** (stato, generazione autofirmata, assistente CA locale, assistente Let's Encrypt/Certbot, rinnovo automatico, revoca, attiva/disattiva — vedi §9); un secondo riquadro, **OPZIONI E VERIFICA**, raggruppa le scorciatoie verso **Opzioni** (`option` CLI, §7) e **Verifica la configurazione** (`config check` CLI, §10) — lo stesso percorso di regolare e poi verificare; queste due schermate non sono più raggiungibili direttamente dal menu principale. Il WAF non si trova più lì (vedi "Sicurezza attiva" qui sotto): espone soprattutto uno stato operativo che cambia di continuo, non un semplice modulo di configurazione statico. Ogni salvataggio indica sistematicamente il passo successivo: ricaricamento a caldo automatico e silenzioso se un servizio è attivo (elenco delle cartelle, accessi, alias/reindirizzamenti/riscritture, cache, pagine di errore, proxy attendibili, zone reverse proxy/FastCGI, utenti/zone di autenticazione), o conferma esplicita di riavvio completo quando la modifica riguarda il socket di ascolto, il TLS o Active Defense — nessuna schermata ti lascia più indovinare se bisogna riavviare il server.
- **Sicurezza attiva** — schermata unica che raggruppa due blocchi affiancati: **Active Defense** (Stato, Minacce monitorate con punteggio/livello, Incidenti con cronologia/esportazione IoC/rapporto, assegnazioni di Deception, Simula una decisione in dry-run, **Impostazioni** — configurazione completa senza mai modificare `config/omega-serve.json` a mano, vedi §11) e **WAF** (Stato, Moduli — modalità/pacchetti di regole/lista di blocco, Prova una richiesta, Custom — creazione di regole personalizzate e caricamento di liste di percorsi/parole chiave modificabili con il mouse (vedi §11b), Magnet — importare uno script `mod_magnet` esterno con verifica di compatibilità prima dell'attivazione) — vedi §11.
- **Gestione dei log** — menu a due colonne. Colonna **Libreria**: hub centrale che referenzia ogni log da trattare (alimentazione manuale, un clic aggiunge d'ufficio i log propri dell'istanza — access/error/WAF nativo, + script magnet §7 se attivo —, o un'**origine remota** recuperata via SSH, vedi sotto); **Preferiti** (combinazione log + visualizzatore salvata con un nome, avvio diretto); **Vedi i log** con 3 visualizzatori a scelta in base al numero di log selezionati — Semplice (tail in tempo reale + statistiche generiche IP/errori/codici HTTP su qualsiasi formato), Classico (lettura + monitoraggio), `lnav` unificato (vero rendering di terminale dentro l'interfaccia, log magnet inclusi d'ufficio + percorsi manuali **fissati** per conservarli tra le sessioni); **Vedi e gestisci IP** (top IP su uno o più log a scelta, periodo 24 h/7 g/30 g/tutto, rimozione di un IP). Colonna **Manutenzione** (invariata): rotazione/archiviazione manuale o automatica per soglia di dimensione, creazione immediata di un backup, configurazione/gestione di automazioni pianificate (dichiarative — vedi la nota qui sotto), ripristinare/eliminare un archivio, esportazione dell'elenco.
- **Servizio** — stesse azioni di `service` nella CLI (§12), elevazione `sudo` puntuale per azione, mai l'intera applicazione avviata come root.
- **Multi-istanza** — registro globale (`~/.config/omega-serv/instances.json`, fuori da ogni cartella di progetto) delle installazioni note sulla macchina, con lo stato systemd di ciascuna; creazione di una nuova istanza (copia dell'albero, ambiente virtuale e dipendenze propri, configurazione nuova con porta distinta, controllo di non annidamento e di conflitto di porta) direttamente dall'interfaccia. Pulsante praticamente invisibile per un'installazione unica (l'etichetta "Multi-istanza" diventa "Istanze (N)" non appena se ne conoscono 2); passaggio completo a un'altra istanza (`os.execv`, conferma esplicita, splash dedicato che annuncia il passaggio al riavvio); disinstallazione completa di un'istanza (rimozione dell'unità, dell'account di sistema dedicato se nessun'altra istanza lo usa più, ed eliminazione facoltativa della cartella, mai di default).
- **Stato e risorse** — panoramica a colpo d'occhio, aggiornata ogni 2 secondi: stato del server (processo/PID, stato del servizio di sistema, profilo/opzioni attive/TLS/porta), flusso del log di accesso in tempo reale (throughput, ripartizione per codice di stato, IP unici, tasso di errore), risorse di sistema (CPU/RAM/disco/swap/carico/rete, tramite `psutil`); raggruppa anche la scorciatoia **Simula una richiesta** (stesso caso d'uso del comando CLI corrispondente, §10).
- **Audit di sicurezza** — stesso caso d'uso del comando CLI corrispondente (§10).
- **Backup della configurazione** — archivio tar.gz del file di configurazione e, su opzione esplicita, delle regole WAF/zone di autenticazione/certificati (conferma obbligatoria non appena sono inclusi segreti reali)/base di Active Defense, ripristino, elenco, eliminazione.

> Nota sulle automazioni di rotazione pianificate: vengono registrate (frequenza + log di destinazione) ma **nulla le esegue automaticamente** — né l'interfaccia, né un'attività in background. È una scelta deliberata di parità con la schermata equivalente di `omega-fire`, che ha lo stesso comportamento dichiarativo. Un'esecuzione periodica reale (timer systemd, attività in background) resta da costruire separatamente, se il bisogno verrà confermato.

#### Impostazioni dell'applicazione (tasto `o` o tavolozza dei comandi)

Solo preferenze dell'interfaccia — mai da confondere con `config/omega-serve.json` (configurazione del server): tema attivo, profilo di rendering (`complete`/`standard`/`reduced`/`mono`, riavvio necessario), percorso delle esportazioni (`var/exports/` di default), percorso degli screenshot (`var/screenshots/` di default), svuotamento dell'una o dell'altra cartella (conferma obbligatoria).

```bash
# Avviare il server (primo piano, SIGTERM = arresto pulito con periodo di tolleranza, SIGHUP = ricaricamento a caldo WAF/Auth)
./omega-serv.sh serve

# Configurazione
./omega-serv.sh config init                # genera config/omega-serve.json (valori sicuri di default)
./omega-serv.sh config check                # verifica senza avviare (stesse barriere bloccanti dell'avvio)
./omega-serv.sh config show
./omega-serv.sh config enable-tls --cert ... --key ... --mode direct
./omega-serv.sh config disable-tls

# Profili (minimal / standard / hardened / development)
./omega-serv.sh profile list
./omega-serv.sh profile show hardened
./omega-serv.sh profile apply hardened --dry-run   # diff prima dell'applicazione, sempre

# Opzioni (aliases, redirects, rewrites, dirlisting, cache, waf, upload, fastcgi, reverse_proxy...)
./omega-serv.sh option list
./omega-serv.sh option enable waf
./omega-serv.sh option disable waf

# Simulare una richiesta senza avviare il server (utile per validare una regola prima di attivarla)
./omega-serv.sh simulate-request GET /index.html

# WAF (funziona anche con l'opzione disattivata, tramite --force implicito)
./omega-serv.sh waf test --method GET --path /admin --remote-ip 203.0.113.1
./omega-serv.sh blocklist list
./omega-serv.sh blocklist add --network 203.0.113.0/24 --reason "scansione rilevata" --duration-seconds 3600
./omega-serv.sh blocklist remove --network 203.0.113.0/24

# Active Defense (deception + modalità guerra, opzione "active_defense" - vedi §11)
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

# Certificati TLS - autofirmato (9a)
./omega-serv.sh certs generate-self-signed --cn localhost --san-dns localhost --san-ip 127.0.0.1
./omega-serv.sh certs show
./omega-serv.sh certs check-expiry --warn-days 30

# Certificati TLS - CA locale (9b)
./omega-serv.sh certs generate-ca --cn "La mia CA locale" --days 3650
./omega-serv.sh certs generate-csr --cn server.local --san-dns server.local --key-out server.key --csr-out server.csr
./omega-serv.sh certs sign-csr --csr server.csr --ca-key secure/certificates/ca/root-ca.key --ca-cert secure/certificates/ca/root-ca.pem --out server.pem --fullchain-out fullchain.pem
./omega-serv.sh certs revoke --cert server.pem --ca-key secure/certificates/ca/root-ca.key --ca-cert secure/certificates/ca/root-ca.pem

# Certificati TLS - importazione (9c, ad es. da un hook di Certbot)
./omega-serv.sh certs import --key privkey.pem --cert fullchain.pem

# Autenticazione HTTP Basic
./omega-serv.sh auth add-user --username alice
./omega-serv.sh auth create-zone --url-prefix /admin/ --allowed-users alice
./omega-serv.sh auth list

# Audit di sicurezza (non blocca mai, informativo)
./omega-serv.sh audit security --format text --min-severity medium

# Backup della configurazione (config sempre inclusa; segreti reali
# mai cifrati di default, --confirm-secrets obbligatorio per includerli)
./omega-serv.sh config backup --description "prima della migrazione"
./omega-serv.sh config backup --include-auth --include-certificates --confirm-secrets
./omega-serv.sh config backup --include-active-defense --description "minacce/incidenti"
./omega-serv.sh config list-backups
./omega-serv.sh config restore --snapshot-id snapshot_20260908_170003_762484

# Servizio di sistema (systemd/OpenRC/runit, rilevamento automatico)
./omega-serv.sh service install --user omega-serv --group omega-serv
./omega-serv.sh service start
./omega-serv.sh service status
```

### Codici di uscita rilevanti

| Comando | Codice | Significato |
|---|---:|---|
| `audit security` | `0` | Niente di grave (nessun `CRITICAL`/`HIGH`) |
| `audit security` | `1` | Almeno un rilievo `CRITICAL` |
| `audit security` | `2` | Almeno un `HIGH` senza `CRITICAL` |
| `audit security` | `3` | Errore di esecuzione (config non trovata...) |
| `certs check-expiry` | `1` | Certificato scaduto |
| qualsiasi altro comando | `0`/`1` | Successo / validazione fallita |

## 4. Compatibilità dei terminali

L'interfaccia interattiva ([Textual](https://textual.textualize.io/), costruita su [Rich](https://rich.readthedocs.io/)) rileva automaticamente le capacità del terminale (emulatore, dimensioni) e adatta di conseguenza il proprio foglio di stile strutturale (`complete`/`standard`/`reduced`/`mono`), senza flag manuale. La modalità CLI resta sempre in testo semplice, indipendente dal terminale. Politica condivisa da tutta la suite `omega-` (`omega-lib`, `terminal/policies.py`) — identica a quella di `omega-check`/`omega-fire`.

### Profilo in base all'emulatore rilevato

| Emulatore | Profilo iniziale |
|---|---|
| Ghostty, Alacritty, WezTerm, Kitty | `complete` |
| Konsole, GNOME Terminal, Terminator, Xfce4 Terminal | `standard` |
| xterm, urxvt, SSH moderno | `reduced` |
| TTY di Linux, SSH datato | `mono` |
| Emulatore non riconosciuto | `reduced` (ripiego di default) |

### Profilo in base alle dimensioni del terminale

| Dimensione minima (colonne × righe) | Limite del profilo |
|---|---|
| 120 × 32 | `complete` |
| 100 × 28 | `standard` |
| 80 × 24 | `reduced` |
| al di sotto | `mono` |

Il profilo finale scelto è **il più restrittivo dei due** (emulatore e dimensioni) — un Ghostty a schermo intero ridimensionato a 70 colonne scende a `mono`, anche se il suo emulatore consentirebbe `complete`. Aggiornabile in tempo reale con il tasto `r`, o forzabile manualmente dalle Impostazioni dell'applicazione (tasto `o`, §3).

## 5. Profili

| Profilo | Uso previsto |
|---|---|
| `minimal` | Dimostrazione/locale semplice: solo statico, nessuna opzione attivata |
| `standard` | Sito statico o piccola produzione: intestazioni usuali, CSP di base, dirlisting/CGI/FastCGI disattivati |
| `hardened` | Esposizione con privilegio minimo: bind locale di default (reverse proxy consigliato per Internet), metodi limitati a GET/HEAD, CSP rigorosa, anti-slowloris — il WAF **non** viene **mai** attivato automaticamente, nemmeno qui |
| `development` | Solo sviluppo locale, mai presentato come adatto a Internet: bind loopback obbligatorio, CSP in report-only, pagine di errore dettagliate |

Ordine di fusione della configurazione: valori sicuri integrati → profilo selezionato → opzioni attualmente attive conservate (sopravvivono a un cambio di profilo) → livello esplicito dell'utente. Un diff completo viene sempre mostrato prima della scrittura (`profile apply`).

## 6. Architettura

Clean Architecture (`core / domain / ports / application / infrastructure / interfaces / bootstrap`) — `bootstrap/` è la radice di composizione (equivalente dell'`app/` degli altri strumenti della suite). Particolarità assunta di questo progetto, verificata da `import-linter` invece che data per scontata: `application/server/start_server.py` (e `validate_config.py`, `run_audit.py`) svolgono il ruolo di **fabbrica di costruzione dipendente dalla configurazione reale** (quale gestore di servizi, attivare o meno il WAF...) e istanziano direttamente adattatori concreti di `infrastructure/` — a differenza dello schema più rigoroso di CHECK/TRACK, in cui `application/` consuma solo `ports/`. L'unica regola universale realmente imposta: `domain/`/`core/` non dipendono mai dagli strati esterni.

```text
src/omega_serv/
├── core/            Vocabolario trasversale (platform_info, costanti)
├── domain/           Logica di business pura (HTTP, config, sicurezza WAF/TLS/auth/audit, instradamento)
├── ports/            Contratti (Protocol) attesi dall'applicazione
├── application/      Casi d'uso - alcune funzioni (build_server...) compongono anche adattatori concreti (vedi sopra)
├── infrastructure/    Implementazioni reali (asyncio, openssl come sottoprocesso, systemd/OpenRC/runit, file)
├── interfaces/cli/    CLI argparse non interattiva
├── interfaces/tui/    Interfaccia interattiva Textual (stessi casi d'uso, mai logica duplicata)
└── bootstrap/         DependencyContainer, risoluzione della radice del progetto
```

Regole verificate da `import-linter` (8 contratti): `domain`/`core` non dipendono mai dagli strati esterni; `interfaces.tui` non dipende mai direttamente da `infrastructure`; `textual` confinato in `interfaces.tui`; `subprocess` confinato in `infrastructure/process/subprocess_runner.py` (e `infrastructure/lnav/`, flusso PTY interattivo); `ssl` confinato in `infrastructure/tls/ssl_context_builder.py`; `jinja2` confinato in `infrastructure/exporters/html_exporter.py`; `sqlite3` confinato in `infrastructure/persistence/sqlite_active_defense_connection.py` (unico archivio relazionale del progetto, riservato ad Active Defense — vedi §11); `lupa` confinato in `infrastructure/waf/lua_waf_adapter.py` (script WAF complementare « magnet », §7).

## 7. Moduli opzionali

Tutti disattivati di default in tutti i profili forniti — attivazione sempre esplicita (`option enable <nome>` o `config enable-tls`):

| Modulo | Ruolo |
|---|---|
| `waf` | Firme (percorsi sensibili, UA/Referer di scanner, SQLi/XSS/CMDi nel corpo), liste modificabili in file di testo (parole chiave, o percorsi sensibili con eccezioni `!`, modalità Osservazione e recidiva propria di ogni lista — due riferimenti forniti, caricamento esplicito, vedi §11b), limitazione della frequenza (secchio a gettoni, regole per cartella e per IP/rete, vedi §11c), lista di blocco (CIDR + scadenza), reputazione/escalation, importazione di uno script WAF `mod_magnet` di Lighttpd esistente come rinforzo opzionale di tipo « magnet » (senza riscriverlo, extra `pip install -e ".[magnet]"` — additivo, non può mai revocare un blocco nativo; verifica di compatibilità al momento dell'importazione, schermata TUI dedicata) — modalità `log-only` strutturalmente incapace di bloccare |
| TLS | Diretto (autofirmato, CA locale, o pubblico tramite Let's Encrypt/Certbot con rinnovo automatico — vedi §9), mai mTLS/OCSP nella V1 |
| Autenticazione | HTTP Basic per zona (`url_prefix`), `hashlib.scrypt` con difesa anti-timing (tempo costante anche per un utente sconosciuto) |
| FastCGI/PHP-FPM | Un solo `(url_prefix, script_root)`, `script_root` confinato fuori da `webroot/` per costruzione (il gestore statico non può mai divulgare sorgenti PHP) |
| Reverse proxy in uscita | Omega-serv agisce esso stesso da proxy verso uno o più backend (direzione opposta a `server.tls.mode = "behind_proxy"`) — bilanciamento del carico (round-robin, ponderato, least-connections, ip-hash, least-response-time, carico reale), affinità di sessione e regole di instradamento per intestazione, salute passiva e attiva, cache delle risposte (multivariante `Vary`), backpressure, protezione anti-loop, API di amministrazione a caldo — vedi §7a per il dettaglio completo |
| Upload | Zone confinate, quote per zona, nomi di file generati lato server — niente streaming nella V1 (limitato da `server.max_request_size`) |
| `active_defense` | Deception + modalità guerra a partire dai segnali WAF già calcolati (mai un secondo punteggio): esche statiche, rallentamento/registrazione arricchita/limitazione della frequenza mirati, incidenti + esportazione IoC — vedi §11 |

### 7a. Reverse proxy in uscita — dettaglio

OMEGA-SERV può agire esso stesso da reverse proxy verso uno o più backend HTTP/HTTPS — da non confondere mai con `server.tls.mode = "behind_proxy"` (OMEGA-SERV **dietro** un proxy, meccanismo inverso). Zone configurabili con CRUD completo (TUI: *Configurazione dettagliata → Reverse Proxy*), uno o più upstream per zona.

- **Bilanciamento del carico** — `round_robin` (default), `weighted_round_robin`/`weighted_least_connections`/`ip_hash` (ponderati), `least_connections`, `least_response_time`, `real_load` (carico reale). Modalità `real_load` nativa (sonda `/.omega-serv-load/`, riutilizza la stessa lettura `psutil` della schermata « Stato e risorse », mai una seconda chiamata) o dichiarativa (sonda HTTP di terze parti, formato minimo `{"load_percent": ...}` o numero semplice) — granularità per upstream, una stessa zona può mescolare i due.
- **Affinità di sessione e instradamento condizionale** — cookie sticky opaco (mai l'host:porta reale esposto al client) e regole per intestazione (uguaglianza o prefisso), entrambe filtrate dall'idoneità dell'upstream di destinazione (ricadono in modo pulito sulla strategia attiva se l'upstream scelto non è disponibile).
- **Salute** — passiva (errori/successi consecutivi, soglie di passaggio down/up distinte per limitare il flapping) **e** attiva (sonda periodica indipendente dal traffico reale, facoltativa per upstream, riutilizza lo stesso meccanismo di attività in background del carico reale). Stati `DOWN` (sempre automatico), `DRAINING`/`MAINTENANCE` (sempre manuali, esplicitamente effimeri, mai persistiti) — un upstream attivato manualmente resta escluso dalle nuove scelte senza mai interrompere una connessione già stabilita. Nuovo tentativo automatico su un altro upstream, solo per i metodi idempotenti (GET/HEAD/OPTIONS) e solo in caso di errore di connessione.
- **Backpressure** — limite di connessioni attive configurabile per upstream; un upstream saturo rifiuta in modo pulito con 503, distinto da un upstream guasto (502, ritentato comunque).
- **Cache delle risposte** — solo GET/HEAD, mai una risposta di errore, mai `Set-Cookie` salvo opt-in esplicito per zona; rispetta `Cache-Control`/`Vary` dell'upstream (opzione disattivabile ma pericolosa, stessa filosofia della verifica TLS). Più varianti di una stessa risorsa (`Vary`) coesistono davvero su disco, mai un semplice « vince l'ultimo arrivato ». Blocco anti-stampede (una sola richiesta concorrente ricostruisce davvero la cache). Intestazione di diagnostica `X-Omega-Cache: HIT`/`MISS`/`BYPASS` su ogni risposta. Supervisione/svuotamento in una schermata TUI dedicata (*Cache del reverse proxy*).
- **Protezione anti-loop** — intestazioni hop-by-hop rimosse, `X-Forwarded-*` sempre sovrascritte (mai unite a quelle del client), contatore `X-Omega-Proxy-Hops` incrementato a ogni inoltro (rifiuto pulito oltre 5 salti — rileva un loop indiretto tra due istanze, che una semplice validazione della configurazione locale non può mai vedere).
- **WebSocket** — upgrade consentito per zona, un solo upstream fissato per tutta la durata del tunnel una volta stabilito, senza timeout applicativo.
- **Amministrazione a caldo** — piccola API HTTP locale (`/.omega-serv-admin/`, protetta da `trusted_proxy` come la sonda di carico nativa) che permette alla TUI di leggere/forzare lo stato DRAINING/MAINTENANCE di un backend e di leggere il rapporto hits/miss della cache **del server realmente in esecuzione** (schermata dedicata *Stato in tempo reale dei backend*) — poiché TUI e server restano due processi separati senza memoria condivisa, questo canale HTTP locale è l'unico ponte tra i due.

## 8. Irrigidimento HTTP (non disattivabile)

- Intestazione/riga di richiesta limitate **durante** la lettura (mai a posteriori), ripiegamento di intestazioni obsoleto rifiutato, `Transfer-Encoding` sempre rifiutato (mai indovinato).
- `Content-Length` duplicato rifiutato; `Expect: 100-continue` rifiutato in modo pulito (417).
- Lista bianca esplicita dei metodi (405 + `Allow` altrimenti), intestazione `Host` validata (mancante/vuota/duplicata-anche-se-identica/carattere di controllo → 400).
- Intestazioni di sicurezza e CSP di base (`enforce`/`report-only`) applicate a **ogni** risposta, errori compresi — non aggirabili tramite un'opzione. `Cross-Origin-Opener-Policy`/`Cross-Origin-Resource-Policy` sempre `same-origin`, senza rischio reale di rompere un sito. `Cross-Origin-Embedder-Policy` sempre emessa esplicitamente (mai assente — uno scanner esterno distingue « non considerata » da « permissiva per scelta »), default `unsafe-none` su **tutti** i profili compreso `hardened`: a differenza delle due precedenti, `require-corp`/`credentialless` possono bloccare risorse cross-origin (font, immagini, iframe di terze parti) proprie del sito realmente servito — regolabile (`security.coep_mode`). Zone CSP (`security.csp_zones`): eccezioni **esplicite** per prefisso di percorso (ad es. `unsafe-inline` solo sotto `/una-cartella/` che ne ha davvero bisogno), ognuna sostituisce interamente la politica di default per il proprio prefisso — mai una fusione, mai un allentamento globale; ogni eccezione resta visibile in `audit security` (CSP-001/CSP-002 analizzano anche le zone), anche se deliberata. Creazione guidata da un assistente direttiva per direttiva (schermata **Sicurezza generica**), ogni campo precompilato con il valore **attuale** della politica globale — per modificare solo ciò che deve cambiare invece di ripartire da un campo vuoto che sacrificherebbe involontariamente le altre direttive; viene chiesta un'ulteriore conferma esplicita se la zona assemblata allenta `unsafe-inline`/`unsafe-eval`/una sorgente generica `*`.
- Indirizzi IPv4 mappati in IPv6 (`::ffff:x.x.x.x`) normalizzati prima di qualsiasi confronto (lista di blocco, proxy attendibile, limitazione della frequenza) — altrimenti, aggiramento noto.
- Verificato con test basati su proprietà (`hypothesis`, migliaia di esempi generati) sul parser HTTP e sul risolutore di percorsi, oltre ai classici test unitari/di integrazione.

## 9. TLS

### 9a. Certificato autofirmato (minimo)

Copre l'uso realistico locale/laboratorio/VPN (Tailscale...): un solo listener, `ssl.SSLContext` diretto, RSA 2048/4096 o ECDSA P-256/P-384.

### 9b. CA locale

Per più dispositivi client che devono fidarsi senza reimportare un certificato singolarmente: un'autorità di certificazione locale firma tutti i certificati di server necessari.

```text
secure/certificates/ca/
├── root-ca.key    # 0600 - l'elemento più sensibile del progetto
├── root-ca.pem    # 0644 - da importare nell'archivio di fiducia dei client
├── serial.txt     # 0600 - tiene traccia del prossimo numero di serie
└── index.txt      # 0600 - tiene traccia dello stato V(alido)/R(evocato) per certificato firmato
```

Flusso: `certs generate-ca` (passphrase della chiave della CA **obbligatoria**, inserimento interattivo con doppia conferma se `--password` è omesso) → `certs generate-csr` (chiave + CSR del server) → `certs sign-csr` (firma con la CA, copia il SAN della CSR, costruisce `fullchain.pem` se richiesto) → puntare `tls.certificate.certificate_path` su quel `fullchain.pem`. Un certificato compromesso si ritira con `certs revoke` (contrassegna `index.txt`, verifica prima che il certificato provenga davvero da questa CA — rifiuta altrimenti). Nessuna distribuzione di CRL nella V1, né CA esterna/CSR per un'autorità di terze parti, né mTLS (vedi §15).

### 9c. Let's Encrypt / ACME (Certbot) — pubblico, self-hosted

Per un sito realmente pubblico con un certificato riconosciuto dai browser, schema self-hosted completo: DDNS (Dynu o equivalente, interamente a carico dell'operatore) → Certbot → Omega-serv. Solo assistente TUI (`Configurazione dettagliata → TLS → Assistente Let's Encrypt`) — invoca `certbot certonly --webroot` come sottoprocesso (**mai** `--standalone`, la porta 80 è già occupata da Omega-serv; **mai** un client ACME reimplementato) con `--config-dir`/`--work-dir`/`--logs-dir` puntati sotto `secure/certificates/letsencrypt/` del progetto — **mai** `/etc/letsencrypt/` — il che rende Certbot stesso completamente privo di privilegi. Il certificato ottenuto viene importato automaticamente (stesso meccanismo di `certs import`, vedi gli esempi CLI sopra) e viene scritto uno script di hook per il rinnovo. Modalità di prova (staging) selezionata di default — da deselezionare una volta verificato che dominio/webroot funzionano, per evitare i limiti di frequenza reali di Let's Encrypt.

Prerequisiti interamente fuori dal perimetro di Omega-serv: un dominio puntato sull'IP pubblico (DDNS), e le porte 80/443 inoltrate a questa macchina.

### 9d. Rinnovo automatico (Certbot)

`Configurazione dettagliata → TLS → Rinnovo automatico` si adatta al gestore di servizi realmente rilevato **per questa istanza** (mai un meccanismo condiviso tra più istanze multi-istanza): systemd → genera e installa un timer (`<servizio>-certbot-renew.timer`, due volte al giorno + ritardo casuale, `certbot renew` limitato al `--config-dir` dell'istanza); altrimenti → riga di crontab (utente corrente, nessun privilegio) se `crontab` è disponibile; altrimenti → istruzioni manuali mostrate, nessuna scrittura forzata. Su alcune distribuzioni (tra cui Arch/Manjaro), il pacchetto Certbot non installa **nessun** timer di default, a differenza di Debian/Ubuntu — da qui questa schermata invece di una semplice verifica di un meccanismo che si presume già presente. Una volta configurato, il rinnovo reimporta automaticamente ogni certificato rinnovato (`certs import`) e poi riavvia il servizio, senza più alcun intervento manuale.

## 10. Audit di sicurezza

`audit security` è **non bloccante**: riesegue le barriere già bloccanti di `config check` come `CRITICAL`, poi applica regole consultive (TLS, CSP, metodi pericolosi, timeout, igiene degli upload in modo puro; permessi dei file, scadenza dei certificati, unità systemd installata, dimensione dei log con I/O reale). `WAF-001` (WAF rimasto in `log-only`) viene osservato nel tempo tramite un piccolo file di stato (`var/run/waf-mode-state.json`) — si attiva solo dopo ≥14 giorni osservati in `log-only` su esecuzioni ripetute, non al primo `audit`.

## 11. Active Defense (deception + modalità guerra)

Modulo opzionale (`option enable active_defense`, disattivato di default) che qualifica un comportamento ostile a partire dai segnali WAF già calcolati (`WafDecision`/reputazione/lista di blocco — mai un secondo calcolo di punteggio indipendente), e può dirottare una sorgente verso un'esca, rallentarne le risposte e registrarla più in dettaglio, costruire un incidente sfruttabile, poi esportare indicatori di compromissione (IoC). Non blocca mai il traffico da sé — il blocco di rete resta compito di `omega-fire`; Active Defense osserva, devia, rallenta e registra.

**Minacce e punteggio**: ogni sorgente (`IP + hash SHA-256 dello User-Agent`) accumula un punteggio (`WAF-001` bloccante +10, escalation di reputazione +25, ban noto +25, POST su un'esca già assegnata +30 — decremento di -5 ogni 15 minuti senza nuovi eventi) qualificato come `normal`/`suspicious`/`hostile`/`contained` (`contained` richiede in più un ban già noto). `mode: monitor` osserva senza agire; `mode: enforce` applica davvero le azioni seguenti.

**Modalità guerra** (`options.active_defense.settings.war_mode`): un `DefensePlaybook` (`actions: ["redirect_to_decoy", "enrich_log", "delay", "rate_limit", "create_incident", "export_ioc"]`) attivato da soglie configurabili, per ogni sorgente non `normal`:
- `enrich_log` — registro JSONL separato (`var/log/active-defense-enriched.jsonl`, mai mescolato al log WAF/di produzione), intestazioni oscurate, corpo HTTP con hash (SHA-256) o troncato a seconda di `logging.capture_request_body`.
- `delay` — rallentamento limitato e con jitter (`war_mode.slowdown.minimum_ms`/`maximum_ms`/`jitter_ms`), mai un blocco del ciclo asyncio.
- `rate_limit` — limitazione della frequenza dedicata per sorgente (`war_mode.rate_limit.requests`/`window_seconds`), riutilizza lo stesso meccanismo del WAF con una chiave distinta.
- `create_incident` — apertura/fusione automatica di un incidente al superamento di `thresholds.incident_score`.

**Deception**: una sorgente `hostile`/`contained` può essere assegnata a un'esca statica (`fake_admin`, `fake_cms`, `fake_api`, `fake_secrets` — risposte plausibili ma sempre fisse, mai una lettura reale di file né un sottoprocesso) scelta in base alla classe di attacco osservata (`deception.profiles.<nome>.match_attack_classes`, una o più tra `scan`/`credential_stuffing`/`sqli`/`xss`/`path_traversal`/`upload_probe`/`api_probe`/`unknown`). Due livelli di isolamento, assunti e documentati come tali:
- **Livello 1** (fixture nel processo, `isolation_level: "fixture"`, di default) — isolamento DEBOLE esplicito: stesso processo, stesso utente di sistema della produzione, accettabile solo perché la fixture non fa mai altro che restituire un modello statico. Il NOME del profilo deve corrispondere esattamente a una delle 4 fixture sopra — altrimenti viene rifiutato in validazione (`validate_active_defense_config`), per evitare la trappola di un'esca dal nome sbagliato che non si attiverebbe mai, in silenzio.
- **Livello 2** (backend realmente isolato, `isolation_level: "proxy"`) — inoltrato a un processo separato tramite `options.active_defense.settings.deception.decoy_zones.<nome>` (upstream `host`/`port` di un server già in esecuzione, mai creato automaticamente; mai letto da `options.reverse_proxy` — un'esca non può mai puntare per errore a una zona di produzione, verificato da `config check`), riutilizzando lo stesso meccanismo di reverse proxy in uscita della produzione (`serve_proxy()` — upstream irraggiungibile al momento di una richiesta reale: 502 restituito all'attaccante, mai un crash).

**Schermata Impostazioni** (TUI, Sicurezza attiva → Active Defense → Impostazioni): configurazione completa di tutto quanto sopra — modalità, attivazione della modalità guerra, ambito/azioni/soglie/rallentamento/limite di richieste, deception (comportamento di default, CRUD dei profili di esca e delle zone di esca con valori di esempio mostrati in ogni campo), IoC, archiviazione e registrazione — validata dalle stesse regole della CLI prima di ogni salvataggio, senza mai richiedere la modifica manuale di `config/omega-serve.json`. Dopo ogni modifica è sempre richiesto un riavvio completo (Active Defense non viene mai ricaricato a caldo).

**Incidenti e IoC**: cronologia completa per incidente, estrazione di indicatori (IP, User-Agent con hash), esportazione JSON versionata/CSV limitata agli IoC condivisibili/rapporto Markdown, e formati di scambio **STIX 2.1** (bundle da caricare in OpenCTI, in un SIEM…) e **MISP** (evento da importare dall'interfaccia di MISP), marcati TLP:AMBER di default — file locali, mai inviati; ogni esportazione è accompagnata da un file `<export>.sha256` (formato `sha256sum` standard). Esportazione automatica alla chiusura di un incidente se `ioc.auto_export_on_close` (vero di default). Gli stati scaduti e il registro di audit vengono ripuliti automaticamente e la base è limitata (protezione contro il riempimento del disco); `active-defense purge` chiude inoltre gli incidenti tornati silenziosi.

**Simulazione**: `active-defense simulate` (CLI) e il pulsante "Simula" (TUI, schermata Sicurezza attiva) proiettano punteggio/livello e spiegano ogni azione che si attiverebbe — dry-run rigoroso, nessuna scrittura reale, nessun impatto sulla rete.

Backup/ripristino: `config backup --include-active-defense` include la base sqlite (minacce/incidenti/assegnazioni) nell'archivio — mai un segreto in chiaro, quindi non serve `--confirm-secrets`, a differenza di `--include-auth`.

## 11b. Liste di percorsi sensibili (WAF)

Il WAF può caricare **liste modificabili** in file di testo, un percorso (o una parola chiave) per riga, da **Sicurezza attiva → Custom → Aggiungi → « CARICA una lista »**. Nulla viene mai caricato di default: è un'azione esplicita.

- **Riferimenti forniti**: `sensitive-paths-hostile` (298 percorsi senza uso legittimo: segreti, backup, VCS, console…) e `sensitive-paths-probe` (132 percorsi di sondaggio, a volte serviti da un sito reale: `/admin`, `/api`, monitoraggio…). Al caricamento viene creata una **copia locale** in `secure/waf/rules/keywords/`: è quella che modifichi, e un aggiornamento di omega-serv non la sovrascrive mai (« Novità del riferimento » propone poi, voce per voce, le nuove voci).
- **Sintassi**: `/admin` (→ `/admin` e `/admin/xxx`, mai `/administrator`), `/.git/` (tutto ciò che sta sotto), `/*.bak` (estensione), `!/api/v1` (eccezione, sempre prioritaria). Percorsi decodificati come nel motore (`%2e`, doppia codifica, caratteri a larghezza piena).
- **Gravità**: *Osservazione* (solo registro, consigliata al primo caricamento), poi Media (non blocca mai da sola) o Alta (403 fin dal primo accesso).
- **Recidiva propria di ogni lista**: 1° accesso = informazione o rifiuto; N accessi in M minuti = ban applicativo temporaneo (risposta 451, anche tramite Tailscale); blocchi ripetuti = ban di rete da parte di omega-jail. Riferimenti: hostile 2 accessi in 10 min → 24 h, sondaggio 5 in 10 min → 1 h.
- **Mai un ban automatico** per l'host locale, Tailscale (`100.64.0.0/10`) e la rete locale (`options.waf.reputation.never_auto_block`): solo il traffico esterno può essere bannato. Dietro un proxy locale, l'esenzione di `127.0.0.1` richiede `trusted_proxy` attivo. `X-Forwarded-For` viene letto da destra a sinistra: un client non può dichiararsi locale.
- **Salvaguardie**: percorsi vitali protetti (`/`, `robots.txt`, `sitemap.xml`, `/.well-known/acme-challenge/`…), rifiuto di una lista bloccante che toccherebbe un percorso realmente servito (alias, reverse proxy, zona Auth, webroot), **« Verifica sui miei log »** nell'editor (righe che avrebbero colpito richieste riuscite, eccezione con un clic).
- **Editor integrato**: diagnostica in tempo reale con numero di riga, « Prova » un percorso, scrittura sicura (permessi e gruppo conservati, link simbolici rifiutati, modifica esterna rilevata), leggibilità da parte dell'account del servizio verificata (« Correggi i permessi »), e ricaricamento **onesto**: rifiutato con il motivo se la lista non supera la verifica, e il server mantiene allora le regole attuali.

## 11c. Limitazione della frequenza per cartella e per IP/rete (WAF)

La limitazione della frequenza del WAF (secchio a gettoni, `options.waf.rate_limit`, 60 richieste / 60 s per IP di default) può essere affinata da **Sicurezza attiva → Esclusioni e frequenza** (oppure a mano, `rate_limit.path_policies` / `rate_limit.source_policies`):

- **Regola per cartella** (`prefix`, `requests`, `window_seconds`): **sostituisce** il limite globale per quella cartella, con un proprio contatore (`requests: 0` = illimitato). Vince il prefisso più lungo; `/images` copre `/images/a.png`, mai `/images2`. Tipicamente una pagina pesante (galleria di immagini) che restituisce 429.
- **Regola per IP/rete** (`network`, `requests`, `window_seconds`, `trusted`): stesso principio; vince la rete più precisa. Priorità: cartella, poi IP/rete, poi limite globale.
- **Ban invariato per il pubblico**: un superamento da parte di un IP pubblico resta registrato `"action": "block"` in `waf-alerts.log`, quindi bannabile da omega-jail (3 rifiuti in 10 min → 12 h). Una **sorgente sicura** — rete `never_auto_block` o regola marcata `trusted: true` — riceve comunque il 429 ma viene registrata `"action": "throttle"`, che la jail non conta mai.
- **Script magnet**: il suo limite di frequenza (risposta 429) non conta mai come rilevamento, quindi non porta mai all'auto-ban; su una richiesta coperta da una regola per cartella o per IP/rete prevale la regola nativa e il 429 di magnet viene ignorato (le sue firme d'attacco restano applicate).
- Una regola di frequenza non disattiva **mai** l'ispezione del WAF; al contrario, un'esclusione dall'ispezione (`exclusions.path_prefixes`) non revoca mai la limitazione della frequenza. Senza `trusted_proxy` attivo, una regola che copre `127.0.0.1`/`::1` viene ignorata (stessa salvaguardia di `never_auto_block`).

## 12. Servizi e gestione

Rilevamento automatico di systemd/OpenRC/runit (`service install/status/start/stop/restart/enable/disable/uninstall`). L'unità systemd generata applica di default un irrigidimento non negoziabile: `NoNewPrivileges`, `PrivateTmp`, `ProtectSystem=strict`, `ProtectHome`, `ReadWritePaths` limitato a `var/`, utente/gruppo dedicati obbligatori, `UMask=0077`, `Restart=on-failure`. Arresto pulito con SIGTERM (svuotamento delle connessioni in corso, periodo di tolleranza configurabile poi chiusura forzata); ricaricamento a caldo con SIGHUP (solo regole WAF e zone Auth — bind/porta/TLS e Active Defense mai modificabili senza un riavvio completo).

## 13. Log

`var/log/access.log` (formato Apache combined + `request_id`, escaping contro l'iniezione nei log), `var/log/error.log`. Rotazione per dimensione/numero di file conservati (`logs.rotation`). WAF nativo: `var/log/waf-alerts.log` (`options.waf.logging.path`). Script magnet (§7): `options.waf.magnet.paths.alerts_log`/`.blocklist_log`, default `var/log/waf-magnet-alerts.log`/`var/log/waf-magnet-blocklist.log` — aggiunti d'ufficio alla Libreria (pulsante *Aggiungi i log noti di Omega-Serv*) solo se magnet è attivo; `lnav` invece li propone sempre (un file assente viene semplicemente ignorato all'avvio).

### 13a. Origini remote (SSH)

Centralizza, su richiesta esplicita, il log di un server backend situato nella stessa rete locale dietro il reverse proxy (schermata **Gestione dei log → Libreria → Origini remote (SSH)**). Un « fetch » è un'azione manuale e puntuale, mai un flusso in tempo reale né un polling automatico: una **copia** viene recuperata tramite `scp` al clic su *Recupera ora*, scritta sotto `var/log/remote/`, poi aggiunta alla Libreria come un log normale (colonna *Accesso* = `ssh`, colonna *Modificato* = data di **questo** recupero — mai quella del file remoto); un nuovo recupero sostituisce semplicemente la copia precedente con una più recente.

Salvaguardie deliberate (vedi `OMEGA-SERV_ETUDE-FAISABILITE_LOGS_DISTANTS.md` per lo studio completo): nessuna scansione di rete automatica, nessuna connessione senza configurazione esplicita (etichetta/host/percorso remoto, utente/porta/chiave privata facoltativi — vuoti, lasciano decidere `ssh`/`~/.ssh/config` come se il comando fosse digitato a mano), nessuna password mai chiesta né memorizzata (una chiave privata è referenziata solo dal suo percorso, mai letta né memorizzata da Omega-serv), nessuna verifica della dimensione prima del trasferimento. Capacità `scp` rilevata localmente nel **Registro delle capacità** (solo presenza del binario, mai un test di raggiungibilità di un host); Samba volutamente lasciato da parte (YAGNI, finché non si conferma un bisogno reale).

## 14. Test

```bash
source .venv/bin/activate
lint-imports        # verifica gli 8 contratti di strati
pytest -q           # 2485 test
ruff check .
mypy src
```

Struttura: `tests/unit/` (dominio/applicazione, doppi di test), `tests/integration/` (vero server asyncio su veri socket TCP, vero `openssl` come sottoprocesso, veri comandi CLI su un progetto temporaneo completo, interfaccia interattiva tramite l'API `Pilot` di Textual - mai uno screenshot), `tests/security/` (test basati su proprietà `hypothesis` sul parser HTTP e sul risolutore di percorsi).

## 15. Fuori perimetro

- CGI grezzo (solo FastCGI/PHP-FPM)
- mTLS (autenticazione del client tramite certificato), OCSP stapling
- CA esterna / CSR per un'autorità di terze parti, distribuzione completa di CRL
- Active Defense: integrazione reale con gli eventi di ban di `omega-fire` (bloccata lato `omega-fire`, che oggi non espone alcuna superficie di lettura)

---

> 🔒 OMEGA-SERV — Un server web solido, completo, sicuro e difensivo.
