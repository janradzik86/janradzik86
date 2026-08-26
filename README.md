# ⬢ WOJAN STUDIO

> **MASZ POMYSŁ? ZBUDUJMY GO.**
> Projektujemy. Budujemy. Programujemy. Produkujemy. Tworzymy.

Platforma usługowa łącząca studio projektowe, warsztat techniczny, produkcję, elektronikę,
technologie cyfrowe, AI, marketing, grafikę oraz audio/wideo. Klient przechodzi od prostego
opisu pomysłu do gotowego projektu, prototypu, aplikacji, strony lub produktu fizycznego.

Główna ścieżka: **POMYSŁ → ANALIZA AI → SPECYFIKACJA → PROTOTYP → REALIZACJA → TESTY → GOTOWY PRODUKT**

---

## Szybki start

```bash
cd wojan-studio
npm start          # zero zależności — wystarczy Node.js 18+
npm test           # 32 testy (API + przeglądarkowy przepływ logowania)
```

Strona działa na `http://localhost:3000` (serwer nasłuchuje na `0.0.0.0`).

### Konta demonstracyjne

| Rola | E-mail | Hasło |
|---|---|---|
| Klient | `demo@wojan.studio` | `demo123` |
| Właściciel (admin) | `wojan@wojan.studio` | `wojan123` |

Można też zarejestrować własne konto — rejestracja jest otwarta.

> **Naprawa logowania (hotfix):** formularz logowania/rejestracji i zmiany hasła używały
> dostępu do pól przez `form.email` / `form.password`, który nie działa we wszystkich
> środowiskach (m.in. jsdom). Przełączono na jawne `form.elements.…` oraz naprawiono
> kolejność renderowania panelu (`renderPanel('')` przed widokiem asynchronicznym) —
> logowanie klienta i właściciela jest teraz pokryte testem przeglądarkowym.

---

## Co zawiera MVP

### 1. Strona publiczna (marketingowa)
- Hero „MASZ POMYSŁ? ZBUDUJMY GO.” z animowanym gradientem, particles, parallaksem
  reagującym na kursor, holograficznym ringiem i scanline.
- 7 obszarów usług (Metal, Laser, Technologia, Elektronika, Projektowanie, Marka & Reklama, Audio & Wideo) — sterowanych z panelu właściciela.
- Sekcja „laboratorium + warsztat” ze zdjęciem tła.
- Animowana sekcja procesu **„Od pomysłu do produktu”** (7 etapów, pasek postępu sterowany scrollem).
- Portfolio „CO JUŻ ZBUDOWALIŚMY” — zdjęcia, technologie, zakres, rezultat.
- Formularz kontaktowy **„CO CHCESZ STWORZYĆ?”** (imię, e-mail, telefon, opis, budżet, termin, załączniki).
- Scroll-reveal, microinteractions, magnetyczne przyciski, animowane CTA, hover-efekty.
- Pełna obsługa `prefers-reduced-motion` i optymalizacja mobilna.

**Interakcje:**
- **Kafelki usług prowadzą do galerii realizacji** (`#/galeria/<usługa>`) filtrowanej per dziedzina,
  z chipami kategorii i CTA do AI Buildera.
- **✦ Kafelka specjalna „PIOSENKI & UPOMINKI NA ŻYCZENIE”** (`#/zamowienie`):
  - pole opisu piosenki/upominku + wybór okazji,
  - 3 warianty do wyboru: **🎵✦ piosenka + grawer z QR code do utworu**, **🎵 sam utwór**, **✦ sam grawer personalizowany** (pole „treść graweru” chowa się dla wariantu bez graweru),
  - zamówienia zapisują się w backendzie, właściciel dostaje powiadomienie i obsługuje je
    w zakładce **✦ Upominki** (statusy: nowe → realizacja → gotowe).
- **Prawdziwe konto**: rejestracja/login na hashowane hasła, sesje tokenowe,
  zmiana hasła w **⚙ Ustawieniach konta** (`/api/me/password` weryfikuje obecne hasło).

