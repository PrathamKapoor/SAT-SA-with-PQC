"""Build or verify a write-once publication snapshot of the paper package."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from evaluation.research.publication import build_publication, verify_publication


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify", type=Path, help="verify an existing snapshot")
    parser.add_argument("--paper", type=Path, default=Path("paper"))
    parser.add_argument(
        "--freeze", type=Path, default=Path("research/evidence/freeze-v2")
    )
    parser.add_argument("--out", type=Path)
    parser.add_argument("--publication-id")
    parser.add_argument("--paper-commit")
    parser.add_argument("--manuscript-version")
    parser.add_argument("--literature-date")
    args = parser.parse_args(argv)
    if args.verify:
        result = verify_publication(args.verify)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if result["intact"] else 1
    required = {
        "--out": args.out,
        "--publication-id": args.publication_id,
        "--paper-commit": args.paper_commit,
        "--manuscript-version": args.manuscript_version,
        "--literature-date": args.literature_date,
    }
    missing = [flag for flag, value in required.items() if not value]
    if missing:
        parser.error(f"building a snapshot needs {', '.join(missing)}")
    record = build_publication(
        args.paper,
        args.freeze,
        args.out,
        publication_id=args.publication_id,
        paper_commit=args.paper_commit,
        manuscript_version=args.manuscript_version,
        literature_snapshot_date=args.literature_date,
    )
    print(
        json.dumps(
            {"publication_id": record["publication_id"], "files": len(record["files"])},
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
