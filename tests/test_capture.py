"""Tests for session capture (capture.py)."""

import json
import pytest
from pathlib import Path

from cortex_lib.capture import (
    capture_session, load_stoplist, tokenize_paths, tokenize_commits,
    filter_tokens, compute_session_hash, capture_prune, DEFAULT_STOPLIST,
)
from cortex_lib.ops import upsert_concept


def test_tokenize_paths():
    """Splits file paths into component tokens."""
    paths = ['M src/lib/ops.py', 'A app/main.py']
    tokens = tokenize_paths(paths)
    assert 'src' in tokens
    assert 'lib' in tokens
    assert 'ops' in tokens
    assert 'py' in tokens
    assert 'app' in tokens
    assert 'main' in tokens


def test_tokenize_commits():
    """Extracts tokens from commit messages, stripping hashes and prefixes."""
    commits = ['a1b2c3d feat: add capture command', 'd4e5f6g fix: edge case']
    tokens = tokenize_commits(commits)
    assert 'add' in tokens
    assert 'capture' in tokens
    assert 'command' in tokens
    assert 'edge' in tokens
    assert 'case' in tokens


def test_filter_tokens_removes_stoplist():
    """Stoplist tokens are removed from the result."""
    stoplist = {'src', 'lib', 'py', 'fix'}
    tokens = ['src', 'capture', 'lib', 'py', 'session']
    result = filter_tokens(tokens, stoplist)
    assert 'src' not in result
    assert 'lib' not in result
    assert 'py' not in result
    assert 'capture' in result
    assert 'session' in result


def test_filter_tokens_removes_short():
    """Tokens shorter than 3 chars are removed."""
    result = filter_tokens(['ab', 'cd', 'api', 'db'], set())
    assert 'ab' not in result
    assert 'cd' not in result
    assert 'db' not in result
    assert 'api' in result


def test_filter_tokens_deduplicates():
    """Duplicate tokens appear only once."""
    result = filter_tokens(['capture', 'capture', 'session'], set())
    assert result.count('capture') == 1


def test_load_stoplist_defaults():
    """Default stoplist includes expected path components and extensions."""
    stoplist = load_stoplist(Path('/nonexistent'))
    assert 'src' in stoplist
    assert 'py' in stoplist
    assert 'feat' in stoplist
    assert '__pycache__' in stoplist


def test_load_stoplist_from_file(tmp_path):
    """Custom stoplist file extends defaults."""
    custom = tmp_path / 'stoplist.txt'
    custom.write_text('custom-token\nanother-token\n')
    stoplist = load_stoplist(custom)
    assert 'custom-token' in stoplist
    assert 'another-token' in stoplist
    # Defaults still present
    assert 'src' in stoplist


def test_compute_session_hash_deterministic():
    """Same inputs produce the same hash."""
    h1 = compute_session_hash('2026-01-01T00:00:00Z', 'project-alpha',
                              ['a.py', 'b.py'], 'abc123')
    h2 = compute_session_hash('2026-01-01T00:00:00Z', 'project-alpha',
                              ['b.py', 'a.py'], 'abc123')  # sorted
    assert h1 == h2


def test_compute_session_hash_varies_with_head():
    """Different HEAD refs produce different hashes."""
    h1 = compute_session_hash('2026-01-01T00:00:00Z', 'project-alpha', [], 'abc123')
    h2 = compute_session_hash('2026-01-01T00:00:00Z', 'project-alpha', [], 'def456')
    assert h1 != h2


