"""Hostile evidence uploads: every one is refused or reported, never a 500.

Upload-time checks refuse what cannot be a dataset (name, type, size, binary,
empty). Content that is a dataset but a bad one is accepted as an artifact and
then reported by validation as invalid, with the version left in a terminal,
explainable state.
"""

import io

import pytest
from test_phase6_api import headers

pytest_plugins = ["test_tenant_schema", "test_phase6_api"]

HEADER = b"native_id,created_at,severity\n"


@pytest.fixture
def version(api):
    c = api["client"]
    h = headers(api)
    entity = c.post("/api/v1/entities", headers=h, json={"display_name": "Upload"}).json()
    assessment = c.post(
        "/api/v1/assessments",
        headers=h,
        json={"entity_id": entity["id"], "period_start": 1700000000, "period_end": 1800000000},
    ).json()
    submission = c.post(
        "/api/v1/submissions",
        headers=headers(api, key="s"),
        json={"assessment_id": assessment["id"]},
    ).json()
    counter = iter(range(1000))

    def fresh():
        return c.post(
            f"/api/v1/submissions/{submission['id']}/versions",
            headers=headers(api, key=f"v{next(counter)}"),
        ).json()["id"]

    return fresh


def upload(api, version_id, name, content, mime="text/csv", category="alerts", key=None):
    return api["client"].post(
        f"/api/v1/versions/{version_id}/artifacts?category={category}",
        headers=headers(api, key=key or f"{category}-{name}"[:100]),
        files={"file": (name, io.BytesIO(content), mime)},
    )


@pytest.mark.parametrize(
    "name,content,mime",
    [
        ("empty.csv", b"", "text/csv"),
        ("../alerts.csv", HEADER, "text/csv"),
        ("..\\alerts.csv", HEADER, "text/csv"),
        ("dir/alerts.csv", HEADER, "text/csv"),
        ("..", HEADER, "text/csv"),
        ("nul\x00.csv", HEADER, "text/csv"),
        ("tab\t.csv", HEADER, "text/csv"),
        ("a" * 252 + ".csv", HEADER, "text/csv"),
        ("alerts.csv", HEADER, "application/json"),
        ("alerts.csv", HEADER, "text/html"),
        ("alerts.exe", HEADER, "application/octet-stream"),
        ("alerts.csv.exe", HEADER, "text/csv"),
        ("alerts", HEADER, "text/csv"),
        ("alerts.json", b"native_id\nA1\n", "application/json"),
        ("alerts.jsonl", b"[1,2]\n", "application/x-ndjson"),
        ("alerts.csv", b"\x89PNG\r\n\x1a\n\x00\x00", "text/csv"),
        ("alerts.csv", b"\xff\xfen\x00a\x00t\x00", "text/csv"),  # UTF-16 LE
    ],
    ids=["empty", "dotdot-slash", "dotdot-backslash", "subdir", "dotdot", "nul-name",
         "control-name", "long-name", "mime-json", "mime-html", "exe", "double-ext",
         "no-ext", "json-not-json", "jsonl-not-object", "png", "utf16"],
)
def test_undeliverable_uploads_are_refused(api, version, name, content, mime):
    v = version()
    response = upload(api, v, name, content, mime)
    assert response.status_code in {400, 409, 413, 422}, response.text
    assert response.json()["error"]["code"] != "INTERNAL_ERROR"
    assert api["db"].query_one(
        "SELECT COUNT(*) AS n FROM satsa_artifacts WHERE submission_version_id=?", (v,)
    )["n"] == 0


