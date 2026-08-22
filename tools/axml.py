#!/usr/bin/env python3
"""Binary Android XML (AXML) encoder."""
from __future__ import annotations

import struct
from typing import List, Optional, Tuple

RES_XML_TYPE = 0x0003
RES_STRING_POOL_TYPE = 0x0001
RES_XML_RESOURCE_MAP_TYPE = 0x0180
RES_XML_START_NAMESPACE_TYPE = 0x0100
RES_XML_END_NAMESPACE_TYPE = 0x0101
RES_XML_START_ELEMENT_TYPE = 0x0102
RES_XML_END_ELEMENT_TYPE = 0x0103

TYPE_NULL = 0x00
TYPE_REFERENCE = 0x01
TYPE_ATTRIBUTE = 0x02
TYPE_STRING = 0x03
TYPE_FLOAT = 0x04
TYPE_DIMENSION = 0x05
TYPE_FRACTION = 0x06
TYPE_INT_DEC = 0x10
TYPE_INT_HEX = 0x11
TYPE_INT_BOOLEAN = 0x12

NS_ANDROID = "http://schemas.android.com/apk/res/android"

# Common android attribute resource IDs
ATTR_IDS = {
    "theme": 0x01010000,
    "label": 0x01010001,
    "icon": 0x01010002,
    "name": 0x01010003,
    "permission": 0x01010006,
    "exported": 0x01010010,
    "enabled": 0x0101000E,
    "debuggable": 0x0101000F,
    "background": 0x010100D4,
    "minSdkVersion": 0x0101020C,
    "versionCode": 0x0101021B,
    "versionName": 0x0101021C,
    "targetSdkVersion": 0x01010270,
    "hardwareAccelerated": 0x010102D3,
    "allowBackup": 0x01010280,
    "supportsRtl": 0x010103AF,
    "extractNativeLibs": 0x010104EA,
    "usesCleartextTraffic": 0x010104EC,
    "appComponentFactory": 0x0101055C,
    "compileSdkVersion": 0x01010572,
    "compileSdkVersionCodename": 0x01010573,
    "roundIcon": 0x0101052C,
    "banner": 0x010103F2,
    "description": 0x01010020,
    "process": 0x01010011,
    "taskAffinity": 0x01010012,
    "multiprocess": 0x01010013,
    "excludeFromRecents": 0x01010017,
    "authorities": 0x01010018,
    "grantUriPermissions": 0x0101001B,
    "priority": 0x0101001C,
    "launchMode": 0x0101001D,
    "screenOrientation": 0x0101001E,
    "configChanges": 0x0101001F,
    "windowSoftInputMode": 0x0101022B,
    "protectionLevel": 0x0101001A,
    "required": 0x0101028E,
    "foregroundServiceType": 0x01010599,
}


class SPool:
    def __init__(self) -> None:
        self.arr: List[str] = []
        self.idx = {}

    def add(self, s: Optional[str]) -> int:
        if s is None:
            return -1
        if s not in self.idx:
            self.idx[s] = len(self.arr)
            self.arr.append(s)
        return self.idx[s]


def _utf16_pool(strings: List[str]) -> bytes:
    # UTF-16 string pool (flags = 0)
    data = bytearray()
    offsets = []
    for s in strings:
        offsets.append(len(data))
        encoded = s.encode("utf-16le")
        # charLen (ushort) + data + 00 00
        charlen = len(s)
        data.extend(struct.pack("<H", charlen))
        data.extend(encoded)
        data.extend(b"\x00\x00")
        if len(data) % 4:
            data.extend(b"\x00" * (4 - len(data) % 4))
    # Some implementations don't pad per string; Android pads each string to 4.
    header_size = 28
    strings_start = header_size + 4 * len(strings)
    chunk_size = strings_start + len(data)
    while chunk_size % 4:
        data.append(0)
        chunk_size += 1
    flags = 0  # UTF-16
    buf = bytearray()
    buf.extend(struct.pack("<HHI", RES_STRING_POOL_TYPE, header_size, chunk_size))
    buf.extend(struct.pack("<I", len(strings)))  # stringCount
    buf.extend(struct.pack("<I", 0))  # styleCount
    buf.extend(struct.pack("<I", flags))
    buf.extend(struct.pack("<I", strings_start))  # stringsStart
    buf.extend(struct.pack("<I", 0))  # stylesStart
    for off in offsets:
        buf.extend(struct.pack("<I", off))
    buf.extend(data)
    return bytes(buf)


