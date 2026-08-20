#!/usr/bin/env python3
"""Minimal resources.arsc writer: package 0x7f with drawable/ic_launcher and app_name string."""
from __future__ import annotations

import struct
from typing import List


RES_TABLE_TYPE = 0x0002
RES_STRING_POOL_TYPE = 0x0001
RES_TABLE_PACKAGE_TYPE = 0x0200
RES_TABLE_TYPE_SPEC_TYPE = 0x0202
RES_TABLE_TYPE_TYPE = 0x0201

UTF8_FLAG = 1 << 8


def _utf16_pool(strings: List[str], with_styles=False) -> bytes:
    data = bytearray()
    offsets = []
    for s in strings:
        offsets.append(len(data))
        data.extend(struct.pack("<H", len(s)))
        data.extend(s.encode("utf-16le"))
        data.extend(b"\x00\x00")
        while len(data) % 4:
            data.append(0)
    header_size = 28
    strings_start = header_size + 4 * len(strings)
    chunk_size = strings_start + len(data)
    while chunk_size % 4:
        data.append(0)
        chunk_size += 1
    buf = bytearray()
    buf.extend(struct.pack("<HHI", RES_STRING_POOL_TYPE, header_size, chunk_size))
    buf.extend(struct.pack("<IIIIII", len(strings), 0, 0, strings_start, 0))
    # wait that's 5 I after? header already has HHI. stringCount, styleCount, flags, stringsStart, stylesStart = 5I
    # I packed 6I. Fix.
    return b""  # replaced below


def utf16_pool(strings: List[str]) -> bytes:
    data = bytearray()
    offsets = []
    for s in strings:
        offsets.append(len(data))
        data.extend(struct.pack("<H", len(s)))
        data.extend(s.encode("utf-16le"))
        data.extend(b"\x00\x00")
        while len(data) % 4:
            data.append(0)
    header_size = 28
    strings_start = header_size + 4 * len(strings)
    pad = (4 - (len(data) % 4)) % 4
    data.extend(b"\x00" * pad)
    chunk_size = strings_start + len(data)
    buf = bytearray()
    buf.extend(struct.pack("<HHI", RES_STRING_POOL_TYPE, header_size, chunk_size))
    buf.extend(
        struct.pack(
            "<IIIII",
            len(strings),
            0,
            0,
            strings_start,
            0,
        )
    )
    for off in offsets:
        buf.extend(struct.pack("<I", off))
    buf.extend(data)
    return bytes(buf)


def pad_name_128(s: str) -> bytes:
    b = s.encode("utf-16le")
    if len(b) > 256:
        b = b[:256]
    return b + b"\x00" * (256 - len(b))


def build_arsc(app_name: str = "Czarne Wilki Prawdy") -> bytes:
    """
    IDs:
      0x7f010000  attr unused skip
    We use:
      type 1 = drawable  -> 0x7f010000 ic_launcher  (file)
      type 2 = string    -> 0x7f020000 app_name
    """
    global_strings = [
        "res/drawable/ic_launcher.png",
        app_name,
    ]
    global_pool = utf16_pool(global_strings)

    type_strings = utf16_pool(["drawable", "string"])
    key_strings = utf16_pool(["ic_launcher", "app_name"])

    # typeSpec drawable (id=1)
    def type_spec(type_id: int, entry_count: int) -> bytes:
        header_size = 16
        size = header_size + 4 * entry_count
        buf = bytearray()
        buf.extend(struct.pack("<HHI", RES_TABLE_TYPE_SPEC_TYPE, header_size, size))
        buf.extend(struct.pack("<BBH I", type_id, 0, 0, entry_count))
        for _ in range(entry_count):
            buf.extend(struct.pack("<I", 0))
        return bytes(buf)

    def type_chunk_file(type_id: int, string_pool_index: int) -> bytes:
        # one entry, default config
        # ResTable_type headerSize is 0x44 (68) for 32-byte config? Older is 0x38 (56)
        # Use 0x44 with 64-byte ResTable_config? Simpler: headerSize 20 + 36 config? 
        # Standard aapt: headerSize = 0x44, config size 0x40
        entry = bytearray()
        # ResTable_entry: size(2)=8, flags(2)=0, key(4)=0
        entry.extend(struct.pack("<HHI", 8, 0, 0))
        # Res_value: size(2)=8, res0(1)=0, dataType(1)=0x03 string, data(4)=index
        entry.extend(struct.pack("<HBBI", 8, 0, 0x03, string_pool_index))

        config = b"\x40" + b"\x00" * 63  # size=64 rest zero = default
        header_size = 12 + 4 + 4 + 64  # type, headerSize, size, id+res, entryCount, entriesStart, config
        # ResTable_type:
        # ResChunk_header (8) but headerSize includes config
        # Actual: headerSize = 0x44 = 68 = 8 + 4 (id) + 4 (entryCount) + 4 (entriesStart) + 48? 
        # AOSP ResTable_type: header, id, res0, res1, entryCount, entriesStart, config
        # If config.sizeof = 36 (old), headerSize = 8+1+1+2+4+4+36 = 56 = 0x38
        config36 = struct.pack("<I", 36) + b"\x00" * 32  # size field + 32
        entries_start = 56
        chunk_size = entries_start + 4 + len(entry)  # + offset table 4 bytes
        buf = bytearray()
        buf.extend(struct.pack("<HHI", RES_TABLE_TYPE_TYPE, 56, chunk_size))
        buf.extend(struct.pack("<BBH", type_id, 0, 0))
        buf.extend(struct.pack("<I", 1))  # entryCount
        buf.extend(struct.pack("<I", entries_start))
        buf.extend(config36)
        buf.extend(struct.pack("<I", 0))  # offset of entry 0 from entriesStart
        buf.extend(entry)
        return bytes(buf)

    spec1 = type_spec(1, 1)
    type1 = type_chunk_file(1, 0)
    spec2 = type_spec(2, 1)
    type2 = type_chunk_file(2, 1)

    pkg_body = type_strings + key_strings + spec1 + type1 + spec2 + type2
    # ResTable_package headerSize = 288 (0x120)
    pkg_header_size = 288
    pkg_size = pkg_header_size + len(pkg_body)
    pkg = bytearray()
    pkg.extend(struct.pack("<HHI", RES_TABLE_PACKAGE_TYPE, pkg_header_size, pkg_size))
    pkg.extend(struct.pack("<I", 0x7F))  # id
    pkg.extend(pad_name_128("czarne"))
    type_strings_off = pkg_header_size
    last_public_type = 2
    key_strings_off = pkg_header_size + len(type_strings)
    last_public_key = 2
    pkg.extend(struct.pack("<I", type_strings_off))
    pkg.extend(struct.pack("<I", last_public_type))
    pkg.extend(struct.pack("<I", key_strings_off))
    pkg.extend(struct.pack("<I", last_public_key))
    # remaining header to 288: 8+4+256+16 = 284, need 4 more (typeIdOffset)
    pkg.extend(struct.pack("<I", 0))
    assert len(pkg) == pkg_header_size, len(pkg)
    pkg.extend(pkg_body)

    table_header_size = 12
    table_size = table_header_size + len(global_pool) + len(pkg)
    table = bytearray()
    table.extend(struct.pack("<HHI", RES_TABLE_TYPE, table_header_size, table_size))
    table.extend(struct.pack("<I", 1))  # package count
    table.extend(global_pool)
    table.extend(pkg)
    return bytes(table)
