"""Controlled integrity experiment over a real SAT-SA review workflow.

The experiment creates an isolated SQLite tenant and synthetic submission,
executes the existing worker, records an authorized decision, finalizes with
TRUST-SAT, and applies reversible one-at-a-time mutations to scratch records.
It does not access configured SaaS databases or production artifacts.
"""

from __future__ import annotations

import io
import json
import time
from pathlib import Path
from time import perf_counter
from typing import Any

_ALERTS = b"native_id,created_at,severity\nA1,1735689700,critical\n"


def run_trust_integrity_experiment(scratch_dir: Path) -> dict[str, Any]:
    """Run valid-control verification and eight isolated mutation checks."""
    from qsmlops.database.engine import SQLiteDatabaseEngine
    from qsmlops.database.migrations import MigrationRunner
    from qsmlops.evidence.ledger import EvidenceLedger
    from qsmlops.security.audit.service import AuditService
    from satsa.analysis.execution import (
        AnalysisExecutionService,
        AnalysisExecutionWorker,
    )
    from satsa.analysis.trust import TrustService
    from satsa.submissions import LocalArtifactStorage, SubmissionService
    from satsa.tenancy import TenantAdministration, TenantRepository

    root = Path(scratch_dir)
    root.mkdir(parents=True, exist_ok=True)
    engine = SQLiteDatabaseEngine(root / "research-integrity.sqlite3")
    engine.connect()
    MigrationRunner(engine).migrate()
    try:
        admin = TenantAdministration(engine)
        organization_id = admin.create_organization("Research synthetic tenant")
        now = time.time()
        engine.execute(
            "INSERT INTO identities (identity_id,kind,name,owner,status,created_at,updated_at)"
            " VALUES (?,?,?,?,?,?,?)",
            (
                "research-analyst",
                "human",
                "Research analyst",
                "research",
                "active",
                now,
                now,
            ),
        )
        analyst_id = admin.create_user("research-analyst", "analyst@example.test")
        admin.add_membership(organization_id, analyst_id, "satsa_analyst")
        tenant = TenantRepository(engine, organization_id, analyst_id)
        entity_id = tenant.create_entity("Synthetic research entity", sector="defence")
        assessment_id = tenant.create_assessment(entity_id, 1735689600.0, 1738281600.0)
        audit = AuditService(EvidenceLedger(root / "audit.jsonl"), database=engine)
        submissions = SubmissionService(
            engine,
            organization_id,
            analyst_id,
            storage=LocalArtifactStorage(root / "artifacts"),
            audit=audit,
        )
        submission_id = submissions.create_submission(
            assessment_id, idempotency_key="research-integrity-submission"
        )
        version_id = submissions.create_version(
            submission_id, idempotency_key="research-integrity-version"
        )
        submissions.upload(
            version_id,
            category="alerts",
            stream=io.BytesIO(_ALERTS),
            filename="synthetic-alerts.csv",
            content_type="text/csv",
            idempotency_key="research-integrity-alerts",
        )
        submissions.complete_uploads(version_id)
        validation = submissions.validate(version_id)
        if validation.get("status") != "valid":
            raise RuntimeError("controlled integrity submission failed validation")

        service = AnalysisExecutionService(
            engine, organization_id, analyst_id, audit=audit
        )
        run = service.create_run(
            version_id, idempotency_key="research-integrity-run", review_required=True
        )
        keys = root / "signing-keys"
        worker = AnalysisExecutionWorker(
            engine,
            worker_id="research-integrity-worker",
            audit=audit,
            trust_key_dir=str(keys),
        )
        if worker.run_once() != "awaiting_review":
            raise RuntimeError("analysis did not reach supervisory review")

        supervisor_identity = "research-supervisor"
        now = time.time()
        engine.execute(
            "INSERT INTO identities (identity_id,kind,name,owner,status,created_at,updated_at)"
            " VALUES (?,?,?,?,?,?,?)",
            (
                supervisor_identity,
                "human",
                "Research supervisor",
                "research",
                "active",
                now,
                now,
            ),
        )
        supervisor_id = admin.create_user(
            supervisor_identity, "supervisor@example.test"
        )
        admin.add_membership(organization_id, supervisor_id, "satsa_supervisor")
        review = AnalysisExecutionService(
            engine, organization_id, supervisor_id, audit=audit
        )
        decision = review.decide(
            run["run_id"],
            action="confirm",
            reason="Controlled integrity experiment review",
        )
        if worker.run_once() not in {"completed", "partial"}:
            raise RuntimeError("reviewed analysis did not finalize")

        trust = TrustService(engine, keys, organization_id=organization_id)
        valid, valid_reason = trust.verify_finalization(run["run_id"], audit)
        if not valid:
            raise RuntimeError(f"valid control failed verification: {valid_reason}")

        findings = service.list_findings(run["run_id"])
        evidence = service.list_evidence(run["run_id"])
        recommendations = service.list_recommendations(run["run_id"])
        source_ids = {row["source_record_id"] for row in evidence}
        recommendation_finding_ids = {
            row["finding_id"] for row in recommendations if row.get("finding_id")
        }
        evidence_ref_count = 0
        resolved_evidence_ref_count = 0
        findings_with_recommendation = 0
        findings_with_resolved_refs = 0
        for finding in findings:
            try:
                refs = json.loads(finding.get("evidence_refs_json") or "[]")
            except (TypeError, ValueError):
                refs = []
            refs = [
                ref
                for ref in refs
                if isinstance(ref, str) and ref.startswith("srcrec_")
            ]
            evidence_ref_count += len(refs)
            resolved = sum(ref in source_ids for ref in refs)
            resolved_evidence_ref_count += resolved
            if refs and resolved == len(refs):
                findings_with_resolved_refs += 1
            if finding["id"] in recommendation_finding_ids:
                findings_with_recommendation += 1
        decision_exists = service.get_review_decision(run["run_id"]) is not None
        traceability = {
            "unit": "finding within one controlled synthetic workflow",
            "findings": len(findings),
            "findings_with_all_evidence_references_resolved": findings_with_resolved_refs,
            "finding_evidence_coverage": (
                findings_with_resolved_refs / len(findings) if findings else None
            ),
            "evidence_references": evidence_ref_count,
            "resolved_evidence_references": resolved_evidence_ref_count,
            "evidence_reference_coverage": (
                resolved_evidence_ref_count / evidence_ref_count
                if evidence_ref_count
                else None
            ),
            "findings_with_recommendation": findings_with_recommendation,
            "recommendation_coverage": (
                findings_with_recommendation / len(findings) if findings else None
            ),
            "authorized_decision_exists": decision_exists,
            "trust_receipt_verifies": valid,
            "interpretation": (
                "descriptive measurement on one controlled run; not a human review study"
            ),
        }

        mutations: list[dict[str, Any]] = []

        def mutate_sql(
            name: str, select: str, update: str, parameter: tuple[Any, ...]
        ) -> None:
            row = engine.query_one(select, (run["run_id"],))
            if row is None:
                raise RuntimeError(f"integrity experiment lacks {name} record")
            original = row["value"]
            engine.execute(update, (*parameter, run["run_id"]))
            started = perf_counter()
            verified, reason = trust.verify_finalization(run["run_id"], audit)
            elapsed_ms = (perf_counter() - started) * 1000
            engine.execute(update, (original, run["run_id"]))
            mutations.append(
                {
                    "mutation": name,
                    "detected": not verified,
                    "verification_outcome": "tampered" if not verified else "verified",
                    "failure_category": reason if not verified else None,
                    "verification_ms": round(elapsed_ms, 4),
                }
            )
            if verified:
                raise RuntimeError(f"TRUST-SAT did not detect {name} mutation")

        mutate_sql(
            "decision",
            "SELECT action AS value FROM satsa_run_review_decisions WHERE run_id=?",
            "UPDATE satsa_run_review_decisions SET action=? WHERE run_id=?",
            ("dismiss",),
        )
        mutate_sql(
            "finding",
            "SELECT rationale AS value FROM satsa_findings WHERE observation_id IN"
            " (SELECT id FROM satsa_observations WHERE run_id=?) ORDER BY id LIMIT 1",
            "UPDATE satsa_findings SET rationale=? WHERE id=(SELECT f.id FROM satsa_findings f"
            " JOIN satsa_observations o ON o.id=f.observation_id WHERE o.run_id=? ORDER BY f.id LIMIT 1)",
            ("controlled mutation",),
        )
        mutate_sql(
            "risk",
            "SELECT profile_json AS value FROM satsa_run_risk WHERE run_id=?",
            "UPDATE satsa_run_risk SET profile_json=? WHERE run_id=?",
            ("{}",),
        )
        mutate_sql(
            "recommendation",
            "SELECT recommendation_json AS value FROM satsa_run_recommendations"
            " WHERE run_id=? ORDER BY id LIMIT 1",
            "UPDATE satsa_run_recommendations SET recommendation_json=? WHERE id=(SELECT id"
            " FROM satsa_run_recommendations WHERE run_id=? ORDER BY id LIMIT 1)",
            ("{}",),
        )
        mutate_sql(
            "source_provenance",
            "SELECT locator AS value FROM satsa_source_records"
            " WHERE version_id=(SELECT submission_version_id FROM satsa_run_context"
            " WHERE run_id=?) ORDER BY id LIMIT 1",
            "UPDATE satsa_source_records SET locator=? WHERE id=(SELECT id FROM satsa_source_records"
            " WHERE version_id=(SELECT submission_version_id FROM satsa_run_context"
            " WHERE run_id=?) ORDER BY id LIMIT 1)",
            ("controlled-mutation",),
        )
        mutate_sql(
            "canonical_payload",
            "SELECT canonical_json AS value FROM satsa_trust_finalizations"
            " WHERE run_id=?",
            "UPDATE satsa_trust_finalizations SET canonical_json=? WHERE run_id=?",
            ("{}",),
        )
        mutate_sql(
            "receipt_signature",
            "SELECT signature AS value FROM satsa_trust_receipts"
            " WHERE subject_type='supervisory_finalization' AND subject_id=(SELECT id"
            " FROM satsa_trust_finalizations WHERE run_id=?)",
            "UPDATE satsa_trust_receipts SET signature=? WHERE subject_type="
            "'supervisory_finalization' AND subject_id=(SELECT id FROM"
            " satsa_trust_finalizations WHERE run_id=?)",
            (b"controlled-mutation",),
        )

        ledger_path = audit._ledger.path
        original_ledger = ledger_path.read_bytes()
        lines = original_ledger.decode("utf-8").splitlines()
        if not lines:
            raise RuntimeError("integrity experiment audit ledger is empty")
        last = json.loads(lines[-1])
        last["prev_hash"] = "0" * 64
        lines[-1] = json.dumps(last, sort_keys=True, separators=(",", ":"))
        ledger_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        started = perf_counter()
        ledger_verified, ledger_reason = trust.verify_finalization(run["run_id"], audit)
        ledger_ms = (perf_counter() - started) * 1000
        ledger_path.write_bytes(original_ledger)
        mutations.append(
            {
                "mutation": "ledger_chain",
                "detected": not ledger_verified,
                "verification_outcome": "tampered"
                if not ledger_verified
                else "verified",
                "failure_category": ledger_reason if not ledger_verified else None,
                "verification_ms": round(ledger_ms, 4),
            }
        )
        if ledger_verified:
            raise RuntimeError("TRUST-SAT did not detect ledger mutation")

        final_ok, final_reason = trust.verify_finalization(run["run_id"], audit)
        if not final_ok:
            raise RuntimeError(f"restored control failed verification: {final_reason}")
        return {
            "status": "completed",
            "experiment": "trust-sat-controlled-mutation-v1",
            "data_origin": "synthetic",
            "valid_control": {"verified": valid, "reason": valid_reason},
            "mutations": mutations,
            "traceability": traceability,
            "workflow": {
                "organization_id": organization_id,
                "submission_version_id": version_id,
                "analysis_run_id": run["run_id"],
                "decision_id": decision["id"],
                "decision_action": decision["action"],
                "finalization_restored_and_verified": final_ok,
            },
            "limitations": [
                "One isolated SQLite run and one mutation per category; this is a controlled integrity check, not a population detection-rate estimate.",
                "The receipt establishes integrity of recorded canonical state, not truth of real-world evidence.",
                "The signing key and audit ledger are local scratch artifacts, not an external trust anchor.",
            ],
        }
    finally:
        engine.close()
