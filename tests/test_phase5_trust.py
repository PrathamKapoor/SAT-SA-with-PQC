"""Phase 5 trust evaluation tests.

Covers the explainable trust model: evidence-derived scoring, deterministic
results, hard cryptographic blockers, component structure, and policy-fact
integration. No fabricated evidence anywhere: every scenario manipulates
real platform state (artifact bytes, keystore records, passports).
"""
from __future__ import annotations

import json

import pytest

from qsmlops.agents.base import Observation, make_finding
from qsmlops.config import PlatformConfig
from qsmlops.pipeline.selfheal import SelfHealingMLOps
from qsmlops.pipeline.training import make_synthetic_regression
from qsmlops.scores import evaluate_trust
from qsmlops.supervisor.policy import PolicyEngine, Rule, build_facts


@pytest.fixture()
def pipeline(tmp_path):
    config = PlatformConfig(tmp_path / "phase5_home")
    pipe = SelfHealingMLOps(config)
    ds = make_synthetic_regression(200, seed=42)
    pipe.provision_dataset("trust-data", ds)
    yield pipe
    pipe.close()


def _trained(pipeline, model="tm"):
    return pipeline.train_and_register(model, "trust-data")


# ----------------------------------------------------------------------
# Trust model behaviour
# ----------------------------------------------------------------------
class TestTrustModel:
    def test_valid_model_is_trusted_with_full_components(self, pipeline):
        result = _trained(pipeline)
        report = pipeline.registry.trust_evaluation(result["version_id"], actor="test")

        assert report.decision == "TRUSTED"
        assert report.trust_score >= 90.0
        assert report.promotion_eligible is True
        assert report.blocking_conditions == []
        for name in ("security", "integrity", "lineage", "performance", "operational"):
            assert name in report.components
            assert 0.0 <= report.components[name] <= 100.0

    def test_evaluation_is_deterministic(self, pipeline):
        result = _trained(pipeline)
        vid = result["version_id"]
        first = pipeline.registry.trust_evaluation(vid, actor="t1", persist=False)
        second = pipeline.registry.trust_evaluation(vid, actor="t2", persist=False)
        assert first.trust_score == second.trust_score
        assert first.components == second.components
        assert first.decision == second.decision

    def test_result_references_actual_evidence(self, pipeline):
        result = _trained(pipeline)
        vid = result["version_id"]
        rec = pipeline.registry.get_version(vid)
        report = pipeline.registry.trust_evaluation(vid, persist=False)

        assert report.evidence["artifact_digest"] == rec["artifact_digest"]
        assert report.evidence["bom_digest"] == rec["bom_digest"]
        assert report.evidence["signature_valid"] is True
        assert report.evidence["signer_status"] == "active"
        assert report.evidence["bom_verified_entries"] == len(
            pipeline._load_bom(rec["bom_digest"]).entries
        )
        # explanation names the decision and every component score
        assert report.decision in report.explanation
        for name in report.components:
            assert f"{name}=" in report.explanation

    def test_score_reflects_real_agent_findings(self, pipeline):
        """A failing HIGH agent observation must lower the composite."""
        result = _trained(pipeline)
        vid = result["version_id"]
        clean = pipeline.registry.trust_evaluation(vid, persist=False)

        obs = Observation(agent="ml-performance-agent", subject_id=vid,
                          recommendation="RETRAIN")
        obs.findings.append(make_finding(
            "r2_above_threshold", False, "HIGH",
            detail="r2 dropped below threshold in production window"))
        degraded = pipeline.registry.trust_evaluation(
            vid, observations=[obs], persist=False)

        assert degraded.trust_score < clean.trust_score
        assert any("r2_above_threshold" in n["detail"] for n in degraded.negative_factors)


class TestHardBlockers:
    def test_invalid_signature_blocks_regardless_of_score(self, pipeline):
        result = _trained(pipeline)
        vid = result["version_id"]
        rec = pipeline.registry.get_version(vid)
        # tamper the stored passport document -> signature no longer verifies
        path = pipeline.artifacts._path_for(rec["passport_digest"])
        doc = json.loads(path.read_bytes().decode("utf-8"))
        doc["metrics"]["r2"] = 0.123456  # any body change invalidates the signature
        path.write_bytes(json.dumps(doc, sort_keys=True).encode("utf-8"))

        report = pipeline.registry.trust_evaluation(vid, persist=False)
        assert report.decision == "BLOCKED"
        assert "passport_signature_invalid" in report.blocking_conditions
        assert report.promotion_eligible is False
        # a high aggregate can never rescue a broken signature
        assert "passport_signature_invalid" not in report.positive_factors and True

    def test_corrupted_artifact_blocks(self, pipeline):
        result = _trained(pipeline)
        vid = result["version_id"]
        rec = pipeline.registry.get_version(vid)
        path = pipeline.artifacts._path_for(rec["artifact_digest"])
        original = path.read_bytes()
        path.write_bytes(b"tampered" + original)
        try:
            report = pipeline.registry.trust_evaluation(vid, persist=False)
            assert report.decision == "BLOCKED"
            assert "artifact_corrupted_or_missing" in report.blocking_conditions
            assert report.components["integrity"] == 0.0
        finally:
            path.write_bytes(original)

    def test_revoked_signer_blocks(self, pipeline):
        result = _trained(pipeline)
        vid = result["version_id"]
        passport = pipeline.registry.load_passport(vid)
        pipeline.keystore.revoke(passport.signature.signer_key_id)

        report = pipeline.registry.trust_evaluation(vid, persist=False)
        assert report.decision == "BLOCKED"
        assert "signer_key_revoked" in report.blocking_conditions


