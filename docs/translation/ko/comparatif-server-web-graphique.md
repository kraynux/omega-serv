# omega-serv와 시장의 웹 서버 — 그래픽 버전

**omega-serv와 nginx · lighttpd · Apache · Caddy · Traefik 비교 — 세 대의 머신에서 측정(2026년 11월).**

🌐 [Français](../../comparatif-server-web-graphique.md) · [English](../en/comparatif-server-web-graphique.md) · [Español](../es/comparatif-server-web-graphique.md) · [Português (Brasil)](../pt-BR/comparatif-server-web-graphique.md) · [Italiano](../it/comparatif-server-web-graphique.md) · [Deutsch](../de/comparatif-server-web-graphique.md) · [Nederlands](../nl/comparatif-server-web-graphique.md) · [Polski](../pl/comparatif-server-web-graphique.md) · [Русский](../ru/comparatif-server-web-graphique.md) · [中文](../zh-CN/comparatif-server-web-graphique.md) · [Tiếng Việt](../vi/comparatif-server-web-graphique.md) · [ไทย](../th/comparatif-server-web-graphique.md) · [Bahasa Indonesia](../id/comparatif-server-web-graphique.md) · [日本語](../ja/comparatif-server-web-graphique.md) · **한국어** · [हिन्दी](../hi/comparatif-server-web-graphique.md) · [العربية](../ar/comparatif-server-web-graphique.md)

> **읽는 방법:** 막대가 길수록 서버가 빠릅니다. 기준은 **nginx = 1.00**.

## 색상 범례

<!-- 🖼️ IMAGE : legende-couleurs -->
<div align="center">
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/translation/ko/omega-serv/stats-1.png" alt="색상 범례" width="1024">
</div>

---

## 📊 1 KB 파일 — 처리량(요청/초)

머신 A(i5 2010), B(Celeron 2016), C(Ryzen 2024). 막대는 같은 머신의 nginx(1.00)를 기준으로 정규화했습니다.

<!-- 🖼️ IMAGE : 1ko-banner — 3 colonnes côte à côte (Machine A · 2 cœurs | Machine B · 4 cœurs | Machine C · 10 cœurs), largeur totale -->
<div align="center">
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/translation/ko/omega-serv/stats-2.png" alt="1 KB 파일 — 머신 A, B, C" width="1024">
</div>

> \* 머신 C: 네이티브 엔진은 코어 4개, nginx는 프로세스 2개(코어 2개)를 사용합니다. 코어 수를 맞추면 비율은 ~0.70으로 떨어집니다.
---

## 📦 중간 크기 파일(100 KB) — 일반 웹 모드

여기서는 Apache가 의외의 성적을 내며 omega-serv 네이티브 엔진을 자주 앞섭니다. 가장 빠른 것은 여전히 lighttpd입니다. 기준: nginx = 1.00.

<!-- 🖼️ IMAGE : 100ko-banner.png — 3 colonnes côte à côte (A | B | C), largeur totale -->
<div align="center">
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/translation/ko/omega-serv/stats-3.png" alt="100 KB 파일 — 머신 A, B, C" width="1024">
</div>

---

## 💿 큰 파일(5 MB) — 일반 웹 모드

큰 파일에서는 서버 간 차이가 줄어듭니다. 데이터를 복사하는 것은 커널이기 때문입니다(sendfile). 머신 C에서는 Caddy가 예외입니다. 처리량은 MB/s.

<!-- 🖼️ IMAGE : 5mo-banner.png — 3 colonnes côte à côte (A | B | C), largeur totale -->
<div align="center">
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/translation/ko/omega-serv/stats-4.png" alt="5 MB 파일 — 머신 A, B, C" width="1024">
</div>

---

## 🔄 리버스 프록시 — 작은 응답(1 KB)

각 프록시는 nginx 백엔드로 중계합니다. 기준: nginx = 1.00. 머신 C: 프로세스 4개.

