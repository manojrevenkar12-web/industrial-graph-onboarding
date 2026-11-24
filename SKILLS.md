# SKILLS.md

Repeatable tasks, each a short recipe.

## Onboard a new site
1. Copy `config/sites/plant.yml` to `config/sites/<site>.yml`; write the historian name patterns, the functional
   location pattern, equipment codes, measurement fits and typical ranges from the discovery workshop.
2. Run the grammar tests against a sample export (`tests/test_tags.py` pattern); every pattern must refuse what it
   cannot parse.
3. `igo plan --db <site>.sqlite` and review the counts; `igo apply` writes them. Applying twice must change nothing.

## Tune matching
Change only `config/platform.yml: matching`. Rerun `igo run dev && igo gate dev`. A change that raises auto-links
but costs one wrong link is a regression: precision is the gate.

## Add a data-quality check
Add it to `src/igo/platform/quality.py` with a planted fault in `src/igo/world/plant.py` (and its truth), a metric
in `src/igo/lab/simulate.py:score`, a column in the report, and a test for both the fix and the refusal.

## Add an agent tool
Add it to `src/igo/platform/mcp_server.py` (`TOOLS` and `Server.call`) and `src/igo/platform/agent.py`. Every tool
filters to the caller's units and returns the ids it used. Add a test with a user outside the unit.

## Use a real model
`ClaudeReader(api_key)` or `OpenAICompatibleReader(base_url, api_key, model)` from `igo.platform.readers` replace
`SimReader` anywhere a reader is passed. The checks stay the same.
