"""Hook installer tests."""

import json
import pytest
from pathlib import Path
from cortex_lib.hooks import (
    generate_hooks_config, install_hooks,
    REVIEW_CHECK_SH, REFLECT_GATE_SH, CONCEPT_EXTRACT_SH,
)


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


def test_concept_extract_script_content():
    """concept-extract.sh reads last-session.json and runs CLI commands."""
    assert "#!/usr/bin/env bash" in CONCEPT_EXTRACT_SH
    assert "last-session.json" in CONCEPT_EXTRACT_SH
    assert "concepts" in CONCEPT_EXTRACT_SH
    assert "rm -f" in CONCEPT_EXTRACT_SH
    assert 'if [ ! -f "$SESSION_FILE" ]; then exit 0; fi' in CONCEPT_EXTRACT_SH
    assert "upsert" in CONCEPT_EXTRACT_SH
    assert "log-extraction" in CONCEPT_EXTRACT_SH


def test_concept_extract_hook_ordering():
    """concept-extract.sh runs before brief-write.sh in Stop hooks."""
    config = generate_hooks_config()
    stop_hooks = config["hooks"]["Stop"]
    commands = []
    for entry in stop_hooks:
        for h in entry["hooks"]:
            commands.append(h["command"])

    extract_idx = next(i for i, c in enumerate(commands) if "concept-extract" in c)
    brief_idx = next(i for i, c in enumerate(commands) if "brief-write" in c)
    reflect_idx = next(i for i, c in enumerate(commands) if "reflect-gate" in c)

    assert extract_idx < brief_idx, "concept-extract must run before brief-write"
    assert brief_idx < reflect_idx, "brief-write must run before reflect-gate"


def test_install_hooks_includes_concept_extract(tmp_path):
    """install_hooks writes concept-extract.sh to the scripts directory."""
    scripts_dir = tmp_path / "scripts"
    settings_path = tmp_path / "settings.json"
    settings_path.write_text("{}")

    result = install_hooks(scripts_dir=scripts_dir, settings_path=settings_path)

    assert "concept-extract.sh" in result["scripts_installed"]
    assert (scripts_dir / "concept-extract.sh").exists()
    content = (scripts_dir / "concept-extract.sh").read_text()
    assert "last-session.json" in content
