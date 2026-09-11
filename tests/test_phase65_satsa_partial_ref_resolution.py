"""Phase P19 follow-up — a partially-unresolvable escalation/disposition
reference must not sink an otherwise-valid record.

Found by ``tests/test_phase64_satsa_fresh_database_e2e.py``'s negative-
control test: a synthetic CSE tuned to be operationally clean
(escalation_rate=1.0, disposition_rate=1.0 — every critical/high alert
escalated, every alert dispositioned) still tripped
``execution_gap.critical_without_escalation``,
``negative_space.missing_escalation`` and
``negative_space.missing_disposition``. Root cause, confirmed by
inspecting ``result.categories`` from ``SatsaService.submit()``: 3 of
12 generated escalations and 8 of 30 generated dispositions were
silently rejected during normalization, even though each one's
``alert_id`` resolved to a real, accepted alert — because their
*optional* ``case_id`` happened to reference one of 2 cases that were
independently rejected during case validation (unrelated to the
escalation/disposition itself).

``satsa/ingest/normalize.py``'s own module docstring already documents
the intended contract: "warnings capture suspected-but-tolerated
issues... unresolvable *optional* references." ``_resolve_either``'s
own docstring says the record's invariant is "at least one resolvable
ref." But the two call sites (escalations, dispositions) rejected the
whole record via ``if not fail`` whenever *either* half failed to
resolve — contradicting both docstrings. This fixes ``_resolve_either``
to only reject when *neither* reference resolves; a lone unresolvable
reference downgrades to a warning and the record is still built with
the unresolved half as ``None``.
"""
from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

BASE = 1735689600.0
END = 1738281600.0


@pytest.fixture()
def engine(tmp_path):
    from qsmlops.database.engine import SQLiteDatabaseEngine
    from qsmlops.database.migrations import MigrationRunner
    eng = SQLiteDatabaseEngine(tmp_path / "satsa.db")
    eng.connect()
    MigrationRunner(eng).migrate()
    yield eng
    eng.close()


@pytest.fixture()
def service(engine):
    from satsa.service import SatsaService
    return SatsaService(engine)


def _write(tmp_path, files):
    d = tmp_path / "CSE-PARTIAL"
    d.mkdir(parents=True, exist_ok=True)
    for fname, content in files.items():
        (d / fname).write_text(content, encoding="utf-8")
    return d


def test_escalation_with_valid_alert_but_unknown_case_is_kept(tmp_path, service):
    """A1 exists and resolves; C-GHOST does not exist anywhere in this
    submission. Before the fix, this escalation was silently dropped
    (0 accepted, 1 rejected). It must now be accepted, linked to A1,
    with case_id=None and a warning — not a rejection."""
    files = {
        "assets.csv": "native_id,criticality,environment,controls\n"
                       "web-01,critical,prod,AV\n",
        "alerts.csv": (
            "native_id,created_at,severity,category,acknowledged_at,"
            "closed_at,case_ids,asset_ids\n"
            f"A1,{BASE+100},critical,malware,{BASE+400},{BASE+3600},,web-01\n"
        ),
        "escalations.csv": (
            "alert_id,case_id,occurred_at,destination_role,trigger,outcome\n"
            f"A1,C-GHOST,{BASE+500},soc-l2,severity critical,acknowledged\n"
        ),
    }
    d = _write(tmp_path, files)
    entity = service.register_entity("CSE-PARTIAL", sector="defence")
    a = service.open_assessment(entity.id, BASE, END)
    result = service.submit(a.id, d)

    assert result.categories["escalations"]["accepted"] == 1, (
        "the escalation must be kept — its alert_id resolved even "
        "though its case_id did not")
    assert result.categories["escalations"]["rejected"] == 0

    row = service._db.query_one(
        "SELECT * FROM satsa_escalations WHERE entity_id=?", (entity.id,))
    assert row is not None
    assert row["case_id"] is None, (
        "the unresolvable case reference must be dropped (None), not "
        "silently substituted or fabricated")
    alert_row = service._db.query_one(
        "SELECT id FROM satsa_alerts WHERE native_id='A1'")
    assert row["alert_id"] == alert_row["id"]


def test_disposition_with_valid_case_but_unknown_alert_is_kept(tmp_path, service):
    """Symmetric case: C1 exists and resolves; AL-GHOST does not. The
    disposition must be kept, linked to C1, alert_id=None."""
    files = {
        "cases.csv": "native_id,opened_at,status,closed_at,owner,alert_ids,closure_reason\n"
                     f"C1,{BASE+150},closed,{BASE+7000},alice-pseudo,,resolved\n",
        "dispositions.csv": (
            "alert_id,case_id,occurred_at,outcome,reason,approver_role\n"
            f"AL-GHOST,C1,{BASE+3500},true_positive,confirmed,soc-lead\n"
        ),
    }
    d = _write(tmp_path, files)
    entity = service.register_entity("CSE-PARTIAL2", sector="defence")
    a = service.open_assessment(entity.id, BASE, END)
    result = service.submit(a.id, d)

    assert result.categories["dispositions"]["accepted"] == 1
    assert result.categories["dispositions"]["rejected"] == 0
    row = service._db.query_one(
        "SELECT * FROM satsa_dispositions WHERE entity_id=?", (entity.id,))
    assert row is not None
    assert row["alert_id"] is None
    case_row = service._db.query_one(
        "SELECT id FROM satsa_cases WHERE native_id='C1'")
    assert row["case_id"] == case_row["id"]


def test_escalation_with_both_refs_unresolvable_is_still_rejected(tmp_path, service):
    """The true negative: neither reference resolves to anything —
    this must still be rejected, unchanged from prior behavior."""
    files = {
        "escalations.csv": (
            "alert_id,case_id,occurred_at,destination_role,trigger,outcome\n"
            f"AL-GHOST,C-GHOST,{BASE+500},soc-l2,severity critical,acknowledged\n"
        ),
    }
    d = _write(tmp_path, files)
    entity = service.register_entity("CSE-PARTIAL3", sector="defence")
    a = service.open_assessment(entity.id, BASE, END)
    result = service.submit(a.id, d)

    assert result.categories["escalations"]["accepted"] == 0
    assert result.categories["escalations"]["rejected"] == 1


def test_escalation_with_both_refs_valid_still_fully_links(tmp_path, service):
    """The common path is unaffected: both references resolve, both
    fields are populated on the persisted record."""
    files = {
        "assets.csv": "native_id,criticality,environment,controls\n"
                       "web-01,critical,prod,AV\n",
        "alerts.csv": (
            "native_id,created_at,severity,category,acknowledged_at,"
            "closed_at,case_ids,asset_ids\n"
            f"A1,{BASE+100},critical,malware,{BASE+400},{BASE+3600},C1,web-01\n"
        ),
        "cases.csv": "native_id,opened_at,status,closed_at,owner,alert_ids,closure_reason\n"
                     f"C1,{BASE+150},closed,{BASE+7000},alice-pseudo,A1,resolved\n",
        "escalations.csv": (
            "alert_id,case_id,occurred_at,destination_role,trigger,outcome\n"
            f"A1,C1,{BASE+500},soc-l2,severity critical,acknowledged\n"
        ),
    }
    d = _write(tmp_path, files)
    entity = service.register_entity("CSE-PARTIAL4", sector="defence")
    a = service.open_assessment(entity.id, BASE, END)
    result = service.submit(a.id, d)
    assert result.categories["escalations"]["accepted"] == 1
    row = service._db.query_one(
        "SELECT * FROM satsa_escalations WHERE entity_id=?", (entity.id,))
    assert row["alert_id"] is not None
    assert row["case_id"] is not None
