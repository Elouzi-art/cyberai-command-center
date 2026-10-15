"""Analyse statique d'un fichier. AUCUNE exécution, aucun réseau, aucun verdict.

Tout ce qui provient du fichier (noms de sections, de DLL...) est une donnée hostile : il est
réduit à de l'ASCII imprimable et tronqué avant d'entrer dans le rapport (R6).
Chaque constat est étiqueté `tool_data` : un fait mesuré ou une règle déterministe, jamais une
conclusion. Les hypothèses viendront d'une étape distincte, étiquetée comme telle (R4).
"""

from __future__ import annotations

import hashlib
import math
import time
from collections import Counter
from datetime import UTC, datetime
from typing import Any

import pefile

from cyberai_analyzer import __version__

SECTION_CAP = 96
DLL_CAP = 64
IMPORT_SCAN_CAP = 5000
MAX_ITEMS = 200
HIGH_ENTROPY = 7.0
STANDARD_SECTIONS = {
    ".text",
    ".data",
    ".rdata",
    ".rsrc",
    ".reloc",
    ".idata",
    ".edata",
    ".pdata",
    ".bss",
    ".tls",
    ".crt",
    ".didat",
    ".gfids",
    ".xdata",
}
_EXEC, _WRITE, _READ = 0x20000000, 0x80000000, 0x40000000
_DYNAMIC = {"loadlibrarya", "loadlibraryw", "loadlibraryexa", "loadlibraryexw", "getprocaddress"}


def clean(value: object, limit: int = 64) -> str:
    """ASCII imprimable uniquement (le reste devient « ? ») : jamais une instruction."""
    raw = value.decode("latin-1") if isinstance(value, bytes) else str(value)
    out = "".join(c if 0x20 <= ord(c) <= 0x7E else "?" for c in raw)
    return out[:limit]


def entropy(data: bytes) -> float:
    if not data:
        return 0.0
    n = len(data)
    return round(-sum(c / n * math.log2(c / n) for c in Counter(data).values()), 2)


def file_type(data: bytes) -> str:
    if data[:2] == b"MZ":
        return "PE"
    if data[:4] == b"\x7fELF":
        return "ELF"
    if data[:4] == b"PK\x03\x04":
        return "ZIP"
    if data[:5] == b"%PDF-":
        return "PDF"
    if data[:4] == b"\xd0\xcf\x11\xe0":
        return "OLE"
    return "inconnu"


def _item(
    statement: str, evidence: list[str] | None = None, source: str = "pe-rules"
) -> dict[str, Any]:
    return {
        "provenance": "tool_data",
        "statement": statement,
        "confidence": None,
        "evidence": [clean(e, 64) for e in (evidence or [])][:10],
        "source": source,
    }


def _name(table: dict[str, int], value: int) -> str:
    for key, val in table.items():
        if val == value:
            return clean(key, 32)
    return f"inconnu (0x{value:x})"