### 1b. 📻 WOJAN RADIO — odtwarzacz audio/wideo na stronie głównej
- Sekcja radiowa grająca muzykę studia **jak stacja**: gdy utwór się kończy, następny
  startuje automatycznie; playlista zapętla się, jest tryb losowy 🔀, przewijanie, głośność.
- **Wgrywanie z telefonu/komputera**: właściciel (zalogowany) widzi przycisk „＋ DODAJ UTWORY”
  i może wgrać wiele plików naraz — zapisują się w backendzie (`data/media/`) i od razu
  pojawiają na playliście. Formaty: mp3, wav, ogg, m4a, aac, flac, mp4, webm, mov (do 90 MB).
  Wgrywanie idzie przez XMLHttpRequest z **paskiem postępu (%)** — widać, że plik się ładuje,
  nawet przy dużych utworach. Przycisk otwiera picker plików jawnym `input.click()`.
- **Audio i wideo**: utwory wideo renderują się w odtwarzaczu, audio gra w tle.
- Streaming z obsługą **HTTP Range** (206) → płynne przewijanie i szybki start.
- **Czas trwania utworów** mierzony po stronie klienta (metadane, sondy bez pełnego pobierania)
  i pokazywany na playliście.
- **🔍 Wyszukiwarka playlisty** — filtrowanie utworów na żywo po nazwie
  (także w zakładce Media u właściciela).
- **Ostatnio grane** — pasek z 3 ostatnio odtwarzanymi utworami (od najnowszego).
- **⤴ Udostępnianie utworu** — przycisk przy każdym utworze kopiuje bezpośredni, publiczny
  link do pliku (studio może od razu wysłać komuś swój kawałek).
- **„Teraz gra” — pływający widżet** — muzyka gra dalej, gdy użytkownik przechodzi między
  stronami; poza sekcją radia pojawia się widżet z tytułem utworu i sterowaniem
  (⏮ ▶/⏸ ⏭, można go ukryć ✕).
- **Licznik odtworzeń** — każde odtworzenie utworu jest zliczane (`POST /api/media/:id/play`);
  playlista pokazuje „▶ N”, a tabela w panelu właściciela kolumnę „Odtworzenia” (🔥 od 10).
- **Polubienia ❤** — zalogowani użytkownicy lajkują utwory (`POST /api/media/:id/like`, toggle);
  licznik i stan „liked” wracają z `GET /api/media`, a panel właściciela ma kolumnę „❤ Polub.”.
- **Filtr „❤ Tylko ulubione”** — przycisk obok wyszukiwarki zawęża playlistę do polubionych
  (łączy się z wyszukiwarką; czytelny komunikat, gdy brak ulubionych).
- **⌨ Skróty klawiszowe** — po kliknięciu w radio: **Spacja** odtwarzaj/pauza,
  **←/→** poprzedni/następny (bez kolizji z polami tekstowymi i przyciskami).
- **#/radio — samodzielna strona radia** — czysty odtwarzacz bez reszty landinga,
  do podania dalej lub osadzenia; linki z sekcji radia, palety komend i stopki.
- **Wizualizer widma** (Web Audio API) — holograficzne słupki cyan→violet→amber
  animowane w rytm muzyki (odporny na brak wsparcia przeglądarki).
- Globalny odtwarzacz gra dalej, nawet gdy użytkownik przechodzi między sekcjami.
- Zarządzanie: właściciel usuwa utwory bezpośrednio z playlisty (✕).
- **Hotfix wgrywania:** wyjątek wizualizera (np. brak kontekstu canvas) potrafił przerwać
  `RADIO.mount` i zablokować binding plików. Wiązania sterowania/wgrywania są teraz zapinane
  przed wizualizacją, a ta jest w pełni zabezpieczona — radio i upload działają również bez
  canvas. Obie ścieżki wgrywania (strona główna + panel admina) pokryte testami przeglądarkowymi.

