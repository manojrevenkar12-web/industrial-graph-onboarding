# 0001 A simulated plant that keeps its truth

## Context
Onboarding quality is only measurable against the truth: which machine each sensor sits on, which master records are
one machine, which work orders were booked wrongly. Real customer data never comes with that truth.

## Decision
`src/igo/world/` simulates a process plant: units of pumps (60% as duty/standby pairs), compressors, exchangers,
vessels and fans; sensors whose signals follow each machine's starts, stops and load; failures preceded by rising
vibration. It writes the three exports a site hands over and plants the faults onboarding meets: three historian
naming formats, independent loop numbers, generic and German descriptions, internal-id tags, renamed tags, kPa
declared as bar, duplicate equipment records, misbooked work orders, OCR noise in the P&ID list, and incidents after
go-live. The platform never imports the world (a test enforces it).

## Consequences
Every design is scored against the same truth with the same luck. The plant is a model of a plant; the limits are
in the README.
