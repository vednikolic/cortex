---
name: save
description: "Save session learnings to auto-memory. Summarizes what was done, checks for recurring patterns, detects friction and emerging signals, and updates MEMORY.md, project CLAUDE.md, learnings.md, and the daily note. Run at the end of a session or after completing meaningful work."
disable-model-invocation: true
argument-hint: [optional focus area]
allowed-tools: Bash(~/.cortex/concepts *)
---

# /save -- Save Session to Memory

Capture what happened this session and persist it to the right place. Then look for signals -- patterns, friction, emerging connections -- that should influence future sessions.

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

All path references in this document use these variables. Resolve them once at the start of the workflow (Step 1).

---

## Key Principle: Global vs Project Memory

**Global MEMORY.md** (`$MEMORY_DIR/MEMORY.md`): Cross-project knowledge only.
- User preferences and workflow decisions
- Environment setup (tooling, Python versions, paths)
- Pointers to active projects (one line each: name, status, location)
- Repeatable workflows (command sequences you run regularly)
- Mental models (how you conceptualize a domain -- these are highest-value continuity assets)
- Learnings that apply across multiple projects
- `## Promotion Queue`: pattern candidates that have appeared 2+ times, waiting for review

**Project CLAUDE.md** (e.g., `$PROJECT_ROOT/my-app/CLAUDE.md`): Project-specific details.
- Architecture decisions, implementation state, open items
- Project-specific gotchas and conventions
- Phase/milestone tracking
- Tech stack details, test counts, DB sizes, etc.
- `## Friction Log`: repeated pain points and automation candidates
- `## Decision Register`: choices with confidence tags and rationale

**Personal learnings** (`$LEARNINGS`): User-specific patterns.
- Working style observations (how the user thinks, decides, communicates)
- Preferences that emerge from behavior, not just stated rules
- Collaboration patterns (what works well, what to avoid)
- Growth areas and interests observed over time

**Daily notes** (`$DAILY_DIR/YYYY-MM-DD.md`): Daily work log and task tracker.
- What was accomplished today (work log entries), with rough time anchors
- Tasks created for next steps and follow-ups
- Carried-over incomplete tasks from the previous day
- Blockers or waiting-on items

**Rule of thumb**: if it only matters for one project, it goes in that project's CLAUDE.md. If it is about you as a person, it goes in `$LEARNINGS`. If it is cross-project tooling or environment, it goes in MEMORY.md. If it is a concrete action or task, it goes in the daily note.

---

## Workflow

### Step 1: Load config and locate memory files

Read `.memory-config` from the workspace root. If present, parse `key: value` pairs and set the variables from the Configuration table above. If absent, use the PARA defaults.

```bash
MEMORY_DIR="$HOME/.claude/projects/$(pwd | sed 's|/|-|g')/memory"
TODAY=$(date +%Y-%m-%d)
DAILY_FILE="$DAILY_DIR/$TODAY.md"
```

Read `$MEMORY_DIR/MEMORY.md` if it exists. Note current line count and any open items in `## Promotion Queue`.

Determine if the session was project-scoped. If work was done under a specific project directory (e.g., `$PROJECT_ROOT/my-app/`), read that project's CLAUDE.md too -- including its Friction Log and Decision Register.

Check if `$DAILY_FILE` exists. If it does, read it. If not, create it in Step 5 after checking the previous day for carry-over tasks.

---

### Step 2: Summarize this session

Review the full conversation and extract:

- **What was done**: Concrete actions (files created, bugs fixed, features added, configs changed). Tag with rough time anchor if detectable (`~morning`, `~afternoon`, `~2h block`).
- **Decisions made**: Choices with rationale and confidence level. Tag each as `[settled]`, `[tentative]`, or `[revisit]`.
- **Friction observed**: Any point where you ran the same command multiple times, hit the same error type again, worked around a missing abstraction, or context-switched unexpectedly. These are friction candidates.
- **Learnings**: Things discovered that would be useful in future sessions.
- **Connections detected**: Did this session's work touch concepts from another project, past decision, or stated goal? Note it.
- **Unfinished work**: Anything started but not completed, or next steps identified.

If the user provided a focus area via `$ARGUMENTS`, prioritize that topic.

---

### Step 3: Route entries

For each item from Step 2, decide where it belongs:

