"""Tests for v2 to v3 schema migration (sessions + re_explanations tables)."""

import sqlite3
import pytest
from pathlib import Path

from cortex_lib.db import SCHEMA_SQL, SCHEMA_VERSION, init_db, verify_db, connect
from cortex_lib.migrate import get_schema_version, migrate_v2_to_v3


def _create_v2_db(db_path: Path) -> sqlite3.Connection:
    """Create a v2 schema database (no sessions/re_explanations tables)."""
    # Use the v2 schema SQL (strip sessions and re_explanations sections)
    v2_sql = """
    CREATE TABLE IF NOT EXISTS concepts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        aliases TEXT NOT NULL DEFAULT '[]',
        kind TEXT NOT NULL DEFAULT 'topic',
        confidence TEXT NOT NULL DEFAULT 'tentative',
        privacy_level TEXT NOT NULL DEFAULT 'private',
        first_seen TEXT NOT NULL,
        last_referenced TEXT NOT NULL,
        source_count INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS concept_sources (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        concept_id INTEGER NOT NULL REFERENCES concepts(id) ON DELETE CASCADE,
        session_hash TEXT NOT NULL,
        project TEXT NOT NULL DEFAULT '',
        timestamp TEXT NOT NULL,
        weight INTEGER NOT NULL DEFAULT 1
    );
    CREATE TABLE IF NOT EXISTS concept_edges (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        from_concept_id INTEGER NOT NULL REFERENCES concepts(id) ON DELETE CASCADE,
        to_concept_id INTEGER NOT NULL REFERENCES concepts(id) ON DELETE CASCADE,
        relation TEXT NOT NULL,
        strength INTEGER NOT NULL DEFAULT 1,
        confidence TEXT NOT NULL DEFAULT 'tentative',
        history TEXT NOT NULL DEFAULT '[]',
        first_seen TEXT NOT NULL,
        last_strengthened TEXT NOT NULL,
        dismissed INTEGER NOT NULL DEFAULT 0,
        dismissed_original_strength INTEGER,
        UNIQUE(from_concept_id, to_concept_id, relation)
    );
    CREATE TABLE IF NOT EXISTS normalization_rules (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        variant TEXT NOT NULL UNIQUE,
        canonical_id INTEGER NOT NULL REFERENCES concepts(id) ON DELETE CASCADE,
        confidence REAL NOT NULL DEFAULT 1.0,
        source TEXT NOT NULL DEFAULT 'cli',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS extraction_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_hash TEXT NOT NULL,
        timestamp TEXT NOT NULL,
        concepts_proposed TEXT NOT NULL DEFAULT '[]',
        created_concepts TEXT NOT NULL DEFAULT '[]',
        created_edges TEXT NOT NULL DEFAULT '[]',
        rejected INTEGER NOT NULL DEFAULT 0,
        weight INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS schema_meta (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    );
    INSERT OR IGNORE INTO schema_meta (key, value) VALUES ('version', '2');
    CREATE TABLE IF NOT EXISTS weekly_summaries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        week_start TEXT NOT NULL,
        summary TEXT NOT NULL,
        signals TEXT NOT NULL DEFAULT '[]',
        concepts_promoted TEXT NOT NULL DEFAULT '[]',
        concepts_dismissed TEXT NOT NULL DEFAULT '[]',
        concepts_deferred TEXT NOT NULL DEFAULT '[]',
        concept_count INTEGER NOT NULL DEFAULT 0,
        edge_count INTEGER NOT NULL DEFAULT 0,
        project_count INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL
    );
    """
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.executescript(v2_sql)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def test_v2_db_has_version_2(tmp_path):
    """v2 database reports schema version 2."""
    conn = _create_v2_db(tmp_path / "test.db")
    assert get_schema_version(conn) == "2"
    conn.close()


def test_migrate_v2_to_v3_creates_sessions_table(tmp_path):
    """Migration adds sessions table with expected columns."""
    conn = _create_v2_db(tmp_path / "test.db")
    migrate_v2_to_v3(conn)

    tables = {row[0] for row in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()}
    assert 'sessions' in tables

    # Check columns
    cols = {row[1] for row in conn.execute("PRAGMA table_info(sessions)").fetchall()}
    assert 'session_hash' in cols
    assert 'status' in cols
    assert 'matched_concepts' in cols
    assert 'memory_snapshot_hash' in cols
    assert 'concepts_loaded' in cols
    assert 'memory_entries_loaded' in cols
    conn.close()


def test_migrate_v2_to_v3_creates_re_explanations_table(tmp_path):
    """Migration adds re_explanations table with expected columns."""
    conn = _create_v2_db(tmp_path / "test.db")
    migrate_v2_to_v3(conn)

    tables = {row[0] for row in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()}
    assert 're_explanations' in tables

    cols = {row[1] for row in conn.execute("PRAGMA table_info(re_explanations)").fetchall()}
    assert 'concept_id' in cols
    assert 'session_hash' in cols
    assert 'failure_type' in cols
    assert 'detection_method' in cols
    assert 'was_in_brief' in cols
    conn.close()