### 2. 🤖 AI Project Builder (wersja demonstracyjna)
- Klient wpisuje swobodny opis pomysłu → silnik analizy generuje:
  cel, użytkowników, funkcje, ekrany, wymagania, dane, integracje, potencjalne problemy,
  sugerowane technologie, zakres MVP, **POZIOM PROJEKTU**, **SZACOWANY ZAKRES (moduły)**,
  **PROPONOWANY MVP**.
- Tryb **„NIE WIEM JESZCZE, JAK TO ZROBIĆ”** — rozbija pomysł na Hardware / Software / Produkcja / Projekt.
- Przycisk **UTWÓRZ PROTOTYP** zapisuje projekt w panelu klienta (z analizą, wyceną-szkicem, zadaniami i historią).
- Uczciwa informacja w UI: to demo silnika reguł — nic nie udaje prawdziwego generowania kodu.

### 3. Panel klienta
- **Lista kontrolna onboardingu** — karta „Twoja ścieżka • pomysł → produkt” z postępem 0–4
  (pierwszy projekt → analiza AI → prototyp → gotowy produkt) i podpowiedzią następnego kroku.
- **Feed aktywności** — ostatnie zdarzenia ze wszystkich projektów klienta w jednym miejscu
  (klikalne → otwiera projekt); endpoint `/api/activity/recent`.
- **MOJE PROJEKTY** ze statusami: 🔵 Analiza / 🟡 Agent pracuje / 🟢 Prototyp gotowy / ✅ Gotowy produkt.
- Szczegóły projektu z zakładkami: **OVERVIEW, AI AGENT, PREVIEW, PLIKI, WIADOMOŚCI, ZADANIA, HISTORIA**.
- Pipeline agenta (Analiza wymagań → Architektura → Interfejs → Tworzenie → Testy → Preview).
- **PREVIEW** — makieta interaktywna (telefon / przeglądarka / panel urządzenia) zależna od typu projektu.
- **Chat z agentem i Wojanem**: wiadomość w stylu *„Dodaj logowanie przez Google”* wywołuje
  kartę **„Zmiana projektu”** z listą zmian i przyciskiem **ZAAKCEPTUJ ZMIANĘ** → zadania + historia + wpis agenta.
- **🔔 Powiadomienia** — „Twój prototyp jest gotowy”, „Agent wykrył problem wymagający decyzji”,
  „Wojan odpowiedział na wiadomość” — z licznikiem nieprzeczytanych i **deep-linkami**:
  kliknięcie powiadomienia związanego z projektem od razu otwiera ten projekt
  (i oznacza powiadomienie jako przeczytane).
- **▶ Demo Agent** — przycisk start/stop symuluje pracę Coding Agenta w czasie rzeczywistym:
  rosnący postęp, wpisy w dzienniku, prośba o decyzję w połowie prac i automatyczne
  powiadomienie + wersja historii przy gotowym prototypie. Postęp odświeża się na żywo (polling).
- **Karty decyzji** — gdy agent potrzebuje wyboru, klient klika wariant → agent kontynuuje.
- **Wycena** — klient widzi zakres z analizy AI; wiążąca kwota pojawia się dopiero po
  zatwierdzeniu przez właściciela (zielona karta „WYCENA ZATWIERDZONA”) i może ją
  **zaakceptować jednym przyciskiem** → projekt przechodzi do realizacji (status, zadanie,
  wersja w historii, wpis agenta, powiadomienie dla studia).
- **Eksport specyfikacji (.md)** — pełna specyfikacja projektu (analiza, zadania, historia)
  do pobrania z zakładki OVERVIEW.
- **Pliki** — realne pobieranie (serwer generuje plik z zawartością projektu).

