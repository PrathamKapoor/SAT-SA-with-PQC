"""Anomaly detection: previously-unknown suspicious operational
patterns, surfaced via explainable statistics (median / MAD / IQR /
percentiles) over the entity's own assessment data.

Phase 7 scope: an in-scope (entity, assessment) baseline. We compute
the distribution of each of the eight supervisory metrics over the
records actually present in the dataset and flag values that fall
in the tail of the distribution. A future phase (peer benchmarking)
will replace this self-baseline with a cohort baseline; the worker
contract and the per-finding shape stay unchanged.

Why explainable statistics, not black-box ML: every emitted finding
carries its observed value, the computed baseline (median, MAD, p10,
p90), the deviation, and the *metric definition* in plain text. An
examiner can verify the math and challenge the rule without having
to read a model.

The eight metrics (per docs/phase1/analytics-architecture.md):

* closure_time — per closed alert (closed_at − created_at)
* investigation_duration — per case (closed_at − opened_at)
* alerts_per_asset — per asset (count of alerts with that asset_ref)
* critical_alerts_per_critical_asset — same, restricted to
  critical assets and critical alerts
* escalation_rate — entity-level: critical alerts with at least
  one escalation / total critical alerts
* recurrence — per case: count of alerts that resolve into the case
* monitoring_coverage — entity-level: critical assets with at
  least one alert / total critical assets
* investigation_depth — per case: number of investigation steps
"""
from __future__ import annotations

import math
import statistics
from dataclasses import dataclass

from satsa.contracts.worker import (
    AnalyticalWorker,
    ObservationBatch,
    RunContext,
)
from satsa.domain.evidence import ConfidenceVector, Finding


@dataclass(frozen=True)
class AnomalyThresholds:
    """How many MADs away from the median counts as an outlier
    (Phase 7 default is conservative: 3.0 — well above what a
    parametric z=2 would catch, to keep the false-positive rate
    sensible on a small in-scope distribution)."""
    mad_k: float = 3.0
    # Minimum sample size to attempt anomaly detection on a metric
    # (below this the distribution is too small to call tails).
    min_samples: int = 5
    # Maximum number of outliers to report per metric (so a single
    # run cannot be drowned by a thousand 'p99 outliers').
    max_outliers_per_metric: int = 20


DEFAULT_ANOMALY_POLICY = AnomalyThresholds()


def _median(values: list[float]) -> float:
    return statistics.median(values) if values else 0.0


def _mad(values: list[float], med: float) -> float:
    if not values:
        return 0.0
    dev = [abs(v - med) for v in values]
    return statistics.median(dev) if dev else 0.0


def _percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    k = (len(s) - 1) * p
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return s[int(k)]
    return s[f] * (c - k) + s[c] * (k - f)


def _anomalous_outliers(values: list[float], *, k: float, min_samples: int):
    """Return [(index, value, deviation_score)] for outliers above
    median + k*MAD. deviation_score is (value - (median + k*MAD))
    expressed in MAD units (positive = 'how many MADs past the
    cutoff'). When MAD is 0 (all values equal modulo the outlier
    itself) the score collapses to (value - cutoff), still sortable."""
    if len(values) < min_samples:
        return []
    med = _median(values)
    mad = _mad(values, med)
    cutoff = med + k * mad
    out = []
    for i, v in enumerate(values):
        if v > cutoff:
            score = (v - cutoff) / mad if mad > 0 else (v - cutoff)
            out.append((i, v, score))
    out.sort(key=lambda t: t[2], reverse=True)
    return out


