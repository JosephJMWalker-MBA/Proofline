"""Command-line interface for Proofline."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .candidate_analysis import CandidateObservationRunner
from .discovery import SourceDiscoverer, load_discovery_plan
from .evaluation import RetrievalEvaluator, load_retrieval_suite
from .ingest import Ingestor
from .ocr import PyMuPDFTesseractBackend
from .progressive import ProgressiveExtractor
from .recurrence import SegmentRecurrenceClusterer
from .recurrence_packets import RecurrenceEvidencePacketBuilder
from .review import preferred_extraction, review_count, review_queue
from .search import SearchIndex
from .segment_similarity import SegmentSimilarityIndex
from .segments import SegmentIndex, load_segmentation_plan
from .storage import ProoflineStore
from .structured import StructuredIndex
from .version_analysis import VersionObservationRunner
from .watch_analysis import WatchChangeObservationRunner
from .watcher import CorpusWatcher, load_manifest
from .watch_storage import WatcherStore


def _add_recurrence_arguments(
    parser: argparse.ArgumentParser,
    *,
    include_limit: bool = True,
) -> None:
    parser.add_argument("--threshold", type=float, default=0.60)
    parser.add_argument("--shingle-size", type=int, default=3)
    parser.add_argument("--min-shared-shingles", type=int, default=3)
    parser.add_argument("--max-shingle-frequency", type=int, default=64)
    parser.add_argument("--rule", dest="rule_name")
    parser.add_argument("--type", dest="segment_type")
    parser.add_argument("--min-occurrences", type=int, default=2)
    if include_limit:
        parser.add_argument("--limit", type=int, default=100)


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
        "sync",
        help="Discover, watch, analyze source chronology and publisher-backed versions, and rebuild indexes",
    )
    sync_parser.add_argument("plan")
    sync_parser.add_argument("--manifest-output")

    subparsers.add_parser(
        "analyze-watch-changes",
        help="Promote substantive watcher changed transitions into source-change observations",
    )

    subparsers.add_parser(
        "analyze-versions",
        help="Derive publisher-backed version relations and run deterministic version comparisons",
    )

    candidates_parser = subparsers.add_parser(
        "analyze-candidates",
        help="Promote narrowly eligible recurrence fact variations into candidate observations",
    )
    _add_recurrence_arguments(candidates_parser, include_limit=False)
    candidates_parser.add_argument("--min-quality", type=float, default=0.70)

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

    segment_parser = subparsers.add_parser(
        "segment", help="Build a disposable source-profile segment index over preferred evidence"
    )
    segment_parser.add_argument("plan")

    repeated_parser = subparsers.add_parser(
        "repeated-segments",
        help="List exact normalized segments repeated across distinct artifacts",
    )
    repeated_parser.add_argument("--min-artifacts", type=int, default=2)
    repeated_parser.add_argument("--limit", type=int, default=100)

    anchor_parser = subparsers.add_parser(
        "segment-anchor", help="Find indexed segments by exact normalized anchor"
    )
    anchor_parser.add_argument("value")
    anchor_parser.add_argument("--type", dest="segment_type")
    anchor_parser.add_argument("--limit", type=int, default=100)

    near_parser = subparsers.add_parser(
        "near-segments",
        help="Find deterministic near-duplicate segment occurrences across distinct source families",
    )
    near_parser.add_argument("--threshold", type=float, default=0.60)
    near_parser.add_argument("--shingle-size", type=int, default=3)
    near_parser.add_argument("--min-shared-shingles", type=int, default=3)
    near_parser.add_argument("--max-shingle-frequency", type=int, default=64)
    near_parser.add_argument("--rule", dest="rule_name")
    near_parser.add_argument("--type", dest="segment_type")
    near_parser.add_argument("--limit", type=int, default=100)

    recurrence_parser = subparsers.add_parser(
        "recurrence-clusters",
        help="Cluster near-duplicate segment occurrences into deterministic recurrence groups",
    )
    _add_recurrence_arguments(recurrence_parser)

    packets_parser = subparsers.add_parser(
        "recurrence-packets",
        help="Enrich deterministic recurrence groups with structured facts inside each segment span",
    )
    _add_recurrence_arguments(packets_parser)

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
        watched = CorpusWatcher(state_dir).run(discovered.manifest)
        watch_change_analysis = WatchChangeObservationRunner(state_dir).run()
        version_analysis = VersionObservationRunner(state_dir).run()
        lexical = SearchIndex(state_dir).rebuild()
        structured = StructuredIndex(state_dir).rebuild()
        print(
            json.dumps(
                {
                    "plan": plan.name,
                    "manifest_path": str(destination),
                    "discovery": discovered.to_dict(),
                    "watch": watched,
                    "watch_change_analysis": watch_change_analysis.to_dict(),
                    "version_analysis": version_analysis.to_dict(),
                    "indexes": {
                        "lexical": lexical.to_dict(),
                        "structured": structured.to_dict(),
                    },
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0 if watch_change_analysis.failed == 0 and version_analysis.failed == 0 else 1

    if args.command == "analyze-watch-changes":
        result = WatchChangeObservationRunner(state_dir).run()
        print(json.dumps(result.to_dict(), indent=2, sort_keys=True))
        return 0 if result.failed == 0 else 1

    if args.command == "analyze-versions":
        result = VersionObservationRunner(state_dir).run()
        print(json.dumps(result.to_dict(), indent=2, sort_keys=True))
        return 0 if result.failed == 0 else 1

    if args.command == "analyze-candidates":
        result = CandidateObservationRunner(state_dir).run_recurrence_variations(
            threshold=args.threshold,
            shingle_size=args.shingle_size,
            min_shared_shingles=args.min_shared_shingles,
            max_shingle_frequency=args.max_shingle_frequency,
            rule_name=args.rule_name,
            segment_type=args.segment_type,
            min_occurrences=args.min_occurrences,
            min_quality=args.min_quality,
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

    if args.command == "segment":
        plan = load_segmentation_plan(args.plan)
        result = SegmentIndex(state_dir).rebuild(plan)
        print(json.dumps(result.to_dict(), indent=2, sort_keys=True))
        return 0

    if args.command == "repeated-segments":
        groups = SegmentIndex(state_dir).repeated(
            min_artifacts=args.min_artifacts,
            limit=args.limit,
        )
        print(json.dumps([group.to_dict() for group in groups], indent=2, sort_keys=True))
        return 0

    if args.command == "segment-anchor":
        hits = SegmentIndex(state_dir).anchor(
            args.value,
            segment_type=args.segment_type,
            limit=args.limit,
        )
        print(json.dumps([hit.to_dict() for hit in hits], indent=2, sort_keys=True))
        return 0

    if args.command == "near-segments":
        result = SegmentSimilarityIndex(state_dir).find(
            threshold=args.threshold,
            shingle_size=args.shingle_size,
            min_shared_shingles=args.min_shared_shingles,
            max_shingle_frequency=args.max_shingle_frequency,
            rule_name=args.rule_name,
            segment_type=args.segment_type,
            limit=args.limit,
        )
        print(json.dumps(result.to_dict(), indent=2, sort_keys=True))
        return 0

    if args.command == "recurrence-clusters":
        result = SegmentRecurrenceClusterer(state_dir).find(
            threshold=args.threshold,
            shingle_size=args.shingle_size,
            min_shared_shingles=args.min_shared_shingles,
            max_shingle_frequency=args.max_shingle_frequency,
            rule_name=args.rule_name,
            segment_type=args.segment_type,
            min_occurrences=args.min_occurrences,
            limit=args.limit,
        )
        print(json.dumps(result.to_dict(), indent=2, sort_keys=True))
        return 0

    if args.command == "recurrence-packets":
        result = RecurrenceEvidencePacketBuilder(state_dir).find(
            threshold=args.threshold,
            shingle_size=args.shingle_size,
            min_shared_shingles=args.min_shared_shingles,
            max_shingle_frequency=args.max_shingle_frequency,
            rule_name=args.rule_name,
            segment_type=args.segment_type,
            min_occurrences=args.min_occurrences,
            limit=args.limit,
        )
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
        status["segment_index_build"] = SegmentIndex(state_dir).current_build()
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
        trace["source_relations"] = VersionObservationRunner(state_dir).relations_for_observation(
            args.observation_id
        )
        trace["source_checks"] = WatchChangeObservationRunner(state_dir).checks_for_observation(
            args.observation_id
        )
        trace["detector_contexts"] = CandidateObservationRunner(state_dir).contexts_for_observation(
            args.observation_id
        )
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
