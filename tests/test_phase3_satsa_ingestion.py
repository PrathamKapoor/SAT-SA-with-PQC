"""Phase 3 (SAT-SA) — ingestion regression tests.

Proves the contract documented in docs/phase3/ingestion.md: a valid
periodic CSE submission enters the system and becomes validated
canonical SAT-SA evidence; malformed input, missing fields, duplicates
and broken relationships are detected, reported (never silently dropped)
and never reach the canonical store.

The whole stack is exercised end-to-end through ``SatsaService`` on a
real SQLite engine with the real ``MigrationRunner`` applied (no mocks)
so the tests double as a migration+repository smoke test for the new
satsa_* tables.
"""
from __future__ import annotations

import csv
import json
import textwrap
from pathlib import Path

import pytest

from qsmlops.crypto.hashing import sha3_hex
from satsa.errors import DomainValidationError
from satsa.ingest.normalize import parse_timestamp
from satsa.ingest.readers import (
    IngestionFormatError,
    parse_csv_bytes,
    parse_json_bytes,
    scan_directory,
)
from satsa.ingest.service import IngestionError
from satsa.service import SatsaService


# ---------------------------------------------------------------------------
# fixtures + small test data builders
# ---------------------------------------------------------------------------

BASE = 1735689600.0        # 2025-01-01T00:00:00Z
END = 1738281600.0         # 2025-02-01T00:00:00Z


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
    return SatsaService(engine)


def _open_scope(service, name="CSE-001"):
    entity = service.register_entity(name, sector="defence", environment_class="on-prem")
    a = service.open_assessment(entity.id, BASE, END)
    return entity, a


HEALTHY_FILES = {
    "assets.csv": textwrap.dedent("""\
        native_id,criticality,environment,controls
        web-01,critical,prod,"AV;EDR"
        db-01,high,prod,"DB-FW"
    """),
    "alerts.csv": textwrap.dedent("""\
        native_id,created_at,severity,category,acknowledged_at,closed_at,case_ids,asset_ids
        A1,{t0},critical,malware,{t1},{t2},C1,web-01
        A2,{t3},medium,phishing,{t4},{t5},C1,db-01
    """).format(
        t0=BASE + 100, t1=BASE + 400, t2=BASE + 3600,
        t3=BASE + 200, t4=BASE + 800, t5=BASE + 7200,
    ),
    "cases.csv": textwrap.dedent("""\
        native_id,opened_at,status,closed_at,owner,alert_ids,closure_reason
        C1,{t0},closed,{t1},alice-pseudo,"A1;A2",resolved as malicious
    """).format(t0=BASE + 150, t1=BASE + 7000),
    "investigation_steps.csv": textwrap.dedent("""\
        case_id,action_type,performed_at,sequence,analyst,note,evidence_ids
        C1,triage,{t0},1,alice-pseudo,initial triage note,EV-1
        C1,containment,{t1},2,alice-pseudo,isolated host,EV-2;EV-3
    """).format(t0=BASE + 300, t1=BASE + 1800),
    "escalations.csv": textwrap.dedent("""\
        alert_id,case_id,occurred_at,destination_role,trigger,outcome
        A1,C1,{t0},soc-l2,severity critical,acknowledged
    """).format(t0=BASE + 500),
    "dispositions.csv": textwrap.dedent("""\
        alert_id,case_id,occurred_at,outcome,reason,approver_role
        A1,C1,{t0},true_positive,confirmed compromise,soc-lead
    """).format(t0=BASE + 3500),
}


def _write(tmp_path, name, files):
    d = tmp_path / name
    d.mkdir(parents=True, exist_ok=True)
    for fname, content in files.items():
        (d / fname).write_text(content, encoding="utf-8")
    return d


# ---------------------------------------------------------------------------
# 1. healthy end-to-end submission (CSV)
# ---------------------------------------------------------------------------

