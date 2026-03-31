"""Schema migration tests: v1->v2, idempotency, data preservation."""

import sqlite3
import pytest
from cortex_lib.db import init_db, connect, SCHEMA_VERSION
from cortex_lib.migrate import migrate_v1_to_v2, get_schema_version, run_migrations


def test_fresh_init_creates_v2_schema(tmp_path):
    """New databases start at version 2."""
    db_path = tmp_path / "fresh.db"
    conn = init_db(db_path)
    version = get_schema_version(conn)
    assert version == "2"
    tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()}
    assert 'weekly_summaries' in tables
    conn.close()


def test_migrate_v1_to_v2_adds_table(tmp_path):
    """Migrating a v1 database adds weekly_summaries."""
    db_path = tmp_path / "v1.db"
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    # Create v1 schema (no weekly_summaries, version=1)
    conn.executescript("""
        CREATE TABLE concepts (id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE,
            aliases TEXT NOT NULL DEFAULT '[]', kind TEXT NOT NULL DEFAULT 'topic',
            confidence TEXT NOT NULL DEFAULT 'tentative',
            privacy_level TEXT NOT NULL DEFAULT 'private',
            first_seen TEXT NOT NULL, last_referenced TEXT NOT NULL,
            source_count INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
        CREATE TABLE concept_sources (id INTEGER PRIMARY KEY,
            concept_id INTEGER NOT NULL, session_hash TEXT NOT NULL,
            project TEXT NOT NULL DEFAULT '', timestamp TEXT NOT NULL,
            weight INTEGER NOT NULL DEFAULT 1);
        CREATE TABLE concept_edges (id INTEGER PRIMARY KEY,
            from_concept_id INTEGER NOT NULL, to_concept_id INTEGER NOT NULL,
            relation TEXT NOT NULL, strength INTEGER NOT NULL DEFAULT 1,
            confidence TEXT NOT NULL DEFAULT 'tentative',
            history TEXT NOT NULL DEFAULT '[]',
            first_seen TEXT NOT NULL, last_strengthened TEXT NOT NULL,
            dismissed INTEGER NOT NULL DEFAULT 0,
            dismissed_original_strength INTEGER);
        CREATE TABLE normalization_rules (id INTEGER PRIMARY KEY,
            variant TEXT NOT NULL UNIQUE, canonical_id INTEGER NOT NULL,
            confidence REAL NOT NULL DEFAULT 1.0, source TEXT NOT NULL DEFAULT 'cli',
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
        CREATE TABLE extraction_log (id INTEGER PRIMARY KEY,
            session_hash TEXT NOT NULL, timestamp TEXT NOT NULL,
            concepts_proposed TEXT NOT NULL DEFAULT '[]',
            created_concepts TEXT NOT NULL DEFAULT '[]',
            created_edges TEXT NOT NULL DEFAULT '[]',
            rejected INTEGER NOT NULL DEFAULT 0,
            weight INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL);
        CREATE TABLE schema_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        INSERT INTO schema_meta (key, value) VALUES ('version', '1');
    """)
    conn.execute("PRAGMA foreign_keys = ON")
    # Insert test data to verify preservation
    conn.execute(
        "INSERT INTO concepts (name, first_seen, last_referenced, created_at, updated_at) "
        "VALUES ('python', '2026-01-01', '2026-03-01', '2026-01-01', '2026-03-01')"
    )
    conn.commit()

    migrate_v1_to_v2(conn)

    tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()}
    assert 'weekly_summaries' in tables
    assert get_schema_version(conn) == "2"
    # Data preserved
    assert conn.execute("SELECT COUNT(*) FROM concepts").fetchone()[0] == 1
    conn.close()


def test_migration_is_idempotent(tmp_path):
    """Running migration twice does not error or duplicate."""
    db_path = tmp_path / "idem.db"
    conn = init_db(db_path)
    version_before = get_schema_version(conn)
    run_migrations(conn)  # already at v2, should be a no-op
    version_after = get_schema_version(conn)
    assert version_before == version_after == "2"
    conn.close()


def test_run_migrations_upgrades_from_v1(tmp_path):
    """run_migrations detects v1 and applies v1->v2."""
    db_path = tmp_path / "auto.db"
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE schema_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        INSERT INTO schema_meta (key, value) VALUES ('version', '1');
        CREATE TABLE concepts (id INTEGER PRIMARY KEY, name TEXT);
    """)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.commit()

    run_migrations(conn)
    assert get_schema_version(conn) == "2"
    conn.close()