<!-- 🖼️ IMAGE : proxy-1ko-banner.png — 3 colonnes côte à côte (A | B | C), largeur totale -->
<div align="center">
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/translation/ko/omega-serv/stats-5.png" alt="프록시 1 KB — 머신 A, B, C" width="1024">
</div>

---

## 🔄 리버스 프록시 — 100 KB 응답

중간 크기 응답에서는 omega-serv 네이티브가 nginx와 대등하거나 앞섭니다.

<!-- 🖼️ IMAGE : proxy-100ko-banner.png — 3 colonnes côte à côte (A | B | C), largeur totale -->
<div align="center">
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/translation/ko/omega-serv/stats-6.png" alt="프록시 100 KB — 머신 A, B, C" width="1024">
</div>

---

## 💾 메모리(PSS) — 유휴 시 → 부하 후

막대가 짧을수록 서버가 메모리를 아낍니다. lighttpd, nginx, Apache가 가장 검소하고, omega-serv 3.0.0(11월 19일 재측정)이 그 뒤를 이어 네이티브 엔진에서 10~16 MB를 사용합니다.

<!-- 🖼️ IMAGE : memoire-banner.png — 3 colonnes côte à côte de jauges (A | B | C), largeur totale -->
<div align="center">
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/translation/ko/omega-serv/stats-7.png" alt="메모리 — 머신 A, B, C" width="1024">
</div>

---

## 🏆 일반 웹 모드 순위 — 가장 빠른 것은?

세 머신에서 정적 파일을 제공할 때의 종합입니다.

<!-- 🖼️ IMAGE : classement-web.png -->
<!-- Contenu : 1. 🥇 lighttpd — meilleur en petits & moyens fichiers · 2. 🥈 nginx — référence, excellent partout · 3. 🥉 Apache — bon, robuste, écosystème · 4. omega-serv natif — très bon, 2ᵉ en reverse proxy · 5. Caddy — simple, HTTPS auto · 6. omega-serv Python — moteur de repli -->
<div align="center">
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/translation/ko/omega-serv/stats-8.png" alt="일반 웹 모드 순위" width="1024">
</div>

---

## 🔄 리버스 프록시 순위 — 가장 우수한 것은?

nginx가 여전히 기준이며, omega-serv 네이티브는 그에 가장 가까운 차점으로 나머지를 크게 앞섭니다.

<!-- 🖼️ IMAGE : classement-proxy.png -->
<!-- Contenu : 1. 🥇 nginx · 2. 🥈 omega-serv natif — 0,82 à 0,91× nginx en 1 Ko · 3. 🥉 omega-serv + WAF — toujours devant lighttpd/Apache · 4. lighttpd — 0,53 à 0,61× · 5. Apache — 0,50 à 0,59× · 6. Traefik — 0,29 à 0,35× · 7. Caddy — 0,23 à 0,32× · 8. omega-serv Python — moteur de repli -->
<div align="center">
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/translation/ko/omega-serv/stats-9.png" alt="리버스 프록시 순위" width="1024">
</div>

---

## 🆚 맞대결 — 웹과 리버스 프록시 순위를 나란히

두 가지 용도, 두 가지 순위. 한쪽에서 빛나다 다른 쪽에서는 아쉬운 서버도 있습니다. Apache는 중계에서 의외이고, Caddy는 단순함을 빼면 어디서나 실망스럽습니다.

<!-- 🖼️ IMAGE : face-a-face.png — 2 colonnes côte à côte (web | proxy), largeur totale -->
<div align="center">
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/translation/ko/omega-serv/stats-10.png" alt="맞대결 웹 vs 리버스 프록시" width="1024">
</div>

### 교차 종합

