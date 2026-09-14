---
name: save
description: "Save session learnings to auto-memory. Summarizes what was done, checks for recurring patterns, detects friction and emerging signals, and updates MEMORY.md, project AGENTS.md, learnings.md, and the daily note. Run at the end of a session or after completing meaningful work."
argument-hint: [--quick | --deep | focus area]
model: sonnet
allowed-tools: Read, Write, Edit, Glob, Bash(~/.cortex/concepts *), Bash(python3 -c *), Bash(wc -l *), Bash(date *)
---

# /save -- Save Session to Memory

Capture what happened this session and persist it to the right place. Then look for signals -- patterns, friction, emerging connections -- that should influence future sessions.

## Reference files (lazy-loaded)

Read these when the corresponding step needs detail:

- `references/routing.md` -- destinations, strict scope test, anti-pattern walkthrough, routing table, MEMORY.md subtypes, rule of thumb. Read before Step 3
- `references/output.md` -- daily note, MEMORY.md, AGENTS.md, playbook, learnings templates, prioritization, report template. Read before Steps 5-7
- `references/examples.md` -- signal scenarios, rule promotion shapes, what-NOT-to-save anchors. Read before Step 4 and Step 9

## Configuration

Read `.memory-config` from the workspace root (same directory as `.claude/`). Parse `key: value` pairs (one per line, ignore `#` comments). If absent, use PARA defaults.

| Variable | Config key | Default |
|---|---|---|
| `$DAILY_DIR` | `daily_dir` | `2-areas/me/daily` |
| `$LEARNINGS` | `learnings` | `2-areas/me/learnings.md` |
| `$REFLECT_LOG` | `reflect_log` | `2-areas/me/reflect-log.md` |
| `$PROJECT_ROOT` | `project_root` | `1-projects` |
| `$WORKSPACE` | `workspace` | `personal` |

Resolve variables once at Step 1.

Project context file: each project's `AGENTS.md`. If a project has only `CLAUDE.md`, read and write that file wherever this skill says project AGENTS.md.

## Destinations (summary)

Full rules in `references/routing.md`. One-line summary:

- **MEMORY.md** (`$MEMORY_DIR/MEMORY.md`): cross-project knowledge index. One-line entries, ≤150 chars
- **Project AGENTS.md** (`$PROJECT_ROOT/<name>/AGENTS.md`): project-specific state, decisions, friction
- **Project playbook** (`$PROJECT_ROOT/<name>/playbook.md`): durable execution patterns with dated proof points. Create if missing
- **Personal learnings** (`$LEARNINGS`): traits describing the user as a person. NOT technical details. Scope test enforced
- **Daily note** (`$DAILY_DIR/YYYY-MM-DD.md`): today's work log and tasks

## Workflow

### Step 0: Mode selection

Parse `$ARGUMENTS` for a mode flag:

- `--quick`: lightweight mode. Runs Steps 1, 2, 2b, 3 (daily-note routing only), 5, 7 (brief). SKIPS Steps 4 (patterns), 6 writes to learnings.md / MEMORY.md / project AGENTS.md, 8 (signal action), 9 (rule promotions). Use when context is pressured at session end; `/reflect` Pass 8 will catch anything deferred
- `--deep`: full flow with explicit attention to pattern detection and rule promotions. Default intensity
- no flag OR focus string: **full mode** (default, current behavior). Runs all steps

Behavior reasoning: concept capture happens in the cortex Stop hook independently of /save. When context is pressured, the risk is degraded reflection quality (routing, pattern detection, rule promotion), not work loss. `--quick` defers reflection to `/reflect`; work capture still happens in the hook.

If `--quick` was selected, every downstream step has a "skip in quick mode" note. Honor those. At the end, the brief report should say `Mode: quick (reflection deferred to /reflect)`.

If `$ARGUMENTS` contains a non-flag string, treat it as a focus area and forward to Step 2 (same as before).

### Step 1: Load config and locate memory files

Read `.memory-config` and resolve variables. Additional derivations:

- `$MEMORY_DIR` = `~/.claude/projects/{slug}/memory`, where `{slug}` is the workspace absolute path with `/` replaced by `-`. For `/home/user/my-workspace` -> `~/.claude/projects/-home-user-my-workspace/memory`
- `$TODAY` = today's date `YYYY-MM-DD`
- `$DAILY_FILE` = `$DAILY_DIR/$TODAY.md`

