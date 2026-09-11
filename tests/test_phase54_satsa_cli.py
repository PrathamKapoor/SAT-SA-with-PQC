"""Phase P11 — CLI smoke tests.

The CLI must call the same service layer as the UI; it must not
duplicate business logic. These tests verify the CLI handlers
are wired and that ``sat-sa agents`` exposes the 26-agent
registry.
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from satsa import cli as satsa_cli
from satsa.supervisor import list_agents


def test_agents_command_prints_26_agents(capsys):
    rc = satsa_cli.main(["--db", ":memory:", "agents"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "26 agents" in out
    # Both families are listed
    assert "[MLOPS]" in out
    assert "[SATSA]" in out
    # The 17 SAT-SA agents all appear by id
    for a in list_agents(family="satsa"):
        assert a.agent_id in out


def test_ingest_analyze_risk_workflow(tmp_path):
    """End-to-end: ingest a CSE submission, analyze it, compute risk."""
    # Build a minimal CSE submission directory
    sub = tmp_path / "CSE-X"
    sub.mkdir()
    (sub / "alerts.csv").write_text(
        "native_id,created_at,mapped_severity\n"
        "A1,1735689600.0,critical\n",
        encoding="utf-8")
    (sub / "assets.csv").write_text(
        "native_id,criticality\nAS1,critical\n", encoding="utf-8")

    db = tmp_path / "satsa.db"
    keys = tmp_path / "keys"

    rc = satsa_cli.main([
        "--db", str(db), "--trust-key-dir", str(keys),
        "ingest", "CSE-X", str(sub),
        "--period-start", "1735689600.0",
        "--period-end", "1738281600.0",
    ])
    assert rc == 0

    # Find the assessment id the ingest created
    from qsmlops.database.engine import SQLiteDatabaseEngine
    eng = SQLiteDatabaseEngine(db); eng.connect()
    eid = eng.query_one("SELECT id FROM satsa_entities LIMIT 1")["id"]
    aid = eng.query_one(
        "SELECT id FROM satsa_assessments WHERE entity_id=?",
        (eid,))["id"]

    rc = satsa_cli.main([
        "--db", str(db), "--trust-key-dir", str(keys),
        "analyze", eid, aid])
    assert rc == 0

    # Find the run id
    rid = eng.query_one(
        "SELECT id FROM satsa_runs WHERE entity_id=?",
        (eid,))["id"]

    rc = satsa_cli.main([
        "--db", str(db), "--trust-key-dir", str(keys),
        "decision", rid, "--vocabulary", "satsa"])
    assert rc == 0