| 서버 | 위치 |
|---|---|
| 🟢 **omega-serv 네이티브** | 가장 다재다능: 웹 4위, **리버스 프록시 2위**. WAF를 내장하고 중계에서 lighttpd와 Apache보다 앞서는 유일한 서버. 두 용도를 하나의 도구로 처리하면서 보안까지 갖추고 싶을 때 가장 좋은 절충안. |
| 🔵 **nginx** | 가장 꾸준함: 웹 2위, **리버스 프록시 1위**. 항상 순위 상단에 있으며 뚜렷한 약점이 없음. 특별한 요구가 없을 때의 기본 선택. |
| 🟢 **lighttpd** | 정적 파일의 단거리 주자: **웹 1위**, 하지만 중계는 4위. 순수 정적 파일에는 최고의 선택이지만, 리버스 프록시가 더해지면 omega-serv나 nginx에 자리를 내줌. |
| 🔴 **Apache** | 반례: 웹 3위, 중계 5위. 큰 파일에서는 nginx마저 앞섬(머신 C). 가장 빠르지도 가볍지도 않으며, 강점은 PHP 생태계. |
| 🟠 **Caddy** | 속도보다 단순함: 웹 5위, **중계 7위**. 처리량을 위한 서버가 아니며 자동 HTTPS와 짧은 설정이 강점. 소규모 프로젝트용. |
| 🟣 **Traefik** | 웹 범주 밖: 파일 서버가 아니며 중계 6위. 주 무대는 Docker와 Kubernetes이며 순수 성능이 아님. |

---

## 📋 전체 요약표 — nginx(1.00) 대비 비율

**모든** 지표의 개요: 일반 웹 모드(1 KB, 100 KB, 5 MB)와 리버스 프록시(1 KB, 100 KB), 그리고 메모리. 값이 1.00에 가깝거나 그 이상일수록 좋습니다.

| 서버 | Web 1 KB (A/B/C) | Web 100 KB (A/B/C) | Web 5 MB (A/B/C) | Proxy 1 KB (A/B/C) | Proxy 100 KB (A/B/C) | 메모리 (A/B/C) |
|---|---|---|---|---|---|---|
| **lighttpd** | 1.52 / 1.26 / 1.53 | 1.08 / 1.07 / 1.26 | 1.05 / 0.99 / 0.81 | 0.61 / 0.56 / 0.53 | 0.74 / 0.62 / 0.96 | 1 MB |
| **nginx** | 1.00 / 1.00 / 1.00 | 1.00 / 1.00 / 1.00 | 1.00 / 1.00 / 1.00 | 1.00 / 1.00 / 1.00 | 1.00 / 1.00 / 1.00 | 4–5 MB |
| **omega-serv (네이티브)** | **0.70 / 0.67 / 1.15\*** | **0.38 / 0.28 / 0.61** | **0.99 / 0.91 / 1.09** | **0.85 / 0.91 / 0.82** | **1.11 / 0.97 / 1.43** | 10–16 MB |
| **omega-serv + WAF** | 0.56 / 0.53 / 1.07\* | 0.37 / 0.27 / 0.62 | — | 0.81 / 0.89 / 0.77 | 1.10 / 0.93 / 1.30 | 28–33 MB |
| **Apache** | 0.42 / 0.35 / 0.76 | 0.55 / 0.62 / 0.97 | 1.01 / 1.00 / 1.19 | 0.59 / 0.53 / 0.50 | 0.62 / 0.65 / 0.71 | 4–9 MB |
| **Caddy** | 0.26 / 0.17 / 0.21 | 0.40 / 0.33 / 0.14 | 0.95 / 0.94 / 0.11 | 0.32 / 0.28 / 0.23 | 0.60 / 0.54 / 0.59 | 46–67 MB |
| **Traefik** | — | — | — | 0.35 / 0.35 / 0.29 | 0.64 / 0.60 / 0.70 | 93–131 MB |
| **omega-serv (Python)** | 0.11 / 0.05 / 0.08 | 0.14 / 0.10 / 0.12 | 0.92 / 0.91 / 0.75 | 0.09 / 0.08 / 0.07 | 0.21 / 0.19 / — | 20–48 MB |