def test_healthy_csv_submission_ingests_to_scope(service, tmp_path):
    entity, assessment = _open_scope(service)
    src = _write(tmp_path, "sub", HEALTHY_FILES)
    result = service.submit(assessment.id, src)

    assert result.status == "accepted"
    assert result.entity_id == entity.id
    assert result.assessment_id == assessment.id
    assert result.counts == {"alerts": 2, "cases": 1,
                             "investigation_steps": 2,
                             "escalations": 1, "dispositions": 1,
                             "assets": 2}
    assert result.snapshot_digest

    dataset = service.load_scope(entity.id, assessment.id)
    assert {a.native_id for a in dataset.alerts} == {"A1", "A2"}
    assert {c.native_id for c in dataset.cases} == {"C1"}
    assert {s.case_id for s in dataset.steps} == {dataset.cases[0].id}
    assert {e.alert_id for e in dataset.escalations} == {dataset.alerts[0].id}
    assert {d.alert_id for d in dataset.dispositions} == {dataset.alerts[0].id}
    assert {a.native_id for a in dataset.assets} == {"web-01", "db-01"}
    assert dataset.submitted_categories == frozenset((
        "alerts", "cases", "investigation_steps",
        "escalations", "dispositions", "assets"))

    # cross-reference resolution really happened
    a1 = next(a for a in dataset.alerts if a.native_id == "A1")
    c1 = dataset.cases[0]
    assert c1.id in a1.case_refs
    assert {dataset.alerts[0].id, dataset.alerts[1].id} == set(c1.alert_refs)

    # chronology properties on the domain record
    assert a1.time_to_acknowledge == pytest.approx(300.0)
    assert a1.time_to_close == pytest.approx(3500.0)


# ---------------------------------------------------------------------------
# 2. provenance is recorded (submission, source records, file digests)
# ---------------------------------------------------------------------------

def test_provenance_records_submission_and_source_records(service, engine, tmp_path):
    entity, assessment = _open_scope(service)
    src = _write(tmp_path, "sub", HEALTHY_FILES)
    result = service.submit(assessment.id, src)
    total_rows = sum(result.counts.values())

    sub_row = service.submissions.get(result.submission_id)
    assert sub_row is not None
    assert sub_row["ingest_status"] == "accepted"
    assert sub_row["snapshot_digest"] == result.snapshot_digest
    digests = json.loads(sub_row["file_digests_json"])
    for fname in HEALTHY_FILES:
        assert fname in digests
        # each digest is the SHA3-256 of the file's actual bytes
        assert digests[fname] == sha3_hex((src / fname).read_bytes())

    src_rows = engine.query_all(
        "SELECT * FROM satsa_source_records WHERE submission_id=?",
        (result.submission_id,))
    assert len(src_rows) == total_rows
    for sr in src_rows:
        assert sr["submission_id"] == result.submission_id
        assert sr["format"] in ("csv", "json")
        assert sr["file_digest"] in digests.values()
        assert sr["original_record_digest"] and sr["locator"]

    # every accepted record carries a resolvable source_record_ref
    bad_refs = engine.query_all(
        "SELECT id FROM satsa_alerts WHERE submission_id=? AND "
        "(source_record_ref='' OR source_record_ref NOT IN "
        "(SELECT id FROM satsa_source_records WHERE submission_id=?))",
        (result.submission_id, result.submission_id))
    assert bad_refs == []


# ---------------------------------------------------------------------------
# 3. JSON submission (array of objects) — same canonical outcome
# ---------------------------------------------------------------------------

