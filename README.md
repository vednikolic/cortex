# Cortex

The opinionated memory layer [Claude Code](https://docs.anthropic.com/en/docs/claude-code) ships without. One memory system, any workspace.

## What It Does

- **Structured memory routing**: `/save` captures session learnings and routes them to the right file (global memory, project CLAUDE.md, personal learnings, or daily notes)
- **Background consolidation**: `/dream` runs 5 analysis passes over your memory files to detect stale entries, friction patterns, cross-project signals, promotion candidates, and dormant ideas
- **Portable paths**: a single `.memory-config` file maps memory locations to your directory structure. Falls back to PARA defaults if absent
- **Eval suite included**: binary evals for both skills so you can verify quality after forking or customizing

## Install

```bash
git clone https://github.com/vednikolic/cortex.git
cd cortex
./install.sh
```

The installer copies `/save` and `/dream` to `~/.claude/skills/` (global skill discovery) and optionally creates `.memory-config` in your workspace.

## What Ships

| Included in v1 | Deferred to v2 |
|---|---|
| `/save` skill | Concept graph |
| `/dream` skill | `/review` skill |
| `install.sh` | Hooks (auto-dream on session stop) |
| `.memory-config` support | Weekly synthesis |
| Eval suite | Cross-tool exporters (Cursor, Windsurf, Gemini CLI) |

## Skills

### /save

Captures what happened in a session and persists it to the right place. Routes entries across four destinations:

1. **Global MEMORY.md** -- cross-project knowledge, environment facts, mental models, repeatable workflows
2. **Project CLAUDE.md** -- architecture decisions, implementation state, friction log, decision register
3. **Personal learnings** -- working style, preferences, collaboration patterns
4. **Daily notes** -- work log with time anchors, tasks with carry-over from previous days

After routing, `/save` checks for patterns (duplicates, reinforcement, contradictions, staleness) and surfaces signals (opportunities, risks, convergence across projects). Run it at the end of a session or after completing meaningful work.

```
/save
/save eval design
```

### /dream

Background consolidation that reads what `/save` has written and looks for what it implies. Five analysis passes run in sequence:

1. **Stale detection** -- flags entries not referenced in 7+ days
2. **Friction promotion** -- escalates friction appearing 3+ times to automation candidates
3. **Cross-project signals** -- detects shared concepts, conflicting assumptions, and converging needs across projects
4. **Promotion queue review** -- checks whether queued patterns are ready for root CLAUDE.md
5. **Dormant idea detection** -- surfaces ideas mentioned multiple times but never acted on

Output appends to `dream-log.md`. Dream never writes to MEMORY.md, never auto-promotes, never deletes. It surfaces findings. You decide what to act on.

```
/dream
/dream my-project
```

## Configuration

Create `.memory-config` in your workspace root to customize paths. All paths are relative to the workspace root unless absolute.

```
# Directory for daily notes
daily_dir: 2-areas/me/daily

# Personal learnings file
learnings: 2-areas/me/learnings.md

# Dream consolidation log
dream_log: 2-areas/me/dream-log.md

# Root directory for project subdirectories
project_root: 1-projects

# Workspace type (controls concept DB isolation in v2)
workspace: personal
```

If `.memory-config` is absent, PARA defaults are used (`2-areas/me/daily`, `1-projects`, etc.). See `.memory-config.example` for the full template.

## Evals

Both skills ship with binary eval suites scored by an LLM judge via `claude -p`.

```bash
cd evals
python3 eval.py ../.claude/skills/save/SKILL.md --evals save_evals.json --verbose
python3 eval.py ../.claude/skills/dream/SKILL.md --evals dream_evals.json --verbose
```

Each eval is a yes/no question about the skill document. Composite score is the weighted sum of passing evals. Use `--output json` for machine-readable results. Fork the repo, customize the skills, and run evals to verify you did not regress.

## Project Structure

```
cortex/
├── .claude/skills/
│   ├── save/SKILL.md        # /save skill definition
│   └── dream/SKILL.md       # /dream skill definition
├── evals/
│   ├── eval.py              # LLM judge eval harness
│   ├── save_evals.json      # Binary evals for /save
│   └── dream_evals.json     # Binary evals for /dream
├── install.sh               # Installer (copies skills to ~/.claude/skills/)
├── .memory-config.example   # Path configuration template
└── LICENSE
```

## Author

Ved Nikolic ([vednikolic](https://github.com/vednikolic)) -- ved@vednikolic.com

## License

MIT
