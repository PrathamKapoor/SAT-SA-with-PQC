"""Phase P27 — workflow augmentation: the 12 controlled benchmark
scenarios, each proven end to end through the REAL SAT-SA pipeline
(satsa.ingest -> satsa.analysis.run.RunService -> real detector
workers) to trigger its declared detector family from
policy.yaml's expected_signal_families — measured, not asserted from
the generator's own intent.

This is a presence claim, not an exhaustive-exclusivity claim: most
round-trip tests below assert the declared family IS emitted (`in
families`), not that it is the ONLY family emitted. Known/permitted
cross-detector side effects are documented inline where they occur
(e.g. multi_signal's minimal, zero-investigation-step alert also
legitimately draws a negative_space finding onto the same subject —
see that test's own comment) rather than suppressed to force scenario
purity. Only `test_healthy_control_produces_no_execution_gap_or_negative_space_signal`
asserts exhaustive absence, because healthy_control is the negative
control this benchmark actually needs that property from.

Every generated record's provenance is checked too: these are
controlled validation fixtures (provenance_type=
"derived_synthetic_workflow"), never a claim about real analyst
behavior. See public_benchmarks/__init__.py.
"""
from __future__ import annotations

import json

import pytest

from public_benchmarks.provenance import DERIVED_SYNTHETIC_WORKFLOW
from public_benchmarks.workflow_augmentation import (
    generate_peer_entity_workflow,
    generate_workflow,
    get_scenario,
    list_scenarios,
    load_policy,
    provenance_manifest,
    write_submission,
)

BASE = 1499414400.0  # 2017-07-07T08:00:00Z -- inside the CIC-IDS2017 collection window


def _alert(i, *, severity="critical", asset_id="10.0.0.1", created_at=None,
          native_id=None):
    return {
        "native_id": native_id or f"src-alert-{i}",
        "created_at": created_at if created_at is not None else BASE + i * 3600,
        "severity": severity,
        "category": "DDoS",
        "asset_ids": [asset_id],
    }


def _run_scenario(scenario_id, alerts, assets=None, tmp_path=None):
    """Generate, write, ingest, and analyze a scenario. Returns
    (signal_rule_categories: set[str], submission_dir: Path)."""
    bundle = generate_workflow(
        alerts, assets or [], scenario_id=scenario_id, source_dataset="TEST-SOURCE")
    sub = tmp_path / scenario_id
    write_submission(sub, bundle, original_assets=assets or [])

    from qsmlops.database.engine import SQLiteDatabaseEngine
    from qsmlops.database.migrations import MigrationRunner
    from satsa.service import SatsaService

    eng = SQLiteDatabaseEngine(tmp_path / f"{scenario_id}.db")
    eng.connect()
    MigrationRunner(eng).migrate()
    svc = SatsaService(eng)
    entity = svc.register_entity(f"BENCH-{scenario_id}", sector="benchmark",
                                   environment_class="public-dataset")
    assessment = svc.open_assessment(entity.id, BASE - 86400, BASE + 30 * 86400)

    files = {}
    for cat in ("alerts", "cases", "investigation_steps", "escalations",
                "dispositions", "assets"):
        p = sub / f"{cat}.csv"
        if p.exists():
            files[cat] = p
    ingest_result = svc.submit(assessment.id, files)
    svc.run_analysis(entity.id, assessment.id)

    rows = eng.query_all(
        "SELECT DISTINCT rule_or_category FROM satsa_findings"
        " WHERE state='signal' AND observation_id IN"
        " (SELECT id FROM satsa_observations WHERE run_id IN"
        " (SELECT id FROM satsa_runs WHERE entity_id=?))", (entity.id,))
    families = {r["rule_or_category"] for r in rows}
    return families, sub, ingest_result


# ---------------------------------------------------------------------------
# policy.yaml structural integrity
# ---------------------------------------------------------------------------

def test_policy_declares_exactly_twelve_scenarios():
    assert len(list_scenarios()) == 12


def test_every_scenario_has_required_keys():
    policy = load_policy()
    for s in policy["scenarios"]:
        assert "scenario_id" in s
        assert "description" in s
        assert "expects_signal_families" in s
        assert "params" in s


