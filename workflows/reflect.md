# Reflect Workflow Contract

Review saved workspace memory and infer what it implies. The goal is useful decision support, not a complete inventory.

## Inputs

- `<workspace-root>/.memory-config`, when present
- Last reflect entry
- Last 7 daily notes for current work
- Last 14 daily notes for dormant goal checks
- Workspace memory index and relevant topic files
- Active project context files and playbooks
- Cortex CLI reads, when available at `<concepts-command>`

Do not read raw transcripts. Use saved notes and project files as the distilled record.

## Procedure

1. Resolve workspace paths from `.memory-config`; otherwise use local defaults.
2. Read the last reflect entry to avoid repeating prior findings.
3. Gather recent daily notes, relevant project context, workspace memory, and graph reads.
4. Run the analysis passes below.
5. Append one reflect log entry using the required output structure.
6. Summarize the top 3 insights and recommended next actions.

## Optional Cortex Reads

```bash
<concepts-command> --root <workspace-root> --json graph
<concepts-command> --root <workspace-root> --json shared
<concepts-command> --root <workspace-root> --json hot --limit 10
<concepts-command> --root <workspace-root> --json stale --days 14
<concepts-command> --root <workspace-root> --json capture-health
```

## Analysis Passes

### Stale Detection

Flag memory or project entries with no support in recent daily notes. Flag `[revisit]` decisions older than 14 days. Distinguish healthy dormancy from context that may mislead the next session.

### Friction Promotion

Count repeated friction across project logs, playbooks, and reflect entries. At 2 occurrences, mark an automation or rule candidate. At 3 occurrences, recommend a concrete mitigation. At 5 occurrences, treat it as urgent.

### Cross-Project Signals

Surface 3 to 5 high-signal findings when available. Classify each as `OPPORTUNITY`, `RISK`, or `CONVERGENCE`. Prefer graph-backed findings from shared, hot, stale, or co-occurring concepts.

### Promotion Candidates

Identify patterns repeated across sessions or projects. Recommend whether each belongs in root rules, project playbooks, workspace memory, or no action. Do not auto-promote during reflect.

### Dormant Signals And Goal Drift

Compare saved goals with the last 14 daily notes. Flag goals repeatedly mentioned but not worked. If the same dormant project has been flagged 3 times, recommend archive, pause, or a revisit date instead of repeating the stale warning.

### Graph Health

Report concept count, edge count, source coverage, project count, confidence distribution, extraction count, and capture health when graph reads are available. Flag weak graph quality signals.

### Constraint Governance

Scan saved rules for terms like never, always, must, do not, block, prevent, audit, confidential, separation, and public repo. Identify constraints that lack enforcement. Recommend only unless the user asked for edits.

### File Hygiene

Check memory index size, long entries, orphan topic files, project context drift, and duplicate live sources that should be archived or canonicalized.

## Anti-Noise Rules

- If a stale warning appeared in the last reflect entry and no new evidence exists, collapse it under `Repeated from last reflect`.
- If urgency increased, restate the warning and name the new evidence.
- If a signal is one session old and has no cross-project impact, keep it out of the top 3 insights.
- Prefer one sharp finding with evidence over broad summary.

## Insight Quality

Each top insight must include:

```text
Evidence:
Implication:
Recommended action:
Cost of ignoring:
Confidence:
```

## Reflect Log Entry

```markdown
## Reflect -- YYYY-MM-DD HH:MM [trigger: manual]

### Stale flags
- ...

### Friction escalations
- ...

### Cross-project signals
- OPPORTUNITY/RISK/CONVERGENCE: ...

### Promotion candidates
- ...

### Dormant signals
- ...

### Graph health
- ...

### Constraint governance
- ...

### File hygiene
- ...

### Suggested focus
- ...
```
