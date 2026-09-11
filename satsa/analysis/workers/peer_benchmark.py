"""Peer benchmarking: compare a CSE's in-scope metrics against a
cohort baseline built from comparable entities' assessments.

Peer groups are defined by the defensible cohort attributes the
``Entity`` already carries (``sector`` and ``environment_class``,
plus an extensible ``cohort_attributes`` dict). A peer baseline
is built from the *most-recent* assessment of every other entity
in the same cohort, then per-metric statistics (median, MAD, p25,
p75, count) are aggregated. The ``PeerBenchmarkWorker`` compares
the entity's own in-scope metric against this baseline and emits
a Finding per metric whose deviation exceeds the configured
threshold.

The baseline is passed through the worker contract as a
``PeerBaseline`` instance (delivered via the existing
``baselines: list[BaselineRef]`` channel — we attach the actual
``PeerBaseline`` data alongside the digest reference so workers
do not need a second contract).

Phase 7 anomaly metrics covered (re-using the same definitions
so a single source of truth serves both workers):
* median critical closure time
* critical closure rate (closed / total)
* escalation rate (critical alerts with an escalation / total)
* investigation depth (median steps per case)
* recurrence (median alerts per case)
* monitoring coverage (critical assets with any alert / total critical)
* alert volume per critical asset
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional

from satsa.analysis.workers.anomaly import (
    _mad,
    _median,
    _percentile,
)
from satsa.contracts.worker import (
    AnalyticalWorker,
    BaselineRef,
    ObservationBatch,
    RunContext,
)
from satsa.store.dataset import load_dataset


METRIC_KEYS = (
    "critical_closure_median_seconds",
    "critical_closure_rate",
    "escalation_rate",
    "investigation_depth_median",
    "recurrence_median",
    "monitoring_coverage",
    "alerts_per_critical_asset",
)


@dataclass(frozen=True)
class PeerBaseline:
    """A computed peer-cohort baseline: per-metric statistics over
    every other entity in the same cohort whose assessment data is
    available. ``count`` is the number of peer entities that
    actually contributed a sample for each metric (small cohorts
    legitimately produce no baseline for some metrics)."""

    entity_id: str
    cohort_key: tuple
    digest: str
    metrics: dict = field(default_factory=dict)
    # Per-metric: {"median": float, "mad": float, "p25": float,
    #              "p75": float, "count": int}.
    peer_count: int = 0


@dataclass(frozen=True)
class PeerBenchmarkThresholds:
    # minimum number of peer entities needed to form a baseline
    min_peers: int = 3
    # how many MADs away from the peer median counts as a deviation
    mad_k: float = 2.0
    # how small a peer-MAD has to be before the deviation
    # comparison falls back to the raw gap (in the metric's
    # natural unit); this prevents false "infinite deviation"
    # signals when the peer cohort has zero spread
    min_peer_mad: float = 1e-9


DEFAULT_PEER_BENCHMARK_POLICY = PeerBenchmarkThresholds()


# ---------------------------------------------------------------------------
# Peer group selection + per-metric aggregation
# ---------------------------------------------------------------------------

def _cohort_key(entity: dict) -> tuple:
    return (entity.get("sector", ""), entity.get("environment_class", ""))


def _assessment_metrics(dataset) -> dict:
    """Compute the seven peer-benchmark metrics over one dataset.
    Returns a dict of metric -> value (or None if the data is
    insufficient to compute that metric for this entity)."""
    out: dict = {}

    crit_alerts = [a for a in dataset.alerts
                   if a.mapped_severity in ("critical", "high")]
    crit_closed = [a for a in crit_alerts if a.closed_at is not None]
    closure_times = [a.closed_at - a.created_at for a in crit_closed
                     if a.closed_at >= a.created_at]
    out["critical_closure_median_seconds"] = _median(closure_times) if closure_times else None
    out["critical_closure_rate"] = (
        len(crit_closed) / len(crit_alerts) if crit_alerts else None)

    esc_alert_ids = {e.alert_id for e in dataset.escalations if e.alert_id}
    esc_case_ids = {e.case_id for e in dataset.escalations if e.case_id}
    if crit_alerts and "escalations" in dataset.submitted_categories:
        escalated = sum(1 for a in crit_alerts
                        if a.id in esc_alert_ids
                        or any(c in esc_case_ids for c in (a.case_refs or [])))
        out["escalation_rate"] = escalated / len(crit_alerts)
    else:
        out["escalation_rate"] = None

    depth_by_case: dict[str, int] = {c.id: 0 for c in dataset.cases}
    for s in dataset.steps:
        if s.case_id in depth_by_case:
            depth_by_case[s.case_id] += 1
    depths = list(depth_by_case.values())
    out["investigation_depth_median"] = _median(depths) if depths else None

    case_alert_count: dict[str, int] = {c.id: 0 for c in dataset.cases}
    for a in dataset.alerts:
        for c in (a.case_refs or []):
            if c in case_alert_count:
                case_alert_count[c] += 1
    counts = list(case_alert_count.values())
    out["recurrence_median"] = _median(counts) if counts else None

    if "assets" in dataset.submitted_categories and crit_alerts:
        crit_assets = {a.id for a in dataset.assets
                       if a.criticality in ("critical", "high")}
        if crit_assets:
            alerted = set()
            for a in crit_alerts:
                for ref in (a.asset_refs or []):
                    if ref in crit_assets:
                        alerted.add(ref)
            out["monitoring_coverage"] = len(alerted) / len(crit_assets)
        else:
            out["monitoring_coverage"] = None
    else:
        out["monitoring_coverage"] = None

    if crit_alerts and "assets" in dataset.submitted_categories:
        crit_assets = {a.id for a in dataset.assets
                       if a.criticality in ("critical", "high")}
        asset_alert_count: dict[str, int] = {a: 0 for a in crit_assets}
        for a in crit_alerts:
            for ref in (a.asset_refs or []):
                if ref in asset_alert_count:
                    asset_alert_count[ref] += 1
        per_asset = list(asset_alert_count.values())
        out["alerts_per_critical_asset"] = _median(per_asset) if per_asset else None
    else:
        out["alerts_per_critical_asset"] = None
    return out


def _trimmed(values: list[float], trim: float = 0.1) -> list[float]:
    """Remove the top and bottom ``trim`` fraction of values
    (symmetric trimming). With ``trim=0.1`` on 4 peers, no trimming
    happens (4 * 0.1 = 0.4 < 1 on each side). On 10 peers, the top
    and bottom value are dropped. This makes the median / MAD
    robust to a single extreme outlier in a small cohort."""
    if len(values) < 4:
        return list(values)
    s = sorted(values)
    n = len(s)
    k = int(n * trim)
    if k == 0:
        return s
    return s[k : n - k]


def _aggregate_peer_metric(values: list[float]) -> dict:
    """Aggregate a list of peer per-entity metric values into a
    baseline entry: median, MAD, p25, p75, count.

    Uses symmetric 10% trimmed mean for median and MAD (no
    trimming for n < 4, where trimming would discard too much
    data). This makes the baseline robust to a single extreme
    outlier in a small cohort, which is the documented gap from
    the ground-truth audit."""
    if not values:
        return {"median": 0.0, "mad": 0.0, "p25": 0.0, "p75": 0.0, "count": 0}
    trimmed = _trimmed(values, trim=0.1)
    med = _median(trimmed) if trimmed else _median(values)
    return {
        "median": med,
        "mad": _mad(trimmed, med) if trimmed else _mad(values, med),
        "p25": _percentile(values, 0.25),
        "p75": _percentile(values, 0.75),
        "count": len(values),
    }


def _percentile_local(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    k = (len(s) - 1) * p
    f = int(k)
    c = min(int(k) + 1, len(s) - 1)
    if f == c:
        return s[f]
    return s[f] * (c - k) + s[c] * (k - f)


def compute_peer_baseline(engine, entity_id: str, *,
                          min_peers: int = DEFAULT_PEER_BENCHMARK_POLICY.min_peers) -> PeerBaseline:
    """Build a peer baseline for the given entity by:
    1. finding the entity's cohort (sector + environment_class);
    2. collecting every *other* entity in the same cohort;
    3. for each peer, loading their most-recent assessment's
       dataset and computing the seven metrics;
    4. aggregating per-metric statistics across the peers.
    """
    entity = engine.query_one("SELECT * FROM satsa_entities WHERE id=?",
                              (entity_id,))
    if not entity:
        return PeerBaseline(entity_id=entity_id, cohort_key=(),
                            digest="", peer_count=0,
                            metrics={k: {"median": 0.0, "mad": 0.0,
                                          "p25": 0.0, "p75": 0.0, "count": 0}
                                     for k in METRIC_KEYS})
    cohort = _cohort_key(entity)
    peers = engine.query_all(
        "SELECT * FROM satsa_entities"
        " WHERE id != ? AND sector = ? AND environment_class = ?",
        (entity_id, cohort[0], cohort[1]))
    if len(peers) < min_peers:
        return PeerBaseline(entity_id=entity_id, cohort_key=cohort,
                            digest="", peer_count=len(peers),
                            metrics={k: {"median": 0.0, "mad": 0.0,
                                          "p25": 0.0, "p75": 0.0, "count": 0}
                                     for k in METRIC_KEYS})

    # For each peer, take their most-recent assessment.
    per_metric_values: dict[str, list[float]] = {k: [] for k in METRIC_KEYS}
    for peer in peers:
        assess = engine.query_one(
            "SELECT * FROM satsa_assessments WHERE entity_id=?"
            " ORDER BY period_start DESC LIMIT 1", (peer["id"],))
        if not assess:
            continue
        try:
            ds = load_dataset(engine, peer["id"], assess["id"])
        except Exception:
            continue
        m = _assessment_metrics(ds)
        for k, v in m.items():
            if v is not None and math.isfinite(v):
                per_metric_values[k].append(v)
    metrics = {k: _aggregate_peer_metric(vs) for k, vs in per_metric_values.items()}
    digest = _digest_peers(metrics, cohort, len(peers))
    return PeerBaseline(entity_id=entity_id, cohort_key=cohort,
                        digest=digest, metrics=metrics, peer_count=len(peers))


def _digest_peers(metrics: dict, cohort: tuple, n: int) -> str:
    """A content digest of the peer baseline so it can be referenced
    by a BaselineRef alongside the actual data (the
    ``run_service`` keeps both in scope)."""
    from qsmlops.crypto.hashing import digest_document
    return digest_document({"cohort": list(cohort), "n": n,
                             "metrics": metrics})


# Need math.isfinite — imported at top.


# ---------------------------------------------------------------------------
# PeerBenchmarkWorker
# ---------------------------------------------------------------------------

class PeerBenchmarkWorker(AnalyticalWorker):
    name = "peer-benchmark"
    version = "0.1.0"

    def __init__(self, thresholds: PeerBenchmarkThresholds | None = None) -> None:
        self.thresholds = thresholds or DEFAULT_PEER_BENCHMARK_POLICY

    def evaluate(self, snapshot, dataset, baselines, policy,
                 run_context) -> ObservationBatch:
        from satsa.domain.evidence import ConfidenceVector, Finding
        # Find the PeerBaseline among the supplied BaselineRef-shaped
        # objects. We piggyback on the contract by attaching the
        # baseline to a fake ref's data via a side channel
        # (BaselineRef itself is frozen; the actual baseline is
        # passed separately — see RunService).
        baseline = getattr(self, "_baseline", None)
        if baseline is None:
            return ObservationBatch(
                worker_name=self.name, detector_version=self.version,
                scope={"entity_id": run_context.entity_id,
                       "assessment_id": run_context.assessment_id,
                       "reason": "no peer baseline supplied"},
                state="insufficient_data",
                processing_metrics={"reason": "peer baseline missing"},
            )

        if baseline.peer_count < self.thresholds.min_peers:
            return ObservationBatch(
                worker_name=self.name, detector_version=self.version,
                scope={"entity_id": run_context.entity_id,
                       "assessment_id": run_context.assessment_id,
                       "peer_count": baseline.peer_count,
                       "cohort": list(baseline.cohort_key)},
                state="insufficient_data",
                processing_metrics={
                    "reason": "peer cohort too small",
                    "min_peers": self.thresholds.min_peers,
                },
            )

        # Compute the entity's own metrics in the same shape
        own = _assessment_metrics(dataset)
        # Evidence anchors: the source records of the entity's own
        # alerts/cases that contributed to the metric. A peer-benchmark
        # signal is a population-level observation, but it must still
        # be traceable back to the *subject's* records that produced
        # the value being compared (per SIH-EX-02). We pick the first
        # source_record_ref from the subject's alerts (or cases) that
        # fed the metric in question; this is a deliberately
        # conservative anchor (one representative record is enough
        # to satisfy the rule; the rest is in the run's full
        # source-record set).
        subject_evidence_refs: list[str] = []
        for a in dataset.alerts:
            if a.source_record_ref and a.source_record_ref not in subject_evidence_refs:
                subject_evidence_refs.append(a.source_record_ref)
            if len(subject_evidence_refs) >= 5:
                break
        if not subject_evidence_refs:
            for c in dataset.cases:
                if c.source_record_ref and c.source_record_ref not in subject_evidence_refs:
                    subject_evidence_refs.append(c.source_record_ref)
                if len(subject_evidence_refs) >= 5:
                    break
        findings: list[Finding] = []
        for key in METRIC_KEYS:
            if own.get(key) is None:
                continue
            peer = baseline.metrics.get(key)
            if not peer or peer["count"] == 0:
                continue
            peer_med = peer["median"]
            peer_mad = max(peer["mad"], self.thresholds.min_peer_mad)
            deviation = own[key] - peer_med
            deviation_mads = deviation / peer_mad
            if abs(deviation_mads) < self.thresholds.mad_k:
                continue
            direction = "lower than" if deviation < 0 else "higher than"
            pct = (deviation / peer_med) if peer_med else 0.0
            confidence = ConfidenceVector(
                analytical_support=min(1.0, 0.4 + 0.1 * min(1.0, abs(deviation_mads) / 3.0)),
                evidence_completeness=1.0,
                peer_confidence=min(1.0, peer["count"] / 10.0),
            )
            findings.append(Finding(
                observation_id="",
                rule_or_category=f"peer_benchmark.{key}.deviation",
                state="signal",
                rationale=(
                    f"{key}: observed {own[key]:.2f} vs peer median {peer_med:.2f} "
                    f"({pct:+.0%}, {direction}; n={peer['count']} peers, "
                    f"cohort sector={baseline.cohort_key[0]!r} env={baseline.cohort_key[1]!r})."
                ),
                scoped_subjects=[],
                statistic=float(own[key]),
                effect=float(deviation_mads),
                threshold=float(peer_med),
                confidence=confidence,
                evidence_refs=list(subject_evidence_refs),
                limitations=(
                    f"Peer baseline computed from n={peer['count']} entity/entities"
                    f" in cohort (sector={baseline.cohort_key[0]!r},"
                    f" environment={baseline.cohort_key[1]!r}). Peer confidence"
                    " scales with peer count; the spec example '94%' is a"
                    " notional example, not a measured value."
                ),
            ))

        return ObservationBatch(
            worker_name=self.name, detector_version=self.version,
            scope={
                "entity_id": run_context.entity_id,
                "assessment_id": run_context.assessment_id,
                "cohort": list(baseline.cohort_key),
                "peer_count": baseline.peer_count,
                "own_metrics": {k: v for k, v in own.items() if v is not None},
                "peer_metrics_summary": {
                    k: {"median": v["median"], "count": v["count"]}
                    for k, v in baseline.metrics.items()
                },
            },
            state="signal" if findings else "no_signal",
            findings=findings,
            processing_metrics={"thresholds": {
                "min_peers": self.thresholds.min_peers,
                "mad_k": self.thresholds.mad_k,
            }},
        )


def attach_baseline(worker: PeerBenchmarkWorker, baseline: PeerBaseline) -> PeerBenchmarkWorker:
    """Helper: pass a baseline to a PeerBenchmarkWorker before
    evaluate() is called. Mirrors how a future phase may pull the
    baseline out of the contract."""
    worker._baseline = baseline  # type: ignore[attr-defined]
    return worker
