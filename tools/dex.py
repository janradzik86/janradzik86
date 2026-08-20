#!/usr/bin/env python3
"""Dalvik DEX file writer (DEX 035) — enough of the format to ship real Android classes."""
from __future__ import annotations

import hashlib
import struct
import zlib
from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Union

# Access flags
ACC_PUBLIC = 0x1
ACC_PRIVATE = 0x2
ACC_PROTECTED = 0x4
ACC_STATIC = 0x8
ACC_FINAL = 0x10
ACC_SUPER = 0x20
ACC_SYNCHRONIZED = 0x20
ACC_VOLATILE = 0x40
ACC_BRIDGE = 0x40
ACC_TRANSIENT = 0x80
ACC_VARARGS = 0x80
ACC_NATIVE = 0x100
ACC_INTERFACE = 0x200
ACC_ABSTRACT = 0x400
ACC_STRICT = 0x800
ACC_SYNTHETIC = 0x1000
ACC_ANNOTATION = 0x2000
ACC_ENUM = 0x4000
ACC_CONSTRUCTOR = 0x10000


def uleb128(n: int) -> bytes:
    out = bytearray()
    while True:
        b = n & 0x7F
        n >>= 7
        if n:
            out.append(b | 0x80)
        else:
            out.append(b)
            break
    return bytes(out)


def sleb128(n: int) -> bytes:
    n = n & 0xFFFFFFFF
    if n >= 0x80000000:
        n -= 0x100000000
    out = bytearray()
    more = True
    while more:
        b = n & 0x7F
        n >>= 7
        if n == 0 and (b & 0x40) == 0:
            more = False
        elif n == -1 and (b & 0x40):
            more = False
        else:
            b |= 0x80
        out.append(b)
    return bytes(out)


def mutf8(s: str) -> bytes:
    out = bytearray()
    for ch in s:
        c = ord(ch)
        if c == 0:
            out.extend(b"\xc0\x80")
        elif c < 0x80:
            out.append(c)
        elif c < 0x800:
            out.append(0xC0 | (c >> 6))
            out.append(0x80 | (c & 0x3F))
        elif c < 0x10000:
            out.append(0xE0 | (c >> 12))
            out.append(0x80 | ((c >> 6) & 0x3F))
            out.append(0x80 | (c & 0x3F))
        else:
            # surrogate pair as CESU-8
            c -= 0x10000
            s1 = 0xD800 | (c >> 10)
            s2 = 0xDC00 | (c & 0x3FF)
            for x in (s1, s2):
                out.append(0xE0 | (x >> 12))
                out.append(0x80 | ((x >> 6) & 0x3F))
                out.append(0x80 | (x & 0x3F))
    return bytes(out)


def align4(buf: bytearray) -> None:
    while len(buf) % 4:
        buf.append(0)


class DexPool:
    def __init__(self) -> None:
        self.strings: List[str] = []
        self._si = {}
        self.types: List[str] = []
        self._ti = {}
        self.protos: List[Tuple[str, Tuple[str, ...], str]] = []  # shorty, params, ret
        self._pi = {}
        self.fields: List[Tuple[str, str, str]] = []  # class, type, name
        self._fi = {}
        self.methods: List[Tuple[str, Tuple[str, Tuple[str, ...], str], str]] = []
        self._mi = {}

    def string(self, s: str) -> int:
        if s not in self._si:
            self._si[s] = len(self.strings)
            self.strings.append(s)
        return self._si[s]

    def typ(self, t: str) -> int:
        self.string(t)
        if t not in self._ti:
            self._ti[t] = len(self.types)
            self.types.append(t)
        return self._ti[t]

    def proto(self, ret: str, params: Tuple[str, ...] = ()) -> int:
        shorty = _shorty(ret, params)
        self.string(shorty)
        self.typ(ret)
        for p in params:
            self.typ(p)
        key = (shorty, params, ret)
        if key not in self._pi:
            self._pi[key] = len(self.protos)
            self.protos.append(key)
        return self._pi[key]

    def field(self, cls: str, typ: str, name: str) -> int:
        self.typ(cls)
        self.typ(typ)
        self.string(name)
        key = (cls, typ, name)
        if key not in self._fi:
            self._fi[key] = len(self.fields)
            self.fields.append(key)
        return self._fi[key]

    def method(self, cls: str, name: str, ret: str, params: Tuple[str, ...] = ()) -> int:
        self.typ(cls)
        self.string(name)
        p = self.proto(ret, params)
        proto = self.protos[p]
        key = (cls, proto, name)
        if key not in self._mi:
            self._mi[key] = len(self.methods)
            self.methods.append(key)
        return self._mi[key]


