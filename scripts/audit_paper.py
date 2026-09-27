"""Audit the manuscript: numbers vs the evidence freeze, citations, claim wording.

Exits non-zero when any audit reports a problem.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from evaluation.research.paper_audit import run_audit


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--freeze", type=Path, default=Path("research/evidence/freeze-v2")
    )
    parser.add_argument("--paper", type=Path, default=Path("paper"))
    parser.add_argument(
        "--skip-numbers",
        action="store_true",
        help="skip regenerating paper data, tables and figures",
    )
    args = parser.parse_args(argv)
    report = run_audit(args.freeze, args.paper, numbers=not args.skip_numbers)
    print(json.dumps(report, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
