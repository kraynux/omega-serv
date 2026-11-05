<!-- Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE) -->

# omega-serv compared with the web servers on the market

**Measured comparison: nginx · lighttpd · Apache · Caddy · Traefik · omega-serv 2.5**

🌐 [Français](../../comparatif-serveurs-web.md) · **English** · [Español](../es/comparatif-serveurs-web.md) · [Português (Brasil)](../pt-BR/comparatif-serveurs-web.md) · [Italiano](../it/comparatif-serveurs-web.md) · [Deutsch](../de/comparatif-serveurs-web.md) · [Nederlands](../nl/comparatif-serveurs-web.md) · [Polski](../pl/comparatif-serveurs-web.md) · [Русский](../ru/comparatif-serveurs-web.md) · [中文](../zh-CN/comparatif-serveurs-web.md) · [Tiếng Việt](../vi/comparatif-serveurs-web.md) · [ไทย](../th/comparatif-serveurs-web.md) · [Bahasa Indonesia](../id/comparatif-serveurs-web.md) · [日本語](../ja/comparatif-serveurs-web.md) · [한국어](../ko/comparatif-serveurs-web.md) · [हिन्दी](../hi/comparatif-serveurs-web.md) · [العربية](../ar/comparatif-serveurs-web.md)

This document places omega-serv among the most widely used web servers. It does not try to name a "best server": each tool answers different needs, and each has its strengths. It provides three things:

1. **real measurements**, taken on **three** very different **machines**, with the same client, the same files and the same protocol, and reproducible;
2. a **feature comparison**, each feature checked against each server's official documentation (links at the end of the document), distinguishing what is built in from what needs a module or a plugin;
3. what omega-serv **really brings in addition**, and what the others do **better than it**.

All performance measurements were taken on November 3 and 4, 2026. No figure is taken from another site or estimated. The raw figures are published with this document.

---

## Contents

