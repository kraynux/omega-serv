# omega-serv versus the web servers on the market — graphical version

**omega-serv versus nginx · lighttpd · Apache · Caddy · Traefik — measurements on three machines (Nov. 2026).**

🌐 [Français](../../comparatif-server-web-graphique.md) · **English** · [Español](../es/comparatif-server-web-graphique.md) · [Português (Brasil)](../pt-BR/comparatif-server-web-graphique.md) · [Italiano](../it/comparatif-server-web-graphique.md) · [Deutsch](../de/comparatif-server-web-graphique.md) · [Nederlands](../nl/comparatif-server-web-graphique.md) · [Polski](../pl/comparatif-server-web-graphique.md) · [Русский](../ru/comparatif-server-web-graphique.md) · [中文](../zh-CN/comparatif-server-web-graphique.md) · [Tiếng Việt](../vi/comparatif-server-web-graphique.md) · [ไทย](../th/comparatif-server-web-graphique.md) · [Bahasa Indonesia](../id/comparatif-server-web-graphique.md) · [日本語](../ja/comparatif-server-web-graphique.md) · [한국어](../ko/comparatif-server-web-graphique.md) · [हिन्दी](../hi/comparatif-server-web-graphique.md) · [العربية](../ar/comparatif-server-web-graphique.md)

> **How to read:** the longer the bar, the faster the server. The reference is **nginx = 1.00**.

## Color legend

<!-- 🖼️ IMAGE : legende-couleurs -->
<div align="center">
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/translation/en/omega-serv/stats-1.png" alt="Color legend" width="1024">
</div>

---

## 📊 1 KB files — throughput (requests/s)

Machines A (i5 2010), B (Celeron 2016) and C (Ryzen 2024). Bars are normalized against nginx (1.00) on the same machine.

<!-- 🖼️ IMAGE : 1ko-banner — 3 colonnes côte à côte (Machine A · 2 cœurs | Machine B · 4 cœurs | Machine C · 10 cœurs), largeur totale -->
<div align="center">
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/translation/en/omega-serv/stats-2.png" alt="1 KB files — machines A, B and C" width="1024">
</div>

> \* Machine C: the native engine uses 4 cores, nginx 2 processes (2 cores). With equal cores, the ratio falls back to ~0.70.
---

## 📦 Medium files (100 KB) — normal web mode

Here, Apache surprises: it often outperforms omega-serv's native engine. lighttpd remains the fastest. Reference: nginx = 1.00.

<!-- 🖼️ IMAGE : 100ko-banner.png — 3 colonnes côte à côte (A | B | C), largeur totale -->
<div align="center">
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/translation/en/omega-serv/stats-3.png" alt="100 KB files — machines A, B and C" width="1024">
</div>

---

## 💿 Large files (5 MB) — normal web mode

On large files the servers converge: it is the kernel that copies the data (sendfile). Caddy is the exception on machine C. Throughput in MB/s.

<!-- 🖼️ IMAGE : 5mo-banner.png — 3 colonnes côte à côte (A | B | C), largeur totale -->
<div align="center">
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/translation/en/omega-serv/stats-4.png" alt="5 MB files — machines A, B and C" width="1024">
</div>

---

## 🔄 Reverse proxy — small responses (1 KB)

Each proxy relays to an nginx backend. Reference: nginx = 1.00. Machine C: 4 processes.

<!-- 🖼️ IMAGE : proxy-1ko-banner.png — 3 colonnes côte à côte (A | B | C), largeur totale -->
<div align="center">
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/translation/en/omega-serv/stats-5.png" alt="Proxy 1 KB — machines A, B and C" width="1024">
</div>

---

## 🔄 Reverse proxy — 100 KB responses

On medium responses, native omega-serv matches or exceeds nginx.

<!-- 🖼️ IMAGE : proxy-100ko-banner.png — 3 colonnes côte à côte (A | B | C), largeur totale -->
<div align="center">
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/translation/en/omega-serv/stats-6.png" alt="Proxy 100 KB — machines A, B and C" width="1024">
</div>

---

## 💾 Memory (PSS) — idle → after load

