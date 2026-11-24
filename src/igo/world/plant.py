"""A simulated process plant with its truth, and the exports its source systems would hand over.

The truth (which machine each sensor sits on, which records are the same machine, which work orders were booked on
the wrong machine, when machines fail) stays here. The platform sees only `Exports`.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from igo.config import load
from igo.sources import EquipmentRecord, Exports, PidRow, Question, Series, WorkOrder

CODES = {"pump": "P", "compressor": "K", "heat_exchanger": "E", "vessel": "V", "fan": "F"}
SENSORS = {
    "pump": ["PT", "FT", "VT", "IT"],
    "compressor": ["PT", "TT", "VT", "IT"],
    "heat_exchanger": ["TT", "TT", "PT"],
    "vessel": ["LT", "PT", "TT"],
    "fan": ["VT", "IT"],
}
ROTATING = {"pump", "compressor", "fan"}
EN = {"PT": "pressure", "TT": "temperature", "FT": "flow", "VT": "vibration", "IT": "motor current", "LT": "level"}
DE = {"PT": "Druck", "TT": "Temperatur", "FT": "Durchfluss", "VT": "Schwingung", "IT": "Motorstrom", "LT": "Füllstand"}
CLS_EN = {"pump": "pump", "compressor": "compressor", "heat_exchanger": "exchanger", "vessel": "vessel", "fan": "fan"}
CLS_DE = {
    "pump": "Pumpe",
    "compressor": "Verdichter",
    "heat_exchanger": "Wärmetauscher",
    "vessel": "Behälter",
    "fan": "Lüfter",
}
LONG_EN = {
    "pump": "Centrifugal pump",
    "compressor": "Reciprocating compressor",
    "heat_exchanger": "Shell and tube heat exchanger",
    "vessel": "Separator vessel",
    "fan": "Cooling fan",
}
LONG_DE = {
    "pump": "Kreiselpumpe",
    "compressor": "Kolbenverdichter",
    "heat_exchanger": "Rohrbündelwärmetauscher",
    "vessel": "Abscheider",
    "fan": "Kühlerlüfter",
}
UNITS = {"PT": "bar", "TT": "degC", "FT": "m3/h", "VT": "mm/s", "IT": "A", "LT": "%"}
SYMPTOMS = [
    "high vibration",
    "mechanical seal leaking",
    "trips on overload",
    "bearing noise",
    "Lagerschaden",
    "Gleitringdichtung undicht",
    "Motor löst aus",
    "starke Schwingungen",
]


@dataclass
class Equipment:
    eid: str  # the physical machine, e.g. 21-P-2103A
    unit: int
    cls: str
    number: str  # 2103A
    pair: str | None
    sap_ids: list[str]  # primary first; more than one when the master data holds duplicates


@dataclass
class Sensor:
    sid: str
    eid: str
    mtype: str
    loop: str
    native: bool


@dataclass
class Plant:
    name: str
    world: str
    seed: int
    hours: int
    backfill_hours: int
    equipment: dict[str, Equipment]
    sensors: dict[str, Sensor]
    ts_sensor: dict[str, str]  # historian series id -> sensor id (the truth the platform must recover)
    ts_factor: dict[str, float]  # values / factor gives the declared unit (100 for kPa declared as bar)
    renamed: list[tuple[str, str]]  # (old series, new series) of one sensor
    wo_true: dict[str, str]  # work order -> equipment id
    failures: list[tuple[str, int]]  # (equipment id, hour)
    vib_true: dict[str, np.ndarray]  # equipment id -> true vibration signal (for scoring trend answers)
    incidents: list[dict]
    question_truth: dict[str, dict]
    exports: Exports
    sap_owner: dict[str, str] = field(default_factory=dict)  # sap id -> equipment id

    def answer_scope(self) -> dict[str, list[int] | str]:
        return {u["name"]: u["units"] for u in load("platform")["users"]}


def _ar(rng: np.random.Generator, n: int, phi: float, sd: float) -> np.ndarray:
    x = np.empty(n)
    x[0] = rng.normal(0, sd)
    e = rng.normal(0, sd, n)
    for i in range(1, n):
        x[i] = phi * x[i - 1] + e[i]
    return x


def world_settings(world: str) -> dict:
    w = load("world")
    base = dict(w["dev"])
    if world == "heldout":
        over = dict(w["heldout"])
        scale = over.pop("error_scale", 1.0)
        base.update(over)
        base["errors"] = {
            k: (
                min(v * scale, 0.9)
                if k.startswith(("renamed", "description", "unit", "duplicate", "ocr", "wrong"))
                else v
            )
            for k, v in base["errors"].items()
        }
    return base


def simulate(seed: int, world: str = "dev") -> Plant:
    w = world_settings(world)
    rng = np.random.default_rng(seed)
    err = w["errors"]
    days = w["days_backfill"] + w["days_project"]
    H = days * 24
    BF = w["days_backfill"] * 24
    t = np.arange(H)

    # --- equipment ---------------------------------------------------------------------------------------------
    equipment: dict[str, Equipment] = {}
    classes = list(w["classes"])
    probs = np.array([w["classes"][c] for c in classes])
    sap_next = iter(range(10_004_100, 10_099_999, 7))
    for unit in w["units"]:
        n = int(rng.integers(w["equipment_per_unit"][0], w["equipment_per_unit"][1] + 1))
        seq = 1
        made = 0
        while made < n:
            cls = str(rng.choice(classes, p=probs / probs.sum()))
            base = f"{unit}{seq:02d}"
            seq += 1
            if cls == "pump" and rng.random() < w["pump_pairs"]:
                a, b = f"{unit}-P-{base}A", f"{unit}-P-{base}B"
                equipment[a] = Equipment(a, unit, cls, base + "A", b, [str(next(sap_next))])
                equipment[b] = Equipment(b, unit, cls, base + "B", a, [str(next(sap_next))])
                made += 2
            else:
                eid = f"{unit}-{CODES[cls]}-{base}"
                equipment[eid] = Equipment(eid, unit, cls, base, None, [str(next(sap_next))])
                made += 1

    # --- operating signals ---------------------------------------------------------------------------------------
    unit_load = {u: np.clip(0.65 + _ar(rng, H, 0.995, 0.012), 0.3, 1.0) for u in w["units"]}
    run: dict[str, np.ndarray] = {}
    load_: dict[str, np.ndarray] = {}
    for eid, e in equipment.items():
        own = np.clip(0.6 + _ar(rng, H, 0.99, 0.02), 0.2, 1.0)
        load_[eid] = np.clip(0.6 * unit_load[e.unit] + 0.4 * own, 0.1, 1.0)
        if e.pair and e.number.endswith("A"):
            week = (t + int(rng.integers(0, 168))) // 168
            on = (week % 2 == 0).astype(float)
            run[eid], run[e.pair] = on, 1.0 - on
        elif e.pair:
            continue
        elif e.cls in ROTATING:
            r = np.ones(H)
            for _ in range(int(rng.poisson(days / 9))):
                stop = int(rng.integers(0, H))
                r[stop : stop + int(rng.integers(6, 48))] = 0.0
            run[eid] = r
        else:
            run[eid] = np.ones(H)

    failures: list[tuple[str, int]] = []
    deg = {eid: np.zeros(H) for eid in equipment}
    for eid, e in equipment.items():
        if e.cls in ROTATING and rng.random() < w["failure_rate"]:
            fh = int(rng.integers(BF + 10 * 24, H - 5 * 24))
            ramp = int(rng.integers(8, 19)) * 24
            amp = float(rng.uniform(3.0, 5.0))
            deg[eid][fh - ramp : fh] = np.linspace(0, amp, ramp)
            run[eid][fh : fh + int(rng.integers(24, 49))] = 0.0
            failures.append((eid, fh))

    # --- sensors and their true signals -----------------------------------------------------------------------
    sensors: dict[str, Sensor] = {}
    used_loops: set[tuple[str, str]] = set()
    for eid, e in equipment.items():
        seen: set[str] = set()
        for mtype in SENSORS[e.cls]:
            native = mtype not in seen and rng.random() >= w["independent_loop"]
            seen.add(mtype)
            if native:
                loop = e.number
            else:
                while True:
                    loop = f"{e.unit}{int(rng.integers(50, 100))}"
                    if (mtype, loop) not in used_loops:
                        break
            used_loops.add((mtype, loop))
            sid = f"{e.unit}-{mtype}-{loop}"
            sensors[sid] = Sensor(sid, eid, mtype, loop, native)

    def signal(s: Sensor) -> np.ndarray:
        e = equipment[s.eid]
        r, ld = run[s.eid], load_[s.eid]
        noise = {"PT": 0.15, "TT": 0.8, "FT": 2.0, "VT": 0.08, "IT": 1.5, "LT": 1.0}[s.mtype]
        if s.mtype == "PT":
            v = 5 + 2 * ld if e.cls == "vessel" else 2 + r * (4 + 3 * ld)
        elif s.mtype == "FT":
            v = r * (20 + 80 * ld) if e.cls != "heat_exchanger" else 40 + 120 * ld
        elif s.mtype == "VT":
            v = 0.3 + r * (1.2 + deg[s.eid])
        elif s.mtype == "IT":
            v = 1 + r * (40 + 60 * ld)
        elif s.mtype == "TT":
            if e.cls == "heat_exchanger":
                v = (80 + 60 * ld) if s.native else (40 + 30 * ld)
            elif e.cls == "compressor":
                v = 40 + r * (50 + 30 * ld)
            else:
                v = 30 + r * 15 * ld + (60 if e.cls == "vessel" else 0)
        else:
            period = float(rng.uniform(30, 90))
            v = 50 + 25 * np.sin(2 * np.pi * t / period) + 10 * ld
        return v + rng.normal(0, noise, H)

    # --- historian exports -------------------------------------------------------------------------------------
    fmts = list(w["historian_formats"])
    fprob = np.array([w["historian_formats"][f] for f in fmts])
    unit_fmt = {u: str(rng.choice(fmts, p=fprob / fprob.sum())) for u in w["units"]}
    series: list[Series] = []
    ts_sensor: dict[str, str] = {}
    ts_factor: dict[str, float] = {}
    renamed: list[tuple[str, str]] = []
    vib_true: dict[str, np.ndarray] = {}
    ts_seq = iter(range(100_001, 999_999))

    def desc_for(s: Sensor) -> str:
        e = equipment[s.eid]
        x = rng.random()
        if x < w["generic_description"]:
            return EN[s.mtype].upper()
        if rng.random() < w["german_description"]:
            return f"{DE[s.mtype]} {CLS_DE[e.cls]} {e.number}"
        return f"{CODES[e.cls]}-{e.number} {EN[s.mtype]}"

    def name_for(s: Sensor, fmt: str) -> str:
        return fmt.format(u=s.sid.split("-")[0], t=s.mtype, l=s.loop)

    for sid, s in sensors.items():
        v = signal(s)
        if s.mtype == "VT":
            vib_true[s.eid] = v.copy()
        factor = 100.0 if (s.mtype == "PT" and rng.random() < err["unit_mismatch"]) else 1.0
        v = v * factor
        desc = desc_for(s)
        fmt = unit_fmt[equipment[s.eid].unit]
        name = (
            f"TAG_{int(rng.integers(100000, 999999))}" if rng.random() < err["description_only"] else name_for(s, fmt)
        )
        if desc.isupper() and name.startswith("TAG_"):
            desc = f"{EN[s.mtype].upper()} {CLS_EN[equipment[s.eid].cls].upper()}"
        if rng.random() < err["renamed_tag"]:
            cut = int(rng.integers(BF // 2, H - 40 * 24))
            old = Series(f"TS{next(ts_seq)}", name, desc, UNITS[s.mtype], v.copy())
            old.values[cut:] = np.nan
            if rng.random() < err["rename_to_internal_id"]:
                new_name = f"TAG_{int(rng.integers(100000, 999999))}"
            else:
                new_name = name_for(s, str(rng.choice([f for f in fmts if f != fmt])))
            new = Series(f"TS{next(ts_seq)}", new_name, desc, UNITS[s.mtype], v.copy())
            new.values[:cut] = np.nan
            for x in (old, new):
                series.append(x)
                ts_sensor[x.ts_id] = sid
                ts_factor[x.ts_id] = factor
            renamed.append((old.ts_id, new.ts_id))
        else:
            x = Series(f"TS{next(ts_seq)}", name, desc, UNITS[s.mtype], v)
            series.append(x)
            ts_sensor[x.ts_id] = sid
            ts_factor[x.ts_id] = factor

    # --- SAP PM master data, with duplicates ----------------------------------------------------------------------
    records: list[EquipmentRecord] = []
    sap_owner: dict[str, str] = {}
    for eid, e in equipment.items():
        long = LONG_DE[e.cls] if rng.random() < w["german_description"] else LONG_EN[e.cls]
        tag = f"{CODES[e.cls]}-{e.number}"
        floc = f"PLT1-{e.unit}-{CODES[e.cls]}-{e.number}"
        records.append(EquipmentRecord(e.sap_ids[0], floc, f"{long} {tag}", e.cls))
        sap_owner[e.sap_ids[0]] = eid
        if rng.random() < err["duplicate_equipment"]:
            dup = str(next(sap_next))
            e.sap_ids.append(dup)
            sap_owner[dup] = eid
            variant = int(rng.integers(0, 3))
            if variant == 0:
                records.append(EquipmentRecord(dup, floc, f"{tag} (alt)", e.cls))
            elif variant == 1:
                records.append(EquipmentRecord(dup, floc, f"{CLS_DE[e.cls]} {CODES[e.cls]}{e.number}", e.cls))
            else:
                records.append(
                    EquipmentRecord(
                        dup,
                        floc.replace(f"-{e.number}", f"-{e.number[:4]}/{e.number[4:]}"),
                        f"{CLS_EN[e.cls]} {e.number}",
                        e.cls,
                    )
                )

    # --- work orders -------------------------------------------------------------------------------------------
    work_orders: list[WorkOrder] = []
    wo_true: dict[str, str] = {}
    wo_seq = iter(range(4_000_100, 4_999_999, 3))
    by_unit: dict[int, list[str]] = {}
    for eid, e in equipment.items():
        by_unit.setdefault(e.unit, []).append(eid)

    def mention(e: Equipment) -> str:
        c = CODES[e.cls]
        forms = [
            f"{c}-{e.number}",
            f"{c}{e.number}",
            f"{CLS_DE[e.cls]} {e.number}",
            f"{CLS_EN[e.cls]} {e.number[:4]} {e.number[4:]}".strip(),
        ]
        return str(rng.choice(forms))

    def add_wo(eid: str, day: int, kind: str) -> None:
        e = equipment[eid]
        if kind == "corrective":
            body = str(rng.choice(SYMPTOMS))
            text = f"{mention(e)} {body}" if rng.random() < err["wo_mentions_equipment"] else f"Found in round: {body}"
        else:
            text = f"PM inspection {mention(e)}" if rng.random() < err["wo_mentions_equipment"] else "PM inspection"
        booked = e.sap_ids[-1] if len(e.sap_ids) > 1 and rng.random() < 0.5 else e.sap_ids[0]
        if rng.random() < err["wrong_wo_equipment"]:
            other = e.pair or str(rng.choice([x for x in by_unit[e.unit] if x != eid]))
            booked = equipment[other].sap_ids[0]
        wid = str(next(wo_seq))
        work_orders.append(WorkOrder(wid, booked, day, kind, text))
        wo_true[wid] = eid

    for eid, fh in failures:
        add_wo(eid, fh // 24, "corrective")
    for eid, e in equipment.items():
        for _ in range(int(rng.poisson(w["preventive_per_equipment"]))):
            add_wo(eid, int(rng.integers(0, days)), "preventive")
        if e.cls in ROTATING and rng.random() < 0.3:  # an older corrective job from the backfill period
            add_wo(eid, int(rng.integers(0, w["days_backfill"])), "corrective")
    work_orders.sort(key=lambda x: (x.day, x.wo_id))

    # --- P&ID tag list -----------------------------------------------------------------------------------------
    def ocr(text: str) -> str:
        if rng.random() >= err["ocr_noise"]:
            return text
        swaps = [("0", "O"), ("1", "I"), ("-", "")]
        a, b = swaps[int(rng.integers(0, len(swaps)))]
        return text.replace(a, b, 1)

    pid: list[PidRow] = []
    for sensor in sensors.values():
        if rng.random() < w["pid_coverage"]:
            e = equipment[sensor.eid]
            pid.append(
                PidRow(
                    f"{e.unit}-PID-{int(rng.integers(1, 9)):03d}",
                    ocr(f"{sensor.mtype}-{sensor.loop}"),
                    ocr(f"{CODES[e.cls]}-{e.number}"),
                )
            )
    rng.shuffle(pid)  # type: ignore[arg-type]

    # --- incidents after go-live -------------------------------------------------------------------------------
    incidents: list[dict] = []
    ops = w["operations"]
    late = (H - 30 * 24, H - 2 * 24)
    for _ in range(ops["extractor_outage"]):
        u = int(rng.choice(w["units"]))
        h0 = int(rng.integers(*late))
        dur = int(rng.integers(6, 31))
        hit = [x for x in series if ts_sensor[x.ts_id].startswith(f"{u}-") and not np.isnan(x.values[h0])]
        for x in hit:
            x.values[h0 : h0 + dur] = np.nan
        incidents.append({"kind": "extractor_outage", "hour": h0, "unit": u, "series": [x.ts_id for x in hit]})
    live = [x for x in series if not np.isnan(x.values[-1]) and not x.name.startswith("TAG_")]
    for x in rng.choice(np.array(live, dtype=object), size=ops["rename_after_golive"], replace=False):
        h0 = int(rng.integers(*late))
        new = Series(
            f"TS{next(ts_seq)}", f"TAG_{int(rng.integers(100000, 999999))}", x.description, x.unit, x.values.copy()
        )
        new.values[:h0] = np.nan
        x.values[h0:] = np.nan
        series.append(new)
        ts_sensor[new.ts_id] = ts_sensor[x.ts_id]
        ts_factor[new.ts_id] = ts_factor[x.ts_id]
        incidents.append({"kind": "rename_after_golive", "hour": h0, "series": [new.ts_id], "old": x.ts_id})
    live = [x for x in series if not np.isnan(x.values[-1])]
    for x in rng.choice(np.array(live, dtype=object), size=ops["flatline"], replace=False):
        h0 = int(rng.integers(*late))
        x.values[h0:] = x.values[h0 - 1]
        incidents.append({"kind": "flatline", "hour": h0, "series": [x.ts_id]})

    # --- questions for the maintenance agent -------------------------------------------------------------------
    users = load("platform")["users"]
    questions: list[Question] = []
    question_truth: dict[str, dict] = {}
    eids = sorted(equipment)
    kinds = ["sensors", "last_corrective", "vibration_trend", "most_corrective"]
    for i in range(w["agent"]["questions"]):
        user = users[int(rng.integers(0, len(users)))]
        allowed = w["units"] if user["units"] == "all" else user["units"]
        want_out = rng.random() < w["agent"]["out_of_scope"] and user["units"] != "all"
        pool = [x for x in eids if (equipment[x].unit in allowed) != want_out]
        if not pool:
            pool = eids
        eid = str(rng.choice(pool))
        e = equipment[eid]
        kind = kinds[int(rng.integers(0, len(kinds)))]
        m = mention(e)
        text = {
            "sensors": f"Which sensors are installed on {m}?",
            "last_corrective": f"When was the last corrective work order on {m}?",
            "vibration_trend": f"Is vibration on {m} rising over the last 7 days?",
            "most_corrective": f"Which equipment in unit {e.unit} had the most corrective work orders?",
        }[kind]
        qid = f"Q{i:03d}"
        questions.append(Question(qid, user["name"], text, days - 1))
        question_truth[qid] = {"kind": kind, "eid": eid, "unit": e.unit, "mention": m, "allowed": e.unit in allowed}

    exports = Exports("plant", H, BF, series, records, work_orders, pid, questions)
    return Plant(
        w["plant"],
        world,
        seed,
        H,
        BF,
        equipment,
        sensors,
        ts_sensor,
        ts_factor,
        renamed,
        wo_true,
        failures,
        vib_true,
        incidents,
        question_truth,
        exports,
        sap_owner,
    )
