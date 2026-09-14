---
name: reflect
description: "Background memory consolidation. Reviews MEMORY.md, project AGENTS.md files, and daily notes for patterns, stale entries, cross-project signals, and promotion candidates. Runs automatically post-heavy-session (Stop hook) or manually via /reflect. Writes a consolidation report to the configured reflect log path. Never blocks. Never auto-promotes."
argument-hint: [optional focus area or project scope]
model: sonnet
allowed-tools: Read, Write, Edit, Glob, Bash(~/.cortex/concepts *), Bash(python3 -c *)
---

# /reflect -- Background Memory Consolidation

A lightweight consolidation pass that runs after heavy sessions or on demand. It does not save session state -- /save does that. It reads what has already been saved and looks for what it implies: patterns across sessions, stale entries that should be pruned, connections between projects, and ideas that have appeared multiple times without being promoted.

This is not data entry. It is re-indexing.

---

## Configuration

Read `.memory-config` from the workspace root (same directory as `.claude/`). Parse as simple `key: value` pairs (one per line, ignore comments starting with `#`). If the file does not exist, use PARA defaults.

| Variable | Config key | Default |
|---|---|---|
| `$DAILY_DIR` | `daily_dir` | `2-areas/me/daily` |
| `$LEARNINGS` | `learnings` | `2-areas/me/learnings.md` |
| `$REFLECT_LOG` | `reflect_log` | `2-areas/me/reflect-log.md` |
| `$PROJECT_ROOT` | `project_root` | `1-projects` |
| `$WORKSPACE` | `workspace` | `personal` |

All path references in this document use these variables. Resolve them before reading any files.

Project context file: each project's `AGENTS.md`. If a project has only `CLAUDE.md`, read and write that file wherever this skill says project AGENTS.md.

---

## Trigger Logic

Reflect runs in two modes:

### 1. Automatic post-session (Stop hook, async)

The gate script `reflect-gate.sh` decides whether to run a full consolidation:

```bash
#!/usr/bin/env bash
# ~/.claude/scripts/reflect-gate.sh
# Decide whether this session is heavy enough to warrant a reflect pass.
# Inputs: CLAUDE_SESSION_TURN_COUNT (env var from hook context)

TURN_COUNT="${CLAUDE_SESSION_TURN_COUNT:-0}"
LAST_REFLECT="$HOME/.claude/reflect-last-run"
NOW=$(date +%s)

# Run if: session had 15+ turns, OR last reflect was 24h+ ago
if [ "$TURN_COUNT" -ge 15 ]; then
  echo "reflect:trigger:heavy-session turns=$TURN_COUNT" >> "$HOME/.claude/reflect-gate.log"
  exit 0  # signal to proceed
fi

if [ -f "$LAST_REFLECT" ]; then
  LAST=$(cat "$LAST_REFLECT")
  DIFF=$((NOW - LAST))
  if [ "$DIFF" -ge 86400 ]; then
    echo "reflect:trigger:daily-elapsed diff=${DIFF}s" >> "$HOME/.claude/reflect-gate.log"
    exit 0
  fi
fi

exit 1  # skip
```

Exit 0 = proceed with reflect. Exit 1 = skip. Since this is an async hook on Stop, exit code does not block the session.

### 2. Manual (/reflect)

Run at any time. Useful after a large planning session, a naming decision, or a multi-project context switch.

---

## What /reflect reads

Before running any analysis, locate and read these files. All paths are relative to the workspace root unless noted.

| File | Path | What to read |
|---|---|---|
| MEMORY.md | `~/.claude/projects/<project-key>/memory/MEMORY.md` (where project-key is the workspace path with `/` replaced by `-`) | Full file, especially Promotion Queue section |
| Reflect log | `$REFLECT_LOG` | Last entry only (to avoid duplicating findings) |
| Learnings | `$LEARNINGS` | Full file |
| Daily notes | `$DAILY_DIR/YYYY-MM-DD.md` | Last 7 files by date; read only Work Log and Tasks sections |
| Project AGENTS.md files | `$PROJECT_ROOT/*/AGENTS.md` (use `find $PROJECT_ROOT -maxdepth 3 \( -name "AGENTS.md" -o -name "CLAUDE.md" \)`, preferring AGENTS.md when both exist) | Friction Log, Decision Register, and architecture sections |
| Root AGENTS.md | `AGENTS.md` (workspace root) | `## Rules` section (for Pass 7 universal rules) |
| Root CLAUDE.md | `CLAUDE.md` (workspace root) | Claude-specific addenda only |
| Publish audit deny list | `~/.claude/scripts/publish-audit.sh` | `DENY_PATTERNS` array only (for Pass 7) |

