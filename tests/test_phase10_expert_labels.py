"""Expert-label workflow tests. All records here are test fixtures written
for this file; they are not expert labels and support no research claim."""

from __future__ import annotations

import json

import pytest

from evaluation.research.expert_labels import (
    ADJUDICATION_SCHEMA,
    LABEL_SCHEMA,
    adjudicate,
    cohen_kappa,
    load_labels,
    validate_label,
)


def _label(annotator, target, label, **extra):
    record = {
        "schema": LABEL_SCHEMA,
        "label_source": "unit-test-fixture",
        "annotator_id": annotator,
        "labelled_at": "2026-10-01T10:00:00Z",
        "target_type": "finding",
        "target_id": target,
        "label": label,
        "confidence": 0.7,
        "case_set_digest": "a" * 64,
    }
    record.update(extra)
    return record


def test_validation_refuses_templates_and_identifying_annotators():
    assert validate_label(_label("ann-1", "f1", "true_issue")) == []
    assert validate_label(
        _label("ann-1", "f1", "true_issue", label_source="sample-template")
    )
    assert validate_label(_label("jane.doe@example.org", "f1", "true_issue"))
    assert validate_label(_label("Jane Doe", "f1", "true_issue"))
    assert validate_label(_label("ann-1", "f1", "maybe"))
    assert validate_label(_label("ann-1", "f1", "true_issue", labelled_at="2026-10-01"))
    assert validate_label(_label("ann-1", "f1", "true_issue", confidence=1.5))


def test_load_adjudicate_and_agreement(tmp_path):
    rows = [
        _label("ann-1", "f1", "true_issue"),
        _label("ann-2", "f1", "true_issue"),
        _label("ann-1", "f2", "not_issue"),
        _label("ann-2", "f2", "true_issue"),
        _label("ann-1", "f3", "not_issue"),
        _label("ann-2", "f3", "insufficient_evidence"),
        _label("ann-1", "f1", "not_issue"),  # duplicate annotation
        {
            "schema": ADJUDICATION_SCHEMA,
            "target_type": "finding",
            "target_id": "f2",
            "label": "not_issue",
            "adjudicator_id": "adj-1",
            "adjudicated_at": "2026-10-02T09:00:00Z",
        },
    ]
    path = tmp_path / "labels.jsonl"
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n{bad json\n")
    accepted, rejected = load_labels(path)
    assert len(accepted) == 7
    assert {r["line"] for r in rejected} == {7, 9}

    result = adjudicate(accepted)
    consensus = result["consensus"]
    assert consensus["finding:f1"] == {
        "label": "true_issue",
        "method": "majority",
        "annotations": 2,
        "label_counts": {"true_issue": 2},
    }
    assert consensus["finding:f2"]["method"] == "adjudicated"
    assert consensus["finding:f2"]["label"] == "not_issue"
    assert consensus["finding:f3"]["method"] == "unresolved"
    assert consensus["finding:f3"]["label"] is None
    pair = result["pairwise_agreement"]["ann-1|ann-2"]
    assert pair["shared_targets"] == 3
    assert pair["percent_agreement"] == pytest.approx(1 / 3)


def test_cohen_kappa_bounds():
    assert cohen_kappa(["true_issue", "not_issue"], ["true_issue", "not_issue"]) == 1.0
    assert cohen_kappa([], []) is None