The shorter the bar, the more frugal the server. lighttpd, nginx and Apache are the most frugal; omega-serv 3.0.0 (remeasured on 19 November) follows, with 10 to 16 MB for the native engine.

<!-- 🖼️ IMAGE : memoire-banner.png — 3 colonnes côte à côte de jauges (A | B | C), largeur totale -->
<div align="center">
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/translation/en/omega-serv/stats-7.png" alt="Memory — machines A, B and C" width="1024">
</div>

---

## 🏆 Normal web ranking — who is the fastest?

Summary of the three machines serving static files.

<!-- 🖼️ IMAGE : classement-web.png -->
<!-- Contenu : 1. 🥇 lighttpd — meilleur en petits & moyens fichiers · 2. 🥈 nginx — référence, excellent partout · 3. 🥉 omega-serv natif — très bon, 2ᵉ en reverse proxy · 4. Apache — bon, robuste, écosystème · 5. Caddy — simple, HTTPS auto · 6. omega-serv Python — moteur de repli -->
<div align="center">
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/translation/en/omega-serv/stats-8.png" alt="Normal web ranking" width="1024">
</div>

---

## 🔄 Reverse proxy ranking — who is the best?

nginx remains the reference; native omega-serv is its closest runner-up, far ahead of the others.

<!-- 🖼️ IMAGE : classement-proxy.png -->
<!-- Contenu : 1. 🥇 nginx · 2. 🥈 omega-serv natif — 0,82 à 0,91× nginx en 1 Ko · 3. 🥉 omega-serv + WAF — toujours devant lighttpd/Apache · 4. lighttpd — 0,53 à 0,61× · 5. Apache — 0,50 à 0,59× · 6. Traefik — 0,29 à 0,35× · 7. Caddy — 0,23 à 0,32× · 8. omega-serv Python — moteur de repli -->
<div align="center">
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/translation/en/omega-serv/stats-9.png" alt="Reverse proxy ranking" width="1024">
</div>

---

## 🆚 Head to head — web & reverse proxy rankings side by side

Two uses, two rankings. A server can shine in one and disappoint in the other: Apache surprises at relaying, Caddy disappoints everywhere except for its simplicity.

<!-- 🖼️ IMAGE : face-a-face.png — 2 colonnes côte à côte (web | proxy), largeur totale -->
<div align="center">
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/translation/en/omega-serv/stats-10.png" alt="Head to head web vs reverse proxy" width="1024">
</div>

### Cross summary

| Server | Standing |
|---|---|
| 🟢 **omega-serv native** | The most versatile: 3rd in web, **2nd as a reverse proxy**. The only server with a built-in WAF that stays ahead of lighttpd and Apache when relaying. The best compromise for a single tool covering both uses, with security on top. |
| 🔵 **nginx** | The most consistent: 2nd in web, **1st as a reverse proxy**. Always in the upper part of the ranking, with no notable weak point. The default choice when there is no particular requirement. |
| 🟢 **lighttpd** | The static sprinter: **1st in web**, but 4th at relaying. The best choice for pure static content, it yields to omega-serv or nginx as soon as reverse proxying is added. |
| 🔴 **Apache** | The counter-example: 4th in web, 5th at relaying. On large files, it even surprises nginx (machine C). Neither the fastest nor the lightest: its strength remains the PHP ecosystem. |
| 🟠 **Caddy** | Simplicity before speed: 5th in web, **7th at relaying**. Not built for throughput: automatic HTTPS and short configuration. Best kept for small projects. |
| 🟣 **Traefik** | Outside the web category: not a file server, 6th at relaying. Its home ground remains Docker and Kubernetes, not raw performance. |

---

## 📋 Full summary table — ratios vs nginx (1.00)

Overview of **all** the metrics: normal web mode (1 KB, 100 KB, 5 MB) and reverse proxy (1 KB, 100 KB), plus memory. The closer the value is to 1.00 or above, the better.

