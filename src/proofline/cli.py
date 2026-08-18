"""Command-line interface for the Proofline evidence core."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .ingest import Ingestor
from .storage import ProoflineStore


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

    store = ProoflineStore(state_dir / "proofline.db")
    if args.command == "status":
        print(json.dumps(store.status(), indent=2, sort_keys=True))
        return 0

    if args.command == "trace":
        trace = store.trace_observation(args.observation_id)
        if trace is None:
            print(f"observation not found: {args.observation_id}", file=sys.stderr)
            return 2
        print(json.dumps(trace, indent=2, sort_keys=True))
        return 0

    raise AssertionError(f"unhandled command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
