import numpy as np

from igo.platform import monitor
from igo.sources import Series


def test_run_lengths():
    f = np.array([0, 1, 1, 1, 0, 1, 1, 1, 1], bool)
    assert monitor._first_of_runs(f, 0, 3) == [3, 7]


def test_flatline_is_found_after_a_day():
    v = np.random.default_rng(0).normal(5, 1, 200)
    v[100:] = v[99]
    assert monitor.flatline_alerts([Series("A", "n", "d", "bar", v)], 0, 24) == [("A", 123)]


def test_silent_unit_is_found_within_the_sla():
    rng = np.random.default_rng(1)
    ss = [Series(str(i), "n", "d", "bar", rng.normal(5, 1, 300)) for i in range(4)]
    for s in ss:
        s.values[200:220] = np.nan
    assert monitor.freshness_alerts({21: ss}, 30, 2) == [(21, 201)]


def test_rising_vibration():
    days = 40
    v = np.tile(np.r_[np.zeros(4), np.ones(20) * 1.5], days)
    ramp = np.r_[np.zeros(30 * 24), np.linspace(0, 4, 10 * 24)]
    daily = monitor.running_daily(v + ramp * (v > 0))
    assert monitor.rising(daily, 39, 0.12) is True
    assert monitor.rising(daily, 25, 0.12) is False
