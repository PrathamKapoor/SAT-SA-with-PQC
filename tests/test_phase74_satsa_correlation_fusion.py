"""Phase P26 — Correlation & Signal Fusion Agent.

The proposed agent taxonomy the user supplied splits "Correlation &
Signal Fusion" out from "Entity Risk Scoring" (this project's existing
Fusion Agent / ``satsa.analysis.risk.compute_entity_risk``). This
module (``satsa.analysis.correlation``) is the real, distinct
implementation: it clusters signal findings that share a scoped
subject and flags clusters where two or more different detector
*families* corroborate each other, independent of and prior to risk
dimension scoring.

Tests cover the pure clustering function directly (deterministic,
structural — no statistical claims to validate) and the wiring into
``compute_entity_risk`` via ``EntityRiskProfile.correlation_clusters``.
"""
from __future__ import annotations

import json

import pytest

from satsa.analysis.correlation import (
    CorrelationCluster,
    correlate_findings,
    corroborated_clusters,
    rule_family,
)
from satsa.analysis.risk import compute_entity_risk
from satsa.analysis.run import RunService
from satsa.domain.entities import Submission
from satsa.domain.workflow import Alert
from satsa.store.repositories import AlertStore, SubmissionStore


BASE = 1735689600.0


def _f(fid, rule, subjects):
    return {"id": fid, "rule_or_category": rule,
            "scoped_subjects_json": json.dumps(subjects)}


# ---------------------------------------------------------------------------
# pure-function tests
# ---------------------------------------------------------------------------

def test_rule_family_extracts_first_segment():
    assert rule_family("execution_gap.fast_closure") == "execution_gap"
    assert rule_family("negative_space.missing_escalation") == "negative_space"
    assert rule_family("") == "unknown"


def test_no_cluster_when_subject_referenced_once():
    findings = [_f("f1", "execution_gap.fast_closure", ["A1"])]
    clusters = correlate_findings(findings)
    assert clusters == []


def test_cluster_forms_when_two_findings_share_a_subject():
    findings = [
        _f("f1", "execution_gap.fast_closure", ["A1"]),
        _f("f2", "negative_space.missing_escalation", ["A1"]),
    ]
    clusters = correlate_findings(findings)
    assert len(clusters) == 1
    c = clusters[0]
    assert c.subject == "A1"
    assert set(c.finding_ids) == {"f1", "f2"}


def test_cluster_corroborated_when_families_differ():
    findings = [
        _f("f1", "execution_gap.fast_closure", ["A1"]),
        _f("f2", "negative_space.missing_escalation", ["A1"]),
    ]
    clusters = correlate_findings(findings)
    assert clusters[0].corroborated is True
    assert clusters[0].rule_families == ["execution_gap", "negative_space"]
    assert "independent corroboration" in clusters[0].rationale


def test_cluster_not_corroborated_when_same_family_fires_twice():
    """Two findings from the *same* detector family sharing a subject
    is not corroboration — it is the expected within-family behaviour
    (e.g. a worker emitting more than one finding for one alert)."""
    findings = [
        _f("f1", "execution_gap.fast_closure", ["A1"]),
        _f("f2", "execution_gap.ack_without_investigation", ["A1"]),
    ]
    clusters = correlate_findings(findings)
    assert len(clusters) == 1
    assert clusters[0].corroborated is False
    assert clusters[0].rule_families == ["execution_gap"]
    assert "not cross-family corroboration" in clusters[0].rationale


def test_corroborated_clusters_filters_to_flagged_only():
    findings = [
        _f("f1", "execution_gap.fast_closure", ["A1"]),
        _f("f2", "execution_gap.ack_without_investigation", ["A1"]),
        _f("f3", "execution_gap.fast_closure", ["A2"]),
        _f("f4", "negative_space.missing_escalation", ["A2"]),
    ]
    clusters = correlate_findings(findings)
    assert len(clusters) == 2
    strong = corroborated_clusters(clusters)
    assert len(strong) == 1
    assert strong[0].subject == "A2"


def test_multiple_shared_subjects_each_become_their_own_cluster():
    findings = [
        _f("f1", "execution_gap.fast_closure", ["A1", "A2"]),
        _f("f2", "negative_space.missing_escalation", ["A1"]),
        _f("f3", "anomaly.closure_time.high", ["A2"]),
    ]
    clusters = correlate_findings(findings)
    subjects = {c.subject for c in clusters}
    assert subjects == {"A1", "A2"}


