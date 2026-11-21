# omega-serv na tle serwerów WWW dostępnych na rynku — wersja graficzna

**omega-serv na tle nginx · lighttpd · Apache · Caddy · Traefik — pomiary na trzech maszynach (list. 2026).**

🌐 [Français](../../comparatif-server-web-graphique.md) · [English](../en/comparatif-server-web-graphique.md) · [Español](../es/comparatif-server-web-graphique.md) · [Português (Brasil)](../pt-BR/comparatif-server-web-graphique.md) · [Italiano](../it/comparatif-server-web-graphique.md) · [Deutsch](../de/comparatif-server-web-graphique.md) · [Nederlands](../nl/comparatif-server-web-graphique.md) · **Polski** · [Русский](../ru/comparatif-server-web-graphique.md) · [中文](../zh-CN/comparatif-server-web-graphique.md) · [Tiếng Việt](../vi/comparatif-server-web-graphique.md) · [ไทย](../th/comparatif-server-web-graphique.md) · [Bahasa Indonesia](../id/comparatif-server-web-graphique.md) · [日本語](../ja/comparatif-server-web-graphique.md) · [한국어](../ko/comparatif-server-web-graphique.md) · [हिन्दी](../hi/comparatif-server-web-graphique.md) · [العربية](../ar/comparatif-server-web-graphique.md)

> **Jak czytać:** im dłuższy słupek, tym szybszy serwer. Punkt odniesienia: **nginx = 1,00**.

## Legenda kolorów

<!-- 🖼️ IMAGE : legende-couleurs -->
<div align="center">
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/translation/pl/omega-serv/stats-1.png" alt="Légende des couleurs" width="1024">
</div>

---

## 📊 Pliki 1 KB — przepustowość (żądania/s)

Maszyny A (i5 2010), B (Celeron 2016) i C (Ryzen 2024). Słupki są znormalizowane względem nginx (1,00) na tej samej maszynie.

<!-- 🖼️ IMAGE : 1ko-banner — 3 colonnes côte à côte (Machine A · 2 cœurs | Machine B · 4 cœurs | Machine C · 10 cœurs), largeur totale -->
<div align="center">
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/translation/pl/omega-serv/stats-2.png" alt="Fichiers 1 Ko — machines A, B et C" width="1024">
</div>

> \* Maszyna C: silnik natywny używa 4 rdzeni, nginx 2 procesów (2 rdzenie). Przy równej liczbie rdzeni stosunek spada do ~0,70.
---

## 📦 Pliki średnie (100 KB) — normalny tryb WWW

Tu Apache zaskakuje: często wyprzedza silnik natywny omega-serv. lighttpd pozostaje najszybszy. Punkt odniesienia: nginx = 1,00.

<!-- 🖼️ IMAGE : 100ko-banner.png — 3 colonnes côte à côte (A | B | C), largeur totale -->
<div align="center">
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/translation/pl/omega-serv/stats-3.png" alt="Fichiers 100 Ko — machines A, B et C" width="1024">
</div>

---

## 💿 Duże pliki (5 MB) — normalny tryb WWW

Przy dużych plikach serwery się zrównują: dane kopiuje jądro (sendfile). Caddy jest wyjątkiem na maszynie C. Przepustowość w MB/s.

<!-- 🖼️ IMAGE : 5mo-banner.png — 3 colonnes côte à côte (A | B | C), largeur totale -->
<div align="center">
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/translation/pl/omega-serv/stats-4.png" alt="Fichiers 5Mo — machines A, B et C" width="1024">
</div>

---

## 🔄 Reverse proxy — małe odpowiedzi (1 KB)

Każdy proxy przekazuje żądania do backendu nginx. Punkt odniesienia: nginx = 1,00. Maszyna C: 4 procesy.

<!-- 🖼️ IMAGE : proxy-1ko-banner.png — 3 colonnes côte à côte (A | B | C), largeur totale -->
<div align="center">
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/translation/pl/omega-serv/stats-5.png" alt="Proxy 1 Ko — machines A, B et C" width="1024">
</div>

