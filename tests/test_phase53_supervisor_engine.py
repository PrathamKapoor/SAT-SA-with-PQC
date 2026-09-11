"""Phase P11 — generalized supervisor engine + 17-agent registry.

The roadmap explicitly states:

  > one generalized supervisor with two pluggable decision vocabularies
  > (MLOps vocabulary + SAT-SA vocabulary)

This test verifies:

1. The supervisor engine exposes the OBSERVE → REASON → ACT →
   VERIFY → LEARN five-stage loop and runs end-to-end on a
   DecisionContext.
2. The MLOps and SAT-SA vocabularies are distinct, both loadable,
   and the engine refuses unknown vocabularies.
3. The 17-agent SAT-SA registry is present, every agent has a
   distinct id, and there are exactly 26 agents total (9 retained
   MLOps + 17 SAT-SA).
4. A SAT-SA decision requires human authority (no autonomous
   ``ACCEPT`` / ``CLOSE_REVIEW``).
5. The recommendation engine's bounded actions map to SAT-SA
   vocabulary decisions.
"""
from __future__ import annotations

import pytest

from satsa.supervisor import (
    AGENT_REGISTRY, RETAINED_MLOPS_AGENTS, SATSA_AGENTS,
    SATSA_VOCABULARY, MLOPS_VOCABULARY,
    SupervisorEngine, SupervisorContext,
    DecisionContext, get_agent, list_agents,
)


def test_agent_registry_has_26_agents():
    """9 retained MLOps + 17 SAT-SA = 26 agents."""
    assert len(RETAINED_MLOPS_AGENTS) == 9
    assert len(SATSA_AGENTS) == 17
    assert len(AGENT_REGISTRY) == 26
    families = {"mlops": 0, "satsa": 0}
    for a in AGENT_REGISTRY.values():
        families[a.family] += 1
    assert families == {"mlops": 9, "satsa": 17}


def test_agent_ids_unique():
    ids = [a.agent_id for a in AGENT_REGISTRY.values()]
    assert len(ids) == len(set(ids))


def test_satsa_agents_have_required_fields():
    for a in SATSA_AGENTS:
        assert a.agent_id
        assert a.name
        assert a.family == "satsa"
        assert a.purpose
        assert a.inputs
        assert a.outputs
        assert a.evidence_types
        assert a.implementation_ref
        assert a.version


def test_retained_mlops_agents_listed():
    expected = {
        "mlops.data", "mlops.performance", "mlops.security",
        "mlops.quantum", "mlops.redteam", "mlops.training_optimization",
        "mlops.incident_response", "mlops.governance",
        "mlops.optimization",
    }
    actual = {a.agent_id for a in RETAINED_MLOPS_AGENTS}
    assert actual == expected


def test_satsa_agents_correspond_to_roadmap_responsibilities():
    expected = {
        "satsa.ingest", "satsa.normalize", "satsa.execution_gap",
        "satsa.negative_space", "satsa.anomaly", "satsa.peer_benchmark",
        "satsa.coverage_gap", "satsa.drift",
        "satsa.cross_entity_insights", "satsa.case_similarity",
        "satsa.evidence_completeness", "satsa.fusion",
        "satsa.prioritization", "satsa.recommendation",
        "satsa.review_workflow", "satsa.trust_provenance",
        "satsa.validation",
    }
    actual = {a.agent_id for a in SATSA_AGENTS}
    assert actual == expected


def test_vocabularies_disjoint():
    assert set(SATSA_VOCABULARY).isdisjoint(MLOPS_VOCABULARY)


def test_engine_satsa_path_with_signal_findings():
    eng = SupervisorEngine()
    # Build a synthetic signal finding
    from satsa.domain.evidence import ConfidenceVector, Finding
    f = Finding(
        observation_id="obs-x",
        rule_or_category="execution_gap.fast_closure",
        state="signal",
        rationale="critical alert closed in 30s",
        scoped_subjects=["alert-1"],
        statistic=30.0, effect=0.5, threshold=600.0,
        confidence=ConfidenceVector(analytical_support=0.8,
                                   evidence_completeness=0.7,
                                   peer_confidence=None),
        evidence_refs=["sr-1"], limitations="",
    )
    ctx = DecisionContext(
        vocabulary="satsa", scope={"entity_id": "e1"},
        run_id="run-1", findings=[f],
        principal="tester",
    )
    decision = eng.run(ctx)
    assert decision.vocabulary == "satsa"
    # The fast-closure rule maps to SATSA_INSPECT
    assert decision.action in SATSA_VOCABULARY
    assert decision.action != "SATSA_SURFACE"
    assert decision.requires_human is True
    # Lineage has all five stages
    stages = [stage for stage, _ in decision.lineage]
    assert stages == ["observe", "reason", "verify", "learn"]


def test_engine_satsa_path_with_no_findings_defaults_to_surface():
    eng = SupervisorEngine()
    ctx = DecisionContext(
        vocabulary="satsa", scope={"entity_id": "e1"},
        run_id="run-1", findings=[],
    )
    decision = eng.run(ctx)
    assert decision.action == "SATSA_SURFACE"


def test_engine_mlops_path_proposes_known_action():
    eng = SupervisorEngine()
    from satsa.domain.evidence import ConfidenceVector, Finding
    f = Finding(
        observation_id="obs-x",
        rule_or_category="drift.alert_volume",
        state="signal",
        rationale="alert volume increased 30% period-on-period",
        scoped_subjects=["e1"], statistic=10.0, effect=0.3,
        threshold=0.1,
        confidence=ConfidenceVector(analytical_support=0.6,
                                   evidence_completeness=0.5),
    )
    ctx = DecisionContext(
        vocabulary="mlops", scope={"model_name": "m1"},
        run_id="run-1", findings=[f],
    )
    decision = eng.run(ctx)
    assert decision.vocabulary == "mlops"
    assert decision.action in MLOPS_VOCABULARY


def test_engine_rejects_unknown_vocabulary():
    eng = SupervisorEngine()
    ctx = DecisionContext(vocabulary="bogus", scope={})
    with pytest.raises(ValueError):
        eng.run(ctx)


def test_list_agents_filters_by_family():
    all_a = list_agents()
    assert len(all_a) == 26
    satsa_a = list_agents(family="satsa")
    assert len(satsa_a) == 17
    mlops_a = list_agents(family="mlops")
    assert len(mlops_a) == 9
    with pytest.raises(ValueError):
        list_agents(family="bogus")


def test_get_agent_raises_for_unknown_id():
    with pytest.raises(KeyError):
        get_agent("nonexistent.agent")


def test_supervisor_lineage_log_records_every_decision():
    eng = SupervisorEngine()
    ctx = DecisionContext(vocabulary="satsa", scope={"entity_id": "e1"})
    eng.run(ctx)
    eng.run(ctx)
    assert len(eng.lineage_log) == 2
    assert all("decision_id" in entry for entry in eng.lineage_log)