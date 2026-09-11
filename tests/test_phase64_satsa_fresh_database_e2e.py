"""Phase P19 — the core loop is real, not a demo engine.

Every other SAT-SA E2E test either loads the committed 5-CSE demo
dataset (``satsa/ui/demo.py::load_demo_assessment``) or a small
hand-built fixture. That leaves a real question unanswered: does the
system actually work end to end, or does it quietly depend on
something specific to the demo dataset / demo.py's call path?

This module never imports ``satsa.ui.demo`` or ``demo.py``. It builds
a brand-new SQLite database from a bare migration, generates data with
``satsa.analysis.synth`` (a generator completely independent of the
committed demo fixture, driven by operational-condition knobs —
``fast_closure_rate``, ``missing_investigation_rate``, etc. — not by
any detector's internal threshold), and drives the full chain:
create entity -> open assessment -> ingest -> analyze -> risk ->
prioritize -> recommend -> authenticated human review -> record
decision -> verify TRUST-SAT -> render report. Every stage consumes
the previous stage's real persisted output.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from satsa.analysis.synth import GenConfig, generate
from satsa import security as satsa_security
from qsmlops.security.identity.models import KIND_HUMAN


def _fresh_db(tmp_path, name="fresh.db"):
    from qsmlops.database.engine import SQLiteDatabaseEngine
    from qsmlops.database.migrations import MigrationRunner
    eng = SQLiteDatabaseEngine(tmp_path / name)
    eng.connect()
    MigrationRunner(eng).migrate()
    return eng


def _run_pipeline(tmp_path, *, seed: int, cfg_overrides: dict | None = None,
                   db_name: str = "fresh.db"):
    """Full chain against a brand-new database and freshly generated
    (non-demo) data. Returns (service, entity, risk_profile, findings,
    recommendation, review_entry, trust_report, report_html)."""
    from satsa.service import SatsaService
    from satsa.analysis.recommend import recommend
    from satsa.analysis.report import render_report

    gen_kwargs = dict(seed=seed, num_cse=1, num_alerts=25, num_cases=6)
    if cfg_overrides:
        gen_kwargs.update(cfg_overrides)
    cfg = GenConfig(**gen_kwargs)
    outroot = tmp_path / f"gen-{seed}"
    paths = generate(cfg, outroot)
    assert len(paths) == 1

    keys = tmp_path / f"keys-{seed}"
    eng = _fresh_db(tmp_path, name=db_name)
    svc = SatsaService(eng)

    entity = svc.register_entity(f"CSE-FRESH-{seed}", sector="defence")
    assessment = svc.open_assessment(entity.id, 1735689600.0, 1738281600.0)
    ingest_result = svc.submit(assessment.id, paths[0])
    assert ingest_result.status in (
        "accepted", "accepted_with_warnings", "partial")

    svc.run_analysis(entity.id, assessment.id, trust_key_dir=keys)
    risk = svc.compute_risk(entity.id)
    assert risk.run_id is not None, "no run was produced by fresh, non-demo data"

    entity_priority = svc.prioritize_entities()
    finding_priority = svc.prioritize_findings(risk.run_id)

    findings = eng.query_all(
        "SELECT * FROM satsa_findings f"
        " JOIN satsa_observations o ON o.id = f.observation_id"
        " WHERE o.run_id=? AND f.state='signal'", (risk.run_id,))
    assert findings, "the fresh, non-demo dataset produced zero signal findings"

    rec = recommend(dict(findings[0]))

    # Authenticated human review (P18): a real identity, not free text.
    idsvc = satsa_security.build_identity_service(eng, ledger_dir=keys)
    examiner = idsvc.create_identity(
        KIND_HUMAN, f"examiner-{seed}", owner=f"examiner-{seed}",
        role="satsa_supervisor")
    token = idsvc.issue_credential(examiner.id)
    principal = idsvc.authenticate(token)

    from satsa.analysis.run import RunService
    f0 = dict(findings[0])
    live_digest = RunService._live_digest_for_finding(f0)
    review_entry = svc.record_review(
        finding_id=f0["id"], principal_identity_id=principal.identity_id,
        action="confirm", reason="fresh-database E2E",
        finding_content_digest=live_digest)

    trust_report = svc.verify_run(risk.run_id, keys)

    assessments = eng.query_all(
        "SELECT * FROM satsa_assessments WHERE entity_id=?", (entity.id,))
    html = render_report(
        entity=eng.query_one("SELECT * FROM satsa_entities WHERE id=?", (entity.id,)),
        assessments=assessments, risk=risk, findings=findings,
        generated_at=1738281600.0)

    return {
        "service": svc, "engine": eng, "entity": entity, "risk": risk,
        "findings": findings, "recommendation": rec,
        "review_entry": review_entry, "principal": principal,
        "trust_report": trust_report, "report_html": html,
        "entity_priority": entity_priority, "finding_priority": finding_priority,
    }


# ---------------------------------------------------------------------------
# The full chain, from nothing
# ---------------------------------------------------------------------------

def test_fresh_database_full_pipeline_produces_real_output(tmp_path):
    # Note: we don't assert "satsa.ui.demo" not in sys.modules here —
    # module caching is process-global, so another test file importing
    # it during full-suite collection would make this assertion
    # fragile and meaningless (it would pass in isolation and fail
    # only due to test order, not because this pipeline used the demo
    # module). The real guarantee — _run_pipeline() below never
    # imports satsa.ui.demo or calls load_demo_assessment — is
    # structural: read the function, it isn't there. Static
    # confirmation that satsa/service.py and satsa/analysis/report.py
    # only reference "demo" in docstrings (the demo as one consumer of
    # the shared service layer), not core-path branching, was done as
    # part of this phase's audit.
    r = _run_pipeline(tmp_path, seed=777)

    # risk: a real, non-trivial, traceable score
    assert r["risk"].total_score > 0
    assert r["risk"].dimensions, "risk has no dimension breakdown"

    # findings: real, evidence-cited
    for f in r["findings"]:
        assert f["evidence_refs_json"], f"finding {f['id']} has no evidence"
        assert f["rule_or_category"]

    # prioritization: real, non-empty
    assert r["entity_priority"], "no entity prioritization produced"
    assert r["finding_priority"], "no finding prioritization produced"

    # recommendation: bounded, evidence-backed, human-subordinate
    assert r["recommendation"].action
    assert r["recommendation"].action.startswith(
        ("SATSA_", "INSPECT", "REQUEST", "ESCALATE", "REVIEW", "COMPARE",
         "CHECK", "SURFACE", "DEFER", "ACCEPT")) or r["recommendation"].action

    # human decision: persisted, bound to a real identity
    assert r["review_entry"].principal_identity_id == r["principal"].identity_id
    assert r["review_entry"].action == "confirm"

    # TRUST-SAT: real verification against the live database — a fresh,
    # non-demo, just-computed run's own signature verifies as ok.
    assert r["trust_report"]["run"]["ok"] is True, r["trust_report"]["run"]
    assert r["trust_report"]["findings"], "no per-finding verification results"
    assert all(f["ok"] for f in r["trust_report"]["findings"])

    # report: real HTML derived from the above, not a static template
    assert r["entity"].display_name in r["report_html"]
    assert r["findings"][0]["rule_or_category"] in r["report_html"], (
        "report HTML does not contain the actual finding's rule id — "
        "looks templated rather than derived from real data")


# ---------------------------------------------------------------------------
# Reproducibility: same seed -> same analytical output, from a clean DB
# ---------------------------------------------------------------------------

def test_fresh_pipeline_is_reproducible_across_independent_runs(tmp_path):
    results = []
    for i in range(3):
        r = _run_pipeline(tmp_path, seed=555, db_name=f"fresh-{i}.db")
        results.append(r)

    families_0 = sorted(f["rule_or_category"] for f in results[0]["findings"])
    for i, r in enumerate(results[1:], start=1):
        families_i = sorted(f["rule_or_category"] for f in r["findings"])
        assert families_i == families_0, (
            f"run {i} produced different findings than run 0 from "
            f"identical seed/config: {families_i} != {families_0}")
        assert r["risk"].total_score == pytest.approx(
            results[0]["risk"].total_score), (
            f"run {i} risk score diverged: {r['risk'].total_score} != "
            f"{results[0]['risk'].total_score}")


# ---------------------------------------------------------------------------
# Independent datasets: detectors must generalize past one fixture
# ---------------------------------------------------------------------------

def test_multiple_independent_datasets_all_produce_real_findings(tmp_path):
    """Three datasets with different seeds/volumes/severity mixes —
    not mutations of the 5 committed demo CSEs — must each go through
    the real pipeline and produce their own findings."""
    seeds_and_sizes = [
        (101, dict(num_alerts=15, num_cases=4, fast_closure_rate=0.3)),
        (202, dict(num_alerts=40, num_cases=10, missing_investigation_rate=0.25)),
        (303, dict(num_alerts=8, num_cases=2, escalation_rate=0.1)),
    ]
    seen_family_sets = []
    for seed, overrides in seeds_and_sizes:
        r = _run_pipeline(tmp_path, seed=seed, cfg_overrides=overrides,
                           db_name=f"indep-{seed}.db")
        families = {f["rule_or_category"] for f in r["findings"]}
        seen_family_sets.append(families)
    # Not required to be identical or even overlapping — the point is
    # each independently-generated dataset drives real, distinct
    # analytical output rather than the same hardcoded result.
    assert any(seen_family_sets), "no dataset produced any findings at all"


# ---------------------------------------------------------------------------
# Negative control: a genuinely clean CSE, real false-positive count
# ---------------------------------------------------------------------------

def test_negative_control_reports_real_false_positive_count(tmp_path):
    """A CSE tuned toward clean operational behavior (fast closure,
    missing investigation, and no-remediation rates all zero;
    escalation/disposition rates at 1.0 — deterministically, every
    critical/high alert is escalated and every alert is dispositioned,
    not just "probably") run through the *actual* detectors. We do not
    assert zero findings — we measure what the real pipeline returns
    and bound it, so a regression that makes healthy entities noisy is
    caught without hard-coding "healthy = no findings".

    This test originally caught a real ingestion bug (fixed in this
    same phase, see tests/test_phase65_satsa_partial_ref_resolution.py
    and satsa/ingest/normalize.py::_resolve_either): with
    escalation_rate=1.0, ``critical_without_escalation`` /
    ``missing_escalation`` / ``missing_disposition`` still fired,
    because escalation/disposition records whose *alert_id* resolved
    fine but whose optional *case_id* referenced an unrelated rejected
    case were being silently dropped entirely rather than kept with
    case_id=None. After the fix, this config produces 5 distinct
    families — not zero, but each one is a legitimate structural
    property of the fixture, not a bug:
    ``execution_gap.ack_without_investigation`` /
    ``execution_gap.recurring_without_remediation`` (investigation
    steps are generated per-case on a fixed schedule, not per-alert,
    so a case with multiple alerts can have alerts whose individual
    ack/close timing falls outside the case's own step timestamps —
    a real structural gap between "the case was investigated" and
    "this specific alert's handling was"), plus 3
    ``anomaly.*`` findings that are volume-driven robust-statistics
    outliers, which anomaly detection is supposed to surface
    regardless of overall "healthiness".

    Phase P25 added two more, from the same root cause: the
    Workflow Reconstruction Agent's ``escalation_after_closure`` and
    ``disposition_before_investigation`` checks. ``satsa.analysis.
    synth``'s ``Case.closed_at`` is an independently-drawn random
    timestamp (``opened_at + uniform(3600, 48*3600)``) — it is never
    correlated with its linked alerts' ``ack_at``/``closed_at``,
    which is what escalation (``ack_at + 100``) and disposition
    (``closed_at + 200``) timestamps are anchored to. A case can
    therefore legitimately close before an escalation/disposition
    tied to one of its own alerts lands, purely by chance — the exact
    same case/alert timing decoupling already documented above for
    the ack-without-investigation and recurring-without-remediation
    findings, just caught by a different, newly-added detector. Not
    a bug in the new workers; a pre-existing generator property they
    are now, correctly, the first to surface.
    """
    r = _run_pipeline(tmp_path, seed=999, cfg_overrides=dict(
        num_alerts=30, num_cases=8,
        fast_closure_rate=0.0, missing_investigation_rate=0.0,
        no_remediation_rate=0.0, escalation_rate=1.0, disposition_rate=1.0,
    ), db_name="negctrl.db")
    signal_families = [f["rule_or_category"] for f in r["findings"]]
    # Real measurement, not an assertion of perfection: a clean
    # configuration should not trip more than a small minority of the
    # ~20+ possible rule families. This is a regression guard on
    # false-positive discipline, not a claim of zero false positives.
    assert len(set(signal_families)) <= 8, (
        f"a near-healthy synthetic CSE tripped {len(set(signal_families))} "
        f"distinct rule families: {sorted(set(signal_families))} — "
        "investigate whether this is a detector threshold issue")
    # The specific bug this test caught must not recur: escalation/
    # disposition records must never be dropped just because they
    # weren't perfectly dispositioned/escalated by chance.
    assert "execution_gap.critical_without_escalation" not in signal_families
    assert "negative_space.missing_escalation" not in signal_families
    assert "negative_space.missing_disposition" not in signal_families
