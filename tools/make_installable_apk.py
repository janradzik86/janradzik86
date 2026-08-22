#!/usr/bin/env python3
"""Build an Android-installable APK (v1 JAR signature only, aapt-like AXML, DOS zip)."""
from __future__ import annotations

import hashlib
import io
import struct
import sys
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import pkcs7
from cryptography.x509.oid import NameOID

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from dex import ACC_CONSTRUCTOR, ACC_PUBLIC, ACC_SUPER, Asm, ClassDef, DexFile, EncodedMethod

NS = "http://schemas.android.com/apk/res/android"
NO = 0xFFFFFFFF
RES_XML = 0x0003
RES_STR = 0x0001
RES_MAP = 0x0180
RES_NS_START = 0x0100
RES_NS_END = 0x0101
RES_START = 0x0102
RES_END = 0x0103

ATTR_IDS = {
    "versionCode": 0x0101021B,
    "versionName": 0x0101021C,
    "minSdkVersion": 0x0101020C,
    "targetSdkVersion": 0x01010270,
    "label": 0x01010001,
    "name": 0x01010003,
    "exported": 0x01010010,
    "theme": 0x01010000,
}


def utf16_pool(strings):
    data = bytearray()
    offsets = []
    for s in strings:
        offsets.append(len(data))
        data.extend(struct.pack("<H", len(s)))
        data.extend(s.encode("utf-16le"))
        data.extend(b"\x00\x00")
    header_size = 28
    sstart = header_size + 4 * len(strings)
    chunk = header_size + 4 * len(strings) + len(data)
    while chunk % 4:
        data.append(0)
        chunk += 1
    buf = bytearray()
    buf.extend(struct.pack("<HHI", RES_STR, header_size, chunk))
    buf.extend(struct.pack("<IIIII", len(strings), 0, 0, sstart, 0))
    for o in offsets:
        buf.extend(struct.pack("<I", o))
    buf.extend(data)
    return bytes(buf)


def axml_manifest(package: str, activity: str, label: str) -> bytes:
    # Attribute names MUST be the first strings (resource map parallel).
    attr_names = [
        "versionCode",
        "versionName",
        "minSdkVersion",
        "targetSdkVersion",
        "label",
        "name",
        "exported",
    ]
    rest = [
        "android",
        NS,
        "",
        "package",
        "manifest",
        package,
        "1.0.0",
        "uses-sdk",
        "application",
        "activity",
        activity,
        "intent-filter",
        "action",
        "android.intent.action.MAIN",
        "category",
        "android.intent.category.LAUNCHER",
        label,
    ]
    strings = attr_names + rest
    idx = {s: i for i, s in enumerate(strings)}

    def S(s):
        return idx[s]

    pool = utf16_pool(strings)
    rm = bytearray()
    ids = [ATTR_IDS[n] for n in attr_names]
    rm.extend(struct.pack("<HHI", RES_MAP, 8, 8 + 4 * len(ids)))
    for x in ids:
        rm.extend(struct.pack("<I", x))

    body = bytearray()

    def node(typ, payload, line=1):
        hs = 16
        size = hs + len(payload)
        body.extend(struct.pack("<HHI", typ, hs, size))
        body.extend(struct.pack("<II", line, NO))
        body.extend(payload)

    def ns(start, line):
        payload = struct.pack("<II", S("android"), S(NS))
        node(RES_NS_START if start else RES_NS_END, payload, line)

    def attr(ns_i, name_i, raw, dtype, data):
        return struct.pack("<IIIHBBI", ns_i, name_i, raw, 8, 0, dtype, data & 0xFFFFFFFF)

    def start(name, attrs, line):
        # attrExt: ns, name, attrStart=20, attrSize=20, count, id=0, class=0, style=0
        ext = struct.pack("<II", NO, S(name))
        ext += struct.pack("<HHHHHH", 20, 20, len(attrs), 0, 0, 0)
        payload = ext + b"".join(attrs)
        node(RES_START, payload, line)

    def end(name, line):
        node(RES_END, struct.pack("<II", NO, S(name)), line)

    AND = S("android")
    T_INT, T_STR, T_BOOL = 0x10, 0x03, 0x12

    ns(True, 1)
    start(
        "manifest",
        [
            attr(AND, S("versionCode"), NO, T_INT, 1),
            attr(AND, S("versionName"), S("1.0.0"), T_STR, S("1.0.0")),
            attr(NO, S("package"), S(package), T_STR, S(package)),
        ],
        2,
    )
    start(
        "uses-sdk",
        [
            attr(AND, S("minSdkVersion"), NO, T_INT, 21),
            attr(AND, S("targetSdkVersion"), NO, T_INT, 28),
        ],
        3,
    )
    end("uses-sdk", 4)
    start(
        "application",
        [
            attr(AND, S("label"), S(label), T_STR, S(label)),
        ],
        5,
    )
    start(
        "activity",
        [
            attr(AND, S("name"), S(activity), T_STR, S(activity)),
            attr(AND, S("exported"), NO, T_BOOL, 0xFFFFFFFF),
        ],
        6,
    )
    start("intent-filter", [], 7)
    start("action", [attr(AND, S("name"), S("android.intent.action.MAIN"), T_STR, S("android.intent.action.MAIN"))], 8)
    end("action", 9)
    start(
        "category",
        [attr(AND, S("name"), S("android.intent.category.LAUNCHER"), T_STR, S("android.intent.category.LAUNCHER"))],
        10,
    )
    end("category", 11)
    end("intent-filter", 12)
    end("activity", 13)
    end("application", 14)
    end("manifest", 15)
    ns(False, 16)

    inner = pool + bytes(rm) + bytes(body)
    out = struct.pack("<HHI", RES_XML, 8, 8 + len(inner)) + inner
    return out