class Attr:
    def __init__(self, name: str, value, typed=None, ns: Optional[str] = NS_ANDROID):
        self.ns = ns
        self.name = name
        self.value = value
        self.typed = typed  # (type, data) override


class Node:
    def __init__(self, name: str, attrs: Optional[List[Attr]] = None, children: Optional[List["Node"]] = None):
        self.name = name
        self.attrs = attrs or []
        self.children = children or []


def encode_manifest(root: Node, package: str, extra_strings: Optional[List[str]] = None) -> bytes:
    pool = SPool()
    pool.add(NS_ANDROID)
    pool.add("android")
    pool.add(package)

    def walk_collect(n: Node):
        pool.add(n.name)
        for a in n.attrs:
            if a.ns:
                pool.add(a.ns)
            pool.add(a.name)
            if isinstance(a.value, str) and a.typed is None:
                pool.add(a.value)
        for c in n.children:
            walk_collect(c)

    walk_collect(root)
    if extra_strings:
        for s in extra_strings:
            pool.add(s)

    # resource map for android attrs in the order they first appear as attr names that have IDs
    res_ids = []
    seen = set()
    def collect_attr_ids(n: Node):
        for a in n.attrs:
            if a.ns == NS_ANDROID and a.name in ATTR_IDS and a.name not in seen:
                # Resource map is parallel to the FIRST strings in the pool that are android attr names
                seen.add(a.name)
                res_ids.append((a.name, ATTR_IDS[a.name]))
        for c in n.children:
            collect_attr_ids(c)
    collect_attr_ids(root)

    # Android expects resource map strings to be at the start of the string pool
    # Rebuild pool: android attr names first (for resource map), then the rest.
    ordered = []
    for name, _ in res_ids:
        if name not in ordered:
            ordered.append(name)
    for s in pool.arr:
        if s not in ordered:
            ordered.append(s)
    pool.arr = ordered
    pool.idx = {s: i for i, s in enumerate(ordered)}

    def sidx(s: Optional[str]) -> int:
        if s is None:
            return 0xFFFFFFFF
        return pool.idx[s]

    body = bytearray()

    def xml_tree_header(typ, extra_header=8):
        # filled later
        return typ

    def put_ns(start: bool, prefix: str, uri: str, line=2):
        # chunk header 16 bytes + 8? 
        # ResXMLTree_node: header(8) + lineNumber(4) + comment(4) = 16
        # namespace: prefix(4) + uri(4) = 8  total 24
        typ = RES_XML_START_NAMESPACE_TYPE if start else RES_XML_END_NAMESPACE_TYPE
        chunk = bytearray()
        header_size = 16
        size = 24
        chunk.extend(struct.pack("<HHI", typ, header_size, size))
        chunk.extend(struct.pack("<I", line))
        chunk.extend(struct.pack("<I", 0xFFFFFFFF))
        chunk.extend(struct.pack("<I", sidx(prefix)))
        chunk.extend(struct.pack("<I", sidx(uri)))
        body.extend(chunk)

    def put_start(n: Node, line=3):
        attrs_bin = bytearray()
        for a in n.attrs:
            ns_i = sidx(a.ns) if a.ns else 0xFFFFFFFF
            name_i = sidx(a.name)
            raw_str = 0xFFFFFFFF
            typ, data = 0, 0
            if a.typed:
                typ, data = a.typed
                if typ == TYPE_STRING:
                    raw_str = data
            elif isinstance(a.value, bool):
                typ, data = TYPE_INT_BOOLEAN, (0xFFFFFFFF if a.value else 0)
            elif isinstance(a.value, int):
                typ, data = TYPE_INT_DEC, a.value & 0xFFFFFFFF
            else:
                raw_str = sidx(str(a.value))
                typ, data = TYPE_STRING, raw_str
            # ResXMLTree_attribute: ns, name, rawValue, size(2), res0(1), dataType(1), data(4) = 20
            attrs_bin.extend(struct.pack("<III", ns_i, name_i, raw_str))
            attrs_bin.extend(struct.pack("<HBBI", 8, 0, typ, data & 0xFFFFFFFF))

        # start element:
        # node header 16
        # ns, name 8
        # attrStart(2) attrSize(2) attrCount(2) idIndex(2) classIndex(2) styleIndex(2) = 12
        # + attrs
        header_size = 16
        ext = 8 + 12
        size = 16 + ext + len(attrs_bin)
        body.extend(struct.pack("<HHI", RES_XML_START_ELEMENT_TYPE, header_size, size))
        body.extend(struct.pack("<I", line))
        body.extend(struct.pack("<I", 0xFFFFFFFF))
        body.extend(struct.pack("<I", 0xFFFFFFFF))  # element ns
        body.extend(struct.pack("<I", sidx(n.name)))
        body.extend(struct.pack("<HH", 20, 20))  # attrStart, attrSize (from start of ext? )
        # attrStart is offset from start of ResXMLTree_attrExt to first attribute = 20
        body.extend(struct.pack("<HHHH", len(n.attrs), 0, 0, 0))  # count, id, class, style
        # Wait we already packed attrStart/attrSize as HH, then need count as H...
        # I doubled. Fix below by rewriting this function carefully.

        # This function is replaced.

    # Rewrite start/end properly
    body = bytearray()

    def start_ns():
        put_ns(True, "android", NS_ANDROID, 1)

    def end_ns():
        put_ns(False, "android", NS_ANDROID, 100)

    def start_el(n: Node, line=4):
        attr_blobs = []
        for a in n.attrs:
            ns_i = sidx(a.ns) if a.ns else 0xFFFFFFFF
            name_i = sidx(a.name)
            raw_str = 0xFFFFFFFF
            if a.typed:
                typ, data = a.typed
                if typ == TYPE_STRING:
                    raw_str = data
            elif isinstance(a.value, bool):
                typ, data = TYPE_INT_BOOLEAN, (0xFFFFFFFF if a.value else 0)
            elif isinstance(a.value, int):
                typ, data = TYPE_INT_DEC, a.value & 0xFFFFFFFF
            else:
                raw_str = sidx(str(a.value))
                typ, data = TYPE_STRING, raw_str
            blob = bytearray()
            blob.extend(struct.pack("<III", ns_i, name_i, raw_str))
            blob.extend(struct.pack("<HBBI", 8, 0, typ, data & 0xFFFFFFFF))
            attr_blobs.append(bytes(blob))
        attrs_bin = b"".join(attr_blobs)
        # ResXMLTree_node
        # header.size includes everything
        # header.headerSize = 16
        # then line, comment
        # ResXMLTree_attrExt starts: ns, name, attributeStart, attributeSize, attributeCount, idIndex, classIndex, styleIndex
        # attributeStart = 20 (size of attrExt)
        header_size = 16
        size = 16 + 20 + len(attrs_bin)
        body.extend(struct.pack("<HHI", RES_XML_START_ELEMENT_TYPE, header_size, size))
        body.extend(struct.pack("<II", line, 0xFFFFFFFF))
        body.extend(struct.pack("<II", 0xFFFFFFFF, sidx(n.name)))  # ns, name
        body.extend(struct.pack("<HH", 20, 20))  # attributeStart, attributeSize
        body.extend(struct.pack("<HHHH", len(n.attrs), 0, 0, 0))

        body.extend(attrs_bin)

    def end_el(n: Node, line=5):
        header_size = 16
        size = 24
        body.extend(struct.pack("<HHI", RES_XML_END_ELEMENT_TYPE, header_size, size))
        body.extend(struct.pack("<II", line, 0xFFFFFFFF))
        body.extend(struct.pack("<II", 0xFFFFFFFF, sidx(n.name)))

    def emit(n: Node, line=[10]):
        start_el(n, line[0])
        line[0] += 1
        for c in n.children:
            emit(c, line)
        end_el(n, line[0])
        line[0] += 1

    start_ns()
    emit(root)
    end_ns()

    sp = _utf16_pool(pool.arr)

    # resource map chunk
    rm = bytearray()
    ids_only = [rid for _, rid in res_ids]
    rm_header = 8
    rm_size = rm_header + 4 * len(ids_only)
    rm.extend(struct.pack("<HHI", RES_XML_RESOURCE_MAP_TYPE, rm_header, rm_size))
    for rid in ids_only:
        rm.extend(struct.pack("<I", rid))

    inner = sp + bytes(rm) + bytes(body)
    file_header_size = 8
    total = file_header_size + len(inner)
    out = bytearray()
    out.extend(struct.pack("<HHI", RES_XML_TYPE, file_header_size, total))
    out.extend(inner)
    return bytes(out)


def ref(resid: int) -> Tuple[int, int]:
    return TYPE_REFERENCE, resid