Read `$MEMORY_DIR/MEMORY.md` if it exists. Note line count and any open `## Promotion Queue` items.

If the session was project-scoped (work done under `$PROJECT_ROOT/<name>/`), read that project's `AGENTS.md` too -- especially Friction Log and Decision Register.

Check `$DAILY_FILE`. If missing, create it in Step 5 after checking previous day for carry-over.

### Step 2: Summarize this session

Extract from the conversation:

- **What was done**: concrete actions (files, fixes, features, configs). Tag with time anchor if detectable (`~morning`, `~afternoon`, `~2h block`)
- **Decisions made**: choices + rationale + confidence (`[settled]`, `[tentative]`, `[revisit]`)
- **Friction observed**: repeated commands, same error type, workarounds for missing abstractions
- **Learnings**: things useful for future sessions
- **Connections detected**: links to another project, past decision, or stated goal
- **Unfinished work**: started-but-not-done, next steps

If `$ARGUMENTS` provided a focus area, prioritize that topic.

### Step 2b: Queue concept extraction (requires concepts CLI)

**Skip if:** `--sensitive` flag provided, `~/.cortex/concepts` does not exist, or session had no meaningful content.

**Auto-init:** if `~/.cortex/concepts` exists but `concepts.db` does not exist in the workspace root, run `~/.cortex/concepts init`.

**Weight formula:** `weight = 1 + (token_count>5000) + (concepts>=2) + (decisions>=1) + (friction>=1)`, capped at 5.

**Extraction cap:** weight 1-2 -> up to 3 concepts, weight 3 -> up to 5, weight 4-5 -> up to 8.

**Query vocabulary:** `~/.cortex/concepts --root . --json list` returns a bare JSON array. Iterate directly as `[c['name'] for c in data]`. Do NOT call `data.get('concepts', ...)` -- `data` is already the list, `.get` raises `AttributeError`.

Also: `~/.cortex/concepts --root . --json graph` for context (dict with `concepts`, `edges`, `sources`, `normalization_rules`, `extractions`, `projects`, `avg_edges_per_concept`, `confidence_distribution`).

**Propose concepts.** For each, pick:

- `name` canonical (match existing vocabulary first)
- `kind` ∈ {topic, tool, pattern, decision, person, project}
- Relationships to existing/co-proposed concepts with relation ∈ {related-to, depends-on, conflicts-with, enables, is-instance-of, supersedes, blocked-by, derived-from}

**Write to `~/.cortex/last-session.json`** using the Write tool. Session hash = MD5 of `(summary + ISO_timestamp)`, first 16 chars:

```bash
python3 -c "import hashlib; print(hashlib.md5(('summary 2026-03-24T20:00:00').encode()).hexdigest()[:16])"
```

Schema:
```json
{
  "workspace_root": "/absolute/path",
  "session_hash": "c61518a4fd94ac05",
  "weight": 5,
  "project": "cortex",
  "concepts": [{"name": "session-resume", "kind": "pattern"}],
  "edges": [{"from": "session-resume", "to": "cortex", "relation": "enables"}],
  "proposed": ["session-resume", "undercover-mode", "public-repo-audit"],
  "created": ["session-resume", "undercover-mode"],
  "rejected_count": 1
}
```

The Stop hook (`concept-extract.sh`) reads this file after the session ends.

### Step 3: Route entries

For each Step 2 item, use the rule of thumb:

1. User as a person (thinks, decides, communicates, prefers)? -> `$LEARNINGS`
2. Cites a specific project/file/commit/test/regex/flag/phase/task? -> project playbook (create if missing)
3. Cross-project tooling or environment facts? -> MEMORY.md
4. Project decision with state/rationale? -> project AGENTS.md
5. Concrete action or task? -> daily note

Read `references/routing.md` for the full routing table, MEMORY.md subtypes, and the strict scope test for learnings.md. The scope test is REQUIRED before any write to `$LEARNINGS`.

### Step 4: Check for patterns and signals

**Skip in `--quick` mode.** Deferred to `/reflect`.

