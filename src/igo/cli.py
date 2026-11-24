"""igo command line.

igo run dev | heldout        every design on the development plants, or once on the held-out plants (locked)
igo gate dev | heldout       exit 1 when a gate fails
igo report                   README block, REPORT.md, console data, Grafana dashboard
igo plan [--db PATH]         onboard the demo plant and show what would change in the graph store
igo apply [--db PATH]        write the difference; applying twice changes nothing
igo mcp                      serve the demo plant's graph over MCP on stdio (identity from IGO_USER)
"""

from __future__ import annotations

import argparse
import json
import sys

from igo.config import load


def _demo_view():
    from igo.lab import simulate

    seed = load("seeds")["dev"][0]
    st = simulate.onboard("dev", seed, "platform", simulate.designs()["platform"])
    return st["view"], st["g"]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="igo")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("world", choices=["dev", "heldout"])
    r.add_argument("--workers", type=int, default=2)
    gt = sub.add_parser("gate")
    gt.add_argument("world", choices=["dev", "heldout"])
    sub.add_parser("report")
    for c in ("plan", "apply"):
        sp = sub.add_parser(c)
        sp.add_argument("--db", default="graph.sqlite")
    sub.add_parser("mcp")
    a = ap.parse_args(argv)

    if a.cmd == "run":
        from igo.lab import study

        print("wrote", study.run_dev(a.workers) if a.world == "dev" else study.run_heldout(a.workers))
        return 0
    if a.cmd == "gate":
        from igo.lab import study

        data = json.loads((study.REPORTS / f"{a.world}.json").read_text())
        for x in data["gates"]:
            print(("PASS " if x["pass"] else "FAIL ") + f"{x['gate']}: {x['value']:.4g} {x['op']} {x['limit']}")
        return 0 if all(x["pass"] for x in data["gates"]) else 1
    if a.cmd == "report":
        from igo.lab import report

        report.write_all()
        return 0
    if a.cmd in ("plan", "apply"):
        from igo.platform.graph import Store

        view, _ = _demo_view()
        store = Store(a.db)
        if a.cmd == "plan":
            p = store.plan(view.spec())
            print(json.dumps({t: {k: len(v) for k, v in p[t].items()} for t in p}, indent=1))
        else:
            print(json.dumps(store.apply(view.spec()), indent=1))
        return 0
    from igo.platform.mcp_server import serve

    view, g = _demo_view()
    serve(view, g)
    return 0


if __name__ == "__main__":
    sys.exit(main())
