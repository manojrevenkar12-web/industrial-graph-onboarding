import numpy as np

from igo.config import load
from igo.platform import quality
from igo.platform.tags import Grammar
from igo.sources import Series, WorkOrder

g = Grammar()
cfg = load("platform")["quality"]


def _pair(new_name):
    v = np.linspace(5, 6, 500) + np.random.default_rng(0).normal(0, 0.01, 500)
    old = Series("A", "21PT2103A.PV", "x", "bar", v.copy())
    old.values[300:] = np.nan
    new = Series("B", new_name, "x", "bar", v.copy())
    new.values[:300] = np.nan
    return old, new


class Yes:
    def same_sensor(self, old, new):
        return True

    def work_order(self, wo_id, proposed):
        return proposed


def test_rename_same_loop_joins_without_a_person():
    old, new = _pair("U21_PT_2103A_PV")
    found = quality.find_rename(new, [old], g, cfg, None)
    assert found is not None and found.how == "auto"


def test_rename_to_internal_id_needs_the_engineer():
    old, new = _pair("TAG_555555")
    assert quality.find_rename(new, [old], g, cfg, None) is None
    found = quality.find_rename(new, [old], g, cfg, Yes())
    assert found is not None and found.how == "review"


def test_kpa_declared_as_bar_is_converted():
    s = Series("A", "21PT2103A.PV", "x", "bar", np.full(100, 620.0))
    assert quality.unit_factor(s, g) == 100.0
    s.values[:] = 6.2
    assert quality.unit_factor(s, g) == 1.0


def test_work_order_moves_only_on_a_quoted_tag(onboarded):
    view = onboarded["view"]
    md = view.md
    a, b = sorted(md.by_key, key=str)[:2]
    wo = WorkOrder("W1", md.machines[md.by_key[a]].records[0], 100, "preventive", f"PM inspection {b}")
    link = quality.relink_work_order(wo, md, g, None, Yes(), lambda c, d: None)
    assert link.canon == md.by_key[b] and link.how == "review"
    wo2 = WorkOrder("W2", wo.sap_id, 100, "preventive", "PM inspection")
    assert quality.relink_work_order(wo2, md, g, None, Yes(), lambda c, d: None).how == "booked"