def test_a_finding_listing_the_same_subject_twice_is_deduplicated():
    """Guards against a worker's scoped_subjects containing a duplicate
    entry inflating a cluster to look like two findings agree."""
    findings = [
        _f("f1", "execution_gap.fast_closure", ["A1", "A1"]),
    ]
    clusters = correlate_findings(findings)
    assert clusters == []  # only one distinct finding referenced A1


def test_correlation_cluster_to_dict_round_trips_fields():
    c = CorrelationCluster(subject="A1", finding_ids=["f1", "f2"],
                            rule_families=["execution_gap", "negative_space"],
                            corroborated=True, rationale="r")
    d = c.to_dict()
    assert d["subject"] == "A1"
    assert d["finding_ids"] == ["f1", "f2"]
    assert d["corroborated"] is True


# ---------------------------------------------------------------------------
# integration: wired into compute_entity_risk
# ---------------------------------------------------------------------------

@pytest.fixture()
def engine(tmp_path):
    from qsmlops.database.engine import SQLiteDatabaseEngine
    from qsmlops.database.migrations import MigrationRunner

    eng = SQLiteDatabaseEngine(tmp_path / "satsa.db")
    eng.connect()
    MigrationRunner(eng).migrate()
    yield eng
    eng.close()


@pytest.fixture()
def service(engine):
    from satsa.service import SatsaService
    return SatsaService(engine)


def _open_scope(service, name):
    entity = service.register_entity(name, sector="defence",
                                       environment_class="on-prem")
    a = service.open_assessment(entity.id, BASE, BASE + 30 * 86400)
    return entity, a


def _ingest_alerts(service, engine, entity, assessment, rows, sub_id=None):
    import time
    sub_id = sub_id or f"sub-{entity.id}"
    SubmissionStore(engine).insert(
        Submission(id=sub_id, assessment_id=assessment.id, source_system="unit",
                   declared_period_start=BASE, declared_period_end=BASE + 30 * 86400,
                   file_digests={"x": "d"}, declared_counts={"alerts": len(rows)},
                   received_at=time.time(), signature_status="unsigned"),
        entity_id=entity.id, ingest_status="accepted", ingest_report={},
        snapshot_digest=f"snap-{entity.id}", created_at=time.time())
    for r in rows:
        a = Alert(entity_id=entity.id, assessment_id=assessment.id,
                  native_id=r["native_id"], created_at=r["created"],
                  mapped_severity=r["severity"],
                  acknowledged_at=r.get("ack"),
                  closed_at=r.get("closed"),
                  source_record_ref=f"sr-{r['native_id']}")
        AlertStore(engine).insert(a, submission_id=sub_id)


def test_entity_risk_profile_carries_correlation_clusters_field(service, engine):
    entity, a = _open_scope(service, "CSE-CORR")
    _ingest_alerts(service, engine, entity, a, [{
        "native_id": "A1", "created": BASE, "severity": "critical",
        "ack": BASE + 60, "closed": BASE + 120,
    }])
    RunService(engine).run(entity.id, a.id)
    profile = service.compute_risk(entity.id)
    assert isinstance(profile.correlation_clusters, list)
    d = profile.to_dict()
    assert "correlation_clusters" in d


def test_no_run_profile_has_empty_correlation_clusters(service):
    entity, _ = _open_scope(service, "CSE-CORR-EMPTY")
    profile = service.compute_risk(entity.id)
    assert profile.correlation_clusters == []


def test_correlation_clusters_only_reference_signal_findings(service, engine):
    """compute_entity_risk() filters to state=='signal' before both
    dimension scoring and correlation — a finding that never reached
    signal state must not appear in a cluster."""
    entity, a = _open_scope(service, "CSE-CORR-SIGNAL")
    _ingest_alerts(service, engine, entity, a, [{
        "native_id": "A1", "created": BASE, "severity": "critical",
        "ack": BASE + 60, "closed": BASE + 120,
    }])
    RunService(engine).run(entity.id, a.id)
    profile = compute_entity_risk(engine, entity.id)
    referenced_ids = {fid for c in profile.correlation_clusters
                       for fid in c.finding_ids}
    if referenced_ids:
        rows = engine.query_all(
            "SELECT id, state FROM satsa_findings WHERE id IN ({})".format(
                ",".join("?" * len(referenced_ids))),
            list(referenced_ids))
        assert all(r["state"] == "signal" for r in rows)
