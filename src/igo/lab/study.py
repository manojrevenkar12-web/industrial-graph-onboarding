"""The study: every design on the development plants, or once on the held-out plants behind a lock."""

from __future__ import annotations

import hashlib
import json
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any

import numpy as np

from igo.config import CONFIG, ROOT, load
from igo.lab import simulate
from igo.lab.tidy import tidy

REPORTS = ROOT / "reports"
LOCK = REPORTS / "heldout.lock"


def config_hash() -> str:
    h = hashlib.sha256()
    for p in sorted(CONFIG.rglob("*.yml")):
        h.update(str(p.relative_to(CONFIG)).encode())
        h.update(p.read_bytes())
    return h.hexdigest()[:16]


def _job(args: tuple[str, int]) -> list[dict]:
    world, seed = args
    return [simulate.run(world, seed, n, d) for n, d in simulate.designs().items()]


def run_world(world: str, seeds: list[int], workers: int = 2) -> dict[str, list[dict]]:
    with ProcessPoolExecutor(max_workers=workers) as ex:
        per_seed = list(ex.map(_job, [(world, s) for s in seeds]))
    out: dict[str, list[dict]] = {}
    for runs in per_seed:
        for r in runs:
            out.setdefault(r["design"], []).append(r)
    return out


def _sum(rs: list[dict], *path: str) -> float:
    total = 0.0
    for r in rs:
        x: Any = r
        for p in path:
            x = x[p]
        total += x
    return total


def _share(a: float, b: float) -> float | None:
    return a / b if b else None


def summarize(world: str, seeds: list[int], runs: dict[str, list[dict]]) -> dict:
    rows: dict[str, dict[str, Any]] = {}
    for name, rs in runs.items():
        inc = [i for r in rs for i in r["incidents"]]
        kinds = sorted({i["kind"] for i in inc})
        questions_by_hand = sum(r["engineer"]["all_items"].get("question", 0) for r in rs)
        rows[name] = {
            "label": rs[0]["label"],
            "series": int(_sum(rs, "series")),
            "machines": int(_sum(rs, "machines")),
            "link_precision": _share(_sum(rs, "links", "correct"), _sum(rs, "links", "linked")),
            "link_recall": _share(_sum(rs, "links", "correct"), _sum(rs, "series")),
            "wrong_links": int(_sum(rs, "links", "linked") - _sum(rs, "links", "correct")),
            "auto_share": _share(
                sum(r["links"]["how"].get("auto", 0) + r["links"]["how"].get("inherited", 0) for r in rs),
                _sum(rs, "series"),
            ),
            "review_items": int(
                sum(sum(v for k, v in r["engineer"]["all_items"].items() if k != "question") for r in rs)
            ),
            "questions_by_hand": int(questions_by_hand),
            "onboarding_hours": _sum(rs, "engineer", "onboarding_minutes") / 60 / len(rs),
            "golive_days": _sum(rs, "engineer", "golive_days") / len(rs),
            "question_hours": sum(
                r["engineer"]["all_minutes"] - r["engineer"]["onboarding_minutes"]
                for r in rs
                if r["design"] == "status_quo"
            )
            / 60
            / len(rs),
            "duplicates": {
                "planted": int(_sum(rs, "master", "duplicates_planted")),
                "merged_right": int(_sum(rs, "master", "merged_right")),
                "merged_wrong": int(_sum(rs, "master", "merged_wrong")),
            },
            "renames": {
                "planted": int(_sum(rs, "renames", "planted")),
                "merged_right": int(_sum(rs, "renames", "merged_right")),
                "merged_wrong": int(_sum(rs, "renames", "merged_wrong")),
            },
            "units": {k: int(_sum(rs, "units", k)) for k in ("planted", "caught", "false")},
            "work_orders": {
                k: int(_sum(rs, "work_orders", k))
                for k in ("total", "misbooked", "right", "relinked", "relink_wrong", "misbooked_fixed")
            },
            "incidents_in_sla": _share(sum(i["in_sla"] for i in inc), len(inc)),
            "incidents": {
                k: {
                    "n": sum(1 for i in inc if i["kind"] == k),
                    "in_sla": sum(1 for i in inc if i["kind"] == k and i["in_sla"]),
                    "never": sum(1 for i in inc if i["kind"] == k and i["hours_to_detect"] is None),
                    "median_hours": (
                        float(np.median(h))
                        if (
                            h := [
                                i["hours_to_detect"] for i in inc if i["kind"] == k and i["hours_to_detect"] is not None
                            ]
                        )
                        else None
                    ),
                }
                for k in kinds
            },
            "failures": int(_sum(rs, "warnings", "failures")),
            "warned": int(_sum(rs, "warnings", "warned")),
            "false_warnings": int(_sum(rs, "warnings", "false")),
            "agent": {k: int(_sum(rs, "agent", k)) for k in rs[0]["agent"]},
            "store_reapply_changes": rs[0]["store_reapply_changes"],
        }
        a = rows[name]["agent"]
        asked = a["right"] + a["wrong"] + a["declined"] + a["leaks"] + a["refused_wrongly"]
        rows[name]["agent_right"] = _share(a["right"], asked)
        rows[name]["questions"] = asked
    first = {n: rs[0] for n, rs in runs.items()}
    return {
        "world": world,
        "seeds": seeds,
        "config_hash": config_hash(),
        "designs": rows,
        "samples": {
            "transcripts": {n: first[n]["transcripts"] for n in ("platform", "model_alone", "status_quo")},
            "review": first["platform"]["review_sample"],
            "links": first["platform"]["link_sample"],
        },
    }


