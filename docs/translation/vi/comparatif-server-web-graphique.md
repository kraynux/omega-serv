# omega-serv so với các máy chủ web trên thị trường — phiên bản biểu đồ

**omega-serv so với nginx · lighttpd · Apache · Caddy · Traefik — đo trên ba máy (tháng 11 năm 2026).**

🌐 [Français](../../comparatif-server-web-graphique.md) · [English](../en/comparatif-server-web-graphique.md) · [Español](../es/comparatif-server-web-graphique.md) · [Português (Brasil)](../pt-BR/comparatif-server-web-graphique.md) · [Italiano](../it/comparatif-server-web-graphique.md) · [Deutsch](../de/comparatif-server-web-graphique.md) · [Nederlands](../nl/comparatif-server-web-graphique.md) · [Polski](../pl/comparatif-server-web-graphique.md) · [Русский](../ru/comparatif-server-web-graphique.md) · [中文](../zh-CN/comparatif-server-web-graphique.md) · **Tiếng Việt** · [ไทย](../th/comparatif-server-web-graphique.md) · [Bahasa Indonesia](../id/comparatif-server-web-graphique.md) · [日本語](../ja/comparatif-server-web-graphique.md) · [한국어](../ko/comparatif-server-web-graphique.md) · [हिन्दी](../hi/comparatif-server-web-graphique.md) · [العربية](../ar/comparatif-server-web-graphique.md)

> **Cách đọc:** thanh càng dài thì máy chủ càng nhanh. Mốc tham chiếu là **nginx = 1,00**.

## Chú giải màu sắc

<!-- 🖼️ IMAGE : legende-couleurs -->
<div align="center">
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/translation/vi/omega-serv/stats-1.png" alt="Chú giải màu sắc" width="1024">
</div>

---

## 📊 Tệp 1 KB — thông lượng (yêu cầu/giây)

Máy A (i5 2010), B (Celeron 2016) và C (Ryzen 2024). Các thanh được chuẩn hóa theo nginx (1,00) trên cùng một máy.

<!-- 🖼️ IMAGE : 1ko-banner — 3 colonnes côte à côte (Machine A · 2 cœurs | Machine B · 4 cœurs | Machine C · 10 cœurs), largeur totale -->
<div align="center">
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/translation/vi/omega-serv/stats-2.png" alt="Tệp 1 Ko — máy A, B và C" width="1024">
</div>

> \* Máy C: bộ máy native dùng 4 lõi, nginx dùng 2 tiến trình (2 lõi). Khi số lõi bằng nhau, tỷ lệ giảm về khoảng 0,70.
---

## 📦 Tệp trung bình (100 KB) — chế độ web thông thường

Ở đây Apache gây bất ngờ: nó thường vượt bộ máy native của omega-serv. lighttpd vẫn nhanh nhất. Mốc tham chiếu: nginx = 1,00.

<!-- 🖼️ IMAGE : 100ko-banner.png — 3 colonnes côte à côte (A | B | C), largeur totale -->
<div align="center">
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/translation/vi/omega-serv/stats-3.png" alt="Tệp 100 Ko — máy A, B và C" width="1024">
</div>

---

## 💿 Tệp lớn (5 MB) — chế độ web thông thường

Với tệp lớn, các máy chủ ngang nhau: chính nhân hệ điều hành sao chép dữ liệu (sendfile). Caddy là ngoại lệ trên máy C. Thông lượng tính bằng MB/s.

<!-- 🖼️ IMAGE : 5mo-banner.png — 3 colonnes côte à côte (A | B | C), largeur totale -->
<div align="center">
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/translation/vi/omega-serv/stats-4.png" alt="Tệp 5 Mo — máy A, B và C" width="1024">
</div>

---

## 🔄 Reverse proxy — phản hồi nhỏ (1 KB)

Mỗi proxy chuyển tiếp tới một backend nginx. Mốc tham chiếu: nginx = 1,00. Máy C: 4 tiến trình.

<!-- 🖼️ IMAGE : proxy-1ko-banner.png — 3 colonnes côte à côte (A | B | C), largeur totale -->
<div align="center">
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/translation/vi/omega-serv/stats-5.png" alt="Proxy 1 Ko — máy A, B và C" width="1024">
</div>