class TestDecisionMapping:
    def test_thresholds_drive_review_required(self, pipeline):
        """Strict thresholds turn an otherwise-conditional model into REVIEW."""
        result = _trained(pipeline)
        vid = result["version_id"]
        strict = pipeline.registry.trust_evaluation(
            vid, persist=False,
        )
        forced_review = evaluate_trust(
            version_id=vid,
            version_record=pipeline.registry.get_version(vid),
            passport=pipeline.registry.load_passport(vid),
            keystore=pipeline.keystore,
            artifact_store=pipeline.artifacts,
            bom=pipeline._load_bom(pipeline.registry.get_version(vid)["bom_digest"]),
            thresholds={"trusted": 150.0, "conditional": 150.0},  # impossible bars
        )
        # same evidence, stricter policy -> demoted, never blocked
        assert strict.decision != "BLOCKED"
        assert forced_review.decision == "REVIEW_REQUIRED"
        assert forced_review.trust_score == strict.trust_score

    def test_degraded_metrics_are_not_trusted(self, pipeline):
        result = _trained(pipeline, model="degraded")
        vid = result["version_id"]
        rec = pipeline.registry.get_version(vid)
        passport = pipeline.registry.load_passport(vid)
        # simulate genuinely worse recorded performance
        passport.metrics["mse"] = 0.5
        passport.metrics["r2"] = 0.1
        report = evaluate_trust(
            version_id=vid,
            version_record=rec,
            passport=passport,
            keystore=pipeline.keystore,
            artifact_store=pipeline.artifacts,
            bom=pipeline._load_bom(rec["bom_digest"]),
        )
        assert report.components["performance"] == 0.0
        assert report.decision != "TRUSTED"


# ----------------------------------------------------------------------
# Policy integration
# ----------------------------------------------------------------------
class TestPolicyIntegration:
    def test_trust_facts_reach_the_policy_engine(self, pipeline):
        result = _trained(pipeline)
        report = pipeline.registry.trust_evaluation(result["version_id"], persist=False)

        facts = build_facts([], risk_score=0.0, per_agent_risk={}, trust=report.to_dict())
        assert facts["trust_decision"] == "TRUSTED"
        assert facts["trust_promotion_eligible"] is True
        assert facts["trust_blocking_conditions"] == 0

    def test_policy_can_reject_low_trust_models(self):
        engine = PolicyEngine.from_document(
            {
                "rules": [
                    {
                        "name": "require_trusted_models",
                        "priority": 100,
                        "gate": True,
                        "when": {"all": [
                            {"field": "trust_decision", "op": "ne", "value": "TRUSTED"},
                            {"field": "state", "op": "eq", "value": "VERIFIED"},
                        ]},
                        "action": "BLOCK_DEPLOYMENT",
                    }
                ]
            }
        )
        facts = build_facts(
            [], risk_score=0.0, per_agent_risk={},
            version_record={"state": "VERIFIED"},
            trust={"trust_score": 55.0, "decision": "REVIEW_REQUIRED",
                   "promotion_eligible": False, "blocking_conditions": []},
        )
        gate = engine.deployment_blocked(facts)
        assert gate is not None and gate.rule_name == "require_trusted_models"

        trusted_facts = build_facts(
            [], risk_score=0.0, per_agent_risk={},
            version_record={"state": "VERIFIED"},
            trust={"trust_score": 97.0, "decision": "TRUSTED",
                   "promotion_eligible": True, "blocking_conditions": []},
        )
        assert engine.deployment_blocked(trusted_facts) is None

    def test_policy_cannot_override_cryptographic_failure(self):
        """A low-threshold trust rule still loses to the signature fact chain."""
        engine = PolicyEngine.from_document(
            {
                "rules": [
                    {
                        "name": "always_allow_high_score",
                        "priority": 300,
                        "when": {"all": [
                            {"field": "trust_score", "op": "gte", "value": 50},
                        ]},
                        "action": "DEPLOY",
                    },
                    {
                        "name": "block_broken_signatures",
                        "priority": 200,
                        "gate": True,
                        "when": {"all": [
                            {"field": "signature_invalid", "op": "eq", "value": True},
                        ]},
                        "action": "BLOCK_DEPLOYMENT",
                    },
                ],
                "thresholds": {"min_security_score": 90.0},
            }
        )
        facts = build_facts(
            [], risk_score=5.0, per_agent_risk={}, scores={"security_score": 20.0},
            trust={"trust_score": 99.0, "decision": "TRUSTED",
                   "promotion_eligible": True, "blocking_conditions": []},
        )
        facts["signature_invalid"] = True
        gate = engine.deployment_blocked(facts)
        assert gate is not None and gate.action == "BLOCK_DEPLOYMENT"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