---

## 🔄 Reverse proxy — odpowiedzi 100 KB

Przy średnich odpowiedziach omega-serv natywny dorównuje nginx lub go przewyższa.

<!-- 🖼️ IMAGE : proxy-100ko-banner.png — 3 colonnes côte à côte (A | B | C), largeur totale -->
<div align="center">
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/translation/pl/omega-serv/stats-6.png" alt="Proxy 100 Ko — machines A, B et C" width="1024">
</div>

---

## 💾 Pamięć (PSS) — w spoczynku → po obciążeniu

Im krótszy słupek, tym bardziej oszczędny serwer. lighttpd, nginx i Apache są najskromniejsze; omega-serv 3.0.0 (zmierzony ponownie 19 listopada) jest następny, z 10–16 MB dla silnika natywnego.

<!-- 🖼️ IMAGE : memoire-banner.png — 3 colonnes côte à côte de jauges (A | B | C), largeur totale -->
<div align="center">
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/translation/pl/omega-serv/stats-7.png" alt="Mémoire — machines A, B et C" width="1024">
</div>

---

## 🏆 Ranking normalnego trybu WWW — kto jest najszybszy?

Podsumowanie trzech maszyn w serwowaniu plików statycznych.

<!-- 🖼️ IMAGE : classement-web.png -->
<!-- Contenu : 1. 🥇 lighttpd — meilleur en petits & moyens fichiers · 2. 🥈 nginx — référence, excellent partout · 3. 🥉 Apache — bon, robuste, écosystème · 4. omega-serv natif — très bon, 2ᵉ en reverse proxy · 5. Caddy — simple, HTTPS auto · 6. omega-serv Python — moteur de repli -->
<div align="center">
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/translation/pl/omega-serv/stats-8.png" alt="Classement web normal" width="1024">
</div>

---

## 🔄 Ranking reverse proxy — kto jest najlepszy?

nginx pozostaje punktem odniesienia; omega-serv natywny jest jego najbliższym następcą, daleko przed pozostałymi.

<!-- 🖼️ IMAGE : classement-proxy.png -->
<!-- Contenu : 1. 🥇 nginx · 2. 🥈 omega-serv natif — 0,82 à 0,91× nginx en 1 Ko · 3. 🥉 omega-serv + WAF — toujours devant lighttpd/Apache · 4. lighttpd — 0,53 à 0,61× · 5. Apache — 0,50 à 0,59× · 6. Traefik — 0,29 à 0,35× · 7. Caddy — 0,23 à 0,32× · 8. omega-serv Python — moteur de repli -->
<div align="center">
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/translation/pl/omega-serv/stats-9.png" alt="Classement reverse proxy" width="1024">
</div>

---

## 🆚 Starcie — rankingi WWW i reverse proxy obok siebie

Dwa zastosowania, dwa rankingi. Serwer może błyszczeć w jednym i rozczarowywać w drugim: Apache zaskakuje w przekazywaniu, Caddy rozczarowuje wszędzie poza prostotą.

<!-- 🖼️ IMAGE : face-a-face.png — 2 colonnes côte à côte (web | proxy), largeur totale -->
<div align="center">
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/translation/pl/omega-serv/stats-10.png" alt="Face à face web vs reverse proxy" width="1024">
</div>

### Synteza krzyżowa

