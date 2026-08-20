#!/usr/bin/env python3
"""Repack a known-good Android APK with our branding. Keep original DEX/manifest/ARSC."""
from __future__ import annotations

import hashlib
import io
import struct
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import pkcs7
from cryptography.x509.oid import NameOID

ROOT = Path(__file__).resolve().parents[1]
BASE = Path("/tmp/androguard/tests/data/APK/Test-debug.apk")

TEXT = (
    "CZARNE WILKI PRAWDY – WSZYSCY WON!\n\n"
    "1 Most Android-PC\n2 Mikrofon do STOP\n3 Glosy AI\n"
    "4 Modele lokalne\n5 Siec/Offline\n6 Czat +\n7 Planer\n"
    "8 Autopost\n9 Agent\n10 Kod\n11 Naprawa\n12 E2E\n"
    "13 Radio\n14 SQLite\n15 RBAC\n16 Moderacja\n17 Alert\n"
    "18 Komentarze\n19 Bez maski\n20 Logo husarskie\n21 Wplaty\n22 QC Hetman"
)


def patch_layout_text(axml: bytes, new_text: str) -> bytes:
    """Replace the last UTF-16 string in a binary XML string pool (the TextView text)."""
    # XML header 8 bytes, then string pool at 8
    off = 8
    typ, hs, psz = struct.unpack_from("<HHI", axml, off)
    assert typ == 0x0001
    scount, stcount, flags, sstart, ystart = struct.unpack_from("<IIIII", axml, off + 8)
    assert flags == 0  # utf16
    offsets = [struct.unpack_from("<I", axml, off + 28 + 4 * i)[0] for i in range(scount)]
    data_start = off + sstart
    last = offsets[-1]
    # rebuild last string
    enc = new_text.encode("utf-16le")
    last_blob = struct.pack("<H", len(new_text)) + enc + b"\x00\x00"
    new_data = axml[data_start : data_start + last] + last_blob
    while len(new_data) % 4:
        new_data += b"\x00"
    new_psz = 28 + 4 * scount + len(new_data)
    # rest of xml after old pool
    rest = axml[off + psz :]
    new_pool = bytearray()
    new_pool.extend(struct.pack("<HHI", 0x0001, 28, new_psz))
    new_pool.extend(struct.pack("<IIIII", scount, stcount, flags, 28 + 4 * scount, 0))
    for o in offsets:
        new_pool.extend(struct.pack("<I", o))
    new_pool.extend(new_data)
    xml_total = 8 + len(new_pool) + len(rest)
    out = bytearray(struct.pack("<HHI", 0x0003, 8, xml_total))
    out.extend(new_pool)
    out.extend(rest)
    return bytes(out)


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


def sign_v1_sha1(files: dict, key, cert) -> dict:
    import base64

    names = sorted(n for n in files if not n.startswith("META-INF/"))
    mf = ["Manifest-Version: 1.0", "Created-By: 1.0 (Android)", ""]
    sections = []
    for n in names:
        digest = base64.b64encode(hashlib.sha256(files[n]).digest()).decode()
        block = f"Name: {n}\r\nSHA-256-Digest: {digest}\r\n\r\n"
        mf.append(wrap72(f"Name: {n}"))
        mf.append(wrap72(f"SHA-256-Digest: {digest}"))
        mf.append("")
        sections.append(block)
    mf_bytes = ("\r\n".join(mf) + "\r\n").encode("utf-8")

    sf = [
        "Signature-Version: 1.0",
        "Created-By: 1.0 (Android)",
        wrap72("SHA-256-Digest-Manifest: " + base64.b64encode(hashlib.sha256(mf_bytes).digest()).decode()),
        "",
    ]
    for block in sections:
        # first line is Name: ...
        name_line = block.split("\r\n")[0]
        sf.append(wrap72(name_line))
        sf.append(wrap72("SHA-256-Digest: " + base64.b64encode(hashlib.sha256(block.encode()).digest()).decode()))
        sf.append("")
    sf_bytes = ("\r\n".join(sf) + "\r\n").encode("utf-8")
    p7 = (
        pkcs7.PKCS7SignatureBuilder()
        .set_data(sf_bytes)
        .add_signer(cert, key, hashes.SHA256())
        .sign(serialization.Encoding.DER, [pkcs7.PKCS7Options.DetachedSignature])
    )
    out = dict(files)
    out["META-INF/MANIFEST.MF"] = mf_bytes
    out["META-INF/CERT.SF"] = sf_bytes
    out["META-INF/CERT.RSA"] = p7
    return out


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
            info.compress_type = zipfile.ZIP_STORED if name.endswith(".arsc") else zipfile.ZIP_DEFLATED
            z.writestr(info, data)
    return buf.getvalue()


def build(out: Path) -> Path:
    z = zipfile.ZipFile(BASE)
    files = {}
    for n in z.namelist():
        if n.startswith("META-INF/"):
            continue
        files[n] = z.read(n)
    files["res/layout/main.xml"] = patch_layout_text(files["res/layout/main.xml"], TEXT)
    files["assets/identity.txt"] = "Czarne Wilki Prawdy – Wszyscy Won!\n".encode()
    icon = ROOT / "assets" / "icon_48.png"
    if icon.exists():
        files["assets/icon.png"] = icon.read_bytes()
    key, cert = keystore()
    files = sign_v1_sha1(files, key, cert)
    raw = zip_dos(files)
    assert b"APK Sig Block 42" not in raw
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(raw)
    print("APK", out, len(raw), "files", list(files))
    return out


if __name__ == "__main__":
    build(ROOT / "dist" / "CzarneWilkiPrawdy.apk")
