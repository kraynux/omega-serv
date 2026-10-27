<!-- Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE) -->

# omega-serv dibandingkan dengan server web di pasaran

**Perbandingan terukur: nginx · lighttpd · Caddy · Apache · Traefik · omega-serv 2.0**

🌐 [Français](../../comparatif-serveurs-web.md) · [English](../en/comparatif-serveurs-web.md) · [Español](../es/comparatif-serveurs-web.md) · [Português (Brasil)](../pt-BR/comparatif-serveurs-web.md) · [Italiano](../it/comparatif-serveurs-web.md) · [Deutsch](../de/comparatif-serveurs-web.md) · [Nederlands](../nl/comparatif-serveurs-web.md) · [Polski](../pl/comparatif-serveurs-web.md) · [Русский](../ru/comparatif-serveurs-web.md) · [中文](../zh-CN/comparatif-serveurs-web.md) · [Tiếng Việt](../vi/comparatif-serveurs-web.md) · [ไทย](../th/comparatif-serveurs-web.md) · **Bahasa Indonesia** · [日本語](../ja/comparatif-serveurs-web.md) · [한국어](../ko/comparatif-serveurs-web.md) · [हिन्दी](../hi/comparatif-serveurs-web.md) · [العربية](../ar/comparatif-serveurs-web.md)

Dokumen ini menempatkan omega-serv di antara server web yang paling banyak digunakan. Dokumen ini tidak berusaha menunjuk « server terbaik »: setiap alat menjawab kebutuhan yang berbeda. Dokumen ini memberikan tiga hal:

1. **pengukuran nyata**, dilakukan di mesin yang sama, dengan klien yang sama dan berkas yang sama, serta dapat direproduksi;
2. **perbandingan fungsi**, masing-masing diverifikasi dalam dokumentasi resmi setiap server (tautan di akhir dokumen), dengan membedakan yang terintegrasi dari yang memerlukan modul atau plugin;
3. apa yang **benar-benar ditambahkan** omega-serv, dan apa yang dilakukan server lain **lebih baik darinya**.

Semua angka di bawah diukur pada 26 Oktober 2026. Tidak ada angka yang diambil dari situs lain atau diperkirakan.

---

## Daftar isi