def test_valid_json_submission_ingests_identically(service, tmp_path):
    entity, assessment = _open_scope(service, "CSE-JSON")

    files = {
        "alerts.json": json.dumps([
            {"native_id": "A1", "created_at": BASE + 100, "severity": "P1",
             "category": "malware", "acknowledged_at": BASE + 400,
             "closed_at": BASE + 3600, "case_ids": "C1", "asset_ids": "web-01"},
            {"native_id": "A2", "created_at": BASE + 200, "severity": "P3",
             "category": "phishing", "acknowledged_at": BASE + 800,
             "closed_at": BASE + 7200, "case_ids": "C1", "asset_ids": "db-01"},
        ]),
        "cases.json": json.dumps([
            {"native_id": "C1", "opened_at": BASE + 150, "status": "closed",
             "closed_at": BASE + 7000, "owner": "bob", "alert_ids": "A1;A2",
             "closure_reason": "resolved"},
        ]),
        "investigation_steps.json": json.dumps([
            {"case_id": "C1", "action_type": "triage",
             "performed_at": BASE + 300, "sequence": 1, "analyst": "bob",
             "note": "looked", "evidence_ids": "E1"},
        ]),
        "assets.json": json.dumps([
            {"native_id": "web-01", "criticality": "tier1", "environment": "prod",
             "controls": "AV"},
            {"native_id": "db-01", "criticality": "high", "environment": "prod"},
        ]),
    }
    src = _write(tmp_path, "sub_json", files)
    result = service.submit(assessment.id, src)
    assert result.status == "accepted"
    assert result.counts["alerts"] == 2
    assert result.counts["cases"] == 1
    assert result.counts["assets"] == 2

    # every accepted alert/case/asset row records format=json
    rows = engine if False else None
    eng = service._db  # type: ignore[attr-defined]
    formats = {r["format"] for r in eng.query_all(
        "SELECT DISTINCT format FROM satsa_source_records"
        " WHERE submission_id=?", (result.submission_id,))}
    assert formats == {"json"}


def test_jsonl_format_ingests(service, tmp_path):
    entity, assessment = _open_scope(service, "CSE-JSONL")
    lines = [
        json.dumps({"native_id": f"A{i}", "created_at": BASE + 10 * i,
                    "severity": "critical"})
        for i in range(1, 6)
    ]
    src = _write(tmp_path, "sub_jsonl", {"alerts.jsonl": "\n".join(lines)})
    result = service.submit(assessment.id, src)
    assert result.status == "accepted"
    assert result.counts["alerts"] == 5


# ---------------------------------------------------------------------------
# 4. malformed files are not silently dropped
# ---------------------------------------------------------------------------

def test_completely_malformed_submission_raises(engine, service, tmp_path):
    entity, assessment = _open_scope(service, "CSE-BAD")
    src = _write(tmp_path, "sub_bad", {"alerts.json": "{not valid json"})
    with pytest.raises(IngestionError):
        service.submit(assessment.id, src)
    # nothing persisted
    eng = service._db  # type: ignore[attr-defined]
    rows = eng.query_all("SELECT * FROM satsa_alerts")
    assert rows == []
    subs = eng.query_all("SELECT * FROM satsa_submissions")
    assert subs == []


def test_partial_submission_reports_file_failure(service, engine, tmp_path):
    entity, assessment = _open_scope(service, "CSE-PART")
    files = dict(HEALTHY_FILES)
    files["alerts.json"] = "{this is not valid json"
    src = _write(tmp_path, "sub_part", files)
    # remove the competing alerts.csv so the malformed JSON is the file
    # actually scanned (scan_directory uses setdefault on the category)
    (src / "alerts.csv").unlink()
    result = service.submit(assessment.id, src)
    # file failure for alerts but other 5 categories were valid
    assert result.status == "partial"

    sub = service.submissions.get(result.submission_id)
    report = json.loads(sub["ingest_report_json"])
    assert "alerts" in report["categories"]
    assert report["categories"]["alerts"]["present"] is False
    assert "invalid" in report["categories"]["alerts"]["error"].lower()
    # other 5 categories were accepted
    assert report["categories"]["cases"]["accepted"] == 1
    assert report["categories"]["assets"]["accepted"] == 2


def test_empty_directory_raises_informative_error(service, tmp_path):
    entity, assessment = _open_scope(service, "CSE-EMPTY")
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(IngestionError, match="no recognized submission files"):
        service.submit(assessment.id, empty)


# ---------------------------------------------------------------------------
# 5. row-level rejections (missing fields, invalid timestamps, dups)
# ---------------------------------------------------------------------------

