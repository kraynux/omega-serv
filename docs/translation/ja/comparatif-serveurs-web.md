<!-- Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE) -->

# omega-serv と主要な Web サーバーの比較

**測定にもとづく比較：nginx · lighttpd · Apache · Caddy · Traefik · omega-serv 2.5**

🌐 [Français](../../comparatif-serveurs-web.md) · [English](../en/comparatif-serveurs-web.md) · [Español](../es/comparatif-serveurs-web.md) · [Português (Brasil)](../pt-BR/comparatif-serveurs-web.md) · [Italiano](../it/comparatif-serveurs-web.md) · [Deutsch](../de/comparatif-serveurs-web.md) · [Nederlands](../nl/comparatif-serveurs-web.md) · [Polski](../pl/comparatif-serveurs-web.md) · [Русский](../ru/comparatif-serveurs-web.md) · [中文](../zh-CN/comparatif-serveurs-web.md) · [Tiếng Việt](../vi/comparatif-serveurs-web.md) · [ไทย](../th/comparatif-serveurs-web.md) · [Bahasa Indonesia](../id/comparatif-serveurs-web.md) · **日本語** · [한국어](../ko/comparatif-serveurs-web.md) · [हिन्दी](../hi/comparatif-serveurs-web.md) · [العربية](../ar/comparatif-serveurs-web.md)

この文書は、広く使われている Web サーバーの中で omega-serv がどこに位置するかを示します。「最良のサーバー」を決めることが目的ではありません。それぞれのツールは異なる用途に応えるもので、どれにも長所があります。この文書が提供するのは次の 3 点です。

1. **実測値**：性格の大きく異なる **3 台のマシン**で、同じクライアント、同じファイル、同じ手順を用いて測定し、再現可能です。
2. **機能比較**：各項目を各サーバーの公式ドキュメントで確認し（リンクは文書末尾）、組み込み機能とモジュールやプラグインが必要な機能を区別しています。
3. omega-serv が**実際に上乗せしているもの**と、他のサーバーが**omega-serv より優れている点**。

性能測定はすべて 2026 年 11 月 3 日と 4 日に行いました。他のサイトから取った数値や推定値は一つもありません。生データはこの文書とともに公開しています。

---

## 目次

