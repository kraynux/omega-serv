<!-- Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE) -->

# omega-serv na tle serwerów WWW dostępnych na rynku

**Porównanie oparte na pomiarach: nginx · lighttpd · Apache · Caddy · Traefik · omega-serv 2.5 i 3.0.0**

🌐 [Français](../../comparatif-serveurs-web.md) · [English](../en/comparatif-serveurs-web.md) · [Español](../es/comparatif-serveurs-web.md) · [Português (Brasil)](../pt-BR/comparatif-serveurs-web.md) · [Italiano](../it/comparatif-serveurs-web.md) · [Deutsch](../de/comparatif-serveurs-web.md) · [Nederlands](../nl/comparatif-serveurs-web.md) · **Polski** · [Русский](../ru/comparatif-serveurs-web.md) · [中文](../zh-CN/comparatif-serveurs-web.md) · [Tiếng Việt](../vi/comparatif-serveurs-web.md) · [ไทย](../th/comparatif-serveurs-web.md) · [Bahasa Indonesia](../id/comparatif-serveurs-web.md) · [日本語](../ja/comparatif-serveurs-web.md) · [한국어](../ko/comparatif-serveurs-web.md) · [हिन्दी](../hi/comparatif-serveurs-web.md) · [العربية](../ar/comparatif-serveurs-web.md)

Ten dokument umieszcza omega-serv wśród najpopularniejszych serwerów WWW. Nie próbuje wskazać „najlepszego serwera”: każde narzędzie odpowiada na inne potrzeby i każde ma swoje mocne strony. Zawiera trzy rzeczy:

1. **rzeczywiste pomiary**, wykonane na **trzech** bardzo różnych **maszynach**, z tym samym klientem, tymi samymi plikami i tym samym protokołem, powtarzalne;
2. **porównanie funkcji**, każda sprawdzona w oficjalnej dokumentacji danego serwera (odnośniki na końcu dokumentu), z rozróżnieniem tego, co wbudowane, od tego, co wymaga modułu lub wtyczki;
3. co omega-serv **naprawdę wnosi więcej**, a co inni robią **lepiej od niego**.

Pomiary serwera plików wykonano 3 i 4 listopada 2026 (omega-serv 2.5), a pomiary reverse proxy 14 listopada 2026 (omega-serv 3.0.0, w przygotowaniu). Pamięć omega-serv 3.0.0, od tego czasu wyraźnie zmniejszoną, zmierzono ponownie 19 listopada 2026 na wszystkich trzech maszynach według tego samego protokołu (§4, §5 i §6). Żadna liczba nie została przejęta z innej strony ani oszacowana. Surowe dane są publikowane razem z tym dokumentem.

---

## Spis treści

