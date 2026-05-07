"""Deterministic context helpers for portable memory workflows."""

from __future__ import annotations

import re
from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path


DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")
REVISIT_RE = re.compile(r"\[revisit\].*?(\d{4}-\d{2}-\d{2})?", re.IGNORECASE)
FRICTION_RE = re.compile(r"friction[^:\n]*:\s*(.+)", re.IGNORECASE)


def monday_for(day: date) -> date:
    """Return the Monday for the week containing day."""
    return day - timedelta(days=day.weekday())


def daily_note_paths(workspace: Path, days: int = 7, today: date | None = None) -> list[Path]:
    """Return existing daily note paths in the last N days, newest first."""
    today = today or date.today()
    daily_dir = workspace / "2-areas" / "me" / "daily"
    paths: list[Path] = []
    for offset in range(days):
        path = daily_dir / f"{today - timedelta(days=offset)}.md"
        if path.exists():
            paths.append(path)
    return paths


def revisit_decisions(workspace: Path, older_than_days: int = 14, today: date | None = None) -> list[dict[str, str]]:
    """Find [revisit] markers older than the threshold."""
    today = today or date.today()
    cutoff = today - timedelta(days=older_than_days)
    results: list[dict[str, str]] = []
    for path in _markdown_files(workspace):
        for line_no, line in enumerate(path.read_text(errors="ignore").splitlines(), start=1):
            if "[revisit]" not in line.lower():
                continue
            match = DATE_RE.search(line)
            if not match:
                continue
            revisit_date = datetime.strptime(match.group(1), "%Y-%m-%d").date()
            if revisit_date < cutoff:
                results.append({
                    "path": str(path),
                    "line": str(line_no),
                    "date": revisit_date.isoformat(),
                    "text": line.strip(),
                })
    return results


def friction_counts(workspace: Path) -> list[dict[str, object]]:
    """Count repeated Friction Log lines across project and memory files."""
    counter: Counter[str] = Counter()
    examples: dict[str, str] = {}
    for path in _markdown_files(workspace):
        text = path.read_text(errors="ignore")
        if "friction" not in text.lower():
            continue
        for line in text.splitlines():
            match = FRICTION_RE.search(line)
            if not match:
                continue
            item = _normalize_signal(match.group(1))
            if not item:
                continue
            counter[item] += 1
            examples.setdefault(item, line.strip())
    return [
        {"signal": signal, "count": count, "example": examples[signal]}
        for signal, count in counter.most_common()
        if count >= 2
    ]


def memory_hygiene(workspace: Path) -> dict[str, object]:
    """Return basic memory index and orphan topic file checks."""
    memory_dir = workspace / ".agents" / "memory"
    if not memory_dir.exists():
        return {"memory_dir": str(memory_dir), "exists": False, "index_bytes": 0, "long_files": [], "orphans": []}

    index = memory_dir / "index.md"
    index_text = index.read_text(errors="ignore") if index.exists() else ""
    md_files = sorted(p for p in memory_dir.rglob("*.md") if p.is_file())
    long_files = [{"path": str(p), "bytes": p.stat().st_size} for p in md_files if p.stat().st_size > 12000]
    orphans = [
        str(p) for p in md_files
        if p != index and p.name not in index_text and str(p.relative_to(memory_dir)) not in index_text
    ]
    return {
        "memory_dir": str(memory_dir),
        "exists": True,
        "index_bytes": index.stat().st_size if index.exists() else 0,
        "long_files": long_files,
        "orphans": orphans,
    }


def workflow_context(workspace: Path, days: int = 7, today: date | None = None) -> dict[str, object]:
    """Collect deterministic context for reflect and review workflows."""
    today = today or date.today()
    return {
        "workspace": str(workspace.resolve()),
        "today": today.isoformat(),
        "week_start": monday_for(today).isoformat(),
        "daily_notes_7d": [str(p) for p in daily_note_paths(workspace, days=days, today=today)],
        "daily_notes_14d": [str(p) for p in daily_note_paths(workspace, days=14, today=today)],
        "stale_revisit_decisions": revisit_decisions(workspace, today=today),
        "friction_counts": friction_counts(workspace),
        "memory_hygiene": memory_hygiene(workspace),
    }


def _markdown_files(workspace: Path) -> list[Path]:
    roots = [
        workspace / "1-projects",
        workspace / "2-areas" / "me",
        workspace / ".agents" / "memory",
    ]
    files: list[Path] = []
    for root in roots:
        if root.exists():
            files.extend(p for p in root.rglob("*.md") if p.is_file())
    return files


def _normalize_signal(text: str) -> str:
    text = re.sub(r"\[[^\]]+\]", "", text)
    text = re.sub(r"\d{4}-\d{2}-\d{2}", "", text)
    text = re.sub(r"[^a-zA-Z0-9 ]+", " ", text)
    return " ".join(text.lower().split())
