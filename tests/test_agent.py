from igo.platform import agent


class Fixed:
    def __init__(self, reading):
        self.reading = reading

    def read_question(self, text, key):
        return dict(self.reading)


def _ask(onboarded, text, reading, units, checked=True):
    st = onboarded
    return agent.answer("Q", text, units, st["view"], st["g"], Fixed(reading), checked, 0.12, 179)


def _some_machine(onboarded):
    view = onboarded["view"]
    k, c = next((k, c) for k, c in sorted(view.md.by_key.items(), key=lambda x: str(x[0])) if view.sensors(c))
    return k, c, view.machine_unit(c)


def test_answers_inside_the_users_units(onboarded):
    k, _c, unit = _some_machine(onboarded)
    a = _ask(onboarded, f"Which sensors are installed on {k}?", {"intent": "sensors", "entity": str(k)}, [unit])
    assert a.value and not a.refused
    assert all(x.startswith("ts:") for x in a.cited)


def test_refuses_outside_the_users_units(onboarded):
    k, _c, _unit = _some_machine(onboarded)
    a = _ask(onboarded, f"Which sensors are installed on {k}?", {"intent": "sensors", "entity": str(k)}, [99])
    assert a.refused and a.value is None


def test_unguarded_leaks(onboarded):
    k, _c, _unit = _some_machine(onboarded)
    a = _ask(
        onboarded, f"Which sensors are installed on {k}?", {"intent": "sensors", "entity": str(k)}, [99], checked=False
    )
    assert not a.refused and a.value


def test_a_misread_tag_is_not_answered(onboarded):
    k, _c, _unit = _some_machine(onboarded)
    wrong = str(k)[:-1] + ("9" if not str(k).endswith("9") else "8")
    a = _ask(onboarded, f"Which sensors are installed on {k}?", {"intent": "sensors", "entity": wrong}, "all")
    assert a.declined


def test_an_intent_the_question_does_not_support_is_not_answered(onboarded):
    k, _c, _unit = _some_machine(onboarded)
    a = _ask(onboarded, f"Which sensors are installed on {k}?", {"intent": "vibration_trend", "entity": str(k)}, "all")
    assert a.declined
