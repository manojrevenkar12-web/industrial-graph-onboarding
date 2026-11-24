from igo.platform.graph import Store


def test_apply_twice_changes_nothing(onboarded, tmp_path):
    spec = onboarded["view"].spec()
    st = Store(tmp_path / "g.sqlite")
    first = st.apply(spec)
    assert first["nodes"]["create"] > 100
    again = st.apply(spec)
    assert sum(sum(v.values()) for v in again.values()) == 0


def test_plan_shows_deletes_and_updates(onboarded):
    spec = onboarded["view"].spec()
    st = Store()
    st.apply(spec)
    smaller = {"nodes": dict(spec["nodes"]), "edges": dict(spec["edges"])}
    gone = next(iter(smaller["edges"]))
    del smaller["edges"][gone]
    k = next(k for k in smaller["nodes"] if k.startswith("ts:"))
    smaller["nodes"][k] = {**smaller["nodes"][k], "link": "review"}
    p = st.plan(smaller)
    assert p["edges"]["delete"] == [gone]
    assert k in p["nodes"]["update"] or spec["nodes"][k]["link"] == "review"


def test_duplicates_stay_as_aliases(onboarded):
    spec = onboarded["view"].spec()
    assert any("|same_machine_as|" in e for e in spec["edges"])
