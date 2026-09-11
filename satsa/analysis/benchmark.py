"""Performance benchmark helper — prints the scaling benchmark
the audit calls out as required. The committed benchmark lives
in ``reports/scaling_benchmark.csv``; this module reads it and
prints a small summary, plus lets the CLI run a fresh benchmark
on demand.
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Optional


BENCHMARK_CSV = Path(__file__).resolve().parents[2] / "reports" / "scaling_benchmark.csv"


def print_benchmark(scaling_csv: Optional[Path] = None) -> None:
    """Print a small summary of the latest scaling benchmark."""
    p = Path(scaling_csv) if scaling_csv else BENCHMARK_CSV
    if not p.exists():
        print(f"benchmark file {p} not found; run scripts/benchmark_scaling.py")
        return
    rows = []
    with p.open("r", encoding="utf-8") as f:
        header = f.readline().strip().split(",")
        for line in f:
            cells = [c.strip() for c in line.strip().split(",")]
            if len(cells) != len(header):
                continue
            rows.append(dict(zip(header, cells)))
    if not rows:
        print(f"benchmark file {p} is empty")
        return
    print(f"Scaling benchmark — {p}")
    print(f"  {'CSEs':>6}  {'runs':>6}  {'findings':>10}  {'elapsed_s':>10}")
    for r in rows:
        print(f"  {r.get('cse_count', '?'):>6}  "
              f"{r.get('run_count', '?'):>6}  "
              f"{r.get('finding_count', '?'):>10}  "
              f"{r.get('elapsed_seconds', '?'):>10}")