def _shorty(ret: str, params: Tuple[str, ...]) -> str:
    def one(t: str) -> str:
        if t in ("V", "Z", "B", "S", "C", "I", "J", "F", "D"):
            return t
        return "L"

    return one(ret) + "".join(one(p) for p in params)


# Instruction helpers: return list of 16-bit code units
def op_unit(op: int, aa: int = 0) -> int:
    return (aa << 8) | op


@dataclass
class CodeItem:
    registers: int
    ins_size: int
    outs_size: int
    insns: List[int]  # 16-bit units
    tries: List = field(default_factory=list)


@dataclass
class EncodedField:
    idx: int
    access: int


@dataclass
class EncodedMethod:
    idx: int
    access: int
    code: Optional[CodeItem]


@dataclass
class ClassDef:
    name: str
    super_name: str
    access: int = ACC_PUBLIC | ACC_SUPER
    interfaces: Tuple[str, ...] = ()
    source: str = "Wolf.java"
    static_fields: List[EncodedField] = field(default_factory=list)
    instance_fields: List[EncodedField] = field(default_factory=list)
    direct_methods: List[EncodedMethod] = field(default_factory=list)
    virtual_methods: List[EncodedMethod] = field(default_factory=list)


class DexFile:
    def __init__(self) -> None:
        self.pool = DexPool()
        self.classes: List[ClassDef] = []

    def add(self, c: ClassDef) -> None:
        self.pool.typ(c.name)
        self.pool.typ(c.super_name)
        for i in c.interfaces:
            self.pool.typ(i)
        self.pool.string(c.source)
        self.classes.append(c)

    def assemble(self) -> bytes:
        p = self.pool
        # Ensure every referenced string/type exists (already done via helpers)
        # Sort string ids lexicographically as MUTF-8 — DEX requires sorted string_ids
        # We rebuild indices: easiest is to keep insertion and NOT sort if we sort at the end
        # Spec: string_ids must be ordered by string contents. type_ids by string idx. etc.
        return _assemble_sorted(self)


