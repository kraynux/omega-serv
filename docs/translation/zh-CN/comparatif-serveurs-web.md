<!-- Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE) -->

# omega-serv 与市面上的 Web 服务器对比

**基于实测的对比：nginx · lighttpd · Apache · Caddy · Traefik · omega-serv 2.5**

🌐 [Français](../../comparatif-serveurs-web.md) · [English](../en/comparatif-serveurs-web.md) · [Español](../es/comparatif-serveurs-web.md) · [Português (Brasil)](../pt-BR/comparatif-serveurs-web.md) · [Italiano](../it/comparatif-serveurs-web.md) · [Deutsch](../de/comparatif-serveurs-web.md) · [Nederlands](../nl/comparatif-serveurs-web.md) · [Polski](../pl/comparatif-serveurs-web.md) · [Русский](../ru/comparatif-serveurs-web.md) · **中文** · [Tiếng Việt](../vi/comparatif-serveurs-web.md) · [ไทย](../th/comparatif-serveurs-web.md) · [Bahasa Indonesia](../id/comparatif-serveurs-web.md) · [日本語](../ja/comparatif-serveurs-web.md) · [한국어](../ko/comparatif-serveurs-web.md) · [हिन्दी](../hi/comparatif-serveurs-web.md) · [العربية](../ar/comparatif-serveurs-web.md)

本文档说明 omega-serv 在最常用的 Web 服务器中处于什么位置。它不打算评出“最好的服务器”：每个工具满足不同的需求，各有长处。它提供三样东西：

1. **真实测量**，在**三台**差异很大的**机器**上进行，使用相同的客户端、相同的文件和相同的流程，并且可以复现；
2. **功能对比**，每一项都对照相应服务器的官方文档核实（链接在文末），并区分内置功能与需要模块或插件的功能；
3. omega-serv **真正额外提供**了什么，以及其他服务器**比它做得更好**的地方。

所有性能测量均于 2026 年 11 月 3 日和 4 日完成。没有任何数字取自其他网站或经过估算。原始数据随本文档一同发布。

---

## 目录

