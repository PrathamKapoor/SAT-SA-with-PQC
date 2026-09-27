<!-- generated from bundle EXP-X03-external-failure-analysis; do not edit -->

| family | groups_evaluated | groups_flagged | flagging_rate | rule_type |
| --- | --- | --- | --- | --- |
| anomaly.investigation_depth.high | 50 | 50 | 1 | distribution (> 3 MAD within the entity; capped at 20) |
| case_similarity.template_cluster | 50 | 50 | 1 | existence (any cluster of >= 2 near-identical step sequences) |
| execution_gap.ack_without_investigation | 50 | 50 | 1 | existence (any medium+ alert whose case has < 2 steps) |
| negative_space.missing_investigation | 50 | 50 | 1 | existence (any case with 0 steps) |
| anomaly.closure_time.high | 50 | 49 | 0.98 | distribution (> 3 MAD within the entity; capped at 20) |
| anomaly.investigation_duration.high | 50 | 49 | 0.98 | distribution (> 3 MAD within the entity; capped at 20) |
| execution_gap.fast_closure | 50 | 43 | 0.86 | existence (any alert closed faster than its severity limit, >= 30 s) |
| execution_gap.repeated_investigation_pattern | 50 | 39 | 0.78 | rate or note-length rule (dominant step pair >= 60% of pairs, or median note < 30 chars; the source has no notes, so the adapter's empty notes always satisfy it) |
| execution_gap.critical_without_escalation | 50 | 26 | 0.52 | existence (any critical alert without escalation) |
| negative_space.missing_escalation | 50 | 26 | 0.52 | existence (expected escalation absent) |
| peer_benchmark.escalation_rate.deviation | 50 | 17 | 0.34 | cohort (> 2 MAD from peer median, >= 3 peers) |
| peer_benchmark.investigation_depth_median.deviation | 50 | 12 | 0.24 | cohort (> 2 MAD from peer median, >= 3 peers) |
| peer_benchmark.critical_closure_median_seconds.deviation | 50 | 11 | 0.22 | cohort (> 2 MAD from peer median, >= 3 peers) |
| anomaly.escalation_rate.low | 50 | 5 | 0.1 | distribution (> 3 MAD within the entity) |
| execution_gap.potential_metric_gaming | 50 | 5 | 0.1 | rate (critical/high closure rate >= 90% with <= 1.5 average steps) |
| workflow_reconstruction.sequence_chronology_mismatch | 50 | 1 | 0.02 | existence (any case whose step sequence disagrees with timestamps) |
