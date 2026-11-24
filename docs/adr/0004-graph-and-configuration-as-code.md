# 0004 The graph data model, and onboarding as configuration

## Decision
One model for every site: Unit, Machine, TimeSeries, WorkOrder, Record (alias). Site differences live in
`config/sites/<site>.yml` only. Onboarding produces a spec keyed by external ids; `igo plan` diffs it against the
store and `igo apply` writes only the difference, so CI can run plan on every pull request and apply on merge.
Applying the same spec twice changes nothing (tested, and measured in every study run).

## Consequences
A new site is a configuration change reviewed like code, not a project-specific script. The store here is SQLite;
the same spec maps onto a managed graph (data modeling views and edges) without changing the onboarding logic.
