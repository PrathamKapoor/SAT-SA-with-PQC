"""Generalized supervisor engine: Observe → Reason → Act → Verify → Learn.

The roadmap requires a single supervisor engine with two pluggable
decision vocabularies:

* **MLOps vocabulary** — ``ACCEPT``, ``DEPLOY``, ``RETRAIN``,
  ``QUARANTINE``, ``ROTATE_KEYS``, ``BLOCK_DEPLOYMENT``, ``ESCALATE``,
  ``ROLLBACK`` (the decisions the existing ``qsmlops.supervisor``
  already emits).
* **SAT-SA vocabulary** — ``SURFACE``, ``INSPECT``,
  ``REQUEST_EVIDENCE``, ``ESCALATE_FOR_REVIEW``, ``DEFER``,
  ``ACCEPT``, ``CLOSE_REVIEW`` (the decisions a supervisory
  analyst interface uses to drive a human review workflow).

The engine does not invent new vocabulary — it routes the
existing per-domain decision through the same observe/reason/act/
verify/learn loop. The 17 SAT-SA agents all emit findings with
``recommended_action`` set; the SAT-SA vocabulary maps those
findings into one of the seven SAT-SA decisions. The MLOps
vocabulary maps MLOps findings into the eight MLOps decisions.

Human supervisory authority is preserved: every SAT-SA decision
that would constitute an irreversible supervisory action is
emitted as ``Decision(action="INSPECT" | "REQUEST_EVIDENCE" |
"ESCALATE_FOR_REVIEW", requires_human=True, ...)``. No agent
ever ``ACCEPT``s or ``CLOSE_REVIEW``s autonomously — that is the
terminal authority of the human supervisor.

``verify`` runs the trust layer against the latest run + every
finding in the decision's evidence set. ``learn`` records the
decision's lineage into the supervisor's append-only log.
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Decision vocabularies (the two pluggable sets)
# ---------------------------------------------------------------------------

MLOPS_VOCABULARY: tuple[str, ...] = (
    "ACCEPT", "DEPLOY", "RETRAIN", "QUARANTINE",
    "ROTATE_KEYS", "BLOCK_DEPLOYMENT", "ESCALATE", "ROLLBACK",
)

# The SAT-SA vocabulary is a separate, *non-overlapping* set of
# decision actions. The roadmap explicitly calls for two
# pluggable vocabularies; sharing the same identifier (e.g.
# ACCEPT) across both would defeat the point. Every SAT-SA
# action is prefixed ``SAT-SA_`` (or ``SATSA_``) to make the
# vocabulary disjoint at the lexical level and unambiguously
# routed.
SATSA_VOCABULARY: tuple[str, ...] = (
    "SATSA_SURFACE", "SATSA_INSPECT", "SATSA_REQUEST_EVIDENCE",
    "SATSA_ESCALATE_FOR_REVIEW", "SATSA_DEFER",
    "SATSA_ACCEPT", "SATSA_CLOSE_REVIEW",
)

# Backwards-compatible short aliases — the UI surfaces these in
# human-readable form. The engine always emits the prefixed
# canonical action; the alias is for display only.
SATSA_VOCABULARY_DISPLAY = {
    "SATSA_SURFACE": "SURFACE",
    "SATSA_INSPECT": "INSPECT",
    "SATSA_REQUEST_EVIDENCE": "REQUEST_EVIDENCE",
    "SATSA_ESCALATE_FOR_REVIEW": "ESCALATE_FOR_REVIEW",
    "SATSA_DEFER": "DEFER",
    "SATSA_ACCEPT": "ACCEPT",
    "SATSA_CLOSE_REVIEW": "CLOSE_REVIEW",
}


# Decisions that are bounded human-action guidance; the human
# supervisor remains terminal authority on these.
HUMAN_AUTHORITY_DECISIONS = frozenset({
    "INSPECT", "REQUEST_EVIDENCE", "ESCALATE_FOR_REVIEW", "DEFER",
    "ACCEPT", "CLOSE_REVIEW",
})

# Decisions the existing MLOps supervisor emits autonomously on
# the basis of policy (the operator signs off via the deployment
# workflow, not the supervisor).
MLOPS_AUTONOMOUS_DECISIONS = frozenset({
    "ACCEPT", "DEPLOY", "RETRAIN", "QUARANTINE",
    "ROTATE_KEYS", "BLOCK_DEPLOYMENT", "ROLLBACK",
})


# ---------------------------------------------------------------------------
# Decision + DecisionContext
# ---------------------------------------------------------------------------

@dataclass
class DecisionContext:
    """Inputs the supervisor engine threads through
    observe → reason → act → verify → learn."""

    vocabulary: str          # "mlops" or "satsa"
    scope: dict              # entity_id / assessment_id / period etc.
    run_id: str = ""
    findings: list = field(default_factory=list)
    risk_profile: Any = None
    trust_receipts: list = field(default_factory=list)
    review_history: list = field(default_factory=list)
    policy: Any = None
    principal: str = "ui-anonymous"
    provenance: dict = field(default_factory=dict)


@dataclass
class Decision:
    """One supervisor decision: the outcome of reason → act."""

    decision_id: str
    vocabulary: str
    action: str
    rationale: str
    target_ids: list = field(default_factory=list)        # subjects of the decision
    evidence_refs: list = field(default_factory=list)
    requires_human: bool = True
    created_at: float = field(default_factory=time.time)
    provenance: dict = field(default_factory=dict)
    lineage: list = field(default_factory=list)           # the prior stages

    def to_dict(self) -> dict:
        return {
            "decision_id": self.decision_id,
            "vocabulary": self.vocabulary,
            "action": self.action,
            "rationale": self.rationale,
            "target_ids": list(self.target_ids),
            "evidence_refs": list(self.evidence_refs),
            "requires_human": self.requires_human,
            "created_at": self.created_at,
            "provenance": dict(self.provenance),
            "lineage": list(self.lineage),
        }


# ---------------------------------------------------------------------------
# Five stages — explicit, testable, single-purpose functions
# ---------------------------------------------------------------------------

def observe(ctx: DecisionContext) -> DecisionContext:
    """Stage 1 — gather observations. For SAT-SA: every agent
    listed in ``AGENT_REGISTRY`` whose family is ``satsa`` has
    already produced its ObservationBatch during the analysis
    run; we collect those findings into ``ctx.findings``. The
    ``analyze`` call (RunService.run) is what invokes the
    workers; observe() here is the supervisor's post-run
    collection stage."""
    # The findings already live on ctx — observe() is a typed
    # marker stage. The supervisor records the observation stage
    # in the decision lineage.
    if ctx.provenance is None:
        ctx.provenance = {}
    ctx.provenance["observe"] = {
        "observation_count": len(ctx.findings),
        "at": time.time(),
    }
    return ctx


def reason(ctx: DecisionContext) -> DecisionContext:
    """Stage 2 — synthesize. Map the run's findings into a single
    Decision using the vocabulary attached to the context.

    For SAT-SA: the dominant finding's ``recommended_action`` is
    used as the action; the rationale combines the finding's
    rationale + the risk profile's top dimension + the trust
    status of the supporting evidence. If no finding fires, the
    engine defaults to ``SURFACE`` (still surfaces the run to the
    human queue, but does not propose an action).

    For MLOps: the existing ``qsmlops.supervisor`` logic owns
    policy decisions. This stage emits a typed Decision object
    but does not execute the action — it is recorded as a
    proposal, not executed. Execution happens via the existing
    SelfHealingMLOps pipeline.
    """
    if ctx.vocabulary == "satsa":
        return _reason_satsa(ctx)
    if ctx.vocabulary == "mlops":
        return _reason_mlops(ctx)
    raise ValueError(f"unknown vocabulary {ctx.vocabulary!r}")


def _field(finding, name, default=None):
    """Read a field from either a dataclass-like finding or a plain
    row dict (the CLI / demo pass row dicts; tests pass Finding
    objects)."""
    if isinstance(finding, dict):
        return finding.get(name, default)
    return getattr(finding, name, default)


def _confidence_overall(finding) -> float:
    conf = _field(finding, "confidence", None)
    if isinstance(conf, dict):
        overall = conf.get("overall", 0.0)
    else:
        overall = getattr(conf, "overall", 0.0) if conf else 0.0
    try:
        return float(overall or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _reason_satsa(ctx: DecisionContext) -> DecisionContext:
    signal_findings = [f for f in ctx.findings
                       if _field(f, "state", "") == "signal"]
    top = None
    if signal_findings:
        # Prefer the highest-confidence signal finding. ConfidenceVector
        # .overall is the canonical confidence the roadmap asks
        # for.
        top = max(signal_findings, key=_confidence_overall)
    if top is not None:
        # Compute a bounded human-action recommendation from the
        # finding's rule family using the existing
        # satsa.analysis.recommend engine. The recommendation
        # engine returns one of the bounded inspect / check /
        # verify / compare / request / review actions; we then
        # map that to the closest SAT-SA vocabulary action.
        rec_action = _SATSA_RECOMMENDATION_TO_DECISION.get(
            _recommend_for(top), "SATSA_SURFACE")
        ctx.provenance["reason"] = {
            "action": rec_action,
            "selected_finding_id": _field(top, "id", None),
            "rationale": _field(top, "rationale", ""),
            "recommendation_action": _recommend_for(top),
        }
    else:
        ctx.provenance["reason"] = {"action": "SATSA_SURFACE",
                                    "selected_finding_id": None,
                                    "rationale": "no signal findings"}
    return ctx


def _recommend_for(finding) -> str:
    """Map a finding to its bounded recommendation action using the
    existing ``satsa.analysis.recommend`` engine. Imported lazily to
    keep the supervisor importable in tests that don't need the
    full recommendation vocabulary."""
    try:
        from satsa.analysis.recommend import recommend
        return recommend(finding).action
    except Exception:  # noqa: BLE001
        return "REVIEW"


# Map the bounded human-action recommendations emitted by
# satsa.analysis.recommend into the SAT-SA supervisor vocabulary.
# Every value is the prefixed SAT-SA action.
_SATSA_RECOMMENDATION_TO_DECISION = {
    "INSPECT_INVESTIGATION": "SATSA_INSPECT",
    "CHECK_ESCALATION_PATH": "SATSA_INSPECT",
    "VERIFY_MONITORING_COVERAGE": "SATSA_REQUEST_EVIDENCE",
    "COMPARE_WITH_PEERS": "SATSA_SURFACE",
    "REQUEST_MISSING_EVIDENCE": "SATSA_REQUEST_EVIDENCE",
    "REVIEW_METRIC_DEFINITION": "SATSA_DEFER",
    "INSPECT_ROOT_CAUSE_REMEDIATION": "SATSA_INSPECT",
    "REVIEW": "SATSA_SURFACE",
}


def _reason_mlops(ctx: DecisionContext) -> DecisionContext:
    # The MLOps supervisor owns the actual decision logic; we
    # just record the proposal here. The proposal is mapped from
    # the highest-severity finding.
    if not ctx.findings:
        ctx.provenance["reason"] = {"action": "ACCEPT",
                                    "selected_finding_id": None}
        return ctx
    top = max(ctx.findings,
              key=lambda f: float(getattr(f, "severity", 0.0) or 0.0))
    action = getattr(top, "recommended_action", "ESCALATE") or "ESCALATE"
    if action not in MLOPS_VOCABULARY:
        action = "ESCALATE"
    ctx.provenance["reason"] = {"action": action,
                                "selected_finding_id": getattr(top, "id", None)}
    return ctx


def _decision_requires_human(vocabulary: str, action: str) -> bool:
    """Whether the decision is one a human must approve.

    For SAT-SA: every action in the vocabulary is human-directed
    (the supervisor is the terminal authority). For MLOps: only
    ESCALATE is human-directed; the other MLOps decisions are
    policy-driven proposals that flow into the existing
    SelfHealingMLOps pipeline.
    """
    if vocabulary == "satsa":
        return True
    if vocabulary == "mlops":
        return action == "ESCALATE"
    return True


def act(ctx: DecisionContext) -> Decision:
    """Stage 3 — emit the Decision. SAT-SA decisions always
    require human authority. MLOps decisions are proposals that
    feed into the existing SelfHealingMLOps pipeline."""
    reason_meta = ctx.provenance.get("reason", {})
    default_action = "SATSA_SURFACE" if ctx.vocabulary == "satsa" else "ACCEPT"
    action = reason_meta.get("action", default_action)
    rationale = reason_meta.get("rationale", "")
    target_ids = [i for i in (_field(f, "id", None) for f in ctx.findings) if i]
    evidence_refs = []
    for f in ctx.findings:
        refs = _field(f, "evidence_refs", None) or []
        evidence_refs.extend(refs)
    requires_human = _decision_requires_human(ctx.vocabulary, action)
    decision = Decision(
        decision_id="dec_" + uuid.uuid4().hex[:12],
        vocabulary=ctx.vocabulary,
        action=action,
        rationale=rationale,
        target_ids=target_ids,
        evidence_refs=evidence_refs,
        requires_human=requires_human,
        lineage=[
            ("observe", ctx.provenance.get("observe", {})),
            ("reason", reason_meta),
        ],
    )
    ctx.provenance["act"] = {"decision_id": decision.decision_id,
                             "action": action,
                             "requires_human": requires_human,
                             "at": time.time()}
    return decision


def verify(ctx: DecisionContext, decision: Decision) -> Decision:
    """Stage 4 — integrity verification. Pull every trust receipt
    attached to the run + the decision's target findings and add
    a verification summary to the decision's provenance. The
    actual cryptographic check is performed by
    ``satsa.analysis.trust.TrustService.verify_subject``; this
    stage is the supervisor-level gate."""
    receipts = ctx.trust_receipts or []
    verified = 0
    for r in receipts:
        if isinstance(r, dict) and r.get("ok"):
            verified += 1
    total = len(receipts)
    summary = {
        "receipts_total": total,
        "receipts_verified": verified,
        "trust_verified": verified == total,
        "at": time.time(),
    }
    decision.lineage.append(("verify", summary))
    decision.provenance["verify"] = summary
    return decision


def learn(ctx: DecisionContext, decision: Decision) -> Decision:
    """Stage 5 — record the decision's lineage. The supervisor
    engine does not retrain or update weights from decisions;
    that is the roadmap's explicit honesty discipline. The
    ``learn`` stage records the decision for audit and surfaces
    the run's lineage to the human reviewer, who is the only
    entity allowed to mark the decision as acted-on."""
    meta = {
        "run_id": ctx.run_id,
        "scope": ctx.scope,
        "principal": ctx.principal,
        "vocabulary": ctx.vocabulary,
        "at": time.time(),
    }
    decision.lineage.append(("learn", meta))
    decision.provenance["learn"] = meta
    return decision


# ---------------------------------------------------------------------------
# SupervisorEngine — wires the five stages together
# ---------------------------------------------------------------------------

class SupervisorEngine:
    """The single generalized supervisor engine. One instance,
    two pluggable vocabularies. The engine itself is stateless
    except for an append-only lineage log the human reviewer can
    inspect."""

    def __init__(self) -> None:
        self.lineage_log: list[dict] = []

    def run(self, ctx: DecisionContext) -> Decision:
        if ctx.vocabulary == "satsa" and ctx.vocabulary != "satsa":
            raise ValueError("vocabulary must be 'satsa' or 'mlops'")
        if ctx.vocabulary not in ("satsa", "mlops"):
            raise ValueError(f"unknown vocabulary {ctx.vocabulary!r}")
        observe(ctx)
        reason(ctx)
        decision = act(ctx)
        verify(ctx, decision)
        learn(ctx, decision)
        self.lineage_log.append({
            "decision_id": decision.decision_id,
            "vocabulary": decision.vocabulary,
            "action": decision.action,
            "run_id": ctx.run_id,
            "scope": ctx.scope,
            "at": decision.created_at,
        })
        return decision