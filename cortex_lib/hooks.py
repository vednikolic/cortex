"""Cortex hook installer for settings.json."""

import json
from pathlib import Path
from typing import Optional


SESSION_INIT_SH = """#!/usr/bin/env bash
# cortex: session-init.sh (SessionStart hook)
# Writes context snapshot for session tracking.
# Records HEAD ref, MEMORY.md hash, and concepts from brief.

SESSION_START="$HOME/.cortex/session-start"
mkdir -p "$HOME/.cortex"

HEAD_REF=$(git rev-parse HEAD 2>/dev/null || echo "")
TIMESTAMP=$(date -u +%Y-%m-%dT%H:%M:%SZ)

# Hash MEMORY.md content (discover path from current project)
MEMORY_PATH=""
PROJECT_HASH=$(echo -n "$PWD" | sed 's|/|-|g')
CANDIDATE="$HOME/.claude/projects/$PROJECT_HASH/memory/MEMORY.md"
if [ -f "$CANDIDATE" ]; then
    MEMORY_PATH="$CANDIDATE"
fi
if [ -n "$MEMORY_PATH" ]; then
    MEMORY_HASH=$(shasum "$MEMORY_PATH" | cut -d' ' -f1)
else
    MEMORY_HASH=""
fi

# Extract concept names from cortex-brief.md (Hot concepts and Active projects)
CONCEPTS_LOADED="[]"
BRIEF_PATH="cortex-brief.md"
if [ -f "$BRIEF_PATH" ]; then
    CONCEPTS_LOADED=$(python3 -c "
import re, json, sys
concepts = []
try:
    text = open('$BRIEF_PATH').read()
    for line in text.splitlines():
        if '**Hot concepts:**' in line:
            matches = re.findall(r'([a-z][a-z0-9_-]+)\\s*\\(', line)
            concepts.extend(matches)
        if '**Active projects:**' in line:
            projects = line.split(':**')[1].strip() if ':**' in line else ''
            for p in projects.split(','):
                p = p.strip()
                if p:
                    concepts.append(p)
except Exception:
    pass
print(json.dumps(sorted(set(concepts))))
" 2>/dev/null || echo "[]")
fi

# Hash each non-empty line in MEMORY.md
MEMORY_ENTRIES="[]"
if [ -f "$MEMORY_PATH" ]; then
    MEMORY_ENTRIES=$(python3 -c "
import hashlib, json
entries = []
try:
    with open('$MEMORY_PATH') as f:
        for line in f:
            line = line.strip()
            if line:
                entries.append(hashlib.sha1(line.encode()).hexdigest()[:12])
except Exception:
    pass
print(json.dumps(entries))
" 2>/dev/null || echo "[]")
fi

python3 -c "
import json
data = {
    'timestamp': '$TIMESTAMP',
    'head_ref': '$HEAD_REF',
    'memory_snapshot_hash': '$MEMORY_HASH',
    'concepts_loaded': $CONCEPTS_LOADED,
    'memory_entries_loaded': $MEMORY_ENTRIES,
}
with open('$SESSION_START', 'w') as f:
    json.dump(data, f, indent=2)
" 2>/dev/null

exit 0
"""

SESSION_CAPTURE_SH = """#!/usr/bin/env bash
# cortex: session-capture.sh (Stop hook)
# Reads session-start, computes git diff, calls concepts capture.
# Always exits 0.

SESSION_START="$HOME/.cortex/session-start"
CONCEPTS_CLI="$HOME/.cortex/concepts"

if [ ! -f "$CONCEPTS_CLI" ]; then exit 0; fi
if [ ! -f ".memory-config" ]; then exit 0; fi

# Compute git diff against stored HEAD
FILES=""
COMMITS=""
BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "")
DURATION=""

if [ -f "$SESSION_START" ]; then
    START_HEAD=$(python3 -c "
import json, sys
try:
    d = json.load(open('$SESSION_START'))
    print(d.get('head_ref', ''))
except: pass
" 2>/dev/null)

    START_TS=$(python3 -c "
import json, sys
try:
    d = json.load(open('$SESSION_START'))
    print(d.get('timestamp', ''))
except: pass
" 2>/dev/null)

    if [ -n "$START_HEAD" ]; then
        FILES=$(git diff --name-only "$START_HEAD" 2>/dev/null | tr '\\n' ',' | sed 's/,$//')
        COMMITS=$(git log --oneline "$START_HEAD..HEAD" 2>/dev/null | tr '\\n' ',' | sed 's/,$//')
    fi

    if [ -n "$START_TS" ]; then
        NOW=$(date -u +%s)
        START_EPOCH=$(date -u -j -f "%Y-%m-%dT%H:%M:%SZ" "$START_TS" +%s 2>/dev/null || echo "")
        if [ -n "$START_EPOCH" ]; then
            DURATION=$((NOW - START_EPOCH))
        fi
    fi
fi

# Detect project from .memory-config or directory name
PROJECT=$(python3 -c "
try:
    with open('.memory-config') as f:
        for line in f:
            if line.startswith('workspace:'):
                print(line.split(':',1)[1].strip())
                break
except: pass
" 2>/dev/null)
if [ -z "$PROJECT" ]; then
    PROJECT=$(basename "$PWD")
fi

ARGS="--project $PROJECT --branch $BRANCH --session-start $SESSION_START"
if [ -n "$FILES" ]; then ARGS="$ARGS --files $FILES"; fi
if [ -n "$COMMITS" ]; then ARGS="$ARGS --commits $COMMITS"; fi
if [ -n "$DURATION" ]; then ARGS="$ARGS --duration $DURATION"; fi

"$CONCEPTS_CLI" --root "$PWD" capture $ARGS 2>/dev/null

exit 0
"""

