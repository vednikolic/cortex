"""Session capture for automatic session tracking.

Records git state (files, commits, duration) at session end without LLM calls.
Matches file/commit tokens against existing concepts via Tier 1 canonicalization.
"""

import hashlib
import json
import os
import re
import sqlite3
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

from .canon import canonicalize_cli
from .db import utc_now
from .ops import upsert_concept

# Default tokens filtered before canonicalization
DEFAULT_STOPLIST = [
    # Common path components
    'lib', 'src', 'test', 'tests', 'utils', 'docs', 'config', 'scripts',
    '__init__', '__pycache__', 'node_modules', 'dist', 'build',
    # File extensions
    'py', 'md', 'json', 'sh', 'sql', 'html', 'js', 'css', 'ts', 'tsx',
    # Git conventional commit prefixes
    'fix', 'feat', 'docs', 'refactor', 'chore', 'merge', 'rebase',
]

MIN_TOKEN_LENGTH = 3

STOPLIST_PATH = Path.home() / '.cortex' / 'capture-stoplist.txt'
SESSIONS_DIR = Path.home() / '.cortex' / 'sessions'
ENRICH_QUEUE_DIR = Path.home() / '.cortex' / 'enrich-queue'
CURRENT_HASH_PATH = Path.home() / '.cortex' / 'current-session-hash'
SESSION_START_PATH = Path.home() / '.cortex' / 'session-start'


def load_stoplist(path: Optional[Path] = None) -> set[str]:
    """Load token stoplist from file, falling back to bundled defaults."""
    if path is None:
        path = STOPLIST_PATH
    tokens = set(DEFAULT_STOPLIST)
    if path.exists():
        for line in path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith('#'):
                tokens.add(line.lower())
    return tokens


def tokenize_paths(file_paths: list[str]) -> list[str]:
    """Extract tokens from file paths (split on / and .)."""
    tokens = []
    for fp in file_paths:
        # Strip leading status chars like "M ", "A "
        clean = re.sub(r'^[A-Z]\s+', '', fp.strip())
        parts = re.split(r'[/\\.]', clean)
        tokens.extend(p.lower() for p in parts if p)
    return tokens


def tokenize_commits(commits: list[str]) -> list[str]:
    """Extract tokens from commit messages."""
    tokens = []
    for commit in commits:
        # Strip leading hash if present (e.g., "a1b2c3d feat: add capture")
        msg = re.sub(r'^[0-9a-f]{7,}\s*', '', commit.strip())
        # Remove conventional commit prefix colon
        msg = re.sub(r'^[a-z]+:\s*', '', msg)
        words = re.split(r'[\s\-_/.:,;()\[\]]+', msg)
        tokens.extend(w.lower() for w in words if w)
    return tokens


def filter_tokens(tokens: list[str], stoplist: set[str]) -> list[str]:
    """Filter tokens through stoplist and minimum length."""
    seen = set()
    result = []
    for t in tokens:
        t_lower = t.lower().strip()
        if t_lower in stoplist:
            continue
        if len(t_lower) < MIN_TOKEN_LENGTH:
            continue
        if t_lower not in seen:
            seen.add(t_lower)
            result.append(t_lower)
    return result


def compute_session_hash(timestamp: str, project: str,
                         files: list[str], head_ref: str) -> str:
    """Compute deterministic session hash. SHA1(timestamp + project + sorted files + HEAD)."""
    payload = f"{timestamp}|{project}|{'|'.join(sorted(files))}|{head_ref}"
    return hashlib.sha1(payload.encode()).hexdigest()[:12]


def read_session_start(path: Optional[Path] = None) -> Optional[dict]:
    """Read the session-start context snapshot file."""
    if path is None:
        path = SESSION_START_PATH
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return None


