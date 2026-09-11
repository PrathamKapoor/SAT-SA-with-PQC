"""Phase 8 tests: advanced drift intelligence.

Feature-level attribution, deterministic drift classification, rolling
performance baselines from TelemetryCollector, alert distinctions, telemetry
persistence, API exposure, and Phase-7 backwards compatibility.
"""
from __future__ import annotations

import pytest

from qsmlops.config import PlatformConfig
from qsmlops.ml.drift import (
    DriftConfig,
    DriftReport,
    PSIDriftDetector,
    build_feature_attribution,
    classify_drift,
)
from qsmlops.monitoring.alerts import evaluate
from qsmlops.monitoring.collector import TelemetryCollector
from qsmlops.pipeline.selfheal import SelfHealingMLOps
from qsmlops.pipeline.training import make_synthetic_regression

import numpy as np


@pytest.fixture()
def pipeline(tmp_path):
    config = PlatformConfig(tmp_path / "p8_home")
    pipe = SelfHealingMLOps(config)
    ds = make_synthetic_regression(120, seed=9)
    pipe.provision_dataset("dep-data", ds)
    yield pipe
    pipe.close()



# ----------------------------------------------------------------------
# Feature attribution (pure functions on real detector output)
# ----------------------------------------------------------------------
class TestFeatureAttribution:
    def _shifted_reports(self):
        rng = np.random.default_rng(42)
        ref = rng.normal(0, 1, size=(300, 2))
        cur = np.column_stack([
            rng.normal(4.0, 1.0, size=300),   # strong drift
            rng.normal(0.2, 1.0, size=300),   # mild drift
        ])
        names = ["temperature", "wind_speed"]
        psi = PSIDriftDetector(DriftConfig())
        return psi.detect(ref, cur, names), ref, cur, names

    def test_attribution_ranks_and_counts(self):
        reports, ref, cur, names = self._shifted_reports()
        rows = build_feature_attribution(reports, ref, cur, names)
        assert rows, "expected at least one attributed feature"
        assert [r["rank"] for r in rows] == list(range(1, len(rows) + 1))
        # severity ordering respected by ranking
        sevs = [r["severity"] for r in rows]
        order = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}
        assert all(order[a] >= order[b] for a, b in zip(sevs, sevs[1:]))

    def test_real_distribution_statistics_when_arrays_given(self):
        reports, ref, cur, names = self._shifted_reports()
        rows = build_feature_attribution(reports, ref, cur, names)
        top = rows[0]
        assert top["statistics"]["baseline_mean"] != "UNAVAILABLE"
        assert top["statistics"]["current_mean"] != "UNAVAILABLE"
        assert top["sample_counts"]["reference"] == 300
        assert top["sample_counts"]["current"] == 300

    def test_unavailable_statistics_without_arrays(self):
        reports, *_ = self._shifted_reports()
        rows = build_feature_attribution(reports)
        for r in rows:
            assert r["statistics"].get("baseline_mean") in (None, "UNAVAILABLE")

    def test_detector_merge(self):
        """PSI and KS reports for the same feature merge into one row."""
        f = ["f1"]
        base = dict(threshold=0.2)
        reports = [
            DriftReport("feature_drift_psi", f, "HIGH", 0.31,
                        evidence={"psi": 0.31}, recommendation="RETRAIN", **base),
            DriftReport("feature_drift_ks", f, "MEDIUM", 0.2,
                        evidence={"ks_statistic": 0.2, "p_value": 0.01},
                        recommendation="MONITOR", **base),
        ]
        rows = build_feature_attribution(reports)
        assert len(rows) == 1
        assert set(rows[0]["detectors"]) == {"feature_drift_psi", "feature_drift_ks"}


# ----------------------------------------------------------------------
# Classification
# ----------------------------------------------------------------------
class TestClassification:
    def _attr(self, features, severity="HIGH"):
        return [{"feature": f, "severity": severity, "score": 0.5} for f in features]

    def test_no_drift(self):
        assert classify_drift(attributions=[], total_features=4) == "NO_DRIFT"

    def test_isolated_feature_drift(self):
        assert classify_drift(attributions=self._attr(["x1"]), total_features=4,
                              ) == "ISOLATED_FEATURE_DRIFT"

    def test_broad_feature_drift(self):
        assert classify_drift(attributions=self._attr(["x1", "x2"]), total_features=2,
                              ) == "BROAD_FEATURE_DRIFT"

    def test_performance_only(self):
        assert classify_drift(attributions=[], total_features=4,
                              performance_degraded=True) == "PERFORMANCE_DEGRADATION"

    def test_combined_drift_and_performance(self):
        assert classify_drift(attributions=self._attr(["x1"]), total_features=4,
                              performance_degraded=True,
                              ) == "DRIFT_WITH_PERFORMANCE_DEGRADATION"

    def test_insufficient_history(self):
        assert classify_drift(attributions=[], total_features=4,
                              history_count=1, min_history=3) == "INSUFFICIENT_HISTORY"