1. [In short](#1-in-short)
2. [How to read this comparison](#2-how-to-read-this-comparison)
3. [Measurement method](#3-measurement-method)
4. [Performance: omega-serv versus nginx, lighttpd, Apache and Caddy](#4-performance-omega-serv-versus-nginx-lighttpd-apache-and-caddy)
5. [The omega-serv versions: 1.0 → 2.0 → 2.5](#5-the-omega-serv-versions-10--20--25)
6. [Feature comparison](#6-feature-comparison)
7. [Administration and ergonomics](#7-administration-and-ergonomics)
8. [What omega-serv brings in addition](#8-what-omega-serv-brings-in-addition)
9. [What the others do better](#9-what-the-others-do-better)
10. [Which server for which use](#10-which-server-for-which-use)
11. [Reproducing the measurements](#11-reproducing-the-measurements)
12. [Sources](#12-sources)

---

## 1. In short

- **omega-serv has two engines.** The **Python engine** handles everything itself. The **native engine**, written in C++ and introduced with 2.5, serves requests itself; Python keeps the configuration and the security decisions, the native engine recognizing on its own the requests that no WAF rule matches.
- **With the native engine, without WAF**, omega-serv serves small files at **about 0.7 times the speed of nginx**, on all three machines. It thus ranks **ahead of Apache and Caddy, behind nginx and lighttpd**.
- **With the Python engine**, omega-serv stays far behind all the others: **3 to 11 % of nginx's speed**.
- **With the WAF active**, omega-serv inspects every request, which the other measured servers do not do. With the native engine, it then serves **0.53 to 0.56 times** the speed of nginx (without WAF) on machines A and B, and 1.07 times on machine C (4 cores versus 2): the WAF takes only 5 to 22 % of its throughput. It stays ahead of Apache and Caddy measured without WAF.
- **Medium files (100 KB)**: this is the current weak point of the native engine, at **0.3 to 0.6 times** nginx, behind Apache.
- **Large files (5 MB)**: nginx, lighttpd, Apache and native omega-serv reach the same order of throughput. Caddy is clearly slower on the fastest machine.
- **Memory**: lighttpd (1 MB), nginx (4 to 5 MB) and Apache (4 to 9 MB) are very frugal. omega-serv uses **30 to 65 MB** depending on the mode, Caddy **50 to 67 MB**.
- **What omega-serv has in addition**: complete administration in a terminal interface, in 17 languages; a built-in WAF and active defense; exact security limits with several processes; import of lighttpd mod_magnet scripts; management of several instances.
- **What it does not have**: HTTP/2 and HTTP/3, on-the-fly compression, Docker/Kubernetes service discovery, a built-in ACME client (it goes through Certbot), a module ecosystem.

---

## 2. How to read this comparison

A few notions come back throughout the document.

- **Requests per second (req/s)**: the number of files a server sends in one second. The higher, the better.
- **Gap with nginx**: absolute values depend enormously on the machine. On our three machines, nginx goes from 22,000 to 440,000 req/s. What stays stable is **the ratio between servers**. The tables therefore give, next to each value, its ratio with nginx measured in the same session: **1.00 = as fast as nginx**, 0.50 = half as fast, 1.50 = half again as fast.
- **p99 latency**: the response time that 99 % of requests do not exceed. It shows the "bad moments" that an average hides.
- **PSS (*Proportional Set Size*)**: the memory really used by all the server's processes. A page shared between several processes is counted only once.
- **Processes and cores**: a server can use several processor cores. Each does it its own way. nginx, lighttpd, Apache and omega-serv in Python mode start several processes. Caddy, in Go, spreads its work across the cores. The omega-serv native engine starts one thread per available core. To compare on equal terms, we give every server **the same cores**.
- **WAF (*Web Application Firewall*)**: a filter that inspects every request to block attacks (injections, scanners…). omega-serv has one built in. The other servers can receive one as a module (ModSecurity, Coraza), but **they were measured without it**, in their base configuration.

**The right reflex**: compare the ratios, not the absolute values, and always check whether the WAF is active.

---

## 3. Measurement method

### The three machines

| | Machine A | Machine B | Machine C |
|---|---|---|---|
| Processor | Intel Core i5 M480, 2.67 GHz (2010) | Intel Celeron J3455, 1.5 GHz (2016) | AMD Ryzen AI 9 365 (2024) |
| Cores | 2 physical cores, 4 threads | 4 cores, no hyperthreading | 10 cores (4 Zen 5 + 6 Zen 5c), 20 threads |
| Memory | 8 GB | 8 GB | 32 GB |
| System | Mabox Linux (Manjaro based), kernel 6.18 | EndeavourOS, kernel 7.2 | Arch Linux, kernel 7.2 (CachyOS) |
| Server cores | 1 physical core (threads 0 and 2) | 2 cores (0 and 1) | 4 Zen 5 cores, one thread each (0 to 3) |
| Client cores | 1 physical core (threads 1 and 3) | 2 cores (2 and 3) | 6 Zen 5c cores (4 to 9) |

Machine A is an old laptop, machine B a low-power mini PC, machine C a recent laptop, on mains power, in the "balanced" energy profile. They cover a range from a small home server to a current machine.

### Software

| Software | Version |
|---|---|
| nginx | 1.30.4 (A), 1.30.5 (B, C) |
| lighttpd | 1.4.85 |
| Apache HTTP Server | 2.4.69, MPM `event` |
| Caddy | 2.11.4 (A, B), 2.11.7 (C) |
| omega-serv | 1.0.0 and 2.0.0 (published archives) and 2.5, under Python 3.14 |
| Load client | [oha](https://github.com/hatoo/oha) 1.16.0 (written in Rust) |

Traefik was not measured: it is not a file server (see §6). It only appears in the feature comparison.

### Protocol

- **Processor isolation**: the server and the client are pinned to separate cores (table above). The client therefore does not steal time from the server, and all servers have exactly the same resources.
- **Same files for everyone**: `small.html` (1 KB), `medium.png` (100 KB) and `large.bin` (5 MB), served from the same folder.
- **Access log active everywhere**, because a production server logs.
- **Plain HTTP/1.1, persistent connections (keep-alive)**. Concurrency is 32 connections for the 1 KB and 100 KB files, and 8 for the 5 MB file.
- **Duration**: 10 seconds per file and per configuration.
- **Repetitions**: 3 complete rounds, interleaved (all configurations in round 1, then all in round 2, etc.). The tables give the **median** of the three rounds. From one round to the next, the gap mostly stays under 5 %.
- **Memory**: PSS of all the server's processes, read at rest then after the load.
- **Configurations**:
  - nginx, lighttpd, Apache and Caddy in their base configuration: static files and access log;
  - omega-serv with the `standard` profile, the WAF disabled then enabled with all its shipped rules (without rate limit).
- **Number of processes**: each server is measured with 1 then 2 processes: nginx `worker_processes`, lighttpd `server.max-worker`, Apache `StartServers`/`ServerLimit`, Caddy `GOMAXPROCS`, omega-serv `server.workers`. For the omega-serv native engine, `server.workers` counts the Python security processes; the native engine itself always uses all the cores it is given.
- **No error**: all the responses of all the measurements are 200s.

### Limits to know

- **What we compare are the ratios.** The absolute values would be different on your hardware, or on a dedicated server.
- **Loopback (127.0.0.1)**: the measurement does not go through a real network. On a real network, large-file throughput is almost always limited by bandwidth, not by the server. The throughputs of several tens of GB/s on machine C are only possible on loopback.
- **No TLS** in these measurements.
- **Machine A**: the production omega-serv service of this machine was running in the background, without receiving traffic.
- **Machine C**: hybrid processor (Zen 5 and Zen 5c cores). The server got the 4 fast cores, the client the other 6.
- **Base configurations**: no server was optimized. An experienced administrator would no doubt get more out of each, omega-serv included.
- **Raw figures**: [`docs/benchmarks/`](../../benchmarks/) (one file per machine).

---

## 4. Performance: omega-serv versus nginx, lighttpd, Apache and Caddy

In all the tables, the reference value is **nginx with 2 processes** (= 1.00), measured in the same session on the same machine. On machines A and B, this is the configuration that uses all the cores given to the server.

### Small files (1 KB): requests per second

| Server | Machine A | Machine B | Machine C |
|---|---:|---:|---:|
| lighttpd, 2 processes | 33,138 (**1.52**) | 31,125 (**1.26**) | 378,590 (**1.53**) |
| nginx, 2 processes | 21,801 (1.00) | 24,705 (1.00) | 248,184 (1.00) |
| **omega-serv, native engine** | **15,222 (0.70)** | **16,542 (0.67)** | **285,213 (1.15 \*)** |
| omega-serv, native + WAF † | 11,990 (0.56) | 12,998 (0.53) | 264,484 (1.07 \*) |
| omega-serv, native + WAF, 2 security processes † | 11,746 (0.55) | 12,718 (0.52) | 253,527 (1.02 \*) |
| Apache, 2 processes | 9,192 (0.42) | 8,634 (0.35) | 188,335 (0.76) |
| Caddy, 2 processes | 5,749 (0.26) | 4,116 (0.17) | 52,897 (0.21) |
| omega-serv, Python engine, 2 processes | 2,354 (0.11) | 1,312 (0.05) | 19,911 (0.08) |
| omega-serv, Python + WAF, 2 processes | 1,901 (0.09) | 1,104 (0.04) | 15,783 (0.06) |
| omega-serv, Python engine | 1,507 (0.07) | 663 (0.03) | 10,553 (0.04) |
| omega-serv, Python + WAF | 1,561 (0.07) | 564 (0.02) | 8,365 (0.03) |

\* On machine C, the native engine uses its 4 cores, while nginx only uses 2 with 2 processes. The comparison with an equal number of cores is given below: the ratio there goes back to **0.67 to 0.71**, as on the other machines.

† Measured on November 4, after the WAF optimization, in a separate campaign with the same protocol. The ratio is computed with nginx (2 processes) of that campaign: 21 439, 24,424 and 248,127 req/s on small files, 11 545, 11,004 and 157,491 on 100 KB files. Before this optimization, the native engine with WAF served 3 495, 2,622 and 39,000 req/s (0.11 to 0.16 times nginx), because every request went through Python. Raw figures: `*-waf-natif-brut.txt` files.

With a single process, nginx does 0.52 to 0.73, lighttpd 0.81 to 1.43, Apache 0.33 to 0.74 and Caddy 0.09 to 0.17 (raw figures).

### p99 latency on small files

| Server | Machine A | Machine B | Machine C |
|---|---:|---:|---:|
| lighttpd, 2 processes | 4.4 ms | 4.1 ms | 0.2 ms |
| nginx, 2 processes | 4.9 ms | 5.2 ms | 0.2 ms |
| **omega-serv, native engine** | **6.1 ms** | **6.2 ms** | **0.3 ms** |
| omega-serv, native + WAF † | 7.2 ms | 6.7 ms | 0.3 ms |
| Apache, 2 processes | 18.8 ms | 20.6 ms | 0.8 ms |
| Caddy, 2 processes | 24.1 ms | 30.5 ms | 2.8 ms |
| omega-serv, Python engine, 2 processes | 22.6 ms | 28.1 ms | 3.3 ms |
| omega-serv, Python engine | 32.0 ms | 51.6 ms | 4.4 ms |

### Medium files (100 KB): requests per second

| Server | Machine A | Machine B | Machine C |
|---|---:|---:|---:|
| lighttpd, 2 processes | 13,561 (**1.08**) | 12,126 (**1.07**) | 197,905 (**1.26**) |
| nginx, 2 processes | 12,513 (1.00) | 11,303 (1.00) | 157,224 (1.00) |
| Apache, 2 processes | 6,939 (0.55) | 7,035 (0.62) | 153,265 (0.97) |
| Caddy, 2 processes | 5,059 (0.40) | 3,744 (0.33) | 22,094 (0.14) |
| **omega-serv, native engine** | **4,738 (0.38)** | **3,115 (0.28)** | **96,277 (0.61)** |
| omega-serv, native + WAF † | 4,229 (0.37) | 2,926 (0.27) | 98,185 (0.62) |
| omega-serv, Python engine, 2 processes | 1,741 (0.14) | 1,154 (0.10) | 18,806 (0.12) |
| omega-serv, Python engine | 1,329 (0.11) | 611 (0.05) | 9,805 (0.06) |

### Large file (5 MB): throughput

| Server | Machine A | Machine B | Machine C |
|---|---:|---:|---:|
| lighttpd, 2 processes | 2,440 MB/s (1.05) | 2,110 MB/s (0.99) | 28,011 MB/s (0.81) |
| nginx, 2 processes | 2,322 MB/s (1.00) | 2,124 MB/s (1.00) | 34,651 MB/s (1.00) |
| Apache, 2 processes | 2,355 MB/s (1.01) | 2,134 MB/s (1.00) | 41,153 MB/s (**1.19**) |
| **omega-serv, native engine** | **2,294 MB/s (0.99)** | **1,936 MB/s (0.91)** | **37,918 MB/s (1.09)** |
| Caddy, 2 processes | 2,205 MB/s (0.95) | 1,996 MB/s (0.94) | 3,811 MB/s (0.11) |
| omega-serv, Python engine, 2 processes | 2,145 MB/s (0.92) | 1,931 MB/s (0.91) | 25,829 MB/s (0.75) |
| omega-serv, Python engine | 1,686 MB/s (0.73) | 1,472 MB/s (0.69) | 14,227 MB/s (0.41) |

### Memory (PSS, all server processes): at rest → after the load

| Server | Machine A | Machine B | Machine C |
|---|---:|---:|---:|
| lighttpd | 1 → 1 MB | 1 → 1 MB | 1 → 1 MB |
| nginx | 4 → 5 MB | 5 → 5 MB | 4 → 4 MB |
| Apache | 4 → 7 MB | 4 → 7 MB | 4 → 7 MB |
| omega-serv, Python engine | 28 → 32 MB | 29 → 33 MB | 30 → 34 MB |
| **omega-serv, native engine** | **33 → 34 MB** | **34 → 35 MB** | **35 → 39 MB** |
| omega-serv, native + WAF † | 45 → 47 MB | 43 → 44 MB | 44 → 48 MB |
| omega-serv, Python engine, 2 processes | 40 → 50 MB | 43 → 51 MB | 42 → 51 MB |
| omega-serv, native + WAF, 2 security processes † | 45 → 47 MB | 43 → 44 MB | 55 → 57 MB |
| Caddy, 2 processes | 50 → 57 MB | 46 → 54 MB | 48 → 62 MB |

### With an equal number of cores: machine C with 4 processes

Separate campaign of November 3, same protocol, on machine C: each server gets 4 processes (or 4 cores for Caddy and the native engine). Reference: nginx with 4 processes. The native engine with WAF no longer appears here: measured before the WAF optimization, it has not yet been measured again with 4 processes.

| Server | 1 KB | 100 KB | 5 MB | Memory |
|---|---:|---:|---:|---:|
| lighttpd, 4 processes | 638,907 (**1.46**) | 312,402 (**1.21**) | 41,982 MB/s (0.93) | 1 → 2 MB |
| nginx, 4 processes | 438,496 (1.00) | 258,242 (1.00) | 45,162 MB/s (1.00) | 5 → 5 MB |
| **omega-serv, native engine** | **294,083 to 310,972 (0.67 to 0.71)** | **108,991 to 109,955 (0.42)** | **40,137 to 40,463 MB/s (0.89 to 0.90)** | **35 → 38 MB** |
| Apache, 4 processes | 200,592 (0.46) | 162,607 (0.63) | 39,664 MB/s (0.88) | 6 → 9 MB |
| Caddy, 4 cores | 97,085 (0.22) | 35,900 (0.14) | 5,998 MB/s (0.13) | 52 → 67 MB |
| omega-serv, Python engine, 4 processes | 37,697 (0.09) | 35,064 (0.14) | 37,123 MB/s (0.82) | 48 → 66 MB |

### Reading

- **The native engine changes omega-serv's place.**
  - On small files, it goes from 0.03-0.11 times nginx (Python engine) to about **0.7 times nginx**, whatever the machine.
  - It ranks ahead of Apache and Caddy, and behind nginx and lighttpd, which remain the fastest.
  - Its p99 latency is close to nginx's.
- **lighttpd is the fastest on small and medium files**, on all three machines, and the most memory-frugal. Its documentation nevertheless advises against `server.max-worker` (several processes), which we used to compare with an equal number of processes.
- **Medium files are the current weak point of the native engine**: 0.28 to 0.61 times nginx, behind Apache, and no better with more cores. This is an identified area for improvement.
- **On large files**, the servers come together, because it is the kernel that copies the data (`sendfile`). Caddy is the exception on machine C: we did not try to optimize its base configuration.
- **The WAF costs the native engine little, and it must be read fairly.**
  - The native engine searches the WAF rules itself: a request that none of them matches is served without going through Python. At the slightest doubt (match, non-ASCII text, source watched by Active Defense, authentication zone…), Python decides. With the WAF, the native engine thus keeps 78 to 95 % of its throughput on small files, and 93 to 99 % on 100 KB files. Before this optimization, its throughput was divided by 4 to 7.
  - Rate limiting is counted by the native engine: enabling it does not change these figures (machine A: 11,391 req/s with it, 11,330 without). If magnet is active, every request still goes through Python, and the cost goes back to what it was before.
  - omega-serv with WAF stays ahead of Apache and Caddy **without** WAF.
  - nginx, lighttpd, Apache and Caddy were measured **without** WAF. A WAF added to these servers (ModSecurity, Coraza) also has a cost, which we did not measure. The "with WAF" comparison is therefore not made on equal terms, and we do not claim that omega-serv would be faster than another server equipped with a WAF.
- **Several security processes no longer help ordinary traffic**: it no longer goes through them, and throughput stays the same with 2 processes (−2 to −4 %, within measurement noise). They only help when many requests go through Python (magnet active, attack): measured before the optimization, when every request went through Python, 2 security processes multiplied the throughput with WAF by 1.5 to 1.7 on 4 cores, but brought only 5 to 12 % on 2 cores.
- **The Python engine scales with processes** (×1.6 to ×2 with 2 processes, about ×3.5 with 4), but it stays at 5-11 % of nginx.
- **Memory**: omega-serv uses several tens of MB more than nginx, lighttpd or Apache, mainly because of Python, and as much as Caddy. With the native engine without WAF, memory stays almost stable during the load.
- **To put these figures in perspective**: even the slowest case, the Python engine with WAF on machine B (564 req/s), represents nearly 50 million requests per day. That is far beyond the needs of a personal site, an internal service or a lab. Speed is only really decisive for a high-traffic site.

---

## 5. The omega-serv versions: 1.0 → 2.0 → 2.5

The three versions were measured in the same session as §4, on all three machines, with the same protocol. In parentheses: the ratio with nginx (2 processes) of the same session. †: campaign of November 4 after the WAF optimization (see §4).

### Small files (1 KB): requests per second

| Version and mode | Machine A | Machine B | Machine C |
|---|---:|---:|---:|
| 1.0.0 | 1,547 (0.07) | 645 (0.03) | 8,870 (0.04) |
| 1.0.0 + WAF | 1,453 (0.07) | 561 (0.02) | 7,687 (0.03) |
| 2.0.0 | 1,740 (0.08) | 650 (0.03) | 10,245 (0.04) |
| 2.0.0 + WAF | 1,456 (0.07) | 565 (0.02) | 8,371 (0.03) |
| 2.0.0, 2 processes | 2,153 (0.10) | 1,277 (0.05) | 19,192 (0.08) |
| 2.0.0 + WAF, 2 processes | 1,775 (0.08) | 1,113 (0.05) | 15,351 (0.06) |
| 2.5, Python engine | 1,507 (0.07) | 663 (0.03) | 10,553 (0.04) |
| 2.5, Python engine + WAF | 1,561 (0.07) | 564 (0.02) | 8,365 (0.03) |
| 2.5, Python engine, 2 processes | 2,354 (0.11) | 1,312 (0.05) | 19,911 (0.08) |
| 2.5, Python engine + WAF, 2 processes | 1,901 (0.09) | 1,104 (0.04) | 15,783 (0.06) |
| **2.5, native engine** | **15,222 (0.70)** | **16,542 (0.67)** | **285,213 (1.15)** |
| **2.5, native engine + WAF †** | **11,990 (0.56)** | **12,998 (0.53)** | **264,484 (1.07)** |
| **2.5, native engine + WAF, 2 security processes †** | **11,746 (0.55)** | **12,718 (0.52)** | **253,527 (1.02)** |

### Medium files, large file and memory (1 process, without WAF)

| Version | 100 KB, req/s (A / B / C) | 5 MB, MB/s (A / B / C) | Memory at rest → after the load (A / B / C) |
|---|---|---|---|
| 1.0.0 | 1,071 / 563 / 7,625 | 578 / 549 / 3,640 | 21 → **98** / 22 → **98** / 23 → **73** MB |
| 2.0.0 | 1,570 / 603 / 9,469 | 1,665 / 1,470 / 14,058 | 26 → 30 / 27 → 31 / 28 → 32 MB |
| 2.5, Python engine | 1,329 / 611 / 9,805 | 1,686 / 1,472 / 14,227 | 28 → 32 / 29 → 33 / 30 → 34 MB |
| **2.5, native engine** | **4,738 / 3,115 / 96,277** | **2,294 / 1,936 / 37,918** | **33 → 34 / 34 → 35 / 35 → 39 MB** |

### Large simultaneous downloads

Test: 3 simultaneous downloads of a 300 MB file, while a small page is requested continuously. Two runs per version and per machine, with almost identical results. Memory here is the **RSS** of all the server's processes, as in the original test: it counts shared memory several times, which gives higher values than the PSS of the other tables.

| Version | Peak memory | Small page, worst case: A / B / C |
|---|---:|---|
| 1.0.0 | **1,833 to 1,836 MB** | **1.4 to 1.9 s** / **1.4 to 1.7 s** / 0.16 s |
| 2.0.0 | 39 to 42 MB | 3 ms / 4 to 6 ms / 1 ms |
| 2.5, Python engine | 41 to 44 MB | 2 ms / 4 ms / 1 ms |
| 2.5, native engine | 49 to 55 MB | 1 to 2 ms / 2 to 4 ms / less than 1 ms |

### Cost of active defense (1.0 → 2.0)

Measurement of October 26, 2026 on machine A, not repeated since: cost of one threat observation by Active Defense, for each suspicious request, measured on disk (ext4) over 2,000 observations.

| Measurement | 1.0.0 | 2.0.0 |
|---|---:|---:|
| Median | 2.84 ms | 0.23 ms |
| p99 | 11.6 ms | 2.3 ms |
| Maximum | 18 to 20 ms | 37 to 46 ms |

The median is divided by 12. The maximum, on the other hand, is higher in 2.0: a few isolated peaks, linked to the periodic writing of the SQLite journal to disk.

### Reading

- **From 1.0 to 2.0**, the progress is on memory and large files, not on the speed of small pages:
  - memory after the load goes from 73-98 MB to 30-32 MB;
  - during large downloads, it goes from more than 1.8 GB to about 40 MB, and the server stays responsive (a few milliseconds instead of nearly 2 seconds);
  - large-file throughput is multiplied by 2.7 to 3.9;
  - 2.0 adds several processes, which increase small-page throughput by 25 % to almost 100 % depending on the machine.
  1.0 loaded each file entirely into memory before sending it. 2.0 sends it in blocks, or hands it to the kernel.
- **From 2.0 to 2.5, the Python engine does not change speed**: the gaps stay under 4 % on machines B and C, and within the measurement noise of machine A (−13 % to +9 %), the most sensitive to background load. All the gain of 2.5 comes from the **native engine**: about ×10 to ×27 on small files compared with the Python engine, and latency divided by 5 to 15.
- **The native engine uses about 5 MB more** at rest than the Python engine (PSS): that is the price of the second program. With the WAF, it uses about 8 MB more still: the rules loaded into the native engine.

### What to know about the native engine

- It is **optional**: the Python engine remains the default engine, and the fallback engine.
- It serves static content, redirects, rewrites, aliases, the cache, error pages, security headers and TLS itself.
- It searches the WAF rules itself and serves on its own a request that none of them matches. Any other request (WAF match or doubt, Active Defense, authentication) is decided by Python, with exactly the same checks and the same logs. An adjustable check still submits one clean request in N to Python, to verify that both give the same verdict.
- Directory listing and internal pages are requested from Python; the reverse proxy, FastCGI, file upload and WebSocket are handed to it for the whole connection. These features therefore keep the speed of the Python engine.
- With direct TLS, the reverse proxy, FastCGI and file upload are not supported by the native engine: the Python engine then serves, and the interface says so.
- It requires glibc 2.38 or newer and OpenSSL 3. If it does not start, the installation recompiles it on the spot, and failing that omega-serv stays on the Python engine.

---

## 6. Feature comparison

Legend:
- ✅ built in;
- 🧩 official module of the project, to enable or install;
- 🔌 third-party module or plugin;
- ⚙️ through an external tool;
- ❌ absent.

"Commercial" means a feature reserved for the paid edition.

### HTTP service

| Feature | nginx | lighttpd | Caddy | Apache | Traefik | omega-serv 2.5 |
|---|---|---|---|---|---|---|
| Server language | C | C | Go | C | Go | Python, with an optional native C++ engine |
| Serve static files | ✅ | ✅ | ✅ | ✅ | ❌ (proxy only) | ✅ |
| ETag / 304 / Range | ✅ | ✅ | ✅ | ✅ | — | ✅ |
| Pre-compressed `.gz` / `.br` files | ✅ `gzip_static` (`.br`: 🔌) | 🔌 Lua script (mod_magnet) | ✅ `precompressed` | 🧩 mod_rewrite recipe | — | ✅ |
| On-the-fly compression | ✅ | ✅ mod_deflate | ✅ | 🧩 mod_deflate | ✅ middleware | ❌ |
| HTTP/2 | ✅ | ✅ | ✅ | 🧩 mod_http2 | ✅ | ❌ |
| HTTP/3 (QUIC) | ✅ | ❌ | ✅ | ❌ | ✅ | ❌ |
| PHP via FastCGI | ✅ | ✅ | ✅ | ✅ | ❌ | ✅ |
| Several processes or cores | ✅ workers | ⚠️ `max-worker`, advised against by the documentation | ✅ (Go, all cores) | ✅ MPM | ✅ (Go) | ✅ `server.workers`; native engine: all cores |

### Reverse proxy

| Feature | nginx | lighttpd | Caddy | Apache | Traefik | omega-serv 2.5 |
|---|---|---|---|---|---|---|
| Load balancing | ✅ round robin, least connections, hash | ✅ fair, round-robin, hash, sticky | ✅ a dozen strategies | 🧩 mod_proxy_balancer | ✅ wrr, p2c, hrw, least-time | ✅ 7 strategies, including real load |
| Passive health (set aside a failed server) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Active health (periodic probe) | Commercial (NGINX Plus) | ❌ | ✅ | 🧩 mod_proxy_hcheck | ✅ | ✅ |
| Response cache | ✅ `proxy_cache` | ❌ | 🔌 | 🧩 mod_cache | Commercial | ✅ |
| WebSocket | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Service discovery (Docker, Kubernetes) | 🔌 | ❌ | 🔌 | ❌ | ✅ (core of the project) | ❌ |

### TLS

| Feature | nginx | lighttpd | Caddy | Apache | Traefik | omega-serv 2.5 |
|---|---|---|---|---|---|---|
| Automatic certificates (ACME, Let's Encrypt) | 🧩 `ngx_http_acme_module` | ⚙️ Certbot | ✅ by default | 🧩 mod_md | ✅ | ⚙️ Certbot, with a built-in wizard and scheduled renewal |
| Local CA | ❌ | ❌ | ✅ internal CA (automatic issuance) | ❌ | ❌ | ✅ generation, CSR signing, revocation |

### Security

| Feature | nginx | lighttpd | Caddy | Apache | Traefik | omega-serv 2.5 |
|---|---|---|---|---|---|---|
| Per-client rate limit | ✅ `limit_req` | ⚠️ mod_evasive (simultaneous connections only) | 🔌 caddy-ratelimit | 🔌 mod_evasive, mod_qos | ✅ middleware | ✅ |
| Limit shared between processes | ✅ shared memory zone | ❌ counted per process | — (single process) | depends on the module | 1 instance; several with Redis | ✅ shared memory |
| WAF (SQLi/XSS signatures, scanners…) | 🔌 ModSecurity, Commercial (App Protect) | ❌ (Lua scripts to write) | 🔌 Coraza | 🔌 ModSecurity | 🔌 plugins | ✅ built in |
| Blocklist with expiry, recidivism | ⚙️ fail2ban | ⚙️ fail2ban | ⚙️ fail2ban | ⚙️ fail2ban | ⚙️ | ✅ built in |
| Decoys, war mode, incidents, IoC export | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ Active Defense |
| Graduated bans over time | ⚙️ fail2ban | ⚙️ fail2ban | ⚙️ fail2ban | ⚙️ fail2ban | ⚙️ | ✅ RIPOSTE |
| Security audit of the configuration | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ `audit security` |
| Observation mode (log without blocking) | depends on the module | — | depends on the plugin | ✅ ModSecurity `DetectionOnly` | depends on the plugin | ✅ |

Graduated bans: longer and longer bans for addresses that come back, over weeks, locally or at network level. fail2ban gets them with its `bantime.increment` option; RIPOSTE adds policies measured on the logs and simulated before activation, lifting an action, and an emergency stop.

### Extensibility

| Feature | nginx | lighttpd | Caddy | Apache | Traefik | omega-serv 2.5 |
|---|---|---|---|---|---|---|
| Scripting language | 🧩 njs (JavaScript); 🔌 Lua (OpenResty) | ✅ Lua (mod_magnet) | Go modules (recompilation) | 🧩 mod_lua | Go or WebAssembly plugins | 🔌 import of mod_magnet scripts (`magnet` option) |
| Module ecosystem | very large | targeted | large | very large | large | none: everything is built in |

---

## 7. Administration and ergonomics

| Server | Main administration mode | Interface | Reload without interruption |
|---|---|---|---|
| nginx | configuration files | none (dashboard: NGINX Plus, commercial) | ✅ `nginx -s reload` |
| lighttpd | configuration file | none (mod_status read-only) | ✅ graceful restart |
| Caddy | Caddyfile or JSON | administration REST API | ✅ via the API |
| Apache | configuration files and `.htaccess` | none (mod_status read-only) | ✅ `graceful` |
| Traefik | container labels, files or Kubernetes | web dashboard (read-only) | ✅ dynamic configuration |
| omega-serv | terminal interface (TUI) and command line (CLI); the JSON file does not have to be edited | **complete TUI with keyboard and mouse, 17 languages, built-in help** | ✅ for most settings; restart announced for the port, TLS, the engine and the number of processes |

In practice, with omega-serv, the configuration, security, logs, system services, backups and instances are managed from a single interface. Every setting is explained and checked before being written. With the other servers, you edit text files, then call on separate tools (Certbot, fail2ban, logrotate, ModSecurity, a monitoring tool…).

In return, the "configuration file" approach of nginx, Apache and Caddy automates very well (Ansible, containers, version control). omega-serv has a scriptable CLI, but its automation ecosystem remains limited.

---

## 8. What omega-serv brings in addition

This section only keeps what none of the compared servers provides as is, without a third-party module or an external tool.

1. **Complete administration in a terminal interface.**
   - The interface covers the whole server: the site, security, logs, services, backups and instances.
   - It is used with the keyboard and the mouse, on a server without a graphical display, even over SSH.
   - It is available in 17 languages and explains every setting.
   - The other servers have no administration interface (nginx, lighttpd, Apache), or only an API (Caddy) or a read-only dashboard (Traefik).
2. **Built-in active security, with no modules to assemble.**
   - The WAF includes signatures, editable path lists, recidivism, a blocklist with expiry, reputation and an observation mode.
   - Active Defense adds decoys, a war mode, incident tracking, export of indicators of compromise and a dry-run simulation.
   - RIPOSTE responds over time: it remembers the addresses that come back and applies graduated responses to them, longer and longer bans (1 h, 6 h, 24 h, 7 days by default), local in the blocklist or at network level through fail2ban (omega-jail), or an extended decoy. Each policy can be measured on the real logs and simulated before being activated; each action stays visible and can be lifted, with an emergency stop.
   - Elsewhere, these features require assembling ModSecurity or Coraza, rule sets and fail2ban.
3. **Exact security limits with several processes.**
   - With several processes, the WAF rate limit and recidivism are shared in memory between them. An attacker therefore cannot multiply their limit by the number of processes.
   - lighttpd documents the opposite case: with `server.max-worker`, `mod_evasive` and `mod_status` count separately in each process.
   - nginx also shares its counters (`limit_req` zones), but it has no built-in WAF.
4. **Two engines, one behavior.** The native engine and the Python engine produce the same responses and the same logs, checked automatically on a comparison bench. The tools that read the logs (fail2ban, for example) see no difference.
5. **Import of lighttpd mod_magnet scripts.**
   - A Lua protection script already written for lighttpd is imported without being rewritten.
   - It adds to the built-in protection without ever being able to weaken it, and its compatibility is checked before activation.
6. **Management of several instances.**
   - A registry lists all the instances, and the interface switches from one to another.
   - It can also uninstall an instance completely.
7. **A security audit of the configuration**: the `audit security` command is informative, never blocks and returns exit codes usable in a script.
8. **Remote log sources.**
   - The interface fetches another server's log over SSH, on demand, without a stored password.
   - It can read it with lnav, merging it with the local logs.
9. **HTTP hardening that cannot be disabled**, active from installation, whatever the profile and the engine:
   - strict validation of the Host header;
   - rejection of Content-Length / Transfer-Encoding ambiguities;
   - security headers and CSP on the site's responses, including its error pages;
   - safe reading of X-Forwarded-For;
   - refusal to start as root.

---

## 9. What the others do better

- **Throughput**: lighttpd and nginx remain the fastest on small and medium files, on all three machines. Even with the native engine, omega-serv serves about 0.7 times nginx and 0.5 times lighttpd on small files, and 0.3 to 0.6 times nginx on 100 KB files. For a high-traffic site, a public API or a CDN, they are the ones to choose.
- **Medium files**: Apache serves 100 KB files faster than the omega-serv native engine, on all three machines.
- **Memory**: lighttpd (1 MB), nginx (4 to 5 MB) and Apache (4 to 9 MB) suit very constrained machines (embedded, small containers). omega-serv needs 30 to 65.
- **Cost of security**: the WAF still has a cost. With the native engine, it takes 5 to 22 % of the throughput on small files, rate limiting included: omega-serv with WAF serves 0.53 to 0.56 times nginx without WAF on machines A and B. A suspicious or doubtful request (rule match, non-ASCII text, source watched by Active Defense) always goes through Python, and it is served at the speed of the Python engine. With magnet active, every request goes through Python, and the WAF then divides the native engine's throughput by 4 to 7, as before the optimization.
- **Protocols**: HTTP/2 in all the others, HTTP/3 in nginx, Caddy and Traefik. omega-serv only speaks HTTP/1.1.
- **Automatic HTTPS**: Caddy and Traefik build it in by default, and nginx (`ngx_http_acme_module`) and Apache (`mod_md`) with an official module. omega-serv delegates to Certbot, with a wizard and scheduled renewal.
- **Containerized environments**: Traefik's automatic service discovery (Docker, Kubernetes) has no equivalent in omega-serv.
- **Ecosystem and maturity**: nginx and Apache offer thousands of modules, guides and integrations, and decades of production use. Caddy offers a module system in Go. omega-serv is a young project, maintained by a single person, and its native engine is recent.
- **On-the-fly compression**: omega-serv only serves files that are already compressed.

---

## 10. Which server for which use

| Need | Recommended choice |
|---|---|
| High-traffic site, public API, CDN, maximum throughput | **nginx** or **lighttpd** |
| Very constrained machine, embedded, static files | **lighttpd** |
| Quick start with automatic HTTPS, short configuration | **Caddy** |
| Legacy PHP application, `.htaccess`, shared hosting | **Apache** |
| Docker, Kubernetes, microservices | **Traefik** |
| Small or medium site, internal service, lab, VPN, administration without editing files | **omega-serv** (native engine if possible) |
| Exposed server where you want to see and control security (WAF, graduated bans, decoys) from a single interface | **omega-serv** |
| Internal reverse proxy with balancing, health and cache, driven from an interface | **omega-serv** |
| Learning HTTP hardening and active defense | **omega-serv** |

These tools can also be combined. For example:
- nginx or Traefik in front on the Internet, with omega-serv behind for an internal service, its security and its administration;
- omega-serv as an internal reverse proxy in front of several application servers.

---

## 11. Reproducing the measurements

The tools are shipped in the repository, under `tools/bench/`. You need nginx, lighttpd, Apache, Caddy and oha installed, the omega-serv development environment (`.venv`), and, for the native engine, the binary compiled in `native/omega-http-core/build-release`.

```sh
# 1. prepare a measurement folder (test files, configurations, omega-serv 1.0, 2.0 and current version)
tools/bench/compare/setup.sh /path/to/bench omega-serv-1.0.0.tar.gz omega-serv-2.0.0.tar.gz

# 2. the 21 configurations, 3 interleaved repetitions (40 to 60 minutes)
#    SRV_CPUS / CLI_CPUS: server and client cores (lscpu -e gives the topology)
SRV_CPUS=0,1 CLI_CPUS=2,3 tools/bench/compare/campaign.sh /path/to/bench > results.txt

# 3. medians
python3 tools/bench/compare/summarize.py results.txt

# another list of configurations, for example 4 processes
CONFIGS="nginx-4 lighttpd-4 caddy-4 apache-4 omega-v2-1-0-native omega-v2-4-1-native" \
  tools/bench/compare/campaign.sh /path/to/bench > results-4.txt

# large downloads (memory and responsiveness): current version, Python engine then native, then 1.0
.venv/bin/python tools/bench/bigfile.py
BENCH_ENGINE=native .venv/bin/python tools/bench/bigfile.py
BENCH_SRC=/path/to/bench/v1-archive/omega-serv/src \
BENCH_EXTRA_PATH=/path/to/bench/v1-archive/omega-serv/vendor/omega-lib/src \
  .venv/bin/python tools/bench/bigfile.py

# measure any other server already running, without oha
python3 tools/bench/bench_any.py --make-files /srv/test-webroot
python3 tools/bench/bench_any.py --port 8080
```

Configuration names: `nginx-N`, `lighttpd-N`, `apache-N`, `caddy-N` (N processes, or N cores for Caddy); `omega-vX-N-W` for omega-serv (version `v1`, `v20` or `v2` for the current version, N processes, W = 0 without WAF or 1 with), followed by `-native` for the native engine.

To publish your own results, give the machine, the versions, the distribution of cores and the three repetitions.

---

## 12. Sources

Features of the other servers, according to their official documentation (consulted on October 26, 2026).

**nginx**
- [`limit_req` rate limit (shared memory zone)](https://nginx.org/en/docs/http/ngx_http_limit_req_module.html)
- [`gzip_static` pre-compressed files](https://nginx.org/en/docs/http/ngx_http_gzip_static_module.html)
- [Official ACME module `ngx_http_acme_module`](https://nginx.org/en/docs/http/ngx_http_acme_module.html)
- [Load balancing (`upstream`)](https://nginx.org/en/docs/http/ngx_http_upstream_module.html)
- [HTTP/3](https://nginx.org/en/docs/http/ngx_http_v3_module.html)
- [ModSecurity connector for nginx](https://github.com/owasp-modsecurity/ModSecurity-nginx)

**lighttpd**
- [`server.max-worker`: advised against, per-process counters for mod_status and mod_evasive](https://redmine.lighttpd.net/projects/lighttpd/wiki/Server_max-workerDetails)
- [mod_magnet (Lua scripts)](https://redmine.lighttpd.net/projects/lighttpd/wiki/Docs_ModMagnet)
- [mod_deflate (compression, cache)](https://redmine.lighttpd.net/projects/lighttpd/wiki/Mod_deflate)
- [mod_proxy (balancing, passive health, WebSocket)](https://redmine.lighttpd.net/projects/lighttpd/wiki/Docs_ModProxy)
- [mod_evasive (simultaneous connections per address)](https://redmine.lighttpd.net/projects/lighttpd/wiki/Docs_ModEvasive)

**Caddy**
- [Automatic HTTPS](https://caddyserver.com/docs/automatic-https)
- [`file_server` and `precompressed`](https://caddyserver.com/docs/caddyfile/directives/file_server)
- [`reverse_proxy` (strategies, active and passive health)](https://caddyserver.com/docs/caddyfile/directives/reverse_proxy)
- [Administration API](https://caddyserver.com/docs/api)
- [caddy-ratelimit rate limit plugin](https://github.com/mholt/caddy-ratelimit)
- [Coraza WAF for Caddy](https://github.com/corazawaf/coraza-caddy)
- [caddy-docker-proxy](https://github.com/lucaslorentz/caddy-docker-proxy)

**Apache HTTP Server**
- [MPM event](https://httpd.apache.org/docs/2.4/mod/event.html)
- [mod_md (ACME)](https://httpd.apache.org/docs/2.4/mod/mod_md.html)
- [mod_proxy_balancer](https://httpd.apache.org/docs/2.4/mod/mod_proxy_balancer.html)
- [mod_proxy_hcheck](https://httpd.apache.org/docs/2.4/mod/mod_proxy_hcheck.html)
- [mod_http2](https://httpd.apache.org/docs/2.4/mod/mod_http2.html)
- [mod_deflate, pre-compressed content](https://httpd.apache.org/docs/2.4/mod/mod_deflate.html)
- [ModSecurity](https://github.com/owasp-modsecurity/ModSecurity)

**Traefik**
- [`ratelimit` middleware (in memory per instance, Redis as an option)](https://doc.traefik.io/traefik/reference/routing-configuration/http/middlewares/ratelimit/)
- [ACME](https://doc.traefik.io/traefik/https/acme/)
- [Providers (Docker, Kubernetes…)](https://doc.traefik.io/traefik/providers/overview/)

**fail2ban**
- [`jail.conf`: `bantime.increment`, `bantime.factor`, `bantime.multipliers`, `bantime.maxtime` (longer bans for repeat offenders)](https://github.com/fail2ban/fail2ban/blob/master/config/jail.conf) (consulted on November 4, 2026)

**Measurement tool**
- [oha](https://github.com/hatoo/oha)

---

*Comparison by kraynux for omega-serv 2.5: measurements of November 3 and 4, 2026 on three machines (active defense: October 26, 2026). For any capacity decision, measure on your own hardware with the tools provided.*