def _assemble_sorted(dex: DexFile) -> bytes:
    # Collect ALL strings by walking structures after dummy index assignment,
    # then rebuild with sorted pools.
    raw_strings = set()
    raw_types = []
    seen_t = set()

    def add_s(s):
        raw_strings.add(s)

    def add_t(t):
        add_s(t)
        if t not in seen_t:
            seen_t.add(t)
            raw_types.append(t)

    for c in dex.classes:
        add_t(c.name)
        add_t(c.super_name)
        for i in c.interfaces:
            add_t(i)
        add_s(c.source)

    # We need to re-index methods/fields/protos from original pool lists
    # First gather from original pool
    orig = dex.pool
    for s in orig.strings:
        add_s(s)
    for t in orig.types:
        add_t(t)

    strings = sorted(raw_strings)
    s_index = {s: i for i, s in enumerate(strings)}
    types = sorted(orig.types, key=lambda t: s_index[t])
    # include any extra
    extra_types = [t for t in raw_types if t not in orig.types]
    types = sorted(set(orig.types) | set(raw_types), key=lambda t: s_index[t])
    t_index = {t: i for i, t in enumerate(types)}

    protos = sorted(orig.protos, key=lambda pr: (s_index[pr[0]], t_index[pr[2]], [t_index[x] for x in pr[1]]))
    p_index = {pr: i for i, pr in enumerate(protos)}

    fields = sorted(orig.fields, key=lambda f: (t_index[f[0]], s_index[f[2]], t_index[f[1]]))
    f_index = {f: i for i, f in enumerate(fields)}

    methods = sorted(orig.methods, key=lambda m: (t_index[m[0]], s_index[m[2]], p_index[m[1]]))
    m_index = {m: i for i, m in enumerate(methods)}

    # Remap method/field indices inside bytecode: we stored indices via orig pool.
    # Bytecode contains method/field/string/type idxs from orig. Must rewrite.
    old_string = orig._si
    old_type = orig._ti
    old_field = orig._fi
    old_method = orig._mi
    old_proto = orig._pi

    def map_string_idx(i):
        return s_index[orig.strings[i]]

    def map_type_idx(i):
        return t_index[orig.types[i]]

    def map_field_idx(i):
        return f_index[orig.fields[i]]

    def map_method_idx(i):
        return m_index[orig.methods[i]]

    def rewrite_insns(insns: List[int]) -> List[int]:
        out = []
        i = 0
        n = len(insns)
        while i < n:
            unit = insns[i]
            op = unit & 0xFF
            fmt, width = OP_FMT.get(op, ("10x", 1))
            chunk = insns[i : i + width]
            chunk = list(chunk)
            if fmt in ("21c", "31c", "21c_string"):
                # BBBB is index
                kind = OP_INDEX_KIND.get(op, "string")
                idx = chunk[1]
                if kind == "string":
                    chunk[1] = map_string_idx(idx)
                elif kind == "type":
                    chunk[1] = map_type_idx(idx)
                elif kind == "field":
                    chunk[1] = map_field_idx(idx)
                elif kind == "method":
                    chunk[1] = map_method_idx(idx)
            elif fmt == "35c":
                idx = chunk[1]
                kind = OP_INDEX_KIND.get(op, "method")
                if kind == "method":
                    chunk[1] = map_method_idx(idx)
                elif kind == "type":
                    chunk[1] = map_type_idx(idx)
            elif fmt == "3rc":
                idx = chunk[1]
                kind = OP_INDEX_KIND.get(op, "method")
                if kind == "method":
                    chunk[1] = map_method_idx(idx)
                elif kind == "type":
                    chunk[1] = map_type_idx(idx)
            elif fmt == "22c":
                idx = chunk[1]
                kind = OP_INDEX_KIND.get(op, "field")
                if kind == "field":
                    chunk[1] = map_field_idx(idx)
                elif kind == "type":
                    chunk[1] = map_type_idx(idx)
            out.extend(chunk)
            i += width
        return out

    # Build data section
    data = bytearray()
    map_items = []  # (type, size, offset)

    def add_map(typ, size, off):
        map_items.append((typ, size, off))

    # We'll write ids first in a later buffer. First produce data payloads.

    # string_data
    string_data_offs = []
    for s in strings:
        string_data_offs.append(None)  # filled later

    # We'll compose file as: header + ids + data
    # Compute sizes
    header_size = 0x70
    string_ids_off = header_size
    string_ids_size = len(strings)
    type_ids_off = string_ids_off + 4 * string_ids_size
    type_ids_size = len(types)
    proto_ids_off = type_ids_off + 4 * type_ids_size
    proto_ids_size = len(protos)
    field_ids_off = proto_ids_off + 12 * proto_ids_size
    field_ids_size = len(fields)
    method_ids_off = field_ids_off + 8 * field_ids_size
    method_ids_size = len(methods)
    class_defs_off = method_ids_off + 8 * method_ids_size
    class_defs_size = len(dex.classes)
    data_off = class_defs_off + 32 * class_defs_size
    # align data_off to 4
    while data_off % 4:
        data_off += 1

    data = bytearray()

    def here():
        return data_off + len(data)

    def pad4():
        align4(data)

    # annotation_set empty skip

    # code items + class data
    class_data_offs = []
    static_values_offs = []
    interfaces_offs = []
    source_offs = []  # not used separately

    # type_list for protos and interfaces
    type_list_cache = {}

    def write_type_list(params: Tuple[str, ...]) -> int:
        if not params:
            return 0
        key = params
        if key in type_list_cache:
            return type_list_cache[key]
        pad4()
        off = here()
        data.extend(struct.pack("<I", len(params)))
        for t in params:
            data.extend(struct.pack("<H", t_index[t]))
        pad4()
        type_list_cache[key] = off
        return off

    proto_param_offs = [write_type_list(pr[1]) for pr in protos]

    iface_offs_for_class = []
    for c in dex.classes:
        iface_offs_for_class.append(write_type_list(c.interfaces) if c.interfaces else 0)

    def write_code(code: CodeItem) -> int:
        pad4()
        off = here()
        insns = rewrite_insns(code.insns)
        insns_size = len(insns)
        data.extend(
            struct.pack(
                "<HHHHII",
                code.registers,
                0,  # ins_size overwritten
                code.ins_size,
                code.outs_size,
                0,  # tries
                0,  # debug
            )
        )
        # fix: format is registers_size, ins_size, outs_size, tries_size, debug_off, insns_size
        # I packed wrong. Rewrite last bytes.
        data[-16:] = struct.pack(
            "<HHHHI I",
            code.registers,
            code.ins_size,
            code.outs_size,
            0,
            0,
            insns_size,
        )
        # The above might be ambiguous due to space. Use explicit.
        return off  # placeholder, we'll rewrite properly below

    # redo write_code correctly
    data = bytearray()
    type_list_cache = {}

    def write_type_list(params: Tuple[str, ...]) -> int:
        if not params:
            return 0
        if params in type_list_cache:
            return type_list_cache[params]
        pad4()
        off = here()
        data.extend(struct.pack("<I", len(params)))
        for t in params:
            data.extend(struct.pack("<H", t_index[t]))
        pad4()
        type_list_cache[params] = off
        return off

    proto_param_offs = [write_type_list(pr[1]) for pr in protos]
    iface_offs_for_class = [
        write_type_list(c.interfaces) if c.interfaces else 0 for c in dex.classes
    ]

    def write_code(code: CodeItem) -> int:
        pad4()
        off = here()
        insns = rewrite_insns(code.insns)
        insns_size = len(insns)
        debug_off = 0
        tries_size = 0
        data.extend(
            struct.pack(
                "<HHHHII",
                code.registers,
                code.ins_size,
                code.outs_size,
                tries_size,
                debug_off,
                insns_size,
            )
        )
        for u in insns:
            data.extend(struct.pack("<H", u & 0xFFFF))
        if insns_size % 2 == 1:
            data.extend(b"\x00\x00")  # padding to 4-byte for tries; still pad
        pad4()
        return off

    def write_encoded_array_empty():
        return 0

    def write_class_data(c: ClassDef) -> int:
        # must write method code first
        def enc_methods(lst: List[EncodedMethod]) -> bytes:
            buf = bytearray()
            last = 0
            for em in lst:
                diff = em.idx - last
                last = em.idx
                buf += uleb128(diff)
                buf += uleb128(em.access)
                if em.code is None:
                    buf += uleb128(0)
                else:
                    buf += uleb128(write_code(em.code))
            return bytes(buf)

        def enc_fields(lst: List[EncodedField]) -> bytes:
            buf = bytearray()
            last = 0
            for ef in lst:
                diff = ef.idx - last
                last = ef.idx
                buf += uleb128(diff)
                buf += uleb128(ef.access)
            return bytes(buf)

        # Remap field/method idx
        def remap_field(ef: EncodedField) -> EncodedField:
            return EncodedField(f_index[orig.fields[ef.idx]], ef.access)

        def remap_method(em: EncodedMethod) -> EncodedMethod:
            return EncodedMethod(m_index[orig.methods[em.idx]], em.access, em.code)

        sf = [remap_field(x) for x in c.static_fields]
        inf = [remap_field(x) for x in c.instance_fields]
        dm = [remap_method(x) for x in c.direct_methods]
        vm = [remap_method(x) for x in c.virtual_methods]
        sf.sort(key=lambda x: x.idx)
        inf.sort(key=lambda x: x.idx)
        dm.sort(key=lambda x: x.idx)
        vm.sort(key=lambda x: x.idx)

        # Write codes first (append to data), then class_data item
        # enc_methods calls write_code which appends — so we need two-phase:
        # 1 collect code offsets
        def methods_blob(lst: List[EncodedMethod]) -> bytes:
            buf = bytearray()
            last = 0
            for em in lst:
                diff = em.idx - last
                last = em.idx
                buf += uleb128(diff)
                buf += uleb128(em.access)
                if em.code is None:
                    buf += uleb128(0)
                else:
                    buf += uleb128(write_code(em.code))
            return bytes(buf)

        blob_fields_s = enc_fields(sf)
        blob_fields_i = enc_fields(inf)
        blob_dm = methods_blob(dm)
        blob_vm = methods_blob(vm)
        off = here()
        data.extend(uleb128(len(sf)))
        data.extend(uleb128(len(inf)))
        data.extend(uleb128(len(dm)))
        data.extend(uleb128(len(vm)))
        data.extend(blob_fields_s)
        data.extend(blob_fields_i)
        data.extend(blob_dm)
        data.extend(blob_vm)
        return off

    class_data_offs = [write_class_data(c) for c in dex.classes]

    # string data
    pad4()
    string_data_offs = []
    for s in strings:
        string_data_offs.append(here())
        enc = mutf8(s)
        data.extend(uleb128(len(s)))  # UTF-16 length (code points approx)
        data.extend(enc)
        data.append(0)

    # map list at end of data
    pad4()
    map_off = here()
    # We'll fill map after we know id section types — map includes header and ids too
    # For now write placeholder, then patch. Easier: build full file then compute map
    # Let's build map now with known offsets
    map_entries = []
    map_entries.append((0x0000, 1, 0))  # header
    if string_ids_size:
        map_entries.append((0x0001, string_ids_size, string_ids_off))
    if type_ids_size:
        map_entries.append((0x0002, type_ids_size, type_ids_off))
    if proto_ids_size:
        map_entries.append((0x0003, proto_ids_size, proto_ids_off))
    if field_ids_size:
        map_entries.append((0x0004, field_ids_size, field_ids_off))
    if method_ids_size:
        map_entries.append((0x0005, method_ids_size, method_ids_off))
    if class_defs_size:
        map_entries.append((0x0006, class_defs_size, class_defs_off))
    # data items — approximate types used
    # string_data
    map_entries.append((0x2002, len(strings), string_data_offs[0] if string_data_offs else here()))
    # type_list
    if type_list_cache:
        first_tl = min(type_list_cache.values())
        map_entries.append((0x1001, len(type_list_cache), first_tl))
    # code
    # class_data
    if class_data_offs:
        map_entries.append((0x2000, len(class_data_offs), min(class_data_offs)))
    # map_list itself
    map_list_off = here()
    map_entries.append((0x1000, 1, map_list_off))
    map_entries.sort(key=lambda e: e[2])

    data.extend(struct.pack("<I", len(map_entries)))
    for typ, size, off in map_entries:
        data.extend(struct.pack("<HHI I", typ, 0, size, off))

    data_size = len(data)
    while data_size % 4:
        data.append(0)
        data_size += 1

    file_size = data_off + data_size

    # Build ids
    buf = bytearray(file_size)
    # header filled later
    # string_ids
    for i, off in enumerate(string_data_offs):
        struct.pack_into("<I", buf, string_ids_off + 4 * i, off)
    for i, t in enumerate(types):
        struct.pack_into("<I", buf, type_ids_off + 4 * i, s_index[t])
    for i, pr in enumerate(protos):
        off = proto_ids_off + 12 * i
        struct.pack_into("<I", buf, off, s_index[pr[0]])
        struct.pack_into("<I", buf, off + 4, t_index[pr[2]])
        struct.pack_into("<I", buf, off + 8, proto_param_offs[i])
    for i, f in enumerate(fields):
        off = field_ids_off + 8 * i
        struct.pack_into("<HH", buf, off, t_index[f[0]], t_index[f[1]])
        struct.pack_into("<I", buf, off + 4, s_index[f[2]])
    for i, m in enumerate(methods):
        off = method_ids_off + 8 * i
        struct.pack_into("<HH", buf, off, t_index[m[0]], p_index[m[1]])
        struct.pack_into("<I", buf, off + 4, s_index[m[2]])

    # class_defs
    for i, c in enumerate(dex.classes):
        off = class_defs_off + 32 * i
        struct.pack_into("<I", buf, off + 0, t_index[c.name])
        struct.pack_into("<I", buf, off + 4, c.access)
        struct.pack_into("<I", buf, off + 8, t_index[c.super_name])
        struct.pack_into("<I", buf, off + 12, iface_offs_for_class[i])
        struct.pack_into("<I", buf, off + 16, 0xFFFFFFFF)  # source file — use string
        # actually source_file_idx is string index or NO_INDEX
        struct.pack_into("<I", buf, off + 16, s_index.get(c.source, 0xFFFFFFFF))
        struct.pack_into("<I", buf, off + 20, 0)  # annotations
        struct.pack_into("<I", buf, off + 24, class_data_offs[i])
        struct.pack_into("<I", buf, off + 28, 0)  # static values

    buf[data_off : data_off + data_size] = data

    # header
    magic = b"dex\n035\x00"
    buf[0:8] = magic
    # checksum at 8, sha1 at 12, file_size at 32
    struct.pack_into("<I", buf, 32, file_size)
    struct.pack_into("<I", buf, 36, header_size)
    struct.pack_into("<I", buf, 40, 0x12345678)
    struct.pack_into("<I", buf, 44, 0)  # link_size
    struct.pack_into("<I", buf, 48, 0)  # link_off
    struct.pack_into("<I", buf, 52, map_list_off)
    struct.pack_into("<I", buf, 56, string_ids_size)
    struct.pack_into("<I", buf, 60, string_ids_off)
    struct.pack_into("<I", buf, 64, type_ids_size)
    struct.pack_into("<I", buf, 68, type_ids_off)
    struct.pack_into("<I", buf, 72, proto_ids_size)
    struct.pack_into("<I", buf, 76, proto_ids_off)
    struct.pack_into("<I", buf, 80, field_ids_size)
    struct.pack_into("<I", buf, 84, field_ids_off)
    struct.pack_into("<I", buf, 88, method_ids_size)
    struct.pack_into("<I", buf, 92, method_ids_off)
    struct.pack_into("<I", buf, 96, class_defs_size)
    struct.pack_into("<I", buf, 100, class_defs_off)
    struct.pack_into("<I", buf, 104, data_size)
    struct.pack_into("<I", buf, 108, data_off)

    sha = hashlib.sha1(bytes(buf[32:])).digest()
    buf[12:32] = sha
    checksum = zlib.adler32(bytes(buf[12:])) & 0xFFFFFFFF
    struct.pack_into("<I", buf, 8, checksum)
    return bytes(buf[:file_size])


