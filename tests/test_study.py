import json

import pytest

from igo.lab import study


def test_heldout_runs_once(tmp_path, monkeypatch):
    monkeypatch.setattr(study, "REPORTS", tmp_path)
    monkeypatch.setattr(study, "LOCK", tmp_path / "heldout.lock")
    (tmp_path / "heldout.lock").write_text(json.dumps({"seeds": [1]}))
    with pytest.raises(SystemExit) as e:
        study.run_heldout()
    assert e.value.code == 3


def test_gates_read_the_platform_row():
    dev = json.loads((study.REPORTS / "dev.json").read_text())
    gates = study.judge(dev)
    assert [g["gate"] for g in gates] == [g["gate"] for g in dev["gates"]]


def test_the_platform_never_imports_the_world():
    for p in (study.ROOT / "src" / "igo" / "platform").glob("*.py"):
        assert "igo.world" not in p.read_text(), p.name
