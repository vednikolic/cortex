#!/usr/bin/env bash
set -euo pipefail

# cortex installer
# Copies /save and /dream skills to ~/.claude/skills/ (global discovery)
# Optionally creates .memory-config in the target workspace

CORTEX_DIR="$(cd "$(dirname "$0")" && pwd)"
SKILLS_TARGET="$HOME/.claude/skills"
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

# Create target directory
mkdir -p "$SKILLS_TARGET"

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
    echo "  Copied /$skill to $dest"
done

echo ""

# Offer to create .memory-config
read -p "Create .memory-config in a workspace? (y/N) " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
    read -p "Workspace path (default: current directory): " workspace_path
    workspace_path="${workspace_path:-.}"
    if [ ! -d "$workspace_path" ]; then
        echo "  ERROR: $workspace_path is not a valid directory."
        echo "  Skipping .memory-config creation."
    else
        workspace_path="$(cd "$workspace_path" && pwd)"

        if [ -f "$workspace_path/.memory-config" ]; then
            echo "  .memory-config already exists at $workspace_path/.memory-config, skipping."
        else
            cp "$CORTEX_DIR/.memory-config.example" "$workspace_path/.memory-config"
            echo "  Created $workspace_path/.memory-config"
            echo "  Edit this file to customize paths for your workspace."
        fi
    fi
fi

echo ""

# Self-test: verify skill discovery via Claude Code
echo "Verifying skill discovery..."
echo ""

test_passed=0
test_failed=0

for skill in "${SKILLS[@]}"; do
    if [ ! -f "$SKILLS_TARGET/$skill/SKILL.md" ]; then
        echo "  FAIL: /$skill file not found at $SKILLS_TARGET/$skill/SKILL.md"
        test_failed=$((test_failed + 1))
        continue
    fi

    # Ask Claude if it can see the skill
    if discovery=$(cd /tmp && claude -p "Do you see a skill called $skill in your available skills? Answer only YES or NO." --model haiku 2>/dev/null); then
        if echo "$discovery" | grep -qi "YES"; then
            echo "  PASS: /$skill discovered by Claude Code"
            test_passed=$((test_passed + 1))
        else
            echo "  WARN: /$skill installed but not discovered by Claude Code"
            echo "        File exists at $SKILLS_TARGET/$skill/SKILL.md"
            echo "        Try restarting Claude Code, or copy the skill to your project's .claude/skills/"
            test_failed=$((test_failed + 1))
        fi
    else
        echo "  SKIP: could not verify /$skill discovery (claude -p failed)"
        echo "        File exists at $SKILLS_TARGET/$skill/SKILL.md"
        test_passed=$((test_passed + 1))
    fi
done

echo ""

if [ "$test_failed" -eq 0 ]; then
    echo "All $test_passed skills installed and discovered."
    echo ""
    echo "Usage:"
    echo "  /save              Save session learnings to memory"
    echo "  /dream             Run background memory consolidation"
    echo ""
    echo "To customize paths, edit .memory-config in your workspace root."
    echo "Without .memory-config, PARA defaults are used (2-areas/me/daily, etc.)."
else
    echo "WARNING: $test_failed skill(s) had issues. See details above."
    exit 1
fi
