"""Phase P27 — CIC-IDS2017 public-dataset adapter.

Honesty note (see public_benchmarks/__init__.py): this environment has
no practical way to download the actual CIC-IDS2017 dataset files
(large, access-gated research downloads). Every row used here is a
small, hand-built sample matching the dataset's publicly documented
CICFlowMeter CSV schema — this proves the adapter parses the
documented shape correctly, NOT that it has been run against the real
downloaded corpus. That boundary is deliberate and disclosed, not an
oversight.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from public_benchmarks.cicids2017.asset_mapper import build_assets, to_assets_csv
from public_benchmarks.cicids2017.ingest_adapter import (
    ATTACK_SEVERITY,
    BENIGN_LABEL,
    ConvertReport,
    convert_file,
    parse_rows,
    to_alerts_csv,
)
from public_benchmarks.provenance import DERIVED_FROM_SOURCE


EXPECTED_SIGNALS_PATH = (
    Path(__file__).resolve().parent.parent
    / "public_benchmarks" / "cicids2017" / "expected_signals.json")


def _row(dest_ip="10.0.0.5", timestamp="5/7/2017 8:42", label="DDoS", **extra):
    row = {"destination ip": dest_ip, "timestamp": timestamp, "label": label}
    row.update(extra)
    return row


# ---------------------------------------------------------------------------
# expected_signals.json stays in sync with the actual code
# ---------------------------------------------------------------------------

def test_expected_signals_json_matches_the_code_severity_map():
    """The externally-auditable JSON mapping must never silently drift
    from the code that actually implements it."""
    data = json.loads(EXPECTED_SIGNALS_PATH.read_text(encoding="utf-8"))
    json_map = {k.lower(): v for k, v in data["label_to_severity"].items()
               if k != "BENIGN"}
    assert json_map == ATTACK_SEVERITY


def test_expected_signals_json_discloses_the_verification_boundary():
    data = json.loads(EXPECTED_SIGNALS_PATH.read_text(encoding="utf-8"))
    assert "not_verified_against" in data["_meta"]
    assert data["_meta"]["provenance_type"] == DERIVED_FROM_SOURCE


# ---------------------------------------------------------------------------
# parse_rows — pure conversion logic
# ---------------------------------------------------------------------------

def test_benign_rows_are_skipped_not_converted():
    rows = [_row(label="BENIGN"), _row(label="BENIGN")]
    alerts, report = parse_rows(rows, source_name="test")
    assert alerts == []
    assert report.benign_skipped == 2
    assert report.alerts_emitted == 0


def test_benign_label_matching_is_case_insensitive():
    rows = [_row(label="benign"), _row(label="Benign")]
    alerts, report = parse_rows(rows, source_name="test")
    assert report.benign_skipped == 2


def test_known_attack_label_maps_to_documented_severity():
    for label, expected_severity in ATTACK_SEVERITY.items():
        rows = [_row(label=label)]
        alerts, report = parse_rows(rows, source_name="test")
        assert len(alerts) == 1
        assert alerts[0]["severity"] == expected_severity
        assert alerts[0]["category"] == label
        assert report.unrecognized_labels == {}


def test_unrecognized_attack_label_defaults_to_medium_and_is_surfaced():
    rows = [_row(label="SomeNewAttackType2099")]
    alerts, report = parse_rows(rows, source_name="test")
    assert len(alerts) == 1
    assert alerts[0]["severity"] == "medium"
    assert report.unrecognized_labels == {"SomeNewAttackType2099": 1}


def test_alert_carries_destination_ip_as_asset_id():
    rows = [_row(dest_ip="192.168.1.50", label="PortScan")]
    alerts, _ = parse_rows(rows, source_name="test")
    assert alerts[0]["asset_ids"] == ["192.168.1.50"]


def test_native_id_is_deterministic_given_source_and_row_index():
    rows = [_row(), _row()]
    alerts1, _ = parse_rows(rows, source_name="fileA")
    alerts2, _ = parse_rows(rows, source_name="fileA")
    assert [a["native_id"] for a in alerts1] == [a["native_id"] for a in alerts2]
    assert alerts1[0]["native_id"] != alerts1[1]["native_id"]


def test_every_alert_carries_source_derived_provenance():
    rows = [_row()]
    alerts, _ = parse_rows(rows, source_name="test")
    assert alerts[0]["provenance"]["provenance_type"] == DERIVED_FROM_SOURCE
    assert alerts[0]["provenance"]["source_dataset"] == "CIC-IDS2017"


def test_missing_required_column_is_rejected_not_crashed():
    rows = [{"timestamp": "5/7/2017 8:42", "label": "DDoS"}]  # no destination ip
    alerts, report = parse_rows(rows, source_name="test")
    assert alerts == []
    assert len(report.rejected) == 1
    assert "destination ip" in report.rejected[0]["reason"]


def test_empty_destination_ip_is_rejected():
    rows = [_row(dest_ip="")]
    alerts, report = parse_rows(rows, source_name="test")
    assert alerts == []
    assert len(report.rejected) == 1


@pytest.mark.parametrize("ts", [
    "5/7/2017 8:42",
    "05/07/2017 08:42:15",
    "2017-07-05 08:42:15",
])
def test_multiple_known_timestamp_formats_parse(ts):
    rows = [_row(timestamp=ts)]
    alerts, report = parse_rows(rows, source_name="test")
    assert len(alerts) == 1
    assert report.rejected == []


def test_unrecognized_timestamp_format_is_rejected_with_reason():
    rows = [_row(timestamp="not-a-real-timestamp")]
    alerts, report = parse_rows(rows, source_name="test")
    assert alerts == []
    assert "timestamp" in report.rejected[0]["reason"]


def test_convert_report_counts_are_consistent():
    rows = [_row(label="BENIGN"), _row(label="DDoS"), _row(dest_ip="")]
    alerts, report = parse_rows(rows, source_name="test")
    assert report.rows_read == 3
    assert report.benign_skipped == 1
    assert report.alerts_emitted == 1
    assert len(report.rejected) == 1
    assert report.rows_read == (
        report.benign_skipped + report.alerts_emitted + len(report.rejected))


# ---------------------------------------------------------------------------
# to_alerts_csv — output feeds satsa.ingest directly
# ---------------------------------------------------------------------------

def test_to_alerts_csv_produces_satsa_ingest_compatible_columns():
    rows = [_row(dest_ip="10.0.0.9", label="DDoS")]
    alerts, _ = parse_rows(rows, source_name="test")
    csv_text = to_alerts_csv(alerts)
    reader = csv.DictReader(csv_text.splitlines())
    parsed_rows = list(reader)
    assert reader.fieldnames == [
        "native_id", "created_at", "severity", "category", "asset_ids"]
    assert parsed_rows[0]["severity"] == "critical"
    assert parsed_rows[0]["asset_ids"] == "10.0.0.9"


def test_to_alerts_csv_escapes_commas_in_category_safely():
    alerts = [{
        "native_id": "x1", "created_at": 1.0, "severity": "high",
        "category": "Web Attack, Custom", "asset_ids": ["1.2.3.4"],
    }]
    csv_text = to_alerts_csv(alerts)
    reader = csv.DictReader(csv_text.splitlines())
    row = next(reader)
    assert row["category"] == "Web Attack, Custom"


def test_to_alerts_csv_round_trips_through_real_satsa_ingestion(tmp_path):
    """The converted alerts must be genuinely ingestible by SAT-SA's
    real pipeline, not just structurally CSV-shaped."""
    rows = [
        _row(dest_ip="10.0.0.1", timestamp="5/7/2017 8:00", label="DDoS"),
        _row(dest_ip="10.0.0.2", timestamp="5/7/2017 8:05", label="PortScan"),
        _row(dest_ip="10.0.0.1", timestamp="5/7/2017 8:10", label="BENIGN"),
    ]
    alerts, report = parse_rows(rows, source_name="sample")
    assert report.alerts_emitted == 2
    assets = build_assets(alerts)

    sub = tmp_path / "CICIDS-SAMPLE"
    sub.mkdir()
    (sub / "alerts.csv").write_text(to_alerts_csv(alerts), encoding="utf-8")
    (sub / "assets.csv").write_text(to_assets_csv(assets), encoding="utf-8")

    from qsmlops.database.engine import SQLiteDatabaseEngine
    from qsmlops.database.migrations import MigrationRunner
    from satsa.service import SatsaService

    eng = SQLiteDatabaseEngine(tmp_path / "satsa.db")
    eng.connect()
    MigrationRunner(eng).migrate()
    svc = SatsaService(eng)
    entity = svc.register_entity("CICIDS-SAMPLE", sector="benchmark",
                                   environment_class="public-dataset")
    assessment = svc.open_assessment(entity.id, 1499414400.0, 1499500800.0)
    result = svc.submit(assessment.id, {
        "alerts": sub / "alerts.csv", "assets": sub / "assets.csv"})
    assert result.categories["alerts"]["accepted"] == 2
    assert result.categories["alerts"]["rejected"] == 0


# ---------------------------------------------------------------------------
# asset_mapper
# ---------------------------------------------------------------------------

def test_build_assets_uses_highest_severity_seen():
    alerts = [
        {"asset_ids": ["10.0.0.1"], "severity": "medium"},
        {"asset_ids": ["10.0.0.1"], "severity": "critical"},
    ]
    assets = build_assets(alerts)
    assert len(assets) == 1
    assert assets[0]["native_id"] == "10.0.0.1"
    assert assets[0]["criticality"] == "critical"


def test_build_assets_deduplicates_across_multiple_alerts():
    alerts = [
        {"asset_ids": ["10.0.0.1"], "severity": "high"},
        {"asset_ids": ["10.0.0.2"], "severity": "medium"},
        {"asset_ids": ["10.0.0.1"], "severity": "medium"},
    ]
    assets = build_assets(alerts)
    assert {a["native_id"] for a in assets} == {"10.0.0.1", "10.0.0.2"}


def test_build_assets_carries_source_derived_provenance():
    alerts = [{"asset_ids": ["10.0.0.1"], "severity": "high"}]
    assets = build_assets(alerts)
    assert assets[0]["provenance"]["provenance_type"] == DERIVED_FROM_SOURCE


def test_to_assets_csv_round_trips():
    assets = [{"native_id": "10.0.0.1", "criticality": "critical",
              "provenance": {}}]
    csv_text = to_assets_csv(assets)
    reader = csv.DictReader(csv_text.splitlines())
    row = next(reader)
    assert row["native_id"] == "10.0.0.1"
    assert row["criticality"] == "critical"


# ---------------------------------------------------------------------------
# convert_file — header-normalization robustness (schema-conformant file)
# ---------------------------------------------------------------------------

def test_convert_file_handles_leading_whitespace_in_headers(tmp_path):
    """The documented quirk this adapter's docstring calls out: many
    real CIC-IDS2017 mirrors prefix most headers with a space."""
    csv_text = (
        "Flow ID, Source IP, Destination IP, Timestamp, Label\n"
        "f1,10.0.0.9,10.0.0.5,5/7/2017 8:42,DDoS\n"
    )
    path = tmp_path / "sample.csv"
    path.write_text(csv_text, encoding="utf-8")
    alerts, report = convert_file(path)
    assert report.alerts_emitted == 1
    assert alerts[0]["asset_ids"] == ["10.0.0.5"]


def test_convert_file_uses_filename_stem_for_native_id_prefix(tmp_path):
    csv_text = "Destination IP,Timestamp,Label\n10.0.0.5,5/7/2017 8:42,DDoS\n"
    path = tmp_path / "Monday-WorkingHours.csv"
    path.write_text(csv_text, encoding="utf-8")
    alerts, _ = convert_file(path)
    assert alerts[0]["native_id"].startswith("cicids-Monday-WorkingHours-")
