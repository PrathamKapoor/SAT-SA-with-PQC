"""Calibration workflow: propose -> test against labeled data ->
supervisor approval -> versioned deployment.

This is the N17 extension the user's proposed agent taxonomy asked
for: today ``satsa.analysis.validate`` (the Validation Agent) can only
*measure* precision/recall for whatever thresholds a worker already
has; nothing in the codebase before this phase let anyone change a
worker's detection thresholds through a governed process. This module
adds that process without inventing a new detector engine — every
"test" reuses the existing worker contract
(``satsa.contracts.worker.AnalyticalWorker.evaluate``) and the
existing scoring function (``satsa.analysis.validate.evaluate_layer``).

The workflow has four steps, and nothing skips ahead:

1. **propose** — a named worker + a candidate threshold change + a
   rationale. Nothing about production behaviour changes yet.
2. **test** — run the *currently-deployed* worker instance and the
   *candidate* worker instance (identical dataset, identical run
   context) and score each one's emitted rule families against the
   same expert-labeled ground truth via ``evaluate_layer``. A
   proposal is graded against real labels, never against its own
   output — self-grading would make every proposal look like an
   improvement.
3. **decide** — a principal holding ``calibration.approve``
   (``satsa_supervisor``/``satsa_admin`` — the same terminal-authority
   restriction ``decision.record`` already carries; see
   ``qsmlops/security/permissions/model.py``) approves or rejects the
   *tested* proposal. This module does not itself enforce the
   permission check — mirroring ``satsa.analysis.review.ReviewService``,
   permission enforcement is the caller's (UI route / CLI command)
   responsibility via ``satsa.security.require``; this module only
   records who decided and requires the decision to be explicit.
4. **deploy** — an *approved* proposal is recorded as a new, versioned
   entry in the append-only ``CalibrationLedger``. Deployment here
   means the proposed thresholds become the ledger's "latest deployed"
   record for that worker, retrievable via
   ``CalibrationLedger.latest_deployed()`` — a caller can pass that
   dict into the worker's own ``*Thresholds`` dataclass and hand it to
   ``RunService.run(...)`` the same way any other override is passed
   today. This module deliberately does NOT make ``RunService`` load
   the latest deployed calibration automatically on every run — silently
   changing what future runs detect without an explicit, reviewable
   call site would undermine the "nothing changes production behaviour
   without a first fetch/pass through the caller" property everywhere
   else in this codebase (see e.g. ``ReviewService.verify_binding``).

Nothing here is destructive: every state transition is appended, never
overwritten in place (mirrors ``satsa_review_decisions``'s append-only
audit trail), so a proposal's full propose -> test -> decide -> deploy
history is always reconstructable from the ledger file.
"""
from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional

from satsa.analysis.validate import evaluate_layer
from satsa.contracts.worker import AnalyticalWorker, RunContext, SnapshotRef

PROPOSED = "proposed"
TESTED = "tested"
APPROVED = "approved"
REJECTED = "rejected"
DEPLOYED = "deployed"
STATUSES = (PROPOSED, TESTED, APPROVED, REJECTED, DEPLOYED)


@dataclass
class CalibrationProposal:
    id: str
    worker_name: str
    layer: str                          # rule_or_category prefix this proposal targets
    proposed_thresholds: dict
    rationale: str
    proposer: str
    status: str = PROPOSED
    baseline_metric: Optional[dict] = None
    proposed_metric: Optional[dict] = None
    decided_by: str = ""
    decided_at: Optional[float] = None
    decision_rationale: str = ""
    deployed_version: str = ""
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "CalibrationProposal":
        return cls(**d)


def propose_calibration(*, proposal_id: str, worker_name: str, layer: str,
                        proposed_thresholds: dict, rationale: str,
                        proposer: str) -> CalibrationProposal:
    """Step 1: record a candidate threshold change. Does not touch
    production behaviour."""
    if not rationale.strip():
        raise ValueError("a calibration proposal requires a non-empty rationale")
    if not proposed_thresholds:
        raise ValueError("a calibration proposal requires at least one "
                          "proposed threshold value")
    return CalibrationProposal(
        id=proposal_id, worker_name=worker_name, layer=layer,
        proposed_thresholds=dict(proposed_thresholds),
        rationale=rationale, proposer=proposer,
    )


