"""Project definition tests."""

from cortex_lib.ops import upsert_concept
from cortex_lib.analysis import shared_concepts


def test_project_field_populated(db):
    upsert_concept(db, "python", project="cortex", session_hash="s1")
    sources = db.execute("SELECT project FROM concept_sources").fetchall()
    assert sources[0]['project'] == 'cortex'


def test_default_project_empty_string(db):
    upsert_concept(db, "orphan", session_hash="s1")
    sources = db.execute("SELECT project FROM concept_sources").fetchall()
    assert sources[0]['project'] == ''


def test_shared_requires_two_projects(db):
    upsert_concept(db, "python", project="cortex", session_hash="s1")
    upsert_concept(db, "python", project="website", session_hash="s2")
    upsert_concept(db, "sqlite", project="cortex", session_hash="s1")
    results = shared_concepts(db)
    names = [r['name'] for r in results]
    assert 'python' in names
    assert 'sqlite' not in names
