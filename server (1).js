#!/usr/bin/env node
/* ============================================================================
   WOJAN STUDIO — wspólny backend MVP (Web + Android + AI Agent)
   Zero zależności zewnętrznych (czysty Node.js).
   Moduły: auth (role), projekty, wiadomości, pliki, zadania, historia,
           AI Project Builder (silnik analizy), wyceny (szkic), kontakt,
           panel właściciela, rate limiting, audit log.
   Architektura przygotowana pod podłączenie prawdziwego Coding Agenta
   (patrz docs/ARCHITECTURE.md) — endpointy /api/agent/* są zarezerwowane.
   ========================================================================== */
'use strict';
const http = require('http');
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const AGENT = require('./server/agent.js');

const PORT = process.env.PORT || 3000;
const HOST = process.env.HOST || '0.0.0.0';
const PROD = process.env.NODE_ENV === 'production';
const ROOT = path.join(__dirname, 'public');
const DB_PATH = process.env.DB_PATH || path.join(__dirname, 'data', 'db.json');
const MEDIA_DIR = path.join(__dirname, 'data', 'media');
const CORE_VERSION = '0.2';
const APP_VERSION = '1.0.0';

const MEDIA_MIME = {
  '.mp3': 'audio/mpeg', '.wav': 'audio/wav', '.ogg': 'audio/ogg', '.oga': 'audio/ogg',
  '.m4a': 'audio/mp4', '.aac': 'audio/aac', '.flac': 'audio/flac',
  '.mp4': 'video/mp4', '.webm': 'video/webm', '.mov': 'video/quicktime', '.mkv': 'video/x-matroska',
};
const MEDIA_VIDEO_EXT = ['.mp4', '.webm', '.mov', '.mkv'];
const MEDIA_MAX = 90 * 1024 * 1024; // 90 MB
const PROJECT_DIR = path.join(__dirname, 'data', 'projects');
const escHtml = (s) => String(s == null ? '' : s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const humanSize = (b) => b > 1048576 ? (b / 1048576).toFixed(1) + ' MB' : b > 1024 ? (b / 1024).toFixed(0) + ' KB' : b + ' B';

const now = () => new Date().toISOString();
const uid = () => crypto.randomBytes(8).toString('hex');
const sha = (s) => crypto.createHash('sha256').update('wojan::' + s).digest('hex');

/* ---------------------------------------------------------------- DB ---- */
let db;
function loadDb() {
  try { db = JSON.parse(fs.readFileSync(DB_PATH, 'utf8')); } catch (e) { db = seed(); }
  migrate();
  saveDb();
}
/* Ewolucyjna migracja schematu — stare bazy dostają nowe moduły bez utraty danych. */
function migrate() {
  if (!db.knowledge) {
    db.knowledge = {
      version: CORE_VERSION, samples: 0, weights: {},
      log: [{ id: uid(), ts: now(), text: 'Migracja: zainicjowano rdzeń WOJAN.CORE v' + CORE_VERSION + ' w istniejącej bazie.' }],
    };
  }
  db.projects.forEach((p) => { if (!p.decisions) p.decisions = []; });
  db.quotes.forEach((q) => {
    if (q.status !== 'approved' && q.status !== 'draft') q.status = 'draft';
    if (q.amount === undefined) q.amount = '';
    if (q.note === undefined) q.note = '';
  });
  if (!db.notifications) db.notifications = [];
  if (!db.portfolio) db.portfolio = [];
  if (!db.giftOrders) db.giftOrders = [];
  if (!db.media) db.media = [];
  db.media.forEach((m) => { if (m.plays === undefined) m.plays = 0; if (!m.likedBy) m.likedBy = []; if (m.likes === undefined) m.likes = m.likedBy.length; });
  if (!db.payments) db.payments = [];
  if (!db.services.some((s) => s.id === 'gift')) db.services.push({ id: 'gift', name: 'Piosenki & Upominki', enabled: true });
}
function saveDb() {
  fs.mkdirSync(path.dirname(DB_PATH), { recursive: true });
  fs.writeFileSync(DB_PATH, JSON.stringify(db, null, 2));
}

function seed() {
  const t = Date.now();
  const iso = (off) => new Date(t - off * 86400000).toISOString();
  const wojan = { id: 'u-wojan', name: 'Wojan', email: 'wojan@wojan.studio', pass: sha('wojan123'), role: 'owner', createdAt: iso(60) };
  const demo = { id: 'u-demo', name: 'Jan Kowalski', email: 'demo@wojan.studio', pass: sha('demo123'), role: 'client', createdAt: iso(30) };

  const p1 = {
    id: 'p-mag', ownerId: demo.id, name: 'Aplikacja magazynowa',
    description: 'Aplikacja dla firmy, która pozwala pracownikom dodawać zlecenia, robić zdjęcia i oznaczać ich status.',
    domain: 'app', status: 'prototype', progress: 85, level: 'Średni', modules: 8, mvp: 5,
    decisions: [],
    createdAt: iso(21), updatedAt: iso(0.2),
    analysis: {
      goal: 'Usprawnienie obsługi zleceń magazynowych: szybkie dodawanie zleceń, dokumentacja zdjęciowa i czytelne statusy dla zespołu.',
      users: ['Pracownicy magazynu', 'Kierownik zmiany', 'Administrator'],
      features: ['Logowanie i konta użytkowników', 'Lista zleceń z filtrami', 'Dodawanie zlecenia ze zdjęciem', 'Statusy: nowe / w trakcie / gotowe', 'Powiadomienia o zmianach'],
      screens: ['Ekran logowania', 'Dashboard', 'Lista zleceń', 'Szczegóły zlecenia', 'Formularz dodawania', 'Ustawienia'],
      data: ['Zlecenia', 'Zdjęcia i załączniki', 'Użytkownicy i role', 'Historia statusów'],
      integrations: ['Aparat i galeria', 'Powiadomienia push', 'Tryb offline'],
      risks: ['Praca offline w hali — synchronizacja', 'Zakres może urosnąć — zaczynamy od MVP'],
      tech: ['Flutter / React Native', 'Node.js + REST API', 'Baza danych w chmurze'],
    },
  };
  const p2 = {
    id: 'p-web', ownerId: demo.id, name: 'Strona firmy',
    description: 'Nowoczesna strona firmowa z ofertą, realizacjami i formularzem wyceny.',
    domain: 'web', status: 'agent', progress: 55, level: 'Mały', modules: 5, mvp: 4,
    decisions: [{ id: 'd-palety', question: 'Agent prosi o decyzję: którą paletę kolorów wybrać dla strony firmy?', options: ['A: grafit + neonowy cyan', 'B: jasny minimalizm'], status: 'open', answer: null, ts: iso(0.4) }],
    createdAt: iso(9), updatedAt: iso(0.5),
    analysis: {
      goal: 'Zbudowanie wizerunku firmy w internecie i zbieranie zapytań ofertowych.',
      users: ['Potencjalni klienci', 'Kontrahenci'],
      features: ['Strona główna z hero', 'Oferta i usługi', 'Portfolio realizacji', 'Formularz wyceny'],
      screens: ['Strona główna', 'Oferta', 'Portfolio', 'Kontakt'],
      data: ['Treści i zdjęcia', 'Zapytania z formularza'],
      integrations: ['Analityka', 'SEO'],
      risks: ['Kompletowanie materiałów zdjęciowych'],
      tech: ['Nowoczesny frontend', 'CMS dla treści'],
    },
  };
  const p3 = {
    id: 'p-ctrl', ownerId: demo.id, name: 'System sterowania',
    description: 'Chcę urządzenie, które automatycznie podlewa rośliny i mogę sterować nim telefonem.',
    domain: 'electronics', status: 'analysis', progress: 20, level: 'Duży', modules: 9, mvp: 5,
    decisions: [],
    createdAt: iso(2), updatedAt: iso(0.1),
    analysis: {
      goal: 'Automatyczne podlewanie roślin sterowane z aplikacji mobilnej.',
      users: ['Właściciel domu / ogrodu'],
      features: ['Czujniki wilgotności', 'Harmonogram podlewania', 'Sterowanie pompą', 'Aplikacja mobilna', 'Powiadomienia'],
      screens: ['Panel główny', 'Harmonogram', 'Historia podlewania', 'Ustawienia'],
      data: ['Pomiary z czujników', 'Harmonogramy', 'Historia zdarzeń'],
      integrations: ['Wi-Fi / Bluetooth', 'Aplikacja Android'],
      risks: ['Dostępność komponentów', 'Zasilanie i szczelność obudowy'],
      tech: ['Mikrokontroler (ESP32)', 'Czujniki + pompa', 'Aplikacja mobilna'],
    },
  };

  const mkMsg = (projectId, kind, authorName, text, off) =>
    ({ id: uid(), projectId, kind, author: authorName, text, meta: null, ts: iso(off) });

  return {
    users: [wojan, demo],
    sessions: {},
    services: [
      { id: 'metal', name: 'Metal & Konstrukcje', enabled: true },
      { id: 'laser', name: 'Laser & Produkcja', enabled: true },
      { id: 'tech', name: 'Technologia', enabled: true },
      { id: 'electronics', name: 'Elektronika', enabled: true },
      { id: 'design', name: 'Projektowanie', enabled: true },
      { id: 'brand', name: 'Marka & Reklama', enabled: true },
      { id: 'av', name: 'Audio & Wideo', enabled: true },
      { id: 'gift', name: 'Piosenki & Upominki', enabled: true },
    ],
    projects: [p1, p2, p3],
    messages: [
      mkMsg('p-mag', 'agent', 'AI Agent', 'Analiza wymagań zakończona. Wykryłem 8 modułów. Proponuję zakres MVP: 5 funkcji kluczowych.', 20),
      mkMsg('p-mag', 'wojan', 'Wojan', 'Akceptuję zakres MVP. Zaczynamy od listy zleceń i zdjęć.', 19),
      mkMsg('p-mag', 'agent', 'AI Agent', 'Przygotowałem interfejs listy zleceń oraz formularz dodawania ze zdjęciem.', 6),
      mkMsg('p-mag', 'client', 'Jan Kowalski', 'Wygląda świetnie! Czy możemy dodać filtrowanie po statusie?', 5),
      mkMsg('p-mag', 'agent', 'AI Agent', 'Prototyp v0.3 gotowy. Dodałem filtrowanie po statusie oraz widok szczegółów zlecenia.', 0.3),
      mkMsg('p-web', 'agent', 'AI Agent', 'Rozpocząłem generowanie sekcji hero i siatki portfolio.', 1),
      mkMsg('p-web', 'wojan', 'Wojan', 'Dodałem zdjęcia realizacji do plików projektu.', 0.5),
      mkMsg('p-ctrl', 'agent', 'AI Agent', 'Rozbijam pomysł na warstwy: hardware, software, produkcja i projekt. Pełna analiza wkrótce.', 0.2),
    ],
    tasks: [
      { id: uid(), projectId: 'p-mag', title: 'Testy listy zleceń', done: true },
      { id: uid(), projectId: 'p-mag', title: 'Eksport zdjęć do galerii zlecenia', done: false },
      { id: uid(), projectId: 'p-mag', title: 'Powiadomienia push o zmianie statusu', done: false },
      { id: uid(), projectId: 'p-web', title: 'Makieta strony głównej', done: true },
      { id: uid(), projectId: 'p-web', title: 'Sekcja portfolio', done: false },
      { id: uid(), projectId: 'p-ctrl', title: 'Dobór czujników wilgotności', done: false },
    ],
    files: [
      { id: uid(), projectId: 'p-mag', name: 'makiety-v0.3.fig', size: '4.2 MB', kind: 'design', ts: iso(2) },
      { id: uid(), projectId: 'p-mag', name: 'specyfikacja-api.md', size: '38 KB', kind: 'doc', ts: iso(12) },
      { id: uid(), projectId: 'p-mag', name: 'logo-firmy.png', size: '610 KB', kind: 'image', ts: iso(15) },
      { id: uid(), projectId: 'p-web', name: 'zdjecia-realizacji.zip', size: '22 MB', kind: 'archive', ts: iso(1) },
      { id: uid(), projectId: 'p-ctrl', name: 'lista-komponentow.csv', size: '6 KB', kind: 'doc', ts: iso(1) },
    ],
    history: [
      { id: uid(), projectId: 'p-mag', version: 'v0.1', note: 'Analiza wymagań i architektura', ts: iso(20) },
      { id: uid(), projectId: 'p-mag', version: 'v0.2', note: 'Makiety interfejsu (lista + formularz)', ts: iso(9) },
      { id: uid(), projectId: 'p-mag', version: 'v0.3', note: 'Prototyp MVP: filtrowanie, szczegóły, zdjęcia', ts: iso(0.3) },
      { id: uid(), projectId: 'p-web', version: 'v0.1', note: 'Analiza i struktura treści', ts: iso(8) },
      { id: uid(), projectId: 'p-web', version: 'v0.2', note: 'Sekcja hero + nawigacja', ts: iso(1) },
      { id: uid(), projectId: 'p-ctrl', version: 'v0.1', note: 'Analiza pomysłu (tryb: mam tylko pomysł)', ts: iso(1) },
    ],
    activity: [
      { id: uid(), projectId: 'p-mag', text: 'Agent zakończył etap: Przygotowanie interfejsu', ts: iso(0.3) },
      { id: uid(), projectId: 'p-mag', text: 'Prototyp v0.3 oznaczony jako gotowy', ts: iso(0.25) },
      { id: uid(), projectId: 'p-web', text: 'Agent pracuje: sekcja portfolio', ts: iso(0.5) },
      { id: uid(), projectId: 'p-ctrl', text: 'Rozpoczęto analizę pomysłu', ts: iso(1) },
    ],
    contacts: [],
    notifications: [
      { id: uid(), userId: 'u-demo', kind: 'success', text: 'Twój prototyp jest gotowy. („Aplikacja magazynowa”)', ref: 'p-mag', read: false, ts: iso(0.3) },
      { id: uid(), userId: 'u-demo', kind: 'warn', text: 'Agent wykrył problem wymagający decyzji („Strona firmy”).', ref: 'p-web', read: false, ts: iso(0.4) },
      { id: uid(), userId: 'u-demo', kind: 'info', text: 'Wojan odpowiedział na wiadomość w projekcie „Aplikacja magazynowa”.', ref: 'p-mag', read: true, ts: iso(0.5) },
      { id: uid(), userId: 'u-wojan', kind: 'info', text: 'System gotowy. Wczytano projekty demonstracyjne.', ref: null, read: true, ts: iso(1) },
    ],
    portfolio: [
      { id: 'pf-1', img: 'img/p1.jpg', cat: 'LASER & PRODUKCJA', title: 'Ażurowe panele LED dla klubu', desc: 'Seria 24 personalizowanych paneli dekoracyjnych wycinanych laserowo ze stali, z podświetleniem LED.', tech: ['Laser CNC', 'Stal 2 mm', 'Projekt wektorowy', 'LED'], result: 'Realizacja w 9 dni, pełna personalizacja wzorów.', enabled: true },
      { id: 'pf-2', img: 'img/p2.jpg', cat: 'TECHNOLOGIA', title: 'Aplikacja magazynowa', desc: 'Aplikacja dla zespołu magazynu: zlecenia, zdjęcia i statusy w czasie rzeczywistym, działa offline.', tech: ['Flutter', 'Node.js', 'Offline-first', 'Push'], result: '−40% czasu obsługi zleceń w pierwszym miesiącu.', enabled: true },
      { id: 'pf-3', img: 'img/p3.jpg', cat: 'ELEKTRONIKA', title: 'Sterownik nawadniania IoT', desc: 'Urządzenie z czujnikami wilgotności i sterowaniem pompą, zarządzane z aplikacji mobilnej.', tech: ['ESP32', 'Czujniki', 'Aplikacja Android', 'Obudowa 3D'], result: 'Prototyp działający, przygotowany do serii.', enabled: true },
      { id: 'pf-4', img: 'img/p4.jpg', cat: 'METAL & KONSTRUKCJE', title: 'Konstrukcja sceny mobilnej', desc: 'Spawana, skręcana konstrukcja stalowa sceny eventowej — projekt, wykonanie i montaż.', tech: ['Projekt 3D', 'Spawanie MIG', 'Stal S355'], result: 'Konstrukcja przenośna, montaż w 2 osoby.', enabled: true },
      { id: 'pf-5', img: 'img/p5.jpg', cat: 'PROJEKTOWANIE', title: 'Rebranding marki technologicznej', desc: 'Logo, identyfikacja wizualna i materiały firmowe dla firmy z branży automatyki.', tech: ['Logo', 'Brand book', 'Druk', 'Social kit'], result: 'Spójna marka wdrożona w 3 tygodnie.', enabled: true },
      { id: 'pf-6', img: 'img/p6.jpg', cat: 'AUDIO & WIDEO', title: 'Kampania wideo produktu', desc: 'Scenariusz, zdjęcia, montaż i oprawa muzyczna — seria spotów pod social media i WWW.', tech: ['Wideo 4K', 'Montaż', 'Muzyka', 'TikTok/Reels'], result: '12 materiałów gotowych do publikacji.', enabled: true },
    ],
    quotes: [
      { id: uid(), projectId: 'p-mag', scope: 'Projekt: aplikacja mobilna • Zakres: średni • Moduły: 8', status: 'approved', amount: '24 000 – 32 000 zł', note: 'Wycena dla zakresu MVP (5 funkcji).', ts: iso(10) },
      { id: uid(), projectId: 'p-ctrl', scope: 'Projekt: urządzenie IoT • Zakres: duży • Moduły: 9', status: 'draft', amount: '', note: '', ts: iso(0.5) },
      { id: uid(), projectId: 'p-web', scope: 'Projekt: strona internetowa • Zakres: mały • Moduły: 5', status: 'draft', amount: '', note: '', ts: iso(8) },
    ],
    events: [],
  };
}

/* --------------------------------------------------------- AI ENGINE ---- */
const DOMAIN_DEFS = {
  app: {
    label: 'Aplikacja', kw: ['aplikacj', 'app', 'mobile', 'mobiln', 'android', 'ios', 'smartfon', 'telefon'],
    features: ['Logowanie i konta użytkowników', 'Panel główny z listą elementów', 'Dodawanie i edycja wpisów', 'Zdjęcia i załączniki', 'Statusy i oznaczenia', 'Powiadomienia'],
    screens: ['Ekran logowania', 'Dashboard', 'Lista + filtry', 'Szczegóły elementu', 'Formularz dodawania', 'Ustawienia'],
    data: ['Użytkownicy i role', 'Wpisy / zlecenia', 'Zdjęcia i pliki', 'Statusy i historia zmian'],
    integrations: ['Powiadomienia push', 'Aparat i galeria', 'Tryb offline (synchronizacja)'],
    tech: ['Flutter / React Native', 'Node.js + REST API', 'Baza danych w chmurze'],
  },
  web: {
    label: 'Strona / Web', kw: ['stron', 'www', 'witryn', 'sklep', 'e-commerce', 'landing', 'serwis', 'blog', 'program', 'system', 'oprogramowan'],
    features: ['Responsywna strona główna', 'Sekcja oferty / usług', 'Portfolio lub katalog', 'Formularz kontaktowy / wyceny', 'Panel administracyjny treści'],
    screens: ['Strona główna', 'Oferta', 'Portfolio', 'Kontakt', 'Podstrony informacyjne'],
    data: ['Treści i zdjęcia', 'Zapytania z formularzy'],
    integrations: ['Analityka', 'SEO', 'Newsletter'],
    tech: ['Nowoczesny frontend', 'Lekki backend / CMS', 'Hosting + domena'],
  },
  electronics: {
    label: 'Elektronika', kw: ['elektron', 'czujnik', 'urz', 'sterowan', 'iot', 'arduino', 'esp32', 'mikrokontroler', 'pomp', 'silnik', 'podlewa', 'led', 'robot', 'automatyz'],
    features: ['Czujniki i pomiar danych', 'Sterowanie wyjściami (pompa / silnik / LED)', 'Harmonogramy i automatyka', 'Komunikacja bezprzewodowa', 'Aplikacja / panel sterowania'],
    screens: ['Panel główny urządzenia', 'Harmonogram', 'Historia zdarzeń', 'Ustawienia'],
    data: ['Pomiary z czujników', 'Harmonogramy', 'Log zdarzeń'],
    integrations: ['Wi-Fi / Bluetooth', 'Aplikacja mobilna', 'Chmura (opcjonalnie)'],
    tech: ['Mikrokontroler (np. ESP32)', 'Czujniki + elementy wykonawcze', 'Zasilanie i obudowa'],
  },
  laser: {
    label: 'Laser & Produkcja', kw: ['laser', 'grawer', 'wycin', 'cięc', 'ciec', 'tabliczk', 'dekoracj', 'gadżet', 'gadget', 'personaliz'],
    features: ['Projekt wektorowy do wycinania', 'Grawer / cięcie laserowe', 'Personalizacja (napisy, logotypy)', 'Seria produktów lub pojedyncze sztuki'],
    screens: ['Wizualizacja projektu', 'Podgląd wymiarów'],
    data: ['Pliki wektorowe', 'Parametry materiału'],
    integrations: ['Produkcja w warsztacie'],
    tech: ['Projekt CAD / wektorowy', 'Laser CNC', 'Materiał: drewno / pleksi / metal'],
  },
  metal: {
    label: 'Metal & Konstrukcje', kw: ['metal', /\bstal/, 'konstrukcj', 'spaw', 'ślusar', 'slusar', 'profil', /\bram/, 'bram', 'stalow'],
    features: ['Projekt konstrukcji', 'Dobór materiałów i przekrojów', 'Spawanie i montaż', 'Zabezpieczenie antykorozyekt konstrukcji', 'Dobór materiałów i przekrojów', 'Spawanie i montaż', 'Zabezpieczenie antykorozyjne', 'Prototyp / seria'],
    screens: ['Wizualizacja 3D', 'Rysunek techniczny'],
    data: ['Rysunki techniczne', 'Specyfikacja materiałowa'],
    integrations: ['Produkcja w warsztacie', 'Montaż u klienta'],
    tech: ['Projektowanie konstrukcji', 'Spawalnictwo', 'Obróbka metalu'],
  },
  design: {
    label: 'Projektowanie', kw: [/(?:logo|logotyp)(?!wa)/, 'branding', 'grafik', 'identyfikacj', 'wizualizacj', 'projekt produkt', 'plakat', 'ulotk'],
    features: ['Logotyp i znaki', 'Paleta kolorów i typografia', 'Materiały firmowe', 'Wizualizacje zastosowań'],
    screens: ['Prezentacja koncepcji', 'Księga znaku'],
    data: ['Pliki źródłowe', 'Wersje logotypu'],
    integrations: ['Druk / produkcja'],
    tech: ['Projektowanie graficzne', 'Przygotowanie do druku i entacja koncepcji', 'Księga znaku'],
    data: ['Pliki źródłowe', 'Wersje logotypu'],
    integrations: ['Druk / produkcja'],
    tech: ['Projektowanie graficzne', 'Przygotowanie do druku i laserów'],
  },
  media: {
    label: 'Marka & AV', kw: ['reklam', 'mark', 'social', 'tiktok', 'wideo', 'video', 'audio', 'muzyk', 'montaż', 'montaz', 'kampani', 'film', 'spot', 'rolk'],
    features: ['Scenariusz i koncepcja', 'Nagrania / produkcja', 'Montaż i postprodukcja', 'Wersje pod social media', 'Oprawa muzyczna'],
    screens: ['Storyboard', 'Podgląd montażu'],
    data: ['Materiały źródłowe', 'Gotowe pliki wideo / audio'],
    integrations: ['Publikacja w social media'],
    tech: ['Produkcja audio/wideo', 'Motion design'],
  },
};
const OTHER_DEF = {
  label: 'Pomysł do doprecyzowania', kw: [],
  features: ['Doprecyzowanie celu produktu', 'Zdefiniowanie użytkowników', 'Makiety / szkice koncepcji', 'Plan MVP'],
  screens: ['Szkic rozwiązania'], data: ['Notatki i ustalenia'], integrations: [],
  tech: ['Dobierzemy po analizie'],
};

const EXTRA_MODULES = [
  { kw: ['logowan', 'kont', 'auth', 'google'], feat: 'Logowanie i konta użytkowników' },
  { kw: ['płatnoś', 'platnos', 'pлат', 'abonament', 'subskrypcj'], feat: 'Płatności online' },
  { kw: ['zdjęc', 'zdjec', 'foto', 'aparat', 'kamer'], feat: 'Zdjęcia / multimedia' },
  { kw: ['raport', 'statystyk', 'wykres', 'analityk'], feat: 'Raporty i statystyki' },
  { kw: ['map', 'lokaliz', 'gps'], feat: 'Mapy i lokalizacja' },
  { kw: ['powiadom', 'notif', 'sms', 'e-mail', 'mail'], feat: 'Powiadomienia' },
  { kw: ['eksport', 'pdf', 'csv'], feat: 'Eksport danych' },
];

function matchDomain(d, t) {
  return d.kw.filter((w) => (w instanceof RegExp ? w.test(t) : t.includes(w)));
}
function kwLabel(w) { return w instanceof RegExp ? String(w.source).slice(0, 18) : w; }

function analyzeDescription(text, ideaMode, weights) {
  const t = (text || '').toLowerCase();
  const W = weights || {};
  const found = [];
  for (const [key, d] of Object.entries(DOMAIN_DEFS)) {
    const hits = matchDomain(d, t);
    if (hits.length) found.push({ key, d, hits });
  }
  if (!found.length) found.push({ key: ideaMode ? 'electronics' : 'web', d: OTHER_DEF, hits: [] });

  const extras = EXTRA_MODULES.filter((e) => e.kw.some((w) => t.includes(w))).map((e) => e.feat);

  const features = [...new Set([...found.flatMap((f) => f.d.features), ...extras])];
  const users = [];
  if (t.includes('pracownik')) users.push('Pracownicy firmy');
  if (t.includes('klient')) users.push('Klienci');
  if (t.includes('firma') || t.includes('zespół') || t.includes('zespol')) users.push('Zespół firmy');
  if (t.includes('użytkownik') || t.includes('uzytkownik')) users.push('Użytkownicy końcowi');
  if (!users.length) users.push('Użytkownicy końcowi', 'Administrator / właściciel');

  const firstSentence = (text || '').trim().split(/[.!?]/)[0].slice(0, 180);
  const goal = firstSentence
    ? `Zrealizowanie pomysłu: „${firstSentence}” — od analizy, przez prototyp, po gotowy produkt.`
    : 'Przekształcenie opisanego pomysłu w działający produkt.';

  const risks = ['Zakres może urosnąć — zaczynamy od MVP i iterujemy'];
  if (found.some((f) => f.key === 'electronics')) risks.push('Dostępność komponentów elektronicznych', 'Zasilanie, obudowa i bezpieczeństwo urządzenia');
  if (found.some((f) => f.key === 'metal')) risks.push('Tolerancje wykonania i montażu');
  if (found.some((f) => f.key === 'web' || f.key === 'app')) risks.push('Kompletowanie treści i materiałów', 'Migracja danych (jeśli dotyczy)');
  if (risks.length < 3) risks.push('Ustalenie priorytetów funkcji z właścicielem produktu');

  const hitScore = found.reduce((s, f) => s + f.hits.reduce((x, w) => x + 1 + (W[kwLabel(w)] || 0), 0), 0);
  const score = hitScore + extras.length + (t.length > 350 ? 1 : 0) + (t.length > 800 ? 1 : 0);
  const level = score <= 3 ? 'Mały' : score <= 7 ? 'Średni' : 'Duży';
  const modules = Math.min(14, 3 + found.length * 2 + extras.length + (ideaMode ? 1 : 0));
  const mvp = features.slice(0, 5);

  const breakdown = {
    hardware: found.some((f) => ['electronics', 'metal', 'laser'].includes(f.key))
      ? [...new Set(found.filter((f) => ['electronics', 'metal', 'laser'].includes(f.key)).flatMap((f) => f.d.features))].slice(0, 5)
      : ['(brak warstwy sprzętowej w tym pomyśle)'],
    software: found.some((f) => ['app', 'web', 'electronics'].includes(f.key))
      ? [...new Set(found.filter((f) => ['app', 'web', 'electronics'].includes(f.key)).flatMap((f) => f.d.features))].slice(0, 5)
      : ['Aplikacja lub strona wspierająca produkt'],
    production: found.some((f) => ['laser', 'metal', 'design'].includes(f.key))
      ? ['Elementy wycinane laserowo', 'Konstrukcja / montaż', 'Wykończenie i personalizacja']
      : ['Obudowa / elementy fizyczne (jeśli potrzebne)', 'Druk i personalizacja materiałów'],
    design: found.some((f) => ['design', 'media'].includes(f.key))
      ? [...new Set(found.filter((f) => ['design', 'media'].includes(f.key)).flatMap((f) => f.d.features))].slice(0, 5)
      : ['Identyfikacja wizualna produktu', 'Grafiki i materiały promocyjne'],
  };

  return {
    goal,
    users,
    features,
    screens: [...new Set(found.flatMap((f) => f.d.screens))].slice(0, 8),
    requirements: [
      'Opis funkcji w języku biznesowym (bez żargonu technicznego)',
      'Dostęp z telefonu i komputera',
      'Bezpieczne logowanie i ochrona danych',
      'Możliwość rozbudowy w przyszłości',
    ],
    data: [...new Set(found.flatMap((f) => f.d.data))],
    integrations: [...new Set(found.flatMap((f) => f.d.integrations))],
    risks,
    tech: [...new Set(found.flatMap((f) => f.d.tech))],
    mvp,
    domains: found.map((f) => ({ key: f.key, label: f.d.label, matched: f.hits.map(kwLabel) })),
    level, modules, mvpCount: mvp.length,
    time: 'do ustalenia',
    pricing: 'Wycenę przygotuje Wojan Studio (bez automatycznych, wiążących cen)',
    breakdown,
    ideaMode: !!ideaMode,
  };
}

function proposeChange(text) {
  const t = (text || '').toLowerCase();
  const map = [
    { kw: ['logowan', 'google', 'auth', 'sesj', 'kont'], adds: ['Logowanie użytkownika', 'Konto użytkownika', 'Obsługa sesji', 'Ekran logowania'] },
    { kw: ['płatnoś', 'platnos', 'abonament'], adds: ['Bramka płatności', 'Historia transakcji', 'Panel rozliczeń'] },
    { kw: ['powiadom', 'notif', 'sms'], adds: ['Powiadomienia push', 'Konfiguracja powiadomień'] },
    { kw: ['raport', 'statystyk', 'eksport', 'pdf', 'csv'], adds: ['Moduł raportów', 'Eksport danych (PDF/CSV)'] },
    { kw: ['map', 'gps', 'lokaliz'], adds: ['Widok mapy', 'Zapis lokalizacji'] },
    { kw: ['zdjęc', 'zdjec', 'foto', 'kamer'], adds: ['Przechwytywanie zdjęć', 'Galeria w projekcie'] },
    { kw: ['ciemny', 'dark'], adds: ['Ciemny motyw interfejsu'] },
    { kw: ['język', 'jezyk', 'angielsk', 'en'], adds: ['Wersja wielojęzyczna'] },
  ];
  for (const m of map) if (m.kw.some((w) => t.includes(w))) return { title: 'Zmiana projektu', adds: m.adds };
  return {
    title: 'Zmiana projektu',
    adds: ['Analiza nowego wymagania', 'Aktualizacja specyfikacji', 'Nowy element funkcjonalny', 'Aktualizacja harmonogramu'],
  };
}

/* Pytania doprecyzowujące — rdzeń woli dopytać niż zgadywać. */
function followUpQuestions(text) {
  const t = (text || '').toLowerCase();
  const qs = [];
  if (!/(użytkownik|uzytkownik|pracownik|klient|firma|zespół|zespol|dla kogo|dla mnie)/.test(t)) qs.push('Dla kogo ma być ten produkt? (klienci, pracownicy, użytek własny)');
  if (t.length < 90) qs.push('Opisz jedną konkretną scenę: kto i co robi z tym produktem?');
  if (!/(telefon|komputer|stron|aplikacj|urz|browser|przegl)/.test(t)) qs.push('Gdzie ma działać: aplikacja na telefon, strona w przeglądarce, a może urządzenie fizyczne?');
  if (!/(bud|koszt|termin|zł|pln)/.test(t)) qs.push('Czy masz orientacyjny budżet lub termin? (opcjonalnie)');
  return qs.slice(0, 3);
}

/* ------------------------- WOJAN.AGENT v0.3 — generator artefaktów ------ */
/* Agent tworzy prawdziwe pliki projektu (kod prototypu, firmware, dokumenty).
   To wciąż generator szablonowy — ale artefakty są realne: do pobrania,
   do obejrzenia w PREVIEW i do zabrania w pakiecie wdrożeniowym. */
function writeArtifact(proj, relPath, content, kind) {
  try {
    fs.mkdirSync(path.join(PROJECT_DIR, proj.id, path.dirname(relPath)), { recursive: true });
    fs.writeFileSync(path.join(PROJECT_DIR, proj.id, relPath), content);
    if (!db.files.some((f) => f.projectId === proj.id && f.name === relPath)) {
      db.files.push({ id: uid(), projectId: proj.id, name: relPath, size: humanSize(Buffer.byteLength(content)), kind, disk: relPath, generated: true, ts: now() });
      return true;
    }
  } catch (e) {}
  return false;
}
function hasBuildArtifacts(proj) {
  return db.files.some((f) => f.projectId === proj.id && /^(prototyp|firmware|produkcja)\//.test(f.name));
}
function genBaseDocs(proj) {
  const a = proj.analysis || {};
  const list = (t, arr) => arr && arr.length ? '\n## ' + t + '\n' + arr.map((x) => '- ' + x).join('\n') + '\n' : '';
  let spec = '# SPECYFIKACJA — ' + proj.name + '\n\n> ' + (proj.description || '') + '\n\nPoziom: ' + proj.level + ' • Moduły: ' + proj.modules + ' • MVP: ' + proj.mvp + ' funkcji\n';
  if (a.goal) spec += '\n## CEL\n' + a.goal + '\n';
  spec += list('UŻYTKOWNICY', a.users) + list('FUNKCJE', a.features) + list('EKRANY', a.screens) + list('WYMAGANIA', a.requirements) + list('DANE', a.data) + list('INTEGRACJE', a.integrations) + list('POTENCJALNE PROBLEMY', a.risks) + list('SUGEROWANE TECHNOLOGIE', a.tech) + list('ZAKRES MVP', a.mvp);
  spec += '\n---\nWojan Studio • WOJAN.AGENT v0.3 • ' + now() + '\n';
  writeArtifact(proj, 'dokumentacja/specyfikacja.md', spec, 'doc');
  const readme = '# ' + proj.name + '\n\n> ' + (proj.description || '') + '\n\n## Status\n' + (STATUS_LABEL[proj.status] || proj.status) + ' (' + proj.progress + '%)\n\n## Struktura projektu\n- `dokumentacja/` — specyfikacja i analiza\n- `prototyp/` — działający podgląd prototypu (HTML)\n- `firmware/` lub `produkcja/` — artefakty techniczne\n- `wersja.json` — manifest wersji\n\n---\nWygenerowano przez WOJAN.AGENT v0.3 (tryb demo — generatory szablonowe).\n';
  writeArtifact(proj, 'README.md', readme, 'doc');
}
function genWebPrototype(proj) {
  const a = proj.analysis || {};
  const feats = (a.features || []).slice(0, 6);
  const html = `<!doctype html>
<html lang="pl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>${escHtml(proj.name)} — prototyp</title>
<style>
*{box-sizing:border-box}body{margin:0;font-family:system-ui,sans-serif;background:#0a0d11;color:#e9eef4}
.hero{padding:64px 24px;text-align:center;background:linear-gradient(165deg,#0d1117,#050608)}
h1{font-size:2.1rem;margin:0 0 12px;letter-spacing:.02em}
.grad{background:linear-gradient(90deg,#22d3ee,#a78bfa,#ff8a1e);-webkit-background-clip:text;background-clip:text;color:transparent}
p{color:#93a0b0;max-width:560px;margin:0 auto;line-height:1.6}
.cta{display:inline-block;margin-top:22px;padding:14px 32px;border-radius:10px;background:linear-gradient(135deg,#ff8a1e,#ff5e3a);color:#140a02;font-weight:700;border:none;font-size:1rem;cursor:pointer}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:14px;max-width:920px;margin:36px auto;padding:0 24px}
.c{border:1px solid rgba(255,255,255,.1);border-radius:14px;padding:20px;background:rgba(255,255,255,.03)}
.c b{color:#7de8f8;display:block;margin-bottom:6px}.c span{color:#93a0b0;font-size:.88rem}
footer{text-align:center;color:#5d6875;font-size:.78rem;padding:26px;font-family:monospace}
</style></head><body>
<div class="hero"><h1>${escHtml(proj.name)}</h1><p>${escHtml(a.goal || proj.description || '')}</p><button class="cta">SKONTAKTUJ SIĘ Z NAMI</button></div>
<div class="grid">${feats.map((f) => '<div class="c"><b>' + escHtml(f) + '</b><span>Moduł aktywny w prototypie.</span></div>').join('')}</div>
<footer>PROTOTYP • wygenerowany przez WOJAN.AGENT v0.3 • Wojan Studio</footer>
</body></html>`;
  writeArtifact(proj, 'prototyp/index.html', html, 'web');
}
function genAppPrototype(proj) {
  const a = proj.analysis || {};
  const feats = (a.features || []).slice(0, 5);
  const rows = feats.map((f, i) => '<div style="display:flex;align-items:center;gap:10px;background:#11161d;border:1px solid #1b222b;border-radius:12px;padding:12px;font-size:.8rem;color:#93a0b0"><span style="width:26px;height:26px;border-radius:8px;background:rgba(34,211,238,.12);color:#7de8f8;display:grid;place-items:center;font-size:.68rem">' + String(i + 1).padStart(2, '0') + '</span>' + escHtml(f) + '<span style="margin-left:auto;width:7px;height:7px;border-radius:50%;background:' + ['#34d399', '#fbbf24', '#38bdf8'][i % 3] + '"></span></div>').join('');
  const html = `<!doctype html>
<html lang="pl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>${escHtml(proj.name)} — prototyp aplikacji</title>
<style>body{margin:0;background:#050608;display:grid;place-items:center;min-height:100vh;font-family:system-ui,sans-serif}</style></head>
<body><div style="width:300px;border-radius:34px;border:2px solid #2a323c;background:#0b0e12;padding:12px">
<div style="width:110px;height:16px;border-radius:9px;background:#050608;margin:0 auto 10px;border:1px solid #1c232b"></div>
<div style="border-radius:22px;overflow:hidden;background:linear-gradient(170deg,#0d1117,#090b0f);border:1px solid #1c232b;min-height:470px;display:flex;flex-direction:column">
<div style="display:flex;justify-content:space-between;padding:8px 14px;font-family:monospace;font-size:.6rem;color:#5d6875"><span>9:41</span><span>WOJAN.NET</span></div>
<div style="padding:12px 16px 10px;border-bottom:1px solid #161c23"><b style="color:#e9eef4;font-size:.95rem">${escHtml(proj.name)}</b><br><span style="font-size:.66rem;color:#22d3ee;font-family:monospace">PROTOTYP • ${(proj.domain || 'app').toUpperCase()}</span></div>
<div style="flex:1;padding:10px;display:grid;gap:8px;align-content:start">${rows}</div>
<div style="display:flex;justify-content:space-around;padding:12px 8px;border-top:1px solid #161c23;color:#5d6875"><span style="color:#22d3ee">◈</span><span>▤</span><span>＋</span><span>◔</span><span>☰</span></div>
</div></div></body></html>`;
  writeArtifact(proj, 'prototyp/app-mockup.html', html, 'web');
}
function genElectronics(proj) {
  const ino = `/* ${proj.name} — szkic firmware (WOJAN.AGENT v0.3, demo) */\n#include <Arduino.h>\n\nconst int PIN_SENSOR = A0;   // czujnik\nconst int PIN_PUMP   = 5;    // element wykonawczy\nconst int THRESHOLD  = 40;   // próg\n\nvoid setup() {\n  Serial.begin(115200);\n  pinMode(PIN_PUMP, OUTPUT);\n}\n\nvoid loop() {\n  int v = analogRead(PIN_SENSOR);\n  int level = map(v, 0, 1023, 100, 0);\n  Serial.print("Poziom: "); Serial.println(level);\n  digitalWrite(PIN_PUMP, level < THRESHOLD ? HIGH : LOW);\n  delay(5000);\n}\n`;
  writeArtifact(proj, 'firmware/firmware.ino', ino, 'doc');
  writeArtifact(proj, 'dokumentacja/schemat-polaczen.md', '# Schemat połączeń\n\n- Czujnik → wejście analogowe A0\n- Element wykonawczy (pompa/silnik/LED, przez tranzystor) → D5\n- Zasilanie: 5 V + przetwornica\n\n## Docelowo\n- Mikrokontroler z Wi-Fi (np. ESP32)\n- Komunikacja z aplikacją mobilną\n- Obudowa z produkcji Wojan Studio\n', 'doc');
}
function genProductionFile(proj) {
  const svg = '<svg xmlns="http://www.w3.org/2000/svg" width="420" height="320" viewBox="0 0 420 320"><rect width="420" height="320" fill="#0a0d11"/><g fill="none" stroke-width="1.5"><circle cx="210" cy="150" r="95" stroke="#22d3ee" stroke-dasharray="6 5"/><circle cx="210" cy="150" r="62" stroke="#a78bfa" stroke-dasharray="3 4"/><circle cx="210" cy="150" r="28" stroke="#ff8a1e"/><path d="M95 150h230M210 40v220" stroke="#5d6875" stroke-dasharray="2 6"/></g><text x="210" y="292" fill="#e9eef4" font-family="monospace" font-size="13" text-anchor="middle">' + escHtml(proj.name) + ' — projekt do produkcji</text></svg>';
  writeArtifact(proj, 'produkcja/projekt.svg', svg, 'design');
  writeArtifact(proj, 'dokumentacja/specyfikacja-produkcji.md', '# Specyfikacja produkcji\n\n- Materiał: do ustalenia (stal / drewno / pleksi)\n- Technologia: laser CNC / spawanie / obróbka\n- Wykończenie: personalizacja wg zamówienia\n\n> Plik `produkcja/projekt.svg` jest gotowy do wycinania/grawerowania.\n', 'doc');
}
function genManifest(proj) {
  writeArtifact(proj, 'wersja.json', JSON.stringify({
    projekt: proj.name, wersja: 'v0.' + db.history.filter((h) => h.projectId === proj.id).length,
    status: proj.status, postep: proj.progress, agent: 'WOJAN.AGENT v0.3 (demo)', wygenerowano: now(),
  }, null, 2), 'doc');
}
function agentProduce(proj, phase) {
  if (phase === 'start') genBaseDocs(proj);
  if (phase === 'build') {
    const d = proj.domain || 'web';
    if (d === 'web') genWebPrototype(proj);
    else if (d === 'app') genAppPrototype(proj);
    else if (d === 'electronics') genElectronics(proj);
    else if (['laser', 'metal', 'design'].includes(d)) genProductionFile(proj);
    else if (d === 'media') writeArtifact(proj, 'produkcja/scenariusz.md', '# Scenariusz\n\n> ' + (proj.description || '') + '\n\n## Ujęcia\n1. Otwarcie — logo i hasło\n2. Produkt w akcji\n3. Detale i realizacja\n4. CTA — kontakt\n', 'doc');
    else genWebPrototype(proj);
  }
  if (phase === 'done') genManifest(proj);
}
function backfillArtifacts() {
  let changed = false;
  db.projects.forEach((proj) => {
    if (proj.progress >= 40 || proj.status === 'prototype' || proj.status === 'done') {
      agentProduce(proj, 'start');
      if (proj.progress >= 45) agentProduce(proj, 'build');
      if (proj.status === 'prototype' || proj.status === 'done' || proj.progress >= 90) agentProduce(proj, 'done');
      changed = true;
    }
  });
  if (changed) saveDb();
}
function hasPreview(proj) {
  return ['prototyp/index.html', 'prototyp/app-mockup.html'].some((c) => fs.existsSync(path.join(PROJECT_DIR, proj.id, c)));
}

/* ---------------- live updates (SSE) ---------------- */
const sseClients = new Map(); // projectId -> Set<res>
function sseSend(projectId, type, data) {
  const set = sseClients.get(projectId);
  if (!set || !set.size) return;
  const payload = 'event: ' + type + '\ndata: ' + JSON.stringify(data || { ts: Date.now() }) + '\n\n';
  for (const res of set) { try { res.write(payload); } catch (e) {} }
}

/* -------------------------------------------------- DEMO AGENT ENGINE --- */
/* Symulator pracy Coding Agenta (tryb demo). Prawdziwy agent zostanie
   podłączony przez /api/agent/* i będzie działał w izolowanym sandboxie. */
const agentRuns = new Map(); // projectId -> { timer, logIdx }
const AGENT_LOGS = [
  'Generuję strukturę modułów...',
  'Buduję warstwę interfejsu...',
  'Łączę warstwę danych...',
  'Uruchamiam testy jednostkowe...',
  'Analizuję jakość kodu...',
  'Optymalizuję wydajność...',
  'Przygotowuję kolejną wersję...',
  'Weryfikuję zgodność z wymaganiami...',
];

function notify(userId, text, kind = 'info', ref = null) {
  db.notifications.push({ id: uid(), userId, kind, text, ref, read: false, ts: now() });
  saveDb();
}

/* WOJAN.CORE — uczenie adaptacyjne: wzmacnianie/osłabianie wag słów kluczowych
   na podstawie decyzji użytkownika (utworzenie projektu, ocena 👍/👎 analizy). */
function reinforce(analysisLike, delta) {
  const k = db.knowledge;
  let n = 0;
  (analysisLike.domains || []).forEach((d) => (d.matched || []).forEach((kw) => {
    k.weights[kw] = Math.round(((k.weights[kw] || 0) + delta) * 100) / 100;
    n++;
  }));
  if (n) {
    k.samples++;
    k.log.push({ id: uid(), ts: now(), text: (delta > 0 ? 'UCZENIE +: wzmocniono ' : 'UCZENIE −: osłabiono ') + n + ' słów kluczowych (próbka #' + k.samples + ')' });
    if (k.log.length > 80) k.log = k.log.slice(-50);
    saveDb();
  }
  return n;
}

function startDemoAgent(proj, byName) {
  if (agentRuns.has(proj.id)) return false;
  if (!['analysis', 'agent'].includes(proj.status)) return false;
  proj.status = 'agent';
  proj.updatedAt = now();
  proj.decisions = proj.decisions || [];
  db.activity.push({ id: uid(), projectId: proj.id, text: '[WOJAN.CORE] Demo agent uruchomiony przez: ' + byName, ts: now() });
  agentProduce(proj, 'start');
  db.activity.push({ id: uid(), projectId: proj.id, text: '[WOJAN.AGENT] Wygenerowano README.md i specyfikację → zakładka PLIKI', ts: now() });
  const run = { logIdx: 0 };
  run.timer = setInterval(() => {
    // agent czeka, jeśli klient ma podjąć decyzję
    if ((proj.decisions || []).some((x) => x.status === 'open')) return;
    proj.progress = Math.min(90, proj.progress + 2 + Math.floor(Math.random() * 5));
    proj.updatedAt = now();
    db.activity.push({ id: uid(), projectId: proj.id, text: '[Demo agent] ' + AGENT_LOGS[run.logIdx++ % AGENT_LOGS.length], ts: now() });
    sseSend(proj.id, 'update', { progress: proj.progress, status: proj.status });
    if (proj.progress >= 45 && !hasBuildArtifacts(proj)) {
      agentProduce(proj, 'build');
      db.activity.push({ id: uid(), projectId: proj.id, text: '[WOJAN.AGENT] Wygenerowano artefakty prototypu → PLIKI i PREVIEW', ts: now() });
    }
    // w połowie prac agent zgłasza decyzję do podjęcia
    if (proj.progress >= 62 && !(proj.decisions || []).length) {
      proj.decisions.push({
        id: uid(), question: 'Agent prosi o decyzję: który wariant funkcji rozwinąć w pierwszej kolejności?',
        options: ['Wariant A: prostszy i szybszy', 'Wariant B: rozszerzony'], status: 'open', answer: null, ts: now(),
      });
      notify(proj.ownerId, 'Agent wykrył problem wymagający decyzji („' + proj.name + '”).', 'warn', proj.id);
      sseSend(proj.id, 'update', {});
    }
    if (proj.progress >= 90) {
      proj.progress = 90;
      proj.status = 'prototype';
      if (!hasBuildArtifacts(proj)) agentProduce(proj, 'build');
      agentProduce(proj, 'done');
      const v = db.history.filter((h) => h.projectId === proj.id).length + 1;
      db.history.push({ id: uid(), projectId: proj.id, version: 'v0.' + v, note: 'Demo agent: prototyp gotowy', ts: now() });
      db.messages.push({ id: uid(), projectId: proj.id, kind: 'agent', author: 'AI Agent', text: 'Prototyp gotowy ✅ (symulacja demo). Kod został „uruchomiony” w izolowanym środowisku — preview znajdziesz w zakładce PREVIEW.', meta: null, ts: now() });
      notify(proj.ownerId, 'Twój prototyp jest gotowy. („' + proj.name + '”)', 'success', proj.id);
      sseSend(proj.id, 'update', { progress: proj.progress, status: proj.status });
      stopDemoAgent(proj.id);
    }
    if (db.activity.length > 600) db.activity = db.activity.slice(-400);
    saveDb();
  }, 2600);
  agentRuns.set(proj.id, run);
  saveDb();
  return true;
}

function stopDemoAgent(projectId) {
  const r = agentRuns.get(projectId);
  if (r) { clearInterval(r.timer); agentRuns.delete(projectId); }
}

/* ------------------------------------------------------------- HTTP ----- */
const MIME = {
  '.html': 'text/html; charset=utf-8', '.css': 'text/css; charset=utf-8', '.js': 'text/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8', '.svg': 'image/svg+xml', '.png': 'image/png',
  '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.webp': 'image/webp', '.ico': 'image/x-icon',
  '.woff2': 'font/woff2', '.mp4': 'video/mp4', '.md': 'text/markdown; charset=utf-8',
};

/* Nagłówki bezpieczeństwa — aplikacja serwowana jest z tego samego originu,
   więc CSP pozwala tylko self (bez zewnętrznych skryptów/inline poza niezbędnymi). */
function securityHeaders(extra) {
  const h = {
    'X-Content-Type-Options': 'nosniff',
    'X-Frame-Options': 'SAMEORIGIN',
    'Referrer-Policy': 'strict-origin-when-cross-origin',
    'Permissions-Policy': 'camera=(), microphone=(), geolocation=()',
  };
  // Ścisłe CSP tylko w produkcji (NODE_ENV=production) — dev/podgląd bez ograniczeń.
  if (PROD) {
    h['Content-Security-Policy'] = "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; img-src 'self' data: blob:; connect-src 'self'; media-src 'self' blob:; frame-ancestors 'self'; base-uri 'self'; form-action 'self'";
    h['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains';
  }
  return Object.assign(h, extra || {});
}

function json(res, code, obj) {
  const body = JSON.stringify(obj);
  res.writeHead(code, securityHeaders({ 'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'no-store' }));
  res.end(body);
}
function readBody(req) {
  return new Promise((resolve) => {
    let data = '';
    req.on('data', (c) => { data += c; if (data.length > 1e6) req.destroy(); });
    req.on('end', () => { try { resolve(data ? JSON.parse(data) : {}); } catch (e) { resolve({}); } });
  });
}
/* Surowe ciało żądania (upload plików audio/wideo). */
function readRawBody(req, limit) {
  return new Promise((resolve, reject) => {
    const chunks = []; let size = 0;
    req.on('data', (c) => {
      size += c.length;
      if (size > limit) { reject(new Error('limit')); req.destroy(); return; }
      chunks.push(c);
    });
    req.on('end', () => resolve(Buffer.concat(chunks)));
    req.on('error', reject);
  });
}
function logEvent(type, detail) {
  db.events.push({ ts: now(), type, detail });
  if (db.events.length > 500) db.events = db.events.slice(-500);
  saveDb();
}

/* rate limiting */
const rl = new Map();
function rateLimit(ip, bucket, limit, windowMs) {
  const key = bucket + ':' + ip;
  const t = Date.now();
  let e = rl.get(key);
  if (!e || t > e.reset) { e = { count: 0, reset: t + windowMs }; rl.set(key, e); }
  e.count++;
  return e.count <= limit;
}

function getToken(req) {
  const h = req.headers['authorization'] || '';
  return h.startsWith('Bearer ') ? h.slice(7) : null;
}
function getUser(req) {
  const tok = getToken(req);
  if (!tok || !db.sessions[tok]) return null;
  return db.users.find((u) => u.id === db.sessions[tok]) || null;
}
const publicUser = (u) => u && { id: u.id, name: u.name, email: u.email, role: u.role };

const STATUS_LABEL = { analysis: 'Analiza', agent: 'Agent pracuje', prototype: 'Prototyp gotowy', done: 'Gotowy produkt' };
const PIPELINE_STEPS = ['Analiza wymagań', 'Projekt architektury', 'Przygotowanie interfejsu', 'Tworzenie aplikacji', 'Testy', 'Preview'];
const PIPE_AT = [10, 30, 50, 70, 90, 100];

/* ----------------------------------------------------------- ROUTES ----- */
async function api(req, res, url) {
  const ip = req.headers['x-forwarded-for'] || req.socket.remoteAddress || '?';
  if (!rateLimit(ip, 'api', 600, 60000)) return json(res, 429, { error: 'Zbyt wiele żądań. Spróbuj za chwilę.' });
  const p = url.pathname;
  const m = req.method;
  const user = getUser(req);
  let body = {};
  if (m === 'POST' || m === 'PATCH') {
    if (p === '/api/media/upload') body = null; // upload: dane binarne czytane osobno
    else body = await readBody(req);
  }

  // ---------- AUTH ----------
  if (p === '/api/auth/register' && m === 'POST') {
    const { name, email, password } = body;
    if (!name || !email || !password || password.length < 6)
      return json(res, 400, { error: 'Podaj imię, e-mail i hasło (min. 6 znaków).' });
    if (db.users.some((u) => u.email.toLowerCase() === email.toLowerCase()))
      return json(res, 409, { error: 'Konto z tym adresem już istnieje.' });
    const u = { id: 'u-' + uid(), name, email, pass: sha(password), role: 'client', createdAt: now() };
    db.users.push(u);
    const tok = crypto.randomBytes(24).toString('hex');
    db.sessions[tok] = u.id;
    logEvent('auth', 'register ' + email);
    saveDb();
    return json(res, 200, { token: tok, user: publicUser(u) });
  }
  if (p === '/api/auth/login' && m === 'POST') {
    const { email, password } = body;
    const u = db.users.find((x) => x.email.toLowerCase() === String(email || '').toLowerCase());
    if (!u || u.pass !== sha(password || '')) return json(res, 401, { error: 'Nieprawidłowy e-mail lub hasło.' });
    const tok = crypto.randomBytes(24).toString('hex');
    db.sessions[tok] = u.id;
    logEvent('auth', 'login ' + email);
    saveDb();
    return json(res, 200, { token: tok, user: publicUser(u) });
  }
  if (p === '/api/me' && m === 'GET') return json(res, user ? 200 : 401, user ? { user: publicUser(user) } : { error: 'Brak sesji' });
  if (p === '/api/auth/logout' && m === 'POST') {
    const tok = getToken(req);
    if (tok) delete db.sessions[tok];
    saveDb();
    return json(res, 200, { ok: true });
  }

  // ---------- PUBLICZNY PODGLĄD PROJEKTU (link do udostępnienia) ----------
  // Tylko pola bezpieczne marketingowo — bez plików, wiadomości, wycen i danych klienta.
  const pub = p.match(/^\/api\/public\/projects\/([\w-]+)$/);
  if (pub && m === 'GET') {
    const proj = db.projects.find((x) => x.id === pub[1]);
    if (!proj) return json(res, 404, { error: 'Nie znaleziono projektu' });
    const firstTodo = PIPE_AT.findIndex((at) => proj.progress < at);
    return json(res, 200, {
      project: {
        id: proj.id, name: proj.name, domain: proj.domain, status: proj.status,
        progress: proj.progress, level: proj.level, modules: proj.modules,
        updatedAt: proj.updatedAt,
        pipeline: PIPELINE_STEPS.map((s, i) => ({
          label: s,
          state: proj.progress >= PIPE_AT[i] ? 'done' : (i === firstTodo ? 'work' : 'todo'),
        })),
      },
    });
  }

  if (p === '/api/activity/recent' && m === 'GET') {
    if (!user) return json(res, 401, { error: 'Wymagane logowanie' });
    const mine = user.role === 'owner' ? db.projects : db.projects.filter((x) => x.ownerId === user.id);
    const ids = new Set(mine.map((x) => x.id));
    const nameOf = (id) => (db.projects.find((x) => x.id === id) || {}).name || '?';
    const items = db.activity.filter((a) => ids.has(a.projectId)).slice(-15).reverse()
      .map((a) => ({ text: a.text, ts: a.ts, projectId: a.projectId, project: nameOf(a.projectId) }));
    return json(res, 200, { activity: items });
  }

  // ---------- PUBLICZNE STATYSTYKI (hero) ----------
  if (p === '/api/health' && m === 'GET') {
    const base = { ok: true, service: 'wojan-studio', version: APP_VERSION, ts: now(), uptime: Math.floor(process.uptime()) };
    if (user && user.role === 'owner') {
      const mem = process.memoryUsage();
      base.counts = {
        projects: db.projects.length,
        clients: db.users.filter((u) => u.role === 'client').length,
        media: (db.media || []).length,
        contacts: db.contacts.length,
        payments: db.payments.length,
        giftOrders: db.giftOrders.length,
      };
      base.memoryMB = Math.round(mem.heapUsed / 1048576);
      base.nodeVersion = process.version;
    }
    return json(res, 200, base);
  }
  if (p === '/api/stats/public' && m === 'GET') {
    return json(res, 200, {
      projects: db.projects.length,
      prototypes: db.projects.filter((x) => x.status === 'prototype' || x.status === 'done').length,
      tracks: (db.media || []).length,
      portfolio: (db.portfolio || []).filter((x) => x.enabled).length,
      coreSamples: db.knowledge.samples,
      services: (db.services || []).filter((x) => x.enabled).length,
    });
  }

  // ---------- NOTIFICATIONS ----------
  if (p === '/api/notifications' && m === 'GET') {
    if (!user) return json(res, 401, { error: 'Wymagane logowanie' });
    const list = db.notifications.filter((n) => n.userId === user.id).slice(-40).reverse();
    return json(res, 200, { notifications: list, unread: list.filter((n) => !n.read).length });
  }
  if (p === '/api/notifications/read-all' && m === 'POST') {
    if (!user) return json(res, 401, { error: 'Wymagane logowanie' });
    db.notifications.forEach((n) => { if (n.userId === user.id) n.read = true; });
    saveDb();
    return json(res, 200, { ok: true });
  }
  const nr = p.match(/^\/api\/notifications\/([\w-]+)\/read$/);
  if (nr && m === 'POST') {
    if (!user) return json(res, 401, { error: 'Wymagane logowanie' });
    const n = db.notifications.find((x) => x.id === nr[1] && x.userId === user.id);
    if (!n) return json(res, 404, { error: 'Nie znaleziono powiadomienia' });
    n.read = true;
    saveDb();
    return json(res, 200, { ok: true });
  }

  // ---------- SERVICES ----------
  if (p === '/api/services' && m === 'GET') return json(res, 200, { services: db.services });
  const svc = p.match(/^\/api\/services\/([\w-]+)$/);
  if (svc && m === 'PATCH') {
    if (!user || user.role !== 'owner') return json(res, 403, { error: 'Tylko właściciel.' });
    const s = db.services.find((x) => x.id === svc[1]);
    if (!s) return json(res, 404, { error: 'Nie znaleziono' });
    s.enabled = !!body.enabled;
    logEvent('services', (s.enabled ? 'enabled ' : 'disabled ') + s.id);
    saveDb();
    return json(res, 200, { service: s });
  }

  // ---------- PORTFOLIO (publiczne) ----------
  if (p === '/api/portfolio' && m === 'GET') {
    return json(res, 200, { portfolio: (db.portfolio || []).filter((x) => x.enabled) });
  }

  // ---------- AI BUILDER ----------
  if (p === '/api/ai/analyze' && m === 'POST') {
    if (!rateLimit(ip, 'ai', 30, 60000)) return json(res, 429, { error: 'Limit analiz — spróbuj za chwilę.' });
    const text = String(body.description || '').trim();
    if (text.length < 12) return json(res, 400, { error: 'Opisz projekt nieco dokładniej (min. kilka słów).' });
    if (text.length < 60 && !body.force) {
      const qs = followUpQuestions(text);
      if (qs.length) { logEvent('ai', 'follow-up questions'); return json(res, 200, { needQuestions: true, questions: qs, demo: true }); }
    }
    const analysis = analyzeDescription(text, !!body.ideaMode, db.knowledge.weights);
    logEvent('ai', 'analyze (' + text.length + ' znaków) → ' + analysis.level);
    return json(res, 200, { analysis, demo: true, core: { version: CORE_VERSION, samples: db.knowledge.samples } });
  }
  if (p === '/api/ai/change' && m === 'POST') {
    const proposal = proposeChange(String(body.text || ''));
    logEvent('ai', 'change proposal');
    return json(res, 200, { proposal });
  }

  if (p === '/api/ai/feedback' && m === 'POST') {
    if (!rateLimit(ip, 'ai', 30, 60000)) return json(res, 429, { error: 'Limit analiz — spróbuj za chwilę.' });
    const n = reinforce({ domains: Array.isArray(body.domains) ? body.domains : [] }, body.good ? 0.15 : -0.2);
    if (!n) return json(res, 400, { error: 'Brak danych do nauki.' });
    logEvent('ai', 'feedback ' + (body.good ? 'good' : 'bad'));
    return json(res, 200, { ok: true, samples: db.knowledge.samples });
  }

  // ---------- PROJECTS ----------
  if (p === '/api/projects' && m === 'GET') {
    if (!user) return json(res, 401, { error: 'Wymagane logowanie' });
    const list = user.role === 'owner' ? db.projects : db.projects.filter((x) => x.ownerId === user.id);
    return json(res, 200, { projects: list.map((x) => ({ ...x, agentRunning: agentRuns.has(x.id), owner: publicUser(db.users.find((u) => u.id === x.ownerId)) })) });
  }
  if (p === '/api/projects' && m === 'POST') {
    if (!user) return json(res, 401, { error: 'Wymagane logowanie' });
    const name = String(body.name || 'Nowy projekt').slice(0, 80);
    const description = String(body.description || '').slice(0, 2000);
    const a = body.analysis || null;
    const proj = {
      id: 'p-' + uid(), ownerId: user.id, name, description,
      domain: (a && a.domains && a.domains[0] && a.domains[0].key) || 'web',
      status: 'analysis', progress: 15,
      level: (a && a.level) || '—', modules: (a && a.modules) || 0, mvp: (a && a.mvpCount) || 0,
      analysis: a, createdAt: now(), updatedAt: now(),
    };
    db.projects.push(proj);
    db.messages.push({ id: uid(), projectId: proj.id, kind: 'agent', author: 'AI Agent', text: 'Projekt przyjęty. Analiza została zapisana. Kolejny krok: potwierdzenie zakresu MVP przez Wojan Studio.', meta: null, ts: now() });
    db.history.push({ id: uid(), projectId: proj.id, version: 'v0.1', note: 'Utworzenie projektu + analiza AI', ts: now() });
    db.tasks.push({ id: uid(), projectId: proj.id, title: 'Potwierdzenie zakresu MVP', done: false });
    db.activity.push({ id: uid(), projectId: proj.id, text: 'Utworzono projekt na podstawie opisu', ts: now() });
    db.quotes.push({ id: uid(), projectId: proj.id, scope: `Projekt: ${name} • Zakres: ${proj.level} • Moduły: ${proj.modules}`, status: 'draft', amount: '', note: '', ts: now() });
    if (a && Array.isArray(a.domains)) reinforce(a, 0.25);
    logEvent('projects', 'created ' + name);
    const ownerUser = db.users.find((u) => u.role === 'owner');
    if (ownerUser) notify(ownerUser.id, user.name + ' utworzył(a) nowy projekt: „' + name + '”.', 'info', proj.id);
    saveDb();
    return json(res, 200, { project: proj });
  }
  const pid = p.match(/^\/api\/projects\/([\w-]+)$/);
  if (pid && m === 'GET') {
    if (!user) return json(res, 401, { error: 'Wymagane logowanie' });
    const proj = db.projects.find((x) => x.id === pid[1]);
    if (!proj || (user.role !== 'owner' && proj.ownerId !== user.id)) return json(res, 404, { error: 'Nie znaleziono projektu' });
    return json(res, 200, {
      project: proj,
      messages: db.messages.filter((x) => x.projectId === proj.id),
      tasks: db.tasks.filter((x) => x.projectId === proj.id),
      files: db.files.filter((x) => x.projectId === proj.id),
      history: db.history.filter((x) => x.projectId === proj.id),
      activity: db.activity.filter((x) => x.projectId === proj.id).slice(-12),
      quote: db.quotes.find((x) => x.projectId === proj.id) || null,
      payment: db.payments.find((x) => x.projectId === proj.id) || null,
      decisions: proj.decisions || [],
      agentRunning: agentRuns.has(proj.id),
      previewAvailable: hasPreview(proj),
    });
  }
  if (pid && m === 'PATCH') {
    if (!user || user.role !== 'owner') return json(res, 403, { error: 'Tylko właściciel może zmieniać status.' });
    const proj = db.projects.find((x) => x.id === pid[1]);
    if (!proj) return json(res, 404, { error: 'Nie znaleziono' });
    if (body.status) proj.status = body.status;
    if (typeof body.progress === 'number') proj.progress = Math.max(0, Math.min(100, body.progress));
    proj.updatedAt = now();
    db.activity.push({ id: uid(), projectId: proj.id, text: 'Status: ' + (STATUS_LABEL[proj.status] || proj.status) + ' (' + proj.progress + '%)', ts: now() });
    logEvent('projects', 'patched ' + proj.id);
    saveDb();
    sseSend(proj.id, 'update', { kind: 'status' });
    return json(res, 200, { project: proj });
  }
  const sub = p.match(/^\/api\/projects\/([\w-]+)\/(messages|tasks|files|accept-change)$/);
  if (sub && m === 'POST') {
    if (!user) return json(res, 401, { error: 'Wymagane logowanie' });
    const proj = db.projects.find((x) => x.id === sub[1]);
    if (!proj || (user.role !== 'owner' && proj.ownerId !== user.id)) return json(res, 404, { error: 'Nie znaleziono projektu' });
    if (sub[2] === 'messages') {
      const text = String(body.text || '').trim().slice(0, 2000);
      if (!text) return json(res, 400, { error: 'Pusta wiadomość' });
      const kind = user.role === 'owner' ? 'wojan' : 'client';
      const msg = { id: uid(), projectId: proj.id, kind, author: user.name, text, meta: null, ts: now() };
      db.messages.push(msg);
      db.activity.push({ id: uid(), projectId: proj.id, text: 'Nowa wiadomość od: ' + user.name, ts: now() });
      if (kind === 'wojan') {
        notify(proj.ownerId, 'Wojan odpowiedział na wiadomość w projekcie „' + proj.name + '”.', 'info', proj.id);
      } else {
        const ownerUser = db.users.find((u) => u.role === 'owner');
        if (ownerUser) notify(ownerUser.id, 'Nowa wiadomość od ' + user.name + ' w projekcie „' + proj.name + '”.', 'info', proj.id);
      }
      saveDb();
      sseSend(proj.id, 'update', { kind: 'message' });
      return json(res, 200, { message: msg });
    }
    if (sub[2] === 'tasks') {
      const task = { id: uid(), projectId: proj.id, title: String(body.title || 'Zadanie').slice(0, 120), done: false };
      db.tasks.push(task); saveDb();
      return json(res, 200, { task });
    }
    if (sub[2] === 'files') {
      const f = { id: uid(), projectId: proj.id, name: String(body.name || 'plik').slice(0, 120), size: body.size || '—', kind: 'doc', ts: now() };
      db.files.push(f); saveDb();
      sseSend(proj.id, 'update', { kind: 'files' });
      return json(res, 200, { file: f });
    }
    if (sub[2] === 'accept-change') {
      const adds = Array.isArray(body.adds) ? body.adds.slice(0, 10) : [];
      db.messages.push({ id: uid(), projectId: proj.id, kind: 'agent', author: 'AI Agent', text: 'Zmiana zaakceptowana ✅ Dodaję do projektu: ' + (adds.join(', ') || 'nowe wymagania') + '. Zadania trafiły do listy.', meta: null, ts: now() });
      adds.forEach((a) => db.tasks.push({ id: uid(), projectId: proj.id, title: a, done: false }));
      const lastV = db.history.filter((h) => h.projectId === proj.id).length;
      db.history.push({ id: uid(), projectId: proj.id, version: 'v0.' + (lastV + 1), note: 'Zaakceptowana zmiana: ' + adds.slice(0, 2).join(', '), ts: now() });
      db.activity.push({ id: uid(), projectId: proj.id, text: 'Zaakceptowano zmianę projektu (' + adds.length + ' elementów)', ts: now() });
      saveDb();
      sseSend(proj.id, 'update', { kind: 'change' });
      return json(res, 200, { ok: true });
    }
  }
  const tid = p.match(/^\/api\/tasks\/([\w-]+)\/toggle$/);
  if (tid && m === 'POST') {
    if (!user) return json(res, 401, { error: 'Wymagane logowanie' });
    const task = db.tasks.find((x) => x.id === tid[1]);
    if (!task) return json(res, 404, { error: 'Nie znaleziono zadania' });
    task.done = !task.done; saveDb();
    sseSend(task.projectId, 'update', { kind: 'task' });
    return json(res, 200, { task });
  }

  // ---------- DEMO AGENT + DECYZJE + PLIKI (download) ----------
  // ---------- LIVE STREAM (SSE) + PREVIEW + PAKIET WDROŻENIOWY ----------
  const strm = p.match(/^\/api\/projects\/([\w-]+)\/stream$/);
  if (strm && m === 'GET') {
    const tok = url.searchParams.get('token');
    const u = tok && db.sessions[tok] ? db.users.find((x) => x.id === db.sessions[tok]) : null;
    if (!u) return json(res, 401, { error: 'Wymagane logowanie' });
    const proj = db.projects.find((x) => x.id === strm[1]);
    if (!proj || (u.role !== 'owner' && proj.ownerId !== u.id)) return json(res, 404, { error: 'Nie znaleziono projektu' });
    res.writeHead(200, { 'Content-Type': 'text/event-stream', 'Cache-Control': 'no-store', 'Connection': 'keep-alive', 'X-Accel-Buffering': 'no' });
    res.write('event: hello\ndata: {"ok":true}\n\n');
    if (!sseClients.has(proj.id)) sseClients.set(proj.id, new Set());
    sseClients.get(proj.id).add(res);
    const hb = setInterval(() => { try { res.write(': hb\n\n'); } catch (e) {} }, 25000);
    req.on('close', () => {
      clearInterval(hb);
      const s = sseClients.get(proj.id);
      if (s) { s.delete(res); if (!s.size) sseClients.delete(proj.id); }
    });
    return;
  }
  const pv = p.match(/^\/api\/projects\/([\w-]+)\/preview$/);
  if (pv && m === 'GET') {
    const proj = db.projects.find((x) => x.id === pv[1]);
    if (!proj) return json(res, 404, { error: 'Nie znaleziono projektu' });
    for (const c of ['prototyp/index.html', 'prototyp/app-mockup.html']) {
      const fp = path.join(PROJECT_DIR, proj.id, c);
      if (fs.existsSync(fp)) {
        res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8', 'Cache-Control': 'no-store' });
        return fs.createReadStream(fp).pipe(res);
      }
    }
    return json(res, 404, { error: 'Prototyp nie jest jeszcze gotowy' });
  }
  const dp = p.match(/^\/api\/projects\/([\w-]+)\/deploy-package$/);
  if (dp && m === 'GET') {
    if (!user) return json(res, 401, { error: 'Wymagane logowanie' });
    const proj = db.projects.find((x) => x.id === dp[1]);
    if (!proj || (user.role !== 'owner' && proj.ownerId !== user.id)) return json(res, 404, { error: 'Nie znaleziono projektu' });
    if (!['prototype', 'done'].includes(proj.status)) return json(res, 400, { error: 'Pakiet dostępny po gotowym prototypie.' });
    let bundle = '# PAKIET WDROŻENIOWY — ' + proj.name + '\n\nStatus: ' + (STATUS_LABEL[proj.status] || proj.status) + ' • Wygenerowano: ' + now() + '\n';
    bundle += 'Agent: WOJAN.AGENT v0.3 (demo)\n\n> Kompletny zestaw artefaktów projektu. Kolejne kroki: review → deploy / produkcja.\n';
    db.files.filter((f) => f.projectId === proj.id && f.disk).forEach((f) => {
      const fp = path.join(PROJECT_DIR, proj.id, f.disk);
      try {
        bundle += '\n\n' + '='.repeat(70) + '\n## PLIK: ' + f.name + '\n' + '='.repeat(70) + '\n\n' + fs.readFileSync(fp, 'utf8');
      } catch (e) {}
    });
    res.writeHead(200, { 'Content-Type': 'text/plain; charset=utf-8', 'Content-Disposition': 'attachment; filename="pakiet-wdrozeniowy-' + proj.id + '.md"' });
    return res.end(bundle);
  }

  // ---------- PŁATNOŚCI ----------
  if (p === '/api/payments' && m === 'POST') {
    if (!user) return json(res, 401, { error: 'Wymagane logowanie' });
    const q = db.quotes.find((x) => x.id === body.quoteId);
    if (!q) return json(res, 404, { error: 'Nie znaleziono wyceny' });
    const proj = db.projects.find((x) => x.id === q.projectId);
    if (!proj || (user.role !== 'owner' && proj.ownerId !== user.id)) return json(res, 403, { error: 'Brak dostępu do tego projektu' });
    if (q.status !== 'accepted') return json(res, 400, { error: 'Najpierw zaakceptuj wycenę.' });
    if (!['blik', 'karta', 'przelew'].includes(body.method)) return json(res, 400, { error: 'Wybierz metodę płatności.' });
    const pay = { id: 'pay-' + uid(), projectId: proj.id, quoteId: q.id, amount: q.amount || 'do ustalenia', method: body.method, status: 'opłacona', payer: user.name, ts: now() };
    db.payments.push(pay);
    q.status = 'paid';
    db.activity.push({ id: uid(), projectId: proj.id, text: 'Płatność zaksięgowana (' + pay.method + ') — pełna realizacja wystartowała', ts: now() });
    db.messages.push({ id: uid(), projectId: proj.id, kind: 'agent', author: 'AI Agent', text: 'Płatność potwierdzona 💳 Realizacja ruszyła pełną parą. Fakturę pobierzesz z podsumowania projektu.', meta: null, ts: now() });
    const ownerUser = db.users.find((u) => u.role === 'owner');
    if (ownerUser && user.id !== ownerUser.id) notify(ownerUser.id, 'Płatność za projekt „' + proj.name + '” zaksięgowana (' + pay.amount + ').', 'success', proj.id);
    logEvent('payments', 'paid ' + pay.id);
    saveDb();
    sseSend(proj.id, 'update', { kind: 'payment' });
    return json(res, 200, { payment: pay });
  }
  const inv = p.match(/^\/api\/payments\/([\w-]+)\/invoice$/);
  if (inv && m === 'GET') {
    if (!user) return json(res, 401, { error: 'Wymagane logowanie' });
    const pay = db.payments.find((x) => x.id === inv[1]);
    if (!pay) return json(res, 404, { error: 'Nie znaleziono płatności' });
    const proj = db.projects.find((x) => x.id === pay.projectId);
    if (!proj || (user.role !== 'owner' && proj.ownerId !== user.id)) return json(res, 403, { error: 'Brak dostępu' });
    const txt = 'FAKTURA (dokument demonstracyjny)\n================================\n\nSPRZEDAWCA\nWojan Studio • Projektujemy. Budujemy. Programujemy. Produkujemy.\n\nNABYWCA\n' + user.name + '\n\nPROJEKT\n' + proj.name + '\n\nKWOTA: ' + pay.amount + '\nMETODA: ' + pay.method + '\nDATA: ' + now() + '\nNUMER: ' + pay.id + '\n\nSTATUS: ✅ OPŁACONA\n\n---\nDziękujemy! Realizacja projektu została uruchomiona.\n';
    res.writeHead(200, { 'Content-Type': 'text/plain; charset=utf-8', 'Content-Disposition': 'attachment; filename="faktura-' + pay.id + '.txt"' });
    return res.end(txt);
  }

  const agr = p.match(/^\/api\/projects\/([\w-]+)\/agent\/(start|stop)$/);
  if (agr && m === 'POST') {
    if (!user) return json(res, 401, { error: 'Wymagane logowanie' });
    const proj = db.projects.find((x) => x.id === agr[1]);
    if (!proj || (user.role !== 'owner' && proj.ownerId !== user.id)) return json(res, 404, { error: 'Nie znaleziono projektu' });
    if (agr[2] === 'start') {
      if (!startDemoAgent(proj, user.name)) return json(res, 400, { error: 'Nie można uruchomić agenta (już działa albo projekt jest zakończony).' });
    } else {
      stopDemoAgent(proj.id);
      db.activity.push({ id: uid(), projectId: proj.id, text: 'Demo agent zatrzymany przez: ' + user.name, ts: now() });
    }
    saveDb();
    return json(res, 200, { running: agentRuns.has(proj.id), status: proj.status, progress: proj.progress });
  }
  const dr = p.match(/^\/api\/projects\/([\w-]+)\/decisions\/([\w-]+)\/answer$/);
  if (dr && m === 'POST') {
    if (!user) return json(res, 401, { error: 'Wymagane logowanie' });
    const proj = db.projects.find((x) => x.id === dr[1]);
    if (!proj || (user.role !== 'owner' && proj.ownerId !== user.id)) return json(res, 404, { error: 'Nie znaleziono projektu' });
    const dec = (proj.decisions || []).find((x) => x.id === dr[2]);
    if (!dec) return json(res, 404, { error: 'Nie znaleziono decyzji' });
    dec.status = 'answered';
    dec.answer = String(body.answer || '').slice(0, 200);
    db.activity.push({ id: uid(), projectId: proj.id, text: 'Decyzja podjęta: ' + dec.answer, ts: now() });
    db.messages.push({ id: uid(), projectId: proj.id, kind: 'agent', author: 'AI Agent', text: 'Otrzymałem decyzję: „' + dec.answer + '”. Kontynuuję prace zgodnie z wybranym wariantem.', meta: null, ts: now() });
    saveDb();
    sseSend(proj.id, 'update', { kind: 'decision' });
    return json(res, 200, { decision: dec });
  }
  const fdl = p.match(/^\/api\/projects\/([\w-]+)\/files\/([\w-]+)\/download$/);
  if (fdl && m === 'GET') {
    if (!user) return json(res, 401, { error: 'Wymagane logowanie' });
    const proj = db.projects.find((x) => x.id === fdl[1]);
    if (!proj || (user.role !== 'owner' && proj.ownerId !== user.id)) return json(res, 404, { error: 'Nie znaleziono' });
    const f = db.files.find((x) => x.id === fdl[2] && x.projectId === proj.id);
    if (!f) return json(res, 404, { error: 'Nie znaleziono pliku' });
    if (f.disk) {
      const fp = path.join(PROJECT_DIR, proj.id, f.disk);
      if (fs.existsSync(fp)) {
        res.writeHead(200, { 'Content-Type': 'text/plain; charset=utf-8', 'Content-Disposition': 'attachment; filename="' + f.name.replace(/[^\w.\-]/g, '_') + '"' });
        return fs.createReadStream(fp).pipe(res);
      }
    }
    const a = proj.analysis || {};
    let content = '# ' + f.name + '\n\nProjekt: ' + proj.name + '\nStatus: ' + (STATUS_LABEL[proj.status] || proj.status) + ' (' + proj.progress + '%)\nWygenerowano: ' + now() + '\n\n--- WOJAN STUDIO · zawartość demonstracyjna ---\n';
    if (a.goal) content += '\n## Cel\n' + a.goal + '\n';
    if ((a.features || []).length) content += '\n## Funkcje\n' + a.features.map((x) => '- ' + x).join('\n') + '\n';
    if ((a.screens || []).length) content += '\n## Ekrany\n' + a.screens.map((x) => '- ' + x).join('\n') + '\n';
    if ((a.mvp || []).length) content += '\n## Zakres MVP\n' + a.mvp.map((x) => '- ' + x).join('\n') + '\n';
    content += '\n> Wiążącą wycenę zatwierdza właściciel Wojan Studio.\n';
    res.writeHead(200, {
      'Content-Type': 'text/plain; charset=utf-8',
      'Content-Disposition': 'attachment; filename="' + f.name.replace(/[^\w.\- ]/g, '_') + '"',
    });
    return res.end(content);
  }

  // ---------- CONTACT ----------
  if (p === '/api/contact' && m === 'POST') {
    const c = {
      id: uid(), name: String(body.name || '').slice(0, 80), email: String(body.email || '').slice(0, 120),
      phone: String(body.phone || '').slice(0, 40), description: String(body.description || '').slice(0, 3000),
      budget: String(body.budget || ''), deadline: String(body.deadline || ''),
      attachments: Array.isArray(body.attachments) ? body.attachments.slice(0, 10) : [], ts: now(),
    };
    if (!c.email || !c.description) return json(res, 400, { error: 'E-mail i opis projektu są wymagane.' });
    db.contacts.push(c);
    logEvent('contact', 'new from ' + c.email);
    const ownerUser = db.users.find((u) => u.role === 'owner');
    if (ownerUser) notify(ownerUser.id, 'Nowe zgłoszenie z formularza: ' + (c.name || c.email), 'info');
    saveDb();
    return json(res, 200, { ok: true, id: c.id });
  }

  if (p === '/api/me/password' && m === 'POST') {
    if (!user) return json(res, 401, { error: 'Wymagane logowanie' });
    if (!body.current || user.pass !== sha(body.current)) return json(res, 400, { error: 'Obecne hasło jest nieprawidłowe.' });
    if (!body.next || String(body.next).length < 6) return json(res, 400, { error: 'Nowe hasło musi mieć min. 6 znaków.' });
    user.pass = sha(body.next);
    logEvent('auth', 'password changed ' + user.email);
    saveDb();
    return json(res, 200, { ok: true });
  }

  // ---------- PIOSENKI & UPOMINKI ----------
  if (p === '/api/gift-orders' && m === 'POST') {
    if (!rateLimit(ip, 'gift', 10, 60000)) return json(res, 429, { error: 'Zbyt wiele zgłoszeń — spróbuj za chwilę.' });
    const VARIANTS = { song_qr: 'Piosenka + grawer z QR code', song: 'Sam utwór', engraving: 'Sam grawer personalizowany', marketplace: 'Produkt z marketplace' };
    const variant = VARIANTS[body.variant] ? body.variant : null;
    if (!variant) return json(res, 400, { error: 'Wybierz wariant upominku.' });
    const o = {
      id: 'g-' + uid(), variant, product: String(body.product || '').slice(0, 160),
      description: String(body.description || '').slice(0, 2000),
      occasion: String(body.occasion || '').slice(0, 120),
      engraving: String(body.engraving || '').slice(0, 300),
      name: String(body.name || '').slice(0, 80), email: String(body.email || '').slice(0, 120), phone: String(body.phone || '').slice(0, 40),
      status: 'nowe', ts: now(),
    };
    if (!o.description || !o.occasion || !o.email) return json(res, 400, { error: 'Uzupełnij opis, okazję i e-mail.' });
    db.giftOrders.push(o);
    const ownerUser = db.users.find((u) => u.role === 'owner');
    if (ownerUser) notify(ownerUser.id, 'Nowe zamówienie: Piosenki & Upominki (' + VARIANTS[variant] + ') — ' + (o.name || o.email), 'info');
    logEvent('gift', 'new order ' + o.id);
    saveDb();
    return json(res, 200, { ok: true, id: o.id });
  }
  const gm = p.match(/^\/api\/gift-orders\/([\w-]+)$/);
  if (gm && m === 'PATCH') {
    if (!user || user.role !== 'owner') return json(res, 403, { error: 'Tylko właściciel.' });
    const o = db.giftOrders.find((x) => x.id === gm[1]);
    if (!o) return json(res, 404, { error: 'Nie znaleziono' });
    if (['nowe', 'realizacja', 'gotowe'].includes(body.status)) o.status = body.status;
    saveDb();
    return json(res, 200, { order: o });
  }

  // ---------- MEDIA / WOJAN RADIO ----------
  if (p === '/api/media' && m === 'GET') {
    const u = getUser(req);
    return json(res, 200, { tracks: (db.media || []).map(({ id, name, type, ext, size, plays, likes, likedBy, ts }) => ({ id, name, type, ext, size, plays: plays || 0, likes: likes || 0, liked: u ? (likedBy || []).includes(u.id) : false, ts })) });
  }
  const mlike = p.match(/^\/api\/media\/([\w-]+)\/like$/);
  if (mlike && m === 'POST') {
    if (!user) return json(res, 401, { error: 'Wymagane logowanie' });
    const track = (db.media || []).find((x) => x.id === mlike[1]);
    if (!track) return json(res, 404, { error: 'Nie znaleziono utworu' });
    track.likedBy = track.likedBy || [];
    const li = track.likedBy.indexOf(user.id);
    if (li >= 0) track.likedBy.splice(li, 1); else track.likedBy.push(user.id);
    track.likes = track.likedBy.length;
    saveDb();
    return json(res, 200, { id: track.id, likes: track.likes, liked: track.likedBy.includes(user.id) });
  }
  if (p === '/api/media/upload' && m === 'POST') {
    if (!user || user.role !== 'owner') return json(res, 403, { error: 'Tylko właściciel może dodawać utwory.' });
    let buf;
    try { buf = await readRawBody(req, MEDIA_MAX); } catch (e) { return json(res, 413, { error: 'Plik jest za duży (limit 90 MB).' }); }
    if (!buf || !buf.length) return json(res, 400, { error: 'Pusty plik.' });
    const rawName = decodeURIComponent(String(url.searchParams.get('name') || req.headers['x-file-name'] || 'utwor'));
    const ext = path.extname(rawName).toLowerCase();
    if (!MEDIA_MIME[ext]) return json(res, 400, { error: 'Nieobsługiwany format. Dozwolone: mp3, wav, ogg, m4a, aac, flac, mp4, webm, mov.' });
    const id = 'm-' + uid();
    fs.mkdirSync(MEDIA_DIR, { recursive: true });
    fs.writeFileSync(path.join(MEDIA_DIR, id + ext), buf);
    const track = {
      id, name: (path.basename(rawName, ext).replace(/_+/g, ' ').trim().slice(0, 120)) || 'Utwór',
      type: MEDIA_VIDEO_EXT.includes(ext) ? 'video' : 'audio', ext, size: buf.length, plays: 0, likes: 0, likedBy: [], ts: now(),
    };
    db.media.push(track);
    logEvent('media', 'uploaded ' + track.name);
    saveDb();
    return json(res, 200, { track });
  }
  const med = p.match(/^\/api\/media\/([\w-]+)\/file$/);
  if (med && m === 'GET') {
    const track = (db.media || []).find((x) => x.id === med[1]);
    if (!track) return json(res, 404, { error: 'Nie znaleziono utworu' });
    const fp = path.join(MEDIA_DIR, track.id + track.ext);
    let stat;
    try { stat = fs.statSync(fp); } catch (e) { return json(res, 404, { error: 'Brak pliku na dysku' }); }
    const mime = MEDIA_MIME[track.ext] || 'application/octet-stream';
    const range = req.headers.range;
    if (range) {
      const parts = range.replace(/bytes=/, '').split('-');
      const start = parseInt(parts[0], 10) || 0;
      const end = parts[1] ? Math.min(parseInt(parts[1], 10), stat.size - 1) : stat.size - 1;
      if (start >= stat.size || end < start) { res.writeHead(416, { 'Content-Range': `bytes */${stat.size}` }); return res.end(); }
      res.writeHead(206, { 'Content-Range': `bytes ${start}-${end}/${stat.size}`, 'Accept-Ranges': 'bytes', 'Content-Length': end - start + 1, 'Content-Type': mime });
      fs.createReadStream(fp, { start, end }).pipe(res);
    } else {
      res.writeHead(200, { 'Content-Length': stat.size, 'Content-Type': mime, 'Accept-Ranges': 'bytes' });
      fs.createReadStream(fp).pipe(res);
    }
    return;
  }
  const mplay = p.match(/^\/api\/media\/([\w-]+)\/play$/);
  if (mplay && m === 'POST') {
    const track = (db.media || []).find((x) => x.id === mplay[1]);
    if (!track) return json(res, 404, { error: 'Nie znaleziono utworu' });
    track.plays = (track.plays || 0) + 1;
    saveDb();
    return json(res, 200, { id: track.id, plays: track.plays });
  }
  const mdel = p.match(/^\/api\/media\/([\w-]+)$/);
  if (mdel && m === 'DELETE') {
    if (!user || user.role !== 'owner') return json(res, 403, { error: 'Tylko właściciel.' });
    const i = (db.media || []).findIndex((x) => x.id === mdel[1]);
    if (i < 0) return json(res, 404, { error: 'Nie znaleziono' });
    const track = db.media[i];
    db.media.splice(i, 1);
    try { fs.unlinkSync(path.join(MEDIA_DIR, track.id + track.ext)); } catch (e) {}
    logEvent('media', 'deleted ' + track.name);
    saveDb();
    return json(res, 200, { ok: true });
  }

  // ---------- ADMIN ----------
  if (p === '/api/admin/stats' && m === 'GET') {
    if (!user || user.role !== 'owner') return json(res, 403, { error: 'Tylko właściciel.' });
    return json(res, 200, {
      stats: {
        users: db.users.filter((u) => u.role === 'client').length,
        projects: db.projects.length,
        inProgress: db.projects.filter((x) => x.status === 'agent' || x.status === 'analysis').length,
        prototypes: db.projects.filter((x) => x.status === 'prototype' || x.status === 'done').length,
        messages: db.messages.length,
        contacts: db.contacts.length,
        byStatus: {
          analysis: db.projects.filter((x) => x.status === 'analysis').length,
          agent: db.projects.filter((x) => x.status === 'agent').length,
          prototype: db.projects.filter((x) => x.status === 'prototype').length,
          done: db.projects.filter((x) => x.status === 'done').length,
        },
      },
      events: db.events.slice(-30).reverse(),
    });
  }
  if (p === '/api/admin/users' && m === 'GET') {
    if (!user || user.role !== 'owner') return json(res, 403, { error: 'Tylko właściciel.' });
    return json(res, 200, { users: db.users.map((u) => ({ ...publicUser(u), projects: db.projects.filter((x) => x.ownerId === u.id).length })) });
  }
  if (p === '/api/admin/contacts' && m === 'GET') {
    if (!user || user.role !== 'owner') return json(res, 403, { error: 'Tylko właściciel.' });
    return json(res, 200, { contacts: [...db.contacts].reverse() });
  }

  if (p === '/api/admin/gift-orders' && m === 'GET') {
    if (!user || user.role !== 'owner') return json(res, 403, { error: 'Tylko właściciel.' });
    return json(res, 200, { orders: [...db.giftOrders].reverse() });
  }
  if (p === '/api/admin/payments' && m === 'GET') {
    if (!user || user.role !== 'owner') return json(res, 403, { error: 'Tylko właściciel.' });
    return json(res, 200, { payments: [...db.payments].reverse().map((x) => ({ ...x, project: (db.projects.find((pr) => pr.id === x.projectId) || {}).name || '?' })) });
  }
  if (p === '/api/admin/report' && m === 'GET') {
    if (!user || user.role !== 'owner') return json(res, 403, { error: 'Tylko właściciel.' });
    const byStatus = { analysis: 0, agent: 0, prototype: 0, done: 0 };
    db.projects.forEach((x) => { if (byStatus[x.status] != null) byStatus[x.status]++; });
    const clients = db.users.filter((u) => u.role === 'client').length;
    const paid = db.quotes.filter((q) => q.status === 'paid').length;
    const approved = db.quotes.filter((q) => q.status === 'approved' || q.status === 'paid').length;
    let md = '# ⬢ RAPORT — WOJAN STUDIO\n\n';
    md += '> Masz pomysł? Zbudujmy go.\n\n';
    md += 'Wygenerowano: ' + now() + ' • wersja ' + APP_VERSION + '\n\n';
    md += '## Projekty (' + db.projects.length + ')\n';
    md += '- 🔵 Analiza: ' + byStatus.analysis + '\n- 🟡 Agent pracuje: ' + byStatus.agent + '\n- 🟢 Prototyp: ' + byStatus.prototype + '\n- ✅ Gotowe: ' + byStatus.done + '\n\n';
    md += '## Klienci i kontakt\n- Klienci: ' + clients + '\n- Zgłoszenia z formularza: ' + db.contacts.length + '\n- Zamówienia upominków/marketplace: ' + db.giftOrders.length + '\n\n';
    md += '## Wyceny i płatności\n- Wyceny łącznie: ' + db.quotes.length + '\n- Zatwierdzone: ' + approved + '\n- Opłacone: ' + paid + '\n\n';
    md += '## WOJAN RADIO\n- Utwory w bibliotece: ' + (db.media || []).length + '\n\n';
    md += '## Lista projektów\n';
    db.projects.forEach((x) => { md += '- **' + x.name + '** — ' + (STATUS_LABEL[x.status] || x.status) + ' (' + x.progress + '%), moduły: ' + x.modules + '\n'; });
    md += '\n---\nProjektujemy. Budujemy. Programujemy. Produkujemy. Tworzymy.\n';
    logEvent('report', 'generated by ' + user.email);
    res.writeHead(200, { 'Content-Type': 'text/markdown; charset=utf-8', 'Content-Disposition': 'attachment; filename="raport-wojan-studio.md"' });
    return res.end(md);
  }
  if (p === '/api/admin/backup' && m === 'GET') {
    if (!user || user.role !== 'owner') return json(res, 403, { error: 'Tylko właściciel.' });
    logEvent('backup', 'export by ' + user.email);
    res.writeHead(200, {
      'Content-Type': 'application/json; charset=utf-8',
      'Content-Disposition': 'attachment; filename="wojan-studio-backup-' + now().slice(0, 10) + '.json"',
    });
    return res.end(JSON.stringify(db, null, 2));
  }
  if (p === '/api/admin/events' && m === 'GET') {
    if (!user || user.role !== 'owner') return json(res, 403, { error: 'Tylko właściciel.' });
    const limit = Math.min(parseInt(url.searchParams.get('limit'), 10) || 200, 500);
    return json(res, 200, { events: [...db.events].reverse().slice(0, limit) });
  }

  // ---------- WYCENY (zatwierdza właściciel) ----------
  if (p === '/api/admin/quotes' && m === 'GET') {
    if (!user || user.role !== 'owner') return json(res, 403, { error: 'Tylko właściciel.' });
    return json(res, 200, { quotes: db.quotes.map((q) => ({ ...q, project: (db.projects.find((x) => x.id === q.projectId) || {}).name || '?' })) });
  }
  const qm = p.match(/^\/api\/quotes\/([\w-]+)$/);
  if (qm && m === 'PATCH') {
    if (!user || user.role !== 'owner') return json(res, 403, { error: 'Tylko właściciel.' });
    const q = db.quotes.find((x) => x.id === qm[1]);
    if (!q) return json(res, 404, { error: 'Nie znaleziono wyceny' });
    const wasApproved = q.status === 'approved';
    if (body.amount !== undefined) q.amount = String(body.amount).slice(0, 60);
    if (body.note !== undefined) q.note = String(body.note).slice(0, 300);
    if (body.status === 'approved' || body.status === 'draft') q.status = body.status;
    const proj = db.projects.find((x) => x.id === q.projectId);
    if (!wasApproved && q.status === 'approved' && proj) {
      notify(proj.ownerId, 'Wycena projektu „' + proj.name + '” została zatwierdzona: ' + (q.amount || 'indywidualnie'), 'success', proj.id);
    }
    logEvent('quotes', q.status + ' ' + q.id);
    saveDb();
    sseSend(q.projectId, 'update', { kind: 'quote' });
    return json(res, 200, { quote: q });
  }
  const qa = p.match(/^\/api\/quotes\/([\w-]+)\/accept$/);
  if (qa && m === 'POST') {
    if (!user) return json(res, 401, { error: 'Wymagane logowanie' });
    const q = db.quotes.find((x) => x.id === qa[1]);
    if (!q) return json(res, 404, { error: 'Nie znaleziono wyceny' });
    const proj = db.projects.find((x) => x.id === q.projectId);
    if (!proj || (user.role !== 'owner' && proj.ownerId !== user.id)) return json(res, 403, { error: 'Brak dostępu do tego projektu' });
    if (q.status !== 'approved') return json(res, 400, { error: 'Można zaakceptować tylko zatwierdzoną wycenę.' });
    q.status = 'accepted';
    q.acceptedAt = now();
    proj.progress = Math.max(proj.progress, 30);
    if (proj.status === 'analysis') proj.status = 'agent';
    proj.updatedAt = now();
    db.tasks.push({ id: uid(), projectId: proj.id, title: 'Start realizacji projektu (wycena zaakceptowana)', done: false });
    db.history.push({ id: uid(), projectId: proj.id, version: 'v0.' + (db.history.filter((h) => h.projectId === proj.id).length + 1), note: 'Klient zaakceptował wycenę (' + (q.amount || 'indywidualna') + ')', ts: now() });
    db.activity.push({ id: uid(), projectId: proj.id, text: 'Wycena zaakceptowana — projekt przechodzi do realizacji', ts: now() });
    db.messages.push({ id: uid(), projectId: proj.id, kind: 'agent', author: 'AI Agent', text: 'Wycena zaakceptowana ✅ Projekt przechodzi do fazy realizacji. Postęp zobaczysz w zakładkach AI AGENT i PREVIEW.', meta: null, ts: now() });
    const ownerUser = db.users.find((u) => u.role === 'owner');
    if (ownerUser && user.id !== ownerUser.id) notify(ownerUser.id, 'Klient zaakceptował wycenę projektu „' + proj.name + '”.', 'success', proj.id);
    logEvent('quotes', 'accepted ' + q.id);
    saveDb();
    sseSend(proj.id, 'update', { kind: 'quote' });
    return json(res, 200, { quote: q, project: proj });
  }

  // ---------- PORTFOLIO (zarządzanie) ----------
  if (p === '/api/admin/portfolio' && m === 'GET') {
    if (!user || user.role !== 'owner') return json(res, 403, { error: 'Tylko właściciel.' });
    return json(res, 200, { portfolio: db.portfolio || [] });
  }
  if (p === '/api/admin/portfolio' && m === 'POST') {
    if (!user || user.role !== 'owner') return json(res, 403, { error: 'Tylko właściciel.' });
    const it = {
      id: 'pf-' + uid(), img: body.img || 'img/p1.jpg', cat: String(body.cat || 'NOWY PROJEKT').slice(0, 40),
      title: String(body.title || 'Nowa realizacja').slice(0, 90), desc: String(body.desc || '').slice(0, 300),
      tech: Array.isArray(body.tech) ? body.tech.slice(0, 8) : [], result: String(body.result || '').slice(0, 160),
      enabled: body.enabled !== false,
    };
    db.portfolio.push(it);
    logEvent('portfolio', 'added ' + it.title);
    saveDb();
    return json(res, 200, { item: it });
  }
  const pfm = p.match(/^\/api\/admin\/portfolio\/([\w-]+)$/);
  if (pfm && (m === 'PATCH' || m === 'DELETE')) {
    if (!user || user.role !== 'owner') return json(res, 403, { error: 'Tylko właściciel.' });
    const i = (db.portfolio || []).findIndex((x) => x.id === pfm[1]);
    if (i < 0) return json(res, 404, { error: 'Nie znaleziono' });
    if (m === 'DELETE') { db.portfolio.splice(i, 1); saveDb(); return json(res, 200, { ok: true }); }
    const it = db.portfolio[i];
    for (const k of ['img', 'cat', 'title', 'desc', 'result']) if (body[k] !== undefined) it[k] = String(body[k]).slice(0, 400);
    if (Array.isArray(body.tech)) it.tech = body.tech.slice(0, 8);
    if (body.enabled !== undefined) it.enabled = !!body.enabled;
    saveDb();
    return json(res, 200, { item: it });
  }

  if (p === '/api/admin/core' && m === 'GET') {
    if (!user || user.role !== 'owner') return json(res, 403, { error: 'Tylko właściciel.' });
    return json(res, 200, {
      version: db.knowledge.version, samples: db.knowledge.samples,
      weights: Object.entries(db.knowledge.weights).sort((a, b) => b[1] - a[1]).slice(0, 14),
      log: db.knowledge.log.slice(-25).reverse(),
    });
  }

  // /api/agent/* — Coding Agent (LLM jeśli skonfigurowany, inaczej fallback/status)
  if (p.startsWith('/api/agent')) {
    if (p === '/api/agent/status' && m === 'GET') return json(res, 200, AGENT.status());
    if (p === '/api/agent/analyze' && m === 'POST') {
      const a = await AGENT.analyze(String(body.description || ''));
      if (!a) return json(res, 501, { error: 'Coding Agent bez klucza API — użyj /api/ai/analyze (WOJAN.CORE).', status: AGENT.status() });
      return json(res, 200, { analysis: a, engine: 'LLM:' + AGENT.status().provider });
    }
    if (p === '/api/agent/generate' && m === 'POST') {
      const g = await AGENT.generate(body.analysis || {});
      if (!g) return json(res, 501, { error: 'Coding Agent bez klucza API — generatory szablonowe aktywne.', status: AGENT.status() });
      return json(res, 200, g);
    }
    return json(res, 501, { error: 'Coding Agent nie jest jeszcze podłączony.', planned: ['plan', 'scaffold', 'generate', 'sandbox-run', 'test', 'preview', 'deploy'], status: AGENT.status() });
  }

  return json(res, 404, { error: 'Nie znaleziono endpointu' });
}

/* ----------------------------------------------------------- STATIC ----- */
function serveStatic(res, pathname) {
  let fp = path.normalize(path.join(ROOT, pathname === '/' ? 'index.html' : pathname));
  if (!fp.startsWith(ROOT)) { res.writeHead(403); return res.end('Forbidden'); }
  fs.stat(fp, (err, st) => {
    if (err || !st.isFile()) {
      // SPA fallback
      fp = path.join(ROOT, 'index.html');
    }
    const ext = path.extname(fp).toLowerCase();
    const cacheable = PROD && ['/css/', '/js/', '/img/'].some((d) => fp.includes(d));
    res.writeHead(200, securityHeaders({
      'Content-Type': MIME[ext] || 'application/octet-stream',
      'Cache-Control': cacheable ? 'public, max-age=86400' : 'no-cache',
    }));
    fs.createReadStream(fp).pipe(res);
  });
}

/* ------------------------------------------------------------ START ----- */
loadDb();
backfillArtifacts();
const server = http.createServer((req, res) => {
  const url = new URL(req.url, 'http://localhost');
  if (url.pathname.startsWith('/api/')) {
    api(req, res, url).catch((e) => {
      console.error('[api-error]', e);
      json(res, 500, { error: 'Błąd serwera' });
    });
    return;
  }
  serveStatic(res, url.pathname);
});
server.listen(PORT, HOST, () => {
  console.log(`⬢ WOJAN STUDIO — serwer MVP działa: http://${HOST}:${PORT}`);
  console.log(`  Klient demo:  demo@wojan.studio / demo123`);
  console.log(`  Właściciel:   wojan@wojan.studio / wojan123`);
});
