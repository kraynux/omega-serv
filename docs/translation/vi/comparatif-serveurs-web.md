<!-- Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE) -->

# omega-serv so với các máy chủ web trên thị trường

**So sánh có đo đạc: nginx · lighttpd · Caddy · Apache · Traefik · omega-serv 2.0**

🌐 [Français](../../comparatif-serveurs-web.md) · [English](../en/comparatif-serveurs-web.md) · [Español](../es/comparatif-serveurs-web.md) · [Português (Brasil)](../pt-BR/comparatif-serveurs-web.md) · [Italiano](../it/comparatif-serveurs-web.md) · [Deutsch](../de/comparatif-serveurs-web.md) · [Nederlands](../nl/comparatif-serveurs-web.md) · [Polski](../pl/comparatif-serveurs-web.md) · [Русский](../ru/comparatif-serveurs-web.md) · [中文](../zh-CN/comparatif-serveurs-web.md) · **Tiếng Việt** · [ไทย](../th/comparatif-serveurs-web.md) · [Bahasa Indonesia](../id/comparatif-serveurs-web.md) · [日本語](../ja/comparatif-serveurs-web.md) · [한국어](../ko/comparatif-serveurs-web.md) · [हिन्दी](../hi/comparatif-serveurs-web.md) · [العربية](../ar/comparatif-serveurs-web.md)

Tài liệu này đặt omega-serv bên cạnh các máy chủ web phổ biến nhất. Nó không nhằm chỉ ra một « máy chủ tốt nhất »: mỗi công cụ đáp ứng những nhu cầu khác nhau. Tài liệu đưa ra ba điều:

1. các **số đo thực tế**, thực hiện trên cùng một máy, với cùng một client và cùng các tệp, và có thể tái hiện;
2. một **so sánh chức năng**, mỗi chức năng được kiểm chứng trong tài liệu chính thức của từng máy chủ (liên kết ở cuối tài liệu), phân biệt cái tích hợp sẵn với cái cần một mô-đun hoặc plugin;
3. những gì omega-serv **thực sự mang lại thêm**, và những gì các máy chủ khác làm **tốt hơn nó**.

Mọi con số bên dưới đều được đo vào ngày 26 tháng 10 năm 2026. Không có con số nào được lấy từ trang khác hay ước lượng.

---

## Mục lục

