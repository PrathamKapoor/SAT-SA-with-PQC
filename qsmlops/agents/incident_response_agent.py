"""Incident Response Agent (Phase 9).

Classifies open/ongoing incidents from evidence the platform already records:
recent ledger signals (deployment denials, approval denials, escalations,
post-verification failures), adverse registry states, and active critical
drift. Strictly observational — remediation itself remains governed by the
supervisor / policy / registry path.
"""
from __future__ import annotations

from qsmlops.agents.base import BaseAgent, Evidence, Observation, make_finding

_INCIDENT_LEDGER_TYPES = {
    "deployment_denied": "MEDIUM",
    "approval_denied": "HIGH",
    "escalation": "CRITICAL",
    "deployment_failed_postverification": "CRITICAL",
}


class IncidentResponseAgent(BaseAgent):
    name = "incident-response-agent"

    def __init__(self, registry, lookback: int = 25) -> None:
        self.registry = registry
        self.lookback = lookback

    def observe(self, context: dict) -> Observation:
        findings = []
        subject = context.get("subject_id", "")

        # 1. recent incident signals from the authoritative ledger --------
        entries = list(self.registry.ledger.iter_entries())[-self.lookback:]
        signals: list[tuple[str, str]] = []
        for entry in entries:
            rec = entry.get("record", {})
            rtype = rec.get("type")
            if rtype in _INCIDENT_LEDGER_TYPES:
                signals.append((rtype, str(rec.get("reason") or rec.get("detail")
                                           or rec.get("version_id", ""))[:80]))
            elif rtype == "state_transition" and rec.get("to") in (
                    "QUARANTINED", "ROLLED_BACK"):
                signals.append((f"state_{rec['to']}",
                                str(rec.get("reason", ""))[:80]))

        findings.append(make_finding(
            "recent_incident_signals",
            not signals,
            "HIGH" if any(_INCIDENT_LEDGER_TYPES.get(s[0]) in ("HIGH", "CRITICAL")
                          or s[0].startswith("state_") for s in signals) else "MEDIUM",
            f"{len(signals)} recent incident signal(s)",
            observation=(f"ledger shows {len(signals)} recent incident signal(s): "
                         f"{', '.join(s[0] for s in signals[:4])}")
            if signals else "no recent incident signals in ledger tail",
            evidence=[Evidence("evidence_ledger", "log",
                               {"lookback": self.lookback,
                                "signals": [s[0] for s in signals]})],
            confidence=1.0,
            recommendation="ESCALATE" if signals else "",
        ))

        # 2. current version already in an adverse state -------------------
        rec_version = context.get("version_record") or {}
        state = rec_version.get("state", "")
        adverse = state in ("QUARANTINED", "ROLLED_BACK", "REVOKED")
        findings.append(make_finding(
            "subject_state_clear", not adverse,
            "CRITICAL" if state == "QUARANTINED" else ("HIGH" if adverse else "LOW"),
            f"version state={state}" + (" (incident open)" if adverse else ""),
            observation=f"evaluated version is in state {state}",
            evidence=[Evidence("model_registry", "log", {"state": state})],
            confidence=1.0,
            recommendation=("INVESTIGATE" if adverse else ""),
        ))

        # 3. ongoing critical drift ----------------------------------------
        drift = context.get("drift_summary") or {}
        if str(drift.get("max_severity")) == "CRITICAL":
            findings.append(make_finding(
                "drift_critical_ongoing", False, "CRITICAL",
                "critical-severity drift is active",
                observation="drift engine reports CRITICAL severity",
                evidence=[Evidence("drift_engine", "distribution",
                                   dict(drift))],
                confidence=0.95,
                recommendation="ESCALATE",
            ))

        failed = [f for f in findings if not f.passed]
        worst = max((f.severity for f in failed),
                    key=lambda s: {"LOW": 0, "MEDIUM": 1, "HIGH": 2,
                                   "CRITICAL": 3}.get(s, 0), default=None)
        rec = "ACCEPT" if not failed else (
            "ESCALATE" if worst == "CRITICAL" else "INVESTIGATE")
        return Observation(agent=self.name, subject_id=subject,
                           recommendation=rec, findings=findings,
                           notes=f"scanned last {self.lookback} ledger entries")
