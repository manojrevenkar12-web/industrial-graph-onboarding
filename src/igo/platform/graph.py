"""The onboarded industrial knowledge graph, and how it gets into a store.

Data model (config-free, the same for every site):
  Unit -(contains)-> Machine -(measured_by)-> TimeSeries
  Machine -(has_activity)-> WorkOrder
  Record -(same_machine_as)-> Machine            (SAP PM duplicates kept as aliases, never deleted)
  TimeSeries -(continues)-> TimeSeries           (a renamed tag)

Onboarding produces a spec (nodes and edges keyed by external id). `plan` diffs a spec against the store; `apply`
writes only the difference, so applying the same spec twice changes nothing.
"""

from __future__ import annotations

import json
import sqlite3
import warnings
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from igo.platform.masterdata import MasterData
from igo.platform.match import Decision
from igo.platform.monitor import rising, running_daily
from igo.platform.quality import WorkOrderLink
from igo.sources import Series, WorkOrder


@dataclass
class GraphView:
    md: MasterData
    decisions: dict[str, Decision]
    series: dict[str, Series]
    wo_links: dict[str, WorkOrderLink]
    work_orders: dict[str, WorkOrder]
    factors: dict[str, float] = field(default_factory=dict)
    continues: list[tuple[str, str]] = field(default_factory=list)
    mtype_of: dict[str, str | None] = field(default_factory=dict)

    def sensors(self, canon: str) -> list[str]:
        return sorted(t for t, d in self.decisions.items() if d.canon == canon)

    def machine_unit(self, canon: str) -> int | None:
        return self.md.unit_of(canon)

    def machines_in(self, unit: int) -> list[str]:
        return sorted(c for c, m in self.md.machines.items() if m.key is not None and m.key.unit == unit)

    def work_orders_on(self, canon: str) -> list[WorkOrder]:
        return [self.work_orders[w] for w, link in self.wo_links.items() if link.canon == canon]

    def vibration(self, canon: str) -> np.ndarray | None:
        vs = [self.series[t].values for t in self.sensors(canon) if self.mtype_of.get(t) == "VT"]
        if not vs:
            return None
        if len(vs) == 1:
            return vs[0]
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            return np.nanmean(np.vstack(vs), axis=0)

    def vib_rising(self, canon: str, day: int, slope: float) -> bool | None:
        v = self.vibration(canon)
        return None if v is None else rising(running_daily(v), day, slope)

    def spec(self) -> dict[str, dict]:
        nodes: dict[str, dict] = {}
        edges: dict[str, dict] = {}
        for c, m in self.md.machines.items():
            if self.md.canon(c) != c:
                continue
            unit = m.key.unit if m.key else None
            nodes[f"machine:{c}"] = {
                "type": "Machine",
                "tag": str(m.key) if m.key else None,
                "class": m.cls,
                "unit": unit,
            }
            if unit is not None:
                nodes.setdefault(f"unit:{unit}", {"type": "Unit", "unit": unit})
                edges[f"unit:{unit}|contains|machine:{c}"] = {}
            for r in m.records[1:]:
                nodes[f"record:{r}"] = {"type": "Record", "sap_id": r}
                edges[f"record:{r}|same_machine_as|machine:{c}"] = {}
        for t, d in sorted(self.decisions.items()):
            s = self.series[t]
            nodes[f"ts:{t}"] = {
                "type": "TimeSeries",
                "name": s.name,
                "unit": s.unit,
                "factor": self.factors.get(t, 1.0),
                "link": d.how,
                "confidence": round(d.confidence, 4),
            }
            if d.canon is not None:
                edges[f"machine:{d.canon}|measured_by|ts:{t}"] = {"how": d.how}
        for old, new in self.continues:
            edges[f"ts:{old}|continues|ts:{new}"] = {}
        for w, link in sorted(self.wo_links.items()):
            wo = self.work_orders[w]
            nodes[f"wo:{w}"] = {"type": "WorkOrder", "day": wo.day, "kind": wo.kind, "text": wo.text}
            if link.canon is not None:
                edges[f"machine:{link.canon}|has_activity|wo:{w}"] = {"how": link.how}
        return {"nodes": nodes, "edges": edges}


class Store:
    """SQLite: one row per node and per edge, keyed by external id."""

    def __init__(self, path: str | Path = ":memory:"):
        self.db = sqlite3.connect(str(path))
        self.db.executescript(
            "create table if not exists nodes (xid text primary key, props text not null);"
            "create table if not exists edges (xid text primary key, props text not null);"
        )

    def read(self) -> dict[str, dict]:
        return {
            t: {x: json.loads(p) for x, p in self.db.execute(f"select xid, props from {t}")} for t in ("nodes", "edges")
        }

    def plan(self, spec: dict[str, dict]) -> dict[str, dict[str, list[str]]]:
        have = self.read()
        out: dict[str, dict[str, list[str]]] = {}
        for t in ("nodes", "edges"):
            new, old = spec[t], have[t]
            out[t] = {
                "create": sorted(set(new) - set(old)),
                "update": sorted(x for x in set(new) & set(old) if new[x] != old[x]),
                "delete": sorted(set(old) - set(new)),
            }
        return out

    def apply(self, spec: dict[str, dict]) -> dict[str, dict[str, int]]:
        p = self.plan(spec)
        with self.db:
            for t in ("nodes", "edges"):
                for x in p[t]["create"] + p[t]["update"]:
                    self.db.execute(
                        f"insert or replace into {t} values (?, ?)", (x, json.dumps(spec[t][x], sort_keys=True))
                    )
                for x in p[t]["delete"]:
                    self.db.execute(f"delete from {t} where xid = ?", (x,))
        return {t: {k: len(v) for k, v in p[t].items()} for t in p}