Do not read full session transcripts. Too expensive and too noisy. The daily notes are the already-distilled record.

**Graceful handling of missing inputs:**
- If fewer than 7 daily notes exist (new user), use however many are available. A user with 2 days of notes still gets a useful reflect pass over those 2 days. Stale detection uses the available window, not a fixed 7.
- If MEMORY.md has no `## Promotion Queue` section, skip Pass 4 entirely and note "No promotion queue found" in the reflect-log entry under "No action required."
- If no project AGENTS.md files exist under `$PROJECT_ROOT/`, skip Pass 2 (friction promotion) and Pass 3 (cross-project signals). Report "No project AGENTS.md files found" in the reflect-log. Passes 1, 4, 5, and 6 can still run against MEMORY.md, learnings, and daily notes.
- Daily note entries tagged `[sensitive]` must be excluded from pattern analysis, concept matching, and cross-project signal detection. Read them only for their date presence (to count active days) but not their content. This prevents sensitive session data from leaking into reflect-log findings.

---

## Graph availability check (requires concepts CLI)

Before running analysis passes, check if the concepts CLI is available:

1. **CLI exists:** Test by running `~/.cortex/concepts --version`. If it succeeds, set `$GRAPH_AVAILABLE = true`. Graph data will be queried live in each pass that needs it.
2. **CLI does not exist:** Set `$GRAPH_AVAILABLE = false`. Continue without graph data. This is expected before cortex is installed.

There is no reflect-context.json dependency. All graph queries run live against concepts.db via the CLI. This eliminates the staleness gap between /save writes and /reflect reads.

---

## Analysis passes

Run each pass in sequence. Each pass is cheap (pattern match over structured text). Only the signal surfacing requires model reasoning.

**Progress indication (manual invocation only):** When triggered manually via /reflect, output the pass name before starting each pass (e.g., "Pass 1: Stale detection...") so the user sees intermediate progress. When triggered via Stop hook, skip progress output since the user is not watching.

**Pass ordering:** Passes run sequentially (1 through 7) but are logically independent. No pass reads the output of a previous pass. Each pass reads only the source files listed in "What /reflect reads" and the graph CLI. Sequential execution is for simplicity and predictable progress output, not for data dependency.

### Pass 1: Stale detection

**Input:** All entries in MEMORY.md, all entries in each project AGENTS.md under `$PROJECT_ROOT/`, the last 7 daily notes from `$DAILY_DIR/`.
**Output:** A list of `[STALE?]` flags for the reflect-log.md Stale Flags section.

1. Extract every discrete entry (bullet point, decision, or note) from MEMORY.md.
2. Extract every discrete entry from each project AGENTS.md found under `$PROJECT_ROOT/`.
3. For each entry, extract 2-3 key terms (proper nouns, tool names, concept names).
4. Grep the last 7 daily notes for each key term. If zero matches across all 7 notes AND the entry is not tagged `[permanent]`, mark as `[STALE?]`.
5. For Decision Register entries tagged `[revisit]`, compute days since the entry date. If older than 14 days, flag as overdue for revisit.

### Pass 2: Friction promotion

**Input:** Friction Log sections from each project AGENTS.md under `$PROJECT_ROOT/`.
**Output:** A list of friction escalations for the reflect-log.md Friction Escalations section.

1. Collect all Friction Log entries from every project AGENTS.md.
2. For each unique friction description, count distinct date prefixes (each entry has a date prefix).
3. If 3+ appearances: add to the report as "automation candidate".
4. If 5+ appearances: escalate in the reflect-log with "URGENT: Build fix for: [friction description]" and recommend the user create a task. Do not write directly to the daily note (Constraint 2: /reflect never writes to daily notes).
5. If fewer than 3 appearances: skip. One-off friction is noise. Three recurrences is a pattern. Five recurrences is a cost.

### Pass 3: Cross-project signal detection

**Input:** All project AGENTS.md files under `$PROJECT_ROOT/`, MEMORY.md, the last 7 daily notes.
**Output:** 3-5 signal entries for the reflect-log.md Cross-Project Signals section, each classified as OPPORTUNITY, RISK, or CONVERGENCE.

