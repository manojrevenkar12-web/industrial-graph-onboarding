# industrial-graph-onboarding

<!-- results:start -->

_Generated from `reports/*.json` by `igo report`; do not edit by hand._

**Development plants** (seeds [11, 12, 13]; 604 historian series, 169 machines, 240 agent questions)

| Design | Series on the right machine | Wrong links | Engineer hours to go-live | Go-live (days) | Duplicate records merged | Work orders on the right machine | Incidents caught in SLA | Failures warned 2-21 days ahead | Agent answers right | Answers outside the user's units |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Manual onboarding: a spreadsheet lookup for standard names, an engineer maps the rest by hand | 93.0% | 4 | 8.7 | 4.0 | 0 of 11 | 88.6% | 0% | 35 of 41 | 92.1% | 0 |
| Fuzzy name matching, accepted without review | 84.6% | 8 | 0.0 | 0.0 | 0 of 11 | 88.6% | 96% | 30 of 41 | 80.0% | 0 |
| A model reads names and descriptions and links them; agent without checks | 81.5% | 97 | 0.0 | 0.0 | 0 of 11 | 88.6% | 100% | 29 of 41 | 59.6% | 25 |
| **industrial-graph-onboarding** | 100.0% | 0 | 0.8 | 1.0 | 10 of 11 | 97.6% | 100% | 38 of 41 | 98.3% | 0 |

Gates: all 9 pass.

Manual onboarding also costs the engineer 16.0 hours per plant answering the same 80 questions by hand; the agent answers them from the graph.

**Each safeguard removed on its own** (development plants)

| Design | Series on the right machine | Wrong links | Engineer hours to go-live | Go-live (days) | Duplicate records merged | Work orders on the right machine | Incidents caught in SLA | Failures warned 2-21 days ahead | Agent answers right | Answers outside the user's units |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Without signal correlation | 99.8% | 1 | 2.6 | 1.7 | 10 of 11 | 97.6% | 100% | 38 of 41 | 97.9% | 0 |
| Without the P&ID tag list | 99.8% | 1 | 2.8 | 2.0 | 10 of 11 | 97.6% | 100% | 38 of 41 | 97.9% | 0 |
| Best candidate accepted, no engineer review | 98.7% | 1 | 0.0 | 0.0 | 4 of 11 | 90.6% | 100% | 38 of 41 | 96.2% | 0 |
| Without duplicate, rename, unit and work-order checks | 100.0% | 0 | 0.7 | 1.0 | 0 of 11 | 88.6% | 100% | 38 of 41 | 95.4% | 0 |
| Agent without permission and citation checks | 100.0% | 0 | 0.8 | 1.0 | 10 of 11 | 97.6% | 100% | 38 of 41 | 80.8% | 25 |

| What the checks found (all plants) | Fixed, of planted | Fixed wrongly |
|---|---:|---:|
| Duplicate equipment records in SAP PM, merged into one machine | 10 of 11 | 0 |
| Historian tags renamed, old and new joined as one sensor | 46 of 47 | 0 |
| Pressures stored in kPa but declared as bar, converted | 6 of 6 | 0 |
| Work orders booked on the wrong machine, moved to the right one | 23 of 29 | 0 |

<!-- results:end -->
