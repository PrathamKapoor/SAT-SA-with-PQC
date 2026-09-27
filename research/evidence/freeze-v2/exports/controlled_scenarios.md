<!-- generated from bundle controlled-final-seed-17; do not edit -->

| scenario | expected | emitted | tp | fp | fn | action_ok |
| --- | --- | --- | --- | --- | --- | --- |
| healthy | [] | [] | 0 | 0 | 0 | True |
| eg-fast-closure | ["execution_gap.fast_closure"] | ["execution_gap.fast_closure", "execution_gap.recurring_without_remediation"] | 1 | 1 | 0 | True |
| ns-missing-investigation | ["negative_space.missing_investigation"] | ["negative_space.missing_investigation"] | 1 | 0 | 0 | True |
| mixed | ["execution_gap.fast_closure", "negative_space.missing_monitoring"] | ["coverage_gap.missing_monitoring", "execution_gap.fast_closure", "execution_gap.recurring_without_remediation", "negative_space.missing_monitoring", "peer_benchmark.alerts_per_critical_asset.deviation", "peer_benchmark.monitoring_coverage.deviation", "peer_benchmark.recurrence_median.deviation"] | 2 | 5 | 0 | False |
| missing-evidence | ["evidence_completeness.missing_categories"] | ["evidence_completeness.missing_categories", "negative_space.missing_disposition"] | 1 | 1 | 0 | True |