REVIEW_CHECK_SH = """#!/usr/bin/env bash
# cortex: review-check.sh (SessionStart hook)
# Surfaces a reminder if /review has not run this week.

MARKER="$HOME/.cortex-review-pending"

if [ -f "$MARKER" ]; then
    WEEK=$(cat "$MARKER")
    echo "Patterns from recent work are ready to be locked in so future sessions build on them instead of rediscovering them. Run /review (week of $WEEK)."
fi
"""

REFLECT_GATE_SH = """#!/usr/bin/env bash
# cortex: reflect-gate.sh (Stop hook)
# Checks whether a /reflect pass is warranted and logs the result.
# Always exits 0 to avoid spurious hook error messages.
# When conditions are met, writes a flag file that reflect-surface.sh
# reads at next SessionStart to remind the user.

TURN_COUNT="${CLAUDE_SESSION_TURN_COUNT:-0}"
LAST_REFLECT="$HOME/.claude/reflect-last-run"
GATE_LOG="$HOME/.claude/reflect-gate.log"
REFLECT_DUE="$HOME/.claude/reflect-due"
NOW=$(date +%s)

# Trigger on 8+ turns (heavy tool-use sessions have fewer turns
# but more substance than conversational sessions)
if [ "$TURN_COUNT" -ge 8 ]; then
    echo "reflect:trigger:heavy-session turns=$TURN_COUNT $(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "$GATE_LOG"
    echo "heavy-session" > "$REFLECT_DUE"
    exit 0
fi

# Trigger if 24h+ since last reflect
if [ -f "$LAST_REFLECT" ]; then
    LAST=$(cat "$LAST_REFLECT")
    DIFF=$((NOW - LAST))
    if [ "$DIFF" -ge 86400 ]; then
        echo "reflect:trigger:daily-elapsed diff=${DIFF}s $(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "$GATE_LOG"
        echo "daily-elapsed" > "$REFLECT_DUE"
        exit 0
    fi
fi

# Trigger if /save ran this session (last-session.json exists = substantive session)
if [ -f "$HOME/.cortex/last-session.json" ]; then
    echo "reflect:trigger:save-ran $(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "$GATE_LOG"
    echo "save-ran" > "$REFLECT_DUE"
    exit 0
fi

exit 0
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
# If reflect-gate flagged a reflect as due, remind the user.

REFLECT_LOG="${REFLECT_LOG:-2-areas/me/reflect-log.md}"
LAST_SURFACED="$HOME/.claude/reflect-last-surfaced"
REFLECT_DUE="$HOME/.claude/reflect-due"
NOW=$(date +%s)

# Surface latest reflect entry if reflect ran since last surfaced
if [ -f "$REFLECT_LOG" ]; then
    SHOW=0
    if [ ! -f "$LAST_SURFACED" ]; then
        SHOW=1
    else
        LAST=$(cat "$LAST_SURFACED")
        if [ "$(uname)" = "Darwin" ]; then
            REFLECT_TIME=$(stat -f %m "$REFLECT_LOG")
        else
            REFLECT_TIME=$(stat -c %Y "$REFLECT_LOG")
        fi
        if [ "$REFLECT_TIME" -gt "$LAST" ]; then
            SHOW=1
        fi
    fi

    if [ "$SHOW" -eq 1 ]; then
        LATEST=$(awk '/^## Reflect/{found=1;count++} found&&count==1{print} /^## Reflect/&&count>1{exit}' "$REFLECT_LOG")
        echo "$LATEST"
        echo "$NOW" > "$LAST_SURFACED"
        exit 0
    fi
fi

# If reflect-gate flagged a reflect as due, remind with context
if [ -f "$REFLECT_DUE" ]; then
    TRIGGER=$(cat "$REFLECT_DUE")
    case "$TRIGGER" in
        heavy-session)
            echo "Last session was substantial. New patterns may have emerged that /reflect can consolidate."
            ;;
        daily-elapsed)
            echo "Over 24 hours since your last /reflect pass."
            ;;
        save-ran)
            echo "/save captured new concepts after your last /reflect. A quick /reflect pass can integrate them."
            ;;
        *)
            echo "New work since your last /reflect may have created patterns worth consolidating."
            ;;
    esac
    rm -f "$REFLECT_DUE"
fi
"""

