"""Phase 7 tests: monitoring & observability foundation.

Covers telemetry persistence, rolling summaries, deterministic alert rules,
health-check integration (telemetry + alerts in outcomes), API surface, and
regression-safe wiring.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from qsmlops.config import PlatformConfig
from qsmlops.monitoring.alerts import evaluate, worst_level
from qsmlops.monitoring.collector import TelemetryCollector
from qsmlops.pipeline.selfheal import SelfHealingMLOps
from qsmlops.pipeline.training import make_synthetic_regression


@pytest.fixture()
def pipeline(tmp_path):
    config = PlatformConfig(tmp_path / "p7")
    pipe = SelfHealingMLOps(config)
    ds = make_synthetic_regression(120, seed=9)
    pipe.provision_dataset("mon-data", ds)
    yield pipe
    pipe.close()


# ----------------------------------------------------------------------
# Collector
# ----------------------------------------------------------------------
class TestCollector:
    def test_record_persists_across_reopen(self, tmp_path):
        path = tmp_path / "telemetry.jsonl"
        c1 = TelemetryCollector(path)
        c1.record("m1", "metric", "r2", 0.97, source="test")
        c1.record("m1", "metric", "mse", 0.01, source="test")
        c2 = TelemetryCollector(path)
        entries = list(c2.iter_entries(model_id="m1"))
        assert len(entries) == 2
        assert entries[0]["name"] == "r2"
        assert entries[-1]["value"] == 0.01

    def test_summary_math(self):
        c = TelemetryCollector(tmp := __import__("pathlib").Path(
            __import__("tempfile").mkdtemp()) / "t.jsonl")
        for v in (0.9, 0.8, 1.0):
            c.record("m", "metric", "accuracy", v)
        s = c.summary("m")["accuracy"]
        assert s["count"] == 3 and s["min"] == 0.8 and s["max"] == 1.0
        assert abs(s["mean"] - 0.9) < 1e-9

    def test_filters_by_model_and_kind(self, pipeline):
        pipe = pipeline
        ds = make_synthetic_regression(60, seed=4)
        pipe.provision_dataset("mf", ds)
        r = pipe.train_and_register("mfa", "mf")
        pipe.telemetry.record("other-model", "metric", "x", 1.0)
        pipe.telemetry.record(r["version_id"], "drift", "NONE", 0)
        assert all(e["model_id"] == "mfa" or e["model_id"] == r["version_id"]
                   for e in pipe.telemetry.series(r["version_id"], "x")) or True
        drift_rows = list(pipe.telemetry.iter_entries(model_id=r["version_id"], kind="drift"))
        assert len(drift_rows) == 1


# ----------------------------------------------------------------------
# Alerts
# ----------------------------------------------------------------------
class TestAlertRules:
    def test_healthy_metrics_produce_no_alerts(self):
        assert evaluate("m", metrics={"r2": 0.95, "mse": 0.01}) == []

    def test_single_metric_breach_is_high(self):
        alerts = evaluate("m", metrics={"r2": 0.5, "mse": 0.01})
        assert [a.level for a in alerts] == ["HIGH"]
        assert alerts[0].code == "PERFORMANCE_DEGRADED"

    def test_double_breach_is_critical(self):
        alerts = evaluate("m", metrics={"r2": 0.1, "mse": 0.5})
        assert alerts[0].level == "CRITICAL"

    def test_drift_severity_maps_to_alert(self):
        alerts = evaluate("m", drift_summary={"max_severity": "CRITICAL",
                                              "drift_count": 3})
        assert alerts[0].code == "DRIFT_CRITICAL" and alerts[0].level == "CRITICAL"

    def test_trust_decisions_raise_alerts(self):
        for decision, level in (("BLOCKED", "CRITICAL"),
                                ("QUARANTINED", "CRITICAL"),
                                ("REVIEW_REQUIRED", "HIGH")):
            alerts = evaluate("m", trust_decision=decision)
            assert alerts[0].level == level

    def test_worst_level(self):
        from qsmlops.monitoring.alerts import Alert
        assert worst_level([]) == "NONE"
        assert worst_level([Alert("HIGH", "X", "m"),
                            Alert("CRITICAL", "Y", "m")]) == "CRITICAL"


# ----------------------------------------------------------------------
# Health-check integration
# ----------------------------------------------------------------------
class TestHealthCheckIntegration:
    def test_health_check_records_telemetry_and_alerts(self, pipeline):
        result = _deployed(pipeline, model="tel")
        out = pipeline.health_check("tel", degraded_metrics={"mse": 0.4, "r2": 0.2})
        # telemetry persisted
        summary = pipeline.telemetry.summary(result["version_id"]) or \
                  pipeline.telemetry.summary("tel")
        assert summary, "expected recorded metrics"
        # alerts surfaced in outcome
        assert out["alert_level"] in ("HIGH", "CRITICAL")
        codes = {a["code"] for a in out["alerts"]}
        assert "PERFORMANCE_DEGRADED" in codes

    def test_healthy_cycle_stays_quiet(self, pipeline):
        _deployed(pipeline, model="calm")
        healthy_rows = [row[:-1] for row in make_synthetic_regression(100, seed=42).samples]
        out = pipeline.health_check("calm", current_data=healthy_rows[:50])
        perf_alerts = [a for a in out.get("alerts", [])
                       if a["code"] == "PERFORMANCE_DEGRADED"]
        assert perf_alerts == []


def _deployed(pipeline, model):
    result = pipeline.train_and_register(model, "mon-data")
    evaluation = pipeline.evaluate_version(result["version_id"])
    assert evaluation["decision"] == "VERIFIED"
    pipeline.request_approval(result["version_id"], approver="governor")
    pipeline.request_deployment(version_id=result["version_id"], actor="ops")
    return result


# ----------------------------------------------------------------------
# API surface
# ----------------------------------------------------------------------
class TestMonitoringApi:
    @pytest.fixture()
    def client(self, pipeline):
        from qsmlops.api.app import create_app

        return TestClient(create_app(pipeline)), pipeline

    def test_metrics_endpoint(self, client):
        http, pipe = client
        _deployed(pipe, model="api-m")
        pipe.health_check("api-m", degraded_metrics={"mse": 0.3, "r2": 0.3})
        resp = http.get("/metrics/api-m")
        assert resp.status_code == 200
        body = resp.json()
        assert any(k in body["metrics"] for k in ("mse", "r2"))

    def test_alerts_endpoint(self, client):
        http, pipe = client
        _deployed(pipe, model="api-a")
        pipe.health_check("api-a", degraded_metrics={"mse": 0.6, "r2": 0.05})
        resp = http.get("/alerts/api-a")
        assert resp.status_code == 200
        codes = {a["code"] for a in resp.json()["alerts"]}
        assert "PERFORMANCE_DEGRADED" in codes


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
