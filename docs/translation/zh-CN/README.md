<!-- Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE) -->
<div align="center">
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/assets/omega-serv.png" alt="Omega-Serv" width="384">
</div>

# 🔒 OMEGA-SERV

**独立、可移植、默认加固的 HTTP Web 服务器**

> 由 [kraynux](https://github.com/kraynux) 为 [Omega-Server](https://kraynux.snake-mackarel.ts.net) 打造   

官方页面：[OMEGA-SERV](https://kraynux.snake-mackarel.ts.net/omega-serv/translation/zh-CN/) &nbsp; 参考、使用、帮助与常见问题：[完整指南](https://kraynux.snake-mackarel.ts.net/omega-serv/translation/zh-CN/guide.html)  
预览：[截图](https://kraynux.snake-mackarel.ts.net/omega-serv/screenshots/) &nbsp; 演示 [演示服务器](https://craftdark.snake-mackarel.ts.net) &nbsp; [Web 服务器对比/测试](comparatif-serveurs-web.md)  

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](../../../LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![Lua](https://img.shields.io/badge/Lua-5.4%2B-2C2D72.svg)](https://www.lua.org/)
[![JavaScript](https://img.shields.io/badge/JavaScript-ES2020%2B-F7DF1E.svg)](https://developer.mozilla.org/docs/Web/JavaScript)
[![Platform](https://img.shields.io/badge/Platform-Linux-informational.svg)](https://www.linux.org/)
[![Interface](https://img.shields.io/badge/Interface-CLI%20%2B%20TUI-cyan.svg)](#3-使用)
[![Textual](https://img.shields.io/badge/Textual-TUI-5A5AFB.svg)](https://textual.textualize.io/)

🌐 文档、导出和界面提供 **17 种语言** —— 参见 [界面语言](#界面语言)。  
**语言：**
<img src="https://flagcdn.com/w20/fr.png" alt="France" style="height:14px;"> [Français](../../../README.md) · <img src="https://flagcdn.com/w20/gb.png" alt="English" style="height:14px;"> [English](../en/README.md) · <img src="https://flagcdn.com/w20/es.png" alt="Español" style="height:14px;"> [Español](../es/README.md) · <img src="https://flagcdn.com/w20/br.png" alt="Português (Brasil)" style="height:14px;"> [Português (Brasil)](../pt-BR/README.md) · <img src="https://flagcdn.com/w20/it.png" alt="Italiano" style="height:14px;"> [Italiano](../it/README.md) · <img src="https://flagcdn.com/w20/de.png" alt="Deutsch" style="height:14px;"> [Deutsch](../de/README.md) · <img src="https://flagcdn.com/w20/nl.png" alt="Nederlands" style="height:14px;"> [Nederlands](../nl/README.md) · <img src="https://flagcdn.com/w20/pl.png" alt="Polski" style="height:14px;"> [Polski](../pl/README.md) · <img src="https://flagcdn.com/w20/ru.png" alt="Русский" style="height:14px;"> [Русский](../ru/README.md) · <img src="https://flagcdn.com/w20/cn.png" alt="中文" style="height:14px;"> [中文](README.md) · <img src="https://flagcdn.com/w20/vn.png" alt="Tiếng Việt" style="height:14px;"> [Tiếng Việt](../vi/README.md) · <img src="https://flagcdn.com/w20/th.png" alt="ไทย" style="height:14px;"> [ไทย](../th/README.md) · <img src="https://flagcdn.com/w20/id.png" alt="Bahasa Indonesia" style="height:14px;"> [Bahasa Indonesia](../id/README.md) · <img src="https://flagcdn.com/w20/jp.png" alt="日本語" style="height:14px;"> [日本語](../ja/README.md) · <img src="https://flagcdn.com/w20/kr.png" alt="한국어" style="height:14px;"> [한국어](../ko/README.md) · <img src="https://flagcdn.com/w20/in.png" alt="हिन्दी" style="height:14px;"> [हिन्दी](../hi/README.md) · <img src="https://flagcdn.com/w20/ae.png" alt="العربية" style="height:14px;"> [العربية](../ar/README.md)

---

**OMEGA-SERV** 是一个用纯 Python 编写的 HTTP/1.1 服务器（服务器核心仅使用标准库），用于提供静态内容，并可选支持 PHP-FPM；它具有无法关闭的协议加固，以及可按需叠加而非强制启用的安全模块（WAF、TLS、认证）。它是 `omega-` 工具套件中的第七个工具，但有意**不纳入未来的 `omega-suite` 集成**（它作用于托管它的本机，而不是远程目标 —— 与 `omega-fire` 同属一类）；采用整洁架构（Clean Architecture），由 `bootstrap/` 充当组合根。

## 1. 愿景与范围

明确的优先级是**首先保证 HTTP 核心的稳固与安全** —— WAF 和 TLS 是叠加在其上的可选模块，绝不是前提条件。一个只做一件事（提供文件，或许还有 PHP）但把它做好、拥有真正无法绕过的协议加固的服务器，胜过一个样样都做却样样不精的服务器。

### OMEGA-SERV 能做什么

- 提供静态内容（文件、可选目录列表、别名、重定向、重写、缓存），并进行安全的路径解析（目录穿越、双重编码、符号链接）。大文件直接从磁盘分块发送，从不载入内存；每个文件都带有 `ETag` 和 `Last-Modified`（重新加载 = 空的 304 响应），并接受 `Range` 部分请求（断点续传、视频）；图片、媒体、字体、CSS 和 JS 会获得默认的 `Cache-Control`，可在 缓存 屏幕中修改。预压缩的文本文件：如果 `site.css` 旁边存在 `site.css.br` 或 `site.css.gz`（用 `brotli -k site.css` 或 `gzip -k site.css` 生成）且浏览器接受，就改为发送它们 —— 绝不会发送比原文件更旧的版本。
- 默认加固 HTTP 协议，且没有关闭选项：显式允许的方法、`Host` 头校验、拒绝 `Content-Length`/`Transfer-Encoding` 的歧义、无法绕过的安全头和基础 CSP。
- 可选：WAF 过滤（特征、速率限制、封禁列表）、直接 TLS（自签名证书、本地 CA 签发，或通过 Let's Encrypt/Certbot 获取并自动续期的公共证书 —— 参见 §9）、按区域的 HTTP Basic 认证、通过 FastCGI/PHP-FPM 运行 PHP、隔离的上传区域。
- 「boost」模式：多个服务器进程，每个可用 CPU 最多一个（抗压与限制 屏幕）；安全计数器（速率限制、重犯）在各进程之间共享，始终准确。
- 审计自身配置（`audit security`），并可安装为系统服务（systemd/OpenRC/runit）。
- 端到端可脚本化的非交互式 CLI，**以及交互式界面（Textual）**，二者覆盖完全相同的用例 —— 参见 §3。界面路线图（`OMEGA-SERV_PLAN-DETAILLE_INTERFACE.md`，§12）**已全部交付**：能力清单、配置档案/选项、详细配置（别名/重定向/重写/FastCGI/目录列表/认证/缓存/WAF/可信代理/出站反向代理/TLS）、日志管理（日志库/收藏、3 种查看器 —— 简单/经典/合并 lnav ——、查看并处理 IP、SSH 远程来源、轮转/备份/自动化/恢复/清理/导出）、系统服务、多实例（注册表、创建）、检查/模拟/审计、配置备份/恢复、首次启动向导、应用设置（主题、渲染配置、导出/截图路径）、上下文帮助指南（每个屏幕一张卡片并附具体示例、常见问题、HTML 导出、经测试验证的完整覆盖）、每次保存后系统提示重新加载/重启，以及无需手动编辑文件即可完整配置 Active Defense。

### OMEGA-SERV 不做什么

- 原生 CGI（已从 V1 范围中移除 —— 仅支持 FastCGI/PHP-FPM）。
- TLS 双向认证（mTLS）、OCSP stapling —— 不在 V1 范围内，参见 §15。（可通过 Certbot 使用 ACME/Let's Encrypt，参见 §9c/9d。）
- 进程间共享的 HTTP 缓存。
- 扫描/审计远程目标（为此请参见 `omega-check`/`omega-scan`/`omega-deep` —— Omega-serv 只审计自身，绝不审计第三方）。

### OMEGA-SERV 与市面上的 Web 服务器对比

参见 [测量与对比](comparatif-serveurs-web.md)  
实测对比： [Nginx](https://nginx.org/) · [Lighttpd](https://www.lighttpd.net/) · [Caddy](https://caddyserver.com/) · [Apache](https://www.apache.org) · [Traefik](https://traefik.io/) · [Omega-Serv](https://kraynux.snake-mackarel.ts.net/omega-serv/translation/zh-CN/)

### 使用警告

Omega-serv **拒绝以 root 身份启动**。在任何内置配置档案中（包括 `hardened`），都不会默认启用任何安全模块（WAF、TLS、认证）—— 启用它们始终是一个显式操作（`config enable-tls`、`option enable waf`……）。`hardened` 配置档案本身建议在真正暴露于互联网时使用反向代理，而不是取代它。

## 2. 安装

### 前提条件

- Python 3.10+
- `openssl`（程序，而非 Python 库），用于所有与 TLS 证书相关的操作 —— 其他功能没有它也能运行。

### 下载

最新版本的归档包以及每个版本的 SHA-256 校验和：[omega-serv-2.0.1.tar.gz](https://kraynux.snake-mackarel.ts.net/omega-serv/download/omega-serv-2.0.1.tar.gz) · [sha.txt](https://kraynux.snake-mackarel.ts.net/omega-serv/download/sha.txt)

```bash
wget https://kraynux.snake-mackarel.ts.net/omega-serv/download/omega-serv-2.0.1.tar.gz
wget https://kraynux.snake-mackarel.ts.net/omega-serv/download/sha.txt
sha256sum -c --ignore-missing sha.txt
```

### 安装

> ⚠️ **您是在更新现有安装吗？** 如果 `omega-serv/` 已经存在，下面的命令会**静默跳过解压**（它认为这是一次中断的首次安装，而不是更新）—— 这样您就会在**旧的、未改变的代码**上重新安装依赖，而且没有任何错误提示。请改用下方的 [更新](#更新) 一节。

```bash
[ -d omega-serv ] && echo "ℹ️ 已在此处解压，跳过此步骤。" || tar -xzf omega-serv-2.0.1.tar.gz
cd omega-serv/
chmod +x install.sh
./install.sh
```

`install.sh`：

1. 如果虚拟环境 `.venv` 尚不存在，则创建它。
2. 安装软件包（`pip install -e .`）—— **没有任何外部依赖**（参见 §6）。
3. 使 `omega-serv.sh` 和 `install.sh` 可执行。
4. 将别名 `serv` 添加到 `~/.bashrc` 和 `~/.zshrc`（若已存在则不重复添加）。

### 更新

如果 `omega-serv/` 已经存在（之前的安装），**切勿在该目录内部运行 `tar`**：它会尝试创建嵌套的 `omega-serv/omega-serv/` 并失败。与 omega-fire 不同，`install.sh` 从不改动目录权限（没有任何步骤需要 `sudo`）—— 因此这里不存在目录归 `root` 所有的风险，直接在现有安装之上解压是安全的。

```bash
# 在 omega-serv/ 的上级目录中执行（切勿在其内部）
tar -xzf omega-serv-2.0.1.tar.gz
cd omega-serv/
./install.sh
```

归档包有意排除了所有运行时状态（`var/db/`、`var/log/`、`var/backups/`、`secure/secrets/`、`secure/certificates/*.key`、`config/omega-serve.json`、**`webroot/` —— 实际提供的网站**……）—— 覆盖解压绝不会触及现有的数据、证书、设置或所提供的内容，只会替换应用代码。`install.sh` 会复用现有的 `.venv`，并直接在其上重新安装依赖。

自 2026-10-18 起，`var/` 和 `secure/auth/` 完全不再包含在归档包中，哪怕是空目录：因此覆盖解压不会再重置它们的权限（与 systemd 服务账户共享）—— 更新后不再需要「服务 → 重新应用权限」。`install.sh` 会在这些目录缺失时创建它们，但绝不改动已存在的目录。

> ⚠️ **如果服务已在运行，仅上述步骤是不够的。** 它替换了磁盘上的代码，但已在运行的进程仍继续使用加载在内存中的旧代码 —— 之后总是需要一次**完整重启**：
> ```bash
> sudo systemctl restart <服务名>
> ```
> **绝不是简单的重新加载**（`systemctl reload`，或 服务 屏幕 → *重新加载*）：它只会重新读取部分配置选项（WAF 规则、认证区域……），**从不重新读取 Python 代码本身**。如果 `systemctl status <服务名>` 显示的启动时间早于您的更新，就说明它仍在运行旧代码。如果您总是通过覆盖同一目录来更新（上面的标准情况），这次重启就是唯一缺少的步骤 —— 无需重新安装服务。

> ⚠️ **如果之后服务陷入重启循环**（`systemctl status` 在 active/inactive 之间切换，`journalctl -u <服务名>` 显示在 `var/` 下写入文件时出现 `PermissionError`）：`tar` 解压会恢复归档中记录的目录权限，这可能会抹掉首次安装时为专用系统账户设置的权限共享 —— 即使 `install.sh` 本身从不改动它。无需重新安装 unit：服务 屏幕 → **修复权限**（重新为 `var/` 和 `secure/auth/` 应用共享，不改动 systemd unit）。

### 依赖

服务器核心（HTTP/1.1 解析器、FastCGI 客户端、通过 `hashlib.scrypt` 进行密码哈希）保持纯 Python/标准库实现，所有与 TLS 证书相关的操作都通过 `openssl` 程序以子进程方式完成，而不是借助 Python 加密库 —— **这部分没有任何外部依赖**。只有交互式界面（§3）引入了依赖：`omega-lib`（主题、终端检测 —— 套件共享库，未发布到 PyPI，随分发归档包附带）、`textual` 和 `pyte`（在界面中渲染合并 `lnav` 的终端仿真）、`jinja2`（带主题的 HTML 导出）以及 `psutil`（状态与资源 屏幕 —— CPU/内存/磁盘/网络）。可选的开发/测试依赖（`pip install -e ".[test]"`）：`hypothesis`（HTTP 解析器和路径解析器的属性测试，绝不用于生产）。质量工具（`pip install -e ".[dev]"`）：`pytest`、`ruff`、`mypy`、`import-linter`。额外的可选扩展（`pip install -e ".[magnet]"`）：`lupa`（嵌入式 Lua 绑定，预编译 wheel，无需系统 `lua` 解释器），仅用于补充性的 WAF 脚本「magnet」（§7）—— 从不默认安装；缺少它时会给出提示（能力 `waf-magnet`，**能力** 屏幕）并附上确切的安装命令，但不会阻塞服务器其余部分。

### 推荐的可选工具

如果缺少这些工具，界面会以降级模式运行：

- `openssl` —— 所有与 TLS 证书相关的操作都需要它（自签名、本地 CA、导入）；没有它，`certs *` 命令会失败，但服务器其余部分正常运行（参见 §9）。
- `certbot` —— 仅 **Let's Encrypt** 向导及其自动续期需要（§9c/9d）；自签名 TLS/本地 CA 不需要它。
- `lnav` —— 在 **日志管理** 屏幕中进行高级合并日志分析（§3）；找不到程序时给出清晰明确的错误信息，不会崩溃，屏幕其余部分（查看/跟踪/轮转/统计）没有它也正常工作。
- `scp`（`openssh`/`openssh-clients` 软件包，几乎总是已经安装）—— 仅 **远程来源（SSH）** 需要（§13a）；没有它，获取会以清晰的提示失败，日志库其余部分正常工作。
- `python-psutil`（与 PyPI 上的 `psutil` 对应的系统软件包）—— 无论如何都会由 `pip install -e .` 自动安装（软件包的必需依赖，**状态与资源** 屏幕始终需要它），但通过系统包管理器预先安装可以免去 `pip` 在本地编译 wheel。

```bash
# Arch Linux 及其衍生版
sudo pacman -S openssl certbot lnav python-psutil openssh

# Debian/Ubuntu 及其衍生版
sudo apt install openssl certbot lnav python3-psutil openssh-client

# Fedora
sudo dnf install openssl certbot lnav python3-psutil openssh-clients
```

## 3. 使用

两个在功能上严格等价的界面，二者之间绝无重复逻辑：非交互式 CLI（可脚本化，下文使用）和交互式 Textual 界面（菜单、表单、表格）—— 其中任一操作在 CLI 一侧都存在，界面只是为相同用例提供外观。

### 交互模式（TUI）

推荐用于日常使用 —— 不带参数启动：

```bash
./omega-serv.sh
```
如果您创建了别名，只需在终端中输入 `serv`：
```bash
serv
```

### 界面语言

17 种语言：法语、英语、西班牙语、葡萄牙语（巴西）、意大利语、德语、荷兰语、波兰语、俄语、中文、越南语、泰语、印度尼西亚语、日语、韩语、印地语、阿拉伯语。在设置中选择（`o` 键，「Langue / Language」，该标签从不翻译），或通过 `OMEGA_SERV_LANG=en serv` 临时指定。在 Linux 文本控制台（TTY）中，控制台字体不包含其文字的语言（越南语、中文、泰语、日语、韩语、印地语、阿拉伯语）在本次会话中以英语显示。在印地语下，自行组合连写字母的终端（Kitty、Ghostty、Konsole）会使边框和列发生错位，程度因字体而异：启动时会显示警告；Terminator、GNOME Terminal、Xfce Terminal 和 Alacritty 能对齐显示印地语。另有两项独立设置：**访客页面语言**（错误页面、目录列表 —— 错误页面 屏幕，默认法语）和**导出语言**（HTML 和事件报告 —— 设置，默认「与界面相同」）。服务器日志（`journalctl`）保持法语。

### 总体流程

启动画面（splash，按任意键或单击即可关闭）→ 主菜单（首次启动向导 / 能力清单 / 配置档案 / 详细配置 / 主动安全 / 日志管理 / 服务 / 多实例 / 状态与资源 / 审计 / 备份）→ 选择一个部分，再选择一个操作，每个表单都会先校验必填字段再继续 → 在任何敏感或破坏性操作（重启、删除、恢复……）之前进行显式确认 → 每次保存修改了已在提供的配置后，系统提示后续步骤（自动热重新加载，或确认完整重启）。对终端的适配（颜色、尺寸、渲染配置的结构性降级）是自动的，无需手动标志 —— 参见 §4。

#### 键盘快捷键（交互式界面）

| 按键 | 操作 |
|---|---|
| `↑` / `↓` | 在屏幕元素之间移动 |
| `Tab` / `Shift+Tab` | 在表单字段之间移动 |
| `Esc` | 返回上一屏幕（在主页上需确认退出） |
| `t` | 下一个主题（立即应用，无需确认） |
| `r` | 刷新终端检测 |
| `F1` | 当前屏幕的帮助（上下文卡片 —— 参见下方"帮助指南"） |
| `a` | 完整帮助指南（可导航菜单 + 常见问题） |
| `o` | 应用设置（主题、渲染配置、导出/截图路径 —— 参见下文） |
| `q` | 退出（需确认） |
| `Ctrl+P` | 命令面板（主题、截图、选项……） |

> **例外 —— 列表编辑器（WAF → Custom）**：没有任何快捷键，一切都用鼠标完成；键盘只用于输入（字符、Enter、方向键、Home/End、Page Up/Down、Backspace、Delete）。`Esc`、`F1` 和 `Ctrl+P` 在其中无效（使用 **帮助** 按钮）；只有 `Ctrl+Q` 仍然有效，且在有未保存修改时需要确认。

#### 帮助指南（`F1`/`a` 键）

内置的帮助系统，而不只是静态文本：每个有文档的屏幕（卡片包含定义/需填写的字段及具体示例/触发的操作/反应 —— 重新加载、重启或无）都可以直接在该屏幕上通过 `F1` 打开；`a` 键打开完整菜单（树形结构与应用的真实导航完全一致），可访问常见问题（实际使用中遇到的陷阱，例如 Active Defense 攻击类别、共享服务的权限）以及整个指南的独立 HTML 导出（保留当前主题）。在某个屏幕还没有专属卡片时，会回退到通用参考屏幕 —— 目前的覆盖已经完整，并经过测试验证。

#### 主菜单（交互式界面）

- **首次启动向导** —— 分 8 步的引导流程（欢迎 → 只读能力检测 → 选择配置档案 → bind/端口 → 可选 TLS → 检查 → 摘要 + 写入 → 提议安装服务）；无需了解 CLI 即可生成完整配置并启动服务器。
- **能力清单** —— 只读系统探测（init 系统、所配置的端口是否已被占用、是否存在 `openssl`/`logrotate`/`tailscale`/`lnav`、磁盘空间、描述符上限……），可导出 JSON/HTML。
- **配置档案** —— 与 CLI 中 `profile` 相同的用例（§5），写入前始终显示 diff。
- **服务器详细配置** —— 对别名/重定向/重写/目录列表/可信代理/出站反向代理/FastCGI/缓存/认证/访问控制/错误页面的完整增删改查，外加 **TLS** 子菜单（状态、生成自签名证书、本地 CA 向导、Let's Encrypt/Certbot 向导、自动续期、吊销、启用/禁用 —— 参见 §9）；第二个框 **选项与检查** 集中了指向 **选项**（`option` CLI，§7）和 **检查配置**（`config check` CLI，§10）的快捷入口 —— 与"先调整设置再检查"的流程一致，这两个屏幕不再能从主菜单直接打开。WAF 不再位于此处（参见下方"主动安全"）：它主要展示不断变化的运行状态，而不是简单的静态配置表单。每次保存都会系统地指明后续步骤：若服务正在运行，则自动静默热重新加载（目录列表、访问、别名/重定向/重写、缓存、错误页面、可信代理、反向代理/FastCGI 区域、用户/认证区域）；若修改涉及监听套接字、TLS 或 Active Defense，则显式确认完整重启 —— 再也没有任何屏幕让您去猜是否需要重启服务器。
- **主动安全** —— 单一屏幕，两个并排的区块：**Active Defense**（状态、带评分/级别的被跟踪威胁、带时间线/IoC 导出/报告的事件、Deception 分配、以 dry-run 方式模拟决策、**设置** —— 无需手动编辑 `config/omega-serve.json` 的完整配置，参见 §11）以及 **WAF**（状态、模块 —— 模式/规则包/封禁列表、测试请求、Custom —— 编写自定义规则并加载可用鼠标编辑的路径/关键词列表（参见 §11b）、Magnet —— 导入外部 `mod_magnet` 脚本并在启用前检查兼容性）—— 参见 §11。
- **日志管理** —— 两栏菜单。**日志库** 栏：引用所有待处理日志的中心枢纽（手动添加，一次单击即可自动加入实例自身的日志 —— access/error/原生 WAF，若 magnet 脚本 §7 处于活动状态还包括它的日志 ——，或通过 SSH 获取的**远程来源**，参见下文）；**收藏**（以名称保存的日志 + 查看器组合，可直接启动）；**查看日志**，根据所选日志数量提供 3 种查看器 —— 简单（实时 tail + 适用于任意格式的 IP/错误/HTTP 代码通用统计）、经典（阅读 + 跟踪）、合并 `lnav`（在界面中真实渲染终端，自动包含 magnet 日志 + **固定**的手动路径以在会话之间保留）；**查看并处理 IP**（从一个或多个所选日志中统计活跃 IP，时间段 24 小时/7 天/30 天/全部，可移除某个 IP）。**维护** 栏（未变）：按大小阈值手动或自动轮转/归档、立即创建备份、配置/管理计划自动化（声明式 —— 参见下方说明）、恢复/清理归档、导出列表。
- **服务** —— 与 CLI 中 `service` 相同的操作（§12），每个操作单独临时提权 `sudo`，绝不让整个应用以 root 身份运行。
- **多实例** —— 本机已知安装的全局注册表（`~/.config/omega-serv/instances.json`，位于任何项目目录之外），附每个实例的 systemd 状态；可直接在界面中创建新实例（复制目录树、独立的虚拟环境和依赖、带独立端口的全新配置、检查嵌套和端口冲突）。只有一个安装时该按钮几乎不可见（一旦已知实例达到 2 个，"多实例"标签就会变为"实例 (N)"）；可完整切换到另一个实例（`os.execv`，显式确认，重启时显示专门的切换启动画面）；可完整卸载实例（移除 unit、若不再被其他实例使用则移除专用系统账户，并可选删除目录，但绝不默认删除）。
- **状态与资源** —— 一目了然的总览，每 2 秒刷新：服务器状态（进程/PID、系统服务状态、配置档案/活动选项/TLS/端口）、访问日志的实时流量（吞吐量、按状态码分布、唯一 IP、错误率）、系统资源（CPU/内存/磁盘/交换/负载/网络，通过 `psutil`）；还集中了 **模拟请求** 快捷入口（与相应 CLI 命令相同的用例，§10）。
- **安全审计** —— 与相应 CLI 命令相同的用例（§10）。
- **配置备份** —— 配置文件的 tar.gz 归档，并在显式选择时包含 WAF 规则/认证区域/证书（一旦包含真实机密就必须确认）/Active Defense 数据库；支持恢复、列出、删除。

> 关于计划的轮转自动化：它们会被保存（频率 + 目标日志），但**没有任何东西会自动执行它们** —— 界面侧不会，后台也不会。这是有意为之，以与 `omega-fire` 中具有相同声明式行为的对应屏幕保持一致。若确认有需要，真正的周期性执行（systemd 定时器、后台任务）需另行构建。

#### 应用设置（`o` 键或命令面板）

仅为界面偏好设置 —— 绝不要与 `config/omega-serve.json`（服务器配置）混淆：当前主题、渲染配置（`complete`/`standard`/`reduced`/`mono`，需要重启）、导出路径（默认 `var/exports/`）、截图路径（默认 `var/screenshots/`）、清空其中某个目录（必须确认）。

```bash
# 启动服务器（前台运行，SIGTERM = 带宽限期的优雅停止，SIGHUP = 热重新加载 WAF/Auth）
./omega-serv.sh serve

# 配置
./omega-serv.sh config init                # 生成 config/omega-serve.json（安全的默认值）
./omega-serv.sh config check                # 不启动即检查（与启动时相同的阻断检查）
./omega-serv.sh config show
./omega-serv.sh config enable-tls --cert ... --key ... --mode direct
./omega-serv.sh config disable-tls

# 配置档案（minimal / standard / hardened / development）
./omega-serv.sh profile list
./omega-serv.sh profile show hardened
./omega-serv.sh profile apply hardened --dry-run   # 应用前总是先看 diff

# 选项（aliases、redirects、rewrites、dirlisting、cache、waf、upload、fastcgi、reverse_proxy……）
./omega-serv.sh option list
./omega-serv.sh option enable waf
./omega-serv.sh option disable waf

# 不启动服务器即模拟请求（便于在启用前验证规则）
./omega-serv.sh simulate-request GET /index.html

# WAF（即使选项已禁用也能运行，通过隐式 --force）
./omega-serv.sh waf test --method GET --path /admin --remote-ip 203.0.113.1
./omega-serv.sh blocklist list
./omega-serv.sh blocklist add --network 203.0.113.0/24 --reason "检测到扫描" --duration-seconds 3600
./omega-serv.sh blocklist remove --network 203.0.113.0/24

# Active Defense（deception + 战争模式，选项 "active_defense" - 参见 §11）
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

# TLS 证书 - 自签名（9a）
./omega-serv.sh certs generate-self-signed --cn localhost --san-dns localhost --san-ip 127.0.0.1
./omega-serv.sh certs show
./omega-serv.sh certs check-expiry --warn-days 30

# TLS 证书 - 本地 CA（9b）
./omega-serv.sh certs generate-ca --cn "我的本地 CA" --days 3650
./omega-serv.sh certs generate-csr --cn server.local --san-dns server.local --key-out server.key --csr-out server.csr
./omega-serv.sh certs sign-csr --csr server.csr --ca-key secure/certificates/ca/root-ca.key --ca-cert secure/certificates/ca/root-ca.pem --out server.pem --fullchain-out fullchain.pem
./omega-serv.sh certs revoke --cert server.pem --ca-key secure/certificates/ca/root-ca.key --ca-cert secure/certificates/ca/root-ca.pem

# TLS 证书 - 导入（9c，例如从 Certbot hook 中调用）
./omega-serv.sh certs import --key privkey.pem --cert fullchain.pem

# HTTP Basic 认证
./omega-serv.sh auth add-user --username alice
./omega-serv.sh auth create-zone --url-prefix /admin/ --allowed-users alice
./omega-serv.sh auth list

# 安全审计（从不阻断，仅供参考）
./omega-serv.sh audit security --format text --min-severity medium

# 配置备份（始终包含配置；真实机密
# 默认从不加密，包含它们时必须使用 --confirm-secrets）
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

### 重要的退出码

| 命令 | 代码 | 含义 |
|---|---:|---|
| `audit security` | `0` | 没有严重问题（无 `CRITICAL`/`HIGH`） |
| `audit security` | `1` | 至少一项 `CRITICAL` 发现 |
| `audit security` | `2` | 至少一项 `HIGH`，且无 `CRITICAL` |
| `audit security` | `3` | 执行错误（找不到配置……） |
| `certs check-expiry` | `1` | 证书已过期 |
| 其他任何命令 | `0`/`1` | 成功 / 校验失败 |

## 4. 终端兼容性

交互式界面（基于 [Rich](https://rich.readthedocs.io/) 构建的 [Textual](https://textual.textualize.io/)）会自动检测终端的能力（仿真器、尺寸），并据此调整其结构样式表（`complete`/`standard`/`reduced`/`mono`），无需手动标志。CLI 模式始终保持纯文本，与终端无关。这是整个 `omega-` 套件共享的策略（`omega-lib`，`terminal/policies.py`）—— 与 `omega-check`/`omega-fire` 完全相同。

### 根据检测到的仿真器选择配置

| 仿真器 | 初始配置 |
|---|---|
| Ghostty、Alacritty、WezTerm、Kitty | `complete` |
| Konsole、GNOME Terminal、Terminator、Xfce4 Terminal | `standard` |
| xterm、urxvt、现代 SSH | `reduced` |
| Linux TTY、旧版 SSH | `mono` |
| 无法识别的仿真器 | `reduced`（默认回退） |

### 根据终端尺寸选择配置

| 最小尺寸（列 × 行） | 配置上限 |
|---|---|
| 120 × 32 | `complete` |
| 100 × 28 | `standard` |
| 80 × 24 | `reduced` |
| 更小 | `mono` |

最终采用的配置是**两者中更严格的那个**（仿真器和尺寸）—— 一个全屏的 Ghostty 若被缩小到 70 列，就会降到 `mono`，即使其仿真器允许 `complete`。可用 `r` 键实时刷新，也可在应用设置中手动覆盖（`o` 键，§3）。

## 5. 配置档案

| 配置档案 | 适用场景 |
|---|---|
| `minimal` | 演示/简单本地使用：仅静态内容，不启用任何选项 |
| `standard` | 静态网站或小型生产环境：常规头部、基础 CSP，目录列表/CGI/FastCGI 均禁用 |
| `hardened` | 以最小权限对外暴露：默认绑定本地（对互联网建议使用反向代理）、方法仅限 GET/HEAD、严格 CSP、防 slowloris —— 即使在这里，WAF 也**从不**自动启用 |
| `development` | 仅用于本地开发，绝不宣称适合互联网：必须绑定 loopback、CSP 为 report-only、详细错误页面 |

配置合并顺序：内置安全值 → 所选配置档案 → 保留当前已启用的选项（可跨配置档案切换保留）→ 显式的用户覆盖层。写入前始终显示完整 diff（`profile apply`）。

## 6. 架构

整洁架构（`core / domain / ports / application / infrastructure / interfaces / bootstrap`）—— `bootstrap/` 是组合根（相当于套件中其他工具的 `app/`）。这个项目有一个经过 `import-linter` 验证、而非仅凭假设的有意设计：`application/server/start_server.py`（以及 `validate_config.py`、`run_audit.py`）扮演**依赖于实际配置的构建工厂**（使用哪个服务管理器、是否启用 WAF……），会直接实例化具体的 `infrastructure/` 适配器 —— 这与 CHECK/TRACK 更严格的模式不同，后者的 `application/` 只使用 `ports/`。唯一真正强制执行的普遍规则：`domain/`/`core/` 绝不依赖外层。

```text
src/omega_serv/
├── core/            横切词汇（platform_info、常量）
├── domain/           纯业务逻辑（HTTP、配置、WAF/TLS/auth/审计安全、路由）
├── ports/            应用所期望的契约（Protocol）
├── application/      用例 - 部分函数（build_server……）也会组装具体适配器（见上文）
├── infrastructure/    实际实现（asyncio、以子进程运行的 openssl、systemd/OpenRC/runit、文件）
├── interfaces/cli/    非交互式 argparse CLI
├── interfaces/tui/    交互式 Textual 界面（相同用例，绝无重复逻辑）
└── bootstrap/         DependencyContainer、项目根目录解析
```

由 `import-linter` 验证的规则（8 项契约）：`domain`/`core` 绝不依赖外层；`interfaces.tui` 绝不直接依赖 `infrastructure`；`textual` 仅限于 `interfaces.tui`；`subprocess` 仅限于 `infrastructure/process/subprocess_runner.py`（以及 `infrastructure/lnav/`，交互式 PTY 流）；`ssl` 仅限于 `infrastructure/tls/ssl_context_builder.py`；`jinja2` 仅限于 `infrastructure/exporters/html_exporter.py`；`sqlite3` 仅限于 `infrastructure/persistence/sqlite_active_defense_connection.py`（项目唯一的关系型存储，专供 Active Defense 使用 —— 参见 §11）；`lupa` 仅限于 `infrastructure/waf/lua_waf_adapter.py`（补充性 WAF 脚本「magnet」，§7）。

## 7. 可选模块

在所有内置配置档案中均默认禁用 —— 启用始终是显式的（`option enable <名称>` 或 `config enable-tls`）：

| 模块 | 作用 |
|---|---|
| `waf` | 特征（敏感路径、扫描器 UA/Referer、请求体中的 SQLi/XSS/CMDi）、可作为文本文件编辑的列表（关键词，或带 `!` 例外的敏感路径，每个列表各自有观察模式和重犯规则 —— 附带两个参考列表，显式加载，参见 §11b）、速率限制（令牌桶，按目录和按 IP/网络的规则，参见 §11c）、封禁列表（CIDR + 过期时间）、信誉/升级、导入现有的 Lighttpd `mod_magnet` WAF 脚本作为「magnet」类型的可选增强（无需重写，扩展 `pip install -e ".[magnet]"` —— 叠加式，绝不能解除原生封禁；导入时检查兼容性，有专用 TUI 屏幕）—— `log-only` 模式在结构上无法封禁 |
| TLS | 直接 TLS（自签名、本地 CA，或通过 Let's Encrypt/Certbot 获取并自动续期的公共证书 —— 参见 §9），V1 中绝无 mTLS/OCSP |
| 认证 | 按区域（`url_prefix`）的 HTTP Basic，`hashlib.scrypt` 并防御时序攻击（即使用户不存在也保持恒定时间） |
| FastCGI/PHP-FPM | 只有一组 `(url_prefix, script_root)`，`script_root` 在构造上就被限制在 `webroot/` 之外（静态处理器永远无法泄露 PHP 源码） |
| 出站反向代理 | Omega-serv 自身充当一个或多个后端的代理（与 `server.tls.mode = "behind_proxy"` 方向相反）—— 负载均衡（round-robin、加权、least-connections、ip-hash、least-response-time、实际负载）、会话亲和与基于请求头的路由规则、被动与主动健康检查、响应缓存（多个 `Vary` 变体）、背压、防环保护、热管理 API —— 完整细节见 §7a |
| Upload | 隔离区域、按区域配额、服务器端生成的文件名 —— V1 不支持流式传输（受 `server.max_request_size` 限制） |
| `active_defense` | 基于已计算的 WAF 信号（绝不另算第二个评分）的 Deception + 战争模式：静态诱饵、有针对性的减速/增强日志/速率限制、事件 + IoC 导出 —— 参见 §11 |

### 7a. 出站反向代理 —— 详情

OMEGA-SERV 可以自身充当一个或多个 HTTP/HTTPS 后端的反向代理 —— 绝不要与 `server.tls.mode = "behind_proxy"` 混淆（OMEGA-SERV **位于**代理之后，机制相反）。区域支持完整增删改查（TUI：*详细配置 → Reverse Proxy*），每个区域可有一个或多个 upstream。

- **负载均衡** —— `round_robin`（默认）、`weighted_round_robin`/`weighted_least_connections`/`ip_hash`（加权）、`least_connections`、`least_response_time`、`real_load`（实际负载）。`real_load` 模式可为原生（探针 `/.omega-serv-load/`，复用与「状态与资源」屏幕相同的 `psutil` 读数，绝不再调用一次）或声明式（第三方 HTTP 探针，最简格式 `{"load_percent": ...}` 或纯数字）—— 粒度到每个 upstream，同一区域可混用两者。
- **会话亲和与条件路由** —— 不透明的 sticky cookie（绝不向客户端暴露真实的 host:port）以及基于请求头的规则（相等或前缀），两者都会按目标 upstream 的可用性过滤（目标 upstream 不可用时，干净地回退到当前策略）。
- **健康检查** —— 被动（连续失败/成功，down/up 切换阈值分开以减少抖动）**以及**主动（独立于真实流量的周期性探针，可按 upstream 选择启用，复用与实际负载相同的后台任务机制）。`DOWN` 状态（始终自动）、`DRAINING`/`MAINTENANCE`（始终手动，明确为临时状态，绝不持久化）—— 手动设置的 upstream 会被排除在新的选择之外，但绝不会中断已建立的连接。在另一个 upstream 上自动重试，仅限幂等方法（GET/HEAD/OPTIONS），且仅在连接错误时。
- **背压** —— 每个 upstream 可配置活动连接上限；已饱和的 upstream 会干净地以 503 拒绝，与已宕机的 upstream（502，仍会重试）区分开。
- **响应缓存** —— 仅 GET/HEAD，绝不缓存错误响应，除非按区域显式启用否则绝不缓存 `Set-Cookie`；遵守 upstream 的 `Cache-Control`/`Vary`（可禁用但很危险的选项，与 TLS 验证理念相同）。同一资源的多个变体（`Vary`）真正同时存在于磁盘上，绝不是简单的「最后写入者胜」。防惊群锁（只有一个并发请求会真正重建缓存）。每个响应都带有诊断头 `X-Omega-Cache: HIT`/`MISS`/`BYPASS`。在专用 TUI 屏幕（*反向代理缓存*）中监控/清理。
- **防环保护** —— 移除 hop-by-hop 头，`X-Forwarded-*` 始终被覆盖（绝不与客户端的合并），每次转发都会递增计数器 `X-Omega-Proxy-Hops`（超过 5 跳即干净地拒绝 —— 可检测两个实例之间的间接循环，这是简单的本地配置校验永远看不到的）。
- **WebSocket** —— 可按区域允许 upgrade，建立后在整个隧道生命周期内固定一个 upstream，无应用层超时。
- **热管理** —— 小型本地 HTTP API（`/.omega-serv-admin/`，与原生负载探针一样受 `trusted_proxy` 保护），使 TUI 能读取/强制设置某个后端的 DRAINING/MAINTENANCE 状态，并读取**实际正在运行的服务器**的缓存命中/未命中比例（专用屏幕 *后端实时状态*）—— 由于 TUI 和服务器始终是两个没有共享内存的独立进程，这个本地 HTTP 通道是二者之间唯一的桥梁。

## 8. HTTP 加固（无法关闭）

- 请求头/请求行**在读取过程中**就加以限制（绝不事后处理），拒绝过时的头部折叠，始终拒绝 `Transfer-Encoding`（绝不猜测）。
- 拒绝重复的 `Content-Length`；干净地拒绝 `Expect: 100-continue`（417）。
- 显式的方法白名单（否则返回 405 + `Allow`），校验 `Host` 头（缺失/为空/重复即使相同/包含控制字符 → 400）。
- 安全头和基础 CSP（`enforce`/`report-only`）应用于**所有**响应，包括错误响应 —— 任何选项都无法绕过。`Cross-Origin-Opener-Policy`/`Cross-Origin-Resource-Policy` 始终为 `same-origin`，没有真正破坏网站的风险。`Cross-Origin-Embedder-Policy` 始终显式发送（绝不缺失 —— 外部扫描器借此区分「未考虑」和「有意放宽」），在**所有**配置档案（包括 `hardened`）中默认为 `unsafe-none`：与前两者不同，`require-corp`/`credentialless` 可能会阻止属于实际所提供网站的跨源资源（字体、图片、第三方 iframe）—— 可调整（`security.coep_mode`）。CSP 区域（`security.csp_zones`）：按路径前缀的**显式**例外（例如仅在真正需要的 `/某个目录/` 下允许 `unsafe-inline`），每个区域都完全替换其前缀的默认策略 —— 绝不合并，绝不全局放宽；任何例外都会在 `audit security` 中保持可见（CSP-001/CSP-002 也会扫描区域），即使是有意为之。通过向导逐条指令引导创建（**通用安全** 屏幕），每个字段都预填了全局策略的**当前**值 —— 这样只修改需要改变的部分，而不是从空白字段开始而无意中牺牲其他指令；如果组装后的区域放宽了 `unsafe-inline`/`unsafe-eval`/通配源 `*`，则需要额外的显式确认。
- 在任何比较之前（封禁列表、可信代理、速率限制）都会规范化 IPv4 映射的 IPv6 地址（`::ffff:x.x.x.x`）—— 否则就是一个已知的绕过方式。
- 除常规单元/集成测试外，还通过属性测试（`hypothesis`，生成数千个样例）对 HTTP 解析器和路径解析器进行验证。

## 9. TLS

### 9a. 自签名证书（最简）

覆盖本地/实验室/VPN（Tailscale……）的实际用途：单个监听器、直接 `ssl.SSLContext`、RSA 2048/4096 或 ECDSA P-256/P-384。

### 9b. 本地 CA

用于需要信任但又不想逐台重新导入证书的多台客户端设备：由本地证书颁发机构按需签发任意数量的服务器证书。

```text
secure/certificates/ca/
├── root-ca.key    # 0600 - 项目中最敏感的元素
├── root-ca.pem    # 0644 - 需导入到客户端的信任存储
├── serial.txt     # 0600 - 记录下一个序列号
└── index.txt      # 0600 - 记录每张已签发证书的 V(alid)/R(evoked) 状态
```

流程：`certs generate-ca`（CA 密钥口令**必填**，若省略 `--password` 则交互输入并双重确认）→ `certs generate-csr`（服务器密钥 + CSR）→ `certs sign-csr`（用 CA 签名，复制 CSR 的 SAN，按需生成 `fullchain.pem`）→ 让 `tls.certificate.certificate_path` 指向该 `fullchain.pem`。泄露的证书通过 `certs revoke` 吊销（标记 `index.txt`，会先确认证书确实来自此 CA —— 否则拒绝）。V1 不提供 CRL 分发、外部 CA/第三方机构 CSR 或 mTLS（参见 §15）。

### 9c. Let's Encrypt / ACME（Certbot）—— 公共、自托管

适用于需要浏览器认可证书的真正公共网站，完整的自托管方案：DDNS（Dynu 或同类服务，完全由运维方负责）→ Certbot → Omega-serv。仅提供 TUI 向导（`详细配置 → TLS → Let's Encrypt 向导`）—— 以子进程调用 `certbot certonly --webroot`（**绝不**使用 `--standalone`，因为 80 端口已被 Omega-serv 占用；**绝不**重新实现 ACME 客户端），并将 `--config-dir`/`--work-dir`/`--logs-dir` 指向项目的 `secure/certificates/letsencrypt/` —— **绝不**使用 `/etc/letsencrypt/` —— 从而使 Certbot 本身完全无需特权。获取到的证书会自动导入（与 `certs import` 机制相同，参见上面的 CLI 示例），并写入续期 hook 脚本。测试模式（staging）默认勾选 —— 在确认域名/webroot 可用后再取消勾选，以避免触发 Let's Encrypt 的真实速率限制。

完全不在 Omega-serv 范围内的前提条件：域名指向公网 IP（DDNS），以及 80/443 端口转发到本机。

### 9d. 自动续期（Certbot）

`详细配置 → TLS → 自动续期` 会根据**此实例**实际检测到的服务管理器进行适配（绝不是多个实例共享的机制）：systemd → 生成并安装定时器（`<service>-certbot-renew.timer`，每天两次 + 随机延迟，`certbot renew` 限定于该实例的 `--config-dir`）；否则 → 若有 `crontab` 则写入 crontab 行（当前用户，无需特权）；否则 → 显示手动配置说明，不强制写入。在某些发行版（包括 Arch/Manjaro）上，Certbot 软件包默认**不会**安装任何定时器，这与 Debian/Ubuntu 不同 —— 因此提供了这个屏幕，而不是简单地检查一个假定已经存在的机制。配置完成后，续期会自动重新导入每张续期后的证书（`certs import`），然后重启服务，再也无需任何手动干预。

## 10. 安全审计

`audit security` **不会阻断**：它会以 `CRITICAL` 级别重新执行 `config check` 中已有的阻断检查，然后应用建议性规则（TLS、CSP、危险方法、超时、上传卫生 —— 纯计算；文件权限、证书过期、已安装的 systemd unit、日志大小 —— 真实 I/O）。`WAF-001`（WAF 停留在 `log-only`）通过一个小状态文件（`var/run/waf-mode-state.json`）随时间观察 —— 只有在多次运行中观察到 `log-only` 持续 ≥14 天后才会触发，而不是在第一次 `audit` 时就触发。

## 11. Active Defense（deception + 战争模式）

可选模块（`option enable active_defense`，默认禁用），基于已计算的 WAF 信号（`WafDecision`/信誉/封禁列表 —— 绝不另算第二个独立评分）对敌对行为进行定性，并可将某个来源引向诱饵、放慢其响应并更详细地记录日志、构建可利用的事件，然后导出入侵指标（IoC）。它本身从不阻断流量 —— 网络封禁仍由 `omega-fire` 负责；Active Defense 负责观察、引流、减速和记录。

**威胁与评分**：每个来源（`IP + User-Agent 的 SHA-256 哈希`）都会累积评分（阻断性 `WAF-001` +10、信誉升级 +25、已知封禁 +25、对已分配诱饵发起 POST +30 —— 无新事件时每 15 分钟衰减 -5），并被定性为 `normal`/`suspicious`/`hostile`/`contained`（`contained` 还要求已知封禁）。`mode: monitor` 只观察不行动；`mode: enforce` 会真正执行以下操作。

**战争模式**（`options.active_defense.settings.war_mode`）：一个 `DefensePlaybook`（`actions: ["redirect_to_decoy", "enrich_log", "delay", "rate_limit", "create_incident", "export_ioc"]`），由可配置阈值触发，适用于任何非 `normal` 的来源：
- `enrich_log` —— 单独的 JSONL 日志（`var/log/active-defense-enriched.jsonl`，绝不与 WAF/生产日志混在一起），请求头经脱敏处理，HTTP 请求体按 `logging.capture_request_body` 进行哈希（SHA-256）或截断。
- `delay` —— 有上限并带抖动的减速（`war_mode.slowdown.minimum_ms`/`maximum_ms`/`jitter_ms`），绝不阻塞 asyncio 事件循环。
- `rate_limit` —— 针对每个来源的专用速率限制（`war_mode.rate_limit.requests`/`window_seconds`），在独立的键下复用与 WAF 相同的机制。
- `create_incident` —— 超过 `thresholds.incident_score` 时自动开启/合并事件。

**Deception**：`hostile`/`contained` 来源可以被分配到静态诱饵（`fake_admin`、`fake_cms`、`fake_api`、`fake_secrets` —— 看似可信但始终固定的响应，绝不真正读取文件或启动子进程），根据观察到的攻击类别选择（`deception.profiles.<名称>.match_attack_classes`，从 `scan`/`credential_stuffing`/`sqli`/`xss`/`path_traversal`/`upload_probe`/`api_probe`/`unknown` 中选一个或多个）。两个隔离级别，均为有意设计并如实记录：
- **级别 1**（进程内 fixture，`isolation_level: "fixture"`，默认）—— 明确的弱隔离：与生产环境同一进程、同一操作系统用户，之所以可以接受，只是因为 fixture 除了返回静态模板外什么也不做。配置档案的名称必须与上面 4 个 fixture 之一完全一致 —— 否则在校验时会被拒绝（`validate_active_defense_config`），以避免名称写错的诱饵从此静默地永不触发这一陷阱。
- **级别 2**（真正隔离的后端，`isolation_level: "proxy"`）—— 通过 `options.active_defense.settings.deception.decoy_zones.<名称>` 转发到独立进程（某个已在运行的服务器的 upstream `host`/`port`，绝不自动创建；绝不从 `options.reverse_proxy` 读取 —— 诱饵永远不会意外指向生产区域，由 `config check` 验证），复用与生产环境相同的出站反向代理机制（`serve_proxy()` —— 真实请求时 upstream 不可达：向攻击者返回 502，绝不崩溃）。

**设置 屏幕**（TUI，主动安全 → Active Defense → 设置）：对上述所有内容进行完整配置 —— 模式、启用战争模式、范围/操作/阈值/减速/请求限制、deception（默认行为、诱饵配置档案和诱饵区域的增删改查，每个字段都显示示例值）、IoC、存储和日志 —— 每次保存前都按与 CLI 相同的规则校验，永远无需手动编辑 `config/omega-serve.json`。任何更改之后都需要完整重启（Active Defense 从不热重新加载）。

**事件与 IoC**：每个事件都有完整时间线，提取指标（IP、哈希后的 User-Agent），导出为带版本的 JSON/仅限可共享 IoC 的 CSV/Markdown 报告，以及交换格式 **STIX 2.1**（可载入 OpenCTI、SIEM 等的包）和 **MISP**（通过 MISP 界面导入的事件），默认标记 TLP:AMBER —— 仅为本地文件，从不发送；每次导出都附带 `<export>.sha256` 文件（标准 `sha256sum` 格式）。若 `ioc.auto_export_on_close` 为真（默认），关闭事件时自动导出。过期状态和审计日志会自动清除，数据库大小有上限（防止占满磁盘）；`active-defense purge` 还会关闭重新沉寂的事件。

**模拟**：`active-defense simulate`（CLI）以及"模拟"按钮（TUI，主动安全 屏幕）会推算评分/级别并解释将会触发的每个操作 —— 严格的 dry-run，没有真实写入，不影响网络。

备份/恢复：`config backup --include-active-defense` 会将 sqlite 数据库（威胁/事件/分配）纳入归档 —— 其中绝无明文机密，因此不像 `--include-auth` 那样需要 `--confirm-secrets`。

## 11b. 敏感路径列表（WAF）

WAF 可以加载以文本文件形式存在的**可编辑列表**，每行一个路径（或关键词），入口为 **主动安全 → Custom → 添加 →「加载列表」**。默认从不加载任何内容：这是一个显式操作。

- **附带的参考列表**：`sensitive-paths-hostile`（298 个没有合法用途的路径：机密、备份、VCS、控制台……）和 `sensitive-paths-probe`（132 个探测路径，有时会由真实网站提供：`/admin`、`/api`、监控……）。加载时会在 `secure/waf/rules/keywords/` 中创建一份**本地副本**：您编辑的是这份副本，omega-serv 的更新绝不会覆盖它（「参考列表的新增内容」随后会逐项提议新条目）。
- **语法**：`/admin`（→ `/admin` 和 `/admin/xxx`，绝不包括 `/administrator`）、`/.git/`（其下的所有内容）、`/*.bak`（扩展名）、`!/api/v1`（例外，始终优先）。路径按引擎相同的方式解码（`%2e`、双重编码、全角字符）。
- **严重级别**：*观察*（仅记录日志，首次加载时建议使用），然后是 中（自身从不封禁）或 高（首次访问即返回 403）。
- **每个列表各自的重犯规则**：第 1 次访问 = 记录或拒绝；M 分钟内 N 次访问 = 临时应用层封禁（返回 451，即使经由 Tailscale）；反复被阻断 = 由 omega-jail 进行网络封禁。参考设置：hostile 10 分钟内 2 次 → 24 小时，探测 10 分钟内 5 次 → 1 小时。
- **绝不自动封禁** 本机、Tailscale（`100.64.0.0/10`）和本地网络（`options.waf.reputation.never_auto_block`）：只有外部流量会被封禁。在本地代理之后，`127.0.0.1` 的豁免要求 `trusted_proxy` 处于启用状态。`X-Forwarded-For` 从右向左读取：客户端无法自称为本地。
- **防护措施**：受保护的关键路径（`/`、`robots.txt`、`sitemap.xml`、`/.well-known/acme-challenge/`……），会拒绝可能命中实际所提供路由（别名、反向代理、Auth 区域、webroot）的阻断性列表，编辑器中的 **「对照我的日志检查」**（显示本会命中成功请求的行，一键添加例外）。
- **内置编辑器**：带行号的实时诊断、对某个路径进行「测试」、安全写入（保留权限和组、拒绝符号链接、检测外部修改）、检查服务账户可否读取（「修正权限」），以及**如实的**重新加载：若列表未通过检查，则拒绝并给出原因，服务器继续保留当前规则。

## 11c. 按目录和按 IP/网络的速率限制（WAF）

WAF 的速率限制（令牌桶，`options.waf.rate_limit`，默认每个 IP 60 次请求 / 60 秒）可以在 **主动安全 → 排除与速率限制** 中细化（或手动编辑 `rate_limit.path_policies` / `rate_limit.source_policies`）：

- **按目录的规则**（`prefix`、`requests`、`window_seconds`）：对该目录**取代**全局限制，并有自己的计数器（`requests: 0` = 不限）。最长前缀优先；`/images` 覆盖 `/images/a.png`，但绝不覆盖 `/images2`。典型场景是返回 429 的重型页面（图片画廊）。
- **按 IP/网络的规则**（`network`、`requests`、`window_seconds`、`trusted`）：原理相同；最精确的网络优先。优先级：目录，其次 IP/网络，最后全局限制。
- **对公众的封禁不变**：公网 IP 超限仍会在 `waf-alerts.log` 中记录为 `"action": "block"`，因此可被 omega-jail 封禁（10 分钟内 3 次拒绝 → 12 小时）。**可信来源** —— `never_auto_block` 网络或标记为 `trusted: true` 的规则 —— 仍会收到 429，但记录为 `"action": "throttle"`，jail 从不计入。
- **magnet 脚本**：它自己的速率限制（429 响应）从不计为一次检测，因此绝不会导致自动封禁；对于被目录或 IP/网络规则覆盖的请求，以原生规则为准，magnet 的 429 会被忽略（它的攻击特征仍然生效）。
- 速率规则**从不**关闭 WAF 检查；反之，检查排除（`exclusions.path_prefixes`）也从不解除速率限制。没有启用 `trusted_proxy` 时，覆盖 `127.0.0.1`/`::1` 的规则会被忽略（与 `never_auto_block` 相同的防护）。

## 12. 服务与运维

自动检测 systemd/OpenRC/runit（`service install/status/start/stop/restart/enable/disable/uninstall`）。生成的 systemd unit 默认应用不可协商的加固：`NoNewPrivileges`、`PrivateTmp`、`ProtectSystem=strict`、`ProtectHome`、`ReadWritePaths` 仅限 `var/`、必须使用专用用户/组、`UMask=0077`、`Restart=on-failure`。收到 SIGTERM 时优雅停止（处理完进行中的连接，可配置宽限期，然后强制关闭）；收到 SIGHUP 时热重新加载（仅 WAF 规则和 Auth 区域 —— bind/端口/TLS 和 Active Defense 不经完整重启就绝不能修改）。

## 13. 日志

`var/log/access.log`（Apache combined 格式 + `request_id`，转义以防日志注入）、`var/log/error.log`。按大小/保留文件数轮转（`logs.rotation`）。原生 WAF：`var/log/waf-alerts.log`（`options.waf.logging.path`）。magnet 脚本（§7）：`options.waf.magnet.paths.alerts_log`/`.blocklist_log`，默认为 `var/log/waf-magnet-alerts.log`/`var/log/waf-magnet-blocklist.log` —— 只有在 magnet 启用时才会自动加入日志库（按钮 *添加 Omega-Serv 的已知日志*）；而 `lnav` 总是会提供它们（缺失的文件在启动时会被直接忽略）。

### 13a. 远程来源（SSH）

在显式请求时，集中收集位于反向代理之后同一本地网络中的后端服务器日志（屏幕 **日志管理 → 日志库 → 远程来源（SSH）**）。「fetch」是一次手动、单次的操作，绝不是实时流或自动轮询：在单击 *立即获取* 时通过 `scp` 获取一份**副本**，写入 `var/log/remote/`，然后像普通日志一样加入日志库（*访问* 列 = `ssh`，*修改时间* 列 = **这次**获取的日期 —— 绝不是远程文件的日期）；再次获取只会用更新的副本替换之前的副本。

有意设置的防护措施（完整研究见 `OMEGA-SERV_ETUDE-FAISABILITE_LOGS_DISTANTS.md`）：不进行任何自动网络扫描，未经显式配置绝不连接（标签/主机/远程路径，用户/端口/私钥可选 —— 留空时由 `ssh`/`~/.ssh/config` 决定，就像手动输入命令一样），绝不询问或存储密码（私钥只通过路径引用，Omega-serv 绝不读取或存储它），传输前不检查大小。`scp` 能力在本地的 **能力清单** 中检测（仅检测程序是否存在，绝不测试主机可达性）；有意不考虑 Samba（YAGNI，直到确认存在真实需求）。

## 14. 测试

```bash
source .venv/bin/activate
lint-imports        # 检查 8 项分层契约
pytest -q           # 2485 个测试
ruff check .
mypy src
```

结构：`tests/unit/`（领域/应用，测试替身）、`tests/integration/`（在真实 TCP 套接字上运行的真实 asyncio 服务器、以子进程运行的真实 `openssl`、针对完整临时项目执行的真实 CLI 命令、通过 Textual 的 `Pilot` API 测试交互式界面 - 绝不截图）、`tests/security/`（针对 HTTP 解析器和路径解析器的 `hypothesis` 属性测试）。

## 15. 范围之外

- 原生 CGI（仅 FastCGI/PHP-FPM）
- mTLS（通过证书进行客户端认证）、OCSP stapling
- 外部 CA / 第三方机构 CSR、完整的 CRL 分发
- Active Defense：与 `omega-fire` 封禁事件的真正集成（受阻于 `omega-fire` 一侧，它目前没有提供任何读取接口）

---

> 🔒 OMEGA-SERV —— 一个稳固、完整、安全且具防御性的 Web 服务器。