def capture_session(
    conn: sqlite3.Connection,
    files: list[str],
    commits: list[str],
    project: str,
    branch: str = '',
    duration_seconds: Optional[int] = None,
    session_start_path: Optional[Path] = None,
    sessions_dir: Optional[Path] = None,
    enrich_queue_dir: Optional[Path] = None,
    current_hash_path: Optional[Path] = None,
    stoplist_path: Optional[Path] = None,
) -> dict:
    """Capture a session record from git state.

    Returns dict with session_hash, status, matched_concepts, and action
    ('created', 'skipped' for idempotent duplicate, or 'incomplete').
    """
    if sessions_dir is None:
        sessions_dir = SESSIONS_DIR
    if enrich_queue_dir is None:
        enrich_queue_dir = ENRICH_QUEUE_DIR
    if current_hash_path is None:
        current_hash_path = CURRENT_HASH_PATH

    now = utc_now()

    # Read session-start context
    start_data = read_session_start(session_start_path)
    head_ref = start_data.get('head_ref', '') if start_data else ''
    incomplete = start_data is None

    # For incomplete sessions (no session-start file), create minimal record
    if incomplete:
        files = []
        commits = []
        head_ref = ''

    # Compute session hash
    session_hash = compute_session_hash(now, project, files, head_ref)

    # Idempotency check
    existing = conn.execute(
        "SELECT session_hash FROM sessions WHERE session_hash = ?",
        (session_hash,)
    ).fetchone()
    if existing:
        return {
            'session_hash': session_hash,
            'status': 'skipped',
            'matched_concepts': [],
            'action': 'skipped',
        }

    # Match concepts via Tier 1 canonicalization
    stoplist = load_stoplist(stoplist_path)
    path_tokens = tokenize_paths(files)
    commit_tokens = tokenize_commits(commits)
    all_tokens = filter_tokens(path_tokens + commit_tokens, stoplist)

    matched_concepts = []
    for token in all_tokens:
        match = canonicalize_cli(token, conn)
        if match:
            upsert_concept(
                conn, match['canonical_name'],
                project=project,
                session_hash=session_hash,
            )
            if match['canonical_name'] not in matched_concepts:
                matched_concepts.append(match['canonical_name'])

    # Read context snapshot fields
    memory_snapshot_hash = start_data.get('memory_snapshot_hash') if start_data else None
    concepts_loaded = json.dumps(start_data.get('concepts_loaded', [])) if start_data else None
    memory_entries_loaded = json.dumps(start_data.get('memory_entries_loaded', [])) if start_data else None

    # Determine status: incomplete sessions are immediately enriched
    status = 'enriched' if incomplete else 'raw'
    enriched_at = now if incomplete else None

    # Insert session record
    conn.execute(
        "INSERT INTO sessions (session_hash, timestamp, project, branch, "
        "duration_seconds, files, commits, matched_concepts, "
        "memory_snapshot_hash, concepts_loaded, memory_entries_loaded, "
        "status, enriched_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (session_hash, now, project, branch,
         duration_seconds,
         json.dumps(files),
         json.dumps(commits),
         json.dumps(matched_concepts),
         memory_snapshot_hash,
         concepts_loaded,
         memory_entries_loaded,
         status,
         enriched_at)
    )
    conn.commit()

    # Write current session hash
    current_hash_path.parent.mkdir(parents=True, exist_ok=True)
    current_hash_path.write_text(session_hash)

    # Write session detail file
    sessions_dir.mkdir(parents=True, exist_ok=True)
    detail = _format_session_detail(
        session_hash, project, now, duration_seconds, branch,
        status, files, commits, matched_concepts,
        memory_snapshot_hash, concepts_loaded, memory_entries_loaded,
        start_data,
    )
    (sessions_dir / f"{session_hash}.md").write_text(detail)

    # Write enrich-queue entry (only for non-incomplete sessions)
    if not incomplete:
        enrich_queue_dir.mkdir(parents=True, exist_ok=True)
        queue_entry = {
            'session_hash': session_hash,
            'timestamp': now,
            'project': project,
            'detail_path': str(sessions_dir / f"{session_hash}.md"),
        }
        (enrich_queue_dir / f"{session_hash}.json").write_text(
            json.dumps(queue_entry, indent=2)
        )

    return {
        'session_hash': session_hash,
        'status': status,
        'matched_concepts': matched_concepts,
        'action': 'incomplete' if incomplete else 'created',
    }


def _format_session_detail(
    session_hash: str, project: str, timestamp: str,
    duration_seconds: Optional[int], branch: str, status: str,
    files: list[str], commits: list[str],
    matched_concepts: list[str],
    memory_snapshot_hash: Optional[str],
    concepts_loaded: Optional[str],
    memory_entries_loaded: Optional[str],
    start_data: Optional[dict],
) -> str:
    """Format session detail as markdown."""
    duration_str = f"{duration_seconds // 60}min" if duration_seconds else "unknown"
    lines = [
        f"## Session {session_hash[:8]} | {project} | {timestamp}",
        f"Duration: {duration_str} | Branch: {branch} | Status: {status}",
        "",
        f"### Files ({len(files)})",
    ]
    for f in files:
        lines.append(f)
    lines.append("")
    lines.append(f"### Commits ({len(commits)})")
    for c in commits:
        lines.append(c)
    lines.append("")
    lines.append(f"### Matched Concepts ({len(matched_concepts)})")
    lines.append(', '.join(matched_concepts) if matched_concepts else 'none')
    lines.append("")
    lines.append("### Context Loaded")
    lines.append(f"Memory hash: {memory_snapshot_hash or 'unavailable'}")

    if start_data and start_data.get('concepts_loaded'):
        concept_names = start_data['concepts_loaded']
        lines.append(f"Concepts in brief: [{', '.join(concept_names)}]")
    else:
        lines.append("Concepts in brief: []")

    if start_data and start_data.get('memory_entries_loaded'):
        entries = start_data['memory_entries_loaded']
        lines.append(f"Memory entries: [{', '.join(entries[:5])}{'...' if len(entries) > 5 else ''}]")
    else:
        lines.append("Memory entries: []")

    return '\n'.join(lines) + '\n'


