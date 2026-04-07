"""Tests for session context brief generation."""

import json
import sys
from datetime import datetime, timezone, timedelta
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import pytest

from cortex_lib.db import init_db
from cortex_lib.ops import upsert_concept, add_edge, log_extraction
from cortex_lib.brief import generate_brief, format_brief, _relative_time, MAX_BRIEF_CHARS
from cortex_lib.cli import main
from cortex_lib.hooks import (
    generate_hooks_config, install_hooks,
    BRIEF_WRITE_SH, BRIEF_INJECT_SH,
)


# -- generate_brief tests --

def test_empty_database(db):
    """Empty graph returns minimal brief with zero stats."""
    data = generate_brief(db)
    assert data['date']
    assert data['graph_stats']['concepts'] == 0
    assert 'hot' not in data
    assert 'last_session' not in data


def test_with_concepts(db):
    """Database with concepts includes hot list."""
    upsert_concept(db, 'python', kind='tool')
    upsert_concept(db, 'fastapi', kind='tool')
    add_edge(db, 'fastapi', 'python', 'depends-on')

    data = generate_brief(db)
    assert data['graph_stats']['concepts'] == 2
    assert len(data['hot']) == 2
    assert data['hot'][0]['name'] in ('python', 'fastapi')


def test_with_extraction(db):
    """Database with extraction includes last_session data."""
    upsert_concept(db, 'cortex', kind='project', project='cortex')
    log_extraction(
        db, session_hash='abc123',
        concepts_proposed=['cortex', 'graph'],
        created_concepts=['cortex'],
        created_edges=[],
        rejected_count=1, weight=3,
    )

    data = generate_brief(db)
    assert 'last_session' in data
    assert data['last_session']['concepts'] == ['cortex']
    assert data['last_session']['weight'] == 3


def test_active_projects_7day_window(db):
    """Active projects only includes those with sources in last 7 days."""
    upsert_concept(db, 'fresh', kind='topic', project='active-project',
                   session_hash='recent')

    # Insert a stale source (>7 days ago)
    old_ts = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
    db.execute(
        "INSERT INTO concept_sources (concept_id, session_hash, project, timestamp, weight) "
        "VALUES ((SELECT id FROM concepts WHERE name='fresh'), 'old', 'stale-project', ?, 1)",
        (old_ts,)
    )
    db.commit()

    data = generate_brief(db)
    projects = data.get('active_projects', [])
    assert 'active-project' in projects
    assert 'stale-project' not in projects


def test_pending_promotions(db):
    """Concepts eligible for promotion appear in brief."""
    # Create a concept with 3+ sources to make it promotion-eligible
    upsert_concept(db, 'mature-concept', kind='pattern', project='p1',
                   session_hash='s1')
    upsert_concept(db, 'mature-concept', kind='pattern', project='p2',
                   session_hash='s2')
    upsert_concept(db, 'mature-concept', kind='pattern', project='p3',
                   session_hash='s3')

    data = generate_brief(db)
    promos = data.get('pending_promotions', [])
    eligible_names = [p['name'] for p in promos]
    assert 'mature-concept' in eligible_names


def test_hot_concepts_limited_to_5(db):
    """Hot concepts returns at most 5."""
    for i in range(8):
        upsert_concept(db, f'concept-{i}', kind='topic')

    data = generate_brief(db)
    assert len(data['hot']) <= 5


# -- format_brief tests --

def test_format_empty_database(db):
    """Empty database produces 'No sessions recorded yet'."""
    data = generate_brief(db)
    output = format_brief(data)
    assert 'No sessions recorded yet' in output


def test_format_has_header(db):
    """Output starts with Cortex Brief header."""
    upsert_concept(db, 'test', kind='topic')
    data = generate_brief(db)
    output = format_brief(data)
    assert output.startswith('## Cortex Brief (')


def test_format_under_max_chars(db):
    """Brief output stays compact (under MAX_BRIEF_CHARS)."""
    for i in range(25):
        upsert_concept(db, f'concept-{i}', kind='topic', project=f'proj-{i % 5}',
                       session_hash=f's{i}')
    log_extraction(
        db, session_hash='test',
        concepts_proposed=['a', 'b', 'c'],
        created_concepts=['a', 'b', 'c'],
        created_edges=[], rejected_count=0, weight=4,
    )

    data = generate_brief(db)
    output = format_brief(data)
    assert len(output) < MAX_BRIEF_CHARS


def test_format_light_mode_young_graph(db):
    """Graphs with <20 concepts get condensed 2-line format."""
    upsert_concept(db, 'alpha', kind='topic')
    upsert_concept(db, 'beta', kind='topic')
    log_extraction(
        db, session_hash='test',
        concepts_proposed=['alpha'],
        created_concepts=['alpha'],
        created_edges=[], rejected_count=0, weight=2,
    )

    data = generate_brief(db)
    output = format_brief(data)
    assert 'Graph:' in output
    assert 'Last session' in output
    # Light mode should NOT have Active projects or Hot concepts lines
    assert 'Active projects' not in output
    assert 'Hot concepts' not in output


