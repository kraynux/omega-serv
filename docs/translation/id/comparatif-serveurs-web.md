<!-- Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE) -->

# omega-serv dibandingkan dengan server web di pasaran

**Perbandingan berdasarkan pengukuran: nginx · lighttpd · Apache · Caddy · Traefik · omega-serv 2.5**

🌐 [Français](../../comparatif-serveurs-web.md) · [English](../en/comparatif-serveurs-web.md) · [Español](../es/comparatif-serveurs-web.md) · [Português (Brasil)](../pt-BR/comparatif-serveurs-web.md) · [Italiano](../it/comparatif-serveurs-web.md) · [Deutsch](../de/comparatif-serveurs-web.md) · [Nederlands](../nl/comparatif-serveurs-web.md) · [Polski](../pl/comparatif-serveurs-web.md) · [Русский](../ru/comparatif-serveurs-web.md) · [中文](../zh-CN/comparatif-serveurs-web.md) · [Tiếng Việt](../vi/comparatif-serveurs-web.md) · [ไทย](../th/comparatif-serveurs-web.md) · **Bahasa Indonesia** · [日本語](../ja/comparatif-serveurs-web.md) · [한국어](../ko/comparatif-serveurs-web.md) · [हिन्दी](../hi/comparatif-serveurs-web.md) · [العربية](../ar/comparatif-serveurs-web.md)

Dokumen ini menempatkan omega-serv di antara server web yang paling banyak digunakan. Dokumen ini tidak bermaksud menentukan "server terbaik": setiap alat menjawab kebutuhan yang berbeda, dan masing-masing punya keunggulan. Dokumen ini memberikan tiga hal:

1. **pengukuran nyata**, dilakukan pada **tiga mesin** yang sangat berbeda, dengan klien yang sama, berkas yang sama, dan prosedur yang sama, serta dapat diulang;
2. **perbandingan fitur**, masing-masing diverifikasi terhadap dokumentasi resmi server yang bersangkutan (tautan di akhir dokumen), dengan membedakan fitur bawaan dan fitur yang memerlukan modul atau plugin;
3. apa yang **benar-benar ditambahkan** omega-serv, dan apa yang dilakukan server lain **lebih baik darinya**.

Semua pengukuran kinerja dilakukan pada 3 dan 4 November 2026. Tidak ada angka yang diambil dari situs lain atau diperkirakan. Data mentah diterbitkan bersama dokumen ini.

---

## Daftar isi

