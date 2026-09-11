"""Phase 2 — evidence/provenance persistence regression tests (Part E).

Phase 1's audit found ``observations``, ``findings``, ``supervisor_decisions``
and ``provenance_edges`` were migrated, indexed tables with no repository or
insert path anywhere in the codebase — a schema without a service. This file
tests the EvidenceStore that closes that gap (qsmlops/database/evidence_store.py),
against REAL Observation/Finding/DecisionReport objects produced by the actual
nine-agent pipeline and supervisor (not hand-built fixtures), so the test
proves the store works against what the platform actually produces.
"""
from __future__ import annotations

import pytest

from qsmlops.agents.base import Evidence, Finding, Observation
from qsmlops.core.errors import DuplicateEntryError
from qsmlops.database.evidence_store import EvidenceStore


def _rebuild_observation(o: dict) -> Observation:
    obs = Observation(agent=o["agent"], subject_id=o.get("subject_id", ""),
                       recommendation=o.get("recommendation", ""), notes=o.get("notes", ""))
    obs.findings = [Finding.from_dict(f) for f in o.get("findings", [])]
    return obs


def _trained_and_evaluated(pipeline, model="ev-model"):
    from qsmlops.pipeline.training import make_synthetic_regression

    ds = make_synthetic_regression(n=60, seed=7)
    pipeline.provision_dataset(f"{model}-data", ds)
    result = pipeline.train_and_register(model, f"{model}-data")
    eval_result = pipeline.evaluate_version(result["version_id"])
    return result, eval_result


# -------------------- E5: insert / retrieve, real pipeline data --------------------

def test_persist_and_retrieve_real_observation(container):
    pipeline = container.get("pipeline")
    store = container.get("evidence_store")
    _, eval_result = _trained_and_evaluated(pipeline)
    real_observations = eval_result["observations"]
    assert real_observations, "pipeline produced no observations to persist"

    observation = _rebuild_observation(real_observations[0])
    obs_id = store.persist_observation(observation)

    row = store.get_observation(obs_id)
    assert row is not None
    assert row["agent"] == observation.agent
    assert row["subject_id"] == observation.subject_id

    findings = store.get_findings_for_observation(obs_id)
    assert len(findings) == len(observation.findings)
    for f_row, f_obj in zip(findings, observation.findings):
        assert f_row["name"] == f_obj.name
        assert bool(f_row["passed"]) == f_obj.passed


def test_finding_provenance_links_to_its_observation(container):
    pipeline = container.get("pipeline")
    store = container.get("evidence_store")
    _, eval_result = _trained_and_evaluated(pipeline, model="prov-model")
    observation = _rebuild_observation(eval_result["observations"][0])
    obs_id = store.persist_observation(observation)

    for finding in observation.findings:
        edges = store.get_provenance_for("finding", finding.finding_id)
        assert any(
            e["predicate"] == "derived_from" and e["object_type"] == "observation"
            and e["object_id"] == obs_id
            for e in edges
        )


def test_persist_real_supervisor_decision_linked_to_observation(container):
    pipeline = container.get("pipeline")
    store = container.get("evidence_store")
    result, eval_result = _trained_and_evaluated(pipeline, model="dec-model")
    version_id = result["version_id"]
    observation = _rebuild_observation(eval_result["observations"][0])
    obs_id = store.persist_observation(observation)

    report, _ = pipeline.supervisor.reason(version_id)
    decision_id = store.persist_decision(
        report, model_name="dec-model", based_on_observation_ids=[obs_id]
    )

    row = store.get_decision(decision_id)
    assert row is not None
    assert row["decision"] == report.decision.value
    assert row["model_name"] == "dec-model"

    edges = store.get_provenance_for("decision", decision_id)
    assert any(
        e["predicate"] == "based_on" and e["object_type"] == "observation" and e["object_id"] == obs_id
        for e in edges
    )


# -------------------- E5: duplicates, invalid refs, missing data --------------------

