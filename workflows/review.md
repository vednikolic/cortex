# Review Workflow Contract

Turn accumulated signals into decisions. Reflect surfaces patterns; review decides what to promote, defer, dismiss, act on, or watch.

## Inputs

- `<workspace-root>/.memory-config`, when present
- Reflect log entries since the last weekly synthesis
- Current week start date, Monday
- Recent daily notes
- Workspace memory and project context files
- Cortex CLI reads, when available at `<concepts-command>`

Project context file: each project's `AGENTS.md`. If a project has no `AGENTS.md`, use the agent instruction file it does have. Revisit decisions come from the Decision Register in each project context file.

## Procedure

1. Resolve workspace paths from `.memory-config`; otherwise use local defaults.
2. Determine the current week start date in local time.
3. Find the most recent weekly synthesis.
4. Gather unreviewed reflect entries since that synthesis.
5. Run graph reads when available.
6. Triage candidates into promote, defer, dismiss, act now, or watch.
7. Apply graph promotions or decay only when requested or when the review explicitly includes applying weekly decisions.
8. Write or update the weekly synthesis file.
9. Report decisions and residual risks.

## Optional Cortex Reads

```bash
<concepts-command> --root <workspace-root> --json confidence-check
<concepts-command> --root <workspace-root> --json stale --days 14
<concepts-command> --root <workspace-root> --json shared
<concepts-command> --root <workspace-root> --json hot --limit 10
<concepts-command> --root <workspace-root> --json graph
<concepts-command> --root <workspace-root> --json capture-health
```

## Triage Rules

Promote when a concept has 3 or more sources, appears in 2 or more projects, repeats across sessions with clear benefit, or represents a saved preference that was violated again.

Defer when signal is plausible but single-project, fresh but not repeated, or likely caused by a temporary deadline.

Dismiss when signal was a one-off, has been superseded, or no longer maps to an active goal.

Act now when the finding points to an imminent date collision, misleading stale context, low-cost repeated friction fix, or unenforced public/privacy/compliance constraint.

Watch when the signal is strategically interesting but not actionable yet.

## Weekly Synthesis

Write or update `weekly/YYYY-MM-DD.md` using this structure:

```markdown
# Week of YYYY-MM-DD

## What moved
[2-3 sentences on actual progress.]

## What the patterns say
[2-3 sentences on friction, convergence, drift, and opportunity.]

## Concept graph changes
- Concepts: N
- Edges: N
- Projects: N
- Promoted: [...]
- Deferred: [...]
- Dismissed: [...]
- Stale: [...]
- New or strengthened cross-project signals: [...]

## Drift check
- Goals with no work:
- Decisions older than 14 days marked revisit:
- Projects generating repeated stale noise:

## Carry-forward signals
- [1-5 items worth watching or acting on next week]

## Suggested focus
[1-2 sentence recommendation.]
```

Overwrite the current week's synthesis if rerun in the same week. The latest review supersedes earlier synthesis for that week.

## Output

Report:

- promoted
- deferred
- dismissed
- acted now
- watchlist
- weekly synthesis path
- graph write status
