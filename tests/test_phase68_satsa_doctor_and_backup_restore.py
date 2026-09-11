"""Phase P24 — `sat-sa doctor` and a tested backup/restore procedure.

Two mandatory operator-facing gaps closed here:

1. There was no diagnostic command at all — an operator on a fresh
   machine had to read source code to know if their install was
   healthy. `sat-sa doctor` actually exercises each thing it checks
   (a real ML-DSA sign+verify roundtrip, a real DB connect+migrate,
   a real write-permission probe) rather than just checking imports.
2. "Backup/restore" was documented nowhere and tested nowhere. This
   proves the actual procedure: copy the SQLite DB file + trust-key
   directory, destroy the originals, restore from the copies, and
   confirm TRUST-SAT still verifies the exact same run/findings —
   not just that files exist post-restore.
"""
from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import pytest


def test_doctor_passes_on_a_fresh_valid_install(tmp_path):
    from satsa import cli as satsa_cli
    import io
    import contextlib

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = satsa_cli.main([
            "--db", str(tmp_path / "x.db"),
            "--trust-key-dir", str(tmp_path / "keys"),
            "doctor"])
    out = buf.getvalue()
    assert rc == 0
    assert "[FAIL]" not in out
    assert "[PASS] pqc-provider" in out
    assert "[PASS] database" in out
    assert "0 failed" in out


def test_doctor_fails_closed_when_db_path_is_unusable(tmp_path):
    """Point --db at a path that cannot be a SQLite file (it's a
    directory) — doctor must report FAIL and a non-zero exit code,
    not silently pass."""
    from satsa import cli as satsa_cli
    import io
    import contextlib

    bogus_db = tmp_path / "this-is-a-directory"
    bogus_db.mkdir()
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = satsa_cli.main([
            "--db", str(bogus_db),
            "--trust-key-dir", str(tmp_path / "keys"),
            "doctor"])
    out = buf.getvalue()
    assert rc != 0
    assert "[FAIL] database" in out


def test_doctor_warns_rather_than_fails_with_no_trust_key_dir(tmp_path):
    from satsa import cli as satsa_cli
    import io
    import contextlib

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = satsa_cli.main(["--db", str(tmp_path / "x.db"), "doctor"])
    out = buf.getvalue()
    assert rc == 0
    assert "[WARN] trust-key-dir" in out


# ---------------------------------------------------------------------------
# Backup / restore: proven, not just documented
# ---------------------------------------------------------------------------

def _seeded_environment(root: Path):
    from qsmlops.database.engine import SQLiteDatabaseEngine
    from qsmlops.database.migrations import MigrationRunner
    from satsa.service import SatsaService
    from satsa.analysis.synth import GenConfig, generate

    db_path = root / "satsa.db"
    keys_dir = root / "keys"
    eng = SQLiteDatabaseEngine(db_path)
    eng.connect()
    MigrationRunner(eng).migrate()
    svc = SatsaService(eng)
    cfg = GenConfig(seed=4242, num_cse=1, num_alerts=20, num_cases=5)
    paths = generate(cfg, root / "gen")
    entity = svc.register_entity("CSE-BACKUP", sector="defence")
    assessment = svc.open_assessment(entity.id, 1735689600.0, 1738281600.0)
    svc.submit(assessment.id, paths[0])
    svc.run_analysis(entity.id, assessment.id, trust_key_dir=keys_dir)
    risk = svc.compute_risk(entity.id)
    eng.close()
    return db_path, keys_dir, entity.id, risk.run_id


def test_backup_restore_preserves_full_trust_chain(tmp_path):
    working = tmp_path / "working"
    working.mkdir()
    backup = tmp_path / "backup"

    db_path, keys_dir, entity_id, run_id = _seeded_environment(working)

    # Verify BEFORE backup, as a baseline.
    from qsmlops.database.engine import SQLiteDatabaseEngine
    from satsa.service import SatsaService
    eng = SQLiteDatabaseEngine(db_path); eng.connect()
    svc = SatsaService(eng)
    report_before = svc.verify_run(run_id, keys_dir)
    assert report_before["run"]["ok"] is True
    assert all(f["ok"] for f in report_before["findings"])
    eng.close()

    # --- Backup: copy the DB file + the entire trust-key directory ---
    backup.mkdir()
    shutil.copy2(db_path, backup / db_path.name)
    shutil.copytree(keys_dir, backup / "keys")

    # --- Destroy the working copy entirely ---
    db_path.unlink()
    shutil.rmtree(keys_dir)
    assert not db_path.exists()
    assert not keys_dir.exists()

    # --- Restore from the backup ---
    restored_db = working / db_path.name
    restored_keys = working / "keys"
    shutil.copy2(backup / db_path.name, restored_db)
    shutil.copytree(backup / "keys", restored_keys)

    # --- Re-verify: the exact same run/findings must still verify,
    # and the underlying data must be intact (not just present). ---
    eng2 = SQLiteDatabaseEngine(restored_db); eng2.connect()
    svc2 = SatsaService(eng2)
    report_after = svc2.verify_run(run_id, restored_keys)
    assert report_after["run"]["ok"] is True, report_after["run"]
    assert len(report_after["findings"]) == len(report_before["findings"])
    assert all(f["ok"] for f in report_after["findings"])

    risk_after = svc2.compute_risk(entity_id)
    assert risk_after.run_id == run_id
    eng2.close()


def test_restore_from_a_stale_backup_does_not_silently_pass_as_current(tmp_path):
    """A backup taken BEFORE a later tamper must not be mistaken for
    a clean restore of the CURRENT (tampered) state — this just
    confirms backup/restore is a real file operation, not a no-op
    that always reports success regardless of which bytes moved."""
    working = tmp_path / "working"
    working.mkdir()
    db_path, keys_dir, entity_id, run_id = _seeded_environment(working)

    backup = tmp_path / "backup"
    backup.mkdir()
    shutil.copy2(db_path, backup / db_path.name)
    shutil.copytree(keys_dir, backup / "keys")

    # Tamper the WORKING copy (not the backup) after the backup was taken.
    from qsmlops.database.engine import SQLiteDatabaseEngine
    eng = SQLiteDatabaseEngine(db_path); eng.connect()
    eng.execute(
        "UPDATE satsa_findings SET rationale=? WHERE id="
        "(SELECT id FROM satsa_findings LIMIT 1)", ("TAMPERED",))
    eng.close()

    # The backup, restored fresh, must NOT contain the tamper — proving
    # the backup captured a real, independent snapshot rather than a
    # reference to the same live file.
    restored_db = tmp_path / "restored.db"
    shutil.copy2(backup / db_path.name, restored_db)
    eng2 = SQLiteDatabaseEngine(restored_db); eng2.connect()
    row = eng2.query_one(
        "SELECT rationale FROM satsa_findings LIMIT 1")
    assert row["rationale"] != "TAMPERED"
    eng2.close()
