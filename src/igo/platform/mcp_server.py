"""An MCP server over the onboarded graph (JSON-RPC 2.0 on stdio), so any compliant agent can query it.

The caller's units come from the server's start-up identity (IGO_USER), never from tool arguments: a tool call
cannot widen what the user may see. Every result carries the graph ids it was computed from.
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any

from igo.config import load
from igo.platform.graph import GraphView
from igo.platform.tags import Grammar

TOOLS = [
    {
        "name": "find_machine",
        "description": "Resolve a machine tag (P-2103A, Pumpe 2103A) to its graph id.",
        "inputSchema": {"type": "object", "properties": {"tag": {"type": "string"}}, "required": ["tag"]},
    },
    {
        "name": "list_sensors",
        "description": "Time series measured on a machine.",
        "inputSchema": {"type": "object", "properties": {"machine": {"type": "string"}}, "required": ["machine"]},
    },
    {
        "name": "work_orders",
        "description": "Work orders on a machine, newest first.",
        "inputSchema": {"type": "object", "properties": {"machine": {"type": "string"}}, "required": ["machine"]},
    },
    {
        "name": "vibration_trend",
        "description": "Is running vibration rising into the given day?",
        "inputSchema": {
            "type": "object",
            "properties": {"machine": {"type": "string"}, "day": {"type": "integer"}},
            "required": ["machine", "day"],
        },
    },
]


class Server:
    def __init__(self, view: GraphView, g: Grammar, user: str):
        self.view, self.g = view, g
        users = {u["name"]: u["units"] for u in load("platform")["users"]}
        if user not in users:
            raise ValueError(f"unknown user {user!r}")
        self.units = users[user]
        self.slope = load("platform")["monitoring"]["vibration_slope_mm_s_per_day"]

    def _allowed(self, machine: str) -> bool:
        if machine not in self.view.md.machines:
            return False
        unit = self.view.machine_unit(machine)
        return self.units == "all" or (unit is not None and unit in self.units)

    def call(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        if name == "find_machine":
            key = self.g.normalize_mention(str(args.get("tag", "")))
            canon = self.view.md.by_key.get(key) if key else None
            if canon is None or not self._allowed(canon):
                return {"found": False}
            return {"found": True, "machine": canon, "tag": str(key), "cited": [f"machine:{canon}"]}
        machine = str(args.get("machine", ""))
        if not self._allowed(machine):
            return {"error": "not found or outside your units"}
        if name == "list_sensors":
            ts = self.view.sensors(machine)
            return {
                "series": [{"id": t, "name": self.view.series[t].name, "unit": self.view.series[t].unit} for t in ts],
                "cited": [f"ts:{t}" for t in ts],
            }
        if name == "work_orders":
            wos = sorted(self.view.work_orders_on(machine), key=lambda w: -w.day)
            return {
                "work_orders": [{"id": w.wo_id, "day": w.day, "kind": w.kind, "text": w.text} for w in wos],
                "cited": [f"wo:{w.wo_id}" for w in wos],
            }
        if name == "vibration_trend":
            return {
                "rising": self.view.vib_rising(machine, int(args.get("day", 0)), self.slope),
                "cited": [f"machine:{machine}"],
            }
        return {"error": f"unknown tool {name}"}

    def handle(self, msg: dict[str, Any]) -> dict[str, Any] | None:
        method, mid = msg.get("method"), msg.get("id")
        if method == "initialize":
            result: dict[str, Any] = {
                "protocolVersion": "2025-06-18",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "industrial-graph-onboarding", "version": "1.0.0"},
            }
        elif method == "tools/list":
            result = {"tools": TOOLS}
        elif method == "tools/call":
            p = msg.get("params", {})
            out = self.call(str(p.get("name")), dict(p.get("arguments") or {}))
            result = {"content": [{"type": "text", "text": json.dumps(out)}], "isError": "error" in out}
        elif mid is None:
            return None  # a notification
        else:
            return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": f"no method {method}"}}
        return {"jsonrpc": "2.0", "id": mid, "result": result}


def serve(view: GraphView, g: Grammar) -> None:  # pragma: no cover - exercised through Server.handle in tests
    server = Server(view, g, os.environ.get("IGO_USER", ""))
    for line in sys.stdin:
        if not line.strip():
            continue
        reply = server.handle(json.loads(line))
        if reply is not None:
            sys.stdout.write(json.dumps(reply) + "\n")
            sys.stdout.flush()