1. [Tóm tắt](#1-tóm-tắt)
2. [Phương pháp đo](#2-phương-pháp-đo)
3. [Hiệu năng: omega-serv so với nginx, lighttpd và Caddy](#3-hiệu-năng-omega-serv-so-với-nginx-lighttpd-và-caddy)
4. [omega-serv 1.0 → 2.0: những gì đã thay đổi, có đo đạc](#4-omega-serv-10--20-những-gì-đã-thay-đổi-có-đo-đạc)
5. [So sánh chức năng](#5-so-sánh-chức-năng)
6. [Quản trị và trải nghiệm sử dụng](#6-quản-trị-và-trải-nghiệm-sử-dụng)
7. [Những gì omega-serv mang lại thêm](#7-những-gì-omega-serv-mang-lại-thêm)
8. [Những gì các máy chủ khác làm tốt hơn](#8-những-gì-các-máy-chủ-khác-làm-tốt-hơn)
9. [Máy chủ nào cho nhu cầu nào](#9-máy-chủ-nào-cho-nhu-cầu-nào)
10. [Tái hiện các số đo](#10-tái-hiện-các-số-đo)
11. [Nguồn](#11-nguồn)

---

## 1. Tóm tắt

- **Thông lượng thô với tệp nhỏ**: nginx và lighttpd, viết bằng C, phục vụ **nhiều hơn 10 đến 20 lần** số yêu cầu mỗi giây so với omega-serv, viết bằng Python. Caddy, viết bằng Go, nằm ở giữa. Đây là khác biệt về bản chất, không phải về tinh chỉnh: omega-serv không nhắm tới sân chơi này.
- **Tệp lớn**: từ bản 2.0, omega-serv giao việc gửi cho nhân hệ điều hành (`sendfile`). Khi đó nó đạt **cùng cấp độ thông lượng** với nginx, lighttpd và Caddy trên máy này: 2,1 GB/s so với 2,0 đến 2,4 GB/s.
- **Bộ nhớ**: lighttpd (1 MB) và nginx (4 đến 5 MB) vẫn ngoài tầm với. omega-serv giữ dưới 30 MB khi chịu tải với 1 tiến trình, Caddy khoảng 55 MB.
- **Từ 1.0 đến 2.0**: thông lượng tệp lớn tăng 2,8 lần; bộ nhớ khi tải xuống tệp lớn giảm 45 lần; tới +50 % với tệp nhỏ khi dùng 2 tiến trình (chế độ boost); chi phí của Active Defense giảm 12 lần.
- **Những gì omega-serv có thêm**: quản trị đầy đủ qua giao diện terminal (TUI), bằng 17 ngôn ngữ; WAF và phòng thủ chủ động tích hợp; giới hạn bảo mật luôn chính xác với nhiều tiến trình; nhập script mod_magnet của lighttpd; quản lý nhiều instance.
- **Những gì nó không có**: HTTP/2 và HTTP/3, khám phá dịch vụ Docker/Kubernetes, client ACME tích hợp (nó dùng Certbot), thông lượng của một máy chủ viết bằng C.

---

## 2. Phương pháp đo

### Máy và phần mềm

| Thành phần | Giá trị |
|---|---|
| Bộ xử lý | Intel Core i5 M480 2,67 GHz (2010): 2 nhân vật lý, 4 luồng |
| Bộ nhớ | 8 GB |
| Hệ điều hành | Manjaro Linux, nhân 6.18 |
| Mạng | vòng lặp cục bộ (127.0.0.1) |
| Client tạo tải | [oha](https://github.com/hatoo/oha) 1.16.0 (viết bằng Rust) |
| nginx | 1.30.4 (gói Manjaro) |
| lighttpd | 1.4.85 (gói Manjaro) |
| Caddy | 2.11.4 (gói Manjaro) |
| omega-serv | 1.0.0 (bản lưu trữ đã phát hành) và 2.0.0, chạy trên Python 3.14.7 |

Apache và Traefik chưa được đo, vì chưa được cài trên máy này. Traefik vốn cũng không phải là máy chủ tệp (xem §5). Vì vậy hai máy chủ này chỉ xuất hiện trong phần so sánh chức năng.

### Quy trình

- **Cô lập bộ xử lý**: mỗi máy chủ được ghim vào nhân vật lý 0 (luồng 0 và 2), còn client ghim vào nhân vật lý 1 (luồng 1 và 3). Nhờ vậy client không lấy thời gian của máy chủ, và mọi máy chủ có đúng cùng một lượng tài nguyên.
- **Cùng tệp cho tất cả**: `small.html` (1 KB), `medium.png` (100 KB) và `large.bin` (5 MB), phục vụ từ cùng một thư mục.
- **Log truy cập bật ở mọi nơi**, vì một máy chủ production luôn ghi log.
- **HTTP/1.1 không mã hóa, kết nối bền (keep-alive)**. Mức đồng thời là 32 kết nối với tệp 1 KB và 100 KB, và 8 với tệp 5 MB.
- **Thời lượng**: 10 giây cho mỗi tệp và mỗi cấu hình.
- **Số lần lặp**: 3 vòng đầy đủ, xen kẽ (tất cả máy chủ ở vòng 1, rồi tất cả ở vòng 2, v.v.). Các bảng đưa ra **trung vị** của ba vòng.
- **Bộ nhớ**: PSS (*Proportional Set Size*) cộng dồn của mọi tiến trình máy chủ. Khác với RSS, một trang dùng chung giữa các tiến trình chỉ được tính một lần. Số liệu được ghi lúc nghỉ, rồi sau khi chịu tải.
- **Cấu hình**: nginx, lighttpd và Caddy ở cấu hình cơ bản (tệp tĩnh, log truy cập). omega-serv dùng hồ sơ `standard`, với WAF tắt rồi bật với toàn bộ quy tắc được cung cấp.
- **Số tiến trình**: mỗi máy chủ được đo với 1 rồi 2 tiến trình (nginx `worker_processes`, lighttpd `server.max-worker`, Caddy `GOMAXPROCS`, omega-serv `server.workers`).

### Những giới hạn cần biết

- **Máy khiêm tốn và đã cũ.** Giá trị tuyệt đối sẽ cao hơn nhiều trên một máy chủ hiện đại. Điều có ý nghĩa là **tỷ lệ** giữa các máy chủ được đo trong cùng một phiên.
- **Biến động giữa các phiên**: khoảng 10 đến 30 % tùy tải nền của máy. Các vòng trong cùng một phiên thì nhất quán: chênh lệch dưới 5 % với omega-serv và Caddy, nhiều hơn với nginx và lighttpd, vốn có thông lượng rất cao nên nhạy hơn với phần còn lại của máy.
- **Vòng lặp cục bộ**: phép đo không đi qua một mạng thật. Trên mạng thật, thông lượng tệp lớn hầu như luôn bị giới hạn bởi băng thông, không phải bởi máy chủ.
- **Không có TLS** trong các phép đo này. Với HTTPS, omega-serv không thể dùng `sendfile` và gửi tệp theo từng khối.
- **Số liệu thô**: được công bố cùng tài liệu này trong [`docs/benchmarks/2026-10-26-campagne-brute.txt`](../../benchmarks/2026-10-26-campagne-brute.txt).

---

## 3. Hiệu năng: omega-serv so với nginx, lighttpd và Caddy

### Tệp nhỏ (1 KB): số yêu cầu mỗi giây

| Máy chủ | 1 tiến trình | 2 tiến trình | Độ trễ p99 (1 tiến trình) |
|---|---:|---:|---:|
| lighttpd 1.4.85 | 25 521 | 29 700 | 4,5 ms |
| nginx 1.30.4 | 14 054 | 18 315 | 4,7 ms |
| Caddy 2.11.4 | 3 697 | 5 345 | 25,3 ms |
| **omega-serv 2.0** | **1 358** | **1 953** | **37,5 ms** |
| omega-serv 2.0 + WAF | 1 130 | 1 617 | 48,5 ms |
| omega-serv 1.0 | 1 304 | — | 41,2 ms |

### Tệp trung bình (100 KB): số yêu cầu mỗi giây

| Máy chủ | 1 tiến trình | 2 tiến trình |
|---|---:|---:|
| lighttpd | 11 635 | 13 037 |
| nginx | 8 024 | 9 555 |
| Caddy | 3 280 | 4 344 |
| **omega-serv 2.0** | **1 247** | **1 629** |
| omega-serv 2.0 + WAF | 1 012 | 1 347 |
| omega-serv 1.0 | 1 064 | — |

### Tệp lớn (5 MB): thông lượng

| Máy chủ | 1 tiến trình | 2 tiến trình |
|---|---:|---:|
| lighttpd | 2 379 MB/s | 2 407 MB/s |
| nginx | 2 242 MB/s | 1 981 MB/s |
| Caddy | 2 165 MB/s | 2 229 MB/s |
| **omega-serv 2.0** | **1 658 MB/s** | **2 115 MB/s** |
| omega-serv 1.0 | 584 MB/s | — |

### Bộ nhớ (PSS, mọi tiến trình của máy chủ)

| Máy chủ | Lúc nghỉ | Sau khi chịu tải |
|---|---:|---:|
| lighttpd (1 hoặc 2 tiến trình) | 1 MB | 1 MB |
| nginx (1 hoặc 2 tiến trình) | 4 đến 5 MB | 4 đến 5 MB |
| **omega-serv 2.0 (1 tiến trình)** | **26 MB** | **30 MB** |
| omega-serv 2.0 (2 tiến trình) | 39 MB | 48 MB |
| Caddy | 50 MB | 56 MB |
| omega-serv 1.0 | 22 MB | 100 MB |

### Cách đọc

- **Với tệp nhỏ và trung bình**, khoảng cách với nginx và lighttpd là một bậc độ lớn (×10 đến ×20). Đó là cái giá của một máy chủ viết bằng Python: mỗi yêu cầu đi qua trình thông dịch, trong khi nginx và lighttpd xử lý nó bằng mã C đã biên dịch. Chế độ boost thu hẹp khoảng cách, nhưng không lấp đầy.
- **Với tệp lớn**, các máy chủ gặp nhau, vì chính nhân hệ điều hành sao chép dữ liệu (`sendfile`). Với 2 tiến trình, omega-serv 2.0 đạt 2,1 GB/s, cùng vùng với các máy chủ khác (2,0 đến 2,4 GB/s).
- **WAF của omega-serv tốn khoảng 17 %** với tệp nhỏ: nó kiểm tra từng yêu cầu. nginx, lighttpd và Caddy được đo không có WAF; một WAF thêm vào các máy chủ này (ModSecurity, Coraza) cũng có chi phí, không được đo ở đây.
- **Để hình dung các con số này**: 1 300 yêu cầu mỗi giây là hơn 110 triệu yêu cầu mỗi ngày trên chiếc máy năm 2010 này. Con số đó vượt xa nhu cầu của một trang cá nhân, một dịch vụ nội bộ hay một phòng lab, vốn là các mục đích sử dụng mà omega-serv nhắm tới.

---

## 4. omega-serv 1.0 → 2.0: những gì đã thay đổi, có đo đạc

### Hiệu năng

Hai phiên bản được đo trong cùng một phiên, trên cùng một máy và với cùng quy trình.

| Phép đo | 1.0.0 | 2.0.0 | Thay đổi |
|---|---:|---:|---:|
| Tệp nhỏ (1 KB), 1 tiến trình | 1 304 req/s | 1 358 req/s | +4 % |
| Tệp nhỏ (1 KB), chế độ boost 2 tiến trình | — | 1 953 req/s | **+50 %** so với 1.0 |
| Tệp nhỏ có WAF, 1 tiến trình | 1 097 req/s | 1 130 req/s | +3 % |
| Tệp nhỏ có WAF, 2 tiến trình | — | 1 617 req/s | **+47 %** so với 1.0 |
| Tệp 100 KB, 1 tiến trình | 1 064 req/s | 1 247 req/s | +17 % |
| Tệp lớn (5 MB), 1 tiến trình | 584 MB/s | 1 658 MB/s | **×2,8** |
| Tệp lớn (5 MB), 2 tiến trình | — | 2 115 MB/s | **×3,6** so với 1.0 |
| Bộ nhớ sau khi chịu tải, 1 tiến trình | 100 MB | 30 MB | **÷3** |

### Tải xuống đồng thời các tệp lớn

Phép thử: 3 lượt tải xuống đồng thời một tệp 300 MB, trong khi một trang nhỏ được yêu cầu liên tục. Hai lần chạy cho kết quả giống hệt nhau.

| Phép đo | 1.0.0 | 2.0.0 |
|---|---:|---:|
| Bộ nhớ máy chủ ở mức cao nhất | 1 835 MB | 40 MB |
| Trang nhỏ trong lúc tải xuống: trung vị | 3 đến 4 ms | 2 ms |
| Trang nhỏ trong lúc tải xuống: trường hợp xấu nhất | 1,7 đến 1,8 giây | 5 ms |

Bản 1.0 nạp toàn bộ mỗi tệp vào bộ nhớ trước khi gửi. Bản 2.0 gửi theo từng khối, hoặc giao cho nhân hệ điều hành: bộ nhớ không còn phụ thuộc vào kích thước tệp, và máy chủ vẫn phản hồi nhanh trong lúc tải xuống.

### Chi phí của phòng thủ chủ động

Chi phí của một lần Active Defense ghi nhận mối đe dọa, cho mỗi yêu cầu đáng ngờ, đo trên đĩa (ext4) với 2 000 lần ghi nhận:

| Phép đo | 1.0.0 | 2.0.0 |
|---|---:|---:|
| Trung vị | 2,84 ms | 0,23 ms |
| p99 | 11,6 ms | 2,3 ms |
| Tối đa | 18 đến 20 ms | 37 đến 46 ms |

Trung vị giảm 12 lần. Ngược lại, giá trị tối đa cao hơn ở bản 2.0: một vài đỉnh riêng lẻ, liên quan đến việc ghi định kỳ nhật ký SQLite xuống đĩa.

### Các chức năng mới trong bản 2.0

**Bắt kịp các tiêu chuẩn của thị trường**: nginx, lighttpd, Caddy và Apache đều đã làm được những điều này. omega-serv bắt kịp họ.

- Yêu cầu có điều kiện (ETag, Last-Modified, phản hồi 304): tải lại trang chỉ tải lại những gì đã thay đổi.
- Yêu cầu một phần (Range, 206/416): tải tiếp, tua video.
- Gửi tệp bằng `sendfile` hoặc theo từng khối, với bộ nhớ ổn định.
- Tệp nén sẵn (`.gz`, `.br`) đặt cạnh tệp gốc.
- Cache-Control mặc định theo loại tệp (ảnh, phông chữ, CSS/JS), có thể điều chỉnh.
- Nhiều tiến trình máy chủ (chế độ boost, `server.workers`).

**Các chức năng mở rộng hơn:**

- **Reverse proxy đầy đủ.** Bản 1.0 chỉ có một bộ chuyển tiếp đơn giản (lần lượt, TLS tới phía trên, WebSocket). Bản 2.0 bổ sung:
  - 6 chiến lược phân phối, tổng cộng 7;
  - gắn phiên và định tuyến theo tiêu đề;
  - kiểm tra sức khỏe thụ động và chủ động của các máy chủ phía trên;
  - cache phản hồi;
  - bảo vệ chống quá tải và chống vòng lặp;
  - điều khiển nóng.
- **Giới hạn tốc độ theo thư mục và theo địa chỉ hoặc mạng**, bên cạnh giới hạn toàn cục.
- **Bộ đếm bảo mật dùng chung giữa các tiến trình** (xem §7).
- **Danh sách đường dẫn nhạy cảm** dùng ngay, với chế độ quan sát và trình soạn tích hợp.
- **Nhập script mod_magnet của lighttpd** (xem §7).
- **Giao diện bằng 17 ngôn ngữ**, với ngôn ngữ riêng cho các trang khách truy cập nhìn thấy và cho bản xuất.
- **Log được làm lại hoàn toàn**:
  - một thư viện log;
  - ba trình xem, trong đó có lnav;
  - tải log từ xa qua SSH.

---

## 5. So sánh chức năng

Chú thích:
- ✅ tích hợp sẵn;
- 🧩 mô-đun chính thức của dự án, cần bật hoặc cài đặt;
- 🔌 mô-đun hoặc plugin của bên thứ ba;
- ⚙️ qua một công cụ bên ngoài;
- ❌ không có.

« Thương mại » chỉ một chức năng dành riêng cho phiên bản trả phí.

### Dịch vụ HTTP

| Chức năng | nginx | lighttpd | Caddy | Apache | Traefik | omega-serv 2.0 |
|---|---|---|---|---|---|---|
| Phục vụ tệp tĩnh | ✅ | ✅ | ✅ | ✅ | ❌ (chỉ proxy) | ✅ |
| ETag / 304 / Range | ✅ | ✅ | ✅ | ✅ | — | ✅ |
| Tệp nén sẵn `.gz` / `.br` | ✅ `gzip_static` (`.br`: 🔌) | 🔌 script Lua (mod_magnet) | ✅ `precompressed` | 🧩 công thức mod_rewrite | — | ✅ |
| Nén tức thời | ✅ | ✅ mod_deflate | ✅ | 🧩 mod_deflate | ✅ middleware | ❌ |
| HTTP/2 | ✅ | ✅ | ✅ | 🧩 mod_http2 | ✅ | ❌ |
| HTTP/3 (QUIC) | ✅ | ❌ | ✅ | ❌ | ✅ | ❌ |
| PHP qua FastCGI | ✅ | ✅ | ✅ | ✅ | ❌ | ✅ |
| Nhiều tiến trình hoặc nhân | ✅ workers | ⚠️ `max-worker`, tài liệu khuyên không dùng | ✅ (Go, mọi nhân) | ✅ MPM | ✅ (Go) | ✅ `server.workers` |

### Reverse proxy

| Chức năng | nginx | lighttpd | Caddy | Apache | Traefik | omega-serv 2.0 |
|---|---|---|---|---|---|---|
| Cân bằng tải | ✅ lần lượt, ít kết nối nhất, hash | ✅ fair, round-robin, hash, sticky | ✅ khoảng một chục chiến lược | 🧩 mod_proxy_balancer | ✅ wrr, p2c, hrw, least-time | ✅ 7 chiến lược, trong đó có tải thực |
| Sức khỏe thụ động (loại máy chủ bị hỏng) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Sức khỏe chủ động (thăm dò định kỳ) | Thương mại (NGINX Plus) | ❌ | ✅ | 🧩 mod_proxy_hcheck | ✅ | ✅ |
| Cache phản hồi | ✅ `proxy_cache` | ❌ | 🔌 | 🧩 mod_cache | Thương mại | ✅ |
| WebSocket | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Khám phá dịch vụ (Docker, Kubernetes) | 🔌 | ❌ | 🔌 | ❌ | ✅ (cốt lõi của dự án) | ❌ |

### TLS

| Chức năng | nginx | lighttpd | Caddy | Apache | Traefik | omega-serv 2.0 |
|---|---|---|---|---|---|---|
| Chứng chỉ tự động (ACME, Let's Encrypt) | 🧩 `ngx_http_acme_module` | ⚙️ Certbot | ✅ mặc định | 🧩 mod_md | ✅ | ⚙️ Certbot, với trình hướng dẫn tích hợp và gia hạn theo lịch |
| CA cục bộ | ❌ | ❌ | ✅ CA nội bộ (cấp tự động) | ❌ | ❌ | ✅ tạo, ký CSR, thu hồi |

### Bảo mật

| Chức năng | nginx | lighttpd | Caddy | Apache | Traefik | omega-serv 2.0 |
|---|---|---|---|---|---|---|
| Giới hạn tốc độ theo client | ✅ `limit_req` | ⚠️ mod_evasive (chỉ kết nối đồng thời) | 🔌 caddy-ratelimit | 🔌 mod_evasive, mod_qos | ✅ middleware | ✅ |
| Giới hạn dùng chung giữa các tiến trình | ✅ vùng bộ nhớ dùng chung | ❌ đếm theo từng tiến trình | — (chỉ 1 tiến trình) | tùy mô-đun | 1 instance; nhiều instance với Redis | ✅ bộ nhớ dùng chung |
| WAF (chữ ký SQLi/XSS, trình quét…) | 🔌 ModSecurity, Thương mại (App Protect) | ❌ (phải tự viết script Lua) | 🔌 Coraza | 🔌 ModSecurity | 🔌 plugin | ✅ tích hợp |
| Danh sách chặn có thời hạn, tái phạm | ⚙️ fail2ban | ⚙️ fail2ban | ⚙️ fail2ban | ⚙️ fail2ban | ⚙️ | ✅ tích hợp |
| Mồi nhử, chế độ chiến tranh, sự cố, xuất IoC | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ Active Defense |
| Kiểm tra bảo mật cấu hình | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ `audit security` |
| Chế độ quan sát (ghi log mà không chặn) | tùy mô-đun | — | tùy plugin | ✅ ModSecurity `DetectionOnly` | tùy plugin | ✅ |

### Khả năng mở rộng

| Chức năng | nginx | lighttpd | Caddy | Apache | Traefik | omega-serv 2.0 |
|---|---|---|---|---|---|---|
| Ngôn ngữ script | 🧩 njs (JavaScript); 🔌 Lua (OpenResty) | ✅ Lua (mod_magnet) | mô-đun Go (biên dịch lại) | 🧩 mod_lua | plugin Go hoặc WebAssembly | 🔌 nhập script mod_magnet (tùy chọn `magnet`) |
| Hệ sinh thái mô-đun | rất rộng | chọn lọc | rộng | rất rộng | rộng | không có: mọi thứ đều tích hợp |

---

## 6. Quản trị và trải nghiệm sử dụng

| Máy chủ | Cách quản trị chính | Giao diện | Nạp lại không gián đoạn |
|---|---|---|---|
| nginx | tệp cấu hình | không có (bảng điều khiển: NGINX Plus, thương mại) | ✅ `nginx -s reload` |
| lighttpd | tệp cấu hình | không có (mod_status chỉ đọc) | ✅ khởi động lại mềm |
| Caddy | Caddyfile hoặc JSON | API REST quản trị | ✅ qua API |
| Apache | tệp cấu hình và `.htaccess` | không có (mod_status chỉ đọc) | ✅ `graceful` |
| Traefik | nhãn container, tệp hoặc Kubernetes | bảng điều khiển web (chỉ đọc) | ✅ cấu hình động |
| omega-serv | giao diện terminal (TUI) và dòng lệnh (CLI); không cần sửa tệp JSON | **TUI đầy đủ bằng bàn phím và chuột, 17 ngôn ngữ, trợ giúp tích hợp** | ✅ cho phần lớn thiết lập; báo trước việc khởi động lại cho cổng, TLS và số tiến trình |

Cụ thể, với omega-serv, cấu hình, bảo mật, log, dịch vụ hệ thống, sao lưu và instance đều được quản lý từ một giao diện duy nhất. Mỗi thiết lập được giải thích và kiểm tra trước khi ghi. Với các máy chủ khác, người ta sửa tệp văn bản, rồi dùng đến các công cụ riêng (Certbot, fail2ban, logrotate, ModSecurity, một công cụ giám sát…).

Đổi lại, cách tiếp cận « tệp cấu hình » của nginx, Apache và Caddy rất dễ tự động hóa (Ansible, container, quản lý phiên bản). omega-serv có CLI có thể viết script, nhưng hệ sinh thái tự động hóa của nó vẫn còn hạn chế.

---

## 7. Những gì omega-serv mang lại thêm

Phần này chỉ giữ lại những gì không máy chủ nào trong số được so sánh cung cấp sẵn, mà không cần mô-đun bên thứ ba hay công cụ bên ngoài.

1. **Quản trị đầy đủ qua giao diện terminal.**
   - Giao diện bao phủ toàn bộ máy chủ: trang web, bảo mật, log, dịch vụ, sao lưu và instance.
   - Nó dùng được bằng bàn phím và chuột, trên một máy chủ không có giao diện đồ họa, kể cả qua SSH.
   - Nó có sẵn bằng 17 ngôn ngữ và giải thích từng thiết lập.
   - Các máy chủ khác không có giao diện quản trị (nginx, lighttpd, Apache), hoặc chỉ có một API (Caddy) hay một bảng điều khiển chỉ đọc (Traefik).
2. **Bảo mật chủ động tích hợp, không cần lắp ghép mô-đun.**
   - WAF gồm chữ ký, danh sách đường dẫn có thể sửa, tái phạm, danh sách chặn có thời hạn, danh tiếng và chế độ quan sát.
   - Active Defense bổ sung mồi nhử, chế độ chiến tranh, theo dõi sự cố, xuất chỉ báo xâm phạm và mô phỏng không tác động.
   - Ở nơi khác, các chức năng này đòi hỏi lắp ghép ModSecurity hoặc Coraza, các bộ quy tắc và fail2ban.
3. **Giới hạn bảo mật chính xác với nhiều tiến trình.**
   - Ở chế độ boost, giới hạn tốc độ và tái phạm của WAF được chia sẻ trong bộ nhớ giữa các tiến trình. Vì vậy kẻ tấn công không thể nhân giới hạn của mình lên theo số tiến trình.
   - lighttpd ghi lại trường hợp ngược lại: với `server.max-worker`, `mod_evasive` và `mod_status` đếm riêng trong từng tiến trình.
   - nginx cũng chia sẻ bộ đếm (vùng `limit_req`), nhưng không có WAF tích hợp.
4. **Nhập script mod_magnet của lighttpd.**
   - Một script bảo vệ Lua đã viết cho lighttpd có thể được nhập mà không cần viết lại.
   - Nó được cộng thêm vào lớp bảo vệ tích hợp mà không bao giờ có thể làm yếu nó, và tính tương thích được kiểm tra trước khi kích hoạt.
5. **Quản lý nhiều instance.**
   - Một sổ đăng ký liệt kê mọi instance, và giao diện chuyển từ instance này sang instance khác.
   - Nó cũng có thể gỡ cài đặt hoàn toàn một instance.
6. **Kiểm tra bảo mật cấu hình**: lệnh `audit security` mang tính thông tin, không bao giờ chặn và trả về mã thoát có thể dùng trong script.
7. **Nguồn log từ xa.**
   - Giao diện tải log của một máy chủ khác qua SSH, theo yêu cầu, không lưu mật khẩu.
   - Nó có thể đọc log đó bằng lnav, hợp nhất với các log cục bộ.
8. **Gia cố HTTP không thể tắt**, hoạt động ngay từ khi cài đặt, với bất kỳ hồ sơ nào:
   - kiểm tra nghiêm ngặt tiêu đề Host;
   - từ chối các điểm mơ hồ Content-Length / Transfer-Encoding;
   - tiêu đề bảo mật và CSP, kể cả trên trang lỗi;
   - đọc X-Forwarded-For một cách an toàn;
   - từ chối khởi động bằng root.

---

## 8. Những gì các máy chủ khác làm tốt hơn

- **Thông lượng và độ trễ**: nginx và lighttpd phục vụ nhiều hơn 10 đến 20 lần số yêu cầu nhỏ, với độ trễ thấp hơn 8 đến 10 lần. Với một trang có lưu lượng lớn, một API công khai hay một CDN, đó là những máy chủ nên chọn.
- **Bộ nhớ**: lighttpd (1 MB) và nginx (4 đến 5 MB) phù hợp với các máy rất hạn chế tài nguyên (thiết bị nhúng, Raspberry Pi cấp thấp, container nhỏ).
- **Giao thức**: HTTP/2 ở tất cả các máy chủ khác, HTTP/3 ở nginx, Caddy và Traefik. omega-serv chỉ dùng HTTP/1.1.
- **HTTPS tự động**: Caddy và Traefik tích hợp mặc định, nginx (`ngx_http_acme_module`) và Apache (`mod_md`) qua một mô-đun chính thức. omega-serv giao cho Certbot, với trình hướng dẫn và gia hạn theo lịch.
- **Môi trường container hóa**: khả năng tự động khám phá dịch vụ của Traefik (Docker, Kubernetes) không có tương đương trong omega-serv.
- **Hệ sinh thái**: nginx và Apache có hàng nghìn mô-đun, hướng dẫn và tích hợp. Caddy có một hệ thống mô-đun bằng Go. omega-serv là một dự án non trẻ, do một người duy trì.
- **Nén tức thời**: omega-serv chỉ phục vụ các tệp đã được nén sẵn.

---

## 9. Máy chủ nào cho nhu cầu nào

| Nhu cầu | Lựa chọn khuyến nghị |
|---|---|
| Trang lưu lượng lớn, API công khai, CDN, thông lượng tối đa | **nginx** |
| Máy rất hạn chế tài nguyên, thiết bị nhúng, tệp tĩnh | **lighttpd** |
| Khởi đầu nhanh với HTTPS tự động, cấu hình ngắn gọn | **Caddy** |
| Ứng dụng PHP lâu đời, `.htaccess`, hosting chia sẻ | **Apache** |
| Docker, Kubernetes, microservice | **Traefik** |
| Trang nhỏ, dịch vụ nội bộ, phòng lab, VPN, quản trị không cần sửa tệp | **omega-serv** |
| Máy chủ mở ra Internet mà bạn muốn xem và kiểm soát bảo mật (WAF, lệnh cấm, mồi nhử) từ một giao diện duy nhất | **omega-serv** |
| Reverse proxy nội bộ có phân phối tải, kiểm tra sức khỏe và cache, điều khiển từ một giao diện | **omega-serv** |
| Học về gia cố HTTP và phòng thủ chủ động | **omega-serv** |

Các công cụ này cũng có thể kết hợp với nhau. Ví dụ:
- nginx hoặc Traefik ở tuyến đầu trên Internet, với omega-serv phía sau cho một dịch vụ nội bộ, bảo mật và việc quản trị của nó;
- omega-serv làm reverse proxy nội bộ phía trước nhiều máy chủ ứng dụng.

---

## 10. Tái hiện các số đo

Các công cụ được cung cấp trong kho mã, dưới `tools/bench/`. Cần cài nginx, lighttpd, Caddy và oha, cùng với môi trường phát triển của omega-serv (`.venv`).

```sh
# 1. chuẩn bị thư mục đo (tệp thử, cấu hình, omega-serv 1.0 và 2.0)
tools/bench/compare/setup.sh /duong/dan/do omega-serv-1.0.0.tar.gz

# 2. 12 cấu hình, 3 lần lặp xen kẽ (khoảng 22 phút)
tools/bench/compare/campaign.sh /duong/dan/do > ket-qua.txt

# 3. trung vị
python3 tools/bench/compare/summarize.py ket-qua.txt

# tải xuống tệp lớn (bộ nhớ và độ phản hồi), 2.0 rồi 1.0
.venv/bin/python tools/bench/bigfile.py
BENCH_SRC=/duong/dan/do/v1-archive/omega-serv/src \
BENCH_EXTRA_PATH=/duong/dan/do/v1-archive/omega-serv/vendor/omega-lib/src \
  .venv/bin/python tools/bench/bigfile.py

# đo bất kỳ máy chủ nào khác đang chạy, không cần oha
python3 tools/bench/bench_any.py --make-files /srv/webroot-thu-nghiem
python3 tools/bench/bench_any.py --port 8080
```

Mặc định, máy chủ được ghim vào luồng 0 và 2, còn client vào luồng 1 và 3, phù hợp với máy dùng để đo. Hãy điều chỉnh cách phân bổ này theo bộ xử lý của bạn (`lscpu -e` cho biết cấu trúc) bằng các biến `SRV_CPUS` và `CLI_CPUS`.

Để công bố kết quả của riêng bạn, hãy nêu rõ máy, phiên bản, cách phân bổ bộ xử lý và ba lần lặp.

---

## 11. Nguồn

Chức năng của các máy chủ khác, theo tài liệu chính thức của chúng (tra cứu ngày 26 tháng 10 năm 2026).

**nginx**
- [Giới hạn tốc độ `limit_req` (vùng bộ nhớ dùng chung)](https://nginx.org/en/docs/http/ngx_http_limit_req_module.html)
- [Tệp nén sẵn `gzip_static`](https://nginx.org/en/docs/http/ngx_http_gzip_static_module.html)
- [Mô-đun ACME chính thức `ngx_http_acme_module`](https://nginx.org/en/docs/http/ngx_http_acme_module.html)
- [Cân bằng tải (`upstream`)](https://nginx.org/en/docs/http/ngx_http_upstream_module.html)
- [HTTP/3](https://nginx.org/en/docs/http/ngx_http_v3_module.html)
- [Bộ kết nối ModSecurity cho nginx](https://github.com/owasp-modsecurity/ModSecurity-nginx)

**lighttpd**
- [`server.max-worker`: không khuyến khích, bộ đếm theo tiến trình cho mod_status và mod_evasive](https://redmine.lighttpd.net/projects/lighttpd/wiki/Server_max-workerDetails)
- [mod_magnet (script Lua)](https://redmine.lighttpd.net/projects/lighttpd/wiki/Docs_ModMagnet)
- [mod_deflate (nén, cache)](https://redmine.lighttpd.net/projects/lighttpd/wiki/Mod_deflate)
- [mod_proxy (phân phối tải, sức khỏe thụ động, WebSocket)](https://redmine.lighttpd.net/projects/lighttpd/wiki/Docs_ModProxy)
- [mod_evasive (kết nối đồng thời theo địa chỉ)](https://redmine.lighttpd.net/projects/lighttpd/wiki/Docs_ModEvasive)

**Caddy**
- [HTTPS tự động](https://caddyserver.com/docs/automatic-https)
- [`file_server` và `precompressed`](https://caddyserver.com/docs/caddyfile/directives/file_server)
- [`reverse_proxy` (chiến lược, sức khỏe chủ động và thụ động)](https://caddyserver.com/docs/caddyfile/directives/reverse_proxy)
- [API quản trị](https://caddyserver.com/docs/api)
- [Plugin giới hạn tốc độ caddy-ratelimit](https://github.com/mholt/caddy-ratelimit)
- [WAF Coraza cho Caddy](https://github.com/corazawaf/coraza-caddy)
- [caddy-docker-proxy](https://github.com/lucaslorentz/caddy-docker-proxy)

**Apache HTTP Server**
- [mod_md (ACME)](https://httpd.apache.org/docs/2.4/mod/mod_md.html)
- [mod_proxy_balancer](https://httpd.apache.org/docs/2.4/mod/mod_proxy_balancer.html)
- [mod_proxy_hcheck](https://httpd.apache.org/docs/2.4/mod/mod_proxy_hcheck.html)
- [mod_http2](https://httpd.apache.org/docs/2.4/mod/mod_http2.html)
- [mod_deflate, nội dung nén sẵn](https://httpd.apache.org/docs/2.4/mod/mod_deflate.html)
- [ModSecurity](https://github.com/owasp-modsecurity/ModSecurity)

**Traefik**
- [Middleware `ratelimit` (trong bộ nhớ theo từng instance, Redis tùy chọn)](https://doc.traefik.io/traefik/reference/routing-configuration/http/middlewares/ratelimit/)
- [ACME](https://doc.traefik.io/traefik/https/acme/)
- [Providers (Docker, Kubernetes…)](https://doc.traefik.io/traefik/providers/overview/)

**Công cụ đo**
- [oha](https://github.com/hatoo/oha)

---

*So sánh do kraynux thực hiện cho omega-serv 2.0.0: số đo ngày 26 tháng 10 năm 2026. Các số đo chỉ trên một máy duy nhất. Với mọi quyết định về năng lực, hãy đo trên phần cứng của chính bạn bằng các công cụ được cung cấp.*
