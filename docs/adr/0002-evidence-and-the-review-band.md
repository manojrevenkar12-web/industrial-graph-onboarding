# 0002 Evidence per candidate, automatic only when far ahead

## Context
A wrong link is worse than no link: alarms land on the wrong machine, a work order history lies, the agent answers
confidently and wrongly. Engineers' time is the scarce resource during onboarding.

## Decision
Each candidate machine collects evidence (parsed loop number, P&ID connection, quoted description, centred signal
correlation, type misfit), each with a weight in `config/platform.yml`. A link is automatic when the best machine's
probability is at least 0.97 **and** it leads the runner-up by 4 log-odds; otherwise the engineer picks from the
candidates with their evidence (3 minutes), or maps by hand when nothing is plausible (4 minutes).

Signal is centred on the unit's median correlation and only supports: every machine in a unit follows the unit's
load, so raw correlation raises all candidates alike. Measured in development: the first version scored signal
raw and penalised, and sent 111 items to review on one plant; centred and supportive, 15.

## Consequences
On the development plants 0 wrong links out of 604 series with 15% of manual onboarding time; held out, 0 of 542
with 15%. Without the signal, reviews roughly triple; without the P&ID list, the same.
