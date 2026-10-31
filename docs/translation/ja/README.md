<!-- Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE) -->
<div align="center">
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/assets/omega-serv.png" alt="Omega-Serv" width="384">
</div>

# 🔒 OMEGA-SERV

**自己完結型・ポータブル・デフォルトで堅牢化された HTTP Web サーバー**

> [kraynux](https://github.com/kraynux) が [Omega-Server](https://kraynux.snake-mackarel.ts.net) のために開発   

公式ページ：[OMEGA-SERV](https://kraynux.snake-mackarel.ts.net/omega-serv/translation/ja/) &nbsp; リファレンス・使い方・ヘルプ・FAQ：[完全ガイド](https://kraynux.snake-mackarel.ts.net/omega-serv/translation/ja/guide.html)  
プレビュー：[スクリーンショット](https://kraynux.snake-mackarel.ts.net/omega-serv/screenshots/) &nbsp; デモ [デモサーバー](https://craftdark.snake-mackarel.ts.net) &nbsp; [Web サーバーの比較・テスト](comparatif-serveurs-web.md)  

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](../../../LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![Lua](https://img.shields.io/badge/Lua-5.4%2B-2C2D72.svg)](https://www.lua.org/)
[![JavaScript](https://img.shields.io/badge/JavaScript-ES2020%2B-F7DF1E.svg)](https://developer.mozilla.org/docs/Web/JavaScript)
[![HTML](https://img.shields.io/badge/HTML-5-E34F26.svg)](https://developer.mozilla.org/docs/Web/HTML)
[![Platform](https://img.shields.io/badge/Platform-Linux-informational.svg)](https://www.linux.org/)
[![Interface](https://img.shields.io/badge/Interface-CLI%20%2B%20TUI-cyan.svg)](#3-使い方)
[![Textual](https://img.shields.io/badge/Textual-TUI-5A5AFB.svg)](https://textual.textualize.io/)

🌐 ドキュメント・エクスポート・インターフェースは **17 言語** に対応しています — [インターフェースの言語](#インターフェースの言語) を参照してください。  
**言語：**
<img src="https://flagcdn.com/w20/fr.png" alt="France" style="height:14px;"> [Français](../../../README.md) · <img src="https://flagcdn.com/w20/gb.png" alt="English" style="height:14px;"> [English](../en/README.md) · <img src="https://flagcdn.com/w20/es.png" alt="Español" style="height:14px;"> [Español](../es/README.md) · <img src="https://flagcdn.com/w20/br.png" alt="Português (Brasil)" style="height:14px;"> [Português (Brasil)](../pt-BR/README.md) · <img src="https://flagcdn.com/w20/it.png" alt="Italiano" style="height:14px;"> [Italiano](../it/README.md) · <img src="https://flagcdn.com/w20/de.png" alt="Deutsch" style="height:14px;"> [Deutsch](../de/README.md) · <img src="https://flagcdn.com/w20/nl.png" alt="Nederlands" style="height:14px;"> [Nederlands](../nl/README.md) · <img src="https://flagcdn.com/w20/pl.png" alt="Polski" style="height:14px;"> [Polski](../pl/README.md) · <img src="https://flagcdn.com/w20/ru.png" alt="Русский" style="height:14px;"> [Русский](../ru/README.md) · <img src="https://flagcdn.com/w20/cn.png" alt="中文" style="height:14px;"> [中文](../zh-CN/README.md) · <img src="https://flagcdn.com/w20/vn.png" alt="Tiếng Việt" style="height:14px;"> [Tiếng Việt](../vi/README.md) · <img src="https://flagcdn.com/w20/th.png" alt="ไทย" style="height:14px;"> [ไทย](../th/README.md) · <img src="https://flagcdn.com/w20/id.png" alt="Bahasa Indonesia" style="height:14px;"> [Bahasa Indonesia](../id/README.md) · <img src="https://flagcdn.com/w20/jp.png" alt="日本語" style="height:14px;"> [日本語](README.md) · <img src="https://flagcdn.com/w20/kr.png" alt="한국어" style="height:14px;"> [한국어](../ko/README.md) · <img src="https://flagcdn.com/w20/in.png" alt="हिन्दी" style="height:14px;"> [हिन्दी](../hi/README.md) · <img src="https://flagcdn.com/w20/ae.png" alt="العربية" style="height:14px;"> [العربية](../ar/README.md)

---

**OMEGA-SERV** は純粋な Python（サーバーのコアには標準ライブラリのみを使用）で書かれた HTTP/1.1 サーバーです。静的コンテンツの配信と、オプションで PHP-FPM の実行を目的としており、無効化できないプロトコルの堅牢化と、押し付けではなく必要に応じて重ねられるセキュリティモジュール（WAF、TLS、認証）を備えています。`omega-` スイートの 7 番目のツールですが、意図的に **将来の `omega-suite` 統合の対象外** としています（遠隔のターゲットではなく、自身を動かしているローカルマシンに作用するためで、`omega-fire` と同じ系統です）。Clean Architecture で構成され、`bootstrap/` がコンポジションルートの役割を担います。

## 1. ビジョンと範囲

掲げている優先事項は **まず HTTP コアの堅牢性・安全性** です — WAF と TLS はその上に載せるオプションのモジュールであり、前提条件になることはありません。多くのことを中途半端にこなすサーバーよりも、ひとつのこと（ファイルの配信、場合によっては PHP）だけを、回避できない本物のプロトコル堅牢化とともに正しく行うサーバーを目指しています。

### OMEGA-SERV ができること

- 安全なパス解決（トラバーサル、二重エンコード、シンボリックリンク）を備えた静的コンテンツ配信（ファイル、任意のディレクトリ一覧、エイリアス、リダイレクト、リライト、キャッシュ）。大きなファイルはディスクからブロック単位で送信され、メモリに読み込まれることはありません。各ファイルには `ETag` と `Last-Modified` が付き（再読み込み = 空の 304 応答）、部分リクエスト `Range`（ダウンロードの再開、動画）を受け付けます。画像・メディア・フォント・CSS・JS にはデフォルトの `Cache-Control` が付与され、キャッシュ画面で変更できます。事前圧縮されたテキストファイル：`site.css` の隣に `site.css.br` または `site.css.gz` があり（`brotli -k site.css` や `gzip -k site.css` で作成）、ブラウザが受け入れる場合はそれが代わりに送信されます。元のファイルより古い版が送られることはありません。
- 無効化するオプションなしに、デフォルトで HTTP プロトコルを堅牢化します：明示的な許可メソッド、`Host` ヘッダーの検証、`Content-Length`/`Transfer-Encoding` の曖昧さの拒否、回避できないセキュリティヘッダーと基本 CSP。
- オプション：WAF によるフィルタリング（シグネチャ、レート制限、ブロックリスト）、TLS の直接終端（自己署名証明書、ローカル CA による署名、または自動更新付きの Let's Encrypt/Certbot による公開証明書 — §9 参照）、ゾーン単位の HTTP Basic 認証、FastCGI/PHP-FPM による PHP、隔離されたアップロードゾーン。
- 「boost」モード：複数のサーバープロセス（マシンで利用可能な CPU 1 つにつき最大 1 つ、耐性と制限の画面）。セキュリティカウンター（rate limit、再犯）はプロセス間で共有され、常に正確です。
- 自身の設定を監査し（`audit security`）、システムサービス（systemd/OpenRC/runit）として自らをインストールします。
- 最初から最後までスクリプト化できる非対話 CLI と、**まったく同じユースケースを包む対話型インターフェース（Textual）** — §3 参照。インターフェースのロードマップ（`OMEGA-SERV_PLAN-DETAILLE_INTERFACE.md`、§12）は **すべて提供済み** です：機能レジストリ、プロファイル/オプション、詳細設定（エイリアス/リダイレクト/リライト/FastCGI/dirlisting/認証/キャッシュ/WAF/信頼済みプロキシ/送信リバースプロキシ/TLS）、ログ管理（ライブラリ/お気に入り、3 種類のビューア — シンプル/クラシック/統合 lnav —、IP の表示と処理、SSH リモートソース、ローテーション/バックアップ/自動化/復元/削除/エクスポート）、システムサービス、マルチインスタンス（レジストリ、作成）、確認/シミュレーション/監査、設定のバックアップ/復元、初回起動ウィザード、アプリケーション設定（テーマ、描画プロファイル、エクスポート/スクリーンショットのパス）、コンテキストヘルプガイド（具体例付きの画面ごとの解説、FAQ、HTML エクスポート、テストで検証された網羅的なカバー）、保存のたびにリロード/再起動の要否を必ず表示、ファイルを手で編集しない Active Defense の完全な設定。

### OMEGA-SERV がしないこと

- 生の CGI（V1 の範囲から除外 — FastCGI/PHP-FPM のみ対応）。
- TLS 相互認証（mTLS）、OCSP stapling — V1 の範囲外、§15 参照。（Certbot 経由の ACME/Let's Encrypt は利用可能、§9c/9d 参照。）
- プロセス間で共有する HTTP キャッシュ。
- 遠隔ターゲットのスキャン/監査（それには `omega-check`/`omega-scan`/`omega-deep` を使います — Omega-serv は自分自身を監査し、第三者を監査することはありません）。

### OMEGA-SERV と市場の Web サーバーの比較

[計測と比較](comparatif-serveurs-web.md) を参照してください  
計測による比較： [Nginx](https://nginx.org/) · [Lighttpd](https://www.lighttpd.net/) · [Caddy](https://caddyserver.com/) · [Apache](https://www.apache.org) · [Traefik](https://traefik.io/) · [Omega-Serv](https://kraynux.snake-mackarel.ts.net/omega-serv/translation/ja/)

### 利用上の注意

Omega-serv は **root として起動することを拒否します**。提供されるどのプロファイルでも、`hardened` を含め、セキュリティモジュール（WAF、TLS、認証）はデフォルトで有効になっていません — 有効化は常に明示的な操作です（`config enable-tls`、`option enable waf`...）。`hardened` プロファイル自体も、実際にインターネットへ公開する場合はリバースプロキシの代わりになるのではなく、リバースプロキシの利用を推奨しています。

## 2. インストール

### 前提条件

- Python 3.10+
- TLS 証明書に関わるすべてに `openssl`（Python ライブラリではなく実行ファイル） — それ以外の機能はなくても動作します。

### ダウンロード

最新版のアーカイブと各バージョンの SHA-256 フィンガープリント：[omega-serv-2.0.1.tar.gz](https://kraynux.snake-mackarel.ts.net/omega-serv/download/omega-serv-2.0.1.tar.gz) · [sha.txt](https://kraynux.snake-mackarel.ts.net/omega-serv/download/sha.txt)

```bash
wget https://kraynux.snake-mackarel.ts.net/omega-serv/download/omega-serv-2.0.1.tar.gz
wget https://kraynux.snake-mackarel.ts.net/omega-serv/download/sha.txt
sha256sum -c --ignore-missing sha.txt
```

### インストール

> ⚠️ **既存のインストールを更新しますか？** 以下のコマンドは、`omega-serv/` がすでに存在すると **展開を黙ってスキップします**（更新ではなく中断された初回インストールとみなすため）— その場合、**変更されていない古いコード** の上に依存関係を再インストールすることになり、エラーメッセージは一切出ません。代わりに下の [アップデート](#アップデート) を使ってください。

```bash
[ -d omega-serv ] && echo "ℹ️ ここには展開済みです。この手順をスキップします。" || tar -xzf omega-serv-2.0.1.tar.gz
cd omega-serv/
chmod +x install.sh
./install.sh
```

`install.sh`：

1. 仮想環境 `.venv` がなければ作成します。
2. パッケージをインストールします（`pip install -e .`）— **外部依存なし**（§6 参照）。
3. `omega-serv.sh` と `install.sh` を実行可能にします。
4. `~/.bashrc` と `~/.zshrc` にエイリアス `serv` を追加します（既にあれば重複しません）。

### アップデート

`omega-serv/` がすでに存在する場合（以前のインストール）、**このフォルダーの中から `tar` を実行しないでください**：入れ子の `omega-serv/omega-serv/` を作ろうとして失敗します。omega-fire と異なり、`install.sh` はフォルダーのパーミッションに一切触れません（`sudo` を求める手順はありません）— したがってここではフォルダーが `root` の所有になる危険はなく、既存のインストールの上に直接展開しても安全です。

```bash
# omega-serv/ の親フォルダーから実行（中からは絶対に実行しない）
tar -xzf omega-serv-2.0.1.tar.gz
cd omega-serv/
./install.sh
```

アーカイブは稼働中の状態をすべて意図的に除外しています（`var/db/`、`var/log/`、`var/backups/`、`secure/secrets/`、`secure/certificates/*.key`、`config/omega-serve.json`、**`webroot/` — 実際に配信しているサイト**...）— 上書き展開しても、データ・証明書・設定・配信中のコンテンツには一切触れず、アプリケーションのコードだけが置き換わります。`install.sh` は既存の `.venv` を再利用し、その上に依存関係を再インストールするだけです。

2026-10-18 以降、`var/` と `secure/auth/` は空であってもアーカイブにまったく含まれません：そのため上書き展開しても、それらのパーミッション（systemd サービスのアカウントとの共有）がリセットされることはありません — 更新後に「サービス → パーミッションを再適用」する必要はもうありません。`install.sh` はこれらのフォルダーがなければ作成し、既存のものには決して触れません。

> ⚠️ **サービスがすでに稼働している場合、上の手順だけでは不十分です。** ディスク上のコードは置き換わりますが、実行中のプロセスはメモリに読み込まれた古いコードのまま動き続けます — その後は必ず **完全な再起動** が必要です：
> ```bash
> sudo systemctl restart <サービス名>
> ```
> **単なるリロードでは決してだめです**（`systemctl reload`、または SERVICE 画面 → *リロード*）：リロードは一部の設定オプション（WAF ルール、認証ゾーン...）を読み直すだけで、**Python のコード自体は決して読み直しません**。`systemctl status <サービス名>` の起動日時が更新より古ければ、まだ古いコードで動いていることが確認できます。常に同じフォルダーを上書きして更新している場合（上の標準的なケース）、足りない手順はこの再起動だけで、サービスの再インストールは不要です。

> ⚠️ **その後サービスが再起動を繰り返す場合**（`systemctl status` が active/inactive を行き来し、`journalctl -u <サービス名>` に `var/` 配下のファイル書き込み時の `PermissionError` が出る）：`tar` の展開はアーカイブに記録されたとおりにフォルダーのパーミッションを復元するため、初回インストール時に専用システムアカウント向けに設定したパーミッション共有が消えることがあります — `install.sh` 自体はそこに触れないにもかかわらずです。ユニットを再インストールする必要はありません：SERVICE 画面 → **パーミッションを修復**（systemd ユニットには触れずに、`var/` と `secure/auth/` に共有を再適用します）。

### 依存関係

サーバーのコア（HTTP/1.1 パーサー、FastCGI クライアント、`hashlib.scrypt` によるパスワードハッシュ）は純粋な Python/stdlib のままで、TLS 証明書に関わるものはすべて Python の暗号ライブラリではなくサブプロセスの `openssl` 実行ファイルを経由します — **この部分に外部依存はありません**。依存を追加するのは対話型インターフェース（§3）だけです：`omega-lib`（テーマ、ターミナル検出 — スイート共通のライブラリで PyPI には公開されておらず、配布アーカイブに同梱）、`textual` と `pyte`（インターフェース内で統合 `lnav` を描画するためのターミナルエミュレーション）、`jinja2`（テーマ付き HTML エクスポート）、`psutil`（状態とリソース画面 — CPU/RAM/ディスク/ネットワーク）。任意の開発/テスト用依存（`pip install -e ".[test]"`）：`hypothesis`（HTTP パーサーとパスリゾルバーのプロパティテスト、本番では使いません）。品質ツール（`pip install -e ".[dev]"`）：`pytest`、`ruff`、`mypy`、`import-linter`。追加の任意エクストラ（`pip install -e ".[magnet]"`）：`lupa`（組み込み Lua バインディング、ビルド済み wheel で、システムの `lua` インタープリターは不要）。補助 WAF スクリプト「magnet」（§7）専用で、デフォルトではインストールされません。未導入の場合は正確なインストールコマンドとともに通知され（機能 `waf-magnet`、**機能** 画面）、サーバーの他の部分は妨げられません。

### 推奨される任意ツール

これらのツールがない場合、インターフェースは機能を縮退させて動作します：

- `openssl` — TLS 証明書に関わるすべて（自己署名、ローカル CA、インポート）に必要です。ない場合 `certs *` コマンドは失敗しますが、サーバーの他の部分は通常どおり動作します（§9 参照）。
- `certbot` — **Let's Encrypt** ウィザードとその自動更新（§9c/9d）にのみ必要です。自己署名/ローカル CA の TLS には不要です。
- `lnav` — **ログ管理** 画面（§3）に統合された高度なログ解析。実行ファイルが見つからない場合は明確なエラーメッセージを出し、クラッシュしません。画面の他の部分（表示/追跡/ローテーション/統計）はなくても通常どおり動作します。
- `scp`（`openssh`/`openssh-clients` パッケージ、ほぼ常に導入済み）— **リモートソース（SSH）**（§13a）にのみ必要です。ない場合は取得が明確なメッセージとともに失敗し、ライブラリの他の部分は通常どおり動作します。
- `python-psutil`（PyPI の `psutil` に相当するシステムパッケージ）— どの場合も `pip install -e .` で自動的にインストールされます（パッケージの必須依存で、**状態とリソース** 画面が常に必要とします）が、システムのパッケージマネージャーで事前に入れておくと `pip` が wheel をローカルでビルドせずに済みます。

```bash
# Arch Linux と派生ディストリビューション
sudo pacman -S openssl certbot lnav python-psutil openssh

# Debian/Ubuntu と派生ディストリビューション
sudo apt install openssl certbot lnav python3-psutil openssh-client

# Fedora
sudo dnf install openssl certbot lnav python3-psutil openssh-clients
```

## 3. 使い方

機能的に完全に同等な 2 つのインターフェースがあり、両者の間でロジックが重複することはありません：非対話 CLI（スクリプト化可能、以下で使用）と Textual の対話型インターフェース（メニュー、フォーム、表）— 一方の操作はすべて CLI 側にも存在し、インターフェースは同じユースケースを包んでいるだけです。

### 対話モード（TUI）

日常の利用に推奨 — 引数なしで起動します：

```bash
./omega-serv.sh
```
エイリアスを作成済みなら、ターミナルで `serv` と入力するだけです：
```bash
serv
```

### インターフェースの言語

17 言語：フランス語、英語、スペイン語、ポルトガル語（ブラジル）、イタリア語、ドイツ語、オランダ語、ポーランド語、ロシア語、中国語、ベトナム語、タイ語、インドネシア語、日本語、韓国語、ヒンディー語、アラビア語。設定（`o` キー、「Langue / Language」、このラベルは翻訳されません）で選ぶか、一時的に `OMEGA_SERV_LANG=en serv` とします。Linux のテキストコンソール（TTY）では、コンソールフォントに文字が存在しない言語（ベトナム語、中国語、タイ語、日本語、韓国語、ヒンディー語、アラビア語）はそのセッションでは英語で表示されます。ヒンディー語では、連結文字を自前で合成するターミナル（Kitty、Ghostty、Konsole）で枠や列がずれ、その程度はフォントによって異なります：起動時に警告が表示されます。Terminator、GNOME Terminal、Xfce Terminal、Alacritty ではヒンディー語が揃って表示されます。別の設定が 2 つあります：**訪問者向けページの言語**（エラーページ、フォルダー一覧 — エラーページ画面、デフォルトはフランス語）と **エクスポートの言語**（HTML とインシデントレポート — 設定、デフォルトは「インターフェースと同じ」）。サーバーのログ（`journalctl`）はフランス語のままです。

### 全体の流れ

起動画面（スプラッシュ、キーまたはクリックで閉じる）→ メインメニュー（初回起動ウィザード / 機能レジストリ / プロファイル / 詳細設定 / アクティブセキュリティ / ログ管理 / サービス / マルチインスタンス / 状態とリソース / 監査 / バックアップ）→ セクションを選び、次に操作を選択。各フォームは続行前に必須項目を検証 → 機微な操作や破壊的な操作（再起動、削除、復元...）の前には明示的な確認 → 配信中の設定を変更する保存のたびに、次に起こることを必ず表示（自動のホットリロード、または完全な再起動の確認）。ターミナルへの適応（色、サイズ、描画プロファイルの構造的な縮退）は自動で、手動フラグは不要です — §4 参照。

#### キーボードショートカット（対話型インターフェース）

| キー | 操作 |
|---|---|
| `↑` / `↓` | 画面内の要素を移動 |
| `Tab` / `Shift+Tab` | フォームの項目間を移動 |
| `Esc` | 前の画面に戻る（ホームでは終了確認） |
| `t` | 次のテーマ（確認なしで即座に適用） |
| `r` | ターミナル検出を更新 |
| `F1` | 現在の画面のヘルプ（コンテキスト解説 — 下の「ヘルプガイド」参照） |
| `a` | 完全なヘルプガイド（閲覧可能なメニュー + FAQ） |
| `o` | アプリケーション設定（テーマ、描画プロファイル、エクスポート/スクリーンショットのパス — 下記参照） |
| `q` | 終了（確認あり） |
| `Ctrl+P` | コマンドパレット（テーマ、スクリーンショット、オプション...） |

> **例外 — リストエディター（WAF → Custom）**：ショートカットはなく、すべてマウスで操作します。キーボードは入力（文字、Enter、矢印、Home/End、Page Up/Down、Backspace、Delete）にのみ使います。`Esc`、`F1`、`Ctrl+P` はそこでは無効です（**ヘルプ** ボタンを使用）。有効なのは `Ctrl+Q` だけで、未保存の変更があれば確認されます。

#### ヘルプガイド（`F1`/`a` キー）

単なる静的テキストではない、組み込みのヘルプシステムです：解説のある各画面（定義/具体例付きの入力項目/実行される操作/反応 — リロード、再起動、またはなし）には、その画面から `F1` で直接アクセスできます。`a` キーは完全なメニュー（アプリケーションの実際のナビゲーションと同一の階層）を開き、FAQ（実際の利用で遭遇した落とし穴。例：Active Defense の攻撃クラス、共有サービスのパーミッション）と、ガイド全体の自己完結型 HTML エクスポート（現在のテーマを保持）にアクセスできます。個別の解説がまだない画面には汎用のリファレンス画面で代替します — 現在のカバーは網羅的で、テストで検証されています。

#### メインメニュー（対話型インターフェース）

- **初回起動ウィザード** — 8 ステップのガイド付き手順（ようこそ → 読み取り専用の機能確認 → プロファイル選択 → bind/ポート → 任意の TLS → 確認 → 要約 + 書き込み → サービスのインストール提案）。CLI を知らなくても、完全な設定を作成してサーバーを起動できます。
- **機能レジストリ** — 読み取り専用のシステム調査（init システム、設定したポートが使用中かどうか、`openssl`/`logrotate`/`tailscale`/`lnav` の有無、ディスク容量、ファイルディスクリプター上限...）、JSON/HTML エクスポート。
- **プロファイル** — CLI の `profile`（§5）と同じユースケース。書き込み前に必ず差分を表示します。
- **サーバーの詳細設定** — エイリアス/リダイレクト/リライト/dirlisting/信頼済みプロキシ/送信リバースプロキシ/FastCGI/キャッシュ/認証/アクセス制御/エラーページの完全な CRUD と、サブメニュー **TLS**（状態、自己署名の生成、ローカル CA ウィザード、Let's Encrypt/Certbot ウィザード、自動更新、失効、有効化/無効化 — §9 参照）。2 つ目の枠 **オプションと確認** には **オプション**（CLI の `option`、§7）と **設定を確認**（CLI の `config check`、§10）へのショートカットがまとめられています — 設定を調整してから確認するという同じ流れで、この 2 画面はもうメインメニューから直接は開けません。WAF はもうここにはありません（下の「アクティブセキュリティ」参照）：WAF が主に表示するのは常に変化する運用状態であり、単純な静的設定フォームではないためです。保存のたびに次に起こることを必ず明示します：サービスが稼働中なら自動かつ静かなホットリロード（dirlisting、アクセス、エイリアス/リダイレクト/リライト、キャッシュ、エラーページ、信頼済みプロキシ、リバースプロキシ/FastCGI ゾーン、認証ユーザー/ゾーン）、変更が待ち受けソケット・TLS・Active Defense に関わる場合は完全な再起動の明示的な確認 — サーバーを再起動すべきか推測させる画面はもうありません。
- **アクティブセキュリティ** — 2 つのブロックを並べた単一の画面：**Active Defense**（状態、スコア/レベル付きの追跡中の脅威、タイムライン/IoC エクスポート/レポート付きのインシデント、Deception の割り当て、ドライランでの判定シミュレーション、**設定** — `config/omega-serve.json` を手で編集することなく完全に設定、§11 参照）と **WAF**（状態、モジュール — モード/ルールパック/ブロックリスト、リクエストのテスト、Custom — カスタムルールの作成と、マウスで編集できるパス/キーワードリストの読み込み（§11b 参照）、Magnet — 有効化前に互換性を確認したうえで外部の `mod_magnet` スクリプトをインポート）— §11 参照。
- **ログ管理** — 2 列のメニュー。**ライブラリ** 列：処理対象のすべてのログを参照する中心（手動で追加、ワンクリックでインスタンス固有のログを追加 — access/error/ネイティブ WAF、+ 有効なら magnet スクリプト §7 —、または SSH で取得した **リモートソース**、下記参照）。**お気に入り**（ログ + ビューアの組み合わせを名前付きで保存し、直接起動）。**ログを表示** では選択したログの数に応じて 3 種類のビューアから選べます — シンプル（ライブ tail + あらゆる形式での IP/エラー/HTTP コードの汎用統計）、クラシック（閲覧 + 追跡）、統合 `lnav`（インターフェース内での実ターミナル描画、magnet ログを自動で含め、手動パスを **ピン留め** してセッション間で保持）。**IP の表示と処理**（選んだ 1 つ以上のログの上位 IP、期間 24 時間/7 日/30 日/すべて、IP の除去）。**メンテナンス** 列（変更なし）：手動またはサイズしきい値による自動のローテーション/アーカイブ、即時バックアップの作成、スケジュール自動化の設定/管理（宣言的 — 下の注記参照）、アーカイブの復元/削除、一覧のエクスポート。
- **サービス** — CLI の `service`（§12）と同じ操作。操作ごとに一時的に `sudo` で昇格し、アプリケーション全体を root で動かすことはありません。
- **マルチインスタンス** — マシン上の既知のインストールのグローバルレジストリ（`~/.config/omega-serv/instances.json`、どのプロジェクトディレクトリにも属さない）と、それぞれの systemd 状態。新しいインスタンスの作成（ツリーのコピー、専用の仮想環境と依存関係、別ポートの新しい設定、入れ子とポート競合のチェック）をインターフェースから直接行えます。インストールが 1 つだけのときボタンは実質的に目立たず（2 つ以上になるとラベル「マルチインスタンス」が「Instances (N)」に変わります）、別のインスタンスへの完全な切り替え（`os.execv`、明示的な確認、再起動時に切り替えを告げる専用スプラッシュ）、インスタンスの完全なアンインストール（ユニットの削除、他のインスタンスがもう使っていなければ専用システムアカウントの削除、そして任意でディレクトリの削除 — デフォルトでは決して削除しません）が可能です。
- **状態とリソース** — 2 秒ごとに更新される一目でわかる概要：サーバーの状態（プロセス/PID、システムサービスの状態、プロファイル/有効なオプション/TLS/ポート）、アクセスログのライブストリーム（スループット、ステータスコード別の内訳、ユニーク IP、エラー率）、システムリソース（CPU/RAM/ディスク/スワップ/負荷/ネットワーク、`psutil` 経由）。**模擬リクエスト** へのショートカットもここにあります（対応する CLI コマンドと同じユースケース、§10）。
- **セキュリティ監査** — 対応する CLI コマンドと同じユースケース（§10）。
- **設定のバックアップ** — 設定ファイルの tar.gz アーカイブと、明示的に選んだ場合は WAF ルール/認証ゾーン/証明書（実際の秘密情報を含める場合は確認必須）/Active Defense のデータベース、復元、一覧、削除。

> スケジュールされたローテーション自動化についての注記：これらは保存されますが（頻度 + 対象ログ）、**自動で実行するものは何もありません** — インターフェース側でもバックグラウンドタスクとしてもです。これは同じ宣言的な振る舞いを持つ `omega-fire` の対応画面と揃えるための意図的な選択です。実際の定期実行（systemd タイマー、バックグラウンドタスク）は、必要性が確認されれば別途構築します。

#### アプリケーション設定（`o` キーまたはコマンドパレット）

インターフェースの設定のみで、`config/omega-serve.json`（サーバー設定）と混同されることはありません：現在のテーマ、描画プロファイル（`complete`/`standard`/`reduced`/`mono`、再起動が必要）、エクスポートのパス（デフォルト `var/exports/`）、スクリーンショットのパス（デフォルト `var/screenshots/`）、いずれかのフォルダーの削除（確認必須）。

```bash
# サーバーを起動（フォアグラウンド、SIGTERM = 猶予期間付きの正常停止、SIGHUP = WAF/Auth のホットリロード）
./omega-serv.sh serve

# 設定
./omega-serv.sh config init                # config/omega-serve.json を生成（デフォルトは安全な値）
./omega-serv.sh config check                # 起動せずに確認（起動時と同じブロッキングゲート）
./omega-serv.sh config show
./omega-serv.sh config enable-tls --cert ... --key ... --mode direct
./omega-serv.sh config disable-tls

# プロファイル（minimal / standard / hardened / development）
./omega-serv.sh profile list
./omega-serv.sh profile show hardened
./omega-serv.sh profile apply hardened --dry-run   # 適用前に必ず差分を確認

# オプション（aliases, redirects, rewrites, dirlisting, cache, waf, upload, fastcgi, reverse_proxy...）
./omega-serv.sh option list
./omega-serv.sh option enable waf
./omega-serv.sh option disable waf

# サーバーを起動せずにリクエストをシミュレート（有効化前のルール検証に便利）
./omega-serv.sh simulate-request GET /index.html

# WAF（オプションが無効でも暗黙の --force で動作）
./omega-serv.sh waf test --method GET --path /admin --remote-ip 203.0.113.1
./omega-serv.sh blocklist list
./omega-serv.sh blocklist add --network 203.0.113.0/24 --reason "scan detecte" --duration-seconds 3600
./omega-serv.sh blocklist remove --network 203.0.113.0/24

# Active Defense（deception + 戦闘モード、オプション "active_defense" - §11 参照）
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

# TLS 証明書 - 自己署名（9a）
./omega-serv.sh certs generate-self-signed --cn localhost --san-dns localhost --san-ip 127.0.0.1
./omega-serv.sh certs show
./omega-serv.sh certs check-expiry --warn-days 30

# TLS 証明書 - ローカル CA（9b）
./omega-serv.sh certs generate-ca --cn "Mon CA locale" --days 3650
./omega-serv.sh certs generate-csr --cn serveur.local --san-dns serveur.local --key-out server.key --csr-out server.csr
./omega-serv.sh certs sign-csr --csr server.csr --ca-key secure/certificates/ca/root-ca.key --ca-cert secure/certificates/ca/root-ca.pem --out server.pem --fullchain-out fullchain.pem
./omega-serv.sh certs revoke --cert server.pem --ca-key secure/certificates/ca/root-ca.key --ca-cert secure/certificates/ca/root-ca.pem

# TLS 証明書 - インポート（9c、例：Certbot のフックから）
./omega-serv.sh certs import --key privkey.pem --cert fullchain.pem

# HTTP Basic 認証
./omega-serv.sh auth add-user --username alice
./omega-serv.sh auth create-zone --url-prefix /admin/ --allowed-users alice
./omega-serv.sh auth list

# セキュリティ監査（決してブロックせず、情報提供のみ）
./omega-serv.sh audit security --format text --min-severity medium

# 設定のバックアップ（設定は常に含まれる。実際の秘密情報は
# デフォルトでは暗号化されない。含めるには --confirm-secrets が必須）
./omega-serv.sh config backup --description "avant migration"
./omega-serv.sh config backup --include-auth --include-certificates --confirm-secrets
./omega-serv.sh config backup --include-active-defense --description "menaces/incidents"
./omega-serv.sh config list-backups
./omega-serv.sh config restore --snapshot-id snapshot_20260908_170003_762484

# システムサービス（systemd/OpenRC/runit、自動検出）
./omega-serv.sh service install --user omega-serv --group omega-serv
./omega-serv.sh service start
./omega-serv.sh service status
```

### 主な終了コード

| コマンド | コード | 意味 |
|---|---:|---|
| `audit security` | `0` | 重大な問題なし（`CRITICAL`/`HIGH` なし） |
| `audit security` | `1` | `CRITICAL` の指摘が少なくとも 1 件 |
| `audit security` | `2` | `CRITICAL` はなく `HIGH` が少なくとも 1 件 |
| `audit security` | `3` | 実行エラー（設定が見つからない...） |
| `certs check-expiry` | `1` | 証明書の期限切れ |
| その他のコマンド | `0`/`1` | 成功 / 検証失敗 |

## 4. ターミナルの互換性

対話型インターフェース（[Rich](https://rich.readthedocs.io/) の上に構築された [Textual](https://textual.textualize.io/)）はターミナルの機能（エミュレーター、サイズ）を自動で検出し、それに応じて構造的なスタイルシート（`complete`/`standard`/`reduced`/`mono`）を調整します。手動フラグは不要です。CLI モードは常にプレーンテキストで、ターミナルに依存しません。`omega-` スイート全体で共有するポリシー（`omega-lib`、`terminal/policies.py`）で、`omega-check`/`omega-fire` と同一です。

### 検出したエミュレーターによるプロファイル

| エミュレーター | 初期プロファイル |
|---|---|
| Ghostty、Alacritty、WezTerm、Kitty | `complete` |
| Konsole、GNOME Terminal、Terminator、Xfce4 Terminal | `standard` |
| xterm、urxvt、最近の SSH | `reduced` |
| Linux TTY、古い SSH | `mono` |
| 不明なエミュレーター | `reduced`（デフォルトの代替） |

### ターミナルのサイズによるプロファイル

| 最小サイズ（列 × 行） | プロファイルの上限 |
|---|---|
| 120 × 32 | `complete` |
| 100 × 28 | `standard` |
| 80 × 24 | `reduced` |
| それ未満 | `mono` |

最終的に採用されるプロファイルは **2 つ（エミュレーターとサイズ）のうちより制限的なほう** です — 全画面の Ghostty を 70 列に縮めると、エミュレーター的には `complete` が許されていても `mono` に下がります。`r` キーでその場で更新でき、アプリケーション設定（`o` キー、§3）から手動で上書きすることもできます。

## 5. プロファイル

| プロファイル | 想定用途 |
|---|---|
| `minimal` | デモ/シンプルなローカル：静的のみ、オプションはすべて無効 |
| `standard` | 静的サイトまたは小規模な本番：一般的なヘッダー、基本 CSP、dirlisting/CGI/FastCGI は無効 |
| `hardened` | 最小権限での公開：デフォルトはローカル bind（インターネットにはリバースプロキシを推奨）、メソッドは GET/HEAD に限定、厳格な CSP、slowloris 対策 — ここでも WAF が自動で有効になることは **決してありません** |
| `development` | ローカル開発専用で、インターネット向けとして提示されることは決してない：ループバック bind 必須、report-only の CSP、詳細なエラーページ |

設定のマージ順：組み込みの安全な値 → 選択したプロファイル → 現在有効なオプションの保持（プロファイルを変えても残る）→ ユーザーの明示的なオーバーレイ。書き込み前には必ず完全な差分が表示されます（`profile apply`）。

## 6. アーキテクチャ

Clean Architecture（`core / domain / ports / application / infrastructure / interfaces / bootstrap`）— `bootstrap/` がコンポジションルートです（スイートの他のツールの `app/` に相当）。このプロジェクトで受け入れている特徴で、想定ではなく `import-linter` で検証しています：`application/server/start_server.py`（および `validate_config.py`、`run_audit.py`）は **実際の設定に依存する組み立てファクトリー**（どのサービスマネージャーか、WAF を有効にするか...）の役割を担い、具体的な `infrastructure/` アダプターを直接インスタンス化します — `application/` が `ports/` だけを使う CHECK/TRACK のより厳格なパターンとは異なります。実際に強制している唯一の普遍的ルール：`domain/`/`core/` は外側のレイヤーに決して依存しません。

```text
src/omega_serv/
├── core/            横断的な語彙（platform_info、定数）
├── domain/           純粋なビジネスロジック（HTTP、設定、WAF/TLS/auth/audit のセキュリティ、ルーティング）
├── ports/            アプリケーションが期待する契約（Protocol）
├── application/      ユースケース - 一部の関数（build_server...）は具体的なアダプターも組み立てる（上記参照）
├── infrastructure/    実装（asyncio、subprocess 経由の openssl、systemd/OpenRC/runit、ファイル）
├── interfaces/cli/    非対話の argparse CLI
├── interfaces/tui/    Textual の対話型インターフェース（同じユースケース、ロジックの重複なし）
└── bootstrap/         DependencyContainer、プロジェクトルートの解決
```

`import-linter` が検証するルール（8 つの契約）：`domain`/`core` は外側のレイヤーに決して依存しない。`interfaces.tui` は `infrastructure` に決して直接依存しない。`textual` は `interfaces.tui` に限定。`subprocess` は `infrastructure/process/subprocess_runner.py`（と対話 PTY ストリームの `infrastructure/lnav/`）に限定。`ssl` は `infrastructure/tls/ssl_context_builder.py` に限定。`jinja2` は `infrastructure/exporters/html_exporter.py` に限定。`sqlite3` は `infrastructure/persistence/sqlite_active_defense_connection.py` に限定（プロジェクト唯一のリレーショナルストレージで、Active Defense 専用 — §11 参照）。`lupa` は `infrastructure/waf/lua_waf_adapter.py` に限定（補助 WAF スクリプト「magnet」、§7）。

## 7. オプションモジュール

提供されるすべてのプロファイルでデフォルトは無効 — 有効化は常に明示的です（`option enable <名前>` または `config enable-tls`）：

| モジュール | 役割 |
|---|---|
| `waf` | シグネチャ（機微なパス、スキャナーの UA/Referer、ボディ内の SQLi/XSS/CMDi）、テキストファイルとして編集できるリスト（キーワード、または `!` 例外付きの機微なパス。リストごとの観察モードと再犯 — 2 つのリファレンスを同梱、明示的に読み込み、§11b 参照）、レート制限（トークンバケット、フォルダー別および IP/ネットワーク別のルール、§11c 参照）、ブロックリスト（CIDR + 有効期限）、レピュテーション/エスカレーション、既存の Lighttpd 用 WAF スクリプト `mod_magnet` を「magnet」型の任意の補強としてインポート（書き直し不要、エクストラ `pip install -e ".[magnet]"` — 加算的で、ネイティブのブロックを解除することは決してできない。インポート時に互換性を確認、専用の TUI 画面）— `log-only` モードは構造的にブロックできない |
| TLS | 直接終端（自己署名、ローカル CA、または自動更新付きの Let's Encrypt/Certbot による公開証明書 — §9 参照）、V1 では mTLS/OCSP なし |
| 認証 | ゾーン単位の HTTP Basic（`url_prefix`）、タイミング攻撃対策付きの `hashlib.scrypt`（未知のユーザーでも一定時間） |
| FastCGI/PHP-FPM | `(url_prefix, script_root)` は 1 組のみ。`script_root` は設計上 `webroot/` の外に限定（静的ハンドラーが PHP のソースを漏らすことは決してない） |
| 送信リバースプロキシ | Omega-serv 自身が 1 つ以上のバックエンドへのプロキシとして動作（`server.tls.mode = "behind_proxy"` とは逆方向）— 負荷分散（ラウンドロビン、重み付き、least-connections、ip-hash、least-response-time、実負荷）、セッションアフィニティとヘッダーによるルーティング規則、パッシブ/アクティブなヘルスチェック、応答キャッシュ（`Vary` による複数バリアント）、バックプレッシャー、ループ防止、ホット管理 API — 詳細は §7a 参照 |
| アップロード | 隔離されたゾーン、ゾーンごとのクォータ、サーバー側で生成するファイル名 — V1 ではストリーミングなし（`server.max_request_size` で上限） |
| `active_defense` | すでに計算済みの WAF シグナル（決して 2 つ目のスコアではない）に基づく Deception + 戦闘モード：静的なおとり、対象を絞った減速/詳細ログ/レート制限、インシデント + IoC エクスポート — §11 参照 |

### 7a. 送信リバースプロキシ — 詳細

OMEGA-SERV 自身が 1 つ以上の HTTP/HTTPS バックエンドへのリバースプロキシとして動作できます — `server.tls.mode = "behind_proxy"`（OMEGA-SERV がプロキシの **背後** にある、逆の仕組み）とは決して混同しないでください。ゾーンは完全な CRUD で設定でき（TUI：*詳細設定 → Reverse Proxy*）、ゾーンごとに 1 つ以上の upstream を持てます。

- **負荷分散** — `round_robin`（デフォルト）、`weighted_round_robin`/`weighted_least_connections`/`ip_hash`（重み付き）、`least_connections`、`least_response_time`、`real_load`（実負荷）。ネイティブの `real_load` モード（プローブ `/.omega-serv-load/`、「状態とリソース」画面と同じ `psutil` の計測値を再利用し、2 回目の呼び出しはしない）または宣言的モード（サードパーティの HTTP プローブ、最小形式 `{"load_percent": ...}` または数値のみ）— upstream 単位の粒度で、同じゾーンで両方を混在できます。
- **セッションアフィニティと条件付きルーティング** — 不透明な sticky クッキー（実際の host:port はクライアントに決して見せない）とヘッダーによる規則（一致またはプレフィックス）。どちらも対象 upstream の適格性でフィルターされます（対象の upstream が利用できなければ、現在の戦略へきれいにフォールバック）。
- **ヘルス** — パッシブ（連続した失敗/成功、フラッピングを抑えるため down/up の切り替えしきい値は別々）**と** アクティブ（実トラフィックに依存しない定期プローブ、upstream ごとに任意、実負荷と同じバックグラウンドタスクの仕組みを再利用）。状態 `DOWN`（常に自動）、`DRAINING`/`MAINTENANCE`（常に手動、明確に一時的で永続化されない）— 手動で設定した upstream は新しい選択から外れますが、確立済みの接続を切ることは決してありません。別の upstream への自動リトライは、冪等なメソッド（GET/HEAD/OPTIONS）かつ接続エラーの場合に限ります。
- **バックプレッシャー** — upstream ごとに設定できるアクティブ接続の上限。飽和した upstream は 503 できれいに拒否し、障害の upstream（502、それでもリトライされる）とは区別されます。
- **応答キャッシュ** — GET/HEAD のみ、エラー応答は決してキャッシュせず、ゾーンで明示的にオプトインしない限り `Set-Cookie` もキャッシュしません。upstream の `Cache-Control`/`Vary` を尊重します（無効化できますが危険なオプションで、TLS 検証と同じ考え方）。同じリソースの複数のバリアント（`Vary`）がディスク上で実際に共存し、単に「後から来たものが勝つ」ことはありません。スタンピード防止ロック（同時リクエストのうち 1 つだけが実際にキャッシュを再構築）。すべての応答に診断ヘッダー `X-Omega-Cache: HIT`/`MISS`/`BYPASS`。専用の TUI 画面（*リバースプロキシのキャッシュ*）で監視/削除できます。
- **ループ防止** — hop-by-hop ヘッダーを除去し、`X-Forwarded-*` は常に上書き（クライアントのものと決して統合しない）、中継のたびにカウンター `X-Omega-Proxy-Hops` を増やす（5 ホップを超えるときれいに拒否 — ローカルの設定検証だけでは決して見えない、2 つのインスタンス間の間接ループを検出）。
- **WebSocket** — ゾーンごとにアップグレードを許可でき、確立後はパイプの寿命の間 1 つの upstream に固定され、アプリケーションレベルのタイムアウトはありません。
- **ホット管理** — 小さなローカル HTTP API（`/.omega-serv-admin/`、ネイティブの負荷プローブと同様に `trusted_proxy` で保護）により、TUI はバックエンドの DRAINING/MAINTENANCE 状態を読み取り/強制し、**実際に稼働中のサーバー** のキャッシュのヒット/ミス率を読み取れます（専用画面 *バックエンドのライブ状態*）— TUI とサーバーは共有メモリを持たない別々の 2 プロセスなので、このローカル HTTP チャネルが両者をつなぐ唯一の橋です。

## 8. HTTP の堅牢化（無効化不可）

- ヘッダー/リクエスト行は読み込み **中** に上限を適用（後からではない）、廃止されたヘッダーの折り返しは拒否、`Transfer-Encoding` は常に拒否（推測しない）。
- 重複した `Content-Length` は拒否。`Expect: 100-continue` はきれいに拒否（417）。
- 明示的なメソッドのホワイトリスト（それ以外は 405 + `Allow`）、`Host` ヘッダーを検証（欠落/空/同一でも重複/制御文字 → 400）。
- セキュリティヘッダーと基本 CSP（`enforce`/`report-only`）をエラーを含む **すべて** の応答に適用 — オプションで回避できません。`Cross-Origin-Opener-Policy`/`Cross-Origin-Resource-Policy` は常に `same-origin` で、サイトを壊す実際のリスクはありません。`Cross-Origin-Embedder-Policy` は常に明示的に送信し（欠落させない — 外部スキャナーが「考慮されていない」と「意図的に許容」を区別できる）、`hardened` を含む **すべて** のプロファイルでデフォルトは `unsafe-none`：前の 2 つと異なり、`require-corp`/`credentialless` は実際に配信しているサイト固有のクロスオリジンリソース（フォント、画像、サードパーティの iframe）をブロックしうるためです — 調整可能（`security.coep_mode`）。CSP ゾーン（`security.csp_zones`）：パスのプレフィックスごとの **明示的な** 例外（例：本当に必要な `/un-dossier/` 配下だけ `unsafe-inline`）。各ゾーンはそのプレフィックスについてデフォルトのポリシーを完全に置き換えます — 統合も全体的な緩和も決してしません。例外はすべて意図的であっても `audit security` に表示され続けます（CSP-001/CSP-002 はゾーンもスキャンします）。ディレクティブごとのウィザード（**汎用セキュリティ** 画面）で作成でき、各項目にはグローバルポリシーの **現在** の値があらかじめ入っています — 空欄から始めて他のディレクティブを意図せず失うのではなく、変えるべきところだけを変えるためです。組み立てたゾーンが `unsafe-inline`/`unsafe-eval`/汎用ソース `*` を緩める場合は、追加の明示的な確認を求めます。
- IPv4 射影 IPv6 アドレス（`::ffff:x.x.x.x`）はあらゆる比較（ブロックリスト、信頼済みプロキシ、レート制限）の前に正規化します — そうしないと既知の回避手段になります。
- 通常の単体テスト/結合テストに加え、HTTP パーサーとパスリゾルバーに対するプロパティテスト（`hypothesis`、数千件の生成例）で検証しています。

## 9. TLS

### 9a. 自己署名証明書（最小構成）

ローカル/ラボ/VPN（Tailscale...）の現実的な用途をカバー：単一のリスナー、直接の `ssl.SSLContext`、RSA 2048/4096 または ECDSA P-256/P-384。

### 9b. ローカル CA

個別に証明書を再インポートせずに信頼させたい複数のクライアント端末向け：ローカルの認証局が必要なだけサーバー証明書に署名します。

```text
secure/certificates/ca/
├── root-ca.key    # 0600 - プロジェクトで最も機微な要素
├── root-ca.pem    # 0644 - クライアントの信頼ストアにインポートする
├── serial.txt     # 0600 - 次のシリアル番号の管理
└── index.txt      # 0600 - 署名した証明書ごとの V(有効)/R(失効) 状態の管理
```

流れ：`certs generate-ca`（CA 鍵のパスフレーズは **必須**、`--password` を省略すると二重確認付きの対話入力）→ `certs generate-csr`（サーバーの鍵 + CSR）→ `certs sign-csr`（CA で署名し、CSR の SAN をコピー、求めに応じて `fullchain.pem` を作成）→ `tls.certificate.certificate_path` をこの `fullchain.pem` に向けます。漏洩した証明書は `certs revoke` で取り消します（`index.txt` に記録。まずその証明書が本当にこの CA 発行かを確認し、違えば拒否）。V1 では CRL の配布、外部 CA/第三者認証局向けの CSR、mTLS はありません（§15 参照）。

### 9c. Let's Encrypt / ACME（Certbot）— 公開・セルフホスト

ブラウザに認められる証明書を使う本当に公開されたサイト向けの、完全なセルフホスト構成：DDNS（Dynu など、すべて運用者の責任）→ Certbot → Omega-serv。TUI のウィザードのみ（`詳細設定 → TLS → Let's Encrypt ウィザード`）— `certbot certonly --webroot` をサブプロセスで呼び出し（**決して** `--standalone` は使わない。ポート 80 はすでに Omega-serv が使用中。ACME クライアントを再実装することも **決して** ない）、`--config-dir`/`--work-dir`/`--logs-dir` はプロジェクトの `secure/certificates/letsencrypt/` を指します — **決して** `/etc/letsencrypt/` ではない — このため Certbot 自体が完全に非特権で動きます。取得した証明書は自動でインポートされ（`certs import` と同じ仕組み、上の CLI 例を参照）、更新用のフックスクリプトが書き出されます。テストモード（staging）がデフォルトでチェックされています — Let's Encrypt の実際のレート制限を避けるため、ドメイン/webroot の動作を確認してからチェックを外してください。

Omega-serv の範囲外の前提条件：パブリック IP を指すドメイン（DDNS）と、このマシンに転送されたポート 80/443。

### 9d. 自動更新（Certbot）

`詳細設定 → TLS → 自動更新` は、**このインスタンス** で実際に検出したサービスマネージャーに合わせて動作します（複数インスタンス間で共有する仕組みには決してしません）：systemd → タイマー（`<service>-certbot-renew.timer`、1 日 2 回 + ランダムな遅延、インスタンスの `--config-dir` に限定した `certbot renew`）を生成してインストール。そうでなければ → `crontab` があれば crontab の行（現在のユーザー、特権不要）。それもなければ → 手動の手順を表示し、強制的な書き込みはしません。一部のディストリビューション（Arch/Manjaro を含む）では、Debian/Ubuntu と異なり Certbot パッケージがデフォルトでタイマーを **一切** インストールしません — そのため、すでにあるはずの仕組みを確認するだけでなく、この画面を用意しています。設定後は、更新のたびに証明書を自動で再インポート（`certs import`）してからサービスを再起動し、手作業はもう一切不要です。

## 10. セキュリティ監査

`audit security` は **ブロックしません**：`config check` のブロッキングゲートを `CRITICAL` として再実行し、そのうえで助言的なルール（TLS、CSP、危険なメソッド、タイムアウト、純粋なアップロードの衛生面、ファイルのパーミッション、証明書の期限、インストール済みの systemd ユニット、実 I/O によるログサイズ）を適用します。`WAF-001`（WAF が `log-only` のまま）は小さな状態ファイル（`var/run/waf-mode-state.json`）で時間をかけて観察され、繰り返し実行で `log-only` が 14 日以上観察されてはじめて発報します。初回の `audit` では発報しません。

## 11. Active Defense（deception + 戦闘モード）

オプションモジュール（`option enable active_defense`、デフォルトは無効）で、すでに計算済みの WAF シグナル（`WafDecision`/レピュテーション/ブロックリスト — 独立した 2 回目のスコア計算は決してしない）から敵対的な振る舞いを判定し、送信元をおとりへ振り向け、応答を遅らせてより詳細にログを取り、活用できるインシデントを構築し、侵害の痕跡（IoC）をエクスポートできます。トラフィック自体を遮断することは決してありません — ネットワークでの遮断は引き続き `omega-fire` の役割で、Active Defense は観察し、逸らし、遅らせ、記録します。

**脅威とスコア**：各送信元（`IP + User-Agent の SHA-256 ハッシュ`）はスコアを蓄積し（ブロックした `WAF-001` +10、レピュテーションのエスカレーション +25、既知の BAN +25、すでに割り当てられたおとりへの POST +30 — 新しいイベントがなければ 15 分ごとに -5 減衰）、`normal`/`suspicious`/`hostile`/`contained` に分類されます（`contained` にはさらに既知の BAN が必要）。`mode: monitor` は何もせずに観察し、`mode: enforce` は以下の操作を実際に適用します。

**戦闘モード**（`options.active_defense.settings.war_mode`）：設定可能なしきい値で発動する `DefensePlaybook`（`actions: ["redirect_to_decoy", "enrich_log", "delay", "rate_limit", "create_incident", "export_ioc"]`）を、`normal` 以外のすべての送信元に適用します：
- `enrich_log` — 別の JSONL ログ（`var/log/active-defense-enriched.jsonl`、WAF/本番のログと決して混ぜない）、ヘッダーは秘匿化、HTTP ボディは `logging.capture_request_body` に従ってハッシュ化（SHA-256）または切り詰め。
- `delay` — 上限とジッター付きの減速（`war_mode.slowdown.minimum_ms`/`maximum_ms`/`jitter_ms`）、asyncio のループを決してブロックしない。
- `rate_limit` — 送信元ごとの専用レート制限（`war_mode.rate_limit.requests`/`window_seconds`）、別のキーで WAF と同じ仕組みを再利用。
- `create_incident` — `thresholds.incident_score` を超えるとインシデントを自動で作成/統合。

**Deception**：`hostile`/`contained` の送信元は、観察した攻撃クラス（`deception.profiles.<名前>.match_attack_classes`、`scan`/`credential_stuffing`/`sqli`/`xss`/`path_traversal`/`upload_probe`/`api_probe`/`unknown` のうち 1 つ以上）に応じて選ばれる静的なおとり（`fake_admin`、`fake_cms`、`fake_api`、`fake_secrets` — もっともらしいが常に固定の応答で、実ファイルの読み込みやサブプロセスは決してない）に割り当てられます。分離には 2 段階があり、そのとおりに受け入れ、文書化しています：
- **レベル 1**（プロセス内の fixture、`isolation_level: "fixture"`、デフォルト）— 明示的に「弱い」分離：本番と同じプロセス、同じ OS ユーザー。fixture が静的なテンプレートを返す以外に何もしないから許容されるに過ぎません。プロファイルの名前は上の 4 つの fixture のいずれかと完全に一致しなければならず、そうでなければ検証（`validate_active_defense_config`）で拒否されます。名前を誤ったおとりが黙って一度も発動しないという罠を避けるためです。
- **レベル 2**（本当に分離されたバックエンド、`isolation_level: "proxy"`）— `options.active_defense.settings.deception.decoy_zones.<名前>`（すでに稼働しているサーバーの upstream `host`/`port`、自動作成は決してしない。`options.reverse_proxy` からは決して読まない — おとりが誤って本番ゾーンを指すことは決してなく、`config check` で検証）を通じて別プロセスに中継し、本番と同じ送信リバースプロキシの仕組み（`serve_proxy()`）を再利用します — 実際のリクエスト時に upstream に到達できなければ、攻撃者には 502 を返し、クラッシュは決してしません。

**設定画面**（TUI、アクティブセキュリティ → Active Defense → 設定）：上記すべての完全な設定 — モード、戦闘モードの有効化、範囲/操作/しきい値/減速/リクエスト上限、deception（デフォルトの振る舞い、おとりプロファイルとおとりゾーンの CRUD、各項目に例の値を表示）、IoC、保存とログ — を、保存のたびに CLI と同じルールで検証し、`config/omega-serve.json` を手で編集する必要は決してありません。変更後は必ず完全な再起動が必要です（Active Defense がホットリロードされることは決してありません）。

**インシデントと IoC**：インシデントごとの完全なタイムライン、指標の抽出（IP、ハッシュ化した User-Agent）、バージョン付き JSON/共有可能な IoC に限った CSV/Markdown レポートのエクスポート、そして交換形式 **STIX 2.1**（OpenCTI や SIEM などに読み込む bundle）と **MISP**（MISP のインターフェースからインポートするイベント）。デフォルトで TLP:AMBER の標識付き — ローカルファイルで、送信されることは決してありません。各エクスポートには `<export>.sha256` ファイル（標準の `sha256sum` 形式）が付きます。`ioc.auto_export_on_close`（デフォルトは true）なら、インシデントを閉じたときに自動でエクスポートします。期限切れの状態と監査ログは自動で削除され、データベースには上限があります（ディスクの枯渇防止）。`active-defense purge` はさらに、静かになったインシデントを閉じます。

**シミュレーション**：`active-defense simulate`（CLI）と「シミュレート」ボタン（TUI、アクティブセキュリティ画面）は、スコア/レベルを予測し、発動するはずの各操作を説明します — 厳格なドライランで、実際の書き込みもネットワークへの影響もありません。

バックアップ/復元：`config backup --include-active-defense` は sqlite データベース（脅威/インシデント/割り当て）をアーカイブに含めます — 平文の秘密情報は決して含まれないため、`--include-auth` と異なり `--confirm-secrets` は不要です。

## 11b. 機微なパスのリスト（WAF）

WAF は、1 行に 1 つのパス（またはキーワード）を書いた **編集可能なリスト** をテキストファイルとして、**アクティブセキュリティ → Custom → 追加 →「パスリストを読み込む」** から読み込めます。デフォルトで読み込まれるものはありません：明示的な操作です。

- **同梱のリファレンス**：`sensitive-paths-hostile`（正当な用途のない 298 パス：秘密情報、バックアップ、VCS、コンソール…）と `sensitive-paths-probe`（調査用の 132 パスで、本物のサイトが配信していることもある：`/admin`、`/api`、監視…）。読み込むと `secure/waf/rules/keywords/` に **ローカルコピー** が作られます：編集するのはこのコピーで、omega-serv の更新で上書きされることは決してありません（その後「リファレンスの新着」が新しい項目を 1 つずつ提案します）。
- **構文**：`/admin`（→ `/admin` と `/admin/xxx`、`/administrator` は決して含まない）、`/.git/`（その配下すべて）、`/*.bak`（拡張子）、`!/api/v1`（例外、常に優先）。パスはエンジンと同様にデコードされます（`%2e`、二重エンコード、全角文字）。
- **重大度**：*観察*（ログのみ、初回の読み込みに推奨）、その後に中（単独では決してブロックしない）または高（初回アクセスから 403）。
- **リストごとの再犯**：1 回目のアクセス = 情報または拒否。M 分間に N 回のアクセス = 一時的なアプリケーション BAN（応答 451、Tailscale 経由でも）。繰り返しのブロック = omega-jail によるネットワーク BAN。リファレンス：hostile は 10 分間に 2 回 → 24 時間、probe は 10 分間に 5 回 → 1 時間。
- ローカルホスト、Tailscale（`100.64.0.0/10`）、ローカルネットワーク（`options.waf.reputation.never_auto_block`）は **決して自動 BAN されません**：BAN されうるのは外部のトラフィックだけです。ローカルプロキシの背後では、`127.0.0.1` の除外には `trusted_proxy` の有効化が必要です。`X-Forwarded-For` は右から左に読むため、クライアントが自分をローカルだと名乗ることはできません。
- **安全装置**：重要なパスは保護（`/`、`robots.txt`、`sitemap.xml`、`/.well-known/acme-challenge/`…）、実際に配信しているルート（エイリアス、リバースプロキシ、Auth ゾーン、webroot）に当たるブロッキングリストは拒否、エディター内の **「自分のログと照合」**（成功したリクエストに当たったはずの行、ワンクリックで例外）。
- **組み込みエディター**：行番号付きのライブ診断、パスの「テスト」、安全な書き込み（パーミッションとグループを維持、シンボリックリンクは拒否、外部での変更を検出）、サービスアカウントによる読み取り可否の確認（「権限を修正」）、そして **正直な** リロード：リストが検証を通らなければ理由とともに拒否され、サーバーは現在のルールを維持します。

## 11c. フォルダー別・IP/ネットワーク別のレート制限（WAF）

WAF のレート制限（トークンバケット、`options.waf.rate_limit`、デフォルトは IP ごとに 60 リクエスト / 60 秒）は、**アクティブセキュリティ → 除外とレート制限** から（または手で `rate_limit.path_policies` / `rate_limit.source_policies`）細かく調整できます：

- **フォルダー別ルール**（`prefix`、`requests`、`window_seconds`）：そのフォルダーについて全体の上限を **置き換え**、独自のカウンターを持ちます（`requests: 0` = 無制限）。最長のプレフィックスが優先されます。`/images` は `/images/a.png` を含みますが、`/images2` は決して含みません。典型的には 429 を返す重いページ（画像ギャラリー）です。
- **IP/ネットワーク別ルール**（`network`、`requests`、`window_seconds`、`trusted`）：同じ原理で、最も具体的なネットワークが優先されます。優先順位：フォルダー、次に IP/ネットワーク、最後に全体の上限。
- **一般の利用者に対する BAN は変わらない**：パブリック IP による超過は引き続き `waf-alerts.log` に `"action": "block"` として記録されるため、omega-jail による BAN の対象になります（10 分間に 3 回の拒否 → 12 時間）。**安全な送信元** — `never_auto_block` のネットワーク、または `trusted: true` が付いたルール — は 429 を受け取りますが `"action": "throttle"` として記録され、jail はこれを決して数えません。
- **magnet スクリプト**：その独自のレート制限（429 応答）は決して検知として数えられないため、自動 BAN につながることは決してありません。フォルダーまたは IP/ネットワークのルールが適用されるリクエストでは、ネイティブのルールが優先され、magnet の 429 は無視されます（攻撃シグネチャは引き続き適用されます）。
- レートのルールが WAF の検査を無効にすることは **決してありません**。逆に、検査の除外（`exclusions.path_prefixes`）が rate limit を解除することも決してありません。`trusted_proxy` が有効でなければ、`127.0.0.1`/`::1` を含むルールは無視されます（`never_auto_block` と同じ安全装置）。

## 12. サービスと運用

systemd/OpenRC/runit を自動検出（`service install/status/start/stop/restart/enable/disable/uninstall`）。生成される systemd ユニットはデフォルトで交渉の余地のない堅牢化を適用します：`NoNewPrivileges`、`PrivateTmp`、`ProtectSystem=strict`、`ProtectHome`、`var/` に限定した `ReadWritePaths`、専用ユーザー/グループ必須、`UMask=0077`、`Restart=on-failure`。SIGTERM で正常停止（処理中の接続をドレインし、設定可能な猶予期間の後に強制終了）。SIGHUP でホットリロード（WAF ルールと Auth ゾーンのみ — bind/ポート/TLS と Active Defense は完全な再起動なしには決して変更できません）。

## 13. ログ

`var/log/access.log`（Apache combined 形式 + `request_id`、ログインジェクション対策のエスケープ）、`var/log/error.log`。サイズ/保持ファイル数によるローテーション（`logs.rotation`）。ネイティブ WAF：`var/log/waf-alerts.log`（`options.waf.logging.path`）。magnet スクリプト（§7）：`options.waf.magnet.paths.alerts_log`/`.blocklist_log`、デフォルトは `var/log/waf-magnet-alerts.log`/`var/log/waf-magnet-blocklist.log` — magnet が有効な場合にのみライブラリへ自動で追加されます（*Omega-Serv の既知のログを追加* ボタン）。一方 `lnav` は常にこれらを提示します（存在しないファイルは起動時に単に無視されます）。

### 13a. リモートソース（SSH）

明示的な要求に応じて、リバースプロキシの背後にある同じローカルネットワーク上のバックエンドサーバーのログを集約します（**ログ管理 → ライブラリ → リモートソース（SSH）** 画面）。「fetch」は手動で 1 回きりの操作で、ライブストリームや自動ポーリングでは決してありません：*今すぐ取得* をクリックした時点で `scp` により **コピー** を取得し、`var/log/remote/` に書き込み、通常のログと同じようにライブラリに追加します（*アクセス* 列 = `ssh`、*更新日時* 列 = **今回の** 取得の日時 — リモートファイルの日時では決してない）。新たに取得すると、以前のコピーが新しいもので置き換わるだけです。

意図的な安全装置（完全な検討は `OMEGA-SERV_ETUDE-FAISABILITE_LOGS_DISTANTS.md` 参照）：自動のネットワークスキャンなし、明示的な設定なしの接続なし（ラベル/ホスト/リモートパス、任意のユーザー/ポート/秘密鍵 — 空なら手でコマンドを打ったときと同じように `ssh`/`~/.ssh/config` に任せる）、パスワードは決して尋ねず保存もしない（秘密鍵はパスで参照するだけで、Omega-serv が読み込んだり保存したりすることは決してない）、転送前のサイズ確認なし。`scp` の機能は **機能レジストリ** でローカルに検出します（実行ファイルの有無のみで、ホストへの到達性テストは決してしない）。Samba は意図的に見送っています（YAGNI、実際の必要性が確認されるまでは）。

## 14. テスト

```bash
source .venv/bin/activate
lint-imports        # 8 つのレイヤー契約を検証
pytest -q           # 2485 件のテスト
ruff check .
mypy src
```

構成：`tests/unit/`（ドメイン/アプリケーション、テストダブル）、`tests/integration/`（実際の TCP ソケット上の本物の asyncio サーバー、サブプロセスの本物の `openssl`、完全な一時プロジェクトに対する本物の CLI コマンド、Textual の `Pilot` API による対話型インターフェース - スクリーンショットは決して使わない）、`tests/security/`（HTTP パーサーとパスリゾルバーに対する `hypothesis` のプロパティテスト）。

## 15. 範囲外

- 生の CGI（FastCGI/PHP-FPM のみ）
- mTLS（証明書によるクライアント認証）、OCSP stapling
- 外部 CA / 第三者認証局向けの CSR、完全な CRL 配布
- Active Defense：`omega-fire` の BAN イベントとの実際の統合（`omega-fire` 側で止まっており、現時点で読み取り用のインターフェースを一切公開していないため）

---

> 🔒 OMEGA-SERV — 堅牢で、充実し、安全で、防御力のある Web サーバー。
