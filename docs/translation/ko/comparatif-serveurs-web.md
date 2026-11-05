<!-- Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE) -->

# omega-serv와 시장의 웹 서버 비교

**측정에 기반한 비교: nginx · lighttpd · Apache · Caddy · Traefik · omega-serv 2.5**

🌐 [Français](../../comparatif-serveurs-web.md) · [English](../en/comparatif-serveurs-web.md) · [Español](../es/comparatif-serveurs-web.md) · [Português (Brasil)](../pt-BR/comparatif-serveurs-web.md) · [Italiano](../it/comparatif-serveurs-web.md) · [Deutsch](../de/comparatif-serveurs-web.md) · [Nederlands](../nl/comparatif-serveurs-web.md) · [Polski](../pl/comparatif-serveurs-web.md) · [Русский](../ru/comparatif-serveurs-web.md) · [中文](../zh-CN/comparatif-serveurs-web.md) · [Tiếng Việt](../vi/comparatif-serveurs-web.md) · [ไทย](../th/comparatif-serveurs-web.md) · [Bahasa Indonesia](../id/comparatif-serveurs-web.md) · [日本語](../ja/comparatif-serveurs-web.md) · **한국어** · [हिन्दी](../hi/comparatif-serveurs-web.md) · [العربية](../ar/comparatif-serveurs-web.md)

이 문서는 가장 널리 쓰이는 웹 서버들 사이에서 omega-serv가 어디에 위치하는지 보여 줍니다. "최고의 서버"를 가리려는 것이 목적이 아닙니다. 각 도구는 서로 다른 요구에 답하며, 저마다 강점이 있습니다. 이 문서는 세 가지를 제공합니다.

1. **실제 측정값**: 성격이 매우 다른 **세 대의 머신**에서 같은 클라이언트, 같은 파일, 같은 절차로 측정했으며 재현할 수 있습니다.
2. **기능 비교**: 각 항목을 해당 서버의 공식 문서로 확인했으며(링크는 문서 끝에 있음), 내장 기능과 모듈 또는 플러그인이 필요한 기능을 구분했습니다.
3. omega-serv가 **실제로 더 제공하는 것**과, 다른 서버가 **omega-serv보다 잘하는 것**.

모든 성능 측정은 2026년 11월 3일과 4일에 수행했습니다. 다른 사이트에서 가져오거나 추정한 수치는 하나도 없습니다. 원시 데이터는 이 문서와 함께 공개합니다.

---

## 목차

