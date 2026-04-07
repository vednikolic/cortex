"""Tests for re-explanation recording and stats."""

import json
import pytest
from datetime import datetime, timezone, timedelta

from cortex_lib.capture import record_re_explanation, re_explanation_stats
from cortex_lib.ops import upsert_concept


def _setup_concept_and_session(db, concept_name='caching',
                                session_hash='sess1'):
    """Helper: insert a concept and a session for FK references."""
    upsert_concept(db, concept_name, kind='pattern')
    db.execute(
        "INSERT INTO sessions (session_hash, timestamp, project, status) "
        "VALUES (?, ?, 'project-alpha', 'raw')",
        (session_hash, datetime.now(timezone.utc).isoformat())
    )
    db.commit()


def test_record_re_explanation_basic(db):
    """Records a re-explanation with correct fields."""
    _setup_concept_and_session(db)
    result = record_re_explanation(
        db,
        concept_name='caching',
        session_hash='sess1',
        detection_method='save',
        prior_count=5,
        prior_confidence='established',
        was_in_brief=True,
        failure_type='surfacing_miss',
    )
    assert result['concept'] == 'caching'
    assert result['failure_type'] == 'surfacing_miss'
    assert result['id'] is not None


def test_record_re_explanation_capture_miss(db):
    """Capture miss is the default failure type."""
    _setup_concept_and_session(db)
    result = record_re_explanation(
        db,
        concept_name='caching',
        session_hash='sess1',
        detection_method='reflect',
        prior_count=3,
        prior_confidence='established',
    )
    assert result['failure_type'] == 'capture_miss'


def test_record_re_explanation_concept_not_found(db):
    """Raises ValueError for nonexistent concept."""
    db.execute(
        "INSERT INTO sessions (session_hash, timestamp, project, status) "
        "VALUES ('sess1', '2026-04-07T00:00:00Z', 'p', 'raw')"
    )
    db.commit()
    with pytest.raises(ValueError, match="Concept not found"):
        record_re_explanation(
            db, concept_name='nonexistent', session_hash='sess1',
            detection_method='save', prior_count=1,
            prior_confidence='tentative',
        )


def test_record_re_explanation_session_not_found(db):
    """Raises ValueError for nonexistent session."""
    upsert_concept(db, 'caching', kind='pattern')
    with pytest.raises(ValueError, match="Session not found"):
        record_re_explanation(
            db, concept_name='caching', session_hash='nonexistent',
            detection_method='save', prior_count=1,
            prior_confidence='tentative',
        )


def test_record_re_explanation_invalid_method(db):
    """Raises ValueError for invalid detection method."""
    _setup_concept_and_session(db)
    with pytest.raises(ValueError, match="Invalid detection_method"):
        record_re_explanation(
            db, concept_name='caching', session_hash='sess1',
            detection_method='manual', prior_count=1,
            prior_confidence='tentative',
        )


def test_record_re_explanation_invalid_failure_type(db):
    """Raises ValueError for invalid failure type."""
    _setup_concept_and_session(db)
    with pytest.raises(ValueError, match="Invalid failure_type"):
        record_re_explanation(
            db, concept_name='caching', session_hash='sess1',
            detection_method='save', prior_count=1,
            prior_confidence='tentative', failure_type='unknown',
        )


def test_re_explanation_stats_empty(db):
    """Stats on empty DB return zeros."""
    stats = re_explanation_stats(db)
    assert stats['total'] == 0
    assert stats['surfacing_miss'] == 0
    assert stats['capture_miss'] == 0
    assert stats['top_concepts'] == []


def test_re_explanation_stats_decomposed(db):
    """Stats decompose correctly by failure type."""
    _setup_concept_and_session(db, 'api-design', 'sess1')
    _setup_concept_and_session(db, 'retry-pattern', 'sess2')

    record_re_explanation(
        db, concept_name='api-design', session_hash='sess1',
        detection_method='save', prior_count=5,
        prior_confidence='established',
        was_in_brief=True, failure_type='surfacing_miss',
    )
    record_re_explanation(
        db, concept_name='retry-pattern', session_hash='sess2',
        detection_method='reflect', prior_count=3,
        prior_confidence='established',
        failure_type='capture_miss',
    )

    stats = re_explanation_stats(db)
    assert stats['total'] == 2
    assert stats['surfacing_miss'] == 1
    assert stats['capture_miss'] == 1
    assert len(stats['top_concepts']) == 2


def test_re_explanation_stats_respects_days_filter(db):
    """Stats only count re-explanations within the date window."""
    _setup_concept_and_session(db)
    # Insert an old re-explanation directly
    old_ts = (datetime.now(timezone.utc) - timedelta(days=60)).isoformat()
    db.execute(
        "INSERT INTO re_explanations (concept_id, session_hash, timestamp, "
        "prior_source_count, prior_confidence, failure_type, detection_method) "
        "VALUES (1, 'sess1', ?, 3, 'established', 'capture_miss', 'save')",
        (old_ts,)
    )
    db.commit()

    stats = re_explanation_stats(db, days=30)
    assert stats['total'] == 0  # Outside the 30-day window


def test_re_explanation_was_in_brief_stored(db):
    """was_in_brief flag is correctly persisted."""
    _setup_concept_and_session(db)
    record_re_explanation(
        db, concept_name='caching', session_hash='sess1',
        detection_method='save', prior_count=5,
        prior_confidence='established',
        was_in_brief=True, failure_type='surfacing_miss',
    )
    row = db.execute(
        "SELECT was_in_brief FROM re_explanations WHERE id = 1"
    ).fetchone()
    assert row['was_in_brief'] == 1