Go beyond what happened. Look for what it implies.

**Pattern checks:**

1. **Duplicates**: already captured? Skip
2. **Reinforcement**: confirms an existing entry? Increment tally or mark promotion candidate
3. **Contradiction**: conflicts with an existing entry? Flag `[CONFLICT: ...]`
4. **Stale**: existing entry not referenced in 10+ sessions? Flag `[STALE?]`
5. **Violated preference**: if the user corrected behavior this session and the correction matches an existing `$LEARNINGS` or MEMORY.md entry, this is NOT a new learning. Escalate immediately to Step 9 as Rule promotion with `[VIOLATED]`. Do not wait for a second occurrence

**Friction detection**: for each Friction Log item, check if it has appeared 2+ times -> automation candidate. If an obvious fix exists (alias, script, template), propose it.

**Signal detection** -- actively look for:

- **Opportunity**: this session's work connects to a stated goal, past idea, or another active project
- **Risk**: a decision created a dependency/assumption/constraint that could collide elsewhere
- **Convergence**: multiple workstreams pointing toward the same underlying need

See `references/examples.md` for concrete opportunity/risk/convergence scenarios.

Surface detected signals in Step 7 under `Signals`.

### Step 5: Write daily note

Template and grouping rules: `references/output.md` -> Daily note section.

- If `$DAILY_FILE` does not exist: find most recent prior note, extract `[ ]` tasks as carry-over, create the new file grouped by project
- If `$DAILY_FILE` exists: append to existing project sections, mark completed tasks `[x]`

### Step 6: Write memory entries

**In `--quick` mode: skip this step entirely.** Daily note (Step 5) is the only write. Everything else waits for a later `/save --deep` or gets surfaced by `/reflect` Pass 8.

Templates for MEMORY.md, project AGENTS.md, project playbook, personal learnings: `references/output.md`.

**Critical rules:**

- One line per entry in learnings.md, MEMORY.md, project AGENTS.md. Playbook entries can be multi-paragraph with dated proof points
- Before any write to `$LEARNINGS`, run the strict scope test from `references/routing.md`. If it fails, route to project playbook and create the playbook if missing
- Consolidate rather than duplicate. Do not auto-delete. Do not store sensitive data
- MEMORY.md prioritization when near 200-line limit: see `references/output.md`

### Step 7: Report

Emit the Step 7 report template from `references/output.md`.

**In `--quick` mode:** emit a brief report -- mode indicator (`Mode: quick (reflection deferred to /reflect)`), daily note delta, cortex concept count, and a one-line "what to watch" pointer if you noticed something during Step 2 that merits attention. Skip Signals, Patterns, and Promotion Candidates sections. Fill in concept count, daily-note deltas, MEMORY.md line count, new AGENTS.md entries, learnings updates, signals, promotion candidates, stale flags, automation candidates.

### Step 8: Act on high-confidence signals

**Skip in `--quick` mode.** Signals are surfaced in the report only; no inline action.

Do not wait for the user to notice. If a signal is clear, act on it within the session:

- **Friction with obvious fix**: propose the alias/script/template. If it is a one-liner, write it now
- **Opportunity connection**: name it briefly and ask if you should explore it
- **Risk signal**: surface clearly before session ends. Do not bury it in the report

For ambiguous signals, surface and ask. Do not act autonomously on architecture, naming, or project direction.

### Step 9: Check for rule promotions

**Skip in `--quick` mode.** Rule promotions are deferred to `/reflect` and `/review`.

Two escalation paths, shapes in `references/examples.md`:

- **Normal promotion**: a learning appears 2+ times or is phrased as a universal principle
- **Violated preference**: Step 4 flagged `[VIOLATED]`. Skips the 2+ requirement. Surface prominently, not buried

Do not auto-promote. Always let the user decide. For violated preferences, present the promotion first in the report.

## What NOT to save

- Temporary session state (debugging steps, in-progress work)
- File contents or code snippets (save file path + decision rationale instead)
- Meta-conversation (outcomes matter, not the conversation about them)
- Anything already captured in the target file (consolidate, don't duplicate)
- Sensitive data (credentials, tokens, PII -- reference secret manager or env var name)

Full examples in `references/examples.md` -> What NOT to save.