| Serwer | Pozycjonowanie |
|---|---|
| 🟢 **omega-serv natywny** | Najbardziej wszechstronny: 4. w WWW, **2. w reverse proxy**. Jedyny serwer z wbudowanym WAF, który w przekazywaniu pozostaje przed lighttpd i Apache. Najlepszy kompromis dla jednego narzędzia obejmującego oba zastosowania, z bezpieczeństwem w dodatku. |
| 🔵 **nginx** | Najrówniejszy: 2. w WWW, **1. w reverse proxy**. Zawsze w czołówce rankingu, bez wyraźnej słabości. Domyślny wybór bez szczególnych wymagań. |
| 🟢 **lighttpd** | Sprinter plików statycznych: **1. w WWW**, ale 4. w przekazywaniu. Najlepszy wybór do czystej statyki, ustępuje miejsca omega-serv lub nginx, gdy tylko dochodzi reverse proxy. |
| 🔴 **Apache** | Kontrprzykład: 3. w WWW, 5. w przekazywaniu. Przy dużych plikach zaskakuje nawet nginx (maszyna C). Ani najszybszy, ani najlżejszy: jego atutem pozostaje ekosystem PHP. |
| 🟠 **Caddy** | Prostota przed szybkością: 5. w WWW, **7. w przekazywaniu**. Nie jest stworzony do przepustowości: automatyczny HTTPS i krótka konfiguracja. Do zarezerwowania dla małych projektów. |
| 🟣 **Traefik** | Poza kategorią WWW: nie jest serwerem plików, 6. w przekazywaniu. Jego terenem pozostają Docker i Kubernetes, a nie surowa wydajność. |

---

## 📋 Pełna tabela zbiorcza — stosunki do nginx (1,00)

Przegląd **wszystkich** metryk: normalny tryb WWW (1 KB, 100 KB, 5 MB) i reverse proxy (1 KB, 100 KB), plus pamięć. Im wartość bliższa 1,00 lub wyższa, tym lepiej.

| Serwer | WWW 1 KB (A/B/C) | WWW 100 KB (A/B/C) | WWW 5 MB (A/B/C) | Proxy 1 KB (A/B/C) | Proxy 100 KB (A/B/C) | Pamięć (A/B/C) |
|---|---|---|---|---|---|---|
| **lighttpd** | 1,52 / 1,26 / 1,53 | 1,08 / 1,07 / 1,26 | 1,05 / 0,99 / 0,81 | 0,61 / 0,56 / 0,53 | 0,74 / 0,62 / 0,96 | 1 MB |
| **nginx** | 1,00 / 1,00 / 1,00 | 1,00 / 1,00 / 1,00 | 1,00 / 1,00 / 1,00 | 1,00 / 1,00 / 1,00 | 1,00 / 1,00 / 1,00 | 4–5 MB |
| **omega-serv (natywny)** | **0,70 / 0,67 / 1,15\*** | **0,38 / 0,28 / 0,61** | **0,99 / 0,91 / 1,09** | **0,85 / 0,91 / 0,82** | **1,11 / 0,97 / 1,43** | 10–16 MB |
| **omega-serv + WAF** | 0,56 / 0,53 / 1,07\* | 0,37 / 0,27 / 0,62 | — | 0,81 / 0,89 / 0,77 | 1,10 / 0,93 / 1,30 | 28–33 MB |
| **Apache** | 0,42 / 0,35 / 0,76 | 0,55 / 0,62 / 0,97 | 1,01 / 1,00 / 1,19 | 0,59 / 0,53 / 0,50 | 0,62 / 0,65 / 0,71 | 4–9 MB |
| **Caddy** | 0,26 / 0,17 / 0,21 | 0,40 / 0,33 / 0,14 | 0,95 / 0,94 / 0,11 | 0,32 / 0,28 / 0,23 | 0,60 / 0,54 / 0,59 | 46–67 MB |
| **Traefik** | — | — | — | 0,35 / 0,35 / 0,29 | 0,64 / 0,60 / 0,70 | 93–131 MB |
| **omega-serv (Python)** | 0,11 / 0,05 / 0,08 | 0,14 / 0,10 / 0,12 | 0,92 / 0,91 / 0,75 | 0,09 / 0,08 / 0,07 | 0,21 / 0,19 / — | 20–48 MB |

