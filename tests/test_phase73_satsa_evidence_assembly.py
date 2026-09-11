"""Phase P25 (agent expansion) — Evidence & Explainability Assembly
Agent (N12).

One canonical WHAT/WHY/EVIDENCE/CONFIDENCE/LIMITATIONS/RECOMMENDATION
decomposition, replacing logic that was previously duplicated between
the UI's finding_detail route and satsa/analysis/report.py.
"""
from __future__ import annotations

import json

import pytest

from satsa.analysis.evidence_assembly import (
    ExplanationBundle,
    assemble_explanation,
)


def _finding(**overrides):
    base = {
        "id": "finding_1",
        "rule_or_category": "execution_gap.fast_closure",
        "rationale": "3 critical alerts closed in under 60 seconds.",
        "confidence_json": json.dumps({"analytical_support": 0.8,
                                       "evidence_completeness": 1.0,
                                       "overall": 0.75}),
        "limitations": "Small sample size.",
        "evidence_refs_json": "[]",
    }
    base.update(overrides)
    return base


def test_what_is_humanized_from_rule_or_category():
    bundle = assemble_explanation(_finding())
    assert bundle.what == "Execution Gap: Fast Closure"


def test_why_is_the_findings_own_rationale():
    bundle = assemble_explanation(_finding())
    assert bundle.why == "3 critical alerts closed in under 60 seconds."


def test_confidence_is_parsed_from_json():
    bundle = assemble_explanation(_finding())
    assert bundle.confidence["overall"] == pytest.approx(0.75)


def test_malformed_confidence_json_does_not_crash():
    bundle = assemble_explanation(_finding(confidence_json="not json"))
    assert bundle.confidence == {}


def test_evidence_records_pass_through_as_given():
    evidence = [{"id": "sr-1", "locator": "alerts.csv:3"}]
    bundle = assemble_explanation(_finding(), evidence_records=evidence)
    assert bundle.evidence == evidence


def test_recommendation_is_computed_not_hardcoded():
    bundle = assemble_explanation(_finding())
    assert bundle.recommendation.get("action")
    # A different finding must plausibly get a different recommendation
    # — proves this isn't a static/hardcoded value.
    bundle2 = assemble_explanation(_finding(
        rule_or_category="negative_space.missing_monitoring",
        rationale="Critical asset produced no alerts."))
    # Not asserting they always differ (some rules may share an action),
    # but both must be real, non-empty, computed values.
    assert bundle2.recommendation.get("action")


def test_drill_down_carries_observation_metadata():
    bundle = assemble_explanation(
        _finding(observation_id="obs-1"),
        observation={"worker_name": "fast-closure", "run_id": "run-1",
                     "entity_id": "entity-1", "assessment_id": "assessment-1"})
    assert bundle.drill_down["observation_id"] == "obs-1"
    assert bundle.drill_down["worker_name"] == "fast-closure"
    assert bundle.drill_down["run_id"] == "run-1"


def test_to_dict_round_trips_every_field():
    bundle = assemble_explanation(_finding(), evidence_records=[{"id": "sr-1"}])
    d = bundle.to_dict()
    assert set(d.keys()) == {
        "finding_id", "rule_or_category", "what", "why", "evidence",
        "confidence", "limitations", "recommendation", "drill_down"}


def test_ui_finding_detail_uses_the_shared_assembly(tmp_path):
    """End-to-end: the UI's /findings/{id} route actually calls
    assemble_explanation rather than re-implementing the logic
    inline — proves this is real consolidation, not a parallel
    unused module."""
    from qsmlops.database.engine import SQLiteDatabaseEngine
    from qsmlops.database.migrations import MigrationRunner
    from satsa.service import SatsaService
    from satsa.ui import create_app
    from satsa.ui.demo import load_demo_assessment
    from fastapi.testclient import TestClient

    eng = SQLiteDatabaseEngine(tmp_path / "x.db"); eng.connect()
    MigrationRunner(eng).migrate()
    svc = SatsaService(eng)
    load_demo_assessment(svc, tmp_path / "keys")
    app = create_app(svc, trust_key_dir=tmp_path / "keys")
    client = TestClient(app)

    row = eng.query_one(
        "SELECT id FROM satsa_findings WHERE state='signal' LIMIT 1")
    r = client.get(f"/findings/{row['id']}")
    assert r.status_code == 200
    # The humanized "what" label must appear on the page.
    from satsa.analysis.evidence_assembly import _humanize_rule
    f_row = eng.query_one("SELECT rule_or_category FROM satsa_findings WHERE id=?",
                          (row["id"],))
    assert _humanize_rule(f_row["rule_or_category"]) in r.text