REVIEW_GATE_SH = """#!/usr/bin/env bash
# cortex: review-gate.sh (Stop hook)
# Writes the review-pending marker if /review hasn't run this week.
# Always exits 0.

CONCEPTS_CLI="$HOME/.cortex/concepts"
if [ ! -f "$CONCEPTS_CLI" ]; then exit 0; fi

MARKER="$HOME/.cortex-review-pending"
NOW=$(date +%s)

# Check last review-summary date
LAST_REVIEW=$("$CONCEPTS_CLI" --root "$PWD" --json review-summary 2>/dev/null | python3 -c "
import sys, json
try:
    rows = json.load(sys.stdin)
    if rows:
        print(rows[0].get('created_at',''))
except: pass
" 2>/dev/null)

if [ -z "$LAST_REVIEW" ]; then
    WEEK_START=$(python3 -c "from datetime import date,timedelta;d=date.today();print(d-timedelta(days=d.weekday()))")
    echo "$WEEK_START" > "$MARKER"
    exit 0
fi

# Check if last review is older than 7 days
DAYS_SINCE=$(python3 -c "
from datetime import datetime, timezone
import sys
ts = '$LAST_REVIEW'
if ts:
    dt = datetime.fromisoformat(ts)
    now = datetime.now(timezone.utc)
    print(int((now - dt).total_seconds() // 86400))
else:
    print(999)
" 2>/dev/null)

if [ "${DAYS_SINCE:-0}" -ge 7 ]; then
    WEEK_START=$(python3 -c "from datetime import date,timedelta;d=date.today();print(d-timedelta(days=d.weekday()))")
    echo "$WEEK_START" > "$MARKER"
else
    rm -f "$MARKER"
fi

exit 0
"""

CONCEPT_EXTRACT_SH = """#!/usr/bin/env bash
# cortex: concept-extract.sh (Stop hook)
# Executes queued concept extractions from /save.
# Reads ~/.cortex/last-session.json, runs CLI upserts and edges, cleans up.
# If /save ran, upgrades session status to saved and removes enrich-queue file.
# Silent on success. Only prints on error.

SESSION_FILE="$HOME/.cortex/last-session.json"
if [ ! -f "$SESSION_FILE" ]; then exit 0; fi

CONCEPTS_CLI="$HOME/.cortex/concepts"
if [ ! -f "$CONCEPTS_CLI" ]; then
    rm -f "$SESSION_FILE"
    exit 0
fi

python3 -c '
import json, subprocess, sys, os

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

# Upgrade session status to saved
hash_file = os.path.expanduser("~/.cortex/current-session-hash")
if os.path.exists(hash_file):
    session_hash = open(hash_file).read().strip()
    if session_hash:
        subprocess.run(
            [concepts_cli, "--root", root, "sessions",
             "--update-status", session_hash, "saved"],
            capture_output=True
        )
        # Remove enrich-queue file
        queue_file = os.path.expanduser("~/.cortex/enrich-queue/" + session_hash + ".json")
        if os.path.exists(queue_file):
            os.remove(queue_file)

if errors > 0:
    print("cortex: concept-extract: " + str(errors) + " command(s) failed", file=sys.stderr)
' "$SESSION_FILE" "$CONCEPTS_CLI"

rm -f "$SESSION_FILE"
"""


EXPECTED_HOOK_ORDER = {
    "SessionStart": [
        "session-init.sh",
        "review-check.sh",
        "reflect-surface.sh",
        "brief-inject.sh",
    ],
    "Stop": [
        "session-capture.sh",
        "concept-extract.sh",
        "brief-write.sh",
        "reflect-gate.sh",
        "review-gate.sh",
    ],
}


