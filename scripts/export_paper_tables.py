"""Regenerate paper tables (CSV, Markdown, LaTeX) and figure data from bundles."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from evaluation.research.figures import export_figures
from evaluation.research.tables import export_tables


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--freeze",
        type=Path,
        help="evidence freeze directory; exports its bundles and checks manifests",
    )
    parser.add_argument(
        "--bundles",
        type=Path,
        help="directory containing experiment bundle directories",
    )
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument(
        "--only",
        nargs="+",
        help="bundle directory names to include (default: every bundle found)",
    )
    args = parser.parse_args(argv)
    expected = None
    if args.freeze:
        record = json.loads((args.freeze / "freeze.json").read_text(encoding="utf-8"))
        # Only canonical bundles feed paper tables and figures; superseded and
        # historical bundles stay in the freeze for verification only.
        expected = {
            b["bundle"]: b["manifest_sha256"]
            for b in record["bundles"]
            if b["role"] == "canonical"
        }
        args.only = sorted(expected)
        args.bundles = args.freeze / "bundles"
    if args.bundles is None:
        parser.error("give --freeze or --bundles")
    bundles = [
        path
        for path in sorted(args.bundles.iterdir())
        if (path / "manifest.json").is_file()
        and (not args.only or path.name in args.only)
    ]
    record = export_tables(bundles, args.out, expected_manifests=expected)
    figures = export_figures(bundles, args.out / "figures", expected_manifests=expected)
    print(
        json.dumps(
            {
                "sources": [s["bundle"] for s in record["sources"]],
                "skipped": record["skipped"],
                "tables": len(record["tables"]),
                "figures": [
                    f["figure_id"] for f in figures["figures"] if "data_file" in f
                ],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
