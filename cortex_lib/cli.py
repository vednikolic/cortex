"""CLI interface for concepts graph management."""

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .db import connect, init_db, verify_db, find_db_path
from .canon import load_abbreviations, seed_abbreviations
from .ops import upsert_concept, add_edge, query_concept, log_extraction
from .analysis import (
    shared_concepts, stale_concepts, hot_concepts,
    graph_summary, weight_stats, concept_velocity,
)
from .correction import correct_concept, undo_last_extraction, merge_concepts
from .review import (
    create_weekly_summary, list_weekly_summaries, get_weekly_summary,
    triage_signal, pending_signals, generate_synthesis,
)
from .confidence import promote_concept, check_promotion_eligibility, apply_confidence_decay
from .portability import export_graph, import_graph
from .brief import generate_brief, format_brief


def _resolve_db(args) -> Path:
    """Resolve database path from --db, --root, or cwd walk."""
    if args.db:
        return Path(args.db)
    if args.root:
        return find_db_path(root=Path(args.root))
    return find_db_path()


def _connect(args):
    return connect(_resolve_db(args))


def cmd_init(args):
    if args.db:
        db_path = Path(args.db)
    elif args.root:
        db_path = Path(args.root).resolve() / 'concepts.db'
    else:
        db_path = Path('.') / 'concepts.db'
    if db_path.exists() and not args.force:
        print(f"Database already exists at {db_path}. Use --force to reinitialize.")
        return 1
    conn = init_db(db_path)
    print(f"Initialized concepts database at {db_path}")
    abbrevs = load_abbreviations()
    if abbrevs:
        count = seed_abbreviations(conn, abbrevs)
        if count:
            print(f"Seeded {count} abbreviation rules")
    conn.close()
    if not (db_path.parent / '.memory-config').exists():
        print("Note: No .memory-config found. Create one or use --db to specify the database path.",
              file=sys.stderr)
    return 0


def cmd_upsert(args):
    conn = _connect(args)
    try:
        result = upsert_concept(
            conn, args.name, kind=args.kind or 'topic',
            aliases=args.alias, project=args.project or '',
            session_hash=args.session or '', weight=args.weight or 1,
        )
        if args.json:
            print(json.dumps(result))
        else:
            print(f"{result['action'].capitalize()}: {result['name']} (id={result['concept_id']})")
    finally:
        conn.close()
    return 0


def cmd_edge(args):
    conn = _connect(args)
    try:
        result = add_edge(conn, args.from_concept, args.to_concept, args.relation,
                          session_hash=args.session or '')
        if args.json:
            print(json.dumps(result))
        else:
            print(f"Edge {result['action']}: {result['from']} --[{result['relation']}]--> "
                  f"{result['to']} (strength={result['strength']})")
    finally:
        conn.close()
    return 0


def cmd_query(args):
    conn = _connect(args)
    try:
        result = query_concept(conn, args.name)
        if not result:
            print(f"Not found: '{args.name}'")
            return 1
        if args.json:
            print(json.dumps(result, default=str))
        else:
            c = result['concept']
            print(f"{c['name']} ({c['kind']}, {c['confidence']})")
            aliases = json.loads(c['aliases'])
            if aliases:
                print(f"  Aliases: {', '.join(aliases)}")
            print(f"  Sources: {c['source_count']} | First: {c['first_seen'][:10]} | "
                  f"Last: {c['last_referenced'][:10]}")
            if result['edges']:
                print(f"  Edges ({len(result['edges'])}):")
                for e in result['edges']:
                    direction = '->' if e['from_concept_id'] == c['id'] else '<-'
                    other = e['to_name'] if direction == '->' else e['from_name']
                    print(f"    {direction} {other} [{e['relation']}] (strength={e['strength']})")
    finally:
        conn.close()
    return 0


def cmd_shared(args):
    conn = _connect(args)
    try:
        results = shared_concepts(conn)
        if args.json:
            print(json.dumps(results, default=str))
        elif not results:
            print("No cross-project concepts found yet.")
        else:
            for r in results:
                print(f"{r['name']} ({r['kind']}) - {r['project_count']} projects: {r['projects']}")
    finally:
        conn.close()
    return 0


def cmd_stale(args):
    conn = _connect(args)
    try:
        results = stale_concepts(conn, args.days)
        if args.json:
            print(json.dumps(results, default=str))
        elif not results:
            print(f"No concepts unreferenced for {args.days}+ days.")
        else:
            for r in results:
                print(f"{r['name']} ({r['confidence']}) - last ref: {r['last_referenced'][:10]}")
    finally:
        conn.close()
    return 0