1. [要約](#1-要約)
2. [この比較の読み方](#2-この比較の読み方)
3. [測定方法](#3-測定方法)
4. [性能：omega-serv と nginx、lighttpd、Apache、Caddy の比較](#4-性能omega-serv-と-nginxlighttpdapachecaddy-の比較)
5. [omega-serv のバージョン：1.0 → 2.0 → 2.5](#5-omega-serv-のバージョン10--20--25)
6. [機能比較](#6-機能比較)
7. [管理と使いやすさ](#7-管理と使いやすさ)
8. [omega-serv が上乗せしているもの](#8-omega-serv-が上乗せしているもの)
9. [他のサーバーのほうが優れている点](#9-他のサーバーのほうが優れている点)
10. [用途別のサーバー選び](#10-用途別のサーバー選び)
11. [測定の再現](#11-測定の再現)
12. [出典](#12-出典)

---

## 1. 要約

- **omega-serv には 2 つのエンジンがあります。** **Python エンジン**はすべてを処理します。**ネイティブエンジン**は C++ で書かれ、2.5 で導入されたもので、自らリクエストに応答します。設定とセキュリティ上の判断は Python が引き続き受け持ち、どの WAF ルールにも一致しないリクエストはネイティブエンジンが自ら見分けます。
- **ネイティブエンジンで WAF なしの場合**、omega-serv は小さなファイルを **nginx の約 0.7** の速度で配信します。3 台のマシンすべてで同じです。つまり **Apache と Caddy より速く、nginx と lighttpd より遅い**位置です。
- **Python エンジンでは**、omega-serv は他のすべてのサーバーに大きく後れを取ります：**nginx の速度の 3–11 %**。
- **WAF を有効にすると**、omega-serv はすべてのリクエストを検査します。測定した他のサーバーはこれを行っていません。ネイティブエンジンでは、マシン A と B で nginx（WAF なし）の **0.53–0.56**、マシン C で 1.07（4 コア対 2 コア）になります。WAF によるスループットの低下は 5–22 % にとどまります。WAF なしで測定した Apache と Caddy よりも依然として速い結果です。
- **中サイズのファイル（100 KB）**：ネイティブエンジンの現時点での弱点で、nginx の **0.3–0.6**、Apache より遅い結果です。
- **大きなファイル（5 MB）**：nginx、lighttpd、Apache、ネイティブの omega-serv は同程度のスループットに達します。最も速いマシンでは Caddy が明らかに遅くなります。
- **メモリ**：lighttpd（1 MB）、nginx（4–5 MB）、Apache（4–9 MB）は非常に省メモリです。omega-serv はモードにより **30–65 MB**、Caddy は **50–67 MB** を使います。
- **omega-serv が上乗せしているもの**：17 言語に対応したターミナルインターフェースでの完全な管理、組み込みの WAF とアクティブ防御、複数プロセスでも正確なセキュリティ制限、lighttpd の mod_magnet スクリプトの取り込み、複数インスタンスの管理。
- **持っていないもの**：HTTP/2 と HTTP/3、オンザフライ圧縮、Docker/Kubernetes のサービス検出、組み込みの ACME クライアント（Certbot を使用）、モジュールのエコシステム。

---

## 2. この比較の読み方

文書全体を通して、いくつかの概念が繰り返し登場します。

- **毎秒リクエスト数（req/s）**：サーバーが 1 秒間に送るファイルの数。多いほど良い値です。
- **nginx との差**：絶対値はマシンに大きく左右されます。3 台のマシンで、nginx は 22 000 から 440 000 req/s までの幅があります。安定しているのは**サーバー間の比率**です。そのため表では各値の横に、同じセッションで測定した nginx との比率を示しています：**1.00 = nginx と同じ速さ**、0.50 = 半分の速さ、1.50 = 1.5 倍の速さ。
- **p99 レイテンシ**：リクエストの 99 % が超えない応答時間。平均値では隠れてしまう「悪い瞬間」がわかります。
- **PSS（*Proportional Set Size*）**：サーバーの全プロセスが実際に使っているメモリ。複数のプロセスが共有するページは 1 回だけ数えます。
- **プロセスとコア**：サーバーは複数のプロセッサコアを使えます。その方法はサーバーごとに異なります。nginx、lighttpd、Apache、Python モードの omega-serv は複数のプロセスを起動します。Go で書かれた Caddy は作業をコアに分散します。omega-serv のネイティブエンジンは利用可能なコアごとに 1 つのスレッドを起動します。公平に比較するため、各サーバーに**同じコア**を割り当てました。
- **WAF（*Web Application Firewall*）**：攻撃（インジェクション、スキャナーなど）を遮断するために各リクエストを検査するフィルター。omega-serv には組み込まれています。他のサーバーもモジュール（ModSecurity、Coraza）で導入できますが、**測定は WAF なし**の基本設定で行いました。

**正しい読み方**：絶対値ではなく比率を比べ、WAF が有効かどうかを必ず確認してください。

---

## 3. 測定方法

### 3 台のマシン

| | マシン A | マシン B | マシン C |
|---|---|---|---|
| プロセッサ | Intel Core i5 M480、2.67 GHz（2010） | Intel Celeron J3455、1.5 GHz（2016） | AMD Ryzen AI 9 365（2024） |
| コア | 物理 2 コア、4 スレッド | 4 コア、ハイパースレッディングなし | 10 コア（Zen 5 ×4 + Zen 5c ×6）、20 スレッド |
| メモリ | 8 GB | 8 GB | 32 GB |
| システム | Mabox Linux（Manjaro ベース）、カーネル 6.18 | EndeavourOS、カーネル 7.2 | Arch Linux、カーネル 7.2（CachyOS） |
| サーバーのコア | 物理 1 コア（スレッド 0 と 2） | 2 コア（0 と 1） | Zen 5 の 4 コア、各 1 スレッド（0–3） |
| クライアントのコア | 物理 1 コア（スレッド 1 と 3） | 2 コア（2 と 3） | Zen 5c の 6 コア（4–9） |

マシン A は古いノート PC、マシン B は省電力のミニ PC、マシン C は新しいノート PC で、電源に接続し、電源プロファイルは「バランス」です。小さな家庭用サーバーから最新のマシンまでを網羅しています。

### ソフトウェア

| ソフトウェア | バージョン |
|---|---|
| nginx | 1.30.4（A）、1.30.5（B、C） |
| lighttpd | 1.4.85 |
| Apache HTTP Server | 2.4.69、MPM `event` |
| Caddy | 2.11.4（A、B）、2.11.7（C） |
| omega-serv | 1.0.0 と 2.0.0（公開アーカイブ）および 2.5、Python 3.14 上 |
| 負荷クライアント | [oha](https://github.com/hatoo/oha) 1.16.0（Rust 製） |

Traefik はファイルサーバーではないため測定していません（§6 を参照）。機能比較にのみ登場します。

### 手順

- **プロセッサの分離**：サーバーとクライアントは別々のコアに固定しています（上の表）。クライアントがサーバーの時間を奪うことはなく、すべてのサーバーがまったく同じリソースを持ちます。
- **全サーバーで同じファイル**：`small.html`（1 KB）、`medium.png`（100 KB）、`large.bin`（5 MB）を同じフォルダーから配信します。
- **アクセスログはすべてで有効**：本番運用のサーバーはログを取るためです。
- **暗号化なしの HTTP/1.1、持続的接続（keep-alive）**。同時接続数は 1 KB と 100 KB のファイルで 32、5 MB のファイルで 8 です。
- **時間**：ファイルごと、設定ごとに 10 秒。
- **繰り返し**：交互に行う完全な 3 回の測定（1 回目ですべての設定、続いて 2 回目ですべての設定、以下同様）。表には 3 回の**中央値**を示します。回ごとの差はほとんどの場合 5 % 未満です。
- **メモリ**：サーバーの全プロセスの PSS を、アイドル時と負荷後に記録します。
- **設定**：
  - nginx、lighttpd、Apache、Caddy は基本設定：静的ファイルとアクセスログ。
  - omega-serv は `standard` プロファイルで、WAF を無効にした状態と、付属のすべてのルールで有効にした状態（レート制限なし）。
- **プロセス数**：各サーバーを 1 プロセス、次に 2 プロセスで測定します：nginx `worker_processes`、lighttpd `server.max-worker`、Apache `StartServers`/`ServerLimit`、Caddy `GOMAXPROCS`、omega-serv `server.workers`。omega-serv のネイティブエンジンでは、`server.workers` は Python のセキュリティプロセスの数を表します。ネイティブエンジン自体は、割り当てられたすべてのコアを常に使います。
- **エラーはゼロ**：すべての測定のすべての応答が 200 でした。

### 知っておくべき制約

- **比較しているのは比率です。** お使いのハードウェアや専用サーバーでは絶対値が異なります。
- **ループバックインターフェース（127.0.0.1）**：測定は実際のネットワークを通りません。実際のネットワークでは、大きなファイルのスループットはほぼ常にサーバーではなく回線で制限されます。マシン C での数十 GB/s というスループットはループバックでのみ可能です。
- これらの測定では **TLS を使っていません**。
- **マシン A**：このマシンの本番用 omega-serv サービスがバックグラウンドで動いていましたが、トラフィックは受けていません。
- **マシン C**：ハイブリッドプロセッサ（Zen 5 と Zen 5c のコア）。サーバーには高速な 4 コア、クライアントには残りの 6 コアを割り当てました。
- **基本設定**：どのサーバーも最適化していません。経験豊富な管理者なら、omega-serv を含め、どのサーバーからもさらに性能を引き出せるはずです。
- **生データ**：[`docs/benchmarks/`](../../benchmarks/)（マシンごとに 1 ファイル）。

---

## 4. 性能：omega-serv と nginx、lighttpd、Apache、Caddy の比較

すべての表で、基準は**2 プロセスの nginx**（= 1.00）で、同じマシンの同じセッションで測定したものです。マシン A と B では、これがサーバーに割り当てたすべてのコアを使う設定です。

### 小さなファイル（1 KB）：毎秒リクエスト数

| サーバー | マシン A | マシン B | マシン C |
|---|---:|---:|---:|
| lighttpd、2 プロセス | 33 138 (**1.52**) | 31 125 (**1.26**) | 378 590 (**1.53**) |
| nginx、2 プロセス | 21 801 (1.00) | 24 705 (1.00) | 248 184 (1.00) |
| **omega-serv、ネイティブエンジン** | **15 222 (0.70)** | **16 542 (0.67)** | **285 213 (1.15 \*)** |
| omega-serv、ネイティブ + WAF † | 11 990 (0.56) | 12 998 (0.53) | 264 484 (1.07 \*) |
| omega-serv、ネイティブ + WAF、セキュリティプロセス 2 † | 11 746 (0.55) | 12 718 (0.52) | 253 527 (1.02 \*) |
| Apache、2 プロセス | 9 192 (0.42) | 8 634 (0.35) | 188 335 (0.76) |
| Caddy、2 プロセス | 5 749 (0.26) | 4 116 (0.17) | 52 897 (0.21) |
| omega-serv、Python エンジン、2 プロセス | 2 354 (0.11) | 1 312 (0.05) | 19 911 (0.08) |
| omega-serv、Python + WAF、2 プロセス | 1 901 (0.09) | 1 104 (0.04) | 15 783 (0.06) |
| omega-serv、Python エンジン | 1 507 (0.07) | 663 (0.03) | 10 553 (0.04) |
| omega-serv、Python + WAF | 1 561 (0.07) | 564 (0.02) | 8 365 (0.03) |

\* マシン C では、ネイティブエンジンは 4 コアを使い、2 プロセスの nginx は 2 コアしか使いません。同じコア数での比較は下にあります。そこでは比率が再び **0.67–0.71** となり、他のマシンと同じです。

† 11 月 4 日、WAF の最適化後に、同じ手順の別セッションで測定。比率はこのセッションの nginx（2 プロセス）に対して計算しています：小さなファイルで 21 439、24 424、248 127 req/s、100 KB のファイルで 11 545、11 004、157 491。この最適化の前は、WAF ありのネイティブエンジンは 3 495、2 622、39 000 req/s（nginx の 0.11–0.16）でした。すべてのリクエストが Python を経由していたためです。生データ：`*-waf-natif-brut.txt` ファイル。

1 プロセスでは、nginx は 0.52–0.73、lighttpd は 0.81–1.43、Apache は 0.33–0.74、Caddy は 0.09–0.17 です（生データ）。

### 小さなファイルでの p99 レイテンシ

| サーバー | マシン A | マシン B | マシン C |
|---|---:|---:|---:|
| lighttpd、2 プロセス | 4.4 ms | 4.1 ms | 0.2 ms |
| nginx、2 プロセス | 4.9 ms | 5.2 ms | 0.2 ms |
| **omega-serv、ネイティブエンジン** | **6.1 ms** | **6.2 ms** | **0.3 ms** |
| omega-serv、ネイティブ + WAF † | 7.2 ms | 6.7 ms | 0.3 ms |
| Apache、2 プロセス | 18.8 ms | 20.6 ms | 0.8 ms |
| Caddy、2 プロセス | 24.1 ms | 30.5 ms | 2.8 ms |
| omega-serv、Python エンジン、2 プロセス | 22.6 ms | 28.1 ms | 3.3 ms |
| omega-serv、Python エンジン | 32.0 ms | 51.6 ms | 4.4 ms |

### 中サイズのファイル（100 KB）：毎秒リクエスト数

| サーバー | マシン A | マシン B | マシン C |
|---|---:|---:|---:|
| lighttpd、2 プロセス | 13 561 (**1.08**) | 12 126 (**1.07**) | 197 905 (**1.26**) |
| nginx、2 プロセス | 12 513 (1.00) | 11 303 (1.00) | 157 224 (1.00) |
| Apache、2 プロセス | 6 939 (0.55) | 7 035 (0.62) | 153 265 (0.97) |
| Caddy、2 プロセス | 5 059 (0.40) | 3 744 (0.33) | 22 094 (0.14) |
| **omega-serv、ネイティブエンジン** | **4 738 (0.38)** | **3 115 (0.28)** | **96 277 (0.61)** |
| omega-serv、ネイティブ + WAF † | 4 229 (0.37) | 2 926 (0.27) | 98 185 (0.62) |
| omega-serv、Python エンジン、2 プロセス | 1 741 (0.14) | 1 154 (0.10) | 18 806 (0.12) |
| omega-serv、Python エンジン | 1 329 (0.11) | 611 (0.05) | 9 805 (0.06) |

### 大きなファイル（5 MB）：スループット

| サーバー | マシン A | マシン B | マシン C |
|---|---:|---:|---:|
| lighttpd、2 プロセス | 2 440 MB/s (1.05) | 2 110 MB/s (0.99) | 28 011 MB/s (0.81) |
| nginx、2 プロセス | 2 322 MB/s (1.00) | 2 124 MB/s (1.00) | 34 651 MB/s (1.00) |
| Apache、2 プロセス | 2 355 MB/s (1.01) | 2 134 MB/s (1.00) | 41 153 MB/s (**1.19**) |
| **omega-serv、ネイティブエンジン** | **2 294 MB/s (0.99)** | **1 936 MB/s (0.91)** | **37 918 MB/s (1.09)** |
| Caddy、2 プロセス | 2 205 MB/s (0.95) | 1 996 MB/s (0.94) | 3 811 MB/s (0.11) |
| omega-serv、Python エンジン、2 プロセス | 2 145 MB/s (0.92) | 1 931 MB/s (0.91) | 25 829 MB/s (0.75) |
| omega-serv、Python エンジン | 1 686 MB/s (0.73) | 1 472 MB/s (0.69) | 14 227 MB/s (0.41) |

### メモリ（PSS、サーバーの全プロセス）：アイドル時 → 負荷後

| サーバー | マシン A | マシン B | マシン C |
|---|---:|---:|---:|
| lighttpd | 1 → 1 MB | 1 → 1 MB | 1 → 1 MB |
| nginx | 4 → 5 MB | 5 → 5 MB | 4 → 4 MB |
| Apache | 4 → 7 MB | 4 → 7 MB | 4 → 7 MB |
| omega-serv、Python エンジン | 28 → 32 MB | 29 → 33 MB | 30 → 34 MB |
| **omega-serv、ネイティブエンジン** | **33 → 34 MB** | **34 → 35 MB** | **35 → 39 MB** |
| omega-serv、ネイティブ + WAF † | 45 → 47 MB | 43 → 44 MB | 44 → 48 MB |
| omega-serv、Python エンジン、2 プロセス | 40 → 50 MB | 43 → 51 MB | 42 → 51 MB |
| omega-serv、ネイティブ + WAF、セキュリティプロセス 2 † | 45 → 47 MB | 43 → 44 MB | 55 → 57 MB |
| Caddy、2 プロセス | 50 → 57 MB | 46 → 54 MB | 48 → 62 MB |

### 同じコア数：マシン C、4 プロセス

11 月 3 日の別セッション、同じ手順、マシン C：各サーバーに 4 プロセス（Caddy とネイティブエンジンは 4 コア）を割り当てました。基準：4 プロセスの nginx。WAF ありのネイティブエンジンはここには載せていません。WAF の最適化前に測定したもので、4 プロセスでの再測定はまだです。

| サーバー | 1 KB | 100 KB | 5 MB | メモリ |
|---|---:|---:|---:|---:|
| lighttpd、4 プロセス | 638 907 (**1.46**) | 312 402 (**1.21**) | 41 982 MB/s (0.93) | 1 → 2 MB |
| nginx、4 プロセス | 438 496 (1.00) | 258 242 (1.00) | 45 162 MB/s (1.00) | 5 → 5 MB |
| **omega-serv、ネイティブエンジン** | **294 083–310 972 (0.67–0.71)** | **108 991–109 955 (0.42)** | **40 137–40 463 MB/s (0.89–0.90)** | **35 → 38 MB** |
| Apache、4 プロセス | 200 592 (0.46) | 162 607 (0.63) | 39 664 MB/s (0.88) | 6 → 9 MB |
| Caddy、4 コア | 97 085 (0.22) | 35 900 (0.14) | 5 998 MB/s (0.13) | 52 → 67 MB |
| omega-serv、Python エンジン、4 プロセス | 37 697 (0.09) | 35 064 (0.14) | 37 123 MB/s (0.82) | 48 → 66 MB |

### 結論

- **ネイティブエンジンは omega-serv の位置づけを変えます。**
  - 小さなファイルでは、nginx の 0.03–0.11（Python エンジン）から約 **nginx の 0.7** に上がります。どのマシンでも同じです。
  - Apache と Caddy より速く、依然として最速の nginx と lighttpd より遅い位置です。
  - p99 レイテンシは nginx に近い値です。
- **lighttpd は小さなファイルと中サイズのファイルで最速**で、3 台すべてで同じ結果です。メモリも最も少なく済みます。ただし、同じプロセス数で比較するために使った `server.max-worker`（複数プロセス）は、そのドキュメントで推奨されていません。
- **中サイズのファイルはネイティブエンジンの現時点での弱点**です：nginx の 0.28–0.61 で Apache より遅く、コアを増やしても改善しません。これは特定済みの改善課題です。
- **大きなファイル**では、データをシステムのカーネルがコピーするため（`sendfile`）、サーバー間の差が縮まります。例外はマシン C の Caddy で、基本設定の最適化は試みていません。
- **WAF のネイティブエンジンへのコストは小さいものの、正直に読み解く必要があります。**
  - ネイティブエンジンは自ら WAF ルールを検査します。どのルールにも一致しないリクエストは Python を介さずに応答します。少しでも疑いがあれば（一致、ASCII 以外のテキスト、Active Defense が監視している送信元、認証ゾーンなど）、Python が判断します。その結果、WAF ありでもネイティブエンジンは小さなファイルでスループットの 78–95 %、100 KB のファイルで 93–99 % を維持します。この最適化の前は、スループットが 1/4 から 1/7 に落ちていました。
  - レート制限はネイティブエンジンがカウントします。有効にしてもこれらの数値は変わりません（マシン A：有効で 11 391 req/s、無効で 11 330）。magnet を有効にすると、すべてのリクエストが引き続き Python を経由し、コストは以前の水準に戻ります。
  - WAF ありの omega-serv は、WAF **なし**の Apache と Caddy よりも依然として速い結果です。
  - nginx、lighttpd、Apache、Caddy は WAF **なし**で測定しました。これらのサーバーに WAF（ModSecurity、Coraza）を加えれば、それにもコストがかかりますが、測定はしていません。したがって「WAF あり」の比較は対等ではなく、WAF を付けた他のサーバーより omega-serv が速いとは主張しません。
- **複数のセキュリティプロセスは、通常のトラフィックにはもう役立ちません**：通常のトラフィックはもうそこを通らず、2 プロセスでもスループットは変わりません（−2 から −4 %、測定誤差の範囲内）。役立つのは、多くのリクエストが Python を経由する場合（magnet 有効時、攻撃時）だけです。すべてのリクエストがそこを通っていた最適化前の測定では、2 つのセキュリティプロセスにより WAF ありのスループットが 4 コアで 1.5–1.7 倍になりましたが、2 コアでは 5–12 % の向上にとどまりました。
- **Python エンジンはプロセス数に応じてスケールします**（2 プロセスで ×1.6–×2、4 プロセスで約 ×3.5）が、nginx の 5–11 % にとどまります。
- **メモリ**：omega-serv は nginx、lighttpd、Apache より数十 MB 多く使います。主に Python によるもので、Caddy と同程度です。WAF なしのネイティブエンジンでは、負荷中もメモリはほとんど変わりません。
- **これらの数値の捉え方**：最も遅いケースであるマシン B での WAF ありの Python エンジン（564 req/s）でも、1 日あたり約 5000 万リクエストになります。個人サイト、社内サービス、検証環境の需要を大きく上回ります。速度が本当に決め手になるのは、トラフィックの多いサイトだけです。

---

## 5. omega-serv のバージョン：1.0 → 2.0 → 2.5

3 つのバージョンを §4 と同じセッションで、3 台のマシンすべてで、同じ手順により測定しました。括弧内は同じセッションの nginx（2 プロセス）との比率です。†：WAF 最適化後の 11 月 4 日のセッション（§4 を参照）。

### 小さなファイル（1 KB）：毎秒リクエスト数

| バージョンとモード | マシン A | マシン B | マシン C |
|---|---:|---:|---:|
| 1.0.0 | 1 547 (0.07) | 645 (0.03) | 8 870 (0.04) |
| 1.0.0 + WAF | 1 453 (0.07) | 561 (0.02) | 7 687 (0.03) |
| 2.0.0 | 1 740 (0.08) | 650 (0.03) | 10 245 (0.04) |
| 2.0.0 + WAF | 1 456 (0.07) | 565 (0.02) | 8 371 (0.03) |
| 2.0.0、2 プロセス | 2 153 (0.10) | 1 277 (0.05) | 19 192 (0.08) |
| 2.0.0 + WAF、2 プロセス | 1 775 (0.08) | 1 113 (0.05) | 15 351 (0.06) |
| 2.5、Python エンジン | 1 507 (0.07) | 663 (0.03) | 10 553 (0.04) |
| 2.5、Python エンジン + WAF | 1 561 (0.07) | 564 (0.02) | 8 365 (0.03) |
| 2.5、Python エンジン、2 プロセス | 2 354 (0.11) | 1 312 (0.05) | 19 911 (0.08) |
| 2.5、Python エンジン + WAF、2 プロセス | 1 901 (0.09) | 1 104 (0.04) | 15 783 (0.06) |
| **2.5、ネイティブエンジン** | **15 222 (0.70)** | **16 542 (0.67)** | **285 213 (1.15)** |
| **2.5、ネイティブエンジン + WAF †** | **11 990 (0.56)** | **12 998 (0.53)** | **264 484 (1.07)** |
| **2.5、ネイティブエンジン + WAF、セキュリティプロセス 2 †** | **11 746 (0.55)** | **12 718 (0.52)** | **253 527 (1.02)** |

### 中サイズのファイル、大きなファイル、メモリ（1 プロセス、WAF なし）

| バージョン | 100 KB、req/s（A / B / C） | 5 MB、MB/s（A / B / C） | アイドル時のメモリ → 負荷後（A / B / C） |
|---|---|---|---|
| 1.0.0 | 1 071 / 563 / 7 625 | 578 / 549 / 3 640 | 21 → **98** / 22 → **98** / 23 → **73** MB |
| 2.0.0 | 1 570 / 603 / 9 469 | 1 665 / 1 470 / 14 058 | 26 → 30 / 27 → 31 / 28 → 32 MB |
| 2.5、Python エンジン | 1 329 / 611 / 9 805 | 1 686 / 1 472 / 14 227 | 28 → 32 / 29 → 33 / 30 → 34 MB |
| **2.5、ネイティブエンジン** | **4 738 / 3 115 / 96 277** | **2 294 / 1 936 / 37 918** | **33 → 34 / 34 → 35 / 35 → 39 MB** |

### 大きなファイルの同時ダウンロード

テスト：300 MB のファイルを 3 本同時にダウンロードしながら、小さなページを絶えずリクエストします。バージョンごと、マシンごとに 2 回実施し、結果はほぼ同じでした。ここでのメモリは、元のテストと同じくサーバーの全プロセスの **RSS** です。共有メモリを複数回数えるため、他の表の PSS より大きな値になります。

| バージョン | 最大メモリ | 小さなページ、最悪値：A / B / C |
|---|---:|---|
| 1.0.0 | **1 833–1 836 MB** | **1.4–1.9 s** / **1.4–1.7 s** / 0.16 s |
| 2.0.0 | 39–42 MB | 3 ms / 4–6 ms / 1 ms |
| 2.5、Python エンジン | 41–44 MB | 2 ms / 4 ms / 1 ms |
| 2.5、ネイティブエンジン | 49–55 MB | 1–2 ms / 2–4 ms / 未満 1 ms |

### アクティブ防御のコスト（1.0 → 2.0）

2026 年 10 月 26 日にマシン A で測定し、その後は再測定していません：疑わしいリクエストごとに Active Defense が脅威を 1 件記録するコストを、ディスク（ext4）上で 2 000 件の記録により測定しました。

| 測定 | 1.0.0 | 2.0.0 |
|---|---:|---:|
| 中央値 | 2.84 ms | 0.23 ms |
| p99 | 11.6 ms | 2.3 ms |
| 最大値 | 18–20 ms | 37–46 ms |

中央値は 1/12 になります。一方、最大値は 2.0 のほうが高くなっています。SQLite のジャーナルを定期的にディスクへ書き込むことによる、いくつかの孤立したピークです。

### 結論

- **1.0 から 2.0 への進歩**は、小さなページの速度ではなく、メモリと大きなファイルにあります：
  - 負荷後のメモリは 73–98 MB から 30–32 MB に減少；
  - 大きなファイルのダウンロード中は、1.8 GB 超から約 40 MB に減り、サーバーは応答性を保ちます（約 2 秒ではなく数ミリ秒）；
  - 大きなファイルのスループットは 2.7–3.9 倍に向上；
  - 2.0 は複数プロセスを追加し、マシンにより小さなページのスループットが 25 % からほぼ 100 % 向上します。
  1.0 は送信前に各ファイル全体をメモリに読み込んでいました。2.0 はブロック単位で送るか、システムのカーネルに任せます。
- **2.0 から 2.5 で Python エンジンの速度は変わりません**：マシン B と C では差が 4 % 未満、バックグラウンド負荷に最も敏感なマシン A では測定誤差の範囲内（−13 % から +9 %）です。2.5 の向上はすべて**ネイティブエンジン**によるもので、小さなファイルで Python エンジンの約 ×10–×27、レイテンシは 1/5 から 1/15 になります。
- **ネイティブエンジンはアイドル時に Python エンジンより約 5 MB 多く使います**（PSS）：2 つ目のプログラムの代償です。WAF ありではさらに約 8 MB 多くなります。ネイティブエンジンに読み込まれたルールの分です。

### ネイティブエンジンについて知っておくべきこと

- **オプション**です：Python エンジンが引き続き既定のエンジンであり、代替エンジンでもあります。
- 静的コンテンツ、リダイレクト、書き換え、エイリアス、キャッシュ、エラーページ、セキュリティヘッダー、TLS を自ら処理します。
- WAF ルールを自ら検査し、どのルールにも一致しないリクエストに自ら応答します。それ以外のリクエスト（WAF の一致または疑い、Active Defense、認証）は Python が判断し、検査もログもまったく同じです。設定可能なチェックにより、クリーンなリクエストの N 件に 1 件は Python にも渡され、両者が同じ判定を下すことを確認します。
- ディレクトリ一覧と内部ページは Python に問い合わせます。リバースプロキシ、FastCGI、ファイルのアップロード、WebSocket は接続全体を Python に引き渡します。そのため、これらの機能は Python エンジンの速度のままです。
- 直接 TLS の場合、リバースプロキシ、FastCGI、ファイルのアップロードはネイティブエンジンでは扱えません。その場合は Python エンジンが処理し、インターフェースにそのことが表示されます。
- glibc 2.38 以降と OpenSSL 3 が必要です。起動できない場合はインストーラーがその場で再コンパイルし、それも不可能なら omega-serv は Python エンジンのまま動作します。

---

## 6. 機能比較

凡例：
- ✅ 組み込み；
- 🧩 プロジェクト公式のモジュール（有効化またはインストールが必要）；
- 🔌 サードパーティのモジュールまたはプラグイン；
- ⚙️ 外部ツールによる；
- ❌ なし。

「Commercial」は有償版でのみ提供される機能を示します。

### HTTP サービス

| 機能 | nginx | lighttpd | Caddy | Apache | Traefik | omega-serv 2.5 |
|---|---|---|---|---|---|---|
| サーバーの言語 | C | C | Go | C | Go | Python、オプションで C++ のネイティブエンジン |
| 静的ファイルの配信 | ✅ | ✅ | ✅ | ✅ | ❌（プロキシのみ） | ✅ |
| ETag / 304 / Range | ✅ | ✅ | ✅ | ✅ | — | ✅ |
| 事前圧縮ファイル `.gz` / `.br` | ✅ `gzip_static`（`.br`：🔌） | 🔌 Lua スクリプト（mod_magnet） | ✅ `precompressed` | 🧩 mod_rewrite のレシピ | — | ✅ |
| オンザフライ圧縮 | ✅ | ✅ mod_deflate | ✅ | 🧩 mod_deflate | ✅ middleware | ❌ |
| HTTP/2 | ✅ | ✅ | ✅ | 🧩 mod_http2 | ✅ | ❌ |
| HTTP/3（QUIC） | ✅ | ❌ | ✅ | ❌ | ✅ | ❌ |
| FastCGI 経由の PHP | ✅ | ✅ | ✅ | ✅ | ❌ | ✅ |
| 複数プロセスまたは複数コア | ✅ workers | ⚠️ `max-worker`、ドキュメントでは非推奨 | ✅（Go、全コア） | ✅ MPM | ✅（Go） | ✅ `server.workers`；ネイティブエンジン：全コア |

### リバースプロキシ

| 機能 | nginx | lighttpd | Caddy | Apache | Traefik | omega-serv 2.5 |
|---|---|---|---|---|---|---|
| 負荷分散 | ✅ ラウンドロビン、最少接続、ハッシュ | ✅ fair、round-robin、hash、sticky | ✅ 十数種類の方式 | 🧩 mod_proxy_balancer | ✅ wrr、p2c、hrw、least-time | ✅ 実負荷を含む 7 方式 |
| パッシブチェック（故障サーバーの除外） | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| アクティブチェック（定期プローブ） | Commercial（NGINX Plus） | ❌ | ✅ | 🧩 mod_proxy_hcheck | ✅ | ✅ |
| 応答キャッシュ | ✅ `proxy_cache` | ❌ | 🔌 | 🧩 mod_cache | Commercial | ✅ |
| WebSocket | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| サービス検出（Docker、Kubernetes） | 🔌 | ❌ | 🔌 | ❌ | ✅（プロジェクトの中核） | ❌ |

### TLS

| 機能 | nginx | lighttpd | Caddy | Apache | Traefik | omega-serv 2.5 |
|---|---|---|---|---|---|---|
| 証明書の自動取得（ACME、Let's Encrypt） | 🧩 `ngx_http_acme_module` | ⚙️ Certbot | ✅ 既定で有効 | 🧩 mod_md | ✅ | ⚙️ Certbot、組み込みのウィザードと定期更新付き |
| ローカル CA | ❌ | ❌ | ✅ 内部 CA（自動発行） | ❌ | ❌ | ✅ 作成、CSR への署名、失効 |

### セキュリティ

| 機能 | nginx | lighttpd | Caddy | Apache | Traefik | omega-serv 2.5 |
|---|---|---|---|---|---|---|
| クライアントごとのレート制限 | ✅ `limit_req` | ⚠️ mod_evasive（同時接続のみ） | 🔌 caddy-ratelimit | 🔌 mod_evasive、mod_qos | ✅ middleware | ✅ |
| プロセス間で共有される制限 | ✅ 共有メモリゾーン | ❌ プロセスごとにカウント | —（単一プロセス） | モジュール次第 | 1 インスタンス；複数は Redis で | ✅ 共有メモリ |
| WAF（SQLi/XSS のシグネチャ、スキャナーなど） | 🔌 ModSecurity、Commercial（App Protect） | ❌（Lua スクリプトを自作） | 🔌 Coraza | 🔌 ModSecurity | 🔌 プラグイン | ✅ 組み込み |
| 期限付きブロックリスト、再発カウント | ⚙️ fail2ban | ⚙️ fail2ban | ⚙️ fail2ban | ⚙️ fail2ban | ⚙️ | ✅ 組み込み |
| おとり、戦時モード、インシデント、IoC エクスポート | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ Active Defense |
| 時間とともに段階的に強まる BAN | ⚙️ fail2ban | ⚙️ fail2ban | ⚙️ fail2ban | ⚙️ fail2ban | ⚙️ | ✅ RIPOSTE |
| 設定のセキュリティ監査 | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ `audit security` |
| 観察モード（遮断せずに記録） | モジュール次第 | — | プラグイン次第 | ✅ ModSecurity `DetectionOnly` | プラグイン次第 | ✅ |

段階的な BAN：戻ってくるアドレスに対し、数週間にわたって、ローカルまたはネットワークのレベルで、だんだん長くなる BAN を科すものです。fail2ban は `bantime.increment` オプションでこれを実現します。RIPOSTE はさらに、ログで測定でき有効化前にシミュレーションできるポリシー、アクションの解除、緊急停止を加えます。

### 拡張性

| 機能 | nginx | lighttpd | Caddy | Apache | Traefik | omega-serv 2.5 |
|---|---|---|---|---|---|---|
| スクリプト言語 | 🧩 njs（JavaScript）；🔌 Lua（OpenResty） | ✅ Lua（mod_magnet） | Go モジュール（再コンパイル） | 🧩 mod_lua | Go または WebAssembly のプラグイン | 🔌 mod_magnet スクリプトの取り込み（`magnet` オプション） |
| モジュールのエコシステム | 非常に大きい | 的を絞っている | 大きい | 非常に大きい | 大きい | なし：すべて組み込み |

---

## 7. 管理と使いやすさ

| サーバー | 主な管理方法 | インターフェース | 中断なしの再読み込み |
|---|---|---|---|
| nginx | 設定ファイル | なし（ダッシュボード：NGINX Plus、商用） | ✅ `nginx -s reload` |
| lighttpd | 設定ファイル | なし（mod_status は読み取り専用） | ✅ グレースフル再起動 |
| Caddy | Caddyfile または JSON | REST 管理 API | ✅ API 経由 |
| Apache | 設定ファイルと `.htaccess` | なし（mod_status は読み取り専用） | ✅ `graceful` |
| Traefik | コンテナのラベル、ファイル、または Kubernetes | Web ダッシュボード（読み取り専用） | ✅ 動的設定 |
| omega-serv | ターミナルインターフェース（TUI）とコマンドライン（CLI）；JSON ファイルの編集は不要 | **キーボードとマウスで操作する完全な TUI、17 言語、組み込みヘルプ** | ✅ ほとんどの設定；ポート、TLS、エンジン、プロセス数は再起動が必要と表示 |

実際には、omega-serv は設定、セキュリティ、ログ、システムサービス、バックアップ、インスタンスを 1 つのインターフェースから管理します。各設定には説明があり、書き込み前に検証されます。他のサーバーでは、テキストファイルを編集し、さらに個別のツール（Certbot、fail2ban、logrotate、ModSecurity、監視ツールなど）を使います。

一方、nginx、Apache、Caddy の「設定ファイル」方式は自動化に非常に向いています（Ansible、コンテナ、バージョン管理）。omega-serv にもスクリプト向けの CLI がありますが、自動化のエコシステムはまだ限られています。

---

## 8. omega-serv が上乗せしているもの

この節には、比較したどのサーバーも、サードパーティのモジュールや外部ツールなしにはこの形で提供していないものだけを挙げています。

1. **ターミナルインターフェースでの完全な管理。**
   - インターフェースはサーバー全体をカバーします：サイト、セキュリティ、ログ、サービス、バックアップ、インスタンス。
   - キーボードとマウスで操作でき、グラフィカル環境のないサーバーでも、SSH 経由でも使えます。
   - 17 言語に対応し、各設定を説明します。
   - 他のサーバーには管理インターフェースがない（nginx、lighttpd、Apache）か、API のみ（Caddy）、または読み取り専用のダッシュボード（Traefik）です。
2. **モジュールを組み合わせる必要のない、組み込みのアクティブなセキュリティ。**
   - WAF には、シグネチャ、編集可能なパスのリスト、再発カウント、期限付きブロックリスト、レピュテーション、観察モードが含まれます。
   - Active Defense は、おとり、戦時モード、インシデントの追跡、侵害指標のエクスポート、影響のないシミュレーションを加えます。
   - RIPOSTE は時間軸で対応します：戻ってくるアドレスを記憶し、段階的な対応を適用します。だんだん長くなる BAN（既定で 1 時間、6 時間、24 時間、7 日）を、ブロックリストでローカルに、または fail2ban（omega-jail）経由でネットワークレベルで科すか、おとりを延長します。各ポリシーは実際のログで測定でき、有効化前にシミュレーションできます。各アクションは常に見える状態にあって解除でき、緊急停止もあります。
   - 他のサーバーでは、これらの機能には ModSecurity または Coraza、ルールセット、fail2ban を組み合わせる必要があります。
3. **複数プロセスでも正確なセキュリティ制限。**
   - 複数プロセスでは、レート制限と WAF の再発カウントがメモリ上で共有されます。そのため攻撃者は、プロセス数を利用して自分の上限を何倍にもすることができません。
   - lighttpd は逆のケースを文書化しています：`server.max-worker` を使うと、`mod_evasive` と `mod_status` はプロセスごとに別々にカウントします。
   - nginx もカウンター（`limit_req` ゾーン）を共有しますが、組み込みの WAF はありません。
4. **2 つのエンジン、1 つの振る舞い。** ネイティブエンジンと Python エンジンは同じ応答と同じログを生成し、これは比較用テストベンチで自動的に検証されています。ログを読むツール（fail2ban など）には違いが一切見えません。
5. **lighttpd の mod_magnet スクリプトの取り込み。**
   - lighttpd 用に書かれた Lua の防御スクリプトを、書き直さずに取り込めます。
   - 組み込みの防御を補完し、決してそれを弱めることはできません。互換性は有効化前に確認されます。
6. **複数インスタンスの管理。**
   - レジストリがすべてのインスタンスを記録し、インターフェースでそれらを切り替えられます。
   - インスタンスを完全にアンインストールすることもできます。
7. **設定のセキュリティ監査**：`audit security` コマンドは情報提供のみで、決して遮断せず、スクリプトで使える終了コードを返します。
8. **リモートのログソース。**
   - インターフェースは別のサーバーのログを SSH で、必要なときに、パスワードを保存せずに取得します。
   - それを lnav で、ローカルのログと統合して読むことができます。
9. **無効にできない HTTP のハードニング**：インストール直後から、どのプロファイルでもどのエンジンでも有効です。
   - Host ヘッダーの厳格な検証；
   - Content-Length / Transfer-Encoding の曖昧さの拒否；
   - サイトの応答（エラーページを含む）へのセキュリティヘッダーと CSP；
   - X-Forwarded-For の安全な読み取り；
   - root での起動の拒否。

---

## 9. 他のサーバーのほうが優れている点

- **スループット**：lighttpd と nginx は、小さなファイルと中サイズのファイルで依然として最速で、3 台すべてで同じです。ネイティブエンジンでも、omega-serv は小さなファイルで nginx の約 0.7、lighttpd の約 0.5、100 KB のファイルで nginx の 0.3–0.6 です。トラフィックの多いサイト、公開 API、CDN には、これらを選ぶべきです。
- **中サイズのファイル**：Apache は 100 KB のファイルを、3 台すべてで omega-serv のネイティブエンジンより速く配信します。
- **メモリ**：lighttpd（1 MB）、nginx（4–5 MB）、Apache（4–9 MB）は、非常に制約の多いマシン（組み込みシステム、小さなコンテナ）に向いています。omega-serv には 30–65 が必要です。
- **セキュリティのコスト**：WAF にはやはりコストがあります。ネイティブエンジンでは、レート制限を含め、小さなファイルでスループットが 5–22 % 低下します：WAF ありの omega-serv は、マシン A と B で WAF なしの nginx の 0.53–0.56 です。疑わしい、または判断が分かれるリクエスト（ルールの一致、ASCII 以外のテキスト、Active Defense が監視している送信元）は常に Python を経由し、Python エンジンの速度で処理されます。magnet を有効にすると、すべてのリクエストが Python を経由し、最適化前と同様に WAF によってネイティブエンジンのスループットが 1/4 から 1/7 に落ちます。
- **プロトコル**：HTTP/2 は他のすべてのサーバーが、HTTP/3 は nginx、Caddy、Traefik が対応しています。omega-serv は HTTP/1.1 のみです。
- **自動 HTTPS**：Caddy と Traefik は既定で有効、nginx（`ngx_http_acme_module`）と Apache（`mod_md`）は公式モジュールで対応します。omega-serv はこれを Certbot に任せ、ウィザードと定期更新を備えています。
- **コンテナ環境**：Traefik の自動サービス検出（Docker、Kubernetes）に相当する機能は omega-serv にはありません。
- **エコシステムと成熟度**：nginx と Apache には何千ものモジュール、ガイド、連携があり、何十年もの本番運用の実績があります。Caddy には Go のモジュールシステムがあります。omega-serv は 1 人で保守されている若いプロジェクトで、ネイティブエンジンはまだ非常に新しいものです。
- **オンザフライ圧縮**：omega-serv は事前に圧縮されたファイルしか配信しません。

---

## 10. 用途別のサーバー選び

| 用途 | 推奨 |
|---|---|
| トラフィックの多いサイト、公開 API、CDN、最大スループット | **nginx** または **lighttpd** |
| 非常に制約の多いマシン、組み込みシステム、静的ファイル | **lighttpd** |
| 自動 HTTPS ですぐに始めたい、短い設定 | **Caddy** |
| 古い PHP アプリケーション、`.htaccess`、共有ホスティング | **Apache** |
| Docker、Kubernetes、マイクロサービス | **Traefik** |
| 小〜中規模のサイト、社内サービス、検証環境、VPN、ファイルを編集しない管理 | **omega-serv**（可能ならネイティブエンジン） |
| インターネットに公開するサーバーで、セキュリティ（WAF、段階的な BAN、おとり）を 1 つのインターフェースで確認・制御したい | **omega-serv** |
| 負荷分散、チェック、キャッシュを備え、インターフェースから管理する社内リバースプロキシ | **omega-serv** |
| HTTP のハードニングとアクティブ防御の学習 | **omega-serv** |

これらのツールは組み合わせることもできます。例えば：
- インターネット側に nginx または Traefik を置き、その背後で omega-serv が社内サービスとそのセキュリティ、管理を担う；
- 複数のアプリケーションサーバーの前で、omega-serv を社内リバースプロキシとして使う。

---

## 11. 測定の再現

ツールはリポジトリの `tools/bench/` に含まれています。nginx、lighttpd、Apache、Caddy、oha のインストール、omega-serv の開発環境（`.venv`）、さらにネイティブエンジンには `native/omega-http-core/build-release` にコンパイルしたバイナリが必要です。

```sh
# 1. 測定フォルダーの準備（テストファイル、設定、omega-serv 1.0、2.0、現行版）
tools/bench/compare/setup.sh /path/measures omega-serv-1.0.0.tar.gz omega-serv-2.0.0.tar.gz

# 2. 21 の設定、交互に 3 回繰り返し（40–60 分）
#    SRV_CPUS / CLI_CPUS：サーバーとクライアントのコア（lscpu -e でトポロジーを確認）
SRV_CPUS=0,1 CLI_CPUS=2,3 tools/bench/compare/campaign.sh /path/measures > results.txt

# 3. 中央値
python3 tools/bench/compare/summarize.py results.txt

# 別の設定リスト、例えば 4 プロセス
CONFIGS="nginx-4 lighttpd-4 caddy-4 apache-4 omega-v2-1-0-native omega-v2-4-1-native" \
  tools/bench/compare/campaign.sh /path/measures > results-4.txt

# 大きなファイルのダウンロード（メモリと応答性）：現行版の Python エンジン、次にネイティブ、次に 1.0
.venv/bin/python tools/bench/bigfile.py
BENCH_ENGINE=native .venv/bin/python tools/bench/bigfile.py
BENCH_SRC=/path/measures/v1-archive/omega-serv/src \
BENCH_EXTRA_PATH=/path/measures/v1-archive/omega-serv/vendor/omega-lib/src \
  .venv/bin/python tools/bench/bigfile.py

# すでに動いている他の任意のサーバーを oha なしで測定
python3 tools/bench/bench_any.py --make-files /srv/webroot-test
python3 tools/bench/bench_any.py --port 8080
```

設定名：`nginx-N`、`lighttpd-N`、`apache-N`、`caddy-N`（N プロセス、Caddy は N コア）；omega-serv は `omega-vX-N-W`（バージョン `v1`、`v20`、現行版は `v2`、N プロセス、W = 0 で WAF なし、1 で WAF あり）、ネイティブエンジンには接尾辞 `-native`。

ご自身の結果を公開する場合は、マシン、バージョン、コアの割り当て、3 回の繰り返しを明記してください。

---

## 12. 出典

他のサーバーの機能は、各公式ドキュメントにもとづいています（2026 年 10 月 26 日に参照）。

**nginx**
- [レート制限 `limit_req`（共有メモリゾーン）](https://nginx.org/en/docs/http/ngx_http_limit_req_module.html)
- [事前圧縮ファイル `gzip_static`](https://nginx.org/en/docs/http/ngx_http_gzip_static_module.html)
- [公式 ACME モジュール `ngx_http_acme_module`](https://nginx.org/en/docs/http/ngx_http_acme_module.html)
- [負荷分散（`upstream`）](https://nginx.org/en/docs/http/ngx_http_upstream_module.html)
- [HTTP/3](https://nginx.org/en/docs/http/ngx_http_v3_module.html)
- [nginx 用 ModSecurity コネクター](https://github.com/owasp-modsecurity/ModSecurity-nginx)

**lighttpd**
- [`server.max-worker`：非推奨、mod_status と mod_evasive はプロセスごとのカウンター](https://redmine.lighttpd.net/projects/lighttpd/wiki/Server_max-workerDetails)
- [mod_magnet（Lua スクリプト）](https://redmine.lighttpd.net/projects/lighttpd/wiki/Docs_ModMagnet)
- [mod_deflate（圧縮、キャッシュ）](https://redmine.lighttpd.net/projects/lighttpd/wiki/Mod_deflate)
- [mod_proxy（負荷分散、パッシブチェック、WebSocket）](https://redmine.lighttpd.net/projects/lighttpd/wiki/Docs_ModProxy)
- [mod_evasive（1 つのアドレスからの同時接続）](https://redmine.lighttpd.net/projects/lighttpd/wiki/Docs_ModEvasive)

**Caddy**
- [自動 HTTPS](https://caddyserver.com/docs/automatic-https)
- [`file_server` と `precompressed`](https://caddyserver.com/docs/caddyfile/directives/file_server)
- [`reverse_proxy`（方式、アクティブおよびパッシブチェック）](https://caddyserver.com/docs/caddyfile/directives/reverse_proxy)
- [管理 API](https://caddyserver.com/docs/api)
- [レート制限プラグイン caddy-ratelimit](https://github.com/mholt/caddy-ratelimit)
- [Caddy 用 Coraza WAF](https://github.com/corazawaf/coraza-caddy)
- [caddy-docker-proxy](https://github.com/lucaslorentz/caddy-docker-proxy)

**Apache HTTP Server**
- [MPM event](https://httpd.apache.org/docs/2.4/mod/event.html)
- [mod_md（ACME）](https://httpd.apache.org/docs/2.4/mod/mod_md.html)
- [mod_proxy_balancer](https://httpd.apache.org/docs/2.4/mod/mod_proxy_balancer.html)
- [mod_proxy_hcheck](https://httpd.apache.org/docs/2.4/mod/mod_proxy_hcheck.html)
- [mod_http2](https://httpd.apache.org/docs/2.4/mod/mod_http2.html)
- [mod_deflate、事前圧縮コンテンツ](https://httpd.apache.org/docs/2.4/mod/mod_deflate.html)
- [ModSecurity](https://github.com/owasp-modsecurity/ModSecurity)

**Traefik**
- [`ratelimit` middleware（インスタンスごとのメモリ内、Redis は任意）](https://doc.traefik.io/traefik/reference/routing-configuration/http/middlewares/ratelimit/)
- [ACME](https://doc.traefik.io/traefik/https/acme/)
- [Providers（Docker、Kubernetes など）](https://doc.traefik.io/traefik/providers/overview/)

**fail2ban**
- [`jail.conf`：`bantime.increment`、`bantime.factor`、`bantime.multipliers`、`bantime.maxtime`（再犯者へのより長い BAN）](https://github.com/fail2ban/fail2ban/blob/master/config/jail.conf)（2026 年 11 月 4 日に参照）

**測定ツール**
- [oha](https://github.com/hatoo/oha)

---

*この比較は kraynux が omega-serv 2.5 のために作成しました：測定は 2026 年 11 月 3 日と 4 日に 3 台のマシンで実施（アクティブ防御：2026 年 10 月 26 日）。容量に関する判断の際は、付属のツールでご自身のハードウェアで測定してください。*
