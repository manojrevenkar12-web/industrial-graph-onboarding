"""After go-live: freshness, flatlines, new series and early warnings, each routed to an owner.

The checks run on what the graph knows (linked series per unit and machine), hour by hour, as a scheduler would.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from igo.sources import Series


def running_daily(v: np.ndarray) -> np.ndarray:
    """Daily mean over the hours the machine looks to be running (value above a quarter of its usual span)."""
    ok = v[~np.isnan(v)]
    if len(ok) < 48:
        return np.full(len(v) // 24, np.nan)
    lo, hi = np.percentile(ok, 2), np.percentile(ok, 95)
    cut = lo + 0.25 * (hi - lo)
    days = len(v) // 24
    out = np.full(days, np.nan)
    for d in range(days):
        x = v[d * 24 : (d + 1) * 24]
        x = x[~np.isnan(x) & (x > cut)]
        if len(x) >= 6:
            out[d] = x.mean()
    return out


def rising(daily: np.ndarray, day: int, slope_min: float) -> bool | None:
    """Is the running vibration rising into `day`? None when there is too little data to say."""
    if day < 17:
        return None
    recent = daily[day - 3 : day + 1]
    before = daily[day - 6 : day - 2]
    base = daily[max(0, day - 17) : day - 3]
    if np.isnan(recent).all() or np.isnan(before).all() or np.isnan(base).all():
        return None
    slope = (np.nanmean(recent) - np.nanmean(before)) / 3.0
    return bool(slope > slope_min and np.nanmean(recent) > 1.3 * np.nanmedian(base))


def warnings(vib: dict[str, np.ndarray], from_day: int, cfg: dict) -> list[tuple[str, int]]:
    """(machine, day) early warnings from rising running vibration, at most one a week per machine."""
    out: list[tuple[str, int]] = []
    for canon, v in vib.items():
        daily = running_daily(v)
        last = -99
        for d in range(max(from_day, 17), len(daily)):
            if d - last >= 7 and rising(daily, d, cfg["vibration_slope_mm_s_per_day"]):
                out.append((canon, d))
                last = d
    return out


def _first_of_runs(flag: np.ndarray, start: int, length: int) -> list[int]:
    """Hours (from `start`) at which a run of True reaches `length`."""
    f = flag.astype(np.int64)
    f[:start] = 0
    c = np.cumsum(f)
    reset = np.where(f == 0, c, 0)
    run = c - np.maximum.accumulate(reset)
    return [int(h) for h in np.flatnonzero(run == length)]


def freshness_alerts(unit_series: dict[int, list[Series]], start: int, sla: int) -> list[tuple[int, int]]:
    """(unit, hour) when every live series of a unit has been silent for `sla` hours."""
    out: list[tuple[int, int]] = []
    for unit, ss in unit_series.items():
        if not ss:
            continue
        m = np.vstack([s.values for s in ss])
        has = ~np.isnan(m)
        live = np.zeros_like(has)
        live[:, 24:] = has[:, :-24]  # a series is expected if it had data a day earlier
        n_live = live.sum(0)
        silent = (n_live > 0) & ((~has & live).sum(0) >= 0.8 * np.maximum(n_live, 1))
        for h in _first_of_runs(silent, start, sla):
            out.append((unit, h))
    return out


def flatline_alerts(series: list[Series], start: int, hours: int) -> list[tuple[str, int]]:
    out: list[tuple[str, int]] = []
    for s in series:
        v = s.values
        same = np.zeros(len(v), dtype=bool)
        same[1:] = (np.diff(v) == 0) & ~np.isnan(v[1:])
        hits = _first_of_runs(same, start, hours)
        if hits:
            out.append((s.ts_id, hits[0]))
    return out


def grafana_dashboard(site: str, cfg: dict) -> dict:
    """The operations view handed over at go-live: one panel per SLA, thresholds from config."""
    sla = cfg["sla_hours"]
    panels: list[dict[str, Any]] = [
        {
            "title": "Series silent per unit (hours)",
            "type": "timeseries",
            "fieldConfig": {
                "defaults": {
                    "thresholds": {
                        "steps": [
                            {"color": "green", "value": None},
                            {"color": "red", "value": cfg["freshness_sla_hours"]},
                        ]
                    }
                }
            },
            "targets": [{"expr": f'igo_unit_silent_hours{{site="{site}"}}'}],
        },
        {"title": "Flatlined series", "type": "stat", "targets": [{"expr": f'igo_flatlined_series{{site="{site}"}}'}]},
        {
            "title": "Series waiting for a link",
            "type": "stat",
            "targets": [{"expr": f'igo_unlinked_series{{site="{site}"}}'}],
        },
        {
            "title": "Review queue age (hours)",
            "type": "timeseries",
            "targets": [{"expr": f'igo_review_oldest_hours{{site="{site}"}}'}],
        },
        {
            "title": "Early warnings, last 7 days",
            "type": "table",
            "targets": [{"expr": f'igo_vibration_warnings{{site="{site}"}}'}],
        },
    ]
    return {
        "title": f"{site}: industrial graph operations",
        "uid": f"igo-{site}",
        "tags": ["igo", "sla"],
        "annotations": {"list": [{"name": k, "sla_hours": v} for k, v in sla.items()]},
        "panels": [
            {**p, "id": i + 1, "gridPos": {"x": (i % 2) * 12, "y": (i // 2) * 8, "w": 12, "h": 8}}
            for i, p in enumerate(panels)
        ],
        "schemaVersion": 39,
    }
