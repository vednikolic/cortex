"""Session context brief generation for Cortex.

Produces a compact markdown brief from the knowledge graph state.
Designed for injection into coding sessions via @cortex-brief.md import.
"""

import json
import sqlite3
from datetime import datetime, timezone, timedelta

from .analysis import hot_concepts, graph_summary
from .capture import query_sessions, format_session_oneline
from .confidence import check_promotion_eligibility

# Brief should stay under ~200 tokens to avoid bloating session context
MAX_BRIEF_CHARS = 800


def _relative_time(timestamp: str) -> str:
    """Convert ISO timestamp to relative human string (e.g. '2h ago')."""
    try:
        dt = datetime.fromisoformat(timestamp)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        delta = datetime.now(timezone.utc) - dt
        hours = int(delta.total_seconds() // 3600)
        if hours < 1:
            return "just now"
        if hours < 24:
            return f"{hours}h ago"
        days = hours // 24
        if days == 1:
            return "1 day ago"
        return f"{days} days ago"
    except (ValueError, TypeError):
        return ""


def generate_brief(conn: sqlite3.Connection) -> dict:
    """Generate session brief from graph state.

    Queries four data sources (DB only, no file reads):
    - Last extraction from extraction_log
    - Hot concepts (top 5)
    - Active projects (activity in last 7 days)
    - Pending promotions

    Returns dict with optional keys. Missing data produces empty lists/dicts.
    """
    today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    result: dict = {'date': today}

    # Graph stats
    stats = graph_summary(conn)
    result['graph_stats'] = stats

    # Empty graph: return early
    if stats['concepts'] == 0:
        return result

    # Hot concepts (top 5)
    hot = hot_concepts(conn, limit=5)
    result['hot'] = [
        {'name': c['name'], 'score': c['source_count'] + c['edge_count']}
        for c in hot
    ]

    # Active projects (7-day window)
    cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    rows = conn.execute(
        "SELECT DISTINCT project FROM concept_sources "
        "WHERE project != '' AND timestamp > ? ORDER BY project",
        (cutoff,)
    ).fetchall()
    result['active_projects'] = [r['project'] for r in rows]

    # Last extraction
    last = conn.execute(
        "SELECT * FROM extraction_log ORDER BY id DESC LIMIT 1"
    ).fetchone()
    if last:
        created = json.loads(last['created_concepts'])
        result['last_session'] = {
            'concepts': created,
            'weight': last['weight'],
            'timestamp': last['timestamp'],
        }

    # Pending promotions (include concept names for actionability)
    eligible = check_promotion_eligibility(conn)
    if eligible:
        result['pending_promotions'] = [
            {'name': e['name'], 'suggested': e['suggested']}
            for e in eligible
        ]

    # Recent unprocessed sessions (max 3, raw status only)
    raw_sessions = query_sessions(conn, status='raw', limit=3)
    if raw_sessions:
        result['unprocessed_sessions'] = raw_sessions

    return result


def format_brief(data: dict) -> str:
    """Format brief dict as compact markdown for CLAUDE.md injection.

    Target: under MAX_BRIEF_CHARS (~200 tokens). Each section is optional.
    Young graphs (<20 concepts) get a condensed 2-line format.
    """
    lines = [f"## Cortex Brief ({data['date']})"]

    stats = data.get('graph_stats', {})
    if stats.get('concepts', 0) == 0:
        lines.append('')
        lines.append('No sessions recorded yet.')
        return '\n'.join(lines)

    # Light mode for young graphs: just stats + last session
    if stats['concepts'] < 20:
        lines.append(
            f"**Graph:** {stats['concepts']} concepts, "
            f"{stats['edges']} edges, {stats['projects']} projects"
        )
        session = data.get('last_session')
        if session and session['concepts']:
            when = _relative_time(session['timestamp'])
            concepts_str = ', '.join(session['concepts'])
            time_part = f" ({when})" if when else ""
            lines.append(
                f"**Last session{time_part}:** {len(session['concepts'])} concepts "
                f"(weight {session['weight']}) -- {concepts_str}"
            )
        return '\n'.join(lines)

    # Full mode for mature graphs
    # Active projects
    projects = data.get('active_projects', [])
    if projects:
        lines.append(f"**Active projects:** {', '.join(projects)}")

    # Hot concepts
    hot = data.get('hot', [])
    if hot:
        items = ', '.join(f"{c['name']} ({c['score']})" for c in hot)
        lines.append(f"**Hot concepts:** {items}")

    # Last session with relative timestamp
    session = data.get('last_session')
    if session and session['concepts']:
        when = _relative_time(session['timestamp'])
        concepts_str = ', '.join(session['concepts'])
        time_part = f" ({when})" if when else ""
        lines.append(
            f"**Last session{time_part}:** {len(session['concepts'])} concepts "
            f"(weight {session['weight']}) -- {concepts_str}"
        )

    # Pending promotions with concept names (up to 3)
    promos = data.get('pending_promotions', [])
    if promos:
        names = [p['name'] for p in promos[:3]]
        suffix = f" (+{len(promos) - 3} more)" if len(promos) > 3 else ""
        lines.append(f"**Pending promotions:** {', '.join(names)}{suffix}")

    # Recent unprocessed sessions
    unprocessed = data.get('unprocessed_sessions', [])
    if unprocessed:
        entries = [format_session_oneline(s) for s in unprocessed]
        lines.append(f"**Recent unprocessed:** {' | '.join(entries)}")

    # Graph stats
    lines.append(
        f"**Graph:** {stats['concepts']} concepts, "
        f"{stats['edges']} edges, {stats['projects']} projects"
    )

    return '\n'.join(lines)
