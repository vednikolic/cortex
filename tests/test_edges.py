"""Edge lifecycle tests: creation, strength increment, history tracking, decay."""

import json
from datetime import datetime, timezone, timedelta

import pytest
from cortex_lib.ops import upsert_concept, add_edge


def test_edge_creation(db):
    upsert_concept(db, "python")
    upsert_concept(db, "sqlite")
    result = add_edge(db, "python", "sqlite", "related-to")
    assert result['action'] == 'created'
    assert result['strength'] == 1


def test_edge_strength_increment(db):
    upsert_concept(db, "python")
    upsert_concept(db, "sqlite")
    add_edge(db, "python", "sqlite", "related-to")
    result = add_edge(db, "python", "sqlite", "related-to")
    assert result['action'] == 'strengthened'
    assert result['strength'] == 2


def test_edge_history_tracking(db):
    upsert_concept(db, "python")
    upsert_concept(db, "sqlite")
    add_edge(db, "python", "sqlite", "related-to")
    add_edge(db, "python", "sqlite", "related-to")

    edge = db.execute("SELECT history FROM concept_edges").fetchone()
    history = json.loads(edge['history'])
    assert len(history) == 2


def test_edge_invalid_relation(db):
    upsert_concept(db, "python")
    upsert_concept(db, "sqlite")
    with pytest.raises(ValueError):
        add_edge(db, "python", "sqlite", "invalid-relation")


def test_edge_nonexistent_concept(db):
    upsert_concept(db, "python")
    with pytest.raises(ValueError):
        add_edge(db, "python", "nonexistent", "related-to")


def test_all_eight_relations_valid(db):
    """Verify all 8 relation types can be created."""
    upsert_concept(db, "a")
    upsert_concept(db, "b")
    relations = [
        'related-to', 'depends-on', 'conflicts-with', 'enables',
        'is-instance-of', 'supersedes', 'blocked-by', 'derived-from',
    ]
    for rel in relations:
        result = add_edge(db, "a", "b", rel)
        assert result['action'] == 'created', f"Failed for relation: {rel}"
