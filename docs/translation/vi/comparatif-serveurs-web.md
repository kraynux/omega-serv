<!-- Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE) -->

# omega-serv so với các máy chủ web trên thị trường

**So sánh dựa trên phép đo: nginx · lighttpd · Apache · Caddy · Traefik · omega-serv 2.5**

🌐 [Français](../../comparatif-serveurs-web.md) · [English](../en/comparatif-serveurs-web.md) · [Español](../es/comparatif-serveurs-web.md) · [Português (Brasil)](../pt-BR/comparatif-serveurs-web.md) · [Italiano](../it/comparatif-serveurs-web.md) · [Deutsch](../de/comparatif-serveurs-web.md) · [Nederlands](../nl/comparatif-serveurs-web.md) · [Polski](../pl/comparatif-serveurs-web.md) · [Русский](../ru/comparatif-serveurs-web.md) · [中文](../zh-CN/comparatif-serveurs-web.md) · **Tiếng Việt** · [ไทย](../th/comparatif-serveurs-web.md) · [Bahasa Indonesia](../id/comparatif-serveurs-web.md) · [日本語](../ja/comparatif-serveurs-web.md) · [한국어](../ko/comparatif-serveurs-web.md) · [हिन्दी](../hi/comparatif-serveurs-web.md) · [العربية](../ar/comparatif-serveurs-web.md)

Tài liệu này xác định vị trí của omega-serv giữa các máy chủ web phổ biến nhất. Nó không nhằm chỉ ra “máy chủ tốt nhất”: mỗi công cụ đáp ứng những nhu cầu khác nhau và đều có thế mạnh riêng. Nó cung cấp ba điều:

1. **các phép đo thực tế**, thực hiện trên **ba máy** rất khác nhau, với cùng một trình khách, cùng các tệp và cùng một quy trình, và có thể tái lập;
2. **so sánh tính năng**, mỗi mục đều được kiểm chứng theo tài liệu chính thức của máy chủ tương ứng (liên kết ở cuối tài liệu), có phân biệt giữa tính năng tích hợp sẵn và tính năng cần mô-đun hoặc plugin;
3. những gì omega-serv **thực sự mang lại thêm**, và những gì các máy chủ khác **làm tốt hơn nó**.

Tất cả các phép đo hiệu năng được thực hiện vào ngày 3 và 4 tháng 11 năm 2026. Không có con số nào được lấy từ trang web khác hay ước tính. Dữ liệu thô được công bố cùng tài liệu này.

---

## Mục lục

