"""Build paper data, tables and figures from the canonical evidence freeze.

Writes paper/data/paper-data.json and values.tex (every manuscript number),
paper/tables/*.tex and paper/figures/*.pdf with figures.json provenance.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from evaluation.research.paper import build_paper_data, values_tex
from evaluation.research.paper_assets import build_all


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--freeze", type=Path, default=Path("research/evidence/freeze-v2")
    )
    parser.add_argument("--paper", type=Path, default=Path("paper"))
    args = parser.parse_args(argv)
    data = build_paper_data(args.freeze, args.paper / "data" / "claims-spec.json")
    (args.paper / "data" / "paper-data.json").write_text(
        json.dumps(data, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    (args.paper / "data" / "values.tex").write_text(values_tex(data), encoding="utf-8")
    provenance = build_all(args.freeze, args.paper)
    print(
        json.dumps(
            {
                "claims": len(data["claims"]),
                "tables": sorted(provenance["tables"]),
                "figures": [f["figure_id"] for f in provenance["figures"]],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
