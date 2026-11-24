# 0005 Operations after go-live; where visualization and transformation run

## Decision: operations
- Unit freshness: all live series of a unit silent for 2 hours pages the OT on-call (SLA 4 h).
- Flatline: 24 identical readings raise a ticket to the instrument technician (SLA 24 h).
- Coverage: a daily check contextualizes new series, so a tag renamed after go-live is linked within a day (SLA 24 h).
- Early warnings from rising running vibration go to reliability engineering.
Owners, response times and change control are in `docs/RUNBOOK.md`; `deploy/grafana/igo-operations.json` carries
the thresholds from config.

## Decision: visualization
- **Grafana** for operations (freshness, flatlines, review queue, warnings): time series, alerting, the OT team's
  tool.
- **Power BI** for management reporting (work orders per machine, MTBF, onboarding progress) where the customer's
  business reporting already lives.
- **Plotly Dash** for engineering analysis apps that need Python (signal inspection during review), not for
  dashboards that must be maintained by the customer.

## Decision: transformation
Light, per-site transformations (grammar, units, matching) run where the graph lives, as configuration. Heavy
historical backfills and cross-site analytics run on Databricks (or the customer's cloud warehouse) and write back
through the same spec, so there is one path into the graph.