---

## 🔄 Reverse proxy — phản hồi 100 KB

Với phản hồi trung bình, omega-serv native ngang bằng hoặc vượt nginx.

<!-- 🖼️ IMAGE : proxy-100ko-banner.png — 3 colonnes côte à côte (A | B | C), largeur totale -->
<div align="center">
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/translation/vi/omega-serv/stats-6.png" alt="Proxy 100 Ko — máy A, B và C" width="1024">
</div>

---

## 💾 Bộ nhớ (PSS) — lúc nghỉ → sau khi chịu tải

Thanh càng ngắn thì máy chủ càng tiết kiệm. lighttpd, nginx và Apache tiết kiệm nhất; tiếp theo là omega-serv 3.0.0 (đo lại ngày 19 tháng 11), với 10 đến 16 MB cho bộ máy native.

<!-- 🖼️ IMAGE : memoire-banner.png — 3 colonnes côte à côte de jauges (A | B | C), largeur totale -->
<div align="center">
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/translation/vi/omega-serv/stats-7.png" alt="Bộ nhớ — máy A, B và C" width="1024">
</div>

---

## 🏆 Xếp hạng web thông thường — ai nhanh nhất?

Tổng hợp ba máy về phục vụ tệp tĩnh.

<!-- 🖼️ IMAGE : classement-web.png -->
<!-- Contenu : 1. 🥇 lighttpd — meilleur en petits & moyens fichiers · 2. 🥈 nginx — référence, excellent partout · 3. 🥉 Apache — bon, robuste, écosystème · 4. omega-serv natif — très bon, 2ᵉ en reverse proxy · 5. Caddy — simple, HTTPS auto · 6. omega-serv Python — moteur de repli -->
<div align="center">
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/translation/vi/omega-serv/stats-8.png" alt="Xếp hạng web thông thường" width="1024">
</div>

---

## 🔄 Xếp hạng reverse proxy — ai tốt nhất?

nginx vẫn là mốc tham chiếu; omega-serv native là á quân sát nút của nó, bỏ xa các máy chủ còn lại.

<!-- 🖼️ IMAGE : classement-proxy.png -->
<!-- Contenu : 1. 🥇 nginx · 2. 🥈 omega-serv natif — 0,82 à 0,91× nginx en 1 Ko · 3. 🥉 omega-serv + WAF — toujours devant lighttpd/Apache · 4. lighttpd — 0,53 à 0,61× · 5. Apache — 0,50 à 0,59× · 6. Traefik — 0,29 à 0,35× · 7. Caddy — 0,23 à 0,32× · 8. omega-serv Python — moteur de repli -->
<div align="center">
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/translation/vi/omega-serv/stats-9.png" alt="Xếp hạng reverse proxy" width="1024">
</div>

---

## 🆚 Đối đầu — xếp hạng web & reverse proxy cạnh nhau

Hai cách dùng, hai bảng xếp hạng. Một máy chủ có thể nổi bật ở bên này và gây thất vọng ở bên kia: Apache gây bất ngờ khi chuyển tiếp, Caddy gây thất vọng ở mọi nơi trừ sự đơn giản.

<!-- 🖼️ IMAGE : face-a-face.png — 2 colonnes côte à côte (web | proxy), largeur totale -->
<div align="center">
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/translation/vi/omega-serv/stats-10.png" alt="Đối đầu web và reverse proxy" width="1024">
</div>

### Tổng hợp chéo

