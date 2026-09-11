"""Phase P25 (agent expansion) — Entity & Asset Resolution Agent (N3).

A cross-period view of an entity's asset inventory, driven entirely
through the RunContext.extras channel (no unscoped database handle).
The vanished-asset check compares the previous assessment's asset
native_ids (computed once by RunService._build_run_extras and reused
from the same prior_dataset load already done for drift KPIs) against
the current dataset's assets.
"""
from __future__ import annotations

import pytest

from satsa.analysis.workers.entity_asset_resolution import (
    EntityAssetResolutionWorker,
)
from satsa.contracts.worker import RunContext, SnapshotRef
from satsa.domain.entities import Asset
from satsa.store.dataset import CanonicalDataset

BASE = 1735689600.0


def _asset(*, id, native_id) -> Asset:
    return Asset(id=id, entity_id="e", native_id=native_id, criticality="high")


def _ds(*, assets=None) -> CanonicalDataset:
    return CanonicalDataset(
        entity_id="e", assessment_id="a", snapshot_digest="d",
        alerts=[], cases=[], steps=[], escalations=[], dispositions=[],
        assets=assets or [],
        submitted_categories=frozenset(
            ("alerts", "cases", "investigation_steps", "escalations",
             "dispositions", "assets")))


def _ctx(extras=None) -> RunContext:
    return RunContext(run_id="run-x", entity_id="e", assessment_id="a",
                      extras=extras or {})


def _eval(worker, ds, extras=None):
    return worker.evaluate(SnapshotRef("d", "e", "a"), ds, [], None, _ctx(extras))


def test_abstains_with_no_previous_period_extra():
    ds = _ds(assets=[_asset(id="A1", native_id="host-1")])
    batch = _eval(EntityAssetResolutionWorker(), ds, extras={})
    assert batch.state == "insufficient_data"
    assert batch.findings == []


def test_vanished_asset_fires():
    ds = _ds(assets=[_asset(id="A1", native_id="host-1")])
    batch = _eval(EntityAssetResolutionWorker(), ds,
                  extras={"previous_period_assets": ["host-1", "host-2"]})
    f = next(f for f in batch.findings
             if f.rule_or_category == "entity_asset_resolution.vanished_assets")
    assert f.scoped_subjects == ["host-2"]
    assert f.state == "signal"


def test_no_vanished_assets_no_signal():
    ds = _ds(assets=[_asset(id="A1", native_id="host-1"),
                     _asset(id="A2", native_id="host-2")])
    batch = _eval(EntityAssetResolutionWorker(), ds,
                  extras={"previous_period_assets": ["host-1", "host-2"]})
    assert batch.state == "no_signal"
    assert batch.findings == []


def test_new_assets_appearing_is_not_a_vanished_asset_signal():
    """Assets appearing that weren't there before is not this
    worker's concern — only disappearance is."""
    ds = _ds(assets=[_asset(id="A1", native_id="host-1"),
                     _asset(id="A2", native_id="host-new")])
    batch = _eval(EntityAssetResolutionWorker(), ds,
                  extras={"previous_period_assets": ["host-1"]})
    assert batch.state == "no_signal"


def test_empty_previous_period_assets_list_is_not_abstention():
    """An explicit empty list (prior period submitted zero assets)
    is different from the key being absent entirely — no vanished
    assets is correctly reported as no_signal, not insufficient_data,
    since the comparison *was* meaningfully performed."""
    ds = _ds(assets=[_asset(id="A1", native_id="host-1")])
    batch = _eval(EntityAssetResolutionWorker(), ds,
                  extras={"previous_period_assets": []})
    assert batch.state == "no_signal"


def test_worker_is_registered_in_the_agent_roster():
    from satsa.supervisor import list_agents
    ids = {a.agent_id for a in list_agents()}
    assert "satsa.entity_asset_resolution" in ids


def test_previous_period_assets_extra_is_wired_end_to_end(tmp_path):
    """A real second-period run must see the first period's assets
    via extras, driven entirely by RunService — not a hand-built
    RunContext."""
    from qsmlops.database.engine import SQLiteDatabaseEngine
    from qsmlops.database.migrations import MigrationRunner
    from satsa.service import SatsaService
    from satsa.domain.entities import Submission
    from satsa.domain.entities import Asset as AssetRow
    from satsa.store.repositories import AssetStore, SubmissionStore

    eng = SQLiteDatabaseEngine(tmp_path / "x.db"); eng.connect()
    MigrationRunner(eng).migrate()
    svc = SatsaService(eng)
    e = svc.register_entity("CSE-VANISH", sector="defence")

    # Period 1: two assets.
    a1 = svc.open_assessment(e.id, BASE, BASE + 2592000)
    SubmissionStore(eng).insert(Submission(
        id="sub-1", assessment_id=a1.id, source_system="t",
        declared_period_start=BASE, declared_period_end=BASE + 2592000,
        file_digests={}, declared_counts={}, received_at=BASE,
        signature_status="unsigned"),
        entity_id=e.id, ingest_status="accepted", ingest_report={},
        snapshot_digest="snap1", created_at=BASE)
    AssetStore(eng).insert(AssetRow(entity_id=e.id, native_id="host-1",
                                    criticality="critical"),
                           assessment_id=a1.id, submission_id="sub-1")
    AssetStore(eng).insert(AssetRow(entity_id=e.id, native_id="host-2",
                                    criticality="critical"),
                           assessment_id=a1.id, submission_id="sub-1")
    svc.run_analysis(e.id, a1.id)

    # Period 2 (later): only one of the two assets remains.
    period2_start = BASE + 2592000 + 86400
    a2 = svc.open_assessment(e.id, period2_start, period2_start + 2592000)
    SubmissionStore(eng).insert(Submission(
        id="sub-2", assessment_id=a2.id, source_system="t",
        declared_period_start=period2_start,
        declared_period_end=period2_start + 2592000,
        file_digests={}, declared_counts={}, received_at=period2_start,
        signature_status="unsigned"),
        entity_id=e.id, ingest_status="accepted", ingest_report={},
        snapshot_digest="snap2", created_at=period2_start)
    AssetStore(eng).insert(AssetRow(entity_id=e.id, native_id="host-1",
                                    criticality="critical"),
                           assessment_id=a2.id, submission_id="sub-2")
    result = svc.run_analysis(e.id, a2.id)

    rows = eng.query_all(
        "SELECT f.rule_or_category, f.scoped_subjects_json FROM satsa_findings f"
        " JOIN satsa_observations o ON o.id = f.observation_id"
        " WHERE o.run_id=? AND f.rule_or_category="
        "'entity_asset_resolution.vanished_assets'", (result.run_id,))
    assert len(rows) == 1
    import json
    assert json.loads(rows[0]["scoped_subjects_json"]) == ["host-2"]
