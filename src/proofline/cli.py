"""Command-line interface for Proofline."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .discovery import SourceDiscoverer, load_discovery_plan, manifest_to_dict
from .evaluation import RetrievalEvaluator, load_retrieval_suite
from .hashing import sha256_text
from .indirection import discover_pointer_pdf_resources
from .ingest import Ingestor
from .ocr import PyMuPDFTesseractBackend
from .progressive import ProgressiveExtractor
from .review import preferred_extraction, review_count, review_queue
from .search import SearchIndex
from .storage import ProoflineStore
from .structured import StructuredIndex
from .watcher import CorpusWatcher, SourceManifest, load_manifest
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

    discover_parser = subparsers.add_parser(
        "discover", help="Derive a deterministic watch manifest from official public indexes"
    )
    discover_parser.add_argument("plan")
    discover_parser.add_argument("--output")

    sync_parser = subparsers.add_parser(
        "sync", help="Discover current resources and immediately watch the discovered manifest"
    )
    sync_parser.add_argument("plan")
    sync_parser.add_argument("--manifest-output")

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

    subparsers.add_parser(
        "index", help="Rebuild disposable lexical and structured evidence indexes"
    )

    search_parser = subparsers.add_parser("search", help="Search preferred evidence with FTS5")
    search_parser.add_argument("query")
    search_parser.add_argument("--limit", type=int, default=20)

    lookup_parser = subparsers.add_parser(
        "lookup", help="Look up evidence by an exact publisher-native identifier"
    )
    lookup_parser.add_argument("native_identifier")

    amount_parser = subparsers.add_parser(
        "amounts", help="Find evidence containing deterministically normalized monetary values"
    )
    amount_parser.add_argument("--min", dest="minimum", type=float)
    amount_parser.add_argument("--max", dest="maximum", type=float)
    amount_parser.add_argument("--limit", type=int, default=100)

    dates_parser = subparsers.add_parser("dates", help="Find evidence by normalized date range")
    dates_parser.add_argument("--from", dest="start")
    dates_parser.add_argument("--to", dest="end")
    dates_parser.add_argument("--limit", type=int, default=100)

    identifier_parser = subparsers.add_parser(
        "identifier", help="Find an identifier extracted from evidence content"
    )
    identifier_parser.add_argument("value")
    identifier_parser.add_argument("--limit", type=int, default=100)

    evaluate_parser = subparsers.add_parser(
        "evaluate", help="Run a retrieval benchmark against explicit evidence targets"
    )
    evaluate_parser.add_argument("suite")
    evaluate_parser.add_argument("--k", type=int, default=5)

    return parser


def _discover(state_dir: Path, plan_path: str, output: str | None):
    plan = load_discovery_plan(plan_path)
    discoverer = SourceDiscoverer(state_dir)
    result = discoverer.run(plan)
    destination = Path(output) if output else state_dir / "manifests" / f"{plan.name}.json"
    discoverer.write_manifest(result, destination)
    return plan, result, destination


def _write_manifest(path: Path, manifest: SourceManifest) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(manifest_to_dict(manifest), indent=2, sort_keys=True) + "\n"
    path.write_text(serialized, encoding="utf-8")
    return sha256_text(serialized)


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

    if args.command == "discover":
        _, result, destination = _discover(state_dir, args.plan, args.output)
        payload = result.to_dict()
        payload["manifest_path"] = str(destination)
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0

    if args.command == "sync":
        plan, discovered, destination = _discover(
            state_dir, args.plan, args.manifest_output
        )
        watcher = CorpusWatcher(state_dir)
        watched = watcher.run(discovered.manifest)

        linked_resources = discover_pointer_pdf_resources(
            state_dir,
            discovered.manifest,
            watched,
        )
        linked_watch: dict | None = None
        final_manifest = discovered.manifest
        if linked_resources:
            linked_manifest = SourceManifest(
                name=f"{plan.name}:linked-records",
                resources=linked_resources,
            )
            linked_watch = watcher.run(linked_manifest)
            by_uri = {resource.source_uri: resource for resource in discovered.manifest.resources}
            for resource in linked_resources:
                by_uri[resource.source_uri] = resource
            final_manifest = SourceManifest(
                name=discovered.manifest.name,
                resources=tuple(by_uri[uri] for uri in sorted(by_uri)),
            )

        final_manifest_sha256 = _write_manifest(destination, final_manifest)
        lexical = SearchIndex(state_dir).rebuild()
        structured = StructuredIndex(state_dir).rebuild()
        print(
            json.dumps(
                {
                    "plan": plan.name,
                    "manifest_path": str(destination),
                    "manifest_sha256": final_manifest_sha256,
                    "discovery": discovered.to_dict(),
                    "watch": watched,
                    "linked_resources": [
                        {
                            key: value
                            for key, value in manifest_to_dict(
                                SourceManifest(name="linked", resources=(resource,))
                            )["resources"][0].items()
                        }
                        for resource in linked_resources
                    ],
                    "linked_watch": linked_watch,
                    "indexes": {
                        "lexical": lexical.to_dict(),
                        "structured": structured.to_dict(),
                    },
                },
                indent=2,
                sort_keys=True,
            )
        )
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
        lexical = SearchIndex(state_dir).rebuild()
        structured = StructuredIndex(state_dir).rebuild()
        print(
            json.dumps(
                {"lexical": lexical.to_dict(), "structured": structured.to_dict()},
                indent=2,
                sort_keys=True,
            )
        )
        return 0

    if args.command == "search":
        hits = SearchIndex(state_dir).search(args.query, limit=args.limit)
        print(json.dumps([hit.to_dict() for hit in hits], indent=2, sort_keys=True))
        return 0

    if args.command == "lookup":
        hits = SearchIndex(state_dir).lookup_native_identifier(args.native_identifier)
        print(json.dumps([hit.to_dict() for hit in hits], indent=2, sort_keys=True))
        return 0

    if args.command == "amounts":
        hits = StructuredIndex(state_dir).money(
            minimum=args.minimum,
            maximum=args.maximum,
            limit=args.limit,
        )
        print(json.dumps([hit.to_dict() for hit in hits], indent=2, sort_keys=True))
        return 0

    if args.command == "dates":
        hits = StructuredIndex(state_dir).dates(
            start=args.start,
            end=args.end,
            limit=args.limit,
        )
        print(json.dumps([hit.to_dict() for hit in hits], indent=2, sort_keys=True))
        return 0

    if args.command == "identifier":
        hits = StructuredIndex(state_dir).identifier(args.value, limit=args.limit)
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
        status["search_index_build"] = SearchIndex(state_dir).current_build()
        status["structured_index_build"] = StructuredIndex(state_dir).current_build()
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
