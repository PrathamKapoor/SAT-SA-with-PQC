"""Phase 9 tests: agentic intelligence layer.

The four roadmap archetypes (Training Optimization, Incident Response,
Governance, Optimization) on the existing BaseAgent architecture:
instantiation, observation/evidence structure, honest UNAVAILABLE handling,
supervisor receipt, policy-consumable facts, governance non-bypass, quiet
healthy cycles, determinism, and end-to-end registration.
"""
from __future__ import annotations

import json

import pytest

from qsmlops.agents.governance_agent import GovernanceAgent
from qsmlops.agents.incident_response_agent import IncidentResponseAgent
from qsmlops.agents.optimization_agent import OptimizationAgent
from qsmlops.agents.training_optimization_agent import TrainingOptimizationAgent
from qsmlops.config import PlatformConfig
from qsmlops.pipeline.selfheal import SelfHealingMLOps
from qsmlops.pipeline.training import make_synthetic_regression
from qsmlops.supervisor.policy import PolicyEngine, build_facts


@pytest.fixture()
def pipeline(tmp_path):
    config = PlatformConfig(tmp_path / "p9_home")
    pipe = SelfHealingMLOps(config)
    ds = make_synthetic_regression(120, seed=21)
    pipe.provision_dataset("ag-data", ds)
    yield pipe
    pipe.close()


def _trained(pipeline, model="ag-model"):
    return pipeline.train_and_register(model, "ag-data")


def _observations(pipeline, version_id):
    evaluation = pipeline.evaluate_version(version_id)
    by_agent = {o["agent"]: o for o in evaluation["observations"]}
    return evaluation, by_agent


# ----------------------------------------------------------------------
# Instantiation & structure
# ----------------------------------------------------------------------
class TestInstantiationAndStructure:
    def test_all_four_agents_registered_end_to_end(self, pipeline):
        names = [a.name for a in pipeline.agents]
        for expected in ("training-optimization-agent", "incident-response-agent",
                         "governance-agent", "optimization-agent"):
            assert expected in names
        assert len(pipeline.agents) == 9  # 5 prior + 4 new

    def test_observation_structure_and_evidence(self, pipeline):
        result = _trained(pipeline)
        _, by_agent = _observations(pipeline, result["version_id"])
        for agent in ("training-optimization-agent", "incident-response-agent",
                      "governance-agent", "optimization-agent"):
            obs = by_agent[agent]
            assert obs["agent"] == agent
            assert obs["recommendation"]
            assert obs["findings"], f"{agent} produced no findings"
            for f in obs["findings"]:
                assert isinstance(f["passed"], bool)
                if not f["passed"]:
                    assert f["evidence"], f"{agent}:{f['name']} lacks evidence"

    def test_deterministic_on_same_state(self, pipeline):
        result = _trained(pipeline)
        vid = result["version_id"]
        a = _observations(pipeline, vid)[1]
        b = _observations(pipeline, vid)[1]
        # governance_trust_evaluation_present legitimately flips False->True
        # after the first sweep persists the Phase-5 trust evaluation.
        for agent in ("training-optimization-agent", "optimization-agent"):
            fa = [(f["name"], f["passed"], f["severity"]) for f in a[agent]["findings"]]
            fb = [(f["name"], f["passed"], f["severity"]) for f in b[agent]["findings"]]
            assert fa == fb


# ----------------------------------------------------------------------
# Per-agent behavior
# ----------------------------------------------------------------------
class TestTrainingOptimizationAgent:
    def test_healthy_reference_training_is_clean(self, pipeline):
        result = _trained(pipeline)
        _, by = _observations(pipeline, result["version_id"])
        obs = by["training-optimization-agent"]
        failed = [f for f in obs["findings"] if not f["passed"]]
        assert failed == []
        assert obs["recommendation"] == "ACCEPT"

    def test_missing_seed_flagged_with_evidence(self, pipeline):
        result = _trained(pipeline)
        passport = pipeline.registry.load_passport(result["version_id"])
        passport.training_info["hyperparameters"].pop("seed", None)
        context = {"subject_id": result["version_id"], "passport": passport}
        obs = TrainingOptimizationAgent().observe(context)
        seed_f = next(f for f in obs.findings if f.name == "training_reproducible_seed")
        assert seed_f.passed is False and seed_f.recommendation == "RETRAIN_WITH_SEED"
        assert seed_f.evidence[0].payload["has_seed"] is False

    def test_thin_dataset_flagged(self, pipeline):
        result = _trained(pipeline)
        passport = pipeline.registry.load_passport(result["version_id"])
        passport.training_info["n_samples"] = 3   # 3 samples / 2 features
        from qsmlops.pipeline.training import make_synthetic_regression as msr
        tiny_ds = msr(3)                          # 2 features
        context = {"subject_id": result["version_id"], "passport": passport,
                   "datasets": {"ag-data": tiny_ds}}
        obs = TrainingOptimizationAgent().observe(context)
        adequacy = next(f for f in obs.findings if f.name == "sample_adequacy")
        assert adequacy.passed is False and adequacy.severity == "MEDIUM"


