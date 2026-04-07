"""Schema migration for cortex concepts graph.

Migrations are versioned and idempotent. Each migration function
checks preconditions before applying changes.

Note: do not import from .db to avoid circular imports (db.py imports from this module).
"""

import sqlite3


WEEKLY_SUMMARIES_SQL = """
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
CREATE INDEX IF NOT EXISTS idx_weekly_summaries_week ON weekly_summaries(week_start);
"""


def get_schema_version(conn: sqlite3.Connection) -> str:
    """Read current schema version from schema_meta."""
    try:
        row = conn.execute(
            "SELECT value FROM schema_meta WHERE key = 'version'"
        ).fetchone()
        return row[0] if row else "0"
    except sqlite3.OperationalError:
        return "0"


def migrate_v1_to_v2(conn: sqlite3.Connection) -> None:
    """Add weekly_summaries table. Bump version to 2."""
    conn.executescript(WEEKLY_SUMMARIES_SQL)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute(
        "UPDATE schema_meta SET value = '2' WHERE key = 'version'"
    )
    conn.commit()


SESSIONS_SQL = """
CREATE TABLE IF NOT EXISTS sessions (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    session_hash          TEXT UNIQUE NOT NULL,
    timestamp             TEXT NOT NULL,
    project               TEXT NOT NULL DEFAULT '',
    branch                TEXT DEFAULT '',
    duration_seconds      INTEGER,
    files                 TEXT DEFAULT '[]',
    commits               TEXT DEFAULT '[]',
    matched_concepts      TEXT DEFAULT '[]',
    memory_snapshot_hash  TEXT,
    concepts_loaded       TEXT,
    memory_entries_loaded TEXT,
    status                TEXT NOT NULL DEFAULT 'raw'
                          CHECK(status IN ('raw', 'enriched', 'saved')),
    enriched_at           TEXT
);
CREATE INDEX IF NOT EXISTS idx_sessions_status ON sessions(status);
CREATE INDEX IF NOT EXISTS idx_sessions_project ON sessions(project);
CREATE INDEX IF NOT EXISTS idx_sessions_timestamp ON sessions(timestamp);

CREATE TABLE IF NOT EXISTS re_explanations (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    concept_id         INTEGER NOT NULL REFERENCES concepts(id),
    session_hash       TEXT NOT NULL REFERENCES sessions(session_hash),
    timestamp          TEXT NOT NULL,
    prior_source_count INTEGER NOT NULL,
    prior_confidence   TEXT NOT NULL,
    was_in_brief       INTEGER NOT NULL DEFAULT 0,
    failure_type       TEXT NOT NULL DEFAULT 'capture_miss'
                       CHECK(failure_type IN ('surfacing_miss', 'capture_miss')),
    detection_method   TEXT NOT NULL CHECK(detection_method IN ('save', 'reflect'))
);
CREATE INDEX IF NOT EXISTS idx_reexpl_concept ON re_explanations(concept_id);
CREATE INDEX IF NOT EXISTS idx_reexpl_timestamp ON re_explanations(timestamp);
"""


def migrate_v2_to_v3(conn: sqlite3.Connection) -> None:
    """Add sessions and re_explanations tables. Bump version to 3."""
    conn.executescript(SESSIONS_SQL)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute(
        "UPDATE schema_meta SET value = '3' WHERE key = 'version'"
    )
    conn.commit()


def run_migrations(conn: sqlite3.Connection) -> None:
    """Run all pending migrations in order."""
    version = get_schema_version(conn)
    if version == "1":
        migrate_v1_to_v2(conn)
        version = "2"
    if version == "2":
        migrate_v2_to_v3(conn)
        version = "3"