| Entry type | Destination |
|---|---|
| Project architecture, implementation details, open items | Project CLAUDE.md |
| Project decisions | Project CLAUDE.md -> `## Decision Register` |
| Repeated friction, automation candidates | Project CLAUDE.md -> `## Friction Log` |
| Phase/milestone status | Project CLAUDE.md |
| Test counts, DB sizes, file counts | Project CLAUDE.md |
| Cross-project tooling decisions | Global MEMORY.md |
| Repeatable command sequences | Global MEMORY.md |
| Mental models (how you think about a domain) | Global MEMORY.md |
| Environment info (Python paths, system setup) | Global MEMORY.md |
| Active project pointer | Global MEMORY.md |
| Patterns appearing 2+ times | Global MEMORY.md -> `## Promotion Queue` |
| User working style, communication preferences | `$LEARNINGS` |
| Observed interests, growth areas | `$LEARNINGS` |
| Concrete work done this session | Daily note -> Work Log |
| Next steps, follow-ups, tasks | Daily note -> Tasks |
| Blockers or external waiting items | Daily note -> Notes |

**Memory routing for cross-project tooling**: distinguish between three subtypes:

1. **Environment facts** -- paths, versions, system config. Goes in MEMORY.md under `## Environment`. Example entries as they would appear in MEMORY.md:
```
- System Python is 3.9.6 (macOS); use Homebrew Python 3.12 at /opt/homebrew/bin/python3.12
- Homebrew poppler installed for PDF reading support
```

2. **Repeatable workflows** -- command sequences, scripts, standard operating steps. Goes in MEMORY.md under `## Workflows`. Example entries:
```
- GitHub subtree publish: git subtree split --prefix=1-projects/[name] --branch release && git push standalone release:main
- Autoresearch run: copy SKILL.md to target.md, run eval.py baseline, begin loop
```

3. **Mental models** -- how you conceptualize a problem domain. Goes in MEMORY.md under `## Mental Models`. These are the highest-value entries. Example entries:
```
- Treat eval coverage like test coverage -- block on red, never ship with regressions
- Skills are prompts, not code -- optimize for clarity and determinism over cleverness
```

---

### Step 4: Check for patterns and signals

This step is the second-brain layer. Go beyond what happened and look for what it implies.

**Pattern checks**:

1. **Duplicates**: Already captured? Skip.
2. **Reinforcement**: Confirms an existing entry? Increment a tally or mark as promotion candidate.
3. **Contradiction**: Conflicts with an existing entry? Flag with `[CONFLICT: ...]` note for review.
4. **Stale**: Existing entry not referenced in 10+ sessions? Flag as `[STALE?]` in the report.

**Friction detection**: For every item in the Friction Log, check:
- Has this friction appeared 2+ times? Surface it in the report as an automation or abstraction candidate.
- Is there an obvious fix (alias, script, template, workflow step)? Propose it.

**Signal detection** -- actively look for:
- **Opportunity connections**: Does something done in this session connect to a stated goal, a past idea, or another active project? Example: a workaround built for project-A might directly solve a design problem in project-B.
- **Risk signals**: Did a decision made here create a dependency, assumption, or constraint that could collide with something elsewhere? Example: a schema choice in one project that contradicts an architecture principle recorded in MEMORY.md.
- **Convergence**: Are multiple separate workstreams pointing toward the same underlying need? This often surfaces the right abstraction to build next.

**Concrete signal scenarios**:

Scenario 1 (Opportunity): You built a retry-with-backoff wrapper in project-A this session. MEMORY.md has a mental model entry: "treat transient failures with exponential backoff." Project-B's CLAUDE.md lists "flaky API calls" in its Friction Log. Signal entry:
```
Opportunities: project-A retry wrapper maps directly to project-B flaky API friction -- reusable module candidate
```

Scenario 2 (Risk): You chose SQLite for local storage in project-A this session. Project-B's Decision Register says "[tentative] Use Postgres for all persistence." These assumptions conflict silently. Signal entry:
```
Risks: project-A chose SQLite for local storage; project-B assumes Postgres for all persistence -- conflicting data layer assumptions
```

Scenario 3 (Convergence): This session you added event logging to project-A. Last week's daily notes show you added telemetry to project-B and cost tracking to project-C. All three need a lightweight event bus. Signal entry:
```
Convergence: project-A event logging + project-B telemetry + project-C cost tracking all need a shared event bus abstraction
```

Surface detected signals in Step 7 under `Signals`.

**Stale detection**: Entry not referenced in 10 sessions -> flag automatically in the Step 7 report. Do not auto-delete. Let the user decide.

---

### Step 4b: Concept extraction (requires concepts CLI)

**Skip this step entirely if:**
- The `--sensitive` flag was provided
- `~/.cortex/concepts` does not exist (cortex not installed)
- The session had no meaningful content (pure Q&A with no decisions, tools, or patterns)

**Auto-init:** If `~/.cortex/concepts` exists but `concepts.db` does not exist in the workspace root, run `~/.cortex/concepts init` to create it. This is the normal first-run path.

