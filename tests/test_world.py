import numpy as np

from igo.world.plant import simulate


def test_same_seed_same_plant():
    a, b = simulate(11), simulate(11)
    assert [s.name for s in a.exports.series] == [s.name for s in b.exports.series]
    assert np.allclose(a.exports.series[3].values, b.exports.series[3].values, equal_nan=True)


def test_truth_covers_every_export(plant):
    x = plant.exports
    assert all(s.ts_id in plant.ts_sensor for s in x.series)
    assert all(w.wo_id in plant.wo_true for w in x.work_orders)
    assert all(r.sap_id in plant.sap_owner for r in x.equipment)


def test_duty_and_standby_pumps_take_turns(plant):
    pairs = [e for e in plant.equipment.values() if e.pair and e.number.endswith("A")]
    assert pairs
    e = pairs[0]
    current = [s for s in plant.sensors.values() if s.mtype == "IT"]
    a = next((s for s in current if s.eid == e.eid), None)
    b = next((s for s in current if s.eid == e.pair), None)
    if a and b:
        va = next(x for x in plant.exports.series if plant.ts_sensor[x.ts_id] == a.sid).values
        vb = next(x for x in plant.exports.series if plant.ts_sensor[x.ts_id] == b.sid).values
        ok = ~(np.isnan(va) | np.isnan(vb))
        assert np.corrcoef(va[ok], vb[ok])[0, 1] < -0.5


def test_faults_are_planted(plant):
    assert plant.renamed
    assert any(len(e.sap_ids) > 1 for e in plant.equipment.values())
    assert any(plant.exports.series_by_id()[t].name.startswith("TAG_") for t in plant.ts_sensor)
    assert {i["kind"] for i in plant.incidents} == {"extractor_outage", "rename_after_golive", "flatline"}


def test_heldout_is_a_different_site():
    h = simulate(111, "heldout")
    assert {e.unit for e in h.equipment.values()} == {41, 42, 43, 51, 52, 53}
