<!-- Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE) -->

# omega-serv na tle serwerów WWW dostępnych na rynku

**Porównanie oparte na pomiarach: nginx · lighttpd · Caddy · Apache · Traefik · omega-serv 2.0**

🌐 [Français](../../comparatif-serveurs-web.md) · [English](../en/comparatif-serveurs-web.md) · [Español](../es/comparatif-serveurs-web.md) · [Português (Brasil)](../pt-BR/comparatif-serveurs-web.md) · [Italiano](../it/comparatif-serveurs-web.md) · [Deutsch](../de/comparatif-serveurs-web.md) · [Nederlands](../nl/comparatif-serveurs-web.md) · **Polski** · [Русский](../ru/comparatif-serveurs-web.md) · [中文](../zh-CN/comparatif-serveurs-web.md) · [Tiếng Việt](../vi/comparatif-serveurs-web.md) · [ไทย](../th/comparatif-serveurs-web.md) · [Bahasa Indonesia](../id/comparatif-serveurs-web.md) · [日本語](../ja/comparatif-serveurs-web.md) · [한국어](../ko/comparatif-serveurs-web.md) · [हिन्दी](../hi/comparatif-serveurs-web.md) · [العربية](../ar/comparatif-serveurs-web.md)

Ten dokument umiejscawia omega-serv wśród najpopularniejszych serwerów WWW. Nie próbuje wskazać „najlepszego serwera”: każde narzędzie odpowiada na inne potrzeby. Dostarcza trzech rzeczy:

1. **rzeczywistych pomiarów**, wykonanych na tej samej maszynie, tym samym klientem i na tych samych plikach, możliwych do powtórzenia;
2. **porównania funkcji**, z których każda została sprawdzona w oficjalnej dokumentacji danego serwera (linki na końcu dokumentu), z rozróżnieniem tego, co wbudowane, od tego, co wymaga modułu lub wtyczki;
3. tego, co omega-serv **naprawdę wnosi dodatkowo**, i tego, co inni robią **lepiej od niego**.

Wszystkie poniższe liczby zmierzono 26 października 2026 r. Żadna liczba nie pochodzi z innej strony ani nie jest szacunkiem.

---

## Spis treści