def test_missing_required_field_rejects_row_not_whole_submission(
    service, engine, tmp_path
):
    entity, assessment = _open_scope(service, "CSE-MISS")
    bad = dict(HEALTHY_FILES)
    # remove the created_at column header from alerts.csv entirely
    rows = list(csv.DictReader(HEALTHY_FILES["alerts.csv"].splitlines()))
    for r in rows:
        r.pop("created_at", None)
    buf = ["native_id,severity,category,acknowledged_at,closed_at,case_ids,asset_ids"]
    for r in rows:
        buf.append(",".join(str(r[c]) for c in (
            "native_id", "severity", "category", "acknowledged_at",
            "closed_at", "case_ids", "asset_ids")))
    bad["alerts.csv"] = "\n".join(buf) + "\n"
    src = _write(tmp_path, "sub_miss", bad)
    result = service.submit(assessment.id, src)
    # both alert rows are rejected, the rest of the submission lands
    assert result.status == "partial"
    eng = service._db  # type: ignore[attr-defined]
    assert eng.query_all("SELECT id FROM satsa_alerts") == []
    # every rejection cites 'created_at' as the missing field
    sub = service.submissions.get(result.submission_id)
    report = json.loads(sub["ingest_report_json"])
    alerts = report["categories"]["alerts"]
    assert alerts["rejected"] == 2
    for rej in alerts["rejections"]:
        assert any("created_at" in r for r in rej["reasons"])


def test_invalid_timestamp_row_rejected(service, engine, tmp_path):
    entity, assessment = _open_scope(service, "CSE-BAD-TS")
    bad = dict(HEALTHY_FILES)
    # replace A1's timestamp with garbage; A2 stays valid
    lines = HEALTHY_FILES["alerts.csv"].splitlines()
    lines[1] = "A1,not-a-time,critical,malware,{},{},C1,web-01".format(
        BASE + 400, BASE + 3600)
    bad["alerts.csv"] = "\n".join(lines) + "\n"
    src = _write(tmp_path, "sub_badts", bad)
    result = service.submit(assessment.id, src)
    assert result.status == "partial"
    # A1 rejected, A2 accepted
    sub = service.submissions.get(result.submission_id)
    report = json.loads(sub["ingest_report_json"])
    alerts = report["categories"]["alerts"]
    assert alerts["rejected"] == 1
    assert alerts["accepted"] == 1
    assert any("invalid timestamp" in r
               for rej in alerts["rejections"] for r in rej["reasons"])


def test_within_file_duplicate_native_id_rejected(service, tmp_path):
    entity, assessment = _open_scope(service, "CSE-DUP")
    dup = dict(HEALTHY_FILES)
    # duplicate A1 in the same file
    lines = HEALTHY_FILES["alerts.csv"].splitlines()
    lines.append(lines[1])  # same as first data row
    dup["alerts.csv"] = "\n".join(lines) + "\n"
    src = _write(tmp_path, "sub_dup", dup)
    result = service.submit(assessment.id, src)
    assert result.status == "partial"
    sub = service.submissions.get(result.submission_id)
    report = json.loads(sub["ingest_report_json"])
    assert report["categories"]["alerts"]["rejected"] == 1
    assert any("duplicate native_id" in r
               for rej in report["categories"]["alerts"]["rejections"]
               for r in rej["reasons"])


def test_identical_submission_rejected_at_service(service, tmp_path):
    entity, assessment = _open_scope(service, "CSE-RESUB")
    src = _write(tmp_path, "sub", HEALTHY_FILES)
    service.submit(assessment.id, src)
    with pytest.raises(IngestionError, match="identical submission bytes"):
        service.submit(assessment.id, src)