1. [Tóm tắt](#1-tóm-tắt)
2. [Cách đọc bản so sánh này](#2-cách-đọc-bản-so-sánh-này)
3. [Phương pháp đo](#3-phương-pháp-đo)
4. [Hiệu năng: omega-serv so với nginx, lighttpd, Apache và Caddy](#4-hiệu-năng-omega-serv-so-với-nginx-lighttpd-apache-và-caddy)
5. [Các phiên bản omega-serv: 1.0 → 2.0 → 2.5](#5-các-phiên-bản-omega-serv-10--20--25)
6. [So sánh tính năng](#6-so-sánh-tính-năng)
7. [Quản trị và sự tiện lợi](#7-quản-trị-và-sự-tiện-lợi)
8. [Những gì omega-serv mang lại thêm](#8-những-gì-omega-serv-mang-lại-thêm)
9. [Những gì các máy chủ khác làm tốt hơn](#9-những-gì-các-máy-chủ-khác-làm-tốt-hơn)
10. [Máy chủ nào cho nhu cầu nào](#10-máy-chủ-nào-cho-nhu-cầu-nào)
11. [Tái lập các phép đo](#11-tái-lập-các-phép-đo)
12. [Nguồn](#12-nguồn)

---

## 1. Tóm tắt

- **omega-serv có hai bộ máy.** **Bộ máy Python** xử lý mọi thứ. **Bộ máy native**, viết bằng C++ và có từ bản 2.5, tự phục vụ các yêu cầu; Python giữ cấu hình và các quyết định bảo mật, còn bộ máy native tự nhận biết các yêu cầu không khớp với quy tắc WAF nào.
- **Với bộ máy native, không bật WAF**, omega-serv phục vụ tệp nhỏ với tốc độ **khoảng 0,7 so với nginx**, trên cả ba máy. Như vậy nó đứng **trước Apache và Caddy, sau nginx và lighttpd**.
- **Với bộ máy Python**, omega-serv tụt xa so với tất cả các máy chủ khác: **3–11 % tốc độ của nginx**.
- **Khi bật WAF**, omega-serv kiểm tra mọi yêu cầu, điều mà các máy chủ khác được đo không làm. Với bộ máy native, nó khi đó đạt **0,53–0,56** tốc độ của nginx (không WAF) trên máy A và B, và 1,07 trên máy C (4 lõi so với 2): WAF chỉ làm nó mất 5–22 % thông lượng. Nó vẫn đứng trước Apache và Caddy, vốn được đo không có WAF.
- **Tệp trung bình (100 KB)**: đây là điểm yếu hiện tại của bộ máy native, **0,3–0,6** so với nginx, sau Apache.
- **Tệp lớn (5 MB)**: nginx, lighttpd, Apache và omega-serv native đạt thông lượng cùng cỡ. Caddy chậm hơn rõ rệt trên máy nhanh nhất.
- **Bộ nhớ**: lighttpd (1 MB), nginx (4–5 MB) và Apache (4–9 MB) rất tiết kiệm. omega-serv dùng **30–65 MB** tùy chế độ, Caddy **50–67 MB**.
- **Những gì omega-serv có thêm**: quản trị toàn bộ trong giao diện terminal, bằng 17 ngôn ngữ; WAF và phòng thủ chủ động tích hợp sẵn; giới hạn bảo mật chính xác khi chạy nhiều tiến trình; nhập script mod_magnet của lighttpd; quản lý nhiều instance.
- **Những gì nó không có**: HTTP/2 và HTTP/3, nén trực tiếp, khám phá dịch vụ Docker/Kubernetes, trình khách ACME tích hợp (nó dùng Certbot), hệ sinh thái mô-đun.

---

## 2. Cách đọc bản so sánh này

Một vài khái niệm xuất hiện xuyên suốt tài liệu.

- **Yêu cầu mỗi giây (req/s)**: số tệp mà máy chủ gửi đi trong một giây. Càng cao càng tốt.
- **Khoảng cách so với nginx**: giá trị tuyệt đối phụ thuộc nhiều vào máy. Trên ba máy của chúng tôi, nginx đạt từ 22 000 đến 440 000 req/s. Điều ổn định là **tỷ lệ giữa các máy chủ**. Vì vậy các bảng đưa ra, bên cạnh mỗi giá trị, tỷ lệ của nó so với nginx đo trong cùng đợt: **1,00 = nhanh bằng nginx**, 0,50 = chậm bằng một nửa, 1,50 = nhanh gấp rưỡi.
- **Độ trễ p99**: thời gian phản hồi mà 99 % yêu cầu không vượt quá. Nó cho thấy những “khoảnh khắc tồi tệ” mà giá trị trung bình che giấu.
- **PSS (*Proportional Set Size*)**: bộ nhớ thực sự được dùng bởi tất cả tiến trình của máy chủ. Một trang dùng chung bởi nhiều tiến trình chỉ được tính một lần.
- **Tiến trình và lõi**: một máy chủ có thể dùng nhiều lõi bộ xử lý. Mỗi máy chủ làm theo cách riêng. nginx, lighttpd, Apache và omega-serv ở chế độ Python khởi chạy nhiều tiến trình. Caddy, viết bằng Go, phân chia công việc lên các lõi. Bộ máy native của omega-serv khởi chạy một luồng cho mỗi lõi khả dụng. Để so sánh công bằng, chúng tôi cho mỗi máy chủ **cùng các lõi**.
- **WAF (*Web Application Firewall*)**: bộ lọc kiểm tra mọi yêu cầu để chặn các cuộc tấn công (tiêm mã, công cụ quét…). omega-serv tích hợp sẵn nó. Các máy chủ khác có thể có nó dưới dạng mô-đun (ModSecurity, Coraza), nhưng **chúng được đo không có nó**, với cấu hình cơ bản.

**Phản xạ đúng**: so sánh tỷ lệ chứ không phải giá trị tuyệt đối, và luôn kiểm tra xem WAF có được bật không.

---

## 3. Phương pháp đo

### Ba máy

| | Máy A | Máy B | Máy C |
|---|---|---|---|
| Bộ xử lý | Intel Core i5 M480, 2,67 GHz (2010) | Intel Celeron J3455, 1,5 GHz (2016) | AMD Ryzen AI 9 365 (2024) |
| Lõi | 2 lõi vật lý, 4 luồng | 4 lõi, không hyperthreading | 10 lõi (4 Zen 5 + 6 Zen 5c), 20 luồng |
| Bộ nhớ | 8 GB | 8 GB | 32 GB |
| Hệ thống | Mabox Linux (dựa trên Manjaro), nhân 6.18 | EndeavourOS, nhân 7.2 | Arch Linux, nhân 7.2 (CachyOS) |
| Lõi cho máy chủ | 1 lõi vật lý (luồng 0 và 2) | 2 lõi (0 và 1) | 4 lõi Zen 5, mỗi lõi một luồng (0–3) |
| Lõi cho trình khách | 1 lõi vật lý (luồng 1 và 3) | 2 lõi (2 và 3) | 6 lõi Zen 5c (4–9) |

Máy A là một laptop cũ, máy B là một mini PC tiết kiệm điện, máy C là một laptop mới, cắm sạc, ở chế độ năng lượng “cân bằng”. Chúng trải dài từ máy chủ gia đình nhỏ đến máy hiện đại.

### Phần mềm

| Phần mềm | Phiên bản |
|---|---|
| nginx | 1.30.4 (A), 1.30.5 (B, C) |
| lighttpd | 1.4.85 |
| Apache HTTP Server | 2.4.69, MPM `event` |
| Caddy | 2.11.4 (A, B), 2.11.7 (C) |
| omega-serv | 1.0.0 và 2.0.0 (các gói lưu trữ đã phát hành) và 2.5, trên Python 3.14 |
| Trình khách tạo tải | [oha](https://github.com/hatoo/oha) 1.16.0 (viết bằng Rust) |

Traefik không được đo: nó không phải máy chủ tệp (xem §6). Nó chỉ xuất hiện trong phần so sánh tính năng.

### Quy trình

- **Cô lập bộ xử lý**: máy chủ và trình khách được gắn vào các lõi khác nhau (bảng trên). Trình khách không lấy thời gian của máy chủ, và mọi máy chủ có chính xác cùng tài nguyên.
- **Cùng các tệp cho tất cả**: `small.html` (1 KB), `medium.png` (100 KB) và `large.bin` (5 MB), phục vụ từ cùng một thư mục.
- **Nhật ký truy cập được bật ở mọi nơi**, vì một máy chủ đang vận hành sẽ ghi nhật ký.
- **HTTP/1.1 không mã hóa, kết nối bền (keep-alive)**. Độ đồng thời là 32 kết nối cho tệp 1 KB và 100 KB, và 8 cho tệp 5 MB.
- **Thời lượng**: 10 giây cho mỗi tệp và mỗi cấu hình.
- **Lặp lại**: 3 lượt đầy đủ xen kẽ (tất cả cấu hình ở lượt 1, rồi tất cả ở lượt 2, v.v.). Các bảng đưa ra **trung vị** của ba lượt. Từ lượt này sang lượt khác, chênh lệch phần lớn dưới 5 %.
- **Bộ nhớ**: PSS của tất cả tiến trình máy chủ, ghi lúc nghỉ rồi sau khi tải.
- **Cấu hình**:
  - nginx, lighttpd, Apache và Caddy ở cấu hình cơ bản: tệp tĩnh và nhật ký truy cập;
  - omega-serv với hồ sơ `standard`, tắt WAF, rồi bật với tất cả quy tắc đi kèm (không giới hạn tốc độ).
- **Số tiến trình**: mỗi máy chủ được đo với 1 rồi 2 tiến trình: nginx `worker_processes`, lighttpd `server.max-worker`, Apache `StartServers`/`ServerLimit`, Caddy `GOMAXPROCS`, omega-serv `server.workers`. Với bộ máy native của omega-serv, `server.workers` đếm các tiến trình bảo mật Python; bản thân bộ máy native luôn dùng tất cả các lõi được cấp.
- **Không có lỗi nào**: mọi phản hồi của mọi phép đo đều là 200.

### Giới hạn cần biết

- **Chúng tôi so sánh tỷ lệ.** Giá trị tuyệt đối trên phần cứng của bạn hoặc trên một máy chủ chuyên dụng sẽ khác.
- **Giao diện loopback (127.0.0.1)**: phép đo không đi qua mạng thật. Trên mạng thật, thông lượng tệp lớn hầu như luôn bị giới hạn bởi đường truyền chứ không phải máy chủ. Thông lượng vài chục GB/s trên máy C chỉ có thể có trên loopback.
- **Không có TLS** trong các phép đo này.
- **Máy A**: dịch vụ omega-serv đang vận hành của máy này chạy nền, không nhận lưu lượng.
- **Máy C**: bộ xử lý lai (lõi Zen 5 và Zen 5c). Máy chủ nhận 4 lõi nhanh, trình khách nhận 6 lõi còn lại.
- **Cấu hình cơ bản**: không máy chủ nào được tối ưu. Một quản trị viên giàu kinh nghiệm chắc chắn sẽ khai thác được nhiều hơn từ mỗi máy chủ, kể cả omega-serv.
- **Dữ liệu thô**: [`docs/benchmarks/`](../../benchmarks/) (mỗi máy một tệp).

---

## 4. Hiệu năng: omega-serv so với nginx, lighttpd, Apache và Caddy

Trong mọi bảng, mốc tham chiếu là **nginx với 2 tiến trình** (= 1,00), đo trong cùng đợt trên cùng máy. Trên máy A và B, đó là cấu hình dùng hết các lõi cấp cho máy chủ.

### Tệp nhỏ (1 KB): yêu cầu mỗi giây

| Máy chủ | Máy A | Máy B | Máy C |
|---|---:|---:|---:|
| lighttpd, 2 tiến trình | 33 138 (**1,52**) | 31 125 (**1,26**) | 378 590 (**1,53**) |
| nginx, 2 tiến trình | 21 801 (1,00) | 24 705 (1,00) | 248 184 (1,00) |
| **omega-serv, bộ máy native** | **15 222 (0,70)** | **16 542 (0,67)** | **285 213 (1,15 \*)** |
| omega-serv, native + WAF † | 11 990 (0,56) | 12 998 (0,53) | 264 484 (1,07 \*) |
| omega-serv, native + WAF, 2 tiến trình bảo mật † | 11 746 (0,55) | 12 718 (0,52) | 253 527 (1,02 \*) |
| Apache, 2 tiến trình | 9 192 (0,42) | 8 634 (0,35) | 188 335 (0,76) |
| Caddy, 2 tiến trình | 5 749 (0,26) | 4 116 (0,17) | 52 897 (0,21) |
| omega-serv, bộ máy Python, 2 tiến trình | 2 354 (0,11) | 1 312 (0,05) | 19 911 (0,08) |
| omega-serv, Python + WAF, 2 tiến trình | 1 901 (0,09) | 1 104 (0,04) | 15 783 (0,06) |
| omega-serv, bộ máy Python | 1 507 (0,07) | 663 (0,03) | 10 553 (0,04) |
| omega-serv, Python + WAF | 1 561 (0,07) | 564 (0,02) | 8 365 (0,03) |

\* Trên máy C, bộ máy native dùng 4 lõi của nó, trong khi nginx với 2 tiến trình chỉ dùng 2. So sánh với cùng số lõi ở bên dưới: tỷ lệ khi đó lại là **0,67–0,71**, như trên các máy khác.

† Đo ngày 4 tháng 11, sau khi tối ưu WAF, trong một đợt riêng theo cùng quy trình. Tỷ lệ tính so với nginx (2 tiến trình) của đợt này: 21 439, 24 424 và 248 127 req/s cho tệp nhỏ, 11 545, 11 004 và 157 491 cho tệp 100 KB. Trước khi tối ưu, bộ máy native với WAF đạt 3 495, 2 622 và 39 000 req/s (0,11–0,16 so với nginx), vì mỗi yêu cầu đều đi qua Python. Dữ liệu thô: các tệp `*-waf-natif-brut.txt`.

Với 1 tiến trình, nginx đạt 0,52–0,73, lighttpd 0,81–1,43, Apache 0,33–0,74 và Caddy 0,09–0,17 (dữ liệu thô).

### Độ trễ p99 với tệp nhỏ

| Máy chủ | Máy A | Máy B | Máy C |
|---|---:|---:|---:|
| lighttpd, 2 tiến trình | 4,4 ms | 4,1 ms | 0,2 ms |
| nginx, 2 tiến trình | 4,9 ms | 5,2 ms | 0,2 ms |
| **omega-serv, bộ máy native** | **6,1 ms** | **6,2 ms** | **0,3 ms** |
| omega-serv, native + WAF † | 7,2 ms | 6,7 ms | 0,3 ms |
| Apache, 2 tiến trình | 18,8 ms | 20,6 ms | 0,8 ms |
| Caddy, 2 tiến trình | 24,1 ms | 30,5 ms | 2,8 ms |
| omega-serv, bộ máy Python, 2 tiến trình | 22,6 ms | 28,1 ms | 3,3 ms |
| omega-serv, bộ máy Python | 32,0 ms | 51,6 ms | 4,4 ms |

### Tệp trung bình (100 KB): yêu cầu mỗi giây

| Máy chủ | Máy A | Máy B | Máy C |
|---|---:|---:|---:|
| lighttpd, 2 tiến trình | 13 561 (**1,08**) | 12 126 (**1,07**) | 197 905 (**1,26**) |
| nginx, 2 tiến trình | 12 513 (1,00) | 11 303 (1,00) | 157 224 (1,00) |
| Apache, 2 tiến trình | 6 939 (0,55) | 7 035 (0,62) | 153 265 (0,97) |
| Caddy, 2 tiến trình | 5 059 (0,40) | 3 744 (0,33) | 22 094 (0,14) |
| **omega-serv, bộ máy native** | **4 738 (0,38)** | **3 115 (0,28)** | **96 277 (0,61)** |
| omega-serv, native + WAF † | 4 229 (0,37) | 2 926 (0,27) | 98 185 (0,62) |
| omega-serv, bộ máy Python, 2 tiến trình | 1 741 (0,14) | 1 154 (0,10) | 18 806 (0,12) |
| omega-serv, bộ máy Python | 1 329 (0,11) | 611 (0,05) | 9 805 (0,06) |

### Tệp lớn (5 MB): thông lượng

| Máy chủ | Máy A | Máy B | Máy C |
|---|---:|---:|---:|
| lighttpd, 2 tiến trình | 2 440 MB/s (1,05) | 2 110 MB/s (0,99) | 28 011 MB/s (0,81) |
| nginx, 2 tiến trình | 2 322 MB/s (1,00) | 2 124 MB/s (1,00) | 34 651 MB/s (1,00) |
| Apache, 2 tiến trình | 2 355 MB/s (1,01) | 2 134 MB/s (1,00) | 41 153 MB/s (**1,19**) |
| **omega-serv, bộ máy native** | **2 294 MB/s (0,99)** | **1 936 MB/s (0,91)** | **37 918 MB/s (1,09)** |
| Caddy, 2 tiến trình | 2 205 MB/s (0,95) | 1 996 MB/s (0,94) | 3 811 MB/s (0,11) |
| omega-serv, bộ máy Python, 2 tiến trình | 2 145 MB/s (0,92) | 1 931 MB/s (0,91) | 25 829 MB/s (0,75) |
| omega-serv, bộ máy Python | 1 686 MB/s (0,73) | 1 472 MB/s (0,69) | 14 227 MB/s (0,41) |

### Bộ nhớ (PSS, tất cả tiến trình máy chủ): lúc nghỉ → sau tải

| Máy chủ | Máy A | Máy B | Máy C |
|---|---:|---:|---:|
| lighttpd | 1 → 1 MB | 1 → 1 MB | 1 → 1 MB |
| nginx | 4 → 5 MB | 5 → 5 MB | 4 → 4 MB |
| Apache | 4 → 7 MB | 4 → 7 MB | 4 → 7 MB |
| omega-serv, bộ máy Python | 28 → 32 MB | 29 → 33 MB | 30 → 34 MB |
| **omega-serv, bộ máy native** | **33 → 34 MB** | **34 → 35 MB** | **35 → 39 MB** |
| omega-serv, native + WAF † | 45 → 47 MB | 43 → 44 MB | 44 → 48 MB |
| omega-serv, bộ máy Python, 2 tiến trình | 40 → 50 MB | 43 → 51 MB | 42 → 51 MB |
| omega-serv, native + WAF, 2 tiến trình bảo mật † | 45 → 47 MB | 43 → 44 MB | 55 → 57 MB |
| Caddy, 2 tiến trình | 50 → 57 MB | 46 → 54 MB | 48 → 62 MB |

### Cùng số lõi: máy C với 4 tiến trình

Một đợt riêng ngày 3 tháng 11, cùng quy trình, trên máy C: mỗi máy chủ nhận 4 tiến trình (hoặc 4 lõi với Caddy và bộ máy native). Tham chiếu: nginx với 4 tiến trình. Bộ máy native với WAF không còn xuất hiện ở đây: nó được đo trước khi tối ưu WAF và chưa được đo lại với 4 tiến trình.

| Máy chủ | 1 KB | 100 KB | 5 MB | Bộ nhớ |
|---|---:|---:|---:|---:|
| lighttpd, 4 tiến trình | 638 907 (**1,46**) | 312 402 (**1,21**) | 41 982 MB/s (0,93) | 1 → 2 MB |
| nginx, 4 tiến trình | 438 496 (1,00) | 258 242 (1,00) | 45 162 MB/s (1,00) | 5 → 5 MB |
| **omega-serv, bộ máy native** | **294 083–310 972 (0,67–0,71)** | **108 991–109 955 (0,42)** | **40 137–40 463 MB/s (0,89–0,90)** | **35 → 38 MB** |
| Apache, 4 tiến trình | 200 592 (0,46) | 162 607 (0,63) | 39 664 MB/s (0,88) | 6 → 9 MB |
| Caddy, 4 lõi | 97 085 (0,22) | 35 900 (0,14) | 5 998 MB/s (0,13) | 52 → 67 MB |
| omega-serv, bộ máy Python, 4 tiến trình | 37 697 (0,09) | 35 064 (0,14) | 37 123 MB/s (0,82) | 48 → 66 MB |

### Kết luận

- **Bộ máy native thay đổi vị trí của omega-serv.**
  - Với tệp nhỏ, nó tăng từ 0,03–0,11 so với nginx (bộ máy Python) lên khoảng **0,7 so với nginx**, trên mọi máy.
  - Nó đứng trước Apache và Caddy và sau nginx và lighttpd, vốn vẫn nhanh nhất.
  - Độ trễ p99 của nó gần với nginx.
- **lighttpd nhanh nhất với tệp nhỏ và trung bình**, trên cả ba máy, và tiết kiệm bộ nhớ nhất. Tuy vậy tài liệu của nó không khuyến nghị `server.max-worker` (nhiều tiến trình), thứ chúng tôi dùng để so sánh với cùng số tiến trình.
- **Tệp trung bình là điểm yếu hiện tại của bộ máy native**: 0,28–0,61 so với nginx, sau Apache, và không cải thiện khi có thêm lõi. Đây là một hướng cải tiến đã được xác định.
- **Với tệp lớn**, các máy chủ tiến lại gần nhau vì dữ liệu được nhân hệ điều hành sao chép (`sendfile`). Ngoại lệ là Caddy trên máy C: chúng tôi không tìm cách tối ưu cấu hình cơ bản của nó.
- **WAF tốn ít của bộ máy native, nhưng cần đọc một cách trung thực.**
  - Bộ máy native tự kiểm tra các quy tắc WAF: một yêu cầu không khớp quy tắc nào được phục vụ mà không cần Python. Chỉ cần có chút nghi ngờ (khớp, văn bản không phải ASCII, nguồn đang bị Active Defense theo dõi, vùng xác thực…), Python sẽ quyết định. Nhờ vậy, khi bật WAF, bộ máy native giữ được 78–95 % thông lượng với tệp nhỏ và 93–99 % với tệp 100 KB. Trước khi tối ưu, thông lượng của nó bị chia cho 4 đến 7.
  - Giới hạn tốc độ do bộ máy native đếm: bật nó không làm thay đổi các con số này (máy A: 11 391 req/s khi bật, 11 330 khi tắt). Nếu magnet được bật, mọi yêu cầu vẫn đi qua Python và chi phí trở lại như trước.
  - omega-serv có WAF vẫn đứng trước Apache và Caddy **không có** WAF.
  - nginx, lighttpd, Apache và Caddy được đo **không có** WAF. Một WAF thêm vào các máy chủ này (ModSecurity, Coraza) cũng có chi phí riêng, mà chúng tôi không đo. Vì vậy phép so sánh “có WAF” không ngang hàng, và chúng tôi không khẳng định omega-serv sẽ nhanh hơn một máy chủ khác có WAF.
- **Nhiều tiến trình bảo mật không còn giúp ích cho lưu lượng bình thường**: lưu lượng đó không còn đi qua chúng, và thông lượng với 2 tiến trình vẫn như cũ (−2 đến −4 %, nằm trong nhiễu đo). Chúng chỉ hữu ích khi có nhiều yêu cầu đi qua Python (bật magnet, bị tấn công): theo các phép đo trước khi tối ưu, khi mọi yêu cầu đều đi qua chúng, 2 tiến trình bảo mật nhân thông lượng có WAF lên 1,5–1,7 lần trên 4 lõi, nhưng chỉ thêm 5–12 % trên 2 lõi.
- **Bộ máy Python mở rộng theo số tiến trình** (×1,6–×2 với 2 tiến trình, khoảng ×3,5 với 4), nhưng vẫn ở mức 5–11 % so với nginx.
- **Bộ nhớ**: omega-serv dùng nhiều hơn nginx, lighttpd hay Apache vài chục MB, chủ yếu do Python, và tương đương Caddy. Với bộ máy native không WAF, bộ nhớ gần như không đổi trong lúc tải.
- **Để hình dung các con số này**: ngay cả trường hợp chậm nhất, bộ máy Python có WAF trên máy B (564 req/s), cũng gần 50 triệu yêu cầu mỗi ngày. Con số này vượt xa nhu cầu của một trang cá nhân, một dịch vụ nội bộ hay một phòng thí nghiệm. Tốc độ chỉ thực sự quyết định với một trang có lưu lượng lớn.

---

## 5. Các phiên bản omega-serv: 1.0 → 2.0 → 2.5

Ba phiên bản được đo trong cùng đợt với §4, trên cả ba máy, cùng quy trình. Trong ngoặc: tỷ lệ so với nginx (2 tiến trình) của cùng đợt. †: đợt ngày 4 tháng 11 sau khi tối ưu WAF (xem §4).

### Tệp nhỏ (1 KB): yêu cầu mỗi giây

| Phiên bản và chế độ | Máy A | Máy B | Máy C |
|---|---:|---:|---:|
| 1.0.0 | 1 547 (0,07) | 645 (0,03) | 8 870 (0,04) |
| 1.0.0 + WAF | 1 453 (0,07) | 561 (0,02) | 7 687 (0,03) |
| 2.0.0 | 1 740 (0,08) | 650 (0,03) | 10 245 (0,04) |
| 2.0.0 + WAF | 1 456 (0,07) | 565 (0,02) | 8 371 (0,03) |
| 2.0.0, 2 tiến trình | 2 153 (0,10) | 1 277 (0,05) | 19 192 (0,08) |
| 2.0.0 + WAF, 2 tiến trình | 1 775 (0,08) | 1 113 (0,05) | 15 351 (0,06) |
| 2.5, bộ máy Python | 1 507 (0,07) | 663 (0,03) | 10 553 (0,04) |
| 2.5, bộ máy Python + WAF | 1 561 (0,07) | 564 (0,02) | 8 365 (0,03) |
| 2.5, bộ máy Python, 2 tiến trình | 2 354 (0,11) | 1 312 (0,05) | 19 911 (0,08) |
| 2.5, bộ máy Python + WAF, 2 tiến trình | 1 901 (0,09) | 1 104 (0,04) | 15 783 (0,06) |
| **2.5, bộ máy native** | **15 222 (0,70)** | **16 542 (0,67)** | **285 213 (1,15)** |
| **2.5, bộ máy native + WAF †** | **11 990 (0,56)** | **12 998 (0,53)** | **264 484 (1,07)** |
| **2.5, bộ máy native + WAF, 2 tiến trình bảo mật †** | **11 746 (0,55)** | **12 718 (0,52)** | **253 527 (1,02)** |

### Tệp trung bình, tệp lớn và bộ nhớ (1 tiến trình, không WAF)

| Phiên bản | 100 KB, req/s (A / B / C) | 5 MB, MB/s (A / B / C) | Bộ nhớ lúc nghỉ → sau tải (A / B / C) |
|---|---|---|---|
| 1.0.0 | 1 071 / 563 / 7 625 | 578 / 549 / 3 640 | 21 → **98** / 22 → **98** / 23 → **73** MB |
| 2.0.0 | 1 570 / 603 / 9 469 | 1 665 / 1 470 / 14 058 | 26 → 30 / 27 → 31 / 28 → 32 MB |
| 2.5, bộ máy Python | 1 329 / 611 / 9 805 | 1 686 / 1 472 / 14 227 | 28 → 32 / 29 → 33 / 30 → 34 MB |
| **2.5, bộ máy native** | **4 738 / 3 115 / 96 277** | **2 294 / 1 936 / 37 918** | **33 → 34 / 34 → 35 / 35 → 39 MB** |

### Tải xuống lớn đồng thời

Thử nghiệm: 3 lượt tải đồng thời một tệp 300 MB, trong khi một trang nhỏ được yêu cầu liên tục. Hai lượt cho mỗi phiên bản và mỗi máy, với kết quả gần như giống nhau. Bộ nhớ ở đây là **RSS** của tất cả tiến trình máy chủ, như trong thử nghiệm gốc: nó tính bộ nhớ dùng chung nhiều lần, nên cho giá trị cao hơn PSS ở các bảng khác.

| Phiên bản | Bộ nhớ cao nhất | Trang nhỏ, trường hợp xấu nhất: A / B / C |
|---|---:|---|
| 1.0.0 | **1 833–1 836 MB** | **1,4–1,9 s** / **1,4–1,7 s** / 0,16 s |
| 2.0.0 | 39–42 MB | 3 ms / 4–6 ms / 1 ms |
| 2.5, bộ máy Python | 41–44 MB | 2 ms / 4 ms / 1 ms |
| 2.5, bộ máy native | 49–55 MB | 1–2 ms / 2–4 ms / dưới 1 ms |

### Chi phí của phòng thủ chủ động (1.0 → 2.0)

Phép đo ngày 26 tháng 10 năm 2026 trên máy A, chưa đo lại kể từ đó: chi phí của một lần ghi nhận mối đe dọa trong Active Defense cho mỗi yêu cầu đáng ngờ, đo trên đĩa (ext4) với 2 000 lần ghi nhận.

| Phép đo | 1.0.0 | 2.0.0 |
|---|---:|---:|
| Trung vị | 2,84 ms | 0,23 ms |
| p99 | 11,6 ms | 2,3 ms |
| Tối đa | 18–20 ms | 37–46 ms |

Trung vị giảm 12 lần. Ngược lại, giá trị tối đa ở 2.0 cao hơn: vài đỉnh riêng lẻ, liên quan đến việc ghi định kỳ nhật ký SQLite ra đĩa.

### Kết luận

- **Từ 1.0 lên 2.0**, tiến bộ nằm ở bộ nhớ và tệp lớn, chứ không ở tốc độ trang nhỏ:
  - bộ nhớ sau tải giảm từ 73–98 MB xuống 30–32 MB;
  - trong khi tải xuống lớn, nó giảm từ hơn 1,8 GB xuống khoảng 40 MB, và máy chủ vẫn phản hồi tốt (vài mili giây thay vì gần 2 giây);
  - thông lượng tệp lớn tăng 2,7–3,9 lần;
  - 2.0 bổ sung nhiều tiến trình, giúp tăng thông lượng trang nhỏ từ 25 % đến gần 100 % tùy máy.
  1.0 nạp toàn bộ mỗi tệp vào bộ nhớ trước khi gửi. 2.0 gửi theo từng khối hoặc giao cho nhân hệ điều hành.
- **Từ 2.0 lên 2.5, bộ máy Python không đổi tốc độ**: chênh lệch dưới 4 % trên máy B và C, và nằm trong nhiễu đo trên máy A (−13 % đến +9 %), máy nhạy nhất với tải nền. Toàn bộ lợi ích của 2.5 đến từ **bộ máy native**: khoảng ×10–×27 với tệp nhỏ so với bộ máy Python, và độ trễ giảm 5 đến 15 lần.
- **Bộ máy native dùng nhiều hơn bộ máy Python khoảng 5 MB lúc nghỉ** (PSS): đó là cái giá của chương trình thứ hai. Có WAF, nó dùng thêm khoảng 8 MB nữa: đó là các quy tắc được nạp vào bộ máy native.

### Điều cần biết về bộ máy native

- Nó là **tùy chọn**: bộ máy Python vẫn là bộ máy mặc định và dự phòng.
- Nó tự phục vụ nội dung tĩnh, chuyển hướng, viết lại, bí danh, bộ nhớ đệm, trang lỗi, tiêu đề bảo mật và TLS.
- Nó tự kiểm tra các quy tắc WAF và tự phục vụ yêu cầu không khớp quy tắc nào. Mọi yêu cầu khác (WAF khớp hoặc nghi ngờ, Active Defense, xác thực) do Python quyết định, với chính xác cùng các kiểm tra và cùng nhật ký. Một cơ chế kiểm soát có thể cấu hình vẫn chuyển cho Python một yêu cầu sạch trong N yêu cầu, để xác minh cả hai đưa ra cùng phán quyết.
- Danh sách thư mục và các trang nội bộ được yêu cầu từ Python; reverse proxy, FastCGI, tải tệp lên và WebSocket được giao cho Python trong suốt kết nối. Vì vậy các tính năng này giữ tốc độ của bộ máy Python.
- Với TLS trực tiếp, reverse proxy, FastCGI và tải tệp lên không được bộ máy native hỗ trợ: khi đó bộ máy Python phục vụ, và giao diện hiển thị điều này.
- Nó cần glibc 2.38 trở lên và OpenSSL 3. Nếu nó không khởi động được, trình cài đặt sẽ biên dịch lại tại chỗ, và nếu không thể, omega-serv tiếp tục dùng bộ máy Python.

---

## 6. So sánh tính năng

Chú giải:
- ✅ tích hợp sẵn;
- 🧩 mô-đun chính thức của dự án, cần bật hoặc cài đặt;
- 🔌 mô-đun hoặc plugin của bên thứ ba;
- ⚙️ qua công cụ bên ngoài;
- ❌ không có.

“Commercial” chỉ tính năng chỉ có trong phiên bản trả phí.

### Dịch vụ HTTP

| Tính năng | nginx | lighttpd | Caddy | Apache | Traefik | omega-serv 2.5 |
|---|---|---|---|---|---|---|
| Ngôn ngữ của máy chủ | C | C | Go | C | Go | Python, với bộ máy native C++ tùy chọn |
| Phục vụ tệp tĩnh | ✅ | ✅ | ✅ | ✅ | ❌ (chỉ proxy) | ✅ |
| ETag / 304 / Range | ✅ | ✅ | ✅ | ✅ | — | ✅ |
| Tệp nén sẵn `.gz` / `.br` | ✅ `gzip_static` (`.br`: 🔌) | 🔌 script Lua (mod_magnet) | ✅ `precompressed` | 🧩 công thức mod_rewrite | — | ✅ |
| Nén trực tiếp | ✅ | ✅ mod_deflate | ✅ | 🧩 mod_deflate | ✅ middleware | ❌ |
| HTTP/2 | ✅ | ✅ | ✅ | 🧩 mod_http2 | ✅ | ❌ |
| HTTP/3 (QUIC) | ✅ | ❌ | ✅ | ❌ | ✅ | ❌ |
| PHP qua FastCGI | ✅ | ✅ | ✅ | ✅ | ❌ | ✅ |
| Nhiều tiến trình hoặc lõi | ✅ workers | ⚠️ `max-worker`, tài liệu không khuyến nghị | ✅ (Go, mọi lõi) | ✅ MPM | ✅ (Go) | ✅ `server.workers`; bộ máy native: mọi lõi |

### Reverse proxy

| Tính năng | nginx | lighttpd | Caddy | Apache | Traefik | omega-serv 2.5 |
|---|---|---|---|---|---|---|
| Cân bằng tải | ✅ xoay vòng, ít kết nối nhất, băm | ✅ fair, round-robin, hash, sticky | ✅ khoảng mười mấy chiến lược | 🧩 mod_proxy_balancer | ✅ wrr, p2c, hrw, least-time | ✅ 7 chiến lược, gồm cả tải thực |
| Kiểm tra thụ động (loại máy chủ hỏng) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Kiểm tra chủ động (thăm dò định kỳ) | Commercial (NGINX Plus) | ❌ | ✅ | 🧩 mod_proxy_hcheck | ✅ | ✅ |
| Bộ nhớ đệm phản hồi | ✅ `proxy_cache` | ❌ | 🔌 | 🧩 mod_cache | Commercial | ✅ |
| WebSocket | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Khám phá dịch vụ (Docker, Kubernetes) | 🔌 | ❌ | 🔌 | ❌ | ✅ (cốt lõi của dự án) | ❌ |

### TLS

| Tính năng | nginx | lighttpd | Caddy | Apache | Traefik | omega-serv 2.5 |
|---|---|---|---|---|---|---|
| Chứng chỉ tự động (ACME, Let's Encrypt) | 🧩 `ngx_http_acme_module` | ⚙️ Certbot | ✅ mặc định | 🧩 mod_md | ✅ | ⚙️ Certbot, có trình hướng dẫn tích hợp và gia hạn theo lịch |
| CA cục bộ | ❌ | ❌ | ✅ CA nội bộ (cấp tự động) | ❌ | ❌ | ✅ tạo, ký CSR, thu hồi |

### Bảo mật

| Tính năng | nginx | lighttpd | Caddy | Apache | Traefik | omega-serv 2.5 |
|---|---|---|---|---|---|---|
| Giới hạn tốc độ theo trình khách | ✅ `limit_req` | ⚠️ mod_evasive (chỉ kết nối đồng thời) | 🔌 caddy-ratelimit | 🔌 mod_evasive, mod_qos | ✅ middleware | ✅ |
| Giới hạn dùng chung giữa các tiến trình | ✅ vùng bộ nhớ chung | ❌ đếm theo tiến trình | — (một tiến trình) | tùy mô-đun | 1 instance; nhiều instance với Redis | ✅ bộ nhớ chung |
| WAF (chữ ký SQLi/XSS, công cụ quét…) | 🔌 ModSecurity, Commercial (App Protect) | ❌ (phải tự viết script Lua) | 🔌 Coraza | 🔌 ModSecurity | 🔌 plugin | ✅ tích hợp sẵn |
| Danh sách chặn có thời hạn, đếm tái phạm | ⚙️ fail2ban | ⚙️ fail2ban | ⚙️ fail2ban | ⚙️ fail2ban | ⚙️ | ✅ tích hợp sẵn |
| Mồi nhử, chế độ chiến tranh, sự cố, xuất IoC | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ Active Defense |
| Lệnh cấm tăng dần theo thời gian | ⚙️ fail2ban | ⚙️ fail2ban | ⚙️ fail2ban | ⚙️ fail2ban | ⚙️ | ✅ RIPOSTE |
| Kiểm tra bảo mật cấu hình | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ `audit security` |
| Chế độ quan sát (ghi nhật ký mà không chặn) | tùy mô-đun | — | tùy plugin | ✅ ModSecurity `DetectionOnly` | tùy plugin | ✅ |

Lệnh cấm tăng dần: lệnh cấm ngày càng dài đối với các địa chỉ quay lại, trong nhiều tuần, ở mức cục bộ hoặc mạng. fail2ban làm được điều này với tùy chọn `bantime.increment`; RIPOSTE bổ sung các chính sách có thể đo trên nhật ký và mô phỏng trước khi bật, việc gỡ bỏ hành động và nút dừng khẩn cấp.

### Khả năng mở rộng

| Tính năng | nginx | lighttpd | Caddy | Apache | Traefik | omega-serv 2.5 |
|---|---|---|---|---|---|---|
| Ngôn ngữ script | 🧩 njs (JavaScript); 🔌 Lua (OpenResty) | ✅ Lua (mod_magnet) | mô-đun Go (biên dịch lại) | 🧩 mod_lua | plugin Go hoặc WebAssembly | 🔌 nhập script mod_magnet (tùy chọn `magnet`) |
| Hệ sinh thái mô-đun | rất lớn | có trọng tâm | lớn | rất lớn | lớn | không: mọi thứ đều tích hợp sẵn |

---

## 7. Quản trị và sự tiện lợi

| Máy chủ | Cách quản trị chính | Giao diện | Nạp lại không gián đoạn |
|---|---|---|---|
| nginx | tệp cấu hình | không (bảng điều khiển: NGINX Plus, thương mại) | ✅ `nginx -s reload` |
| lighttpd | tệp cấu hình | không (mod_status chỉ đọc) | ✅ khởi động lại nhẹ |
| Caddy | Caddyfile hoặc JSON | API quản trị REST | ✅ qua API |
| Apache | tệp cấu hình và `.htaccess` | không (mod_status chỉ đọc) | ✅ `graceful` |
| Traefik | nhãn container, tệp hoặc Kubernetes | bảng điều khiển web (chỉ đọc) | ✅ cấu hình động |
| omega-serv | giao diện terminal (TUI) và dòng lệnh (CLI); không cần sửa tệp JSON | **TUI đầy đủ dùng bàn phím và chuột, 17 ngôn ngữ, trợ giúp tích hợp** | ✅ với hầu hết cài đặt; cổng, TLS, bộ máy và số tiến trình sẽ được báo cần khởi động lại |

Trên thực tế, omega-serv quản lý cấu hình, bảo mật, nhật ký, dịch vụ hệ thống, sao lưu và instance từ một giao diện duy nhất. Mỗi cài đặt đều được giải thích và kiểm tra trước khi ghi. Với các máy chủ khác, người ta sửa tệp văn bản rồi dùng các công cụ riêng biệt (Certbot, fail2ban, logrotate, ModSecurity, công cụ giám sát…).

Ngược lại, cách tiếp cận “tệp cấu hình” của nginx, Apache và Caddy rất dễ tự động hóa (Ansible, container, quản lý phiên bản). omega-serv có CLI dùng được trong script, nhưng hệ sinh thái tự động hóa của nó còn hạn chế.

---

## 8. Những gì omega-serv mang lại thêm

Phần này chỉ gồm những gì không máy chủ nào được so sánh cung cấp dưới dạng này, mà không cần mô-đun bên thứ ba hay công cụ bên ngoài.

1. **Quản trị toàn bộ trong giao diện terminal.**
   - Giao diện bao quát toàn bộ máy chủ: trang web, bảo mật, nhật ký, dịch vụ, sao lưu và instance.
   - Có thể dùng bằng bàn phím và chuột, trên máy chủ không có môi trường đồ họa, kể cả qua SSH.
   - Nó có sẵn bằng 17 ngôn ngữ và giải thích từng cài đặt.
   - Các máy chủ khác không có giao diện quản trị (nginx, lighttpd, Apache), hoặc chỉ có API (Caddy) hay bảng điều khiển chỉ đọc (Traefik).
2. **Bảo mật chủ động tích hợp sẵn, không cần lắp ghép mô-đun.**
   - WAF gồm chữ ký, danh sách đường dẫn có thể chỉnh sửa, đếm tái phạm, danh sách chặn có thời hạn, danh tiếng và chế độ quan sát.
   - Active Defense bổ sung mồi nhử, chế độ chiến tranh, theo dõi sự cố, xuất chỉ báo xâm nhập và mô phỏng không tác động.
   - RIPOSTE phản ứng theo thời gian: nó ghi nhớ các địa chỉ quay lại và áp dụng cho chúng các phản ứng tăng dần, lệnh cấm ngày càng dài (mặc định 1 giờ, 6 giờ, 24 giờ, 7 ngày), cục bộ trong danh sách chặn hoặc ở mức mạng qua fail2ban (omega-jail), hoặc mồi nhử kéo dài. Mỗi chính sách có thể đo trên nhật ký thực và mô phỏng trước khi bật; mỗi hành động luôn hiển thị và có thể gỡ bỏ, và có nút dừng khẩn cấp.
   - Với các máy chủ khác, những tính năng này đòi hỏi kết hợp ModSecurity hoặc Coraza, các bộ quy tắc và fail2ban.
3. **Giới hạn bảo mật chính xác khi chạy nhiều tiến trình.**
   - Với nhiều tiến trình, giới hạn tốc độ và đếm tái phạm của WAF được dùng chung trong bộ nhớ. Vì vậy kẻ tấn công không thể nhân hạn mức của mình lên theo số tiến trình.
   - lighttpd ghi nhận trường hợp ngược lại: với `server.max-worker`, `mod_evasive` và `mod_status` đếm riêng trong từng tiến trình.
   - nginx cũng dùng chung bộ đếm (vùng `limit_req`), nhưng không có WAF tích hợp.
4. **Hai bộ máy, một hành vi.** Bộ máy native và bộ máy Python tạo ra cùng phản hồi và cùng nhật ký, điều này được kiểm chứng tự động trên một băng thử so sánh. Các công cụ đọc nhật ký (ví dụ fail2ban) không thấy khác biệt nào.
5. **Nhập script mod_magnet của lighttpd.**
   - Một script bảo vệ bằng Lua đã viết cho lighttpd được nhập mà không cần viết lại.
   - Nó bổ sung cho lớp bảo vệ tích hợp mà không bao giờ có thể làm yếu nó, và tính tương thích của nó được kiểm tra trước khi bật.
6. **Quản lý nhiều instance.**
   - Một sổ đăng ký liệt kê mọi instance, và giao diện chuyển đổi giữa chúng.
   - Nó cũng có thể gỡ cài đặt hoàn toàn một instance.
7. **Kiểm tra bảo mật cấu hình**: lệnh `audit security` chỉ mang tính thông tin, không bao giờ chặn, và trả về mã thoát dùng được trong script.
8. **Nguồn nhật ký từ xa.**
   - Giao diện lấy nhật ký của máy chủ khác qua SSH, theo yêu cầu, không lưu mật khẩu.
   - Nó có thể đọc nhật ký đó trong lnav, gộp với nhật ký cục bộ.
9. **Gia cố HTTP không thể tắt**, có hiệu lực ngay từ khi cài đặt, với mọi hồ sơ và mọi bộ máy:
   - kiểm tra nghiêm ngặt tiêu đề Host;
   - từ chối sự mơ hồ giữa Content-Length / Transfer-Encoding;
   - tiêu đề bảo mật và CSP trong các phản hồi của trang, kể cả trang lỗi;
   - đọc X-Forwarded-For một cách an toàn;
   - từ chối khởi động với quyền root.

---

## 9. Những gì các máy chủ khác làm tốt hơn

- **Thông lượng**: lighttpd và nginx vẫn nhanh nhất với tệp nhỏ và trung bình, trên cả ba máy. Ngay cả với bộ máy native, omega-serv đạt khoảng 0,7 so với nginx và 0,5 so với lighttpd với tệp nhỏ, và 0,3–0,6 so với nginx với tệp 100 KB. Với trang có lưu lượng lớn, API công khai hay CDN, nên chọn chúng.
- **Tệp trung bình**: Apache phục vụ tệp 100 KB nhanh hơn bộ máy native của omega-serv, trên cả ba máy.
- **Bộ nhớ**: lighttpd (1 MB), nginx (4–5 MB) và Apache (4–9 MB) phù hợp với các máy rất hạn chế (hệ thống nhúng, container nhỏ). omega-serv cần 30–65.
- **Cái giá của bảo mật**: WAF vẫn có cái giá của nó. Với bộ máy native, nó làm mất 5–22 % thông lượng với tệp nhỏ, kể cả giới hạn tốc độ: omega-serv có WAF đạt 0,53–0,56 so với nginx không WAF trên máy A và B. Một yêu cầu đáng ngờ hoặc còn nghi vấn (khớp quy tắc, văn bản không phải ASCII, nguồn đang bị Active Defense theo dõi) luôn đi qua Python và được phục vụ với tốc độ của bộ máy Python. Khi bật magnet, mọi yêu cầu đều đi qua Python, và WAF khi đó chia thông lượng của bộ máy native cho 4 đến 7, như trước khi tối ưu.
- **Giao thức**: HTTP/2 ở mọi máy chủ khác, HTTP/3 ở nginx, Caddy và Traefik. omega-serv chỉ hỗ trợ HTTP/1.1.
- **HTTPS tự động**: Caddy và Traefik bật mặc định, nginx (`ngx_http_acme_module`) và Apache (`mod_md`) với một mô-đun chính thức. omega-serv giao việc này cho Certbot, có trình hướng dẫn và gia hạn theo lịch.
- **Môi trường container**: khám phá dịch vụ tự động của Traefik (Docker, Kubernetes) không có tương đương trong omega-serv.
- **Hệ sinh thái và độ trưởng thành**: nginx và Apache có hàng nghìn mô-đun, hướng dẫn và tích hợp, cùng hàng chục năm vận hành. Caddy có hệ thống mô-đun Go. omega-serv là một dự án trẻ, do một người duy trì, và bộ máy native của nó còn rất mới.
- **Nén trực tiếp**: omega-serv chỉ phục vụ các tệp đã được nén sẵn.

---

## 10. Máy chủ nào cho nhu cầu nào

| Nhu cầu | Lựa chọn khuyến nghị |
|---|---|
| Trang có lưu lượng lớn, API công khai, CDN, thông lượng tối đa | **nginx** hoặc **lighttpd** |
| Máy rất hạn chế, hệ thống nhúng, tệp tĩnh | **lighttpd** |
| Bắt đầu nhanh với HTTPS tự động, cấu hình ngắn gọn | **Caddy** |
| Ứng dụng PHP cũ, `.htaccess`, hosting dùng chung | **Apache** |
| Docker, Kubernetes, microservice | **Traefik** |
| Trang nhỏ hoặc vừa, dịch vụ nội bộ, phòng thí nghiệm, VPN, quản trị không cần sửa tệp | **omega-serv** (bộ máy native nếu có thể) |
| Máy chủ hướng ra Internet mà bạn muốn xem và kiểm soát bảo mật (WAF, lệnh cấm tăng dần, mồi nhử) từ một giao diện | **omega-serv** |
| Reverse proxy nội bộ có cân bằng tải, kiểm tra và bộ nhớ đệm, quản lý qua giao diện | **omega-serv** |
| Học về gia cố HTTP và phòng thủ chủ động | **omega-serv** |

Các công cụ này cũng có thể kết hợp với nhau. Ví dụ:
- nginx hoặc Traefik ở phía Internet, và omega-serv phía sau cho một dịch vụ nội bộ, bảo mật và quản trị của nó;
- omega-serv làm reverse proxy nội bộ trước nhiều máy chủ ứng dụng.

---

## 11. Tái lập các phép đo

Các công cụ được cung cấp trong kho mã, trong `tools/bench/`. Cần cài nginx, lighttpd, Apache, Caddy và oha, môi trường phát triển của omega-serv (`.venv`) và, với bộ máy native, tệp nhị phân đã biên dịch trong `native/omega-http-core/build-release`.

```sh
# 1. chuẩn bị thư mục đo (tệp thử, cấu hình, omega-serv 1.0, 2.0 và phiên bản hiện tại)
tools/bench/compare/setup.sh /duong/dan/do omega-serv-1.0.0.tar.gz omega-serv-2.0.0.tar.gz

# 2. 21 cấu hình, 3 lượt lặp xen kẽ (40–60 phút)
#    SRV_CPUS / CLI_CPUS: lõi của máy chủ và trình khách (lscpu -e cho biết cấu trúc)
SRV_CPUS=0,1 CLI_CPUS=2,3 tools/bench/compare/campaign.sh /duong/dan/do > ket-qua.txt

# 3. các trung vị
python3 tools/bench/compare/summarize.py ket-qua.txt

# danh sách cấu hình khác, ví dụ 4 tiến trình
CONFIGS="nginx-4 lighttpd-4 caddy-4 apache-4 omega-v2-1-0-native omega-v2-4-1-native" \
  tools/bench/compare/campaign.sh /duong/dan/do > ket-qua-4.txt

# tải xuống lớn (bộ nhớ và độ phản hồi): phiên bản hiện tại, bộ máy Python, rồi native, rồi 1.0
.venv/bin/python tools/bench/bigfile.py
BENCH_ENGINE=native .venv/bin/python tools/bench/bigfile.py
BENCH_SRC=/duong/dan/do/v1-archive/omega-serv/src \
BENCH_EXTRA_PATH=/duong/dan/do/v1-archive/omega-serv/vendor/omega-lib/src \
  .venv/bin/python tools/bench/bigfile.py

# đo bất kỳ máy chủ nào khác đang chạy, không cần oha
python3 tools/bench/bench_any.py --make-files /srv/webroot-thu
python3 tools/bench/bench_any.py --port 8080
```

Tên cấu hình: `nginx-N`, `lighttpd-N`, `apache-N`, `caddy-N` (N tiến trình, hoặc N lõi với Caddy); `omega-vX-N-W` cho omega-serv (phiên bản `v1`, `v20` hoặc `v2` cho phiên bản hiện tại, N tiến trình, W = 0 không WAF hoặc 1 có WAF), với hậu tố `-native` cho bộ máy native.

Để công bố kết quả của riêng bạn, hãy ghi rõ máy, phiên bản, cách phân bổ lõi và ba lượt lặp.

---

## 12. Nguồn

Tính năng của các máy chủ khác theo tài liệu chính thức của chúng (tra cứu ngày 26 tháng 10 năm 2026).

**nginx**
- [Giới hạn tốc độ `limit_req` (vùng bộ nhớ chung)](https://nginx.org/en/docs/http/ngx_http_limit_req_module.html)
- [Tệp nén sẵn `gzip_static`](https://nginx.org/en/docs/http/ngx_http_gzip_static_module.html)
- [Mô-đun ACME chính thức `ngx_http_acme_module`](https://nginx.org/en/docs/http/ngx_http_acme_module.html)
- [Cân bằng tải (`upstream`)](https://nginx.org/en/docs/http/ngx_http_upstream_module.html)
- [HTTP/3](https://nginx.org/en/docs/http/ngx_http_v3_module.html)
- [Bộ kết nối ModSecurity cho nginx](https://github.com/owasp-modsecurity/ModSecurity-nginx)

**lighttpd**
- [`server.max-worker`: không khuyến nghị, bộ đếm theo tiến trình cho mod_status và mod_evasive](https://redmine.lighttpd.net/projects/lighttpd/wiki/Server_max-workerDetails)
- [mod_magnet (script Lua)](https://redmine.lighttpd.net/projects/lighttpd/wiki/Docs_ModMagnet)
- [mod_deflate (nén, bộ nhớ đệm)](https://redmine.lighttpd.net/projects/lighttpd/wiki/Mod_deflate)
- [mod_proxy (cân bằng tải, kiểm tra thụ động, WebSocket)](https://redmine.lighttpd.net/projects/lighttpd/wiki/Docs_ModProxy)
- [mod_evasive (kết nối đồng thời từ một địa chỉ)](https://redmine.lighttpd.net/projects/lighttpd/wiki/Docs_ModEvasive)

**Caddy**
- [HTTPS tự động](https://caddyserver.com/docs/automatic-https)
- [`file_server` và `precompressed`](https://caddyserver.com/docs/caddyfile/directives/file_server)
- [`reverse_proxy` (chiến lược, kiểm tra chủ động và thụ động)](https://caddyserver.com/docs/caddyfile/directives/reverse_proxy)
- [API quản trị](https://caddyserver.com/docs/api)
- [Plugin giới hạn tốc độ caddy-ratelimit](https://github.com/mholt/caddy-ratelimit)
- [WAF Coraza cho Caddy](https://github.com/corazawaf/coraza-caddy)
- [caddy-docker-proxy](https://github.com/lucaslorentz/caddy-docker-proxy)

**Apache HTTP Server**
- [MPM event](https://httpd.apache.org/docs/2.4/mod/event.html)
- [mod_md (ACME)](https://httpd.apache.org/docs/2.4/mod/mod_md.html)
- [mod_proxy_balancer](https://httpd.apache.org/docs/2.4/mod/mod_proxy_balancer.html)
- [mod_proxy_hcheck](https://httpd.apache.org/docs/2.4/mod/mod_proxy_hcheck.html)
- [mod_http2](https://httpd.apache.org/docs/2.4/mod/mod_http2.html)
- [mod_deflate, nội dung nén sẵn](https://httpd.apache.org/docs/2.4/mod/mod_deflate.html)
- [ModSecurity](https://github.com/owasp-modsecurity/ModSecurity)

**Traefik**
- [Middleware `ratelimit` (trong bộ nhớ theo instance, Redis tùy chọn)](https://doc.traefik.io/traefik/reference/routing-configuration/http/middlewares/ratelimit/)
- [ACME](https://doc.traefik.io/traefik/https/acme/)
- [Providers (Docker, Kubernetes…)](https://doc.traefik.io/traefik/providers/overview/)

**fail2ban**
- [`jail.conf`: `bantime.increment`, `bantime.factor`, `bantime.multipliers`, `bantime.maxtime` (lệnh cấm dài hơn cho kẻ tái phạm)](https://github.com/fail2ban/fail2ban/blob/master/config/jail.conf) (tra cứu ngày 4 tháng 11 năm 2026)

**Công cụ đo**
- [oha](https://github.com/hatoo/oha)

---

*Bản so sánh do kraynux thực hiện cho omega-serv 2.5: đo ngày 3 và 4 tháng 11 năm 2026 trên ba máy (phòng thủ chủ động: ngày 26 tháng 10 năm 2026). Với mọi quyết định về năng lực, hãy đo trên phần cứng của chính bạn bằng các công cụ đi kèm.*
