<!-- Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE) -->

# omega-serv compared with the web servers on the market

**Measured comparison: nginx · lighttpd · Caddy · Apache · Traefik · omega-serv 2.0**

🌐 [Français](../../comparatif-serveurs-web.md) · **English** · [Español](../es/comparatif-serveurs-web.md) · [Português (Brasil)](../pt-BR/comparatif-serveurs-web.md) · [Italiano](../it/comparatif-serveurs-web.md) · [Deutsch](../de/comparatif-serveurs-web.md) · [Nederlands](../nl/comparatif-serveurs-web.md) · [Polski](../pl/comparatif-serveurs-web.md) · [Русский](../ru/comparatif-serveurs-web.md) · [中文](../zh-CN/comparatif-serveurs-web.md) · [Tiếng Việt](../vi/comparatif-serveurs-web.md) · [ไทย](../th/comparatif-serveurs-web.md) · [Bahasa Indonesia](../id/comparatif-serveurs-web.md) · [日本語](../ja/comparatif-serveurs-web.md) · [한국어](../ko/comparatif-serveurs-web.md) · [हिन्दी](../hi/comparatif-serveurs-web.md) · [العربية](../ar/comparatif-serveurs-web.md)

This document places omega-serv among the most widely used web servers. It does not try to name a "best server": each tool serves different needs. It provides three things:

1. **real measurements**, taken on the same machine, with the same client and the same files, and reproducible;
2. a **feature comparison**, each feature checked against each server's official documentation (links at the end of the document), distinguishing what is built in from what needs a module or a plugin;
3. what omega-serv **really adds**, and what the others do **better than it**.

All figures below were measured on 26 October 2026. No figure is taken from another website or estimated.

---

## Contents

