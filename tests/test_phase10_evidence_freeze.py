from __future__ import annotations

import json
from pathlib import Path

import pytest

from evaluation.research.artifacts import write_experiment_bundle
from evaluation.research.freeze import build_freeze, verify_bundle, verify_freeze
from evaluation.research.tables import BundleIntegrityError, export_tables, load_bundle

# The research paper and its evidence (paper/, research/) are kept locally and
# are not published in the repository. These checks run where they exist.
_REPO = __import__("pathlib").Path(__file__).resolve().parents[1]
needs_research_artifacts = pytest.mark.skipif(
    not ((_REPO / "paper").is_dir() and (_REPO / "research" / "evidence").is_dir()),
    reason="research paper and evidence are not in this checkout (kept locally, not published)",
)



def _bundle(root: Path, name: str) -> Path:
    return write_experiment_bundle(
        root,
        experiment_id=name,
        results={
            "status": "completed",
            "experiment": "trust-sat-controlled-mutation-v1",
            "mutations": [
                {
                    "mutation": "decision",
                    "target_object": "t",
                    "expected_verification_outcome": "tampered",
                    "verification_outcome": "tampered",
                    "failure_category": "x",
                    "verification_ms": 1.0,
                }
            ],
            "metrics": {"detected": 1},
        },
        config={"experiment": "trust-sat-controlled-mutation-v1", "seed": 1},
        dataset={"id": "fixture", "data_origin": "synthetic"},
        seed=1,
    )


def _freeze(tmp_path: Path) -> Path:
    source = _bundle(tmp_path / "runs", "EXP-TEST")
    build_freeze(
        [{"path": source, "role": "canonical", "note": "test"}],
        tmp_path / "freeze-v1",
        freeze_id="test-freeze",
        canonical_commit="deadbeef",
    )
    return tmp_path / "freeze-v1"


def test_valid_freeze_verifies_and_refuses_overwrite(tmp_path):
    freeze = _freeze(tmp_path)
    result = verify_freeze(freeze)
    assert result == {
        "freeze_id": "test-freeze",
        "intact": True,
        "checked": 1,
        "problems": {},
    }
    record = json.loads((freeze / "freeze.json").read_text())
    entry = record["bundles"][0]
    assert entry["role"] == "canonical" and entry["seed"] == 1
    assert entry["dataset"]["data_origin"] == "synthetic"
    with pytest.raises(FileExistsError):
        build_freeze([], freeze, freeze_id="again", canonical_commit="x")


@pytest.mark.parametrize(
    ("relative", "old", "new"),
    [
        ("manifest.json", '"seed":1', '"seed":2'),
        ("raw/results.json", '"verification_ms":1.0', '"verification_ms":0.5'),
        ("processed/metrics.json", '"detected":1', '"detected":0'),
        ("config.json", '"seed":1', '"seed":9'),
    ],
)
def test_any_modification_is_detected(tmp_path, relative, old, new):
    freeze = _freeze(tmp_path)
    bundle = freeze / "bundles" / "EXP-TEST"
    target = bundle / relative
    text = target.read_text(encoding="utf-8")
    assert old in text
    target.write_text(text.replace(old, new), encoding="utf-8")

    result = verify_freeze(freeze)
    assert result["intact"] is False
    assert result["problems"]["EXP-TEST"]

    record = json.loads((freeze / "freeze.json").read_text())
    expected = {b["bundle"]: b["manifest_sha256"] for b in record["bundles"]}
    with pytest.raises(BundleIntegrityError):
        load_bundle(bundle, expected_manifest_sha256=expected["EXP-TEST"])
    exported = export_tables([bundle], tmp_path / "tables", expected_manifests=expected)
    assert exported["sources"] == []
    assert exported["skipped"][0]["bundle"] == "EXP-TEST"


def test_freeze_refuses_a_bundle_that_already_fails_verification(tmp_path):
    source = _bundle(tmp_path / "runs", "EXP-BAD")
    (source / "summary.md").write_text("edited", encoding="utf-8")
    assert verify_bundle(source) == ["summary.md hash mismatch"]
    with pytest.raises(ValueError):
        build_freeze(
            [{"path": source, "role": "canonical"}],
            tmp_path / "freeze",
            freeze_id="x",
            canonical_commit="x",
        )
    assert not (tmp_path / "freeze").exists()


@needs_research_artifacts
def test_committed_freeze_v1_is_intact():
    """The paper's canonical evidence must verify byte-for-byte."""
    freeze = Path(__file__).resolve().parents[1] / "research" / "evidence" / "freeze-v1"
    result = verify_freeze(freeze)
    assert result["intact"] is True, result["problems"]
    record = json.loads((freeze / "freeze.json").read_text(encoding="utf-8"))
    canonical = {b["bundle"] for b in record["bundles"] if b["role"] == "canonical"}
    assert "EXP-X02-external-itsm" in canonical
    assert all(
        not b["code"]["source_tree_dirty"]
        for b in record["bundles"]
        if b["role"] == "canonical"
    )