| Máy chủ | Vị trí |
|---|---|
| 🟢 **omega-serv native** | Đa năng nhất: thứ 4 về web, **thứ 2 về reverse proxy**. Máy chủ duy nhất có WAF tích hợp mà vẫn đứng trước lighttpd và Apache khi chuyển tiếp. Sự dung hòa tốt nhất cho một công cụ duy nhất bao phủ cả hai cách dùng, kèm thêm bảo mật. |
| 🔵 **nginx** | Ổn định nhất: thứ 2 về web, **thứ 1 về reverse proxy**. Luôn ở nhóm đầu bảng xếp hạng, không có điểm yếu nổi bật. Lựa chọn mặc định khi không có yêu cầu đặc biệt. |
| 🟢 **lighttpd** | Vận động viên chạy nước rút của tệp tĩnh: **thứ 1 về web**, nhưng thứ 4 khi chuyển tiếp. Lựa chọn tốt nhất cho tệp tĩnh thuần túy, nhường chỗ cho omega-serv hoặc nginx ngay khi thêm reverse proxy. |
| 🔴 **Apache** | Phản ví dụ: thứ 3 về web, thứ 5 khi chuyển tiếp. Với tệp lớn, nó thậm chí còn làm nginx bất ngờ (máy C). Không nhanh nhất cũng không nhẹ nhất: thế mạnh của nó vẫn là hệ sinh thái PHP. |
| 🟠 **Caddy** | Đơn giản hơn tốc độ: thứ 5 về web, **thứ 7 khi chuyển tiếp**. Không sinh ra cho thông lượng: HTTPS tự động và cấu hình ngắn gọn. Nên dành cho các dự án nhỏ. |
| 🟣 **Traefik** | Ngoài nhóm web: không phải máy chủ tệp, thứ 6 khi chuyển tiếp. Sân chơi của nó vẫn là Docker và Kubernetes, không phải hiệu năng thô. |

---

## 📋 Bảng tổng hợp đầy đủ — tỷ lệ so với nginx (1,00)

Tổng quan về **tất cả** các chỉ số: chế độ web thông thường (1 KB, 100 KB, 5 MB) và reverse proxy (1 KB, 100 KB), cộng với bộ nhớ. Giá trị càng gần 1,00 hoặc cao hơn thì càng tốt.

| Máy chủ | Web 1 KB (A/B/C) | Web 100 KB (A/B/C) | Web 5 MB (A/B/C) | Proxy 1 KB (A/B/C) | Proxy 100 KB (A/B/C) | Bộ nhớ (A/B/C) |
|---|---|---|---|---|---|---|
| **lighttpd** | 1,52 / 1,26 / 1,53 | 1,08 / 1,07 / 1,26 | 1,05 / 0,99 / 0,81 | 0,61 / 0,56 / 0,53 | 0,74 / 0,62 / 0,96 | 1 MB |
| **nginx** | 1,00 / 1,00 / 1,00 | 1,00 / 1,00 / 1,00 | 1,00 / 1,00 / 1,00 | 1,00 / 1,00 / 1,00 | 1,00 / 1,00 / 1,00 | 4–5 MB |
| **omega-serv (natif)** | **0,70 / 0,67 / 1,15\*** | **0,38 / 0,28 / 0,61** | **0,99 / 0,91 / 1,09** | **0,85 / 0,91 / 0,82** | **1,11 / 0,97 / 1,43** | 10–16 MB |
| **omega-serv + WAF** | 0,56 / 0,53 / 1,07\* | 0,37 / 0,27 / 0,62 | — | 0,81 / 0,89 / 0,77 | 1,10 / 0,93 / 1,30 | 28–33 MB |
| **Apache** | 0,42 / 0,35 / 0,76 | 0,55 / 0,62 / 0,97 | 1,01 / 1,00 / 1,19 | 0,59 / 0,53 / 0,50 | 0,62 / 0,65 / 0,71 | 4–9 MB |
| **Caddy** | 0,26 / 0,17 / 0,21 | 0,40 / 0,33 / 0,14 | 0,95 / 0,94 / 0,11 | 0,32 / 0,28 / 0,23 | 0,60 / 0,54 / 0,59 | 46–67 MB |
| **Traefik** | — | — | — | 0,35 / 0,35 / 0,29 | 0,64 / 0,60 / 0,70 | 93–131 MB |
| **omega-serv (Python)** | 0,11 / 0,05 / 0,08 | 0,14 / 0,10 / 0,12 | 0,92 / 0,91 / 0,75 | 0,09 / 0,08 / 0,07 | 0,21 / 0,19 / — | 20–48 MB |