def cmd_hot(args):
    conn = _connect(args)
    try:
        results = hot_concepts(conn, args.limit)
        if args.json:
            print(json.dumps(results, default=str))
        else:
            for r in results:
                print(f"{r['name']} ({r['kind']}) - sources: {r['source_count']}, "
                      f"edges: {r['edge_count']}")
    finally:
        conn.close()
    return 0


def cmd_graph(args):
    conn = _connect(args)
    try:
        s = graph_summary(conn)
        if args.json:
            print(json.dumps(s))
        else:
            print(f"Concepts: {s['concepts']}")
            print(f"Edges: {s['edges']} (avg {s['avg_edges_per_concept']}/concept)")
            print(f"Projects: {s['projects']}")
            print(f"Normalization rules: {s['normalization_rules']}")
            print(f"Extractions: {s['extractions']}")
            if s['confidence_distribution']:
                print(f"Confidence: {s['confidence_distribution']}")
    finally:
        conn.close()
    return 0


def cmd_merge(args):
    conn = _connect(args)
    try:
        result = merge_concepts(conn, args.source, args.target)
        if args.json:
            print(json.dumps(result))
        else:
            print(f"Merged '{result['source']}' into '{result['target']}'")
    finally:
        conn.close()
    return 0


def cmd_correct(args):
    conn = _connect(args)
    try:
        result = correct_concept(conn, args.name, args.new_name)
        if args.json:
            print(json.dumps(result))
        else:
            print(f"Renamed '{result['old_name']}' to '{result['new_name']}'")
    finally:
        conn.close()
    return 0


def cmd_undo_last(args):
    conn = _connect(args)
    try:
        result = undo_last_extraction(conn)
        if args.json:
            print(json.dumps(result))
        else:
            print(f"Undid extraction #{result['extraction_id']}")
            if result['removed_concepts']:
                print(f"  Removed concepts: {', '.join(result['removed_concepts'])}")
            if result['removed_edges']:
                print(f"  Removed {len(result['removed_edges'])} edges")
    finally:
        conn.close()
    return 0


def cmd_verify(args):
    conn = _connect(args)
    try:
        issues = verify_db(conn)
        if issues:
            for issue in issues:
                print(f"ISSUE: {issue}")
            return 1
        print("Database healthy.")
        return 0
    finally:
        conn.close()


def cmd_stats(args):
    conn = _connect(args)
    try:
        s = graph_summary(conn)
        ws = weight_stats(conn)
        if args.json:
            print(json.dumps({'graph': s, 'weights': ws}))
        else:
            print(f"Graph: {s['concepts']} concepts, {s['edges']} edges, "
                  f"{s['projects']} projects")
            if args.weights and ws['by_weight']:
                print(f"\nWeight distribution ({ws['total_extractions']} extractions):")
                for w in ws['by_weight']:
                    print(f"  Weight {w['weight']}: {w['cnt']} extractions, "
                          f"avg {w['avg_concepts']:.1f} concepts, "
                          f"avg {w['avg_rejected']:.1f} rejected")
    finally:
        conn.close()
    return 0


def cmd_log_extraction(args):
    """Log an extraction event to extraction_log."""
    conn = _connect(args)
    try:
        eid = log_extraction(
            conn, args.session,
            json.loads(args.proposed), json.loads(args.created),
            json.loads(args.edges), args.rejected, args.weight,
        )
        if args.json:
            print(json.dumps({'extraction_id': eid}))
        else:
            print(f"Logged extraction #{eid}")
    finally:
        conn.close()
    return 0


def cmd_list(args):
    """List all concept names (vocabulary query for /save Step 4b)."""
    conn = _connect(args)
    try:
        rows = conn.execute(
            "SELECT name, kind, confidence, source_count FROM concepts ORDER BY name"
        ).fetchall()
        if args.json:
            print(json.dumps([dict(r) for r in rows], default=str))
        else:
            for r in rows:
                print(f"{r['name']} ({r['kind']}, {r['confidence']}, sources={r['source_count']})")
    finally:
        conn.close()
    return 0


