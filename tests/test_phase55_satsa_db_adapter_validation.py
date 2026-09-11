"""Phase P12 — DB ingestion adapter + expert validation + benchmark."""
from __future__ import annotations

import json
import sqlite3
import tempfile
from pathlib import Path

import pytest

from satsa.ingest.db_adapter import read_sqlite_table, read_sqlite_categories
from satsa.ingest.readers import IngestionFormatError
from satsa.analysis.validate import (
    ExpertLabel, GroundTruthCase, evaluate_layer,
    composition_validation, synthetic_ground_truth,
    run_validation, save_expert_labels, load_expert_labels,
)
from satsa.analysis.benchmark import print_benchmark


def _make_source_db(path: Path) -> None:
    conn = sqlite3.connect(str(path))
    try:
        conn.execute("CREATE TABLE alerts ("
                     "id TEXT, native_id TEXT, created_at REAL,"
                     " mapped_severity TEXT)")
        conn.execute("INSERT INTO alerts VALUES (?,?,?,?)",
                     ("A1", "al-1", 1735689600.0, "critical"))
        conn.execute("INSERT INTO alerts VALUES (?,?,?,?)",
                     ("A2", "al-2", 1735689700.0, "high"))
        conn.commit()
    finally:
        conn.close()


def test_db_adapter_reads_table_into_parsed_file(tmp_path):
    src = tmp_path / "source.db"
    _make_source_db(src)
    pf = read_sqlite_table(src, "alerts")
    assert pf.category == "alerts"
    assert pf.format == "sqlite"
    assert pf.file_digest  # non-empty
    assert len(pf.rows) == 2
    assert pf.rows[0].data["native_id"] == "al-1"
    assert pf.rows[0].source_fmt == "sqlite"
    assert pf.rows[0].original_digest


def test_db_adapter_reads_categories(tmp_path):
    src = tmp_path / "source.db"
    _make_source_db(src)
    out = read_sqlite_categories(src, {"alerts": "alerts"})
    assert "alerts" in out
    assert out["alerts"].format == "sqlite"


def test_db_adapter_missing_table_raises(tmp_path):
    src = tmp_path / "source.db"
    _make_source_db(src)
    with pytest.raises(IngestionFormatError):
        read_sqlite_table(src, "doesnotexist")


def test_db_adapter_missing_db_raises(tmp_path):
    with pytest.raises(IngestionFormatError):
        read_sqlite_table(tmp_path / "absent.db", "alerts")


def test_synthetic_ground_truth_has_10_scenarios():
    cases = synthetic_ground_truth()
    scenarios = {c.scenario for c in cases}
    assert scenarios >= {
        "healthy", "execution-gap", "negative-space", "anomaly",
        "peer-deviation", "mixed", "borderline", "noisy",
        "missing-evidence", "conflicting-evidence",
    }


def test_evaluate_layer_precision_recall():
    # A single family labeled BOTH ways (a positive and a negative
    # ExpertLabel for the same layer/family) is a reviewer-
    # disagreement / conflicting case as of phase P22's YES/NO/
    # UNLABELED fix — it is no longer silently resolved by ignoring
    # the negative label (that was the exact bug P22 closed; see
    # tests/test_phase62_satsa_expert_validation.py for the full
    # semantics). It now counts toward both true_positives (the YES
    # side) and false_positives (the NO side, since it was emitted),
    # which is the honest representation of "the labels disagree,"
    # not a fabricated clean 1.0/1.0.
    expert = [
        ExpertLabel(layer="execution_gap.fast_closure", is_signal=True),
        ExpertLabel(layer="execution_gap.fast_closure", is_signal=False),
    ]
    m = evaluate_layer(
        "execution_gap.fast_closure",
        emitted_families=["execution_gap.fast_closure"],
        expert_labels=expert,
    )
    assert m.true_positives == 1
    assert m.false_positives == 1
    assert m.false_negatives == 0
    assert m.precision == pytest.approx(0.5)
    assert m.recall == pytest.approx(1.0)


def test_composition_validation_matches_expected():
    case = GroundTruthCase(
        case_id="c1", scenario="execution-gap",
        expected_signals=["execution_gap.fast_closure"],
        expected_action="SATSA_INSPECT",
    )
    res = composition_validation(
        case, ["execution_gap.fast_closure"], "SATSA_INSPECT")
    assert res["signals_ok"] is True
    assert res["action_ok"] is True


def test_expert_label_round_trip(tmp_path):
    labels = [ExpertLabel(layer="x.y", is_signal=True, severity="high",
                          reviewer="alice", rationale="because")]
    p = tmp_path / "labels.json"
    save_expert_labels(labels, p)
    loaded = load_expert_labels(p)
    assert len(loaded) == 1
    assert loaded[0].reviewer == "alice"


def test_run_validation_returns_structure(tmp_path):
    """Smoke: run_validation returns a dict with layers + composition
    + summary. Without persisted runs / labels, layers is empty
    but composition covers all 10 synthetic scenarios."""
    from qsmlops.database.engine import SQLiteDatabaseEngine
    from qsmlops.database.migrations import MigrationRunner
    db = tmp_path / "x.db"
    eng = SQLiteDatabaseEngine(db); eng.connect()
    MigrationRunner(eng).migrate()
    from satsa.service import SatsaService
    svc = SatsaService(eng)
    rep = run_validation(svc)
    assert "layers" in rep
    assert "composition" in rep
    assert rep["summary"]["cases"] == 10


def test_print_benchmark_handles_missing_file(capsys, tmp_path):
    print_benchmark(tmp_path / "missing.csv")
    out = capsys.readouterr().out
    assert "not found" in out.lower()


def test_print_benchmark_reads_csv(capsys, tmp_path):
    csv = tmp_path / "b.csv"
    csv.write_text(
        "cse_count,run_count,finding_count,elapsed_seconds\n"
        "5,5,12,1.2\n"
        "10,10,25,2.8\n",
        encoding="utf-8")
    print_benchmark(csv)
    out = capsys.readouterr().out
    assert "5" in out
    assert "10" in out