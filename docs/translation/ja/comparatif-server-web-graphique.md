# omega-serv と市場のウェブサーバー — グラフ版

**omega-serv と nginx · lighttpd · Apache · Caddy · Traefik の比較 — 三台のマシンでの測定（2026年11月）。**

🌐 [Français](../../comparatif-server-web-graphique.md) · [English](../en/comparatif-server-web-graphique.md) · [Español](../es/comparatif-server-web-graphique.md) · [Português (Brasil)](../pt-BR/comparatif-server-web-graphique.md) · [Italiano](../it/comparatif-server-web-graphique.md) · [Deutsch](../de/comparatif-server-web-graphique.md) · [Nederlands](../nl/comparatif-server-web-graphique.md) · [Polski](../pl/comparatif-server-web-graphique.md) · [Русский](../ru/comparatif-server-web-graphique.md) · [中文](../zh-CN/comparatif-server-web-graphique.md) · [Tiếng Việt](../vi/comparatif-server-web-graphique.md) · [ไทย](../th/comparatif-server-web-graphique.md) · [Bahasa Indonesia](../id/comparatif-server-web-graphique.md) · **日本語** · [한국어](../ko/comparatif-server-web-graphique.md) · [हिन्दी](../hi/comparatif-server-web-graphique.md) · [العربية](../ar/comparatif-server-web-graphique.md)

> **読み方：** バーが長いほど、サーバーは速いことを表します。基準は **nginx = 1.00**。

## 色の凡例

<!-- 🖼️ IMAGE : legende-couleurs -->
<div align="center">
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/translation/ja/omega-serv/stats-1.png" alt="色の凡例" width="1024">
</div>

---

## 📊 1 KB ファイル — スループット（リクエスト/秒）

マシン A（i5 2010）、B（Celeron 2016）、C（Ryzen 2024）。バーは同じマシン上の nginx（1.00）を基準に正規化しています。

<!-- 🖼️ IMAGE : 1ko-banner — 3 colonnes côte à côte (Machine A · 2 cœurs | Machine B · 4 cœurs | Machine C · 10 cœurs), largeur totale -->
<div align="center">
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/translation/ja/omega-serv/stats-2.png" alt="1 KB ファイル — マシン A、B、C" width="1024">
</div>

> \* マシン C：ネイティブエンジンは 4 コア、nginx は 2 プロセス（2 コア）を使用。コア数を揃えると、比率は ~0.70 に下がります。
---

## 📦 中サイズのファイル（100 KB）— 通常のウェブモード

ここでは Apache が意外な健闘を見せ、omega-serv のネイティブエンジンをしばしば上回ります。最速は引き続き lighttpd です。基準：nginx = 1.00。

<!-- 🖼️ IMAGE : 100ko-banner.png — 3 colonnes côte à côte (A | B | C), largeur totale -->
<div align="center">
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/translation/ja/omega-serv/stats-3.png" alt="100 KB ファイル — マシン A、B、C" width="1024">
</div>

---

## 💿 大きなファイル（5 MB）— 通常のウェブモード

大きなファイルでは各サーバーの差が縮まります。データをコピーするのはカーネルだからです（sendfile）。マシン C では Caddy が例外です。スループットは MB/s。

<!-- 🖼️ IMAGE : 5mo-banner.png — 3 colonnes côte à côte (A | B | C), largeur totale -->
<div align="center">
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/translation/ja/omega-serv/stats-4.png" alt="5 MB ファイル — マシン A、B、C" width="1024">
</div>

---

## 🔄 リバースプロキシ — 小さな応答（1 KB）

各プロキシは nginx のバックエンドに中継します。基準：nginx = 1.00。マシン C：4 プロセス。

<!-- 🖼️ IMAGE : proxy-1ko-banner.png — 3 colonnes côte à côte (A | B | C), largeur totale -->
<div align="center">
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/translation/ja/omega-serv/stats-5.png" alt="プロキシ 1 KB — マシン A、B、C" width="1024">
</div>

---

## 🔄 リバースプロキシ — 100 KB の応答

中サイズの応答では、omega-serv ネイティブは nginx と同等かそれ以上です。

<!-- 🖼️ IMAGE : proxy-100ko-banner.png — 3 colonnes côte à côte (A | B | C), largeur totale -->
<div align="center">
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/translation/ja/omega-serv/stats-6.png" alt="プロキシ 100 KB — マシン A、B、C" width="1024">
</div>

---

## 💾 メモリ（PSS）— アイドル時 → 負荷後