def test_format_promotions_names_concepts(db):
    """Pending promotions line names specific concepts in full mode."""
    # Use very distinct names to avoid fuzzy canonicalization
    distinct_names = [
        'python', 'javascript', 'kubernetes', 'postgresql', 'terraform',
        'docker', 'graphql', 'typescript', 'mongodb', 'elasticsearch',
        'redis', 'nginx', 'fastapi', 'django', 'flask',
        'pytorch', 'pandas', 'numpy', 'scipy', 'matplotlib',
        'airflow', 'kafka', 'spark', 'hadoop', 'dbt',
    ]
    for name in distinct_names:
        upsert_concept(db, name, kind='tool')
    # Create promotion-eligible concept
    upsert_concept(db, 'mature-one', kind='pattern', project='p1', session_hash='s1')
    upsert_concept(db, 'mature-one', kind='pattern', project='p2', session_hash='s2')
    upsert_concept(db, 'mature-one', kind='pattern', project='p3', session_hash='s3')

    data = generate_brief(db)
    assert data['graph_stats']['concepts'] >= 20, f"Need >=20 concepts for full mode, got {data['graph_stats']['concepts']}"
    output = format_brief(data)
    assert 'mature-one' in output


def test_relative_time():
    """_relative_time produces human-readable relative strings."""
    now = datetime.now(timezone.utc)
    assert _relative_time((now - timedelta(minutes=5)).isoformat()) == "just now"
    assert "h ago" in _relative_time((now - timedelta(hours=3)).isoformat())
    assert "day" in _relative_time((now - timedelta(days=2)).isoformat())


def test_format_sections_conditional(db):
    """Sections only appear when data is non-empty."""
    upsert_concept(db, 'test', kind='topic')
    data = generate_brief(db)
    output = format_brief(data)
    # No extraction, so no "Last session" line
    assert 'Last session' not in output
    # No promotions pending
    assert 'Pending promotions' not in output
    # Graph stats always present when concepts exist
    assert 'Graph:' in output


# -- CLI integration tests --

def _run_cli(*args):
    """Run CLI with given args, capture stdout."""
    out = StringIO()
    with patch.object(sys, 'argv', ['concepts'] + list(args)), \
         patch.object(sys, 'stdout', out), \
         patch.object(sys, 'exit') as mock_exit:
        main()
    mock_exit.assert_called_with(0)
    return out.getvalue()


def test_cli_brief_stdout(tmp_path):
    """brief prints markdown to stdout by default."""
    db_path = tmp_path / "test.db"
    conn = init_db(db_path)
    upsert_concept(conn, 'test', kind='topic')
    conn.close()

    output = _run_cli('--db', str(db_path), 'brief')
    assert '## Cortex Brief' in output


def test_cli_brief_json(tmp_path):
    """brief --json returns valid JSON with expected keys."""
    db_path = tmp_path / "test.db"
    conn = init_db(db_path)
    upsert_concept(conn, 'test', kind='topic')
    conn.close()

    output = _run_cli('--db', str(db_path), '--json', 'brief')
    data = json.loads(output)
    assert 'date' in data
    assert 'graph_stats' in data


def test_cli_brief_output_file(tmp_path):
    """brief --output writes file, stdout is empty."""
    db_path = tmp_path / "test.db"
    out_path = tmp_path / "cortex-brief.md"
    conn = init_db(db_path)
    upsert_concept(conn, 'test', kind='topic')
    conn.close()

    output = _run_cli('--db', str(db_path), 'brief', '--output', str(out_path))
    assert output.strip() == ''
    assert out_path.exists()
    content = out_path.read_text()
    assert '## Cortex Brief' in content


def test_cli_brief_empty_db(tmp_path):
    """brief on empty DB produces graceful output."""
    db_path = tmp_path / "test.db"
    conn = init_db(db_path)
    conn.close()

    output = _run_cli('--db', str(db_path), 'brief')
    assert 'No sessions recorded yet' in output


# -- Unprocessed sessions tests --

def test_unprocessed_sessions_in_brief(db):
    """Raw sessions appear in the brief as unprocessed."""
    # Need 20+ concepts for full mode
    distinct_names = [
        'python', 'javascript', 'kubernetes', 'postgresql', 'terraform',
        'docker', 'graphql', 'typescript', 'mongodb', 'elasticsearch',
        'redis', 'nginx', 'fastapi', 'django', 'flask',
        'pytorch', 'pandas', 'numpy', 'scipy', 'matplotlib',
    ]
    for name in distinct_names:
        upsert_concept(db, name, kind='tool')

    # Add a raw session
    db.execute(
        "INSERT INTO sessions (session_hash, timestamp, project, status, "
        "files, commits, duration_seconds) "
        "VALUES ('raw1', '2026-04-07T10:00:00+00:00', 'project-alpha', 'raw', "
        "'[\"src/lib/ops.py\"]', '[\"a1b feat: add thing\"]', 2700)"
    )
    db.commit()

    data = generate_brief(db)
    assert 'unprocessed_sessions' in data
    assert len(data['unprocessed_sessions']) == 1

    output = format_brief(data)
    assert 'Recent unprocessed' in output
    assert 'project-alpha' in output


