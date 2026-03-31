"""Generate reflect-context.json from concepts graph data.

Provides structured graph data for /reflect to consume.
Content-hash based on concepts.db mtime enables freshness validation.
"""

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .db import connect, find_db_path
from .analysis import (
    shared_concepts, stale_concepts, hot_concepts,
    graph_summary, weight_stats,
)


def generate_reflect_context(db_path: Optional[Path] = None) -> dict:
    """Generate reflect context data from the concepts graph."""
    if db_path is None:
        db_path = find_db_path()

    conn = connect(db_path)
    try:
        mtime = str(os.path.getmtime(db_path))
        content_hash = hashlib.md5(mtime.encode()).hexdigest()

        return {
            'generated_at': datetime.now(timezone.utc).isoformat(),
            'content_hash': content_hash,
            'db_path': str(db_path),
            'shared_concepts': shared_concepts(conn),
            'hot_concepts': hot_concepts(conn),
            'stale_concepts': stale_concepts(conn),
            'graph_summary': graph_summary(conn),
            'stats': weight_stats(conn),
        }
    finally:
        conn.close()


def validate_content_hash(reflect_context: dict, db_path: Optional[Path] = None) -> bool:
    """Check if reflect-context.json is still fresh relative to concepts.db."""
    if db_path is None:
        db_path = find_db_path()
    if not db_path.exists():
        return False
    mtime = str(os.path.getmtime(db_path))
    current_hash = hashlib.md5(mtime.encode()).hexdigest()
    return reflect_context.get('content_hash') == current_hash


def write_reflect_context(output_path: Optional[Path] = None,
                          db_path: Optional[Path] = None) -> Path:
    """Write reflect-context.json to workspace root."""
    if db_path is None:
        db_path = find_db_path()
    if output_path is None:
        output_path = db_path.parent / 'reflect-context.json'

    data = generate_reflect_context(db_path)
    with open(output_path, 'w') as f:
        json.dump(data, f, indent=2)
    return output_path


if __name__ == '__main__':
    import sys
    db = Path(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[1] == '--db' else None
    path = write_reflect_context(db_path=db)
    print(f"Written: {path}")
