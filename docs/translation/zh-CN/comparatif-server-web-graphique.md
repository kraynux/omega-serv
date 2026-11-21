# omega-serv 与市面上的 Web 服务器 — 图表版

**omega-serv 与 nginx · lighttpd · Apache · Caddy · Traefik 对比 — 三台机器实测（2026 年11月）。**

🌐 [Français](../../comparatif-server-web-graphique.md) · [English](../en/comparatif-server-web-graphique.md) · [Español](../es/comparatif-server-web-graphique.md) · [Português (Brasil)](../pt-BR/comparatif-server-web-graphique.md) · [Italiano](../it/comparatif-server-web-graphique.md) · [Deutsch](../de/comparatif-server-web-graphique.md) · [Nederlands](../nl/comparatif-server-web-graphique.md) · [Polski](../pl/comparatif-server-web-graphique.md) · [Русский](../ru/comparatif-server-web-graphique.md) · **中文** · [Tiếng Việt](../vi/comparatif-server-web-graphique.md) · [ไทย](../th/comparatif-server-web-graphique.md) · [Bahasa Indonesia](../id/comparatif-server-web-graphique.md) · [日本語](../ja/comparatif-server-web-graphique.md) · [한국어](../ko/comparatif-server-web-graphique.md) · [हिन्दी](../hi/comparatif-server-web-graphique.md) · [العربية](../ar/comparatif-server-web-graphique.md)

> **阅读说明：** 条越长，服务器越快。基准为 **nginx = 1.00**。

## 颜色图例

<!-- 🖼️ IMAGE : legende-couleurs -->
<div align="center">
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/translation/zh-CN/omega-serv/stats-1.png" alt="颜色图例" width="1024">
</div>

---

## 📊 1 KB 文件 — 吞吐量（请求/秒）

机器 A（i5 2010）、B（Celeron 2016）和 C（Ryzen 2024）。条形按同一台机器上的 nginx（1.00）归一化。

<!-- 🖼️ IMAGE : 1ko-banner — 3 colonnes côte à côte (Machine A · 2 cœurs | Machine B · 4 cœurs | Machine C · 10 cœurs), largeur totale -->
<div align="center">
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/translation/zh-CN/omega-serv/stats-2.png" alt="1 Ko 文件 — 机器 A、B 和 C" width="1024">
</div>

> \* 机器 C：原生引擎使用 4 个核心，nginx 为 2 个进程（2 个核心）。核心数相同时，比值回落至约 0.70。
---

## 📦 中等文件（100 KB）— 普通 Web 模式

这里 Apache 令人意外：它经常超过 omega-serv 的原生引擎。lighttpd 仍然最快。基准：nginx = 1.00。

<!-- 🖼️ IMAGE : 100ko-banner.png — 3 colonnes côte à côte (A | B | C), largeur totale -->
<div align="center">
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/translation/zh-CN/omega-serv/stats-3.png" alt="100 Ko 文件 — 机器 A、B 和 C" width="1024">
</div>

---

## 💿 大文件（5 MB）— 普通 Web 模式

在大文件上，各服务器趋于一致：复制数据的是内核（sendfile）。Caddy 在机器 C 上是例外。吞吐量单位为 MB/s。

<!-- 🖼️ IMAGE : 5mo-banner.png — 3 colonnes côte à côte (A | B | C), largeur totale -->
<div align="center">
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/translation/zh-CN/omega-serv/stats-4.png" alt="5 Mo 文件 — 机器 A、B 和 C" width="1024">
</div>

---

## 🔄 反向代理 — 小响应（1 KB）

每个代理都转发到一个 nginx 后端。基准：nginx = 1.00。机器 C：4 个进程。

<!-- 🖼️ IMAGE : proxy-1ko-banner.png — 3 colonnes côte à côte (A | B | C), largeur totale -->
<div align="center">
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/translation/zh-CN/omega-serv/stats-5.png" alt="代理 1 Ko — 机器 A、B 和 C" width="1024">
</div>

---

## 🔄 反向代理 — 100 KB 响应

在中等响应上，omega-serv 原生与 nginx 持平或更快。

<!-- 🖼️ IMAGE : proxy-100ko-banner.png — 3 colonnes côte à côte (A | B | C), largeur totale -->
<div align="center">
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/translation/zh-CN/omega-serv/stats-6.png" alt="代理 100 Ko — 机器 A、B 和 C" width="1024">
</div>

