"""Regenerate paper tables (CSV, Markdown, LaTeX) from experiment bundles."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from evaluation.research.tables import export_tables


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--bundles",
        type=Path,
        required=True,
        help="directory containing experiment bundle directories",
    )
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument(
        "--only",
        nargs="+",
        help="bundle directory names to include (default: every bundle found)",
    )
    args = parser.parse_args(argv)
    bundles = [
        path
        for path in sorted(args.bundles.iterdir())
        if (path / "manifest.json").is_file()
        and (not args.only or path.name in args.only)
    ]
    record = export_tables(bundles, args.out)
    print(
        json.dumps(
            {
                "sources": [s["bundle"] for s in record["sources"]],
                "skipped": record["skipped"],
                "tables": len(record["tables"]),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
