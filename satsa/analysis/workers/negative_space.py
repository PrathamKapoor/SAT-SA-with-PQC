"""Negative-space detection: absence of evidence that should be there.

A negative-space finding says "this thing is *missing*, not
'wrong'." Per docs/phase1/analytics-architecture.md the negative-
space engine must distinguish "absence in reality" from "absence
from submission" — a CSE that did not submit a file at all is
structurally different from one that submitted an empty one, even
if both look 'low activity' on the surface. The worker reports
data-completeness for every negative-space finding so the human
reviewer can interpret it correctly.

Six categories of negative space, per the Phase 6 spec:

* missing file (one of the six SIH categories was not submitted at
  all — a *data-completeness* finding, not a CSE-conduct finding;
  the engine still reports it because it gates everything else)
* missing investigation (a case with no investigation steps at all)
* missing escalation (a critical alert with no escalation AND no
  linked escalated case — note: this is the same data the
  ``critical-without-escalation`` worker reads, but the negative-
  space framing here covers alerts that may also be missing their
  escalation **record** entirely because the escalations file
  was never submitted)
* missing disposition (a closed alert/case with no disposition
  record)
* missing monitoring (critical assets with zero alerts in scope —
  which is a real signal, *unless* the asset inventory was itself
  not submitted, in which case we cannot know)
* unexpectedly low activity (a non-trivial alert volume that is
  suspiciously low given a critical-asset-heavy inventory; only
  fires when the data is rich enough to support the comparison)
"""
from __future__ import annotations

from dataclasses import dataclass

from satsa.contracts.worker import (
    AnalyticalWorker,
    ObservationBatch,
    RunContext,
)
from satsa.store.dataset import CanonicalDataset


ALL_CATEGORIES = ("alerts", "cases", "investigation_steps",
                  "escalations", "dispositions", "assets")


@dataclass(frozen=True)
class NegativeSpaceThresholds:
    # Cases need at least 1 step to be considered investigated.
    min_investigation_steps: int = 1
    # Critical assets must have at least this many alerts to count as
    # 'monitored' (0 alerts on a critical asset is itself a signal).
    min_alerts_per_critical_asset: int = 1
    # Minimum inventory size before 'low activity' is meaningful.
    min_critical_assets: int = 2
    # Below this alert volume we do not raise a low-activity finding
    # even if the ratio is low — small absolute counts are noise.
    min_alert_volume_for_low_activity: int = 3


DEFAULT_NEGATIVE_SPACE_POLICY = NegativeSpaceThresholds()


def _data_completeness(dataset: CanonicalDataset) -> dict:
    """What fraction of the six SIH categories did the CSE submit?
    Returned as a {category: bool} dict the worker includes in every
    finding's limitations string and in the ObservationBatch scope —
    a negative-space finding is only actionable when its data
    category was actually submitted."""
    return {c: c in dataset.submitted_categories for c in ALL_CATEGORIES}


