---
name: dream
description: "Background memory consolidation. Reviews MEMORY.md, project CLAUDE.md files, and daily notes for patterns, stale entries, cross-project signals, and promotion candidates. Runs automatically post-heavy-session (Stop hook) or manually via /dream. Writes a consolidation report to the configured dream log path. Never blocks. Never auto-promotes."
disable-model-invocation: true
argument-hint: [optional focus area or project scope]
allowed-tools: Read, Write, Edit, Glob, Bash(~/.cortex/concepts *), Bash(python3 -c *)
---

# /dream -- Background Memory Consolidation

A lightweight consolidation pass that runs after heavy sessions or on demand. It does not save session state -- /save does that. It reads what has already been saved and looks for what it implies: patterns across sessions, stale entries that should be pruned, connections between projects, and ideas that have appeared multiple times without being promoted.

The metaphor is accurate: this is not data entry. It is re-indexing.

---

## Configuration

Read `.memory-config` from the workspace root (same directory as `.claude/`). Parse as simple `key: value` pairs (one per line, ignore comments starting with `#`). If the file does not exist, use PARA defaults.

| Variable | Config key | Default |
|---|---|---|
| `$DAILY_DIR` | `daily_dir` | `2-areas/me/daily` |
| `$LEARNINGS` | `learnings` | `2-areas/me/learnings.md` |
| `$DREAM_LOG` | `dream_log` | `2-areas/me/dream-log.md` |
| `$PROJECT_ROOT` | `project_root` | `1-projects` |
| `$WORKSPACE` | `workspace` | `personal` |

All path references in this document use these variables. Resolve them before reading any files.

---

## Trigger Logic

Dream runs in two modes:

### 1. Automatic post-session (Stop hook, async)

The gate script `dream-gate.sh` decides whether to run a full consolidation:

```bash
#!/usr/bin/env bash
# ~/.claude/scripts/dream-gate.sh
# Decide whether this session is heavy enough to warrant a dream pass.
# Inputs: CLAUDE_SESSION_TURN_COUNT (env var from hook context)

TURN_COUNT="${CLAUDE_SESSION_TURN_COUNT:-0}"
LAST_DREAM="$HOME/.claude/dream-last-run"
NOW=$(date +%s)

# Run if: session had 15+ turns, OR last dream was 24h+ ago
if [ "$TURN_COUNT" -ge 15 ]; then
  echo "dream:trigger:heavy-session turns=$TURN_COUNT" >> "$HOME/.claude/dream-gate.log"
  exit 0  # signal to proceed
fi

if [ -f "$LAST_DREAM" ]; then
  LAST=$(cat "$LAST_DREAM")
  DIFF=$((NOW - LAST))
  if [ "$DIFF" -ge 86400 ]; then
    echo "dream:trigger:daily-elapsed diff=${DIFF}s" >> "$HOME/.claude/dream-gate.log"
    exit 0
  fi
fi

exit 1  # skip
```

Exit 0 = proceed with dream. Exit 1 = skip. Since this is an async hook on Stop, exit code does not block the session.

### 2. Manual (/dream)

Run at any time. Useful after a large planning session, a naming decision, or a multi-project context switch.

---

## What /dream reads

Before running any analysis, locate and read these files. All paths are relative to the workspace root unless noted.

| File | Path | What to read |
|---|---|---|
| MEMORY.md | `~/.claude/projects/<project-key>/memory/MEMORY.md` (where project-key is the workspace path with `/` replaced by `-`) | Full file, especially Promotion Queue section |
| Dream log | `$DREAM_LOG` | Last entry only (to avoid duplicating findings) |
| Learnings | `$LEARNINGS` | Full file |
| Daily notes | `$DAILY_DIR/YYYY-MM-DD.md` | Last 7 files by date; read only Work Log and Tasks sections |
| Project CLAUDE.md files | `$PROJECT_ROOT/*/CLAUDE.md` (use `find $PROJECT_ROOT -name "CLAUDE.md" -maxdepth 3`) | Friction Log, Decision Register, and architecture sections |

Do not read full session transcripts. Too expensive and too noisy. The daily notes are the already-distilled record.

---

## Graph pre-check (requires concepts CLI)

Before running analysis passes, check for `dream-context.json` in the workspace root:

1. **File exists:** Validate freshness by running:
   ```bash
   ~/.cortex/concepts dream-prep --verify
   ```
   - Exit code 0 (prints "fresh"): graph data is current. Use it in analysis passes below
   - Exit code 1 (prints "stale: ..."): warn `"Graph data stale. Run 'concepts dream-prep' for fresh data."` Continue without graph data
   - If the `concepts` CLI is not available, check `generated_at` timestamp. If older than 1 hour, treat as stale
