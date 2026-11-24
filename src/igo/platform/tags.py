"""A site's naming grammar: historian names, functional locations, equipment tags in text, P&ID text.

Everything a site names differently lives in config/sites/<site>.yml. Code here only applies it, and refuses a
string it cannot parse rather than guessing.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from igo.config import site as load_site

STANDARD_TAG = re.compile(r"\b(?P<code>[PKEVF])-?(?P<num>\d{4})(?P<suf>[AB])?\b")
WORDS = {
    "pump": "P",
    "pumpe": "P",
    "compressor": "K",
    "verdichter": "K",
    "exchanger": "E",
    "wärmetauscher": "E",
    "vessel": "V",
    "behälter": "V",
    "fan": "F",
    "lüfter": "F",
}
WORD_TAG = re.compile(r"^(?P<word>[^\W\d_]+)\s+(?P<num>\d{4})\s?(?P<suf>[AB])?$", re.IGNORECASE)
UNIT_TYPE = {"bar": "PT", "degC": "TT", "m3/h": "FT", "mm/s": "VT", "A": "IT", "%": "LT"}


@dataclass(frozen=True)
class EquipmentKey:
    code: str
    number: str  # 2103A

    @property
    def unit(self) -> int:
        return int(self.number[:2])

    def __str__(self) -> str:
        return f"{self.code}-{self.number}"


@dataclass(frozen=True)
class InstrumentKey:
    unit: int
    mtype: str
    loop: str


class Grammar:
    def __init__(self, site: str = "plant"):
        cfg = load_site(site)
        self.cfg = cfg
        self.name_patterns = [re.compile(p) for p in cfg["historian"]["name_patterns"]]
        self.floc = re.compile(cfg["sap_pm"]["floc_pattern"])
        self.codes: dict[str, str] = cfg["equipment_codes"]
        self.fit_map: dict[str, list[str]] = cfg["measurement_fits"]
        self.ranges: dict[str, list[float]] = cfg["typical_range"]
        self.declared: dict[str, str] = cfg["historian"]["units"]

    def parse_name(self, name: str) -> InstrumentKey | None:
        for p in self.name_patterns:
            m = p.match(name)
            if m:
                return InstrumentKey(int(m["unit"]), m["type"], m["loop"])
        return None

    def parse_floc(self, floc: str) -> EquipmentKey | None:
        m = self.floc.match(floc)
        if not m or m["cls"] not in self.codes:
            return None
        return EquipmentKey(m["cls"], m["number"])

    def tags_in(self, text: str) -> list[EquipmentKey]:
        """Equipment tags written in the plant's standard form (P-2103A, P2103A)."""
        return [EquipmentKey(m["code"], m["num"] + (m["suf"] or "")) for m in STANDARD_TAG.finditer(text)]

    def normalize_mention(self, quote: str) -> EquipmentKey | None:
        """A model's quote, in any of the forms people write, turned into a tag; None if it does not parse."""
        q = quote.strip()
        tags = self.tags_in(q)
        if len(tags) == 1 and STANDARD_TAG.fullmatch(q.replace(" ", "")):
            return tags[0]
        m = WORD_TAG.match(q)
        if m and m["word"].lower() in WORDS:
            return EquipmentKey(WORDS[m["word"].lower()], m["num"] + (m["suf"] or "").upper())
        return None

    def mtype(self, name: str, unit: str) -> str | None:
        k = self.parse_name(name)
        return k.mtype if k else UNIT_TYPE.get(unit)

    def fits(self, code: str, mtype: str | None) -> bool:
        return mtype is None or mtype in self.fit_map[self.codes[code]]

    @staticmethod
    def repairs(text: str) -> list[str]:
        """OCR repairs for P&ID text: letters read in place of digits, a dropped dash. Only the text itself and
        its repaired forms are returned; the caller keeps one only if it parses and names something that exists."""
        out = [text]
        fixed = re.sub(r"(?<=\d)O|O(?=\d)", "0", text)
        fixed = re.sub(r"(?<=\d)I|I(?=\d)", "1", fixed)
        if fixed != text:
            out.append(fixed)
        for t in list(out):
            m = re.match(r"^([A-Z]{1,2})(\d.*)$", t)
            if m:
                out.append(f"{m.group(1)}-{m.group(2)}")
        return out

    def pid_instrument(self, text: str) -> tuple[str, str] | None:
        for t in self.repairs(text):
            m = re.fullmatch(r"(?P<type>[A-Z]{2})-(?P<loop>\d{4}[AB]?)", t)
            if m:
                return m["type"], m["loop"]
        return None

    def pid_equipment(self, text: str) -> EquipmentKey | None:
        for t in self.repairs(text):
            m = re.fullmatch(r"(?P<code>[PKEVF])-(?P<num>\d{4}[AB]?)", t)
            if m:
                return EquipmentKey(m["code"], m["num"])
        return None
