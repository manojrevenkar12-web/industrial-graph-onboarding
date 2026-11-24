"""What the customer's source systems hand over: a historian, SAP PM and a P&ID tag list.

The world writes these; the platform reads only these. Nothing here says which machine a series belongs to.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


@dataclass
class Series:
    ts_id: str  # the historian's internal id
    name: str
    description: str
    unit: str  # as declared in the historian
    values: np.ndarray  # hourly, NaN where the historian has nothing


@dataclass
class EquipmentRecord:
    sap_id: str
    floc: str
    description: str
    cls_text: str


@dataclass
class WorkOrder:
    wo_id: str
    sap_id: str  # the equipment it was booked on
    day: int
    kind: str  # corrective | preventive
    text: str


@dataclass
class PidRow:
    drawing: str
    instrument: str
    equipment: str


@dataclass
class Question:
    q_id: str
    user: str
    text: str
    day: int


@dataclass
class Exports:
    site: str
    hours: int
    backfill_hours: int
    series: list[Series]
    equipment: list[EquipmentRecord]
    work_orders: list[WorkOrder]
    pid: list[PidRow]
    questions: list[Question] = field(default_factory=list)

    def series_by_id(self) -> dict[str, Series]:
        return {s.ts_id: s for s in self.series}
