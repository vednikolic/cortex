"""Correction primitive tests: correct, undo-last, merge (reqs 2.20, 2.21, 2.T5)."""

import json
from cortex_lib.ops import upsert_concept, add_edge, log_extraction
from cortex_lib.correction import correct_concept, undo_last_extraction, merge_concepts


def test_correct_renames_concept(db):
    upsert_concept(db, "pytohn")
    result = correct_concept(db, "pytohn", "python")
    assert result['new_name'] == 'python'
    row = db.execute("SELECT name FROM concepts WHERE id = ?", (result['concept_id'],)).fetchone()
    assert row['name'] == 'python'


def test_correct_adds_old_name_as_alias(db):
    upsert_concept(db, "pytohn")
    correct_concept(db, "pytohn", "python")
    row = db.execute("SELECT aliases FROM concepts WHERE name = 'python'").fetchone()
    aliases = json.loads(row['aliases'])
    assert 'pytohn' in aliases


def test_correct_preserves_edges(db):
    upsert_concept(db, "pytohn")
    upsert_concept(db, "sqlite")
    add_edge(db, "pytohn", "sqlite", "related-to")
    correct_concept(db, "pytohn", "python")

    edges = db.execute("""
        SELECT c1.name as from_name, c2.name as to_name
        FROM concept_edges e
        JOIN concepts c1 ON e.from_concept_id = c1.id
        JOIN concepts c2 ON e.to_concept_id = c2.id
    """).fetchall()
    assert len(edges) == 1
    assert edges[0]['from_name'] == 'python'


def test_correct_logs_in_extraction_log(db):
    upsert_concept(db, "pytohn")
    correct_concept(db, "pytohn", "python")
    log = db.execute("SELECT * FROM extraction_log ORDER BY id DESC LIMIT 1").fetchone()
    assert 'correction' in log['session_hash']


def test_correct_creates_normalization_rule(db):
    upsert_concept(db, "pytohn")
    correct_concept(db, "pytohn", "python")
    rule = db.execute(
        "SELECT * FROM normalization_rules WHERE variant = 'pytohn'"
    ).fetchone()
    assert rule is not None


def test_correct_conflict_raises(db):
    upsert_concept(db, "python")
    upsert_concept(db, "javascript")
    try:
        correct_concept(db, "python", "javascript")
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert 'already exists' in str(e).lower()


def test_undo_last_removes_created_concepts(db):
    # Create concept via extraction
    upsert_concept(db, "gamma", session_hash="session2")
    log_extraction(db, "session2", ["gamma"], ["gamma"], [], 0, 2)

    result = undo_last_extraction(db)
    assert 'gamma' in result['removed_concepts']

    remaining = db.execute("SELECT name FROM concepts").fetchall()
    names = [r['name'] for r in remaining]
    assert 'gamma' not in names


def test_undo_last_removes_edges(db):
    upsert_concept(db, "alpha")
    upsert_concept(db, "beta")
    add_edge(db, "alpha", "beta", "related-to")
    log_extraction(
        db, "session1", ["alpha", "beta"], ["alpha", "beta"],
        [{"from": "alpha", "to": "beta", "relation": "related-to"}], 0, 3,
    )

    result = undo_last_extraction(db)
    assert len(result['removed_edges']) == 1
    edges = db.execute("SELECT * FROM concept_edges").fetchall()
    assert len(edges) == 0


def test_undo_last_empty_raises(db):
    try:
        undo_last_extraction(db)
        assert False, "Should have raised ValueError"
    except ValueError:
        pass


def test_merge_combines_concepts(db):
    upsert_concept(db, "js", session_hash="s1", project="web")
    upsert_concept(db, "javascript", session_hash="s2", project="web")
    result = merge_concepts(db, "js", "javascript")
    assert result['target'] == 'javascript'

    # Source concept should be gone
    remaining = db.execute("SELECT name FROM concepts").fetchall()
    names = [r['name'] for r in remaining]
    assert 'js' not in names
    assert 'javascript' in names


def test_merge_combines_sources(db):
    upsert_concept(db, "js", session_hash="s1", project="web")
    upsert_concept(db, "javascript", session_hash="s2", project="api")
    merge_concepts(db, "js", "javascript")

    target = db.execute("SELECT * FROM concepts WHERE name = 'javascript'").fetchone()
    sources = db.execute(
        "SELECT * FROM concept_sources WHERE concept_id = ?", (target['id'],)
    ).fetchall()
    assert len(sources) == 2


def test_merge_self_raises(db):
    upsert_concept(db, "python")
    try:
        merge_concepts(db, "python", "python")
        assert False, "Should have raised ValueError"
    except ValueError:
        pass