# Opcode formats used by rewriter. width in 16-bit units.
OP_FMT = {
    0x00: ("10x", 1),  # nop
    0x01: ("12x", 1),  # move
    0x02: ("22x", 2),
    0x04: ("12x", 1),  # move-wide
    0x07: ("12x", 1),  # move-object
    0x08: ("22x", 2),
    0x0A: ("11x", 1),  # move-result
    0x0B: ("11x", 1),  # move-result-wide
    0x0C: ("11x", 1),  # move-result-object
    0x0D: ("11x", 1),  # move-exception
    0x0E: ("10x", 1),  # return-void
    0x0F: ("11x", 1),  # return
    0x10: ("11x", 1),  # return-wide
    0x11: ("11x", 1),  # return-object
    0x12: ("11n", 1),  # const/4
    0x13: ("21s", 2),  # const/16
    0x14: ("31i", 3),  # const
    0x15: ("21h", 2),
    0x16: ("21s", 2),  # const-wide/16
    0x17: ("31i", 3),
    0x18: ("51l", 5),
    0x1A: ("21c", 2),  # const-string
    0x1B: ("31c", 3),  # const-string/jumbo
    0x1C: ("21c", 2),  # const-class
    0x1F: ("21c", 2),  # check-cast
    0x20: ("22c", 2),  # instance-of
    0x21: ("12x", 1),  # array-length
    0x22: ("21c", 2),  # new-instance
    0x23: ("22c", 2),  # new-array
    0x24: ("35c", 3),  # filled-new-array
    0x27: ("11x", 1),  # throw
    0x28: ("10t", 1),  # goto
    0x29: ("20t", 2),
    0x2A: ("30t", 3),
    0x31: ("22t", 2),
    0x32: ("22t", 2),  # if-eq
    0x33: ("22t", 2),
    0x34: ("22t", 2),
    0x35: ("22t", 2),
    0x36: ("22t", 2),
    0x37: ("22t", 2),
    0x38: ("21t", 2),  # if-eqz
    0x39: ("21t", 2),
    0x3A: ("21t", 2),
    0x3B: ("21t", 2),
    0x3C: ("21t", 2),
    0x3D: ("21t", 2),
    0x44: ("23x", 2),  # aget
    0x45: ("23x", 2),
    0x46: ("23x", 2),
    0x47: ("23x", 2),
    0x48: ("23x", 2),
    0x49: ("23x", 2),
    0x4A: ("23x", 2),
    0x4B: ("23x", 2),  # aput
    0x4C: ("23x", 2),
    0x4D: ("23x", 2),
    0x4E: ("23x", 2),
    0x4F: ("23x", 2),
    0x50: ("23x", 2),
    0x51: ("23x", 2),
    0x52: ("22c", 2),  # iget
    0x53: ("22c", 2),
    0x54: ("22c", 2),  # iget-object
    0x55: ("22c", 2),
    0x56: ("22c", 2),
    0x57: ("22c", 2),
    0x58: ("22c", 2),
    0x59: ("22c", 2),  # iput
    0x5A: ("22c", 2),
    0x5B: ("22c", 2),  # iput-object
    0x5C: ("22c", 2),
    0x5D: ("22c", 2),
    0x5E: ("22c", 2),
    0x5F: ("22c", 2),
    0x60: ("21c", 2),  # sget
    0x61: ("21c", 2),
    0x62: ("21c", 2),  # sget-object
    0x63: ("21c", 2),
    0x64: ("21c", 2),
    0x65: ("21c", 2),
    0x66: ("21c", 2),
    0x67: ("21c", 2),  # sput
    0x68: ("21c", 2),
    0x69: ("21c", 2),
    0x6A: ("21c", 2),
    0x6B: ("21c", 2),
    0x6C: ("21c", 2),
    0x6D: ("21c", 2),
    0x6E: ("35c", 3),  # invoke-virtual
    0x6F: ("35c", 3),
    0x70: ("35c", 3),
    0x71: ("35c", 3),
    0x72: ("35c", 3),
    0x74: ("3rc", 3),
    0x75: ("3rc", 3),
    0x76: ("3rc", 3),
    0x77: ("3rc", 3),
    0x78: ("3rc", 3),
    0x7B: ("12x", 1),
    0x81: ("12x", 1),  # int-to-long
    0x84: ("12x", 1),
    0x8A: ("12x", 1),
    0x90: ("23x", 2),  # add-int
    0x91: ("23x", 2),
    0x92: ("23x", 2),
    0x93: ("23x", 2),
    0x94: ("23x", 2),
    0x95: ("23x", 2),
    0x96: ("23x", 2),
    0x97: ("23x", 2),
    0x98: ("23x", 2),
    0x99: ("23x", 2),
    0x9A: ("23x", 2),
    0x9B: ("23x", 2),
    0xB0: ("12x", 1),  # add-int/2addr
    0xD8: ("22s", 2),  # add-int/lit16
    0xD9: ("22s", 2),
    0xDC: ("22b", 2),  # add-int/lit8
    0xDD: ("22b", 2),
    0xDE: ("22b", 2),
    0xDF: ("22b", 2),
    0xE0: ("22b", 2),
    0xE1: ("22b", 2),
    0xE2: ("22b", 2),
}