def make_dex() -> bytes:
    dex = DexFile()
    p = dex.pool
    MAIN = "Lpl/czarnewilkiprawdy/app/MainActivity;"
    ACT = "Landroid/app/Activity;"
    CTX = "Landroid/content/Context;"
    TV = "Landroid/widget/TextView;"
    VIEW = "Landroid/view/View;"
    CHAR = "Ljava/lang/CharSequence;"
    STR = "Ljava/lang/String;"
    BUNDLE = "Landroid/os/Bundle;"

    c = ClassDef(MAIN, ACT, access=ACC_PUBLIC | ACC_SUPER)
    a = Asm(p, n_ins=1, n_locals=1)
    a.invoke_direct([a.this], ACT, "<init>", "V")
    a.ret_void()
    c.direct_methods.append(
        EncodedMethod(p.method(MAIN, "<init>", "V"), ACC_PUBLIC | ACC_CONSTRUCTOR, a.finish())
    )

    a = Asm(p, n_ins=2, n_locals=6)
    a.invoke_super([a.this, a.p_reg(1)], ACT, "onCreate", "V", (BUNDLE,))
    a.new_instance(0, TV)
    a.invoke_direct([0, a.this], TV, "<init>", "V", (CTX,))
    a.const_string(1, "Czarne Wilki Prawdy")
    a.invoke_virtual([0, 1], TV, "setText", "V", (CHAR,))
    a.const32(2, 0xFFFFFFFF)
    a.invoke_virtual([0, 2], TV, "setTextColor", "V", ("I",))
    a.const32(2, 0xFF080808)
    a.invoke_virtual([0, 2], VIEW, "setBackgroundColor", "V", ("I",))
    a.const_string(1, "Wszyscy Won!\n\n1 Most LAN\n2 Mikrofon STOP\n3 Glosy AI\n4 Modele lokalne\n5 Offline/Siec\n6 Czat +\n7 Planer\n8 Autopost\n9 Agent\n10 Kod\n11 Naprawa\n12 E2E\n13 Radio\n14 SQLite\n15 RBAC\n16 Moderacja\n17 Alert\n18 Komentarze\n19 Bez maski\n20 Tozsamosc\n21 Wplaty\n22 QC Hetman")
    a.invoke_virtual([0, 1], TV, "setText", "V", (CHAR,))
    a.invoke_virtual([a.this, 0], ACT, "setContentView", "V", (VIEW,))
    a.ret_void()
    c.virtual_methods.append(
        EncodedMethod(p.method(MAIN, "onCreate", "V", (BUNDLE,)), ACC_PUBLIC, a.finish())
    )
    dex.add(c)
    return dex.assemble()