def test_migrate_v2_to_v3_bumps_version(tmp_path):
    """Migration updates schema version to 3."""
    conn = _create_v2_db(tmp_path / "test.db")
    assert get_schema_version(conn) == "2"
    migrate_v2_to_v3(conn)
    assert get_schema_version(conn) == "3"
    conn.close()


def test_migrate_v2_to_v3_preserves_existing_data(tmp_path):
    """Migration does not disturb existing concept data."""
    conn = _create_v2_db(tmp_path / "test.db")
    now = "2026-04-07T00:00:00+00:00"
    conn.execute(
        "INSERT INTO concepts (name, kind, first_seen, last_referenced, "
        "source_count, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("api-design", "pattern", now, now, 3, now, now)
    )
    conn.commit()

    migrate_v2_to_v3(conn)

    row = conn.execute("SELECT name, source_count FROM concepts WHERE name = ?",
                       ("api-design",)).fetchone()
    assert row is not None
    assert row[0] == "api-design"
    assert row[1] == 3
    conn.close()


def test_migrate_v2_to_v3_foreign_keys_restored(tmp_path):
    """Foreign keys are re-enabled after executescript in migration."""
    conn = _create_v2_db(tmp_path / "test.db")
    migrate_v2_to_v3(conn)

    fk = conn.execute("PRAGMA foreign_keys").fetchone()[0]
    assert fk == 1, "PRAGMA foreign_keys must be ON after migration"
    conn.close()


def test_connect_auto_migrates_v2_to_v3(tmp_path):
    """connect() triggers migration when it sees a v2 database."""
    db_path = tmp_path / "test.db"
    # Create a .memory-config so find_db_path works
    (tmp_path / ".memory-config").write_text("")

    # Create v2 database
    v2_conn = _create_v2_db(db_path)
    v2_conn.close()

    # connect() should auto-migrate
    conn = connect(db_path)
    assert get_schema_version(conn) == "3"

    tables = {row[0] for row in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()}
    assert 'sessions' in tables
    assert 're_explanations' in tables
    conn.close()


def test_fresh_init_creates_v3_schema(tmp_path):
    """init_db creates a fresh v3 database with all tables."""
    db_path = tmp_path / "test.db"
    conn = init_db(db_path)

    assert get_schema_version(conn) == "3"
    issues = verify_db(conn)
    assert issues == [], f"verify_db found issues: {issues}"
    conn.close()


def test_sessions_status_check_constraint(db):
    """sessions.status only accepts raw, enriched, saved."""
    db.execute(
        "INSERT INTO sessions (session_hash, timestamp, status) "
        "VALUES ('abc', '2026-01-01T00:00:00Z', 'raw')"
    )
    db.commit()

    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "INSERT INTO sessions (session_hash, timestamp, status) "
            "VALUES ('def', '2026-01-01T00:00:00Z', 'invalid')"
        )


def test_sessions_hash_unique_constraint(db):
    """sessions.session_hash is unique."""
    db.execute(
        "INSERT INTO sessions (session_hash, timestamp) "
        "VALUES ('abc123', '2026-01-01T00:00:00Z')"
    )
    db.commit()

    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "INSERT INTO sessions (session_hash, timestamp) "
            "VALUES ('abc123', '2026-01-02T00:00:00Z')"
        )


def test_re_explanations_failure_type_check(db):
    """re_explanations.failure_type only accepts surfacing_miss, capture_miss."""
    now = "2026-01-01T00:00:00Z"
    db.execute(
        "INSERT INTO concepts (name, kind, first_seen, last_referenced, "
        "source_count, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("caching", "pattern", now, now, 3, now, now)
    )
    db.execute(
        "INSERT INTO sessions (session_hash, timestamp) VALUES ('sess1', ?)", (now,)
    )
    db.commit()

    # Valid failure_type
    db.execute(
        "INSERT INTO re_explanations (concept_id, session_hash, timestamp, "
        "prior_source_count, prior_confidence, failure_type, detection_method) "
        "VALUES (1, 'sess1', ?, 3, 'established', 'surfacing_miss', 'save')", (now,)
    )
    db.commit()

    # Invalid failure_type
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "INSERT INTO re_explanations (concept_id, session_hash, timestamp, "
            "prior_source_count, prior_confidence, failure_type, detection_method) "
            "VALUES (1, 'sess1', ?, 3, 'established', 'bad_type', 'save')", (now,)
        )


def test_re_explanations_detection_method_check(db):
    """re_explanations.detection_method only accepts save, reflect."""
    now = "2026-01-01T00:00:00Z"
    db.execute(
        "INSERT INTO concepts (name, kind, first_seen, last_referenced, "
        "source_count, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("retry-pattern", "pattern", now, now, 2, now, now)
    )
    db.execute(
        "INSERT INTO sessions (session_hash, timestamp) VALUES ('sess2', ?)", (now,)
    )
    db.commit()

    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "INSERT INTO re_explanations (concept_id, session_hash, timestamp, "
            "prior_source_count, prior_confidence, failure_type, detection_method) "
            "VALUES (1, 'sess2', ?, 2, 'established', 'capture_miss', 'manual')", (now,)
        )
