# Cortex

Claude Code's built-in auto-memory dumps everything into one flat file. After a few weeks, it's cluttered with stale entries, duplicates, and noise that actively degrades context quality. Cortex replaces that with structured memory you control.

Two commands. Run them manually when you want. No background processes, no magic.

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

## Evals

Both skills ship with binary eval suites so you can verify quality after forking or customizing.

```bash
cd evals
python3 eval.py ../.claude/skills/save/SKILL.md --evals save_evals.json --verbose
python3 eval.py ../.claude/skills/dream/SKILL.md --evals dream_evals.json --verbose
```

Each eval is a yes/no question scored by an LLM judge via `claude -p`. Use `--output json` for machine-readable results.

## Project Structure

```
cortex/
├── .claude/skills/
│   ├── save/SKILL.md        # /save skill
│   └── dream/SKILL.md       # /dream skill
├── evals/
│   ├── eval.py              # LLM judge eval harness
│   ├── save_evals.json      # Binary evals for /save
│   └── dream_evals.json     # Binary evals for /dream
├── install.sh               # Copies skills into your workspace
├── .memory-config.example   # Path configuration template
└── LICENSE
```

## Author

Ved Nikolic ([vednikolic](https://github.com/vednikolic))

## License

MIT