2. **File does not exist:** Continue without graph data. This is expected before the first /save with cortex installed

When graph data is available, the variable `$GRAPH_DATA` refers to the parsed dream-context.json contents.

---

## Analysis passes

Run each pass in sequence. Each pass is cheap (pattern match over structured text). Only the signal surfacing requires model reasoning.

### Pass 1: Stale detection

**Input:** All entries in MEMORY.md, all entries in each project CLAUDE.md under `$PROJECT_ROOT/`, the last 7 daily notes from `$DAILY_DIR/`.
**Output:** A list of `[STALE?]` flags for the dream-log.md Stale Flags section.

1. Extract every discrete entry (bullet point, decision, or note) from MEMORY.md.
2. Extract every discrete entry from each project CLAUDE.md found under `$PROJECT_ROOT/`.
3. For each entry, extract 2-3 key terms (proper nouns, tool names, concept names).
4. Grep the last 7 daily notes for each key term. If zero matches across all 7 notes AND the entry is not tagged `[permanent]`, mark as `[STALE?]`.
5. For Decision Register entries tagged `[revisit]`, compute days since the entry date. If older than 14 days, flag as overdue for revisit.

### Pass 2: Friction promotion

**Input:** Friction Log sections from each project CLAUDE.md under `$PROJECT_ROOT/`.
**Output:** A list of friction escalations for the dream-log.md Friction Escalations section.

1. Collect all Friction Log entries from every project CLAUDE.md.
2. For each unique friction description, count distinct date prefixes (each entry has a date prefix).
3. If 3+ appearances: add to the report as "automation candidate".
4. If 5+ appearances: write a task to the next daily note: "Build fix for: [friction description]".
5. If fewer than 3 appearances: skip. One-off friction is noise. Three recurrences is a pattern. Five recurrences is a cost.

### Pass 3: Cross-project signal detection

**Input:** All project CLAUDE.md files under `$PROJECT_ROOT/`, MEMORY.md, the last 7 daily notes.
**Output:** 3-5 signal entries for the dream-log.md Cross-Project Signals section, each classified as OPPORTUNITY, RISK, or CONVERGENCE.

**When $GRAPH_DATA is available**, use structured graph data instead of raw text matching:
- Use `shared_concepts` for cross-project signals (replaces pairwise concept comparison)
- Use `hot_concepts` for concept velocity and trending patterns
- Use `stale_concepts` as additional input for stale detection (supplement Pass 1)
- Classify signals as before (OPPORTUNITY / RISK / CONVERGENCE) with higher confidence when backed by graph data with edge strength >= 2

This is the second-brain pass. It requires model reasoning (string matching alone cannot detect conceptual overlap).

1. Extract all named concepts, tools, decisions, and problem areas from each project CLAUDE.md.
2. Compare pairwise across projects. For each concept appearing in 2+ projects, classify as:
   - **OPPORTUNITY**: shared abstraction, reusable component, or naming convergence.
   - **RISK**: conflicting assumptions, architectural contradiction, or unacknowledged dependency.
   - **CONVERGENCE**: multiple workstreams with the same underlying need.
3. Write exactly 3-5 signal entries. If more than 5 candidates exist, rank by number of cross-project appearances and keep the top 5.

Examples of what this catches:

- Two projects both have an "eval rerun" concept in separate CLAUDE.md files. Dream detects overlap. Surfaces: "Shared concept: eval rerun -- potential shared module or API boundary."
- One project uses an exponential backoff pattern. MEMORY.md has a mental model about retry logic. Dream connects them and notes the mental model should reference the implementation as a concrete example.
- A decision in one project assumes a specific data format. A different project's architecture note contradicts it silently. Dream flags the conflict.

### Pass 4: Promotion queue review

**Input:** The `## Promotion Queue` section in MEMORY.md, the last 7 daily notes.
**Output:** Promotion recommendations for the dream-log.md Promotion Queue section.

1. Read each candidate in the Promotion Queue.
2. For each candidate, grep the last 7 daily notes for related terms.
3. If related work is still active (1+ matches in daily notes): mark as "still relevant".
4. If the candidate concept has appeared again since it was queued (check daily notes for new mentions after the queue date): increase urgency and note the new occurrence.
5. If a candidate is both still relevant and has appeared 3+ times total: surface as "ready for root CLAUDE.md" in the report.
6. Do not auto-promote. Write the recommendation and stop.

### Pass 5: Idea and opportunity graph update

**Input:** `$LEARNINGS`, the last 14 daily notes from `$DAILY_DIR/`.
**Output:** Dormant signal entries for the dream-log.md Dormant Signals section.

