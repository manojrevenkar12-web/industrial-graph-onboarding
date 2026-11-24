"""Run one design on one simulated plant and score what it built against the plant's truth.

Timeline: the backfill (60 days) exists when onboarding starts. The design onboards; the engineer's review minutes
decide the go-live day (engineer_hours_per_day). After go-live the plant keeps running for the rest of the window:
new series appear, a historian extractor stops, sensors flatline, machines degrade and fail, people ask questions.
"""

from __future__ import annotations

import difflib
import math
import re
from typing import Any

from igo.config import ROOT, load
from igo.platform import agent as agent_mod
from igo.platform import masterdata, monitor, quality
from igo.platform.graph import GraphView, Store
from igo.platform.match import Contextualizer, Decision
from igo.platform.quality import WorkOrderLink, first_last
from igo.platform.tags import Grammar
from igo.sources import Series
from igo.world.actors import Engineer, SimReader, _rng
from igo.world.plant import Plant, simulate

CONFIG = ROOT / "config"
_PLANTS: dict[tuple[str, int], Plant] = {}


def plant(world: str, seed: int) -> Plant:
    if (world, seed) not in _PLANTS:
        _PLANTS.clear()
        _PLANTS[(world, seed)] = simulate(seed, world)
    return _PLANTS[(world, seed)]


def designs() -> dict[str, dict]:
    d = load("designs")
    out = {k: v for k, v in d.items() if k != "ablations"}
    base = d["platform"]
    for name, a in d["ablations"].items():
        spec = {**base, "label": a["label"]}
        for k, v in a["overlay"].items():
            spec[k] = {**base.get(k, {}), **v} if isinstance(v, dict) else v
        out[name] = spec
    return out


class PerfectReader:
    """How a person reads a question: no misreads. Used for the manual design's engineer."""

    def __init__(self, inner: SimReader):
        self.inner = inner

    def read_question(self, text: str, key: str) -> dict:
        r = self.inner.read_question(text, key)
        m = re.search(r"\bon (.+?)(?: rising over the last 7 days)?\?$", text)
        r["entity"] = m.group(1) if m else None
        low = text.lower()
        r["intent"] = (
            "most_corrective"
            if "most corrective" in low
            else "last_corrective"
            if "last corrective" in low
            else "vibration_trend"
            if "vibration" in low
            else "sensors"
        )
        return r


def _view(s: Series, upto: int) -> Series:
    return Series(s.ts_id, s.name, s.description, s.unit, s.values[:upto])


def run(world: str, seed: int, name: str, design: dict) -> dict[str, Any]:
    return score(**onboard(world, seed, name, design))