### 4. Panel właściciela (admin)
- Statystyki (klienci, projekty, wiadomości, zgłoszenia) + dziennik zdarzeń systemowych.
- Zarządzanie projektami (zmiana statusu → automatyczny postęp).
- Lista klientów, zgłoszenia z formularza kontaktowego.
- Konfiguracja usług (włącz/wyłącz → natychmiastowy efekt na stronie głównej).
- **✦ Upominki** — zamówienia piosenek/grawerów z wariantami i statusami realizacji.
- **🤖 AI Agent** — podgląd i sterowanie demo agentem dla każdego projektu (start/stop, status pracy).
- **Wyceny** — edycja kwoty i notatki oraz zatwierdzanie (klient dostaje powiadomienie).
- **Portfolio** — pełny CRUD wpisów portfolio (tytuł, kategoria, zdjęcie, opis, technologie,
  rezultat, widoczność) → natychmiastowa publikacja na stronie głównej.
- **🔔 Powiadomienia** — nowe zgłoszenia, wiadomości od klientów, nowe projekty.

### 5. Backend (wspólny dla Web i Androida)
Node.js bez zależności zewnętrznych: konta i sesje (tokeny), role i uprawnienia,
projekty, wiadomości, pliki, zadania, historia, wyceny-szkice, zgłoszenia,
rate limiting per IP, audit log. Dane trzymane w `data/db.json`.

### 6. Android (szkielet rozszerzony)
Katalog `android/` zawiera gotowy do otwarcia w Android Studio szkielet aplikacji:
- `MainActivity` — WebView wskazujący na wspólny backend,
- `ApiClient` — pełny kontrakt endpointów REST dla wersji natywnej,
- `NotificationsService` — szkielet powiadomień gotowy pod FCM.
Plan migracji do Jetpack Compose i FCM w `android/README.md`.

---

**Marketing i SEO:**
- Sekcja **OPINIE** (3 karty) i **FAQ** (6 pytań, akordeon) przed formularzem kontaktowym.
- Open Graph / Twitter Card, `robots.txt`, `sitemap.xml`, PWA manifest.

### 7. 🤖 WOJAN.AGENT v0.3 — generator artefaktów
Demo agent nie tylko „udaje pracę” — **naprawdę generuje pliki projektu** (generatory
szablonowe, jawnie oznaczone):
- na starcie: `README.md` + `dokumentacja/specyfikacja.md`,
- w połowie prac: artefakty zależne od dziedziny — **działający prototyp HTML** (web/app),
  `firmware.ino` + schemat (elektronika), `projekt.svg` do lasera (produkcja), scenariusz (AV),
- na koniec: `wersja.json` (manifest).
Pliki widać w zakładce **PLIKI** (do pobrania), a **PREVIEW renderuje prawdziwy
wygenerowany HTML w iframe** (przeglądarka dla web, ramka telefonu dla app).
Przycisk **📦 PAKIET WDROŻENIOWY** pobiera cały kod projektu jednym plikiem.
Istniejące gotowe projekty dostają artefakty automatycznie (backfill przy starcie).

### 8. 💳 Płatności i marketplace
- Pełny cykl biznesowy: **wycena → akceptacja → płatność → realizacja**.
- Po akceptacji wyceny klient wybiera metodę (📱 BLIK / 💳 Karta / 🏦 Przelew) i klika
  „OPŁAĆ” (tryb demonstracyjny) → status `paid`, powiadomienie dla studia,
  **faktura do pobrania**.
- Panel właściciela: zakładka **💳 Płatności** (lista transakcji).
- **MARKETPLACE** — sekcja gotowych produktów (Landing PRO, tabliczka grawerowana,
  jingle) z modalem zamówienia; zamówienia wpadają do panelu właściciela.

### 9d. 🛠 Operacje i moc użytkownika
- **PWA offline** — service worker (`sw.js`): dane żywe zawsze z sieci, assety **network-first**
  (online zawsze świeży kod, cache jako fallback offline), nawigacje z fallbackiem → aplikacja
  instalowalna i odporna na utratę zasięgu. Przy nowej wersji SW strona odświeża się raz sama
  (zabezpieczenie przed pętlą), więc użytkownik zawsze dostaje aktualny kod.