def test_cross_submission_duplicate_native_id_rejected(service, tmp_path):
    entity, assessment = _open_scope(service, "CSE-CROSS")
    src1 = _write(tmp_path, "s1", HEALTHY_FILES)
    service.submit(assessment.id, src1)

    # second submission via the lower-level API so only the new alerts.json
    # is in play (other categories unchanged → identical-digest guard would
    # otherwise mask the duplicate-native_id check we are exercising here)
    new_alerts = Path(tmp_path) / "second_alerts.json"
    new_alerts.write_text(json.dumps([
        {"native_id": "A1", "created_at": BASE + 5000,
         "severity": "high", "category": "malware", "case_ids": "C1"},
        {"native_id": "A3", "created_at": BASE + 500, "severity": "low",
         "category": "test"},
    ]), encoding="utf-8")
    from satsa.ingest.service import IngestionService
    ingester = IngestionService(service._db)  # type: ignore[attr-defined]
    result = ingester.submit_files(
        assessment.id, {"alerts": new_alerts},
        source_system="unit-test-cross",
    )
    sub = service.submissions.get(result.submission_id)
    report = json.loads(sub["ingest_report_json"])
    assert report["categories"]["alerts"]["rejected"] == 1
    assert report["categories"]["alerts"]["accepted"] == 1
    assert any("duplicates an already-ingested record" in r
               for rej in report["categories"]["alerts"]["rejections"]
               for r in rej["reasons"])


# ---------------------------------------------------------------------------
# 6. relationships: mandatory vs optional
# ---------------------------------------------------------------------------

def test_broken_mandatory_reference_rejects_row(service, tmp_path):
    entity, assessment = _open_scope(service, "CSE-REL")
    bad = dict(HEALTHY_FILES)
    # investigation step for a case that does not exist
    lines = HEALTHY_FILES["investigation_steps.csv"].splitlines()
    lines[1] = "C99,triage,{},1,x,note,".format(BASE + 300)
    bad["investigation_steps.csv"] = "\n".join(lines) + "\n"
    src = _write(tmp_path, "sub_rel", bad)
    result = service.submit(assessment.id, src)
    assert result.status == "partial"
    sub = service.submissions.get(result.submission_id)
    report = json.loads(sub["ingest_report_json"])
    steps = report["categories"]["investigation_steps"]
    assert steps["rejected"] == 1
    assert any("unknown case" in r
               for rej in steps["rejections"] for r in rej["reasons"])


def test_optional_unknown_reference_emits_warning_but_accepts(
    service, engine, tmp_path
):
    entity, assessment = _open_scope(service, "CSE-OPT")
    warn = dict(HEALTHY_FILES)
    # alert A1 references a case that does not exist
    lines = HEALTHY_FILES["alerts.csv"].splitlines()
    lines[1] = "A1,{},critical,malware,{},{},C99,web-01".format(
        BASE + 100, BASE + 400, BASE + 3600)
    warn["alerts.csv"] = "\n".join(lines) + "\n"
    src = _write(tmp_path, "sub_opt", warn)
    result = service.submit(assessment.id, src)
    # A1 still accepted (the unknown case ref is dropped + a warning is
    # surfaced); A2 also accepted; the other categories land cleanly.
    assert result.status in ("accepted", "accepted_with_warnings")

    sub = service.submissions.get(result.submission_id)
    report = json.loads(sub["ingest_report_json"])
    assert any("unknown case" in w
               for w in report["categories"]["alerts"]["warnings"])

    # A1 still landed (optional reference, alert doesn't fail)
    eng = service._db  # type: ignore[attr-defined]
    rows = eng.query_all(
        "SELECT native_id, case_refs_json FROM satsa_alerts ORDER BY native_id")
    assert [r["native_id"] for r in rows] == ["A1", "A2"]
    a1 = next(r for r in rows if r["native_id"] == "A1")
    assert json.loads(a1["case_refs_json"]) == []  # the unknown ref was dropped


