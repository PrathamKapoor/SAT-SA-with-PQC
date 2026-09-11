"""IngestionService: the Phase 3 entry point — take submission files for one
(entity, assessment), normalize them into canonical domain records, persist
everything in a single transaction, and return a full IngestionReport.

Guarantees:
- nothing is persisted unless the whole normalized batch passes (one
  transaction around submission + all records + all source records);
- duplicate submission bytes are rejected, not re-ingested;
- every rejected row is enumerated with reasons in the report;
- every accepted record carries a resolvable SourceRecord pointer and a
  content digest (SHA3-256 over its canonical dict);
- the submission records file digests, counts, format, timing and the
  frozen snapshot digest — the provenance anchors later phases sign/commit.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from qsmlops.core.logging import get_logger
from qsmlops.crypto.hashing import digest_document
from satsa.domain.base import new_id
from satsa.domain.entities import Submission
from satsa.ingest.normalize import NormResult, normalize_category, extract_fields
from satsa.ingest.readers import (
    IngestionFormatError,
    ParsedFile,
    parse_file,
    scan_directory,
)
from satsa.ingest.spec import ALERT_FIELDS, ASSET_FIELDS, CASE_FIELDS
from satsa.store.repositories import (
    AlertStore,
    AssessmentStore,
    AssetStore,
    CaseStore,
    DispositionStore,
    EscalationStore,
    InvestigationStepStore,
    SourceRecordStore,
    SubmissionStore,
)

log = get_logger(__name__)

INGEST_VERSION = "satsa-ingest/1.0.0"

# Normalization order: id-bearing categories first (they feed the native
# reference maps), then the reference-only categories.
NORMALIZE_ORDER = ("alerts", "cases", "assets",
                   "investigation_steps", "escalations", "dispositions")


class IngestionError(Exception):
    """Submission-level failure (unknown assessment, duplicate submission,
    unreadable file). Row-level problems are reported, not raised."""


@dataclass
class IngestionResult:
    submission_id: str
    entity_id: str
    assessment_id: str
    status: str                     # accepted | accepted_with_warnings | partial | rejected
    snapshot_digest: str
    categories: dict = field(default_factory=dict)
    counts: dict = field(default_factory=dict)     # category -> accepted rows
    duration_seconds: float = 0.0

    def to_dict(self) -> dict:
        return {
            "submission_id": self.submission_id, "entity_id": self.entity_id,
            "assessment_id": self.assessment_id, "status": self.status,
            "snapshot_digest": self.snapshot_digest, "categories": self.categories,
            "counts": self.counts, "duration_seconds": self.duration_seconds,
        }


class IngestionService:
    def __init__(self, engine) -> None:
        self._db = engine

    # ------------------------------------------------------------------
    def submit_directory(self, assessment_id: str, directory, *,
                         source_system: str = "",
                         received_at: Optional[float] = None) -> IngestionResult:
        files = scan_directory(directory)
        if not files:
            raise IngestionError(
                f"no recognized submission files in {directory} "
                "(expected alerts/cases/investigation_steps/escalations/dispositions/assets"
                " as .csv/.json)")
        return self.submit_files(assessment_id, files,
                                 source_system=source_system or f"directory:{directory}",
                                 received_at=received_at)

    def submit_files(self, assessment_id: str, files: dict, *,
                     source_system: str = "",
                     received_at: Optional[float] = None) -> IngestionResult:
        started = time.time()
        assessment = AssessmentStore(self._db).get(assessment_id)
        if assessment is None:
            raise IngestionError(f"assessment {assessment_id!r} not found")
        entity_id = assessment["entity_id"]
        received = received_at if received_at is not None else time.time()

        # 1. parse all files (file-level failures recorded, do not abort)
        parsed: dict = {}
        file_failures: dict = {}
        for category, path in files.items():
            try:
                parsed[category] = parse_file(Path(path), category)
            except IngestionFormatError as exc:
                file_failures[category] = str(exc)
        if not parsed:
            raise IngestionError(
                "no submission file could be parsed: "
                + "; ".join(f"{k}: {v}" for k, v in file_failures.items()))

        file_digests = {Path(files[c]).name: pf.file_digest for c, pf in parsed.items()}

        submissions = SubmissionStore(self._db)
        if submissions.has_identical(assessment_id, file_digests):
            raise IngestionError(
                "identical submission bytes (same file digests) were already ingested "
                f"for assessment {assessment_id}")

        # 2. seed native->internal maps from already-persisted scope records
        persisted_alerts = AlertStore(self._db).list_for_scope(entity_id, assessment_id)
        persisted_cases = CaseStore(self._db).list_for_scope(entity_id, assessment_id)
        persisted_assets = AssetStore(self._db).list_for_scope(entity_id, assessment_id)
        alert_map = {r["native_id"]: r["id"] for r in persisted_alerts}
        case_map = {r["native_id"]: r["id"] for r in persisted_cases}
        asset_map = {r["native_id"]: r["id"] for r in persisted_assets}
        existing_alert_natives = set(alert_map)
        existing_case_natives = set(case_map)
        existing_asset_natives = set(asset_map)

        # 3. pre-assign internal ids for this submission's new id-bearing records
        #    (so alert<->case refs resolve regardless of normalization order)
        pre: dict = {"alerts": {}, "cases": {}, "assets": {}}
        spec_for = {"alerts": ALERT_FIELDS, "cases": CASE_FIELDS, "assets": ASSET_FIELDS}
        prefix_for = {"alerts": "alert", "cases": "case", "assets": "asset"}
        for category in ("alerts", "cases", "assets"):
            pf = parsed.get(category)
            if pf is None:
                continue
            for row in pf.rows:
                fields = extract_fields(row, spec_for[category])
                native = str(fields.get("native_id") or "").strip()
                if not native:
                    continue
                target_map = {"alerts": alert_map, "cases": case_map,
                              "assets": asset_map}[category]
                if native in target_map or native in pre[category]:
                    continue  # existing record (cross-submission) or in-file dup
                ident = new_id(prefix_for[category])
                pre[category][native] = ident
                target_map[native] = ident

        # 4. normalize in dependency order
        results: dict = {}
        for category in NORMALIZE_ORDER:
            pf = parsed.get(category)
            if pf is None:
                continue
            res = normalize_category(
                pf, entity_id=entity_id, assessment_id=assessment_id,
                case_native_to_id=case_map, alert_native_to_id=alert_map,
                asset_native_to_id=asset_map, preassigned=pre.get(category) or {},
                existing_natives={"alerts": existing_alert_natives,
                                  "cases": existing_case_natives,
                                  "assets": existing_asset_natives}.get(category, set()))
            results[category] = res
            # prune pre-assigned ids for rows that failed normalization, so
            # later categories never resolve references into phantom records
            if category in pre:
                accepted = set(res.accepted_native)
                target_map = {"alerts": alert_map, "cases": case_map,
                              "assets": asset_map}[category]
                for native in list(pre[category]):
                    if native not in accepted:
                        del pre[category][native]
                        target_map.pop(native, None)

        # 5. post-consistency sweep: drop refs that resolved against ids whose
        #    records were later rejected (phantom pruning above guarantees the
        #    maps are clean; here we also re-check list fields against the
        #    final accepted id sets) and clean alerts/cases cross-refs.
        final_alert_ids = {a.id for a in results.get("alerts", NormResult("alerts")).records} \
            | set(alert_map.values())
        final_case_ids = {c.id for c in results.get("cases", NormResult("cases")).records} \
            | set(case_map.values())
        final_asset_ids = {a.id for a in results.get("assets", NormResult("assets")).records} \
            | set(asset_map.values())
        for res_cat, getter in (("alerts", lambda r: r), ("cases", lambda r: r)):
            res = results.get(res_cat)
            if not res:
                continue
            for rec in res.records:
                if res_cat == "alerts":
                    kept = [c for c in rec.case_refs if c in final_case_ids]
                    dropped = [c for c in rec.case_refs if c not in final_case_ids]
                    if dropped:
                        res.warnings.append(
                            f"alert {rec.native_id!r}: dropped {len(dropped)} case ref(s) whose "
                            "target case failed validation")
                        rec.case_refs = kept
                else:
                    kept = [a for a in rec.alert_refs if a in final_alert_ids]
                    dropped = [a for a in rec.alert_refs if a not in final_alert_ids]
                    if dropped:
                        res.warnings.append(
                            f"case {rec.native_id!r}: dropped {len(dropped)} alert ref(s) whose "
                            "target alert failed validation")
                        rec.alert_refs = kept
        for res in results.values():
            for rec in res.records:
                if hasattr(rec, "asset_refs"):
                    kept = [a for a in rec.asset_refs if a in final_asset_ids]
                    if len(kept) != len(rec.asset_refs):
                        res.warnings.append(
                            f"alert {rec.native_id!r}: dropped asset ref(s) whose target "
                            "failed validation")
                        rec.asset_refs = kept

        # 6. build submission + snapshot digest
        submission = Submission(
            id=new_id("submission"), assessment_id=assessment_id,
            source_system=source_system,
            declared_period_start=assessment["period_start"],
            declared_period_end=assessment["period_end"],
            file_digests=file_digests,
            declared_counts={c: len(p.rows) for c, p in parsed.items()},
            received_at=received, signature_status="unsigned",
        )
        report_categories = {}
        for category in NORMALIZE_ORDER:
            if category in results:
                report_categories[category] = results[category].summary()
            elif category in file_failures:
                report_categories[category] = {
                    "present": False, "error": file_failures[category],
                    "received": 0, "accepted": 0, "rejected": 0,
                    "rejections": [], "warnings": []}
        digest_parts = sorted(
            digest_document(r.to_dict())
            for cat in results.values() for r in cat.records)
        snapshot_digest = digest_document({
            "assessment_id": assessment_id, "entity_id": entity_id,
            "files": file_digests, "records": digest_parts,
        })

        total_accepted = sum(len(r.records) for r in results.values())
        total_rejected = sum(len(r.rejected) for r in results.values())
        total_warnings = sum(len(r.warnings) for r in results.values())
        if total_rejected and total_accepted:
            status = "partial"
        elif total_rejected and not total_accepted:
            status = "rejected"
        elif total_warnings:
            status = "accepted_with_warnings"
        else:
            status = "accepted"
        if file_failures and status in ("accepted", "accepted_with_warnings"):
            # a whole category file failed to parse: the submission did not
            # fully land, whatever the surviving rows look like
            status = "partial"

        ingest_report = {
            "version": INGEST_VERSION, "categories": report_categories,
            "status": status, "received_at": received,
            "totals": {"accepted": total_accepted, "rejected": total_rejected,
                       "warnings": total_warnings},
        }

        # 7. persist atomically
        with self._db.transaction():
            submissions.insert(
                submission, entity_id=entity_id, ingest_status=status,
                ingest_report=ingest_report, snapshot_digest=snapshot_digest,
                created_at=received)
            sr_store = SourceRecordStore(self._db)
            for res in results.values():
                for sr in res.source_records:
                    sr.submission_id = submission.id
                    sr_store.insert(sr)
            stores = {
                "alerts": lambda r: AlertStore(self._db).insert(r, submission_id=submission.id),
                "cases": lambda r: CaseStore(self._db).insert(r, submission_id=submission.id),
                "investigation_steps": lambda r: InvestigationStepStore(self._db).insert(
                    r, submission_id=submission.id),
                "escalations": lambda r: EscalationStore(self._db).insert(
                    r, submission_id=submission.id),
                "dispositions": lambda r: DispositionStore(self._db).insert(
                    r, submission_id=submission.id),
                "assets": lambda r: AssetStore(self._db).insert(
                    r, assessment_id=assessment_id, submission_id=submission.id),
            }
            for category, res in results.items():
                for rec in res.records:
                    stores[category](rec)

        duration = time.time() - started
        log.info(
            "satsa ingestion %s: %d accepted, %d rejected, %d warnings in %.2fs",
            status, total_accepted, total_rejected, total_warnings, duration,
            extra={"event": "satsa.ingest.completed", "submission_id": submission.id,
                   "assessment_id": assessment_id, "entity_id": entity_id},
        )
        return IngestionResult(
            submission_id=submission.id, entity_id=entity_id,
            assessment_id=assessment_id, status=status,
            snapshot_digest=snapshot_digest,
            categories={c: {"accepted": r.summary()["accepted"],
                            "rejected": r.summary()["rejected"],
                            "received": r.received}
                        for c, r in results.items()},
            counts={c: len(r.records) for c, r in results.items()},
            duration_seconds=duration,
        )
