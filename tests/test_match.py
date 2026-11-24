def test_every_link_is_right(onboarded, plant):
    view = onboarded["view"]
    for t, d in view.decisions.items():
        if d.canon is not None:
            assert plant.sap_owner[d.canon] == plant.sensors[plant.ts_sensor[t]].eid, t


def test_most_links_need_no_person(onboarded):
    hows = [d.how for d in onboarded["view"].decisions.values()]
    assert hows.count("auto") / len(hows) > 0.8


def test_review_items_carry_their_evidence(onboarded):
    reviewed = [d for d in onboarded["view"].decisions.values() if d.how == "review" and d.candidates]
    assert reviewed
    assert all("evidence" in c for d in reviewed for c in d.candidates)


def test_signal_places_an_unnamed_series(onboarded, plant):
    view = onboarded["view"]
    hits = [
        d
        for t, d in view.decisions.items()
        if view.series[t].name.startswith("TAG_")
        and d.how == "auto"
        and d.candidates
        and "signal" in d.candidates[0]["evidence"]
    ]
    assert hits