def cmd_reflect_prep(args):
    print("WARNING: reflect-prep is deprecated. /reflect now queries the graph directly via CLI.",
          file=sys.stderr)
    from .reflect_prep import write_reflect_context, validate_content_hash
    db = Path(args.db) if args.db else None
    if args.verify:
        db_path = _resolve_db(args)
        context_path = db_path.parent / 'reflect-context.json'
        if not context_path.exists():
            print("stale: reflect-context.json does not exist")
            return 1
        with open(context_path) as f:
            data = json.load(f)
        if validate_content_hash(data, db_path):
            print("fresh")
            return 0
        else:
            print("stale: content hash mismatch")
            return 1
    path = write_reflect_context(db_path=db)
    print(f"Written: {path}")
    return 0


def cmd_review_summary(args):
    conn = _connect(args)
    try:
        if args.create:
            result = create_weekly_summary(conn, args.create)
            if args.json:
                print(json.dumps(result))
            else:
                print(f"Created summary for week of {result['week_start']}: "
                      f"{result['concept_count']} concepts, {result['edge_count']} edges")
        elif args.week:
            s = get_weekly_summary(conn, args.week)
            if not s:
                print(f"No summary for week {args.week}")
                return 1
            if args.json:
                print(json.dumps(dict(s), default=str))
            else:
                print(f"Week of {s['week_start']}: {s['concept_count']} concepts, "
                      f"{s['edge_count']} edges, {s['project_count']} projects")
                if s['summary']:
                    print(f"\n{s['summary']}")
        else:
            summaries = list_weekly_summaries(conn)
            if args.json:
                print(json.dumps(summaries, default=str))
            elif not summaries:
                print("No weekly summaries yet. Use --create YYYY-MM-DD to create one.")
            else:
                for s in summaries:
                    print(f"{s['week_start']}: {s['concept_count']} concepts, "
                          f"{s['edge_count']} edges, {s['project_count']} projects")
    finally:
        conn.close()
    return 0


def cmd_promote(args):
    conn = _connect(args)
    try:
        result = promote_concept(conn, args.name, args.level)
        if args.json:
            print(json.dumps(result))
        else:
            print(f"Promoted '{result['name']}': {result['old_confidence']} -> {result['new_confidence']}")
    finally:
        conn.close()
    return 0


def cmd_dismiss(args):
    conn = _connect(args)
    try:
        result = triage_signal(conn, edge_id=args.edge_id, action="dismiss")
        if args.json:
            print(json.dumps(result))
        else:
            print(f"Dismissed edge #{result['edge_id']}")
    finally:
        conn.close()
    return 0


def cmd_brief(args):
    conn = _connect(args)
    try:
        data = generate_brief(conn)
        if getattr(args, 'verbose', False):
            stats = data.get('graph_stats', {})
            print(f"[brief] concepts={stats.get('concepts', 0)} "
                  f"edges={stats.get('edges', 0)} "
                  f"projects={stats.get('projects', 0)}", file=sys.stderr)
            if 'last_session' in data:
                print(f"[brief] last_extraction={data['last_session']['timestamp']}", file=sys.stderr)
            if args.output:
                print(f"[brief] writing to {args.output}", file=sys.stderr)
        if args.json:
            print(json.dumps(data, indent=2))
        elif args.output:
            Path(args.output).write_text(format_brief(data) + '\n')
        else:
            print(format_brief(data))
    finally:
        conn.close()
    return 0


def cmd_export(args):
    conn = _connect(args)
    try:
        data = export_graph(conn)
        output = json.dumps(data, indent=2)
        if args.output:
            Path(args.output).write_text(output)
            print(f"Exported to {args.output}")
        else:
            print(output)
    finally:
        conn.close()
    return 0


def cmd_import(args):
    conn = _connect(args)
    try:
        data = json.loads(Path(args.file).read_text())
        result = import_graph(conn, data)
        print(f"Import complete:")
        print(f"  Concepts: {result['concepts_created']} created, {result['concepts_updated']} updated")
        print(f"  Edges: {result['edges_created']} created, {result['edges_strengthened']} strengthened")
        print(f"  Rules: {result['rules_added']} added")
    finally:
        conn.close()
    return 0


def cmd_confidence_check(args):
    conn = _connect(args)
    try:
        if args.decay:
            demoted = apply_confidence_decay(conn)
            if args.json:
                print(json.dumps(demoted))
            elif not demoted:
                print("No concepts demoted.")
            else:
                for d in demoted:
                    print(f"Demoted '{d['name']}': {d['from']} -> {d['to']}")
        else:
            eligible = check_promotion_eligibility(conn)
            if args.json:
                print(json.dumps(eligible))
            elif not eligible:
                print("No concepts eligible for promotion.")
            else:
                for e in eligible:
                    print(f"{e['name']}: {e['current']} -> {e['suggested']} ({e['reason']})")
    finally:
        conn.close()
    return 0


