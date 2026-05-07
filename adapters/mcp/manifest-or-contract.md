# MCP Adapter Contract

MCP support should expose the same workflow contracts without becoming the source of truth.

Initial read tools:

- read workflow contract
- collect workflow context
- read graph summary

Future write tools:

- capture session
- upsert concept
- add edge
- promote concept
- dismiss signal

All writes should go through serialized Cortex CLI/API behavior to avoid graph write races.