def test_duplicate_observation_id_rejected(container):
    store = container.get("evidence_store")
    obs = Observation(agent="tester", subject_id="s1", recommendation="none")
    store.persist_observation(obs)
    with pytest.raises(DuplicateEntryError):
        store.persist_observation(obs)  # same observation_id again


def test_missing_observation_returns_none_not_error(container):
    store = container.get("evidence_store")
    assert store.get_observation("does-not-exist") is None
    assert store.get_findings_for_observation("does-not-exist") == []
    assert store.get_decision("does-not-exist") is None


def test_provenance_edge_is_idempotent(container):
    """Asserting the same edge twice must not raise (Part E design: the same
    lifecycle stage may legitimately be reprocessed)."""
    store = container.get("evidence_store")
    obs = Observation(agent="tester", subject_id="s2", recommendation="none")
    obs.findings = [Finding(name="f1", passed=True, severity="LOW")]
    store.persist_observation(obs)
    edges_before = store.get_provenance_for("finding", obs.findings[0].finding_id)
    # Re-run the same provenance assertion the store already made internally.
    store._provenance.insert(
        "finding", obs.findings[0].finding_id, "derived_from", "observation",
        obs.observation_id, content_digest="irrelevant-for-idempotency-check",
    )
    edges_after = store.get_provenance_for("finding", obs.findings[0].finding_id)
    assert len(edges_after) == len(edges_before)  # no duplicate row added


# -------------------- E4: integrity --------------------

def test_integrity_check_passes_for_untouched_row(container):
    store = container.get("evidence_store")
    obs = Observation(agent="tester", subject_id="s3", recommendation="none")
    obs.findings = [Finding(name="f1", passed=False, severity="HIGH", confidence=0.7,
                             evidence=[Evidence(source="unit-test", payload={"x": 1})])]
    obs_id = store.persist_observation(obs)
    ok, msg = store.verify_observation_integrity(obs_id)
    assert ok, msg


def test_integrity_check_detects_out_of_band_row_edit(container):
    store = container.get("evidence_store")
    obs = Observation(agent="tester", subject_id="s4", recommendation="none")
    obs_id = store.persist_observation(obs)

    # Simulate a row edit that bypasses the EvidenceStore/repository layer
    # entirely (e.g. direct DB access, or a bug elsewhere).
    engine = container.get("database").engine
    engine.execute(
        "UPDATE observations SET recommendation=? WHERE observation_id=?",
        ("tampered-value", obs_id),
    )
    ok, msg = store.verify_observation_integrity(obs_id)
    assert not ok
    assert "content_digest mismatch" in msg


# -------------------- E5: transaction rollback --------------------

def test_persist_observation_rolls_back_on_partial_failure(container):
    """If persisting a finding fails partway through, the whole observation
    (including findings already written in this call) must not remain
    partially committed — this is exactly what DatabaseEngine.transaction()
    exists to guarantee (Phase 2 addition; previously execute() auto-committed
    every statement independently, so a partial failure would have left a
    half-written observation)."""
    store = container.get("evidence_store")
    obs = Observation(agent="tester", subject_id="s5", recommendation="none")
    good_finding = Finding(name="ok", passed=True, severity="LOW")
    obs.findings = [good_finding]

    # Force the second finding to collide on finding_id with the first,
    # which the findings table's PRIMARY KEY rejects — simulating a failure
    # partway through the multi-row persist.
    colliding_finding = Finding(name="bad", passed=False, severity="HIGH")
    colliding_finding.finding_id = good_finding.finding_id
    obs.findings.append(colliding_finding)

    with pytest.raises(DuplicateEntryError):
        store.persist_observation(obs)

    # Nothing from this attempt should be visible — not the observation row,
    # not the one finding that would otherwise have succeeded on its own.
    assert store.get_observation(obs.observation_id) is None
    assert store.get_findings_for_observation(obs.observation_id) == []
