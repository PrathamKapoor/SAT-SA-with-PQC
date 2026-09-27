"""Write research/evidence/catalog.json from a freeze and a claim spec."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from evaluation.research.catalog import build_catalog


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--freeze", type=Path, required=True)
    parser.add_argument("--spec", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    catalog = build_catalog(args.freeze, args.spec)
    args.out.write_text(
        json.dumps(catalog, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    statuses: dict[str, int] = {}
    for entry in catalog["entries"]:
        statuses[entry["status"]] = statuses.get(entry["status"], 0) + 1
    print(json.dumps({"entries": len(catalog["entries"]), "statuses": statuses}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
