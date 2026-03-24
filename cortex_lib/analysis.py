"""Graph analysis: shared, stale, hot, graph summary, weight stats, confidence decay."""

import sqlite3
from datetime import datetime, timezone, timedelta


def shared_concepts(conn: sqlite3.Connection) -> list[dict]:
    """Concepts appearing in 2+ projects."""
    rows = conn.execute("""
        SELECT c.id, c.name, c.kind, c.confidence,
               GROUP_CONCAT(DISTINCT cs.project) as projects,
               COUNT(DISTINCT cs.project) as project_count
        FROM concepts c
        JOIN concept_sources cs ON c.id = cs.concept_id
        WHERE cs.project != ''
        GROUP BY c.id
        HAVING COUNT(DISTINCT cs.project) >= 2
        ORDER BY project_count DESC, c.name
    """).fetchall()
    return [dict(r) for r in rows]


def stale_concepts(conn: sqlite3.Connection, days: int = 60) -> list[dict]:
    """Concepts not referenced in N days."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    rows = conn.execute("""
        SELECT id, name, kind, confidence, last_referenced
        FROM concepts WHERE last_referenced < ?
        ORDER BY last_referenced ASC
    """, (cutoff,)).fetchall()
    return [dict(r) for r in rows]


def hot_concepts(conn: sqlite3.Connection, limit: int = 10) -> list[dict]:
    """Most-referenced concepts by source_count + edge count."""
    rows = conn.execute("""
        SELECT c.id, c.name, c.kind, c.confidence, c.source_count,
               COUNT(DISTINCT e.id) as edge_count
        FROM concepts c
        LEFT JOIN concept_edges e
            ON c.id = e.from_concept_id OR c.id = e.to_concept_id
        GROUP BY c.id
        ORDER BY c.source_count + COUNT(DISTINCT e.id) DESC
        LIMIT ?
    """, (limit,)).fetchall()
    return [dict(r) for r in rows]


def graph_summary(conn: sqlite3.Connection) -> dict:
    """Graph-level statistics."""
    concept_count = conn.execute("SELECT COUNT(*) FROM concepts").fetchone()[0]
    edge_count = conn.execute("SELECT COUNT(*) FROM concept_edges").fetchone()[0]
    source_count = conn.execute("SELECT COUNT(*) FROM concept_sources").fetchone()[0]
    rule_count = conn.execute("SELECT COUNT(*) FROM normalization_rules").fetchone()[0]
    extraction_count = conn.execute("SELECT COUNT(*) FROM extraction_log").fetchone()[0]
    project_count = conn.execute(
        "SELECT COUNT(DISTINCT project) FROM concept_sources WHERE project != ''"
    ).fetchone()[0]

    avg_edges = edge_count / concept_count if concept_count > 0 else 0

    confidence_dist = {}
    for row in conn.execute(
        "SELECT confidence, COUNT(*) as cnt FROM concepts GROUP BY confidence"
    ).fetchall():
        confidence_dist[row['confidence']] = row['cnt']

    return {
        'concepts': concept_count,
        'edges': edge_count,
        'sources': source_count,
        'normalization_rules': rule_count,
        'extractions': extraction_count,
        'projects': project_count,
        'avg_edges_per_concept': round(avg_edges, 2),
        'confidence_distribution': confidence_dist,
    }


def weight_stats(conn: sqlite3.Connection) -> dict:
    """Extraction weight distribution for revision protocol (req 2.5)."""
    rows = conn.execute("""
        SELECT weight, COUNT(*) as cnt,
               AVG(json_array_length(created_concepts)) as avg_concepts,
               AVG(rejected) as avg_rejected
        FROM extraction_log
        GROUP BY weight ORDER BY weight
    """).fetchall()
    return {
        'by_weight': [dict(r) for r in rows],
        'total_extractions': sum(r['cnt'] for r in rows),
    }


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
        demoted.append({'id': c['id'], 'name': c['name'], 'from': 'settled', 'to': 'established'})

    # Exclude concepts just demoted above to prevent double-demotion in one pass
    demoted_ids = {d['id'] for d in demoted}
    cutoff_60 = (now - timedelta(days=60)).isoformat()
    for c in conn.execute(
        "SELECT id, name FROM concepts "
        "WHERE confidence = 'established' AND last_referenced < ?", (cutoff_60,)
    ).fetchall():
        if c['id'] in demoted_ids:
            continue  # already demoted this pass
        conn.execute(
            "UPDATE concepts SET confidence = 'tentative', updated_at = ? WHERE id = ?",
            (now.isoformat(), c['id'])
        )
        demoted.append({'id': c['id'], 'name': c['name'], 'from': 'established', 'to': 'tentative'})

    conn.commit()
    return demoted
