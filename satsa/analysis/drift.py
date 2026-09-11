"""Supervisory drift / trend analytics.

Compare an entity's current assessment against its previous
assessment and emit trend findings. Every drift finding is
explicit about:

* which period is the baseline,
* which metric changed,
* the direction and magnitude,
* the data limitations (e.g. "only two periods of data").

This is NOT a black-box trend model. It is a deterministic
delta on a fixed set of metrics.
"""
from __future__ import annotations

import statistics
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from satsa.store.dataset import CanonicalDataset


# The fixed metric set we track across periods. These are the
# metrics the existing analytics compute per-assessment; drift
# compares their current value to the previous value.
DRIFT_METRICS = (
    "critical_closure_rate",
    "critical_closure_median_seconds",
    "escalation_rate",
    "investigation_depth_median",
    "recurrence_median",
    "monitoring_coverage",
)


@dataclass
class DriftFinding:
    entity_id: str
    metric: str
    previous: float
    current: float
    delta: float
    relative_delta: float
    direction: str
    limitations: str

    def to_dict(self) -> dict:
        return {
            "entity_id": self.entity_id,
            "metric": self.metric,
            "previous": round(self.previous, 4),
            "current": round(self.current, 4),
            "delta": round(self.delta, 4),
            "relative_delta": round(self.relative_delta, 4),
            "direction": self.direction,
            "limitations": self.limitations,
        }


def _direction(prev: float, curr: float) -> str:
    if curr > prev:
        return "increased"
    if curr < prev:
        return "decreased"
    return "unchanged"


def compute_drift(entity_id: str,
                 previous_metrics: dict[str, float],
                 current_metrics: dict[str, float],
                 *,
                 relative_threshold: float = 0.2) -> list[DriftFinding]:
    """Compare two periods' metric dicts. Emit a drift finding for
    every metric whose relative change is >= ``relative_threshold``
    (default 20%). A note about data limitations is always
    included.

    If either dict is empty, no findings are emitted (the
    ``limitations`` note would simply say "no baseline" or
    "no current" — we choose to not emit a finding in that
    case rather than invent one)."""
    if not previous_metrics or not current_metrics:
        return []
    findings: list[DriftFinding] = []
    limitations = (
        f"Drift computed from {len(previous_metrics)} and "
        f"{len(current_metrics)} metric values. Two data points do "
        "not establish a trend; treat as a signal, not a conclusion."
    )
    for metric in DRIFT_METRICS:
        if metric not in previous_metrics or metric not in current_metrics:
            continue
        prev = previous_metrics[metric]
        curr = current_metrics[metric]
        if prev == 0 and curr == 0:
            continue
        # relative delta: if prev is 0, treat any non-zero curr as
        # infinite change → cap at 1.0 for the report.
        if prev == 0:
            rel = 1.0 if curr != 0 else 0.0
        else:
            rel = (curr - prev) / abs(prev)
        if abs(rel) < relative_threshold:
            continue
        findings.append(DriftFinding(
            entity_id=entity_id, metric=metric,
            previous=prev, current=curr,
            delta=curr - prev, relative_delta=rel,
            direction=_direction(prev, curr),
            limitations=limitations,
        ))
    return findings


def compute_kpis(dataset) -> dict[str, float]:
    """Derive the fixed DRIFT_METRICS dict from a CanonicalDataset.

    The metrics are deterministic, explainable counters/rates — no
    black-box model. Metrics that cannot be computed from this
    dataset (e.g. no critical alerts → no closure rate) are
    omitted, not set to zero; ``compute_drift`` then naturally
    ignores them and emits no finding. This is the honest
    no-fabrication contract.
    """
    metrics: dict[str, float] = {}

    alerts = list(getattr(dataset, "alerts", []) or [])
    cases = list(getattr(dataset, "cases", []) or [])
    escalations = list(getattr(dataset, "escalations", []) or [])
    steps = list(getattr(dataset, "steps", []) or [])
    assets = list(getattr(dataset, "assets", []) or [])

    # critical_closure_rate: closed critical alerts / total critical alerts
    critical = [a for a in alerts if a.mapped_severity == "critical"]
    if critical:
        closed = sum(1 for a in critical if a.closed_at is not None)
        metrics["critical_closure_rate"] = closed / len(critical)

    # critical_closure_median_seconds: median(closed_at - created_at)
    durations: list[float] = []
    for a in critical:
        if a.closed_at is not None and a.created_at is not None:
            durations.append(float(a.closed_at) - float(a.created_at))
    if durations:
        metrics["critical_closure_median_seconds"] = statistics.median(durations)

    # escalation_rate: escalations tied to critical alerts / critical alerts
    if critical:
        crit_ids = {a.id for a in critical}
        crit_escalations = sum(
            1 for e in escalations
            if (e.alert_id and e.alert_id in crit_ids))
        metrics["escalation_rate"] = crit_escalations / len(critical)

    # investigation_depth_median: median steps-per-case
    if cases:
        steps_by_case: dict[str, int] = {}
        for s in steps:
            steps_by_case[s.case_id] = steps_by_case.get(s.case_id, 0) + 1
        # include cases with zero steps so the median reflects reality
        depths = [steps_by_case.get(c.id, 0) for c in cases]
        metrics["investigation_depth_median"] = statistics.median(depths)

    # recurrence_median: median(alert count) per asset referenced by alerts
    if assets:
        asset_ids = {a.id for a in assets}
        per_asset: list[int] = []
        for a in assets:
            count = sum(1 for al in alerts if al.asset_refs and a.id in al.asset_refs)
            per_asset.append(count)
        if per_asset:
            metrics["recurrence_median"] = statistics.median(per_asset)

    # monitoring_coverage: assets referenced by at least one alert / total assets
    if assets:
        referenced = sum(
            1 for a in assets
            if any(al.asset_refs and a.id in al.asset_refs for al in alerts))
        metrics["monitoring_coverage"] = referenced / len(assets)

    return metrics


def collect_evidence_refs(dataset) -> list[str]:
    """Collect the source-record refs the current-period KPIs were
    computed from, so a drift Finding's evidence_refs is honest
    (SIH-EX-02: a score without explanation is insufficient)."""
    refs: list[str] = []
    for a in getattr(dataset, "alerts", []) or []:
        if a.source_record_ref:
            refs.append(a.source_record_ref)
    # dedupe, preserve order
    seen: set[str] = set()
    out: list[str] = []
    for r in refs:
        if r not in seen:
            seen.add(r)
            out.append(r)
    return out