> \* 머신 C: 네이티브는 코어 4개, nginx는 2개. 코어 수를 맞추면 비율은 ~0.67–0.71.
> 셀마다 세 개의 값은 머신 **A / B / C**에 해당합니다. "—": 측정하지 않았거나 해당 없음.

---

## ⚖️ 강점과 약점 — 모든 서버

각 서버에는 강점과 한계가 있습니다. 편애 없이 전체를 살펴봅니다.

### 🟢 omega-serv(네이티브)

**강점**
- ✅ 터미널에서의 완전한 관리(TUI, 17개 언어)
- ✅ WAF + Active Defense + RIPOSTE 내장
- ✅ C++ 네이티브 엔진: 정적 파일에서 nginx의 ~0.7배
- ✅ 리버스 프록시에서 nginx 다음인 2위
- ✅ 프로세스 간에 공유되는 제한(정확한 보안)
- ✅ lighttpd mod_magnet 스크립트 가져오기
- ✅ 여러 인스턴스 관리
- ✅ 웹 관리


**약점**
- ❌ HTTP/2도 HTTP/3도 없음
- ❌ 즉석 압축 없음
- ❌ Docker/Kubernetes 디스커버리 없음
- ❌ ACME는 Certbot 경유(네이티브 통합 아님)
- ❌ 100 KB 파일: nginx의 0.3–0.6배
- ❌ 메모리 10–55 MB, 모드에 따라 다름(nginx/lighttpd는 1–5 MB)
- ❌ 젊은 생태계, 한 사람이 유지보수

---

### 🔵 nginx

**강점**
- ✅ 성능과 안정성의 기준
- ✅ HTTP/2, HTTP/3, 압축
- ✅ 방대한 생태계(모듈, 문서, 커뮤니티)
- ✅ 메모리 사용이 매우 적음(4–5 MB)
- ✅ 훌륭한 리버스 프록시
- ✅ 공식 ACME 모듈
- ✅ 성숙하고 검증된 설정

**약점**
- ❌ 장황한 설정, 고유한 문법을 배워야 함
- ❌ 내장 WAF 없음(ModSecurity 또는 동급 필요)
- ❌ 네이티브 관리 인터페이스 없음
- ❌ 설정 리로드가 운영 환경에서 까다로울 때가 있음
- ❌ 오픈 소스 버전은 제한적(일부 기능은 유료 Nginx Plus)
- ❌ 네이티브 Docker/Kubernetes 디스커버리 없음(템플릿 경유)

---

### 🟢 lighttpd

**강점**
- ✅ 작은·중간 파일에서 가장 빠름
- ✅ 메모리를 가장 아낌(1 MB)
- ✅ 가볍고 제약이 있는 시스템에 적합
- ✅ 좋은 리버스 프록시
- ✅ 단순하고 읽기 쉬운 설정

**약점**
- ❌ HTTP/3 없음(HTTP/2는 빌드에 따라 부분 지원)
- ❌ 리버스 프록시에서 4위에 그침(nginx의 0.53–0.61배)
- ❌ nginx/Apache보다 생태계가 작음
- ❌ 내장 WAF 없음
- ❌ Docker/Kubernetes 디스커버리 없음
- ❌ 예전보다 개발이 덜 활발함
- ❌ 큰 파일에 약함(머신 C에서 nginx의 0.81배)

---

### 🔴 Apache

**강점**
- ✅ 역사적으로 방대한 생태계(모듈, `.htaccess`, PHP)
- ✅ 수십 년간 검증된 견고함
- ✅ 큰 파일에서 훌륭함(머신 C에서 nginx를 앞섬)
- ✅ 재시작 없는 `.htaccess` 지원
- ✅ 압축, HTTP/2, ACME 사용 가능
- ✅ 풍부한 문서

