"""Explorer server endpoint tests."""

import json
import threading
import pytest
from http.server import HTTPServer
from urllib.request import urlopen, Request
from urllib.error import HTTPError

from cortex_lib.db import init_db
from cortex_lib.ops import upsert_concept, add_edge


@pytest.fixture
def explorer_server(tmp_path):
    """Start explorer on a random port with a test DB."""
    from cortex_lib.explorer import ExplorerHandler

    db_path = tmp_path / "explorer_test.db"
    conn = init_db(db_path)
    upsert_concept(conn, "python", kind="tool")
    upsert_concept(conn, "fastapi", kind="tool")
    upsert_concept(conn, "auth", kind="topic")
    add_edge(conn, "python", "fastapi", "enables")
    add_edge(conn, "fastapi", "auth", "related-to")
    conn.close()

    ExplorerHandler.db_path = db_path
    server = HTTPServer(("127.0.0.1", 0), ExplorerHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield port
    server.shutdown()
    server.server_close()


def test_root_serves_html(explorer_server):
    """GET / returns HTML page."""
    resp = urlopen(f"http://127.0.0.1:{explorer_server}/")
    assert resp.status == 200
    body = resp.read().decode()
    assert "<html" in body
    assert "Cortex Explorer" in body


def test_graph_endpoint(explorer_server):
    """GET /api/graph returns concepts and edges."""
    resp = urlopen(f"http://127.0.0.1:{explorer_server}/api/graph")
    data = json.loads(resp.read())
    assert len(data["concepts"]) == 3
    assert len(data["edges"]) == 2
    assert "summary" in data


def test_timeline_endpoint(explorer_server):
    """GET /api/timeline returns time-ordered data."""
    resp = urlopen(f"http://127.0.0.1:{explorer_server}/api/timeline")
    data = json.loads(resp.read())
    assert "concepts" in data
    assert "edges" in data
    assert "summaries" in data


def test_clusters_endpoint(explorer_server):
    """GET /api/clusters returns connected components."""
    resp = urlopen(f"http://127.0.0.1:{explorer_server}/api/clusters")
    data = json.loads(resp.read())
    assert "clusters" in data
    # python-fastapi-auth form one cluster
    assert len(data["clusters"]) >= 1


def test_unknown_path_returns_404(explorer_server):
    """Unknown path returns 404."""
    with pytest.raises(HTTPError) as exc_info:
        urlopen(f"http://127.0.0.1:{explorer_server}/api/nonexistent")
    assert exc_info.value.code == 404


def test_html_contains_d3(explorer_server):
    """Explorer HTML loads D3.js."""
    resp = urlopen(f"http://127.0.0.1:{explorer_server}/")
    body = resp.read().decode()
    assert "d3js.org" in body


def test_html_contains_search(explorer_server):
    """Explorer HTML has a search input."""
    resp = urlopen(f"http://127.0.0.1:{explorer_server}/")
    body = resp.read().decode()
    assert 'id="search"' in body


def test_timeline_concepts_ordered_by_date(explorer_server):
    """Timeline concepts are sorted chronologically."""
    resp = urlopen(f"http://127.0.0.1:{explorer_server}/api/timeline")
    data = json.loads(resp.read())
    dates = [c["first_seen"] for c in data["concepts"]]
    assert dates == sorted(dates)


def test_timeline_edges_ordered_by_date(explorer_server):
    """Timeline edges are sorted chronologically."""
    resp = urlopen(f"http://127.0.0.1:{explorer_server}/api/timeline")
    data = json.loads(resp.read())
    dates = [e["first_seen"] for e in data["edges"]]
    assert dates == sorted(dates)


def test_html_contains_replay_slider(explorer_server):
    """Explorer HTML has the temporal replay slider."""
    resp = urlopen(f"http://127.0.0.1:{explorer_server}/")
    body = resp.read().decode()
    assert 'id="replay-slider"' in body
    assert 'id="replay-btn"' in body


def test_correct_endpoint_renames(explorer_server):
    """POST /api/correct renames a concept."""
    body = json.dumps({"old_name": "auth", "new_name": "authentication"}).encode()
    req = Request(f"http://127.0.0.1:{explorer_server}/api/correct",
                  data=body, headers={"Content-Type": "application/json"})
    resp = urlopen(req)
    data = json.loads(resp.read())
    assert data["new_name"] == "authentication"

    # Verify via graph endpoint
    resp2 = urlopen(f"http://127.0.0.1:{explorer_server}/api/graph")
    graph = json.loads(resp2.read())
    names = [c["name"] for c in graph["concepts"]]
    assert "authentication" in names
    assert "auth" not in names


def test_merge_endpoint(explorer_server):
    """POST /api/merge merges source into target."""
    body = json.dumps({"source": "auth", "target": "python"}).encode()
    req = Request(f"http://127.0.0.1:{explorer_server}/api/merge",
                  data=body, headers={"Content-Type": "application/json"})
    resp = urlopen(req)
    data = json.loads(resp.read())
    assert data["target"] == "python"


def test_flag_endpoint_creates_queue(explorer_server, tmp_path):
    """POST /api/flag writes to correction-queue.json."""
    body = json.dumps({"name": "auth", "issue": "wrong kind"}).encode()
    req = Request(f"http://127.0.0.1:{explorer_server}/api/flag",
                  data=body, headers={"Content-Type": "application/json"})
    resp = urlopen(req)
    data = json.loads(resp.read())
    assert data["status"] == "flagged"
    assert data["queue_length"] == 1

    queue_path = tmp_path / "correction-queue.json"
    assert queue_path.exists()
    queue = json.loads(queue_path.read_text())
    assert len(queue) == 1
    assert queue[0]["concept"] == "auth"