**1. Compute session weight:**

From the Step 2 summary, estimate:
- `token_count`: short session < 5000, medium 5000-15000, long > 15000 tokens
- `concepts`: count of distinct topics, tools, or patterns identified
- `decisions`: count of decisions logged
- `friction`: count of friction points identified

The weight formula is: `weight = 1 + (token_count>5000) + (concepts>=2) + (decisions>=1) + (friction>=1)`, capped at 5.

The extraction cap by weight: weight 1-2 allows up to 3 concepts, weight 3 up to 5, weight 4-5 up to 8.

**2. Query existing vocabulary:**

```bash
~/.cortex/concepts --json list
```

This returns all concept names with their kind, confidence, and source count. Use this to match proposed concepts against existing vocabulary before creating new entries. Also run `~/.cortex/concepts --json graph` to get edge and project counts for context.

**3. Propose concepts:**

From the session summary, identify up to the extraction cap number of concepts that:
- Represent tools, patterns, decisions, or recurring themes (not ephemeral details)
- Map against existing vocabulary first (prefer matching over creating new)
- Have at least one clear relationship to another concept

For each concept, determine:
- `name`: canonical name (check existing vocabulary)
- `kind`: one of topic, tool, pattern, decision, person, project
- Relationships: edges to existing or co-proposed concepts, with relation type from: related-to, depends-on, conflicts-with, enables, is-instance-of, supersedes, blocked-by, derived-from

**4. Execute extraction:**

Compute a session hash: `hashlib.md5((session_summary + ISO_timestamp).encode()).hexdigest()[:16]`

Determine the project name from the working directory or `.memory-config` `projects:` section.

For each proposed concept:
```bash
~/.cortex/concepts upsert "$name" --kind $kind --project "$project" --session "$session_hash" --weight $weight
```

For each relationship:
```bash
~/.cortex/concepts edge "$from" "$to" "$relation" --session "$session_hash"
```

Concepts that do not meet quality threshold (too generic, already fully captured, ephemeral) are counted as rejected but their names are NOT logged. Only the rejected count is stored.

**5. Log the extraction:**

After all upserts and edges are created, log the extraction event. This is critical for undo-last support and future analysis.

```bash
~/.cortex/concepts log-extraction --session "$session_hash" \
  --proposed '["concept1", "concept2"]' \
  --created '["concept1"]' \
  --edges '[{"from": "concept1", "to": "existing", "relation": "related-to"}]' \
  --rejected 1 \
  --weight $weight
```

Alternatively, if calling from Python within the /save skill context, use the `log_extraction` function directly. The key fields are:
- `session_hash`: unique per extraction (includes ISO timestamp)
- `concepts_proposed`: all concepts considered (JSON array of names)
- `created_concepts`: concepts actually created or updated (JSON array)
- `created_edges`: edges created (JSON array of {from, to, relation} objects)
- `rejected`: integer count of concepts that did not meet quality threshold
- `weight`: session weight computed in sub-step 1

**6. Report graph status (graph warming UX):**

After extraction, append a graph status line to the Step 7 report:

```
Graph: N concepts, M edges, K projects.
```

At specific thresholds, add invitations:
- At 5+ concepts: `Tip: Run 'concepts graph' to see your knowledge graph.`
- At 10+ concepts across 2+ projects: `Your graph is ready for full /dream integration. Run 'concepts dream-prep' before your next /dream.`

---

### Step 5: Write daily note

**Location:** `$DAILY_DIR/YYYY-MM-DD.md`

**If the file does not exist (new day):**

1. Find the most recent previous daily note in `$DAILY_DIR/` (sort by filename descending, take the first that is not today).
2. If a previous note exists, read it and extract any tasks marked `[ ]`. These are carry-over tasks. If no previous daily note exists (first time using the system), skip carry-over and create the note with only today's entries.
3. Create the new daily note:

```markdown
# YYYY-MM-DD

## my-app
### Work Log
- (~morning) Fixed container startup race condition in deploy pipeline
### Tasks
- [ ] Add integration test for classification edge cases

## my-api
### Work Log
- (~afternoon) Drafted naming candidates for new product
### Tasks
- [ ] Evaluate top 3 naming candidates on memorability criteria
- [ ] Decide: separate service or monolith module? (carry over)

## Other
### Work Log
- Updated global MEMORY.md with new venv convention
### Tasks
- [ ] Review Promotion Queue items before next session

## Notes
- Blocked on design review until Thursday
```

