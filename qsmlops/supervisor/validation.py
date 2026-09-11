"""Evidence/observation validation (Phase 10 — Evidence Validation Engine).

Deterministic, fail-safe sanitisation of everything an agent hands to the
supervisor. Validation NEVER upgrades malformed input into trusted evidence:
problems are reported, unparseable findings are replaced by a failed
HIGH-severity ``malformed_finding`` marker so downstream gates see them, and
duplicate findings are collapsed (first occurrence wins).

The validator never raises; a completely unusable Observation is reported via
the returned problems list and reduced to a single malformed marker by the
caller-side helper :func:`sanitise_observation`.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from qsmlops.agents.base import Finding, Observation

VALID_SEVERITIES = {"LOW", "MEDIUM", "HIGH", "CRITICAL"}


@dataclass
class ValidationReport:
    agent: str
    problems: list[str] = field(default_factory=list)
    duplicates_collapsed: int = 0
    confidences_clamped: int = 0
    dropped: int = 0

    @property
    def ok(self) -> bool:
        return not self.problems

    def to_dict(self) -> dict:
        return {
            "agent": self.agent,
            "ok": self.ok,
            "problems": list(self.problems),
            "duplicates_collapsed": self.duplicates_collapsed,
            "confidences_clamped": self.confidences_clamped,
            "dropped": self.dropped,
        }


def _clamp_confidence(value) -> tuple[float, bool]:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return 0.5, True
    if v != v:  # NaN
        return 0.5, True
    clamped = max(0.0, min(1.0, v))
    return clamped, clamped != v


def validate_observation(observation: Observation) -> tuple[Observation, ValidationReport]:
    """Return a sanitised copy of ``observation`` plus a validation report."""
    report = ValidationReport(agent=getattr(observation, "agent", "<unknown>"))

    if not isinstance(observation, Observation):
        marker = Finding(name="malformed_finding", passed=False, severity="HIGH",
                         detail="agent returned a non-Observation value",
                         observation="malformed agent output",
                         confidence=1.0, recommendation="ESCALATE")
        bogus = Observation(agent=str(report.agent), subject_id="",
                            recommendation="ESCALATE", findings=[marker],
                            notes="replaced malformed observation")
        report.problems.append("observation is not an Observation instance")
        return bogus, report

    # ---- shallow identity -------------------------------------------------
    if not isinstance(observation.agent, str) or not observation.agent.strip():
        report.problems.append("agent name missing/blank")
    if not isinstance(observation.subject_id, str):
        report.problems.append("subject_id is not a string")

    # ---- findings ---------------------------------------------------------
    cleaned: list[Finding] = []
    seen: set[tuple] = set()
    raw_findings = getattr(observation, "findings", None)
    if not isinstance(raw_findings, list):
        report.problems.append("findings container is not a list")
        raw_findings = []

    for f in raw_findings:
        name = getattr(f, "name", None)
        severity = getattr(f, "severity", None)
        passed = getattr(f, "passed", None)
        detail = getattr(f, "detail", "")
        if not isinstance(name, str) or not name.strip():
            report.problems.append(f"finding with invalid name: {name!r}")
            report.dropped += 1
            continue
        if severity not in VALID_SEVERITIES:
            report.problems.append(
                f"finding {name!r} has invalid severity {severity!r}")
            report.dropped += 1
            continue
        if not isinstance(passed, bool):
            report.problems.append(
                f"finding {name!r} has non-boolean 'passed' ({passed!r})")
            report.dropped += 1
            continue

        key = (f.name, f.passed, getattr(f, "detail", ""))
        if key in seen:
            report.duplicates_collapsed += 1
            continue
        seen.add(key)

        conf, was_clamped = _clamp_confidence(getattr(f, "confidence", 0.8))
        if was_clamped:
            report.confidences_clamped += 1
            report.problems.append(
                f"finding {name!r} confidence out of [0,1]; clamped")

        evidence_ok = True
        ev_list = getattr(f, "evidence", [])
        if not isinstance(ev_list, list):
            evidence_ok = False
            report.problems.append(f"finding {name!r} evidence container invalid")
        else:
            for e in ev_list:
                if not hasattr(e, "source") or not getattr(e, "source"):
                    evidence_ok = False
                    report.problems.append(
                        f"finding {name!r} carries evidence without a source")
                    break
                payload = getattr(e, "payload", {})
                if payload is not None and not isinstance(payload, dict):
                    evidence_ok = False
                    report.problems.append(
                        f"finding {name!r} evidence payload is not a mapping")
                    break

        rec = getattr(f, "recommendation", "")
        if not isinstance(rec, str):
            report.problems.append(f"finding {name!r} recommendation not a string")
            rec = ""

        nf = Finding(
            name=f.name, passed=f.passed, severity=f.severity,
            detail=getattr(f, "detail", ""), observation=getattr(f, "observation", ""),
            evidence=list(ev_list or []), confidence=conf,
            recommendation=rec,
        )
        if not evidence_ok:
            from qsmlops.agents.base import Evidence as _E

            nf.evidence.append(_E(source="supervisor.validator", kind="log",
                                  payload={"problem": "invalid evidence structure"},
                                  description="evidence validation"))
        cleaned.append(nf)

    out = Observation(agent=observation.agent,
                      subject_id=getattr(observation, "subject_id", ""),
                      recommendation=observation.recommendation,
                      findings=cleaned,
                      notes=getattr(observation, "notes", ""))
    return out, report


def sanitise_all(observations: list) -> tuple[list[Observation], list[dict]]:
    """Validate a sweep; returns (sanitised observations, report dicts)."""
    out, reports = [], []
    for obs in observations:
        clean, report = validate_observation(obs)
        out.append(clean)
        reports.append(report.to_dict())
    return out, reports