1. [W skrócie](#1-w-skrócie)
2. [Metoda pomiaru](#2-metoda-pomiaru)
3. [Wydajność: omega-serv na tle nginx, lighttpd i Caddy](#3-wydajność-omega-serv-na-tle-nginx-lighttpd-i-caddy)
4. [omega-serv 1.0 → 2.0: co się zmieniło, w pomiarach](#4-omega-serv-10--20-co-się-zmieniło-w-pomiarach)
5. [Porównanie funkcji](#5-porównanie-funkcji)
6. [Administracja i ergonomia](#6-administracja-i-ergonomia)
7. [Co omega-serv wnosi dodatkowo](#7-co-omega-serv-wnosi-dodatkowo)
8. [Co inni robią lepiej](#8-co-inni-robią-lepiej)
9. [Który serwer do jakiego zastosowania](#9-który-serwer-do-jakiego-zastosowania)
10. [Powtórzenie pomiarów](#10-powtórzenie-pomiarów)
11. [Źródła](#11-źródła)

---

## 1. W skrócie

- **Surowa przepustowość dla małych plików**: nginx i lighttpd, napisane w C, obsługują **10–20 razy więcej** żądań na sekundę niż omega-serv, napisany w Pythonie. Caddy, napisany w Go, plasuje się pośrodku. To różnica natury, nie konfiguracji: omega-serv nie celuje w ten obszar.
- **Duże pliki**: od wersji 2.0 omega-serv powierza wysyłanie jądru (`sendfile`). Osiąga wtedy na tej maszynie **ten sam rząd przepustowości** co nginx, lighttpd i Caddy: 2,1 GB/s wobec 2,0–2,4 GB/s.
- **Pamięć**: lighttpd (1 MB) i nginx (4–5 MB) pozostają poza zasięgiem. omega-serv mieści się pod obciążeniem poniżej 30 MB przy 1 procesie, Caddy około 55 MB.
- **Z 1.0 do 2.0**: przepustowość dla dużych plików pomnożona przez 2,8; pamięć przy dużych pobraniach podzielona przez 45; do +50% dla małych plików przy 2 procesach (tryb boost); koszt Active Defense podzielony przez 12.
- **Co omega-serv ma dodatkowo**: pełną administrację z interfejsu terminalowego (TUI) w 17 językach; wbudowany WAF i aktywną obronę; limity bezpieczeństwa, które pozostają dokładne przy wielu procesach; import skryptów mod_magnet z lighttpd; zarządzanie wieloma instancjami.
- **Czego nie ma**: HTTP/2 i HTTP/3, wykrywania usług Docker/Kubernetes, wbudowanego klienta ACME (korzysta z Certbota), przepustowości serwera napisanego w C.

---

## 2. Metoda pomiaru

### Maszyna i oprogramowanie

| Element | Wartość |
|---|---|
| Procesor | Intel Core i5 M480 2,67 GHz (2010): 2 rdzenie fizyczne, 4 wątki |
| Pamięć | 8 GB |
| System | Manjaro Linux, jądro 6.18 |
| Sieć | pętla zwrotna (127.0.0.1) |
| Klient obciążający | [oha](https://github.com/hatoo/oha) 1.16.0 (napisany w Rust) |
| nginx | 1.30.4 (pakiet Manjaro) |
| lighttpd | 1.4.85 (pakiet Manjaro) |
| Caddy | 2.11.4 (pakiet Manjaro) |
| omega-serv | 1.0.0 (opublikowane archiwum) i 2.0.0, pod Pythonem 3.14.7 |

Apache i Traefik nie zostały zmierzone, ponieważ nie były zainstalowane na tej maszynie. Traefik zresztą nie jest serwerem plików (zob. §5). Te dwa serwery występują więc tylko w porównaniu funkcji.

### Protokół

- **Izolacja procesora**: każdy serwer jest przypięty do fizycznego rdzenia 0 (wątki 0 i 2), a klient do fizycznego rdzenia 1 (wątki 1 i 3). Dzięki temu klient nie zabiera czasu serwerowi, a wszystkie serwery dysponują dokładnie tymi samymi zasobami.
- **Te same pliki dla wszystkich**: `small.html` (1 KB), `medium.png` (100 KB) i `large.bin` (5 MB), serwowane z tego samego folderu.
- **Dziennik dostępu włączony wszędzie**, bo serwer produkcyjny prowadzi dziennik.
- **HTTP/1.1 bez szyfrowania, połączenia trwałe (keep-alive)**. Współbieżność wynosi 32 połączenia dla plików 1 KB i 100 KB oraz 8 dla pliku 5 MB.
- **Czas trwania**: 10 sekund na plik i na konfigurację.
- **Powtórzenia**: 3 pełne, przeplatane rundy (wszystkie serwery w rundzie 1, potem wszystkie w rundzie 2 itd.). Tabele podają **medianę** z trzech rund.
- **Pamięć**: PSS (*Proportional Set Size*) zsumowany dla wszystkich procesów serwera. W przeciwieństwie do RSS strona współdzielona między procesami jest liczona tylko raz. Mierzona w spoczynku, a następnie po obciążeniu.
- **Konfiguracje**: nginx, lighttpd i Caddy w konfiguracji podstawowej (pliki statyczne, dziennik dostępu). omega-serv używa profilu `standard`, z wyłączonym WAF, a następnie z włączonym WAF i wszystkimi dostarczonymi regułami.
- **Liczba procesów**: każdy serwer mierzony jest z 1, a potem z 2 procesami (nginx `worker_processes`, lighttpd `server.max-worker`, Caddy `GOMAXPROCS`, omega-serv `server.workers`).

### Ograniczenia, o których warto wiedzieć

- **Skromna i stara maszyna.** Wartości bezwzględne byłyby znacznie wyższe na nowym serwerze. Sens mają **proporcje** między serwerami zmierzonymi w tej samej sesji.
- **Zmienność między sesjami**: około 10–30% zależnie od obciążenia tła maszyny. Rundy w ramach jednej sesji pozostają spójne: poniżej 5% różnicy dla omega-serv i Caddy, więcej dla nginx i lighttpd, których bardzo wysoka przepustowość jest bardziej wrażliwa na resztę maszyny.
- **Pętla zwrotna**: pomiar nie przechodzi przez prawdziwą sieć. W prawdziwej sieci przepustowość dla dużych plików niemal zawsze ogranicza pasmo, a nie serwer.
- **Brak TLS** w tych pomiarach. Przy HTTPS omega-serv nie może używać `sendfile` i wysyła pliki blokami.
- **Surowe wyniki**: są publikowane wraz z tym dokumentem w [`docs/benchmarks/2026-10-26-campagne-brute.txt`](../../benchmarks/2026-10-26-campagne-brute.txt).

---

## 3. Wydajność: omega-serv na tle nginx, lighttpd i Caddy

### Małe pliki (1 KB): żądania na sekundę

| Serwer | 1 proces | 2 procesy | Opóźnienie p99 (1 proc.) |
|---|---:|---:|---:|
| lighttpd 1.4.85 | 25 521 | 29 700 | 4,5 ms |
| nginx 1.30.4 | 14 054 | 18 315 | 4,7 ms |
| Caddy 2.11.4 | 3 697 | 5 345 | 25,3 ms |
| **omega-serv 2.0** | **1 358** | **1 953** | **37,5 ms** |
| omega-serv 2.0 + WAF | 1 130 | 1 617 | 48,5 ms |
| omega-serv 1.0 | 1 304 | — | 41,2 ms |

### Średnie pliki (100 KB): żądania na sekundę

| Serwer | 1 proces | 2 procesy |
|---|---:|---:|
| lighttpd | 11 635 | 13 037 |
| nginx | 8 024 | 9 555 |
| Caddy | 3 280 | 4 344 |
| **omega-serv 2.0** | **1 247** | **1 629** |
| omega-serv 2.0 + WAF | 1 012 | 1 347 |
| omega-serv 1.0 | 1 064 | — |

### Duży plik (5 MB): przepustowość

| Serwer | 1 proces | 2 procesy |
|---|---:|---:|
| lighttpd | 2 379 MB/s | 2 407 MB/s |
| nginx | 2 242 MB/s | 1 981 MB/s |
| Caddy | 2 165 MB/s | 2 229 MB/s |
| **omega-serv 2.0** | **1 658 MB/s** | **2 115 MB/s** |
| omega-serv 1.0 | 584 MB/s | — |

### Pamięć (PSS, wszystkie procesy serwera)

| Serwer | W spoczynku | Po obciążeniu |
|---|---:|---:|
| lighttpd (1 lub 2 proc.) | 1 MB | 1 MB |
| nginx (1 lub 2 proc.) | 4–5 MB | 4–5 MB |
| **omega-serv 2.0 (1 proc.)** | **26 MB** | **30 MB** |
| omega-serv 2.0 (2 proc.) | 39 MB | 48 MB |
| Caddy | 50 MB | 56 MB |
| omega-serv 1.0 | 22 MB | 100 MB |

### Interpretacja

- **Dla małych i średnich plików** różnica względem nginx i lighttpd to rząd wielkości (×10 do ×20). To koszt serwera napisanego w Pythonie: każde żądanie przechodzi przez interpreter, podczas gdy nginx i lighttpd przetwarzają je w skompilowanym C. Tryb boost zmniejsza różnicę, ale jej nie niweluje.
- **Dla dużych plików** serwery się zbliżają, bo dane kopiuje jądro (`sendfile`). Przy 2 procesach omega-serv 2.0 osiąga 2,1 GB/s, w tym samym przedziale co pozostałe (2,0–2,4 GB/s).
- **WAF omega-serv kosztuje około 17%** przy małych plikach: sprawdza każde żądanie. nginx, lighttpd i Caddy mierzono bez WAF; WAF dodany do tych serwerów (ModSecurity, Coraza) również ma swój koszt, którego tu nie mierzono.
- **Dla porównania**: 1 300 żądań na sekundę to ponad 110 milionów żądań dziennie na tej maszynie z 2010 roku. To znacznie więcej, niż potrzebuje strona osobista, usługa wewnętrzna czy laboratorium – czyli zastosowania, w które celuje omega-serv.

---

## 4. omega-serv 1.0 → 2.0: co się zmieniło, w pomiarach

### Wydajność

Obie wersje zmierzono w tej samej sesji, na tej samej maszynie i tym samym protokołem.

| Pomiar | 1.0.0 | 2.0.0 | Zmiana |
|---|---:|---:|---:|
| Małe pliki (1 KB), 1 proces | 1 304 żąd./s | 1 358 żąd./s | +4% |
| Małe pliki (1 KB), tryb boost 2 procesy | — | 1 953 żąd./s | **+50%** wzgl. 1.0 |
| Małe pliki z WAF, 1 proces | 1 097 żąd./s | 1 130 żąd./s | +3% |
| Małe pliki z WAF, 2 procesy | — | 1 617 żąd./s | **+47%** wzgl. 1.0 |
| Pliki 100 KB, 1 proces | 1 064 żąd./s | 1 247 żąd./s | +17% |
| Duży plik (5 MB), 1 proces | 584 MB/s | 1 658 MB/s | **×2,8** |
| Duży plik (5 MB), 2 procesy | — | 2 115 MB/s | **×3,6** wzgl. 1.0 |
| Pamięć po obciążeniu, 1 proces | 100 MB | 30 MB | **÷3** |

### Równoczesne duże pobrania

Test: 3 równoczesne pobrania pliku 300 MB, podczas gdy mała strona jest pobierana w sposób ciągły. Dwa przebiegi dają identyczne wyniki.

| Pomiar | 1.0.0 | 2.0.0 |
|---|---:|---:|
| Szczytowe zużycie pamięci serwera | 1 835 MB | 40 MB |
| Mała strona podczas pobrań: mediana | 3–4 ms | 2 ms |
| Mała strona podczas pobrań: najgorszy przypadek | 1,7–1,8 s | 5 ms |

Wersja 1.0 wczytywała każdy plik w całości do pamięci przed wysłaniem. Wersja 2.0 wysyła go blokami albo powierza jądru: pamięć nie zależy już od rozmiaru plików, a serwer pozostaje responsywny podczas pobrań.

### Koszt aktywnej obrony

Koszt jednej obserwacji zagrożenia przez Active Defense, dla każdego podejrzanego żądania, zmierzony na dysku (ext4) na 2 000 obserwacji:

| Pomiar | 1.0.0 | 2.0.0 |
|---|---:|---:|
| Mediana | 2,84 ms | 0,23 ms |
| p99 | 11,6 ms | 2,3 ms |
| Maksimum | 18–20 ms | 37–46 ms |

Mediana jest podzielona przez 12. Maksimum jest natomiast wyższe w 2.0: kilka pojedynczych skoków spowodowanych okresowym zapisem dziennika SQLite na dysk.

### Funkcje, które przyszły z wersją 2.0

**Wyrównanie do standardów rynkowych**: nginx, lighttpd, Caddy i Apache już to wszystko robią. omega-serv nadrabia zaległości.

- Żądania warunkowe (ETag, Last-Modified, odpowiedzi 304): przy przeładowaniu strony ponownie pobierane jest tylko to, co się zmieniło.
- Żądania częściowe (Range, 206/416): wznowienie pobierania, przewijanie wideo.
- Wysyłanie plików przez `sendfile` lub blokami, przy stabilnym zużyciu pamięci.
- Wstępnie skompresowane pliki (`.gz`, `.br`) umieszczone obok oryginału.
- Domyślny Cache-Control według typu pliku (obrazy, czcionki, CSS/JS), z możliwością zmiany.
- Wiele procesów serwera (tryb boost, `server.workers`).

**Szersze funkcje:**

- **Pełne reverse proxy.** Wersja 1.0 miała tylko proste przekazywanie (po kolei, TLS do serwera źródłowego, WebSocket). Wersja 2.0 dodaje:
  - 6 strategii rozdzielania, łącznie 7;
  - powinowactwo sesji i trasowanie według nagłówka;
  - pasywną i aktywną kontrolę stanu serwerów źródłowych;
  - pamięć podręczną odpowiedzi;
  - ochronę przed przeciążeniem i przed pętlami;
  - sterowanie w trakcie pracy.
- **Limit żądań na folder oraz na adres lub sieć**, oprócz limitu globalnego.
- **Liczniki bezpieczeństwa współdzielone między procesami** (zob. §7).
- **Gotowe listy wrażliwych ścieżek**, z trybem obserwacji i wbudowanym edytorem.
- **Import skryptów mod_magnet z lighttpd** (zob. §7).
- **Interfejs w 17 językach**, z osobnym językiem dla stron widocznych dla odwiedzających i dla eksportów.
- **Całkowicie przebudowane dzienniki**:
  - biblioteka dzienników;
  - trzy przeglądarki, w tym lnav;
  - pobieranie zdalnych dzienników przez SSH.

---

## 5. Porównanie funkcji

Legenda:
- ✅ wbudowane;
- 🧩 oficjalny moduł projektu, do włączenia lub zainstalowania;
- 🔌 moduł lub wtyczka zewnętrznego dostawcy;
- ⚙️ za pomocą zewnętrznego narzędzia;
- ❌ brak.

„Komercyjne” oznacza funkcję zarezerwowaną dla płatnej edycji.

### Obsługa HTTP

| Funkcja | nginx | lighttpd | Caddy | Apache | Traefik | omega-serv 2.0 |
|---|---|---|---|---|---|---|
| Serwowanie plików statycznych | ✅ | ✅ | ✅ | ✅ | ❌ (tylko proxy) | ✅ |
| ETag / 304 / Range | ✅ | ✅ | ✅ | ✅ | — | ✅ |
| Wstępnie skompresowane pliki `.gz` / `.br` | ✅ `gzip_static` (`.br`: 🔌) | 🔌 skrypt Lua (mod_magnet) | ✅ `precompressed` | 🧩 przepis z mod_rewrite | — | ✅ |
| Kompresja w locie | ✅ | ✅ mod_deflate | ✅ | 🧩 mod_deflate | ✅ middleware | ❌ |
| HTTP/2 | ✅ | ✅ | ✅ | 🧩 mod_http2 | ✅ | ❌ |
| HTTP/3 (QUIC) | ✅ | ❌ | ✅ | ❌ | ✅ | ❌ |
| PHP przez FastCGI | ✅ | ✅ | ✅ | ✅ | ❌ | ✅ |
| Wiele procesów lub rdzeni | ✅ workery | ⚠️ `max-worker`, odradzane przez dokumentację | ✅ (Go, wszystkie rdzenie) | ✅ MPM | ✅ (Go) | ✅ `server.workers` |

### Reverse proxy

| Funkcja | nginx | lighttpd | Caddy | Apache | Traefik | omega-serv 2.0 |
|---|---|---|---|---|---|---|
| Rozdzielanie obciążenia | ✅ po kolei, najmniej połączeń, hash | ✅ fair, round-robin, hash, sticky | ✅ kilkanaście strategii | 🧩 mod_proxy_balancer | ✅ wrr, p2c, hrw, least-time | ✅ 7 strategii, w tym rzeczywiste obciążenie |
| Kontrola pasywna (odsunięcie niedziałającego serwera) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Kontrola aktywna (okresowa sonda) | Komercyjne (NGINX Plus) | ❌ | ✅ | 🧩 mod_proxy_hcheck | ✅ | ✅ |
| Pamięć podręczna odpowiedzi | ✅ `proxy_cache` | ❌ | 🔌 | 🧩 mod_cache | Komercyjne | ✅ |
| WebSocket | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Wykrywanie usług (Docker, Kubernetes) | 🔌 | ❌ | 🔌 | ❌ | ✅ (rdzeń projektu) | ❌ |

### TLS

| Funkcja | nginx | lighttpd | Caddy | Apache | Traefik | omega-serv 2.0 |
|---|---|---|---|---|---|---|
| Automatyczne certyfikaty (ACME, Let's Encrypt) | 🧩 `ngx_http_acme_module` | ⚙️ Certbot | ✅ domyślnie | 🧩 mod_md | ✅ | ⚙️ Certbot, z wbudowanym kreatorem i zaplanowanym odnawianiem |
| Lokalny urząd certyfikacji (CA) | ❌ | ❌ | ✅ wewnętrzny CA (automatyczne wystawianie) | ❌ | ❌ | ✅ generowanie, podpisywanie CSR, unieważnianie |

### Bezpieczeństwo

| Funkcja | nginx | lighttpd | Caddy | Apache | Traefik | omega-serv 2.0 |
|---|---|---|---|---|---|---|
| Limit żądań na klienta | ✅ `limit_req` | ⚠️ mod_evasive (tylko połączenia równoczesne) | 🔌 caddy-ratelimit | 🔌 mod_evasive, mod_qos | ✅ middleware | ✅ |
| Limit współdzielony między procesami | ✅ strefa pamięci współdzielonej | ❌ liczony na proces | — (jeden proces) | zależnie od modułu | 1 instancja; kilka z Redisem | ✅ pamięć współdzielona |
| WAF (sygnatury SQLi/XSS, skanery…) | 🔌 ModSecurity, Komercyjne (App Protect) | ❌ (skrypty Lua do napisania) | 🔌 Coraza | 🔌 ModSecurity | 🔌 wtyczki | ✅ wbudowany |
| Lista blokad z wygasaniem, recydywa | ⚙️ fail2ban | ⚙️ fail2ban | ⚙️ fail2ban | ⚙️ fail2ban | ⚙️ | ✅ wbudowane |
| Przynęty, tryb wojenny, incydenty, eksport IoC | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ Active Defense |
| Audyt bezpieczeństwa konfiguracji | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ `audit security` |
| Tryb obserwacji (rejestrowanie bez blokowania) | zależnie od modułu | — | zależnie od wtyczki | ✅ ModSecurity `DetectionOnly` | zależnie od wtyczki | ✅ |

### Rozszerzalność

| Funkcja | nginx | lighttpd | Caddy | Apache | Traefik | omega-serv 2.0 |
|---|---|---|---|---|---|---|
| Język skryptowy | 🧩 njs (JavaScript); 🔌 Lua (OpenResty) | ✅ Lua (mod_magnet) | moduły Go (rekompilacja) | 🧩 mod_lua | wtyczki Go lub WebAssembly | 🔌 import skryptów mod_magnet (opcja `magnet`) |
| Ekosystem modułów | bardzo szeroki | ukierunkowany | szeroki | bardzo szeroki | szeroki | brak: wszystko jest wbudowane |

---

## 6. Administracja i ergonomia

| Serwer | Główny sposób administracji | Interfejs | Przeładowanie bez przerwy |
|---|---|---|---|
| nginx | pliki konfiguracyjne | brak (panel: NGINX Plus, komercyjny) | ✅ `nginx -s reload` |
| lighttpd | plik konfiguracyjny | brak (mod_status, tylko odczyt) | ✅ łagodny restart |
| Caddy | Caddyfile lub JSON | API REST do administracji | ✅ przez API |
| Apache | pliki konfiguracyjne i `.htaccess` | brak (mod_status, tylko odczyt) | ✅ `graceful` |
| Traefik | etykiety kontenerów, pliki lub Kubernetes | panel WWW (tylko odczyt) | ✅ konfiguracja dynamiczna |
| omega-serv | interfejs terminalowy (TUI) i wiersz poleceń (CLI); pliku JSON nie trzeba nigdy edytować ręcznie | **pełny TUI z klawiaturą i myszą, 17 języków, wbudowana pomoc** | ✅ dla większości ustawień; zapowiadany restart przy zmianie portu, TLS i liczby procesów |

W praktyce w omega-serv konfiguracja, bezpieczeństwo, dzienniki, usługi systemowe, kopie zapasowe i instancje są zarządzane z jednego interfejsu. Każde ustawienie jest objaśniane i sprawdzane przed zapisaniem. W pozostałych serwerach edytuje się pliki tekstowe, a potem sięga po osobne narzędzia (Certbot, fail2ban, logrotate, ModSecurity, narzędzie do monitorowania…).

W zamian podejście „plików konfiguracyjnych” w nginx, Apache i Caddy bardzo dobrze się automatyzuje (Ansible, kontenery, kontrola wersji). omega-serv ma CLI nadające się do skryptów, ale jego ekosystem automatyzacji pozostaje ograniczony.

---

## 7. Co omega-serv wnosi dodatkowo

Ta sekcja obejmuje wyłącznie to, czego żaden z porównywanych serwerów nie dostarcza w takiej postaci, bez modułu zewnętrznego ani narzędzia zewnętrznego.

1. **Pełna administracja z interfejsu terminalowego.**
   - Interfejs obejmuje cały serwer: stronę, bezpieczeństwo, dzienniki, usługi, kopie zapasowe i instancje.
   - Obsługuje się go klawiaturą i myszą, na serwerze bez środowiska graficznego, także przez SSH.
   - Jest dostępny w 17 językach i objaśnia każde ustawienie.
   - Pozostałe serwery nie mają interfejsu administracyjnego (nginx, lighttpd, Apache) albo mają tylko API (Caddy) lub panel tylko do odczytu (Traefik).
2. **Wbudowane aktywne bezpieczeństwo, bez składania modułów.**
   - WAF obejmuje sygnatury, edytowalne listy ścieżek, recydywę, listę blokad z wygasaniem, reputację i tryb obserwacji.
   - Active Defense dodaje przynęty, tryb wojenny, śledzenie incydentów, eksport wskaźników kompromitacji i symulację na sucho.
   - Gdzie indziej te funkcje wymagają złożenia ModSecurity lub Coraza, zestawów reguł i fail2ban.
3. **Dokładne limity bezpieczeństwa przy wielu procesach.**
   - W trybie boost limit żądań i recydywa WAF są współdzielone w pamięci między procesami. Atakujący nie może więc pomnożyć swojego limitu przez liczbę procesów.
   - lighttpd dokumentuje przypadek odwrotny: przy `server.max-worker` moduły `mod_evasive` i `mod_status` liczą osobno w każdym procesie.
   - nginx również współdzieli swoje liczniki (strefy `limit_req`), ale nie ma wbudowanego WAF.
4. **Import skryptów mod_magnet z lighttpd.**
   - Skrypt ochronny w Lua napisany już dla lighttpd można zaimportować bez przepisywania.
   - Uzupełnia wbudowaną ochronę i nigdy nie może jej osłabić, a jego zgodność jest sprawdzana przed włączeniem.
5. **Zarządzanie wieloma instancjami.**
   - Rejestr obejmuje wszystkie instancje, a interfejs przełącza się między nimi.
   - Potrafi też całkowicie odinstalować instancję.
6. **Audyt bezpieczeństwa konfiguracji**: polecenie `audit security` ma charakter informacyjny, nigdy nie blokuje i zwraca kody wyjścia przydatne w skryptach.
7. **Zdalne źródła dzienników.**
   - Interfejs pobiera przez SSH dziennik innego serwera, na żądanie, bez zapisanego hasła.
   - Może go odczytać w lnav, scalony z dziennikami lokalnymi.
8. **Utwardzenie HTTP, którego nie da się wyłączyć**, aktywne od instalacji, niezależnie od profilu:
   - ścisła walidacja nagłówka Host;
   - odrzucanie niejednoznaczności Content-Length / Transfer-Encoding;
   - nagłówki bezpieczeństwa i CSP, także na stronach błędów;
   - bezpieczny odczyt X-Forwarded-For;
   - odmowa uruchomienia jako root.

---

## 8. Co inni robią lepiej

- **Przepustowość i opóźnienia**: nginx i lighttpd obsługują 10–20 razy więcej małych żądań, z 8–10 razy mniejszym opóźnieniem. Dla strony o dużym ruchu, publicznego API czy CDN to je należy wybrać.
- **Pamięć**: lighttpd (1 MB) i nginx (4–5 MB) nadają się na bardzo ograniczone maszyny (systemy wbudowane, podstawowe Raspberry Pi, małe kontenery).
- **Protokoły**: HTTP/2 we wszystkich pozostałych, HTTP/3 w nginx, Caddy i Traefik. omega-serv obsługuje tylko HTTP/1.1.
- **Automatyczny HTTPS**: Caddy i Traefik mają go domyślnie, a nginx (`ngx_http_acme_module`) i Apache (`mod_md`) przez oficjalny moduł. omega-serv deleguje to do Certbota, z kreatorem i zaplanowanym odnawianiem.
- **Środowiska kontenerowe**: automatyczne wykrywanie usług w Traefik (Docker, Kubernetes) nie ma odpowiednika w omega-serv.
- **Ekosystem**: nginx i Apache oferują tysiące modułów, poradników i integracji. Caddy oferuje system modułów w Go. omega-serv to młody projekt utrzymywany przez jedną osobę.
- **Kompresja w locie**: omega-serv serwuje tylko pliki już skompresowane.

---

## 9. Który serwer do jakiego zastosowania

| Potrzeba | Zalecany wybór |
|---|---|
| Strona o dużym ruchu, publiczne API, CDN, maksymalna przepustowość | **nginx** |
| Bardzo ograniczona maszyna, systemy wbudowane, pliki statyczne | **lighttpd** |
| Szybki start z automatycznym HTTPS, krótka konfiguracja | **Caddy** |
| Starsza aplikacja PHP, `.htaccess`, hosting współdzielony | **Apache** |
| Docker, Kubernetes, mikrousługi | **Traefik** |
| Mała strona, usługa wewnętrzna, laboratorium, VPN, administracja bez edytowania plików | **omega-serv** |
| Serwer wystawiony do sieci, którego bezpieczeństwo (WAF, blokady, przynęty) chce się widzieć i kontrolować z jednego interfejsu | **omega-serv** |
| Wewnętrzne reverse proxy z rozdzielaniem, kontrolą stanu i pamięcią podręczną, zarządzane z interfejsu | **omega-serv** |
| Nauka utwardzania HTTP i aktywnej obrony | **omega-serv** |

Te narzędzia można też łączyć. Na przykład:
- nginx lub Traefik na froncie od strony Internetu, a za nimi omega-serv dla usługi wewnętrznej, jej bezpieczeństwa i administracji;
- omega-serv jako wewnętrzne reverse proxy przed kilkoma serwerami aplikacji.

---

## 10. Powtórzenie pomiarów

Narzędzia są dostarczane w repozytorium, w `tools/bench/`. Potrzebne są zainstalowane nginx, lighttpd, Caddy i oha oraz środowisko programistyczne omega-serv (`.venv`).

```sh
# 1. przygotowanie folderu pomiarowego (pliki testowe, konfiguracje, omega-serv 1.0 i 2.0)
tools/bench/compare/setup.sh /sciezka/pomiar omega-serv-1.0.0.tar.gz

# 2. 12 konfiguracji, 3 przeplatane powtórzenia (około 22 minut)
tools/bench/compare/campaign.sh /sciezka/pomiar > wyniki.txt

# 3. mediany
python3 tools/bench/compare/summarize.py wyniki.txt

# duże pobrania (pamięć i responsywność), 2.0, a potem 1.0
.venv/bin/python tools/bench/bigfile.py
BENCH_SRC=/sciezka/pomiar/v1-archive/omega-serv/src \
BENCH_EXTRA_PATH=/sciezka/pomiar/v1-archive/omega-serv/vendor/omega-lib/src \
  .venv/bin/python tools/bench/bigfile.py

# pomiar dowolnego innego, już uruchomionego serwera, bez oha
python3 tools/bench/bench_any.py --make-files /srv/testowy-webroot
python3 tools/bench/bench_any.py --port 8080
```

Domyślnie serwer jest przypięty do wątków 0 i 2, a klient do wątków 1 i 3, co odpowiada maszynie pomiarowej. Dostosuj ten podział do swojego procesora (`lscpu -e` pokazuje topologię) za pomocą zmiennych `SRV_CPUS` i `CLI_CPUS`.

Publikując własne wyniki, podaj maszynę, wersje, podział procesorów i trzy powtórzenia.

---

## 11. Źródła

Funkcje pozostałych serwerów według ich oficjalnej dokumentacji (stan na 26 października 2026 r.).

**nginx**
- [Limit żądań `limit_req` (strefa pamięci współdzielonej)](https://nginx.org/en/docs/http/ngx_http_limit_req_module.html)
- [Wstępnie skompresowane pliki `gzip_static`](https://nginx.org/en/docs/http/ngx_http_gzip_static_module.html)
- [Oficjalny moduł ACME `ngx_http_acme_module`](https://nginx.org/en/docs/http/ngx_http_acme_module.html)
- [Rozdzielanie obciążenia (`upstream`)](https://nginx.org/en/docs/http/ngx_http_upstream_module.html)
- [HTTP/3](https://nginx.org/en/docs/http/ngx_http_v3_module.html)
- [Konektor ModSecurity dla nginx](https://github.com/owasp-modsecurity/ModSecurity-nginx)

**lighttpd**
- [`server.max-worker`: odradzane, liczniki na proces dla mod_status i mod_evasive](https://redmine.lighttpd.net/projects/lighttpd/wiki/Server_max-workerDetails)
- [mod_magnet (skrypty Lua)](https://redmine.lighttpd.net/projects/lighttpd/wiki/Docs_ModMagnet)
- [mod_deflate (kompresja, pamięć podręczna)](https://redmine.lighttpd.net/projects/lighttpd/wiki/Mod_deflate)
- [mod_proxy (rozdzielanie, kontrola pasywna, WebSocket)](https://redmine.lighttpd.net/projects/lighttpd/wiki/Docs_ModProxy)
- [mod_evasive (równoczesne połączenia na adres)](https://redmine.lighttpd.net/projects/lighttpd/wiki/Docs_ModEvasive)

**Caddy**
- [Automatyczny HTTPS](https://caddyserver.com/docs/automatic-https)
- [`file_server` i `precompressed`](https://caddyserver.com/docs/caddyfile/directives/file_server)
- [`reverse_proxy` (strategie, kontrola aktywna i pasywna)](https://caddyserver.com/docs/caddyfile/directives/reverse_proxy)
- [API administracyjne](https://caddyserver.com/docs/api)
- [Wtyczka limitu żądań caddy-ratelimit](https://github.com/mholt/caddy-ratelimit)
- [WAF Coraza dla Caddy](https://github.com/corazawaf/coraza-caddy)
- [caddy-docker-proxy](https://github.com/lucaslorentz/caddy-docker-proxy)

**Apache HTTP Server**
- [mod_md (ACME)](https://httpd.apache.org/docs/2.4/mod/mod_md.html)
- [mod_proxy_balancer](https://httpd.apache.org/docs/2.4/mod/mod_proxy_balancer.html)
- [mod_proxy_hcheck](https://httpd.apache.org/docs/2.4/mod/mod_proxy_hcheck.html)
- [mod_http2](https://httpd.apache.org/docs/2.4/mod/mod_http2.html)
- [mod_deflate, treści wstępnie skompresowane](https://httpd.apache.org/docs/2.4/mod/mod_deflate.html)
- [ModSecurity](https://github.com/owasp-modsecurity/ModSecurity)

**Traefik**
- [Middleware `ratelimit` (w pamięci na instancję, opcjonalnie Redis)](https://doc.traefik.io/traefik/reference/routing-configuration/http/middlewares/ratelimit/)
- [ACME](https://doc.traefik.io/traefik/https/acme/)
- [Providery (Docker, Kubernetes…)](https://doc.traefik.io/traefik/providers/overview/)

**Narzędzie pomiarowe**
- [oha](https://github.com/hatoo/oha)

---

*Porównanie przygotowane przez kraynux dla omega-serv 2.0.0: pomiary z 26 października 2026 r. Pomiary dotyczą jednej maszyny. Przy każdej decyzji dotyczącej wydajności wykonaj pomiary na własnym sprzęcie za pomocą dostarczonych narzędzi.*