def cmd_velocity(args):
    conn = _connect(args)
    try:
        result = concept_velocity(conn, args.weeks)
        if args.json:
            print(json.dumps(result))
        else:
            print(f"Concept velocity (last {args.weeks} weeks):")
            print(f"  Average: {result['avg_per_week']:.1f} concepts/week")
            for w in result['weeks']:
                print(f"  {w['week_start']}: {w['concepts_added']} added")
    finally:
        conn.close()
    return 0


def cmd_co_occurs(args):
    conn = _connect(args)
    try:
        from .analysis import co_occurring_concepts
        results = co_occurring_concepts(conn, args.name, args.min_shared)
        if args.json:
            print(json.dumps(results))
        elif not results:
            print(f"No co-occurring concepts for '{args.name}' "
                  f"(min shared neighbors: {args.min_shared})")
        else:
            print(f"Concepts co-occurring with '{args.name}':")
            for r in results:
                print(f"  {r['concept']} ({r['shared_count']} shared): "
                      f"{', '.join(r['shared_neighbors'])}")
    finally:
        conn.close()
    return 0


def cmd_explore(args):
    from .explorer import start_explorer
    db_path = Path(args.db) if args.db else None
    start_explorer(db_path=db_path, port=args.port,
                   open_browser=not args.no_browser)
    return 0


