"""Export a development fixture for the web UI from a REAL SAT-SA backend run.

Development-only. This script never touches a real deployment database:
it builds a fresh temporary SQLite database + trust key directory, loads
the committed demo dataset (docs/demo/submissions/) through the real
SatsaService pipeline, and serializes what the backend actually produced
into web/src/lib/mocks/fixture.json.

Every value in the fixture comes from backend code paths (ingestion,
the 16 analytical workers, risk, prioritization, recommendation, PQC
trust receipts, verification, meta-audit, validation, agent registry).
Nothing is hand-written. No review decisions are fabricated: the demo
records none, so the fixture carries none.

Usage (from the repository root, with the backend installed):

    python web/scripts/export-demo-fixture.py [--out web/src/lib/mocks/fixture.json]
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import sys
import tempfile
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _j(text, default):
    try:
        return json.loads(text) if text else default
    except (TypeError, ValueError):
        return default


def _plain(obj):
    if dataclasses.is_dataclass(obj):
        return {k: _plain(v) for k, v in dataclasses.asdict(obj).items()}
    if isinstance(obj, dict):
        return {k: _plain(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_plain(v) for v in obj]
    if isinstance(obj, bytes):
        return None
    return obj


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default=str(REPO_ROOT / "web/src/lib/mocks/fixture.json"))
    args = ap.parse_args()

    from qsmlops.database.engine import SQLiteDatabaseEngine
    from qsmlops.database.migrations import MigrationRunner
    from satsa import __version__ as satsa_version
    from satsa.analysis import ANALYTICS_VERSION
    from satsa.analysis.meta_audit import run_meta_audit
    from satsa.analysis.prioritize import prioritize_entities, prioritize_findings
    from satsa.analysis.recommend import recommend
    from satsa.analysis.risk import DIMENSION_WEIGHTS, _dimension_for
    from satsa.analysis.validate import run_validation
    from satsa.service import SatsaService
    from satsa.supervisor import DecisionContext, SupervisorEngine, list_agents
    from satsa.ui.demo import load_demo_assessment

    tmp = Path(tempfile.mkdtemp(prefix="satsa-fixture-"))
    key_dir = tmp / "keys"
    eng = SQLiteDatabaseEngine(tmp / "fixture.db")
    eng.connect()
    MigrationRunner(eng).migrate()
    svc = SatsaService(eng)
    t0 = time.time()
    demo = load_demo_assessment(svc, key_dir)
    q = eng.query_all

    entities = []
    for e in q("SELECT * FROM satsa_entities ORDER BY display_name"):
        entities.append({
            "id": e["id"], "displayName": e["display_name"], "sector": e["sector"],
            "environmentClass": e["environment_class"],
            "cohortAttributes": _j(e["cohort_attributes_json"], {}),
            "accessScope": e["access_scope"], "contentDigest": e["content_digest"],
        })

    assessments = [{
        "id": a["id"], "entityId": a["entity_id"], "periodStart": a["period_start"],
        "periodEnd": a["period_end"], "timezone": a["timezone"],
        "policyVersion": a["policy_version"], "status": a["status"],
        "contentDigest": a["content_digest"],
    } for a in q("SELECT * FROM satsa_assessments")]

    submissions = [{
        "id": s["id"], "assessmentId": s["assessment_id"], "entityId": s["entity_id"],
        "sourceSystem": s["source_system"],
        "declaredPeriodStart": s["declared_period_start"],
        "declaredPeriodEnd": s["declared_period_end"],
        "fileDigests": _j(s["file_digests_json"], {}),
        "declaredCounts": _j(s["declared_counts_json"], {}),
        "schemaName": s["schema_name"], "receivedAt": s["received_at"],
        "signatureStatus": s["signature_status"], "ingestStatus": s["ingest_status"],
        "ingestReport": _j(s["ingest_report_json"], {}),
        "snapshotDigest": s["snapshot_digest"], "contentDigest": s["content_digest"],
    } for s in q("SELECT * FROM satsa_submissions")]

    runs, verifications = [], {}
    for r in q("SELECT * FROM satsa_runs"):
        runs.append({
            "id": r["id"], "entityId": r["entity_id"], "assessmentId": r["assessment_id"],
            "snapshotDigest": r["snapshot_digest"], "codeVersion": r["code_version"],
            "analyticsVersion": r["analytics_version"], "status": r["status"],
            "startedAt": r["started_at"], "finishedAt": r["finished_at"],
            "summary": _j(r["summary_json"], {}), "error": r["error"],
            "contentDigest": r["content_digest"],
        })
        verifications[r["id"]] = {"verifiedAt": time.time(),
                                  **svc.verify_run(r["id"], key_dir)}

    jobs = [{
        "id": j["id"], "runId": j["run_id"], "workerName": j["worker_name"],
        "status": j["status"], "startedAt": j["started_at"],
        "finishedAt": j["finished_at"], "error": j["error"],
    } for j in q("SELECT * FROM satsa_jobs")]

    observations = [{
        "id": o["id"], "runId": o["run_id"], "workerName": o["worker_name"],
        "detectorVersion": o["detector_version"], "entityId": o["entity_id"],
        "assessmentId": o["assessment_id"], "scope": _j(o["scope_json"], {}),
        "state": o["state"],
    } for o in q("SELECT * FROM satsa_observations")]

    priorities = {}
    for r in runs:
        for fp in prioritize_findings(eng, r["id"]):
            priorities[fp.finding_id] = fp

    findings = []
    for f in q("SELECT f.*, o.worker_name, o.run_id, o.entity_id, o.assessment_id,"
               " o.detector_version FROM satsa_findings f"
               " JOIN satsa_observations o ON o.id = f.observation_id"
               " ORDER BY f.created_at"):
        row = dict(f)
        rec = recommend(row) if row["state"] == "signal" else None
        fp = priorities.get(row["id"])
        findings.append({
            "id": row["id"], "observationId": row["observation_id"],
            "runId": row["run_id"], "entityId": row["entity_id"],
            "assessmentId": row["assessment_id"], "workerName": row["worker_name"],
            "detectorVersion": row["detector_version"],
            "ruleOrCategory": row["rule_or_category"], "state": row["state"],
            "rationale": row["rationale"],
            "scopedSubjects": _j(row["scoped_subjects_json"], []),
            "statistic": row["statistic"], "effect": row["effect"],
            "threshold": row["threshold"],
            "confidence": _j(row["confidence_json"], None),
            "evidenceRefs": _j(row["evidence_refs_json"], []),
            "limitations": row["limitations"], "createdAt": row["created_at"],
            "contentDigest": row["content_digest"],
            "riskDimension": _dimension_for(row["rule_or_category"]),
            "severity": fp.severity if fp else None,
            "priorityScore": fp.priority_score if fp else None,
            "recommendation": _plain(rec) if rec else None,
        })

    risk_profiles = {e["id"]: svc.compute_risk(e["id"]).to_dict() for e in entities}
    entity_priorities = [_plain(p) for p in prioritize_entities(eng)]

    receipts = [{
        "id": t["id"], "subjectType": t["subject_type"], "subjectId": t["subject_id"],
        "algorithmId": t["algorithm_id"], "contentDigest": t["content_digest"],
        "publicKeyBytes": len(t["public_key"] or b""),
        "signatureBytes": len(t["signature"] or b""), "createdAt": t["created_at"],
    } for t in q("SELECT * FROM satsa_trust_receipts")]

    source_records = [{
        "id": s["id"], "submissionId": s["submission_id"], "fileDigest": s["file_digest"],
        "format": s["format"], "locator": s["locator"],
        "originalRecordDigest": s["original_record_digest"],
    } for s in q("SELECT * FROM satsa_source_records")]

    def rows(table, mapping):
        return [{k: (_j(r[c], []) if c.endswith("_json") else r[c]) for k, c in mapping.items()}
                for r in q(f"SELECT * FROM {table}")]

    security_data = {
        "alerts": rows("satsa_alerts", {
            "id": "id", "entityId": "entity_id", "assessmentId": "assessment_id",
            "submissionId": "submission_id", "nativeId": "native_id",
            "createdAt": "created_at", "nativeSeverity": "native_severity",
            "mappedSeverity": "mapped_severity", "mappedCategory": "mapped_category",
            "assetRefs": "asset_refs_json", "caseRefs": "case_refs_json",
            "acknowledgedAt": "acknowledged_at", "closedAt": "closed_at",
            "dispositionId": "disposition_id", "sourceRecordRef": "source_record_ref"}),
        "cases": rows("satsa_cases", {
            "id": "id", "entityId": "entity_id", "assessmentId": "assessment_id",
            "nativeId": "native_id", "openedAt": "opened_at", "alertRefs": "alert_refs_json",
            "ownerPseudonym": "owner_pseudonym", "status": "status", "closedAt": "closed_at",
            "closureReason": "closure_reason", "investigationRefs": "investigation_refs_json",
            "sourceRecordRef": "source_record_ref"}),
        "investigationSteps": rows("satsa_investigation_steps", {
            "id": "id", "caseId": "case_id", "actionType": "action_type",
            "performedAt": "performed_at", "sequence": "sequence",
            "analystPseudonym": "analyst_pseudonym", "noteText": "note_text"}),
        "escalations": rows("satsa_escalations", {
            "id": "id", "entityId": "entity_id", "assessmentId": "assessment_id",
            "occurredAt": "occurred_at", "alertId": "alert_id", "caseId": "case_id",
            "destinationRole": "destination_role", "trigger": "trigger", "outcome": "outcome"}),
        "dispositions": rows("satsa_dispositions", {
            "id": "id", "entityId": "entity_id", "assessmentId": "assessment_id",
            "occurredAt": "occurred_at", "alertId": "alert_id", "caseId": "case_id",
            "mappedCategory": "mapped_category", "reason": "reason",
            "approverRole": "approver_role"}),
        "assets": rows("satsa_assets", {
            "id": "id", "entityId": "entity_id", "assessmentId": "assessment_id",
            "nativeId": "native_id", "criticality": "criticality",
            "environment": "environment", "controls": "control_applicability_json"}),
    }

    agents = [_plain(a) for a in list_agents()]

    supervisor = {}
    for r in runs:
        sig = [f for f in findings if f["runId"] == r["id"] and f["state"] == "signal"]
        ctx_findings = [{"id": f["id"], "state": f["state"],
                         "rule_or_category": f["ruleOrCategory"],
                         "rationale": f["rationale"], "confidence": f["confidence"],
                         "evidence_refs": f["evidenceRefs"]} for f in sig]
        dec = SupervisorEngine().run(DecisionContext(
            vocabulary="satsa", scope={"entity_id": r["entityId"]}, run_id=r["id"],
            findings=ctx_findings, principal=None))
        supervisor[r["id"]] = _plain(dec)

    audit = run_meta_audit(eng, key_dir).to_dict()
    try:
        validation = run_validation(svc)
    except Exception as exc:  # noqa: BLE001 - report, never fabricate
        validation = {"error": str(exc)}

    fixture = {
        "meta": {
            "kind": "development-fixture",
            "notice": "Generated from a real SAT-SA backend run over the committed synthetic "
                      "demo dataset (docs/demo/submissions). Development only. Not live data.",
            "generatedAt": time.time(), "generator": "web/scripts/export-demo-fixture.py",
            "satsaVersion": satsa_version, "analyticsVersion": ANALYTICS_VERSION,
            "loadSeconds": round(time.time() - t0, 2),
            "signatureAlgorithm": "ML-DSA-65", "digestAlgorithm": "SHA3-256",
        },
        "riskWeights": dict(DIMENSION_WEIGHTS),
        "demoLoad": _plain(demo.get("results", [])),
        "entities": entities, "assessments": assessments, "submissions": submissions,
        "runs": runs, "jobs": jobs, "observations": observations, "findings": findings,
        "riskProfiles": risk_profiles, "entityPriorities": entity_priorities,
        "trustReceipts": receipts, "verifications": verifications,
        "sourceRecords": source_records, "securityData": security_data,
        "reviewDecisions": [], "agents": agents, "supervisorDecisions": supervisor,
        "metaAudit": audit, "validation": _plain(validation),
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(fixture, indent=1, default=str)
    # Never ship local machine paths (source_system embeds the submission dir).
    for prefix in (str(REPO_ROOT) + "\\", str(REPO_ROOT) + "/"):
        text = text.replace(json.dumps(prefix)[1:-1], "")
    out.write_text(text, encoding="utf-8")
    eng.close()
    print(f"wrote {out} ({out.stat().st_size // 1024} KB): {len(entities)} entities, "
          f"{len(findings)} findings, {len(receipts)} receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
