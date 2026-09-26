from __future__ import annotations

from evaluation.research.peer import run_peer_sensitivity_experiment


def test_peer_sensitivity_uses_isolated_synthetic_research_cohorts(tmp_path):
    result = run_peer_sensitivity_experiment(tmp_path)
    assert result["status"] == "completed"
    assert result["data_origin"] == "synthetic"
    assert result["production_or_cross_tenant_data_used"] is False
    assert {row["peer_count"] for row in result["cohort_size_sweep"]} == {2, 3, 4}
    assert all(
        row["finding_emitted"] is False
        for row in result["cohort_size_sweep"]
        if row["peer_count"] in {2, 3}
    )
    assert (
        next(row for row in result["cohort_size_sweep"] if row["peer_count"] == 4)[
            "finding_emitted"
        ]
        is True
    )
    magnitude = result["outlier_magnitude_sweep"]
    assert [row["subject_closure_seconds"] for row in magnitude] == [30, 400, 750]
    assert magnitude[0]["finding_emitted"] is True
    assert all(row["finding_emitted"] is False for row in magnitude[1:])
    assert all(row["peer_count"] == 4 for row in magnitude)


def test_peer_sweep_records_matrix_risk_and_rank(tmp_path):
    from evaluation.research.peer import run_peer_sweep_experiment

    result = run_peer_sweep_experiment(
        tmp_path,
        cohort_sizes=(2, 4),
        subject_closures=(30, 600),
        spreads={"tight": (540, 660)},
    )
    matrix = {
        (row["cohort_size"], row["subject_closure_seconds"]): row
        for row in result["metrics"]["matrix"]
    }
    assert len(matrix) == 4
    # Below the minimum peer count the worker abstains.
    assert matrix[(2, 30)]["finding_emitted"] is False
    # A far-below-median subject in a tight 4-peer cohort is flagged.
    assert matrix[(4, 30)]["finding_emitted"] is True
    assert matrix[(4, 30)]["deviation_mad_units"] < -2.0
    assert matrix[(4, 600)]["finding_emitted"] is False
    for row in matrix.values():
        assert row["cohort_entities_ranked"] == row["cohort_size"] + 1
        assert 1 <= row["subject_priority_rank"] <= row["cohort_entities_ranked"]
        assert row["subject_risk_total_score"] is not None
    assert result["production_or_cross_tenant_data_used"] is False
