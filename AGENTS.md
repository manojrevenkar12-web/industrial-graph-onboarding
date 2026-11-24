# AGENTS.md

How to work in this repository, for people and coding agents alike.

## Fast feedback

```bash
pip install -e ".[dev]"
pytest -q                      # ~2 s
ruff check . && ruff format --check . && mypy src
igo run dev && igo gate dev    # every design on the 3 development plants, ~15 s
igo report                     # README block, REPORT.md, console data, Grafana dashboard
cd web && npm ci && npm test && npm run typecheck && npm run lint && npm run build
```

## Invariants

1. **The truth stays in the world.** `src/igo/world/` simulates the plant and keeps the truth (which machine each
   sensor is on, which records are one machine, which work orders were booked wrongly, when machines fail).
   `src/igo/platform/` never imports it (a test enforces this); it sees only `igo.sources.Exports`.
2. **The world does not read the platform's settings.** `config/world.yml` is the world's; `config/platform.yml`,
   `config/sites/*.yml` and `config/designs.yml` are the platform's. The world never reads them, except the user
   list, which both share as fact.
3. **Same luck for every design.** The simulated model and the engineer draw their luck from (seed, purpose, key),
   so every design meets the same misreads, the same review slips and the same incidents.
4. **The model reads and code decides.** A model only returns words from a text. Code keeps a quote only if it is
   in the text and parses with the site grammar; links, merges, relinks, permissions and answers are computed by
   code from the graph.
5. **A name never decides.** A link needs a parsed loop number, a P&ID connection, a quoted description or the
   signal, scored together; when the best machine is not far ahead, the engineer decides.
6. **The caller's units come from identity, never from a tool argument** (agent and MCP server).
7. **Settings in config.** Thresholds, weights, review minutes, SLAs and users live in `config/`. Code has none.
8. **Generated reports.** `README.md` between the results markers, `REPORT.md`, `web/public/data/report.json`
   and `deploy/grafana/` are written by `igo report`; never edit them by hand. CI regenerates and diffs them.

## The held-out rule

The held-out plants (`config/seeds.yml: heldout`, `config/world.yml: heldout`) run **once**, after the code and the
gates (`config/gates.yml`) are committed. `igo run heldout` writes `reports/heldout.lock`; a second run exits with
code 3. Results are published as they came out. New evidence needs new seeds and an ADR, never a rerun.
