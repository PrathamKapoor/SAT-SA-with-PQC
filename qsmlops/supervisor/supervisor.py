"""Adaptive Agentic Supervisor: the platform's central decision engine.

Implements the control loop:

    Observe -> Detect -> Reason -> Act -> Verify -> Learn

Agents observe and return evidence-backed findings; the supervisor detects
risk, reasons to a decision (policy thresholds + agent recommendations +
learning state), acts through guarded handlers, verifies the outcome, and
records everything into the evidence ledger so the loop improves over time.
"""
from __future__ import annotations

import time

from qsmlops.agents.base import BaseAgent, Observation
from qsmlops.artifacts.store import ArtifactStore
from qsmlops.crypto.agility import AgilityEngine
from qsmlops.crypto.keys import KeyStore
from qsmlops.evidence.ledger import EvidenceLedger
from qsmlops.evidence.packet import SecurityCheck, VerificationPacket
from qsmlops.registry.registry import ModelRegistry
from qsmlops.scores import compute_scores
from qsmlops.supervisor.validation import ValidationReport, validate_observation
from qsmlops.supervisor.decisions import (
    Decision,
    DecisionReport,
    SupervisorPolicy,
    aggregate_risk,
)
from qsmlops.supervisor.learning import LearningStore
from qsmlops.supervisor.policy import (
    PolicyDecision,
    PolicyEngine,
    build_facts,
    default_policy_engine,
)


class SupervisorError(Exception):
    pass


ACTION_HANDLERS = {}


def action_handler(decision: Decision):
    def deco(fn):
        ACTION_HANDLERS[decision] = fn
        return fn

    return deco


# C1: Agents may emit advisory / non-Decision recommendation strings
# (BLOCK, REVIEW, INVESTIGATE, OPTIMIZE, MONITOR, EVALUATE_TRUST,
# REVIEW_SUPPLY_CHAIN). These are NOT decision conflicts. BLOCK is a genuine
# governance signal and maps to BLOCK_DEPLOYMENT; pure advisory strings
# collapse to ADVISORY (excluded from the supervisor's conflict tally); any
# unrecognised string fails closed to ESCALATE.
_DECISION_RECOMMENDATIONS = {d.value for d in Decision}
_ADVISORY_RECOMMENDATIONS = {
    "REVIEW", "INVESTIGATE", "OPTIMIZE", "MONITOR",
    "EVALUATE_TRUST", "REVIEW_SUPPLY_CHAIN",
}
_RECOMMENDATION_MAP = {
    "BLOCK": Decision.BLOCK_DEPLOYMENT.value,
}


def _normalize_recommendation(rec: str) -> str:
    if rec in _DECISION_RECOMMENDATIONS:
        return rec
    if rec in _RECOMMENDATION_MAP:
        return _RECOMMENDATION_MAP[rec]
    if rec in _ADVISORY_RECOMMENDATIONS:
        return "ADVISORY"
    if not rec:
        return ""
    # Unrecognized recommendation string: fail closed to ESCALATE rather than
    # silently ignoring it.
    return Decision.ESCALATE.value


class _NoOpLearner:
    """Safe default when no learning store is supplied: never escalates and
    records nothing, so the supervisor still functions without a learner.
    (Replaces the previous `LearningStore.__new__(LearningStore)`, which
    returned an uninitialised instance whose methods raised at runtime.)"""

    def should_escalate(self, model_name: str) -> bool:
        return False

    def consecutive_failures(self, model_name: str) -> int:
        return 0

    def record_outcome(self, model_name: str, decision: str,
                       success: bool, detail: str = "") -> None:
        return None


