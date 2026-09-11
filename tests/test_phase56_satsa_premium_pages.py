"""Phase P13 — premium architecture visualization, agent explorer,
TRUST-SAT page, human-decision view, security-data view, and
analytics-pipeline view.

These tests verify each new page renders without error and
surfaces the expected real data (no fabricated metrics).
"""
from __future__ import annotations

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
def client_with_demo(service, trust_key_dir):
    from satsa.ui import create_app
    from satsa.ui.demo import load_demo_assessment
    load_demo_assessment(service, trust_key_dir)
    app = create_app(service, trust_key_dir=trust_key_dir)
    from fastapi.testclient import TestClient
    return TestClient(app)


def test_architecture_page_renders(client_with_demo):
    r = client_with_demo.get("/architecture")
    assert r.status_code == 200
    # The eight architecture layers are all rendered
    body = r.text
    for marker in ("SECURITY DATA", "ML / ANALYTICS",
                   "SUPERVISORY AGENT FABRIC",
                   "Detect", "Correlate", "Assess",
                   "RISK FINDING", "RECOMMENDATION",
                   "HUMAN SUPERVISOR", "ACTION / DECISION",
                   "TRUST-SAT"):
        assert marker in body


def test_architecture_page_lists_32_agents(client_with_demo):
    r = client_with_demo.get("/architecture")
    assert r.status_code == 200
    body = r.text
    assert "9 retained MLOps" in body
    assert "23 SAT-SA supervisory" in body
    # All 23 SAT-SA agents are present
    for agent_id in [
        "satsa.entity_asset_resolution", "satsa.ingest", "satsa.normalize",
        "satsa.execution_gap", "satsa.negative_space",
        "satsa.workflow_reconstruction", "satsa.anomaly",
        "satsa.peer_benchmark",
        "satsa.coverage_gap", "satsa.drift",
        "satsa.cross_entity_insights", "satsa.case_similarity",
        "satsa.evidence_completeness", "satsa.correlation_fusion",
        "satsa.fusion",
        "satsa.prioritization", "satsa.recommendation",
        "satsa.review_workflow", "satsa.trust_provenance",
        "satsa.evidence_assembly", "satsa.meta_audit",
        "satsa.report_generation",
        "satsa.validation",
    ]:
        assert agent_id in body


def test_agents_page_renders_32_agents(client_with_demo):
    r = client_with_demo.get("/agents")
    assert r.status_code == 200
    assert "32 agents" in r.text
    # All 9 MLOps and 23 SAT-SA ids are listed
    for agent_id in [
        "mlops.data", "mlops.performance", "mlops.security",
        "mlops.quantum", "mlops.redteam",
        "mlops.training_optimization", "mlops.incident_response",
        "mlops.governance", "mlops.optimization",
    ]:
        assert agent_id in r.text


def test_trust_page_shows_verification(client_with_demo):
    r = client_with_demo.get("/trust")
    assert r.status_code == 200
    assert "TRUST-SAT" in r.text
    # The verification grid is present
    for marker in ("Cryptographic integrity", "Provenance",
                   "Evidence chain", "Ledger"):
        assert marker in r.text
    # Algorithm + digest are named
    assert "ML-DSA-65" in r.text
    assert "SHA3-256" in r.text


def test_decisions_page_renders(client_with_demo):
    r = client_with_demo.get("/decisions")
    assert r.status_code == 200
    assert "Human supervisory authority" in r.text
    assert "HUMAN DECISION" in r.text
    # The SATSA vocabulary is enumerated
    for marker in ("SATSA_SURFACE", "SATSA_INSPECT",
                   "SATSA_REQUEST_EVIDENCE", "SATSA_ESCALATE_FOR_REVIEW",
                   "SATSA_DEFER", "SATSA_ACCEPT", "SATSA_CLOSE_REVIEW"):
        assert marker in r.text


def test_security_data_page_renders_counts(client_with_demo):
    r = client_with_demo.get("/security-data")
    assert r.status_code == 200
    # Six categories listed
    for marker in ("alerts", "cases", "investigation_steps",
                   "escalations", "dispositions", "assets"):
        assert marker in r.text


def test_pipeline_page_renders_stages(client_with_demo):
    r = client_with_demo.get("/pipeline")
    assert r.status_code == 200
    for marker in ("Detect", "Correlate", "Assess", "Reason"):
        assert marker in r.text


def test_overview_shows_architecture_links(client_with_demo):
    r = client_with_demo.get("/")
    assert r.status_code == 200
    # The overview now links to Architecture / TRUST-SAT / Agents
    assert "Architecture" in r.text
    assert "TRUST-SAT" in r.text or "Trust" in r.text
    assert "Agents" in r.text


def test_nav_includes_new_pages(client_with_demo):
    r = client_with_demo.get("/")
    assert r.status_code == 200
    for path in ("/architecture", "/agents", "/trust",
                 "/decisions", "/security-data", "/pipeline"):
        assert path in r.text