**When $GRAPH_AVAILABLE is true**, query the graph directly instead of raw text matching:
- Run `~/.cortex/concepts --root . shared --json` for cross-project concepts (replaces pairwise concept comparison)
- Run `~/.cortex/concepts --root . hot --json` for concept velocity and trending patterns
- Run `~/.cortex/concepts --root . stale --json` as additional input for stale detection (supplement Pass 1)
- Classify signals as before (OPPORTUNITY / RISK / CONVERGENCE) with higher confidence when backed by graph data with edge strength >= 2

This is the second-brain pass. It requires model reasoning (string matching alone cannot detect conceptual overlap).

1. Extract all named concepts, tools, decisions, and problem areas from each project AGENTS.md.
2. Compare pairwise across projects. For each concept appearing in 2+ projects, classify as:
   - **OPPORTUNITY**: shared abstraction, reusable component, or naming convergence.
   - **RISK**: conflicting assumptions, architectural contradiction, or unacknowledged dependency.
   - **CONVERGENCE**: multiple workstreams with the same underlying need.
3. Write exactly 3-5 signal entries. If more than 5 candidates exist, rank by number of cross-project appearances and keep the top 5.

Examples of what this catches:

- Two projects both have an "eval rerun" concept in separate CLAUDE.md files. Reflect detects overlap. Surfaces: "Shared concept: eval rerun -- potential shared module or API boundary."
- One project uses an exponential backoff pattern. MEMORY.md has a mental model about retry logic. Reflect connects them and notes the mental model should reference the implementation as a concrete example.
- A decision in one project assumes a specific data format. A different project's architecture note contradicts it silently. Reflect flags the conflict.

### Pass 4: Promotion queue review

**Input:** The `## Promotion Queue` section in MEMORY.md, the last 7 daily notes.
**Output:** Promotion recommendations for the reflect-log.md Promotion Queue section.

1. Read each candidate in the Promotion Queue.
2. For each candidate, grep the last 7 daily notes for related terms.
3. If related work is still active (1+ matches in daily notes): mark as "still relevant".
4. If the candidate concept has appeared again since it was queued (check daily notes for new mentions after the queue date): increase urgency and note the new occurrence.
5. If a candidate is both still relevant and has appeared 3+ times total: surface as "ready for root CLAUDE.md" in the report.
6. Do not auto-promote. Write the recommendation and stop.

### Pass 5: Idea and opportunity graph update

**Input:** `$LEARNINGS`, the last 14 daily notes from `$DAILY_DIR/`.
**Output:** Dormant signal entries for the reflect-log.md Dormant Signals section.

1. Read `$LEARNINGS` in full and the Work Log section of the last 14 daily notes.
2. Extract all ideas, goals, and interests mentioned in learnings.md.
3. For each idea or goal, search the 14 daily notes for mentions (use loose matching: same concept, different phrasing counts).
4. If an idea appears in 2+ daily notes but has no corresponding Work Log entry: flag as "dormant idea, mentioned N times, not acted on".
5. If a stated goal from learnings.md has zero Work Log entries in the last 14 days: flag as "stagnant goal".
6. If an interest or growth area from learnings.md connects to an active project (appears in a project AGENTS.md): flag as "connection opportunity" with the project name.

### Pass 6: Graph health (requires concepts CLI)

**Input:** Live CLI queries (if $GRAPH_AVAILABLE is true). Skip this pass if CLI is not available.
**Output:** A graph health section in the reflect-log entry.

1. Run `~/.cortex/concepts --root . graph --json` and report summary: N concepts, M edges, K projects, N normalization rules
2. Run `~/.cortex/concepts --root . velocity --json` and note extraction rate trends
3. Flag any graph maturity metrics below threshold:
   - Fewer than 10 concepts
   - Fewer than 2 projects
   - No edges with strength >= 3
   - No cross-project concepts
4. Run `~/.cortex/concepts --root . hot --json` and surface concepts with edge strength >= 3 (mature signals worth reviewing)
5. Run `~/.cortex/concepts --root . co-occurs --json <name>` for the top 3 hot concepts to surface structural similarity

### Pass 7: Constraint governance

**Input:** `$LEARNINGS`, root `CLAUDE.md` (Rules section only), `~/.claude/scripts/publish-audit.sh` (DENY_PATTERNS array only).
**Output:** A constraint governance section in the reflect-log entry.

This pass checks whether constraint-type learnings have corresponding enforcement. Constraints that sit in learnings.md without matching rules or deny patterns are leak vectors.