class AdaptiveSupervisor:
    def __init__(
        self,
        agents: list[BaseAgent],
        registry: ModelRegistry,
        keystore: KeyStore,
        agility: AgilityEngine,
        ledger: EvidenceLedger,
        artifacts: ArtifactStore,
        policy: SupervisorPolicy | None = None,
        policy_engine: PolicyEngine | None = None,
        learner: LearningStore | None = None,
        verifier_owner: str = "verifier",
    ) -> None:
        self.agents = agents
        self.registry = registry
        self.keystore = keystore
        self.agility = agility
        self.ledger = ledger
        self.artifacts = artifacts
        self.policy = policy or SupervisorPolicy()
        self.policy_engine = policy_engine or default_policy_engine()
        self.learner = learner or _NoOpLearner()
        self.verifier_owner = verifier_owner
        self._retrain_fn = None
        self._last_facts: dict = {}
        self._last_policy_decisions: list[dict] = []

    def set_retrain_function(self, fn) -> None:
        """fn(model_name) -> new_version_id ; used by the RETRAIN action."""
        self._retrain_fn = fn

    # ---------------- Observe ----------------
    def gather_context(self, version_id: str) -> dict:
        rec = self.registry.get_version(version_id)
        passport = self.registry.load_passport(version_id)
        from qsmlops.supplychain.bom import QMLBOM

        try:
            bom_doc = self.artifacts.get_if_exists(rec["bom_digest"])
        except IOError:
            bom_doc = None
        bom = None
        if bom_doc:
            import json

            bom = QMLBOM.from_dict(json.loads(bom_doc.decode("utf-8")))
        context = {
            "subject_id": version_id,
            "version_record": rec,
            "passport": passport,
            "keystore": self.keystore,
            "bom": bom,
            "artifact_digest": rec["artifact_digest"],
            "metrics": passport.metrics,
            "probe_inputs": [[0.1, -0.2], [0.5, 0.3], [-0.4, 0.6], [1.0, -1.0], [0.0, 0.0]],
        }
        return context

    def collect_observations(self, context: dict) -> list[Observation]:
        observations = []
        self._last_validation: list[dict] = []
        for agent in self.agents:
            try:
                obs = agent.observe(context)
            except Exception as exc:
                from qsmlops.agents.base import Finding

                obs = Observation(
                    agent=agent.name,
                    subject_id=context.get("subject_id", ""),
                    recommendation="ESCALATE",
                    notes=f"agent crashed: {type(exc).__name__}: {exc}",
                )
                obs.findings.append(
                    Finding("agent_executed", False, "HIGH", str(exc))
                )
            # Phase 10 evidence-validation engine (fail-safe sanitisation).
            clean, report = None, None
            # T1: even the validator itself must not be able to crash the
            # supervisor loop or silently drop evidence. If validation raises,
            # replace the observation with a structured HIGH/ESCALATE marker so
            # the fail-closed model is preserved.
            try:
                clean, report = validate_observation(obs)
            except Exception as exc:
                from qsmlops.agents.base import Finding

                agent_name = getattr(obs, "name", "<unknown>")
                clean = Observation(
                    agent=agent_name,
                    subject_id=context.get("subject_id", ""),
                    recommendation="ESCALATE",
                    findings=[Finding(
                        "observation_validation", False, "HIGH",
                        detail=f"validation crashed: {type(exc).__name__}: {exc}",
                        observation="observation validation failed",
                        confidence=1.0, recommendation="ESCALATE",
                    )],
                    notes=f"validation crashed: {type(exc).__name__}: {exc}",
                )
                report = ValidationReport(
                    agent=agent_name,
                    problems=[f"validation raised: {exc}"],
                )
            self._last_validation.append(report.to_dict())
            # C2: the dropped-evidence marker fires ONLY when validation
            # actually DROPPED findings (invalid name/severity/passed), never
            # on benign de-duplication (which is counted separately and keeps
            # the first occurrence). A dropped finding means evidence was
            # lost, so we replace it with an explicit failed marker rather
            # than letting the agent's output become weaker (fail-closed).
            if report.dropped > 0:
                from qsmlops.agents.base import Finding

                clean.findings.append(Finding(
                    "evidence_validation", False, "HIGH",
                    detail=("validation dropped "
                            f"{report.dropped} finding(s): "
                            + "; ".join(report.problems[:3])),
                    observation="observation failed evidence validation",
                    confidence=1.0, recommendation="ESCALATE",
                ))
                # S3: the dropped-evidence marker must also flip the
                # observation-level recommendation to ESCALATE so the
                # supervisor's reason() path (which reads obs.recommendation)
                # cannot accidentally ACCEPT after evidence loss (fail-closed).
                clean.recommendation = "ESCALATE"
            observations.append(clean)
        # C1: normalise recommendation strings AFTER validation so advisory
        # values (REVIEW/INVESTIGATE/OPTIMIZE/MONITOR/... ) do not inflate the
        # decision-conflict count in reason(), while BLOCK becomes the genuine
        # BLOCK_DEPLOYMENT decision and unrecognised strings fail closed.
        for obs in observations:
            obs.recommendation = _normalize_recommendation(obs.recommendation)
        return observations

    # ---------------- Detect + Reason ----------------
    def reason(
        self, version_id: str, context_override: dict | None = None
    ) -> tuple[DecisionReport, list[Observation]]:
        context = context_override or self.gather_context(version_id)
        observations = self.collect_observations(context)
        validation = getattr(self, "_last_validation", [])
        risk, per_agent = aggregate_risk(observations)  # Phase-10 adaptive

        recs = {obs.recommendation for obs in observations}
        model_name = context["version_record"]["model_name"]
        rationale_parts: list[str] = []

        hard_quarantine = any(
            not f.passed and f.severity == "CRITICAL" and not f.name.startswith("drift_")
            for obs in observations
            for f in obs.findings
        )
        block_signals = [
            obs
            for obs in observations
            if obs.recommendation == "BLOCK_DEPLOYMENT"
        ]
        rotate = any(obs.recommendation == "ROTATE_KEYS" for obs in observations)
        rollback = any(obs.recommendation == "ROLLBACK" for obs in observations)
        retrain = any(obs.recommendation == "RETRAIN" for obs in observations)

        # --- policy layer facts (scores + drift summary) ---
        drift_summary = context.get("drift_summary")
        scores = compute_scores(
            observations,
            passport=context.get("passport"),
            keystore=self.keystore,
            drift_summary=drift_summary,
        )
        facts = build_facts(
            observations, risk, per_agent,
            version_record=context.get("version_record"),
            scores=scores,
            drift_summary=drift_summary if isinstance(drift_summary, dict) else None,
        )
        self._last_facts = facts

        # --- policy engine evaluation (declarative rules, priority order) ---
        policy_decisions = (
            self.policy_engine.evaluate(facts) if self.policy_engine else []
        )
        self._last_policy_decisions = [d.to_dict() for d in policy_decisions]

        def _apply(d: PolicyDecision) -> Decision:
            try:
                return Decision(d.action)
            except ValueError:
                return Decision.ESCALATE

        learning_escalate = self.learner.should_escalate(model_name)
        gate_block = (
            self.policy_engine.deployment_blocked(facts)
            if self.policy_engine else None
        )

        if not observations:
            decision = Decision.ESCALATE
            rationale_parts.append(
                "no agent observations produced; cannot assess autonomously")
        elif learning_escalate:
            decision = Decision.ESCALATE
            rationale_parts.append(
                f"learning store: {self.learner.consecutive_failures(model_name)} "
                f"consecutive failed recoveries for {model_name}"
            )
        elif hard_quarantine:
            decision = Decision.QUARANTINE
            rationale_parts.append("critical finding(s): trust chain broken")
        elif block_signals:
            decision = Decision.BLOCK_DEPLOYMENT
            rationale_parts.append("security agent blocked deployment")
        elif policy_decisions:
            top = policy_decisions[0]
            decision = _apply(top)
            cond = ", ".join(top.matched_conditions[:3])
            rationale_parts.append(
                f"policy rule {top.rule_name!r} fired ({top.action}): {cond}"
            )
        elif Decision.QUARANTINE.value in recs:
            decision = Decision.QUARANTINE
            rationale_parts.append("agent recommended quarantine")
        elif rotate:
            decision = Decision.ROTATE_KEYS
            rationale_parts.append("crypto posture degraded; key rotation required")
        elif rollback:
            decision = Decision.ROLLBACK
            rationale_parts.append("critical drift detected; rollback required")
        elif "ESCALATE" in recs:
            decision = Decision.ESCALATE
            rationale_parts.append("agent recommended escalation for human review")
        elif risk >= self.policy.quarantine_risk:
            decision = Decision.QUARANTINE
            rationale_parts.append(f"aggregate risk {risk:.1f} above quarantine threshold")
        elif retrain:
            decision = Decision.RETRAIN
            rationale_parts.append("performance below threshold")
        else:
            decision = Decision.ACCEPT
            rationale_parts.append(f"all agents passed (risk {risk:.1f})")

        # deployment gates always win over promotion decisions
        if gate_block is not None and decision == Decision.DEPLOY:
            decision = Decision.BLOCK_DEPLOYMENT
            rationale_parts.append(f"deployment gate {gate_block.rule_name!r} closed")

        if len(recs - {"ACCEPT", "ADVISORY"}) > 2 and decision == Decision.ACCEPT:
            decision = Decision.ESCALATE
            rationale_parts.append("conflicting agent recommendations require human review")

        report = DecisionReport(
            decision=decision,
            risk_score=risk,
            category_scores=per_agent,
            observations=[o.to_dict() for o in observations],
            rationale="; ".join(rationale_parts),
            subject_id=version_id,
            facts=facts,
            policy_decisions=[d.to_dict() for d in policy_decisions],
            scores=scores,
            validation=list(validation),
        )
        return report, observations

    # ---------------- Act + Verify + Learn ----------------
    def run_cycle(self, version_id: str, context_override: dict | None = None) -> dict:
        report, observations = self.reason(version_id, context_override)
        packet = VerificationPacket.create(
            objective=f"supervise {report.subject_id}",
            actor="adaptive-supervisor",
            inputs={"risk_score": round(report.risk_score, 3)},
            security_checks=[
                SecurityCheck(
                    name=f"{o['agent']}:{f['name']}",
                    passed=f["passed"],
                    severity=f["severity"],
                    detail=f["detail"],
                )
                for o in report.observations
                for f in o["findings"]
            ],
            proofs={
                "category_scores": report.category_scores,
                "scores": {k: round(v, 2) for k, v in report.scores.items()},
                "policy_decisions": report.policy_decisions,
                "policy": {
                    "quarantine": self.policy.quarantine_risk,
                    "block": self.policy.block_risk,
                    "escalate": self.policy.escalate_risk,
                },
            },
            decision=report.decision.value,
            status="CLOSED",
        )
        outcome_success, outcome_detail = self._execute(report, version_id)
        verified = self._verify_outcome(report.decision, version_id)
        success = bool(outcome_success and verified)
        self.learner.record_outcome(
            self.gather_context(version_id)["version_record"]["model_name"],
            report.decision.value,
            success,
            outcome_detail or report.rationale,
        )
        packet.metrics = {"outcome_success": success}
        self.ledger.append_packet(packet)
        return {
            "report": report.to_dict(),
            "packet_id": packet.packet_id,
            "action_success": outcome_success,
            "verified": verified,
            "detail": outcome_detail,
        }

    def _execute(self, report: DecisionReport, version_id: str) -> tuple[bool, str]:
        d = report.decision
        try:
            if d == Decision.ACCEPT:
                return True, "no action required"
            if d == Decision.QUARANTINE:
                self.registry.quarantine(version_id, "supervisor", report.rationale)
                return True, f"quarantined {version_id[:12]}"
            if d == Decision.BLOCK_DEPLOYMENT:
                active = self.registry.active_deployment(
                    self.gather_context(version_id)["version_record"]["model_name"]
                )
                if active and active["version_id"] == version_id:
                    prev = self.registry.rollback(
                        active["model_name"], "supervisor"
                    )
                    return True, f"blocked and rolled back to {str(prev)[:12]}"
                return True, "deployment blocked before gate"
            if d == Decision.ROLLBACK:
                name = self.gather_context(version_id)["version_record"]["model_name"]
                prev = self.registry.rollback(name, "supervisor")
                return True, f"rolled back to {str(prev)[:12]}"
            if d == Decision.RETRAIN:
                if self._retrain_fn is None:
                    return False, "no retrain function registered"
                new_vid = self._retrain_fn(
                    self.gather_context(version_id)["version_record"]["model_name"]
                )
                return True, f"retrained as {new_vid[:12]}"
            if d == Decision.ROTATE_KEYS:
                signer_owner = self._signer_owner(version_id)
                new_key = self.keystore.rotate_signer(signer_owner)
                return True, f"rotated signing key for {signer_owner} -> {new_key[:16]}…"
            if d == Decision.ESCALATE:
                self.ledger.append(
                    {"type": "escalation", "version_id": version_id, "reason": report.rationale}
                )
                return True, "escalated to human operators"
            if d == Decision.DEPLOY:
                packet = VerificationPacket.create(
                    objective="supervisor-approved deploy", actor="adaptive-supervisor",
                    decision="ACCEPT", status="CLOSED",
                )
                self.registry.approve_deployment(version_id, "supervisor", packet)
                dep_id = self.registry.deploy(version_id, "supervisor")
                return True, f"deployed as {dep_id[:12]}"
        except Exception as exc:
            return False, f"action failed: {type(exc).__name__}: {exc}"
        return False, f"unhandled decision {d}"

    def _verify_outcome(self, decision: Decision, version_id: str) -> bool:
        try:
            rec = self.registry.get_version(version_id)
        except KeyError:
            return False
        if decision == Decision.QUARANTINE:
            return rec["state"] == "QUARANTINED"
        if decision == Decision.DEPLOY:
            name = rec["model_name"]
            active = self.registry.active_deployment(name)
            return bool(active and active["version_id"] == version_id)
        if decision == Decision.BLOCK_DEPLOYMENT:
            return rec["state"] != "APPROVED"
        if decision == Decision.RETRAIN:
            versions = self.registry.list_versions(rec["model_name"])
            if not versions:
                return False
            newest = versions[-1]
            # A retrain cycle is only "verified" if it produced a genuinely
            # newer version that has since been promoted (APPROVED/DEPLOYED) —
            # merely having >1 version in the registry does not prove recovery.
            return (newest["version_id"] != version_id
                    and newest["state"] in ("APPROVED", "DEPLOYED"))
        return True

    def _signer_owner(self, version_id: str) -> str:
        passport = self.registry.load_passport(version_id)
        if passport.signature is None:
            return "producer"
        parts = passport.signature.signer_key_id.split("-")
        return parts[0] if parts else "producer"
