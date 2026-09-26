from __future__ import annotations

import csv
import json

import pytest

from evaluation.baselines.statistical import score
from evaluation.research.artifacts import write_experiment_bundle


def _result() -> dict:
    return {
        "benchmark_name": "controlled",
        "benchmark_version": "1.0",
        "environment": {"python": "3.test", "satsa_version": "test"},
        "metrics": {
            "scenario_corpus": {
                "micro": {"tp": 2, "fp": 1, "fn": 0, "precision": 0.6667},
                "coverage": {"executed": 2, "not_executed": 3},
            },
        },
        "provenance_note": "synthetic controlled data",
        "limitations": ["synthetic only"],
    }


def test_score_preserves_defined_zero_f1():
    metrics = score([True, False], [False, True])
    assert metrics["precision"] == 0.0
    assert metrics["recall"] == 0.0
    assert metrics["f1"] == 0.0


def test_write_bundle_emits_manifest_hashes_and_exports(tmp_path):
    bundle = write_experiment_bundle(
        tmp_path,
        experiment_id="pilot-001",
        results=_result(),
        config={"seed": 11, "population": 4},
        dataset={
            "id": "controlled-synthetic",
            "version": "1.0",
            "data_origin": "synthetic",
        },
        seed=11,
    )

    manifest = json.loads((bundle / "manifest.json").read_text())
    assert manifest["status"] == "completed"
    assert manifest["experiment_id"] == "pilot-001"
    assert manifest["dataset"]["data_origin"] == "synthetic"
    assert manifest["seed"] == 11
    assert manifest["configuration_sha256"]
    assert manifest["code"]["commit"]
    assert "source_tree_dirty" in manifest["code"]
    assert "pyproject.toml" in manifest["environment"]["dependency_definition_sha256"]
    assert manifest["artifacts_sha256"]["raw/results.json"]
    assert (bundle / "raw/results.json").exists()
    assert (bundle / "processed/metrics.json").exists()
    assert (bundle / "summary.md").exists()
    with (bundle / "processed/metrics.csv").open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert {row["metric"] for row in rows} >= {
        "scenario_corpus.micro.tp",
        "scenario_corpus.coverage.executed",
    }


def test_bundle_is_immutable_and_experiment_id_is_path_safe(tmp_path):
    kwargs = {
        "experiment_id": "same-id",
        "results": _result(),
        "config": {"seed": 1},
        "dataset": {"id": "test", "version": "1", "data_origin": "controlled"},
        "seed": 1,
    }
    write_experiment_bundle(tmp_path, **kwargs)
    with pytest.raises(FileExistsError):
        write_experiment_bundle(tmp_path, **kwargs)
    with pytest.raises(ValueError, match="experiment_id"):
        write_experiment_bundle(tmp_path, **{**kwargs, "experiment_id": "../escape"})


def test_failed_experiment_bundle_is_not_marked_completed(tmp_path):
    bundle = write_experiment_bundle(
        tmp_path,
        experiment_id="failed-001",
        results=None,
        config={"seed": 7},
        dataset={
            "id": "controlled-synthetic",
            "version": "1.0",
            "data_origin": "synthetic",
        },
        seed=7,
        status="failed",
        failure_reason="controlled failure",
    )
    manifest = json.loads((bundle / "manifest.json").read_text())
    assert manifest["status"] == "failed"
    assert manifest["failure_reason"] == "controlled failure"
    assert not (bundle / "processed/metrics.json").exists()
