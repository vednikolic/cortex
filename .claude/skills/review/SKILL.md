---
name: review
description: "Weekly triage of accumulated signals. Reviews reflect-log entries, promotion-eligible concepts, stale entries, and cross-project patterns. For each signal: promote, dismiss, or defer. Generates a weekly synthesis snapshot. Run weekly or when reflect-log has unreviewed findings."
user-invocable: true
---

# /review -- Weekly Signal Triage

Review accumulated signals and make decisions. Promotes concepts that have earned higher confidence, dismisses noise, and generates a weekly synthesis showing how your knowledge graph is evolving.

## When to run

- Weekly (Sunday or Monday works well)
- After /reflect surfaces findings you haven't reviewed
- When `concepts confidence-check` shows promotion-eligible concepts

## Workflow

### Step 1: Load context

Read `.memory-config` from the workspace root (same directory as `.claude/`). Parse as simple `key: value` pairs (one per line, ignore comments starting with `#`). If the file does not exist, use defaults below.

```
REFLECT_LOG: path from reflect_log config key (default: 2-areas/me/reflect-log.md)
WEEKLY_DIR: path from weekly_dir config key (default: 2-areas/me/weekly)
LEARNINGS: path from learnings config key (default: 2-areas/me/learnings.md)
PROJECT_ROOT: path from project_root config key (default: 1-projects)
TODAY: current date (YYYY-MM-DD)
WEEK_START: Monday of this week (YYYY-MM-DD)
```

### Step 2: Gather pending signals

First, check if the concepts CLI is available by running `~/.cortex/concepts --version`. If the CLI is not installed:
- Skip all CLI-dependent queries (confidence-check, stale, shared, hot, confidence-check --decay, review-summary)
- Still read the reflect log, correction queue, and learnings
- Still produce a weekly synthesis from reflect-log signals and learnings-based drift check
- Note in the report: "Graph CLI not available. Synthesis based on reflect-log and learnings only."

If the CLI is available, run:

```bash
~/.cortex/concepts confidence-check --json
~/.cortex/concepts stale --days 14 --json
~/.cortex/concepts shared --json
~/.cortex/concepts hot --limit 10 --json
```

**Confidence lifecycle thresholds** for interpreting promotion eligibility:
- Tentative to established: concept has 3+ sources OR appears in 2+ projects
- Established to settled: edge strength >= 5 AND concept age >= 30 days, OR manually promoted by user
- Decay (checked in Step 4): settled demotes to established after 90 days unreferenced; established demotes to tentative after 60 days unreferenced. Tentative is the floor; nothing is deleted by decay.

Also read:
- The reflect log (`$REFLECT_LOG`) for any unreviewed entries since the last weekly summary. An entry is "unreviewed" if it was written after the most recent `weekly_summaries` row. If the reflect log does not exist or has no entries, skip reflect-log signal triage but still proceed with CLI signals, correction queue, and synthesis generation. A review with zero reflect-log entries is valid (the graph data alone provides signal).
- The correction queue at `~/.claude/memory/correction-queue.json` if it exists. This contains concepts flagged as incorrect via the graph explorer's "Flag as incorrect" button.
- `$LEARNINGS` for stated goals (used in drift check).

### Step 3: Present signals for triage

Present each signal category to the user with recommended actions:

**Promotion eligible:**
Present promotions as a numbered list, grouped into "Recommend promote" and "Recommend defer." For each concept, show four lines:

1. **Name and stats**: concept name, source count, project count
2. **What**: one sentence describing what this concept represents in the user's work
3. **Why listed**: which threshold it crossed (3+ sources, 2+ projects, or both) and what makes it significant
4. **Promoting it / Deferring it**: one sentence on the concrete effect. For promotions: what changes (e.g., "resists stale detection for 90 days instead of 60, gets higher priority in /reflect cross-project signals"). For deferrals: why waiting is better (e.g., "single-project, wait for a second project reference")

Example format:
```
Recommend promote:
1. postgresql (5 sources, 3 projects)
   What: Your most-used database tool across my-api, my-app, and admin-dashboard.
   Why listed: 3+ sources AND 2+ projects. High-confidence cross-project concept.
   Promoting it: Gets higher priority in /reflect signals. Resists stale detection for 90 days instead of 60.

Recommend defer:
3. redis-caching (2 sources, 1 project)
   What: Caching layer discussed in my-api only.
   Why listed: 2 sources meets minimum, but single-project and not referenced recently.
   Deferring: Wait for a second project reference or continued usage before promoting.
```

