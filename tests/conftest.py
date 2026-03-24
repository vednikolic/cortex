"""Shared test fixtures for cortex concepts graph."""

import json
import pytest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cortex_lib.db import init_db


@pytest.fixture
def db(tmp_path):
    """SQLite DB with schema initialized."""
    db_path = tmp_path / "test_concepts.db"
    conn = init_db(db_path)
    yield conn
    conn.close()


@pytest.fixture
def abbreviations_file(tmp_path):
    """Test abbreviations.json."""
    data = {
        "k8s": "kubernetes",
        "ts": "typescript",
        "py": "python",
        "js": "javascript",
        "tf": "terraform",
    }
    path = tmp_path / "abbreviations.json"
    path.write_text(json.dumps(data))
    return path
