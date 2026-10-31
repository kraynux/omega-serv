<!-- Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE) -->
<div align="center">
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/assets/omega-serv.png" alt="Omega-Serv" width="384">
</div>

# 🔒 OMEGA-SERV

**Self-contained, portable HTTP server, hardened by default**

> Developed by **kraynux** for **Omega-server** 
[kraynux.snake-mackarel](https://kraynux.snake-mackarel.ts.net)

Official page: [OMEGA-SERV](https://kraynux.snake-mackarel.ts.net/omega-serv/translation/en/) &nbsp; Wiki & FAQ: [User guide](https://kraynux.snake-mackarel.ts.net/omega-serv/translation/en/guide.html)  
Preview: [Screenshots](https://kraynux.snake-mackarel.ts.net/omega-serv/screenshots/) &nbsp; Demo [Live server](https://craftdark.snake-mackarel.ts.net) &nbsp; [Web server comparison/benchmarks](comparatif-serveurs-web.md)  

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](../../../LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![Lua](https://img.shields.io/badge/Lua-5.4%2B-2C2D72.svg)](https://www.lua.org/)
[![JavaScript](https://img.shields.io/badge/JavaScript-ES2020%2B-F7DF1E.svg)](https://developer.mozilla.org/docs/Web/JavaScript)
[![Platform](https://img.shields.io/badge/Platform-Linux-informational.svg)](https://www.linux.org/)
[![Interface](https://img.shields.io/badge/Interface-CLI%20%2B%20TUI-cyan.svg)](#3-usage)
[![Textual](https://img.shields.io/badge/Textual-TUI-5A5AFB.svg)](https://textual.textualize.io/)

🌐 Documentation, exports & interface available in **17 languages** — see [Interface languages](#interface-languages).  

**Languages:**
<img src="https://flagcdn.com/w20/fr.png" alt="Français" style="height:14px;"> [Français](../../../README.md) · <img src="https://flagcdn.com/w20/gb.png" alt="English" style="height:14px;"> [English](README.md) · <img src="https://flagcdn.com/w20/es.png" alt="Español" style="height:14px;"> [Español](../es/README.md) · <img src="https://flagcdn.com/w20/br.png" alt="Português (Brasil)" style="height:14px;"> [Português (Brasil)](../pt-BR/README.md) · <img src="https://flagcdn.com/w20/it.png" alt="Italiano" style="height:14px;"> [Italiano](../it/README.md) · <img src="https://flagcdn.com/w20/de.png" alt="Deutsch" style="height:14px;"> [Deutsch](../de/README.md) · <img src="https://flagcdn.com/w20/nl.png" alt="Nederlands" style="height:14px;"> [Nederlands](../nl/README.md) · <img src="https://flagcdn.com/w20/pl.png" alt="Polski" style="height:14px;"> [Polski](../pl/README.md) · <img src="https://flagcdn.com/w20/ru.png" alt="Русский" style="height:14px;"> [Русский](../ru/README.md) · <img src="https://flagcdn.com/w20/cn.png" alt="中文" style="height:14px;"> [中文](../zh-CN/README.md) · <img src="https://flagcdn.com/w20/vn.png" alt="Tiếng Việt" style="height:14px;"> [Tiếng Việt](../vi/README.md) · <img src="https://flagcdn.com/w20/th.png" alt="ไทย" style="height:14px;"> [ไทย](../th/README.md) · <img src="https://flagcdn.com/w20/id.png" alt="Bahasa Indonesia" style="height:14px;"> [Bahasa Indonesia](../id/README.md) · <img src="https://flagcdn.com/w20/jp.png" alt="日本語" style="height:14px;"> [日本語](../ja/README.md) · <img src="https://flagcdn.com/w20/kr.png" alt="한국어" style="height:14px;"> [한국어](../ko/README.md) · <img src="https://flagcdn.com/w20/in.png" alt="हिन्दी" style="height:14px;"> [हिन्दी](../hi/README.md) · <img src="https://flagcdn.com/w20/ae.png" alt="العربية" style="height:14px;"> [العربية](../ar/README.md)

---

**OMEGA-SERV** is an HTTP/1.1 server written in pure Python (standard library only for the server core), built to serve static content and, optionally, PHP-FPM, with non-disableable protocol hardening and layered (never mandatory) security modules (WAF, TLS, authentication). Seventh tool in the `omega-` suite, but deliberately **outside the future `omega-suite` integration** (it acts on the local machine that hosts it, not on remote targets — same family as `omega-fire`); structured with Clean Architecture, `bootstrap/` acting as the composition root.

## 1. Vision and scope

The stated priority is **HTTP core solidity/security first** — WAF and TLS are optional modules layered on top, never prerequisites. A server that does one thing (serve files, optionally PHP) but does it correctly, with real, non-bypassable protocol hardening, rather than a server that does many things halfway.

### What OMEGA-SERV does

- Serves static content (files, optional directory listing, aliases, redirects, rewrites, cache) with safe path resolution (traversal, double-encoding, symlinks). Large files are sent in chunks straight from disk, never loaded into memory; every file carries an `ETag` and a `Last-Modified` (reload = empty 304 response) and accepts partial `Range` requests (resumed downloads, video); images, media, fonts, CSS and JS get a default `Cache-Control`, adjustable in the Cache screen. Pre-compressed text files: if `site.css.br` or `site.css.gz` exists next to `site.css` (created with `brotli -k site.css` or `gzip -k site.css`) and the browser accepts it, it is sent instead, never a version older than the original.
- Hardens the HTTP protocol by default, with no option to disable it: explicit allowed methods, `Host` header validation, rejection of `Content-Length`/`Transfer-Encoding` ambiguity, non-bypassable security headers and baseline CSP.
- Optionally: WAF filtering (signatures, rate limiting, blocklist), direct TLS (self-signed, locally-CA-signed, or public via Let's Encrypt/Certbot with automatic renewal — see §9), per-zone HTTP Basic authentication, PHP via FastCGI/PHP-FPM, confined upload zones.
- "Boost" mode: several server processes, at most one per CPU available on the machine (Resilience and limits screen); the security counters (rate limit, recidivism) are shared between them and stay exact.
- Audits its own configuration (`audit security`) and installs itself as a system service (systemd/OpenRC/runit).
- End-to-end scriptable non-interactive CLI, **and an interactive (Textual) interface** that wraps exactly the same use cases — see §3. The interface roadmap (`OMEGA-SERV_PLAN-DETAILLE_INTERFACE.md`, §12) is **fully delivered**: capability registry, profiles/options, detailed configuration (aliases/redirects/rewrites/FastCGI/directory listing/authentication/cache/WAF/trusted proxies/outgoing reverse proxy/TLS), log management (Library/Favorites, 3 viewers — simple/classic/merged lnav —, View and handle IPs, SSH remote sources, rotation/backup/automation/restore/purge/export), system service, multi-instance (registry, creation), check/simulate/audit, configuration backup/restore, first-run wizard, application settings (theme, render profile, export/screenshot paths), contextual help guide (per-screen sheet with concrete examples, FAQ, HTML export, exhaustive coverage verified by test), systematic reload/restart indication after every save, full Active Defense configuration with no manual file editing required.

### What OMEGA-SERV does not do

- Raw CGI (dropped from V1 scope — only FastCGI/PHP-FPM is supported).
- Mutual TLS authentication (mTLS), OCSP stapling — out of scope for V1, see §15. (ACME/Let's Encrypt via Certbot is available, see §9c/9d.)
- HTTP cache shared across processes.
- Scanning/auditing a remote target (see `omega-check`/`omega-scan`/`omega-deep` for that — Omega-serv audits only itself, never a third party).

### OMEGA-SERV compared with the web servers on the market

See [Measurements & comparison](comparatif-serveurs-web.md)  
Measured comparison between: [Nginx](https://nginx.org/) · [Lighttpd](https://www.lighttpd.net/) · [Caddy](https://caddyserver.com/) · [Apache](https://www.apache.org) · [Traefik](https://traefik.io/) · [Omega-Serv](https://kraynux.snake-mackarel.ts.net/omega-serv/translation/en/)

### Usage warning

Omega-serv **refuses to start as root**. No security module (WAF, TLS, authentication) is enabled by default in any shipped profile, including `hardened` — enabling one is always an explicit action (`config enable-tls`, `option enable waf`...). The `hardened` profile itself recommends a reverse proxy for real Internet exposure rather than substituting for one.

## 2. Installation

### Requirements

- Python 3.10+
- `openssl` (the binary, not a Python library) for anything touching TLS certificates — everything else works without it.

### Download

Latest release archive and SHA-256 checksums of every release: [omega-serv-2.0.1.tar.gz](https://kraynux.snake-mackarel.ts.net/omega-serv/download/omega-serv-2.0.1.tar.gz) · [sha.txt](https://kraynux.snake-mackarel.ts.net/omega-serv/download/sha.txt)

```bash
wget https://kraynux.snake-mackarel.ts.net/omega-serv/download/omega-serv-2.0.1.tar.gz
wget https://kraynux.snake-mackarel.ts.net/omega-serv/download/sha.txt
sha256sum -c --ignore-missing sha.txt
```

### Install

> ⚠️ **Updating an existing install?** The command below **silently skips extraction** if `omega-serv/` already exists (it assumes an interrupted first install, not an update) — you'd then reinstall dependencies over the **old, unchanged code**, with no error message at all. Use the [Upgrading](#upgrading) section below instead.

```bash
[ -d omega-serv ] && echo "ℹ️ Already extracted here, skipping." || tar -xzf omega-serv-2.0.1.tar.gz
cd omega-serv/
chmod +x install.sh
./install.sh
```

`install.sh`:

1. Creates the `.venv` virtual environment if it doesn't already exist.
2. Installs the package (`pip install -e .`) — **no external dependency** (see §6).
3. Makes `omega-serv.sh` and `install.sh` executable.
4. Adds the `serv` alias to `~/.bashrc` and `~/.zshrc` (no duplicate if already present).

### Upgrading

If `omega-serv/` already exists (previous install), **never run `tar` from inside that folder**: it would try to create a nested `omega-serv/omega-serv/` and fail. Unlike omega-fire, `install.sh` never touches folder permissions here (no step ever calls `sudo`) — so there's no risk of a `root`-owned folder, extracting directly over the existing install is safe.

```bash
# From the PARENT folder of omega-serv/ (never from inside it)
tar -xzf omega-serv-2.0.1.tar.gz
cd omega-serv/
./install.sh
```

The archive deliberately excludes all live state (`var/db/`, `var/log/`, `var/backups/`, `secure/secrets/`, `secure/certificates/*.key`, `config/omega-serve.json`, **`webroot/` — the actually served site**...) — extracting over an existing install never touches your data, certificates, settings, or served content, only the application code is replaced. `install.sh` reuses the existing `.venv` and simply reinstalls dependencies into it.

Since 2026-10-18, `var/` and `secure/auth/` are no longer in the archive at all, not even empty: extracting an update on top no longer resets their permissions (sharing with the systemd service account) — no more need for « Service → Réappliquer les permissions » after an update. `install.sh` creates these directories if missing, never touching existing ones.

> ⚠️ **If a service is already active, the step above is not enough.** It replaces the code on disk, but the already-running process keeps the old code loaded in memory — a **full restart** is always required afterwards:
> ```bash
> sudo systemctl restart <service-name>
> ```
> **Never a simple reload** (`systemctl reload`, or SERVICE screen → *Reload*): that only re-reads some configuration options (WAF rules, auth zones...), **never the Python code itself**. A `systemctl status <service-name>` showing a start date older than your update confirms it's still running the old code. If you always update by overwriting the same folder (the standard case above), this restart is the only missing step — no service reinstall is needed.

> ⚠️ **If the service then restart-loops** (`systemctl status` alternating active/inactive, `journalctl -u <service-name>` showing a `PermissionError` writing a file under `var/`): `tar` restores directory permissions as captured in the archive, which can wipe out the permission sharing set up for the dedicated system account during initial install — even though `install.sh` itself never touches it. No need to reinstall the unit: SERVICE screen → **Repair permissions** (reapplies sharing on `var/` and `secure/auth/`, without touching the systemd unit).

### Dependencies

The server core (HTTP/1.1 parser, FastCGI client, password hashing via `hashlib.scrypt`) stays in pure Python/stdlib, and anything touching TLS certificates goes through the `openssl` binary as a subprocess rather than a Python crypto library — **no external dependency for that**. Only the interactive interface (§3) introduces some: `omega-lib` (themes, terminal detection — shared suite library, not published on PyPI, vendored in the distributable archive), `textual` and `pyte` (terminal emulation for the merged `lnav` rendering inside the interface), `jinja2` (themed HTML exports) and `psutil` (Status & Resources screen — CPU/RAM/disk/network). Optional dev/test dependency (`pip install -e ".[test]"`): `hypothesis` (property-based tests for the HTTP parser and the path resolver, never in production). Quality tooling (`pip install -e ".[dev]"`): `pytest`, `ruff`, `mypy`, `import-linter`. Additional optional extra (`pip install -e ".[magnet]"`): `lupa` (embedded Lua binding, precompiled wheel, no system `lua` interpreter required), used only by the complementary WAF "magnet" script (§7) — never installed by default; its absence is reported (capability `waf-magnet`, **Capabilities** screen) with the exact install command, without blocking the rest of the server.

### Recommended optional tools

The interface runs in a degraded mode if these tools are missing:

- `openssl` — required for anything touching TLS certificates (self-signed, local CA, import); without it `certs *` commands fail but the rest of the server works normally (see §9).
- `certbot` — required only for the **Let's Encrypt** wizard and its automatic renewal (§9c/9d); self-signed/local-CA TLS never needs it.
- `lnav` — advanced log analysis merged into the **Log management** screen (§3); a clear, explicit error message if the executable can't be found, no crash, the rest of the screen (view/tail/rotation/statistics) works normally without it.
- `scp` (`openssh`/`openssh-clients` package, almost always already present) — needed only for **Remote sources (SSH)** (§13a); without it, fetching fails with a clear message, the rest of the Library works normally.
- `python-psutil` (system package equivalent to PyPI's `psutil`) — always installed automatically by `pip install -e .` (a mandatory package dependency, the **Status & Resources** screen always needs it), but pre-installing it via the system package manager saves `pip` from having to compile its wheel locally.

```bash
# Arch Linux and derivatives (Manjaro...)
sudo pacman -S openssl certbot lnav python-psutil openssh

# Debian/Ubuntu and derivatives
sudo apt install openssl certbot lnav python3-psutil openssh-client

# Fedora
sudo dnf install openssl certbot lnav python3-psutil openssh-clients
```

## 3. Usage

Two functionally strictly equivalent interfaces, never duplicated logic between the two: non-interactive CLI (scriptable, used below) and interactive Textual interface (menus, forms, tables) — every action in one exists on the CLI side, the interface only dresses up the same use cases.

### Interactive mode (TUI)

Recommended for daily use — launched with no argument:

```bash
./omega-serv.sh
```
if you created the alias, just type `serv` in the terminal:
```bash
serv
```

### Interface languages

17 languages: French, English, Spanish, Portuguese (Brazil), Italian, German, Dutch, Polish, Russian, Chinese, Vietnamese, Thai, Indonesian, Japanese, Korean, Hindi, Arabic. Choose in the Settings (`o` key, "Langue / Language", a label that is never translated), or for a single run `OMEGA_SERV_LANG=en serv`. In the Linux text console (TTY), languages whose script is missing from the console fonts (Vietnamese, Chinese, Thai, Japanese, Korean, Hindi, Arabic) are shown in English for the session. In Hindi, terminals that shape conjunct letters themselves (Kitty, Ghostty, Konsole) shift boxes and columns, variably depending on the font: a warning is shown at startup; Terminator, GNOME Terminal, Xfce Terminal and Alacritty display Hindi aligned. Two separate settings: the **visitor pages language** (error pages, directory listing — Error pages screen, French by default) and the **export language** (HTML exports and incident report — Settings, "Same as interface" by default). Server logs (`journalctl`) stay in French.

### General flow

Splash screen (closes on any key or click) → main menu (First-run wizard / Capability registry / Profiles / Detailed configuration / Active Security / Log management / Service / Multi-instance / Status & Resources / Audit / Backup) → picking a section then an action, each form validating its required fields before continuing → an explicit confirmation before any sensitive or destructive operation (restart, deletion, restore...) → a systematic indication of what comes next (automatic hot reload, or a full-restart confirmation) after any save that changes a configuration already being served. Adapting to the terminal (colors, size, structural degradation of the render profile) is automatic, no manual flag needed — see §4.

#### Keyboard shortcuts (interactive interface)

| Key | Action |
|---|---|
| `↑` / `↓` | Navigate between elements on a screen |
| `Tab` / `Shift+Tab` | Navigate between fields in a form |
| `Esc` | Back to the previous screen (exit confirmation on the home screen) |
| `t` | Next theme (applied immediately, no confirmation) |
| `r` | Refresh terminal detection |
| `F1` | Help for the current screen (contextual sheet — see "Help guide" below) |
| `a` | Full help guide (navigable menu + FAQ) |
| `o` | Application settings (theme, render profile, export/screenshot paths — see below) |
| `q` | Quit (with confirmation) |
| `Ctrl+P` | Command palette (Theme, Screenshot, Options...) |

> **Exception — list editor (WAF → Custom)**: no shortcuts at all, everything is done with the mouse; the keyboard is only used for typing (characters, Enter, arrows, Home/End, Page Up/Down, Backspace, Delete). `Esc`, `F1` and `Ctrl+P` are inactive there (**Help** button); only `Ctrl+Q` remains, with a confirmation for unsaved changes.

#### Help guide (`F1`/`a` keys)

A built-in help system, never a plain static text block: every documented screen (a sheet covering definition/fields-to-fill-in with concrete examples/action triggered/reaction — reload, restart, or none) is reachable directly from it via `F1`; the `a` key opens the full menu (a tree mirroring the application's real navigation) with access to the FAQ (real pitfalls hit in actual use, e.g. Active Defense attack classes, shared-service-log permissions) and a self-contained HTML export (keeping the active theme) of the entire guide. Falls back to a generic reference screen for as long as a precise sheet doesn't exist yet — coverage is currently exhaustive, verified by test.

#### Main menu (interactive interface)

- **First-run wizard** — an 8-step guided journey (welcome → read-only capabilities → profile choice → bind/port → optional TLS → check → summary + write → service-install proposal); lets you generate a full configuration and get the server running without ever touching the CLI.
- **Capability registry** — read-only system probe (init system, whether the configured port is already taken, whether `openssl`/`logrotate`/`tailscale`/`lnav` are present, disk space, file-descriptor limit...), JSON/HTML export.
- **Profiles** — same use cases as `profile` on the CLI (§5), a diff is always shown before writing.
- **Detailed server configuration** — full CRUD on aliases/redirects/rewrites/directory listing/trusted proxies/outgoing reverse proxy/FastCGI/cache/authentication/access control/error pages, plus the **TLS** sub-menu (status, self-signed generation, local CA wizard, Let's Encrypt/Certbot wizard, automatic renewal, revocation, enable/disable — see §9) ; a second frame, **OPTIONS AND VERIFICATION**, groups shortcuts to **Options** (`option` CLI, §7) and **Check configuration** (`config check` CLI, §10) — same journey as adjusting settings then verifying them, these two screens are no longer directly accessible from the main menu. WAF no longer lives here (see "Active Security" below): it mostly exposes continuously-changing operational state, not a plain static configuration form. Every save now spells out what comes next: an automatic, silent hot reload if a service is active (directory listing, access control, aliases/redirects/rewrites, cache, error pages, trusted proxies, reverse-proxy/FastCGI zones, authentication users/zones), or an explicit restart confirmation when the change touches the listening socket, TLS, or Active Defense — no screen leaves you guessing whether the server needs relaunching.
- **Active Security** — a single screen grouping two blocks side by side: **Active Defense** (Status, tracked Threats with score/level, Incidents with timeline/IoC export/report, Deception assignments, Simulate a decision in dry-run, **Settings** — full configuration without ever hand-editing `config/omega-serve.json`, see §11) and **WAF** (Status, Modules — mode/rule packs/blocklist, Test a request, Custom — custom rule authoring and loading of mouse-editable path/keyword lists (see §11b), Magnet — import an external `mod_magnet` script with a compatibility check before activation) — see §11.
- **Log management** — a two-column menu. **Library** column: a central hub referencing every log to work with (manual feeding — one click adds the logs native to this instance by default — access/error/native WAF, + magnet script §7 if active —, or a **remote source** fetched over SSH, see below); **Favorites** (a saved combination of logs + viewer, launched directly); **View logs** with 3 viewers to choose from depending on how many logs are selected — Simple (live tail + generic stats: unique IPs/error rate/HTTP status breakdown on any format), Classic (read + follow), merged `lnav` (real terminal rendering inside the interface, magnet logs included by default + manually **pinned** paths kept across sessions); **View and handle IPs** (top IPs across one or more chosen logs, 24h/7d/30d/all period, per-IP removal). **Maintenance** column (unchanged): manual or size-threshold-automatic rotation/archiving, immediate backup creation, scheduled-automation configuration/management (declarative — see note below), restore/purge an archive, export the list.
- **Service** — same actions as `service` on the CLI (§12), one-off `sudo` elevation per action, the whole application is never launched as root.
- **Multi-instance** — global registry (`~/.config/omega-serv/instances.json`, outside any project directory) of known installations on this machine, with each one's systemd status; create a new instance (tree copy, its own fresh virtual environment and dependencies, fresh config with a distinct port, non-nesting and port-conflict checks) directly from the interface. The button stays visually invisible for a single install (label "Multi-instance" becomes "Instances (N)" once 2 are known); a full switch to another instance is also offered (`os.execv`, explicit confirmation, dedicated splash announcing the switch on restart); full uninstall of an instance (removes the unit, the dedicated system account if no other instance still uses it, and optionally the directory, never by default).
- **Status & Resources** — an at-a-glance overview, refreshed every 2 seconds: server state (process/PID, system service status, active profile/options/TLS/port), live access-log traffic (throughput, status-code breakdown, unique IPs, error rate), system resources (CPU/RAM/disk/swap/load/network, via `psutil`) ; also groups the **Simulate a request** shortcut (same use case as the corresponding CLI command, §10).
- **Security audit** — same use case as the corresponding CLI command (§10).
- **Configuration backup** — a tar.gz archive of the configuration file and, on explicit opt-in, WAF rules/authentication zones/certificates (mandatory confirmation as soon as real secrets are included)/the Active Defense database, restore, list, delete.

> Note on scheduled rotation automations: they are recorded (frequency + targeted log) but **nothing executes them automatically** — neither in the interface nor as a background task. This is a deliberate parity choice with the equivalent screen in `omega-fire`, which has the exact same declarative-only behavior. A real periodic executor (a systemd timer, a background task) would be separate, only-if-confirmed-needed future work.

#### Application settings (`o` key or command palette)

Interface preferences only — never confused with `config/omega-serve.json` (the server's own configuration): active theme, render profile (`complete`/`standard`/`reduced`/`mono`, restart required), export path (`var/exports/` by default), screenshot path (`var/screenshots/` by default), purging either folder (confirmation required).

```bash
# Start the server (foreground, SIGTERM = graceful shutdown with grace period, SIGHUP = hot reload of WAF/Auth)
./omega-serv.sh serve

# Configuration
./omega-serv.sh config init                # generates config/omega-serve.json (safe defaults)
./omega-serv.sh config check                # validates without starting (same blocking gates as at startup)
./omega-serv.sh config show
./omega-serv.sh config enable-tls --cert ... --key ... --mode direct
./omega-serv.sh config disable-tls

# Profiles (minimal / standard / hardened / development)
./omega-serv.sh profile list
./omega-serv.sh profile show hardened
./omega-serv.sh profile apply hardened --dry-run   # diff before applying, always

# Options (aliases, redirects, rewrites, dirlisting, cache, waf, upload, fastcgi, reverse_proxy...)
./omega-serv.sh option list
./omega-serv.sh option enable waf
./omega-serv.sh option disable waf

# Simulate a request without starting the server (useful to validate a rule before enabling it)
./omega-serv.sh simulate-request GET /index.html

# WAF (works even with the option disabled, via an implicit --force)
./omega-serv.sh waf test --method GET --path /admin --remote-ip 203.0.113.1
./omega-serv.sh blocklist list
./omega-serv.sh blocklist add --network 203.0.113.0/24 --reason "scan detected" --duration-seconds 3600
./omega-serv.sh blocklist remove --network 203.0.113.0/24

# Active Defense (deception + war mode, "active_defense" option - see §11)
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

# TLS certificates - self-signed (9a)
./omega-serv.sh certs generate-self-signed --cn localhost --san-dns localhost --san-ip 127.0.0.1
./omega-serv.sh certs show
./omega-serv.sh certs check-expiry --warn-days 30

# TLS certificates - local CA (9b)
./omega-serv.sh certs generate-ca --cn "My local CA" --days 3650
./omega-serv.sh certs generate-csr --cn server.local --san-dns server.local --key-out server.key --csr-out server.csr
./omega-serv.sh certs sign-csr --csr server.csr --ca-key secure/certificates/ca/root-ca.key --ca-cert secure/certificates/ca/root-ca.pem --out server.pem --fullchain-out fullchain.pem
./omega-serv.sh certs revoke --cert server.pem --ca-key secure/certificates/ca/root-ca.key --ca-cert secure/certificates/ca/root-ca.pem

# TLS certificates - import (9c, e.g. from a Certbot hook)
./omega-serv.sh certs import --key privkey.pem --cert fullchain.pem

# HTTP Basic authentication
./omega-serv.sh auth add-user --username alice
./omega-serv.sh auth create-zone --url-prefix /admin/ --allowed-users alice
./omega-serv.sh auth list

# Security audit (never blocking, informational)
./omega-serv.sh audit security --format text --min-severity medium

# Configuration backup (config is always included; real secrets are never
# encrypted by default, --confirm-secrets required to include them)
./omega-serv.sh config backup --description "before migration"
./omega-serv.sh config backup --include-auth --include-certificates --confirm-secrets
./omega-serv.sh config backup --include-active-defense --description "threats/incidents"
./omega-serv.sh config list-backups
./omega-serv.sh config restore --snapshot-id snapshot_20260908_170003_762484

# System service (systemd/OpenRC/runit, auto-detected)
./omega-serv.sh service install --user omega-serv --group omega-serv
./omega-serv.sh service start
./omega-serv.sh service status
```

### Notable exit codes

| Command | Code | Meaning |
|---|---:|---|
| `audit security` | `0` | Nothing serious (no `CRITICAL`/`HIGH`) |
| `audit security` | `1` | At least one `CRITICAL` finding |
| `audit security` | `2` | At least one `HIGH`, no `CRITICAL` |
| `audit security` | `3` | Execution error (config not found...) |
| `certs check-expiry` | `1` | Certificate expired |
| any other command | `0`/`1` | Validation success / failure |

## 4. Terminal compatibility

The interactive interface ([Textual](https://textual.textualize.io/) built on [Rich](https://rich.readthedocs.io/)) automatically detects terminal capabilities (emulator, size) and adapts its structural stylesheet accordingly (`complete`/`standard`/`reduced`/`mono`), with no manual flag. The CLI mode always stays in plain text, independent of the terminal. A policy shared across the whole `omega-` suite (`omega-lib`, `terminal/policies.py`) — identical to `omega-check`'s/`omega-fire`'s.

### Profile by detected emulator

| Emulator | Initial profile |
|---|---|
| Ghostty, Alacritty, WezTerm, Kitty | `complete` |
| Konsole, GNOME Terminal, Terminator, Xfce4 Terminal | `standard` |
| xterm, urxvt, modern SSH | `reduced` |
| Linux TTY, legacy SSH | `mono` |
| Unrecognized emulator | `reduced` (default fallback) |

### Profile by terminal size

| Minimum size (columns × rows) | Profile ceiling |
|---|---|
| 120 × 32 | `complete` |
| 100 × 28 | `standard` |
| 80 × 24 | `reduced` |
| below that | `mono` |

The final profile retained is **the more restrictive of the two** (emulator and size) — a full-screen Ghostty resized down to 70 columns drops back to `mono`, even though its emulator would allow `complete`. Refreshable live with the `r` key, or manually overridable from Application Settings (`o` key, §3).

## 5. Profiles

| Profile | Intended use |
|---|---|
| `minimal` | Simple demo/local: static only, no option enabled |
| `standard` | Static site or small production: usual headers, baseline CSP, dirlisting/CGI/FastCGI disabled |
| `hardened` | Least-privilege exposure: local bind by default (reverse proxy recommended for the Internet), GET/HEAD-only methods, strict CSP, anti-slowloris — WAF is **never** enabled automatically, even here |
| `development` | Local development only, never presented as fit for the Internet: mandatory loopback bind, report-only CSP, detailed error pages |

Configuration merge order: built-in safe values → selected profile → currently-active options preserved (survive a profile change) → explicit user overlay. A full diff is always shown before writing (`profile apply`).

## 6. Architecture

Clean Architecture (`core / domain / ports / application / infrastructure / interfaces / bootstrap`) — `bootstrap/` is the composition root (equivalent to the other suite tools' `app/`). A deliberate, `import-linter`-verified (not merely assumed) peculiarity of this project: `application/server/start_server.py` (and `validate_config.py`, `run_audit.py`) act as **configuration-dependent construction factories** (which service manager, whether to enable WAF...) and instantiate concrete `infrastructure/` adapters directly — unlike the stricter CHECK/TRACK pattern where `application/` only consumes `ports/`. The one universal rule that really is enforced: `domain/`/`core/` never depend on outer layers.

```text
src/omega_serv/
├── core/            Cross-cutting vocabulary (platform_info, constants)
├── domain/           Pure business logic (HTTP, config, WAF/TLS/auth/audit security, routing)
├── ports/            Contracts (Protocol) expected by the application layer
├── application/      Use cases - some functions (build_server...) also compose concrete adapters (see above)
├── infrastructure/    Real implementations (asyncio, openssl as subprocess, systemd/OpenRC/runit, files)
├── interfaces/cli/    Non-interactive argparse CLI
├── interfaces/tui/    Interactive Textual interface (same use cases, never duplicated logic)
└── bootstrap/         DependencyContainer, project-root resolution
```

Rules verified by `import-linter` (8 contracts): `domain`/`core` never dependent on outer layers; `interfaces.tui` never directly dependent on `infrastructure`; `textual` confined to `interfaces.tui`; `subprocess` confined to `infrastructure/process/subprocess_runner.py` (and `infrastructure/lnav/`, interactive PTY stream); `ssl` confined to `infrastructure/tls/ssl_context_builder.py`; `jinja2` confined to `infrastructure/exporters/html_exporter.py`; `sqlite3` confined to `infrastructure/persistence/sqlite_active_defense_connection.py` (the project's only relational storage, reserved for Active Defense — see §11); `lupa` confined to `infrastructure/waf/lua_waf_adapter.py` (complementary WAF "magnet" script, §7).

## 7. Optional modules

All disabled by default in every shipped profile — enabling one is always explicit (`option enable <name>` or `config enable-tls`):

| Module | Role |
|---|---|
| `waf` | Signatures (sensitive paths, UA/Referer scanner, SQLi/XSS/CMDi in the body), editable plain-text lists (keywords, or sensitive paths with `!` exceptions, Observation mode and per-list recidivism — two shipped references, explicit loading, see §11b), rate limiting (token bucket, per-folder and per-IP/network rules, see §11c), blocklist (CIDR + expiration), reputation/escalation, importing an existing Lighttpd `mod_magnet` WAF script as an optional "magnet" reinforcement (without rewriting it, extra `pip install -e ".[magnet]"` — additive, can never lift a native block; compatibility check at import time, dedicated TUI screen) — `log-only` mode is structurally unable to block |
| TLS | Direct (self-signed, local CA, or public via Let's Encrypt/Certbot with automatic renewal — see §9), never mTLS/OCSP in V1 |
| Authentication | Per-zone HTTP Basic (`url_prefix`), `hashlib.scrypt` with anti-timing defense (constant time even for an unknown user) |
| FastCGI/PHP-FPM | A single `(url_prefix, script_root)`, `script_root` confined outside `webroot/` by construction (the static handler can never leak PHP source) |
| Outgoing reverse proxy | Omega-serv acts itself as a proxy toward one or more backends (the opposite direction of `server.tls.mode = "behind_proxy"`) — load balancing (round-robin, weighted, least-connections, ip-hash, least-response-time, real load), session affinity and header-based routing rules, passive and active health checking, response caching (`Vary`-aware, multi-variant), backpressure, anti-loop protection, hot-administration API — see §7a for the full detail |
| Upload | Confined zones, per-zone quotas, server-generated filenames — no streaming in V1 (bounded by `server.max_request_size`) |
| `active_defense` | Deception + war mode driven by already-computed WAF signals (never a second score): static decoys, targeted slowdown/enriched logging/rate limiting, incidents + IoC export — see §11 |

### 7a. Outgoing reverse proxy — detail

OMEGA-SERV can act itself as a reverse proxy toward one or more HTTP/HTTPS backends — never to be confused with `server.tls.mode = "behind_proxy"` (OMEGA-SERV sitting **behind** a proxy, the opposite mechanism). Zones are managed via full CRUD (TUI: *Detailed configuration → Reverse Proxy*), one or more upstreams per zone.

- **Load balancing** — `round_robin` (default), `weighted_round_robin`/`weighted_least_connections`/`ip_hash` (weighted), `least_connections`, `least_response_time`, `real_load` (real load). `real_load` has a native mode (probes `/.omega-serv-load/`, reuses the exact same `psutil` reading as the "System status" screen, never a second call) or a declarative mode (probes a third-party HTTP endpoint, minimal format `{"load_percent": ...}` or a bare number) — granularity is per upstream, a single zone can mix both.
- **Session affinity and conditional routing** — an opaque sticky cookie (the real host:port is never exposed to the client) and header-based rules (exact match or prefix), both filtered by the targeted upstream's eligibility (cleanly fall back to the active strategy if the targeted upstream is unavailable).
- **Health** — passive (consecutive failure/success counters, distinct fall/rise thresholds to limit flapping) **and** active (a periodic probe independent of real traffic, optional per upstream, reuses the same background-task mechanism as real-load polling). States `DOWN` (always automatic), `DRAINING`/`MAINTENANCE` (always manual, explicitly ephemeral, never persisted) — a manually-triggered upstream is excluded from new selections without ever interrupting an already-established connection. Automatic retry on another upstream, only for idempotent methods (GET/HEAD/OPTIONS) and only on a connection error.
- **Backpressure** — a configurable active-connection cap per upstream; a saturated upstream cleanly refuses with 503, distinct from a dead upstream (502, retried anyway).
- **Response caching** — GET/HEAD only, never an error response, never `Set-Cookie` unless a zone explicitly opts in; honors the upstream's `Cache-Control`/`Vary` (an override exists but is dangerous, same philosophy as TLS verification). Several variants of the same resource (`Vary`) genuinely coexist on disk, never a simple "last write wins". Anti-stampede lock (only one concurrent request actually rebuilds the cache). Diagnostic header `X-Omega-Cache: HIT`/`MISS`/`BYPASS` on every response. Supervision/purge in a dedicated TUI screen (*Reverse proxy cache*).
- **Anti-loop protection** — hop-by-hop headers stripped, `X-Forwarded-*` always overwritten (never merged with client-supplied values), an `X-Omega-Proxy-Hops` counter incremented on every relay (cleanly refuses past 5 hops — detects an indirect loop between two instances, something a purely local config validation can never see).
- **WebSocket** — upgrade can be allowed per zone, a single upstream pinned for the whole tunnel lifetime once established, no application-level timeout.
- **Hot administration** — a small local HTTP API (`/.omega-serv-admin/`, protected by `trusted_proxy` just like the native load probe) lets the TUI read/force a backend's DRAINING/MAINTENANCE state and read the cache's live hit/miss ratio **of the server actually running** (dedicated *Live backend status* screen) — since the TUI and the server remain two separate processes with no shared memory, this local HTTP channel is the only bridge between the two.

## 8. HTTP hardening (non-disableable)

- Request line/headers bounded **while** being read (never after the fact), obsolete header folding rejected, `Transfer-Encoding` always rejected (never guessed).
- Duplicate `Content-Length` rejected; `Expect: 100-continue` cleanly rejected (417).
- Explicit method allowlist (405 + `Allow` otherwise), `Host` header validated (missing/empty/duplicate-even-if-identical/control character → 400).
- Security headers and baseline CSP (`enforce`/`report-only`) applied to **every** response, including errors — not bypassable by any option. `Cross-Origin-Opener-Policy`/`Cross-Origin-Resource-Policy` always `same-origin`, with no real risk of breaking a site. `Cross-Origin-Embedder-Policy` always explicitly emitted (never absent — an external scanner distinguishes "not considered" from "permissive by choice"), defaulting to `unsafe-none` on **all** profiles including `hardened`: unlike the two previous headers, `require-corp`/`credentialless` can block cross-origin resources (fonts, images, third-party iframes) specific to the actual site content — configurable (`security.coep_mode`). CSP zones (`security.csp_zones`): **explicit** exceptions per path prefix (e.g. `unsafe-inline` only under `/some-folder/` that genuinely needs it), each one entirely replacing the default policy for its prefix — never a merge, never a global relaxation; any exception stays visible in `audit security` (CSP-001/CSP-002 also scan zones), even when deliberate. Creation guided by a directive-by-directive wizard (**Generic Security** screen), each field pre-filled with the **current** value of the global policy — so you only change what needs changing instead of starting from a blank field that would sacrifice the other directives unintentionally; an extra explicit confirmation is required if the assembled zone relaxes `unsafe-inline`/`unsafe-eval`/a generic `*` source.
- IPv4-mapped-IPv6 addresses (`::ffff:x.x.x.x`) normalized before any comparison (blocklist, trusted proxy, rate limiting) — a known bypass otherwise.
- Verified with property-based tests (`hypothesis`, thousands of generated examples) against the HTTP parser and the path resolver, in addition to classic unit/integration tests.

## 9. TLS

### 9a. Self-signed certificate (minimal)

Covers the realistic local/lab/VPN use case (Tailscale...): a single listener, direct `ssl.SSLContext`, RSA 2048/4096 or ECDSA P-256/P-384.

### 9b. Local CA

For several client devices that need to trust the server without individually re-importing a certificate: a local certificate authority signs as many server certificates as needed.

```text
secure/certificates/ca/
├── root-ca.key    # 0600 - the most sensitive item in the project
├── root-ca.pem    # 0644 - to import into clients' trust store
├── serial.txt     # 0600 - tracks the next serial number
└── index.txt      # 0600 - tracks V(alid)/R(evoked) status per signed certificate
```

Flow: `certs generate-ca` (CA key passphrase **mandatory**, interactive double-confirmation prompt if `--password` is omitted) → `certs generate-csr` (server key + CSR) → `certs sign-csr` (signs with the CA, copies the CSR's SAN, builds `fullchain.pem` if requested) → point `tls.certificate.certificate_path` at that `fullchain.pem`. A compromised certificate is removed via `certs revoke` (marks `index.txt`, first verifies the certificate really comes from this CA — refuses otherwise). No CRL distribution in V1, no external CA/CSR for a third-party authority, no mTLS (see §15).

### 9c. Let's Encrypt / ACME (Certbot) — public, self-hosted

For a genuinely public site with a browser-trusted certificate, full self-hosted scheme: DDNS (Dynu or equivalent, entirely the operator's responsibility) → Certbot → Omega-serv. TUI wizard only (`Detailed configuration → TLS → Let's Encrypt wizard`) — invokes `certbot certonly --webroot` as a subprocess (**never** `--standalone`, port 80 is already taken by Omega-serv; **never** a reimplemented ACME client) with `--config-dir`/`--work-dir`/`--logs-dir` pointed under the project's `secure/certificates/letsencrypt/` — **never** `/etc/letsencrypt/` — which makes Certbot itself entirely unprivileged. The obtained certificate is imported automatically and a renewal hook script is written. Staging (test) mode is checked by default — uncheck it only once the domain/webroot are verified working, to avoid Let's Encrypt's real rate limits.

Prerequisites entirely outside Omega-serv's scope: a domain pointed at the public IP (DDNS), and ports 80/443 forwarded to this machine.

### 9d. Automatic renewal (Certbot)

`Detailed configuration → TLS → Automatic renewal` adapts to the service manager actually detected **for this instance** (never a mechanism shared across multi-instance deployments): systemd → generates and installs a timer (`<service>-certbot-renew.timer`, twice daily plus a randomized delay, `certbot renew` scoped to the instance's `--config-dir`); otherwise → a crontab line (current user, no privilege required) if `crontab` is available; otherwise → manual instructions are shown, no forced write. On some distributions (Arch/Manjaro among them), the Certbot package installs **no** timer by default, unlike Debian/Ubuntu — hence this screen rather than a plain check for an assumed-already-present mechanism. Once configured, renewal automatically re-imports each renewed certificate and restarts the service, with no further manual intervention.

## 10. Security audit

`audit security` is **non-blocking**: it re-runs `config check`'s already-blocking gates as `CRITICAL`, then applies advisory rules (TLS, CSP, dangerous methods, timeouts, upload hygiene in pure logic; file permissions, certificate expiry, installed systemd unit, log size via real I/O). `WAF-001` (WAF stuck in `log-only`) is observed over time via a small state file (`var/run/waf-mode-state.json`) — only fires after ≥14 days observed in `log-only` across repeated runs, not on the first `audit`.

## 11. Active Defense (deception + war mode)

Optional module (`option enable active_defense`, disabled by default) that qualifies hostile behavior from already-computed WAF signals (`WafDecision`/reputation/blocklist — never an independent second score calculation), and can switch a source over to a decoy, slow down its responses and log more finely, build an actionable incident, then export indicators of compromise (IoC). Never blocks traffic itself — network blocking remains `omega-fire`'s responsibility; Active Defense observes, deceives, slows down and records.

**Threats and score**: each source (`IP + SHA-256 hash of the User-Agent`) accumulates a score (blocking `WAF-001` +10, reputation escalation +25, known ban +25, POST on an already-assigned decoy +30 — decays by -5 every 15 minutes with no new event) qualified as `normal`/`suspicious`/`hostile`/`contained` (`contained` additionally requires an already-known ban). `mode: monitor` observes without acting; `mode: enforce` actually applies the actions below.

**War mode** (`options.active_defense.settings.war_mode`): a `DefensePlaybook` (`actions: ["redirect_to_decoy", "enrich_log", "delay", "rate_limit", "create_incident", "export_ioc"]`) triggered by configurable thresholds, for any non-`normal` source:
- `enrich_log` — a separate JSONL log (`var/log/active-defense-enriched.jsonl`, never mixed with the WAF/production log), headers redacted, HTTP body hashed (SHA-256) or truncated depending on `logging.capture_request_body`.
- `delay` — bounded, jittered slowdown (`war_mode.slowdown.minimum_ms`/`maximum_ms`/`jitter_ms`), never a blocking call on the asyncio loop.
- `rate_limit` — dedicated per-source rate limiting (`war_mode.rate_limit.requests`/`window_seconds`), reuses the same mechanism as the WAF under a distinct key.
- `create_incident` — automatic opening/merging of an incident once `thresholds.incident_score` is crossed.

**Deception**: a `hostile`/`contained` source can be assigned to a static decoy (`fake_admin`, `fake_cms`, `fake_api`, `fake_secrets` — plausible but always fixed responses, never a real file read or subprocess) selected according to the observed attack class (`deception.profiles.<name>.match_attack_classes`, one or more of `scan`/`credential_stuffing`/`sqli`/`xss`/`path_traversal`/`upload_probe`/`api_probe`/`unknown`). Two isolation levels, deliberately designed and documented as such:
- **Level 1** (in-process fixture, `isolation_level: "fixture"`, default) — explicitly WEAK isolation: same process, same OS user as production, acceptable only because the fixture never does anything beyond returning a static template. The profile's NAME must match exactly one of the 4 fixtures above — otherwise rejected at validation (`validate_active_defense_config`), to avoid the trap of a mis-named decoy that then silently never triggers.
- **Level 2** (a genuinely isolated backend, `isolation_level: "proxy"`) — relayed to a separate process via `options.active_defense.settings.deception.decoy_zones.<name>` (upstream `host`/`port` of a server already running, never created automatically; never read from `options.reverse_proxy` — a decoy can never accidentally point at a production zone, verified at `config check`), reusing the same outgoing reverse-proxy mechanism as production (`serve_proxy()` — upstream unreachable at request time: a 502 is returned to the attacker, never a crash).

**Settings screen** (TUI, Active Security → Active Defense → Settings): full configuration of everything above — mode, enabling war mode, scope/actions/thresholds/slowdown/rate limit, deception (default behavior, CRUD of decoy profiles and decoy zones with example values shown in every field), IoC, storage and logging — validated by the same rules as the CLI before any write, never requiring manual editing of `config/omega-serve.json`. A full restart is always required after any change (Active Defense is never hot-reloaded).

**Incidents and IoC**: a complete per-incident timeline, indicator extraction (IP, hashed User-Agent), export as versioned JSON/CSV limited to shareable IoC/Markdown report, and the **STIX 2.1** (bundle to load into OpenCTI, a SIEM…) and **MISP** (event to import through the MISP interface) exchange formats, marked TLP:AMBER by default — local files, never sent; every export comes with a `<export>.sha256` file (standard `sha256sum` format). Automatic export on incident closure if `ioc.auto_export_on_close` (true by default). Expired states and the audit log are purged automatically and the database is capped (protection against filling the disk); `active-defense purge` additionally closes incidents that have gone quiet again.

**Simulation**: `active-defense simulate` (CLI) and the "Simulate" button (TUI, Active Security screen) project the score/level and explain each action that would trigger — a strict dry-run, no real write, no network impact.

Backup/restore: `config backup --include-active-defense` includes the sqlite database (threats/incidents/assignments) in the archive — never a plaintext secret, so no `--confirm-secrets` required, unlike `--include-auth`.

## 11b. Sensitive path lists (WAF)

The WAF can load **editable plain-text lists**, one path (or keyword) per line, from **Active Security → Custom → Add → "LOAD a list"**. Nothing is ever loaded by default: it is an explicit action.

- **Shipped references**: `sensitive-paths-hostile` (298 paths with no legitimate use: secrets, backups, VCS, consoles…) and `sensitive-paths-probe` (132 probing paths, sometimes served by a real site: `/admin`, `/api`, monitoring…). On loading, a **local copy** is created in `secure/waf/rules/keywords/`: that is the file you edit, and an omega-serv update never overwrites it ("What's new in the reference" then offers new entries one checkbox at a time).
- **Syntax**: `/admin` (→ `/admin` and `/admin/xxx`, never `/administrator`), `/.git/` (everything below), `/*.bak` (extension), `!/api/v1` (exception, always wins). Paths are decoded exactly like the engine does (`%2e`, double encoding, full-width characters).
- **Severity**: *Observation* (log only, recommended on first load), then Medium (never blocks on its own) or High (403 from the first hit).
- **Per-list recidivism**: 1st hit = information or refusal; N hits within M minutes = temporary application ban (451 response, even through Tailscale); repeated blocks = network ban by omega-jail. References: hostile 2 hits in 10 min → 24 h, probe 5 in 10 min → 1 h.
- **Never auto-banned**: localhost, Tailscale (`100.64.0.0/10`) and the local network (`options.waf.reputation.never_auto_block`): only external traffic can be banned. Behind a local proxy, the `127.0.0.1` exemption requires `trusted_proxy` to be enabled. `X-Forwarded-For` is read right to left: a client cannot declare itself local.
- **Safeguards**: vital paths protected (`/`, `robots.txt`, `sitemap.xml`, `/.well-known/acme-challenge/`…), a blocking list that would hit a route actually served (alias, reverse proxy, Auth zone, webroot) is refused, **"Check against my logs"** in the editor (lines that would have hit successful requests, exception in one click).
- **Built-in editor**: live diagnostics with line numbers, "Test" a path, safe writes (mode and group kept, symlinks refused, external changes detected), readability by the service account checked ("Fix permissions"), and an **honest** reload: refused with its reason when the list fails validation, the server then keeping its current rules.

## 11c. Per-folder and per-IP/network rate limit (WAF)

The WAF rate limit (token bucket, `options.waf.rate_limit`, 60 requests / 60 s per IP by default) can be refined from **Active Security → Exclusions and rate limit** (or by hand, `rate_limit.path_policies` / `rate_limit.source_policies`):

- **Per-folder rule** (`prefix`, `requests`, `window_seconds`): it **replaces** the global limit for that folder, with its own counter (`requests: 0` = unlimited). The longest prefix wins; `/images` covers `/images/a.png`, never `/images2`. Typically a heavy page (image gallery) that returns 429.
- **Per-IP/network rule** (`network`, `requests`, `window_seconds`, `trusted`): same principle; the most specific network wins. Priority: folder, then IP/network, then the global limit.
- **Banning unchanged for the public**: an overrun by a public IP is still logged `"action": "block"` in `waf-alerts.log`, so it can be banned by omega-jail (3 rejections in 10 min → 12 h). A **trusted source** — a `never_auto_block` network or a rule marked `trusted: true` — still gets the 429 but is logged `"action": "throttle"`, which the jail never counts.
- **Magnet script**: its own rate limit (429 response) is never counted as a detection, so it never leads to an auto-ban; on a request covered by a folder or IP/network rule, the native rule prevails and the magnet 429 is ignored (its attack signatures still apply).
- A rate rule **never** disables WAF inspection; conversely, an inspection exclusion (`exclusions.path_prefixes`) never lifts the rate limit. Without an active `trusted_proxy`, a rule covering `127.0.0.1`/`::1` is ignored (same safeguard as `never_auto_block`).

## 12. Services and operations

Automatic systemd/OpenRC/runit detection (`service install/status/start/stop/restart/enable/disable/uninstall`). The generated systemd unit applies non-negotiable hardening by default: `NoNewPrivileges`, `PrivateTmp`, `ProtectSystem=strict`, `ProtectHome`, `ReadWritePaths` limited to `var/`, mandatory dedicated user/group, `UMask=0077`, `Restart=on-failure`. Graceful shutdown on SIGTERM (drains in-flight connections, configurable grace period then forced close); hot reload on SIGHUP (WAF rules and Auth zones only — bind/port/TLS and Active Defense are never changeable without a full restart).

## 13. Logs

`var/log/access.log` (Apache combined format + `request_id`, log-injection escaping), `var/log/error.log`. Rotation by size/number of kept files (`logs.rotation`). Native WAF: `var/log/waf-alerts.log` (`options.waf.logging.path`). Magnet script (§7): `options.waf.magnet.paths.alerts_log`/`.blocklist_log`, defaulting to `var/log/waf-magnet-alerts.log`/`var/log/waf-magnet-blocklist.log` — added to the Library by default (*Add Omega-Serv's known logs* button) only while the magnet is active; `lnav` always offers them regardless (a missing file is simply ignored at launch).

### 13a. Remote sources (SSH)

Centralizes, on explicit request, the log of a backend server on the same local network behind the reverse proxy (**Log management → Library → Remote sources (SSH)** screen). A "fetch" is a manual, one-off action, never a live stream or automatic polling: a **copy** is fetched via `scp` the moment you click *Fetch now*, written under `var/log/remote/`, then added to the Library as an ordinary log (*Access* column = `ssh`, *Modified* column = the date of **this** fetch — never the remote file's own date); a new fetch simply replaces the previous copy with a fresher one.

Deliberate guardrails (see `OMEGA-SERV_ETUDE-FAISABILITE_LOGS_DISTANTS.md` for the full study): no automatic network scanning, no connection without explicit configuration (label/host/remote path, with optional user/port/private key — left blank, they let `ssh`/`~/.ssh/config` decide exactly as if the command were typed by hand), no password ever requested or stored (a private key is only ever referenced by its path, never read or stored by Omega-serv), no size check before transfer. The `scp` capability is detected locally in the **Capability registry** (binary presence only, never a reachability test against any host); Samba is deliberately left out (YAGNI, until a real need is confirmed).

## 14. Tests

```bash
source .venv/bin/activate
lint-imports        # checks the 8 layer contracts
pytest -q           # 2485 tests
ruff check .
mypy src
```

Structure: `tests/unit/` (domain/application, test doubles), `tests/integration/` (a real asyncio server on real TCP sockets, real `openssl` as a subprocess, real CLI commands against a full temporary project, the interactive interface via Textual's `Pilot` API — never a screenshot), `tests/security/` (`hypothesis` property-based tests against the HTTP parser and the path resolver).

## 15. Out of scope

- Raw CGI (FastCGI/PHP-FPM only)
- mTLS (client certificate authentication), OCSP stapling
- External CA / CSR for a third-party authority, full CRL distribution
- Active Defense: real integration with `omega-fire`'s ban events (blocked on `omega-fire`'s side, which currently exposes no read surface)

---

> 🔒 OMEGA-SERV — A powerful, complete, secure and defensive web server.
