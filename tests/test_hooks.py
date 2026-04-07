"""Hook installer tests."""

import json
import pytest
from pathlib import Path
from cortex_lib.hooks import (
    generate_hooks_config, install_hooks,
    REVIEW_CHECK_SH, REFLECT_GATE_SH, CONCEPT_EXTRACT_SH,
    SESSION_INIT_SH, SESSION_CAPTURE_SH,
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


def test_stop_hook_ordering():
    """Stop hooks run in correct order: capture, extract, brief, reflect, review."""
    config = generate_hooks_config()
    stop_hooks = config["hooks"]["Stop"]
    commands = []
    for entry in stop_hooks:
        for h in entry["hooks"]:
            commands.append(h["command"])

    capture_idx = next(i for i, c in enumerate(commands) if "session-capture" in c)
    extract_idx = next(i for i, c in enumerate(commands) if "concept-extract" in c)
    brief_idx = next(i for i, c in enumerate(commands) if "brief-write" in c)
    reflect_idx = next(i for i, c in enumerate(commands) if "reflect-gate" in c)
    review_idx = next(i for i, c in enumerate(commands) if "review-gate" in c)

    assert capture_idx < extract_idx, "session-capture must run before concept-extract"
    assert extract_idx < brief_idx, "concept-extract must run before brief-write"
    assert brief_idx < reflect_idx, "brief-write must run before reflect-gate"
    assert reflect_idx < review_idx, "reflect-gate must run before review-gate"


def test_session_start_hook_ordering():
    """SessionStart hooks: session-init first, brief-inject last."""
    config = generate_hooks_config()
    hooks = config["hooks"]["SessionStart"]
    commands = []
    for entry in hooks:
        for h in entry["hooks"]:
            commands.append(h["command"])

    init_idx = next(i for i, c in enumerate(commands) if "session-init" in c)
    inject_idx = next(i for i, c in enumerate(commands) if "brief-inject" in c)

    assert init_idx == 0, "session-init must be first SessionStart hook"
    assert inject_idx == len(commands) - 1, "brief-inject must be last SessionStart hook"


def test_session_init_script_content():
    """session-init.sh writes session-start JSON with HEAD ref and memory hash."""
    assert '#!/usr/bin/env bash' in SESSION_INIT_SH
    assert 'session-start' in SESSION_INIT_SH
    assert 'head_ref' in SESSION_INIT_SH
    assert 'memory_snapshot_hash' in SESSION_INIT_SH
    assert 'concepts_loaded' in SESSION_INIT_SH
    assert 'exit 0' in SESSION_INIT_SH


def test_session_capture_script_content():
    """session-capture.sh reads session-start and calls concepts capture."""
    assert '#!/usr/bin/env bash' in SESSION_CAPTURE_SH
    assert 'session-start' in SESSION_CAPTURE_SH
    assert 'concepts' in SESSION_CAPTURE_SH
    assert 'capture' in SESSION_CAPTURE_SH
    assert '.memory-config' in SESSION_CAPTURE_SH
    assert 'exit 0' in SESSION_CAPTURE_SH


def test_concept_extract_upgrades_session_status():
    """concept-extract.sh reads current-session-hash and upgrades to saved."""
    assert 'current-session-hash' in CONCEPT_EXTRACT_SH
    assert 'update-status' in CONCEPT_EXTRACT_SH
    assert 'saved' in CONCEPT_EXTRACT_SH
    assert 'enrich-queue' in CONCEPT_EXTRACT_SH


def test_install_hooks_includes_new_scripts(tmp_path):
    """install_hooks writes session-init.sh and session-capture.sh."""
    scripts_dir = tmp_path / "scripts"
    settings_path = tmp_path / "settings.json"
    settings_path.write_text("{}")

    result = install_hooks(scripts_dir=scripts_dir, settings_path=settings_path)
    assert "session-init.sh" in result["scripts_installed"]
    assert "session-capture.sh" in result["scripts_installed"]
    assert (scripts_dir / "session-init.sh").exists()
    assert (scripts_dir / "session-capture.sh").exists()


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
