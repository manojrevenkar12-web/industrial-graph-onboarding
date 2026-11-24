# 0006 The maintenance agent and the MCP server

## Decision
The model reads the question into an intent and the words that name the machine. Code then checks:
- the intent's cue words are in the question, and the quoted words are in the question and parse with the site
  grammar; if not, it asks the model once more, then asks the user to name the machine;
- the machine is inside the caller's units, which come from identity (the agent's user, `IGO_USER` for MCP), never
  from a tool argument;
- the answer is computed from the graph and cites the ids it used.

## Consequences
Development: 98.3% of 240 questions answered right, 0 answers outside the asker's units. Without these checks, the
same graph answered 80.8% right and showed 25 answers outside the asker's units.
