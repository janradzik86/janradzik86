# Czarne Wilki Prawdy — oficjalna strona (Wojan)

Statyczna strona zespołu: strona główna, katalog utworów, **Wilcze Radio** grające
wszystkie utwory w pętli, koncerty i kontakt. Zero backendu, zero kosztów hostingu.

Pliki:
```
index.html    struktura strony
style.css     wygląd (ciemny, „wilczy”)
app.js        logika + odtwarzacz radia (YouTube IFrame API)
tracks.json   >>> TU DODAJESZ NOWE UTWORY I KONCERTY <<<
assets/       okładki, hero, logo
```

---

## 1. Jak dodać nowy utwór (30 sekund)

Otwórz `tracks.json` i dopisz nowy wpis **na początku** listy `tracks`:

```json
{
  "id": "nowy-singiel",
  "title": "Nazwa Utworu",
  "year": 2026,
  "type": "singiel",
  "cover": "assets/cover-nowy.jpg",
  "description": "Krótki opis, który pojawi się na stronie i w radiu.",
  "source": "youtube",
  "videoId": "ABCdef12345",
  "spotify": "https://open.spotify.com/track/...",
  "featured": true
}
```

- `videoId` — to, co jest w linku po `youtu.be/` lub `watch?v=`.
  Przykład: `https://youtu.be/**ABCdef12345**` → `"videoId": "ABCdef12345"`.
- `featured: true` — utwór ląduje w wielkim bloku „NAJNOWSZA PREMIERA”.
  Ustaw `false` przy poprzednim, żeby był tylko jeden wyróżniony.
- `cover` — wrzuć kwadratowy JPG do `assets/`. Możesz też użyć miniatury z YT:
  `"cover": "https://i.ytimg.com/vi/ABCdef12345/maxresdefault.jpg"`.
- Każdy utwór z `videoId` **automatycznie trafia do Wilczego Radia**.

Koncerty dodajesz analogicznie w sekcji `concerts`.

Po zapisaniu pliku i wysłaniu na GitHub strona aktualizuje się sama w ~30 sekund.

---

## 2. Radio — jak działa

Utwory odtwarzane są przez ukryty odtwarzacz YouTube (legalnie, z licznikiem
odsłon lecącym na Twój kanał). Po zakończeniu utworu automatycznie startuje
następny, a po ostatnim wraca do pierwszego — **pętla bez końca**.
Jest też przycisk losowania (🔀), następny/poprzedni i klikalna playlista.

> Uwaga przeglądarek: dźwięk startuje dopiero po kliknięciu przez użytkownika
> (blokada autoplay) — dlatego w hero jest przycisk „Włącz radio”.

---

## 3. Wdrożenie — hosting ZA DARMO (Cloudflare Pages)

1. Wejdź na https://dash.cloudflare.com → **Workers & Pages → Create → Pages →
   Connect to Git**.
2. Wybierz repozytorium `janradzik86/janradzik86`, gałąź z tą stroną.
3. Ustawienia builda:
   - Framework preset: **None**
   - Build command: *(puste)*
   - Build output directory: `czarne-wilki-prawdy`
4. **Save and Deploy**. Po chwili masz działający adres `*.pages.dev`.

Alternatywa identycznie prosta: **Netlify** (Add new site → Import from Git →
publish directory `czarne-wilki-prawdy`) albo **GitHub Pages**.

---

## 4. Domena czarnewilkiprawdy.pl

**Zakup** (ok. 10–20 zł pierwszy rok, ~60–90 zł odnowienie):
- OVH.pl, home.pl, nazwa.pl, cyberFolks — lub taniej: **Cloudflare Registrar**
  (cena hurtowa, ale `.pl` bywa niedostępne → wtedy OVH).

Najprostsza ścieżka: kup domenę w **OVH**, a DNS przenieś do Cloudflare.

**Podpięcie do Cloudflare Pages:**
1. W Cloudflare: **Add a site** → `czarnewilkiprawdy.pl` → plan **Free**.
2. Cloudflare pokaże 2 serwery nazw, np. `xxx.ns.cloudflare.com`.
3. W panelu OVH (Domeny → czarnewilkiprawdy.pl → Serwery DNS) wpisz te dwa
   serwery zamiast domyślnych. Propagacja: od 15 min do kilku godzin.
4. Wróć do swojego projektu Pages → **Custom domains → Set up a domain** →
   wpisz `czarnewilkiprawdy.pl`, potem drugi raz `www.czarnewilkiprawdy.pl`.
   Cloudflare doda rekordy i **certyfikat SSL sam** (HTTPS gratis).

Gotowe — strona działa pod https://czarnewilkiprawdy.pl.

**E-mail kontakt@czarnewilkiprawdy.pl:** w Cloudflare → **Email → Email Routing**
→ przekierowanie na Twój Gmail. Darmowe.

---

## 5. Koszty

| Pozycja | Koszt |
|---|---|
| Hosting (Cloudflare Pages) | 0 zł |
| SSL / HTTPS | 0 zł |
| E-mail przekierowanie | 0 zł |
| Domena .pl | ~15 zł 1. rok, potem ~70 zł/rok |

**Razem: tylko domena.**

---

## 6. Podgląd lokalny

```bash
cd czarne-wilki-prawdy
python3 -m http.server 8080
# http://localhost:8080
```

## 7. Do podmiany przed startem

- `tracks.json` — prawdziwe `videoId` (teraz są placeholdery).
- `index.html` sekcja `.socials` — linki do YouTube/Spotify/FB/IG/TikTok.
- `assets/` — prawdziwe zdjęcia zespołu i okładki (obecne są poglądowe, AI).
