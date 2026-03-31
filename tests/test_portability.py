"""Export/import tests: round-trip, merge semantics, conflict handling."""

import json
import pytest
from cortex_lib.db import init_db
from cortex_lib.ops import upsert_concept, add_edge
from cortex_lib.portability import export_graph, import_graph


def test_export_roundtrip(tmp_path):
    """Export then import into a fresh DB preserves all data."""
    db1 = init_db(tmp_path / "source.db")
    upsert_concept(db1, "fastapi", kind="tool", project="my-api")
    upsert_concept(db1, "auth", kind="topic", project="my-api")
    add_edge(db1, "fastapi", "auth", "related-to")

    data = export_graph(db1)
    assert len(data["concepts"]) == 2
    assert len(data["edges"]) == 1
    assert data["version"] == "cortex-export-v1"

    db2 = init_db(tmp_path / "target.db")
    result = import_graph(db2, data)
    assert result["concepts_created"] == 2
    assert result["edges_created"] == 1
    db1.close()
    db2.close()


def test_import_merge_existing(tmp_path):
    """Importing into a DB with existing concepts merges, not duplicates."""
    db = init_db(tmp_path / "merge.db")
    upsert_concept(db, "fastapi", kind="tool", project="my-api")

    data = export_graph(db)
    # Re-import same data: should upsert, not fail
    result = import_graph(db, data)
    assert result["concepts_created"] == 0
    assert result["concepts_updated"] == 1
    db.close()


def test_import_strengthens_edges(tmp_path):
    """Importing an edge that already exists increments strength."""
    db1 = init_db(tmp_path / "source.db")
    upsert_concept(db1, "a", kind="topic")
    upsert_concept(db1, "b", kind="topic")
    add_edge(db1, "a", "b", "related-to")
    data = export_graph(db1)

    db2 = init_db(tmp_path / "target.db")
    upsert_concept(db2, "a", kind="topic")
    upsert_concept(db2, "b", kind="topic")
    add_edge(db2, "a", "b", "related-to")

    import_graph(db2, data)
    row = db2.execute(
        "SELECT strength FROM concept_edges WHERE relation='related-to'"
    ).fetchone()
    assert row[0] == 2  # original 1 + imported 1
    db1.close()
    db2.close()


def test_export_includes_normalization_rules(tmp_path):
    """Export includes normalization rules for alias preservation."""
    db = init_db(tmp_path / "norm.db")
    upsert_concept(db, "kubernetes", kind="tool")
    db.execute(
        "INSERT INTO normalization_rules (variant, canonical_id, confidence, source, created_at, updated_at) "
        "VALUES (?, (SELECT id FROM concepts WHERE name=?), 1.0, 'cli', datetime('now'), datetime('now'))",
        ("k8s", "kubernetes")
    )
    db.commit()

    data = export_graph(db)
    assert len(data["normalization_rules"]) == 1
    assert data["normalization_rules"][0]["variant"] == "k8s"
    db.close()


def test_export_json_serializable(tmp_path):
    """Export output is valid JSON (no datetime or bytes issues)."""
    db = init_db(tmp_path / "serial.db")
    upsert_concept(db, "test", kind="topic")

    data = export_graph(db)
    serialized = json.dumps(data)
    roundtrip = json.loads(serialized)
    assert roundtrip["concepts"][0]["name"] == "test"
    db.close()