1. [요약](#1-요약)
2. [이 비교를 읽는 방법](#2-이-비교를-읽는-방법)
3. [측정 방법](#3-측정-방법)
4. [성능: omega-serv와 nginx, lighttpd, Apache, Caddy 비교](#4-성능-omega-serv와-nginx-lighttpd-apache-caddy-비교)
5. [omega-serv 버전: 1.0 → 2.0 → 2.5](#5-omega-serv-버전-10--20--25)
6. [기능 비교](#6-기능-비교)
7. [관리와 편의성](#7-관리와-편의성)
8. [omega-serv가 더 제공하는 것](#8-omega-serv가-더-제공하는-것)
9. [다른 서버가 더 잘하는 것](#9-다른-서버가-더-잘하는-것)
10. [어떤 용도에 어떤 서버를](#10-어떤-용도에-어떤-서버를)
11. [측정 재현](#11-측정-재현)
12. [출처](#12-출처)

---

## 1. 요약

- **omega-serv에는 엔진이 두 개 있습니다.** **Python 엔진**은 모든 것을 처리합니다. **네이티브 엔진**은 C++로 작성되어 2.5부터 제공되며, 요청에 직접 응답합니다. 설정과 보안 결정은 계속 Python이 맡고, 어떤 WAF 규칙에도 일치하지 않는 요청은 네이티브 엔진이 직접 가려냅니다.
- **네이티브 엔진에서 WAF 없이**, omega-serv는 작은 파일을 **nginx의 약 0.7** 속도로 제공합니다. 세 머신 모두에서 같습니다. 따라서 **Apache와 Caddy보다 앞서고, nginx와 lighttpd보다 뒤**에 있습니다.
- **Python 엔진에서는** omega-serv가 다른 모든 서버에 크게 뒤처집니다: **nginx 속도의 3–11 %**.
- **WAF를 켜면** omega-serv는 모든 요청을 검사하며, 측정한 다른 서버들은 이를 하지 않습니다. 네이티브 엔진에서는 머신 A와 B에서 nginx(WAF 없음)의 **0.53–0.56**, 머신 C에서 1.07(코어 4개 대 2개)에 이릅니다. WAF로 잃는 처리량은 5–22 %에 불과합니다. WAF 없이 측정한 Apache와 Caddy보다 여전히 앞섭니다.
- **중간 크기 파일(100 KB)**: 네이티브 엔진의 현재 약점으로, nginx의 **0.3–0.6**이며 Apache보다 뒤입니다.
- **큰 파일(5 MB)**: nginx, lighttpd, Apache, 네이티브 omega-serv는 같은 수준의 처리량에 도달합니다. 가장 빠른 머신에서는 Caddy가 눈에 띄게 느립니다.
- **메모리**: lighttpd(1 MB), nginx(4–5 MB), Apache(4–9 MB)는 매우 절약형입니다. omega-serv는 모드에 따라 **30–65 MB**, Caddy는 **50–67 MB**를 사용합니다.
- **omega-serv가 더 제공하는 것**: 17개 언어를 지원하는 터미널 인터페이스에서의 완전한 관리, 내장 WAF와 능동 방어, 여러 프로세스에서도 정확한 보안 제한, lighttpd mod_magnet 스크립트 가져오기, 여러 인스턴스 관리.
- **없는 것**: HTTP/2와 HTTP/3, 실시간 압축, Docker/Kubernetes 서비스 검색, 내장 ACME 클라이언트(Certbot 사용), 모듈 생태계.

---

## 2. 이 비교를 읽는 방법

문서 전반에 몇 가지 개념이 반복해서 나옵니다.

- **초당 요청 수(req/s)**: 서버가 1초에 보내는 파일 수. 높을수록 좋습니다.
- **nginx와의 차이**: 절대값은 머신에 따라 크게 달라집니다. 세 머신에서 nginx는 22 000에서 440 000 req/s까지 차이가 납니다. 안정적인 것은 **서버 간 비율**입니다. 그래서 표에는 각 값 옆에 같은 세션에서 측정한 nginx와의 비율을 표시합니다: **1.00 = nginx만큼 빠름**, 0.50 = 절반 속도, 1.50 = 1.5배 빠름.
- **p99 지연 시간**: 요청의 99 %가 넘지 않는 응답 시간. 평균이 감추는 "나쁜 순간"을 드러냅니다.
- **PSS(*Proportional Set Size*)**: 서버의 모든 프로세스가 실제로 사용하는 메모리. 여러 프로세스가 공유하는 페이지는 한 번만 셉니다.
- **프로세스와 코어**: 서버는 여러 프로세서 코어를 사용할 수 있으며, 방식은 서버마다 다릅니다. nginx, lighttpd, Apache와 Python 모드의 omega-serv는 여러 프로세스를 실행합니다. Go로 작성된 Caddy는 작업을 코어에 분산합니다. omega-serv의 네이티브 엔진은 사용 가능한 코어마다 스레드 하나를 실행합니다. 공정하게 비교하기 위해 각 서버에 **같은 코어**를 주었습니다.
- **WAF(*Web Application Firewall*)**: 공격(인젝션, 스캐너 등)을 차단하기 위해 모든 요청을 검사하는 필터. omega-serv에는 내장되어 있습니다. 다른 서버도 모듈(ModSecurity, Coraza)로 갖출 수 있지만, **측정은 WAF 없이** 기본 설정으로 했습니다.

**올바른 습관**: 절대값이 아니라 비율을 비교하고, WAF가 켜져 있는지 항상 확인하세요.

---

## 3. 측정 방법

### 세 대의 머신

| | 머신 A | 머신 B | 머신 C |
|---|---|---|---|
| 프로세서 | Intel Core i5 M480, 2.67 GHz (2010) | Intel Celeron J3455, 1.5 GHz (2016) | AMD Ryzen AI 9 365 (2024) |
| 코어 | 물리 코어 2개, 스레드 4개 | 코어 4개, 하이퍼스레딩 없음 | 코어 10개(Zen 5 4개 + Zen 5c 6개), 스레드 20개 |
| 메모리 | 8 GB | 8 GB | 32 GB |
| 시스템 | Mabox Linux(Manjaro 기반), 커널 6.18 | EndeavourOS, 커널 7.2 | Arch Linux, 커널 7.2 (CachyOS) |
| 서버 코어 | 물리 코어 1개(스레드 0과 2) | 코어 2개(0과 1) | Zen 5 코어 4개, 코어당 스레드 1개(0–3) |
| 클라이언트 코어 | 물리 코어 1개(스레드 1과 3) | 코어 2개(2와 3) | Zen 5c 코어 6개(4–9) |

머신 A는 오래된 노트북, 머신 B는 저전력 미니 PC, 머신 C는 새 노트북으로 전원에 연결하고 "균형" 전원 프로필을 사용했습니다. 작은 가정용 서버부터 최신 머신까지 아우릅니다.

### 소프트웨어

| 소프트웨어 | 버전 |
|---|---|
| nginx | 1.30.4 (A), 1.30.5 (B, C) |
| lighttpd | 1.4.85 |
| Apache HTTP Server | 2.4.69, MPM `event` |
| Caddy | 2.11.4 (A, B), 2.11.7 (C) |
| omega-serv | 1.0.0과 2.0.0(공개된 아카이브) 및 2.5, Python 3.14 |
| 부하 클라이언트 | [oha](https://github.com/hatoo/oha) 1.16.0 (Rust로 작성) |

Traefik은 파일 서버가 아니므로 측정하지 않았습니다(§6 참조). 기능 비교에만 등장합니다.

### 절차

- **프로세서 격리**: 서버와 클라이언트를 서로 다른 코어에 고정했습니다(위 표). 클라이언트가 서버의 시간을 빼앗지 않으며, 모든 서버가 정확히 같은 자원을 가집니다.
- **모두에게 같은 파일**: `small.html`(1 KB), `medium.png`(100 KB), `large.bin`(5 MB)을 같은 폴더에서 제공합니다.
- **접근 로그는 모두 켜져 있음**: 운영 중인 서버는 로그를 남기기 때문입니다.
- **암호화 없는 HTTP/1.1, 지속 연결(keep-alive)**. 동시성은 1 KB와 100 KB 파일에 연결 32개, 5 MB 파일에 8개입니다.
- **시간**: 파일별, 설정별 10초.
- **반복**: 번갈아 진행하는 완전한 3회(1회차에 모든 설정, 이어서 2회차에 모든 설정 등). 표에는 3회의 **중앙값**을 표시합니다. 회차 간 차이는 대부분 5 % 미만입니다.
- **메모리**: 서버의 모든 프로세스의 PSS를 유휴 시와 부하 후에 기록합니다.
- **설정**:
  - nginx, lighttpd, Apache, Caddy는 기본 설정: 정적 파일과 접근 로그;
  - omega-serv는 `standard` 프로필로, WAF를 끈 상태와 제공되는 모든 규칙으로 켠 상태(속도 제한 없음).
- **프로세스 수**: 각 서버를 프로세스 1개, 이어서 2개로 측정합니다: nginx `worker_processes`, lighttpd `server.max-worker`, Apache `StartServers`/`ServerLimit`, Caddy `GOMAXPROCS`, omega-serv `server.workers`. omega-serv 네이티브 엔진에서 `server.workers`는 Python 보안 프로세스 수를 뜻하며, 네이티브 엔진 자체는 할당된 모든 코어를 항상 사용합니다.
- **오류 없음**: 모든 측정의 모든 응답이 200이었습니다.

### 알아 두어야 할 한계

- **비교하는 것은 비율입니다.** 여러분의 하드웨어나 전용 서버에서는 절대값이 다를 것입니다.
- **루프백 인터페이스(127.0.0.1)**: 측정은 실제 네트워크를 거치지 않습니다. 실제 네트워크에서는 큰 파일의 처리량이 거의 항상 서버가 아니라 회선에 의해 제한됩니다. 머신 C에서의 수십 GB/s 처리량은 루프백에서만 가능합니다.
- 이 측정에는 **TLS가 없습니다**.
- **머신 A**: 이 머신의 운영용 omega-serv 서비스가 백그라운드에서 실행 중이었지만 트래픽은 받지 않았습니다.
- **머신 C**: 하이브리드 프로세서(Zen 5와 Zen 5c 코어). 서버에는 빠른 코어 4개, 클라이언트에는 나머지 6개를 할당했습니다.
- **기본 설정**: 어떤 서버도 최적화하지 않았습니다. 숙련된 관리자라면 omega-serv를 포함해 각 서버에서 더 많은 성능을 끌어낼 수 있을 것입니다.
- **원시 데이터**: [`docs/benchmarks/`](../../benchmarks/) (머신별 파일 하나).

---

## 4. 성능: omega-serv와 nginx, lighttpd, Apache, Caddy 비교

모든 표에서 기준은 **프로세스 2개의 nginx**(= 1.00)이며, 같은 머신의 같은 세션에서 측정했습니다. 머신 A와 B에서는 이것이 서버에 할당된 모든 코어를 사용하는 설정입니다.

### 작은 파일(1 KB): 초당 요청 수

| 서버 | 머신 A | 머신 B | 머신 C |
|---|---:|---:|---:|
| lighttpd, 프로세스 2개 | 33 138 (**1.52**) | 31 125 (**1.26**) | 378 590 (**1.53**) |
| nginx, 프로세스 2개 | 21 801 (1.00) | 24 705 (1.00) | 248 184 (1.00) |
| **omega-serv, 네이티브 엔진** | **15 222 (0.70)** | **16 542 (0.67)** | **285 213 (1.15 \*)** |
| omega-serv, 네이티브 + WAF † | 11 990 (0.56) | 12 998 (0.53) | 264 484 (1.07 \*) |
| omega-serv, 네이티브 + WAF, 보안 프로세스 2개 † | 11 746 (0.55) | 12 718 (0.52) | 253 527 (1.02 \*) |
| Apache, 프로세스 2개 | 9 192 (0.42) | 8 634 (0.35) | 188 335 (0.76) |
| Caddy, 프로세스 2개 | 5 749 (0.26) | 4 116 (0.17) | 52 897 (0.21) |
| omega-serv, Python 엔진, 프로세스 2개 | 2 354 (0.11) | 1 312 (0.05) | 19 911 (0.08) |
| omega-serv, Python + WAF, 프로세스 2개 | 1 901 (0.09) | 1 104 (0.04) | 15 783 (0.06) |
| omega-serv, Python 엔진 | 1 507 (0.07) | 663 (0.03) | 10 553 (0.04) |
| omega-serv, Python + WAF | 1 561 (0.07) | 564 (0.02) | 8 365 (0.03) |

\* 머신 C에서 네이티브 엔진은 코어 4개를 사용하지만, 프로세스 2개의 nginx는 2개만 사용합니다. 같은 코어 수에서의 비교는 아래에 있습니다. 그 경우 비율은 다시 **0.67–0.71**로, 다른 머신과 같습니다.

† 11월 4일, WAF 최적화 후 같은 절차의 별도 세션에서 측정. 비율은 이 세션의 nginx(프로세스 2개) 기준으로 계산했습니다: 작은 파일은 21 439, 24 424, 248 127 req/s, 100 KB 파일은 11 545, 11 004, 157 491. 이 최적화 전에는 WAF를 켠 네이티브 엔진이 3 495, 2 622, 39 000 req/s(nginx의 0.11–0.16)였는데, 모든 요청이 Python을 거쳤기 때문입니다. 원시 데이터: `*-waf-natif-brut.txt` 파일.

프로세스 1개에서는 nginx가 0.52–0.73, lighttpd가 0.81–1.43, Apache가 0.33–0.74, Caddy가 0.09–0.17입니다(원시 데이터).

### 작은 파일의 p99 지연 시간

| 서버 | 머신 A | 머신 B | 머신 C |
|---|---:|---:|---:|
| lighttpd, 프로세스 2개 | 4.4 ms | 4.1 ms | 0.2 ms |
| nginx, 프로세스 2개 | 4.9 ms | 5.2 ms | 0.2 ms |
| **omega-serv, 네이티브 엔진** | **6.1 ms** | **6.2 ms** | **0.3 ms** |
| omega-serv, 네이티브 + WAF † | 7.2 ms | 6.7 ms | 0.3 ms |
| Apache, 프로세스 2개 | 18.8 ms | 20.6 ms | 0.8 ms |
| Caddy, 프로세스 2개 | 24.1 ms | 30.5 ms | 2.8 ms |
| omega-serv, Python 엔진, 프로세스 2개 | 22.6 ms | 28.1 ms | 3.3 ms |
| omega-serv, Python 엔진 | 32.0 ms | 51.6 ms | 4.4 ms |

### 중간 크기 파일(100 KB): 초당 요청 수

| 서버 | 머신 A | 머신 B | 머신 C |
|---|---:|---:|---:|
| lighttpd, 프로세스 2개 | 13 561 (**1.08**) | 12 126 (**1.07**) | 197 905 (**1.26**) |
| nginx, 프로세스 2개 | 12 513 (1.00) | 11 303 (1.00) | 157 224 (1.00) |
| Apache, 프로세스 2개 | 6 939 (0.55) | 7 035 (0.62) | 153 265 (0.97) |
| Caddy, 프로세스 2개 | 5 059 (0.40) | 3 744 (0.33) | 22 094 (0.14) |
| **omega-serv, 네이티브 엔진** | **4 738 (0.38)** | **3 115 (0.28)** | **96 277 (0.61)** |
| omega-serv, 네이티브 + WAF † | 4 229 (0.37) | 2 926 (0.27) | 98 185 (0.62) |
| omega-serv, Python 엔진, 프로세스 2개 | 1 741 (0.14) | 1 154 (0.10) | 18 806 (0.12) |
| omega-serv, Python 엔진 | 1 329 (0.11) | 611 (0.05) | 9 805 (0.06) |

### 큰 파일(5 MB): 처리량

| 서버 | 머신 A | 머신 B | 머신 C |
|---|---:|---:|---:|
| lighttpd, 프로세스 2개 | 2 440 MB/s (1.05) | 2 110 MB/s (0.99) | 28 011 MB/s (0.81) |
| nginx, 프로세스 2개 | 2 322 MB/s (1.00) | 2 124 MB/s (1.00) | 34 651 MB/s (1.00) |
| Apache, 프로세스 2개 | 2 355 MB/s (1.01) | 2 134 MB/s (1.00) | 41 153 MB/s (**1.19**) |
| **omega-serv, 네이티브 엔진** | **2 294 MB/s (0.99)** | **1 936 MB/s (0.91)** | **37 918 MB/s (1.09)** |
| Caddy, 프로세스 2개 | 2 205 MB/s (0.95) | 1 996 MB/s (0.94) | 3 811 MB/s (0.11) |
| omega-serv, Python 엔진, 프로세스 2개 | 2 145 MB/s (0.92) | 1 931 MB/s (0.91) | 25 829 MB/s (0.75) |
| omega-serv, Python 엔진 | 1 686 MB/s (0.73) | 1 472 MB/s (0.69) | 14 227 MB/s (0.41) |

### 메모리(PSS, 서버의 모든 프로세스): 유휴 → 부하 후

| 서버 | 머신 A | 머신 B | 머신 C |
|---|---:|---:|---:|
| lighttpd | 1 → 1 MB | 1 → 1 MB | 1 → 1 MB |
| nginx | 4 → 5 MB | 5 → 5 MB | 4 → 4 MB |
| Apache | 4 → 7 MB | 4 → 7 MB | 4 → 7 MB |
| omega-serv, Python 엔진 | 28 → 32 MB | 29 → 33 MB | 30 → 34 MB |
| **omega-serv, 네이티브 엔진** | **33 → 34 MB** | **34 → 35 MB** | **35 → 39 MB** |
| omega-serv, 네이티브 + WAF † | 45 → 47 MB | 43 → 44 MB | 44 → 48 MB |
| omega-serv, Python 엔진, 프로세스 2개 | 40 → 50 MB | 43 → 51 MB | 42 → 51 MB |
| omega-serv, 네이티브 + WAF, 보안 프로세스 2개 † | 45 → 47 MB | 43 → 44 MB | 55 → 57 MB |
| Caddy, 프로세스 2개 | 50 → 57 MB | 46 → 54 MB | 48 → 62 MB |

### 같은 코어 수: 머신 C, 프로세스 4개

11월 3일의 별도 세션, 같은 절차, 머신 C: 각 서버에 프로세스 4개(Caddy와 네이티브 엔진은 코어 4개)를 주었습니다. 기준: 프로세스 4개의 nginx. WAF를 켠 네이티브 엔진은 여기에 더 이상 나오지 않습니다. WAF 최적화 전에 측정했고 아직 프로세스 4개로 다시 측정하지 않았기 때문입니다.

| 서버 | 1 KB | 100 KB | 5 MB | 메모리 |
|---|---:|---:|---:|---:|
| lighttpd, 프로세스 4개 | 638 907 (**1.46**) | 312 402 (**1.21**) | 41 982 MB/s (0.93) | 1 → 2 MB |
| nginx, 프로세스 4개 | 438 496 (1.00) | 258 242 (1.00) | 45 162 MB/s (1.00) | 5 → 5 MB |
| **omega-serv, 네이티브 엔진** | **294 083–310 972 (0.67–0.71)** | **108 991–109 955 (0.42)** | **40 137–40 463 MB/s (0.89–0.90)** | **35 → 38 MB** |
| Apache, 프로세스 4개 | 200 592 (0.46) | 162 607 (0.63) | 39 664 MB/s (0.88) | 6 → 9 MB |
| Caddy, 코어 4개 | 97 085 (0.22) | 35 900 (0.14) | 5 998 MB/s (0.13) | 52 → 67 MB |
| omega-serv, Python 엔진, 프로세스 4개 | 37 697 (0.09) | 35 064 (0.14) | 37 123 MB/s (0.82) | 48 → 66 MB |

### 결론

- **네이티브 엔진은 omega-serv의 위치를 바꿉니다.**
  - 작은 파일에서 nginx의 0.03–0.11(Python 엔진)에서 약 **nginx의 0.7**로 올라가며, 어떤 머신에서도 같습니다.
  - Apache와 Caddy보다 앞서고, 여전히 가장 빠른 nginx와 lighttpd보다는 뒤입니다.
  - p99 지연 시간은 nginx에 가깝습니다.
- **lighttpd는 작은 파일과 중간 크기 파일에서 가장 빠르며**, 세 머신 모두에서 그렇고, 메모리도 가장 적게 씁니다. 다만 같은 프로세스 수로 비교하기 위해 사용한 `server.max-worker`(여러 프로세스)는 그 문서에서 권장하지 않습니다.
- **중간 크기 파일은 네이티브 엔진의 현재 약점입니다**: nginx의 0.28–0.61로 Apache보다 뒤이며, 코어를 늘려도 나아지지 않습니다. 이미 파악된 개선 과제입니다.
- **큰 파일에서는** 데이터를 시스템 커널이 복사하므로(`sendfile`) 서버 간 차이가 줄어듭니다. 예외는 머신 C의 Caddy이며, 기본 설정의 최적화는 시도하지 않았습니다.
- **WAF는 네이티브 엔진에 비용이 적지만, 정직하게 읽어야 합니다.**
  - 네이티브 엔진은 WAF 규칙을 직접 검사합니다. 어떤 규칙에도 일치하지 않는 요청은 Python 없이 응답합니다. 조금이라도 의심스러우면(일치, ASCII가 아닌 텍스트, Active Defense가 감시하는 출처, 인증 구역 등) Python이 결정합니다. 그 결과 WAF를 켜도 네이티브 엔진은 작은 파일에서 처리량의 78–95 %, 100 KB 파일에서 93–99 %를 유지합니다. 이 최적화 전에는 처리량이 1/4에서 1/7로 줄었습니다.
  - 속도 제한은 네이티브 엔진이 셉니다. 켜도 이 수치는 변하지 않습니다(머신 A: 켰을 때 11 391 req/s, 껐을 때 11 330). magnet을 켜면 모든 요청이 계속 Python을 거치며 비용은 이전 수준으로 돌아갑니다.
  - WAF를 켠 omega-serv는 WAF가 **없는** Apache와 Caddy보다 여전히 앞섭니다.
  - nginx, lighttpd, Apache, Caddy는 WAF **없이** 측정했습니다. 이 서버들에 WAF(ModSecurity, Coraza)를 더하면 그것에도 비용이 있지만, 측정하지 않았습니다. 따라서 "WAF 포함" 비교는 동등하지 않으며, WAF를 갖춘 다른 서버보다 omega-serv가 빠르다고 주장하지 않습니다.
- **여러 보안 프로세스는 일반 트래픽에는 더 이상 도움이 되지 않습니다**: 일반 트래픽은 더 이상 그곳을 거치지 않으며, 프로세스 2개에서도 처리량은 그대로입니다(−2에서 −4 %, 측정 오차 범위). 많은 요청이 Python을 거칠 때(magnet 사용, 공격)에만 유용합니다. 모든 요청이 그곳을 거치던 최적화 전 측정에서는 보안 프로세스 2개가 WAF 포함 처리량을 코어 4개에서 1.5–1.7배로 늘렸지만, 코어 2개에서는 5–12 % 향상에 그쳤습니다.
- **Python 엔진은 프로세스 수에 따라 확장됩니다**(프로세스 2개에서 ×1.6–×2, 4개에서 약 ×3.5). 하지만 nginx의 5–11 %에 머뭅니다.
- **메모리**: omega-serv는 nginx, lighttpd, Apache보다 수십 MB를 더 쓰며, 주로 Python 때문이고, Caddy와 비슷합니다. WAF 없는 네이티브 엔진에서는 부하 중에도 메모리가 거의 변하지 않습니다.
- **이 수치를 가늠하자면**: 가장 느린 경우인 머신 B의 WAF 포함 Python 엔진(564 req/s)도 하루 약 5천만 건의 요청에 해당합니다. 개인 사이트, 내부 서비스, 실험실의 요구를 훨씬 넘어섭니다. 속도가 정말로 결정적인 것은 트래픽이 많은 사이트뿐입니다.

---

## 5. omega-serv 버전: 1.0 → 2.0 → 2.5

세 버전을 §4와 같은 세션에서, 세 머신 모두에서, 같은 절차로 측정했습니다. 괄호 안은 같은 세션의 nginx(프로세스 2개)와의 비율입니다. †: WAF 최적화 후 11월 4일 세션(§4 참조).

### 작은 파일(1 KB): 초당 요청 수

| 버전과 모드 | 머신 A | 머신 B | 머신 C |
|---|---:|---:|---:|
| 1.0.0 | 1 547 (0.07) | 645 (0.03) | 8 870 (0.04) |
| 1.0.0 + WAF | 1 453 (0.07) | 561 (0.02) | 7 687 (0.03) |
| 2.0.0 | 1 740 (0.08) | 650 (0.03) | 10 245 (0.04) |
| 2.0.0 + WAF | 1 456 (0.07) | 565 (0.02) | 8 371 (0.03) |
| 2.0.0, 프로세스 2개 | 2 153 (0.10) | 1 277 (0.05) | 19 192 (0.08) |
| 2.0.0 + WAF, 프로세스 2개 | 1 775 (0.08) | 1 113 (0.05) | 15 351 (0.06) |
| 2.5, Python 엔진 | 1 507 (0.07) | 663 (0.03) | 10 553 (0.04) |
| 2.5, Python 엔진 + WAF | 1 561 (0.07) | 564 (0.02) | 8 365 (0.03) |
| 2.5, Python 엔진, 프로세스 2개 | 2 354 (0.11) | 1 312 (0.05) | 19 911 (0.08) |
| 2.5, Python 엔진 + WAF, 프로세스 2개 | 1 901 (0.09) | 1 104 (0.04) | 15 783 (0.06) |
| **2.5, 네이티브 엔진** | **15 222 (0.70)** | **16 542 (0.67)** | **285 213 (1.15)** |
| **2.5, 네이티브 엔진 + WAF †** | **11 990 (0.56)** | **12 998 (0.53)** | **264 484 (1.07)** |
| **2.5, 네이티브 엔진 + WAF, 보안 프로세스 2개 †** | **11 746 (0.55)** | **12 718 (0.52)** | **253 527 (1.02)** |

### 중간 크기 파일, 큰 파일, 메모리(프로세스 1개, WAF 없음)

| 버전 | 100 KB, req/s (A / B / C) | 5 MB, MB/s (A / B / C) | 유휴 메모리 → 부하 후 (A / B / C) |
|---|---|---|---|
| 1.0.0 | 1 071 / 563 / 7 625 | 578 / 549 / 3 640 | 21 → **98** / 22 → **98** / 23 → **73** MB |
| 2.0.0 | 1 570 / 603 / 9 469 | 1 665 / 1 470 / 14 058 | 26 → 30 / 27 → 31 / 28 → 32 MB |
| 2.5, Python 엔진 | 1 329 / 611 / 9 805 | 1 686 / 1 472 / 14 227 | 28 → 32 / 29 → 33 / 30 → 34 MB |
| **2.5, 네이티브 엔진** | **4 738 / 3 115 / 96 277** | **2 294 / 1 936 / 37 918** | **33 → 34 / 34 → 35 / 35 → 39 MB** |

### 대용량 동시 다운로드

테스트: 300 MB 파일을 동시에 3개 다운로드하는 동안 작은 페이지를 계속 요청합니다. 버전별, 머신별로 2회 실행했으며 결과는 거의 같았습니다. 여기서 메모리는 원래 테스트와 같이 서버의 모든 프로세스의 **RSS**입니다. 공유 메모리를 여러 번 세므로 다른 표의 PSS보다 큰 값이 나옵니다.

| 버전 | 최대 메모리 | 작은 페이지, 최악의 경우: A / B / C |
|---|---:|---|
| 1.0.0 | **1 833–1 836 MB** | **1.4–1.9 s** / **1.4–1.7 s** / 0.16 s |
| 2.0.0 | 39–42 MB | 3 ms / 4–6 ms / 1 ms |
| 2.5, Python 엔진 | 41–44 MB | 2 ms / 4 ms / 1 ms |
| 2.5, 네이티브 엔진 | 49–55 MB | 1–2 ms / 2–4 ms / 미만 1 ms |

### 능동 방어의 비용(1.0 → 2.0)

2026년 10월 26일 머신 A에서 측정했으며 이후 다시 측정하지 않았습니다: 의심스러운 요청마다 Active Defense가 위협을 한 번 기록하는 비용을 디스크(ext4)에서 2 000회 기록으로 측정했습니다.

| 측정 | 1.0.0 | 2.0.0 |
|---|---:|---:|
| 중앙값 | 2.84 ms | 0.23 ms |
| p99 | 11.6 ms | 2.3 ms |
| 최댓값 | 18–20 ms | 37–46 ms |

중앙값은 12분의 1로 줄어듭니다. 반대로 최댓값은 2.0에서 더 높습니다. SQLite 저널을 주기적으로 디스크에 쓰면서 생기는 몇 개의 고립된 최고치입니다.

### 결론

- **1.0에서 2.0으로의 발전**은 작은 페이지의 속도가 아니라 메모리와 큰 파일에 있습니다:
  - 부하 후 메모리가 73–98 MB에서 30–32 MB로 감소;
  - 대용량 다운로드 중에는 1.8 GB 이상에서 약 40 MB로 줄고, 서버는 응답성을 유지(거의 2초가 아니라 몇 밀리초);
  - 큰 파일의 처리량이 2.7–3.9배 증가;
  - 2.0은 여러 프로세스를 추가해, 머신에 따라 작은 페이지의 처리량을 25 %에서 거의 100 %까지 높입니다.
  1.0은 전송 전에 각 파일 전체를 메모리에 읽어 들였습니다. 2.0은 블록 단위로 보내거나 시스템 커널에 맡깁니다.
- **2.0에서 2.5로 Python 엔진의 속도는 변하지 않습니다**: 머신 B와 C에서는 차이가 4 % 미만이고, 백그라운드 부하에 가장 민감한 머신 A에서는 측정 오차 범위(−13 %에서 +9 %)입니다. 2.5의 이득은 모두 **네이티브 엔진**에서 나옵니다: 작은 파일에서 Python 엔진 대비 약 ×10–×27, 지연 시간은 5분의 1에서 15분의 1.
- **네이티브 엔진은 유휴 시 Python 엔진보다 약 5 MB를 더 씁니다**(PSS): 두 번째 프로그램의 대가입니다. WAF를 켜면 약 8 MB를 더 씁니다: 네이티브 엔진에 로드된 규칙입니다.

### 네이티브 엔진에 대해 알아 둘 점

- **선택 사항**입니다: Python 엔진이 계속 기본 엔진이자 대체 엔진입니다.
- 정적 콘텐츠, 리디렉션, 재작성, 별칭, 캐시, 오류 페이지, 보안 헤더, TLS를 직접 처리합니다.
- WAF 규칙을 직접 검사하고, 어떤 규칙에도 일치하지 않는 요청에 직접 응답합니다. 그 밖의 모든 요청(WAF 일치 또는 의심, Active Defense, 인증)은 Python이 결정하며, 검사와 로그는 완전히 같습니다. 설정 가능한 점검이 깨끗한 요청 N개 중 하나를 Python에도 넘겨, 둘이 같은 판정을 내리는지 확인합니다.
- 디렉터리 목록과 내부 페이지는 Python에 요청하고, 리버스 프록시, FastCGI, 파일 업로드, WebSocket은 연결 전체를 Python에 넘깁니다. 따라서 이 기능들은 Python 엔진의 속도를 유지합니다.
- 직접 TLS에서는 리버스 프록시, FastCGI, 파일 업로드를 네이티브 엔진이 지원하지 않습니다. 이때는 Python 엔진이 제공하며, 인터페이스에 그렇게 표시됩니다.
- glibc 2.38 이상과 OpenSSL 3이 필요합니다. 시작할 수 없으면 설치 과정에서 그 자리에서 다시 컴파일하며, 그것도 불가능하면 omega-serv는 Python 엔진으로 계속 동작합니다.

---

## 6. 기능 비교

범례:
- ✅ 내장;
- 🧩 프로젝트의 공식 모듈, 활성화 또는 설치 필요;
- 🔌 서드파티 모듈 또는 플러그인;
- ⚙️ 외부 도구를 통해;
- ❌ 없음.

"Commercial"은 유료 에디션에서만 제공되는 기능을 뜻합니다.

### HTTP 서비스

| 기능 | nginx | lighttpd | Caddy | Apache | Traefik | omega-serv 2.5 |
|---|---|---|---|---|---|---|
| 서버 언어 | C | C | Go | C | Go | Python, 선택적 C++ 네이티브 엔진 |
| 정적 파일 제공 | ✅ | ✅ | ✅ | ✅ | ❌ (프록시 전용) | ✅ |
| ETag / 304 / Range | ✅ | ✅ | ✅ | ✅ | — | ✅ |
| 미리 압축된 파일 `.gz` / `.br` | ✅ `gzip_static` (`.br`: 🔌) | 🔌 Lua 스크립트 (mod_magnet) | ✅ `precompressed` | 🧩 mod_rewrite 레시피 | — | ✅ |
| 실시간 압축 | ✅ | ✅ mod_deflate | ✅ | 🧩 mod_deflate | ✅ middleware | ❌ |
| HTTP/2 | ✅ | ✅ | ✅ | 🧩 mod_http2 | ✅ | ❌ |
| HTTP/3 (QUIC) | ✅ | ❌ | ✅ | ❌ | ✅ | ❌ |
| FastCGI를 통한 PHP | ✅ | ✅ | ✅ | ✅ | ❌ | ✅ |
| 여러 프로세스 또는 코어 | ✅ workers | ⚠️ `max-worker`, 문서에서 비권장 | ✅ (Go, 모든 코어) | ✅ MPM | ✅ (Go) | ✅ `server.workers`; 네이티브 엔진: 모든 코어 |

### 리버스 프록시

| 기능 | nginx | lighttpd | Caddy | Apache | Traefik | omega-serv 2.5 |
|---|---|---|---|---|---|---|
| 부하 분산 | ✅ 라운드 로빈, 최소 연결, 해시 | ✅ fair, round-robin, hash, sticky | ✅ 십여 가지 전략 | 🧩 mod_proxy_balancer | ✅ wrr, p2c, hrw, least-time | ✅ 실제 부하를 포함한 7가지 전략 |
| 수동 점검(고장 서버 제외) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| 능동 점검(주기적 프로브) | Commercial (NGINX Plus) | ❌ | ✅ | 🧩 mod_proxy_hcheck | ✅ | ✅ |
| 응답 캐시 | ✅ `proxy_cache` | ❌ | 🔌 | 🧩 mod_cache | Commercial | ✅ |
| WebSocket | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| 서비스 검색(Docker, Kubernetes) | 🔌 | ❌ | 🔌 | ❌ | ✅ (프로젝트의 핵심) | ❌ |

### TLS

| 기능 | nginx | lighttpd | Caddy | Apache | Traefik | omega-serv 2.5 |
|---|---|---|---|---|---|---|
| 자동 인증서(ACME, Let's Encrypt) | 🧩 `ngx_http_acme_module` | ⚙️ Certbot | ✅ 기본값 | 🧩 mod_md | ✅ | ⚙️ Certbot, 내장 마법사와 예약 갱신 포함 |
| 로컬 CA | ❌ | ❌ | ✅ 내부 CA(자동 발급) | ❌ | ❌ | ✅ 생성, CSR 서명, 폐기 |

### 보안

| 기능 | nginx | lighttpd | Caddy | Apache | Traefik | omega-serv 2.5 |
|---|---|---|---|---|---|---|
| 클라이언트별 속도 제한 | ✅ `limit_req` | ⚠️ mod_evasive (동시 연결만) | 🔌 caddy-ratelimit | 🔌 mod_evasive, mod_qos | ✅ middleware | ✅ |
| 프로세스 간 공유되는 제한 | ✅ 공유 메모리 영역 | ❌ 프로세스별 계산 | — (단일 프로세스) | 모듈에 따라 다름 | 인스턴스 1개; 여러 개는 Redis로 | ✅ 공유 메모리 |
| WAF(SQLi/XSS 시그니처, 스캐너 등) | 🔌 ModSecurity, Commercial (App Protect) | ❌ (Lua 스크립트 직접 작성) | 🔌 Coraza | 🔌 ModSecurity | 🔌 플러그인 | ✅ 내장 |
| 만료 기간이 있는 차단 목록, 재발 횟수 | ⚙️ fail2ban | ⚙️ fail2ban | ⚙️ fail2ban | ⚙️ fail2ban | ⚙️ | ✅ 내장 |
| 미끼, 전시 모드, 사고, IoC 내보내기 | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ Active Defense |
| 시간에 따라 단계적으로 늘어나는 차단 | ⚙️ fail2ban | ⚙️ fail2ban | ⚙️ fail2ban | ⚙️ fail2ban | ⚙️ | ✅ RIPOSTE |
| 설정 보안 감사 | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ `audit security` |
| 관찰 모드(차단 없이 기록) | 모듈에 따라 다름 | — | 플러그인에 따라 다름 | ✅ ModSecurity `DetectionOnly` | 플러그인에 따라 다름 | ✅ |

단계적 차단: 다시 돌아오는 주소에 대해 몇 주에 걸쳐 로컬 또는 네트워크 수준에서 점점 길어지는 차단을 적용하는 것입니다. fail2ban은 `bantime.increment` 옵션으로 이를 제공합니다. RIPOSTE는 여기에 로그로 측정하고 켜기 전에 시뮬레이션할 수 있는 정책, 조치 해제, 비상 정지를 더합니다.

### 확장성

| 기능 | nginx | lighttpd | Caddy | Apache | Traefik | omega-serv 2.5 |
|---|---|---|---|---|---|---|
| 스크립트 언어 | 🧩 njs (JavaScript); 🔌 Lua (OpenResty) | ✅ Lua (mod_magnet) | Go 모듈(재컴파일) | 🧩 mod_lua | Go 또는 WebAssembly 플러그인 | 🔌 mod_magnet 스크립트 가져오기(`magnet` 옵션) |
| 모듈 생태계 | 매우 큼 | 특화됨 | 큼 | 매우 큼 | 큼 | 없음: 모두 내장 |

---

## 7. 관리와 편의성

| 서버 | 주요 관리 방식 | 인터페이스 | 중단 없는 다시 불러오기 |
|---|---|---|---|
| nginx | 설정 파일 | 없음(대시보드: NGINX Plus, 상용) | ✅ `nginx -s reload` |
| lighttpd | 설정 파일 | 없음(mod_status 읽기 전용) | ✅ 부드러운 재시작 |
| Caddy | Caddyfile 또는 JSON | REST 관리 API | ✅ API를 통해 |
| Apache | 설정 파일과 `.htaccess` | 없음(mod_status 읽기 전용) | ✅ `graceful` |
| Traefik | 컨테이너 레이블, 파일 또는 Kubernetes | 웹 대시보드(읽기 전용) | ✅ 동적 설정 |
| omega-serv | 터미널 인터페이스(TUI)와 명령줄(CLI); JSON 파일 편집 불필요 | **키보드와 마우스로 쓰는 완전한 TUI, 17개 언어, 내장 도움말** | ✅ 대부분의 설정; 포트, TLS, 엔진, 프로세스 수는 재시작 필요를 알림 |

실제로 omega-serv는 설정, 보안, 로그, 시스템 서비스, 백업, 인스턴스를 하나의 인터페이스에서 관리합니다. 각 설정에는 설명이 있고, 쓰기 전에 검증됩니다. 다른 서버에서는 텍스트 파일을 편집한 다음 별도의 도구(Certbot, fail2ban, logrotate, ModSecurity, 모니터링 도구 등)를 사용합니다.

반면 nginx, Apache, Caddy의 "설정 파일" 방식은 자동화에 매우 적합합니다(Ansible, 컨테이너, 버전 관리). omega-serv에도 스크립트용 CLI가 있지만, 자동화 생태계는 아직 제한적입니다.

---

## 8. omega-serv가 더 제공하는 것

이 절에는 비교한 어떤 서버도 서드파티 모듈이나 외부 도구 없이는 이런 형태로 제공하지 않는 것만 담았습니다.

1. **터미널 인터페이스에서의 완전한 관리.**
   - 인터페이스는 서버 전체를 다룹니다: 사이트, 보안, 로그, 서비스, 백업, 인스턴스.
   - 키보드와 마우스로 사용할 수 있으며, 그래픽 환경이 없는 서버에서도, SSH를 통해서도 쓸 수 있습니다.
   - 17개 언어로 제공되며 각 설정을 설명합니다.
   - 다른 서버에는 관리 인터페이스가 없거나(nginx, lighttpd, Apache), API(Caddy) 또는 읽기 전용 대시보드(Traefik)만 있습니다.
2. **모듈을 조립할 필요 없는 내장 능동 보안.**
   - WAF에는 시그니처, 편집 가능한 경로 목록, 재발 횟수, 만료 기간이 있는 차단 목록, 평판, 관찰 모드가 포함됩니다.
   - Active Defense는 미끼, 전시 모드, 사고 추적, 침해 지표 내보내기, 영향 없는 시뮬레이션을 더합니다.
   - RIPOSTE는 시간에 따라 대응합니다: 다시 돌아오는 주소를 기억하고 단계적 대응을 적용합니다. 점점 길어지는 차단(기본값 1시간, 6시간, 24시간, 7일)을 차단 목록에서 로컬로, 또는 fail2ban(omega-jail)을 통해 네트워크 수준에서 적용하거나, 미끼를 연장합니다. 각 정책은 실제 로그로 측정하고 켜기 전에 시뮬레이션할 수 있으며, 각 조치는 항상 보이고 해제할 수 있고, 비상 정지도 있습니다.
   - 다른 서버에서는 이런 기능을 위해 ModSecurity 또는 Coraza, 규칙 세트, fail2ban을 조합해야 합니다.
3. **여러 프로세스에서도 정확한 보안 제한.**
   - 여러 프로세스에서 속도 제한과 WAF 재발 횟수가 메모리에서 공유됩니다. 따라서 공격자가 프로세스 수만큼 자신의 한도를 늘릴 수 없습니다.
   - lighttpd는 반대 경우를 문서화하고 있습니다: `server.max-worker`를 쓰면 `mod_evasive`와 `mod_status`가 프로세스마다 따로 셉니다.
   - nginx도 카운터(`limit_req` 영역)를 공유하지만 내장 WAF는 없습니다.
4. **두 엔진, 하나의 동작.** 네이티브 엔진과 Python 엔진은 같은 응답과 같은 로그를 만들며, 이는 비교 테스트 벤치에서 자동으로 검증됩니다. 로그를 읽는 도구(예: fail2ban)는 아무 차이도 보지 못합니다.
5. **lighttpd mod_magnet 스크립트 가져오기.**
   - lighttpd용으로 이미 작성한 Lua 보호 스크립트를 다시 쓰지 않고 가져올 수 있습니다.
   - 내장 보호를 보완하되 결코 약화시킬 수 없으며, 호환성은 켜기 전에 확인됩니다.
6. **여러 인스턴스 관리.**
   - 레지스트리가 모든 인스턴스를 기록하고, 인터페이스에서 인스턴스 사이를 전환합니다.
   - 인스턴스를 완전히 제거할 수도 있습니다.
7. **설정 보안 감사**: `audit security` 명령은 정보 제공용으로, 결코 차단하지 않으며 스크립트에서 쓸 수 있는 종료 코드를 반환합니다.
8. **원격 로그 소스.**
   - 인터페이스가 다른 서버의 로그를 SSH로, 필요할 때, 비밀번호를 저장하지 않고 가져옵니다.
   - 이를 lnav에서 로컬 로그와 합쳐 읽을 수 있습니다.
9. **끌 수 없는 HTTP 강화**: 설치 직후부터, 어떤 프로필과 엔진에서든 적용됩니다.
   - Host 헤더의 엄격한 검증;
   - Content-Length / Transfer-Encoding 모호성 거부;
   - 사이트 응답(오류 페이지 포함)의 보안 헤더와 CSP;
   - X-Forwarded-For의 안전한 읽기;
   - root로 시작하는 것을 거부.

---

## 9. 다른 서버가 더 잘하는 것

- **처리량**: lighttpd와 nginx는 작은 파일과 중간 크기 파일에서 여전히 가장 빠르며, 세 머신 모두에서 그렇습니다. 네이티브 엔진으로도 omega-serv는 작은 파일에서 nginx의 약 0.7, lighttpd의 약 0.5, 100 KB 파일에서 nginx의 0.3–0.6입니다. 트래픽이 많은 사이트, 공개 API, CDN에는 이들을 선택해야 합니다.
- **중간 크기 파일**: Apache는 100 KB 파일을 세 머신 모두에서 omega-serv의 네이티브 엔진보다 빠르게 제공합니다.
- **메모리**: lighttpd(1 MB), nginx(4–5 MB), Apache(4–9 MB)는 매우 제약이 많은 머신(임베디드 시스템, 작은 컨테이너)에 알맞습니다. omega-serv에는 30–65가 필요합니다.
- **보안의 비용**: WAF에는 여전히 비용이 있습니다. 네이티브 엔진에서는 속도 제한을 포함해 작은 파일의 처리량이 5–22 % 줄어듭니다: WAF를 켠 omega-serv는 머신 A와 B에서 WAF 없는 nginx의 0.53–0.56입니다. 의심스럽거나 판단이 애매한 요청(규칙 일치, ASCII가 아닌 텍스트, Active Defense가 감시하는 출처)은 항상 Python을 거치며 Python 엔진의 속도로 제공됩니다. magnet을 켜면 모든 요청이 Python을 거치고, 최적화 전과 마찬가지로 WAF가 네이티브 엔진의 처리량을 1/4에서 1/7로 줄입니다.
- **프로토콜**: HTTP/2는 다른 모든 서버가, HTTP/3은 nginx, Caddy, Traefik이 지원합니다. omega-serv는 HTTP/1.1만 지원합니다.
- **자동 HTTPS**: Caddy와 Traefik은 기본으로 켜져 있고, nginx(`ngx_http_acme_module`)와 Apache(`mod_md`)는 공식 모듈로 제공합니다. omega-serv는 이를 Certbot에 맡기며, 마법사와 예약 갱신을 갖추고 있습니다.
- **컨테이너 환경**: Traefik의 자동 서비스 검색(Docker, Kubernetes)에 해당하는 기능이 omega-serv에는 없습니다.
- **생태계와 성숙도**: nginx와 Apache는 수천 개의 모듈, 가이드, 연동과 수십 년의 운영 경험을 제공합니다. Caddy는 Go 모듈 시스템을 제공합니다. omega-serv는 한 사람이 유지하는 젊은 프로젝트이며, 네이티브 엔진은 아직 매우 새롭습니다.
- **실시간 압축**: omega-serv는 이미 압축된 파일만 제공합니다.

---

## 10. 어떤 용도에 어떤 서버를

| 용도 | 권장 선택 |
|---|---|
| 트래픽이 많은 사이트, 공개 API, CDN, 최대 처리량 | **nginx** 또는 **lighttpd** |
| 매우 제약이 많은 머신, 임베디드 시스템, 정적 파일 | **lighttpd** |
| 자동 HTTPS로 빠르게 시작, 짧은 설정 | **Caddy** |
| 오래된 PHP 애플리케이션, `.htaccess`, 공유 호스팅 | **Apache** |
| Docker, Kubernetes, 마이크로서비스 | **Traefik** |
| 중소 규모 사이트, 내부 서비스, 실험실, VPN, 파일을 편집하지 않는 관리 | **omega-serv**(가능하면 네이티브 엔진) |
| 인터넷에 노출된 서버로, 보안(WAF, 단계적 차단, 미끼)을 하나의 인터페이스에서 보고 제어하고 싶은 경우 | **omega-serv** |
| 부하 분산, 점검, 캐시를 갖추고 인터페이스에서 관리하는 내부 리버스 프록시 | **omega-serv** |
| HTTP 강화와 능동 방어 학습 | **omega-serv** |

이 도구들은 함께 쓸 수도 있습니다. 예를 들어:
- 인터넷 쪽에 nginx 또는 Traefik을 두고, 그 뒤에서 omega-serv가 내부 서비스와 그 보안, 관리를 맡는 구성;
- 여러 애플리케이션 서버 앞에서 omega-serv를 내부 리버스 프록시로 쓰는 구성.

---

## 11. 측정 재현

도구는 저장소의 `tools/bench/`에 포함되어 있습니다. nginx, lighttpd, Apache, Caddy, oha 설치, omega-serv 개발 환경(`.venv`), 그리고 네이티브 엔진의 경우 `native/omega-http-core/build-release`에 컴파일한 바이너리가 필요합니다.

```sh
# 1. 측정 폴더 준비(테스트 파일, 설정, omega-serv 1.0, 2.0, 현재 버전)
tools/bench/compare/setup.sh /path/measures omega-serv-1.0.0.tar.gz omega-serv-2.0.0.tar.gz

# 2. 설정 21개, 번갈아 3회 반복(40–60분)
#    SRV_CPUS / CLI_CPUS: 서버와 클라이언트의 코어(lscpu -e로 토폴로지 확인)
SRV_CPUS=0,1 CLI_CPUS=2,3 tools/bench/compare/campaign.sh /path/measures > results.txt

# 3. 중앙값
python3 tools/bench/compare/summarize.py results.txt

# 다른 설정 목록, 예: 프로세스 4개
CONFIGS="nginx-4 lighttpd-4 caddy-4 apache-4 omega-v2-1-0-native omega-v2-4-1-native" \
  tools/bench/compare/campaign.sh /path/measures > results-4.txt

# 대용량 다운로드(메모리와 응답성): 현재 버전의 Python 엔진, 이어서 네이티브, 이어서 1.0
.venv/bin/python tools/bench/bigfile.py
BENCH_ENGINE=native .venv/bin/python tools/bench/bigfile.py
BENCH_SRC=/path/measures/v1-archive/omega-serv/src \
BENCH_EXTRA_PATH=/path/measures/v1-archive/omega-serv/vendor/omega-lib/src \
  .venv/bin/python tools/bench/bigfile.py

# 이미 실행 중인 다른 서버를 oha 없이 측정
python3 tools/bench/bench_any.py --make-files /srv/webroot-test
python3 tools/bench/bench_any.py --port 8080
```

설정 이름: `nginx-N`, `lighttpd-N`, `apache-N`, `caddy-N`(프로세스 N개, Caddy는 코어 N개); omega-serv는 `omega-vX-N-W`(버전 `v1`, `v20`, 현재 버전은 `v2`, 프로세스 N개, W = 0은 WAF 없음, 1은 WAF 있음), 네이티브 엔진은 접미사 `-native`.

직접 측정한 결과를 공개할 때는 머신, 버전, 코어 배분, 3회 반복을 명시해 주세요.

---

## 12. 출처

다른 서버의 기능은 각 공식 문서를 따릅니다(2026년 10월 26일 확인).

**nginx**
- [속도 제한 `limit_req`(공유 메모리 영역)](https://nginx.org/en/docs/http/ngx_http_limit_req_module.html)
- [미리 압축된 파일 `gzip_static`](https://nginx.org/en/docs/http/ngx_http_gzip_static_module.html)
- [공식 ACME 모듈 `ngx_http_acme_module`](https://nginx.org/en/docs/http/ngx_http_acme_module.html)
- [부하 분산(`upstream`)](https://nginx.org/en/docs/http/ngx_http_upstream_module.html)
- [HTTP/3](https://nginx.org/en/docs/http/ngx_http_v3_module.html)
- [nginx용 ModSecurity 커넥터](https://github.com/owasp-modsecurity/ModSecurity-nginx)

**lighttpd**
- [`server.max-worker`: 비권장, mod_status와 mod_evasive는 프로세스별 카운터](https://redmine.lighttpd.net/projects/lighttpd/wiki/Server_max-workerDetails)
- [mod_magnet(Lua 스크립트)](https://redmine.lighttpd.net/projects/lighttpd/wiki/Docs_ModMagnet)
- [mod_deflate(압축, 캐시)](https://redmine.lighttpd.net/projects/lighttpd/wiki/Mod_deflate)
- [mod_proxy(부하 분산, 수동 점검, WebSocket)](https://redmine.lighttpd.net/projects/lighttpd/wiki/Docs_ModProxy)
- [mod_evasive(한 주소의 동시 연결)](https://redmine.lighttpd.net/projects/lighttpd/wiki/Docs_ModEvasive)

**Caddy**
- [자동 HTTPS](https://caddyserver.com/docs/automatic-https)
- [`file_server`와 `precompressed`](https://caddyserver.com/docs/caddyfile/directives/file_server)
- [`reverse_proxy`(전략, 능동 및 수동 점검)](https://caddyserver.com/docs/caddyfile/directives/reverse_proxy)
- [관리 API](https://caddyserver.com/docs/api)
- [속도 제한 플러그인 caddy-ratelimit](https://github.com/mholt/caddy-ratelimit)
- [Caddy용 Coraza WAF](https://github.com/corazawaf/coraza-caddy)
- [caddy-docker-proxy](https://github.com/lucaslorentz/caddy-docker-proxy)

**Apache HTTP Server**
- [MPM event](https://httpd.apache.org/docs/2.4/mod/event.html)
- [mod_md(ACME)](https://httpd.apache.org/docs/2.4/mod/mod_md.html)
- [mod_proxy_balancer](https://httpd.apache.org/docs/2.4/mod/mod_proxy_balancer.html)
- [mod_proxy_hcheck](https://httpd.apache.org/docs/2.4/mod/mod_proxy_hcheck.html)
- [mod_http2](https://httpd.apache.org/docs/2.4/mod/mod_http2.html)
- [mod_deflate, 미리 압축된 콘텐츠](https://httpd.apache.org/docs/2.4/mod/mod_deflate.html)
- [ModSecurity](https://github.com/owasp-modsecurity/ModSecurity)

**Traefik**
- [`ratelimit` middleware(인스턴스별 메모리, Redis 선택)](https://doc.traefik.io/traefik/reference/routing-configuration/http/middlewares/ratelimit/)
- [ACME](https://doc.traefik.io/traefik/https/acme/)
- [Providers(Docker, Kubernetes 등)](https://doc.traefik.io/traefik/providers/overview/)

**fail2ban**
- [`jail.conf`: `bantime.increment`, `bantime.factor`, `bantime.multipliers`, `bantime.maxtime`(재범자에 대한 더 긴 차단)](https://github.com/fail2ban/fail2ban/blob/master/config/jail.conf)(2026년 11월 4일 확인)

**측정 도구**
- [oha](https://github.com/hatoo/oha)

---

*이 비교는 kraynux가 omega-serv 2.5를 위해 작성했습니다: 2026년 11월 3일과 4일 세 머신에서 측정(능동 방어: 2026년 10월 26일). 용량에 관한 결정을 내릴 때는 제공되는 도구로 직접 보유한 하드웨어에서 측정하세요.*
