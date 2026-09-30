"""docs/API_CONTRACT.md must describe the live API exactly."""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "docs" / "API_CONTRACT.md"


@pytest.fixture(scope="module")
def openapi(tmp_path_factory):
    from qsmlops.database.engine import create_engine
    from qsmlops.evidence.ledger import EvidenceLedger
    from qsmlops.security.audit.service import AuditService
    from qsmlops.security.identity.service import IdentityService
    from satsa.api import create_app
    from satsa.api.settings import ApiSettings
    from satsa.submissions.storage import LocalArtifactStorage

    tmp = tmp_path_factory.mktemp("contract")
    engine = create_engine(f"sqlite:///{(tmp / 'api.db').as_posix()}")
    audit = AuditService(EvidenceLedger(tmp / "audit.jsonl"), database=engine)
    app = create_app(
        engine,
        storage=LocalArtifactStorage(tmp / "artifacts"),
        audit=audit,
        identity_service=IdentityService(engine, audit),
        settings=ApiSettings(secure_cookies=False),
        trust_key_dir=tmp / "keys",
    )
    return app.openapi()


def _live_routes(spec) -> set[tuple[str, str]]:
    return {
        (method.upper(), path)
        for path, operations in spec["paths"].items()
        for method in operations
    }


def _documented_routes() -> list[tuple[str, str]]:
    text = CONTRACT.read_text(encoding="utf-8")
    index = text.split("## 4. Route index", 1)[1].split("```text", 1)[1]
    block = index.split("```", 1)[0]
    return [
        (m.group(1), m.group(2))
        for m in re.finditer(
            r"^(GET|POST|PUT|PATCH|DELETE)\s+(\S+)$", block, re.MULTILINE
        )
    ]


def test_route_index_matches_live_application(openapi):
    documented = _documented_routes()
    assert len(documented) == len(set(documented)), "duplicate route in the index"
    assert set(documented) == _live_routes(openapi)
    assert len(documented) == 71
    assert "**71 routes**" in CONTRACT.read_text(encoding="utf-8")


def test_every_collection_route_is_paginated(openapi):
    for path, operations in openapi["paths"].items():
        for method, operation in operations.items():
            schema = (
                operation["responses"]
                .get("200", {})
                .get("content", {})
                .get("application/json", {})
                .get("schema", {})
            )
            if not schema.get("$ref", "").split("/")[-1].startswith("Page_"):
                continue
            names = {p["name"] for p in operation.get("parameters", [])}
            assert {"limit", "offset"} <= names, f"{method.upper()} {path}"


def test_idempotency_key_is_required_exactly_where_documented(openapi):
    required = {
        (method.upper(), path)
        for path, operations in openapi["paths"].items()
        for method, operation in operations.items()
        for p in operation.get("parameters", [])
        if p["name"] == "Idempotency-Key" and p.get("required")
    }
    assert required == {
        ("POST", "/api/v1/submissions"),
        ("POST", "/api/v1/submissions/{submission_id}/versions"),
        ("POST", "/api/v1/versions/{version_id}/artifacts"),
        ("POST", "/api/v1/runs"),
        # Phase 21: every route that queues an MLOps job.
        ("POST", "/api/v1/ml/datasets/{dataset_id}/validate"),
        ("POST", "/api/v1/ml/training-runs"),
        ("POST", "/api/v1/ml/drift-checks"),
        ("POST", "/api/v1/ml/retraining-requests/{request_id}/accept"),
    }


def test_documented_schemas_name_every_response_field(openapi):
    text = CONTRACT.read_text(encoding="utf-8")
    schemas = text.split("## 6. Schemas", 1)[1].split("## 7.", 1)[0]
    for name in [
        "Session",
        "Entity",
        "Run",
        "Finding",
        "Evidence",
        "CanonicalRecord",
        "EntityPriority",
        "Decision",
        "Receipt",
        "Verification",
    ]:
        properties = openapi["components"]["schemas"][name]["properties"]
        line = re.search(
            rf"^{name}\s+\{{(.*?)\}}\s*$", schemas, re.MULTILINE | re.DOTALL
        )
        assert line, name
        block = schemas[line.start() :].split("\n\n", 1)[0]
        block = (
            block.split("\n", 1)[0]
            + "\n"
            + "\n".join(row for row in block.split("\n")[1:] if row.startswith(" "))
        )
        for field in properties:
            assert re.search(rf"\b{field}\b", block), f"{name}.{field}"
