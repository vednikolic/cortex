"""Tests for CRUD operations."""

import pytest
from cortex_lib.ops import upsert_concept, query_concept, log_extraction


def test_upsert_creates_new_concept(db):
    result = upsert_concept(db, "python", kind="tool", project="cortex", session_hash="s1")
    assert result['action'] == 'created'
    assert result['name'] == 'python'
    assert result['concept_id'] > 0


def test_upsert_updates_existing(db):
    upsert_concept(db, "python", session_hash="s1")
    result = upsert_concept(db, "python", session_hash="s2")
    assert result['action'] == 'updated'

    row = db.execute("SELECT source_count FROM concepts WHERE name = 'python'").fetchone()
    assert row['source_count'] == 2


def test_upsert_fuzzy_matches_existing(db):
    upsert_concept(db, "kubernetes", session_hash="s1")
    result = upsert_concept(db, "kubernates", session_hash="s2")  # typo
    assert result['action'] == 'updated'
    assert result['name'] == 'kubernetes'


def test_upsert_invalid_kind_raises(db):
    with pytest.raises(ValueError):
        upsert_concept(db, "test", kind="invalid_kind")


def test_upsert_adds_source(db):
    upsert_concept(db, "python", project="cortex", session_hash="s1", weight=3)
    sources = db.execute("SELECT * FROM concept_sources").fetchall()
    assert len(sources) == 1
    assert sources[0]['project'] == 'cortex'
    assert sources[0]['weight'] == 3


def test_query_returns_concept_with_edges(db):
    upsert_concept(db, "python", session_hash="s1")
    upsert_concept(db, "sqlite", session_hash="s1")
    from cortex_lib.ops import add_edge
    add_edge(db, "python", "sqlite", "related-to")

    result = query_concept(db, "python")
    assert result is not None
    assert result['concept']['name'] == 'python'
    assert len(result['edges']) == 1


def test_query_returns_none_for_unknown(db):
    result = query_concept(db, "nonexistent")
    assert result is None


def test_log_extraction(db):
    eid = log_extraction(db, "session-abc", ["a", "b"], ["a"], [{"from": "a", "to": "b", "relation": "related-to"}], 1, 3)
    assert eid > 0
    row = db.execute("SELECT * FROM extraction_log WHERE id = ?", (eid,)).fetchone()
    assert row['rejected'] == 1
    assert row['weight'] == 3
