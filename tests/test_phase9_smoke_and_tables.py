from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from evaluation.research.artifacts import write_experiment_bundle
from evaluation.research.tables import BundleIntegrityError, export_tables, load_bundle

_ROOT = Path(__file__).resolve().parents[1]


def _smoke_module():
    spec = importlib.util.spec_from_file_location(
        "deployment_smoke", _ROOT / "scripts" / "deployment_smoke.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_smoke_checks_never_report_pass_for_unexecuted_steps():
    smoke = _smoke_module()
    checks = smoke.Checks()
    checks.run("first", lambda: {"run_id": "run_1"})

    def broken():
        raise smoke.SmokeFailure("readiness reported degraded")

    checks.run("second", broken)
    called = []
    checks.run("third", lambda: called.append(True))
    report = checks.report()

    assert called == []
    assert [row["status"] for row in report["checks"]] == ["PASS", "FAIL", "NOT_RUN"]
    assert report["checks"][0]["run_id"] == "run_1"
    assert "degraded" in report["checks"][1]["failure_reason"]
    assert report["checks"][2]["duration_seconds"] is None
    assert report["status"] == "failed"
    assert report["counts"] == {"PASS": 1, "FAIL": 1, "NOT_RUN": 1}


def test_smoke_requires_credentials_or_provisioning(monkeypatch):
    smoke = _smoke_module()
    for name in (
        "SATSA_SMOKE_ANALYST_CREDENTIAL",
        "SATSA_SMOKE_SUPERVISOR_CREDENTIAL",
        "SATSA_SMOKE_AUDITOR_CREDENTIAL",
        "SATSA_SMOKE_ORGANIZATION_ID",
        "SATSA_SMOKE_ADMIN_CREDENTIAL",
    ):
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(smoke.SmokeFailure):
        smoke.main([])
    with pytest.raises(smoke.SmokeFailure):
        smoke.main(["--provision"])


def _integrity_bundle(root: Path, experiment_id: str) -> Path:
    results = {
        "status": "completed",
        "experiment": "trust-sat-controlled-mutation-v1",
        "mutations": [
            {
                "mutation": "decision",
                "target_object": "satsa_run_review_decisions.action",
                "expected_verification_outcome": "tampered",
                "verification_outcome": "tampered",
                "failure_category": "decision digest mismatch",
                "verification_ms": 1.5,
            }
        ],
        "metrics": {},
    }
    return write_experiment_bundle(
        root,
        experiment_id=experiment_id,
        results=results,
        config={"experiment": "trust-sat-controlled-mutation-v1"},
        dataset={"id": "test", "data_origin": "synthetic"},
        seed=None,
    )


def test_tables_are_generated_from_verified_bundles_only(tmp_path):
    good = _integrity_bundle(tmp_path / "bundles", "good")
    tampered = _integrity_bundle(tmp_path / "bundles", "tampered")
    results = tampered / "raw" / "results.json"
    results.write_text(results.read_text().replace("1.5", "0.1"))
    with pytest.raises(BundleIntegrityError):
        load_bundle(tampered)

    record = export_tables([good, tampered], tmp_path / "tables")
    assert [s["bundle"] for s in record["sources"]] == ["good"]
    assert record["skipped"][0]["bundle"] == "tampered"
    csv_text = (tmp_path / "tables" / "integrity_mutations.csv").read_text()
    assert "satsa_run_review_decisions.action" in csv_text
    tex = (tmp_path / "tables" / "integrity_mutations.tex").read_text()
    assert r"satsa\_run\_review\_decisions.action" in tex
    manifest = json.loads((tmp_path / "tables" / "tables-manifest.json").read_text())
    assert "integrity_mutations.md" in manifest["tables"]


def test_tables_keep_both_bundles_of_one_experiment(tmp_path):
    first = _integrity_bundle(tmp_path / "bundles", "run-a")
    second = _integrity_bundle(tmp_path / "bundles", "run-b")
    export_tables([first, second], tmp_path / "tables")
    assert (tmp_path / "tables" / "integrity_mutations.csv").exists()
    assert (tmp_path / "tables" / "integrity_mutations__run-b.csv").exists()
