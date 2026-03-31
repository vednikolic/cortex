"""Confidence lifecycle tests: promotion, decay, and round-trips."""

import pytest
from datetime import datetime, timezone, timedelta
from cortex_lib.db import utc_now
from cortex_lib.ops import upsert_concept
from cortex_lib.confidence import (
    promote_concept, apply_confidence_decay, check_promotion_eligibility,
)


def test_promote_tentative_to_established(db):
    """Manual promotion from tentative to established."""
    upsert_concept(db, "python", kind="tool")
    result = promote_concept(db, "python", "established")
    assert result['new_confidence'] == 'established'
    row = db.execute("SELECT confidence FROM concepts WHERE name = 'python'").fetchone()
    assert row['confidence'] == 'established'


def test_promote_established_to_settled(db):
    """Manual promotion from established to settled."""
    upsert_concept(db, "python", kind="tool")
    promote_concept(db, "python", "established")
    result = promote_concept(db, "python", "settled")
    assert result['new_confidence'] == 'settled'


def test_promote_invalid_level_raises(db):
    upsert_concept(db, "python")
    with pytest.raises(ValueError, match="Invalid"):
        promote_concept(db, "python", "bogus")


def test_promote_downgrade_raises(db):
    """Cannot promote downward."""
    upsert_concept(db, "python")
    promote_concept(db, "python", "settled")
    with pytest.raises(ValueError, match="Cannot demote"):
        promote_concept(db, "python", "tentative")


def test_promote_unknown_concept_raises(db):
    with pytest.raises(ValueError, match="not found"):
        promote_concept(db, "nonexistent", "established")


def test_check_eligibility_by_sources(db):
    """3+ sources qualifies tentative for established."""
    for i in range(3):
        upsert_concept(db, "python", session_hash=f"s{i}", project="p1")
    result = check_promotion_eligibility(db)
    eligible = [e for e in result if e['name'] == 'python']
    assert len(eligible) == 1
    assert eligible[0]['suggested'] == 'established'


def test_check_eligibility_by_projects(db):
    """2+ projects qualifies tentative for established."""
    upsert_concept(db, "python", session_hash="s1", project="p1")
    upsert_concept(db, "python", session_hash="s2", project="p2")
    result = check_promotion_eligibility(db)
    eligible = [e for e in result if e['name'] == 'python']
    assert len(eligible) == 1
    assert eligible[0]['suggested'] == 'established'


def test_check_eligibility_established_to_settled(db):
    """strength>=5 and age>=30d qualifies established for settled."""
    upsert_concept(db, "python")
    promote_concept(db, "python", "established")
    # Set first_seen to 31 days ago
    old_date = (datetime.now(timezone.utc) - timedelta(days=31)).isoformat()
    db.execute("UPDATE concepts SET first_seen = ? WHERE name = 'python'", (old_date,))
    # Create edges with total strength >= 5
    upsert_concept(db, "sqlite")
    from cortex_lib.ops import add_edge
    for _ in range(5):
        add_edge(db, "python", "sqlite", "related-to")
    db.commit()
    result = check_promotion_eligibility(db)
    eligible = [e for e in result if e['name'] == 'python']
    assert len(eligible) == 1
    assert eligible[0]['suggested'] == 'settled'


def test_decay_settled_to_established(db):
    upsert_concept(db, "python")
    promote_concept(db, "python", "settled")
    old_date = (datetime.now(timezone.utc) - timedelta(days=91)).isoformat()
    db.execute("UPDATE concepts SET last_referenced = ? WHERE name = 'python'", (old_date,))
    db.commit()
    demoted = apply_confidence_decay(db)
    assert any(d['name'] == 'python' and d['to'] == 'established' for d in demoted)


def test_decay_established_to_tentative(db):
    upsert_concept(db, "python")
    promote_concept(db, "python", "established")
    old_date = (datetime.now(timezone.utc) - timedelta(days=61)).isoformat()
    db.execute("UPDATE concepts SET last_referenced = ? WHERE name = 'python'", (old_date,))
    db.commit()
    demoted = apply_confidence_decay(db)
    assert any(d['name'] == 'python' and d['to'] == 'tentative' for d in demoted)


def test_no_double_demotion_in_single_pass(db):
    """settled should not decay past established in one pass."""
    upsert_concept(db, "python")
    promote_concept(db, "python", "settled")
    old_date = (datetime.now(timezone.utc) - timedelta(days=91)).isoformat()
    db.execute("UPDATE concepts SET last_referenced = ? WHERE name = 'python'", (old_date,))
    db.commit()
    demoted = apply_confidence_decay(db)
    python_demotions = [d for d in demoted if d['name'] == 'python']
    assert len(python_demotions) == 1
    assert python_demotions[0]['to'] == 'established'