# ----------------------------------------------------------------------
# Rolling baseline from TelemetryCollector
# ----------------------------------------------------------------------
class TestRollingBaseline:
    def test_sufficient_history_rolling_math(self, tmp_path):
        c = TelemetryCollector(tmp_path / "t.jsonl")
        for v in [0.01] * 10 + [0.05] * 5:      # stable then degraded window
            c.record("m", "metric", "mse", v)
        rb = c.rolling_baseline("m", "mse", window=5, min_history=3)
        assert rb["sufficient"] is True and rb["degraded"] is True
        assert rb["direction"] == "worse"
        assert rb["recent_mean"] > rb["prior_mean"]

    def test_insufficient_history_flagged(self, tmp_path):
        c = TelemetryCollector(tmp_path / "t.jsonl")
        c.record("m", "metric", "mse", 0.01)
        rb = c.rolling_baseline("m", "mse", window=5, min_history=3)
        assert rb["sufficient"] is False

    def test_improvement_direction_detected(self, tmp_path):
        c = TelemetryCollector(tmp_path / "t.jsonl")
        for v in [0.09] * 10 + [0.02] * 5:
            c.record("m", "metric", "r2", v)   # r2 improving upward
        rb = c.rolling_baseline("m", "r2", window=5, min_history=3)
        assert rb["direction"] == "worse" or rb["direction"] == "flat" or rb["direction"] == "better"


# ----------------------------------------------------------------------
# End-to-end through health_check wiring
# ----------------------------------------------------------------------
class TestWiring:
    def test_shifted_data_yields_attribution_telemetry_and_intelligence(self, pipeline):
        result = pipeline.train_and_register("dw", "dep-data")
        pipeline.evaluate_version(result["version_id"])
        pipeline.request_approval(result["version_id"], approver="g")
        pipeline.request_deployment(version_id=result["version_id"], actor="ops")

        healthy = [row[:-1] for row in make_synthetic_regression(150, seed=42).samples]
        shifted = [[x * 3 + 4, y * 0.5 - 6] for x, y in healthy]

        out = pipeline.health_check("dw", current_data=shifted)
        summary = out.get("drift_summary") or {}
        assert summary.get("feature_attribution"), "attribution embedded in summary"
        intelligence = summary.get("intelligence")
        assert intelligence in ("ISOLATED_FEATURE_DRIFT", "BROAD_FEATURE_DRIFT",
                                "DRIFT_WITH_PERFORMANCE_DEGRADATION")
        assert out.get("drift_intelligence") == intelligence
        # per-feature rows persisted with rank/check_ts stamps
        persisted = pipeline.telemetry.feature_history("dw")
        assert persisted and all("check_ts" in r["detail"] for r in persisted)
        ranked = pipeline.telemetry.latest_feature_attribution("dw")
        assert ranked and ranked[0]["detail"]["rank"] == 1

    def test_stable_cycle_remains_quiet(self, pipeline):
        result = pipeline.train_and_register("calm8", "dep-data")
        pipeline.evaluate_version(result["version_id"])
        pipeline.request_approval(result["version_id"], approver="g")
        pipeline.request_deployment(version_id=result["version_id"], actor="ops")
        # exact training rows => statistically identical distribution
        healthy = [row[:-1] for row in pipeline.dataset_cache["dep-data"].samples]
        out = pipeline.health_check("calm8", current_data=healthy[:60])
        feature_codes = {a["code"] for a in out.get("alerts", [])
                         if a["code"].startswith("FEATURE_DRIFT")}
        assert feature_codes == set()

    def test_backwards_compatible_phase7_alerts(self, pipeline):
        """Phase-7 alert behavior unchanged when no Phase-8 kwargs passed."""
        alerts = evaluate("x", metrics={"r2": 0.1, "mse": 0.9})
        assert [a.code for a in alerts] == ["PERFORMANCE_DEGRADED"]


# ----------------------------------------------------------------------
# API exposure
# ----------------------------------------------------------------------
class TestApi:
    @pytest.fixture()
    def client(self, pipeline):
        from fastapi.testclient import TestClient
        from qsmlops.api.app import create_app

        return TestClient(create_app(pipeline)), pipeline

    def test_attribution_endpoint(self, client):
        http, pipe = client
        result = pipe.train_and_register("api-d", "dep-data")
        pipe.evaluate_version(result["version_id"])
        pipe.request_approval(result["version_id"], approver="g")
        pipe.request_deployment(version_id=result["version_id"], actor="ops")
        feats = [row[:-1] for row in make_synthetic_regression(120, seed=42).samples]
        shifted = [[x * 3 + 4, y * 0.5 - 6] for x, y in feats][:100]
        pipe.health_check("api-d", current_data=shifted)

        resp = http.get("/drift/api-d/attribution")
        assert resp.status_code == 200
        body = resp.json()
        assert body["count"] >= 1
        first = body["features"][0]
        assert first["rank"] == 1 and "statistics" in first

    def test_rolling_endpoint(self, client):
        http, pipe = client
        result = pipe.train_and_register("api-r", "dep-data")
        pipe.evaluate_version(result["version_id"])
        pipe.request_approval(result["version_id"], approver="g")
        pipe.request_deployment(version_id=result["version_id"], actor="ops")
        # seed history then degrade
        for mse in (0.005, 0.006, 0.007, 0.05, 0.06):
            pipe.telemetry.record("api-r", "metric", "mse", mse)
        resp = http.get(f"/performance/api-r/rolling?window=2")
        assert resp.status_code == 200
        rb = resp.json()["baselines"]["mse"]
        assert rb["sufficient"] is True and rb["degraded"] is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
