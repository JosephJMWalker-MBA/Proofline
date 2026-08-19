"""CLI for retrieval-blind benchmark candidate curation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .benchmark_curation import curate_benchmark_pool


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m proofline.benchmark_curate_cli")
    parser.add_argument("input")
    parser.add_argument("--output", required=True)
    parser.add_argument("--max-per-kind", type=int, default=6)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    source = Path(args.input)
    pool = json.loads(source.read_text(encoding="utf-8"))
    curated = curate_benchmark_pool(pool, max_per_kind=args.max_per_kind)
    destination = Path(args.output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(curated, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "input": str(source),
                "output": str(destination),
                "selection": curated["selection"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
