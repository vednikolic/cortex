"""Install portable workflow adapters into a workspace."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable


REPO_ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS_SRC = REPO_ROOT / "workflows"
ADAPTERS_SRC = REPO_ROOT / "adapters"

SUPPORTED_ADAPTERS = ("claude-code", "gemini-cli", "codex", "prompts")


def _copy_tree(src: Path, dest: Path) -> list[str]:
    """Copy files from src to dest, preserving relative paths."""
    written: list[str] = []
    for path in sorted(p for p in src.rglob("*") if p.is_file()):
        rel = path.relative_to(src)
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(path.read_text())
        written.append(str(target))
    return written


def _copy_files(files: Iterable[tuple[Path, Path]]) -> list[str]:
    written: list[str] = []
    for src, dest in files:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(src.read_text())
        written.append(str(dest))
    return written


def _install_workflows(workspace: Path) -> list[str]:
    return _copy_tree(WORKFLOWS_SRC, workspace / ".agents" / "workflows" / "cortex")


def _ensure_codex_marketplace(workspace: Path) -> str:
    path = workspace / ".agents" / "plugins" / "marketplace.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        data = json.loads(path.read_text())
    else:
        data = {
            "name": "local",
            "interface": {"displayName": "Local"},
            "plugins": [],
        }

    plugins = data.setdefault("plugins", [])
    entry = {
        "name": "workspace-memory",
        "source": {
            "source": "local",
            "path": "./plugins/workspace-memory",
        },
        "policy": {
            "installation": "INSTALLED_BY_DEFAULT",
            "authentication": "ON_INSTALL",
        },
        "category": "Productivity",
    }
    for index, plugin in enumerate(plugins):
        if plugin.get("name") == "workspace-memory":
            plugins[index] = entry
            break
    else:
        plugins.append(entry)

    path.write_text(json.dumps(data, indent=2) + "\n")
    return str(path)


def install_adapter(adapter: str, workspace: Path) -> dict[str, object]:
    """Install one adapter and the shared workflow contracts."""
    if adapter not in SUPPORTED_ADAPTERS:
        supported = ", ".join(SUPPORTED_ADAPTERS)
        raise ValueError(f"Unsupported adapter '{adapter}'. Supported: {supported}")

    workspace = workspace.resolve()
    written = _install_workflows(workspace)
    follow_up: list[str] = []

    if adapter == "prompts":
        written.extend(_copy_tree(ADAPTERS_SRC / "prompts", workspace / ".agents" / "workflows" / "prompts"))
        follow_up.append("Paste the installed prompt into any client with filesystem and shell access.")
    elif adapter == "gemini-cli":
        written.extend(_copy_tree(ADAPTERS_SRC / "gemini-cli" / "prompts", workspace / ".agents" / "workflows" / "gemini"))
        written.extend(_copy_files([
            (ADAPTERS_SRC / "gemini-cli" / "commands-or-docs.md",
             workspace / ".agents" / "workflows" / "gemini" / "commands-or-docs.md")
        ]))
        follow_up.append("Use the prompt files under .agents/workflows/gemini or copy them into the local command directory.")
    elif adapter == "claude-code":
        written.extend(_copy_tree(ADAPTERS_SRC / "claude-code" / "skills", workspace / ".claude" / "skills"))
        follow_up.append("Start a fresh session if the client does not reload skills automatically.")
    elif adapter == "codex":
        written.extend(_copy_tree(ADAPTERS_SRC / "codex" / "skills", workspace / ".codex-compat-skills"))
        written.extend(_copy_tree(ADAPTERS_SRC / "codex" / "plugin", workspace / "plugins" / "workspace-memory"))
        written.append(_ensure_codex_marketplace(workspace))
        follow_up.append("Reload the local plugin marketplace, then start a fresh session to see /save, /reflect, and /review.")

    return {
        "adapter": adapter,
        "workspace": str(workspace),
        "files_written": written,
        "follow_up": follow_up,
    }
