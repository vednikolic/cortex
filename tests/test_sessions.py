"""Tests for session queries, status updates, and health checks."""

import json
import pytest
from pathlib import Path

from cortex_lib.capture import (
    query_sessions, format_session_oneline, update_session_status,
    capture_health,
)


def _insert_session(db, session_hash, project='project-alpha', status='raw',
                    timestamp='2026-04-07T10:00:00+00:00', files='[]',
                    commits='[]', duration=None):
    """Helper to insert a session record directly."""
    db.execute(
        "INSERT INTO sessions (session_hash, timestamp, project, status, "
        "files, commits, duration_seconds) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (session_hash, timestamp, project, status, files, commits, duration)
    )
    db.commit()


def test_query_sessions_all(db):
    """Query with no filters returns all sessions."""
    _insert_session(db, 'sess1')
    _insert_session(db, 'sess2', project='project-beta')
    results = query_sessions(db)
    assert len(results) == 2


def test_query_sessions_by_status(db):
    """Filter by status returns only matching sessions."""
    _insert_session(db, 'sess1', status='raw')
    _insert_session(db, 'sess2', status='enriched')
    results = query_sessions(db, status='raw')
    assert len(results) == 1
    assert results[0]['session_hash'] == 'sess1'


def test_query_sessions_by_project(db):
    """Filter by project returns only matching sessions."""
    _insert_session(db, 'sess1', project='project-alpha')
    _insert_session(db, 'sess2', project='project-beta')
    results = query_sessions(db, project='project-beta')
    assert len(results) == 1
    assert results[0]['project'] == 'project-beta'


def test_query_sessions_since(db):
    """Since filter excludes older sessions."""
    _insert_session(db, 'old', timestamp='2026-01-01T00:00:00+00:00')
    _insert_session(db, 'new', timestamp='2026-04-07T00:00:00+00:00')
    results = query_sessions(db, since='2026-04-01T00:00:00+00:00')
    assert len(results) == 1
    assert results[0]['session_hash'] == 'new'


def test_query_sessions_limit(db):
    """Limit caps the number of results."""
    for i in range(5):
        _insert_session(db, f'sess{i}', timestamp=f'2026-04-0{i+1}T00:00:00+00:00')
    results = query_sessions(db, limit=3)
    assert len(results) == 3


def test_format_session_oneline(db):
    """One-line format includes project, duration, commits, and file."""
    session = {
        'session_hash': 'abc123def456',
        'project': 'project-alpha',
        'duration_seconds': 1800,
        'commits': json.dumps(['a1b feat: add thing']),
        'files': json.dumps(['M src/lib/ops.py']),
    }
    line = format_session_oneline(session)
    assert 'project-alpha' in line
    assert '30min' in line
    assert '1 commit' in line
    assert 'ops.py' in line


def test_format_session_oneline_no_duration():
    """One-line format handles missing duration gracefully."""
    session = {
        'session_hash': 'abc123',
        'project': 'project-beta',
        'duration_seconds': None,
        'commits': '[]',
        'files': '[]',
    }
    line = format_session_oneline(session)
    assert 'project-beta' in line


def test_update_session_status(db):
    """Status update changes the session status and returns old/new."""
    _insert_session(db, 'sess1', status='raw')
    result = update_session_status(db, 'sess1', 'saved')
    assert result['old_status'] == 'raw'
    assert result['new_status'] == 'saved'

    row = db.execute("SELECT status FROM sessions WHERE session_hash = 'sess1'").fetchone()
    assert row['status'] == 'saved'


def test_update_session_status_enriched_sets_timestamp(db):
    """Updating to enriched sets enriched_at timestamp."""
    _insert_session(db, 'sess1', status='raw')
    update_session_status(db, 'sess1', 'enriched')
    row = db.execute("SELECT enriched_at FROM sessions WHERE session_hash = 'sess1'").fetchone()
    assert row['enriched_at'] is not None


def test_update_session_status_invalid(db):
    """Invalid status raises ValueError."""
    _insert_session(db, 'sess1')
    with pytest.raises(ValueError, match="Invalid status"):
        update_session_status(db, 'sess1', 'invalid')


def test_update_session_status_not_found(db):
    """Nonexistent session raises ValueError."""
    with pytest.raises(ValueError, match="Session not found"):
        update_session_status(db, 'nonexistent', 'saved')


def test_capture_health_healthy(db, tmp_path):
    """Health check reports healthy when no issues exist."""
    sessions_dir = tmp_path / 'sessions'
    sessions_dir.mkdir()
    queue_dir = tmp_path / 'enrich-queue'

    _insert_session(db, 'sess1', status='saved')
    result = capture_health(db, sessions_dir=sessions_dir,
                            enrich_queue_dir=queue_dir)
    assert result['healthy'] is True
    assert result['last_capture'] is not None


def test_capture_health_missing_details(db, tmp_path):
    """Health check detects raw sessions without detail files."""
    sessions_dir = tmp_path / 'sessions'
    sessions_dir.mkdir()
    queue_dir = tmp_path / 'enrich-queue'

    _insert_session(db, 'sess1', status='raw')
    # No detail file for sess1
    result = capture_health(db, sessions_dir=sessions_dir,
                            enrich_queue_dir=queue_dir)
    assert result['healthy'] is False
    assert 'sess1' in result['missing_details']


def test_capture_health_orphaned_queue(db, tmp_path):
    """Health check detects queue files with no matching session."""
    sessions_dir = tmp_path / 'sessions'
    sessions_dir.mkdir()
    queue_dir = tmp_path / 'enrich-queue'
    queue_dir.mkdir()
    (queue_dir / 'orphan123.json').write_text('{}')

    result = capture_health(db, sessions_dir=sessions_dir,
                            enrich_queue_dir=queue_dir)
    assert result['healthy'] is False
    assert 'orphan123' in result['orphaned_queue']


def test_capture_health_empty_db(db, tmp_path):
    """Health check on empty DB is healthy with no last capture."""
    sessions_dir = tmp_path / 'sessions'
    sessions_dir.mkdir()
    queue_dir = tmp_path / 'enrich-queue'

    result = capture_health(db, sessions_dir=sessions_dir,
                            enrich_queue_dir=queue_dir)
    assert result['healthy'] is True
    assert result['last_capture'] is None