| Server | Web 1 KB (A/B/C) | Web 100 KB (A/B/C) | Web 5 MB (A/B/C) | Proxy 1 KB (A/B/C) | Proxy 100 KB (A/B/C) | Memory (A/B/C) |
|---|---|---|---|---|---|---|
| **lighttpd** | 1.52 / 1.26 / 1.53 | 1.08 / 1.07 / 1.26 | 1.05 / 0.99 / 0.81 | 0.61 / 0.56 / 0.53 | 0.74 / 0.62 / 0.96 | 1 MB |
| **nginx** | 1.00 / 1.00 / 1.00 | 1.00 / 1.00 / 1.00 | 1.00 / 1.00 / 1.00 | 1.00 / 1.00 / 1.00 | 1.00 / 1.00 / 1.00 | 4–5 MB |
| **omega-serv (native)** | **0.70 / 0.67 / 1.15\*** | **0.38 / 0.28 / 0.61** | **0.99 / 0.91 / 1.09** | **0.85 / 0.91 / 0.82** | **1.11 / 0.97 / 1.43** | 10–16 MB |
| **omega-serv + WAF** | 0.56 / 0.53 / 1.07\* | 0.37 / 0.27 / 0.62 | — | 0.81 / 0.89 / 0.77 | 1.10 / 0.93 / 1.30 | 28–33 MB |
| **Apache** | 0.42 / 0.35 / 0.76 | 0.55 / 0.62 / 0.97 | 1.01 / 1.00 / 1.19 | 0.59 / 0.53 / 0.50 | 0.62 / 0.65 / 0.71 | 4–9 MB |
| **Caddy** | 0.26 / 0.17 / 0.21 | 0.40 / 0.33 / 0.14 | 0.95 / 0.94 / 0.11 | 0.32 / 0.28 / 0.23 | 0.60 / 0.54 / 0.59 | 46–67 MB |
| **Traefik** | — | — | — | 0.35 / 0.35 / 0.29 | 0.64 / 0.60 / 0.70 | 93–131 MB |
| **omega-serv (Python)** | 0.11 / 0.05 / 0.08 | 0.14 / 0.10 / 0.12 | 0.92 / 0.91 / 0.75 | 0.09 / 0.08 / 0.07 | 0.21 / 0.19 / — | 20–48 MB |

> \* Machine C: 4 cores for the native engine vs 2 for nginx; with equal cores, ratio ~0.67–0.71.
> The three values per cell correspond to machines **A / B / C**. "—": not measured or not applicable.

---

## ⚖️ Strengths and weaknesses — all servers

Each server has its strengths and its limits. Here is the complete view, without favoritism.

### 🟢 omega-serv (native)

**Strengths**
- ✅ Complete administration in the terminal (TUI, 17 languages)
- ✅ Built-in WAF + Active Defense + RIPOSTE
- ✅ Native C++ engine: ~0.7× nginx on static files
- ✅ 2nd as a reverse proxy behind nginx
- ✅ Limits shared between processes (exact security)
- ✅ Import of lighttpd mod_magnet scripts
- ✅ Multi-instance management
- ✅ Web administration


**Weaknesses**
- ❌ No HTTP/2 or HTTP/3
- ❌ No on-the-fly compression
- ❌ No Docker/Kubernetes discovery
- ❌ ACME via Certbot (not natively integrated)
- ❌ 100 KB files: 0.3–0.6× nginx
- ❌ Memory 10–55 MB depending on the mode (vs 1–5 MB nginx/lighttpd)
- ❌ Young ecosystem, maintained by one person

---

### 🔵 nginx

**Strengths**
- ✅ Reference for performance and stability
- ✅ HTTP/2, HTTP/3, compression
- ✅ Huge ecosystem (modules, docs, community)
- ✅ Very frugal in memory (4–5 MB)
- ✅ Excellent reverse proxy
- ✅ Official ACME module
- ✅ Mature, proven configuration

**Weaknesses**
- ❌ Verbose configuration, its own syntax to learn
- ❌ No built-in WAF (requires ModSecurity or equivalent)
- ❌ No native administration interface
- ❌ Configuration reload sometimes delicate in production
- ❌ Limited open source version (some features in paid Nginx Plus)
- ❌ No native Docker/Kubernetes discovery (via templates)

---

