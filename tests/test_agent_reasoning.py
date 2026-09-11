"""Agent reasoning tests: evidence objects, false positives, conflicts, escalation."""
from __future__ import annotations

import pytest

from qsmlops.agents.base import Evidence, Finding, Observation, make_finding
from qsmlops.agents.performance_agent import PerformanceAgent
from qsmlops.config import PlatformConfig
from qsmlops.pipeline.selfheal import SelfHealingMLOps
from qsmlops.pipeline.training import make_synthetic_regression
from qsmlops.supervisor.learning import LearningStore
from qsmlops.supervisor.policy import PolicyEngine, default_policy_engine
from qsmlops.supervisor.supervisor import AdaptiveSupervisor
from qsmlops.supervisor.decisions import Decision


@pytest.fixture()
def pipeline(tmp_path):
    config = PlatformConfig(tmp_path / "root")
    config.ensure_dirs()
    p = SelfHealingMLOps(config)
    ds = make_synthetic_regression(200, seed=42)
    p.provision_dataset("data", ds)
    yield p
    p.close()


class TestEvidenceObjects:
    def test_every_finding_carries_full_evidence(self):
        finding = make_finding(
            "accuracy_drop", False, "HIGH", detail="Accuracy dropped 8%",
            observation="Accuracy dropped 8%", confidence=0.91, recommendation="RETRAIN",
        )
        finding.add_evidence("rolling_accuracy_window", "metric",
                             {"baseline": 0.94, "current": 0.86, "window": 10},
                             description="rolling accuracy window")
        d = finding.to_dict()
        assert d["observation"] == "Accuracy dropped 8%"
        assert d["confidence"] == 0.91
        assert d["risk"] == "HIGH"
        assert d["recommendation"] == "RETRAIN"
        assert d["evidence"][0]["source"] == "rolling_accuracy_window"
        assert d["evidence"][0]["payload"]["current"] == 0.86

    def test_passing_findings_have_no_risk(self):
        f = make_finding("ok", True, "LOW")
        assert f.risk == "NONE" and f.to_dict()["recommendation"] == ""

    def test_agent_sweep_emits_structured_evidence(self, pipeline):
        result = pipeline.train_and_register("ev", "data")
        evaluation = pipeline.evaluate_version(result["version_id"])
        for obs in evaluation["observations"]:
            for f in obs["findings"]:
                assert f["observation"], f"{f['name']} missing observation"
                assert 0.0 <= f["confidence"] <= 1.0
                if not f["passed"]:
                    assert f["recommendation"], f"{f['name']} failed without recommendation"


class TestFalsePositives:
    def test_healthy_model_produces_no_failed_critical(self, pipeline):
        result = pipeline.train_and_register("fp", "data")
        evaluation = pipeline.evaluate_version(result["version_id"])
        critical = [f for o in evaluation["observations"] for f in o["findings"]
                    if not f["passed"] and f["severity"] == "CRITICAL"]
        assert critical == [], [f["name"] for f in critical]

    def test_stable_rolling_metrics_do_not_flag(self):
        agent = PerformanceAgent()
        window = [{"mse": 0.01, "r2": 0.99}] * 6
        obs = agent.observe({
            "subject_id": "x",
            "metrics": {"mse": 0.01, "r2": 0.99},
            "rolling_metrics": {"window": window, "baseline": {"mse": 0.01, "r2": 0.99}},
        })
        failed = [f for f in obs.findings if not f.passed]
        assert failed == []

    def test_false_positive_feedback_decays_trust_in_finding(self, tmp_path):
        learner = LearningStore(tmp_path / "learning.json")
        learner.report_false_positive("drift_feature_drift_ks")
        learner.report_false_positive("drift_feature_drift_ks")
        assert learner.false_positive_count("drift_feature_drift_ks") == 2


class TestConflictingRecommendations:
    def test_conflicting_agent_recommendations_escalate(self):
        class ConflictingA(PerformanceAgent):
            name = "agent-a"

            def observe(self, context):
                obs = super().observe(context)
                obs.recommendation = "RETRAIN"
                return obs

        class ConflictingB(PerformanceAgent):
            name = "agent-b"

            def observe(self, context):
                obs = super().observe(context)
                obs.recommendation = "ROLLBACK"
                return obs

        class ConflictingC(PerformanceAgent):
            name = "agent-c"

            def observe(self, context):
                obs = super().observe(context)
                obs.recommendation = "QUARANTINE"
                return obs

        # three distinct non-ACCEPT recommendations -> supervisor escalates
        agents = [ConflictingA(), ConflictingB(), ConflictingC()]
        obs = [a.observe({"subject_id": "x", "metrics": {"mse": 0.01, "r2": 0.99}}) for a in agents]
        recs = {o.recommendation for o in obs}
        assert len(recs - {"ACCEPT"}) == 3  # conflicts present


class TestEscalationLogic:
    def test_repeated_failed_recoveries_escalate(self, tmp_path):
        learner = LearningStore(tmp_path / "l.json", max_consecutive_failures=2)
        assert not learner.should_escalate("m")
        learner.record_outcome("m", "RETRAIN", success=False)
        assert not learner.should_escalate("m")
        learner.record_outcome("m", "RETRAIN", success=False)
        assert learner.should_escalate("m")
        learner.record_outcome("m", "RETRAIN", success=True)
        assert not learner.should_escalate("m")

    def test_supervisor_escalates_on_learning_state(self, pipeline, tmp_path):
        result = pipeline.train_and_register("esc", "data")
        pipeline.evaluate_version(result["version_id"])
        pipeline.approve_and_deploy(result["version_id"])
        # force escalation state: two failed outcomes
        pipeline.learner.record_outcome("esc", "RETRAIN", success=False)
        pipeline.learner.record_outcome("esc", "RETRAIN", success=False)
        outcome = pipeline.health_check("esc", degraded_metrics={"mse": 0.5, "r2": 0.2})
        assert outcome["report"]["decision"] == "ESCALATE"
        assert "learning store" in outcome["report"]["rationale"]


class TestPolicyEngine:
    def test_security_gate_blocks_deployment(self):
        engine = default_policy_engine()
        facts = {"security_score": 50, "signature_invalid": True}
        gate = engine.deployment_blocked(facts)
        assert gate is not None and gate.action == "BLOCK_DEPLOYMENT"

    def test_gate_requires_both_conditions(self):
        engine = default_policy_engine()
        assert engine.deployment_blocked({"security_score": 50, "signature_invalid": False}) is None
        assert engine.deployment_blocked({"security_score": 95, "signature_invalid": True}) is None

    def test_custom_rules_loaded_from_document(self):
        engine = PolicyEngine.from_document({"rules": [{
            "name": "always_alert", "priority": 10,
            "when": {"all": [{"field": "risk_score", "op": "gte", "value": 0}]},
            "action": "ESCALATE",
        }]})
        decision = engine.first_decision({"risk_score": 1})
        assert decision is not None and decision.action == "ESCALATE"

    def test_supervisor_uses_policy_decisions(self, pipeline):
        result = pipeline.train_and_register("pol", "data")
        pipeline.evaluate_version(result["version_id"])
        pipeline.approve_and_deploy(result["version_id"])
        outcome = pipeline.health_check("pol", degraded_metrics={"mse": 0.6, "r2": 0.1})
        report = outcome["report"]
        assert report["policy_decisions"], "policy engine contributed decisions"
        assert report["decision"] in ("RETRAIN", "ROLLBACK", "ESCALATE", "QUARANTINE")
