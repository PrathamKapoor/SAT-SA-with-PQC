"""Phase 5 registry API tests.

Exercises the /registry/* surface end-to-end against a real pipeline:
trust inspection/evaluation, governed approval (including refusal),
revocation, and rejection of invalid operations.
"""
from __future__ import annotations

import pytest

fastapi_testclient = pytest.importorskip("fastapi.testclient")

from qsmlops.api.app import create_app  # noqa: E402
from qsmlops.config import PlatformConfig  # noqa: E402
from qsmlops.pipeline.selfheal import SelfHealingMLOps  # noqa: E402
from qsmlops.pipeline.training import make_synthetic_regression  # noqa: E402


@pytest.fixture()
def client(tmp_path):
    config = PlatformConfig(tmp_path / "phase5_api")
    pipe = SelfHealingMLOps(config)
    ds = make_synthetic_regression(200, seed=42)
    pipe.provision_dataset("api-data", ds)
    app = create_app(pipe)
    yield fastapi_testclient.TestClient(app), pipe
    pipe.close()


def _trained(pipe, model="api-model"):
    return pipe.train_and_register(model, "api-data")


class TestRegistryApiReads:
    def test_registry_models_lists_trust_state(self, client):
        http, pipe = client
        result = _trained(pipe)
        response = http.get("/registry/models")
        assert response.status_code == 200
        rows = response.json()["models"]
        row = next(r for r in rows if r["version_id"] == result["version_id"])
        # trained but not yet evaluated: trust columns empty until evaluation
        assert row["state"] == "REGISTERED"
        assert row["model_name"] == "api-model"

    def test_trust_endpoint_requires_evaluation_first(self, client):
        http, pipe = client
        result = _trained(pipe)
        response = http.get(f"/registry/trust/{result['version_id']}")
        assert response.status_code == 404
        assert "no trust evaluation" in response.json()["detail"]

    def test_unknown_version_rejected(self, client):
        http, _ = client
        assert http.get("/registry/trust/deadbeef").status_code == 404
        assert http.get("/registry/versions/deadbeef").status_code == 404


class TestRegistryApiTrust:
    def test_request_and_fetch_trust_evaluation(self, client):
        http, pipe = client
        result = _trained(pipe)
        vid = result["version_id"]

        refreshed = http.post(f"/registry/trust/{vid}", json={"actor": "tester"})
        assert refreshed.status_code == 200
        body = refreshed.json()
        assert body["decision"] == "TRUSTED"
        assert body["promotion_eligible"] is True
        assert body["components"]["security"] == 100.0

        fetched = http.get(f"/registry/trust/{vid}")
        assert fetched.status_code == 200
        assert fetched.json()["report"]["decision"] == "TRUSTED"

    def test_version_detail_includes_latest_trust(self, client):
        http, pipe = client
        result = _trained(pipe)
        http.post(f"/registry/trust/{result['version_id']}", json={})
        detail = http.get(f"/registry/versions/{result['version_id']}")
        assert detail.status_code == 200
        body = detail.json()
        assert body["is_active_deployment"] is False
        assert body["trust"]["trust_decision"] == "TRUSTED"


class TestRegistryApiMutations:
    def test_governed_approval_via_api(self, client):
        http, pipe = client
        result = _trained(pipe)
        vid = result["version_id"]
        pipe.evaluate_version(vid)  # -> VERIFIED + trust persisted

        response = http.post(
            f"/registry/approve/{vid}", json={"approver": "api-governor"}
        )
        assert response.status_code == 200
        approval = response.json()
        assert approval["state"] == "APPROVED"
        assert approval["approver"] == "api-governor"
        assert pipe.registry.get_version(vid)["state"] == "APPROVED"

    def test_approval_refusal_surfaces_explanation(self, client):
        http, pipe = client
        result = _trained(pipe, model="refused")
        vid = result["version_id"]
        pipe.evaluate_version(vid)  # -> VERIFIED with clean trust state
        rec = pipe.registry.get_version(vid)
        # corrupt artifact AFTER verification: the gate must refuse
        path = pipe.artifacts._path_for(rec["artifact_digest"])
        original = path.read_bytes()
        path.write_bytes(b"broken" + original)
        try:
            response = http.post(
                f"/registry/approve/{vid}", json={"approver": "operator"}
            )
            assert response.status_code == 409
            detail = response.json()["detail"]
            assert "refused" in detail.lower()
        finally:
            path.write_bytes(original)

    def test_approval_requires_approver_identity(self, client):
        http, pipe = client
        result = _trained(pipe, model="noapprover")
        vid = result["version_id"]
        pipe.evaluate_version(vid)
        response = http.post(f"/registry/approve/{vid}", json={"approver": ""})
        assert response.status_code == 409
        assert "approver" in response.json()["detail"].lower()

    def test_revocation_via_api_is_audited(self, client):
        http, pipe = client
        result = _trained(pipe, model="revoke-me")
        vid = result["version_id"]
        response = http.post(
            f"/registry/revoke/{vid}",
            json={"reason": "supply chain alert", "actor": "secops"},
        )
        assert response.status_code == 200
        assert response.json()["state"] == "REVOKED"
        events = [
            e["record"] for e in pipe.ledger.iter_entries()
            if e["record"].get("type") == "state_transition"
        ]
        assert any(e.get("to") == "REVOKED" for e in events)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
