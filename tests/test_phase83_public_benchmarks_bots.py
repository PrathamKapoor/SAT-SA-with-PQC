"""Phase P27 — Splunk BOTS public-dataset adapter.

Honesty note (see public_benchmarks/__init__.py): this environment has
no practical way to download an actual Splunk BOTS export
(registration-gated, multi-gigabyte, distributed as a Splunk index
snapshot). Every row used here is a small, hand-built sample matching
Splunk Enterprise Security's publicly documented notable-event field
schema. This proves the adapter parses that documented shape
correctly, NOT that it has been run against a real downloaded BOTS
dataset. That boundary is deliberate and disclosed.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from public_benchmarks.bots.ingest_adapter import (
    URGENCY_TO_SEVERITY,
    BotsParseError,
    ConvertReport,
    convert_jsonl,
    parse_rows,
    to_alerts_csv,
)
from public_benchmarks.provenance import DERIVED_FROM_SOURCE


EXPECTED_SIGNALS_PATH = (
    Path(__file__).resolve().parent.parent
    / "public_benchmarks" / "bots" / "expected_signals.json")
SCENARIO_MANIFEST_PATH = (
    Path(__file__).resolve().parent.parent
    / "public_benchmarks" / "bots" / "scenario_manifest.json")


def _row(dest="10.0.1.5", time=1499414400.0, urgency="high",
        search_name="Suspicious Login Activity", **extra):
    row = {"_time": time, "dest": dest, "urgency": urgency,
          "search_name": search_name}
    row.update(extra)
    return row


# ---------------------------------------------------------------------------
# expected_signals.json stays in sync with the actual code
# ---------------------------------------------------------------------------

def test_expected_signals_json_matches_the_code_urgency_map():
    data = json.loads(EXPECTED_SIGNALS_PATH.read_text(encoding="utf-8"))
    assert data["urgency_to_severity"] == URGENCY_TO_SEVERITY


def test_expected_signals_json_discloses_the_verification_boundary():
    data = json.loads(EXPECTED_SIGNALS_PATH.read_text(encoding="utf-8"))
    assert "not_verified_against" in data["_meta"]
    assert data["_meta"]["provenance_type"] == DERIVED_FROM_SOURCE


def test_scenario_manifest_discloses_its_template_status():
    """The manifest must not silently present placeholder content as
    if it were filled in against real data."""
    data = json.loads(SCENARIO_MANIFEST_PATH.read_text(encoding="utf-8"))
    assert data["_meta"]["status"] == "TEMPLATE -- not filled in against a real dataset"
    assert data["bots_source_to_scenario_mapping"] == []


# ---------------------------------------------------------------------------
# parse_rows — pure conversion logic
# ---------------------------------------------------------------------------

def test_known_urgency_maps_to_documented_severity():
    for urgency, expected_severity in URGENCY_TO_SEVERITY.items():
        rows = [_row(urgency=urgency)]
        alerts, report = parse_rows(rows, source_name="test")
        assert len(alerts) == 1
        assert alerts[0]["severity"] == expected_severity
        assert report.unrecognized_urgency == {}


def test_missing_urgency_defaults_to_unknown_and_is_surfaced():
    rows = [{"_time": 1499414400.0, "dest": "10.0.1.5",
             "search_name": "Something"}]
    alerts, report = parse_rows(rows, source_name="test")
    assert len(alerts) == 1
    assert alerts[0]["severity"] == "unknown"
    assert "(missing)" in report.unrecognized_urgency


def test_unrecognized_urgency_defaults_to_unknown_and_is_surfaced():
    rows = [_row(urgency="banana")]
    alerts, report = parse_rows(rows, source_name="test")
    assert alerts[0]["severity"] == "unknown"
    assert report.unrecognized_urgency == {"banana": 1}


def test_severity_field_used_when_urgency_absent():
    """Some exports use `severity` rather than `urgency` -- both are
    Splunk-documented field names for the same concept."""
    rows = [{"_time": 1499414400.0, "dest": "10.0.1.5", "severity": "critical",
             "search_name": "x"}]
    alerts, _ = parse_rows(rows, source_name="test")
    assert alerts[0]["severity"] == "critical"


def test_missing_required_field_is_rejected_not_crashed():
    rows = [{"_time": 1499414400.0}]  # no dest
    alerts, report = parse_rows(rows, source_name="test")
    assert alerts == []
    assert "dest" in report.rejected[0]["reason"]


def test_empty_dest_is_rejected():
    rows = [_row(dest="")]
    alerts, report = parse_rows(rows, source_name="test")
    assert alerts == []


def test_epoch_time_parses():
    rows = [_row(time=1499414400)]
    alerts, report = parse_rows(rows, source_name="test")
    assert report.rejected == []
    assert alerts[0]["created_at"] == 1499414400.0


def test_epoch_time_as_string_parses():
    rows = [_row(time="1499414400")]
    alerts, report = parse_rows(rows, source_name="test")
    assert report.rejected == []


def test_iso8601_time_parses():
    rows = [_row(time="2017-07-07T08:00:00")]
    alerts, report = parse_rows(rows, source_name="test")
    assert report.rejected == []


def test_unrecognized_time_format_is_rejected_with_reason():
    rows = [_row(time="not-a-real-timestamp")]
    alerts, report = parse_rows(rows, source_name="test")
    assert alerts == []
    assert "_time" in report.rejected[0]["reason"]


def test_category_prefers_search_name_then_signature_then_unspecified():
    rows = [_row(search_name="Rule A")]
    alerts, _ = parse_rows(rows, source_name="test")
    assert alerts[0]["category"] == "Rule A"

    rows2 = [{"_time": 1.0, "dest": "10.0.1.5", "urgency": "high",
              "signature": "Rule B"}]
    alerts2, _ = parse_rows(rows2, source_name="test")
    assert alerts2[0]["category"] == "Rule B"

    rows3 = [{"_time": 1.0, "dest": "10.0.1.5", "urgency": "high"}]
    alerts3, _ = parse_rows(rows3, source_name="test")
    assert alerts3[0]["category"] == "unspecified"


def test_src_added_to_asset_ids_when_present_and_distinct():
    rows = [_row(src="10.0.1.1")]
    alerts, _ = parse_rows(rows, source_name="test")
    assert alerts[0]["asset_ids"] == ["10.0.1.5", "10.0.1.1"]


def test_src_not_duplicated_when_equal_to_dest():
    rows = [_row(dest="10.0.1.5", src="10.0.1.5")]
    alerts, _ = parse_rows(rows, source_name="test")
    assert alerts[0]["asset_ids"] == ["10.0.1.5"]


def test_every_alert_carries_source_derived_provenance():
    rows = [_row()]
    alerts, _ = parse_rows(rows, source_name="test")
    assert alerts[0]["provenance"]["provenance_type"] == DERIVED_FROM_SOURCE
    assert alerts[0]["provenance"]["source_dataset"] == "Splunk BOTS"


def test_custom_source_dataset_name_is_honored():
    rows = [_row()]
    alerts, _ = parse_rows(rows, source_name="test", source_dataset="Splunk BOTS v3")
    assert alerts[0]["provenance"]["source_dataset"] == "Splunk BOTS v3"


def test_native_id_prefers_event_id_when_present():
    rows = [_row(event_id="EVT-12345")]
    alerts, _ = parse_rows(rows, source_name="test")
    assert alerts[0]["native_id"] == "bots-EVT-12345"


def test_native_id_falls_back_to_deterministic_hash():
    rows = [_row(), _row()]
    alerts1, _ = parse_rows(rows, source_name="fileA")
    alerts2, _ = parse_rows(rows, source_name="fileA")
    assert alerts1[0]["native_id"] == alerts2[0]["native_id"]


def test_convert_report_counts_are_consistent():
    rows = [_row(), {"_time": 1.0}, _row(dest="")]
    alerts, report = parse_rows(rows, source_name="test")
    assert report.rows_read == 3
    assert report.rows_read == report.alerts_emitted + len(report.rejected)


# ---------------------------------------------------------------------------
# to_alerts_csv + real satsa.ingest round trip
# ---------------------------------------------------------------------------

def test_to_alerts_csv_produces_satsa_ingest_compatible_columns():
    rows = [_row()]
    alerts, _ = parse_rows(rows, source_name="test")
    csv_text = to_alerts_csv(alerts)
    reader = csv.DictReader(csv_text.splitlines())
    assert reader.fieldnames == [
        "native_id", "created_at", "severity", "category", "asset_ids"]


def test_to_alerts_csv_round_trips_through_real_satsa_ingestion(tmp_path):
    rows = [
        _row(dest="10.0.1.1", time=1499414400.0, urgency="critical"),
        _row(dest="10.0.1.2", time=1499414500.0, urgency="medium"),
    ]
    alerts, report = parse_rows(rows, source_name="sample")
    assert report.alerts_emitted == 2

    sub = tmp_path / "BOTS-SAMPLE"
    sub.mkdir()
    (sub / "alerts.csv").write_text(to_alerts_csv(alerts), encoding="utf-8")

    from qsmlops.database.engine import SQLiteDatabaseEngine
    from qsmlops.database.migrations import MigrationRunner
    from satsa.service import SatsaService

    eng = SQLiteDatabaseEngine(tmp_path / "satsa.db")
    eng.connect()
    MigrationRunner(eng).migrate()
    svc = SatsaService(eng)
    entity = svc.register_entity("BOTS-SAMPLE", sector="benchmark",
                                   environment_class="public-dataset")
    assessment = svc.open_assessment(entity.id, 1499414400.0, 1499500800.0)
    result = svc.submit(assessment.id, {"alerts": sub / "alerts.csv"})
    assert result.categories["alerts"]["accepted"] == 2
    assert result.categories["alerts"]["rejected"] == 0


# ---------------------------------------------------------------------------
# convert_jsonl — file-format robustness
# ---------------------------------------------------------------------------

def test_convert_jsonl_handles_newline_delimited_json(tmp_path):
    path = tmp_path / "notables.jsonl"
    path.write_text(
        json.dumps(_row(dest="10.0.1.1")) + "\n"
        + json.dumps(_row(dest="10.0.1.2")) + "\n",
        encoding="utf-8")
    alerts, report = convert_jsonl(path)
    assert report.alerts_emitted == 2


def test_convert_jsonl_handles_a_json_array(tmp_path):
    path = tmp_path / "notables.json"
    path.write_text(json.dumps([_row(dest="10.0.1.1"), _row(dest="10.0.1.2")]),
                    encoding="utf-8")
    alerts, report = convert_jsonl(path)
    assert report.alerts_emitted == 2


def test_convert_jsonl_skips_blank_lines(tmp_path):
    path = tmp_path / "notables.jsonl"
    path.write_text(
        json.dumps(_row()) + "\n\n\n" + json.dumps(_row()) + "\n",
        encoding="utf-8")
    alerts, report = convert_jsonl(path)
    assert report.alerts_emitted == 2
