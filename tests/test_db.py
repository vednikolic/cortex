"""Tests for schema creation, WAL mode, and database verification."""

import pytest
from pathlib import Path
from cortex_lib.db import verify_db, find_db_path


def test_init_creates_all_tables(db):
    tables = {row[0] for row in db.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()}
    expected = {'concepts', 'concept_sources', 'concept_edges',
                'normalization_rules', 'extraction_log', 'schema_meta',
                'weekly_summaries'}
    assert expected.issubset(tables)


def test_wal_mode_enabled(db):
    mode = db.execute("PRAGMA journal_mode").fetchone()[0]
    assert mode == 'wal'


def test_foreign_keys_enabled(db):
    fk = db.execute("PRAGMA foreign_keys").fetchone()[0]
    assert fk == 1


def test_schema_version(db):
    version = db.execute(
        "SELECT value FROM schema_meta WHERE key = 'version'"
    ).fetchone()[0]
    assert version == '3'


def test_verify_healthy_db(db):
    issues = verify_db(db)
    assert issues == []


def test_verify_catches_missing_table(db):
    db.execute("DROP TABLE extraction_log")
    issues = verify_db(db)
    assert any('Missing tables' in i for i in issues)


def test_concept_cascade_delete(db):
    """Deleting a concept cascades to sources and edges."""
    now = "2026-01-01T00:00:00Z"
    db.execute(
        "INSERT INTO concepts (name, kind, confidence, privacy_level, "
        "first_seen, last_referenced, source_count, created_at, updated_at) "
        "VALUES ('alpha', 'topic', 'tentative', 'private', ?, ?, 1, ?, ?)",
        (now, now, now, now)
    )
    db.execute(
        "INSERT INTO concepts (name, kind, confidence, privacy_level, "
        "first_seen, last_referenced, source_count, created_at, updated_at) "
        "VALUES ('beta', 'topic', 'tentative', 'private', ?, ?, 1, ?, ?)",
        (now, now, now, now)
    )
    db.execute(
        "INSERT INTO concept_sources (concept_id, session_hash, project, timestamp, weight) "
        "VALUES (1, 's1', '', ?, 1)", (now,)
    )
    db.execute(
        "INSERT INTO concept_edges (from_concept_id, to_concept_id, relation, strength, "
        "confidence, history, first_seen, last_strengthened) "
        "VALUES (1, 2, 'related-to', 1, 'tentative', '[]', ?, ?)", (now, now)
    )
    db.commit()

    db.execute("DELETE FROM concepts WHERE name = 'alpha'")
    db.commit()

    edges = db.execute("SELECT * FROM concept_edges").fetchall()
    sources = db.execute("SELECT * FROM concept_sources WHERE concept_id = 1").fetchall()
    assert len(edges) == 0
    assert len(sources) == 0


def test_find_db_path_with_root(tmp_path):
    """--root flag finds concepts.db directly without cwd walk."""
    (tmp_path / '.memory-config').write_text('workspace: test\n')
    result = find_db_path(root=tmp_path)
    assert result == tmp_path / 'concepts.db'


def test_find_db_path_root_missing_config(tmp_path):
    """--root flag errors clearly when .memory-config is missing."""
    with pytest.raises(FileNotFoundError, match=str(tmp_path)):
        find_db_path(root=tmp_path)


def test_find_db_path_root_overrides_start(tmp_path):
    """root takes precedence over start parameter."""
    root_dir = tmp_path / 'workspace'
    root_dir.mkdir()
    (root_dir / '.memory-config').write_text('workspace: test\n')
    result = find_db_path(start=tmp_path, root=root_dir)
    assert result == root_dir / 'concepts.db'


def test_find_db_path_walk_still_works(tmp_path):
    """Existing cwd walk behavior is preserved when root is not given."""
    (tmp_path / '.memory-config').write_text('workspace: test\n')
    subdir = tmp_path / 'a' / 'b' / 'c'
    subdir.mkdir(parents=True)
    result = find_db_path(start=subdir)
    assert result == tmp_path / 'concepts.db'