バーが短いほど、サーバーは省メモリです。lighttpd、nginx、Apache が最も控えめで、omega-serv 3.0.0（11 月 19 日に再測定）がそれに続き、ネイティブエンジンでは 10〜16 MB です。

<!-- 🖼️ IMAGE : memoire-banner.png — 3 colonnes côte à côte de jauges (A | B | C), largeur totale -->
<div align="center">
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/translation/ja/omega-serv/stats-7.png" alt="メモリ — マシン A、B、C" width="1024">
</div>

---

## 🏆 通常のウェブモードのランキング — 最速はどれ？

三台のマシンでの静的ファイル配信の総括。

<!-- 🖼️ IMAGE : classement-web.png -->
<!-- Contenu : 1. 🥇 lighttpd — meilleur en petits & moyens fichiers · 2. 🥈 nginx — référence, excellent partout · 3. 🥉 omega-serv natif — très bon, 2ᵉ en reverse proxy · 4. Apache — bon, robuste, écosystème · 5. Caddy — simple, HTTPS auto · 6. omega-serv Python — moteur de repli -->
<div align="center">
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/translation/ja/omega-serv/stats-8.png" alt="通常のウェブモードのランキング" width="1024">
</div>

---

## 🔄 リバースプロキシのランキング — 最も優れているのはどれ？

nginx が引き続き基準で、omega-serv ネイティブはそれに最も近い次点であり、他を大きく引き離しています。

<!-- 🖼️ IMAGE : classement-proxy.png -->
<!-- Contenu : 1. 🥇 nginx · 2. 🥈 omega-serv natif — 0,82 à 0,91× nginx en 1 Ko · 3. 🥉 omega-serv + WAF — toujours devant lighttpd/Apache · 4. lighttpd — 0,53 à 0,61× · 5. Apache — 0,50 à 0,59× · 6. Traefik — 0,29 à 0,35× · 7. Caddy — 0,23 à 0,32× · 8. omega-serv Python — moteur de repli -->
<div align="center">
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/translation/ja/omega-serv/stats-9.png" alt="リバースプロキシのランキング" width="1024">
</div>

---

## 🆚 直接対決 — ウェブとリバースプロキシのランキングを並べて

二つの用途、二つのランキング。一方で光り、他方で見劣りするサーバーもあります。Apache は中継で意外な健闘を見せ、Caddy はシンプルさ以外ではどこでも期待外れです。

<!-- 🖼️ IMAGE : face-a-face.png — 2 colonnes côte à côte (web | proxy), largeur totale -->
<div align="center">
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/translation/ja/omega-serv/stats-10.png" alt="直接対決 ウェブ vs リバースプロキシ" width="1024">
</div>

### 総合評価

| サーバー | 位置づけ |
|---|---|
| 🟢 **omega-serv ネイティブ** | 最も万能：ウェブで3位、**リバースプロキシで2位**。WAF を内蔵し、中継で lighttpd と Apache の上に位置する唯一のサーバー。両方の用途を一つのツールでこなし、さらにセキュリティも得たい場合の最良の折衷案。 |
| 🔵 **nginx** | 最も安定：ウェブで2位、**リバースプロキシで1位**。常に上位にあり、目立った弱点なし。特に要件がない場合の標準的な選択肢。 |
| 🟢 **lighttpd** | 静的ファイルのスプリンター：**ウェブで1位**、ただし中継では4位。純粋な静的配信には最良の選択で、リバースプロキシが加わると omega-serv や nginx に譲る。 |
| 🔴 **Apache** | 反例：ウェブで4位、中継で5位。大きなファイルでは nginx をも上回る（マシン C）。最速でも最軽量でもなく、強みは PHP のエコシステム。 |
| 🟠 **Caddy** | 速度よりシンプルさ：ウェブで5位、**中継で7位**。スループット向きではなく、自動 HTTPS と短い設定が強み。小規模なプロジェクト向け。 |
| 🟣 **Traefik** | ウェブの対象外：ファイルサーバーではなく、中継で6位。本領は Docker と Kubernetes であり、純粋な性能ではない。 |

---

## 📋 完全な一覧表 — nginx（1.00）との比

**すべての**指標の概観：通常のウェブモード（1 KB、100 KB、5 MB）とリバースプロキシ（1 KB、100 KB）、さらにメモリ。値が 1.00 に近いか上回るほど良好です。

