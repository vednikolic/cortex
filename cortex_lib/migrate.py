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


def run_migrations(conn: sqlite3.Connection) -> None:
    """Run all pending migrations in order."""
    version = get_schema_version(conn)
    if version == "1":
        migrate_v1_to_v2(conn)
        version = "2"
    # Future migrations chain here: if version == "2": migrate_v2_to_v3(conn)
