"""Phase P15 follow-up — expert-label layer validation is really wired.

``docs/roadmap-status.md`` disclosed P15 as PARTIAL because no
real ``ExpertLabel`` records were ever loaded anywhere: ``cmd_validate``
in ``satsa/cli.py`` called ``run_validation(svc)`` with no
``expert_labels`` argument, so the ``layers`` section of every
``sat-sa validate`` report was unconditionally empty — the
precision/recall machinery in ``satsa/analysis/validate.py`` had
zero test coverage with real labels.

This closes the *wiring* gap: ``sat-sa validate --expert-labels
<path>`` now loads real ``ExpertLabel`` records and computes real
per-layer precision/recall against findings emitted by an actual
run. It does not manufacture "expert" judgment — the labels used
here are constructed from findings a live demo run is already
known to emit (see ``docs/demo/expert-labels.sample.json``, which
is explicitly marked as an illustrative template, not certified
NCIIPC examiner review). Production expert-label volume remains a
disclosed limitation pending real human reviewers.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from satsa import cli as satsa_cli
from satsa.analysis.validate import (
    ExpertLabel,
    evaluate_layer,
    save_expert_labels,
    load_expert_labels,
)


# ---------------------------------------------------------------------------
# Pure unit coverage of the metric itself
# ---------------------------------------------------------------------------

def test_expert_label_roundtrip_through_json(tmp_path):
    labels = [
        ExpertLabel(layer="execution_gap", is_signal=True,
                    finding_category="execution_gap.fast_closure",
                    severity="high", expected_action="SATSA_INSPECT",
                    rationale="3 critical alerts closed <60s",
                    confidence=0.9, reviewer="sample-template"),
        ExpertLabel(layer="execution_gap", is_signal=False,
                    finding_category="execution_gap.metric_gaming",
                    rationale="no gaming pattern observed",
                    reviewer="sample-template"),
    ]
    path = tmp_path / "labels.json"
    save_expert_labels(labels, path)
    loaded = load_expert_labels(path)
    assert len(loaded) == 2
    assert loaded[0].signature() == labels[0].signature()
    # A positive and a negative label on the same finding_category
    # must be distinguishable.
    pos = ExpertLabel(layer="x", is_signal=True, finding_category="x.y",
                       rationale="r", reviewer="r")
    neg = ExpertLabel(layer="x", is_signal=False, finding_category="x.y",
                       rationale="r", reviewer="r")
    assert pos.signature() != neg.signature()


def test_evaluate_layer_is_not_vacuous():
    """precision/recall must reflect real set arithmetic, not
    trivially report 1.0/1.0 or 0/0 regardless of input. Also proves
    the YES/NO/UNLABELED fix (phase P22): an emitted family with no
    label at all (neither positive nor negative) must be excluded
    from the confusion matrix, not silently counted as a false
    positive — it lands in unlabeled_emitted instead."""
    emitted = [
        "execution_gap.fast_closure",
        "execution_gap.ack_without_investigation",
        "execution_gap.recurring_without_remediation",  # unlabeled -> excluded
    ]
    labels = [
        ExpertLabel(layer="execution_gap", is_signal=True,
                    finding_category="execution_gap.fast_closure",
                    reviewer="sample-template", rationale="r1"),
        ExpertLabel(layer="execution_gap", is_signal=True,
                    finding_category="execution_gap.ack_without_investigation",
                    reviewer="sample-template", rationale="r2"),
        ExpertLabel(layer="execution_gap", is_signal=True,
                    finding_category="execution_gap.metric_gaming",  # not emitted -> FN
                    reviewer="sample-template", rationale="r3"),
    ]
    metric = evaluate_layer("execution_gap", emitted, labels)
    assert metric.true_positives == 2
    assert metric.false_positives == 0
    assert metric.false_negatives == 1
    assert metric.unlabeled_emitted == 1
    assert metric.precision == pytest.approx(1.0)
    assert metric.recall == pytest.approx(2 / 3)
    assert metric.support == 3


def test_evaluate_layer_negative_label_on_emitted_family_is_a_real_fp():
    """The contrasting case: a family that IS negatively labeled
    (reviewer explicitly said this should NOT fire) and DID fire is
    a genuine, confirmed false positive — distinct from the unlabeled
    case above."""
    emitted = ["case_similarity.template_cluster"]
    labels = [ExpertLabel(
        layer="case_similarity", is_signal=False,
        finding_category="case_similarity.template_cluster",
        reviewer="sample-template", rationale="reviewer confirms not a signal")]
    metric = evaluate_layer("case_similarity", emitted, labels)
    assert metric.true_positives == 0
    assert metric.false_positives == 1
    assert metric.unlabeled_emitted == 0
    assert metric.precision == pytest.approx(0.0)


def test_evaluate_layer_true_negative_and_specificity():
    """A negatively-labeled family that correctly did NOT fire is a
    true negative, and specificity is computable from it."""
    emitted: list[str] = []
    labels = [ExpertLabel(
        layer="case_similarity", is_signal=False,
        finding_category="case_similarity.template_cluster",
        reviewer="sample-template", rationale="correctly quiet")]
    metric = evaluate_layer("case_similarity", emitted, labels)
    assert metric.true_negatives == 1
    assert metric.false_positives == 0
    assert metric.specificity == pytest.approx(1.0)


def test_evaluate_layer_undefined_metrics_are_none_not_fabricated_zero():
    """With no labels and no emissions at all, precision/recall/etc.
    must be None (undefined), never a fabricated 0.0."""
    metric = evaluate_layer("anomaly", [], [])
    assert metric.precision is None
    assert metric.recall is None
    assert metric.specificity is None
    assert metric.f1 is None
    assert metric.coverage is None


# ---------------------------------------------------------------------------
# End-to-end: real findings from a live demo run, real labels, real metrics
# ---------------------------------------------------------------------------

def _load_demo(db_path: Path, keys_dir: Path):
    from qsmlops.database.engine import SQLiteDatabaseEngine
    from qsmlops.database.migrations import MigrationRunner
    from satsa.service import SatsaService
    from satsa.ui.demo import load_demo_assessment
    eng = SQLiteDatabaseEngine(db_path)
    eng.connect()
    MigrationRunner(eng).migrate()
    svc = SatsaService(eng)
    load_demo_assessment(svc, keys_dir)
    return svc, eng


def test_run_validation_against_live_demo_findings(tmp_path):
    from satsa.analysis.validate import run_validation

    svc, eng = _load_demo(tmp_path / "satsa.db", tmp_path / "keys")
    emitted = sorted({
        r["rule_or_category"] for r in eng.query_all(
            "SELECT DISTINCT rule_or_category FROM satsa_findings"
            " WHERE state='signal'")
    })
    assert emitted, "demo run produced no findings — test fixture is stale"
    neg_space_emitted = [f for f in emitted if f.startswith("negative_space.")]
    assert len(neg_space_emitted) >= 2, neg_space_emitted

    # Label all-but-one of the actually-emitted negative_space findings
    # as expert-expected (-> those are TPs), plus one label for a
    # family we know this fixture does NOT emit (-> a real FN).
    held_out = neg_space_emitted[0]
    expected = neg_space_emitted[1:]
    labels = [
        ExpertLabel(layer="negative_space", is_signal=True,
                    finding_category=fam, reviewer="sample-template",
                    rationale="matches live demo finding")
        for fam in expected
    ]
    labels.append(ExpertLabel(
        layer="negative_space", is_signal=True,
        finding_category="negative_space.__not_emitted_by_this_fixture__",
        reviewer="sample-template", rationale="deliberately unmet expectation"))

    report = run_validation(svc, expert_labels=labels)
    layer_row = next(r for r in report["layers"] if r["layer"] == "negative_space")
    assert layer_row["true_positives"] == len(expected)
    assert layer_row["false_negatives"] == 1
    # held_out was emitted but never labeled at all (neither positive
    # nor negative) -> excluded from the confusion matrix entirely
    # (phase P22 fix), not counted as a false positive.
    assert layer_row["false_positives"] == 0
    assert layer_row["unlabeled_emitted"] == 1
    assert layer_row["precision"] == pytest.approx(1.0)
    assert 0.0 < layer_row["recall"] < 1.0


def test_cli_validate_wires_expert_labels_when_provided(tmp_path, capsys):
    db = tmp_path / "satsa.db"
    keys = tmp_path / "keys"
    rc = satsa_cli.main(["--db", str(db), "--trust-key-dir", str(keys), "demo"])
    assert rc == 0
    capsys.readouterr()  # discard demo output

    from qsmlops.database.engine import SQLiteDatabaseEngine
    eng = SQLiteDatabaseEngine(db); eng.connect()
    emitted = sorted({
        r["rule_or_category"] for r in eng.query_all(
            "SELECT DISTINCT rule_or_category FROM satsa_findings"
            " WHERE state='signal' AND rule_or_category LIKE 'execution_gap.%'")
    })
    assert emitted

    labels_path = tmp_path / "labels.json"
    save_expert_labels(
        [ExpertLabel(layer="execution_gap", is_signal=True,
                     finding_category=emitted[0], reviewer="sample-template",
                     rationale="live demo finding")],
        labels_path)

    rc = satsa_cli.main([
        "--db", str(db), "--trust-key-dir", str(keys),
        "validate", "--expert-labels", str(labels_path)])
    assert rc == 0
    out = capsys.readouterr().out
    combined = json.loads(out)
    assert combined["layers"], "expert labels were supplied but layers report is empty"
    eg_layer = next(r for r in combined["layers"] if r["layer"] == "execution_gap")
    assert eg_layer["true_positives"] >= 1


def test_cli_validate_without_expert_labels_stays_backward_compatible(tmp_path, capsys):
    """Omitting --expert-labels must reproduce the pre-existing
    behaviour exactly: an empty layers list, never a fabricated one."""
    db = tmp_path / "satsa.db"
    keys = tmp_path / "keys"
    satsa_cli.main(["--db", str(db), "--trust-key-dir", str(keys), "demo"])
    capsys.readouterr()

    rc = satsa_cli.main(["--db", str(db), "--trust-key-dir", str(keys), "validate"])
    assert rc == 0
    combined = json.loads(capsys.readouterr().out)
    assert combined["layers"] == []