OP_INDEX_KIND = {
    0x1A: "string",
    0x1B: "string",
    0x1C: "type",
    0x1F: "type",
    0x20: "type",
    0x22: "type",
    0x23: "type",
    0x24: "type",
    0x52: "field",
    0x53: "field",
    0x54: "field",
    0x55: "field",
    0x56: "field",
    0x57: "field",
    0x58: "field",
    0x59: "field",
    0x5A: "field",
    0x5B: "field",
    0x5C: "field",
    0x5D: "field",
    0x5E: "field",
    0x5F: "field",
    0x60: "field",
    0x61: "field",
    0x62: "field",
    0x63: "field",
    0x64: "field",
    0x65: "field",
    0x66: "field",
    0x67: "field",
    0x68: "field",
    0x69: "field",
    0x6A: "field",
    0x6B: "field",
    0x6C: "field",
    0x6D: "field",
    0x6E: "method",
    0x6F: "method",
    0x70: "method",
    0x71: "method",
    0x72: "method",
    0x74: "method",
    0x75: "method",
    0x76: "method",
    0x77: "method",
    0x78: "method",
}


class Asm:
    """Tiny Dalvik assembler for one method."""

    def __init__(self, pool: DexPool, n_ins: int, n_locals: int = 14):
        self.p = pool
        self.n_ins = n_ins
        self.n_locals = n_locals
        self.registers = n_locals + n_ins
        self.insns: List[int] = []
        self.outs = 0
        self._tmp = 0

    @property
    def this(self) -> int:
        return self.n_locals  # first in-reg

    def p_reg(self, i: int) -> int:
        return self.n_locals + i

    def emit(self, *units: int) -> None:
        self.insns.extend(units)

    def nop(self):
        self.emit(0x0000)

    def ret_void(self):
        self.emit(0x0E00)

    def ret_obj(self, v: int):
        self.emit(op_unit(0x11, v))

    def ret_int(self, v: int):
        self.emit(op_unit(0x0F, v))

    def move_obj(self, dst, src):
        self.emit(((dst & 0xF) << 12) | ((src & 0xF) << 8) | 0x07)

    def move(self, dst, src):
        self.emit(((dst & 0xF) << 12) | ((src & 0xF) << 8) | 0x01)

    def move_result_obj(self, v):
        self.emit(op_unit(0x0C, v))

    def move_result(self, v):
        self.emit(op_unit(0x0A, v))

    def const4(self, v, n):
        self.emit(((n & 0xF) << 12) | ((v & 0xF) << 8) | 0x12)

    def const16(self, v, n):
        self.emit(op_unit(0x13, v), n & 0xFFFF)

    def const32(self, v, n):
        self.emit(op_unit(0x14, v), n & 0xFFFF, (n >> 16) & 0xFFFF)

    def const_string(self, v, s: str):
        idx = self.p.string(s)
        self.emit(op_unit(0x1A, v), idx)

    def const_class(self, v, t: str):
        idx = self.p.typ(t)
        self.emit(op_unit(0x1C, v), idx)

    def check_cast(self, v, t: str):
        idx = self.p.typ(t)
        self.emit(op_unit(0x1F, v), idx)

    def new_instance(self, v, t: str):
        idx = self.p.typ(t)
        self.emit(op_unit(0x22, v), idx)

    def iget_obj(self, dst, obj, cls, typ, name):
        idx = self.p.field(cls, typ, name)
        self.emit(op_unit(0x54, dst) | ((obj & 0xF) << 12), idx)

    def iput_obj(self, src, obj, cls, typ, name):
        idx = self.p.field(cls, typ, name)
        self.emit(op_unit(0x5B, src) | ((obj & 0xF) << 12), idx)

    def iget(self, dst, obj, cls, typ, name):
        idx = self.p.field(cls, typ, name)
        self.emit(op_unit(0x52, dst) | ((obj & 0xF) << 12), idx)

    def iput(self, src, obj, cls, typ, name):
        idx = self.p.field(cls, typ, name)
        self.emit(op_unit(0x59, src) | ((obj & 0xF) << 12), idx)

    def sget_obj(self, dst, cls, typ, name):
        idx = self.p.field(cls, typ, name)
        self.emit(op_unit(0x62, dst), idx)

    def sput_obj(self, src, cls, typ, name):
        idx = self.p.field(cls, typ, name)
        self.emit(op_unit(0x69, src), idx)

    def _invoke(self, op, regs: List[int], cls, name, ret, params):
        idx = self.p.method(cls, name, ret, params)
        n = len(regs)
        self.outs = max(self.outs, n)
        g = regs[4] if n > 4 else 0
        c = regs[0] if n > 0 else 0
        d = regs[1] if n > 1 else 0
        e = regs[2] if n > 2 else 0
        f = regs[3] if n > 3 else 0
        u0 = ((n & 0xF) << 12) | ((g & 0xF) << 8) | op
        u2 = ((f & 0xF) << 12) | ((e & 0xF) << 8) | ((d & 0xF) << 4) | (c & 0xF)
        self.emit(u0, idx, u2)

    def invoke_virtual(self, regs, cls, name, ret, params=()):
        self._invoke(0x6E, regs, cls, name, ret, params)

    def invoke_super(self, regs, cls, name, ret, params=()):
        self._invoke(0x6F, regs, cls, name, ret, params)

    def invoke_direct(self, regs, cls, name, ret, params=()):
        self._invoke(0x70, regs, cls, name, ret, params)

    def invoke_static(self, regs, cls, name, ret, params=()):
        self._invoke(0x71, regs, cls, name, ret, params)

    def invoke_interface(self, regs, cls, name, ret, params=()):
        self._invoke(0x72, regs, cls, name, ret, params)

    def goto(self, rel: int):
        self.emit(op_unit(0x28, rel & 0xFF))

    def if_eqz(self, v, rel: int):
        self.emit(op_unit(0x38, v), rel & 0xFFFF)

    def if_nez(self, v, rel: int):
        self.emit(op_unit(0x39, v), rel & 0xFFFF)

    def add_int_lit8(self, dst, src, lit):
        self.emit(op_unit(0xDC, dst) | ((src & 0xFF) << 8), lit & 0xFF)

    def new_array(self, dst, size_reg, ty: str):
        idx = self.p.typ(ty)
        self.emit(op_unit(0x23, dst) | ((size_reg & 0xF) << 12), idx)

    def aget_obj(self, dst, arr, idx):
        self.emit(op_unit(0x46, dst), (idx << 8) | arr)

    def aput_obj(self, src, arr, idx):
        self.emit(op_unit(0x4D, src), (idx << 8) | arr)

    def finish(self) -> CodeItem:
        return CodeItem(self.registers, self.n_ins, self.outs, self.insns)
