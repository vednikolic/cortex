"""Tests for hooks verify command."""

import json
import pytest
from pathlib import Path

from cortex_lib.hooks import (
    hooks_verify, generate_hooks_config, install_hooks,
    EXPECTED_HOOK_ORDER,
)


def test_verify_correct_ordering(tmp_path):
    """Correctly ordered hooks pass verification."""
    scripts_dir = tmp_path / "scripts"
    settings_path = tmp_path / "settings.json"
    settings_path.write_text("{}")
    install_hooks(scripts_dir=scripts_dir, settings_path=settings_path)

    result = hooks_verify(settings_path=settings_path)
    assert result['valid'] is True
    assert result['issues'] == []


def test_verify_missing_settings(tmp_path):
    """Missing settings.json is reported."""
    result = hooks_verify(settings_path=tmp_path / "nonexistent.json")
    assert result['valid'] is False
    assert any('not found' in i for i in result['issues'])


def test_verify_missing_hook(tmp_path):
    """Missing hooks are detected."""
    settings_path = tmp_path / "settings.json"
    # Only include some hooks, omitting session-init
    settings_path.write_text(json.dumps({
        "hooks": {
            "SessionStart": [
                {"matcher": "", "hooks": [{"type": "command", "command": "bash ~/.claude/scripts/review-check.sh"}]},
                {"matcher": "", "hooks": [{"type": "command", "command": "bash ~/.claude/scripts/reflect-surface.sh"}]},
                {"matcher": "", "hooks": [{"type": "command", "command": "bash ~/.claude/scripts/brief-inject.sh"}]},
            ],
            "Stop": [
                {"matcher": "", "hooks": [{"type": "command", "command": "bash ~/.claude/scripts/session-capture.sh"}]},
                {"matcher": "", "hooks": [{"type": "command", "command": "bash ~/.claude/scripts/concept-extract.sh"}]},
                {"matcher": "", "hooks": [{"type": "command", "command": "bash ~/.claude/scripts/brief-write.sh"}]},
                {"matcher": "", "hooks": [{"type": "command", "command": "bash ~/.claude/scripts/reflect-gate.sh"}]},
                {"matcher": "", "hooks": [{"type": "command", "command": "bash ~/.claude/scripts/review-gate.sh"}]},
            ],
        }
    }))

    result = hooks_verify(settings_path=settings_path)
    assert result['valid'] is False
    assert any('session-init.sh' in i for i in result['issues'])


def test_verify_wrong_ordering(tmp_path):
    """Out-of-order hooks are detected."""
    settings_path = tmp_path / "settings.json"
    # Swap concept-extract and session-capture in Stop
    settings_path.write_text(json.dumps({
        "hooks": {
            "SessionStart": [
                {"matcher": "", "hooks": [{"type": "command", "command": "bash ~/.claude/scripts/session-init.sh"}]},
                {"matcher": "", "hooks": [{"type": "command", "command": "bash ~/.claude/scripts/review-check.sh"}]},
                {"matcher": "", "hooks": [{"type": "command", "command": "bash ~/.claude/scripts/reflect-surface.sh"}]},
                {"matcher": "", "hooks": [{"type": "command", "command": "bash ~/.claude/scripts/brief-inject.sh"}]},
            ],
            "Stop": [
                {"matcher": "", "hooks": [{"type": "command", "command": "bash ~/.claude/scripts/concept-extract.sh"}]},
                {"matcher": "", "hooks": [{"type": "command", "command": "bash ~/.claude/scripts/session-capture.sh"}]},
                {"matcher": "", "hooks": [{"type": "command", "command": "bash ~/.claude/scripts/brief-write.sh"}]},
                {"matcher": "", "hooks": [{"type": "command", "command": "bash ~/.claude/scripts/reflect-gate.sh"}]},
                {"matcher": "", "hooks": [{"type": "command", "command": "bash ~/.claude/scripts/review-gate.sh"}]},
            ],
        }
    }))

    result = hooks_verify(settings_path=settings_path)
    assert result['valid'] is False
    assert any('ordering mismatch' in i for i in result['issues'])


def test_verify_unknown_hook(tmp_path):
    """Unknown hooks are flagged."""
    scripts_dir = tmp_path / "scripts"
    settings_path = tmp_path / "settings.json"
    settings_path.write_text("{}")
    install_hooks(scripts_dir=scripts_dir, settings_path=settings_path)

    # Add an unknown hook
    data = json.loads(settings_path.read_text())
    data['hooks']['Stop'].append({
        "matcher": "",
        "hooks": [{"type": "command", "command": "bash ~/.claude/scripts/unknown-hook.sh"}]
    })
    settings_path.write_text(json.dumps(data))

    result = hooks_verify(settings_path=settings_path)
    assert result['valid'] is False
    assert any('unknown hook' in i for i in result['issues'])


def test_verify_missing_event(tmp_path):
    """Missing event section is detected."""
    settings_path = tmp_path / "settings.json"
    settings_path.write_text(json.dumps({
        "hooks": {
            "SessionStart": [
                {"matcher": "", "hooks": [{"type": "command", "command": "bash ~/.claude/scripts/session-init.sh"}]},
                {"matcher": "", "hooks": [{"type": "command", "command": "bash ~/.claude/scripts/review-check.sh"}]},
                {"matcher": "", "hooks": [{"type": "command", "command": "bash ~/.claude/scripts/reflect-surface.sh"}]},
                {"matcher": "", "hooks": [{"type": "command", "command": "bash ~/.claude/scripts/brief-inject.sh"}]},
            ],
        }
    }))

    result = hooks_verify(settings_path=settings_path)
    assert result['valid'] is False
    assert any('Missing event: Stop' in i for i in result['issues'])


def test_expected_hook_order_constant():
    """EXPECTED_HOOK_ORDER matches generate_hooks_config output."""
    config = generate_hooks_config()
    for event, expected in EXPECTED_HOOK_ORDER.items():
        actual = []
        for entry in config['hooks'][event]:
            cmd = entry['hooks'][0]['command']
            actual.append(cmd.split('/')[-1])
        assert actual == expected, f"{event} ordering mismatch"
