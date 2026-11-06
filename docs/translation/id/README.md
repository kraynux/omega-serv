<!-- Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE) -->
<div align="center">
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/assets/omega-serv.png" alt="Omega-Serv" width="384">
</div>

# 🔒 OMEGA-SERV

**Server web HTTP/1.1 yang mandiri, portabel, dan diperkeras secara bawaan.**

OMEGA-SERV menyajikan situs statis dan, jika Anda mau, PHP melalui PHP-FPM. Ia dirancang agar mudah dijalankan, mudah dikelola dari terminal, dan sulit disalahgunakan: pemeriksaan protokol HTTP aktif sejak awal dijalankan, sedangkan fungsi yang lebih lanjut — WAF, TLS, autentikasi, reverse proxy — tetap opsional dan harus diaktifkan dengan sengaja.

> Dibuat oleh [kraynux](https://github.com/kraynux) untuk [Omega-Server](https://kraynux.snake-mackarel.ts.net)

[Halaman resmi](https://kraynux.snake-mackarel.ts.net/omega-serv/translation/id/) ·
[Panduan lengkap](https://kraynux.snake-mackarel.ts.net/omega-serv/translation/id/guide.html) ·
[Tangkapan layar](https://kraynux.snake-mackarel.ts.net/omega-serv/screenshots/) ·
[Server demo](https://craftdark.snake-mackarel.ts.net) ·
[Perbandingan server web](comparatif-serveurs-web.md)

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![C++](https://img.shields.io/badge/C%2B%2B-20-00599C.svg?logo=c%2B%2B&logoColor=white)](https://isocpp.org/)
[![Lua](https://img.shields.io/badge/Lua-5.4%2B-2C2D72.svg)](https://www.lua.org/)
[![HTML](https://img.shields.io/badge/HTML-5-E34F26.svg)](https://developer.mozilla.org/docs/Web/HTML)
[![JavaScript](https://img.shields.io/badge/JavaScript-ES2020%2B-F7DF1E.svg)](https://developer.mozilla.org/docs/Web/JavaScript)
![Interface](https://img.shields.io/badge/Interface-CLI%20%2B%20TUI-cyan.svg)
[![Textual](https://img.shields.io/badge/Textual-TUI-5A5AFB.svg)](https://textual.textualize.io/)
[![Platform](https://img.shields.io/badge/Platform-Linux-informational.svg)](https://www.linux.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](../../../LICENSE)

🌐 Antarmuka, dokumentasi, ekspor, dan halaman pengunjung tersedia dalam **17 bahasa**.  
**Bahasa:**
<img src="https://flagcdn.com/w20/fr.png" alt="France" style="height:14px;"> [Français](../../../README.md) · <img src="https://flagcdn.com/w20/gb.png" alt="English" style="height:14px;"> [English](../en/README.md) · <img src="https://flagcdn.com/w20/es.png" alt="Español" style="height:14px;"> [Español](../es/README.md) · <img src="https://flagcdn.com/w20/br.png" alt="Português (Brasil)" style="height:14px;"> [Português (Brasil)](../pt-BR/README.md) · <img src="https://flagcdn.com/w20/it.png" alt="Italiano" style="height:14px;"> [Italiano](../it/README.md) · <img src="https://flagcdn.com/w20/de.png" alt="Deutsch" style="height:14px;"> [Deutsch](../de/README.md) · <img src="https://flagcdn.com/w20/nl.png" alt="Nederlands" style="height:14px;"> [Nederlands](../nl/README.md) · <img src="https://flagcdn.com/w20/pl.png" alt="Polski" style="height:14px;"> [Polski](../pl/README.md) · <img src="https://flagcdn.com/w20/ru.png" alt="Русский" style="height:14px;"> [Русский](../ru/README.md) · <img src="https://flagcdn.com/w20/cn.png" alt="中文" style="height:14px;"> [中文](../zh-CN/README.md) · <img src="https://flagcdn.com/w20/vn.png" alt="Tiếng Việt" style="height:14px;"> [Tiếng Việt](../vi/README.md) · <img src="https://flagcdn.com/w20/th.png" alt="ไทย" style="height:14px;"> [ไทย](../th/README.md) · <img src="https://flagcdn.com/w20/id.png" alt="Bahasa Indonesia" style="height:14px;"> [Bahasa Indonesia](README.md) · <img src="https://flagcdn.com/w20/jp.png" alt="日本語" style="height:14px;"> [日本語](../ja/README.md) · <img src="https://flagcdn.com/w20/kr.png" alt="한국어" style="height:14px;"> [한국어](../ko/README.md) · <img src="https://flagcdn.com/w20/in.png" alt="हिन्दी" style="height:14px;"> [हिन्दी](../hi/README.md) · <img src="https://flagcdn.com/w20/ae.png" alt="العربية" style="height:14px;"> [العربية](../ar/README.md)

---

**OMEGA-SERV** adalah server HTTP/1.1 yang ditulis dalam Python murni (hanya pustaka standar untuk inti server), dirancang untuk menyajikan konten statis dan, secara opsional, PHP-FPM, dengan pengerasan protokol yang aktif secara bawaan serta modul keamanan (WAF, TLS, autentikasi) yang dapat ditumpuk alih-alih dipaksakan. Mesin native C++ opsional dapat melayani permintaan sebagai pengganti mesin Python, dengan pemeriksaan keamanan yang sama. Ia bekerja pada mesin lokal yang menjalankannya, bukan pada target jarak jauh (keluarga yang sama dengan `omega-fire`); disusun dengan Clean Architecture, dengan `bootstrap/` sebagai akar komposisi (composition root).

<p align="center">
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/translation/id/A.png" width="24%" />
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/translation/id/B.png" width="24%" />
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/translation/id/C.png" width="24%" />
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/translation/id/D.png" width="24%" />
</p>

## Daftar isi

- [1. Visi dan cakupan](#1-visi-dan-cakupan)
  - [Yang dilakukan OMEGA-SERV](#yang-dilakukan-omega-serv)
  - [Yang tidak dilakukan OMEGA-SERV](#yang-tidak-dilakukan-omega-serv)
  - [OMEGA-SERV dibandingkan dengan server web di pasaran](#omega-serv-dibandingkan-dengan-server-web-di-pasaran)
  - [Peringatan penggunaan](#peringatan-penggunaan)
  - [Prasyarat](#prasyarat)
  - [Unduhan](#unduhan)
- [2. Instalasi](#2-instalasi)
  - [Pembaruan](#pembaruan)
  - [Dependensi](#dependensi)
  - [Alat opsional yang disarankan](#alat-opsional-yang-disarankan)
- [3. Penggunaan](#3-penggunaan)
  - [Mode interaktif (TUI)](#mode-interaktif-tui)
  - [Bahasa antarmuka](#bahasa-antarmuka)
  - [Alur umum](#alur-umum)
    - [Pintasan keyboard (antarmuka interaktif)](#pintasan-keyboard-antarmuka-interaktif)
    - [Panduan bantuan (tombol `F1`/`a`)](#panduan-bantuan-tombol-f1a)
    - [Kontak dan dukungan (panduan bantuan)](#kontak-dan-dukungan-panduan-bantuan)
    - [Menu utama (antarmuka interaktif)](#menu-utama-antarmuka-interaktif)
    - [Pengaturan aplikasi (tombol `o` atau palet perintah)](#pengaturan-aplikasi-tombol-o-atau-palet-perintah)
  - [Bantuan lengkap perintah](#bantuan-lengkap-perintah)
  - [Kode keluar penting](#kode-keluar-penting)
- [4. Kompatibilitas terminal](#4-kompatibilitas-terminal)
  - [Profil menurut emulator yang terdeteksi](#profil-menurut-emulator-yang-terdeteksi)
  - [Profil menurut ukuran terminal](#profil-menurut-ukuran-terminal)
- [5. Profil](#5-profil)
- [6. Arsitektur](#6-arsitektur)
- [6b. Mesin HTTP dan jumlah proses](#6b-mesin-http-dan-jumlah-proses)
- [7. Modul opsional](#7-modul-opsional)
  - [7a. Reverse proxy keluar — detail](#7a-reverse-proxy-keluar--detail)
- [8. Pengerasan HTTP (aktif secara bawaan)](#8-pengerasan-http-aktif-secara-bawaan)
- [9. TLS](#9-tls)
  - [9a. Sertifikat swatanda (minimal)](#9a-sertifikat-swatanda-minimal)
  - [9b. CA lokal](#9b-ca-lokal)
  - [9c. Let's Encrypt / ACME (Certbot) — publik, di-hosting sendiri](#9c-lets-encrypt--acme-certbot--publik-di-hosting-sendiri)
  - [9d. Perpanjangan otomatis (Certbot)](#9d-perpanjangan-otomatis-certbot)
- [10. Audit keamanan](#10-audit-keamanan)
- [11. Active Defense (deception + mode perang)](#11-active-defense-deception--mode-perang)
- [11b. Daftar jalur sensitif (WAF)](#11b-daftar-jalur-sensitif-waf)
- [11c. Batas laju per folder dan per IP/jaringan (WAF)](#11c-batas-laju-per-folder-dan-per-ipjaringan-waf)
- [11d. RIPOSTE (respons bertingkat dari waktu ke waktu)](#11d-riposte-respons-bertingkat-dari-waktu-ke-waktu)
- [11e. Intervensi manual (Keamanan Aktif)](#11e-intervensi-manual-keamanan-aktif)
- [12. Layanan dan operasi](#12-layanan-dan-operasi)
- [13. Log](#13-log)
  - [13a. Sumber jarak jauh (SSH)](#13a-sumber-jarak-jauh-ssh)
- [14. Pengujian](#14-pengujian)
- [15. Di luar cakupan](#15-di-luar-cakupan)

## 1. Visi dan cakupan

Prioritas yang dinyatakan adalah **kekokohan/keamanan inti HTTP terlebih dahulu** — WAF dan TLS adalah modul opsional yang ditempatkan di atasnya, tidak pernah menjadi prasyarat. Server yang melakukan berbagai hal (menyajikan berkas, mungkin juga PHP, reverse proxy...) tetapi melakukannya dengan benar, dengan pengerasan protokol yang benar-benar tidak dapat dilewati, lebih baik daripada server yang melakukan sangat banyak hal setengah-setengah.

### Yang dilakukan OMEGA-SERV

- Menyajikan konten statis (berkas, daftar direktori opsional, alias, pengalihan, penulisan ulang, cache) dengan resolusi jalur yang aman (traversal, pengodean ganda, tautan simbolik). Berkas besar dikirim per blok dari disk, tidak pernah dimuat ke memori; setiap berkas membawa `ETag` dan `Last-Modified` (muat ulang = respons 304 kosong), menerima permintaan parsial `Range` (melanjutkan unduhan, video); gambar, media, font, CSS, dan JS menerima `Cache-Control` bawaan yang dapat diubah di layar Cache. Berkas teks yang sudah dikompresi: jika `site.css.br` atau `site.css.gz` ada di samping `site.css` (dibuat dengan `brotli -k site.css` atau `gzip -k site.css`) dan peramban menerimanya, berkas itu yang dikirim, tidak pernah versi yang lebih lama dari aslinya.
- Mengeraskan protokol HTTP secara bawaan: analisis permintaan yang ketat, tanpa opsi untuk menonaktifkannya (penolakan ambiguitas `Content-Length`/`Transfer-Encoding`), daftar metode yang diizinkan secara eksplisit, validasi header `Host`, header keamanan dan CSP dasar pada respons situs dan halaman galatnya.
- Secara opsional: penyaringan WAF (tanda tangan, pembatasan laju, daftar blokir), TLS langsung (sertifikat swatanda, ditandatangani CA lokal, atau publik melalui Let's Encrypt/Certbot dengan perpanjangan otomatis), autentikasi HTTP Basic per zona, PHP melalui FastCGI/PHP-FPM, zona unggahan yang terkurung.
- Beberapa proses server, paling banyak satu per inti fisik mesin dengan mesin Python (layar Ketahanan dan batas); penghitung keamanan (rate limit, residivisme) dibagi di antara proses dan tetap akurat.
- Mengaudit konfigurasinya sendiri (`audit security`) dan memasang dirinya sebagai layanan sistem (systemd/OpenRC/runit).
- CLI non-interaktif yang dapat ditulis skrip dari awal hingga akhir, **dan antarmuka interaktif (Textual)** yang membungkus kasus penggunaan yang persis sama. Antarmuka **sepenuhnya dapat dikendalikan dengan tetikus dan/atau papan ketik**: registri kapabilitas, profil/opsi, konfigurasi terperinci (alias/pengalihan/rewrite/FastCGI/dirlisting/autentikasi/cache/WAF/proxy tepercaya/reverse proxy keluar/TLS), pengelolaan log (Pustaka/Favorit, 3 penampil — sederhana/klasik/lnav gabungan —, Lihat dan tangani IP, sumber jarak jauh SSH, rotasi/cadangan/otomatisasi/pemulihan/pembersihan/ekspor), layanan sistem, multi-instans (registri, pembuatan), pemeriksaan/simulasi/audit, pencadangan/pemulihan konfigurasi, asisten peluncuran pertama, pengaturan aplikasi (tema, profil tampilan, jalur ekspor/tangkapan layar), panduan bantuan kontekstual (lembar per layar dengan contoh konkret, FAQ, ekspor HTML, cakupan lengkap yang diverifikasi oleh pengujian), penunjukan sistematis muat ulang/mulai ulang setelah setiap penyimpanan, konfigurasi Active Defense lengkap tanpa mengedit berkas secara manual.

### Yang tidak dilakukan OMEGA-SERV

- CGI mentah (tetapi FastCGI/PHP-FPM didukung).
- Autentikasi TLS timbal balik (mTLS), OCSP stapling (sedangkan ACME/Let's Encrypt melalui Certbot tersedia).
- Cache HTTP yang dibagi antarproses.
- Pemindaian/audit target jarak jauh (gunakan `omega-check`/`omega-scan`/`omega-deep` untuk itu — Omega-serv mengaudit dirinya sendiri, tidak pernah pihak ketiga).

### OMEGA-SERV dibandingkan dengan server web di pasaran

Lihat [Pengukuran & perbandingan](comparatif-serveurs-web.md)  
Perbandingan terukur antara: [Nginx](https://nginx.org/) · [Lighttpd](https://www.lighttpd.net/) · [Caddy](https://caddyserver.com/) · [Apache](https://www.apache.org) · [Traefik](https://traefik.io/) · [Omega-Serv](https://kraynux.snake-mackarel.ts.net/omega-serv/translation/id/)

### Peringatan penggunaan

Omega-serv **menolak berjalan sebagai root**. Tidak ada modul keamanan (WAF, TLS, autentikasi) yang aktif secara bawaan di profil mana pun yang disediakan, termasuk `hardened` — mengaktifkannya selalu merupakan tindakan eksplisit (`config enable-tls`, `option enable waf`...). Profil `hardened` sendiri merekomendasikan reverse proxy untuk paparan Internet yang sebenarnya, alih-alih menggantikannya.

### Prasyarat

- Python 3.10+
- `openssl` (berkas biner, bukan pustaka Python) untuk semua hal terkait sertifikat TLS — fungsi lainnya berjalan tanpanya.
- Mesin native (opsional, disertakan dalam bentuk terkompilasi untuk x86_64): glibc 2.38 atau lebih baru dan OpenSSL 3, dua pustaka sistem yang sudah dipakai Python. Jika tidak dapat dijalankan, `install.sh` mengompilasinya ulang di tempat bila cmake, kompiler C++20, dan header OpenSSL tersedia; jika tidak, omega-serv berjalan dengan mesin Python-nya.

### Unduhan

Arsip versi terbaru dan sidik jari SHA-256 dari setiap versi: [omega-serv-2.5.0.tar.gz](https://kraynux.snake-mackarel.ts.net/omega-serv/download/omega-serv-2.5.0.tar.gz) · [sha.txt](https://kraynux.snake-mackarel.ts.net/omega-serv/download/sha.txt)

```bash
wget https://kraynux.snake-mackarel.ts.net/omega-serv/download/omega-serv-2.5.0.tar.gz
wget https://kraynux.snake-mackarel.ts.net/omega-serv/download/sha.txt
sha256sum -c --ignore-missing sha.txt
```

[↑ Daftar isi](#daftar-isi)

## 2. Instalasi

> ⚠️ **Anda memperbarui instalasi yang sudah ada?** Perintah di bawah **diam-diam melewati ekstraksi** jika `omega-serv/` sudah ada (ia menganggap ini instalasi pertama yang terputus, bukan pembaruan) — Anda akan memasang ulang dependensi di atas **kode lama yang tidak berubah**, tanpa pesan galat sedikit pun. Gunakan bagian [Pembaruan](#pembaruan) di bawah sebagai gantinya.

```bash
[ -d omega-serv ] && echo "ℹ️ Sudah diekstrak di sini, langkah dilewati." || tar -xzf omega-serv-2.5.0.tar.gz
cd omega-serv/
chmod +x install.sh
./install.sh
```

`install.sh`:

1. Membuat lingkungan virtual `.venv` jika belum ada.
2. Memasang paket (`pip install -e .`) — **tanpa dependensi eksternal** untuk inti server.
3. Membuat `omega-serv.sh` dan `install.sh` dapat dieksekusi.
4. Memeriksa apakah mesin native yang disertakan dapat dijalankan di mesin ini, dan mengompilasinya ulang di tempat bila perlu dan bila memungkinkan — tanpa pernah menghambat instalasi.
5. Menambahkan alias `serv` ke `~/.bashrc` dan `~/.zshrc` (tanpa duplikat jika sudah ada).

### Pembaruan

Jika `omega-serv/` sudah ada (instalasi sebelumnya), **jangan pernah menjalankan `tar` dari dalam folder ini**: ia akan mencoba membuat `omega-serv/omega-serv/` bertingkat dan gagal. Berbeda dengan omega-fire, `install.sh` tidak pernah menyentuh izin folder (tidak ada langkah yang meminta `sudo`) — jadi tidak ada risiko folder dimiliki `root` di sini, ekstraksi langsung di atas instalasi yang ada aman.

```bash
# Dari folder INDUK omega-serv/ (jangan pernah dari dalamnya)
tar -xzf omega-serv-2.5.0.tar.gz
cd omega-serv/
./install.sh
```

Arsip ini sengaja mengecualikan seluruh status aktif (`var/db/`, `var/log/`, `var/backups/`, `secure/secrets/`, `secure/certificates/*.key`, `config/omega-serve.json`, **`webroot/` — situs yang benar-benar disajikan**...) — ekstraksi di atasnya tidak pernah menyentuh data, sertifikat, pengaturan, atau konten yang sedang disajikan, hanya kode aplikasi yang diganti. `install.sh` menggunakan kembali `.venv` yang ada dan hanya memasang ulang dependensi di atasnya.

Folder `var/` dan `secure/auth/` tidak ada di arsip, bahkan dalam keadaan kosong: ekstraksi di atasnya tidak lagi mengatur ulang izinnya (yang dibagi dengan akun layanan systemd) — tidak perlu lagi « Layanan → Perbaiki izin » setelah pembaruan. `install.sh` membuat folder-folder ini jika belum ada, tanpa pernah menyentuh yang sudah ada.

> ⚠️ **Jika sebuah layanan sedang aktif, langkah di atas belum cukup.** Langkah itu mengganti kode di disk, tetapi proses yang sedang berjalan tetap berjalan dengan kode lama yang dimuat di memori — setelahnya selalu diperlukan **mulai ulang penuh**:
> ```bash
> sudo systemctl restart <nama-layanan>
> ```
> **Jangan pernah hanya memuat ulang** (`systemctl reload`, atau layar SERVICE → *Muat ulang*): itu hanya membaca ulang beberapa opsi konfigurasi (aturan WAF, zona autentikasi...), **tidak pernah kode Python itu sendiri**. `systemctl status <nama-layanan>` yang menampilkan waktu mulai lebih lama dari pembaruan Anda memastikan bahwa ia masih berjalan dengan kode lama. Jika Anda selalu memperbarui dengan menimpa folder yang sama (kasus standar di atas), mulai ulang ini adalah satu-satunya langkah yang kurang — tidak perlu memasang ulang layanan. Sebuah pesan akan muncul di area notifikasi: cukup mulai ulang layanan dari menu « SERVICE ».

> ⚠️ **Jika layanan terus-menerus memulai ulang setelah itu** (`systemctl status` berganti-ganti active/inactive, `journalctl -u <nama-layanan>` menunjukkan `PermissionError` saat menulis berkas di bawah `var/`): ekstraksi `tar` memulihkan izin folder sesuai yang tersimpan di arsip, yang dapat menghapus pembagian izin yang dipasang untuk akun sistem khusus saat instalasi awal — meskipun `install.sh` sendiri tidak pernah menyentuhnya. Tidak perlu memasang ulang unit: layar SERVICE → **Perbaiki izin** (menerapkan ulang pembagian pada `var/` dan `secure/auth/`, tanpa menyentuh unit systemd).

### Dependensi

Inti server (pengurai HTTP/1.1, klien FastCGI, hash kata sandi melalui `hashlib.scrypt`) tetap Python murni/stdlib, dan semua yang terkait sertifikat TLS melewati biner `openssl` sebagai subproses alih-alih pustaka kripto Python — **tanpa dependensi eksternal untuk itu**. Hanya antarmuka interaktif yang menambah dependensi: `omega-lib` (tema, deteksi terminal — pustaka bersama rangkaian ini, tidak diterbitkan di PyPI, disertakan dalam arsip distribusi), `textual` dan `pyte` (emulasi terminal untuk menampilkan `lnav` gabungan di antarmuka), `jinja2` (ekspor HTML bertema) dan `psutil` (layar Status & Sumber Daya — CPU/RAM/disk/jaringan). Dependensi pengembangan/pengujian opsional (`pip install -e ".[test]"`): `hypothesis` (pengujian properti untuk pengurai HTTP dan resolver jalur, tidak pernah di produksi). Perkakas kualitas (`pip install -e ".[dev]"`): `pytest`, `ruff`, `mypy`, `import-linter`. Tambahan opsional lain (`pip install -e ".[magnet]"`): `lupa` (pengikatan Lua tertanam, wheel prakompilasi, tidak perlu interpreter `lua` sistem), hanya untuk skrip WAF pelengkap « magnet » — tidak pernah dipasang secara bawaan; ketiadaannya ditandai (kapabilitas `waf-magnet`, layar **Kapabilitas**) beserta perintah instalasi yang tepat, tanpa menghambat bagian server lainnya.

### Alat opsional yang disarankan

Antarmuka berjalan dalam mode terdegradasi jika alat-alat ini tidak ada:

- `openssl` — diperlukan untuk semua yang terkait sertifikat TLS (swatanda, CA lokal, impor); tanpanya, perintah `certs *` gagal tetapi bagian server lainnya tetap berjalan normal.
- `certbot` — hanya diperlukan untuk asisten **Let's Encrypt** dan perpanjangan otomatisnya; TLS swatanda/CA lokal tidak memerlukannya.
- `lnav` — analisis log tingkat lanjut yang digabungkan di layar **Pengelolaan log**; pesan galat yang jelas jika biner tidak ditemukan, tanpa crash, bagian layar lainnya (lihat/ikuti/rotasi/statistik) tetap berjalan normal tanpanya.
- `scp` (paket `openssh`/`openssh-clients`, hampir selalu sudah ada) — hanya diperlukan untuk **Sumber jarak jauh (SSH)**; tanpanya, pengambilan gagal dengan pesan yang jelas, bagian Pustaka lainnya tetap berjalan normal.
- `python-psutil` (paket sistem setara `psutil` dari PyPI) — selalu dipasang otomatis oleh `pip install -e .` (dependensi wajib paket, layar **Status & Sumber Daya** selalu memerlukannya), tetapi memasangnya lebih dulu melalui pengelola paket sistem membuat `pip` tidak perlu mengompilasi wheel-nya sendiri.
- `cmake`, kompiler C++20 (`g++`), header OpenSSL 3, dan PCRE2 — hanya diperlukan jika mesin native bawaan tidak bisa berjalan (glibc lebih lama dari 2.38): `install.sh` lalu mengompilasinya ulang di mesin tersebut. Tanpa PCRE2, mesin hasil kompilasi akan membuat Python memeriksa setiap permintaan saat WAF aktif (lebih lambat); tanpa alat-alat ini, omega-serv tetap memakai mesin Python.
- Font emoji (Noto Color Emoji) — opsional, untuk ikon penampil Sederhana (Pengelolaan log); tanpanya beberapa ikon tampil sebagai kotak, selebihnya tidak terpengaruh. Nerd Font tidak berisi emoji ini.

```bash
# Arch Linux dan turunannya
sudo pacman -S openssl certbot lnav python-psutil openssh

# Debian/Ubuntu dan turunannya
sudo apt install openssl certbot lnav python3-psutil openssh-client

# Fedora
sudo dnf install openssl certbot lnav python3-psutil openssh-clients

# Kompilasi lokal mesin native (hanya jika glibc < 2.38)
sudo pacman -S cmake gcc openssl pcre2                     # Arch
sudo apt install cmake g++ libssl-dev libpcre2-dev         # Debian/Ubuntu
sudo dnf install cmake gcc-c++ openssl-devel pcre2-devel   # Fedora

# Ikon penampil Sederhana (font emoji, opsional)
sudo pacman -S noto-fonts-emoji                            # Arch
sudo apt install fonts-noto-color-emoji                    # Debian/Ubuntu
sudo dnf install google-noto-color-emoji-fonts             # Fedora
```

[↑ Daftar isi](#daftar-isi)

## 3. Penggunaan

Dua antarmuka yang setara sepenuhnya secara fungsional, tanpa logika yang digandakan di antara keduanya: CLI non-interaktif (dapat ditulis skrip, dipakai di bawah) dan antarmuka interaktif Textual (menu, formulir, tabel) — setiap tindakan di salah satunya ada di sisi CLI, antarmuka hanya membungkus kasus penggunaan yang sama.

### Mode interaktif (TUI)

Disarankan untuk penggunaan sehari-hari — dijalankan tanpa argumen:

```bash
./omega-serv.sh
```
jika Anda sudah membuat alias, cukup ketik `serv` di terminal:
```bash
serv
```

### Bahasa antarmuka

17 bahasa: Prancis, Inggris, Spanyol, Portugis (Brasil), Italia, Jerman, Belanda, Polandia, Rusia, Tionghoa, Vietnam, Thai, Indonesia, Jepang, Korea, Hindi, Arab. Dipilih di Pengaturan (tombol `o`, « Langue / Language », label yang tidak pernah diterjemahkan), atau sesekali dengan `OMEGA_SERV_LANG=en serv`. Di konsol teks Linux (TTY), bahasa yang aksaranya tidak ada di font konsol (Vietnam, Tionghoa, Thai, Jepang, Korea, Hindi, Arab) ditampilkan dalam bahasa Inggris untuk sesi tersebut. Untuk bahasa Hindi, terminal yang menyusun sendiri huruf bersambung (Kitty, Ghostty, Konsole) menggeser bingkai dan kolom, bervariasi menurut font: peringatan ditampilkan saat mulai; Terminator, GNOME Terminal, Xfce Terminal, dan Alacritty menampilkan Hindi dengan rata. Dua pengaturan terpisah: **bahasa halaman pengunjung** (halaman kesalahan, daftar folder — layar Halaman kesalahan, bawaan bahasa Prancis) dan **bahasa ekspor** (HTML dan laporan insiden — Pengaturan, bawaan « Sama dengan antarmuka »). Log server (`journalctl`) tetap dalam bahasa Prancis.

### Alur umum

Layar pembuka (splash, tertutup dengan satu tombol atau klik) → menu utama (Asisten peluncuran pertama / Registri kapabilitas / Profil / Konfigurasi terperinci / Keamanan Aktif / Pengelolaan log / Layanan / Multi-instans / Status & Sumber Daya / Audit / Cadangan) → pilih bagian lalu tindakan, setiap formulir memvalidasi kolom wajibnya sebelum melanjutkan → konfirmasi eksplisit sebelum setiap operasi sensitif atau destruktif (mulai ulang, penghapusan, pemulihan...) → penunjukan sistematis langkah berikutnya (muat ulang panas otomatis, atau konfirmasi mulai ulang penuh) setelah setiap penyimpanan yang mengubah konfigurasi yang sedang disajikan. Adaptasi terhadap terminal (warna, ukuran, degradasi struktural profil tampilan) bersifat otomatis tanpa flag manual.

#### Pintasan keyboard (antarmuka interaktif)

| Tombol | Tindakan |
|---|---|
| `↑` / `↓` | Berpindah antarelemen layar |
| `Tab` / `Shift+Tab` | Berpindah antarkolom formulir |
| `Esc` | Kembali ke layar sebelumnya (konfirmasi keluar di beranda) |
| `t` | Tema berikutnya (langsung diterapkan, tanpa konfirmasi) |
| `r` | Segarkan deteksi terminal |
| `F1` | Bantuan layar aktif (lembar kontekstual — lihat "Panduan bantuan" di bawah) |
| `a` | Panduan bantuan lengkap (menu yang dapat dijelajahi + FAQ) |
| `o` | Pengaturan aplikasi (tema, profil tampilan, jalur ekspor/tangkapan layar — lihat di bawah) |
| `q` | Keluar (dengan konfirmasi) |
| `Ctrl+P` | Palet perintah (Tema, Tangkapan layar, Opsi...) |

> **Pengecualian — editor daftar (WAF → Custom)**: tidak ada pintasan, semuanya dengan tetikus; keyboard hanya untuk mengetik (karakter, Enter, panah, Home/End, Page Up/Down, Backspace, Delete). `Esc`, `F1`, dan `Ctrl+P` tidak aktif di sana (tombol **Bantuan**); hanya `Ctrl+Q` yang tetap aktif, dengan konfirmasi jika ada perubahan yang belum disimpan.

#### Panduan bantuan (tombol `F1`/`a`)

Sistem bantuan terintegrasi, tidak pernah sekadar teks statis: setiap layar yang terdokumentasi (lembar definisi/kolom yang diisi dengan contoh konkret/tindakan yang dipicu/reaksi — muat ulang, mulai ulang, atau tidak ada) dapat diakses langsung darinya melalui `F1`; tombol `a` membuka menu lengkap (struktur pohon yang identik dengan navigasi nyata aplikasi) dengan akses ke FAQ (jebakan yang ditemui dalam penggunaan nyata, misalnya kelas serangan Active Defense, izin layanan bersama) dan ekspor HTML mandiri (tema aktif dipertahankan) dari seluruh panduan. Ada layar referensi umum sebagai cadangan selama lembar spesifik belum ada — cakupan saat ini lengkap, diverifikasi oleh pengujian.

#### Kontak dan dukungan (panduan bantuan)

Panduan bantuan (tombol `a`) menyediakan layar **Kontak dan dukungan**: *Traktir kopi* (halaman PayPal pengembang), *Hubungi dukungan* (formulir kontak situs, alamat surel ditampilkan) dan *Daftarkan saya sebagai pengguna (anonim)*. Pendaftaran bersifat sukarela dan nonaktif secara bawaan: hanya untuk menghitung pengguna dan, jika mau, benua atau negara mereka (daftar tertutup, tanpa teks bebas). Yang dikirim adalah kunci acak, versi omega-serv, dan mode yang dipilih (*sekali* atau *setiap hari*, yang terakhir memungkinkan penghitungan instalasi aktif); tidak pernah nama, nama mesin, isi, atau log. Pengiriman harian berjalan di proses terpisah dan tidak pernah memperlambat server. Alamat IP tidak dicatat dalam pendaftaran, tetapi seperti setiap kunjungan, alamat itu melewati pemeriksaan keamanan dan log server penerima. Dapat ditarik kapan saja dari layar yang sama atau dengan `omega-serv declaration withdraw`; `DO_NOT_TRACK=1` menghentikan semua pengiriman otomatis.

#### Menu utama (antarmuka interaktif)

- **Asisten peluncuran pertama** — alur terpandu 8 langkah (sambutan → kapabilitas hanya-baca → pilihan profil → bind/port → TLS opsional → pemeriksaan → ringkasan + penulisan → tawaran pemasangan layanan); memungkinkan membuat konfigurasi lengkap dan menjalankan server tanpa mengenal CLI.
- **Registri kapabilitas** — penyelidikan sistem hanya-baca (sistem init, apakah port yang dikonfigurasi sudah dipakai, ada/tidaknya `openssl`/`logrotate`/`tailscale`/`lnav`, ruang disk, batas deskriptor berkas...), ekspor JSON/HTML.
- **Profil** — kasus penggunaan yang sama dengan `profile` di CLI, diff selalu ditampilkan sebelum penulisan.
- **Konfigurasi terperinci server** — CRUD lengkap untuk alias/pengalihan/rewrite/dirlisting/proxy tepercaya/reverse proxy keluar/FastCGI/cache/autentikasi/kontrol akses/halaman kesalahan, ditambah submenu **TLS** (status, pembuatan swatanda, asisten CA lokal, asisten Let's Encrypt/Certbot, perpanjangan otomatis, pencabutan, aktifkan/nonaktifkan); bingkai kedua **OPSI DAN PEMERIKSAAN** mengelompokkan pintasan ke **Opsi** (`option` di CLI) dan **Periksa konfigurasi** (`config check` di CLI) — alur yang sama seperti menyesuaikan pengaturan lalu memeriksa, kedua layar ini tidak lagi dapat diakses langsung dari menu utama. WAF tidak lagi berada di sini (lihat "Keamanan Aktif" di bawah): ia terutama menampilkan status operasional yang terus berubah, bukan formulir konfigurasi statis sederhana. Setiap penyimpanan selalu menyebutkan langkah berikutnya: muat ulang panas otomatis dan senyap jika ada layanan aktif (dirlisting, akses, alias/pengalihan/rewrite, cache, halaman kesalahan, proxy tepercaya, zona reverse proxy/FastCGI, pengguna/zona autentikasi), atau konfirmasi eksplisit mulai ulang penuh ketika perubahan menyentuh soket pendengar, TLS, atau Active Defense — tidak ada lagi layar yang membuat Anda menebak apakah server harus dijalankan ulang.
- **Keamanan Aktif** — layar tunggal yang mengelompokkan tiga blok berdampingan, sesuai urutan sebuah serangan: **WAF**, **Active Defense**, dan **RIPOSTE** (respons bertingkat dari waktu ke waktu). **Active Defense** (Status, Ancaman yang dilacak dengan skor/tingkat, Insiden dengan kronologi/ekspor IoC/laporan, penugasan Deception, Simulasikan keputusan dalam dry-run, **Pengaturan** — konfigurasi lengkap tanpa pernah mengedit `config/omega-serve.json` secara manual) dan **WAF** (Status, Modul — mode/paket aturan/daftar blokir, Uji permintaan, Custom — penulis aturan khusus dan pemuatan daftar jalur/kata kunci yang dapat diedit dengan tetikus, Magnet — impor skrip `mod_magnet` eksternal dengan pemeriksaan kompatibilitas sebelum aktivasi). Di bawah tiga blok, **INTERVENSI MANUAL**: memblokir atau membuka blokir alamat IP secara manual, status semua blokir.
- **Pengelolaan log** — menu dua kolom. Kolom **Pustaka**: pusat yang merujuk setiap log yang perlu ditangani (penambahan manual, satu klik langsung menambahkan log milik instans — access/error/WAF bawaan, + skrip magnet jika aktif —, atau **sumber jarak jauh** yang diambil melalui SSH, lihat di bawah); **Favorit** (kombinasi log + penampil yang disimpan dengan sebuah nama, dibuka langsung); **Lihat log** dengan 3 penampil pilihan menurut jumlah log yang dipilih — Sederhana (tail langsung + statistik umum IP/galat/kode HTTP pada format apa pun), Klasik (baca + ikuti), `lnav` gabungan (tampilan terminal nyata di antarmuka, log magnet otomatis disertakan + jalur manual yang **disematkan** agar tetap tersimpan antarsesi); **Lihat dan tangani IP** (IP teratas pada satu atau beberapa log pilihan, periode 24 jam/7 hari/30 hari/semua, penghapusan IP). Kolom **Pemeliharaan** (tidak berubah): rotasi/pengarsipan manual atau otomatis berdasarkan ambang ukuran, pembuatan cadangan seketika, konfigurasi/pengelolaan otomatisasi terjadwal (deklaratif — lihat catatan di bawah), pulihkan/bersihkan arsip, ekspor daftar.
- **Layanan** — tindakan yang sama dengan `service` di CLI, elevasi `sudo` sesekali per tindakan, tidak pernah seluruh aplikasi dijalankan sebagai root.
- **Multi-instans** — registri global (`~/.config/omega-serv/instances.json`, di luar direktori proyek mana pun) dari instalasi yang dikenal di mesin, dengan status systemd masing-masing; pembuatan instans baru (salinan pohon direktori, lingkungan virtual dan dependensi tersendiri, konfigurasi baru dengan port berbeda, pemeriksaan tidak bertingkat dan tidak ada konflik port) langsung dari antarmuka. Tombol ini praktis tak terlihat untuk satu instalasi (label "Multi-instans" menjadi "Instances (N)" begitu 2 instans dikenal); peralihan penuh ke instans lain (`os.execv`, konfirmasi eksplisit, splash khusus yang mengumumkan peralihan saat mulai ulang); pencopotan lengkap sebuah instans (penghapusan unit, akun sistem khusus jika tidak lagi dipakai instans lain, dan penghapusan direktori secara opsional, tidak pernah secara bawaan).
- **Status & Sumber Daya** — ringkasan sekilas, disegarkan setiap 2 detik: status server (proses/PID, status layanan sistem, profil/opsi aktif/TLS/port), aliran log akses langsung (laju, distribusi per kode status, IP unik, tingkat galat), sumber daya sistem (CPU/RAM/disk/swap/beban/jaringan, melalui `psutil`); juga mengelompokkan pintasan **Simulasikan permintaan** (kasus penggunaan yang sama dengan perintah CLI terkait).
- **Audit keamanan** — kasus penggunaan yang sama dengan perintah CLI terkait.
- **Cadangan konfigurasi** — arsip tar.gz dari berkas konfigurasi dan, atas pilihan eksplisit, aturan WAF/zona autentikasi/sertifikat (konfirmasi wajib begitu rahasia nyata disertakan)/basis data Active Defense, pemulihan, daftar, penghapusan.

> Catatan tentang otomatisasi rotasi terjadwal: otomatisasi ini disimpan (frekuensi + log sasaran) tetapi **tidak ada yang menjalankannya secara otomatis** — baik di sisi antarmuka maupun sebagai tugas latar belakang. Ini pilihan yang disengaja demi keselarasan dengan layar setara di `omega-fire`, yang berperilaku deklaratif yang sama. Eksekusi berkala yang nyata (timer systemd, tugas latar belakang) akan dibangun terpisah jika kebutuhannya terkonfirmasi.

#### Pengaturan aplikasi (tombol `o` atau palet perintah)

Hanya preferensi antarmuka — tidak pernah dicampur dengan `config/omega-serve.json` (konfigurasi server): tema aktif, profil tampilan (`complete`/`standard`/`reduced`/`mono`, perlu mulai ulang), jalur ekspor (bawaan `var/exports/`), jalur tangkapan layar (bawaan `var/screenshots/`), pembersihan salah satu folder tersebut (konfirmasi wajib).

```bash
# Menjalankan server (latar depan, SIGTERM = berhenti rapi dengan masa tenggang, SIGHUP = muat ulang panas WAF/Auth)
./omega-serv.sh serve

# Konfigurasi
./omega-serv.sh config init                # membuat config/omega-serve.json (nilai aman bawaan)
./omega-serv.sh config check                # memeriksa tanpa memulai (gerbang pemblokir yang sama seperti saat mulai)
./omega-serv.sh config show
./omega-serv.sh config enable-tls --cert ... --key ... --mode direct
./omega-serv.sh config disable-tls

# Profil (minimal / standard / hardened / development)
./omega-serv.sh profile list
./omega-serv.sh profile show hardened
./omega-serv.sh profile apply hardened --dry-run   # selalu lihat diff sebelum menerapkan

# Opsi (aliases, redirects, rewrites, dirlisting, cache, waf, upload, fastcgi, reverse_proxy...)
./omega-serv.sh option list
./omega-serv.sh option enable waf
./omega-serv.sh option disable waf

# Simulasikan permintaan tanpa menjalankan server (berguna untuk memvalidasi aturan sebelum diaktifkan)
./omega-serv.sh simulate-request --method GET --url /index.html

# WAF (berfungsi meski opsi dinonaktifkan, melalui --force implisit)
./omega-serv.sh waf test --method GET --path /admin --remote-ip 203.0.113.1
./omega-serv.sh blocklist list
./omega-serv.sh blocklist add --network 203.0.113.0/24 --reason "scan detecte" --duration-seconds 3600
./omega-serv.sh blocklist remove --network 203.0.113.0/24

# Active Defense (deception + mode perang, opsi "active_defense")
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

# RIPOSTE (respons bertingkat dari waktu ke waktu, opsi "riposte")
./omega-serv.sh riposte status
./omega-serv.sh riposte simulate --ip 203.0.113.7 --class scan --returns 3
./omega-serv.sh riposte actions list
./omega-serv.sh riposte stop

# Sertifikat TLS - swatanda (9a)
./omega-serv.sh certs generate-self-signed --cn localhost --san-dns localhost --san-ip 127.0.0.1
./omega-serv.sh certs show
./omega-serv.sh certs check-expiry --warn-days 30

# Sertifikat TLS - CA lokal (9b)
./omega-serv.sh certs generate-ca --cn "Mon CA locale" --days 3650
./omega-serv.sh certs generate-csr --cn serveur.local --san-dns serveur.local --key-out server.key --csr-out server.csr
./omega-serv.sh certs sign-csr --csr server.csr --ca-key secure/certificates/ca/root-ca.key --ca-cert secure/certificates/ca/root-ca.pem --out server.pem --fullchain-out fullchain.pem
./omega-serv.sh certs revoke --cert server.pem --ca-key secure/certificates/ca/root-ca.key --ca-cert secure/certificates/ca/root-ca.pem

# Sertifikat TLS - impor (9c, mis. dari hook Certbot)
./omega-serv.sh certs import --key privkey.pem --cert fullchain.pem

# Autentikasi HTTP Basic
./omega-serv.sh auth add-user --username alice
./omega-serv.sh auth create-zone --path-prefix /admin/ --realm "Administration" --allowed-users alice
./omega-serv.sh auth list

# Audit keamanan (tidak pernah memblokir, bersifat informatif)
./omega-serv.sh audit security --format text --min-severity medium

# Cadangan konfigurasi (konfigurasi selalu disertakan; rahasia nyata
# tidak pernah dienkripsi secara bawaan, --confirm-secrets wajib untuk menyertakannya)
./omega-serv.sh config backup --description "avant migration"
./omega-serv.sh config backup --include-auth --include-certificates --confirm-secrets
./omega-serv.sh config backup --include-active-defense --description "menaces/incidents"
./omega-serv.sh config list-backups
./omega-serv.sh config restore --snapshot-id snapshot_20260908_170003_762484

# Layanan sistem (systemd/OpenRC/runit, deteksi otomatis)
./omega-serv.sh service install --user omega-serv --group omega-serv
./omega-serv.sh service start
./omega-serv.sh service status
```

### Bantuan lengkap perintah

Perintah di atas hanyalah contoh. Untuk semua perintah dan opsinya:

```bash
./omega-serv.sh help                    # pohon perintah lengkap
./omega-serv.sh help riposte            # satu cabang saja
./omega-serv.sh riposte actions --help  # detail sebuah perintah
man omega-serv                          # halaman manual (dipasang oleh install.sh)
```

Referensi lengkap: [docs/HELP.md](../../HELP.md).

### Kode keluar penting

| Perintah | Kode | Arti |
|---|---:|---|
| `audit security` | `0` | Tidak ada yang serius (tidak ada `CRITICAL`/`HIGH`) |
| `audit security` | `1` | Setidaknya satu temuan `CRITICAL` |
| `audit security` | `2` | Setidaknya satu `HIGH` tanpa `CRITICAL` |
| `audit security` | `3` | Galat eksekusi (konfigurasi tidak ditemukan...) |
| `certs check-expiry` | `1` | Sertifikat kedaluwarsa |
| perintah lainnya | `0`/`1` | Berhasil / validasi gagal |

[↑ Daftar isi](#daftar-isi)

## 4. Kompatibilitas terminal

Antarmuka interaktif ([Textual](https://textual.textualize.io/) yang dibangun di atas [Rich](https://rich.readthedocs.io/)) secara otomatis mendeteksi kapabilitas terminal (emulator, ukuran) dan menyesuaikan lembar gaya strukturalnya (`complete`/`standard`/`reduced`/`mono`), tanpa flag manual. Mode CLI selalu berupa teks biasa, tidak bergantung pada terminal. Kebijakan ini dipakai bersama oleh seluruh rangkaian `omega-` (`omega-lib`, `terminal/policies.py`) — identik dengan milik `omega-check`/`omega-fire`.

### Profil menurut emulator yang terdeteksi

| Emulator | Profil awal |
|---|---|
| Ghostty, Alacritty, WezTerm, Kitty | `complete` |
| Konsole, GNOME Terminal, Terminator, Xfce4 Terminal | `standard` |
| xterm, urxvt, SSH modern | `reduced` |
| TTY Linux, SSH lama | `mono` |
| Emulator tidak dikenal | `reduced` (cadangan bawaan) |

### Profil menurut ukuran terminal

| Ukuran minimum (kolom × baris) | Batas atas profil |
|---|---|
| 120 × 32 | `complete` |
| 100 × 28 | `standard` |
| 80 × 24 | `reduced` |
| di bawahnya | `mono` |

Profil akhir yang dipilih adalah **yang paling ketat dari keduanya** (emulator dan ukuran) — Ghostty layar penuh yang diperkecil menjadi 70 kolom turun ke `mono`, meskipun emulatornya mengizinkan `complete`. Dapat disegarkan langsung dengan tombol `r`, atau ditimpa secara manual dari Pengaturan aplikasi (tombol `o`).

[↑ Daftar isi](#daftar-isi)

## 5. Profil

| Profil | Tujuan penggunaan |
|---|---|
| `minimal` | Demonstrasi/lokal sederhana: hanya statis, tidak ada opsi yang aktif |
| `standard` | Situs statis atau produksi kecil: header umum, CSP dasar, dirlisting/CGI/FastCGI dinonaktifkan |
| `hardened` | Paparan dengan hak akses minimum: bind lokal secara bawaan (reverse proxy disarankan untuk Internet), metode dibatasi GET/HEAD, CSP ketat, anti-slowloris — WAF **tidak pernah** diaktifkan otomatis, bahkan di sini |
| `development` | Hanya untuk pengembangan lokal, tidak pernah disajikan sebagai cocok untuk Internet: bind loopback wajib, CSP report-only, halaman kesalahan terperinci |

Urutan penggabungan konfigurasi: nilai aman bawaan → profil terpilih → opsi yang sedang aktif dipertahankan (bertahan saat profil diganti) → lapisan eksplisit pengguna. Diff lengkap selalu ditampilkan sebelum penulisan (`profile apply`).

[↑ Daftar isi](#daftar-isi)

## 6. Arsitektur

Clean Architecture (`core / domain / ports / application / infrastructure / interfaces / bootstrap`) — `bootstrap/` adalah akar komposisi (setara dengan `app/` di alat lain dalam rangkaian). Kekhasan proyek ini yang disengaja, diverifikasi oleh `import-linter` alih-alih diasumsikan: `application/server/start_server.py` (serta `validate_config.py`, `run_audit.py`) berperan sebagai **pabrik perakitan yang bergantung pada konfigurasi nyata** (pengelola layanan mana, aktifkan WAF atau tidak...) dan langsung membuat instans adaptor `infrastructure/` konkret — berbeda dengan pola yang lebih ketat di CHECK/TRACK, tempat `application/` hanya memakai `ports/`. Satu-satunya aturan universal yang benar-benar diberlakukan: `domain/`/`core/` tidak pernah bergantung pada lapisan luar.

```text
src/omega_serv/
├── core/            Kosakata lintas lapisan (platform_info, konstanta)
├── domain/           Logika bisnis murni (HTTP, konfigurasi, keamanan WAF/TLS/auth/audit, perutean)
├── ports/            Kontrak (Protocol) yang dibutuhkan aplikasi
├── application/      Kasus penggunaan - beberapa fungsi (build_server...) juga merakit adaptor konkret (lihat di atas)
├── infrastructure/    Implementasi nyata (asyncio, openssl lewat subprocess, systemd/OpenRC/runit, berkas)
├── interfaces/cli/    CLI argparse non-interaktif
├── interfaces/tui/    Antarmuka interaktif Textual (kasus penggunaan sama, tanpa logika ganda)
└── bootstrap/         DependencyContainer, resolusi akar proyek
```

Aturan yang diverifikasi oleh `import-linter` (8 kontrak): `domain`/`core` tidak pernah bergantung pada lapisan luar; `interfaces.tui` tidak pernah langsung bergantung pada `infrastructure`; `textual` terkurung di `interfaces.tui`; `subprocess` terkurung di `infrastructure/process/subprocess_runner.py` (dan `infrastructure/lnav/`, aliran PTY interaktif); `ssl` terkurung di `infrastructure/tls/ssl_context_builder.py`; `jinja2` terkurung di `infrastructure/exporters/html_exporter.py`; `sqlite3` terkurung di `infrastructure/persistence/sqlite_active_defense_connection.py` (satu-satunya penyimpanan relasional proyek, khusus untuk Active Defense); `lupa` terkurung di `infrastructure/waf/lua_waf_adapter.py` (skrip WAF pelengkap « magnet »).

[↑ Daftar isi](#daftar-isi)

## 6b. Mesin HTTP dan jumlah proses

Dua mesin dapat melayani permintaan. Dengan **mesin Python**, bawaan, interpreter Python menangani semua permintaan. **Mesin native** (C++, `bin/omega-http-core`) membaca, menganalisis, dan melayani permintaan sendiri; server Python tetap memegang konfigurasi, pemantauan, dan keputusan keamanan.

- **Dua pengaturan**: mesin (layar **Konfigurasi dasar**) dan jumlah proses (layar **Ketahanan dan batas**). Jumlah proses dibatasi menurut mesin dan prosesor yang terdeteksi: dengan mesin Python, hingga satu per inti fisik; dengan mesin native, yang sudah memakai semua inti, itu adalah proses pemeriksaan keamanan, 1, atau 2 mulai dari 4 inti fisik. Layar menunjukkan apa yang diberikan oleh penambahan pada mesin dan menolak nilai yang terlalu besar; yang berjalan ditampilkan apa adanya (“mesin native, 1 proses”). Mengganti mesin atau jumlah proses memerlukan mulai ulang penuh. Apa yang diubah oleh pilihan, diukur: FAQ panduan dan [perbandingan server web](comparatif-serveurs-web.md).
- **Respons sama, log sama**: dengan mesin native, konten statis, pengalihan, penulisan ulang, alias, cache, halaman galat, dan header keamanan dilayani oleh mesin native; ia memeriksa sendiri aturan WAF dan melayani sendiri permintaan yang tidak cocok dengan aturan mana pun, dan setiap permintaan lain (kecocokan atau keraguan WAF, Active Defense, autentikasi) melewati proses Python yang menerapkan pemeriksaan yang persis sama dan menulis log keamanan yang sama (RIPOSTE dan omega-jail tidak melihat perbedaan apa pun); daftar direktori dan halaman internal diminta dari Python; reverse proxy, FastCGI, pengiriman berkas, dan WebSocket diserahkan kepadanya untuk seluruh koneksi. TLS langsung ditangani mesin native dengan pustaka yang sama dan pengaturan yang sama.
- **Tidak pernah campuran**: satu aturan menentukan mesin yang berlaku dan semua tempat menampilkannya (layar **Status & Sumber Daya**, `omega-serv engine status`). Jika mesin native tidak dapat melayani semuanya (TLS langsung bersama reverse proxy, FastCGI, atau pengiriman berkas) atau tidak dapat dijalankan, mesin Python yang melayani, dan alasannya ditampilkan. Di **Konfigurasi dasar**, pilihan mesin native berwarna abu-abu selama ada fungsi aktif yang menghalanginya, beserta apa yang harus diubah agar memungkinkan; pengaturan yang disimpan di tempat lain yang akan membuat mesin native hilang meminta konfirmasi lebih dulu.
- **Jika pemeriksaan Python tidak menjawab**, `waf.on_internal_error` yang memutuskan: melayani tanpa pemeriksaan atau menolak (503). Zona autentikasi selalu ditolak dalam hal ini, dan alamat yang sudah diblokir tetap ditolak (451).

[↑ Daftar isi](#daftar-isi)

## 7. Modul opsional

Semuanya dinonaktifkan secara bawaan di semua profil yang disediakan — aktivasi selalu eksplisit (`option enable <nama>` atau `config enable-tls`):

| Modul | Peran |
|---|---|
| `waf` | Tanda tangan (jalur sensitif, UA/Referer pemindai, SQLi/XSS/CMDi di badan permintaan), daftar yang dapat diedit sebagai berkas teks (kata kunci, atau jalur sensitif dengan pengecualian `!`, mode Pengamatan dan residivisme khusus per daftar — dua daftar referensi disediakan, dimuat secara eksplisit), pembatasan laju (token bucket, aturan per folder dan per IP/jaringan), daftar blokir (CIDR + kedaluwarsa), reputasi/eskalasi, impor skrip WAF `mod_magnet` Lighttpd yang sudah ada sebagai penguat opsional tipe « magnet » (tanpa menulis ulang, tambahan `pip install -e ".[magnet]"` — aditif, tidak pernah dapat mencabut blokir bawaan; pemeriksaan kompatibilitas saat impor, layar TUI khusus) — mode `log-only` secara struktural tidak mampu memblokir |
| TLS | Langsung (swatanda, CA lokal, atau publik melalui Let's Encrypt/Certbot dengan perpanjangan otomatis), tidak pernah mTLS/OCSP di V1 |
| Autentikasi | HTTP Basic per zona (`url_prefix`), `hashlib.scrypt` dengan pertahanan anti-timing (waktu konstan bahkan untuk pengguna yang tidak dikenal) |
| FastCGI/PHP-FPM | Hanya satu `(url_prefix, script_root)`, `script_root` terkurung di luar `webroot/` secara desain (penangan statis tidak pernah dapat membocorkan sumber PHP) |
| Reverse proxy keluar | Omega-serv sendiri bertindak sebagai proxy ke satu atau beberapa backend (arah kebalikan dari `server.tls.mode = "behind_proxy"`) — penyeimbangan beban (round-robin, berbobot, least-connections, ip-hash, least-response-time, beban nyata), afinitas sesi dan aturan perutean berdasarkan header, kesehatan pasif dan aktif, cache respons (multivarian `Vary`), backpressure, perlindungan anti-loop, API administrasi panas |
| Unggahan | Zona terkurung, kuota per zona, nama berkas dibuat di sisi server — tanpa streaming di V1 (dibatasi oleh `server.max_request_size`) |
| `active_defense` | Deception + mode perang dari sinyal WAF yang sudah dihitung (tidak pernah skor kedua): umpan statis, perlambatan/pencatatan diperkaya/pembatasan laju yang terarah, insiden + ekspor IoC |
| `riposte` | Respons bertingkat dari waktu ke waktu: ingatan residivis per alamat, blokir yang makin lama (blocklist WAF, blokir jaringan melalui omega-jail) atau umpan diperpanjang, pencabutan dan henti darurat — proses terpisah |

### 7a. Reverse proxy keluar — detail

OMEGA-SERV dapat sendiri bertindak sebagai reverse proxy ke satu atau beberapa backend HTTP/HTTPS — jangan pernah disamakan dengan `server.tls.mode = "behind_proxy"` (OMEGA-SERV **di belakang** sebuah proxy, mekanisme kebalikannya). Zona dapat dikonfigurasi dengan CRUD lengkap (TUI: *Konfigurasi terperinci → Reverse Proxy*), satu atau beberapa upstream per zona.

- **Penyeimbangan beban** — `round_robin` (bawaan), `weighted_round_robin`/`weighted_least_connections`/`ip_hash` (berbobot), `least_connections`, `least_response_time`, `real_load` (beban nyata). Mode `real_load` bawaan (probe `/.omega-serv-load/`, memakai ulang pengukuran `psutil` yang sama dengan layar « Status & Sumber Daya », tidak pernah panggilan kedua) atau deklaratif (probe HTTP pihak ketiga, format minimal `{"load_percent": ...}` atau angka polos) — granularitas per upstream, satu zona dapat mencampur keduanya.
- **Afinitas sesi dan perutean bersyarat** — cookie sticky buram (host:port nyata tidak pernah terlihat oleh klien) dan aturan berdasarkan header (kesamaan atau awalan), keduanya disaring menurut kelayakan upstream sasaran (kembali dengan rapi ke strategi aktif jika upstream sasaran tidak tersedia).
- **Kesehatan** — pasif (kegagalan/keberhasilan berturut-turut, ambang peralihan down/up yang terpisah untuk membatasi flapping) **dan** aktif (probe berkala yang tidak bergantung pada lalu lintas nyata, opsional per upstream, memakai ulang mekanisme tugas latar yang sama dengan beban nyata). Status `DOWN` (selalu otomatis), `DRAINING`/`MAINTENANCE` (selalu manual, jelas bersifat sementara, tidak pernah disimpan) — upstream yang ditetapkan manual tetap dikeluarkan dari pilihan baru tanpa pernah memutus koneksi yang sudah terjalin. Percobaan ulang otomatis pada upstream lain, hanya untuk metode idempoten (GET/HEAD/OPTIONS) dan hanya pada galat koneksi.
- **Backpressure** — batas koneksi aktif yang dapat dikonfigurasi per upstream; upstream yang jenuh menolak dengan rapi dengan 503, berbeda dari upstream yang mati (502, tetap dicoba ulang).
- **Cache respons** — hanya GET/HEAD, tidak pernah respons galat, tidak pernah `Set-Cookie` kecuali diaktifkan eksplisit per zona; menghormati `Cache-Control`/`Vary` dari upstream (opsi yang dapat dinonaktifkan tetapi berbahaya, filosofi yang sama dengan verifikasi TLS). Beberapa varian dari sumber daya yang sama (`Vary`) benar-benar hidup berdampingan di disk, tidak pernah sekadar « yang datang terakhir menang ». Kunci anti-stampede (hanya satu permintaan serentak yang benar-benar membangun ulang cache). Header diagnostik `X-Omega-Cache: HIT`/`MISS`/`BYPASS` di setiap respons. Pemantauan/pembersihan di layar TUI khusus (*Cache reverse proxy*).
- **Perlindungan anti-loop** — header hop-by-hop dihapus, `X-Forwarded-*` selalu ditimpa (tidak pernah digabung dengan milik klien), penghitung `X-Omega-Proxy-Hops` bertambah di setiap penerusan (penolakan rapi di atas 5 lompatan — mendeteksi loop tidak langsung antara dua instans, yang tidak pernah terlihat oleh validasi konfigurasi lokal biasa).
- **WebSocket** — upgrade dapat diizinkan per zona, satu upstream dikunci selama umur saluran setelah terjalin, tanpa timeout tingkat aplikasi.
- **Administrasi panas** — API HTTP lokal kecil (`/.omega-serv-admin/`, dilindungi oleh `trusted_proxy` seperti probe beban bawaan) yang memungkinkan TUI membaca/memaksa status DRAINING/MAINTENANCE sebuah backend dan membaca rasio hit/miss cache **dari server yang benar-benar sedang berjalan** (layar khusus *Status langsung backend*) — TUI dan server tetap dua proses terpisah tanpa memori bersama, kanal HTTP lokal ini adalah satu-satunya jembatan di antara keduanya.

[↑ Daftar isi](#daftar-isi)

## 8. Pengerasan HTTP (aktif secara bawaan)

- Analisis permintaan, tanpa opsi untuk menonaktifkannya: header/baris permintaan dibatasi **selama** pembacaan (tidak pernah setelahnya), pelipatan header usang ditolak, `Transfer-Encoding` selalu ditolak (tidak pernah ditebak).
- `Content-Length` ganda ditolak; header `Expect` (misalnya `100-continue`) ditolak dengan rapi (417).
- Daftar putih metode yang eksplisit (405 + `Allow` jika tidak), header `Host` divalidasi (hilang/kosong/ganda-meski-identik/karakter kontrol → 400); pemeriksaan ini aktif secara bawaan dan hanya dapat dinonaktifkan di konfigurasi (`security.require_valid_host`).
- Header keamanan dan CSP dasar (`enforce`/`report-only`) diterapkan pada respons situs, termasuk halaman galatnya (403, 404…), dan tidak pernah dihapus atau ditimpa oleh modul. Pengecualian: respons yang dikirim sebelum permintaan diproses sama sekali (permintaan cacat atau terlalu besar, batas waktu terlampaui, `Host` tidak valid, metode ditolak, server penuh) keluar tanpa header ini — itu adalah halaman galat singkat tanpa konten situs. Aktif secara bawaan, hanya dapat dinonaktifkan di layar **Keamanan umum** (`security.security_headers_enabled`). `Cross-Origin-Opener-Policy`/`Cross-Origin-Resource-Policy` selalu `same-origin`, tanpa risiko nyata merusak situs. `Cross-Origin-Embedder-Policy` selalu dikirim secara eksplisit (tidak pernah absen — pemindai eksternal membedakan « tidak dipertimbangkan » dari « longgar karena pilihan »), bawaan `unsafe-none` di **semua** profil termasuk `hardened`: berbeda dengan dua sebelumnya, `require-corp`/`credentialless` dapat memblokir sumber daya cross-origin (font, gambar, iframe pihak ketiga) milik situs yang benar-benar disajikan — dapat diatur (`security.coep_mode`). Zona CSP (`security.csp_zones`): pengecualian **eksplisit** per awalan jalur (mis. `unsafe-inline` hanya di bawah `/sebuah-folder/` yang benar-benar membutuhkannya), masing-masing menggantikan sepenuhnya kebijakan bawaan untuk awalannya — tidak pernah penggabungan, tidak pernah pelonggaran global; setiap pengecualian tetap terlihat di `audit security` (CSP-001/CSP-002 juga memindai zona), meski disengaja. Pembuatan terpandu oleh asisten per direktif (layar **Keamanan umum**), setiap kolom terisi lebih dulu dengan nilai **saat ini** dari kebijakan global — agar hanya mengubah yang perlu diubah alih-alih memulai dari kolom kosong yang tanpa sengaja mengorbankan direktif lain; konfirmasi eksplisit tambahan diminta jika zona yang dirakit melonggarkan `unsafe-inline`/`unsafe-eval`/sumber umum `*`.
- Alamat IPv4-terpetakan-IPv6 (`::ffff:x.x.x.x`) dinormalisasi sebelum perbandingan apa pun (daftar blokir, proxy tepercaya, pembatasan laju) — jika tidak, ini celah pelewatan yang dikenal.
- Diverifikasi dengan pengujian properti (`hypothesis`, ribuan contoh yang dibangkitkan) terhadap pengurai HTTP dan resolver jalur, di samping pengujian unit/integrasi biasa.

[↑ Daftar isi](#daftar-isi)

## 9. TLS

### 9a. Sertifikat swatanda (minimal)

Mencakup penggunaan realistis lokal/lab/VPN (Tailscale...): satu listener, `ssl.SSLContext` langsung, RSA 2048/4096 atau ECDSA P-256/P-384.

### 9b. CA lokal

Untuk beberapa perangkat klien yang harus percaya tanpa mengimpor ulang sertifikat satu per satu: otoritas sertifikat lokal menandatangani sertifikat server sebanyak yang diperlukan.

```text
secure/certificates/ca/
├── root-ca.key    # 0600 - elemen paling sensitif dalam proyek
├── root-ca.pem    # 0644 - diimpor ke penyimpanan kepercayaan klien
├── serial.txt     # 0600 - pelacakan nomor seri berikutnya
└── index.txt      # 0600 - pelacakan status V(alid)/R(dicabut) per sertifikat yang ditandatangani
```

Alur: `certs generate-ca` (frasa sandi kunci CA **wajib**, masukan interaktif dengan konfirmasi ganda jika `--password` dihilangkan) → `certs generate-csr` (kunci + CSR server) → `certs sign-csr` (menandatangani dengan CA, menyalin SAN dari CSR, membangun `fullchain.pem` jika diminta) → arahkan `tls.certificate.certificate_path` ke `fullchain.pem` ini. Sertifikat yang terkompromi dicabut melalui `certs revoke` (menandai `index.txt`, terlebih dahulu memeriksa bahwa sertifikat memang berasal dari CA ini — menolak jika tidak). Tidak ada distribusi CRL di V1, juga tidak ada CA eksternal/CSR untuk otoritas pihak ketiga, maupun mTLS.

### 9c. Let's Encrypt / ACME (Certbot) — publik, di-hosting sendiri

Untuk situs yang benar-benar publik dengan sertifikat yang diakui peramban, skema hosting mandiri lengkap: DDNS (Dynu atau setara, sepenuhnya tanggung jawab operator) → Certbot → Omega-serv. Hanya asisten TUI (`Konfigurasi terperinci → TLS → Asisten Let's Encrypt`) — memanggil `certbot certonly --webroot` sebagai subproses (**tidak pernah** `--standalone`, port 80 sudah dipakai Omega-serv; **tidak pernah** klien ACME yang ditulis ulang) dengan `--config-dir`/`--work-dir`/`--logs-dir` diarahkan ke `secure/certificates/letsencrypt/` proyek — **tidak pernah** `/etc/letsencrypt/` — sehingga Certbot sendiri sepenuhnya tanpa hak istimewa. Sertifikat yang diperoleh diimpor otomatis (mekanisme yang sama dengan `certs import`, lihat contoh CLI di atas) dan skrip hook perpanjangan ditulis. Mode uji (staging) dicentang secara bawaan — hapus centangnya setelah domain/webroot terverifikasi berfungsi, untuk menghindari batas laju nyata Let's Encrypt.

Prasyarat yang sepenuhnya di luar cakupan Omega-serv: domain yang diarahkan ke IP publik (DDNS), dan port 80/443 yang diteruskan ke mesin ini.

### 9d. Perpanjangan otomatis (Certbot)

`Konfigurasi terperinci → TLS → Perpanjangan otomatis` menyesuaikan diri dengan pengelola layanan yang benar-benar terdeteksi **untuk instans ini** (tidak pernah mekanisme bersama antarinstans): systemd → membuat dan memasang timer (`<service>-certbot-renew.timer`, dua kali sehari + jeda acak, `certbot renew` dibatasi pada `--config-dir` instans); jika tidak → baris crontab (pengguna saat ini, tanpa hak istimewa) jika `crontab` tersedia; jika tidak → instruksi manual ditampilkan, tanpa penulisan paksa. Pada beberapa distribusi (termasuk Arch/Manjaro), paket Certbot **tidak** memasang timer apa pun secara bawaan, berbeda dengan Debian/Ubuntu — karena itu ada layar ini alih-alih sekadar memeriksa mekanisme yang diasumsikan sudah ada. Setelah dikonfigurasi, perpanjangan otomatis mengimpor ulang setiap sertifikat yang diperpanjang (`certs import`) lalu memulai ulang layanan, tanpa pernah perlu campur tangan manual lagi.

[↑ Daftar isi](#daftar-isi)

## 10. Audit keamanan

`audit security` **tidak memblokir**: ia menjalankan ulang gerbang pemblokir `config check` sebagai `CRITICAL`, lalu menerapkan aturan konsultatif (TLS, CSP, metode berbahaya, timeout, kebersihan unggahan murni; izin berkas, kedaluwarsa sertifikat, unit systemd terpasang, ukuran log melalui I/O nyata). `WAF-001` (WAF tetap di `log-only`) diamati seiring waktu melalui berkas status kecil (`var/run/waf-mode-state.json`) — hanya terpicu setelah ≥14 hari teramati dalam `log-only` pada eksekusi berulang, bukan pada `audit` pertama.

[↑ Daftar isi](#daftar-isi)

## 11. Active Defense (deception + mode perang)

Modul opsional (`option enable active_defense`, dinonaktifkan secara bawaan) yang menilai perilaku bermusuhan dari sinyal WAF yang sudah dihitung (`WafDecision`/reputasi/daftar blokir — tidak pernah penghitungan skor independen kedua), dan dapat mengalihkan sumber ke umpan, memperlambat responsnya dan mencatat lebih rinci, membangun insiden yang dapat ditindaklanjuti, lalu mengekspor indikator kompromi (IoC). Tidak pernah memblokir lalu lintas sendiri — pemblokiran jaringan tetap tugas `omega-fire`; Active Defense mengamati, mengalihkan, memperlambat, dan mencatat.

**Ancaman dan skor**: setiap sumber (`IP + hash SHA-256 dari User-Agent`) mengumpulkan skor (`WAF-001` memblokir +10, eskalasi reputasi +25, larangan yang sudah dikenal +25, POST ke umpan yang sudah ditetapkan +30 — penurunan -5 setiap 15 menit tanpa peristiwa baru) yang dikategorikan sebagai `normal`/`suspicious`/`hostile`/`contained` (`contained` juga mensyaratkan larangan yang sudah dikenal). `mode: monitor` mengamati tanpa bertindak; `mode: enforce` benar-benar menerapkan tindakan di bawah.

**Mode perang** (`options.active_defense.settings.war_mode`): sebuah `DefensePlaybook` (`actions: ["redirect_to_decoy", "enrich_log", "delay", "rate_limit", "create_incident", "export_ioc"]`) yang dipicu oleh ambang yang dapat dikonfigurasi, untuk setiap sumber yang bukan `normal`:
- `enrich_log` — log JSONL terpisah (`var/log/active-defense-enriched.jsonl`, tidak pernah dicampur dengan log WAF/produksi), header disamarkan, badan HTTP di-hash (SHA-256) atau dipotong sesuai `logging.capture_request_body`.
- `delay` — perlambatan yang dibatasi dan diberi jitter (`war_mode.slowdown.minimum_ms`/`maximum_ms`/`jitter_ms`), tidak pernah memblokir loop asyncio.
- `rate_limit` — pembatasan laju khusus per sumber (`war_mode.rate_limit.requests`/`window_seconds`), memakai ulang mekanisme yang sama dengan WAF di bawah kunci terpisah.
- `create_incident` — pembukaan/penggabungan insiden otomatis saat melewati `thresholds.incident_score`.

**Deception**: sumber `hostile`/`contained` dapat ditugaskan ke umpan statis (`fake_admin`, `fake_cms`, `fake_api`, `fake_secrets` — respons yang masuk akal tetapi selalu tetap, tidak pernah membaca berkas nyata atau menjalankan subproses) yang dipilih menurut kelas serangan yang teramati (`deception.profiles.<nama>.match_attack_classes`, satu atau lebih dari `scan`/`credential_stuffing`/`sqli`/`xss`/`path_traversal`/`upload_probe`/`api_probe`/`unknown`). Dua tingkat isolasi, diakui dan didokumentasikan sebagaimana adanya:
- **Tingkat 1** (fixture dalam proses, `isolation_level: "fixture"`, bawaan) — isolasi LEMAH yang eksplisit: proses yang sama, pengguna OS yang sama dengan produksi, hanya dapat diterima karena fixture tidak pernah melakukan apa pun selain mengembalikan templat statis. NAMA profil harus persis sama dengan salah satu dari 4 fixture di atas — jika tidak, ditolak saat validasi (`validate_active_defense_config`), untuk menghindari jebakan umpan yang salah nama lalu diam-diam tidak pernah terpicu.
- **Tingkat 2** (backend yang benar-benar terisolasi, `isolation_level: "proxy"`) — diteruskan ke proses terpisah melalui `options.active_defense.settings.deception.decoy_zones.<nama>` (upstream `host`/`port` dari server yang sudah berjalan, tidak pernah dibuat otomatis; tidak pernah dibaca dari `options.reverse_proxy` — umpan tidak pernah dapat tanpa sengaja mengarah ke zona produksi, diverifikasi saat `config check`), memakai ulang mekanisme reverse proxy keluar yang sama dengan produksi (`serve_proxy()` — upstream tidak terjangkau saat permintaan nyata: 502 dikembalikan ke penyerang, tidak pernah crash).

**Layar Pengaturan** (TUI, Keamanan Aktif → Active Defense → Pengaturan): konfigurasi lengkap untuk semua hal di atas — mode, aktivasi mode perang, cakupan/tindakan/ambang/perlambatan/batas permintaan, deception (perilaku bawaan, CRUD profil umpan dan zona umpan dengan contoh nilai yang ditampilkan di setiap kolom), IoC, penyimpanan dan pencatatan — divalidasi dengan aturan yang sama seperti CLI sebelum setiap penyimpanan, tanpa pernah perlu mengedit `config/omega-serve.json` secara manual. Mulai ulang penuh selalu diperlukan setelah setiap perubahan (Active Defense tidak pernah dimuat ulang secara panas).

**Insiden dan IoC**: kronologi lengkap per insiden, ekstraksi indikator (IP, User-Agent yang di-hash), ekspor JSON berversi/CSV yang dibatasi pada IoC yang dapat dibagikan/laporan Markdown, serta format pertukaran **STIX 2.1** (bundle untuk dimuat ke OpenCTI, SIEM…) dan **MISP** (peristiwa untuk diimpor melalui antarmuka MISP), ditandai TLP:AMBER secara bawaan — berkas lokal, tidak pernah dikirim; setiap ekspor disertai berkas `<export>.sha256` (format `sha256sum` standar). Ekspor otomatis saat insiden ditutup jika `ioc.auto_export_on_close` (bawaan true). Status yang kedaluwarsa dan log audit dibersihkan otomatis, basis data diberi batas atas (perlindungan terhadap disk penuh); `active-defense purge` juga menutup insiden yang kembali tenang.

**Simulasi**: `active-defense simulate` (CLI) dan tombol "Simulasi" (TUI, layar Keamanan Aktif) memproyeksikan skor/tingkat dan menjelaskan setiap tindakan yang akan terpicu — dry-run ketat, tanpa penulisan nyata, tanpa dampak jaringan.

Pencadangan/pemulihan: `config backup --include-active-defense` menyertakan basis data sqlite (ancaman/insiden/penugasan) dalam arsip — tidak pernah ada rahasia dalam teks biasa, sehingga `--confirm-secrets` tidak diperlukan, berbeda dengan `--include-auth`.

[↑ Daftar isi](#daftar-isi)

## 11b. Daftar jalur sensitif (WAF)

WAF dapat memuat **daftar yang dapat diedit** sebagai berkas teks, satu jalur (atau satu kata kunci) per baris, dari **Keamanan Aktif → WAF → Custom → Tambah → « MUAT daftar »**. Tidak ada yang dimuat secara bawaan: itu tindakan eksplisit.

- **Referensi yang disediakan**: `sensitive-paths-hostile` (298 jalur tanpa penggunaan sah: rahasia, cadangan, VCS, konsol…) dan `sensitive-paths-probe` (132 jalur penyelidikan, terkadang disajikan oleh situs sungguhan: `/admin`, `/api`, pemantauan…). Saat dimuat, **salinan lokal** dibuat di `secure/waf/rules/keywords/`: salinan itulah yang Anda ubah, pembaruan omega-serv tidak pernah menimpanya (« Hal baru di referensi » kemudian menawarkan entri baru, kotak demi kotak).
- **Sintaks**: `/admin` (→ `/admin` dan `/admin/xxx`, tidak pernah `/administrator`), `/.git/` (semua yang ada di bawahnya), `/*.bak` (ekstensi), `!/api/v1` (pengecualian, selalu diprioritaskan). Jalur didekodekan seperti di mesin (`%2e`, pengodean ganda, karakter lebar penuh).
- **Tingkat keparahan**: *Pengamatan* (hanya log, disarankan pada pemuatan pertama), lalu Sedang (tidak pernah memblokir sendirian) atau Tinggi (403 sejak akses pertama).
- **Residivisme khusus per daftar**: akses ke-1 = informasi atau penolakan; N akses dalam M menit = larangan aplikasi sementara (respons 451, bahkan melalui Tailscale); pemblokiran berulang = larangan jaringan oleh omega-jail. Referensi: hostile 2 akses dalam 10 menit → 24 jam, probe 5 dalam 10 menit → 1 jam.
- **Tidak pernah larangan otomatis** untuk host lokal, Tailscale (`100.64.0.0/10`), dan jaringan lokal (`options.waf.reputation.never_auto_block`): hanya lalu lintas eksternal yang dapat dilarang. Di belakang proxy lokal, pengecualian `127.0.0.1` mensyaratkan `trusted_proxy` aktif. `X-Forwarded-For` dibaca dari kanan ke kiri: klien tidak dapat mengaku dirinya lokal.
- **Pengaman**: jalur vital dilindungi (`/`, `robots.txt`, `sitemap.xml`, `/.well-known/acme-challenge/`…), penolakan daftar pemblokir yang akan mengenai rute yang benar-benar disajikan (alias, reverse proxy, zona Auth, webroot), **« Cocokkan dengan log saya »** di editor (baris yang akan mengenai permintaan yang berhasil, pengecualian dengan satu klik).
- **Editor terintegrasi**: diagnostik langsung dengan nomor baris, « Uji » sebuah jalur, penulisan aman (izin dan grup dipertahankan, tautan simbolik ditolak, perubahan dari luar terdeteksi), keterbacaan oleh akun layanan diperiksa (« Benahi hak akses »), dan muat ulang yang **jujur**: ditolak beserta alasannya jika daftar tidak lolos pemeriksaan, dan server tetap memakai aturannya saat ini.

[↑ Daftar isi](#daftar-isi)

## 11c. Batas laju per folder dan per IP/jaringan (WAF)

Batas laju WAF (token bucket, `options.waf.rate_limit`, bawaan 60 permintaan / 60 dtk per IP) dapat diperhalus dari **Keamanan Aktif → WAF → Pembatasan** (atau secara manual, `rate_limit.path_policies` / `rate_limit.source_policies`):

- **Aturan per folder** (`prefix`, `requests`, `window_seconds`): aturan ini **menggantikan** batas global untuk folder tersebut, dengan penghitungnya sendiri (`requests: 0` = tanpa batas). Awalan terpanjang menang; `/images` mencakup `/images/a.png`, tidak pernah `/images2`. Biasanya untuk halaman berat (galeri gambar) yang mengembalikan 429.
- **Aturan per IP/jaringan** (`network`, `requests`, `window_seconds`, `trusted`): prinsip yang sama; jaringan yang paling spesifik menang. Prioritas: folder, lalu IP/jaringan, lalu batas global.
- **Larangan tidak berubah untuk publik**: pelampauan oleh IP publik tetap dicatat `"action": "block"` di `waf-alerts.log`, sehingga dapat dilarang oleh omega-jail (3 penolakan dalam 10 menit → 12 jam). **Sumber aman** — jaringan `never_auto_block` atau aturan bertanda `trusted: true` — tetap menerima 429 tetapi dicatat `"action": "throttle"`, yang tidak pernah dihitung oleh jail.
- **Skrip magnet**: batas lajunya sendiri (respons 429) tidak pernah dihitung sebagai deteksi, sehingga tidak pernah berujung pada larangan otomatis; pada permintaan yang dicakup aturan folder atau IP/jaringan, aturan bawaan yang berlaku dan 429 dari magnet diabaikan (tanda tangan serangannya tetap diterapkan).
- Aturan laju **tidak pernah** menonaktifkan pemeriksaan WAF; sebaliknya, pengecualian pemeriksaan (`exclusions.path_prefixes`) tidak pernah mencabut rate limit. Tanpa `trusted_proxy` aktif, aturan yang mencakup `127.0.0.1`/`::1` diabaikan (pengaman yang sama dengan `never_auto_block`).

[↑ Daftar isi](#daftar-isi)

## 11d. RIPOSTE (respons bertingkat dari waktu ke waktu)

Modul opsional (`option enable riposte`, nonaktif secara bawaan, perlu mulai ulang penuh): jika Active Defense bereaksi **selama** permintaan, RIPOSTE bertindak **dari waktu ke waktu**. Ia mengingat alamat yang kembali setelah masa tenang (episode) dan memberinya blokir yang makin lama — tingkat bawaan 1 jam, 6 jam, 24 jam, 7 hari, jendela residivis 30 hari, riwayat 90 hari.

- **Proses terpisah**, dijalankan dan diawasi oleh layanan (dengan satu atau beberapa proses, satu per instans): membaca log WAF dan Active Defense, tidak pernah permintaan yang sedang berjalan. Tanpa WAF aktif, ia tidak melihat serangan apa pun.
- **Kebijakan**: kapan bertindak (kelas serangan, jumlah kembali, tingkat Active Defense, kunjungan umpan) dan bagaimana (blokir lokal di blocklist WAF, blokir lokal + jaringan melalui jail omega-jail, atau umpan Active Defense yang diperpanjang). Lima skenario siap muat; setiap kebijakan dapat diukur pada log nyata dan disimulasikan sebelum diaktifkan. Kebijakan aktif bertindak otomatis.
- **Tidak ada yang hilang**: setiap tindakan tetap terlihat, sedang berjalan atau selesai, beserta alasannya. Tiga tingkat penghentian: mencabut satu tindakan (dengan pengecualian atau « tidak dihitung sebagai residivis »), menonaktifkan aturan, henti darurat yang diingat.
- **Pengaman**: pengecualian yang sama dengan WAF (host lokal, Tailscale, jaringan lokal), tidak pernah menimpa blokir manual atau yang lebih lama, satu tindakan per episode, batas blokir serentak.
- **Ban lokal dan ban jaringan**: ban lokal dipasang omega-serv di daftar blokir WAF — alamat menerima halaman 451 “IP Anda telah di-ban” untuk semua permintaannya, selama ban berlangsung. Ban jaringan diserahkan ke fail2ban melalui jail omega-jail (`<service>-riposte-1h/6h/24h/7d`, satu set per instans); ban ini tidak berpengaruh saat koneksi datang melalui proxy lokal (Tailscale Funnel), di mana hanya ban lokal yang melindungi.
- **Antarmuka**: enam layar di Keamanan aktif (Status, Kebijakan, Tindakan, Residivis, Simulasi, Pengaturan) dan perintah baris yang sama (`riposte …`). Cadangan: `config backup --include-riposte`.

[↑ Daftar isi](#daftar-isi)

## 11e. Intervensi manual (Keamanan Aktif)

Bingkai **INTERVENSI MANUAL**, di bawah tiga blok Keamanan Aktif, untuk bertindak secara manual tanpa menulis aturan konfigurasi: memblokir alamat IP tanpa syarat, membuka blokirnya, melihat semua blokir yang berlaku.

- **Blokir**: satu alamat IPv4 atau IPv6, satu alasan, satu durasi (1 jam hingga 30 hari, bebas atau permanen). Blokir melalui daftar blokir WAF: halaman 451 di seluruh situs, sebelum perutean — backend tidak pernah melihat alamat itu. Langsung berlaku dengan kedua mesin, tanpa hak root. Jaringan diblokir di WAF → Modul.
- **Independen**: tidak terkait dengan Active Defense maupun RIPOSTE — blokir manual tidak pernah dihitung sebagai pelanggaran berulang, dan tidak ada otomatisasi yang menggantikannya. Konfirmasi diminta untuk alamat lokal, privat, atau Tailscale.
- **Buka blokir**: hanya blokir yang dipasang di sini; yang lain dicabut di tempat ia dipasang (WAF → Modul, RIPOSTE → Tindakan).
- **Status blokir**: semua blokir beserta asalnya (manual, blokir otomatis WAF, RIPOSTE, omega-jail, Magnet), dapat diekspor ke JSON, HTML, atau TXT — satu alamat per baris, bisa diimpor apa adanya ke omega-fire.

[↑ Daftar isi](#daftar-isi)

## 12. Layanan dan operasi

Deteksi otomatis systemd/OpenRC/runit (`service install/status/start/stop/restart/enable/disable/uninstall`). Unit systemd yang dibuat menerapkan pengerasan yang tidak dapat ditawar secara bawaan: `NoNewPrivileges`, `PrivateTmp`, `ProtectSystem=strict`, `ProtectHome`, `ReadWritePaths` dibatasi pada `var/`, pengguna/grup khusus wajib, `UMask=0007`, `Restart=on-failure`. Berhenti rapi saat SIGTERM (pengurasan koneksi yang sedang berjalan, masa tenggang yang dapat dikonfigurasi lalu penutupan paksa); muat ulang panas saat SIGHUP (hanya aturan WAF dan zona Auth — bind/port/TLS dan Active Defense tidak pernah dapat diubah tanpa mulai ulang penuh).

[↑ Daftar isi](#daftar-isi)

## 13. Log

`var/log/access.log` (format Apache combined + `request_id`, pelolosan anti-injeksi log), `var/log/error.log`. Rotasi berdasarkan ukuran/jumlah berkas yang disimpan (`logs.rotation`). WAF bawaan: `var/log/waf-alerts.log` (`options.waf.logging.path`). Skrip magnet: `options.waf.magnet.paths.alerts_log`/`.blocklist_log`, bawaan `var/log/waf-magnet-alerts.log`/`var/log/waf-magnet-blocklist.log` — langsung ditambahkan ke Pustaka (tombol *Tambahkan log Omega-Serv yang dikenal*) hanya jika magnet aktif; sebaliknya `lnav` selalu menawarkannya (berkas yang tidak ada cukup diabaikan saat dijalankan).

### 13a. Sumber jarak jauh (SSH)

Memusatkan, atas permintaan eksplisit, log dari server backend yang berada di jaringan lokal yang sama di belakang reverse proxy (layar **Pengelolaan log → Pustaka → Sumber jarak jauh (SSH)**). Sebuah « fetch » adalah tindakan manual sekali jalan, tidak pernah aliran langsung atau polling otomatis: **salinan** diambil melalui `scp` saat Anda mengklik *Ambil sekarang*, ditulis di bawah `var/log/remote/`, lalu ditambahkan ke Pustaka seperti log biasa (kolom *Akses* = `ssh`, kolom *Diubah* = tanggal pengambilan **ini** — tidak pernah tanggal berkas jarak jauh); pengambilan baru cukup menggantikan salinan sebelumnya dengan yang lebih baru.

Pengaman yang disengaja: tanpa pemindaian jaringan otomatis, tanpa koneksi tanpa konfigurasi eksplisit (label/host/jalur jarak jauh, pengguna/port/kunci privat opsional — jika kosong, `ssh`/`~/.ssh/config` yang menentukan seolah perintah diketik manual), tidak pernah meminta atau menyimpan kata sandi (kunci privat hanya dirujuk melalui jalurnya, tidak pernah dibaca atau disimpan oleh Omega-serv), tanpa pemeriksaan ukuran sebelum transfer. Kapabilitas `scp` dideteksi secara lokal di **Registri kapabilitas** (hanya keberadaan biner, tidak pernah uji keterjangkauan host); Samba sengaja dikesampingkan (YAGNI, selama belum ada kebutuhan nyata yang terkonfirmasi).

[↑ Daftar isi](#daftar-isi)

## 14. Pengujian

```bash
source .venv/bin/activate
lint-imports        # memeriksa 8 kontrak lapisan
pytest -q           # seluruh rangkaian pengujian
ruff check .
mypy src
```

Struktur: `tests/unit/` (domain/aplikasi, test double), `tests/integration/` (server asyncio nyata pada soket TCP nyata, `openssl` nyata sebagai subproses, perintah CLI nyata terhadap proyek sementara yang lengkap, antarmuka interaktif melalui API `Pilot` Textual - tidak pernah tangkapan layar), `tests/security/` (pengujian properti `hypothesis` pada pengurai HTTP dan resolver jalur).

[↑ Daftar isi](#daftar-isi)

## 15. Di luar cakupan

- CGI mentah (hanya FastCGI/PHP-FPM)
- mTLS (autentikasi klien dengan sertifikat), OCSP stapling
- CA eksternal / CSR untuk otoritas pihak ketiga, distribusi CRL lengkap
- Active Defense: integrasi nyata dengan peristiwa larangan `omega-fire` (terhambat di sisi `omega-fire`, yang saat ini belum menyediakan antarmuka baca apa pun)

[↑ Daftar isi](#daftar-isi)

---

> 🔒 **OMEGA-SERV** — Server web yang kokoh, lengkap, aman, dan sengaja defensif.