1. Read `$LEARNINGS` in full and the Work Log section of the last 14 daily notes.
2. Extract all ideas, goals, and interests mentioned in learnings.md.
3. For each idea or goal, search the 14 daily notes for mentions (use loose matching: same concept, different phrasing counts).
4. If an idea appears in 2+ daily notes but has no corresponding Work Log entry: flag as "dormant idea, mentioned N times, not acted on".
5. If a stated goal from learnings.md has zero Work Log entries in the last 14 days: flag as "stagnant goal".
6. If an interest or growth area from learnings.md connects to an active project (appears in a project CLAUDE.md): flag as "connection opportunity" with the project name.

### Pass 6: Graph health (requires concepts CLI)

**Input:** `$GRAPH_DATA` (if available). Skip this pass if no graph data.
**Output:** A graph health section in the dream-log entry.

1. Report graph summary: N concepts, M edges, K projects, N normalization rules
2. Flag any graph maturity metrics below threshold:
   - Fewer than 10 concepts
   - Fewer than 2 projects
   - No edges with strength >= 3
   - No cross-project concepts
3. Surface concepts with edge strength >= 3 (mature signals worth reviewing)
4. Note extraction rate trends if stats data shows velocity change
5. If graph data was stale, note that and recommend running dream-prep

---

## Output: dream-log.md entry

Append to `$DREAM_LOG`:

```markdown
## Dream -- YYYY-MM-DD HH:MM [trigger: heavy-session|manual]

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
```

Keep each entry to one line. No paragraphs. The log is a feed, not a document.

After writing, update the timestamp. Use python3 (covered by allowed-tools) to avoid shell redirect permission prompts:
```bash
python3 -c "import time, pathlib; pathlib.Path.home().joinpath('.claude','dream-last-run').write_text(str(int(time.time())))"
```

---

## What /dream never does

These are hard constraints. Violating any of them is a bug.

1. **Never writes to MEMORY.md.** Dream reads MEMORY.md but never modifies it. All findings go to dream-log.md only.
2. **Never writes to project CLAUDE.md files or daily notes.** It surfaces findings. You decide what to act on.
3. **Never auto-promotes entries to root CLAUDE.md.** It recommends promotions in the report. A human reviews and acts.
4. **Never deletes stale entries.** It flags them as `[STALE?]`. Deletion is a human decision.
5. **Never runs synchronously during a session.** Always async (Stop hook) or manual invocation. It must not block interactive work.
6. **Never reads full session transcripts.** Too expensive (full transcripts can be 100K+ tokens). The daily notes are the already-distilled record.
7. **Never analyzes code directly.** It analyzes the memory files that describe code decisions, not source code itself.

---

## Companion SessionStart hook

To surface dream findings at the start of the next session, add:

```bash
#!/usr/bin/env bash
# ~/.claude/scripts/dream-surface.sh
# If a dream ran since last session, inject the latest dream-log entry as context.

DREAM_LOG="${DREAM_LOG:-2-areas/me/dream-log.md}"
LAST_SESSION="$HOME/.claude/dream-last-surfaced"
NOW=$(date +%s)

if [ ! -f "$DREAM_LOG" ]; then exit 0; fi

if [ -f "$LAST_SESSION" ]; then
  LAST=$(cat "$LAST_SESSION")
  # Only surface if dream ran after last surface
  DREAM_TIME=$(stat -f %m "$DREAM_LOG" 2>/dev/null || stat -c %Y "$DREAM_LOG")
  if [ "$DREAM_TIME" -le "$LAST" ]; then exit 0; fi
fi

# Extract the most recent dream entry (from last ## Dream header to next one)
LATEST=$(awk '/^## Dream/{found=1; count++} found && count==1{print} /^## Dream/ && count>1{exit}' "$DREAM_LOG")

echo "$LATEST"
echo "$NOW" > "$LAST_SESSION"
```

---

## Design notes

**Why not run on every Stop?** Too expensive and too noisy. The gate threshold (15 turns or 24h elapsed) ensures consolidation runs after sessions where enough happened to generate signal. A 3-turn session asking one question does not warrant a dream pass.

**Why append-only to dream-log.md?** The log is an audit trail. You want to see not just the current state of signals but when they first appeared and how they evolved. Overwriting would destroy that. Prune old entries manually every few weeks.

**Why 7 daily notes for stale detection?** Seven days is roughly one working week. If an entry has not come up in a week of active work, it is either stale or belongs in cold storage. 14 days would catch more false positives; 3 days would be too aggressive.

**Why no auto-write to MEMORY.md?** Trust. The dream pass makes inferences. Inferences can be wrong. You need to review before anything gets encoded as ground truth. The report is advisory; MEMORY.md is authoritative.
