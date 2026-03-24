"""Tests for canonicalization and abbreviation handling."""

import json
from cortex_lib.canon import (
    canonicalize_cli, load_abbreviations, seed_abbreviations,
    add_normalization_rule,
)


def _insert_concept(db, name, aliases=None):
    """Helper: insert concept directly for canon tests."""
    now = "2026-01-01T00:00:00Z"
    db.execute(
        "INSERT INTO concepts (name, aliases, kind, confidence, privacy_level, "
        "first_seen, last_referenced, source_count, created_at, updated_at) "
        "VALUES (?, ?, 'topic', 'tentative', 'private', ?, ?, 0, ?, ?)",
        (name, json.dumps(aliases or []), now, now, now, now)
    )
    db.commit()
    return db.execute("SELECT id FROM concepts WHERE name = ?", (name,)).fetchone()['id']


def test_exact_match(db):
    _insert_concept(db, "Python")
    result = canonicalize_cli("Python", db)
    assert result is not None
    assert result['canonical_name'] == 'Python'
    assert result['match_type'] == 'exact'


def test_case_insensitive_match(db):
    _insert_concept(db, "Python")
    result = canonicalize_cli("python", db)
    assert result is not None
    assert result['canonical_name'] == 'Python'


def test_fuzzy_match_typo(db):
    _insert_concept(db, "kubernetes")
    result = canonicalize_cli("kubernates", db)
    assert result is not None
    assert result['canonical_name'] == 'kubernetes'
    assert result['match_type'] == 'fuzzy'


def test_fuzzy_match_plural(db):
    _insert_concept(db, "microservice")
    result = canonicalize_cli("microservices", db)
    assert result is not None
    assert result['canonical_name'] == 'microservice'


def test_fuzzy_no_match_unrelated(db):
    _insert_concept(db, "python")
    result = canonicalize_cli("javascript", db)
    assert result is None


def test_short_string_abbreviation_lookup(db):
    cid = _insert_concept(db, "kubernetes")
    add_normalization_rule(db, "k8s", cid)
    result = canonicalize_cli("k8s", db)
    assert result is not None
    assert result['canonical_name'] == 'kubernetes'
    assert result['match_type'] == 'normalization_rule'


def test_abbreviation_seeding(db, abbreviations_file):
    _insert_concept(db, "kubernetes")
    _insert_concept(db, "typescript")
    abbrevs = load_abbreviations(abbreviations_file)
    count = seed_abbreviations(db, abbrevs)
    assert count == 2  # k8s->kubernetes, ts->typescript

    result = canonicalize_cli("k8s", db)
    assert result is not None
    assert result['canonical_name'] == 'kubernetes'


def test_normalization_confidence_increments(db):
    """Core feedback loop: repeated variant lookups increase confidence."""
    cid = _insert_concept(db, "python")
    add_normalization_rule(db, "py", cid)
    add_normalization_rule(db, "py", cid)  # second time

    rule = db.execute(
        "SELECT confidence FROM normalization_rules WHERE variant = 'py'"
    ).fetchone()
    assert rule['confidence'] > 1.0


def test_alias_match(db):
    _insert_concept(db, "TypeScript", aliases=["TS", "ts-lang"])
    result = canonicalize_cli("ts-lang", db)
    assert result is not None
    assert result['canonical_name'] == 'TypeScript'
    assert result['match_type'] == 'alias'
