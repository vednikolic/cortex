"""Graph export/import for cross-device transfer and backup."""

import json
import sqlite3
from typing import Any


def export_graph(conn: sqlite3.Connection) -> dict[str, Any]:
    """Export full graph to a stable JSON-serializable dict.

    Includes concepts, edges, and normalization rules.
    Does not include extraction_log (audit trail stays local).
    """
    concepts = []
    for row in conn.execute(
        "SELECT name, aliases, kind, confidence, privacy_level, "
        "first_seen, last_referenced, source_count, created_at "
        "FROM concepts ORDER BY name"
    ).fetchall():
        concepts.append({
            "name": row[0],
            "aliases": json.loads(row[1]) if row[1] else [],
            "kind": row[2],
            "confidence": row[3],
            "privacy_level": row[4],
            "first_seen": row[5],
            "last_referenced": row[6],
            "source_count": row[7],
            "created_at": row[8],
        })

    edges = []
    for row in conn.execute(
        "SELECT c1.name, c2.name, e.relation, e.strength, e.confidence, "
        "e.history, e.first_seen, e.last_strengthened "
        "FROM concept_edges e "
        "JOIN concepts c1 ON e.from_concept_id = c1.id "
        "JOIN concepts c2 ON e.to_concept_id = c2.id "
        "ORDER BY c1.name, c2.name, e.relation"
    ).fetchall():
        edges.append({
            "from": row[0],
            "to": row[1],
            "relation": row[2],
            "strength": row[3],
            "confidence": row[4],
            "history": json.loads(row[5]) if row[5] else [],
            "first_seen": row[6],
            "last_strengthened": row[7],
        })

    rules = []
    for row in conn.execute(
        "SELECT n.variant, c.name, n.confidence, n.source "
        "FROM normalization_rules n "
        "JOIN concepts c ON n.canonical_id = c.id "
        "ORDER BY n.variant"
    ).fetchall():
        rules.append({
            "variant": row[0],
            "canonical": row[1],
            "confidence": row[2],
            "source": row[3],
        })

    return {
        "version": "cortex-export-v1",
        "concepts": concepts,
        "edges": edges,
        "normalization_rules": rules,
    }


def import_graph(
    conn: sqlite3.Connection,
    data: dict[str, Any],
) -> dict[str, int]:
    """Import graph data with merge semantics.

    Concepts: upsert by name (updates last_referenced, increments source_count).
    Edges: create or strengthen (increment strength, append to history).
    Normalization rules: insert or skip if variant already mapped.

    Returns counts of created/updated entities.
    """
    if data.get("version") != "cortex-export-v1":
        raise ValueError(f"Unsupported export version: {data.get('version')}")

    from .ops import upsert_concept, add_edge

    stats = {
        "concepts_created": 0,
        "concepts_updated": 0,
        "edges_created": 0,
        "edges_strengthened": 0,
        "rules_added": 0,
    }

    for c in data.get("concepts", []):
        existing = conn.execute(
            "SELECT id FROM concepts WHERE name = ?", (c["name"],)
        ).fetchone()

        upsert_concept(conn, c["name"], kind=c.get("kind"))

        if c.get("aliases"):
            current = conn.execute(
                "SELECT aliases FROM concepts WHERE name = ?", (c["name"],)
            ).fetchone()
            merged = list(set(
                (json.loads(current[0]) if current[0] else []) + c["aliases"]
            ))
            conn.execute(
                "UPDATE concepts SET aliases = ? WHERE name = ?",
                (json.dumps(merged), c["name"])
            )
            conn.commit()

        if existing:
            stats["concepts_updated"] += 1
        else:
            stats["concepts_created"] += 1

    for e in data.get("edges", []):
        existing = conn.execute(
            "SELECT strength FROM concept_edges "
            "WHERE from_concept_id = (SELECT id FROM concepts WHERE name = ?) "
            "AND to_concept_id = (SELECT id FROM concepts WHERE name = ?) "
            "AND relation = ?",
            (e["from"], e["to"], e["relation"])
        ).fetchone()

        add_edge(conn, e["from"], e["to"], e["relation"])

        if existing:
            stats["edges_strengthened"] += 1
        else:
            stats["edges_created"] += 1

    for r in data.get("normalization_rules", []):
        exists = conn.execute(
            "SELECT 1 FROM normalization_rules WHERE variant = ?",
            (r["variant"],)
        ).fetchone()
        if not exists:
            conn.execute(
                "INSERT INTO normalization_rules (variant, canonical_id, confidence, source, created_at, updated_at) "
                "VALUES (?, (SELECT id FROM concepts WHERE name = ?), ?, ?, datetime('now'), datetime('now'))",
                (r["variant"], r["canonical"], r.get("confidence", 1.0), r.get("source", "import"))
            )
            conn.commit()
            stats["rules_added"] += 1

    return stats
