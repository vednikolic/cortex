# Cortex

Claude Code's built-in auto-memory dumps everything into one flat file. After a few weeks, it's cluttered with stale entries, duplicates, and noise that actively degrades context quality. Cortex replaces that with structured memory you control.

Two skills and a CLI. Run them manually when you want. No background processes, no magic.

## Why

Claude Code remembers things, but not well. Auto-memory entries pile up without organization, go stale without review, and live in a single file with no routing logic. The result: your agent's context gets worse over time, not better.

Cortex fixes this with two slash commands:

- **`/save`** routes session learnings to the right file instead of dumping everything in one place
- **`/dream`** reviews what's accumulated and surfaces what needs attention

## Install

```bash
git clone https://github.com/vednikolic/cortex.git
cd cortex
./install.sh
```

The installer copies both skills into your workspace's `.claude/skills/` directory and optionally creates a `.memory-config` file to customize paths.

Requires [Claude Code](https://docs.anthropic.com/en/docs/claude-code).

## Usage

### /save

Run at the end of a session or after completing meaningful work. `/save` reads the conversation, extracts what's worth keeping, and routes each entry to one of four destinations:

| Destination | What goes there | Example |
|---|---|---|
| **MEMORY.md** | Cross-project knowledge, environment facts, reusable patterns | "Homebrew Python is at /opt/homebrew/bin/python3.12" |
| **Project CLAUDE.md** | Architecture decisions, implementation state, project-specific context | "Auth uses JWT with 24h expiry, refresh tokens in httpOnly cookies" |
| **Learnings file** | Working style, collaboration preferences, personal process insights | "Breaking PRs into <300 line chunks gets faster reviews" |
| **Daily notes** | Work log with timestamps, task progress, carry-over items | "Finished API migration, auth endpoint still needs tests" |

After routing, `/save` checks for patterns across your memory: duplicates, contradictions, entries that reinforce each other, and signals worth surfacing.

```
/save
/save auth refactor decisions
```

### /dream

Run periodically (weekly works well) to consolidate what `/save` has written. Five analysis passes:

1. **Stale detection** flags entries not referenced in 7+ days
2. **Friction patterns** escalates recurring friction (3+ mentions) to automation candidates
3. **Cross-project signals** finds shared concepts, conflicting assumptions, and converging needs across projects
4. **Promotion candidates** checks whether patterns are mature enough for root CLAUDE.md
5. **Dormant ideas** surfaces things mentioned multiple times but never acted on

Output appends to `dream-log.md`. Dream never modifies your memory files, never auto-promotes, never deletes. It surfaces findings. You decide what to act on.

```
/dream
/dream my-project
```

## Phase 2: Knowledge Graph

The `concepts` CLI builds a knowledge graph from your sessions. `/save` extracts concepts automatically; `/dream` uses graph data for higher-confidence cross-project signals.

### Quick start

```bash
concepts init                    # Create concepts.db in workspace root
# ... use /save normally, concepts are extracted automatically ...
concepts graph                   # See your knowledge graph
concepts dream-prep              # Generate graph data for /dream
```

### Concepts CLI

| Command | Description |
|---|---|
| `concepts init` | Initialize concepts database |
| `concepts upsert <name>` | Create or update a concept |
| `concepts edge <from> <to> <relation>` | Create or strengthen an edge |
| `concepts query <name>` | Query a concept and its relationships |
| `concepts list` | List all concept names |
| `concepts shared` | Show concepts appearing in 2+ projects |
| `concepts stale` | Show concepts not recently referenced |
| `concepts hot` | Show most active concepts |
| `concepts graph` | Show graph summary |
| `concepts stats` | Show statistics and weight distributions |
| `concepts merge <source> <target>` | Merge source concept into target |
| `concepts correct <name> <new_name>` | Rename a concept |
| `concepts undo-last` | Revert most recent extraction |
| `concepts verify` | Check database integrity |
| `concepts log-extraction` | Log an extraction event |
| `concepts dream-prep` | Generate or verify dream-context.json |

All commands support `--db <path>` to override database location and `--json` for machine-readable output.

### How it works

1. `/save` runs Step 4b after each session: computes session weight, proposes concepts, creates edges, logs the extraction
2. The graph accumulates over sessions. Canonicalization prevents duplicates (fuzzy matching, abbreviation handling)
3. `concepts dream-prep` generates `dream-context.json` with shared concepts, hot concepts, stale concepts, and graph summary
4. `/dream` reads this file for higher-confidence cross-project signal detection (Pass 3) and reports graph health (Pass 6)

### Configuration

Add project definitions to `.memory-config`:

```
projects:
  cortex: 1-projects/memory/cortex
  website: 1-projects/ved-website
```

## When to Use What

| Situation | Command |
|---|---|
| Wrapping up a coding session | `/save` |
| Made a key architecture decision | `/save` |
| Learned something about your tools or environment | `/save` |
| Memory files feel cluttered or stale | `/dream` |
| Starting a new week, want to clean house | `/dream` |
| Wondering if patterns are emerging across projects | `/dream` |

## Configuration

Create `.memory-config` in your workspace root to map memory locations to your directory structure:

```
daily_dir: 2-areas/me/daily
learnings: 2-areas/me/learnings.md
dream_log: 2-areas/me/dream-log.md
project_root: 1-projects
workspace: personal
```

Without `.memory-config`, PARA defaults are used. See `.memory-config.example` for the full template.

## Testing

### Unit tests

```bash
cd cortex
python3.12 -m pytest tests/ -v
```

### LLM evals

```bash
cd evals
python3 eval.py ../.claude/skills/save/SKILL.md --evals save_evals.json --verbose
python3 eval.py ../.claude/skills/dream/SKILL.md --evals dream_evals.json --verbose
python3 eval.py ../.claude/skills/save/SKILL.md --evals extraction_evals.json --verbose
python3 eval.py ../.claude/skills/dream/SKILL.md --evals dream_graph_evals.json --verbose
```

Each eval is a yes/no question scored by an LLM judge via `claude -p`. Use `--output json` for machine-readable results.

## Project Structure

```
cortex/
├── .claude/skills/
│   ├── save/SKILL.md            # /save skill (with Step 4b extraction)
│   └── dream/SKILL.md           # /dream skill (with graph integration)
├── cortex_lib/                  # Python library (stdlib-only)
│   ├── __init__.py
│   ├── db.py                    # Schema, connection, verify
│   ├── canon.py                 # Two-tier canonicalization
│   ├── ops.py                   # CRUD operations
│   ├── weight.py                # Session weight computation
│   ├── analysis.py              # Graph analysis queries
│   ├── correction.py            # Correct, undo-last, merge
│   ├── dream_prep.py            # Generate dream-context.json
│   └── cli.py                   # argparse CLI
├── concepts                     # CLI entry point
├── abbreviations.json           # ~40 seeded abbreviation pairs
├── dream-prep.sh                # Bash wrapper for dream_prep.py
├── tests/                       # pytest suite
├── evals/                       # LLM eval suites
│   ├── eval.py                  # LLM judge harness
│   ├── save_evals.json          # /save evals
│   ├── dream_evals.json         # /dream evals
│   ├── extraction_evals.json    # Step 4b extraction evals
│   └── dream_graph_evals.json   # Dream graph integration evals
├── install.sh                   # Installs skills + CLI
├── .memory-config.example       # Path configuration template
└── LICENSE
```

## Author

Ved Nikolic ([vednikolic](https://github.com/vednikolic))

## License

MIT
