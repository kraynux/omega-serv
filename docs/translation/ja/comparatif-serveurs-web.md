<!-- Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE) -->

# omega-serv と市場の Web サーバーの比較

**計測による比較：nginx · lighttpd · Caddy · Apache · Traefik · omega-serv 2.0**

🌐 [Français](../../comparatif-serveurs-web.md) · [English](../en/comparatif-serveurs-web.md) · [Español](../es/comparatif-serveurs-web.md) · [Português (Brasil)](../pt-BR/comparatif-serveurs-web.md) · [Italiano](../it/comparatif-serveurs-web.md) · [Deutsch](../de/comparatif-serveurs-web.md) · [Nederlands](../nl/comparatif-serveurs-web.md) · [Polski](../pl/comparatif-serveurs-web.md) · [Русский](../ru/comparatif-serveurs-web.md) · [中文](../zh-CN/comparatif-serveurs-web.md) · [Tiếng Việt](../vi/comparatif-serveurs-web.md) · [ไทย](../th/comparatif-serveurs-web.md) · [Bahasa Indonesia](../id/comparatif-serveurs-web.md) · **日本語** · [한국어](../ko/comparatif-serveurs-web.md) · [हिन्दी](../hi/comparatif-serveurs-web.md) · [العربية](../ar/comparatif-serveurs-web.md)

この文書は、最も広く使われている Web サーバーの中に omega-serv を位置づけるものです。「最高のサーバー」を決めようとするものではありません：ツールごとに応える用途が異なるからです。この文書は次の 3 つを示します：

1. 同じマシン、同じクライアント、同じファイルで行った、再現可能な **実測値**。
2. 各サーバーの公式ドキュメント（文書末尾にリンク）で 1 つずつ確認した **機能比較**。組み込み機能と、モジュールやプラグインが必要な機能を区別しています。
3. omega-serv が **本当に上乗せしているもの** と、他のサーバーのほうが **優れている点**。

以下の数値はすべて 2026 年 10 月 26 日に計測したものです。他のサイトから引用した数値や推定値は一切ありません。

---

## 目次

