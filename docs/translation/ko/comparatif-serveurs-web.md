<!-- Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE) -->

# 시장의 웹 서버와 비교한 omega-serv

**측정 기반 비교: nginx · lighttpd · Caddy · Apache · Traefik · omega-serv 2.0**

🌐 [Français](../../comparatif-serveurs-web.md) · [English](../en/comparatif-serveurs-web.md) · [Español](../es/comparatif-serveurs-web.md) · [Português (Brasil)](../pt-BR/comparatif-serveurs-web.md) · [Italiano](../it/comparatif-serveurs-web.md) · [Deutsch](../de/comparatif-serveurs-web.md) · [Nederlands](../nl/comparatif-serveurs-web.md) · [Polski](../pl/comparatif-serveurs-web.md) · [Русский](../ru/comparatif-serveurs-web.md) · [中文](../zh-CN/comparatif-serveurs-web.md) · [Tiếng Việt](../vi/comparatif-serveurs-web.md) · [ไทย](../th/comparatif-serveurs-web.md) · [Bahasa Indonesia](../id/comparatif-serveurs-web.md) · [日本語](../ja/comparatif-serveurs-web.md) · **한국어** · [हिन्दी](../hi/comparatif-serveurs-web.md) · [العربية](../ar/comparatif-serveurs-web.md)

이 문서는 가장 널리 쓰이는 웹 서버 가운데 omega-serv의 위치를 보여 줍니다. 「최고의 서버」를 가리려는 것이 아닙니다: 각 도구는 서로 다른 필요에 답합니다. 이 문서가 주는 것은 세 가지입니다:

1. 같은 머신에서, 같은 클라이언트와 같은 파일로 수행하여 재현할 수 있는 **실제 측정값**;
2. 각 서버의 공식 문서(문서 끝의 링크)에서 하나하나 확인한 **기능 비교** — 내장 기능과 모듈이나 플러그인이 필요한 기능을 구분합니다;
3. omega-serv가 **실제로 더 제공하는 것**과, 다른 서버가 **더 잘하는 것**.

아래의 모든 수치는 2026년 10월 26일에 측정했습니다. 다른 사이트에서 가져오거나 추정한 수치는 하나도 없습니다.

---

## 목차