| サーバー | Web 1 KB (A/B/C) | Web 100 KB (A/B/C) | Web 5 MB (A/B/C) | Proxy 1 KB (A/B/C) | Proxy 100 KB (A/B/C) | メモリ (A/B/C) |
|---|---|---|---|---|---|---|
| **lighttpd** | 1.52 / 1.26 / 1.53 | 1.08 / 1.07 / 1.26 | 1.05 / 0.99 / 0.81 | 0.61 / 0.56 / 0.53 | 0.74 / 0.62 / 0.96 | 1 MB |
| **nginx** | 1.00 / 1.00 / 1.00 | 1.00 / 1.00 / 1.00 | 1.00 / 1.00 / 1.00 | 1.00 / 1.00 / 1.00 | 1.00 / 1.00 / 1.00 | 4–5 MB |
| **omega-serv (ネイティブ)** | **0.70 / 0.67 / 1.15\*** | **0.38 / 0.28 / 0.61** | **0.99 / 0.91 / 1.09** | **0.85 / 0.91 / 0.82** | **1.11 / 0.97 / 1.43** | 10–16 MB |
| **omega-serv + WAF** | 0.56 / 0.53 / 1.07\* | 0.37 / 0.27 / 0.62 | — | 0.81 / 0.89 / 0.77 | 1.10 / 0.93 / 1.30 | 28–33 MB |
| **Apache** | 0.42 / 0.35 / 0.76 | 0.55 / 0.62 / 0.97 | 1.01 / 1.00 / 1.19 | 0.59 / 0.53 / 0.50 | 0.62 / 0.65 / 0.71 | 4–9 MB |
| **Caddy** | 0.26 / 0.17 / 0.21 | 0.40 / 0.33 / 0.14 | 0.95 / 0.94 / 0.11 | 0.32 / 0.28 / 0.23 | 0.60 / 0.54 / 0.59 | 46–67 MB |
| **Traefik** | — | — | — | 0.35 / 0.35 / 0.29 | 0.64 / 0.60 / 0.70 | 93–131 MB |
| **omega-serv (Python)** | 0.11 / 0.05 / 0.08 | 0.14 / 0.10 / 0.12 | 0.92 / 0.91 / 0.75 | 0.09 / 0.08 / 0.07 | 0.21 / 0.19 / — | 20–48 MB |

> \* マシン C：ネイティブは 4 コア、nginx は 2 コア。コア数を揃えると、比率は ~0.67–0.71。
> セルごとの三つの値は、マシン **A / B / C** に対応します。「—」：未測定または該当なし。

---

## ⚖️ 長所と短所 — すべてのサーバー

各サーバーには強みと限界があります。ひいきなしの全体像です。

### 🟢 omega-serv（ネイティブ）

**長所**
- ✅ ターミナルでの完全な管理（TUI、17 言語）
- ✅ WAF + Active Defense + RIPOSTE を内蔵
- ✅ C++ ネイティブエンジン：静的配信で nginx の ~0.7 倍
- ✅ リバースプロキシで nginx に次ぐ 2 位
- ✅ プロセス間で共有される制限（正確なセキュリティ）
- ✅ lighttpd の mod_magnet スクリプトのインポート
- ✅ 複数インスタンスの管理
- ✅ Web 管理


**短所**
- ❌ HTTP/2 も HTTP/3 もなし
- ❌ オンザフライ圧縮なし
- ❌ Docker/Kubernetes のディスカバリなし
- ❌ ACME は Certbot 経由（ネイティブ統合ではない）
- ❌ 100 KB ファイル：nginx の 0.3–0.6 倍
- ❌ メモリ 10–55 MB、モードによる（nginx/lighttpd は 1–5 MB）
- ❌ 若いエコシステム、一人でメンテナンス

---

### 🔵 nginx

**長所**
- ✅ 性能と安定性の基準
- ✅ HTTP/2、HTTP/3、圧縮
- ✅ 巨大なエコシステム（モジュール、ドキュメント、コミュニティ）
- ✅ メモリ消費が非常に少ない（4–5 MB）
- ✅ 優れたリバースプロキシ
- ✅ 公式 ACME モジュール
- ✅ 成熟し、実績のある設定

**短所**
- ❌ 冗長な設定、独自の構文を学ぶ必要がある
- ❌ WAF 非内蔵（ModSecurity など同等のものが必要）
- ❌ ネイティブの管理インターフェースなし
- ❌ 設定のリロードが本番環境で難しいことがある
- ❌ オープンソース版は機能が限られる（一部の機能は有償の Nginx Plus）
- ❌ ネイティブな Docker/Kubernetes ディスカバリなし（テンプレート経由）

---

### 🟢 lighttpd

**長所**
- ✅ 小・中サイズのファイルで最速
- ✅ 最もメモリ効率が良い（1 MB）
- ✅ 軽量で、制約のあるシステムに適している
- ✅ 良好なリバースプロキシ
- ✅ シンプルで読みやすい設定

