<!-- Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE) -->
<div align="center">
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/assets/omega-serv.png" alt="Omega-Serv" width="384">
</div>

# 🔒 OMEGA-SERV

**Samodzielny, przenośny i domyślnie utwardzony serwer WWW HTTP**

> Stworzony przez **kraynux** dla **Omega-server** 
[kraynux.snake-mackarel](https://kraynux.snake-mackarel.ts.net)

Oficjalna strona: [OMEGA-SERV](https://kraynux.snake-mackarel.ts.net/omega-serv/translation/pl/) &nbsp; Dokumentacja, użycie, Pomoc i FAQ: [Pełny przewodnik](https://kraynux.snake-mackarel.ts.net/omega-serv/translation/pl/guide.html)  
Podgląd: [Zrzuty ekranu](https://kraynux.snake-mackarel.ts.net/omega-serv/screenshots/) &nbsp; Demonstracja [Serwer demo](https://craftdark.snake-mackarel.ts.net) &nbsp; [Porównanie/testy serwerów WWW](comparatif-serveurs-web.md)  

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](../../../LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![Lua](https://img.shields.io/badge/Lua-5.4%2B-2C2D72.svg)](https://www.lua.org/)
[![JavaScript](https://img.shields.io/badge/JavaScript-ES2020%2B-F7DF1E.svg)](https://developer.mozilla.org/docs/Web/JavaScript)
[![Platform](https://img.shields.io/badge/Platform-Linux-informational.svg)](https://www.linux.org/)
[![Interface](https://img.shields.io/badge/Interface-CLI%20%2B%20TUI-cyan.svg)](#3-użycie)
[![Textual](https://img.shields.io/badge/Textual-TUI-5A5AFB.svg)](https://textual.textualize.io/)

🌐 Dokumentacja, eksporty i interfejs dostępne w **17 językach** — zobacz [Języki interfejsu](#języki-interfejsu).  
**Języki:**
<img src="https://flagcdn.com/w20/fr.png" alt="France" style="height:14px;"> [Français](../../../README.md) · <img src="https://flagcdn.com/w20/gb.png" alt="English" style="height:14px;"> [English](../en/README.md) · <img src="https://flagcdn.com/w20/es.png" alt="Español" style="height:14px;"> [Español](../es/README.md) · <img src="https://flagcdn.com/w20/br.png" alt="Português (Brasil)" style="height:14px;"> [Português (Brasil)](../pt-BR/README.md) · <img src="https://flagcdn.com/w20/it.png" alt="Italiano" style="height:14px;"> [Italiano](../it/README.md) · <img src="https://flagcdn.com/w20/de.png" alt="Deutsch" style="height:14px;"> [Deutsch](../de/README.md) · <img src="https://flagcdn.com/w20/nl.png" alt="Nederlands" style="height:14px;"> [Nederlands](../nl/README.md) · <img src="https://flagcdn.com/w20/pl.png" alt="Polski" style="height:14px;"> [Polski](README.md) · <img src="https://flagcdn.com/w20/ru.png" alt="Русский" style="height:14px;"> [Русский](../ru/README.md) · <img src="https://flagcdn.com/w20/cn.png" alt="中文" style="height:14px;"> [中文](../zh-CN/README.md) · <img src="https://flagcdn.com/w20/vn.png" alt="Tiếng Việt" style="height:14px;"> [Tiếng Việt](../vi/README.md) · <img src="https://flagcdn.com/w20/th.png" alt="ไทย" style="height:14px;"> [ไทย](../th/README.md) · <img src="https://flagcdn.com/w20/id.png" alt="Bahasa Indonesia" style="height:14px;"> [Bahasa Indonesia](../id/README.md) · <img src="https://flagcdn.com/w20/jp.png" alt="日本語" style="height:14px;"> [日本語](../ja/README.md) · <img src="https://flagcdn.com/w20/kr.png" alt="한국어" style="height:14px;"> [한국어](../ko/README.md) · <img src="https://flagcdn.com/w20/in.png" alt="हिन्दी" style="height:14px;"> [हिन्दी](../hi/README.md) · <img src="https://flagcdn.com/w20/ae.png" alt="العربية" style="height:14px;"> [العربية](../ar/README.md)

---

**OMEGA-SERV** to serwer HTTP/1.1 napisany w czystym Pythonie (rdzeń serwera korzysta wyłącznie z biblioteki standardowej), przeznaczony do serwowania treści statycznych i opcjonalnie PHP-FPM, z utwardzeniem protokołu, którego nie da się wyłączyć, oraz modułami bezpieczeństwa (WAF, TLS, uwierzytelnianie), które można nakładać zamiast mieć je narzucone. Siódme narzędzie pakietu `omega-`, ale celowo **poza przyszłą integracją `omega-suite`** (działa na lokalnej maszynie, która go hostuje, a nie na zdalnych celach — ta sama rodzina co `omega-fire`); zbudowany zgodnie z Clean Architecture, gdzie `bootstrap/` pełni rolę korzenia kompozycji.

## 1. Wizja i zakres

Deklarowanym priorytetem jest **przede wszystkim solidność/bezpieczeństwo rdzenia HTTP** — WAF i TLS to moduły opcjonalne nakładane na wierzch, nigdy wymagania wstępne. Serwer, który robi tylko jedno (serwuje pliki, ewentualnie PHP), ale robi to dobrze, z prawdziwym, nieomijalnym utwardzeniem protokołu — zamiast serwera, który robi wiele rzeczy po łebkach.

### Co robi OMEGA-SERV

- Serwuje treści statyczne (pliki, opcjonalna lista katalogu, aliasy, przekierowania, przepisywanie adresów, cache) z bezpiecznym rozwiązywaniem ścieżek (traversal, podwójne kodowanie, dowiązania symboliczne). Duże pliki są wysyłane blokami prosto z dysku, nigdy nie są ładowane do pamięci; każdy plik ma `ETag` i `Last-Modified` (ponowne załadowanie = pusta odpowiedź 304) i przyjmuje żądania częściowe `Range` (wznawianie pobierania, wideo); obrazy, multimedia, czcionki, CSS i JS dostają domyślny `Cache-Control`, zmieniany na ekranie Cache. Wstępnie skompresowane pliki tekstowe: jeśli obok `site.css` istnieje `site.css.br` lub `site.css.gz` (utworzone poleceniem `brotli -k site.css` lub `gzip -k site.css`), a przeglądarka je akceptuje, są wysyłane zamiast niego — nigdy wersja starsza niż oryginał.
- Domyślnie utwardza protokół HTTP, bez opcji wyłączenia: jawnie dozwolone metody, walidacja nagłówka `Host`, odrzucanie niejednoznaczności `Content-Length`/`Transfer-Encoding`, nieomijalne nagłówki bezpieczeństwa i bazowa CSP.
- Opcjonalnie: filtrowanie WAF (sygnatury, ograniczanie szybkości, lista blokad), bezpośredni TLS (certyfikat samopodpisany, podpisany przez lokalny CA lub publiczny przez Let's Encrypt/Certbot z automatycznym odnawianiem — zobacz §9), uwierzytelnianie HTTP Basic dla stref, PHP przez FastCGI/PHP-FPM, odizolowane strefy uploadu.
- Tryb « boost »: kilka procesów serwera, najwyżej jeden na każdy dostępny procesor maszyny (ekran Odporność i limity); liczniki bezpieczeństwa (limit żądań, recydywa) są między nimi współdzielone i pozostają dokładne.
- Audytuje własną konfigurację (`audit security`) i instaluje się jako usługa systemowa (systemd/OpenRC/runit).
- W pełni skryptowalne, nieinteraktywne CLI **oraz interaktywny interfejs (Textual)**, który obejmuje dokładnie te same przypadki użycia — zobacz §3. Plan rozwoju interfejsu (`OMEGA-SERV_PLAN-DETAILLE_INTERFACE.md`, §12) **w całości zrealizowany**: rejestr możliwości, profile/opcje, szczegółowa konfiguracja (aliasy/przekierowania/przepisywanie/FastCGI/lista katalogu/uwierzytelnianie/cache/WAF/zaufane proxy/wychodzący reverse proxy/TLS), zarządzanie logami (Biblioteka/Ulubione, 3 przeglądarki — prosta/klasyczna/scalony lnav —, podgląd i obsługa IP, zdalne źródła SSH, rotacja/kopia/automatyzacja/przywracanie/czyszczenie/eksport), usługa systemowa, multi-instancja (rejestr, tworzenie), sprawdzanie/symulacja/audyt, kopia zapasowa/przywracanie konfiguracji, kreator pierwszego uruchomienia, ustawienia aplikacji (motyw, profil renderowania, ścieżki eksportów/zrzutów), kontekstowy przewodnik pomocy (karta dla każdego ekranu z konkretnymi przykładami, FAQ, eksport HTML, pełne pokrycie weryfikowane testem), systematyczna informacja o przeładowaniu/restarcie po każdym zapisie, pełna konfiguracja Active Defense bez ręcznej edycji plików.

### Czego OMEGA-SERV nie robi

- Surowe CGI (usunięte z zakresu V1 — obsługiwane jest tylko FastCGI/PHP-FPM).
- Wzajemne uwierzytelnianie TLS (mTLS), OCSP stapling — poza zakresem V1, zobacz §15. (ACME/Let's Encrypt przez Certbot jest dostępne, zobacz §9c/9d.)
- Cache HTTP współdzielony między procesami.
- Skanowanie/audyt zdalnego celu (do tego służą `omega-check`/`omega-scan`/`omega-deep` — Omega-serv audytuje siebie, nigdy nikogo innego).

### OMEGA-SERV na tle serwerów WWW dostępnych na rynku

Zobacz [Pomiary i porównanie](comparatif-serveurs-web.md)  
Zmierzone porównanie: [Nginx](https://nginx.org/) · [Lighttpd](https://www.lighttpd.net/) · [Caddy](https://caddyserver.com/) · [Apache](https://www.apache.org) · [Traefik](https://traefik.io/) · [Omega-Serv](https://kraynux.snake-mackarel.ts.net/omega-serv/translation/pl/)

### Ostrzeżenie o użyciu

Omega-serv **odmawia uruchomienia jako root**. Żaden moduł bezpieczeństwa (WAF, TLS, uwierzytelnianie) nie jest domyślnie włączony w żadnym dostarczonym profilu, łącznie z `hardened` — ich włączenie to zawsze jawne działanie (`config enable-tls`, `option enable waf`...). Sam profil `hardened` zaleca reverse proxy przy prawdziwej ekspozycji w Internecie, zamiast go zastępować.

## 2. Instalacja

### Wymagania

- Python 3.10+
- `openssl` (program, nie biblioteka Pythona) do wszystkiego, co dotyczy certyfikatów TLS — pozostałe funkcje działają bez niego.

### Pobieranie

Archiwum najnowszej wersji i sumy kontrolne SHA-256 każdej wersji: [omega-serv-2.0.0.tar.gz](https://kraynux.snake-mackarel.ts.net/omega-serv/download/omega-serv-2.0.0.tar.gz) · [sha.txt](https://kraynux.snake-mackarel.ts.net/omega-serv/download/sha.txt)

```bash
wget https://kraynux.snake-mackarel.ts.net/omega-serv/download/omega-serv-2.0.0.tar.gz
wget https://kraynux.snake-mackarel.ts.net/omega-serv/download/sha.txt
sha256sum -c --ignore-missing sha.txt
```

### Instalacja

> ⚠️ **Aktualizujesz istniejącą instalację?** Poniższe polecenie **po cichu pomija rozpakowanie**, jeśli `omega-serv/` już istnieje (zakłada, że to przerwana pierwsza instalacja, a nie aktualizacja) — przeinstalowałbyś wtedy zależności na **starym, niezmienionym kodzie**, bez najmniejszego komunikatu o błędzie. Zamiast tego użyj sekcji [Aktualizacja](#aktualizacja) poniżej.

```bash
[ -d omega-serv ] && echo "ℹ️ Już tu rozpakowane, krok pominięty." || tar -xzf omega-serv-2.0.0.tar.gz
cd omega-serv/
chmod +x install.sh
./install.sh
```

`install.sh`:

1. Tworzy środowisko wirtualne `.venv`, jeśli jeszcze nie istnieje.
2. Instaluje pakiet (`pip install -e .`) — **żadnej zewnętrznej zależności** (zobacz §6).
3. Nadaje plikom `omega-serv.sh` i `install.sh` prawo wykonywania.
4. Dodaje alias `serv` do `~/.bashrc` i `~/.zshrc` (bez duplikatu, jeśli już istnieje).

### Aktualizacja

Jeśli `omega-serv/` już istnieje (poprzednia instalacja), **nigdy nie uruchamiaj `tar` z wnętrza tego katalogu**: próbowałby utworzyć zagnieżdżony `omega-serv/omega-serv/` i zakończyłby się błędem. W przeciwieństwie do omega-fire `install.sh` nigdy nie zmienia uprawnień katalogu (żaden krok nie wymaga tam `sudo`) — nie ma więc tu ryzyka katalogu należącego do `root`; rozpakowanie bezpośrednio na istniejącą instalację jest bezpieczne.

```bash
# Z katalogu NADRZĘDNEGO względem omega-serv/ (nigdy z wnętrza)
tar -xzf omega-serv-2.0.0.tar.gz
cd omega-serv/
./install.sh
```

Archiwum celowo pomija cały żywy stan (`var/db/`, `var/log/`, `var/backups/`, `secure/secrets/`, `secure/certificates/*.key`, `config/omega-serve.json`, **`webroot/` — faktycznie serwowaną stronę**...) — rozpakowanie na wierzch nigdy nie rusza obecnych danych, certyfikatów, ustawień ani serwowanych treści; zastępowany jest tylko kod aplikacji. `install.sh` ponownie wykorzystuje istniejące `.venv` i po prostu przeinstalowuje na nim zależności.

Od 2026-10-18 `var/` i `secure/auth/` w ogóle nie są już częścią archiwum, nawet puste: rozpakowanie na wierzch nie resetuje więc już ich uprawnień (współdzielonych z kontem usługi systemd) — po aktualizacji nie trzeba już « Usługa → Zastosuj ponownie uprawnienia ». `install.sh` tworzy te katalogi, jeśli ich brakuje, nigdy nie ruszając istniejących.

> ⚠️ **Jeśli usługa już działa, powyższy krok nie wystarczy.** Zastępuje kod na dysku, ale już działający proces nadal pracuje ze starym kodem załadowanym do pamięci — potem zawsze potrzebny jest **pełny restart**:
> ```bash
> sudo systemctl restart <nazwa-usługi>
> ```
> **Nigdy zwykłe przeładowanie** (`systemctl reload` ani ekran USŁUGA → *Przeładuj*): ono odczytuje ponownie tylko niektóre opcje konfiguracji (reguły WAF, strefy uwierzytelniania...), **nigdy samego kodu Pythona**. `systemctl status <nazwa-usługi>` pokazujący datę uruchomienia wcześniejszą niż twoja aktualizacja potwierdza, że wciąż działa na starym kodzie. Jeśli zawsze aktualizujesz, nadpisując ten sam katalog (standardowy przypadek powyżej), ten restart jest jedynym brakującym krokiem — ponowna instalacja usługi nie jest potrzebna.

> ⚠️ **Jeśli usługa potem wpada w pętlę restartów** (`systemctl status` przełącza się między active/inactive, `journalctl -u <nazwa-usługi>` pokazuje `PermissionError` przy zapisie pliku w `var/`): rozpakowanie przez `tar` przywraca uprawnienia katalogów zapisane w archiwum, co może usunąć współdzielenie uprawnień ustawione dla dedykowanego konta systemowego podczas pierwszej instalacji — nawet jeśli sam `install.sh` nigdy go nie rusza. Nie trzeba reinstalować unitu: ekran USŁUGA → **Napraw uprawnienia** (ponownie stosuje współdzielenie na `var/` i `secure/auth/`, nie ruszając unitu systemd).

### Zależności

Rdzeń serwera (parser HTTP/1.1, klient FastCGI, haszowanie haseł przez `hashlib.scrypt`) pozostaje czystym Pythonem/stdlib, a wszystko, co dotyczy certyfikatów TLS, przechodzi przez program `openssl` jako podproces zamiast przez bibliotekę kryptograficzną Pythona — **żadnej zewnętrznej zależności w tym celu**. Wprowadza je tylko interaktywny interfejs (§3): `omega-lib` (motywy, wykrywanie terminala — wspólna biblioteka pakietu, nieopublikowana na PyPI, dołączona do archiwum dystrybucyjnego), `textual` i `pyte` (emulacja terminala do scalonego renderowania `lnav` w interfejsie), `jinja2` (eksporty HTML z motywem) i `psutil` (ekran Stan i zasoby — CPU/RAM/dysk/sieć). Opcjonalna zależność deweloperska/testowa (`pip install -e ".[test]"`): `hypothesis` (testy właściwości parsera HTTP i resolwera ścieżek, nigdy w produkcji). Narzędzia jakości (`pip install -e ".[dev]"`): `pytest`, `ruff`, `mypy`, `import-linter`. Dodatkowy opcjonalny pakiet (`pip install -e ".[magnet]"`): `lupa` (osadzone wiązanie Lua, prekompilowany wheel, bez systemowego interpretera `lua`), wyłącznie dla uzupełniającego skryptu WAF « magnet » (§7) — nigdy domyślnie instalowany; jego brak jest zgłaszany (możliwość `waf-magnet`, ekran **Możliwości**) z dokładnym poleceniem instalacji, bez blokowania reszty serwera.

### Zalecane narzędzia opcjonalne

Interfejs działa w trybie ograniczonym, jeśli tych narzędzi brakuje:

- `openssl` — potrzebny do wszystkiego, co dotyczy certyfikatów TLS (samopodpisany, lokalny CA, import); bez niego polecenia `certs *` kończą się błędem, ale reszta serwera działa normalnie (zobacz §9).
- `certbot` — potrzebny tylko dla kreatora **Let's Encrypt** i jego automatycznego odnawiania (§9c/9d); samopodpisany TLS/lokalny CA go nie wymagają.
- `lnav` — zaawansowana, scalona analiza logów w ekranie **Zarządzanie logami** (§3); jasny, jednoznaczny komunikat o błędzie, jeśli program nie zostanie znaleziony, żadnej awarii; reszta ekranu (podgląd/śledzenie/rotacja/statystyki) działa bez niego normalnie.
- `scp` (pakiet `openssh`/`openssh-clients`, prawie zawsze już obecny) — potrzebny tylko dla **Zdalnych źródeł (SSH)** (§13a); bez niego pobieranie kończy się jasnym komunikatem, reszta Biblioteki działa normalnie.
- `python-psutil` (pakiet systemowy odpowiadający `psutil` z PyPI) — w każdym przypadku instalowany automatycznie przez `pip install -e .` (obowiązkowa zależność pakietu, ekran **Stan i zasoby** zawsze go potrzebuje), ale wcześniejsza instalacja przez menedżer pakietów oszczędza `pip` lokalnej kompilacji wheela.

```bash
# Arch Linux i pochodne
sudo pacman -S openssl certbot lnav python-psutil openssh

# Debian/Ubuntu i pochodne
sudo apt install openssl certbot lnav python3-psutil openssh-client

# Fedora
sudo dnf install openssl certbot lnav python3-psutil openssh-clients
```

## 3. Użycie

Dwa funkcjonalnie ściśle równoważne interfejsy, nigdy zduplikowana logika między nimi: nieinteraktywne CLI (skryptowalne, używane poniżej) i interaktywny interfejs Textual (menu, formularze, tabele) — każda akcja jednego istnieje po stronie CLI, interfejs jedynie obejmuje te same przypadki użycia.

### Tryb interaktywny (TUI)

Zalecany do codziennego użytku — uruchamiany bez argumentu:

```bash
./omega-serv.sh
```
jeśli utworzyłeś alias, po prostu wpisz `serv` w terminalu:
```bash
serv
```

### Języki interfejsu

17 języków: francuski, angielski, hiszpański, portugalski (Brazylia), włoski, niemiecki, niderlandzki, polski, rosyjski, chiński, wietnamski, tajski, indonezyjski, japoński, koreański, hindi, arabski. Wybór w Ustawieniach (klawisz `o`, « Langue / Language », etykieta nigdy nie jest tłumaczona) lub jednorazowo przez `OMEGA_SERV_LANG=en serv`. W tekstowej konsoli Linuksa (TTY) języki, których pismo nie istnieje w czcionkach konsoli (wietnamski, chiński, tajski, japoński, koreański, hindi, arabski), są na czas sesji wyświetlane po angielsku. W hindi terminale, które same składają połączone litery (Kitty, Ghostty, Konsole), przesuwają ramki i kolumny, różnie w zależności od czcionki: przy uruchomieniu pojawia się ostrzeżenie; Terminator, GNOME Terminal, Xfce Terminal i Alacritty wyświetlają hindi wyrównane. Dwa osobne ustawienia: **język stron dla odwiedzających** (strony błędów, lista katalogu — ekran Strony błędów, domyślnie francuski) i **język eksportów** (HTML i raport incydentu — Ustawienia, domyślnie « Jak interfejs »). Logi serwera (`journalctl`) pozostają po francusku.

### Ogólny przebieg

Ekran startowy (splash, zamyka się klawiszem lub kliknięciem) → menu główne (Kreator pierwszego uruchomienia / Rejestr możliwości / Profile / Szczegółowa konfiguracja / Aktywne zabezpieczenia / Zarządzanie logami / Usługa / Multi-instancja / Stan i zasoby / Audyt / Kopia zapasowa) → wybór sekcji, a potem akcji, przy czym każdy formularz waliduje wymagane pola przed przejściem dalej → jawne potwierdzenie przed każdą wrażliwą lub destrukcyjną operacją (restart, usunięcie, przywrócenie...) → systematyczna informacja o dalszym kroku (automatyczne przeładowanie w locie lub potwierdzenie pełnego restartu) po każdym zapisie, który zmienia już serwowaną konfigurację. Dopasowanie do terminala (kolory, rozmiar, strukturalne obniżanie profilu renderowania) jest automatyczne i nie wymaga ręcznej flagi — zobacz §4.

#### Skróty klawiszowe (interfejs interaktywny)

| Klawisz | Akcja |
|---|---|
| `↑` / `↓` | Poruszanie się między elementami ekranu |
| `Tab` / `Shift+Tab` | Poruszanie się między polami formularza |
| `Esc` | Powrót do poprzedniego ekranu (potwierdzenie wyjścia na ekranie startowym) |
| `t` | Następny motyw (stosowany od razu, bez potwierdzenia) |
| `r` | Odświeżenie wykrywania terminala |
| `F1` | Pomoc do aktywnego ekranu (karta kontekstowa — zobacz "Przewodnik pomocy" poniżej) |
| `a` | Pełny przewodnik pomocy (nawigowalne menu + FAQ) |
| `o` | Ustawienia aplikacji (motyw, profil renderowania, ścieżki eksportów/zrzutów — zobacz poniżej) |
| `q` | Wyjście (z potwierdzeniem) |
| `Ctrl+P` | Paleta poleceń (Motyw, Zrzut ekranu, Opcje...) |

> **Wyjątek — edytor list (WAF → Custom)**: żadnych skrótów, wszystko robi się myszą; klawiatura służy tylko do wpisywania (znaki, Enter, strzałki, Home/End, Page Up/Down, Backspace, Delete). `Esc`, `F1` i `Ctrl+P` są tam nieaktywne (przycisk **Pomoc**); aktywny pozostaje tylko `Ctrl+Q`, z potwierdzeniem przy niezapisanych zmianach.

#### Przewodnik pomocy (klawisze `F1`/`a`)

Wbudowany system pomocy, nigdy zwykły statyczny tekst: każdy udokumentowany ekran (karta z definicją/polami do wypełnienia z konkretnymi przykładami/wywoływaną akcją/reakcją — przeładowanie, restart lub brak) jest dostępny bezpośrednio z niego przez `F1`; klawisz `a` otwiera pełne menu (drzewo identyczne z rzeczywistą nawigacją aplikacji) z dostępem do FAQ (pułapki napotkane w rzeczywistym użyciu, np. klasy ataków Active Defense, uprawnienia przy współdzielonej usłudze) i samodzielnym eksportem HTML (zachowany aktywny motyw) całego przewodnika. Ogólny ekran referencyjny jako rozwiązanie zastępcze, dopóki nie istnieje konkretna karta — pokrycie jest obecnie pełne i weryfikowane testem.

#### Menu główne (interfejs interaktywny)

- **Kreator pierwszego uruchomienia** — prowadzony proces w 8 krokach (powitanie → możliwości tylko do odczytu → wybór profilu → bind/port → opcjonalny TLS → sprawdzenie → podsumowanie + zapis → propozycja instalacji usługi); pozwala wygenerować pełną konfigurację i uruchomić serwer bez znajomości CLI.
- **Rejestr możliwości** — systemowa sonda tylko do odczytu (system init, czy skonfigurowany port jest już zajęty, obecność `openssl`/`logrotate`/`tailscale`/`lnav`, miejsce na dysku, limit deskryptorów...), eksport JSON/HTML.
- **Profile** — ten sam przypadek użycia co `profile` w CLI (§5), diff zawsze wyświetlany przed zapisem.
- **Szczegółowa konfiguracja serwera** — pełny CRUD dla aliasów/przekierowań/przepisywania/listy katalogu/zaufanych proxy/wychodzącego reverse proxy/FastCGI/cache/uwierzytelniania/kontroli dostępu/stron błędów, plus podmenu **TLS** (stan, generowanie samopodpisanego, kreator lokalnego CA, kreator Let's Encrypt/Certbot, automatyczne odnawianie, unieważnianie, włączanie/wyłączanie — zobacz §9); druga ramka **OPCJE I SPRAWDZANIE** grupuje tam skróty do **Opcji** (`option` CLI, §7) i **Sprawdź konfigurację** (`config check` CLI, §10) — ten sam przebieg co dostosowanie ustawień, a potem sprawdzenie; tych dwóch ekranów nie da się już otworzyć bezpośrednio z menu głównego. WAF już tu nie mieszka (zobacz "Aktywne zabezpieczenia" poniżej): pokazuje głównie stan operacyjny, który stale się zmienia, a nie prosty statyczny formularz konfiguracji. Każdy zapis systematycznie wskazuje dalszy krok: automatyczne i ciche przeładowanie w locie, jeśli usługa jest aktywna (lista katalogu, dostęp, aliasy/przekierowania/przepisywanie, cache, strony błędów, zaufane proxy, strefy reverse proxy/FastCGI, użytkownicy/strefy uwierzytelniania), lub jawne potwierdzenie pełnego restartu, gdy zmiana dotyczy gniazda nasłuchu, TLS lub Active Defense — żaden ekran nie każe już zgadywać, czy trzeba zrestartować serwer.
- **Aktywne zabezpieczenia** — jeden ekran z dwoma blokami obok siebie: **Active Defense** (Stan, Śledzone zagrożenia z wynikiem/poziomem, Incydenty z chronologią/eksportem IoC/raportem, przydziały Deception, Symulacja decyzji w trybie dry-run, **Ustawienia** — pełna konfiguracja bez ręcznej edycji `config/omega-serve.json`, zobacz §11) i **WAF** (Stan, Moduły — tryb/pakiety reguł/lista blokad, Testowanie żądania, Custom — tworzenie własnych reguł i ładowanie list ścieżek/słów kluczowych edytowalnych myszą (zobacz §11b), Magnet — import zewnętrznego skryptu `mod_magnet` ze sprawdzeniem zgodności przed aktywacją) — zobacz §11.
- **Zarządzanie logami** — menu w dwóch kolumnach. Kolumna **Biblioteka**: centralny hub odwołujący się do każdego logu do obsłużenia (ręczne uzupełnianie, jedno kliknięcie automatycznie dodaje logi własne instancji — access/error/natywny WAF, + skrypt magnet §7, jeśli aktywny —, lub **zdalne źródło** pobrane przez SSH, zobacz poniżej); **Ulubione** (kombinacja logów + przeglądarki zapisana pod nazwą, bezpośrednie uruchamianie); **Podgląd logów** z 3 przeglądarkami do wyboru zależnie od liczby wybranych logów — Prosta (tail na żywo + ogólne statystyki IP/błędów/kodów HTTP dla dowolnego formatu), Klasyczna (odczyt + śledzenie), scalony `lnav` (rzeczywiste renderowanie terminala w interfejsie, logi magnet dołączane automatycznie + ręczne ścieżki **przypięte**, by zachować je między sesjami); **Podgląd i obsługa IP** (najaktywniejsze IP z jednego lub kilku wybranych logów, okres 24h/7d/30d/wszystko, usunięcie IP). Kolumna **Konserwacja** (bez zmian): ręczna lub automatyczna rotacja/archiwizacja według progu rozmiaru, natychmiastowe tworzenie kopii, konfiguracja/zarządzanie zaplanowanymi automatyzacjami (deklaratywne — zobacz uwagę poniżej), przywracanie/czyszczenie archiwum, eksport listy.
- **Usługa** — te same akcje co `service` w CLI (§12), jednorazowe podniesienie uprawnień `sudo` dla każdej akcji, nigdy cała aplikacja uruchomiona jako root.
- **Multi-instancja** — globalny rejestr (`~/.config/omega-serv/instances.json`, poza jakimkolwiek katalogiem projektu) znanych instalacji na maszynie, ze stanem systemd każdej z nich; tworzenie nowej instancji (kopia drzewa katalogów, własne środowisko wirtualne i zależności, świeża konfiguracja z osobnym portem, sprawdzenie zagnieżdżenia i konfliktu portów) bezpośrednio z interfejsu. Przycisk praktycznie niewidoczny przy pojedynczej instalacji (etykieta "Multi-instancja" zmienia się w "Instancje (N)" od 2 znanych); pełne przełączenie na inną instancję (`os.execv`, jawne potwierdzenie, dedykowany splash zapowiadający przełączenie przy restarcie); pełna deinstalacja instancji (usunięcie unitu, dedykowanego konta systemowego, jeśli nie używa go już żadna inna instancja, oraz opcjonalne usunięcie katalogu, nigdy domyślnie).
- **Stan i zasoby** — przegląd na jedno spojrzenie, odświeżany co 2 sekundy: stan serwera (proces/PID, stan usługi systemowej, profil/aktywne opcje/TLS/port), strumień logu dostępu na żywo (przepustowość, rozkład według kodu stanu, unikalne IP, odsetek błędów), zasoby systemowe (CPU/RAM/dysk/swap/obciążenie/sieć, przez `psutil`); zawiera też skrót **Symuluj żądanie** (ten sam przypadek użycia co odpowiednie polecenie CLI, §10).
- **Audyt bezpieczeństwa** — ten sam przypadek użycia co odpowiednie polecenie CLI (§10).
- **Kopia zapasowa konfiguracji** — archiwum tar.gz pliku konfiguracji i, na jawne życzenie, reguł WAF/stref uwierzytelniania/certyfikatów (potwierdzenie obowiązkowe, gdy zawarte są prawdziwe sekrety)/bazy Active Defense, przywracanie, lista, usuwanie.

> Uwaga o zaplanowanych automatyzacjach rotacji: są zapisywane (częstotliwość + docelowy log), ale **nic ich automatycznie nie wykonuje** — ani po stronie interfejsu, ani w tle. To celowy wybór dla zgodności z odpowiednim ekranem `omega-fire`, który ma to samo deklaratywne zachowanie. Rzeczywiste okresowe wykonywanie (timer systemd, zadanie w tle) trzeba zbudować osobno, jeśli potrzeba się potwierdzi.

#### Ustawienia aplikacji (klawisz `o` lub paleta poleceń)

Tylko preferencje interfejsu — nigdy nie mylić z `config/omega-serve.json` (konfiguracja serwera): aktywny motyw, profil renderowania (`complete`/`standard`/`reduced`/`mono`, wymagany restart), ścieżka eksportów (domyślnie `var/exports/`), ścieżka zrzutów ekranu (domyślnie `var/screenshots/`), czyszczenie jednego lub drugiego katalogu (potwierdzenie obowiązkowe).

```bash
# Uruchomienie serwera (pierwszy plan, SIGTERM = czyste zatrzymanie z okresem karencji, SIGHUP = przeladowanie w locie WAF/Auth)
./omega-serv.sh serve

# Konfiguracja
./omega-serv.sh config init                # generuje config/omega-serve.json (bezpieczne wartosci domyslne)
./omega-serv.sh config check                # sprawdza bez uruchamiania (te same blokady co przy starcie)
./omega-serv.sh config show
./omega-serv.sh config enable-tls --cert ... --key ... --mode direct
./omega-serv.sh config disable-tls

# Profile (minimal / standard / hardened / development)
./omega-serv.sh profile list
./omega-serv.sh profile show hardened
./omega-serv.sh profile apply hardened --dry-run   # diff przed zastosowaniem, zawsze

# Opcje (aliases, redirects, rewrites, dirlisting, cache, waf, upload, fastcgi, reverse_proxy...)
./omega-serv.sh option list
./omega-serv.sh option enable waf
./omega-serv.sh option disable waf

# Symulacja zadania bez uruchamiania serwera (przydatne do sprawdzenia reguly przed aktywacja)
./omega-serv.sh simulate-request GET /index.html

# WAF (dziala nawet przy wylaczonej opcji, przez niejawne --force)
./omega-serv.sh waf test --method GET --path /admin --remote-ip 203.0.113.1
./omega-serv.sh blocklist list
./omega-serv.sh blocklist add --network 203.0.113.0/24 --reason "wykryto skan" --duration-seconds 3600
./omega-serv.sh blocklist remove --network 203.0.113.0/24

# Active Defense (deception + tryb wojenny, opcja "active_defense" - zobacz §11)
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

# Certyfikaty TLS - samopodpisany (9a)
./omega-serv.sh certs generate-self-signed --cn localhost --san-dns localhost --san-ip 127.0.0.1
./omega-serv.sh certs show
./omega-serv.sh certs check-expiry --warn-days 30

# Certyfikaty TLS - lokalny CA (9b)
./omega-serv.sh certs generate-ca --cn "Moj lokalny CA" --days 3650
./omega-serv.sh certs generate-csr --cn server.local --san-dns server.local --key-out server.key --csr-out server.csr
./omega-serv.sh certs sign-csr --csr server.csr --ca-key secure/certificates/ca/root-ca.key --ca-cert secure/certificates/ca/root-ca.pem --out server.pem --fullchain-out fullchain.pem
./omega-serv.sh certs revoke --cert server.pem --ca-key secure/certificates/ca/root-ca.key --ca-cert secure/certificates/ca/root-ca.pem

# Certyfikaty TLS - import (9c, np. z hooka Certbota)
./omega-serv.sh certs import --key privkey.pem --cert fullchain.pem

# Uwierzytelnianie HTTP Basic
./omega-serv.sh auth add-user --username alice
./omega-serv.sh auth create-zone --url-prefix /admin/ --allowed-users alice
./omega-serv.sh auth list

# Audyt bezpieczenstwa (nigdy nie blokuje, informacyjny)
./omega-serv.sh audit security --format text --min-severity medium

# Kopia zapasowa konfiguracji (konfiguracja zawsze dolaczona; prawdziwe sekrety
# domyslnie nigdy nieszyfrowane, --confirm-secrets obowiazkowe, by je dolaczyc)
./omega-serv.sh config backup --description "przed migracja"
./omega-serv.sh config backup --include-auth --include-certificates --confirm-secrets
./omega-serv.sh config backup --include-active-defense --description "zagrozenia/incydenty"
./omega-serv.sh config list-backups
./omega-serv.sh config restore --snapshot-id snapshot_20260908_170003_762484

# Usluga systemowa (systemd/OpenRC/runit, automatyczne wykrywanie)
./omega-serv.sh service install --user omega-serv --group omega-serv
./omega-serv.sh service start
./omega-serv.sh service status
```

### Ważne kody wyjścia

| Polecenie | Kod | Znaczenie |
|---|---:|---|
| `audit security` | `0` | Nic poważnego (brak `CRITICAL`/`HIGH`) |
| `audit security` | `1` | Co najmniej jedno ustalenie `CRITICAL` |
| `audit security` | `2` | Co najmniej jedno `HIGH` bez `CRITICAL` |
| `audit security` | `3` | Błąd wykonania (nie znaleziono konfiguracji...) |
| `certs check-expiry` | `1` | Certyfikat wygasł |
| każde inne polecenie | `0`/`1` | Sukces / błąd walidacji |

## 4. Zgodność z terminalami

Interaktywny interfejs ([Textual](https://textual.textualize.io/) zbudowany na [Rich](https://rich.readthedocs.io/)) automatycznie wykrywa możliwości terminala (emulator, rozmiar) i odpowiednio dostosowuje swój strukturalny arkusz stylów (`complete`/`standard`/`reduced`/`mono`), bez ręcznej flagi. Tryb CLI pozostaje zawsze zwykłym tekstem, niezależnie od terminala. Polityka współdzielona przez cały pakiet `omega-` (`omega-lib`, `terminal/policies.py`) — identyczna z tą w `omega-check`/`omega-fire`.

### Profil według wykrytego emulatora

| Emulator | Profil początkowy |
|---|---|
| Ghostty, Alacritty, WezTerm, Kitty | `complete` |
| Konsole, GNOME Terminal, Terminator, Xfce4 Terminal | `standard` |
| xterm, urxvt, nowoczesne SSH | `reduced` |
| TTY Linuksa, stare SSH | `mono` |
| Nierozpoznany emulator | `reduced` (domyślne rozwiązanie zastępcze) |

### Profil według rozmiaru terminala

| Minimalny rozmiar (kolumny × wiersze) | Górny limit profilu |
|---|---|
| 120 × 32 | `complete` |
| 100 × 28 | `standard` |
| 80 × 24 | `reduced` |
| poniżej | `mono` |

Ostateczny profil to **bardziej restrykcyjny z dwóch** (emulator i rozmiar) — Ghostty na pełnym ekranie zmniejszony do 70 kolumn schodzi do `mono`, nawet jeśli jego emulator pozwalałby na `complete`. Można go odświeżyć na żywo klawiszem `r` lub ręcznie nadpisać w Ustawieniach aplikacji (klawisz `o`, §3).

## 5. Profile

| Profil | Przeznaczenie |
|---|---|
| `minimal` | Demonstracja/proste lokalne użycie: tylko statyka, żadna opcja nie jest włączona |
| `standard` | Strona statyczna lub mała produkcja: typowe nagłówki, bazowa CSP, lista katalogu/CGI/FastCGI wyłączone |
| `hardened` | Ekspozycja z minimalnymi uprawnieniami: domyślnie lokalny bind (reverse proxy zalecany dla Internetu), metody ograniczone do GET/HEAD, ścisła CSP, ochrona anti-slowloris — WAF **nigdy** nie jest włączany automatycznie, nawet tutaj |
| `development` | Tylko lokalny rozwój, nigdy nieprzedstawiany jako odpowiedni dla Internetu: bind loopback obowiązkowy, CSP w trybie report-only, szczegółowe strony błędów |

Kolejność scalania konfiguracji: wbudowane bezpieczne wartości → wybrany profil → aktualnie aktywne opcje są zachowywane (przetrwają zmianę profilu) → jawna nakładka użytkownika. Przed zapisem zawsze wyświetlany jest pełny diff (`profile apply`).

## 6. Architektura

Clean Architecture (`core / domain / ports / application / infrastructure / interfaces / bootstrap`) — `bootstrap/` jest korzeniem kompozycji (odpowiednik `app/` w pozostałych narzędziach pakietu). Świadoma osobliwość tego projektu, weryfikowana przez `import-linter`, a nie zakładana: `application/server/start_server.py` (oraz `validate_config.py`, `run_audit.py`) pełnią rolę **fabryki zależnej od rzeczywistej konfiguracji** (który menedżer usług, czy włączyć WAF...) i bezpośrednio tworzą konkretne adaptery `infrastructure/` — w przeciwieństwie do ściślejszego wzorca CHECK/TRACK, gdzie `application/` korzysta tylko z `ports/`. Jedyna naprawdę wymuszana uniwersalna reguła: `domain/`/`core/` nigdy nie zależą od warstw zewnętrznych.

```text
src/omega_serv/
├── core/            Wspolne slownictwo (platform_info, stale)
├── domain/           Czysta logika biznesowa (HTTP, konfiguracja, bezpieczenstwo WAF/TLS/auth/audyt, routing)
├── ports/            Kontrakty (Protocol) oczekiwane przez aplikacje
├── application/      Przypadki uzycia - niektore funkcje (build_server...) skladaja tez konkretne adaptery (zobacz wyzej)
├── infrastructure/    Rzeczywiste implementacje (asyncio, openssl jako podproces, systemd/OpenRC/runit, pliki)
├── interfaces/cli/    Nieinteraktywne CLI argparse
├── interfaces/tui/    Interaktywny interfejs Textual (te same przypadki uzycia, nigdy zduplikowana logika)
└── bootstrap/         DependencyContainer, ustalanie korzenia projektu
```

Reguły weryfikowane przez `import-linter` (8 kontraktów): `domain`/`core` nigdy nie zależą od warstw zewnętrznych; `interfaces.tui` nigdy bezpośrednio zależne od `infrastructure`; `textual` ograniczony do `interfaces.tui`; `subprocess` ograniczony do `infrastructure/process/subprocess_runner.py` (i `infrastructure/lnav/`, interaktywny strumień PTY); `ssl` ograniczony do `infrastructure/tls/ssl_context_builder.py`; `jinja2` ograniczony do `infrastructure/exporters/html_exporter.py`; `sqlite3` ograniczony do `infrastructure/persistence/sqlite_active_defense_connection.py` (jedyny relacyjny magazyn projektu, zarezerwowany dla Active Defense — zobacz §11); `lupa` ograniczona do `infrastructure/waf/lua_waf_adapter.py` (uzupełniający skrypt WAF « magnet », §7).

## 7. Moduły opcjonalne

We wszystkich dostarczonych profilach domyślnie wyłączone — włączanie zawsze jawne (`option enable <nazwa>` lub `config enable-tls`):

| Moduł | Rola |
|---|---|
| `waf` | Sygnatury (wrażliwe ścieżki, UA/Referer skanerów, SQLi/XSS/CMDi w treści), listy edytowalne jako plik tekstowy (słowa kluczowe lub wrażliwe ścieżki z wyjątkami `!`, tryb Obserwacji i własna reguła recydywy dla każdej listy — dwa dostarczone wzorce, jawne ładowanie, zobacz §11b), ograniczanie szybkości (token bucket, reguły na folder i na IP/sieć, zobacz §11c), lista blokad (CIDR + wygasanie), reputacja/eskalacja, import istniejącego skryptu WAF `mod_magnet` z Lighttpd jako opcjonalne wzmocnienie typu « magnet » (bez przepisywania, dodatek `pip install -e ".[magnet]"` — addytywny, nigdy nie może znieść natywnej blokady; sprawdzenie zgodności podczas importu, dedykowany ekran TUI) — tryb `log-only` strukturalnie niezdolny do blokowania |
| TLS | Bezpośredni (samopodpisany, lokalny CA lub publiczny przez Let's Encrypt/Certbot z automatycznym odnawianiem — zobacz §9), nigdy mTLS/OCSP w V1 |
| Uwierzytelnianie | HTTP Basic dla strefy (`url_prefix`), `hashlib.scrypt` z ochroną przed atakami czasowymi (stały czas nawet dla nieznanego użytkownika) |
| FastCGI/PHP-FPM | Jedna para `(url_prefix, script_root)`, `script_root` z założenia trzymany poza `webroot/` (handler statyczny nigdy nie może ujawnić kodu źródłowego PHP) |
| Wychodzący reverse proxy | Omega-serv sam działa jako proxy do jednego lub kilku backendów (kierunek odwrotny do `server.tls.mode = "behind_proxy"`) — rozkładanie obciążenia (round-robin, ważony, least-connections, ip-hash, least-response-time, rzeczywiste obciążenie), powinowactwo sesji i reguły routingu według nagłówka, pasywna i aktywna kontrola zdrowia, cache odpowiedzi (wiele wariantów `Vary`), backpressure, ochrona przed pętlami, API administracyjne w locie — zobacz §7a, gdzie są wszystkie szczegóły |
| Upload | Odizolowane strefy, limity na strefę, nazwy plików generowane po stronie serwera — brak streamingu w V1 (ograniczone przez `server.max_request_size`) |
| `active_defense` | Deception + tryb wojenny na podstawie już obliczonych sygnałów WAF (nigdy drugi wynik): statyczne przynęty, celowane spowalnianie/wzbogacone logowanie/ograniczanie szybkości, incydenty + eksport IoC — zobacz §11 |

### 7a. Wychodzący reverse proxy — szczegóły

OMEGA-SERV może sam działać jako reverse proxy do jednego lub kilku backendów HTTP/HTTPS — nigdy nie mylić z `server.tls.mode = "behind_proxy"` (OMEGA-SERV **za** proxy, odwrotny mechanizm). Strefy konfigurowalne z pełnym CRUD (TUI: *Szczegółowa konfiguracja → Reverse Proxy*), jeden lub kilka upstreamów na strefę.

- **Rozkładanie obciążenia** — `round_robin` (domyślnie), `weighted_round_robin`/`weighted_least_connections`/`ip_hash` (ważone), `least_connections`, `least_response_time`, `real_load` (rzeczywiste obciążenie). Tryb `real_load` natywny (sonda `/.omega-serv-load/`, wykorzystuje ten sam odczyt `psutil` co ekran « Stan i zasoby », nigdy drugie wywołanie) lub deklaratywny (zewnętrzna sonda HTTP, minimalny format `{"load_percent": ...}` lub sama liczba) — granulacja na upstream, jedna strefa może łączyć oba.
- **Powinowactwo sesji i routing warunkowy** — nieprzezroczyste ciasteczko sticky (rzeczywisty host:port nigdy nie jest ujawniany klientowi) i reguły według nagłówka (równość lub prefiks), obie filtrowane według dostępności docelowego upstreamu (czysto wracają do aktywnej strategii, jeśli docelowy upstream jest niedostępny).
- **Zdrowie** — pasywne (kolejne niepowodzenia/sukcesy, osobne progi przełączania down/up, by ograniczyć flapping) **i** aktywne (okresowa sonda niezależna od rzeczywistego ruchu, opcjonalna na upstream, wykorzystuje ten sam mechanizm zadań w tle co rzeczywiste obciążenie). Stany `DOWN` (zawsze automatyczny), `DRAINING`/`MAINTENANCE` (zawsze ręczne, wyraźnie tymczasowe, nigdy nie utrwalane) — ręcznie ustawiony upstream pozostaje wykluczony z nowych wyborów, nigdy nie przerywając już ustanowionego połączenia. Automatyczna ponowna próba na innym upstreamie, tylko dla metod idempotentnych (GET/HEAD/OPTIONS) i tylko przy błędzie połączenia.
- **Backpressure** — konfigurowalny dla każdego upstreamu limit aktywnych połączeń; nasycony upstream czysto odmawia kodem 503, w odróżnieniu od niedziałającego upstreamu (502, mimo to ponawiany).
- **Cache odpowiedzi** — tylko GET/HEAD, nigdy odpowiedź z błędem, nigdy `Set-Cookie` poza jawnym opt-in dla strefy; respektuje `Cache-Control`/`Vary` upstreamu (opcja możliwa do wyłączenia, ale niebezpieczna, ta sama filozofia co weryfikacja TLS). Wiele wariantów tego samego zasobu (`Vary`) faktycznie współistnieje na dysku, nigdy proste « ostatni wygrywa ». Blokada anti-stampede (tylko jedno równoczesne żądanie faktycznie odbudowuje cache). Nagłówek diagnostyczny `X-Omega-Cache: HIT`/`MISS`/`BYPASS` przy każdej odpowiedzi. Nadzór/czyszczenie w dedykowanym ekranie TUI (*Cache reverse proxy*).
- **Ochrona przed pętlami** — nagłówki hop-by-hop usuwane, `X-Forwarded-*` zawsze nadpisywane (nigdy scalane z nagłówkami klienta), licznik `X-Omega-Proxy-Hops` zwiększany przy każdym przekazaniu (czysta odmowa powyżej 5 przeskoków — wykrywa pośrednią pętlę między dwiema instancjami, której prosta lokalna walidacja konfiguracji nigdy nie zobaczy).
- **WebSocket** — upgrade dopuszczalny dla strefy, jeden upstream ustalony na cały czas trwania tunelu po jego zestawieniu, bez limitu czasu aplikacji.
- **Administracja w locie** — małe lokalne API HTTP (`/.omega-serv-admin/`, chronione przez `trusted_proxy` jak natywna sonda obciążenia), pozwalające TUI odczytać/wymusić stan DRAINING/MAINTENANCE backendu i odczytać współczynnik hit/miss cache **faktycznie działającego serwera** (dedykowany ekran *Stan backendów na żywo*) — ponieważ TUI i serwer pozostają dwoma osobnymi procesami bez współdzielonej pamięci, ten lokalny kanał HTTP jest jedynym mostem między nimi.

## 8. Utwardzenie HTTP (niewyłączalne)

- Nagłówek/wiersz żądania ograniczane **podczas** odczytu (nigdy po fakcie), przestarzałe zawijanie nagłówków odrzucane, `Transfer-Encoding` zawsze odrzucany (nigdy zgadywany).
- Zduplikowany `Content-Length` odrzucany; `Expect: 100-continue` czysto odrzucany (417).
- Jawna biała lista metod (w przeciwnym razie 405 + `Allow`), nagłówek `Host` walidowany (brakujący/pusty/zduplikowany-nawet-identyczny/znak sterujący → 400).
- Nagłówki bezpieczeństwa i bazowa CSP (`enforce`/`report-only`) stosowane do **każdej** odpowiedzi, także błędów — nieomijalne żadną opcją. `Cross-Origin-Opener-Policy`/`Cross-Origin-Resource-Policy` zawsze `same-origin`, bez realnego ryzyka zepsucia strony. `Cross-Origin-Embedder-Policy` zawsze wysyłany jawnie (nigdy nieobecny — zewnętrzny skaner odróżnia w ten sposób « nierozważony » od « świadomie permisywny »), domyślnie `unsafe-none` we **wszystkich** profilach, łącznie z `hardened`: w przeciwieństwie do dwóch poprzednich `require-corp`/`credentialless` mogą blokować zasoby cross-origin (czcionki, obrazy, iframe'y stron trzecich) należące do faktycznie serwowanej strony — konfigurowalne (`security.coep_mode`). Strefy CSP (`security.csp_zones`): **jawne** wyjątki dla prefiksu ścieżki (np. `unsafe-inline` tylko pod `/jakis-katalog/`, który naprawdę tego potrzebuje), każdy w pełni zastępuje domyślną politykę dla swojego prefiksu — nigdy scalanie, nigdy globalne poluzowanie; każdy wyjątek pozostaje widoczny w `audit security` (CSP-001/CSP-002 skanują też strefy), nawet jeśli jest świadomy. Tworzenie prowadzone przez kreator dyrektywa po dyrektywie (ekran **Bezpieczeństwo ogólne**), każde pole wstępnie wypełnione **bieżącą** wartością globalnej polityki — by zmieniać tylko to, co musi się zmienić, zamiast zaczynać od pustego pola, które mimowolnie poświęciłoby inne dyrektywy; dodatkowe jawne potwierdzenie jest wymagane, jeśli złożona strefa luzuje `unsafe-inline`/`unsafe-eval`/ogólne źródło `*`.
- Adresy IPv4 zmapowane na IPv6 (`::ffff:x.x.x.x`) normalizowane przed każdym porównaniem (lista blokad, zaufane proxy, ograniczanie szybkości) — w przeciwnym razie znane obejście.
- Weryfikowane testami właściwości (`hypothesis`, tysiące wygenerowanych przykładów) parsera HTTP i resolwera ścieżek, oprócz klasycznych testów jednostkowych/integracyjnych.

## 9. TLS

### 9a. Certyfikat samopodpisany (minimalny)

Obejmuje realistyczne użycie lokalne/laboratoryjne/VPN (Tailscale...): jeden listener, bezpośredni `ssl.SSLContext`, RSA 2048/4096 lub ECDSA P-256/P-384.

### 9b. Lokalny CA

Dla kilku urządzeń klienckich, które mają ufać bez osobnego importowania certyfikatu: lokalny urząd certyfikacji podpisuje tyle certyfikatów serwera, ile potrzeba.

```text
secure/certificates/ca/
├── root-ca.key    # 0600 - najbardziej wrazliwy element projektu
├── root-ca.pem    # 0644 - do zaimportowania do magazynu zaufania klientow
├── serial.txt     # 0600 - sledzenie nastepnego numeru seryjnego
└── index.txt      # 0600 - sledzenie stanu V(alid)/R(evoked) dla kazdego podpisanego certyfikatu
```

Przebieg: `certs generate-ca` (hasło klucza CA **obowiązkowe**, interaktywne wprowadzanie z podwójnym potwierdzeniem, jeśli pominięto `--password`) → `certs generate-csr` (klucz + CSR serwera) → `certs sign-csr` (podpisuje CA, kopiuje SAN z CSR, na życzenie tworzy `fullchain.pem`) → wskazanie `tls.certificate.certificate_path` na ten `fullchain.pem`. Skompromitowany certyfikat wycofuje się przez `certs revoke` (oznacza `index.txt`, najpierw sprawdza, czy certyfikat rzeczywiście pochodzi z tego CA — w przeciwnym razie odmawia). Brak dystrybucji CRL w V1, brak zewnętrznego CA/CSR dla urzędu zewnętrznego, brak mTLS (zobacz §15).

### 9c. Let's Encrypt / ACME (Certbot) — publiczny, samodzielnie hostowany

Dla naprawdę publicznej strony z certyfikatem uznawanym przez przeglądarki, pełny schemat samodzielnego hostingu: DDNS (Dynu lub odpowiednik, w całości po stronie operatora) → Certbot → Omega-serv. Tylko kreator TUI (`Szczegółowa konfiguracja → TLS → Kreator Let's Encrypt`) — wywołuje `certbot certonly --webroot` jako podproces (**nigdy** `--standalone`, port 80 jest już zajęty przez Omega-serv; **nigdy** ponownie zaimplementowany klient ACME) z `--config-dir`/`--work-dir`/`--logs-dir` wskazującymi na `secure/certificates/letsencrypt/` projektu — **nigdy** `/etc/letsencrypt/` — dzięki czemu sam Certbot działa w pełni bez uprawnień. Uzyskany certyfikat jest importowany automatycznie (ten sam mechanizm co `certs import`, zobacz przykłady CLI powyżej) i zapisywany jest skrypt hooka odnawiania. Tryb testowy (staging) domyślnie zaznaczony — do odznaczenia po sprawdzeniu, że domena/webroot działają, by uniknąć rzeczywistych limitów Let's Encrypt.

Wymagania całkowicie poza zakresem Omega-serv: domena wskazująca na publiczne IP (DDNS) oraz porty 80/443 przekierowane na tę maszynę.

### 9d. Automatyczne odnawianie (Certbot)

`Szczegółowa konfiguracja → TLS → Automatyczne odnawianie` dostosowuje się do faktycznie wykrytego menedżera usług **dla tej instancji** (nigdy mechanizm współdzielony przez kilka instancji): systemd → generuje i instaluje timer (`<service>-certbot-renew.timer`, dwa razy dziennie + losowe opóźnienie, `certbot renew` ograniczony do `--config-dir` instancji); w przeciwnym razie → wiersz crontab (bieżący użytkownik, bez uprawnień), jeśli `crontab` jest dostępny; w przeciwnym razie → wyświetlane instrukcje ręczne, żadnego wymuszonego zapisu. W niektórych dystrybucjach (m.in. Arch/Manjaro) pakiet Certbot domyślnie **nie** instaluje żadnego timera, w przeciwieństwie do Debiana/Ubuntu — stąd ten ekran zamiast prostego sprawdzenia mechanizmu rzekomo już obecnego. Po skonfigurowaniu odnawianie automatycznie importuje ponownie każdy odnowiony certyfikat (`certs import`), a następnie restartuje usługę, bez żadnej dalszej ręcznej interwencji.

## 10. Audyt bezpieczeństwa

`audit security` jest **nieblokujący**: ponownie wykonuje już blokujące bramki `config check` jako `CRITICAL`, a następnie stosuje reguły doradcze (TLS, CSP, niebezpieczne metody, limity czasu, higiena uploadu w czystej postaci; uprawnienia plików, wygaśnięcie certyfikatu, zainstalowany unit systemd, rozmiar logów przy rzeczywistym I/O). `WAF-001` (WAF pozostawiony w `log-only`) jest obserwowany w czasie przez mały plik stanu (`var/run/waf-mode-state.json`) — wyzwala się dopiero po ≥14 dniach obserwacji w `log-only` przy powtarzanych uruchomieniach, nie przy pierwszym `audit`.

## 11. Active Defense (deception + tryb wojenny)

Moduł opcjonalny (`option enable active_defense`, domyślnie wyłączony), który kwalifikuje wrogie zachowanie na podstawie już obliczonych sygnałów WAF (`WafDecision`/reputacja/lista blokad — nigdy drugie, niezależne obliczanie wyniku) i może przekierować źródło na przynętę, spowolnić jego odpowiedzi i logować dokładniej, zbudować użyteczny incydent, a następnie wyeksportować wskaźniki kompromitacji (IoC). Nigdy sam nie blokuje ruchu — blokada sieciowa pozostaje zadaniem `omega-fire`; Active Defense obserwuje, przekierowuje, spowalnia i dokumentuje.

**Zagrożenia i wynik**: każde źródło (`IP + skrót SHA-256 User-Agenta`) gromadzi wynik (`WAF-001` blokujący +10, eskalacja reputacji +25, znany ban +25, POST na już przydzieloną przynętę +30 — spadek o -5 co 15 minut bez nowego zdarzenia), kwalifikowane jako `normal`/`suspicious`/`hostile`/`contained` (`contained` wymaga dodatkowo już znanego bana). `mode: monitor` obserwuje bez działania; `mode: enforce` faktycznie stosuje poniższe akcje.

**Tryb wojenny** (`options.active_defense.settings.war_mode`): `DefensePlaybook` (`actions: ["redirect_to_decoy", "enrich_log", "delay", "rate_limit", "create_incident", "export_ioc"]`) wyzwalany przez konfigurowalne progi, dla każdego źródła innego niż `normal`:
- `enrich_log` — osobny log JSONL (`var/log/active-defense-enriched.jsonl`, nigdy niemieszany z logiem WAF/produkcyjnym), zredagowane nagłówki, treść HTTP haszowana (SHA-256) lub obcinana zgodnie z `logging.capture_request_body`.
- `delay` — ograniczone spowolnienie z jitterem (`war_mode.slowdown.minimum_ms`/`maximum_ms`/`jitter_ms`), nigdy blokowanie pętli asyncio.
- `rate_limit` — dedykowane ograniczanie szybkości na źródło (`war_mode.rate_limit.requests`/`window_seconds`), wykorzystuje ten sam mechanizm co WAF pod osobnym kluczem.
- `create_incident` — automatyczne otwarcie/scalenie incydentu po przekroczeniu `thresholds.incident_score`.

**Deception**: źródło `hostile`/`contained` może zostać przydzielone do statycznej przynęty (`fake_admin`, `fake_cms`, `fake_api`, `fake_secrets` — wiarygodne, ale zawsze stałe odpowiedzi, nigdy rzeczywisty odczyt plików ani podprocesy), wybranej według zaobserwowanej klasy ataku (`deception.profiles.<nazwa>.match_attack_classes`, jedna lub kilka spośród `scan`/`credential_stuffing`/`sqli`/`xss`/`path_traversal`/`upload_probe`/`api_probe`/`unknown`). Dwa poziomy izolacji, świadomie przyjęte i udokumentowane jako takie:
- **Poziom 1** (fixture w procesie, `isolation_level: "fixture"`, domyślnie) — jawnie SŁABA izolacja: ten sam proces, ten sam użytkownik systemu co produkcja, akceptowalna tylko dlatego, że fixture nigdy nie robi nic innego niż zwrócenie statycznego szablonu. NAZWA profilu musi dokładnie odpowiadać jednej z 4 powyższych fixture — w przeciwnym razie odrzucona przy walidacji (`validate_active_defense_config`), by uniknąć pułapki źle nazwanej przynęty, która wtedy po cichu nigdy się nie uruchamia.
- **Poziom 2** (naprawdę odizolowany backend, `isolation_level: "proxy"`) — przekazywanie do osobnego procesu przez `options.active_defense.settings.deception.decoy_zones.<nazwa>` (upstream `host`/`port` już działającego serwera, nigdy tworzony automatycznie; nigdy odczytywany z `options.reverse_proxy` — przynęta nigdy nie może przypadkiem wskazać strefy produkcyjnej, sprawdzane przez `config check`), z ponownym użyciem tego samego mechanizmu wychodzącego reverse proxy co produkcja (`serve_proxy()` — upstream nieosiągalny w chwili rzeczywistego żądania: 502 zwracane atakującemu, nigdy awaria).

**Ekran Ustawienia** (TUI, Aktywne zabezpieczenia → Active Defense → Ustawienia): pełna konfiguracja wszystkiego powyższego — tryb, włączenie trybu wojennego, zakres/akcje/progi/spowolnienie/limit żądań, deception (domyślne zachowanie, CRUD profili przynęt i stref przynęt z przykładowymi wartościami w każdym polu), IoC, przechowywanie i logowanie — walidowana tymi samymi regułami co CLI przed każdym zapisem, bez potrzeby ręcznej edycji `config/omega-serve.json`. Po każdej zmianie zawsze wymagany jest pełny restart (Active Defense nigdy nie jest przeładowywany w locie).

**Incydenty i IoC**: pełna chronologia dla każdego incydentu, wyodrębnianie wskaźników (IP, haszowany User-Agent), wersjonowany eksport JSON/CSV ograniczony do udostępnialnych IoC/raport Markdown oraz formaty wymiany **STIX 2.1** (pakiet do wczytania w OpenCTI, systemie SIEM…) i **MISP** (zdarzenie do zaimportowania przez interfejs MISP), domyślnie oznaczone TLP:AMBER — pliki lokalne, nigdy nie wysyłane; każdy eksport z plikiem `<export>.sha256` (standardowy format `sha256sum`). Automatyczny eksport przy zamknięciu incydentu, jeśli `ioc.auto_export_on_close` (domyślnie prawda). Wygasłe stany i dziennik audytu są czyszczone automatycznie, a baza ma ograniczony rozmiar (ochrona przed zapełnieniem dysku); `active-defense purge` dodatkowo zamyka incydenty, które ucichły.

**Symulacja**: `active-defense simulate` (CLI) i przycisk "Symuluj" (TUI, ekran Aktywne zabezpieczenia) prognozują wynik/poziom i wyjaśniają każdą akcję, która by się uruchomiła — ścisły dry-run, żadnego rzeczywistego zapisu, żadnego wpływu na sieć.

Kopia/przywracanie: `config backup --include-active-defense` dołącza bazę sqlite (zagrożenia/incydenty/przydziały) do archiwum — nigdy sekretów jawnym tekstem, więc bez wymaganego `--confirm-secrets`, w przeciwieństwie do `--include-auth`.

## 11b. Listy wrażliwych ścieżek (WAF)

WAF może ładować **edytowalne listy** jako plik tekstowy, jedna ścieżka (lub słowo kluczowe) na wiersz, z **Aktywne zabezpieczenia → Custom → Dodaj → « ZAŁADUJ listę »**. Domyślnie nigdy nic nie jest ładowane: to jawna akcja.

- **Dostarczone wzorce**: `sensitive-paths-hostile` (298 ścieżek bez uzasadnionego użycia: sekrety, kopie zapasowe, VCS, konsole…) i `sensitive-paths-probe` (132 ścieżki sondujące, czasem serwowane przez prawdziwą stronę: `/admin`, `/api`, monitoring…). Przy ładowaniu tworzona jest **lokalna kopia** w `secure/waf/rules/keywords/`: to ją edytujesz, aktualizacja omega-serv nigdy jej nie nadpisuje (« Nowości we wzorcu » proponuje potem, pole po polu, nowe wpisy).
- **Składnia**: `/admin` (→ `/admin` i `/admin/xxx`, nigdy `/administrator`), `/.git/` (wszystko pod spodem), `/*.bak` (rozszerzenie), `!/api/v1` (wyjątek, zawsze ma pierwszeństwo). Ścieżki dekodowane jak w silniku (`%2e`, podwójne kodowanie, znaki pełnej szerokości).
- **Waga**: *Obserwacja* (tylko log, zalecana przy pierwszym ładowaniu), potem Średnia (nigdy nie blokuje sama) lub Wysoka (403 od pierwszego dostępu).
- **Własna reguła recydywy dla każdej listy**: 1. dostęp = informacja lub odmowa; N dostępów w M minut = tymczasowy ban aplikacyjny (odpowiedź 451, także przez Tailscale); powtarzające się blokady = ban sieciowy przez omega-jail. Wzorce: hostile 2 dostępy w 10 min → 24 h, sondowanie 5 w 10 min → 1 h.
- **Nigdy automatycznego bana** dla lokalnego hosta, Tailscale (`100.64.0.0/10`) i sieci lokalnej (`options.waf.reputation.never_auto_block`): zbanowany może zostać tylko ruch zewnętrzny. Za lokalnym proxy wyjątek dla `127.0.0.1` wymaga aktywnego `trusted_proxy`. `X-Forwarded-For` jest czytany od prawej do lewej: klient nie może sam ogłosić się lokalnym.
- **Zabezpieczenia**: chronione ścieżki kluczowe (`/`, `robots.txt`, `sitemap.xml`, `/.well-known/acme-challenge/`…), odrzucenie blokującej listy, która trafiłaby w faktycznie serwowaną trasę (alias, reverse proxy, strefa Auth, webroot), **« Sprawdź z moimi logami »** w edytorze (wiersze, które trafiłyby w udane żądania, wyjątek jednym kliknięciem).
- **Wbudowany edytor**: diagnostyka na żywo z numerem wiersza, « Testuj » ścieżkę, bezpieczny zapis (uprawnienia i grupa zachowane, dowiązania symboliczne odrzucane, zewnętrzna modyfikacja wykrywana), czytelność dla konta usługi sprawdzana (« Napraw uprawnienia ») i **uczciwe** przeładowanie: odrzucane z podaniem powodu, jeśli lista nie przejdzie sprawdzenia, a serwer zachowuje wtedy bieżące reguły.

## 11c. Limit żądań na folder i na IP/sieć (WAF)

Limit żądań WAF (token bucket, `options.waf.rate_limit`, domyślnie 60 żądań / 60 s na IP) można doprecyzować w **Aktywne zabezpieczenia → Wyjątki i limit żądań** (lub ręcznie, `rate_limit.path_policies` / `rate_limit.source_policies`):

- **Reguła na folder** (`prefix`, `requests`, `window_seconds`): **zastępuje** limit globalny dla tego folderu, z własnym licznikiem (`requests: 0` = bez limitu). Wygrywa najdłuższy prefiks; `/images` obejmuje `/images/a.png`, nigdy `/images2`. Typowo ciężka strona (galeria obrazów), która zwraca 429.
- **Reguła na IP/sieć** (`network`, `requests`, `window_seconds`, `trusted`): ta sama zasada; wygrywa najdokładniejsza sieć. Priorytet: folder, potem IP/sieć, potem limit globalny.
- **Banowanie bez zmian dla publiczności**: przekroczenie przez publiczny adres IP nadal jest zapisywane jako `"action": "block"` w `waf-alerts.log`, więc omega-jail może go zbanować (3 odrzucenia w 10 min → 12 h). **Bezpieczne źródło** — sieć `never_auto_block` lub reguła oznaczona `trusted: true` — nadal dostaje 429, ale jest zapisywane jako `"action": "throttle"`, czego jail nigdy nie liczy.
- **Skrypt magnet**: jego własny limit żądań (odpowiedź 429) nigdy nie jest liczony jako wykrycie, więc nigdy nie prowadzi do automatycznego bana; przy żądaniu objętym regułą folderu lub IP/sieci obowiązuje reguła natywna, a 429 z magnet jest ignorowane (jego sygnatury ataków nadal działają).
- Reguła limitu **nigdy** nie wyłącza inspekcji WAF; i odwrotnie, wyłączenie z inspekcji (`exclusions.path_prefixes`) nigdy nie znosi limitu żądań. Bez aktywnego `trusted_proxy` reguła obejmująca `127.0.0.1`/`::1` jest ignorowana (to samo zabezpieczenie co `never_auto_block`).

## 12. Usługi i eksploatacja

Automatyczne wykrywanie systemd/OpenRC/runit (`service install/status/start/stop/restart/enable/disable/uninstall`). Wygenerowany unit systemd domyślnie stosuje niepodlegające negocjacji utwardzenie: `NoNewPrivileges`, `PrivateTmp`, `ProtectSystem=strict`, `ProtectHome`, `ReadWritePaths` ograniczone do `var/`, dedykowany użytkownik/grupa obowiązkowe, `UMask=0077`, `Restart=on-failure`. Czyste zatrzymanie przy SIGTERM (opróżnianie trwających połączeń, konfigurowalny okres karencji, potem wymuszone zamknięcie); przeładowanie w locie przy SIGHUP (tylko reguły WAF i strefy Auth — bind/port/TLS i Active Defense nigdy niezmienialne bez pełnego restartu).

## 13. Dzienniki

`var/log/access.log` (format Apache combined + `request_id`, escapowanie przeciw wstrzykiwaniu do logów), `var/log/error.log`. Rotacja według rozmiaru/liczby zachowanych plików (`logs.rotation`). Natywny WAF: `var/log/waf-alerts.log` (`options.waf.logging.path`). Skrypt magnet (§7): `options.waf.magnet.paths.alerts_log`/`.blocklist_log`, domyślnie `var/log/waf-magnet-alerts.log`/`var/log/waf-magnet-blocklist.log` — automatycznie dodawane do Biblioteki (przycisk *Dodaj znane logi Omega-Serv*) tylko wtedy, gdy magnet jest aktywny; `lnav` za to zawsze je proponuje (brakujący plik jest po prostu pomijany przy uruchomieniu).

### 13a. Zdalne źródła (SSH)

Centralizuje, na jawne żądanie, log serwera backendowego w tej samej sieci lokalnej za reverse proxy (ekran **Zarządzanie logami → Biblioteka → Zdalne źródła (SSH)**). « Fetch » to ręczna, jednorazowa akcja, nigdy strumień na żywo ani automatyczne odpytywanie: **kopia** jest pobierana przez `scp` w chwili kliknięcia *Pobierz teraz*, zapisywana w `var/log/remote/`, a następnie dodawana do Biblioteki jak zwykły log (kolumna *Dostęp* = `ssh`, kolumna *Zmodyfikowano* = data **tego** pobrania — nigdy data zdalnego pliku); nowe pobranie po prostu zastępuje poprzednią kopię nowszą.

Świadome zabezpieczenia (zobacz `OMEGA-SERV_ETUDE-FAISABILITE_LOGS_DISTANTS.md`, gdzie jest pełne studium): brak automatycznego skanowania sieci, brak połączenia bez jawnej konfiguracji (etykieta/host/zdalna ścieżka, użytkownik/port/klucz prywatny opcjonalne — puste pozwalają `ssh`/`~/.ssh/config` zdecydować tak, jakby polecenie było wpisane ręcznie), nigdy nie jest pytane ani przechowywane hasło (klucz prywatny jest wskazywany tylko ścieżką, nigdy nie jest czytany ani przechowywany przez Omega-serv), brak sprawdzania rozmiaru przed transferem. Możliwość `scp` wykrywana lokalnie w **Rejestrze możliwości** (tylko obecność programu, nigdy test osiągalności hosta); Samba świadomie pominięta (YAGNI, dopóki nie potwierdzi się rzeczywista potrzeba).

## 14. Testy

```bash
source .venv/bin/activate
lint-imports        # sprawdza 8 kontraktow warstw
pytest -q           # 2485 testow
ruff check .
mypy src
```

Struktura: `tests/unit/` (domena/aplikacja, dublery testowe), `tests/integration/` (prawdziwy serwer asyncio na prawdziwych gniazdach TCP, prawdziwy `openssl` jako podproces, prawdziwe polecenia CLI na pełnym tymczasowym projekcie, interaktywny interfejs przez API `Pilot` z Textual - nigdy zrzuty ekranu), `tests/security/` (testy właściwości `hypothesis` parsera HTTP i resolwera ścieżek).

## 15. Poza zakresem

- Surowe CGI (tylko FastCGI/PHP-FPM)
- mTLS (uwierzytelnianie klienta certyfikatem), OCSP stapling
- Zewnętrzny CA / CSR dla urzędu zewnętrznego, pełna dystrybucja CRL
- Active Defense: rzeczywista integracja ze zdarzeniami banów `omega-fire` (zablokowana po stronie `omega-fire`, które obecnie nie udostępnia żadnej powierzchni odczytu)

---

> 🔒 OMEGA-SERV — Solidny, kompletny, bezpieczny i defensywny serwer WWW.
