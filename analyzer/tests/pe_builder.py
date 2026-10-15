"""Fabrique de PE SYNTHÉTIQUES pour les tests : aucun échantillon malveillant réel dans le dépôt."""

from __future__ import annotations

import struct
from dataclasses import dataclass

CODE, DATA, RDATA = 0x60000020, 0xC0000040, 0x40000040
RWX = 0xE0000020
FILE_ALIGN, SECT_ALIGN = 0x200, 0x1000


@dataclass
class Sec:
    name: bytes
    data: bytes
    flags: int = CODE
    virtual_size: int | None = None


def _align(n: int, a: int) -> int:
    return (n + a - 1) // a * a


def make_pe(
    sections: list[Sec],
    entry_rva: int | None = 0x1000,
    timestamp: int = 1_700_000_000,
    imports: dict[str, list[str]] | None = None,
    overlay: bytes = b"",
    signed: bool = False,
) -> bytes:
    sections = list(sections)
    rva = SECT_ALIGN
    for s in sections:
        rva += _align(s.virtual_size or max(len(s.data), 1), SECT_ALIGN)
    import_dir = (0, 0)
    if imports:
        idata, size = _import_section(imports, rva)
        sections.append(Sec(b".idata", idata, DATA))
        import_dir = (rva, size)
    headers_size = 0x200
    offsets, vas = [], []
    off, va = headers_size, SECT_ALIGN
    for s in sections:
        offsets.append(off)
        vas.append(va)
        off += _align(len(s.data), FILE_ALIGN) if s.data else 0
        va += _align(s.virtual_size or max(len(s.data), 1), SECT_ALIGN)
    image_size = va
    sig_off = 0
    body = b"".join(
        s.data.ljust(_align(len(s.data), FILE_ALIGN), b"\0") if s.data else b"" for s in sections
    )
    sig = b""
    if signed:
        sig_off = headers_size + len(body) + len(overlay)
        sig = b"\0" * 64
    dirs = [(0, 0)] * 16
    dirs[1] = import_dir
    dirs[4] = (sig_off, 64) if signed else (0, 0)
    opt = struct.pack(
        "<HBBIIIIIQIIHHHHHHIIIIHHQQQQII",
        0x20B,
        14,
        0,
        0x200,
        0x200,
        0,
        entry_rva or 0,
        SECT_ALIGN,
        0x140000000,
        SECT_ALIGN,
        FILE_ALIGN,
        6,
        0,
        0,
        0,
        6,
        0,
        0,
        image_size,
        headers_size,
        0,
        3,
        0x8160,
        0x100000,
        0x1000,
        0x100000,
        0x1000,
        0,
        16,
    )
    opt = opt.replace(b"", b"")
    opt += b"".join(struct.pack("<II", a, b) for a, b in dirs)
    coff = struct.pack("<HHIIIHH", 0x8664, len(sections), timestamp, 0, 0, len(opt), 0x22)
    table = b""
    for s, o, v in zip(sections, offsets, vas, strict=True):
        table += struct.pack(
            "<8sIIIIIIHHI",
            s.name[:8],
            s.virtual_size or max(len(s.data), 1),
            v,
            _align(len(s.data), FILE_ALIGN) if s.data else 0,
            o if s.data else 0,
            0,
            0,
            0,
            0,
            s.flags,
        )
    dos = b"MZ" + b"\0" * 58 + struct.pack("<I", 0x80)
    head = dos.ljust(0x80, b"\0") + b"PE\0\0" + coff + opt + table
    return head.ljust(headers_size, b"\0") + body + overlay + sig


def _import_section(imports: dict[str, list[str]], base_rva: int) -> tuple[bytes, int]:
    n_dll = len(imports)
    desc_size = (n_dll + 1) * 20
    blob = bytearray(desc_size)
    descs = bytearray()
    cursor = desc_size
    for dll, funcs in imports.items():
        names = bytearray()
        name_rvas = []
        for f in funcs:
            name_rvas.append(len(names))
            names += struct.pack("<H", 0) + f.encode() + b"\0"
            if len(names) % 2:
                names += b"\0"
        thunks_size = (len(funcs) + 1) * 8
        int_off = cursor
        names_off = int_off + thunks_size
        dll_off = names_off + len(names)
        thunks = (
            b"".join(struct.pack("<Q", base_rva + names_off + r) for r in name_rvas) + b"\0" * 8
        )
        blob += thunks + names + dll.encode() + b"\0"
        cursor = len(blob)
        descs += struct.pack(
            "<IIIII", base_rva + int_off, 0, 0, base_rva + dll_off, base_rva + int_off
        )
    blob[: len(descs)] = descs
    return bytes(blob), desc_size
