"""Phase 46 — large-scale performance benchmark.

Uses the existing deterministic synthetic dataset generator.
Measures actual timings for ingestion, analytics, risk,
prioritization, trust, and verification at 5 / 50 / 100 CSEs.

Honest measurement only. No extrapolation.
"""
from __future__ import annotations

import json
import tempfile
import time
from pathlib import Path

from qsmlops.crypto.hashing import digest_document
from qsmlops.database.engine import SQLiteDatabaseEngine
from qsmlops.database.migrations import MigrationRunner
from satsa.analysis.synth import GenConfig, generate
from satsa.service import SatsaService
from satsa.analysis.canonical import live_finding_digest
from satsa.analysis.trust import TrustService


SCALES = [
    (5, 20, 5),
    (10, 50, 10),
    (25, 100, 15),
    (50, 100, 20),
]


def benchmark(num_cse, num_alerts, num_assets):
    td = Path(tempfile.mkdtemp(prefix=f"perf_{num_cse}cse_"))
    try:
        eng = SQLiteDatabaseEngine(td / "x.db")
        eng.connect()
        MigrationRunner(eng).migrate()
        svc = SatsaService(eng)
        key_dir = td / "keys"

        cfg = GenConfig(
            seed=42, num_cse=num_cse, num_alerts=num_alerts,
            num_cases=max(2, num_alerts // 4),
            num_assets=num_assets,
        )
        out = td / "sub"
        generate(cfg, out)

        timings = {
            "ingest": 0.0, "run": 0.0, "risk": 0.0,
            "verify": 0.0,
        }
        finding_count = 0
        record_count = 0

        for cse_dir in sorted(out.iterdir()):
            if not cse_dir.is_dir():
                continue
            e = svc.register_entity(cse_dir.name, sector=cfg.sector,
                                     environment_class=cfg.environment)
            a = svc.open_assessment(e.id, 1735689600.0, 1738281600.0)
            t0 = time.time()
            r = svc.submit(a.id, cse_dir)
            timings["ingest"] += time.time() - t0
            t0 = time.time()
            run = svc.run_analysis(e.id, a.id, trust_key_dir=key_dir)
            timings["run"] += time.time() - t0
            finding_count += len(run.finding_ids)
            t0 = time.time()
            svc.compute_risk(e.id)
            timings["risk"] += time.time() - t0
            t0 = time.time()
            svc.verify_run(run.run_id, key_dir)
            timings["verify"] += time.time() - t0

        # Count records in the database
        record_count = eng.query_one(
            "SELECT COUNT(*) AS c FROM satsa_findings")["c"]

        # Database file size
        db_size = (td / "x.db").stat().st_size

        # Mismatch check (honest reporting)
        mismatches = 0
        for r in eng.query_all("SELECT * FROM satsa_findings"):
            if r["content_digest"] != live_finding_digest(dict(r)):
                mismatches += 1

        eng.close()
        total = sum(timings.values())
        return {
            "scale": f"{num_cse}cse/{num_alerts}alerts/{num_assets}assets",
            "findings": finding_count,
            "records": record_count,
            "db_size_kb": db_size // 1024,
            "mismatches": mismatches,
            "ingest_s": round(timings["ingest"], 3),
            "run_s": round(timings["run"], 3),
            "risk_s": round(timings["risk"], 3),
            "verify_s": round(timings["verify"], 3),
            "total_s": round(total, 3),
            "records_per_sec": round(record_count / total, 1) if total > 0 else 0,
        }
    finally:
        import shutil
        shutil.rmtree(td, ignore_errors=True)


def main():
    print(f"{'Scale':<30} {'Findings':>9} {'Records':>9} "
          f"{'DB KB':>7} {'Mismatch':>9} {'Ingest':>8} {'Run':>8} "
          f"{'Risk':>8} {'Verify':>8} {'Total':>8} {'rec/s':>8}")
    print("-" * 122)
    for num_cse, num_alerts, num_assets in SCALES:
        result = benchmark(num_cse, num_alerts, num_assets)
        print(
            f"{result['scale']:<30} {result['findings']:>9} "
            f"{result['records']:>9} {result['db_size_kb']:>7} "
            f"{result['mismatches']:>9} {result['ingest_s']:>8} "
            f"{result['run_s']:>8} {result['risk_s']:>8} "
            f"{result['verify_s']:>8} {result['total_s']:>8} "
            f"{result['records_per_sec']:>8}"
        )


if __name__ == "__main__":
    main()
