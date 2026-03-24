"""CRUD operations for concepts graph tables."""

import json
import sqlite3
from datetime import datetime, timezone
from typing import Optional

from .canon import canonicalize_cli, add_normalization_rule
from .db import VALID_RELATIONS, VALID_KINDS


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def upsert_concept(conn: sqlite3.Connection, name: str, kind: str = 'topic',
                    aliases: Optional[list[str]] = None, project: str = '',
                    session_hash: str = '', weight: int = 1) -> dict:
    """Upsert a concept. Canonicalizes first. Returns {concept_id, name, action}."""
    if kind not in VALID_KINDS:
        raise ValueError(f"Invalid kind '{kind}'. Must be one of: {', '.join(sorted(VALID_KINDS))}")

    now = _now()
    match = canonicalize_cli(name, conn)

    if match:
        concept_id = match['concept_id']
        conn.execute(
            "UPDATE concepts SET last_referenced = ?, source_count = source_count + 1, "
            "updated_at = ? WHERE id = ?",
            (now, now, concept_id)
        )
        if session_hash:
            conn.execute(
                "INSERT INTO concept_sources (concept_id, session_hash, project, timestamp, weight) "
                "VALUES (?, ?, ?, ?, ?)",
                (concept_id, session_hash, project, now, weight)
            )
        if match['match_type'] == 'fuzzy':
            add_normalization_rule(conn, name, concept_id)
        conn.commit()
        return {'concept_id': concept_id, 'name': match['canonical_name'], 'action': 'updated'}

    cursor = conn.execute(
        "INSERT INTO concepts (name, aliases, kind, confidence, privacy_level, "
        "first_seen, last_referenced, source_count, created_at, updated_at) "
        "VALUES (?, ?, ?, 'tentative', 'private', ?, ?, 1, ?, ?)",
        (name, json.dumps(aliases or []), kind, now, now, now, now)
    )
    concept_id = cursor.lastrowid

    if session_hash:
        conn.execute(
            "INSERT INTO concept_sources (concept_id, session_hash, project, timestamp, weight) "
            "VALUES (?, ?, ?, ?, ?)",
            (concept_id, session_hash, project, now, weight)
        )
    conn.commit()
    return {'concept_id': concept_id, 'name': name, 'action': 'created'}


def add_edge(conn: sqlite3.Connection, from_name: str, to_name: str,
             relation: str, session_hash: str = '') -> dict:
    """Add or strengthen an edge between two concepts."""
    if relation not in VALID_RELATIONS:
        raise ValueError(
            f"Invalid relation '{relation}'. Must be one of: {', '.join(sorted(VALID_RELATIONS))}"
        )

    now = _now()
    from_match = canonicalize_cli(from_name, conn)
    to_match = canonicalize_cli(to_name, conn)

    if not from_match:
        raise ValueError(f"Concept not found: '{from_name}'")
    if not to_match:
        raise ValueError(f"Concept not found: '{to_name}'")

    from_id = from_match['concept_id']
    to_id = to_match['concept_id']

    existing = conn.execute(
        "SELECT id, strength, history FROM concept_edges "
        "WHERE from_concept_id = ? AND to_concept_id = ? AND relation = ?",
        (from_id, to_id, relation)
    ).fetchone()

    if existing:
        history = json.loads(existing['history'])
        history.append(now)
        new_strength = existing['strength'] + 1
        conn.execute(
            "UPDATE concept_edges SET strength = ?, history = ?, "
            "last_strengthened = ? WHERE id = ?",
            (new_strength, json.dumps(history), now, existing['id'])
        )
        conn.commit()
        return {
            'edge_id': existing['id'],
            'from': from_match['canonical_name'],
            'to': to_match['canonical_name'],
            'relation': relation,
            'strength': new_strength,
            'action': 'strengthened',
        }

    history = json.dumps([now])
    cursor = conn.execute(
        "INSERT INTO concept_edges (from_concept_id, to_concept_id, relation, "
        "strength, confidence, history, first_seen, last_strengthened) "
        "VALUES (?, ?, ?, 1, 'tentative', ?, ?, ?)",
        (from_id, to_id, relation, history, now, now)
    )
    conn.commit()
    return {
        'edge_id': cursor.lastrowid,
        'from': from_match['canonical_name'],
        'to': to_match['canonical_name'],
        'relation': relation,
        'strength': 1,
        'action': 'created',
    }


def query_concept(conn: sqlite3.Connection, name: str) -> Optional[dict]:
    """Query a concept with edges and sources."""
    match = canonicalize_cli(name, conn)
    if not match:
        return None

    concept = conn.execute(
        "SELECT * FROM concepts WHERE id = ?", (match['concept_id'],)
    ).fetchone()

    edges = conn.execute(
        "SELECT e.*, c1.name as from_name, c2.name as to_name "
        "FROM concept_edges e "
        "JOIN concepts c1 ON e.from_concept_id = c1.id "
        "JOIN concepts c2 ON e.to_concept_id = c2.id "
        "WHERE e.from_concept_id = ? OR e.to_concept_id = ?",
        (match['concept_id'], match['concept_id'])
    ).fetchall()

    sources = conn.execute(
        "SELECT * FROM concept_sources WHERE concept_id = ? ORDER BY timestamp DESC",
        (match['concept_id'],)
    ).fetchall()

    return {
        'concept': dict(concept),
        'edges': [dict(e) for e in edges],
        'sources': [dict(s) for s in sources],
        'match_type': match['match_type'],
    }


def log_extraction(conn: sqlite3.Connection, session_hash: str,
                   concepts_proposed: list[str], created_concepts: list[str],
                   created_edges: list[dict], rejected_count: int,
                   weight: int) -> int:
    """Log an extraction event. Returns extraction_log id."""
    now = _now()
    cursor = conn.execute(
        "INSERT INTO extraction_log (session_hash, timestamp, concepts_proposed, "
        "created_concepts, created_edges, rejected, weight, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (session_hash, now, json.dumps(concepts_proposed), json.dumps(created_concepts),
         json.dumps(created_edges), rejected_count, weight, now)
    )
    conn.commit()
    return cursor.lastrowid