def query_sessions(
    conn: sqlite3.Connection,
    status: Optional[str] = None,
    project: Optional[str] = None,
    since: Optional[str] = None,
    limit: int = 50,
) -> list[dict]:
    """Query session records with optional filters."""
    clauses = []
    params: list = []

    if status:
        clauses.append("status = ?")
        params.append(status)
    if project:
        clauses.append("project = ?")
        params.append(project)
    if since:
        clauses.append("timestamp >= ?")
        params.append(since)

    where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    query = f"SELECT * FROM sessions{where} ORDER BY timestamp DESC LIMIT ?"
    params.append(limit)

    rows = conn.execute(query, params).fetchall()
    return [dict(r) for r in rows]


def format_session_oneline(session: dict) -> str:
    """Format a session as a one-line brief-compatible string."""
    project = session.get('project', '')
    duration = session.get('duration_seconds')
    dur_str = f"{duration // 60}min" if duration else ""
    commits = json.loads(session.get('commits', '[]'))
    files = json.loads(session.get('files', '[]'))

    parts = [project]
    if dur_str:
        parts.append(dur_str)
    if commits:
        parts.append(f"{len(commits)} commit{'s' if len(commits) != 1 else ''}")
    if files:
        # Most changed file: pick the first one, strip status prefix
        first_file = re.sub(r'^[A-Z]\s+', '', files[0]) if files else ''
        if first_file:
            parts.append(os.path.basename(first_file))

    return ' | '.join(p for p in parts if p) if parts else session.get('session_hash', '')[:8]


def update_session_status(conn: sqlite3.Connection, session_hash: str,
                          new_status: str) -> dict:
    """Update a session's status. Returns the updated session or raises ValueError."""
    valid = {'raw', 'enriched', 'saved'}
    if new_status not in valid:
        raise ValueError(f"Invalid status '{new_status}'. Must be one of: {', '.join(sorted(valid))}")

    row = conn.execute(
        "SELECT * FROM sessions WHERE session_hash = ?", (session_hash,)
    ).fetchone()
    if not row:
        raise ValueError(f"Session not found: '{session_hash}'")

    now = utc_now()
    enriched_at = now if new_status == 'enriched' else dict(row).get('enriched_at')

    conn.execute(
        "UPDATE sessions SET status = ?, enriched_at = ? WHERE session_hash = ?",
        (new_status, enriched_at, session_hash)
    )
    conn.commit()
    return {'session_hash': session_hash, 'old_status': row['status'], 'new_status': new_status}


def record_re_explanation(
    conn: sqlite3.Connection,
    concept_name: str,
    session_hash: str,
    detection_method: str,
    prior_count: int,
    prior_confidence: str,
    was_in_brief: bool = False,
    failure_type: str = 'capture_miss',
) -> dict:
    """Record a re-explanation event. Validates concept and session exist."""
    if detection_method not in ('save', 'reflect'):
        raise ValueError(f"Invalid detection_method '{detection_method}'")
    if failure_type not in ('surfacing_miss', 'capture_miss'):
        raise ValueError(f"Invalid failure_type '{failure_type}'")

    concept = conn.execute(
        "SELECT id, name FROM concepts WHERE LOWER(name) = LOWER(?)",
        (concept_name,)
    ).fetchone()
    if not concept:
        raise ValueError(f"Concept not found: '{concept_name}'")

    session = conn.execute(
        "SELECT session_hash FROM sessions WHERE session_hash = ?",
        (session_hash,)
    ).fetchone()
    if not session:
        raise ValueError(f"Session not found: '{session_hash}'")

    now = utc_now()
    cursor = conn.execute(
        "INSERT INTO re_explanations (concept_id, session_hash, timestamp, "
        "prior_source_count, prior_confidence, was_in_brief, failure_type, "
        "detection_method) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (concept['id'], session_hash, now, prior_count, prior_confidence,
         1 if was_in_brief else 0, failure_type, detection_method)
    )
    conn.commit()
    return {
        'id': cursor.lastrowid,
        'concept': concept['name'],
        'session_hash': session_hash,
        'failure_type': failure_type,
    }