- **💾 Backup danych** — właściciel pobiera pełną bazę jako JSON (przycisk w sidebarze i w Logach).
- **📜 Logi systemowe** — osobna zakładka z audit logiem (logowania, AI, projekty, płatności, backupy).
- **🩺 System** — monitoring platformy: status, uptime, wersja, zużycie pamięci + liczniki zasobów
  (projekty, klienci, utwory, zgłoszenia, płatności, upominki); rozszerzony `/api/health`
  (szczegóły tylko dla właściciela).
- **📊 Raport studia** — pobieralne podsumowanie (Markdown): projekty wg statusu, klienci,
  zgłoszenia, wyceny/płatności, biblioteka radia + lista projektów (`/api/admin/report`).
- **⌘K Paleta komend** — Ctrl+K otwiera wyszukiwarkę widoków (strzałki + Enter), dostępna z każdego miejsca.
- **`/api/health`** — endpoint monitoringu (status + uptime).
- Esc zamyka modale; wszystkie akcje mają stany ładowania i toasty.

### 9c. 🔗 Udostępnianie i wygoda
- **Publiczny link do śledzenia projektu** (`/#/public/:id`) — read-only status z pipeline'em,
  bez danych poufnych (serwer zwraca tylko bezpieczne pola); przycisk **🔗 UDOSTĘPNIJ**
  w panelu projektu kopiuje link do schowka. Link **odświeża się sam co 5 s** —
  współdzielony postęp aktualizuje się na żywo u każdego, kto go otworzy.
- **Szablony startowe w AI Builderze** — 4 gotowe opisy jednym kliknięciem
  (aplikacja, strona, urządzenie + aplikacja, dekoracja laserowa).
- **Wyszukiwarka w galerii** realizacji (filtrowanie po tytule, opisie, technologiach).
- **Wykres transakcji wg metody** (BLIK/karta/przelew) w zakładce Płatności.

### 9b. ⚡ Live updates (SSE) i analityka
- Panel projektu subskrybuje **Server-Sent Events** (`/api/projects/:id/stream`) —
  postęp agenta, wiadomości, decyzje, wyceny i płatności odświeżają się **natychmiast**,
  bez odpytywania (fallback polling na wypadek zerwania; sprzątanie połączeń przy nawigacji).
- Panel właściciela: **wykresy canvas** (projekty wg statusu, zdarzenia systemowe z 14 dni).
- Hero strony: **liczniki na żywo** z `/api/stats/public` (projekty, prototypy, utwory w radiu).
- Czat projektu: **szybkie odpowiedzi** (gotowe prośby o zmiany jednym kliknięciem).
- **WOJAN API v0.3** — pełna dokumentacja endpointów: `/api-docs.html` (link w stopce).

### 9. WOJAN.CORE v0.2 — adaptacyjny rdzeń AI
- Silnik analizy z **uczeniem wag słów kluczowych**: utworzenie projektu z analizy (+0.25)
  i ocena 👍/👎 (+0.15 / −0.20) realnie zmieniają dopasowania dziedzin.
- **Pytania doprecyzowujące** — przy krótkim opisie rdzeń woli dopytać niż zgadywać.
- Pełna obserwowalność: licznik próbek, tabela wag i **dziennik ewolucji** w panelu
  właściciela (zakładka 🧠 Rdzeń AI).
- **Migracje schematu** — stare bazy automatycznie dostają nowe moduły bez utraty danych.
- **Testy automatyczne**: `npm test` — **32 testy** (node:test):
  - 31 testów API — własna instancja serwera na osobnym porcie z tymczasową bazą
    (SSE, publiczne statystyki/linki, backup, logi, health, service worker, dokumentacja),
  - 1 test przeglądarkowy (jsdom, devDependency) — realny przepływ logowania w DOM:
    klient → panel, właściciel → admin, błędne hasło → komunikat bez nawigacji.
- PWA: manifest + ikona (aplikacja instalowalna).

