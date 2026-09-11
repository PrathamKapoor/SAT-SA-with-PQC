"""UI smoke test: build the FastAPI app, render every page,
run the demo loader, post a review decision, hit every API
endpoint. This is the only "live" test against the UI — the
templates are simple enough that Jinja2's own error reporting
catches the rest."""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest


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


@pytest.fixture()
def trust_key_dir(tmp_path):
    return tmp_path / "trust_keys"


@pytest.fixture()
def client(service, trust_key_dir):
    from satsa.ui import create_app
    app = create_app(service, trust_key_dir=trust_key_dir)
    from fastapi.testclient import TestClient
    return TestClient(app)


@pytest.fixture()
def client_with_demo(service, trust_key_dir):
    from satsa.ui import create_app
    from satsa.ui.demo import load_demo_assessment
    load_demo_assessment(service, trust_key_dir)
    app = create_app(service, trust_key_dir=trust_key_dir)
    from fastapi.testclient import TestClient
    return TestClient(app)


def test_ui_app_builds(client):
    """The app starts and the overview page renders (even empty)."""
    r = client.get("/")
    assert r.status_code == 200
    assert "SAT-SA" in r.text
    assert "Demonstration" in r.text or "Run Demonstration" in r.text


def test_demo_load_runs_full_pipeline(client, service, engine):
    """The demo loader ingests + runs all 5 CSEs and the
    /demo/result page renders the top-risk entity."""
    r = client.post("/demo/load", follow_redirects=False)
    assert r.status_code == 303
    loc = r.headers["location"]
    assert "/demo/result" in loc
    r2 = client.get(loc)
    assert r2.status_code == 200
    assert "Demonstration" in r2.text or "Loaded" in r2.text
    # 5 entities + 5 assessments + submissions
    assert engine.query_one(
        "SELECT COUNT(*) AS c FROM satsa_entities")["c"] == 5
    assert engine.query_one(
        "SELECT COUNT(*) AS c FROM satsa_runs")["c"] == 5


def test_overview_after_demo_lists_top_risks(client_with_demo):
    r = client_with_demo.get("/")
    assert r.status_code == 200
    # top-risk entity is mentioned
    assert "CSE-EXEC" in r.text or "CSE-PEER" in r.text


def test_entities_page_after_demo(client_with_demo):
    r = client_with_demo.get("/entities")
    assert r.status_code == 200
    for cse in ("CSE-HEALTHY", "CSE-EXEC", "CSE-NEG", "CSE-ANOM", "CSE-PEER"):
        assert cse in r.text


def test_entity_detail_renders_risk_and_findings(client_with_demo, service):
    # find the CSE-EXEC entity id
    row = service._db.query_one(  # type: ignore[attr-defined]
        "SELECT id FROM satsa_entities WHERE display_name='CSE-EXEC'")
    assert row
    eid = row["id"]
    r = client_with_demo.get(f"/entities/{eid}")
    assert r.status_code == 200
    assert "Risk decomposition" in r.text or "risk" in r.text.lower()
    assert "execution_gap" in r.text


def test_findings_page_filter(client_with_demo):
    r = client_with_demo.get("/findings")
    assert r.status_code == 200
    assert "Findings" in r.text or "findings" in r.text.lower()
    r2 = client_with_demo.get("/findings?rule=peer_benchmark")
    assert r2.status_code == 200
    assert "peer_benchmark" in r2.text


def test_finding_detail_and_review_post(client_with_demo, service, engine, trust_key_dir):
    # Phase P18: the review endpoint now requires a real, authenticated
    # satsa_supervisor identity — see satsa/security.py and
    # tests/test_phase63_satsa_auth_rbac.py for the dedicated auth suite.
    from satsa import security as satsa_security
    from qsmlops.security.identity.models import KIND_HUMAN
    idsvc = satsa_security.build_identity_service(engine, ledger_dir=trust_key_dir)
    ident = idsvc.create_identity(
        KIND_HUMAN, "ui-test-examiner", owner="ui-test-examiner",
        role="satsa_supervisor")
    token = idsvc.issue_credential(ident.id)

    row = service._db.query_one(  # type: ignore[attr-defined]
        "SELECT id FROM satsa_findings WHERE state='signal' LIMIT 1")
    assert row
    fid = row["id"]
    r = client_with_demo.get(f"/findings/{fid}")
    assert r.status_code == 200
    assert "Confidence" in r.text
    r2 = client_with_demo.post(f"/findings/{fid}/review",
                                data={"action": "confirm", "reason": "ui-test"},
                                headers={"Authorization": f"Bearer {token}"},
                                follow_redirects=False)
    assert r2.status_code == 303
    rev = service._db.query_one(  # type: ignore[attr-defined]
        "SELECT * FROM satsa_review_decisions WHERE finding_id=?",
        (fid,))
    assert rev is not None
    assert rev["action"] == "confirm"
    assert rev["reason"] == "ui-test"
    assert rev["principal_identity_id"] == ident.id


def test_benchmarks_page_after_demo(client_with_demo):
    r = client_with_demo.get("/benchmarks")
    assert r.status_code == 200
    assert "Peer benchmarks" in r.text or "benchmark" in r.text.lower()


def test_queue_page_after_demo(client_with_demo):
    r = client_with_demo.get("/queue")
    assert r.status_code == 200
    assert "Review Queue" in r.text or "queue" in r.text.lower()


def test_evidence_page(client_with_demo):
    r = client_with_demo.get("/evidence")
    assert r.status_code == 200
    assert "Evidence" in r.text


def test_system_page_trust(client_with_demo):
    r = client_with_demo.get("/system")
    assert r.status_code == 200
    assert "Trust" in r.text or "trust" in r.text.lower()
    assert "verified" in r.text or "unverified" in r.text


def test_report_page_renders_html(client_with_demo, service):
    row = service._db.query_one(  # type: ignore[attr-defined]
        "SELECT id FROM satsa_entities WHERE display_name='CSE-EXEC'")
    r = client_with_demo.get(f"/reports/{row['id']}")
    assert r.status_code == 200
    assert "Assessment — CSE-EXEC" in r.text
    assert "Risk" in r.text
    assert "Findings" in r.text


def test_api_endpoints(client_with_demo):
    r = client_with_demo.get("/api/entities")
    assert r.status_code == 200
    assert isinstance(r.json(), list)
