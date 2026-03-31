"""Weekly review: summary persistence, signal triage, synthesis generation."""

import sqlite3
from typing import Optional

from .db import utc_now
from .analysis import (
    shared_concepts, stale_concepts, hot_concepts,
    graph_summary, concept_velocity,
)
from .confidence import promote_concept, check_promotion_eligibility


def create_weekly_summary(conn: sqlite3.Connection, week_start: str,
                          summary_text: str = '') -> dict:
    """Create a weekly summary snapshot. One per week."""
    existing = conn.execute(
        "SELECT id FROM weekly_summaries WHERE week_start = ?", (week_start,)
    ).fetchone()
    if existing:
        raise ValueError(f"Summary for week {week_start} already exists.")

    now = utc_now()
    stats = graph_summary(conn)

    cursor = conn.execute(
        "INSERT INTO weekly_summaries "
        "(week_start, summary, signals, concept_count, edge_count, "
        "project_count, created_at) VALUES (?, ?, '[]', ?, ?, ?, ?)",
        (week_start, summary_text, stats['concepts'], stats['edges'],
         stats['projects'], now)
    )
    conn.commit()
    return {
        'id': cursor.lastrowid,
        'week_start': week_start,
        'concept_count': stats['concepts'],
        'edge_count': stats['edges'],
        'project_count': stats['projects'],
    }


def list_weekly_summaries(conn: sqlite3.Connection,
                          limit: int = 12) -> list[dict]:
    """List recent weekly summaries, newest first."""
    rows = conn.execute(
        "SELECT * FROM weekly_summaries ORDER BY week_start DESC LIMIT ?",
        (limit,)
    ).fetchall()
    return [dict(r) for r in rows]


def get_weekly_summary(conn: sqlite3.Connection,
                       week_start: str) -> Optional[dict]:
    """Get a specific weekly summary by week_start date."""
    row = conn.execute(
        "SELECT * FROM weekly_summaries WHERE week_start = ?", (week_start,)
    ).fetchone()
    return dict(row) if row else None


def triage_signal(conn: sqlite3.Connection, concept_name: str = '',
                  edge_id: int = 0, action: str = 'defer',
                  target_confidence: str = '') -> dict:
    """Triage a signal: promote, dismiss, or defer.

    promote: elevate concept confidence (requires target_confidence).
    dismiss: mark edge as dismissed (requires edge_id).
    defer: no-op, logged for tracking.
    """
    if action not in ('promote', 'dismiss', 'defer'):
        raise ValueError(f"Invalid action '{action}'. Must be: promote, dismiss, defer")

    if action == 'promote':
        result = promote_concept(conn, concept_name, target_confidence)
        return {'action': 'promote', **result}

    if action == 'dismiss':
        edge = conn.execute(
            "SELECT id, strength FROM concept_edges WHERE id = ?", (edge_id,)
        ).fetchone()
        if not edge:
            raise ValueError(f"Edge not found: {edge_id}")
        conn.execute(
            "UPDATE concept_edges SET dismissed = 1, "
            "dismissed_original_strength = ? WHERE id = ?",
            (edge['strength'], edge_id)
        )
        conn.commit()
        return {'action': 'dismiss', 'edge_id': edge_id}

    # defer
    return {'action': 'defer', 'concept_name': concept_name}


def pending_signals(conn: sqlite3.Connection) -> dict:
    """Gather all signals that need triage."""
    return {
        'promotion_eligible': check_promotion_eligibility(conn),
        'stale': stale_concepts(conn, days=14),
        'hot': hot_concepts(conn, limit=5),
        'shared': shared_concepts(conn),
    }


def generate_synthesis(conn: sqlite3.Connection) -> dict:
    """Generate a weekly synthesis data structure.

    Contains graph snapshot, pending signals, velocity,
    and comparison to previous week.
    """
    stats = graph_summary(conn)
    velocity = concept_velocity(conn, weeks=4)
    eligible = check_promotion_eligibility(conn)
    stale = stale_concepts(conn, days=14)
    shared = shared_concepts(conn)

    # Previous week comparison
    prev = conn.execute(
        "SELECT * FROM weekly_summaries ORDER BY week_start DESC LIMIT 1"
    ).fetchone()
    delta = {}
    if prev:
        delta = {
            'concepts': stats['concepts'] - prev['concept_count'],
            'edges': stats['edges'] - prev['edge_count'],
            'projects': stats['projects'] - prev['project_count'],
        }

    return {
        'graph_snapshot': stats,
        'velocity': velocity,
        'promotion_eligible': eligible,
        'stale': stale,
        'shared': shared,
        'delta': delta,
    }
