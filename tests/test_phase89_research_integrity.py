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
    assert all(row["detected"] is True for row in mutations)
    assert all(row["verification_ms"] >= 0 for row in mutations)
    assert result["workflow"]["analysis_run_id"]
    assert result["workflow"]["decision_id"]
