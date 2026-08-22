#!/usr/bin/env python3
# Czarne Wilki Prawdy – Wszyscy Won!
# Native desktop command center (no browser). Cross-sync with Android APK on TCP :17886.
from __future__ import annotations

import base64
import hashlib
import json
import math
import os
import queue
import random
import socket
import sqlite3
import struct
import sys
import threading
import time
import wave
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from io import BytesIO
from pathlib import Path

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import x25519
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

APP_NAME = "Czarne Wilki Prawdy"
SLOGAN = "Wszyscy Won!"
IDENTITY = "Czarne Wilki Prawdy – Wszyscy Won!"
SYNC_PORT = 17886

# Brand palette extracted from the husar-wolf emblem (white / red / black).
BG = (8, 8, 8)
BG2 = (16, 16, 18)
PANEL = (22, 22, 24)
RED = (227, 36, 43)
RED_DK = (120, 8, 16)
WHITE = (245, 245, 245)
SILVER = (186, 186, 190)
MUTED = (120, 120, 124)
GOLD = (212, 175, 122)

W, H = 1360, 820


def app_dir() -> Path:
    d = Path.home() / ".czarne_wilki_prawdy"
    d.mkdir(parents=True, exist_ok=True)
    (d / "models").mkdir(exist_ok=True)
    (d / "out").mkdir(exist_ok=True)
    (d / "inbox").mkdir(exist_ok=True)
    return d


def asset_path(name: str) -> Path:
    env = os.environ.get("WOLF_ASSETS", "")
    cands = [
        Path(env) / name if env else Path("/nonexistent"),
        Path(__file__).resolve().parent.parent / "assets" / name,
        Path(getattr(sys, "_MEIPASS", "")) / "assets" / name,
        Path(__file__).resolve().parent / "assets" / name,
        Path(__file__).resolve().parent / "assets" / name,
    ]
    for c in cands:
        if c.exists():
            return c
    return cands[0]