**短所**
- ❌ HTTP/3 なし（HTTP/2 はビルドによっては部分的）
- ❌ リバースプロキシでは 4 位にとどまる（nginx の 0.53–0.61 倍）
- ❌ nginx/Apache よりエコシステムが小さい
- ❌ WAF 非内蔵
- ❌ Docker/Kubernetes のディスカバリなし
- ❌ 以前より開発が活発でない
- ❌ 大きなファイルに弱い（マシン C で nginx の 0.81 倍）

---

### 🔴 Apache

**長所**
- ✅ 歴史ある巨大なエコシステム（モジュール、`.htaccess`、PHP）
- ✅ 数十年にわたり実績のある堅牢さ
- ✅ 大きなファイルで優秀（マシン C で nginx を上回る）
- ✅ 再起動なしの `.htaccess` 対応
- ✅ 圧縮、HTTP/2、ACME に対応
- ✅ 豊富なドキュメント

**短所**
- ❌ 小さなファイルが遅い（nginx の 0.35–0.42 倍）
- ❌ prefork モードではメモリ消費が大きい（4–9 MB、負荷で急増）
- ❌ プロセスモデルがイベント駆動より非効率
- ❌ 冗長な設定
- ❌ リバースプロキシで 5 位（nginx の 0.50–0.59 倍）
- ❌ WAF 非内蔵（ModSecurity は別モジュール）
- ❌ 歴史的に攻撃対象領域が広い

---

### 🟠 Caddy

**長所**
- ✅ 自動 HTTPS（ACME 内蔵、設定不要）
- ✅ 非常に短く読みやすい設定（Caddyfile）
- ✅ HTTP/2 と HTTP/3 にネイティブ対応
- ✅ 単一バイナリ、簡単なデプロイ
- ✅ 中サイズの応答では妥当なリバースプロキシ

**短所**
- ❌ 純粋なスループットが遅い（ウェブで 5 位、中継で 7 位）
- ❌ メモリ消費が大きい（46–67 MB）
- ❌ マシン C の大きなファイルで非常に弱い（nginx の 0.11 倍）
- ❌ WAF 非内蔵
- ❌ nginx/Apache より若いエコシステム
- ❌ 非常に高いスループットには不向き

---

### 🟣 Traefik

**長所**
- ✅ Docker/Kubernetes の自動ディスカバリ
- ✅ コンテナ環境に最適
- ✅ 自動 HTTPS（ACME 内蔵）
- ✅ 再起動なしの動的設定
- ✅ 中サイズの応答でのリバースプロキシは良好（nginx の 0.60–0.70 倍）

**短所**
- ❌ ファイルサーバーではない（ウェブのランキングには登場しない）
- ❌ リバースプロキシで 6 位（1 KB で nginx の 0.29–0.35 倍）
- ❌ メモリ消費が非常に大きい（93–131 MB）
- ❌ コンテナ以外の文脈では設定が複雑
- ❌ WAF 非内蔵
- ❌ 単純な静的サイトには過剰

---

## 🎯 どの用途にどのサーバー？

| 用途 | 推奨サーバー | 理由 |
|---|---|---|
| 高トラフィックのサイト | **nginx** または **lighttpd** | 最大スループット、HTTP/2-3 |
| 制約のあるマシン / 組み込み | **lighttpd** | メモリ 1 MB、最速かつ最も省リソース |
| シンプルな自動 HTTPS | **Caddy** | 自動証明書、短い設定 |
| Docker / Kubernetes | **Traefik** | サービスディスカバリ |
| PHP アプリケーション / .htaccess | **Apache** | 歴史あるエコシステム |
| リバースプロキシ | **nginx** または **omega-serv (ネイティブ)** | 最良の性能 |
| ウェブサイト + セキュリティ + インターフェース | **omega-serv (ネイティブ)** | 完全なインフラ：WAF、Web 管理、マルチインスタンス、リバースプロキシ、ログ管理、バックアップ… |

---

omega-serv の比較（2026年11月）に基づくデータ — kraynux。MIT ライセンス。
[oha](https://github.com/hatoo/oha) で測定 · 自己完結型の HTML/CSS グラフ。

> *omega-serv の測定比較のグラフ版です（詳細な比較と同じ数値：三台のマシンでの 2026年11月3日と4日の測定、リバースプロキシは 2026年11月14日、omega-serv 3.0.0 のメモリは 2026年11月19日）。容量に関する判断をする際は、ご自身のハードウェアで測定してください。*
>
> Copyright © 2026 kraynux — kraynux@proton.me — MIT ライセンス（LICENSE ファイルを参照）。
