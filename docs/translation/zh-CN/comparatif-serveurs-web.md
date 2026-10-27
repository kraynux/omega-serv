<!-- Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE) -->

# omega-serv 与市面上的 Web 服务器对比

**实测对比：nginx · lighttpd · Caddy · Apache · Traefik · omega-serv 2.0**

🌐 [Français](../../comparatif-serveurs-web.md) · [English](../en/comparatif-serveurs-web.md) · [Español](../es/comparatif-serveurs-web.md) · [Português (Brasil)](../pt-BR/comparatif-serveurs-web.md) · [Italiano](../it/comparatif-serveurs-web.md) · [Deutsch](../de/comparatif-serveurs-web.md) · [Nederlands](../nl/comparatif-serveurs-web.md) · [Polski](../pl/comparatif-serveurs-web.md) · [Русский](../ru/comparatif-serveurs-web.md) · **中文** · [Tiếng Việt](../vi/comparatif-serveurs-web.md) · [ไทย](../th/comparatif-serveurs-web.md) · [Bahasa Indonesia](../id/comparatif-serveurs-web.md) · [日本語](../ja/comparatif-serveurs-web.md) · [한국어](../ko/comparatif-serveurs-web.md) · [हिन्दी](../hi/comparatif-serveurs-web.md) · [العربية](../ar/comparatif-serveurs-web.md)

本文档介绍 omega-serv 在主流 Web 服务器中的定位。它并不试图评出“最好的服务器”：每个工具满足的需求各不相同。本文提供三方面内容：

1. **真实测量**：在同一台机器上，用同一个客户端、同一批文件完成，并且可以复现；
2. **功能对比**：每项功能都对照各服务器的官方文档核实过（链接见文末），并区分哪些是内置的，哪些需要模块或插件；
3. omega-serv **真正多出来的能力**，以及其他服务器**比它做得更好**的地方。

下文所有数字均于 2026 年 10 月 26 日实测得出。没有任何数字取自其他网站，也没有任何估算。

---

## 目录

