<!-- Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE) -->
<div align="center">
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/assets/omega-serv.png" alt="Omega-Serv" width="384">
</div>

# 🔒 OMEGA-SERV

**독립형, 이식 가능, 기본적으로 강화된 HTTP 웹 서버**

> [kraynux](https://github.com/kraynux)가 [Omega-Server](https://kraynux.snake-mackarel.ts.net)를 위해 개발   

공식 페이지: [OMEGA-SERV](https://kraynux.snake-mackarel.ts.net/omega-serv/translation/ko/) &nbsp; 레퍼런스, 사용법, 도움말 및 FAQ: [전체 가이드](https://kraynux.snake-mackarel.ts.net/omega-serv/translation/ko/guide.html)  
미리 보기: [스크린샷](https://kraynux.snake-mackarel.ts.net/omega-serv/screenshots/) &nbsp; 데모 [데모 서버](https://craftdark.snake-mackarel.ts.net) &nbsp; [웹 서버 비교/테스트](comparatif-serveurs-web.md)  

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](../../../LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![Lua](https://img.shields.io/badge/Lua-5.4%2B-2C2D72.svg)](https://www.lua.org/)
[![JavaScript](https://img.shields.io/badge/JavaScript-ES2020%2B-F7DF1E.svg)](https://developer.mozilla.org/docs/Web/JavaScript)
[![HTML](https://img.shields.io/badge/HTML-5-E34F26.svg)](https://developer.mozilla.org/docs/Web/HTML)
[![Platform](https://img.shields.io/badge/Platform-Linux-informational.svg)](https://www.linux.org/)
[![Interface](https://img.shields.io/badge/Interface-CLI%20%2B%20TUI-cyan.svg)](#3-사용법)
[![Textual](https://img.shields.io/badge/Textual-TUI-5A5AFB.svg)](https://textual.textualize.io/)

🌐 문서, 내보내기 및 인터페이스를 **17개 언어**로 제공합니다 — [인터페이스 언어](#인터페이스-언어)를 참조하십시오.  
**언어:**
<img src="https://flagcdn.com/w20/fr.png" alt="France" style="height:14px;"> [Français](../../../README.md) · <img src="https://flagcdn.com/w20/gb.png" alt="English" style="height:14px;"> [English](../en/README.md) · <img src="https://flagcdn.com/w20/es.png" alt="Español" style="height:14px;"> [Español](../es/README.md) · <img src="https://flagcdn.com/w20/br.png" alt="Português (Brasil)" style="height:14px;"> [Português (Brasil)](../pt-BR/README.md) · <img src="https://flagcdn.com/w20/it.png" alt="Italiano" style="height:14px;"> [Italiano](../it/README.md) · <img src="https://flagcdn.com/w20/de.png" alt="Deutsch" style="height:14px;"> [Deutsch](../de/README.md) · <img src="https://flagcdn.com/w20/nl.png" alt="Nederlands" style="height:14px;"> [Nederlands](../nl/README.md) · <img src="https://flagcdn.com/w20/pl.png" alt="Polski" style="height:14px;"> [Polski](../pl/README.md) · <img src="https://flagcdn.com/w20/ru.png" alt="Русский" style="height:14px;"> [Русский](../ru/README.md) · <img src="https://flagcdn.com/w20/cn.png" alt="中文" style="height:14px;"> [中文](../zh-CN/README.md) · <img src="https://flagcdn.com/w20/vn.png" alt="Tiếng Việt" style="height:14px;"> [Tiếng Việt](../vi/README.md) · <img src="https://flagcdn.com/w20/th.png" alt="ไทย" style="height:14px;"> [ไทย](../th/README.md) · <img src="https://flagcdn.com/w20/id.png" alt="Bahasa Indonesia" style="height:14px;"> [Bahasa Indonesia](../id/README.md) · <img src="https://flagcdn.com/w20/jp.png" alt="日本語" style="height:14px;"> [日本語](../ja/README.md) · <img src="https://flagcdn.com/w20/kr.png" alt="한국어" style="height:14px;"> [한국어](README.md) · <img src="https://flagcdn.com/w20/in.png" alt="हिन्दी" style="height:14px;"> [हिन्दी](../hi/README.md) · <img src="https://flagcdn.com/w20/ae.png" alt="العربية" style="height:14px;"> [العربية](../ar/README.md)

---

**OMEGA-SERV**는 순수 Python(서버 핵심부는 표준 라이브러리만 사용)으로 작성된 HTTP/1.1 서버로, 정적 콘텐츠를 제공하고 선택적으로 PHP-FPM을 실행하도록 설계되었습니다. 끌 수 없는 프로토콜 강화와, 강제가 아니라 필요에 따라 겹쳐 쓸 수 있는 보안 모듈(WAF, TLS, 인증)을 갖추고 있습니다. `omega-` 도구 모음의 일곱 번째 도구이지만 의도적으로 **향후 `omega-suite` 통합에서 제외**됩니다(원격 대상이 아니라 자신을 실행하는 로컬 머신에 작용하기 때문이며, `omega-fire`와 같은 계열입니다). Clean Architecture로 구성되며, `bootstrap/`이 컴포지션 루트 역할을 합니다.

## 1. 비전과 범위

내세우는 우선순위는 **무엇보다 HTTP 핵심부의 견고성/보안**입니다 — WAF와 TLS는 그 위에 얹는 선택 모듈이며, 결코 전제 조건이 아닙니다. 많은 일을 어설프게 하는 서버보다, 한 가지 일(파일 제공, 경우에 따라 PHP)만 하되 우회할 수 없는 진짜 프로토콜 강화와 함께 제대로 하는 서버를 지향합니다.

### OMEGA-SERV가 하는 일

- 안전한 경로 해석(traversal, 이중 인코딩, 심볼릭 링크)을 갖춘 정적 콘텐츠 제공(파일, 선택적 디렉터리 목록, 별칭, 리디렉션, 재작성, 캐시). 큰 파일은 디스크에서 블록 단위로 전송되며 메모리에 적재되지 않습니다. 모든 파일에는 `ETag`와 `Last-Modified`가 붙고(새로 고침 = 빈 304 응답), 부분 요청 `Range`(다운로드 재개, 동영상)를 받아들입니다. 이미지, 미디어, 글꼴, CSS, JS에는 기본 `Cache-Control`이 붙으며 캐시 화면에서 바꿀 수 있습니다. 미리 압축한 텍스트 파일: `site.css` 옆에 `site.css.br` 또는 `site.css.gz`가 있고(`brotli -k site.css` 또는 `gzip -k site.css`로 생성) 브라우저가 받아들이면 그것을 대신 전송하며, 원본보다 오래된 버전을 보내는 일은 없습니다.
- 끌 수 있는 옵션 없이 기본적으로 HTTP 프로토콜을 강화합니다: 명시적인 허용 메서드, `Host` 헤더 검증, `Content-Length`/`Transfer-Encoding` 모호성 거부, 우회할 수 없는 보안 헤더와 기본 CSP.
- 선택 사항: WAF 필터링(시그니처, 요청 제한, 차단 목록), 직접 TLS(자체 서명 인증서, 로컬 CA 서명, 또는 자동 갱신되는 Let's Encrypt/Certbot 공개 인증서 — §9 참조), 영역별 HTTP Basic 인증, FastCGI/PHP-FPM을 통한 PHP, 격리된 업로드 영역.
- 「boost」 모드: 여러 서버 프로세스, 머신에서 사용할 수 있는 CPU당 최대 하나(내구성과 제한 화면). 보안 카운터(rate limit, 재범)는 프로세스 간에 공유되며 정확하게 유지됩니다.
- 자신의 설정을 감사하고(`audit security`) 시스템 서비스(systemd/OpenRC/runit)로 스스로를 설치합니다.
- 처음부터 끝까지 스크립트로 쓸 수 있는 비대화형 CLI와, **똑같은 사용 사례를 감싸는 대화형 인터페이스(Textual)** — §3 참조. 인터페이스 로드맵(`OMEGA-SERV_PLAN-DETAILLE_INTERFACE.md`, §12)은 **모두 제공되었습니다**: 기능 레지스트리, 프로필/옵션, 상세 설정(별칭/리디렉션/재작성/FastCGI/dirlisting/인증/캐시/WAF/신뢰 프록시/아웃바운드 리버스 프록시/TLS), 로그 관리(라이브러리/즐겨찾기, 3가지 뷰어 — 단순/클래식/통합 lnav —, IP 보기 및 처리, SSH 원격 소스, 순환/백업/자동화/복원/삭제/내보내기), 시스템 서비스, 다중 인스턴스(레지스트리, 생성), 확인/시뮬레이션/감사, 설정 백업/복원, 첫 실행 마법사, 애플리케이션 설정(테마, 렌더링 프로필, 내보내기/스크린샷 경로), 상황별 도움말 가이드(구체적인 예가 담긴 화면별 안내, FAQ, HTML 내보내기, 테스트로 검증된 빠짐없는 범위), 저장할 때마다 다시 로드/재시작 여부를 항상 표시, 파일을 직접 편집하지 않는 Active Defense의 전체 설정.

### OMEGA-SERV가 하지 않는 일

- 원시 CGI(V1 범위에서 제외 — FastCGI/PHP-FPM만 지원).
- TLS 상호 인증(mTLS), OCSP stapling — V1 범위 밖, §15 참조. (Certbot을 통한 ACME/Let's Encrypt는 사용할 수 있습니다, §9c/9d 참조.)
- 프로세스 간에 공유되는 HTTP 캐시.
- 원격 대상의 스캔/감사(그런 작업에는 `omega-check`/`omega-scan`/`omega-deep`을 사용하십시오 — Omega-serv는 자기 자신을 감사하며, 제3자를 감사하지 않습니다).

### 시장의 웹 서버와 비교한 OMEGA-SERV

[측정 및 비교](comparatif-serveurs-web.md) 참조  
측정 기반 비교: [Nginx](https://nginx.org/) · [Lighttpd](https://www.lighttpd.net/) · [Caddy](https://caddyserver.com/) · [Apache](https://www.apache.org) · [Traefik](https://traefik.io/) · [Omega-Serv](https://kraynux.snake-mackarel.ts.net/omega-serv/translation/ko/)

### 사용상 경고

Omega-serv는 **root로 시작하기를 거부합니다**. 제공되는 어떤 프로필에서도, `hardened`를 포함해, 보안 모듈(WAF, TLS, 인증)은 기본으로 켜져 있지 않습니다 — 켜는 것은 항상 명시적인 동작입니다(`config enable-tls`, `option enable waf`...). `hardened` 프로필 자체도 실제로 인터넷에 노출할 때는 리버스 프록시를 대신하려 하지 않고 리버스 프록시 사용을 권장합니다.

## 2. 설치

### 필요 조건

- Python 3.10+
- TLS 인증서와 관련된 모든 작업에 `openssl`(Python 라이브러리가 아닌 실행 파일) — 다른 기능은 없어도 동작합니다.

### 다운로드

최신 버전 아카이브와 각 버전의 SHA-256 지문: [omega-serv-2.0.1.tar.gz](https://kraynux.snake-mackarel.ts.net/omega-serv/download/omega-serv-2.0.1.tar.gz) · [sha.txt](https://kraynux.snake-mackarel.ts.net/omega-serv/download/sha.txt)

```bash
wget https://kraynux.snake-mackarel.ts.net/omega-serv/download/omega-serv-2.0.1.tar.gz
wget https://kraynux.snake-mackarel.ts.net/omega-serv/download/sha.txt
sha256sum -c --ignore-missing sha.txt
```

### 설치

> ⚠️ **기존 설치를 업데이트하시나요?** 아래 명령은 `omega-serv/`가 이미 있으면 **압축 해제를 조용히 건너뜁니다**(업데이트가 아니라 중단된 첫 설치로 간주하기 때문) — 그러면 **바뀌지 않은 예전 코드** 위에 의존성을 다시 설치하게 되며, 오류 메시지는 전혀 나오지 않습니다. 대신 아래의 [업데이트](#업데이트) 절을 사용하십시오.

```bash
[ -d omega-serv ] && echo "ℹ️ 여기에는 이미 압축이 풀려 있습니다. 이 단계를 건너뜁니다." || tar -xzf omega-serv-2.0.1.tar.gz
cd omega-serv/
chmod +x install.sh
./install.sh
```

`install.sh`:

1. 가상 환경 `.venv`가 없으면 만듭니다.
2. 패키지를 설치합니다(`pip install -e .`) — **외부 의존성 없음**(§6 참조).
3. `omega-serv.sh`와 `install.sh`를 실행 가능하게 만듭니다.
4. `~/.bashrc`와 `~/.zshrc`에 별칭 `serv`를 추가합니다(이미 있으면 중복되지 않음).

### 업데이트

`omega-serv/`가 이미 있다면(이전 설치), **이 폴더 안에서 `tar`를 절대 실행하지 마십시오**: 중첩된 `omega-serv/omega-serv/`를 만들려다 실패합니다. omega-fire와 달리 `install.sh`는 폴더 권한을 전혀 건드리지 않으므로(`sudo`를 요구하는 단계가 없음) — 여기서는 폴더가 `root` 소유가 될 위험이 없으며, 기존 설치 위에 바로 압축을 풀어도 안전합니다.

```bash
# omega-serv/의 상위 폴더에서 실행(절대 안에서 실행하지 않음)
tar -xzf omega-serv-2.0.1.tar.gz
cd omega-serv/
./install.sh
```

아카이브는 실행 중인 상태 전체를 의도적으로 제외합니다(`var/db/`, `var/log/`, `var/backups/`, `secure/secrets/`, `secure/certificates/*.key`, `config/omega-serve.json`, **`webroot/` — 실제로 제공 중인 사이트**...) — 덮어써서 압축을 풀어도 데이터, 인증서, 설정, 제공 중인 콘텐츠는 전혀 건드리지 않으며, 애플리케이션 코드만 교체됩니다. `install.sh`는 기존 `.venv`를 재사용하고 그 위에 의존성만 다시 설치합니다.

2026-10-18부터 `var/`와 `secure/auth/`는 비어 있더라도 아카이브에 전혀 포함되지 않습니다: 따라서 덮어써서 압축을 풀어도 그 권한(systemd 서비스 계정과의 공유)이 더 이상 초기화되지 않습니다 — 업데이트 후 「서비스 → 권한 다시 적용」이 더는 필요 없습니다. `install.sh`는 이 폴더들이 없으면 만들고, 이미 있는 것은 결코 건드리지 않습니다.

> ⚠️ **서비스가 이미 실행 중이라면 위 단계만으로는 부족합니다.** 디스크의 코드는 교체되지만, 실행 중인 프로세스는 메모리에 올라간 예전 코드로 계속 동작합니다 — 그 후에는 항상 **완전한 재시작**이 필요합니다:
> ```bash
> sudo systemctl restart <서비스-이름>
> ```
> **단순한 다시 로드로는 절대 안 됩니다**(`systemctl reload`, 또는 SERVICE 화면 → *다시 로드*): 다시 로드는 일부 설정 옵션(WAF 규칙, 인증 영역...)만 다시 읽으며, **Python 코드 자체는 결코 다시 읽지 않습니다**. `systemctl status <서비스-이름>`에 표시된 시작 시각이 업데이트보다 이르다면 여전히 예전 코드로 실행 중이라는 뜻입니다. 항상 같은 폴더를 덮어써서 업데이트한다면(위의 일반적인 경우), 빠진 단계는 이 재시작뿐이며 서비스를 다시 설치할 필요는 없습니다.

> ⚠️ **그 후 서비스가 계속 재시작을 반복한다면**(`systemctl status`가 active/inactive를 오가고, `journalctl -u <서비스-이름>`에 `var/` 아래 파일을 쓸 때의 `PermissionError`가 보임): `tar` 압축 해제는 아카이브에 기록된 대로 폴더 권한을 복원하므로, 처음 설치할 때 전용 시스템 계정을 위해 설정한 권한 공유가 지워질 수 있습니다 — `install.sh` 자체는 이를 건드리지 않는데도 말입니다. 유닛을 다시 설치할 필요는 없습니다: SERVICE 화면 → **퍼미션 복구**(systemd 유닛은 건드리지 않고 `var/`와 `secure/auth/`에 공유를 다시 적용).

### 의존성

서버 핵심부(HTTP/1.1 파서, FastCGI 클라이언트, `hashlib.scrypt`를 통한 비밀번호 해시)는 순수 Python/stdlib로 남아 있으며, TLS 인증서와 관련된 모든 것은 Python 암호화 라이브러리가 아니라 하위 프로세스로 실행되는 `openssl` 실행 파일을 거칩니다 — **이 부분에는 외부 의존성이 없습니다**. 의존성을 추가하는 것은 대화형 인터페이스(§3)뿐입니다: `omega-lib`(테마, 터미널 감지 — 도구 모음 공용 라이브러리로 PyPI에 공개되지 않았으며 배포 아카이브에 포함), `textual`과 `pyte`(인터페이스 안에서 통합 `lnav`를 그리기 위한 터미널 에뮬레이션), `jinja2`(테마가 적용된 HTML 내보내기), `psutil`(상태 및 리소스 화면 — CPU/RAM/디스크/네트워크). 선택적인 개발/테스트 의존성(`pip install -e ".[test]"`): `hypothesis`(HTTP 파서와 경로 해석기의 속성 테스트, 운영 환경에서는 절대 사용하지 않음). 품질 도구(`pip install -e ".[dev]"`): `pytest`, `ruff`, `mypy`, `import-linter`. 추가 선택 항목(`pip install -e ".[magnet]"`): `lupa`(내장 Lua 바인딩, 미리 빌드된 wheel, 시스템의 `lua` 인터프리터 불필요)는 보조 WAF 스크립트 「magnet」(§7) 전용이며 기본으로 설치되지 않습니다. 없으면 정확한 설치 명령과 함께 알려 주고(기능 `waf-magnet`, **기능** 화면), 서버의 나머지 부분은 막지 않습니다.

### 권장 선택 도구

이 도구들이 없으면 인터페이스는 기능을 줄인 모드로 동작합니다:

- `openssl` — TLS 인증서와 관련된 모든 작업(자체 서명, 로컬 CA, 가져오기)에 필요합니다. 없으면 `certs *` 명령은 실패하지만 서버의 나머지 부분은 정상 동작합니다(§9 참조).
- `certbot` — **Let's Encrypt** 마법사와 그 자동 갱신(§9c/9d)에만 필요합니다. 자체 서명/로컬 CA TLS에는 필요 없습니다.
- `lnav` — **로그 관리** 화면(§3)에 통합된 고급 로그 분석. 실행 파일을 찾지 못하면 명확한 오류 메시지를 보이며 충돌하지 않고, 화면의 나머지 부분(보기/추적/순환/통계)은 없어도 정상 동작합니다.
- `scp`(`openssh`/`openssh-clients` 패키지, 거의 항상 이미 설치됨) — **원격 소스(SSH)**(§13a)에만 필요합니다. 없으면 가져오기가 명확한 메시지와 함께 실패하고, 라이브러리의 나머지 부분은 정상 동작합니다.
- `python-psutil`(PyPI의 `psutil`에 해당하는 시스템 패키지) — 어떤 경우든 `pip install -e .`가 자동으로 설치합니다(패키지의 필수 의존성이며 **상태 및 리소스** 화면에 항상 필요). 다만 시스템 패키지 관리자로 미리 설치해 두면 `pip`이 wheel을 직접 빌드하지 않아도 됩니다.

```bash
# Arch Linux 및 파생 배포판
sudo pacman -S openssl certbot lnav python-psutil openssh

# Debian/Ubuntu 및 파생 배포판
sudo apt install openssl certbot lnav python3-psutil openssh-client

# Fedora
sudo dnf install openssl certbot lnav python3-psutil openssh-clients
```

## 3. 사용법

기능적으로 완전히 동등한 두 인터페이스가 있으며, 둘 사이에 로직이 중복되는 일은 없습니다: 비대화형 CLI(스크립트 가능, 아래에서 사용)와 Textual 대화형 인터페이스(메뉴, 양식, 표) — 한쪽의 모든 동작은 CLI 쪽에도 있으며, 인터페이스는 같은 사용 사례를 감쌀 뿐입니다.

### 대화형 모드(TUI)

일상적인 사용에 권장 — 인수 없이 실행합니다:

```bash
./omega-serv.sh
```
별칭을 만들었다면 터미널에 `serv`만 입력하면 됩니다:
```bash
serv
```

### 인터페이스 언어

17개 언어: 프랑스어, 영어, 스페인어, 포르투갈어(브라질), 이탈리아어, 독일어, 네덜란드어, 폴란드어, 러시아어, 중국어, 베트남어, 태국어, 인도네시아어, 일본어, 한국어, 힌디어, 아랍어. 설정(`o` 키, 「Langue / Language」, 이 레이블은 번역하지 않음)에서 고르거나, 일시적으로 `OMEGA_SERV_LANG=en serv`를 씁니다. Linux 텍스트 콘솔(TTY)에서는 콘솔 글꼴에 문자가 없는 언어(베트남어, 중국어, 태국어, 일본어, 한국어, 힌디어, 아랍어)가 해당 세션 동안 영어로 표시됩니다. 힌디어의 경우 결합 문자를 직접 조합하는 터미널(Kitty, Ghostty, Konsole)에서 테두리와 열이 어긋나며 그 정도는 글꼴에 따라 다릅니다: 시작할 때 경고가 표시됩니다. Terminator, GNOME Terminal, Xfce Terminal, Alacritty는 힌디어를 정렬된 상태로 표시합니다. 별도의 설정이 두 가지 있습니다: **방문자 페이지 언어**(오류 페이지, 폴더 목록 — 오류 페이지 화면, 기본값 프랑스어)와 **내보내기 언어**(HTML과 인시던트 보고서 — 설정, 기본값 「인터페이스와 같음」). 서버 로그(`journalctl`)는 프랑스어로 유지됩니다.

### 전체 흐름

시작 화면(스플래시, 키나 클릭으로 닫힘) → 메인 메뉴(첫 실행 마법사 / 기능 레지스트리 / 프로필 / 상세 설정 / 능동 보안 / 로그 관리 / 서비스 / 다중 인스턴스 / 상태 및 리소스 / 감사 / 백업) → 섹션을 고른 다음 동작을 선택, 모든 양식은 계속하기 전에 필수 항목을 검증 → 민감하거나 파괴적인 작업(재시작, 삭제, 복원...) 전에는 명시적 확인 → 제공 중인 설정을 바꾸는 저장 후에는 다음 단계를 항상 표시(자동 핫 리로드, 또는 완전한 재시작 확인). 터미널 적응(색상, 크기, 렌더링 프로필의 구조적 축소)은 자동이며 수동 플래그가 필요 없습니다 — §4 참조.

#### 키보드 단축키(대화형 인터페이스)

| 키 | 동작 |
|---|---|
| `↑` / `↓` | 화면의 요소 사이를 이동 |
| `Tab` / `Shift+Tab` | 양식의 항목 사이를 이동 |
| `Esc` | 이전 화면으로 돌아가기(홈에서는 종료 확인) |
| `t` | 다음 테마(확인 없이 즉시 적용) |
| `r` | 터미널 감지 새로 고침 |
| `F1` | 현재 화면의 도움말(상황별 안내 — 아래 「도움말 가이드」 참조) |
| `a` | 전체 도움말 가이드(탐색 가능한 메뉴 + FAQ) |
| `o` | 애플리케이션 설정(테마, 렌더링 프로필, 내보내기/스크린샷 경로 — 아래 참조) |
| `q` | 종료(확인 포함) |
| `Ctrl+P` | 명령 팔레트(테마, 스크린샷, 옵션...) |

> **예외 — 목록 편집기(WAF → Custom)**: 단축키가 없으며 모든 작업은 마우스로 합니다. 키보드는 입력(문자, Enter, 화살표, Home/End, Page Up/Down, Backspace, Delete)에만 씁니다. `Esc`, `F1`, `Ctrl+P`는 여기서 동작하지 않으며(**도움말** 버튼 사용), `Ctrl+Q`만 동작하고 저장하지 않은 변경이 있으면 확인합니다.

#### 도움말 가이드(`F1`/`a` 키)

단순한 정적 텍스트가 아닌 내장 도움말 시스템입니다: 문서화된 각 화면(정의/구체적인 예가 있는 입력 항목/실행되는 동작/반응 — 다시 로드, 재시작 또는 없음)은 그 화면에서 `F1`로 바로 열 수 있습니다. `a` 키는 전체 메뉴(애플리케이션의 실제 탐색과 동일한 트리)를 열며, FAQ(실제 사용에서 만난 함정, 예: Active Defense의 공격 유형, 공유 서비스 권한)와 가이드 전체의 독립형 HTML 내보내기(현재 테마 유지)로 이어집니다. 개별 안내가 아직 없는 동안에는 일반 참조 화면으로 대체합니다 — 현재는 빠짐없이 다루며, 테스트로 검증합니다.

#### 메인 메뉴(대화형 인터페이스)

- **첫 실행 마법사** — 8단계 안내 과정(환영 → 읽기 전용 기능 확인 → 프로필 선택 → bind/포트 → 선택적 TLS → 확인 → 요약 + 기록 → 서비스 설치 제안). CLI를 몰라도 완전한 설정을 만들고 서버를 실행할 수 있습니다.
- **기능 레지스트리** — 읽기 전용 시스템 조사(init 시스템, 설정한 포트가 이미 사용 중인지, `openssl`/`logrotate`/`tailscale`/`lnav` 유무, 디스크 공간, 파일 디스크립터 한도...), JSON/HTML 내보내기.
- **프로필** — CLI의 `profile`(§5)과 같은 사용 사례이며, 기록 전에 항상 diff를 보여 줍니다.
- **서버 상세 설정** — 별칭/리디렉션/재작성/dirlisting/신뢰 프록시/아웃바운드 리버스 프록시/FastCGI/캐시/인증/접근 제어/오류 페이지의 완전한 CRUD와 하위 메뉴 **TLS**(상태, 자체 서명 생성, 로컬 CA 마법사, Let's Encrypt/Certbot 마법사, 자동 갱신, 폐기, 활성화/비활성화 — §9 참조). 두 번째 틀 **옵션 및 확인**에는 **옵션**(CLI `option`, §7)과 **설정 확인**(CLI `config check`, §10)으로 가는 바로 가기가 모여 있습니다 — 설정을 조정한 뒤 확인하는 같은 흐름이며, 이 두 화면은 더 이상 메인 메뉴에서 바로 열 수 없습니다. WAF는 더 이상 여기에 없습니다(아래 「능동 보안」 참조): WAF가 주로 보여 주는 것은 계속 변하는 운영 상태이지, 단순한 정적 설정 양식이 아니기 때문입니다. 저장할 때마다 다음 단계를 항상 밝힙니다: 서비스가 실행 중이면 자동으로 조용히 핫 리로드(dirlisting, 접근, 별칭/리디렉션/재작성, 캐시, 오류 페이지, 신뢰 프록시, 리버스 프록시/FastCGI 영역, 인증 사용자/영역), 변경이 수신 소켓, TLS, Active Defense에 관련되면 완전한 재시작의 명시적 확인 — 이제 어떤 화면도 서버를 다시 시작해야 하는지 추측하게 하지 않습니다.
- **능동 보안** — 두 블록을 나란히 모은 단일 화면: **Active Defense**(상태, 점수/수준이 있는 추적 중인 위협, 타임라인/IoC 내보내기/보고서가 있는 인시던트, Deception 할당, 드라이런으로 결정 시뮬레이션, **설정** — `config/omega-serve.json`을 직접 편집하지 않는 전체 설정, §11 참조)와 **WAF**(상태, 모듈 — 모드/규칙 팩/차단 목록, 요청 테스트, Custom — 사용자 규칙 작성과 마우스로 편집할 수 있는 경로/키워드 목록 불러오기(§11b 참조), Magnet — 활성화 전에 호환성을 확인하고 외부 `mod_magnet` 스크립트 가져오기) — §11 참조.
- **로그 관리** — 2열 메뉴. **라이브러리** 열: 처리할 모든 로그를 참조하는 중심(수동 추가, 클릭 한 번으로 인스턴스 고유 로그 추가 — access/error/네이티브 WAF, + 켜져 있으면 magnet 스크립트 §7 —, 또는 SSH로 가져온 **원격 소스**, 아래 참조). **즐겨찾기**(로그 + 뷰어 조합을 이름으로 저장해 바로 실행). **로그 보기**는 선택한 로그 수에 따라 3가지 뷰어 중에서 고릅니다 — 단순(실시간 tail + 모든 형식에서 IP/오류/HTTP 코드의 일반 통계), 클래식(읽기 + 추적), 통합 `lnav`(인터페이스 안의 실제 터미널 렌더링, magnet 로그 자동 포함 + 세션 간에 유지되도록 **고정한** 수동 경로). **IP 보기 및 처리**(선택한 하나 이상의 로그의 상위 IP, 기간 24시간/7일/30일/전체, IP 제거). **유지 관리** 열(변경 없음): 수동 또는 크기 기준 자동 순환/보관, 즉시 백업 생성, 예약 자동화 설정/관리(선언적 — 아래 참고 참조), 보관 파일 복원/삭제, 목록 내보내기.
- **서비스** — CLI의 `service`(§12)와 같은 동작. 동작마다 일시적으로 `sudo`로 권한을 올리며, 애플리케이션 전체를 root로 실행하지 않습니다.
- **다중 인스턴스** — 머신에서 알려진 설치의 전역 레지스트리(`~/.config/omega-serv/instances.json`, 어떤 프로젝트 디렉터리에도 속하지 않음)와 각 설치의 systemd 상태. 인터페이스에서 바로 새 인스턴스를 만들 수 있습니다(트리 복사, 전용 가상 환경과 의존성, 다른 포트를 쓰는 새 설정, 중첩과 포트 충돌 검사). 설치가 하나뿐이면 버튼이 사실상 드러나지 않고(2개 이상 알려지면 레이블 「다중 인스턴스」가 「Instances (N)」으로 바뀜), 다른 인스턴스로 완전히 전환할 수 있으며(`os.execv`, 명시적 확인, 재시작 시 전환을 알리는 전용 스플래시), 인스턴스를 완전히 제거할 수도 있습니다(유닛 제거, 다른 인스턴스가 더 이상 쓰지 않으면 전용 시스템 계정 제거, 그리고 선택적으로 디렉터리 삭제 — 기본으로 삭제하는 일은 없음).
- **상태 및 리소스** — 2초마다 새로 고치는 한눈에 보는 개요: 서버 상태(프로세스/PID, 시스템 서비스 상태, 프로필/켜진 옵션/TLS/포트), 실시간 접근 로그 흐름(처리량, 상태 코드별 분포, 고유 IP, 오류율), 시스템 리소스(CPU/RAM/디스크/스왑/부하/네트워크, `psutil` 사용). **요청 시뮬레이션** 바로 가기도 여기에 있습니다(해당 CLI 명령과 같은 사용 사례, §10).
- **보안 감사** — 해당 CLI 명령과 같은 사용 사례(§10).
- **설정 백업** — 설정 파일의 tar.gz 아카이브와, 명시적으로 고르면 WAF 규칙/인증 영역/인증서(실제 비밀 정보를 포함하면 확인 필수)/Active Defense 데이터베이스, 복원, 목록, 삭제.

> 예약된 순환 자동화에 대한 참고: 이것들은 저장되지만(빈도 + 대상 로그) **자동으로 실행하는 것은 아무것도 없습니다** — 인터페이스에서도, 백그라운드 작업으로도 마찬가지입니다. 같은 선언적 동작을 하는 `omega-fire`의 해당 화면과 맞추기 위한 의도적인 선택입니다. 실제 주기적 실행(systemd 타이머, 백그라운드 작업)은 필요성이 확인되면 따로 만들 예정입니다.

#### 애플리케이션 설정(`o` 키 또는 명령 팔레트)

인터페이스 환경설정일 뿐이며, `config/omega-serve.json`(서버 설정)과 섞이지 않습니다: 현재 테마, 렌더링 프로필(`complete`/`standard`/`reduced`/`mono`, 재시작 필요), 내보내기 경로(기본값 `var/exports/`), 스크린샷 경로(기본값 `var/screenshots/`), 두 폴더 중 하나의 비우기(확인 필수).

```bash
# 서버 실행(포그라운드, SIGTERM = 유예 기간이 있는 정상 종료, SIGHUP = WAF/Auth 핫 리로드)
./omega-serv.sh serve

# 설정
./omega-serv.sh config init                # config/omega-serve.json 생성(기본값은 안전한 값)
./omega-serv.sh config check                # 시작하지 않고 확인(시작 시와 같은 차단 게이트)
./omega-serv.sh config show
./omega-serv.sh config enable-tls --cert ... --key ... --mode direct
./omega-serv.sh config disable-tls

# 프로필(minimal / standard / hardened / development)
./omega-serv.sh profile list
./omega-serv.sh profile show hardened
./omega-serv.sh profile apply hardened --dry-run   # 적용 전에 항상 diff 확인

# 옵션(aliases, redirects, rewrites, dirlisting, cache, waf, upload, fastcgi, reverse_proxy...)
./omega-serv.sh option list
./omega-serv.sh option enable waf
./omega-serv.sh option disable waf

# 서버를 실행하지 않고 요청 시뮬레이션(활성화 전 규칙 검증에 유용)
./omega-serv.sh simulate-request GET /index.html

# WAF(옵션이 꺼져 있어도 암묵적 --force로 동작)
./omega-serv.sh waf test --method GET --path /admin --remote-ip 203.0.113.1
./omega-serv.sh blocklist list
./omega-serv.sh blocklist add --network 203.0.113.0/24 --reason "scan detecte" --duration-seconds 3600
./omega-serv.sh blocklist remove --network 203.0.113.0/24

# Active Defense(deception + 전쟁 모드, 옵션 "active_defense" - §11 참조)
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

# TLS 인증서 - 자체 서명(9a)
./omega-serv.sh certs generate-self-signed --cn localhost --san-dns localhost --san-ip 127.0.0.1
./omega-serv.sh certs show
./omega-serv.sh certs check-expiry --warn-days 30

# TLS 인증서 - 로컬 CA(9b)
./omega-serv.sh certs generate-ca --cn "Mon CA locale" --days 3650
./omega-serv.sh certs generate-csr --cn serveur.local --san-dns serveur.local --key-out server.key --csr-out server.csr
./omega-serv.sh certs sign-csr --csr server.csr --ca-key secure/certificates/ca/root-ca.key --ca-cert secure/certificates/ca/root-ca.pem --out server.pem --fullchain-out fullchain.pem
./omega-serv.sh certs revoke --cert server.pem --ca-key secure/certificates/ca/root-ca.key --ca-cert secure/certificates/ca/root-ca.pem

# TLS 인증서 - 가져오기(9c, 예: Certbot 훅에서)
./omega-serv.sh certs import --key privkey.pem --cert fullchain.pem

# HTTP Basic 인증
./omega-serv.sh auth add-user --username alice
./omega-serv.sh auth create-zone --url-prefix /admin/ --allowed-users alice
./omega-serv.sh auth list

# 보안 감사(절대 차단하지 않으며 정보 제공용)
./omega-serv.sh audit security --format text --min-severity medium

# 설정 백업(설정은 항상 포함, 실제 비밀 정보는
# 기본으로 암호화되지 않음, 포함하려면 --confirm-secrets 필수)
./omega-serv.sh config backup --description "avant migration"
./omega-serv.sh config backup --include-auth --include-certificates --confirm-secrets
./omega-serv.sh config backup --include-active-defense --description "menaces/incidents"
./omega-serv.sh config list-backups
./omega-serv.sh config restore --snapshot-id snapshot_20260908_170003_762484

# 시스템 서비스(systemd/OpenRC/runit, 자동 감지)
./omega-serv.sh service install --user omega-serv --group omega-serv
./omega-serv.sh service start
./omega-serv.sh service status
```

### 주요 종료 코드

| 명령 | 코드 | 의미 |
|---|---:|---|
| `audit security` | `0` | 심각한 문제 없음(`CRITICAL`/`HIGH` 없음) |
| `audit security` | `1` | `CRITICAL` 지적 사항이 적어도 하나 |
| `audit security` | `2` | `CRITICAL` 없이 `HIGH`가 적어도 하나 |
| `audit security` | `3` | 실행 오류(설정을 찾을 수 없음...) |
| `certs check-expiry` | `1` | 인증서 만료 |
| 그 밖의 모든 명령 | `0`/`1` | 성공 / 검증 실패 |

## 4. 터미널 호환성

대화형 인터페이스([Rich](https://rich.readthedocs.io/) 위에 구축된 [Textual](https://textual.textualize.io/))는 터미널의 기능(에뮬레이터, 크기)을 자동으로 감지하고 그에 맞게 구조적 스타일시트(`complete`/`standard`/`reduced`/`mono`)를 조정하며, 수동 플래그가 필요 없습니다. CLI 모드는 항상 일반 텍스트이며 터미널과 무관합니다. `omega-` 도구 모음 전체가 공유하는 정책(`omega-lib`, `terminal/policies.py`)으로, `omega-check`/`omega-fire`와 동일합니다.

### 감지된 에뮬레이터에 따른 프로필

| 에뮬레이터 | 초기 프로필 |
|---|---|
| Ghostty, Alacritty, WezTerm, Kitty | `complete` |
| Konsole, GNOME Terminal, Terminator, Xfce4 Terminal | `standard` |
| xterm, urxvt, 최신 SSH | `reduced` |
| Linux TTY, 오래된 SSH | `mono` |
| 알 수 없는 에뮬레이터 | `reduced`(기본 대체값) |

### 터미널 크기에 따른 프로필

| 최소 크기(열 × 줄) | 프로필 상한 |
|---|---|
| 120 × 32 | `complete` |
| 100 × 28 | `standard` |
| 80 × 24 | `reduced` |
| 그 미만 | `mono` |

최종적으로 선택되는 프로필은 **두 가지(에뮬레이터와 크기) 중 더 제한적인 쪽**입니다 — 전체 화면 Ghostty를 70열로 줄이면, 에뮬레이터로는 `complete`가 허용되더라도 `mono`로 내려갑니다. `r` 키로 즉시 새로 고칠 수 있고, 애플리케이션 설정(`o` 키, §3)에서 수동으로 덮어쓸 수도 있습니다.

## 5. 프로필

| 프로필 | 의도한 용도 |
|---|---|
| `minimal` | 데모/단순한 로컬: 정적 콘텐츠만, 켜진 옵션 없음 |
| `standard` | 정적 사이트 또는 소규모 운영: 일반적인 헤더, 기본 CSP, dirlisting/CGI/FastCGI 비활성화 |
| `hardened` | 최소 권한 노출: 기본은 로컬 bind(인터넷에는 리버스 프록시 권장), 메서드는 GET/HEAD로 제한, 엄격한 CSP, slowloris 방어 — 여기서도 WAF가 자동으로 켜지는 일은 **절대** 없음 |
| `development` | 로컬 개발 전용이며 인터넷에 적합하다고 소개되지 않음: 루프백 bind 필수, report-only CSP, 상세한 오류 페이지 |

설정 병합 순서: 내장된 안전한 값 → 선택한 프로필 → 현재 켜진 옵션 유지(프로필을 바꿔도 남음) → 사용자의 명시적 덮어쓰기. 기록 전에는 항상 완전한 diff가 표시됩니다(`profile apply`).

## 6. 아키텍처

Clean Architecture(`core / domain / ports / application / infrastructure / interfaces / bootstrap`) — `bootstrap/`이 컴포지션 루트입니다(도구 모음의 다른 도구의 `app/`에 해당). 이 프로젝트에서 받아들인 특성이며, 가정이 아니라 `import-linter`로 검증합니다: `application/server/start_server.py`(그리고 `validate_config.py`, `run_audit.py`)는 **실제 설정에 의존하는 조립 팩토리**(어떤 서비스 관리자인지, WAF를 켤지...) 역할을 하며 구체적인 `infrastructure/` 어댑터를 직접 생성합니다 — `application/`이 `ports/`만 사용하는 CHECK/TRACK의 더 엄격한 패턴과는 다릅니다. 실제로 강제하는 유일한 보편 규칙: `domain/`/`core/`는 바깥 계층에 결코 의존하지 않습니다.

```text
src/omega_serv/
├── core/            계층 공통 어휘(platform_info, 상수)
├── domain/           순수 비즈니스 로직(HTTP, 설정, WAF/TLS/auth/audit 보안, 라우팅)
├── ports/            애플리케이션이 기대하는 계약(Protocol)
├── application/      사용 사례 - 일부 함수(build_server...)는 구체 어댑터도 조립함(위 참조)
├── infrastructure/    실제 구현(asyncio, subprocess로 openssl, systemd/OpenRC/runit, 파일)
├── interfaces/cli/    비대화형 argparse CLI
├── interfaces/tui/    Textual 대화형 인터페이스(같은 사용 사례, 로직 중복 없음)
└── bootstrap/         DependencyContainer, 프로젝트 루트 해석
```

`import-linter`가 검증하는 규칙(계약 8개): `domain`/`core`는 바깥 계층에 결코 의존하지 않음. `interfaces.tui`는 `infrastructure`에 결코 직접 의존하지 않음. `textual`은 `interfaces.tui`에 한정. `subprocess`는 `infrastructure/process/subprocess_runner.py`(그리고 대화형 PTY 흐름인 `infrastructure/lnav/`)에 한정. `ssl`은 `infrastructure/tls/ssl_context_builder.py`에 한정. `jinja2`는 `infrastructure/exporters/html_exporter.py`에 한정. `sqlite3`는 `infrastructure/persistence/sqlite_active_defense_connection.py`에 한정(프로젝트의 유일한 관계형 저장소이며 Active Defense 전용 — §11 참조). `lupa`는 `infrastructure/waf/lua_waf_adapter.py`에 한정(보조 WAF 스크립트 「magnet」, §7).

## 7. 선택 모듈

제공되는 모든 프로필에서 기본은 비활성화이며 — 활성화는 항상 명시적입니다(`option enable <이름>` 또는 `config enable-tls`):

| 모듈 | 역할 |
|---|---|
| `waf` | 시그니처(민감한 경로, 스캐너 UA/Referer, 본문 안의 SQLi/XSS/CMDi), 텍스트 파일로 편집할 수 있는 목록(키워드, 또는 `!` 예외가 있는 민감한 경로, 목록마다의 관찰 모드와 재범 — 참조 목록 두 개 제공, 명시적으로 불러오기, §11b 참조), 요청 제한(토큰 버킷, 폴더별 및 IP/네트워크별 규칙, §11c 참조), 차단 목록(CIDR + 만료), 평판/에스컬레이션, 기존 Lighttpd용 WAF 스크립트 `mod_magnet`을 「magnet」 형태의 선택적 보강으로 가져오기(다시 쓰지 않음, 추가 항목 `pip install -e ".[magnet]"` — 가산적이며 네이티브 차단을 결코 해제할 수 없음. 가져올 때 호환성 확인, 전용 TUI 화면) — `log-only` 모드는 구조적으로 차단할 수 없음 |
| TLS | 직접(자체 서명, 로컬 CA, 또는 자동 갱신되는 Let's Encrypt/Certbot 공개 인증서 — §9 참조), V1에는 mTLS/OCSP 없음 |
| 인증 | 영역별 HTTP Basic(`url_prefix`), 타이밍 공격 방어가 있는 `hashlib.scrypt`(알 수 없는 사용자에게도 일정한 시간) |
| FastCGI/PHP-FPM | `(url_prefix, script_root)`는 하나뿐이며, `script_root`는 설계상 `webroot/` 밖에 한정(정적 처리기가 PHP 소스를 노출할 수 없음) |
| 아웃바운드 리버스 프록시 | Omega-serv 자신이 하나 이상의 백엔드로 가는 프록시로 동작(`server.tls.mode = "behind_proxy"`와 반대 방향) — 부하 분산(round-robin, 가중치, least-connections, ip-hash, least-response-time, 실제 부하), 세션 고정과 헤더 기반 라우팅 규칙, 수동적·능동적 상태 점검, 응답 캐시(`Vary`에 따른 여러 변형), 백프레셔, 루프 방지, 실시간 관리 API — 자세한 내용은 §7a 참조 |
| 업로드 | 격리된 영역, 영역별 할당량, 서버가 생성하는 파일 이름 — V1에는 스트리밍 없음(`server.max_request_size`로 제한) |
| `active_defense` | 이미 계산된 WAF 신호를 바탕으로 한 Deception + 전쟁 모드(두 번째 점수를 매기지 않음): 정적 미끼, 대상을 좁힌 감속/상세 로그/요청 제한, 인시던트 + IoC 내보내기 — §11 참조 |

### 7a. 아웃바운드 리버스 프록시 — 상세

OMEGA-SERV는 스스로 하나 이상의 HTTP/HTTPS 백엔드로 가는 리버스 프록시로 동작할 수 있습니다 — `server.tls.mode = "behind_proxy"`(OMEGA-SERV가 프록시 **뒤에** 있는, 반대 메커니즘)와 절대 혼동하지 마십시오. 영역은 완전한 CRUD로 설정할 수 있고(TUI: *상세 설정 → Reverse Proxy*), 영역마다 하나 이상의 upstream을 둡니다.

- **부하 분산** — `round_robin`(기본값), `weighted_round_robin`/`weighted_least_connections`/`ip_hash`(가중치), `least_connections`, `least_response_time`, `real_load`(실제 부하). 네이티브 `real_load` 모드(프로브 `/.omega-serv-load/`, 「상태 및 리소스」 화면과 같은 `psutil` 측정값을 재사용하며 두 번째 호출은 하지 않음) 또는 선언적 모드(서드파티 HTTP 프로브, 최소 형식 `{"load_percent": ...}` 또는 숫자만) — upstream 단위로 세분화되며, 한 영역에서 둘을 섞을 수 있습니다.
- **세션 고정과 조건부 라우팅** — 불투명한 sticky 쿠키(실제 host:port를 클라이언트에 결코 노출하지 않음)와 헤더 기반 규칙(같음 또는 접두사). 둘 다 대상 upstream의 적격성으로 걸러집니다(대상 upstream을 쓸 수 없으면 현재 전략으로 깔끔하게 되돌아감).
- **상태 점검** — 수동적(연속 실패/성공, 깜빡임을 줄이기 위해 down/up 전환 임곗값을 따로 둠) **그리고** 능동적(실제 트래픽과 무관한 주기적 프로브, upstream마다 선택, 실제 부하와 같은 백그라운드 작업 메커니즘을 재사용). 상태 `DOWN`(항상 자동), `DRAINING`/`MAINTENANCE`(항상 수동, 명백히 일시적이며 결코 저장되지 않음) — 수동으로 설정한 upstream은 이미 맺어진 연결을 끊지 않으면서 새 선택에서만 제외됩니다. 다른 upstream으로의 자동 재시도는 멱등 메서드(GET/HEAD/OPTIONS)이면서 연결 오류일 때만 합니다.
- **백프레셔** — upstream마다 설정할 수 있는 활성 연결 상한. 포화된 upstream은 503으로 깔끔하게 거절하며, 고장 난 upstream(502, 그래도 재시도됨)과 구별됩니다.
- **응답 캐시** — GET/HEAD만, 오류 응답은 결코 캐시하지 않고, 영역에서 명시적으로 허용하지 않는 한 `Set-Cookie`도 캐시하지 않습니다. upstream의 `Cache-Control`/`Vary`를 존중합니다(끌 수 있지만 위험한 옵션이며, TLS 검증과 같은 철학). 같은 리소스의 여러 변형(`Vary`)이 실제로 디스크에 함께 존재하며, 단순히 「나중에 온 것이 이기는」 방식이 아닙니다. 스탬피드 방지 잠금(동시 요청 중 하나만 실제로 캐시를 다시 구성). 모든 응답에 진단 헤더 `X-Omega-Cache: HIT`/`MISS`/`BYPASS`. 전용 TUI 화면(*리버스 프록시 캐시*)에서 감시/비우기.
- **루프 방지** — hop-by-hop 헤더 제거, `X-Forwarded-*`는 항상 덮어씀(클라이언트의 것과 결코 합치지 않음), 중계할 때마다 카운터 `X-Omega-Proxy-Hops` 증가(5홉을 넘으면 깔끔하게 거절 — 로컬 설정 검증만으로는 결코 보이지 않는, 두 인스턴스 사이의 간접 루프를 감지).
- **WebSocket** — 영역별로 업그레이드를 허용할 수 있으며, 연결된 뒤에는 통로가 유지되는 동안 하나의 upstream에 고정되고 애플리케이션 수준 타임아웃이 없습니다.
- **실시간 관리** — 작은 로컬 HTTP API(`/.omega-serv-admin/`, 네이티브 부하 프로브처럼 `trusted_proxy`로 보호)로 TUI가 백엔드의 DRAINING/MAINTENANCE 상태를 읽거나 강제하고, **실제로 실행 중인 서버**의 캐시 적중/실패 비율을 읽을 수 있습니다(전용 화면 *백엔드 실시간 상태*) — TUI와 서버는 메모리를 공유하지 않는 별개의 두 프로세스이므로, 이 로컬 HTTP 채널이 둘을 잇는 유일한 다리입니다.

## 8. HTTP 강화(끌 수 없음)

- 헤더/요청 줄은 읽는 **도중에** 제한하며(나중이 아님), 오래된 헤더 접기는 거부하고, `Transfer-Encoding`은 항상 거부합니다(추측하지 않음).
- 중복된 `Content-Length`는 거부. `Expect: 100-continue`는 깔끔하게 거부(417).
- 명시적인 메서드 허용 목록(아니면 405 + `Allow`), `Host` 헤더 검증(없음/비어 있음/같아도 중복/제어 문자 → 400).
- 보안 헤더와 기본 CSP(`enforce`/`report-only`)를 오류를 포함한 **모든** 응답에 적용 — 옵션으로 우회할 수 없습니다. `Cross-Origin-Opener-Policy`/`Cross-Origin-Resource-Policy`는 항상 `same-origin`이며, 사이트를 망가뜨릴 실제 위험이 없습니다. `Cross-Origin-Embedder-Policy`는 항상 명시적으로 보내며(결코 빠지지 않음 — 외부 스캐너가 「고려하지 않음」과 「의도적으로 허용」을 구별할 수 있음), `hardened`를 포함한 **모든** 프로필에서 기본값은 `unsafe-none`입니다: 앞의 두 가지와 달리 `require-corp`/`credentialless`는 실제로 제공하는 사이트 고유의 교차 출처 리소스(글꼴, 이미지, 서드파티 iframe)를 막을 수 있기 때문입니다 — 조정 가능(`security.coep_mode`). CSP 영역(`security.csp_zones`): 경로 접두사별 **명시적** 예외(예: 정말로 필요한 `/un-dossier/` 아래에서만 `unsafe-inline`)이며, 각 영역은 그 접두사에 대해 기본 정책을 완전히 대체합니다 — 결코 병합하지 않고, 결코 전체적으로 완화하지 않습니다. 모든 예외는 의도적이더라도 `audit security`에 계속 보입니다(CSP-001/CSP-002는 영역도 검사). 지시어별 마법사(**일반 보안** 화면)로 만들 수 있으며, 각 항목에는 전역 정책의 **현재** 값이 미리 채워집니다 — 빈 항목에서 시작해 다른 지시어를 무심코 잃는 대신 바꿔야 할 것만 바꾸기 위해서입니다. 조립한 영역이 `unsafe-inline`/`unsafe-eval`/일반 출처 `*`를 완화하면 추가로 명시적 확인을 요구합니다.
- IPv4 매핑 IPv6 주소(`::ffff:x.x.x.x`)는 모든 비교(차단 목록, 신뢰 프록시, 요청 제한) 전에 정규화합니다 — 그렇지 않으면 알려진 우회 수단이 됩니다.
- 일반적인 단위/통합 테스트에 더해, HTTP 파서와 경로 해석기에 대한 속성 테스트(`hypothesis`, 생성된 예제 수천 개)로 검증합니다.

## 9. TLS

### 9a. 자체 서명 인증서(최소)

로컬/실험실/VPN(Tailscale...)의 현실적인 용도를 다룹니다: 단일 리스너, 직접 `ssl.SSLContext`, RSA 2048/4096 또는 ECDSA P-256/P-384.

### 9b. 로컬 CA

인증서를 하나씩 다시 가져오지 않고도 신뢰해야 하는 여러 클라이언트 기기용: 로컬 인증 기관이 필요한 만큼 서버 인증서에 서명합니다.

```text
secure/certificates/ca/
├── root-ca.key    # 0600 - 프로젝트에서 가장 민감한 요소
├── root-ca.pem    # 0644 - 클라이언트의 신뢰 저장소로 가져올 것
├── serial.txt     # 0600 - 다음 일련번호 관리
└── index.txt      # 0600 - 서명한 인증서별 V(유효)/R(폐기) 상태 관리
```

흐름: `certs generate-ca`(CA 키 암호 문구 **필수**, `--password`를 생략하면 이중 확인이 있는 대화형 입력) → `certs generate-csr`(서버 키 + CSR) → `certs sign-csr`(CA로 서명, CSR의 SAN 복사, 요청하면 `fullchain.pem` 생성) → `tls.certificate.certificate_path`를 이 `fullchain.pem`으로 지정. 유출된 인증서는 `certs revoke`로 철회합니다(`index.txt`에 표시하며, 먼저 그 인증서가 정말 이 CA에서 나왔는지 확인 — 아니면 거부). V1에는 CRL 배포도, 외부 CA/제3자 기관용 CSR도, mTLS도 없습니다(§15 참조).

### 9c. Let's Encrypt / ACME(Certbot) — 공개, 자체 호스팅

브라우저가 인정하는 인증서를 쓰는 진짜 공개 사이트를 위한 완전한 자체 호스팅 구성: DDNS(Dynu 또는 동등한 서비스, 전적으로 운영자 책임) → Certbot → Omega-serv. TUI 마법사만 있습니다(`상세 설정 → TLS → Let's Encrypt 마법사`) — `certbot certonly --webroot`를 하위 프로세스로 호출하며(**절대** `--standalone`은 쓰지 않음, 포트 80은 이미 Omega-serv가 사용 중. ACME 클라이언트를 다시 구현하는 일도 **절대** 없음), `--config-dir`/`--work-dir`/`--logs-dir`은 프로젝트의 `secure/certificates/letsencrypt/`를 가리킵니다 — **절대** `/etc/letsencrypt/`가 아님 — 덕분에 Certbot 자체가 완전히 비특권으로 동작합니다. 받은 인증서는 자동으로 가져오며(`certs import`와 같은 메커니즘, 위의 CLI 예 참조), 갱신용 훅 스크립트가 기록됩니다. 테스트 모드(staging)가 기본으로 선택되어 있습니다 — Let's Encrypt의 실제 요청 한도를 피하려면 도메인/webroot가 동작함을 확인한 뒤 선택을 해제하십시오.

Omega-serv 범위 밖의 필요 조건: 공인 IP를 가리키는 도메인(DDNS), 그리고 이 머신으로 전달되는 포트 80/443.

### 9d. 자동 갱신(Certbot)

`상세 설정 → TLS → 자동 갱신`은 **이 인스턴스에서** 실제로 감지된 서비스 관리자에 맞춰 동작합니다(여러 인스턴스가 공유하는 메커니즘은 결코 쓰지 않음): systemd → 타이머(`<service>-certbot-renew.timer`, 하루 두 번 + 무작위 지연, 인스턴스의 `--config-dir`로 범위를 정한 `certbot renew`)를 생성해 설치. 아니면 → `crontab`이 있으면 crontab 줄(현재 사용자, 권한 불필요). 그것도 아니면 → 수동 안내를 표시하며 강제로 기록하지 않음. 일부 배포판(Arch/Manjaro 포함)에서는 Debian/Ubuntu와 달리 Certbot 패키지가 기본으로 타이머를 **하나도** 설치하지 않습니다 — 그래서 이미 있다고 가정한 메커니즘을 확인만 하는 대신 이 화면을 둡니다. 설정한 뒤에는 갱신할 때마다 인증서를 자동으로 다시 가져오고(`certs import`) 서비스를 재시작하므로, 더 이상 손으로 할 일이 없습니다.

## 10. 보안 감사

`audit security`는 **차단하지 않습니다**: `config check`의 차단 게이트를 `CRITICAL`로 다시 실행한 뒤, 권고 규칙(TLS, CSP, 위험한 메서드, 타임아웃, 순수 업로드 위생, 파일 권한, 인증서 만료, 설치된 systemd 유닛, 실제 I/O로 본 로그 크기)을 적용합니다. `WAF-001`(WAF가 `log-only`로 남아 있음)은 작은 상태 파일(`var/run/waf-mode-state.json`)로 시간에 걸쳐 관찰되며 — 반복 실행에서 `log-only`가 14일 이상 관찰된 뒤에만 발생하고, 첫 `audit`에서는 발생하지 않습니다.

## 11. Active Defense(deception + 전쟁 모드)

선택 모듈(`option enable active_defense`, 기본 비활성화)로, 이미 계산된 WAF 신호(`WafDecision`/평판/차단 목록 — 독립적인 두 번째 점수 계산은 결코 하지 않음)에서 적대적 행동을 판정하며, 출처를 미끼로 돌리고, 응답을 늦추며 더 자세히 기록하고, 활용할 수 있는 인시던트를 만든 뒤, 침해 지표(IoC)를 내보낼 수 있습니다. 트래픽 자체를 차단하지는 않습니다 — 네트워크 차단은 여전히 `omega-fire`의 몫이며, Active Defense는 관찰하고, 우회시키고, 늦추고, 기록합니다.

**위협과 점수**: 각 출처(`IP + User-Agent의 SHA-256 해시`)는 점수를 쌓으며(차단한 `WAF-001` +10, 평판 에스컬레이션 +25, 이미 알려진 차단 +25, 이미 할당된 미끼로의 POST +30 — 새 이벤트 없이 15분마다 -5 감소) `normal`/`suspicious`/`hostile`/`contained`로 분류됩니다(`contained`에는 이미 알려진 차단도 필요). `mode: monitor`는 행동하지 않고 관찰만 하며, `mode: enforce`는 아래 동작을 실제로 적용합니다.

**전쟁 모드**(`options.active_defense.settings.war_mode`): 설정 가능한 임곗값으로 발동되는 `DefensePlaybook`(`actions: ["redirect_to_decoy", "enrich_log", "delay", "rate_limit", "create_incident", "export_ioc"]`)을 `normal`이 아닌 모든 출처에 적용합니다:
- `enrich_log` — 별도의 JSONL 로그(`var/log/active-defense-enriched.jsonl`, WAF/운영 로그와 결코 섞지 않음), 헤더는 가림 처리, HTTP 본문은 `logging.capture_request_body`에 따라 해시(SHA-256)하거나 잘라냄.
- `delay` — 상한과 지터가 있는 감속(`war_mode.slowdown.minimum_ms`/`maximum_ms`/`jitter_ms`), asyncio 루프를 결코 막지 않음.
- `rate_limit` — 출처별 전용 요청 제한(`war_mode.rate_limit.requests`/`window_seconds`), 별도의 키로 WAF와 같은 메커니즘을 재사용.
- `create_incident` — `thresholds.incident_score`를 넘으면 인시던트를 자동으로 열거나 병합.

**Deception**: `hostile`/`contained` 출처는 관찰된 공격 유형(`deception.profiles.<이름>.match_attack_classes`, `scan`/`credential_stuffing`/`sqli`/`xss`/`path_traversal`/`upload_probe`/`api_probe`/`unknown` 중 하나 이상)에 따라 고른 정적 미끼(`fake_admin`, `fake_cms`, `fake_api`, `fake_secrets` — 그럴듯하지만 항상 고정된 응답이며, 실제 파일을 읽거나 하위 프로세스를 실행하지 않음)에 할당될 수 있습니다. 격리 수준은 두 가지이며, 그대로 받아들이고 문서화합니다:
- **수준 1**(프로세스 내 fixture, `isolation_level: "fixture"`, 기본값) — 명시적으로 약한 격리: 운영과 같은 프로세스, 같은 OS 사용자이며, fixture가 정적 템플릿을 돌려주는 것 외에는 아무것도 하지 않기 때문에만 허용됩니다. 프로필 이름은 위의 4가지 fixture 중 하나와 정확히 같아야 하며 — 아니면 검증(`validate_active_defense_config`)에서 거부됩니다. 이름이 잘못된 미끼가 조용히 한 번도 작동하지 않는 함정을 피하기 위해서입니다.
- **수준 2**(실제로 격리된 백엔드, `isolation_level: "proxy"`) — `options.active_defense.settings.deception.decoy_zones.<이름>`(이미 실행 중인 서버의 upstream `host`/`port`, 자동으로 만들지 않음. `options.reverse_proxy`에서 읽지 않음 — 미끼가 실수로 운영 영역을 가리킬 수 없으며, `config check`에서 검증)을 통해 별도 프로세스로 중계하며, 운영과 같은 아웃바운드 리버스 프록시 메커니즘(`serve_proxy()`)을 재사용합니다 — 실제 요청 시점에 upstream에 닿을 수 없으면 공격자에게 502를 돌려주며, 결코 충돌하지 않습니다.

**설정 화면**(TUI, 능동 보안 → Active Defense → 설정): 위의 모든 것을 빠짐없이 설정 — 모드, 전쟁 모드 활성화, 범위/동작/임곗값/감속/요청 한도, deception(기본 동작, 미끼 프로필과 미끼 영역의 CRUD, 각 항목에 예시 값 표시), IoC, 저장과 로그 — 저장할 때마다 CLI와 같은 규칙으로 검증하며, `config/omega-serve.json`을 손으로 편집할 필요가 전혀 없습니다. 변경 후에는 항상 완전한 재시작이 필요합니다(Active Defense는 결코 핫 리로드되지 않음).

**인시던트와 IoC**: 인시던트별 완전한 타임라인, 지표 추출(IP, 해시한 User-Agent), 버전이 있는 JSON/공유 가능한 IoC로 한정한 CSV/Markdown 보고서 내보내기, 그리고 교환 형식 **STIX 2.1**(OpenCTI, SIEM 등에 불러올 bundle)과 **MISP**(MISP 인터페이스로 가져올 이벤트). 기본으로 TLP:AMBER 표시 — 로컬 파일이며 결코 전송하지 않습니다. 모든 내보내기에는 `<export>.sha256` 파일(표준 `sha256sum` 형식)이 함께 붙습니다. `ioc.auto_export_on_close`(기본값 true)이면 인시던트를 닫을 때 자동으로 내보냅니다. 만료된 상태와 감사 로그는 자동으로 정리되며, 데이터베이스에는 상한이 있습니다(디스크 가득 참 방지). `active-defense purge`는 다시 조용해진 인시던트도 닫습니다.

**시뮬레이션**: `active-defense simulate`(CLI)와 「시뮬레이션」 버튼(TUI, 능동 보안 화면)은 점수/수준을 예측하고 발동될 각 동작을 설명합니다 — 엄격한 드라이런이며, 실제 기록도 네트워크 영향도 없습니다.

백업/복원: `config backup --include-active-defense`는 sqlite 데이터베이스(위협/인시던트/할당)를 아카이브에 포함합니다 — 평문 비밀 정보가 결코 없으므로 `--include-auth`와 달리 `--confirm-secrets`가 필요 없습니다.

## 11b. 민감한 경로 목록(WAF)

WAF는 한 줄에 경로(또는 키워드) 하나씩을 쓴 **편집 가능한 목록**을 텍스트 파일로 **능동 보안 → Custom → 추가 → 「목록 불러오기」**에서 불러올 수 있습니다. 기본으로 불러오는 것은 없습니다: 명시적인 동작입니다.

- **제공되는 참조 목록**: `sensitive-paths-hostile`(정당한 용도가 없는 경로 298개: 비밀 정보, 백업, VCS, 콘솔…)과 `sensitive-paths-probe`(탐색용 경로 132개, 실제 사이트가 제공하기도 함: `/admin`, `/api`, 모니터링…). 불러올 때 `secure/waf/rules/keywords/`에 **로컬 사본**이 만들어집니다: 고치는 것은 이 사본이며, omega-serv 업데이트가 이를 덮어쓰는 일은 없습니다(이후 「참조본의 새 항목」이 새 항목을 하나씩 제안).
- **문법**: `/admin`(→ `/admin`과 `/admin/xxx`, `/administrator`는 절대 포함하지 않음), `/.git/`(그 아래 전부), `/*.bak`(확장자), `!/api/v1`(예외, 항상 우선). 경로는 엔진과 똑같이 디코딩됩니다(`%2e`, 이중 인코딩, 전각 문자).
- **심각도**: *관찰*(로그만, 처음 불러올 때 권장), 그다음 보통(혼자서는 결코 차단하지 않음) 또는 높음(첫 접근부터 403).
- **목록마다의 재범**: 첫 접근 = 정보 또는 거부. M분 안에 N회 접근 = 일시적인 애플리케이션 차단(응답 451, Tailscale을 거쳐도). 반복된 차단 = omega-jail에 의한 네트워크 차단. 참조값: hostile은 10분에 2회 → 24시간, probe는 10분에 5회 → 1시간.
- 로컬 호스트, Tailscale(`100.64.0.0/10`), 로컬 네트워크(`options.waf.reputation.never_auto_block`)는 **결코 자동 차단되지 않습니다**: 차단될 수 있는 것은 외부 트래픽뿐입니다. 로컬 프록시 뒤에서는 `127.0.0.1`을 면제하려면 `trusted_proxy`가 켜져 있어야 합니다. `X-Forwarded-For`는 오른쪽에서 왼쪽으로 읽으므로, 클라이언트가 자신을 로컬이라고 주장할 수 없습니다.
- **안전장치**: 핵심 경로 보호(`/`, `robots.txt`, `sitemap.xml`, `/.well-known/acme-challenge/`…), 실제로 제공 중인 경로(별칭, 리버스 프록시, Auth 영역, webroot)에 걸리는 차단 목록 거부, 편집기의 **「내 로그와 대조」**(성공한 요청에 걸렸을 줄, 클릭 한 번으로 예외).
- **내장 편집기**: 줄 번호가 있는 실시간 진단, 경로 「테스트」, 안전한 기록(권한과 그룹 유지, 심볼릭 링크 거부, 외부 수정 감지), 서비스 계정의 읽기 가능 여부 확인(「권한 수정」), 그리고 **정직한** 다시 로드: 목록이 검증을 통과하지 못하면 이유와 함께 거부되며, 서버는 현재 규칙을 유지합니다.

## 11c. 폴더별 및 IP/네트워크별 요청 제한(WAF)

WAF의 요청 제한(토큰 버킷, `options.waf.rate_limit`, 기본값 IP당 60요청 / 60초)은 **능동 보안 → 제외 및 요청 제한**에서(또는 직접 `rate_limit.path_policies` / `rate_limit.source_policies`로) 세밀하게 조정할 수 있습니다:

- **폴더별 규칙**(`prefix`, `requests`, `window_seconds`): 그 폴더에 대해 전역 제한을 **대체**하며, 자체 카운터를 가집니다(`requests: 0` = 무제한). 가장 긴 접두사가 이기며, `/images`는 `/images/a.png`를 포함하지만 `/images2`는 결코 포함하지 않습니다. 대표적으로 429를 돌려주는 무거운 페이지(이미지 갤러리)에 씁니다.
- **IP/네트워크별 규칙**(`network`, `requests`, `window_seconds`, `trusted`): 같은 원리이며, 가장 구체적인 네트워크가 이깁니다. 우선순위: 폴더, 그다음 IP/네트워크, 그다음 전역 제한.
- **일반 사용자에 대한 차단은 그대로**: 공인 IP의 초과는 여전히 `waf-alerts.log`에 `"action": "block"`으로 기록되므로 omega-jail이 차단할 수 있습니다(10분에 거부 3회 → 12시간). **안전한 출처** — `never_auto_block` 네트워크 또는 `trusted: true`로 표시한 규칙 — 는 여전히 429를 받지만 `"action": "throttle"`로 기록되며, jail은 이를 결코 세지 않습니다.
- **magnet 스크립트**: 그 자체의 요청 제한(429 응답)은 결코 탐지로 세지 않으므로 자동 차단으로 이어지지 않습니다. 폴더 또는 IP/네트워크 규칙에 해당하는 요청에서는 네이티브 규칙이 기준이 되며 magnet의 429는 무시됩니다(공격 시그니처는 계속 적용).
- 요청 제한 규칙은 WAF 검사를 **결코** 끄지 않습니다. 반대로 검사 제외(`exclusions.path_prefixes`)가 rate limit을 해제하는 일도 결코 없습니다. `trusted_proxy`가 켜져 있지 않으면 `127.0.0.1`/`::1`을 포함하는 규칙은 무시됩니다(`never_auto_block`과 같은 안전장치).

## 12. 서비스와 운영

systemd/OpenRC/runit 자동 감지(`service install/status/start/stop/restart/enable/disable/uninstall`). 생성되는 systemd 유닛은 기본으로 타협할 수 없는 강화를 적용합니다: `NoNewPrivileges`, `PrivateTmp`, `ProtectSystem=strict`, `ProtectHome`, `var/`로 한정한 `ReadWritePaths`, 전용 사용자/그룹 필수, `UMask=0077`, `Restart=on-failure`. SIGTERM에 정상 종료(진행 중인 연결을 배수하고, 설정 가능한 유예 기간 후 강제 종료). SIGHUP에 핫 리로드(WAF 규칙과 Auth 영역만 — bind/포트/TLS와 Active Defense는 완전한 재시작 없이는 결코 바꿀 수 없음).

## 13. 로그

`var/log/access.log`(Apache combined 형식 + `request_id`, 로그 주입 방지 이스케이프), `var/log/error.log`. 크기/보관 파일 수에 따른 순환(`logs.rotation`). 네이티브 WAF: `var/log/waf-alerts.log`(`options.waf.logging.path`). magnet 스크립트(§7): `options.waf.magnet.paths.alerts_log`/`.blocklist_log`, 기본값 `var/log/waf-magnet-alerts.log`/`var/log/waf-magnet-blocklist.log` — magnet이 켜져 있을 때만 라이브러리에 바로 추가됩니다(*Omega-Serv의 알려진 로그 추가* 버튼). 반면 `lnav`는 항상 이를 제안합니다(없는 파일은 실행할 때 그냥 무시됨).

### 13a. 원격 소스(SSH)

명시적인 요청에 따라, 리버스 프록시 뒤 같은 로컬 네트워크에 있는 백엔드 서버의 로그를 모읍니다(**로그 관리 → 라이브러리 → 원격 소스(SSH)** 화면). 「fetch」는 수동으로 한 번 하는 동작이며, 실시간 흐름이나 자동 폴링이 결코 아닙니다: *지금 가져오기* 버튼을 누른 순간 `scp`로 **사본**을 가져와 `var/log/remote/` 아래에 쓰고, 일반 로그처럼 라이브러리에 추가합니다(*접근* 열 = `ssh`, *수정 시각* 열 = **이번** 가져오기의 날짜 — 원격 파일의 날짜가 아님). 새로 가져오면 이전 사본이 더 새것으로 바뀔 뿐입니다.

의도적인 안전장치(전체 검토는 `OMEGA-SERV_ETUDE-FAISABILITE_LOGS_DISTANTS.md` 참조): 자동 네트워크 스캔 없음, 명시적 설정 없는 연결 없음(레이블/호스트/원격 경로, 선택적 사용자/포트/개인 키 — 비워 두면 명령을 직접 입력할 때처럼 `ssh`/`~/.ssh/config`가 결정), 비밀번호를 묻거나 저장하는 일 없음(개인 키는 경로로만 참조하며, Omega-serv가 읽거나 저장하지 않음), 전송 전 크기 확인 없음. `scp` 기능은 **기능 레지스트리**에서 로컬로 감지합니다(실행 파일 존재 여부만, 호스트 도달성 테스트는 결코 하지 않음). Samba는 의도적으로 제외했습니다(YAGNI, 실제 필요가 확인될 때까지).

## 14. 테스트

```bash
source .venv/bin/activate
lint-imports        # 8개의 계층 계약 검증
pytest -q           # 테스트 2485개
ruff check .
mypy src
```

구조: `tests/unit/`(도메인/애플리케이션, 테스트 더블), `tests/integration/`(실제 TCP 소켓 위의 실제 asyncio 서버, 하위 프로세스의 실제 `openssl`, 완전한 임시 프로젝트에 대한 실제 CLI 명령, Textual의 `Pilot` API를 통한 대화형 인터페이스 - 스크린샷은 결코 쓰지 않음), `tests/security/`(HTTP 파서와 경로 해석기에 대한 `hypothesis` 속성 테스트).

## 15. 범위 밖

- 원시 CGI(FastCGI/PHP-FPM만)
- mTLS(인증서를 통한 클라이언트 인증), OCSP stapling
- 외부 CA / 제3자 기관용 CSR, 완전한 CRL 배포
- Active Defense: `omega-fire` 차단 이벤트와의 실제 통합(`omega-fire` 쪽에서 막혀 있음. 현재 읽기용 인터페이스를 전혀 제공하지 않음)

---

> 🔒 OMEGA-SERV — 견고하고, 완전하며, 안전하고, 방어적인 웹 서버.
