"""Deterministic workflow helper tests."""

from datetime import date

from cortex_lib.workflow_helpers import (
    daily_note_paths,
    friction_counts,
    monday_for,
    revisit_decisions,
    workflow_context,
)


def test_monday_for():
    assert monday_for(date(2026, 5, 7)).isoformat() == "2026-05-04"
    assert monday_for(date(2026, 5, 4)).isoformat() == "2026-05-04"


def test_daily_note_paths_returns_existing_recent_notes(tmp_path):
    daily = tmp_path / "2-areas" / "me" / "daily"
    daily.mkdir(parents=True)
    (daily / "2026-05-07.md").write_text("# Today\n")
    (daily / "2026-05-05.md").write_text("# Earlier\n")
    (daily / "2026-04-01.md").write_text("# Old\n")

    paths = daily_note_paths(tmp_path, days=7, today=date(2026, 5, 7))

    assert [p.name for p in paths] == ["2026-05-07.md", "2026-05-05.md"]


def test_revisit_decisions_finds_old_markers(tmp_path):
    project = tmp_path / "1-projects" / "app"
    project.mkdir(parents=True)
    (project / "AGENTS.md").write_text(
        "- [revisit] 2026-04-01 decide whether to keep this rule\n"
        "- [revisit] 2026-05-01 this is still fresh\n"
    )

    results = revisit_decisions(tmp_path, older_than_days=14, today=date(2026, 5, 7))

    assert len(results) == 1
    assert results[0]["date"] == "2026-04-01"


def test_friction_counts_returns_repeated_signals(tmp_path):
    first = tmp_path / "1-projects" / "app" / "AGENTS.md"
    second = tmp_path / "2-areas" / "me" / "reflect-log.md"
    first.parent.mkdir(parents=True)
    second.parent.mkdir(parents=True)
    first.write_text("- Friction: hook install order needed manual repair\n")
    second.write_text("- Friction: hook install order needed manual repair\n")

    results = friction_counts(tmp_path)

    assert results == [
        {
            "signal": "hook install order needed manual repair",
            "count": 2,
            "example": "- Friction: hook install order needed manual repair",
        }
    ]


def test_workflow_context_combines_helper_outputs(tmp_path):
    daily = tmp_path / "2-areas" / "me" / "daily"
    daily.mkdir(parents=True)
    (daily / "2026-05-07.md").write_text("# Today\n")

    result = workflow_context(tmp_path, today=date(2026, 5, 7))

    assert result["today"] == "2026-05-07"
    assert result["week_start"] == "2026-05-04"
    assert len(result["daily_notes_7d"]) == 1
