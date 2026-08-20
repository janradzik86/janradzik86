# Czarne Wilki Prawdy – Wszyscy Won!

Natywna aplikacja **Android (APK)** oraz **komputer stacjonarny (Linux ELF)** — bez przeglądarki.

Logo husarsko-wilcze jest użyte w oryginale (ekran startowy, nagłówek, ikona). Paleta: czerń / biel / czerwień.

## Gotowe pliki instalacyjne

| Platforma | Plik |
|-----------|------|
| Android | [`dist/CzarneWilkiPrawdy.apk`](dist/CzarneWilkiPrawdy.apk) |
| Linux desktop | [`dist/CzarneWilkiPrawdy`](dist/CzarneWilkiPrawdy) |

### Android
Zainstaluj APK (źródło nieznane / ADB):

```bash
adb install -r dist/CzarneWilkiPrawdy.apk
```

Pakiet: `pl.czarnewilkiprawdy.app`  
minSdk 21, podpis v1+v2.

### Desktop
```bash
chmod +x dist/CzarneWilkiPrawdy
./dist/CzarneWilkiPrawdy
```

Dane lokalne: `~/.czarne_wilki_prawdy/wolf.db`  
Most LAN (sync live): TCP `0.0.0.0:17886` (JSON-lines).

Konto startowe RBAC: `hetman` / `wilki` (role: admin, moderator, operator, guest).

## 22 moduły

1. Most Android ↔ desktop w czasie rzeczywistym  
2. Mikrofon z nasłuchem do ręcznego STOP (bez autostopu)  
3. Biblioteka głosów AI (Hetman, Husaria, Wilczyca, Kronikarz)  
4. Lokalne modele + repozytoria GGUF/Ollama (`~/.czarne_wilki_prawdy/models`)  
5. Przełącznik Sieć / Offline  
6. Czat + menu generatora tekst/obraz/dźwięk/wideo  
7. Planer publikacji  
8. Autopost — `WolfAccessibilityService` (drzewo widoków Androida)  
9. Personalizacja agenta (nazwa, rola, system prompt)  
10. Asystent kodowania  
11. Samonaprawa / iniekcja (desktop: pliki; Android: DexClassLoader)  
12. Komunikator E2E (X25519 + AES-GCM, pokoje grupowe)  
13. Radio społecznościowe ze zsynchronizowaną kolejką  
14. Historia SQLite na urządzeniu  
15. RBAC (Hetman = administrator)  
16. Kolejka moderacji  
17. Alerty `WILKI_ALERT`  
18. Agent komentarzy po publikacji  
19. Tryb bez maski (otwarte modele; twardy zakaz treści przestępczych)  
20. Tożsamość projektu + logo  
21. Dobrowolne wpłaty  
22. Wieloagentowy kontroler jakości (Hetman zatwierdza każdy materiał)

## Źródła

- `desktop/wolf.py` — natywny klient desktop  
- `tools/` — kompilator DEX + pakowacz APK  
- `czarne_wilki/` — projekt Flutter + moduły Kotlin  
- `branding/logo_czarne_wilki.png` — logo oryginalne  

Kompilacja APK (bez Android SDK / Flutter CDN):

```bash
python3 tools/build_apk.py dist/CzarneWilkiPrawdy.apk
```
