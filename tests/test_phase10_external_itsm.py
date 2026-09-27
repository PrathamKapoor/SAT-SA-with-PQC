"""Adapter and experiment tests on a tiny hand-written event log.

The fixture below is written in the UCI-498 column format for testing only;
it is not the real dataset and produces no research result.
"""

from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path

import pytest

from evaluation.research.external_itsm import run_external_itsm_experiment, spearman
from public_benchmarks.itsm_incident_log.adapter import (
    build_submissions,
    load_incidents,
    map_incident,
)

COLUMNS = [
    "number", "incident_state", "active", "reassignment_count", "reopen_count",
    "sys_mod_count", "made_sla", "caller_id", "opened_by", "opened_at",
    "sys_created_by", "sys_created_at", "sys_updated_by", "sys_updated_at",
    "contact_type", "location", "category", "subcategory", "u_symptom", "cmdb_ci",
    "impact", "urgency", "priority", "assignment_group", "assigned_to", "knowledge",
    "u_priority_confirmation", "notify", "problem_id", "rfc", "vendor", "caused_by",
    "closed_code", "resolved_by", "resolved_at", "closed_at",
]  # fmt: skip


def _events(number, group, *, day, sla_missed, reassign=False, priority="3 - Moderate"):
    base = {c: "?" for c in COLUMNS}
    base.update(
        number=number, opened_at=f"{day}/3/2016 09:00", priority=priority,
        assignment_group=group, closed_code="code 6",
        resolved_at=f"{day}/3/2016 12:00", closed_at=f"{day + 2}/3/2016 12:00",
        reopen_count="0", active="true",
    )  # fmt: skip
    states = [
        ("New", "0", "09:05", "true"),
        ("Active", "1", "09:30", "true"),
        ("Active", "2", "10:30", "false" if sla_missed else "true"),
        ("Resolved", "3", "12:00", "false" if sla_missed else "true"),
        ("Closed", "4", "12:00", "false" if sla_missed else "true"),
    ]
    rows = []
    for index, (state, mod, clock, made) in enumerate(states):
        row = dict(base)
        row.update(
            incident_state=state, sys_mod_count=mod, made_sla=made,
            sys_updated_at=f"{day}/3/2016 {clock}", sys_updated_by=f"Updated by {index}",
            reassignment_count="1" if reassign and index >= 2 else "0",
        )  # fmt: skip
        rows.append(row)
    return rows


def _write_log(path: Path) -> Path:
    rows = []
    groups = ["Group 1", "Group 2", "Group 3", "Group 4"]
    for g_index, group in enumerate(groups):
        for i in range(4):
            rows += _events(
                f"INC{g_index}{i:03d}",
                group,
                day=1 + i,
                sla_missed=i < g_index,
                reassign=i == 0,
                priority="1 - Critical" if i == 0 else "3 - Moderate",
            )
    rows += _events("INC9999", "?", day=5, sla_missed=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    return path


def test_mapping_is_source_derived_and_hides_labels(tmp_path):
    source = _write_log(tmp_path / "incident_event_log.csv")
    incidents = load_incidents(source)
    mapped = map_incident("INC0000", incidents["INC0000"], Counter())
    assert mapped["alert"]["severity"] == "critical"
    assert mapped["alert"]["ack_at"] < mapped["alert"]["closed_at"]
    assert [s["action_type"] for s in mapped["steps"]] == ["active", "active"]
    assert len(mapped["escalations"]) == 1
    assert mapped["case"]["status"] == "closed"

    out = tmp_path / "derived"
    report = build_submissions(source, out, min_incidents=2)
    assert report["groups_eligible"] == 4
    assert report["incidents_unknown_group_excluded"] == 1
    assert report["provenance"]["provenance_type"] == "derived_from_source"
    for path in (out / "submissions").rglob("*.csv"):
        text = path.read_text(encoding="utf-8")
        assert "made_sla" not in text and "sla" not in text.lower()
    labels = json.loads((out / "labels.json").read_text())
    assert labels["groups"]["Group 4"]["sla_miss_rate"] == 0.75
    assert not (out / "submissions" / "Group_1" / "assets.csv").exists()
    with pytest.raises(ValueError):
        build_submissions(source, tmp_path, min_incidents=2)


def test_spearman_handles_ties_and_perfect_order():
    assert spearman([1, 2, 3, 4], [10, 20, 30, 40]) == pytest.approx(1.0)
    assert spearman([1, 2, 3, 4], [4, 3, 2, 1]) == pytest.approx(-1.0)
    assert spearman([1, 1, 1, 1], [1, 2, 3, 4]) is None


def test_external_experiment_runs_unchanged_pipeline(tmp_path):
    source = _write_log(tmp_path / "incident_event_log.csv")
    result = run_external_itsm_experiment(
        tmp_path / "scratch", source_csv=source, min_incidents=2, random_trials=20
    )
    metrics = result["metrics"]
    assert metrics["design"]["entities"] == 4
    assert set(metrics["feasibility"]["run_status_counts"]) <= {"completed", "partial"}
    # Regression: X02 recorded ingestion totals as null (wrong key).
    totals = metrics["feasibility"]["ingest_row_totals"]
    assert totals["received"] > 0
    assert totals["accepted"] + totals["rejected"] == totals["received"]
    for entity in metrics["entities"].values():
        assert entity["ingest_counts"]["alerts"]["received"] >= 2
    assert set(metrics["ranking_vs_sla_miss_quartile"]) == {
        "satsa_priority",
        "incident_volume",
        "slowest_median_resolution",
        "reassignment_rate",
        "random",
    }
    assert "satsa_risk_score" in metrics["association_with_sla_miss_rate"]
    with pytest.raises(ValueError):
        run_external_itsm_experiment(
            tmp_path / "scratch2", source_csv=source, expected_source_sha256="0" * 64
        )


def test_failure_analysis_diagnoses_without_changing_detectors(tmp_path):
    from evaluation.research.external_failure import run_external_failure_analysis

    source = _write_log(tmp_path / "incident_event_log.csv")
    result = run_external_failure_analysis(
        tmp_path / "scratch", source_csv=source, min_incidents=2
    )
    metrics = result["metrics"]
    assert metrics["design"]["detectors_thresholds_weights_changed"] is False
    assert metrics["detector_saturation"]
    for family, value in metrics["detector_saturation"].items():
        assert value["groups_evaluated"] == 4, family
        assert 0 <= value["flagging_rate"] <= 1
    assert {c["classification"] for c in metrics["construct_validity"]} >= {
        "directly observed",
        "proxy",
        "unavailable",
    }
    checks = metrics["label_and_temporal_checks"]
    assert checks["counts"]["incidents"] == 16
    assert checks["counts"]["sla_missed"] == 6
    prevalence = next(iter(metrics["groups"].values()))["prevalence"]
    assert 0 <= prevalence["cases_without_steps_rate"] <= 1
    assert set(metrics["prevalence_vs_sla_miss"]) == set(prevalence)
