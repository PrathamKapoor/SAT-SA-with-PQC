"""Build a research evidence freeze from a committed selection file.

Selection JSON: {"freeze_id": ..., "bundles": [{"path", "role", "note"}],
"supporting_files": [{"path", "note"}]}. The freeze records the current Git
commit as the tool commit and refuses to overwrite an existing freeze.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from evaluation.research.freeze import build_freeze


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--selection", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    selection = json.loads(args.selection.read_text(encoding="utf-8"))
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True
    ).stdout.strip()
    record = build_freeze(
        [{**item, "path": Path(item["path"])} for item in selection["bundles"]],
        args.out,
        freeze_id=selection["freeze_id"],
        canonical_commit=commit,
        supporting_files=[
            {**item, "path": Path(item["path"])}
            for item in selection.get("supporting_files", [])
        ],
    )
    print(
        json.dumps(
            {
                "freeze_id": record["freeze_id"],
                "tool_commit": commit,
                "bundles": {b["bundle"]: b["role"] for b in record["bundles"]},
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