def capture_prune(
    conn: sqlite3.Connection,
    days: int = 3,
    sessions_dir: Optional[Path] = None,
    enrich_queue_dir: Optional[Path] = None,
) -> dict:
    """Remove session detail files older than N days.

    Also removes orphaned enrich-queue files and marks pruned raw sessions
    as enriched with zero concepts.
    """
    if sessions_dir is None:
        sessions_dir = SESSIONS_DIR
    if enrich_queue_dir is None:
        enrich_queue_dir = ENRICH_QUEUE_DIR

    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    pruned_details = 0
    pruned_queue = 0

    # Find sessions older than cutoff
    rows = conn.execute(
        "SELECT session_hash, status FROM sessions WHERE timestamp < ?",
        (cutoff,)
    ).fetchall()

    now = utc_now()
    for row in rows:
        sh = row['session_hash']

        # Remove detail file
        detail_path = sessions_dir / f"{sh}.md"
        if detail_path.exists():
            detail_path.unlink()
            pruned_details += 1

        # Remove enrich-queue file
        queue_path = enrich_queue_dir / f"{sh}.json"
        if queue_path.exists():
            queue_path.unlink()
            pruned_queue += 1

        # Mark raw sessions as enriched
        if row['status'] == 'raw':
            conn.execute(
                "UPDATE sessions SET status = 'enriched', enriched_at = ? "
                "WHERE session_hash = ?",
                (now, sh)
            )

    conn.commit()
    return {
        'pruned_details': pruned_details,
        'pruned_queue': pruned_queue,
        'sessions_affected': len(rows),
    }


def capture_health(
    conn: sqlite3.Connection,
    sessions_dir: Optional[Path] = None,
    enrich_queue_dir: Optional[Path] = None,
) -> dict:
    """Report session tracking health status."""
    if sessions_dir is None:
        sessions_dir = SESSIONS_DIR
    if enrich_queue_dir is None:
        enrich_queue_dir = ENRICH_QUEUE_DIR

    cutoff_7d = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()

    # Last successful capture
    last = conn.execute(
        "SELECT timestamp FROM sessions ORDER BY timestamp DESC LIMIT 1"
    ).fetchone()
    last_capture = last['timestamp'] if last else None

    # Sessions by status in last 7 days
    status_counts = {}
    rows = conn.execute(
        "SELECT status, COUNT(*) as cnt FROM sessions "
        "WHERE timestamp >= ? GROUP BY status",
        (cutoff_7d,)
    ).fetchall()
    for r in rows:
        status_counts[r['status']] = r['cnt']

    # Missing detail files
    missing_details = []
    raw_sessions = conn.execute(
        "SELECT session_hash FROM sessions WHERE status = 'raw'"
    ).fetchall()
    for r in raw_sessions:
        if not (sessions_dir / f"{r['session_hash']}.md").exists():
            missing_details.append(r['session_hash'])

    # Orphaned enrich-queue entries
    orphaned_queue = []
    if enrich_queue_dir.exists():
        for qf in enrich_queue_dir.glob('*.json'):
            sh = qf.stem
            row = conn.execute(
                "SELECT session_hash FROM sessions WHERE session_hash = ?",
                (sh,)
            ).fetchone()
            if not row:
                orphaned_queue.append(sh)

    return {
        'last_capture': last_capture,
        'sessions_7d': status_counts,
        'missing_details': missing_details,
        'orphaned_queue': orphaned_queue,
        'healthy': len(missing_details) == 0 and len(orphaned_queue) == 0,
    }


def re_explanation_stats(
    conn: sqlite3.Connection,
    days: int = 30,
) -> dict:
    """Compute re-explanation statistics decomposed by failure type."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

    rows = conn.execute(
        "SELECT failure_type, COUNT(*) as cnt FROM re_explanations "
        "WHERE timestamp >= ? GROUP BY failure_type",
        (cutoff,)
    ).fetchall()
    by_type = {r['failure_type']: r['cnt'] for r in rows}

    # Most re-explained concepts
    top = conn.execute(
        "SELECT c.name, COUNT(*) as cnt, r.failure_type "
        "FROM re_explanations r JOIN concepts c ON r.concept_id = c.id "
        "WHERE r.timestamp >= ? "
        "GROUP BY c.name, r.failure_type ORDER BY cnt DESC LIMIT 10",
        (cutoff,)
    ).fetchall()

    # Total
    total = sum(by_type.values())

    return {
        'total': total,
        'surfacing_miss': by_type.get('surfacing_miss', 0),
        'capture_miss': by_type.get('capture_miss', 0),
        'top_concepts': [dict(r) for r in top],
        'days': days,
    }
