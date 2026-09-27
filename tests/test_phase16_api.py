"""Phase 16 API additions: entity prioritization and canonical records."""

from test_phase6_api import dataset, headers

pytest_plugins = ["test_tenant_schema", "test_phase6_api"]


def _analysed_run(api):
    from satsa.analysis.execution import AnalysisExecutionWorker

    c = api["client"]
    entity, _, _, version, _ = dataset(api)
    start = c.post(
        "/api/v1/runs",
        headers=headers(api, key="run"),
        json={"submission_version_id": version["id"], "execution_mode": "standard"},
    )
    assert start.status_code == 202, start.text
    worker = AnalysisExecutionWorker(
        api["db"],
        worker_id="priority-test",
        audit=api["audit"],
        trust_key_dir=str(api["keys"]),
    )
    assert worker.run_once() == "awaiting_review"
    return entity, start.json()["id"], worker


def test_priorities_rank_persisted_risk_within_tenant(api):
    c = api["client"]
    empty = c.get("/api/v1/priorities", headers=headers(api, "viewer"))
    assert empty.status_code == 200, empty.text
    assert empty.json()["items"] == []

    entity, run, worker = _analysed_run(api)
    page = c.get("/api/v1/priorities", headers=headers(api, "viewer"))
    assert page.status_code == 200, page.text
    body = page.json()
    assert body["has_more"] is False
    [item] = body["items"]
    assert item["entity_id"] == entity["id"]
    assert item["run_id"] == run
    assert item["run_status"] == "awaiting_review"
    risk = c.get(f"/api/v1/runs/{run}/risk", headers=headers(api)).json()
    assert item["risk_score"] == round(risk["profile"]["total_score"], 2)
    assert item["confidence_bucket"] == risk["profile"]["confidence_bucket"]
    assert item["priority_score"] >= item["risk_score"]

    # The ranking survives the decision and terminal finalization.
    decided = c.post(
        f"/api/v1/runs/{run}/decision",
        headers=headers(api, "supervisor"),
        json={"action": "confirm", "reason": "Examined evidence"},
    )
    assert decided.status_code == 201, decided.text
    assert worker.run_once() in {"completed", "partial"}
    [after] = c.get("/api/v1/priorities", headers=headers(api)).json()["items"]
    assert after["run_id"] == run
    assert after["run_status"] in {"completed", "partial"}


def test_priorities_do_not_cross_tenants(api):
    c = api["client"]
    _analysed_run(api)
    foreign = c.get("/api/v1/priorities", headers=headers(api, "outsider"))
    assert foreign.status_code == 200, foreign.text
    assert foreign.json()["items"] == []

    # An outsider naming the other organization is refused, not served.
    spoofed = {**headers(api, "outsider"), "X-Organization-ID": api["org"]}
    assert c.get("/api/v1/priorities", headers=spoofed).status_code in {403, 404}
    unauthenticated = c.get(
        "/api/v1/priorities", headers={"X-Organization-ID": api["org"]}
    )
    assert unauthenticated.status_code == 401


def test_canonical_records_page_filter_and_evidence_link(api):
    c = api["client"]
    _, _, _, version, _ = dataset(api)
    counts = c.get(
        f"/api/v1/versions/{version['id']}/summary", headers=headers(api)
    ).json()["counts"]
    assert counts.get("alerts", 0) >= 1
    total = sum(counts.values())
    page = c.get(
        f"/api/v1/versions/{version['id']}/records?category=alerts&limit=200",
        headers=headers(api, "viewer"),
    )
    assert page.status_code == 200, page.text
    items = page.json()["items"]
    assert len(items) == counts["alerts"]
    assert all(r["category"] == "alerts" and r["payload"] for r in items)
    assert "payload_json" not in items[0]

    first = c.get(
        f"/api/v1/versions/{version['id']}/records?limit=1", headers=headers(api)
    ).json()
    assert len(first["items"]) == 1
    assert first["has_more"] is (total > 1)
    bad = c.get(
        f"/api/v1/versions/{version['id']}/records?category=secrets",
        headers=headers(api),
    )
    assert bad.status_code == 422

    foreign = c.get(
        f"/api/v1/versions/{version['id']}/records", headers=headers(api, "outsider")
    )
    assert foreign.status_code in {403, 404}


def test_finding_evidence_resolves_to_record_content(api):
    c = api["client"]
    _, run, _ = _analysed_run(api)
    version = c.get(f"/api/v1/runs/{run}", headers=headers(api)).json()[
        "submission_version_id"
    ]
    evidence = c.get(f"/api/v1/runs/{run}/evidence", headers=headers(api)).json()[
        "items"
    ]
    records = c.get(
        f"/api/v1/versions/{version}/records?limit=200", headers=headers(api)
    ).json()["items"]
    by_source = {r["source_record_id"]: r for r in records}
    assert evidence, "the analysed run cites no source records"
    for ref in evidence:
        record = by_source[ref["source_record_id"]]
        assert record["record_id"] == ref["record_id"]
        assert record["content_digest"] == ref["canonical_record_digest"]


def test_sqlite_graph_checkpointer_needs_no_postgres_driver(tmp_path, monkeypatch):
    """An offline install without the `postgres` extra can still run graph mode."""
    import importlib
    import sys

    from qsmlops.database.engine import create_engine

    monkeypatch.setitem(sys.modules, "langgraph.checkpoint.postgres", None)
    monkeypatch.setitem(sys.modules, "psycopg", None)
    # Import the module fresh so a copy cached by earlier tests cannot hide
    # a module-level PostgreSQL import.
    monkeypatch.delitem(sys.modules, "satsa.analysis.graph", raising=False)
    durable_checkpointer = importlib.import_module(
        "satsa.analysis.graph"
    ).durable_checkpointer
    engine = create_engine(f"sqlite:///{(tmp_path / 'offline.db').as_posix()}")
    with durable_checkpointer(engine) as saver:
        assert type(saver).__name__ == "SqliteSaver"