**Default behavior: auto-promote.** Concepts that cross the threshold are promoted automatically. Present the numbered list as a report of what was promoted and what was deferred, not as a question. End with:

```
Promoted 1-N automatically. Deferred M-K (reasons above).
Tip: To undo a promotion, run `concepts correct <name>` or tell me to demote any concept by number.
```

The user can adjust after the fact ("demote 3", "also promote 12") but does not need to approve each one. This keeps the review fast. The thresholds are conservative enough that auto-promotion is safe: 3+ independent sources or 2+ projects is a high bar.

For confirmed promotions:
```bash
~/.cortex/concepts promote "$name" $level
```

**Stale concepts:**
For concepts unreferenced in 14+ days, show:
- Name, last referenced date, confidence level
- Your recommendation: is this still relevant?

No automated action. Note stale concepts in the weekly synthesis for awareness.

**Cross-project patterns:**
For shared concepts, surface:
- Which projects share the concept
- Whether this creates opportunities (shared abstractions) or risks (conflicting assumptions)

Note findings in the weekly synthesis.

**Correction queue:**
If `~/.claude/memory/correction-queue.json` exists and has entries, present each:
- Concept name, what was flagged, when it was flagged
- Your recommendation: accept correction (rename/merge/remove), or dismiss

For accepted corrections:
```bash
~/.cortex/concepts correct "$name" --rename "$new_name"
~/.cortex/concepts merge "$source" "$target"
```

After triage, clear processed entries from the queue file.

**Reflect log signals:**
For unreviewed reflect entries, present:
- The finding text
- Your recommendation: act now, defer, or dismiss

For edge dismissals:
```bash
~/.cortex/concepts dismiss $edge_id
```

### Step 4: Run confidence decay

After triage, apply decay to catch concepts that have gone stale:

```bash
~/.cortex/concepts confidence-check --decay --json
```

Report any demotions to the user.

### Step 5: Generate weekly synthesis

Create the weekly summary snapshot:

```bash
~/.cortex/concepts review-summary --create $WEEK_START --json
```

If `$WEEKLY_DIR` does not exist, create it before writing.

**Idempotency:** If `$WEEKLY_DIR/$WEEK_START.md` already exists (review run twice in the same week), overwrite it with the new synthesis. The most recent triage decisions take precedence. The concepts.db `review-summary` row is also upserted (not duplicated) for the same week.

Then write a synthesis markdown file to `$WEEKLY_DIR/$WEEK_START.md`:

```markdown
# Week of YYYY-MM-DD

## What moved
[2-3 sentences on actual progress across projects, based on reflect log entries and graph changes]

## What the patterns say
[2-3 sentences on what friction, convergence, and dormant signals imply]

## Concept graph changes
- Concepts: N (+/-delta from last week)
- Edges: M (+/-delta)
- Projects: K
- Velocity: N concepts/week (4-week average)
- New: [concepts added this week]
- Strengthened: [edges that increased in strength]
- Conflicting: [any new conflict edges]
- Promoted: [list of promoted concepts with new level]
- Dismissed: [list of dismissed edges]
- Demoted by decay: [list of decayed concepts]

## Drift check
- Goals with no work this week: [compare stated goals from $LEARNINGS against recent daily notes and graph activity]
- Decisions marked revisit older than 14 days: [from project CLAUDE.md Decision Registers]

## Carry-forward signals
- [1-3 unresolved signals from reflect log]
- [Deferred items from this triage that need attention next week]
- Stale concepts: [concepts unreferenced 14+ days, for awareness]
- Corrections pending: [any remaining correction-queue items not triaged]

## Suggested focus
[1-2 sentence recommendation for next week based on patterns, drift, and carry-forward]
```

### Step 6: Report

```
Review complete.

Triage:
  Promoted: N concepts
  Dismissed: M edges
  Deferred: K items
  Decayed: J concepts
  Corrections: C processed

Weekly synthesis written to $WEEKLY_DIR/$WEEK_START.md

Graph: X concepts, Y edges, Z projects
  This week: +A concepts, +B edges

[If drift detected]: Drift check found G goals with no activity this week.
[If first review]: Your first weekly review. Run /review weekly to track concept evolution.
[If 4+ reviews]: You have N weeks of synthesis data. Concept evolution is visible in $WEEKLY_DIR/.
```
