# Runbook and support agreement

Agreed at go-live between the customer's OT team, the customer's IT, the reliability engineers and the platform
team. Thresholds come from `config/platform.yml: monitoring`.

| Alert | Detected by | Owner (responsible) | Accountable | Response | Resolve within |
|---|---|---|---|---|---|
| Unit silent 2 h (extractor or network) | freshness check, hourly | Customer OT on-call | OT lead | Acknowledge 30 min | 4 h |
| Series flatlined 24 h | flatline check | Instrument technician | Maintenance planner | Next working day | 3 working days |
| New series not linked | daily coverage check | Plant engineer (review queue) | Platform team | Review within 24 h | 24 h |
| Review queue older than 48 h | review queue age | Platform team | Solution architect | Escalate to site lead | 48 h |
| Early warning: vibration rising | warning check, daily | Reliability engineer | Maintenance manager | Inspect within 2 days | Planned work order |
| Agent refused or declined | agent log | Platform team | Solution architect | Weekly review | Next release |

## Change control
- Site grammar, thresholds and users change by pull request; CI runs `igo plan` and the gates; `igo apply` runs on
  merge. A change that adds one wrong link on the development plants does not merge.
- The engineer's review decisions are kept; re-onboarding asks only about what is new.
- Model or prompt changes run the full study before release; the held-out plants are never rerun.

## Support levels
- P1 (whole unit silent, agent answering outside scope): 30 min, 24/7, OT on-call and platform team.
- P2 (series flatlined, review queue stalled): next working day.
- P3 (agent declines, dashboard requests): weekly triage.
