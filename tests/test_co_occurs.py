"""Co-occurring concept detection tests."""

import pytest
from cortex_lib.db import init_db
from cortex_lib.ops import upsert_concept, add_edge
from cortex_lib.analysis import co_occurring_concepts


def test_co_occurs_finds_shared_neighbors(tmp_path):
    """Two concepts sharing 2+ common neighbors are co-occurring."""
    db = init_db(tmp_path / "co.db")
    upsert_concept(db, "fastapi", kind="tool")
    upsert_concept(db, "django", kind="tool")
    upsert_concept(db, "python", kind="tool")
    upsert_concept(db, "rest-api", kind="pattern")
    upsert_concept(db, "auth", kind="topic")

    # Both fastapi and django connect to python, rest-api, and auth
    add_edge(db, "fastapi", "python", "depends-on")
    add_edge(db, "fastapi", "rest-api", "enables")
    add_edge(db, "fastapi", "auth", "related-to")
    add_edge(db, "django", "python", "depends-on")
    add_edge(db, "django", "rest-api", "enables")
    add_edge(db, "django", "auth", "related-to")

    results = co_occurring_concepts(db, "fastapi")
    assert len(results) == 1
    assert results[0]["concept"] == "django"
    assert results[0]["shared_count"] == 3
    assert set(results[0]["shared_neighbors"]) == {"python", "rest-api", "auth"}
    db.close()


def test_co_occurs_respects_min_shared(tmp_path):
    """min_shared threshold filters out weak co-occurrences."""
    db = init_db(tmp_path / "min.db")
    upsert_concept(db, "a", kind="topic")
    upsert_concept(db, "b", kind="topic")
    upsert_concept(db, "c", kind="topic")

    add_edge(db, "a", "c", "related-to")
    add_edge(db, "b", "c", "related-to")

    # Default min_shared=2, only 1 shared neighbor -> empty
    results = co_occurring_concepts(db, "a")
    assert len(results) == 0

    # With min_shared=1 -> finds b
    results = co_occurring_concepts(db, "a", min_shared=1)
    assert len(results) == 1
    assert results[0]["concept"] == "b"
    db.close()


def test_co_occurs_unknown_concept_raises(tmp_path):
    """Unknown concept name raises ValueError."""
    db = init_db(tmp_path / "unknown.db")
    with pytest.raises(ValueError, match="not found"):
        co_occurring_concepts(db, "nonexistent")
    db.close()


def test_co_occurs_no_edges_returns_empty(tmp_path):
    """Concept with no edges returns empty list."""
    db = init_db(tmp_path / "iso.db")
    upsert_concept(db, "isolated", kind="topic")
    results = co_occurring_concepts(db, "isolated")
    assert results == []
    db.close()
