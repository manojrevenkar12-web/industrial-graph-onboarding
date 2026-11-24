"""Data quality checks that change what the graph says: renamed tags, wrong units, work orders on the wrong machine.

Each check either fixes without a person (when the evidence is unambiguous), sends the item to the engineer with
its evidence, or leaves the data as it was. Nothing is guessed.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import numpy as np

from igo.platform.masterdata import MasterData
from igo.platform.tags import Grammar
from igo.sources import Series, WorkOrder


class Reader(Protocol):
    def mention(self, text: str, key: str) -> dict: ...


class Reviewer(Protocol):
    def same_sensor(self, old: str, new: str) -> bool: ...
    def work_order(self, wo_id: str, proposed: str) -> str: ...


def first_last(v: np.ndarray) -> tuple[int | None, int | None]:
    ok = np.flatnonzero(~np.isnan(v))
    return (int(ok[0]), int(ok[-1])) if len(ok) else (None, None)


@dataclass
class RenameFinding:
    old: str
    new: str
    how: str  # auto | review


def find_rename(
    new: Series,
    ended: list[Series],
    g: Grammar,
    cfg: dict,
    reviewer: Reviewer | None,
) -> RenameFinding | None:
    f, _ = first_last(new.values)
    if f is None or f == 0:
        return None
    best: tuple[float, Series] | None = None
    for o in ended:
        _, last = first_last(o.values)
        if last is None or o.unit != new.unit or not (f - cfg["rename_gap_hours"] <= last < f):
            continue
        tail = o.values[max(0, last - 168) : last + 1]
        tail = tail[~np.isnan(tail)]
        if len(tail) < 24:
            continue
        step = float(np.nanstd(np.diff(tail))) + 1e-6
        jump = abs(float(new.values[f]) - float(tail[-1])) / step
        if jump <= cfg["rename_jump_sigma"] and (best is None or jump < best[0]):
            best = (jump, o)
    if best is None:
        return None
    o = best[1]
    a, b = g.parse_name(o.name), g.parse_name(new.name)
    if a and b and (a.mtype, a.loop) == (b.mtype, b.loop):
        return RenameFinding(o.ts_id, new.ts_id, "auto")
    if reviewer is not None and reviewer.same_sensor(o.ts_id, new.ts_id):
        return RenameFinding(o.ts_id, new.ts_id, "review")
    return None


def unit_factor(s: Series, g: Grammar) -> float:
    """100 when a pressure declared in bar sits in the kPa range; 1 otherwise. Code decides from the declared unit
    and the plant's typical ranges; nothing else is converted."""
    mtype = g.mtype(s.name, s.unit)
    if mtype != "PT" or s.unit != "bar":
        return 1.0
    v = s.values[~np.isnan(s.values)]
    if len(v) == 0:
        return 1.0
    med = float(np.median(v))
    lo, hi = g.ranges["PT"]
    if med > hi and lo <= med / 100 <= hi:
        return 100.0
    return 1.0


@dataclass
class WorkOrderLink:
    wo_id: str
    booked: str | None  # canonical machine it was booked on
    canon: str | None  # where the graph puts it
    how: str  # booked | auto | review | kept


def mention_key(text: str, key: str, g: Grammar, reader: Reader | None):
    tags = g.tags_in(text)
    if len(tags) == 1:
        return tags[0]
    if reader is None:
        return None
    got = reader.mention(text, key)
    q = got.get("quote")
    if q and q in text:
        return g.normalize_mention(q)
    return None


def relink_work_order(
    wo: WorkOrder,
    md: MasterData,
    g: Grammar,
    reader: Reader | None,
    reviewer: Reviewer | None,
    vib_rise,  # callable(canon, day) -> bool | None
) -> WorkOrderLink:
    booked = md.canon(wo.sap_id)
    k = mention_key(wo.text, "wo:" + wo.wo_id, g, reader)
    if k is None or k not in md.by_key:
        return WorkOrderLink(wo.wo_id, booked, booked, "booked")
    named = md.by_key[k]
    if named == booked:
        return WorkOrderLink(wo.wo_id, booked, booked, "booked")
    if wo.kind == "corrective" and vib_rise(named, wo.day) is True and vib_rise(booked, wo.day) is not True:
        return WorkOrderLink(wo.wo_id, booked, named, "auto")
    if reviewer is not None:
        picked = reviewer.work_order(wo.wo_id, named)
        return WorkOrderLink(wo.wo_id, booked, md.canon(picked), "review")
    return WorkOrderLink(wo.wo_id, booked, booked, "kept")
