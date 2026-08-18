"""Command-line interface for Proofline."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .evaluation import RetrievalEvaluator, load_retrieval_suite
from .ingest import Ingestor
from .ocr import PyMuPDFTesseractBackend
from .progressive import ProgressiveExtractor
from .review import preferred_extraction, review_count, review_queue
from .search import SearchIndex
from .storage import ProoflineStore
from .watcher import CorpusWatcher, load_manifest
from .watch_storage import WatcherStore


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="proofline")
    parser.add_argument(
        "--state-dir",
        default=".proofline",
        help="Proofline state directory (default: .proofline)",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    ingest_parser = subparsers.add_parser("ingest", help="Preserve and ingest a local artifact")
    ingest_parser.add_argument("path")
    ingest_parser.add_argument("--source-uri")
    ingest_parser.add_argument("--source-name")
    ingest_parser.add_argument("--native-id")

    subparsers.add_parser("status", help="Show evidence-core counts and review backlog")

    trace_parser = subparsers.add_parser("trace", help="Trace an observation back to source evidence")
    trace_parser.add_argument("observation_id")

    watch_parser = subparsers.add_parser("watch", help="Check all resources in a source manifest")
    watch_parser.add_argument("manifest")

    changes_parser = subparsers.add_parser("changes", help="Show recorded source changes")
    changes_parser.add_argument("--limit", type=int, default=100)
    changes_parser.add_argument("--include-unchanged", action="store_true")
    changes_parser.add_argument("--run-id")

    review_parser = subparsers.add_parser("review", help="List evidence below a quality threshold")
    review_parser.add_argument("--threshold", type=float, default=0.70)
    review_parser.add_argument("--limit", type=int, default=100)

    extract_parser = subparsers.add_parser(
        "extract", help="Escalate extraction for an existing artifact"
    )
    extract_parser.add_argument("artifact_id")
    extract_parser.add_argument("--ocr", choices=["tesseract"], required=True)
    extract_parser.add_argument("--threshold", type=float, default=0.70)
    extract_parser.add_argument("--language", default="eng")
    extract_parser.add_argument("--dpi", type=int, default=200)
    extract_parser.add_argument("--force", action="store_true")

    subparsers.add_parser("index", help="Rebuild the disposable lexical evidence index")

    search_parser = subparsers.add_parser("search", help="Search preferred evidence with FTS5")
    search_parser.add_argument("query")
    search_parser.add_argument("--limit", type=int, default=20)

    lookup_parser = subparsers.add_parser(
        "lookup", help="Look up evidence by an exact publisher-native identifier"
    )
    lookup_parser.add_argument("native_identifier")

    evaluate_parser = subparsers.add_parser(
        "evaluate", help="Run a retrieval benchmark against explicit evidence targets"
    )
    evaluate_parser.add_argument("suite")
    evaluate_parser.add_argument("--k", type=int, default=5)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    state_dir = Path(args.state_dir)

    if args.command == "ingest":
        result = Ingestor(state_dir).ingest(
            args.path,
            source_uri=args.source_uri,
            source_name=args.source_name,
            native_identifier=args.native_id,
        )
        print(json.dumps(result.to_dict(), indent=2, sort_keys=True))
        return 0

    if args.command == "watch":
        manifest = load_manifest(args.manifest)
        result = CorpusWatcher(state_dir).run(manifest)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0

    if args.command == "review":
        items = review_queue(state_dir, threshold=args.threshold, limit=args.limit)
        print(json.dumps([item.to_dict() for item in items], indent=2, sort_keys=True))
        return 0

    if args.command == "extract":
        backend = PyMuPDFTesseractBackend(language=args.language, dpi=args.dpi)
        result = ProgressiveExtractor(state_dir).run_ocr(
            args.artifact_id,
            backend,
            threshold=args.threshold,
            force=args.force,
        )
        print(json.dumps(result.to_dict(), indent=2, sort_keys=True))
        return 0 if result.failed == 0 else 1

    if args.command == "index":
        result = SearchIndex(state_dir).rebuild()
        print(json.dumps(result.to_dict(), indent=2, sort_keys=True))
        return 0

    if args.command == "search":
        hits = SearchIndex(state_dir).search(args.query, limit=args.limit)
        print(json.dumps([hit.to_dict() for hit in hits], indent=2, sort_keys=True))
        return 0

    if args.command == "lookup":
        hits = SearchIndex(state_dir).lookup_native_identifier(args.native_identifier)
        print(json.dumps([hit.to_dict() for hit in hits], indent=2, sort_keys=True))
        return 0

    if args.command == "evaluate":
        suite = load_retrieval_suite(args.suite)
        result = RetrievalEvaluator(state_dir).run(suite, k=args.k)
        print(json.dumps(result.to_dict(), indent=2, sort_keys=True))
        return 0

    store = ProoflineStore(state_dir / "proofline.db")
    if args.command == "status":
        status = store.status()
        status["needs_review"] = review_count(state_dir)
        current_build = SearchIndex(state_dir).current_build()
        status["search_index_build"] = current_build
        print(json.dumps(status, indent=2, sort_keys=True))
        return 0

    if args.command == "trace":
        trace = store.trace_observation(args.observation_id)
        if trace is None:
            print(f"observation not found: {args.observation_id}", file=sys.stderr)
            return 2
        for item in trace.get("evidence", []):
            reference = item.get("reference") or {}
            evidence_id = reference.get("evidence_id")
            if evidence_id:
                item["preferred_extraction"] = preferred_extraction(store, evidence_id)
        print(json.dumps(trace, indent=2, sort_keys=True))
        return 0

    if args.command == "changes":
        changes = WatcherStore(state_dir / "proofline.db").recent_changes(
            limit=args.limit,
            include_unchanged=args.include_unchanged,
            run_id=args.run_id,
        )
        print(json.dumps(changes, indent=2, sort_keys=True))
        return 0

    raise AssertionError(f"unhandled command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
