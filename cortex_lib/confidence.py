"""Bidirectional confidence lifecycle for concepts.

Promotion: tentative -> established -> settled (manual or auto-eligible).
Decay: settled -> established (90d) -> tentative (60d).
"""

import sqlite3
from datetime import datetime, timezone, timedelta

from .db import utc_now, VALID_CONFIDENCE

CONFIDENCE_ORDER = ['tentative', 'established', 'settled']


def promote_concept(conn: sqlite3.Connection, name: str,
                    new_confidence: str) -> dict:
    """Manually promote a concept's confidence level. Cannot demote."""
    if new_confidence not in VALID_CONFIDENCE:
        raise ValueError(
            f"Invalid confidence '{new_confidence}'. "
            f"Must be one of: {', '.join(sorted(VALID_CONFIDENCE))}"
        )

    concept = conn.execute(
        "SELECT id, name, confidence FROM concepts WHERE LOWER(name) = LOWER(?)",
        (name,)
    ).fetchone()
    if not concept:
        raise ValueError(f"Concept not found: '{name}'")

    old_idx = CONFIDENCE_ORDER.index(concept['confidence'])
    new_idx = CONFIDENCE_ORDER.index(new_confidence)
    if new_idx < old_idx:
        raise ValueError(
            f"Cannot demote '{name}' from {concept['confidence']} to {new_confidence}. "
            f"Use confidence decay for demotions."
        )

    now = utc_now()
    conn.execute(
        "UPDATE concepts SET confidence = ?, updated_at = ? WHERE id = ?",
        (new_confidence, now, concept['id'])
    )
    conn.commit()
    return {
        'concept_id': concept['id'],
        'name': concept['name'],
        'old_confidence': concept['confidence'],
        'new_confidence': new_confidence,
    }


def check_promotion_eligibility(conn: sqlite3.Connection) -> list[dict]:
    """Check which concepts are eligible for promotion.

    Tentative -> established: 3+ sources OR 2+ projects.
    Established -> settled: max edge strength >= 5 AND age >= 30 days.
    """
    eligible = []
    now = datetime.now(timezone.utc)

    # Tentative -> established
    for c in conn.execute("""
        SELECT c.id, c.name, c.source_count, c.first_seen,
               COUNT(DISTINCT cs.project) as project_count
        FROM concepts c
        LEFT JOIN concept_sources cs ON c.id = cs.concept_id AND cs.project != ''
        WHERE c.confidence = 'tentative'
        GROUP BY c.id
        HAVING c.source_count >= 3 OR COUNT(DISTINCT cs.project) >= 2
    """).fetchall():
        eligible.append({
            'id': c['id'], 'name': c['name'],
            'current': 'tentative', 'suggested': 'established',
            'reason': f"sources={c['source_count']}, projects={c['project_count']}",
        })

    # Established -> settled
    for c in conn.execute("""
        SELECT c.id, c.name, c.first_seen,
               MAX(e.strength) as max_strength
        FROM concepts c
        LEFT JOIN concept_edges e
            ON c.id = e.from_concept_id OR c.id = e.to_concept_id
        WHERE c.confidence = 'established'
        GROUP BY c.id
        HAVING MAX(e.strength) >= 5
    """).fetchall():
        first_seen = datetime.fromisoformat(c['first_seen'])
        age_days = (now - first_seen).days
        if age_days >= 30:
            eligible.append({
                'id': c['id'], 'name': c['name'],
                'current': 'established', 'suggested': 'settled',
                'reason': f"max_strength={c['max_strength']}, age={age_days}d",
            })

    return eligible


def apply_confidence_decay(conn: sqlite3.Connection) -> list[dict]:
    """Apply decay rules. Returns list of demoted concepts.

    settled -> established after 90d unreferenced.
    established -> tentative after 60d unreferenced.
    """
    now = datetime.now(timezone.utc)
    demoted = []

    cutoff_90 = (now - timedelta(days=90)).isoformat()
    for c in conn.execute(
        "SELECT id, name FROM concepts "
        "WHERE confidence = 'settled' AND last_referenced < ?", (cutoff_90,)
    ).fetchall():
        conn.execute(
            "UPDATE concepts SET confidence = 'established', updated_at = ? WHERE id = ?",
            (now.isoformat(), c['id'])
        )
        demoted.append({'id': c['id'], 'name': c['name'],
                        'from': 'settled', 'to': 'established'})

    demoted_ids = {d['id'] for d in demoted}
    cutoff_60 = (now - timedelta(days=60)).isoformat()
    for c in conn.execute(
        "SELECT id, name FROM concepts "
        "WHERE confidence = 'established' AND last_referenced < ?", (cutoff_60,)
    ).fetchall():
        if c['id'] in demoted_ids:
            continue
        conn.execute(
            "UPDATE concepts SET confidence = 'tentative', updated_at = ? WHERE id = ?",
            (now.isoformat(), c['id'])
        )
        demoted.append({'id': c['id'], 'name': c['name'],
                        'from': 'established', 'to': 'tentative'})

    conn.commit()
    return demoted
