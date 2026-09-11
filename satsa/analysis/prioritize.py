"""Review prioritization: rank entities and findings for human
review attention.

Two rankings are produced:

* ``prioritize_entities`` ranks every entity that has a
  most-recent AnalysisRun. Each entity is given a priority score
  and an *evidence-backed* explanation naming the top contributing
  dimensions / findings.

* ``prioritize_findings`` ranks every ``signal`` finding inside a
  given run, so the reviewer can ask "given this entity, where
  should I look first?" — useful for the review queue.

The priority score is **not** just the risk score. The risk score
is the per-entity aggregate; the priority score is the
reviewer's *next action*: it also weights confidence, recency and
high-severity-signal-count, so that two entities with the same
risk score but very different confidence levels or signal
profiles do not appear equal.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional


def _priority_score(profile, *, recency_weight: float = 5.0,
                    confidence_weight: float = 10.0,
                    high_signal_weight: float = 2.0) -> float:
    """Combine risk score, confidence, recency and high-signal
    count into a single priority number. Weights are documented
    here; changing them is a one-line edit."""
    confidence_value = {
        "very_low": 0.0, "low": 0.25, "medium": 0.6, "high": 1.0,
    }.get(profile.confidence_bucket, 0.0)
    age_seconds = max(0.0, time.time() - (profile.run_created_at or time.time()))
    # recency decays linearly over a 30-day window
    recency = max(0.0, 1.0 - age_seconds / (30 * 86400))
    high_signal_count = sum(
        1 for f in profile.signal_findings if f.get("severity") == "high")
    return (profile.total_score
            + confidence_weight * confidence_value
            + recency_weight * recency
            + high_signal_weight * high_signal_count)


def _load_run_and_findings(engine, run_id: str) -> dict:
    run = engine.query_one("SELECT * FROM satsa_runs WHERE id=?", (run_id,))
    if not run:
        return {"run": None, "findings": []}
    finding_rows = engine.query_all(
        "SELECT f.*, o.worker_name FROM satsa_findings f"
        " JOIN satsa_observations o ON o.id = f.observation_id"
        " WHERE o.run_id = ? ORDER BY f.created_at", (run_id,))
    return {"run": run, "findings": finding_rows}


def _severity_of(rule: str) -> str:
    """Bucket a rule_or_category into a coarse severity for
    prioritization. High = externally anchored, or directly
    associated with a known SIH execution gap; medium = anomalous
    pattern or negative space; low = data-completeness."""
    if rule.startswith("peer_benchmark.") or rule.startswith(
            "execution_gap.potential_metric_gaming"):
        return "high"
    if rule.startswith("execution_gap.") or rule.startswith("anomaly."):
        return "medium"
    return "low"


def _profile_with_findings(engine, entity_id: str) -> Optional[object]:
    """Build an ad-hoc profile-like object with the fields the
    priority code reads. Re-using ``compute_entity_risk`` keeps the
    math in one place; this helper just adds the extras the
    priority function needs."""
    from satsa.analysis.risk import compute_entity_risk
    profile = compute_entity_risk(engine, entity_id)
    if profile.run_id is None:
        return None
    extras = _load_run_and_findings(engine, profile.run_id)
    profile.run_created_at = extras["run"].get("created_at") if extras["run"] else None
    profile.signal_findings = [
        {**row, "severity": _severity_of(row.get("rule_or_category", ""))}
        for row in extras["findings"]
        if row.get("state") == "signal"]
    return profile


@dataclass
class EntityPriority:
    entity_id: str
    priority_score: float
    risk_score: float
    confidence_bucket: str
    run_id: Optional[str]
    rationale: str
    top_dimensions: list = field(default_factory=list)
    high_signal_count: int = 0

    def to_dict(self) -> dict:
        return {
            "entity_id": self.entity_id,
            "priority_score": round(self.priority_score, 2),
            "risk_score": round(self.risk_score, 2),
            "confidence_bucket": self.confidence_bucket,
            "run_id": self.run_id,
            "rationale": self.rationale,
            "top_dimensions": list(self.top_dimensions),
            "high_signal_count": self.high_signal_count,
        }


def prioritize_entities(engine) -> list[EntityPriority]:
    """Rank every entity that has a most-recent completed or partial
    run, by the priority score. Returns a list ordered highest-first."""
    entity_rows = engine.query_all(
        "SELECT DISTINCT entity_id FROM satsa_runs"
        " WHERE status IN ('completed','partial')"
        " ORDER BY entity_id")
    items: list[EntityPriority] = []
    for row in entity_rows:
        eid = row["entity_id"]
        profile = _profile_with_findings(engine, eid)
        if profile is None:
            continue
        # top dimensions by score, dropping zeros
        top_dims = sorted(
            [(d.name, d.score) for d in profile.dimensions if d.score > 0],
            key=lambda t: t[1], reverse=True)[:3]
        rationale_parts = [
            f"risk {profile.total_score:.0f}/100",
            f"confidence {profile.confidence_bucket}",
        ]
        if top_dims:
            rationale_parts.append(
                "top dimensions: " + ", ".join(f"{n}={s:.1f}" for n, s in top_dims))
        high_sig = sum(1 for f in profile.signal_findings
                       if f["severity"] == "high")
        if high_sig:
            rationale_parts.append(f"{high_sig} high-severity signal(s)")
        rationale = "; ".join(rationale_parts)
        items.append(EntityPriority(
            entity_id=eid,
            priority_score=_priority_score(profile),
            risk_score=profile.total_score,
            confidence_bucket=profile.confidence_bucket,
            run_id=profile.run_id,
            rationale=rationale,
            top_dimensions=[n for n, _ in top_dims],
            high_signal_count=high_sig,
        ))
    items.sort(key=lambda p: p.priority_score, reverse=True)
    return items


# ---------------------------------------------------------------------------
# Per-finding prioritization (within one run)
# ---------------------------------------------------------------------------

def _finding_priority(finding: dict, *, run: dict | None) -> float:
    """A within-run score: severity + confidence. Recency is implied
    because the run is the most-recent one for the entity."""
    severity_value = {"high": 25, "medium": 15, "low": 5}.get(
        finding.get("severity", "low"), 5)
    conf = finding.get("confidence_overall", 0.5)
    return severity_value * (0.5 + conf)


@dataclass
class FindingPriority:
    finding_id: str
    rule_or_category: str
    rationale: str
    state: str
    severity: str
    confidence_overall: float
    priority_score: float
    observation_id: str
    worker_name: str

    def to_dict(self) -> dict:
        return {
            "finding_id": self.finding_id, "rule_or_category": self.rule_or_category,
            "rationale": self.rationale, "state": self.state,
            "severity": self.severity,
            "confidence_overall": round(self.confidence_overall, 2),
            "priority_score": round(self.priority_score, 2),
            "observation_id": self.observation_id,
            "worker_name": self.worker_name,
        }


def prioritize_findings(engine, run_id: str) -> list[FindingPriority]:
    """Rank the *signal* findings of a single run, highest first.
    Every priority includes an evidence-backed rationale built from
    the finding's own rule + rationale text — no fabricated
    reasons."""
    data = _load_run_and_findings(engine, run_id)
    if not data["run"]:
        return []
    out: list[FindingPriority] = []
    for row in data["findings"]:
        if row.get("state") != "signal":
            continue
        import json as _json
        try:
            conf = _json.loads(row.get("confidence_json") or "{}")
            overall = float(conf.get("overall", 0.5))
        except (TypeError, ValueError):
            overall = 0.5
        rule = row.get("rule_or_category", "")
        severity = _severity_of(rule)
        # evidence-backed rationale: combine the finding's own
        # rationale with the dimension it's mapped to
        from satsa.analysis.risk import _dimension_for
        dim = _dimension_for(rule)
        rationale = (
            f"{dim} ({severity} severity): {row.get('rationale', '')}"
        )
        out.append(FindingPriority(
            finding_id=row["id"],
            rule_or_category=rule,
            rationale=rationale,
            state=row.get("state", ""),
            severity=severity,
            confidence_overall=overall,
            priority_score=_finding_priority(
                {**row, "severity": severity,
                 "confidence_overall": overall},
                run=data["run"]),
            observation_id=row.get("observation_id", ""),
            worker_name=row.get("worker_name", ""),
        ))
    out.sort(key=lambda p: p.priority_score, reverse=True)
    return out
