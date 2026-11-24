"""Contextualization: which machine does each historian series measure?

Evidence per candidate machine, each kept with its source so a reviewer sees why:
- name: the series name parses with the site grammar and its loop number is the machine's number;
- pid: the P&ID tag list connects that instrument to the machine (after OCR repair, only if it parses);
- description: the description names the machine (standard tag by code; other wording read by the model, kept only
  when the quote is in the text and parses);
- signal: the series moves with the machine's other sensors (starts, stops, load) over the backfill;
- type misfit: a vibration sensor on a vessel, a level on a fan.

A link is made without a person only when the best machine is near-certain and far ahead of the next one. Everything
else goes to the engineer with the candidates and their evidence, or, in designs without review, is taken as is.
"""

from __future__ import annotations

import math
import warnings
from dataclasses import dataclass, field
from typing import Protocol

import numpy as np

from igo.platform.masterdata import MasterData
from igo.platform.tags import EquipmentKey, Grammar
from igo.sources import PidRow, Series


class Reader(Protocol):
    def mention(self, text: str, key: str) -> dict: ...


class Reviewer(Protocol):
    def link(self, ts_id: str, candidates: list[str], by_hand: bool = False) -> str | None: ...


@dataclass
class Decision:
    ts_id: str
    canon: str | None
    how: str  # auto | review | accepted | inherited | none
    confidence: float
    candidates: list[dict] = field(default_factory=list)


def _blocks(v: np.ndarray, width: int = 4) -> np.ndarray:
    n = len(v) // width
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        return np.nanmean(v[: n * width].reshape(n, width), axis=1)


def _z(v: np.ndarray) -> np.ndarray:
    sd = np.nanstd(v)
    return (v - np.nanmean(v)) / sd if sd > 1e-9 else np.full_like(v, np.nan)


def corr(a: np.ndarray, b: np.ndarray, min_points: int) -> float | None:
    ok = ~(np.isnan(a) | np.isnan(b))
    if ok.sum() < min_points:
        return None
    x, y = a[ok], b[ok]
    if x.std() < 1e-9 or y.std() < 1e-9:
        return None
    return float(np.corrcoef(x, y)[0, 1])


