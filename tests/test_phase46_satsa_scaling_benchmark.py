"""Phase 46 — large-scale performance benchmark test."""
from __future__ import annotations

import time
import tempfile
from pathlib import Path

from satsa.analysis.synth import GenConfig, generate
from satsa.service import SatsaService
from satsa.analysis.canonical import live_finding_digest


def test_benchmark_5_cse_completes_quickly():
    td = Path(tempfile.mkdtemp())
    try:
        from qsmlops.crypto.hashing import digest_document
        from qsmlops.database.engine import SQLiteDatabaseEngine
        from qsmlops.database.migrations import MigrationRunner
        eng = SQLiteDatabaseEngine(td / "x.db"); eng.connect()
        MigrationRunner(eng).migrate()
        svc = SatsaService(eng)
        cfg = GenConfig(seed=42, num_cse=5, num_alerts=20, num_cases=5, num_assets=5)
        out = td / "sub"; generate(cfg, out)
        t0 = time.time()
        for cse_dir in sorted(out.iterdir()):
            e = svc.register_entity(cse_dir.name, sector=cfg.sector,
                                     environment_class=cfg.environment)
            a = svc.open_assessment(e.id, 1735689600.0, 1738281600.0)
            svc.submit(a.id, cse_dir)
            svc.run_analysis(e.id, a.id)
        elapsed = time.time() - t0
        # 5 CSEs should complete in well under 30 seconds
        assert elapsed < 30
        # All findings should have matching digests
        mismatches = 0
        for r in eng.query_all("SELECT * FROM satsa_findings"):
            if r["content_digest"] != live_finding_digest(dict(r)):
                mismatches += 1
        assert mismatches == 0
        eng.close()
    finally:
        import shutil; shutil.rmtree(td, ignore_errors=True)
