"""Velocity subcommand test."""

import json
import sys
from io import StringIO
from unittest.mock import patch

from cortex_lib.db import init_db
from cortex_lib.ops import upsert_concept
from cortex_lib.cli import main


def _run_cli(*args):
    """Run CLI with given args, capture stdout."""
    out = StringIO()
    with patch.object(sys, 'argv', ['concepts'] + list(args)), \
         patch.object(sys, 'stdout', out), \
         patch.object(sys, 'exit') as mock_exit:
        main()
    mock_exit.assert_called_with(0)
    return out.getvalue()


def test_velocity_subcommand_json(tmp_path):
    """velocity --json returns weekly concept counts."""
    db_path = tmp_path / "test.db"
    conn = init_db(db_path)
    upsert_concept(conn, "python", kind="tool")
    conn.close()

    output = _run_cli("--db", str(db_path), "--json", "velocity")
    data = json.loads(output)
    assert "weeks" in data
    assert "avg_per_week" in data
    assert len(data["weeks"]) == 4  # default 4 weeks


def test_velocity_subcommand_text(tmp_path):
    """velocity without --json prints readable output."""
    db_path = tmp_path / "test.db"
    conn = init_db(db_path)
    conn.close()

    output = _run_cli("--db", str(db_path), "velocity")
    assert "Concept velocity" in output
    assert "Average:" in output
