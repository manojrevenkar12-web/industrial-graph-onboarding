from igo.platform.tags import EquipmentKey, Grammar

g = Grammar()


def test_three_historian_formats():
    for name in ("21PT2103A.PV", "21-PT-2103A", "U21_PT_2103A_PV"):
        k = g.parse_name(name)
        assert k is not None and (k.unit, k.mtype, k.loop) == (21, "PT", "2103A")
    assert g.parse_name("TAG_123456") is None


def test_floc_and_text_tags():
    assert g.parse_floc("PLT1-21-P-2103A") == EquipmentKey("P", "2103A")
    assert g.parse_floc("PLT1-21-P-2103/A") is None
    assert g.tags_in("seal leaking on P2103A") == [EquipmentKey("P", "2103A")]


def test_model_quotes_in_any_wording():
    assert g.normalize_mention("Pumpe 2103A") == EquipmentKey("P", "2103A")
    assert g.normalize_mention("pump 2103 A") == EquipmentKey("P", "2103A")
    assert g.normalize_mention("Wärmetauscher 2102") == EquipmentKey("E", "2102")
    assert g.normalize_mention("the big pump") is None


def test_ocr_repairs_only_when_they_parse():
    assert g.pid_equipment("P-23O9B") == EquipmentKey("P", "2309B")
    assert g.pid_instrument("PT2101") == ("PT", "2101")
    assert g.pid_instrument("PT-I1O1") == ("PT", "1101")
    assert g.pid_equipment("PUMP") is None


def test_measurement_fits():
    assert g.fits("V", "LT") and not g.fits("V", "VT")
