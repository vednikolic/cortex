"""Cortex hook installer for settings.json."""

import json
from pathlib import Path
from typing import Optional


REVIEW_CHECK_SH = """#!/usr/bin/env bash
# cortex: review-check.sh (SessionStart hook)
# Surfaces a reminder if /review has not run this week.

MARKER="$HOME/.cortex-review-pending"

if [ -f "$MARKER" ]; then
    WEEK=$(cat "$MARKER")
    echo "cortex: /review pending for week of $WEEK. Run /review to triage signals."
fi
"""

REFLECT_GATE_SH = """#!/usr/bin/env bash
# cortex: reflect-gate.sh (Stop hook)
# Decide whether this session warrants a /reflect pass.

TURN_COUNT="${CLAUDE_SESSION_TURN_COUNT:-0}"
LAST_REFLECT="$HOME/.claude/reflect-last-run"
NOW=$(date +%s)

if [ "$TURN_COUNT" -ge 15 ]; then
    echo "reflect:trigger:heavy-session turns=$TURN_COUNT"
    exit 0
fi

if [ -f "$LAST_REFLECT" ]; then
    LAST=$(cat "$LAST_REFLECT")
    DIFF=$((NOW - LAST))
    if [ "$DIFF" -ge 86400 ]; then
        echo "reflect:trigger:daily-elapsed diff=${DIFF}s"
        exit 0
    fi
fi

exit 1
"""

BRIEF_WRITE_SH = """#!/usr/bin/env bash
# cortex: brief-write.sh (Stop hook)
# Regenerates cortex-brief.md when a session ends.
# Primary trigger for brief freshness. Async from /save.

if [ ! -f ".memory-config" ]; then exit 0; fi

CONCEPTS_CLI="$HOME/.cortex/concepts"
if [ ! -f "$CONCEPTS_CLI" ]; then exit 0; fi

"$CONCEPTS_CLI" --root "$PWD" brief --output "cortex-brief.md" 2>/dev/null
"""

BRIEF_INJECT_SH = """#!/usr/bin/env bash
# cortex: brief-inject.sh (SessionStart hook)
# Fallback: regenerates cortex-brief.md if stale (>24h) or missing.

if [ ! -f ".memory-config" ]; then exit 0; fi

CONCEPTS_CLI="$HOME/.cortex/concepts"
if [ ! -f "$CONCEPTS_CLI" ]; then exit 0; fi

BRIEF_PATH="cortex-brief.md"
# 24h chosen because most users start 1-2 sessions per day.
# The Stop hook (brief-write.sh) handles session-to-session freshness.
# This fallback only fires after crashes, force-quits, or first install.
STALE_SECONDS=86400

if [ -f "$BRIEF_PATH" ]; then
    if [ "$(uname)" = "Darwin" ]; then
        FILE_AGE=$(stat -f %m "$BRIEF_PATH")
    else
        FILE_AGE=$(stat -c %Y "$BRIEF_PATH")
    fi
    NOW=$(date +%s)
    AGE=$((NOW - FILE_AGE))
    if [ "$AGE" -lt "$STALE_SECONDS" ]; then exit 0; fi
fi

"$CONCEPTS_CLI" --root "$PWD" brief --output "$BRIEF_PATH" 2>/dev/null
"""

REFLECT_SURFACE_SH = """#!/usr/bin/env bash
# cortex: reflect-surface.sh (SessionStart hook)
# If a reflect ran since last session, show the latest finding.

REFLECT_LOG="${REFLECT_LOG:-2-areas/me/reflect-log.md}"
LAST_SURFACED="$HOME/.claude/reflect-last-surfaced"
NOW=$(date +%s)

if [ ! -f "$REFLECT_LOG" ]; then exit 0; fi

if [ -f "$LAST_SURFACED" ]; then
    LAST=$(cat "$LAST_SURFACED")
    if [ "$(uname)" = "Darwin" ]; then
        REFLECT_TIME=$(stat -f %m "$REFLECT_LOG")
    else
        REFLECT_TIME=$(stat -c %Y "$REFLECT_LOG")
    fi
    if [ "$REFLECT_TIME" -le "$LAST" ]; then exit 0; fi
fi

LATEST=$(awk '/^## Reflect/{found=1;count++} found&&count==1{print} /^## Reflect/&&count>1{exit}' "$REFLECT_LOG")
echo "$LATEST"
echo "$NOW" > "$LAST_SURFACED"
"""

