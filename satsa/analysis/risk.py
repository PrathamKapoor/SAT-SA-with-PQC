"""Entity risk engine: aggregate a run's findings into a single
decomposable supervisory risk profile.

Why a separate engine and not just a per-finding summary? A
supervisor's first question is "which entity is most worth my
time?". That is a *per-entity* question, and the answer must be
explainable — "82 because {26 from execution gap, 14 from peer
deviation, 12 from anomaly, …}" — not a single opaque number.

The engine takes the findings from the most-recent completed
AnalysisRun for the entity and produces:

* a per-dimension risk score (0..weight, with documented weights),
* a total risk score (sum, capped at 100),
* a tree-shaped decomposition (total → dimensions → findings),
* a confidence bucket ("very_low" / "low" / "medium" / "high")
  derived from the average confidence.overall of the contributing
  findings, so the UI can show "82 (high confidence)" not just 82.

Weights (documented, not invented):

| Dimension            | Weight | Why |
|----------------------|--------|-----|
| execution_gap        |     25 | the SIH core signal class; directly tested in the spec |
| peer_deviation       |     20 | externally-anchored, hardest for a CSE to dismiss |
| detection_gap        |     15 | missing monitoring/alerting is a system-level risk |
| negative_space       |     15 | absence of expected evidence is the spec's 6th category |
| anomaly              |     15 | in-scope outliers, complementary to peer deviation |
| investigation_quality|      5 | shallow-playbook signals; important but tactical |
| escalation_discipline|      5 | single-rule dimension; supplements execution_gap |
| **total**            | **100**| |

The weights are documented here and in the persisted risk
profile's `weights` block; changing them is a one-line edit and
is observable (the profile carries the weights it was computed
with).
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional


DIMENSION_WEIGHTS: dict[str, int] = {
    "execution_gap": 25,
    "peer_deviation": 20,
    "detection_gap": 15,
    "negative_space": 15,
    "anomaly": 15,
    "investigation_quality": 5,
    "escalation_discipline": 5,
}
TOTAL_WEIGHT = sum(DIMENSION_WEIGHTS.values())  # 100


def _dimension_for(rule: str) -> str:
    """Map a rule_or_category to its risk dimension. Unknown rules
    are bucketed into 'anomaly' by default (it is the
    catch-all dimension for unmodelled signals)."""
    if rule.startswith("execution_gap."):
        return "execution_gap"
    if rule.startswith("peer_benchmark."):
        return "peer_deviation"
    if rule.startswith("negative_space."):
        return "negative_space"
    if rule.startswith("anomaly."):
        return "anomaly"
    # detection_gap covers missing monitoring / missing coverage
    if "monitoring" in rule or "detection" in rule or "coverage" in rule:
        return "detection_gap"
    if "escalation" in rule:
        return "escalation_discipline"
    if ("investigation" in rule or "depth" in rule
            or "recurrence" in rule or "metric_gaming" in rule):
        return "investigation_quality"
    return "anomaly"


@dataclass
class DimensionRisk:
    name: str
    weight: int
    score: float
    finding_ids: list = field(default_factory=list)
    rationale: str = ""

    def to_dict(self) -> dict:
        return {
            "name": self.name, "weight": self.weight,
            "score": round(self.score, 2),
            "finding_ids": list(self.finding_ids),
            "rationale": self.rationale,
        }


@dataclass
class EntityRiskProfile:
    entity_id: str
    run_id: Optional[str]
    total_score: float
    confidence_bucket: str
    dimensions: list  # list[DimensionRisk]
    weights: dict

    def to_dict(self) -> dict:
        return {
            "entity_id": self.entity_id, "run_id": self.run_id,
            "total_score": round(self.total_score, 2),
            "confidence_bucket": self.confidence_bucket,
            "dimensions": [d.to_dict() for d in self.dimensions],
            "weights": dict(self.weights),
        }

    def decomposition(self) -> dict:
        """Tree-shaped decomposition for the UI: total → dimensions
        → finding_ids. Always decomposable, never a single number."""
        return {
            "total": round(self.total_score, 2),
            "dimensions": {d.name: {
                "score": round(d.score, 2),
                "weight": d.weight,
                "finding_ids": list(d.finding_ids),
            } for d in self.dimensions},
        }


def _confidence_overall(finding: dict) -> float:
    """Extract a 0-1 'overall' from a finding row's confidence_json.
    Falls back to 0.5 when confidence is missing — a deliberately
    neutral default, not zero (zero would never contribute and bias
    the totals toward 0)."""
    raw = finding.get("confidence_json") or "{}"
    import json
    try:
        c = json.loads(raw) if isinstance(raw, str) else raw
    except (TypeError, ValueError):
        return 0.5
    if not c:
        return 0.5
    return float(c.get("overall", 0.5))


def _confidence_bucket(avg_conf: float) -> str:
    if avg_conf < 0.25:
        return "very_low"
    if avg_conf < 0.5:
        return "low"
    if avg_conf < 0.75:
        return "medium"
    return "high"


def compute_entity_risk(engine, entity_id: str, *,
                        run_id: Optional[str] = None) -> EntityRiskProfile:
    """Build a risk profile for ``entity_id`` from a specific run
    (or, if ``run_id`` is None, the most-recent completed run)."""
    rows_engine = engine
    if run_id is None:
        # Find the most recent completed (or partial) run for this entity
        row = rows_engine.query_one(
            "SELECT * FROM satsa_runs WHERE entity_id=?"
            " AND status IN ('completed','partial')"
            " ORDER BY created_at DESC LIMIT 1", (entity_id,))
        if not row:
            return EntityRiskProfile(
                entity_id=entity_id, run_id=None, total_score=0.0,
                confidence_bucket="very_low", dimensions=[],
                weights=dict(DIMENSION_WEIGHTS))
        run_id = row["id"]
    finding_rows = rows_engine.query_all(
        "SELECT * FROM satsa_findings"
        " WHERE observation_id IN (SELECT id FROM satsa_observations WHERE run_id=?)"
        " ORDER BY created_at", (run_id,))

    by_dimension: dict[str, list] = {k: [] for k in DIMENSION_WEIGHTS}
    for f in finding_rows:
        if f.get("state") != "signal":
            continue
        dim = _dimension_for(f.get("rule_or_category", ""))
        by_dimension[dim].append(f)

    dims: list[DimensionRisk] = []
    total = 0.0
    for dim_name, weight in DIMENSION_WEIGHTS.items():
        findings = by_dimension.get(dim_name, [])
        # Each finding contributes up to its full dimension weight,
        # scaled by confidence.overall. A single finding can never
        # push a dimension above its weight; a single very-strong
        # finding and many weak ones are both legitimate.
        raw = sum(_confidence_overall(f) for f in findings)
        # Use a saturating curve so many low-confidence findings
        # still cap at the dimension weight.
        score = weight * (1 - (1 / (1 + raw))) if raw else 0.0
        # round to 2 decimals for stable display
        score = round(score, 2)
        total += score
        # rationale describes the dimension + the source findings
        if not findings:
            rationale = f"No findings in this dimension (weight {weight})."
        else:
            top = sorted(findings,
                         key=lambda f: _confidence_overall(f),
                         reverse=True)[:3]
            rule_summary = ", ".join(
                f.get("rule_or_category", "?") for f in top)
            rationale = (
                f"{len(findings)} finding(s) in this dimension; "
                f"top contributors: {rule_summary}.")
        dims.append(DimensionRisk(
            name=dim_name, weight=weight, score=score,
            finding_ids=[f["id"] for f in findings],
            rationale=rationale,
        ))

    # Confidence bucket: average overall confidence of the
    # contributing signal findings (0 if none).
    if finding_rows:
        avg_conf = sum(_confidence_overall(f) for f in finding_rows) / len(finding_rows)
    else:
        avg_conf = 0.0
    return EntityRiskProfile(
        entity_id=entity_id, run_id=run_id,
        total_score=min(TOTAL_WEIGHT, total),  # cap at 100
        confidence_bucket=_confidence_bucket(avg_conf),
        dimensions=dims, weights=dict(DIMENSION_WEIGHTS),
    )
