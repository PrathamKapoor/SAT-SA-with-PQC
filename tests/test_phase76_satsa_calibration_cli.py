"""Phase P26 — `sat-sa calibrate` CLI wiring for the N17 calibration
workflow.

Proves the workflow is reachable through a real execution path (not
just a library nobody calls): propose -> test (against a real ingested
scope + real expert labels) -> approve (gated by calibration.approve,
same permission model as `sat-sa review`) -> deploy -> history, all
through `satsa.cli.main`, plus the negative paths (missing credential,
wrong role) failing closed.
"""
from __future__ import annotations

import json

import pytest

from satsa import cli as satsa_cli


BASE = 1735689600.0


@pytest.fixture()
def scope(tmp_path):
    """A real ingested entity/assessment with one critical alert
    closed in 200s — qualifies as fast-closure under the default
    600s threshold."""
    sub = tmp_path / "CSE-CALIB"
    sub.mkdir()
    (sub / "alerts.csv").write_text(
        "native_id,created_at,severity,acknowledged_at,closed_at\n"
        f"A1,{BASE},critical,{BASE + 30},{BASE + 200}\n",
        encoding="utf-8")

    db = tmp_path / "satsa.db"
    keys = tmp_path / "keys"
    rc = satsa_cli.main([
        "--db", str(db), "--trust-key-dir", str(keys),
        "ingest", "CSE-CALIB", str(sub),
        "--period-start", str(BASE), "--period-end", str(BASE + 30 * 86400),
    ])
    assert rc == 0

    from qsmlops.database.engine import SQLiteDatabaseEngine
    eng = SQLiteDatabaseEngine(db)
    eng.connect()
    eid = eng.query_one("SELECT id FROM satsa_entities LIMIT 1")["id"]
    aid = eng.query_one(
        "SELECT id FROM satsa_assessments WHERE entity_id=?", (eid,))["id"]
    eng.close()

    expert_labels_path = tmp_path / "labels.json"
    expert_labels_path.write_text(json.dumps([{
        "layer": "execution_gap.fast_closure",
        "is_signal": False,
        "finding_category": "execution_gap.fast_closure",
        "reviewer": "expert1",
        "rationale": "200s closure was a legitimate benign auto-closure",
        "confidence": 0.9,
        "timestamp": BASE,
    }]), encoding="utf-8")

    return {
        "db": str(db), "keys": str(keys), "entity_id": eid,
        "assessment_id": aid, "expert_labels": str(expert_labels_path),
    }


@pytest.fixture()
def supervisor_token(scope):
    from satsa import security as satsa_security
    from qsmlops.database.engine import SQLiteDatabaseEngine
    from qsmlops.security.identity.models import KIND_HUMAN
    from pathlib import Path
    eng = SQLiteDatabaseEngine(scope["db"])
    eng.connect()
    idsvc = satsa_security.build_identity_service(eng, ledger_dir=Path(scope["keys"]))
    identity = idsvc.create_identity(KIND_HUMAN, "sup1", owner="sup1",
                                     role="satsa_supervisor")
    token = idsvc.issue_credential(identity.id)
    eng.close()
    return token


@pytest.fixture()
def viewer_token(scope):
    from satsa import security as satsa_security
    from qsmlops.database.engine import SQLiteDatabaseEngine
    from qsmlops.security.identity.models import KIND_HUMAN
    from pathlib import Path
    eng = SQLiteDatabaseEngine(scope["db"])
    eng.connect()
    idsvc = satsa_security.build_identity_service(eng, ledger_dir=Path(scope["keys"]))
    identity = idsvc.create_identity(KIND_HUMAN, "view1", owner="view1",
                                     role="satsa_viewer")
    token = idsvc.issue_credential(identity.id)
    eng.close()
    return token


def _run(scope, extra, capsys):
    rc = satsa_cli.main(["--db", scope["db"], "--trust-key-dir", scope["keys"],
                         "calibrate"] + extra)
    out = capsys.readouterr().out
    return rc, out


def test_propose_requires_thresholds(scope, capsys):
    with pytest.raises(SystemExit):
        satsa_cli.main([
            "--db", scope["db"], "--trust-key-dir", scope["keys"],
            "calibrate", "propose", "--id", "cli-p1",
            "--worker", "fast-closure",
            "--layer", "execution_gap.fast_closure",
            "--rationale", "tighten it", "--proposer", "alice"])