def test_upload_size_limit_is_enforced_by_the_service_and_the_edge(api, version):
    from satsa.submissions.service import MAX_ARTIFACT_BYTES

    v = version()
    big = HEADER + b"A1,1735689700,critical\n" * (MAX_ARTIFACT_BYTES // 23 + 10)
    assert len(big) > MAX_ARTIFACT_BYTES
    response = upload(api, v, "alerts.csv", big)
    assert response.status_code in {413, 422}, response.text
    # Beyond the edge limit the body is refused before multipart parsing.
    huge = big + b"x" * (2 * 1024 * 1024)
    response = upload(api, v, "alerts.csv", huge, key="huge")
    assert response.status_code == 413, response.text
    assert response.json()["error"]["code"] == "REQUEST_TOO_LARGE"


def test_unknown_category_and_malformed_parameters(api, version):
    v = version()
    assert upload(api, v, "alerts.csv", HEADER, category="secrets").status_code == 422
    assert upload(api, v, "alerts.csv", HEADER, category="../alerts").status_code == 422
    c = api["client"]
    no_file = c.post(
        f"/api/v1/versions/{v}/artifacts?category=alerts", headers=headers(api, key="nf")
    )
    assert no_file.status_code == 422
    for key in ["", " ", "k" * 129, "bad key"]:
        response = c.post(
            f"/api/v1/versions/{v}/artifacts?category=alerts",
            headers={**headers(api), "Idempotency-Key": key},
            files={"file": ("alerts.csv", io.BytesIO(HEADER), "text/csv")},
        )
        assert response.status_code == 422, (key, response.text)


def complete_and_validate(api, v):
    c = api["client"]
    h = headers(api)
    assert c.post(f"/api/v1/versions/{v}/complete", headers=h).status_code == 200
    report = c.post(f"/api/v1/versions/{v}/validate", headers=h)
    assert report.status_code == 200, report.text
    return report.json()


@pytest.mark.parametrize(
    "name,content,mime",
    [
        ("alerts.csv", HEADER, "text/csv"),  # header only
        ("alerts.csv", b'native_id,created_at,severity\n"A1,1735689700,critical\n', "text/csv"),
        ("alerts.csv", b"native_id,created_at\nA1\n", "text/csv"),
        ("alerts.csv", HEADER + b"A1,1735689700," + b"x" * 200_000 + b"\n", "text/csv"),
        ("alerts.csv", HEADER + b"A1,1735689700,critical\n" * 2, "text/csv"),
        ("alerts.csv", HEADER + b"A1,not-a-time,critical\n", "text/csv"),
        ("alerts.csv", b"native_id,created_at,severity\nA1,1735689700,\xe9\xe8\n", "text/csv"),
        ("alerts.json", b'{"native_id": "A1", ', "application/json"),
        ("alerts.json", b"[" + b"[" * 5000 + b"]" * 5000 + b"]", "application/json"),
        ("alerts.jsonl", b'{"native_id": "A1"}\nnot json\n', "application/x-ndjson"),
        ("alerts.jsonl", b'{"native_id": "A1"}\n[1]\n', "application/x-ndjson"),
    ],
    ids=["header-only", "unbalanced-quote", "short-row", "huge-field", "duplicate-row",
         "bad-time", "latin1", "truncated-json", "deep-json", "jsonl-garbage", "jsonl-array"],
)
def test_bad_datasets_are_reported_invalid_not_crashed(api, version, name, content, mime):
    v = version()
    response = upload(api, v, name, content, mime)
    assert response.status_code == 201, response.text
    report = complete_and_validate(api, v)
    assert report["status"] in {"invalid", "failed"}, report
    assert report["errors"], report
    state = api["client"].get(f"/api/v1/versions/{v}", headers=headers(api)).json()
    assert state["status"] in {"invalid", "failed"}, state
    # Repeating validation returns the recorded report instead of re-running.
    again = api["client"].post(f"/api/v1/versions/{v}/validate", headers=headers(api))
    assert again.json()["status"] == report["status"]


def test_valid_bom_prefixed_dataset_and_repeated_lifecycle_calls(api, version):
    c = api["client"]
    h = headers(api)
    v = version()
    content = b"\xef\xbb\xbf" + HEADER + b"A1,1735689700,critical\n"
    first = upload(api, v, "alerts.csv", content, key="same")
    assert first.status_code == 201, first.text
    # Idempotent replay returns the same artifact; a different body is a conflict.
    assert upload(api, v, "alerts.csv", content, key="same").json()["id"] == first.json()["id"]
    assert upload(api, v, "alerts.csv", content + b"A2,1735689701,low\n", key="same").status_code in {409, 422}
    # A second artifact for the same category is refused.
    assert upload(api, v, "alerts.csv", content, key="other").status_code == 409
    report = complete_and_validate(api, v)
    assert report["status"] == "valid", report
    for _ in range(2):
        assert c.post(f"/api/v1/versions/{v}/complete", headers=h).status_code == 200
        assert c.post(f"/api/v1/versions/{v}/validate", headers=h).json()["status"] == "valid"
    # The version is immutable once complete.
    late = upload(api, v, "cases.csv", b"native_id\nC1\n", category="cases", key="late")
    assert late.status_code == 409, late.text


def test_validation_before_completion_is_refused(api, version):
    v = version()
    assert upload(api, v, "alerts.csv", HEADER + b"A1,1735689700,critical\n").status_code == 201
    early = api["client"].post(f"/api/v1/versions/{v}/validate", headers=headers(api))
    assert early.status_code in {409, 422}, early.text
    assert api["client"].get(f"/api/v1/versions/{v}", headers=headers(api)).json()["status"] == "uploading"


def test_interrupted_validation_does_not_strand_the_version(api, version, monkeypatch):
    from satsa.submissions.service import SubmissionService

    c = api["client"]
    h = headers(api)
    v = version()
    assert upload(api, v, "alerts.csv", HEADER + b"A1,1735689700,critical\n").status_code == 201
    assert c.post(f"/api/v1/versions/{v}/complete", headers=h).status_code == 200

    def crash(*_args, **_kwargs):
        raise RuntimeError("worker process lost mid-validation")

    monkeypatch.setattr(SubmissionService, "_normalize", crash)
    failed = c.post(f"/api/v1/versions/{v}/validate", headers=h)
    assert failed.status_code == 500
    assert "mid-validation" not in failed.text
    assert c.get(f"/api/v1/versions/{v}", headers=h).json()["status"] == "uploaded"
    monkeypatch.undo()
    retry = c.post(f"/api/v1/versions/{v}/validate", headers=h)
    assert retry.status_code == 200, retry.text
    assert retry.json()["status"] == "valid"
