"""Review module tests: weekly summary CRUD, signal triage."""

import json
import pytest
from datetime import datetime, timezone, timedelta
from cortex_lib.db import utc_now
from cortex_lib.ops import upsert_concept, add_edge
from cortex_lib.confidence import promote_concept
from cortex_lib.review import (
    create_weekly_summary, list_weekly_summaries, get_weekly_summary,
    triage_signal, pending_signals, generate_synthesis,
)


def _populate(db):
    """Create a graph with enough data for synthesis."""
    for name in ["python", "sqlite", "testing", "cortex", "knowledge-graph"]:
        upsert_concept(db, name, kind="tool", project="cortex", session_hash="s1")
    upsert_concept(db, "react", kind="tool", project="website", session_hash="s2")
    upsert_concept(db, "testing", project="website", session_hash="s3")
    add_edge(db, "python", "sqlite", "related-to")
    add_edge(db, "cortex", "knowledge-graph", "enables")
    add_edge(db, "testing", "python", "related-to")


def test_create_weekly_summary(db):
    _populate(db)
    summary = create_weekly_summary(db, "2026-03-17")
    assert summary['week_start'] == '2026-03-17'
    assert summary['concept_count'] > 0
    assert summary['id'] > 0


def test_create_duplicate_week_raises(db):
    _populate(db)
    create_weekly_summary(db, "2026-03-17")
    with pytest.raises(ValueError, match="already exists"):
        create_weekly_summary(db, "2026-03-17")


def test_list_weekly_summaries(db):
    _populate(db)
    create_weekly_summary(db, "2026-03-10")
    create_weekly_summary(db, "2026-03-17")
    summaries = list_weekly_summaries(db)
    assert len(summaries) == 2
    assert summaries[0]['week_start'] == '2026-03-17'  # newest first


def test_get_weekly_summary(db):
    _populate(db)
    created = create_weekly_summary(db, "2026-03-17")
    fetched = get_weekly_summary(db, "2026-03-17")
    assert fetched['id'] == created['id']


def test_get_missing_summary_returns_none(db):
    assert get_weekly_summary(db, "2026-01-01") is None


def test_triage_promote(db):
    _populate(db)
    result = triage_signal(db, "python", action="promote", target_confidence="established")
    assert result['action'] == 'promote'
    assert result['new_confidence'] == 'established'


def test_triage_dismiss(db):
    """Dismiss sets edge dismissed=1."""
    _populate(db)
    edge = db.execute("SELECT id FROM concept_edges LIMIT 1").fetchone()
    result = triage_signal(db, edge_id=edge['id'], action="dismiss")
    assert result['action'] == 'dismiss'
    dismissed = db.execute(
        "SELECT dismissed FROM concept_edges WHERE id = ?", (edge['id'],)
    ).fetchone()
    assert dismissed['dismissed'] == 1


def test_triage_defer_is_noop(db):
    """Defer logs intent but changes nothing."""
    _populate(db)
    result = triage_signal(db, "python", action="defer")
    assert result['action'] == 'defer'


def test_triage_invalid_action_raises(db):
    _populate(db)
    with pytest.raises(ValueError, match="Invalid action"):
        triage_signal(db, "python", action="delete")


def test_generate_synthesis(db):
    """Synthesis includes graph snapshot and signals."""
    _populate(db)
    synthesis = generate_synthesis(db)
    assert 'graph_snapshot' in synthesis
    assert 'promotion_eligible' in synthesis
    assert 'stale' in synthesis
    assert 'velocity' in synthesis
    assert 'shared' in synthesis


def test_pending_signals(db):
    """Pending signals returns concepts eligible for promotion."""
    for i in range(4):
        upsert_concept(db, "python", session_hash=f"s{i}", project="cortex")
    signals = pending_signals(db)
    assert any(s['name'] == 'python' for s in signals['promotion_eligible'])


def test_generate_synthesis_with_prior_week(db):
    """Synthesis includes delta when a prior weekly summary exists."""
    _populate(db)
    create_weekly_summary(db, "2026-03-10")
    # Add more data after the summary
    upsert_concept(db, "docker", kind="tool", project="cortex", session_hash="s4")
    synthesis = generate_synthesis(db)
    assert synthesis['delta'] != {}
    assert 'concepts' in synthesis['delta']