CONCEPT_EXTRACT_SH = """#!/usr/bin/env bash
# cortex: concept-extract.sh (Stop hook)
# Executes queued concept extractions from /save.
# Reads ~/.cortex/last-session.json, runs CLI upserts and edges, cleans up.
# Silent on success. Only prints on error.

SESSION_FILE="$HOME/.cortex/last-session.json"
if [ ! -f "$SESSION_FILE" ]; then exit 0; fi

CONCEPTS_CLI="$HOME/.cortex/concepts"
if [ ! -f "$CONCEPTS_CLI" ]; then
    rm -f "$SESSION_FILE"
    exit 0
fi

python3 -c '
import json, subprocess, sys

session_file = sys.argv[1]
concepts_cli = sys.argv[2]

try:
    d = json.load(open(session_file))
except Exception:
    sys.exit(0)

root = d.get("workspace_root", "")
if not root:
    sys.exit(0)

sh = d.get("session_hash", "")
w = str(d.get("weight", 1))
proj = d.get("project", "")
errors = 0

for c in d.get("concepts", []):
    r = subprocess.run(
        [concepts_cli, "--root", root, "upsert", c["name"],
         "--kind", c.get("kind", "topic"), "--project", proj,
         "--session", sh, "--weight", w],
        capture_output=True
    )
    if r.returncode != 0:
        errors += 1

for e in d.get("edges", []):
    r = subprocess.run(
        [concepts_cli, "--root", root, "edge", e["from"], e["to"], e["relation"],
         "--session", sh],
        capture_output=True
    )
    if r.returncode != 0:
        errors += 1

proposed = json.dumps(d.get("proposed", []))
created = json.dumps(d.get("created", []))
edges_json = json.dumps(d.get("edges", []))
rejected = str(d.get("rejected_count", 0))

r = subprocess.run(
    [concepts_cli, "--root", root, "log-extraction",
     "--session", sh, "--proposed", proposed, "--created", created,
     "--edges", edges_json, "--rejected", rejected, "--weight", w],
    capture_output=True
)
if r.returncode != 0:
    errors += 1

if errors > 0:
    print("cortex: concept-extract: " + str(errors) + " command(s) failed", file=sys.stderr)
' "$SESSION_FILE" "$CONCEPTS_CLI"

rm -f "$SESSION_FILE"
"""


def generate_hooks_config() -> dict:
    """Generate the hooks configuration for settings.json.

    Uses the {matcher, hooks[]} schema required by the hooks system (as of 2026-04).
    Each entry wraps one command in a matcher object with empty string (match all).
    """
    return {
        "hooks": {
            "SessionStart": [
                {
                    "matcher": "",
                    "hooks": [{"type": "command", "command": "bash ~/.claude/scripts/brief-inject.sh"}],
                },
                {
                    "matcher": "",
                    "hooks": [{"type": "command", "command": "bash ~/.claude/scripts/review-check.sh"}],
                },
                {
                    "matcher": "",
                    "hooks": [{"type": "command", "command": "bash ~/.claude/scripts/reflect-surface.sh"}],
                },
            ],
            "Stop": [
                {
                    "matcher": "",
                    "hooks": [{"type": "command", "command": "bash ~/.claude/scripts/concept-extract.sh"}],
                },
                {
                    "matcher": "",
                    "hooks": [{"type": "command", "command": "bash ~/.claude/scripts/brief-write.sh"}],
                },
                {
                    "matcher": "",
                    "hooks": [{"type": "command", "command": "bash ~/.claude/scripts/reflect-gate.sh"}],
                },
            ],
        }
    }


def install_hooks(
    scripts_dir: Optional[Path] = None,
    settings_path: Optional[Path] = None,
) -> dict:
    """Install cortex hooks.

    1. Write hook scripts to scripts_dir
    2. Merge hooks config into settings.json

    Returns summary of what was installed.
    """
    if scripts_dir is None:
        scripts_dir = Path.home() / ".claude" / "scripts"
    if settings_path is None:
        settings_path = Path.home() / ".claude" / "settings.json"

    scripts_dir.mkdir(parents=True, exist_ok=True)

    scripts = {
        "brief-write.sh": BRIEF_WRITE_SH,
        "brief-inject.sh": BRIEF_INJECT_SH,
        "review-check.sh": REVIEW_CHECK_SH,
        "reflect-gate.sh": REFLECT_GATE_SH,
        "reflect-surface.sh": REFLECT_SURFACE_SH,
        "concept-extract.sh": CONCEPT_EXTRACT_SH,
    }

    for name, content in scripts.items():
        path = scripts_dir / name
        path.write_text(content)
        path.chmod(0o755)

    settings = {}
    if settings_path.exists():
        try:
            settings = json.loads(settings_path.read_text())
        except json.JSONDecodeError:
            settings = {}

    hooks_config = generate_hooks_config()
    if "hooks" not in settings:
        settings["hooks"] = {}

    for event, hook_list in hooks_config["hooks"].items():
        if event not in settings["hooks"]:
            settings["hooks"][event] = []

        # Collect existing commands from both flat and matcher-wrapped formats
        existing_cmds = set()
        for entry in settings["hooks"][event]:
            # Matcher-wrapped: {matcher, hooks: [{type, command}]}
            if "hooks" in entry and isinstance(entry["hooks"], list):
                for h in entry["hooks"]:
                    existing_cmds.add(h.get("command", ""))
            # Legacy flat: {type, command}
            elif "command" in entry:
                existing_cmds.add(entry["command"])

        for hook in hook_list:
            # Extract command from matcher-wrapped format
            cmd = hook.get("hooks", [{}])[0].get("command", "") if "hooks" in hook else hook.get("command", "")
            if cmd not in existing_cmds:
                settings["hooks"][event].append(hook)

    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(json.dumps(settings, indent=2) + "\n")

    return {
        "scripts_installed": list(scripts.keys()),
        "scripts_dir": str(scripts_dir),
        "settings_path": str(settings_path),
    }


def write_review_pending(week_start: str) -> Path:
    """Write the review-pending marker file."""
    marker = Path.home() / ".cortex-review-pending"
    marker.write_text(week_start)
    return marker


def clear_review_pending() -> bool:
    """Clear the review-pending marker. Returns True if it existed."""
    marker = Path.home() / ".cortex-review-pending"
    if marker.exists():
        marker.unlink()
        return True
    return False
