"""CLI for retrieval-blind benchmark pool generation.

Kept separate from the main Proofline CLI for the R1 experiment so benchmark sampling can be
validated independently before it becomes part of the stable command surface.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .benchmark_sources import load_benchmark_source_policy
from .benchmarking import RetrievalBenchmarkPoolBuilder


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m proofline.benchmark_cli")
    parser.add_argument("--state-dir", default=".proofline")
    parser.add_argument("--output", required=True)
    parser.add_argument("--max-per-kind", type=int, default=6)
    parser.add_argument("--max-targets", type=int, default=5)
    parser.add_argument("--source-policy")
    parser.add_argument(
        "--name",
        default="Proofline R1 deterministic real-corpus benchmark candidate pool",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    source_policy = (
        load_benchmark_source_policy(args.source_policy) if args.source_policy else None
    )
    pool = RetrievalBenchmarkPoolBuilder(
        args.state_dir,
        source_policy=source_policy,
    ).build(
        name=args.name,
        max_per_kind=args.max_per_kind,
        max_targets=args.max_targets,
    )
    destination = Path(args.output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(pool, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(destination),
                "cases": len(pool["cases"]),
                "selection": pool["selection"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
