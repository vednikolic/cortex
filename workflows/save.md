# Save Workflow Contract

Persist durable session learnings so future sessions can resume from outcomes, decisions, risks, and next actions.

## Inputs

- `<workspace-root>/.memory-config`, when present
- Current git status for changed files, when relevant
- Daily notes, project context files, project playbooks, personal learnings, and workspace memory files
- Cortex CLI reads, when available at `<concepts-command>`

## Modes

- `quick`: daily note only, plus a brief report
- `full`: daily note plus durable routing and signal scan
- `deep`: full mode plus explicit friction, risk, opportunity, and graph signal pass

Default to `full`.

## Procedure

1. Resolve workspace paths from `.memory-config`; otherwise use the workspace defaults documented by the local project.
2. Identify the project touched by the session from paths, current directory, and conversation context.
3. Inspect changed files with `git status --short` when useful. Do not revert unrelated changes.
4. Summarize durable signal:
   - work completed
   - decisions made and rationale
   - friction observed
   - reusable patterns proven
   - risks, opportunities, or convergence
   - unfinished work
5. Read destination files before editing so the save consolidates instead of duplicating.
6. Write the smallest durable update:
   - daily notes for concrete work and next actions
   - project context for state, decisions, and continuity rules
   - project playbooks for reusable execution patterns with proof
   - personal learnings for durable user operating preferences
   - workspace memory for cross-project patterns and tool behavior
7. In full or deep mode, run the signal pass.
8. Report what changed, what was intentionally skipped, and any follow-up risk.

## Signal Pass

Classify each candidate as one of:

- duplicate: already captured; skip or consolidate
- reinforcement: strengthens an existing rule or pattern
- contradiction: conflicts with saved context
- stale: saved context appears superseded
- violated preference: repeated miss against a saved preference
- friction recurrence: same friction appears at least twice
- opportunity: connection to a stated goal, another project, or reusable asset
- risk: dependency, date collision, drift, or unverified assumption
- convergence: multiple projects point at the same underlying need

Do not invent durable patterns from one weak mention.

## Optional Cortex Reads

When available, use graph reads to ground the signal pass:

```bash
<concepts-command> --root <workspace-root> --json graph
<concepts-command> --root <workspace-root> --json shared
<concepts-command> --root <workspace-root> --json hot --limit 10
<concepts-command> --root <workspace-root> --json capture-health
```

Only write graph changes when the user explicitly requests persistence or the save workflow clearly includes graph capture.

## Output

Report:

- files updated
- durable signal saved
- signals surfaced
- graph or capture result, if attempted
- intentionally skipped items
