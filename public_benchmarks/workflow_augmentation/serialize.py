"""Render a ``WorkflowBundle`` (plus the source-derived alerts/assets
it was built from) as a satsa.ingest-ready submission directory, and
extract every generated record's provenance into a separate,
auditable JSON manifest.

The provenance manifest is the literal artifact the user's own
instruction asked for: "For every generated case, investigation,
escalation, or disposition, store: {provenance_type, source_dataset,
generation_policy_version, scenario_id}." It lives alongside the CSVs
as ``provenance_manifest.json``, not inside them — the CSV columns
stay byte-for-byte what ``satsa.ingest`` (and any other SAT-SA
submission) expects; nothing about the ingestible files themselves
changes shape because they happen to be benchmark-generated.
"""
from __future__ import annotations

import csv
import io
import json
from pathlib import Path

from public_benchmarks.workflow_augmentation.generator import WorkflowBundle

_ALERT_COLUMNS = ["native_id", "created_at", "severity", "category",
                  "acknowledged_at", "closed_at", "case_ids", "asset_ids"]
_CASE_COLUMNS = ["native_id", "opened_at", "status", "closed_at", "owner",
                 "alert_ids", "closure_reason"]
_STEP_COLUMNS = ["case_id", "action_type", "performed_at", "sequence",
                 "analyst", "note"]
_ESCALATION_COLUMNS = ["alert_id", "case_id", "occurred_at",
                       "destination_role", "trigger", "outcome"]
_DISPOSITION_COLUMNS = ["alert_id", "case_id", "occurred_at", "outcome",
                        "reason", "approver_role"]
_ASSET_COLUMNS = ["native_id", "criticality"]


def _write_csv(rows: list, columns: list, list_fields: tuple = ()) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(columns)
    for r in rows:
        line = []
        for col in columns:
            v = r.get(col, "")
            if col in list_fields and isinstance(v, list):
                v = ";".join(str(x) for x in v)
            if v is None:
                v = ""
            line.append(v)
        writer.writerow(line)
    return buf.getvalue()


def to_alerts_csv(alerts: list) -> str:
    return _write_csv(alerts, _ALERT_COLUMNS, list_fields=("case_ids", "asset_ids"))


def to_cases_csv(cases: list) -> str:
    return _write_csv(cases, _CASE_COLUMNS, list_fields=("alert_ids",))


def to_investigation_steps_csv(steps: list) -> str:
    return _write_csv(steps, _STEP_COLUMNS)


def to_escalations_csv(escalations: list) -> str:
    return _write_csv(escalations, _ESCALATION_COLUMNS)


def to_dispositions_csv(dispositions: list) -> str:
    return _write_csv(dispositions, _DISPOSITION_COLUMNS)


def to_assets_csv(assets: list) -> str:
    return _write_csv(assets, _ASSET_COLUMNS)


def provenance_manifest(bundle: WorkflowBundle) -> dict:
    """Every generated record's own provenance tag, keyed by record
    type and a stable local key (native_id for cases/assets; a
    composite key for steps/escalations/dispositions, which have no
    native_id of their own in the canonical schema)."""
    manifest = {
        "scenario_id": bundle.scenario_id,
        "source_dataset": bundle.source_dataset,
        "records": {"cases": {}, "investigation_steps": [],
                    "escalations": [], "dispositions": [], "extra_assets": {}},
    }
    for c in bundle.cases:
        manifest["records"]["cases"][c["native_id"]] = c["provenance"]
    for s in bundle.investigation_steps:
        manifest["records"]["investigation_steps"].append({
            "case_id": s["case_id"], "sequence": s["sequence"],
            "provenance": s["provenance"]})
    for e in bundle.escalations:
        manifest["records"]["escalations"].append({
            "alert_id": e["alert_id"], "case_id": e["case_id"],
            "provenance": e["provenance"]})
    for d in bundle.dispositions:
        manifest["records"]["dispositions"].append({
            "alert_id": d["alert_id"], "case_id": d["case_id"],
            "provenance": d["provenance"]})
    for a in bundle.extra_assets:
        manifest["records"]["extra_assets"][a["native_id"]] = a["provenance"]
    return manifest


def write_submission(directory: Path, bundle: WorkflowBundle, *,
                     original_assets: list = None) -> dict:
    """Write a full satsa.ingest-ready submission directory from a
    generated ``bundle``, plus the ``original_assets`` (the
    source-derived assets, e.g. from
    ``public_benchmarks.cicids2017.asset_mapper``) merged with any
    ``bundle.extra_assets`` the scenario invented.

    Respects ``bundle.omit_categories`` — a category named there is
    not written at all (not written empty), matching
    ``missing_escalation_file``'s deliberate "the file itself is
    absent" semantics.

    Returns the ``provenance_manifest`` dict (also written to
    ``provenance_manifest.json`` in the same directory).
    """
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)

    if "alerts" not in bundle.omit_categories:
        (directory / "alerts.csv").write_text(
            to_alerts_csv(bundle.alerts_used), encoding="utf-8")
    if "cases" not in bundle.omit_categories:
        (directory / "cases.csv").write_text(
            to_cases_csv(bundle.cases), encoding="utf-8")
    if "investigation_steps" not in bundle.omit_categories:
        (directory / "investigation_steps.csv").write_text(
            to_investigation_steps_csv(bundle.investigation_steps), encoding="utf-8")
    if "escalations" not in bundle.omit_categories:
        (directory / "escalations.csv").write_text(
            to_escalations_csv(bundle.escalations), encoding="utf-8")
    if "dispositions" not in bundle.omit_categories:
        (directory / "dispositions.csv").write_text(
            to_dispositions_csv(bundle.dispositions), encoding="utf-8")
    if "assets" not in bundle.omit_categories:
        all_assets = list(original_assets or []) + list(bundle.extra_assets)
        (directory / "assets.csv").write_text(
            to_assets_csv(all_assets), encoding="utf-8")

    manifest = provenance_manifest(bundle)
    (directory / "provenance_manifest.json").write_text(
        json.dumps(manifest, indent=2, default=str), encoding="utf-8")
    return manifest
