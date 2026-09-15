"""Eval harness tests: document loading and judge invocation."""

import importlib.util
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("eval_harness", REPO_ROOT / "evals" / "eval.py")
eval_harness = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(eval_harness)


def test_load_document_appends_skill_references(tmp_path):
    skill = tmp_path / "SKILL.md"
    skill.write_text("# Skill body\n")
    refs = tmp_path / "references"
    refs.mkdir()
    (refs / "b.md").write_text("beta reference\n")
    (refs / "a.md").write_text("alpha reference\n")

    document = eval_harness.load_document(str(skill))

    assert document.startswith("# Skill body")
    assert "references/a.md" in document
    assert document.index("alpha reference") < document.index("beta reference")


def test_load_document_without_references_returns_file(tmp_path):
    doc = tmp_path / "plain.md"
    doc.write_text("just this\n")
    assert eval_harness.load_document(str(doc)) == "just this\n"


def test_judge_command_skips_user_hooks_and_session_persistence():
    command = eval_harness.judge_command()
    assert command[:2] == ["claude", "-p"]
    assert command[command.index("--setting-sources") + 1] == "project"
    assert "--no-session-persistence" in command


def test_normalize_item_accepts_name_and_prompt_keys():
    item = eval_harness.normalize_item({"name": "x", "prompt": "Is it?", "weight": 0.5})
    assert (item["id"], item["check"], item["weight"]) == ("x", "Is it?", 0.5)