def keystore():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    now = datetime.now(timezone.utc)
    name = x509.Name(
        [
            x509.NameAttribute(NameOID.COUNTRY_NAME, "PL"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Czarne Wilki Prawdy"),
            x509.NameAttribute(NameOID.COMMON_NAME, "Czarne Wilki Prawdy"),
        ]
    )
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(0xC7A12E01)
        .not_valid_before(now - timedelta(days=1))
        .not_valid_after(now + timedelta(days=3650))
        .sign(key, hashes.SHA256())
    )
    return key, cert


def wrap72(line: str) -> str:
    if len(line) <= 70:
        return line
    parts = [line[:70]]
    rest = line[70:]
    while rest:
        parts.append(" " + rest[:69])
        rest = rest[69:]
    return "\r\n".join(parts)


def sign_v1(files: dict, key, cert) -> dict:
    import base64

    names = sorted(n for n in files if not n.startswith("META-INF/"))
    mf = ["Manifest-Version: 1.0", "Created-By: 1.0 (CzarneWilki)", ""]
    sections = []
    for n in names:
        digest = base64.b64encode(hashlib.sha256(files[n]).digest()).decode()
        sec = f"Name: {n}\r\nSHA-256-Digest: {digest}\r\n"
        mf.append(wrap72(f"Name: {n}"))
        mf.append(wrap72(f"SHA-256-Digest: {digest}"))
        mf.append("")
        sections.append((n, sec + "\r\n"))
    mf_bytes = ("\r\n".join(mf) + "\r\n").encode("utf-8")

    sf = [
        "Signature-Version: 1.0",
        "Created-By: 1.0 (CzarneWilki)",
        wrap72("SHA-256-Digest-Manifest: " + base64.b64encode(hashlib.sha256(mf_bytes).digest()).decode()),
        "",
    ]
    for n, sec in sections:
        sf.append(wrap72(f"Name: {n}"))
        sf.append(wrap72("SHA-256-Digest: " + base64.b64encode(hashlib.sha256(sec.encode()).digest()).decode()))
        sf.append("")
    sf_bytes = ("\r\n".join(sf) + "\r\n").encode("utf-8")

    p7 = (
        pkcs7.PKCS7SignatureBuilder()
        .set_data(sf_bytes)
        .add_signer(cert, key, hashes.SHA256())
        .sign(serialization.Encoding.DER, [pkcs7.PKCS7Options.DetachedSignature])
    )
    files = dict(files)
    files["META-INF/MANIFEST.MF"] = mf_bytes
    files["META-INF/CERT.SF"] = sf_bytes
    files["META-INF/CERT.RSA"] = p7
    return files


def zip_dos(files: dict) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for name, data in files.items():
            info = zipfile.ZipInfo(name, date_time=(2026, 8, 20, 12, 0, 0))
            info.create_system = 0
            info.create_version = 20
            info.extract_version = 20
            info.extra = b""
            info.comment = b""
            info.flag_bits = 0
            if name.endswith(".arsc"):
                info.compress_type = zipfile.ZIP_STORED
            else:
                info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, data)
    return buf.getvalue()


def build(out: Path) -> Path:
    package = "pl.czarnewilkiprawdy.app"
    activity = "pl.czarnewilkiprawdy.app.MainActivity"
    label = "Czarne Wilki Prawdy"
    files = {
        "AndroidManifest.xml": axml_manifest(package, activity, label),
        "classes.dex": make_dex(),
        "assets/identity.txt": "Czarne Wilki Prawdy – Wszyscy Won!\n".encode("utf-8"),
    }
    logo = ROOT / "assets" / "logo.png"
    if logo.exists():
        files["assets/logo.png"] = logo.read_bytes()
    key, cert = keystore()
    files = sign_v1(files, key, cert)
    raw = zip_dos(files)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(raw)
    print("APK", out, "bytes", len(raw), "dex", len(files["classes.dex"]), "manifest", len(files["AndroidManifest.xml"]))
    print("v2_block", b"APK Sig Block 42" in raw)
    return out


if __name__ == "__main__":
    dest = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "dist" / "CzarneWilkiPrawdy.apk"
    build(dest)