def test_no_unprocessed_when_clean(db):
    """No unprocessed section when all sessions are enriched/saved."""
    for name in ['alpha', 'beta']:
        upsert_concept(db, name, kind='topic')

    db.execute(
        "INSERT INTO sessions (session_hash, timestamp, project, status) "
        "VALUES ('sess1', '2026-04-07T10:00:00+00:00', 'project-alpha', 'saved')"
    )
    db.commit()

    data = generate_brief(db)
    assert 'unprocessed_sessions' not in data


def test_unprocessed_sessions_max_3(db):
    """At most 3 unprocessed sessions appear."""
    upsert_concept(db, 'placeholder', kind='topic')
    for i in range(5):
        db.execute(
            "INSERT INTO sessions (session_hash, timestamp, project, status) "
            "VALUES (?, ?, 'project-alpha', 'raw')",
            (f'sess{i}', f'2026-04-0{i+1}T10:00:00+00:00')
        )
    db.commit()

    data = generate_brief(db)
    assert len(data.get('unprocessed_sessions', [])) <= 3


# -- Hook tests --

def test_hooks_config_includes_brief():
    """generate_hooks_config includes brief-write in Stop and brief-inject in SessionStart."""
    config = generate_hooks_config()
    session_cmds = [e['hooks'][0]['command'] for e in config['hooks']['SessionStart']]
    stop_cmds = [e['hooks'][0]['command'] for e in config['hooks']['Stop']]

    assert any('brief-inject.sh' in c for c in session_cmds)
    assert any('brief-write.sh' in c for c in stop_cmds)


def test_hooks_install_writes_brief_scripts(tmp_path):
    """install_hooks writes both brief hook scripts."""
    scripts_dir = tmp_path / "scripts"
    settings_path = tmp_path / "settings.json"
    settings_path.write_text("{}")

    install_hooks(scripts_dir=scripts_dir, settings_path=settings_path)

    assert (scripts_dir / "brief-write.sh").exists()
    assert (scripts_dir / "brief-inject.sh").exists()


def test_brief_write_script_content():
    """brief-write.sh has .memory-config guard and --output flag."""
    assert '.memory-config' in BRIEF_WRITE_SH
    assert '--output' in BRIEF_WRITE_SH
    assert '#!/usr/bin/env bash' in BRIEF_WRITE_SH


def test_brief_inject_script_content():
    """brief-inject.sh has staleness check and .memory-config guard."""
    assert '.memory-config' in BRIEF_INJECT_SH
    assert 'STALE_SECONDS' in BRIEF_INJECT_SH
    assert '--output' in BRIEF_INJECT_SH
    assert '#!/usr/bin/env bash' in BRIEF_INJECT_SH


def test_hooks_no_duplicates_on_reinstall(tmp_path):
    """Reinstalling hooks does not duplicate entries."""
    scripts_dir = tmp_path / "scripts"
    settings_path = tmp_path / "settings.json"
    settings_path.write_text("{}")

    install_hooks(scripts_dir=scripts_dir, settings_path=settings_path)
    install_hooks(scripts_dir=scripts_dir, settings_path=settings_path)

    data = json.loads(settings_path.read_text())
    # Extract commands from matcher-wrapped format
    session_cmds = []
    for entry in data['hooks']['SessionStart']:
        if 'hooks' in entry:
            for h in entry['hooks']:
                session_cmds.append(h.get('command', ''))
        elif 'command' in entry:
            session_cmds.append(entry['command'])
    brief_inject_count = sum(1 for c in session_cmds if 'brief-inject.sh' in c)
    assert brief_inject_count == 1


def test_hooks_no_duplicates_with_legacy_format(tmp_path):
    """Reinstalling does not duplicate when existing hooks use legacy flat format."""
    scripts_dir = tmp_path / "scripts"
    settings_path = tmp_path / "settings.json"
    # Seed with legacy flat format hooks
    legacy = {
        "hooks": {
            "SessionStart": [
                {"type": "command", "command": "bash ~/.claude/scripts/review-check.sh"},
            ],
            "Stop": [
                {"type": "command", "command": "bash ~/.claude/scripts/reflect-gate.sh"},
            ],
        }
    }
    settings_path.write_text(json.dumps(legacy))

    install_hooks(scripts_dir=scripts_dir, settings_path=settings_path)

    data = json.loads(settings_path.read_text())
    # review-check should not be duplicated (detected in legacy format)
    all_cmds = []
    for entry in data['hooks']['SessionStart']:
        if 'hooks' in entry:
            for h in entry['hooks']:
                all_cmds.append(h.get('command', ''))
        elif 'command' in entry:
            all_cmds.append(entry['command'])
    review_count = sum(1 for c in all_cmds if 'review-check.sh' in c)
    assert review_count == 1