1. Read `$LEARNINGS` and identify constraint-type entries. Heuristic: entries containing words like "never", "always", "do not", "must", "block", "prevent", "audit", "separation", "confidentiality agreement", "confidential", or entries under sections named "Confidentiality", "Separation", "Security". Err toward false positives (surface too many) rather than false negatives (miss real constraints).
2. Read the `## Rules` section of root `CLAUDE.md`.
3. Read `~/.claude/scripts/publish-audit.sh` and extract the DENY_PATTERNS array entries.
4. For each constraint found in step 1:
   a. Check if a semantically matching rule exists in the CLAUDE.md Rules section.
   b. Check if the constraint references a greppable term (person name, product name, path pattern). If so, check whether that term appears in DENY_PATTERNS.
5. Classify each constraint as:
   - **Covered**: matching rule exists in CLAUDE.md AND deny pattern exists (if the constraint references a greppable term)
   - **Partially covered**: rule exists but no deny pattern (or vice versa)
   - **Unprotected**: neither rule nor deny pattern
6. Write findings to the Constraint Governance section of the reflect-log. If no gaps found, write "All N constraints covered. No gaps detected."

This pass is read-only. It MUST NOT edit CLAUDE.md, publish-audit.sh, or learnings.md. It surfaces recommendations only.

---

### Pass 8: File hygiene

**Input:** `$MEMORY_DIR/MEMORY.md`, `$LEARNINGS`, root `AGENTS.md`, root `CLAUDE.md`, all files in `$MEMORY_DIR/*.md`.
**Output:** A file hygiene section in the reflect-log entry.

This pass watches for drift toward index bloat and truncation. It does NOT refactor. It reports.

Checks:

1. **MEMORY.md size**: measure byte size. Warn at >15KB, error at >24KB (the index truncation threshold). One line entry for each threshold crossed.
2. **MEMORY.md index entry length**: count entries exceeding 200 characters. Every index entry should be ≤150 chars; long entries indicate embedded content that belongs in a topic file.
3. **learnings.md scope violations**: scan for entries containing project names (grep for `$PROJECT_ROOT/`, common project basenames), file paths, commit SHAs (7+ hex chars), regex patterns (backtick + `[` + `\\`), tool flags (`--\w+`), or dated proof points (`20\d\d-\d\d-\d\d`). Report count and 3 examples. These should route to project playbook per the `/save` strict scope test.
4. **Topic file orphans**: list every `.md` file in `$MEMORY_DIR/` other than `MEMORY.md`. Check if each is referenced in `MEMORY.md`. Unreferenced topic files are orphans; either add an index entry or archive them.
5. **Rule duplication across AGENTS.md and CLAUDE.md**: do a rough textual overlap check. If a sentence of >60 characters appears in both root `AGENTS.md` and root `CLAUDE.md`, flag for consolidation.

This pass is read-only. It surfaces recommendations only; no auto-refactor.

---

## Output: reflect-log.md entry

Append to `$REFLECT_LOG`:

```markdown
## Reflect -- YYYY-MM-DD HH:MM [trigger: heavy-session|manual]

### Stale flags
- MEMORY.md: "[entry]" -- not referenced in 7 days [STALE?]
- my-app CLAUDE.md: "[decision]" tagged [revisit], 18 days old

### Friction escalations
- my-app: "manually rebuilding container config before deploy" -- 4 occurrences -> automation candidate
- my-api: "re-explaining naming rationale each session" -- 3 occurrences -> candidate for CLAUDE.md standing context

### Cross-project signals
- OPPORTUNITY: "eval rerun" concept appears in both my-dashboard and my-api CLAUDE.md -- potential shared abstraction
- RISK: my-api assumes flat config schema; my-dashboard Decision Register has a conflicting nested schema note
- CONVERGENCE: three workstreams all need a lightweight event log -- same underlying need

### Promotion queue
- "treat eval coverage like test coverage -- block on red" -- seen 3 times -- ready for root CLAUDE.md

### Dormant signals
- Idea: "constructed language as a tagging system for memory retrieval" -- mentioned twice, not acted on
- Stagnant goal: "publish go-to-market doc" -- in MEMORY.md 14+ days, no Work Log entry

### No action required
- my-dashboard CLAUDE.md: all entries referenced recently, no stale flags

### Graph health
- Graph: N concepts, M edges, K projects
- Maturity: [which graph health criteria are met / not met]
- Mature signals: [concepts with strength >= 3 edges]

### Constraint governance
Scanned: N constraint-type entries in learnings.md
Covered: M (have matching CLAUDE.md rule + deny pattern where applicable)
Gaps: K

Unprotected:
- learnings.md L42: "[entry text]" -- no matching CLAUDE.md rule
- learnings.md L73: references "ProjectX" -- no deny pattern in publish-audit.sh

Recommendations:
- Add to AGENTS.md Rules (universal) or CLAUDE.md (Claude-specific): [proposed rule text]
- Add to publish-audit.sh DENY_PATTERNS: 'pattern'

### File hygiene
- MEMORY.md size: N KB (warn at 15KB, error at 24KB)
- Long index entries: K entries over 200 chars (should be ≤150) -- examples: [entry 1], [entry 2]
- learnings.md scope violations: K entries with project/path/regex/SHA markers -- examples: [text 1]
- Topic file orphans: [list unreferenced .md files in memory dir]
- Rule duplication: [duplicated sentences between AGENTS.md and CLAUDE.md]

Recommendations:
- Extract long index entries to new topic files
- Route learnings.md violations to project playbook per /save strict scope test
- Archive or index orphan topic files
```

