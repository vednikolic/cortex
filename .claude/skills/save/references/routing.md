# Routing Reference

Used by `/save` Step 3 (route entries) and Step 6 (write entries). Read this when you need to decide where a new entry belongs, or verify a routing decision against the strict scope test.

## Destinations

### Global MEMORY.md
`$MEMORY_DIR/MEMORY.md`. Cross-project knowledge only. Index of pointers to topic files. One-line entries, ≤150 chars each, no embedded content.

- User preferences and workflow decisions
- Environment setup (tooling, Python versions, paths)
- Pointers to active projects (one line each)
- Repeatable workflows (command sequences run regularly)
- Mental models (how you conceptualize a domain -- highest-value continuity assets)
- Learnings that apply across multiple projects
- `## Promotion Queue`: pattern candidates that have appeared 2+ times

### Project AGENTS.md
`$PROJECT_ROOT/<name>/AGENTS.md`. Project-specific state, tool-agnostic.

- Architecture decisions, implementation state, open items
- Project-specific gotchas and conventions
- Phase/milestone tracking
- Tech stack details, test counts, DB sizes
- `## Friction Log`: repeated pain points and automation candidates
- `## Decision Register`: choices with confidence tags and rationale
- Task carry-over between sessions

### Project playbook
`$PROJECT_ROOT/<name>/playbook.md`. Durable execution patterns. Different from AGENTS.md: AGENTS.md is current state, playbook is reusable patterns.

- Technical patterns with dated proof points ("Proven YYYY-MM-DD on Phase A")
- Tool-specific workarounds and anti-patterns (CLI probe gotchas, workflow node settings, hook friction)
- Architecture patterns discovered during implementation (narrow env readers, pure-helper extraction, inline SQL in fix contracts)
- Phase-gate review and fix session contract shapes
- Indexable: TOC at top, each section jumpable, each entry keeps its dated proof point
- Cross-reference skill-update candidates inline ("Candidate for writing-plans skill: ...")

Create the playbook if missing. Do NOT put entries in learnings.md with a TODO marker; that is how drift starts.

### Personal learnings
`$LEARNINGS` (`2-areas/me/learnings.md` by default). Traits that describe the user as a person. NOT technical details.

- Working style observations (how the user thinks, decides, communicates)
- Pacing, triage rhythm, approval cadence
- Preferences and writing style that emerge from behavior
- Collaboration patterns (what works well, what to avoid)
- Growth areas and interests observed over time

### Daily notes
`$DAILY_DIR/YYYY-MM-DD.md`. Daily work log and task tracker.

- What was accomplished today (work log entries), with rough time anchors
- Tasks created for next steps and follow-ups
- Carried-over incomplete tasks from the previous day
- Blockers or waiting-on items

## Strict scope test for learnings.md (REQUIRED before any write)

Scan the entry for any of these signals. If present, it is NOT a personal learning -- route to project playbook instead:

- Specific project name, file path, commit SHA, or phase/task identifier
- Dated proof point ("Proven YYYY-MM-DD on X")
- Regex, tool flag, CLI command, node setting, line count
- Weighed options list ("Options: (a)...(b)...(c)...")
- "Rule:" clause or "Candidate for <skill>:" clause

If no project playbook exists for the project the entry belongs to, create `$PROJECT_ROOT/<name>/playbook.md` with a TOC and a first section. Do NOT defer with a TODO.

## Anti-pattern: reframed workflow pattern

If an entry describes a workflow pattern (plan chunking, phase gates, subagent dispatch, audit prompts, fix session contracts) but is framed as "user prefers X", strip the framing and route to project playbook or a skill-update candidate. Without this filter, learnings.md drifts into a pattern dump that has to be extracted to project playbooks later.

## Routing table

| Entry type | Destination |
|---|---|
| Project architecture, implementation details, open items | Project AGENTS.md |
| Project decisions | Project AGENTS.md -> `## Decision Register` |
| Repeated friction, automation candidates | Project AGENTS.md -> `## Friction Log` |
| Phase/milestone status | Project AGENTS.md |
| Test counts, DB sizes, file counts | Project AGENTS.md |
| Project execution patterns with dated proof points | Project playbook |
| Tool-specific workarounds discovered mid-build | Project playbook |
| Phase-gate review / fix session contract shapes | Project playbook |
| Architecture patterns (narrow env readers, pure-helper extraction) | Project playbook |
| Skill-update candidates | Project playbook (cross-referenced inline) |
| Cross-project tooling decisions | MEMORY.md |
| Repeatable command sequences | MEMORY.md |
| Mental models | MEMORY.md |
| Environment info (Python paths, system setup) | MEMORY.md |
| Active project status | `cortex-brief.md` (dynamic) OR project AGENTS.md. NOT MEMORY.md |
| Patterns appearing 2+ times | MEMORY.md -> `## Promotion Queue` |
| User working style, pacing, triage, approval cadence | `$LEARNINGS` |
| User communication style, writing preferences, positioning | `$LEARNINGS` |
| Observed interests, growth areas | `$LEARNINGS` |
| Concrete work done this session | Daily note -> Work Log |
| Next steps, follow-ups, tasks | Daily note -> Tasks |
| Blockers or external waiting items | Daily note -> Notes |

## MEMORY.md subtypes

MEMORY.md entries split into three subtypes. All are one-line index entries.

1. **Environment facts** -- paths, versions, system config. Goes under `## Environment`.
   - `- System Python is 3.9.6 (macOS); use Homebrew Python 3.12 at /opt/homebrew/bin/python3.12`
   - `- Homebrew poppler installed for PDF reading support`

2. **Repeatable workflows** -- command sequences, scripts, standard operating steps. Goes under `## Workflows`.
   - `- GitHub subtree publish: git subtree split --prefix=projects/[name] --branch release && git push standalone release:main`

3. **Mental models** -- how you conceptualize a domain. Highest-value entries. Goes under `## Mental Models`.
   - `- Treat eval coverage like test coverage -- block on red, never ship with regressions`
   - `- Skills are prompts, not code -- optimize for clarity and determinism over cleverness`

## Rule of thumb (decision order)

1. Is it about the user as a person (how they think, decide, communicate, prefer)? -> `$LEARNINGS`
2. Does it cite a specific project/file/commit/test/regex/flag/phase/task as proof? -> project playbook
3. Is it cross-project tooling or environment facts? -> MEMORY.md
4. Is it a project decision with state/rationale? -> project AGENTS.md
5. Is it a concrete action or task? -> daily note
