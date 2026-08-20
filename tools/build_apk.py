#!/usr/bin/env python3
"""Build a signed, installable APK for Czarne Wilki Prawdy."""
from __future__ import annotations

import io
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from android_gen import build_dex
from arsc import build_arsc
from axml import NS_ANDROID, Attr, Node, encode_manifest, ref, TYPE_INT_DEC, TYPE_STRING
from signer import sign_apk


def manifest_axml() -> bytes:
    def A(name, value, typed=None):
        return Attr(name, value, typed=typed, ns=NS_ANDROID)

    def N(name, attrs=None, children=None):
        return Node(name, attrs or [], children or [])

    icon = A("icon", None, typed=ref(0x7F010000))
    label = A("label", None, typed=ref(0x7F020000))

    perms = [
        "android.permission.INTERNET",
        "android.permission.ACCESS_NETWORK_STATE",
        "android.permission.RECORD_AUDIO",
        "android.permission.FOREGROUND_SERVICE",
        "android.permission.POST_NOTIFICATIONS",
        "android.permission.WRITE_EXTERNAL_STORAGE",
        "android.permission.READ_EXTERNAL_STORAGE",
        "android.permission.WAKE_LOCK",
        "android.permission.VIBRATE",
        "android.permission.MODIFY_AUDIO_SETTINGS",
    ]
    perm_nodes = [N("uses-permission", [A("name", p)]) for p in perms]

    main = N(
        "activity",
        [
            A("name", "pl.czarnewilkiprawdy.app.MainActivity"),
            A("exported", True),
            A("theme", "@android:style/Theme.DeviceDefault.NoActionBar"),
            A("configChanges", "orientation|screenSize|keyboardHidden"),
        ],
        [
            N(
                "intent-filter",
                [],
                [
                    N("action", [A("name", "android.intent.action.MAIN")]),
                    N("category", [A("name", "android.intent.category.LAUNCHER")]),
                ],
            )
        ],
    )
    # theme as string might fail. Use no theme attr.
    main = N(
        "activity",
        [
            A("name", "pl.czarnewilkiprawdy.app.MainActivity"),
            A("exported", True),
        ],
        [
            N(
                "intent-filter",
                [],
                [
                    N("action", [A("name", "android.intent.action.MAIN")]),
                    N("category", [A("name", "android.intent.category.LAUNCHER")]),
                ],
            )
        ],
    )
    acc = N(
        "service",
        [
            A("name", "pl.czarnewilkiprawdy.app.WolfAccessibility"),
            A("exported", True),
            A("permission", "android.permission.BIND_ACCESSIBILITY_SERVICE"),
        ],
        [
            N(
                "intent-filter",
                [],
                [
                    N(
                        "action",
                        [A("name", "android.accessibilityservice.AccessibilityService")],
                    )
                ],
            )
        ],
    )
    mic = N(
        "service",
        [A("name", "pl.czarnewilkiprawdy.app.MicService"), A("exported", False)],
    )
    app = N(
        "application",
        [
            A("name", "pl.czarnewilkiprawdy.app.WolfApp"),
            icon,
            label,
            A("debuggable", False),
            A("allowBackup", False),
            A("usesCleartextTraffic", True),
        ],
        [main, acc, mic],
    )
    uses_sdk = N(
        "uses-sdk",
        [
            Attr("minSdkVersion", 21, typed=(TYPE_INT_DEC, 21)),
            Attr("targetSdkVersion", 28, typed=(TYPE_INT_DEC, 28)),
        ],
    )
    root = N(
        "manifest",
        [
            Attr("package", "pl.czarnewilkiprawdy.app", ns=None),
            Attr("versionCode", 1, typed=(TYPE_INT_DEC, 1), ns=NS_ANDROID),
            Attr("versionName", "1.0.0", ns=NS_ANDROID),
        ],
        [uses_sdk] + perm_nodes + [app],
    )
    return encode_manifest(root, "pl.czarnewilkiprawdy.app")


def build(out_path: Path) -> Path:
    dex = build_dex()
    axml = manifest_axml()
    arsc = build_arsc("Czarne Wilki Prawdy")
    icon = (ROOT / "assets" / "icon_192.png").read_bytes()
    logo = (ROOT / "assets" / "logo.png").read_bytes()

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        def put(name, data, stored=False):
            info = zipfile.ZipInfo(name)
            info.compress_type = zipfile.ZIP_STORED if stored else zipfile.ZIP_DEFLATED
            info.create_system = 0
            z.writestr(info, data)

        put("AndroidManifest.xml", axml)
        put("classes.dex", dex)
        put("resources.arsc", arsc, stored=True)
        put("res/drawable/ic_launcher.png", icon)
        put("assets/logo.png", logo)
        put(
            "assets/identity.txt",
            "Czarne Wilki Prawdy – Wszyscy Won!\n".encode("utf-8"),
        )
        put(
            "META-INF/native-bridge.txt",
            b"sync=tcp:17886\nprotocol=wolf-jsonl\n",
        )

    unsigned = buf.getvalue()
    signed = sign_apk(unsigned)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(signed)
    print(f"APK written {out_path} ({len(signed)} bytes)")
    print(f"  dex={len(dex)} manifest={len(axml)} arsc={len(arsc)}")
    return out_path


if __name__ == "__main__":
    dest = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "dist" / "CzarneWilkiPrawdy.apk"
    build(dest)