---

## 💾 内存（PSS）— 空闲 → 负载后

条越短，服务器越节省内存。lighttpd、nginx 和 Apache 最为节省；其次是 omega-serv 3.0.0（11 月 19 日重新测量），原生引擎占用 10 到 16 MB。

<!-- 🖼️ IMAGE : memoire-banner.png — 3 colonnes côte à côte de jauges (A | B | C), largeur totale -->
<div align="center">
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/translation/zh-CN/omega-serv/stats-7.png" alt="内存 — 机器 A、B 和 C" width="1024">
</div>

---

## 🏆 普通 Web 排名 — 谁最快？

三台机器在静态文件服务上的综合结果。

<!-- 🖼️ IMAGE : classement-web.png -->
<!-- Contenu : 1. 🥇 lighttpd — meilleur en petits & moyens fichiers · 2. 🥈 nginx — référence, excellent partout · 3. 🥉 Apache — bon, robuste, écosystème · 4. omega-serv natif — très bon, 2ᵉ en reverse proxy · 5. Caddy — simple, HTTPS auto · 6. omega-serv Python — moteur de repli -->
<div align="center">
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/translation/zh-CN/omega-serv/stats-8.png" alt="普通 Web 排名" width="1024">
</div>

---

## 🔄 反向代理排名 — 谁最好？

nginx 仍是基准；omega-serv 原生是它最接近的亚军，远远领先其他服务器。

<!-- 🖼️ IMAGE : classement-proxy.png -->
<!-- Contenu : 1. 🥇 nginx · 2. 🥈 omega-serv natif — 0,82 à 0,91× nginx en 1 Ko · 3. 🥉 omega-serv + WAF — toujours devant lighttpd/Apache · 4. lighttpd — 0,53 à 0,61× · 5. Apache — 0,50 à 0,59× · 6. Traefik — 0,29 à 0,35× · 7. Caddy — 0,23 à 0,32× · 8. omega-serv Python — moteur de repli -->
<div align="center">
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/translation/zh-CN/omega-serv/stats-9.png" alt="反向代理排名" width="1024">
</div>

---

## 🆚 对比 — Web 与反向代理排名并列

两种用途，两个排名。一个服务器可能在其中一个表现出色，在另一个令人失望：Apache 在转发上令人意外，Caddy 除了简单之外处处令人失望。

<!-- 🖼️ IMAGE : face-a-face.png — 2 colonnes côte à côte (web | proxy), largeur totale -->
<div align="center">
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/translation/zh-CN/omega-serv/stats-10.png" alt="Web 与反向代理对比" width="1024">
</div>

### 交叉综合

| 服务器 | 定位 |
|---|---|
| 🟢 **omega-serv 原生** | 最全能：Web 第4，**反向代理第2**。唯一内置 WAF 且在转发上仍领先于 lighttpd 和 Apache 的服务器。用一个工具覆盖两种用途并额外获得安全性，这是最佳折中。 |
| 🔵 **nginx** | 最稳定：Web 第2，**反向代理第1**。始终处于排名上游，没有明显短板。没有特殊要求时的默认选择。 |
| 🟢 **lighttpd** | 静态文件的短跑选手：**Web 第1**，但转发第4。纯静态场景的最佳选择，一旦加入反向代理，就应让位于 omega-serv 或 nginx。 |
| 🔴 **Apache** | 反例：Web 第3，转发第5。在大文件上，它甚至让 nginx 感到意外（机器 C）。既不是最快的也不是最轻的：其优势仍是 PHP 生态。 |
| 🟠 **Caddy** | 简单优先于速度：Web 第5，**转发第7**。不是为吞吐量而生：自动 HTTPS 和简短的配置。适合留给小项目。 |
| 🟣 **Traefik** | 不属于 Web 类别：不是文件服务器，转发第6。它的主场仍是 Docker 和 Kubernetes，而不是原始性能。 |

---

## 📋 完整汇总表 — 相对 nginx 的比值（1.00）

涵盖**所有**指标的总览：普通 Web 模式（1 KB、100 KB、5 MB）和反向代理（1 KB、100 KB），以及内存。数值越接近或高于 1.00，越好。