1. [W skrócie](#1-w-skrócie)
2. [Jak czytać to porównanie](#2-jak-czytać-to-porównanie)
3. [Metoda pomiaru](#3-metoda-pomiaru)
4. [Wydajność: omega-serv na tle nginx, lighttpd, Apache i Caddy](#4-wydajność-omega-serv-na-tle-nginx-lighttpd-apache-i-caddy)
5. [Wydajność jako reverse proxy: omega-serv na tle nginx, lighttpd, Apache, Caddy i Traefik](#5-wydajność-jako-reverse-proxy-omega-serv-na-tle-nginx-lighttpd-apache-caddy-i-traefik)
6. [Wersje omega-serv: 1.0 → 2.0 → 2.5 → 3.0.0](#6-wersje-omega-serv-10--20--25--300)
7. [Porównanie funkcji](#7-porównanie-funkcji)
8. [Administracja i ergonomia](#8-administracja-i-ergonomia)
9. [Co omega-serv wnosi więcej](#9-co-omega-serv-wnosi-więcej)
10. [Co inni robią lepiej](#10-co-inni-robią-lepiej)
11. [Jaki serwer do jakiego zastosowania](#11-jaki-serwer-do-jakiego-zastosowania)
12. [Odtworzenie pomiarów](#12-odtworzenie-pomiarów)
13. [Źródła](#13-źródła)

---

## 1. W skrócie

- **omega-serv ma dwa silniki.** **Silnik Python** obsługuje wszystko sam. **Silnik natywny**, napisany w C++ i wprowadzony w wersji 2.5, sam obsługuje żądania; Python zachowuje konfigurację i decyzje dotyczące bezpieczeństwa, a silnik natywny sam rozpoznaje żądania, do których nie pasuje żadna reguła WAF.
- **Z silnikiem natywnym, bez WAF**, omega-serv serwuje małe pliki z **około 0,7 szybkości nginx**, na wszystkich trzech maszynach. Plasuje się więc **przed Apache i Caddy, za nginx i lighttpd**.
- **Z silnikiem Python** omega-serv pozostaje daleko za wszystkimi innymi: **3–11 % szybkości nginx**.
- **Z aktywnym WAF** omega-serv sprawdza każde żądanie, czego inne mierzone serwery nie robią. Z silnikiem natywnym osiąga wtedy **0,53–0,56** szybkości nginx (bez WAF) na maszynach A i B oraz 1,07 na maszynie C (4 rdzenie wobec 2): WAF odbiera mu tylko 5–22 % przepustowości. Pozostaje przed Apache i Caddy mierzonymi bez WAF.
- **Średnie pliki (100 KB)**: to obecny słaby punkt silnika natywnego, z wynikiem **0,3–0,6** nginx, za Apache.
- **Duże pliki (5 MB)**: nginx, lighttpd, Apache i natywny omega-serv osiągają ten sam rząd przepustowości. Caddy jest wyraźnie wolniejszy na najszybszej maszynie.
- **Jako reverse proxy (3.0.0)** silnik natywny przekazuje małe odpowiedzi z wynikiem **0,82–0,91 nginx**, a odpowiedzi 100 KB **równie szybko jak nginx lub szybciej** (0,97–1,43). Jest **drugi za nginx**, przed lighttpd, Apache, Traefikiem i Caddy. W HTTPS pozostaje drugi dla małych odpowiedzi na maszynach A i B; na maszynie C lighttpd mu dorównuje.
- **Pamięć**: lighttpd (1 MB), nginx (4–5 MB) i Apache (4–9 MB) są bardzo oszczędne. omega-serv 3.0.0 zajmuje **10–16 MB** z silnikiem natywnym, **20–33 MB** z silnikiem Python lub z WAF i 35–55 MB z 2 procesami; Caddy **50–67 MB**. Wersja 2.5 zajmowała 28–57 MB.
- **Co omega-serv ma więcej**: pełne zarządzanie w interfejsie terminalowym, w 17 językach; wbudowany WAF i aktywną obronę; dokładne limity bezpieczeństwa przy wielu procesach; import skryptów mod_magnet z lighttpd; zarządzanie wieloma instancjami.
- **Czego nie ma**: HTTP/2 i HTTP/3, kompresji w locie, wykrywania usług Docker/Kubernetes, wbudowanego klienta ACME (korzysta z Certbota), ekosystemu modułów.

---

## 2. Jak czytać to porównanie

Kilka pojęć powraca w całym dokumencie.

- **Żądania na sekundę (req/s)**: liczba plików, które serwer wysyła w ciągu sekundy. Im więcej, tym lepiej.
- **Różnica względem nginx**: wartości bezwzględne silnie zależą od maszyny. Na naszych trzech maszynach nginx osiąga od 22 000 do 440 000 req/s. Stały pozostaje **stosunek między serwerami**. Tabele podają więc obok każdej wartości jej stosunek do nginx zmierzonego w tej samej sesji: **1,00 = tak szybko jak nginx**, 0,50 = o połowę wolniej, 1,50 = o połowę szybciej.
- **Opóźnienie p99**: czas odpowiedzi, którego nie przekracza 99 % żądań. Pokazuje „złe chwile”, które średnia ukrywa.
- **PSS (*Proportional Set Size*)**: pamięć faktycznie zajmowana przez wszystkie procesy serwera. Strona współdzielona przez kilka procesów jest liczona tylko raz.
- **Procesy i rdzenie**: serwer może używać kilku rdzeni procesora. Każdy robi to na swój sposób. nginx, lighttpd, Apache i omega-serv w trybie Python uruchamiają kilka procesów. Caddy, napisany w Go, rozkłada pracę na rdzenie. Silnik natywny omega-serv uruchamia jeden wątek na każdy dostępny rdzeń. Aby porównywać uczciwie, dajemy każdemu serwerowi **te same rdzenie**.
- **WAF (*Web Application Firewall*)**: filtr, który sprawdza każde żądanie, by blokować ataki (wstrzyknięcia, skanery…). omega-serv ma go wbudowanego. Inne serwery mogą otrzymać go jako moduł (ModSecurity, Coraza), ale **zmierzono je bez niego**, w konfiguracji podstawowej.

**Dobry odruch**: porównywać stosunki, a nie wartości bezwzględne, i zawsze sprawdzać, czy WAF jest aktywny.

---

## 3. Metoda pomiaru

### Trzy maszyny

| | Maszyna A | Maszyna B | Maszyna C |
|---|---|---|---|
| Procesor | Intel Core i5 M480, 2,67 GHz (2010) | Intel Celeron J3455, 1,5 GHz (2016) | AMD Ryzen AI 9 365 (2024) |
| Rdzenie | 2 rdzenie fizyczne, 4 wątki | 4 rdzenie, bez hyperthreadingu | 10 rdzeni (4 Zen 5 + 6 Zen 5c), 20 wątków |
| Pamięć | 8 GB | 8 GB | 32 GB |
| System | Mabox Linux (baza Manjaro), jądro 6.18 | EndeavourOS, jądro 7.2 | Arch Linux, jądro 7.2 (CachyOS) |
| Rdzenie serwera | 1 rdzeń fizyczny (wątki 0 i 2) | 2 rdzenie (0 i 1) | 4 rdzenie Zen 5, po jednym wątku (0–3) |
| Rdzenie klienta | 1 rdzeń fizyczny (wątki 1 i 3) | 2 rdzenie (2 i 3) | 6 rdzeni Zen 5c (4–9) |

Maszyna A to stary laptop, maszyna B energooszczędny mini PC, maszyna C nowy laptop, zasilany z sieci, w profilu energii „zrównoważony”. Obejmują zakres od małego domowego serwera do współczesnej maszyny.

### Oprogramowanie

| Oprogramowanie | Wersja |
|---|---|
| nginx | 1.30.4 (A), 1.30.5 (B, C) |
| lighttpd | 1.4.85 |
| Apache HTTP Server | 2.4.69, MPM `event` |
| Caddy | 2.11.4 (A, B), 2.11.7 (C) |
| omega-serv | 1.0.0 i 2.0.0 (opublikowane archiwa), 2.5 i 3.0.0, pod Pythonem 3.14 |
| Klient obciążenia | [oha](https://github.com/hatoo/oha) 1.16.0 (napisany w Ruście) |

Traefika nie mierzono jako serwera plików: nim nie jest (zob. §7). Zmierzono go jako reverse proxy, czyli w jego właściwej roli, w §5.

### Protokół

- **Izolacja procesora**: serwer i klient są przypięte do oddzielnych rdzeni (tabela powyżej). Klient nie zabiera więc czasu serwerowi, a wszystkie serwery mają dokładnie te same zasoby.
- **Te same pliki dla wszystkich**: `small.html` (1 KB), `medium.png` (100 KB) i `large.bin` (5 MB), serwowane z tego samego katalogu.
- **Log dostępu włączony wszędzie**, bo serwer produkcyjny prowadzi logi.
- **HTTP/1.1 bez szyfrowania, połączenia trwałe (keep-alive)**. Współbieżność wynosi 32 połączenia dla plików 1 KB i 100 KB oraz 8 dla pliku 5 MB.
- **Czas trwania**: 10 sekund na plik i na konfigurację.
- **Powtórzenia**: 3 pełne, przeplatane rundy (wszystkie konfiguracje w rundzie 1, potem wszystkie w rundzie 2 itd.). Tabele podają **medianę** trzech rund. Między rundami różnica zwykle nie przekracza 5 %.
- **Pamięć**: PSS wszystkich procesów serwera, mierzona w spoczynku, a potem po obciążeniu. Pamięć omega-serv 3.0.0 zmierzono ponownie 19 listopada 2026, z nginx jako odniesieniem w tej samej sesji: nginx mieści się w granicach 3 % swojej przepustowości z 4 listopada dla małych plików, a jego pamięć w granicach 1 MB.
- **Konfiguracje**:
  - nginx, lighttpd, Apache i Caddy w konfiguracji podstawowej: pliki statyczne i log dostępu;
  - omega-serv z profilem `standard`, z WAF wyłączonym, a potem włączonym ze wszystkimi dostarczonymi regułami (bez ograniczania liczby żądań).
- **Liczba procesów**: każdy serwer mierzono z 1, a potem z 2 procesami: nginx `worker_processes`, lighttpd `server.max-worker`, Apache `StartServers`/`ServerLimit`, Caddy `GOMAXPROCS`, omega-serv `server.workers`. Dla silnika natywnego omega-serv `server.workers` liczy procesy bezpieczeństwa Pythona; sam silnik natywny zawsze używa wszystkich przydzielonych mu rdzeni.
- **Żadnego błędu**: wszystkie odpowiedzi we wszystkich pomiarach to 200.

### Ograniczenia, o których trzeba wiedzieć

- **Porównujemy stosunki.** Wartości bezwzględne byłyby inne na Twoim sprzęcie lub na serwerze dedykowanym.
- **Pętla zwrotna (127.0.0.1)**: pomiar nie przechodzi przez prawdziwą sieć. W prawdziwej sieci przepustowość dużych plików jest prawie zawsze ograniczona pasmem, a nie serwerem. Przepustowości rzędu kilkudziesięciu GB/s na maszynie C są możliwe tylko w pętli zwrotnej.
- **Bez TLS** w pomiarach serwera plików (§4 i §6). Reverse proxy (§5) zmierzono w HTTP i w HTTPS.
- **Maszyna A**: produkcyjna usługa omega-serv tej maszyny działała w tle, nie otrzymując ruchu.
- **Maszyna C**: procesor hybrydowy (rdzenie Zen 5 i Zen 5c). Serwer dostał 4 szybkie rdzenie, klient 6 pozostałych.
- **Konfiguracje podstawowe**: żadnego serwera nie optymalizowano. Doświadczony administrator z pewnością wydobyłby więcej z każdego, omega-serv włącznie.
- **Surowe dane**: [`docs/benchmarks/`](../../benchmarks/) (jeden plik na maszynę i na kampanię; ponowny pomiar 3.0.0: `2026-11-19-*-memoire-3.0.0-brut.txt`).

---

## 4. Wydajność: omega-serv na tle nginx, lighttpd, Apache i Caddy

We wszystkich tabelach wartością odniesienia jest **nginx z 2 procesami** (= 1,00), zmierzony w tej samej sesji na tej samej maszynie. Na maszynach A i B to konfiguracja zajmująca wszystkie rdzenie przydzielone serwerowi.

### Małe pliki (1 KB): żądania na sekundę

| Serwer | Maszyna A | Maszyna B | Maszyna C |
|---|---:|---:|---:|
| lighttpd, 2 procesy | 33 138 (**1,52**) | 31 125 (**1,26**) | 378 590 (**1,53**) |
| nginx, 2 procesy | 21 801 (1,00) | 24 705 (1,00) | 248 184 (1,00) |
| **omega-serv, silnik natywny** | **15 222 (0,70)** | **16 542 (0,67)** | **285 213 (1,15 \*)** |
| omega-serv, natywny + WAF † | 11 990 (0,56) | 12 998 (0,53) | 264 484 (1,07 \*) |
| omega-serv, natywny + WAF, 2 procesy bezpieczeństwa † | 11 746 (0,55) | 12 718 (0,52) | 253 527 (1,02 \*) |
| Apache, 2 procesy | 9 192 (0,42) | 8 634 (0,35) | 188 335 (0,76) |
| Caddy, 2 procesy | 5 749 (0,26) | 4 116 (0,17) | 52 897 (0,21) |
| omega-serv, silnik Python, 2 procesy | 2 354 (0,11) | 1 312 (0,05) | 19 911 (0,08) |
| omega-serv, Python + WAF, 2 procesy | 1 901 (0,09) | 1 104 (0,04) | 15 783 (0,06) |
| omega-serv, silnik Python | 1 507 (0,07) | 663 (0,03) | 10 553 (0,04) |
| omega-serv, Python + WAF | 1 561 (0,07) | 564 (0,02) | 8 365 (0,03) |

\* Na maszynie C silnik natywny używa swoich 4 rdzeni, podczas gdy nginx z 2 procesami używa tylko 2. Porównanie przy tej samej liczbie rdzeni znajduje się niżej: stosunek wraca tam do **0,67–0,71**, jak na pozostałych maszynach.

† Zmierzone 4 listopada, po optymalizacji WAF, w osobnej kampanii według tego samego protokołu. Stosunek obliczono względem nginx (2 procesy) z tej kampanii: 21 439, 24 424 i 248 127 req/s dla małych plików, 11 545, 11 004 i 157 491 dla plików 100 KB. Przed tą optymalizacją silnik natywny z WAF osiągał 3 495, 2 622 i 39 000 req/s (0,11–0,16 nginx), bo każde żądanie przechodziło przez Pythona. Surowe dane: pliki `*-waf-natif-brut.txt`.

Z 1 procesem nginx osiąga 0,52–0,73, lighttpd 0,81–1,43, Apache 0,33–0,74, a Caddy 0,09–0,17 (surowe dane).

### Opóźnienie p99 dla małych plików

| Serwer | Maszyna A | Maszyna B | Maszyna C |
|---|---:|---:|---:|
| lighttpd, 2 procesy | 4,4 ms | 4,1 ms | 0,2 ms |
| nginx, 2 procesy | 4,9 ms | 5,2 ms | 0,2 ms |
| **omega-serv, silnik natywny** | **6,1 ms** | **6,2 ms** | **0,3 ms** |
| omega-serv, natywny + WAF † | 7,2 ms | 6,7 ms | 0,3 ms |
| Apache, 2 procesy | 18,8 ms | 20,6 ms | 0,8 ms |
| Caddy, 2 procesy | 24,1 ms | 30,5 ms | 2,8 ms |
| omega-serv, silnik Python, 2 procesy | 22,6 ms | 28,1 ms | 3,3 ms |
| omega-serv, silnik Python | 32,0 ms | 51,6 ms | 4,4 ms |

### Średnie pliki (100 KB): żądania na sekundę

| Serwer | Maszyna A | Maszyna B | Maszyna C |
|---|---:|---:|---:|
| lighttpd, 2 procesy | 13 561 (**1,08**) | 12 126 (**1,07**) | 197 905 (**1,26**) |
| nginx, 2 procesy | 12 513 (1,00) | 11 303 (1,00) | 157 224 (1,00) |
| Apache, 2 procesy | 6 939 (0,55) | 7 035 (0,62) | 153 265 (0,97) |
| Caddy, 2 procesy | 5 059 (0,40) | 3 744 (0,33) | 22 094 (0,14) |
| **omega-serv, silnik natywny** | **4 738 (0,38)** | **3 115 (0,28)** | **96 277 (0,61)** |
| omega-serv, natywny + WAF † | 4 229 (0,37) | 2 926 (0,27) | 98 185 (0,62) |
| omega-serv, silnik Python, 2 procesy | 1 741 (0,14) | 1 154 (0,10) | 18 806 (0,12) |
| omega-serv, silnik Python | 1 329 (0,11) | 611 (0,05) | 9 805 (0,06) |

### Duży plik (5 MB): przepustowość

| Serwer | Maszyna A | Maszyna B | Maszyna C |
|---|---:|---:|---:|
| lighttpd, 2 procesy | 2 440 MB/s (1,05) | 2 110 MB/s (0,99) | 28 011 MB/s (0,81) |
| nginx, 2 procesy | 2 322 MB/s (1,00) | 2 124 MB/s (1,00) | 34 651 MB/s (1,00) |
| Apache, 2 procesy | 2 355 MB/s (1,01) | 2 134 MB/s (1,00) | 41 153 MB/s (**1,19**) |
| **omega-serv, silnik natywny** | **2 294 MB/s (0,99)** | **1 936 MB/s (0,91)** | **37 918 MB/s (1,09)** |
| Caddy, 2 procesy | 2 205 MB/s (0,95) | 1 996 MB/s (0,94) | 3 811 MB/s (0,11) |
| omega-serv, silnik Python, 2 procesy | 2 145 MB/s (0,92) | 1 931 MB/s (0,91) | 25 829 MB/s (0,75) |
| omega-serv, silnik Python | 1 686 MB/s (0,73) | 1 472 MB/s (0,69) | 14 227 MB/s (0,41) |

### Pamięć (PSS, wszystkie procesy serwera): w spoczynku → po obciążeniu

omega-serv: wersja 3.0.0, ponownie zmierzona 19 listopada 2026 (wartości dla 2.5 są w §6). Pozostałe serwery: kampania z 4 listopada.

| Serwer | Maszyna A | Maszyna B | Maszyna C |
|---|---:|---:|---:|
| lighttpd | 1 → 1 MB | 1 → 1 MB | 1 → 1 MB |
| nginx | 4 → 5 MB | 5 → 5 MB | 4 → 4 MB |
| Apache | 4 → 7 MB | 4 → 7 MB | 4 → 7 MB |
| **omega-serv, silnik natywny** | **10 → 10 MB** | **10 → 12 MB** | **12 → 16 MB** |
| omega-serv, silnik Python | 20 → 23 MB | 21 → 24 MB | 22 → 28 MB |
| omega-serv, natywny + WAF | 28 → 30 MB | 29 → 32 MB | 30 → 33 MB |
| omega-serv, silnik Python, 2 procesy | 35 → 46 MB | 36 → 46 MB | 38 → 48 MB |
| omega-serv, natywny + WAF, 2 procesy bezpieczeństwa ‡ | 28 → 28 MB | 29 → 31 MB | 51 → 55 MB |
| Caddy, 2 procesy | 50 → 57 MB | 46 → 54 MB | 48 → 62 MB |

‡ Na maszynach A i B serwer ma tylko 2 rdzenie: omega-serv uruchamia tam tylko jeden proces bezpieczeństwa (2 uruchamia od 4 rdzeni). Na maszynie C, z 2 procesami bezpieczeństwa, nadzorca w Pythonie zachowuje pełną postać, potrzebną do współdzielonych przez nie liczników: 51 MB zamiast 30.

### Przy tej samej liczbie rdzeni: maszyna C z 4 procesami

Osobna kampania z 3 listopada, ten sam protokół, na maszynie C: każdy serwer otrzymuje 4 procesy (lub 4 rdzenie w przypadku Caddy i silnika natywnego). Odniesienie: nginx z 4 procesami. Silnika natywnego z WAF już tu nie ma: zmierzony przed optymalizacją WAF, nie został jeszcze ponownie zmierzony z 4 procesami. Pamięć omega-serv: 3.0.0, ponownie zmierzona 19 listopada (przepustowość: 2.5, 3 listopada).

| Serwer | 1 KB | 100 KB | 5 MB | Pamięć |
|---|---:|---:|---:|---:|
| lighttpd, 4 procesy | 638 907 (**1,46**) | 312 402 (**1,21**) | 41 982 MB/s (0,93) | 1 → 2 MB |
| nginx, 4 procesy | 438 496 (1,00) | 258 242 (1,00) | 45 162 MB/s (1,00) | 5 → 5 MB |
| **omega-serv, silnik natywny** | **294 083–310 972 (0,67–0,71)** | **108 991–109 955 (0,42)** | **40 137–40 463 MB/s (0,89–0,90)** | **12 → 16–18 MB** |
| Apache, 4 procesy | 200 592 (0,46) | 162 607 (0,63) | 39 664 MB/s (0,88) | 6 → 9 MB |
| Caddy, 4 rdzenie | 97 085 (0,22) | 35 900 (0,14) | 5 998 MB/s (0,13) | 52 → 67 MB |
| omega-serv, silnik Python, 4 procesy | 37 697 (0,09) | 35 064 (0,14) | 37 123 MB/s (0,82) | 45 → 60 MB |

### Interpretacja

- **Silnik natywny zmienia pozycję omega-serv.**
  - Dla małych plików przechodzi od 0,03–0,11 nginx (silnik Python) do około **0,7 nginx**, niezależnie od maszyny.
  - Plasuje się przed Apache i Caddy oraz za nginx i lighttpd, które pozostają najszybsze.
  - Jego opóźnienie p99 jest bliskie opóźnieniu nginx.
- **lighttpd jest najszybszy dla małych i średnich plików**, na wszystkich trzech maszynach, i najoszczędniejszy pod względem pamięci. Jego dokumentacja odradza jednak `server.max-worker` (wiele procesów), którego użyliśmy, by porównywać przy tej samej liczbie procesów.
- **Średnie pliki to obecny słaby punkt silnika natywnego**: 0,28–0,61 nginx, za Apache, i bez poprawy przy większej liczbie rdzeni. To rozpoznany kierunek ulepszeń.
- **Przy dużych plikach** serwery się wyrównują, bo dane kopiuje jądro (`sendfile`). Wyjątkiem jest Caddy na maszynie C: nie próbowaliśmy optymalizować jego konfiguracji podstawowej.
- **WAF niewiele kosztuje silnik natywny, ale trzeba to czytać uczciwie.**
  - Silnik natywny sam przeszukuje reguły WAF: żądanie, do którego nie pasuje żadna z nich, jest obsługiwane bez udziału Pythona. Przy najmniejszej wątpliwości (dopasowanie, tekst spoza ASCII, źródło śledzone przez Active Defense, strefa uwierzytelniania…) decyduje Python. Z WAF silnik natywny zachowuje w ten sposób 78–95 % przepustowości dla małych plików i 93–99 % dla plików 100 KB. Przed tą optymalizacją jego przepustowość była dzielona przez 4–7.
  - Ograniczanie liczby żądań liczy silnik natywny: jego włączenie nie zmienia tych liczb (maszyna A: 11 391 req/s z nim, 11 330 bez niego). Gdy magnet jest aktywny, wszystkie żądania nadal przechodzą przez Pythona, a koszt wraca do poprzedniego poziomu.
  - omega-serv z WAF pozostaje przed Apache i Caddy **bez** WAF.
  - nginx, lighttpd, Apache i Caddy zmierzono **bez** WAF. WAF dodany do tych serwerów (ModSecurity, Coraza) też ma swój koszt, którego nie mierzyliśmy. Porównanie „z WAF” nie odbywa się więc na równych warunkach i nie twierdzimy, że omega-serv byłby szybszy od innego serwera wyposażonego w WAF.
- **Wiele procesów bezpieczeństwa nie pomaga już zwykłemu ruchowi**: nie przechodzi on już przez nie, a przepustowość z 2 procesami pozostaje taka sama (−2 do −4 %, w granicach szumu pomiarowego). Pomagają tylko wtedy, gdy wiele żądań przechodzi przez Pythona (aktywny magnet, atak): zmierzone przed optymalizacją, gdy wszystkie żądania tam trafiały, 2 procesy bezpieczeństwa zwiększały przepustowość z WAF 1,5–1,7 raza na 4 rdzeniach, ale na 2 rdzeniach dawały tylko 5–12 %.
- **Silnik Python skaluje się z procesami** (×1,6–×2 z 2 procesami, około ×3,5 z 4), ale pozostaje na poziomie 5–11 % nginx.
- **Pamięć**: z silnikiem natywnym bez WAF omega-serv 3.0.0 zajmuje 10–16 MB, dwa do czterech razy więcej niż nginx czy Apache i trzy do sześciu razy mniej niż Caddy. Z WAF lub silnikiem Python trzeba liczyć 20–33 MB, głównie z powodu Pythona: proces Pythona z asyncio kosztuje co najmniej 10 MB. Przy jednym procesie to o 30–70 % mniej niż w 2.5 (§6).
- **Dla porównania**: nawet najwolniejszy przypadek, silnik Python z WAF na maszynie B (564 req/s), to prawie 50 milionów żądań dziennie. To znacznie więcej, niż potrzebuje strona prywatna, usługa wewnętrzna czy laboratorium. Szybkość jest naprawdę decydująca tylko dla strony o dużym ruchu.

---

## 5. Wydajność jako reverse proxy: omega-serv na tle nginx, lighttpd, Apache, Caddy i Traefik

Tutaj żaden serwer nie serwuje plików: każdy **przekazuje** żądania do serwera aplikacji (*backendu*) i odsyła jego odpowiedź. Pomiary z 14 listopada 2026, z omega-serv 3.0.0 (w przygotowaniu), którego silnik natywny sam obsługuje reverse proxy.

### Protokół właściwy tym pomiarom

- **Ten sam backend dla wszystkich**: statyczny nginx z 2 procesami, serwujący `small.html` (1 KB) i `medium.png` (100 KB). Każdy pomiar sprawdza, że odpowiedź rzeczywiście pochodzi z backendu (dodany przez niego nagłówek): proxy przekazuje, nigdy nie serwuje pliku sam.
- **Rdzenie**: maszyna A — proxy na jednym rdzeniu fizycznym (wątki 0 i 2), klient i backend na drugim (1 i 3); maszyna B — proxy na rdzeniach 0 i 1, klient i backend na 2 i 3; maszyna C — proxy na 4 rdzeniach Zen 5 (0–3), backend na 2 rdzeniach Zen 5c (4 i 5), klient na 4 pozostałych (6–9).
- **Procesy**: 2 na maszynach A i B, **4 na maszynie C**, aby każdy serwer używał wszystkich rdzeni przydzielonych proxy. Silnik natywny omega-serv zawsze używa wszystkich tych rdzeni, z jednym procesem bezpieczeństwa Pythona.
- **HTTP i HTTPS** po stronie klienta (samopodpisany certyfikat ECDSA P-256); z backendem zawsze łączy się przez HTTP.
- **Konfiguracje**:
  - nginx: `proxy_pass` do grupy `upstream`, która utrzymuje swoje połączenia z backendem (`keepalive 64`); bez tego ustawienia, nieobecnego w jego konfiguracji podstawowej, nginx otwiera jedno połączenie na każde żądanie;
  - lighttpd: `mod_proxy`, konfiguracja podstawowa;
  - Apache: `mod_proxy` i `mod_proxy_http`, MPM `event`, jeden wiersz `ProxyPass`;
  - Caddy: `reverse_proxy`, konfiguracja podstawowa;
  - Traefik 3.7: jeden router i jedna usługa, konfiguracja podstawowa;
  - omega-serv: strefa reverse proxy na `/`, profil `standard`, silnik natywny bez WAF, a potem z WAF (wszystkie dostarczone reguły, bez ograniczania liczby żądań), oraz silnik Python z 2 procesami.
- **Reszta się nie zmienia** (§3): log dostępu włączony wszędzie, oha, 32 połączenia trwałe, 10 sekund, 3 przeplatane rundy, mediana. **Żadnego błędu**: wszystkie odpowiedzi to 200.

W nawiasach: stosunek do nginx z tą samą liczbą procesów, zmierzonego w tej samej sesji (= 1,00).

### Małe odpowiedzi (1 KB): żądania na sekundę

| Serwer | Maszyna A (2 procesy) | Maszyna B (2 procesy) | Maszyna C (4 procesy) |
|---|---:|---:|---:|
| nginx | 11 151 (1,00) | 11 049 (1,00) | 246 595 (1,00) |
| **omega-serv, silnik natywny** | **9 507 (0,85)** | **10 098 (0,91)** | **203 021 (0,82)** |
| omega-serv, natywny + WAF | 9 078 (0,81) | 9 857 (0,89) | 190 201 (0,77) |
| lighttpd | 6 752 (0,61) | 6 242 (0,56) | 129 827 (0,53) |
| Apache | 6 616 (0,59) | 5 872 (0,53) | 124 458 (0,50) |
| Traefik | 3 940 (0,35) | 3 890 (0,35) | 70 465 (0,29) |
| Caddy | 3 578 (0,32) | 3 117 (0,28) | 55 910 (0,23) |
| omega-serv, silnik Python | 1 039 (0,09) | 859 (0,08) | — \* |

\* Silnik Python zmierzono na maszynie C tylko z 2 procesami: 11 530 req/s, czyli 0,07 nginx z 2 procesami (171 075 req/s).

### Średnie odpowiedzi (100 KB): żądania na sekundę

| Serwer | Maszyna A | Maszyna B | Maszyna C |
|---|---:|---:|---:|
| **omega-serv, silnik natywny** | **4 281 (1,11)** | **3 497 (0,97)** | **80 361 (1,43)** |
| omega-serv, natywny + WAF | 4 236 (1,10) | 3 335 (0,93) | 73 025 (1,30) |
| nginx | 3 855 (1,00) | 3 605 (1,00) | 56 011 (1,00) |
| lighttpd | 2 834 (0,74) | 2 252 (0,62) | 53 523 (0,96) |
| Apache | 2 404 (0,62) | 2 357 (0,65) | 39 807 (0,71) |
| Traefik | 2 477 (0,64) | 2 181 (0,60) | 39 419 (0,70) |
| Caddy | 2 294 (0,60) | 1 956 (0,54) | 33 120 (0,59) |
| omega-serv, silnik Python | 821 (0,21) | 669 (0,19) | — |

### HTTPS: żądania na sekundę

| Serwer | 1 KB: A | 1 KB: B | 1 KB: C | 100 KB: A | 100 KB: B | 100 KB: C |
|---|---:|---:|---:|---:|---:|---:|
| nginx | 9 203 (1,00) | 9 305 (1,00) | 202 095 (1,00) | 780 (1,00) | 2 338 (1,00) | 47 609 (1,00) |
| **omega-serv, silnik natywny** | **6 840 (0,74)** | **7 976 (0,86)** | **130 337 (0,64) †** | **690 (0,88)** | **1 917 (0,82)** | **42 507 (0,89)** |
| omega-serv, natywny + WAF | 6 372 (0,69) | 7 456 (0,80) | 146 590 (0,73) † | 683 (0,88) | 1 882 (0,80) | 39 400 (0,83) |
| lighttpd | 5 188 (0,56) | 5 513 (0,59) | 130 572 (0,65) | 638 (0,82) | 1 381 (0,59) | 45 566 (0,96) |
| Apache | 5 038 (0,55) | 4 193 (0,45) | 114 898 (0,57) | 588 (0,75) | 1 368 (0,59) | 29 948 (0,63) |
| Traefik | 3 389 (0,37) | 3 195 (0,34) | 62 251 (0,31) | 889 (**1,14**) | 1 548 (0,66) | 28 513 (0,60) |
| Caddy | 3 263 (0,35) | 2 733 (0,29) | 54 279 (0,27) | 1 135 (**1,46**) | 1 424 (0,61) | 26 452 (0,56) |
| omega-serv, silnik Python | 922 (0,10) | 759 (0,08) | — | 423 (0,54) | 549 (0,23) | — |

† Na maszynie C, w HTTPS, wynik silnika natywnego mocno się waha między rundami: 130 000–185 000 req/s bez WAF, 138 000–150 000 z WAF. Różnica między oboma wierszami mieści się więc w szumie tego pomiaru.

### Opóźnienie p99 dla małych odpowiedzi (HTTP)

| Serwer | Maszyna A | Maszyna B | Maszyna C |
|---|---:|---:|---:|
| nginx | 7,7 ms | 7,8 ms | 0,4 ms |
| **omega-serv, silnik natywny** | **10,5 ms** | **9,7 ms** | **0,6 ms** |
| omega-serv, natywny + WAF | 9,6 ms | 11,0 ms | 0,8 ms |
| lighttpd | 11,9 ms | 14,0 ms | 0,9 ms |
| Apache | 14,7 ms | 21,3 ms | 2,0 ms |
| Traefik | 25,9 ms | 26,5 ms | 2,1 ms |
| Caddy | 23,9 ms | 27,2 ms | 2,5 ms |
| omega-serv, silnik Python | 41,0 ms | 47,6 ms | — |

### Pamięć proxy (PSS): w spoczynku → po obciążeniu, w HTTP

omega-serv: wersja 3.0.0, ponownie zmierzona 19 listopada 2026; powyższe przepustowości pochodzą z 14 listopada.

| Serwer | Maszyna A | Maszyna B | Maszyna C |
|---|---:|---:|---:|
| lighttpd | 3 → 4 MB | 3 → 4 MB | 3 → 4 MB |
| nginx | 7 → 8 MB | 7 → 8 MB | 10 → 11 MB |
| Apache | 6 → 12 MB | 6 → 12 MB | 8 → 15 MB |
| **omega-serv, silnik natywny** | **27 → 28 MB** | **27 → 28 MB** | **29 → 33 MB** |
| omega-serv, natywny + WAF | 29 → 30 MB | 29 → 31 MB | 31 → 36 MB |
| Caddy | 48 → 57 MB | 48 → 59 MB | 50 → 60 MB |
| omega-serv, silnik Python | 42 → 50 MB | 43 → 51 MB | — |
| Traefik | 93 → 117 MB | 107 → 131 MB | 100 → 123 MB |

W HTTPS pamięć po obciążeniu rośnie o 0–5 MB w przypadku większości serwerów, bardziej w przypadku Apache (do 66 MB na maszynie C) i silnika Python (do 72 MB): zob. surowe dane.

### Interpretacja

- **Jako reverse proxy omega-serv z silnikiem natywnym jest drugi za nginx**, na wszystkich trzech maszynach.
  - Dla małych odpowiedzi przekazuje 0,82–0,91 tego, co nginx. To 1,4–1,7 raza więcej niż lighttpd i Apache oraz 2,4–3,6 raza więcej niż Traefik i Caddy.
  - Jego opóźnienie p99 jest najniższe po opóźnieniu nginx.
- **Dla odpowiedzi 100 KB dorównuje nginx lub go wyprzedza** (0,97–1,43). Silnik natywny przekazuje odpowiedź na bieżąco, z ograniczonym buforem. W konfiguracji podstawowej nginx trzyma w pamięci tylko kilkadziesiąt KB na każdą przekazywaną odpowiedź (`proxy_buffers`) i może zapisać resztę do pliku tymczasowego. Nie zmienialiśmy tego ustawienia.
- **W HTTPS** silnik natywny pozostaje drugi dla małych odpowiedzi na maszynach A i B. Na maszynie C on i lighttpd są na tym samym poziomie.
  - Dla odpowiedzi 100 KB lighttpd wyprzedza go na maszynie C.
  - Na maszynie A Caddy i Traefik wyprzedzają wszystkich, łącznie z nginx. Są napisane w Go, z własną biblioteką TLS, najwyraźniej wydajniejszą na tym procesorze z 2010 roku. Nie badaliśmy tego dalej.
- **WAF niewiele kosztuje w roli reverse proxy**: 1–9 % przepustowości w HTTP, przy wszystkich aktywnych regułach. Pozostałe serwery zmierzono bez WAF: porównanie „z WAF” nie odbywa się na równych warunkach (zob. §4).
- **Pamięć**: z silnikiem natywnym omega-serv 3.0.0 zajmuje około 30 MB (27–36 MB). Ta suma obejmuje nadzorcę w Pythonie, proces bezpieczeństwa i silnik natywny. To kilka razy więcej niż nginx, lighttpd czy Apache, ale mniej niż Caddy i trzy do czterech razy mniej niż Traefik. W pomiarze z 14 listopada (3.0.0 w przygotowaniu) zajmował około 50 MB.
- **Silnik Python** przekazuje małe odpowiedzi z wynikiem 0,08–0,10 nginx: pozostaje silnikiem zapasowym. Strefy reverse proxy z pamięcią podręczną nadal są mu powierzane, więc zachowują jego przepustowość.
- **Poprawka wprowadzona przed tymi pomiarami.** Pierwsza seria pomiarów, tego samego dnia i według tego samego protokołu, dawała silnikowi natywnemu 0,32–0,69 nginx dla małych odpowiedzi. Na maszynie C zatrzymywał się na około 78 000 req/s, niezależnie od liczby rdzeni. Jego pula połączeń z backendem była za mała: otwierał nowe połączenie co pięć żądań. Przed opublikowaną tu serią pulę powiększono, a przekazywanie odciążono. Liczby z pierwszej serii również są opublikowane.

### Ograniczenia tych pomiarów

- **nginx jest ustawiony na swoją korzyść**: utrzymuje połączenia z backendem, czego nie robi w konfiguracji podstawowej. Pozostałe serwery działają w konfiguracji podstawowej.
- **Backend działa na tej samej maszynie**, w pętli zwrotnej. Na maszynach A i B dzieli rdzenie z klientem. Liczą się więc tylko stosunki między serwerami, zmierzone w tych samych warunkach. Sam ten backend serwuje na maszynie C około 345 000 req/s: nie ogranicza tam żadnego z proxy.
- **Tylko HTTP/1.1**, zarówno do klienta, jak i do backendu: omega-serv nie obsługuje HTTP/2.
- **Surowe dane**: [`docs/benchmarks/`](../../benchmarks/), pliki `2026-11-14-*-reverse-proxy-brut.txt`, w tym pierwsza seria (`2026-11-14-reverse-proxy-avant-correctif-brut.txt`).

---

## 6. Wersje omega-serv: 1.0 → 2.0 → 2.5 → 3.0.0

Trzy wersje zmierzono w tej samej sesji co w §4, na wszystkich trzech maszynach, według tego samego protokołu. W nawiasach: stosunek do nginx (2 procesy) z tej samej sesji. †: kampania z 4 listopada po optymalizacji WAF (zob. §4). Wersję 3.0.0 zmierzono 19 listopada według tego samego protokołu; jej stosunki odnoszą się do nginx (2 procesy) zmierzonego ponownie w tej sesji, który mieści się w granicach 3 % swojej wartości z 4 listopada.

### Małe pliki (1 KB): żądania na sekundę

| Wersja i tryb | Maszyna A | Maszyna B | Maszyna C |
|---|---:|---:|---:|
| 1.0.0 | 1 547 (0,07) | 645 (0,03) | 8 870 (0,04) |
| 1.0.0 + WAF | 1 453 (0,07) | 561 (0,02) | 7 687 (0,03) |
| 2.0.0 | 1 740 (0,08) | 650 (0,03) | 10 245 (0,04) |
| 2.0.0 + WAF | 1 456 (0,07) | 565 (0,02) | 8 371 (0,03) |
| 2.0.0, 2 procesy | 2 153 (0,10) | 1 277 (0,05) | 19 192 (0,08) |
| 2.0.0 + WAF, 2 procesy | 1 775 (0,08) | 1 113 (0,05) | 15 351 (0,06) |
| 2.5, silnik Python | 1 507 (0,07) | 663 (0,03) | 10 553 (0,04) |
| 2.5, silnik Python + WAF | 1 561 (0,07) | 564 (0,02) | 8 365 (0,03) |
| 2.5, silnik Python, 2 procesy | 2 354 (0,11) | 1 312 (0,05) | 19 911 (0,08) |
| 2.5, silnik Python + WAF, 2 procesy | 1 901 (0,09) | 1 104 (0,04) | 15 783 (0,06) |
| **2.5, silnik natywny** | **15 222 (0,70)** | **16 542 (0,67)** | **285 213 (1,15)** |
| **2.5, silnik natywny + WAF †** | **11 990 (0,56)** | **12 998 (0,53)** | **264 484 (1,07)** |
| **2.5, silnik natywny + WAF, 2 procesy bezpieczeństwa †** | **11 746 (0,55)** | **12 718 (0,52)** | **253 527 (1,02)** |
| 3.0.0, silnik Python | 1 309 (0,06) | 752 (0,03) | 9 482 (0,04) |
| 3.0.0, silnik Python + WAF | 1 168 (0,05) | 653 (0,03) | 8 788 (0,04) |
| 3.0.0, silnik Python, 2 procesy | 1 733 (0,08) | 1 154 (0,05) | 17 234 (0,07) |
| 3.0.0, silnik Python + WAF, 2 procesy | 1 605 (0,07) | 994 (0,04) | 14 873 (0,06) |
| **3.0.0, silnik natywny** | **14 503 (0,68)** | **15 075 (0,63)** | **276 938 (1,15)** |
| **3.0.0, silnik natywny + WAF** | **12 762 (0,60)** | **11 618 (0,48)** | **257 741 (1,07)** |
| **3.0.0, silnik natywny + WAF, 2 procesy bezpieczeństwa** | **12 974 (0,61)** | **11 957 (0,50)** | **253 993 (1,06)** |

### Średnie pliki, duży plik i pamięć (1 proces, bez WAF)

| Wersja | 100 KB, req/s (A / B / C) | 5 MB, MB/s (A / B / C) | Pamięć w spoczynku → po obciążeniu (A / B / C) |
|---|---|---|---|
| 1.0.0 | 1 071 / 563 / 7 625 | 578 / 549 / 3 640 | 21 → **98** / 22 → **98** / 23 → **73** MB |
| 2.0.0 | 1 570 / 603 / 9 469 | 1 665 / 1 470 / 14 058 | 26 → 30 / 27 → 31 / 28 → 32 MB |
| 2.5, silnik Python | 1 329 / 611 / 9 805 | 1 686 / 1 472 / 14 227 | 28 → 32 / 29 → 33 / 30 → 34 MB |
| **2.5, silnik natywny** | **4 738 / 3 115 / 96 277** | **2 294 / 1 936 / 37 918** | **33 → 34 / 34 → 35 / 35 → 39 MB** |
| 3.0.0, silnik Python | 1 185 / 606 / 8 655 | 1 765 / 1 318 / 13 028 | 20 → 23 / 21 → 24 / 22 → 28 MB |
| **3.0.0, silnik natywny** | **4 665 / 3 026 / 100 513** | **2 399 / 1 932 / 40 755** | **10 → 10 / 10 → 12 / 12 → 16 MB** |

### Duże jednoczesne pobierania

Test: 3 jednoczesne pobierania pliku 300 MB, podczas gdy mała strona jest pobierana nieprzerwanie. Dwa przebiegi na wersję i na maszynę, z niemal identycznymi wynikami. Pamięć to tutaj **RSS** wszystkich procesów serwera, jak w oryginalnym teście: liczy ona pamięć współdzieloną kilka razy, co daje wyższe wartości niż PSS w innych tabelach.

| Wersja | Szczytowa pamięć | Mała strona, najgorszy przypadek: A / B / C |
|---|---:|---|
| 1.0.0 | **1 833–1 836 MB** | **1,4–1,9 s** / **1,4–1,7 s** / 0,16 s |
| 2.0.0 | 39–42 MB | 3 ms / 4–6 ms / 1 ms |
| 2.5, silnik Python | 41–44 MB | 2 ms / 4 ms / 1 ms |
| 2.5, silnik natywny | 49–55 MB | 1–2 ms / 2–4 ms / poniżej 1 ms |
| 3.0.0, silnik Python | 39 MB | 3 ms / 5–8 ms / 1 ms |
| 3.0.0, silnik natywny | 23–26 MB | 1 ms / 2–3 ms / poniżej 1 ms |

### Koszt aktywnej obrony (1.0 → 2.0)

Pomiar z 26 października 2026 na maszynie A, od tamtej pory niepowtarzany: koszt jednej obserwacji zagrożenia przez Active Defense, dla każdego podejrzanego żądania, mierzony na dysku (ext4) na 2 000 obserwacji.

| Pomiar | 1.0.0 | 2.0.0 |
|---|---:|---:|
| Mediana | 2,84 ms | 0,23 ms |
| p99 | 11,6 ms | 2,3 ms |
| Maksimum | 18–20 ms | 37–46 ms |

Mediana jest dzielona przez 12. Maksimum jest natomiast wyższe w 2.0: kilka pojedynczych skoków, związanych z okresowym zapisem dziennika SQLite na dysk.

### Interpretacja

- **Od 1.0 do 2.0** postęp dotyczy pamięci i dużych plików, a nie szybkości małych stron:
  - pamięć po obciążeniu spada z 73–98 MB do 30–32 MB;
  - podczas dużych pobierań spada z ponad 1,8 GB do około 40 MB, a serwer pozostaje responsywny (kilka milisekund zamiast prawie 2 sekund);
  - przepustowość dużych plików rośnie 2,7–3,9 raza;
  - 2.0 dodaje wiele procesów, które zwiększają przepustowość małych stron o 25 % do prawie 100 %, zależnie od maszyny.
  1.0 wczytywała każdy plik w całości do pamięci przed wysłaniem. 2.0 wysyła go blokami lub przekazuje jądru.
- **Od 2.0 do 2.5 silnik Python nie zmienia szybkości**: różnice pozostają poniżej 4 % na maszynach B i C oraz w granicach szumu pomiarowego maszyny A (−13 % do +9 %), najbardziej wrażliwej na obciążenie w tle. Cały zysk wersji 2.5 pochodzi z **silnika natywnego**: około ×10–×27 dla małych plików względem silnika Python i opóźnienie podzielone przez 5–15.
- **W wersji 2.5 silnik natywny zajmował w spoczynku około 5 MB więcej** niż silnik Python (PSS): cena drugiego programu. Z WAF jeszcze około 8 MB więcej: reguły wczytane do silnika natywnego.
- **Od 2.5 do 3.0.0 pamięć spada o 30–70 %** przy jednym procesie:
  - silnik natywny: 33–35 → 10–12 MB w spoczynku. Gdy nic innego tego nie wymaga, nadzorca w Pythonie ogranicza się do małego programu monitorującego, który nie trzyma w pamięci ani konfiguracji, ani serwera Python;
  - silnik Python: 28–30 → 20–22 MB. Kod opcji jest wczytywany tylko wtedy, gdy jest ona aktywna, a biblioteka TLS tylko wtedy, gdy jest używana;
  - natywny + WAF: 43–45 → 28–30 MB. Proces bezpieczeństwa powstaje z ograniczonego nadzorcy i współdzieli z nim swoje strony pamięci;
  - silnik Python z 2 procesami: 40–43 → 35–38 MB;
  - podczas dużych pobierań: 39 MB (Python) i 23–26 MB (natywny), wobec 41–55 MB;
  - silnik natywny zajmuje teraz o połowę mniej pamięci niż silnik Python.
- **Praca nad pamięcią nie zmienia przepustowości**: przeplatany test na maszynach B i C, z kodem 3.0.0 przed tą pracą i po niej, daje 1–4 % różnicy. W porównaniu z 2.5 silnik Python z 2 procesami obsługuje o 12–13 % mniej na maszynach B i C (26 % na maszynie A, najbardziej wrażliwej na obciążenie w tle); kod 3.0.0 sprzed tej pracy wykazuje ten sam spadek, który pochodzi więc z innych zmian w 3.0.0 i wymaga jeszcze zbadania. Pozostałe różnice względem 2.5 wynoszą od −13 % do +13 %, w obie strony.

### Co warto wiedzieć o silniku natywnym

- Jest **opcjonalny**: silnik Python pozostaje silnikiem domyślnym i zapasowym.
- Sam serwuje treść statyczną, przekierowania, przepisania, aliasy, pamięć podręczną, strony błędów, nagłówki bezpieczeństwa i TLS.
- Sam przeszukuje reguły WAF i sam obsługuje żądanie, do którego nie pasuje żadna z nich. O każdym innym żądaniu (dopasowanie lub wątpliwość WAF, Active Defense, uwierzytelnianie) decyduje Python, z dokładnie tymi samymi kontrolami i tymi samymi logami. Regulowana kontrola i tak przekazuje Pythonowi jedno czyste żądanie na N, aby sprawdzić, że oba wydają ten sam werdykt.
- Sam przekazuje ruch reverse proxy, łącznie z WebSocket (od wersji 3.0.0). Listowanie katalogów i strony wewnętrzne są pobierane od Pythona; FastCGI, przesyłanie plików i strefy reverse proxy z pamięcią podręczną są mu przekazywane na całe połączenie. Te funkcje zachowują więc szybkość silnika Python.
- Przy bezpośrednim TLS silnik natywny nie obsługuje FastCGI, przesyłania plików ani stref reverse proxy z pamięcią podręczną: wtedy obsługuje silnik Python, a interfejs to pokazuje.
- Wymaga glibc 2.38 lub nowszej i OpenSSL 3. Jeśli się nie uruchamia, instalacja kompiluje go ponownie na miejscu, a w przeciwnym razie omega-serv zostaje przy silniku Python.

---

## 7. Porównanie funkcji

Legenda:
- ✅ wbudowane;
- 🧩 oficjalny moduł projektu, do włączenia lub zainstalowania;
- 🔌 moduł lub wtyczka zewnętrzna;
- ⚙️ za pomocą zewnętrznego narzędzia;
- ❌ brak.

„Commercial” oznacza funkcję zastrzeżoną dla płatnej edycji.

### Usługa HTTP

| Funkcja | nginx | lighttpd | Caddy | Apache | Traefik | omega-serv 2.5 |
|---|---|---|---|---|---|---|
| Język serwera | C | C | Go | C | Go | Python, z opcjonalnym silnikiem natywnym C++ |
| Serwowanie plików statycznych | ✅ | ✅ | ✅ | ✅ | ❌ (tylko proxy) | ✅ |
| ETag / 304 / Range | ✅ | ✅ | ✅ | ✅ | — | ✅ |
| Pliki wstępnie skompresowane `.gz` / `.br` | ✅ `gzip_static` (`.br`: 🔌) | 🔌 skrypt Lua (mod_magnet) | ✅ `precompressed` | 🧩 przepis mod_rewrite | — | ✅ |
| Kompresja w locie | ✅ | ✅ mod_deflate | ✅ | 🧩 mod_deflate | ✅ middleware | ❌ |
| HTTP/2 | ✅ | ✅ | ✅ | 🧩 mod_http2 | ✅ | ❌ |
| HTTP/3 (QUIC) | ✅ | ❌ | ✅ | ❌ | ✅ | ❌ |
| PHP przez FastCGI | ✅ | ✅ | ✅ | ✅ | ❌ | ✅ |
| Wiele procesów lub rdzeni | ✅ workery | ⚠️ `max-worker`, odradzany przez dokumentację | ✅ (Go, wszystkie rdzenie) | ✅ MPM | ✅ (Go) | ✅ `server.workers`; silnik natywny: wszystkie rdzenie |

### Reverse proxy

| Funkcja | nginx | lighttpd | Caddy | Apache | Traefik | omega-serv 2.5 |
|---|---|---|---|---|---|---|
| Równoważenie obciążenia | ✅ round robin, najmniej połączeń, hash | ✅ fair, round-robin, hash, sticky | ✅ kilkanaście strategii | 🧩 mod_proxy_balancer | ✅ wrr, p2c, hrw, least-time | ✅ 7 strategii, w tym rzeczywiste obciążenie |
| Pasywna kontrola zdrowia (odsunięcie niesprawnego serwera) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Aktywna kontrola zdrowia (okresowa sonda) | Commercial (NGINX Plus) | ❌ | ✅ | 🧩 mod_proxy_hcheck | ✅ | ✅ |
| Pamięć podręczna odpowiedzi | ✅ `proxy_cache` | ❌ | 🔌 | 🧩 mod_cache | Commercial | ✅ |
| WebSocket | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Wykrywanie usług (Docker, Kubernetes) | 🔌 | ❌ | 🔌 | ❌ | ✅ (rdzeń projektu) | ❌ |

### TLS

| Funkcja | nginx | lighttpd | Caddy | Apache | Traefik | omega-serv 2.5 |
|---|---|---|---|---|---|---|
| Automatyczne certyfikaty (ACME, Let's Encrypt) | 🧩 `ngx_http_acme_module` | ⚙️ Certbot | ✅ domyślnie | 🧩 mod_md | ✅ | ⚙️ Certbot, z wbudowanym kreatorem i zaplanowanym odnawianiem |
| Lokalne CA | ❌ | ❌ | ✅ wewnętrzne CA (automatyczne wystawianie) | ❌ | ❌ | ✅ generowanie, podpisywanie CSR, unieważnianie |

### Bezpieczeństwo

| Funkcja | nginx | lighttpd | Caddy | Apache | Traefik | omega-serv 2.5 |
|---|---|---|---|---|---|---|
| Limit żądań na klienta | ✅ `limit_req` | ⚠️ mod_evasive (tylko jednoczesne połączenia) | 🔌 caddy-ratelimit | 🔌 mod_evasive, mod_qos | ✅ middleware | ✅ |
| Limit współdzielony między procesami | ✅ współdzielona strefa pamięci | ❌ liczony na proces | — (tylko 1 proces) | zależnie od modułu | 1 instancja; kilka z Redis | ✅ pamięć współdzielona |
| WAF (sygnatury SQLi/XSS, skanery…) | 🔌 ModSecurity, Commercial (App Protect) | ❌ (skrypty Lua do napisania) | 🔌 Coraza | 🔌 ModSecurity | 🔌 wtyczki | ✅ wbudowany |
| Lista blokad z wygasaniem, recydywa | ⚙️ fail2ban | ⚙️ fail2ban | ⚙️ fail2ban | ⚙️ fail2ban | ⚙️ | ✅ wbudowana |
| Pułapki, tryb wojenny, incydenty, eksport IoC | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ Active Defense |
| Stopniowane blokady w czasie | ⚙️ fail2ban | ⚙️ fail2ban | ⚙️ fail2ban | ⚙️ fail2ban | ⚙️ | ✅ RIPOSTE |
| Audyt bezpieczeństwa konfiguracji | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ `audit security` |
| Tryb obserwacji (logowanie bez blokowania) | zależnie od modułu | — | zależnie od wtyczki | ✅ ModSecurity `DetectionOnly` | zależnie od wtyczki | ✅ |

Stopniowane blokady: coraz dłuższe blokady dla adresów, które wracają, przez tygodnie, lokalnie lub na poziomie sieci. fail2ban osiąga to opcją `bantime.increment`; RIPOSTE dodaje polityki mierzone na logach i symulowane przed włączeniem, uchylanie akcji i wyłącznik awaryjny.

### Rozszerzalność

| Funkcja | nginx | lighttpd | Caddy | Apache | Traefik | omega-serv 2.5 |
|---|---|---|---|---|---|---|
| Język skryptowy | 🧩 njs (JavaScript); 🔌 Lua (OpenResty) | ✅ Lua (mod_magnet) | moduły Go (rekompilacja) | 🧩 mod_lua | wtyczki Go lub WebAssembly | 🔌 import skryptów mod_magnet (opcja `magnet`) |
| Ekosystem modułów | bardzo duży | ukierunkowany | duży | bardzo duży | duży | brak: wszystko jest wbudowane |

---

## 8. Administracja i ergonomia

| Serwer | Główny sposób administracji | Interfejs | Przeładowanie bez przerwy |
|---|---|---|---|
| nginx | pliki konfiguracyjne | brak (panel: NGINX Plus, komercyjny) | ✅ `nginx -s reload` |
| lighttpd | plik konfiguracyjny | brak (mod_status tylko do odczytu) | ✅ łagodny restart |
| Caddy | Caddyfile lub JSON | REST API administracji | ✅ przez API |
| Apache | pliki konfiguracyjne i `.htaccess` | brak (mod_status tylko do odczytu) | ✅ `graceful` |
| Traefik | etykiety kontenerów, pliki lub Kubernetes | panel WWW (tylko do odczytu) | ✅ konfiguracja dynamiczna |
| omega-serv | interfejs terminalowy (TUI) i wiersz poleceń (CLI); pliku JSON nie trzeba edytować | **pełne TUI z klawiaturą i myszą, 17 języków, wbudowana pomoc** | ✅ dla większości ustawień; restart zapowiadany dla portu, TLS, silnika i liczby procesów |

W praktyce z omega-serv konfiguracją, bezpieczeństwem, logami, usługami systemowymi, kopiami zapasowymi i instancjami zarządza się z jednego interfejsu. Każde ustawienie jest objaśnione i sprawdzone przed zapisaniem. W innych serwerach edytuje się pliki tekstowe, a potem sięga po osobne narzędzia (Certbot, fail2ban, logrotate, ModSecurity, narzędzie monitorujące…).

Z drugiej strony podejście „plik konfiguracyjny” w nginx, Apache i Caddy bardzo dobrze się automatyzuje (Ansible, kontenery, kontrola wersji). omega-serv ma skryptowalne CLI, ale jego ekosystem automatyzacji pozostaje ograniczony.

---

## 9. Co omega-serv wnosi więcej

Ta sekcja uwzględnia tylko to, czego żaden z porównywanych serwerów nie zapewnia w takiej postaci, bez modułu zewnętrznego ani zewnętrznego narzędzia.

1. **Pełne zarządzanie w interfejsie terminalowym.**
   - Interfejs obejmuje cały serwer: stronę, bezpieczeństwo, logi, usługi, kopie zapasowe i instancje.
   - Obsługuje się go klawiaturą i myszą, na serwerze bez środowiska graficznego, nawet przez SSH.
   - Jest dostępny w 17 językach i objaśnia każde ustawienie.
   - Inne serwery nie mają interfejsu administracyjnego (nginx, lighttpd, Apache) albo mają tylko API (Caddy) lub panel tylko do odczytu (Traefik).
2. **Wbudowane aktywne bezpieczeństwo, bez składania modułów.**
   - WAF obejmuje sygnatury, edytowalne listy ścieżek, recydywę, listę blokad z wygasaniem, reputację i tryb obserwacji.
   - Active Defense dodaje pułapki, tryb wojenny, śledzenie incydentów, eksport wskaźników kompromitacji i symulację na sucho.
   - RIPOSTE reaguje w czasie: zapamiętuje adresy, które wracają, i stosuje wobec nich stopniowane odpowiedzi, coraz dłuższe blokady (domyślnie 1 h, 6 h, 24 h, 7 dni), lokalne na liście blokad lub sieciowe przez fail2ban (omega-jail), albo przedłużoną pułapkę. Każdą politykę można zmierzyć na prawdziwych logach i zasymulować przed włączeniem; każda akcja pozostaje widoczna i można ją uchylić, z wyłącznikiem awaryjnym.
   - Gdzie indziej te funkcje wymagają złożenia ModSecurity lub Coraza, zestawów reguł i fail2ban.
3. **Dokładne limity bezpieczeństwa przy wielu procesach.**
   - Przy wielu procesach limit żądań i recydywa WAF są współdzielone w pamięci między nimi. Atakujący nie może więc pomnożyć swojego limitu przez liczbę procesów.
   - lighttpd dokumentuje przypadek odwrotny: z `server.max-worker` `mod_evasive` i `mod_status` liczą osobno w każdym procesie.
   - nginx także współdzieli swoje liczniki (strefy `limit_req`), ale nie ma wbudowanego WAF.
4. **Dwa silniki, jedno zachowanie.** Silnik natywny i silnik Python dają te same odpowiedzi i te same logi, automatycznie sprawdzane na stanowisku porównawczym. Narzędzia czytające logi (na przykład fail2ban) nie widzą żadnej różnicy.
5. **Import skryptów mod_magnet z lighttpd.**
   - Skrypt ochronny Lua napisany już dla lighttpd jest importowany bez przepisywania.
   - Dodaje się do wbudowanej ochrony, nigdy nie mogąc jej osłabić, a jego zgodność jest sprawdzana przed włączeniem.
6. **Zarządzanie wieloma instancjami.**
   - Rejestr obejmuje wszystkie instancje, a interfejs przełącza się między nimi.
   - Potrafi też całkowicie odinstalować instancję.
7. **Audyt bezpieczeństwa konfiguracji**: polecenie `audit security` jest informacyjne, nigdy nie blokuje i zwraca kody wyjścia przydatne w skrypcie.
8. **Zdalne źródła logów.**
   - Interfejs pobiera przez SSH log innego serwera, na żądanie, bez zapisanego hasła.
   - Może go czytać w lnav, łącząc z logami lokalnymi.
9. **Utwardzenie HTTP, którego nie da się wyłączyć**, aktywne od instalacji, niezależnie od profilu i silnika:
   - ścisła walidacja nagłówka Host;
   - odrzucanie niejednoznaczności Content-Length / Transfer-Encoding;
   - nagłówki bezpieczeństwa i CSP w odpowiedziach strony, także na jej stronach błędów;
   - bezpieczne odczytywanie X-Forwarded-For;
   - odmowa uruchomienia jako root.

---

## 10. Co inni robią lepiej

- **Przepustowość**: lighttpd i nginx pozostają najszybsze dla małych i średnich plików, na wszystkich trzech maszynach. Nawet z silnikiem natywnym omega-serv osiąga około 0,7 nginx i 0,5 lighttpd dla małych plików oraz 0,3–0,6 nginx dla plików 100 KB. Dla strony o dużym ruchu, publicznego API lub CDN to je należy wybrać.
- **Średnie pliki**: Apache serwuje pliki 100 KB szybciej niż silnik natywny omega-serv, na wszystkich trzech maszynach.
- **Reverse proxy**:
  - nginx przekazuje małe odpowiedzi o 10–22 % szybciej niż silnik natywny, a w HTTPS na maszynie C nawet 1,6 raza szybciej;
  - w HTTPS, dla odpowiedzi 100 KB, wyprzedza go lighttpd na maszynie C oraz Caddy i Traefik na maszynie A;
  - nginx, lighttpd i Apache przekazują ruch przy 4–15 MB pamięci, omega-serv przy około 30.
- **Pamięć**: lighttpd (1 MB), nginx (4–5 MB) i Apache (4–9 MB) nadają się do bardzo ograniczonych maszyn (systemy wbudowane, małe kontenery). omega-serv 3.0.0 potrzebuje 10–55 zależnie od trybu.
- **Koszt bezpieczeństwa**: WAF nadal ma swój koszt. Z silnikiem natywnym odbiera 5–22 % przepustowości dla małych plików, łącznie z ograniczaniem liczby żądań: omega-serv z WAF osiąga 0,53–0,56 nginx bez WAF na maszynach A i B. Podejrzane lub wątpliwe żądanie (dopasowanie reguły, tekst spoza ASCII, źródło śledzone przez Active Defense) zawsze przechodzi przez Pythona i jest obsługiwane z szybkością silnika Python. Z aktywnym magnetem wszystkie żądania przechodzą przez Pythona, a WAF dzieli wtedy przepustowość silnika natywnego przez 4–7, jak przed optymalizacją.
- **Protokoły**: HTTP/2 u wszystkich pozostałych, HTTP/3 w nginx, Caddy i Traefiku. omega-serv obsługuje tylko HTTP/1.1.
- **Automatyczny HTTPS**: Caddy i Traefik mają go domyślnie, a nginx (`ngx_http_acme_module`) i Apache (`mod_md`) z oficjalnym modułem. omega-serv deleguje to Certbotowi, z kreatorem i zaplanowanym odnawianiem.
- **Środowiska kontenerowe**: automatyczne wykrywanie usług w Traefiku (Docker, Kubernetes) nie ma odpowiednika w omega-serv.
- **Ekosystem i dojrzałość**: nginx i Apache oferują tysiące modułów, poradników i integracji oraz dziesięciolecia użycia produkcyjnego. Caddy oferuje system modułów w Go. omega-serv to młody projekt, utrzymywany przez jedną osobę, a jego silnik natywny jest nowy.
- **Kompresja w locie**: omega-serv serwuje tylko pliki już skompresowane.

---

## 11. Jaki serwer do jakiego zastosowania

| Potrzeba | Zalecany wybór |
|---|---|
| Strona o dużym ruchu, publiczne API, CDN, maksymalna przepustowość | **nginx** lub **lighttpd** |
| Reverse proxy o maksymalnej przepustowości, HTTP/2 lub HTTP/3 do klientów | **nginx** |
| Bardzo ograniczona maszyna, system wbudowany, pliki statyczne | **lighttpd** |
| Szybki start z automatycznym HTTPS, krótka konfiguracja | **Caddy** |
| Starsza aplikacja PHP, `.htaccess`, hosting współdzielony | **Apache** |
| Docker, Kubernetes, mikrousługi | **Traefik** |
| Mała lub średnia strona, usługa wewnętrzna, laboratorium, VPN, administracja bez edycji plików | **omega-serv** (silnik natywny, jeśli to możliwe) |
| Wystawiony serwer, którego bezpieczeństwo (WAF, stopniowane blokady, pułapki) chce się widzieć i kontrolować z jednego interfejsu | **omega-serv** |
| Reverse proxy z równoważeniem, kontrolą zdrowia, pamięcią podręczną i WAF, sterowany z interfejsu | **omega-serv** (silnik natywny: drugi za nginx pod względem przepustowości) |
| Nauka utwardzania HTTP i aktywnej obrony | **omega-serv** |

Te narzędzia można też łączyć. Na przykład:
- nginx lub Traefik z przodu, od strony Internetu, z omega-serv za nimi dla usługi wewnętrznej, jej bezpieczeństwa i administracji;
- omega-serv jako wewnętrzny reverse proxy przed kilkoma serwerami aplikacji.

---

## 12. Odtworzenie pomiarów

Narzędzia są dostarczane w repozytorium, w `tools/bench/`. Potrzebne są zainstalowane nginx, lighttpd, Apache, Caddy i oha (oraz Traefik dla reverse proxy), środowisko deweloperskie omega-serv (`.venv`) oraz, dla silnika natywnego, plik binarny skompilowany w `native/omega-http-core/build-release`.

```sh
# 1. przygotować katalog pomiarowy (pliki testowe, konfiguracje, omega-serv 1.0, 2.0 i wersja bieżąca)
tools/bench/compare/setup.sh /sciezka/pomiar omega-serv-1.0.0.tar.gz omega-serv-2.0.0.tar.gz

# 2. 21 konfiguracji, 3 przeplatane powtórzenia (40–60 minut)
#    SRV_CPUS / CLI_CPUS: rdzenie serwera i klienta (lscpu -e pokazuje topologię)
SRV_CPUS=0,1 CLI_CPUS=2,3 tools/bench/compare/campaign.sh /sciezka/pomiar > wyniki.txt

# 3. mediany
python3 tools/bench/compare/summarize.py wyniki.txt

# inna lista konfiguracji, na przykład 4 procesy
CONFIGS="nginx-4 lighttpd-4 caddy-4 apache-4 omega-v2-1-0-native omega-v2-4-1-native" \
  tools/bench/compare/campaign.sh /sciezka/pomiar > wyniki-4.txt

# duże pobierania (pamięć i responsywność): wersja bieżąca, silnik Python, potem natywny, potem 1.0
.venv/bin/python tools/bench/bigfile.py
BENCH_ENGINE=native .venv/bin/python tools/bench/bigfile.py
BENCH_SRC=/sciezka/pomiar/v1-archive/omega-serv/src \
BENCH_EXTRA_PATH=/sciezka/pomiar/v1-archive/omega-serv/vendor/omega-lib/src \
  .venv/bin/python tools/bench/bigfile.py

# reverse proxy (§5): backend, certyfikat, konfiguracje 6 proxy, potem 3 przeplatane powtórzenia
#    maszyna C: SRV_CPUS=0-3 BACK_CPUS=4,5 CLI_CPUS=6-9 i CONFIGS="nginx-4 lighttpd-4 apache-4 caddy-4 traefik-4 omega-nat-1-0 omega-nat-1-1"
tools/bench/proxy/setup.sh /sciezka/proxy /sciezka/do/traefik
SRV_CPUS=0,1 CLI_CPUS=2,3 tools/bench/proxy/campaign.sh /sciezka/proxy > proxy.txt
python3 tools/bench/proxy/summarize.py proxy.txt

# ponowny pomiar samego omega-serv (pamięć 3.0.0): pliki, duże pobierania i reverse proxy, nginx jako odniesienie
MACHINE=a SRV_CPUS=0,2 CLI_CPUS=1,3 tools/bench/memoire-3.0.0.sh /sciezka/pomiar > pamiec.txt

# zmierzyć dowolny inny, już uruchomiony serwer, bez oha
python3 tools/bench/bench_any.py --make-files /srv/webroot-testowy
python3 tools/bench/bench_any.py --port 8080
```

Nazwy konfiguracji: `nginx-N`, `lighttpd-N`, `apache-N`, `caddy-N` (N procesów lub N rdzeni dla Caddy); `omega-vX-N-W` dla omega-serv (wersja `v1`, `v20` lub `v2` dla wersji bieżącej, N procesów, W = 0 bez WAF lub 1 z WAF), z przyrostkiem `-native` dla silnika natywnego.

Dla reverse proxy: `nginx-N`, `lighttpd-N`, `apache-N`, `caddy-N`, `traefik-N`, `omega-py-N-W` (silnik Python) i `omega-nat-N-W` (silnik natywny, N procesów bezpieczeństwa), z przyrostkiem `-tls` dla HTTPS po stronie klienta.

Aby opublikować własne wyniki, podaj maszynę, wersje, przydział rdzeni i trzy powtórzenia.

---

## 13. Źródła

Funkcje pozostałych serwerów według ich oficjalnej dokumentacji (sprawdzonej 26 października 2026).

**nginx**
- [Limit żądań `limit_req` (współdzielona strefa pamięci)](https://nginx.org/en/docs/http/ngx_http_limit_req_module.html)
- [Pliki wstępnie skompresowane `gzip_static`](https://nginx.org/en/docs/http/ngx_http_gzip_static_module.html)
- [Oficjalny moduł ACME `ngx_http_acme_module`](https://nginx.org/en/docs/http/ngx_http_acme_module.html)
- [Równoważenie obciążenia (`upstream`)](https://nginx.org/en/docs/http/ngx_http_upstream_module.html)
- [HTTP/3](https://nginx.org/en/docs/http/ngx_http_v3_module.html)
- [Łącznik ModSecurity dla nginx](https://github.com/owasp-modsecurity/ModSecurity-nginx)

**lighttpd**
- [`server.max-worker`: odradzany, liczniki na proces dla mod_status i mod_evasive](https://redmine.lighttpd.net/projects/lighttpd/wiki/Server_max-workerDetails)
- [mod_magnet (skrypty Lua)](https://redmine.lighttpd.net/projects/lighttpd/wiki/Docs_ModMagnet)
- [mod_deflate (kompresja, pamięć podręczna)](https://redmine.lighttpd.net/projects/lighttpd/wiki/Mod_deflate)
- [mod_proxy (równoważenie, pasywna kontrola zdrowia, WebSocket)](https://redmine.lighttpd.net/projects/lighttpd/wiki/Docs_ModProxy)
- [mod_evasive (jednoczesne połączenia na adres)](https://redmine.lighttpd.net/projects/lighttpd/wiki/Docs_ModEvasive)

**Caddy**
- [Automatyczny HTTPS](https://caddyserver.com/docs/automatic-https)
- [`file_server` i `precompressed`](https://caddyserver.com/docs/caddyfile/directives/file_server)
- [`reverse_proxy` (strategie, aktywna i pasywna kontrola zdrowia)](https://caddyserver.com/docs/caddyfile/directives/reverse_proxy)
- [API administracji](https://caddyserver.com/docs/api)
- [Wtyczka limitu żądań caddy-ratelimit](https://github.com/mholt/caddy-ratelimit)
- [WAF Coraza dla Caddy](https://github.com/corazawaf/coraza-caddy)
- [caddy-docker-proxy](https://github.com/lucaslorentz/caddy-docker-proxy)

**Apache HTTP Server**
- [MPM event](https://httpd.apache.org/docs/2.4/mod/event.html)
- [mod_md (ACME)](https://httpd.apache.org/docs/2.4/mod/mod_md.html)
- [mod_proxy_balancer](https://httpd.apache.org/docs/2.4/mod/mod_proxy_balancer.html)
- [mod_proxy_hcheck](https://httpd.apache.org/docs/2.4/mod/mod_proxy_hcheck.html)
- [mod_http2](https://httpd.apache.org/docs/2.4/mod/mod_http2.html)
- [mod_deflate, treść wstępnie skompresowana](https://httpd.apache.org/docs/2.4/mod/mod_deflate.html)
- [ModSecurity](https://github.com/owasp-modsecurity/ModSecurity)

**Traefik**
- [Middleware `ratelimit` (w pamięci na instancję, Redis opcjonalnie)](https://doc.traefik.io/traefik/reference/routing-configuration/http/middlewares/ratelimit/)
- [ACME](https://doc.traefik.io/traefik/https/acme/)
- [Providers (Docker, Kubernetes…)](https://doc.traefik.io/traefik/providers/overview/)

**fail2ban**
- [`jail.conf`: `bantime.increment`, `bantime.factor`, `bantime.multipliers`, `bantime.maxtime` (dłuższe blokady dla recydywistów)](https://github.com/fail2ban/fail2ban/blob/master/config/jail.conf) (sprawdzone 4 listopada 2026)

**Narzędzie pomiarowe**
- [oha](https://github.com/hatoo/oha)

---

*Porównanie przygotowane przez kraynux dla omega-serv 2.5 i 3.0.0: pomiary z 3 i 4 listopada 2026 na trzech maszynach (reverse proxy: 14 listopada 2026; pamięć omega-serv 3.0.0: 19 listopada 2026; aktywna obrona: 26 października 2026). Przy każdej decyzji dotyczącej wydajności mierz na własnym sprzęcie dostarczonymi narzędziami.*
