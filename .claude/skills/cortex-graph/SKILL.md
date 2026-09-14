---
name: cortex-graph
description: Query and write to the cortex knowledge graph via the ~/.cortex/concepts CLI. Use when looking up a concept's history or edges, finding concepts shared across projects, checking which concepts are hot or stale, pulling a session brief, auditing capture health, or when explicitly asked to add a concept or edge to the graph.
---

# Cortex Knowledge Graph

Access via `~/.cortex/concepts`. Always pass `--root <workspace-root>` to anchor to the workspace (the directory that holds `concepts.db`).

## Read commands (safe, use freely)

- `~/.cortex/concepts --root <workspace-root> graph` graph summary
- `~/.cortex/concepts --root <workspace-root> --json hot --limit 10` most active concepts
- `~/.cortex/concepts --root <workspace-root> --json shared` concepts spanning 2+ projects
- `~/.cortex/concepts --root <workspace-root> --json query <name>` concept detail with edges
- `~/.cortex/concepts --root <workspace-root> brief` session context brief
- `~/.cortex/concepts --root <workspace-root> --json sessions --limit 5` recent sessions
- `~/.cortex/concepts --root <workspace-root> --json capture-health` tracking health

## When to query

- Before starting work: run `brief` to see active projects and pending items. Note that the `SessionStart` hook already injects `cortex-brief.md`, so this is only needed for a fresher read
- When a concept comes up: run `query <name>` to see its history and connections
- When looking for patterns: run `shared` or `hot` to find cross-project concepts

All read commands support `--json` for structured output. Prefer `--json` when reasoning over the data. `--json` must precede the subcommand.

## Write commands (use only when asked)

- `~/.cortex/concepts --root <workspace-root> upsert <name> --kind <kind> --project <project>` create or update a concept
- `~/.cortex/concepts --root <workspace-root> edge <from> <to> <relation>` create or strengthen an edge

Do not write to the graph unless explicitly asked. Reads are safe and encouraged.
