from __future__ import annotations

from evaluation.research.integrity import run_trust_integrity_experiment


def test_integrity_experiment_runs_real_workflow_and_detects_each_mutation(tmp_path):
    result = run_trust_integrity_experiment(tmp_path)

    assert result["status"] == "completed"
    assert result["valid_control"]["verified"] is True
    mutations = result["mutations"]
    assert {row["mutation"] for row in mutations} >= {
        "decision",
        "finding",
        "risk",
        "recommendation",
        "source_provenance",
        "canonical_payload",
        "receipt_signature",
        "ledger_chain",
    }
    assert all(
        row["detected"] is True
        for row in mutations
        if row["expected_verification_outcome"] == "tampered"
    )
    assert all(row["matches_expected"] is True for row in mutations)
    assert all(row["target_object"] for row in mutations)
    control = next(
        row for row in mutations if row["mutation"] == "operational_queue_field_control"
    )
    assert control["detected"] is False
    summary = result["mutation_summary"]
    assert summary["detected_of_expected_tampered"] == summary["expected_tampered"]
    assert summary["negative_controls_verified"] == 1
    assert all(row["verification_ms"] >= 0 for row in mutations)
    assert result["workflow"]["analysis_run_id"]
    assert result["workflow"]["decision_id"]