1. [概要](#1-概要)
2. [計測方法](#2-計測方法)
3. [性能：nginx、lighttpd、Caddy と比べた omega-serv](#3-性能nginxlighttpdcaddy-と比べた-omega-serv)
4. [omega-serv 1.0 → 2.0：変わったことと計測結果](#4-omega-serv-10--20変わったことと計測結果)
5. [機能比較](#5-機能比較)
6. [管理と使いやすさ](#6-管理と使いやすさ)
7. [omega-serv が上乗せしているもの](#7-omega-serv-が上乗せしているもの)
8. [他のサーバーのほうが優れている点](#8-他のサーバーのほうが優れている点)
9. [用途別のサーバーの選び方](#9-用途別のサーバーの選び方)
10. [計測の再現](#10-計測の再現)
11. [出典](#11-出典)

---

## 1. 概要

- **小さなファイルでの生のスループット**：C で書かれた nginx と lighttpd は、Python で書かれた omega-serv の **10〜20 倍** の秒間リクエストを処理します。Go で書かれた Caddy はその中間です。これは調整の問題ではなく本質的な差で、omega-serv はこの領域を狙っていません。
- **大きなファイル**：2.0 以降、omega-serv は送信をカーネル（`sendfile`）に任せます。その結果、このマシンでは nginx、lighttpd、Caddy と **同じ桁のスループット** に達します：2.1 GB/s 対 2.0〜2.4 GB/s。
- **メモリ**：lighttpd（1 MB）と nginx（4〜5 MB）には届きません。omega-serv は 1 プロセスで負荷時 30 MB 未満、Caddy は約 55 MB です。
- **1.0 から 2.0 へ**：大きなファイルのスループットは 2.8 倍、大きなダウンロード中のメモリは 45 分の 1、2 プロセス（boost モード）で小さなファイルが最大 +50 %、Active Defense のコストは 12 分の 1。
- **omega-serv にあるもの**：ターミナルインターフェース（TUI）による 17 言語の完全な管理、WAF とアクティブ防御の内蔵、複数プロセスでも正確なままのセキュリティ上限、lighttpd mod_magnet スクリプトのインポート、複数インスタンスの管理。
- **ないもの**：HTTP/2 と HTTP/3、Docker/Kubernetes のサービスディスカバリー、組み込みの ACME クライアント（Certbot を利用）、C で書かれたサーバーのスループット。

---

## 2. 計測方法

### マシンとソフトウェア

| 項目 | 値 |
|---|---|
| プロセッサー | Intel Core i5 M480 2.67 GHz（2010 年）：物理 2 コア、4 スレッド |
| メモリ | 8 GB |
| システム | Manjaro Linux、カーネル 6.18 |
| ネットワーク | ローカルループバック（127.0.0.1） |
| 負荷クライアント | [oha](https://github.com/hatoo/oha) 1.16.0（Rust 製） |
| nginx | 1.30.4（Manjaro パッケージ） |
| lighttpd | 1.4.85（Manjaro パッケージ） |
| Caddy | 2.11.4（Manjaro パッケージ） |
| omega-serv | 1.0.0（公開アーカイブ）と 2.0.0、Python 3.14.7 上 |

Apache と Traefik は、このマシンにインストールされていないため計測していません。そもそも Traefik はファイルサーバーではありません（§5 参照）。この 2 つは機能比較にのみ登場します。

### 手順

- **プロセッサーの分離**：各サーバーを物理コア 0（スレッド 0 と 2）に、クライアントを物理コア 1（スレッド 1 と 3）に固定しました。これによりクライアントがサーバーの時間を奪わず、すべてのサーバーがまったく同じリソースを使えます。
- **全サーバーで同じファイル**：`small.html`（1 KB）、`medium.png`（100 KB）、`large.bin`（5 MB）を同じフォルダーから配信。
- **すべてでアクセスログを有効化**。本番のサーバーはログを取るためです。
- **平文の HTTP/1.1、持続的接続（keep-alive）**。同時接続数は 1 KB と 100 KB のファイルで 32、5 MB のファイルで 8。
- **時間**：ファイルと構成ごとに 10 秒。
- **繰り返し**：完全な 3 周を交互に実施（1 周目に全サーバー、次に 2 周目に全サーバー、など）。表には 3 周の **中央値** を示します。
- **メモリ**：サーバーの全プロセスの PSS（*Proportional Set Size*）の合計。RSS と異なり、プロセス間で共有されるページは 1 回しか数えません。アイドル時と負荷後に計測します。
- **構成**：nginx、lighttpd、Caddy は基本構成（静的ファイル、アクセスログ）。omega-serv は `standard` プロファイルで、WAF を無効にした場合と、同梱のルールをすべて有効にした場合。
- **プロセス数**：各サーバーを 1 プロセスと 2 プロセスで計測（nginx `worker_processes`、lighttpd `server.max-worker`、Caddy `GOMAXPROCS`、omega-serv `server.workers`）。

### 知っておくべき制限

- **控えめで古いマシンです。** 最近のサーバーでは絶対値はずっと高くなります。意味があるのは、同じセッションで計測したサーバー間の **比率** です。
- **セッション間のばらつき**：マシンのバックグラウンド負荷に応じて約 10〜30 %。同じセッション内の各周は一貫しています：omega-serv と Caddy では差が 5 % 未満、nginx と lighttpd ではそれより大きく、非常に高いスループットのぶんマシンの他の部分の影響を受けやすいためです。
- **ローカルループバック**：計測は実際のネットワークを通っていません。実際のネットワークでは、大きなファイルのスループットはほぼ常にサーバーではなく帯域幅で制限されます。
- この計測には **TLS はありません**。HTTPS では omega-serv は `sendfile` を使えず、ファイルをブロック単位で送信します。
- **生データ**：この文書とともに [`docs/benchmarks/2026-10-26-campagne-brute.txt`](../../benchmarks/2026-10-26-campagne-brute.txt) で公開しています。

---

## 3. 性能：nginx、lighttpd、Caddy と比べた omega-serv

### 小さなファイル（1 KB）：秒間リクエスト数

| サーバー | 1 プロセス | 2 プロセス | p99 レイテンシ（1 プロセス） |
|---|---:|---:|---:|
| lighttpd 1.4.85 | 25 521 | 29 700 | 4.5 ms |
| nginx 1.30.4 | 14 054 | 18 315 | 4.7 ms |
| Caddy 2.11.4 | 3 697 | 5 345 | 25.3 ms |
| **omega-serv 2.0** | **1 358** | **1 953** | **37.5 ms** |
| omega-serv 2.0 + WAF | 1 130 | 1 617 | 48.5 ms |
| omega-serv 1.0 | 1 304 | — | 41.2 ms |

### 中くらいのファイル（100 KB）：秒間リクエスト数

| サーバー | 1 プロセス | 2 プロセス |
|---|---:|---:|
| lighttpd | 11 635 | 13 037 |
| nginx | 8 024 | 9 555 |
| Caddy | 3 280 | 4 344 |
| **omega-serv 2.0** | **1 247** | **1 629** |
| omega-serv 2.0 + WAF | 1 012 | 1 347 |
| omega-serv 1.0 | 1 064 | — |

### 大きなファイル（5 MB）：スループット

| サーバー | 1 プロセス | 2 プロセス |
|---|---:|---:|
| lighttpd | 2 379 MB/s | 2 407 MB/s |
| nginx | 2 242 MB/s | 1 981 MB/s |
| Caddy | 2 165 MB/s | 2 229 MB/s |
| **omega-serv 2.0** | **1 658 MB/s** | **2 115 MB/s** |
| omega-serv 1.0 | 584 MB/s | — |

### メモリ（PSS、サーバーの全プロセス）

| サーバー | アイドル時 | 負荷後 |
|---|---:|---:|
| lighttpd（1 または 2 プロセス） | 1 MB | 1 MB |
| nginx（1 または 2 プロセス） | 4〜5 MB | 4〜5 MB |
| **omega-serv 2.0（1 プロセス）** | **26 MB** | **30 MB** |
| omega-serv 2.0（2 プロセス） | 39 MB | 48 MB |
| Caddy | 50 MB | 56 MB |
| omega-serv 1.0 | 22 MB | 100 MB |

### 読み方

- **小さな・中くらいのファイル** では、nginx や lighttpd との差は 1 桁（×10〜×20）です。これは Python で書かれたサーバーのコストです：各リクエストがインタープリターを通るのに対し、nginx と lighttpd はコンパイル済みの C で処理します。boost モードは差を縮めますが、埋めはしません。
- **大きなファイル** では、データをコピーするのがカーネル（`sendfile`）なので、サーバーどうしの差はなくなります。2 プロセスで omega-serv 2.0 は 2.1 GB/s に達し、他のサーバー（2.0〜2.4 GB/s）と同じ範囲です。
- **omega-serv の WAF のコストは小さなファイルで約 17 %** です：すべてのリクエストを検査するためです。nginx、lighttpd、Caddy は WAF なしで計測しました。これらのサーバーに WAF（ModSecurity、Coraza）を加えた場合にもコストがありますが、ここでは計測していません。
- **数値の目安として**：1 300 リクエスト/秒は、この 2010 年のマシンで 1 日 1 億 1,000 万リクエスト以上に相当します。これは omega-serv が想定する用途である個人サイト、社内サービス、ラボの必要量をはるかに超えています。

---

## 4. omega-serv 1.0 → 2.0：変わったことと計測結果

### 性能

両バージョンは、同じセッション、同じマシン、同じ手順で計測しました。

| 計測 | 1.0.0 | 2.0.0 | 変化 |
|---|---:|---:|---:|
| 小さなファイル（1 KB）、1 プロセス | 1 304 req/s | 1 358 req/s | +4 % |
| 小さなファイル（1 KB）、boost モード 2 プロセス | — | 1 953 req/s | 1.0 比 **+50 %** |
| WAF ありの小さなファイル、1 プロセス | 1 097 req/s | 1 130 req/s | +3 % |
| WAF ありの小さなファイル、2 プロセス | — | 1 617 req/s | 1.0 比 **+47 %** |
| 100 KB のファイル、1 プロセス | 1 064 req/s | 1 247 req/s | +17 % |
| 大きなファイル（5 MB）、1 プロセス | 584 MB/s | 1 658 MB/s | **×2.8** |
| 大きなファイル（5 MB）、2 プロセス | — | 2 115 MB/s | 1.0 比 **×3.6** |
| 負荷後のメモリ、1 プロセス | 100 MB | 30 MB | **÷3** |

### 大きなファイルの同時ダウンロード

テスト：300 MB のファイルを 3 本同時にダウンロードしながら、小さなページを継続的にリクエスト。2 回の実行で同じ結果が得られました。

| 計測 | 1.0.0 | 2.0.0 |
|---|---:|---:|
| サーバーのメモリのピーク | 1 835 MB | 40 MB |
| ダウンロード中の小さなページ：中央値 | 3〜4 ms | 2 ms |
| ダウンロード中の小さなページ：最悪値 | 1.7〜1.8 秒 | 5 ms |

1.0 は各ファイルを送信前に丸ごとメモリに読み込んでいました。2.0 はブロック単位で送るか、カーネルに任せます：メモリはファイルサイズに依存しなくなり、サーバーはダウンロード中も応答性を保ちます。

### アクティブ防御のコスト

疑わしいリクエストごとに Active Defense が脅威を 1 回観察するコストを、ディスク（ext4）上で 2 000 回の観察について計測：

| 計測 | 1.0.0 | 2.0.0 |
|---|---:|---:|
| 中央値 | 2.84 ms | 0.23 ms |
| p99 | 11.6 ms | 2.3 ms |
| 最大値 | 18〜20 ms | 37〜46 ms |

中央値は 12 分の 1 になりました。一方、最大値は 2.0 のほうが高くなっています：SQLite のジャーナルを定期的にディスクへ書き込むことによる、まれな単発のピークです。

### 2.0 で加わった機能

**市場の標準に追いつく**：nginx、lighttpd、Caddy、Apache はすでにこれらをすべて備えています。omega-serv はそれに追いつきました。

- 条件付きリクエスト（ETag、Last-Modified、304 応答）：ページの再読み込みでは変わったものだけを再ダウンロード。
- 部分リクエスト（Range、206/416）：ダウンロードの再開、動画のシーク。
- `sendfile` またはブロック単位でのファイル送信、メモリは安定。
- 元のファイルの隣に置いた事前圧縮ファイル（`.gz`、`.br`）。
- ファイルの種類（画像、フォント、CSS/JS）に応じたデフォルトの Cache-Control、調整可能。
- 複数のサーバープロセス（boost モード、`server.workers`）。

**より広がった機能：**

- **完全なリバースプロキシ。** 1.0 には単純な中継（ラウンドロビン、上流への TLS、WebSocket）しかありませんでした。2.0 で追加されたもの：
  - 6 つの分散戦略（合計 7 つ）。
  - セッションアフィニティとヘッダーによるルーティング。
  - 上流サーバーのパッシブ/アクティブなヘルスチェック。
  - 応答キャッシュ。
  - 過負荷とループからの保護。
  - ホットな操作。
- **フォルダー別・アドレスまたはネットワーク別のレート制限**（全体の上限に加えて）。
- **プロセス間で共有するセキュリティカウンター**（§7 参照）。
- 観察モードと組み込みエディターを備えた、すぐに使える **機微なパスのリスト**。
- **lighttpd mod_magnet スクリプトのインポート**（§7 参照）。
- 訪問者が見るページとエクスポートに別の言語を設定できる、**17 言語のインターフェース**。
- **全面的に見直したログ**：
  - ログのライブラリ。
  - lnav を含む 3 種類のビューア。
  - SSH による遠隔ログの取得。

---

## 5. 機能比較

凡例：
- ✅ 組み込み。
- 🧩 プロジェクト公式のモジュール（有効化またはインストールが必要）。
- 🔌 サードパーティのモジュールまたはプラグイン。
- ⚙️ 外部ツール経由。
- ❌ なし。

「商用」は有償版にのみある機能を指します。

### HTTP サービス

| 機能 | nginx | lighttpd | Caddy | Apache | Traefik | omega-serv 2.0 |
|---|---|---|---|---|---|---|
| 静的ファイルの配信 | ✅ | ✅ | ✅ | ✅ | ❌（プロキシのみ） | ✅ |
| ETag / 304 / Range | ✅ | ✅ | ✅ | ✅ | — | ✅ |
| 事前圧縮ファイル `.gz` / `.br` | ✅ `gzip_static`（`.br`：🔌） | 🔌 Lua スクリプト（mod_magnet） | ✅ `precompressed` | 🧩 mod_rewrite のレシピ | — | ✅ |
| オンザフライ圧縮 | ✅ | ✅ mod_deflate | ✅ | 🧩 mod_deflate | ✅ ミドルウェア | ❌ |
| HTTP/2 | ✅ | ✅ | ✅ | 🧩 mod_http2 | ✅ | ❌ |
| HTTP/3（QUIC） | ✅ | ❌ | ✅ | ❌ | ✅ | ❌ |
| FastCGI による PHP | ✅ | ✅ | ✅ | ✅ | ❌ | ✅ |
| 複数のプロセスまたはコア | ✅ workers | ⚠️ `max-worker`、ドキュメントでは非推奨 | ✅（Go、全コア） | ✅ MPM | ✅（Go） | ✅ `server.workers` |

### リバースプロキシ

| 機能 | nginx | lighttpd | Caddy | Apache | Traefik | omega-serv 2.0 |
|---|---|---|---|---|---|---|
| 負荷分散 | ✅ ラウンドロビン、最少接続、ハッシュ | ✅ fair、round-robin、hash、sticky | ✅ 十数種類の戦略 | 🧩 mod_proxy_balancer | ✅ wrr、p2c、hrw、least-time | ✅ 実負荷を含む 7 戦略 |
| パッシブヘルス（故障サーバーの除外） | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| アクティブヘルス（定期プローブ） | 商用（NGINX Plus） | ❌ | ✅ | 🧩 mod_proxy_hcheck | ✅ | ✅ |
| 応答キャッシュ | ✅ `proxy_cache` | ❌ | 🔌 | 🧩 mod_cache | 商用 | ✅ |
| WebSocket | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| サービスディスカバリー（Docker、Kubernetes） | 🔌 | ❌ | 🔌 | ❌ | ✅（プロジェクトの中核） | ❌ |

### TLS

| 機能 | nginx | lighttpd | Caddy | Apache | Traefik | omega-serv 2.0 |
|---|---|---|---|---|---|---|
| 証明書の自動化（ACME、Let's Encrypt） | 🧩 `ngx_http_acme_module` | ⚙️ Certbot | ✅ デフォルト | 🧩 mod_md | ✅ | ⚙️ Certbot、組み込みウィザードと定期更新付き |
| ローカル CA | ❌ | ❌ | ✅ 内部 CA（自動発行） | ❌ | ❌ | ✅ 生成、CSR への署名、失効 |

### セキュリティ

| 機能 | nginx | lighttpd | Caddy | Apache | Traefik | omega-serv 2.0 |
|---|---|---|---|---|---|---|
| クライアントごとのレート制限 | ✅ `limit_req` | ⚠️ mod_evasive（同時接続のみ） | 🔌 caddy-ratelimit | 🔌 mod_evasive、mod_qos | ✅ ミドルウェア | ✅ |
| プロセス間で共有する上限 | ✅ 共有メモリゾーン | ❌ プロセスごとに計数 | —（1 プロセスのみ） | モジュール次第 | 1 インスタンス、複数なら Redis | ✅ 共有メモリ |
| WAF（SQLi/XSS のシグネチャ、スキャナー…） | 🔌 ModSecurity、商用（App Protect） | ❌（Lua スクリプトを自作） | 🔌 Coraza | 🔌 ModSecurity | 🔌 プラグイン | ✅ 組み込み |
| 有効期限・再犯付きのブロックリスト | ⚙️ fail2ban | ⚙️ fail2ban | ⚙️ fail2ban | ⚙️ fail2ban | ⚙️ | ✅ 組み込み |
| おとり、戦闘モード、インシデント、IoC エクスポート | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ Active Defense |
| 設定のセキュリティ監査 | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ `audit security` |
| 観察モード（ブロックせずに記録） | モジュール次第 | — | プラグイン次第 | ✅ ModSecurity `DetectionOnly` | プラグイン次第 | ✅ |

### 拡張性

| 機能 | nginx | lighttpd | Caddy | Apache | Traefik | omega-serv 2.0 |
|---|---|---|---|---|---|---|
| スクリプト言語 | 🧩 njs（JavaScript）、🔌 Lua（OpenResty） | ✅ Lua（mod_magnet） | Go モジュール（再コンパイル） | 🧩 mod_lua | Go または WebAssembly のプラグイン | 🔌 mod_magnet スクリプトのインポート（`magnet` オプション） |
| モジュールのエコシステム | 非常に広い | 絞り込まれている | 広い | 非常に広い | 広い | なし：すべて組み込み |

---

## 6. 管理と使いやすさ

| サーバー | 主な管理方法 | インターフェース | 無停止のリロード |
|---|---|---|---|
| nginx | 設定ファイル | なし（ダッシュボード：NGINX Plus、商用） | ✅ `nginx -s reload` |
| lighttpd | 設定ファイル | なし（mod_status は読み取り専用） | ✅ グレースフル再起動 |
| Caddy | Caddyfile または JSON | 管理用 REST API | ✅ API 経由 |
| Apache | 設定ファイルと `.htaccess` | なし（mod_status は読み取り専用） | ✅ `graceful` |
| Traefik | コンテナのラベル、ファイル、または Kubernetes | Web ダッシュボード（読み取り専用） | ✅ 動的設定 |
| omega-serv | ターミナルインターフェース（TUI）とコマンドライン（CLI）、JSON ファイルの編集は不要 | **キーボードとマウスによる完全な TUI、17 言語、ヘルプ内蔵** | ✅ ほとんどの設定で。ポート、TLS、プロセス数は再起動を案内 |

具体的には、omega-serv では設定、セキュリティ、ログ、システムサービス、バックアップ、インスタンスをひとつのインターフェースで管理します。各設定は説明され、書き込み前に検証されます。他のサーバーでは、テキストファイルを編集し、別々のツール（Certbot、fail2ban、logrotate、ModSecurity、監視ツール…）を使います。

その代わり、nginx、Apache、Caddy の「設定ファイル」方式は自動化（Ansible、コンテナ、バージョン管理）と非常に相性がよいです。omega-serv にもスクリプト化できる CLI がありますが、自動化のエコシステムはまだ限られています。

---

## 7. omega-serv が上乗せしているもの

この節では、比較したどのサーバーもサードパーティのモジュールや外部ツールなしにはそのままでは提供していないものだけを挙げます。

1. **ターミナルインターフェースによる完全な管理。**
   - インターフェースはサーバー全体をカバーします：サイト、セキュリティ、ログ、サービス、バックアップ、インスタンス。
   - グラフィカルな表示のないサーバーでも、SSH 越しでも、キーボードとマウスで使えます。
   - 17 言語に対応し、各設定を説明します。
   - 他のサーバーには管理インターフェースがない（nginx、lighttpd、Apache）か、API（Caddy）や読み取り専用のダッシュボード（Traefik）があるだけです。
2. **組み立て不要の、組み込みのアクティブセキュリティ。**
   - WAF には、シグネチャ、編集可能なパスのリスト、再犯、有効期限付きのブロックリスト、レピュテーション、観察モードが含まれます。
   - Active Defense は、おとり、戦闘モード、インシデントの追跡、侵害の痕跡のエクスポート、空実行のシミュレーションを加えます。
   - 他では、これらの機能のために ModSecurity や Coraza、ルールセット、fail2ban を組み合わせる必要があります。
3. **複数プロセスでも正確なセキュリティ上限。**
   - boost モードでは、WAF のレート制限と再犯がプロセス間でメモリ共有されます。そのため攻撃者がプロセス数の分だけ上限を増やすことはできません。
   - lighttpd は逆のケースを文書化しています：`server.max-worker` では、`mod_evasive` と `mod_status` が各プロセスで別々に数えます。
   - nginx もカウンターを共有します（`limit_req` ゾーン）が、組み込みの WAF はありません。
4. **lighttpd mod_magnet スクリプトのインポート。**
   - lighttpd 向けにすでに書かれた Lua の保護スクリプトを、書き直さずにインポートできます。
   - 組み込みの保護に加わるだけで決して弱めることはできず、有効化前に互換性が確認されます。
5. **複数インスタンスの管理。**
   - レジストリがすべてのインスタンスを把握し、インターフェースが一方から他方へ切り替えます。
   - インスタンスを完全にアンインストールすることもできます。
6. **設定のセキュリティ監査**：`audit security` コマンドは情報提供のためのもので、決してブロックせず、スクリプトで使える終了コードを返します。
7. **遠隔のログソース。**
   - インターフェースは要求に応じて、パスワードを保存せずに、別のサーバーのログを SSH で取得します。
   - それをローカルのログと統合して lnav で読めます。
8. **無効化できない HTTP の堅牢化**。プロファイルにかかわらず、インストール直後から有効です：
   - Host ヘッダーの厳格な検証。
   - Content-Length / Transfer-Encoding の曖昧さの拒否。
   - エラーページを含むセキュリティヘッダーと CSP。
   - X-Forwarded-For の安全な読み取り。
   - root での起動の拒否。

---

## 8. 他のサーバーのほうが優れている点

- **スループットとレイテンシ**：nginx と lighttpd は小さなリクエストを 10〜20 倍多く処理し、レイテンシは 8〜10 倍低くなります。高トラフィックのサイト、公開 API、CDN には、これらを選ぶべきです。
- **メモリ**：lighttpd（1 MB）と nginx（4〜5 MB）は、リソースが非常に限られたマシン（組み込み、エントリーモデルの Raspberry Pi、小さなコンテナ）に適しています。
- **プロトコル**：他のすべてのサーバーに HTTP/2、nginx・Caddy・Traefik に HTTP/3 があります。omega-serv は HTTP/1.1 しか話しません。
- **自動 HTTPS**：Caddy と Traefik はデフォルトで組み込み、nginx（`ngx_http_acme_module`）と Apache（`mod_md`）は公式モジュールで対応しています。omega-serv は、ウィザードと定期更新を備えたうえで Certbot に任せます。
- **コンテナ環境**：Traefik の自動サービスディスカバリー（Docker、Kubernetes）に相当するものは omega-serv にはありません。
- **エコシステム**：nginx と Apache には数千のモジュール、ガイド、連携があります。Caddy には Go によるモジュールシステムがあります。omega-serv は一人で保守している若いプロジェクトです。
- **オンザフライ圧縮**：omega-serv が配信するのは事前に圧縮されたファイルだけです。

---

## 9. 用途別のサーバーの選び方

| 必要なもの | 推奨 |
|---|---|
| 高トラフィックのサイト、公開 API、CDN、最大スループット | **nginx** |
| リソースが非常に限られたマシン、組み込み、静的ファイル | **lighttpd** |
| 自動 HTTPS ですばやく開始、短い設定 | **Caddy** |
| 既存の PHP アプリケーション、`.htaccess`、共有ホスティング | **Apache** |
| Docker、Kubernetes、マイクロサービス | **Traefik** |
| 小さなサイト、社内サービス、ラボ、VPN、ファイルを編集しない管理 | **omega-serv** |
| セキュリティ（WAF、BAN、おとり）をひとつのインターフェースから見て制御したい公開サーバー | **omega-serv** |
| 分散、ヘルスチェック、キャッシュを備え、インターフェースから操作する社内のリバースプロキシ | **omega-serv** |
| HTTP の堅牢化とアクティブ防御を学ぶ | **omega-serv** |

これらのツールは組み合わせることもできます。例：
- インターネットの最前線に nginx や Traefik を置き、その背後で omega-serv が社内サービスとそのセキュリティ・管理を担う。
- 複数のアプリケーションサーバーの前に、omega-serv を社内のリバースプロキシとして置く。

---

## 10. 計測の再現

ツールはリポジトリの `tools/bench/` に同梱されています。nginx、lighttpd、Caddy、oha のインストールと、omega-serv の開発環境（`.venv`）が必要です。

```sh
# 1. 計測用フォルダーを準備（テストファイル、設定、omega-serv 1.0 と 2.0）
tools/bench/compare/setup.sh /path/mesure omega-serv-1.0.0.tar.gz

# 2. 12 の構成、交互に 3 回繰り返し（約 22 分）
tools/bench/compare/campaign.sh /path/mesure > results.txt

# 3. 中央値
python3 tools/bench/compare/summarize.py results.txt

# 大きなダウンロード（メモリと応答性）、2.0 の次に 1.0
.venv/bin/python tools/bench/bigfile.py
BENCH_SRC=/path/mesure/v1-archive/omega-serv/src \
BENCH_EXTRA_PATH=/path/mesure/v1-archive/omega-serv/vendor/omega-lib/src \
  .venv/bin/python tools/bench/bigfile.py

# oha なしで、すでに起動している他のサーバーを計測
python3 tools/bench/bench_any.py --make-files /srv/webroot-test
python3 tools/bench/bench_any.py --port 8080
```

デフォルトでは、計測マシンに合わせて、サーバーをスレッド 0 と 2、クライアントをスレッド 1 と 3 に固定します。この割り当ては変数 `SRV_CPUS` と `CLI_CPUS` で、お使いのプロセッサーに合わせて調整してください（トポロジーは `lscpu -e` でわかります）。

ご自身の結果を公開する場合は、マシン、バージョン、プロセッサーの割り当て、3 回の繰り返しを示してください。

---

## 11. 出典

他のサーバーの機能は、それぞれの公式ドキュメントに基づきます（2026 年 10 月 26 日に参照）。

**nginx**
- [レート制限 `limit_req`（共有メモリゾーン）](https://nginx.org/en/docs/http/ngx_http_limit_req_module.html)
- [事前圧縮ファイル `gzip_static`](https://nginx.org/en/docs/http/ngx_http_gzip_static_module.html)
- [公式 ACME モジュール `ngx_http_acme_module`](https://nginx.org/en/docs/http/ngx_http_acme_module.html)
- [負荷分散（`upstream`）](https://nginx.org/en/docs/http/ngx_http_upstream_module.html)
- [HTTP/3](https://nginx.org/en/docs/http/ngx_http_v3_module.html)
- [nginx 用 ModSecurity コネクター](https://github.com/owasp-modsecurity/ModSecurity-nginx)

**lighttpd**
- [`server.max-worker`：非推奨、mod_status と mod_evasive はプロセスごとにカウント](https://redmine.lighttpd.net/projects/lighttpd/wiki/Server_max-workerDetails)
- [mod_magnet（Lua スクリプト）](https://redmine.lighttpd.net/projects/lighttpd/wiki/Docs_ModMagnet)
- [mod_deflate（圧縮、キャッシュ）](https://redmine.lighttpd.net/projects/lighttpd/wiki/Mod_deflate)
- [mod_proxy（分散、パッシブヘルス、WebSocket）](https://redmine.lighttpd.net/projects/lighttpd/wiki/Docs_ModProxy)
- [mod_evasive（アドレスごとの同時接続）](https://redmine.lighttpd.net/projects/lighttpd/wiki/Docs_ModEvasive)

**Caddy**
- [自動 HTTPS](https://caddyserver.com/docs/automatic-https)
- [`file_server` と `precompressed`](https://caddyserver.com/docs/caddyfile/directives/file_server)
- [`reverse_proxy`（戦略、アクティブとパッシブのヘルス）](https://caddyserver.com/docs/caddyfile/directives/reverse_proxy)
- [管理 API](https://caddyserver.com/docs/api)
- [レート制限プラグイン caddy-ratelimit](https://github.com/mholt/caddy-ratelimit)
- [Caddy 用 WAF Coraza](https://github.com/corazawaf/coraza-caddy)
- [caddy-docker-proxy](https://github.com/lucaslorentz/caddy-docker-proxy)

**Apache HTTP Server**
- [mod_md（ACME）](https://httpd.apache.org/docs/2.4/mod/mod_md.html)
- [mod_proxy_balancer](https://httpd.apache.org/docs/2.4/mod/mod_proxy_balancer.html)
- [mod_proxy_hcheck](https://httpd.apache.org/docs/2.4/mod/mod_proxy_hcheck.html)
- [mod_http2](https://httpd.apache.org/docs/2.4/mod/mod_http2.html)
- [mod_deflate、事前圧縮コンテンツ](https://httpd.apache.org/docs/2.4/mod/mod_deflate.html)
- [ModSecurity](https://github.com/owasp-modsecurity/ModSecurity)

**Traefik**
- [ミドルウェア `ratelimit`（インスタンスごとのメモリ、Redis はオプション）](https://doc.traefik.io/traefik/reference/routing-configuration/http/middlewares/ratelimit/)
- [ACME](https://doc.traefik.io/traefik/https/acme/)
- [Providers（Docker、Kubernetes…）](https://doc.traefik.io/traefik/providers/overview/)

**計測ツール**
- [oha](https://github.com/hatoo/oha)

---

*kraynux が omega-serv 2.0.0 のために作成した比較：2026 年 10 月 26 日の計測。計測は 1 台のマシンのみで行っています。容量に関する判断は、同梱のツールを使ってご自身のハードウェアで計測してください。*