> \* Máy C: 4 lõi cho native so với 2 lõi cho nginx; khi số lõi bằng nhau, tỷ lệ khoảng 0,67–0,71.
> Ba giá trị trong mỗi ô tương ứng với các máy **A / B / C**. « — »: không đo hoặc không áp dụng.

---

## ⚖️ Điểm mạnh và điểm yếu — tất cả máy chủ

Mỗi máy chủ có thế mạnh và giới hạn riêng. Dưới đây là bức tranh đầy đủ, không thiên vị.

### 🟢 omega-serv (native)

**Điểm mạnh**
- ✅ Quản trị đầy đủ trong terminal (TUI, 17 ngôn ngữ)
- ✅ Tích hợp sẵn WAF + Active Defense + RIPOSTE
- ✅ Bộ máy native C++: ~0,7× nginx với tệp tĩnh
- ✅ Thứ 2 về reverse proxy, sau nginx
- ✅ Giới hạn dùng chung giữa các tiến trình (bảo mật chính xác)
- ✅ Nhập script mod_magnet của lighttpd
- ✅ Quản lý nhiều instance
- ✅ Quản trị web


**Điểm yếu**
- ❌ Không có HTTP/2 và HTTP/3
- ❌ Không nén trực tiếp
- ❌ Không có khám phá Docker/Kubernetes
- ❌ ACME qua Certbot (không tích hợp sẵn)
- ❌ Tệp 100 KB: 0,3–0,6× nginx
- ❌ Bộ nhớ 10–55 MB tùy chế độ (so với 1–5 MB của nginx/lighttpd)
- ❌ Hệ sinh thái còn non trẻ, do một người duy trì

---

### 🔵 nginx

**Điểm mạnh**
- ✅ Chuẩn mực về hiệu năng và độ ổn định
- ✅ HTTP/2, HTTP/3, nén
- ✅ Hệ sinh thái khổng lồ (mô-đun, tài liệu, cộng đồng)
- ✅ Rất tiết kiệm bộ nhớ (4–5 MB)
- ✅ Reverse proxy xuất sắc
- ✅ Mô-đun ACME chính thức
- ✅ Cấu hình trưởng thành và đã được kiểm chứng

**Điểm yếu**
- ❌ Cấu hình dài dòng, cú pháp riêng cần học
- ❌ Không có WAF tích hợp (cần ModSecurity hoặc tương đương)
- ❌ Không có giao diện quản trị gốc
- ❌ Tải lại cấu hình đôi khi khó khăn trong môi trường production
- ❌ Bản mã nguồn mở bị hạn chế (một số chức năng thuộc Nginx Plus trả phí)
- ❌ Không có khám phá Docker/Kubernetes gốc (qua template)

---

### 🟢 lighttpd

**Điểm mạnh**
- ✅ Nhanh nhất với tệp nhỏ/trung bình
- ✅ Tiết kiệm bộ nhớ nhất (1 MB)
- ✅ Nhẹ, phù hợp với hệ thống hạn chế
- ✅ Reverse proxy tốt
- ✅ Cấu hình đơn giản và dễ đọc

**Điểm yếu**
- ❌ Không có HTTP/3 (HTTP/2 một phần tùy bản build)
- ❌ Chỉ thứ 4 về reverse proxy (0,53–0,61× nginx)
- ❌ Hệ sinh thái nhỏ hơn nginx/Apache
- ❌ Không có WAF tích hợp
- ❌ Không có khám phá Docker/Kubernetes
- ❌ Phát triển kém sôi động hơn trước đây
- ❌ Yếu với tệp lớn (0,81× nginx trên máy C)

---

### 🔴 Apache

**Điểm mạnh**
- ✅ Hệ sinh thái lịch sử khổng lồ (mô-đun, `.htaccess`, PHP)
- ✅ Vững chắc và được kiểm chứng qua nhiều thập kỷ
- ✅ Xuất sắc với tệp lớn (vượt nginx trên máy C)
- ✅ Hỗ trợ `.htaccess` không cần khởi động lại
- ✅ Có nén, HTTP/2, ACME
- ✅ Tài liệu phong phú