1. [요약](#1-요약)
2. [측정 방법](#2-측정-방법)
3. [성능: nginx, lighttpd, Caddy와 비교한 omega-serv](#3-성능-nginx-lighttpd-caddy와-비교한-omega-serv)
4. [omega-serv 1.0 → 2.0: 바뀐 점, 측정 결과](#4-omega-serv-10--20-바뀐-점-측정-결과)
5. [기능 비교](#5-기능-비교)
6. [관리와 사용성](#6-관리와-사용성)
7. [omega-serv가 더 제공하는 것](#7-omega-serv가-더-제공하는-것)
8. [다른 서버가 더 잘하는 것](#8-다른-서버가-더-잘하는-것)
9. [용도별 서버 선택](#9-용도별-서버-선택)
10. [측정 재현하기](#10-측정-재현하기)
11. [출처](#11-출처)

---

## 1. 요약

- **작은 파일의 원시 처리량**: C로 작성된 nginx와 lighttpd는 Python으로 작성된 omega-serv보다 초당 **10~20배 많은** 요청을 처리합니다. Go로 작성된 Caddy는 그 사이에 있습니다. 이는 설정이 아니라 본질의 차이입니다: omega-serv는 이 영역을 목표로 하지 않습니다.
- **큰 파일**: 2.0부터 omega-serv는 전송을 커널(`sendfile`)에 맡깁니다. 그러면 이 머신에서 nginx, lighttpd, Caddy와 **같은 수준의 처리량**에 이릅니다: 2.1 GB/s 대 2.0~2.4 GB/s.
- **메모리**: lighttpd(1 MB)와 nginx(4~5 MB)는 여전히 따라잡을 수 없습니다. omega-serv는 프로세스 1개로 부하 상태에서 30 MB 미만, Caddy는 약 55 MB입니다.
- **1.0에서 2.0으로**: 큰 파일 처리량 2.8배; 대용량 다운로드 중 메모리 45분의 1; 프로세스 2개(boost 모드)로 작은 파일에서 최대 +50 %; Active Defense 비용 12분의 1.
- **omega-serv에만 있는 것**: 17개 언어로 된 터미널 인터페이스(TUI)의 완전한 관리; 내장 WAF와 능동 방어; 여러 프로세스에서도 정확한 보안 제한; lighttpd mod_magnet 스크립트 가져오기; 여러 인스턴스 관리.
- **없는 것**: HTTP/2와 HTTP/3, Docker/Kubernetes 서비스 검색, 내장 ACME 클라이언트(Certbot을 거침), C로 작성된 서버의 처리량.

---

## 2. 측정 방법

### 머신과 소프트웨어

| 항목 | 값 |
|---|---|
| 프로세서 | Intel Core i5 M480 2.67 GHz(2010년): 물리 코어 2개, 스레드 4개 |
| 메모리 | 8 GB |
| 시스템 | Manjaro Linux, 커널 6.18 |
| 네트워크 | 로컬 루프백(127.0.0.1) |
| 부하 클라이언트 | [oha](https://github.com/hatoo/oha) 1.16.0(Rust로 작성) |
| nginx | 1.30.4(Manjaro 패키지) |
| lighttpd | 1.4.85(Manjaro 패키지) |
| Caddy | 2.11.4(Manjaro 패키지) |
| omega-serv | 1.0.0(공개 아카이브)과 2.0.0, Python 3.14.7 |

Apache와 Traefik은 이 머신에 설치되어 있지 않아 측정하지 않았습니다. 게다가 Traefik은 파일 서버가 아닙니다(§5 참조). 따라서 이 두 서버는 기능 비교에만 나옵니다.

### 절차

- **프로세서 격리**: 각 서버는 물리 코어 0(스레드 0과 2)에, 클라이언트는 물리 코어 1(스레드 1과 3)에 고정했습니다. 그래서 클라이언트가 서버의 시간을 빼앗지 않으며, 모든 서버가 정확히 같은 자원을 씁니다.
- **모두에게 같은 파일**: `small.html`(1 KB), `medium.png`(100 KB), `large.bin`(5 MB)을 같은 폴더에서 제공합니다.
- **모든 서버에서 접근 로그 활성화** — 운영 중인 서버는 로그를 남기기 때문입니다.
- **평문 HTTP/1.1, 지속 연결(keep-alive)**. 동시 연결 수는 1 KB와 100 KB 파일에서 32, 5 MB 파일에서 8입니다.
- **시간**: 파일별, 구성별 10초.
- **반복**: 교차 진행한 완전한 3회(1회차에 모든 서버, 그다음 2회차에 모든 서버 등). 표에는 세 회차의 **중앙값**을 적었습니다.
- **메모리**: 서버의 모든 프로세스의 PSS(*Proportional Set Size*) 합계. RSS와 달리 프로세스 사이에 공유되는 페이지는 한 번만 셉니다. 유휴 상태에서, 그리고 부하 후에 측정합니다.
- **구성**: nginx, lighttpd, Caddy는 기본 구성(정적 파일, 접근 로그). omega-serv는 `standard` 프로필을 쓰며, WAF를 끈 상태와 제공되는 모든 규칙으로 켠 상태를 측정했습니다.
- **프로세스 수**: 각 서버를 프로세스 1개와 2개로 측정했습니다(nginx `worker_processes`, lighttpd `server.max-worker`, Caddy `GOMAXPROCS`, omega-serv `server.workers`).

### 알아 둘 한계

- **소박하고 오래된 머신.** 최신 서버에서는 절댓값이 훨씬 높을 것입니다. 의미 있는 것은 같은 세션에서 측정한 서버 사이의 **비율**입니다.
- **세션 간 변동**: 머신의 배경 부하에 따라 약 10~30 %. 같은 세션의 회차끼리는 일관됩니다: omega-serv와 Caddy는 5 % 미만의 차이, nginx와 lighttpd는 더 큰데, 처리량이 매우 높아 머신의 나머지에 더 민감하기 때문입니다.
- **로컬 루프백**: 측정은 실제 네트워크를 거치지 않습니다. 실제 네트워크에서는 큰 파일의 처리량이 거의 언제나 서버가 아니라 대역폭에 의해 제한됩니다.
- 이 측정에는 **TLS 없음**. HTTPS에서는 omega-serv가 `sendfile`을 쓸 수 없어 파일을 블록 단위로 보냅니다.
- **원시 수치**: 이 문서와 함께 [`docs/benchmarks/2026-10-26-campagne-brute.txt`](../../benchmarks/2026-10-26-campagne-brute.txt)에 공개되어 있습니다.

---

## 3. 성능: nginx, lighttpd, Caddy와 비교한 omega-serv

### 작은 파일(1 KB): 초당 요청 수

| 서버 | 프로세스 1개 | 프로세스 2개 | p99 지연(프로세스 1개) |
|---|---:|---:|---:|
| lighttpd 1.4.85 | 25 521 | 29 700 | 4.5 ms |
| nginx 1.30.4 | 14 054 | 18 315 | 4.7 ms |
| Caddy 2.11.4 | 3 697 | 5 345 | 25.3 ms |
| **omega-serv 2.0** | **1 358** | **1 953** | **37.5 ms** |
| omega-serv 2.0 + WAF | 1 130 | 1 617 | 48.5 ms |
| omega-serv 1.0 | 1 304 | — | 41.2 ms |

### 중간 파일(100 KB): 초당 요청 수

| 서버 | 프로세스 1개 | 프로세스 2개 |
|---|---:|---:|
| lighttpd | 11 635 | 13 037 |
| nginx | 8 024 | 9 555 |
| Caddy | 3 280 | 4 344 |
| **omega-serv 2.0** | **1 247** | **1 629** |
| omega-serv 2.0 + WAF | 1 012 | 1 347 |
| omega-serv 1.0 | 1 064 | — |

### 큰 파일(5 MB): 처리량

| 서버 | 프로세스 1개 | 프로세스 2개 |
|---|---:|---:|
| lighttpd | 2 379 MB/s | 2 407 MB/s |
| nginx | 2 242 MB/s | 1 981 MB/s |
| Caddy | 2 165 MB/s | 2 229 MB/s |
| **omega-serv 2.0** | **1 658 MB/s** | **2 115 MB/s** |
| omega-serv 1.0 | 584 MB/s | — |

### 메모리(PSS, 서버의 모든 프로세스)

| 서버 | 유휴 | 부하 후 |
|---|---:|---:|
| lighttpd(프로세스 1개 또는 2개) | 1 MB | 1 MB |
| nginx(프로세스 1개 또는 2개) | 4~5 MB | 4~5 MB |
| **omega-serv 2.0(프로세스 1개)** | **26 MB** | **30 MB** |
| omega-serv 2.0(프로세스 2개) | 39 MB | 48 MB |
| Caddy | 50 MB | 56 MB |
| omega-serv 1.0 | 22 MB | 100 MB |

### 해석

- **작은 파일과 중간 파일에서는** nginx, lighttpd와의 차이가 한 자릿수 규모(×10~×20)입니다. Python으로 작성된 서버의 비용입니다: 모든 요청이 인터프리터를 거치지만, nginx와 lighttpd는 컴파일된 C로 처리합니다. boost 모드는 차이를 줄이지만 메우지는 못합니다.
- **큰 파일에서는** 서버들이 비슷해집니다. 데이터를 복사하는 것이 커널(`sendfile`)이기 때문입니다. 프로세스 2개로 omega-serv 2.0은 2.1 GB/s에 이르며, 다른 서버들(2.0~2.4 GB/s)과 같은 범위입니다.
- **omega-serv의 WAF는 작은 파일에서 약 17 %의 비용**이 듭니다: 모든 요청을 검사합니다. nginx, lighttpd, Caddy는 WAF 없이 측정했습니다. 이 서버들에 WAF(ModSecurity, Coraza)를 더해도 비용이 들며, 여기서는 측정하지 않았습니다.
- **이 수치의 규모를 가늠하면**: 초당 1,300 요청은 이 2010년 머신에서 하루 1억 1천만 요청이 넘습니다. 개인 사이트, 내부 서비스, 실습 환경 — omega-serv가 목표로 하는 용도 — 의 필요를 훨씬 넘어섭니다.

---

## 4. omega-serv 1.0 → 2.0: 바뀐 점, 측정 결과

### 성능

두 버전은 같은 세션에서, 같은 머신과 같은 절차로 측정했습니다.

| 측정 | 1.0.0 | 2.0.0 | 변화 |
|---|---:|---:|---:|
| 작은 파일(1 KB), 프로세스 1개 | 1 304 req/s | 1 358 req/s | +4 % |
| 작은 파일(1 KB), boost 모드 프로세스 2개 | — | 1 953 req/s | 1.0 대비 **+50 %** |
| WAF 켠 작은 파일, 프로세스 1개 | 1 097 req/s | 1 130 req/s | +3 % |
| WAF 켠 작은 파일, 프로세스 2개 | — | 1 617 req/s | 1.0 대비 **+47 %** |
| 100 KB 파일, 프로세스 1개 | 1 064 req/s | 1 247 req/s | +17 % |
| 큰 파일(5 MB), 프로세스 1개 | 584 MB/s | 1 658 MB/s | **×2.8** |
| 큰 파일(5 MB), 프로세스 2개 | — | 2 115 MB/s | 1.0 대비 **×3.6** |
| 부하 후 메모리, 프로세스 1개 | 100 MB | 30 MB | **÷3** |

### 동시 대용량 다운로드

테스트: 작은 페이지를 계속 요청하는 동안 300 MB 파일을 동시에 3개 다운로드. 두 번 실행해 같은 결과를 얻었습니다.

| 측정 | 1.0.0 | 2.0.0 |
|---|---:|---:|
| 서버 메모리 최고치 | 1 835 MB | 40 MB |
| 다운로드 중 작은 페이지: 중앙값 | 3~4 ms | 2 ms |
| 다운로드 중 작은 페이지: 최악 | 1.7~1.8 s | 5 ms |

1.0은 각 파일을 보내기 전에 전부 메모리에 올렸습니다. 2.0은 블록 단위로 보내거나 커널에 맡깁니다: 메모리가 더 이상 파일 크기에 좌우되지 않으며, 다운로드 중에도 서버가 계속 빠르게 반응합니다.

### 능동 방어 비용

의심스러운 요청마다 Active Defense가 위협을 관찰하는 비용, 디스크(ext4)에서 관찰 2,000건으로 측정:

| 측정 | 1.0.0 | 2.0.0 |
|---|---:|---:|
| 중앙값 | 2.84 ms | 0.23 ms |
| p99 | 11.6 ms | 2.3 ms |
| 최댓값 | 18~20 ms | 37~46 ms |

중앙값은 12분의 1이 되었습니다. 반면 최댓값은 2.0에서 더 높습니다: SQLite 저널을 주기적으로 디스크에 쓰는 데서 오는 몇몇 고립된 정점입니다.

### 2.0에서 추가된 기능

**시장 표준 따라잡기**: nginx, lighttpd, Caddy, Apache는 이미 이 모든 것을 합니다. omega-serv가 따라잡았습니다.

- 조건부 요청(ETag, Last-Modified, 304 응답): 페이지를 새로 고칠 때 바뀐 것만 다시 받습니다.
- 부분 요청(Range, 206/416): 다운로드 재개, 동영상 건너뛰기.
- `sendfile` 또는 블록 단위 파일 전송, 안정된 메모리.
- 원본 옆에 둔 미리 압축된 파일(`.gz`, `.br`).
- 파일 유형(이미지, 글꼴, CSS/JS)에 따른 기본 Cache-Control, 조정 가능.
- 여러 서버 프로세스(boost 모드, `server.workers`).

**더 넓어진 기능:**

- **완전한 리버스 프록시.** 1.0에는 단순한 중계(라운드 로빈, 상위 서버로의 TLS, WebSocket)만 있었습니다. 2.0이 추가한 것:
  - 6가지 분배 전략, 모두 7가지;
  - 세션 고정과 헤더 기반 라우팅;
  - 상위 서버의 수동 및 능동 상태 확인;
  - 응답 캐시;
  - 과부하와 루프에 대한 보호;
  - 실행 중 제어.
- 전역 제한에 더해 **폴더별, 주소 또는 네트워크별 요청 제한**.
- **프로세스 사이에 공유되는 보안 카운터**(§7 참조).
- 관찰 모드와 내장 편집기를 갖춘, 바로 쓸 수 있는 **민감한 경로 목록**.
- **lighttpd mod_magnet 스크립트 가져오기**(§7 참조).
- 방문자가 보는 페이지와 내보내기용 언어를 따로 둔 **17개 언어 인터페이스**.
- **완전히 새로 다듬은 로그**:
  - 로그 라이브러리;
  - lnav를 포함한 뷰어 세 가지;
  - SSH로 원격 로그 가져오기.

---

## 5. 기능 비교

범례:
- ✅ 내장;
- 🧩 프로젝트의 공식 모듈, 켜거나 설치해야 함;
- 🔌 서드파티 모듈 또는 플러그인;
- ⚙️ 외부 도구를 통해;
- ❌ 없음.

「상용」은 유료 에디션 전용 기능을 뜻합니다.

### HTTP 서비스

| 기능 | nginx | lighttpd | Caddy | Apache | Traefik | omega-serv 2.0 |
|---|---|---|---|---|---|---|
| 정적 파일 제공 | ✅ | ✅ | ✅ | ✅ | ❌ (프록시 전용) | ✅ |
| ETag / 304 / Range | ✅ | ✅ | ✅ | ✅ | — | ✅ |
| 미리 압축된 파일 `.gz` / `.br` | ✅ `gzip_static` (`.br`: 🔌) | 🔌 Lua 스크립트(mod_magnet) | ✅ `precompressed` | 🧩 mod_rewrite 레시피 | — | ✅ |
| 실시간 압축 | ✅ | ✅ mod_deflate | ✅ | 🧩 mod_deflate | ✅ middleware | ❌ |
| HTTP/2 | ✅ | ✅ | ✅ | 🧩 mod_http2 | ✅ | ❌ |
| HTTP/3 (QUIC) | ✅ | ❌ | ✅ | ❌ | ✅ | ❌ |
| FastCGI를 통한 PHP | ✅ | ✅ | ✅ | ✅ | ❌ | ✅ |
| 여러 프로세스 또는 코어 | ✅ workers | ⚠️ `max-worker`, 문서에서 권장하지 않음 | ✅ (Go, 모든 코어) | ✅ MPM | ✅ (Go) | ✅ `server.workers` |

### 리버스 프록시

| 기능 | nginx | lighttpd | Caddy | Apache | Traefik | omega-serv 2.0 |
|---|---|---|---|---|---|---|
| 부하 분산 | ✅ 라운드 로빈, 최소 연결, 해시 | ✅ fair, round-robin, hash, sticky | ✅ 십여 가지 전략 | 🧩 mod_proxy_balancer | ✅ wrr, p2c, hrw, least-time | ✅ 실제 부하 기반을 포함한 7가지 전략 |
| 수동 상태 확인(고장 난 서버 제외) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| 능동 상태 확인(주기적 탐침) | 상용(NGINX Plus) | ❌ | ✅ | 🧩 mod_proxy_hcheck | ✅ | ✅ |
| 응답 캐시 | ✅ `proxy_cache` | ❌ | 🔌 | 🧩 mod_cache | 상용 | ✅ |
| WebSocket | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| 서비스 검색(Docker, Kubernetes) | 🔌 | ❌ | 🔌 | ❌ | ✅ (프로젝트의 핵심) | ❌ |

### TLS

| 기능 | nginx | lighttpd | Caddy | Apache | Traefik | omega-serv 2.0 |
|---|---|---|---|---|---|---|
| 자동 인증서(ACME, Let's Encrypt) | 🧩 `ngx_http_acme_module` | ⚙️ Certbot | ✅ 기본 | 🧩 mod_md | ✅ | ⚙️ Certbot, 내장 마법사와 예약 갱신 |
| 로컬 CA | ❌ | ❌ | ✅ 내부 CA(자동 발급) | ❌ | ❌ | ✅ 생성, CSR 서명, 폐기 |

### 보안

| 기능 | nginx | lighttpd | Caddy | Apache | Traefik | omega-serv 2.0 |
|---|---|---|---|---|---|---|
| 클라이언트별 요청 제한 | ✅ `limit_req` | ⚠️ mod_evasive(동시 연결만) | 🔌 caddy-ratelimit | 🔌 mod_evasive, mod_qos | ✅ middleware | ✅ |
| 프로세스 간 공유 제한 | ✅ 공유 메모리 영역 | ❌ 프로세스별 계산 | — (프로세스 1개뿐) | 모듈에 따라 | 인스턴스 1개; 여럿이면 Redis | ✅ 공유 메모리 |
| WAF(SQLi/XSS 시그니처, 스캐너…) | 🔌 ModSecurity, 상용(App Protect) | ❌ (Lua 스크립트를 직접 작성) | 🔌 Coraza | 🔌 ModSecurity | 🔌 플러그인 | ✅ 내장 |
| 만료와 재범을 갖춘 차단 목록 | ⚙️ fail2ban | ⚙️ fail2ban | ⚙️ fail2ban | ⚙️ fail2ban | ⚙️ | ✅ 내장 |
| 미끼, 전쟁 모드, 인시던트, IoC 내보내기 | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ Active Defense |
| 설정의 보안 감사 | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ `audit security` |
| 관찰 모드(차단 없이 기록) | 모듈에 따라 | — | 플러그인에 따라 | ✅ ModSecurity `DetectionOnly` | 플러그인에 따라 | ✅ |

### 확장성

| 기능 | nginx | lighttpd | Caddy | Apache | Traefik | omega-serv 2.0 |
|---|---|---|---|---|---|---|
| 스크립트 언어 | 🧩 njs(JavaScript); 🔌 Lua(OpenResty) | ✅ Lua(mod_magnet) | Go 모듈(다시 컴파일) | 🧩 mod_lua | Go 또는 WebAssembly 플러그인 | 🔌 mod_magnet 스크립트 가져오기(`magnet` 옵션) |
| 모듈 생태계 | 매우 넓음 | 집중됨 | 넓음 | 매우 넓음 | 넓음 | 없음: 모두 내장 |

---

## 6. 관리와 사용성

| 서버 | 주된 관리 방식 | 인터페이스 | 끊김 없는 다시 로드 |
|---|---|---|---|
| nginx | 설정 파일 | 없음(대시보드: NGINX Plus, 상용) | ✅ `nginx -s reload` |
| lighttpd | 설정 파일 | 없음(읽기 전용 mod_status) | ✅ graceful 재시작 |
| Caddy | Caddyfile 또는 JSON | 관리용 REST API | ✅ API를 통해 |
| Apache | 설정 파일과 `.htaccess` | 없음(읽기 전용 mod_status) | ✅ `graceful` |
| Traefik | 컨테이너 레이블, 파일 또는 Kubernetes | 웹 대시보드(읽기 전용) | ✅ 동적 설정 |
| omega-serv | 터미널 인터페이스(TUI)와 명령줄(CLI); JSON 파일을 편집할 필요 없음 | **키보드와 마우스로 쓰는 완전한 TUI, 17개 언어, 내장 도움말** | ✅ 대부분의 설정; 포트, TLS, 프로세스 수는 재시작을 안내 |

구체적으로, omega-serv에서는 설정, 보안, 로그, 시스템 서비스, 백업, 인스턴스를 하나의 인터페이스에서 관리합니다. 각 설정은 설명이 붙어 있으며 쓰기 전에 검증됩니다. 다른 서버에서는 텍스트 파일을 편집한 뒤 별도의 도구(Certbot, fail2ban, logrotate, ModSecurity, 모니터링 도구…)를 씁니다.

대신 nginx, Apache, Caddy의 「설정 파일」 방식은 자동화하기가 매우 좋습니다(Ansible, 컨테이너, 버전 관리). omega-serv에는 스크립트로 쓸 수 있는 CLI가 있지만, 자동화 생태계는 여전히 제한적입니다.

---

## 7. omega-serv가 더 제공하는 것

이 절에는 비교한 서버 중 어느 것도 서드파티 모듈이나 외부 도구 없이 그대로 제공하지 않는 것만 담았습니다.

1. **터미널 인터페이스의 완전한 관리.**
   - 인터페이스는 서버 전체를 다룹니다: 사이트, 보안, 로그, 서비스, 백업, 인스턴스.
   - 그래픽 화면이 없는 서버에서도, SSH를 거쳐서도 키보드와 마우스로 쓸 수 있습니다.
   - 17개 언어로 제공되며 각 설정을 설명합니다.
   - 다른 서버에는 관리 인터페이스가 없거나(nginx, lighttpd, Apache), API(Caddy)나 읽기 전용 대시보드(Traefik)뿐입니다.
2. **조립할 모듈이 필요 없는 내장 능동 보안.**
   - WAF에는 시그니처, 편집 가능한 경로 목록, 재범, 만료가 있는 차단 목록, 평판, 관찰 모드가 들어 있습니다.
   - Active Defense는 미끼, 전쟁 모드, 인시던트 추적, 침해 지표 내보내기, 모의 실행을 더합니다.
   - 다른 곳에서는 이 기능을 위해 ModSecurity나 Coraza, 규칙 세트, fail2ban을 조립해야 합니다.
3. **여러 프로세스에서도 정확한 보안 제한.**
   - boost 모드에서는 요청 제한과 WAF 재범이 프로세스 사이의 메모리에서 공유됩니다. 그래서 공격자가 자신의 제한을 프로세스 수만큼 늘릴 수 없습니다.
   - lighttpd는 반대 경우를 문서화합니다: `server.max-worker`를 쓰면 `mod_evasive`와 `mod_status`가 프로세스마다 따로 셉니다.
   - nginx도 카운터를 공유하지만(`limit_req` 영역), 내장 WAF는 없습니다.
4. **lighttpd mod_magnet 스크립트 가져오기.**
   - lighttpd용으로 이미 작성된 Lua 보호 스크립트를 다시 쓰지 않고 가져옵니다.
   - 내장 보호에 더해지되 결코 그것을 약하게 만들 수 없으며, 켜기 전에 호환성을 확인합니다.
5. **여러 인스턴스 관리.**
   - 레지스트리가 모든 인스턴스를 기록하며, 인터페이스가 그 사이를 오갑니다.
   - 인스턴스를 완전히 제거할 수도 있습니다.
6. **설정의 보안 감사**: `audit security` 명령은 정보용이며 결코 막지 않고, 스크립트에서 쓸 수 있는 종료 코드를 돌려줍니다.
7. **원격 로그 소스.**
   - 인터페이스가 요청에 따라 다른 서버의 로그를 SSH로 가져오며, 비밀번호를 저장하지 않습니다.
   - lnav로 로컬 로그와 합쳐 읽을 수 있습니다.
8. 설치 직후부터 프로필과 관계없이 동작하는 **끌 수 없는 HTTP 강화**:
   - Host 헤더의 엄격한 검증;
   - Content-Length / Transfer-Encoding 모호성 거부;
   - 오류 페이지에도 적용되는 보안 헤더와 CSP;
   - X-Forwarded-For의 안전한 해석;
   - root로 시작하기 거부.

---

## 8. 다른 서버가 더 잘하는 것

- **처리량과 지연**: nginx와 lighttpd는 작은 요청을 10~20배 더 많이 처리하며, 지연은 8~10배 낮습니다. 트래픽이 많은 사이트, 공개 API, CDN에는 이들을 골라야 합니다.
- **메모리**: lighttpd(1 MB)와 nginx(4~5 MB)는 매우 제약된 머신(임베디드, 보급형 Raspberry Pi, 작은 컨테이너)에 알맞습니다.
- **프로토콜**: 다른 모든 서버에 HTTP/2, nginx, Caddy, Traefik에 HTTP/3. omega-serv는 HTTP/1.1만 씁니다.
- **자동 HTTPS**: Caddy와 Traefik은 기본으로 내장하며, nginx(`ngx_http_acme_module`)와 Apache(`mod_md`)는 공식 모듈로 제공합니다. omega-serv는 마법사와 예약 갱신을 갖추고 Certbot에 맡깁니다.
- **컨테이너 환경**: Traefik의 자동 서비스 검색(Docker, Kubernetes)에 해당하는 것이 omega-serv에는 없습니다.
- **생태계**: nginx와 Apache는 수천 개의 모듈, 가이드, 통합을 제공합니다. Caddy는 Go 모듈 시스템을 제공합니다. omega-serv는 한 사람이 유지 관리하는 젊은 프로젝트입니다.
- **실시간 압축**: omega-serv는 이미 압축된 파일만 제공합니다.

---

## 9. 용도별 서버 선택

| 필요 | 권장 선택 |
|---|---|
| 트래픽이 많은 사이트, 공개 API, CDN, 최대 처리량 | **nginx** |
| 매우 제약된 머신, 임베디드, 정적 파일 | **lighttpd** |
| 자동 HTTPS로 빠르게 시작, 짧은 설정 | **Caddy** |
| 오래된 PHP 애플리케이션, `.htaccess`, 공유 호스팅 | **Apache** |
| Docker, Kubernetes, 마이크로서비스 | **Traefik** |
| 작은 사이트, 내부 서비스, 실습 환경, VPN, 파일을 편집하지 않는 관리 | **omega-serv** |
| 보안(WAF, 차단, 미끼)을 하나의 인터페이스에서 보고 제어하고 싶은 노출된 서버 | **omega-serv** |
| 인터페이스로 제어하는, 분배·상태 확인·캐시를 갖춘 내부 리버스 프록시 | **omega-serv** |
| HTTP 강화와 능동 방어 배우기 | **omega-serv** |

이 도구들은 함께 쓸 수도 있습니다. 예를 들어:
- 인터넷 앞단에 nginx나 Traefik을 두고, 그 뒤에 내부 서비스와 그 보안 및 관리를 위해 omega-serv를 둠;
- 여러 애플리케이션 서버 앞에 내부 리버스 프록시로 omega-serv를 둠.

---

## 10. 측정 재현하기

도구는 저장소의 `tools/bench/` 아래에 제공됩니다. nginx, lighttpd, Caddy, oha가 설치되어 있어야 하며, omega-serv 개발 환경(`.venv`)도 필요합니다.

```sh
# 1. 측정 폴더 준비(테스트 파일, 구성, omega-serv 1.0과 2.0)
tools/bench/compare/setup.sh /chemin/mesure omega-serv-1.0.0.tar.gz

# 2. 12가지 구성, 교차 반복 3회(약 22분)
tools/bench/compare/campaign.sh /chemin/mesure > resultats.txt

# 3. 중앙값
python3 tools/bench/compare/summarize.py resultats.txt

# 대용량 다운로드(메모리와 반응성), 2.0 다음 1.0
.venv/bin/python tools/bench/bigfile.py
BENCH_SRC=/chemin/mesure/v1-archive/omega-serv/src \
BENCH_EXTRA_PATH=/chemin/mesure/v1-archive/omega-serv/vendor/omega-lib/src \
  .venv/bin/python tools/bench/bigfile.py

# oha 없이, 이미 실행 중인 다른 서버 측정
python3 tools/bench/bench_any.py --make-files /srv/webroot-de-test
python3 tools/bench/bench_any.py --port 8080
```

기본으로 서버는 스레드 0과 2에, 클라이언트는 스레드 1과 3에 고정되며, 이는 측정 머신에 맞춘 것입니다. 이 배치는 `SRV_CPUS`와 `CLI_CPUS` 변수로 여러분의 프로세서에 맞게 조정하십시오(`lscpu -e`가 토폴로지를 보여 줍니다).

자신의 결과를 공개하려면 머신, 버전, 프로세서 배치, 세 번의 반복을 함께 밝히십시오.

---

## 11. 출처

다른 서버의 기능은 공식 문서를 따릅니다(2026년 10월 26일 확인).

**nginx**
- [요청 제한 `limit_req`(공유 메모리 영역)](https://nginx.org/en/docs/http/ngx_http_limit_req_module.html)
- [미리 압축된 파일 `gzip_static`](https://nginx.org/en/docs/http/ngx_http_gzip_static_module.html)
- [공식 ACME 모듈 `ngx_http_acme_module`](https://nginx.org/en/docs/http/ngx_http_acme_module.html)
- [부하 분산(`upstream`)](https://nginx.org/en/docs/http/ngx_http_upstream_module.html)
- [HTTP/3](https://nginx.org/en/docs/http/ngx_http_v3_module.html)
- [nginx용 ModSecurity 커넥터](https://github.com/owasp-modsecurity/ModSecurity-nginx)

**lighttpd**
- [`server.max-worker`: 권장하지 않음, mod_status와 mod_evasive는 프로세스별 카운터](https://redmine.lighttpd.net/projects/lighttpd/wiki/Server_max-workerDetails)
- [mod_magnet(Lua 스크립트)](https://redmine.lighttpd.net/projects/lighttpd/wiki/Docs_ModMagnet)
- [mod_deflate(압축, 캐시)](https://redmine.lighttpd.net/projects/lighttpd/wiki/Mod_deflate)
- [mod_proxy(분배, 수동 상태 확인, WebSocket)](https://redmine.lighttpd.net/projects/lighttpd/wiki/Docs_ModProxy)
- [mod_evasive(주소별 동시 연결)](https://redmine.lighttpd.net/projects/lighttpd/wiki/Docs_ModEvasive)

**Caddy**
- [자동 HTTPS](https://caddyserver.com/docs/automatic-https)
- [`file_server`와 `precompressed`](https://caddyserver.com/docs/caddyfile/directives/file_server)
- [`reverse_proxy`(전략, 능동 및 수동 상태 확인)](https://caddyserver.com/docs/caddyfile/directives/reverse_proxy)
- [관리 API](https://caddyserver.com/docs/api)
- [요청 제한 플러그인 caddy-ratelimit](https://github.com/mholt/caddy-ratelimit)
- [Caddy용 Coraza WAF](https://github.com/corazawaf/coraza-caddy)
- [caddy-docker-proxy](https://github.com/lucaslorentz/caddy-docker-proxy)

**Apache HTTP Server**
- [mod_md(ACME)](https://httpd.apache.org/docs/2.4/mod/mod_md.html)
- [mod_proxy_balancer](https://httpd.apache.org/docs/2.4/mod/mod_proxy_balancer.html)
- [mod_proxy_hcheck](https://httpd.apache.org/docs/2.4/mod/mod_proxy_hcheck.html)
- [mod_http2](https://httpd.apache.org/docs/2.4/mod/mod_http2.html)
- [mod_deflate, 미리 압축된 콘텐츠](https://httpd.apache.org/docs/2.4/mod/mod_deflate.html)
- [ModSecurity](https://github.com/owasp-modsecurity/ModSecurity)

**Traefik**
- [`ratelimit` middleware(인스턴스별 메모리, 선택적으로 Redis)](https://doc.traefik.io/traefik/reference/routing-configuration/http/middlewares/ratelimit/)
- [ACME](https://doc.traefik.io/traefik/https/acme/)
- [Providers(Docker, Kubernetes…)](https://doc.traefik.io/traefik/providers/overview/)

**측정 도구**
- [oha](https://github.com/hatoo/oha)

---

*omega-serv 2.0.0을 위해 kraynux가 작성한 비교: 2026년 10월 26일 측정. 측정은 한 대의 머신에서만 이루어졌습니다. 용량 결정을 위해서는 제공된 도구로 여러분의 하드웨어에서 측정하십시오.*
