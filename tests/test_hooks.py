"""Hook installer tests."""

import json
import pytest
from pathlib import Path
from cortex_lib.hooks import generate_hooks_config, install_hooks, REVIEW_CHECK_SH, REFLECT_GATE_SH


def test_generate_hooks_config():
    """generate_hooks_config returns valid matcher-wrapped settings structure."""
    config = generate_hooks_config()
    assert "hooks" in config
    hooks = config["hooks"]
    assert "SessionStart" in hooks
    assert "Stop" in hooks
    # Verify matcher-wrapped format
    for entry in hooks["SessionStart"]:
        assert "matcher" in entry
        assert "hooks" in entry
        assert isinstance(entry["hooks"], list)
        assert entry["hooks"][0]["type"] == "command"
    for entry in hooks["Stop"]:
        assert "matcher" in entry
        assert "hooks" in entry


def test_install_hooks_creates_scripts(tmp_path):
    """install_hooks writes hook scripts to the target directory."""
    scripts_dir = tmp_path / "scripts"
    settings_path = tmp_path / "settings.json"
    settings_path.write_text("{}")

    install_hooks(scripts_dir=scripts_dir, settings_path=settings_path)

    assert (scripts_dir / "review-check.sh").exists()
    assert (scripts_dir / "reflect-gate.sh").exists()
    rc = (scripts_dir / "review-check.sh").read_text()
    assert "#!/usr/bin/env bash" in rc
    assert "review-pending" in rc


def test_install_hooks_patches_settings(tmp_path):
    """install_hooks adds hooks to settings.json without overwriting existing."""
    scripts_dir = tmp_path / "scripts"
    settings_path = tmp_path / "settings.json"
    settings_path.write_text(json.dumps({"existingKey": True}))

    install_hooks(scripts_dir=scripts_dir, settings_path=settings_path)

    data = json.loads(settings_path.read_text())
    assert "existingKey" in data
    assert "hooks" in data


def test_review_check_script_content():
    """review-check.sh checks for the pending marker file."""
    assert ".cortex-review-pending" in REVIEW_CHECK_SH
    assert "#!/usr/bin/env bash" in REVIEW_CHECK_SH