### 🟢 lighttpd

**Strengths**
- ✅ The fastest on small/medium files
- ✅ The most frugal in memory (1 MB)
- ✅ Lightweight, suited to constrained systems
- ✅ Good reverse proxy
- ✅ Simple, readable configuration

**Weaknesses**
- ❌ No HTTP/3 (HTTP/2 partial depending on build)
- ❌ Only 4th as a reverse proxy (0.53–0.61× nginx)
- ❌ Smaller ecosystem than nginx/Apache
- ❌ No built-in WAF
- ❌ No Docker/Kubernetes discovery
- ❌ Development less active than in the past
- ❌ Weak on large files (0.81× nginx on machine C)

---

### 🔴 Apache

**Strengths**
- ✅ Huge historical ecosystem (modules, `.htaccess`, PHP)
- ✅ Robust and proven for decades
- ✅ Excellent on large files (outperforms nginx on machine C)
- ✅ `.htaccess` support without restart
- ✅ Compression, HTTP/2, ACME available
- ✅ Abundant documentation

**Weaknesses**
- ❌ Slow on small files (0.35–0.42× nginx)
- ❌ Memory-hungry in prefork mode (4–9 MB, climbs quickly under load)
- ❌ Process model less efficient than event-driven
- ❌ Verbose configuration
- ❌ 5th as a reverse proxy (0.50–0.59× nginx)
- ❌ No built-in WAF (ModSecurity as a separate module)
- ❌ Historically larger attack surface

---

### 🟠 Caddy

**Strengths**
- ✅ Automatic HTTPS (built-in ACME, zero config)
- ✅ Very short, readable configuration (Caddyfile)
- ✅ Native HTTP/2 and HTTP/3
- ✅ Single binary, simple deployment
- ✅ Decent reverse proxy on medium responses

**Weaknesses**
- ❌ Slow in raw throughput (5th in web, 7th at relaying)
- ❌ High memory (46–67 MB)
- ❌ Very weak on large files on machine C (0.11× nginx)
- ❌ No built-in WAF
- ❌ Younger ecosystem than nginx/Apache
- ❌ Poorly suited to very high throughput

---

### 🟣 Traefik

**Strengths**
- ✅ Automatic Docker/Kubernetes discovery
- ✅ Ideal in a containerized environment
- ✅ Automatic HTTPS (built-in ACME)
- ✅ Dynamic configuration without restart
- ✅ Good as a reverse proxy on medium responses (0.60–0.70× nginx)

**Weaknesses**
- ❌ Not a file server (absent from the web ranking)
- ❌ 6th as a reverse proxy (0.29–0.35× nginx at 1 KB)
- ❌ Very high memory (93–131 MB)
- ❌ Configuration complexity outside container contexts
- ❌ No built-in WAF
- ❌ Oversized for a simple static site

---

## 🎯 Which server for which use?

| Use | Recommended server | Reason |
|---|---|---|
| High-traffic site | **nginx** or **lighttpd** | Maximum throughput, HTTP/2-3 |
| Constrained machine / embedded | **lighttpd** | 1 MB of memory, the fastest and the least demanding |
| Simple automatic HTTPS | **Caddy** | Automatic certificates, short configuration |
| Docker / Kubernetes | **Traefik** | Service discovery |
| PHP application / .htaccess | **Apache** | Historical ecosystem |
| Reverse proxy | **nginx** or **omega-serv (native)** | Best performance |
| Websites + security + interface | **omega-serv (native)** | Complete infrastructure: WAF, web administration, multi-instance, reverse proxy, log manager, backups... |

---

Data from the omega-serv comparison (November 2026) — kraynux. MIT license.
[oha](https://github.com/hatoo/oha) for measuring · standalone HTML/CSS charts.

> *Graphical version of the measured omega-serv comparison (same figures as the detailed comparison: measurements of 3 and 4 November 2026 on three machines; reverse proxy: 14 November 2026; omega-serv 3.0.0 memory: 19 November 2026). For any capacity decision, measure on your own hardware.*
>
> Copyright © 2026 kraynux — kraynux@proton.me — MIT License (see LICENSE file).