1. [概要](#1-概要)
2. [如何阅读本对比](#2-如何阅读本对比)
3. [测量方法](#3-测量方法)
4. [性能：omega-serv 对比 nginx、lighttpd、Apache 和 Caddy](#4-性能omega-serv-对比-nginxlighttpdapache-和-caddy)
5. [omega-serv 各版本：1.0 → 2.0 → 2.5](#5-omega-serv-各版本10--20--25)
6. [功能对比](#6-功能对比)
7. [管理与易用性](#7-管理与易用性)
8. [omega-serv 额外提供的](#8-omega-serv-额外提供的)
9. [其他服务器做得更好的地方](#9-其他服务器做得更好的地方)
10. [什么场景用哪个服务器](#10-什么场景用哪个服务器)
11. [复现测量](#11-复现测量)
12. [来源](#12-来源)

---

## 1. 概要

- **omega-serv 有两个引擎。** **Python 引擎**处理一切。**原生引擎**用 C++ 编写，在 2.5 中引入，自行响应请求；Python 保留配置和安全决策，而原生引擎会自行识别出不匹配任何 WAF 规则的请求。
- **使用原生引擎、不启用 WAF 时**，omega-serv 提供小文件的速度**约为 nginx 的 0.7**，三台机器上都是如此。因此它**领先于 Apache 和 Caddy，落后于 nginx 和 lighttpd**。
- **使用 Python 引擎时**，omega-serv 远远落后于其他所有服务器：**为 nginx 速度的 3–11%**。
- **启用 WAF 时**，omega-serv 会检查每个请求，而其他被测服务器不做这件事。使用原生引擎时，它在机器 A 和 B 上达到 nginx（无 WAF）的 **0.53–0.56**，在机器 C 上为 1.07（4 个核心对 2 个）：WAF 只让它损失 5–22% 的吞吐量。它仍领先于未启用 WAF 测量的 Apache 和 Caddy。
- **中等文件（100 KB）**：这是原生引擎目前的弱点，为 nginx 的 **0.3–0.6**，落后于 Apache。
- **大文件（5 MB）**：nginx、lighttpd、Apache 和原生 omega-serv 的吞吐量处于同一量级。Caddy 在最快的机器上明显较慢。
- **内存**：lighttpd（1 MB）、nginx（4–5 MB）和 Apache（4–9 MB）非常节省。omega-serv 视模式占用 **30–65 MB**，Caddy 为 **50–67 MB**。
- **omega-serv 额外提供的**：在终端界面中完成全部管理，支持 17 种语言；内置 WAF 和主动防御；多进程下精确的安全限制；导入 lighttpd 的 mod_magnet 脚本；多实例管理。
- **它没有的**：HTTP/2 和 HTTP/3、实时压缩、Docker/Kubernetes 服务发现、内置 ACME 客户端（它使用 Certbot）、模块生态。

---

## 2. 如何阅读本对比

有几个概念贯穿全文。

- **每秒请求数（req/s）**：服务器每秒发送的文件数。越高越好。
- **与 nginx 的差距**：绝对值很大程度上取决于机器。在我们的三台机器上，nginx 的结果从 22,000 到 440,000 req/s 不等。保持稳定的是**服务器之间的比值**。因此表格在每个值旁边给出它与同一轮测量中 nginx 的比值：**1.00 = 与 nginx 一样快**，0.50 = 慢一半，1.50 = 快 1.5 倍。
- **p99 延迟**：99% 的请求不超过的响应时间。它揭示平均值所掩盖的“糟糕时刻”。
- **PSS（*Proportional Set Size*）**：服务器所有进程实际占用的内存。多个进程共享的页面只计算一次。
- **进程与核心**：服务器可以使用多个处理器核心，各有各的方式。nginx、lighttpd、Apache 以及 Python 模式下的 omega-serv 启动多个进程。用 Go 编写的 Caddy 将工作分配到各个核心上。omega-serv 的原生引擎为每个可用核心启动一个线程。为了公平比较，我们给每个服务器**相同的核心**。
- **WAF（*Web Application Firewall*）**：检查每个请求以拦截攻击（注入、扫描器……）的过滤器。omega-serv 内置了它。其他服务器可以通过模块获得（ModSecurity、Coraza），但**它们是在未启用 WAF 的情况下测量的**，使用基础配置。

**正确的做法**：比较比值而不是绝对值，并始终确认 WAF 是否启用。

---

## 3. 测量方法

### 三台机器

| | 机器 A | 机器 B | 机器 C |
|---|---|---|---|
| 处理器 | Intel Core i5 M480，2.67 GHz（2010） | Intel Celeron J3455，1.5 GHz（2016） | AMD Ryzen AI 9 365（2024） |
| 核心 | 2 个物理核心，4 个线程 | 4 个核心，无超线程 | 10 个核心（4 个 Zen 5 + 6 个 Zen 5c），20 个线程 |
| 内存 | 8 GB | 8 GB | 32 GB |
| 系统 | Mabox Linux（基于 Manjaro），内核 6.18 | EndeavourOS，内核 7.2 | Arch Linux，内核 7.2（CachyOS） |
| 服务器核心 | 1 个物理核心（线程 0 和 2） | 2 个核心（0 和 1） | 4 个 Zen 5 核心，每个一个线程（0–3） |
| 客户端核心 | 1 个物理核心（线程 1 和 3） | 2 个核心（2 和 3） | 6 个 Zen 5c 核心（4–9） |

机器 A 是一台旧笔记本，机器 B 是一台低功耗迷你 PC，机器 C 是一台新笔记本，接通电源，使用“平衡”电源配置。它们覆盖了从小型家用服务器到现代机器的范围。

### 软件

| 软件 | 版本 |
|---|---|
| nginx | 1.30.4（A），1.30.5（B、C） |
| lighttpd | 1.4.85 |
| Apache HTTP Server | 2.4.69，MPM `event` |
| Caddy | 2.11.4（A、B），2.11.7（C） |
| omega-serv | 1.0.0 和 2.0.0（已发布的归档）以及 2.5，运行于 Python 3.14 |
| 负载客户端 | [oha](https://github.com/hatoo/oha) 1.16.0（用 Rust 编写） |

Traefik 未被测量：它不是文件服务器（见 §6）。它只出现在功能对比中。

### 流程

- **处理器隔离**：服务器和客户端绑定在不同的核心上（见上表）。客户端不会占用服务器的时间，所有服务器拥有完全相同的资源。
- **所有服务器使用相同的文件**：`small.html`（1 KB）、`medium.png`（100 KB）和 `large.bin`（5 MB），从同一个目录提供。
- **所有服务器都启用访问日志**，因为生产环境中的服务器会记录日志。
- **HTTP/1.1 不加密，持久连接（keep-alive）**。并发数为：1 KB 和 100 KB 文件 32 个连接，5 MB 文件 8 个连接。
- **时长**：每个文件、每种配置 10 秒。
- **重复**：3 轮完整的交替测量（第 1 轮测所有配置，再第 2 轮测所有配置，依此类推）。表格给出三轮的**中位数**。各轮之间的差异大多低于 5%。
- **内存**：服务器所有进程的 PSS，先在空闲时记录，再在负载后记录。
- **配置**：
  - nginx、lighttpd、Apache 和 Caddy 使用基础配置：静态文件和访问日志；
  - omega-serv 使用 `standard` 配置档，先关闭 WAF，再启用全部随附规则（不启用速率限制）。
- **进程数**：每个服务器先用 1 个进程测量，再用 2 个进程：nginx `worker_processes`、lighttpd `server.max-worker`、Apache `StartServers`/`ServerLimit`、Caddy `GOMAXPROCS`、omega-serv `server.workers`。对于 omega-serv 的原生引擎，`server.workers` 计的是 Python 安全进程；原生引擎本身总是使用分配给它的所有核心。
- **零错误**：所有测量的所有响应都是 200。

### 需要了解的局限

- **我们比较的是比值。** 在你的硬件或专用服务器上，绝对值会有所不同。
- **回环接口（127.0.0.1）**：测量不经过真实网络。在真实网络中，大文件的吞吐量几乎总是受链路而非服务器限制。机器 C 上几十 GB/s 的吞吐量只有在回环接口上才可能出现。
- 这些测量中**没有 TLS**。
- **机器 A**：该机器上的生产 omega-serv 服务在后台运行，但没有接收流量。
- **机器 C**：混合架构处理器（Zen 5 和 Zen 5c 核心）。服务器分配到 4 个快速核心，客户端分配到其余 6 个。
- **基础配置**：没有对任何服务器进行优化。有经验的管理员无疑能让每个服务器发挥更多性能，omega-serv 也不例外。
- **原始数据**：[`docs/benchmarks/`](../../benchmarks/)（每台机器一个文件）。

---

## 4. 性能：omega-serv 对比 nginx、lighttpd、Apache 和 Caddy

在所有表格中，参照值都是**2 个进程的 nginx**（= 1.00），在同一台机器的同一轮测量中得到。在机器 A 和 B 上，这是占用分配给服务器的所有核心的配置。

### 小文件（1 KB）：每秒请求数

| 服务器 | 机器 A | 机器 B | 机器 C |
|---|---:|---:|---:|
| lighttpd，2 个进程 | 33,138 (**1.52**) | 31,125 (**1.26**) | 378,590 (**1.53**) |
| nginx，2 个进程 | 21,801 (1.00) | 24,705 (1.00) | 248,184 (1.00) |
| **omega-serv，原生引擎** | **15,222 (0.70)** | **16,542 (0.67)** | **285,213 (1.15 \*)** |
| omega-serv，原生 + WAF † | 11,990 (0.56) | 12,998 (0.53) | 264,484 (1.07 \*) |
| omega-serv，原生 + WAF，2 个安全进程 † | 11,746 (0.55) | 12,718 (0.52) | 253,527 (1.02 \*) |
| Apache，2 个进程 | 9,192 (0.42) | 8,634 (0.35) | 188,335 (0.76) |
| Caddy，2 个进程 | 5,749 (0.26) | 4,116 (0.17) | 52,897 (0.21) |
| omega-serv，Python 引擎，2 个进程 | 2,354 (0.11) | 1,312 (0.05) | 19,911 (0.08) |
| omega-serv，Python + WAF，2 个进程 | 1,901 (0.09) | 1,104 (0.04) | 15,783 (0.06) |
| omega-serv，Python 引擎 | 1,507 (0.07) | 663 (0.03) | 10,553 (0.04) |
| omega-serv，Python + WAF | 1,561 (0.07) | 564 (0.02) | 8,365 (0.03) |

\* 在机器 C 上，原生引擎使用它的 4 个核心，而 2 个进程的 nginx 只使用 2 个。相同核心数下的对比见下文：比值又回到 **0.67–0.71**，与其他机器一致。

† 11 月 4 日在 WAF 优化之后测量，属于同一流程下的单独一轮。比值相对于这一轮的 nginx（2 个进程）计算：小文件为 21,439、24,424 和 248,127 req/s，100 KB 文件为 11,545、11,004 和 157,491。在此优化之前，启用 WAF 的原生引擎为 3,495、2,622 和 39,000 req/s（nginx 的 0.11–0.16），因为每个请求都要经过 Python。原始数据：`*-waf-natif-brut.txt` 文件。

使用 1 个进程时，nginx 为 0.52–0.73，lighttpd 为 0.81–1.43，Apache 为 0.33–0.74，Caddy 为 0.09–0.17（原始数据）。

### 小文件的 p99 延迟

| 服务器 | 机器 A | 机器 B | 机器 C |
|---|---:|---:|---:|
| lighttpd，2 个进程 | 4.4 ms | 4.1 ms | 0.2 ms |
| nginx，2 个进程 | 4.9 ms | 5.2 ms | 0.2 ms |
| **omega-serv，原生引擎** | **6.1 ms** | **6.2 ms** | **0.3 ms** |
| omega-serv，原生 + WAF † | 7.2 ms | 6.7 ms | 0.3 ms |
| Apache，2 个进程 | 18.8 ms | 20.6 ms | 0.8 ms |
| Caddy，2 个进程 | 24.1 ms | 30.5 ms | 2.8 ms |
| omega-serv，Python 引擎，2 个进程 | 22.6 ms | 28.1 ms | 3.3 ms |
| omega-serv，Python 引擎 | 32.0 ms | 51.6 ms | 4.4 ms |

### 中等文件（100 KB）：每秒请求数

| 服务器 | 机器 A | 机器 B | 机器 C |
|---|---:|---:|---:|
| lighttpd，2 个进程 | 13,561 (**1.08**) | 12,126 (**1.07**) | 197,905 (**1.26**) |
| nginx，2 个进程 | 12,513 (1.00) | 11,303 (1.00) | 157,224 (1.00) |
| Apache，2 个进程 | 6,939 (0.55) | 7,035 (0.62) | 153,265 (0.97) |
| Caddy，2 个进程 | 5,059 (0.40) | 3,744 (0.33) | 22,094 (0.14) |
| **omega-serv，原生引擎** | **4,738 (0.38)** | **3,115 (0.28)** | **96,277 (0.61)** |
| omega-serv，原生 + WAF † | 4,229 (0.37) | 2,926 (0.27) | 98,185 (0.62) |
| omega-serv，Python 引擎，2 个进程 | 1,741 (0.14) | 1,154 (0.10) | 18,806 (0.12) |
| omega-serv，Python 引擎 | 1,329 (0.11) | 611 (0.05) | 9,805 (0.06) |

### 大文件（5 MB）：吞吐量

| 服务器 | 机器 A | 机器 B | 机器 C |
|---|---:|---:|---:|
| lighttpd，2 个进程 | 2,440 MB/s (1.05) | 2,110 MB/s (0.99) | 28,011 MB/s (0.81) |
| nginx，2 个进程 | 2,322 MB/s (1.00) | 2,124 MB/s (1.00) | 34,651 MB/s (1.00) |
| Apache，2 个进程 | 2,355 MB/s (1.01) | 2,134 MB/s (1.00) | 41,153 MB/s (**1.19**) |
| **omega-serv，原生引擎** | **2,294 MB/s (0.99)** | **1,936 MB/s (0.91)** | **37,918 MB/s (1.09)** |
| Caddy，2 个进程 | 2,205 MB/s (0.95) | 1,996 MB/s (0.94) | 3,811 MB/s (0.11) |
| omega-serv，Python 引擎，2 个进程 | 2,145 MB/s (0.92) | 1,931 MB/s (0.91) | 25,829 MB/s (0.75) |
| omega-serv，Python 引擎 | 1,686 MB/s (0.73) | 1,472 MB/s (0.69) | 14,227 MB/s (0.41) |

### 内存（PSS，服务器所有进程）：空闲 → 负载后

| 服务器 | 机器 A | 机器 B | 机器 C |
|---|---:|---:|---:|
| lighttpd | 1 → 1 MB | 1 → 1 MB | 1 → 1 MB |
| nginx | 4 → 5 MB | 5 → 5 MB | 4 → 4 MB |
| Apache | 4 → 7 MB | 4 → 7 MB | 4 → 7 MB |
| omega-serv，Python 引擎 | 28 → 32 MB | 29 → 33 MB | 30 → 34 MB |
| **omega-serv，原生引擎** | **33 → 34 MB** | **34 → 35 MB** | **35 → 39 MB** |
| omega-serv，原生 + WAF † | 45 → 47 MB | 43 → 44 MB | 44 → 48 MB |
| omega-serv，Python 引擎，2 个进程 | 40 → 50 MB | 43 → 51 MB | 42 → 51 MB |
| omega-serv，原生 + WAF，2 个安全进程 † | 45 → 47 MB | 43 → 44 MB | 55 → 57 MB |
| Caddy，2 个进程 | 50 → 57 MB | 46 → 54 MB | 48 → 62 MB |

### 相同核心数：机器 C，4 个进程

11 月 3 日的单独一轮，相同流程，在机器 C 上：每个服务器获得 4 个进程（Caddy 和原生引擎为 4 个核心）。参照：4 个进程的 nginx。这里不再列出启用 WAF 的原生引擎：它是在 WAF 优化之前测量的，尚未用 4 个进程重新测量。

| 服务器 | 1 KB | 100 KB | 5 MB | 内存 |
|---|---:|---:|---:|---:|
| lighttpd，4 个进程 | 638,907 (**1.46**) | 312,402 (**1.21**) | 41,982 MB/s (0.93) | 1 → 2 MB |
| nginx，4 个进程 | 438,496 (1.00) | 258,242 (1.00) | 45,162 MB/s (1.00) | 5 → 5 MB |
| **omega-serv，原生引擎** | **294,083–310,972 (0.67–0.71)** | **108,991–109,955 (0.42)** | **40,137–40,463 MB/s (0.89–0.90)** | **35 → 38 MB** |
| Apache，4 个进程 | 200,592 (0.46) | 162,607 (0.63) | 39,664 MB/s (0.88) | 6 → 9 MB |
| Caddy，4 个核心 | 97,085 (0.22) | 35,900 (0.14) | 5,998 MB/s (0.13) | 52 → 67 MB |
| omega-serv，Python 引擎，4 个进程 | 37,697 (0.09) | 35,064 (0.14) | 37,123 MB/s (0.82) | 48 → 66 MB |

### 结论

- **原生引擎改变了 omega-serv 的位置。**
  - 在小文件上，它从 nginx 的 0.03–0.11（Python 引擎）提升到约 **nginx 的 0.7**，在任何机器上都是如此。
  - 它领先于 Apache 和 Caddy，落后于仍然最快的 nginx 和 lighttpd。
  - 它的 p99 延迟接近 nginx。
- **lighttpd 在小文件和中等文件上最快**，三台机器上都是如此，而且内存最省。但它的文档不推荐 `server.max-worker`（多进程），而我们为了在相同进程数下比较使用了它。
- **中等文件是原生引擎目前的弱点**：nginx 的 0.28–0.61，落后于 Apache，而且增加核心也没有改善。这是一个已确定的改进方向。
- **在大文件上**，各服务器趋于接近，因为数据由操作系统内核复制（`sendfile`）。例外是机器 C 上的 Caddy：我们没有尝试优化它的基础配置。
- **WAF 对原生引擎的开销很小，但需要如实解读。**
  - 原生引擎自行检查 WAF 规则：不匹配任何规则的请求不经 Python 即被响应。只要有一点疑问（匹配、非 ASCII 文本、处于 Active Defense 监视下的来源、认证区域……），就由 Python 决定。因此启用 WAF 后，原生引擎在小文件上保持 78–95% 的吞吐量，在 100 KB 文件上保持 93–99%。在此优化之前，它的吞吐量会降为原来的 1/4 到 1/7。
  - 速率限制由原生引擎计数：启用它不会改变这些数字（机器 A：启用为 11,391 req/s，不启用为 11,330）。如果启用了 magnet，所有请求仍然经过 Python，开销回到以前的水平。
  - 启用 WAF 的 omega-serv 仍领先于**未启用** WAF 的 Apache 和 Caddy。
  - nginx、lighttpd、Apache 和 Caddy 是在**未启用** WAF 的情况下测量的。给这些服务器加上 WAF（ModSecurity、Coraza）也有开销，我们没有测量。因此“启用 WAF”的对比并不对等，我们也不声称 omega-serv 会比启用 WAF 的其他服务器更快。
- **多个安全进程对正常流量不再有帮助**：正常流量不再经过它们，2 个进程时吞吐量保持不变（−2% 到 −4%，在测量噪声之内）。只有当大量请求经过 Python 时（启用 magnet、遭受攻击）它们才有用：根据优化前所有请求都经过它们时的测量，2 个安全进程在 4 个核心上使启用 WAF 的吞吐量提高 1.5–1.7 倍，但在 2 个核心上只提高 5–12%。
- **Python 引擎随进程数扩展**（2 个进程 ×1.6–×2，4 个进程约 ×3.5），但仍为 nginx 的 5–11%。
- **内存**：omega-serv 比 nginx、lighttpd 或 Apache 多占几十 MB，主要因为 Python，与 Caddy 相当。使用原生引擎、不启用 WAF 时，负载期间内存几乎不变。
- **衡量这些数字**：即使最慢的情况——机器 B 上启用 WAF 的 Python 引擎（564 req/s）——也接近每天 5000 万个请求。这远超个人网站、内部服务或实验室的需求。只有大流量网站才真正需要考虑速度。

---

## 5. omega-serv 各版本：1.0 → 2.0 → 2.5

三个版本与 §4 在同一轮中测量，三台机器，相同流程。括号中为与同一轮 nginx（2 个进程）的比值。†：11 月 4 日 WAF 优化后的一轮（见 §4）。

### 小文件（1 KB）：每秒请求数

| 版本和模式 | 机器 A | 机器 B | 机器 C |
|---|---:|---:|---:|
| 1.0.0 | 1,547 (0.07) | 645 (0.03) | 8,870 (0.04) |
| 1.0.0 + WAF | 1,453 (0.07) | 561 (0.02) | 7,687 (0.03) |
| 2.0.0 | 1,740 (0.08) | 650 (0.03) | 10,245 (0.04) |
| 2.0.0 + WAF | 1,456 (0.07) | 565 (0.02) | 8,371 (0.03) |
| 2.0.0，2 个进程 | 2,153 (0.10) | 1,277 (0.05) | 19,192 (0.08) |
| 2.0.0 + WAF，2 个进程 | 1,775 (0.08) | 1,113 (0.05) | 15,351 (0.06) |
| 2.5，Python 引擎 | 1,507 (0.07) | 663 (0.03) | 10,553 (0.04) |
| 2.5，Python 引擎 + WAF | 1,561 (0.07) | 564 (0.02) | 8,365 (0.03) |
| 2.5，Python 引擎，2 个进程 | 2,354 (0.11) | 1,312 (0.05) | 19,911 (0.08) |
| 2.5，Python 引擎 + WAF，2 个进程 | 1,901 (0.09) | 1,104 (0.04) | 15,783 (0.06) |
| **2.5，原生引擎** | **15,222 (0.70)** | **16,542 (0.67)** | **285,213 (1.15)** |
| **2.5，原生引擎 + WAF †** | **11,990 (0.56)** | **12,998 (0.53)** | **264,484 (1.07)** |
| **2.5，原生引擎 + WAF，2 个安全进程 †** | **11,746 (0.55)** | **12,718 (0.52)** | **253,527 (1.02)** |

### 中等文件、大文件和内存（1 个进程，无 WAF）

| 版本 | 100 KB，req/s（A / B / C） | 5 MB，MB/s（A / B / C） | 空闲内存 → 负载后（A / B / C） |
|---|---|---|---|
| 1.0.0 | 1,071 / 563 / 7,625 | 578 / 549 / 3,640 | 21 → **98** / 22 → **98** / 23 → **73** MB |
| 2.0.0 | 1,570 / 603 / 9,469 | 1,665 / 1,470 / 14,058 | 26 → 30 / 27 → 31 / 28 → 32 MB |
| 2.5，Python 引擎 | 1,329 / 611 / 9,805 | 1,686 / 1,472 / 14,227 | 28 → 32 / 29 → 33 / 30 → 34 MB |
| **2.5，原生引擎** | **4,738 / 3,115 / 96,277** | **2,294 / 1,936 / 37,918** | **33 → 34 / 34 → 35 / 35 → 39 MB** |

### 大文件并发下载

测试：3 个 300 MB 文件同时下载，同时持续请求一个小页面。每个版本每台机器测两轮，结果几乎相同。这里的内存是服务器所有进程的 **RSS**，与原始测试一致：它会多次计算共享内存，因此数值高于其他表格中的 PSS。

| 版本 | 峰值内存 | 小页面，最差情况：A / B / C |
|---|---:|---|
| 1.0.0 | **1,833–1,836 MB** | **1.4–1.9 s** / **1.4–1.7 s** / 0.16 s |
| 2.0.0 | 39–42 MB | 3 ms / 4–6 ms / 1 ms |
| 2.5，Python 引擎 | 41–44 MB | 2 ms / 4 ms / 1 ms |
| 2.5，原生引擎 | 49–55 MB | 1–2 ms / 2–4 ms / 少于 1 ms |

### 主动防御的开销（1.0 → 2.0）

2026 年 10 月 26 日在机器 A 上的测量，此后未重测：对每个可疑请求，Active Defense 记录一次威胁观察的开销，在磁盘（ext4）上用 2,000 次观察测得。

| 测量 | 1.0.0 | 2.0.0 |
|---|---:|---:|
| 中位数 | 2.84 ms | 0.23 ms |
| p99 | 11.6 ms | 2.3 ms |
| 最大值 | 18–20 ms | 37–46 ms |

中位数缩小为原来的 1/12。相反，2.0 的最大值更高：少数孤立的峰值，与 SQLite 日志定期写入磁盘有关。

### 结论

- **从 1.0 到 2.0**，进步体现在内存和大文件上，而不是小页面的速度：
  - 负载后内存从 73–98 MB 降到 30–32 MB；
  - 大文件下载期间，内存从超过 1.8 GB 降到约 40 MB，服务器仍保持响应（几毫秒，而不是近 2 秒）；
  - 大文件吞吐量提高 2.7–3.9 倍；
  - 2.0 增加了多进程，视机器不同使小页面吞吐量提高 25% 到接近 100%。
  1.0 在发送前将每个文件完整载入内存。2.0 分块发送，或交给操作系统内核处理。
- **从 2.0 到 2.5，Python 引擎速度没有变化**：在机器 B 和 C 上差异低于 4%，在对后台负载最敏感的机器 A 上处于测量噪声之内（−13% 到 +9%）。2.5 的全部收益来自**原生引擎**：小文件上比 Python 引擎快约 ×10–×27，延迟降为原来的 1/5 到 1/15。
- **原生引擎空闲时比 Python 引擎多占约 5 MB**（PSS）：这是第二个程序的代价。启用 WAF 时还要再多约 8 MB：这是加载到原生引擎中的规则。

### 关于原生引擎需要了解的

- 它是**可选的**：Python 引擎仍是默认引擎和后备引擎。
- 它自行提供静态内容、重定向、重写、别名、缓存、错误页面、安全标头和 TLS。
- 它自行检查 WAF 规则，并自行响应不匹配任何规则的请求。其他所有请求（WAF 匹配或存疑、Active Defense、认证）都由 Python 决定，检查和日志完全相同。一个可配置的检查仍会每 N 个干净请求中交给 Python 一个，以核实两者给出相同的判定。
- 目录列表和内部页面向 Python 请求；反向代理、FastCGI、文件上传和 WebSocket 在整个连接期间交给 Python。因此这些功能保持 Python 引擎的速度。
- 在直接 TLS 下，原生引擎不支持反向代理、FastCGI 和文件上传：此时由 Python 引擎提供服务，界面会显示这一点。
- 它需要 glibc 2.38 或更新版本以及 OpenSSL 3。如果无法启动，安装程序会就地重新编译；如果仍不可能，omega-serv 继续使用 Python 引擎。

---

## 6. 功能对比

图例：
- ✅ 内置；
- 🧩 项目官方模块，需要启用或安装；
- 🔌 第三方模块或插件；
- ⚙️ 通过外部工具；
- ❌ 不具备。

“Commercial”表示仅在付费版本中提供的功能。

### HTTP 服务

| 功能 | nginx | lighttpd | Caddy | Apache | Traefik | omega-serv 2.5 |
|---|---|---|---|---|---|---|
| 服务器语言 | C | C | Go | C | Go | Python，可选 C++ 原生引擎 |
| 提供静态文件 | ✅ | ✅ | ✅ | ✅ | ❌（仅代理） | ✅ |
| ETag / 304 / Range | ✅ | ✅ | ✅ | ✅ | — | ✅ |
| 预压缩文件 `.gz` / `.br` | ✅ `gzip_static`（`.br`：🔌） | 🔌 Lua 脚本（mod_magnet） | ✅ `precompressed` | 🧩 mod_rewrite 配方 | — | ✅ |
| 实时压缩 | ✅ | ✅ mod_deflate | ✅ | 🧩 mod_deflate | ✅ middleware | ❌ |
| HTTP/2 | ✅ | ✅ | ✅ | 🧩 mod_http2 | ✅ | ❌ |
| HTTP/3（QUIC） | ✅ | ❌ | ✅ | ❌ | ✅ | ❌ |
| 通过 FastCGI 运行 PHP | ✅ | ✅ | ✅ | ✅ | ❌ | ✅ |
| 多进程或多核 | ✅ workers | ⚠️ `max-worker`，文档不推荐 | ✅（Go，所有核心） | ✅ MPM | ✅（Go） | ✅ `server.workers`；原生引擎：所有核心 |

### 反向代理

| 功能 | nginx | lighttpd | Caddy | Apache | Traefik | omega-serv 2.5 |
|---|---|---|---|---|---|---|
| 负载均衡 | ✅ 轮询、最少连接、哈希 | ✅ fair、round-robin、hash、sticky | ✅ 约十几种策略 | 🧩 mod_proxy_balancer | ✅ wrr、p2c、hrw、least-time | ✅ 7 种策略，包括真实负载 |
| 被动检查（剔除故障服务器） | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| 主动检查（定期探测） | Commercial（NGINX Plus） | ❌ | ✅ | 🧩 mod_proxy_hcheck | ✅ | ✅ |
| 响应缓存 | ✅ `proxy_cache` | ❌ | 🔌 | 🧩 mod_cache | Commercial | ✅ |
| WebSocket | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| 服务发现（Docker、Kubernetes） | 🔌 | ❌ | 🔌 | ❌ | ✅（项目核心） | ❌ |

### TLS

| 功能 | nginx | lighttpd | Caddy | Apache | Traefik | omega-serv 2.5 |
|---|---|---|---|---|---|---|
| 自动证书（ACME、Let's Encrypt） | 🧩 `ngx_http_acme_module` | ⚙️ Certbot | ✅ 默认 | 🧩 mod_md | ✅ | ⚙️ Certbot，带内置向导和定期续期 |
| 本地 CA | ❌ | ❌ | ✅ 内部 CA（自动签发） | ❌ | ❌ | ✅ 创建、签署 CSR、吊销 |

### 安全

| 功能 | nginx | lighttpd | Caddy | Apache | Traefik | omega-serv 2.5 |
|---|---|---|---|---|---|---|
| 按客户端限速 | ✅ `limit_req` | ⚠️ mod_evasive（仅并发连接） | 🔌 caddy-ratelimit | 🔌 mod_evasive、mod_qos | ✅ middleware | ✅ |
| 进程间共享的限制 | ✅ 共享内存区 | ❌ 按进程计数 | —（单进程） | 取决于模块 | 1 个实例；多个需 Redis | ✅ 共享内存 |
| WAF（SQLi/XSS 特征、扫描器……） | 🔌 ModSecurity、Commercial（App Protect） | ❌（需自写 Lua 脚本） | 🔌 Coraza | 🔌 ModSecurity | 🔌 插件 | ✅ 内置 |
| 带有效期的封锁列表、重复计数 | ⚙️ fail2ban | ⚙️ fail2ban | ⚙️ fail2ban | ⚙️ fail2ban | ⚙️ | ✅ 内置 |
| 诱饵、战时模式、事件、IoC 导出 | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ Active Defense |
| 随时间分级的封禁 | ⚙️ fail2ban | ⚙️ fail2ban | ⚙️ fail2ban | ⚙️ fail2ban | ⚙️ | ✅ RIPOSTE |
| 配置安全审计 | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ `audit security` |
| 观察模式（记录而不拦截） | 取决于模块 | — | 取决于插件 | ✅ ModSecurity `DetectionOnly` | 取决于插件 | ✅ |

分级封禁：对反复回来的地址施加越来越长的封禁，持续数周，可在本地或网络层面执行。fail2ban 通过其 `bantime.increment` 选项实现；RIPOSTE 还增加了可基于日志测量、启用前可模拟的策略，以及撤销操作和紧急停止。

### 可扩展性

| 功能 | nginx | lighttpd | Caddy | Apache | Traefik | omega-serv 2.5 |
|---|---|---|---|---|---|---|
| 脚本语言 | 🧩 njs（JavaScript）；🔌 Lua（OpenResty） | ✅ Lua（mod_magnet） | Go 模块（需重新编译） | 🧩 mod_lua | Go 或 WebAssembly 插件 | 🔌 导入 mod_magnet 脚本（`magnet` 选项） |
| 模块生态 | 非常庞大 | 针对性强 | 庞大 | 非常庞大 | 庞大 | 无：一切内置 |

---

## 7. 管理与易用性

| 服务器 | 主要管理方式 | 界面 | 不中断重载 |
|---|---|---|---|
| nginx | 配置文件 | 无（仪表板：NGINX Plus，商业版） | ✅ `nginx -s reload` |
| lighttpd | 配置文件 | 无（mod_status 只读） | ✅ 平滑重启 |
| Caddy | Caddyfile 或 JSON | REST 管理 API | ✅ 通过 API |
| Apache | 配置文件和 `.htaccess` | 无（mod_status 只读） | ✅ `graceful` |
| Traefik | 容器标签、文件或 Kubernetes | Web 仪表板（只读） | ✅ 动态配置 |
| omega-serv | 终端界面（TUI）和命令行（CLI）；无需编辑 JSON 文件 | **键盘和鼠标操作的完整 TUI，17 种语言，内置帮助** | ✅ 大多数设置；端口、TLS、引擎和进程数会提示需要重启 |

实际使用中，omega-serv 在同一个界面中管理配置、安全、日志、系统服务、备份和实例。每项设置都有说明，并在写入前进行校验。其他服务器则需要编辑文本文件，再借助各自独立的工具（Certbot、fail2ban、logrotate、ModSecurity、监控工具……）。

另一方面，nginx、Apache 和 Caddy 的“配置文件”方式非常便于自动化（Ansible、容器、版本控制）。omega-serv 有可用于脚本的 CLI，但其自动化生态目前仍然有限。

---

## 8. omega-serv 额外提供的

本节只列出被比较的服务器中没有一个能以这种形式、不借助第三方模块或外部工具提供的内容。

1. **在终端界面中完成全部管理。**
   - 界面覆盖整个服务器：网站、安全、日志、服务、备份和实例。
   - 可以用键盘和鼠标操作，适用于没有图形环境的服务器，甚至通过 SSH。
   - 它支持 17 种语言，并解释每一项设置。
   - 其他服务器要么没有管理界面（nginx、lighttpd、Apache），要么只有 API（Caddy）或只读仪表板（Traefik）。
2. **内置的主动安全，无需组装模块。**
   - WAF 包括特征、可编辑的路径列表、重复计数、带有效期的封锁列表、信誉和观察模式。
   - Active Defense 增加了诱饵、战时模式、事件跟踪、入侵指标导出和空跑模拟。
   - RIPOSTE 随时间作出反应：它记住反复回来的地址，并对它们施加分级响应，越来越长的封禁（默认 1 小时、6 小时、24 小时、7 天），可以是封锁列表中的本地封禁，也可以是通过 fail2ban（omega-jail）的网络封禁，或者延长的诱饵。每条策略都可以基于真实日志测量并在启用前模拟；每个操作都保持可见、可撤销，并有紧急停止。
   - 在其他服务器中，这些功能需要组合 ModSecurity 或 Coraza、规则集和 fail2ban。
3. **多进程下精确的安全限制。**
   - 在多进程下，速率限制和 WAF 重复计数在内存中由各进程共享。因此攻击者无法用进程数来倍增自己的限额。
   - lighttpd 记录了相反的情况：使用 `server.max-worker` 时，`mod_evasive` 和 `mod_status` 在每个进程中分别计数。
   - nginx 也共享其计数器（`limit_req` 区），但没有内置 WAF。
4. **两个引擎，同一种行为。** 原生引擎和 Python 引擎产生相同的响应和相同的日志，这由对比测试台自动核验。读取日志的工具（例如 fail2ban）看不出任何差别。
5. **导入 lighttpd 的 mod_magnet 脚本。**
   - 已为 lighttpd 编写的 Lua 防护脚本无需重写即可导入。
   - 它补充内置防护，但永远无法削弱它，并且在启用前会检查其兼容性。
6. **多实例管理。**
   - 注册表记录所有实例，界面可以在它们之间切换。
   - 它也能完整卸载一个实例。
7. **配置安全审计**：`audit security` 命令仅提供信息，从不阻断，并返回可用于脚本的退出码。
8. **远程日志源。**
   - 界面按需通过 SSH 获取另一台服务器的日志，不保存密码。
   - 它可以在 lnav 中查看这些日志，并与本地日志合并。
9. **无法关闭的 HTTP 加固**，从安装起即生效，适用于任何配置档和引擎：
   - 严格校验 Host 标头；
   - 拒绝 Content-Length / Transfer-Encoding 歧义；
   - 网站响应中的安全标头和 CSP，包括其错误页面；
   - 安全读取 X-Forwarded-For；
   - 拒绝以 root 身份启动。

---

## 9. 其他服务器做得更好的地方

- **吞吐量**：lighttpd 和 nginx 在小文件和中等文件上仍然最快，三台机器上都是如此。即使使用原生引擎，omega-serv 在小文件上约为 nginx 的 0.7、lighttpd 的 0.5，在 100 KB 文件上为 nginx 的 0.3–0.6。对于大流量网站、公共 API 或 CDN，应该选择它们。
- **中等文件**：在三台机器上，Apache 提供 100 KB 文件都比 omega-serv 原生引擎快。
- **内存**：lighttpd（1 MB）、nginx（4–5 MB）和 Apache（4–9 MB）适合资源非常有限的机器（嵌入式系统、小型容器）。omega-serv 需要 30–65。
- **安全的代价**：WAF 仍有代价。使用原生引擎时，它在小文件上使吞吐量损失 5–22%，包括速率限制：启用 WAF 的 omega-serv 在机器 A 和 B 上为无 WAF nginx 的 0.53–0.56。可疑或存疑的请求（规则匹配、非 ASCII 文本、处于 Active Defense 监视下的来源）总是经过 Python，以 Python 引擎的速度提供服务。启用 magnet 时，所有请求都经过 Python，WAF 会像优化前一样使原生引擎的吞吐量降为原来的 1/4 到 1/7。
- **协议**：其他所有服务器都支持 HTTP/2，nginx、Caddy 和 Traefik 支持 HTTP/3。omega-serv 只支持 HTTP/1.1。
- **自动 HTTPS**：Caddy 和 Traefik 默认启用，nginx（`ngx_http_acme_module`）和 Apache（`mod_md`）通过官方模块提供。omega-serv 交给 Certbot，并提供向导和定期续期。
- **容器环境**：Traefik 的自动服务发现（Docker、Kubernetes）在 omega-serv 中没有对应功能。
- **生态与成熟度**：nginx 和 Apache 提供成千上万的模块、指南和集成，以及数十年的生产经验。Caddy 提供 Go 模块系统。omega-serv 是一个由一个人维护的年轻项目，它的原生引擎刚刚问世。
- **实时压缩**：omega-serv 只提供已经压缩好的文件。

---

## 10. 什么场景用哪个服务器

| 场景 | 推荐选择 |
|---|---|
| 大流量网站、公共 API、CDN、最大吞吐量 | **nginx** 或 **lighttpd** |
| 资源非常有限的机器、嵌入式系统、静态文件 | **lighttpd** |
| 快速上手、自动 HTTPS、简短配置 | **Caddy** |
| 老旧 PHP 应用、`.htaccess`、共享主机 | **Apache** |
| Docker、Kubernetes、微服务 | **Traefik** |
| 中小型网站、内部服务、实验室、VPN、无需编辑文件的管理 | **omega-serv**（尽可能使用原生引擎） |
| 面向互联网的服务器，希望在一个界面中查看和控制其安全（WAF、分级封禁、诱饵） | **omega-serv** |
| 带负载均衡、检查和缓存的内部反向代理，通过界面管理 | **omega-serv** |
| 学习 HTTP 加固和主动防御 | **omega-serv** |

这些工具也可以组合使用。例如：
- 由 nginx 或 Traefik 面向互联网，后面由 omega-serv 负责内部服务及其安全和管理；
- 由 omega-serv 作为多台应用服务器前面的内部反向代理。

---

## 11. 复现测量

工具随代码仓库提供，位于 `tools/bench/`。需要安装 nginx、lighttpd、Apache、Caddy 和 oha，omega-serv 的开发环境（`.venv`），以及（对于原生引擎）在 `native/omega-http-core/build-release` 中编译好的二进制文件。

```sh
# 1. 准备测量目录（测试文件、配置、omega-serv 1.0、2.0 和当前版本）
tools/bench/compare/setup.sh /路径/测量 omega-serv-1.0.0.tar.gz omega-serv-2.0.0.tar.gz

# 2. 21 种配置，3 轮交替重复（40–60 分钟）
#    SRV_CPUS / CLI_CPUS：服务器和客户端的核心（lscpu -e 显示拓扑）
SRV_CPUS=0,1 CLI_CPUS=2,3 tools/bench/compare/campaign.sh /路径/测量 > 结果.txt

# 3. 中位数
python3 tools/bench/compare/summarize.py 结果.txt

# 其他配置列表，例如 4 个进程
CONFIGS="nginx-4 lighttpd-4 caddy-4 apache-4 omega-v2-1-0-native omega-v2-4-1-native" \
  tools/bench/compare/campaign.sh /路径/测量 > 结果-4.txt

# 大文件下载（内存和响应性）：当前版本，Python 引擎，再原生引擎，再 1.0
.venv/bin/python tools/bench/bigfile.py
BENCH_ENGINE=native .venv/bin/python tools/bench/bigfile.py
BENCH_SRC=/路径/测量/v1-archive/omega-serv/src \
BENCH_EXTRA_PATH=/路径/测量/v1-archive/omega-serv/vendor/omega-lib/src \
  .venv/bin/python tools/bench/bigfile.py

# 测量任何其他已在运行的服务器，无需 oha
python3 tools/bench/bench_any.py --make-files /srv/测试-webroot
python3 tools/bench/bench_any.py --port 8080
```

配置名称：`nginx-N`、`lighttpd-N`、`apache-N`、`caddy-N`（N 个进程，Caddy 为 N 个核心）；omega-serv 为 `omega-vX-N-W`（版本 `v1`、`v20`，或 `v2` 表示当前版本，N 个进程，W = 0 表示无 WAF，1 表示启用），原生引擎加后缀 `-native`。

如需发布你自己的结果，请注明机器、版本、核心分配和三轮重复。

---

## 12. 来源

其他服务器的功能依据其官方文档（于 2026 年 10 月 26 日查阅）。

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
- [mod_proxy（负载均衡、被动检查、WebSocket）](https://redmine.lighttpd.net/projects/lighttpd/wiki/Docs_ModProxy)
- [mod_evasive（单个地址的并发连接）](https://redmine.lighttpd.net/projects/lighttpd/wiki/Docs_ModEvasive)

**Caddy**
- [自动 HTTPS](https://caddyserver.com/docs/automatic-https)
- [`file_server` 和 `precompressed`](https://caddyserver.com/docs/caddyfile/directives/file_server)
- [`reverse_proxy`（策略、主动和被动检查）](https://caddyserver.com/docs/caddyfile/directives/reverse_proxy)
- [管理 API](https://caddyserver.com/docs/api)
- [限速插件 caddy-ratelimit](https://github.com/mholt/caddy-ratelimit)
- [Caddy 的 Coraza WAF](https://github.com/corazawaf/coraza-caddy)
- [caddy-docker-proxy](https://github.com/lucaslorentz/caddy-docker-proxy)

**Apache HTTP Server**
- [MPM event](https://httpd.apache.org/docs/2.4/mod/event.html)
- [mod_md（ACME）](https://httpd.apache.org/docs/2.4/mod/mod_md.html)
- [mod_proxy_balancer](https://httpd.apache.org/docs/2.4/mod/mod_proxy_balancer.html)
- [mod_proxy_hcheck](https://httpd.apache.org/docs/2.4/mod/mod_proxy_hcheck.html)
- [mod_http2](https://httpd.apache.org/docs/2.4/mod/mod_http2.html)
- [mod_deflate，预压缩内容](https://httpd.apache.org/docs/2.4/mod/mod_deflate.html)
- [ModSecurity](https://github.com/owasp-modsecurity/ModSecurity)

**Traefik**
- [`ratelimit` middleware（每个实例在内存中，可选 Redis）](https://doc.traefik.io/traefik/reference/routing-configuration/http/middlewares/ratelimit/)
- [ACME](https://doc.traefik.io/traefik/https/acme/)
- [Providers（Docker、Kubernetes……）](https://doc.traefik.io/traefik/providers/overview/)

**fail2ban**
- [`jail.conf`：`bantime.increment`、`bantime.factor`、`bantime.multipliers`、`bantime.maxtime`（对惯犯更长的封禁）](https://github.com/fail2ban/fail2ban/blob/master/config/jail.conf)（于 2026 年 11 月 4 日查阅）

**测量工具**
- [oha](https://github.com/hatoo/oha)

---

*本对比由 kraynux 为 omega-serv 2.5 编写：测量于 2026 年 11 月 3 日和 4 日在三台机器上完成（主动防御：2026 年 10 月 26 日）。任何容量决策，请使用随附工具在你自己的硬件上测量。*
