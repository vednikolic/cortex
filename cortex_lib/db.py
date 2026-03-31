"""Schema definition and database management for cortex concepts graph."""

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .migrate import run_migrations, get_schema_version

SCHEMA_VERSION = "2"

SCHEMA_SQL = """
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

CREATE INDEX IF NOT EXISTS idx_concepts_name ON concepts(name);
CREATE INDEX IF NOT EXISTS idx_concepts_confidence ON concepts(confidence);
CREATE INDEX IF NOT EXISTS idx_concept_sources_concept_id ON concept_sources(concept_id);
CREATE INDEX IF NOT EXISTS idx_concept_sources_project ON concept_sources(project);
CREATE INDEX IF NOT EXISTS idx_concept_edges_from ON concept_edges(from_concept_id);
CREATE INDEX IF NOT EXISTS idx_concept_edges_to ON concept_edges(to_concept_id);
CREATE INDEX IF NOT EXISTS idx_normalization_rules_variant ON normalization_rules(variant);
CREATE INDEX IF NOT EXISTS idx_extraction_log_session ON extraction_log(session_hash);

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
CREATE INDEX IF NOT EXISTS idx_weekly_summaries_week ON weekly_summaries(week_start);
"""

VALID_RELATIONS = frozenset({
    'related-to', 'depends-on', 'conflicts-with', 'enables',
    'is-instance-of', 'supersedes', 'blocked-by', 'derived-from',
})

VALID_CONFIDENCE = frozenset({'tentative', 'established', 'settled'})
VALID_PRIVACY = frozenset({'private', 'work', 'shared'})
VALID_KINDS = frozenset({'topic', 'tool', 'pattern', 'decision', 'person', 'project'})


def utc_now() -> str:
    """Return current UTC time as ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()


def find_db_path(start: Optional[Path] = None) -> Path:
    """Walk up from start (default: cwd) looking for .memory-config. Return concepts.db path."""
    current = (start or Path.cwd()).resolve()
    while True:
        if (current / '.memory-config').exists():
            return current / 'concepts.db'
        parent = current.parent
        if parent == current:
            raise FileNotFoundError(
                "No .memory-config found. Run 'concepts init' in your workspace root "
                "or create a .memory-config file."
            )
        current = parent


def connect(db_path: Optional[Path] = None, wal: bool = True) -> sqlite3.Connection:
    """Connect to SQLite DB with WAL mode and foreign keys enabled."""
    if db_path is None:
        db_path = find_db_path()
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    if wal:
        conn.execute("PRAGMA journal_mode = WAL")
    if get_schema_version(conn) != SCHEMA_VERSION:
        run_migrations(conn)
    return conn


def init_db(db_path: Path) -> sqlite3.Connection:
    """Create schema and return connection."""
    conn = connect(db_path)
    conn.executescript(SCHEMA_SQL)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def verify_db(conn: sqlite3.Connection) -> list[str]:
    """Check database integrity. Returns list of issues (empty = healthy)."""
    issues = []

    result = conn.execute("PRAGMA integrity_check").fetchone()
    if result[0] != 'ok':
        issues.append(f"Integrity check failed: {result[0]}")

    fk_violations = conn.execute("PRAGMA foreign_key_check").fetchall()
    if fk_violations:
        issues.append(f"Foreign key violations: {len(fk_violations)}")

    tables = {row[0] for row in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()}
    expected = {'concepts', 'concept_sources', 'concept_edges',
                'normalization_rules', 'extraction_log', 'schema_meta',
                'weekly_summaries'}
    missing = expected - tables
    if missing:
        issues.append(f"Missing tables: {', '.join(sorted(missing))}")

    journal = conn.execute("PRAGMA journal_mode").fetchone()[0]
    if journal != 'wal':
        issues.append(f"Journal mode is '{journal}', expected 'wal'")

    version = conn.execute(
        "SELECT value FROM schema_meta WHERE key = 'version'"
    ).fetchone()
    if version is None:
        issues.append("Missing schema version in schema_meta")
    elif version[0] != SCHEMA_VERSION:
        issues.append(f"Schema version mismatch: DB has '{version[0]}', expected '{SCHEMA_VERSION}'")

    return issues