def _analyze_pe(data: bytes, items: list[dict[str, Any]]) -> dict[str, Any] | None:
    try:
        pe = pefile.PE(data=data, fast_load=True)
        pe.parse_data_directories(
            directories=[pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_IMPORT"]]
        )
    except pefile.PEFormatError:
        return None
    try:
        oh, fh = pe.OPTIONAL_HEADER, pe.FILE_HEADER
        machine = _name(pefile.MACHINE_TYPE, fh.Machine)
        subsystem = _name(pefile.SUBSYSTEM_TYPE, oh.Subsystem)
        raw_sections = list(pe.sections)[:SECTION_CAP]
        sections: list[dict[str, Any]] = []
        for s in raw_sections:
            flags = [
                f
                for f, bit in (("read", _READ), ("write", _WRITE), ("exec", _EXEC))
                if s.Characteristics & bit
            ]
            sections.append(
                {
                    "name": clean(s.Name.rstrip(b"\x00"), 16),
                    "virtual_size": int(s.Misc_VirtualSize),
                    "raw_size": int(s.SizeOfRawData),
                    "entropy": min(8.0, round(float(s.get_entropy()), 2)),
                    "flags": flags,
                }
            )
        ts = int(fh.TimeDateStamp)
        timestamp = datetime.fromtimestamp(ts, UTC).isoformat(timespec="seconds") if ts else None

        dlls: list[str] = []
        functions: list[str] = []
        scanned = 0
        for entry in getattr(pe, "DIRECTORY_ENTRY_IMPORT", [])[: DLL_CAP * 8]:
            if len(dlls) < DLL_CAP:
                dlls.append(clean(entry.dll, 64).lower())
            for imp in entry.imports:
                scanned += 1
                if scanned > IMPORT_SCAN_CAP:
                    break
                if imp.name:
                    functions.append(clean(imp.name, 64).lower())

        sec_dir = oh.DATA_DIRECTORY[4] if len(oh.DATA_DIRECTORY) > 4 else None
        sig_size = int(sec_dir.Size) if sec_dir is not None else 0
        overlay_at = pe.get_overlay_data_start_offset()
        overlay = max(0, len(data) - overlay_at - sig_size) if overlay_at else 0

        ep = int(oh.AddressOfEntryPoint)
        ep_section: dict[str, Any] | None = None
        for raw, s in zip(raw_sections, sections, strict=True):
            span = max(raw.Misc_VirtualSize, raw.SizeOfRawData)
            if raw.VirtualAddress <= ep < raw.VirtualAddress + span:
                ep_section = s

        items.append(
            _item(
                f"Machine {machine}, sous-système {subsystem}, {len(sections)} section(s).",
                source="pefile",
            )
        )
        items.append(
            _item(
                "Horodatage de compilation : " + (timestamp or "absent (valeur 0)") + ".",
                source="pefile",
            )
        )
        if ts == 0:
            items.append(_item("Règle : horodatage de compilation nul.", ["header:timestamp"]))
        elif ts > time.time() + 86400:
            items.append(
                _item("Règle : horodatage de compilation dans le futur.", ["header:timestamp"])
            )
        for s in sections:
            ev = [f"section:{s['name']}"]
            if s["entropy"] >= HIGH_ENTROPY:
                items.append(
                    _item(f"Règle : entropie élevée ({s['entropy']} ≥ {HIGH_ENTROPY}).", ev)
                )
            if "write" in s["flags"] and "exec" in s["flags"]:
                items.append(_item("Règle : section à la fois inscriptible et exécutable.", ev))
            if s["raw_size"] == 0 and s["virtual_size"] >= 0x1000:
                items.append(
                    _item("Règle : section vide dans le fichier mais volumineuse en mémoire.", ev)
                )
            if s["name"].lower() not in STANDARD_SECTIONS:
                items.append(_item("Règle : nom de section inhabituel.", ev))
        if ep_section is None:
            items.append(
                _item("Règle : point d'entrée hors de toute section.", ["header:entry_point"])
            )
        else:
            ev = [f"section:{ep_section['name']}"]
            if "exec" not in ep_section["flags"]:
                items.append(_item("Règle : point d'entrée dans une section non exécutable.", ev))
            if len(sections) > 1 and ep_section is sections[-1]:
                items.append(_item("Règle : point d'entrée dans la dernière section.", ev))
        if dlls:
            items.append(
                _item(
                    f"{len(dlls)} DLL importée(s), {len(functions)} fonction(s) nommée(s).",
                    source="pefile",
                )
            )
        if len(functions) <= 5 and _DYNAMIC & set(functions):
            items.append(
                _item(
                    "Règle : très peu d'imports, avec résolution dynamique d'API.",
                    ["imports:dynamic"],
                )
            )
        if overlay >= 100_000 and overlay * 4 >= len(data):
            items.append(_item(f"Règle : overlay volumineux ({overlay} octets).", ["overlay"]))
        if sig_size:
            items.append(
                _item(
                    "Signature Authenticode présente (non vérifiée).",
                    ["header:security"],
                    source="pefile",
                )
            )
        return {
            "machine": machine,
            "subsystem": subsystem,
            "timestamp": timestamp,
            "sections": sections,
            "imports_dlls": dlls,
            "imports_count": len(functions),
            "overlay_size": overlay,
            "signed": bool(sig_size),
            "entry_section": ep_section["name"] if ep_section else None,
        }
    finally:
        pe.close()


def analyze(data: bytes, subject: str = "sample") -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    ftype = file_type(data)
    total_entropy = entropy(data)
    pe_info: dict[str, Any] | None = None
    if ftype == "PE":
        pe_info = _analyze_pe(data, items)
        if pe_info is None:
            ftype = "PE (invalide)"
            items.append(
                _item(
                    "En-tête PE invalide ou tronqué : analyse structurelle impossible.",
                    ["header:pe"],
                    source="pefile",
                )
            )
    elif ftype != "inconnu":
        items.append(
            _item(f"Type {ftype} détecté : analyse détaillée non implémentée.", source="magic")
        )
    items.insert(0, _item(f"Entropie globale : {total_entropy} (sur 8).", source="entropy"))
    report: dict[str, Any] = {
        "subject": clean(subject, 128),
        "agent": "malware",
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "needs_human_review": True,
        "sample": {
            "sha256": hashlib.sha256(data).hexdigest(),
            "md5": hashlib.md5(data, usedforsecurity=False).hexdigest(),
            "sha1": hashlib.sha1(data, usedforsecurity=False).hexdigest(),
            "size": len(data),
            "file_type": ftype,
            "entropy": total_entropy,
        },
        "items": items[:MAX_ITEMS],
        "tool_versions": {"cyberai-analyzer": __version__, "pefile": clean(pefile.__version__, 32)},
    }
    if pe_info is not None:
        report["pe"] = pe_info
    return report
