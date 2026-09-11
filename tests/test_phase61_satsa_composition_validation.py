"""Phase P15/P16-complete follow-up — real coverage for composition
validation binding.

``satsa/analysis/compval.py`` (HEAD commit ``phaseP15+P16-complete``)
closes a previously-disclosed scaffold gap: ``run_validation``'s
composition section used to compare the synthetic ground truth to
itself (``emitted_families = list(case.expected_signals)``), which
trivially always "passed". ``run_composition_validation`` instead
builds a real synthetic CSE submission, ingests it through
``SatsaService``, runs the actual analytics pipeline, and compares
*emitted* findings/actions to the ground-truth catalog.

This module shipped with no dedicated test coverage. These tests
verify the binding is real (drives an actual pipeline run per
scenario, produces a run_id, and reports honest not-executed
reasons for scenarios that require peer cohorts / multi-period
baselines a single-entity fixture cannot provide) rather than a
disguised scaffold.
"""
from __future__ import annotations

import pytest

from satsa.analysis.compval import (
    run_composition_validation,
    SCENARIO_MAP,
    NOT_EXECUTABLE_REASON,
)
from satsa.analysis.validate import synthetic_ground_truth


@pytest.fixture(scope="module")
def report():
    return run_composition_validation()


def test_shape(report):
    assert set(report.keys()) == {"executed", "not_executed", "summary"}
    summary = report["summary"]
    for key in (
        "executed_cases", "not_executed_cases",
        "signals_alignment", "action_alignment",
        "incidental_extra_signals", "at",
    ):
        assert key in summary


def test_every_ground_truth_case_is_accounted_for(report):
    all_case_ids = {c.case_id for c in synthetic_ground_truth()}
    seen = {r["case_id"] for r in report["executed"]}
    seen |= {r["case_id"] for r in report["not_executed"]}
    assert seen == all_case_ids


def test_executable_scenarios_actually_run_the_pipeline(report):
    """Every SCENARIO_MAP entry must appear as executed, with a
    real run_id — proof a live analysis run happened, not a
    fabricated comparison.
    """
    executed_by_id = {r["case_id"]: r for r in report["executed"]}
    assert len(report["executed"]) == len(SCENARIO_MAP)
    for case in synthetic_ground_truth():
        if case.scenario in SCENARIO_MAP:
            assert case.case_id in executed_by_id, case.case_id
            row = executed_by_id[case.case_id]
            assert row.get("run_id"), "expected a real run_id, not a scaffold"


def test_non_executable_scenarios_report_honest_reasons(report):
    """Scenarios that require peer cohorts / multi-period baselines
    a single-entity fixture cannot deterministically produce are
    reported as not_executed with a specific reason — never
    silently dropped or fabricated as passing.
    """
    not_executed_by_id = {r["case_id"]: r for r in report["not_executed"]}
    for case in synthetic_ground_truth():
        if case.case_id not in SCENARIO_MAP:
            assert case.case_id in not_executed_by_id
            row = not_executed_by_id[case.case_id]
            assert row["reason"], "not-executed case must carry a reason"
            assert NOT_EXECUTABLE_REASON.get(case.scenario, "") in row["reason"]
            # Honesty: ground truth expectations are still surfaced even
            # though the case could not be run.
            assert "expected_signals" in row
            assert "expected_action" in row


def test_healthy_control_produces_no_signal(report):
    """The clean-control gate: a healthy submission must not trip
    any analytical rule family. This is the specific semantics the
    HEAD commit fixed (empty-expected-signals no longer trivially
    passes under `expected <= emitted`).
    """
    row = next(r for r in report["executed"] if r["case_id"] == "healthy")
    assert row["expected_signals"] == []
    assert row["emitted_signals"] == [], (
        "healthy fixture unexpectedly tripped a signal family: "
        f"{row['emitted_signals']}")
    assert row["signals_ok"] is True


def test_fast_closure_scenario_fires_the_expected_family(report):
    row = next(r for r in report["executed"] if r["case_id"] == "eg-fast-closure")
    assert "execution_gap.fast_closure" in row["emitted_signals"]
    assert row["signals_ok"] is True


def test_missing_investigation_scenario_fires_the_expected_family(report):
    row = next(
        r for r in report["executed"]
        if r["case_id"] == "ns-missing-investigation")
    assert "negative_space.missing_investigation" in row["emitted_signals"]
    assert row["signals_ok"] is True


def test_summary_alignment_is_bounded_and_not_vacuous(report):
    summary = report["summary"]
    assert summary["executed_cases"] == len(SCENARIO_MAP)
    assert 0.0 <= summary["signals_alignment"] <= 1.0
    assert 0.0 <= summary["action_alignment"] <= 1.0
    assert summary["incidental_extra_signals"] >= 0


def test_cli_validate_wires_real_composition_binding(capsys):
    """`sat-sa validate` must expose both the legacy expected-vs-
    expected catalog (compatibility) and the real pipeline-bound
    composition report — the CLI must not duplicate business logic,
    only call into `run_validation` + `run_composition_validation`.
    """
    import json
    from satsa import cli as satsa_cli

    rc = satsa_cli.main(["--db", ":memory:", "validate"])
    assert rc == 0
    out = capsys.readouterr().out
    combined = json.loads(out)
    assert "composition_bound" in combined
    assert "composition_not_executed" in combined
    assert "composition_summary" in combined
    assert combined["composition_summary"]["executed_cases"] == len(SCENARIO_MAP)
    bound_ids = {r["case_id"] for r in combined["composition_bound"]}
    assert "healthy" in bound_ids
    assert "eg-fast-closure" in bound_ids