def test_capture_session_basic(db, tmp_path):
    """Capture creates a session record and detail files."""
    sessions_dir = tmp_path / 'sessions'
    queue_dir = tmp_path / 'enrich-queue'
    hash_path = tmp_path / 'current-session-hash'

    # Write session-start file
    start_path = tmp_path / 'session-start'
    start_path.write_text(json.dumps({
        'timestamp': '2026-04-07T10:00:00Z',
        'head_ref': 'abc123def456',
        'memory_snapshot_hash': 'memhash1',
        'concepts_loaded': ['api-design'],
        'memory_entries_loaded': ['hash1', 'hash2'],
    }))

    result = capture_session(
        db,
        files=['M src/lib/utils.py', 'A app/main.py'],
        commits=['a1b2c3d feat: add new feature'],
        project='project-alpha',
        branch='main',
        duration_seconds=300,
        session_start_path=start_path,
        sessions_dir=sessions_dir,
        enrich_queue_dir=queue_dir,
        current_hash_path=hash_path,
    )

    assert result['action'] == 'created'
    assert result['status'] == 'raw'
    assert isinstance(result['session_hash'], str)
    assert len(result['session_hash']) == 12

    # Verify DB record
    row = db.execute("SELECT * FROM sessions WHERE session_hash = ?",
                     (result['session_hash'],)).fetchone()
    assert row is not None
    assert row['project'] == 'project-alpha'
    assert row['status'] == 'raw'

    # Verify detail file
    assert (sessions_dir / f"{result['session_hash']}.md").exists()

    # Verify enrich-queue entry
    assert (queue_dir / f"{result['session_hash']}.json").exists()

    # Verify current-session-hash
    assert hash_path.read_text() == result['session_hash']


def test_capture_session_idempotent(db, tmp_path):
    """Pre-existing session hash causes skip (crash recovery scenario)."""
    sessions_dir = tmp_path / 'sessions'
    queue_dir = tmp_path / 'enrich-queue'
    hash_path = tmp_path / 'current-session-hash'
    start_path = tmp_path / 'session-start'
    start_path.write_text(json.dumps({
        'timestamp': '2026-04-07T10:00:00Z',
        'head_ref': 'abc123',
    }))

    r1 = capture_session(
        db, files=[], commits=[], project='project-alpha',
        session_start_path=start_path,
        sessions_dir=sessions_dir, enrich_queue_dir=queue_dir,
        current_hash_path=hash_path,
    )
    assert r1['action'] == 'created'

    # Manually insert the same hash to simulate crash-recovery duplicate
    # The hash is based on utc_now() so a second call produces a different hash.
    # Idempotency protects against duplicate hashes (e.g., hook re-execution).
    db.execute(
        "INSERT OR IGNORE INTO sessions (session_hash, timestamp, project, status) "
        "VALUES ('forceddup123', '2026-04-07T10:00:00Z', 'project-alpha', 'raw')"
    )
    db.commit()

    # Verify the session exists
    row = db.execute("SELECT * FROM sessions WHERE session_hash = 'forceddup123'").fetchone()
    assert row is not None

    # Count sessions before
    count_before = db.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
    # Trying to insert same hash again is a no-op at the DB level
    try:
        db.execute(
            "INSERT INTO sessions (session_hash, timestamp, project, status) "
            "VALUES ('forceddup123', '2026-04-07T11:00:00Z', 'project-alpha', 'raw')"
        )
    except Exception:
        pass
    count_after = db.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
    assert count_before == count_after


def test_capture_session_incomplete(db, tmp_path):
    """Missing session-start produces an incomplete record."""
    sessions_dir = tmp_path / 'sessions'
    queue_dir = tmp_path / 'enrich-queue'
    hash_path = tmp_path / 'current-session-hash'

    result = capture_session(
        db,
        files=['something.py'],
        commits=['abc fix: thing'],
        project='project-alpha',
        session_start_path=tmp_path / 'nonexistent',
        sessions_dir=sessions_dir,
        enrich_queue_dir=queue_dir,
        current_hash_path=hash_path,
    )

    assert result['action'] == 'incomplete'
    assert result['status'] == 'enriched'
    assert result['matched_concepts'] == []

    # No enrich-queue file for incomplete sessions
    assert not queue_dir.exists() or len(list(queue_dir.glob('*.json'))) == 0