**약점**
- ❌ 작은 파일에서 느림(nginx의 0.35–0.42배)
- ❌ prefork 모드에서 메모리 사용이 큼(4–9 MB, 부하에서 빠르게 증가)
- ❌ 이벤트 기반보다 비효율적인 프로세스 모델
- ❌ 장황한 설정
- ❌ 리버스 프록시 5위(nginx의 0.50–0.59배)
- ❌ 내장 WAF 없음(ModSecurity는 별도 모듈)
- ❌ 역사적으로 공격 표면이 더 넓음

---

### 🟠 Caddy

**강점**
- ✅ 자동 HTTPS(ACME 내장, 설정 불필요)
- ✅ 매우 짧고 읽기 쉬운 설정(Caddyfile)
- ✅ HTTP/2와 HTTP/3 네이티브 지원
- ✅ 단일 바이너리, 간단한 배포
- ✅ 중간 크기 응답에서 무난한 리버스 프록시

**약점**
- ❌ 순수 처리량이 느림(웹 5위, 중계 7위)
- ❌ 높은 메모리 사용(46–67 MB)
- ❌ 머신 C의 큰 파일에서 매우 약함(nginx의 0.11배)
- ❌ 내장 WAF 없음
- ❌ nginx/Apache보다 젊은 생태계
- ❌ 매우 높은 처리량에는 부적합

---

### 🟣 Traefik

**강점**
- ✅ Docker/Kubernetes 자동 디스커버리
- ✅ 컨테이너 환경에 이상적
- ✅ 자동 HTTPS(ACME 내장)
- ✅ 재시작 없는 동적 설정
- ✅ 중간 크기 응답에서 좋은 리버스 프록시(nginx의 0.60–0.70배)

**약점**
- ❌ 파일 서버가 아님(웹 순위에 없음)
- ❌ 리버스 프록시 6위(1 KB에서 nginx의 0.29–0.35배)
- ❌ 매우 높은 메모리 사용(93–131 MB)
- ❌ 컨테이너 밖에서는 설정이 복잡
- ❌ 내장 WAF 없음
- ❌ 단순한 정적 사이트에는 과함

---

## 🎯 어떤 용도에 어떤 서버?

| 용도 | 권장 서버 | 이유 |
|---|---|---|
| 트래픽이 많은 사이트 | **nginx** 또는 **lighttpd** | 최대 처리량, HTTP/2-3 |
| 제약이 있는 머신 / 임베디드 | **lighttpd** | 메모리 1 MB, 가장 빠르고 가장 적게 소모 |
| 간단한 자동 HTTPS | **Caddy** | 자동 인증서, 짧은 설정 |
| Docker / Kubernetes | **Traefik** | 서비스 디스커버리 |
| PHP 애플리케이션 / .htaccess | **Apache** | 역사적인 생태계 |
| 리버스 프록시 | **nginx** 또는 **omega-serv (네이티브)** | 최고의 성능 |
| 웹 사이트 + 보안 + 인터페이스 | **omega-serv (네이티브)** | 완전한 인프라: WAF, 웹 관리, 멀티 인스턴스, 리버스 프록시, 로그 관리자, 백업… |

---

omega-serv 비교(2026년 11월)에서 가져온 데이터 — kraynux. MIT 라이선스.
[oha](https://github.com/hatoo/oha)로 측정 · 독립형 HTML/CSS 그래프.

> *측정으로 비교한 omega-serv의 그래픽 버전입니다(상세 비교와 같은 수치: 세 대의 머신에서 2026년 11월 3일과 4일에 측정, 리버스 프록시는 2026년 11월 14일, omega-serv 3.0.0 메모리는 2026년 11월 19일). 용량 관련 결정을 내릴 때는 직접 사용하는 하드웨어에서 측정하십시오.*
>
> Copyright © 2026 kraynux — kraynux@proton.me — MIT 라이선스(LICENSE 파일 참조).