def test_escalation_requires_at_least_one_ref(service, tmp_path):
    entity, assessment = _open_scope(service, "CSE-ESC")
    bad = dict(HEALTHY_FILES)
    lines = HEALTHY_FILES["escalations.csv"].splitlines()
    lines[1] = ",,{},soc-l2,severity critical,ack".format(BASE + 500)
    bad["escalations.csv"] = "\n".join(lines) + "\n"
    src = _write(tmp_path, "sub_esc", bad)
    result = service.submit(assessment.id, src)
    assert result.status == "partial"
    sub = service.submissions.get(result.submission_id)
    report = json.loads(sub["ingest_report_json"])
    assert report["categories"]["escalations"]["rejected"] == 1


# ---------------------------------------------------------------------------
# 7. severity / criticality normalization with warnings
# ---------------------------------------------------------------------------

def test_unmapped_severity_yields_warning_and_unknown(service, engine, tmp_path):
    entity, assessment = _open_scope(service, "CSE-SEV")
    # replace severity "critical" with something unrecognised
    bad = dict(HEALTHY_FILES)
    bad["alerts.csv"] = HEALTHY_FILES["alerts.csv"].replace(
        "critical", "P9-super-critical", 1)
    src = _write(tmp_path, "sub_sev", bad)
    result = service.submit(assessment.id, src)
    # A1 accepted_with_warnings, A2 still normal
    assert result.status in ("partial", "accepted_with_warnings")
    sub = service.submissions.get(result.submission_id)
    report = json.loads(sub["ingest_report_json"])
    assert any("unrecognized severity" in w
               for w in report["categories"]["alerts"]["warnings"])
    eng = service._db  # type: ignore[attr-defined]
    rows = eng.query_all(
        "SELECT native_id, mapped_severity FROM satsa_alerts ORDER BY native_id")
    assert rows[0]["mapped_severity"] == "unknown"
    assert rows[1]["mapped_severity"] == "medium"


# ---------------------------------------------------------------------------
# 8. multiple entities / assessments — scope isolation
# ---------------------------------------------------------------------------

def test_multiple_entities_have_isolated_scopes(service, tmp_path):
    e1, a1 = _open_scope(service, "CSE-A")
    e2, a2 = _open_scope(service, "CSE-B")

    src1 = _write(tmp_path, "s1", HEALTHY_FILES)
    r1 = service.submit(a1.id, src1)

    # second entity: completely different native ids
    files_b = {
        "alerts.csv": (
            "native_id,created_at,severity,category,acknowledged_at,"
            "closed_at,case_ids,asset_ids\n"
            f"Z1,{BASE + 50},low,test,{BASE + 100},{BASE + 200},Z9,z-host\n"
        ),
        "cases.csv": (
            "native_id,opened_at,status,closed_at,owner,alert_ids,closure_reason\n"
            f"Z9,{BASE + 60},closed,{BASE + 250},z-pseudo,Z1,benign\n"
        ),
        "assets.csv": "native_id,criticality,environment,controls\nz-host,low,dev,\n",
    }
    src2 = _write(tmp_path, "s2", files_b)
    r2 = service.submit(a2.id, src2)

    assert r1.status == "accepted"
    assert r2.status == "accepted"

    ds1 = service.load_scope(e1.id, a1.id)
    ds2 = service.load_scope(e2.id, a2.id)
    assert {a.native_id for a in ds1.alerts} == {"A1", "A2"}
    assert {a.native_id for a in ds2.alerts} == {"Z1"}
    assert {a.native_id for a in ds1.assets} == {"web-01", "db-01"}
    assert {a.native_id for a in ds2.assets} == {"z-host"}


# ---------------------------------------------------------------------------
# 9. determinism (parsing + normalization decisions)
# ---------------------------------------------------------------------------

def test_parse_is_byte_deterministic():
    raw = HEALTHY_FILES["alerts.csv"].encode("utf-8")
    a = parse_csv_bytes(raw, "alerts")
    b = parse_csv_bytes(raw, "alerts")
    assert a.file_digest == b.file_digest
    assert [r.original_digest for r in a.rows] == [
        r.original_digest for r in b.rows
    ]
    # parser is row-order stable
    assert [r.row_number for r in a.rows] == list(range(1, len(a.rows) + 1))