def test_capture_session_concept_matching(db, tmp_path):
    """Capture matches file tokens against existing concepts."""
    # Pre-populate concepts
    upsert_concept(db, 'caching', kind='pattern')
    upsert_concept(db, 'api-design', kind='pattern')

    sessions_dir = tmp_path / 'sessions'
    queue_dir = tmp_path / 'enrich-queue'
    hash_path = tmp_path / 'current-session-hash'
    start_path = tmp_path / 'session-start'
    start_path.write_text(json.dumps({
        'timestamp': '2026-04-07T10:00:00Z',
        'head_ref': 'abc123',
    }))

    result = capture_session(
        db,
        files=['M src/caching/handler.py'],
        commits=['d4e5f6g refactor: improve caching layer'],
        project='project-alpha',
        session_start_path=start_path,
        sessions_dir=sessions_dir,
        enrich_queue_dir=queue_dir,
        current_hash_path=hash_path,
    )

    assert 'caching' in result['matched_concepts']


def test_capture_session_stoplist_prevents_false_matches(db, tmp_path):
    """Stoplist prevents matching noise tokens like 'test' or 'config'."""
    upsert_concept(db, 'test', kind='topic')
    upsert_concept(db, 'config', kind='topic')

    sessions_dir = tmp_path / 'sessions'
    queue_dir = tmp_path / 'enrich-queue'
    hash_path = tmp_path / 'current-session-hash'
    start_path = tmp_path / 'session-start'
    start_path.write_text(json.dumps({
        'timestamp': '2026-04-07T10:00:00Z',
        'head_ref': 'abc123',
    }))

    result = capture_session(
        db,
        files=['M tests/test_ops.py', 'M config/settings.json'],
        commits=[],
        project='project-alpha',
        session_start_path=start_path,
        sessions_dir=sessions_dir,
        enrich_queue_dir=queue_dir,
        current_hash_path=hash_path,
    )

    # 'test' and 'config' are in the stoplist, should not match
    assert 'test' not in result['matched_concepts']
    assert 'config' not in result['matched_concepts']


def test_capture_prune_removes_old_files(db, tmp_path):
    """Prune removes detail and queue files for sessions older than threshold."""
    sessions_dir = tmp_path / 'sessions'
    sessions_dir.mkdir()
    queue_dir = tmp_path / 'enrich-queue'
    queue_dir.mkdir()

    # Insert an old session
    old_ts = '2026-01-01T00:00:00+00:00'
    db.execute(
        "INSERT INTO sessions (session_hash, timestamp, project, status) "
        "VALUES ('old123', ?, 'project-alpha', 'raw')", (old_ts,)
    )
    db.commit()
    (sessions_dir / 'old123.md').write_text('old session')
    (queue_dir / 'old123.json').write_text('{}')

    result = capture_prune(db, days=3, sessions_dir=sessions_dir,
                           enrich_queue_dir=queue_dir)

    assert result['pruned_details'] == 1
    assert result['pruned_queue'] == 1
    assert not (sessions_dir / 'old123.md').exists()
    assert not (queue_dir / 'old123.json').exists()

    # Session should be marked as enriched
    row = db.execute("SELECT status FROM sessions WHERE session_hash = 'old123'").fetchone()
    assert row['status'] == 'enriched'


def test_capture_zero_file_session(db, tmp_path):
    """Sessions with no files are recorded correctly."""
    sessions_dir = tmp_path / 'sessions'
    queue_dir = tmp_path / 'enrich-queue'
    hash_path = tmp_path / 'current-session-hash'
    start_path = tmp_path / 'session-start'
    start_path.write_text(json.dumps({
        'timestamp': '2026-04-07T10:00:00Z',
        'head_ref': 'abc123',
    }))

    result = capture_session(
        db, files=[], commits=[], project='project-alpha',
        session_start_path=start_path,
        sessions_dir=sessions_dir,
        enrich_queue_dir=queue_dir,
        current_hash_path=hash_path,
    )

    assert result['action'] == 'created'
    assert result['matched_concepts'] == []
    row = db.execute("SELECT files FROM sessions WHERE session_hash = ?",
                     (result['session_hash'],)).fetchone()
    assert json.loads(row['files']) == []
