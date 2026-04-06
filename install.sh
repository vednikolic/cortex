#!/usr/bin/env bash
set -euo pipefail

# cortex installer
# Copies /save, /reflect, and /review skills into a workspace's .claude/skills/ directory.
# Skills are discovered from project-local .claude/skills/<name>/SKILL.md.
# Global ~/.claude/skills/ does NOT support skill discovery (verified 2026-03-23).
# Optionally creates .memory-config in the same workspace.

CORTEX_DIR="$(cd "$(dirname "$0")" && pwd)"
SKILLS=("save" "reflect" "review")

echo "cortex installer"
echo "================"
echo ""

# Check prerequisites
if ! command -v claude &>/dev/null; then
    echo "ERROR: claude CLI not found."
    echo "  Install it from https://docs.anthropic.com/en/docs/claude-code"
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

# Install concepts CLI
CORTEX_HOME="$HOME/.cortex"
echo "Installing concepts CLI to $CORTEX_HOME..."
mkdir -p "$CORTEX_HOME"

# Copy CLI files
cp -r "$CORTEX_DIR/cortex_lib" "$CORTEX_HOME/"
cp "$CORTEX_DIR/concepts" "$CORTEX_HOME/"
cp "$CORTEX_DIR/abbreviations.json" "$CORTEX_HOME/"
cp "$CORTEX_DIR/reflect-prep.sh" "$CORTEX_HOME/"
chmod +x "$CORTEX_HOME/concepts"
chmod +x "$CORTEX_HOME/reflect-prep.sh"

# Install hook scripts
echo "Installing hook scripts..."
"$CORTEX_HOME/concepts" hooks install 2>/dev/null || true

echo "Concepts CLI installed."

# Add cortex-brief.md to .gitignore
if [ -f "$workspace_path/.gitignore" ]; then
    if ! grep -q "cortex-brief.md" "$workspace_path/.gitignore"; then
        echo "cortex-brief.md" >> "$workspace_path/.gitignore"
        echo "  Added cortex-brief.md to .gitignore"
    fi
else
    echo "cortex-brief.md" > "$workspace_path/.gitignore"
    echo "  Created .gitignore with cortex-brief.md"
fi

# Add @cortex-brief.md import to CLAUDE.md
CLAUDE_MD="$workspace_path/CLAUDE.md"
if [ -f "$CLAUDE_MD" ]; then
    if ! grep -q "@cortex-brief.md" "$CLAUDE_MD"; then
        echo "" >> "$CLAUDE_MD"
        echo "@cortex-brief.md" >> "$CLAUDE_MD"
        echo "  Added @cortex-brief.md import to CLAUDE.md"
    fi
else
    echo "@cortex-brief.md" > "$CLAUDE_MD"
    echo "  Created CLAUDE.md with @cortex-brief.md import"
fi

# Generate initial brief so first session has context immediately
if [ -f "$workspace_path/concepts.db" ] || [ -f "$workspace_path/.memory-config" ]; then
    "$CORTEX_HOME/concepts" --root "$workspace_path" brief --output "$workspace_path/cortex-brief.md" 2>/dev/null && \
        echo "  Generated initial cortex-brief.md" || true
fi

# Check if ~/.cortex is in PATH
if ! echo "$PATH" | tr ':' '\n' | grep -q "$CORTEX_HOME"; then
    echo ""
    echo "Add to your shell profile (~/.zshrc or ~/.bashrc):"
    echo "  export PATH=\"\$HOME/.cortex:\$PATH\""
    echo ""
fi

# Offer to initialize concepts.db
WORKSPACE_PATH="$workspace_path"
if [ -n "$WORKSPACE_PATH" ] && [ ! -f "$WORKSPACE_PATH/concepts.db" ]; then
    read -p "Initialize concepts.db in $WORKSPACE_PATH? [y/N] " INIT_DB
    if [ "$INIT_DB" = "y" ] || [ "$INIT_DB" = "Y" ]; then
        cd "$WORKSPACE_PATH"
        "$CORTEX_HOME/concepts" init
        cd - > /dev/null
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

# Self-test: verify concepts CLI
if "$CORTEX_HOME/concepts" --version > /dev/null 2>&1; then
    echo "  PASS: concepts CLI ($("$CORTEX_HOME/concepts" --version))"
    test_passed=$((test_passed + 1))
else
    echo "  FAIL: concepts CLI"
    test_failed=$((test_failed + 1))
fi

# Self-test: verify hook scripts
for script in concept-extract.sh brief-write.sh brief-inject.sh review-check.sh reflect-gate.sh reflect-surface.sh; do
    if [ -f "$HOME/.claude/scripts/$script" ]; then
        echo "  PASS: $script installed"
        test_passed=$((test_passed + 1))
    else
        echo "  WARN: $script not found (run 'concepts hooks install' manually)"
    fi
done

echo ""

if [ "$test_failed" -eq 0 ]; then
    echo "All $test_passed checks passed."
    echo ""
    echo "Usage (from $workspace_path):"
    echo "  /save              Save session learnings to memory"
    echo "  /reflect           Run background memory consolidation"
    echo "  /review            Weekly signal triage and synthesis"
    echo "  concepts brief     Generate session context brief"
    echo "  concepts <cmd>     Manage the knowledge graph"
    echo "  concepts explore    Open graph explorer in browser"
    echo "  concepts hooks install  Install automated hooks"
    echo ""
    echo "To customize paths, edit .memory-config in your workspace root."
    echo "Without .memory-config, PARA defaults are used (2-areas/me/daily, etc.)."
else
    echo "ERROR: $test_failed skill(s) failed verification. See details above."
    exit 1
fi
