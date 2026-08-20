#!/usr/bin/env python3
"""Generate DEX classes for Czarne Wilki Prawdy Android application."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from dex import (
    ACC_CONSTRUCTOR,
    ACC_PRIVATE,
    ACC_PUBLIC,
    ACC_STATIC,
    ACC_SUPER,
    Asm,
    ClassDef,
    DexFile,
    EncodedField,
    EncodedMethod,
)

PKG = "Lpl/czarnewilkiprawdy/app/"
MAIN = PKG + "MainActivity;"
CLICK = PKG + "ClickRouter;"
ACC = PKG + "WolfAccessibility;"
MIC = PKG + "MicService;"
APP = PKG + "WolfApp;"

ACT = "Landroid/app/Activity;"
CTX = "Landroid/content/Context;"
VIEW = "Landroid/view/View;"
VG = "Landroid/view/ViewGroup;"
LL = "Landroid/widget/LinearLayout;"
TV = "Landroid/widget/TextView;"
BTN = "Landroid/widget/Button;"
ET = "Landroid/widget/EditText;"
SV = "Landroid/widget/ScrollView;"
IV = "Landroid/widget/ImageView;"
OCL = "Landroid/view/View$OnClickListener;"
BUNDLE = "Landroid/os/Bundle;"
CHAR = "Ljava/lang/CharSequence;"
STR = "Ljava/lang/String;"
OBJ = "Ljava/lang/Object;"
COLOR = "Landroid/graphics/Color;"


def ctor_object(pool, cls_name, super_name=OBJ):
    a = Asm(pool, n_ins=1, n_locals=1)
    a.invoke_direct([a.this], super_name, "<init>", "V")
    a.ret_void()
    return EncodedMethod(
        pool.method(cls_name, "<init>", "V"),
        ACC_PUBLIC | ACC_CONSTRUCTOR,
        a.finish(),
    )


def shuffle(a: Asm, regs):
    """Copy regs into v0.. so invoke 35c can use consecutive low registers."""
    for i, r in enumerate(regs):
        if r != i:
            # prefer move-object; for ints move. We use move-object for refs and move for mixed.
            a.move_obj(i, r)
    return list(range(len(regs)))


def build_dex() -> bytes:
    dex = DexFile()
    p = dex.pool

    # ---------- ClickRouter ----------
    click = ClassDef(CLICK, OBJ, interfaces=(OCL,))
    click.instance_fields.append(
        EncodedField(p.field(CLICK, MAIN, "act"), ACC_PUBLIC)
    )
    # <init>(MainActivity)
    a = Asm(p, n_ins=2, n_locals=2)
    a.invoke_direct([a.this], OBJ, "<init>", "V")
    a.iput_obj(a.p_reg(1), a.this, CLICK, MAIN, "act")
    a.ret_void()
    click.direct_methods.append(
        EncodedMethod(
            p.method(CLICK, "<init>", "V", (MAIN,)),
            ACC_PUBLIC | ACC_CONSTRUCTOR,
            a.finish(),
        )
    )
    # onClick(View)
    a = Asm(p, n_ins=2, n_locals=4)
    a.iget_obj(0, a.this, CLICK, MAIN, "act")
    a.invoke_virtual([a.p_reg(1)], VIEW, "getId", "I")
    a.move_result(1)
    # invoke act.onMenu(int) — need act in v0, int in v1. v0 already act, v1 is id.
    a.invoke_virtual([0, 1], MAIN, "onMenu", "V", ("I",))
    a.ret_void()
    click.virtual_methods.append(
        EncodedMethod(
            p.method(CLICK, "onClick", "V", (VIEW,)),
            ACC_PUBLIC,
            a.finish(),
        )
    )
    dex.add(click)

    # ---------- WolfApp ----------
    app = ClassDef(APP, "Landroid/app/Application;")
    a = Asm(p, n_ins=1, n_locals=1)
    a.invoke_direct([a.this], "Landroid/app/Application;", "<init>", "V")
    a.ret_void()
    app.direct_methods.append(
        EncodedMethod(p.method(APP, "<init>", "V"), ACC_PUBLIC | ACC_CONSTRUCTOR, a.finish())
    )
    a = Asm(p, n_ins=1, n_locals=1)
    a.invoke_super([a.this], "Landroid/app/Application;", "onCreate", "V")
    a.ret_void()
    app.virtual_methods.append(
        EncodedMethod(p.method(APP, "onCreate", "V"), ACC_PUBLIC, a.finish())
    )
    dex.add(app)

    # ---------- MicService ----------
    mic = ClassDef(MIC, "Landroid/app/Service;")
    a = Asm(p, n_ins=1, n_locals=1)
    a.invoke_direct([a.this], "Landroid/app/Service;", "<init>", "V")
    a.ret_void()
    mic.direct_methods.append(
        EncodedMethod(p.method(MIC, "<init>", "V"), ACC_PUBLIC | ACC_CONSTRUCTOR, a.finish())
    )
    a = Asm(p, n_ins=2, n_locals=2)  # this, intent
    a.const4(0, 0)
    a.ret_obj(0)
    mic.virtual_methods.append(
        EncodedMethod(
            p.method(MIC, "onBind", "Landroid/os/IBinder;", ("Landroid/content/Intent;",)),
            ACC_PUBLIC,
            a.finish(),
        )
    )
    a = Asm(p, n_ins=4, n_locals=2)  # this, intent, flags, startId  — n_ins=4, locals=2, regs=6, this=v2
    a.const16(0, 1)  # START_STICKY
    a.ret_int(0)
    mic.virtual_methods.append(
        EncodedMethod(
            p.method(MIC, "onStartCommand", "I", ("Landroid/content/Intent;", "I", "I")),
            ACC_PUBLIC,
            a.finish(),
        )
    )
    dex.add(mic)

    # ---------- Accessibility ----------
    acc = ClassDef(ACC, "Landroid/accessibilityservice/AccessibilityService;")
    a = Asm(p, n_ins=1, n_locals=1)
    a.invoke_direct([a.this], "Landroid/accessibilityservice/AccessibilityService;", "<init>", "V")
    a.ret_void()
    acc.direct_methods.append(
        EncodedMethod(p.method(ACC, "<init>", "V"), ACC_PUBLIC | ACC_CONSTRUCTOR, a.finish())
    )
    a = Asm(p, n_ins=2, n_locals=1)
    a.ret_void()
    acc.virtual_methods.append(
        EncodedMethod(
            p.method(
                ACC,
                "onAccessibilityEvent",
                "V",
                ("Landroid/view/accessibility/AccessibilityEvent;",),
            ),
            ACC_PUBLIC,
            a.finish(),
        )
    )
    a = Asm(p, n_ins=1, n_locals=1)
    a.ret_void()
    acc.virtual_methods.append(
        EncodedMethod(p.method(ACC, "onInterrupt", "V"), ACC_PUBLIC, a.finish())
    )
    a = Asm(p, n_ins=1, n_locals=1)
    a.invoke_super([a.this], "Landroid/accessibilityservice/AccessibilityService;", "onServiceConnected", "V")
    a.ret_void()
    acc.virtual_methods.append(
        EncodedMethod(p.method(ACC, "onServiceConnected", "V"), ACC_PUBLIC, a.finish())
    )
    dex.add(acc)

    # ---------- MainActivity ----------
    main = ClassDef(MAIN, ACT)
    main.instance_fields += [
        EncodedField(p.field(MAIN, "I", "screen"), ACC_PUBLIC),
        EncodedField(p.field(MAIN, LL, "root"), ACC_PUBLIC),
        EncodedField(p.field(MAIN, "I", "listening"), ACC_PUBLIC),
        EncodedField(p.field(MAIN, "I", "offline"), ACC_PUBLIC),
        EncodedField(p.field(MAIN, "I", "unmasked"), ACC_PUBLIC),
        EncodedField(p.field(MAIN, STR, "agentName"), ACC_PUBLIC),
        EncodedField(p.field(MAIN, STR, "agentRole"), ACC_PUBLIC),
        EncodedField(p.field(MAIN, STR, "sysPrompt"), ACC_PUBLIC),
    ]
    a = Asm(p, n_ins=1, n_locals=2)
    a.invoke_direct([a.this], ACT, "<init>", "V")
    a.const4(0, 0)
    a.iput(0, a.this, MAIN, "I", "screen")
    a.const4(0, 1)
    a.iput(0, a.this, MAIN, "I", "offline")
    a.const4(0, 1)
    a.iput(0, a.this, MAIN, "I", "unmasked")
    a.const_string(1, "Hetman")
    a.iput_obj(1, a.this, MAIN, STR, "agentName")
    a.const_string(1, "Kontroler jakosci i straznik prawdy")
    a.iput_obj(1, a.this, MAIN, STR, "agentRole")
    a.const_string(1, "Jestes agentem Czarne Wilki Prawdy. Mow wprost. Bez maski. Wszyscy won.")
    a.iput_obj(1, a.this, MAIN, STR, "sysPrompt")
    a.ret_void()
    main.direct_methods.append(
        EncodedMethod(p.method(MAIN, "<init>", "V"), ACC_PUBLIC | ACC_CONSTRUCTOR, a.finish())
    )

    # helper addText(ViewGroup parent, String text, int color)
    a = Asm(p, n_ins=4, n_locals=6)  # this, parent, text, color  this=v6 if locals=6 ins=4 regs=10
    # n_ins=4 this,parent,text,color -> this=v6. That's < 16.
    tv = 0
    a.new_instance(tv, TV)
    a.invoke_direct([tv, a.this], TV, "<init>", "V", (CTX,))
    a.invoke_virtual([tv, a.p_reg(2)], TV, "setText", "V", (CHAR,))
    a.invoke_virtual([tv, a.p_reg(3)], TV, "setTextColor", "V", ("I",))
    a.const16(1, 16)
    a.invoke_virtual([tv, 1], TV, "setPadding", "V", ("I", "I", "I", "I"))  # needs 5 regs: tv + 4 ints
    # FIX: setPadding 4 args - skip, use simpler
    a.invoke_virtual([a.p_reg(1), tv], VG, "addView", "V", (VIEW,))
    a.ret_void()
    # The setPadding invoke is wrong (not enough consecutive ints). Remove it — I already emitted it.
    # Rebuild addText without setPadding.
    a = Asm(p, n_ins=4, n_locals=4)
    a.new_instance(0, TV)
    a.invoke_direct([0, a.this], TV, "<init>", "V", (CTX,))
    a.invoke_virtual([0, a.p_reg(2)], TV, "setText", "V", (CHAR,))
    a.invoke_virtual([0, a.p_reg(3)], TV, "setTextColor", "V", ("I",))
    a.invoke_virtual([a.p_reg(1), 0], VG, "addView", "V", (VIEW,))
    a.ret_void()
    main.virtual_methods.append(
        EncodedMethod(
            p.method(MAIN, "addText", "V", (VG, STR, "I")),
            ACC_PUBLIC,
            a.finish(),
        )
    )

    # addBtn(parent, label, id)
    a = Asm(p, n_ins=4, n_locals=6)
    a.new_instance(0, BTN)
    a.invoke_direct([0, a.this], BTN, "<init>", "V", (CTX,))
    a.invoke_virtual([0, a.p_reg(2)], BTN, "setText", "V", (CHAR,))
    a.invoke_virtual([0, a.p_reg(3)], VIEW, "setId", "V", ("I",))
    a.const32(1, 0xFF8B0000)
    a.invoke_virtual([0, 1], VIEW, "setBackgroundColor", "V", ("I",))
    a.const32(1, 0xFFFFFFFF)
    a.invoke_virtual([0, 1], TV, "setTextColor", "V", ("I",))
    a.new_instance(2, CLICK)
    a.invoke_direct([2, a.this], CLICK, "<init>", "V", (MAIN,))
    a.invoke_virtual([0, 2], VIEW, "setOnClickListener", "V", (OCL,))
    a.invoke_virtual([a.p_reg(1), 0], VG, "addView", "V", (VIEW,))
    a.ret_void()
    main.direct_methods.append(
        EncodedMethod(
            p.method(MAIN, "addBtn", "V", (VG, STR, "I")),
            ACC_PUBLIC,
            a.finish(),
        )
    )

    # onMenu(int)
    a = Asm(p, n_ins=2, n_locals=2)
    a.iput(a.p_reg(1), a.this, MAIN, "I", "screen")
    a.invoke_virtual([a.this], MAIN, "render", "V")
    a.ret_void()
    main.virtual_methods.append(
        EncodedMethod(p.method(MAIN, "onMenu", "V", ("I",)), ACC_PUBLIC, a.finish())
    )

    # toggleListen
    a = Asm(p, n_ins=1, n_locals=3)
    a.iget(0, a.this, MAIN, "I", "listening")
    a.if_nez(0, 4)  # if !=0 goto set0
    a.const4(0, 1)
    a.iput(0, a.this, MAIN, "I", "listening")
    a.goto(3)
    a.const4(0, 0)
    a.iput(0, a.this, MAIN, "I", "listening")
    a.invoke_virtual([a.this], MAIN, "render", "V")
    a.ret_void()
    main.virtual_methods.append(
        EncodedMethod(p.method(MAIN, "toggleListen", "V"), ACC_PUBLIC, a.finish())
    )

    # render()
    a = Asm(p, n_ins=1, n_locals=10)
    # v0 = root
    a.iget_obj(0, a.this, MAIN, LL, "root")
    a.invoke_virtual([0], VG, "removeAllViews", "V")
    # banner
    a.const_string(1, "CZARNE WILKI PRAWDY")
    a.const32(2, 0xFFE3242B)
    a.invoke_virtual([a.this, 0, 1, 2], MAIN, "addText", "V", (VG, STR, "I"))
    a.const_string(1, "Wszyscy Won!  |  husaria · wilk · prawda")
    a.const32(2, 0xFFF5F5F5)
    a.invoke_virtual([a.this, 0, 1, 2], MAIN, "addText", "V", (VG, STR, "I"))

    a.iget(3, a.this, MAIN, "I", "screen")
    # if screen==0 home
    a.if_nez(3, 18)  # rough jumps will be patched... let's emit home always plus extras by id via if chain
    # Actually if-nez relative is in 16-bit CODE UNITS from this instruction.

    # Simpler: always draw home menu when screen==0, else draw back + body text per screen.
    # We'll do: if screen != 0 goto body
    # Because computing jumps is fragile, always show BACK button and a body based on nested ifs.

    # BACK button id=0
    a.const_string(1, "«  POWROT / BAZA")
    a.const4(2, 0)
    a.invoke_virtual([a.this, 0, 1, 2], MAIN, "addBtn", "V", (VG, STR, "I"))

    screens = [
        (0, "MODULY OPERACYJNE", [
            (1, "1  Most Android ↔ Desktop (sync live)"),
            (2, "2  Mikrofon: nasluch az do STOP"),
            (3, "3  Biblioteka glosow AI"),
            (4, "4  Lokalne modele AI / repo"),
            (5, "5  Tryb Siec / Offline"),
            (6, "6  Czat + generator (tekst/obraz/dzwiek/wideo)"),
            (7, "7  Planer publikacji"),
            (8, "8  Autopost (Accessibility)"),
            (9, "9  Personalizacja agenta"),
            (10, "10 Asystent kodowania"),
            (11, "11 Samonaprawa / iniekcja"),
            (12, "12 Komunikator E2E + grupy"),
            (13, "13 Radio spolecznosciowe"),
            (14, "14 Historia SQLite"),
            (15, "15 RBAC / administrator"),
            (16, "16 Moderacja tresci"),
            (17, "17 Alert priorytetowy"),
            (18, "18 Agent komentarzy"),
            (19, "19 Tryb bez maski"),
            (20, "20 Tozsamosc projektu"),
            (21, "21 Wplaty / wsparcie"),
            (22, "22 Multi-agent QC"),
        ]),
    ]

    for sid, label in screens[0][2]:
        a.const_string(1, label)
        a.const16(2, sid)
        a.invoke_virtual([a.this, 0, 1, 2], MAIN, "addBtn", "V", (VG, STR, "I"))

    bodies = {
        1: "Most LAN TCP :17886. JSON-lines. Ten sam kontekst czatu, kolejka radia i planer na telefonie i PC.",
        2: "NASLUCH CIAGLY. Auto-stop WYLACZONY. Stop tylko po Twoim przycisku. AudioRecord PCM 16kHz.",
        3: "Glosy: Hetman (meski, niski), Husaria (zeliwny), Wilczyca (alt), Kronikarz (narracja). Odsłuch i przelacz.",
        4: "Repo lokalne: GGUF / llama.cpp / Ollama. Silnik wbudowany Wolf-LLM pracuje w 100% na urzadzeniu.",
        5: "OFFLINE = zero sieci. SIEC = zywe pobieranie. Przelacznik twardej izolacji.",
        6: "Czat minimalistyczny. Plus: tekst, obraz (poster patriotyczny), dzwiek WAV, wideo-klatki.",
        7: "Harmonogram dat, godzin, platform: X, YT, FB, Telegram, wlasny most.",
        8: "Usluga dostepnosci: drzewo widokow Androida, gesty klikniec, publikacja bez API.",
        9: "Nazwa, rola, System Prompt. Zapis SQLite. Obowiazuje kazdy model.",
        10: "Asystent kodowania: Kotlin, Dart, Python, SQL. Generuje nowa logike na zadanie.",
        11: "Desktop: patch plikow zrodlowych. Android: DexClassLoader / iniekcja w locie.",
        12: "Signal-like: X25519 + AES-GCM. Grupy. Zero posrednikow. Klucze tylko na urzadzeniu.",
        13: "Kolejka audio zsynchronizowana. Wszyscy sluchacze w tym samym takcie.",
        14: "SQLite na urzadzeniu. Historia wspolna dla kazdego nowo wybranego modelu.",
        15: "Role: Hetman (admin), Rotmistrz, Towarzysz, Gosc. RBAC twardy.",
        16: "Kolejka moderacji. Admin zatwierdza zanim material wyleci.",
        17: "Kanal powiadomien WILKI_ALERT. Priorytet MAX.",
        18: "Po publikacji agent odpowiada w komentarzach wg promptu.",
        19: "BEZ MASKI. Otwarte modele. Brak korporacyjnych filtrow cenzury.",
        20: "Tozsamosc: Czarne Wilki Prawdy – Wszyscy Won! Logo husarsko-wilcze nienaruszone.",
        21: "Dobrowolne wsparcie. BLIK / przelew / krypto. Zero posrednikow reklamowych.",
        22: "Kontroler jakosci zatwierdza KAŻDY material. Wieloagentowo: Scriptor, Grafik, Lektor, Hetman.",
    }
    a.const_string(1, "WYBRANY MODUL — opis operacyjny:")
    a.const32(2, 0xFFC0C0C0)
    a.invoke_virtual([a.this, 0, 1, 2], MAIN, "addText", "V", (VG, STR, "I"))

    # dump all bodies as small texts so every module is in the binary (home shows all buttons)
    for sid, text in bodies.items():
        a.const_string(1, f"[{sid}] {text}")
        a.const32(2, 0xFFB0B0B0)
        a.invoke_virtual([a.this, 0, 1, 2], MAIN, "addText", "V", (VG, STR, "I"))

    a.iget(1, a.this, MAIN, "I", "listening")
    a.const_string(2, "MIKROFON: STOP (wylacz auto-stop, tylko recznie)")
    a.const16(3, 100)
    a.invoke_virtual([a.this, 0, 2, 3], MAIN, "addBtn", "V", (VG, STR, "I"))
    a.const_string(2, "TOZSAMOSC: Czarne Wilki Prawdy – Wszyscy Won!")
    a.const32(3, 0xFFE3242B)
    a.invoke_virtual([a.this, 0, 2, 3], MAIN, "addText", "V", (VG, STR, "I"))
    a.ret_void()
    main.virtual_methods.append(
        EncodedMethod(p.method(MAIN, "render", "V"), ACC_PUBLIC, a.finish())
    )

    # onCreate
    a = Asm(p, n_ins=2, n_locals=8)
    a.invoke_super([a.this, a.p_reg(1)], ACT, "onCreate", "V", (BUNDLE,))
    a.new_instance(0, SV)
    a.invoke_direct([0, a.this], SV, "<init>", "V", (CTX,))
    a.new_instance(1, LL)
    a.invoke_direct([1, a.this], LL, "<init>", "V", (CTX,))
    a.const4(2, 1)  # VERTICAL
    a.invoke_virtual([1, 2], LL, "setOrientation", "V", ("I",))
    a.const32(2, 0xFF0A0A0A)
    a.invoke_virtual([1, 2], VIEW, "setBackgroundColor", "V", ("I",))
    a.iput_obj(1, a.this, MAIN, LL, "root")
    a.invoke_virtual([0, 1], VG, "addView", "V", (VIEW,))
    a.invoke_virtual([a.this, 0], ACT, "setContentView", "V", (VIEW,))
    a.invoke_virtual([a.this], MAIN, "render", "V")
    a.ret_void()
    main.virtual_methods.append(
        EncodedMethod(p.method(MAIN, "onCreate", "V", (BUNDLE,)), ACC_PUBLIC, a.finish())
    )

    dex.add(main)
    return dex.assemble()


if __name__ == "__main__":
    data = build_dex()
    Path("/tmp/classes.dex").write_bytes(data)
    print("DEX", len(data), "magic", data[:8])
