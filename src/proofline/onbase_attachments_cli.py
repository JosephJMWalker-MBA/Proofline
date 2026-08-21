"""CLI for publisher-linked OnBase Supporting Documents."""

from __future__ import annotations

import argparse
import json

from .onbase import OnBaseAgendaDiscoverer, OnBaseDiscoveryResult, load_onbase_agenda_plan
from .onbase_attachments import OnBaseAttachmentDiscoverer


def _canonical_payload(
    agenda_result: OnBaseDiscoveryResult,
    canonical_sync: dict,
) -> dict:
    """Preserve publisher meeting metadata alongside canonical sync accounting."""
    return {
        "meeting_count": len(agenda_result.meetings),
        "meetings": [meeting.to_dict() for meeting in agenda_result.meetings],
        "agenda_item_count": agenda_result.agenda_item_count,
        "manifest_sha256": agenda_result.discovery.manifest_sha256,
        "sync_counts": canonical_sync["counts"],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="proofline-onbase-attachments",
        description=(
            "Derive publisher-linked OnBase Supporting Documents from preserved canonical "
            "agenda-item evidence and optionally sync a bounded or explicit full set."
        ),
    )
    parser.add_argument("plan", help="proofline-onbase-agenda-plan/v1 JSON file")
    parser.add_argument("--state-dir", default=".proofline", help="Proofline state directory")
    parser.add_argument("--manifest-out", help="write the full derived attachment manifest")
    parser.add_argument("--relations-out", help="write publisher-backed item/attachment relations")
    parser.add_argument("--rejections-out", help="write non-promotable supporting links and reasons")
    sync = parser.add_mutually_exclusive_group()
    sync.add_argument(
        "--sync-limit",
        type=int,
        help="sync at most N deterministically selected attachment sources",
    )
    sync.add_argument(
        "--sync-all",
        action="store_true",
        help="explicitly sync every discovered attachment source",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.sync_limit is not None and args.sync_limit < 1:
        raise SystemExit("--sync-limit must be a positive integer")

    plan = load_onbase_agenda_plan(args.plan)
    agenda = OnBaseAgendaDiscoverer(args.state_dir)
    agenda_result = agenda.run(plan)
    if not agenda_result.discovery.manifest.resources:
        raise SystemExit("OnBase discovery produced no canonical agenda-item resources")

    canonical_sync = agenda.watcher.run(agenda_result.discovery.manifest)
    if canonical_sync["counts"]["unavailable"]:
        raise SystemExit(
            "canonical OnBase sync is incomplete; attachment discovery requires all parent items"
        )

    attachments = OnBaseAttachmentDiscoverer(args.state_dir)
    result = attachments.discover(plan, agenda_result.discovery.manifest)

    if args.manifest_out:
        attachments.write_manifest(result, args.manifest_out)
    if args.relations_out:
        attachments.write_relations(result, args.relations_out)
    if args.rejections_out:
        attachments.write_rejections(result, args.rejections_out)

    payload = {
        "schema": "proofline-onbase-attachment-run/v1",
        "canonical": _canonical_payload(agenda_result, canonical_sync),
        "attachments": {
            "manifest": result.manifest.name,
            "manifest_sha256": result.manifest_sha256,
            "resource_count": len(result.manifest.resources),
            "relation_count": len(result.relations),
            "rejected_link_count": len(result.rejected_links),
            "parent_item_count": result.parent_item_count,
            "items_with_support_marker": result.items_with_support_marker,
            "items_with_accepted_links": result.items_with_accepted_links,
        },
    }

    if args.sync_all:
        payload["attachment_sync"] = attachments.sync(result)
    elif args.sync_limit is not None:
        payload["attachment_sync"] = attachments.sync(result, limit=args.sync_limit)

    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
