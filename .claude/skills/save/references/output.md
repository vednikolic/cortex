# Output Templates

Used by `/save` Steps 5, 6, and 7 (write files, emit report). Read this when writing to any destination or emitting the final report.

## Daily note

Location: `$DAILY_DIR/YYYY-MM-DD.md`.

### New-day template (file does not exist)

1. Find the most recent previous daily note (sort `$DAILY_DIR/` filenames descending, take first that is not today).
2. Extract any `[ ]` tasks from it as carry-overs. If no previous note exists, skip carry-over.
3. Create the new file with this structure:

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

### Grouping rules

- Group by project heading using the directory name
- Use `## Other` for entries not tied to a specific project
- Include time anchors in Work Log where detectable
- Carry-over tasks get `(carry over)` suffix
- Only include sections that have entries
- Order sections by most work done this session (heaviest first)

### Same-day append (file already exists)

1. Read existing file
2. Find or create the project section for each project touched
3. Append new Work Log entries and new Tasks
4. Mark completed tasks `[x]`

## MEMORY.md entry

Append under session header. One-line entries, ≤150 chars.

```markdown
## Session YYYY-MM-DD
- [cross-project learning, one line each]
- [new repeatable workflow, one line]
- [new mental model, one line]

## Promotion Queue
- "[pattern]" -- seen N times, source: [project or area]
```

## Project AGENTS.md entry

Update or create sections as needed:

```markdown
## Current State
- [implementation status, open items, recent changes]

## Decision Register
- [YYYY-MM-DD] Chose X over Y -- [one-line rationale] [settled|tentative|revisit]

## Friction Log
- [YYYY-MM-DD] [description of friction] -- candidate: [proposed fix]
```

## Project playbook entry

`$PROJECT_ROOT/<name>/playbook.md`. Create if missing. Append to existing numbered section or add a new section with a TOC entry at the top.

```markdown
## N. <Section Name>

<Pattern or rule statement in one sentence.>

**Proof (YYYY-MM-DD, <phase/task>):** <concrete evidence: file, commit SHA, command output, or observed behavior>.

**Rule:** <generalizable form of the pattern>.

**Candidate for <skill-name> skill:** <if applicable, what should migrate out of this playbook into a skill update>.
```

Every playbook entry keeps its dated proof point. The generalized rule sits above the proof so a future reader can skip the proof unless they want to verify. Skill-update candidates surface inline so future skill maintenance finds them.

## Personal learnings entry

`$LEARNINGS`. Run the scope test from `routing.md` before writing. One line per entry.

```markdown
## Working Style
- [observed trait about how the user thinks, decides, communicates]

## Preferences
- [preference that emerged from behavior]
```

## Rules for all files

- One line per entry in learnings.md, MEMORY.md, and project AGENTS.md. Playbook entries can be multi-paragraph with dated proof points
- Skip trivial actions (reading files, running git status)
- Do not store sensitive data
- Consolidate rather than duplicate
- Do not auto-delete; flag stale items for user review

## Prioritization when MEMORY.md is near limit (150+ lines)

1. **Always write**: decisions, mental models, environment changes -- high-value, low-volume
2. **Write if new**: repeatable workflows, cross-project patterns -- skip if a similar entry exists
3. **Defer to daily note**: promotion queue items, project pointers -- update existing instead of adding
4. **Skip entirely**: session-specific learnings for one project -- write to that project's AGENTS.md instead

If a session produces 8+ items for MEMORY.md, consolidate related entries before writing.

## Report template (Step 7)

```
Session saved.

Concepts queued for extraction: [N] (or "skipped")

Daily note ($DAILY_DIR/YYYY-MM-DD.md):
  Work: [summary of work log entries added]
  Tasks: [N new, N carried over, N completed]

Global MEMORY.md ([n]/200 lines):
  [new global entries, if any]

Project AGENTS.md ([project name]):
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