1. [Ringkasan](#1-ringkasan)
2. [Cara membaca perbandingan ini](#2-cara-membaca-perbandingan-ini)
3. [Metode pengukuran](#3-metode-pengukuran)
4. [Kinerja: omega-serv dibandingkan dengan nginx, lighttpd, Apache, dan Caddy](#4-kinerja-omega-serv-dibandingkan-dengan-nginx-lighttpd-apache-dan-caddy)
5. [Versi omega-serv: 1.0 → 2.0 → 2.5](#5-versi-omega-serv-10--20--25)
6. [Perbandingan fitur](#6-perbandingan-fitur)
7. [Administrasi dan kenyamanan](#7-administrasi-dan-kenyamanan)
8. [Kelebihan omega-serv](#8-kelebihan-omega-serv)
9. [Yang dilakukan server lain dengan lebih baik](#9-yang-dilakukan-server-lain-dengan-lebih-baik)
10. [Server mana untuk kebutuhan apa](#10-server-mana-untuk-kebutuhan-apa)
11. [Mengulang pengukuran](#11-mengulang-pengukuran)
12. [Sumber](#12-sumber)

---

## 1. Ringkasan

- **omega-serv memiliki dua mesin.** **Mesin Python** menangani semuanya. **Mesin native**, ditulis dalam C++ dan hadir sejak 2.5, melayani permintaan sendiri; Python tetap memegang konfigurasi dan keputusan keamanan, dan mesin native sendiri mengenali permintaan yang tidak cocok dengan aturan WAF mana pun.
- **Dengan mesin native, tanpa WAF**, omega-serv menyajikan berkas kecil dengan kecepatan **sekitar 0,7 dari nginx**, di ketiga mesin. Dengan demikian ia berada **di depan Apache dan Caddy, di belakang nginx dan lighttpd**.
- **Dengan mesin Python**, omega-serv jauh tertinggal dari semua server lain: **3–11 % dari kecepatan nginx**.
- **Dengan WAF aktif**, omega-serv memeriksa setiap permintaan, sesuatu yang tidak dilakukan server lain yang diukur. Dengan mesin native, ia kemudian mencapai **0,53–0,56** dari kecepatan nginx (tanpa WAF) di mesin A dan B, dan 1,07 di mesin C (4 inti dibanding 2): WAF hanya mengurangi 5–22 % throughput-nya. Ia tetap di depan Apache dan Caddy, yang diukur tanpa WAF.
- **Berkas sedang (100 KB)**: ini kelemahan mesin native saat ini, **0,3–0,6** dari nginx, di belakang Apache.
- **Berkas besar (5 MB)**: nginx, lighttpd, Apache, dan omega-serv native mencapai throughput dengan orde yang sama. Caddy jelas lebih lambat di mesin tercepat.
- **Memori**: lighttpd (1 MB), nginx (4–5 MB), dan Apache (4–9 MB) sangat hemat. omega-serv memakai **30–65 MB** tergantung mode, Caddy **50–67 MB**.
- **Kelebihan omega-serv**: administrasi lengkap di antarmuka terminal, dalam 17 bahasa; WAF dan pertahanan aktif bawaan; batas keamanan yang tepat dengan banyak proses; impor skrip mod_magnet dari lighttpd; pengelolaan banyak instans.
- **Yang tidak dimilikinya**: HTTP/2 dan HTTP/3, kompresi langsung, penemuan layanan Docker/Kubernetes, klien ACME bawaan (ia memakai Certbot), ekosistem modul.

---

## 2. Cara membaca perbandingan ini

Beberapa konsep muncul di seluruh dokumen.

- **Permintaan per detik (req/s)**: jumlah berkas yang dikirim server dalam satu detik. Semakin tinggi semakin baik.
- **Selisih dari nginx**: nilai absolut sangat bergantung pada mesin. Di tiga mesin kami, nginx berkisar dari 22 000 hingga 440 000 req/s. Yang tetap stabil adalah **rasio antarserver**. Karena itu tabel menampilkan, di samping setiap nilai, rasionya terhadap nginx yang diukur pada sesi yang sama: **1,00 = secepat nginx**, 0,50 = separuh kecepatannya, 1,50 = satu setengah kali lebih cepat.
- **Latensi p99**: waktu respons yang tidak dilampaui oleh 99 % permintaan. Ini menunjukkan "saat-saat buruk" yang disembunyikan oleh rata-rata.
- **PSS (*Proportional Set Size*)**: memori yang benar-benar dipakai oleh semua proses server. Halaman yang dibagi oleh beberapa proses hanya dihitung sekali.
- **Proses dan inti**: server dapat memakai beberapa inti prosesor. Masing-masing melakukannya dengan caranya sendiri. nginx, lighttpd, Apache, dan omega-serv dalam mode Python menjalankan beberapa proses. Caddy, yang ditulis dalam Go, membagi pekerjaan ke inti-inti. Mesin native omega-serv menjalankan satu thread per inti yang tersedia. Agar perbandingan adil, kami memberi setiap server **inti yang sama**.
- **WAF (*Web Application Firewall*)**: penyaring yang memeriksa setiap permintaan untuk memblokir serangan (injeksi, pemindai…). omega-serv sudah memilikinya bawaan. Server lain bisa mendapatkannya sebagai modul (ModSecurity, Coraza), tetapi **diukur tanpanya**, dalam konfigurasi dasar.

**Kebiasaan yang benar**: bandingkan rasio, bukan nilai absolut, dan selalu periksa apakah WAF aktif.

---

## 3. Metode pengukuran

### Tiga mesin

| | Mesin A | Mesin B | Mesin C |
|---|---|---|---|
| Prosesor | Intel Core i5 M480, 2,67 GHz (2010) | Intel Celeron J3455, 1,5 GHz (2016) | AMD Ryzen AI 9 365 (2024) |
| Inti | 2 inti fisik, 4 thread | 4 inti, tanpa hyperthreading | 10 inti (4 Zen 5 + 6 Zen 5c), 20 thread |
| Memori | 8 GB | 8 GB | 32 GB |
| Sistem | Mabox Linux (berbasis Manjaro), kernel 6.18 | EndeavourOS, kernel 7.2 | Arch Linux, kernel 7.2 (CachyOS) |
| Inti server | 1 inti fisik (thread 0 dan 2) | 2 inti (0 dan 1) | 4 inti Zen 5, satu thread per inti (0–3) |
| Inti klien | 1 inti fisik (thread 1 dan 3) | 2 inti (2 dan 3) | 6 inti Zen 5c (4–9) |

Mesin A adalah laptop lama, mesin B adalah mini PC hemat daya, mesin C adalah laptop baru, tersambung ke listrik, dengan profil daya "seimbang". Ketiganya mencakup rentang dari server rumahan kecil hingga mesin modern.

### Perangkat lunak

| Perangkat lunak | Versi |
|---|---|
| nginx | 1.30.4 (A), 1.30.5 (B, C) |
| lighttpd | 1.4.85 |
| Apache HTTP Server | 2.4.69, MPM `event` |
| Caddy | 2.11.4 (A, B), 2.11.7 (C) |
| omega-serv | 1.0.0 dan 2.0.0 (arsip yang diterbitkan) serta 2.5, di Python 3.14 |
| Klien beban | [oha](https://github.com/hatoo/oha) 1.16.0 (ditulis dalam Rust) |

Traefik tidak diukur: ia bukan server berkas (lihat §6). Ia hanya muncul dalam perbandingan fitur.

### Prosedur

- **Isolasi prosesor**: server dan klien dipasangkan ke inti yang berbeda (tabel di atas). Klien tidak mengambil waktu server, dan semua server memiliki sumber daya yang persis sama.
- **Berkas yang sama untuk semua**: `small.html` (1 KB), `medium.png` (100 KB), dan `large.bin` (5 MB), disajikan dari folder yang sama.
- **Log akses aktif di semua server**, karena server produksi mencatat log.
- **HTTP/1.1 tanpa enkripsi, koneksi persisten (keep-alive)**. Konkurensi 32 koneksi untuk berkas 1 KB dan 100 KB, dan 8 untuk berkas 5 MB.
- **Durasi**: 10 detik per berkas dan per konfigurasi.
- **Pengulangan**: 3 putaran lengkap bergantian (semua konfigurasi di putaran 1, lalu semuanya di putaran 2, dan seterusnya). Tabel menampilkan **median** dari tiga putaran. Dari putaran ke putaran, selisihnya sebagian besar di bawah 5 %.
- **Memori**: PSS dari semua proses server, dicatat saat diam lalu setelah beban.
- **Konfigurasi**:
  - nginx, lighttpd, Apache, dan Caddy dalam konfigurasi dasar: berkas statis dan log akses;
  - omega-serv dengan profil `standard`, WAF nonaktif, lalu aktif dengan semua aturan yang disertakan (tanpa pembatasan laju).
- **Jumlah proses**: setiap server diukur dengan 1 lalu 2 proses: nginx `worker_processes`, lighttpd `server.max-worker`, Apache `StartServers`/`ServerLimit`, Caddy `GOMAXPROCS`, omega-serv `server.workers`. Untuk mesin native omega-serv, `server.workers` menghitung proses keamanan Python; mesin native sendiri selalu memakai semua inti yang dialokasikan kepadanya.
- **Tanpa satu galat pun**: semua respons dari semua pengukuran adalah 200.

### Batasan yang perlu diketahui

- **Kami membandingkan rasio.** Nilai absolut di perangkat keras Anda atau di server khusus akan berbeda.
- **Antarmuka loopback (127.0.0.1)**: pengukuran tidak melewati jaringan nyata. Di jaringan nyata, throughput berkas besar hampir selalu dibatasi oleh tautan, bukan oleh server. Throughput puluhan GB/s di mesin C hanya mungkin di loopback.
- **Tanpa TLS** dalam pengukuran ini.
- **Mesin A**: layanan omega-serv produksi di mesin ini berjalan di latar belakang, tanpa menerima lalu lintas.
- **Mesin C**: prosesor hibrida (inti Zen 5 dan Zen 5c). Server mendapat 4 inti cepat, klien mendapat 6 sisanya.
- **Konfigurasi dasar**: tidak ada server yang dioptimalkan. Administrator berpengalaman pasti bisa memeras lebih banyak dari setiap server, termasuk omega-serv.
- **Data mentah**: [`docs/benchmarks/`](../../benchmarks/) (satu berkas per mesin).

---

## 4. Kinerja: omega-serv dibandingkan dengan nginx, lighttpd, Apache, dan Caddy

Di semua tabel, acuannya adalah **nginx dengan 2 proses** (= 1,00), diukur pada sesi yang sama di mesin yang sama. Di mesin A dan B, ini adalah konfigurasi yang memakai semua inti yang dialokasikan untuk server.

### Berkas kecil (1 KB): permintaan per detik

| Server | Mesin A | Mesin B | Mesin C |
|---|---:|---:|---:|
| lighttpd, 2 proses | 33 138 (**1,52**) | 31 125 (**1,26**) | 378 590 (**1,53**) |
| nginx, 2 proses | 21 801 (1,00) | 24 705 (1,00) | 248 184 (1,00) |
| **omega-serv, mesin native** | **15 222 (0,70)** | **16 542 (0,67)** | **285 213 (1,15 \*)** |
| omega-serv, native + WAF † | 11 990 (0,56) | 12 998 (0,53) | 264 484 (1,07 \*) |
| omega-serv, native + WAF, 2 proses keamanan † | 11 746 (0,55) | 12 718 (0,52) | 253 527 (1,02 \*) |
| Apache, 2 proses | 9 192 (0,42) | 8 634 (0,35) | 188 335 (0,76) |
| Caddy, 2 proses | 5 749 (0,26) | 4 116 (0,17) | 52 897 (0,21) |
| omega-serv, mesin Python, 2 proses | 2 354 (0,11) | 1 312 (0,05) | 19 911 (0,08) |
| omega-serv, Python + WAF, 2 proses | 1 901 (0,09) | 1 104 (0,04) | 15 783 (0,06) |
| omega-serv, mesin Python | 1 507 (0,07) | 663 (0,03) | 10 553 (0,04) |
| omega-serv, Python + WAF | 1 561 (0,07) | 564 (0,02) | 8 365 (0,03) |

\* Di mesin C, mesin native memakai 4 intinya, sedangkan nginx dengan 2 proses hanya memakai 2. Perbandingan dengan jumlah inti yang sama ada di bawah: rasionya kembali menjadi **0,67–0,71**, seperti di mesin lain.

† Diukur pada 4 November, setelah optimasi WAF, dalam sesi terpisah dengan prosedur yang sama. Rasio dihitung terhadap nginx (2 proses) dari sesi ini: 21 439, 24 424, dan 248 127 req/s untuk berkas kecil, 11 545, 11 004, dan 157 491 untuk berkas 100 KB. Sebelum optimasi ini, mesin native dengan WAF mencapai 3 495, 2 622, dan 39 000 req/s (0,11–0,16 dari nginx), karena setiap permintaan melewati Python. Data mentah: berkas `*-waf-natif-brut.txt`.

Dengan 1 proses, nginx mencapai 0,52–0,73, lighttpd 0,81–1,43, Apache 0,33–0,74, dan Caddy 0,09–0,17 (data mentah).

### Latensi p99 pada berkas kecil

| Server | Mesin A | Mesin B | Mesin C |
|---|---:|---:|---:|
| lighttpd, 2 proses | 4,4 ms | 4,1 ms | 0,2 ms |
| nginx, 2 proses | 4,9 ms | 5,2 ms | 0,2 ms |
| **omega-serv, mesin native** | **6,1 ms** | **6,2 ms** | **0,3 ms** |
| omega-serv, native + WAF † | 7,2 ms | 6,7 ms | 0,3 ms |
| Apache, 2 proses | 18,8 ms | 20,6 ms | 0,8 ms |
| Caddy, 2 proses | 24,1 ms | 30,5 ms | 2,8 ms |
| omega-serv, mesin Python, 2 proses | 22,6 ms | 28,1 ms | 3,3 ms |
| omega-serv, mesin Python | 32,0 ms | 51,6 ms | 4,4 ms |

### Berkas sedang (100 KB): permintaan per detik

| Server | Mesin A | Mesin B | Mesin C |
|---|---:|---:|---:|
| lighttpd, 2 proses | 13 561 (**1,08**) | 12 126 (**1,07**) | 197 905 (**1,26**) |
| nginx, 2 proses | 12 513 (1,00) | 11 303 (1,00) | 157 224 (1,00) |
| Apache, 2 proses | 6 939 (0,55) | 7 035 (0,62) | 153 265 (0,97) |
| Caddy, 2 proses | 5 059 (0,40) | 3 744 (0,33) | 22 094 (0,14) |
| **omega-serv, mesin native** | **4 738 (0,38)** | **3 115 (0,28)** | **96 277 (0,61)** |
| omega-serv, native + WAF † | 4 229 (0,37) | 2 926 (0,27) | 98 185 (0,62) |
| omega-serv, mesin Python, 2 proses | 1 741 (0,14) | 1 154 (0,10) | 18 806 (0,12) |
| omega-serv, mesin Python | 1 329 (0,11) | 611 (0,05) | 9 805 (0,06) |

### Berkas besar (5 MB): throughput

| Server | Mesin A | Mesin B | Mesin C |
|---|---:|---:|---:|
| lighttpd, 2 proses | 2 440 MB/s (1,05) | 2 110 MB/s (0,99) | 28 011 MB/s (0,81) |
| nginx, 2 proses | 2 322 MB/s (1,00) | 2 124 MB/s (1,00) | 34 651 MB/s (1,00) |
| Apache, 2 proses | 2 355 MB/s (1,01) | 2 134 MB/s (1,00) | 41 153 MB/s (**1,19**) |
| **omega-serv, mesin native** | **2 294 MB/s (0,99)** | **1 936 MB/s (0,91)** | **37 918 MB/s (1,09)** |
| Caddy, 2 proses | 2 205 MB/s (0,95) | 1 996 MB/s (0,94) | 3 811 MB/s (0,11) |
| omega-serv, mesin Python, 2 proses | 2 145 MB/s (0,92) | 1 931 MB/s (0,91) | 25 829 MB/s (0,75) |
| omega-serv, mesin Python | 1 686 MB/s (0,73) | 1 472 MB/s (0,69) | 14 227 MB/s (0,41) |

### Memori (PSS, semua proses server): saat diam → setelah beban

| Server | Mesin A | Mesin B | Mesin C |
|---|---:|---:|---:|
| lighttpd | 1 → 1 MB | 1 → 1 MB | 1 → 1 MB |
| nginx | 4 → 5 MB | 5 → 5 MB | 4 → 4 MB |
| Apache | 4 → 7 MB | 4 → 7 MB | 4 → 7 MB |
| omega-serv, mesin Python | 28 → 32 MB | 29 → 33 MB | 30 → 34 MB |
| **omega-serv, mesin native** | **33 → 34 MB** | **34 → 35 MB** | **35 → 39 MB** |
| omega-serv, native + WAF † | 45 → 47 MB | 43 → 44 MB | 44 → 48 MB |
| omega-serv, mesin Python, 2 proses | 40 → 50 MB | 43 → 51 MB | 42 → 51 MB |
| omega-serv, native + WAF, 2 proses keamanan † | 45 → 47 MB | 43 → 44 MB | 55 → 57 MB |
| Caddy, 2 proses | 50 → 57 MB | 46 → 54 MB | 48 → 62 MB |

### Dengan jumlah inti yang sama: mesin C dengan 4 proses

Sesi terpisah pada 3 November, prosedur yang sama, di mesin C: setiap server mendapat 4 proses (atau 4 inti untuk Caddy dan mesin native). Acuan: nginx dengan 4 proses. Mesin native dengan WAF tidak lagi muncul di sini: ia diukur sebelum optimasi WAF dan belum diukur ulang dengan 4 proses.

| Server | 1 KB | 100 KB | 5 MB | Memori |
|---|---:|---:|---:|---:|
| lighttpd, 4 proses | 638 907 (**1,46**) | 312 402 (**1,21**) | 41 982 MB/s (0,93) | 1 → 2 MB |
| nginx, 4 proses | 438 496 (1,00) | 258 242 (1,00) | 45 162 MB/s (1,00) | 5 → 5 MB |
| **omega-serv, mesin native** | **294 083–310 972 (0,67–0,71)** | **108 991–109 955 (0,42)** | **40 137–40 463 MB/s (0,89–0,90)** | **35 → 38 MB** |
| Apache, 4 proses | 200 592 (0,46) | 162 607 (0,63) | 39 664 MB/s (0,88) | 6 → 9 MB |
| Caddy, 4 inti | 97 085 (0,22) | 35 900 (0,14) | 5 998 MB/s (0,13) | 52 → 67 MB |
| omega-serv, mesin Python, 4 proses | 37 697 (0,09) | 35 064 (0,14) | 37 123 MB/s (0,82) | 48 → 66 MB |

### Kesimpulan

- **Mesin native mengubah posisi omega-serv.**
  - Pada berkas kecil, ia naik dari 0,03–0,11 dari nginx (mesin Python) menjadi sekitar **0,7 dari nginx**, di mesin apa pun.
  - Ia berada di depan Apache dan Caddy, dan di belakang nginx dan lighttpd, yang tetap tercepat.
  - Latensi p99-nya mendekati nginx.
- **lighttpd tercepat pada berkas kecil dan sedang**, di ketiga mesin, dan paling hemat memori. Namun dokumentasinya tidak menganjurkan `server.max-worker` (banyak proses), yang kami gunakan untuk membandingkan dengan jumlah proses yang sama.
- **Berkas sedang adalah kelemahan mesin native saat ini**: 0,28–0,61 dari nginx, di belakang Apache, dan tanpa perbaikan dengan lebih banyak inti. Ini arah perbaikan yang sudah teridentifikasi.
- **Pada berkas besar**, server-server saling mendekat karena data disalin oleh kernel sistem (`sendfile`). Pengecualiannya Caddy di mesin C: kami tidak mencoba mengoptimalkan konfigurasi dasarnya.
- **WAF hanya sedikit membebani mesin native, tetapi ini harus dibaca dengan jujur.**
  - Mesin native sendiri memeriksa aturan WAF: permintaan yang tidak cocok dengan aturan mana pun dilayani tanpa Python. Sedikit saja keraguan (kecocokan, teks non-ASCII, sumber yang diawasi Active Defense, zona autentikasi…), Python yang memutuskan. Dengan WAF, mesin native dengan demikian mempertahankan 78–95 % throughput-nya pada berkas kecil dan 93–99 % pada berkas 100 KB. Sebelum optimasi ini, throughput-nya terbagi 4 hingga 7.
  - Pembatasan laju dihitung oleh mesin native: mengaktifkannya tidak mengubah angka-angka ini (mesin A: 11 391 req/s dengan pembatasan, 11 330 tanpa). Jika magnet aktif, semua permintaan tetap melewati Python, dan biayanya kembali seperti sebelumnya.
  - omega-serv dengan WAF tetap di depan Apache dan Caddy **tanpa** WAF.
  - nginx, lighttpd, Apache, dan Caddy diukur **tanpa** WAF. WAF yang ditambahkan pada server-server ini (ModSecurity, Coraza) juga memiliki biaya, yang tidak kami ukur. Karena itu perbandingan "dengan WAF" tidak setara, dan kami tidak mengklaim bahwa omega-serv akan lebih cepat daripada server lain dengan WAF.
- **Banyak proses keamanan tidak lagi membantu lalu lintas normal**: lalu lintas itu tidak lagi melewatinya, dan throughput dengan 2 proses tetap sama (−2 hingga −4 %, dalam derau pengukuran). Proses-proses ini hanya berguna saat banyak permintaan melewati Python (magnet aktif, serangan): menurut pengukuran sebelum optimasi, ketika semua permintaan melewatinya, 2 proses keamanan mengalikan throughput dengan WAF 1,5–1,7 kali pada 4 inti, tetapi hanya menambah 5–12 % pada 2 inti.
- **Mesin Python berskala dengan jumlah proses** (×1,6–×2 dengan 2 proses, sekitar ×3,5 dengan 4), tetapi tetap di 5–11 % dari nginx.
- **Memori**: omega-serv memakai beberapa puluh MB lebih banyak daripada nginx, lighttpd, atau Apache, terutama karena Python, dan sebanding dengan Caddy. Dengan mesin native tanpa WAF, memori hampir tidak berubah selama beban.
- **Untuk menimbang angka-angka ini**: bahkan kasus paling lambat, mesin Python dengan WAF di mesin B (564 req/s), setara hampir 50 juta permintaan per hari. Itu jauh melampaui kebutuhan situs pribadi, layanan internal, atau laboratorium. Kecepatan benar-benar menentukan hanya untuk situs dengan lalu lintas tinggi.

---

## 5. Versi omega-serv: 1.0 → 2.0 → 2.5

Ketiga versi diukur pada sesi yang sama dengan §4, di ketiga mesin, dengan prosedur yang sama. Dalam kurung: rasio terhadap nginx (2 proses) dari sesi yang sama. †: sesi 4 November setelah optimasi WAF (lihat §4).

### Berkas kecil (1 KB): permintaan per detik

| Versi dan mode | Mesin A | Mesin B | Mesin C |
|---|---:|---:|---:|
| 1.0.0 | 1 547 (0,07) | 645 (0,03) | 8 870 (0,04) |
| 1.0.0 + WAF | 1 453 (0,07) | 561 (0,02) | 7 687 (0,03) |
| 2.0.0 | 1 740 (0,08) | 650 (0,03) | 10 245 (0,04) |
| 2.0.0 + WAF | 1 456 (0,07) | 565 (0,02) | 8 371 (0,03) |
| 2.0.0, 2 proses | 2 153 (0,10) | 1 277 (0,05) | 19 192 (0,08) |
| 2.0.0 + WAF, 2 proses | 1 775 (0,08) | 1 113 (0,05) | 15 351 (0,06) |
| 2.5, mesin Python | 1 507 (0,07) | 663 (0,03) | 10 553 (0,04) |
| 2.5, mesin Python + WAF | 1 561 (0,07) | 564 (0,02) | 8 365 (0,03) |
| 2.5, mesin Python, 2 proses | 2 354 (0,11) | 1 312 (0,05) | 19 911 (0,08) |
| 2.5, mesin Python + WAF, 2 proses | 1 901 (0,09) | 1 104 (0,04) | 15 783 (0,06) |
| **2.5, mesin native** | **15 222 (0,70)** | **16 542 (0,67)** | **285 213 (1,15)** |
| **2.5, mesin native + WAF †** | **11 990 (0,56)** | **12 998 (0,53)** | **264 484 (1,07)** |
| **2.5, mesin native + WAF, 2 proses keamanan †** | **11 746 (0,55)** | **12 718 (0,52)** | **253 527 (1,02)** |

### Berkas sedang, berkas besar, dan memori (1 proses, tanpa WAF)

| Versi | 100 KB, req/s (A / B / C) | 5 MB, MB/s (A / B / C) | Memori saat diam → setelah beban (A / B / C) |
|---|---|---|---|
| 1.0.0 | 1 071 / 563 / 7 625 | 578 / 549 / 3 640 | 21 → **98** / 22 → **98** / 23 → **73** MB |
| 2.0.0 | 1 570 / 603 / 9 469 | 1 665 / 1 470 / 14 058 | 26 → 30 / 27 → 31 / 28 → 32 MB |
| 2.5, mesin Python | 1 329 / 611 / 9 805 | 1 686 / 1 472 / 14 227 | 28 → 32 / 29 → 33 / 30 → 34 MB |
| **2.5, mesin native** | **4 738 / 3 115 / 96 277** | **2 294 / 1 936 / 37 918** | **33 → 34 / 34 → 35 / 35 → 39 MB** |

### Unduhan besar bersamaan

Uji: 3 unduhan bersamaan berkas 300 MB, sementara halaman kecil diminta terus-menerus. Dua putaran per versi dan per mesin, dengan hasil yang hampir identik. Memori di sini adalah **RSS** dari semua proses server, seperti pada uji aslinya: ia menghitung memori bersama beberapa kali, sehingga memberi nilai lebih tinggi daripada PSS di tabel lain.

| Versi | Memori puncak | Halaman kecil, kasus terburuk: A / B / C |
|---|---:|---|
| 1.0.0 | **1 833–1 836 MB** | **1,4–1,9 s** / **1,4–1,7 s** / 0,16 s |
| 2.0.0 | 39–42 MB | 3 ms / 4–6 ms / 1 ms |
| 2.5, mesin Python | 41–44 MB | 2 ms / 4 ms / 1 ms |
| 2.5, mesin native | 49–55 MB | 1–2 ms / 2–4 ms / kurang dari 1 ms |

### Biaya pertahanan aktif (1.0 → 2.0)

Pengukuran pada 26 Oktober 2026 di mesin A, belum diulang sejak itu: biaya satu pengamatan ancaman di Active Defense untuk setiap permintaan mencurigakan, diukur pada disk (ext4) dengan 2 000 pengamatan.

| Pengukuran | 1.0.0 | 2.0.0 |
|---|---:|---:|
| Median | 2,84 ms | 0,23 ms |
| p99 | 11,6 ms | 2,3 ms |
| Maksimum | 18–20 ms | 37–46 ms |

Median berkurang 12 kali lipat. Sebaliknya, nilai maksimum lebih tinggi di 2.0: beberapa lonjakan terisolasi, terkait penulisan berkala jurnal SQLite ke disk.

### Kesimpulan

- **Dari 1.0 ke 2.0**, kemajuannya ada pada memori dan berkas besar, bukan pada kecepatan halaman kecil:
  - memori setelah beban turun dari 73–98 MB menjadi 30–32 MB;
  - selama unduhan besar, memori turun dari lebih dari 1,8 GB menjadi sekitar 40 MB, dan server tetap responsif (beberapa milidetik, bukan hampir 2 detik);
  - throughput berkas besar naik 2,7–3,9 kali;
  - 2.0 menambahkan banyak proses, yang meningkatkan throughput halaman kecil 25 % hingga hampir 100 % tergantung mesin.
  1.0 memuat setiap berkas utuh ke memori sebelum mengirimnya. 2.0 mengirimnya per blok atau menyerahkannya ke kernel sistem.
- **Dari 2.0 ke 2.5, mesin Python tidak berubah kecepatannya**: selisihnya di bawah 4 % di mesin B dan C, dan dalam derau pengukuran di mesin A (−13 % hingga +9 %), yang paling peka terhadap beban latar belakang. Seluruh keuntungan 2.5 berasal dari **mesin native**: sekitar ×10–×27 pada berkas kecil dibanding mesin Python, dan latensi berkurang 5 hingga 15 kali.
- **Mesin native memakai sekitar 5 MB lebih banyak saat diam** daripada mesin Python (PSS): itu harga program kedua. Dengan WAF, ia memakai sekitar 8 MB lagi: itu aturan yang dimuat ke mesin native.

### Yang perlu diketahui tentang mesin native

- Ia **opsional**: mesin Python tetap menjadi mesin bawaan dan mesin cadangan.
- Ia sendiri menyajikan konten statis, pengalihan, penulisan ulang, alias, cache, halaman galat, header keamanan, dan TLS.
- Ia sendiri memeriksa aturan WAF dan sendiri melayani permintaan yang tidak cocok dengan aturan mana pun. Setiap permintaan lain (kecocokan atau keraguan WAF, Active Defense, autentikasi) diputuskan oleh Python, dengan pemeriksaan dan log yang persis sama. Kontrol yang dapat dikonfigurasi tetap meneruskan ke Python satu permintaan bersih dari setiap N, untuk memastikan keduanya memberi putusan yang sama.
- Daftar direktori dan halaman internal diminta dari Python; reverse proxy, FastCGI, unggahan berkas, dan WebSocket diserahkan kepadanya untuk seluruh koneksi. Karena itu fitur-fitur ini mempertahankan kecepatan mesin Python.
- Dengan TLS langsung, reverse proxy, FastCGI, dan unggahan berkas tidak didukung oleh mesin native: mesin Python yang melayani, dan antarmuka menunjukkannya.
- Ia memerlukan glibc 2.38 atau lebih baru dan OpenSSL 3. Jika tidak dapat berjalan, instalasi akan mengompilasinya ulang di tempat, dan jika itu tidak mungkin, omega-serv tetap memakai mesin Python.

---

## 6. Perbandingan fitur

Keterangan:
- ✅ bawaan;
- 🧩 modul resmi proyek, perlu diaktifkan atau dipasang;
- 🔌 modul atau plugin pihak ketiga;
- ⚙️ melalui alat eksternal;
- ❌ tidak ada.

"Commercial" menandai fitur yang hanya tersedia di edisi berbayar.

### Layanan HTTP

| Fitur | nginx | lighttpd | Caddy | Apache | Traefik | omega-serv 2.5 |
|---|---|---|---|---|---|---|
| Bahasa server | C | C | Go | C | Go | Python, dengan mesin native C++ opsional |
| Menyajikan berkas statis | ✅ | ✅ | ✅ | ✅ | ❌ (proxy saja) | ✅ |
| ETag / 304 / Range | ✅ | ✅ | ✅ | ✅ | — | ✅ |
| Berkas terkompresi sebelumnya `.gz` / `.br` | ✅ `gzip_static` (`.br`: 🔌) | 🔌 skrip Lua (mod_magnet) | ✅ `precompressed` | 🧩 resep mod_rewrite | — | ✅ |
| Kompresi langsung | ✅ | ✅ mod_deflate | ✅ | 🧩 mod_deflate | ✅ middleware | ❌ |
| HTTP/2 | ✅ | ✅ | ✅ | 🧩 mod_http2 | ✅ | ❌ |
| HTTP/3 (QUIC) | ✅ | ❌ | ✅ | ❌ | ✅ | ❌ |
| PHP melalui FastCGI | ✅ | ✅ | ✅ | ✅ | ❌ | ✅ |
| Banyak proses atau inti | ✅ workers | ⚠️ `max-worker`, tidak dianjurkan oleh dokumentasinya | ✅ (Go, semua inti) | ✅ MPM | ✅ (Go) | ✅ `server.workers`; mesin native: semua inti |

### Reverse proxy

| Fitur | nginx | lighttpd | Caddy | Apache | Traefik | omega-serv 2.5 |
|---|---|---|---|---|---|---|
| Penyeimbangan beban | ✅ bergiliran, koneksi paling sedikit, hash | ✅ fair, round-robin, hash, sticky | ✅ sekitar selusin strategi | 🧩 mod_proxy_balancer | ✅ wrr, p2c, hrw, least-time | ✅ 7 strategi, termasuk beban nyata |
| Pemeriksaan pasif (mengeluarkan server rusak) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Pemeriksaan aktif (probe berkala) | Commercial (NGINX Plus) | ❌ | ✅ | 🧩 mod_proxy_hcheck | ✅ | ✅ |
| Cache respons | ✅ `proxy_cache` | ❌ | 🔌 | 🧩 mod_cache | Commercial | ✅ |
| WebSocket | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Penemuan layanan (Docker, Kubernetes) | 🔌 | ❌ | 🔌 | ❌ | ✅ (inti proyek) | ❌ |

### TLS

| Fitur | nginx | lighttpd | Caddy | Apache | Traefik | omega-serv 2.5 |
|---|---|---|---|---|---|---|
| Sertifikat otomatis (ACME, Let's Encrypt) | 🧩 `ngx_http_acme_module` | ⚙️ Certbot | ✅ secara bawaan | 🧩 mod_md | ✅ | ⚙️ Certbot, dengan asisten bawaan dan perpanjangan terjadwal |
| CA lokal | ❌ | ❌ | ✅ CA internal (penerbitan otomatis) | ❌ | ❌ | ✅ pembuatan, penandatanganan CSR, pencabutan |

### Keamanan

| Fitur | nginx | lighttpd | Caddy | Apache | Traefik | omega-serv 2.5 |
|---|---|---|---|---|---|---|
| Pembatasan laju per klien | ✅ `limit_req` | ⚠️ mod_evasive (koneksi bersamaan saja) | 🔌 caddy-ratelimit | 🔌 mod_evasive, mod_qos | ✅ middleware | ✅ |
| Batas bersama antarproses | ✅ zona memori bersama | ❌ dihitung per proses | — (satu proses) | tergantung modul | 1 instans; beberapa dengan Redis | ✅ memori bersama |
| WAF (tanda tangan SQLi/XSS, pemindai…) | 🔌 ModSecurity, Commercial (App Protect) | ❌ (skrip Lua ditulis sendiri) | 🔌 Coraza | 🔌 ModSecurity | 🔌 plugin | ✅ bawaan |
| Daftar blokir dengan masa berlaku, hitungan pengulangan | ⚙️ fail2ban | ⚙️ fail2ban | ⚙️ fail2ban | ⚙️ fail2ban | ⚙️ | ✅ bawaan |
| Umpan, mode perang, insiden, ekspor IoC | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ Active Defense |
| Larangan bertingkat dari waktu ke waktu | ⚙️ fail2ban | ⚙️ fail2ban | ⚙️ fail2ban | ⚙️ fail2ban | ⚙️ | ✅ RIPOSTE |
| Audit keamanan konfigurasi | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ `audit security` |
| Mode observasi (mencatat tanpa memblokir) | tergantung modul | — | tergantung plugin | ✅ ModSecurity `DetectionOnly` | tergantung plugin | ✅ |

Larangan bertingkat: larangan yang makin lama untuk alamat yang kembali, selama berminggu-minggu, secara lokal atau di tingkat jaringan. fail2ban mendapatkannya dengan opsi `bantime.increment`; RIPOSTE menambahkan kebijakan yang dapat diukur pada log dan disimulasikan sebelum diaktifkan, pencabutan tindakan, dan penghentian darurat.

### Ekstensibilitas

| Fitur | nginx | lighttpd | Caddy | Apache | Traefik | omega-serv 2.5 |
|---|---|---|---|---|---|---|
| Bahasa skrip | 🧩 njs (JavaScript); 🔌 Lua (OpenResty) | ✅ Lua (mod_magnet) | modul Go (kompilasi ulang) | 🧩 mod_lua | plugin Go atau WebAssembly | 🔌 impor skrip mod_magnet (opsi `magnet`) |
| Ekosistem modul | sangat besar | terarah | besar | sangat besar | besar | tidak ada: semuanya bawaan |

---

## 7. Administrasi dan kenyamanan

| Server | Cara administrasi utama | Antarmuka | Muat ulang tanpa gangguan |
|---|---|---|---|
| nginx | berkas konfigurasi | tidak ada (dasbor: NGINX Plus, komersial) | ✅ `nginx -s reload` |
| lighttpd | berkas konfigurasi | tidak ada (mod_status hanya baca) | ✅ restart halus |
| Caddy | Caddyfile atau JSON | API administrasi REST | ✅ melalui API |
| Apache | berkas konfigurasi dan `.htaccess` | tidak ada (mod_status hanya baca) | ✅ `graceful` |
| Traefik | label kontainer, berkas, atau Kubernetes | dasbor web (hanya baca) | ✅ konfigurasi dinamis |
| omega-serv | antarmuka terminal (TUI) dan baris perintah (CLI); tidak perlu menyunting berkas JSON | **TUI lengkap dengan papan ketik dan tetikus, 17 bahasa, bantuan bawaan** | ✅ untuk sebagian besar pengaturan; port, TLS, mesin, dan jumlah proses memberi tahu perlunya restart |

Dalam praktiknya, omega-serv mengelola konfigurasi, keamanan, log, layanan sistem, cadangan, dan instans dari satu antarmuka. Setiap pengaturan dijelaskan dan diverifikasi sebelum ditulis. Di server lain, orang menyunting berkas teks lalu memakai alat terpisah (Certbot, fail2ban, logrotate, ModSecurity, alat pemantauan…).

Sebaliknya, pendekatan "berkas konfigurasi" nginx, Apache, dan Caddy sangat mudah diotomatiskan (Ansible, kontainer, kontrol versi). omega-serv memiliki CLI untuk skrip, tetapi ekosistem otomasinya masih terbatas.

---

## 8. Kelebihan omega-serv

Bagian ini hanya memuat apa yang tidak diberikan oleh satu pun server yang dibandingkan dalam bentuk ini, tanpa modul pihak ketiga atau alat eksternal.

1. **Administrasi lengkap di antarmuka terminal.**
   - Antarmuka mencakup seluruh server: situs, keamanan, log, layanan, cadangan, dan instans.
   - Dapat dipakai dengan papan ketik dan tetikus, di server tanpa lingkungan grafis, bahkan melalui SSH.
   - Tersedia dalam 17 bahasa dan menjelaskan setiap pengaturan.
   - Server lain tidak memiliki antarmuka administrasi (nginx, lighttpd, Apache), atau hanya API (Caddy) atau dasbor hanya baca (Traefik).
2. **Keamanan aktif bawaan, tanpa merakit modul.**
   - WAF mencakup tanda tangan, daftar jalur yang dapat disunting, hitungan pengulangan, daftar blokir dengan masa berlaku, reputasi, dan mode observasi.
   - Active Defense menambahkan umpan, mode perang, pelacakan insiden, ekspor indikator kompromi, dan simulasi tanpa efek.
   - RIPOSTE bereaksi dari waktu ke waktu: ia mengingat alamat yang kembali dan menerapkan respons bertingkat kepadanya, larangan yang makin lama (bawaan 1 j, 6 j, 24 j, 7 hari), lokal di daftar blokir atau di tingkat jaringan melalui fail2ban (omega-jail), atau umpan yang diperpanjang. Setiap kebijakan dapat diukur pada log nyata dan disimulasikan sebelum diaktifkan; setiap tindakan tetap terlihat dan dapat dicabut, dan ada penghentian darurat.
   - Di server lain, fitur-fitur ini memerlukan perakitan ModSecurity atau Coraza, kumpulan aturan, dan fail2ban.
3. **Batas keamanan yang tepat dengan banyak proses.**
   - Dengan banyak proses, pembatasan laju dan hitungan pengulangan WAF dibagi di memori. Karena itu penyerang tidak dapat melipatgandakan batasnya dengan jumlah proses.
   - lighttpd mendokumentasikan kasus sebaliknya: dengan `server.max-worker`, `mod_evasive` dan `mod_status` menghitung terpisah di setiap proses.
   - nginx juga membagi penghitungnya (zona `limit_req`), tetapi tidak memiliki WAF bawaan.
4. **Dua mesin, satu perilaku.** Mesin native dan mesin Python menghasilkan respons dan log yang sama, yang diverifikasi otomatis pada bangku uji pembanding. Alat yang membaca log (misalnya fail2ban) tidak melihat perbedaan apa pun.
5. **Impor skrip mod_magnet dari lighttpd.**
   - Skrip perlindungan Lua yang sudah ditulis untuk lighttpd dapat diimpor tanpa ditulis ulang.
   - Ia melengkapi perlindungan bawaan tanpa pernah bisa melemahkannya, dan kompatibilitasnya diperiksa sebelum diaktifkan.
6. **Pengelolaan banyak instans.**
   - Sebuah registri mencatat semua instans, dan antarmuka berpindah di antaranya.
   - Ia juga dapat mencopot pemasangan sebuah instans sepenuhnya.
7. **Audit keamanan konfigurasi**: perintah `audit security` bersifat informatif, tidak pernah memblokir, dan mengembalikan kode keluar yang dapat dipakai dalam skrip.
8. **Sumber log jarak jauh.**
   - Antarmuka mengambil log server lain melalui SSH, sesuai permintaan, tanpa kata sandi tersimpan.
   - Ia dapat membacanya di lnav, digabung dengan log lokal.
9. **Pengerasan HTTP yang tidak dapat dinonaktifkan**, aktif sejak instalasi, apa pun profil dan mesinnya:
   - pemeriksaan ketat header Host;
   - penolakan ambiguitas Content-Length / Transfer-Encoding;
   - header keamanan dan CSP dalam respons situs, termasuk halaman galatnya;
   - pembacaan X-Forwarded-For yang aman;
   - penolakan untuk berjalan sebagai root.

---

## 9. Yang dilakukan server lain dengan lebih baik

- **Throughput**: lighttpd dan nginx tetap tercepat pada berkas kecil dan sedang, di ketiga mesin. Bahkan dengan mesin native, omega-serv mencapai sekitar 0,7 dari nginx dan 0,5 dari lighttpd pada berkas kecil, serta 0,3–0,6 dari nginx pada berkas 100 KB. Untuk situs dengan lalu lintas tinggi, API publik, atau CDN, pilihlah mereka.
- **Berkas sedang**: Apache menyajikan berkas 100 KB lebih cepat daripada mesin native omega-serv, di ketiga mesin.
- **Memori**: lighttpd (1 MB), nginx (4–5 MB), dan Apache (4–9 MB) cocok untuk mesin yang sangat terbatas (sistem tertanam, kontainer kecil). omega-serv memerlukan 30–65.
- **Biaya keamanan**: WAF tetap memiliki biaya. Dengan mesin native, ia mengurangi 5–22 % throughput pada berkas kecil, termasuk pembatasan laju: omega-serv dengan WAF mencapai 0,53–0,56 dari nginx tanpa WAF di mesin A dan B. Permintaan yang mencurigakan atau meragukan (kecocokan aturan, teks non-ASCII, sumber yang diawasi Active Defense) selalu melewati Python dan dilayani dengan kecepatan mesin Python. Dengan magnet aktif, semua permintaan melewati Python, dan WAF kemudian membagi throughput mesin native dengan 4 hingga 7, seperti sebelum optimasi.
- **Protokol**: HTTP/2 di semua server lain, HTTP/3 di nginx, Caddy, dan Traefik. omega-serv hanya mendukung HTTP/1.1.
- **HTTPS otomatis**: Caddy dan Traefik mengaktifkannya secara bawaan, nginx (`ngx_http_acme_module`) dan Apache (`mod_md`) dengan modul resmi. omega-serv menyerahkannya kepada Certbot, dengan asisten dan perpanjangan terjadwal.
- **Lingkungan kontainer**: penemuan layanan otomatis Traefik (Docker, Kubernetes) tidak memiliki padanan di omega-serv.
- **Ekosistem dan kematangan**: nginx dan Apache menawarkan ribuan modul, panduan, dan integrasi, serta puluhan tahun pemakaian produksi. Caddy menawarkan sistem modul Go. omega-serv adalah proyek muda, dikelola oleh satu orang, dan mesin native-nya masih sangat baru.
- **Kompresi langsung**: omega-serv hanya menyajikan berkas yang sudah dikompresi.

---

## 10. Server mana untuk kebutuhan apa

| Kebutuhan | Pilihan yang dianjurkan |
|---|---|
| Situs lalu lintas tinggi, API publik, CDN, throughput maksimum | **nginx** atau **lighttpd** |
| Mesin sangat terbatas, sistem tertanam, berkas statis | **lighttpd** |
| Mulai cepat dengan HTTPS otomatis, konfigurasi singkat | **Caddy** |
| Aplikasi PHP lama, `.htaccess`, hosting bersama | **Apache** |
| Docker, Kubernetes, layanan mikro | **Traefik** |
| Situs kecil atau sedang, layanan internal, laboratorium, VPN, administrasi tanpa menyunting berkas | **omega-serv** (mesin native jika memungkinkan) |
| Server yang terbuka ke internet, yang keamanannya (WAF, larangan bertingkat, umpan) ingin dilihat dan dikendalikan dari satu antarmuka | **omega-serv** |
| Reverse proxy internal dengan penyeimbangan, pemeriksaan, dan cache, dikelola dari antarmuka | **omega-serv** |
| Belajar pengerasan HTTP dan pertahanan aktif | **omega-serv** |

Alat-alat ini juga dapat dikombinasikan. Misalnya:
- nginx atau Traefik di depan internet, dan omega-serv di belakangnya untuk layanan internal, keamanannya, dan administrasinya;
- omega-serv sebagai reverse proxy internal di depan beberapa server aplikasi.

---

## 11. Mengulang pengukuran

Alat-alatnya disertakan dalam repositori, di `tools/bench/`. Diperlukan nginx, lighttpd, Apache, Caddy, dan oha yang terpasang, lingkungan pengembangan omega-serv (`.venv`), dan, untuk mesin native, biner yang dikompilasi di `native/omega-http-core/build-release`.

```sh
# 1. siapkan folder pengukuran (berkas uji, konfigurasi, omega-serv 1.0, 2.0, dan versi saat ini)
tools/bench/compare/setup.sh /jalur/pengukuran omega-serv-1.0.0.tar.gz omega-serv-2.0.0.tar.gz

# 2. 21 konfigurasi, 3 pengulangan bergantian (40–60 menit)
#    SRV_CPUS / CLI_CPUS: inti server dan klien (lscpu -e menampilkan topologi)
SRV_CPUS=0,1 CLI_CPUS=2,3 tools/bench/compare/campaign.sh /jalur/pengukuran > hasil.txt

# 3. median
python3 tools/bench/compare/summarize.py hasil.txt

# daftar konfigurasi lain, misalnya 4 proses
CONFIGS="nginx-4 lighttpd-4 caddy-4 apache-4 omega-v2-1-0-native omega-v2-4-1-native" \
  tools/bench/compare/campaign.sh /jalur/pengukuran > hasil-4.txt

# unduhan besar (memori dan responsivitas): versi saat ini, mesin Python, lalu native, lalu 1.0
.venv/bin/python tools/bench/bigfile.py
BENCH_ENGINE=native .venv/bin/python tools/bench/bigfile.py
BENCH_SRC=/jalur/pengukuran/v1-archive/omega-serv/src \
BENCH_EXTRA_PATH=/jalur/pengukuran/v1-archive/omega-serv/vendor/omega-lib/src \
  .venv/bin/python tools/bench/bigfile.py

# mengukur server lain mana pun yang sudah berjalan, tanpa oha
python3 tools/bench/bench_any.py --make-files /srv/webroot-uji
python3 tools/bench/bench_any.py --port 8080
```

Nama konfigurasi: `nginx-N`, `lighttpd-N`, `apache-N`, `caddy-N` (N proses, atau N inti untuk Caddy); `omega-vX-N-W` untuk omega-serv (versi `v1`, `v20`, atau `v2` untuk versi saat ini, N proses, W = 0 tanpa WAF atau 1 dengan WAF), dengan akhiran `-native` untuk mesin native.

Untuk menerbitkan hasil Anda sendiri, sebutkan mesin, versi, pembagian inti, dan tiga pengulangan.

---

## 12. Sumber

Fitur server lain menurut dokumentasi resminya (dilihat pada 26 Oktober 2026).

**nginx**
- [Pembatasan laju `limit_req` (zona memori bersama)](https://nginx.org/en/docs/http/ngx_http_limit_req_module.html)
- [Berkas terkompresi sebelumnya `gzip_static`](https://nginx.org/en/docs/http/ngx_http_gzip_static_module.html)
- [Modul ACME resmi `ngx_http_acme_module`](https://nginx.org/en/docs/http/ngx_http_acme_module.html)
- [Penyeimbangan beban (`upstream`)](https://nginx.org/en/docs/http/ngx_http_upstream_module.html)
- [HTTP/3](https://nginx.org/en/docs/http/ngx_http_v3_module.html)
- [Konektor ModSecurity untuk nginx](https://github.com/owasp-modsecurity/ModSecurity-nginx)

**lighttpd**
- [`server.max-worker`: tidak dianjurkan, penghitung per proses untuk mod_status dan mod_evasive](https://redmine.lighttpd.net/projects/lighttpd/wiki/Server_max-workerDetails)
- [mod_magnet (skrip Lua)](https://redmine.lighttpd.net/projects/lighttpd/wiki/Docs_ModMagnet)
- [mod_deflate (kompresi, cache)](https://redmine.lighttpd.net/projects/lighttpd/wiki/Mod_deflate)
- [mod_proxy (penyeimbangan, pemeriksaan pasif, WebSocket)](https://redmine.lighttpd.net/projects/lighttpd/wiki/Docs_ModProxy)
- [mod_evasive (koneksi bersamaan dari satu alamat)](https://redmine.lighttpd.net/projects/lighttpd/wiki/Docs_ModEvasive)

**Caddy**
- [HTTPS otomatis](https://caddyserver.com/docs/automatic-https)
- [`file_server` dan `precompressed`](https://caddyserver.com/docs/caddyfile/directives/file_server)
- [`reverse_proxy` (strategi, pemeriksaan aktif dan pasif)](https://caddyserver.com/docs/caddyfile/directives/reverse_proxy)
- [API administrasi](https://caddyserver.com/docs/api)
- [Plugin pembatasan laju caddy-ratelimit](https://github.com/mholt/caddy-ratelimit)
- [WAF Coraza untuk Caddy](https://github.com/corazawaf/coraza-caddy)
- [caddy-docker-proxy](https://github.com/lucaslorentz/caddy-docker-proxy)

**Apache HTTP Server**
- [MPM event](https://httpd.apache.org/docs/2.4/mod/event.html)
- [mod_md (ACME)](https://httpd.apache.org/docs/2.4/mod/mod_md.html)
- [mod_proxy_balancer](https://httpd.apache.org/docs/2.4/mod/mod_proxy_balancer.html)
- [mod_proxy_hcheck](https://httpd.apache.org/docs/2.4/mod/mod_proxy_hcheck.html)
- [mod_http2](https://httpd.apache.org/docs/2.4/mod/mod_http2.html)
- [mod_deflate, konten terkompresi sebelumnya](https://httpd.apache.org/docs/2.4/mod/mod_deflate.html)
- [ModSecurity](https://github.com/owasp-modsecurity/ModSecurity)

**Traefik**
- [Middleware `ratelimit` (di memori per instans, Redis opsional)](https://doc.traefik.io/traefik/reference/routing-configuration/http/middlewares/ratelimit/)
- [ACME](https://doc.traefik.io/traefik/https/acme/)
- [Providers (Docker, Kubernetes…)](https://doc.traefik.io/traefik/providers/overview/)

**fail2ban**
- [`jail.conf`: `bantime.increment`, `bantime.factor`, `bantime.multipliers`, `bantime.maxtime` (larangan lebih lama untuk pelanggar berulang)](https://github.com/fail2ban/fail2ban/blob/master/config/jail.conf) (dilihat pada 4 November 2026)

**Alat pengukuran**
- [oha](https://github.com/hatoo/oha)

---

*Perbandingan disusun oleh kraynux untuk omega-serv 2.5: pengukuran pada 3 dan 4 November 2026 di tiga mesin (pertahanan aktif: 26 Oktober 2026). Untuk setiap keputusan kapasitas, ukurlah di perangkat keras Anda sendiri dengan alat yang disertakan.*
