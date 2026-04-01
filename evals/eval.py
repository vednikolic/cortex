#!/usr/bin/env python3
"""
Cortex Skill Eval Harness
Scores /save and /reflect SKILL.md files with binary evals.

Uses `claude -p` (Claude Code CLI) as the LLM judge.

Usage:
    python eval.py ../.claude/skills/save/SKILL.md --evals save_evals.json
    python eval.py ../.claude/skills/reflect/SKILL.md --evals reflect_evals.json
    python eval.py <target> --evals <evals.json> --verbose --output json
"""

import json
import subprocess
import sys
import os

JUDGE_SYSTEM = """You are a strict binary document evaluator. You will be given a document and a yes/no question about it.

Rules:
- Answer ONLY "YES" or "NO". Nothing else.
- Be strict. If the answer is ambiguous, partially true, or only loosely addressed, answer NO.
- Base your answer solely on what is explicitly present in the document.
- Do not infer, assume, or give benefit of the doubt.
- "Mentioned briefly" is not the same as "thoroughly addressed". If the question asks for thorough coverage, a passing mention does not count.
"""


def normalize_item(ev: dict) -> dict:
    """Normalize JSON to canonical schema: id, check, category, weight."""
    normalized = {}
    normalized["id"] = ev.get("id") or ev.get("name", "unknown")
    normalized["check"] = ev.get("check") or ev.get("prompt") or ev.get("question", "")
    normalized["category"] = ev.get("category", "general")
    normalized["weight"] = ev.get("weight", 1.0)
    normalized["prd_ref"] = ev.get("prd_ref", "")
    return normalized


def load_evals(evals_path: str) -> list[dict]:
    """Load definitions from JSON file. Normalizes all schema variants."""
    with open(evals_path, "r") as f:
        items = json.load(f)
    return [normalize_item(ev) for ev in items]


def evaluate_single(document: str, eval_item: dict) -> dict:
    """Run a single binary eval via claude -p."""
    prompt = f"""<document>
{document}
</document>

Question: {eval_item['check']}

Answer YES or NO only."""

    try:
        result = subprocess.run(
            [
                "claude", "-p",
                "--model", "sonnet",
                "--system-prompt", JUDGE_SYSTEM,
            ],
            input=prompt,
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0:
            print(f"  ERROR evaluating {eval_item['id']}: {result.stderr[:200]}", file=sys.stderr)
            return {
                "id": eval_item["id"],
                "category": eval_item["category"],
                "passed": False,
                "weight": eval_item.get("weight", 1.0),
            }
        answer = result.stdout.strip().upper()
        passed = answer.startswith("YES")
    except subprocess.TimeoutExpired:
        print(f"  TIMEOUT evaluating {eval_item['id']}", file=sys.stderr)
        passed = False
    except Exception as e:
        print(f"  ERROR evaluating {eval_item['id']}: {e}", file=sys.stderr)
        passed = False

    return {
        "id": eval_item["id"],
        "category": eval_item["category"],
        "passed": passed,
        "weight": eval_item.get("weight", 1.0),
    }


def run_evals(document_path: str, evals_path: str, verbose: bool = False) -> dict:
    """Run all evals against a document."""
    evals = load_evals(evals_path)

    with open(document_path, "r") as f:
        document = f.read()

    results = []
    for i, eval_item in enumerate(evals):
        if verbose:
            print(f"  [{i+1}/{len(evals)}] {eval_item['id']}...", file=sys.stderr)
        result = evaluate_single(document, eval_item)
        results.append(result)
        if verbose:
            status = "PASS" if result["passed"] else "FAIL"
            print(f"           -> {status}", file=sys.stderr)

    total_weight = sum(r["weight"] for r in results)
    passing_weight = sum(r["weight"] for r in results if r["passed"])
    composite_score = (passing_weight / total_weight * 100) if total_weight > 0 else 0
    passing_count = sum(1 for r in results if r["passed"])

    # Constraint gate: if any constraint_gate category item fails, score is 0
    constraint_gate_passed = True
    constraint_failures = []
    for r in results:
        if r["category"] == "constraint_gate" and not r["passed"]:
            constraint_gate_passed = False
            constraint_failures.append(r["id"])

    if not constraint_gate_passed:
        composite_score = 0.0

    categories: dict[str, dict] = {}
    for r in results:
        cat = r["category"]
        if cat not in categories:
            categories[cat] = {"passed": 0, "total": 0, "weight_passed": 0, "weight_total": 0}
        categories[cat]["total"] += 1
        categories[cat]["weight_total"] += r["weight"]
        if r["passed"]:
            categories[cat]["passed"] += 1
            categories[cat]["weight_passed"] += r["weight"]

    return {
        "composite_score": round(composite_score, 2),
        "passing": passing_count,
        "total": len(results),
        "constraint_gate": constraint_gate_passed,
        "constraint_failures": constraint_failures,
        "categories": categories,
        "results": results,
    }


def print_results(output: dict, fmt: str = "text"):
    if fmt == "json":
        print(json.dumps(output, indent=2))
        return

    print(f"composite_score: {output['composite_score']}")
    print(f"passing: {output['passing']}/{output['total']}")
    if not output.get("constraint_gate", True):
        print(f"CONSTRAINT GATE FAILED: {', '.join(output['constraint_failures'])}")
        print("  Score forced to 0% -- fix constraint violations first")
    print()
    print("--- Category Breakdown ---")
    for cat, data in output["categories"].items():
        pct = (data["weight_passed"] / data["weight_total"] * 100) if data["weight_total"] > 0 else 0
        print(f"  {cat}: {data['passed']}/{data['total']} ({pct:.0f}%)")
    print()
    print("--- Individual Results ---")
    for r in output["results"]:
        status = "PASS" if r["passed"] else "FAIL"
        print(f"  [{status}] {r['id']} (weight: {r['weight']})")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python eval.py <target.md> --evals <evals.json> [--verbose] [--output json]")
        sys.exit(1)

    doc_path = sys.argv[1]
    verbose = "--verbose" in sys.argv
    output_fmt = "json" if "--output" in sys.argv and "json" in sys.argv else "text"

    evals_path = None
    if "--evals" in sys.argv:
        idx = sys.argv.index("--evals")
        if idx + 1 < len(sys.argv):
            evals_path = sys.argv[idx + 1]

    if not evals_path:
        print("ERROR: --evals <file.json> is required")
        sys.exit(1)

    if not os.path.exists(doc_path):
        print(f"ERROR: {doc_path} not found")
        sys.exit(1)

    if not os.path.exists(evals_path):
        print(f"ERROR: {evals_path} not found")
        sys.exit(1)

    results = run_evals(doc_path, evals_path, verbose=verbose)
    print_results(results, fmt=output_fmt)
