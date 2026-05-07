"""Portable workflow adapter tests."""

import json
from pathlib import Path

import pytest

from cortex_lib.adapters import install_adapter


REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.mark.parametrize("workflow", ["save.md", "reflect.md", "review.md"])
def test_portable_contract_has_no_tool_specific_assumptions(workflow):
    text = (REPO_ROOT / "workflows" / workflow).read_text().lower()
    banned = [
        "claude",
        "codex",
        "gemini",
        "cursor",
        "chatgpt",
        "mcp",
        "slash command",
        "hook",
    ]
    for term in banned:
        assert term not in text


@pytest.mark.parametrize("adapter", ["claude-code", "gemini-cli", "codex", "prompts"])
def test_install_adapter_installs_shared_contract(adapter, tmp_path):
    result = install_adapter(adapter, tmp_path)

    assert result["adapter"] == adapter
    assert (tmp_path / ".agents" / "workflows" / "cortex" / "save.md").exists()
    assert (tmp_path / ".agents" / "workflows" / "cortex" / "reflect.md").exists()
    assert (tmp_path / ".agents" / "workflows" / "cortex" / "review.md").exists()
    assert result["files_written"]


def test_codex_install_writes_skills_plugin_and_marketplace(tmp_path):
    install_adapter("codex", tmp_path)

    assert (tmp_path / ".codex-compat-skills" / "save" / "SKILL.md").exists()
    assert (tmp_path / ".codex-compat-skills" / "reflect" / "SKILL.md").exists()
    assert (tmp_path / ".codex-compat-skills" / "review" / "SKILL.md").exists()
    assert (tmp_path / "plugins" / "workspace-memory" / "commands" / "save.md").exists()
    assert (tmp_path / "plugins" / "workspace-memory" / ".codex-plugin" / "plugin.json").exists()

    marketplace = json.loads((tmp_path / ".agents" / "plugins" / "marketplace.json").read_text())
    plugin = marketplace["plugins"][0]
    assert plugin["name"] == "workspace-memory"
    assert plugin["source"]["path"] == "./plugins/workspace-memory"


@pytest.mark.parametrize(
    ("adapter_path", "workflow"),
    [
        ("adapters/claude-code/skills/save/SKILL.md", "save.md"),
        ("adapters/claude-code/skills/reflect/SKILL.md", "reflect.md"),
        ("adapters/claude-code/skills/review/SKILL.md", "review.md"),
        ("adapters/gemini-cli/prompts/save.md", "save.md"),
        ("adapters/gemini-cli/prompts/reflect.md", "reflect.md"),
        ("adapters/gemini-cli/prompts/review.md", "review.md"),
        ("adapters/codex/skills/save/SKILL.md", "save.md"),
        ("adapters/codex/skills/reflect/SKILL.md", "reflect.md"),
        ("adapters/codex/skills/review/SKILL.md", "review.md"),
        ("adapters/prompts/save.md", "save.md"),
        ("adapters/prompts/reflect.md", "reflect.md"),
        ("adapters/prompts/review.md", "review.md"),
    ],
)
def test_primary_adapters_invoke_same_contract(adapter_path, workflow):
    text = (REPO_ROOT / adapter_path).read_text()
    assert f".agents/workflows/cortex/{workflow}" in text


def test_unsupported_adapter_fails(tmp_path):
    with pytest.raises(ValueError):
        install_adapter("unknown", tmp_path)