class NegativeSpaceWorker(AnalyticalWorker):
    name = "negative-space"
    version = "0.1.0"

    def __init__(self, thresholds: NegativeSpaceThresholds | None = None) -> None:
        self.thresholds = thresholds or DEFAULT_NEGATIVE_SPACE_POLICY

    def evaluate(self, snapshot, dataset, baselines, policy, run_context) -> ObservationBatch:
        from satsa.domain.evidence import ConfidenceVector, Finding

        completeness = _data_completeness(dataset)
        findings: list[Finding] = []

        # -- 1. Missing file: a category that was never submitted ----
        for cat in ALL_CATEGORIES:
            if not completeness[cat]:
                findings.append(Finding(
                    observation_id="",
                    rule_or_category=f"negative_space.missing_file.{cat}",
                    state="insufficient_data",
                    rationale=(
                        f"No {cat} file was submitted for this assessment. The "
                        "engine cannot evaluate any {cat}-dependent rule for "
                        "this scope; the analysis is structurally incomplete.".format(cat=cat)
                    ),
                    scoped_subjects=[],
                    statistic=0.0,
                    effect=0.0,
                    threshold=0.0,
                    confidence=ConfidenceVector(
                        analytical_support=1.0,  # the data simply isn't there
                        evidence_completeness=0.0,
                    ),
                    evidence_refs=[],
                    limitations=(
                        "Data-completeness finding, NOT a CSE-conduct finding. "
                        "Resolve by re-ingesting with the missing category present."
                    ),
                ))

        # -- 2. Missing investigation: cases with zero steps ----------
        if completeness["cases"] and completeness["investigation_steps"]:
            steps_per_case: dict[str, int] = {}
            for s in dataset.steps:
                steps_per_case[s.case_id] = steps_per_case.get(s.case_id, 0) + 1
            uninvestigated = [c for c in dataset.cases
                              if steps_per_case.get(c.id, 0) < self.thresholds.min_investigation_steps]
            if uninvestigated:
                findings.append(Finding(
                    observation_id="",
                    rule_or_category="negative_space.missing_investigation",
                    state="signal",
                    rationale=(
                        f"{len(uninvestigated)} case(s) have zero investigation "
                        "steps recorded. A case without any recorded action is "
                        "either a data-quality problem or a workflow gap."
                    ),
                    scoped_subjects=[c.id for c in uninvestigated],
                    statistic=float(len(uninvestigated)),
                    effect=min(1.0, len(uninvestigated) / max(1, len(dataset.cases))),
                    threshold=float(self.thresholds.min_investigation_steps),
                    confidence=ConfidenceVector(
                        analytical_support=0.7,
                        evidence_completeness=1.0 if completeness["investigation_steps"] else 0.0,
                    ),
                    evidence_refs=[c.source_record_ref for c in uninvestigated if c.source_record_ref],
                    limitations=(
                        "Zero-step detection is a coarse check; legitimate "
                        "one-touch closures (e.g. auto-resolved noise) will "
                        "appear here."
                    ),
                ))

        # -- 3. Missing escalation: critical alerts with no escalation
        #       AND no linked escalated case -----------------------
        if completeness["alerts"]:
            esc_alert_ids = {e.alert_id for e in dataset.escalations if e.alert_id}
            esc_case_ids = {e.case_id for e in dataset.escalations if e.case_id}
            unesc = [a for a in dataset.alerts
                     if a.mapped_severity == "critical"
                     and a.id not in esc_alert_ids
                     and not any(c in esc_case_ids for c in (a.case_refs or []))]
            if unesc:
                # If escalations was *not* submitted, we still flag this
                # — every critical alert trivially has "no escalation
                # record" when the whole category is absent — but with
                # attenuated effect/confidence below, since this is also
                # separately covered by negative_space.missing_file.
                # escalations (a pure data-completeness finding) and we
                # cannot distinguish "no escalation happened" from "no
                # escalation was ever recorded" without the file.
                effect = (0.6 if completeness["escalations"] else 0.3)
                findings.append(Finding(
                    observation_id="",
                    rule_or_category="negative_space.missing_escalation",
                    state="signal",
                    rationale=(
                        f"{len(unesc)} critical alert(s) have no recorded "
                        "escalation, and no linked case was escalated either."
                    ),
                    scoped_subjects=[a.id for a in unesc],
                    statistic=float(len(unesc)),
                    effect=effect,
                    threshold=1.0,
                    confidence=ConfidenceVector(
                        analytical_support=0.6,
                        evidence_completeness=(1.0 if completeness["escalations"] else 0.0),
                    ),
                    evidence_refs=[a.source_record_ref for a in unesc if a.source_record_ref],
                    limitations=(
                        "If the escalations file was not submitted, this finding "
                        "is a *data-completeness* signal as well as a possible "
                        "conduct signal; resolve by re-ingesting first."
                    ),
                ))

        # -- 4. Missing disposition: closed alerts with no disposition -
        if completeness["alerts"]:
            disp_alert_ids = {d.alert_id for d in dataset.dispositions if d.alert_id}
            disp_case_ids = {d.case_id for d in dataset.dispositions if d.case_id}
            no_disp = [a for a in dataset.alerts
                       if a.closed_at is not None
                       and a.id not in disp_alert_ids
                       and not any(c in disp_case_ids for c in (a.case_refs or []))]
            if no_disp and completeness["dispositions"]:
                findings.append(Finding(
                    observation_id="",
                    rule_or_category="negative_space.missing_disposition",
                    state="signal",
                    rationale=(
                        f"{len(no_disp)} closed alert(s) have no disposition "
                        "record. The closure decision (true positive / false "
                        "positive / benign / etc.) was not captured."
                    ),
                    scoped_subjects=[a.id for a in no_disp],
                    statistic=float(len(no_disp)),
                    effect=min(1.0, len(no_disp) / max(1, len(dataset.alerts))),
                    threshold=1.0,
                    confidence=ConfidenceVector(
                        analytical_support=0.5,
                        evidence_completeness=(1.0 if completeness["dispositions"] else 0.0),
                    ),
                    evidence_refs=[a.source_record_ref for a in no_disp if a.source_record_ref],
                    limitations=(
                        "Some teams close without a formal disposition; not "
                        "all of these are gaps."
                    ),
                ))

        # -- 5. Missing monitoring: critical assets with no alerts ---
        if completeness["assets"] and completeness["alerts"]:
            critical_assets = [a for a in dataset.assets
                                if a.criticality in ("critical", "high")]
            assets_with_alerts = set()
            for a_ in dataset.alerts:
                for ref in (a_.asset_refs or []):
                    assets_with_alerts.add(ref)
            silent_assets = [a_ for a_ in critical_assets
                             if a_.id not in assets_with_alerts]
            if (silent_assets
                    and len(critical_assets) >= self.thresholds.min_critical_assets):
                findings.append(Finding(
                    observation_id="",
                    rule_or_category="negative_space.missing_monitoring",
                    state="signal",
                    rationale=(
                        f"{len(silent_assets)} critical/high asset(s) produced no "
                        "alerts in the assessment period. A silent critical asset "
                        "may be a sensor gap."
                    ),
                    scoped_subjects=[a_.id for a_ in silent_assets],
                    statistic=float(len(silent_assets)),
                    effect=min(1.0, len(silent_assets) / max(1, len(critical_assets))),
                    threshold=float(self.thresholds.min_alerts_per_critical_asset),
                    confidence=ConfidenceVector(
                        analytical_support=0.6,
                        evidence_completeness=1.0,
                    ),
                    evidence_refs=[a_.id for a_ in silent_assets],  # asset IDs are referenceable
                    limitations=(
                        "A critical asset with zero alerts may be genuinely quiet "
                        "or genuinely blind. Check the sensor coverage map for "
                        "the asset before treating as a finding."
                    ),
                ))

        # -- 6. Unexpectedly low activity: many critical assets, few alerts
        if completeness["assets"] and completeness["alerts"]:
            critical_assets = [a for a in dataset.assets
                                if a.criticality in ("critical", "high")]
            if (len(critical_assets) >= self.thresholds.min_critical_assets
                    and len(dataset.alerts) < self.thresholds.min_alert_volume_for_low_activity):
                # Evidence for a low-activity claim is the (small) set
                # of alerts that DID fire plus the critical-asset
                # inventory the claim is measured against. A signal
                # finding must cite at least one evidence_ref
                # (SIH-EX-02); without either, the claim is
                # ungrounded and must not be emitted.
                low_activity_refs = [
                    a.source_record_ref for a in dataset.alerts
                    if a.source_record_ref]
                low_activity_refs += [a.id for a in critical_assets]
                if low_activity_refs:
                    findings.append(Finding(
                        observation_id="",
                        rule_or_category="negative_space.unexpectedly_low_activity",
                        state="signal",
                        rationale=(
                            f"Only {len(dataset.alerts)} alert(s) across "
                            f"{len(critical_assets)} critical/high asset(s). Either "
                            "the period is unusually quiet or the alert pipeline is "
                            "not firing."
                        ),
                        scoped_subjects=[a.id for a in critical_assets],
                        statistic=float(len(dataset.alerts)),
                        effect=min(1.0, (self.thresholds.min_alert_volume_for_low_activity
                                         - len(dataset.alerts))
                                    / self.thresholds.min_alert_volume_for_low_activity),
                        threshold=float(self.thresholds.min_alert_volume_for_low_activity),
                        confidence=ConfidenceVector(
                            analytical_support=0.4,
                            evidence_completeness=1.0,
                        ),
                        evidence_refs=low_activity_refs,
                        limitations=(
                            "Volume-based; legitimate quiet periods (e.g. "
                            "holiday weekends) will trip this finding. Peer-"
                            "benchmarked thresholds land in a later phase."
                        ),
                    ))

        return ObservationBatch(
            worker_name=self.name, detector_version=self.version,
            scope={
                "entity_id": run_context.entity_id,
                "assessment_id": run_context.assessment_id,
                "alerts_total": len(dataset.alerts),
                "cases_total": len(dataset.cases),
                "assets_total": len(dataset.assets),
                "data_completeness": completeness,
                "findings_count": len(findings),
            },
            state="signal" if any(f.state == "signal" for f in findings) else (
                "insufficient_data" if any(f.state == "insufficient_data" for f in findings)
                else "no_signal"),
            findings=findings,
            processing_metrics={"thresholds": {
                "min_investigation_steps": self.thresholds.min_investigation_steps,
                "min_alerts_per_critical_asset": self.thresholds.min_alerts_per_critical_asset,
                "min_critical_assets": self.thresholds.min_critical_assets,
                "min_alert_volume_for_low_activity": self.thresholds.min_alert_volume_for_low_activity,
            }},
        )