| 服务器 | Web 1 KB (A/B/C) | Web 100 KB (A/B/C) | Web 5 MB (A/B/C) | 代理 1 KB (A/B/C) | 代理 100 KB (A/B/C) | 内存 (A/B/C) |
|---|---|---|---|---|---|---|
| **lighttpd** | 1.52 / 1.26 / 1.53 | 1.08 / 1.07 / 1.26 | 1.05 / 0.99 / 0.81 | 0.61 / 0.56 / 0.53 | 0.74 / 0.62 / 0.96 | 1 MB |
| **nginx** | 1.00 / 1.00 / 1.00 | 1.00 / 1.00 / 1.00 | 1.00 / 1.00 / 1.00 | 1.00 / 1.00 / 1.00 | 1.00 / 1.00 / 1.00 | 4–5 MB |
| **omega-serv (natif)** | **0.70 / 0.67 / 1.15\*** | **0.38 / 0.28 / 0.61** | **0.99 / 0.91 / 1.09** | **0.85 / 0.91 / 0.82** | **1.11 / 0.97 / 1.43** | 10–16 MB |
| **omega-serv + WAF** | 0.56 / 0.53 / 1.07\* | 0.37 / 0.27 / 0.62 | — | 0.81 / 0.89 / 0.77 | 1.10 / 0.93 / 1.30 | 28–33 MB |
| **Apache** | 0.42 / 0.35 / 0.76 | 0.55 / 0.62 / 0.97 | 1.01 / 1.00 / 1.19 | 0.59 / 0.53 / 0.50 | 0.62 / 0.65 / 0.71 | 4–9 MB |
| **Caddy** | 0.26 / 0.17 / 0.21 | 0.40 / 0.33 / 0.14 | 0.95 / 0.94 / 0.11 | 0.32 / 0.28 / 0.23 | 0.60 / 0.54 / 0.59 | 46–67 MB |
| **Traefik** | — | — | — | 0.35 / 0.35 / 0.29 | 0.64 / 0.60 / 0.70 | 93–131 MB |
| **omega-serv (Python)** | 0.11 / 0.05 / 0.08 | 0.14 / 0.10 / 0.12 | 0.92 / 0.91 / 0.75 | 0.09 / 0.08 / 0.07 | 0.21 / 0.19 / — | 20–48 MB |

> \* 机器 C：原生为 4 个核心，nginx 为 2 个；核心数相同时，比值约 0.67–0.71。
> 每个单元格中的三个值分别对应机器 **A / B / C**。“—”：未测量或不适用。

---

## ⚖️ 优势与劣势 — 所有服务器

每个服务器都有各自的长处和局限。以下是不偏不倚的完整视图。

### 🟢 omega-serv（原生）

**优势**
- ✅ 终端中的完整管理（TUI，17 种语言）
- ✅ 内置 WAF + Active Defense + RIPOSTE
- ✅ C++ 原生引擎：静态文件约为 nginx 的 0.7×
- ✅ 反向代理第2，仅次于 nginx
- ✅ 进程间共享限制（精确的安全性）
- ✅ 导入 lighttpd mod_magnet 脚本
- ✅ 多实例管理
- ✅ Web 管理


**劣势**
- ❌ 不支持 HTTP/2 和 HTTP/3
- ❌ 不支持实时压缩
- ❌ 不支持 Docker/Kubernetes 发现
- ❌ ACME 通过 Certbot（非原生集成）
- ❌ 100 KB 文件：nginx 的 0.3–0.6×
- ❌ 内存 10–55 MB，视模式而定（nginx/lighttpd 为 1–5 MB）
- ❌ 生态较新，由一人维护

---

### 🔵 nginx

**优势**
- ✅ 性能与稳定性的基准
- ✅ HTTP/2、HTTP/3、压缩
- ✅ 庞大的生态（模块、文档、社区）
- ✅ 非常节省内存（4–5 MB）
- ✅ 出色的反向代理
- ✅ 官方 ACME 模块
- ✅ 成熟且久经考验的配置

**劣势**
- ❌ 配置冗长，需要学习其专有语法
- ❌ 无内置 WAF（需要 ModSecurity 或同类产品）
- ❌ 无原生管理界面
- ❌ 生产环境中重新加载配置有时较棘手
- ❌ 开源版本受限（部分功能属于付费的 Nginx Plus）
- ❌ 无原生 Docker/Kubernetes 发现（通过模板）

---

### 🟢 lighttpd

