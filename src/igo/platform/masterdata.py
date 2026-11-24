"""Equipment master data from SAP PM: one canonical machine per physical asset.

A record's tag comes from its functional location when that parses; otherwise from its description, read by the
model and checked by code. Records that share a tag and class are one machine: merged without a person when both
functional locations parse to the same tag, and sent to the engineer when one of them was read from text.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from igo.platform.tags import EquipmentKey, Grammar
from igo.sources import EquipmentRecord


class Reader(Protocol):
    def mention(self, text: str, key: str) -> dict: ...


class Reviewer(Protocol):
    def same_machine(self, a: str, b: str) -> bool: ...


@dataclass
class Machine:
    canon: str  # sap id of the record kept
    key: EquipmentKey | None
    cls: str
    records: list[str] = field(default_factory=list)


@dataclass
class MasterData:
    machines: dict[str, Machine]
    record_to_canon: dict[str, str]
    by_key: dict[EquipmentKey, str]
    merges: list[tuple[str, str, str]]  # (kept, merged, how: auto|review)
    review_rejected: int = 0

    def canon(self, sap_id: str) -> str | None:
        return self.record_to_canon.get(sap_id)

    def unit_of(self, canon: str) -> int | None:
        k = self.machines[canon].key
        return k.unit if k else None


def record_key(r: EquipmentRecord, g: Grammar, reader: Reader | None) -> tuple[EquipmentKey | None, str]:
    k = g.parse_floc(r.floc)
    if k:
        return k, "floc"
    tags = g.tags_in(r.description)
    if len(tags) == 1:
        return tags[0], "description"
    if reader is not None:
        got = reader.mention(r.description, "record:" + r.sap_id)
        q = got.get("quote")
        if q and q in r.description:
            k2 = g.normalize_mention(q)
            if k2:
                return k2, "model"
    return None, "none"


def build(
    records: list[EquipmentRecord],
    g: Grammar,
    reader: Reader | None,
    reviewer: Reviewer | None,
    dedupe: bool,
) -> MasterData:
    machines: dict[str, Machine] = {}
    record_to_canon: dict[str, str] = {}
    by_key: dict[EquipmentKey, str] = {}
    merges: list[tuple[str, str, str]] = []
    rejected = 0
    how_found: dict[str, str] = {}
    for r in records:
        key, how = record_key(r, g, reader)
        how_found[r.sap_id] = how
        if dedupe and key is not None and key in by_key:
            kept = by_key[key]
            m = machines[kept]
            same_class = m.cls == r.cls_text
            if same_class and how == "floc" and how_found[kept] == "floc":
                merges.append((kept, r.sap_id, "auto"))
            elif same_class and reviewer is not None and reviewer.same_machine(kept, r.sap_id):
                merges.append((kept, r.sap_id, "review"))
            else:
                rejected += 1
                machines[r.sap_id] = Machine(r.sap_id, None, r.cls_text, [r.sap_id])
                record_to_canon[r.sap_id] = r.sap_id
                continue
            m.records.append(r.sap_id)
            record_to_canon[r.sap_id] = kept
            continue
        machines[r.sap_id] = Machine(r.sap_id, key, r.cls_text, [r.sap_id])
        record_to_canon[r.sap_id] = r.sap_id
        if key is not None and key not in by_key:
            by_key[key] = r.sap_id
    return MasterData(machines, record_to_canon, by_key, merges, rejected)
