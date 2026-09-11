"""Phase 29 — performance benchmark.

Measures real ingestion / analytics / risk / trust / verification
times on the synthetic dataset. Reports actual numbers; does not
extrapolate.
"""
from __future__ import annotations

import json
import time
import tempfile
from pathlib import Path

import pytest

from qsmlops.database.engine import SQLiteDatabaseEngine
from qsmlops.database.migrations import MigrationRunner
from satsa.analysis.synth import GenConfig, generate
from satsa.service import SatsaService
from satsa.analysis.run import RunService
from satsa.analysis.trust import TrustService


@pytest.mark.parametrize("num_cse,num_alerts", [(5, 20), (10, 50), (25, 100)])
def test_performance_at_scale(tmp_path, num_cse, num_alerts):
    """Run the full pipeline at three scales and report timings."""
    cfg = GenConfig(seed=42, num_cse=num_cse, num_alerts=num_alerts,
                   num_cases=max(2, num_alerts // 4),
                   num_assets=max(4, num_cse * 2))
    out = tmp_path / "sub"
    generate(cfg, out)
    db_path = tmp_path / "bench.db"
    eng = SQLiteDatabaseEngine(db_path); eng.connect()
    MigrationRunner(eng).migrate()
    svc = SatsaService(eng)
    key_dir = tmp_path / "keys"

    # Register + open + submit + run + risk + verify for each CSE
    timings = {"ingest": 0.0, "run": 0.0, "risk": 0.0, "verify": 0.0}
    finding_count = 0
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
    eng.close()
    print(f"\n=== benchmark: {num_cse} CSEs, {num_alerts} alerts/CSE ===")
    print(f"  findings total: {finding_count}")
    for k, v in timings.items():
        print(f"  {k}: {v*1000:.0f}ms total")
    # Sanity: all stages completed
    assert timings["ingest"] > 0
    assert timings["run"] > 0
    # No hard upper bound — these are real measurements