## Bezpieczeństwo (wbudowane w MVP)
- Autoryzacja tokenowa (Bearer), role `client` / `owner`, kontrola dostępu do zasobów.
- Hasła hashowane (SHA-256 + salt aplikacyjny) — do wymiany na bcrypt/argon2 w produkcji.
- Rate limiting (ogólny + osobny, ostrzejszy limit dla `/api/ai/*`).
- Walidacja i przycinanie danych wejściowych, ochrona ścieżek plików (path traversal).
- Audit log zdarzeń (`auth`, `ai`, `projects`, `contact`, `services`).
- Endpointy `/api/agent/*` celowo zwracają **501** — Coding Agent nie ma jeszcze dostępu,
  a jego przyszłe środowisko ma być izolowane (sandbox) i pozbawione dostępu do danych produkcyjnych klientów.

## 🌐 Szybka publikacja (darmowa domena)
- **Render** — `render.yaml` (Blueprint) + przewodnik `deploy/RENDER.md`.
  Darmowy Web Service z adresem `*.onrender.com` i TLS; podmień `BASE_URL` w Androidzie
  i zbuduj APK. Uwaga: darmowy tier usypia po ~15 min i ma ulotny dysk (dane demo
  odradzają się przy starcie — aplikacja seeduje sama).
- **VPS / Docker** — `deploy/README.md` (Docker, systemd, nginx+HTTPS).

## Struktura

```
wojan-studio/
├── server.js              # wspólny backend (auth, projekty, AI, media, admin) + hardening
├── Dockerfile             # obraz produkcyjny (node:20-alpine, user non-root, healthcheck)
├── docker-compose.yml     # wolumen danych + restart policy + healthcheck
├── .dockerignore / .env.example
├── deploy/                # PAKIET PUBLIKACJI
│   ├── README.md          # przewodnik: Docker / systemd / nginx+HTTPS / checklist
│   ├── nginx.conf.example # reverse proxy + TLS + SSE + limity uploadu
│   └── wojan-studio.service  # serwis systemd z hardeningiem
├── data/db.json           # baza (auto-migracje schematu)
├── data/media/            # utwory WOJAN RADIO + artefakty projektów
├── public/                # SPA + PWA
│   ├── manifest.json      # PWA: ikony 192/512/maskable
│   ├── img/icon-*.png     # ikony aplikacji (PWA + Android)
│   ├── sw.js              # service worker (network-first, auto-update)
│   ├── api-docs.html      # dokumentacja WOJAN API
│   └── ...
├── android/               # aplikacja Android (ikony launcher + manifest gotowe)
├── tests/api.test.mjs     # 32 testy (API + przeglądarkowe)
└── docs/ARCHITECTURE.md   # architektura + plan Coding Agenta i rozbudowy
```

## Roadmapa — stan obecny
1. ✅ MVP: strona, usługi, portfolio, formularz, AI Builder, panel projektu, konta, wspólny backend.
2. ✅ Rozszerzenia: powiadomienia, karty decyzji, wyceny (zatwierdzanie + akceptacja przez klienta),
   portfolio jako CMS, pobieranie plików, live-odświeżanie, panel AI Agenta.
3. ✅ WOJAN.AGENT v0.3: agent generuje prawdziwe artefakty (kod prototypów, firmware, SVG),
   działające PREVIEW w iframe, eksport specyfikacji i pakiet wdrożeniowy.
4. ✅ WOJAN RADIO: upload audio/wideo, streaming z Range, tryb stacji, wizualizer widma.
5. ✅ Płatności (BLIK/karta/przelew + faktury), marketplace, usługi specjalne (piosenki/grawery),
   galeria realizacji, FAQ/opinie/SEO/PWA.
6. ✅ Jakość i infra: 32 testy (31 API + przeglądarkowy), migracje schematu, rate limiting, audit log, role i izolacja,
   SSE live updates, wykresy analityczne, publiczne statystyki, dokumentacja WOJAN API.
7. 🔜 Produkcja: podmiana generatorów szablonowych na prawdziwego Coding Agenta w sandboxie
   (`/api/agent/*` — kontrakty gotowe, interfejs bez zmian), natywny Android (Compose + FCM),
   magazyn plików S3, integracja Git i realne płatności.