def onboard(world: str, seed: int, name: str, design: dict) -> dict[str, Any]:
    """Onboard one plant with one design and run it to the end of the window; returns what scoring needs."""
    p = plant(world, seed)
    x = p.exports
    cfg = load("platform")
    g = Grammar(x.site)
    reader = SimReader(seed)
    eng = Engineer(p)
    BF, H = x.backfill_hours, x.hours
    series = x.series_by_id()
    span = {t: first_last(s.values) for t, s in series.items()}
    first: dict[str, int] = {t: f for t, (f, _) in span.items() if f is not None}
    last = {t: lst for t, (_, lst) in span.items()}
    visible = sorted((t for t in first if first[t] < BF), key=lambda t: (first[t], t))
    later = sorted((t for t in first if first[t] >= BF), key=lambda t: (first[t], t))
    matcher, review, use_quality = design["matcher"], design.get("review", "none"), bool(design.get("quality"))
    capacity = cfg["engineer_hours_per_day"] * 60

    dedupe = matcher == "platform" and use_quality
    md = masterdata.build(
        x.equipment,
        g,
        reader if matcher == "platform" else None,
        eng if (dedupe and review == "band") else None,
        dedupe,
    )
    decisions: dict[str, Decision] = {}
    continues: list[tuple[str, str]] = []
    factors: dict[str, float] = {}
    detected_new: dict[str, int] = {}

    # ---- onboarding --------------------------------------------------------------------------------------------
    ctx: Contextualizer | None = None
    records = [(r.sap_id, r.floc, r.description) for r in x.equipment]

    def fuzzy(s: Series) -> Decision:
        """String matching as most onboarding scripts do it: the record whose tag number shares the longest run of
        digits with the series name and description, ties broken by description similarity; best taken as is."""
        text = f"{s.name} {s.description}".lower()

        def sim(r) -> tuple[int, float]:
            num = r.floc.rsplit("-", 1)[-1].lower()
            m = difflib.SequenceMatcher(None, text, num).find_longest_match(0, len(text), 0, len(num))
            return m.size, difflib.SequenceMatcher(None, s.description.lower(), r.description.lower()).ratio()

        best = max(((sim(r), r.sap_id) for r in x.equipment), default=((0, 0.0), None))
        (digits, ratio), sap = best
        canon = md.canon(sap) if sap and (digits >= 4 or ratio >= 0.5) else None
        return Decision(s.ts_id, canon, "accepted" if canon else "none", ratio)

    def model(s: Series) -> Decision:
        sap = reader.link(s.name, s.description, records, s.ts_id)
        canon = md.canon(sap) if sap else None
        return Decision(s.ts_id, canon, "accepted" if canon else "none", 0.9)

    standard = re.compile(load(f"sites/{x.site}")["historian"]["name_patterns"][1])

    def manual(s: Series) -> Decision:
        m = standard.match(s.name)
        if m:
            k = next((k for k in md.by_key if k.number == m["loop"] and k.unit == int(m["unit"])), None)
            if k is not None:
                return Decision(s.ts_id, md.by_key[k], "lookup", 1.0)
        picked = eng.link(s.ts_id, [], by_hand=True)
        return Decision(s.ts_id, md.canon(picked) if picked else None, "review", 1.0)

    def contextualize(t: str, upto: int) -> None:
        assert ctx is not None
        s = _view(series[t], upto)
        if use_quality:
            ended = [_view(series[o], upto) for o in decisions if last[o] is not None and last[o] < upto - 1]  # type: ignore[operator]
            found = quality.find_rename(s, ended, g, load("platform")["quality"], eng if review == "band" else None)
            if found is not None:
                decisions[t] = ctx.inherit(t, found.old)
                continues.append((found.old, t))
                return
        decisions[t] = ctx.decide(s)

    if matcher == "platform":
        ctx = Contextualizer(
            g, md, x.pid, cfg["matching"], design.get("features", {}), reader, eng if review == "band" else None, review
        )
        ctx.build_profiles([_view(series[t], BF) for t in visible], BF)
        for t in visible:
            contextualize(t, BF)
    else:
        fn = {"fuzzy": fuzzy, "model": model, "manual": manual}[matcher]
        for t in visible:
            decisions[t] = fn(_view(series[t], BF))
    if use_quality:
        for t in visible:
            factors[t] = quality.unit_factor(_view(series[t], BF), g)

    # work orders known at onboarding
    mtype_of = {t: g.mtype(s.name, s.unit) for t, s in series.items()}
    wo_by_id = {w.wo_id: w for w in x.work_orders}
    view = GraphView(md, decisions, series, {}, wo_by_id, factors, continues, mtype_of)
    slope = cfg["monitoring"]["vibration_slope_mm_s_per_day"]

    def link_wo(w) -> WorkOrderLink:
        if not use_quality:
            return WorkOrderLink(w.wo_id, md.canon(w.sap_id), md.canon(w.sap_id), "booked")
        return quality.relink_work_order(
            w, md, g, reader, eng if review == "band" else None, lambda c, d: view.vib_rising(c, d, slope)
        )

    for w in x.work_orders:
        if w.day < BF // 24:
            view.wo_links[w.wo_id] = link_wo(w)
    onboarding_minutes = eng.minutes
    onboarding_items = dict(eng.items)
    golive = BF + math.ceil(onboarding_minutes / capacity) * 24

    # ---- operations after go-live ------------------------------------------------------------------------------
    if design["monitoring"] == "platform":
        for day in range(golive // 24, H // 24 + 1):
            check = day * 24
            new = [t for t in later if t not in decisions and first[t] < check]
            if not new:
                continue
            if ctx is not None:
                ctx.build_profiles([series[t] for t in sorted(decisions) + new], check)
            for t in new:
                detected_new[t] = check
                if ctx is not None:
                    contextualize(t, check)
                else:
                    fn = fuzzy if matcher == "fuzzy" else model
                    decisions[t] = fn(_view(series[t], check))
                if use_quality:
                    factors[t] = quality.unit_factor(_view(series[t], check), g)
    for w in x.work_orders:
        if w.wo_id not in view.wo_links:
            view.wo_links[w.wo_id] = link_wo(w)
    for t in series:
        decisions.setdefault(t, Decision(t, None, "none", 0.0))

    return {
        "p": p,
        "design": design,
        "name": name,
        "view": view,
        "golive": golive,
        "onboarding_minutes": onboarding_minutes,
        "onboarding_items": onboarding_items,
        "eng": eng,
        "reader": reader,
        "detected_new": detected_new,
        "g": g,
    }


def score(
    p: Plant,
    design: dict,
    name: str,
    view: GraphView,
    golive: int,
    onboarding_minutes: float,
    onboarding_items: dict,
    eng: Engineer,
    reader: SimReader,
    detected_new: dict[str, int],
    g: Grammar,
) -> dict[str, Any]:
    cfg = load("platform")
    x = p.exports
    owner = p.sap_owner
    truth_eid = {t: p.sensors[s].eid for t, s in p.ts_sensor.items()}

    # links
    decided = view.decisions
    linked = {t: d for t, d in decided.items() if d.canon is not None}
    correct = sum(1 for t, d in linked.items() if d.canon is not None and owner.get(d.canon) == truth_eid[t])
    hows: dict[str, int] = {}
    for d in decided.values():
        hows[d.how] = hows.get(d.how, 0) + 1

    # master data
    planted_dups = sum(len(e.sap_ids) - 1 for e in p.equipment.values())
    merges = view.md.merges
    dup_right = sum(1 for a, b, _ in merges if owner[a] == owner[b])
    renames_planted = len(p.renamed) + sum(1 for i in p.incidents if i["kind"] == "rename_after_golive")
    true_pairs = set(p.renamed) | {
        (i["old"], i["series"][0]) for i in p.incidents if i["kind"] == "rename_after_golive"
    }
    ren_right = sum(1 for pair in view.continues if pair in true_pairs)
    unit_planted = sum(1 for f in p.ts_factor.values() if f != 1.0)
    unit_caught = sum(1 for t, f in view.factors.items() if f != 1.0 and p.ts_factor[t] != 1.0)
    unit_false = sum(1 for t, f in view.factors.items() if f != 1.0 and p.ts_factor[t] == 1.0)

    # work orders
    wo_total = len(x.work_orders)
    misbooked = [w for w in x.work_orders if owner[w.sap_id] != p.wo_true[w.wo_id]]
    links = view.wo_links
    wo_right = sum(1 for w in x.work_orders if owner.get(links[w.wo_id].canon or "") == p.wo_true[w.wo_id])
    relinked = [w for w in x.work_orders if links[w.wo_id].canon != links[w.wo_id].booked]
    relink_wrong = sum(1 for w in relinked if owner.get(links[w.wo_id].canon or "") != p.wo_true[w.wo_id])
    misbooked_fixed = sum(1 for w in misbooked if owner.get(links[w.wo_id].canon or "") == p.wo_true[w.wo_id])

    # incidents
    mon = cfg["monitoring"]
    slope = mon["vibration_slope_mm_s_per_day"]
    unit_series: dict[int, list[Series]] = {}
    for t, d in linked.items():
        u = view.machine_unit(d.canon)  # type: ignore[arg-type]
        if u is not None:
            unit_series.setdefault(u, []).append(view.series[t])
    fresh = (
        monitor.freshness_alerts(unit_series, golive, mon["freshness_sla_hours"])
        if design["monitoring"] == "platform"
        else []
    )
    flat = (
        dict(monitor.flatline_alerts([view.series[t] for t in linked], golive, mon["flatline_hours"]))
        if design["monitoring"] == "platform"
        else {}
    )
    incidents = []
    for i, inc in enumerate(p.incidents):
        h0 = inc["hour"]
        if design["monitoring"] != "platform":
            r = _rng(p.seed, "user-notice", f"{inc['kind']}:{i}")
            delay = {"extractor_outage": r.uniform(12, 72), "flatline": r.uniform(48, 240)}.get(inc["kind"])
            det = None if delay is None or h0 + delay > x.hours else float(delay)
        elif inc["kind"] == "extractor_outage":
            hits = [h - h0 for u, h in fresh if u == inc["unit"] and h0 <= h <= h0 + 48]
            det = float(min(hits)) if hits else None
        elif inc["kind"] == "flatline":
            t = inc["series"][0]
            det = float(flat[t] - h0) if t in flat else None
        else:
            t = inc["series"][0]
            det = float(detected_new[t] - h0) if t in detected_new else None
        sla = mon["sla_hours"][inc["kind"]]
        incidents.append({"kind": inc["kind"], "hours_to_detect": det, "in_sla": det is not None and det <= sla})

    # early warnings
    vib = {c: v for c in view.md.machines if (v := view.vibration(c)) is not None}
    warns = monitor.warnings(vib, golive // 24, mon)
    lo, hi = mon["warning_window_days"]
    warned = 0
    for eid, fh in p.failures:
        fd = fh // 24
        if any(owner[c] == eid and fd - hi <= d <= fd - lo for c, d in warns):
            warned += 1
    false_warn = sum(
        1 for c, d in warns if not any(owner[c] == eid and 0 <= fh // 24 - d <= hi for eid, fh in p.failures)
    )

    # agent
    users = {u["name"]: u["units"] for u in cfg["users"]}
    kind = design["agent"]
    rdr = PerfectReader(reader) if kind == "manual" else reader
    res = {"right": 0, "wrong": 0, "declined": 0, "leaks": 0, "refused_wrongly": 0, "model_calls": 0}
    transcripts: list[dict] = []
    for q in x.questions:
        tr = p.question_truth[q.q_id]
        a = agent_mod.answer(q.q_id, q.text, users[q.user], view, g, rdr, kind != "unguarded", slope, q.day)
        if kind == "manual":
            eng.answer_question()
        else:
            res["model_calls"] += a.model_calls
        verdict = _judge(p, tr, a, owner, slope, q.day)
        res[verdict] += 1
        if len(transcripts) < 12:
            transcripts.append(
                {
                    "q": q.q_id,
                    "user": q.user,
                    "text": q.text,
                    "kind": a.kind,
                    "answer": _show(a, view),
                    "verdict": verdict,
                    "cited": a.cited[:6],
                }
            )

    golive_days = (golive - x.backfill_hours) / 24
    store_changes = None
    if name == "platform":
        st = Store()
        st.apply(view.spec())
        store_changes = sum(sum(v.values()) for v in st.apply(view.spec()).values())
    return {
        "design": name,
        "label": design["label"],
        "series": len(decided),
        "links": {
            "linked": len(linked),
            "correct": correct,
            "precision": correct / max(1, len(linked)),
            "recall": correct / max(1, len(decided)),
            "how": hows,
        },
        "engineer": {
            "onboarding_minutes": onboarding_minutes,
            "items": onboarding_items,
            "all_items": dict(eng.items),
            "all_minutes": eng.minutes,
            "golive_days": golive_days,
        },
        "master": {
            "duplicates_planted": planted_dups,
            "merged_right": dup_right,
            "merged_wrong": len(merges) - dup_right,
        },
        "renames": {
            "planted": renames_planted,
            "merged_right": ren_right,
            "merged_wrong": len(view.continues) - ren_right,
        },
        "units": {"planted": unit_planted, "caught": unit_caught, "false": unit_false},
        "work_orders": {
            "total": wo_total,
            "misbooked": len(misbooked),
            "right": wo_right,
            "relinked": len(relinked),
            "relink_wrong": relink_wrong,
            "misbooked_fixed": misbooked_fixed,
        },
        "incidents": incidents,
        "warnings": {"failures": len(p.failures), "warned": warned, "false": false_warn},
        "agent": res,
        "transcripts": transcripts,
        "store_reapply_changes": store_changes,
        "review_sample": _review_sample(view, p),
        "machines": len(p.equipment),
    }


def _judge(p: Plant, tr: dict, a, owner: dict[str, str], slope: float, day: int) -> str:
    answered = not (a.refused or a.declined)
    if not tr["allowed"]:
        if a.refused:
            return "right"
        return "leaks" if answered else "declined"
    if a.refused:
        return "refused_wrongly"
    if a.declined:
        return "declined"
    eid = tr["eid"]
    if tr["kind"] != a.kind:
        return "wrong"
    if a.kind == "sensors":
        want = {s for s, x in p.sensors.items() if x.eid == eid}
        got = {p.ts_sensor[t] for t in a.value}
        return "right" if got == want else "wrong"
    if a.kind == "last_corrective":
        days = [
            w.day
            for w in p.exports.work_orders
            if p.wo_true[w.wo_id] == eid and w.kind == "corrective" and w.day <= day
        ]
        return "right" if a.value == (max(days) if days else None) else "wrong"
    if a.kind == "vibration_trend":
        v = p.vib_true.get(eid)
        trend = None if v is None else monitor.rising(monitor.running_daily(v), day, slope)
        return "right" if a.value == trend else "wrong"
    counts: dict[str, int] = {}
    for e in p.equipment.values():
        if e.unit == tr["unit"]:
            counts[e.eid] = 0
    for w in p.exports.work_orders:
        if w.kind == "corrective" and w.day <= day and p.wo_true[w.wo_id] in counts:
            counts[p.wo_true[w.wo_id]] += 1
    top = max(counts.values()) if counts else 0
    best = {e for e, c in counts.items() if c == top}
    return "right" if a.value is not None and owner.get(a.value) in best else "wrong"


def _show(a, view: GraphView) -> str:
    if a.refused:
        return "Not shown: outside your units."
    if a.declined:
        return "Which machine do you mean? Please name it by its tag."
    if a.kind == "sensors":
        return ", ".join(view.series[t].name for t in a.value) or "No sensors linked."
    if a.kind == "most_corrective":
        k = view.md.machines[a.value].key if a.value else None
        return str(k) if k else "No machines."
    if a.kind == "last_corrective":
        return f"Day {a.value}" if a.value is not None else "No corrective work order."
    return {True: "Yes, rising.", False: "No.", None: "No vibration sensor linked."}[a.value]


def _review_sample(view: GraphView, p: Plant) -> list[dict]:
    out: list[dict] = []
    for t, d in sorted(view.decisions.items()):
        if d.how != "review" or not d.candidates or len(out) >= 8:
            continue
        s = view.series[t]
        cands = []
        for c in d.candidates[:3]:
            k = view.md.machines[c["canon"]].key
            cands.append(
                {
                    "tag": str(k) if k else c["canon"],
                    "p": c["p"],
                    "evidence": {k2: round(v, 2) for k2, v in c["evidence"].items()},
                }
            )
        chosen = view.md.machines[d.canon].key if d.canon else None
        out.append(
            {
                "ts": t,
                "name": s.name,
                "description": s.description,
                "candidates": cands,
                "chosen": str(chosen) if chosen else None,
                "right": d.canon is not None and p.sap_owner.get(d.canon) == p.sensors[p.ts_sensor[t]].eid,
            }
        )
    return out
