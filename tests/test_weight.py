"""Session weight computation tests."""

from cortex_lib.weight import compute_session_weight, extraction_cap


def test_minimum_weight():
    assert compute_session_weight() == 1


def test_maximum_weight():
    assert compute_session_weight(token_count=10000, concepts=5, decisions=3, friction=2) == 5


def test_token_count_threshold():
    assert compute_session_weight(token_count=5000) == 1  # not >5000
    assert compute_session_weight(token_count=5001) == 2


def test_concepts_threshold():
    assert compute_session_weight(concepts=1) == 1
    assert compute_session_weight(concepts=2) == 2


def test_decisions_threshold():
    assert compute_session_weight(decisions=0) == 1
    assert compute_session_weight(decisions=1) == 2


def test_friction_threshold():
    assert compute_session_weight(friction=0) == 1
    assert compute_session_weight(friction=1) == 2


def test_all_signals():
    w = compute_session_weight(token_count=6000, concepts=3, decisions=1, friction=1)
    assert w == 5


def test_cap_at_five():
    w = compute_session_weight(token_count=99999, concepts=99, decisions=99, friction=99)
    assert w == 5


def test_extraction_cap_low_weight():
    assert extraction_cap(1) == 3
    assert extraction_cap(2) == 3


def test_extraction_cap_medium_weight():
    assert extraction_cap(3) == 5


def test_extraction_cap_high_weight():
    assert extraction_cap(4) == 8
    assert extraction_cap(5) == 8
