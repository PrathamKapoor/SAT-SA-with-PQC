"""Phase P25-lite — browser-facing CSE data upload is real, not for show.

Answers the question directly: can an operator actually get their own
CSE's data into SAT-SA through the web UI, or is everything limited to
the committed demo dataset? These tests upload a hand-built submission
through the actual `POST /ingest` multipart endpoint (not the CLI, not
`load_demo_assessment`) and assert on real, computed output.

`/ingest` calls the exact same `SatsaService.submit()` +
`run_analysis()` path `sat-sa ingest`/`sat-sa analyze` use — no
separate ingestion logic lives in the UI layer.
"""
from __future__ import annotations

from pathlib import Path

import pytest

ALERTS_CSV = (
    "AlertID,timestamp,priority,type,ack_at,resolved_at,case,host\n"
    "ALRT-1,2026-08-01T09:14:00Z,P1,ransomware-behavior,"
    "2026-08-01T09:14:30Z,2026-08-01T09:15:10Z,INC-1,payroll-db-01\n"
    "ALRT-2,2026-08-02T11:02:00Z,P1,lateral-movement,"
    "2026-08-02T11:03:00Z,2026-08-02T11:03:45Z,INC-2,payroll-db-01\n"
)
CASES_CSV = (
    "CaseID,created_at,status,resolve_time,assignee,alerts,reason_notes\n"
    "INC-1,2026-08-01T09:14:10Z,closed,2026-08-01T09:15:10Z,"
    "analyst-a,ALRT-1,closed as benign after 40s\n"
    "INC-2,2026-08-02T11:02:20Z,closed,2026-08-02T11:03:45Z,"
    "analyst-a,ALRT-2,closed as benign after 45s\n"
)
ASSETS_CSV = (
    "host,criticality,environment,controls\n"
    "payroll-db-01,critical,prod,EDR;DLP\n"
)


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
    from fastapi.testclient import TestClient
    app = create_app(service, trust_key_dir=trust_key_dir)
    return TestClient(app)


@pytest.fixture()
def analyst_token(engine, trust_key_dir):
    from satsa import security as satsa_security
    from qsmlops.security.identity.models import KIND_HUMAN
    idsvc = satsa_security.build_identity_service(engine, ledger_dir=trust_key_dir)
    ident = idsvc.create_identity(
        KIND_HUMAN, "upload-analyst", owner="upload-analyst", role="satsa_analyst")
    return idsvc.issue_credential(ident.id)


def _files():
    return {
        "alerts": ("alerts.csv", ALERTS_CSV, "text/csv"),
        "cases": ("cases.csv", CASES_CSV, "text/csv"),
        "assets": ("assets.csv", ASSETS_CSV, "text/csv"),
    }


def test_ingest_page_loads(client):
    r = client.get("/ingest")
    assert r.status_code == 200
    assert "alerts" in r.text.lower()


def test_unauthenticated_upload_is_rejected(client):
    r = client.post("/ingest", data={
        "entity_name": "SHOULD-FAIL",
        "period_start": "2026-08-01T00:00:00Z",
        "period_end": "2026-09-01T00:00:00Z",
    }, files=_files())
    assert r.status_code == 401


def test_viewer_role_cannot_ingest(client, engine, trust_key_dir):
    from satsa import security as satsa_security
    from qsmlops.security.identity.models import KIND_HUMAN
    idsvc = satsa_security.build_identity_service(engine, ledger_dir=trust_key_dir)
    ident = idsvc.create_identity(
        KIND_HUMAN, "viewer-only", owner="viewer-only", role="satsa_viewer")
    token = idsvc.issue_credential(ident.id)
    r = client.post("/ingest",
                     headers={"Authorization": f"Bearer {token}"},
                     data={"entity_name": "SHOULD-FAIL",
                           "period_start": "2026-08-01T00:00:00Z",
                           "period_end": "2026-09-01T00:00:00Z"},
                     files=_files())
    assert r.status_code == 403


def test_missing_alerts_file_is_rejected(client, analyst_token):
    r = client.post("/ingest",
                     headers={"Authorization": f"Bearer {analyst_token}"},
                     data={"entity_name": "NO-ALERTS",
                           "period_start": "2026-08-01T00:00:00Z",
                           "period_end": "2026-09-01T00:00:00Z"},
                     files={"cases": ("cases.csv", CASES_CSV, "text/csv")},
                     follow_redirects=False)
    assert r.status_code == 303
    assert "error=" in r.headers["location"]


def test_real_upload_produces_real_computed_findings(
        client, analyst_token, service):
    r = client.post(
        "/ingest",
        headers={"Authorization": f"Bearer {analyst_token}"},
        data={
            "entity_name": "REAL-UPLOAD-CSE",
            "sector": "banking", "environment": "prod",
            "period_start": "2026-08-01T00:00:00Z",
            "period_end": "2026-09-01T00:00:00Z",
            "source_system": "test-upload",
        },
        files=_files(), follow_redirects=False)
    assert r.status_code == 303
    entity_url = r.headers["location"]
    assert entity_url.startswith("/entities/")
    entity_id = entity_url.rsplit("/", 1)[-1]

    # The redirect target must itself render real, non-empty analysis —
    # not a stub "processing" page.
    detail = client.get(entity_url)
    assert detail.status_code == 200
    assert "REAL-UPLOAD-CSE" in detail.text
    assert "execution_gap" in detail.text

    # And the underlying data is real, queryable, computed — not a
    # canned response: the fast-closure finding (both alerts closed
    # in <60s) must actually be present.
    row = service._db.query_one(
        "SELECT f.id FROM satsa_findings f"
        " JOIN satsa_observations o ON o.id = f.observation_id"
        " WHERE o.entity_id=? AND f.rule_or_category="
        "'execution_gap.fast_closure' AND f.state='signal'",
        (entity_id,))
    assert row is not None, "the uploaded data's genuine fast-closure pattern was not detected"

    # Column-alias tolerance: the uploaded CSV used AlertID/priority/
    # host/case, not native_id/severity/asset_id/case_id — proves
    # this isn't only wired to one exact column naming convention.
    alert_row = service._db.query_one(
        "SELECT mapped_severity FROM satsa_alerts WHERE native_id='ALRT-1'")
    assert alert_row is not None
    assert alert_row["mapped_severity"] == "critical"  # P1 -> critical


def test_uploading_the_same_entity_name_twice_reuses_the_entity(
        client, analyst_token, service):
    common = {
        "entity_name": "REPEAT-CSE",
        "period_start": "2026-08-01T00:00:00Z",
        "period_end": "2026-09-01T00:00:00Z",
    }
    r1 = client.post("/ingest",
                      headers={"Authorization": f"Bearer {analyst_token}"},
                      data=common, files=_files(), follow_redirects=False)
    r2 = client.post("/ingest",
                      headers={"Authorization": f"Bearer {analyst_token}"},
                      data=common, files=_files(), follow_redirects=False)
    assert r1.headers["location"] == r2.headers["location"], (
        "re-submitting under the same entity name should reuse the "
        "entity, not silently create a duplicate")