> \* Maszyna C: 4 rdzenie dla silnika natywnego wobec 2 dla nginx; przy równej liczbie rdzeni stosunek ~0,67–0,71.
> Trzy wartości w komórce odpowiadają maszynom **A / B / C**. „—”: niemierzone lub nie dotyczy.

---

## ⚖️ Mocne i słabe strony — wszystkie serwery

Każdy serwer ma swoje atuty i ograniczenia. Oto pełny obraz, bez faworyzowania.

### 🟢 omega-serv (natywny)

**Mocne strony**
- ✅ Pełna administracja w terminalu (TUI, 17 języków)
- ✅ WAF + Active Defense + RIPOSTE wbudowane
- ✅ Silnik natywny C++: ~0,7× nginx w statyce
- ✅ 2. w reverse proxy za nginx
- ✅ Limity współdzielone między procesami (dokładne zabezpieczenia)
- ✅ Import skryptów lighttpd mod_magnet
- ✅ Zarządzanie wieloma instancjami
- ✅ Administracja przez WWW


**Słabe strony**
- ❌ Brak HTTP/2 i HTTP/3
- ❌ Brak kompresji w locie
- ❌ Brak wykrywania Docker/Kubernetes
- ❌ ACME przez Certbot (niewbudowane natywnie)
- ❌ Pliki 100 KB: 0,3–0,6× nginx
- ❌ Pamięć 10–55 MB zależnie od trybu (wobec 1–5 MB nginx/lighttpd)
- ❌ Młody ekosystem, utrzymywany przez jedną osobę

---

### 🔵 nginx

**Mocne strony**
- ✅ Punkt odniesienia pod względem wydajności i stabilności
- ✅ HTTP/2, HTTP/3, kompresja
- ✅ Ogromny ekosystem (moduły, dokumentacja, społeczność)
- ✅ Bardzo oszczędny w pamięci (4–5 MB)
- ✅ Doskonały reverse proxy
- ✅ Oficjalny moduł ACME
- ✅ Dojrzała, sprawdzona konfiguracja

**Słabe strony**
- ❌ Rozwlekła konfiguracja, własna składnia do nauczenia
- ❌ Brak wbudowanego WAF (wymaga ModSecurity lub odpowiednika)
- ❌ Brak natywnego interfejsu administracyjnego
- ❌ Przeładowanie konfiguracji bywa kłopotliwe w produkcji
- ❌ Wersja open source ograniczona (niektóre funkcje w płatnym Nginx Plus)
- ❌ Brak natywnego wykrywania Docker/Kubernetes (przez szablony)

---

### 🟢 lighttpd

**Mocne strony**
- ✅ Najszybszy przy małych i średnich plikach
- ✅ Najbardziej oszczędny w pamięci (1 MB)
- ✅ Lekki, dostosowany do systemów o ograniczonych zasobach
- ✅ Dobry reverse proxy
- ✅ Prosta i czytelna konfiguracja

**Słabe strony**
- ❌ Brak HTTP/3 (HTTP/2 częściowo, zależnie od kompilacji)
- ❌ Tylko 4. w reverse proxy (0,53–0,61× nginx)
- ❌ Ekosystem mniejszy niż nginx/Apache
- ❌ Brak wbudowanego WAF
- ❌ Brak wykrywania Docker/Kubernetes
- ❌ Rozwój mniej aktywny niż dawniej
- ❌ Słaby przy dużych plikach (0,81× nginx na maszynie C)

---

### 🔴 Apache

**Mocne strony**
- ✅ Ogromny historyczny ekosystem (moduły, `.htaccess`, PHP)
- ✅ Solidny i sprawdzony od dziesięcioleci
- ✅ Doskonały przy dużych plikach (wyprzedza nginx na maszynie C)
- ✅ Obsługa `.htaccess` bez restartu
- ✅ Dostępne: kompresja, HTTP/2, ACME
- ✅ Obfita dokumentacja

