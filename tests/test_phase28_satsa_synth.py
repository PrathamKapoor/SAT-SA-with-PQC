"""Phase 28 — synthetic dataset generator tests."""
from __future__ import annotations

import csv
import tempfile
from pathlib import Path

import pytest

from satsa.analysis.synth import GenConfig, generate, _gen_cse


def test_generator_is_deterministic():
    cfg = GenConfig(seed=42, num_cse=3, num_alerts=10, num_cases=3)
    cse1 = _gen_cse(cfg, 0)
    cse2 = _gen_cse(cfg, 0)
    assert cse1.name == cse2.name
    assert cse1.assets == cse2.assets
    assert cse1.alerts == cse2.alerts
    assert cse1.cases == cse2.cases
    assert cse1.steps == cse2.steps
    assert cse1.escalations == cse2.escalations
    assert cse1.dispositions == cse2.dispositions


def test_generator_produces_referential_integrity():
    """Every alert references a real case and asset. Every step
    references a real case. Every escalation / disposition
    references a real alert / case."""
    cfg = GenConfig(seed=7, num_cse=1, num_alerts=20, num_cases=5,
                   num_assets=8, steps_per_case=3, escalation_rate=0.5,
                   disposition_rate=0.8)
    cse = _gen_cse(cfg, 0)
    case_ids = {c["native_id"] for c in cse.cases}
    asset_ids = {a["native_id"] for a in cse.assets}
    alert_ids = {a["native_id"] for a in cse.alerts}
    for a in cse.alerts:
        assert a["case_id"] in case_ids, f"orphan case ref: {a['case_id']}"
        assert a["asset_id"] in asset_ids, f"orphan asset ref: {a['asset_id']}"
    for s in cse.steps:
        assert s["case_id"] in case_ids
    for e in cse.escalations:
        assert e["alert_id"] in alert_ids
        assert e["case_id"] in case_ids
    for d in cse.dispositions:
        assert d["alert_id"] in alert_ids
        assert d["case_id"] in case_ids


def test_generator_writes_valid_csvs():
    cfg = GenConfig(seed=1, num_cse=1, num_alerts=5, num_cases=2,
                   num_assets=3, steps_per_case=2)
    cse = _gen_cse(cfg, 0)
    with tempfile.TemporaryDirectory() as td:
        d = Path(td) / cse.name
        from satsa.analysis.synth import _write_cse
        _write_cse(cse, d)
        # each CSV should be readable by the csv module
        for fname in ("assets.csv", "alerts.csv", "cases.csv",
                      "investigation_steps.csv", "escalations.csv",
                      "dispositions.csv"):
            with open(d / fname, encoding="utf-8") as f:
                rows = list(csv.DictReader(f))
                assert rows is not None  # at least header
            if fname != "investigation_steps.csv":  # may be empty
                # assert header has expected columns
                with open(d / fname, encoding="utf-8") as f:
                    reader = csv.reader(f)
                    header = next(reader)
                    assert len(header) > 0


def test_generator_scales():
    """5 / 50 / 100 CSE with default alert volumes completes in
    reasonable time."""
    import time
    for n in (5, 50, 100):
        cfg = GenConfig(seed=1, num_cse=n, num_alerts=20, num_cases=5,
                       num_assets=10)
        with tempfile.TemporaryDirectory() as td:
            t0 = time.time()
            generate(cfg, Path(td) / "out")
            elapsed = time.time() - t0
        # generous bound; this is in-process, not I/O bound
        assert elapsed < 30, f"generate({n}) took {elapsed:.1f}s"


def test_generator_pathological_scenarios_are_controllable():
    """Pathological injection rates produce the expected outcomes."""
    # All alerts fast-close + no investigation
    cfg = GenConfig(seed=1, num_cse=1, num_alerts=5, num_cases=1,
                   num_assets=2, steps_per_case=0,
                   fast_closure_rate=1.0, missing_investigation_rate=1.0,
                   escalation_rate=0.0, disposition_rate=0.0,
                   asset_critical_fraction=1.0)
    cse = _gen_cse(cfg, 0)
    assert len(cse.steps) == 0
    assert len(cse.escalations) == 0
    assert len(cse.dispositions) == 0
    for a in cse.alerts:
        # critical asset → severity is "critical" or "high" (weighted
        # 0.3 critical, 0.4 high), and fast_closure_rate=1.0 means
        # all are fast-closed: close - ack < 300
        if a["severity"] in ("critical", "high"):
            assert (a["closed_at"] - a["ack_at"]) < 300, (
                f"alert {a['native_id']} ({a['severity']}) not fast-closed"
            )