def test_get_scenario_raises_for_unknown_id():
    with pytest.raises(KeyError):
        get_scenario("not-a-real-scenario")


def test_scenario_ids_are_unique():
    ids = list_scenarios()
    assert len(ids) == len(set(ids))


# ---------------------------------------------------------------------------
# provenance
# ---------------------------------------------------------------------------

def test_every_generated_record_carries_provenance(tmp_path):
    alerts = [_alert(i) for i in range(3)]
    bundle = generate_workflow(alerts, [], scenario_id="healthy_control",
                               source_dataset="TEST-SOURCE")
    for c in bundle.cases:
        assert c["provenance"]["provenance_type"] == DERIVED_SYNTHETIC_WORKFLOW
    for s in bundle.investigation_steps:
        assert s["provenance"]["provenance_type"] == DERIVED_SYNTHETIC_WORKFLOW
    for d in bundle.dispositions:
        assert d["provenance"]["provenance_type"] == DERIVED_SYNTHETIC_WORKFLOW


def test_provenance_manifest_written_alongside_csvs(tmp_path):
    alerts = [_alert(i) for i in range(3)]
    bundle = generate_workflow(alerts, [], scenario_id="healthy_control",
                               source_dataset="TEST-SOURCE")
    sub = tmp_path / "sub1"
    manifest = write_submission(sub, bundle, original_assets=[])
    assert (sub / "provenance_manifest.json").exists()
    on_disk = json.loads((sub / "provenance_manifest.json").read_text(encoding="utf-8"))
    assert on_disk == manifest
    assert manifest["scenario_id"] == "healthy_control"
    assert len(manifest["records"]["cases"]) == 3


def test_csv_files_do_not_contain_a_provenance_column(tmp_path):
    """The provenance tag lives in the manifest, never inside the
    satsa.ingest-facing CSVs themselves."""
    alerts = [_alert(i) for i in range(2)]
    bundle = generate_workflow(alerts, [], scenario_id="healthy_control",
                               source_dataset="TEST-SOURCE")
    sub = tmp_path / "sub2"
    write_submission(sub, bundle, original_assets=[])
    for name in ("alerts.csv", "cases.csv", "investigation_steps.csv",
                 "escalations.csv", "dispositions.csv"):
        header = (sub / name).read_text(encoding="utf-8").splitlines()[0]
        assert "provenance" not in header.lower()


# ---------------------------------------------------------------------------
# missing_escalation_file: the omitted-category property
# ---------------------------------------------------------------------------

def test_missing_escalation_file_scenario_omits_the_file_entirely(tmp_path):
    alerts = [_alert(i) for i in range(2)]
    bundle = generate_workflow(alerts, [], scenario_id="missing_escalation_file",
                               source_dataset="TEST-SOURCE")
    assert bundle.omit_categories == frozenset({"escalations"})
    sub = tmp_path / "sub3"
    write_submission(sub, bundle, original_assets=[])
    assert not (sub / "escalations.csv").exists()
    assert (sub / "alerts.csv").exists()


# ---------------------------------------------------------------------------
# full round-trip: each scenario's declared signal family, measured
# through the real satsa.ingest -> RunService -> detector pipeline
# ---------------------------------------------------------------------------

def test_healthy_control_produces_no_execution_gap_or_negative_space_signal(tmp_path):
    alerts = ([_alert(i, severity="critical", asset_id=f"host-{i % 2}")
              for i in range(3)]
             + [_alert(i + 10, severity="high", asset_id=f"host-{i % 2}")
                for i in range(2)])
    assets = [{"native_id": "host-0", "criticality": "critical"},
             {"native_id": "host-1", "criticality": "high"}]
    families, _, _ = _run_scenario("healthy_control", alerts, assets, tmp_path)
    execution_gap_or_negative_space = {
        f for f in families
        if f.startswith("execution_gap.") or f.startswith("negative_space.")}
    assert execution_gap_or_negative_space == set()


def test_fast_closure_scenario_triggers_expected_family(tmp_path):
    alerts = [_alert(i, severity="critical", asset_id=f"host-{i}") for i in range(2)]
    families, _, _ = _run_scenario("fast_closure", alerts, [], tmp_path)
    assert "execution_gap.fast_closure" in families


