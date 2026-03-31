"""Cortex hook installer for Claude Code settings.json."""

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


def generate_hooks_config() -> dict:
    """Generate the hooks configuration for settings.json."""
    return {
        "hooks": {
            "SessionStart": [
                {
                    "type": "command",
                    "command": "bash ~/.claude/scripts/review-check.sh",
                },
                {
                    "type": "command",
                    "command": "bash ~/.claude/scripts/reflect-surface.sh",
                },
            ],
            "Stop": [
                {
                    "type": "command",
                    "command": "bash ~/.claude/scripts/reflect-gate.sh",
                },
            ],
        }
    }


def install_hooks(
    scripts_dir: Optional[Path] = None,
    settings_path: Optional[Path] = None,
) -> dict:
    """Install cortex hooks into Claude Code.

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
        "review-check.sh": REVIEW_CHECK_SH,
        "reflect-gate.sh": REFLECT_GATE_SH,
        "reflect-surface.sh": REFLECT_SURFACE_SH,
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
        existing_cmds = {h.get("command", "") for h in settings["hooks"][event]}
        for hook in hook_list:
            if hook["command"] not in existing_cmds:
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