def run_calibration_test(
    proposal: CalibrationProposal, *,
    baseline_worker: AnalyticalWorker,
    candidate_worker: AnalyticalWorker,
    snapshot: SnapshotRef,
    dataset,
    baselines: list,
    run_context: RunContext,
    expert_labels: list,
) -> CalibrationProposal:
    """Step 2: run the currently-deployed worker and the candidate
    worker over the same dataset, score each against the same
    expert-labeled ground truth via ``evaluate_layer``, and record the
    before/after ``LayerMetric``.

    Returns a *new* ``CalibrationProposal`` (does not mutate the
    input) with ``status == 'tested'``. Raises ``ValueError`` if the
    proposal is not currently in ``'proposed'`` state — a proposal is
    tested exactly once from that state; re-testing an already-tested
    proposal would silently overwrite the metrics a decision may
    already be based on.
    """
    if proposal.status != PROPOSED:
        raise ValueError(
            f"proposal {proposal.id!r} is not in 'proposed' state "
            f"(status={proposal.status!r}); it has already been tested")

    baseline_batch = baseline_worker.evaluate(
        snapshot, dataset, baselines, None, run_context)
    candidate_batch = candidate_worker.evaluate(
        snapshot, dataset, baselines, None, run_context)

    baseline_families = sorted({f.rule_or_category for f in baseline_batch.findings})
    candidate_families = sorted({f.rule_or_category for f in candidate_batch.findings})

    layer_labels = [l for l in expert_labels if l.layer == proposal.layer]
    baseline_metric = evaluate_layer(proposal.layer, baseline_families, layer_labels)
    candidate_metric = evaluate_layer(proposal.layer, candidate_families, layer_labels)

    return CalibrationProposal(
        id=proposal.id, worker_name=proposal.worker_name, layer=proposal.layer,
        proposed_thresholds=dict(proposal.proposed_thresholds),
        rationale=proposal.rationale, proposer=proposal.proposer,
        status=TESTED,
        baseline_metric=baseline_metric.to_dict(),
        proposed_metric=candidate_metric.to_dict(),
        created_at=proposal.created_at,
    )


def decide_calibration_proposal(
    proposal: CalibrationProposal, *, decided_by: str, approve: bool,
    rationale: str,
) -> CalibrationProposal:
    """Step 3: an explicit human decision on a *tested* proposal.

    Permission enforcement (``calibration.approve``) is the caller's
    responsibility — see this module's docstring. ``decided_by`` is
    recorded faithfully, the same trust boundary
    ``ReviewService.record`` already documents for
    ``principal_identity_id``.
    """
    if proposal.status != TESTED:
        raise ValueError(
            f"proposal {proposal.id!r} is not in 'tested' state "
            f"(status={proposal.status!r}); it must be tested against "
            "labeled data before it can be decided")
    if not rationale.strip():
        raise ValueError("a calibration decision requires a non-empty rationale")
    return CalibrationProposal(
        id=proposal.id, worker_name=proposal.worker_name, layer=proposal.layer,
        proposed_thresholds=dict(proposal.proposed_thresholds),
        rationale=proposal.rationale, proposer=proposal.proposer,
        status=APPROVED if approve else REJECTED,
        baseline_metric=proposal.baseline_metric,
        proposed_metric=proposal.proposed_metric,
        decided_by=decided_by, decided_at=time.time(),
        decision_rationale=rationale,
        created_at=proposal.created_at,
    )


def deploy_calibration_proposal(
    proposal: CalibrationProposal, *, version: str,
) -> CalibrationProposal:
    """Step 4: record an *approved* proposal as deployed under
    ``version``. See this module's docstring for exactly what
    "deployed" does and does not mean here."""
    if proposal.status != APPROVED:
        raise ValueError(
            f"proposal {proposal.id!r} is not in 'approved' state "
            f"(status={proposal.status!r}); only an approved proposal "
            "can be deployed")
    if not version.strip():
        raise ValueError("a deployed calibration requires a non-empty version label")
    return CalibrationProposal(
        id=proposal.id, worker_name=proposal.worker_name, layer=proposal.layer,
        proposed_thresholds=dict(proposal.proposed_thresholds),
        rationale=proposal.rationale, proposer=proposal.proposer,
        status=DEPLOYED,
        baseline_metric=proposal.baseline_metric,
        proposed_metric=proposal.proposed_metric,
        decided_by=proposal.decided_by, decided_at=proposal.decided_at,
        decision_rationale=proposal.decision_rationale,
        deployed_version=version,
        created_at=proposal.created_at,
    )


class CalibrationLedger:
    """Append-only, file-backed record of every calibration proposal
    state transition (one JSON line per transition — propose, test,
    decide, deploy each append a new line rather than editing a
    previous one). Mirrors ``satsa_review_decisions``'s append-only
    audit trail: a proposal's full history is always reconstructable,
    never overwritten in place."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, proposal: CalibrationProposal) -> None:
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(proposal.to_dict(), ensure_ascii=False) + "\n")

    def history(self, proposal_id: Optional[str] = None) -> list:
        if not self.path.exists():
            return []
        rows = [json.loads(line) for line in
                self.path.read_text(encoding="utf-8").splitlines()
                if line.strip()]
        if proposal_id:
            rows = [r for r in rows if r["id"] == proposal_id]
        return rows

    def latest_deployed(self, worker_name: str) -> Optional[dict]:
        """The most recently deployed calibration for ``worker_name``,
        or ``None`` if nothing has ever been deployed for it. A caller
        wanting to apply it constructs the worker's own
        ``*Thresholds`` dataclass from ``["proposed_thresholds"]`` and
        passes it to ``RunService.run(...)`` explicitly — see this
        module's docstring for why that step is intentionally not
        automatic."""
        rows = [r for r in self.history()
                if r["worker_name"] == worker_name and r["status"] == DEPLOYED]
        if not rows:
            return None
        return max(rows, key=lambda r: r["decided_at"] or 0)
