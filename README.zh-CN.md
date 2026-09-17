<!-- Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE) -->
<div align="center">
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/assets/omega-serv.png" alt="Omega-Serv" width="384">
</div>

# 🔒 OMEGA-SERV

**独立、可移植、默认加固的 Python HTTP 服务器**

> 由 **kraynux** 为 **Omega-server** 开发
[https://kraynux.snake-mackarel.ts.net](https://kraynux.snake-mackarel.ts.net)

官方页面：[OMEGA-SERV](https://kraynux.snake-mackarel.ts.net/omega-serv/) &nbsp; Wiki 和常见问题：[使用指南](https://kraynux.snake-mackarel.ts.net/omega-serv/guide.html) &nbsp; 预览：[Screenshots](https://kraynux.snake-mackarel.ts.net/omega-serv/screenshots/)  

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/Platform-Linux-informational.svg)](https://www.linux.org/)
[![Interface](https://img.shields.io/badge/Interface-CLI%20%2B%20TUI-cyan.svg)](#3-使用方法)

**语言:**
[Français](README.md) · [English](README.en.md) · [Español](README.es.md) · [Русский](README.ru.md) · [中文](README.zh-CN.md)

---

**Omega-serv** 是一个用纯 Python 编写的 HTTP/1.1 服务器（服务器核心仅使用标准库），用于提供静态内容，并可选支持 PHP-FPM，具有不可禁用的协议加固功能，以及可叠加（而非强制）的安全模块（WAF、TLS、身份验证）。它是 `omega-` 套件中的第七个工具，但被有意排除在未来的 **`omega-suite` 集成之外**（它作用于承载它的本地机器，而非远程目标 —— 与 `omega-fire` 属于同一类别）；采用 Clean Architecture 结构，`bootstrap/` 充当组合根。

## 1. 愿景与范围

明确的优先级是**首先保证 HTTP 核心的稳固性/安全性**——WAF 和 TLS 是叠加其上的可选模块，绝非前提条件。一个只做一件事（提供文件，可选 PHP）但把这件事做对、拥有真正且不可绕过的协议加固的服务器，胜过一个什么都做一点却都不彻底的服务器。

### Omega-serv 能做什么

- 提供静态内容（文件、可选的目录列表、别名、重定向、重写、缓存），并采用安全的路径解析（路径穿越、双重编码、符号链接）。
- 默认加固 HTTP 协议，且无法关闭：明确的允许方法列表、`Host` 头校验、拒绝 `Content-Length`/`Transfer-Encoding` 的歧义、不可绕过的安全响应头与基础 CSP。
- 可选功能：WAF 过滤（签名、速率限制、封禁列表）、直接 TLS（自签名证书或由本地 CA 签发的证书）、按区域划分的 HTTP Basic 身份验证、通过 FastCGI/PHP-FPM 运行 PHP、受限的上传区域。
- 审计自身配置（`audit security`），并可作为系统服务安装（systemd/OpenRC/runit）。
- 端到端可脚本化的非交互式 CLI，**以及一个交互式（Textual）界面**，二者封装完全相同的用例——见 §3。界面路线图（`OMEGA-SERV_PLAN-DETAILLE_INTERFACE.md`，§12）**已全部交付**：能力注册表、配置文件/选项、详细配置（别名/重定向/重写/FastCGI/目录列表/身份验证/缓存/WAF/可信代理/出站反向代理/TLS）、日志管理（查看/跟踪/lnav/轮转/备份/自动化/统计/热门 IP）、系统服务、多实例（注册表、创建）、检查/模拟/审计、配置备份/恢复、首次启动向导、应用设置（主题、渲染配置、导出/截图路径）、内置帮助指南（每屏一份带具体示例的说明卡片、FAQ、HTML 导出，覆盖率已做到全覆盖并通过测试验证）、每次保存后系统性地提示热重载/重启、无需手动编辑文件即可完成的 Active Defense 完整配置。

### Omega-serv 不做什么

- 原始 CGI（已从 V1 范围中移除——仅支持 FastCGI/PHP-FPM）。
- TLS 双向认证（mTLS）、OCSP stapling、ACME——不在 V1 范围内，见 §15。
- 跨进程共享的 HTTP 缓存。
- 扫描/审计远程目标（这方面请参见 `omega-check`/`omega-scan`/`omega-deep`——Omega-serv 只审计自身，绝不审计第三方）。

### 使用警告

Omega-serv **拒绝以 root 身份启动**。所提供的任何配置文件（包括 `hardened`）中都没有默认启用任何安全模块（WAF、TLS、身份验证）——启用它们始终是一个明确的操作（`config enable-tls`、`option enable waf`……）。`hardened` 配置文件本身也建议使用反向代理来应对真实的互联网暴露，而非取而代之。

## 2. 安装

### 前置条件

- Python 3.10+
- `openssl`（二进制程序，而非 Python 库），用于一切涉及 TLS 证书的操作——其余功能无需它即可运行。

### 安装

```bash
[ -d omega-serv ] && echo "ℹ️ 此处已解压，跳过该步骤。" || tar -xzf omega-serv.tar.gz
cd omega-serv/
chmod +x install.sh
./install.sh
```

`install.sh`：

1. 如果 `.venv` 虚拟环境尚不存在，则创建它。
2. 安装软件包（`pip install -e .`）——**无外部依赖**（见 §6）。
3. 使 `omega-serv.sh` 和 `install.sh` 可执行。
4. 将 `serv` 别名添加到 `~/.bashrc` 和 `~/.zshrc`（如已存在则不重复添加）。

### 依赖

服务器核心（HTTP/1.1 解析器、FastCGI 客户端、通过 `hashlib.scrypt` 进行的密码哈希）保持纯 Python/标准库实现，而一切涉及 TLS 证书的操作都通过子进程调用 `openssl` 二进制程序，而非使用 Python 加密库——**这方面没有外部依赖**。只有交互式界面（§3）引入了一些依赖：`omega-lib`（主题、终端检测——套件共享库，未发布到 PyPI，随发行档案一并打包）、`textual` 以及 `pyte`（用于界面内嵌合并 `lnav` 渲染的终端模拟）、`jinja2`（主题化 HTML 导出）以及 `psutil`（状态与资源屏幕——CPU/内存/磁盘/网络）。可选的开发/测试依赖（`pip install -e ".[test]"`）：`hypothesis`（针对 HTTP 解析器和路径解析器的基于属性的测试，从不在生产环境中使用）。质量工具（`pip install -e ".[dev]"`）：`pytest`、`ruff`、`mypy`、`import-linter`。

### 推荐的可选工具

如果缺少这些工具，界面会以降级模式运行：

- `lnav` —— 融合在**日志管理**屏幕（§3）中的高级日志分析；如果找不到可执行文件，会显示清晰明确的错误信息，不会崩溃，屏幕的其余部分（查看/跟踪/轮转/统计）在没有它的情况下仍正常工作。
- `python-psutil`（与 PyPI 上的 `psutil` 等价的系统软件包）—— 在所有情况下都会由 `pip install -e .` 自动安装（软件包的强制依赖，**状态与资源**屏幕始终需要它），但通过系统包管理器预先安装可以让 `pip` 免于在本地编译其 wheel。

```bash
# Arch Linux 及其衍生版（Manjaro……）
sudo pacman -S lnav python-psutil

# Debian/Ubuntu 及其衍生版
sudo apt install lnav python3-psutil

# Fedora
sudo dnf install lnav python3-psutil
```

## 3. 使用方法

两个功能上严格等价的界面，二者之间从不重复逻辑：非交互式 CLI（可脚本化，下文使用）与交互式 Textual 界面（菜单、表单、表格）——CLI 一侧存在的每一个操作，界面只是对相同用例的包装。

### 交互模式（TUI）

推荐日常使用 —— 不带任何参数启动：

```bash
./omega-serv.sh
```
如果已创建别名，直接在终端输入 `serv` 即可：
```bash
serv
```

### 整体流程

启动屏幕（splash，按任意键或点击即可关闭）→ 主菜单（首次启动向导 / 能力注册表 / 配置文件 / 服务器详细配置 / 主动安全 / 日志管理 / 服务 / 多实例 / 状态与资源 / 安全审计 / 配置备份）→ 先选择一个板块再选择一个操作，每个表单都会在继续前校验所有必填字段 → 在任何敏感或破坏性操作（重启、删除、恢复……）之前都会要求明确确认 → 任何修改已在运行的配置的保存操作之后，都会系统性地提示后续步骤（自动热重载，或要求确认完全重启）。对终端的适配（颜色、尺寸、渲染配置的结构性降级）是自动完成的，无需任何手动参数——见 §4。

#### 键盘快捷键（交互式界面）

| 按键 | 操作 |
|---|---|
| `↑` / `↓` | 在屏幕元素间导航 |
| `Tab` / `Shift+Tab` | 在表单字段间导航 |
| `Esc` | 返回上一屏幕（在主屏幕上则要求确认退出） |
| `t` | 切换到下一个主题（立即应用，无需确认） |
| `r` | 刷新终端检测 |
| `F1` | 当前屏幕的帮助（上下文说明卡片——见下文「帮助指南」） |
| `a` | 完整帮助指南（可导航菜单 + FAQ） |
| `o` | 应用设置（主题、渲染配置、导出/截图路径——见下文） |
| `q` | 退出（需确认） |
| `Ctrl+P` | 命令面板（主题、截图、设置……） |

#### 帮助指南（`F1`/`a` 按键）

内置帮助系统，绝非单纯的静态文字：每个已建档的屏幕（定义卡片/需填写字段及具体示例/触发的操作/后续反应——重载、重启或无需任何操作）都可以通过 `F1` 直接从该屏幕访问；`a` 键则打开完整菜单（与应用程序真实导航结构完全一致的树状结构），其中还可访问 FAQ（实际使用中遇到的陷阱，例如 Active Defense 的攻击类别、共享服务的权限问题）以及一个可独立使用的 HTML 导出功能（保留当前主题），导出整份指南。在尚未建立具体条目之前会回退到一个通用参考屏幕——目前的覆盖率已经做到全覆盖，并通过测试验证。

#### 主菜单（交互式界面）

- **首次启动向导** —— 分 8 个步骤引导（欢迎 → 只读能力检测 → 选择配置文件 → 绑定地址/端口 → 可选 TLS → 检查 → 摘要与写入 → 提议安装服务）；无需接触 CLI 即可生成完整配置并启动服务器。
- **能力注册表** —— 只读系统探测（初始化系统、所配置端口是否已被占用、`openssl`/`logrotate`/`tailscale`/`lnav` 是否存在、磁盘空间、文件描述符限制……），支持 JSON/HTML 导出。
- **配置文件** —— 与 CLI 中的 `profile` 用例相同（§5），写入前始终显示差异对比。
- **服务器详细配置** —— 对别名/重定向/重写/目录列表/可信代理/出站反向代理/FastCGI/缓存/身份验证/访问控制/错误页面的完整增删改查，外加 **TLS** 子菜单（状态、自签名生成、本地 CA 向导、吊销、启用/禁用——见 §9）；下方第二个区域「**选项与验证**」汇集了指向**选项**（`option` CLI，§7）与**检查配置**（`config check` CLI，§10）的快捷入口——与先调整选项再验证是同一流程，这两个屏幕已不再能从主菜单直接进入。WAF 已不再位于此处（见下文「主动安全」）：它主要展示持续变化的运行状态，而非一份单纯的静态配置表单。每次保存都会明确说明后续操作：若有服务正在运行，则自动且静默地热重载（目录列表、访问控制、别名/重定向/重写、缓存、错误页面、可信代理、反向代理/FastCGI 区域、身份验证用户/区域），或者当更改涉及监听套接字、TLS 或 Active Defense 时则明确弹出重启确认——不再有任何屏幕让人猜测是否需要重启服务器。
- **主动安全** —— 一个统一的屏幕，汇集两大板块：**Active Defense**（状态、带评分/等级的已跟踪威胁、带完整时间线/IoC 导出/报告的事件、欺骗分配情况、以 dry-run 方式模拟一次判定，以及**设置**——无需手动编辑 `config/omega-serve.json` 即可完成完整配置，见 §11）与 **WAF**（状态、模块——模式/规则包/封禁列表、测试一次请求、自定义——编写自定义规则）——见 §11。
- **日志管理** —— 实时查看/跟踪文件、合并的 `lnav`（界面内真实终端渲染）、按大小阈值手动或自动轮转/归档、立即创建备份、配置/管理计划中的自动化任务（声明式——见下方说明）、恢复/清理归档、导出列表、统计（热门 IP、状态码分布、每小时直方图）并可从访问日志中移除某个 IP 的记录。
- **服务** —— 与 CLI 中的 `service` 相同的操作（§12），按操作临时提升 `sudo` 权限，整个应用程序绝不会以 root 身份启动。
- **多实例** —— 本机已知安装的全局注册表（`~/.config/omega-serv/instances.json`，位于任何项目目录之外），显示各实例的 systemd 状态；可直接从界面创建新实例（复制代码树、独立全新的虚拟环境与依赖、生成使用不同端口的全新配置、检查嵌套冲突与端口冲突）。仅有单个安装时按钮在视觉上保持隐形（一旦已知实例达到 2 个，标签会自动变为“实例 (N)”）；也提供完整切换到另一实例的功能（`os.execv`，需明确确认，重启后显示专门的切换提示屏幕）；以及完整卸载某个实例（移除该服务单元、在没有其他实例仍使用时移除专用系统账户，并可选择性删除目录，默认从不删除）。
- **状态与资源** —— 一目了然的总览，每 2 秒刷新一次：服务器状态（进程/PID、系统服务状态、当前配置文件/已启用选项/TLS/端口）、访问日志实时流量（吞吐量、状态码分布、唯一 IP、错误率）、系统资源（CPU/内存/磁盘/交换分区/负载/网络，基于 `psutil`）；同时汇集了**模拟请求**快捷入口（与相应 CLI 命令相同的用例，§10）。
- **安全审计** —— 与相应 CLI 命令相同的用例（§10）。
- **配置备份** —— 对配置文件进行 tar.gz 归档，并可显式选择包含 WAF 规则/身份验证区域/证书（一旦包含真实密钥信息则必须确认）/Active Defense 数据库，支持恢复、列出、删除。

> 关于计划中的轮转自动化任务的说明：这些任务会被记录下来（频率 + 目标日志），但**没有任何机制会自动执行它们**——无论是在界面中还是作为后台任务。这是与 `omega-fire` 中等效屏幕保持一致的刻意选择，后者具有完全相同的纯声明式行为。真正的周期性执行器（systemd 定时器、后台任务）将是另一项独立工作，只有在确认需要时才会开展。

#### 应用设置（按键 `o` 或命令面板）

仅限界面偏好设置——切勿与 `config/omega-serve.json`（服务器自身的配置）混淆：当前主题、渲染配置（`complete`/`standard`/`reduced`/`mono`，需要重启）、导出路径（默认 `var/exports/`）、截图路径（默认 `var/screenshots/`）、清空以上任一文件夹（需要确认）。

```bash
# 启动服务器（前台运行，SIGTERM = 带宽限期的优雅关闭，SIGHUP = WAF/Auth 热重载）
./omega-serv.sh serve

# 配置
./omega-serv.sh config init                # 生成 config/omega-serve.json（安全的默认值）
./omega-serv.sh config check                # 不启动即验证（与启动时相同的阻断条件）
./omega-serv.sh config show
./omega-serv.sh config enable-tls --cert ... --key ... --mode direct
./omega-serv.sh config disable-tls

# 配置文件（minimal / standard / hardened / development）
./omega-serv.sh profile list
./omega-serv.sh profile show hardened
./omega-serv.sh profile apply hardened --dry-run   # 应用前始终显示差异对比

# 选项（aliases、redirects、rewrites、dirlisting、cache、waf、upload、fastcgi、reverse_proxy……）
./omega-serv.sh option list
./omega-serv.sh option enable waf
./omega-serv.sh option disable waf

# 在不启动服务器的情况下模拟一次请求（适合在启用规则前进行验证）
./omega-serv.sh simulate-request GET /index.html

# WAF（即使选项被禁用也可运行，通过隐式 --force）
./omega-serv.sh waf test --method GET --path /admin --remote-ip 203.0.113.1
./omega-serv.sh blocklist list
./omega-serv.sh blocklist add --network 203.0.113.0/24 --reason "检测到扫描" --duration-seconds 3600
./omega-serv.sh blocklist remove --network 203.0.113.0/24

# Active Defense（欺骗 + 战争模式，选项 "active_defense" —— 见 §11）
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

# TLS 证书 - 自签名（6a）
./omega-serv.sh certs generate-self-signed --cn localhost --san-dns localhost --san-ip 127.0.0.1
./omega-serv.sh certs show
./omega-serv.sh certs check-expiry --warn-days 30

# TLS 证书 - 本地 CA（6b，见 §9）
./omega-serv.sh certs generate-ca --cn "我的本地 CA" --days 3650
./omega-serv.sh certs generate-csr --cn server.local --san-dns server.local --key-out server.key --csr-out server.csr
./omega-serv.sh certs sign-csr --csr server.csr --ca-key secure/certificates/ca/root-ca.key --ca-cert secure/certificates/ca/root-ca.pem --out server.pem --fullchain-out fullchain.pem
./omega-serv.sh certs revoke --cert server.pem --ca-key secure/certificates/ca/root-ca.key --ca-cert secure/certificates/ca/root-ca.pem

# HTTP Basic 身份验证
./omega-serv.sh auth add-user --username alice
./omega-serv.sh auth create-zone --url-prefix /admin/ --allowed-users alice
./omega-serv.sh auth list

# 安全审计（从不阻断，仅供参考）
./omega-serv.sh audit security --format text --min-severity medium

# 配置备份（配置文件始终包含在内；真实密钥默认从不加密，
# 必须使用 --confirm-secrets 才能将其包含在内）
./omega-serv.sh config backup --description "迁移之前"
./omega-serv.sh config backup --include-auth --include-certificates --confirm-secrets
./omega-serv.sh config backup --include-active-defense --description "威胁/事件"
./omega-serv.sh config list-backups
./omega-serv.sh config restore --snapshot-id snapshot_20260908_170003_762484

# 系统服务（systemd/OpenRC/runit，自动检测）
./omega-serv.sh service install --user omega-serv --group omega-serv
./omega-serv.sh service start
./omega-serv.sh service status
```

### 值得注意的退出码

| 命令 | 代码 | 含义 |
|---|---:|---|
| `audit security` | `0` | 没有严重问题（无 `CRITICAL`/`HIGH`） |
| `audit security` | `1` | 至少有一个 `CRITICAL` 级别的发现 |
| `audit security` | `2` | 至少有一个 `HIGH`，但没有 `CRITICAL` |
| `audit security` | `3` | 执行错误（配置文件未找到……） |
| `certs check-expiry` | `1` | 证书已过期 |
| 其他任意命令 | `0`/`1` | 校验成功 / 失败 |

## 4. 终端兼容性

交互式界面（Textual）会自动检测终端能力（模拟器类型、尺寸）并据此调整其结构化样式表（`complete`/`standard`/`reduced`/`mono`），无需任何手动参数。CLI 模式则始终保持纯文本，与终端无关。这是整个 `omega-` 套件共享的策略（`omega-lib`、`terminal/policies.py`）——与 `omega-check`/`omega-fire` 完全一致。

### 按检测到的终端模拟器确定的配置

| 终端模拟器 | 初始配置 |
|---|---|
| Ghostty、Alacritty、WezTerm、Kitty | `complete` |
| Konsole、GNOME Terminal、Terminator、Xfce4 Terminal | `standard` |
| xterm、urxvt、现代 SSH | `reduced` |
| Linux TTY、旧版 SSH | `mono` |
| 未识别的终端模拟器 | `reduced`（默认回退值） |

### 按终端尺寸确定的配置

| 最小尺寸（列 × 行） | 配置上限 |
|---|---|
| 120 × 32 | `complete` |
| 100 × 28 | `standard` |
| 80 × 24 | `reduced` |
| 低于此值 | `mono` |

最终采用的配置是**两者中更严格的一个**（终端模拟器与尺寸）——一个全屏的 Ghostty 若被调整为 70 列，即使其模拟器本可支持 `complete`，也会降级为 `mono`。可通过 `r` 键实时刷新，也可以从应用设置（`o` 键，§3）中手动覆盖。

## 5. 配置文件

| 配置文件 | 预期用途 |
|---|---|
| `minimal` | 简单演示/本地使用：仅静态内容，未启用任何选项 |
| `standard` | 静态网站或小型生产环境：常规响应头、基础 CSP，dirlisting/CGI/FastCGI 均已禁用 |
| `hardened` | 最小权限暴露：默认本地绑定（面向互联网建议使用反向代理）、仅限 GET/HEAD 方法、严格 CSP、防 slowloris——即使在此配置下 WAF **也从不**自动启用 |
| `development` | 仅限本地开发，从不被视为适合互联网使用：强制回环地址绑定、CSP 为 report-only 模式、详细的错误页面 |

配置合并顺序：内置安全值 → 所选配置文件 → 保留当前已启用的选项（在切换配置文件后依然保留）→ 显式的用户覆盖项。写入前始终显示完整的差异对比（`profile apply`）。

## 6. 架构

Clean Architecture（`core / domain / ports / application / infrastructure / interfaces / bootstrap`）——`bootstrap/` 是组合根（相当于套件中其他工具的 `app/`）。本项目的一个刻意为之、并由 `import-linter` 验证而非仅凭假设的特殊之处：`application/server/start_server.py`（以及 `validate_config.py`、`run_audit.py`）扮演**依赖真实配置的构建工厂**角色（使用哪种服务管理器、是否启用 WAF……），并直接实例化具体的 `infrastructure/` 适配器——这与 CHECK/TRACK 更严格的模式不同，后者的 `application/` 只消费 `ports/`。真正普遍适用的唯一规则：`domain/`/`core/` 从不依赖外层。

```text
src/omega_serv/
├── core/            跨层通用词汇（platform_info、常量）
├── domain/           纯业务逻辑（HTTP、配置、WAF/TLS/auth/audit 安全、路由）
├── ports/            应用层所期望的契约（Protocol）
├── application/      用例 —— 部分函数（build_server……）也会组装具体适配器（见上文）
├── infrastructure/    真实实现（asyncio、以子进程方式调用 openssl、systemd/OpenRC/runit、文件）
├── interfaces/cli/    非交互式 argparse CLI
├── interfaces/tui/    交互式 Textual 界面（相同用例，从不重复逻辑）
└── bootstrap/         DependencyContainer，项目根目录解析
```

由 `import-linter` 验证的规则（7 项契约）：`domain`/`core` 从不依赖外层；`interfaces.tui` 从不直接依赖 `infrastructure`；`textual` 被限制在 `interfaces.tui` 内；`subprocess` 被限制在 `infrastructure/process/subprocess_runner.py`（以及 `infrastructure/lnav/`，用于交互式 PTY 流）；`ssl` 被限制在 `infrastructure/tls/ssl_context_builder.py`；`jinja2` 被限制在 `infrastructure/exporters/html_exporter.py`；`sqlite3` 被限制在 `infrastructure/persistence/sqlite_active_defense_connection.py`（项目中唯一的关系型存储，专用于 Active Defense——见 §11）。

## 7. 可选模块

在所有提供的配置文件中默认全部禁用——启用始终是显式操作（`option enable <名称>` 或 `config enable-tls`）：

| 模块 | 作用 |
|---|---|
| `waf` | 签名检测（敏感路径、扫描器 UA、请求体中的 SQLi/XSS/CMDi）、速率限制（令牌桶）、封禁列表（CIDR + 过期时间）、信誉/升级机制——`log-only` 模式在结构上无法进行阻断 |
| TLS | 最小化直接支持（自签名或本地 CA，见 §9），V1 中绝不支持 mTLS/OCSP/ACME |
| 身份验证 | 按区域（`url_prefix`）划分的 HTTP Basic，采用带防时序攻击的 `hashlib.scrypt`（即使对未知用户也保持恒定耗时） |
| FastCGI/PHP-FPM | 仅支持单一的 `(url_prefix, script_root)`，`script_root` 在结构上被限制在 `webroot/` 之外（静态处理器绝不可能泄露 PHP 源码） |
| 出站反向代理 | Omega-serv 本身充当面向后端的代理（与 `server.tls.mode = "behind_proxy"` 方向相反）——每个区域支持一个或多个 HTTP/HTTPS 上游，采用 round-robin 负载均衡（默认严格校验 TLS，可关闭但存在风险），剥离 hop-by-hop 头，`X-Forwarded-*` 始终被覆盖（绝不与客户端提供的值合并），支持 WebSocket（隧道建立后单个上游在整个生命周期内保持固定，且不设应用层超时） |
| 上传 | 受限区域、按区域配额、由服务器生成文件名——V1 中不支持流式传输（受 `server.max_request_size` 限制） |
| `active_defense` | 基于已计算好的 WAF 信号进行欺骗与战争模式（绝不进行第二次独立评分）：静态诱饵、针对性的减速/增强日志/速率限制、事件构建 + IoC 导出——见 §11 |

## 8. HTTP 加固（不可禁用）

- 请求行/请求头在读取**过程中**即被限制长度（绝非事后处理），拒绝过时的头部折叠写法，`Transfer-Encoding` 始终被拒绝（绝不猜测）。
- 拒绝重复的 `Content-Length`；`Expect: 100-continue` 被干净地拒绝（417）。
- 显式的方法白名单（否则返回 405 + `Allow`），校验 `Host` 请求头（缺失/为空/重复即使内容相同/含控制字符 → 400）。
- 安全响应头与基础 CSP（`enforce`/`report-only`）应用于**每一个**响应，包括错误响应——无法通过任何选项绕过。
- 在任何比较之前（封禁列表、可信代理、速率限制），IPv4 映射的 IPv6 地址（`::ffff:x.x.x.x`）均会被规范化——否则会构成一个已知的绕过手段。
- 通过基于属性的测试（`hypothesis`，生成数千个示例）针对 HTTP 解析器与路径解析器进行了验证，此外还有经典的单元/集成测试。

## 9. TLS

### 9a. 自签名证书（最简方案）

覆盖实际的本地/实验室/VPN（Tailscale……）使用场景：单一监听器、直接使用 `ssl.SSLContext`、RSA 2048/4096 或 ECDSA P-256/P-384。

### 9b. 本地 CA

适用于多个客户端设备需要建立信任、而无需逐一重新导入证书的场景：由本地证书颁发机构按需签发任意数量的服务器证书。

```text
secure/certificates/ca/
├── root-ca.key    # 0600 - 项目中最敏感的元素
├── root-ca.pem    # 0644 - 需导入客户端的信任存储
├── serial.txt     # 0600 - 跟踪下一个序列号
└── index.txt      # 0600 - 跟踪每个已签发证书的 V（有效）/R（已吊销）状态
```

流程：`certs generate-ca`（CA 密钥口令**为必填项**，若省略 `--password` 则交互式双重确认输入）→ `certs generate-csr`（服务器密钥 + CSR）→ `certs sign-csr`（使用 CA 签名，复制 CSR 中的 SAN，如有需要则构建 `fullchain.pem`）→ 将 `tls.certificate.certificate_path` 指向该 `fullchain.pem`。若证书被泄露，可通过 `certs revoke` 将其移除（在 `index.txt` 中标记，会先验证该证书确实来自此 CA——否则拒绝操作）。V1 中不提供 CRL 分发、不支持面向第三方机构的外部 CA/CSR、也不支持 mTLS（见 §15）。

## 10. 安全审计

`audit security` **不具有阻断性**：它会将 `config check` 中已具阻断性的条件以 `CRITICAL` 级别重新执行一遍，然后应用一系列建议性规则（纯逻辑层面的 TLS、CSP、危险方法、超时、上传卫生规范；以及基于真实 I/O 的文件权限、证书过期时间、已安装的 systemd 单元、日志大小）。`WAF-001`（WAF 长期停留在 `log-only`）通过一个小型状态文件（`var/run/waf-mode-state.json`）随时间进行观察——只有在多次运行中连续观察到 ≥14 天处于 `log-only` 状态后才会触发，而非在第一次 `audit` 时就触发。

## 11. Active Defense（欺骗与战争模式）

可选模块（`option enable active_defense`，默认禁用），基于已计算好的 WAF 信号（`WafDecision`/信誉/封禁列表——绝不进行第二次独立评分）来判定恶意行为，可以将某个来源切换至诱饵、减慢其响应速度并进行更精细的日志记录、构建可用于分析的事件，然后导出入侵指标（IoC）。它本身绝不阻断流量——网络层面的阻断仍由 `omega-fire` 负责；Active Defense 只负责观察、引导、减速与记录。

**威胁与评分**：每个来源（`IP + User-Agent 的 SHA-256 哈希`）会累积一个评分（阻断性的 `WAF-001` +10、信誉升级 +25、已知封禁 +25、对已分配诱饵发起 POST +30——每 15 分钟无新事件则衰减 -5），并据此被划分为 `normal`/`suspicious`/`hostile`/`contained` 四个等级（`contained` 还要求存在已知的封禁记录）。`mode: monitor` 仅观察而不采取行动；`mode: enforce` 则真正执行以下动作。

**战争模式**（`options.active_defense.settings.war_mode`）：由可配置阈值触发的 `DefensePlaybook`（`actions: ["redirect_to_decoy", "enrich_log", "delay", "rate_limit", "create_incident", "export_ioc"]`），对任何非 `normal` 的来源执行：
- `enrich_log` —— 独立的 JSONL 日志（`var/log/active-defense-enriched.jsonl`，绝不与 WAF/生产日志混在一起），请求头经过脱敏处理，HTTP 请求体根据 `logging.capture_request_body` 进行哈希（SHA-256）或截断。
- `delay` —— 有界且带抖动的减速（`war_mode.slowdown.minimum_ms`/`maximum_ms`/`jitter_ms`），绝不阻塞 asyncio 事件循环。
- `rate_limit` —— 针对单个来源的专用速率限制（`war_mode.rate_limit.requests`/`window_seconds`），复用与 WAF 相同的机制，但使用独立的键。
- `create_incident` —— 在评分超过 `thresholds.incident_score` 时自动开启/合并事件。

**欺骗（Deception）**：`hostile`/`contained` 级别的来源可以被分配到一个静态诱饵（`fake_admin`、`fake_cms`、`fake_api`、`fake_secrets`——响应内容看似真实但始终固定，绝不会真正读取文件或调用子进程），诱饵根据观察到的攻击类别来选择（`deception.profiles.<名称>.match_attack_classes`，可以是 `scan`/`credential_stuffing`/`sqli`/`xss`/`path_traversal`/`upload_probe`/`api_probe`/`unknown` 中的一个或多个）。两种隔离级别，均被明确认定并如实记录：
- **第 1 级**（进程内 fixture，`isolation_level: "fixture"`，默认级别）——明确的弱隔离：与生产环境处于同一进程、同一操作系统用户，之所以可以接受，仅仅是因为该 fixture 除了返回一个固定模板之外从不做任何其他事情。配置文件中该诱饵的**名称**必须与上述 4 个 fixture 之一完全一致——否则在校验时（`validate_active_defense_config`）会被拒绝，以避免一个命名错误的诱饵从此静默地永不触发这个陷阱。
- **第 2 级**（真正隔离的后端，`isolation_level: "proxy"`）——通过 `options.active_defense.settings.deception.decoy_zones.<名称>` 转发到一个独立进程（上游 `host`/`port` 指向一个已经在运行的服务器，绝不会自动创建；也绝不会从 `options.reverse_proxy` 读取——诱饵绝不可能意外指向某个生产区域，这一点已在 `config check` 中得到验证），复用与生产环境完全相同的出站反向代理机制（`serve_proxy()`——若在真实请求发生时上游无法访问，则向攻击者返回 502，绝不会导致崩溃）。

**「设置」屏幕**（TUI，主动安全 → Active Defense → 设置）：对上述全部内容进行完整配置——模式、战争模式的启用、作用范围/动作/阈值/减速/请求限制、欺骗（默认行为、诱饵配置文件与诱饵区域的增删改查，每个字段都会显示取值示例）、IoC、存储与日志——在每次保存前都会经过与 CLI 相同的规则校验，绝不需要手动编辑 `config/omega-serve.json`。任何更改之后都必须完全重启（Active Defense 从不支持热重载）。

**事件与 IoC**：每个事件都有完整的时间线、指标提取（IP、经哈希处理的 User-Agent）、支持带版本号的 JSON 导出/仅限可共享 IoC 的 CSV 导出/Markdown 报告——每次导出都会附带一个 `<export>.sha256` 文件（标准 `sha256sum` 格式）。若 `ioc.auto_export_on_close` 为真（默认即为真），则在关闭事件时自动导出。`active-defense purge` 会关闭重新恢复沉寂的事件，并清除已过期的威胁状态。

**模拟**：`active-defense simulate`（CLI）以及「模拟」按钮（TUI，主动安全屏幕）会预测评分/等级，并说明将会触发哪些动作——严格的 dry-run，不进行任何真实写入，也不产生任何网络影响。

备份/恢复：`config backup --include-active-defense` 会将 sqlite 数据库（威胁/事件/分配记录）纳入归档——其中从不包含明文密钥，因此不像 `--include-auth` 那样需要 `--confirm-secrets`。

## 12. 服务与运维

自动检测 systemd/OpenRC/runit（`service install/status/start/stop/restart/enable/disable/uninstall`）。生成的 systemd 单元默认应用不可协商的加固配置：`NoNewPrivileges`、`PrivateTmp`、`ProtectSystem=strict`、`ProtectHome`、`ReadWritePaths` 限制在 `var/`、强制使用专用用户/组、`UMask=0077`、`Restart=on-failure`。SIGTERM 触发优雅关闭（排空进行中的连接，经过可配置的宽限期后强制关闭）；SIGHUP 触发热重载（仅限 WAF 规则与 Auth 区域——绑定地址/端口/TLS 以及 Active Defense 若不完全重启则永远不可修改）。

## 13. 日志

`var/log/access.log`（Apache combined 格式 + `request_id`，防日志注入转义）、`var/log/error.log`。按大小/保留文件数量进行轮转（`logs.rotation`）。

## 14. 测试

```bash
source .venv/bin/activate
lint-imports        # 校验 7 项分层契约
pytest -q           # 1763 项测试
ruff check .
mypy src
```

结构：`tests/unit/`(领域层/应用层，测试替身)，`tests/integration/`(真实的 asyncio 服务器运行在真实的 TCP 套接字上、以子进程方式调用真实的 `openssl`、针对完整临时项目执行真实的 CLI 命令、通过 Textual 的 `Pilot` API 测试交互式界面——绝不使用截图)，`tests/security/`(针对 HTTP 解析器与路径解析器的 `hypothesis` 基于属性的测试)。

## 15. 范围之外

- 原始 CGI（仅支持 FastCGI/PHP-FPM）
- mTLS（客户端证书身份验证）、OCSP stapling、ACME
- 面向第三方机构的外部 CA/CSR、完整的 CRL 分发
- 批处理/周期性监控模式——每条命令都是一次显式操作
- 将 WAF 模块拆分为独立项目 `omega-waf`（已规划，但尚未启动——已提前以清晰分层的方式设计以便日后拆分，不进行并行开发）
- 与 `omega-suite` 集成（作用于本地机器，而非远程目标——与 `omega-fire` 享有相同的例外）
- Active Defense：STIX 2.1/MISP 导出、专门的负载测试、与 `omega-fire` 封禁事件的真正集成（受阻于 `omega-fire` 一侧，该工具目前未暴露任何可供读取的接口）

---

> Omega-serv —— 一个强大、完整、安全且具备主动防御能力的 Web 服务器。
