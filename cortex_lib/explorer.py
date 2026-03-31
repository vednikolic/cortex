"""Graph explorer: local web visualization served via HTTP."""

import json
import sqlite3
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse, parse_qs

from .db import connect, find_db_path, utc_now
from .analysis import graph_summary
from .correction import correct_concept, merge_concepts
from .explorer_html import EXPLORER_HTML


class ExplorerHandler(BaseHTTPRequestHandler):
    """HTTP request handler for the graph explorer."""

    db_path: Optional[Path] = None

    def _get_conn(self) -> sqlite3.Connection:
        return connect(self.db_path)

    def _send_json(self, data: dict, status: int = 200):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, html: str):
        body = html.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self) -> dict:
        length = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(length)) if length else {}

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/":
            self._send_html(EXPLORER_HTML)
        elif path == "/api/graph":
            self._handle_graph()
        elif path == "/api/timeline":
            self._handle_timeline()
        elif path == "/api/clusters":
            self._handle_clusters()
        else:
            self.send_error(404)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/api/correct":
            self._handle_correct()
        elif path == "/api/merge":
            self._handle_merge()
        elif path == "/api/flag":
            self._handle_flag()
        else:
            self.send_error(404)

    def _handle_graph(self):
        conn = self._get_conn()
        try:
            concepts = [dict(r) for r in conn.execute(
                "SELECT id, name, kind, confidence, source_count, "
                "first_seen, last_referenced FROM concepts ORDER BY name"
            ).fetchall()]

            edges = [dict(r) for r in conn.execute(
                "SELECT e.id, e.from_concept_id, e.to_concept_id, "
                "c1.name as from_name, c2.name as to_name, "
                "e.relation, e.strength, e.confidence, e.first_seen "
                "FROM concept_edges e "
                "JOIN concepts c1 ON e.from_concept_id = c1.id "
                "JOIN concepts c2 ON e.to_concept_id = c2.id "
                "WHERE e.dismissed = 0 "
                "ORDER BY e.strength DESC"
            ).fetchall()]

            summary = graph_summary(conn)
            self._send_json({
                "concepts": concepts,
                "edges": edges,
                "summary": summary,
            })
        finally:
            conn.close()

    def _handle_timeline(self):
        conn = self._get_conn()
        try:
            concepts = [dict(c) for c in conn.execute(
                "SELECT id, name, kind, confidence, source_count, first_seen "
                "FROM concepts ORDER BY first_seen"
            ).fetchall()]

            edges = [dict(e) for e in conn.execute(
                "SELECT e.id, c1.name as from_name, c2.name as to_name, "
                "e.relation, e.strength, e.first_seen "
                "FROM concept_edges e "
                "JOIN concepts c1 ON e.from_concept_id = c1.id "
                "JOIN concepts c2 ON e.to_concept_id = c2.id "
                "WHERE e.dismissed = 0 "
                "ORDER BY e.first_seen"
            ).fetchall()]

            summaries = [dict(s) for s in conn.execute(
                "SELECT week_start, concept_count, edge_count, project_count "
                "FROM weekly_summaries ORDER BY week_start"
            ).fetchall()]

            self._send_json({
                "concepts": concepts,
                "edges": edges,
                "summaries": summaries,
            })
        finally:
            conn.close()

    def _handle_clusters(self):
        conn = self._get_conn()
        try:
            concepts = {row[0]: row[1] for row in conn.execute(
                "SELECT id, name FROM concepts"
            ).fetchall()}

            adj: dict[int, set[int]] = {cid: set() for cid in concepts}
            for row in conn.execute(
                "SELECT from_concept_id, to_concept_id FROM concept_edges "
                "WHERE dismissed = 0"
            ).fetchall():
                adj[row[0]].add(row[1])
                adj[row[1]].add(row[0])

            visited: set[int] = set()
            clusters: list[list[str]] = []
            for start in concepts:
                if start in visited:
                    continue
                component: list[str] = []
                queue = [start]
                while queue:
                    node = queue.pop(0)
                    if node in visited:
                        continue
                    visited.add(node)
                    component.append(concepts[node])
                    queue.extend(adj[node] - visited)
                if len(component) >= 2:
                    clusters.append(sorted(component))

            clusters.sort(key=len, reverse=True)
            self._send_json({"clusters": clusters})
        finally:
            conn.close()

    def _handle_correct(self):
        data = self._read_body()
        conn = self._get_conn()
        try:
            result = correct_concept(conn, data["old_name"], data["new_name"])
            self._send_json(result)
        except (ValueError, KeyError) as e:
            self._send_json({"error": str(e)}, 400)
        finally:
            conn.close()

    def _handle_merge(self):
        data = self._read_body()
        conn = self._get_conn()
        try:
            result = merge_concepts(conn, data["source"], data["target"])
            self._send_json(result)
        except (ValueError, KeyError) as e:
            self._send_json({"error": str(e)}, 400)
        finally:
            conn.close()

    def _handle_flag(self):
        data = self._read_body()
        db_path = self.db_path or find_db_path()
        queue_path = db_path.parent / "correction-queue.json"

        queue = []
        if queue_path.exists():
            queue = json.loads(queue_path.read_text())

        queue.append({
            "concept": data.get("name", ""),
            "issue": data.get("issue", "flagged for review"),
            "flagged_at": utc_now(),
        })
        queue_path.write_text(json.dumps(queue, indent=2))
        self._send_json({"status": "flagged", "queue_length": len(queue)})

    def log_message(self, format, *args):
        """Suppress default request logging."""
        pass


def start_explorer(db_path: Optional[Path] = None, port: int = 9474,
                   open_browser: bool = True) -> HTTPServer:
    """Start the explorer HTTP server."""
    ExplorerHandler.db_path = db_path
    server = HTTPServer(("127.0.0.1", port), ExplorerHandler)
    url = f"http://127.0.0.1:{port}"
    print(f"Cortex explorer running at {url}")
    print("Press Ctrl+C to stop.")
    if open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nExplorer stopped.")
    server.server_close()
    return server
