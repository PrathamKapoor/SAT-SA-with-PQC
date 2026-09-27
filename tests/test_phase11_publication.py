from __future__ import annotations

import json
from pathlib import Path

import pytest

from evaluation.research.audit import audit_bundle
from evaluation.research.catalog import build_catalog
from evaluation.research.tables import load_bundle

ROOT = Path(__file__).resolve().parents[1]
FREEZE_V1 = ROOT / "research" / "evidence" / "freeze-v1"


def _canonical(freeze: Path) -> list[Path]:
    record = json.loads((freeze / "freeze.json").read_text(encoding="utf-8"))
    return [
        freeze / "bundles" / b["bundle"]
        for b in record["bundles"]
        if b["role"] == "canonical"
    ]


def test_statistical_audit_separates_trials_from_independent_units():
    rows = []
    for bundle in _canonical(FREEZE_V1):
        _, results = load_bundle(bundle)
        rows.extend(audit_bundle(bundle.name, results))
    experiments = {row["experiment"] for row in rows}
    assert "satsa-orchestration-overhead-v1" in experiments
    for row in rows:
        assert row["n"] >= 1 and row["independent_unit"], row
        assert "p_value" not in row
    overhead = [r for r in rows if r["experiment"] == "satsa-orchestration-overhead-v1"]
    assert all("one machine" in r["independent_unit"] for r in overhead)
    external = [r for r in rows if r["experiment"] == "satsa-external-itsm-v1"]
    assert all("one organisation" in r["independent_unit"] for r in external)


def _spec(tmp_path: Path, entries: list[dict]) -> Path:
    path = tmp_path / "spec.json"
    path.write_text(json.dumps({"entries": entries}), encoding="utf-8")
    return path


def test_catalog_reads_facts_from_freeze_and_requires_explicit_status(tmp_path):
    spec = _spec(
        tmp_path,
        [
            {
                "experiment_id": "EXP-T01",
                "bundle": "EXP-T01-trust-mutation-matrix",
                "research_question": "RQ5",
                "claim": "detected all 13 tested mutations",
                "baseline": "valid control",
                "metric": "detected / expected",
                "limitations": ["one workflow"],
            },
            {
                "experiment_id": "EXP-H01",
                "research_question": "human review",
                "claim": "not demonstrated",
                "status": "NOT EXECUTED",
            },
        ],
    )
    catalog = build_catalog(FREEZE_V1, spec)
    measured, planned = catalog["entries"]
    assert measured["status"] == "MEASURED"
    assert len(measured["manifest_hash"]) == 64
    assert measured["dataset_type"] == "controlled synthetic"
    assert planned["status"] == "NOT EXECUTED" and planned["manifest_hash"] is None

    with pytest.raises(ValueError):
        build_catalog(
            FREEZE_V1,
            _spec(tmp_path, [{"experiment_id": "X", "research_question": "q"}]),
        )
    with pytest.raises(ValueError):
        build_catalog(
            FREEZE_V1,
            _spec(
                tmp_path,
                [{"experiment_id": "R01", "bundle": "EXP-R01-evidence-robustness"}],
            ),
        )
