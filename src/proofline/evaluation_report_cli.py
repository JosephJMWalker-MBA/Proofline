"""CLI for deriving scorable retrieval metrics from a saved evaluation result."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .evaluation_reporting import build_scorable_report, load_evaluation_result


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m proofline.evaluation_report_cli")
    parser.add_argument("evaluation", help="Saved proofline retrieval evaluation JSON")
    parser.add_argument("--output")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    report = build_scorable_report(load_evaluation_result(args.evaluation))
    payload = report.to_dict()
    rendered = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if args.output:
        destination = Path(args.output)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
