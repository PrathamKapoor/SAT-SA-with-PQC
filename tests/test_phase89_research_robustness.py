from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from evaluation.research.robustness import (
    declared_conditions,
    run_evidence_robustness_experiment,
)
from satsa.analysis.compval import SCENARIO_MAP

_INVALID_BY_CONTRACT = {
    "duplicate_exact:alerts",
    "duplicate_conflicting:alerts",
    "duplicate_exact:cases",
    "duplicate_conflicting:cases",
    "duplicate_exact:investigation_steps",
    "malformed_timestamp",
    "chronology_violation",
    "missing_required_column",
    "conflict:case_status_vs_closure_time",
}
_FAMILIES = {
    "control",
    "missingness",
    "duplication",
    "malformation",
    "staleness",
    "conflict",
}


@pytest.fixture(scope="module")
def mixed_result(tmp_path_factory):
    return run_evidence_robustness_experiment(
        tmp_path_factory.mktemp("robustness"),
        scenarios=("mixed",),
        rates=(0.5,),
        seeds=1,
    )


def _conditions(result):
    return {
        row["condition"]: row
        for row in result["metrics"]["per_scenario"][0]["conditions"]
    }


def test_declared_conditions_are_seeded_and_do_not_mutate_the_fixture():
    cse, _ = SCENARIO_MAP["mixed"]()
    before = json.dumps(cse.__dict__, sort_keys=True, default=str)
    first = declared_conditions(cse, rates=(0.25,), seeds=2, base_seed=7)
    second = declared_conditions(cse, rates=(0.25,), seeds=2, base_seed=7)

    assert json.dumps(cse.__dict__, sort_keys=True, default=str) == before
    assert [c.name for c, _, _ in first] == [c.name for c, _, _ in second]
    assert [truth for _, _, truth in first] == [truth for _, _, truth in second]
    names = [c.name for c, _, _ in first]
    assert names[0] == "control"
    assert "omit_records:0.25:seed7" in names
    assert "omit_records_cascade:0.25:seed8" in names
    stale = [c for c, _, _ in first if c.family == "staleness"]
    assert len(stale) == 3
    assert all(c.expected_validation is None for c in stale)
    assert {c.family for c, _, _ in first} == _FAMILIES
    assert all(c.expected_effect for c, _, _ in first)


def test_control_runs_real_hosted_analysis_and_is_scored_against_catalog(mixed_result):
    control = _conditions(mixed_result)["control"]

    assert mixed_result["status"] == "completed"
    assert control["validation_status"] == "valid"
    assert control["status"] == "completed"
    assert control["emitted_families"]
    assert control["traceability"]["findings"] == control["finding_count"]
    catalog = mixed_result["metrics"]["per_scenario"][0]["control_vs_catalog"]
    assert catalog["expected_families"]
    assert catalog["emitted_families"] == control["emitted_families"]


def test_contract_violations_are_rejected_without_analysis(mixed_result):
    rows = _conditions(mixed_result)
    for name in _INVALID_BY_CONTRACT:
        row = rows[name]
        assert row["validation_status"] == "invalid", name
        assert row["validation_matches_expected"] is True, name
        assert row["status"] == "rejected_by_validation", name
        assert "emitted_families" not in row
        assert row["paired_delta_vs_control"] is None
        assert row["validation_errors"], name


def test_omissions_are_compared_with_paired_control(mixed_result):
    rows = _conditions(mixed_result)
    escalations = rows["omit_category:escalations"]
    assert escalations["expected_validation"] == "valid"
    assert escalations["status"] == "completed"
    delta = escalations["paired_delta_vs_control"]
    assert delta is not None
    assert set(delta) >= {"families_added", "families_removed", "risk_fields_changed"}
    assert "entity_id" not in delta["risk_fields_changed"]

    # Omitting the only case leaves its investigation steps dangling, which
    # the all-or-nothing hosted validator rejects; this is declared up front.
    cases = rows["omit_category:cases"]
    assert cases["expected_validation"] == "invalid"
    assert cases["validation_matches_expected"] is True

    cascade = rows["omit_records_cascade:0.50:seed0"]
    truth = cascade["perturbation_ground_truth"]
    assert not any(truth["dangling_references_after_omission"].values())
    assert cascade["validation_status"] == "valid"


def test_valid_duplicates_and_conflicts_reach_analysis(mixed_result):
    rows = _conditions(mixed_result)
    for name in (
        "duplicate_near:investigation_steps",
        "duplicate_near:dispositions",
        "conflict:contradictory_dispositions",
        "conflict:closed_case_open_alert",
        "conflict:escalation_without_investigation",
    ):
        row = rows[name]
        assert row["expected_validation"] == "valid", name
        assert row["status"] == "completed", name
        assert row["paired_delta_vs_control"] is not None, name
        metrics = row["catalog_family_metrics"]
        assert metrics["labels_apply_to"] == "unperturbed fixture"


def test_staleness_is_observational_and_aggregates_are_consistent(mixed_result):
    rows = _conditions(mixed_result)
    stale = [row for row in rows.values() if row["family"] == "staleness"]
    assert len(stale) == 3
    for row in stale:
        assert row["expected_validation"] is None
        assert row["validation_matches_expected"] is None
        assert row["validation_status"] in {"valid", "invalid"}

    metrics = mixed_result["metrics"]
    conformance = metrics["validation_contract_conformance"]
    rows = [
        r
        for r in metrics["per_scenario"][0]["conditions"]
        if r["status"] != "not_applicable"
    ]
    assert conformance["conditions_with_expectation"] == len(rows) - len(stale)
    assert set(conformance["by_family"]) == _FAMILIES
    assert conformance["matches"] == sum(
        bool(r["validation_matches_expected"]) for r in rows
    )
    by_rate = metrics["record_omission_by_rate"]
    assert set(by_rate) == {"omit_records:0.50", "omit_records_cascade:0.50"}
    assert all(entry["replicates"] == 1 for entry in by_rate.values())


def test_cli_writes_immutable_bundle(tmp_path):
    path = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / ("run_evidence_robustness_experiment.py")
    )
    spec = importlib.util.spec_from_file_location("robustness_cli", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    argv = [
        "--out",
        str(tmp_path),
        "--experiment-id",
        "robustness-test",
        "--scenarios",
        "healthy",
        "--rates",
        "0.5",
        "--seeds",
        "1",
    ]
    assert module.main(argv) == 0
    bundle = tmp_path / "robustness-test"
    manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "completed"
    assert manifest["dataset"]["data_origin"] == "synthetic"
    assert (bundle / "processed" / "metrics.csv").is_file()
    with pytest.raises(SystemExit):
        module.main(argv)