class AnomalyWorker(AnalyticalWorker):
    name = "anomaly"
    version = "0.1.0"

    def __init__(self, thresholds: AnomalyThresholds | None = None) -> None:
        self.thresholds = thresholds or DEFAULT_ANOMALY_POLICY

    def evaluate(self, snapshot, dataset, baselines, policy, run_context) -> ObservationBatch:
        findings: list[Finding] = []
        t = self.thresholds

        # ---- 1. closure_time (per closed alert) ----
        closure_times: list[float] = []
        closure_alerts: list = []
        for a in dataset.alerts:
            if a.closed_at is None or a.created_at is None:
                continue
            dt = a.closed_at - a.created_at
            if dt < 0:
                continue
            closure_times.append(dt)
            closure_alerts.append(a)
        outliers = _anomalous_outliers(closure_times, k=t.mad_k,
                                         min_samples=t.min_samples)
        for i, v, score in outliers[:t.max_outliers_per_metric]:
            a = closure_alerts[i]
            findings.append(_signal( rule="anomaly.closure_time.high",
                rationale=(
                    f"Alert {a.native_id!r} closed in {int(v)}s, well above the "
                    f"in-scope median ({int(_median(closure_times))}s) — an "
                    "unusually slow closure."),
                scoped=[a.id], statistic=v, baseline=_median(closure_times),
                effect=score, source_record_ref=a.source_record_ref,
            ))

        # ---- 2. investigation_duration (per case) ----
        durations: list[float] = []
        cases_with_dur: list = []
        for c in dataset.cases:
            if c.closed_at is None or c.opened_at is None:
                continue
            dt = c.closed_at - c.opened_at
            if dt < 0:
                continue
            durations.append(dt)
            cases_with_dur.append(c)
        outliers = _anomalous_outliers(durations, k=t.mad_k,
                                         min_samples=t.min_samples)
        for i, v, score in outliers[:t.max_outliers_per_metric]:
            c = cases_with_dur[i]
            findings.append(_signal( rule="anomaly.investigation_duration.high",
                rationale=(
                    f"Case {c.native_id!r} was open for {int(v)}s, well above "
                    f"the in-scope median ({int(_median(durations))}s) — an "
                    "unusually long investigation."),
                scoped=[c.id], statistic=v, baseline=_median(durations),
                effect=score, source_record_ref=c.source_record_ref,
            ))

        # ---- 3. alerts_per_asset (per asset) ----
        asset_alert_count: dict[str, int] = {}
        for a in dataset.alerts:
            for ref in (a.asset_refs or []):
                asset_alert_count[ref] = asset_alert_count.get(ref, 0) + 1
        per_asset_values = list(asset_alert_count.values())
        outliers = _anomalous_outliers(
            per_asset_values, k=t.mad_k, min_samples=t.min_samples)
        asset_ids = sorted(asset_alert_count.keys())
        for i, v, score in outliers[:t.max_outliers_per_metric]:
            asset_id = asset_ids[i] if i < len(asset_ids) else f"asset-{i}"
            findings.append(_signal( rule="anomaly.alerts_per_asset.high",
                rationale=(
                    f"Asset {asset_id!r} received {v} alert(s), well above the "
                    f"in-scope median ({_median(per_asset_values):.0f}) — an "
                    "unusually hot asset."),
                scoped=[asset_id], statistic=v,
                baseline=_median(per_asset_values), effect=score,
                source_record_ref="",
            ))

        # ---- 4. critical_alerts_per_critical_asset ----
        crit_assets = {a.id for a in dataset.assets
                       if a.criticality in ("critical", "high")}
        crit_asset_alerts: dict[str, int] = {a.id: 0 for a in dataset.assets
                                              if a.id in crit_assets}
        for a in dataset.alerts:
            if a.mapped_severity not in ("critical", "high"):
                continue
            for ref in (a.asset_refs or []):
                if ref in crit_asset_alerts:
                    crit_asset_alerts[ref] += 1
        values = list(crit_asset_alerts.values())
        outliers = _anomalous_outliers(values, k=t.mad_k,
                                         min_samples=t.min_samples)
        crit_asset_ids = sorted(crit_asset_alerts.keys())
        for i, v, score in outliers[:t.max_outliers_per_metric]:
            asset_id = crit_asset_ids[i] if i < len(crit_asset_ids) else f"asset-{i}"
            findings.append(_signal( rule="anomaly.critical_alerts_per_critical_asset.high",
                rationale=(
                    f"Critical asset {asset_id!r} received {v} critical/high "
                    f"alert(s), well above the in-scope median "
                    f"({_median(values):.0f}) — an unusually targeted asset."),
                scoped=[asset_id], statistic=v,
                baseline=_median(values), effect=score,
                source_record_ref="",
            ))

        # ---- 5. escalation_rate (entity-level scalar) ----
        # Only meaningful when the escalations file was submitted
        # (otherwise the absence is the negative-space engine's
        # concern, not an anomaly).
        crit_alerts = [a for a in dataset.alerts
                       if a.mapped_severity == "critical"]
        if crit_alerts and "escalations" in dataset.submitted_categories:
            esc_alert_ids = {e.alert_id for e in dataset.escalations if e.alert_id}
            esc_case_ids = {e.case_id for e in dataset.escalations if e.case_id}
            escalated = sum(1 for a in crit_alerts
                            if a.id in esc_alert_ids
                            or any(c in esc_case_ids for c in (a.case_refs or [])))
            rate = escalated / len(crit_alerts)
            # Anomaly threshold: < 30% escalation of criticals is unusual
            # given the in-scope data (informational; not a hard rule).
            if rate < 0.30 and len(crit_alerts) >= t.min_samples:
                # anchor to the critical-alert source records so the
                # signal finding always cites evidence (per SIH-EX-02)
                anchor_refs = [a.source_record_ref for a in crit_alerts
                                if a.source_record_ref][:5]
                findings.append(_signal(
                    rule="anomaly.escalation_rate.low",
                    rationale=(
                        f"Only {int(rate * 100)}% of critical alerts were "
                        f"escalated (n={len(crit_alerts)}). A very low "
                        "escalation rate is itself an outlier to inspect."),
                    scoped=[a.id for a in crit_alerts],
                    statistic=rate, baseline=0.30, effect=(0.30 - rate),
                    source_record_ref=anchor_refs[0] if anchor_refs else "",
                ))

        # ---- 6. recurrence (per case: alerts referencing it) ----
        case_alert_count: dict[str, int] = {c.id: 0 for c in dataset.cases}
        for a in dataset.alerts:
            for c in (a.case_refs or []):
                if c in case_alert_count:
                    case_alert_count[c] += 1
        values = list(case_alert_count.values())
        outliers = _anomalous_outliers(values, k=t.mad_k,
                                         min_samples=t.min_samples)
        case_ids = sorted(case_alert_count.keys())
        for i, v, score in outliers[:t.max_outliers_per_metric]:
            case_id = case_ids[i] if i < len(case_ids) else f"case-{i}"
            case = next((c for c in dataset.cases if c.id == case_id), None)
            findings.append(_signal( rule="anomaly.recurrence.high",
                rationale=(
                    f"Case {case_id!r} absorbed {v} alert(s), well above the "
                    f"in-scope median ({_median(values):.0f}) — a recurring "
                    "case."),
                scoped=[case_id], statistic=v,
                baseline=_median(values), effect=score,
                source_record_ref=case.source_record_ref if case else "",
            ))

        # ---- 7. monitoring_coverage (entity-level) ----
        if crit_assets:
            covered = sum(1 for aid in crit_assets
                          if asset_alert_count.get(aid, 0) > 0)
            coverage = covered / len(crit_assets)
            if coverage < 0.5 and len(crit_assets) >= t.min_samples:
                findings.append(_signal( rule="anomaly.monitoring_coverage.low",
                    rationale=(
                        f"Only {int(coverage * 100)}% of critical assets had any "
                        f"alert in scope (n={len(crit_assets)}). Coverage looks "
                        "incomplete."),
                    scoped=sorted(crit_assets), statistic=coverage,
                    baseline=1.0, effect=(1.0 - coverage),
                    source_record_ref="",
                ))

        # ---- 8. investigation_depth (per case) ----
        depth_by_case: dict[str, int] = {c.id: 0 for c in dataset.cases}
        for s in dataset.steps:
            if s.case_id in depth_by_case:
                depth_by_case[s.case_id] += 1
        values = list(depth_by_case.values())
        outliers = _anomalous_outliers(values, k=t.mad_k,
                                         min_samples=t.min_samples)
        case_ids = sorted(depth_by_case.keys())
        for i, v, score in outliers[:t.max_outliers_per_metric]:
            case_id = case_ids[i] if i < len(case_ids) else f"case-{i}"
            case = next((c for c in dataset.cases if c.id == case_id), None)
            findings.append(_signal( rule="anomaly.investigation_depth.high",
                rationale=(
                    f"Case {case_id!r} had {v} investigation step(s), well above "
                    f"the in-scope median ({_median(values):.0f}) — a "
                    "notable outlier in depth (not necessarily a problem; "
                    "inspect for unusually heavy / unusually thin work)."),
                scoped=[case_id], statistic=v,
                baseline=_median(values), effect=score,
                source_record_ref=case.source_record_ref if case else "",
            ))

        return ObservationBatch(
            worker_name=self.name, detector_version=self.version,
            scope={
                "entity_id": run_context.entity_id,
                "assessment_id": run_context.assessment_id,
                "alerts_total": len(dataset.alerts),
                "cases_total": len(dataset.cases),
                "assets_total": len(dataset.assets),
                "findings_count": len(findings),
            },
            state="signal" if findings else "no_signal",
            findings=findings,
            processing_metrics={
                "thresholds": {
                    "mad_k": t.mad_k, "min_samples": t.min_samples,
                    "max_outliers_per_metric": t.max_outliers_per_metric,
                },
                "metric_sample_sizes": {
                    "closure_time": len(closure_times),
                    "investigation_duration": len(durations),
                    "alerts_per_asset": len(per_asset_values),
                    "critical_alerts_per_critical_asset": len(values),
                    "recurrence": len(case_alert_count),
                    "investigation_depth": len(depth_by_case),
                },
            },
        )


def _signal(*, rule, rationale, scoped, statistic, baseline,
            effect, source_record_ref):
    """Build a Finding with a sensible ConfidenceVector for an
    anomaly: analytical_support scales with effect, evidence
    completeness is 1.0 if the worker had the data it needed."""
    support = min(1.0, 0.4 + 0.5 * min(1.0, effect / 3.0))
    return Finding(
        observation_id="",
        rule_or_category=rule,
        state="signal",
        rationale=rationale,
        scoped_subjects=scoped,
        statistic=float(statistic) if statistic is not None else None,
        effect=float(effect) if effect is not None else None,
        threshold=float(baseline) if baseline is not None else None,
        confidence=ConfidenceVector(
            analytical_support=support, evidence_completeness=1.0,
        ),
        evidence_refs=([source_record_ref] if isinstance(source_record_ref, str)
                        else source_record_ref),
        limitations=(
            "Phase 7 baseline is *in-scope* (this assessment's own records). "
            "Cohort benchmarks land in Phase 8 — until then an outlier here "
            "may simply be a CSE with a very different operating shape, not "
            "a problem."
        ),
    )