def generate_hooks_config() -> dict:
    """Generate the hooks configuration for settings.json.

    Uses the {matcher, hooks[]} schema required by the hooks system (as of 2026-04).
    Each entry wraps one command in a matcher object with empty string (match all).

    Hook ordering (SessionStart):
      1. session-init.sh    (context snapshot + HEAD ref)
      2. review-check.sh    (review reminder)
      3. reflect-surface.sh (reflect findings/reminder)
      4. brief-inject.sh    (brief regeneration, depends on session data)

    Hook ordering (Stop):
      1. session-capture.sh  (always runs, calls concepts capture)
      2. concept-extract.sh  (processes /save output, upgrades status)
      3. brief-write.sh      (regenerates brief)
      4. reflect-gate.sh     (checks if /reflect is due)
      5. review-gate.sh      (checks if /review is due)
    """
    return {
        "hooks": {
            "SessionStart": [
                {
                    "matcher": "",
                    "hooks": [{"type": "command", "command": "bash ~/.claude/scripts/session-init.sh"}],
                },
                {
                    "matcher": "",
                    "hooks": [{"type": "command", "command": "bash ~/.claude/scripts/review-check.sh"}],
                },
                {
                    "matcher": "",
                    "hooks": [{"type": "command", "command": "bash ~/.claude/scripts/reflect-surface.sh"}],
                },
                {
                    "matcher": "",
                    "hooks": [{"type": "command", "command": "bash ~/.claude/scripts/brief-inject.sh"}],
                },
            ],
            "Stop": [
                {
                    "matcher": "",
                    "hooks": [{"type": "command", "command": "bash ~/.claude/scripts/session-capture.sh"}],
                },
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
                {
                    "matcher": "",
                    "hooks": [{"type": "command", "command": "bash ~/.claude/scripts/review-gate.sh"}],
                },
            ],
        }
    }


def hooks_verify(settings_path: Optional[Path] = None) -> dict:
    """Verify hook ordering in settings.json matches expected sequence.

    Returns dict with 'valid' bool and list of 'issues'.
    """
    if settings_path is None:
        settings_path = Path.home() / ".claude" / "settings.json"

    issues = []
    if not settings_path.exists():
        return {'valid': False, 'issues': ['settings.json not found']}

    try:
        settings = json.loads(settings_path.read_text())
    except json.JSONDecodeError:
        return {'valid': False, 'issues': ['settings.json is not valid JSON']}

    hooks = settings.get('hooks', {})

    for event, expected_scripts in EXPECTED_HOOK_ORDER.items():
        if event not in hooks:
            issues.append(f"Missing event: {event}")
            continue

        # Extract script names from settings
        actual_scripts = []
        for entry in hooks[event]:
            cmd = ''
            if 'hooks' in entry and isinstance(entry['hooks'], list):
                for h in entry['hooks']:
                    cmd = h.get('command', '')
            elif 'command' in entry:
                cmd = entry['command']
            # Extract script name from command
            if cmd:
                script = cmd.split('/')[-1]
                actual_scripts.append(script)

        # Check for missing hooks
        for script in expected_scripts:
            if script not in actual_scripts:
                issues.append(f"{event}: missing hook {script}")

        # Check ordering (only for hooks that exist)
        expected_present = [s for s in expected_scripts if s in actual_scripts]
        actual_present = [s for s in actual_scripts if s in expected_scripts]
        if expected_present != actual_present:
            issues.append(
                f"{event}: ordering mismatch. "
                f"Expected: {', '.join(expected_present)}. "
                f"Got: {', '.join(actual_present)}"
            )

        # Check for unknown hooks
        known = set(expected_scripts)
        for script in actual_scripts:
            if script not in known:
                issues.append(f"{event}: unknown hook {script}")

    return {'valid': len(issues) == 0, 'issues': issues}


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
        "session-init.sh": SESSION_INIT_SH,
        "session-capture.sh": SESSION_CAPTURE_SH,
        "brief-write.sh": BRIEF_WRITE_SH,
        "brief-inject.sh": BRIEF_INJECT_SH,
        "review-check.sh": REVIEW_CHECK_SH,
        "reflect-gate.sh": REFLECT_GATE_SH,
        "reflect-surface.sh": REFLECT_SURFACE_SH,
        "concept-extract.sh": CONCEPT_EXTRACT_SH,
        "review-gate.sh": REVIEW_GATE_SH,
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
