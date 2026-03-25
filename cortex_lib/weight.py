"""Session weight computation.

Formula: weight = 1 + (token_count>5000) + (concepts>=2) + (decisions>=1) + (friction>=1)
Capped at 5.

After 20 extraction_log entries, `concepts stats --weights` surfaces threshold
distributions so the user can adjust.
"""


def compute_session_weight(token_count: int = 0, concepts: int = 0,
                            decisions: int = 0, friction: int = 0) -> int:
    """Compute session weight. Returns 1-5."""
    weight = 1
    if token_count > 5000:
        weight += 1
    if concepts >= 2:
        weight += 1
    if decisions >= 1:
        weight += 1
    if friction >= 1:
        weight += 1
    return min(weight, 5)


def extraction_cap(weight: int) -> int:
    """Max concepts to extract based on session weight.

    Weight 1-2: up to 3. Weight 3: up to 5. Weight 4-5: up to 8.
    """
    if weight <= 2:
        return 3
    if weight == 3:
        return 5
    return 8