**Điểm yếu**
- ❌ Chậm với tệp nhỏ (0,35–0,42× nginx)
- ❌ Tốn bộ nhớ ở chế độ prefork (4–9 MB, tăng nhanh khi có tải)
- ❌ Mô hình tiến trình kém hiệu quả hơn mô hình hướng sự kiện
- ❌ Cấu hình dài dòng
- ❌ Thứ 5 về reverse proxy (0,50–0,59× nginx)
- ❌ Không có WAF tích hợp (ModSecurity là mô-đun riêng)
- ❌ Bề mặt tấn công vốn rộng hơn

---

### 🟠 Caddy

**Điểm mạnh**
- ✅ HTTPS tự động (ACME tích hợp, không cần cấu hình)
- ✅ Cấu hình rất ngắn gọn và dễ đọc (Caddyfile)
- ✅ HTTP/2 và HTTP/3 gốc
- ✅ Một tệp nhị phân duy nhất, triển khai đơn giản
- ✅ Reverse proxy khá với phản hồi trung bình

**Điểm yếu**
- ❌ Thông lượng thô chậm (thứ 5 về web, thứ 7 khi chuyển tiếp)
- ❌ Bộ nhớ cao (46–67 MB)
- ❌ Rất yếu với tệp lớn trên máy C (0,11× nginx)
- ❌ Không có WAF tích hợp
- ❌ Hệ sinh thái trẻ hơn nginx/Apache
- ❌ Không phù hợp với thông lượng rất cao

---

### 🟣 Traefik

**Điểm mạnh**
- ✅ Tự động khám phá Docker/Kubernetes
- ✅ Lý tưởng trong môi trường container
- ✅ HTTPS tự động (ACME tích hợp)
- ✅ Cấu hình động không cần khởi động lại
- ✅ Reverse proxy tốt với phản hồi trung bình (0,60–0,70× nginx)

**Điểm yếu**
- ❌ Không phải máy chủ tệp (không có trong bảng xếp hạng web)
- ❌ Thứ 6 về reverse proxy (0,29–0,35× nginx với 1 KB)
- ❌ Bộ nhớ rất cao (93–131 MB)
- ❌ Cấu hình phức tạp ngoài môi trường container
- ❌ Không có WAF tích hợp
- ❌ Quá cồng kềnh cho một trang tĩnh đơn giản

---

## 🎯 Máy chủ nào cho nhu cầu nào?

| Nhu cầu | Máy chủ khuyến nghị | Lý do |
|---|---|---|
| Trang có lưu lượng lớn | **nginx** hoặc **lighttpd** | Thông lượng tối đa, HTTP/2-3 |
| Máy hạn chế / nhúng | **lighttpd** | 1 MB bộ nhớ, nhanh nhất và ít tốn tài nguyên nhất |
| HTTPS tự động đơn giản | **Caddy** | Chứng chỉ tự động, cấu hình ngắn gọn |
| Docker / Kubernetes | **Traefik** | Khám phá dịch vụ |
| Ứng dụng PHP / .htaccess | **Apache** | Hệ sinh thái lịch sử |
| Reverse proxy | **nginx** hoặc **omega-serv (native)** | Hiệu năng tốt nhất |
| Trang web + bảo mật + giao diện | **omega-serv (native)** | Hạ tầng đầy đủ: WAF, quản trị web, nhiều instance, reverse proxy, trình quản lý log, sao lưu… |

---

Dữ liệu lấy từ bản so sánh omega-serv (tháng 11 năm 2026) — kraynux. Giấy phép MIT.
[oha](https://github.com/hatoo/oha) pour la mesure · graphiques HTML/CSS autonomes.

> *Phiên bản biểu đồ của bản so sánh có đo đạc của omega-serv (cùng số liệu với bản so sánh chi tiết: các phép đo ngày 3 và 4 tháng 11 năm 2026 trên ba máy; reverse proxy: ngày 14 tháng 11 năm 2026; bộ nhớ của omega-serv 3.0.0: ngày 19 tháng 11 năm 2026). Với mọi quyết định về năng lực, hãy đo trên phần cứng của chính bạn.*
>
> Copyright © 2026 kraynux — kraynux@proton.me — Giấy phép MIT (xem tệp LICENSE).
