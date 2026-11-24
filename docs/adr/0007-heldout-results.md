# 0007 Held-out results, run once

The held-out plants (seeds 111 and 112, another site with units 41-53, more independent loop numbers, more German,
error rates x1.4) ran once on 2026-11-24 after the code and gates were committed (`reports/heldout.lock`).

**All 9 gates passed.** 0 wrong links out of 542 series; engineer onboarding 2.2 hours against 14.9 by hand (go-live
after 1 day against 6.5); 14 of 15 duplicates merged; 95.9% of work orders on the right machine against 76.6%; all 18
incidents caught within their SLA; 26 of 29 failures warned 2-21 days ahead.

## Found after the run
The users in `config/platform.yml` name development-plant units (21, 22, 23, 31, 32). On the held-out site three of
the four users therefore had no units, and only 30 of 160 held-out questions were inside the asker's units. The
held-out agent rate (98.1%) mostly measures correct refusals; the model-alone agent's 120 leaks are answers to users
with no units there. The run was not repeated. A future held-out world should carry its own user list; that needs
new seeds and this ADR's successor.
