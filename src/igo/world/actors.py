"""The people and the model the designs share: a simulated language model and a plant engineer who reviews.

Both draw their luck from (seed, purpose, key), so every design meets the same misreads and the same review slips.
"""

from __future__ import annotations

import re
import zlib

import numpy as np

from igo.config import load
from igo.world.plant import Plant

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
ANY_MENTION = re.compile(
    r"\b(?:(?P<code>[PKEVF])-?|(?P<word>pump|pumpe|compressor|verdichter|exchanger|wärmetauscher|vessel|"
    r"behälter|fan|lüfter)\s+)(?P<num>\d{4})(?:\s?(?P<suf>[AB]))?\b",
    re.IGNORECASE,
)
INTENTS = {
    "sensors": "which sensors",
    "last_corrective": "last corrective",
    "vibration_trend": "vibration",
    "most_corrective": "most corrective",
}


def _rng(seed: int, purpose: str, key: str) -> np.random.Generator:
    return np.random.default_rng([seed, zlib.crc32(purpose.encode()), zlib.crc32(key.encode())])


class SimReader:
    """A language model that reads text well, but not perfectly: it sometimes flips a suffix, swaps two digits or
    invents a tag that is not in the text. It never sees the truth; its mistakes come from its own luck."""

    def __init__(self, seed: int, misread: float = 0.04, invent: float = 0.03, miss: float = 0.03):
        self.seed, self.misread, self.invent, self.miss = seed, misread, invent, miss
        self.calls = 0

    def _corrupt(self, quote: str, r: np.random.Generator) -> str:
        m = re.search(r"(\d{4})(\s?)([AB])?$", quote)
        if not m:
            return quote
        num, sp, suf = m.group(1), m.group(2), m.group(3)
        if suf:
            return quote[: m.start()] + num + sp + ("B" if suf == "A" else "A")
        return quote[: m.start()] + num[:2] + num[3] + num[2]

    def mention(self, text: str, key: str) -> dict:
        """Find the equipment a text talks about. Returns the words it relies on, as a quote."""
        self.calls += 1
        r = _rng(self.seed, "mention", key)
        found = ANY_MENTION.search(text)
        x = r.random()
        if found is None:
            if x < self.invent:
                return {"quote": f"P-{int(r.integers(20, 60))}{int(r.integers(1, 15)):02d}A", "confidence": 0.6}
            return {"quote": None, "confidence": 0.9}
        quote = found.group(0)
        if x < self.miss:
            return {"quote": None, "confidence": 0.5}
        if x < self.miss + self.misread:
            return {"quote": self._corrupt(quote, r), "confidence": 0.85}
        return {"quote": quote, "confidence": 0.95}

    def link(self, name: str, description: str, records: list[tuple[str, str, str]], key: str) -> str | None:
        """Model alone: pick the master record a series belongs to from its name and description."""
        self.calls += 1
        r = _rng(self.seed, "link", key)
        if r.random() < self.invent:
            return f"1009{int(r.integers(1000, 9999))}"
        m = re.match(r"^U?(\d{2})[_-]?([A-Z]{2})[_-]?(\d{4}[AB]?)", name)
        unit = m.group(1) if m else None
        loop = m.group(3) if m else None
        for sap_id, floc, _desc in records:
            if loop and floc.endswith(f"-{loop}"):
                return sap_id
        mm = ANY_MENTION.search(description)
        if mm:
            num = mm.group("num") + (mm.group("suf") or "").upper()
            hits = [s for s, f, _ in records if f.endswith(f"-{num}")]
            if hits and r.random() > self.misread:
                return hits[0]
        pool = [s for s, f, _ in records if unit and f"-{unit}-" in f] or [s for s, _, _ in records]
        return str(r.choice(pool)) if pool else None

    def read_question(self, text: str, key: str) -> dict:
        """Turn a question into an intent and the words that name the equipment or unit."""
        self.calls += 1
        r = _rng(self.seed, "question", key)
        low = text.lower()
        intent = next((k for k, v in INTENTS.items() if v in low), "sensors")
        if r.random() < 0.03:
            intent = str(r.choice([k for k in INTENTS if k != intent]))
        unit_m = re.search(r"unit (\d{2})", text)
        out: dict = {"intent": intent, "unit": int(unit_m.group(1)) if unit_m else None, "confidence": 0.9}
        m = self.mention(text, "q:" + key)
        out["entity"] = m["quote"]
        return out


class Engineer:
    """The customer's plant engineer. Knows the plant, answers review items, and sometimes slips."""

    def __init__(self, plant: Plant, error: float = 0.02):
        self.p, self.error = plant, error
        self.minutes = 0.0
        self.items: dict[str, int] = {}
        self.cost = load("platform")["review_minutes"]
        self.manual = load("platform")["manual_minutes"]

    def _spend(self, kind: str, minutes: float) -> None:
        self.minutes += minutes
        self.items[kind] = self.items.get(kind, 0) + 1

    def _slip(self, kind: str, key: str) -> bool:
        return bool(_rng(self.p.seed, "engineer:" + kind, key).random() < self.error)

    def link(self, ts_id: str, candidates: list[str], by_hand: bool = False) -> str | None:
        """The master record the series belongs to; by hand when no candidate list helps."""
        self._spend("link", self.manual["link"] if by_hand or not candidates else self.cost["link"])
        sid = self.p.ts_sensor[ts_id]
        eid = self.p.sensors[sid].eid
        truth = self.p.equipment[eid].sap_ids[0]
        if self._slip("link", ts_id):
            unit = self.p.equipment[eid].unit
            others = [e.sap_ids[0] for e in self.p.equipment.values() if e.unit == unit and e.eid != eid]
            pool = [c for c in candidates if c != truth] or others
            return str(_rng(self.p.seed, "engineer:pick", ts_id).choice(pool))
        return truth

    def same_machine(self, a: str, b: str) -> bool:
        self._spend("duplicate", self.cost["duplicate"])
        truth = self.p.sap_owner.get(a) == self.p.sap_owner.get(b)
        return (not truth) if self._slip("duplicate", a + b) else truth

    def same_sensor(self, old: str, new: str) -> bool:
        self._spend("rename", self.cost["rename"])
        truth = self.p.ts_sensor.get(old) == self.p.ts_sensor.get(new)
        return (not truth) if self._slip("rename", old + new) else truth

    def unit_factor(self, ts_id: str) -> float:
        self._spend("unit", self.cost["unit"])
        return self.p.ts_factor[ts_id]

    def work_order(self, wo_id: str, proposed: str) -> str:
        """Confirms where a work order belongs; answers with the primary record of the right machine."""
        self._spend("work_order", self.cost["work_order"])
        eid = self.p.wo_true[wo_id]
        truth = self.p.equipment[eid].sap_ids[0]
        if self._slip("work_order", wo_id):
            return proposed if proposed != truth else self.p.equipment[eid].sap_ids[-1]
        return truth

    def answer_question(self) -> None:
        self._spend("question", self.manual["question"])
