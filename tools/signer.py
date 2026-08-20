#!/usr/bin/env python3
"""APK v1 (JAR) + v2 signing."""
from __future__ import annotations

import hashlib
import io
import struct
import zipfile
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Tuple

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.serialization import pkcs7
from cryptography.x509.oid import NameOID


def make_keystore():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name(
        [
            x509.NameAttribute(NameOID.COUNTRY_NAME, "PL"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Czarne Wilki Prawdy"),
            x509.NameAttribute(NameOID.COMMON_NAME, "Czarne Wilki Prawdy"),
        ]
    )
    now = datetime.now(timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(0xC7A12E01)
        .not_valid_before(now - timedelta(days=1))
        .not_valid_after(now + timedelta(days=3650))
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .sign(key, hashes.SHA256())
    )
    return key, cert


def _digest_hex(data: bytes) -> str:
    return hashlib.sha256(data).digest().hex()


def sign_v1(unsigned_apk: bytes, key, cert) -> bytes:
    zsrc = zipfile.ZipFile(io.BytesIO(unsigned_apk), "r")
    digests: Dict[str, str] = {}
    contents: Dict[str, Tuple[bytes, zipfile.ZipInfo]] = {}
    for info in zsrc.infolist():
        if info.filename.startswith("META-INF/"):
            continue
        data = zsrc.read(info.filename)
        digests[info.filename] = _digest_hex(data)
        contents[info.filename] = (data, info)
    zsrc.close()

    mf_lines = ["Manifest-Version: 1.0", "Created-By: CzarneWilkiPacker", ""]
    for name in sorted(digests):
        mf_lines.append(f"Name: {name}")
        mf_lines.append(f"SHA-256-Digest: {__import__('base64').b64encode(bytes.fromhex(digests[name])).decode()}")
        mf_lines.append("")
    mf = ("\r\n".join(mf_lines) + "\r\n").encode("utf-8")

    import base64

    sf_lines = [
        "Signature-Version: 1.0",
        "Created-By: CzarneWilkiPacker",
        "SHA-256-Digest-Manifest: " + base64.b64encode(hashlib.sha256(mf).digest()).decode(),
        "X-Android-APK-Signed: 2",
        "",
    ]
    # per-entry digest of the manifest section
    # Reconstruct sections from mf
    parts = mf.decode().split("\r\n\r\n")
    for section in parts[1:]:
        if not section.strip():
            continue
        sec = (section + "\r\n\r\n").encode()
        name_line = section.split("\r\n")[0]
        sf_lines.append(name_line)
        sf_lines.append("SHA-256-Digest: " + base64.b64encode(hashlib.sha256(sec).digest()).decode())
        sf_lines.append("")
    sf = ("\r\n".join(sf_lines) + "\r\n").encode("utf-8")

    p7 = (
        pkcs7.PKCS7SignatureBuilder()
        .set_data(sf)
        .add_signer(cert, key, hashes.SHA256())
        .sign(serialization.Encoding.DER, [pkcs7.PKCS7Options.DetachedSignature])
    )

    out = io.BytesIO()
    zdst = zipfile.ZipFile(out, "w")
    for name in sorted(contents):
        data, info = contents[name]
        zin = zipfile.ZipInfo(name, date_time=info.date_time)
        zin.compress_type = info.compress_type
        zdst.writestr(zin, data)
    for name, data in (
        ("META-INF/MANIFEST.MF", mf),
        ("META-INF/CERT.SF", sf),
        ("META-INF/CERT.RSA", p7),
    ):
        zin = zipfile.ZipInfo(name)
        zin.compress_type = zipfile.ZIP_DEFLATED
        zdst.writestr(zin, data)
    zdst.close()
    return out.getvalue()


def _chunked_sha256(data: bytes) -> bytes:
    """APK sig v2 chunked digest: 0x5a + uint32le(chunk_count) + sha256(0xa5||uint32le(len)||chunk)*"""
    chunk_size = 1024 * 1024
    chunks = []
    for i in range(0, len(data), chunk_size):
        chunk = data[i : i + chunk_size]
        h = hashlib.sha256()
        h.update(b"\xa5")
        h.update(struct.pack("<I", len(chunk)))
        h.update(chunk)
        chunks.append(h.digest())
    top = hashlib.sha256()
    top.update(b"\x5a")
    top.update(struct.pack("<I", len(chunks)))
    for c in chunks:
        top.update(c)
    return top.digest()


def _len_pref(data: bytes, width=4) -> bytes:
    if width == 4:
        return struct.pack("<I", len(data)) + data
    raise ValueError


def sign_v2(apk: bytes, key, cert) -> bytes:
    """Insert APK Signing Block before EOCD."""
    # Find EOCD
    eocd_sig = b"PK\x05\x06"
    pos = apk.rfind(eocd_sig)
    if pos < 0:
        raise ValueError("EOCD not found")
    disk = struct.unpack_from("<H", apk, pos + 4)[0]
    cd_disk = struct.unpack_from("<H", apk, pos + 6)[0]
    n_this = struct.unpack_from("<H", apk, pos + 8)[0]
    n_total = struct.unpack_from("<H", apk, pos + 10)[0]
    cd_size = struct.unpack_from("<I", apk, pos + 12)[0]
    cd_off = struct.unpack_from("<I", apk, pos + 16)[0]
    comment_len = struct.unpack_from("<H", apk, pos + 20)[0]
    eocd = apk[pos:]
    cd = apk[cd_off : cd_off + cd_size]
    before = apk[:cd_off]

    # Algorithm 0x0103: RSASSA-PKCS1-v1_5 with SHA2-256, chunks SHA256
    algo_id = 0x0103
    digest = _chunked_sha256(before + cd + eocd)

    cert_der = cert.public_bytes(serialization.Encoding.DER)
    pub_der = key.public_key().public_bytes(
        serialization.Encoding.DER,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )

    # signed data
    digest_seq = _len_pref(struct.pack("<I", algo_id) + _len_pref(digest))
    digests_block = _len_pref(digest_seq)
    certs_block = _len_pref(_len_pref(cert_der))
    attrs_block = _len_pref(b"")
    signed_data = _len_pref(digests_block + certs_block + attrs_block)

    signature = key.sign(signed_data, padding.PKCS1v15(), hashes.SHA256())
    sig_seq = _len_pref(struct.pack("<I", algo_id) + _len_pref(signature))
    sigs_block = _len_pref(sig_seq)
    pub_block = _len_pref(pub_der)
    signer = _len_pref(signed_data + sigs_block + pub_block)
    v2_block = _len_pref(signer)

    # APK Signing Block:
    # uint64 size_of_block
    # pairs: uint64 len + uint32 id + value  (len includes id?)
    #   length = sizeof(id)+sizeof(value)
    # uint64 size_of_block (again)
    # magic 16 bytes
    magic = b"APK Sig Block 42"
    pair = struct.pack("<I", 0x7109871A) + v2_block  # id + value
    pair_with_len = struct.pack("<Q", len(pair)) + pair
    # padding to 4096? not required
    size_of_block = 8 + len(pair_with_len) + 8 + 16  # first size not counted? 
    # Spec: size of block = length of the entire block minus the first uint64
    # block = uint64(size) + pairs + uint64(size) + magic
    # size = len(pairs)+8+16
    size = len(pair_with_len) + 8 + 16
    signing_block = struct.pack("<Q", size) + pair_with_len + struct.pack("<Q", size) + magic

    new_cd_off = cd_off + len(signing_block)
    new_eocd = bytearray(eocd)
    struct.pack_into("<I", new_eocd, 16, new_cd_off)
    return before + signing_block + cd + bytes(new_eocd)


def sign_apk(unsigned: bytes, key=None, cert=None) -> bytes:
    if key is None:
        key, cert = make_keystore()
    v1 = sign_v1(unsigned, key, cert)
    return sign_v2(v1, key, cert)