def test_no_escalation_scenario_triggers_expected_family(tmp_path):
    alerts = [_alert(i, severity="critical", asset_id=f"host-{i}") for i in range(2)]
    families, _, _ = _run_scenario("no_escalation", alerts, [], tmp_path)
    assert "execution_gap.critical_without_escalation" in families
    assert "execution_gap.fast_closure" not in families


def test_ack_no_investigation_scenario_triggers_expected_family(tmp_path):
    alerts = [_alert(i, severity="high", asset_id=f"host-{i}") for i in range(2)]
    families, _, _ = _run_scenario("ack_no_investigation", alerts, [], tmp_path)
    assert "execution_gap.ack_without_investigation" in families
    assert "negative_space.missing_investigation" not in families


def test_missing_investigation_scenario_triggers_expected_family(tmp_path):
    alerts = [_alert(i, severity="critical", asset_id=f"host-{i}") for i in range(2)]
    families, _, _ = _run_scenario("missing_investigation", alerts, [], tmp_path)
    assert "negative_space.missing_investigation" in families
    assert "execution_gap.ack_without_investigation" not in families


def test_missing_escalation_file_scenario_triggers_expected_family(tmp_path):
    alerts = [_alert(i, severity="critical", asset_id=f"host-{i}") for i in range(2)]
    families, _, _ = _run_scenario("missing_escalation_file", alerts, [], tmp_path)
    assert "negative_space.missing_escalation" in families


def test_silent_critical_asset_scenario_triggers_expected_family(tmp_path):
    alerts = [_alert(i, severity="critical", asset_id="active-host") for i in range(2)]
    assets = [{"native_id": "active-host", "criticality": "high"}]
    families, _, _ = _run_scenario("silent_critical_asset", alerts, assets, tmp_path)
    assert "negative_space.missing_monitoring" in families


def test_low_activity_scenario_triggers_expected_family(tmp_path):
    alerts = [_alert(i, severity="critical", asset_id=f"host-{i}") for i in range(2)]
    assets = [{"native_id": "host-0", "criticality": "critical"},
             {"native_id": "host-1", "criticality": "high"},
             {"native_id": "host-2", "criticality": "critical"}]
    families, _, _ = _run_scenario("low_activity", alerts, assets, tmp_path)
    assert "negative_space.unexpectedly_low_activity" in families


def test_template_investigation_scenario_triggers_expected_family(tmp_path):
    alerts = [_alert(i, severity="medium", asset_id="host-0") for i in range(3)]
    families, _, _ = _run_scenario("template_investigation", alerts, [], tmp_path)
    assert "execution_gap.repeated_investigation_pattern" in families


def test_recurring_no_remediation_scenario_triggers_expected_family(tmp_path):
    alerts = [_alert(i, severity="medium", asset_id="host-0") for i in range(2)]
    families, _, _ = _run_scenario("recurring_no_remediation", alerts, [], tmp_path)
    assert "execution_gap.recurring_without_remediation" in families


def test_multi_signal_scenario_triggers_both_expected_families(tmp_path):
    alerts = [_alert(i, severity="critical", asset_id=f"host-{i}") for i in range(2)]
    families, _, _ = _run_scenario("multi_signal", alerts, [], tmp_path)
    assert "execution_gap.fast_closure" in families
    assert "execution_gap.critical_without_escalation" in families