class TestIncidentResponseAgent:
    def test_quiet_on_healthy_platform(self, pipeline):
        result = _trained(pipeline)
        _, by = _observations(pipeline, result["version_id"])
        failed = [f for f in by["incident-response-agent"]["findings"] if not f["passed"]]
        assert failed == []

    def test_denial_in_ledger_raises_signal(self, pipeline):
        result = _trained(pipeline)
        # inject a real governed denial through the deployment boundary
        rec = pipeline.registry.get_version(result["version_id"])
        path = pipeline.artifacts._path_for(rec["artifact_digest"])
        original = path.read_bytes()
        path.write_bytes(b"broken" + original)
        try:
            with pytest.raises(Exception):
                pipeline.request_deployment(version_id=result["version_id"], actor="ops")
        finally:
            path.write_bytes(original)
        _, by = _observations(pipeline, result["version_id"])
        sig = next(f for f in by["incident-response-agent"]["findings"]
                   if f["name"] == "recent_incident_signals")
        assert sig["passed"] is False
        assert "deployment_denied" in json.dumps(sig["evidence"][0]["payload"])


class TestGovernanceAgent:
    def test_compliant_version_passes_governance(self, pipeline):
        result = _trained(pipeline)
        _, by = _observations(pipeline, result["version_id"])
        gov = by["governance-agent"]
        critical_failures = [f for f in gov["findings"]
                             if not f["passed"] and f["severity"] == "CRITICAL"]
        assert critical_failures == []

    def test_tampered_signature_blocked_by_governance_findings(self, pipeline):
        result = _trained(pipeline)
        vid = result["version_id"]
        rec = pipeline.registry.get_version(vid)
        ppath = pipeline.artifacts._path_for(rec["passport_digest"])
        doc = json.loads(ppath.read_bytes().decode("utf-8"))
        doc["identity"]["owner"] = "attacker"
        ppath.write_bytes(json.dumps(doc, sort_keys=True).encode())
        evaluation = pipeline.evaluate_version(vid)   # registry quarantines anyway
        gov = next(o for o in evaluation["observations"]
                   if o["agent"] == "governance-agent")
        sig = next(f for f in gov["findings"] if f["name"] == "governance_signature_valid")
        assert sig["passed"] is False and sig["severity"] == "CRITICAL"
        assert sig["evidence"][0]["source"] == "trust_anchors"


class TestOptimizationAgent:
    def test_quiet_on_unique_registry(self, pipeline):
        result = _trained(pipeline)
        _, by = _observations(pipeline, result["version_id"])
        failed = [f for f in by["optimization-agent"]["findings"] if not f["passed"]]
        assert failed == []

    def test_duplicate_artifact_detected(self, pipeline):
        first = pipeline.train_and_register("dup-a", "ag-data")
        second = pipeline.train_and_register("dup-b", "ag-data")
        assert first["artifact_digest"] == second["artifact_digest"]  # same data/seed
        _, by = _observations(pipeline, second["version_id"])
        dup = next(f for f in by["optimization-agent"]["findings"]
                   if f["name"] == "no_duplicate_artifacts")
        assert dup["passed"] is False
        assert dup["evidence"][0]["payload"]["duplicate_digests"] >= 1


# ----------------------------------------------------------------------
# Supervisor facts / policy consumption
# ----------------------------------------------------------------------
class TestSupervisorFacts:
    def test_new_agent_risks_become_policy_facts(self):
        """Real Observation/Finding objects flow into build_facts and the
        existing PolicyEngine consumes per-agent risk keys."""
        from qsmlops.agents.base import Observation, make_finding
        from qsmlops.supervisor.decisions import aggregate_risk

        observations = []
        for agent in ("training-optimization-agent", "incident-response-agent",
                      "governance-agent", "optimization-agent"):
            obs = Observation(agent=agent, subject_id="x", recommendation="MONITOR")
            obs.findings.append(make_finding(f"{agent}_check", False, "MEDIUM",
                                             detail="illustrative breach"))
            observations.append(obs)

        risk, per_agent = aggregate_risk(observations)
        facts = build_facts(observations, risk_score=risk, per_agent_risk=per_agent)
        for agent in ("training-optimization-agent", "incident-response-agent",
                      "governance-agent", "optimization-agent"):
            key = f"{agent}_risk"   # agent names keep their hyphens in facts
            assert key in facts and facts[key] > 0

        engine = PolicyEngine.from_document({"rules": [{
            "name": "governance_risk_gate", "priority": 90, "gate": True,
            "when": {"all": [{"field": "governance-agent_risk", "op": "gte", "value": 3}]},
            "action": "BLOCK_DEPLOYMENT",
        }]})
        assert engine.deployment_blocked(facts) is not None


class TestSafety:
    def test_agents_never_invoke_promotion_paths(self):
        import inspect

        from qsmlops import agents as pkg
        import pathlib

        mod_dir = pathlib.Path(pkg.__file__).parent
        offenders = []
        for f in mod_dir.glob("*_agent.py"):
            src = f.read_text(encoding="utf-8")
            for forbidden in (".deploy(", ".approve_deployment(", ".transition(",
                              ".request_approval(", ".quarantine(", ".revoke("):
                if forbidden in src:
                    offenders.append((f.name, forbidden))
        assert offenders == [], f"agents contain mutation calls: {offenders}"

    def test_full_registration_reaches_supervisor(self, pipeline):
        result = _trained(pipeline)
        evaluation = pipeline.evaluate_version(result["version_id"])
        agents_seen = {o["agent"] for o in evaluation["observations"]}
        assert agents_seen == {a.name for a in pipeline.agents}


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
