"""Correction primitives: correct (rename), undo-last, merge."""

import json
import sqlite3

from .canon import add_normalization_rule
from .db import utc_now


def correct_concept(conn: sqlite3.Connection, old_name: str, new_name: str) -> dict:
    """Rename a concept. Updates aliases, normalization rules, logs correction."""
    now = utc_now()

    concept = conn.execute(
        "SELECT id, name, aliases FROM concepts WHERE LOWER(name) = LOWER(?)",
        (old_name,)
    ).fetchone()
    if not concept:
        raise ValueError(f"Concept not found: '{old_name}'")

    concept_id = concept['id']

    existing = conn.execute(
        "SELECT id FROM concepts WHERE LOWER(name) = LOWER(?) AND id != ?",
        (new_name, concept_id)
    ).fetchone()
    if existing:
        raise ValueError(f"Concept '{new_name}' already exists. Use 'concepts merge' instead.")

    # Add old name to aliases
    aliases = json.loads(concept['aliases'])
    if old_name.lower() not in [a.lower() for a in aliases]:
        aliases.append(old_name)

    conn.execute(
        "UPDATE concepts SET name = ?, aliases = ?, updated_at = ? WHERE id = ?",
        (new_name, json.dumps(aliases), now, concept_id)
    )

    # Update normalization rules that point to this concept
    conn.execute(
        "UPDATE normalization_rules SET updated_at = ? WHERE canonical_id = ?",
        (now, concept_id)
    )
    add_normalization_rule(conn, old_name, concept_id, source='cli')

    # Log correction in extraction_log
    conn.execute(
        "INSERT INTO extraction_log (session_hash, timestamp, concepts_proposed, "
        "created_concepts, created_edges, rejected, weight, created_at) "
        "VALUES (?, ?, ?, ?, '[]', 0, 0, ?)",
        (f"correction:{old_name}->{new_name}", now,
         json.dumps([f"correct:{old_name}->{new_name}"]),
         json.dumps([new_name]), now)
    )
    conn.commit()
    return {'concept_id': concept_id, 'old_name': old_name, 'new_name': new_name}


def undo_last_extraction(conn: sqlite3.Connection) -> dict:
    """Revert the most recent extraction. Removes concepts, edges, normalization rules."""
    last = conn.execute(
        "SELECT * FROM extraction_log ORDER BY id DESC LIMIT 1"
    ).fetchone()
    if not last:
        raise ValueError("No extractions to undo.")
    if last['weight'] == 0:
        raise ValueError("Last entry is a correction, not an extraction. Cannot undo.")

    created_concepts = json.loads(last['created_concepts'])
    created_edges = json.loads(last['created_edges'])

    removed_concepts = []
    removed_edges = []

    # Remove created edges first
    for edge_info in created_edges:
        from_c = conn.execute(
            "SELECT id FROM concepts WHERE LOWER(name) = LOWER(?)", (edge_info['from'],)
        ).fetchone()
        to_c = conn.execute(
            "SELECT id FROM concepts WHERE LOWER(name) = LOWER(?)", (edge_info['to'],)
        ).fetchone()
        if from_c and to_c:
            conn.execute(
                "DELETE FROM concept_edges WHERE from_concept_id = ? "
                "AND to_concept_id = ? AND relation = ?",
                (from_c['id'], to_c['id'], edge_info['relation'])
            )
            removed_edges.append(edge_info)

    # Remove created concepts (only if source_count <= 1, meaning newly created)
    for concept_name in created_concepts:
        concept = conn.execute(
            "SELECT id, source_count FROM concepts WHERE LOWER(name) = LOWER(?)",
            (concept_name,)
        ).fetchone()
        if concept and concept['source_count'] <= 1:
            conn.execute(
                "DELETE FROM normalization_rules WHERE canonical_id = ?", (concept['id'],)
            )
            conn.execute(
                "DELETE FROM concept_sources WHERE concept_id = ?", (concept['id'],)
            )
            conn.execute("DELETE FROM concepts WHERE id = ?", (concept['id'],))
            removed_concepts.append(concept_name)

    conn.execute("DELETE FROM extraction_log WHERE id = ?", (last['id'],))
    conn.commit()
    return {
        'extraction_id': last['id'],
        'removed_concepts': removed_concepts,
        'removed_edges': removed_edges,
    }