1. [In short](#1-in-short)
2. [Measurement method](#2-measurement-method)
3. [Performance: omega-serv versus nginx, lighttpd and Caddy](#3-performance-omega-serv-versus-nginx-lighttpd-and-caddy)
4. [omega-serv 1.0 → 2.0: what changed, measured](#4-omega-serv-10--20-what-changed-measured)
5. [Feature comparison](#5-feature-comparison)
6. [Administration and ergonomics](#6-administration-and-ergonomics)
7. [What omega-serv adds](#7-what-omega-serv-adds)
8. [What the others do better](#8-what-the-others-do-better)
9. [Which server for which use](#9-which-server-for-which-use)
10. [Reproducing the measurements](#10-reproducing-the-measurements)
11. [Sources](#11-sources)

---

## 1. In short

- **Raw throughput on small files**: nginx and lighttpd, written in C, serve **10 to 20 times more** requests per second than omega-serv, written in Python. Caddy, written in Go, sits in between. This is a difference in nature, not in tuning: omega-serv does not aim at this ground.
- **Large files**: since 2.0, omega-serv hands the sending over to the kernel (`sendfile`). It then reaches **the same order of throughput** as nginx, lighttpd and Caddy on this machine: 2.1 GB/s versus 2.0 to 2.4 GB/s.
- **Memory**: lighttpd (1 MB) and nginx (4 to 5 MB) remain out of reach. omega-serv stays under 30 MB under load with 1 process, Caddy around 55 MB.
- **From 1.0 to 2.0**: large-file throughput multiplied by 2.8; memory during large downloads divided by 45; up to +50% on small files with 2 processes (boost mode); Active Defense cost divided by 12.
- **What omega-serv has in addition**: complete administration from a terminal interface (TUI), in 17 languages; a built-in WAF and active defense; security limits that stay exact with several processes; import of lighttpd mod_magnet scripts; management of several instances.
- **What it does not have**: HTTP/2 and HTTP/3, Docker/Kubernetes service discovery, a built-in ACME client (it goes through Certbot), the throughput of a server written in C.

---

## 2. Measurement method

### Machine and software

| Item | Value |
|---|---|
| Processor | Intel Core i5 M480 at 2.67 GHz (2010): 2 physical cores, 4 threads |
| Memory | 8 GB |
| System | Manjaro Linux, kernel 6.18 |
| Network | loopback (127.0.0.1) |
| Load client | [oha](https://github.com/hatoo/oha) 1.16.0 (written in Rust) |
| nginx | 1.30.4 (Manjaro package) |
| lighttpd | 1.4.85 (Manjaro package) |
| Caddy | 2.11.4 (Manjaro package) |
| omega-serv | 1.0.0 (published archive) and 2.0.0, under Python 3.14.7 |

Apache and Traefik were not measured, as they were not installed on this machine. Traefik is not a file server anyway (see §5). These two servers therefore only appear in the feature comparison.

### Protocol

- **Processor isolation**: each server is pinned to physical core 0 (threads 0 and 2), and the client to physical core 1 (threads 1 and 3). The client thus does not steal time from the server, and all servers have exactly the same resources.
- **Same files for all**: `small.html` (1 KB), `medium.png` (100 KB) and `large.bin` (5 MB), served from the same folder.
- **Access log enabled everywhere**, because a production server logs.
- **Plain HTTP/1.1, persistent connections (keep-alive)**. Concurrency is 32 connections for the 1 KB and 100 KB files, and 8 for the 5 MB file.
- **Duration**: 10 seconds per file and per configuration.
- **Repetitions**: 3 full rounds, interleaved (all servers in round 1, then all in round 2, etc.). The tables give the **median** of the three rounds.
- **Memory**: PSS (*Proportional Set Size*) summed over all the server's processes. Unlike RSS, a page shared between processes is counted only once. It is recorded at rest, then after the load.
- **Configurations**: nginx, lighttpd and Caddy in their basic configuration (static files, access log). omega-serv uses the `standard` profile, with the WAF disabled, then enabled with all its bundled rules.
- **Number of processes**: each server is measured with 1 then 2 processes (nginx `worker_processes`, lighttpd `server.max-worker`, Caddy `GOMAXPROCS`, omega-serv `server.workers`).

### Limits to keep in mind

- **Modest and old machine.** Absolute values would be much higher on a recent server. What matters are the **ratios** between servers measured in the same session.
- **Variability from one session to another**: about 10 to 30% depending on the machine's background load. Rounds within the same session remain consistent: less than 5% difference for omega-serv and Caddy, more for nginx and lighttpd, whose very high throughput is more sensitive to the rest of the machine.
- **Loopback**: the measurement does not go through a real network. On a real network, large-file throughput is almost always limited by bandwidth, not by the server.
- **No TLS** in these measurements. With HTTPS, omega-serv cannot use `sendfile` and sends files in chunks.
- **Raw figures**: they are published with this document in [`docs/benchmarks/2026-10-26-campagne-brute.txt`](../../benchmarks/2026-10-26-campagne-brute.txt).

---

## 3. Performance: omega-serv versus nginx, lighttpd and Caddy

### Small files (1 KB): requests per second

| Server | 1 process | 2 processes | p99 latency (1 proc.) |
|---|---:|---:|---:|
| lighttpd 1.4.85 | 25,521 | 29,700 | 4.5 ms |
| nginx 1.30.4 | 14,054 | 18,315 | 4.7 ms |
| Caddy 2.11.4 | 3,697 | 5,345 | 25.3 ms |
| **omega-serv 2.0** | **1,358** | **1,953** | **37.5 ms** |
| omega-serv 2.0 + WAF | 1,130 | 1,617 | 48.5 ms |
| omega-serv 1.0 | 1,304 | — | 41.2 ms |

### Medium files (100 KB): requests per second

| Server | 1 process | 2 processes |
|---|---:|---:|
| lighttpd | 11,635 | 13,037 |
| nginx | 8,024 | 9,555 |
| Caddy | 3,280 | 4,344 |
| **omega-serv 2.0** | **1,247** | **1,629** |
| omega-serv 2.0 + WAF | 1,012 | 1,347 |
| omega-serv 1.0 | 1,064 | — |

### Large file (5 MB): throughput

| Server | 1 process | 2 processes |
|---|---:|---:|
| lighttpd | 2,379 MB/s | 2,407 MB/s |
| nginx | 2,242 MB/s | 1,981 MB/s |
| Caddy | 2,165 MB/s | 2,229 MB/s |
| **omega-serv 2.0** | **1,658 MB/s** | **2,115 MB/s** |
| omega-serv 1.0 | 584 MB/s | — |

### Memory (PSS, all server processes)

| Server | At rest | After the load |
|---|---:|---:|
| lighttpd (1 or 2 proc.) | 1 MB | 1 MB |
| nginx (1 or 2 proc.) | 4 to 5 MB | 4 to 5 MB |
| **omega-serv 2.0 (1 proc.)** | **26 MB** | **30 MB** |
| omega-serv 2.0 (2 proc.) | 39 MB | 48 MB |
| Caddy | 50 MB | 56 MB |
| omega-serv 1.0 | 22 MB | 100 MB |

### Reading

- **On small and medium files**, the gap with nginx and lighttpd is an order of magnitude (×10 to ×20). It is the cost of a server written in Python: each request goes through the interpreter, whereas nginx and lighttpd process it in compiled C. Boost mode narrows the gap, without closing it.
- **On large files**, the servers converge, because the kernel copies the data (`sendfile`). With 2 processes, omega-serv 2.0 reaches 2.1 GB/s, in the same range as the others (2.0 to 2.4 GB/s).
- **omega-serv's WAF costs about 17%** on small files: it inspects every request. nginx, lighttpd and Caddy were measured without a WAF; a WAF added to these servers (ModSecurity, Coraza) also has a cost, not measured here.
- **To put these figures in perspective**: 1,300 requests per second is more than 110 million requests per day on this 2010 machine. That is far beyond the needs of a personal site, an internal service or a lab, which are the uses omega-serv targets.

---

## 4. omega-serv 1.0 → 2.0: what changed, measured

### Performance

Both versions were measured in the same session, on the same machine and with the same protocol.

| Measurement | 1.0.0 | 2.0.0 | Change |
|---|---:|---:|---:|
| Small files (1 KB), 1 process | 1,304 req/s | 1,358 req/s | +4% |
| Small files (1 KB), boost mode 2 processes | — | 1,953 req/s | **+50%** vs 1.0 |
| Small files with WAF, 1 process | 1,097 req/s | 1,130 req/s | +3% |
| Small files with WAF, 2 processes | — | 1,617 req/s | **+47%** vs 1.0 |
| 100 KB files, 1 process | 1,064 req/s | 1,247 req/s | +17% |
| Large file (5 MB), 1 process | 584 MB/s | 1,658 MB/s | **×2.8** |
| Large file (5 MB), 2 processes | — | 2,115 MB/s | **×3.6** vs 1.0 |
| Memory after the load, 1 process | 100 MB | 30 MB | **÷3** |

### Simultaneous large downloads

Test: 3 simultaneous downloads of a 300 MB file, while a small page is requested continuously. Two runs give identical results.

| Measurement | 1.0.0 | 2.0.0 |
|---|---:|---:|
| Peak server memory | 1,835 MB | 40 MB |
| Small page during the downloads: median | 3 to 4 ms | 2 ms |
| Small page during the downloads: worst case | 1.7 to 1.8 s | 5 ms |

Version 1.0 loaded each file entirely into memory before sending it. Version 2.0 sends it in chunks, or hands it over to the kernel: memory no longer depends on file size, and the server stays responsive during downloads.

### Cost of active defense

Cost of one threat observation by Active Defense, for each suspicious request, measured on disk (ext4) over 2,000 observations:

| Measurement | 1.0.0 | 2.0.0 |
|---|---:|---:|
| Median | 2.84 ms | 0.23 ms |
| p99 | 11.6 ms | 2.3 ms |
| Maximum | 18 to 20 ms | 37 to 46 ms |

The median is divided by 12. The maximum, however, is higher in 2.0: a few isolated spikes, caused by the periodic writing of the SQLite journal to disk.

### Features that arrived with 2.0

**Catching up with market standards**: nginx, lighttpd, Caddy and Apache already do all of this. omega-serv catches up.

- Conditional requests (ETag, Last-Modified, 304 responses): reloading a page only downloads again what has changed.
- Partial requests (Range, 206/416): resuming a download, seeking in a video.
- Sending files with `sendfile` or in chunks, with stable memory.
- Pre-compressed files (`.gz`, `.br`) placed next to the original.
- Default Cache-Control by file type (images, fonts, CSS/JS), adjustable.
- Several server processes (boost mode, `server.workers`).

**Broader features:**

- **Complete reverse proxy.** Version 1.0 only had a simple relay (round robin, TLS to the upstream, WebSocket). Version 2.0 adds:
  - 6 load-balancing strategies, 7 in total;
  - session affinity and header-based routing;
  - passive and active health checks of the upstream servers;
  - a response cache;
  - protection against overload and against loops;
  - live control.
- **Rate limit per folder and per address or network**, in addition to the global limit.
- **Security counters shared between processes** (see §7).
- **Ready-to-use sensitive path lists**, with an observation mode and a built-in editor.
- **Import of lighttpd mod_magnet scripts** (see §7).
- **Interface in 17 languages**, with a separate language for the pages seen by visitors and for exports.
- **Logs completely reworked**:
  - a log library;
  - three viewers, including lnav;
  - fetching remote logs over SSH.

---

## 5. Feature comparison

Legend:
- ✅ built in;
- 🧩 official module of the project, to enable or install;
- 🔌 third-party module or plugin;
- ⚙️ through an external tool;
- ❌ absent.

"Commercial" means a feature reserved for the paid edition.

### HTTP serving

| Feature | nginx | lighttpd | Caddy | Apache | Traefik | omega-serv 2.0 |
|---|---|---|---|---|---|---|
| Serving static files | ✅ | ✅ | ✅ | ✅ | ❌ (proxy only) | ✅ |
| ETag / 304 / Range | ✅ | ✅ | ✅ | ✅ | — | ✅ |
| Pre-compressed `.gz` / `.br` files | ✅ `gzip_static` (`.br`: 🔌) | 🔌 Lua script (mod_magnet) | ✅ `precompressed` | 🧩 mod_rewrite recipe | — | ✅ |
| On-the-fly compression | ✅ | ✅ mod_deflate | ✅ | 🧩 mod_deflate | ✅ middleware | ❌ |
| HTTP/2 | ✅ | ✅ | ✅ | 🧩 mod_http2 | ✅ | ❌ |
| HTTP/3 (QUIC) | ✅ | ❌ | ✅ | ❌ | ✅ | ❌ |
| PHP through FastCGI | ✅ | ✅ | ✅ | ✅ | ❌ | ✅ |
| Several processes or cores | ✅ workers | ⚠️ `max-worker`, discouraged by the documentation | ✅ (Go, all cores) | ✅ MPM | ✅ (Go) | ✅ `server.workers` |

### Reverse proxy

| Feature | nginx | lighttpd | Caddy | Apache | Traefik | omega-serv 2.0 |
|---|---|---|---|---|---|---|
| Load balancing | ✅ round robin, least connections, hash | ✅ fair, round-robin, hash, sticky | ✅ about a dozen strategies | 🧩 mod_proxy_balancer | ✅ wrr, p2c, hrw, least-time | ✅ 7 strategies, including real load |
| Passive health (removing a failed server) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Active health (periodic probe) | Commercial (NGINX Plus) | ❌ | ✅ | 🧩 mod_proxy_hcheck | ✅ | ✅ |
| Response cache | ✅ `proxy_cache` | ❌ | 🔌 | 🧩 mod_cache | Commercial | ✅ |
| WebSocket | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Service discovery (Docker, Kubernetes) | 🔌 | ❌ | 🔌 | ❌ | ✅ (core of the project) | ❌ |

### TLS

| Feature | nginx | lighttpd | Caddy | Apache | Traefik | omega-serv 2.0 |
|---|---|---|---|---|---|---|
| Automatic certificates (ACME, Let's Encrypt) | 🧩 `ngx_http_acme_module` | ⚙️ Certbot | ✅ by default | 🧩 mod_md | ✅ | ⚙️ Certbot, with a built-in wizard and scheduled renewal |
| Local CA | ❌ | ❌ | ✅ internal CA (automatic issuance) | ❌ | ❌ | ✅ generation, CSR signing, revocation |

### Security

| Feature | nginx | lighttpd | Caddy | Apache | Traefik | omega-serv 2.0 |
|---|---|---|---|---|---|---|
| Per-client rate limit | ✅ `limit_req` | ⚠️ mod_evasive (simultaneous connections only) | 🔌 caddy-ratelimit | 🔌 mod_evasive, mod_qos | ✅ middleware | ✅ |
| Limit shared between processes | ✅ shared memory zone | ❌ counted per process | — (single process) | depends on the module | 1 instance; several with Redis | ✅ shared memory |
| WAF (SQLi/XSS signatures, scanners…) | 🔌 ModSecurity, Commercial (App Protect) | ❌ (Lua scripts to write) | 🔌 Coraza | 🔌 ModSecurity | 🔌 plugins | ✅ built in |
| Blocklist with expiry, recidivism | ⚙️ fail2ban | ⚙️ fail2ban | ⚙️ fail2ban | ⚙️ fail2ban | ⚙️ | ✅ built in |
| Decoys, war mode, incidents, IoC export | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ Active Defense |
| Security audit of the configuration | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ `audit security` |
| Observation mode (log without blocking) | depends on the module | — | depends on the plugin | ✅ ModSecurity `DetectionOnly` | depends on the plugin | ✅ |

### Extensibility

| Feature | nginx | lighttpd | Caddy | Apache | Traefik | omega-serv 2.0 |
|---|---|---|---|---|---|---|
| Scripting language | 🧩 njs (JavaScript); 🔌 Lua (OpenResty) | ✅ Lua (mod_magnet) | Go modules (recompilation) | 🧩 mod_lua | Go or WebAssembly plugins | 🔌 import of mod_magnet scripts (`magnet` option) |
| Module ecosystem | very large | targeted | large | very large | large | none: everything is built in |

---

## 6. Administration and ergonomics

| Server | Main administration mode | Interface | Reload without interruption |
|---|---|---|---|
| nginx | configuration files | none (dashboard: NGINX Plus, commercial) | ✅ `nginx -s reload` |
| lighttpd | configuration file | none (mod_status, read-only) | ✅ graceful restart |
| Caddy | Caddyfile or JSON | REST administration API | ✅ through the API |
| Apache | configuration files and `.htaccess` | none (mod_status, read-only) | ✅ `graceful` |
| Traefik | container labels, files or Kubernetes | web dashboard (read-only) | ✅ dynamic configuration |
| omega-serv | terminal interface (TUI) and command line (CLI); the JSON file never needs editing | **complete TUI with keyboard and mouse, 17 languages, built-in help** | ✅ for most settings; restart announced for the port, TLS and the number of processes |

In practice, with omega-serv, configuration, security, logs, system services, backups and instances are all managed from a single interface. Each setting is explained and checked before being written. With the other servers, you edit text files, then call on separate tools (Certbot, fail2ban, logrotate, ModSecurity, a monitoring tool…).

In return, the "configuration file" approach of nginx, Apache and Caddy automates very well (Ansible, containers, version control). omega-serv has a scriptable CLI, but its automation ecosystem remains limited.

---

## 7. What omega-serv adds

This section only keeps what none of the compared servers provides as is, without a third-party module or an external tool.

1. **Complete administration from a terminal interface.**
   - The interface covers the whole server: the site, security, logs, services, backups and instances.
   - It works with keyboard and mouse, on a server without a graphical display, even over SSH.
   - It is available in 17 languages and explains every setting.
   - The other servers have no administration interface (nginx, lighttpd, Apache), or only an API (Caddy) or a read-only dashboard (Traefik).
2. **Built-in active security, with no modules to assemble.**
   - The WAF includes signatures, editable path lists, recidivism, a blocklist with expiry, reputation and an observation mode.
   - Active Defense adds decoys, a war mode, incident tracking, export of indicators of compromise and a dry-run simulation.
   - Elsewhere, these features require assembling ModSecurity or Coraza, rule sets and fail2ban.
3. **Security limits that stay exact with several processes.**
   - In boost mode, the rate limit and WAF recidivism are shared in memory between processes. An attacker therefore cannot multiply their limit by the number of processes.
   - lighttpd documents the opposite case: with `server.max-worker`, `mod_evasive` and `mod_status` count separately in each process.
   - nginx also shares its counters (`limit_req` zones), but it has no built-in WAF.
4. **Import of lighttpd mod_magnet scripts.**
   - A Lua protection script already written for lighttpd can be imported without being rewritten.
   - It adds to the built-in protection without ever being able to weaken it, and its compatibility is checked before activation.
5. **Management of several instances.**
   - A registry lists all instances, and the interface switches from one to another.
   - It can also uninstall an instance completely.
6. **A security audit of the configuration**: the `audit security` command is informative, never blocks and returns exit codes usable in a script.
7. **Remote log sources.**
   - The interface fetches another server's log over SSH, on demand, with no stored password.
   - It can read it with lnav, merged with the local logs.
8. **HTTP hardening that cannot be disabled**, active from installation, whatever the profile:
   - strict validation of the Host header;
   - rejection of Content-Length / Transfer-Encoding ambiguities;
   - security headers and CSP, even on error pages;
   - safe reading of X-Forwarded-For;
   - refusal to start as root.

---

## 8. What the others do better

- **Throughput and latency**: nginx and lighttpd serve 10 to 20 times more small requests, with 8 to 10 times lower latency. For a high-traffic site, a public API or a CDN, they are the ones to choose.
- **Memory**: lighttpd (1 MB) and nginx (4 to 5 MB) suit very constrained machines (embedded, entry-level Raspberry Pi, small containers).
- **Protocols**: HTTP/2 in all the others, HTTP/3 in nginx, Caddy and Traefik. omega-serv only speaks HTTP/1.1.
- **Automatic HTTPS**: Caddy and Traefik build it in by default, and nginx (`ngx_http_acme_module`) and Apache (`mod_md`) through an official module. omega-serv delegates to Certbot, with a wizard and scheduled renewal.
- **Containerised environments**: Traefik's automatic service discovery (Docker, Kubernetes) has no equivalent in omega-serv.
- **Ecosystem**: nginx and Apache offer thousands of modules, guides and integrations. Caddy offers a module system in Go. omega-serv is a young project, maintained by a single person.
- **On-the-fly compression**: omega-serv only serves files that are already compressed.

---

## 9. Which server for which use

| Need | Recommended choice |
|---|---|
| High-traffic site, public API, CDN, maximum throughput | **nginx** |
| Very constrained machine, embedded, static files | **lighttpd** |
| Quick start with automatic HTTPS, short configuration | **Caddy** |
| Legacy PHP application, `.htaccess`, shared hosting | **Apache** |
| Docker, Kubernetes, microservices | **Traefik** |
| Small site, internal service, lab, VPN, administration without editing files | **omega-serv** |
| Exposed server where you want to see and control security (WAF, bans, decoys) from a single interface | **omega-serv** |
| Internal reverse proxy with load balancing, health checks and cache, managed from an interface | **omega-serv** |
| Learning HTTP hardening and active defense | **omega-serv** |

These tools can also be combined. For example:
- nginx or Traefik at the front on the Internet, with omega-serv behind for an internal service, its security and its administration;
- omega-serv as an internal reverse proxy in front of several application servers.

---

## 10. Reproducing the measurements

The tools ship in the repository, under `tools/bench/`. You need nginx, lighttpd, Caddy and oha installed, as well as the omega-serv development environment (`.venv`).

```sh
# 1. prepare a measurement folder (test files, configurations, omega-serv 1.0 and 2.0)
tools/bench/compare/setup.sh /path/to/measure omega-serv-1.0.0.tar.gz

# 2. the 12 configurations, 3 interleaved repetitions (about 22 minutes)
tools/bench/compare/campaign.sh /path/to/measure > results.txt

# 3. medians
python3 tools/bench/compare/summarize.py results.txt

# large downloads (memory and responsiveness), 2.0 then 1.0
.venv/bin/python tools/bench/bigfile.py
BENCH_SRC=/path/to/measure/v1-archive/omega-serv/src \
BENCH_EXTRA_PATH=/path/to/measure/v1-archive/omega-serv/vendor/omega-lib/src \
  .venv/bin/python tools/bench/bigfile.py

# measure any other server already running, without oha
python3 tools/bench/bench_any.py --make-files /srv/test-webroot
python3 tools/bench/bench_any.py --port 8080
```

By default, the server is pinned to threads 0 and 2, and the client to threads 1 and 3, which matches the measurement machine. Adapt this split to your processor (`lscpu -e` shows the topology) with the `SRV_CPUS` and `CLI_CPUS` variables.

To publish your own results, give the machine, the versions, the processor split and the three repetitions.

---

## 11. Sources

Features of the other servers, according to their official documentation (consulted on 26 October 2026).

**nginx**
- [Rate limit `limit_req` (shared memory zone)](https://nginx.org/en/docs/http/ngx_http_limit_req_module.html)
- [Pre-compressed files `gzip_static`](https://nginx.org/en/docs/http/ngx_http_gzip_static_module.html)
- [Official ACME module `ngx_http_acme_module`](https://nginx.org/en/docs/http/ngx_http_acme_module.html)
- [Load balancing (`upstream`)](https://nginx.org/en/docs/http/ngx_http_upstream_module.html)
- [HTTP/3](https://nginx.org/en/docs/http/ngx_http_v3_module.html)
- [ModSecurity connector for nginx](https://github.com/owasp-modsecurity/ModSecurity-nginx)

**lighttpd**
- [`server.max-worker`: discouraged, per-process counters for mod_status and mod_evasive](https://redmine.lighttpd.net/projects/lighttpd/wiki/Server_max-workerDetails)
- [mod_magnet (Lua scripts)](https://redmine.lighttpd.net/projects/lighttpd/wiki/Docs_ModMagnet)
- [mod_deflate (compression, cache)](https://redmine.lighttpd.net/projects/lighttpd/wiki/Mod_deflate)
- [mod_proxy (load balancing, passive health, WebSocket)](https://redmine.lighttpd.net/projects/lighttpd/wiki/Docs_ModProxy)
- [mod_evasive (simultaneous connections per address)](https://redmine.lighttpd.net/projects/lighttpd/wiki/Docs_ModEvasive)

**Caddy**
- [Automatic HTTPS](https://caddyserver.com/docs/automatic-https)
- [`file_server` and `precompressed`](https://caddyserver.com/docs/caddyfile/directives/file_server)
- [`reverse_proxy` (strategies, active and passive health)](https://caddyserver.com/docs/caddyfile/directives/reverse_proxy)
- [Administration API](https://caddyserver.com/docs/api)
- [Rate limit plugin caddy-ratelimit](https://github.com/mholt/caddy-ratelimit)
- [Coraza WAF for Caddy](https://github.com/corazawaf/coraza-caddy)
- [caddy-docker-proxy](https://github.com/lucaslorentz/caddy-docker-proxy)

**Apache HTTP Server**
- [mod_md (ACME)](https://httpd.apache.org/docs/2.4/mod/mod_md.html)
- [mod_proxy_balancer](https://httpd.apache.org/docs/2.4/mod/mod_proxy_balancer.html)
- [mod_proxy_hcheck](https://httpd.apache.org/docs/2.4/mod/mod_proxy_hcheck.html)
- [mod_http2](https://httpd.apache.org/docs/2.4/mod/mod_http2.html)
- [mod_deflate, pre-compressed content](https://httpd.apache.org/docs/2.4/mod/mod_deflate.html)
- [ModSecurity](https://github.com/owasp-modsecurity/ModSecurity)

**Traefik**
- [`ratelimit` middleware (in memory per instance, Redis optional)](https://doc.traefik.io/traefik/reference/routing-configuration/http/middlewares/ratelimit/)
- [ACME](https://doc.traefik.io/traefik/https/acme/)
- [Providers (Docker, Kubernetes…)](https://doc.traefik.io/traefik/providers/overview/)

**Measurement tool**
- [oha](https://github.com/hatoo/oha)

---

*Comparison by kraynux for omega-serv 2.0.0: measurements of 26 October 2026. The measurements cover a single machine. For any capacity decision, measure on your own hardware with the tools provided.*
