"""Supervisory Audit & Compliance (Meta-Audit): sweeps the *whole*
database — every signal finding across every run, every review
decision across every finding — verifying each one's provenance and
trust coverage, rather than the on-demand single-run check
``RunService.verify_run`` already provides.

This is deliberately not an ``AnalyticalWorker``: it doesn't operate
on one entity's ``CanonicalDataset`` for one run — it's a
cross-cutting sweep over persisted state, the same category of
operation as ``sat-sa doctor`` or ``verify_run`` itself, not a
per-run detector. Reuses ``TrustService.verify_subject`` and
``ReviewService.verify_binding`` directly; no new verification logic
is invented here, only the sweep that calls them exhaustively instead
of for one run/finding at a time.

Honesty note: "continuously verifies" in the roadmap sense means this
function is meant to be run on a schedule (e.g. a periodic
``sat-sa audit`` invocation) — this module does not itself implement
a scheduler or daemon; that is an operational deployment decision,
not something to fabricate here.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class MetaAuditReport:
    findings_checked: int = 0
    findings_ok: int = 0
    findings_failed: list = field(default_factory=list)  # [{finding_id, reason}]
    reviews_checked: int = 0
    reviews_ok: int = 0
    reviews_failed: list = field(default_factory=list)  # [{finding_id, review_id, reason}]
    runs_checked: int = 0
    runs_ok: int = 0
    runs_failed: list = field(default_factory=list)  # [{run_id, reason}]
    # Phase P26 addendum: cross-checks satsa_review_decisions against
    # its independent hash-chained ledger for deletion/reordering —
    # distinct from reviews_failed above, which catches in-place
    # content tampering via verify_binding. See
    # satsa.analysis.review.ReviewService.verify_ledger_integrity.
    ledger_integrity: Optional[dict] = None

    @property
    def finding_coverage(self) -> float | None:
        return (self.findings_ok / self.findings_checked
                if self.findings_checked else None)

    @property
    def review_coverage(self) -> float | None:
        return (self.reviews_ok / self.reviews_checked
                if self.reviews_checked else None)

    @property
    def run_coverage(self) -> float | None:
        return (self.runs_ok / self.runs_checked
                if self.runs_checked else None)

    @property
    def fully_compliant(self) -> bool:
        ledger_ok = (self.ledger_integrity is None
                    or self.ledger_integrity.get("fully_consistent", False))
        return (not self.findings_failed and not self.reviews_failed
                and not self.runs_failed and ledger_ok)

    def to_dict(self) -> dict:
        return {
            "findings_checked": self.findings_checked,
            "findings_ok": self.findings_ok,
            "findings_failed": list(self.findings_failed),
            "finding_coverage": self.finding_coverage,
            "reviews_checked": self.reviews_checked,
            "reviews_ok": self.reviews_ok,
            "reviews_failed": list(self.reviews_failed),
            "review_coverage": self.review_coverage,
            "runs_checked": self.runs_checked,
            "runs_ok": self.runs_ok,
            "runs_failed": list(self.runs_failed),
            "run_coverage": self.run_coverage,
            "ledger_integrity": self.ledger_integrity,
            "fully_compliant": self.fully_compliant,
        }


def run_meta_audit(engine, trust_key_dir: Path) -> MetaAuditReport:
    """Sweep every run, every signal finding, and every review
    decision currently in the database and verify each one's trust
    receipt / provenance binding. Returns a report an operator or a
    scheduled job can act on — never partial or best-effort silently;
    every checked record either passes or is listed in the relevant
    ``*_failed`` list with a reason."""
    from satsa.analysis.canonical import live_finding_digest, live_run_seed
    from satsa.analysis.review import ReviewService, build_review_decision_ledger
    from satsa.analysis.trust import TrustService

    trust = TrustService(engine, Path(trust_key_dir))
    report = MetaAuditReport()

    # ---- runs ----
    run_rows = engine.query_all(
        "SELECT * FROM satsa_runs WHERE status IN ('completed','partial')")
    for r in run_rows:
        report.runs_checked += 1
        digest = live_run_seed(dict(r))
        ok, reason = trust.verify_subject("run", r["id"], digest)
        if ok:
            report.runs_ok += 1
        else:
            report.runs_failed.append({"run_id": r["id"], "reason": reason})

    # ---- findings ----
    finding_rows = engine.query_all(
        "SELECT * FROM satsa_findings WHERE state='signal'")
    for f in finding_rows:
        report.findings_checked += 1
        digest = live_finding_digest(dict(f))
        ok, reason = trust.verify_subject("finding", f["id"], digest)
        if ok:
            report.findings_ok += 1
        else:
            report.findings_failed.append({"finding_id": f["id"], "reason": reason})

    # ---- review-decision bindings ----
    review_svc = ReviewService(engine)
    finding_ids_with_reviews = {
        r["finding_id"] for r in engine.query_all(
            "SELECT DISTINCT finding_id FROM satsa_review_decisions")}
    for finding_id in finding_ids_with_reviews:
        f_row = engine.query_one(
            "SELECT * FROM satsa_findings WHERE id=?", (finding_id,))
        if f_row is None:
            report.reviews_checked += 1
            report.reviews_failed.append({
                "finding_id": finding_id,
                "reason": "the finding this decision was recorded against "
                          "no longer exists in satsa_findings",
            })
            continue
        bindings = review_svc.verify_binding(finding_id, dict(f_row))
        for b in bindings:
            report.reviews_checked += 1
            if b["ok"]:
                report.reviews_ok += 1
            else:
                report.reviews_failed.append({
                    "finding_id": finding_id, "review_id": b["review_id"],
                    "reason": b["reason"],
                })

    # ---- review-decision ledger integrity (deletion/reordering) ----
    ledger = build_review_decision_ledger(trust_key_dir)
    ledger_review_svc = ReviewService(engine, decision_ledger=ledger)
    report.ledger_integrity = ledger_review_svc.verify_ledger_integrity()

    return report
