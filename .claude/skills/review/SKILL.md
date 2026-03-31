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

Read `.memory-config` for path configuration. Set variables:

```
REFLECT_LOG: path from reflect_log config key (default: 2-areas/me/reflect-log.md)
WEEKLY_DIR: path from weekly_dir config key (default: 2-areas/me/weekly)
TODAY: current date (YYYY-MM-DD)
WEEK_START: Monday of this week (YYYY-MM-DD)
```

### Step 2: Gather pending signals

Run the following to collect all signals needing triage:

```bash
~/.cortex/concepts confidence-check --json
~/.cortex/concepts stale --days 14 --json
~/.cortex/concepts shared --json
~/.cortex/concepts hot --limit 10 --json
```

Also read the reflect log (`$REFLECT_LOG`) for any unreviewed entries since the last weekly summary. An entry is "unreviewed" if it was written after the most recent `weekly_summaries` row.

### Step 3: Present signals for triage

Present each signal category to the user with recommended actions:

**Promotion eligible:**
For each concept eligible for promotion (from Step 2), show:
- Concept name, current confidence, suggested level, and reason
- Your recommendation: promote or defer (with reasoning)

Ask the user to confirm each: promote, defer, or skip.

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

Then write a synthesis markdown file to `$WEEKLY_DIR/$WEEK_START.md`:

```markdown
# Week of YYYY-MM-DD

## Graph this week
- Concepts: N (+/-delta from last week)
- Edges: M (+/-delta)
- Projects: K

## Velocity
- N concepts/week (4-week average)

## Decisions made
- Promoted: [list of promoted concepts with new level]
- Dismissed: [list of dismissed edges]
- Deferred: [list of deferred items]
- Demoted by decay: [list of decayed concepts]

## Patterns
- [Cross-project patterns from shared concepts]
- [Friction patterns from reflect log]

## Stale concepts
- [Concepts unreferenced 14+ days, for awareness]

## Carry-forward
- [Deferred items that need attention next week]
```

### Step 6: Report

```
Review complete.

Triage:
  Promoted: N concepts
  Dismissed: M edges
  Deferred: K items
  Decayed: J concepts

Weekly synthesis written to $WEEKLY_DIR/$WEEK_START.md

Graph: X concepts, Y edges, Z projects
  This week: +A concepts, +B edges

[If first review]: Your first weekly review. Run /review weekly to track concept evolution.
[If 4+ reviews]: You have N weeks of synthesis data. Concept evolution is visible in $WEEKLY_DIR/.
```