def cmd_hooks(args):
    if args.action == "install":
        from .hooks import install_hooks
        result = install_hooks()
        print("Cortex hooks installed:")
        print(f"  Scripts: {', '.join(result['scripts_installed'])}")
        print(f"  Location: {result['scripts_dir']}")
        print(f"  Settings: {result['settings_path']}")
    elif args.action == "status":
        from .hooks import generate_hooks_config
        scripts_dir = Path.home() / ".claude" / "scripts"
        config = generate_hooks_config()
        for event, hooks in config["hooks"].items():
            for h in hooks:
                script_name = h["command"].split("/")[-1]
                installed = (scripts_dir / script_name).exists()
                status = "installed" if installed else "missing"
                print(f"  {event}: {script_name} [{status}]")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog='concepts', description='Cortex concepts graph CLI')
    parser.add_argument('--version', action='version', version=f'%(prog)s {__version__}')
    parser.add_argument('--db', help='Path to concepts.db (default: auto-detect from .memory-config)')
    parser.add_argument('--root', help='Workspace root directory containing .memory-config')
    parser.add_argument('--json', action='store_true', help='Output as JSON')

    sub = parser.add_subparsers(dest='command', required=True)

    p = sub.add_parser('init', help='Initialize concepts database')
    p.add_argument('--force', action='store_true', help='Reinitialize existing database')
    p.set_defaults(func=cmd_init)

    p = sub.add_parser('upsert', help='Create or update a concept')
    p.add_argument('name')
    p.add_argument('--kind', choices=['topic', 'tool', 'pattern', 'decision', 'person', 'project'])
    p.add_argument('--alias', action='append', help='Alternative names')
    p.add_argument('--project', help='Project name')
    p.add_argument('--session', help='Session hash')
    p.add_argument('--weight', type=int, help='Session weight')
    p.set_defaults(func=cmd_upsert)

    p = sub.add_parser('edge', help='Create or strengthen an edge')
    p.add_argument('from_concept')
    p.add_argument('to_concept')
    p.add_argument('relation', choices=sorted([
        'related-to', 'depends-on', 'conflicts-with', 'enables',
        'is-instance-of', 'supersedes', 'blocked-by', 'derived-from',
    ]))
    p.add_argument('--session', help='Session hash')
    p.set_defaults(func=cmd_edge)

    p = sub.add_parser('query', help='Query a concept and its relationships')
    p.add_argument('name')
    p.set_defaults(func=cmd_query)

    p = sub.add_parser('shared', help='Show concepts appearing in 2+ projects')
    p.set_defaults(func=cmd_shared)

    p = sub.add_parser('stale', help='Show concepts not recently referenced')
    p.add_argument('--days', type=int, default=60)
    p.set_defaults(func=cmd_stale)

    p = sub.add_parser('hot', help='Show most active concepts')
    p.add_argument('--limit', type=int, default=10)
    p.set_defaults(func=cmd_hot)

    p = sub.add_parser('graph', help='Show graph summary')
    p.set_defaults(func=cmd_graph)

    p = sub.add_parser('merge', help='Merge source concept into target')
    p.add_argument('source')
    p.add_argument('target')
    p.set_defaults(func=cmd_merge)

    p = sub.add_parser('correct', help='Rename a concept')
    p.add_argument('name', help='Current name')
    p.add_argument('new_name', help='New name')
    p.set_defaults(func=cmd_correct)

    p = sub.add_parser('undo-last', help='Revert most recent extraction')
    p.set_defaults(func=cmd_undo_last)

    p = sub.add_parser('verify', help='Check database integrity')
    p.set_defaults(func=cmd_verify)

    p = sub.add_parser('stats', help='Show statistics and weight distributions')
    p.add_argument('--weights', action='store_true', help='Show weight distributions')
    p.set_defaults(func=cmd_stats)

    p = sub.add_parser('log-extraction', help='Log an extraction event')
    p.add_argument('--session', required=True, help='Session hash')
    p.add_argument('--proposed', required=True, help='JSON array of proposed concept names')
    p.add_argument('--created', required=True, help='JSON array of created concept names')
    p.add_argument('--edges', required=True, help='JSON array of {from, to, relation} objects')
    p.add_argument('--rejected', type=int, required=True, help='Count of rejected concepts')
    p.add_argument('--weight', type=int, required=True, help='Session weight')
    p.set_defaults(func=cmd_log_extraction)

    p = sub.add_parser('list', help='List all concept names (vocabulary query)')
    p.set_defaults(func=cmd_list)

    p = sub.add_parser('reflect-prep', help='Generate or verify reflect-context.json')
    p.add_argument('--verify', action='store_true',
                   help='Check if existing reflect-context.json is fresh (exit 0=fresh, 1=stale)')
    p.set_defaults(func=cmd_reflect_prep)

    p = sub.add_parser('review-summary', help='Create, list, or view weekly summaries')
    p.add_argument('--create', metavar='YYYY-MM-DD', help='Create summary for this week')
    p.add_argument('--week', metavar='YYYY-MM-DD', help='View summary for this week')
    p.set_defaults(func=cmd_review_summary)

    p = sub.add_parser('promote', help='Promote concept confidence level')
    p.add_argument('name', help='Concept name')
    p.add_argument('level', choices=['established', 'settled'], help='Target confidence')
    p.set_defaults(func=cmd_promote)

    p = sub.add_parser('dismiss', help='Dismiss an edge signal')
    p.add_argument('edge_id', type=int, help='Edge ID to dismiss')
    p.set_defaults(func=cmd_dismiss)

    p = sub.add_parser('confidence-check', help='Check promotion eligibility or run decay')
    p.add_argument('--decay', action='store_true', help='Apply confidence decay rules')
    p.set_defaults(func=cmd_confidence_check)

    p = sub.add_parser('velocity', help='Show concept creation velocity per week')
    p.add_argument('--weeks', type=int, default=4, help='Number of weeks to analyze')
    p.set_defaults(func=cmd_velocity)

    p = sub.add_parser('co-occurs', help='Find concepts sharing common neighbors')
    p.add_argument('name', help='Concept name')
    p.add_argument('--min-shared', type=int, default=2,
                   help='Minimum shared neighbors (default: 2)')
    p.set_defaults(func=cmd_co_occurs)

    p = sub.add_parser('explore', help='Open graph explorer in browser')
    p.add_argument('--port', type=int, default=9474, help='Server port (default: 9474)')
    p.add_argument('--no-browser', action='store_true', help='Do not open browser')
    p.set_defaults(func=cmd_explore)

    p = sub.add_parser('hooks', help='Install or check cortex hooks')
    p.add_argument('action', choices=['install', 'status'],
                   help='install: add hooks to settings.json; status: check installation')
    p.set_defaults(func=cmd_hooks)

    p = sub.add_parser('brief', help='Generate session context brief')
    p.add_argument('--output', '-o', help='Write brief to file (default: stdout)')
    p.add_argument('--verbose', '-v', action='store_true', help='Print debug info to stderr')
    p.set_defaults(func=cmd_brief)

    p = sub.add_parser('export', help='Export graph to JSON')
    p.add_argument('--output', '-o', help='Output file path (default: stdout)')
    p.set_defaults(func=cmd_export)

    p = sub.add_parser('import', help='Import graph from JSON')
    p.add_argument('file', help='JSON file to import')
    p.set_defaults(func=cmd_import)

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    try:
        sys.exit(args.func(args) or 0)
    except (ValueError, FileNotFoundError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
