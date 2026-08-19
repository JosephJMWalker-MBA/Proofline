"""CLI for the generic OnBase Agenda Online transfer adapter."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .onbase import OnBaseAgendaDiscoverer, load_onbase_agenda_plan


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="proofline-onbase",
        description="Discover and optionally sync canonical OnBase Agenda Online agenda-item evidence.",
    )
    parser.add_argument("plan", help="proofline-onbase-agenda-plan/v1 JSON file")
    parser.add_argument("--state-dir", default=".proofline", help="Proofline state directory")
    parser.add_argument("--manifest-out", help="write the derived source manifest to this path")
    parser.add_argument(
        "--discover-only",
        action="store_true",
        help="preserve search/tree provenance and emit the manifest without syncing agenda items",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    plan = load_onbase_agenda_plan(args.plan)
    discoverer = OnBaseAgendaDiscoverer(args.state_dir)
    result = discoverer.run(plan)
    if args.manifest_out:
        discoverer.write_manifest(result, Path(args.manifest_out))

    payload = result.to_dict()
    if not args.discover_only:
        if not result.discovery.manifest.resources:
            raise SystemExit("OnBase discovery produced no canonical agenda-item resources")
        payload["canonical_sync"] = discoverer.watcher.run(result.discovery.manifest)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