1. [概要](#1-概要)
2. [测量方法](#2-测量方法)
3. [性能：omega-serv 与 nginx、lighttpd、Caddy 对比](#3-性能omega-serv-与-nginxlighttpdcaddy-对比)
4. [omega-serv 1.0 → 2.0：变化及实测](#4-omega-serv-10--20变化及实测)
5. [功能对比](#5-功能对比)
6. [管理方式与易用性](#6-管理方式与易用性)
7. [omega-serv 多出来的能力](#7-omega-serv-多出来的能力)
8. [其他服务器做得更好的地方](#8-其他服务器做得更好的地方)
9. [不同用途选择哪种服务器](#9-不同用途选择哪种服务器)
10. [复现测量](#10-复现测量)
11. [资料来源](#11-资料来源)

---

## 1. 概要

- **小文件的原始吞吐量**：用 C 编写的 nginx 和 lighttpd，每秒处理的请求数是用 Python 编写的 omega-serv 的 **10 到 20 倍**。用 Go 编写的 Caddy 介于两者之间。这是本质上的差距，不是调优问题：omega-serv 并不瞄准这一领域。
- **大文件**：从 2.0 起，omega-serv 把发送工作交给内核（`sendfile`）。在这台机器上，它因此达到与 nginx、lighttpd、Caddy **同一数量级的吞吐量**：2.1 GB/s，对比 2.0 至 2.4 GB/s。
- **内存**：lighttpd（1 MB）和 nginx（4 至 5 MB）依然遥不可及。omega-serv 在 1 个进程、有负载时保持在 30 MB 以下，Caddy 约 55 MB。
- **从 1.0 到 2.0**：大文件吞吐量提高到 2.8 倍；大文件下载期间的内存降为原来的 1/45；使用 2 个进程（boost 模式）时小文件性能最多提升 50%；Active Defense 的开销降为原来的 1/12。
- **omega-serv 多出来的能力**：通过终端界面（TUI）完成全部管理，支持 17 种语言；内置 WAF 和主动防御；多进程下依然精确的安全限制；导入 lighttpd 的 mod_magnet 脚本；管理多个实例。
- **它没有的**：HTTP/2 和 HTTP/3、Docker/Kubernetes 服务发现、内置的 ACME 客户端（它通过 Certbot 实现）、C 语言服务器的吞吐量。

---

## 2. 测量方法

### 机器与软件

| 项目 | 值 |
|---|---|
| 处理器 | Intel Core i5 M480，2.67 GHz（2010 年）：2 个物理核心，4 个线程 |
| 内存 | 8 GB |
| 系统 | Manjaro Linux，内核 6.18 |
| 网络 | 本地回环（127.0.0.1） |
| 压测客户端 | [oha](https://github.com/hatoo/oha) 1.16.0（用 Rust 编写） |
| nginx | 1.30.4（Manjaro 软件包） |
| lighttpd | 1.4.85（Manjaro 软件包） |
| Caddy | 2.11.4（Manjaro 软件包） |
| omega-serv | 1.0.0（已发布的归档）和 2.0.0，运行于 Python 3.14.7 |

Apache 和 Traefik 没有测量，因为这台机器上没有安装它们。而且 Traefik 并不是文件服务器（见 §5）。因此这两个服务器只出现在功能对比中。

### 测试流程

- **处理器隔离**：每个服务器绑定到物理核心 0（线程 0 和 2），客户端绑定到物理核心 1（线程 1 和 3）。这样客户端不会抢占服务器的时间，所有服务器拥有完全相同的资源。
- **所有服务器使用相同文件**：`small.html`（1 KB）、`medium.png`（100 KB）和 `large.bin`（5 MB），从同一个目录提供。
- **所有服务器都开启访问日志**，因为生产环境中的服务器会记录日志。
- **明文 HTTP/1.1，持久连接（keep-alive）**。1 KB 和 100 KB 文件使用 32 个并发连接，5 MB 文件使用 8 个。
- **时长**：每个文件、每种配置各 10 秒。
- **重复次数**：3 轮完整测试，交错进行（第 1 轮测完所有服务器，再进行第 2 轮，依此类推）。表格给出三轮的**中位数**。
- **内存**：服务器所有进程的 PSS（*Proportional Set Size*）之和。与 RSS 不同，多个进程共享的内存页只计算一次。在空闲时和负载后各记录一次。
- **配置**：nginx、lighttpd 和 Caddy 使用基本配置（静态文件、访问日志）。omega-serv 使用 `standard` 配置档，先关闭 WAF，再开启 WAF 并加载全部自带规则。
- **进程数**：每个服务器先用 1 个、再用 2 个进程测量（nginx `worker_processes`、lighttpd `server.max-worker`、Caddy `GOMAXPROCS`、omega-serv `server.workers`）。

### 需要了解的局限

- **机器配置较低且老旧。** 在新服务器上，绝对数值会高得多。有意义的是同一次测试中各服务器之间的**比例**。
- **不同测试批次之间的波动**：根据机器后台负载，约为 10% 至 30%。同一批次内各轮结果保持一致：omega-serv 和 Caddy 的差异小于 5%，nginx 和 lighttpd 稍大，因为它们极高的吞吐量对机器上的其他负载更敏感。
- **本地回环**：测量没有经过真实网络。在真实网络中，大文件的吞吐量几乎总是受带宽限制，而不是受服务器限制。
- **这些测量未使用 TLS**。使用 HTTPS 时，omega-serv 无法使用 `sendfile`，会分块发送文件。
- **原始数据**：随本文档一同发布于 [`docs/benchmarks/2026-10-26-campagne-brute.txt`](../../benchmarks/2026-10-26-campagne-brute.txt)。

---

## 3. 性能：omega-serv 与 nginx、lighttpd、Caddy 对比

### 小文件（1 KB）：每秒请求数

| 服务器 | 1 个进程 | 2 个进程 | p99 延迟（1 个进程） |
|---|---:|---:|---:|
| lighttpd 1.4.85 | 25,521 | 29,700 | 4.5 ms |
| nginx 1.30.4 | 14,054 | 18,315 | 4.7 ms |
| Caddy 2.11.4 | 3,697 | 5,345 | 25.3 ms |
| **omega-serv 2.0** | **1,358** | **1,953** | **37.5 ms** |
| omega-serv 2.0 + WAF | 1,130 | 1,617 | 48.5 ms |
| omega-serv 1.0 | 1,304 | — | 41.2 ms |

### 中等文件（100 KB）：每秒请求数

| 服务器 | 1 个进程 | 2 个进程 |
|---|---:|---:|
| lighttpd | 11,635 | 13,037 |
| nginx | 8,024 | 9,555 |
| Caddy | 3,280 | 4,344 |
| **omega-serv 2.0** | **1,247** | **1,629** |
| omega-serv 2.0 + WAF | 1,012 | 1,347 |
| omega-serv 1.0 | 1,064 | — |

### 大文件（5 MB）：吞吐量

| 服务器 | 1 个进程 | 2 个进程 |
|---|---:|---:|
| lighttpd | 2,379 MB/s | 2,407 MB/s |
| nginx | 2,242 MB/s | 1,981 MB/s |
| Caddy | 2,165 MB/s | 2,229 MB/s |
| **omega-serv 2.0** | **1,658 MB/s** | **2,115 MB/s** |
| omega-serv 1.0 | 584 MB/s | — |

### 内存（PSS，服务器所有进程）

| 服务器 | 空闲时 | 负载后 |
|---|---:|---:|
| lighttpd（1 或 2 个进程） | 1 MB | 1 MB |
| nginx（1 或 2 个进程） | 4 至 5 MB | 4 至 5 MB |
| **omega-serv 2.0（1 个进程）** | **26 MB** | **30 MB** |
| omega-serv 2.0（2 个进程） | 39 MB | 48 MB |
| Caddy | 50 MB | 56 MB |
| omega-serv 1.0 | 22 MB | 100 MB |

### 解读

- **在小文件和中等文件上**，与 nginx、lighttpd 的差距是一个数量级（10 至 20 倍）。这是用 Python 编写服务器的代价：每个请求都要经过解释器，而 nginx 和 lighttpd 用编译后的 C 代码处理。boost 模式缩小了差距，但无法消除。
- **在大文件上**，各服务器趋于接近，因为数据由内核复制（`sendfile`）。使用 2 个进程时，omega-serv 2.0 达到 2.1 GB/s，与其他服务器处于同一区间（2.0 至 2.4 GB/s）。
- **omega-serv 的 WAF 在小文件上约有 17% 的开销**：它会检查每个请求。nginx、lighttpd 和 Caddy 是在没有 WAF 的情况下测量的；为这些服务器加装 WAF（ModSecurity、Coraza）同样有开销，本文未测量。
- **换个角度看这些数字**：在这台 2010 年的机器上，每秒 1,300 个请求相当于每天超过 1.1 亿个请求。这远远超过个人网站、内部服务或实验环境的需求，而这些正是 omega-serv 面向的用途。

---

## 4. omega-serv 1.0 → 2.0：变化及实测

### 性能

两个版本在同一批次、同一台机器上，按同一流程测量。

| 测量项 | 1.0.0 | 2.0.0 | 变化 |
|---|---:|---:|---:|
| 小文件（1 KB），1 个进程 | 1,304 次/秒 | 1,358 次/秒 | +4% |
| 小文件（1 KB），boost 模式 2 个进程 | — | 1,953 次/秒 | 相比 1.0 **+50%** |
| 小文件开启 WAF，1 个进程 | 1,097 次/秒 | 1,130 次/秒 | +3% |
| 小文件开启 WAF，2 个进程 | — | 1,617 次/秒 | 相比 1.0 **+47%** |
| 100 KB 文件，1 个进程 | 1,064 次/秒 | 1,247 次/秒 | +17% |
| 大文件（5 MB），1 个进程 | 584 MB/s | 1,658 MB/s | **×2.8** |
| 大文件（5 MB），2 个进程 | — | 2,115 MB/s | 相比 1.0 **×3.6** |
| 负载后内存，1 个进程 | 100 MB | 30 MB | **÷3** |

### 同时进行的大文件下载

测试：同时下载 3 个 300 MB 的文件，同时持续请求一个小页面。两次运行结果完全相同。

| 测量项 | 1.0.0 | 2.0.0 |
|---|---:|---:|
| 服务器内存峰值 | 1,835 MB | 40 MB |
| 下载期间小页面：中位数 | 3 至 4 ms | 2 ms |
| 下载期间小页面：最差情况 | 1.7 至 1.8 s | 5 ms |

1.0 在发送前会把每个文件完整读入内存。2.0 则分块发送，或交给内核处理：内存不再取决于文件大小，下载期间服务器依然能及时响应。

### 主动防御的开销

Active Defense 对每个可疑请求进行一次威胁观察的开销，在磁盘（ext4）上对 2,000 次观察进行测量：

| 测量项 | 1.0.0 | 2.0.0 |
|---|---:|---:|
| 中位数 | 2.84 ms | 0.23 ms |
| p99 | 11.6 ms | 2.3 ms |
| 最大值 | 18 至 20 ms | 37 至 46 ms |

中位数降为原来的 1/12。但 2.0 的最大值更高：出现了几个孤立的峰值，原因是 SQLite 日志定期写入磁盘。

### 2.0 新增的功能

**追平市场标准**：nginx、lighttpd、Caddy 和 Apache 早已具备以下全部功能，omega-serv 在此补齐。

- 条件请求（ETag、Last-Modified、304 响应）：重新加载页面时，只重新下载有变化的内容。
- 部分请求（Range、206/416）：断点续传、在视频中跳转。
- 通过 `sendfile` 或分块发送文件，内存占用稳定。
- 预压缩文件（`.gz`、`.br`），放在原文件旁边。
- 按文件类型设置默认 Cache-Control（图片、字体、CSS/JS），可调整。
- 多个服务器进程（boost 模式，`server.workers`）。

**更全面的功能：**

- **完整的反向代理。** 1.0 只有简单转发（轮询、到上游服务器的 TLS、WebSocket）。2.0 新增：
  - 6 种负载分配策略，共 7 种；
  - 会话亲和与基于请求头的路由；
  - 上游服务器的被动和主动健康检查；
  - 响应缓存；
  - 防止过载和防止代理环路；
  - 运行时管理。
- **按目录和按地址或网络的速率限制**，作为全局限制的补充。
- **多进程共享的安全计数器**（见 §7）。
- **现成的敏感路径列表**，带观察模式和内置编辑器。
- **导入 lighttpd 的 mod_magnet 脚本**（见 §7）。
- **界面支持 17 种语言**，访客所见页面和导出内容可单独设置语言。
- **日志功能全面重做**：
  - 日志库；
  - 三种查看器，其中包括 lnav；
  - 通过 SSH 获取远程日志。

---

## 5. 功能对比

图例：
- ✅ 内置；
- 🧩 项目官方模块，需要启用或安装；
- 🔌 第三方模块或插件；
- ⚙️ 借助外部工具；
- ❌ 不具备。

“商业版”表示该功能仅在付费版本中提供。

### HTTP 服务

| 功能 | nginx | lighttpd | Caddy | Apache | Traefik | omega-serv 2.0 |
|---|---|---|---|---|---|---|
| 提供静态文件 | ✅ | ✅ | ✅ | ✅ | ❌（仅代理） | ✅ |
| ETag / 304 / Range | ✅ | ✅ | ✅ | ✅ | — | ✅ |
| 预压缩文件 `.gz` / `.br` | ✅ `gzip_static`（`.br`：🔌） | 🔌 Lua 脚本（mod_magnet） | ✅ `precompressed` | 🧩 mod_rewrite 方案 | — | ✅ |
| 实时压缩 | ✅ | ✅ mod_deflate | ✅ | 🧩 mod_deflate | ✅ 中间件 | ❌ |
| HTTP/2 | ✅ | ✅ | ✅ | 🧩 mod_http2 | ✅ | ❌ |
| HTTP/3（QUIC） | ✅ | ❌ | ✅ | ❌ | ✅ | ❌ |
| 通过 FastCGI 运行 PHP | ✅ | ✅ | ✅ | ✅ | ❌ | ✅ |
| 多进程或多核 | ✅ worker | ⚠️ `max-worker`，官方文档不推荐 | ✅（Go，所有核心） | ✅ MPM | ✅（Go） | ✅ `server.workers` |

### 反向代理

| 功能 | nginx | lighttpd | Caddy | Apache | Traefik | omega-serv 2.0 |
|---|---|---|---|---|---|---|
| 负载均衡 | ✅ 轮询、最少连接、哈希 | ✅ fair、round-robin、hash、sticky | ✅ 约十几种策略 | 🧩 mod_proxy_balancer | ✅ wrr、p2c、hrw、least-time | ✅ 7 种策略，包括按实际负载 |
| 被动健康检查（剔除故障服务器） | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| 主动健康检查（定期探测） | 商业版（NGINX Plus） | ❌ | ✅ | 🧩 mod_proxy_hcheck | ✅ | ✅ |
| 响应缓存 | ✅ `proxy_cache` | ❌ | 🔌 | 🧩 mod_cache | 商业版 | ✅ |
| WebSocket | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| 服务发现（Docker、Kubernetes） | 🔌 | ❌ | 🔌 | ❌ | ✅（项目核心） | ❌ |

### TLS

| 功能 | nginx | lighttpd | Caddy | Apache | Traefik | omega-serv 2.0 |
|---|---|---|---|---|---|---|
| 自动证书（ACME、Let's Encrypt） | 🧩 `ngx_http_acme_module` | ⚙️ Certbot | ✅ 默认开启 | 🧩 mod_md | ✅ | ⚙️ Certbot，带内置向导和定时续期 |
| 本地 CA | ❌ | ❌ | ✅ 内部 CA（自动签发） | ❌ | ❌ | ✅ 生成、签署 CSR、吊销 |

### 安全

| 功能 | nginx | lighttpd | Caddy | Apache | Traefik | omega-serv 2.0 |
|---|---|---|---|---|---|---|
| 按客户端限速 | ✅ `limit_req` | ⚠️ mod_evasive（仅限并发连接数） | 🔌 caddy-ratelimit | 🔌 mod_evasive、mod_qos | ✅ 中间件 | ✅ |
| 多进程共享限制 | ✅ 共享内存区 | ❌ 按进程分别计数 | —（单进程） | 取决于模块 | 单实例；多实例需 Redis | ✅ 共享内存 |
| WAF（SQLi/XSS 特征、扫描器…） | 🔌 ModSecurity，商业版（App Protect） | ❌（需自行编写 Lua 脚本） | 🔌 Coraza | 🔌 ModSecurity | 🔌 插件 | ✅ 内置 |
| 带过期时间的封禁列表、累犯判定 | ⚙️ fail2ban | ⚙️ fail2ban | ⚙️ fail2ban | ⚙️ fail2ban | ⚙️ | ✅ 内置 |
| 诱饵、战争模式、事件、IoC 导出 | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ Active Defense |
| 配置安全审计 | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ `audit security` |
| 观察模式（只记录不拦截） | 取决于模块 | — | 取决于插件 | ✅ ModSecurity `DetectionOnly` | 取决于插件 | ✅ |

### 可扩展性

| 功能 | nginx | lighttpd | Caddy | Apache | Traefik | omega-serv 2.0 |
|---|---|---|---|---|---|---|
| 脚本语言 | 🧩 njs（JavaScript）；🔌 Lua（OpenResty） | ✅ Lua（mod_magnet） | Go 模块（需重新编译） | 🧩 mod_lua | Go 或 WebAssembly 插件 | 🔌 导入 mod_magnet 脚本（`magnet` 选项） |
| 模块生态 | 非常丰富 | 针对性强 | 丰富 | 非常丰富 | 丰富 | 无：一切均已内置 |

---

## 6. 管理方式与易用性

| 服务器 | 主要管理方式 | 界面 | 不中断重新加载 |
|---|---|---|---|
| nginx | 配置文件 | 无（仪表板：NGINX Plus，商业版） | ✅ `nginx -s reload` |
| lighttpd | 配置文件 | 无（mod_status，只读） | ✅ 平滑重启 |
| Caddy | Caddyfile 或 JSON | REST 管理 API | ✅ 通过 API |
| Apache | 配置文件和 `.htaccess` | 无（mod_status，只读） | ✅ `graceful` |
| Traefik | 容器标签、文件或 Kubernetes | Web 仪表板（只读） | ✅ 动态配置 |
| omega-serv | 终端界面（TUI）和命令行（CLI）；无需手动编辑 JSON 文件 | **完整的 TUI，支持键盘和鼠标，17 种语言，内置帮助** | ✅ 适用于大多数设置；修改端口、TLS 和进程数时会提示需要重启 |

实际使用中，omega-serv 的配置、安全、日志、系统服务、备份和实例都在同一个界面中管理。每项设置在写入前都会给出说明并进行检查。使用其他服务器时，需要编辑文本文件，再借助各种独立工具（Certbot、fail2ban、logrotate、ModSecurity、监控工具…）。

相应地，nginx、Apache 和 Caddy 的“配置文件”方式非常适合自动化（Ansible、容器、版本控制）。omega-serv 有可用于脚本的 CLI，但其自动化生态仍然有限。

---

## 7. omega-serv 多出来的能力

本节只列出被比较的服务器在不借助第三方模块或外部工具的情况下都无法直接提供的能力。

1. **通过终端界面完成全部管理。**
   - 界面覆盖整个服务器：站点、安全、日志、服务、备份和实例。
   - 支持键盘和鼠标操作，可在没有图形环境的服务器上使用，也可以通过 SSH 使用。
   - 支持 17 种语言，并解释每一项设置。
   - 其他服务器没有管理界面（nginx、lighttpd、Apache），或者只有 API（Caddy）或只读仪表板（Traefik）。
2. **内置主动安全，无需拼装模块。**
   - WAF 包括特征规则、可编辑的路径列表、累犯判定、带过期时间的封禁列表、信誉评分和观察模式。
   - Active Defense 增加了诱饵、战争模式、事件跟踪、入侵指标（IoC）导出和空跑模拟。
   - 在其他服务器上，这些功能需要组合 ModSecurity 或 Coraza、规则集和 fail2ban 才能实现。
3. **多进程下依然精确的安全限制。**
   - 在 boost 模式下，速率限制和 WAF 累犯计数在各进程之间通过共享内存共享。因此攻击者无法通过进程数量成倍放大自己的限额。
   - lighttpd 的文档描述了相反的情况：使用 `server.max-worker` 时，`mod_evasive` 和 `mod_status` 在每个进程中分别计数。
   - nginx 也共享其计数器（`limit_req` 区域），但没有内置 WAF。
4. **导入 lighttpd 的 mod_magnet 脚本。**
   - 已经为 lighttpd 编写的 Lua 防护脚本可以直接导入，无需重写。
   - 它在内置防护之上叠加，永远不会削弱内置防护，并且在启用前会检查兼容性。
5. **管理多个实例。**
   - 注册表记录所有实例，界面可以在实例之间切换。
   - 还可以彻底卸载某个实例。
6. **配置安全审计**：`audit security` 命令仅提供信息，从不阻断，并返回可在脚本中使用的退出码。
7. **远程日志来源。**
   - 界面可按需通过 SSH 获取另一台服务器的日志，不保存密码。
   - 可以用 lnav 打开，并与本地日志合并查看。
8. **无法关闭的 HTTP 加固**，安装后即生效，与配置档无关：
   - 严格校验 Host 请求头；
   - 拒绝 Content-Length / Transfer-Encoding 歧义；
   - 安全响应头和 CSP，错误页面也不例外；
   - 安全地读取 X-Forwarded-For；
   - 拒绝以 root 身份启动。

---

## 8. 其他服务器做得更好的地方

- **吞吐量和延迟**：nginx 和 lighttpd 处理的小请求数是 omega-serv 的 10 到 20 倍，延迟低 8 到 10 倍。对于高流量网站、公共 API 或 CDN，应该选择它们。
- **内存**：lighttpd（1 MB）和 nginx（4 至 5 MB）适合资源非常受限的机器（嵌入式设备、入门级树莓派、小型容器）。
- **协议**：其他服务器都支持 HTTP/2，nginx、Caddy 和 Traefik 还支持 HTTP/3。omega-serv 只支持 HTTP/1.1。
- **自动 HTTPS**：Caddy 和 Traefik 默认内置，nginx（`ngx_http_acme_module`）和 Apache（`mod_md`）通过官方模块提供。omega-serv 交由 Certbot 完成，并提供向导和定时续期。
- **容器环境**：Traefik 的自动服务发现（Docker、Kubernetes）在 omega-serv 中没有对应功能。
- **生态**：nginx 和 Apache 拥有数以千计的模块、教程和集成。Caddy 提供基于 Go 的模块系统。omega-serv 是一个年轻的项目，由一个人维护。
- **实时压缩**：omega-serv 只提供已经压缩好的文件。

---

## 9. 不同用途选择哪种服务器

| 需求 | 推荐选择 |
|---|---|
| 高流量网站、公共 API、CDN、最高吞吐量 | **nginx** |
| 资源非常受限的机器、嵌入式、静态文件 | **lighttpd** |
| 快速上手、自动 HTTPS、配置简短 | **Caddy** |
| 老旧 PHP 应用、`.htaccess`、共享主机 | **Apache** |
| Docker、Kubernetes、微服务 | **Traefik** |
| 小型网站、内部服务、实验环境、VPN、无需编辑文件的管理 | **omega-serv** |
| 对外暴露的服务器，希望在同一个界面中查看和控制安全（WAF、封禁、诱饵） | **omega-serv** |
| 内部反向代理，需要负载分配、健康检查和缓存，并通过界面管理 | **omega-serv** |
| 学习 HTTP 加固和主动防御 | **omega-serv** |

这些工具也可以组合使用。例如：
- nginx 或 Traefik 部署在面向互联网的前端，后面由 omega-serv 承载内部服务及其安全与管理；
- omega-serv 作为内部反向代理，部署在多个应用服务器之前。

---

## 10. 复现测量

工具随代码仓库提供，位于 `tools/bench/`。需要安装 nginx、lighttpd、Caddy 和 oha，以及 omega-serv 的开发环境（`.venv`）。

```sh
# 1. 准备测量目录（测试文件、配置、omega-serv 1.0 和 2.0）
tools/bench/compare/setup.sh /路径/测量 omega-serv-1.0.0.tar.gz

# 2. 12 种配置，3 次交错重复（约 22 分钟）
tools/bench/compare/campaign.sh /路径/测量 > 结果.txt

# 3. 中位数
python3 tools/bench/compare/summarize.py 结果.txt

# 大文件下载（内存和响应能力），先测 2.0，再测 1.0
.venv/bin/python tools/bench/bigfile.py
BENCH_SRC=/路径/测量/v1-archive/omega-serv/src \
BENCH_EXTRA_PATH=/路径/测量/v1-archive/omega-serv/vendor/omega-lib/src \
  .venv/bin/python tools/bench/bigfile.py

# 测量任何已在运行的其他服务器，无需 oha
python3 tools/bench/bench_any.py --make-files /srv/test-webroot
python3 tools/bench/bench_any.py --port 8080
```

默认情况下，服务器绑定到线程 0 和 2，客户端绑定到线程 1 和 3，与测量机器相对应。请通过 `SRV_CPUS` 和 `CLI_CPUS` 变量，按自己的处理器调整这一分配（`lscpu -e` 可查看拓扑）。

发布自己的结果时，请注明机器、版本、处理器分配和三次重复的数据。

---

## 11. 资料来源

其他服务器的功能依据其官方文档（查阅日期：2026 年 10 月 26 日）。

**nginx**
- [速率限制 `limit_req`（共享内存区）](https://nginx.org/en/docs/http/ngx_http_limit_req_module.html)
- [预压缩文件 `gzip_static`](https://nginx.org/en/docs/http/ngx_http_gzip_static_module.html)
- [官方 ACME 模块 `ngx_http_acme_module`](https://nginx.org/en/docs/http/ngx_http_acme_module.html)
- [负载均衡（`upstream`）](https://nginx.org/en/docs/http/ngx_http_upstream_module.html)
- [HTTP/3](https://nginx.org/en/docs/http/ngx_http_v3_module.html)
- [nginx 的 ModSecurity 连接器](https://github.com/owasp-modsecurity/ModSecurity-nginx)

**lighttpd**
- [`server.max-worker`：不推荐，mod_status 和 mod_evasive 按进程计数](https://redmine.lighttpd.net/projects/lighttpd/wiki/Server_max-workerDetails)
- [mod_magnet（Lua 脚本）](https://redmine.lighttpd.net/projects/lighttpd/wiki/Docs_ModMagnet)
- [mod_deflate（压缩、缓存）](https://redmine.lighttpd.net/projects/lighttpd/wiki/Mod_deflate)
- [mod_proxy（负载均衡、被动健康检查、WebSocket）](https://redmine.lighttpd.net/projects/lighttpd/wiki/Docs_ModProxy)
- [mod_evasive（每个地址的并发连接数）](https://redmine.lighttpd.net/projects/lighttpd/wiki/Docs_ModEvasive)

**Caddy**
- [自动 HTTPS](https://caddyserver.com/docs/automatic-https)
- [`file_server` 与 `precompressed`](https://caddyserver.com/docs/caddyfile/directives/file_server)
- [`reverse_proxy`（策略、主动和被动健康检查）](https://caddyserver.com/docs/caddyfile/directives/reverse_proxy)
- [管理 API](https://caddyserver.com/docs/api)
- [限速插件 caddy-ratelimit](https://github.com/mholt/caddy-ratelimit)
- [Caddy 的 Coraza WAF](https://github.com/corazawaf/coraza-caddy)
- [caddy-docker-proxy](https://github.com/lucaslorentz/caddy-docker-proxy)

**Apache HTTP Server**
- [mod_md（ACME）](https://httpd.apache.org/docs/2.4/mod/mod_md.html)
- [mod_proxy_balancer](https://httpd.apache.org/docs/2.4/mod/mod_proxy_balancer.html)
- [mod_proxy_hcheck](https://httpd.apache.org/docs/2.4/mod/mod_proxy_hcheck.html)
- [mod_http2](https://httpd.apache.org/docs/2.4/mod/mod_http2.html)
- [mod_deflate，预压缩内容](https://httpd.apache.org/docs/2.4/mod/mod_deflate.html)
- [ModSecurity](https://github.com/owasp-modsecurity/ModSecurity)

**Traefik**
- [`ratelimit` 中间件（每个实例内存计数，可选 Redis）](https://doc.traefik.io/traefik/reference/routing-configuration/http/middlewares/ratelimit/)
- [ACME](https://doc.traefik.io/traefik/https/acme/)
- [Providers（Docker、Kubernetes…）](https://doc.traefik.io/traefik/providers/overview/)

**测量工具**
- [oha](https://github.com/hatoo/oha)

---

*本对比由 kraynux 为 omega-serv 2.0.0 制作：测量日期为 2026 年 10 月 26 日。测量仅涉及一台机器。如需做容量决策，请使用随附工具在自己的硬件上测量。*