def test_multi_signal_findings_are_corroborated_by_correlation_fusion(tmp_path):
    """The whole point of multi_signal: the two rule families above
    must reference the SAME underlying alert, so
    satsa.analysis.correlation flags them as corroborated -- not
    merely two independent, unrelated findings."""
    alerts = [_alert(0, severity="critical", asset_id="host-0")]
    families, sub, _ = _run_scenario("multi_signal", alerts, [], tmp_path)
    # multi_signal's minimal workflow (no escalation, zero investigation
    # steps) legitimately also trips negative_space/ack_without_investigation
    # side effects -- the two families under test here are the deliberate
    # target, not an exhaustive claim about every family this scenario emits.
    assert {"execution_gap.fast_closure",
            "execution_gap.critical_without_escalation"} <= families

    from qsmlops.database.engine import SQLiteDatabaseEngine
    from satsa.analysis.risk import compute_entity_risk

    eng = SQLiteDatabaseEngine(tmp_path / "multi_signal.db")
    eng.connect()
    entity_row = eng.query_one(
        "SELECT id FROM satsa_entities WHERE display_name=?",
        ("BENCH-multi_signal",))
    profile = compute_entity_risk(eng, entity_row["id"])
    corroborated = [c for c in profile.correlation_clusters if c.corroborated]
    assert len(corroborated) >= 1
    # At least one cluster corroborates BOTH target rules on the same
    # subject -- the scenario's whole point. (The same minimal, zero-
    # investigation-step alert legitimately also draws a negative_space
    # finding onto the same subject, which is itself a real, honest
    # demonstration of correlation.py's cross-family clustering working
    # as designed, not a test artifact to suppress.)
    target = {"execution_gap.fast_closure", "execution_gap.critical_without_escalation"}
    matched = False
    for cluster in corroborated:
        referenced_rules = set()
        for fid in cluster.finding_ids:
            row = eng.query_one(
                "SELECT rule_or_category FROM satsa_findings WHERE id=?", (fid,))
            referenced_rules.add(row["rule_or_category"])
        if target <= referenced_rules:
            matched = True
            break
    assert matched, "no corroborated cluster referenced both target rules"


# ---------------------------------------------------------------------------
# peer_outlier: subject + peer cohort
# ---------------------------------------------------------------------------

def test_peer_outlier_scenario_triggers_peer_benchmark(tmp_path):
    from qsmlops.database.engine import SQLiteDatabaseEngine
    from qsmlops.database.migrations import MigrationRunner
    from satsa.analysis.run import RunService
    from satsa.service import SatsaService

    eng = SQLiteDatabaseEngine(tmp_path / "peer.db")
    eng.connect()
    MigrationRunner(eng).migrate()
    svc = SatsaService(eng)

    # 4 peer entities, healthy-paced closures.
    for p in range(4):
        alerts = [_alert(i, severity="critical", asset_id=f"peer{p}-host")
                 for i in range(1)]
        bundle = generate_peer_entity_workflow(
            alerts, [], source_dataset="TEST-SOURCE", peer_label=f"p{p}")
        sub = tmp_path / f"peer-{p}"
        write_submission(sub, bundle, original_assets=[])
        entity = svc.register_entity(f"PEER-{p}", sector="benchmark",
                                       environment_class="public-dataset")
        assessment = svc.open_assessment(entity.id, BASE - 86400, BASE + 30 * 86400)
        files = {c: sub / f"{c}.csv" for c in
                 ("alerts", "cases", "investigation_steps", "escalations",
                  "dispositions") if (sub / f"{c}.csv").exists()}
        svc.submit(assessment.id, files)
        svc.run_analysis(entity.id, assessment.id)

    # Subject entity: dramatically faster closures than peers.
    subject_alerts = [_alert(i, severity="critical", asset_id="subj-host")
                      for i in range(1)]
    bundle = generate_workflow(
        subject_alerts, [], scenario_id="peer_outlier",
        source_dataset="TEST-SOURCE")
    sub = tmp_path / "subject"
    write_submission(sub, bundle, original_assets=[])
    entity = svc.register_entity("SUBJECT", sector="benchmark",
                                   environment_class="public-dataset")
    assessment = svc.open_assessment(entity.id, BASE - 86400, BASE + 30 * 86400)
    files = {c: sub / f"{c}.csv" for c in
             ("alerts", "cases", "investigation_steps", "escalations",
              "dispositions") if (sub / f"{c}.csv").exists()}
    svc.submit(assessment.id, files)
    svc.run_analysis(entity.id, assessment.id)

    rows = eng.query_all(
        "SELECT DISTINCT rule_or_category FROM satsa_findings"
        " WHERE state='signal' AND observation_id IN"
        " (SELECT id FROM satsa_observations WHERE run_id IN"
        " (SELECT id FROM satsa_runs WHERE entity_id=?))", (entity.id,))
    families = {r["rule_or_category"] for r in rows}
    peer_benchmark_families = {f for f in families if f.startswith("peer_benchmark.")}
    assert peer_benchmark_families, (
        f"expected a peer_benchmark.* finding for the outlier subject, got {families}")