1. [Ringkasnya](#1-ringkasnya)
2. [Metode pengukuran](#2-metode-pengukuran)
3. [Performa: omega-serv dibandingkan dengan nginx, lighttpd, dan Caddy](#3-performa-omega-serv-dibandingkan-dengan-nginx-lighttpd-dan-caddy)
4. [omega-serv 1.0 → 2.0: apa yang berubah, terukur](#4-omega-serv-10--20-apa-yang-berubah-terukur)
5. [Perbandingan fungsi](#5-perbandingan-fungsi)
6. [Administrasi dan kemudahan penggunaan](#6-administrasi-dan-kemudahan-penggunaan)
7. [Apa yang ditambahkan omega-serv](#7-apa-yang-ditambahkan-omega-serv)
8. [Apa yang dilakukan server lain lebih baik](#8-apa-yang-dilakukan-server-lain-lebih-baik)
9. [Server mana untuk kebutuhan apa](#9-server-mana-untuk-kebutuhan-apa)
10. [Mereproduksi pengukuran](#10-mereproduksi-pengukuran)
11. [Sumber](#11-sumber)

---

## 1. Ringkasnya

- **Throughput mentah pada berkas kecil**: nginx dan lighttpd, yang ditulis dalam C, melayani **10 hingga 20 kali lebih banyak** permintaan per detik daripada omega-serv, yang ditulis dalam Python. Caddy, yang ditulis dalam Go, berada di antaranya. Ini perbedaan sifat, bukan penyetelan: omega-serv tidak menyasar ranah ini.
- **Berkas besar**: sejak 2.0, omega-serv menyerahkan pengiriman ke kernel (`sendfile`). Ia lalu mencapai **orde throughput yang sama** dengan nginx, lighttpd, dan Caddy di mesin ini: 2,1 GB/dtk dibandingkan 2,0 hingga 2,4 GB/dtk.
- **Memori**: lighttpd (1 MB) dan nginx (4 hingga 5 MB) tetap tak terjangkau. omega-serv bertahan di bawah 30 MB saat dibebani dengan 1 proses, Caddy sekitar 55 MB.
- **Dari 1.0 ke 2.0**: throughput berkas besar dikali 2,8; memori selama unduhan besar dibagi 45; hingga +50 % pada berkas kecil dengan 2 proses (mode boost); biaya Active Defense dibagi 12.
- **Yang dimiliki omega-serv sebagai tambahan**: administrasi lengkap lewat antarmuka terminal (TUI), dalam 17 bahasa; WAF dan pertahanan aktif terintegrasi; batas keamanan yang tetap akurat dengan beberapa proses; impor skrip lighttpd mod_magnet; pengelolaan beberapa instans.
- **Yang tidak dimilikinya**: HTTP/2 dan HTTP/3, penemuan layanan Docker/Kubernetes, klien ACME terintegrasi (memakai Certbot), throughput server yang ditulis dalam C.

---

## 2. Metode pengukuran

### Mesin dan perangkat lunak

| Elemen | Nilai |
|---|---|
| Prosesor | Intel Core i5 M480 2,67 GHz (2010): 2 inti fisik, 4 thread |
| Memori | 8 GB |
| Sistem | Manjaro Linux, kernel 6.18 |
| Jaringan | loopback lokal (127.0.0.1) |
| Klien beban | [oha](https://github.com/hatoo/oha) 1.16.0 (ditulis dalam Rust) |
| nginx | 1.30.4 (paket Manjaro) |
| lighttpd | 1.4.85 (paket Manjaro) |
| Caddy | 2.11.4 (paket Manjaro) |
| omega-serv | 1.0.0 (arsip yang dirilis) dan 2.0.0, dengan Python 3.14.7 |

Apache dan Traefik tidak diukur, karena tidak terpasang di mesin ini. Traefik juga bukan server berkas (lihat §5). Kedua server ini karenanya hanya muncul di perbandingan fungsi.

### Protokol

- **Isolasi prosesor**: setiap server disematkan ke inti fisik 0 (thread 0 dan 2), dan klien ke inti fisik 1 (thread 1 dan 3). Dengan begitu klien tidak mencuri waktu server, dan semua server mendapat sumber daya yang persis sama.
- **Berkas yang sama untuk semua**: `small.html` (1 KB), `medium.png` (100 KB), dan `large.bin` (5 MB), disajikan dari folder yang sama.
- **Log akses aktif di semua server**, karena server produksi mencatat log.
- **HTTP/1.1 tanpa enkripsi, koneksi persisten (keep-alive)**. Konkurensi 32 koneksi untuk berkas 1 KB dan 100 KB, dan 8 untuk berkas 5 MB.
- **Durasi**: 10 detik per berkas dan per konfigurasi.
- **Pengulangan**: 3 putaran lengkap, diselang-seling (semua server di putaran 1, lalu semua di putaran 2, dst.). Tabel memberikan **median** dari ketiga putaran.
- **Memori**: PSS (*Proportional Set Size*) kumulatif dari semua proses server. Berbeda dengan RSS, halaman yang dibagi antarproses hanya dihitung sekali. Diukur saat diam, lalu setelah dibebani.
- **Konfigurasi**: nginx, lighttpd, dan Caddy dalam konfigurasi dasarnya (berkas statis, log akses). omega-serv memakai profil `standard`, dengan WAF dinonaktifkan lalu diaktifkan dengan semua aturan yang disediakan.
- **Jumlah proses**: setiap server diukur dengan 1 lalu 2 proses (nginx `worker_processes`, lighttpd `server.max-worker`, Caddy `GOMAXPROCS`, omega-serv `server.workers`).

### Batasan yang perlu diketahui

- **Mesin sederhana dan lama.** Nilai absolut akan jauh lebih tinggi pada server modern. Yang bermakna adalah **rasio** antarserver yang diukur dalam sesi yang sama.
- **Variabilitas antarsesi**: sekitar 10 hingga 30 % tergantung beban latar mesin. Putaran dalam satu sesi tetap konsisten: selisih kurang dari 5 % untuk omega-serv dan Caddy, lebih besar untuk nginx dan lighttpd, yang throughput sangat tingginya lebih sensitif terhadap bagian mesin lainnya.
- **Loopback lokal**: pengukuran tidak melewati jaringan nyata. Di jaringan nyata, throughput berkas besar hampir selalu dibatasi oleh bandwidth, bukan oleh server.
- **Tanpa TLS** dalam pengukuran ini. Dengan HTTPS, omega-serv tidak dapat memakai `sendfile` dan mengirim berkas per blok.
- **Angka mentah**: diterbitkan bersama dokumen ini di [`docs/benchmarks/2026-10-26-campagne-brute.txt`](../../benchmarks/2026-10-26-campagne-brute.txt).

---

## 3. Performa: omega-serv dibandingkan dengan nginx, lighttpd, dan Caddy

### Berkas kecil (1 KB): permintaan per detik

| Server | 1 proses | 2 proses | Latensi p99 (1 proses) |
|---|---:|---:|---:|
| lighttpd 1.4.85 | 25 521 | 29 700 | 4,5 ms |
| nginx 1.30.4 | 14 054 | 18 315 | 4,7 ms |
| Caddy 2.11.4 | 3 697 | 5 345 | 25,3 ms |
| **omega-serv 2.0** | **1 358** | **1 953** | **37,5 ms** |
| omega-serv 2.0 + WAF | 1 130 | 1 617 | 48,5 ms |
| omega-serv 1.0 | 1 304 | — | 41,2 ms |

### Berkas sedang (100 KB): permintaan per detik

| Server | 1 proses | 2 proses |
|---|---:|---:|
| lighttpd | 11 635 | 13 037 |
| nginx | 8 024 | 9 555 |
| Caddy | 3 280 | 4 344 |
| **omega-serv 2.0** | **1 247** | **1 629** |
| omega-serv 2.0 + WAF | 1 012 | 1 347 |
| omega-serv 1.0 | 1 064 | — |

### Berkas besar (5 MB): throughput

| Server | 1 proses | 2 proses |
|---|---:|---:|
| lighttpd | 2 379 MB/dtk | 2 407 MB/dtk |
| nginx | 2 242 MB/dtk | 1 981 MB/dtk |
| Caddy | 2 165 MB/dtk | 2 229 MB/dtk |
| **omega-serv 2.0** | **1 658 MB/dtk** | **2 115 MB/dtk** |
| omega-serv 1.0 | 584 MB/dtk | — |

### Memori (PSS, semua proses server)

| Server | Saat diam | Setelah dibebani |
|---|---:|---:|
| lighttpd (1 atau 2 proses) | 1 MB | 1 MB |
| nginx (1 atau 2 proses) | 4 hingga 5 MB | 4 hingga 5 MB |
| **omega-serv 2.0 (1 proses)** | **26 MB** | **30 MB** |
| omega-serv 2.0 (2 proses) | 39 MB | 48 MB |
| Caddy | 50 MB | 56 MB |
| omega-serv 1.0 | 22 MB | 100 MB |

### Cara membaca

- **Pada berkas kecil dan sedang**, selisih dengan nginx dan lighttpd adalah satu orde besaran (×10 hingga ×20). Itulah biaya server yang ditulis dalam Python: setiap permintaan melewati interpreter, sedangkan nginx dan lighttpd memprosesnya dalam C terkompilasi. Mode boost mengurangi selisih itu, tanpa menutupnya.
- **Pada berkas besar**, server-server bertemu, karena kernel yang menyalin data (`sendfile`). Dengan 2 proses, omega-serv 2.0 mencapai 2,1 GB/dtk, dalam rentang yang sama dengan yang lain (2,0 hingga 2,4 GB/dtk).
- **WAF omega-serv memakan sekitar 17 %** pada berkas kecil: ia memeriksa setiap permintaan. nginx, lighttpd, dan Caddy diukur tanpa WAF; WAF yang ditambahkan ke server ini (ModSecurity, Coraza) juga memiliki biaya, yang tidak diukur di sini.
- **Untuk memberi gambaran**: 1 300 permintaan per detik berarti lebih dari 110 juta permintaan per hari di mesin tahun 2010 ini. Jauh melampaui kebutuhan situs pribadi, layanan internal, atau laboratorium, yang merupakan penggunaan yang disasar omega-serv.

---

## 4. omega-serv 1.0 → 2.0: apa yang berubah, terukur

### Performa

Kedua versi diukur dalam sesi yang sama, di mesin yang sama, dan dengan protokol yang sama.

| Pengukuran | 1.0.0 | 2.0.0 | Perubahan |
|---|---:|---:|---:|
| Berkas kecil (1 KB), 1 proses | 1 304 req/s | 1 358 req/s | +4 % |
| Berkas kecil (1 KB), mode boost 2 proses | — | 1 953 req/s | **+50 %** vs 1.0 |
| Berkas kecil dengan WAF, 1 proses | 1 097 req/s | 1 130 req/s | +3 % |
| Berkas kecil dengan WAF, 2 proses | — | 1 617 req/s | **+47 %** vs 1.0 |
| Berkas 100 KB, 1 proses | 1 064 req/s | 1 247 req/s | +17 % |
| Berkas besar (5 MB), 1 proses | 584 MB/dtk | 1 658 MB/dtk | **×2,8** |
| Berkas besar (5 MB), 2 proses | — | 2 115 MB/dtk | **×3,6** vs 1.0 |
| Memori setelah dibebani, 1 proses | 100 MB | 30 MB | **÷3** |

### Unduhan besar secara bersamaan

Uji: 3 unduhan bersamaan sebuah berkas 300 MB, sementara halaman kecil diminta terus-menerus. Dua kali uji memberikan hasil yang identik.

| Pengukuran | 1.0.0 | 2.0.0 |
|---|---:|---:|
| Memori server pada puncaknya | 1 835 MB | 40 MB |
| Halaman kecil selama unduhan: median | 3 hingga 4 ms | 2 ms |
| Halaman kecil selama unduhan: kasus terburuk | 1,7 hingga 1,8 dtk | 5 ms |

Versi 1.0 memuat setiap berkas sepenuhnya ke memori sebelum mengirimnya. Versi 2.0 mengirimnya per blok, atau menyerahkannya ke kernel: memori tidak lagi bergantung pada ukuran berkas, dan server tetap responsif selama unduhan.

### Biaya pertahanan aktif

Biaya satu pengamatan ancaman oleh Active Defense, untuk setiap permintaan mencurigakan, diukur di disk (ext4) pada 2 000 pengamatan:

| Pengukuran | 1.0.0 | 2.0.0 |
|---|---:|---:|
| Median | 2,84 ms | 0,23 ms |
| p99 | 11,6 ms | 2,3 ms |
| Maksimum | 18 hingga 20 ms | 37 hingga 46 ms |

Median dibagi 12. Sebaliknya, maksimumnya lebih tinggi di 2.0: beberapa lonjakan terisolasi, terkait penulisan berkala jurnal SQLite ke disk.

### Fungsi yang hadir di 2.0

**Mengejar standar pasar**: nginx, lighttpd, Caddy, dan Apache sudah melakukan semua ini. omega-serv mengejar mereka.

- Permintaan bersyarat (ETag, Last-Modified, respons 304): memuat ulang halaman hanya mengunduh ulang yang berubah.
- Permintaan parsial (Range, 206/416): melanjutkan unduhan, memajukan video.
- Pengiriman berkas dengan `sendfile` atau per blok, dengan memori yang stabil.
- Berkas yang sudah dikompresi (`.gz`, `.br`) diletakkan di samping aslinya.
- Cache-Control bawaan menurut jenis berkas (gambar, font, CSS/JS), dapat diatur.
- Beberapa proses server (mode boost, `server.workers`).

**Fungsi yang lebih luas:**

- **Reverse proxy lengkap.** Versi 1.0 hanya memiliki penerus sederhana (bergiliran, TLS ke hulu, WebSocket). Versi 2.0 menambahkan:
  - 6 strategi distribusi, total 7;
  - afinitas sesi dan perutean berdasarkan header;
  - kesehatan pasif dan aktif server hulu;
  - cache respons;
  - perlindungan terhadap kelebihan beban dan loop;
  - pengendalian panas.
- **Batas laju per folder dan per alamat atau jaringan**, selain batas global.
- **Penghitung keamanan yang dibagi antarproses** (lihat §7).
- **Daftar jalur sensitif** siap pakai, dengan mode pengamatan dan editor terintegrasi.
- **Impor skrip lighttpd mod_magnet** (lihat §7).
- **Antarmuka dalam 17 bahasa**, dengan bahasa terpisah untuk halaman yang dilihat pengunjung dan untuk ekspor.
- **Log yang dirombak sepenuhnya**:
  - pustaka log;
  - tiga penampil, termasuk lnav;
  - pengambilan log jarak jauh melalui SSH.

---

## 5. Perbandingan fungsi

Keterangan:
- ✅ terintegrasi;
- 🧩 modul resmi proyek, perlu diaktifkan atau dipasang;
- 🔌 modul atau plugin pihak ketiga;
- ⚙️ melalui alat eksternal;
- ❌ tidak ada.

« Komersial » berarti fungsi yang hanya ada di edisi berbayar.

### Layanan HTTP

| Fungsi | nginx | lighttpd | Caddy | Apache | Traefik | omega-serv 2.0 |
|---|---|---|---|---|---|---|
| Menyajikan berkas statis | ✅ | ✅ | ✅ | ✅ | ❌ (hanya proxy) | ✅ |
| ETag / 304 / Range | ✅ | ✅ | ✅ | ✅ | — | ✅ |
| Berkas terkompresi `.gz` / `.br` | ✅ `gzip_static` (`.br`: 🔌) | 🔌 skrip Lua (mod_magnet) | ✅ `precompressed` | 🧩 resep mod_rewrite | — | ✅ |
| Kompresi langsung | ✅ | ✅ mod_deflate | ✅ | 🧩 mod_deflate | ✅ middleware | ❌ |
| HTTP/2 | ✅ | ✅ | ✅ | 🧩 mod_http2 | ✅ | ❌ |
| HTTP/3 (QUIC) | ✅ | ❌ | ✅ | ❌ | ✅ | ❌ |
| PHP melalui FastCGI | ✅ | ✅ | ✅ | ✅ | ❌ | ✅ |
| Beberapa proses atau inti | ✅ workers | ⚠️ `max-worker`, tidak disarankan oleh dokumentasi | ✅ (Go, semua inti) | ✅ MPM | ✅ (Go) | ✅ `server.workers` |

### Reverse proxy

| Fungsi | nginx | lighttpd | Caddy | Apache | Traefik | omega-serv 2.0 |
|---|---|---|---|---|---|---|
| Penyeimbangan beban | ✅ bergiliran, koneksi paling sedikit, hash | ✅ fair, round-robin, hash, sticky | ✅ sekitar selusin strategi | 🧩 mod_proxy_balancer | ✅ wrr, p2c, hrw, least-time | ✅ 7 strategi, termasuk beban nyata |
| Kesehatan pasif (menyingkirkan server mati) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Kesehatan aktif (probe berkala) | Komersial (NGINX Plus) | ❌ | ✅ | 🧩 mod_proxy_hcheck | ✅ | ✅ |
| Cache respons | ✅ `proxy_cache` | ❌ | 🔌 | 🧩 mod_cache | Komersial | ✅ |
| WebSocket | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Penemuan layanan (Docker, Kubernetes) | 🔌 | ❌ | 🔌 | ❌ | ✅ (inti proyek) | ❌ |

### TLS

| Fungsi | nginx | lighttpd | Caddy | Apache | Traefik | omega-serv 2.0 |
|---|---|---|---|---|---|---|
| Sertifikat otomatis (ACME, Let's Encrypt) | 🧩 `ngx_http_acme_module` | ⚙️ Certbot | ✅ secara bawaan | 🧩 mod_md | ✅ | ⚙️ Certbot, dengan asisten terintegrasi dan perpanjangan terjadwal |
| CA lokal | ❌ | ❌ | ✅ CA internal (penerbitan otomatis) | ❌ | ❌ | ✅ pembuatan, penandatanganan CSR, pencabutan |

### Keamanan

| Fungsi | nginx | lighttpd | Caddy | Apache | Traefik | omega-serv 2.0 |
|---|---|---|---|---|---|---|
| Batas laju per klien | ✅ `limit_req` | ⚠️ mod_evasive (hanya koneksi serentak) | 🔌 caddy-ratelimit | 🔌 mod_evasive, mod_qos | ✅ middleware | ✅ |
| Batas yang dibagi antarproses | ✅ zona memori bersama | ❌ dihitung per proses | — (hanya 1 proses) | tergantung modul | 1 instans; beberapa dengan Redis | ✅ memori bersama |
| WAF (tanda tangan SQLi/XSS, pemindai…) | 🔌 ModSecurity, Komersial (App Protect) | ❌ (skrip Lua harus ditulis) | 🔌 Coraza | 🔌 ModSecurity | 🔌 plugin | ✅ terintegrasi |
| Daftar blokir dengan kedaluwarsa, residivisme | ⚙️ fail2ban | ⚙️ fail2ban | ⚙️ fail2ban | ⚙️ fail2ban | ⚙️ | ✅ terintegrasi |
| Umpan, mode perang, insiden, ekspor IoC | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ Active Defense |
| Audit keamanan konfigurasi | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ `audit security` |
| Mode pengamatan (mencatat tanpa memblokir) | tergantung modul | — | tergantung plugin | ✅ ModSecurity `DetectionOnly` | tergantung plugin | ✅ |

### Ekstensibilitas

| Fungsi | nginx | lighttpd | Caddy | Apache | Traefik | omega-serv 2.0 |
|---|---|---|---|---|---|---|
| Bahasa skrip | 🧩 njs (JavaScript); 🔌 Lua (OpenResty) | ✅ Lua (mod_magnet) | modul Go (kompilasi ulang) | 🧩 mod_lua | plugin Go atau WebAssembly | 🔌 impor skrip mod_magnet (opsi `magnet`) |
| Ekosistem modul | sangat luas | terarah | luas | sangat luas | luas | tidak ada: semuanya terintegrasi |

---

## 6. Administrasi dan kemudahan penggunaan

| Server | Cara administrasi utama | Antarmuka | Muat ulang tanpa gangguan |
|---|---|---|---|
| nginx | berkas konfigurasi | tidak ada (dasbor: NGINX Plus, komersial) | ✅ `nginx -s reload` |
| lighttpd | berkas konfigurasi | tidak ada (mod_status hanya-baca) | ✅ mulai ulang halus |
| Caddy | Caddyfile atau JSON | API REST administrasi | ✅ melalui API |
| Apache | berkas konfigurasi dan `.htaccess` | tidak ada (mod_status hanya-baca) | ✅ `graceful` |
| Traefik | label kontainer, berkas, atau Kubernetes | dasbor web (hanya-baca) | ✅ konfigurasi dinamis |
| omega-serv | antarmuka terminal (TUI) dan baris perintah (CLI); berkas JSON tidak perlu diedit | **TUI lengkap dengan keyboard dan tetikus, 17 bahasa, bantuan terintegrasi** | ✅ untuk sebagian besar pengaturan; mulai ulang diumumkan untuk port, TLS, dan jumlah proses |

Secara konkret, dengan omega-serv, konfigurasi, keamanan, log, layanan sistem, cadangan, dan instans dikelola dari satu antarmuka. Setiap pengaturan dijelaskan dan diperiksa sebelum ditulis. Dengan server lain, orang mengedit berkas teks, lalu memakai alat-alat terpisah (Certbot, fail2ban, logrotate, ModSecurity, alat pemantauan…).

Sebagai gantinya, pendekatan « berkas konfigurasi » nginx, Apache, dan Caddy sangat mudah diotomatisasi (Ansible, kontainer, kontrol versi). omega-serv memiliki CLI yang dapat ditulis skrip, tetapi ekosistem otomatisasinya masih terbatas.

---

## 7. Apa yang ditambahkan omega-serv

Bagian ini hanya memuat hal yang tidak disediakan apa adanya oleh server mana pun yang dibandingkan, tanpa modul pihak ketiga atau alat eksternal.

1. **Administrasi lengkap lewat antarmuka terminal.**
   - Antarmuka mencakup seluruh server: situs, keamanan, log, layanan, cadangan, dan instans.
   - Dapat dipakai dengan keyboard dan tetikus, di server tanpa tampilan grafis, bahkan melalui SSH.
   - Tersedia dalam 17 bahasa dan menjelaskan setiap pengaturan.
   - Server lain tidak memiliki antarmuka administrasi (nginx, lighttpd, Apache), atau hanya API (Caddy) atau dasbor hanya-baca (Traefik).
2. **Keamanan aktif terintegrasi, tanpa modul yang harus dirakit.**
   - WAF mencakup tanda tangan, daftar jalur yang dapat diedit, residivisme, daftar blokir dengan kedaluwarsa, reputasi, dan mode pengamatan.
   - Active Defense menambahkan umpan, mode perang, pelacakan insiden, ekspor indikator kompromi, dan simulasi tanpa efek.
   - Di tempat lain, fungsi-fungsi ini menuntut perakitan ModSecurity atau Coraza, set aturan, dan fail2ban.
3. **Batas keamanan yang akurat dengan beberapa proses.**
   - Dalam mode boost, batas laju dan residivisme WAF dibagi dalam memori antarproses. Penyerang karenanya tidak dapat melipatgandakan batasnya dengan jumlah proses.
   - lighttpd mendokumentasikan kasus sebaliknya: dengan `server.max-worker`, `mod_evasive` dan `mod_status` menghitung terpisah di setiap proses.
   - nginx juga membagi penghitungnya (zona `limit_req`), tetapi tidak memiliki WAF terintegrasi.
4. **Impor skrip lighttpd mod_magnet.**
   - Skrip perlindungan Lua yang sudah ditulis untuk lighttpd dapat diimpor tanpa ditulis ulang.
   - Skrip itu ditambahkan ke perlindungan terintegrasi tanpa pernah dapat melemahkannya, dan kompatibilitasnya diperiksa sebelum aktivasi.
5. **Pengelolaan beberapa instans.**
   - Registri mencatat semua instans, dan antarmuka berpindah dari satu ke yang lain.
   - Antarmuka juga dapat mencopot instans sepenuhnya.
6. **Audit keamanan konfigurasi**: perintah `audit security` bersifat informatif, tidak pernah memblokir, dan mengembalikan kode keluar yang dapat dipakai dalam skrip.
7. **Sumber log jarak jauh.**
   - Antarmuka mengambil log server lain melalui SSH, sesuai permintaan, tanpa kata sandi yang disimpan.
   - Antarmuka dapat membacanya dengan lnav, sambil menggabungkannya dengan log lokal.
8. **Pengerasan HTTP yang tidak dapat dinonaktifkan**, aktif sejak instalasi, apa pun profilnya:
   - validasi ketat header Host;
   - penolakan ambiguitas Content-Length / Transfer-Encoding;
   - header keamanan dan CSP, bahkan di halaman galat;
   - pembacaan X-Forwarded-For yang aman;
   - menolak berjalan sebagai root.

---

## 8. Apa yang dilakukan server lain lebih baik

- **Throughput dan latensi**: nginx dan lighttpd melayani 10 hingga 20 kali lebih banyak permintaan kecil, dengan latensi 8 hingga 10 kali lebih rendah. Untuk situs berlalu lintas tinggi, API publik, atau CDN, merekalah yang harus dipilih.
- **Memori**: lighttpd (1 MB) dan nginx (4 hingga 5 MB) cocok untuk mesin yang sangat terbatas (perangkat tertanam, Raspberry Pi kelas pemula, kontainer kecil).
- **Protokol**: HTTP/2 di semua server lain, HTTP/3 di nginx, Caddy, dan Traefik. omega-serv hanya berbicara HTTP/1.1.
- **HTTPS otomatis**: Caddy dan Traefik mengintegrasikannya secara bawaan, dan nginx (`ngx_http_acme_module`) serta Apache (`mod_md`) dengan modul resmi. omega-serv menyerahkannya ke Certbot, dengan asisten dan perpanjangan terjadwal.
- **Lingkungan terkontainerisasi**: penemuan layanan otomatis Traefik (Docker, Kubernetes) tidak memiliki padanan di omega-serv.
- **Ekosistem**: nginx dan Apache menawarkan ribuan modul, panduan, dan integrasi. Caddy menawarkan sistem modul dalam Go. omega-serv adalah proyek muda, dipelihara oleh satu orang.
- **Kompresi langsung**: omega-serv hanya menyajikan berkas yang sudah dikompresi.

---

## 9. Server mana untuk kebutuhan apa

| Kebutuhan | Pilihan yang disarankan |
|---|---|
| Situs berlalu lintas tinggi, API publik, CDN, throughput maksimum | **nginx** |
| Mesin sangat terbatas, perangkat tertanam, berkas statis | **lighttpd** |
| Mulai cepat dengan HTTPS otomatis, konfigurasi singkat | **Caddy** |
| Aplikasi PHP lama, `.htaccess`, hosting bersama | **Apache** |
| Docker, Kubernetes, layanan mikro | **Traefik** |
| Situs kecil, layanan internal, laboratorium, VPN, administrasi tanpa mengedit berkas | **omega-serv** |
| Server terpapar tempat Anda ingin melihat dan mengendalikan keamanan (WAF, larangan, umpan) dari satu antarmuka | **omega-serv** |
| Reverse proxy internal dengan distribusi, kesehatan, dan cache, dikendalikan dari antarmuka | **omega-serv** |
| Mempelajari pengerasan HTTP dan pertahanan aktif | **omega-serv** |

Alat-alat ini juga dapat digabungkan. Misalnya:
- nginx atau Traefik di garis depan Internet, dengan omega-serv di belakangnya untuk layanan internal, keamanannya, dan administrasinya;
- omega-serv sebagai reverse proxy internal di depan beberapa server aplikasi.

---

## 10. Mereproduksi pengukuran

Alat-alatnya disertakan di repositori, di bawah `tools/bench/`. Diperlukan nginx, lighttpd, Caddy, dan oha terpasang, serta lingkungan pengembangan omega-serv (`.venv`).

```sh
# 1. siapkan folder pengukuran (berkas uji, konfigurasi, omega-serv 1.0 dan 2.0)
tools/bench/compare/setup.sh /jalur/ukur omega-serv-1.0.0.tar.gz

# 2. 12 konfigurasi, 3 pengulangan diselang-seling (sekitar 22 menit)
tools/bench/compare/campaign.sh /jalur/ukur > hasil.txt

# 3. median
python3 tools/bench/compare/summarize.py hasil.txt

# unduhan besar (memori dan responsivitas), 2.0 lalu 1.0
.venv/bin/python tools/bench/bigfile.py
BENCH_SRC=/jalur/ukur/v1-archive/omega-serv/src \
BENCH_EXTRA_PATH=/jalur/ukur/v1-archive/omega-serv/vendor/omega-lib/src \
  .venv/bin/python tools/bench/bigfile.py

# ukur server lain mana pun yang sudah berjalan, tanpa oha
python3 tools/bench/bench_any.py --make-files /srv/webroot-uji
python3 tools/bench/bench_any.py --port 8080
```

Secara bawaan, server disematkan ke thread 0 dan 2, dan klien ke thread 1 dan 3, sesuai dengan mesin pengukuran. Sesuaikan pembagian ini dengan prosesor Anda (`lscpu -e` memberikan topologinya) melalui variabel `SRV_CPUS` dan `CLI_CPUS`.

Untuk menerbitkan hasil Anda sendiri, sebutkan mesin, versi, pembagian prosesor, dan ketiga pengulangan.

---

## 11. Sumber

Fungsi server lain, menurut dokumentasi resminya (diakses pada 26 Oktober 2026).

**nginx**
- [Batas laju `limit_req` (zona memori bersama)](https://nginx.org/en/docs/http/ngx_http_limit_req_module.html)
- [Berkas terkompresi `gzip_static`](https://nginx.org/en/docs/http/ngx_http_gzip_static_module.html)
- [Modul ACME resmi `ngx_http_acme_module`](https://nginx.org/en/docs/http/ngx_http_acme_module.html)
- [Penyeimbangan beban (`upstream`)](https://nginx.org/en/docs/http/ngx_http_upstream_module.html)
- [HTTP/3](https://nginx.org/en/docs/http/ngx_http_v3_module.html)
- [Konektor ModSecurity untuk nginx](https://github.com/owasp-modsecurity/ModSecurity-nginx)

**lighttpd**
- [`server.max-worker`: tidak disarankan, penghitung per proses untuk mod_status dan mod_evasive](https://redmine.lighttpd.net/projects/lighttpd/wiki/Server_max-workerDetails)
- [mod_magnet (skrip Lua)](https://redmine.lighttpd.net/projects/lighttpd/wiki/Docs_ModMagnet)
- [mod_deflate (kompresi, cache)](https://redmine.lighttpd.net/projects/lighttpd/wiki/Mod_deflate)
- [mod_proxy (distribusi, kesehatan pasif, WebSocket)](https://redmine.lighttpd.net/projects/lighttpd/wiki/Docs_ModProxy)
- [mod_evasive (koneksi serentak per alamat)](https://redmine.lighttpd.net/projects/lighttpd/wiki/Docs_ModEvasive)

**Caddy**
- [HTTPS otomatis](https://caddyserver.com/docs/automatic-https)
- [`file_server` dan `precompressed`](https://caddyserver.com/docs/caddyfile/directives/file_server)
- [`reverse_proxy` (strategi, kesehatan aktif dan pasif)](https://caddyserver.com/docs/caddyfile/directives/reverse_proxy)
- [API administrasi](https://caddyserver.com/docs/api)
- [Plugin batas laju caddy-ratelimit](https://github.com/mholt/caddy-ratelimit)
- [WAF Coraza untuk Caddy](https://github.com/corazawaf/coraza-caddy)
- [caddy-docker-proxy](https://github.com/lucaslorentz/caddy-docker-proxy)

**Apache HTTP Server**
- [mod_md (ACME)](https://httpd.apache.org/docs/2.4/mod/mod_md.html)
- [mod_proxy_balancer](https://httpd.apache.org/docs/2.4/mod/mod_proxy_balancer.html)
- [mod_proxy_hcheck](https://httpd.apache.org/docs/2.4/mod/mod_proxy_hcheck.html)
- [mod_http2](https://httpd.apache.org/docs/2.4/mod/mod_http2.html)
- [mod_deflate, konten terkompresi](https://httpd.apache.org/docs/2.4/mod/mod_deflate.html)
- [ModSecurity](https://github.com/owasp-modsecurity/ModSecurity)

**Traefik**
- [Middleware `ratelimit` (di memori per instans, Redis opsional)](https://doc.traefik.io/traefik/reference/routing-configuration/http/middlewares/ratelimit/)
- [ACME](https://doc.traefik.io/traefik/https/acme/)
- [Providers (Docker, Kubernetes…)](https://doc.traefik.io/traefik/providers/overview/)

**Alat ukur**
- [oha](https://github.com/hatoo/oha)

---

*Perbandingan disusun oleh kraynux untuk omega-serv 2.0.0: pengukuran tanggal 26 Oktober 2026. Pengukuran hanya dilakukan pada satu mesin. Untuk setiap keputusan kapasitas, ukurlah di perangkat keras Anda sendiri dengan alat yang disediakan.*
