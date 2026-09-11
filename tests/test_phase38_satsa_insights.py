"""Phase 38 — cross-entity insights tests."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from qsmlops.crypto.hashing import digest_document
from qsmlops.database.engine import SQLiteDatabaseEngine
from qsmlops.database.migrations import MigrationRunner
from satsa.analysis.insights import (
    CrossInsight, all_insights, common_execution_gap,
    common_negative_space, sector_deviation,
)


def test_to_dict_is_serializable():
    i = CrossInsight(title="t", description="d", affected_entities=["e1"],
                     statistical_basis={"k": 1}, confidence="medium",
                     limitations="l")
    json.dumps(i.to_dict())


def test_common_execution_gap_empty_db():
    td = Path(tempfile.mkdtemp())
    try:
        eng = SQLiteDatabaseEngine(td / "x.db"); eng.connect()
        MigrationRunner(eng).migrate()
        assert common_execution_gap(eng) is None
        eng.close()
    finally:
        import shutil; shutil.rmtree(td, ignore_errors=True)


def test_all_insights_empty_db():
    td = Path(tempfile.mkdtemp())
    try:
        eng = SQLiteDatabaseEngine(td / "x.db"); eng.connect()
        MigrationRunner(eng).migrate()
        assert all_insights(eng) == []
        eng.close()
    finally:
        import shutil; shutil.rmtree(td, ignore_errors=True)