def merge_concepts(conn: sqlite3.Connection, source_name: str, target_name: str) -> dict:
    """Merge source concept into target. Moves all edges, sources, and normalization rules."""
    now = utc_now()

    source = conn.execute(
        "SELECT id, name, aliases FROM concepts WHERE LOWER(name) = LOWER(?)",
        (source_name,)
    ).fetchone()
    target = conn.execute(
        "SELECT id, name, aliases FROM concepts WHERE LOWER(name) = LOWER(?)",
        (target_name,)
    ).fetchone()

    if not source:
        raise ValueError(f"Source concept not found: '{source_name}'")
    if not target:
        raise ValueError(f"Target concept not found: '{target_name}'")
    if source['id'] == target['id']:
        raise ValueError("Cannot merge a concept with itself.")

    source_id, target_id = source['id'], target['id']

    # Move sources
    conn.execute(
        "UPDATE concept_sources SET concept_id = ? WHERE concept_id = ?",
        (target_id, source_id)
    )

    # Recalculate source_count
    count = conn.execute(
        "SELECT COUNT(*) FROM concept_sources WHERE concept_id = ?", (target_id,)
    ).fetchone()[0]
    conn.execute(
        "UPDATE concepts SET source_count = ?, updated_at = ? WHERE id = ?",
        (count, now, target_id)
    )

    # Move edges (from source -> X becomes target -> X)
    for edge in conn.execute(
        "SELECT * FROM concept_edges WHERE from_concept_id = ?", (source_id,)
    ).fetchall():
        existing = conn.execute(
            "SELECT id, strength, history FROM concept_edges "
            "WHERE from_concept_id = ? AND to_concept_id = ? AND relation = ?",
            (target_id, edge['to_concept_id'], edge['relation'])
        ).fetchone()
        if existing:
            history = json.loads(existing['history']) + json.loads(edge['history'])
            conn.execute(
                "UPDATE concept_edges SET strength = ?, history = ?, "
                "last_strengthened = ? WHERE id = ?",
                (existing['strength'] + edge['strength'], json.dumps(history),
                 now, existing['id'])
            )
            conn.execute("DELETE FROM concept_edges WHERE id = ?", (edge['id'],))
        else:
            conn.execute(
                "UPDATE concept_edges SET from_concept_id = ? WHERE id = ?",
                (target_id, edge['id'])
            )

    # Move edges (X -> source becomes X -> target)
    for edge in conn.execute(
        "SELECT * FROM concept_edges WHERE to_concept_id = ?", (source_id,)
    ).fetchall():
        existing = conn.execute(
            "SELECT id, strength, history FROM concept_edges "
            "WHERE from_concept_id = ? AND to_concept_id = ? AND relation = ?",
            (edge['from_concept_id'], target_id, edge['relation'])
        ).fetchone()
        if existing:
            history = json.loads(existing['history']) + json.loads(edge['history'])
            conn.execute(
                "UPDATE concept_edges SET strength = ?, history = ?, "
                "last_strengthened = ? WHERE id = ?",
                (existing['strength'] + edge['strength'], json.dumps(history),
                 now, existing['id'])
            )
            conn.execute("DELETE FROM concept_edges WHERE id = ?", (edge['id'],))
        else:
            conn.execute(
                "UPDATE concept_edges SET to_concept_id = ? WHERE id = ?",
                (target_id, edge['id'])
            )

    # Move normalization rules pointing to source -> target
    conn.execute(
        "UPDATE normalization_rules SET canonical_id = ?, updated_at = ? "
        "WHERE canonical_id = ?",
        (target_id, now, source_id)
    )
    add_normalization_rule(conn, source_name, target_id, source='cli')

    # Merge aliases
    source_aliases = json.loads(source['aliases'])
    target_aliases = json.loads(target['aliases'])
    all_aliases = list(set(target_aliases + source_aliases + [source_name]))
    all_aliases = [a for a in all_aliases if a.lower() != target['name'].lower()]
    conn.execute(
        "UPDATE concepts SET aliases = ?, updated_at = ? WHERE id = ?",
        (json.dumps(all_aliases), now, target_id)
    )

    # Delete source (cascades handle any remaining references)
    conn.execute("DELETE FROM concepts WHERE id = ?", (source_id,))
    conn.commit()
    return {'source': source_name, 'target': target['name'], 'target_id': target_id}
