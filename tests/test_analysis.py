"""Tests for analysis commands: shared, stale, hot, graph, stats, velocity."""

from datetime import datetime, timezone, timedelta
from cortex_lib.ops import upsert_concept, add_edge, log_extraction
from cortex_lib.analysis import (
    shared_concepts, stale_concepts, hot_concepts,
    graph_summary, weight_stats, concept_velocity,
)


def _populate(db):
    """Build a small test graph."""
    upsert_concept(db, "python", kind="tool", project="cortex", session_hash="s1", weight=3)
    upsert_concept(db, "sqlite", kind="tool", project="cortex", session_hash="s1", weight=3)
    upsert_concept(db, "knowledge-graph", kind="pattern", project="cortex", session_hash="s1")
    upsert_concept(db, "react", kind="tool", project="website", session_hash="s2", weight=2)
    # Cross-project concept
    upsert_concept(db, "python", project="website", session_hash="s2", weight=2)
    add_edge(db, "python", "sqlite", "related-to")
    add_edge(db, "knowledge-graph", "sqlite", "depends-on")
    return db


def test_shared_returns_cross_project(db):
    _populate(db)
    results = shared_concepts(db)
    names = [r['name'] for r in results]
    assert 'python' in names


def test_shared_excludes_single_project(db):
    _populate(db)
    results = shared_concepts(db)
    names = [r['name'] for r in results]
    assert 'sqlite' not in names


def test_stale_none_when_fresh(db):
    _populate(db)
    results = stale_concepts(db, days=60)
    assert results == []


def test_stale_finds_old_concepts(db):
    upsert_concept(db, "ancient")
    old = (datetime.now(timezone.utc) - timedelta(days=90)).isoformat()
    db.execute("UPDATE concepts SET last_referenced = ? WHERE name = 'ancient'", (old,))
    db.commit()
    results = stale_concepts(db, days=60)
    assert len(results) == 1
    assert results[0]['name'] == 'ancient'


def test_hot_concepts_ordered(db):
    _populate(db)
    results = hot_concepts(db, limit=3)
    assert len(results) <= 3
    assert results[0]['name'] == 'python'  # most sources


def test_graph_summary_counts(db):
    _populate(db)
    s = graph_summary(db)
    assert s['concepts'] == 4
    assert s['edges'] == 2
    assert s['projects'] >= 2


def test_weight_stats_empty(db):
    result = weight_stats(db)
    assert result['total_extractions'] == 0


def test_weight_stats_populated(db):
    upsert_concept(db, "alpha")
    log_extraction(db, "s1", ["alpha"], ["alpha"], [], 0, 2)
    log_extraction(db, "s2", ["beta"], [], [], 1, 3)
    result = weight_stats(db)
    assert result['total_extractions'] == 2


def test_concept_velocity(db):
    upsert_concept(db, "python", session_hash="s1")
    result = concept_velocity(db, weeks=4)
    assert 'weeks' in result
    assert 'avg_per_week' in result
    assert len(result['weeks']) == 4
