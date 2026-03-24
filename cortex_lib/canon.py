"""Two-tier concept canonicalization with abbreviation handling.

Tier 1 (CLI path): difflib fuzzy match + short-string normalization_rules lookup.
Tier 2 (LLM path in /save): semantic match. Not implemented here; handled by the skill.
Both tiers write to normalization_rules on match.
"""

import difflib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

FUZZY_THRESHOLD = 0.8
SHORT_STRING_MAX = 4


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_abbreviations(path: Optional[Path] = None) -> dict[str, str]:
    """Load bundled abbreviation pairs from JSON file."""
    if path is None:
        path = Path(__file__).resolve().parent.parent / 'abbreviations.json'
    if not path.exists():
        return {}
    with open(path) as f:
        return json.load(f)


def seed_abbreviations(conn: sqlite3.Connection, abbreviations: dict[str, str]) -> int:
    """Seed normalization_rules from abbreviation dict. Returns count of new rules."""
    now = _now()
    added = 0
    for abbrev, full_name in abbreviations.items():
        row = conn.execute(
            "SELECT id FROM concepts WHERE LOWER(name) = LOWER(?)", (full_name,)
        ).fetchone()
        if row is None:
            continue
        existing = conn.execute(
            "SELECT id FROM normalization_rules WHERE LOWER(variant) = LOWER(?)",
            (abbrev,)
        ).fetchone()
        if existing is None:
            conn.execute(
                "INSERT INTO normalization_rules "
                "(variant, canonical_id, confidence, source, created_at, updated_at) "
                "VALUES (?, ?, 1.0, 'cli', ?, ?)",
                (abbrev.lower(), row['id'], now, now)
            )
            added += 1
    conn.commit()
    return added


def canonicalize_cli(name: str, conn: sqlite3.Connection) -> Optional[dict]:
    """Tier 1 canonicalization (CLI path).

    Returns dict {concept_id, canonical_name, match_type, confidence} or None.
    Match priority: normalization_rule (short strings) > exact > alias > fuzzy.
    """
    name_lower = name.lower().strip()

    # Short string: check normalization_rules first (abbreviation routing)
    if len(name_lower) <= SHORT_STRING_MAX:
        rule = conn.execute(
            "SELECT canonical_id, confidence FROM normalization_rules "
            "WHERE LOWER(variant) = ?", (name_lower,)
        ).fetchone()
        if rule:
            concept = conn.execute(
                "SELECT id, name FROM concepts WHERE id = ?", (rule['canonical_id'],)
            ).fetchone()
            if concept:
                return {
                    'concept_id': concept['id'],
                    'canonical_name': concept['name'],
                    'match_type': 'normalization_rule',
                    'confidence': rule['confidence'],
                }

    # Exact match (case-insensitive)
    exact = conn.execute(
        "SELECT id, name FROM concepts WHERE LOWER(name) = ?", (name_lower,)
    ).fetchone()
    if exact:
        return {
            'concept_id': exact['id'],
            'canonical_name': exact['name'],
            'match_type': 'exact',
            'confidence': 1.0,
        }

    # Alias match
    all_concepts = conn.execute("SELECT id, name, aliases FROM concepts").fetchall()
    for concept in all_concepts:
        aliases = json.loads(concept['aliases'])
        for alias in aliases:
            if alias.lower() == name_lower:
                return {
                    'concept_id': concept['id'],
                    'canonical_name': concept['name'],
                    'match_type': 'alias',
                    'confidence': 1.0,
                }

    # Fuzzy match (difflib)
    concept_names = [c['name'] for c in all_concepts]
    name_map = {n.lower(): n for n in concept_names}
    matches = difflib.get_close_matches(
        name_lower, list(name_map.keys()), n=1, cutoff=FUZZY_THRESHOLD
    )
    if matches:
        matched_original = name_map[matches[0]]
        matched_concept = next(c for c in all_concepts if c['name'] == matched_original)
        ratio = difflib.SequenceMatcher(None, name_lower, matches[0]).ratio()
        return {
            'concept_id': matched_concept['id'],
            'canonical_name': matched_concept['name'],
            'match_type': 'fuzzy',
            'confidence': ratio,
        }

    return None


def add_normalization_rule(conn: sqlite3.Connection, variant: str,
                           canonical_id: int, source: str = 'cli') -> None:
    """Add or update a normalization rule. Increments confidence on repeat."""
    now = _now()
    existing = conn.execute(
        "SELECT id, confidence FROM normalization_rules WHERE LOWER(variant) = ?",
        (variant.lower(),)
    ).fetchone()

    if existing:
        conn.execute(
            "UPDATE normalization_rules SET confidence = confidence + 0.1, "
            "canonical_id = ?, updated_at = ? WHERE id = ?",
            (canonical_id, now, existing['id'])
        )
    else:
        conn.execute(
            "INSERT INTO normalization_rules "
            "(variant, canonical_id, confidence, source, created_at, updated_at) "
            "VALUES (?, ?, 1.0, ?, ?, ?)",
            (variant.lower(), canonical_id, source, now, now)
        )
    conn.commit()
