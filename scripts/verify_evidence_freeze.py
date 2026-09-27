"""Verify every hash recorded in a research evidence freeze."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from evaluation.research.freeze import verify_freeze


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("freeze_dir", type=Path)
    args = parser.parse_args(argv)
    result = verify_freeze(args.freeze_dir)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["intact"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