**优势**
- ✅ 小/中等文件最快
- ✅ 内存最节省（1 MB）
- ✅ 轻量，适合受限系统
- ✅ 良好的反向代理
- ✅ 配置简单易读

**劣势**
- ❌ 不支持 HTTP/3（HTTP/2 视构建而定，部分支持）
- ❌ 反向代理仅第4（nginx 的 0.53–0.61×）
- ❌ 生态比 nginx/Apache 更小
- ❌ 无内置 WAF
- ❌ 不支持 Docker/Kubernetes 发现
- ❌ 开发不如过去活跃
- ❌ 大文件较弱（机器 C 上为 nginx 的 0.81×）

---

### 🔴 Apache

**优势**
- ✅ 庞大的历史生态（模块、`.htaccess`、PHP）
- ✅ 数十年来稳健且久经考验
- ✅ 大文件表现出色（在机器 C 上超过 nginx）
- ✅ 支持 `.htaccess`，无需重启
- ✅ 提供压缩、HTTP/2、ACME
- ✅ 文档丰富

**劣势**
- ❌ 小文件较慢（nginx 的 0.35–0.42×）
- ❌ prefork 模式下内存占用大（4–9 MB，负载上升时增长很快）
- ❌ 进程模型不如事件驱动高效
- ❌ 配置冗长
- ❌ 反向代理第5（nginx 的 0.50–0.59×）
- ❌ 无内置 WAF（ModSecurity 为独立模块）
- ❌ 攻击面历来较大

---

### 🟠 Caddy

**优势**
- ✅ 自动 HTTPS（内置 ACME，零配置）
- ✅ 配置非常简短易读（Caddyfile）
- ✅ 原生 HTTP/2 和 HTTP/3
- ✅ 单一二进制文件，部署简单
- ✅ 中等响应上的反向代理表现尚可

**劣势**
- ❌ 原始吞吐量较慢（Web 第5，转发第7）
- ❌ 内存占用高（46–67 MB）
- ❌ 机器 C 上的大文件非常弱（nginx 的 0.11×）
- ❌ 无内置 WAF
- ❌ 生态比 nginx/Apache 更新
- ❌ 不适合极高吞吐量

---

### 🟣 Traefik

**优势**
- ✅ 自动 Docker/Kubernetes 发现
- ✅ 容器化环境的理想选择
- ✅ 自动 HTTPS（内置 ACME）
- ✅ 动态配置，无需重启
- ✅ 中等响应上的反向代理表现良好（nginx 的 0.60–0.70×）

**劣势**
- ❌ 不是文件服务器（不在 Web 排名中）
- ❌ 反向代理第6（1 KB 时为 nginx 的 0.29–0.35×）
- ❌ 内存占用非常高（93–131 MB）
- ❌ 脱离容器环境后配置复杂
- ❌ 无内置 WAF
- ❌ 对于简单的静态站点而言过于庞大

---

## 🎯 什么用途选哪个服务器？

| 用途 | 推荐服务器 | 原因 |
|---|---|---|
| 高流量站点 | **nginx** 或 **lighttpd** | 最大吞吐量，HTTP/2-3 |
| 受限机器 / 嵌入式 | **lighttpd** | 1 MB 内存，最快且最省资源 |
| 简单的自动 HTTPS | **Caddy** | 自动证书，配置简短 |
| Docker / Kubernetes | **Traefik** | 服务发现 |
| PHP 应用 / .htaccess | **Apache** | 历史生态 |
| 反向代理 | **nginx** 或 **omega-serv（原生）** | 最佳性能 |
| Web 站点 + 安全 + 界面 | **omega-serv（原生）** | 完整基础设施：WAF、Web 管理、多实例、反向代理、日志管理器、备份…… |

---

数据来自 omega-serv 对比（2026 年11月）— kraynux。MIT 许可证。
[oha](https://github.com/hatoo/oha) pour la mesure · graphiques HTML/CSS autonomes.

> *omega-serv 实测对比的图表版（数字与详细对比相同：2026 年11月 3 日和 4 日在三台机器上的测量；反向代理：2026 年11月 14 日；omega-serv 3.0.0 内存：2026 年11月 19 日）。任何容量决策，请在您自己的硬件上测量。*
>
> Copyright © 2026 kraynux — kraynux@proton.me — MIT 许可证（见 LICENSE 文件）。