def judge(summary: dict) -> list[dict]:
    g = load("gates")
    d = summary["designs"]
    p, sq = d["platform"], d["status_quo"]
    wo = p["work_orders"]
    checks = [
        ("Links to the right machine, of links made", p["link_precision"], ">=", g["link_precision_min"]),
        ("Series linked to the right machine, of all series", p["link_recall"], ">=", g["link_recall_min"]),
        (
            "Engineer onboarding hours / manual onboarding hours",
            p["onboarding_hours"] / sq["onboarding_hours"],
            "<=",
            g["engineer_minutes_ratio_max"],
        ),
        (
            "Duplicate master records merged, of planted",
            p["duplicates"]["merged_right"] / max(1, p["duplicates"]["planted"]),
            ">=",
            g["duplicates_found_min"],
        ),
        (
            "Wrong work-order relinks, of relinks",
            wo["relink_wrong"] / max(1, wo["relinked"]),
            "<=",
            g["wo_wrong_relinks_max"],
        ),
        ("Incidents detected within their SLA", p["incidents_in_sla"], ">=", g["incidents_in_sla_min"]),
        ("Agent questions answered right", p["agent_right"], ">=", g["agent_right_min"]),
        ("Agent answers outside the user's units", p["agent"]["leaks"], "<=", g["agent_leaks_max"]),
        ("Failures warned 2-21 days ahead", p["warned"] / max(1, p["failures"]), ">=", g["failures_warned_min"]),
    ]
    return [
        {
            "gate": n,
            "value": float(v),
            "op": op,
            "limit": float(lim),
            "pass": bool(v <= lim if op == "<=" else v >= lim),
        }
        for n, v, op, lim in checks
    ]


def write(name: str, summary: dict) -> Path:
    REPORTS.mkdir(exist_ok=True)
    summary["gates"] = judge(summary)
    path = REPORTS / f"{name}.json"
    path.write_text(json.dumps(tidy(summary), indent=1, sort_keys=True, default=float) + "\n")
    return path


def run_dev(workers: int = 2) -> Path:
    seeds = load("seeds")["dev"]
    return write("dev", summarize("dev", seeds, run_world("dev", seeds, workers)))


def run_heldout(workers: int = 2) -> Path:
    if LOCK.exists():
        print(
            f"held-out plants already ran ({LOCK.read_text().strip()}); new evidence needs new seeds and an ADR",
            file=sys.stderr,
        )
        raise SystemExit(3)
    seeds = load("seeds")["heldout"]
    REPORTS.mkdir(exist_ok=True)
    LOCK.write_text(json.dumps({"seeds": seeds, "config_hash": config_hash()}) + "\n")
    return write("heldout", summarize("heldout", seeds, run_world("heldout", seeds, workers)))
