"""Assemble the IEEE Access submission package in paper/submission/.

Copies, without modification, everything the venue build needs: the shared
sections, the generated paper data, tables, figures and supplementary files, the
bibliography and literature matrix (so scripts/audit_paper.py --paper
paper/submission can audit the package), the vendored IEEE Access template files
and the venue wrapper as manuscript.tex. Build outputs (PDF, aux files) are not
touched. Run from the repository root:

    python paper/make_submission.py
    cd paper/submission && latexmk -pdf manuscript.tex
"""

from __future__ import annotations

import shutil
from pathlib import Path

PAPER = Path(__file__).resolve().parent
OUT = PAPER / "submission"
TREES = [
    "sections",
    "data",
    "tables",
    "figures",
    "figures-static",
    "figures-src",
    "supplementary",
]
FILES = ["references.bib", "literature-matrix.csv"]
SKIP = {"__pycache__"}


def main() -> None:
    OUT.mkdir(exist_ok=True)
    for name in TREES:
        target = OUT / name
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(PAPER / name, target, ignore=shutil.ignore_patterns(*SKIP))
    # Literature-search protocol and tables as supplementary material; the raw API
    # responses stay in the repository (paper/literature-review/raw).
    target = OUT / "supplementary" / "literature-review"
    shutil.copytree(
        PAPER / "literature-review", target, ignore=shutil.ignore_patterns("raw", *SKIP)
    )
    for name in FILES:
        shutil.copy2(PAPER / name, OUT / name)
    for f in (PAPER / "venue" / "ieee-access-template").iterdir():
        if f.name != "README.md":
            shutil.copy2(f, OUT / f.name)
    shutil.copy2(PAPER / "venue" / "ieee-access-manuscript.tex", OUT / "manuscript.tex")
    shutil.copy2(
        PAPER / "REPRODUCIBILITY.md", OUT / "supplementary" / "S9-reproducibility.md"
    )
    print(f"submission package assembled in {OUT}")


if __name__ == "__main__":
    main()