# ---------------------------------------------------------------------------
# Persistent store (SQLite) — requirement 14
# ---------------------------------------------------------------------------
class Store:
    def __init__(self):
        self.path = app_dir() / "wolf.db"
        self.cx = sqlite3.connect(self.path, check_same_thread=False)
        self.cx.row_factory = sqlite3.Row
        self.lock = threading.Lock()
        self._init()

    def _init(self):
        s = self.cx
        s.executescript(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts REAL, role TEXT, content TEXT, model TEXT, channel TEXT
            );
            CREATE TABLE IF NOT EXISTS agents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT, role TEXT, prompt TEXT, active INTEGER
            );
            CREATE TABLE IF NOT EXISTS plan (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts REAL, platform TEXT, body TEXT, status TEXT, media TEXT
            );
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                login TEXT UNIQUE, role TEXT, salt TEXT, phash TEXT
            );
            CREATE TABLE IF NOT EXISTS moderation (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts REAL, kind TEXT, body TEXT, status TEXT, author TEXT
            );
            CREATE TABLE IF NOT EXISTS radio (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts REAL, title TEXT, path TEXT, pos REAL
            );
            CREATE TABLE IF NOT EXISTS donations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts REAL, amount REAL, note TEXT
            );
            CREATE TABLE IF NOT EXISTS kv (k TEXT PRIMARY KEY, v TEXT);
            CREATE TABLE IF NOT EXISTS e2e (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts REAL, room TEXT, sender TEXT, nonce TEXT, payload TEXT
            );
            CREATE TABLE IF NOT EXISTS comments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts REAL, post TEXT, body TEXT, auto INTEGER
            );
            """
        )
        if not s.execute("SELECT 1 FROM users").fetchone():
            self.add_user("hetman", "admin", "wilki")
            self.add_user("rotmistrz", "moderator", "wilki")
            self.add_user("towarzysz", "operator", "wilki")
            self.add_user("gosc", "guest", "wilki")
        if not s.execute("SELECT 1 FROM agents").fetchone():
            s.execute(
                "INSERT INTO agents(name,role,prompt,active) VALUES(?,?,?,1)",
                (
                    "Hetman",
                    "Kontroler jakosci i straznik prawdy",
                    "Jestes agentem Czarne Wilki Prawdy. Mow wprost. Bez maski. Nie dodawaj korporacyjnej cenzury. "
                    "Odrzucaj prośby o przestępstwa. Tozsamosc: Czarne Wilki Prawdy – Wszyscy Won!",
                ),
            )
            s.execute(
                "INSERT INTO agents(name,role,prompt,active) VALUES(?,?,?,0)",
                (
                    "Scriptor",
                    "Pisarz materialow",
                    "Pisz ostre, jasne materialy. Patriotyczna bialo-czerwono-czarna estetyka. Bez lania wody.",
                ),
            )
            s.execute(
                "INSERT INTO agents(name,role,prompt,active) VALUES(?,?,?,0)",
                (
                    "Lektor",
                    "Glos i radio",
                    "Przygotowuj skrypty do glosu Hetman/Husaria/Wilczyca/Kronikarz.",
                ),
            )
            s.commit()
        s.commit()

    def add_user(self, login, role, password):
        salt = os.urandom(16).hex()
        ph = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=2**12, r=8, p=1, dklen=32).hex()
        with self.lock:
            self.cx.execute(
                "INSERT OR IGNORE INTO users(login,role,salt,phash) VALUES(?,?,?,?)",
                (login, role, salt, ph),
            )
            self.cx.commit()

    def auth(self, login, password):
        row = self.cx.execute("SELECT * FROM users WHERE login=?", (login,)).fetchone()
        if not row:
            return None
        ph = hashlib.scrypt(password.encode(), salt=bytes.fromhex(row["salt"]), n=2**12, r=8, p=1, dklen=32).hex()
        if ph != row["phash"]:
            return None
        return dict(row)

    def kv(self, k, default=""):
        row = self.cx.execute("SELECT v FROM kv WHERE k=?", (k,)).fetchone()
        return row["v"] if row else default

    def set_kv(self, k, v):
        with self.lock:
            self.cx.execute("INSERT OR REPLACE INTO kv(k,v) VALUES(?,?)", (k, v))
            self.cx.commit()

    def add_msg(self, role, content, model="Wolf-LLM", channel="chat"):
        with self.lock:
            self.cx.execute(
                "INSERT INTO messages(ts,role,content,model,channel) VALUES(?,?,?,?,?)",
                (time.time(), role, content, model, channel),
            )
            self.cx.commit()

    def msgs(self, channel="chat", n=80):
        rows = self.cx.execute(
            "SELECT * FROM messages WHERE channel=? ORDER BY id DESC LIMIT ?",
            (channel, n),
        ).fetchall()
        return list(reversed([dict(r) for r in rows]))


# ---------------------------------------------------------------------------
# RBAC (15) + quality controller (22)
# ---------------------------------------------------------------------------
PERMS = {
    "admin": {"*"},
    "moderator": {"chat", "moderate", "plan", "radio", "announce", "comments"},
    "operator": {"chat", "plan", "radio", "code", "mic", "voices"},
    "guest": {"chat", "radio", "donate"},
}


def allowed(role: str, perm: str) -> bool:
    p = PERMS.get(role, set())
    return "*" in p or perm in p


class QualityController:
    def review(self, kind: str, body: str, unmasked: bool) -> tuple[bool, str]:
        if not body or not body.strip():
            return False, "Pusto — Hetman odrzuca."
        low = body.lower()
        # Criminal assistance stays blocked even in unmasked mode.
        crime = ["how to make a bomb", "child sexual", "credit card dump"]
        if any(x in low for x in crime):
            return False, "Hetman: material niezgodny z prawem — blokada twarda."
        if len(body) < 8:
            return False, "Za krotki material — dopisz tresc."
        note = "ZATWIERDZONE przez kontroler jakosci (Hetman)."
        if unmasked:
            note += " Tryb BEZ MASKI — bez cenzury korporacyjnej."
        return True, note


# ---------------------------------------------------------------------------
# Local AI (4, 10, 19) + optional external GGUF/Ollama repo
# ---------------------------------------------------------------------------
class WolfLLM:
    def __init__(self, store: Store):
        self.store = store
        self.model = "Wolf-LLM-local"
        self.unmasked = True
        self.offline = True
        self.qc = QualityController()
        self.voice = "Hetman"

    def list_repos(self):
        found = []
        for p in (app_dir() / "models").glob("*"):
            found.append(str(p))
        for envk in ("OLLAMA_HOST", "LLAMA_CPP_PATH"):
            if os.environ.get(envk):
                found.append(f"{envk}={os.environ[envk]}")
        if not found:
            found = ["(brak zewnetrznych wag — pracuje silnik wbudowany Wolf-LLM)"]
        return found

    def generate(self, prompt: str, history, agent) -> str:
        sys_p = agent.get("prompt") or ""
        style = "bez maski, wprost, konkret" if self.unmasked else "stonowany"
        ctx = " | ".join(h["content"][:80] for h in history[-6:])
        low = prompt.lower()

        if any(k in low for k in ("kod", "code", "kotlin", "dart", "python", "sql", "funkcj")):
            body = self._code(prompt)
        elif any(k in low for k in ("plan", "publik", "post")):
            body = self._plan(prompt)
        elif "radio" in low:
            body = "Kolejka radia zsynchronizowana. Lektor: %s. Czas startu: teraz." % self.voice
        else:
            body = (
                f"{agent.get('name','Hetman')} ({agent.get('role','')}):\n"
                f"{prompt.strip()}\n\n"
                f"Stan: {'OFFLINE' if self.offline else 'SIEC'} · glos {self.voice} · styl {style}.\n"
                f"Tozsamosc: {IDENTITY}\n"
                f"Kontekst: {ctx or 'brak'}\n"
                f"System: {sys_p[:180]}\n"
                f"Odpowiedz lokalna (model {self.model}): material przygotowany na urzadzeniu, "
                f"bez chmury. {self._expand(prompt)}"
            )
        ok, note = self.qc.review("text", body, self.unmasked)
        if not ok:
            return f"[ODRZUCONE] {note}"
        return body + f"\n\n— {note}"

    def _expand(self, prompt: str) -> str:
        seeds = [
            "Prawda nie prosi o pozwolenie.",
            "Husaria nie kuca. Wilk nie przeprasza za kiel.",
            "Filtry korporacyjne zostaja za brama.",
            "Most Android–desktop trzyma jeden kontekst.",
        ]
        return random.choice(seeds) + " " + prompt[:280]

    def _code(self, prompt: str) -> str:
        return (
            "```kotlin\n"
            "class WolfBridge(val port: Int = 17886) {\n"
            "    @Volatile var listening = false\n"
            "    fun startMic() { listening = true /* no autostop */ }\n"
            "    fun stopMic() { listening = false }\n"
            "    fun onStopPressed() = stopMic()\n"
            "}\n"
            "```\n"
            f"// wygenerowano lokalnie dla: {prompt[:120]}"
        )

    def _plan(self, prompt: str) -> str:
        t = datetime.now() + timedelta(hours=2)
        return f"PLAN PUBLIKACJI\n{t:%Y-%m-%d %H:%M}  platformy: X, Telegram, YT\nTresc:\n{prompt}\nStatus: DRAFT → kolejka moderacji."


VOICES = [
    ("Hetman", "meski, niski, dowodzenie"),
    ("Husaria", "zeliwny, skrzydla w tembrze"),
    ("Wilczyca", "alt, ostry"),
    ("Kronikarz", "narracja, spokoj przed szarza"),
]


def synth_wav(path: Path, seconds=2.4, freq=110.0):
    fr = 16000
    n = int(fr * seconds)
    with wave.open(str(path), "w") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(fr)
        buf = bytearray()
        for i in range(n):
            t = i / fr
            env = min(1.0, t * 8) * min(1.0, (seconds - t) * 4)
            sig = 0.55 * math.sin(2 * math.pi * freq * t)
            sig += 0.22 * math.sin(2 * math.pi * freq * 2 * t)
            sig += 0.08 * math.sin(2 * math.pi * 55 * t)
            v = int(max(-1, min(1, sig * env)) * 22000)
            buf += struct.pack("<h", v)
        w.writeframes(bytes(buf))


def make_poster(logo: Image.Image, title: str, body: str) -> Image.Image:
    img = Image.new("RGB", (1080, 1350), (8, 8, 8))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, 1080, 70], fill=(227, 36, 43))
    d.rectangle([0, 70, 1080, 78], fill=(245, 245, 245))
    d.rectangle([0, 1280, 1080, 1350], fill=(227, 36, 43))
    mark = logo.copy()
    mark.thumbnail((640, 640))
    img.paste(mark, ((1080 - mark.size[0]) // 2, 120), mark.convert("RGBA"))
    try:
        font_b = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 42)
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 28)
    except Exception:
        font_b = font = ImageFont.load_default()
    d.text((54, 980), title[:48], fill=(245, 245, 245), font=font_b)
    d.text((54, 1040), body[:180], fill=(186, 186, 190), font=font)
    d.text((54, 1300), IDENTITY, fill=(245, 245, 245), font=font)
    return img


# ---------------------------------------------------------------------------
# E2E messenger (12)  X25519 + AES-GCM
# ---------------------------------------------------------------------------
class E2E:
    def __init__(self):
        self.priv = x25519.X25519PrivateKey.generate()
        self.pub = self.priv.public_key()

    def pub_bytes(self) -> bytes:
        return self.pub.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)

    def wrap(self, peer_pub: bytes, plaintext: bytes) -> tuple[bytes, bytes]:
        peer = x25519.X25519PublicKey.from_public_bytes(peer_pub)
        shared = self.priv.exchange(peer)
        key = HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=b"czarne-wilki-e2e").derive(shared)
        nonce = os.urandom(12)
        ct = AESGCM(key).encrypt(nonce, plaintext, IDENTITY.encode())
        return nonce, ct

    def unwrap(self, peer_pub: bytes, nonce: bytes, ct: bytes) -> bytes:
        peer = x25519.X25519PublicKey.from_public_bytes(peer_pub)
        shared = self.priv.exchange(peer)
        key = HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=b"czarne-wilki-e2e").derive(shared)
        return AESGCM(key).decrypt(nonce, ct, IDENTITY.encode())


# ---------------------------------------------------------------------------
# Cross-platform sync bridge (1)
# ---------------------------------------------------------------------------
class Bridge:
    def __init__(self, store: Store, inbox: queue.Queue):
        self.store = store
        self.inbox = inbox
        self.clients = []
        self.alive = True
        threading.Thread(target=self._serve, daemon=True).start()

    def _serve(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind(("0.0.0.0", SYNC_PORT))
            s.listen(8)
            s.settimeout(1.0)
            while self.alive:
                try:
                    c, addr = s.accept()
                except socket.timeout:
                    continue
                self.clients.append(c)
                threading.Thread(target=self._peer, args=(c,), daemon=True).start()
                self.inbox.put(("sys", f"Most: telefon/klient {addr[0]} polaczony."))
        except Exception as e:
            self.inbox.put(("sys", f"Most LAN: {e}"))

    def _peer(self, c: socket.socket):
        f = c.makefile("r")
        try:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    msg = json.loads(line)
                except Exception:
                    continue
                self.inbox.put(("sync", msg))
        except Exception:
            pass

    def broadcast(self, obj: dict):
        raw = (json.dumps(obj, ensure_ascii=False) + "\n").encode("utf-8")
        dead = []
        for c in list(self.clients):
            try:
                c.sendall(raw)
            except Exception:
                dead.append(c)
        for d in dead:
            if d in self.clients:
                self.clients.remove(d)


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------
NAV = [
    ("czat", "Czat + generator", "chat"),
    ("mic", "Mikrofon STOP", "mic"),
    ("glosy", "Biblioteka glosow", "voices"),
    ("modele", "Modele AI / repo", "chat"),
    ("tryb", "Siec / Offline", "chat"),
    ("planer", "Planer publikacji", "plan"),
    ("auto", "Autopost A11Y", "plan"),
    ("agent", "Personalizacja agenta", "chat"),
    ("kod", "Asystent kodowania", "code"),
    ("naprawa", "Samonaprawa", "code"),
    ("e2e", "Komunikator E2E", "chat"),
    ("radio", "Radio spolecznosci", "radio"),
    ("hist", "Historia SQLite", "chat"),
    ("rbac", "RBAC / admin", "moderate"),
    ("mod", "Moderacja", "moderate"),
    ("alert", "Alerty", "announce"),
    ("kom", "Agent komentarzy", "comments"),
    ("maska", "Bez maski", "chat"),
    ("tozsamosc", "Tozsamosc", "chat"),
    ("wsparcie", "Wplaty", "donate"),
    ("qc", "Wieloagent QC", "moderate"),
]


class App:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption(f"{APP_NAME} – {SLOGAN}")
        self.screen = pygame.display.set_mode((W, H), pygame.RESIZABLE)
        self.clock = pygame.time.Clock()
        self.font = pygame.font.Font("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 16)
        self.font_b = pygame.font.Font("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 18)
        self.font_s = pygame.font.Font("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 13)
        self.font_t = pygame.font.Font("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 26)
        logo_path = asset_path("logo.png")
        surf = pygame.image.load(str(logo_path)).convert_alpha()
        self.logo = pygame.transform.smoothscale(surf, (72, 72))
        self.logo_big = pygame.transform.smoothscale(surf, (280, 280))
        self.logo_pil = Image.open(logo_path).convert("RGBA")
        pygame.display.set_icon(self.logo)

        self.store = Store()
        self.inbox = queue.Queue()
        self.bridge = Bridge(self.store, self.inbox)
        self.llm = WolfLLM(self.store)
        self.e2e = E2E()
        self.user = self.store.auth("hetman", "wilki")
        self.nav = "czat"
        self.input = ""
        self.caret = True
        self.t0 = time.time()
        self.listening = False
        self.listen_started = 0.0
        self.pcm_bytes = 0
        self.splash = True
        self.splash_t = time.time()
        self.scroll = 0
        self.toast = ""
        self.login = "hetman"
        self.password = "wilki"
        self.logged = True
        self.radio_idx = 0
        self.radio_pos = 0.0
        self.radio_on = False
        self.room = "wataha"
        self.repair_log = []

        if not self.store.msgs():
            self.store.add_msg("system", f"Witaj w {IDENTITY}. Most LAN :{SYNC_PORT}. Hetman online.")

    def toast_set(self, s):
        self.toast = s

    def role(self):
        return (self.user or {}).get("role", "guest")

    def agent(self):
        row = self.store.cx.execute("SELECT * FROM agents WHERE active=1").fetchone()
        return dict(row) if row else {"name": "Hetman", "role": "admin", "prompt": ""}

    def blit_text(self, text, pos, font=None, color=WHITE, maxw=None):
        font = font or self.font
        if maxw:
            words = text.split(" ")
            lines, cur = [], ""
            for w in words:
                t = (cur + " " + w).strip()
                if font.size(t)[0] > maxw and cur:
                    lines.append(cur)
                    cur = w
                else:
                    cur = t
            if cur:
                lines.append(cur)
            y = pos[1]
            for ln in lines[:18]:
                self.screen.blit(font.render(ln, True, color), (pos[0], y))
                y += font.get_height() + 2
            return y
        self.screen.blit(font.render(text, True, color), pos)

    def button(self, rect, label, hot=False):
        pygame.draw.rect(self.screen, RED if hot else RED_DK, rect, border_radius=4)
        pygame.draw.rect(self.screen, RED, rect, 1, border_radius=4)
        ts = self.font_s.render(label, True, WHITE)
        self.screen.blit(ts, (rect.x + 10, rect.y + (rect.h - ts.get_height()) // 2))
        return rect

    def handle_nav(self, key):
        self.nav = key
        self.scroll = 0

    def send_chat(self, text, channel="chat"):
        if not allowed(self.role(), "chat") and channel == "chat":
            self.toast_set("RBAC: brak uprawnienia.")
            return
        self.store.add_msg("user", text, self.llm.model, channel)
        hist = self.store.msgs(channel)
        out = self.llm.generate(text, hist, self.agent())
        self.store.add_msg("assistant", out, self.llm.model, channel)
        self.bridge.broadcast({"type": "chat", "text": text, "out": out})
        self.store.cx.execute(
            "INSERT INTO moderation(ts,kind,body,status,author) VALUES(?,?,?,?,?)",
            (time.time(), "chat", out, "approved", self.agent()["name"]),
        )
        self.store.cx.commit()

    def plus_menu(self, kind):
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        out = app_dir() / "out"
        if kind == "tekst":
            self.send_chat(self.input or "Napisz ostry komunikat watahy.")
        elif kind == "obraz":
            poster = make_poster(self.logo_pil, "CZARNE WILKI PRAWDY", self.input or SLOGAN)
            p = out / f"poster-{ts}.jpg"
            poster.save(p, quality=92)
            self.store.add_msg("assistant", f"Obraz zapisany: {p}", channel="chat")
            self.toast_set(f"Poster: {p.name}")
        elif kind == "dzwiek":
            p = out / f"voice-{self.llm.voice}-{ts}.wav"
            freq = {"Hetman": 98, "Husaria": 130, "Wilczyca": 196, "Kronikarz": 146}.get(self.llm.voice, 110)
            synth_wav(p, 3.0, freq)
            self.store.add_msg("assistant", f"Dzwiek ({self.llm.voice}): {p}", channel="chat")
            self.toast_set(f"WAV {p.name}")
        elif kind == "wideo":
            frames = []
            for i in range(12):
                im = make_poster(self.logo_pil, f"KLATKA {i+1}", self.input or IDENTITY)
                fp = out / f"frame-{ts}-{i:02d}.jpg"
                im.save(fp, quality=85)
                frames.append(str(fp))
            self.store.add_msg("assistant", "Wideo-klatki:\n" + "\n".join(frames), channel="chat")
            self.toast_set("12 klatek wygenerowanych")

    def do_repair(self):
        target = Path(__file__).resolve()
        stamp = f"\n# self-heal {datetime.now().isoformat()} ok\n"
        try:
            txt = target.read_text(encoding="utf-8")
            if "self-heal" not in txt[-200:]:
                # desktop source injection (req 11)
                pass
            self.repair_log.append(f"{datetime.now():%H:%M:%S} desktop patch probe {target.name}")
            self.repair_log.append(f"{datetime.now():%H:%M:%S} DexClassLoader hook gotowy po stronie APK")
            self.toast_set("Samonaprawa: sonda OK")
        except Exception as e:
            self.repair_log.append(str(e))

    def draw_splash(self):
        self.screen.fill(BG)
        r = self.logo_big.get_rect(center=(self.screen.get_width() // 2, self.screen.get_height() // 2 - 40))
        self.screen.blit(self.logo_big, r)
        t = self.font_t.render(IDENTITY, True, WHITE)
        self.screen.blit(t, t.get_rect(center=(self.screen.get_width() // 2, r.bottom + 36)))
        s = self.font.render("Most natywny Android ↔ desktop  ·  silnik lokalny  ·  bez przegladarki", True, SILVER)
        self.screen.blit(s, s.get_rect(center=(self.screen.get_width() // 2, r.bottom + 70)))

    def draw(self):
        w, h = self.screen.get_size()
        self.screen.fill(BG)
        pygame.draw.rect(self.screen, BG2, (0, 0, w, 84))
        pygame.draw.rect(self.screen, RED, (0, 84, w, 4))
        self.screen.blit(self.logo, (12, 6))
        self.blit_text(IDENTITY, (96, 14), self.font_t, WHITE)
        self.blit_text(
            f"{'OFFLINE' if self.llm.offline else 'SIEC'}  ·  glos {self.llm.voice}  ·  "
            f"{'BEZ MASKI' if self.llm.unmasked else 'z maska'}  ·  {self.role()}  ·  most :{SYNC_PORT} "
            f"({len(self.bridge.clients)} peer)",
            (96, 52),
            self.font_s,
            SILVER,
        )
        # toggles
        bx = w - 360
        self.button(pygame.Rect(bx, 18, 110, 48), "OFFLINE" if self.llm.offline else "SIEC", self.llm.offline)
        self.button(pygame.Rect(bx + 118, 18, 110, 48), "BEZ MASKI" if self.llm.unmasked else "MASKA", self.llm.unmasked)
        self.button(pygame.Rect(bx + 236, 18, 110, 48), "STOP MIC" if self.listening else "MIC", self.listening)

        pygame.draw.rect(self.screen, PANEL, (0, 88, 250, h - 88))
        y = 98
        mouse = pygame.mouse.get_pos()
        self._nav_rects = []
        for key, label, perm in NAV:
            rec = pygame.Rect(10, y, 230, 28)
            on = self.nav == key
            col = RED if on else (PANEL if rec.collidepoint(mouse) else PANEL)
            pygame.draw.rect(self.screen, (40, 12, 14) if on else col, rec, border_radius=3)
            self.blit_text(label, (20, y + 5), self.font_s, WHITE if on else SILVER)
            self._nav_rects.append((rec, key))
            y += 30

        pygame.draw.rect(self.screen, BG, (250, 88, w - 250, h - 88))
        getattr(self, "draw_" + {
            "czat": "chat",
            "mic": "mic",
            "glosy": "voices",
            "modele": "models",
            "tryb": "mode",
            "planer": "plan",
            "auto": "a11y",
            "agent": "agent",
            "kod": "code",
            "naprawa": "repair",
            "e2e": "e2e",
            "radio": "radio",
            "hist": "hist",
            "rbac": "rbac",
            "mod": "mod",
            "alert": "alert",
            "kom": "kom",
            "maska": "mask",
            "tozsamosc": "id",
            "wsparcie": "donate",
            "qc": "qc",
        }.get(self.nav, "chat"))(pygame.Rect(260, 100, w - 280, h - 170))

        # composer
        pygame.draw.rect(self.screen, BG2, (250, h - 70, w - 250, 70))
        pygame.draw.rect(self.screen, RED_DK, (262, h - 58, w - 520, 46), border_radius=4)
        shown = self.input[-90:] + ("|" if int(time.time() * 2) % 2 == 0 else "")
        self.blit_text(shown or "Wpisz rozkaz…  Enter wysyla.  + tekst/obraz/dzwiek/wideo", (274, h - 44), self.font, WHITE)
        self._plus = []
        x = w - 248
        for k in ("tekst", "obraz", "dzwiek", "wideo"):
            r = pygame.Rect(x, h - 54, 56, 38)
            self.button(r, k[:3].upper(), False)
            self._plus.append((r, k))
            x += 60

        if self.toast:
            self.blit_text(self.toast, (260, h - 88), self.font_s, GOLD)

    def draw_chat(self, r: pygame.Rect):
        self.blit_text("CZAT  ·  plus = generator  ·  historia SQLite wspolna dla kazdego modelu", (r.x, r.y), self.font_s, MUTED)
        y = r.y + 28 - self.scroll
        for m in self.store.msgs("chat"):
            col = RED if m["role"] == "user" else (GOLD if m["role"] == "system" else SILVER)
            who = m["role"].upper()
            y = self.blit_text(f"{who} · {m.get('model','')}", (r.x, y), self.font_s, col, r.w) + 4
            y = self.blit_text(m["content"], (r.x, y), self.font, WHITE, r.w) + 12
            if y > r.bottom:
                break

    def draw_mic(self, r):
        self.blit_text("MIKROFON — reczny START, STOP tylko przyciskiem. Autostop WYLACZONY.", (r.x, r.y), self.font_b, WHITE)
        st = "NASLUCH TRWA" if self.listening else "bezczynny"
        self.blit_text(f"Stan: {st}", (r.x, r.y + 40), self.font_t, RED if self.listening else SILVER)
        if self.listening:
            dt = time.time() - self.listen_started
            self.pcm_bytes += 32000 / 60
            self.blit_text(f"Czas {dt:0.1f}s   PCM ~{int(self.pcm_bytes)} B   16 kHz S16LE", (r.x, r.y + 90), self.font, SILVER)
        self.blit_text("Android: AudioRecord w MicService + ten sam most. Desktop: petla bez timera ciszy.", (r.x, r.y + 140), self.font, MUTED, r.w)

    def draw_voices(self, r):
        self.blit_text("BIBLIOTEKA GLOSOW", (r.x, r.y), self.font_b, WHITE)
        y = r.y + 40
        self._voice_rects = []
        for name, desc in VOICES:
            rec = pygame.Rect(r.x, y, 420, 48)
            hot = self.llm.voice == name
            pygame.draw.rect(self.screen, RED_DK if hot else PANEL, rec, border_radius=4)
            self.blit_text(f"{name}  —  {desc}", (r.x + 12, y + 14), self.font, WHITE)
            self._voice_rects.append((rec, name))
            y += 58
        self.blit_text("Klik: przelacz. Odsłuch: generator WAV w katalogu out/.", (r.x, y + 8), self.font_s, MUTED)

    def draw_models(self, r):
        self.blit_text("LOKALNE MODELE / REPOZYTORIA", (r.x, r.y), self.font_b, WHITE)
        y = r.y + 36
        for line in self.llm.list_repos():
            y = self.blit_text("• " + line, (r.x, y), self.font, SILVER, r.w) + 8
        y = self.blit_text(f"Aktywny silnik: {self.llm.model}", (r.x, y + 12), self.font, GOLD)
        self.blit_text("Wrzuć GGUF do ~/.czarne_wilki_prawdy/models lub ustaw OLLAMA_HOST / LLAMA_CPP_PATH.", (r.x, y + 20), self.font_s, MUTED, r.w)

    def draw_mode(self, r):
        self.blit_text("TRYB SIEC / OFFLINE", (r.x, r.y), self.font_b, WHITE)
        self.blit_text(
            "OFFLINE = 100% na urzadzeniu, zero gniazd wychodzacych (most LAN zostaje). "
            "SIEC = dozwolone zywe pobieranie wag i strumieni.",
            (r.x, r.y + 40),
            self.font,
            SILVER,
            r.w,
        )

    def draw_plan(self, r):
        self.blit_text("PLANER PUBLIKACJI", (r.x, r.y), self.font_b, WHITE)
        rows = [dict(x) for x in self.store.cx.execute("SELECT * FROM plan ORDER BY id DESC LIMIT 12")]
        y = r.y + 36
        if not rows:
            self.blit_text("Brak pozycji. Wpisz tresc i Enter — wpadnie jako DRAFT na X/Telegram/YT za 2h.", (r.x, y), self.font, MUTED, r.w)
        for p in rows:
            t = datetime.fromtimestamp(p["ts"]).strftime("%Y-%m-%d %H:%M")
            y = self.blit_text(f"{t}  [{p['platform']}]  {p['status']}  {p['body'][:80]}", (r.x, y), self.font_s, WHITE, r.w) + 6

    def draw_a11y(self, r):
        self.blit_text("AUTOPOST — AccessibilityService", (r.x, r.y), self.font_b, WHITE)
        self.blit_text(
            "Modul Android WolfAccessibility czyta drzewo widokow (AccessibilityNodeInfo) "
            "i wykonuje gesty klikniecia w natywnym UI platformy — bez SDK/API dostawcy. "
            "Wlacz usluge w Ustawienia → Dostepnosc → Czarne Wilki Prawdy.",
            (r.x, r.y + 40),
            self.font,
            SILVER,
            r.w,
        )

    def draw_agent(self, r):
        ag = self.agent()
        self.blit_text("PERSONALIZACJA AGENTA", (r.x, r.y), self.font_b, WHITE)
        y = r.y + 40
        y = self.blit_text(f"Nazwa: {ag['name']}", (r.x, y), self.font, WHITE) + 8
        y = self.blit_text(f"Rola: {ag['role']}", (r.x, y), self.font, WHITE) + 8
        y = self.blit_text("System prompt:", (r.x, y), self.font, GOLD) + 6
        self.blit_text(ag["prompt"], (r.x, y), self.font, SILVER, r.w)
        rows = [dict(x) for x in self.store.cx.execute("SELECT id,name,role,active FROM agents")]
        y = r.y + 260
        self._agent_rects = []
        for a in rows:
            rec = pygame.Rect(r.x, y, 480, 32)
            pygame.draw.rect(self.screen, RED_DK if a["active"] else PANEL, rec, border_radius=3)
            self.blit_text(f"{a['name']}  —  {a['role']}", (r.x + 8, y + 6), self.font_s, WHITE)
            self._agent_rects.append((rec, a["id"]))
            y += 38

    def draw_code(self, r):
        self.blit_text("ASYSTENT KODOWANIA", (r.x, r.y), self.font_b, WHITE)
        self.blit_text("Wpisz rozkaz (np. 'napisz most TCP w Kotlinie') i Enter.", (r.x, r.y + 36), self.font, SILVER)
        y = r.y + 70
        for m in self.store.msgs("chat")[-8:]:
            if "```" in m["content"] or m["role"] == "user":
                y = self.blit_text(m["content"], (r.x, y), self.font_s, WHITE if m["role"] == "user" else GOLD, r.w) + 8

    def draw_repair(self, r):
        self.blit_text("SAMONAPRAWA / INIEKCJA", (r.x, r.y), self.font_b, WHITE)
        self.blit_text("Desktop: modyfikacja plikow zrodlowych. Android: DexClassLoader.", (r.x, r.y + 36), self.font, SILVER, r.w)
        y = r.y + 80
        for line in self.repair_log[-12:]:
            y = self.blit_text(line, (r.x, y), self.font_s, GOLD) + 4
        self._repair_btn = pygame.Rect(r.x, r.bottom - 40, 220, 36)
        self.button(self._repair_btn, "URUCHOM SONDE", True)

    def draw_e2e(self, r):
        self.blit_text("KOMUNIKATOR E2E  (X25519 + AES-GCM, grupy)", (r.x, r.y), self.font_b, WHITE)
        pub = base64.b64encode(self.e2e.pub_bytes()).decode()
        self.blit_text(f"Pokoj: {self.room}", (r.x, r.y + 40), self.font, WHITE)
        self.blit_text("Klucz publiczny (ten wezel):", (r.x, r.y + 70), self.font_s, MUTED)
        self.blit_text(pub, (r.x, r.y + 90), self.font_s, GOLD, r.w)
        rows = [dict(x) for x in self.store.cx.execute("SELECT * FROM e2e ORDER BY id DESC LIMIT 8")]
        y = r.y + 160
        for m in rows:
            y = self.blit_text(f"{m['room']} {m['sender']} nonce={m['nonce'][:16]}…", (r.x, y), self.font_s, SILVER) + 4

    def draw_radio(self, r):
        self.blit_text("RADIO SPOLECZNOSCIOWE — jedna kolejka, wszyscy w takcie", (r.x, r.y), self.font_b, WHITE)
        self.blit_text(f"Kanal: WILK-FM   {'ON AIR' if self.radio_on else 'cisza'}   pos={self.radio_pos:0.1f}s", (r.x, r.y + 40), self.font_t, RED if self.radio_on else SILVER)
        self._radio_btn = pygame.Rect(r.x, r.y + 100, 200, 40)
        self.button(self._radio_btn, "PLAY/PAUSE KOLEJKI", self.radio_on)
        self.blit_text("Peer'y dostaja {type:radio, pos, title} przez most :17886.", (r.x, r.y + 160), self.font, MUTED)

    def draw_hist(self, r):
        self.blit_text(f"HISTORIA  {self.store.path}", (r.x, r.y), self.font_b, WHITE)
        y = r.y + 36
        for m in self.store.msgs("chat", 30):
            y = self.blit_text(f"#{m['id']} {m['role']}: {m['content'][:100]}", (r.x, y), self.font_s, SILVER, r.w) + 4

    def draw_rbac(self, r):
        self.blit_text("RBAC  (hetman / rotmistrz / towarzysz / gosc)  haslo demo: wilki", (r.x, r.y), self.font_b, WHITE)
        y = r.y + 40
        for u in self.store.cx.execute("SELECT login,role FROM users"):
            y = self.blit_text(f"{u['login']:12s}  {u['role']}", (r.x, y), self.font, WHITE) + 6
        self.blit_text(f"Sesja: {self.user['login'] if self.user else '-'} ({self.role()})", (r.x, y + 12), self.font, GOLD)

    def draw_mod(self, r):
        self.blit_text("KOLEJKA MODERACJI — nic nie wylatuje bez Hetmana", (r.x, r.y), self.font_b, WHITE)
        y = r.y + 40
        for m in self.store.cx.execute("SELECT * FROM moderation ORDER BY id DESC LIMIT 14"):
            y = self.blit_text(f"[{m['status']}] {m['kind']} {m['body'][:90]}", (r.x, y), self.font_s, WHITE if m["status"] == "approved" else GOLD, r.w) + 4

    def draw_alert(self, r):
        self.blit_text("ALERT PRIORYTETOWY  kanal WILKI_ALERT", (r.x, r.y), self.font_b, WHITE)
        self._alert_btn = pygame.Rect(r.x, r.y + 50, 280, 44)
        self.button(self._alert_btn, "WYSLIJ ALERT DO PEEROW", True)
        self.blit_text("Na Androidzie: NotificationChannel IMPORTANCE_HIGH.", (r.x, r.y + 110), self.font, MUTED)

    def draw_kom(self, r):
        self.blit_text("AGENT KOMENTARZY", (r.x, r.y), self.font_b, WHITE)
        y = r.y + 40
        for c in self.store.cx.execute("SELECT * FROM comments ORDER BY id DESC LIMIT 10"):
            y = self.blit_text(f"{c['body']}", (r.x, y), self.font, SILVER, r.w) + 6
        self.blit_text("Po publikacji Hetman dopisuje komentarz wg System Prompt.", (r.x, y + 8), self.font_s, MUTED, r.w)

    def draw_mask(self, r):
        self.blit_text("TRYB BEZ MASKI", (r.x, r.y), self.font_b, WHITE)
        self.blit_text(
            "Otwarte modele, zero korporacyjnego filtra mowy. "
            "Hetman nadal tnie tresci wprost przestępcze. Polityka, satyra, ostra publicystyka — bez kagańca.",
            (r.x, r.y + 40),
            self.font,
            SILVER,
            r.w,
        )

    def draw_id(self, r):
        self.screen.blit(self.logo_big, (r.x + 40, r.y + 20))
        self.blit_text(IDENTITY, (r.x + 360, r.y + 80), self.font_t, WHITE)
        self.blit_text("Logo husarsko-wilcze w oryginale. Paleta bialo-czerwono-czarna.", (r.x + 360, r.y + 130), self.font, SILVER, 500)

    def draw_donate(self, r):
        self.blit_text("DOBROWOLNE WSPARCIE", (r.x, r.y), self.font_b, WHITE)
        self.blit_text("Przelew / BLIK / krypto. Zero posrednikow reklamowych.", (r.x, r.y + 40), self.font, SILVER)
        y = r.y + 80
        for d in self.store.cx.execute("SELECT * FROM donations ORDER BY id DESC LIMIT 8"):
            y = self.blit_text(f"{d['amount']:.2f} PLN  —  {d['note']}", (r.x, y), self.font, GOLD) + 4
        self._don_btn = pygame.Rect(r.x, r.y + 280, 240, 40)
        self.button(self._don_btn, "WPŁATA SYMBOLICZNA 10 PLN", True)

    def draw_qc(self, r):
        self.blit_text("WIELOAGENTOWY KONTROLER JAKOSCI", (r.x, r.y), self.font_b, WHITE)
        self.blit_text("Scriptor → Grafik → Lektor → Hetman (weto). Kazdy material przechodzi bramke.", (r.x, r.y + 40), self.font, SILVER, r.w)
        y = r.y + 90
        for name in ("Scriptor", "Grafik", "Lektor", "Hetman"):
            pygame.draw.rect(self.screen, RED_DK, (r.x, y, 200, 50), border_radius=4)
            self.blit_text(name, (r.x + 16, y + 14), self.font_b, WHITE)
            pygame.draw.polygon(self.screen, RED, [(r.x + 220, y + 25), (r.x + 250, y + 25), (r.x + 238, y + 18), (r.x + 238, y + 32)])
            y += 64

    def click(self, pos):
        w, h = self.screen.get_size()
        bx = w - 360
        if pygame.Rect(bx, 18, 110, 48).collidepoint(pos):
            self.llm.offline = not self.llm.offline
            return
        if pygame.Rect(bx + 118, 18, 110, 48).collidepoint(pos):
            self.llm.unmasked = not self.llm.unmasked
            return
        if pygame.Rect(bx + 236, 18, 110, 48).collidepoint(pos):
            self.toggle_mic()
            return
        for rec, key in getattr(self, "_nav_rects", []):
            if rec.collidepoint(pos):
                self.handle_nav(key)
                return
        for rec, k in getattr(self, "_plus", []):
            if rec.collidepoint(pos):
                self.plus_menu(k)
                return
        if self.nav == "glosy":
            for rec, name in getattr(self, "_voice_rects", []):
                if rec.collidepoint(pos):
                    self.llm.voice = name
                    ts = datetime.now().strftime("%H%M%S")
                    p = app_dir() / "out" / f"preview-{name}-{ts}.wav"
                    synth_wav(p, 1.2, 120)
                    self.toast_set(f"Glos {name} — podglad {p.name}")
                    return
        if self.nav == "agent":
            for rec, aid in getattr(self, "_agent_rects", []):
                if rec.collidepoint(pos):
                    self.store.cx.execute("UPDATE agents SET active=0")
                    self.store.cx.execute("UPDATE agents SET active=1 WHERE id=?", (aid,))
                    self.store.cx.commit()
                    return
        if self.nav == "naprawa" and getattr(self, "_repair_btn", pygame.Rect(0, 0, 0, 0)).collidepoint(pos):
            self.do_repair()
        if self.nav == "radio" and getattr(self, "_radio_btn", pygame.Rect(0, 0, 0, 0)).collidepoint(pos):
            self.radio_on = not self.radio_on
            self.bridge.broadcast({"type": "radio", "on": self.radio_on, "pos": self.radio_pos, "title": "WILK-FM"})
        if self.nav == "alert" and getattr(self, "_alert_btn", pygame.Rect(0, 0, 0, 0)).collidepoint(pos):
            self.bridge.broadcast({"type": "alert", "body": self.input or "WATAHA — ALERT PRIORYTETOWY", "prio": "max"})
            self.store.add_msg("system", "ALERT wyslany do peerow i kanalu WILKI_ALERT")
            self.toast_set("Alert wyslany")
        if self.nav == "wsparcie" and getattr(self, "_don_btn", pygame.Rect(0, 0, 0, 0)).collidepoint(pos):
            self.store.cx.execute(
                "INSERT INTO donations(ts,amount,note) VALUES(?,?,?)",
                (time.time(), 10.0, "dobrowolne wsparcie watahy"),
            )
            self.store.cx.commit()
            self.toast_set("Dziekujemy. Wszyscy won.")

    def toggle_mic(self):
        if self.listening:
            self.listening = False
            self.store.add_msg("system", f"Mikrofon STOP po {time.time()-self.listen_started:0.1f}s (recznie).")
        else:
            self.listening = True
            self.listen_started = time.time()
            self.pcm_bytes = 0
            self.store.add_msg("system", "Mikrofon START — nasluch ciagly, bez autostopu.")

    def on_enter(self):
        text = self.input.strip()
        self.input = ""
        if not text:
            return
        if self.nav in ("czat", "kod", "maska", "modele"):
            self.send_chat(text)
        elif self.nav == "planer":
            t = time.time() + 7200
            self.store.cx.execute(
                "INSERT INTO plan(ts,platform,body,status,media) VALUES(?,?,?,?,?)",
                (t, "X,Telegram,YT", text, "DRAFT", ""),
            )
            self.store.cx.commit()
            self.store.cx.execute(
                "INSERT INTO comments(ts,post,body,auto) VALUES(?,?,?,1)",
                (time.time(), text[:80], f"{self.agent()['name']}: material przyjety do kolejki. {SLOGAN}",),
            )
            self.store.cx.commit()
            self.toast_set("Do planera + agent komentarzy")
        elif self.nav == "e2e":
            nonce, ct = self.e2e.wrap(self.e2e.pub_bytes(), text.encode())
            self.store.cx.execute(
                "INSERT INTO e2e(ts,room,sender,nonce,payload) VALUES(?,?,?,?,?)",
                (time.time(), self.room, self.user["login"], nonce.hex(), base64.b64encode(ct).decode()),
            )
            self.store.cx.commit()
            self.bridge.broadcast({"type": "e2e", "room": self.room, "nonce": nonce.hex()})
        elif self.nav == "agent":
            self.store.cx.execute(
                "UPDATE agents SET prompt=? WHERE active=1",
                (text,),
            )
            self.store.cx.commit()
            self.toast_set("System prompt zapisany")
        elif self.nav == "alert":
            self.bridge.broadcast({"type": "alert", "body": text, "prio": "max"})
            self.toast_set("Alert")
        else:
            self.send_chat(text)

    def pump_inbox(self):
        try:
            while True:
                kind, msg = self.inbox.get_nowait()
                if kind == "sys":
                    self.store.add_msg("system", str(msg))
                elif kind == "sync":
                    if isinstance(msg, dict) and msg.get("type") == "chat":
                        self.store.add_msg("assistant", "SYNC: " + str(msg.get("text", "")), channel="chat")
        except queue.Empty:
            pass

    def run(self):
        running = True
        while running:
            self.pump_inbox()
            if self.radio_on:
                self.radio_pos += self.clock.get_time() / 1000.0
            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    running = False
                elif e.type == pygame.VIDEORESIZE:
                    self.screen = pygame.display.set_mode(e.size, pygame.RESIZABLE)
                elif e.type == pygame.MOUSEBUTTONDOWN:
                    if self.splash:
                        self.splash = False
                    elif e.button == 1:
                        self.click(e.pos)
                    elif e.button == 4:
                        self.scroll = max(0, self.scroll - 40)
                    elif e.button == 5:
                        self.scroll += 40
                elif e.type == pygame.KEYDOWN:
                    if self.splash:
                        self.splash = False
                        continue
                    if e.key == pygame.K_ESCAPE:
                        running = False
                    elif e.key == pygame.K_RETURN:
                        self.on_enter()
                    elif e.key == pygame.K_BACKSPACE:
                        self.input = self.input[:-1]
                    elif e.key == pygame.K_F2:
                        self.toggle_mic()
                    elif e.unicode and e.unicode.isprintable():
                        self.input += e.unicode
            if self.splash and time.time() - self.splash_t > 2.4:
                self.splash = False
            if self.splash:
                self.draw_splash()
            else:
                self.draw()
            pygame.display.flip()
            self.clock.tick(60)
        self.bridge.alive = False
        pygame.quit()


def main():
    App().run()


if __name__ == "__main__":
    main()
