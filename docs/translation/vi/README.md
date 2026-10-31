<!-- Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE) -->
<div align="center">
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/assets/omega-serv.png" alt="Omega-Serv" width="384">
</div>

# 🔒 OMEGA-SERV

**Máy chủ web HTTP độc lập, di động và được gia cố mặc định**

> Được xây dựng bởi **kraynux** cho **Omega-server** 
[kraynux.snake-mackarel](https://kraynux.snake-mackarel.ts.net)

Trang chính thức: [OMEGA-SERV](https://kraynux.snake-mackarel.ts.net/omega-serv/translation/vi/) &nbsp; Tham chiếu, sử dụng, trợ giúp & FAQ: [Hướng dẫn đầy đủ](https://kraynux.snake-mackarel.ts.net/omega-serv/translation/vi/guide.html)  
Xem trước: [Ảnh chụp màn hình](https://kraynux.snake-mackarel.ts.net/omega-serv/screenshots/) &nbsp; Trình diễn [Máy chủ demo](https://craftdark.snake-mackarel.ts.net) &nbsp; [So sánh/Kiểm thử các máy chủ web](comparatif-serveurs-web.md)  

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](../../../LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![Lua](https://img.shields.io/badge/Lua-5.4%2B-2C2D72.svg)](https://www.lua.org/)
[![JavaScript](https://img.shields.io/badge/JavaScript-ES2020%2B-F7DF1E.svg)](https://developer.mozilla.org/docs/Web/JavaScript)
[![HTML](https://img.shields.io/badge/HTML-5-E34F26.svg)](https://developer.mozilla.org/docs/Web/HTML)
[![Platform](https://img.shields.io/badge/Platform-Linux-informational.svg)](https://www.linux.org/)
[![Interface](https://img.shields.io/badge/Interface-CLI%20%2B%20TUI-cyan.svg)](#3-sử-dụng)
[![Textual](https://img.shields.io/badge/Textual-TUI-5A5AFB.svg)](https://textual.textualize.io/)

🌐 Tài liệu, bản xuất & giao diện có sẵn bằng **17 ngôn ngữ** — xem [Ngôn ngữ giao diện](#ngôn-ngữ-giao-diện).  
**Ngôn ngữ:**
<img src="https://flagcdn.com/w20/fr.png" alt="France" style="height:14px;"> [Français](../../../README.md) · <img src="https://flagcdn.com/w20/gb.png" alt="English" style="height:14px;"> [English](../en/README.md) · <img src="https://flagcdn.com/w20/es.png" alt="Español" style="height:14px;"> [Español](../es/README.md) · <img src="https://flagcdn.com/w20/br.png" alt="Português (Brasil)" style="height:14px;"> [Português (Brasil)](../pt-BR/README.md) · <img src="https://flagcdn.com/w20/it.png" alt="Italiano" style="height:14px;"> [Italiano](../it/README.md) · <img src="https://flagcdn.com/w20/de.png" alt="Deutsch" style="height:14px;"> [Deutsch](../de/README.md) · <img src="https://flagcdn.com/w20/nl.png" alt="Nederlands" style="height:14px;"> [Nederlands](../nl/README.md) · <img src="https://flagcdn.com/w20/pl.png" alt="Polski" style="height:14px;"> [Polski](../pl/README.md) · <img src="https://flagcdn.com/w20/ru.png" alt="Русский" style="height:14px;"> [Русский](../ru/README.md) · <img src="https://flagcdn.com/w20/cn.png" alt="中文" style="height:14px;"> [中文](../zh-CN/README.md) · <img src="https://flagcdn.com/w20/vn.png" alt="Tiếng Việt" style="height:14px;"> [Tiếng Việt](README.md) · <img src="https://flagcdn.com/w20/th.png" alt="ไทย" style="height:14px;"> [ไทย](../th/README.md) · <img src="https://flagcdn.com/w20/id.png" alt="Bahasa Indonesia" style="height:14px;"> [Bahasa Indonesia](../id/README.md) · <img src="https://flagcdn.com/w20/jp.png" alt="日本語" style="height:14px;"> [日本語](../ja/README.md) · <img src="https://flagcdn.com/w20/kr.png" alt="한국어" style="height:14px;"> [한국어](../ko/README.md) · <img src="https://flagcdn.com/w20/in.png" alt="हिन्दी" style="height:14px;"> [हिन्दी](../hi/README.md) · <img src="https://flagcdn.com/w20/ae.png" alt="العربية" style="height:14px;"> [العربية](../ar/README.md)

---

**OMEGA-SERV** là một máy chủ HTTP/1.1 viết bằng Python thuần (chỉ dùng thư viện chuẩn cho lõi máy chủ), được thiết kế để phục vụ nội dung tĩnh và, tùy chọn, PHP-FPM, với cơ chế gia cố giao thức không thể tắt và các mô-đun bảo mật (WAF, TLS, xác thực) có thể xếp chồng thay vì bị áp đặt. Là công cụ thứ bảy của bộ `omega-` nhưng cố ý **nằm ngoài đợt tích hợp `omega-suite` sắp tới** (nó tác động lên chính máy cục bộ đang chạy nó, không phải lên mục tiêu từ xa — cùng họ với `omega-fire`); được tổ chức theo Clean Architecture, với `bootstrap/` đóng vai trò gốc lắp ghép (composition root).

## 1. Tầm nhìn và phạm vi

Ưu tiên được nêu rõ là **sự vững chắc/an toàn của lõi HTTP trước hết** — WAF và TLS là các mô-đun tùy chọn đặt lên trên, không bao giờ là điều kiện tiên quyết. Một máy chủ chỉ làm một việc (phục vụ tệp, có thể cả PHP) nhưng làm đúng, với cơ chế gia cố giao thức thực sự không thể vượt qua, thay vì một máy chủ làm nhiều việc nửa vời.

### Những gì OMEGA-SERV làm

- Phục vụ nội dung tĩnh (tệp, liệt kê thư mục tùy chọn, alias, chuyển hướng, rewrite, cache) với cơ chế phân giải đường dẫn an toàn (traversal, mã hóa kép, liên kết tượng trưng). Tệp lớn được gửi theo từng khối từ đĩa, không bao giờ nạp vào bộ nhớ; mỗi tệp mang một `ETag` và một `Last-Modified` (tải lại = phản hồi 304 rỗng), chấp nhận yêu cầu một phần `Range` (tải tiếp, video); ảnh, media, phông chữ, CSS và JS nhận một `Cache-Control` mặc định, có thể sửa trong màn hình Cache. Tệp văn bản nén sẵn: nếu `site.css.br` hoặc `site.css.gz` tồn tại cạnh `site.css` (tạo bằng `brotli -k site.css` hoặc `gzip -k site.css`) và trình duyệt chấp nhận, chúng được gửi thay thế, không bao giờ là một phiên bản cũ hơn bản gốc.
- Gia cố giao thức HTTP mặc định, không có tùy chọn để tắt: danh sách phương thức được phép tường minh, kiểm tra tiêu đề `Host`, từ chối sự mơ hồ `Content-Length`/`Transfer-Encoding`, tiêu đề bảo mật và CSP cơ bản không thể vượt qua.
- Tùy chọn: lọc WAF (chữ ký, giới hạn tốc độ, danh sách chặn), TLS trực tiếp (chứng chỉ tự ký, do CA cục bộ ký, hoặc công khai qua Let's Encrypt/Certbot với gia hạn tự động — xem §9), xác thực HTTP Basic theo vùng, PHP qua FastCGI/PHP-FPM, vùng tải lên được cô lập.
- Chế độ « boost »: nhiều tiến trình máy chủ, tối đa một tiến trình cho mỗi CPU khả dụng của máy (màn hình Khả năng chịu tải và giới hạn); các bộ đếm bảo mật (rate limit, tái phạm) được chia sẻ giữa chúng và luôn chính xác.
- Tự kiểm tra cấu hình của chính mình (`audit security`) và tự cài đặt như dịch vụ hệ thống (systemd/OpenRC/runit).
- CLI không tương tác có thể viết script từ đầu đến cuối, **và giao diện tương tác (Textual)** bao bọc đúng các trường hợp sử dụng đó — xem §3. Lộ trình giao diện (`OMEGA-SERV_PLAN-DETAILLE_INTERFACE.md`, §12) **đã hoàn tất toàn bộ**: sổ đăng ký khả năng, hồ sơ/tùy chọn, cấu hình chi tiết (alias/chuyển hướng/rewrite/FastCGI/dirlisting/xác thực/cache/WAF/proxy tin cậy/reverse proxy đi ra/TLS), quản lý log (Thư viện/Yêu thích, 3 trình xem — đơn giản/cổ điển/lnav hợp nhất —, Xem và xử lý IP, nguồn từ xa SSH, xoay vòng/sao lưu/tự động hóa/khôi phục/dọn dẹp/xuất), dịch vụ hệ thống, đa instance (sổ đăng ký, tạo mới), kiểm tra/mô phỏng/kiểm toán, sao lưu/khôi phục cấu hình, trình hướng dẫn lần đầu chạy, thiết lập ứng dụng (giao diện, hồ sơ hiển thị, đường dẫn xuất/ảnh chụp), hướng dẫn trợ giúp theo ngữ cảnh (phiếu cho từng màn hình với ví dụ cụ thể, FAQ, xuất HTML, độ bao phủ đầy đủ được kiểm chứng bằng test), luôn chỉ rõ cần nạp lại hay khởi động lại sau mỗi lần lưu, cấu hình Active Defense đầy đủ mà không cần sửa tệp thủ công.

### Những gì OMEGA-SERV không làm

- CGI thô (đã loại khỏi phạm vi V1 — chỉ hỗ trợ FastCGI/PHP-FPM).
- Xác thực TLS hai chiều (mTLS), OCSP stapling — ngoài phạm vi V1, xem §15. (ACME/Let's Encrypt qua Certbot đã có sẵn, xem §9c/9d.)
- Cache HTTP dùng chung giữa các tiến trình.
- Quét/kiểm toán một mục tiêu từ xa (dùng `omega-check`/`omega-scan`/`omega-deep` cho việc đó — Omega-serv tự kiểm toán chính nó, không bao giờ kiểm toán bên thứ ba).

### OMEGA-SERV so với các máy chủ web trên thị trường

Xem [Đo đạc & so sánh](comparatif-serveurs-web.md)  
So sánh có đo đạc giữa: [Nginx](https://nginx.org/) · [Lighttpd](https://www.lighttpd.net/) · [Caddy](https://caddyserver.com/) · [Apache](https://www.apache.org) · [Traefik](https://traefik.io/) · [Omega-Serv](https://kraynux.snake-mackarel.ts.net/omega-serv/translation/vi/)

### Cảnh báo sử dụng

Omega-serv **từ chối khởi động với quyền root**. Không mô-đun bảo mật nào (WAF, TLS, xác thực) được bật mặc định trong bất kỳ hồ sơ nào được cung cấp, kể cả `hardened` — bật chúng luôn là một thao tác tường minh (`config enable-tls`, `option enable waf`...). Chính hồ sơ `hardened` cũng khuyến nghị dùng reverse proxy khi thực sự mở ra Internet thay vì thay thế nó.

## 2. Cài đặt

### Yêu cầu

- Python 3.10+
- `openssl` (tệp thực thi, không phải thư viện Python) cho mọi thứ liên quan đến chứng chỉ TLS — các chức năng khác hoạt động không cần nó.

### Tải xuống

Bản lưu trữ của phiên bản mới nhất và dấu SHA-256 của từng phiên bản: [omega-serv-2.0.1.tar.gz](https://kraynux.snake-mackarel.ts.net/omega-serv/download/omega-serv-2.0.1.tar.gz) · [sha.txt](https://kraynux.snake-mackarel.ts.net/omega-serv/download/sha.txt)

```bash
wget https://kraynux.snake-mackarel.ts.net/omega-serv/download/omega-serv-2.0.1.tar.gz
wget https://kraynux.snake-mackarel.ts.net/omega-serv/download/sha.txt
sha256sum -c --ignore-missing sha.txt
```

### Cài đặt

> ⚠️ **Bạn đang cập nhật một bản cài đặt có sẵn?** Lệnh bên dưới **lặng lẽ bỏ qua bước giải nén** nếu `omega-serv/` đã tồn tại (nó cho rằng đó là một lần cài đặt đầu tiên bị gián đoạn, không phải một bản cập nhật) — khi đó bạn sẽ cài lại các phụ thuộc trên **mã cũ không thay đổi**, mà không có bất kỳ thông báo lỗi nào. Hãy dùng mục [Cập nhật](#cập-nhật) bên dưới thay thế.

```bash
[ -d omega-serv ] && echo "ℹ️ Đã giải nén ở đây, bỏ qua bước này." || tar -xzf omega-serv-2.0.1.tar.gz
cd omega-serv/
chmod +x install.sh
./install.sh
```

`install.sh`:

1. Tạo môi trường ảo `.venv` nếu chưa có.
2. Cài đặt gói (`pip install -e .`) — **không có phụ thuộc bên ngoài** (xem §6).
3. Cấp quyền thực thi cho `omega-serv.sh` và `install.sh`.
4. Thêm alias `serv` vào `~/.bashrc` và `~/.zshrc` (không trùng lặp nếu đã có).

### Cập nhật

Nếu `omega-serv/` đã tồn tại (bản cài đặt trước), **đừng bao giờ chạy `tar` từ bên trong thư mục này**: nó sẽ cố tạo một `omega-serv/omega-serv/` lồng nhau và thất bại. Khác với omega-fire, `install.sh` không bao giờ đụng đến quyền của thư mục (không bước nào yêu cầu `sudo`) — vì vậy ở đây không có nguy cơ thư mục thuộc sở hữu của `root`, việc giải nén trực tiếp đè lên bản cài đặt hiện có là an toàn.

```bash
# Từ thư mục CHA của omega-serv/ (không bao giờ từ bên trong)
tar -xzf omega-serv-2.0.1.tar.gz
cd omega-serv/
./install.sh
```

Bản lưu trữ cố ý loại trừ toàn bộ trạng thái đang hoạt động (`var/db/`, `var/log/`, `var/backups/`, `secure/secrets/`, `secure/certificates/*.key`, `config/omega-serve.json`, **`webroot/` — trang web thực sự được phục vụ**...) — giải nén đè lên không bao giờ đụng đến dữ liệu, chứng chỉ, thiết lập hay nội dung đang phục vụ, chỉ mã ứng dụng được thay thế. `install.sh` tái sử dụng `.venv` hiện có và chỉ cài lại các phụ thuộc đè lên.

Kể từ 2026-10-18, `var/` và `secure/auth/` hoàn toàn không còn nằm trong bản lưu trữ, kể cả khi rỗng: vì vậy giải nén đè lên không còn đặt lại quyền của chúng (chia sẻ với tài khoản của dịch vụ systemd) — không cần « Dịch vụ → Áp dụng lại quyền » sau khi cập nhật nữa. `install.sh` tạo các thư mục này nếu thiếu, không bao giờ đụng đến những thư mục đã tồn tại.

> ⚠️ **Nếu một dịch vụ đang chạy, bước trên là chưa đủ.** Nó thay mã trên đĩa, nhưng tiến trình đang chạy vẫn tiếp tục chạy với mã cũ đã nạp trong bộ nhớ — sau đó luôn cần **khởi động lại hoàn toàn**:
> ```bash
> sudo systemctl restart <tên-dịch-vụ>
> ```
> **Không bao giờ chỉ nạp lại** (`systemctl reload`, hoặc màn hình SERVICE → *Nạp lại*): thao tác này chỉ đọc lại một số tùy chọn cấu hình (quy tắc WAF, vùng xác thực...), **không bao giờ đọc lại chính mã Python**. Một `systemctl status <tên-dịch-vụ>` hiển thị thời điểm khởi động cũ hơn bản cập nhật của bạn xác nhận rằng nó vẫn chạy mã cũ. Nếu bạn luôn cập nhật bằng cách ghi đè cùng một thư mục (trường hợp chuẩn ở trên), lần khởi động lại này là bước duy nhất còn thiếu — không cần cài lại dịch vụ.

> ⚠️ **Nếu dịch vụ khởi động lại liên tục sau đó** (`systemctl status` luân phiên active/inactive, `journalctl -u <tên-dịch-vụ>` cho thấy một `PermissionError` khi ghi một tệp trong `var/`): việc giải nén bằng `tar` khôi phục quyền của các thư mục như được ghi lại trong bản lưu trữ, điều này có thể xóa mất phần chia sẻ quyền đã đặt cho tài khoản hệ thống riêng lúc cài đặt ban đầu — dù chính `install.sh` không bao giờ đụng đến. Không cần cài lại unit: màn hình SERVICE → **Khôi phục quyền** (áp dụng lại phần chia sẻ trên `var/` và `secure/auth/`, không đụng đến unit systemd).

### Phụ thuộc

Lõi máy chủ (bộ phân tích HTTP/1.1, client FastCGI, băm mật khẩu bằng `hashlib.scrypt`) vẫn là Python thuần/stdlib, và mọi thứ liên quan đến chứng chỉ TLS đi qua tệp thực thi `openssl` dưới dạng tiến trình con thay vì một thư viện mã hóa Python — **không có phụ thuộc bên ngoài cho phần này**. Chỉ giao diện tương tác (§3) mới thêm phụ thuộc: `omega-lib` (giao diện, phát hiện terminal — thư viện dùng chung của bộ công cụ, không phát hành trên PyPI, được đóng gói sẵn trong bản lưu trữ phân phối), `textual` và `pyte` (giả lập terminal để hiển thị `lnav` hợp nhất trong giao diện), `jinja2` (bản xuất HTML theo giao diện) và `psutil` (màn hình Trạng thái & Tài nguyên — CPU/RAM/đĩa/mạng). Phụ thuộc phát triển/kiểm thử tùy chọn (`pip install -e ".[test]"`): `hypothesis` (kiểm thử thuộc tính cho bộ phân tích HTTP và bộ phân giải đường dẫn, không bao giờ dùng trong production). Công cụ chất lượng (`pip install -e ".[dev]"`): `pytest`, `ruff`, `mypy`, `import-linter`. Phần bổ sung tùy chọn khác (`pip install -e ".[magnet]"`): `lupa` (liên kết Lua nhúng, wheel biên dịch sẵn, không cần trình thông dịch `lua` của hệ thống), chỉ dành cho script WAF bổ trợ « magnet » (§7) — không bao giờ được cài mặc định; việc thiếu nó được báo hiệu (khả năng `waf-magnet`, màn hình **Khả năng**) kèm lệnh cài đặt chính xác, mà không chặn phần còn lại của máy chủ.

### Công cụ tùy chọn được khuyến nghị

Giao diện hoạt động ở chế độ suy giảm nếu thiếu các công cụ này:

- `openssl` — cần cho mọi thứ liên quan đến chứng chỉ TLS (tự ký, CA cục bộ, nhập); không có nó, các lệnh `certs *` thất bại nhưng phần còn lại của máy chủ vẫn hoạt động bình thường (xem §9).
- `certbot` — chỉ cần cho trình hướng dẫn **Let's Encrypt** và việc gia hạn tự động của nó (§9c/9d); TLS tự ký/CA cục bộ không yêu cầu.
- `lnav` — phân tích log nâng cao được hợp nhất trong màn hình **Quản lý log** (§3); thông báo lỗi rõ ràng nếu không tìm thấy tệp thực thi, không có sự cố, phần còn lại của màn hình (xem/theo dõi/xoay vòng/thống kê) vẫn hoạt động bình thường không cần nó.
- `scp` (gói `openssh`/`openssh-clients`, hầu như luôn có sẵn) — chỉ cần cho **Nguồn từ xa (SSH)** (§13a); không có nó, việc tải về thất bại với thông báo rõ ràng, phần còn lại của Thư viện vẫn hoạt động bình thường.
- `python-psutil` (gói hệ thống tương đương `psutil` trên PyPI) — luôn được `pip install -e .` cài tự động (phụ thuộc bắt buộc của gói, màn hình **Trạng thái & Tài nguyên** luôn cần đến), nhưng cài sẵn qua trình quản lý gói hệ thống giúp `pip` không phải tự biên dịch wheel.

```bash
# Arch Linux và các bản phái sinh
sudo pacman -S openssl certbot lnav python-psutil openssh

# Debian/Ubuntu và các bản phái sinh
sudo apt install openssl certbot lnav python3-psutil openssh-client

# Fedora
sudo dnf install openssl certbot lnav python3-psutil openssh-clients
```

## 3. Sử dụng

Hai giao diện tương đương hoàn toàn về chức năng, không bao giờ trùng lặp logic giữa hai bên: CLI không tương tác (có thể viết script, dùng ở bên dưới) và giao diện tương tác Textual (menu, biểu mẫu, bảng) — mọi hành động của bên này đều có ở phía CLI, giao diện chỉ bao bọc cùng các trường hợp sử dụng.

### Chế độ tương tác (TUI)

Khuyến nghị cho việc dùng hằng ngày — chạy không kèm tham số:

```bash
./omega-serv.sh
```
nếu bạn đã tạo alias, chỉ cần gõ `serv` trong terminal:
```bash
serv
```

### Ngôn ngữ giao diện

17 ngôn ngữ: tiếng Pháp, tiếng Anh, tiếng Tây Ban Nha, tiếng Bồ Đào Nha (Brazil), tiếng Ý, tiếng Đức, tiếng Hà Lan, tiếng Ba Lan, tiếng Nga, tiếng Trung, tiếng Việt, tiếng Thái, tiếng Indonesia, tiếng Nhật, tiếng Hàn, tiếng Hindi, tiếng Ả Rập. Chọn trong Thiết lập (phím `o`, « Langue / Language », nhãn này không bao giờ được dịch), hoặc tạm thời bằng `OMEGA_SERV_LANG=en serv`. Trong console văn bản Linux (TTY), các ngôn ngữ có chữ viết không tồn tại trong phông console (tiếng Việt, tiếng Trung, tiếng Thái, tiếng Nhật, tiếng Hàn, tiếng Hindi, tiếng Ả Rập) được hiển thị bằng tiếng Anh trong phiên đó. Với tiếng Hindi, các terminal tự ghép các chữ cái nối (Kitty, Ghostty, Konsole) làm lệch khung và cột, mức độ tùy theo phông chữ: một cảnh báo hiển thị khi khởi động; Terminator, GNOME Terminal, Xfce Terminal và Alacritty hiển thị tiếng Hindi thẳng hàng. Hai thiết lập riêng: **ngôn ngữ trang cho khách truy cập** (trang lỗi, danh sách thư mục — màn hình Trang lỗi, mặc định tiếng Pháp) và **ngôn ngữ bản xuất** (HTML và báo cáo sự cố — Thiết lập, mặc định « Giống giao diện »). Log của máy chủ (`journalctl`) vẫn bằng tiếng Pháp.

### Luồng tổng quát

Màn hình khởi động (splash, đóng khi nhấn phím hoặc nhấp chuột) → menu chính (Trình hướng dẫn lần đầu chạy / Sổ đăng ký khả năng / Hồ sơ / Cấu hình chi tiết / Bảo mật chủ động / Quản lý log / Dịch vụ / Đa instance / Trạng thái & Tài nguyên / Kiểm toán / Sao lưu) → chọn một mục rồi một hành động, mỗi biểu mẫu kiểm tra các trường bắt buộc trước khi tiếp tục → xác nhận tường minh trước mọi thao tác nhạy cảm hoặc phá hủy (khởi động lại, xóa, khôi phục...) → luôn chỉ rõ bước tiếp theo (nạp lại nóng tự động, hoặc xác nhận khởi động lại hoàn toàn) sau mỗi lần lưu làm thay đổi cấu hình đang được phục vụ. Việc thích ứng với terminal (màu sắc, kích thước, suy giảm cấu trúc của hồ sơ hiển thị) là tự động, không cần cờ thủ công — xem §4.

#### Phím tắt (giao diện tương tác)

| Phím | Hành động |
|---|---|
| `↑` / `↓` | Di chuyển giữa các phần tử của màn hình |
| `Tab` / `Shift+Tab` | Di chuyển giữa các trường của biểu mẫu |
| `Esc` | Quay lại màn hình trước (xác nhận thoát ở trang chủ) |
| `t` | Giao diện kế tiếp (áp dụng ngay, không cần xác nhận) |
| `r` | Làm mới việc phát hiện terminal |
| `F1` | Trợ giúp của màn hình hiện tại (phiếu theo ngữ cảnh — xem "Hướng dẫn trợ giúp" bên dưới) |
| `a` | Hướng dẫn trợ giúp đầy đủ (menu có thể duyệt + FAQ) |
| `o` | Thiết lập ứng dụng (giao diện, hồ sơ hiển thị, đường dẫn xuất/ảnh chụp — xem bên dưới) |
| `q` | Thoát (có xác nhận) |
| `Ctrl+P` | Bảng lệnh (Giao diện, Chụp màn hình, Tùy chọn...) |

> **Ngoại lệ — trình soạn danh sách (WAF → Custom)**: không có phím tắt nào, mọi thao tác bằng chuột; bàn phím chỉ dùng để nhập (ký tự, Enter, phím mũi tên, Home/End, Page Up/Down, Backspace, Delete). `Esc`, `F1` và `Ctrl+P` không hoạt động ở đó (nút **Trợ giúp**); chỉ `Ctrl+Q` còn hoạt động, kèm xác nhận nếu có thay đổi chưa lưu.

#### Hướng dẫn trợ giúp (phím `F1`/`a`)

Hệ thống trợ giúp tích hợp, không bao giờ chỉ là văn bản tĩnh đơn thuần: mỗi màn hình được tài liệu hóa (phiếu định nghĩa/các trường cần điền với ví dụ cụ thể/hành động được kích hoạt/phản ứng — nạp lại, khởi động lại hoặc không) có thể truy cập trực tiếp từ chính nó qua `F1`; phím `a` mở menu đầy đủ (cây cấu trúc giống hệt điều hướng thực của ứng dụng) với lối vào FAQ (những cạm bẫy gặp phải khi sử dụng thực tế, ví dụ các lớp tấn công của Active Defense, quyền của dịch vụ dùng chung) và một bản xuất HTML độc lập (giữ nguyên giao diện đang dùng) của toàn bộ hướng dẫn. Có màn hình tham chiếu chung dự phòng khi chưa có phiếu cụ thể — độ bao phủ hiện tại là đầy đủ, được kiểm chứng bằng test.

#### Menu chính (giao diện tương tác)

- **Trình hướng dẫn lần đầu chạy** — lộ trình có hướng dẫn gồm 8 bước (chào mừng → khả năng ở chế độ chỉ đọc → chọn hồ sơ → bind/cổng → TLS tùy chọn → kiểm tra → tóm tắt + ghi → đề xuất cài đặt dịch vụ); cho phép tạo một cấu hình hoàn chỉnh và khởi chạy máy chủ mà không cần biết CLI.
- **Sổ đăng ký khả năng** — thăm dò hệ thống ở chế độ chỉ đọc (hệ thống init, cổng cấu hình đã bị chiếm hay chưa, có `openssl`/`logrotate`/`tailscale`/`lnav` hay không, dung lượng đĩa, giới hạn file descriptor...), xuất JSON/HTML.
- **Hồ sơ** — cùng trường hợp sử dụng với `profile` trong CLI (§5), luôn hiển thị diff trước khi ghi.
- **Cấu hình chi tiết của máy chủ** — CRUD đầy đủ cho alias/chuyển hướng/rewrite/dirlisting/proxy tin cậy/reverse proxy đi ra/FastCGI/cache/xác thực/kiểm soát truy cập/trang lỗi, cùng menu con **TLS** (trạng thái, tạo chứng chỉ tự ký, trình hướng dẫn CA cục bộ, trình hướng dẫn Let's Encrypt/Certbot, gia hạn tự động, thu hồi, bật/tắt — xem §9); khung thứ hai **TÙY CHỌN VÀ KIỂM TRA** gom các lối tắt tới **Tùy chọn** (`option` trong CLI, §7) và **Kiểm tra cấu hình** (`config check` trong CLI, §10) — cùng lộ trình chỉnh thiết lập rồi kiểm tra, hai màn hình này không còn truy cập trực tiếp từ menu chính. WAF không còn nằm ở đây (xem "Bảo mật chủ động" bên dưới): nó chủ yếu hiển thị trạng thái vận hành thay đổi liên tục, không phải một biểu mẫu cấu hình tĩnh đơn giản. Mỗi lần lưu luôn chỉ rõ bước tiếp theo: nạp lại nóng tự động và lặng lẽ nếu dịch vụ đang chạy (dirlisting, truy cập, alias/chuyển hướng/rewrite, cache, trang lỗi, proxy tin cậy, vùng reverse proxy/FastCGI, người dùng/vùng xác thực), hoặc xác nhận tường minh việc khởi động lại hoàn toàn khi thay đổi liên quan đến socket lắng nghe, TLS hoặc Active Defense — không màn hình nào còn để bạn phải đoán có cần khởi động lại máy chủ hay không.
- **Bảo mật chủ động** — một màn hình duy nhất gom hai khối đặt cạnh nhau: **Active Defense** (Trạng thái, Mối đe dọa được theo dõi với điểm/mức, Sự cố với dòng thời gian/xuất IoC/báo cáo, phân bổ Deception, Mô phỏng một quyết định ở chế độ dry-run, **Thiết lập** — cấu hình đầy đủ mà không bao giờ phải sửa tay `config/omega-serve.json`, xem §11) và **WAF** (Trạng thái, Mô-đun — chế độ/gói quy tắc/danh sách chặn, Thử một yêu cầu, Custom — tạo quy tắc tùy chỉnh và nạp các danh sách đường dẫn/từ khóa có thể sửa bằng chuột (xem §11b), Magnet — nhập một script `mod_magnet` bên ngoài có kiểm tra tương thích trước khi kích hoạt) — xem §11.
- **Quản lý log** — menu hai cột. Cột **Thư viện**: trung tâm tham chiếu mọi log cần xử lý (thêm thủ công, một cú nhấp thêm ngay các log riêng của instance — access/error/WAF gốc, + script magnet §7 nếu đang bật —, hoặc một **nguồn từ xa** được tải về qua SSH, xem bên dưới); **Yêu thích** (tổ hợp log + trình xem được lưu dưới một tên, mở trực tiếp); **Xem log** với 3 trình xem tùy chọn theo số log được chọn — Đơn giản (tail trực tiếp + thống kê chung IP/lỗi/mã HTTP trên mọi định dạng), Cổ điển (đọc + theo dõi), `lnav` hợp nhất (hiển thị terminal thực trong giao diện, log magnet được đưa vào sẵn + các đường dẫn thủ công **được ghim** để giữ lại giữa các phiên); **Xem và xử lý IP** (top IP trên một hoặc nhiều log tùy chọn, khoảng thời gian 24h/7 ngày/30 ngày/tất cả, gỡ một IP). Cột **Bảo trì** (không đổi): xoay vòng/lưu trữ thủ công hoặc tự động theo ngưỡng kích thước, tạo bản sao lưu ngay, cấu hình/quản lý các tác vụ tự động lên lịch (dạng khai báo — xem ghi chú bên dưới), khôi phục/dọn dẹp một bản lưu trữ, xuất danh sách.
- **Dịch vụ** — cùng các hành động với `service` trong CLI (§12), nâng quyền `sudo` từng lần cho mỗi hành động, không bao giờ chạy toàn bộ ứng dụng bằng root.
- **Đa instance** — sổ đăng ký toàn cục (`~/.config/omega-serv/instances.json`, nằm ngoài mọi thư mục dự án) các bản cài đặt đã biết trên máy, kèm trạng thái systemd của từng bản; tạo instance mới (sao chép cây thư mục, môi trường ảo và phụ thuộc riêng, cấu hình mới với cổng khác, kiểm tra không lồng nhau và không xung đột cổng) ngay từ giao diện. Nút về cơ bản không hiển thị khi chỉ có một bản cài đặt (nhãn "Đa instance" trở thành "Instances (N)" khi biết từ 2 bản trở lên); chuyển hẳn sang một instance khác (`os.execv`, xác nhận tường minh, splash riêng thông báo việc chuyển khi khởi động lại); gỡ cài đặt hoàn toàn một instance (gỡ unit, gỡ tài khoản hệ thống riêng nếu không còn instance nào khác dùng, và tùy chọn xóa thư mục, không bao giờ mặc định).
- **Trạng thái & Tài nguyên** — tổng quan trong nháy mắt, làm mới mỗi 2 giây: trạng thái máy chủ (tiến trình/PID, trạng thái dịch vụ hệ thống, hồ sơ/tùy chọn đang bật/TLS/cổng), luồng log truy cập trực tiếp (lưu lượng, phân bố theo mã trạng thái, IP duy nhất, tỷ lệ lỗi), tài nguyên hệ thống (CPU/RAM/đĩa/swap/tải/mạng, qua `psutil`); cũng gom lối tắt **Mô phỏng yêu cầu** (cùng trường hợp sử dụng với lệnh CLI tương ứng, §10).
- **Kiểm tra bảo mật** — cùng trường hợp sử dụng với lệnh CLI tương ứng (§10).
- **Sao lưu cấu hình** — bản lưu trữ tar.gz của tệp cấu hình và, khi được chọn tường minh, các quy tắc WAF/vùng xác thực/chứng chỉ (bắt buộc xác nhận khi có bí mật thật được đưa vào)/cơ sở dữ liệu Active Defense, khôi phục, liệt kê, xóa.

> Ghi chú về các tác vụ xoay vòng tự động lên lịch: chúng được lưu lại (tần suất + log đích) nhưng **không có gì tự động thực thi chúng** — cả ở phía giao diện lẫn dưới dạng tác vụ nền. Đây là lựa chọn có chủ ý để đồng nhất với màn hình tương đương của `omega-fire`, vốn có cùng hành vi khai báo. Việc thực thi định kỳ thật sự (bộ hẹn giờ systemd, tác vụ nền) sẽ được xây dựng riêng nếu nhu cầu được xác nhận.

#### Thiết lập ứng dụng (phím `o` hoặc bảng lệnh)

Chỉ là tùy chọn giao diện — không bao giờ nhầm với `config/omega-serve.json` (cấu hình máy chủ): giao diện đang dùng, hồ sơ hiển thị (`complete`/`standard`/`reduced`/`mono`, cần khởi động lại), đường dẫn bản xuất (mặc định `var/exports/`), đường dẫn ảnh chụp màn hình (mặc định `var/screenshots/`), dọn dẹp một trong hai thư mục (bắt buộc xác nhận).

```bash
# Chạy máy chủ (tiền cảnh, SIGTERM = dừng sạch với thời gian ân hạn, SIGHUP = nạp lại nóng WAF/Auth)
./omega-serv.sh serve

# Cấu hình
./omega-serv.sh config init                # tạo config/omega-serve.json (giá trị an toàn mặc định)
./omega-serv.sh config check                # kiểm tra mà không khởi động (cùng các cổng chặn như khi khởi động)
./omega-serv.sh config show
./omega-serv.sh config enable-tls --cert ... --key ... --mode direct
./omega-serv.sh config disable-tls

# Hồ sơ (minimal / standard / hardened / development)
./omega-serv.sh profile list
./omega-serv.sh profile show hardened
./omega-serv.sh profile apply hardened --dry-run   # luôn xem diff trước khi áp dụng

# Tùy chọn (aliases, redirects, rewrites, dirlisting, cache, waf, upload, fastcgi, reverse_proxy...)
./omega-serv.sh option list
./omega-serv.sh option enable waf
./omega-serv.sh option disable waf

# Mô phỏng một yêu cầu mà không chạy máy chủ (hữu ích để kiểm tra một quy tắc trước khi kích hoạt)
./omega-serv.sh simulate-request GET /index.html

# WAF (hoạt động cả khi tùy chọn bị tắt, qua --force ngầm định)
./omega-serv.sh waf test --method GET --path /admin --remote-ip 203.0.113.1
./omega-serv.sh blocklist list
./omega-serv.sh blocklist add --network 203.0.113.0/24 --reason "scan detecte" --duration-seconds 3600
./omega-serv.sh blocklist remove --network 203.0.113.0/24

# Active Defense (deception + chế độ chiến tranh, tùy chọn "active_defense" - xem §11)
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

# Chứng chỉ TLS - tự ký (9a)
./omega-serv.sh certs generate-self-signed --cn localhost --san-dns localhost --san-ip 127.0.0.1
./omega-serv.sh certs show
./omega-serv.sh certs check-expiry --warn-days 30

# Chứng chỉ TLS - CA cục bộ (9b)
./omega-serv.sh certs generate-ca --cn "Mon CA locale" --days 3650
./omega-serv.sh certs generate-csr --cn serveur.local --san-dns serveur.local --key-out server.key --csr-out server.csr
./omega-serv.sh certs sign-csr --csr server.csr --ca-key secure/certificates/ca/root-ca.key --ca-cert secure/certificates/ca/root-ca.pem --out server.pem --fullchain-out fullchain.pem
./omega-serv.sh certs revoke --cert server.pem --ca-key secure/certificates/ca/root-ca.key --ca-cert secure/certificates/ca/root-ca.pem

# Chứng chỉ TLS - nhập (9c, ví dụ từ một hook Certbot)
./omega-serv.sh certs import --key privkey.pem --cert fullchain.pem

# Xác thực HTTP Basic
./omega-serv.sh auth add-user --username alice
./omega-serv.sh auth create-zone --url-prefix /admin/ --allowed-users alice
./omega-serv.sh auth list

# Kiểm tra bảo mật (không bao giờ chặn, chỉ mang tính thông tin)
./omega-serv.sh audit security --format text --min-severity medium

# Sao lưu cấu hình (cấu hình luôn được đưa vào; bí mật thật
# không bao giờ được mã hóa mặc định, bắt buộc --confirm-secrets để đưa chúng vào)
./omega-serv.sh config backup --description "avant migration"
./omega-serv.sh config backup --include-auth --include-certificates --confirm-secrets
./omega-serv.sh config backup --include-active-defense --description "menaces/incidents"
./omega-serv.sh config list-backups
./omega-serv.sh config restore --snapshot-id snapshot_20260908_170003_762484

# Dịch vụ hệ thống (systemd/OpenRC/runit, tự động phát hiện)
./omega-serv.sh service install --user omega-serv --group omega-serv
./omega-serv.sh service start
./omega-serv.sh service status
```

### Mã thoát đáng chú ý

| Lệnh | Mã | Ý nghĩa |
|---|---:|---|
| `audit security` | `0` | Không có gì nghiêm trọng (không có `CRITICAL`/`HIGH`) |
| `audit security` | `1` | Ít nhất một phát hiện `CRITICAL` |
| `audit security` | `2` | Ít nhất một `HIGH` và không có `CRITICAL` |
| `audit security` | `3` | Lỗi thực thi (không tìm thấy cấu hình...) |
| `certs check-expiry` | `1` | Chứng chỉ đã hết hạn |
| mọi lệnh khác | `0`/`1` | Thành công / kiểm tra thất bại |

## 4. Tương thích terminal

Giao diện tương tác ([Textual](https://textual.textualize.io/) xây dựng trên [Rich](https://rich.readthedocs.io/)) tự động phát hiện khả năng của terminal (trình giả lập, kích thước) và điều chỉnh bảng kiểu cấu trúc tương ứng (`complete`/`standard`/`reduced`/`mono`), không cần cờ thủ công. Chế độ CLI luôn là văn bản thuần, độc lập với terminal. Chính sách dùng chung cho toàn bộ bộ `omega-` (`omega-lib`, `terminal/policies.py`) — giống với chính sách của `omega-check`/`omega-fire`.

### Hồ sơ theo trình giả lập được phát hiện

| Trình giả lập | Hồ sơ ban đầu |
|---|---|
| Ghostty, Alacritty, WezTerm, Kitty | `complete` |
| Konsole, GNOME Terminal, Terminator, Xfce4 Terminal | `standard` |
| xterm, urxvt, SSH hiện đại | `reduced` |
| TTY Linux, SSH cũ | `mono` |
| Trình giả lập không nhận diện được | `reduced` (dự phòng mặc định) |

### Hồ sơ theo kích thước terminal

| Kích thước tối thiểu (cột × dòng) | Mức trần của hồ sơ |
|---|---|
| 120 × 32 | `complete` |
| 100 × 28 | `standard` |
| 80 × 24 | `reduced` |
| nhỏ hơn | `mono` |

Hồ sơ cuối cùng được chọn là **hồ sơ hạn chế hơn trong hai** (trình giả lập và kích thước) — một Ghostty toàn màn hình bị thu nhỏ còn 70 cột sẽ hạ xuống `mono`, dù trình giả lập của nó cho phép `complete`. Có thể làm mới trực tiếp bằng phím `r`, hoặc ghi đè thủ công trong Thiết lập ứng dụng (phím `o`, §3).

## 5. Hồ sơ

| Hồ sơ | Mục đích sử dụng |
|---|---|
| `minimal` | Trình diễn/cục bộ đơn giản: chỉ nội dung tĩnh, không bật tùy chọn nào |
| `standard` | Trang tĩnh hoặc production nhỏ: các tiêu đề thông dụng, CSP cơ bản, tắt dirlisting/CGI/FastCGI |
| `hardened` | Mở ra ngoài với đặc quyền tối thiểu: bind cục bộ mặc định (khuyến nghị reverse proxy cho Internet), chỉ phương thức GET/HEAD, CSP nghiêm ngặt, chống slowloris — WAF **không bao giờ** được bật tự động, kể cả ở đây |
| `development` | Chỉ để phát triển cục bộ, không bao giờ được giới thiệu là phù hợp cho Internet: bắt buộc bind loopback, CSP ở chế độ report-only, trang lỗi chi tiết |

Thứ tự hợp nhất cấu hình: giá trị an toàn tích hợp → hồ sơ được chọn → các tùy chọn đang bật được giữ lại (tồn tại qua việc đổi hồ sơ) → lớp phủ tường minh của người dùng. Một diff đầy đủ luôn được hiển thị trước khi ghi (`profile apply`).

## 6. Kiến trúc

Clean Architecture (`core / domain / ports / application / infrastructure / interfaces / bootstrap`) — `bootstrap/` là gốc lắp ghép (tương đương `app/` của các công cụ khác trong bộ). Đặc điểm được chấp nhận của dự án này, được kiểm chứng bằng `import-linter` chứ không chỉ giả định: `application/server/start_server.py` (và `validate_config.py`, `run_audit.py`) đóng vai trò **nhà máy lắp ráp phụ thuộc vào cấu hình thực** (trình quản lý dịch vụ nào, có bật WAF hay không...) và khởi tạo trực tiếp các adapter `infrastructure/` cụ thể — khác với khuôn mẫu chặt chẽ hơn của CHECK/TRACK, nơi `application/` chỉ dùng các `ports/`. Quy tắc phổ quát duy nhất thực sự được áp đặt: `domain/`/`core/` không bao giờ phụ thuộc vào các lớp bên ngoài.

```text
src/omega_serv/
├── core/            Từ vựng xuyên suốt (platform_info, hằng số)
├── domain/           Logic nghiệp vụ thuần (HTTP, cấu hình, bảo mật WAF/TLS/auth/audit, định tuyến)
├── ports/            Hợp đồng (Protocol) mà tầng ứng dụng cần
├── application/      Trường hợp sử dụng - một số hàm (build_server...) cũng lắp ráp adapter cụ thể (xem ở trên)
├── infrastructure/    Triển khai thực (asyncio, openssl qua subprocess, systemd/OpenRC/runit, tệp)
├── interfaces/cli/    CLI argparse không tương tác
├── interfaces/tui/    Giao diện tương tác Textual (cùng trường hợp sử dụng, không bao giờ trùng lặp logic)
└── bootstrap/         DependencyContainer, phân giải thư mục gốc của dự án
```

Các quy tắc được `import-linter` kiểm chứng (8 hợp đồng): `domain`/`core` không bao giờ phụ thuộc vào các lớp bên ngoài; `interfaces.tui` không bao giờ phụ thuộc trực tiếp vào `infrastructure`; `textual` chỉ nằm trong `interfaces.tui`; `subprocess` chỉ nằm trong `infrastructure/process/subprocess_runner.py` (và `infrastructure/lnav/`, luồng PTY tương tác); `ssl` chỉ nằm trong `infrastructure/tls/ssl_context_builder.py`; `jinja2` chỉ nằm trong `infrastructure/exporters/html_exporter.py`; `sqlite3` chỉ nằm trong `infrastructure/persistence/sqlite_active_defense_connection.py` (kho lưu trữ quan hệ duy nhất của dự án, dành riêng cho Active Defense — xem §11); `lupa` chỉ nằm trong `infrastructure/waf/lua_waf_adapter.py` (script WAF bổ trợ « magnet », §7).

## 7. Mô-đun tùy chọn

Tất cả đều tắt mặc định trong mọi hồ sơ được cung cấp — luôn kích hoạt một cách tường minh (`option enable <tên>` hoặc `config enable-tls`):

| Mô-đun | Vai trò |
|---|---|
| `waf` | Chữ ký (đường dẫn nhạy cảm, UA/Referer của trình quét, SQLi/XSS/CMDi trong phần thân), danh sách có thể sửa dưới dạng tệp văn bản (từ khóa, hoặc đường dẫn nhạy cảm với ngoại lệ `!`, chế độ Quan sát và tái phạm riêng cho từng danh sách — hai danh sách tham chiếu được cung cấp, nạp tường minh, xem §11b), giới hạn tốc độ (token bucket, quy tắc theo thư mục và theo IP/mạng, xem §11c), danh sách chặn (CIDR + thời hạn), danh tiếng/leo thang, nhập một script WAF `mod_magnet` có sẵn của Lighttpd làm lớp tăng cường tùy chọn kiểu « magnet » (không cần viết lại, phần bổ sung `pip install -e ".[magnet]"` — mang tính cộng thêm, không bao giờ có thể gỡ một lệnh chặn gốc; kiểm tra tương thích lúc nhập, màn hình TUI riêng) — chế độ `log-only` về mặt cấu trúc không thể chặn |
| TLS | Trực tiếp (tự ký, CA cục bộ, hoặc công khai qua Let's Encrypt/Certbot với gia hạn tự động — xem §9), không bao giờ có mTLS/OCSP ở V1 |
| Xác thực | HTTP Basic theo vùng (`url_prefix`), `hashlib.scrypt` với cơ chế chống tấn công định thời (thời gian không đổi kể cả với người dùng không tồn tại) |
| FastCGI/PHP-FPM | Chỉ một `(url_prefix, script_root)`, `script_root` theo thiết kế bị giới hạn bên ngoài `webroot/` (trình xử lý tĩnh không bao giờ có thể làm lộ mã nguồn PHP) |
| Reverse proxy đi ra | Omega-serv tự đóng vai trò proxy tới một hoặc nhiều backend (chiều ngược với `server.tls.mode = "behind_proxy"`) — cân bằng tải (round-robin, có trọng số, least-connections, ip-hash, least-response-time, tải thực), gắn phiên và quy tắc định tuyến theo tiêu đề, kiểm tra sức khỏe thụ động và chủ động, cache phản hồi (nhiều biến thể `Vary`), backpressure, chống vòng lặp, API quản trị nóng — xem §7a để biết chi tiết đầy đủ |
| Tải lên | Vùng được cô lập, hạn ngạch theo vùng, tên tệp do máy chủ tạo — không có streaming ở V1 (giới hạn bởi `server.max_request_size`) |
| `active_defense` | Deception + chế độ chiến tranh dựa trên các tín hiệu WAF đã được tính (không bao giờ là điểm số thứ hai): mồi nhử tĩnh, làm chậm/ghi log chi tiết/giới hạn tốc độ có mục tiêu, sự cố + xuất IoC — xem §11 |

### 7a. Reverse proxy đi ra — chi tiết

OMEGA-SERV có thể tự đóng vai trò reverse proxy tới một hoặc nhiều backend HTTP/HTTPS — đừng bao giờ nhầm với `server.tls.mode = "behind_proxy"` (OMEGA-SERV **phía sau** một proxy, cơ chế ngược lại). Các vùng có thể cấu hình với CRUD đầy đủ (TUI: *Cấu hình chi tiết → Reverse Proxy*), một hoặc nhiều upstream cho mỗi vùng.

- **Cân bằng tải** — `round_robin` (mặc định), `weighted_round_robin`/`weighted_least_connections`/`ip_hash` (có trọng số), `least_connections`, `least_response_time`, `real_load` (tải thực). Chế độ `real_load` gốc (thăm dò `/.omega-serv-load/`, dùng lại cùng số đo `psutil` với màn hình « Trạng thái & Tài nguyên », không bao giờ gọi lần thứ hai) hoặc dạng khai báo (thăm dò HTTP bên thứ ba, định dạng tối thiểu `{"load_percent": ...}` hoặc một số trần) — chi tiết theo từng upstream, cùng một vùng có thể trộn cả hai.
- **Gắn phiên và định tuyến có điều kiện** — cookie sticky không trong suốt (không bao giờ để lộ host:port thật cho client) và quy tắc theo tiêu đề (bằng nhau hoặc tiền tố), cả hai đều được lọc theo điều kiện hợp lệ của upstream đích (quay về chiến lược đang dùng một cách gọn gàng nếu upstream đích không khả dụng).
- **Sức khỏe** — thụ động (số lần thất bại/thành công liên tiếp, ngưỡng chuyển down/up riêng biệt để hạn chế dao động) **và** chủ động (thăm dò định kỳ độc lập với lưu lượng thực, tùy chọn cho từng upstream, dùng lại cùng cơ chế tác vụ nền với tải thực). Các trạng thái `DOWN` (luôn tự động), `DRAINING`/`MAINTENANCE` (luôn thủ công, rõ ràng là tạm thời, không bao giờ được lưu lại) — một upstream được kích hoạt thủ công vẫn bị loại khỏi các lựa chọn mới mà không bao giờ cắt ngang một kết nối đã thiết lập. Tự động thử lại trên upstream khác, chỉ với các phương thức idempotent (GET/HEAD/OPTIONS) và chỉ khi lỗi kết nối.
- **Backpressure** — mức trần kết nối hoạt động có thể cấu hình cho mỗi upstream; một upstream bão hòa từ chối gọn gàng bằng 503, khác với upstream bị hỏng (502, vẫn được thử lại).
- **Cache phản hồi** — chỉ GET/HEAD, không bao giờ là phản hồi lỗi, không bao giờ có `Set-Cookie` trừ khi bật tường minh theo vùng; tuân thủ `Cache-Control`/`Vary` của upstream (tùy chọn có thể tắt nhưng nguy hiểm, cùng triết lý với việc kiểm tra TLS). Nhiều biến thể của cùng một tài nguyên (`Vary`) thực sự cùng tồn tại trên đĩa, không bao giờ chỉ đơn giản « bản đến sau thắng ». Khóa chống stampede (chỉ một yêu cầu đồng thời thực sự dựng lại cache). Tiêu đề chẩn đoán `X-Omega-Cache: HIT`/`MISS`/`BYPASS` trên mỗi phản hồi. Giám sát/dọn dẹp trong một màn hình TUI riêng (*Cache của reverse proxy*).
- **Chống vòng lặp** — loại bỏ tiêu đề hop-by-hop, `X-Forwarded-*` luôn bị ghi đè (không bao giờ hợp nhất với tiêu đề của client), bộ đếm `X-Omega-Proxy-Hops` tăng ở mỗi lần chuyển tiếp (từ chối gọn gàng khi vượt quá 5 bước — phát hiện vòng lặp gián tiếp giữa hai instance, điều mà một bước kiểm tra cấu hình cục bộ đơn thuần không bao giờ thấy được).
- **WebSocket** — cho phép nâng cấp theo vùng, một upstream duy nhất được cố định trong suốt thời gian của đường ống một khi đã thiết lập, không có timeout ở tầng ứng dụng.
- **Quản trị nóng** — một API HTTP cục bộ nhỏ (`/.omega-serv-admin/`, được bảo vệ bởi `trusted_proxy` giống như thăm dò tải gốc) cho phép TUI đọc/ép trạng thái DRAINING/MAINTENANCE của một backend và đọc tỷ lệ hit/miss của cache **của máy chủ đang thực sự chạy** (màn hình riêng *Trạng thái trực tiếp của backend*) — TUI và máy chủ là hai tiến trình riêng biệt không có bộ nhớ dùng chung, kênh HTTP cục bộ này là cầu nối duy nhất giữa hai bên.

## 8. Gia cố HTTP (không thể tắt)

- Tiêu đề/dòng yêu cầu được giới hạn **trong khi** đọc (không bao giờ sau đó), từ chối việc gập tiêu đề lỗi thời, `Transfer-Encoding` luôn bị từ chối (không bao giờ đoán).
- `Content-Length` trùng lặp bị từ chối; `Expect: 100-continue` bị từ chối gọn gàng (417).
- Danh sách phương thức được phép tường minh (405 + `Allow` nếu không), tiêu đề `Host` được kiểm tra (thiếu/rỗng/trùng lặp-kể-cả-giống-hệt/ký tự điều khiển → 400).
- Tiêu đề bảo mật và CSP cơ bản (`enforce`/`report-only`) được áp dụng cho **mọi** phản hồi, kể cả lỗi — không thể vượt qua bằng tùy chọn. `Cross-Origin-Opener-Policy`/`Cross-Origin-Resource-Policy` luôn là `same-origin`, không có rủi ro thực sự làm hỏng trang. `Cross-Origin-Embedder-Policy` luôn được phát tường minh (không bao giờ vắng mặt — trình quét bên ngoài phân biệt « chưa được xem xét » với « cố ý cho phép »), mặc định `unsafe-none` trên **mọi** hồ sơ kể cả `hardened`: khác với hai tiêu đề trên, `require-corp`/`credentialless` có thể chặn các tài nguyên cross-origin (phông chữ, ảnh, iframe bên thứ ba) của chính trang đang phục vụ — có thể điều chỉnh (`security.coep_mode`). Vùng CSP (`security.csp_zones`): ngoại lệ **tường minh** theo tiền tố đường dẫn (ví dụ `unsafe-inline` chỉ dưới `/mot-thu-muc/` thực sự cần đến), mỗi vùng thay thế hoàn toàn chính sách mặc định cho tiền tố của nó — không bao giờ hợp nhất, không bao giờ nới lỏng toàn cục; mọi ngoại lệ vẫn hiển thị trong `audit security` (CSP-001/CSP-002 cũng quét các vùng), kể cả khi có chủ ý. Tạo có hướng dẫn qua một trình hướng dẫn từng directive một (màn hình **Bảo mật chung**), mỗi trường được điền sẵn giá trị **hiện tại** của chính sách toàn cục — để chỉ sửa những gì cần thay đổi thay vì bắt đầu lại từ một trường rỗng vô tình hy sinh các directive khác; một xác nhận tường minh bổ sung được yêu cầu nếu vùng được lắp ráp nới lỏng `unsafe-inline`/`unsafe-eval`/một nguồn chung `*`.
- Địa chỉ IPv4-ánh-xạ-IPv6 (`::ffff:x.x.x.x`) được chuẩn hóa trước mọi phép so sánh (danh sách chặn, proxy tin cậy, giới hạn tốc độ) — nếu không sẽ là một lối vượt qua đã biết.
- Được kiểm chứng bằng kiểm thử thuộc tính (`hypothesis`, hàng nghìn ví dụ được sinh ra) trên bộ phân tích HTTP và bộ phân giải đường dẫn, bên cạnh các kiểm thử đơn vị/tích hợp thông thường.

## 9. TLS

### 9a. Chứng chỉ tự ký (tối thiểu)

Bao phủ nhu cầu thực tế cục bộ/phòng lab/VPN (Tailscale...): một listener duy nhất, `ssl.SSLContext` trực tiếp, RSA 2048/4096 hoặc ECDSA P-256/P-384.

### 9b. CA cục bộ

Dành cho nhiều thiết bị client cần tin cậy mà không phải nhập lại từng chứng chỉ riêng lẻ: một cơ quan cấp chứng chỉ cục bộ ký bao nhiêu chứng chỉ máy chủ tùy ý.

```text
secure/certificates/ca/
├── root-ca.key    # 0600 - thành phần nhạy cảm nhất của dự án
├── root-ca.pem    # 0644 - cần nhập vào kho tin cậy của các client
├── serial.txt     # 0600 - theo dõi số sê-ri tiếp theo
└── index.txt      # 0600 - theo dõi trạng thái V(hợp lệ)/R(đã thu hồi) cho mỗi chứng chỉ đã ký
```

Luồng: `certs generate-ca` (mật khẩu khóa CA **bắt buộc**, nhập tương tác với xác nhận hai lần nếu bỏ `--password`) → `certs generate-csr` (khóa + CSR máy chủ) → `certs sign-csr` (ký bằng CA, sao chép SAN từ CSR, tạo `fullchain.pem` nếu được yêu cầu) → trỏ `tls.certificate.certificate_path` tới `fullchain.pem` này. Một chứng chỉ bị lộ được thu hồi qua `certs revoke` (đánh dấu `index.txt`, trước tiên kiểm tra rằng chứng chỉ đúng là do CA này cấp — nếu không thì từ chối). Không phân phối CRL ở V1, cũng không có CA bên ngoài/CSR cho cơ quan bên thứ ba, không có mTLS (xem §15).

### 9c. Let's Encrypt / ACME (Certbot) — công khai, tự lưu trữ

Dành cho một trang thực sự công khai với chứng chỉ được trình duyệt công nhận, mô hình tự lưu trữ hoàn chỉnh: DDNS (Dynu hoặc tương đương, hoàn toàn do người vận hành đảm nhận) → Certbot → Omega-serv. Chỉ có trình hướng dẫn TUI (`Cấu hình chi tiết → TLS → Trình hướng dẫn Let's Encrypt`) — gọi `certbot certonly --webroot` dưới dạng tiến trình con (**không bao giờ** `--standalone`, cổng 80 đã bị Omega-serv chiếm; **không bao giờ** tự viết lại client ACME) với `--config-dir`/`--work-dir`/`--logs-dir` trỏ vào `secure/certificates/letsencrypt/` của dự án — **không bao giờ** `/etc/letsencrypt/` — điều này khiến chính Certbot hoàn toàn không cần đặc quyền. Chứng chỉ nhận được được nhập tự động (cùng cơ chế với `certs import`, xem các ví dụ CLI ở trên) và một script hook gia hạn được ghi ra. Chế độ thử (staging) được chọn mặc định — bỏ chọn khi đã xác nhận tên miền/webroot hoạt động, để tránh các giới hạn tốc độ thật của Let's Encrypt.

Các điều kiện tiên quyết hoàn toàn nằm ngoài phạm vi của Omega-serv: tên miền trỏ tới IP công khai (DDNS), và cổng 80/443 được chuyển tiếp tới máy này.

### 9d. Gia hạn tự động (Certbot)

`Cấu hình chi tiết → TLS → Gia hạn tự động` thích ứng với trình quản lý dịch vụ thực sự được phát hiện **cho instance này** (không bao giờ là cơ chế dùng chung giữa nhiều instance): systemd → tạo và cài một timer (`<service>-certbot-renew.timer`, hai lần mỗi ngày + độ trễ ngẫu nhiên, `certbot renew` giới hạn trong `--config-dir` của instance); nếu không → một dòng crontab (người dùng hiện tại, không cần đặc quyền) nếu có `crontab`; nếu không → hiển thị hướng dẫn thủ công, không ghi gì cưỡng ép. Trên một số bản phân phối (trong đó có Arch/Manjaro), gói Certbot **không** cài timer nào mặc định, khác với Debian/Ubuntu — do đó có màn hình này thay vì chỉ kiểm tra một cơ chế được cho là đã có sẵn. Sau khi cấu hình, việc gia hạn tự động nhập lại mỗi chứng chỉ được gia hạn (`certs import`) rồi khởi động lại dịch vụ, không bao giờ cần can thiệp thủ công nữa.

## 10. Kiểm tra bảo mật

`audit security` **không chặn**: nó chạy lại các cổng vốn đã chặn của `config check` ở mức `CRITICAL`, sau đó áp dụng các quy tắc tham vấn (TLS, CSP, phương thức nguy hiểm, timeout, vệ sinh tải lên thuần; quyền tệp, hạn chứng chỉ, unit systemd đã cài, kích thước log qua I/O thực). `WAF-001` (WAF vẫn ở `log-only`) được quan sát theo thời gian qua một tệp trạng thái nhỏ (`var/run/waf-mode-state.json`) — chỉ kích hoạt sau ≥14 ngày được quan sát ở `log-only` qua các lần chạy lặp lại, không phải ở lần `audit` đầu tiên.

## 11. Active Defense (deception + chế độ chiến tranh)

Mô-đun tùy chọn (`option enable active_defense`, tắt mặc định) đánh giá hành vi thù địch dựa trên các tín hiệu WAF đã được tính (`WafDecision`/danh tiếng/danh sách chặn — không bao giờ tính điểm độc lập lần thứ hai), và có thể chuyển một nguồn sang mồi nhử, làm chậm phản hồi của nó và ghi log chi tiết hơn, dựng một sự cố có thể khai thác, rồi xuất các chỉ báo xâm phạm (IoC). Không bao giờ tự chặn lưu lượng — việc chặn ở tầng mạng vẫn thuộc về `omega-fire`; Active Defense quan sát, chuyển hướng, làm chậm và ghi nhận.

**Mối đe dọa và điểm số**: mỗi nguồn (`IP + hash SHA-256 của User-Agent`) tích lũy điểm (`WAF-001` chặn +10, leo thang danh tiếng +25, đã bị cấm từ trước +25, POST lên một mồi nhử đã được gán +30 — giảm -5 mỗi 15 phút không có sự kiện mới) được phân loại thành `normal`/`suspicious`/`hostile`/`contained` (`contained` còn đòi hỏi nguồn đã bị cấm từ trước). `mode: monitor` quan sát mà không hành động; `mode: enforce` thực sự áp dụng các hành động bên dưới.

**Chế độ chiến tranh** (`options.active_defense.settings.war_mode`): một `DefensePlaybook` (`actions: ["redirect_to_decoy", "enrich_log", "delay", "rate_limit", "create_incident", "export_ioc"]`) được kích hoạt bởi các ngưỡng có thể cấu hình, cho mọi nguồn không phải `normal`:
- `enrich_log` — log JSONL riêng (`var/log/active-defense-enriched.jsonl`, không bao giờ trộn với log WAF/production), tiêu đề được che, phần thân HTTP được băm (SHA-256) hoặc cắt ngắn theo `logging.capture_request_body`.
- `delay` — làm chậm có giới hạn và có jitter (`war_mode.slowdown.minimum_ms`/`maximum_ms`/`jitter_ms`), không bao giờ chặn vòng lặp asyncio.
- `rate_limit` — giới hạn tốc độ riêng cho từng nguồn (`war_mode.rate_limit.requests`/`window_seconds`), dùng lại cùng cơ chế với WAF dưới một khóa riêng.
- `create_incident` — tự động mở/gộp một sự cố khi vượt `thresholds.incident_score`.

**Deception**: một nguồn `hostile`/`contained` có thể được gán cho một mồi nhử tĩnh (`fake_admin`, `fake_cms`, `fake_api`, `fake_secrets` — phản hồi trông hợp lý nhưng luôn cố định, không bao giờ đọc tệp thật hay chạy tiến trình con) được chọn theo lớp tấn công quan sát được (`deception.profiles.<tên>.match_attack_classes`, một hoặc nhiều trong số `scan`/`credential_stuffing`/`sqli`/`xss`/`path_traversal`/`upload_probe`/`api_probe`/`unknown`). Hai mức cô lập, được chấp nhận và tài liệu hóa đúng như vậy:
- **Mức 1** (fixture trong tiến trình, `isolation_level: "fixture"`, mặc định) — cô lập YẾU một cách tường minh: cùng tiến trình, cùng người dùng OS với production, chỉ chấp nhận được vì fixture không bao giờ làm gì khác ngoài trả về một mẫu tĩnh. TÊN của hồ sơ phải khớp chính xác với một trong 4 fixture ở trên — nếu không sẽ bị từ chối khi kiểm tra (`validate_active_defense_config`), để tránh cái bẫy một mồi nhử đặt sai tên rồi âm thầm không bao giờ được kích hoạt.
- **Mức 2** (backend thực sự cô lập, `isolation_level: "proxy"`) — chuyển tiếp tới một tiến trình riêng qua `options.active_defense.settings.deception.decoy_zones.<tên>` (upstream `host`/`port` của một máy chủ đã đang chạy, không bao giờ được tạo tự động; không bao giờ đọc từ `options.reverse_proxy` — một mồi nhử không bao giờ có thể vô tình trỏ tới một vùng production, được kiểm tra ở `config check`), dùng lại cùng cơ chế reverse proxy đi ra với production (`serve_proxy()` — upstream không thể liên lạc tại thời điểm có yêu cầu thật: trả 502 cho kẻ tấn công, không bao giờ sập).

**Màn hình Thiết lập** (TUI, Bảo mật chủ động → Active Defense → Thiết lập): cấu hình đầy đủ mọi thứ ở trên — chế độ, kích hoạt chế độ chiến tranh, phạm vi/hành động/ngưỡng/làm chậm/giới hạn yêu cầu, deception (hành vi mặc định, CRUD các hồ sơ mồi nhử và vùng mồi nhử với giá trị ví dụ hiển thị trong mỗi trường), IoC, lưu trữ và ghi log — được kiểm tra bằng cùng các quy tắc như CLI trước mỗi lần lưu, không bao giờ cần sửa tay `config/omega-serve.json`. Luôn cần khởi động lại hoàn toàn sau mọi thay đổi (Active Defense không bao giờ được nạp lại nóng).

**Sự cố và IoC**: dòng thời gian đầy đủ cho mỗi sự cố, trích xuất chỉ báo (IP, User-Agent đã băm), xuất JSON có phiên bản/CSV chỉ gồm IoC có thể chia sẻ/báo cáo Markdown, và các định dạng trao đổi **STIX 2.1** (bundle để nạp vào OpenCTI, một SIEM…) và **MISP** (sự kiện để nhập qua giao diện của MISP), được đánh dấu TLP:AMBER mặc định — tệp cục bộ, không bao giờ được gửi đi; mỗi bản xuất kèm một tệp `<export>.sha256` (định dạng `sha256sum` chuẩn). Tự động xuất khi đóng một sự cố nếu `ioc.auto_export_on_close` (mặc định là true). Các trạng thái hết hạn và nhật ký kiểm toán được dọn tự động, cơ sở dữ liệu có mức trần (bảo vệ chống đầy đĩa); `active-defense purge` còn đóng thêm các sự cố đã yên lặng trở lại.

**Mô phỏng**: `active-defense simulate` (CLI) và nút "Mô phỏng" (TUI, màn hình Bảo mật chủ động) dự đoán điểm/mức và giải thích từng hành động sẽ được kích hoạt — dry-run nghiêm ngặt, không ghi gì thật, không ảnh hưởng mạng.

Sao lưu/khôi phục: `config backup --include-active-defense` đưa cơ sở dữ liệu sqlite (mối đe dọa/sự cố/phân bổ) vào bản lưu trữ — không bao giờ có bí mật ở dạng rõ, nên không cần `--confirm-secrets`, khác với `--include-auth`.

## 11b. Danh sách đường dẫn nhạy cảm (WAF)

WAF có thể nạp các **danh sách có thể sửa** dưới dạng tệp văn bản, mỗi dòng một đường dẫn (hoặc một từ khóa), từ **Bảo mật chủ động → Custom → Thêm → « NẠP danh sách »**. Không có gì được nạp mặc định: đó là một hành động tường minh.

- **Danh sách tham chiếu được cung cấp**: `sensitive-paths-hostile` (298 đường dẫn không có mục đích chính đáng: bí mật, bản sao lưu, VCS, console…) và `sensitive-paths-probe` (132 đường dẫn thăm dò, đôi khi được một trang thật phục vụ: `/admin`, `/api`, giám sát…). Khi nạp, một **bản sao cục bộ** được tạo trong `secure/waf/rules/keywords/`: đó là bản bạn chỉnh sửa, một bản cập nhật omega-serv không bao giờ ghi đè nó (« Mục mới trong mẫu tham chiếu » sau đó đề xuất các mục mới, từng ô một).
- **Cú pháp**: `/admin` (→ `/admin` và `/admin/xxx`, không bao giờ `/administrator`), `/.git/` (mọi thứ bên dưới), `/*.bak` (phần mở rộng), `!/api/v1` (ngoại lệ, luôn được ưu tiên). Đường dẫn được giải mã giống như trong engine (`%2e`, mã hóa kép, ký tự toàn chiều rộng).
- **Mức độ**: *Quan sát* (chỉ ghi log, khuyến nghị cho lần nạp đầu tiên), sau đó Trung bình (không bao giờ tự mình chặn) hoặc Cao (403 ngay từ lần truy cập đầu tiên).
- **Tái phạm riêng cho từng danh sách**: lần truy cập thứ 1 = thông tin hoặc từ chối; N lần truy cập trong M phút = cấm tạm thời ở tầng ứng dụng (phản hồi 451, kể cả qua Tailscale); chặn lặp lại = cấm ở tầng mạng bởi omega-jail. Tham chiếu: hostile 2 lần truy cập trong 10 phút → 24 giờ, probe 5 lần trong 10 phút → 1 giờ.
- **Không bao giờ tự động cấm** máy cục bộ, Tailscale (`100.64.0.0/10`) và mạng cục bộ (`options.waf.reputation.never_auto_block`): chỉ lưu lượng bên ngoài mới có thể bị cấm. Phía sau một proxy cục bộ, việc miễn trừ `127.0.0.1` đòi hỏi `trusted_proxy` đang bật. `X-Forwarded-For` được đọc từ phải sang trái: một client không thể tự khai mình là cục bộ.
- **Rào chắn an toàn**: các đường dẫn thiết yếu được bảo vệ (`/`, `robots.txt`, `sitemap.xml`, `/.well-known/acme-challenge/`…), từ chối một danh sách chặn đụng vào một tuyến đường đang thực sự được phục vụ (alias, reverse proxy, vùng Auth, webroot), **« Đối chiếu với log của tôi »** trong trình soạn (các dòng lẽ ra đã khớp với yêu cầu thành công, thêm ngoại lệ bằng một cú nhấp).
- **Trình soạn tích hợp**: chẩn đoán trực tiếp kèm số dòng, « Thử » một đường dẫn, ghi an toàn (giữ nguyên quyền và nhóm, từ chối liên kết tượng trưng, phát hiện sửa đổi từ bên ngoài), kiểm tra khả năng đọc của tài khoản dịch vụ (« Sửa quyền »), và nạp lại **trung thực**: bị từ chối kèm lý do nếu danh sách không vượt qua kiểm tra, khi đó máy chủ giữ nguyên các quy tắc hiện tại.

## 11c. Giới hạn tốc độ theo thư mục và theo IP/mạng (WAF)

Giới hạn tốc độ của WAF (token bucket, `options.waf.rate_limit`, mặc định 60 yêu cầu / 60 giây cho mỗi IP) có thể được tinh chỉnh từ **Bảo mật chủ động → Ngoại lệ và tần suất** (hoặc thủ công, `rate_limit.path_policies` / `rate_limit.source_policies`):

- **Quy tắc theo thư mục** (`prefix`, `requests`, `window_seconds`): nó **thay thế** giới hạn toàn cục cho thư mục đó, với bộ đếm riêng (`requests: 0` = không giới hạn). Tiền tố dài nhất thắng; `/images` bao phủ `/images/a.png`, không bao giờ `/images2`. Điển hình là một trang nặng (thư viện ảnh) trả về 429.
- **Quy tắc theo IP/mạng** (`network`, `requests`, `window_seconds`, `trusted`): cùng nguyên tắc; mạng chính xác nhất thắng. Thứ tự ưu tiên: thư mục, rồi IP/mạng, rồi giới hạn toàn cục.
- **Việc cấm không đổi với công chúng**: một lần vượt giới hạn của IP công khai vẫn được ghi `"action": "block"` trong `waf-alerts.log`, do đó có thể bị omega-jail cấm (3 lần từ chối trong 10 phút → 12 giờ). Một **nguồn an toàn** — mạng `never_auto_block` hoặc quy tắc được đánh dấu `trusted: true` — vẫn nhận 429 nhưng được ghi `"action": "throttle"`, thứ mà jail không bao giờ đếm.
- **Script magnet**: giới hạn tốc độ riêng của nó (phản hồi 429) không bao giờ được tính là một phát hiện, do đó không bao giờ dẫn đến tự động cấm; với một yêu cầu thuộc phạm vi một quy tắc thư mục hoặc IP/mạng, quy tắc gốc là căn cứ và 429 của magnet bị bỏ qua (các chữ ký tấn công của nó vẫn được áp dụng).
- Một quy tắc tốc độ **không bao giờ** tắt việc kiểm tra của WAF; ngược lại, một ngoại lệ kiểm tra (`exclusions.path_prefixes`) không bao giờ gỡ bỏ rate limit. Khi không bật `trusted_proxy`, một quy tắc bao phủ `127.0.0.1`/`::1` bị bỏ qua (cùng rào chắn với `never_auto_block`).

## 12. Dịch vụ và vận hành

Tự động phát hiện systemd/OpenRC/runit (`service install/status/start/stop/restart/enable/disable/uninstall`). Unit systemd được tạo áp dụng cơ chế gia cố mặc định không thương lượng: `NoNewPrivileges`, `PrivateTmp`, `ProtectSystem=strict`, `ProtectHome`, `ReadWritePaths` giới hạn ở `var/`, bắt buộc người dùng/nhóm riêng, `UMask=0077`, `Restart=on-failure`. Dừng sạch khi nhận SIGTERM (xả các kết nối đang xử lý, thời gian ân hạn có thể cấu hình rồi đóng cưỡng bức); nạp lại nóng khi nhận SIGHUP (chỉ quy tắc WAF và vùng Auth — bind/cổng/TLS và Active Defense không bao giờ thay đổi được nếu không khởi động lại hoàn toàn).

## 13. Log

`var/log/access.log` (định dạng Apache combined + `request_id`, thoát ký tự chống chèn log), `var/log/error.log`. Xoay vòng theo kích thước/số tệp được giữ lại (`logs.rotation`). WAF gốc: `var/log/waf-alerts.log` (`options.waf.logging.path`). Script magnet (§7): `options.waf.magnet.paths.alerts_log`/`.blocklist_log`, mặc định `var/log/waf-magnet-alerts.log`/`var/log/waf-magnet-blocklist.log` — chỉ được thêm sẵn vào Thư viện (nút *Thêm các log đã biết của Omega-Serv*) nếu magnet đang bật; còn `lnav` thì luôn đề xuất chúng (tệp không tồn tại chỉ đơn giản bị bỏ qua khi khởi chạy).

### 13a. Nguồn từ xa (SSH)

Tập trung, theo yêu cầu tường minh, log của một máy chủ backend nằm trong cùng mạng cục bộ phía sau reverse proxy (màn hình **Quản lý log → Thư viện → Nguồn từ xa (SSH)**). Một lần « fetch » là thao tác thủ công và đơn lẻ, không bao giờ là luồng trực tiếp hay thăm dò tự động: một **bản sao** được tải về qua `scp` lúc nhấp *Tải về ngay*, ghi vào `var/log/remote/`, rồi thêm vào Thư viện như một log bình thường (cột *Truy cập* = `ssh`, cột *Sửa đổi* = ngày của **lần** tải về **này** — không bao giờ là ngày của tệp từ xa); lần tải về mới chỉ đơn giản thay bản sao trước bằng bản mới hơn.

Rào chắn có chủ ý (xem `OMEGA-SERV_ETUDE-FAISABILITE_LOGS_DISTANTS.md` cho nghiên cứu đầy đủ): không quét mạng tự động, không kết nối khi chưa có cấu hình tường minh (nhãn/máy chủ/đường dẫn từ xa, người dùng/cổng/khóa riêng tùy chọn — để trống thì để `ssh`/`~/.ssh/config` quyết định như khi gõ lệnh bằng tay), không bao giờ hỏi hay lưu mật khẩu (một khóa riêng chỉ được tham chiếu qua đường dẫn, không bao giờ được Omega-serv đọc hay lưu), không kiểm tra kích thước trước khi truyền. Khả năng `scp` được phát hiện cục bộ trong **Sổ đăng ký khả năng** (chỉ kiểm tra sự hiện diện của tệp thực thi, không bao giờ kiểm tra khả năng kết nối tới một máy chủ); Samba được cố ý để sang một bên (YAGNI, chừng nào chưa có nhu cầu thực sự được xác nhận).

## 14. Kiểm thử

```bash
source .venv/bin/activate
lint-imports        # kiểm tra 8 hợp đồng phân lớp
pytest -q           # 2485 bài kiểm thử
ruff check .
mypy src
```

Cấu trúc: `tests/unit/` (domain/application, test double), `tests/integration/` (máy chủ asyncio thật trên socket TCP thật, `openssl` thật dưới dạng tiến trình con, lệnh CLI thật trên một dự án tạm thời hoàn chỉnh, giao diện tương tác qua API `Pilot` của Textual - không bao giờ chụp màn hình), `tests/security/` (kiểm thử thuộc tính `hypothesis` trên bộ phân tích HTTP và bộ phân giải đường dẫn).

## 15. Ngoài phạm vi

- CGI thô (chỉ FastCGI/PHP-FPM)
- mTLS (xác thực client bằng chứng chỉ), OCSP stapling
- CA bên ngoài / CSR cho cơ quan bên thứ ba, phân phối CRL đầy đủ
- Active Defense: tích hợp thực sự với các sự kiện cấm của `omega-fire` (bị chặn ở phía `omega-fire`, hiện chưa cung cấp bề mặt đọc nào)

---

> 🔒 OMEGA-SERV — Một máy chủ web vững chắc, đầy đủ, an toàn và có khả năng phòng thủ.