**Słabe strony**
- ❌ Wolny przy małych plikach (0,35–0,42× nginx)
- ❌ Żarłoczny w pamięci w trybie prefork (4–9 MB, szybko rośnie pod obciążeniem)
- ❌ Model procesów mniej wydajny niż event-driven
- ❌ Rozwlekła konfiguracja
- ❌ 5. w reverse proxy (0,50–0,59× nginx)
- ❌ Brak wbudowanego WAF (ModSecurity jako osobny moduł)
- ❌ Historycznie większa powierzchnia ataku

---

### 🟠 Caddy

**Mocne strony**
- ✅ Automatyczny HTTPS (wbudowany ACME, zero konfiguracji)
- ✅ Bardzo krótka i czytelna konfiguracja (Caddyfile)
- ✅ Natywne HTTP/2 i HTTP/3
- ✅ Jeden plik binarny, proste wdrożenie
- ✅ Poprawny reverse proxy przy średnich odpowiedziach

**Słabe strony**
- ❌ Wolny w surowej przepustowości (5. w WWW, 7. w przekazywaniu)
- ❌ Wysokie zużycie pamięci (46–67 MB)
- ❌ Bardzo słaby przy dużych plikach na maszynie C (0,11× nginx)
- ❌ Brak wbudowanego WAF
- ❌ Młodszy ekosystem niż nginx/Apache
- ❌ Mało przystosowany do bardzo wysokich przepustowości

---

### 🟣 Traefik

**Mocne strony**
- ✅ Automatyczne wykrywanie Docker/Kubernetes
- ✅ Idealny w środowisku kontenerowym
- ✅ Automatyczny HTTPS (wbudowany ACME)
- ✅ Dynamiczna konfiguracja bez restartu
- ✅ Dobry jako reverse proxy przy średnich odpowiedziach (0,60–0,70× nginx)

**Słabe strony**
- ❌ Nie jest serwerem plików (brak w rankingu WWW)
- ❌ 6. w reverse proxy (0,29–0,35× nginx przy 1 KB)
- ❌ Bardzo wysokie zużycie pamięci (93–131 MB)
- ❌ Złożona konfiguracja poza kontekstem kontenerów
- ❌ Brak wbudowanego WAF
- ❌ Przewymiarowany do zwykłej strony statycznej

---

## 🎯 Jaki serwer do jakiego zastosowania?

| Zastosowanie | Zalecany serwer | Powód |
|---|---|---|
| Strona o dużym ruchu | **nginx** lub **lighttpd** | Maksymalna przepustowość, HTTP/2-3 |
| Maszyna o ograniczonych zasobach / systemy wbudowane | **lighttpd** | 1 MB pamięci, najszybszy i najmniej wymagający |
| Prosty automatyczny HTTPS | **Caddy** | Automatyczne certyfikaty, krótka konfiguracja |
| Docker / Kubernetes | **Traefik** | Wykrywanie usług |
| Aplikacja PHP / .htaccess | **Apache** | Historyczny ekosystem |
| Reverse proxy | **nginx** lub **omega-serv (natywny)** | Najlepsza wydajność |
| Strony WWW + bezpieczeństwo + interfejs | **omega-serv (natywny)** | Kompletna infrastruktura: WAF, administracja przez WWW, wiele instancji, reverse proxy, menedżer logów, kopie zapasowe… |

---

Dane pochodzą z porównania omega-serv (listopad 2026) — kraynux. Licencja MIT.
[oha](https://github.com/hatoo/oha) do pomiarów · samodzielne wykresy HTML/CSS.

> *Wersja graficzna zmierzonego porównania omega-serv (te same liczby co w porównaniu szczegółowym: pomiary z 3 i 4 listopada 2026 na trzech maszynach; reverse proxy: 14 listopada 2026; pamięć omega-serv 3.0.0: 19 listopada 2026). Przy każdej decyzji o wydajności zmierz na własnym sprzęcie.*
>
> Copyright © 2026 kraynux — kraynux@proton.me — Licencja MIT (zob. plik LICENSE).