class Contextualizer:
    def __init__(
        self,
        g: Grammar,
        md: MasterData,
        pid: list[PidRow],
        cfg: dict,
        features: dict[str, bool],
        reader: Reader | None,
        reviewer: Reviewer | None,
        review: str,
    ):
        self.g, self.md, self.cfg, self.f = g, md, cfg, features
        self.reader, self.reviewer, self.review = reader, reviewer, review
        self.w = cfg["weights"]
        self.pid: dict[tuple[str, str], EquipmentKey] = {}
        if features.get("pid", True):
            for row in pid:
                inst, eq = g.pid_instrument(row.instrument), g.pid_equipment(row.equipment)
                if inst and eq and eq in md.by_key:
                    self.pid[inst] = eq
        self.decisions: dict[str, Decision] = {}
        self.profiles: dict[str, np.ndarray] = {}
        self.blocks: dict[str, np.ndarray] = {}

    # -- evidence ------------------------------------------------------------------------------------------------
    def _unit_machines(self, unit: int | None) -> list[str]:
        return [c for c, m in self.md.machines.items() if m.key is not None and (unit is None or m.key.unit == unit)]

    def _description_key(self, s: Series) -> EquipmentKey | None:
        if not self.f.get("description", True):
            return None
        tags = self.g.tags_in(s.description)
        if len(tags) == 1:
            return tags[0]
        if self.reader is None:
            return None
        got = self.reader.mention(s.description, "desc:" + s.ts_id)
        q = got.get("quote")
        if q and q in s.description:
            return self.g.normalize_mention(q)
        return None

    def evidence(self, s: Series) -> dict[str, dict[str, float]]:
        """candidate canon -> feature -> value"""
        inst = self.g.parse_name(s.name) if self.f.get("name", True) else None
        mtype = self.g.mtype(s.name, s.unit)
        dkey = self._description_key(s)
        unit = inst.unit if inst else (dkey.unit if dkey else None)
        cands: dict[str, dict[str, float]] = {c: {} for c in self._unit_machines(unit)}
        if inst:
            for c in cands:
                k = self.md.machines[c].key
                if k is not None and k.number == inst.loop:
                    cands[c]["name"] = 1.0
            pk = self.pid.get((inst.mtype, inst.loop))
            if pk is not None and pk in self.md.by_key:
                cands.setdefault(self.md.by_key[pk], {})["pid"] = 1.0
        if dkey is not None and dkey in self.md.by_key:
            cands.setdefault(self.md.by_key[dkey], {})["description"] = 1.0
        for c in cands:
            k = self.md.machines[c].key
            if k is not None and not self.g.fits(k.code, mtype):
                cands[c]["type_misfit"] = 1.0
        if self.f.get("signal", True) and s.ts_id in self.blocks:
            # Correlation against each candidate's profile, centred on the candidates' median: every machine in a
            # unit follows the unit's load, so only what sets one machine apart (its own starts and stops) counts.
            mine = self.blocks[s.ts_id]
            rs: dict[str, float] = {}
            for c in cands:
                prof = self.profiles.get(c)
                if prof is not None:
                    r = corr(mine, prof, self.cfg["signal_min_overlap_days"] * 6)
                    if r is not None:
                        rs[c] = r
            if len(rs) >= 3:
                mid = float(np.median(list(rs.values())))
                for c, r in rs.items():
                    if r - mid > 0:  # support only: a static machine can look unremarkable and still be the one
                        cands[c]["signal"] = round(r - mid, 4)
        return cands

    def score(self, ev: dict[str, float]) -> float:
        return self.w["prior"] + sum(self.w[k] * v for k, v in ev.items())

    # -- profiles from anchors --------------------------------------------------------------------------------------
    def build_profiles(self, series: list[Series], upto: int) -> None:
        anchors: dict[str, list[np.ndarray]] = {}
        for s in series:
            z = _z(_blocks(s.values[:upto]))
            self.blocks[s.ts_id] = z
            ev = self.evidence_static(s)
            strong = [c for c, e in ev.items() if e.get("name") or e.get("pid")]
            if len(strong) == 1:
                anchors.setdefault(strong[0], []).append(z)
        for c, zs in anchors.items():
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", RuntimeWarning)
                self.profiles[c] = np.nanmean(np.vstack(zs), axis=0)

    def evidence_static(self, s: Series) -> dict[str, dict[str, float]]:
        keep, self.f = self.f, {**self.f, "signal": False, "description": False}
        try:
            return self.evidence(s)
        finally:
            self.f = keep

    # -- decide --------------------------------------------------------------------------------------------------
    def decide(self, s: Series) -> Decision:
        ev = self.evidence(s)
        ranked = sorted(((self.score(e), c, e) for c, e in ev.items()), key=lambda x: -x[0])
        probs = [1 / (1 + math.exp(-sc)) for sc, _, _ in ranked]
        cands: list[dict] = [
            {"canon": c, "p": round(p, 4), "evidence": e} for (_, c, e), p in zip(ranked, probs, strict=True)
        ][:5]
        p1 = probs[0] if probs else 0.0
        lead = ranked[0][0] - ranked[1][0] if len(ranked) > 1 else math.inf
        top = ranked[0][1] if ranked else None
        if top is not None and p1 >= self.cfg["auto_accept"] and lead >= self.cfg["auto_margin"]:
            d = Decision(s.ts_id, top, "auto", p1, cands)
        elif self.review == "band" and self.reviewer is not None:
            useful = p1 >= self.cfg["review_floor"]
            picked = self.reviewer.link(s.ts_id, [c["canon"] for c in cands] if useful else [], by_hand=not useful)
            d = Decision(s.ts_id, self.md.canon(picked) if picked else None, "review", p1, cands)
        elif top is not None and p1 >= self.cfg["review_floor"]:
            d = Decision(s.ts_id, top, "accepted", p1, cands)
        else:
            d = Decision(s.ts_id, None, "none", p1, cands)
        self.decisions[s.ts_id] = d
        return d

    def inherit(self, new_id: str, old_id: str) -> Decision:
        old = self.decisions[old_id]
        d = Decision(new_id, old.canon, "inherited", old.confidence, [{"from": old_id}])
        self.decisions[new_id] = d
        return d
