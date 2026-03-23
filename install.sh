#!/usr/bin/env bash
set -euo pipefail

# cortex installer
# Copies /save and /dream skills into a workspace's .claude/skills/ directory.
# Claude Code discovers skills from project-local .claude/skills/<name>/SKILL.md.
# Global ~/.claude/skills/ does NOT support skill discovery (verified 2026-03-23).
# Optionally creates .memory-config in the same workspace.

CORTEX_DIR="$(cd "$(dirname "$0")" && pwd)"
SKILLS=("save" "dream")

echo "cortex installer"
echo "================"
echo ""

# Check prerequisites
if ! command -v claude &>/dev/null; then
    echo "ERROR: claude CLI not found. Install Claude Code first."
    echo "  https://docs.anthropic.com/en/docs/claude-code"
    exit 1
fi

# Determine target workspace
read -p "Workspace path to install into (default: current directory): " workspace_path
workspace_path="${workspace_path:-.}"
if [ ! -d "$workspace_path" ]; then
    echo "ERROR: $workspace_path is not a valid directory."
    exit 1
fi
workspace_path="$(cd "$workspace_path" && pwd)"
SKILLS_TARGET="$workspace_path/.claude/skills"

echo ""
echo "Installing to: $workspace_path"
echo ""

# Copy skills
for skill in "${SKILLS[@]}"; do
    src="$CORTEX_DIR/.claude/skills/$skill/SKILL.md"
    dest="$SKILLS_TARGET/$skill/SKILL.md"
    if [ ! -f "$src" ]; then
        echo "ERROR: $src not found. Run install.sh from the cortex repo root."
        exit 1
    fi
    mkdir -p "$SKILLS_TARGET/$skill"
    cp "$src" "$dest"
    echo "  Copied /$skill to $SKILLS_TARGET/$skill/SKILL.md"
done

echo ""

# Offer to create .memory-config
if [ -f "$workspace_path/.memory-config" ]; then
    echo ".memory-config already exists at $workspace_path/.memory-config, skipping."
else
    read -p "Create .memory-config with default paths? (y/N) " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        cp "$CORTEX_DIR/.memory-config.example" "$workspace_path/.memory-config"
        echo "  Created $workspace_path/.memory-config"
        echo "  Edit this file to customize paths for your workspace."
    fi
fi

echo ""

# Self-test: verify skill files are in place
echo "Verifying installation..."
echo ""

test_passed=0
test_failed=0

for skill in "${SKILLS[@]}"; do
    dest="$SKILLS_TARGET/$skill/SKILL.md"
    if [ -f "$dest" ]; then
        # Verify the file has valid frontmatter (starts with ---)
        if head -1 "$dest" | grep -q "^---"; then
            echo "  PASS: /$skill installed at $dest"
            test_passed=$((test_passed + 1))
        else
            echo "  FAIL: /$skill file exists but has invalid frontmatter"
            test_failed=$((test_failed + 1))
        fi
    else
        echo "  FAIL: /$skill not found at $dest"
        test_failed=$((test_failed + 1))
    fi
done

echo ""

if [ "$test_failed" -eq 0 ]; then
    echo "All $test_passed skills installed."
    echo ""
    echo "Usage (in a Claude Code session started from $workspace_path):"
    echo "  /save              Save session learnings to memory"
    echo "  /dream             Run background memory consolidation"
    echo ""
    echo "To customize paths, edit .memory-config in your workspace root."
    echo "Without .memory-config, PARA defaults are used (2-areas/me/daily, etc.)."
else
    echo "ERROR: $test_failed skill(s) failed verification. See details above."
    exit 1
fi
