import { familyOf } from "./labels";
import { fmtDuration, fmtNum, fmtPct } from "./format";

/**
 * What a finding's `statistic` and `threshold` mean, per rule, read from the
 * worker that emits it (satsa/analysis/workers/*). `comparable` is true only
 * when both numbers share a unit and can be drawn on one axis; otherwise the
 * UI shows them side by side without implying a scale.
 */
export type Unit = "seconds" | "ratio" | "count" | "steps" | "chars" | "value";

export interface Measure {
  statistic: string;
  threshold: string;
  unit: Unit;
  thresholdUnit?: Unit;
  comparable: boolean;
  /** which side of the threshold the observation fell on to raise the signal */
  flaggedWhen: "above" | "below" | "at_or_above" | "differs";
  /** whether the backend `effect` value is a bounded 0..1 magnitude worth showing */
  boundedEffect: boolean;
}

const M: Record<string, Measure> = {
  "execution_gap.fast_closure": { statistic: "Median time to close", threshold: "Fast-closure threshold", unit: "seconds", comparable: true, flaggedWhen: "below", boundedEffect: true },
  "execution_gap.ack_without_investigation": { statistic: "Alerts affected", threshold: "Minimum investigation steps", unit: "count", thresholdUnit: "steps", comparable: false, flaggedWhen: "below", boundedEffect: true },
  "execution_gap.critical_without_escalation": { statistic: "Critical alerts without escalation", threshold: "Trigger count", unit: "count", comparable: true, flaggedWhen: "at_or_above", boundedEffect: true },
  "execution_gap.repeated_investigation_pattern": { statistic: "Median note length", threshold: "Trivial-note ceiling", unit: "chars", comparable: true, flaggedWhen: "below", boundedEffect: true },
  "execution_gap.recurring_without_remediation": { statistic: "Most alerts absorbed by one case", threshold: "Recurrence threshold", unit: "count", comparable: true, flaggedWhen: "at_or_above", boundedEffect: true },
  "execution_gap.potential_metric_gaming": { statistic: "Average investigation steps per alert", threshold: "Maximum for a gaming pattern", unit: "steps", comparable: true, flaggedWhen: "below", boundedEffect: true },
  "negative_space.missing_investigation": { statistic: "Cases with no investigation", threshold: "Minimum steps per case", unit: "count", thresholdUnit: "steps", comparable: false, flaggedWhen: "at_or_above", boundedEffect: true },
  "negative_space.missing_escalation": { statistic: "Critical alerts without escalation", threshold: "Trigger count", unit: "count", comparable: true, flaggedWhen: "at_or_above", boundedEffect: true },
  "negative_space.missing_disposition": { statistic: "Closed alerts without disposition", threshold: "Trigger count", unit: "count", comparable: true, flaggedWhen: "at_or_above", boundedEffect: true },
  "negative_space.missing_monitoring": { statistic: "Silent critical assets", threshold: "Minimum alerts per critical asset", unit: "count", comparable: false, flaggedWhen: "at_or_above", boundedEffect: true },
  "negative_space.unexpectedly_low_activity": { statistic: "Alerts in period", threshold: "Expected minimum volume", unit: "count", comparable: true, flaggedWhen: "below", boundedEffect: true },
  "coverage_gap.missing_monitoring": { statistic: "Share of critical assets below floor", threshold: "Tolerated share", unit: "ratio", comparable: true, flaggedWhen: "above", boundedEffect: true },
  "evidence_completeness.missing_categories": { statistic: "Share of categories missing", threshold: "Tolerated share", unit: "ratio", comparable: true, flaggedWhen: "at_or_above", boundedEffect: true },
  "case_similarity.template_cluster": { statistic: "Cases sharing one signature", threshold: "Similarity threshold", unit: "ratio", comparable: true, flaggedWhen: "at_or_above", boundedEffect: true },
};

const ANOMALY_UNIT: Record<string, Unit> = {
  closure_time: "seconds",
  investigation_duration: "seconds",
  escalation_rate: "ratio",
  investigation_depth: "steps",
};

export function measureFor(rule: string): Measure {
  if (M[rule]) return M[rule];
  const family = familyOf(rule);
  const parts = rule.split(".");
  if (family === "anomaly") {
    const unit = ANOMALY_UNIT[parts[1]] ?? "value";
    return { statistic: "Observed value", threshold: "In-scope median", unit, comparable: true, flaggedWhen: parts[2] === "low" ? "below" : "above", boundedEffect: false };
  }
  if (family === "peer_benchmark") {
    const unit: Unit = parts[1]?.includes("rate") ? "ratio" : "value";
    return { statistic: "Entity value", threshold: "Peer median", unit, comparable: true, flaggedWhen: "differs", boundedEffect: false };
  }
  return { statistic: "Statistic", threshold: "Threshold", unit: "value", comparable: false, flaggedWhen: "differs", boundedEffect: false };
}

export function fmtMeasure(v: number | null, unit: Unit): string {
  if (v == null) return "n/a";
  switch (unit) {
    case "seconds":
      return fmtDuration(v);
    case "ratio":
      return fmtPct(v);
    case "count":
      return fmtNum(v, 0);
    case "steps":
      return `${fmtNum(v, 1)} step${v === 1 ? "" : "s"}`;
    case "chars":
      return `${fmtNum(v, 0)} chars`;
    default:
      return fmtNum(v, 2);
  }
}

export const FLAGGED_WHEN_TEXT: Record<Measure["flaggedWhen"], string> = {
  above: "Flagged because the observation is above the threshold",
  below: "Flagged because the observation is below the threshold",
  at_or_above: "Flagged because the observation reached the threshold",
  differs: "Flagged because the observation deviates from the reference",
};
