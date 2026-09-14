# Save Workflow Contract

Persist durable session learnings so future sessions can resume from outcomes, decisions, risks, and next actions.

## Inputs

- `<workspace-root>/.memory-config`, when present
- Current git status for changed files, when relevant
- Daily notes, project context files, project playbooks, personal learnings, and workspace memory files
- Cortex CLI reads, when available at `<concepts-command>`

Project context file: each project's `AGENTS.md`. If a project has no `AGENTS.md`, use the agent instruction file it does have.

## Modes

- `quick`: daily note only, plus a brief report that starts with `Mode: quick (reflection deferred to reflect)`. Skip the signal pass, memory, learnings, and project context writes, signal actions, and rule promotions. Use when context is tight at session end
- `full`: daily note plus durable routing, signal pass, signal actions, and rule promotions
- `deep`: full mode with explicit attention to friction, risk, opportunity, graph signals, and rule promotions

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
5. Read destination files before editing so the save consolidates instead of duplicating. Route each item with `references/routing.md`, and run its strict scope test before any write to personal learnings.
6. Write the smallest durable update:
   - daily notes for concrete work and next actions
   - project context for state, decisions, and continuity rules
   - project playbooks for reusable execution patterns with proof
   - personal learnings for durable user operating preferences
   - workspace memory for cross-project patterns and tool behavior
   Keep one line per entry in daily notes, project context, learnings, and workspace memory index entries of 150 characters or fewer. Playbook entries may run longer and keep their dated proof.
7. In full or deep mode, run the signal pass, act on high confidence signals, and check for rule promotions.
8. Report what changed, what was intentionally skipped, and any follow-up risk.

## Signal Pass

Classify each candidate as one of:

- duplicate: already captured; skip or consolidate
- reinforcement: strengthens an existing rule or pattern
- contradiction: conflicts with saved context
- stale: saved context appears superseded
- violated preference: the user corrected behavior that a saved preference already covers. Escalate immediately as a rule promotion candidate tagged `[VIOLATED]`, with no second occurrence needed, and list it first in the report
- friction recurrence: same friction appears at least twice
- opportunity: connection to a stated goal, another project, or reusable asset
- risk: dependency, date collision, drift, or unverified assumption
- convergence: multiple projects point at the same underlying need

Do not invent durable patterns from one weak mention.

## Signal Actions

Act within the session when a signal is clear:

- friction with an obvious fix: propose the alias, script, or template. Write it now if it is a one liner
- opportunity: name it briefly and ask whether to explore it
- risk: surface it clearly before the session ends, not buried in the report

For ambiguous signals, surface and ask. Do not act autonomously on architecture, naming, or project direction.

## Rule Promotion

- normal promotion: a learning has appeared 2 or more times, or is phrased as a universal principle. Propose it as a standing rule for the root agent instruction file
- violated preference: skips the 2 occurrence threshold, because a documented preference that was not applied has already proven the observation layer insufficient

Never auto-promote. The user decides.

## What Not To Save

- temporary session state such as in-progress debugging steps. Save the pattern, not the step
- file contents or code snippets. Save the file path and decision rationale
- conversation about the work instead of its outcome
- anything the target file already captures. Consolidate instead
- credentials, tokens, secrets, or personal data. Reference the secret store or variable name instead

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
