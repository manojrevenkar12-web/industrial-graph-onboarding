"""A maintenance agent over the graph. The model reads the question; code finds the machine, checks the user may see
it, computes the answer from the graph and cites the ids it used.

Checked (the platform): the words the model says name the machine must be in the question and parse with the site
grammar, or the agent asks again once and then asks the user; every tool call is filtered to the user's units.
Unguarded (model alone): the model's reading is used as is and the tools see the whole plant.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from igo.platform.graph import GraphView
from igo.platform.tags import Grammar

CUES = {  # words a question must contain for the model's reading of its intent to stand
    "sensors": ("sensor",),
    "last_corrective": ("last", "work order"),
    "vibration_trend": ("vibration",),
    "most_corrective": ("most", "work order"),
}


def intent_holds(intent: object, text: str) -> bool:
    low = text.lower()
    return isinstance(intent, str) and intent in CUES and all(c in low for c in CUES[intent])


class Reader(Protocol):
    def read_question(self, text: str, key: str) -> dict: ...


@dataclass
class Answer:
    q_id: str
    kind: str
    value: object = None
    refused: bool = False  # outside the user's units
    declined: bool = False  # the machine could not be identified; the user is asked to name it
    cited: list[str] = field(default_factory=list)
    model_calls: int = 0


def answer(
    q_id: str,
    text: str,
    units: list[int] | str,
    view: GraphView,
    g: Grammar,
    reader: Reader,
    checked: bool,
    slope: float,
    day: int,
) -> Answer:
    calls = 0
    reading: dict = {}
    for attempt in range(2 if checked else 1):
        reading = reader.read_question(text, f"{q_id}:{attempt}")
        calls += 1
        if not checked:
            break
        if not intent_holds(reading.get("intent"), text):
            continue
        if reading.get("intent") == "most_corrective":
            break
        q = reading.get("entity")
        if q and q in text and g.normalize_mention(q) is not None:
            break
    if checked and not intent_holds(reading.get("intent"), text):
        return Answer(q_id, str(reading.get("intent")), declined=True, model_calls=calls)
    kind = str(reading.get("intent"))
    allowed = (lambda u: True) if (units == "all" or not checked) else (lambda u: u in units)

    if kind == "most_corrective":
        unit = reading.get("unit")
        if unit is None:
            return Answer(q_id, kind, declined=True, model_calls=calls)
        if not allowed(unit):
            return Answer(q_id, kind, refused=True, model_calls=calls)
        counts = {
            c: sum(1 for w in view.work_orders_on(c) if w.kind == "corrective" and w.day <= day)
            for c in view.machines_in(unit)
        }
        if not counts:
            return Answer(q_id, kind, None, model_calls=calls)
        best = sorted(counts, key=lambda c: (-counts[c], c))[0]
        return Answer(q_id, kind, best, cited=[f"machine:{best}"], model_calls=calls)

    q = reading.get("entity")
    if not q:
        return Answer(q_id, kind, declined=True, model_calls=calls)
    if checked and q not in text:
        return Answer(q_id, kind, declined=True, model_calls=calls)
    key = g.normalize_mention(q)
    canon = view.md.by_key.get(key) if key else None
    if canon is None:
        return Answer(q_id, kind, declined=True, model_calls=calls)
    unit = view.machine_unit(canon)
    if unit is None or not allowed(unit):
        return Answer(q_id, kind, refused=True, model_calls=calls)
    if kind == "sensors":
        ts = view.sensors(canon)
        return Answer(q_id, kind, ts, cited=[f"ts:{t}" for t in ts], model_calls=calls)
    if kind == "last_corrective":
        days = [w.day for w in view.work_orders_on(canon) if w.kind == "corrective" and w.day <= day]
        return Answer(q_id, kind, max(days) if days else None, cited=[f"machine:{canon}"], model_calls=calls)
    if kind == "vibration_trend":
        return Answer(q_id, kind, view.vib_rising(canon, day, slope), cited=[f"machine:{canon}"], model_calls=calls)
    return Answer(q_id, kind, declined=True, model_calls=calls)