def test_full_cli_workflow(scope, supervisor_token, capsys):
    rc, out = _run(scope, [
        "propose", "--id", "cli-p1", "--worker", "fast-closure",
        "--layer", "execution_gap.fast_closure",
        "--thresholds", json.dumps({"critical_max_seconds": 100.0}),
        "--rationale", "false positives on legitimate fast closures",
        "--proposer", "alice"], capsys)
    assert rc == 0
    assert json.loads(out)["status"] == "proposed"

    rc, out = _run(scope, [
        "test", "--id", "cli-p1",
        "--entity-id", scope["entity_id"],
        "--assessment-id", scope["assessment_id"],
        "--expert-labels", scope["expert_labels"]], capsys)
    assert rc == 0
    tested = json.loads(out)
    assert tested["status"] == "tested"
    assert tested["proposed_metric"]["false_positives"] < tested["baseline_metric"]["false_positives"]

    rc, out = _run(scope, [
        "approve", "--id", "cli-p1",
        "--rationale", "measurable improvement",
        "--credential", supervisor_token], capsys)
    assert rc == 0
    assert json.loads(out)["status"] == "approved"

    rc, out = _run(scope, [
        "deploy", "--id", "cli-p1", "--version", "fast-closure-v2",
        "--credential", supervisor_token], capsys)
    assert rc == 0
    deployed = json.loads(out)
    assert deployed["status"] == "deployed"
    assert deployed["deployed_version"] == "fast-closure-v2"

    rc, out = _run(scope, ["history", "--id", "cli-p1"], capsys)
    assert rc == 0
    history = json.loads(out)
    assert [r["status"] for r in history] == [
        "proposed", "tested", "approved", "deployed"]


def test_approve_requires_credential(scope, capsys):
    _run(scope, [
        "propose", "--id", "cli-p2", "--worker", "fast-closure",
        "--layer", "execution_gap.fast_closure",
        "--thresholds", json.dumps({"critical_max_seconds": 100.0}),
        "--rationale", "r", "--proposer", "alice"], capsys)
    _run(scope, [
        "test", "--id", "cli-p2",
        "--entity-id", scope["entity_id"],
        "--assessment-id", scope["assessment_id"],
        "--expert-labels", scope["expert_labels"]], capsys)
    with pytest.raises(SystemExit):
        satsa_cli.main([
            "--db", scope["db"], "--trust-key-dir", scope["keys"],
            "calibrate", "approve", "--id", "cli-p2",
            "--rationale", "ok"])  # no --credential


def test_approve_rejects_viewer_role(scope, viewer_token, capsys):
    _run(scope, [
        "propose", "--id", "cli-p3", "--worker", "fast-closure",
        "--layer", "execution_gap.fast_closure",
        "--thresholds", json.dumps({"critical_max_seconds": 100.0}),
        "--rationale", "r", "--proposer", "alice"], capsys)
    _run(scope, [
        "test", "--id", "cli-p3",
        "--entity-id", scope["entity_id"],
        "--assessment-id", scope["assessment_id"],
        "--expert-labels", scope["expert_labels"]], capsys)
    with pytest.raises(SystemExit):
        satsa_cli.main([
            "--db", scope["db"], "--trust-key-dir", scope["keys"],
            "calibrate", "approve", "--id", "cli-p3",
            "--rationale", "ok", "--credential", viewer_token])


def test_deploy_before_approve_rejected(scope, supervisor_token, capsys):
    _run(scope, [
        "propose", "--id", "cli-p4", "--worker", "fast-closure",
        "--layer", "execution_gap.fast_closure",
        "--thresholds", json.dumps({"critical_max_seconds": 100.0}),
        "--rationale", "r", "--proposer", "alice"], capsys)
    with pytest.raises(SystemExit):
        satsa_cli.main([
            "--db", scope["db"], "--trust-key-dir", scope["keys"],
            "calibrate", "deploy", "--id", "cli-p4",
            "--version", "v2", "--credential", supervisor_token])


def test_unknown_worker_rejected(scope, capsys):
    _run(scope, [
        "propose", "--id", "cli-p5", "--worker", "does-not-exist",
        "--layer", "some.layer",
        "--thresholds", json.dumps({"x": 1}),
        "--rationale", "r", "--proposer", "alice"], capsys)
    with pytest.raises(SystemExit):
        satsa_cli.main([
            "--db", scope["db"], "--trust-key-dir", scope["keys"],
            "calibrate", "test", "--id", "cli-p5",
            "--entity-id", scope["entity_id"],
            "--assessment-id", scope["assessment_id"],
            "--expert-labels", scope["expert_labels"]])
