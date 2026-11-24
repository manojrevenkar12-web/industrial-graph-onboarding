import json

import pytest

from igo.platform.mcp_server import Server


def test_handshake_and_tools(onboarded):
    s = Server(onboarded["view"], onboarded["g"], "site_manager")
    assert s.handle({"jsonrpc": "2.0", "id": 1, "method": "initialize"})["result"]["serverInfo"]["name"]
    names = [t["name"] for t in s.handle({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})["result"]["tools"]]
    assert {"find_machine", "list_sensors", "work_orders", "vibration_trend"} <= set(names)
    assert s.handle({"jsonrpc": "2.0", "method": "notifications/initialized"}) is None


def _call(s, name, args):
    r = s.handle({"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": name, "arguments": args}})
    return json.loads(r["result"]["content"][0]["text"])


def test_identity_bounds_every_tool(onboarded):
    view = onboarded["view"]
    canon = next(c for c in sorted(view.md.machines) if view.machine_unit(c) == 21 and view.sensors(c))
    tag = str(view.md.machines[canon].key)
    inside = Server(view, onboarded["g"], "ops_lead_21")
    outside = Server(view, onboarded["g"], "reliability_31")
    assert _call(inside, "find_machine", {"tag": tag})["machine"] == canon
    assert _call(inside, "list_sensors", {"machine": canon})["series"]
    assert _call(outside, "find_machine", {"tag": tag}) == {"found": False}
    assert "error" in _call(outside, "list_sensors", {"machine": canon})


def test_unknown_user_is_refused(onboarded):
    with pytest.raises(ValueError):
        Server(onboarded["view"], onboarded["g"], "someone")