**Grouping rules:**
- Group by project heading using the directory name (`my-app`, `my-api`, `my-dashboard`).
- Use `## Other` for entries not tied to a specific project.
- Include time anchors in Work Log where detectable.
- Carry-over tasks get `(carry over)` suffix.
- Only include sections that have entries.
- Order sections by most work done this session (heaviest first).

**If the file already exists (same day, later session):**

1. Read existing file.
2. Find or create the project section for each project touched.
3. Append new Work Log entries and new Tasks.
4. Mark completed tasks `[x]`.

---

### Step 6: Write memory entries

**Global MEMORY.md** -- append under session header:

```markdown
## Session YYYY-MM-DD
- [cross-project learning, one line each]
- [new repeatable workflow, one line]
- [new mental model, one line]

## Promotion Queue
- "[pattern]" -- seen N times, source: [project or area]
```

**Project CLAUDE.md** -- update or create sections as needed:

```markdown
## Current State
- [implementation status, open items, recent changes]

## Decision Register
- [YYYY-MM-DD] Chose X over Y -- [one-line rationale] [settled|tentative|revisit]

## Friction Log
- [YYYY-MM-DD] [description of friction] -- candidate: [proposed fix]
```

**Personal learnings** (`$LEARNINGS`):

```markdown
## Working Style
- [observed pattern]

## Preferences
- [preference that emerged from behavior]
```

**Rules for all files:**
- One line per entry. No paragraphs.
- Skip trivial actions (reading files, running git status).
- Do not store sensitive data.
- Consolidate rather than duplicate.
- Do not auto-delete; flag stale items for user review.

**Prioritization when MEMORY.md is near the 200-line limit** (150+ lines):
1. **Always write**: decisions, mental models, environment changes -- high-value, low-volume.
2. **Write if new**: repeatable workflows, cross-project patterns -- skip if a similar entry exists.
3. **Defer to daily note**: promotion queue items, project pointers -- update existing entries instead of adding.
4. **Skip entirely**: session-specific learnings for one project -- write to that project's CLAUDE.md instead.
If a session produces 8+ items for MEMORY.md, consolidate related entries before writing.

---

### Step 7: Report

```
Session saved.

Daily note ($DAILY_DIR/YYYY-MM-DD.md):
  Work: [summary of work log entries added]
  Tasks: [N new, N carried over, N completed]

Global MEMORY.md ([n]/200 lines):
  [new global entries, if any]

Project CLAUDE.md ([project name]):
  Decisions: [new entries with confidence tags]
  Friction: [new friction entries]

Personal learnings ($LEARNINGS):
  [new or updated observations]

Signals:
  Opportunities: [cross-project connections detected]
  Risks: [constraints or conflicts detected]
  Convergence: [workstreams pointing to the same need]

Patterns:
  Promotion candidates: [entries appearing 2+ times]
  Stale flags: [entries not referenced in 10+ sessions]
  Automation candidates: [friction appearing 2+ times]

```

---

### Step 8: Act on high-confidence signals

Do not wait for the user to notice. If a signal is clear, act on it within the session:

- **Friction with an obvious fix**: Propose the alias, script, or template immediately. If it is a one-liner, write it now.
- **Opportunity connection**: Briefly name it and ask if you should explore it. Example: "The retry logic you just built in project-A maps directly to the flaky API problem in project-B -- want me to sketch a shared abstraction?"
- **Risk signal**: Surface it clearly before the session ends. Do not bury it in the report.

For ambiguous signals, surface them and ask. Do not act autonomously on anything that touches architecture, naming, or project direction.

---

### Step 9: Check for rule promotions

If any learning appears 2+ times, or is phrased as a universal principle, suggest promotion to the root CLAUDE.md:

```
Potential CLAUDE.md rules:
  "[pattern]" -- seen N times, could be a standing rule
```

Do not auto-promote. Always let the user decide.

---

## What NOT to save

- **Temporary context that only matters right now.** Bad: `- Currently debugging a failing test in my-app/tests/test_classify.py`. This is session state, not a learning. If the bug reveals a pattern, save the pattern, not the debugging step.
- **File contents or code snippets.** Bad: `- Added retry logic: \`for i in range(3): try: ... except: sleep(2**i)\``. Save the file path and the decision rationale instead: `- Added retry with exponential backoff to API client (my-app/src/client.py)`.
- **Meta-conversation.** Bad: `- User asked me to refactor the auth module and I suggested using middleware`. The refactoring outcome matters, not the conversation about it.
- **Anything already captured in the target file.** If MEMORY.md already says `Use per-project venvs with Python 3.12`, do not add it again. Consolidate or update the existing entry.
- **Sensitive data.** Bad: `- API key for staging: sk-abc123...`. Never save credentials, tokens, secrets, or PII. Reference the secret manager or env var name instead.