def test_normalize_decisions_are_deterministic(service, tmp_path):
    # two independent parses + normalizations on the same input produce the
    # same set of accepted native ids, same warnings, same rejection reasons.
    from satsa.ingest.normalize import normalize_category
    from satsa.ingest.readers import parse_file

    src = _write(tmp_path, "s", HEALTHY_FILES)
    pf1 = parse_file(src / "alerts.csv", "alerts")
    pf2 = parse_file(src / "alerts.csv", "alerts")

    n1 = normalize_category(pf1, entity_id="e", assessment_id="a",
                            case_native_to_id={"C1": "case-1"},
                            alert_native_to_id={},
                            asset_native_to_id={"web-01": "asset-1",
                                                "db-01": "asset-2"})
    n2 = normalize_category(pf2, entity_id="e", assessment_id="a",
                            case_native_to_id={"C1": "case-1"},
                            alert_native_to_id={},
                            asset_native_to_id={"web-01": "asset-1",
                                                "db-01": "asset-2"})
    assert n1 is not None and n2 is not None
    assert sorted(n1.accepted_native) == sorted(n2.accepted_native)
    assert sorted(n1.warnings) == sorted(n2.warnings)
    assert [r.reasons for r in n1.rejected] == [r.reasons for r in n2.rejected]


def test_scan_directory_recognises_aliases(tmp_path):
    d = tmp_path / "alias"
    d.mkdir()
    (d / "alert.csv").write_text("native_id,created_at\nA1,1\n")
    (d / "Investigation.CSV").write_text("case_id,action_type,performed_at\nC1,x,1\n")
    found = scan_directory(d)
    assert set(found) == {"alerts", "investigation_steps"}


# ---------------------------------------------------------------------------
# 10. parse_timestamp unit checks
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("text,expected", [
    ("1735689600", 1735689600.0),
    ("1735689600.5", 1735689600.5),
    (1735689600, 1735689600.0),
    ("2025-01-01T00:00:00Z", 1735689600.0),
    ("2025-01-01T05:30:00+05:30", 1735689600.0),
])
def test_parse_timestamp(text, expected):
    assert parse_timestamp(text) == pytest.approx(expected)


def test_parse_timestamp_rejects_garbage():
    with pytest.raises(ValueError):
        parse_timestamp("not a time")


# ---------------------------------------------------------------------------
# 11. SatsaService + domain validation guards
# ---------------------------------------------------------------------------

def test_register_entity_is_idempotent_by_name(service):
    e1 = service.register_entity("CSE-X", sector="defence")
    e2 = service.register_entity("CSE-X", sector="defence")
    assert e1.id == e2.id


def test_open_assessment_validates_period(service):
    e = service.register_entity("CSE-Y")
    with pytest.raises(DomainValidationError):
        service.open_assessment(e.id, END, BASE)  # end before start


def test_open_assessment_rejects_unknown_entity(service):
    with pytest.raises(DomainValidationError):
        service.open_assessment("ghost-id", BASE, END)


# ---------------------------------------------------------------------------
# 12. JSON parsing edge cases
# ---------------------------------------------------------------------------

def test_json_object_with_records_key_parses(tmp_path):
    raw = json.dumps({
        "alerts": [
            {"native_id": "A1", "created_at": BASE + 1, "severity": "critical"},
            {"native_id": "A2", "created_at": BASE + 2, "severity": "high"},
        ]
    }).encode()
    pf = parse_json_bytes(raw, "alerts")
    assert pf.format == "json"
    assert len(pf.rows) == 2
    assert [r.data["native_id"] for r in pf.rows] == ["A1", "A2"]


def test_json_not_an_array_raises_format_error():
    bad = b'"just a string"'
    with pytest.raises(IngestionFormatError):
        parse_json_bytes(bad, "alerts")


def test_csv_missing_header_raises_format_error():
    with pytest.raises(IngestionFormatError):
        parse_csv_bytes(b"", "alerts")