Keep each entry to one line. No paragraphs. The log is a feed, not a document.

After writing, check if there are unreviewed signals (promotion-eligible concepts, stale entries, or unreviewed reflect-log findings). If so, append to the output:

```
[If unreviewed signals exist]: Run /review to triage N pending signals.
```

After writing, update the timestamp. Use python3 (covered by allowed-tools) to avoid shell redirect permission prompts:
```bash
python3 -c "import time, pathlib; pathlib.Path.home().joinpath('.claude','reflect-last-run').write_text(str(int(time.time())))"
```

---

## What /reflect never does

These are hard constraints. Violating any of them is a bug.

1. **Never writes to MEMORY.md.** Reflect reads MEMORY.md but never modifies it. All findings go to reflect-log.md only.
2. **Never writes to project AGENTS.md files or daily notes.** It surfaces findings. You decide what to act on.
3. **Never auto-promotes entries to root CLAUDE.md.** It recommends promotions in the report. A human reviews and acts.
4. **Never deletes stale entries.** It flags them as `[STALE?]`. Deletion is a human decision.
5. **Never runs synchronously during a session.** Always async (Stop hook) or manual invocation. It must not block interactive work.
6. **Never reads full session transcripts.** Too expensive (full transcripts can be 100K+ tokens). The daily notes are the already-distilled record.
7. **Never analyzes code directly.** It analyzes the memory files that describe code decisions, not source code itself.

---

## Companion SessionStart hook

To surface reflect findings at the start of the next session, add:

```bash
#!/usr/bin/env bash
# ~/.claude/scripts/reflect-surface.sh
# If a reflect ran since last session, inject the latest reflect-log entry as context.

REFLECT_LOG="${REFLECT_LOG:-2-areas/me/reflect-log.md}"
LAST_SESSION="$HOME/.claude/reflect-last-surfaced"
NOW=$(date +%s)

if [ ! -f "$REFLECT_LOG" ]; then exit 0; fi

if [ -f "$LAST_SESSION" ]; then
  LAST=$(cat "$LAST_SESSION")
  # Only surface if reflect ran after last surface
  REFLECT_TIME=$(stat -f %m "$REFLECT_LOG" 2>/dev/null || stat -c %Y "$REFLECT_LOG")
  if [ "$REFLECT_TIME" -le "$LAST" ]; then exit 0; fi
fi

# Extract the most recent reflect entry (from last ## Reflect header to next one)
LATEST=$(awk '/^## Reflect/{found=1; count++} found && count==1{print} /^## Reflect/ && count>1{exit}' "$REFLECT_LOG")

echo "$LATEST"
echo "$NOW" > "$LAST_SESSION"
```

---

## Design notes

**Why not run on every Stop?** Too expensive and too noisy. The gate threshold (15 turns or 24h elapsed) ensures consolidation runs after sessions where enough happened to generate signal. A 3-turn session asking one question does not warrant a reflect pass.

**Why append-only to reflect-log.md?** The log is an audit trail. You want to see not just the current state of signals but when they first appeared and how they evolved. Overwriting would destroy that. Prune old entries manually every few weeks.

**Why 7 daily notes for stale detection?** Seven days is roughly one working week. If an entry has not come up in a week of active work, it is either stale or belongs in cold storage. 14 days would catch more false positives; 3 days would be too aggressive.

**Why no auto-write to MEMORY.md?** Trust. The reflect pass makes inferences. Inferences can be wrong. You need to review before anything gets encoded as ground truth. The report is advisory; MEMORY.md is authoritative.
